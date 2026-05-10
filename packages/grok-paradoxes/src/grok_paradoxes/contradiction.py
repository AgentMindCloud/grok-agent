# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Contradiction detection across multi-source claim sets.

Built for xAI, X, Grok and the ecosystem community. ❤️

The :class:`ContradictionDetector` groups claims by ``(subject, predicate)``
and flags every pair that asserts a different ``value``. Severity is
derived from two normalised components — the spread in source authority
and the spread in claim confidence — and bucketed into a closed literal
set (``minor`` / ``moderate`` / ``major``).

The detector is deliberately pure: it performs no I/O, makes no network
calls, and never silently picks a winner. Both sides of every disagreement
are returned so the caller can surface them verbatim.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

from .types import Claim, Contradiction, Severity

__all__ = ["ContradictionDetector"]

#: Allowed severity tokens, ranked from least to most severe. A constant so
#: ``min_severity`` filtering and severity bucketing share one source of truth.
_SEVERITY_ORDER: tuple[Severity, ...] = ("minor", "moderate", "major")

#: Bucketing thresholds for the combined severity score in ``[0.0, 1.0]``.
#: A score at or above ``major`` is ``"major"``; at or above ``moderate`` is
#: ``"moderate"``; otherwise ``"minor"``. The numbers mirror the four-component
#: weighting used inside the Living Narrative Fabric orchestrator while staying
#: simple enough to reason about in tests.
_SEVERITY_THRESHOLDS: dict[Severity, float] = {
    "major": 0.66,
    "moderate": 0.33,
    "minor": 0.0,
}

#: Weights applied to the two normalised severity components. They sum to 1.0
#: so the combined score stays inside ``[0.0, 1.0]``.
_AUTHORITY_WEIGHT = 0.6
_CONFIDENCE_WEIGHT = 0.4


def _bucket_severity(score: float) -> Severity:
    """Map a combined severity score in ``[0.0, 1.0]`` to a literal bucket."""

    clamped = max(0.0, min(1.0, score))
    if clamped >= _SEVERITY_THRESHOLDS["major"]:
        return "major"
    if clamped >= _SEVERITY_THRESHOLDS["moderate"]:
        return "moderate"
    return "minor"


def _severity_at_least(candidate: Severity, floor: Severity) -> bool:
    """Return True when ``candidate`` is at least as severe as ``floor``."""

    return _SEVERITY_ORDER.index(candidate) >= _SEVERITY_ORDER.index(floor)


def _format_rationale(
    claim_a: Claim,
    claim_b: Claim,
    *,
    authority_spread: float,
    confidence_spread: float,
    severity: Severity,
) -> str:
    """Compose a short audit-friendly rationale for a single contradiction."""

    return (
        f"{severity} disagreement on '{claim_a.subject}' / '{claim_a.predicate}': "
        f"{claim_a.source.name} says '{claim_a.value}' "
        f"(authority {claim_a.source.authority:.2f}, confidence {claim_a.confidence:.2f}); "
        f"{claim_b.source.name} says '{claim_b.value}' "
        f"(authority {claim_b.source.authority:.2f}, confidence {claim_b.confidence:.2f}); "
        f"authority spread {authority_spread:.2f}, confidence spread {confidence_spread:.2f}. "
        "Both sides are surfaced verbatim — the detector never picks a winner."
    )


class ContradictionDetector:
    """Pair claims that share a subject and predicate but assert different values.

    Parameters
    ----------
    min_severity:
        Floor for emitted contradictions. Pairs whose computed severity falls
        below this floor are dropped from the returned list. Defaults to
        ``"minor"`` so every disagreement is surfaced.

    The detector is stateless across calls; instances are cheap and safe to
    reuse. Construction validates ``min_severity`` against the closed literal
    set so a typo fails fast rather than silently filtering everything out.
    """

    def __init__(self, min_severity: Severity = "minor") -> None:
        if min_severity not in _SEVERITY_ORDER:
            raise ValueError(
                f"min_severity must be one of {_SEVERITY_ORDER!r}, got {min_severity!r}"
            )
        self._min_severity: Severity = min_severity

    @property
    def min_severity(self) -> Severity:
        """Return the configured severity floor."""

        return self._min_severity

    def detect(self, claims: Iterable[Claim]) -> list[Contradiction]:
        """Return every flagged contradiction across ``claims``.

        Claims are grouped by ``(subject, predicate)``. Within each group,
        every unordered pair that asserts a different ``value`` is scored
        and bucketed; pairs at or above ``min_severity`` are returned. The
        order of the returned list is deterministic for a given input
        ordering: groups are processed in insertion order and pairs within
        a group are emitted in the natural order produced by
        :func:`itertools.combinations`.
        """

        grouped: dict[tuple[str, str], list[Claim]] = defaultdict(list)
        for claim in claims:
            grouped[(claim.subject, claim.predicate)].append(claim)

        contradictions: list[Contradiction] = []
        for group in grouped.values():
            if len(group) < 2:
                continue
            for claim_a, claim_b in combinations(group, 2):
                if claim_a.value == claim_b.value:
                    continue
                authority_spread = abs(claim_a.source.authority - claim_b.source.authority)
                confidence_spread = abs(claim_a.confidence - claim_b.confidence)
                score = (
                    _AUTHORITY_WEIGHT * authority_spread
                    + _CONFIDENCE_WEIGHT * confidence_spread
                )
                severity = _bucket_severity(score)
                if not _severity_at_least(severity, self._min_severity):
                    continue
                rationale = _format_rationale(
                    claim_a,
                    claim_b,
                    authority_spread=authority_spread,
                    confidence_spread=confidence_spread,
                    severity=severity,
                )
                contradictions.append(
                    Contradiction(
                        claim_a=claim_a,
                        claim_b=claim_b,
                        severity=severity,
                        rationale=rationale,
                    )
                )
        return contradictions

    def summary(self, contradictions: Iterable[Contradiction]) -> dict[str, int]:
        """Return counts bucketed by severity, including a ``total`` entry.

        The returned dict always contains keys for every severity level in
        :data:`_SEVERITY_ORDER` plus ``"total"`` so callers can render a
        complete table without conditional key access.
        """

        counts: dict[str, int] = {level: 0 for level in _SEVERITY_ORDER}
        total = 0
        for c in contradictions:
            counts[c.severity] += 1
            total += 1
        counts["total"] = total
        return counts
