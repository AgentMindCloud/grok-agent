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
"""Cross-Reality Action Fabric — CLI entry point.

This is the user-visible binary for Super Agent #3. It exposes a
PowerShell-friendly CLI that drives the LangGraph orchestration core
(``graph.py``) and enforces the six Constitution Rules from P128's
``constitution.md``.

Subcommands
-----------

- ``daily-plan``         Build a fresh plan of proposed actions for today
                         and run the full HITL → execute → output loop.
                         Use ``--stub`` (default ON) to keep the run
                         offline; use ``--auto-approve`` only in CI to
                         skip the typed-approval prompt.
- ``execute-action``     Run a single ad-hoc request through the loop
                         (the canonical path for "Grok says do X").
- ``search``             Run the read-only ``x_search`` tool and print
                         hits — no consent token needed.
- ``approve-pending``    Print the pending plan with a numbered approval
                         prompt; on input, mints a consent_token per
                         step and re-invokes the graph.
- ``rollback-last``      Find the most-recent successful state-changing
                         action and run its verbatim rollback snippet.
- ``info``               Print the graph description (nodes, tools,
                         backend selection).
- ``version``            Print agent + backend versions.

Run on Windows
--------------

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python agent.py daily-plan --stub

Local-first by design: every state file lives under
``$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\`` (Windows)
or the XDG fallback (CI). No third-party services are contacted unless
the user opts in.

Built to make Grok the obvious choice for every agent on X — Cross-
Reality Action Fabric is the missing "do something for me" layer that
turns a Grok conversation into something a non-technical creator can
trust at the OS level.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the script's own folder is on sys.path when invoked via
# ``python agent.py ...`` (the parent folder name uses hyphens and
# cannot be a Python package identifier — same situation as Super
# Agent #2's CLI).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import graph as _graph  # type: ignore  # noqa: E402
from graph import (  # type: ignore  # noqa: E402
    ALLOWED_TOOLS,
    BACKEND_NAME,
    ConsentContext,
    ConstitutionViolation,
    READ_ONLY_TOOLS,
    STATE_CHANGING_TOOLS,
    appdata_root,
    describe_graph,
    make_consent_token,
)


__all__ = [
    "AGENT_NAME",
    "AGENT_VERSION",
    "build_default_consent",
    "daily_plan",
    "execute_action",
    "search",
    "approve_pending",
    "rollback_last",
    "info",
    "log_path",
    "main",
]


# --- Section 1. Constants -------------------------------------------------

AGENT_NAME    = "cross-reality-action-fabric"
AGENT_VERSION = "0.1.0"


def log_path() -> Path:
    """Append-only run-log path for every CLI invocation."""
    return appdata_root() / "logs" / "agent.log"


def pending_plan_path() -> Path:
    """Where the most-recent plan awaiting approval lives on disk."""
    return appdata_root() / "pending_plan.json"


def runs_dir() -> Path:
    """Where each completed run's output dict is persisted."""
    return appdata_root() / "runs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Section 2. Consent helpers ------------------------------------------

# Every per-tool gate name the runtime references at HITL time. The names
# match the manifest's ``constitution.consent_gates`` list verbatim.
ALL_GATES = (
    "publish_to_x",
    "send_dm",
    "move_funds",
    "pay_real_money",
    "export_tax_report",
    "sync_to_cloud",
    "modify_local_files_outside_appdata",
    "publish_synthesis",
    "run_powershell_local",
    "run_web_action",
    "read_calendar",
    "read_email",
)


def build_default_consent(
    *,
    auto_approve: bool = False,
    consent_token: str | None = None,
) -> ConsentContext:
    """Construct a consent context for a CLI session.

    By default the context is *empty* — every action requires a typed
    approval at the HITL prompt. Pass ``auto_approve=True`` only in
    automated runs (CI, smoke tests, the demo's ``--stub`` path); the
    flag holds every gate listed in :data:`ALL_GATES`.
    """
    if auto_approve:
        return ConsentContext.from_iterable(
            ALL_GATES,
            consent_token=consent_token or f"cli-auto-{_now_iso()}",
        )
    return ConsentContext(
        gates=frozenset(),
        consent_token=consent_token,
    )


# --- Section 3. Logging ---------------------------------------------------

def _log_run(action: str, payload: dict) -> None:
    """Append one JSON line to the agent's run-log (best-effort)."""
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":      _now_iso(),
        "action":  action,
        "agent":   AGENT_NAME,
        "version": AGENT_VERSION,
        "payload": payload,
    }
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def _persist_run(out: dict, *, run_id: str | None = None) -> Path | None:
    """Persist one run's output dict to disk for later inspection."""
    rid = run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    target = runs_dir() / f"{rid}.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(out, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return target
    except OSError:
        return None


def _persist_pending_plan(plan: dict) -> Path | None:
    """Stash the plan awaiting approval so ``approve-pending`` can load it."""
    target = pending_plan_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return target
    except OSError:
        return None


def _load_pending_plan() -> dict | None:
    target = pending_plan_path()
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _clear_pending_plan() -> None:
    target = pending_plan_path()
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass


# --- Section 4. Commands --------------------------------------------------

def daily_plan(
    *,
    user_id: str = "default",
    force_stub: bool = True,
    auto_approve: bool = False,
    quiet: bool = False,
) -> dict:
    """Build today's action plan and run the full LangGraph loop.

    With ``auto_approve=False`` the loop terminates after the HITL gate
    refuses unapproved steps; the unapproved plan is persisted to
    :func:`pending_plan_path` for ``approve-pending`` to pick up.
    """
    consent = build_default_consent(auto_approve=auto_approve)
    out = _graph.run_action_loop(
        user_id=user_id,
        user_request="(daily plan: today's proposed actions)",
        consent=consent,
        force_stub=force_stub,
        auto_approve=auto_approve,
    )
    out.setdefault("agent_name",    AGENT_NAME)
    out.setdefault("agent_version", AGENT_VERSION)
    _persist_run(out)
    plan = (out.get("plan") or {})
    if (out.get("violations") or []) and plan:
        _persist_pending_plan(plan)
    elif plan and any(
        not s.get("executed") for s in (plan.get("proposed_actions") or [])
    ):
        _persist_pending_plan(plan)
    else:
        _clear_pending_plan()

    _log_run("daily_plan", {
        "force_stub":      bool(force_stub),
        "auto_approve":    bool(auto_approve),
        "violation_count": len((out.get("violations") or [])),
        "executed":        (out.get("provenance") or {}).get("successful", 0),
        "aborted":         (out.get("provenance") or {}).get("aborted", 0),
        "backend":         out.get("backend"),
    })
    if not quiet:
        print(_format_run(out))
    return out


def execute_action(
    user_request: str,
    *,
    user_id: str = "default",
    force_stub: bool = True,
    auto_approve: bool = False,
    quiet: bool = False,
) -> dict:
    """Drive one ad-hoc user request end-to-end through the graph."""
    consent = build_default_consent(auto_approve=auto_approve)
    out = _graph.run_action_loop(
        user_id=user_id,
        user_request=str(user_request or "").strip(),
        consent=consent,
        force_stub=force_stub,
        auto_approve=auto_approve,
    )
    out.setdefault("agent_name",    AGENT_NAME)
    out.setdefault("agent_version", AGENT_VERSION)
    _persist_run(out)
    _log_run("execute_action", {
        "user_request":    out.get("plan", {}).get("user_request"),
        "force_stub":      bool(force_stub),
        "auto_approve":    bool(auto_approve),
        "violation_count": len((out.get("violations") or [])),
    })
    if not quiet:
        print(_format_run(out))
    return out


def search(
    query: str,
    *,
    limit: int = 10,
    force_stub: bool = True,
    quiet: bool = False,
) -> dict:
    """Read-only search via the ``x_search`` tool — no consent token required."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("search: query must be a non-empty string")
    # Read-only tools don't need consent; we still run the full graph so
    # the provenance trail records the search exactly like an action.
    consent = build_default_consent(auto_approve=True)
    out = _graph.run_action_loop(
        user_id="default",
        user_request=f"(search) {query[:200]} limit={int(limit)}",
        consent=consent,
        force_stub=force_stub,
        auto_approve=True,
    )
    out.setdefault("agent_name",    AGENT_NAME)
    out.setdefault("agent_version", AGENT_VERSION)
    _log_run("search", {
        "query":      query,
        "limit":      int(limit),
        "force_stub": bool(force_stub),
    })
    if not quiet:
        print(_format_run(out))
    return out


def approve_pending(
    *,
    accept_steps: list[int] | None = None,
    user_id: str = "default",
    force_stub: bool = True,
    quiet: bool = False,
) -> dict:
    """Approve the pending plan (typed at the HITL prompt) and re-run.

    ``accept_steps`` selects which step indices to approve; ``None``
    means "all remaining". This is the canonical typed-approval path —
    the runtime mints one consent_token per accepted step and re-invokes
    the graph from the start, which finds the pre-existing tokens and
    advances past the HITL gate cleanly.
    """
    pending = _load_pending_plan()
    if pending is None:
        if not quiet:
            print("No pending plan on disk. Run `python agent.py daily-plan --stub` first.")
        return {"approved": 0, "executed": 0, "no_pending": True}

    proposed = list(pending.get("proposed_actions") or [])
    accept_set = set(accept_steps) if accept_steps else None
    minted = 0
    for raw_step in proposed:
        idx = int(raw_step.get("step", 0))
        if accept_set is not None and idx not in accept_set:
            continue
        if raw_step.get("executed"):
            continue
        # The HITL refusal reason is "missing consent_token (HITL gate
        # blocked)" — clear it on approval so the re-run can proceed.
        # Other refusal reasons (Rule 3 / 5 / 6 violations) stay sticky.
        rr = raw_step.get("refusal_reason") or ""
        if rr and "consent_token" not in rr.lower():
            continue
        if rr:
            raw_step["refusal_reason"] = None
        if not raw_step.get("consent_token"):
            raw_step["consent_token"] = make_consent_token(
                scope=str(raw_step.get("tool", "tool"))
            )
            minted += 1

    pending["proposed_actions"] = proposed
    _persist_pending_plan(pending)

    # Re-run the graph from the start with the approved plan held in
    # state. The graph respects pre-existing consent_tokens (HITL gate
    # is a pass-through when tokens are already there), so the
    # execute_* nodes proceed cleanly.
    consent = build_default_consent(auto_approve=False)
    runnable, _backend = _graph.build_graph()
    state = _graph.build_state(
        user_id=user_id,
        user_request=str(pending.get("user_request") or ""),
        consent=consent,
        force_stub=force_stub,
        auto_approve=False,   # tokens are pre-attached to each step
    )
    state["plan"] = pending
    state["approvals"] = [
        {
            "step":          int(s.get("step", 0)),
            "consent_token": s.get("consent_token"),
            "tool":          s.get("tool"),
            "granted_at":    _now_iso(),
            "stub":          bool(force_stub),
        }
        for s in proposed if s.get("consent_token")
    ]
    final = runnable.invoke(state)
    out = final.get("output") or {}
    out.setdefault("agent_name",    AGENT_NAME)
    out.setdefault("agent_version", AGENT_VERSION)
    out.setdefault("backend",       BACKEND_NAME)
    _persist_run(out)
    if not (out.get("plan") or {}).get("proposed_actions") or all(
        s.get("executed") or s.get("refusal_reason")
        for s in (out.get("plan") or {}).get("proposed_actions") or []
    ):
        _clear_pending_plan()
    else:
        _persist_pending_plan(out["plan"])

    _log_run("approve_pending", {
        "minted_tokens": int(minted),
        "executed":      (out.get("provenance") or {}).get("successful", 0),
        "aborted":       (out.get("provenance") or {}).get("aborted", 0),
        "force_stub":    bool(force_stub),
    })
    if not quiet:
        print(_format_run(out))
    return {
        "approved": int(minted),
        "executed": (out.get("provenance") or {}).get("successful", 0),
        "output":   out,
    }


def rollback_last(
    *,
    user_id: str = "default",
    force_stub: bool = True,
    quiet: bool = False,
) -> dict:
    """Find the most-recent successful state-changing action on disk and
    run its verbatim rollback snippet. Implements Rule 3."""
    most_recent: Path | None = None
    target_run: dict | None = None
    if runs_dir().exists():
        candidates = sorted(runs_dir().glob("run-*.json"), reverse=True)
        for path in candidates:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for s in (data.get("plan") or {}).get("proposed_actions") or []:
                if (
                    s.get("executed")
                    and s.get("outcome") == "success"
                    and not s.get("rolled_back")
                    and s.get("tool") in STATE_CHANGING_TOOLS
                ):
                    most_recent = path
                    target_run = data
                    break
            if target_run is not None:
                break

    if target_run is None:
        if not quiet:
            print("No eligible state-changing action found in run history.")
        _log_run("rollback_last", {"found": False})
        return {"found": False, "rolled_back": 0}

    consent = build_default_consent(auto_approve=True)
    state = _graph.build_state(
        user_id=user_id,
        user_request="(rollback-last) revert most-recent state-changing action",
        consent=consent,
        force_stub=force_stub,
    )
    state["plan"] = target_run.get("plan") or {}
    # Run rollback + output directly (no plan / approve / execute — those
    # already happened in the prior run we're reverting).
    state.update(_graph.rollback(state))
    state.update(_graph.output_with_provenance(state))
    out = state.get("output") or {}
    out.setdefault("agent_name",    AGENT_NAME)
    out.setdefault("agent_version", AGENT_VERSION)
    out.setdefault("backend",       BACKEND_NAME)
    _persist_run(out)
    rolled = sum(
        1 for r in (out.get("rollbacks") or [])
        if r.get("outcome") == "rolled_back"
    )
    _log_run("rollback_last", {
        "found":        True,
        "rolled_back":  int(rolled),
        "source_run":   str(most_recent) if most_recent else None,
    })
    if not quiet:
        print(_format_run(out))
    return {
        "found":       True,
        "rolled_back": int(rolled),
        "output":      out,
    }


def info(*, quiet: bool = False) -> dict:
    """Static description of the graph + backend selection."""
    desc = describe_graph()
    desc["agent_name"]    = AGENT_NAME
    desc["agent_version"] = AGENT_VERSION
    desc["appdata_root"]  = str(appdata_root())
    desc["all_gates"]     = list(ALL_GATES)
    if not quiet:
        print(json.dumps(desc, indent=2, ensure_ascii=False, default=str))
    return desc


# --- Section 5. Output formatter -----------------------------------------

def _format_run(out: dict) -> str:
    plan        = out.get("plan") or {}
    actions     = plan.get("proposed_actions") or []
    executions  = out.get("executions") or []
    rollbacks   = out.get("rollbacks")  or []
    violations  = out.get("violations") or []
    prov        = out.get("provenance") or {}

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("Cross-Reality Action Fabric — Run Report")
    lines.append("=" * 70)
    lines.append(f"User ID:     {out.get('user_id')}")
    lines.append(f"Agent:       {out.get('agent_name')} v{out.get('agent_version')}")
    lines.append(f"Backend:     {out.get('backend')}")
    lines.append(f"Stub mode:   {out.get('stub')}")
    lines.append(f"Plan ID:     {plan.get('plan_id')}")
    lines.append(f"Started at:  {prov.get('started_at')}")
    lines.append(f"Finished at: {prov.get('finished_at')}")
    lines.append("-" * 70)

    if plan.get("refusal_reason"):
        lines.append(f"Plan refused: {plan['refusal_reason']}")
        lines.append("=" * 70)
        return "\n".join(lines)

    lines.append("Proposed actions:")
    for a in actions:
        flag = "OK" if a.get("executed") and a.get("outcome") == "success" else (
            "ROLL"  if a.get("rolled_back")
            else "REF"  if a.get("refusal_reason")
            else "PEND"
        )
        lines.append(
            f"  [{flag}] step {a.get('step')} · {a.get('tool')} · "
            f"{(a.get('description') or '')[:60]}"
        )
        if a.get("refusal_reason"):
            lines.append(f"         refusal: {a['refusal_reason']}")
    lines.append("")

    if executions:
        lines.append(f"Executed: {len(executions)} action(s)")
        for r in executions:
            lines.append(
                f"  - step {r.get('step')} · {r.get('tool')} · "
                f"{r.get('outcome')}"
            )
        lines.append("")

    if rollbacks:
        lines.append(f"Rollbacks: {len(rollbacks)}")
        for r in rollbacks:
            lines.append(
                f"  - step {r.get('step')} · {r.get('tool')} · "
                f"{r.get('outcome')}"
            )
        lines.append("")

    if violations:
        lines.append(f"Constitution violations surfaced: {len(violations)}")
        for v in violations:
            lines.append(
                f"  - rule {v.get('rule')} · {v.get('tool')} · {v.get('message')}"
            )
        lines.append("")

    lines.append(f"Successful:    {prov.get('successful', 0)}")
    lines.append(f"Aborted:       {prov.get('aborted', 0)}")
    lines.append(f"Cost USD:      {prov.get('cost_usd', 0.0):.2f}")
    lines.append(f"Trail entries: {len(prov.get('trail') or [])}")
    lines.append("=" * 70)
    return "\n".join(lines)


# --- Section 6. CLI parser + dispatch ------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description=(
            "Cross-Reality Action Fabric — Grok Agent OS Super Agent #3. "
            "Built to make Grok the obvious choice for every agent on X. "
            "Every real-world action requires a typed user approval."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser(
        "daily-plan",
        help="Build today's action plan and run the HITL → execute loop.",
    )
    p_plan.add_argument("--user-id", default="default")
    p_plan.add_argument("--stub",    action="store_true",
                        help="Force offline stub backends (default).")
    p_plan.add_argument("--no-stub", action="store_true",
                        help="Disable force_stub; requires real backends.")
    p_plan.add_argument("--auto-approve", action="store_true",
                        help="CI / smoke-test path — auto-mint consent tokens. Never use interactively.")
    p_plan.add_argument("--json",    action="store_true",
                        help="Print JSON output instead of the human report.")
    p_plan.add_argument("--quiet",   action="store_true")

    p_exec = sub.add_parser(
        "execute-action",
        help="Drive one ad-hoc user request through the action loop.",
    )
    p_exec.add_argument("request", help="Natural-language description of the action.")
    p_exec.add_argument("--user-id", default="default")
    p_exec.add_argument("--stub",    action="store_true")
    p_exec.add_argument("--no-stub", action="store_true")
    p_exec.add_argument("--auto-approve", action="store_true")
    p_exec.add_argument("--json",    action="store_true")
    p_exec.add_argument("--quiet",   action="store_true")

    p_search = sub.add_parser(
        "search",
        help="Read-only search via x_search (no consent token required).",
    )
    p_search.add_argument("query")
    p_search.add_argument("--limit",  type=int, default=10)
    p_search.add_argument("--stub",   action="store_true")
    p_search.add_argument("--no-stub", action="store_true")
    p_search.add_argument("--quiet",  action="store_true")

    p_appr = sub.add_parser(
        "approve-pending",
        help="Approve the pending plan and re-run the loop with consent tokens.",
    )
    p_appr.add_argument("--user-id", default="default")
    p_appr.add_argument("--steps",   type=int, nargs="*", default=None,
                        help="Specific step indices to approve (default: all).")
    p_appr.add_argument("--stub",    action="store_true")
    p_appr.add_argument("--no-stub", action="store_true")
    p_appr.add_argument("--quiet",   action="store_true")

    p_roll = sub.add_parser(
        "rollback-last",
        help="Run the verbatim rollback for the most-recent state-changing action.",
    )
    p_roll.add_argument("--user-id", default="default")
    p_roll.add_argument("--stub",    action="store_true")
    p_roll.add_argument("--no-stub", action="store_true")
    p_roll.add_argument("--quiet",   action="store_true")

    p_improve = sub.add_parser(
        "improve",
        help="Run the weekly self-improvement loop (Promptfoo + DeepEval).",
    )
    p_improve.add_argument("--user-id", default="default")
    p_improve.add_argument("--stub",    action="store_true",
                           help="Force offline + stub backends (default).")
    p_improve.add_argument("--no-stub", action="store_true",
                           help="Disable force_stub. Requires real backends.")
    p_improve.add_argument("--json",    action="store_true",
                           help="Print full EvalReport JSON instead of human summary.")
    p_improve.add_argument("--quiet",   action="store_true")

    sub.add_parser("info",    help="Print the graph description + backend selection.")
    sub.add_parser("version", help="Print agent + backend version.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    def _resolve_stub(arg_obj: Any) -> bool:
        # --stub OR (default ON unless --no-stub passed)
        if getattr(arg_obj, "no_stub", False):
            return False
        return True

    if args.command == "daily-plan":
        out = daily_plan(
            user_id=args.user_id,
            force_stub=_resolve_stub(args),
            auto_approve=bool(args.auto_approve),
            quiet=bool(args.quiet) or bool(args.json),
        )
        if args.json and not args.quiet:
            print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.command == "execute-action":
        out = execute_action(
            args.request,
            user_id=args.user_id,
            force_stub=_resolve_stub(args),
            auto_approve=bool(args.auto_approve),
            quiet=bool(args.quiet) or bool(args.json),
        )
        if args.json and not args.quiet:
            print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.command == "search":
        search(
            args.query,
            limit=int(args.limit),
            force_stub=_resolve_stub(args),
            quiet=bool(args.quiet),
        )
        return 0

    if args.command == "approve-pending":
        approve_pending(
            accept_steps=list(args.steps) if args.steps else None,
            user_id=args.user_id,
            force_stub=_resolve_stub(args),
            quiet=bool(args.quiet),
        )
        return 0

    if args.command == "rollback-last":
        rollback_last(
            user_id=args.user_id,
            force_stub=_resolve_stub(args),
            quiet=bool(args.quiet),
        )
        return 0

    if args.command == "improve":
        from eval.deepeval_suite import run_full_loop, _print_summary  # type: ignore
        force_stub = False if args.no_stub else True
        report = run_full_loop(force_stub=force_stub, user_id=args.user_id)
        _log_run("improve", {
            "force_stub":      force_stub,
            "overall_score":   report.overall_score,
            "promptfoo_pass":  sum(1 for r in report.promptfoo if r.get("passed")),
            "promptfoo_total": len(report.promptfoo),
            "deepeval_pass":   sum(1 for m in report.deepeval if m.passed),
            "deepeval_total":  len(report.deepeval),
            "suggestion_count": len(report.suggestions),
            "review_required": report.review_required,
        })
        if args.json:
            print(json.dumps(report.to_dict(), indent=2,
                             ensure_ascii=False, default=str))
        elif not args.quiet:
            _print_summary(report)
        return 0

    if args.command == "info":
        info()
        return 0

    if args.command == "version":
        print(json.dumps({
            "agent":        AGENT_NAME,
            "version":      AGENT_VERSION,
            "backend":      BACKEND_NAME,
            "python":       sys.version.split()[0],
            "platform":     sys.platform,
            "appdata_root": str(appdata_root()),
            "tools":        list(ALLOWED_TOOLS),
            "state_changing_tools": sorted(STATE_CHANGING_TOOLS),
            "read_only_tools":      sorted(READ_ONLY_TOOLS),
        }, indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
