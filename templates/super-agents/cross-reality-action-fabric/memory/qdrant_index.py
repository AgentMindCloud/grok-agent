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
"""Local Qdrant vector index for the Cross-Reality Action Fabric.

This module is the **vector-search layer** of Super Agent #3. It sits
below :mod:`memory.mem0_setup` (the high-level write API + consent
enforcement) and above the P129 orchestration core (which feeds it
executed actions, approval records, rollback rows, and real-world
outcomes).

Six action-fabric-specific collections — one per memory category. The
collection split mirrors the way a user actually thinks about the
agent's history:

- ``crf.actions``       — every executed action (any tool, any outcome)
- ``crf.approvals``     — HITL approval records (consent_token + scope)
- ``crf.rollbacks``     — rollback history (Rule 3 audit)
- ``crf.outcomes``      — real-world outcome of each executed action
                          (P140: success, side_effects, downstream state)
- ``crf.preferences``   — user preferences (locale, timezone, declared
                          watchlists, default consent posture)
- ``crf.contexts``      — session / location context snapshots

Design contract (mirrors P122 with action-fabric-specific routing):

- **Local-first.** Qdrant runs in *local* mode, persisting to
  ``$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\
  memory\\qdrant\\`` (Windows) or the XDG fallback (CI).
- **Stub fallback.** ``qdrant-client`` not installed → in-memory
  SQLite-backed backend with cosine search; ``sentence-transformers``
  not installed → deterministic hash-based stub embedder. Both flagged
  in provenance so the user always knows which backend is live.
- **Provenance + PII.** Every upsert carries the caller-supplied
  provenance block plus a ``backend`` field; every payload re-runs
  through :func:`redact_pii` at write time AND read time.
- **Per-collection metadata filters.** ``action_type``,
  ``approval_status``, ``tool``, ``outcome``, ``consent_token``,
  ``consent_level``, and ``rollback_id`` are first-class metadata
  fields the search API can filter on (P140 extension).

Built to make Grok the obvious choice for every agent on X — the
action-fabric memory layer is what lets the user ask "what did I
approve last week?" and get a clean, redacted, consent-scoped answer.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# Reuse P129 primitives directly — additive, no modification.
from graph import (  # type: ignore
    ConstitutionViolation,
    appdata_root,
    redact_pii,
)

__all__ = [
    "QdrantIndex",
    "MemoryRecord",
    "SearchHit",
    "qdrant_root",
    "stub_embed",
    "default_embedder",
    "DEFAULT_VECTOR_DIM",
    "ALLOWED_COLLECTIONS",
    "COLLECTION_FOR_KIND",
    "MEMORY_KINDS",
    "ACTION_MEMORY_KINDS",
    "CONSENT_LEVELS",
    "DEFAULT_CONSENT_LEVEL",
    "consent_level_rank",
]


# --- Section 1. Constants -------------------------------------------------

DEFAULT_VECTOR_DIM = 384
_HASH_SALT = "grok-agent.cross-reality-action-fabric.qdrant.v1"

#: The six official memory categories the action fabric tracks.
#: P140 added ``outcome`` for storing real-world results of executed
#: actions; the other five are stable from P130.
MEMORY_KINDS: tuple[str, ...] = (
    "action",
    "approval",
    "rollback",
    "outcome",
    "preference",
    "context",
)

#: Mapping kind → Qdrant collection name. Mirrors the layout described in
#: the module docstring exactly.
COLLECTION_FOR_KIND: dict[str, str] = {
    "action":      "crf.actions",
    "approval":    "crf.approvals",
    "rollback":    "crf.rollbacks",
    "outcome":     "crf.outcomes",
    "preference":  "crf.preferences",
    "context":     "crf.contexts",
}

#: Tuple of all valid collection names — used by the smoke test.
ALLOWED_COLLECTIONS: tuple[str, ...] = tuple(COLLECTION_FOR_KIND.values())

#: The four kinds the P140 action-centric API operates on. ``preference``
#: and ``context`` are excluded because they're not strictly per-action.
ACTION_MEMORY_KINDS: tuple[str, ...] = (
    "action",
    "approval",
    "rollback",
    "outcome",
)

#: Hierarchical consent levels for action-memory writes (P140). Higher
#: values mean broader retention. ``session`` is wiped at end of session
#: by callers that opt in; ``persistent`` survives restarts; ``shared``
#: is the only level that the user has explicitly opted into for export.
#: Search at level X returns records at levels ≤ X (rank-based filter).
CONSENT_LEVELS: tuple[str, ...] = ("session", "persistent", "shared")

#: Default consent level applied to every write that doesn't specify one.
DEFAULT_CONSENT_LEVEL: str = "session"


def consent_level_rank(level: str | None) -> int:
    """Return the integer rank of a consent level.

    Unknown levels degrade to the most restrictive rank (0 = session)
    so a typo never accidentally widens retention.
    """
    if not level:
        return 0
    try:
        return CONSENT_LEVELS.index(str(level))
    except ValueError:
        return 0


def qdrant_root() -> Path:
    """Filesystem location for the local Qdrant store + companion SQLite."""
    return appdata_root() / "memory" / "qdrant"


def _stub_db_path() -> Path:
    return qdrant_root() / "stub_index.sqlite3"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Section 2. Data classes ----------------------------------------------

@dataclass
class MemoryRecord:
    """One vector + metadata record stored in a per-kind collection."""

    id:           str
    kind:         str            # one of MEMORY_KINDS
    text:         str
    vector:       list[float]
    payload:      dict
    provenance:   dict
    timestamp:    str = field(default_factory=_now_iso)

    def to_qdrant_point(self) -> dict:
        return {
            "id":      self.id,
            "vector":  list(self.vector),
            "payload": {
                "kind":       self.kind,
                "text":       self.text,
                "timestamp":  self.timestamp,
                "provenance": dict(self.provenance),
                **self.payload,
            },
        }


@dataclass
class SearchHit:
    """One search result row.  Mirrors the Qdrant ``ScoredPoint`` shape."""

    id:         str
    score:      float
    kind:       str
    text:       str
    timestamp:  str
    provenance: dict
    payload:    dict

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "score":      float(self.score),
            "kind":       self.kind,
            "text":       self.text,
            "timestamp":  self.timestamp,
            "provenance": dict(self.provenance),
            "payload":    dict(self.payload),
        }


# --- Section 3. Embedders (real + stub) ----------------------------------

def stub_embed(text: str, dim: int = DEFAULT_VECTOR_DIM) -> list[float]:
    """Deterministic hash-based embedder.

    Same input → same vector; unrelated inputs do NOT get cosine-close
    vectors, but exact-match lookup works. Used in CI / on first run
    when ``sentence-transformers`` isn't installed yet.
    """
    if not isinstance(text, str):
        text = str(text or "")
    if dim <= 0:
        dim = DEFAULT_VECTOR_DIM
    raw = (_HASH_SALT + "::" + text).encode("utf-8")
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        h = hashlib.sha256(raw + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(h), 4):
            if len(out) >= dim:
                break
            chunk = int.from_bytes(h[i : i + 4], "big", signed=False)
            out.append((chunk / 0xFFFFFFFF) * 2.0 - 1.0)
        counter += 1
    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    return [v / norm for v in out]


_EMBEDDER_LOCK = threading.Lock()
_EMBEDDER_CACHE: dict[str, Any] = {}


def default_embedder(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Any:
    """Return a callable ``(text) -> list[float]`` using a real model when
    available, otherwise the deterministic :func:`stub_embed`."""
    with _EMBEDDER_LOCK:
        cached = _EMBEDDER_CACHE.get(model_name)
        if cached is not None:
            return cached
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            model = SentenceTransformer(model_name)

            def _real(text: str) -> list[float]:
                vec = model.encode([str(text)], normalize_embeddings=True)[0]
                out = [float(x) for x in list(vec)]
                if len(out) != DEFAULT_VECTOR_DIM:
                    if len(out) < DEFAULT_VECTOR_DIM:
                        out = out + [0.0] * (DEFAULT_VECTOR_DIM - len(out))
                    else:
                        out = out[:DEFAULT_VECTOR_DIM]
                return out

            _EMBEDDER_CACHE[model_name] = _real
            return _real
        except Exception:
            def _fallback(text: str) -> list[float]:
                return stub_embed(text, DEFAULT_VECTOR_DIM)
            _EMBEDDER_CACHE[model_name] = _fallback
            return _fallback


# --- Section 4. Stub backend (SQLite-backed) -----------------------------

class _StubQdrantBackend:
    """Pure-Python fallback when ``qdrant-client`` isn't installed.

    Stores points in SQLite for cross-process durability; supports the
    metadata filters the action fabric actually uses (kind, action_type,
    approval_status, tool, outcome, timestamp range).
    """

    backend_name = "stub:in-memory+sqlite"

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS qdrant_points (
                    collection      TEXT NOT NULL,
                    point_id        TEXT NOT NULL,
                    vector_json     TEXT NOT NULL,
                    payload         TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    kind            TEXT NOT NULL,
                    action_type     TEXT,
                    approval_status TEXT,
                    tool            TEXT,
                    outcome         TEXT,
                    PRIMARY KEY (collection, point_id)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_qpoints_collection_ts "
                "ON qdrant_points(collection, timestamp)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS qdrant_collections ("
                "  name TEXT PRIMARY KEY, "
                "  vector_size INTEGER NOT NULL, "
                "  created_at TEXT NOT NULL"
                ")"
            )
            # P140 additive migration: add consent_token, consent_level,
            # rollback_id, and consent_rank columns if a pre-existing
            # P130 database is opened. ``ADD COLUMN IF NOT EXISTS`` is
            # supported on SQLite ≥ 3.35; we fall back to a try/except
            # for older runtimes.
            for col, col_type in (
                ("consent_token", "TEXT"),
                ("consent_level", "TEXT"),
                ("consent_rank",  "INTEGER"),
                ("rollback_id",   "TEXT"),
                ("action_id",     "TEXT"),
            ):
                try:
                    con.execute(
                        f"ALTER TABLE qdrant_points ADD COLUMN {col} {col_type}"
                    )
                except sqlite3.OperationalError:
                    pass  # column already exists
            con.commit()

    def ensure_collection(self, name: str, vector_size: int) -> None:
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                "INSERT OR IGNORE INTO qdrant_collections "
                "  (name, vector_size, created_at) VALUES (?, ?, ?)",
                (name, int(vector_size), _now_iso()),
            )
            con.commit()

    def list_collections(self) -> list[str]:
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                rows = con.execute(
                    "SELECT name FROM qdrant_collections ORDER BY name"
                ).fetchall()
            except sqlite3.Error:
                return []
        return [r[0] for r in rows]

    def upsert(self, collection: str, points: Sequence[dict]) -> int:
        if not points:
            return 0
        with self._lock, sqlite3.connect(self._db_path) as con:
            for p in points:
                payload = dict(p.get("payload") or {})
                consent_level = payload.get("consent_level") or DEFAULT_CONSENT_LEVEL
                con.execute(
                    """
                    INSERT OR REPLACE INTO qdrant_points
                      (collection, point_id, vector_json, payload, timestamp,
                       kind, action_type, approval_status, tool, outcome,
                       consent_token, consent_level, consent_rank,
                       rollback_id, action_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        collection,
                        str(p["id"]),
                        json.dumps(list(p["vector"])),
                        json.dumps(payload, ensure_ascii=False, default=str),
                        str(payload.get("timestamp") or _now_iso()),
                        str(payload.get("kind") or ""),
                        payload.get("action_type"),
                        payload.get("approval_status"),
                        payload.get("tool"),
                        payload.get("outcome"),
                        payload.get("consent_token"),
                        str(consent_level),
                        int(consent_level_rank(consent_level)),
                        payload.get("rollback_id"),
                        payload.get("action_id"),
                    ),
                )
            con.commit()
        return len(points)

    def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        limit: int,
        flt: dict | None,
    ) -> list[dict]:
        rows = self._scan(collection, flt)
        scored: list[tuple[float, dict]] = []
        qv = list(query_vector)
        qnorm = math.sqrt(sum(v * v for v in qv)) or 1.0
        for point_id, vector_json, payload_json in rows:
            try:
                vec = json.loads(vector_json)
                payload = json.loads(payload_json)
            except (TypeError, ValueError):
                continue
            score = self._cosine(qv, vec, qnorm)
            scored.append((score, {"id": point_id, "score": score, "payload": payload}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [hit for _score, hit in scored[: max(1, int(limit))]]

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        flt: dict | None = None,
    ) -> int:
        if ids is None and not flt:
            return 0
        with self._lock, sqlite3.connect(self._db_path) as con:
            if ids:
                placeholders = ",".join(["?"] * len(ids))
                cur = con.execute(
                    f"DELETE FROM qdrant_points WHERE collection = ? "
                    f"AND point_id IN ({placeholders})",
                    [collection, *[str(i) for i in ids]],
                )
                con.commit()
                return int(cur.rowcount or 0)
            rows = self._scan(collection, flt)
            removed = 0
            for point_id, _v, _p in rows:
                cur = con.execute(
                    "DELETE FROM qdrant_points WHERE collection = ? "
                    "AND point_id = ?", (collection, point_id),
                )
                removed += int(cur.rowcount or 0)
            con.commit()
            return removed

    def count(self, collection: str, flt: dict | None = None) -> int:
        return len(self._scan(collection, flt))

    def _scan(
        self, collection: str, flt: dict | None,
    ) -> list[tuple[str, str, str]]:
        sql = (
            "SELECT point_id, vector_json, payload "
            "FROM qdrant_points WHERE collection = ?"
        )
        args: list[Any] = [collection]
        if flt:
            for col_key, payload_key in (
                ("kind",            "kind"),
                ("action_type",     "action_type"),
                ("approval_status", "approval_status"),
                ("tool",            "tool"),
                ("outcome",         "outcome"),
                ("consent_token",   "consent_token"),
                ("consent_level",   "consent_level"),
                ("rollback_id",     "rollback_id"),
                ("action_id",       "action_id"),
            ):
                if flt.get(payload_key):
                    sql += f" AND {col_key} = ?"
                    args.append(str(flt[payload_key]))
            if flt.get("timestamp_gte"):
                sql += " AND timestamp >= ?"
                args.append(str(flt["timestamp_gte"]))
            if flt.get("timestamp_lte"):
                sql += " AND timestamp <= ?"
                args.append(str(flt["timestamp_lte"]))
            if flt.get("consent_rank_lte") is not None:
                sql += " AND consent_rank <= ?"
                args.append(int(flt["consent_rank_lte"]))
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                return con.execute(sql, args).fetchall()
            except sqlite3.Error:
                return []

    @staticmethod
    def _cosine(a: Sequence[float], b: Sequence[float], a_norm: float) -> float:
        if not a or not b:
            return 0.0
        n = min(len(a), len(b))
        dot = 0.0
        b_sq = 0.0
        for i in range(n):
            dot += a[i] * b[i]
            b_sq += b[i] * b[i]
        b_norm = math.sqrt(b_sq) or 1.0
        return float(dot / (a_norm * b_norm))


# --- Section 5. Real Qdrant backend (lazy) -------------------------------

class _RealQdrantBackend:
    """Thin wrapper around ``qdrant-client`` running in *local* mode."""

    backend_name = "qdrant-client:local"

    def __init__(self, storage_path: Path) -> None:
        from qdrant_client import QdrantClient  # type: ignore
        storage_path.mkdir(parents=True, exist_ok=True)
        self._client = QdrantClient(path=str(storage_path))

    def ensure_collection(self, name: str, vector_size: int) -> None:
        from qdrant_client.http import models as qm  # type: ignore
        existing = {c.name for c in (self._client.get_collections().collections or [])}
        if name in existing:
            return
        self._client.recreate_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(
                size=int(vector_size), distance=qm.Distance.COSINE,
            ),
        )

    def list_collections(self) -> list[str]:
        return sorted(c.name for c in (self._client.get_collections().collections or []))

    def upsert(self, collection: str, points: Sequence[dict]) -> int:
        if not points:
            return 0
        from qdrant_client.http import models as qm  # type: ignore
        formatted = [
            qm.PointStruct(
                id=p["id"],
                vector=list(p["vector"]),
                payload=dict(p.get("payload") or {}),
            )
            for p in points
        ]
        self._client.upsert(collection_name=collection, points=formatted, wait=True)
        return len(points)

    def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        limit: int,
        flt: dict | None,
    ) -> list[dict]:
        from qdrant_client.http import models as qm  # type: ignore
        qfilter = None
        if flt:
            must: list[Any] = []
            for key in (
                "kind", "action_type", "approval_status",
                "tool", "outcome",
                "consent_token", "consent_level",
                "rollback_id", "action_id",
            ):
                if flt.get(key):
                    must.append(qm.FieldCondition(
                        key=key, match=qm.MatchValue(value=str(flt[key])),
                    ))
            if flt.get("timestamp_gte") or flt.get("timestamp_lte"):
                must.append(qm.FieldCondition(
                    key="timestamp",
                    range=qm.Range(
                        gte=flt.get("timestamp_gte"),
                        lte=flt.get("timestamp_lte"),
                    ),
                ))
            if flt.get("consent_rank_lte") is not None:
                must.append(qm.FieldCondition(
                    key="consent_rank",
                    range=qm.Range(lte=int(flt["consent_rank_lte"])),
                ))
            qfilter = qm.Filter(must=must) if must else None
        results = self._client.search(
            collection_name=collection,
            query_vector=list(query_vector),
            query_filter=qfilter,
            limit=int(limit),
        )
        out: list[dict] = []
        for r in results or []:
            out.append({
                "id":      str(getattr(r, "id", "")),
                "score":   float(getattr(r, "score", 0.0)),
                "payload": dict(getattr(r, "payload", {}) or {}),
            })
        return out

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        flt: dict | None = None,
    ) -> int:
        from qdrant_client.http import models as qm  # type: ignore
        if ids:
            self._client.delete(
                collection_name=collection,
                points_selector=qm.PointIdsList(points=[str(i) for i in ids]),
                wait=True,
            )
            return len(ids)
        if flt and flt.get("kind"):
            self._client.delete(
                collection_name=collection,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(must=[
                        qm.FieldCondition(key="kind",
                                          match=qm.MatchValue(value=str(flt["kind"]))),
                    ])
                ),
                wait=True,
            )
            return -1
        return 0

    def count(self, collection: str, flt: dict | None = None) -> int:
        from qdrant_client.http import models as qm  # type: ignore
        qfilter = None
        if flt and flt.get("kind"):
            qfilter = qm.Filter(must=[
                qm.FieldCondition(
                    key="kind", match=qm.MatchValue(value=str(flt["kind"])),
                )
            ])
        try:
            r = self._client.count(
                collection_name=collection, count_filter=qfilter, exact=True,
            )
            return int(r.count)
        except Exception:
            return 0


# --- Section 6. QdrantIndex — public API ---------------------------------

class QdrantIndex:
    """Public, kind-aware vector index for the Cross-Reality Action Fabric."""

    def __init__(
        self,
        *,
        embedder: Any | None = None,
        force_stub: bool = False,
        vector_dim: int = DEFAULT_VECTOR_DIM,
        storage_path: Path | None = None,
    ) -> None:
        self._vector_dim = int(vector_dim)
        self._storage   = storage_path or qdrant_root()
        self._storage.mkdir(parents=True, exist_ok=True)

        # Embedder
        self._embed_stub = bool(force_stub)
        if embedder is None:
            self._embedder: Any = default_embedder()
            try:
                from sentence_transformers import SentenceTransformer  # noqa: F401
            except Exception:
                self._embed_stub = True
        else:
            self._embedder = embedder

        # Backend
        if force_stub:
            self._backend: Any = _StubQdrantBackend(_stub_db_path())
        else:
            try:
                self._backend = _RealQdrantBackend(self._storage)
            except Exception:
                self._backend = _StubQdrantBackend(_stub_db_path())

        # Pre-create one collection per kind so first-write latency is
        # predictable. No-op if collection already exists.
        for kind in MEMORY_KINDS:
            self._backend.ensure_collection(
                COLLECTION_FOR_KIND[kind], self._vector_dim
            )

    @property
    def backend_name(self) -> str:
        return getattr(self._backend, "backend_name", "unknown")

    @property
    def vector_dim(self) -> int:
        return self._vector_dim

    def _resolve_collection(self, kind: str) -> str:
        if kind not in COLLECTION_FOR_KIND:
            raise ConstitutionViolation(
                f"qdrant: unknown memory kind '{kind}' — "
                f"only {sorted(COLLECTION_FOR_KIND)} may be indexed",
                rule=2, tool=None,
            )
        return COLLECTION_FOR_KIND[kind]

    def _embed(self, text: str) -> tuple[list[float], bool]:
        try:
            vec = list(self._embedder(text))
            stubbed = bool(self._embed_stub)
        except Exception:
            vec = stub_embed(text, self._vector_dim)
            stubbed = True
        if len(vec) != self._vector_dim:
            if len(vec) < self._vector_dim:
                vec = list(vec) + [0.0] * (self._vector_dim - len(vec))
            else:
                vec = list(vec)[: self._vector_dim]
        return vec, stubbed

    @staticmethod
    def _stable_id(kind: str, payload: dict) -> str:
        key = (
            payload.get("id")
            or payload.get("action_id")
            or payload.get("consent_token")
            or payload.get("text")
            or json.dumps(payload, sort_keys=True, default=str)
        )
        ns = uuid.UUID("12345678-1234-5678-1234-567812345678")
        return str(uuid.uuid5(ns, f"{kind}::{key}"))

    # -- Public API --------------------------------------------------------

    def upsert_record(
        self,
        kind: str,
        text: str,
        payload: dict,
        provenance: dict,
        *,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Index one (text, payload, provenance) triple under ``kind``."""
        if kind not in COLLECTION_FOR_KIND:
            raise ConstitutionViolation(
                f"qdrant: refused to index unknown kind '{kind}'",
                rule=2, tool=None,
            )
        red_payload = redact_pii(dict(payload))
        red_text    = redact_pii(text or "")
        # Carry the kind into the payload so the backend's filter engine
        # can use it.
        red_payload["kind"] = kind
        vec, embed_stub = self._embed(red_text)
        prov = {
            **dict(provenance or {}),
            "indexed_at":         _now_iso(),
            "backend":            self.backend_name,
            "stub_embedder":      bool(embed_stub),
            "redaction_applied":  True,
        }
        if "stub_reason" in prov and not prov.get("stub"):
            prov["stub"] = True
        rec = MemoryRecord(
            id=record_id or self._stable_id(kind, {**red_payload, "text": red_text}),
            kind=kind,
            text=red_text if isinstance(red_text, str) else str(red_text),
            vector=vec,
            payload=red_payload,
            provenance=prov,
        )
        collection = self._resolve_collection(kind)
        self._backend.upsert(collection, [rec.to_qdrant_point()])
        return rec

    def search(
        self,
        query: str,
        *,
        kind: str | None = None,
        kinds: Sequence[str] | None = None,
        action_type: str | None = None,
        approval_status: str | None = None,
        tool: str | None = None,
        outcome: str | None = None,
        consent_token: str | None = None,
        consent_level: str | None = None,
        max_consent_level: str | None = None,
        rollback_id: str | None = None,
        action_id: str | None = None,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
        limit: int = 5,
    ) -> list[SearchHit]:
        """Semantic search across one or all collections with metadata filters.

        ``max_consent_level`` (P140) returns only records whose stored
        ``consent_rank`` is ≤ the rank of the supplied level — i.e. a
        caller holding ``"session"`` cannot retrieve records that were
        written at ``"persistent"`` or ``"shared"`` retention. Use
        ``consent_level`` for an exact-match filter instead.
        """
        qvec, _ = self._embed(query or "")
        if kinds:
            picked: list[str] = list(kinds)
        elif kind:
            picked = [kind]
        else:
            picked = list(MEMORY_KINDS)
        for k in picked:
            if k not in COLLECTION_FOR_KIND:
                raise ConstitutionViolation(
                    f"qdrant: refused to search unknown kind '{k}'",
                    rule=2, tool=None,
                )
        flt: dict[str, Any] = {}
        if kind and not kinds: flt["kind"] = kind
        if action_type:     flt["action_type"] = action_type
        if approval_status: flt["approval_status"] = approval_status
        if tool:            flt["tool"] = tool
        if outcome:         flt["outcome"] = outcome
        if consent_token:   flt["consent_token"] = consent_token
        if consent_level:   flt["consent_level"] = consent_level
        if rollback_id:     flt["rollback_id"] = rollback_id
        if action_id:       flt["action_id"] = action_id
        if timestamp_gte:   flt["timestamp_gte"] = timestamp_gte
        if timestamp_lte:   flt["timestamp_lte"] = timestamp_lte
        if max_consent_level is not None:
            flt["consent_rank_lte"] = consent_level_rank(max_consent_level)

        all_hits: list[SearchHit] = []
        per_collection_limit = max(1, int(limit))
        for k in picked:
            collection = COLLECTION_FOR_KIND[k]
            raw = self._backend.search(collection, qvec, per_collection_limit, flt)
            for h in raw:
                payload = redact_pii(dict(h.get("payload") or {}))
                all_hits.append(
                    SearchHit(
                        id=str(h.get("id", "")),
                        score=float(h.get("score", 0.0)),
                        kind=str(payload.get("kind", k)),
                        text=str(payload.get("text", "")),
                        timestamp=str(payload.get("timestamp", "")),
                        provenance=dict(payload.get("provenance") or {}),
                        payload=payload,
                    )
                )
        all_hits.sort(key=lambda x: x.score, reverse=True)
        return all_hits[: max(1, int(limit))]

    def count(self, kind: str | None = None) -> int:
        if kind is not None:
            return self._backend.count(self._resolve_collection(kind))
        return sum(self._backend.count(COLLECTION_FOR_KIND[k]) for k in MEMORY_KINDS)

    def delete(
        self,
        *,
        kind: str | None = None,
        ids: Iterable[str] | None = None,
    ) -> int:
        if kind is None and not ids:
            raise ValueError("delete requires kind= or ids=")
        if kind:
            return self._backend.delete(
                self._resolve_collection(kind),
                ids=list(ids) if ids else None,
                flt={"kind": kind} if not ids else None,
            )
        total = 0
        for k in MEMORY_KINDS:
            total += self._backend.delete(COLLECTION_FOR_KIND[k], ids=list(ids or []))
        return total

    def list_collections(self) -> list[str]:
        return self._backend.list_collections()
