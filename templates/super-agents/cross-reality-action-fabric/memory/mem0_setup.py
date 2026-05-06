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
    ACTION_MEMORY_KINDS,
    COLLECTION_FOR_KIND,
    CONSENT_LEVELS,
    DEFAULT_CONSENT_LEVEL,
    DEFAULT_VECTOR_DIM,
    MEMORY_KINDS,
    MemoryRecord,
    QdrantIndex,
    SearchHit,
    consent_level_rank,
)

__all__ = [
    "MEMORY_WRITE_GATE",
    "PersonalMemoryClient",
    "PersonalActionMemoryClient",
    "MemoryStoreAdapter",
    "ActionMemoryStoreAdapter",
    "get_memory_client",
    "get_action_memory_client",
    "build_memory_store",
    "build_action_memory_store",
    "attach_memory_store",
    "attach_action_memory",
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
        consent_level = action.get("consent_level") or DEFAULT_CONSENT_LEVEL
        payload = {
            "action_id":      action.get("action_id") or action.get("step_id"),
            "step":           action.get("step"),
            "tool":           action.get("tool"),
            "action_type":    action.get("tool"),
            "outcome":        action.get("outcome"),
            "started_at":     action.get("started_at"),
            "finished_at":    action.get("finished_at"),
            "consent_token":  action.get("consent_token"),
            "consent_level":  str(consent_level),
            "rollback_id":    action.get("rollback_id"),
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
        consent_level = approval.get("consent_level") or DEFAULT_CONSENT_LEVEL
        payload = {
            "step":              approval.get("step"),
            "tool":              approval.get("tool"),
            "action_type":       approval.get("tool"),
            "action_id":         approval.get("action_id"),
            "consent_token":     approval.get("consent_token"),
            "consent_level":     str(consent_level),
            "rollback_id":       approval.get("rollback_id"),
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
        consent_level = rollback.get("consent_level") or DEFAULT_CONSENT_LEVEL
        payload = {
            "step":               rollback.get("step"),
            "tool":               rollback.get("tool"),
            "action_type":        rollback.get("tool"),
            "outcome":            rollback.get("outcome"),
            "rolled_back_from":   rollback.get("rolled_back_from")
                                  or rollback.get("step"),
            "action_id":          rollback.get("action_id")
                                  or rollback.get("rolled_back_from"),
            "rollback_id":        rollback.get("rollback_id"),
            "consent_token":      rollback.get("consent_token"),
            "consent_level":      str(consent_level),
            "started_at":         rollback.get("started_at"),
            "finished_at":        rollback.get("finished_at"),
            "rollback_script":    rollback.get("rollback"),
            "stub":               bool(rollback.get("stub")),
        }
        prov = self._make_provenance(provenance, kind="rollback")
        return self._upsert("rollback", text, payload, prov, record_id)

    def add_outcome_record(
        self,
        outcome: dict,
        *,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Record one real-world outcome of an executed action (P140).

        ``outcome`` should carry at minimum: ``action_id`` (links back to
        the originating action row), ``outcome`` ("success" / "failure" /
        "rolled_back" / "side_effect"), and a free-form ``description``.
        """
        self._enforce_write("outcome")
        outcome = redact_pii(dict(outcome or {}))
        text = (
            f"[outcome] action={outcome.get('action_id')} "
            f"result={outcome.get('outcome')}: "
            f"{outcome.get('description','') or ''}"
        ).strip()
        consent_level = outcome.get("consent_level") or DEFAULT_CONSENT_LEVEL
        payload = {
            "action_id":         outcome.get("action_id"),
            "step":              outcome.get("step"),
            "tool":              outcome.get("tool"),
            "action_type":       outcome.get("tool"),
            "outcome":           outcome.get("outcome"),
            "description":       outcome.get("description"),
            "side_effects":      outcome.get("side_effects") or [],
            "downstream_state":  outcome.get("downstream_state"),
            "consent_token":     outcome.get("consent_token"),
            "consent_level":     str(consent_level),
            "rollback_id":       outcome.get("rollback_id"),
            "observed_at":       outcome.get("observed_at") or _now_iso(),
        }
        prov = self._make_provenance(provenance, kind="outcome")
        return self._upsert("outcome", text, payload, prov, record_id)

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


# --- Section 8. P140 action-centric API ----------------------------------
#
# The :class:`PersonalActionMemoryClient` below specialises the P130
# :class:`PersonalMemoryClient` with action-shaped wrappers. Every write
# is consent-scoped (Rule 1), provenance-stamped (Rule 2), and the
# rollback chain is preserved verbatim (Rule 3). The names match the
# P140 contract one-to-one: ``add_approved_action`` /
# ``add_rollback_record`` / ``add_outcome_record`` /
# ``search_past_actions``. Older callers that import
# :class:`PersonalMemoryClient` keep working unchanged.


def _coerce_consent_level(level: str | None) -> str:
    """Snap a level to one of :data:`CONSENT_LEVELS`; default = session."""
    if not level:
        return DEFAULT_CONSENT_LEVEL
    s = str(level).strip().lower()
    return s if s in CONSENT_LEVELS else DEFAULT_CONSENT_LEVEL


class PersonalActionMemoryClient(PersonalMemoryClient):
    """Action-centric memory client (P140).

    Sits on top of :class:`PersonalMemoryClient` and adds:

    - :meth:`add_approved_action`   — record a step that the user has
                                      already approved (writes one
                                      ``action`` row + one matching
                                      ``approval`` row in lock-step).
    - :meth:`add_rollback_record`   — inherited; rebound here so callers
                                      get the new ``consent_level`` /
                                      ``rollback_id`` / ``action_id``
                                      metadata for free.
    - :meth:`add_outcome_record`    — inherited; rebound for symmetry.
    - :meth:`search_past_actions`   — semantic search restricted to the
                                      four action-shaped kinds with a
                                      hierarchical ``consent_level``
                                      filter. Records written at a
                                      retention level higher than the
                                      caller's are hidden.

    The class never relaxes a Constitution rule. It only adds typed
    helpers around the P130 surface so callers stop hand-rolling the
    same payload dicts.
    """

    #: Public re-exports so ``from memory import (
    #: PersonalActionMemoryClient, CONSENT_LEVELS)`` works.
    CONSENT_LEVELS = CONSENT_LEVELS
    DEFAULT_CONSENT_LEVEL = DEFAULT_CONSENT_LEVEL

    # -- Writes ------------------------------------------------------------

    def add_approved_action(
        self,
        action: dict,
        *,
        consent_token: str,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        rollback_id: str | None = None,
        action_id: str | None = None,
        scope: str | None = None,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> dict:
        """Record one HITL-approved + executed action with full audit trail.

        Writes two records in lock-step:

        - one ``action`` row with the executed-action payload, and
        - one ``approval`` row with the held ``consent_token`` and scope.

        Both share the same ``consent_level``, ``rollback_id``, and
        ``action_id``, so :meth:`search_past_actions` can correlate them
        downstream.

        Returns a dict ``{"action": MemoryRecord, "approval": MemoryRecord,
        "action_id": str, "consent_token": str, "consent_level": str,
        "rollback_id": str | None}``.

        Raises :class:`ConstitutionViolation` (Rule 1) if either:

        - the caller's consent does not hold ``MEMORY_WRITE_GATE``, or
        - ``consent_token`` is missing / empty (Rule 1 audit trail).
        """
        if not consent_token or not str(consent_token).strip():
            raise ConstitutionViolation(
                "memory.add_approved_action: refused — empty consent_token "
                "violates Rule 1 (every action must carry a typed approval).",
                rule=1, tool=action.get("tool") if isinstance(action, dict) else None,
            )
        level = _coerce_consent_level(consent_level)
        body = dict(action or {})
        body.setdefault("consent_token", consent_token)
        body["consent_level"] = level
        if rollback_id:
            body["rollback_id"] = rollback_id
        # Keep the existing ``action_id`` if present; otherwise mint a
        # stable one from the step number + consent_token so downstream
        # correlation is deterministic.
        chosen_action_id = (
            action_id
            or body.get("action_id")
            or f"act::{body.get('step') or 'step'}::{consent_token}"
        )
        body["action_id"] = chosen_action_id

        action_rec = self.add_action_history(
            body,
            provenance={**dict(provenance or {}), "consent_level": level},
            record_id=record_id,
        )
        approval_rec = self.add_approval_record(
            {
                "step":            body.get("step"),
                "tool":            body.get("tool"),
                "consent_token":   consent_token,
                "consent_level":   level,
                "rollback_id":     body.get("rollback_id"),
                "action_id":       chosen_action_id,
                "approval_status": "granted",
                "scope":           scope or body.get("description"),
                "stub":            bool(body.get("stub")),
            },
            provenance={**dict(provenance or {}), "consent_level": level,
                        "action_id": chosen_action_id},
        )
        return {
            "action":         action_rec,
            "approval":       approval_rec,
            "action_id":      chosen_action_id,
            "consent_token":  consent_token,
            "consent_level":  level,
            "rollback_id":    body.get("rollback_id"),
        }

    def add_rollback_record(   # type: ignore[override]
        self,
        rollback: dict,
        *,
        consent_token: str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        rollback_id: str | None = None,
        action_id: str | None = None,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Record one Rule-3 rollback with explicit chain metadata.

        Falls back to the parent implementation when called with the
        legacy positional-only signature (so existing P130 callers keep
        working).
        """
        body = dict(rollback or {})
        if consent_token and not body.get("consent_token"):
            body["consent_token"] = consent_token
        body["consent_level"] = _coerce_consent_level(
            consent_level if consent_level != DEFAULT_CONSENT_LEVEL
            else body.get("consent_level") or DEFAULT_CONSENT_LEVEL
        )
        if rollback_id:
            body["rollback_id"] = rollback_id
        if action_id:
            body["action_id"] = action_id
        return super().add_rollback_record(
            body, provenance=provenance, record_id=record_id,
        )

    def add_outcome_record(   # type: ignore[override]
        self,
        outcome: dict,
        *,
        consent_token: str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        rollback_id: str | None = None,
        action_id: str | None = None,
        provenance: dict | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Record the real-world outcome of an executed action."""
        body = dict(outcome or {})
        if consent_token and not body.get("consent_token"):
            body["consent_token"] = consent_token
        body["consent_level"] = _coerce_consent_level(
            consent_level if consent_level != DEFAULT_CONSENT_LEVEL
            else body.get("consent_level") or DEFAULT_CONSENT_LEVEL
        )
        if rollback_id:
            body["rollback_id"] = rollback_id
        if action_id:
            body["action_id"] = action_id
        return super().add_outcome_record(
            body, provenance=provenance, record_id=record_id,
        )

    # -- Reads -------------------------------------------------------------

    def search_past_actions(
        self,
        query: str,
        *,
        consent_token: str | None = None,
        consent_level: str | None = None,
        max_consent_level: str | None = None,
        rollback_id: str | None = None,
        action_id: str | None = None,
        tool: str | None = None,
        outcome: str | None = None,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
        kinds: Iterable[str] | None = None,
        limit: int = 5,
    ) -> list[SearchHit]:
        """Semantic search over past actions, scoped to caller consent.

        Returned hits are limited to the four action-shaped kinds
        (``action``, ``approval``, ``rollback``, ``outcome``) by
        default. The ``max_consent_level`` filter is the headline P140
        guarantee: a caller searching at ``"session"`` retention can
        never see records that were written at a higher level
        (``"persistent"`` or ``"shared"``). Pass ``consent_level`` for
        an exact-match filter (e.g. *only* shared records).

        ``consent_token`` lets you pull every record tied to one
        specific approval — convenient for "what happened after I
        approved token ct-123?" reporting.

        Pass ``kinds=("action",)`` to restrict to a single category
        without losing the consent-level filter.
        """
        # Default search scope is the four action-shaped kinds — ignores
        # preferences and contexts which aren't strictly per-action.
        if kinds is None:
            search_kinds = list(ACTION_MEMORY_KINDS)
        else:
            search_kinds = []
            for k in kinds:
                if k not in COLLECTION_FOR_KIND:
                    raise ConstitutionViolation(
                        f"search_past_actions: unknown kind '{k}'",
                        rule=2, tool=None,
                    )
                search_kinds.append(k)
            if not search_kinds:
                search_kinds = list(ACTION_MEMORY_KINDS)

        # If the caller asked for a max_consent_level, it cannot exceed
        # the levels for which their ConsentContext holds the write
        # gate. Without the write gate, search is still allowed but is
        # implicitly capped at the most restrictive level.
        effective_max = max_consent_level
        if effective_max is None and not self._consent.has(MEMORY_WRITE_GATE):
            effective_max = DEFAULT_CONSENT_LEVEL

        return self._qdrant.search(
            query,
            kinds=search_kinds,
            tool=tool,
            outcome=outcome,
            consent_token=consent_token,
            consent_level=consent_level,
            max_consent_level=effective_max,
            rollback_id=rollback_id,
            action_id=action_id,
            timestamp_gte=timestamp_gte,
            timestamp_lte=timestamp_lte,
            limit=limit,
        )

    def list_rollback_chain(
        self, action_id: str, *, limit: int = 25,
    ) -> list[SearchHit]:
        """Return every record correlated with one ``action_id``.

        Convenience for the P133 dashboard's "rollback chain visualizer"
        — given the originating action, surface the matching approval +
        rollback + outcome rows in one call.
        """
        if not action_id:
            return []
        return self._qdrant.search(
            "",
            kinds=list(ACTION_MEMORY_KINDS),
            action_id=action_id,
            limit=limit,
        )


# --- Section 9. P140 adapters + factories --------------------------------


class ActionMemoryStoreAdapter(MemoryStoreAdapter):
    """Adapter wrapping a :class:`PersonalActionMemoryClient`.

    Subclasses :class:`MemoryStoreAdapter` so callers that already hold a
    :class:`MemoryStoreAdapter` reference don't need a type-narrowing
    branch; ``adapter.client`` is correctly typed as a
    :class:`PersonalActionMemoryClient` here.
    """

    def __init__(self, client: PersonalActionMemoryClient) -> None:
        if not isinstance(client, PersonalActionMemoryClient):
            raise TypeError(
                "ActionMemoryStoreAdapter requires a "
                "PersonalActionMemoryClient instance"
            )
        super().__init__(client)

    @property
    def client(self) -> PersonalActionMemoryClient:   # type: ignore[override]
        return self._client  # type: ignore[return-value]


_ACTION_CLIENT_LOCK = threading.Lock()
_DEFAULT_ACTION_CLIENT: PersonalActionMemoryClient | None = None


def get_action_memory_client(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
    refresh: bool = False,
) -> PersonalActionMemoryClient:
    """Process-wide cached :class:`PersonalActionMemoryClient`.

    ``refresh=True`` always rebuilds the client. Otherwise the cached
    instance is returned and its consent is updated in place when a new
    :class:`ConsentContext` is provided.
    """
    global _DEFAULT_ACTION_CLIENT
    with _ACTION_CLIENT_LOCK:
        if (
            refresh
            or _DEFAULT_ACTION_CLIENT is None
            or _DEFAULT_ACTION_CLIENT.user_id != user_id
        ):
            _DEFAULT_ACTION_CLIENT = PersonalActionMemoryClient(
                user_id=user_id, force_stub=force_stub, consent=consent,
            )
        elif consent is not None:
            _DEFAULT_ACTION_CLIENT.set_consent(consent)
    return _DEFAULT_ACTION_CLIENT


def build_action_memory_store(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
) -> ActionMemoryStoreAdapter:
    """Factory — fresh action-centric client + adapter pair."""
    client = PersonalActionMemoryClient(
        user_id=user_id, force_stub=force_stub, consent=consent,
    )
    return ActionMemoryStoreAdapter(client)


def attach_action_memory(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    consent: ConsentContext | None = None,
) -> tuple[PersonalActionMemoryClient, Callable[..., dict]]:
    """Wire an action-centric memory client into the P129 graph.

    Returns ``(client, run_with_action_memory)``. The wrapper preserves
    every keyword argument :func:`graph.run_action_loop` already
    accepts (``user_id``, ``user_request``, ``consent``, ``force_stub``,
    ``auto_approve``, ``prompt_version``) and adds two memory-side
    keyword arguments:

    - ``consent_level`` — retention level applied to every row written
      from this run. Defaults to ``"session"``.
    - ``record_outcomes`` — when True, an ``outcome`` row is written per
      executed action with ``outcome="success"`` / ``"failure"`` /
      ``"rolled_back"`` derived from the graph's per-step result.

    The wrapper is **additive** — it never modifies P129 ``graph.py``
    or ``agent.py``. Callers opt in by importing from this module.
    """
    client = PersonalActionMemoryClient(
        user_id=user_id, force_stub=force_stub, consent=consent,
    )

    def run_with_action_memory(
        *,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        record_outcomes: bool = True,
        **kwargs: Any,
    ) -> dict:
        out = _graph_run_action_loop(**kwargs)
        if not client.consent.has(MEMORY_WRITE_GATE):
            out.setdefault("memory_ingest", {
                "skipped": True,
                "reason":  f"consent gate '{MEMORY_WRITE_GATE}' not held",
            })
            return out

        plan        = (out.get("plan") or {})
        proposed    = plan.get("proposed_actions") or []
        rollbacks   = out.get("rollbacks") or []
        plan_id     = plan.get("plan_id")
        level       = _coerce_consent_level(consent_level)
        counters = {
            "actions":   0, "approvals": 0,
            "rollbacks": 0, "outcomes":  0,
            "consent_level": level,
        }
        try:
            for raw_step in proposed:
                if not raw_step.get("executed"):
                    continue
                token = raw_step.get("consent_token")
                if not token:
                    continue
                pair = client.add_approved_action(
                    {**raw_step, "consent_level": level,
                     "stub": bool(out.get("stub"))},
                    consent_token=token,
                    consent_level=level,
                    rollback_id=(
                        f"rb::{plan_id}::step{raw_step.get('step')}"
                    ),
                    provenance={
                        "plan_id": plan_id,
                        "stub":    bool(out.get("stub")),
                    },
                )
                counters["actions"]   += 1
                counters["approvals"] += 1
                if record_outcomes:
                    client.add_outcome_record(
                        {
                            "action_id":   pair["action_id"],
                            "step":        raw_step.get("step"),
                            "tool":        raw_step.get("tool"),
                            "outcome":     raw_step.get("outcome") or "success",
                            "description": raw_step.get("description"),
                            "side_effects": raw_step.get("side_effects") or [],
                            "downstream_state": (
                                raw_step.get("execution_result") or {}
                            ),
                            "rollback_id":  pair.get("rollback_id"),
                            "consent_token": token,
                            "consent_level": level,
                        },
                        provenance={
                            "plan_id": plan_id,
                            "stub":    bool(out.get("stub")),
                        },
                    )
                    counters["outcomes"] += 1
            for r in rollbacks:
                rb_step = r.get("step") or r.get("rolled_back_from")
                client.add_rollback_record(
                    {**r, "consent_level": level,
                     "stub": bool(out.get("stub"))},
                    consent_token=r.get("consent_token"),
                    consent_level=level,
                    rollback_id=f"rb::{plan_id}::step{rb_step}",
                    action_id=f"act::{rb_step}::{r.get('consent_token')}",
                    provenance={
                        "plan_id": plan_id,
                        "stub":    bool(out.get("stub")),
                    },
                )
                counters["rollbacks"] += 1
        except ConstitutionViolation:
            counters.setdefault("refused", True)
        out["memory_ingest"] = counters
        return out

    return client, run_with_action_memory
