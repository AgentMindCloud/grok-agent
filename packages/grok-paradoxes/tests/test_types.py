# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic type tests for grok_paradoxes.

Built for xAI, X, Grok and the ecosystem community. ❤️

Pins the validation rules on the public Pydantic models:

* ``Source.authority`` is constrained to the closed interval [0, 1].
* ``Claim.timestamp`` is optional (None is acceptable).
* ``Contradiction.severity`` is a Literal["minor", "moderate", "major"].

These tests catch schema regressions early — if Agent 2.1 (or a future
contributor) loosens a constraint by accident, the suite goes red on the
next push.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

grok_paradoxes = pytest.importorskip(
    "grok_paradoxes",
    reason="grok_paradoxes source not yet present (parallel swarm — Agent 2.1).",
)

Source = grok_paradoxes.Source
Claim = grok_paradoxes.Claim
Contradiction = grok_paradoxes.Contradiction

# Pydantic v2 raises ``ValidationError`` from ``pydantic`` for bad inputs.
pydantic = pytest.importorskip("pydantic")
ValidationError = pydantic.ValidationError


def _good_source() -> Source:
    return Source(name="newsapi", authority=0.65)


def _good_claim(**overrides) -> Claim:
    base = dict(
        subject="grok-os",
        predicate="adoption",
        value="rising",
        source=_good_source(),
        confidence=0.8,
    )
    base.update(overrides)
    return Claim(**base)


@pytest.mark.smoke
def test_source_rejects_authority_above_one() -> None:
    """Authority > 1.0 must raise ValidationError."""

    with pytest.raises(ValidationError):
        Source(name="bad-src", authority=1.5)


@pytest.mark.smoke
def test_source_rejects_authority_below_zero() -> None:
    """Authority < 0 must raise ValidationError."""

    with pytest.raises(ValidationError):
        Source(name="bad-src", authority=-0.1)


@pytest.mark.smoke
def test_claim_accepts_optional_timestamp() -> None:
    """Claim.timestamp is optional — None and datetime are both accepted."""

    no_ts = _good_claim(timestamp=None)
    assert no_ts.timestamp is None

    ts_value = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)
    with_ts = _good_claim(timestamp=ts_value)
    assert with_ts.timestamp == ts_value


@pytest.mark.smoke
def test_contradiction_severity_must_be_literal_set() -> None:
    """severity outside {minor, moderate, major} must raise ValidationError."""

    claim_a = _good_claim(value="rising")
    claim_b = _good_claim(value="falling")

    # Valid values build cleanly.
    for sev in ("minor", "moderate", "major"):
        ok = Contradiction(
            claim_a=claim_a,
            claim_b=claim_b,
            severity=sev,
            rationale="two sources disagree on direction",
        )
        assert ok.severity == sev

    # Anything else is rejected.
    with pytest.raises(ValidationError):
        Contradiction(
            claim_a=claim_a,
            claim_b=claim_b,
            severity="catastrophic",
            rationale="invalid severity literal",
        )
