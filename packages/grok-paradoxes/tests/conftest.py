# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built for xAI, X, Grok and the ecosystem community. ❤️
#
# Shared pytest configuration for the grok-paradoxes test suite.
#
# Two responsibilities:
#
#   1. Inject ``packages/grok-paradoxes/src`` onto ``sys.path`` so a plain
#      ``import grok_paradoxes`` resolves even when the package has not been
#      installed via ``pip install -e packages/grok-paradoxes/`` (common
#      during local hacking and during the parallel swarm where Agent 2.1
#      may still be writing the source files).
#
#   2. Register the ``smoke`` pytest marker. The package's pyproject.toml
#      runs pytest with ``--strict-markers``, so any custom marker must be
#      declared somewhere or collection fails. Declaring it here keeps the
#      registration co-located with the test files that use it.
#
# Tests use ``pytest.importorskip("grok_paradoxes")`` at module top-level
# so the entire module skips cleanly when Agent 2.1's source is not yet
# importable. This avoids spurious red CI runs while the swarm is in flight.

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# sys.path injection — make ``import grok_paradoxes`` resolve even without
# ``pip install -e``. The package layout is:
#
#   packages/grok-paradoxes/
#       src/
#           grok_paradoxes/
#               __init__.py
#       tests/
#           conftest.py   <- this file
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
if _SRC.is_dir():
    src_str = str(_SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


# ---------------------------------------------------------------------------
# Marker registration — required because pyproject.toml uses --strict-markers
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so ``--strict-markers`` does not reject them."""

    config.addinivalue_line(
        "markers",
        "smoke: hermetic smoke check (no network, no GUI, no secrets).",
    )
