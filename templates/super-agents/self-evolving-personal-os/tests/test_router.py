# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
"""Router unit tests for SEPOS — locks the P178 routing fix.

The bug: ``should_loop_back_to_ingest`` used ``<`` against
``MAX_EVOLUTION_LOOPS``, but ``evolve_workflows`` increments
``loop_count`` BEFORE the router runs. With ``MAX = 1`` and one
error-driven evolution, ``loop_count`` is already ``1`` when the
router checks ``1 < 1`` — which is False — so the router incorrectly
routed to NODE_BRIEF instead of looping back to NODE_INGEST.

These tests pin the fix and the cap behaviour so a future edit can't
silently regress.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add the agent's directory to sys.path so `import graph` works whether
# pytest is invoked from the repo root or this folder. Mirrors the same
# trick the agent's smoke_test.py uses.
_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

import graph as _graph  # type: ignore  # noqa: E402


def _state(*, loop_count: int, should_loop: bool) -> dict:
    return {
        "loop_count": loop_count,
        "evolution": {"should_loop": should_loop},
    }


def test_router_returns_ingest_after_first_evolve_with_error() -> None:
    """After evolve_workflows increments loop_count to 1 (cap=1) and sets
    should_loop=True, the router must allow exactly one loop back."""
    routed = _graph.should_loop_back_to_ingest(
        _state(loop_count=1, should_loop=True)
    )
    assert routed == _graph.NODE_INGEST


def test_router_refuses_when_loop_count_exceeds_cap() -> None:
    """When loop_count is already past MAX_EVOLUTION_LOOPS, refuse to
    loop again even if should_loop is True."""
    routed = _graph.should_loop_back_to_ingest(
        _state(
            loop_count=_graph.MAX_EVOLUTION_LOOPS + 1,
            should_loop=True,
        )
    )
    assert routed == _graph.NODE_BRIEF


def test_router_refuses_when_should_loop_is_false() -> None:
    """When evolve_workflows decided no loop is needed, the router
    must advance to NODE_BRIEF regardless of loop_count."""
    routed = _graph.should_loop_back_to_ingest(
        _state(loop_count=0, should_loop=False)
    )
    assert routed == _graph.NODE_BRIEF


def test_router_handles_missing_state_keys() -> None:
    """A degenerate state with no evolution block should be treated as
    'no loop' (fail-safe path), not raise."""
    assert _graph.should_loop_back_to_ingest({}) == _graph.NODE_BRIEF
    assert _graph.should_loop_back_to_ingest(
        {"evolution": None}
    ) == _graph.NODE_BRIEF
