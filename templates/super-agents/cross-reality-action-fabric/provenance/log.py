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
"""Local-first JSONL action provenance logger for Cross-Reality Action Fabric.

This module is the **audit-trail layer** of Super Agent #3. It captures
one :class:`ActionProvenanceRecord` per action, approval, rollback, and
graph-node execution per run, and appends it to a date-rolled JSONL
file under the user's Windows AppData folder.

Where Super Agent #2's P124 logger captured *one record per node*, this
logger captures *one record per Constitution-relevant event*, with an
extended schema specifically designed for the action fabric's six Rules:

- ``consent_token``      Rule 1 — every action's typed approval
- ``tool``               which of the 5 manifest-declared tools fired
- ``outcome``            "success" | "failure" | "aborted" | "rolled_back"
- ``cost_usd``           the cost the user actually incurred
- ``rollback_id``        Rule 3 — points at the matching rollback record
- ``rolled_back_from``   Rule 3 — reverse pointer (forward → rollback)
- ``rule_compliance``    explicit dict of {rule_n: True | False | "n/a"}

Local-first by design (Rule 6):

- One JSONL file per UTC day at
  ``$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\
  provenance\\YYYY-MM-DD.jsonl``.
- Append-only — the logger never opens an existing file in write mode.
- PII redacted at write time via :func:`graph.redact_pii` (the same
  engine the connectors use).
- Pure-Python: no external service is contacted from this module.
  Cloud observability is opt-in and lives in
  :mod:`provenance.langfuse_hooks`.

Public surface:

- :class:`ActionProvenanceRecord`     extended JSONL schema
- :class:`LocalProvenanceLogger`      append + query API
- :func:`get_default_logger`          process-wide cached singleton
- :func:`export_audit_report`         Markdown audit report with full
                                       rollback chains (forward + reverse
                                       links between every action and its
                                       eventual rollback)
- :func:`summarise_run`                compact per-run digest

Built to help xAI and Grok win — a Super Agent that acts on the user's
machine MUST keep an honest, queryable, local-only audit trail. Without
that, it's a liability; with it, it's a tool the user can trust.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Reuse P129 primitives directly. Absolute import because the parent
# folder name (``cross-reality-action-fabric``) contains hyphens.
from graph import (  # type: ignore
    appdata_root,
    redact_pii,
)

__all__ = [
    "ActionProvenanceRecord",
    "LocalProvenanceLogger",
    "provenance_root",
    "current_log_path",
    "log_path_for",
    "get_default_logger",
    "reset_default_logger",
    "export_audit_report",
    "summarise_run",
    "make_run_id",
    "make_action_id",
    "make_rollback_id",
    "EVENT_KINDS",
    "ROLLBACK_OUTCOME",
    "ALL_RULE_NUMBERS",
]


# --- Section 1. Constants and paths --------------------------------------

#: Every event the action-fabric logger knows how to write.
EVENT_KINDS: tuple[str, ...] = (
    "plan_built",
    "approval_granted",
    "approval_refused",
    "action_executed",
    "action_failed",
    "rollback_executed",
    "rollback_failed",
    "node_step",        # one row per LangGraph node execution
    "run_complete",
)

#: Outcome string we tag rollback rows with — kept as a constant so the
#: Markdown report can scan for it without string matching elsewhere.
ROLLBACK_OUTCOME = "rolled_back"

#: The six Constitution Rules from P128's constitution.md, in the order
#: they appear in that file. Used by the rule_compliance dict.
ALL_RULE_NUMBERS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)

_ISO_FMT = "%Y-%m-%d"
_DATE_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.jsonl$")


def provenance_root() -> Path:
    """Filesystem location for the daily JSONL files."""
    return appdata_root() / "provenance"


def log_path_for(date_iso: str) -> Path:
    """Path of the JSONL file for one UTC day (``YYYY-MM-DD``)."""
    safe = "".join(c for c in date_iso if c.isdigit() or c == "-")
    if not safe:
        raise ValueError(f"invalid date_iso: {date_iso!r}")
    return provenance_root() / f"{safe}.jsonl"


def current_log_path() -> Path:
    """Path of the JSONL file for today (UTC)."""
    return log_path_for(datetime.now(timezone.utc).strftime(_ISO_FMT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    """One run = one CLI invocation = one full graph traversal."""
    return f"crf-run-{uuid.uuid4().hex[:12]}"


def make_action_id() -> str:
    """One action = one execute_* dispatch on a single step."""
    return f"crf-act-{uuid.uuid4().hex[:12]}"


def make_rollback_id() -> str:
    """One rollback = one Rule-3 reversal of a forward action."""
    return f"crf-rb-{uuid.uuid4().hex[:12]}"


def _date_jsonl_files(root: Path) -> list[Path]:
    """List date-named JSONL files (YYYY-MM-DD.jsonl) so the reader never
    accidentally parses sibling files in the same dir (e.g. the Langfuse
    stub trace)."""
    try:
        return sorted(
            p for p in root.glob("*.jsonl")
            if _DATE_FILENAME_RE.match(p.name)
        )
    except OSError:
        return []


# --- Section 2. ActionProvenanceRecord schema ---------------------------

@dataclass
class ActionProvenanceRecord:
    """One JSONL row.  Schema is intentionally tight and stable.

    Every event the action fabric emits — plan built, approval granted /
    refused, action executed / failed, rollback executed / failed, node
    step, run complete — conforms to this dataclass.
    """

    record_id:        str
    run_id:           str
    user_id:          str
    event_kind:       str            # one of EVENT_KINDS
    timestamp:        str
    plan_id:          str | None
    step:             int | None
    tool:             str | None
    action_id:        str | None     # populated for action_* and rollback_* rows
    consent_token:    str | None     # Rule 1
    outcome:          str | None     # success / failure / aborted / rolled_back
    cost_usd:         float
    duration_ms:      float | None
    rollback_id:      str | None     # Rule 3 — points to the rollback row
    rolled_back_from: str | None     # Rule 3 — reverse pointer (action_id)
    inputs_redacted:  dict
    outputs_redacted: dict
    rule_compliance:  dict           # {rule_n: True | False | "n/a" | reason str}
    stub_reason:      str | None
    error:            str | None
    correlation_id:   str | None
    backend:          str = "local-jsonl"
    schema_version:   str = "p131.v1"
    extra:            dict = field(default_factory=dict)

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)

    @classmethod
    def from_jsonl(cls, line: str) -> "ActionProvenanceRecord":
        data = json.loads(line)
        return cls(
            record_id=str(data.get("record_id") or ""),
            run_id=str(data.get("run_id") or ""),
            user_id=str(data.get("user_id") or ""),
            event_kind=str(data.get("event_kind") or ""),
            timestamp=str(data.get("timestamp") or ""),
            plan_id=data.get("plan_id"),
            step=data.get("step"),
            tool=data.get("tool"),
            action_id=data.get("action_id"),
            consent_token=data.get("consent_token"),
            outcome=data.get("outcome"),
            cost_usd=float(data.get("cost_usd") or 0.0),
            duration_ms=data.get("duration_ms"),
            rollback_id=data.get("rollback_id"),
            rolled_back_from=data.get("rolled_back_from"),
            inputs_redacted=dict(data.get("inputs_redacted") or {}),
            outputs_redacted=dict(data.get("outputs_redacted") or {}),
            rule_compliance=dict(data.get("rule_compliance") or {}),
            stub_reason=data.get("stub_reason"),
            error=data.get("error"),
            correlation_id=data.get("correlation_id"),
            backend=str(data.get("backend") or "local-jsonl"),
            schema_version=str(data.get("schema_version") or "p131.v1"),
            extra=dict(data.get("extra") or {}),
        )


# --- Section 3. Rule-compliance evaluator -------------------------------

def _evaluate_rules(
    *,
    event_kind: str,
    consent_token: str | None,
    tool: str | None,
    rollback_id: str | None,
    rollback_script: str | None,
    script: str | None,
    error: str | None,
    state_changing_tools: frozenset[str],
) -> dict:
    """Best-effort per-event Rule-compliance map.

    The compliance values are deliberately strings/booleans so the
    Markdown report can render them as a one-glance status table:

    - ``True``        Rule satisfied for this event
    - ``False``       Rule violated (with a hint in the field name)
    - ``"n/a"``       Rule doesn't apply to this event kind
    """
    rc: dict[str, Any] = {f"rule_{n}": "n/a" for n in ALL_RULE_NUMBERS}

    # Rule 1 — Human approval required for every action / approval event.
    if event_kind in ("action_executed", "action_failed", "approval_granted"):
        rc["rule_1"] = bool(consent_token)
    elif event_kind == "approval_refused":
        # Refusal is itself a Rule-1 success (the gate did its job).
        rc["rule_1"] = True
    elif event_kind in ("rollback_executed", "rollback_failed"):
        rc["rule_1"] = True   # rollback is auto-authorized by the original consent
    else:
        rc["rule_1"] = "n/a"

    # Rule 2 — Provenance mandatory: this record IS the provenance.
    rc["rule_2"] = True

    # Rule 3 — Verbatim rollback for state-changing tools.
    # We check whether the *plan step* carries a non-empty rollback
    # snippet, NOT the rollback_id (which is only populated on rollback
    # rows). The rollback_id presence on a forward action would mean
    # the rollback already fired — a different and rarer condition.
    if (
        event_kind in ("action_executed", "action_failed")
        and tool in state_changing_tools
    ):
        rc["rule_3"] = bool((rollback_script or "").strip())
    elif event_kind in ("rollback_executed", "rollback_failed"):
        rc["rule_3"] = True   # the row itself proves the rollback exists
    else:
        rc["rule_3"] = "n/a"

    # Rule 4 — No silent contradiction resolution. Best-effort: this
    # event-level logger doesn't see contradictions, but we don't
    # falsely claim compliance either.
    rc["rule_4"] = "n/a"

    # Rule 5 — Windows-only execution. We sniff the script for unix
    # leaks at write time (defence in depth — request_approval already
    # blocks these in the graph).
    bad = ("bash -c", "sh -c", "osascript", "wsl.exe", "/usr/bin/",
           "/bin/bash", " sudo ", "/etc/", "/var/", "/Applications/")
    if isinstance(script, str) and any(b in script for b in bad):
        rc["rule_5"] = False
    elif tool == "windows_local":
        rc["rule_5"] = True
    else:
        rc["rule_5"] = "n/a"

    # Rule 6 — Privacy-first. The redactor runs unconditionally on
    # inputs/outputs at write time, so this is True for every record.
    rc["rule_6"] = True

    return rc


# --- Section 4. LocalProvenanceLogger -----------------------------------

# State-changing tools partition (mirrors the P129 graph constant).
# Imported here lazily so we don't create a circular import.
def _state_changing_tools() -> frozenset[str]:
    try:
        from graph import STATE_CHANGING_TOOLS  # type: ignore
        return STATE_CHANGING_TOOLS
    except Exception:
        return frozenset({"web_via_stagehand", "windows_local"})


class LocalProvenanceLogger:
    """Append-only JSONL audit logger for the Cross-Reality Action Fabric."""

    def __init__(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        root: Path | None = None,
    ) -> None:
        self._user_id = user_id or "default"
        self._run_id  = run_id or make_run_id()
        self._root    = root or provenance_root()
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def run_id(self) -> str:
        return self._run_id

    def new_run(self, run_id: str | None = None) -> str:
        with self._lock:
            self._run_id = run_id or make_run_id()
        return self._run_id

    # -- Write side --------------------------------------------------------

    def log_event(
        self,
        *,
        event_kind: str,
        plan_id: str | None = None,
        step: int | None = None,
        tool: str | None = None,
        action_id: str | None = None,
        consent_token: str | None = None,
        outcome: str | None = None,
        cost_usd: float = 0.0,
        duration_ms: float | None = None,
        rollback_id: str | None = None,
        rolled_back_from: str | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        script: str | None = None,
        rollback_script: str | None = None,
        stub_reason: str | None = None,
        error: str | None = None,
        correlation_id: str | None = None,
        extra: dict | None = None,
    ) -> ActionProvenanceRecord:
        """Persist one ActionProvenanceRecord and return it."""
        if event_kind not in EVENT_KINDS:
            raise ValueError(
                f"unknown event_kind {event_kind!r} — must be one of {EVENT_KINDS}"
            )
        rule_compliance = _evaluate_rules(
            event_kind=event_kind,
            consent_token=consent_token,
            tool=tool,
            rollback_id=rollback_id,
            rollback_script=rollback_script,
            script=script,
            error=error,
            state_changing_tools=_state_changing_tools(),
        )
        record = ActionProvenanceRecord(
            record_id=f"prv-{uuid.uuid4().hex[:16]}",
            run_id=self._run_id,
            user_id=self._user_id,
            event_kind=event_kind,
            timestamp=_now_iso(),
            plan_id=plan_id,
            step=int(step) if step is not None else None,
            tool=tool,
            action_id=action_id,
            consent_token=consent_token,
            outcome=outcome,
            cost_usd=float(cost_usd or 0.0),
            duration_ms=float(duration_ms) if duration_ms is not None else None,
            rollback_id=rollback_id,
            rolled_back_from=rolled_back_from,
            inputs_redacted=redact_pii(dict(inputs or {})),
            outputs_redacted=redact_pii(dict(outputs or {})),
            rule_compliance=rule_compliance,
            stub_reason=stub_reason,
            error=error,
            correlation_id=correlation_id,
            extra=dict(extra or {}),
        )
        return self._append(record)

    def log_record(self, record: ActionProvenanceRecord) -> ActionProvenanceRecord:
        """Persist a pre-built record (used by the wrapper in __init__.py)."""
        return self._append(record)

    def _append(self, record: ActionProvenanceRecord) -> ActionProvenanceRecord:
        path = log_path_for(record.timestamp.split("T", 1)[0])
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(record.to_jsonl() + "\n")
        return record

    # -- Bulk-ingest from a P129 graph output -----------------------------

    def record_run(self, out: dict) -> dict:
        """Walk a P129 :func:`graph.run_action_loop` output and emit one
        ActionProvenanceRecord per event.

        Returns a dict of per-event-kind counters so the caller can
        render them into a UI badge.
        """
        if not isinstance(out, dict):
            return {k: 0 for k in EVENT_KINDS}

        plan        = out.get("plan") or {}
        plan_id     = plan.get("plan_id")
        executions  = out.get("executions")  or []
        rollbacks   = out.get("rollbacks")   or []
        violations  = out.get("violations")  or []
        prov        = out.get("provenance")  or {}
        proposed    = plan.get("proposed_actions") or []

        force_stub = bool(prov.get("force_stub"))
        stub_reason = ("force_stub mode (offline backends)"
                       if force_stub else None)

        counters: dict[str, int] = {k: 0 for k in EVENT_KINDS}

        # plan_built — one record per plan.
        if plan_id:
            self.log_event(
                event_kind="plan_built",
                plan_id=plan_id,
                stub_reason=stub_reason,
                inputs={"user_request": plan.get("user_request")},
                outputs={
                    "action_count":  len(proposed),
                    "tools":         [s.get("tool") for s in proposed],
                },
            )
            counters["plan_built"] += 1

        # approval_granted / approval_refused — one per step.
        for s in proposed:
            if s.get("consent_token"):
                self.log_event(
                    event_kind="approval_granted",
                    plan_id=plan_id, step=s.get("step"),
                    tool=s.get("tool"),
                    consent_token=s.get("consent_token"),
                    stub_reason=stub_reason,
                )
                counters["approval_granted"] += 1
            elif s.get("refusal_reason"):
                self.log_event(
                    event_kind="approval_refused",
                    plan_id=plan_id, step=s.get("step"),
                    tool=s.get("tool"),
                    error=s.get("refusal_reason"),
                    stub_reason=stub_reason,
                )
                counters["approval_refused"] += 1

        # action_executed / action_failed — one per execution row.
        action_id_by_step: dict[int, str] = {}
        for r in executions:
            step_idx = r.get("step")
            tool = r.get("tool")
            action_id = make_action_id()
            if step_idx is not None:
                action_id_by_step[int(step_idx)] = action_id
            event_kind = "action_executed" if r.get("ok") else "action_failed"
            matched_step = next(
                (s for s in proposed if s.get("step") == step_idx), None,
            )
            cost = float((matched_step or {}).get("expected_cost_usd") or 0.0)
            self.log_event(
                event_kind=event_kind,
                plan_id=plan_id,
                step=step_idx,
                tool=tool,
                action_id=action_id,
                consent_token=(matched_step or {}).get("consent_token"),
                outcome=r.get("outcome"),
                cost_usd=cost,
                rollback_id=None,
                inputs={"description": (matched_step or {}).get("description")},
                outputs={"result": r},
                script=(matched_step or {}).get("script"),
                rollback_script=(matched_step or {}).get("rollback"),
                stub_reason=stub_reason,
                error=r.get("reason") if not r.get("ok") else None,
            )
            counters[event_kind] += 1

        # rollback_executed / rollback_failed — one per rollback row,
        # cross-linked to its forward action via rolled_back_from.
        # When the in-memory map doesn't have the step (because the
        # forward action was logged in a *prior* record_run call —
        # the canonical CLI rollback flow), fall back to scanning the
        # JSONL log for the most recent matching action_executed.
        for r in rollbacks:
            step_idx = r.get("step")
            tool = r.get("tool")
            forward_action_id = (
                action_id_by_step.get(int(step_idx))
                if step_idx is not None else None
            )
            if forward_action_id is None:
                forward_action_id = self._find_prior_action_id(
                    plan_id=plan_id, step=step_idx, tool=tool,
                )
            rollback_id = make_rollback_id()
            event_kind = (
                "rollback_executed" if r.get("outcome") == ROLLBACK_OUTCOME
                else "rollback_failed"
            )
            self.log_event(
                event_kind=event_kind,
                plan_id=plan_id,
                step=step_idx,
                tool=tool,
                action_id=rollback_id,
                consent_token=None,
                outcome=r.get("outcome"),
                cost_usd=0.0,
                rollback_id=rollback_id,
                rolled_back_from=forward_action_id,
                inputs={"rollback_script": r.get("rollback")},
                outputs={"result": r},
                stub_reason=stub_reason,
                error=r.get("reason"),
            )
            counters[event_kind] += 1

        # run_complete — one final record summarising the whole run.
        self.log_event(
            event_kind="run_complete",
            plan_id=plan_id,
            inputs={
                "violation_count": len(violations),
                "successful":      int(prov.get("successful") or 0),
                "aborted":         int(prov.get("aborted") or 0),
            },
            outputs={
                "started_at":    prov.get("started_at"),
                "finished_at":   prov.get("finished_at"),
                "cost_usd_total": float(prov.get("cost_usd") or 0.0),
            },
            cost_usd=float(prov.get("cost_usd") or 0.0),
            stub_reason=stub_reason,
        )
        counters["run_complete"] += 1
        return counters

    # -- Read side ---------------------------------------------------------

    def query_by_date(self, date_iso: str) -> list[ActionProvenanceRecord]:
        path = log_path_for(date_iso)
        if not path.exists():
            return []
        return list(self._read_lines(path))

    def query_by_run_id(self, run_id: str) -> list[ActionProvenanceRecord]:
        out: list[ActionProvenanceRecord] = []
        for path in _date_jsonl_files(self._root):
            for rec in self._read_lines(path):
                if rec.run_id == run_id:
                    out.append(rec)
        return out

    def query_by_action_type(self, tool: str) -> list[ActionProvenanceRecord]:
        out: list[ActionProvenanceRecord] = []
        for path in _date_jsonl_files(self._root):
            for rec in self._read_lines(path):
                if rec.tool == tool:
                    out.append(rec)
        return out

    def query_by_event_kind(self, event_kind: str) -> list[ActionProvenanceRecord]:
        out: list[ActionProvenanceRecord] = []
        for path in _date_jsonl_files(self._root):
            for rec in self._read_lines(path):
                if rec.event_kind == event_kind:
                    out.append(rec)
        return out

    def latest_run(self) -> list[ActionProvenanceRecord]:
        """Return every record from the most recent run on disk."""
        run_id: str | None = None
        for path in sorted(_date_jsonl_files(self._root), reverse=True):
            recs = list(self._read_lines(path))
            if not recs:
                continue
            run_id = recs[-1].run_id
            break
        return self.query_by_run_id(run_id) if run_id else []

    def list_runs(self) -> list[str]:
        seen: dict[str, str] = {}
        for path in _date_jsonl_files(self._root):
            for rec in self._read_lines(path):
                if rec.run_id and rec.run_id not in seen:
                    seen[rec.run_id] = rec.timestamp
        return [
            rid for rid, _ts in
            sorted(seen.items(), key=lambda kv: kv[1], reverse=True)
        ]

    def _find_prior_action_id(
        self,
        *,
        plan_id: str | None,
        step: int | None,
        tool: str | None,
    ) -> str | None:
        """Scan the JSONL log for the most-recent action_executed record
        matching ``plan_id`` + ``step`` + ``tool``. Used to wire up the
        rollback ↔ forward action link across separate ``record_run``
        calls (the canonical CLI rollback-last flow)."""
        if step is None:
            return None
        for path in sorted(_date_jsonl_files(self._root), reverse=True):
            for rec in reversed(list(self._read_lines(path))):
                if rec.event_kind != "action_executed":
                    continue
                if rec.step != int(step):
                    continue
                if tool is not None and rec.tool != tool:
                    continue
                if plan_id is not None and rec.plan_id != plan_id:
                    continue
                return rec.action_id
        return None

    @staticmethod
    def _read_lines(path: Path) -> Iterable[ActionProvenanceRecord]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield ActionProvenanceRecord.from_jsonl(line)
                    except (ValueError, KeyError, TypeError):
                        continue
        except OSError:
            return


# --- Section 5. Process-wide singleton ----------------------------------

_DEFAULT_LOCK = threading.Lock()
_DEFAULT_LOGGER: LocalProvenanceLogger | None = None


def get_default_logger(
    *,
    user_id: str = "default",
    refresh: bool = False,
) -> LocalProvenanceLogger:
    """Cached default logger.  ``refresh=True`` rebuilds the singleton."""
    global _DEFAULT_LOGGER
    with _DEFAULT_LOCK:
        if (
            refresh
            or _DEFAULT_LOGGER is None
            or _DEFAULT_LOGGER.user_id != user_id
        ):
            _DEFAULT_LOGGER = LocalProvenanceLogger(user_id=user_id)
    return _DEFAULT_LOGGER


def reset_default_logger() -> None:
    global _DEFAULT_LOGGER
    with _DEFAULT_LOCK:
        _DEFAULT_LOGGER = None


# --- Section 6. Markdown audit export ----------------------------------

_REPORT_HEADER = (
    "# Cross-Reality Action Fabric — Action Provenance Audit\n"
    "\n"
    "Built to help xAI and Grok win. This report is generated locally on\n"
    "your Windows machine and never leaves it unless you opt in to Langfuse\n"
    "(off by default — see `provenance.langfuse_hooks`).\n"
    "\n"
)


def summarise_run(records: list[ActionProvenanceRecord]) -> dict:
    """Compact per-run summary used by the Markdown report and the CLI."""
    if not records:
        return {
            "run_id":            None,
            "started_at":        None,
            "finished_at":       None,
            "event_count":       0,
            "tools_used":        [],
            "stub":              False,
            "errors":            [],
            "outcomes":          {},
            "rule_violations":   [],
            "user_id":           None,
            "rollback_chain":    [],
            "cost_usd_total":    0.0,
        }
    tools_used: set[str] = set()
    errors: list[str] = []
    outcomes: dict[str, int] = {}
    rule_violations: list[str] = []
    rollback_chain: list[dict] = []
    stub_run = False
    cost_total = 0.0
    by_action_id: dict[str, ActionProvenanceRecord] = {}

    for r in records:
        if r.tool:
            tools_used.add(r.tool)
        if r.error:
            errors.append(f"{r.event_kind}: {r.error}")
        if r.outcome:
            outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1
        if r.stub_reason:
            stub_run = True
        if r.cost_usd:
            cost_total += float(r.cost_usd)
        for k, v in (r.rule_compliance or {}).items():
            if v is False:
                rule_violations.append(f"{r.event_kind} step {r.step}: {k}=False")
        if r.action_id:
            by_action_id[r.action_id] = r

    # Build the rollback chain — pair every rollback row with its forward
    # action via rolled_back_from.
    for r in records:
        if r.event_kind == "rollback_executed" and r.rolled_back_from:
            forward = by_action_id.get(r.rolled_back_from)
            rollback_chain.append({
                "forward_action_id": r.rolled_back_from,
                "forward_tool":      forward.tool if forward else None,
                "forward_step":      forward.step if forward else None,
                "rollback_id":       r.rollback_id,
                "rollback_step":     r.step,
                "rollback_outcome":  r.outcome,
                "timestamp":         r.timestamp,
            })

    return {
        "run_id":           records[0].run_id,
        "started_at":       records[0].timestamp,
        "finished_at":      records[-1].timestamp,
        "event_count":      len(records),
        "tools_used":       sorted(tools_used),
        "stub":             stub_run,
        "errors":           errors,
        "outcomes":         outcomes,
        "rule_violations":  rule_violations,
        "user_id":          records[0].user_id,
        "rollback_chain":   rollback_chain,
        "cost_usd_total":   round(cost_total, 4),
    }


def export_audit_report(
    *,
    date_iso: str | None = None,
    run_id: str | None = None,
    tool: str | None = None,
    logger: LocalProvenanceLogger | None = None,
) -> str:
    """Build a Markdown audit report with full rollback chains.

    Pass at most one filter (``date_iso`` / ``run_id`` / ``tool``); if all
    three are None the report covers the most recent run on disk.
    """
    log = logger or get_default_logger()
    if run_id:
        records = log.query_by_run_id(run_id)
        scope = f"run `{run_id}`"
    elif tool:
        records = log.query_by_action_type(tool)
        scope = f"tool `{tool}`"
    elif date_iso:
        records = log.query_by_date(date_iso)
        scope = f"date `{date_iso}`"
    else:
        records = log.latest_run()
        scope = "latest run"

    summary = summarise_run(records)
    lines: list[str] = []
    lines.append(_REPORT_HEADER.rstrip())
    lines.append(f"## Audit scope: {scope}")
    lines.append("")
    lines.append(f"- Run ID: `{summary['run_id']}`")
    lines.append(f"- User ID: `{summary['user_id']}`")
    lines.append(f"- Started: `{summary['started_at']}`")
    lines.append(f"- Finished: `{summary['finished_at']}`")
    lines.append(f"- Event count: **{summary['event_count']}**")
    lines.append(
        f"- Tools used: "
        f"{', '.join(f'`{t}`' for t in summary['tools_used']) or '_none_'}"
    )
    lines.append(f"- Stub run: **{summary['stub']}**")
    lines.append(f"- Cost USD total: **{summary['cost_usd_total']:.4f}**")
    if summary["outcomes"]:
        bits = [f"{k}={v}" for k, v in sorted(summary["outcomes"].items())]
        lines.append(f"- Outcomes: {', '.join(bits)}")
    if summary["rule_violations"]:
        lines.append("- Rule violations surfaced:")
        for v in summary["rule_violations"]:
            lines.append(f"  - {v}")
    if summary["errors"]:
        lines.append("- Errors:")
        for e in summary["errors"]:
            lines.append(f"  - {e}")
    lines.append("")

    # --- Rollback chain section --------------------------------------------
    lines.append("## Rollback chain (forward action ↔ rollback)")
    lines.append("")
    chain = summary["rollback_chain"]
    if not chain:
        lines.append("_No rollbacks recorded for this scope._")
    else:
        lines.append(
            "| # | Forward action | Forward tool | Forward step | "
            "Rollback ID | Rollback outcome | Timestamp |"
        )
        lines.append(
            "|---|----------------|--------------|--------------|"
            "-------------|------------------|-----------|"
        )
        for i, c in enumerate(chain, 1):
            lines.append(
                f"| {i} | `{c['forward_action_id']}` | "
                f"`{c['forward_tool']}` | {c['forward_step']} | "
                f"`{c['rollback_id']}` | {c['rollback_outcome']} | "
                f"`{c['timestamp']}` |"
            )
    lines.append("")

    # --- Per-event trail section ------------------------------------------
    lines.append("## Per-event trail")
    lines.append("")
    if not records:
        lines.append("_No records matched the requested filter._")
    else:
        lines.append(
            "| # | Event | Step | Tool | Outcome | Consent | "
            "Cost USD | Stub | Error |"
        )
        lines.append(
            "|---|-------|------|------|---------|---------|"
            "----------|------|-------|"
        )
        for i, r in enumerate(records, 1):
            err = (r.error or "_none_").replace("|", "\\|")
            stub = "yes" if r.stub_reason else "no"
            consent = "yes" if r.consent_token else "no"
            outcome = r.outcome or "_none_"
            lines.append(
                f"| {i} | `{r.event_kind}` | {r.step or ''} | "
                f"`{r.tool or ''}` | {outcome} | {consent} | "
                f"{r.cost_usd:.4f} | {stub} | {err} |"
            )
    lines.append("")
    lines.append(f"_Report generated at {_now_iso()}._")
    lines.append("")
    return "\n".join(lines)
