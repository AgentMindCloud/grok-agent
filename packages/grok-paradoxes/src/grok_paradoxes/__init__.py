# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""grok-paradoxes — contradiction detection and multi-authority reconciliation.

Built for xAI, X, Grok and the ecosystem community. ❤️

This package extracts the contradiction-detection and authority-weighted
reconciliation primitives that originated inside the Living Narrative Fabric
Super Agent (see ``templates/super-agents/living-narrative-fabric/`` in the
AgentMindCloud/grok-agent monorepo). The goal is to make those primitives
citable, testable, and reusable outside the Super Agent.

Public API (stable for v0.1):

* :class:`Source` — a named information source with an authority weight.
* :class:`Claim` — a normalised assertion (subject, predicate, value) tied
  to a source and a confidence.
* :class:`Contradiction` — two or more claims on the same subject and
  predicate that disagree.
* :class:`ReconciliationSuggestion` — an authority-weighted suggestion of
  which claim to prefer, kept as advisory information only.
* :class:`ContradictionDetector` — pairs claims that share subject and
  predicate but assert different values; never silently picks a winner.
* :func:`weight_authorities` — convenience function that ranks claims by
  ``authority * confidence`` and returns a single
  :class:`ReconciliationSuggestion`.

Constitution rule reproduced verbatim from the parent repository:
contradictions are surfaced, never silently resolved. Reconciliation is
a *suggestion*, and callers are expected to keep both sides visible.
"""

from __future__ import annotations

from ._version import __version__
from .authority import weight_authorities
from .contradiction import ContradictionDetector
from .types import Claim, Contradiction, ReconciliationSuggestion, Source

__all__ = [
    "__version__",
    "Claim",
    "Contradiction",
    "ContradictionDetector",
    "ReconciliationSuggestion",
    "Source",
    "weight_authorities",
]
