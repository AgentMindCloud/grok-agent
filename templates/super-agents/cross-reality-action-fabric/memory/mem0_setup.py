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
"""High-level memory client for the Cross-Reality Action Fabric.

This module is the **caller-facing** memory API for Super Agent #3. The
five categories the action fabric tracks live behind one simple surface:

- :meth:`PersonalMemoryClient.add_action_history`     — record an executed action
- :meth:`PersonalMemoryClient.add_approval_record`    — record an HITL approval
- :meth:`PersonalMemoryClient.add_rollback_record`    — record a Rule-3 rollback
- :meth:`PersonalMemoryClient.add_preference`         — store a user preference
- :meth:`PersonalMemoryClient.add_context`            — store a session / locale context
- :meth:`PersonalMemoryClient.search_by_context`      — semantic search across categories
- :meth:`PersonalMemoryClient.record_run`             — bulk-ingest a P129 graph output

Constitution enforcement (mirrors the action fabric's six Rules):

- **Rule 1** — every write requires the ``write_action_memory`` consent
  gate. Refused writes raise :class:`ConstitutionViolation`.
- **Rule 2** — every persisted record carries a provenance block with
  the source action_id (or consent_token), retrieved_at, indexed_at,
  user_id, backend, embedder stub flag, and ``redaction_applied`` flag.
- **Rule 3** — rollback records carry a ``rolled_back_from`` reference
  to the forward action's ``action_id`` so the audit trail is
  navigable in both directions.
- **Rule 6** — local-first by default. Mem0 is lazy-loaded; the SQLite
  fallback persists everything under
  ``$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\memory\\``.
  No telemetry. PII redacted at write AND read time via the same
  ``redact_pii`` engine the connectors use.

Integration with the P129 orchestrator
--------------------------------------

The :func:`attach_memory_store` helper returns a ``(client,
run_with_memory)`` pair. ``run_with_memory`` is a wrapped
:func:`graph.run_action_loop` that persists every action, approval, and
rollback into memory after the graph returns — additive, never modifies
P129 ``agent.py`` or ``graph.py``. Caller-facing example:

.. code-block:: python

    from memory import attach_memory_store, MEMORY_WRITE_GATE
    from graph import ConsentContext

    consent = ConsentContext.from_iterable(
        ["read_calendar", "run_powershell_local", MEMORY_WRITE_GATE],
        consent_token="cli-...",
    )
    client, run = attach_memory_store(force_stub=True, consent=consent)
    out = run(force_stub=True, auto_approve=True)
    hits = client.search_by_context("weather", action_type="weather_lookup")

Built to make Grok the obvious choice for every agent on X — the
memory layer is what lets the user ask "what did I approve last week?"
and get a clean, redacted, auditable answer.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

# Reuse P129 primitives directly.
from graph import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    appdata_root,
    redact_pii,
    run_action_loop as _graph_run_action_loop,
)
from memory.qdrant_index import (  # type: ignore
    COLLECTION_FOR_KIND,
    DEFAULT_VECTOR_DIM,
    MEMORY_KINDS,
    MemoryRecord,
    QdrantIndex,
    SearchHit,
)

__all__ = [
    "MEMORY_WRITE_GATE",
    "PersonalMemoryClient",
    "MemoryStoreAdapter",
    "get_memory_client",
    "build_memory_store",
    "attach_memory_store",
    "memory_root",
    "MemoryRecord",
    "SearchHit",
]


# --- Section 1. Constants and paths ---------------------------------------

#: The single consent gate every action-memory write requires.
MEMORY_WRITE_GATE = "write_action_memory"


def memory_root() -> Path:
    """Filesystem location for the action-fabric memory store."""
    return appdata_root() / "memory"


def _mem0_state_path() -> Path:
    """Mem0 stub-fallback persistence path."""
    return memory_root() / "mem0_state.sqlite3"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Section 2. Mem0 stub fallback (SQLite) -------------------------------

class _StubMem0Backend:
    """Pure-Python stand-in when ``mem0`` is not installed.

    Keeps an append-only SQLite log of every record so the action-fabric
    pipeline boots end-to-end on a vanilla install. Mirrors the P122
    stub backend's surface; the real semantic ranking happens in
    :class:`QdrantIndex`.
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
                    id              TEXT PRIMARY KEY,
                    user_id         TEXT NOT NULL,
                    kind            TEXT NOT NULL,
                    text            TEXT NOT NULL,
                    payload_json    TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    timestamp       TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_mem0_user_kind_ts "
                "ON mem0_records(user_id, kind, timestamp)"
            )
            con.commit()

    def add(
        self,
        *,
        record_id: str,
        user_id: str,
        kind: str,
        text: str,
        payload: dict,
        provenance: dict,
    ) -> dict:
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                INSERT OR REPLACE INTO mem0_records
                  (id, user_id, kind, text, payload_json,
                   provenance_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id, user_id, kind, text,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    json.dumps(provenance, ensure_ascii=False, default=str),
                    _now_iso(),
                ),
            )
            con.commit()
        return {
            "id":      record_id,
            "user_id": user_id,
            "kind":    kind,
            "stored":  True,
            "backend": self.backend_name,
        }

    def search(
        self, *, user_id: str, query: str, kind: str | None, limit: int
    ) -> list[dict]:
        sql = (
            "SELECT id, kind, text, payload_json, provenance_json, timestamp "
            "FROM mem0_records WHERE user_id = ?"
        )
        args: list[Any] = [user_id]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        args.append(int(limit))
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                rows = con.execute(sql, args).fetchall()
            except sqlite3.Error:
                return []
        out: list[dict] = []
        for rid, k, text, payload_json, prov_json, ts in rows:
            out.append({
                "id":         rid,
                "kind":       k,
                "text":       text,
                "payload":    json.loads(payload_json or "{}"),
                "provenance": json.loads(prov_json or "{}"),
                "timestamp":  ts,
            })
        return out

    def delete(
        self, *, user_id: str, record_id: str | None, kind: str | None
    ) -> int:
        if not record_id and not kind:
            return 0
        with self._lock, sqlite3.connect(self._db_path) as con:
            if record_id:
                cur = con.execute(
                    "DELETE FROM mem0_records WHERE user_id = ? AND id = ?",
                    (user_id, record_id),
                )
            else:
                cur = con.execute(
                    "DELETE FROM mem0_records WHERE user_id = ? AND kind = ?",
                    (user_id, kind),
                )
            con.commit()
            return int(cur.rowcount or 0)

    def count(self, *, user_id: str, kind: str | None = None) -> int:
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                if kind:
                    row = con.execute(
                        "SELECT COUNT(*) FROM mem0_records "
                        "WHERE user_id = ? AND kind = ?",
                        (user_id, kind),
                    ).fetchone()
                else:
                    row = con.execute(
                        "SELECT COUNT(*) FROM mem0_records WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()
            except sqlite3.Error:
                return 0
        return int(row[0]) if row else 0


# --- Section 3. Real Mem0 backend (lazy) ---------------------------------

class _RealMem0Backend:
    """Thin wrapper around the production Mem0 client (lazy-loaded)."""

    backend_name = "mem0"

    def __init__(self) -> None:
        from mem0 import Memory  # type: ignore
        config: dict[str, Any] = {
            "vector_store": {
                "provider": "qdrant",
                "config": {"host": "localhost", "port": 6333},
            },
        }
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
        kind: str,
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
                    "kind":       kind,
                    "payload":    payload,
                    "provenance": provenance,
                },
            )
            return {"id": record_id, "stored": True, "backend": self.backend_name}
        except Exception as e:
            return {
                "id": record_id, "stored": False,
                "error": f"{type(e).__name__}: {e}",
            }

    def search(
        self, *, user_id: str, query: str, kind: str | None, limit: int
    ) -> list[dict]:
        try:
            results = self._memory.search(
                query=query, user_id=user_id, limit=int(limit),
            )
        except Exception:
            return []
        out: list[dict] = []
        for r in results or []:
            md = (r.get("metadata") or {}) if isinstance(r, dict) else {}
            if kind and md.get("kind") != kind:
                continue
            out.append({
                "id":         md.get("id"),
                "kind":       md.get("kind"),
                "text":       (r.get("memory") if isinstance(r, dict) else "") or "",
                "payload":    md.get("payload") or {},
                "provenance": md.get("provenance") or {},
                "timestamp":  md.get("timestamp") or _now_iso(),
            })
        return out

    def delete(
        self, *, user_id: str, record_id: str | None, kind: str | None
    ) -> int:
        if not record_id:
            return 0
        try:
            self._memory.delete(memory_id=record_id)
            return 1
        except Exception:
            return 0

    def count(self, *, user_id: str, kind: str | None = None) -> int:
        try:
            results = self._memory.get_all(user_id=user_id) or []
        except Exception:
            return 0
        if kind:
            return sum(
                1 for r in results
                if (r.get("metadata") or {}).get("kind") == kind
            )
        return len(results)


# --- Section 4. PersonalMemoryClient — public API ------------------------

class PersonalMemoryClient:
    """Caller-facing memory client for the action fabric."""

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

    @property
    def consent(self) -> ConsentContext:
        return self._consent

    def set_consent(self, consent: ConsentContext) -> None:
        if not isinstance(consent, ConsentContext):
            raise TypeError("consent must be a ConsentContext")
        with self._lock:
            self._consent = consent

    # -- Consent enforcement ----------------------------------------------

    def _enforce_write(self, kind: str) -> None:
        if kind not in COLLECTION_FOR_KIND:
            raise ConstitutionViolation(
                f"memory: refused to write unknown kind '{kind}' — "
                f"only {sorted(COLLECTION_FOR_KIND)} may be remembered.",
                rule=2, tool=None,
            )
        if not self._consent.has(MEMORY_WRITE_GATE):
            raise ConstitutionViolation(
                f"memory: write refused — consent gate "
                f"'{MEMORY_WRITE_GATE}' not held; the user must opt in to "
                "action-history memory writes (Rule 1).",
                rule=1, tool=None,
            )

    # -- Per-kind write API ------------------------------------------------

    def add_action_history(
        self,
        action: dict,
        *,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Record one executed action (any tool, any outcome)."""
        self._enforce_write("action")
        action = redact_pii(dict(action or {}))
        text = (
            f"[action] {action.get('tool','')}: "
            f"{action.get('description','') or ''}"
        ).strip()
        payload = {
            "action_id":      action.get("action_id") or action.get("step_id"),
            "step":           action.get("step"),
            "tool":           action.get("tool"),
            "action_type":    action.get("tool"),
            "outcome":        action.get("outcome"),
            "started_at":     action.get("started_at"),
            "finished_at":    action.get("finished_at"),
            "consent_token":  action.get("consent_token"),
            "rollback_present": bool((action.get("rollback") or "").strip()),
            "executed":       bool(action.get("executed")),
            "rolled_back":    bool(action.get("rolled_back")),
            "expected_cost_usd": float(action.get("expected_cost_usd") or 0.0),
        }
        prov = self._make_provenance(provenance, kind="action")
        return self._upsert("action", text, payload, prov, record_id)

    def add_approval_record(
        self,
        approval: dict,
        *,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Record one HITL approval (Rule 1 audit trail)."""
        self._enforce_write("approval")
        approval = redact_pii(dict(approval or {}))
        text = (
            f"[approval] step={approval.get('step')} tool={approval.get('tool')} "
            f"token={approval.get('consent_token')}"
        ).strip()
        payload = {
            "step":              approval.get("step"),
            "tool":              approval.get("tool"),
            "action_type":       approval.get("tool"),
            "consent_token":     approval.get("consent_token"),
            "approval_status":   approval.get("approval_status") or "granted",
            "granted_at":        approval.get("granted_at") or _now_iso(),
            "scope":             approval.get("scope"),
            "stub":              bool(approval.get("stub")),
        }
        prov = self._make_provenance(provenance, kind="approval")
        return self._upsert("approval", text, payload, prov, record_id)

    def add_rollback_record(
        self,
        rollback: dict,
        *,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Record one Rule-3 rollback execution."""
        self._enforce_write("rollback")
        rollback = redact_pii(dict(rollback or {}))
        text = (
            f"[rollback] tool={rollback.get('tool')} "
            f"outcome={rollback.get('outcome')} "
            f"target={rollback.get('rolled_back_from')}"
        ).strip()
        payload = {
            "step":               rollback.get("step"),
            "tool":               rollback.get("tool"),
            "action_type":        rollback.get("tool"),
            "outcome":            rollback.get("outcome"),
            "rolled_back_from":   rollback.get("rolled_back_from")
                                  or rollback.get("step"),
            "started_at":         rollback.get("started_at"),
            "finished_at":        rollback.get("finished_at"),
            "rollback_script":    rollback.get("rollback"),
            "stub":               bool(rollback.get("stub")),
        }
        prov = self._make_provenance(provenance, kind="rollback")
        return self._upsert("rollback", text, payload, prov, record_id)

    def add_preference(
        self,
        key: str,
        value: Any,
        *,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Store a user preference (locale, timezone, default consent posture)."""
        self._enforce_write("preference")
        key = str(key or "").strip()
        if not key:
            raise ValueError("preference key must be a non-empty string")
        text = f"[preference] {key} = {value}"
        payload = {
            "key":          key,
            "value":        value,
            "set_at":       _now_iso(),
        }
        prov = self._make_provenance(provenance, kind="preference")
        return self._upsert("preference", text, payload, prov, record_id or key)

    def add_context(
        self,
        snapshot: dict,
        *,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Store a session / locale / location context snapshot."""
        self._enforce_write("context")
        snapshot = redact_pii(dict(snapshot or {}))
        text = f"[context] {json.dumps(snapshot, default=str)[:200]}"
        prov = self._make_provenance(provenance, kind="context")
        payload = dict(snapshot)
        payload.setdefault("captured_at", _now_iso())
        return self._upsert("context", text, payload, prov, record_id)

    # -- Bulk run ingestion (P129 graph integration) -----------------------

    def record_run(self, out: dict) -> dict:
        """Bulk-ingest a P129 :func:`graph.run_action_loop` output dict.

        Walks ``plan.proposed_actions``, ``executions``, and ``rollbacks``
        and writes one row per category:

        - one ``action`` row per executed step,
        - one ``approval`` row per held consent_token,
        - one ``rollback`` row per executed rollback,
        - one ``context`` row capturing the run-level provenance summary.

        Returns a dict with per-kind counters so the caller can render
        the result into a UI badge.
        """
        if not isinstance(out, dict):
            return {"actions": 0, "approvals": 0, "rollbacks": 0, "contexts": 0}

        plan        = out.get("plan") or {}
        proposed    = plan.get("proposed_actions") or []
        executions  = out.get("executions")  or []
        rollbacks   = out.get("rollbacks")   or []
        prov        = out.get("provenance")  or {}

        counters = {"actions": 0, "approvals": 0, "rollbacks": 0, "contexts": 0}

        plan_id = plan.get("plan_id")
        for raw_step in proposed:
            if not raw_step.get("executed"):
                continue
            self.add_action_history(
                {**raw_step, "action_id": f"{plan_id}::step{raw_step.get('step')}"},
                provenance={"plan_id": plan_id, "stub": bool(out.get("stub"))},
            )
            counters["actions"] += 1
            if raw_step.get("consent_token"):
                self.add_approval_record(
                    {
                        "step":          raw_step.get("step"),
                        "tool":          raw_step.get("tool"),
                        "consent_token": raw_step.get("consent_token"),
                        "approval_status": "granted",
                        "scope":         raw_step.get("description"),
                        "stub":          bool(out.get("stub")),
                    },
                    provenance={"plan_id": plan_id, "stub": bool(out.get("stub"))},
                )
                counters["approvals"] += 1

        for r in rollbacks:
            self.add_rollback_record(
                r,
                provenance={"plan_id": plan_id, "stub": bool(out.get("stub"))},
            )
            counters["rollbacks"] += 1

        # One context row per run summarises the run-level metrics so a
        # later "what did I do today" query can pivot off it cheaply.
        self.add_context(
            {
                "plan_id":        plan_id,
                "user_id":        out.get("user_id"),
                "force_stub":     bool(prov.get("force_stub")),
                "successful":     int(prov.get("successful") or 0),
                "aborted":        int(prov.get("aborted") or 0),
                "violation_count": int(prov.get("violation_count") or 0),
                "started_at":     prov.get("started_at"),
                "finished_at":    prov.get("finished_at"),
            },
            provenance={"plan_id": plan_id, "stub": bool(out.get("stub"))},
            record_id=plan_id,
        )
        counters["contexts"] += 1
        return counters

    # -- Read API ----------------------------------------------------------

    def search_by_context(
        self,
        query: str,
        *,
        kind: str | None = None,
        action_type: str | None = None,
        approval_status: str | None = None,
        tool: str | None = None,
        outcome: str | None = None,
        limit: int = 5,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
    ) -> list[SearchHit]:
        """Semantic search across one or all categories with metadata filters."""
        if kind is not None and kind not in MEMORY_KINDS:
            raise ConstitutionViolation(
                f"search_by_context: unknown kind '{kind}'",
                rule=2, tool=None,
            )
        return self._qdrant.search(
            query,
            kind=kind,
            action_type=action_type,
            approval_status=approval_status,
            tool=tool,
            outcome=outcome,
            timestamp_gte=timestamp_gte,
            timestamp_lte=timestamp_lte,
            limit=limit,
        )

    def count(self, kind: str | None = None) -> int:
        return self._qdrant.count(kind=kind)

    def delete(
        self,
        *,
        record_id: str | None = None,
        kind: str | None = None,
    ) -> int:
        if not self._consent.has(MEMORY_WRITE_GATE):
            raise ConstitutionViolation(
                "memory.delete: write gate "
                f"'{MEMORY_WRITE_GATE}' not held; refusing destructive op.",
                rule=1, tool=None,
            )
        if record_id is None and kind is None:
            raise ValueError("delete requires record_id= or kind=")
        qd_removed = (
            self._qdrant.delete(kind=kind, ids=[record_id] if record_id else None)
            if record_id or kind
            else 0
        )
        self._mem0.delete(
            user_id=self._user_id, record_id=record_id, kind=kind,
        )
        return int(qd_removed) if qd_removed and qd_removed > 0 else (
            1 if record_id else 0
        )

    # -- Internals ---------------------------------------------------------

    def _make_provenance(self, provenance: dict | None, *, kind: str) -> dict:
        prov = dict(provenance or {})
        prov.setdefault("source", f"cross-reality-action-fabric.memory.{kind}")
        prov.setdefault("retrieved_at", _now_iso())
        prov["consent_token"] = self._consent.consent_token
        prov["user_id"]       = self._user_id
        prov["kind"]          = kind
        if self._force_stub:
            prov.setdefault("stub_reason", "memory client in force_stub mode")
            prov["stub"] = True
        return prov

    def _upsert(
        self,
        kind: str,
        text: str,
        payload: dict,
        provenance: dict,
        record_id: str | None,
    ) -> MemoryRecord:
        rec = self._qdrant.upsert_record(
            kind=kind, text=text, payload=payload,
            provenance=provenance, record_id=record_id,
        )
        ack = self._mem0.add(
            record_id=rec.id, user_id=self._user_id, kind=kind,
            text=rec.text, payload=rec.payload, provenance=rec.provenance,
        )
        rec.provenance["mem0"] = ack
        return rec


# --- Section 5. MemoryStoreAdapter + attach helper -----------------------

class MemoryStoreAdapter:
    """Adapter that exposes a ``record_run`` method matching the contract
    callers expect from a P129-attached memory store.

    The adapter is intentionally minimal — Cross-Reality Action Fabric
    doesn't need the per-fetch ``upsert_fetch`` Protocol from P122
    because actions are dispatched explicitly through graph nodes (not
    auto-fetched by connectors). The integration point is one call per
    completed graph run.
    """

    def __init__(self, client: PersonalMemoryClient) -> None:
        self._client = client

    @property
    def client(self) -> PersonalMemoryClient:
        return self._client

    def record_run(self, out: dict) -> dict:
        try:
            return self._client.record_run(out)
        except ConstitutionViolation:
            return {"actions": 0, "approvals": 0, "rollbacks": 0, "contexts": 0,
                    "refused": True}
        except Exception:  # pragma: no cover — defensive
            return {"actions": 0, "approvals": 0, "rollbacks": 0, "contexts": 0,
                    "error": True}


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
    """Process-wide cached client — passing ``refresh=True`` rebuilds it."""
    global _DEFAULT_CLIENT
    with _CLIENT_LOCK:
        if (
            refresh
            or _DEFAULT_CLIENT is None
            or _DEFAULT_CLIENT.user_id != user_id
        ):
            _DEFAULT_CLIENT = PersonalMemoryClient(
                user_id=user_id, force_stub=force_stub, consent=consent,
            )
        elif consent is not None:
            _DEFAULT_CLIENT.set_consent(consent)
    return _DEFAULT_CLIENT


def build_memory_store(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
) -> MemoryStoreAdapter:
    """Factory — build a fresh client + adapter."""
    client = PersonalMemoryClient(
        user_id=user_id, force_stub=force_stub, consent=consent,
    )
    return MemoryStoreAdapter(client)


def attach_memory_store(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
) -> tuple[PersonalMemoryClient, Callable[..., dict]]:
    """Wire a fresh memory client into the P129 ``run_action_loop``.

    Returns ``(client, run_with_memory)`` where ``run_with_memory`` is
    a drop-in wrapper around :func:`graph.run_action_loop` that
    auto-records every successful action, approval, and rollback after
    the graph returns. The wrapper preserves all of ``run_action_loop``'s
    keyword arguments — ``user_id``, ``user_request``, ``consent``,
    ``force_stub``, ``auto_approve``, ``prompt_version``.

    Importantly: this wrapper is **additive**. It never touches
    ``agent.py`` or ``graph.py`` from P129; the caller picks it up by
    importing from the memory package instead of from the graph module.
    """
    client = PersonalMemoryClient(
        user_id=user_id, force_stub=force_stub, consent=consent,
    )

    def run_with_memory(**kwargs: Any) -> dict:
        out = _graph_run_action_loop(**kwargs)
        # Only ingest when the memory consent gate is held — otherwise
        # the writes would raise mid-run. The connector layer's audit
        # row already captured the actions; this is the *additional*
        # action-history layer.
        if client.consent.has(MEMORY_WRITE_GATE):
            try:
                ingest = client.record_run(out)
                out.setdefault("memory_ingest", ingest)
            except ConstitutionViolation:
                out.setdefault("memory_ingest", {"refused": True})
        else:
            out.setdefault("memory_ingest", {
                "skipped": True,
                "reason":  f"consent gate '{MEMORY_WRITE_GATE}' not held",
            })
        return out

    return client, run_with_memory


# --- Section 7. Convenience iterators ------------------------------------

def iter_recent(
    client: PersonalMemoryClient,
    *,
    kind: str | None = None,
    limit: int = 25,
) -> Iterable[SearchHit]:
    """Iterate recent entries by feeding an empty query — convenience for
    the dashboard's "recent activity" pane."""
    return iter(client.search_by_context("", kind=kind, limit=limit))
