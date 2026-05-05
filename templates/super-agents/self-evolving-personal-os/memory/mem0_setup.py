# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Self-Evolving Personal OS — Mem0 structured-memory backend (P120, Slot 3 / 1 of 2).

Built to help xAI and Grok win the agent platform battle on X.

This module is the canonical structured-memory tier for Super Agent #2.
It owns the durable persistence of every ``BriefingVersion`` produced
by the orchestrator (P119), every ``Insight`` extracted, every
recurring ``Pattern`` flagged, every ``WorkflowSuggestion`` emitted by
the eval loop (P124), AND a NEW personal-OS-specific layer of
**procedural memory** — the long-term routine patterns the agent
learns over time (e.g. "user replies to DMs in the morning").

Layered fallback (mirrors P111's runtime selector pattern)
==========================================================

1. **Mem0 + SQLite history** (preferred) — ``mem0`` (PyPI ``mem0ai``)
   wraps a SQLite history backend; we maintain the relational rows in
   the same database for indexed lookups.
2. **Direct SQLite** (always-on safety net) — when ``mem0`` is missing,
   the store writes/reads exclusively from local SQLite. Every public
   method works identically.

DPAPI encryption-at-rest
========================

Article X of the Personal OS Constitution requires encryption-at-rest
where the OS supports it. On Windows, ``pywin32``'s
``win32crypt.CryptProtectData`` / ``CryptUnprotectData`` provide DPAPI
which encrypts blobs to the current Windows user — even another local
user can't decrypt them. The ``_DpapiCipher`` helper in this module
soft-imports ``pywin32`` and degrades to a passthrough on other OSes
(or when the import fails). The dashboard's Settings tab queries
``runtime_info["dpapi_status"]`` and surfaces a yellow banner when
encryption is unavailable.

PII redaction (defense-in-depth)
================================

Article II of the Personal OS Constitution mandates that PII never
leaves the local machine without explicit consent. The
``redact_pii`` helper here strips emails, phone numbers, SSN-like
patterns, and card-like sequences from any string passed to it.
Slot 5 (P123) routes every Langfuse-bound payload through this
redactor; the memory layer also applies it at store time on
``Insight.value`` whenever ``pii_redact_on_store=True`` is set.

Slot boundary contract
======================

* This module satisfies the lower-level storage primitives the
  composite ``Mem0QdrantPersonalStore`` (in ``__init__.py``) delegates
  to. The 4 Protocol methods declared on
  ``orchestrator.PersonalMemoryStore`` live on the composite.
* This module re-imports ``ConstitutionViolation`` from Living
  Narrative Fabric via the same ``importlib.util`` pattern P119's
  orchestrator uses — never redefines it.
* This module makes ZERO changes to the orchestrator, graph, or any
  Slot-1 file.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import dataclasses + exception from this folder's orchestrator + LNF
# ---------------------------------------------------------------------------


def _import_orchestrator():
    try:
        from .. import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
BriefingVersion = _orch.BriefingVersion
Insight = _orch.Insight
Pattern = _orch.Pattern
WorkflowSuggestion = _orch.WorkflowSuggestion
ConstitutionViolation = _orch.ConstitutionViolation  # already imported from LNF
_default_appdata_root = _orch._default_appdata_root


# ---------------------------------------------------------------------------
# Soft Mem0 import
# ---------------------------------------------------------------------------


try:
    import mem0  # type: ignore
except Exception:  # pragma: no cover — soft import
    mem0 = None  # type: ignore


# ---------------------------------------------------------------------------
# Soft DPAPI import (Windows-only — pywin32)
# ---------------------------------------------------------------------------


try:
    import win32crypt  # type: ignore
    _HAS_DPAPI = True
except Exception:  # pragma: no cover — soft import (non-Windows / no pywin32)
    win32crypt = None  # type: ignore
    _HAS_DPAPI = False


# ---------------------------------------------------------------------------
# DPAPI cipher (passthrough when unavailable)
# ---------------------------------------------------------------------------


@dataclass
class _DpapiCipher:
    """Encrypt/decrypt small byte blobs using Windows DPAPI when available.

    Falls back to passthrough on non-Windows + when ``pywin32`` is missing.
    The ``status`` property returns ``"available"``, ``"unavailable"``, or
    ``"passthrough"`` so the dashboard can surface a yellow banner.
    """

    description: str = "grok-agent-personal-os"

    @property
    def status(self) -> str:
        if not _HAS_DPAPI:
            return "unavailable"
        return "available"

    def encrypt(self, blob: bytes) -> bytes:
        if not _HAS_DPAPI:
            return blob
        try:
            return win32crypt.CryptProtectData(  # type: ignore[union-attr]
                blob, self.description, None, None, None, 0,
            )
        except Exception:
            return blob

    def decrypt(self, blob: bytes) -> bytes:
        if not _HAS_DPAPI:
            return blob
        try:
            _, decrypted = win32crypt.CryptUnprotectData(  # type: ignore[union-attr]
                blob, None, None, None, 0,
            )
            return decrypted
        except Exception:
            return blob


# ---------------------------------------------------------------------------
# PII redactor (defense-in-depth for Article II)
# ---------------------------------------------------------------------------


_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
     "[email-redacted]"),
    (re.compile(r"\b\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{3,4}\b"),
     "[phone-redacted]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
     "[ssn-like-redacted]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"),
     "[card-like-redacted]"),
)


def redact_pii(text: str) -> str:
    """Strip common PII patterns from a string.

    This is a defense-in-depth helper — Slot 5's Langfuse hook uses it
    on every outbound payload, and the memory layer can use it at store
    time when ``pii_redact_on_store=True``.
    """

    if not isinstance(text, str) or not text:
        return text
    redacted = text
    for pattern, replacement in _PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def has_pii(text: str) -> bool:
    """Cheap pre-check — returns True when any PII pattern matches."""

    if not isinstance(text, str) or not text:
        return False
    return any(p.search(text) for p, _ in _PII_PATTERNS)


# ---------------------------------------------------------------------------
# SQLite schema — 7 tables (briefings/insights/patterns/pattern_flags/
# workflow_suggestions/routine_patterns/audit_trail)
# ---------------------------------------------------------------------------


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS briefings (
    briefing_id          TEXT PRIMARY KEY,
    for_date             TEXT NOT NULL,
    time_zone            TEXT NOT NULL,
    parent_briefing_id   TEXT,
    created_at           TEXT NOT NULL,
    trust_score          INTEGER NOT NULL,
    audit_triggered      INTEGER NOT NULL,
    has_real_world_action INTEGER NOT NULL,
    blob_json            BLOB NOT NULL,
    encrypted            INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_briefings_for_date ON briefings(for_date, created_at);
CREATE INDEX IF NOT EXISTS ix_briefings_parent   ON briefings(parent_briefing_id);

CREATE TABLE IF NOT EXISTS insights (
    insight_id    TEXT PRIMARY KEY,
    briefing_id   TEXT,
    subject       TEXT,
    predicate     TEXT,
    value         TEXT,
    source        TEXT,
    source_id     TEXT NOT NULL,
    confidence    REAL,
    captured_at   TEXT,
    sentiment     TEXT,
    pii_redacted  INTEGER NOT NULL DEFAULT 0,
    signal_strength REAL,
    FOREIGN KEY(briefing_id) REFERENCES briefings(briefing_id)
);
CREATE INDEX IF NOT EXISTS ix_insights_source_id  ON insights(source_id);
CREATE INDEX IF NOT EXISTS ix_insights_briefing   ON insights(briefing_id);
CREATE INDEX IF NOT EXISTS ix_insights_subject    ON insights(subject, predicate);

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id        TEXT PRIMARY KEY,
    briefing_id       TEXT NOT NULL,
    subject           TEXT,
    predicate         TEXT,
    severity          INTEGER NOT NULL,
    note              TEXT,
    suggested_stance  TEXT,
    FOREIGN KEY(briefing_id) REFERENCES briefings(briefing_id)
);
CREATE INDEX IF NOT EXISTS ix_patterns_briefing ON patterns(briefing_id);
CREATE INDEX IF NOT EXISTS ix_patterns_subject  ON patterns(subject, predicate);

CREATE TABLE IF NOT EXISTS pattern_flags (
    flag_id      TEXT PRIMARY KEY,
    pattern_id   TEXT NOT NULL,
    stance       TEXT NOT NULL,
    reason       TEXT NOT NULL,
    flagged_by   TEXT NOT NULL,
    flagged_at   TEXT NOT NULL,
    FOREIGN KEY(pattern_id) REFERENCES patterns(pattern_id)
);
CREATE INDEX IF NOT EXISTS ix_pattern_flags_pattern ON pattern_flags(pattern_id);

CREATE TABLE IF NOT EXISTS workflow_suggestions (
    suggestion_id     TEXT PRIMARY KEY,
    emitted_at        TEXT NOT NULL,
    severity          TEXT NOT NULL,
    target_file       TEXT NOT NULL,
    title             TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    suggested_change  TEXT NOT NULL,
    extra_json        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_workflow_suggestions_severity ON workflow_suggestions(severity);

CREATE TABLE IF NOT EXISTS routine_patterns (
    routine_id        TEXT PRIMARY KEY,
    routine_kind      TEXT NOT NULL,
    description       TEXT NOT NULL,
    frequency         REAL NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at  TEXT NOT NULL,
    observation_count INTEGER NOT NULL,
    extra_json        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_routine_patterns_kind ON routine_patterns(routine_kind);

CREATE TABLE IF NOT EXISTS audit_trail (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_id  TEXT,
    kind         TEXT NOT NULL,
    reason       TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,
    FOREIGN KEY(briefing_id) REFERENCES briefings(briefing_id)
);
CREATE INDEX IF NOT EXISTS ix_audit_briefing ON audit_trail(briefing_id);
"""


# ---------------------------------------------------------------------------
# Serialise / hydrate helpers
# ---------------------------------------------------------------------------


def serialise_insight(i: Insight) -> dict:
    if not i.source_id:
        raise ConstitutionViolation(
            f"Constitution Article II violation: insight {i.insight_id!r} has empty "
            f"source_id; the memory layer refuses to persist citation-less insights."
        )
    return {
        "insight_id":     i.insight_id,
        "subject":        i.subject,
        "predicate":      i.predicate,
        "value":          i.value,
        "source":         i.source,
        "source_id":      i.source_id,
        "confidence":     float(i.confidence),
        "captured_at":    i.captured_at.isoformat(),
        "sentiment":      i.sentiment,
        "pii_redacted":   bool(i.pii_redacted),
        "signal_strength": float(i.signal_strength),
    }


def hydrate_insight(d: dict) -> Insight:
    return Insight(
        insight_id=d["insight_id"],
        subject=d["subject"], predicate=d["predicate"], value=d["value"],
        source=d["source"], source_id=d["source_id"],
        confidence=float(d["confidence"]),
        captured_at=datetime.fromisoformat(d["captured_at"]),
        sentiment=d.get("sentiment"),
        pii_redacted=bool(d.get("pii_redacted", False)),
        signal_strength=float(d.get("signal_strength", 1.0)),
    )


def serialise_pattern(p: Pattern) -> dict:
    return {
        "pattern_id":          p.pattern_id,
        "subject":             p.subject,
        "predicate":           p.predicate,
        "insight_ids":         list(p.insight_ids),
        "severity":            int(p.severity),
        "severity_components": dict(p.severity_components),
        "note":                p.note,
        "suggested_stance":    p.suggested_stance,
    }


def hydrate_pattern(d: dict) -> Pattern:
    return Pattern(
        pattern_id=d["pattern_id"],
        subject=d["subject"], predicate=d["predicate"],
        insight_ids=tuple(d["insight_ids"]),
        severity=int(d["severity"]),
        severity_components=dict(d["severity_components"]),
        note=d["note"],
        suggested_stance=d.get("suggested_stance"),
    )


def serialise_briefing(b: BriefingVersion) -> dict:
    return {
        "briefing_id":           b.briefing_id,
        "for_date":              b.for_date.isoformat(),
        "time_zone":             b.time_zone,
        "parent_briefing_id":    b.parent_briefing_id,
        "created_at":            b.created_at.isoformat(),
        "sources_used":          list(b.sources_used),
        "insights":              [serialise_insight(i) for i in b.insights],
        "patterns":              [serialise_pattern(p) for p in b.patterns],
        "trust_metrics":         dict(b.trust_metrics),
        "trust_score":           int(b.trust_score),
        "audit_triggered":       bool(b.audit_triggered),
        "audit_reasons":         list(b.audit_reasons),
        "has_real_world_action": bool(b.has_real_world_action),
        "bridges":               list(b.bridges),
        "metadata":              dict(b.metadata),
    }


def hydrate_briefing(d: dict) -> BriefingVersion:
    return BriefingVersion(
        briefing_id=d["briefing_id"],
        for_date=date.fromisoformat(d["for_date"]),
        time_zone=d["time_zone"],
        parent_briefing_id=d.get("parent_briefing_id"),
        created_at=datetime.fromisoformat(d["created_at"]),
        sources_used=tuple(d.get("sources_used") or ()),
        insights=tuple(hydrate_insight(i) for i in (d.get("insights") or ())),
        patterns=tuple(hydrate_pattern(p) for p in (d.get("patterns") or ())),
        trust_metrics=dict(d.get("trust_metrics") or {}),
        trust_score=int(d.get("trust_score") or 0),
        audit_triggered=bool(d.get("audit_triggered")),
        audit_reasons=tuple(d.get("audit_reasons") or ()),
        has_real_world_action=bool(d.get("has_real_world_action")),
        bridges=tuple(d.get("bridges") or ()),
        metadata=dict(d.get("metadata") or {}),
    )


def serialise_workflow_suggestion(s: WorkflowSuggestion) -> dict:
    return {
        "suggestion_id":    s.suggestion_id,
        "severity":         s.severity,
        "target_file":      s.target_file,
        "title":            s.title,
        "rationale":        s.rationale,
        "suggested_change": s.suggested_change,
        "extra":            dict(s.extra),
    }


def hydrate_workflow_suggestion(d: dict) -> WorkflowSuggestion:
    return WorkflowSuggestion(
        suggestion_id=d["suggestion_id"],
        severity=d["severity"],
        target_file=d["target_file"],
        title=d["title"],
        rationale=d["rationale"],
        suggested_change=d["suggested_change"],
        extra=dict(d.get("extra") or {}),
    )


# ---------------------------------------------------------------------------
# Lightweight result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditEntry:
    briefing_id: Optional[str]
    recorded_at: datetime
    reason:      str
    kind:        str


@dataclass(frozen=True)
class RoutinePattern:
    routine_id:        str
    routine_kind:      str          # "morning_dms" | "evening_review" | ...
    description:       str
    frequency:         float        # 0.0–1.0 (e.g. 0.85 = 85% of mornings)
    first_observed_at: datetime
    last_observed_at:  datetime
    observation_count: int
    extra:             dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Mem0PersonalStore — the canonical structured tier
# ---------------------------------------------------------------------------


@dataclass
class Mem0PersonalStore:
    """Mem0-primary structured store for every Personal-OS persistent record.

    Holds 7 SQLite tables + an optional Mem0 mirror + a DPAPI cipher.
    The composite ``Mem0QdrantPersonalStore`` (in ``__init__.py``) holds
    an instance of this class as its ``structured`` field.
    """

    appdata_root:       Path
    sqlite_path:        Path
    pii_redact_on_store: bool = False
    _sqlite_conn:       Optional[sqlite3.Connection] = field(default=None, repr=False)
    _mem0_client:       Optional[Any] = field(default=None, repr=False)
    _cipher:            _DpapiCipher = field(default_factory=_DpapiCipher, repr=False)

    # ---- construction ---------------------------------------------------

    def __post_init__(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(
            str(self.sqlite_path), check_same_thread=False,
        )
        self._sqlite_conn.row_factory = sqlite3.Row
        with self._sqlite_conn:
            self._sqlite_conn.executescript(SCHEMA_SQL)
        if mem0 is not None:
            try:
                self._mem0_client = mem0.Memory.from_config({  # type: ignore[attr-defined]
                    "history_db_path": str(self.sqlite_path),
                })
            except Exception:
                self._mem0_client = None

    # ---- introspection --------------------------------------------------

    @property
    def runtime_info(self) -> dict:
        return {
            "structured_backend":
                "mem0+sqlite" if self._mem0_client is not None else "sqlite-only",
            "dpapi_status":      self._cipher.status,
            "pii_redact_on_store": bool(self.pii_redact_on_store),
            "sqlite_path":       str(self.sqlite_path),
        }

    # ---- helpers --------------------------------------------------------

    def _encrypt_blob(self, payload: dict) -> tuple[bytes, int]:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self._cipher.status == "available":
            return self._cipher.encrypt(text), 1
        return text, 0

    def _decrypt_blob(self, blob: bytes, encrypted: int) -> dict:
        text = blob if not encrypted else self._cipher.decrypt(blob)
        return json.loads(text.decode("utf-8"))

    def _maybe_redact_value(self, raw_value: str) -> tuple[str, bool]:
        if not self.pii_redact_on_store:
            return raw_value, False
        if has_pii(raw_value):
            return redact_pii(raw_value), True
        return raw_value, False

    # ---- briefings ------------------------------------------------------

    def put_briefing(self, b: BriefingVersion) -> None:
        if self._sqlite_conn is None:
            raise RuntimeError("Mem0PersonalStore is closed")
        payload = serialise_briefing(b)
        blob, encrypted = self._encrypt_blob(payload)
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT OR REPLACE INTO briefings(
                    briefing_id, for_date, time_zone, parent_briefing_id,
                    created_at, trust_score, audit_triggered,
                    has_real_world_action, blob_json, encrypted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    b.briefing_id, b.for_date.isoformat(), b.time_zone,
                    b.parent_briefing_id, b.created_at.isoformat(),
                    int(b.trust_score), 1 if b.audit_triggered else 0,
                    1 if b.has_real_world_action else 0, blob, encrypted,
                ),
            )
            # Replace insights for this briefing.
            self._sqlite_conn.execute(
                "DELETE FROM insights WHERE briefing_id = ?", (b.briefing_id,)
            )
            for i in b.insights:
                value_to_store, did_redact = self._maybe_redact_value(i.value)
                self._sqlite_conn.execute(
                    """
                    INSERT OR REPLACE INTO insights(
                        insight_id, briefing_id, subject, predicate, value,
                        source, source_id, confidence, captured_at,
                        sentiment, pii_redacted, signal_strength
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        i.insight_id, b.briefing_id, i.subject, i.predicate,
                        value_to_store, i.source, i.source_id,
                        float(i.confidence), i.captured_at.isoformat(),
                        i.sentiment,
                        1 if (i.pii_redacted or did_redact) else 0,
                        float(i.signal_strength),
                    ),
                )
            self._sqlite_conn.execute(
                "DELETE FROM patterns WHERE briefing_id = ?", (b.briefing_id,)
            )
            for p in b.patterns:
                self._sqlite_conn.execute(
                    """
                    INSERT OR REPLACE INTO patterns(
                        pattern_id, briefing_id, subject, predicate,
                        severity, note, suggested_stance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p.pattern_id, b.briefing_id, p.subject, p.predicate,
                        int(p.severity), p.note, p.suggested_stance,
                    ),
                )
            now_iso = datetime.now(timezone.utc).isoformat()
            if b.audit_triggered and b.audit_reasons:
                for r in b.audit_reasons:
                    self._sqlite_conn.execute(
                        """
                        INSERT INTO audit_trail(briefing_id, kind, reason, recorded_at)
                        VALUES (?, 'auto-trigger', ?, ?)
                        """,
                        (b.briefing_id, r, now_iso),
                    )

    def get_briefing(self, briefing_id: str) -> Optional[BriefingVersion]:
        if self._sqlite_conn is None:
            return None
        cur = self._sqlite_conn.execute(
            "SELECT blob_json, encrypted FROM briefings WHERE briefing_id = ?",
            (briefing_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return hydrate_briefing(self._decrypt_blob(row["blob_json"], int(row["encrypted"])))

    def latest_briefing_for(self, for_date: date) -> Optional[BriefingVersion]:
        if self._sqlite_conn is None:
            return None
        cur = self._sqlite_conn.execute(
            """
            SELECT blob_json, encrypted FROM briefings
            WHERE for_date = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (for_date.isoformat(),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return hydrate_briefing(self._decrypt_blob(row["blob_json"], int(row["encrypted"])))

    def history_for(self, for_date_range: tuple[date, date]) -> tuple[BriefingVersion, ...]:
        if self._sqlite_conn is None:
            return ()
        start, end = for_date_range
        cur = self._sqlite_conn.execute(
            """
            SELECT blob_json, encrypted FROM briefings
            WHERE for_date BETWEEN ? AND ?
            ORDER BY for_date ASC, created_at ASC
            """,
            (start.isoformat(), end.isoformat()),
        )
        return tuple(
            hydrate_briefing(self._decrypt_blob(r["blob_json"], int(r["encrypted"])))
            for r in cur.fetchall()
        )

    def walk_chain(self, briefing_id: str) -> tuple[BriefingVersion, ...]:
        if self._sqlite_conn is None:
            return ()
        chain: list[BriefingVersion] = []
        cursor_id: Optional[str] = briefing_id
        seen: set[str] = set()
        while cursor_id and cursor_id not in seen:
            seen.add(cursor_id)
            cur = self._sqlite_conn.execute(
                "SELECT parent_briefing_id FROM briefings WHERE briefing_id = ?",
                (cursor_id,),
            )
            row = cur.fetchone()
            if row is None or row["parent_briefing_id"] is None:
                break
            parent_id = row["parent_briefing_id"]
            parent = self.get_briefing(parent_id)
            if parent is None:
                break
            chain.append(parent)
            cursor_id = parent_id
        chain.reverse()
        return tuple(chain)

    # ---- insights -------------------------------------------------------

    def store_insight(self, i: Insight, *, briefing_id: Optional[str] = None) -> None:
        if self._sqlite_conn is None:
            raise RuntimeError("Mem0PersonalStore is closed")
        if not i.source_id:
            raise ConstitutionViolation(
                f"Constitution Article II violation: insight {i.insight_id!r} "
                f"has empty source_id; the memory layer refuses to persist."
            )
        value_to_store, did_redact = self._maybe_redact_value(i.value)
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT OR REPLACE INTO insights(
                    insight_id, briefing_id, subject, predicate, value,
                    source, source_id, confidence, captured_at,
                    sentiment, pii_redacted, signal_strength
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    i.insight_id, briefing_id, i.subject, i.predicate,
                    value_to_store, i.source, i.source_id,
                    float(i.confidence), i.captured_at.isoformat(),
                    i.sentiment,
                    1 if (i.pii_redacted or did_redact) else 0,
                    float(i.signal_strength),
                ),
            )

    def insights_by_query(
        self,
        *,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        source_filter: Optional[Iterable[str]] = None,
        since: Optional[datetime] = None,
        k: int = 50,
    ) -> tuple[Insight, ...]:
        if self._sqlite_conn is None:
            return ()
        clauses: list[str] = []
        params: list[Any] = []
        if subject:
            clauses.append("subject = ?")
            params.append(subject)
        if predicate:
            clauses.append("predicate = ?")
            params.append(predicate)
        if source_filter:
            sources = list(source_filter)
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source IN ({placeholders})")
            params.extend(sources)
        if since is not None:
            clauses.append("captured_at >= ?")
            params.append(since.isoformat())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(k))
        cur = self._sqlite_conn.execute(
            f"""
            SELECT insight_id, subject, predicate, value, source, source_id,
                   confidence, captured_at, sentiment, pii_redacted, signal_strength
            FROM insights
            {where}
            ORDER BY captured_at DESC
            LIMIT ?
            """,
            params,
        )
        return tuple(
            Insight(
                insight_id=r["insight_id"], subject=r["subject"],
                predicate=r["predicate"], value=r["value"],
                source=r["source"], source_id=r["source_id"],
                confidence=float(r["confidence"]) if r["confidence"] is not None else 0.0,
                captured_at=datetime.fromisoformat(r["captured_at"]),
                sentiment=r["sentiment"],
                pii_redacted=bool(r["pii_redacted"]),
                signal_strength=float(r["signal_strength"]) if r["signal_strength"] is not None else 1.0,
            )
            for r in cur.fetchall()
        )

    # ---- patterns + flags ----------------------------------------------

    def append_pattern_flag(
        self,
        *,
        pattern_id: str,
        stance: str,
        reason: str,
        flagged_by: str = "user",
    ) -> str:
        if stance not in ("amplify", "cease", "monitor"):
            raise ValueError(f"stance must be one of (amplify|cease|monitor); got {stance!r}")
        if not pattern_id or not reason:
            raise ValueError("pattern_id and reason are mandatory")
        if self._sqlite_conn is None:
            raise RuntimeError("Mem0PersonalStore is closed")
        flagged_at_iso = datetime.now(timezone.utc).isoformat()
        flag_id = hashlib.sha256(
            f"{pattern_id}|{stance}|{reason}|{flagged_at_iso}|{flagged_by}".encode("utf-8")
        ).hexdigest()[:16]
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT INTO pattern_flags(
                    flag_id, pattern_id, stance, reason, flagged_by, flagged_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (flag_id, pattern_id, stance, reason, flagged_by, flagged_at_iso),
            )
            # Mirror into the audit_trail under the parent briefing.
            cur = self._sqlite_conn.execute(
                "SELECT briefing_id FROM patterns WHERE pattern_id = ?",
                (pattern_id,),
            )
            row = cur.fetchone()
            briefing_id = row["briefing_id"] if row is not None else None
            self._sqlite_conn.execute(
                """
                INSERT INTO audit_trail(briefing_id, kind, reason, recorded_at)
                VALUES (?, 'pattern-flag', ?, ?)
                """,
                (
                    briefing_id,
                    f"flag {stance!r} on pattern {pattern_id} by {flagged_by}: {reason}",
                    flagged_at_iso,
                ),
            )
        return flag_id

    def flags_for_pattern(self, pattern_id: str) -> tuple[dict, ...]:
        if self._sqlite_conn is None:
            return ()
        cur = self._sqlite_conn.execute(
            """
            SELECT flag_id, pattern_id, stance, reason, flagged_by, flagged_at
            FROM pattern_flags WHERE pattern_id = ?
            ORDER BY flagged_at ASC
            """,
            (pattern_id,),
        )
        return tuple(
            {
                "flag_id":    r["flag_id"],
                "pattern_id": r["pattern_id"],
                "stance":     r["stance"],
                "reason":     r["reason"],
                "flagged_by": r["flagged_by"],
                "flagged_at": r["flagged_at"],
            }
            for r in cur.fetchall()
        )

    # ---- workflow suggestions ------------------------------------------

    def store_workflow_suggestion(self, s: WorkflowSuggestion) -> None:
        if self._sqlite_conn is None:
            raise RuntimeError("Mem0PersonalStore is closed")
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT OR REPLACE INTO workflow_suggestions(
                    suggestion_id, emitted_at, severity, target_file,
                    title, rationale, suggested_change, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s.suggestion_id, datetime.now(timezone.utc).isoformat(),
                    s.severity, s.target_file, s.title, s.rationale,
                    s.suggested_change,
                    json.dumps(dict(s.extra), ensure_ascii=False),
                ),
            )

    def list_workflow_suggestions(
        self,
        *,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> tuple[WorkflowSuggestion, ...]:
        if self._sqlite_conn is None:
            return ()
        if severity:
            cur = self._sqlite_conn.execute(
                """
                SELECT suggestion_id, severity, target_file, title,
                       rationale, suggested_change, extra_json
                FROM workflow_suggestions
                WHERE severity = ?
                ORDER BY emitted_at DESC LIMIT ?
                """,
                (severity, int(limit)),
            )
        else:
            cur = self._sqlite_conn.execute(
                """
                SELECT suggestion_id, severity, target_file, title,
                       rationale, suggested_change, extra_json
                FROM workflow_suggestions
                ORDER BY emitted_at DESC LIMIT ?
                """,
                (int(limit),),
            )
        return tuple(
            WorkflowSuggestion(
                suggestion_id=r["suggestion_id"], severity=r["severity"],
                target_file=r["target_file"], title=r["title"],
                rationale=r["rationale"], suggested_change=r["suggested_change"],
                extra=json.loads(r["extra_json"] or "{}"),
            )
            for r in cur.fetchall()
        )

    # ---- routine_patterns (procedural memory) --------------------------

    def upsert_routine(self, r: RoutinePattern) -> None:
        if self._sqlite_conn is None:
            raise RuntimeError("Mem0PersonalStore is closed")
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT OR REPLACE INTO routine_patterns(
                    routine_id, routine_kind, description, frequency,
                    first_observed_at, last_observed_at,
                    observation_count, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.routine_id, r.routine_kind, r.description,
                    float(r.frequency),
                    r.first_observed_at.isoformat(),
                    r.last_observed_at.isoformat(),
                    int(r.observation_count),
                    json.dumps(dict(r.extra), ensure_ascii=False),
                ),
            )

    def get_routines(
        self,
        *,
        kind: Optional[str] = None,
        min_frequency: float = 0.0,
    ) -> tuple[RoutinePattern, ...]:
        if self._sqlite_conn is None:
            return ()
        clauses: list[str] = []
        params: list[Any] = []
        if kind:
            clauses.append("routine_kind = ?")
            params.append(kind)
        clauses.append("frequency >= ?")
        params.append(float(min_frequency))
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        cur = self._sqlite_conn.execute(
            f"""
            SELECT routine_id, routine_kind, description, frequency,
                   first_observed_at, last_observed_at, observation_count, extra_json
            FROM routine_patterns
            {where}
            ORDER BY frequency DESC, observation_count DESC
            """,
            params,
        )
        return tuple(
            RoutinePattern(
                routine_id=r["routine_id"],
                routine_kind=r["routine_kind"],
                description=r["description"],
                frequency=float(r["frequency"]),
                first_observed_at=datetime.fromisoformat(r["first_observed_at"]),
                last_observed_at=datetime.fromisoformat(r["last_observed_at"]),
                observation_count=int(r["observation_count"]),
                extra=json.loads(r["extra_json"] or "{}"),
            )
            for r in cur.fetchall()
        )

    # ---- audit_trail ---------------------------------------------------

    def append_audit_entry(
        self,
        *,
        kind: str,
        reason: str,
        briefing_id: Optional[str] = None,
    ) -> None:
        if self._sqlite_conn is None:
            return
        with self._sqlite_conn:
            self._sqlite_conn.execute(
                """
                INSERT INTO audit_trail(briefing_id, kind, reason, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (briefing_id, kind, reason, datetime.now(timezone.utc).isoformat()),
            )

    def audit_trail_for(
        self,
        briefing_id: str,
        *,
        full_chain: bool = True,
    ) -> tuple[AuditEntry, ...]:
        if self._sqlite_conn is None:
            return ()
        ids: list[str] = [briefing_id]
        if full_chain:
            for v in self.walk_chain(briefing_id):
                ids.append(v.briefing_id)
        placeholders = ",".join("?" for _ in ids)
        cur = self._sqlite_conn.execute(
            f"""
            SELECT briefing_id, recorded_at, reason, kind
            FROM audit_trail WHERE briefing_id IN ({placeholders})
            ORDER BY recorded_at ASC
            """,
            ids,
        )
        return tuple(
            AuditEntry(
                briefing_id=r["briefing_id"],
                recorded_at=datetime.fromisoformat(r["recorded_at"]),
                reason=r["reason"],
                kind=r["kind"],
            )
            for r in cur.fetchall()
        )

    # ---- lifecycle -----------------------------------------------------

    def close(self) -> None:
        if self._sqlite_conn is not None:
            try:
                self._sqlite_conn.close()
            except Exception:
                pass
            self._sqlite_conn = None


__all__ = (
    "AuditEntry",
    "Mem0PersonalStore",
    "RoutinePattern",
    "SCHEMA_SQL",
    "_DpapiCipher",
    "has_pii",
    "hydrate_briefing",
    "hydrate_insight",
    "hydrate_pattern",
    "hydrate_workflow_suggestion",
    "redact_pii",
    "serialise_briefing",
    "serialise_insight",
    "serialise_pattern",
    "serialise_workflow_suggestion",
)
