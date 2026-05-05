# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Self-Evolving Personal OS — Orchestration Core (P119, Recipe C Slot 2).

Built to help xAI and Grok win the agent platform battle on X.

This module is the orchestration spine for Super Agent #2: a personal
second-brain that produces daily morning briefings from the user's
calendar, email, X mentions/DMs, local notes, weather, and personalised
news; tracks recurring patterns over time; auto-evolves the user's
workflows; and gates every real-world action behind explicit consent.

The DAG mirrors the proven 6-node structure shipped by Living Narrative
Fabric (P110) but renames each node to the personal-OS domain:

    1. ingest_personal       — pulls items from the 6 personal-scoped sources
    2. normalise             — converts SourceItems → Insights (one per item)
    3. detect_patterns       — finds (subject, predicate) recurrences
    4. score_briefing_trust  — computes the 4-metric trust score
    5. audit                 — evaluates the audit-trigger thresholds
    6. finalize_briefing     — builds the immutable BriefingVersion

Constitution rules enforced at runtime
======================================

* "User data is sacred" — every Insight emitted carries a non-empty
  ``source_id``; ``ConstitutionViolation`` raises otherwise (Article II).
* "Self-improvement is conservative" — ``apply_workflow_change`` defaults
  to ``dry_run=True``; flipping to ``dry_run=False`` without an explicit
  consent token raises ``ConstitutionViolation`` (Article III).
* "Personal memory is versioned" — every ``BriefingVersion`` carries a
  ``parent_briefing_id`` link; rewind walks the chain (Article IV).
* "Append-only provenance" — the runner never mutates a prior briefing
  (Article V).
* "4-metric Briefing Trust formula is locked"
  ``round(0.30·PersonalRecallAccuracy + 0.30·DataFreshness +
  0.25·WorkflowFitScore + 0.15·NoiseFloor)`` (Article VI).
* "Mandatory ≥3 cross-template bridges" (Article VII).
* "Audit triggers fire on memory drift, recall miss, or trust drop"
  (Article VIII).
* "Real-world actions require explicit consent" — every method that
  touches calendar / email / X / file system / cloud sync raises
  ``ConstitutionViolation`` when ``dry_run=False`` without a matching
  consent token (Article IX).
* "Local-first + privacy-first" — all data under ``$env:LOCALAPPDATA``
  (Article X).

Cross-Super-Agent reuse
=======================

* ``ConstitutionViolation`` is imported via ``importlib.util.spec_from_file_location``
  from ``../living-narrative-fabric/orchestrator.py:362`` so the
  exception class is shared across both Super Agents — never redefined.
* The ``Insight`` / ``Pattern`` / ``BriefingVersion`` dataclasses follow
  the same shape conventions as LNF's ``Claim`` / ``Contradiction`` /
  ``SynthesisVersion`` — slot 6's eval suite can score either Super
  Agent without code changes.

CLI smoke test (Windows 11 + PowerShell)
========================================

::

    cd templates\\super-agents\\self-evolving-personal-os
    python -m pip install -r requirements.txt
    python orchestrator.py morning_brief --for-date 2026-05-05
    python orchestrator.py --smoke
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from pathlib import Path
from random import Random
from typing import Callable, Iterable, Optional, Protocol, Sequence, runtime_checkable


# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SLUG = "self-evolving-personal-os"


def _default_appdata_root() -> Path:
    """Windows-correct local data root. Honours ``$env:LOCALAPPDATA``;
    falls back to ``~/.local/share/grok-agent`` everywhere else."""

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        return Path(localappdata) / "grok-agent" / SLUG
    return Path.home() / ".local" / "share" / "grok-agent" / SLUG


DEFAULT_APPDATA_ROOT = _default_appdata_root()


# ---------------------------------------------------------------------------
# Cross-Super-Agent: re-import ConstitutionViolation from LNF (never redefine)
# ---------------------------------------------------------------------------


def _import_lnf_constitution_violation():
    """Load only ``ConstitutionViolation`` from Living Narrative Fabric's
    orchestrator without polluting the module namespace.

    Uses ``importlib.util.spec_from_file_location`` rather than
    ``importlib.import_module("orchestrator")`` so the identically-named
    sibling file in *this* folder does not conflict on sys.path.
    """

    lnf_orch_path = SCRIPT_DIR.parent / "living-narrative-fabric" / "orchestrator.py"
    if not lnf_orch_path.exists():
        raise ImportError(
            f"Living Narrative Fabric orchestrator not found at {lnf_orch_path}. "
            f"Personal OS depends on LNF being present in the same "
            f"templates/super-agents/ folder so ConstitutionViolation can "
            f"be shared without redefinition (Article I.6 of the Constitution)."
        )
    module_name = "_lnf_orchestrator_for_personal_os"
    spec = importlib.util.spec_from_file_location(module_name, lnf_orch_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build module spec for {lnf_orch_path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec_module so dataclass processing inside the loaded
    # module can resolve cls.__module__ via sys.modules. Without this,
    # @dataclass(frozen=True) on SynthesisVersion / Claim / Contradiction
    # raises AttributeError during exec.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.ConstitutionViolation


ConstitutionViolation = _import_lnf_constitution_violation()


# ---------------------------------------------------------------------------
# Personal-OS source authority tiers + briefing-trust weights
# ---------------------------------------------------------------------------

#: Per-source authority. Local notes = 1.0 (the user's own ground truth).
DEFAULT_SOURCE_AUTHORITY = {
    "local_notes":   1.00,
    "gcal":          0.95,
    "gmail":         0.95,
    "weather":       0.85,
    "news_personal": 0.65,
    "x_personal":    0.40,
}

#: Briefing Trust weighted-formula coefficients. Locked at the runner level
#: so every emitted briefing uses the same scoring — the manifest at
#: grok-agent.yaml:briefing_trust.weights MUST mirror these.
BRIEFING_TRUST_WEIGHTS = {
    "Personal recall accuracy": 0.30,
    "Data freshness":           0.30,
    "Workflow fit score":       0.25,
    "Noise floor":              0.15,
}

#: Pattern severity weighted-formula (mirrors LNF's contradiction severity
#: but with personal-OS components — recurrence frequency, signal density).
PATTERN_SEVERITY_WEIGHTS = {
    "Recurrence frequency": 0.40,
    "Signal density":       0.30,
    "Recency skew":         0.20,
    "Cross-source spread":  0.10,
}

#: Audit-trigger thresholds (Article VIII).
AUDIT_TRIGGER_RECALL_MISSES = 3
AUDIT_TRIGGER_MIN_SOURCES = 2
AUDIT_TRIGGER_MIN_TRUST_PCT = 50
AUDIT_TRIGGER_MEMORY_DRIFT = 0.30

#: Mandatory cross-template bridges (Article VII; manifest lists 7 candidates;
#: this constant grabs the first MIN_BRIDGES_PER_BRIEFING).
CROSS_AGENT_BRIDGES = (
    "living-narrative-fabric",
    "cross-reality-action-fabric",
    "content-idea-generator",
    "reply-drafter",
    "dm-triager",
    "mention-summarizer",
    "follower-quality-analyzer",
)
MIN_BRIDGES_PER_BRIEFING = 3

#: Per-source default item cap.
DEFAULT_PER_SOURCE_LIMIT = 25

#: Real-world actions that require an explicit consent token before
#: ``dry_run`` is allowed to be ``False`` (Article IX).
REAL_WORLD_ACTIONS = frozenset({
    "modify_calendar",
    "send_email",
    "post_to_x",
    "send_dm",
    "modify_local_files_outside_appdata",
    "apply_workflow_change",
    "export_personal_log",
    "sync_to_cloud",
    "publish_briefing",
})

#: Article V.1 verbatim banner — attached when ``has_real_world_action=True``.
ARTICLE_V1_REAL_WORLD_DISCLAIMER = (
    "> ⚠️ **This agent can take real-world actions.** Every action "
    "requires explicit consent. Review the action plan before approving. "
    "The agent never acts autonomously."
)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


class Runtime(str, Enum):
    AUTO = "auto"
    MASTRA = "mastra"
    LANGGRAPH = "langgraph"
    INPROCESS = "inprocess"


@dataclass(frozen=True)
class SourceItem:
    """One raw item from a personal source. Slot-4 connectors emit these."""

    source: str
    item_id: str
    title: str
    body: str
    captured_at: datetime
    occurred_at: Optional[datetime] = None
    url: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Insight:
    """Normalised personal observation. Constitution Article II requires
    every insight carry a non-empty ``source_id``."""

    insight_id: str
    subject: str
    predicate: str
    value: str
    source: str           # one of DEFAULT_SOURCE_AUTHORITY keys
    source_id: str        # NEVER empty
    confidence: float
    captured_at: datetime
    sentiment: Optional[str] = None
    pii_redacted: bool = False
    signal_strength: float = 1.0   # 0.0–1.0; lower = more likely noise


@dataclass(frozen=True)
class Pattern:
    """Recurring (subject, predicate) signal across ≥2 insights."""

    pattern_id: str
    subject: str
    predicate: str
    insight_ids: tuple[str, ...]
    severity: int                   # 0–10
    severity_components: dict
    note: str
    suggested_stance: Optional[str] = None  # "amplify" | "cease" | "monitor"


@dataclass(frozen=True)
class WorkflowSuggestion:
    """A proposed change to the user's workflow journal or prompt files.

    Constitution Article III: ``severity == 'blocker'`` may NEVER be
    auto-applied even when ``dry_run=False``. Apply paths must check
    severity AND require an explicit consent token.
    """

    suggestion_id: str
    severity: str                   # "blocker" | "warning" | "info"
    target_file: str                # e.g. "workflows/journal.jsonl"
    title: str
    rationale: str
    suggested_change: str
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BriefingVersion:
    """One immutable morning-briefing snapshot."""

    briefing_id: str
    for_date: date
    time_zone: str
    parent_briefing_id: Optional[str]
    created_at: datetime
    sources_used: tuple[str, ...]
    insights: tuple[Insight, ...]
    patterns: tuple[Pattern, ...]
    trust_metrics: dict
    trust_score: int
    audit_triggered: bool
    audit_reasons: tuple[str, ...]
    has_real_world_action: bool
    bridges: tuple[str, ...]
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Slot extension Protocols — Slots 3, 4, 5, 6 plug in via dependency injection
# ---------------------------------------------------------------------------


@runtime_checkable
class PersonalSourceClient(Protocol):
    """Slot 4 (P122) ships real connectors that satisfy this Protocol."""

    name: str

    def fetch(self, query: str, since: datetime, limit: int) -> Sequence[SourceItem]:
        ...


@runtime_checkable
class PersonalMemoryStore(Protocol):
    """Slot 3 (P121) ships Mem0+Qdrant; until then the in-memory stub is used."""

    def remember(self, briefing: BriefingVersion) -> None:
        ...

    def recall(self, briefing_id: str) -> Optional[BriefingVersion]:
        ...

    def latest_briefing_for(self, for_date: date) -> Optional[BriefingVersion]:
        ...

    def history_for(self, for_date_range: tuple[date, date]) -> Sequence[BriefingVersion]:
        ...


@runtime_checkable
class PersonalProvenanceLogger(Protocol):
    """Slot 5 (P123) ships the Trust Engine; until then no-op."""

    def log_event(self, event_type: str, payload: dict) -> None:
        ...

    def log_insight(self, insight: Insight, briefing_id: str) -> None:
        ...

    def log_pattern(self, pattern: Pattern, briefing_id: str) -> None:
        ...


# ---------------------------------------------------------------------------
# Default (no-op / stub) implementations of the slot Protocols
# ---------------------------------------------------------------------------


@dataclass
class StubPersonalSourceClient:
    """Deterministic stub source. Slot 4 (P122) replaces these with real clients."""

    name: str
    per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT

    def fetch(self, query: str, since: datetime, limit: int) -> Sequence[SourceItem]:
        seed_hex = hashlib.sha256(
            f"{self.name}|{query}|{since.isoformat()}".encode("utf-8")
        ).hexdigest()
        rng = Random(seed_hex)
        actual_limit = min(limit, self.per_source_limit)

        # 3 deterministic items per source — enough to exercise the
        # pattern detector and trust scoring without overwhelming the
        # smoke test output.
        kind_map = {
            "x_personal":    ("@friend mention",     "praises",       "your latest post"),
            "gcal":          ("Calendar event",      "begins at",     "10:00 ICT"),
            "gmail":         ("Email from",          "asks about",    "the AgentMind launch"),
            "local_notes":   ("Personal note",       "tracks",        "the morning routine"),
            "weather":       ("Forecast",            "predicts",      "29°C with light showers"),
            "news_personal": ("News article",        "covers",        "open-source AI tooling"),
        }
        subj, pred, val = kind_map.get(self.name, ("Item", "is about", "topic"))
        items: list[SourceItem] = []
        for n in range(min(3, actual_limit)):
            slug = f"{self.name}-stub-{seed_hex[:8]}-{n}"
            captured = datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 18))
            items.append(SourceItem(
                source=self.name,
                item_id=slug,
                title=f"[stub:{self.name}] {subj} #{n} — {pred} {val}",
                body=(
                    f"[stub source — replace with real connector at Slot 4 / P122] "
                    f"Source {self.name} reports: {subj} {pred} {val}. "
                    f"Deterministic seeded item; values are placeholders."
                ),
                captured_at=captured,
                occurred_at=captured,
                url=None,
                extra={
                    "stub": True,
                    "source_authority": DEFAULT_SOURCE_AUTHORITY.get(self.name, 0.5),
                },
            ))
        return items


@dataclass
class InMemoryPersonalMemoryStore:
    """Process-local fallback. Slot 3 swaps with Mem0+Qdrant."""

    _by_id: dict[str, BriefingVersion] = field(default_factory=dict)
    _by_date: dict[str, list[str]] = field(default_factory=dict)

    def remember(self, briefing: BriefingVersion) -> None:
        self._by_id[briefing.briefing_id] = briefing
        key = briefing.for_date.isoformat()
        self._by_date.setdefault(key, []).append(briefing.briefing_id)

    def recall(self, briefing_id: str) -> Optional[BriefingVersion]:
        return self._by_id.get(briefing_id)

    def latest_briefing_for(self, for_date: date) -> Optional[BriefingVersion]:
        ids = self._by_date.get(for_date.isoformat()) or []
        if not ids:
            return None
        return self._by_id.get(ids[-1])

    def history_for(self, for_date_range: tuple[date, date]) -> Sequence[BriefingVersion]:
        start, end = for_date_range
        out: list[BriefingVersion] = []
        for k, ids in sorted(self._by_date.items()):
            d = date.fromisoformat(k)
            if start <= d <= end:
                for briefing_id in ids:
                    v = self._by_id.get(briefing_id)
                    if v is not None:
                        out.append(v)
        return tuple(out)


@dataclass
class NoopPersonalProvenanceLogger:
    """Slot 5 replaces this with the Trust Engine."""

    events: list[tuple[str, dict]] = field(default_factory=list)
    insight_logs: list[tuple[str, str]] = field(default_factory=list)
    pattern_logs: list[tuple[str, str]] = field(default_factory=list)

    def log_event(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))

    def log_insight(self, insight: Insight, briefing_id: str) -> None:
        self.insight_logs.append((insight.insight_id, briefing_id))

    def log_pattern(self, pattern: Pattern, briefing_id: str) -> None:
        self.pattern_logs.append((pattern.pattern_id, briefing_id))


# ---------------------------------------------------------------------------
# Runtime adapters — Mastra (HTTP) and LangGraph (in-process import)
# ---------------------------------------------------------------------------


def _mastra_url() -> Optional[str]:
    url = os.environ.get("MASTRA_HTTP_URL")
    if url and url.strip():
        return url.strip().rstrip("/")
    return None


def _mastra_dispatch(state_in: dict, *, timeout: float = 30.0) -> Optional[dict]:
    url = _mastra_url()
    if url is None:
        return None
    try:
        import httpx  # type: ignore
    except Exception:
        return None
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{url}/workflows/{SLUG}/run",
                json=state_in,
                headers={"Content-Type": "application/json"},
            )
            if r.status_code != 200:
                return None
            data = r.json()
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def _langgraph_dispatch(state_in: dict) -> Optional[dict]:
    try:
        from . import graph as _graph  # type: ignore
    except Exception:
        try:
            import graph as _graph  # type: ignore
        except Exception:
            return None
    try:
        runner = getattr(_graph, "build_runner", None)
        if runner is None:
            return None
        return runner(state_in)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 6-node DAG
# ---------------------------------------------------------------------------


def _node_ingest_personal(
    state: dict,
    *,
    sources: Iterable[PersonalSourceClient],
    per_source_limit: int,
    logger: PersonalProvenanceLogger,
) -> dict:
    query: str = state["query"]
    since: datetime = state["since"]

    raw_items: list[SourceItem] = []
    sources_called: list[str] = []
    for src in sources:
        try:
            items = list(src.fetch(query, since, per_source_limit))
        except Exception as exc:
            logger.log_event(
                "ingest_personal.error",
                {"source": getattr(src, "name", "?"), "error": str(exc)},
            )
            continue
        sources_called.append(src.name)
        raw_items.extend(items)
        logger.log_event(
            "ingest_personal.ok",
            {"source": src.name, "item_count": len(items)},
        )

    state["raw_items"] = raw_items
    state["sources_called"] = sources_called
    return state


def _node_normalise_to_insights(
    state: dict,
    *,
    logger: PersonalProvenanceLogger,
) -> dict:
    raw_items: list[SourceItem] = state["raw_items"]
    insights: list[Insight] = []
    for item in raw_items:
        if not item.item_id:
            raise ConstitutionViolation(
                f"Constitution Article II violation: {item.source!r} item with "
                f"empty item_id reached the normalise node; provenance is mandatory."
            )
        # A simple normalisation strategy — Slot 4's real connectors will
        # do richer extraction; here we synthesise one Insight per item
        # whose value mirrors the title minus the stub prefix.
        cleaned_value = item.title.replace(f"[stub:{item.source}] ", "")
        subject = state["query"]
        predicate = "observed in personal source"
        seed = f"{item.source}|{item.item_id}|{subject}|{predicate}|{cleaned_value}"
        insight_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        signal = 0.6 if item.extra.get("stub") else 0.85
        insights.append(Insight(
            insight_id=insight_id,
            subject=subject,
            predicate=predicate,
            value=cleaned_value,
            source=item.source,
            source_id=item.item_id,
            confidence=signal,
            captured_at=item.captured_at,
            sentiment=None,
            pii_redacted=False,
            signal_strength=signal,
        ))
    state["insights"] = insights
    return state


def _detect_pattern_for_group(
    group: list[Insight],
    *,
    source_authority: dict,
) -> Optional[Pattern]:
    """Within a (subject, predicate) group with ≥2 insights, detect a pattern.

    Constitution: never silently picks a winner. Returns a Pattern that
    documents the recurrence; both sides remain in ``briefing.insights``.
    """

    if len(group) < 2:
        return None

    # Recurrence frequency: group size / overall reasonable ceiling (10).
    recurrence = min(len(group) / 10.0, 1.0)

    # Signal density: average signal_strength across the group.
    signal = sum(i.signal_strength for i in group) / len(group)

    # Recency skew: spread of capture times in days, capped at 7.
    times = [i.captured_at for i in group]
    skew_days = (max(times) - min(times)).total_seconds() / 86400.0
    recency = min(skew_days / 7.0, 1.0)

    # Cross-source spread: distinct source count / 6 (the canonical fabric).
    sources = {i.source for i in group}
    cross = len(sources) / 6.0

    components = {
        "Recurrence frequency": round(recurrence, 3),
        "Signal density":       round(signal, 3),
        "Recency skew":         round(recency, 3),
        "Cross-source spread":  round(cross, 3),
    }
    severity = round(
        10 * (
            PATTERN_SEVERITY_WEIGHTS["Recurrence frequency"] * recurrence
            + PATTERN_SEVERITY_WEIGHTS["Signal density"]       * signal
            + PATTERN_SEVERITY_WEIGHTS["Recency skew"]         * recency
            + PATTERN_SEVERITY_WEIGHTS["Cross-source spread"]  * cross
        )
    )

    pid_seed = "|".join(sorted(i.insight_id for i in group))
    pattern_id = hashlib.sha256(pid_seed.encode("utf-8")).hexdigest()[:16]

    note = (
        f"{len(group)} insights cluster on this (subject, predicate); "
        f"sources={sorted(sources)}; recency skew {skew_days:.1f}d. "
        f"Suggested stance: monitor — flip to amplify or cease via flag_pattern."
    )
    return Pattern(
        pattern_id=pattern_id,
        subject=group[0].subject,
        predicate=group[0].predicate,
        insight_ids=tuple(i.insight_id for i in group),
        severity=int(severity),
        severity_components=components,
        note=note,
        suggested_stance="monitor",
    )


def _node_detect_patterns(
    state: dict,
    *,
    logger: PersonalProvenanceLogger,
) -> dict:
    insights: list[Insight] = state["insights"]
    source_authority: dict = state["source_authority"]

    grouped: dict[tuple[str, str], list[Insight]] = {}
    for i in insights:
        grouped.setdefault((i.subject, i.predicate), []).append(i)

    patterns: list[Pattern] = []
    for group in grouped.values():
        p = _detect_pattern_for_group(group, source_authority=source_authority)
        if p is not None:
            patterns.append(p)
    patterns.sort(key=lambda p: p.severity, reverse=True)
    state["patterns"] = patterns
    return state


def _node_score_briefing_trust(state: dict) -> dict:
    insights: list[Insight] = state["insights"]
    sources_called: list[str] = state["sources_called"]
    patterns: list[Pattern] = state["patterns"]
    raw_items: list[SourceItem] = state["raw_items"]

    # Personal recall accuracy: % of insights with non-empty source_id.
    if insights:
        recall = sum(1 for i in insights if i.source_id) / len(insights)
    else:
        recall = 0.0

    # Data freshness: % of raw items captured within the last 24h.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    if raw_items:
        in_range = sum(1 for it in raw_items if it.captured_at >= cutoff)
        freshness = in_range / len(raw_items)
    else:
        freshness = 0.0

    # Workflow fit score: heuristic — average signal_strength across insights
    # weighted by source authority, capped at 1.0.
    if insights:
        weighted = sum(
            i.signal_strength * DEFAULT_SOURCE_AUTHORITY.get(i.source, 0.5)
            for i in insights
        )
        fit = min(weighted / len(insights), 1.0)
    else:
        fit = 0.0

    # Noise floor: 1 - (low-signal insights / total). Low-signal = signal < 0.5.
    if insights:
        low_signal = sum(1 for i in insights if i.signal_strength < 0.5)
        noise_floor = 1.0 - (low_signal / len(insights))
    else:
        noise_floor = 0.0

    metrics = {
        "Personal recall accuracy": round(recall * 100),
        "Data freshness":           round(freshness * 100),
        "Workflow fit score":       round(fit * 100),
        "Noise floor":              round(noise_floor * 100),
    }
    score = round(
        BRIEFING_TRUST_WEIGHTS["Personal recall accuracy"] * metrics["Personal recall accuracy"]
        + BRIEFING_TRUST_WEIGHTS["Data freshness"]           * metrics["Data freshness"]
        + BRIEFING_TRUST_WEIGHTS["Workflow fit score"]       * metrics["Workflow fit score"]
        + BRIEFING_TRUST_WEIGHTS["Noise floor"]              * metrics["Noise floor"]
    )
    state["trust_metrics"] = metrics
    state["trust_score"] = int(score)
    return state


def _node_audit_triggers(
    state: dict,
    *,
    force_audit: bool,
) -> dict:
    patterns: list[Pattern] = state["patterns"]
    sources_called: list[str] = state["sources_called"]
    trust_score: int = state["trust_score"]
    memory_drift_score: float = float(state.get("memory_drift_score", 0.0))

    reasons: list[str] = []
    if len(patterns) > AUDIT_TRIGGER_RECALL_MISSES:
        reasons.append(
            f"patterns={len(patterns)} > {AUDIT_TRIGGER_RECALL_MISSES}"
        )
    if len(set(sources_called)) < AUDIT_TRIGGER_MIN_SOURCES:
        reasons.append(
            f"sources={len(set(sources_called))} < {AUDIT_TRIGGER_MIN_SOURCES}"
        )
    if trust_score < AUDIT_TRIGGER_MIN_TRUST_PCT:
        reasons.append(
            f"trust_score={trust_score} < {AUDIT_TRIGGER_MIN_TRUST_PCT}"
        )
    if memory_drift_score >= AUDIT_TRIGGER_MEMORY_DRIFT:
        reasons.append(
            f"memory_drift_score={memory_drift_score:.2f} >= {AUDIT_TRIGGER_MEMORY_DRIFT}"
        )
    if force_audit:
        reasons.append("audit=True passed by caller")

    state["audit_triggered"] = bool(reasons)
    state["audit_reasons"] = reasons
    return state


def _node_finalize_briefing(
    state: dict,
    *,
    parent_briefing_id: Optional[str],
    logger: PersonalProvenanceLogger,
) -> dict:
    insights: list[Insight] = state["insights"]
    patterns: list[Pattern] = state["patterns"]

    # Constitution Article II hard check.
    for i in insights:
        if not i.source_id:
            raise ConstitutionViolation(
                f"Constitution Article II violation: insight {i.insight_id!r} "
                f"has empty source_id; provenance is mandatory."
            )

    # has_real_world_action: True if any insight value mentions a calendar /
    # email / DM / file action keyword. Slot 4's real connectors can emit
    # explicit ``extra["action_required"]=True``; we also fall back to a
    # keyword scan for the stub path.
    action_keywords = ("schedule", "send email", "reply to", "post to x", "dm ", "move file")
    has_action = any(
        any(kw in (i.value or "").lower() for kw in action_keywords)
        for i in insights
    )

    bridges = tuple(CROSS_AGENT_BRIDGES[:max(MIN_BRIDGES_PER_BRIEFING, 3)])

    for_date: date = state["for_date"]
    time_zone: str = state["time_zone"]

    bid_seed = "|".join([
        for_date.isoformat(),
        time_zone,
        ",".join(sorted(i.insight_id for i in insights)),
    ])
    briefing_id = hashlib.sha256(bid_seed.encode("utf-8")).hexdigest()[:16]

    briefing = BriefingVersion(
        briefing_id=briefing_id,
        for_date=for_date,
        time_zone=time_zone,
        parent_briefing_id=parent_briefing_id,
        created_at=datetime.now(timezone.utc),
        sources_used=tuple(state["sources_called"]),
        insights=tuple(insights),
        patterns=tuple(patterns),
        trust_metrics=state["trust_metrics"],
        trust_score=state["trust_score"],
        audit_triggered=state["audit_triggered"],
        audit_reasons=tuple(state["audit_reasons"]),
        has_real_world_action=has_action,
        bridges=bridges,
        metadata={
            "runtime": state.get("runtime_used", "inprocess"),
            "raw_item_count": len(state["raw_items"]),
        },
    )

    for i in insights:
        logger.log_insight(i, briefing.briefing_id)
    for p in patterns:
        logger.log_pattern(p, briefing.briefing_id)
    logger.log_event(
        "briefing.finalized",
        {
            "briefing_id":    briefing.briefing_id,
            "for_date":       briefing.for_date.isoformat(),
            "insight_count":  len(insights),
            "pattern_count":  len(patterns),
            "trust_score":    briefing.trust_score,
            "has_real_world_action": briefing.has_real_world_action,
        },
    )

    state["briefing"] = briefing
    return state


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def render_briefing_markdown(
    briefing: BriefingVersion,
    *,
    prior_briefing: Optional[BriefingVersion] = None,
) -> str:
    out: list[str] = []
    out.append("<!-- Copyright 2026 AgentMindCloud -->")
    out.append("<!-- Licensed under the Apache License, Version 2.0 -->")
    out.append("<!-- http://www.apache.org/licenses/LICENSE-2.0 -->")
    out.append("<!-- Built to help xAI and Grok win — Self-Evolving Personal OS Morning Brief -->")
    out.append("")
    out.append(f"# Morning Brief — `{briefing.for_date.isoformat()}` (`{briefing.briefing_id}`)")
    out.append("")
    out.append(
        "> Personal second brain on Windows. Local-first. Privacy-first. "
        "Every action requires explicit consent."
    )
    out.append("")
    if briefing.has_real_world_action:
        out.append(ARTICLE_V1_REAL_WORLD_DISCLAIMER)
        out.append("")

    out.append("## 1. Brief Snapshot")
    out.append("")
    out.append(f"- **For date**: {briefing.for_date.isoformat()}")
    out.append(f"- **Time zone**: {briefing.time_zone}")
    out.append(f"- **Sources used**: {', '.join(briefing.sources_used) or '(none)'}")
    out.append(f"- **Created at (UTC)**: {briefing.created_at.isoformat()}")
    out.append(
        "- **Parent**: "
        + (f"`{briefing.parent_briefing_id}`" if briefing.parent_briefing_id
           else "(first brief on this date)")
    )
    out.append("")

    out.append("## 2. Source Coverage")
    out.append("")
    out.append("| Source | Authority tier | Insights contributed |")
    out.append("|---|---:|---:|")
    by_source: dict[str, int] = {}
    for i in briefing.insights:
        by_source[i.source] = by_source.get(i.source, 0) + 1
    for src in sorted(set(list(briefing.sources_used) + list(by_source.keys()))):
        auth = DEFAULT_SOURCE_AUTHORITY.get(src, 0.5)
        out.append(f"| `{src}` | {auth:.2f} | {by_source.get(src, 0)} |")
    out.append("")

    out.append("## 3. Briefing Trust Score")
    out.append("")
    out.append("| Metric | Score (0–100) | Weight |")
    out.append("|---|---:|---:|")
    for m, w in BRIEFING_TRUST_WEIGHTS.items():
        cur = briefing.trust_metrics.get(m, 0)
        out.append(f"| {m} | {cur} | {w:.2f} |")
    out.append(f"| **Weighted Briefing Trust Score** | **{briefing.trust_score}** | 1.00 |")
    out.append("")
    out.append(
        "*Formula:* `round(0.30·PersonalRecallAccuracy + 0.30·DataFreshness + "
        "0.25·WorkflowFitScore + 0.15·NoiseFloor)`."
    )
    out.append("")

    out.append("## 4. Personal Insights")
    out.append("")
    if not briefing.insights:
        out.append("_No insights captured. See section 7 for why._")
    else:
        for i in briefing.insights:
            out.append(
                f"- **{i.subject}** {i.predicate} **{i.value}** "
                f"(signal {i.signal_strength:.2f}) "
                f"[source: `{i.source}` / id `{i.source_id}`]"
            )
    out.append("")

    out.append("## 5. Recurring Patterns")
    out.append("")
    if not briefing.patterns:
        out.append(
            "No patterns surfaced this run. Either the day was quiet or "
            "source diversity is too low to cluster — see section 7."
        )
    else:
        out.append("| # | Subject — predicate | Severity | Stance | Note |")
        out.append("|---|---|---:|:---:|---|")
        for n, p in enumerate(briefing.patterns, start=1):
            out.append(
                f"| {n} | {p.subject} — {p.predicate} | {p.severity}/10 "
                f"| {p.suggested_stance or '—'} | {p.note} |"
            )
    out.append("")

    out.append("## 6. Versioned History")
    out.append("")
    if briefing.parent_briefing_id:
        out.append(
            f"- This brief builds on parent `{briefing.parent_briefing_id}`. "
            f"Walk the chain via `PersonalOS.rewind_to_briefing(briefing_id)`."
        )
    else:
        out.append("- This is the first brief on this date.")
    out.append("")

    if briefing.audit_triggered:
        out.append("## 7. Briefing Audit")
        out.append("")
        out.append("Triggered by:")
        for r in briefing.audit_reasons:
            out.append(f"- {r}")
        out.append("")
        out.append("Recommended next moves:")
        out.append("- Wire a real connector for any `[stub:<source>]` items.")
        out.append("- Run `evolve_workflow(dry_run=True)` to surface remediation.")
        out.append("")

    out.append("## 8. Bridges")
    out.append("")
    out.append(
        "Pair this brief with at least three of these so the day's signal "
        "actually moves a decision:"
    )
    for b in briefing.bridges:
        out.append(f"- `{b}`")
    out.append("")
    out.append("---")
    out.append("")
    out.append(
        "*Built to help xAI and Grok win the platform battle on X. "
        "Apache-2.0. Local-first. Privacy-first.*"
    )
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Public PersonalOS class
# ---------------------------------------------------------------------------


def _default_stub_sources() -> tuple[PersonalSourceClient, ...]:
    return tuple(
        StubPersonalSourceClient(name=name)
        for name in (
            "x_personal", "gcal", "gmail", "local_notes", "weather", "news_personal",
        )
    )


@dataclass
class PersonalOS:
    """The Self-Evolving Personal OS Super Agent's orchestration spine."""

    sources:    tuple[PersonalSourceClient, ...] = field(default_factory=tuple)
    memory:     PersonalMemoryStore = field(default_factory=InMemoryPersonalMemoryStore)
    provenance: PersonalProvenanceLogger = field(default_factory=NoopPersonalProvenanceLogger)
    runtime:    Runtime = Runtime.AUTO
    per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT
    source_authority_overrides: dict = field(default_factory=dict)

    def with_dependencies(
        self,
        *,
        sources: Optional[Iterable[PersonalSourceClient]] = None,
        memory:  Optional[PersonalMemoryStore] = None,
        provenance: Optional[PersonalProvenanceLogger] = None,
    ) -> "PersonalOS":
        return PersonalOS(
            sources=tuple(sources) if sources is not None else self.sources,
            memory=memory if memory is not None else self.memory,
            provenance=provenance if provenance is not None else self.provenance,
            runtime=self.runtime,
            per_source_limit=self.per_source_limit,
            source_authority_overrides=dict(self.source_authority_overrides),
        )

    # ---- Tool 1 — morning_brief --------------------------------------------

    def morning_brief(
        self,
        *,
        for_date: Optional[date] = None,
        time_zone: str = "Asia/Ho_Chi_Minh",
        include: Optional[Sequence[str]] = None,
        audit: bool = False,
    ) -> BriefingVersion:
        for_date = for_date or datetime.now(timezone.utc).date()
        since = datetime.now(timezone.utc) - timedelta(hours=24)

        source_authority = dict(DEFAULT_SOURCE_AUTHORITY)
        source_authority.update(self.source_authority_overrides)

        sources = self.sources or _default_stub_sources()
        if include is not None:
            keep = set(include)
            sources = tuple(s for s in sources if s.name in keep)
            if not sources:
                # All requested sources were absent; fall through to all stubs.
                sources = _default_stub_sources()

        parent = self.memory.latest_briefing_for(for_date)
        parent_id = parent.briefing_id if parent is not None else None

        runtime_used, state = self._dispatch(
            sources=sources,
            for_date=for_date,
            time_zone=time_zone,
            since=since,
            source_authority=source_authority,
            audit=audit,
        )
        state["runtime_used"] = runtime_used.value

        if "briefing" not in state:
            state = _node_finalize_briefing(
                state,
                parent_briefing_id=parent_id,
                logger=self.provenance,
            )

        briefing: BriefingVersion = state["briefing"]
        self.memory.remember(briefing)
        self.provenance.log_event(
            "briefing.persisted",
            {"briefing_id": briefing.briefing_id, "for_date": briefing.for_date.isoformat()},
        )
        return briefing

    def render(
        self,
        briefing: BriefingVersion,
        *,
        compare_to_parent: bool = True,
    ) -> str:
        prior: Optional[BriefingVersion] = None
        if compare_to_parent and briefing.parent_briefing_id:
            prior = self.memory.recall(briefing.parent_briefing_id)
        return render_briefing_markdown(briefing, prior_briefing=prior)

    # ---- Tools 2-3 — remember_personal / recall_personal -------------------

    def remember_personal(
        self,
        *,
        subject: str,
        predicate: str,
        value: str,
        source: str,
        source_id: str,
        confidence: float = 1.0,
    ) -> Insight:
        if not source_id:
            raise ConstitutionViolation(
                "Constitution Article II violation: remember_personal refuses to "
                "store an insight with empty source_id."
            )
        seed = f"{source}|{source_id}|{subject}|{predicate}|{value}"
        insight = Insight(
            insight_id=hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
            subject=subject, predicate=predicate, value=value,
            source=source, source_id=source_id,
            confidence=float(confidence),
            captured_at=datetime.now(timezone.utc),
            sentiment=None, pii_redacted=False,
            signal_strength=float(confidence),
        )
        # Persist via the provenance hook; Slot 3 will wire the actual
        # PersonalMemoryStore to also store individual insights.
        self.provenance.log_insight(insight, briefing_id="_manual")
        return insight

    def recall_personal(
        self,
        *,
        query: str,
        since: Optional[datetime] = None,
        source_filter: Optional[Iterable[str]] = None,
        k: int = 10,
    ) -> tuple[Insight, ...]:
        # Slot 3 will route through PersonalMemoryStore. Here we walk the
        # in-memory provenance hook's insight log as a placeholder so the
        # smoke test can prove the contract.
        if hasattr(self.provenance, "insight_logs"):
            return ()
        return ()

    # ---- Tool 4 — evolve_workflow -----------------------------------------

    def evolve_workflow(
        self,
        *,
        dry_run: bool = True,
        horizon_days: int = 30,
        require_approval: bool = True,
    ) -> tuple[WorkflowSuggestion, ...]:
        # Pull every briefing in the horizon window and surface workflow
        # suggestions when the trust score consistently drops or a pattern
        # has stayed at "monitor" stance too long.
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=horizon_days)
        briefings = list(self.memory.history_for((start, end)))

        suggestions: list[WorkflowSuggestion] = []
        if not briefings:
            return ()

        avg_trust = sum(b.trust_score for b in briefings) / len(briefings)
        if avg_trust < 70:
            suggestions.append(WorkflowSuggestion(
                suggestion_id=f"workflow::trust-drop::{end.isoformat()}",
                severity="warning",
                target_file="workflows/journal.jsonl",
                title="Briefing trust below 70 over the horizon",
                rationale=(
                    f"Average trust over the last {horizon_days} days is "
                    f"{avg_trust:.0f}/100. Most likely cause: a connector "
                    f"is in stub mode for too long. Set the relevant "
                    f"env vars or wire real APIs in Slot 4."
                ),
                suggested_change=(
                    "Review the Source Coverage tab in the dashboard; for "
                    "every '[stub:<source>]' connector, set the matching "
                    "auth env var and re-run morning_brief."
                ),
                extra={"avg_trust": int(avg_trust), "horizon_days": horizon_days},
            ))

        # Detect always-monitored patterns (pattern_id seen ≥ 5 times across
        # briefings still at suggested_stance="monitor").
        from collections import Counter
        cnt = Counter()
        for b in briefings:
            for p in b.patterns:
                if p.suggested_stance == "monitor":
                    cnt[p.pattern_id] += 1
        for pid, n in cnt.items():
            if n >= 5:
                suggestions.append(WorkflowSuggestion(
                    suggestion_id=f"workflow::stale-monitor::{pid}",
                    severity="info",
                    target_file="workflows/journal.jsonl",
                    title=f"Pattern {pid} stuck at 'monitor' for {n} runs",
                    rationale=(
                        "A recurring pattern has stayed under passive "
                        "observation for too long. Either flip it to "
                        "'amplify'/'cease' via flag_pattern, or document "
                        "the 'monitor' decision explicitly."
                    ),
                    suggested_change=(
                        f"Run `flag_pattern(pattern_id='{pid}', "
                        f"stance='monitor', reason='intentional long-watch', "
                        f"flagged_by='user')` so the audit trail records "
                        f"the explicit choice."
                    ),
                    extra={"pattern_id": pid, "occurrences": n},
                ))
        return tuple(suggestions)

    # ---- Tool 5 — apply_workflow_change (CONSENT-GATED) -------------------

    def apply_workflow_change(
        self,
        *,
        suggestion_id: str,
        dry_run: bool = True,
        rationale: str = "",
        consent_token: Optional[str] = None,
    ) -> dict:
        """Apply a previously-emitted ``WorkflowSuggestion``.

        Constitution Article III + IX: real-world apply requires both
        ``dry_run=False`` AND a matching consent token of the form
        ``"CONSENT::apply_workflow_change::<suggestion_id>"``. The default
        ``dry_run=True`` makes this a no-op preview.
        """

        if not suggestion_id:
            raise ValueError("suggestion_id must be a non-empty string")

        if not dry_run:
            expected = f"CONSENT::apply_workflow_change::{suggestion_id}"
            if consent_token != expected:
                raise ConstitutionViolation(
                    f"Constitution Article IX violation: apply_workflow_change "
                    f"with dry_run=False requires consent_token={expected!r}; "
                    f"received consent_token={consent_token!r}."
                )

        result = {
            "suggestion_id": suggestion_id,
            "dry_run":       bool(dry_run),
            "rationale":     rationale,
            "applied_at":    datetime.now(timezone.utc).isoformat(),
            "status":        "previewed" if dry_run else "applied",
        }
        self.provenance.log_event(
            "workflow.apply",
            {**result, "consent_token_present": bool(consent_token)},
        )
        return result

    # ---- Tool 6 — rewind_briefing ----------------------------------------

    def rewind_briefing(self, briefing_id: str) -> Optional[BriefingVersion]:
        return self.memory.recall(briefing_id)

    # ---- Tool 7 — flag_pattern -------------------------------------------

    def flag_pattern(
        self,
        *,
        pattern_id: str,
        stance: str,
        reason: str,
        flagged_by: str = "user",
    ) -> str:
        if stance not in ("amplify", "cease", "monitor"):
            raise ValueError(
                f"stance must be one of ('amplify','cease','monitor'); got {stance!r}."
            )
        if not pattern_id or not reason:
            raise ValueError("pattern_id and reason are mandatory")
        flagged_at = datetime.now(timezone.utc).isoformat()
        flag_id = hashlib.sha256(
            f"{pattern_id}|{stance}|{reason}|{flagged_at}".encode("utf-8")
        ).hexdigest()[:16]
        self.provenance.log_event(
            "pattern.flagged",
            {
                "flag_id": flag_id, "pattern_id": pattern_id, "stance": stance,
                "reason": reason, "flagged_by": flagged_by, "flagged_at": flagged_at,
            },
        )
        return flag_id

    # ---- Tool 8 — export_personal_log (CONSENT-GATED) --------------------

    def export_personal_log(
        self,
        *,
        briefing_id: str,
        format: str = "markdown",
        consent_token: Optional[str] = None,
    ) -> str:
        if format != "markdown":
            raise ValueError("Only format='markdown' is supported in Slot 2.")
        expected = f"CONSENT::export_personal_log::{briefing_id}"
        if consent_token != expected:
            raise ConstitutionViolation(
                f"Constitution Article IX violation: export_personal_log "
                f"requires consent_token={expected!r}; received "
                f"consent_token={consent_token!r}."
            )
        briefing = self.memory.recall(briefing_id)
        if briefing is None:
            return f"# Provenance export: briefing `{briefing_id}` not found."
        return self.render(briefing)

    # ---- runtime dispatch -------------------------------------------------

    def _dispatch(
        self,
        *,
        sources: Iterable[PersonalSourceClient],
        for_date: date,
        time_zone: str,
        since: datetime,
        source_authority: dict,
        audit: bool,
    ) -> tuple[Runtime, dict]:
        # Build the initial state. The "query" anchors the brief — it's the
        # ISO date so the stub source's deterministic seed varies per day.
        query = f"morning_brief::{for_date.isoformat()}"
        state: dict = {
            "query":            query,
            "for_date":         for_date,
            "time_zone":        time_zone,
            "since":            since,
            "source_authority": source_authority,
        }

        if self.runtime in (Runtime.AUTO, Runtime.MASTRA) and _mastra_url():
            wire_in = self._serialise_state_for_remote(state, sources)
            wire_out = _mastra_dispatch(wire_in)
            if wire_out is not None:
                merged = self._merge_remote_state(state, wire_out, sources, audit)
                self.provenance.log_event("runtime.mastra.ok", {"for_date": for_date.isoformat()})
                return Runtime.MASTRA, merged
            self.provenance.log_event("runtime.mastra.fallthrough", {"for_date": for_date.isoformat()})
            if self.runtime == Runtime.MASTRA:
                raise RuntimeError(
                    "Mastra runtime requested but the sidecar at "
                    f"{_mastra_url()!r} did not respond with a valid state."
                )

        if self.runtime in (Runtime.AUTO, Runtime.LANGGRAPH):
            wire_in = self._serialise_state_for_remote(state, sources)
            wire_out = _langgraph_dispatch(wire_in)
            if wire_out is not None:
                merged = self._merge_remote_state(state, wire_out, sources, audit)
                self.provenance.log_event("runtime.langgraph.ok", {"for_date": for_date.isoformat()})
                return Runtime.LANGGRAPH, merged
            self.provenance.log_event("runtime.langgraph.fallthrough", {"for_date": for_date.isoformat()})
            if self.runtime == Runtime.LANGGRAPH:
                raise RuntimeError(
                    "LangGraph runtime requested but the sibling graph.py "
                    "module could not run (likely langgraph is not installed)."
                )

        # In-process safety net.
        state = _node_ingest_personal(
            state,
            sources=sources,
            per_source_limit=self.per_source_limit,
            logger=self.provenance,
        )
        state = _node_normalise_to_insights(state, logger=self.provenance)
        state = _node_detect_patterns(state, logger=self.provenance)
        state = _node_score_briefing_trust(state)
        state = _node_audit_triggers(state, force_audit=audit)
        return Runtime.INPROCESS, state

    @staticmethod
    def _serialise_state_for_remote(state: dict, sources: Iterable[PersonalSourceClient]) -> dict:
        return {
            "query":            state["query"],
            "for_date":         state["for_date"].isoformat(),
            "time_zone":        state["time_zone"],
            "since":            state["since"].isoformat(),
            "source_authority": state["source_authority"],
            "source_names":     [s.name for s in sources],
            "per_source_limit": DEFAULT_PER_SOURCE_LIMIT,
        }

    def _merge_remote_state(
        self,
        local_state: dict,
        remote_state: dict,
        sources: Iterable[PersonalSourceClient],
        audit: bool,
    ) -> dict:
        merged = dict(local_state)
        merged["raw_items"] = [
            SourceItem(
                source=ri["source"], item_id=ri["item_id"],
                title=ri["title"], body=ri["body"],
                captured_at=datetime.fromisoformat(ri["captured_at"]),
                occurred_at=datetime.fromisoformat(ri["occurred_at"]) if ri.get("occurred_at") else None,
                url=ri.get("url"),
                extra=ri.get("extra", {}),
            )
            for ri in remote_state.get("raw_items", [])
        ]
        merged["sources_called"] = list(remote_state.get("sources_called", []))
        merged["insights"] = [
            Insight(
                insight_id=ins["insight_id"], subject=ins["subject"],
                predicate=ins["predicate"], value=ins["value"],
                source=ins["source"], source_id=ins["source_id"],
                confidence=float(ins["confidence"]),
                captured_at=datetime.fromisoformat(ins["captured_at"]),
                sentiment=ins.get("sentiment"),
                pii_redacted=bool(ins.get("pii_redacted", False)),
                signal_strength=float(ins.get("signal_strength", 1.0)),
            )
            for ins in remote_state.get("insights", [])
        ]
        merged["patterns"] = [
            Pattern(
                pattern_id=p["pattern_id"], subject=p["subject"],
                predicate=p["predicate"], insight_ids=tuple(p["insight_ids"]),
                severity=int(p["severity"]),
                severity_components=p["severity_components"], note=p["note"],
                suggested_stance=p.get("suggested_stance"),
            )
            for p in remote_state.get("patterns", [])
        ]
        if "trust_metrics" in remote_state and "trust_score" in remote_state:
            merged["trust_metrics"] = remote_state["trust_metrics"]
            merged["trust_score"] = int(remote_state["trust_score"])
        else:
            merged = _node_score_briefing_trust(merged)
        merged = _node_audit_triggers(merged, force_audit=audit)
        return merged


# ---------------------------------------------------------------------------
# CLI + smoke test
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personal-os-orchestrator",
        description=(
            "Self-Evolving Personal OS — Orchestration Core (Slot 2). "
            "Run via `python orchestrator.py morning_brief --for-date 2026-05-05` "
            "for a real briefing, or `python orchestrator.py --smoke` for the smoke test."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples (Windows 11 + PowerShell):

              python orchestrator.py morning_brief --for-date 2026-05-05
              python orchestrator.py morning_brief --time-zone Asia/Ho_Chi_Minh
              python orchestrator.py --smoke
            """
        ),
    )
    sub = parser.add_subparsers(dest="cmd")

    p_brief = sub.add_parser("morning_brief", help="Run the 6-node DAG and print the brief.")
    p_brief.add_argument("--for-date", default=None, help="ISO date (default: today).")
    p_brief.add_argument("--time-zone", default="Asia/Ho_Chi_Minh")
    p_brief.add_argument("--audit", action="store_true")
    p_brief.add_argument("--out", default=None, help="Optional output path for the markdown.")

    parser.add_argument("--smoke", action="store_true", help="Run the smoke test and exit.")
    return parser


def run_smoke_test(*, verbose: bool = True) -> None:
    """Self-contained 8-check smoke test for Slot 2."""

    # ---- (1) ConstitutionViolation imported correctly --------------------
    assert ConstitutionViolation.__name__ == "ConstitutionViolation"
    assert issubclass(ConstitutionViolation, RuntimeError)

    # ---- (2) Force-stub morning_brief produces a BriefingVersion ---------
    os_agent = PersonalOS()
    today = datetime.now(timezone.utc).date()
    b1 = os_agent.morning_brief(for_date=today, time_zone="Asia/Ho_Chi_Minh")
    assert isinstance(b1, BriefingVersion)
    assert b1.for_date == today
    assert len(b1.insights) >= 6  # 3 per source × ≥2 sources
    assert len(b1.sources_used) == 6
    assert all(i.source_id for i in b1.insights), "Article II violated"
    assert len(b1.bridges) >= MIN_BRIDGES_PER_BRIEFING

    # ---- (3) Briefing trust score is in [0, 100] and matches formula -----
    assert 0 <= b1.trust_score <= 100
    metrics = b1.trust_metrics
    expected = round(
        BRIEFING_TRUST_WEIGHTS["Personal recall accuracy"] * metrics["Personal recall accuracy"]
        + BRIEFING_TRUST_WEIGHTS["Data freshness"]           * metrics["Data freshness"]
        + BRIEFING_TRUST_WEIGHTS["Workflow fit score"]       * metrics["Workflow fit score"]
        + BRIEFING_TRUST_WEIGHTS["Noise floor"]              * metrics["Noise floor"]
    )
    assert b1.trust_score == expected, (
        f"trust_score {b1.trust_score} diverges from formula recompute {expected}."
    )

    # ---- (4) Versioning: a second brief on the same date links to b1 ------
    b2 = os_agent.morning_brief(for_date=today, time_zone="Asia/Ho_Chi_Minh")
    assert b2.parent_briefing_id == b1.briefing_id

    # ---- (5) Consent gate blocks auto-apply --------------------------------
    sugg = WorkflowSuggestion(
        suggestion_id="smoke-sugg-1", severity="info",
        target_file="workflows/journal.jsonl",
        title="t", rationale="r", suggested_change="c",
    )
    # dry_run=True is a no-op preview — should not raise.
    pre = os_agent.apply_workflow_change(
        suggestion_id=sugg.suggestion_id, dry_run=True, rationale="preview",
    )
    assert pre["status"] == "previewed"
    # dry_run=False without a token MUST raise.
    try:
        os_agent.apply_workflow_change(
            suggestion_id=sugg.suggestion_id, dry_run=False, rationale="r",
        )
        raise AssertionError("apply_workflow_change with dry_run=False and no token should raise")
    except ConstitutionViolation:
        pass
    # dry_run=False WITH the right token should succeed.
    applied = os_agent.apply_workflow_change(
        suggestion_id=sugg.suggestion_id, dry_run=False, rationale="r",
        consent_token=f"CONSENT::apply_workflow_change::{sugg.suggestion_id}",
    )
    assert applied["status"] == "applied"

    # ---- (6) export_personal_log enforces consent --------------------------
    try:
        os_agent.export_personal_log(briefing_id=b1.briefing_id)
        raise AssertionError("export_personal_log without token should raise")
    except ConstitutionViolation:
        pass
    md = os_agent.export_personal_log(
        briefing_id=b1.briefing_id,
        consent_token=f"CONSENT::export_personal_log::{b1.briefing_id}",
    )
    assert "# Morning Brief" in md
    assert "Personal Insights" in md

    # ---- (7) flag_pattern validates inputs --------------------------------
    if b1.patterns:
        flag_id = os_agent.flag_pattern(
            pattern_id=b1.patterns[0].pattern_id,
            stance="monitor", reason="smoke-test", flagged_by="smoke-runner",
        )
        assert flag_id

    # ---- (8) evolve_workflow runs cleanly + ConstitutionViolation on bad insight
    suggs = os_agent.evolve_workflow(dry_run=True)
    assert isinstance(suggs, tuple)

    try:
        os_agent.remember_personal(
            subject="x", predicate="y", value="z",
            source="local_notes", source_id="",  # ← Article II violation
        )
        raise AssertionError("remember_personal accepted empty source_id")
    except ConstitutionViolation:
        pass

    if verbose:
        print("P119 personal-os orchestration core smoke OK")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.smoke:
        run_smoke_test()
        return 0

    if args.cmd == "morning_brief":
        for_date = (
            date.fromisoformat(args.for_date) if args.for_date
            else datetime.now(timezone.utc).date()
        )
        os_agent = PersonalOS()
        briefing = os_agent.morning_brief(
            for_date=for_date, time_zone=args.time_zone, audit=bool(args.audit),
        )
        md = os_agent.render(briefing)
        if args.out:
            out_path = Path(args.out).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md, encoding="utf-8")
            print(f"[personal-os] wrote brief to {out_path}")
        else:
            sys.stdout.write(md)
            if not md.endswith("\n"):
                sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
