# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Orchestration Core (P110, Recipe C Slot 2).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module is the orchestration spine for the Living Narrative Fabric Super
Agent: a versioned, provenance-first synthesis engine that pulls from X (via
Grok 4.3), news (NewsAPI + GNews), academia (Semantic Scholar), government
(data.gov), and open web (Crawl4AI), detects contradictions across those
sources without silently resolving them, and emits a rewindable synthesis
trail the creator can audit at any point.

Runtime selection (Mastra primary, LangGraph fallback, in-process safety net)
============================================================================

The orchestrator targets three runtimes in this order:

1. **Mastra** (preferred) — Mastra is a Node.js TypeScript orchestration
   framework. To use it, run a local Mastra sidecar exposing an HTTP endpoint
   and set ``MASTRA_HTTP_URL`` (e.g. ``http://localhost:4111/api/v1``). The
   orchestrator dispatches the graph state to the sidecar via JSON-RPC. The
   sidecar runs the Mastra ``Workflow`` and returns the same Pydantic state
   shape this module defines. Mastra adapter is best-effort — any failure
   falls through to LangGraph.

2. **LangGraph** (Python-native fallback) — when Mastra is not configured,
   the orchestrator imports ``graph.py`` (sibling module) and runs the same
   DAG in-process via LangGraph's ``StateGraph``. LangGraph is the Python
   default for Windows installs that don't ship Node.

3. **In-process** (always-on safety net) — when neither Mastra nor LangGraph
   is available, the orchestrator runs the same DAG sequentially in pure
   Python. This guarantees ``python orchestrator.py`` always succeeds on a
   fresh Windows machine with only ``pydantic`` installed.

Slot boundary contract
======================

Slot 2 (this file) builds **only the orchestration spine**. It explicitly
does NOT:

* Implement real source connectors (Slot 4 / P112 ships those — this slot
  uses ``StubSourceClient`` which returns deterministic seeded items).
* Implement real memory persistence (Slot 3 / P111 ships Mem0 + Qdrant —
  this slot uses ``InMemoryMemoryStore`` which holds versions in a dict).
* Implement real provenance logging (Slot 5 / P113 ships Langfuse + the
  ``provenance.log`` writer — this slot uses ``NoopProvenanceLogger``
  which records calls but never persists or streams anything).
* Render the Streamlit UI (Slot 7 / P115).

Every one of those is a Python ``Protocol`` defined in this module.
Slot N's job is to provide a concrete implementation and inject it via
``LivingNarrativeFabric.with_dependencies(...)``. The orchestrator code
in this file does NOT change when those slots ship.

Style alignment with P98–P102 (mandatory)
=========================================

The synthesis output mirrors the consistent style introduced in P98–P102
(analytics-summarizer, comment-engagement-booster, hashtag-strategy-advisor,
ab-test-suggester, monetization-optimizer):

* **4 official Synthesis Confidence metrics** with a fixed weighted
  formula:
  ``round(0.30·SourceDiversity_norm + 0.30·ProvenanceCompleteness_norm +
          0.25·CrossSourceAgreement_norm + 0.15·RecencyCoverage_norm)``.
* **Paradox surfacing in BOTH places**: when a contradiction crosses the
  authority threshold, it appears in BOTH the Synthesis Confidence metric
  table AND the dedicated Contradictions section.
* **5-arrow trend vocabulary** (▲▲ / ▲ / ▬ / ▼ / ▼▼) for any metric
  comparison against the prior version.
* **Mandatory bridges** to ≥3 cross-template / cross-super-agent slugs in
  every emitted synthesis (self-evolving-personal-os, cross-reality-action-
  fabric, plus any relevant creator templates).
* **Audit triggers**: a Synthesis Audit section auto-appends when
  contradictions > 3 OR source_count < 3 OR confidence_avg < 0.5 OR the
  caller passes ``audit=True``.

Constitution rules enforced at runtime
======================================

* "Never publish without provenance" — ``finalize()`` raises
  ``ConstitutionViolation`` if any claim has ``source_id is None``.
* "Flag contradictions; do not resolve them silently" — the contradiction
  detector NEVER picks a winner; both sides are kept verbatim with their
  source authority and recency.
* "Source citations are mandatory on every claim" — every ``Claim`` row
  carries a non-empty ``source_id``; the renderer refuses to omit them.
* "User can rewind to any prior state — synthesis is versioned" — every
  ``SynthesisVersion`` records a ``parent_version_id`` (or ``None`` for
  the first version on a topic). Slot 3's memory layer makes the rewind
  walk persistent.

CLI smoke test (Windows 11 + PowerShell)
========================================

::

    cd templates\\super-agents\\living-narrative-fabric
    python -m pip install -r requirements.txt
    python orchestrator.py --topic "Grok Agent OS launch" --time-range 7d --runtime auto

A successful smoke run emits a markdown synthesis to stdout with:

* Topic Snapshot
* Source Coverage table
* Synthesis Confidence metric table + weighted score
* Key Claims (every line ends with ``[source: <source_id>]``)
* Contradictions (paradox surfacing, with severity)
* Versioned History (parent_version_id chain)
* Bridges (≥3 cross-template slugs)
* Synthesis Audit (auto-appended when triggers fire)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from random import Random
from typing import Callable, Iterable, Optional, Protocol, Sequence, runtime_checkable


# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SLUG = "living-narrative-fabric"

#: Default Windows-correct local data root. Honours ``$env:LOCALAPPDATA`` when
#: running on Windows; falls back to ``~/.local/share/grok-agent`` everywhere
#: else (CI, Codespaces, Linux dev boxes) so the smoke test runs anywhere.
def _default_appdata_root() -> Path:
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        return Path(localappdata) / "grok-agent" / SLUG
    return Path.home() / ".local" / "share" / "grok-agent" / SLUG


DEFAULT_APPDATA_ROOT = _default_appdata_root()

#: Source authority tiers. Higher = more trustworthy. Numbers are deliberate
#: defaults; Slot 4 (real connectors) may override per-source via the
#: ``source_authority_overrides`` arg to ``LivingNarrativeFabric``.
DEFAULT_SOURCE_AUTHORITY = {
    "semantic_scholar": 0.95,  # peer-reviewed
    "data_gov":         0.90,  # primary government data
    "newsapi":          0.65,  # curated news
    "gnews":            0.65,  # curated news
    "crawl4ai":         0.45,  # open web scrape
    "x_search":         0.35,  # social signal (via Grok 4.3)
}

#: Synthesis Confidence weighted-formula coefficients. Locked at the runner
#: level so every emitted synthesis uses the same scoring across versions.
SYNTHESIS_CONFIDENCE_WEIGHTS = {
    "Source diversity":         0.30,
    "Provenance completeness":  0.30,
    "Cross-source agreement":   0.25,
    "Recency coverage":         0.15,
}

#: Contradiction severity weighted-formula coefficients (paradox surfacing).
CONTRADICTION_SEVERITY_WEIGHTS = {
    "Authority spread":         0.40,
    "Value disagreement":       0.30,
    "Recency skew":             0.20,
    "Subject centrality":       0.10,
}

#: 5-arrow trend bucketing thresholds (% delta vs the prior version).
TREND_THRESHOLDS = {
    "strong_rise":   25.0,
    "rise":           5.0,
    "fall":          -5.0,
    "strong_fall":  -25.0,
}

TREND_ARROWS = {
    "strong_rise":  "▲▲",
    "rise":         "▲",
    "stable":       "▬",
    "fall":         "▼",
    "strong_fall":  "▼▼",
}

#: Audit triggers — any one fires the auto-appended Synthesis Audit section.
AUDIT_TRIGGER_CONTRADICTIONS = 3
AUDIT_TRIGGER_MIN_SOURCES = 3
AUDIT_TRIGGER_MIN_CONFIDENCE = 0.5

#: Mandatory cross-Super-Agent / cross-template bridges. The renderer pulls
#: the first ``MIN_BRIDGES_PER_SYNTHESIS`` of these into every emitted output.
CROSS_AGENT_BRIDGES = (
    "self-evolving-personal-os",     # Super Agent #2 — personalises the synthesis
    "cross-reality-action-fabric",   # Super Agent #3 — turns synthesis into action
    "analytics-summarizer",          # creator template — periodises performance
    "competitor-watch",              # creator template — peer narratives
    "content-idea-generator",        # creator template — synthesis → posts
    "research-assistant",            # creator template — deeper recall
    "x-money-companion-dashboard",   # X Money tool #1 — contextualises spend
)
MIN_BRIDGES_PER_SYNTHESIS = 3

#: Hard cap on raw items pulled per source per run. Slot 4's real clients
#: should respect this cap so cost stays predictable.
DEFAULT_PER_SOURCE_LIMIT = 25

#: Default Article V.1 disclaimer banner — applied when the synthesis touches
#: finance subjects (finance/cashtag/portfolio claim subjects).
ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This synthesis surfaces public information; "
    "always consult a licensed financial advisor before making decisions."
)


# ---------------------------------------------------------------------------
# Domain model (Pydantic-light dataclasses — no hard pydantic dep at import)
# ---------------------------------------------------------------------------


class Runtime(str, Enum):
    AUTO = "auto"
    MASTRA = "mastra"
    LANGGRAPH = "langgraph"
    INPROCESS = "inprocess"


class TimeRange(str, Enum):
    D7 = "7d"
    D30 = "30d"
    D90 = "90d"

    @property
    def days(self) -> int:
        return {"7d": 7, "30d": 30, "90d": 90}[self.value]


@dataclass(frozen=True)
class SourceItem:
    """One raw item retrieved from a source. Slot 4 connectors emit these."""

    source: str            # one of DEFAULT_SOURCE_AUTHORITY keys
    item_id: str           # source-local identifier (URL, DOI, tweet ID...)
    title: str
    body: str              # short excerpt or summary (NOT full article — keep < 2KB)
    retrieved_at: datetime
    published_at: Optional[datetime] = None
    url: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Claim:
    """A normalised assertion derived from one or more SourceItems.

    Constitution rule "Source citations mandatory" requires every Claim
    carry a non-empty ``source_id`` (the SourceItem.item_id it came from).
    """

    claim_id: str          # sha256-derived stable id
    subject: str           # what the claim is about (entity, topic, cashtag...)
    predicate: str         # the relationship (is, has, says, supports, ...)
    value: str             # the asserted value (verbatim from source)
    source: str            # the source name (e.g. "newsapi")
    source_id: str         # the SourceItem.item_id (NEVER empty)
    confidence: float      # 0.0–1.0 — how confidently the extractor parsed
    extracted_at: datetime
    sentiment: Optional[str] = None  # "positive" / "neutral" / "negative" / None


@dataclass(frozen=True)
class Contradiction:
    """Two (or more) claims on the same subject+predicate that disagree."""

    contradiction_id: str
    subject: str
    predicate: str
    claim_ids: tuple[str, ...]            # the conflicting claim_ids (>= 2)
    severity: int                         # 0–10 weighted score
    severity_components: dict             # the 4 components that produced severity
    note: str                             # short renderable explanation


@dataclass(frozen=True)
class SynthesisVersion:
    """One immutable synthesis snapshot. Slot 3's memory layer persists these."""

    version_id: str
    topic: str
    time_range: str
    parent_version_id: Optional[str]      # None == first version on this topic
    created_at: datetime
    sources_used: tuple[str, ...]
    claims: tuple[Claim, ...]
    contradictions: tuple[Contradiction, ...]
    confidence_metrics: dict              # {"Source diversity": 73, ...}
    confidence_score: int                 # weighted 0–100
    audit_triggered: bool
    audit_reasons: tuple[str, ...]
    has_finance_subject: bool             # gates the V.1 disclaimer
    bridges: tuple[str, ...]              # >= MIN_BRIDGES_PER_SYNTHESIS
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Slot extension Protocols — Slots 3, 4, 5 plug in via dependency injection
# ---------------------------------------------------------------------------


@runtime_checkable
class SourceClient(Protocol):
    """Slot 4 (P112) ships real connectors that satisfy this Protocol."""

    name: str

    def fetch(self, query: str, since: datetime, limit: int) -> Sequence[SourceItem]:
        ...


@runtime_checkable
class MemoryStore(Protocol):
    """Slot 3 (P111) ships Mem0+Qdrant. Until then the in-memory stub is used."""

    def remember(self, version: SynthesisVersion) -> None:
        ...

    def recall(self, version_id: str) -> Optional[SynthesisVersion]:
        ...

    def latest_version_for(self, topic: str) -> Optional[SynthesisVersion]:
        ...

    def history_for(self, topic: str) -> Sequence[SynthesisVersion]:
        ...


@runtime_checkable
class ProvenanceLogger(Protocol):
    """Slot 5 (P113) ships Langfuse + provenance.log. Until then no-op."""

    def log_event(self, event_type: str, payload: dict) -> None:
        ...

    def log_claim(self, claim: Claim, version_id: str) -> None:
        ...

    def log_contradiction(self, contradiction: Contradiction, version_id: str) -> None:
        ...


class ConstitutionViolation(RuntimeError):
    """Raised whenever a hard Constitution rule is broken at runtime."""


# ---------------------------------------------------------------------------
# Default (no-op / stub) implementations of the slot Protocols
# ---------------------------------------------------------------------------


@dataclass
class StubSourceClient:
    """Deterministic stub source. Slot 4 (P112) replaces these with real clients.

    The stub returns ``per_source_limit`` deterministic SourceItems seeded by
    ``sha256(name + query + since)`` so smoke tests are reproducible. Each
    item carries an explicit ``[stub source — replace with real connector
    at Slot 4 / P112]`` line in its body so the synthesis renderer can show
    callers that the source is not yet wired live.
    """

    name: str
    per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT
    seeded_subjects: tuple[str, ...] = ("Grok Agent OS", "xAI", "X creators")

    def fetch(self, query: str, since: datetime, limit: int) -> Sequence[SourceItem]:
        seed = hashlib.sha256(
            f"{self.name}|{query}|{since.isoformat()}".encode("utf-8")
        ).hexdigest()
        rng = Random(seed)
        actual_limit = min(limit, self.per_source_limit)

        # 3 deterministic items per source — small enough to keep CLI smoke
        # output readable, big enough to exercise the contradiction detector.
        items: list[SourceItem] = []
        for n in range(min(3, actual_limit)):
            subj = rng.choice(self.seeded_subjects)
            stance = rng.choice(["supports", "questions", "neutral on"])
            value = rng.choice(["accelerating adoption", "slowing adoption", "uncertain trajectory"])
            published = since + timedelta(hours=rng.randint(1, 24 * ((datetime.now(timezone.utc) - since).days or 1)))
            items.append(
                SourceItem(
                    source=self.name,
                    item_id=f"{self.name}-stub-{seed[:8]}-{n}",
                    title=f"[stub:{self.name}] {subj} — {stance} {value}",
                    body=(
                        f"[stub source — replace with real connector at Slot 4 / P112] "
                        f"Source {self.name} reports {subj} {stance} {value}. "
                        f"This is a deterministic seeded item; numbers and quotes are "
                        f"placeholders only."
                    ),
                    retrieved_at=datetime.now(timezone.utc),
                    published_at=published,
                    url=None,
                    extra={"stub": True, "source_authority": DEFAULT_SOURCE_AUTHORITY.get(self.name, 0.5)},
                )
            )
        return items


@dataclass
class InMemoryMemoryStore:
    """Slot 3 (P111) replaces this with Mem0+Qdrant. Until then a dict is fine.

    The dict is intentionally process-local: the smoke test demonstrates the
    versioning chain works without persisting anything outside RAM. Slot 3
    swaps the dict for Mem0 episodic + Qdrant semantic retrieval; the
    orchestrator does not change.
    """

    _by_id: dict[str, SynthesisVersion] = field(default_factory=dict)
    _by_topic: dict[str, list[str]] = field(default_factory=dict)

    def remember(self, version: SynthesisVersion) -> None:
        self._by_id[version.version_id] = version
        self._by_topic.setdefault(version.topic, []).append(version.version_id)

    def recall(self, version_id: str) -> Optional[SynthesisVersion]:
        return self._by_id.get(version_id)

    def latest_version_for(self, topic: str) -> Optional[SynthesisVersion]:
        ids = self._by_topic.get(topic) or []
        if not ids:
            return None
        return self._by_id.get(ids[-1])

    def history_for(self, topic: str) -> Sequence[SynthesisVersion]:
        ids = self._by_topic.get(topic) or []
        return tuple(self._by_id[i] for i in ids if i in self._by_id)


@dataclass
class NoopProvenanceLogger:
    """Slot 5 (P113) replaces this with Langfuse + provenance.log writer.

    The no-op records counts in-memory so the CLI smoke test can assert
    "every claim was logged exactly once" without writing anything to disk.
    """

    events: list[tuple[str, dict]] = field(default_factory=list)
    claim_logs: list[tuple[str, str]] = field(default_factory=list)
    contradiction_logs: list[tuple[str, str]] = field(default_factory=list)

    def log_event(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))

    def log_claim(self, claim: Claim, version_id: str) -> None:
        self.claim_logs.append((claim.claim_id, version_id))

    def log_contradiction(self, contradiction: Contradiction, version_id: str) -> None:
        self.contradiction_logs.append((contradiction.contradiction_id, version_id))


# ---------------------------------------------------------------------------
# Runtime adapters — Mastra (HTTP) and LangGraph (in-process import)
# ---------------------------------------------------------------------------


def _mastra_url() -> Optional[str]:
    """Return the configured Mastra sidecar URL or ``None``."""

    url = os.environ.get("MASTRA_HTTP_URL")
    if url and url.strip():
        return url.strip().rstrip("/")
    return None


def _mastra_dispatch(state_in: dict, *, timeout: float = 30.0) -> Optional[dict]:
    """Best-effort dispatch to a local Mastra sidecar. Returns None on any failure.

    The sidecar is expected to expose ``POST {MASTRA_HTTP_URL}/workflows/
    living-narrative-fabric/run`` accepting the JSON-serialisable state and
    returning the same shape with the graph nodes already executed. The
    sidecar implementation is out of scope for Slot 2 — this function
    returns ``None`` (clean fallback) when the sidecar is unreachable or
    when ``httpx`` is not installed, so the orchestrator never blocks on
    a missing Node runtime.
    """

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
            if not isinstance(data, dict):
                return None
            return data
    except Exception:
        return None


def _langgraph_dispatch(state_in: dict) -> Optional[dict]:
    """Best-effort dispatch to the sibling ``graph.py`` LangGraph runtime.

    Returns ``None`` when LangGraph itself is not installed (fallback path).
    """

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
# Graph nodes (the same DAG every runtime executes)
# ---------------------------------------------------------------------------


def _node_ingest(
    state: dict,
    *,
    sources: Iterable[SourceClient],
    per_source_limit: int,
    logger: ProvenanceLogger,
) -> dict:
    topic: str = state["topic"]
    since: datetime = state["since"]

    raw_items: list[SourceItem] = []
    sources_called: list[str] = []
    for src in sources:
        try:
            items = list(src.fetch(topic, since, per_source_limit))
        except Exception as exc:
            logger.log_event(
                "ingest.error",
                {"source": getattr(src, "name", "?"), "error": str(exc)},
            )
            continue
        sources_called.append(src.name)
        raw_items.extend(items)
        logger.log_event(
            "ingest.ok",
            {"source": src.name, "item_count": len(items)},
        )

    state["raw_items"] = raw_items
    state["sources_called"] = sources_called
    return state


def _node_normalise_to_claims(state: dict, *, logger: ProvenanceLogger) -> dict:
    """Convert raw SourceItems → Claims. Slot 4 will swap this for a Grok
    structured-extraction call; the no-op extractor here produces ONE claim
    per item (subject = topic, predicate = "is described by source", value
    = item.title) so the contradiction detector and the renderer have data
    to work with during smoke tests.
    """

    raw_items: list[SourceItem] = state["raw_items"]
    topic: str = state["topic"]
    claims: list[Claim] = []

    for item in raw_items:
        subject = topic
        predicate = "is described by source"
        value = item.title.replace("[stub:" + item.source + "] ", "")
        claim_id = hashlib.sha256(
            f"{item.source}|{item.item_id}|{subject}|{predicate}|{value}".encode("utf-8")
        ).hexdigest()[:16]
        confidence = 0.7 if item.extra.get("stub") else 0.85
        claim = Claim(
            claim_id=claim_id,
            subject=subject,
            predicate=predicate,
            value=value,
            source=item.source,
            source_id=item.item_id,
            confidence=confidence,
            extracted_at=datetime.now(timezone.utc),
            sentiment=None,
        )
        claims.append(claim)

    state["claims"] = claims
    return state


def _detect_contradictions_for_group(
    group_claims: list[Claim],
    *,
    source_authority: dict,
) -> Optional[Contradiction]:
    """Within a group of claims sharing (subject, predicate), detect disagreement.

    Constitution: this function NEVER picks a winner. It returns a
    ``Contradiction`` describing the disagreement; callers surface BOTH
    sides verbatim.
    """

    if len(group_claims) < 2:
        return None

    distinct_values = {c.value for c in group_claims}
    if len(distinct_values) < 2:
        return None  # all sources agree — not a contradiction

    # Authority spread (0–1): max - min authority across the disagreeing sources.
    authorities = [source_authority.get(c.source, 0.5) for c in group_claims]
    authority_spread = max(authorities) - min(authorities)

    # Value disagreement (0–1): proportion of distinct values vs total claims.
    value_disagreement = len(distinct_values) / len(group_claims)

    # Recency skew (0–1): days between the earliest and latest extraction
    # divided by 30 (capped). Larger skew = more suspicion the disagreement
    # reflects a real shift over time.
    times = [c.extracted_at for c in group_claims]
    skew_days = (max(times) - min(times)).total_seconds() / 86400.0
    recency_skew = min(skew_days / 30.0, 1.0)

    # Subject centrality (0–1): how many claims in the run reference this
    # subject. We approximate via a normalised count from the caller; here
    # we use the group size / 10 cap.
    subject_centrality = min(len(group_claims) / 10.0, 1.0)

    components = {
        "Authority spread":     round(authority_spread, 3),
        "Value disagreement":   round(value_disagreement, 3),
        "Recency skew":         round(recency_skew, 3),
        "Subject centrality":   round(subject_centrality, 3),
    }
    severity = round(
        10 * (
            CONTRADICTION_SEVERITY_WEIGHTS["Authority spread"] * authority_spread
            + CONTRADICTION_SEVERITY_WEIGHTS["Value disagreement"] * value_disagreement
            + CONTRADICTION_SEVERITY_WEIGHTS["Recency skew"] * recency_skew
            + CONTRADICTION_SEVERITY_WEIGHTS["Subject centrality"] * subject_centrality
        )
    )

    cid_seed = "|".join(sorted(c.claim_id for c in group_claims))
    contradiction_id = hashlib.sha256(cid_seed.encode("utf-8")).hexdigest()[:16]

    note = (
        f"{len(distinct_values)} distinct values asserted by "
        f"{len(group_claims)} sources; authority spread "
        f"{authority_spread:.2f}; recency skew {skew_days:.1f}d. "
        f"Both sides are kept verbatim — this orchestrator never picks a winner."
    )

    return Contradiction(
        contradiction_id=contradiction_id,
        subject=group_claims[0].subject,
        predicate=group_claims[0].predicate,
        claim_ids=tuple(c.claim_id for c in group_claims),
        severity=int(severity),
        severity_components=components,
        note=note,
    )


def _node_detect_contradictions(state: dict, *, logger: ProvenanceLogger) -> dict:
    claims: list[Claim] = state["claims"]
    source_authority: dict = state["source_authority"]

    grouped: dict[tuple[str, str], list[Claim]] = {}
    for c in claims:
        key = (c.subject, c.predicate)
        grouped.setdefault(key, []).append(c)

    contradictions: list[Contradiction] = []
    for group in grouped.values():
        cd = _detect_contradictions_for_group(group, source_authority=source_authority)
        if cd is not None:
            contradictions.append(cd)

    contradictions.sort(key=lambda c: c.severity, reverse=True)
    state["contradictions"] = contradictions
    return state


def _node_score_confidence(state: dict) -> dict:
    claims: list[Claim] = state["claims"]
    sources_called: list[str] = state["sources_called"]
    contradictions: list[Contradiction] = state["contradictions"]
    time_range: str = state["time_range"]
    raw_items: list[SourceItem] = state["raw_items"]

    # Source diversity: distinct sources / 6 (the official fabric size). 0–1.
    diversity = min(len(set(sources_called)) / 6.0, 1.0)

    # Provenance completeness: fraction of claims with non-empty source_id.
    if claims:
        provenance = sum(1 for c in claims if c.source_id) / len(claims)
    else:
        provenance = 0.0

    # Cross-source agreement: 1 - (contradicting_groups / total_groups).
    grouped_keys = {(c.subject, c.predicate) for c in claims}
    if grouped_keys:
        agreement = 1.0 - min(len(contradictions) / len(grouped_keys), 1.0)
    else:
        agreement = 0.0

    # Recency coverage: fraction of items whose published_at is within the
    # requested time range. Items with no published_at count as half.
    days = TimeRange(time_range).days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if raw_items:
        in_range = 0.0
        for item in raw_items:
            if item.published_at is None:
                in_range += 0.5
            elif item.published_at >= cutoff:
                in_range += 1.0
        recency = in_range / len(raw_items)
    else:
        recency = 0.0

    metrics = {
        "Source diversity":         round(diversity * 100),
        "Provenance completeness":  round(provenance * 100),
        "Cross-source agreement":   round(agreement * 100),
        "Recency coverage":         round(recency * 100),
    }
    score = round(
        SYNTHESIS_CONFIDENCE_WEIGHTS["Source diversity"] * metrics["Source diversity"]
        + SYNTHESIS_CONFIDENCE_WEIGHTS["Provenance completeness"] * metrics["Provenance completeness"]
        + SYNTHESIS_CONFIDENCE_WEIGHTS["Cross-source agreement"] * metrics["Cross-source agreement"]
        + SYNTHESIS_CONFIDENCE_WEIGHTS["Recency coverage"] * metrics["Recency coverage"]
    )

    state["confidence_metrics"] = metrics
    state["confidence_score"] = int(score)
    return state


def _node_audit_triggers(state: dict, *, force_audit: bool) -> dict:
    contradictions: list[Contradiction] = state["contradictions"]
    sources_called: list[str] = state["sources_called"]
    confidence_score: int = state["confidence_score"]

    reasons: list[str] = []
    if len(contradictions) > AUDIT_TRIGGER_CONTRADICTIONS:
        reasons.append(
            f"contradictions={len(contradictions)} > {AUDIT_TRIGGER_CONTRADICTIONS}"
        )
    if len(set(sources_called)) < AUDIT_TRIGGER_MIN_SOURCES:
        reasons.append(
            f"sources={len(set(sources_called))} < {AUDIT_TRIGGER_MIN_SOURCES}"
        )
    if confidence_score < int(AUDIT_TRIGGER_MIN_CONFIDENCE * 100):
        reasons.append(
            f"confidence_score={confidence_score} < {int(AUDIT_TRIGGER_MIN_CONFIDENCE * 100)}"
        )
    if force_audit:
        reasons.append("audit=True passed by caller")

    state["audit_triggered"] = bool(reasons)
    state["audit_reasons"] = reasons
    return state


def _node_finalize(
    state: dict,
    *,
    parent_version_id: Optional[str],
    logger: ProvenanceLogger,
) -> dict:
    """Build the immutable SynthesisVersion. Enforces hard Constitution rules."""

    claims: list[Claim] = state["claims"]
    contradictions: list[Contradiction] = state["contradictions"]

    # Constitution enforcement (HARD): "Source citations are mandatory".
    for c in claims:
        if not c.source_id:
            raise ConstitutionViolation(
                f"Constitution violation: claim {c.claim_id!r} has no source_id."
            )

    finance_keywords = ("$", "price", "market cap", "tax", "payout", "revenue")
    has_finance_subject = any(
        any(kw.lower() in c.subject.lower() or kw.lower() in c.value.lower() for kw in finance_keywords)
        for c in claims
    )

    bridges = tuple(CROSS_AGENT_BRIDGES[:max(MIN_BRIDGES_PER_SYNTHESIS, 3)])

    version_id_seed = "|".join([
        state["topic"],
        state["time_range"],
        state["since"].isoformat(),
        ",".join(sorted(c.claim_id for c in claims)),
    ])
    version_id = hashlib.sha256(version_id_seed.encode("utf-8")).hexdigest()[:16]

    version = SynthesisVersion(
        version_id=version_id,
        topic=state["topic"],
        time_range=state["time_range"],
        parent_version_id=parent_version_id,
        created_at=datetime.now(timezone.utc),
        sources_used=tuple(state["sources_called"]),
        claims=tuple(claims),
        contradictions=tuple(contradictions),
        confidence_metrics=state["confidence_metrics"],
        confidence_score=state["confidence_score"],
        audit_triggered=state["audit_triggered"],
        audit_reasons=tuple(state["audit_reasons"]),
        has_finance_subject=has_finance_subject,
        bridges=bridges,
        metadata={
            "runtime": state.get("runtime_used", "inprocess"),
            "raw_item_count": len(state["raw_items"]),
        },
    )

    # Record provenance for every claim + every contradiction (Slot 5 plug).
    for c in claims:
        logger.log_claim(c, version.version_id)
    for cd in contradictions:
        logger.log_contradiction(cd, version.version_id)
    logger.log_event(
        "synthesis.finalized",
        {
            "version_id": version.version_id,
            "topic": version.topic,
            "claim_count": len(claims),
            "contradiction_count": len(contradictions),
            "confidence_score": version.confidence_score,
        },
    )

    state["synthesis_version"] = version
    return state


# ---------------------------------------------------------------------------
# Markdown renderer (consistent style with P98–P102)
# ---------------------------------------------------------------------------


def _trend_arrow(current: float, prior: Optional[float]) -> str:
    if prior is None or prior == 0:
        return TREND_ARROWS["stable"]
    delta_pct = (current - prior) / prior * 100.0
    if delta_pct >= TREND_THRESHOLDS["strong_rise"]:
        return TREND_ARROWS["strong_rise"]
    if delta_pct >= TREND_THRESHOLDS["rise"]:
        return TREND_ARROWS["rise"]
    if delta_pct <= TREND_THRESHOLDS["strong_fall"]:
        return TREND_ARROWS["strong_fall"]
    if delta_pct <= TREND_THRESHOLDS["fall"]:
        return TREND_ARROWS["fall"]
    return TREND_ARROWS["stable"]


def render_synthesis_markdown(
    version: SynthesisVersion,
    *,
    prior_version: Optional[SynthesisVersion] = None,
) -> str:
    """Render a SynthesisVersion to the official 7/8-section markdown.

    Style is locked to the P98–P102 paradox-pattern + dual-surface +
    weighted-formula + bridges + audit-trigger format.

    Section numbering is always consecutive: when the Synthesis Audit
    section is not triggered the renderer emits 7 sections; when it is,
    8 sections (audit appended at the end so the user reads it right
    before deciding the next move).
    """

    out: list[str] = []
    sec_num = 0

    def heading(title: str) -> str:
        nonlocal sec_num
        sec_num += 1
        return f"## {sec_num}. {title}"

    out.append("<!-- Copyright 2026 AgentMindCloud -->")
    out.append("<!-- Licensed under the Apache License, Version 2.0 -->")
    out.append("<!-- http://www.apache.org/licenses/LICENSE-2.0 -->")
    out.append("<!-- Built for xAI, X, Grok and the ecosystem community — Living Narrative Fabric synthesis -->")
    out.append("")
    out.append(f"# Living Narrative Fabric — Synthesis `{version.version_id}`")
    out.append("")
    out.append(
        "> Versioned, provenance-first synthesis across X, news, academia, government, "
        "and open web. This orchestrator never silently resolves contradictions — "
        "both sides are kept verbatim."
    )
    out.append("")

    if version.has_finance_subject:
        out.append(ARTICLE_V1_DISCLAIMER)
        out.append("")

    # Topic Snapshot
    out.append(heading("Topic Snapshot"))
    out.append("")
    out.append(f"- **Topic**: {version.topic}")
    out.append(f"- **Time range**: {version.time_range}")
    out.append(f"- **Sources used**: {', '.join(version.sources_used) or '(none)'}")
    out.append(f"- **Created at (UTC)**: {version.created_at.isoformat()}")
    out.append(
        "- **Parent version**: "
        + (f"`{version.parent_version_id}`" if version.parent_version_id else "(first version on this topic)")
    )
    out.append("")

    # Source Coverage
    out.append(heading("Source Coverage"))
    out.append("")
    out.append("| Source | Authority tier | Claims contributed |")
    out.append("|---|---:|---:|")
    by_source: dict[str, int] = {}
    for c in version.claims:
        by_source[c.source] = by_source.get(c.source, 0) + 1
    for src in sorted(set(list(version.sources_used) + list(by_source.keys()))):
        auth = DEFAULT_SOURCE_AUTHORITY.get(src, 0.5)
        out.append(f"| `{src}` | {auth:.2f} | {by_source.get(src, 0)} |")
    out.append("")

    # Synthesis Confidence (4-row table + weighted score, P98–P102 style)
    confidence_section_num = sec_num + 1  # remember for audit-section back-reference
    out.append(heading("Synthesis Confidence"))
    out.append("")
    out.append("| Metric | Score (0–100) | Weight | Trend vs parent |")
    out.append("|---|---:|---:|:---:|")
    for metric_name, weight in SYNTHESIS_CONFIDENCE_WEIGHTS.items():
        current = version.confidence_metrics.get(metric_name, 0)
        prior = (
            prior_version.confidence_metrics.get(metric_name)
            if prior_version is not None
            else None
        )
        arrow = _trend_arrow(current, prior)
        out.append(f"| {metric_name} | {current} | {weight:.2f} | {arrow} |")
    out.append(
        f"| **Weighted Synthesis Confidence** | **{version.confidence_score}** | 1.00 | "
        f"{_trend_arrow(version.confidence_score, prior_version.confidence_score if prior_version else None)} |"
    )
    out.append("")
    out.append(
        "*Formula:* `round(0.30·SourceDiversity + 0.30·ProvenanceCompleteness + "
        "0.25·CrossSourceAgreement + 0.15·RecencyCoverage)`."
    )
    out.append("")
    contradictions_section_num = sec_num + 2  # contradictions is always 2 sections later
    if version.contradictions:
        # Paradox surfacing — first place (the metric table footnote).
        out.append(
            "> ⚠️ **Contradiction paradox** — Cross-source agreement is dragged down by "
            f"{len(version.contradictions)} contradictions. The same paradox is "
            f"surfaced in section {contradictions_section_num} (Contradictions) per the dual-surface rule."
        )
        out.append("")

    # Key Claims
    key_claims_section_num = sec_num + 1
    out.append(heading("Key Claims"))
    out.append("")
    if not version.claims:
        out.append(
            "_No claims extracted. The Synthesis Audit section at the end of "
            "this report explains why._"
        )
    else:
        for c in version.claims:
            out.append(
                f"- **{c.subject}** {c.predicate} **{c.value}** "
                f"(confidence {c.confidence:.2f}) "
                f"[source: `{c.source}` / id `{c.source_id}`]"
            )
    out.append("")

    # Contradictions (paradox surfacing — second place)
    out.append(heading("Contradictions"))
    out.append("")
    if not version.contradictions:
        out.append(
            "No contradictions detected across the sources called. This could mean: "
            "(a) the sources genuinely agree, or (b) source diversity is too low to "
            "surface real disagreement. Pass `--audit` to force the Synthesis Audit "
            "section so you can see exactly which trigger thresholds were missed."
        )
    else:
        out.append("| # | Subject — predicate | Severity | Components | Note |")
        out.append("|---|---|---:|---|---|")
        for n, cd in enumerate(version.contradictions, start=1):
            comp = "; ".join(f"{k}={v}" for k, v in cd.severity_components.items())
            out.append(
                f"| {n} | {cd.subject} — {cd.predicate} | {cd.severity}/10 | {comp} | {cd.note} |"
            )
        out.append("")
        out.append(
            "*Severity formula:* "
            "`round(10·(0.40·AuthoritySpread + 0.30·ValueDisagreement + "
            "0.20·RecencySkew + 0.10·SubjectCentrality))`. "
            f"Constitution rule: this orchestrator never picks a winner — both sides "
            f"stay in section {key_claims_section_num} verbatim."
        )
    out.append("")

    # Versioned History
    out.append(heading("Versioned History"))
    out.append("")
    if version.parent_version_id:
        out.append(
            f"- This synthesis builds on parent `{version.parent_version_id}`. "
            f"Walk the chain via `LivingNarrativeFabric.rewind(version_id)` "
            f"(persistent walk lands in Slot 3 / P111)."
        )
    else:
        out.append("- This is the first version on this topic — no parent to rewind to yet.")
    out.append("")

    # Bridges (mandatory, >= MIN_BRIDGES_PER_SYNTHESIS)
    out.append(heading("Bridges"))
    out.append("")
    out.append(
        "This synthesis is one node in a wider fabric. Pair it with at least "
        f"{MIN_BRIDGES_PER_SYNTHESIS} of these so the narrative actually moves:"
    )
    for b in version.bridges:
        out.append(f"- `{b}`")
    out.append("")

    # Synthesis Audit (auto-appended last, only when triggers fire)
    if version.audit_triggered:
        out.append(heading("Synthesis Audit"))
        out.append("")
        out.append("Triggered by:")
        for r in version.audit_reasons:
            out.append(f"- {r}")
        out.append("")
        out.append("Recommended next moves:")
        out.append(
            "- Add a missing source family (semantic_scholar, data_gov, gnews) "
            "before re-running."
        )
        out.append(
            "- Widen the time range from `7d` to `30d` to lift the recency window."
        )
        out.append(
            "- Re-run with `--audit` once a real connector replaces the stub source "
            "(real connectors land in Slot 4 / P112)."
        )
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        "*Built for xAI, X, Grok and the ecosystem community. ❤️ "
        "Apache-2.0. Local-first. Privacy-first.*"
    )
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Public orchestrator class
# ---------------------------------------------------------------------------


@dataclass
class LivingNarrativeFabric:
    """The Living Narrative Fabric Super Agent's orchestration spine."""

    sources: tuple[SourceClient, ...] = field(default_factory=tuple)
    memory: MemoryStore = field(default_factory=InMemoryMemoryStore)
    provenance: ProvenanceLogger = field(default_factory=NoopProvenanceLogger)
    runtime: Runtime = Runtime.AUTO
    per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT
    source_authority_overrides: dict = field(default_factory=dict)

    def with_dependencies(
        self,
        *,
        sources: Optional[Iterable[SourceClient]] = None,
        memory: Optional[MemoryStore] = None,
        provenance: Optional[ProvenanceLogger] = None,
    ) -> "LivingNarrativeFabric":
        """Return a copy with new slot dependencies wired in.

        Slots 3, 4, 5 each call this with their concrete implementation:

        * Slot 3 (P111) injects ``memory=Mem0QdrantStore(...)``
        * Slot 4 (P112) injects ``sources=[NewsApiClient(...), GnewsClient(...), ...]``
        * Slot 5 (P113) injects ``provenance=LangfuseProvenanceLogger(...)``
        """

        return LivingNarrativeFabric(
            sources=tuple(sources) if sources is not None else self.sources,
            memory=memory if memory is not None else self.memory,
            provenance=provenance if provenance is not None else self.provenance,
            runtime=self.runtime,
            per_source_limit=self.per_source_limit,
            source_authority_overrides=dict(self.source_authority_overrides),
        )

    def synthesize(
        self,
        *,
        topic: str,
        time_range: str = TimeRange.D30.value,
        audit: bool = False,
    ) -> SynthesisVersion:
        """Run the full DAG and return an immutable SynthesisVersion."""

        if not topic or not topic.strip():
            raise ValueError("topic must be a non-empty string")
        time_range_enum = TimeRange(time_range)
        since = datetime.now(timezone.utc) - timedelta(days=time_range_enum.days)

        # Compose the source authority table (defaults + caller overrides).
        source_authority = dict(DEFAULT_SOURCE_AUTHORITY)
        source_authority.update(self.source_authority_overrides)

        sources = self.sources or _default_stub_sources()
        parent = self.memory.latest_version_for(topic)
        parent_id = parent.version_id if parent is not None else None

        runtime_used, state = self._dispatch(
            sources=sources,
            topic=topic,
            time_range=time_range_enum.value,
            since=since,
            source_authority=source_authority,
            audit=audit,
        )
        state["runtime_used"] = runtime_used.value

        # The dispatch path may or may not have done finalize() depending on
        # which runtime ran. We always finalize locally to guarantee the
        # Constitution checks + provenance logs happen exactly once.
        if "synthesis_version" not in state:
            state = _node_finalize(
                state,
                parent_version_id=parent_id,
                logger=self.provenance,
            )

        version: SynthesisVersion = state["synthesis_version"]
        self.memory.remember(version)
        self.provenance.log_event(
            "synthesis.persisted",
            {"version_id": version.version_id, "topic": version.topic},
        )
        return version

    def render(
        self,
        version: SynthesisVersion,
        *,
        compare_to_parent: bool = True,
    ) -> str:
        """Render a SynthesisVersion to the official markdown report."""

        prior: Optional[SynthesisVersion] = None
        if compare_to_parent and version.parent_version_id:
            prior = self.memory.recall(version.parent_version_id)
        return render_synthesis_markdown(version, prior_version=prior)

    def rewind(self, version_id: str) -> Optional[SynthesisVersion]:
        """Return any prior SynthesisVersion. Hooks into Slot 3's persistent store."""

        return self.memory.recall(version_id)

    def history(self, topic: str) -> Sequence[SynthesisVersion]:
        """All known versions for a topic, oldest → newest."""

        return self.memory.history_for(topic)

    # ---- runtime dispatch -------------------------------------------------

    def _dispatch(
        self,
        *,
        sources: Iterable[SourceClient],
        topic: str,
        time_range: str,
        since: datetime,
        source_authority: dict,
        audit: bool,
    ) -> tuple[Runtime, dict]:
        """Pick a runtime and run the DAG. Always falls through to in-process."""

        # We always build the initial state dict locally so that whichever
        # runtime we pick gets the exact same starting shape.
        state: dict = {
            "topic": topic,
            "time_range": time_range,
            "since": since,
            "source_authority": source_authority,
        }

        # 1. Mastra (preferred) — only attempted when AUTO or MASTRA explicitly.
        if self.runtime in (Runtime.AUTO, Runtime.MASTRA):
            url = _mastra_url()
            if url is None:
                if self.runtime == Runtime.MASTRA:
                    raise RuntimeError(
                        "Mastra runtime requested but MASTRA_HTTP_URL is not "
                        "set. Either start the Mastra sidecar and export "
                        "MASTRA_HTTP_URL, or use --runtime auto / --runtime "
                        "langgraph / --runtime inprocess."
                    )
                # AUTO without Mastra configured — fall through to LangGraph.
            else:
                wire_in = self._serialise_state_for_remote(state, sources)
                wire_out = _mastra_dispatch(wire_in)
                if wire_out is not None:
                    merged = self._merge_remote_state(state, wire_out, sources, audit)
                    self.provenance.log_event("runtime.mastra.ok", {"topic": topic})
                    return Runtime.MASTRA, merged
                self.provenance.log_event("runtime.mastra.fallthrough", {"topic": topic})
                if self.runtime == Runtime.MASTRA:
                    raise RuntimeError(
                        "Mastra runtime requested but the sidecar at "
                        f"{url!r} did not respond with a valid state."
                    )

        # 2. LangGraph (Python-native fallback).
        if self.runtime in (Runtime.AUTO, Runtime.LANGGRAPH):
            wire_in = self._serialise_state_for_remote(state, sources)
            wire_out = _langgraph_dispatch(wire_in)
            if wire_out is not None:
                merged = self._merge_remote_state(state, wire_out, sources, audit)
                self.provenance.log_event("runtime.langgraph.ok", {"topic": topic})
                return Runtime.LANGGRAPH, merged
            self.provenance.log_event("runtime.langgraph.fallthrough", {"topic": topic})
            if self.runtime == Runtime.LANGGRAPH:
                raise RuntimeError(
                    "LangGraph runtime requested but the sibling graph.py "
                    "module could not run (likely langgraph is not installed)."
                )

        # 3. In-process safety net — same DAG, pure Python, no extra deps.
        state = _node_ingest(
            state,
            sources=sources,
            per_source_limit=self.per_source_limit,
            logger=self.provenance,
        )
        state = _node_normalise_to_claims(state, logger=self.provenance)
        state = _node_detect_contradictions(state, logger=self.provenance)
        state = _node_score_confidence(state)
        state = _node_audit_triggers(state, force_audit=audit)
        return Runtime.INPROCESS, state

    @staticmethod
    def _serialise_state_for_remote(state: dict, sources: Iterable[SourceClient]) -> dict:
        """Make the state JSON-safe so a remote runtime (Mastra) can consume it."""

        return {
            "topic": state["topic"],
            "time_range": state["time_range"],
            "since": state["since"].isoformat(),
            "source_authority": state["source_authority"],
            "source_names": [s.name for s in sources],
            "per_source_limit": DEFAULT_PER_SOURCE_LIMIT,
        }

    def _merge_remote_state(
        self,
        local_state: dict,
        remote_state: dict,
        sources: Iterable[SourceClient],
        audit: bool,
    ) -> dict:
        """Re-hydrate a remote runtime's response into the local Python state.

        Remote runtimes are expected to return ``raw_items``, ``claims``,
        ``contradictions``, ``confidence_metrics``, ``confidence_score``,
        ``sources_called``. Anything else we recompute locally.
        """

        merged = dict(local_state)
        merged["raw_items"] = [
            SourceItem(
                source=ri["source"],
                item_id=ri["item_id"],
                title=ri["title"],
                body=ri["body"],
                retrieved_at=datetime.fromisoformat(ri["retrieved_at"]),
                published_at=datetime.fromisoformat(ri["published_at"]) if ri.get("published_at") else None,
                url=ri.get("url"),
                extra=ri.get("extra", {}),
            )
            for ri in remote_state.get("raw_items", [])
        ]
        merged["sources_called"] = list(remote_state.get("sources_called", []))
        merged["claims"] = [
            Claim(
                claim_id=cl["claim_id"],
                subject=cl["subject"],
                predicate=cl["predicate"],
                value=cl["value"],
                source=cl["source"],
                source_id=cl["source_id"],
                confidence=float(cl["confidence"]),
                extracted_at=datetime.fromisoformat(cl["extracted_at"]),
                sentiment=cl.get("sentiment"),
            )
            for cl in remote_state.get("claims", [])
        ]
        merged["contradictions"] = [
            Contradiction(
                contradiction_id=cd["contradiction_id"],
                subject=cd["subject"],
                predicate=cd["predicate"],
                claim_ids=tuple(cd["claim_ids"]),
                severity=int(cd["severity"]),
                severity_components=cd["severity_components"],
                note=cd["note"],
            )
            for cd in remote_state.get("contradictions", [])
        ]
        if "confidence_metrics" in remote_state and "confidence_score" in remote_state:
            merged["confidence_metrics"] = remote_state["confidence_metrics"]
            merged["confidence_score"] = int(remote_state["confidence_score"])
        else:
            merged = _node_score_confidence(merged)
        merged = _node_audit_triggers(merged, force_audit=audit)
        return merged


def _default_stub_sources() -> tuple[SourceClient, ...]:
    """The 6 official Living Narrative Fabric sources, all stubbed for Slot 2."""

    return tuple(
        StubSourceClient(name=name)
        for name in ("x_search", "newsapi", "gnews", "semantic_scholar", "data_gov", "crawl4ai")
    )


# ---------------------------------------------------------------------------
# CLI smoke test (Windows 11 + PowerShell)
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator",
        description=(
            "Living Narrative Fabric — Orchestration Core (Slot 2). "
            "Runs the multi-source synthesis DAG and prints the official "
            "markdown report to stdout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples (Windows 11 + PowerShell):

              python orchestrator.py --topic "Grok Agent OS launch" --time-range 7d
              python orchestrator.py --topic "$XAI" --time-range 30d --audit
              python orchestrator.py --topic "X creator monetisation" --runtime langgraph

            Slot integration points (left for later prompts):
              Slot 3 / P111 — Mem0 + Qdrant memory layer
              Slot 4 / P112 — Real source connectors (NewsAPI, GNews, ...)
              Slot 5 / P113 — Langfuse + provenance.log writer
              Slot 6 / P114 — Promptfoo + DeepEval suite
              Slot 7 / P115 — Streamlit dashboard
              Slot 8 / P116 — Demo video script + X launch thread
            """
        ),
    )
    parser.add_argument("--topic", required=True, help="Topic to synthesise (e.g. 'Grok Agent OS launch')")
    parser.add_argument(
        "--time-range",
        choices=tuple(t.value for t in TimeRange),
        default=TimeRange.D30.value,
        help="How far back to look for source items (default: 30d).",
    )
    parser.add_argument(
        "--runtime",
        choices=tuple(r.value for r in Runtime),
        default=Runtime.AUTO.value,
        help="Orchestration runtime (default: auto = Mastra → LangGraph → in-process).",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Force the Synthesis Audit section regardless of trigger thresholds.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the markdown report. If omitted, prints to stdout.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    fabric = LivingNarrativeFabric(runtime=Runtime(args.runtime))
    version = fabric.synthesize(
        topic=args.topic,
        time_range=args.time_range,
        audit=args.audit,
    )
    md = fabric.render(version)

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"[living-narrative-fabric] wrote synthesis to {out_path}")
    else:
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
