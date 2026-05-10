# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Core Pydantic v2 types for grok-paradoxes.

Built for xAI, X, Grok and the ecosystem community. ❤️

These types are intentionally minimal and self-contained: no I/O, no
network, no implicit defaults beyond what is required for ergonomic use.
Every model uses ``model_config = ConfigDict(extra="forbid")`` so that
typos in caller code surface as validation errors rather than silently
ignored fields. Severity is restricted to a literal set so downstream
filters can rely on a closed enumeration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Severity",
    "Source",
    "Claim",
    "Contradiction",
    "ReconciliationSuggestion",
]

#: Severity literal — closed set so downstream code can match exhaustively.
Severity = Literal["minor", "moderate", "major"]


class Source(BaseModel):
    """A named information source with an authority weight in ``[0.0, 1.0]``.

    ``authority`` is a tunable trust weight assigned by the caller; higher
    values mean the source is treated as more trustworthy when reconciling
    contradictions. ``scope`` is a free-form label (for example a domain
    name or a topic area) that downstream renderers may surface in audit
    output.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, description="Human-readable source identifier.")
    authority: float = Field(
        ge=0.0,
        le=1.0,
        description="Authority weight in [0.0, 1.0]; higher means more trustworthy.",
    )
    scope: Optional[str] = Field(
        default=None,
        description="Optional scope label (for example a domain or topic area).",
    )


class Claim(BaseModel):
    """A normalised assertion derived from a single source.

    A claim is the smallest unit the contradiction detector can work with.
    ``subject`` and ``predicate`` together act as the grouping key — two
    claims are candidates for contradiction if they share the same subject
    and predicate but assert different ``value`` strings.

    ``confidence`` is the parser or extractor's self-reported confidence in
    the value, in ``[0.0, 1.0]``. ``source`` is the :class:`Source` the
    claim originated from; the source's ``authority`` is what the
    reconciler weights with. ``timestamp`` is optional — when provided it
    is used by callers that want to apply recency tie-breaking.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, description="What the claim is about.")
    predicate: str = Field(min_length=1, description="Relationship between subject and value.")
    value: str = Field(min_length=1, description="The asserted value, verbatim from the source.")
    source: Source = Field(description="The source that produced the claim.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Parser confidence in the value, in [0.0, 1.0].",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional moment the claim was extracted or observed.",
    )


class Contradiction(BaseModel):
    """A pair of claims on the same subject and predicate that disagree.

    Per the Living Narrative Fabric Constitution, a :class:`Contradiction`
    is a record of disagreement, not a resolution: both ``claim_a`` and
    ``claim_b`` are kept verbatim and the caller is expected to surface
    both. ``severity`` is bucketed into a closed literal set so downstream
    filters can match exhaustively. ``rationale`` is a short renderable
    explanation suitable for audit logs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_a: Claim = Field(description="First conflicting claim.")
    claim_b: Claim = Field(description="Second conflicting claim.")
    severity: Severity = Field(description="Bucketed severity: minor, moderate, or major.")
    rationale: str = Field(
        min_length=1,
        description="Short human-readable explanation of why this disagreement was flagged.",
    )


class ReconciliationSuggestion(BaseModel):
    """An advisory ranking of which claim to prefer when forced to pick one.

    A reconciliation suggestion is *not* a verdict. The Constitution rule
    is that contradictions are surfaced, never silently resolved; this
    object exists so callers that need a single value (for example a UI
    cell or a downstream aggregator) have a defensible default. Callers
    that respect the Constitution must continue to surface the losing
    claims alongside the suggestion.

    ``confidence_delta`` is the gap between the preferred claim's
    ``authority * confidence`` score and the next-best claim's score, in
    ``[0.0, 1.0]``. A small delta indicates the preference is weak.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    preferred_claim: Claim = Field(description="The claim ranked highest by authority * confidence.")
    rationale: str = Field(
        min_length=1,
        description="Short human-readable explanation of the ranking.",
    )
    confidence_delta: float = Field(
        ge=0.0,
        le=1.0,
        description="Gap between the preferred claim score and the next-best claim score.",
    )
