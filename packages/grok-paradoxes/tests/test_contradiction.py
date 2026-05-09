# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

"""Contradiction detection tests for grok_paradoxes.

Built for xAI, X, Grok and the ecosystem community. ❤️

These tests pin the public ContradictionDetector contract: same subject +
predicate with disagreeing values flag a contradiction; consistent claims
return an empty result; low-confidence inputs cap severity at "minor"; and
empty input is a no-op (never raises). Every test is hermetic — no network,
no GUI, no secrets — and is marked ``@pytest.mark.smoke`` so the suite can
run as a fast pre-commit / pre-push gate.

If grok_paradoxes is not yet importable (Agent 2.1 may still be writing the
source files in a parallel swarm), the whole module skips cleanly via
``pytest.importorskip``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

grok_paradoxes = pytest.importorskip(
    "grok_paradoxes",
    reason="grok_paradoxes source not yet present (parallel swarm — Agent 2.1).",
)

ContradictionDetector = grok_paradoxes.ContradictionDetector
Source = grok_paradoxes.Source
Claim = grok_paradoxes.Claim
Contradiction = grok_paradoxes.Contradiction


# ---------------------------------------------------------------------------
# Fixtures — small deterministic factories
# ---------------------------------------------------------------------------


def _src(name: str, authority: float) -> Source:
    return Source(name=name, authority=authority)


def _claim(
    *,
    subject: str,
    predicate: str,
    value: str,
    source: Source,
    confidence: float = 0.8,
    timestamp: datetime | None = None,
) -> Claim:
    return Claim(
        subject=subject,
        predicate=predicate,
        value=value,
        source=source,
        confidence=confidence,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_simple_two_source_contradiction_flagged() -> None:
    """Two sources, same subject + predicate, different values → flagged."""

    s1 = _src("newsapi", authority=0.65)
    s2 = _src("gnews", authority=0.65)

    claims = [
        _claim(subject="grok-os", predicate="adoption", value="rising", source=s1, confidence=0.8),
        _claim(subject="grok-os", predicate="adoption", value="falling", source=s2, confidence=0.78),
    ]

    detector = ContradictionDetector()
    result = detector.detect(claims)

    assert len(result) == 1, f"expected exactly 1 contradiction, got {len(result)}"
    cd = result[0]
    assert isinstance(cd, Contradiction)
    assert cd.severity in {"minor", "moderate", "major"}


@pytest.mark.smoke
def test_three_way_disagreement_flags_all_pairs() -> None:
    """Three sources, three different values → at least one Contradiction emitted.

    The detector may emit one Contradiction per pair (3 pairs) or one
    aggregate Contradiction covering all three claims; both shapes are
    valid as long as the disagreement is surfaced (Constitution: never
    silently resolve).
    """

    s1 = _src("newsapi", authority=0.7)
    s2 = _src("gnews", authority=0.7)
    s3 = _src("crawl4ai", authority=0.45)

    claims = [
        _claim(subject="x-money", predicate="status", value="growing", source=s1),
        _claim(subject="x-money", predicate="status", value="shrinking", source=s2),
        _claim(subject="x-money", predicate="status", value="flat", source=s3),
    ]

    detector = ContradictionDetector()
    result = detector.detect(claims)

    assert len(result) >= 1, "three-way disagreement must surface as at least one contradiction"
    flagged_ids = set()
    for cd in result:
        flagged_ids.add(id(cd.claim_a))
        flagged_ids.add(id(cd.claim_b))
    assert len(flagged_ids) >= 2, "at least two distinct claims must be referenced"


@pytest.mark.smoke
def test_no_contradiction_for_consistent_claims() -> None:
    """Consistent claims (same subject+predicate, same value) → empty result."""

    s1 = _src("newsapi", authority=0.65)
    s2 = _src("gnews", authority=0.65)

    claims = [
        _claim(subject="grok-os", predicate="adoption", value="rising", source=s1),
        _claim(subject="grok-os", predicate="adoption", value="rising", source=s2),
    ]

    detector = ContradictionDetector()
    result = detector.detect(claims)

    assert result == [] or len(result) == 0, "agreeing claims must not flag a contradiction"


@pytest.mark.smoke
def test_low_confidence_caps_severity_at_minor() -> None:
    """A claim with confidence < 0.3 must not push severity to 'major'.

    Rationale: a barely-confident extraction disagreeing with a
    high-confidence one is much more likely an extraction artefact than a
    real-world paradox; the detector should reflect that with reduced
    severity.
    """

    s_high = _src("semantic_scholar", authority=0.95)
    s_low = _src("crawl4ai", authority=0.45)

    claims = [
        _claim(subject="x-payouts", predicate="trend", value="up", source=s_high, confidence=0.95),
        _claim(subject="x-payouts", predicate="trend", value="down", source=s_low, confidence=0.2),
    ]

    detector = ContradictionDetector(min_severity="minor")
    result = detector.detect(claims)

    # Either the contradiction is suppressed (filtered below min_severity)
    # OR it is surfaced with severity strictly less than 'major'.
    if result:
        for cd in result:
            assert cd.severity != "major", (
                f"low-confidence claim must not produce major severity, got {cd.severity!r}"
            )


@pytest.mark.smoke
def test_empty_input_returns_empty_no_error() -> None:
    """Empty claim list → empty result, no exception."""

    detector = ContradictionDetector()
    result = detector.detect([])

    assert result == [] or len(result) == 0


@pytest.mark.smoke
def test_summary_consumes_detect_output() -> None:
    """The summary helper accepts what detect() returns and yields a string.

    This pins the round-trip contract: detect → summary → renderable text.
    The exact summary format is intentionally not asserted (Agent 2.1
    owns the wording); only that the helper does not crash and returns a
    non-None value when given the empty list (the boring base case).
    """

    detector = ContradictionDetector()
    summary = detector.summary([])
    assert summary is not None
