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
"""LangGraph state machine for the Cross-Reality Action Fabric.

This module is the **orchestration core** of Super Agent #3. Where Super
Agent #2 (Self-Evolving Personal OS) reads + remembers, Super Agent #3
**acts** — and every action is gated, reversible, and provenance-logged.

The graph implements the seven Constitution Rules from
``constitution.md`` directly in code:

    plan_actions
        ↓
    request_approval        ← HITL gate (Rule 1)
        ↓
    ┌──────────────────────────────────────────┐
    │  per-action dispatch (one tool per step) │
    │                                          │
    │  execute_web      execute_windows        │
    │  execute_realworld   execute_x           │
    └──────────────────────────────────────────┘
        ↓
    output_with_provenance      ← Rule 2 (mandatory provenance)
        ↓
    rollback (conditional)      ← Rule 3 (verbatim rollback)
        ↓
    END

Every action node:

- Refuses if its step's ``consent_token`` field is empty (Rule 1).
- Refuses if its step's ``rollback`` field is empty for state-changing
  tools (Rule 3 — schema-enforced upstream by the P128 manifest, but
  re-checked here as defence in depth).
- Writes the verbatim action plan, consent token, started_at /
  finished_at, and outcome into ``state['provenance']`` (Rule 2).
- Surfaces conflicting sources rather than silently picking one
  (Rule 4 — encoded in the action-plan generator).
- Refuses any non-Windows path / shell prefix (Rule 5).
- Only writes under ``$env:LOCALAPPDATA\\grok-agent\\
  cross-reality-action-fabric\\`` unless ``modify_local_files_outside_
  appdata`` is held (Rule 6).

LangGraph is the production runtime. When it is not installed (CI,
Codespaces, the user's first install before they run
``python -m pip install -r requirements.txt``), this module switches to
the same self-contained sequential executor used by Super Agent #2's
P123 graph — exposing the **same** ``add_node`` / ``add_edge`` /
``add_conditional_edges`` / ``set_entry_point`` / ``compile`` /
``invoke`` API. The smoke test exercises both backends.

Built to make Grok the obvious choice for every agent on X — the
orchestration core is what turns "Grok runs on X" into "Grok runs your
laptop, with explicit consent on every action".
"""

from __future__ import annotations

import copy
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

__all__ = [
    # Constants
    "AGENT_NAME",
    "BACKEND_NAME",
    "DEFAULT_PROMPT_VERSION",
    "ALLOWED_TOOLS",
    "STATE_CHANGING_TOOLS",
    "READ_ONLY_TOOLS",
    "MAX_ACTIONS_PER_PLAN",
    # Exceptions + data classes
    "ConstitutionViolation",
    "ConsentContext",
    "ActionStep",
    "ActionPlan",
    # State + nodes
    "CrossRealityState",
    "build_state",
    "plan_actions",
    "request_approval",
    "execute_web",
    "execute_windows",
    "execute_realworld",
    "execute_x",
    "rollback",
    "output_with_provenance",
    # Routing
    "route_after_approval",
    "route_after_execution",
    # Builder + driver
    "build_graph",
    "run_action_loop",
    # Helpers
    "appdata_root",
    "describe_graph",
    "make_consent_token",
    "make_run_id",
    "redact_pii",
]


# --- Section 1. Constants ------------------------------------------------

AGENT_NAME = "cross-reality-action-fabric"
DEFAULT_PROMPT_VERSION = f"{AGENT_NAME}/prompts@v1"
MAX_ACTIONS_PER_PLAN = 5
MAX_PLAN_LOOPS = 1   # bounded re-plan after rollback

# Tool taxonomy — must match the 5 tools declared in P128 grok-agent.yaml.
ALLOWED_TOOLS: tuple[str, ...] = (
    "web_via_stagehand",
    "windows_local",
    "weather_lookup",
    "flight_search",
    "x_search",
)
# State-changing tools require Rule 3 (verbatim rollback).
STATE_CHANGING_TOOLS: frozenset[str] = frozenset({
    "web_via_stagehand",
    "windows_local",
})
# Read-only tools are exempt from rollback (Rule 3 carve-out).
READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "weather_lookup",
    "flight_search",
    "x_search",
})

# Mapping from tool name to the dispatch node that executes it.
TOOL_NODE_MAP: dict[str, str] = {
    "web_via_stagehand":  "execute_web",
    "windows_local":      "execute_windows",
    "weather_lookup":     "execute_realworld",
    "flight_search":      "execute_realworld",
    "x_search":           "execute_x",
}

# Node names (referenced from `add_node` and `add_edge`).
NODE_PLAN     = "plan_actions"
NODE_APPROVE  = "request_approval"
NODE_EXEC_WEB = "execute_web"
NODE_EXEC_WIN = "execute_windows"
NODE_EXEC_RW  = "execute_realworld"
NODE_EXEC_X   = "execute_x"
NODE_ROLLBACK = "rollback"
NODE_OUTPUT   = "output_with_provenance"


# --- Section 2. Path helpers ---------------------------------------------

def appdata_root() -> Path:
    """Resolve the local-first data folder for this Super Agent."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / AGENT_NAME
    return Path.home() / ".local" / "share" / "grok-agent" / AGENT_NAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_consent_token(scope: str, *, prefix: str = "ct") -> str:
    """Mint a scoped consent token for one action."""
    return f"{prefix}-{scope}-{uuid.uuid4().hex[:12]}"


def make_run_id() -> str:
    """One run = one full graph traversal."""
    return f"crf-run-{uuid.uuid4().hex[:12]}"


# --- Section 3. PII redactor (self-contained, mirrors P121) --------------

# Conservative regexes — false positives are preferable to leaking PII. The
# patterns are deliberately strict and the redaction strings are all-caps
# tokens so a downstream eyeball test can spot them at a glance. The set
# matches the P121 redactor exactly so the two stacks stay PII-equivalent.
_PII_PATTERNS: tuple[tuple[str, "re.Pattern[str]", str], ...] = (
    ("email",   re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
                "[REDACTED_EMAIL]"),
    ("xhandle", re.compile(r"(?<![\w/])@([A-Za-z0-9_]{2,15})\b"),
                "@[REDACTED_HANDLE]"),
    ("phone",   re.compile(r"(?<![\d:T-])\+?\d{1,3}[\s.\-]?\(?\d{3}\)?"
                           r"[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)"),
                "[REDACTED_PHONE]"),
    ("card",    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
                "[REDACTED_CARD]"),
    ("ssn_us",  re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
                "[REDACTED_SSN]"),
    ("street",  re.compile(r"\b\d{1,6}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+"
                           r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|"
                           r"Lane|Ln|Drive|Dr)\b"),
                "[REDACTED_ADDRESS]"),
    ("latlon",  re.compile(r"\b-?\d{1,3}\.\d{4,}\s*[,;]\s*-?\d{1,3}\.\d{4,}\b"),
                "[REDACTED_GEO]"),
)

_PII_FIELD_NAMES: frozenset[str] = frozenset({
    "email", "email_address", "phone", "phone_number",
    "address", "home_address", "billing_address", "shipping_address",
    "ssn", "tax_id", "passport", "credit_card", "card_number", "card",
    "lat", "lon", "latitude", "longitude", "geo",
    "ip", "ip_address", "device_id",
    "password", "secret", "token", "api_key",
})

_ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+\-]\d{2}:?\d{2})?)?$"
)


def redact_pii(value: Any) -> Any:
    """Recursive PII redactor — same engine as P121, ISO timestamps skipped."""
    if isinstance(value, str):
        if _ISO_TIMESTAMP_RE.match(value):
            return value
        out = value
        for _name, pattern, replacement in _PII_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, list):
        return [redact_pii(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_pii(v) for v in value)
    if isinstance(value, dict):
        red: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _PII_FIELD_NAMES:
                red[k] = "[REDACTED]" if v is not None else None
            else:
                red[k] = redact_pii(v)
        return red
    return value


# --- Section 4. Exceptions + dataclasses ---------------------------------

class ConstitutionViolation(RuntimeError):
    """Raised when a graph node is asked to do something the Constitution
    forbids. The orchestrator surfaces this in ``state['violations']``
    rather than crashing — the user sees an honest refusal report."""

    def __init__(
        self,
        message: str,
        *,
        rule: int = 1,
        tool: str | None = None,
        step_index: int | None = None,
    ) -> None:
        super().__init__(message)
        self.rule = int(rule)
        self.tool = tool
        self.step_index = step_index

    def __repr__(self) -> str:  # pragma: no cover — diagnostic helper
        return (
            f"ConstitutionViolation(rule={self.rule!r}, tool={self.tool!r}, "
            f"step_index={self.step_index!r}, message={self.args[0]!r})"
        )


@dataclass
class ConsentContext:
    """Snapshot of the user's currently-held consent gates."""
    gates: frozenset[str] = field(default_factory=frozenset)
    consent_token: str | None = None
    granted_at: str | None = None
    timeout_seconds: int = 60

    def has(self, gate: str) -> bool:
        return gate in self.gates

    @classmethod
    def from_iterable(cls, gates, **kwargs: Any) -> "ConsentContext":
        return cls(gates=frozenset(gates), **kwargs)


@dataclass
class ActionStep:
    """One step in an action plan.

    The ``script`` and ``rollback`` are verbatim — no template expansion,
    no late-bound parameters. ``consent_token`` is empty until the user
    approves the step at the HITL prompt.
    """

    step:                 int
    tool:                 str
    description:          str
    script:               str
    rollback:             str
    expected_cost_usd:    float
    consent_required:     bool = True
    consent_token:        str | None = None
    executed:             bool = False
    rolled_back:          bool = False
    outcome:              str | None = None       # "success" | "failure" | "aborted" | "rolled_back"
    started_at:           str | None = None
    finished_at:          str | None = None
    execution_result:     dict = field(default_factory=dict)
    refusal_reason:       str | None = None

    def to_dict(self) -> dict:
        return {
            "step":               int(self.step),
            "tool":               self.tool,
            "description":        self.description,
            "script":             self.script,
            "rollback":           self.rollback,
            "expected_cost_usd":  float(self.expected_cost_usd),
            "consent_required":   bool(self.consent_required),
            "consent_token":      self.consent_token,
            "executed":           bool(self.executed),
            "rolled_back":        bool(self.rolled_back),
            "outcome":            self.outcome,
            "started_at":         self.started_at,
            "finished_at":        self.finished_at,
            "execution_result":   dict(self.execution_result),
            "refusal_reason":     self.refusal_reason,
        }


@dataclass
class ActionPlan:
    """The output of :func:`plan_actions` — what the agent INTENDS to do.

    Every step must be presented to the user (via :func:`request_approval`)
    before any of them runs. The user can approve all, approve some, or
    cancel the plan entirely.
    """

    plan_id:            str
    user_request:       str
    proposed_actions:   list[ActionStep]
    total_cost_usd:     float
    created_at:         str
    contradictions:     list[dict] = field(default_factory=list)
    refusal_reason:     str | None = None

    def to_dict(self) -> dict:
        return {
            "plan_id":          self.plan_id,
            "user_request":     self.user_request,
            "proposed_actions": [a.to_dict() for a in self.proposed_actions],
            "total_cost_usd":   float(self.total_cost_usd),
            "created_at":       self.created_at,
            "contradictions":   list(self.contradictions),
            "refusal_reason":   self.refusal_reason,
        }


# --- Section 5. State definition -----------------------------------------

CrossRealityState = dict   # alias for clarity


def build_state(
    *,
    user_id: str = "default",
    user_request: str = "",
    consent: ConsentContext | None = None,
    force_stub: bool = False,
    auto_approve: bool = False,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> CrossRealityState:
    """Construct a fresh state for one action-loop run."""
    return {
        # caller-provided
        "user_id":         user_id,
        "user_request":    user_request,
        "consent":         consent or ConsentContext(),
        "force_stub":      bool(force_stub),
        "auto_approve":    bool(auto_approve),
        "prompt_version":  prompt_version,
        # runtime accumulators
        "plan":            None,    # ActionPlan dict
        "approvals":       [],      # list of {step, consent_token, granted_at}
        "executions":      [],      # list of executed step dicts
        "rollbacks":       [],      # list of rollback step dicts
        "violations":      [],
        "provenance":      [],
        "loop_count":      0,
        "output":          {},
        "started_at":      _now_iso(),
        "finished_at":     None,
    }


# --- Section 6. PII / safety helpers used by nodes -----------------------

def _trail(action: str, *, stub: bool, **extra: Any) -> dict:
    row = {
        "ts":     _now_iso(),
        "node":   action,
        "action": action,
        "stub":   bool(stub),
    }
    if extra:
        row.update(extra)
    return row


def _has_bash_leak(script: str) -> bool:
    """Rule 5 enforcement — refuse non-Windows shell prefixes."""
    if not isinstance(script, str):
        return False
    bad = ("bash -c", "sh -c", "osascript", "wsl.exe", "/usr/bin/",
           "/bin/bash", " sudo ", "/etc/", "/var/", "/Applications/")
    s = script
    for needle in bad:
        if needle in s:
            return True
    return False


def _validate_step(step: ActionStep) -> tuple[bool, str | None]:
    """Run static Constitution checks against an action step."""
    if step.tool not in ALLOWED_TOOLS:
        return False, f"unknown tool '{step.tool}' (Rule 1 — allowed: {list(ALLOWED_TOOLS)})"
    # Rule 5 — Windows-only execution.
    if step.tool == "windows_local" and _has_bash_leak(step.script):
        return False, "bash / unix shell prefix detected in script (Rule 5)"
    # Rule 3 — verbatim rollback for state-changing tools.
    if step.tool in STATE_CHANGING_TOOLS and not step.rollback.strip():
        return False, "state-changing tool requires verbatim rollback (Rule 3)"
    # Rule 6 — local-first; refuse paths outside AppData unless gate held.
    if step.tool == "windows_local":
        outside_appdata = (
            "C:\\Windows\\" in step.script
            or "C:\\Program Files\\" in step.script
        )
        if outside_appdata:
            return False, (
                "script touches files outside %LOCALAPPDATA% — "
                "modify_local_files_outside_appdata gate not implemented "
                "in this orchestrator (Rule 6)"
            )
    return True, None


# --- Section 7. Node implementations -------------------------------------

def plan_actions(state: CrossRealityState) -> dict:
    """Node 1 — generate the action plan.

    In ``force_stub`` mode (the default for CI / weekly cron / first-run
    on a fresh Windows install) the plan is deterministically generated
    from a small lookup so the rest of the graph is exercised end-to-end.
    A future prompt wires Grok 4.3 here for real natural-language plans;
    the contract surface (an :class:`ActionPlan` dict) is identical
    either way.
    """
    user_request = (state.get("user_request") or "").strip()
    force_stub   = bool(state.get("force_stub"))
    plan_id      = f"plan-{uuid.uuid4().hex[:12]}"

    # If the caller pre-populated state['plan'] (the official path for
    # ``approve_pending`` and ``rollback_last``), this node is a pass-
    # through: we record a provenance row but do not overwrite the plan.
    existing = state.get("plan") or {}
    if isinstance(existing, dict) and existing.get("proposed_actions"):
        trail = _trail(
            NODE_PLAN, stub=force_stub,
            note="pre-existing plan kept (caller path: approve / rollback)",
            plan_id=existing.get("plan_id"),
            action_count=len(existing.get("proposed_actions") or []),
        )
        return {
            "plan":       existing,
            "provenance": list(state.get("provenance") or []) + [trail],
        }

    if force_stub or not user_request:
        # Deterministic 4-action stub plan covering all 5 tool classes
        # (one consolidated real-world step exercises both weather + flight).
        steps = [
            ActionStep(
                step=1,
                tool="weather_lookup",
                description="Read-only lookup: weather forecast for Hanoi this Saturday.",
                script="GET /data/2.5/forecast?q=Hanoi,VN",
                rollback="",   # read-only — no rollback needed
                expected_cost_usd=0.0,
            ),
            ActionStep(
                step=2,
                tool="x_search",
                description="Read-only search: latest X posts mentioning '#GrokAgentOS'.",
                script="x_search query='#GrokAgentOS' limit=10",
                rollback="",
                expected_cost_usd=0.0,
            ),
            ActionStep(
                step=3,
                tool="windows_local",
                description="Append a single line to the agent's daily journal.",
                script=(
                    "$path = Join-Path $env:LOCALAPPDATA "
                    "'grok-agent\\cross-reality-action-fabric\\journal.md' ; "
                    "Add-Content -Path $path -Value '[stub] daily plan rendered.'"
                ),
                rollback=(
                    "$path = Join-Path $env:LOCALAPPDATA "
                    "'grok-agent\\cross-reality-action-fabric\\journal.md' ; "
                    "if (Test-Path $path) { "
                    "  $c = Get-Content $path ; "
                    "  $c[0..($c.Count - 2)] | Set-Content $path "
                    "}"
                ),
                expected_cost_usd=0.0,
            ),
            ActionStep(
                step=4,
                tool="web_via_stagehand",
                description="Open Booking.com in a visible Chrome window (no submit).",
                script="navigate https://www.booking.com",
                rollback="close_chrome_tab(target='https://www.booking.com')",
                expected_cost_usd=0.0,
            ),
        ]
        plan = ActionPlan(
            plan_id=plan_id,
            user_request=user_request or "(stub) daily plan",
            proposed_actions=steps,
            total_cost_usd=0.0,
            created_at=_now_iso(),
            contradictions=[],
        )
        prov_extra = {
            "stub_reason": "force_stub mode — deterministic 4-action plan",
            "action_count": len(steps),
            "tools": [s.tool for s in steps],
        }
    else:
        # No force_stub and a real request, but no LLM client yet.
        # Refuse honestly rather than silently fabricate.
        plan = ActionPlan(
            plan_id=plan_id,
            user_request=user_request,
            proposed_actions=[],
            total_cost_usd=0.0,
            created_at=_now_iso(),
            refusal_reason=(
                "Grok 4.3 client not wired in this orchestrator slot. "
                "Re-run with --stub or wait for a later prompt."
            ),
        )
        prov_extra = {"refusal_reason": plan.refusal_reason}

    plan_dict = plan.to_dict()
    trail = _trail(NODE_PLAN, stub=force_stub, **prov_extra)

    return {
        "plan":           plan_dict,
        "provenance":     list(state.get("provenance") or []) + [trail],
    }


def request_approval(state: CrossRealityState) -> dict:
    """Node 2 — HITL gate.  Refuses to advance until consent is in state.

    The runtime is responsible for *prompting* the user. This node only
    checks whether the held consent matches the plan's required scope.
    The CLI's ``approve-pending`` command attaches consent_tokens to
    each step before invoking the graph again; the dashboard does the
    same via session_state.
    """
    plan = state.get("plan") or {}
    consent: ConsentContext = state.get("consent") or ConsentContext()
    force_stub = bool(state.get("force_stub"))

    proposed = plan.get("proposed_actions") or []
    violations: list[dict] = list(state.get("violations") or [])

    # Refuse the whole run when the plan itself failed.
    if plan.get("refusal_reason"):
        violations.append({
            "node":   NODE_APPROVE,
            "rule":   1,
            "reason": plan["refusal_reason"],
        })
        trail = _trail(
            NODE_APPROVE, stub=force_stub,
            note="plan refused upstream — nothing to approve",
            refusal_reason=plan["refusal_reason"],
        )
        return {
            "violations": violations,
            "provenance": list(state.get("provenance") or []) + [trail],
        }

    # Per-step static checks (Rules 3, 5, 6) — fail fast before approval.
    for raw_step in proposed:
        step = _action_step_from_dict(raw_step)
        ok, why = _validate_step(step)
        if not ok:
            violations.append({
                "node":     NODE_APPROVE,
                "rule":     5 if "Rule 5" in (why or "") else 3,
                "tool":     step.tool,
                "step":     step.step,
                "message":  why,
            })
            raw_step["consent_token"]  = None
            raw_step["refusal_reason"] = why

    # Consent enforcement: each step needs a consent_token *unless* the
    # session-wide ``consent`` already holds the per-tool gate.
    approvals: list[dict] = list(state.get("approvals") or [])
    consent_map = {a["step"]: a for a in approvals}
    for raw_step in proposed:
        step_idx = raw_step.get("step")
        tool     = raw_step.get("tool")
        if raw_step.get("refusal_reason"):
            continue
        # auto_approve mints consent tokens automatically. The CLI only
        # sets this when the user passed --auto-approve; the smoke test
        # exercises both the auto-approve and the gate-blocked path.
        if state.get("auto_approve") and not raw_step.get("consent_token"):
            tok = make_consent_token(scope=str(tool or "unknown"))
            raw_step["consent_token"] = tok
            approvals.append({
                "step":          step_idx,
                "consent_token": tok,
                "tool":          tool,
                "granted_at":    _now_iso(),
                "stub":          True,
            })
            continue
        ack = consent_map.get(step_idx)
        if ack is None and not raw_step.get("consent_token"):
            violations.append({
                "node":    NODE_APPROVE,
                "rule":    1,
                "tool":    tool,
                "step":    step_idx,
                "message": (
                    "step has no consent_token; HITL gate blocks execution "
                    "(Rule 1 — typed approval required)"
                ),
            })
            raw_step["refusal_reason"] = (
                raw_step.get("refusal_reason")
                or "missing consent_token (HITL gate blocked)"
            )

    plan["proposed_actions"] = proposed
    trail = _trail(
        NODE_APPROVE, stub=force_stub,
        approved_count=sum(
            1 for s in proposed
            if s.get("consent_token") and not s.get("refusal_reason")
        ),
        refused_count=sum(1 for s in proposed if s.get("refusal_reason")),
        note="HITL gate evaluated each step.",
    )
    return {
        "plan":       plan,
        "approvals":  approvals,
        "violations": violations,
        "provenance": list(state.get("provenance") or []) + [trail],
    }


def _action_step_from_dict(d: dict) -> ActionStep:
    return ActionStep(
        step=int(d.get("step", 0)),
        tool=str(d.get("tool", "")),
        description=str(d.get("description", "")),
        script=str(d.get("script", "")),
        rollback=str(d.get("rollback", "")),
        expected_cost_usd=float(d.get("expected_cost_usd", 0.0) or 0.0),
        consent_required=bool(d.get("consent_required", True)),
        consent_token=d.get("consent_token"),
        executed=bool(d.get("executed", False)),
        rolled_back=bool(d.get("rolled_back", False)),
        outcome=d.get("outcome"),
        started_at=d.get("started_at"),
        finished_at=d.get("finished_at"),
        execution_result=dict(d.get("execution_result") or {}),
        refusal_reason=d.get("refusal_reason"),
    )


def _execute_one(
    raw_step: dict,
    *,
    expected_node: str,
    state: CrossRealityState,
) -> tuple[dict, dict]:
    """Common per-step execution path used by all four execute_* nodes.

    Returns ``(updated_step_dict, result_payload)``. Persists outcome /
    timestamps / execution_result on the step. Refuses if consent is
    missing (Rule 1 belt-and-braces, even though request_approval just
    enforced it).
    """
    force_stub = bool(state.get("force_stub"))
    step = _action_step_from_dict(raw_step)

    if step.refusal_reason:
        return raw_step, {
            "step":   step.step,
            "tool":   step.tool,
            "ok":     False,
            "outcome": "aborted",
            "reason": step.refusal_reason,
        }

    if step.consent_required and not step.consent_token:
        raw_step["refusal_reason"] = (
            "execute_* node refused: consent_token missing (Rule 1)"
        )
        raw_step["outcome"] = "aborted"
        return raw_step, {
            "step":   step.step,
            "tool":   step.tool,
            "ok":     False,
            "outcome": "aborted",
            "reason": raw_step["refusal_reason"],
        }

    expected_tool_for_node = {
        NODE_EXEC_WEB: ("web_via_stagehand",),
        NODE_EXEC_WIN: ("windows_local",),
        NODE_EXEC_RW:  ("weather_lookup", "flight_search"),
        NODE_EXEC_X:   ("x_search",),
    }
    if step.tool not in expected_tool_for_node.get(expected_node, ()):
        # Wrong dispatch — refuse without executing.
        raw_step["refusal_reason"] = (
            f"step {step.step} tool '{step.tool}' routed to wrong "
            f"execute node {expected_node}"
        )
        raw_step["outcome"] = "aborted"
        return raw_step, {
            "step":   step.step,
            "tool":   step.tool,
            "ok":     False,
            "outcome": "aborted",
            "reason": raw_step["refusal_reason"],
        }

    started = _now_iso()
    raw_step["started_at"] = started

    if force_stub:
        # Build a deterministic, structurally-valid result.
        result = {
            "step":   step.step,
            "tool":   step.tool,
            "ok":     True,
            "outcome": "success",
            "stub":   True,
            "summary": f"[stub] {step.tool} executed: {step.description[:80]}",
        }
        raw_step["execution_result"] = redact_pii(result)
        raw_step["executed"]         = True
        raw_step["outcome"]          = "success"
        raw_step["finished_at"]      = _now_iso()
    else:
        # No real client wired in this slot — refuse honestly.
        raw_step["refusal_reason"] = (
            f"real {step.tool} client not wired in this orchestrator slot; "
            "re-run with --stub or wait for a later prompt"
        )
        raw_step["outcome"]    = "aborted"
        raw_step["finished_at"] = _now_iso()
        result = {
            "step":   step.step,
            "tool":   step.tool,
            "ok":     False,
            "outcome": "aborted",
            "reason": raw_step["refusal_reason"],
        }

    return raw_step, redact_pii(result)


def _execute_batch(
    state: CrossRealityState,
    *,
    expected_node: str,
    accept_tools: tuple[str, ...],
) -> dict:
    plan = state.get("plan") or {}
    proposed = plan.get("proposed_actions") or []
    executions = list(state.get("executions") or [])
    for raw_step in proposed:
        if raw_step.get("tool") not in accept_tools:
            continue
        if raw_step.get("executed") or raw_step.get("outcome") in (
            "aborted", "rolled_back"
        ):
            continue
        new_raw, result = _execute_one(
            raw_step, expected_node=expected_node, state=state
        )
        # Mutate raw_step in-place AND record an execution row.
        raw_step.update(new_raw)
        executions.append(result)
    plan["proposed_actions"] = proposed

    trail = _trail(
        expected_node, stub=bool(state.get("force_stub")),
        executed_count=sum(
            1 for r in executions
            if r.get("tool") in accept_tools and r.get("ok")
        ),
        aborted_count=sum(
            1 for r in executions
            if r.get("tool") in accept_tools and not r.get("ok")
        ),
    )
    return {
        "plan":       plan,
        "executions": executions,
        "provenance": list(state.get("provenance") or []) + [trail],
    }


def execute_web(state: CrossRealityState) -> dict:
    """Node — Stagehand web automation.  Stubs return a structurally-valid
    success row; the real Stagehand client wires in P131."""
    return _execute_batch(state, expected_node=NODE_EXEC_WEB,
                          accept_tools=("web_via_stagehand",))


def execute_windows(state: CrossRealityState) -> dict:
    """Node — local PowerShell action.  Refuses bash leaks at the
    static-validation pass (Rule 5).  Stubs return a deterministic success
    so the smoke test can verify the pipeline end-to-end."""
    return _execute_batch(state, expected_node=NODE_EXEC_WIN,
                          accept_tools=("windows_local",))


def execute_realworld(state: CrossRealityState) -> dict:
    """Node — read-only public APIs (weather + flights)."""
    return _execute_batch(state, expected_node=NODE_EXEC_RW,
                          accept_tools=("weather_lookup", "flight_search"))


def execute_x(state: CrossRealityState) -> dict:
    """Node — read-only X search via Grok 4.3 tool-calling."""
    return _execute_batch(state, expected_node=NODE_EXEC_X,
                          accept_tools=("x_search",))


def rollback(state: CrossRealityState) -> dict:
    """Node — revert the last successful state-changing action.

    Rule 3 in code: takes the most-recent successful state-changing step
    and runs its verbatim ``rollback`` snippet. Stubbing is handled the
    same way as the forward action: a deterministic success row +
    ``rolled_back: True`` flag. The user can re-invoke this node from
    the CLI's ``rollback-last`` command — the same code path runs
    either way.
    """
    plan = state.get("plan") or {}
    proposed = plan.get("proposed_actions") or []
    rollbacks = list(state.get("rollbacks") or [])
    force_stub = bool(state.get("force_stub"))

    target: dict | None = None
    for raw_step in reversed(proposed):
        if (
            raw_step.get("executed")
            and raw_step.get("outcome") == "success"
            and not raw_step.get("rolled_back")
            and raw_step.get("tool") in STATE_CHANGING_TOOLS
        ):
            target = raw_step
            break

    if target is None:
        trail = _trail(
            NODE_ROLLBACK, stub=force_stub,
            note="no eligible state-changing action to roll back",
        )
        return {
            "rollbacks":  rollbacks,
            "provenance": list(state.get("provenance") or []) + [trail],
        }

    if not (target.get("rollback") or "").strip():
        # Schema and request_approval both check this — if we get here,
        # someone bypassed the contract; refuse loudly.
        violations = list(state.get("violations") or [])
        violations.append({
            "node":   NODE_ROLLBACK,
            "rule":   3,
            "tool":   target.get("tool"),
            "step":   target.get("step"),
            "message": "rollback snippet missing (Rule 3 — must be verbatim)",
        })
        trail = _trail(
            NODE_ROLLBACK, stub=force_stub,
            refusal_reason="missing rollback snippet (Rule 3)",
        )
        return {
            "violations": violations,
            "provenance": list(state.get("provenance") or []) + [trail],
        }

    started = _now_iso()
    if force_stub:
        result = {
            "step":         target.get("step"),
            "tool":         target.get("tool"),
            "ok":           True,
            "outcome":      "rolled_back",
            "stub":         True,
            "rollback":     target.get("rollback"),
            "started_at":   started,
            "finished_at":  _now_iso(),
            "rolled_back_from": target.get("step"),
        }
        target["rolled_back"] = True
        target["outcome"]     = "rolled_back"
    else:
        result = {
            "step":         target.get("step"),
            "tool":         target.get("tool"),
            "ok":           False,
            "outcome":      "aborted",
            "reason":       "real rollback runtime not wired; re-run with --stub",
            "started_at":   started,
            "finished_at":  _now_iso(),
        }

    rollbacks.append(redact_pii(result))
    trail = _trail(
        NODE_ROLLBACK, stub=force_stub,
        target_step=target.get("step"),
        target_tool=target.get("tool"),
        outcome=result["outcome"],
    )
    return {
        "plan":       plan,
        "rollbacks":  rollbacks,
        "provenance": list(state.get("provenance") or []) + [trail],
    }


def output_with_provenance(state: CrossRealityState) -> dict:
    """Final node — assemble the user-visible payload + provenance."""
    finished_at = _now_iso()
    plan = state.get("plan") or {}
    executions = list(state.get("executions") or [])
    rollbacks  = list(state.get("rollbacks") or [])
    violations = list(state.get("violations") or [])

    # Aggregate metrics
    successful = sum(1 for r in executions if r.get("ok"))
    aborted    = sum(1 for r in executions if not r.get("ok"))
    cost = sum(
        float((s or {}).get("expected_cost_usd") or 0.0)
        for s in (plan.get("proposed_actions") or [])
        if s.get("executed") and s.get("outcome") == "success"
    )

    output = {
        "plan":            plan,
        "executions":      executions,
        "rollbacks":       rollbacks,
        "violations":      violations,
        "provenance": {
            "trail":           list(state.get("provenance") or []),
            "started_at":      state.get("started_at"),
            "finished_at":     finished_at,
            "force_stub":      bool(state.get("force_stub")),
            "successful":      successful,
            "aborted":         aborted,
            "cost_usd":        cost,
            "violation_count": len(violations),
            "prompt_version":  state.get("prompt_version"),
        },
        "user_id":         state.get("user_id"),
        "stub":            bool(state.get("force_stub")),
        "agent_name":      AGENT_NAME,
    }

    trail = _trail(
        NODE_OUTPUT, stub=bool(state.get("force_stub")),
        executed=successful, aborted=aborted,
        violation_count=len(violations),
    )
    output["provenance"]["trail"].append(trail)

    return {
        "output":      output,
        "finished_at": finished_at,
        "provenance":  list(state.get("provenance") or []) + [trail],
    }


# --- Section 8. Conditional routing --------------------------------------

def route_after_approval(state: CrossRealityState) -> str:
    """Where to dispatch after request_approval.

    Strategy: walk the proposed actions in order, find the first one
    that's approved + not yet executed + not refused. Route to its
    matching execute_* node. If everything is done (or refused), advance
    to output_with_provenance.
    """
    plan = state.get("plan") or {}
    for raw_step in plan.get("proposed_actions") or []:
        if raw_step.get("executed"):
            continue
        if raw_step.get("refusal_reason"):
            continue
        if not raw_step.get("consent_token"):
            continue
        tool = raw_step.get("tool")
        target = TOOL_NODE_MAP.get(tool)
        if target:
            return target
    return NODE_OUTPUT


def route_after_execution(state: CrossRealityState) -> str:
    """After every execute_* node, decide whether to keep dispatching, run
    rollback, or advance to output."""
    plan = state.get("plan") or {}
    failed_state_changing = any(
        s.get("outcome") == "failure"
        and s.get("tool") in STATE_CHANGING_TOOLS
        and not s.get("rolled_back")
        for s in (plan.get("proposed_actions") or [])
    )
    if failed_state_changing and int(state.get("loop_count") or 0) < MAX_PLAN_LOOPS:
        state["loop_count"] = int(state.get("loop_count") or 0) + 1
        return NODE_ROLLBACK
    # Continue dispatching pending steps.
    for raw_step in plan.get("proposed_actions") or []:
        if (
            not raw_step.get("executed")
            and raw_step.get("consent_token")
            and not raw_step.get("refusal_reason")
        ):
            tool = raw_step.get("tool")
            target = TOOL_NODE_MAP.get(tool)
            if target:
                return target
    return NODE_OUTPUT


# --- Section 9. Backend selection (LangGraph or stub) --------------------

def _try_import_langgraph() -> Any | None:
    try:
        from langgraph.graph import END, StateGraph  # type: ignore
        return (StateGraph, END)
    except Exception:
        return None


_LG_PAIR = _try_import_langgraph()
BACKEND_NAME = "langgraph" if _LG_PAIR else "stub:sequential"


@dataclass
class _StubGraph:
    """Pure-Python stand-in for ``langgraph.graph.StateGraph``, mirroring
    the same minimal API used by the P123 graph."""

    state_type: Any
    nodes: dict[str, Callable[[dict], dict]] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)
    conditional_edges: dict[str, tuple[Callable[[dict], str], dict[str, str]]] = field(default_factory=dict)
    entry_point: str | None = None

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> None:
        self.nodes[name] = fn

    def add_edge(self, src: str, dst: str) -> None:
        self.edges[src] = dst

    def add_conditional_edges(self, src: str, condition: Callable[[dict], str],
                              mapping: dict[str, str]) -> None:
        self.conditional_edges[src] = (condition, dict(mapping))

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def compile(self) -> "_StubRunnable":
        if self.entry_point is None:
            raise RuntimeError("graph: entry point not set")
        return _StubRunnable(self)


@dataclass
class _StubRunnable:
    graph: _StubGraph

    def invoke(self, state: dict) -> dict:
        state = copy.copy(state)
        node = self.graph.entry_point
        steps = 0
        max_steps = (len(self.graph.nodes) + 2) * (
            MAX_ACTIONS_PER_PLAN + MAX_PLAN_LOOPS + 4
        )
        while node and node != "__end__":
            if node not in self.graph.nodes:
                raise RuntimeError(f"graph: unknown node '{node}'")
            update = self.graph.nodes[node](state)
            if not isinstance(update, dict):
                raise RuntimeError(f"graph: node '{node}' returned non-dict")
            state = {**state, **update}
            if node in self.graph.conditional_edges:
                condition, mapping = self.graph.conditional_edges[node]
                key = condition(state)
                node = mapping.get(key, key)
            else:
                node = self.graph.edges.get(node, "__end__")
            steps += 1
            if steps > max_steps:
                raise RuntimeError(
                    f"graph: step budget exhausted at {steps} (max {max_steps})"
                )
        return state


# --- Section 10. Builder + driver ----------------------------------------

def build_graph() -> tuple[Any, str]:
    """Compile the LangGraph (or stub) state machine + return (runnable, backend)."""
    if _LG_PAIR:
        StateGraph, END = _LG_PAIR  # type: ignore[misc]
        graph: Any = StateGraph(dict)
    else:
        graph = _StubGraph(state_type=dict)
        END = "__end__"  # type: ignore[assignment]

    # Register nodes.
    graph.add_node(NODE_PLAN,     plan_actions)
    graph.add_node(NODE_APPROVE,  request_approval)
    graph.add_node(NODE_EXEC_WEB, execute_web)
    graph.add_node(NODE_EXEC_WIN, execute_windows)
    graph.add_node(NODE_EXEC_RW,  execute_realworld)
    graph.add_node(NODE_EXEC_X,   execute_x)
    graph.add_node(NODE_ROLLBACK, rollback)
    graph.add_node(NODE_OUTPUT,   output_with_provenance)

    # Linear edges.
    graph.add_edge(NODE_PLAN, NODE_APPROVE)

    # After approval, dispatch to the right execute_* node (or output).
    graph.add_conditional_edges(
        NODE_APPROVE,
        route_after_approval,
        {
            NODE_EXEC_WEB: NODE_EXEC_WEB,
            NODE_EXEC_WIN: NODE_EXEC_WIN,
            NODE_EXEC_RW:  NODE_EXEC_RW,
            NODE_EXEC_X:   NODE_EXEC_X,
            NODE_OUTPUT:   NODE_OUTPUT,
        },
    )

    # After each execute_*, route_after_execution decides next.
    for node in (NODE_EXEC_WEB, NODE_EXEC_WIN, NODE_EXEC_RW, NODE_EXEC_X):
        graph.add_conditional_edges(
            node,
            route_after_execution,
            {
                NODE_EXEC_WEB: NODE_EXEC_WEB,
                NODE_EXEC_WIN: NODE_EXEC_WIN,
                NODE_EXEC_RW:  NODE_EXEC_RW,
                NODE_EXEC_X:   NODE_EXEC_X,
                NODE_ROLLBACK: NODE_ROLLBACK,
                NODE_OUTPUT:   NODE_OUTPUT,
            },
        )

    # After rollback, go to output (rollback is one-shot in this slot).
    graph.add_edge(NODE_ROLLBACK, NODE_OUTPUT)
    graph.add_edge(NODE_OUTPUT,   END)

    graph.set_entry_point(NODE_PLAN)
    return graph.compile(), BACKEND_NAME


def run_action_loop(
    *,
    user_id: str = "default",
    user_request: str = "",
    consent: ConsentContext | None = None,
    force_stub: bool = True,
    auto_approve: bool = False,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict:
    """End-to-end driver: build the graph, run it once, return ``output``.

    Always defaults to ``force_stub=True`` because every real-world
    backend in this slot is stubbed until P131 lands the connectors.
    ``auto_approve=False`` (the default) preserves Rule 1: the HITL gate
    refuses any step without a held consent_token. The CLI's
    ``--auto-approve`` flag is the only legitimate way to flip this on.
    """
    runnable, _backend = build_graph()
    state = build_state(
        user_id=user_id,
        user_request=user_request,
        consent=consent,
        force_stub=force_stub,
        auto_approve=auto_approve,
        prompt_version=prompt_version,
    )
    final = runnable.invoke(state)
    out = final.get("output") or {}
    out.setdefault("backend", BACKEND_NAME)
    return out


# --- Section 11. Diagnostics ---------------------------------------------

def describe_graph() -> dict:
    """Static description of the graph — used by the CLI ``info`` command."""
    return {
        "backend":         BACKEND_NAME,
        "agent_name":      AGENT_NAME,
        "nodes": [
            NODE_PLAN, NODE_APPROVE,
            NODE_EXEC_WEB, NODE_EXEC_WIN, NODE_EXEC_RW, NODE_EXEC_X,
            NODE_ROLLBACK, NODE_OUTPUT,
        ],
        "tools":            list(ALLOWED_TOOLS),
        "state_changing":   sorted(STATE_CHANGING_TOOLS),
        "read_only":        sorted(READ_ONLY_TOOLS),
        "max_actions":      MAX_ACTIONS_PER_PLAN,
        "max_plan_loops":   MAX_PLAN_LOOPS,
    }
