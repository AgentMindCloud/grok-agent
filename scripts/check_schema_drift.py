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
"""Schema-drift detector (P162).

Validates that the Pydantic models in cli/grok-agent.py stay in sync with
the documented schema in spec/v2.15/grok-agent.yaml and
spec/v2.15/windows-extensions.yaml.

Exit codes:
    0  - no drift detected
    1  - drift found (Pydantic field undocumented OR doc field unimplemented)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Set

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    sys.stderr.write("ERROR: pyyaml is required: python -m pip install pyyaml\n")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "cli" / "grok-agent.py"
SPEC_GROK = REPO_ROOT / "spec" / "v2.15" / "grok-agent.yaml"
SPEC_WIN = REPO_ROOT / "spec" / "v2.15" / "windows-extensions.yaml"


def _load_grok_module():
    """Import cli/grok-agent.py despite the dashed filename."""
    spec = importlib.util.spec_from_file_location("grok_agent_cli", str(CLI_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {CLI_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pydantic_fields(model_cls) -> Set[str]:
    if not hasattr(model_cls, "model_fields"):
        return set()
    return set(model_cls.model_fields.keys())


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def _windows_doc_fields(win_yaml: Dict[str, Any], grok_yaml: Dict[str, Any]) -> Set[str]:
    fields: Set[str] = set()
    win_block = win_yaml.get("windows_extensions", {}).get("fields") or {}
    if isinstance(win_block, dict):
        fields.update(win_block.keys())
    main_win = grok_yaml.get("windows") or {}
    if isinstance(main_win, dict):
        fields.update(main_win.keys())
    return fields


def _section_doc_fields(grok_yaml: Dict[str, Any], section: str) -> Set[str]:
    block = grok_yaml.get(section)
    if not isinstance(block, dict):
        return set()
    return set(block.keys())


def _compare(label: str, pydantic: Set[str], spec: Set[str]) -> bool:
    extra_in_pydantic = pydantic - spec
    extra_in_spec = spec - pydantic
    if not extra_in_pydantic and not extra_in_spec:
        print(f"OK    {label}: aligned ({len(pydantic)} fields)")
        return True
    print(f"DRIFT {label}:")
    if extra_in_pydantic:
        print(f"      Pydantic-only (not documented): {sorted(extra_in_pydantic)}")
    if extra_in_spec:
        print(f"      Spec-only (no Pydantic field):  {sorted(extra_in_spec)}")
    return False


def main() -> int:
    print("=" * 72)
    print("Schema Drift Detector (P162)")
    print(f"  Pydantic source: {CLI_PATH.relative_to(REPO_ROOT)}")
    print(f"  Spec sources:    {SPEC_GROK.relative_to(REPO_ROOT)}, "
          f"{SPEC_WIN.relative_to(REPO_ROOT)}")
    print("=" * 72)

    grok_yaml = _load_yaml(SPEC_GROK)
    win_yaml = _load_yaml(SPEC_WIN)
    cli_module = _load_grok_module()

    sections = [
        ("metadata", "Metadata"),
        ("install", "Install"),
        ("grok", "Grok"),
        ("multi_agent", "MultiAgent"),
        ("real_time_x", "RealTimeX"),
        ("memory", "Memory"),
        ("provenance", "Provenance"),
        ("constitution", "Constitution"),
        ("safety", "Safety"),
        ("dependencies", "Dependencies"),
        ("evaluation", "Evaluation"),
    ]

    all_clean = True

    win_class = getattr(cli_module, "Windows", None)
    if win_class is None:
        print("WARN  Cannot find Windows class in Pydantic models")
    else:
        if not _compare("windows", _pydantic_fields(win_class),
                         _windows_doc_fields(win_yaml, grok_yaml)):
            all_clean = False

    for section_name, class_name in sections:
        cls = getattr(cli_module, class_name, None)
        if cls is None:
            print(f"WARN  Pydantic class '{class_name}' not found")
            continue
        if not _compare(section_name, _pydantic_fields(cls),
                         _section_doc_fields(grok_yaml, section_name)):
            all_clean = False

    print("=" * 72)
    if all_clean:
        print("RESULT  No drift detected.")
        return 0
    print("RESULT  Schema drift detected. See sections marked DRIFT above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
