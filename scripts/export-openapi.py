# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Export the v2.15 manifest schema as JSON Schema + OpenAPI 3.1.

Built for xAI, X, Grok and the ecosystem community. ❤️

The Pydantic v2.15 model in cli/grok-agent.py is the single source of
truth for the manifest schema. This script imports the model, dumps its
JSON schema, and wraps it in an OpenAPI 3.1 envelope so language-agnostic
tooling (VS Code YAML extension, generic OpenAPI validators, npm /
JetBrains / browser-extension wrappers) can consume the standard without
re-implementing Pydantic.

Outputs (overwritten on every run):

    spec/v2.15/schema.json        — pure JSON Schema 2020-12
    spec/v2.15/openapi.yaml       — OpenAPI 3.1 (yaml)

CI integration: a step in validate.yml or tests.yml can re-run this and
diff against the on-disk artifacts to catch silent schema drift.

Usage:

    python scripts/export-openapi.py
    python scripts/export-openapi.py --check     # exit 1 if drift detected
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make cli/ importable so we can pull GrokAgentManifest from grok-agent.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CLI_DIR = _REPO_ROOT / "cli"
if str(_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(_CLI_DIR))

# The CLI module file is named with a hyphen ("grok-agent.py") which is
# not a legal Python identifier, so import via importlib.
import importlib.util  # noqa: E402

_CLI_MODULE_PATH = _CLI_DIR / "grok-agent.py"
_spec = importlib.util.spec_from_file_location("grok_agent_cli", _CLI_MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load CLI module at {_CLI_MODULE_PATH}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

GrokAgentManifest = _module.GrokAgentManifest
SPEC_VERSION = _module.SPEC_VERSION
ACCEPTED_VERSIONS = _module.ACCEPTED_VERSIONS
TAGLINE = _module.TAGLINE


SCHEMA_OUT = _REPO_ROOT / "spec" / "v2.15" / "schema.json"
OPENAPI_OUT = _REPO_ROOT / "spec" / "v2.15" / "openapi.yaml"

LICENSE_HEADER_JSON_NOTE = (
    "JSON does not support comments. License + provenance metadata are "
    "carried in the $schema and info blocks below; the canonical license "
    "is Apache-2.0, the canonical source is "
    "https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/openapi.yaml"
)


def _build_json_schema() -> dict:
    """Build the JSON Schema 2020-12 document from the Pydantic model."""
    # cli/grok-agent.py uses `from __future__ import annotations`, which
    # turns every type hint into a string. Pydantic needs the forward
    # references resolved before it can emit a JSON schema, so we kick
    # the rebuild now in the same module's namespace.
    GrokAgentManifest.model_rebuild(_types_namespace=vars(_module))
    raw = GrokAgentManifest.model_json_schema()
    raw["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    raw["$id"] = (
        "https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/schema.json"
    )
    raw["title"] = "Grok Agent OS Manifest (v2.15)"
    raw["description"] = (
        "Schema for grok-agent.yaml v2.15 manifests — the open Windows-first "
        "distribution layer for deploying Grok agents on X. " + TAGLINE
    )
    raw["x-license"] = "Apache-2.0"
    raw["x-spec-version"] = SPEC_VERSION
    raw["x-accepted-versions"] = list(ACCEPTED_VERSIONS)
    raw["x-source"] = (
        "https://github.com/AgentMindCloud/grok-agent/blob/main/cli/grok-agent.py"
    )
    raw["x-note"] = LICENSE_HEADER_JSON_NOTE
    return raw


def _build_openapi(schema: dict) -> dict:
    """Wrap the JSON Schema in an OpenAPI 3.1 envelope.

    OpenAPI 3.1 is fully JSON Schema 2020-12 compatible, so the model
    can be dropped under `components.schemas.GrokAgentManifest` verbatim.
    A single notional /validate endpoint is declared so any OpenAPI tool
    that requires a `paths` block has something to render.
    """
    components_schema = {k: v for k, v in schema.items() if not k.startswith("$")}
    components_schema.pop("title", None)
    components_schema.pop("description", None)

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Grok Agent OS Manifest API",
            "version": SPEC_VERSION,
            "description": (
                "OpenAPI 3.1 envelope around the Grok Agent OS v2.15 manifest "
                "schema. The notional /validate endpoint is documentation-only — "
                "no server is required. Any OpenAPI-aware client can read "
                "components.schemas.GrokAgentManifest to validate a manifest "
                "locally. Built for xAI, X, Grok and the ecosystem community."
            ),
            "license": {
                "name": "Apache-2.0",
                "url": "https://www.apache.org/licenses/LICENSE-2.0",
            },
            "contact": {
                "name": "AgentMindCloud",
                "url": "https://github.com/AgentMindCloud/grok-agent",
            },
        },
        "externalDocs": {
            "description": "Grok Agent OS documentation + spec",
            "url": "https://github.com/AgentMindCloud/grok-agent",
        },
        "paths": {
            "/validate": {
                "post": {
                    "summary": "Validate a v2.15 manifest",
                    "description": (
                        "Notional endpoint. The manifest in the request body is "
                        "validated against components.schemas.GrokAgentManifest. "
                        "No server is required — this is for OpenAPI tooling only."
                    ),
                    "operationId": "validateManifest",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/yaml": {
                                "schema": {"$ref": "#/components/schemas/GrokAgentManifest"}
                            },
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/GrokAgentManifest"}
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Valid manifest",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "ok": {"type": "boolean"},
                                            "version": {"type": "string"},
                                            "kind": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        },
                        "422": {
                            "description": "Manifest failed v2.15 schema validation",
                        },
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "GrokAgentManifest": components_schema,
            }
        },
        "x-spec-version": SPEC_VERSION,
        "x-accepted-versions": list(ACCEPTED_VERSIONS),
        "x-license": "Apache-2.0",
    }


def _write_yaml(path: Path, data: dict) -> str:
    """Write a YAML file (no anchors, deterministic key order)."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover — pyyaml is a hard dep
        sys.stderr.write(
            "ERROR: pyyaml is required. Install with: python -m pip install pyyaml\n"
        )
        sys.exit(69)
    text = yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return text


def _write_json(path: Path, data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


LICENSE_HEADER_YAML = (
    "# Copyright 2026 AgentMindCloud\n"
    "# Licensed under the Apache License, Version 2.0\n"
    "# http://www.apache.org/licenses/LICENSE-2.0\n"
    "#\n"
    "# Auto-generated by scripts/export-openapi.py from cli/grok-agent.py.\n"
    "# Do NOT edit by hand — the next regeneration will overwrite changes.\n"
    f"# Spec version: v{SPEC_VERSION}. Accepted versions: "
    f"{', '.join(ACCEPTED_VERSIONS)}.\n"
    f"# {TAGLINE}\n"
    "\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export the v2.15 Grok Agent OS manifest schema as JSON Schema "
            "and OpenAPI 3.1. " + TAGLINE
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Exit 1 if the on-disk artifacts differ from what this script "
            "would generate. Use in CI to detect schema drift."
        ),
    )
    args = parser.parse_args(argv)

    schema = _build_json_schema()
    openapi = _build_openapi(schema)

    json_text = _write_json(SCHEMA_OUT, schema)
    yaml_body = _write_yaml(OPENAPI_OUT, openapi)
    yaml_text = LICENSE_HEADER_YAML + yaml_body

    if args.check:
        drift = []
        if not SCHEMA_OUT.is_file() or SCHEMA_OUT.read_text(encoding="utf-8") != json_text:
            drift.append(str(SCHEMA_OUT.relative_to(_REPO_ROOT)))
        if not OPENAPI_OUT.is_file() or OPENAPI_OUT.read_text(encoding="utf-8") != yaml_text:
            drift.append(str(OPENAPI_OUT.relative_to(_REPO_ROOT)))
        if drift:
            sys.stderr.write(
                "X  Schema drift detected. Re-run scripts/export-openapi.py:\n"
            )
            for d in drift:
                sys.stderr.write(f"   - {d}\n")
            return 1
        sys.stdout.write("OK No schema drift detected.\n")
        return 0

    SCHEMA_OUT.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_OUT.write_text(json_text, encoding="utf-8")
    OPENAPI_OUT.write_text(yaml_text, encoding="utf-8")
    sys.stdout.write(
        f"OK Wrote {SCHEMA_OUT.relative_to(_REPO_ROOT)} "
        f"({len(json_text)} bytes)\n"
    )
    sys.stdout.write(
        f"OK Wrote {OPENAPI_OUT.relative_to(_REPO_ROOT)} "
        f"({len(yaml_text)} bytes)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
