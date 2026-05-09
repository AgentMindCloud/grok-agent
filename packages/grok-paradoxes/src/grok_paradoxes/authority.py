# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Multi-authority reconciliation for grok-paradoxes.

Built for xAI, X, Grok and the ecosystem community. ❤️

This module provides :func:`weight_authorities`, a pure-Python helper that
ranks a collection of :class:`Claim` objects by their composite
``authority * confidence`` score and returns a single
:class:`ReconciliationSuggestion`.

The function is deliberately advisory. Per the Living Narrative Fabric
Constitution, contradictions are surfaced and never silently resolved; a
reconciliation suggestion is one defensible default that callers can
attach to a UI cell or downstream aggregator while still surfacing the
losing claims alongside it.

Algorithm
---------
1. Group the input claims by ``(subject, predicate)``.
2. If the input contains exactly one such group, use it directly. If it
   contains more than one, the largest group (most claims) is selected;
   ties are broken by the group whose top-scoring claim has the highest
   composite score so the suggestion is deterministic.
3. Within the selected group, score every claim as
   ``source.authority * confidence`` and keep the highest-scoring claim.
4. Compute ``confidence_delta`` as the gap between the top score and the
   next-best score in the same group, clamped to ``[0.0, 1.0]``. When the
   group contains only one claim the gap is ``1.0`` (no rival to compare).
5. Compose a short audit-friendly rationale that names the preferred
   source, the score, and the delta so downstream readers can audit the
   decision.

The function performs no I/O, makes no network calls, and is safe to call
from any thread; it produces the same output for the same input every
time.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .types import Claim, ReconciliationSuggestion

__all__ = ["weight_authorities"]


def _composite_score(claim: Claim) -> float:
    """Return ``authority * confidence`` for a single claim.

    Both factors live in ``[0.0, 1.0]`` so the product is also in
    ``[0.0, 1.0]``. Kept as a private helper so the scoring rule has one
    canonical definition shared by the ranker and the delta calculator.
    """

    return float(claim.source.authority) * float(claim.confidence)


def _select_group(grouped: dict[tuple[str, str], list[Claim]]) -> list[Claim]:
    """Pick the group the suggestion will be drawn from.

    Selection rule (deterministic):

    * Largest group wins on group size.
    * Ties on group size are broken by the highest top score in the group.
    * Further ties fall back to the natural insertion order of the keys.
    """

    if not grouped:
        return []
    best_key: tuple[str, str] | None = None
    best_size = -1
    best_top_score = -1.0
    for key, group in grouped.items():
        size = len(group)
        top_score = max(_composite_score(c) for c in group)
        if (
            size > best_size
            or (size == best_size and top_score > best_top_score)
        ):
            best_key = key
            best_size = size
            best_top_score = top_score
    assert best_key is not None  # grouped was non-empty
    return grouped[best_key]


def weight_authorities(claims: Iterable[Claim]) -> ReconciliationSuggestion:
    """Rank ``claims`` and return a single :class:`ReconciliationSuggestion`.

    Parameters
    ----------
    claims:
        An iterable of :class:`Claim` objects. Must contain at least one
        claim; an empty iterable raises :class:`ValueError` because there
        is nothing to rank.

    Returns
    -------
    ReconciliationSuggestion
        The preferred claim plus a rationale and a ``confidence_delta``
        in ``[0.0, 1.0]``. The suggestion is advisory only; callers must
        continue to surface the losing claims alongside it to honour the
        Constitution rule against silent resolution.

    Raises
    ------
    ValueError
        If ``claims`` is empty.
    """

    materialised = list(claims)
    if not materialised:
        raise ValueError("weight_authorities requires at least one claim")

    grouped: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for claim in materialised:
        grouped[(claim.subject, claim.predicate)].append(claim)

    group = _select_group(dict(grouped))

    # Stable sort by composite score descending. Python's sort is stable, so
    # ties resolve by the input order of the selected group.
    ranked = sorted(group, key=_composite_score, reverse=True)
    preferred = ranked[0]
    top_score = _composite_score(preferred)

    if len(ranked) >= 2:
        runner_up_score = _composite_score(ranked[1])
        raw_delta = top_score - runner_up_score
    else:
        # Single-claim case: no competitor exists, so by contract the gap is
        # zero (not the maximum 1.0). The 1.0 reading would be misleading
        # since "no runner-up" is not the same signal as "huge runner-up gap".
        # Locked by tests/test_authority.py::test_single_source_returns_self_with_zero_delta.
        raw_delta = 0.0

    confidence_delta = max(0.0, min(1.0, raw_delta))

    rationale = (
        f"Preferred '{preferred.source.name}' for subject "
        f"'{preferred.subject}' / predicate '{preferred.predicate}': "
        f"composite score {top_score:.3f} "
        f"(authority {preferred.source.authority:.2f} * "
        f"confidence {preferred.confidence:.2f}); "
        f"gap to next-best {confidence_delta:.3f}. "
        "Advisory only — surface losing claims alongside this suggestion."
    )

    return ReconciliationSuggestion(
        preferred_claim=preferred,
        rationale=rationale,
        confidence_delta=confidence_delta,
    )
