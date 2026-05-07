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
"""
Grok Agent OS — Autonomous Template Generator (P121).

Emits a v2.15-compliant grok-agent.yaml manifest plus a starter README
for any of the eight kinds in the v2.15 enum:

  agent · finance-dashboard · alpha-engine · creator-payout-optimizer ·
  vision-analyzer · super-agent · x-native · creator-template

The output is written to the destination folder (created on demand) and
is guaranteed to validate cleanly against `safety/scanner.py` when given
a sensible description and a valid X handle.

Usage (Windows 11, PowerShell):

    python scripts/generate-template.py new my-agent `
        --kind super-agent `
        --description "Synthesises X + news for daily briefings." `
        --author "@JanSol0s" `
        --out templates/super-agents/my-agent

    python scripts/generate-template.py new payout-helper `
        --kind creator-payout-optimizer `
        --description "Forecasts X creator payouts with tax export." `
        --author "@JanSol0s" `
        --out templates/finance/payout-helper

The script only emits text — it never touches the network, never reads
a remote schema, and never mutates files outside the `--out` folder.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

VERSION = "0.1.0"

KINDS: Tuple[str, ...] = (
    "agent",
    "finance-dashboard",
    "alpha-engine",
    "creator-payout-optimizer",
    "vision-analyzer",
    "super-agent",
    "x-native",
    "creator-template",
)

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
AUTHOR_PATTERN = re.compile(r"^@[A-Za-z0-9_]{1,15}$")

KIND_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "agent": {
        "tags": ["agent", "windows-first"],
        "port": 8540,
        "consent_gates": [],
        "needs_finance": False,
        "needs_tax": False,
        "needs_real_world": False,
        "is_super": False,
        "needs_vision": False,
    },
    "finance-dashboard": {
        "tags": ["finance", "x-money", "streamlit", "sqlite"],
        "port": 8501,
        "consent_gates": ["export_tax_report", "sync_to_cloud"],
        "needs_finance": True,
        "needs_tax": True,
        "needs_real_world": False,
        "is_super": False,
        "needs_vision": False,
    },
    "alpha-engine": {
        "tags": ["alpha", "x-money", "cashtag", "streamlit"],
        "port": 8502,
        "consent_gates": ["publish_alert"],
        "needs_finance": True,
        "needs_tax": False,
        "needs_real_world": False,
        "is_super": False,
        "needs_vision": False,
    },
    "creator-payout-optimizer": {
        "tags": ["payout", "x-money", "creator-tools", "tax"],
        "port": 8503,
        "consent_gates": ["export_tax_report"],
        "needs_finance": True,
        "needs_tax": True,
        "needs_real_world": False,
        "is_super": False,
        "needs_vision": False,
    },
    "vision-analyzer": {
        "tags": ["vision", "x-money", "receipts", "streamlit"],
        "port": 8504,
        "consent_gates": ["import_receipt", "export_tax_report"],
        "needs_finance": True,
        "needs_tax": True,
        "needs_real_world": False,
        "is_super": False,
        "needs_vision": True,
    },
    "super-agent": {
        "tags": ["super-agent", "memory", "provenance"],
        "port": 8510,
        "consent_gates": [
            "publish_synthesis",
            "export_provenance_log",
            "apply_improvements",
        ],
        "needs_finance": False,
        "needs_tax": False,
        "needs_real_world": True,
        "is_super": True,
        "needs_vision": False,
    },
    "x-native": {
        "tags": ["x-native", "reply-only"],
        "port": 8530,
        "consent_gates": ["reply_on_x"],
        "needs_finance": False,
        "needs_tax": False,
        "needs_real_world": True,
        "is_super": False,
        "needs_vision": False,
    },
    "creator-template": {
        "tags": ["creator", "creator-tools"],
        "port": 8520,
        "consent_gates": ["publish_post"],
        "needs_finance": False,
        "needs_tax": False,
        "needs_real_world": False,
        "is_super": False,
        "needs_vision": False,
    },
}


def _yaml_list(items: List[str], indent: int) -> str:
    if not items:
        return "[]"
    pad = " " * indent
    return "\n" + "\n".join(f'{pad}- "{item}"' for item in items)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_manifest(
    name: str,
    kind: str,
    description: str,
    author: str,
) -> str:
    if kind not in KIND_DEFAULTS:
        raise ValueError(f"Unknown kind: {kind!r}. Choose one of {KINDS}.")
    cfg = KIND_DEFAULTS[kind]
    title = " ".join(part.capitalize() for part in name.split("-"))
    lines: List[str] = [
        "# Copyright 2026 AgentMindCloud",
        "# Licensed under the Apache License, Version 2.0",
        "# http://www.apache.org/licenses/LICENSE-2.0",
        "#",
        f"# Generated by scripts/generate-template.py v{VERSION}",
        f"# kind: {kind}  ·  name: {name}",
        "",
        f'version: "2.15"',
        f'kind: "{kind}"',
        f'name: "{name}"',
        f'description: "{_escape(description)}"',
        f'author: "{author}"',
        f'license: "Apache-2.0"',
        "",
        "metadata:",
        f'  display_name: "{title}"',
        f'  tagline: "{_escape(description[:120])}"',
        f"  tags:{_yaml_list(cfg['tags'], 4)}",
        '  language: "en"',
        '  repository: "https://github.com/AgentMindCloud/grok-agent"',
        "",
        "install:",
        "  one_click: true",
        f'  install_command: "grok-agent install {name}"',
        "  prerequisites:",
        '    - "Windows 11"',
        '    - "Python 3.12+"',
        '    - "PowerShell 5.1+"',
        "",
        "windows:",
        '  launcher: "launcher.ps1"',
        f'  appdata_folder: "grok-agent/{name}"',
        f'  log_folder: "grok-agent/{name}/logs"',
        f"  default_port: {cfg['port']}",
        "  chrome_only: true",
        "  requires_admin: false",
        '  min_powershell_version: "5.1"',
        "",
        "grok:",
        '  model: "grok-4.3"',
        "  temperature: 0.5",
        "  max_tokens: 4096",
        '  system_prompt_file: "prompts/system.md"',
        "  tool_calling: true",
        f"  vision: {'true' if cfg['needs_vision'] else 'false'}",
        "",
        "safety:",
        '  pii_handling: "local-only"',
        "  data_retention_days: 90",
        '  scanner_severity_floor: "warn"',
        "  cost_limits:",
        "    usd_per_session_max: 0.50",
        "    usd_per_day_max: 5.00",
        "  human_in_the_loop:",
        f"    enabled: {'true' if cfg['consent_gates'] else 'false'}",
    ]
    if cfg["consent_gates"]:
        lines.append("    confirm_before:")
        for gate in cfg["consent_gates"]:
            lines.append(f'      - "{gate}"')
    lines += [
        "  disclaimers:",
        f"    not_financial_advice: {str(cfg['needs_finance']).lower()}",
        f"    not_tax_advice: {str(cfg['needs_tax']).lower()}",
        f"    real_world_action_consent: {str(cfg['needs_real_world']).lower()}",
        "    not_medical_advice: false",
    ]

    lines += [
        "",
        "constitution:",
        "  rules:",
        '    - "Every claim must cite its source."',
        '    - "Real-world actions require explicit user consent."',
        '    - "Local data stays under $env:LOCALAPPDATA."',
        '    - "Provenance is append-only — never mutated."',
    ]
    if cfg["consent_gates"]:
        lines.append("  consent_gates:")
        for gate in cfg["consent_gates"]:
            lines.append(f'    - "{gate}"')
    else:
        lines.append("  consent_gates: []")

    if kind == "x-native":
        lines += [
            "",
            "real_time_x:",
            "  enabled: true",
            "  reply_only: true",
            "  consent_required: true",
            "  max_posts_per_day: 25",
        ]

    if cfg["is_super"]:
        lines += [
            "",
            "memory:",
            "  enabled: true",
            '  provider: "mem0"',
            "  vector_store:",
            '    backend: "qdrant"',
            f'    collection_prefix: "{name}"',
            "  retention_days: 730",
            "  encryption_at_rest: true",
            "",
            "provenance:",
            "  enabled: true",
            f'  log_path: "$env:LOCALAPPDATA\\\\grok-agent\\\\{name}\\\\provenance\\\\events.jsonl"',
            "  cite_sources: true",
            "  append_only: true",
            "",
            "multi_agent:",
            '  role: "orchestrator"',
            '  shared_memory: "mem0://grok-agent-shared"',
            "  max_concurrent_workers: 3",
        ]

    lines += [
        "",
        "tools:",
        '  - name: "run"',
        '    type: "local_function"',
        f'    description: "Primary entry point for {title}."',
        '    module: "main"',
        f'    function: "{name.replace("-", "_")}_run"',
        "    parameters:",
        "      schema:",
        '        type: "object"',
        '        properties: {}',
        "        required: []",
    ]

    return "\n".join(lines) + "\n"


def render_readme(name: str, kind: str, description: str) -> str:
    title = " ".join(part.capitalize() for part in name.split("-"))
    disclaimers = ""
    if KIND_DEFAULTS[kind]["needs_finance"]:
        disclaimers += (
            "\n> ⚠️ **Not financial advice.** This tool provides information only.\n"
            "> Always consult a licensed financial advisor before making decisions.\n"
        )
    if KIND_DEFAULTS[kind]["needs_tax"]:
        disclaimers += (
            "\n> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.\n"
            "> Consult a licensed tax professional.\n"
        )
    if KIND_DEFAULTS[kind]["needs_real_world"]:
        disclaimers += (
            "\n> ⚠️ **This agent can take real-world actions.** Every action requires explicit consent.\n"
        )
    return (
        "<!-- Apache 2.0 License -->\n"
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "\n"
        f"# {title}\n"
        "\n"
        f"_kind:_ `{kind}` · _generated by `scripts/generate-template.py`._\n"
        f"{disclaimers}\n"
        f"{description}\n"
        "\n"
        "## Install (Windows 11, PowerShell)\n"
        "\n"
        "```powershell\n"
        f".\\cli\\grok-agent.ps1 install templates/<your-folder>/{name}/grok-agent.yaml\n"
        "```\n"
        "\n"
        "## Validate\n"
        "\n"
        "```powershell\n"
        "python cli/grok-agent.py validate grok-agent.yaml\n"
        "python safety/scanner.py scan grok-agent.yaml\n"
        "```\n"
        "\n"
        "## License\n"
        "\n"
        "Apache 2.0\n"
    )


def cmd_new(args: argparse.Namespace) -> int:
    name = args.name.strip().lower()
    kind = args.kind.strip().lower()
    description = args.description.strip()
    author = args.author.strip()

    if not NAME_PATTERN.match(name):
        sys.stderr.write(
            f"X  name '{name}' must match /^[a-z][a-z0-9-]*$/ (kebab-case).\n"
        )
        return 65
    if kind not in KINDS:
        sys.stderr.write(
            f"X  kind '{kind}' is not in v2.15 enum: {', '.join(KINDS)}\n"
        )
        return 65
    if len(description) < 10:
        sys.stderr.write("X  description must be at least 10 characters.\n")
        return 65
    if not AUTHOR_PATTERN.match(author):
        sys.stderr.write(
            "X  author must be an X handle, e.g. @JanSol0s (1-15 chars after @).\n"
        )
        return 65

    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "grok-agent.yaml"
    readme_path = out / "README.md"
    if manifest_path.exists() and not args.force:
        sys.stderr.write(
            f"X  {manifest_path} already exists. Use --force to overwrite.\n"
        )
        return 70

    manifest_path.write_text(
        render_manifest(name, kind, description, author),
        encoding="utf-8",
        newline="\n",
    )
    readme_path.write_text(
        render_readme(name, kind, description),
        encoding="utf-8",
        newline="\n",
    )

    sys.stdout.write(f"OK  Wrote {manifest_path}\n")
    sys.stdout.write(f"OK  Wrote {readme_path}\n")
    sys.stdout.write(
        f"--  Validate: python cli/grok-agent.py validate \"{manifest_path}\"\n"
        f"--  Scan:     python safety/scanner.py scan \"{manifest_path}\"\n"
    )
    return 0


def cmd_kinds(_args: argparse.Namespace) -> int:
    sys.stdout.write("Supported kinds (v2.15):\n")
    for kind in KINDS:
        cfg = KIND_DEFAULTS[kind]
        sys.stdout.write(
            f"  - {kind:28s} port={cfg['port']:5d}  "
            f"finance={str(cfg['needs_finance']):5s}  super={str(cfg['is_super']):5s}\n"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok-agent-generate-template",
        description=(
            f"Grok Agent OS — autonomous v2.15 manifest builder (v{VERSION}). "
            "Emits a kind-aware grok-agent.yaml + a starter README for any of "
            f"the {len(KINDS)} v2.15 kinds."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"generate-template.py {VERSION}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Generate a manifest + README for a new agent.")
    p_new.add_argument("name", help="kebab-case slug (matches the parent folder name).")
    p_new.add_argument("--kind", required=True, choices=KINDS, help="v2.15 kind enum.")
    p_new.add_argument(
        "--description",
        required=True,
        help="One-sentence description (>=10 chars).",
    )
    p_new.add_argument(
        "--author",
        default="@JanSol0s",
        help="X handle (default: @JanSol0s).",
    )
    p_new.add_argument(
        "--out",
        required=True,
        help="Destination folder (will be created if missing).",
    )
    p_new.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing grok-agent.yaml in --out.",
    )
    p_new.set_defaults(func=cmd_new)

    p_kinds = sub.add_parser("kinds", help="List supported v2.15 kinds and defaults.")
    p_kinds.set_defaults(func=cmd_kinds)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
