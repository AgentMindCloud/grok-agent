# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Offline regression test for the README -> v2.15 manifest generator prompt.

Built for xAI, X, Grok and the ecosystem community. ❤️

This script reproduces the exact system + user prompt used by the serverless
route at marketplace/app/api/generate/route.ts so we can:

  - inspect the prompt without a browser,
  - dry-run the wizard offline (no API spend) via --mock,
  - validate live Anthropic outputs against the canonical Pydantic v2.15
    model from cli/grok-agent.py.

Usage:

    python scripts/test-generator-prompt.py --mock
    python scripts/test-generator-prompt.py                  # live, if ANTHROPIC_API_KEY set
    python scripts/test-generator-prompt.py --kind super-agent --source-file path/to/README.md

Default behaviour: if ANTHROPIC_API_KEY is unset, the script auto-falls-back
to --mock mode and prints the stub manifest. When the env var IS set (and
--mock is not passed), the script calls Anthropic with the same parameters
the route uses and validates the result.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the canonical Pydantic model — same trick scripts/export-openapi.py uses
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CLI_MODULE_PATH = _REPO_ROOT / "cli" / "grok-agent.py"
_SCHEMA_REFERENCE = _REPO_ROOT / "spec" / "v2.15" / "grok-agent.yaml"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("grok_agent_cli", _CLI_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CLI module at {_CLI_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Prompt — DO NOT DRIFT from marketplace/app/api/generate/route.ts.
# Both copies are scanned by safety/scanner.py for forbidden phrases.
# ---------------------------------------------------------------------------

VALID_KINDS = (
    "agent",
    "finance-dashboard",
    "alpha-engine",
    "creator-payout-optimizer",
    "vision-analyzer",
    "super-agent",
    "x-native",
    "creator-template",
)

SYSTEM_PROMPT = "\n".join(
    [
        "You are a v2.15 grok-agent.yaml manifest author for the open Grok Agent OS",
        "distribution layer (AgentMindCloud/grok-agent). Given a project description",
        "and a manifest kind, produce a single valid YAML manifest.",
        "",
        "Hard rules:",
        "- Output YAML only. No markdown fences. No commentary before or after.",
        "- Never invent fields that are not in the v2.15 schema summary you are given.",
        "- Always declare every required top-level field: version, kind, name,",
        "  description, author, license. version must be the string \"2.15\".",
        "  license must be the string \"Apache-2.0\".",
        "- name must be kebab-case matching ^[a-z][a-z0-9-]*$.",
        "- Enumerate items explicitly. Do not abbreviate lists with vague",
        "  trailing phrases. If you do not know an item, omit it.",
        "- If kind is super-agent, include a constitution: block.",
        "- If kind is vision-analyzer, include a grok: block with vision: true.",
        "- Prefer omitting optional sections over guessing. The user can extend later.",
        "- All shell examples in any field must be PowerShell on Windows 11",
        "  (use $env:LOCALAPPDATA, semicolons, New-Item — never bash).",
    ]
)

SCHEMA_SUMMARY = "\n".join(
    [
        "v2.15 schema summary (use only these top-level keys):",
        "",
        "REQUIRED top-level keys:",
        "  version       string  must be \"2.15\"",
        "  kind          string  one of: agent, finance-dashboard, alpha-engine,",
        "                          creator-payout-optimizer, vision-analyzer,",
        "                          super-agent, x-native, creator-template",
        "  name          string  kebab-case slug, ^[a-z][a-z0-9-]*$",
        "  description   string  >= 10 chars, ends with a period",
        "  author        string  X handle with @ prefix (e.g. \"@JanSol0s\")",
        "  license       string  must be \"Apache-2.0\"",
        "",
        "OPTIONAL top-level sections (declare only what the agent uses):",
        "  metadata, install, windows, grok, tools, data, ui, safety,",
        "  constitution, evaluation, multi_agent, real_time_x.",
        "",
        "Disclaimers (mandatory when kind matches):",
        "  finance-dashboard, alpha-engine, creator-payout-optimizer:",
        "    safety.disclaimers must include \"Not financial advice\".",
        "  Any tool that touches taxes:",
        "    safety.disclaimers must also include \"Not tax advice\".",
        "  super-agent, x-native, real-world action agents:",
        "    safety.consent_gates must enumerate every external action explicitly.",
    ]
)


def build_user_message(source: str, kind: str) -> str:
    return "\n".join(
        [
            f"Kind: {kind}",
            "",
            SCHEMA_SUMMARY,
            "",
            "Project description (verbatim, may be a README or freeform notes):",
            "---",
            source.strip(),
            "---",
            "",
            "Produce the YAML manifest now. YAML only.",
        ]
    )


# ---------------------------------------------------------------------------
# Stub manifest used by --mock mode
# ---------------------------------------------------------------------------

STUB_SOURCE = (
    "# Demo Agent\n\n"
    "This is a sample project description used by the offline generator test.\n"
    "It is intentionally longer than 100 characters so the route's input "
    "validator would accept it in a live request. The agent reads sample text "
    "and produces a friendly summary."
)

STUB_MANIFEST_BY_KIND = {
    "agent": (
        'version: "2.15"\n'
        'kind: "agent"\n'
        'name: "demo-generator-agent"\n'
        'description: "A minimal demo agent produced by the offline generator stub."\n'
        'author: "@JanSol0s"\n'
        'license: "Apache-2.0"\n'
        "metadata:\n"
        '  display_name: "Demo Generator Agent"\n'
        '  tagline: "Stub manifest for offline tests."\n'
    ),
    "super-agent": (
        'version: "2.15"\n'
        'kind: "super-agent"\n'
        'name: "demo-super-agent"\n'
        'description: "Super agent stub produced by the offline generator test."\n'
        'author: "@JanSol0s"\n'
        'license: "Apache-2.0"\n'
        "constitution:\n"
        '  rules: ["Local-first by default. Always require explicit consent for external actions."]\n'
        "  consent_gates: []\n"
        "  hard_refusals: []\n"
    ),
    "vision-analyzer": (
        'version: "2.15"\n'
        'kind: "vision-analyzer"\n'
        'name: "demo-vision-agent"\n'
        'description: "Vision analyzer stub produced by the offline generator test."\n'
        'author: "@JanSol0s"\n'
        'license: "Apache-2.0"\n'
        "grok:\n"
        '  model: "grok-4.3"\n'
        "  vision: true\n"
    ),
}


def stub_manifest(kind: str) -> str:
    if kind in STUB_MANIFEST_BY_KIND:
        return STUB_MANIFEST_BY_KIND[kind]
    return (
        f'version: "2.15"\n'
        f'kind: "{kind}"\n'
        f'name: "demo-{kind}"\n'
        f'description: "Stub manifest produced by the offline generator test."\n'
        f'author: "@JanSol0s"\n'
        f'license: "Apache-2.0"\n'
    )


# ---------------------------------------------------------------------------
# Live API call (only used when not in mock mode)
# ---------------------------------------------------------------------------

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"


def call_anthropic(api_key: str, source: str, kind: str, timeout: int = 60) -> str:
    payload = json.dumps(
        {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 2048,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": build_user_message(source, kind)}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ANTHROPIC_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Anthropic URL error: {e}") from e

    data = json.loads(body)
    chunks = [
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    ]
    return _strip_fence("".join(chunks).strip())


def _strip_fence(text: str) -> str:
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1 and text.rstrip().endswith("```"):
            return text[first_newline + 1 : text.rstrip()[:-3].__len__()].strip()
    return text


# ---------------------------------------------------------------------------
# Validation against the canonical Pydantic model
# ---------------------------------------------------------------------------


def validate_yaml(yaml_text: str) -> tuple[bool, str]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return False, "pyyaml not installed (python -m pip install pyyaml)"
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return False, f"YAML parse error: {e}"
    if not isinstance(data, dict):
        return False, "Manifest must be a YAML mapping at the top level."

    cli = _load_cli_module()
    Manifest = cli.GrokAgentManifest
    # cli/grok-agent.py uses `from __future__ import annotations`, so every
    # field annotation is a string. Pydantic needs forward refs resolved
    # against the module namespace before validate works.
    try:
        Manifest.model_rebuild(_types_namespace=vars(cli))
    except Exception as e:
        return False, f"Pydantic model rebuild failed: {e}"
    try:
        Manifest.model_validate(data)
    except Exception as e:
        return False, f"Pydantic validation failed: {e}"
    return True, "VALID v2.15 manifest"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Offline test for the README -> v2.15 manifest generator prompt. "
            "Built for xAI, X, Grok and the ecosystem community."
        )
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Skip the Anthropic call. Print the prompt + a stub manifest. Default if ANTHROPIC_API_KEY is unset.",
    )
    parser.add_argument(
        "--kind",
        choices=VALID_KINDS,
        default="agent",
        help="Manifest kind to generate (default: agent).",
    )
    parser.add_argument(
        "--source-file",
        type=Path,
        default=None,
        help="Path to a README or notes file to feed as source. Falls back to a built-in stub.",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the system + user prompt that would be sent.",
    )
    args = parser.parse_args(argv)

    if args.source_file is not None:
        if not args.source_file.is_file():
            sys.stderr.write(f"X  source-file not found: {args.source_file}\n")
            return 2
        source = args.source_file.read_text(encoding="utf-8")
    else:
        source = STUB_SOURCE

    if len(source) < 100:
        sys.stderr.write(
            f"X  source must be >= 100 chars (got {len(source)}). "
            "The route enforces the same minimum.\n"
        )
        return 2

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    use_mock = args.mock or not api_key

    sys.stdout.write("=" * 72 + "\n")
    sys.stdout.write(f"Generator prompt test  |  kind={args.kind}  |  mode={'mock' if use_mock else 'live'}\n")
    sys.stdout.write(f"Schema reference: {_SCHEMA_REFERENCE.relative_to(_REPO_ROOT)}\n")
    sys.stdout.write("=" * 72 + "\n")

    if args.print_prompt or use_mock:
        sys.stdout.write("\n--- SYSTEM PROMPT ---\n")
        sys.stdout.write(SYSTEM_PROMPT + "\n")
        sys.stdout.write("\n--- USER MESSAGE ---\n")
        sys.stdout.write(build_user_message(source, args.kind) + "\n")

    if use_mock:
        if args.mock:
            sys.stdout.write("\n[mock] Skipping Anthropic call (--mock).\n")
        else:
            sys.stdout.write("\n[mock] ANTHROPIC_API_KEY unset — auto-falling back to mock mode.\n")
        yaml_text = stub_manifest(args.kind)
    else:
        sys.stdout.write("\n[live] Calling Anthropic Messages API...\n")
        try:
            yaml_text = call_anthropic(api_key, source, args.kind)
        except RuntimeError as e:
            sys.stderr.write(f"X  {e}\n")
            return 1

    sys.stdout.write("\n--- GENERATED YAML ---\n")
    sys.stdout.write(yaml_text.rstrip() + "\n")

    ok, message = validate_yaml(yaml_text)
    sys.stdout.write("\n--- VERDICT ---\n")
    if ok:
        sys.stdout.write(f"OK {message}\n")
        return 0
    sys.stdout.write(f"X  INVALID: {message}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
