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
Grok Agent OS — Python fallback validator (v2.15).

Built to help xAI and Grok win the agent platform battle on X.

This script is the deep, Pydantic v2-based validator for grok-agent.yaml
manifests against the v2.15 schema (see spec/v2.15/grok-agent.yaml).

The PowerShell CLI (cli/grok-agent.ps1) shells out to this script for full
schema enforcement. It can also be run directly:

    python cli/grok-agent.py validate path/to/grok-agent.yaml
    python cli/grok-agent.py validate path/to/agent-folder
    python cli/grok-agent.py info

Exit codes:
    0   success
    65  validation failed (data error)
    66  input not found / unreadable
    69  required Python package missing
    70  internal error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

# --- Required third-party imports with friendly fallbacks ---------------------

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    sys.stderr.write(
        "ERROR: pyyaml is required. Install with:\n"
        "    python -m pip install pyyaml\n"
    )
    sys.exit(69)

try:
    from pydantic import (
        BaseModel,
        ConfigDict,
        Field,
        ValidationError,
        field_validator,
        model_validator,
    )
except ImportError:
    sys.stderr.write(
        "ERROR: pydantic v2 is required. Install with:\n"
        "    python -m pip install 'pydantic>=2.7,<3'\n"
    )
    sys.exit(69)


# ============================================================================
# Constants
# ============================================================================

VERSION = "0.1.0"
TAGLINE = "Built to help xAI and Grok win."
SPEC_VERSION = "2.15"
ACCEPTED_VERSIONS = ("2.14", "2.15")

KIND_VALUES = (
    "agent",
    "finance-dashboard",
    "alpha-engine",
    "creator-payout-optimizer",
    "vision-analyzer",
    "super-agent",
    "x-native",
    "creator-template",
)

KindLiteral = Literal[
    "agent",
    "finance-dashboard",
    "alpha-engine",
    "creator-payout-optimizer",
    "vision-analyzer",
    "super-agent",
    "x-native",
    "creator-template",
]

NAME_PATTERN = r"^[a-z][a-z0-9-]*$"
TOOL_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


# ============================================================================
# Pydantic models — mirror every section of spec/v2.15/grok-agent.yaml
# ============================================================================

# Default config: forbid unknown keys so typos surface early. Sections override
# this only where explicitly justified (schema_meta accepts evolving docs).
_strict = ConfigDict(extra="forbid")


class SchemaMeta(BaseModel):
    """Optional documentation header — only the canonical spec file declares this.
    User manifests typically omit it. Tolerant of evolving fields."""
    spec_version: Optional[str] = None
    spec_release_date: Optional[str] = None
    backwards_compatible_with: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    positioning: Optional[str] = None
    license: Optional[str] = None
    pydantic_module: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class Metadata(BaseModel):
    display_name: Optional[str] = None
    tagline: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    icon: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    language: str = "en"
    created: Optional[str] = None
    updated: Optional[str] = None

    model_config = _strict


class Install(BaseModel):
    one_click: bool = False
    install_command: Optional[str] = None
    post_url: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)

    model_config = _strict


class Windows(BaseModel):
    launcher: Optional[str] = None
    appdata_folder: Optional[str] = None
    config_folder: Optional[str] = None
    cache_folder: Optional[str] = None
    log_folder: Optional[str] = None
    defender_exclusion_recommended: bool = False
    registry_keys: List[str] = Field(default_factory=list)
    min_powershell_version: str = "5.1"
    requires_admin: bool = False
    chrome_only: bool = True
    no_install_dependencies: List[str] = Field(default_factory=list)

    model_config = _strict

    @model_validator(mode="after")
    def _admin_must_be_justified(self) -> "Windows":
        # The Hard Six: agents must run without admin. Surface a hard error
        # so anyone trying to flip this has to do it knowingly upstream.
        if self.requires_admin:
            raise ValueError(
                "windows.requires_admin must be false — agents must run without admin"
            )
        return self


class Grok(BaseModel):
    model: str = "grok-4.3"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, gt=0)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    system_prompt_file: Optional[str] = None
    user_template_file: Optional[str] = None
    tool_calling: bool = True
    vision: bool = False
    streaming: bool = True
    fallback_model: Optional[str] = None

    model_config = _strict


class ToolApi(BaseModel):
    url: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    auth: Literal["none", "bearer", "basic", "api_key", "oauth2"] = "none"
    env_var: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    query: Dict[str, str] = Field(default_factory=dict)
    rate_limit: Optional[int] = Field(default=None, ge=0)
    cache_ttl_seconds: int = Field(default=0, ge=0)
    retry: Optional[Dict[str, Any]] = None

    model_config = _strict


class ToolServer(BaseModel):
    command: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    transport: Literal["stdio", "http"] = "stdio"

    model_config = _strict


class ToolParameters(BaseModel):
    # The YAML key is `schema:` — alias avoids shadowing Pydantic's BaseModel.schema.
    json_schema: Dict[str, Any] = Field(default_factory=dict, alias="schema")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Tool(BaseModel):
    name: str = Field(..., pattern=TOOL_NAME_PATTERN)
    type: Literal["public_api", "local_function", "mcp_server"]
    description: str = Field(..., min_length=1)
    parameters: ToolParameters
    api: Optional[ToolApi] = None
    module: Optional[str] = None
    function: Optional[str] = None
    server: Optional[ToolServer] = None

    model_config = _strict

    @model_validator(mode="after")
    def _type_consistency(self) -> "Tool":
        if self.type == "public_api" and self.api is None:
            raise ValueError(
                f"tools[].api is required when type='public_api' (tool '{self.name}')"
            )
        if self.type == "local_function" and (not self.module or not self.function):
            raise ValueError(
                f"tools[].module and tools[].function are required when "
                f"type='local_function' (tool '{self.name}')"
            )
        if self.type == "mcp_server" and self.server is None:
            raise ValueError(
                f"tools[].server is required when type='mcp_server' (tool '{self.name}')"
            )
        return self


class PublicApi(BaseModel):
    name: str
    base_url: str
    auth_env_var: Optional[str] = None
    auth: Optional[Literal["none", "bearer", "basic", "api_key", "oauth2"]] = None
    free_tier_quota: Optional[str] = None
    rate_limit: Optional[int] = Field(default=None, ge=0)
    privacy: str = "no_pii_sent"

    model_config = _strict


class MultiAgent(BaseModel):
    role: Literal["orchestrator", "worker", "observer"] = "worker"
    delegates_to: List[str] = Field(default_factory=list)
    shared_memory: Optional[str] = None
    message_bus: Optional[str] = None
    max_concurrent_workers: int = Field(default=4, ge=1)

    model_config = _strict


class RealTimeX(BaseModel):
    enabled: bool = False
    consent_required: bool = True
    triggers: List[Literal["mention", "dm", "schedule", "cashtag_change"]] = Field(
        default_factory=list
    )
    schedule_cron: Optional[str] = None
    cashtag_threshold_pct: Optional[float] = Field(default=None, ge=0.0)
    watched_cashtags: List[str] = Field(default_factory=list)
    posts: bool = False
    reply_only: bool = True
    max_posts_per_day: int = Field(default=10, ge=0)

    model_config = _strict

    @model_validator(mode="after")
    def _posting_requires_consent(self) -> "RealTimeX":
        if self.posts and not self.consent_required:
            raise ValueError(
                "real_time_x.posts=true requires real_time_x.consent_required=true"
            )
        return self


class VectorStore(BaseModel):
    backend: Literal["qdrant", "chroma", "pgvector"] = "qdrant"
    url: Optional[str] = None
    collection: Optional[str] = None

    model_config = _strict


class Memory(BaseModel):
    enabled: bool = False
    provider: Literal["mem0", "qdrant", "sqlite", "in_memory"] = "in_memory"
    vector_store: Optional[VectorStore] = None
    episodic: bool = True
    semantic: bool = True
    procedural: bool = False
    retention_days: int = Field(default=365, ge=0)
    encryption_at_rest: bool = True

    model_config = _strict


class LangfuseConfig(BaseModel):
    enabled: bool = False
    public_key_env_var: Optional[str] = None
    secret_key_env_var: Optional[str] = None
    host: str = "https://cloud.langfuse.com"

    model_config = _strict


class Provenance(BaseModel):
    enabled: bool = False
    log_path: Optional[str] = None
    langfuse: Optional[LangfuseConfig] = None
    cite_sources: bool = True
    versioned_synthesis: bool = False
    contradiction_detection: bool = False

    model_config = _strict


class Constitution(BaseModel):
    rules: List[str] = Field(..., min_length=1)
    consent_gates: List[str] = Field(default_factory=list)
    hard_refusals: List[str] = Field(default_factory=list)

    model_config = _strict


class CostLimits(BaseModel):
    usd_per_session_max: float = Field(default=1.00, ge=0.0)
    usd_per_day_max: float = Field(default=5.00, ge=0.0)
    tokens_per_session_max: int = Field(default=200000, ge=0)
    api_calls_per_session_max: int = Field(default=500, ge=0)

    model_config = _strict


class HumanInTheLoop(BaseModel):
    enabled: bool = True
    confirm_before: List[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, ge=0)

    model_config = _strict


class Disclaimers(BaseModel):
    not_financial_advice: bool = False
    not_tax_advice: bool = False
    real_world_action_consent: bool = False

    model_config = _strict


class Safety(BaseModel):
    pii_handling: Literal["local-only", "redacted-cloud", "none"] = "local-only"
    data_retention_days: int = Field(default=365, ge=0)
    scanner_severity_floor: Literal["info", "warn", "error"] = "warn"
    forbidden_actions: List[str] = Field(default_factory=list)
    cost_limits: Optional[CostLimits] = None
    human_in_the_loop: Optional[HumanInTheLoop] = None
    disclaimers: Optional[Disclaimers] = None

    model_config = _strict


class PythonDeps(BaseModel):
    version: str = "^3.12"
    packages: List[str] = Field(default_factory=list)

    model_config = _strict


class Dependencies(BaseModel):
    python: Optional[PythonDeps] = None
    system: List[str] = Field(default_factory=list)
    apis_required: List[str] = Field(default_factory=list)

    model_config = _strict


class PromptfooConfig(BaseModel):
    enabled: bool = False
    config: Optional[str] = None

    model_config = _strict


class DeepEvalConfig(BaseModel):
    enabled: bool = False
    suite: Optional[str] = None

    model_config = _strict


class Evaluation(BaseModel):
    enabled: bool = False
    promptfoo: Optional[PromptfooConfig] = None
    deepeval: Optional[DeepEvalConfig] = None
    langfuse_traces: bool = False
    weekly_loop: bool = False

    model_config = _strict


# ----------------------------------------------------------------------------
# Root model
# ----------------------------------------------------------------------------


class GrokAgentManifest(BaseModel):
    """Root v2.15 manifest. Mirrors spec/v2.15/grok-agent.yaml.

    Backwards-compat: any v2.14 manifest validates as v2.15 unchanged.
    """

    # Optional documentation header (only the canonical spec file declares it).
    schema_meta: Optional[SchemaMeta] = None

    # REQUIRED top-level fields
    version: str = Field(...)
    kind: KindLiteral
    name: str = Field(..., pattern=NAME_PATTERN)
    description: str = Field(..., min_length=10)
    author: str = Field(..., min_length=1)
    license: Literal["Apache-2.0"]

    # Optional sections
    metadata: Optional[Metadata] = None
    install: Optional[Install] = None
    windows: Optional[Windows] = None
    grok: Optional[Grok] = None
    tools: List[Tool] = Field(default_factory=list)
    public_apis: List[PublicApi] = Field(default_factory=list)
    multi_agent: Optional[MultiAgent] = None
    real_time_x: Optional[RealTimeX] = None
    memory: Optional[Memory] = None
    provenance: Optional[Provenance] = None
    constitution: Optional[Constitution] = None
    safety: Optional[Safety] = None
    dependencies: Optional[Dependencies] = None
    evaluation: Optional[Evaluation] = None

    model_config = _strict

    @field_validator("version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in ACCEPTED_VERSIONS:
            raise ValueError(
                f"version must be one of {ACCEPTED_VERSIONS}, got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def _kind_consistency(self) -> "GrokAgentManifest":
        # super-agent kind must declare a constitution
        if self.kind == "super-agent" and self.constitution is None:
            raise ValueError(
                "kind='super-agent' requires a 'constitution:' section"
            )
        # vision-analyzer kind should set grok.vision=true if grok is declared
        if (
            self.kind == "vision-analyzer"
            and self.grok is not None
            and not self.grok.vision
        ):
            raise ValueError(
                "kind='vision-analyzer' requires grok.vision=true"
            )
        return self


# ============================================================================
# Validation entry point
# ============================================================================


def _resolve_manifest_path(p: Path) -> Path:
    """If `p` is a folder, resolve to <folder>/grok-agent.yaml."""
    if p.is_dir():
        candidate = p / "grok-agent.yaml"
        if not candidate.is_file():
            raise FileNotFoundError(
                f"No grok-agent.yaml in folder: {p}"
            )
        return candidate
    return p


def validate_manifest_file(path: Path) -> GrokAgentManifest:
    """Load + parse + validate. Raises on error."""
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    text = path.read_text(encoding="utf-8-sig")  # tolerate UTF-8 BOM
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error: {e}")
    if not isinstance(data, dict):
        raise ValueError(
            f"Manifest must be a YAML mapping at the top level, got {type(data).__name__}"
        )
    return GrokAgentManifest.model_validate(data)


def _format_validation_error(err: ValidationError, manifest_path: Path) -> str:
    """Render Pydantic errors as a human-readable bullet list."""
    lines = [f"X  Validation failed for {manifest_path}:"]
    for e in err.errors():
        loc = ".".join(str(p) for p in e.get("loc", ()))
        msg = e.get("msg", "invalid")
        typ = e.get("type", "")
        lines.append(f"   - {loc}: {msg}  [{typ}]")
    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================


def cmd_validate(args: argparse.Namespace) -> int:
    raw = Path(args.path).expanduser()
    try:
        path = _resolve_manifest_path(raw)
    except FileNotFoundError as e:
        sys.stderr.write(f"X  {e}\n")
        return 66
    if not args.quiet:
        sys.stdout.write(f"-> Validating: {path}\n")

    try:
        manifest = validate_manifest_file(path)
    except FileNotFoundError as e:
        sys.stderr.write(f"X  {e}\n")
        return 66
    except ValidationError as e:
        sys.stderr.write(_format_validation_error(e, path) + "\n")
        return 65
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 65
    except Exception as e:  # last-resort safety net
        sys.stderr.write(f"X  Internal error: {e}\n")
        return 70

    if not args.quiet:
        sys.stdout.write(
            f"OK Valid v{SPEC_VERSION} manifest: "
            f"name='{manifest.name}' kind='{manifest.kind}' version='{manifest.version}'\n"
        )
    return 0


def cmd_info(_args: argparse.Namespace) -> int:
    sys.stdout.write(
        f"grok-agent.py v{VERSION}\n"
        f"Spec version: v{SPEC_VERSION} (accepts {', '.join(ACCEPTED_VERSIONS)})\n"
        f"Kinds: {', '.join(KIND_VALUES)}\n"
        f"{TAGLINE}\n"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok-agent",
        description=(
            f"Grok Agent OS — Pydantic v{SPEC_VERSION} manifest validator. {TAGLINE}"
        ),
        epilog=(
            "Examples:\n"
            "  python cli/grok-agent.py validate path/to/grok-agent.yaml\n"
            "  python cli/grok-agent.py validate path/to/agent-folder\n"
            "  python cli/grok-agent.py info\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"grok-agent.py {VERSION} (spec v{SPEC_VERSION})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser(
        "validate",
        help="Validate a grok-agent.yaml manifest against the v2.15 schema.",
    )
    p_val.add_argument(
        "path",
        type=str,
        help="Path to grok-agent.yaml or to a folder that contains it.",
    )
    p_val.add_argument(
        "--quiet",
        action="store_true",
        help="Print only on failure (machine-readable mode).",
    )
    p_val.set_defaults(func=cmd_validate)

    p_info = sub.add_parser(
        "info", help="Print version / kind / spec info and exit."
    )
    p_info.set_defaults(func=cmd_info)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
