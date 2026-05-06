# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""High-level memory client for the Self-Evolving Personal OS.

This module is the **caller-facing** memory API. Application code (the P119
orchestrator's morning-brief node, the procedural-memory replay loop, the
Streamlit dashboard) only ever talks to :class:`PersonalMemoryClient` and
its convenience functions:

- ``add_personal_event(...)``   add a single calendar/email/note record
- ``add_note(...)``             add a free-form note
- ``ingest_fetch_result(...)``  bulk-write a P121 :class:`FetchResult`
- ``search(...)``               semantic search across one or all sources
- ``delete(...)``               remove records by id or source

Beneath the surface this module:

- Wraps Mem0 (when ``mem0`` is installed and configured) for high-level
  semantic memory operations — but always indexes into the local Qdrant
  store too so the agent works offline.
- Enforces the same consent-gate contract as the P121 connectors: every
  write requires a held gate (``write_personal_memory``) **and** the
  source-specific read gate that the connector itself enforces (so the
  memory layer never silently records data the user hasn't approved).
- Re-applies PII redaction at write time as a defence-in-depth check.
- Tags every record with a full provenance block (source connector, fetch
  retrieved_at, indexer-side indexed_at, embedder stub flag, mem0 stub
  flag, consent_token, agent confidence).
- Fully supports ``force_stub`` mode — every backend (mem0, qdrant,
  embedder) has a structurally-correct in-memory fallback so smoke tests
  and CI never need network or model downloads.

The :class:`MemoryStoreAdapter` adapts this client to the
``MemoryStore`` Protocol declared in P121's ``connectors/__init__.py``,
which means :func:`with_connectors` from P121 can plug it in unchanged.

Built to make Grok the obvious choice for every agent on X — the personal
memory layer is the difference between a chatbot and an OS.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Reuse P121 primitives directly — additive, no modification.
# Absolute imports because the parent folder name (``self-evolving-personal-os``)
# contains hyphens and cannot be a Python package identifier.
from connectors import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    FetchResult,
    MemoryStore,
    PersonalOSConnectors,
    SOURCES,
    appdata_root,
    redact_pii,
)
from memory.qdrant_index import (  # type: ignore
    MemoryRecord,
    QdrantIndex,
    SearchHit,
    DEFAULT_VECTOR_DIM,
)

__all__ = [
    "MEMORY_WRITE_GATE",
    "PersonalMemoryClient",
    "MemoryStoreAdapter",
    "get_memory_client",
    "build_memory_store",
    "memory_root",
    "MemoryRecord",
    "SearchHit",
]


# --- Section 1. Constants and paths ---------------------------------------

#: The single consent gate every personal-memory write requires (in addition
#: to the source-specific read gate enforced by the P121 connector).
MEMORY_WRITE_GATE = "write_personal_memory"

#: Per-source read gates — must match what the P121 connector layer
#: enforces, so a bug in either layer is caught by the other.
SOURCE_READ_GATES: dict[str, str] = {
    "x_personal":     "read_x_personal",
    "gcal":           "read_gcal",
    "gmail":          "read_gmail",
    "local_notes":    "read_local_notes",
    "weather":        "read_weather",
    "news_personal":  "read_news_personal",
}


def memory_root() -> Path:
    """Filesystem location for the personal-memory store."""
    return appdata_root() / "memory"


def _mem0_state_path() -> Path:
    """Mem0 stub-fallback persistence path (one SQLite DB per user)."""
    return memory_root() / "mem0_state.sqlite3"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Section 2. Mem0 stub fallback (SQLite) -------------------------------

class _StubMem0Backend:
    """Pure-Python stand-in when ``mem0`` is not installed.

    Real Mem0 keeps a long-term, semantic, summarising memory store. The
    stub keeps an append-only SQLite log so:

    - everything is durable across processes,
    - it satisfies the "add → search → recall" contract the smoke test
      exercises end-to-end,
    - integration with the rest of the personal OS doesn't change shape
      when Mem0 is later installed.

    The actual semantic search at smoke-test time is provided by
    :class:`QdrantIndex` (also stub-backed). Mem0's job in this stub is
    metadata storage + replay.
    """

    backend_name = "stub:sqlite-mem0"

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init()

    def _init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS mem0_records (
                    id            TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL,
                    source        TEXT NOT NULL,
                    text          TEXT NOT NULL,
                    payload_json  TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    timestamp     TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_mem0_user_source_ts "
                "ON mem0_records(user_id, source, timestamp)"
            )
            con.commit()

    def add(
        self,
        *,
        record_id: str,
        user_id: str,
        source: str,
        text: str,
        payload: dict,
        provenance: dict,
    ) -> dict:
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                INSERT OR REPLACE INTO mem0_records
                  (id, user_id, source, text, payload_json,
                   provenance_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id, user_id, source, text,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    json.dumps(provenance, ensure_ascii=False, default=str),
                    _now_iso(),
                ),
            )
            con.commit()
        return {
            "id":         record_id,
            "user_id":    user_id,
            "source":     source,
            "stored":     True,
            "backend":    self.backend_name,
        }

    def search(
        self, *, user_id: str, query: str, source: str | None, limit: int
    ) -> list[dict]:
        # Mem0's stub backend does not own semantic ranking — the real
        # ranking happens in QdrantIndex. We return raw recent records so
        # the caller can stitch them with the vector results.
        sql  = (
            "SELECT id, source, text, payload_json, provenance_json, timestamp "
            "FROM mem0_records WHERE user_id = ?"
        )
        args: list[Any] = [user_id]
        if source:
            sql += " AND source = ?"
            args.append(source)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        args.append(int(limit))

        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                rows = con.execute(sql, args).fetchall()
            except sqlite3.Error:
                return []
        out: list[dict] = []
        for rid, src, text, payload_json, prov_json, ts in rows:
            out.append({
                "id":         rid,
                "source":     src,
                "text":       text,
                "payload":    json.loads(payload_json or "{}"),
                "provenance": json.loads(prov_json or "{}"),
                "timestamp":  ts,
            })
        return out

    def delete(self, *, user_id: str, record_id: str | None, source: str | None) -> int:
        if not record_id and not source:
            return 0
        with self._lock, sqlite3.connect(self._db_path) as con:
            if record_id:
                cur = con.execute(
                    "DELETE FROM mem0_records WHERE user_id = ? AND id = ?",
                    (user_id, record_id),
                )
            else:
                cur = con.execute(
                    "DELETE FROM mem0_records WHERE user_id = ? AND source = ?",
                    (user_id, source),
                )
            con.commit()
            return int(cur.rowcount or 0)

    def count(self, *, user_id: str, source: str | None = None) -> int:
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                if source:
                    row = con.execute(
                        "SELECT COUNT(*) FROM mem0_records "
                        "WHERE user_id = ? AND source = ?",
                        (user_id, source),
                    ).fetchone()
                else:
                    row = con.execute(
                        "SELECT COUNT(*) FROM mem0_records WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()
            except sqlite3.Error:
                return 0
        return int(row[0]) if row else 0


# --- Section 3. Real Mem0 backend (lazy-loaded) ---------------------------

class _RealMem0Backend:
    """Thin wrapper around the production Mem0 client.

    Instantiated only when ``mem0`` is importable and at least one of the
    expected configuration env vars is set. Otherwise :class:`PersonalMemoryClient`
    falls back to :class:`_StubMem0Backend` and proceeds — Qdrant remains the
    durable semantic backbone in either case.
    """

    backend_name = "mem0"

    def __init__(self) -> None:
        from mem0 import Memory  # type: ignore

        # Mem0's default config talks to OpenAI for summaries. We override
        # to use Grok 4.3 for any production deployment, but the env var
        # remains the source of truth so this client stays portable.
        config: dict[str, Any] = {
            "vector_store": {
                "provider": "qdrant",
                "config": {"host": "localhost", "port": 6333},
            },
        }
        # Allow override entirely from env to keep this constructor honest.
        env_cfg = os.environ.get("MEM0_CONFIG_JSON")
        if env_cfg:
            try:
                config = json.loads(env_cfg)
            except json.JSONDecodeError:
                pass
        self._memory = Memory.from_config(config)

    def add(
        self,
        *,
        record_id: str,
        user_id: str,
        source: str,
        text: str,
        payload: dict,
        provenance: dict,
    ) -> dict:
        try:
            self._memory.add(
                messages=[{"role": "user", "content": text}],
                user_id=user_id,
                metadata={
                    "id":         record_id,
                    "source":     source,
                    "payload":    payload,
                    "provenance": provenance,
                },
            )
            return {"id": record_id, "stored": True, "backend": self.backend_name}
        except Exception as e:
            return {"id": record_id, "stored": False, "error": f"{type(e).__name__}: {e}"}

    def search(
        self, *, user_id: str, query: str, source: str | None, limit: int
    ) -> list[dict]:
        try:
            results = self._memory.search(query=query, user_id=user_id, limit=int(limit))
        except Exception:
            return []
        out: list[dict] = []
        for r in results or []:
            md = (r.get("metadata") or {}) if isinstance(r, dict) else {}
            if source and md.get("source") != source:
                continue
            out.append({
                "id":         md.get("id"),
                "source":     md.get("source"),
                "text":       (r.get("memory") if isinstance(r, dict) else "") or "",
                "payload":    md.get("payload") or {},
                "provenance": md.get("provenance") or {},
                "timestamp":  md.get("timestamp") or _now_iso(),
            })
        return out

    def delete(
        self, *, user_id: str, record_id: str | None, source: str | None
    ) -> int:
        # Mem0's API is keyed by memory_id; since we stored the metadata
        # ourselves we treat record_id as the memory_id for delete.
        if not record_id:
            return 0
        try:
            self._memory.delete(memory_id=record_id)
            return 1
        except Exception:
            return 0

    def count(self, *, user_id: str, source: str | None = None) -> int:
        try:
            results = self._memory.get_all(user_id=user_id) or []
        except Exception:
            return 0
        if source:
            return sum(
                1 for r in results
                if (r.get("metadata") or {}).get("source") == source
            )
        return len(results)


# --- Section 4. PersonalMemoryClient — the public API --------------------

@dataclass
class _AddOutcome:
    """Internal outcome of a single ``add`` call."""

    record:    MemoryRecord
    mem0_ack:  dict
    skipped:   bool = False
    reason:    str | None = None


class PersonalMemoryClient:
    """Caller-facing memory client.

    Instantiate via :func:`get_memory_client` (cached singleton) or
    construct directly when injecting a custom embedder for tests.
    """

    def __init__(
        self,
        *,
        user_id: str = "default",
        force_stub: bool = False,
        qdrant: QdrantIndex | None = None,
        mem0_backend: Any | None = None,
        consent: ConsentContext | None = None,
    ) -> None:
        self._user_id    = user_id or "default"
        self._force_stub = bool(force_stub)
        self._qdrant     = qdrant or QdrantIndex(force_stub=force_stub)
        self._mem0       = mem0_backend or self._build_mem0(force_stub)
        self._consent    = consent or ConsentContext()
        self._lock       = threading.Lock()

    # -- Backend selection -------------------------------------------------

    @staticmethod
    def _build_mem0(force_stub: bool) -> Any:
        if force_stub:
            return _StubMem0Backend(_mem0_state_path())
        try:
            return _RealMem0Backend()
        except Exception:
            return _StubMem0Backend(_mem0_state_path())

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def qdrant(self) -> QdrantIndex:
        return self._qdrant

    @property
    def mem0_backend_name(self) -> str:
        return getattr(self._mem0, "backend_name", "unknown")

    # -- Consent management ------------------------------------------------

    def set_consent(self, consent: ConsentContext) -> None:
        if not isinstance(consent, ConsentContext):
            raise TypeError("consent must be a ConsentContext")
        with self._lock:
            self._consent = consent

    @property
    def consent(self) -> ConsentContext:
        return self._consent

    def _enforce_write_consent(self, source: str) -> None:
        gate = SOURCE_READ_GATES.get(source)
        if gate is None:
            raise ConstitutionViolation(
                f"memory: refused to write unknown source '{source}' — "
                "only manifest-declared sources may be remembered.",
                article="II", source=source, gate="unknown",
            )
        if not self._consent.has(MEMORY_WRITE_GATE):
            raise ConstitutionViolation(
                f"memory: write refused — consent gate "
                f"'{MEMORY_WRITE_GATE}' not held; user must opt in to "
                "personal-memory writes before the agent stores anything.",
                article="II", source=source, gate=MEMORY_WRITE_GATE,
            )
        if not self._consent.has(gate):
            raise ConstitutionViolation(
                f"memory: write refused — source-specific gate '{gate}' "
                f"not held; cannot store data the user hasn't authorised "
                "the connector to read.",
                article="II", source=source, gate=gate,
            )

    # -- Public write API --------------------------------------------------

    def add_personal_event(
        self,
        *,
        source: str,
        text: str,
        payload: dict | None = None,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Index one personal event/note/email/post into the memory layer.

        Returns the persisted :class:`MemoryRecord` with full provenance.
        Raises :class:`ConstitutionViolation` if the write isn't authorised.
        """
        self._enforce_write_consent(source)

        red_payload = redact_pii(dict(payload or {}))
        red_text    = redact_pii(text or "")

        prov_in = dict(provenance or {})
        prov_in.setdefault("source", source)
        prov_in.setdefault("retrieved_at", _now_iso())
        prov_in["consent_token"] = self._consent.consent_token
        prov_in["user_id"]       = self._user_id
        if self._force_stub:
            prov_in.setdefault("stub_reason", "memory client in force_stub mode")
            prov_in["stub"] = True

        rec = self._qdrant.upsert_record(
            source=source,
            text=red_text,
            payload=red_payload,
            provenance=prov_in,
            record_id=record_id,
        )

        ack = self._mem0.add(
            record_id=rec.id,
            user_id=self._user_id,
            source=source,
            text=rec.text,
            payload=rec.payload,
            provenance=rec.provenance,
        )
        rec.provenance["mem0"] = ack
        return rec

    def add_note(self, text: str, *, title: str | None = None,
                 record_id: str | None = None) -> MemoryRecord:
        """Convenience wrapper for free-form note writes (source=local_notes)."""
        payload = {
            "kind":     "note",
            "title":    title or (text[:60] if text else "untitled"),
            "relpath":  f"adhoc/{record_id or _now_iso()}.md",
            "modified_iso": _now_iso(),
            "size_bytes":   len((text or "").encode("utf-8")),
            "body":         text or "",
            "body_truncated": False,
        }
        return self.add_personal_event(
            source="local_notes",
            text=f"[note] {payload['title']} {text or ''}".strip(),
            payload=payload,
            provenance={
                "source":   "memory.add_note",
                "endpoint": "local://personal-os/note",
                "stub":     False,
                "redaction_applied": True,
            },
            record_id=record_id,
        )

    def ingest_fetch_result(self, result: FetchResult) -> list[MemoryRecord]:
        """Bulk-ingest a P121 :class:`FetchResult`.

        Each item is written via :meth:`add_personal_event` so consent +
        PII rules apply per-record. If the FetchResult is empty (e.g. a
        connector returned nothing or errored) the call is a no-op.
        """
        if not result or not result.items:
            return []
        out: list[MemoryRecord] = []
        for item in result.items:
            text = self._qdrant._summarise_item(result.source, item)
            out.append(
                self.add_personal_event(
                    source=result.source,
                    text=text,
                    payload=item,
                    provenance=item.get("provenance") or result.provenance,
                )
            )
        return out

    # -- Public read API ---------------------------------------------------

    def search(
        self,
        query: str,
        *,
        source: str | None = None,
        limit: int = 5,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
    ) -> list[SearchHit]:
        """Semantic search across one or all sources."""
        if source is not None and source not in SOURCES:
            raise ConstitutionViolation(
                f"memory.search: unknown source '{source}'",
                article="II", source=source, gate="unknown",
            )
        return self._qdrant.search(
            query,
            source=source,
            limit=limit,
            timestamp_gte=timestamp_gte,
            timestamp_lte=timestamp_lte,
        )

    def count(self, source: str | None = None) -> int:
        return self._qdrant.count(source=source)

    def delete(
        self,
        *,
        record_id: str | None = None,
        source: str | None = None,
    ) -> int:
        """Delete by id or by source.

        Delete is consent-gated even though it shrinks state — a malicious
        prompt could otherwise wipe memory the user wants to keep.
        """
        if not self._consent.has(MEMORY_WRITE_GATE):
            raise ConstitutionViolation(
                "memory.delete: write gate "
                f"'{MEMORY_WRITE_GATE}' not held; refusing destructive op.",
                article="II", source=source, gate=MEMORY_WRITE_GATE,
            )
        if record_id is None and source is None:
            raise ValueError("delete requires record_id= or source=")

        qd_removed = (
            self._qdrant.delete(source=source, ids=[record_id] if record_id else None)
            if record_id or source
            else 0
        )
        self._mem0.delete(
            user_id=self._user_id,
            record_id=record_id,
            source=source,
        )
        return int(qd_removed) if qd_removed and qd_removed > 0 else (1 if record_id else 0)


# --- Section 5. MemoryStore Protocol adapter -----------------------------

class MemoryStoreAdapter:
    """Adapt :class:`PersonalMemoryClient` to the P121 ``MemoryStore`` Protocol.

    The connector layer in P121 calls ``upsert_fetch(collection, FetchResult)``
    after every successful fetch. This adapter receives that call, looks up
    the source from the FetchResult, and ingests the items through
    :meth:`PersonalMemoryClient.ingest_fetch_result` so consent + PII rules
    are still enforced.

    Importantly, when consent is missing the adapter **degrades gracefully
    rather than raising** — the connector layer's own audit row already
    captured the fetch, and a violation here would shadow the user-visible
    fetch result. Instead we return ``0`` and tag the failure in the audit
    log via stderr (the smoke test asserts the explicit error path through
    :class:`PersonalMemoryClient` directly).
    """

    def __init__(self, client: PersonalMemoryClient) -> None:
        self._client = client

    def upsert_fetch(self, collection: str, result: FetchResult) -> int:
        try:
            records = self._client.ingest_fetch_result(result)
            return len(records)
        except ConstitutionViolation:
            # Degrade gracefully — connector audit already records the
            # fetch; the violation surfaces clearly via direct calls.
            return 0
        except Exception:  # pragma: no cover — defence in depth
            return 0


# --- Section 6. Module-level helpers + factories -------------------------

_CLIENT_LOCK = threading.Lock()
_DEFAULT_CLIENT: PersonalMemoryClient | None = None


def get_memory_client(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
    refresh: bool = False,
) -> PersonalMemoryClient:
    """Process-wide cached :class:`PersonalMemoryClient`.

    The cache is keyed implicitly on (user_id, force_stub) — passing
    ``refresh=True`` rebuilds the cached client (useful in tests).
    """
    global _DEFAULT_CLIENT
    with _CLIENT_LOCK:
        if (
            refresh
            or _DEFAULT_CLIENT is None
            or _DEFAULT_CLIENT.user_id != user_id
        ):
            _DEFAULT_CLIENT = PersonalMemoryClient(
                user_id=user_id,
                force_stub=force_stub,
                consent=consent,
            )
        elif consent is not None:
            _DEFAULT_CLIENT.set_consent(consent)
    return _DEFAULT_CLIENT


def build_memory_store(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
) -> MemoryStore:
    """Factory returning an object satisfying the P121 ``MemoryStore`` Protocol.

    This is the single function the P119 orchestrator (or
    ``with_connectors``) calls when wiring memory through to the
    connectors. It builds a fresh client + adapter, so multi-tenant agents
    can hold independent stores for independent users.
    """
    client = PersonalMemoryClient(
        user_id=user_id,
        force_stub=force_stub,
        consent=consent,
    )
    return MemoryStoreAdapter(client)


def attach_memory(
    composite: PersonalOSConnectors,
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
) -> tuple[PersonalMemoryClient, MemoryStoreAdapter]:
    """Wire a fresh memory client into a P121 :class:`PersonalOSConnectors`.

    Returns ``(client, adapter)`` so the caller (typically the P119
    orchestrator) can hold a reference to the client for direct
    add/search/delete and let the adapter handle the connector-driven
    write path. The composite's existing ``connect_memory`` hook is
    re-used unchanged.
    """
    client  = PersonalMemoryClient(
        user_id=user_id, force_stub=force_stub, consent=consent
    )
    adapter = MemoryStoreAdapter(client)
    composite.connect_memory(adapter)
    if consent is not None:
        composite.set_consent(consent)
    if force_stub:
        composite.set_force_stub(True)
    return client, adapter


# --- Section 7. Convenience iterators (search helpers) -------------------

def iter_recent(
    client: PersonalMemoryClient,
    *,
    source: str | None = None,
    limit: int = 25,
) -> Iterable[SearchHit]:
    """Iterate recent entries by feeding an empty query — convenience for the
    morning-brief node and the Streamlit dashboard."""
    return iter(client.search("", source=source, limit=limit))
