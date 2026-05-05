# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Self-Evolving Personal OS — Memory Layer (P120, Recipe C Slot 3).

Built to help xAI and Grok win the agent platform battle on X.

This package is the durable, semantic-search-capable replacement for
P119's default ``InMemoryPersonalMemoryStore``. It composes:

* :class:`memory.mem0_setup.Mem0PersonalStore` — canonical structured
  store across 7 SQLite tables (briefings, insights, patterns,
  pattern_flags, workflow_suggestions, routine_patterns, audit_trail)
  with optional Mem0 mirror, DPAPI encryption-at-rest, and PII
  redaction at store time.
* :class:`memory.qdrant_index.QdrantPersonalIndex` — vector-similarity
  layer across 4 Qdrant collections (briefings, insights, patterns,
  workflow_suggestions).

Slot boundary contract
======================

* The composite ``Mem0QdrantPersonalStore`` satisfies the
  ``PersonalMemoryStore`` Protocol from P119's ``orchestrator.py``
  exactly (4 methods: ``remember``, ``recall``, ``latest_briefing_for``,
  ``history_for``). The orchestrator wires it via
  ``PersonalOS.with_dependencies(memory=...)``.
* On the SAME composite, this package exposes 6 RICH methods for
  slots 5/6/7 to call directly: ``store_personal_insight``,
  ``recall_personal``, ``store_workflow_suggestion``,
  ``get_routine_patterns``, ``rewind_briefing``, ``flag_pattern``.
* ZERO changes to ``orchestrator.py``, ``graph.py``, the
  manifest/constitution, or any LNF code.

Plug-in pattern
===============

::

    from memory import build_memory_store
    from orchestrator import PersonalOS

    store = build_memory_store()
    os_agent = PersonalOS().with_dependencies(memory=store)
    b = os_agent.morning_brief()

    # 6 rich methods are available directly on the composite
    insights = store.recall_personal(query="DM pattern", k=5)
    rewind   = store.rewind_briefing(b.briefing_id)
    flag_id  = store.flag_pattern(pattern_id=p.pattern_id, stance="monitor",
                                  reason="explicit long-watch", flagged_by="user")
    routines = store.get_routine_patterns(min_frequency=0.5)

CLI smoke test (Windows 11 + PowerShell)
========================================

::

    cd templates\\super-agents\\self-evolving-personal-os
    python memory\\__init__.py

Prints ``P120 personal-os memory layer smoke OK`` on success.
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import dataclasses + Protocol from this folder's orchestrator
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
ConstitutionViolation = _orch.ConstitutionViolation
PersonalMemoryStore = _orch.PersonalMemoryStore   # the Protocol
PersonalOS = _orch.PersonalOS
_default_appdata_root = _orch._default_appdata_root


# ---------------------------------------------------------------------------
# Sibling imports — work whether loaded as ``memory`` package or directly
# ---------------------------------------------------------------------------


def _import_siblings():
    try:
        from . import mem0_setup as _mod_mem0  # type: ignore
        from . import qdrant_index as _mod_qdrant  # type: ignore
        return _mod_mem0, _mod_qdrant
    except Exception:
        pass
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    return (
        importlib.import_module("mem0_setup"),
        importlib.import_module("qdrant_index"),
    )


_mod_mem0, _mod_qdrant = _import_siblings()
Mem0PersonalStore = _mod_mem0.Mem0PersonalStore
RoutinePattern = _mod_mem0.RoutinePattern
AuditEntry = _mod_mem0.AuditEntry
QdrantPersonalIndex = _mod_qdrant.QdrantPersonalIndex
SearchHit = _mod_qdrant.SearchHit
serialise_briefing = _mod_mem0.serialise_briefing
serialise_insight = _mod_mem0.serialise_insight
serialise_pattern = _mod_mem0.serialise_pattern
redact_pii = _mod_mem0.redact_pii
has_pii = _mod_mem0.has_pii


# ---------------------------------------------------------------------------
# Public result dataclasses (mirror P111's shapes for cross-Super-Agent
# tooling consistency)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceHits:
    insights:  tuple[Insight, ...]
    briefings: tuple[BriefingVersion, ...]


@dataclass(frozen=True)
class RewindResult:
    briefing:     BriefingVersion
    parent_chain: tuple[BriefingVersion, ...]
    descendants:  tuple[BriefingVersion, ...]


# ---------------------------------------------------------------------------
# Mem0QdrantPersonalStore — composite that satisfies PersonalMemoryStore
# ---------------------------------------------------------------------------


@dataclass
class Mem0QdrantPersonalStore:
    """The composite memory store P119's orchestrator wires via with_dependencies.

    Implements the PersonalMemoryStore Protocol (4 methods) AND
    exposes 6 rich methods for later slots:
      * ``store_personal_insight``
      * ``recall_personal``
      * ``store_workflow_suggestion``
      * ``get_routine_patterns``
      * ``rewind_briefing``
      * ``flag_pattern``
    """

    structured:        Mem0PersonalStore
    vectors:           QdrantPersonalIndex
    appdata_root:      Path
    collection_prefix: str = "self-evolving-personal-os"

    # ---- Protocol-required (4) -----------------------------------------

    def remember(self, briefing: BriefingVersion) -> None:
        """Persist a BriefingVersion + index every Insight + Pattern.

        Order of operations:
          1. ``structured.put_briefing`` — atomic SQLite transaction.
             Raises ConstitutionViolation if any insight has empty
             source_id.
          2. ``vectors.index_briefing`` — 1 vector for the whole brief.
          3. ``vectors.index_insight`` — one vector per insight.
          4. ``vectors.index_pattern`` — one vector per pattern.
        """

        self.structured.put_briefing(briefing)
        self.vectors.index_briefing(briefing)
        for i in briefing.insights:
            self.vectors.index_insight(i, briefing_id=briefing.briefing_id)
        for p in briefing.patterns:
            self.vectors.index_pattern(p, briefing_id=briefing.briefing_id)

    def recall(self, briefing_id: str) -> Optional[BriefingVersion]:
        return self.structured.get_briefing(briefing_id)

    def latest_briefing_for(self, for_date: date) -> Optional[BriefingVersion]:
        return self.structured.latest_briefing_for(for_date)

    def history_for(self, for_date_range: tuple[date, date]) -> Sequence[BriefingVersion]:
        return self.structured.history_for(for_date_range)

    # ---- Rich API (6) --------------------------------------------------

    def store_personal_insight(
        self,
        insight: Insight,
        *,
        briefing_id: Optional[str] = None,
    ) -> str:
        """Store a single Insight with full provenance.

        Constitution Article II: empty source_id → ``ConstitutionViolation``
        from ``serialise_insight`` inside ``structured.store_insight``.
        Returns the persisted ``insight_id``.
        """

        self.structured.store_insight(insight, briefing_id=briefing_id)
        self.vectors.index_insight(insight, briefing_id=briefing_id)
        return insight.insight_id

    def recall_personal(
        self,
        *,
        query: str,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        source_filter: Optional[Iterable[str]] = None,
        since: Optional[datetime] = None,
        k: int = 10,
        consent_token: Optional[str] = None,
    ) -> tuple[Insight, ...]:
        """Constitution Article IX: bulk personal-recall is a sensitive op
        and is consent-gated when crossing a high-volume threshold.

        Behaviour:
          * ``k <= 50`` → returns the structured-table results directly
            (no consent token required for routine queries).
          * ``k > 50``  → requires ``consent_token = "CONSENT::recall_personal::bulk"``;
            otherwise raises ConstitutionViolation.
        """

        if k > 50 and consent_token != "CONSENT::recall_personal::bulk":
            raise ConstitutionViolation(
                f"Constitution Article IX violation: recall_personal with "
                f"k={k} > 50 is a bulk-personal-recall operation; pass "
                f"consent_token='CONSENT::recall_personal::bulk' to authorise."
            )

        # 1. Structured-table query for the indexed fields.
        structured_hits = self.structured.insights_by_query(
            subject=subject, predicate=predicate,
            source_filter=source_filter, since=since, k=k,
        )

        # 2. Vector similarity for free-text queries — merge top-k by
        #    insight_id; structured results win on duplicates because
        #    they're fresher and don't depend on the embedding tier.
        vec_hits: tuple[SearchHit, ...] = ()
        if query:
            vec_hits = self.vectors.search(query, kind="insight", k=k)

        seen: set[str] = {i.insight_id for i in structured_hits}
        merged: list[Insight] = list(structured_hits)
        for hit in vec_hits:
            if hit.ref_id in seen:
                continue
            # We have a vector hit for an insight that didn't surface
            # via the structured query — pull the full row.
            extra = self.structured.insights_by_query(k=k * 2)
            for i in extra:
                if i.insight_id == hit.ref_id and i.insight_id not in seen:
                    merged.append(i)
                    seen.add(i.insight_id)
        return tuple(merged[:k])

    def store_workflow_suggestion(
        self,
        suggestion: WorkflowSuggestion,
    ) -> str:
        """Persist + index a WorkflowSuggestion. Returns the suggestion_id."""

        self.structured.store_workflow_suggestion(suggestion)
        self.vectors.index_workflow_suggestion(suggestion)
        return suggestion.suggestion_id

    def get_routine_patterns(
        self,
        *,
        kind: Optional[str] = None,
        min_frequency: float = 0.0,
    ) -> tuple[RoutinePattern, ...]:
        return self.structured.get_routines(kind=kind, min_frequency=min_frequency)

    def rewind_briefing(self, briefing_id: str) -> Optional[RewindResult]:
        target = self.structured.get_briefing(briefing_id)
        if target is None:
            return None
        parent_chain = self.structured.walk_chain(briefing_id)
        # Descendants — every briefing whose parent_briefing_id transitively
        # points back to this one. We collect descendant briefing_ids via
        # a recursive CTE then hydrate each via the public ``get_briefing``
        # helper so DPAPI decryption + JSON parsing flow through one
        # well-tested path.
        descendant_ids: list[str] = []
        if self.structured._sqlite_conn is not None:
            cur = self.structured._sqlite_conn.execute(
                """
                WITH RECURSIVE descendants(briefing_id, parent_briefing_id, created_at) AS (
                    SELECT briefing_id, parent_briefing_id, created_at
                    FROM briefings WHERE parent_briefing_id = ?
                    UNION ALL
                    SELECT b.briefing_id, b.parent_briefing_id, b.created_at
                    FROM briefings b
                    INNER JOIN descendants d ON b.parent_briefing_id = d.briefing_id
                )
                SELECT briefing_id FROM descendants ORDER BY created_at ASC
                """,
                (briefing_id,),
            )
            descendant_ids = [r["briefing_id"] for r in cur.fetchall()]
        hydrated_desc = tuple(
            v for v in (self.structured.get_briefing(bid) for bid in descendant_ids)
            if v is not None
        )
        return RewindResult(
            briefing=target,
            parent_chain=parent_chain,
            descendants=hydrated_desc,
        )

    def flag_pattern(
        self,
        *,
        pattern_id: str,
        stance: str,
        reason: str,
        flagged_by: str = "user",
    ) -> str:
        return self.structured.append_pattern_flag(
            pattern_id=pattern_id, stance=stance,
            reason=reason, flagged_by=flagged_by,
        )

    # ---- introspection -------------------------------------------------

    @property
    def runtime_info(self) -> dict:
        return {
            "structured":      self.structured.runtime_info,
            "vectors":         self.vectors.runtime_info,
            "appdata_root":    str(self.appdata_root),
            "collection_prefix": self.collection_prefix,
        }


# ---------------------------------------------------------------------------
# Factory + convenience wirers
# ---------------------------------------------------------------------------


def build_memory_store(
    *,
    appdata_root:        Optional[Path] = None,
    collection_prefix:   str = "self-evolving-personal-os",
    qdrant_url:          Optional[str] = None,
    embedding_model:     str = "all-MiniLM-L6-v2",
    sqlite_filename:     str = "personal.sqlite3",
    pii_redact_on_store: bool = True,
) -> Mem0QdrantPersonalStore:
    """Build a fully-wired Mem0QdrantPersonalStore with sensible defaults.

    ``pii_redact_on_store`` defaults to ``True`` for this Super Agent
    (LNF defaults it off because LNF processes public data; this agent
    processes the user's calendar / email / DMs and must redact at
    store time as defense-in-depth alongside the Slot-5 Langfuse hook).
    """

    root = appdata_root if appdata_root is not None else _default_appdata_root()
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    sqlite_path = root / "mem0" / sqlite_filename

    structured = Mem0PersonalStore(
        appdata_root=root, sqlite_path=sqlite_path,
        pii_redact_on_store=pii_redact_on_store,
    )
    vectors = QdrantPersonalIndex(
        appdata_root=root, collection_prefix=collection_prefix,
        qdrant_url=qdrant_url, embedding_model_name=embedding_model,
    )
    return Mem0QdrantPersonalStore(
        structured=structured, vectors=vectors,
        appdata_root=root, collection_prefix=collection_prefix,
    )


def with_memory_layer(
    os_agent: PersonalOS,
    **kwargs: Any,
) -> PersonalOS:
    """Convenience: build a Mem0QdrantPersonalStore and wire it in via
    ``PersonalOS.with_dependencies``.
    """

    return os_agent.with_dependencies(memory=build_memory_store(**kwargs))


# ---------------------------------------------------------------------------
# Smoke test (zero-install, zero-API-keys)
# ---------------------------------------------------------------------------


def run_smoke_test(*, verbose: bool = True) -> None:
    """10-check smoke test for the Personal-OS memory layer.

    Verifies:

      1. Composite satisfies the ``PersonalMemoryStore`` Protocol.
      2. ``runtime_info`` reports DPAPI status + structured/vector backends.
      3. Storing two briefings on the same date links v2.parent → v1.
      4. ``recall``, ``latest_briefing_for``, ``history_for`` work.
      5. Empty source_id raises ``ConstitutionViolation`` at store time.
      6. ``store_personal_insight`` + ``recall_personal`` round-trip works.
      7. ``recall_personal(k=51)`` without consent raises
         ``ConstitutionViolation`` (Article IX bulk gate).
      8. ``store_workflow_suggestion`` persists; ``get_routine_patterns``
         returns a tuple (empty by default).
      9. ``flag_pattern`` writes an immutable pattern flag.
     10. End-to-end with PersonalOS.morning_brief: Briefing persists +
         ``rewind_briefing`` returns a RewindResult with parent_chain.
     11. ``redact_pii`` strips a synthetic email + phone.
    """

    import shutil
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="lnf-personal-memory-smoke-"))
    try:
        store = build_memory_store(appdata_root=tmp_root)
        if verbose:
            print(f"[smoke] runtime_info = {store.runtime_info}")

        # ---- (1) Protocol satisfaction ------------------------------
        assert isinstance(store, PersonalMemoryStore), (
            "Mem0QdrantPersonalStore does not satisfy PersonalMemoryStore Protocol."
        )

        # ---- (2) runtime_info shape ---------------------------------
        info = store.runtime_info
        assert "structured" in info and "dpapi_status" in info["structured"]
        assert info["structured"]["dpapi_status"] in (
            "available", "unavailable", "passthrough",
        )

        # ---- (3) + (4) two briefings on same date ------------------
        os_agent = PersonalOS().with_dependencies(memory=store)
        today = datetime.now(timezone.utc).date()
        b1 = os_agent.morning_brief(for_date=today)
        b2 = os_agent.morning_brief(for_date=today)
        assert b2.parent_briefing_id == b1.briefing_id

        recalled = store.recall(b1.briefing_id)
        assert recalled is not None and recalled.briefing_id == b1.briefing_id

        latest = store.latest_briefing_for(today)
        assert latest is not None and latest.briefing_id == b2.briefing_id

        history = tuple(store.history_for((today, today)))
        assert len(history) == 2

        # ---- (5) ConstitutionViolation on empty source_id ----------
        bad = Insight(
            insight_id="bad", subject="x", predicate="y", value="z",
            source="local_notes", source_id="",
            confidence=0.5,
            captured_at=datetime.now(timezone.utc),
        )
        try:
            store.store_personal_insight(bad)
            raise AssertionError("store_personal_insight accepted empty source_id")
        except ConstitutionViolation:
            pass

        # ---- (6) round-trip via store_personal_insight + recall_personal
        good = Insight(
            insight_id="good-1", subject="morning", predicate="includes",
            value="DM check at 09:00", source="local_notes",
            source_id="vault-note-001",
            confidence=0.9, captured_at=datetime.now(timezone.utc),
            signal_strength=0.9,
        )
        store.store_personal_insight(good, briefing_id=b1.briefing_id)
        hits = store.recall_personal(query="DM check", k=10)
        assert any(h.insight_id == "good-1" for h in hits), (
            f"recall_personal did not return the stored insight; got "
            f"{[h.insight_id for h in hits]}"
        )

        # ---- (7) bulk-recall consent gate ---------------------------
        try:
            store.recall_personal(query="x", k=51)
            raise AssertionError("recall_personal(k=51) without consent should raise")
        except ConstitutionViolation:
            pass
        big = store.recall_personal(
            query="x", k=51,
            consent_token="CONSENT::recall_personal::bulk",
        )
        assert isinstance(big, tuple)

        # ---- (8) workflow suggestion + routine patterns -------------
        sugg = WorkflowSuggestion(
            suggestion_id="smoke-sugg-1", severity="info",
            target_file="workflows/journal.jsonl",
            title="t", rationale="r", suggested_change="c",
        )
        sid = store.store_workflow_suggestion(sugg)
        assert sid == "smoke-sugg-1"
        listed = store.structured.list_workflow_suggestions(limit=5)
        assert any(s.suggestion_id == "smoke-sugg-1" for s in listed)

        routines = store.get_routine_patterns()
        assert isinstance(routines, tuple)
        # Insert a synthetic routine and read it back.
        rp = RoutinePattern(
            routine_id="rt-1", routine_kind="morning_dms",
            description="user reviews DMs around 09:00",
            frequency=0.85,
            first_observed_at=datetime.now(timezone.utc) - timedelta(days=14),
            last_observed_at=datetime.now(timezone.utc),
            observation_count=10,
        )
        store.structured.upsert_routine(rp)
        again = store.get_routine_patterns(min_frequency=0.5)
        assert any(r.routine_id == "rt-1" for r in again)

        # ---- (9) flag_pattern --------------------------------------
        if b1.patterns:
            flag_id = store.flag_pattern(
                pattern_id=b1.patterns[0].pattern_id,
                stance="monitor", reason="smoke flag",
                flagged_by="smoke-runner",
            )
            assert flag_id
            flags = store.structured.flags_for_pattern(b1.patterns[0].pattern_id)
            assert any(f["flag_id"] == flag_id for f in flags)

        # ---- (10) rewind_briefing -----------------------------------
        rewind = store.rewind_briefing(b2.briefing_id)
        assert rewind is not None
        assert rewind.briefing.briefing_id == b2.briefing_id
        assert rewind.parent_chain and rewind.parent_chain[-1].briefing_id == b1.briefing_id

        # ---- (11) redact_pii ---------------------------------------
        sample = "Contact me at jan@example.com or +84 90 123 4567."
        redacted = redact_pii(sample)
        assert "[email-redacted]" in redacted
        assert "[phone-redacted]" in redacted
        assert has_pii(sample) is True
        assert has_pii("just a clean sentence") is False

        store.structured.close()
        if verbose:
            print("P120 personal-os memory layer smoke OK")
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


__all__ = (
    "AuditEntry",
    "ConstitutionViolation",
    "Mem0QdrantPersonalStore",
    "PersonalMemoryStore",
    "ProvenanceHits",
    "RewindResult",
    "RoutinePattern",
    "SearchHit",
    "build_memory_store",
    "has_pii",
    "redact_pii",
    "run_smoke_test",
    "with_memory_layer",
)


if __name__ == "__main__":  # pragma: no cover
    run_smoke_test()
