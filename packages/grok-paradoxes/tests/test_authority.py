# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

"""Authority weighting tests for grok_paradoxes.

Built for xAI, X, Grok and the ecosystem community. ❤️

Pins the contract for ``weight_authorities(claims) -> ReconciliationSuggestion``:

* Equal authorities fall back to confidence as the tie-breaker.
* A dominant authority wins regardless of confidence.
* Fractional authorities pick from the higher-authority pair.
* A single claim is returned verbatim with ``confidence_delta == 0``.

The function NEVER silently resolves a real-world contradiction; it merely
suggests a preferred claim with a transparent rationale so the caller can
decide whether to act. Every test is hermetic and marked ``@pytest.mark.smoke``.
"""

from __future__ import annotations

import pytest

grok_paradoxes = pytest.importorskip(
    "grok_paradoxes",
    reason="grok_paradoxes source not yet present (parallel swarm — Agent 2.1).",
)

weight_authorities = grok_paradoxes.weight_authorities
Source = grok_paradoxes.Source
Claim = grok_paradoxes.Claim
ReconciliationSuggestion = grok_paradoxes.ReconciliationSuggestion


def _src(name: str, authority: float) -> Source:
    return Source(name=name, authority=authority)


def _claim(value: str, source: Source, confidence: float) -> Claim:
    return Claim(
        subject="x-revenue",
        predicate="trend",
        value=value,
        source=source,
        confidence=confidence,
    )


@pytest.mark.smoke
def test_equal_authorities_picks_by_confidence() -> None:
    """When two sources share authority, the higher-confidence claim wins."""

    s1 = _src("newsapi", authority=0.7)
    s2 = _src("gnews", authority=0.7)

    higher = _claim("rising", s1, confidence=0.9)
    lower = _claim("falling", s2, confidence=0.4)

    suggestion = weight_authorities([lower, higher])

    assert isinstance(suggestion, ReconciliationSuggestion)
    assert suggestion.preferred_claim.value == "rising", (
        "equal authority → higher-confidence claim must be preferred"
    )


@pytest.mark.smoke
def test_dominant_authority_wins_regardless_of_confidence() -> None:
    """A 0.9-authority source beats a 0.3-authority source even at lower confidence."""

    s_strong = _src("semantic_scholar", authority=0.9)
    s_weak = _src("crawl4ai", authority=0.3)

    strong_claim = _claim("rising", s_strong, confidence=0.5)
    weak_claim = _claim("falling", s_weak, confidence=0.99)

    suggestion = weight_authorities([weak_claim, strong_claim])

    assert suggestion.preferred_claim.value == "rising", (
        "dominant authority must win even when the other claim has higher confidence"
    )
    assert suggestion.preferred_claim.source.name == "semantic_scholar"


@pytest.mark.smoke
def test_fractional_authorities_picks_from_higher_pair() -> None:
    """0.5 + 0.5 + 0.0 → preferred claim must come from one of the 0.5 sources."""

    s_mid_1 = _src("newsapi", authority=0.5)
    s_mid_2 = _src("gnews", authority=0.5)
    s_zero = _src("crawl4ai", authority=0.0)

    c1 = _claim("rising", s_mid_1, confidence=0.6)
    c2 = _claim("rising", s_mid_2, confidence=0.7)
    c3 = _claim("falling", s_zero, confidence=0.95)

    suggestion = weight_authorities([c1, c2, c3])

    assert suggestion.preferred_claim.source.authority >= 0.5, (
        "preferred claim must come from a non-zero authority source"
    )


@pytest.mark.smoke
def test_single_source_returns_self_with_zero_delta() -> None:
    """One claim in → that same claim out, with ``confidence_delta == 0``."""

    s = _src("newsapi", authority=0.65)
    only = _claim("rising", s, confidence=0.8)

    suggestion = weight_authorities([only])

    assert suggestion.preferred_claim.value == "rising"
    assert suggestion.confidence_delta == 0, (
        f"single-claim suggestion must report zero delta, got {suggestion.confidence_delta!r}"
    )


@pytest.mark.smoke
def test_rationale_is_human_readable_string() -> None:
    """The rationale field must be a non-empty string callers can display."""

    s1 = _src("newsapi", authority=0.7)
    s2 = _src("gnews", authority=0.7)

    suggestion = weight_authorities([
        _claim("rising", s1, confidence=0.9),
        _claim("falling", s2, confidence=0.4),
    ])

    assert isinstance(suggestion.rationale, str)
    assert suggestion.rationale.strip(), "rationale must not be blank"
