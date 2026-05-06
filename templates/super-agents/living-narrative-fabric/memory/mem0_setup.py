# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Mem0 structured-memory backend (P111, Slot 3).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module is the standard structured-memory tier for the Living Narrative
Fabric Super Agent. It owns the durable persistence of every
``SynthesisVersion`` the orchestrator produces — full JSON blob plus
indexed relational rows for the rich-API methods in ``memory/__init__.py``
to do constant-time lookups (claims by provenance, contradictions by
version, audit-trail walks).

Layered fallback (mirrors P110's runtime selector pattern)
==========================================================

1. **Mem0 + SQLite history** (preferred) — when ``mem0`` (PyPI ``mem0ai``)
   is importable, ``Mem0NarrativeStore`` constructs a ``mem0.Memory`` with
   a SQLite history backend pointed at the same database file we write to
   directly. Mem0 gets the official SynthesisVersion blob via
   ``_mem0_client.add(...)``; we still maintain the indexed relational
   rows ourselves because Mem0's free-text search is not the right tool
   for "claims by source_id" lookups.

2. **Direct SQLite** (always-on safety net) — when ``mem0`` is not
   installed, ``Mem0NarrativeStore`` writes/reads exclusively from the
   local SQLite database. Every rich-API method works identically.

The Qdrant vector layer lives in ``qdrant_index.py`` and is composed
alongside this module by ``Mem0QdrantStore`` in ``__init__.py``.

Slot boundary contract
======================

* This module does NOT implement the 4 Protocol methods (``remember``,
  ``recall``, ``latest_version_for``, ``history_for``) — those live on
  the composite ``Mem0QdrantStore`` in ``__init__.py``. This module
  exposes the lower-level storage primitives the composite delegates to
  (``put_version``, ``get_version``, ``latest_for_topic``, ...).
* This module does NOT define ``ConstitutionViolation`` — it re-imports
  the exception from ``orchestrator`` and raises it whenever a
  ``Claim`` or ``Contradiction``-referenced claim has empty ``source_id``.
* This module does NOT modify ``orchestrator.py`` or ``graph.py``.
* The serialise/hydrate helpers exposed here mirror exactly the wire
  shape used in ``orchestrator._merge_remote_state`` (orchestrator.py
  lines 1301-1362) and ``graph._serialize_state_to_wire`` (graph.py lines
  102-160) — so a SynthesisVersion stored here can be re-hydrated on
  any host that imports the orchestrator.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Re-import dataclasses + exception from the orchestrator (graph.py-style)
# ---------------------------------------------------------------------------


def _import_orchestrator():
    """Import the sibling ``orchestrator`` module via the relative-then-absolute
    idiom (matches ``graph.py`` lines 182-187 exactly).

    We isolate the import in a function so unit tests can mock it cleanly
    and so a circular import cannot occur at module load time.
    """

    try:
        from . import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    # Absolute fallback — works when this file is run directly via
    # ``python memory/mem0_setup.py`` or imported as ``memory.mem0_setup``
    # from a CWD that includes the parent folder.
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
_default_appdata_root = _orch._default_appdata_root


# ---------------------------------------------------------------------------
# Soft Mem0 import (Mem0 OSS, PyPI: ``mem0ai``; Python import: ``mem0``)
# ---------------------------------------------------------------------------

try:
    import mem0  # type: ignore
except Exception:  # pragma: no cover — soft import
    mem0 = None  # type: ignore


# ---------------------------------------------------------------------------
# SQLite schema — 5 tables, all keyed by version_id; auto-created on connect
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS versions (
    version_id          TEXT PRIMARY KEY,
    topic               TEXT NOT NULL,
    parent_version_id   TEXT,
    created_at          TEXT NOT NULL,
    confidence_score    INTEGER NOT NULL,
    audit_triggered     INTEGER NOT NULL,
    has_finance_subject INTEGER NOT NULL,
    blob_json           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_versions_topic   ON versions(topic, created_at);
CREATE INDEX IF NOT EXISTS ix_versions_parent  ON versions(parent_version_id);

CREATE TABLE IF NOT EXISTS claims (
    claim_id     TEXT PRIMARY KEY,
    version_id   TEXT NOT NULL,
    subject      TEXT,
    predicate    TEXT,
    value        TEXT,
    source       TEXT,
    source_id    TEXT NOT NULL,
    confidence   REAL,
    extracted_at TEXT,
    sentiment    TEXT,
    FOREIGN KEY(version_id) REFERENCES versions(version_id)
);
CREATE INDEX IF NOT EXISTS ix_claims_source_id ON claims(source_id);
CREATE INDEX IF NOT EXISTS ix_claims_version   ON claims(version_id);

CREATE TABLE IF NOT EXISTS contradictions (
    contradiction_id TEXT PRIMARY KEY,
    version_id       TEXT NOT NULL,
    subject          TEXT,
    predicate        TEXT,
    severity         INTEGER NOT NULL,
    note             TEXT,
    FOREIGN KEY(version_id) REFERENCES versions(version_id)
);
CREATE INDEX IF NOT EXISTS ix_contradictions_version ON contradictions(version_id);

CREATE TABLE IF NOT EXISTS contradiction_flags (
    flag_id          TEXT PRIMARY KEY,
    contradiction_id TEXT NOT NULL,
    reason           TEXT NOT NULL,
    flagged_by       TEXT NOT NULL,
    flagged_at       TEXT NOT NULL,
    FOREIGN KEY(contradiction_id) REFERENCES contradictions(contradiction_id)
);
CREATE INDEX IF NOT EXISTS ix_flags_contradiction ON contradiction_flags(contradiction_id);

CREATE TABLE IF NOT EXISTS audit_trail (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    reason       TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,
    FOREIGN KEY(version_id) REFERENCES versions(version_id)
);
CREATE INDEX IF NOT EXISTS ix_audit_version ON audit_trail(version_id);
"""


# ---------------------------------------------------------------------------
# Serialise / hydrate helpers — round-trip SynthesisVersion ↔ JSON-safe dict
# ---------------------------------------------------------------------------


def serialise_claim(c: Claim) -> dict:
    """Convert a Claim dataclass to a JSON-safe dict.

    Constitution rule "Source citations are mandatory": raises
    ``ConstitutionViolation`` when ``source_id`` is empty.
    """

    if not c.source_id:
        raise ConstitutionViolation(
            f"Constitution violation: claim {c.claim_id!r} has empty source_id; "
            f"the memory layer refuses to persist citations-less claims."
        )
    return {
        "claim_id":     c.claim_id,
        "subject":      c.subject,
        "predicate":    c.predicate,
        "value":        c.value,
        "source":       c.source,
        "source_id":    c.source_id,
        "confidence":   float(c.confidence),
        "extracted_at": c.extracted_at.isoformat(),
        "sentiment":    c.sentiment,
    }


def hydrate_claim(d: dict) -> Claim:
    return Claim(
        claim_id=d["claim_id"],
        subject=d["subject"],
        predicate=d["predicate"],
        value=d["value"],
        source=d["source"],
        source_id=d["source_id"],
        confidence=float(d["confidence"]),
        extracted_at=datetime.fromisoformat(d["extracted_at"]),
        sentiment=d.get("sentiment"),
    )


def serialise_contradiction(cd: Contradiction) -> dict:
    return {
        "contradiction_id":    cd.contradiction_id,
        "subject":             cd.subject,
        "predicate":           cd.predicate,
        "claim_ids":           list(cd.claim_ids),
        "severity":            int(cd.severity),
        "severity_components": dict(cd.severity_components),
        "note":                cd.note,
    }


def hydrate_contradiction(d: dict) -> Contradiction:
    return Contradiction(
        contradiction_id=d["contradiction_id"],
        subject=d["subject"],
        predicate=d["predicate"],
        claim_ids=tuple(d["claim_ids"]),
        severity=int(d["severity"]),
        severity_components=dict(d["severity_components"]),
        note=d["note"],
    )


def serialise_synthesis_version(v: SynthesisVersion) -> dict:
    """Convert a SynthesisVersion to a JSON-safe dict.

    Defense-in-depth Constitution check: every claim is run through
    ``serialise_claim`` which raises ``ConstitutionViolation`` on empty
    ``source_id``. The orchestrator already enforces this at finalize
    time (orchestrator.py ``_node_finalize``); we re-enforce here so the
    memory layer can never accept a citationless version.
    """

    return {
        "version_id":          v.version_id,
        "topic":               v.topic,
        "time_range":          v.time_range,
        "parent_version_id":   v.parent_version_id,
        "created_at":          v.created_at.isoformat(),
        "sources_used":        list(v.sources_used),
        "claims":              [serialise_claim(c) for c in v.claims],
        "contradictions":      [serialise_contradiction(cd) for cd in v.contradictions],
        "confidence_metrics":  dict(v.confidence_metrics),
        "confidence_score":    int(v.confidence_score),
        "audit_triggered":     bool(v.audit_triggered),
        "audit_reasons":       list(v.audit_reasons),
        "has_finance_subject": bool(v.has_finance_subject),
        "bridges":             list(v.bridges),
        "metadata":            dict(v.metadata),
    }


def hydrate_synthesis_version(d: dict) -> SynthesisVersion:
    return SynthesisVersion(
        version_id=d["version_id"],
        topic=d["topic"],
        time_range=d["time_range"],
        parent_version_id=d.get("parent_version_id"),
        created_at=datetime.fromisoformat(d["created_at"]),
        sources_used=tuple(d.get("sources_used") or ()),
        claims=tuple(hydrate_claim(c) for c in (d.get("claims") or ())),
        contradictions=tuple(hydrate_contradiction(cd) for cd in (d.get("contradictions") or ())),
        confidence_metrics=dict(d.get("confidence_metrics") or {}),
        confidence_score=int(d.get("confidence_score") or 0),
        audit_triggered=bool(d.get("audit_triggered")),
        audit_reasons=tuple(d.get("audit_reasons") or ()),
        has_finance_subject=bool(d.get("has_finance_subject")),
        bridges=tuple(d.get("bridges") or ()),
        metadata=dict(d.get("metadata") or {}),
    )


# ---------------------------------------------------------------------------
# Lightweight result types used by the rich API (mirrored in __init__.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditEntry:
    """One row from the audit_trail table.

    ``kind`` is one of:
      * ``"auto-trigger"`` — written by ``put_version`` whenever the
        SynthesisVersion has ``audit_triggered=True`` (one row per
        ``audit_reason``).
      * ``"user-flag"`` — written by ``append_flag`` whenever a user
        flags a contradiction (the flag row's ``reason`` is copied into
        the audit trail with ``kind="user-flag"``).
      * ``"constitution-check"`` — reserved for Slot 5 (P113); the
        provenance logger may write these when the safety scanner runs.
    """

    version_id:  str
    topic:       str
    recorded_at: datetime
    reason:      str
    kind:        str


# ---------------------------------------------------------------------------
# Mem0NarrativeStore — the standard structured tier
# ---------------------------------------------------------------------------


@dataclass
class Mem0NarrativeStore:
    """Mem0-primary structured store for SynthesisVersion + sub-records.

    The instance owns:

    * ``_sqlite_conn`` — a SQLite connection at ``sqlite_path`` whose schema
      is auto-created on first construction. Always the source of truth.
    * ``_mem0_client`` — an optional ``mem0.Memory`` instance that mirrors
      the same SynthesisVersion JSON for richer episodic recall in slots
      that want it (e.g. P115's Streamlit dashboard could use Mem0's
      free-text search). When ``mem0`` is not installed, this stays ``None``
      and every method still works via SQLite.

    The composite (``Mem0QdrantStore`` in ``__init__.py``) holds an instance
    of this class as its ``structured`` field.
    """

    appdata_root: Path
    sqlite_path:  Path
    _sqlite_conn: Optional[sqlite3.Connection] = field(default=None, repr=False)
    _mem0_client: Optional[Any] = field(default=None, repr=False)

    # ---- construction / teardown -----------------------------------------

    def __post_init__(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(
            str(self.sqlite_path),
            check_same_thread=False,
        )
        self._sqlite_conn.row_factory = sqlite3.Row
        with self._sqlite_conn:
            self._sqlite_conn.executescript(SCHEMA_SQL)

        if mem0 is not None:
            try:
                # Mem0's config schema varies across versions; we keep the
                # call conservative and silently fall through if the
                # installed Mem0 doesn't accept this shape.
                self._mem0_client = mem0.Memory.from_config({  # type: ignore[attr-defined]
                    "history_db_path": str(self.sqlite_path),
                })
            except Exception:
                self._mem0_client = None

    def close(self) -> None:
        if self._sqlite_conn is not None:
            try:
                self._sqlite_conn.close()
            except Exception:
                pass
            self._sqlite_conn = None

    # ---- write-side primitives -------------------------------------------

    def put_version(self, v: SynthesisVersion) -> None:
        """Persist a SynthesisVersion + all its claims/contradictions atomically.

        Constitution-violation defense-in-depth: ``serialise_synthesis_version``
        raises ``ConstitutionViolation`` if any claim has empty ``source_id``,
        which aborts the transaction before any row is written.
        """

        if self._sqlite_conn is None:
            raise RuntimeError("Mem0NarrativeStore is closed")

        blob = serialise_synthesis_version(v)
        blob_json = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))

        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT OR REPLACE INTO versions(
                    version_id, topic, parent_version_id, created_at,
                    confidence_score, audit_triggered, has_finance_subject,
                    blob_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    v.version_id,
                    v.topic,
                    v.parent_version_id,
                    v.created_at.isoformat(),
                    int(v.confidence_score),
                    1 if v.audit_triggered else 0,
                    1 if v.has_finance_subject else 0,
                    blob_json,
                ),
            )
            self._sqlite_conn.execute(
                "DELETE FROM claims WHERE version_id = ?", (v.version_id,)
            )
            self._sqlite_conn.executemany(
                """
                INSERT INTO claims(
                    claim_id, version_id, subject, predicate, value,
                    source, source_id, confidence, extracted_at, sentiment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        c.claim_id, v.version_id, c.subject, c.predicate, c.value,
                        c.source, c.source_id, float(c.confidence),
                        c.extracted_at.isoformat(), c.sentiment,
                    )
                    for c in v.claims
                ],
            )
            self._sqlite_conn.execute(
                "DELETE FROM contradictions WHERE version_id = ?", (v.version_id,)
            )
            self._sqlite_conn.executemany(
                """
                INSERT INTO contradictions(
                    contradiction_id, version_id, subject, predicate,
                    severity, note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (cd.contradiction_id, v.version_id, cd.subject, cd.predicate,
                     int(cd.severity), cd.note)
                    for cd in v.contradictions
                ],
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            if v.audit_triggered and v.audit_reasons:
                self._sqlite_conn.executemany(
                    """
                    INSERT INTO audit_trail(version_id, kind, reason, recorded_at)
                    VALUES (?, 'auto-trigger', ?, ?)
                    """,
                    [(v.version_id, reason, now_iso) for reason in v.audit_reasons],
                )

        if self._mem0_client is not None:
            try:
                # Mem0's API accepts a text body + metadata; we put a short
                # human-readable summary in the body so Mem0's free-text
                # recall surfaces sensible hits, and the full JSON in the
                # metadata so we can hydrate without a second round trip.
                summary = (
                    f"SynthesisVersion {v.version_id} on topic {v.topic!r} "
                    f"({v.time_range}); confidence={v.confidence_score}, "
                    f"contradictions={len(v.contradictions)}"
                )
                self._mem0_client.add(  # type: ignore[union-attr]
                    summary,
                    user_id=v.topic,
                    metadata={
                        "version_id":         v.version_id,
                        "topic":              v.topic,
                        "parent_version_id":  v.parent_version_id,
                        "blob_json":          blob_json,
                    },
                )
            except Exception:
                # Mem0 is an enhancement layer; a Mem0 failure must never
                # poison the SQLite write that already succeeded.
                pass

    def append_flag(
        self,
        contradiction_id: str,
        reason: str,
        flagged_by: str,
    ) -> str:
        """Append an immutable flag row pointing at an existing contradiction.

        Returns the ``flag_id``. Constitution rule: contradictions
        themselves are never mutated — flags are append-only metadata.
        """

        if self._sqlite_conn is None:
            raise RuntimeError("Mem0NarrativeStore is closed")
        flagged_at_iso = datetime.now(timezone.utc).isoformat()
        flag_id = hashlib.sha256(
            f"{contradiction_id}|{reason}|{flagged_at_iso}|{flagged_by}".encode("utf-8")
        ).hexdigest()[:16]

        # Look up the version_id so we can mirror the flag into audit_trail.
        cur = self._sqlite_conn.execute(
            "SELECT version_id FROM contradictions WHERE contradiction_id = ?",
            (contradiction_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(
                f"flag_contradiction: contradiction_id {contradiction_id!r} "
                f"is not present in this memory store."
            )
        version_id = row["version_id"]

        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT INTO contradiction_flags(
                    flag_id, contradiction_id, reason, flagged_by, flagged_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (flag_id, contradiction_id, reason, flagged_by, flagged_at_iso),
            )
            self._sqlite_conn.execute(
                """
                INSERT INTO audit_trail(version_id, kind, reason, recorded_at)
                VALUES (?, 'user-flag', ?, ?)
                """,
                (
                    version_id,
                    f"flag on contradiction {contradiction_id} by {flagged_by}: {reason}",
                    flagged_at_iso,
                ),
            )
        return flag_id

    def append_audit_entry(self, version_id: str, kind: str, reason: str) -> None:
        if self._sqlite_conn is None:
            raise RuntimeError("Mem0NarrativeStore is closed")
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT INTO audit_trail(version_id, kind, reason, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    version_id,
                    kind,
                    reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    # ---- read-side primitives --------------------------------------------

    def get_version(self, version_id: str) -> Optional[SynthesisVersion]:
        if self._sqlite_conn is None:
            return None
        cur = self._sqlite_conn.execute(
            "SELECT blob_json FROM versions WHERE version_id = ?",
            (version_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return hydrate_synthesis_version(json.loads(row["blob_json"]))

    def latest_for_topic(self, topic: str) -> Optional[SynthesisVersion]:
        if self._sqlite_conn is None:
            return None
        cur = self._sqlite_conn.execute(
            """
            SELECT blob_json FROM versions
            WHERE topic = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (topic,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return hydrate_synthesis_version(json.loads(row["blob_json"]))

    def history_for_topic(self, topic: str) -> tuple[SynthesisVersion, ...]:
        if self._sqlite_conn is None:
            return ()
        cur = self._sqlite_conn.execute(
            """
            SELECT blob_json FROM versions
            WHERE topic = ?
            ORDER BY created_at ASC
            """,
            (topic,),
        )
        return tuple(
            hydrate_synthesis_version(json.loads(row["blob_json"]))
            for row in cur.fetchall()
        )

    def claims_by_source_id(self, source_id: str) -> tuple[Claim, ...]:
        if self._sqlite_conn is None:
            return ()
        cur = self._sqlite_conn.execute(
            """
            SELECT claim_id, subject, predicate, value, source, source_id,
                   confidence, extracted_at, sentiment
            FROM claims WHERE source_id = ?
            """,
            (source_id,),
        )
        return tuple(
            Claim(
                claim_id=row["claim_id"],
                subject=row["subject"],
                predicate=row["predicate"],
                value=row["value"],
                source=row["source"],
                source_id=row["source_id"],
                confidence=float(row["confidence"]) if row["confidence"] is not None else 0.0,
                extracted_at=datetime.fromisoformat(row["extracted_at"]),
                sentiment=row["sentiment"],
            )
            for row in cur.fetchall()
        )

    def versions_by_source_id(self, source_id: str) -> tuple[SynthesisVersion, ...]:
        if self._sqlite_conn is None:
            return ()
        cur = self._sqlite_conn.execute(
            """
            SELECT DISTINCT v.blob_json, v.created_at
            FROM versions v
            INNER JOIN claims c ON c.version_id = v.version_id
            WHERE c.source_id = ?
            ORDER BY v.created_at ASC
            """,
            (source_id,),
        )
        return tuple(
            hydrate_synthesis_version(json.loads(row["blob_json"]))
            for row in cur.fetchall()
        )

    def walk_chain(self, version_id: str) -> tuple[SynthesisVersion, ...]:
        """Walk the parent_version_id chain from this version up to the root.

        Returns versions in oldest-first order: ``(root, ..., grandparent,
        parent)``. The target version itself is NOT included — callers
        that want it can prepend it themselves. This matches the way
        ``RewindResult`` is structured in ``__init__.py``.
        """

        if self._sqlite_conn is None:
            return ()
        chain: list[SynthesisVersion] = []
        cursor_id: Optional[str] = version_id
        seen: set[str] = set()
        while cursor_id is not None and cursor_id not in seen:
            seen.add(cursor_id)
            cur = self._sqlite_conn.execute(
                "SELECT parent_version_id, blob_json FROM versions WHERE version_id = ?",
                (cursor_id,),
            )
            row = cur.fetchone()
            if row is None:
                break
            parent_id = row["parent_version_id"]
            if parent_id is None:
                break
            parent_cur = self._sqlite_conn.execute(
                "SELECT blob_json FROM versions WHERE version_id = ?",
                (parent_id,),
            )
            parent_row = parent_cur.fetchone()
            if parent_row is None:
                break
            chain.append(hydrate_synthesis_version(json.loads(parent_row["blob_json"])))
            cursor_id = parent_id
        # Currently parent-most is at the end; reverse so caller gets
        # (root, ..., parent).
        chain.reverse()
        return tuple(chain)

    def descendants_of(self, version_id: str) -> tuple[SynthesisVersion, ...]:
        """All versions that link back to this one through parent_version_id."""

        if self._sqlite_conn is None:
            return ()
        # Recursive-CTE walk down the tree. SQLite supports WITH RECURSIVE.
        cur = self._sqlite_conn.execute(
            """
            WITH RECURSIVE descendants(version_id, blob_json, created_at) AS (
                SELECT version_id, blob_json, created_at FROM versions
                WHERE parent_version_id = ?
                UNION ALL
                SELECT v.version_id, v.blob_json, v.created_at
                FROM versions v
                INNER JOIN descendants d ON v.parent_version_id = d.version_id
            )
            SELECT blob_json FROM descendants ORDER BY created_at ASC
            """,
            (version_id,),
        )
        return tuple(
            hydrate_synthesis_version(json.loads(row["blob_json"]))
            for row in cur.fetchall()
        )

    def audit_trail_for(
        self,
        version_id: str,
        *,
        full_chain: bool = True,
    ) -> tuple[AuditEntry, ...]:
        """Return audit-trail entries for this version (and ancestors when full_chain)."""

        if self._sqlite_conn is None:
            return ()

        chain_ids: list[str] = [version_id]
        if full_chain:
            for v in self.walk_chain(version_id):
                chain_ids.append(v.version_id)

        placeholders = ",".join("?" for _ in chain_ids)
        cur = self._sqlite_conn.execute(
            f"""
            SELECT a.version_id, v.topic, a.recorded_at, a.reason, a.kind
            FROM audit_trail a
            INNER JOIN versions v ON v.version_id = a.version_id
            WHERE a.version_id IN ({placeholders})
            ORDER BY a.recorded_at ASC
            """,
            chain_ids,
        )
        return tuple(
            AuditEntry(
                version_id=row["version_id"],
                topic=row["topic"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
                reason=row["reason"],
                kind=row["kind"],
            )
            for row in cur.fetchall()
        )

    def flags_for_contradiction(self, contradiction_id: str) -> tuple[dict, ...]:
        if self._sqlite_conn is None:
            return ()
        cur = self._sqlite_conn.execute(
            """
            SELECT flag_id, contradiction_id, reason, flagged_by, flagged_at
            FROM contradiction_flags
            WHERE contradiction_id = ?
            ORDER BY flagged_at ASC
            """,
            (contradiction_id,),
        )
        return tuple(
            {
                "flag_id":          row["flag_id"],
                "contradiction_id": row["contradiction_id"],
                "reason":           row["reason"],
                "flagged_by":       row["flagged_by"],
                "flagged_at":       row["flagged_at"],
            }
            for row in cur.fetchall()
        )


__all__ = (
    "AuditEntry",
    "Mem0NarrativeStore",
    "SCHEMA_SQL",
    "hydrate_claim",
    "hydrate_contradiction",
    "hydrate_synthesis_version",
    "serialise_claim",
    "serialise_contradiction",
    "serialise_synthesis_version",
)
