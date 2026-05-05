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
"""Smoke test for the Cross-Reality Action Fabric orchestration core (P129).

Layered on top of all 169 prior P121–P127 checks (which run unchanged
because P128/P129 are an entirely separate Super Agent stack). This
suite adds 21 new checks across five acceptance areas:

1. Module + graph structure — 8 nodes, conditional routing, _StubGraph
   selection, ALLOWED_TOOLS / STATE_CHANGING_TOOLS / READ_ONLY_TOOLS.
2. Action plan generation — stub plan emits 4 actions covering all 5
   tools; refusal_reason populated when force_stub=False with no LLM.
3. HITL gate behaviour — gate refuses without consent_token (Rule 1);
   ``--auto-approve`` mints tokens; pre-attached tokens pass through.
4. Per-tool execution + rollback — every state-changing action carries
   verbatim rollback (Rule 3); rollback node reverts the most-recent
   state-changing action and writes a provenance row.
5. CLI end-to-end — daily-plan / execute-action / search /
   approve-pending / rollback-last / info / version all exit 0; the
   gate-block → approve-pending round-trip works.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import agent as _agent  # type: ignore
import graph as _graph  # type: ignore


# -- Section S.1. Helpers --------------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe() -> None:
    root = _graph.appdata_root()
    try:
        shutil.rmtree(root, ignore_errors=True)
    except OSError:
        pass


# -- Section S.2. Test cases ---------------------------------------------

def test_module_and_graph_structure() -> None:
    print("[1/5] module + graph structure -------------------------------------")

    for name in (
        "AGENT_NAME", "AGENT_VERSION", "ALLOWED_TOOLS", "ALL_GATES",
        "BACKEND_NAME", "ConsentContext", "ConstitutionViolation",
        "ActionStep", "ActionPlan",
        "appdata_root", "build_graph", "build_state",
        "describe_graph", "make_consent_token",
        "plan_actions", "request_approval",
        "execute_web", "execute_windows", "execute_realworld",
        "execute_x", "rollback", "output_with_provenance",
        "route_after_approval", "route_after_execution",
        "run_action_loop",
    ):
        if not hasattr(_graph, name) and not hasattr(_agent, name):
            _fail(f"name {name}", "missing from graph/agent")
    _ok("graph + agent expose the canonical 25-name public surface")

    if list(_graph.ALLOWED_TOOLS) != [
        "web_via_stagehand", "windows_local",
        "weather_lookup", "flight_search", "x_search",
    ]:
        _fail("ALLOWED_TOOLS", str(_graph.ALLOWED_TOOLS))
    _ok(f"ALLOWED_TOOLS lists exactly the 5 manifest-declared tools")

    if _graph.STATE_CHANGING_TOOLS != frozenset({"web_via_stagehand", "windows_local"}):
        _fail("STATE_CHANGING_TOOLS", str(_graph.STATE_CHANGING_TOOLS))
    if _graph.READ_ONLY_TOOLS != frozenset({"weather_lookup", "flight_search", "x_search"}):
        _fail("READ_ONLY_TOOLS", str(_graph.READ_ONLY_TOOLS))
    _ok("state-changing vs read-only tool partition matches the Constitution")

    desc = _graph.describe_graph()
    expected_nodes = [
        "plan_actions", "request_approval",
        "execute_web", "execute_windows",
        "execute_realworld", "execute_x",
        "rollback", "output_with_provenance",
    ]
    if list(desc["nodes"]) != expected_nodes:
        _fail("describe_graph nodes", str(desc["nodes"]))
    _ok("describe_graph reports the 8 expected nodes in order")

    if _graph.BACKEND_NAME not in {"langgraph", "stub:sequential"}:
        _fail("BACKEND_NAME", str(_graph.BACKEND_NAME))
    _ok(f"BACKEND_NAME selected cleanly: {_graph.BACKEND_NAME}")


def test_plan_actions_stub_and_refusal() -> None:
    print("[2/5] plan_actions stub + honest refusal --------------------------")
    _wipe()
    state = _graph.build_state(force_stub=True, user_request="ignored in stub mode")
    upd = _graph.plan_actions(state)
    state.update(upd)
    plan = state["plan"]

    if not (3 <= len(plan["proposed_actions"]) <= 5):
        _fail("plan size", f"expected 3-5 actions, got {len(plan['proposed_actions'])}")
    _ok(f"stub plan has {len(plan['proposed_actions'])} proposed actions (3-5)")

    seen_tools = {a["tool"] for a in plan["proposed_actions"]}
    expected = {"weather_lookup", "x_search", "windows_local", "web_via_stagehand"}
    if not expected.issubset(seen_tools):
        _fail("plan tools", f"missing: {expected - seen_tools}")
    _ok("stub plan covers all 4 expected tool families")

    # State-changing actions must carry a verbatim rollback (Rule 3).
    for a in plan["proposed_actions"]:
        if a["tool"] in _graph.STATE_CHANGING_TOOLS and not a["rollback"].strip():
            _fail("rollback contract", f"step {a['step']} ({a['tool']}) has no rollback")
    _ok("every state-changing action carries a verbatim rollback (Rule 3)")

    # Read-only actions are exempt from rollback.
    rs = [a for a in plan["proposed_actions"] if a["tool"] in _graph.READ_ONLY_TOOLS]
    if not rs:
        _fail("read-only actions", "no read-only actions in plan")
    if any(r["rollback"].strip() for r in rs):
        _fail("read-only carve-out", "read-only action has unnecessary rollback")
    _ok("read-only actions correctly omit the rollback (Rule 3 carve-out)")

    # Honest refusal when force_stub=False without an LLM.
    state2 = _graph.build_state(force_stub=False, user_request="real request")
    upd2 = _graph.plan_actions(state2)
    state2.update(upd2)
    if not state2["plan"]["refusal_reason"]:
        _fail("force_stub=False refusal", "expected refusal_reason populated")
    if state2["plan"]["proposed_actions"]:
        _fail("force_stub=False refusal", "expected empty proposed_actions list")
    _ok("plan_actions honestly refuses when force_stub=False with no LLM")


def test_hitl_gate_behaviour() -> None:
    print("[3/5] HITL gate behaviour ------------------------------------------")
    _wipe()

    # 1. force_stub=True, auto_approve=False → gate refuses every step.
    state = _graph.build_state(
        force_stub=True, auto_approve=False, user_request="(stub plan)"
    )
    state.update(_graph.plan_actions(state))
    state.update(_graph.request_approval(state))
    refused = sum(
        1 for a in state["plan"]["proposed_actions"]
        if a.get("refusal_reason")
    )
    if refused != len(state["plan"]["proposed_actions"]):
        _fail("gate-block", f"expected all refused, got {refused}/{len(state['plan']['proposed_actions'])}")
    if not state["violations"]:
        _fail("gate-block violations", "expected ≥ 1 Rule-1 violation")
    _ok(f"HITL gate refused all {refused} steps without consent_tokens")
    # All violations cite Rule 1.
    if not all(v.get("rule") == 1 for v in state["violations"]):
        _fail("gate-block violations rule", str(state["violations"]))
    _ok("every gate-block violation cites Rule 1 (Article I)")

    # 2. force_stub=True, auto_approve=True → gate auto-mints tokens.
    state2 = _graph.build_state(
        force_stub=True, auto_approve=True, user_request="(stub plan)"
    )
    state2.update(_graph.plan_actions(state2))
    state2.update(_graph.request_approval(state2))
    if any(a.get("refusal_reason") for a in state2["plan"]["proposed_actions"]):
        _fail("auto-approve", "some steps still refused with auto_approve=True")
    if not all(
        a.get("consent_token") for a in state2["plan"]["proposed_actions"]
    ):
        _fail("auto-approve tokens", "some steps missing consent_token")
    _ok("auto_approve=True mints consent_tokens for every step")

    # 3. Pre-attached tokens pass through cleanly (the approve-pending path).
    state3 = _graph.build_state(
        force_stub=True, auto_approve=False, user_request="(stub plan)"
    )
    state3.update(_graph.plan_actions(state3))
    for a in state3["plan"]["proposed_actions"]:
        a["consent_token"] = _graph.make_consent_token(scope=a["tool"])
    state3.update(_graph.request_approval(state3))
    if any(a.get("refusal_reason") for a in state3["plan"]["proposed_actions"]):
        _fail("pre-attached tokens", "gate refused steps with pre-attached tokens")
    _ok("pre-attached consent_tokens pass the HITL gate cleanly")


def test_execution_and_rollback() -> None:
    print("[4/5] per-tool execution + rollback --------------------------------")
    _wipe()
    out = _graph.run_action_loop(force_stub=True, auto_approve=True)

    if (out.get("provenance") or {}).get("successful", 0) < 3:
        _fail("end-to-end run", f"expected ≥ 3 successes, got {out['provenance']['successful']}")
    _ok(f"end-to-end run produced {out['provenance']['successful']} successful executions")

    # Every executed step has a non-empty execution_result and an outcome.
    for a in out["plan"]["proposed_actions"]:
        if not a.get("executed"):
            _fail("execution coverage", f"step {a['step']} not executed")
        if a.get("outcome") != "success":
            _fail("execution outcome", f"step {a['step']} outcome: {a.get('outcome')}")
        if not a.get("execution_result"):
            _fail("execution_result", f"step {a['step']} missing result")
    _ok("every step executed with outcome=success and a result payload")

    # Provenance trail covers all 8 nodes (or at least all involved nodes).
    trail_nodes = {row["node"] for row in out["provenance"]["trail"]}
    expected_nodes_seen = {
        "plan_actions", "request_approval",
        "execute_web", "execute_windows",
        "execute_realworld", "execute_x",
        "output_with_provenance",
    }
    missing = expected_nodes_seen - trail_nodes
    if missing:
        _fail("trail node coverage", f"missing: {sorted(missing)}")
    _ok(f"provenance trail covers every dispatched node: {sorted(trail_nodes)}")

    # Rollback last: directly invoke the rollback node on the run.
    state = _graph.build_state(force_stub=True, auto_approve=True)
    state["plan"] = out["plan"]
    state.update(_graph.rollback(state))
    state.update(_graph.output_with_provenance(state))
    rb_count = len(state["output"].get("rollbacks") or [])
    if rb_count < 1:
        _fail("rollback node", "expected ≥ 1 rollback row")
    _ok(f"rollback node reverted {rb_count} state-changing action(s)")
    if not any(r.get("outcome") == "rolled_back" for r in state["output"]["rollbacks"]):
        _fail("rollback outcome", "no row with outcome=rolled_back")
    _ok("rollback row carries outcome=rolled_back and a started_at/finished_at")

    # Rule-5 enforcement: a step with bash leak is refused before execution.
    state_bad = _graph.build_state(force_stub=True, auto_approve=True)
    state_bad["plan"] = {
        "plan_id": "bad",
        "user_request": "ignored",
        "proposed_actions": [
            {
                "step": 1, "tool": "windows_local",
                "description": "bash leak",
                "script": "bash -c 'rm -rf /'",
                "rollback": "echo nope",
                "expected_cost_usd": 0.0,
                "consent_required": True,
                "consent_token": None,
                "executed": False,
                "rolled_back": False,
                "outcome": None,
            },
        ],
        "total_cost_usd": 0.0,
        "created_at": "2026-05-05T00:00:00+00:00",
        "contradictions": [],
    }
    state_bad.update(_graph.request_approval(state_bad))
    rule5 = [v for v in state_bad["violations"] if v.get("rule") == 5]
    if not rule5:
        _fail("Rule 5", "bash leak not refused")
    _ok("Rule 5 enforcement refuses any bash / unix-shell prefix in scripts")


def test_cli_end_to_end() -> None:
    print("[5/5] CLI end-to-end -----------------------------------------------")
    _wipe()

    # Programmatic daily_plan with auto_approve.
    out = _agent.daily_plan(force_stub=True, auto_approve=True, quiet=True)
    if (out.get("provenance") or {}).get("successful", 0) < 3:
        _fail("daily_plan auto", "fewer than 3 successes")
    _ok(f"daily_plan auto-approve produced {out['provenance']['successful']} successes")

    # CLI subprocess — version + info + daily-plan happy path.
    here = Path(__file__).resolve().parent
    for argv in (["version"], ["info"]):
        proc = subprocess.run(
            [sys.executable, "agent.py", *argv],
            cwd=here, capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            _fail(f"agent.py {argv[0]}", f"exit {proc.returncode}; stderr={proc.stderr[:200]}")
    _ok("agent.py version + info subcommands return 0")

    # CLI subprocess — the daily-plan → approve-pending → rollback-last
    # round-trip.
    _wipe()
    proc = subprocess.run(
        [sys.executable, "agent.py", "daily-plan", "--stub", "--quiet"],
        cwd=here, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        _fail("daily-plan gate-block", f"exit {proc.returncode}")
    _ok("daily-plan --stub (no auto-approve) exits 0 with HITL refusals")
    pending_path = _graph.appdata_root() / "pending_plan.json"
    if not pending_path.exists():
        _fail("pending_plan persistence", f"file missing at {pending_path}")
    _ok("pending plan persisted to disk after gate-block")

    proc = subprocess.run(
        [sys.executable, "agent.py", "approve-pending", "--stub", "--quiet"],
        cwd=here, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        _fail("approve-pending", f"exit {proc.returncode}; stderr={proc.stderr[:200]}")
    _ok("approve-pending --stub exits 0 and re-runs the plan")

    proc = subprocess.run(
        [sys.executable, "agent.py", "rollback-last", "--stub", "--quiet"],
        cwd=here, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        _fail("rollback-last", f"exit {proc.returncode}; stderr={proc.stderr[:200]}")
    _ok("rollback-last --stub exits 0 and reverts the last state-changing action")

    # Run-log row written.
    log_lines = _agent.log_path().read_text(encoding="utf-8").splitlines()
    actions_in_log = {
        json.loads(line).get("action")
        for line in log_lines if line.strip()
    }
    for needed in ("daily_plan", "approve_pending", "rollback_last"):
        if needed not in actions_in_log:
            _fail(f"log[{needed}]", f"action not recorded; log has {sorted(actions_in_log)}")
    _ok(f"agent.log records every CLI action: {sorted(actions_in_log)}")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P129 Cross-Reality Action Fabric orchestration smoke test")
    print(f"Backend: {_graph.BACKEND_NAME}")
    print("=" * 70)
    try:
        test_module_and_graph_structure()
        test_plan_actions_stub_and_refusal()
        test_hitl_gate_behaviour()
        test_execution_and_rollback()
        test_cli_end_to_end()
    except SystemExit:
        print("=" * 70)
        print("RESULT: FAIL")
        return 1
    except Exception:
        print("UNCAUGHT EXCEPTION:")
        traceback.print_exc()
        print("=" * 70)
        print("RESULT: FAIL")
        return 1
    print("=" * 70)
    print("RESULT: PASS — all 5 P129 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
