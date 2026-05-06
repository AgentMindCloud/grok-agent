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
Grok Agent OS — Safety Scanner.

Built for xAI, X, Grok and the ecosystem community. ❤️

Layered safety enforcement on top of the v2.15 schema validator:
the schema (cli/grok-agent.py) checks STRUCTURE; this scanner checks the
Agent Constitution (safety/constitution.md) — the rules about what an agent
is allowed to *do*.

Severity model:
    info  — recommended-but-not-required (exit 0)
    warn  — should-fix (exit 0; non-blocking)
    error — Constitution violation; install / merge blocked (exit 1)

Usage:
    python safety/scanner.py scan path/to/grok-agent.yaml
    python safety/scanner.py scan path/to/agent-folder
    python safety/scanner.py scan-all templates/
    python safety/scanner.py scan path/to/manifest.yaml --json
    python safety/scanner.py scan path/to/manifest.yaml --severity-floor warn

Designed to be callable from cli/grok-agent.ps1 (pre-install) and from
.github/workflows/validate.yml (CI). The `--json` flag emits one JSON
object per line so PowerShell + GH Actions can parse findings easily.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    sys.stderr.write(
        "ERROR: pyyaml is required. Install with:\n"
        "    python -m pip install pyyaml\n"
    )
    sys.exit(69)


# ============================================================================
# Constants
# ============================================================================

VERSION = "0.1.0"
TAGLINE = "Built for xAI, X, Grok and the ecosystem community. ❤️"
CONSTITUTION_VERSION = "1.0"

SEVERITIES = ("info", "warn", "error")
SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}

# Kinds that should declare not_financial_advice
FINANCE_KINDS = {
    "finance-dashboard",
    "alpha-engine",
    "creator-payout-optimizer",
}

# Kinds that may need tax disclaimers
TAX_KINDS = {
    "finance-dashboard",
    "creator-payout-optimizer",
}

# Mandatory consent gates per the Constitution (Article II)
MANDATORY_CONSENT_GATES_FOR_REAL_WORLD = {
    "publish_to_x",
    "send_dm",
    "move_funds",
    "pay_real_money",
    "modify_local_files_outside_appdata",
}


# ============================================================================
# Finding model
# ============================================================================


@dataclass
class Finding:
    severity: str  # 'info' | 'warn' | 'error'
    code: str
    message: str
    location: str = ""  # e.g. "windows.requires_admin"
    article: str = ""  # which Constitution article (e.g. "I.1", "V.1")

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Bad severity: {self.severity}")

    def to_line(self) -> str:
        sev = self.severity.upper().ljust(5)
        loc = f" ({self.location})" if self.location else ""
        art = f" [Const. Art. {self.article}]" if self.article else ""
        return f"  {sev} {self.code}: {self.message}{loc}{art}"

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    manifest_path: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def max_severity(self) -> str:
        if not self.findings:
            return "info"
        return max(self.findings, key=lambda f: SEVERITY_RANK[f.severity]).severity

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self.findings)

    def filter_by_floor(self, floor: str) -> List[Finding]:
        threshold = SEVERITY_RANK[floor]
        return [f for f in self.findings if SEVERITY_RANK[f.severity] >= threshold]


# ============================================================================
# Check framework — each check is a function that returns a list[Finding]
# ============================================================================


CheckFn = Callable[[Dict[str, Any]], List[Finding]]
CHECKS: Dict[str, CheckFn] = {}


def register(name: str) -> Callable[[CheckFn], CheckFn]:
    def deco(fn: CheckFn) -> CheckFn:
        CHECKS[name] = fn
        return fn
    return deco


def _get(d: Dict[str, Any], dotted: str, default: Any = None) -> Any:
    """Safely traverse a nested dict by dotted path."""
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


# ============================================================================
# Bridge Registry — Article VII enforcement
# ============================================================================

_BRIDGES_REGISTRY: Optional[Dict[str, Any]] = None
_BRIDGES_REGISTRY_PATHS = [
    Path(__file__).parent.parent / "templates" / "super-agents" / "_bridges" / "registry.json",
    Path.cwd() / "templates" / "super-agents" / "_bridges" / "registry.json",
]


def _load_bridges_registry() -> Optional[Dict[str, Any]]:
    """Load templates/super-agents/_bridges/registry.json (lazy + cached).

    Searches paths relative to scanner.py and to cwd. Returns None when the
    registry file is missing — callers MUST treat that as graceful skip
    rather than a hard error so the scanner stays usable in stripped repos.
    """
    global _BRIDGES_REGISTRY
    if _BRIDGES_REGISTRY is not None:
        return _BRIDGES_REGISTRY
    for path in _BRIDGES_REGISTRY_PATHS:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    _BRIDGES_REGISTRY = json.load(fh)
                return _BRIDGES_REGISTRY
            except (json.JSONDecodeError, OSError):
                continue
    return None


# ============================================================================
# Checks — Article I: Universal Rules
# ============================================================================


@register("I.1-license")
def check_license(m: Dict[str, Any]) -> List[Finding]:
    lic = m.get("license")
    if lic is None:
        return [Finding("error", "LIC-001", "license is required and must be 'Apache-2.0'", "license", "I.1")]
    if lic != "Apache-2.0":
        return [Finding("error", "LIC-002", f"license must be 'Apache-2.0', got '{lic}'", "license", "I.1")]
    return []


@register("I.3-windows-requires-admin")
def check_no_admin(m: Dict[str, Any]) -> List[Finding]:
    if _get(m, "windows.requires_admin", False):
        return [Finding(
            "error", "WIN-001",
            "windows.requires_admin must be false — agents must run without admin",
            "windows.requires_admin", "I.3",
        )]
    return []


@register("I.4-version")
def check_version(m: Dict[str, Any]) -> List[Finding]:
    v = m.get("version")
    if v not in ("2.14", "2.15"):
        return [Finding("error", "VER-001", f"version must be '2.14' or '2.15', got {v!r}", "version", "I.4")]
    if v == "2.14":
        return [Finding("info", "VER-002", "version is v2.14 — accepted, but consider upgrading to v2.15", "version", "I.4")]
    return []


# ============================================================================
# Checks — Article II: Consent Gates
# ============================================================================


@register("II.posts-consent")
def check_posts_require_consent(m: Dict[str, Any]) -> List[Finding]:
    rt = m.get("real_time_x") or {}
    if rt.get("posts") and not rt.get("consent_required", True):
        return [Finding(
            "error", "CG-001",
            "real_time_x.posts=true requires real_time_x.consent_required=true",
            "real_time_x.consent_required", "II",
        )]
    return []


@register("II.publish-gate")
def check_publish_consent_gate(m: Dict[str, Any]) -> List[Finding]:
    rt = m.get("real_time_x") or {}
    gates = _get(m, "constitution.consent_gates", []) or []
    if rt.get("posts") and "publish_to_x" not in gates:
        return [Finding(
            "error", "CG-002",
            "real_time_x.posts=true requires 'publish_to_x' in constitution.consent_gates",
            "constitution.consent_gates", "II",
        )]
    return []


# ============================================================================
# Checks — Article III: Hard Refusals
# ============================================================================


_HARD_REFUSAL_BLACKLIST = {
    "scrape_authenticated_x_content",
    "impersonate_user_identity",
    "bypass_safety_scanner",
    "exfiltrate_user_data",
}


@register("III.no-forbidden-actions-flipped")
def check_forbidden_not_silently_allowed(m: Dict[str, Any]) -> List[Finding]:
    """If a manifest enumerates `safety.forbidden_actions`, none of the
    constitution.consent_gates may overlap (you can't 'unblock' a refusal
    via a consent gate)."""
    findings: List[Finding] = []
    forbidden = set(_get(m, "safety.forbidden_actions", []) or [])
    gates = set(_get(m, "constitution.consent_gates", []) or [])
    overlap = forbidden & gates
    for action in overlap:
        findings.append(Finding(
            "error", "HR-001",
            f"action '{action}' is in safety.forbidden_actions AND constitution.consent_gates — "
            f"a forbidden action cannot be re-enabled via consent",
            "constitution.consent_gates", "III",
        ))
    return findings


# ============================================================================
# Checks — Article IV: Provenance & Truth
# ============================================================================


@register("IV.super-agent-provenance")
def check_super_agent_provenance(m: Dict[str, Any]) -> List[Finding]:
    if m.get("kind") != "super-agent":
        return []
    if not _get(m, "provenance.enabled", False):
        return [Finding(
            "error", "PRV-001",
            "kind='super-agent' requires provenance.enabled=true",
            "provenance.enabled", "IV",
        )]
    return []


@register("IV.super-agent-constitution")
def check_super_agent_constitution(m: Dict[str, Any]) -> List[Finding]:
    if m.get("kind") != "super-agent":
        return []
    if not m.get("constitution"):
        return [Finding(
            "error", "PRV-002",
            "kind='super-agent' requires a constitution: section",
            "constitution", "IV",
        )]
    rules = _get(m, "constitution.rules", []) or []
    if not rules:
        return [Finding(
            "error", "PRV-003",
            "constitution.rules must contain at least one rule",
            "constitution.rules", "IV",
        )]
    return []


# ============================================================================
# Checks — Article V: Disclaimers
# ============================================================================


@register("V.1-finance-disclaimer")
def check_finance_disclaimer(m: Dict[str, Any]) -> List[Finding]:
    kind = m.get("kind")
    if kind not in FINANCE_KINDS:
        return []
    if not _get(m, "safety.disclaimers.not_financial_advice", False):
        return [Finding(
            "error", "DSC-001",
            f"kind='{kind}' requires safety.disclaimers.not_financial_advice=true",
            "safety.disclaimers.not_financial_advice", "V.1",
        )]
    return []


@register("V.2-tax-disclaimer")
def check_tax_disclaimer(m: Dict[str, Any]) -> List[Finding]:
    kind = m.get("kind")
    if kind not in TAX_KINDS:
        return []
    if not _get(m, "safety.disclaimers.not_tax_advice", False):
        return [Finding(
            "warn", "DSC-002",
            f"kind='{kind}' should set safety.disclaimers.not_tax_advice=true if tax export is shipped",
            "safety.disclaimers.not_tax_advice", "V.2",
        )]
    return []


@register("V.3-real-world-action-disclaimer")
def check_real_world_disclaimer(m: Dict[str, Any]) -> List[Finding]:
    """Agents that take real-world actions must disclose it."""
    gates = set(_get(m, "constitution.consent_gates", []) or [])
    has_real_world = bool(gates & MANDATORY_CONSENT_GATES_FOR_REAL_WORLD)
    if not has_real_world:
        return []
    if not _get(m, "safety.disclaimers.real_world_action_consent", False):
        return [Finding(
            "warn", "DSC-003",
            "agent declares real-world consent gates; "
            "set safety.disclaimers.real_world_action_consent=true",
            "safety.disclaimers.real_world_action_consent", "V.3",
        )]
    return []


# ============================================================================
# Checks — Article VI: Cost Limits & HITL
# ============================================================================


@register("VI.1-cost-limits-for-finance-and-super-agent")
def check_cost_limits(m: Dict[str, Any]) -> List[Finding]:
    kind = m.get("kind")
    needs_cost = (kind in FINANCE_KINDS) or (kind == "super-agent")
    if not needs_cost:
        return []
    cl = _get(m, "safety.cost_limits")
    if cl is None:
        return [Finding(
            "warn", "COST-001",
            f"kind='{kind}' should declare safety.cost_limits with usd_per_session_max, usd_per_day_max, and tokens_per_session_max",
            "safety.cost_limits", "VI.1",
        )]
    return []


@register("VI.2-hitl-for-consent-gated-agents")
def check_hitl_when_consent_gates_declared(m: Dict[str, Any]) -> List[Finding]:
    gates = _get(m, "constitution.consent_gates", []) or []
    if not gates:
        return []
    hitl = _get(m, "safety.human_in_the_loop")
    if hitl is None:
        return [Finding(
            "warn", "HITL-001",
            "agent declares consent_gates; safety.human_in_the_loop should be configured",
            "safety.human_in_the_loop", "VI.2",
        )]
    if hitl.get("enabled") is False:
        return [Finding(
            "error", "HITL-002",
            "consent_gates declared but human_in_the_loop.enabled=false",
            "safety.human_in_the_loop.enabled", "VI.2",
        )]
    return []


# ============================================================================
# Checks — Article VII: Local-First & Privacy-First
# ============================================================================


@register("VII.pii-default")
def check_pii_local_only(m: Dict[str, Any]) -> List[Finding]:
    kind = m.get("kind")
    pii = _get(m, "safety.pii_handling", "local-only")
    if pii == "none" and kind in (FINANCE_KINDS | {"vision-analyzer", "super-agent"}):
        return [Finding(
            "warn", "PII-001",
            f"safety.pii_handling='none' is permissive for kind='{kind}'; consider 'local-only' or 'redacted-cloud'",
            "safety.pii_handling", "VII",
        )]
    return []


# ============================================================================
# Checks — Article I.2: xAI ecosystem positioning
# ============================================================================


_FORBIDDEN_POSITIONING_TERMS = (
    "compete with xai",
    "replace xai",
    "alternative to grok",
    "replacement for grok",
    "anti-xai",
)


@register("I.2-xai-positioning")
def check_xai_positioning(m: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    desc = (m.get("description") or "").lower()
    tagline = (_get(m, "metadata.tagline") or "").lower()
    blob = desc + " | " + tagline
    for term in _FORBIDDEN_POSITIONING_TERMS:
        if term in blob:
            findings.append(Finding(
                "error", "POS-001",
                f"description / metadata.tagline contains forbidden positioning '{term}' — "
                f"agents must position as ecosystem allies, never competitors",
                "description", "I.2",
            ))
    return findings


# ============================================================================
# Additional Article III: Hard Refusals — provenance integrity
# ============================================================================


@register("III.cite-sources-for-super-agent")
def check_super_agent_cite_sources(m: Dict[str, Any]) -> List[Finding]:
    if m.get("kind") != "super-agent":
        return []
    if not _get(m, "provenance.cite_sources", False):
        return [Finding(
            "error", "HR-002",
            "super-agent must set provenance.cite_sources=true (Article III — no claim without a source)",
            "provenance.cite_sources", "III",
        )]
    return []


@register("III.append-only-provenance")
def check_append_only_provenance(m: Dict[str, Any]) -> List[Finding]:
    if not _get(m, "provenance.enabled", False):
        return []
    if _get(m, "provenance.append_only") is False:
        return [Finding(
            "error", "HR-003",
            "provenance.enabled=true requires provenance.append_only=true (Article III — never mutate provenance)",
            "provenance.append_only", "III",
        )]
    return []


@register("III.bridges-min-count")
def check_bridges_min_count(m: Dict[str, Any]) -> List[Finding]:
    if m.get("kind") != "super-agent":
        return []
    bridges = m.get("bridges")
    if not isinstance(bridges, dict):
        return []
    min_count = bridges.get("min_count")
    if isinstance(min_count, int) and min_count < 1:
        return [Finding(
            "warn", "HR-004",
            "bridges.min_count should be >= 1 for super-agents (Article III — synthesis must connect to others)",
            "bridges.min_count", "III",
        )]
    return []


@register("III.contradiction-detection")
def check_contradiction_detection(m: Dict[str, Any]) -> List[Finding]:
    if m.get("kind") != "super-agent":
        return []
    if not _get(m, "provenance.enabled", False):
        return []
    if _get(m, "provenance.contradiction_detection") is False:
        return [Finding(
            "warn", "HR-005",
            "super-agent with provenance should set provenance.contradiction_detection=true",
            "provenance.contradiction_detection", "III",
        )]
    return []


# ============================================================================
# Additional Article VII: Local-First & Privacy-First
# ============================================================================


_ABSOLUTE_DRIVE_RE = ("C:\\", "D:\\", "E:\\", "/usr/", "/etc/", "/var/")
_TRACKER_DOMAINS = (
    "google-analytics.com",
    "googletagmanager.com",
    "mixpanel.com",
    "segment.io",
    "amplitude.com",
)


@register("VII.appdata-paths-only")
def check_appdata_paths_only(m: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    windows = m.get("windows") or {}
    if not isinstance(windows, dict):
        return []
    for key, val in windows.items():
        if not isinstance(val, str):
            continue
        for prefix in _ABSOLUTE_DRIVE_RE:
            if val.startswith(prefix):
                findings.append(Finding(
                    "error", "PII-002",
                    f"windows.{key}='{val}' uses an absolute drive path; use a relative path under $env:LOCALAPPDATA",
                    f"windows.{key}", "VII",
                ))
    return findings


@register("VII.encryption-at-rest")
def check_encryption_at_rest(m: Dict[str, Any]) -> List[Finding]:
    if not _get(m, "memory.enabled", False):
        return []
    pii = _get(m, "safety.pii_handling", "local-only")
    if pii == "none":
        return []
    if _get(m, "memory.encryption_at_rest") is False:
        return [Finding(
            "warn", "PII-003",
            "memory.enabled=true with pii_handling != 'none' should set memory.encryption_at_rest=true",
            "memory.encryption_at_rest", "VII",
        )]
    return []


@register("VII.data-retention-required")
def check_data_retention(m: Dict[str, Any]) -> List[Finding]:
    kind = m.get("kind")
    needs_retention = (kind in FINANCE_KINDS) or (kind == "super-agent")
    if not needs_retention:
        return []
    if _get(m, "safety.data_retention_days") is None:
        return [Finding(
            "warn", "PII-004",
            f"kind='{kind}' should declare safety.data_retention_days (e.g. 90 or 365)",
            "safety.data_retention_days", "VII",
        )]
    return []


@register("VII.no-trackers")
def check_no_trackers(m: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    blob = json.dumps(m, default=str).lower()
    for tracker in _TRACKER_DOMAINS:
        if tracker in blob:
            findings.append(Finding(
                "error", "PII-005",
                f"manifest references third-party tracker '{tracker}'; "
                f"agents must not bundle telemetry by default (Article VII)",
                "manifest", "VII",
            ))
    return findings


# ============================================================================
# Additional Article II: Consent Gates — confirm_before completeness
# ============================================================================


_REAL_WORLD_VERBS = ("publish_", "send_", "move_", "pay_", "delete_", "modify_")


@register("II.action-gate-confirm-list")
def check_action_gate_confirm_list(m: Dict[str, Any]) -> List[Finding]:
    gates = _get(m, "constitution.consent_gates", []) or []
    confirm_before = _get(m, "safety.human_in_the_loop.confirm_before", []) or []
    findings: List[Finding] = []
    for gate in gates:
        if not isinstance(gate, str):
            continue
        if any(gate.startswith(v) for v in _REAL_WORLD_VERBS):
            if gate not in confirm_before:
                findings.append(Finding(
                    "warn", "CG-003",
                    f"consent gate '{gate}' looks like a real-world action; "
                    f"add it to safety.human_in_the_loop.confirm_before",
                    "safety.human_in_the_loop.confirm_before", "II",
                ))
    return findings


# ============================================================================
# Additional Article VIII: Audit & Self-Improvement
# ============================================================================


@register("VIII.scanner-severity-floor")
def check_scanner_severity_floor(m: Dict[str, Any]) -> List[Finding]:
    floor = _get(m, "safety.scanner_severity_floor")
    if floor is None:
        return [Finding(
            "info", "AUD-001",
            "safety.scanner_severity_floor is not declared; defaulting to 'warn' is recommended",
            "safety.scanner_severity_floor", "VIII",
        )]
    if floor not in SEVERITIES:
        return [Finding(
            "error", "AUD-002",
            f"safety.scanner_severity_floor='{floor}' must be one of {SEVERITIES}",
            "safety.scanner_severity_floor", "VIII",
        )]
    return []


@register("VIII.severity-floor-not-info")
def check_severity_floor_not_info(m: Dict[str, Any]) -> List[Finding]:
    kind = m.get("kind")
    if kind not in (FINANCE_KINDS | {"super-agent"}):
        return []
    floor = _get(m, "safety.scanner_severity_floor")
    if floor == "info":
        return [Finding(
            "warn", "AUD-003",
            f"kind='{kind}' should not run with scanner_severity_floor='info' "
            f"(use 'warn' or 'error' to surface real issues)",
            "safety.scanner_severity_floor", "VIII",
        )]
    return []


# ============================================================================
# Additional Article X: Local-first storage
# ============================================================================


@register("X.local-first-storage")
def check_local_first_storage(m: Dict[str, Any]) -> List[Finding]:
    appdata = _get(m, "windows.appdata_folder")
    if appdata is None:
        return []
    if not isinstance(appdata, str):
        return []
    if not appdata.startswith("grok-agent/"):
        return [Finding(
            "warn", "LF-001",
            f"windows.appdata_folder='{appdata}' should start with 'grok-agent/' "
            f"to keep all per-user data under one umbrella",
            "windows.appdata_folder", "X",
        )]
    return []


# ============================================================================
# Article VII — Bridge Registry checks
# ============================================================================


@register("VII.bridge-registry-alignment")
def check_bridge_registry_alignment(m: Dict[str, Any]) -> List[Finding]:
    """Verify a super-agent's bridges.links exist in the registry's
    citations_to block (or fall outside the super-agent set, in which case
    they are flagged as info — registry only tracks super-agents)."""
    if m.get("kind") != "super-agent":
        return []
    registry = _load_bridges_registry()
    if registry is None:
        return [Finding(
            "info", "BR-001",
            "bridge registry not found at templates/super-agents/_bridges/registry.json; "
            "skipping bridge alignment check",
            "bridges", "VII",
        )]
    name = m.get("name")
    if not isinstance(name, str):
        return []
    agent_entry = (registry.get("agents") or {}).get(name)
    if agent_entry is None:
        return [Finding(
            "warn", "BR-002",
            f"super-agent '{name}' is not listed in the bridge registry; "
            f"please add it to templates/super-agents/_bridges/registry.json",
            "name", "VII",
        )]
    findings: List[Finding] = []
    declared_links = _get(m, "bridges.links", []) or []
    if not isinstance(declared_links, list):
        return findings
    citations_to = agent_entry.get("citations_to", {}) or {}
    super_agent_names = set((registry.get("agents") or {}).keys())
    flagships = set(registry.get("flagships") or [])
    lighters = set(registry.get("lighters") or [])
    # Flagships must exactly match the registry (ERROR on mismatch);
    # lighters stay at WARN so the registry can evolve without blocking them.
    if name in flagships:
        mismatch_severity = "error"
    elif name in lighters:
        mismatch_severity = "warn"
    else:
        mismatch_severity = "warn"
    for link in declared_links:
        if not isinstance(link, str):
            continue
        if link in citations_to:
            continue
        if link in super_agent_names:
            findings.append(Finding(
                mismatch_severity, "BR-003",
                f"bridges.links contains super-agent '{link}' but the registry "
                f"does not authorise '{name}' to cite it; "
                f"add it to registry.agents['{name}'].citations_to or remove it from the manifest",
                "bridges.links", "VII",
            ))
        else:
            findings.append(Finding(
                "info", "BR-003b",
                f"bridges.links contains '{link}' which is not a super-agent; "
                f"registry tracks only super-agent citations, so this is informational",
                "bridges.links", "VII",
            ))
    return findings


@register("VII.bridge-reciprocity")
def check_bridge_reciprocity(m: Dict[str, Any]) -> List[Finding]:
    """For each `reciprocal: true` citation, the cited agent must declare a
    matching reverse entry. Citation type and consent gates should match."""
    if m.get("kind") != "super-agent":
        return []
    registry = _load_bridges_registry()
    if registry is None:
        return []
    name = m.get("name")
    if not isinstance(name, str):
        return []
    agent_entry = (registry.get("agents") or {}).get(name)
    if agent_entry is None:
        return []
    findings: List[Finding] = []
    citations_to = agent_entry.get("citations_to", {}) or {}
    for cited_name, citation in citations_to.items():
        if not isinstance(citation, dict):
            continue
        if not citation.get("reciprocal"):
            continue
        cited_entry = (registry.get("agents") or {}).get(cited_name)
        if cited_entry is None:
            findings.append(Finding(
                "error", "BR-005",
                f"'{name}' cites '{cited_name}' as reciprocal=true but '{cited_name}' is missing from the registry",
                "registry", "VII",
            ))
            continue
        reverse = (cited_entry.get("citations_to") or {}).get(name)
        if reverse is None:
            findings.append(Finding(
                "error", "BR-006",
                f"reciprocal citation '{name}' -> '{cited_name}' has no matching reverse entry "
                f"in '{cited_name}'.citations_to['{name}']",
                "registry", "VII",
            ))
            continue
        if citation.get("citation_type") != reverse.get("citation_type"):
            findings.append(Finding(
                "warn", "BR-007",
                f"reciprocal citation_type mismatch between '{name}' <-> '{cited_name}' "
                f"({citation.get('citation_type')} vs {reverse.get('citation_type')})",
                "registry", "VII",
            ))
    return findings


@register("VII.bridge-transitive-action")
def check_bridge_transitive_action(m: Dict[str, Any]) -> List[Finding]:
    """Action citations must complete inline. If A cites B as `action`, B
    must NOT have any further `action` citations (no A -> B -> C action
    chains). Per the registry's transitive_citation_rules.rule_3."""
    if m.get("kind") != "super-agent":
        return []
    registry = _load_bridges_registry()
    if registry is None:
        return []
    name = m.get("name")
    if not isinstance(name, str):
        return []
    agent_entry = (registry.get("agents") or {}).get(name)
    if agent_entry is None:
        return []
    findings: List[Finding] = []
    citations_to = agent_entry.get("citations_to", {}) or {}
    for cited_name, citation in citations_to.items():
        if not isinstance(citation, dict):
            continue
        if citation.get("citation_type") != "action":
            continue
        cited_entry = (registry.get("agents") or {}).get(cited_name)
        if cited_entry is None:
            continue
        for next_name, next_citation in (cited_entry.get("citations_to") or {}).items():
            if isinstance(next_citation, dict) and next_citation.get("citation_type") == "action":
                findings.append(Finding(
                    "error", "BR-009",
                    f"action chain '{name}' -> '{cited_name}' -> '{next_name}' violates "
                    f"the transitive-action rule (registry rule_3)",
                    "registry", "VII",
                ))
    return findings


@register("VII.bridge-min-count")
def check_bridge_min_count(m: Dict[str, Any]) -> List[Finding]:
    """Verify the manifest's bridges.min_count matches the registry's
    min_bridges entry for this agent."""
    if m.get("kind") != "super-agent":
        return []
    registry = _load_bridges_registry()
    if registry is None:
        return []
    name = m.get("name")
    if not isinstance(name, str):
        return []
    agent_entry = (registry.get("agents") or {}).get(name)
    if agent_entry is None:
        return []
    declared = _get(m, "bridges.min_count")
    registry_min = agent_entry.get("min_bridges")
    if declared is None or registry_min is None:
        return []
    if declared < registry_min:
        return [Finding(
            "warn", "BR-010",
            f"bridges.min_count={declared} below registry.min_bridges={registry_min} for '{name}'",
            "bridges.min_count", "VII",
        )]
    return []


# ============================================================================
# Article VII — Transitive citation enforcement (registry rules 1 & 2)
# ============================================================================


@register("VII.bridge-transitive-synthesis")
def check_bridge_transitive_synthesis(m: Dict[str, Any]) -> List[Finding]:
    """Registry rule_1: Agent A may cite Agent B's synthesis of Agent C
    only when B is authorised to cite C. We treat a chain as
    *transitive* when both edges are reciprocal=true synthesis edges
    (the citation type that re-publishes B's view of C). Such a chain
    means A's manifest must explicitly opt into the transitive flow via
    `bridges.transitive_synthesis_consent: true`. Self-cycles (C == A)
    are excluded — those are already covered by the reciprocity check.
    """
    if m.get("kind") != "super-agent":
        return []
    registry = _load_bridges_registry()
    if registry is None:
        return []
    name = m.get("name")
    if not isinstance(name, str):
        return []
    agents = registry.get("agents") or {}
    agent_entry = agents.get(name)
    if agent_entry is None:
        return []
    consent = bool(_get(m, "bridges.transitive_synthesis_consent", False))
    findings: List[Finding] = []
    seen_chains = set()
    citations_to = agent_entry.get("citations_to", {}) or {}
    for b_name, b_citation in citations_to.items():
        if not isinstance(b_citation, dict):
            continue
        if b_citation.get("citation_type") != "synthesis":
            continue
        if not b_citation.get("reciprocal"):
            continue
        b_entry = agents.get(b_name)
        if b_entry is None:
            continue
        for c_name, c_citation in (b_entry.get("citations_to") or {}).items():
            if not isinstance(c_citation, dict):
                continue
            if c_citation.get("citation_type") != "synthesis":
                continue
            if not c_citation.get("reciprocal"):
                continue
            if c_name == name:
                continue  # cycle back to A — handled by reciprocity check
            chain_key = (b_name, c_name)
            if chain_key in seen_chains:
                continue
            seen_chains.add(chain_key)
            if not consent:
                findings.append(Finding(
                    "error", "BR-011",
                    f"transitive synthesis chain '{name}' -> '{b_name}' -> '{c_name}' "
                    f"requires bridges.transitive_synthesis_consent=true in the manifest "
                    f"(registry rule_1 — no transitive shortcuts without explicit consent)",
                    "bridges.transitive_synthesis_consent", "VII",
                ))
    return findings


@register("VII.bridge-transitive-contradiction")
def check_bridge_transitive_contradiction(m: Dict[str, Any]) -> List[Finding]:
    """Registry rule_2: Contradiction flags are not transitive.
    If A cites synthesis from B, and `narrative-contradiction-detector`
    has raised a contradiction-flag citation toward B, then A risks
    laundering a flagged claim through B's synthesis. To proceed, A
    must declare `bridges.acknowledge_contradiction: true` so the user
    is told the upstream agent has open contradiction flags.
    """
    if m.get("kind") != "super-agent":
        return []
    registry = _load_bridges_registry()
    if registry is None:
        return []
    name = m.get("name")
    if not isinstance(name, str):
        return []
    agents = registry.get("agents") or {}
    agent_entry = agents.get(name)
    if agent_entry is None:
        return []
    ncd_entry = agents.get("narrative-contradiction-detector")
    if ncd_entry is None:
        return []
    flagged_targets = set()
    for target_name, target_citation in (ncd_entry.get("citations_to") or {}).items():
        if not isinstance(target_citation, dict):
            continue
        if target_citation.get("citation_type") == "contradiction-flag":
            flagged_targets.add(target_name)
    if not flagged_targets:
        return []
    acknowledge = bool(_get(m, "bridges.acknowledge_contradiction", False))
    findings: List[Finding] = []
    citations_to = agent_entry.get("citations_to", {}) or {}
    for b_name, b_citation in citations_to.items():
        if not isinstance(b_citation, dict):
            continue
        if b_citation.get("citation_type") != "synthesis":
            continue
        if b_name not in flagged_targets:
            continue
        if name == "narrative-contradiction-detector":
            continue  # NCD is the source of flags; cannot flag itself
        if not acknowledge:
            findings.append(Finding(
                "error", "BR-012",
                f"'{name}' cites synthesis from '{b_name}', and "
                f"'narrative-contradiction-detector' has raised a contradiction-flag "
                f"on '{b_name}'; set bridges.acknowledge_contradiction=true in the "
                f"manifest to surface the open flag (registry rule_2 — contradiction "
                f"flags are not transitive)",
                "bridges.acknowledge_contradiction", "VII",
            ))
    return findings


# ============================================================================
# Article VIII — Forbidden-phrase repo-wide leak detector
# ============================================================================
#
# The Hard Six rules (CLAUDE.md §3) ban a small set of vague phrases from any
# generated prompt or output. This walks the entire repo and flags any
# accidental leak. Governance files that *define* the banned list (CLAUDE.md,
# docs/CONSTRAINTS.md) and a couple of launch threads that quote the list
# inside a verification checklist surround those sections with HTML-comment
# markers `<!-- SCANNER:EXEMPT-START -->` / `<!-- SCANNER:EXEMPT-END -->`.
# The scanner reads those markers at runtime instead of relying on hardcoded
# line numbers, so future edits to the governance files don't silently break
# the whitelist.
#
# `_FORBIDDEN_PHRASE_EXEMPT_FILES` lists the repo-root-relative POSIX paths
# that opt into marker-based exemption. `_get_exempt_ranges()` parses the
# markers on each call.

_FORBIDDEN_PHRASE_EXEMPT_FILES: set = {
    "CLAUDE.md",
    "docs/CONSTRAINTS.md",
    "templates/super-agents/self-evolving-personal-os/X_LAUNCH_THREAD.md",
    "templates/super-agents/cross-reality-action-fabric/X_LAUNCH_THREAD.md",
}

# The scanner's own regex literal references the banned phrases by necessity
# (it has to match them). We can't put HTML-comment markers inside a Python
# source file, so this single line is exempt via a hardcoded fallback in
# `_get_self_exempt_ranges()` below.
_SELF_EXEMPT_FILE = "safety/scanner.py"

_EXEMPT_START_MARKER = "<!-- SCANNER:EXEMPT-START -->"
_EXEMPT_END_MARKER = "<!-- SCANNER:EXEMPT-END -->"

# Pattern matches each banned phrase (case-insensitive). The leading \b on the
# first alternative prevents false positives on words like "fetcher" or
# "etcetera"; the rest are multi-word phrases that are already self-anchoring.
_FORBIDDEN_PHRASES_RE = re.compile(
    r"\betc\.|and so on|anything related to|as you see fit|use your judgment|boilerplate as needed",
    re.IGNORECASE,
)

_FORBIDDEN_PHRASE_SCAN_INCLUDES = (
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".js",
    ".ps1",
    ".tsx",
    ".ts",
)

# Path fragments / filenames to skip outright. Lockfiles and vendored deps
# never need scanning and are full of unrelated tokens.
_FORBIDDEN_PHRASE_SCAN_EXCLUDES = (
    "node_modules/",
    ".git/",
    "LICENSE",
    "package-lock.json",
    "marketplace/package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
)


def _get_self_exempt_ranges() -> List[Tuple[int, int]]:
    """Hardcoded exemption for the scanner's own forbidden-phrase references.

    The forbidden-phrase regex (`_FORBIDDEN_PHRASES_RE`) must reference the
    banned phrases verbatim, and the helper that locates that regex must also
    contain the same token to find it. We can't put HTML-comment markers
    inside a Python source file, so we rescan the scanner at runtime and
    return every line whose content would otherwise trigger a leak finding.
    Single-line ranges are emitted (one per match) so the line count stays
    intuitive (one exempt line per forbidden token).
    """
    here = Path(__file__)
    try:
        text = here.read_text(encoding="utf-8")
    except OSError:
        return []
    ranges: List[Tuple[int, int]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _FORBIDDEN_PHRASES_RE.search(line):
            ranges.append((line_no, line_no))
    return ranges


def _get_exempt_ranges(file_path: Path) -> List[Tuple[int, int]]:
    """Return inclusive (start, end) line ranges marked as exempt in a file.

    Walks the file line-by-line tracking marker state. Lines containing
    `<!-- SCANNER:EXEMPT-START -->` open a range; lines containing
    `<!-- SCANNER:EXEMPT-END -->` close it. Both marker lines are included
    in the exempt range (they're HTML comments so they wouldn't fire anyway,
    but counting them keeps the math intuitive).

    Unmatched markers are tolerated: a stray START with no END is dropped,
    and a stray END is ignored.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return []
    ranges: List[Tuple[int, int]] = []
    start_line: Optional[int] = None
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _EXEMPT_START_MARKER in line and start_line is None:
            start_line = line_no
        elif _EXEMPT_END_MARKER in line and start_line is not None:
            ranges.append((start_line, line_no))
            start_line = None
    return ranges


def _exempt_line_count(repo_root: Path) -> int:
    """Total number of lines whitelisted across all exempt files."""
    total = 0
    for rel_path in _FORBIDDEN_PHRASE_EXEMPT_FILES:
        full = repo_root / rel_path
        if not full.is_file():
            continue
        for start, end in _get_exempt_ranges(full):
            total += (end - start + 1)
    # Add the scanner's own self-exemption.
    for start, end in _get_self_exempt_ranges():
        total += (end - start + 1)
    return total


def _is_excluded(rel_path: str) -> bool:
    for frag in _FORBIDDEN_PHRASE_SCAN_EXCLUDES:
        if frag in rel_path:
            return True
    return False


def _is_exempt(rel_path: str, line_no: int, exempt_cache: Dict[str, List[Tuple[int, int]]]) -> bool:
    ranges = exempt_cache.get(rel_path)
    if not ranges:
        return False
    for start, end in ranges:
        if start <= line_no <= end:
            return True
    return False


def _build_exempt_cache(repo_root: Path) -> Dict[str, List[Tuple[int, int]]]:
    """Resolve all exempt ranges once per scan.

    Marker-based ranges are derived from the governance files listed in
    `_FORBIDDEN_PHRASE_EXEMPT_FILES`. The scanner's own regex literal is
    located dynamically by `_get_self_exempt_ranges()`.
    """
    cache: Dict[str, List[Tuple[int, int]]] = {}
    for rel_path in _FORBIDDEN_PHRASE_EXEMPT_FILES:
        full = repo_root / rel_path
        if not full.is_file():
            continue
        cache[rel_path] = _get_exempt_ranges(full)
    self_ranges = _get_self_exempt_ranges()
    if self_ranges:
        cache[_SELF_EXEMPT_FILE] = self_ranges
    return cache


def check_forbidden_phrase_leak(repo_root: Path) -> List[Finding]:
    """Walk repo_root and emit ERROR Findings for each forbidden-phrase hit
    that is not covered by the marker-based exempt cache.

    Returns a flat list of Findings. A clean repo returns []. The check_id is
    `VIII.forbidden-phrase-leak`; location encodes the file:line of each hit
    so downstream tooling (CI, PowerShell wrapper) can group output.
    """
    findings: List[Finding] = []
    if not repo_root.is_dir():
        return findings
    exempt_cache = _build_exempt_cache(repo_root)
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in _FORBIDDEN_PHRASE_SCAN_INCLUDES:
            continue
        try:
            rel_path = path.relative_to(repo_root).as_posix()
        except ValueError:
            continue
        if _is_excluded(rel_path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not _FORBIDDEN_PHRASES_RE.search(line):
                continue
            if _is_exempt(rel_path, line_no, exempt_cache):
                continue
            snippet = line.strip()[:100]
            findings.append(Finding(
                severity="error",
                code="VIII.forbidden-phrase-leak",
                message=f"Forbidden phrase at {rel_path}:{line_no}: {snippet}",
                location=f"{rel_path}:{line_no}",
                article="VIII",
            ))
    return findings


# ============================================================================
# Scan driver
# ============================================================================


def load_manifest(path: Path) -> Dict[str, Any]:
    if path.is_dir():
        candidate = path / "grok-agent.yaml"
        if not candidate.is_file():
            raise FileNotFoundError(f"No grok-agent.yaml in folder: {path}")
        path = candidate
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    text = path.read_text(encoding="utf-8-sig")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(
            f"Manifest must be a YAML mapping, got {type(data).__name__}"
        )
    return data


def scan_manifest(path: Path) -> ScanResult:
    data = load_manifest(path)
    result = ScanResult(manifest_path=str(path))
    for name, fn in CHECKS.items():
        try:
            findings = fn(data)
        except Exception as e:  # check itself broke — never block on that
            findings = [Finding(
                "warn", "INT-001",
                f"check '{name}' raised: {e}", name, "VIII",
            )]
        result.findings.extend(findings)
    return result


def find_manifests(root: Path) -> List[Path]:
    """Return every grok-agent.yaml under `root` (recursive)."""
    if root.is_file():
        return [root]
    return sorted(root.rglob("grok-agent.yaml"))


# ============================================================================
# CLI
# ============================================================================


def _print_text_report(result: ScanResult, severity_floor: str) -> None:
    visible = result.filter_by_floor(severity_floor)
    sys.stdout.write(f"-> Scanning: {result.manifest_path}\n")
    if not visible:
        sys.stdout.write(
            f"OK No findings at or above '{severity_floor}'. "
            f"({len(result.findings)} info-level checks ran cleanly.)\n"
        )
        return
    counts = {s: 0 for s in SEVERITIES}
    for f in visible:
        counts[f.severity] += 1
        sys.stdout.write(f.to_line() + "\n")
    summary = ", ".join(f"{counts[s]} {s}" for s in SEVERITIES if counts[s])
    sys.stdout.write(f"-- {summary}\n")


def _print_json_report(result: ScanResult, severity_floor: str) -> None:
    visible = result.filter_by_floor(severity_floor)
    payload = {
        "manifest_path": result.manifest_path,
        "max_severity": result.max_severity,
        "has_errors": result.has_errors,
        "findings": [f.to_json() for f in visible],
        "constitution_version": CONSTITUTION_VERSION,
        "scanner_version": VERSION,
    }
    sys.stdout.write(json.dumps(payload) + "\n")


def cmd_scan(args: argparse.Namespace) -> int:
    raw = Path(args.path).expanduser()
    try:
        result = scan_manifest(raw)
    except FileNotFoundError as e:
        sys.stderr.write(f"X  {e}\n")
        return 66
    except Exception as e:
        sys.stderr.write(f"X  Failed to load manifest: {e}\n")
        return 65

    if args.json:
        _print_json_report(result, args.severity_floor)
    else:
        _print_text_report(result, args.severity_floor)

    return 1 if result.has_errors else 0


def cmd_scan_all(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser()
    if not root.exists():
        sys.stderr.write(f"X  Root not found: {root}\n")
        return 66
    paths = find_manifests(root)
    if not paths:
        sys.stderr.write(f"!! No grok-agent.yaml files under {root}\n")
        return 0
    any_errors = False
    if not args.json:
        sys.stdout.write(f"-> Scanning {len(paths)} manifest(s) under {root}\n\n")
    for p in paths:
        try:
            result = scan_manifest(p)
        except Exception as e:
            sys.stderr.write(f"X  {p}: failed to load: {e}\n")
            any_errors = True
            continue
        any_errors = any_errors or result.has_errors
        if args.json:
            _print_json_report(result, args.severity_floor)
        else:
            _print_text_report(result, args.severity_floor)
            sys.stdout.write("\n")
    return 1 if any_errors else 0


def cmd_info(_args: argparse.Namespace) -> int:
    sys.stdout.write(
        f"safety/scanner.py v{VERSION}\n"
        f"Constitution: v{CONSTITUTION_VERSION} (safety/constitution.md)\n"
        f"Checks registered: {len(CHECKS)}\n"
    )
    for name in sorted(CHECKS):
        sys.stdout.write(f"  - {name}\n")
    sys.stdout.write(f"{TAGLINE}\n")
    return 0


def cmd_forbidden_phrase_scan(args: argparse.Namespace) -> int:
    """Run the repo-wide forbidden-phrase leak check (Article VIII)."""
    repo_root = Path(getattr(args, "repo_root", None) or Path.cwd()).expanduser().resolve()
    if not repo_root.is_dir():
        sys.stderr.write(f"X  Repo root not found: {repo_root}\n")
        return 66
    findings = check_forbidden_phrase_leak(repo_root)
    exempt_count = _exempt_line_count(repo_root)
    if args.json:
        payload = {
            "repo_root": str(repo_root),
            "check_id": "VIII.forbidden-phrase-leak",
            "exempt_line_count": exempt_count,
            "findings": [f.to_json() for f in findings],
            "has_errors": any(f.severity == "error" for f in findings),
            "scanner_version": VERSION,
        }
        sys.stdout.write(json.dumps(payload) + "\n")
        return 1 if findings else 0
    sys.stdout.write(f"-> Forbidden-phrase scan: {repo_root}\n")
    if not findings:
        sys.stdout.write(
            f"OK No forbidden-phrase leaks. ({exempt_count} exempt lines whitelisted)\n"
        )
        return 0
    for f in findings:
        sys.stdout.write(f.to_line() + "\n")
    sys.stdout.write(
        f"-- {len(findings)} error finding(s) ({exempt_count} exempt lines whitelisted)\n"
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok-safety-scanner",
        description=(
            f"Grok Agent OS — Safety Scanner. Enforces Constitution v{CONSTITUTION_VERSION}. "
            f"{TAGLINE}"
        ),
        epilog=(
            "Examples:\n"
            "  python safety/scanner.py scan path/to/grok-agent.yaml\n"
            "  python safety/scanner.py scan path/to/agent-folder --json\n"
            "  python safety/scanner.py scan-all templates/\n"
            "  python safety/scanner.py info\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"safety/scanner.py {VERSION} (Constitution v{CONSTITUTION_VERSION})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan a single manifest.")
    p_scan.add_argument("path", help="Path to grok-agent.yaml or agent folder.")
    p_scan.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    p_scan.add_argument(
        "--severity-floor",
        choices=SEVERITIES,
        default="info",
        help="Hide findings below this severity (default: info).",
    )
    p_scan.set_defaults(func=cmd_scan)

    p_all = sub.add_parser(
        "scan-all", help="Recursively scan every grok-agent.yaml under a root."
    )
    p_all.add_argument("root", help="Root directory to scan (e.g. templates/).")
    p_all.add_argument("--json", action="store_true", help="Emit JSON per manifest.")
    p_all.add_argument(
        "--severity-floor",
        choices=SEVERITIES,
        default="info",
        help="Hide findings below this severity (default: info).",
    )
    p_all.set_defaults(func=cmd_scan_all)

    p_info = sub.add_parser("info", help="Print version + check list and exit.")
    p_info.set_defaults(func=cmd_info)

    p_fp = sub.add_parser(
        "forbidden-phrase-scan",
        help="Walk the repo and flag any forbidden-phrase leak (Article VIII).",
    )
    p_fp.add_argument(
        "--repo-root",
        default=None,
        help="Repo root to scan (default: current working directory).",
    )
    p_fp.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    p_fp.set_defaults(func=cmd_forbidden_phrase_scan)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
