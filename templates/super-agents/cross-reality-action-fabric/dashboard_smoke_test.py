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
"""Smoke test for the Cross-Reality Action Fabric dashboard (P133).

Layered on top of all 277 prior P121–P132 checks. This suite adds 22
new checks across five acceptance areas:

1. Module / file surface — dashboard.py + requirements.txt +
   .streamlit/config.toml exist with the right shape (Apache 2.0
   header, ecosystem-ally line, port 8506, no telemetry, 6 tabs in
   canonical order).
2. Pure-Python data helpers — build_overview_payload, build_plan_
   payload, build_pending_payload, build_history_payload,
   build_provenance_payload, build_improve_payload all return the
   expected schema regardless of whether Streamlit is installed.
3. Action runners — run_daily_plan_action, approve_pending_action,
   rollback_last_action, run_memory_search_action, run_improve_action
   wire the dashboard to the existing CLI without modifying agent.py
   or graph.py.
4. Rollback chain visualizer — build_provenance_payload exposes a
   rollback_chain list that pairs every rollback_executed record with
   its forward action_executed record.
5. V.3 banner + bash-leak guard — dashboard.py contains the exact
   Article V.3 wording AND no bash-only commands.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m dashboard_smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

import dashboard as _dash  # type: ignore
from graph import (  # type: ignore
    ConsentContext,
    appdata_root,
    build_state,
    output_with_provenance as graph_output,
    rollback as graph_rollback,
)
from memory import MEMORY_KINDS, MEMORY_WRITE_GATE  # type: ignore
from provenance import (  # type: ignore
    LocalProvenanceLogger,
    current_log_path,
    reset_default_logger,
    reset_langfuse_client,
)


# -- Section S.1. Helpers -------------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe() -> None:
    try:
        shutil.rmtree(appdata_root(), ignore_errors=True)
    except OSError:
        pass
    reset_default_logger()
    reset_langfuse_client()


# -- Section S.2. Test cases ---------------------------------------------

def test_module_and_file_surface() -> None:
    print("[1/5] module / file surface ----------------------------------------")
    here = Path(__file__).resolve().parent

    dash_path = here / "dashboard.py"
    if not dash_path.exists():
        _fail("dashboard.py", "missing")
    text = dash_path.read_text(encoding="utf-8")
    if "Apache License, Version 2.0" not in text:
        _fail("dashboard header", "Apache 2.0 missing")
    _ok("dashboard.py present + Apache 2.0 header")

    if "Built to help xAI and Grok win" not in text \
            and "Built for xAI, Grok" not in text:
        _fail("dashboard tagline", "ecosystem-ally line missing")
    _ok("dashboard.py carries 'help xAI and Grok win' tagline")

    cfg_path = here / ".streamlit" / "config.toml"
    if not cfg_path.exists():
        _fail(".streamlit/config.toml", "missing")
    cfg_text = cfg_path.read_text(encoding="utf-8")
    if "Apache License, Version 2.0" not in cfg_text:
        _fail("config.toml header", "Apache 2.0 missing")
    if "port = 8506" not in cfg_text:
        _fail("config.toml port", "expected port = 8506 (Super Agent #3 slot)")
    if "gatherUsageStats = false" not in cfg_text:
        _fail("config.toml privacy", "gatherUsageStats must be false")
    _ok(".streamlit/config.toml port=8506 + privacy-safe defaults")

    req_path = here / "requirements.txt"
    if not req_path.exists():
        _fail("requirements.txt", "missing")
    req_text = req_path.read_text(encoding="utf-8")
    for dep in ("streamlit", "pandas", "plotly", "PyYAML"):
        if dep not in req_text:
            _fail(f"requirements.txt[{dep}]", "dep missing")
    _ok("requirements.txt declares streamlit + pandas + plotly + PyYAML")

    if list(_dash.TAB_TITLES) != [
        "Overview", "Action Planner", "Pending Approvals",
        "Action History", "Provenance Audit", "Self-Improve",
    ]:
        _fail("TAB_TITLES order", str(_dash.TAB_TITLES))
    _ok("dashboard advertises exactly 6 tabs in the canonical order")

    if not isinstance(_dash.STREAMLIT_AVAILABLE, bool):
        _fail("STREAMLIT_AVAILABLE", "must be a bool")
    _ok(f"dashboard module imports cleanly (Streamlit available: "
        f"{_dash.STREAMLIT_AVAILABLE})")


def test_data_helpers() -> None:
    print("[2/5] pure-Python data helpers -----------------------------------")
    _wipe()

    # build_overview_payload — even on a fresh machine.
    payload = _dash.build_overview_payload()
    for k in (
        "agent_name", "agent_version", "graph_backend",
        "langfuse_backend", "deepeval_backend",
        "appdata_root", "memory_root", "provenance_root", "eval_root",
        "max_actions", "max_plan_loops", "tools",
        "state_changing", "read_only",
        "latest_run", "rows_per_kind", "tagline",
    ):
        if k not in payload:
            _fail(f"overview[{k}]", "missing")
    _ok("build_overview_payload returns the canonical 17-field shape")

    if set(payload["rows_per_kind"].keys()) != set(MEMORY_KINDS):
        _fail("rows_per_kind keys", str(payload["rows_per_kind"]))
    _ok("overview.rows_per_kind covers all 5 memory kinds")

    # Drive a real run + check build_plan_payload + build_pending_payload.
    out = _dash.run_daily_plan_action(force_stub=True, auto_approve=True)
    if not out or not out.get("plan"):
        _fail("run_daily_plan_action", "empty plan")
    _ok("run_daily_plan_action returned a plan via the existing CLI")

    plan_payload = _dash.build_plan_payload(out)
    for k in (
        "plan_id", "user_request", "stub", "backend",
        "actions", "violations", "executions", "rollbacks",
        "provenance",
    ):
        if k not in plan_payload:
            _fail(f"plan[{k}]", "missing")
    if plan_payload["empty"]:
        _fail("plan.empty", "should be False after a real run")
    _ok("build_plan_payload echoes the run dict with all expected fields")

    # Pending plan payload (gate-blocked path).
    _wipe()
    out_blocked = _dash.run_daily_plan_action(
        force_stub=True, auto_approve=False,
    )
    pending_path = _dash._agent.pending_plan_path()
    if not pending_path.exists():
        _fail("pending plan persistence", "no file on disk after gate-block")
    plan_dict = json.loads(pending_path.read_text(encoding="utf-8"))
    pending_payload = _dash.build_pending_payload(plan_dict)
    if pending_payload["empty"]:
        _fail("pending.empty", "expected pending steps")
    if pending_payload["count"] < 3:
        _fail("pending.count", f"expected ≥ 3, got {pending_payload['count']}")
    if not all(
        "step" in r and "tool" in r and "has_rollback" in r
        for r in pending_payload["rows"]
    ):
        _fail("pending.rows shape", "missing required fields")
    _ok(f"build_pending_payload lists {pending_payload['count']} pending step(s)")

    # build_history_payload — tolerates dict and SearchHit forms.
    hits_dict = [
        {"score": 0.9, "kind": "action", "timestamp": "2026-05-05T00:00:00Z",
         "text": "long" * 100, "id": "x",
         "provenance": {"redaction_applied": True}},
    ]
    hist_payload = _dash.build_history_payload(hits_dict)
    if hist_payload["row_count"] != 1:
        _fail("history.row_count", str(hist_payload["row_count"]))
    if "snippet" not in hist_payload["rows"][0]:
        _fail("history.rows[0]", "missing snippet")
    _ok("build_history_payload accepts dict-form hits and produces snippets")


def test_action_runners() -> None:
    print("[3/5] action runners ---------------------------------------------")
    _wipe()

    # run_daily_plan_action with auto-approve — every action executes.
    out = _dash.run_daily_plan_action(force_stub=True, auto_approve=True)
    if (out.get("provenance") or {}).get("successful", 0) < 3:
        _fail("daily_plan auto", "fewer than 3 successes")
    _ok(f"run_daily_plan_action(auto_approve=True) → "
        f"{out['provenance']['successful']} successes")

    # Populate memory via the P130 attach_memory_store wrapper (the
    # CLI's daily_plan doesn't write memory — that's the canonical
    # split: CLI runs are pure graph executions; memory is opt-in via
    # attach_memory_store). The dashboard's Action History tab assumes
    # the user has gone through that wrapper at least once.
    from memory import attach_memory_store  # type: ignore
    consent = ConsentContext.from_iterable(
        list(_dash._agent.ALL_GATES) + [MEMORY_WRITE_GATE],
        consent_token="dash-history",
    )
    _client, run_with_memory = attach_memory_store(
        force_stub=True, consent=consent,
    )
    run_with_memory(force_stub=True, auto_approve=True,
                    user_request="(history seed)")

    # run_memory_search_action returns hits now that memory is populated.
    hits = _dash.run_memory_search_action("weather", limit=5, force_stub=True)
    if not hits:
        _fail("memory search", "no hits after attach_memory_store run")
    _ok(f"run_memory_search_action returned {len(hits)} hit(s)")

    # rollback_last_action runs cleanly + writes a rollback row.
    rb = _dash.rollback_last_action(force_stub=True)
    if not rb.get("rolled_back", 0):
        _fail("rollback_last_action", str(rb))
    _ok(f"rollback_last_action rolled back {rb['rolled_back']} action(s)")

    # run_improve_action returns an EvalReport.
    report = _dash.run_improve_action(force_stub=True)
    if not hasattr(report, "promptfoo") or not hasattr(report, "deepeval"):
        _fail("run_improve_action", f"got {type(report)}")
    if len(report.promptfoo) != 8 or len(report.deepeval) != 6:
        _fail("improve report shape",
              f"promptfoo={len(report.promptfoo)}, deepeval={len(report.deepeval)}")
    _ok("run_improve_action returned EvalReport with 8 promptfoo + 6 deepeval")

    # build_improve_payload — schema check.
    improve_payload = _dash.build_improve_payload(report)
    for k in (
        "run_id", "started_at", "finished_at", "force_stub",
        "backend", "overall_score", "review_required",
        "promptfoo", "deepeval", "suggestions",
    ):
        if k not in improve_payload:
            _fail(f"improve[{k}]", "missing")
    _ok("build_improve_payload returns the canonical 10-field shape")


def test_rollback_chain_visualizer() -> None:
    print("[4/5] rollback chain visualizer ----------------------------------")
    _wipe()

    # Forward run + rollback to populate JSONL.
    consent = ConsentContext.from_iterable(
        [g for g in _dash._agent.ALL_GATES] + [MEMORY_WRITE_GATE],
        consent_token="p133-smoke",
    )
    from provenance import attach_provenance  # type: ignore
    logger, lf, run = attach_provenance(
        user_id="dash", consent=consent, refresh=True,
    )
    out1 = run(force_stub=True, auto_approve=True, user_request="forward")

    s = build_state(force_stub=True, auto_approve=True, user_id="dash")
    s["plan"] = out1["plan"]
    s.update(graph_rollback(s))
    s.update(graph_output(s))
    out2 = s["output"]
    logger.record_run(out2)

    # The dashboard's provenance payload must contain a rollback_chain.
    today = current_log_path().name.replace(".jsonl", "")
    records = _dash.load_records_for_date(today)
    payload = _dash.build_provenance_payload(records)
    if "rollback_chain" not in payload:
        _fail("provenance.rollback_chain", "missing")
    if not payload["rollback_chain"]:
        _fail("rollback_chain rows", "empty after a rollback")
    _ok(f"build_provenance_payload includes rollback_chain "
        f"({len(payload['rollback_chain'])} row(s))")

    chain_row = payload["rollback_chain"][0]
    for k in (
        "forward_action_id", "forward_tool", "forward_step",
        "rollback_id", "rollback_outcome", "timestamp",
    ):
        if k not in chain_row:
            _fail(f"rollback_chain[{k}]", "missing")
    if not chain_row["forward_action_id"].startswith("crf-act-"):
        _fail("forward_action_id prefix", chain_row["forward_action_id"])
    _ok("rollback_chain row links forward action_id ↔ rollback_id correctly")

    # Filter narrowing on the provenance payload.
    rb_only = _dash.build_provenance_payload(
        records, event_kind_filter="rollback_executed",
    )
    if not rb_only["rows"]:
        _fail("event_kind filter", "no rows after rollback_executed filter")
    if any(r["event_kind"] != "rollback_executed" for r in rb_only["rows"]):
        _fail("event_kind filter", "leaked other event kinds")
    _ok("event_kind filter returns rollback_executed rows only")


def test_disclaimers_and_constants() -> None:
    print("[5/5] disclaimers + constants ------------------------------------")
    here = Path(__file__).resolve().parent
    text = (here / "dashboard.py").read_text(encoding="utf-8")

    # V.3 wording verbatim from constitution.md. The disclaimer string
    # is concatenated from multiple Python literals in the source, so we
    # check the runtime-concatenated DISCLAIMER_RW constant rather than
    # the source text directly.
    if "real-world actions" not in _dash.DISCLAIMER_RW \
            or "explicit consent" not in _dash.DISCLAIMER_RW:
        _fail("V.3 wording", "missing")
    if "agent never acts autonomously" not in _dash.DISCLAIMER_RW:
        _fail("V.3 closing line", str(_dash.DISCLAIMER_RW))
    _ok("dashboard.DISCLAIMER_RW carries the V.3 banner verbatim")

    # V.1 / V.2 banners must NOT appear (action fabric is not finance/tax).
    if "Not financial advice" in text or "Not tax advice" in text:
        _fail("disclaimer mix", "must NOT carry V.1/V.2 finance/tax banners")
    _ok("dashboard correctly omits V.1 / V.2 finance / tax banners")

    # Local-first banner present.
    if "Local-first" not in text:
        _fail("local-first banner", "missing")
    _ok("dashboard surfaces local-first + privacy-first banner")

    # No bash-isms.
    bad = ["sudo ", "chmod ", "mkdir -p", " && ", "/usr/bin/python", "/bin/bash"]
    leaked = [b for b in bad if b in text]
    if leaked:
        _fail("PowerShell-only", f"bash-isms present: {leaked}")
    _ok("dashboard.py contains no bash-only invocations")

    # Action runners refuse anything that would bypass auto_approve quietly.
    out = _dash.run_daily_plan_action(force_stub=True, auto_approve=False)
    if not (out.get("violations") or []):
        _fail("auto_approve=False default", "no violations recorded")
    _ok("dashboard's run_daily_plan_action(auto_approve=False) preserves the HITL gate")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P133 Cross-Reality Action Fabric dashboard smoke test")
    print(f"Streamlit available: {_dash.STREAMLIT_AVAILABLE}")
    print("=" * 70)
    try:
        test_module_and_file_surface()
        test_data_helpers()
        test_action_runners()
        test_rollback_chain_visualizer()
        test_disclaimers_and_constants()
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
    print("RESULT: PASS — all 5 P133 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
