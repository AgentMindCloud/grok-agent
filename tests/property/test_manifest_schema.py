# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Property-based tests for the v2.15 manifest schema.

Built for xAI, X, Grok and the ecosystem community.

Three properties under test:

1. Every dict produced by ``valid_manifest_strategy`` validates without
   raising (positive coverage of the six required fields plus the
   kind-conditional rules in cli/grok-agent.py).

2. Every dict produced by ``invalid_manifest_strategy`` raises a
   pydantic ``ValidationError`` (negative coverage of the same rules).

3. Round-trip through ``yaml.safe_dump`` then ``yaml.safe_load`` then
   validation is idempotent — the dump+load+validate output equals the
   model_dump of the first validation. This catches the silent drift
   failure mode where a YAML round-trip mutates a field in a way the
   schema accepts but the runtime doesn't.

All three are capped at ``max_examples=20`` and ``deadline=None`` so the
suite stays under one second on a typical Codespaces runner.
"""
from __future__ import annotations

from typing import Any

import pytest

# Skip cleanly if the deps aren't installed — keeps the suite green on
# minimal installs.
hypothesis = pytest.importorskip("hypothesis")
pytest.importorskip("hypothesis.strategies")
pytest.importorskip("yaml")
pytest.importorskip("pydantic")

import yaml  # noqa: E402  (after importorskip)
from hypothesis import given, settings  # noqa: E402
from pydantic import ValidationError  # noqa: E402


pytestmark = pytest.mark.property


# Hypothesis can't pick up fixtures from arguments to @given, so we read
# the strategies and the model class out of pytest fixtures via small
# wrapper tests that hypothesis composes inside.


@settings(max_examples=20, deadline=None)
def _run_valid(strategy: Any, manifest_cls: Any) -> None:
    @given(manifest=strategy)
    def _inner(manifest: dict) -> None:
        # Should not raise. We assert version + license land in the
        # validated model exactly as generated, which catches the
        # silent-coercion failure mode.
        instance = manifest_cls.model_validate(manifest)
        assert instance.version == manifest["version"]
        assert instance.license == "Apache-2.0"
        assert instance.kind == manifest["kind"]
        assert instance.name == manifest["name"]

    _inner()


def test_valid_manifests_round_trip(
    valid_manifest_strategy: Any,
    grok_agent_manifest_cls: Any,
) -> None:
    """Property 1: every valid generated dict validates cleanly."""
    _run_valid(valid_manifest_strategy, grok_agent_manifest_cls)


@settings(max_examples=20, deadline=None)
def _run_invalid(strategy: Any, manifest_cls: Any) -> None:
    @given(manifest=strategy)
    def _inner(manifest: dict) -> None:
        with pytest.raises(ValidationError):
            manifest_cls.model_validate(manifest)

    _inner()


def test_invalid_manifests_are_rejected(
    invalid_manifest_strategy: Any,
    grok_agent_manifest_cls: Any,
) -> None:
    """Property 2: every mutated dict raises ValidationError."""
    _run_invalid(invalid_manifest_strategy, grok_agent_manifest_cls)


@settings(max_examples=20, deadline=None)
def _run_yaml_round_trip(strategy: Any, manifest_cls: Any) -> None:
    @given(manifest=strategy)
    def _inner(manifest: dict) -> None:
        first = manifest_cls.model_validate(manifest)
        first_dump = first.model_dump(exclude_none=True, mode="python")

        text = yaml.safe_dump(first_dump, sort_keys=True, allow_unicode=True)
        reloaded = yaml.safe_load(text)
        second = manifest_cls.model_validate(reloaded)
        second_dump = second.model_dump(exclude_none=True, mode="python")

        assert first_dump == second_dump, (
            "yaml.safe_dump → safe_load → validate is not idempotent"
        )

    _inner()


def test_yaml_round_trip_is_idempotent(
    valid_manifest_strategy: Any,
    grok_agent_manifest_cls: Any,
) -> None:
    """Property 3: dump + load + validate is idempotent."""
    _run_yaml_round_trip(valid_manifest_strategy, grok_agent_manifest_cls)
