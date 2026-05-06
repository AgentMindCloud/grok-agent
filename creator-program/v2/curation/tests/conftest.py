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
"""Pytest configuration for the curation submodule.

The parent directory `creator-program/` contains a hyphen, so a plain
`import` of `creator-program.v2.curation` is not legal Python. This conftest
mirrors the P168 pattern under `creator-program/v2/tests/conftest.py`:
the v2 package is loaded under the alias `grok_creator_v2`, then the
curation package is registered as `grok_creator_v2.curation` so the test
file can do `from grok_creator_v2.curation import ...` directly.

Running the suite from the repo root:

    python -m pytest creator-program/v2/curation/tests/

This pattern keeps the tests runnable both inside and outside CI without
modifying the parent directory layout.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_V2_ALIAS = "grok_creator_v2"
_CURATION_ALIAS = f"{_V2_ALIAS}.curation"


def _load_package(alias: str, init_file: Path, search_dir: Path) -> None:
    """Load a package under a custom alias with submodule discovery enabled."""
    spec = importlib.util.spec_from_file_location(
        alias,
        init_file,
        submodule_search_locations=[str(search_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to build import spec for {init_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


def _bootstrap_curation_aliases() -> None:
    """Register `grok_creator_v2` and `grok_creator_v2.curation` in sys.modules.

    The curation package's relative imports
    (`from .trend_analyzer import ...`) work as long as the parent package
    object knows its own `__path__`, which is supplied via
    `submodule_search_locations` on the spec.
    """
    curation_dir = Path(__file__).resolve().parent.parent
    v2_dir = curation_dir.parent

    if _V2_ALIAS not in sys.modules:
        _load_package(_V2_ALIAS, v2_dir / "__init__.py", v2_dir)

    if _CURATION_ALIAS not in sys.modules:
        _load_package(_CURATION_ALIAS, curation_dir / "__init__.py", curation_dir)
        # Bind the curation module as an attribute of its parent so that
        # `grok_creator_v2.curation` works in `from ... import ...` form.
        setattr(sys.modules[_V2_ALIAS], "curation", sys.modules[_CURATION_ALIAS])


_bootstrap_curation_aliases()
