# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Snapshot tests for the three flagship Super Agent stub-mode outputs.

Built for xAI, X, Grok and the ecosystem community.

What's snapshotted
------------------
For each of the three flagship Super Agents we drive the canonical
stub-mode entry point, scrub volatile fields with the
``deterministic_serializer`` from ``conftest.py``, and compare against
the on-disk syrupy snapshot:

1. ``cross-reality-action-fabric.daily_plan(force_stub=True,
   auto_approve=True)`` — the action-graph stub.
2. ``living-narrative-fabric.LivingNarrativeFabric().synthesize(
   topic="snapshot-fixture", time_range="d7")`` — the synthesis stub.
3. ``self-evolving-personal-os.daily_brief(force_stub=True,
   allow_write=True, sources=[])`` — the daily-brief stub.

If a Super Agent's stub-mode contract drifts (a new field appears, a
field's shape changes, a prompt-version string regresses) the snapshot
diff catches it the next time CI runs.

Hermeticity
-----------
- Every test installs ``LOCALAPPDATA`` + ``HOME`` to the per-test
  ``tmp_path`` so any best-effort filesystem writes land inside the
  pytest temp dir and never touch the user's machine.
- ``force_stub=True`` is passed everywhere — no LLM calls, no network.
- ``syrupy`` is loaded via ``pytest.importorskip`` so the file skips
  cleanly on minimal installs.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


syrupy = pytest.importorskip("syrupy")
pytest.importorskip("yaml")
pytest.importorskip("pydantic")


pytestmark = pytest.mark.snapshot


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPER_AGENTS_DIR = _REPO_ROOT / "templates" / "super-agents"


def _redirect_appdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every appdata + home lookup at ``tmp_path`` for hermeticity."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


# Sibling-module names that the three Super Agent packages all expose
# under bare names (``import graph``, ``import connectors``, ``import
# orchestrator``, ...). Each Super Agent ships its own copy, so we must
# evict any stale entry from a previous test before loading the next one
# — otherwise SEPOS's ``import graph`` resolves to cross-reality's graph
# module from a prior test and ``run_daily_brief`` is missing.
_SIBLING_MODULES_TO_EVICT: tuple[str, ...] = (
    "graph",
    "agent",
    "orchestrator",
    "connectors",
    "memory",
    "provenance",
    "dashboard",
    "constants",
    "router",
)


def _load_module_from_path(module_name: str, file_path: Path) -> Any:
    """Load a Python module by absolute path, registering it in ``sys.modules``.

    Both Super Agent folders use hyphens in their names (not valid Python
    identifiers) so we can't ``import templates.super-agents.x.agent``.
    The same trick that ``scripts/export-openapi.py`` uses for the CLI
    module is reused here.

    To stay hermetic across tests, we evict any sibling modules a prior
    Super Agent left in ``sys.modules`` AND we put the new agent's
    folder at the *front* of ``sys.path`` so its sibling imports win.
    """
    if not file_path.exists():
        pytest.skip(f"Super Agent module missing at {file_path}")

    parent = str(file_path.parent)
    # Remove any stale path entries pointing at other Super Agent folders.
    sys.path[:] = [p for p in sys.path if "templates/super-agents" not in p]
    sys.path.insert(0, parent)

    # Evict stale sibling modules so the new agent's ``import graph`` etc
    # picks up the right file.
    for stale in _SIBLING_MODULES_TO_EVICT:
        sys.modules.pop(stale, None)
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        pytest.skip(f"Could not load module at {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Test 1 — cross-reality-action-fabric
# --------------------------------------------------------------------------

def test_cross_reality_daily_plan_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deterministic_serializer,
    snapshot,
) -> None:
    """Snapshot the cross-reality stub-mode daily_plan output."""
    _redirect_appdata(monkeypatch, tmp_path)

    agent_path = _SUPER_AGENTS_DIR / "cross-reality-action-fabric" / "agent.py"
    agent = _load_module_from_path(
        "snapshot_cross_reality_agent_for_tests", agent_path
    )

    out = agent.daily_plan(
        user_id="snapshot-fixture",
        force_stub=True,
        auto_approve=True,
        quiet=True,
    )

    scrubbed = deterministic_serializer(out)
    # Drop the top-level ``agent_version`` key because version bumps are
    # intentional — surfacing them as snapshot diffs would be noise.
    if isinstance(scrubbed, dict):
        scrubbed.pop("agent_version", None)
    assert scrubbed == snapshot


# --------------------------------------------------------------------------
# Test 2 — living-narrative-fabric
# --------------------------------------------------------------------------

def test_living_narrative_synthesize_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deterministic_serializer,
    snapshot,
) -> None:
    """Snapshot the living-narrative-fabric stub synthesis output."""
    _redirect_appdata(monkeypatch, tmp_path)

    orch_path = (
        _SUPER_AGENTS_DIR / "living-narrative-fabric" / "orchestrator.py"
    )
    orch = _load_module_from_path(
        "snapshot_living_narrative_orchestrator_for_tests", orch_path
    )

    fabric = orch.LivingNarrativeFabric(runtime=orch.Runtime("inprocess"))
    version = fabric.synthesize(
        topic="snapshot-fixture",
        time_range=orch.TimeRange.D7.value,
        audit=False,
    )

    # ``SynthesisVersion`` is a dataclass — serialise it via vars().
    payload = {
        "topic": version.topic,
        "time_range": version.time_range,
        "claim_count": len(getattr(version, "claims", []) or []),
        "contradiction_count": len(
            getattr(version, "contradictions", []) or []
        ),
        # version_id + parent_version_id + computed_at are scrubbed by the
        # deterministic_serializer below.
        "version_id": getattr(version, "version_id", None),
        "parent_version_id": getattr(version, "parent_version_id", None),
        "computed_at": str(getattr(version, "computed_at", "")),
    }

    scrubbed = deterministic_serializer(payload)
    assert scrubbed == snapshot


# --------------------------------------------------------------------------
# Test 3 — self-evolving-personal-os
# --------------------------------------------------------------------------

def test_self_evolving_personal_os_daily_brief_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deterministic_serializer,
    snapshot,
) -> None:
    """Snapshot the SEPOS stub-mode daily_brief output."""
    _redirect_appdata(monkeypatch, tmp_path)

    agent_path = (
        _SUPER_AGENTS_DIR / "self-evolving-personal-os" / "agent.py"
    )
    agent = _load_module_from_path(
        "snapshot_sepos_agent_for_tests", agent_path
    )

    out = agent.daily_brief(
        user_id="snapshot-fixture",
        force_stub=True,
        allow_write=False,
        sources=[],
        quiet=True,
    )

    scrubbed = deterministic_serializer(out)
    if isinstance(scrubbed, dict):
        scrubbed.pop("agent_version", None)
    assert scrubbed == snapshot
