# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Built for xAI, X, Grok and the ecosystem community.
"""Pytest configuration for Creator Program v2.

The parent directory `creator-program/` contains a hyphen, which is not a
valid Python module identifier. To make `import` of the v2 package work
during test collection, this conftest loads `v2/__init__.py` via importlib
under the alias `grok_creator_v2` and registers the submodules so that the
relative-import statements inside the v2 package (e.g.
`from .tier_manager import Tier`) resolve to the same loaded module.

This keeps the test suite runnable from the repo root with:

    python -m pytest creator-program/v2/tests/

without requiring callers to rename `creator-program/` or add a top-level
package shim.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_v2_package() -> None:
    """Load creator-program/v2 as a package under the alias `grok_creator_v2`.

    The alias is also exposed via `sys.modules['v2']` so that the package's
    own relative imports (`from .tier_manager import ...`) work without
    modification.
    """
    v2_dir = Path(__file__).resolve().parent.parent
    init_file = v2_dir / "__init__.py"

    spec = importlib.util.spec_from_file_location(
        "grok_creator_v2",
        init_file,
        submodule_search_locations=[str(v2_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to build import spec for {init_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["grok_creator_v2"] = module
    spec.loader.exec_module(module)


_load_v2_package()
