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

P176 fix (Step 34): in addition to the dict-shaped top-level sections
(metadata, install, grok, multi_agent, ...), the detector now traverses
nested Pydantic submodels:

  * Tool         → tools[] list-of-dicts in spec
  * PublicApi    → public_apis[] list-of-dicts in spec
  * ToolApi      → tools[].api dict in spec
  * ToolServer   → tools[].server dict in spec
  * DemoVideo    → metadata.demo_video dict in spec (P172)

For list sections we compute the union of keys present across every example
entry and compare against the corresponding Pydantic model's `model_fields`.
This guarantees that adding a new field to Tool / PublicApi / ToolApi /
ToolServer / DemoVideo without documenting it in the spec triggers DRIFT.

Exit codes:
    0  - no drift detected
    1  - drift found (Pydantic field undocumented OR doc field unimplemented)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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


def _list_section_doc_fields(grok_yaml: Dict[str, Any], section: str) -> Set[str]:
    """Return the union of keys present across every entry of a list-shaped section.

    Used for `tools:` (Tool model) and `public_apis:` (PublicApi model). The
    spec YAML documents a list of example entries; each entry illustrates a
    different shape (one tool may use `api`, another `module`/`function`,
    another `server`). Taking the union of keys across all entries yields
    the full surface of fields a user can declare — which is exactly what
    we must compare to the Pydantic model.
    """
    block = grok_yaml.get(section)
    if not isinstance(block, list):
        return set()
    fields: Set[str] = set()
    for entry in block:
        if isinstance(entry, dict):
            fields.update(entry.keys())
    return fields


def _list_section_nested_doc_fields(
    grok_yaml: Dict[str, Any], section: str, child_key: str
) -> Set[str]:
    """Return the union of keys for a nested dict child inside a list section.

    Example: `_list_section_nested_doc_fields(grok_yaml, "tools", "api")`
    returns the union of keys appearing under any `tools[].api` entry,
    matching the ToolApi Pydantic model. Likewise for `tools[].server`
    matching ToolServer.
    """
    block = grok_yaml.get(section)
    if not isinstance(block, list):
        return set()
    fields: Set[str] = set()
    for entry in block:
        if not isinstance(entry, dict):
            continue
        child = entry.get(child_key)
        if isinstance(child, dict):
            fields.update(child.keys())
    return fields


def _nested_dict_doc_fields(
    grok_yaml: Dict[str, Any], parent: str, child: str
) -> Set[str]:
    """Return the keys of a nested dict child under a top-level dict section.

    Example: `_nested_dict_doc_fields(grok_yaml, "metadata", "demo_video")`
    returns the keys of `metadata.demo_video` — which the DemoVideo model
    must mirror exactly (modulo extra="forbid", required vs optional).
    """
    parent_block = grok_yaml.get(parent)
    if not isinstance(parent_block, dict):
        return set()
    child_block = parent_block.get(child)
    if not isinstance(child_block, dict):
        return set()
    return set(child_block.keys())


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

    # ------------------------------------------------------------------
    # P176 (Step 34): nested Pydantic submodels.
    # Adding a field to one of these without updating the spec yaml must
    # surface as DRIFT — same way the top-level sections do.
    # ------------------------------------------------------------------
    nested_list_sections = [
        # (label,             pydantic class,  list section in YAML)
        ("tools[]",           "Tool",          "tools"),
        ("public_apis[]",     "PublicApi",     "public_apis"),
    ]
    for label, class_name, section_name in nested_list_sections:
        cls = getattr(cli_module, class_name, None)
        if cls is None:
            print(f"WARN  Pydantic class '{class_name}' not found")
            continue
        if not _compare(label, _pydantic_fields(cls),
                         _list_section_doc_fields(grok_yaml, section_name)):
            all_clean = False

    # Nested dicts INSIDE list-shaped sections (e.g. tools[].api, tools[].server).
    nested_in_list_sections = [
        # (label,             pydantic class,  list section,  child key)
        ("tools[].api",       "ToolApi",       "tools",       "api"),
        ("tools[].server",    "ToolServer",    "tools",       "server"),
    ]
    for label, class_name, section_name, child_key in nested_in_list_sections:
        cls = getattr(cli_module, class_name, None)
        if cls is None:
            print(f"WARN  Pydantic class '{class_name}' not found")
            continue
        if not _compare(label, _pydantic_fields(cls),
                         _list_section_nested_doc_fields(grok_yaml, section_name,
                                                         child_key)):
            all_clean = False

    # Nested dicts INSIDE dict-shaped sections (metadata.demo_video — P172).
    nested_in_dict_sections = [
        # (label,                     pydantic class, parent,    child)
        ("metadata.demo_video",       "DemoVideo",    "metadata", "demo_video"),
    ]
    for label, class_name, parent_section, child_key in nested_in_dict_sections:
        cls = getattr(cli_module, class_name, None)
        if cls is None:
            print(f"WARN  Pydantic class '{class_name}' not found")
            continue
        if not _compare(label, _pydantic_fields(cls),
                         _nested_dict_doc_fields(grok_yaml, parent_section,
                                                 child_key)):
            all_clean = False

    print("=" * 72)
    if all_clean:
        print("RESULT  No drift detected.")
        return 0
    print("RESULT  Schema drift detected. See sections marked DRIFT above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
