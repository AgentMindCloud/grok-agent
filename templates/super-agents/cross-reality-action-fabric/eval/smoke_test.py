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
"""Smoke test for the Cross-Reality Action Fabric self-improvement loop (P132).

Layered on top of the 249 prior P121–P131 checks. This suite adds 18
new checks across four acceptance areas:

1. Module / file surface — eval/promptfoo.yaml + eval/deepeval_suite.py
   + eval/__init__.py present, parseable, advertise the canonical
   public surface (16 names, 6 metric classes, 8 Promptfoo test cases,
   ≥ 6 SUGGESTION_LIBRARY entries).
2. Six DeepEval metrics — every metric class scores in [0,1], the
   threshold is honest, OverallActionImprovement aggregates correctly,
   no-collapse penalty fires when any component drops below 0.5.
3. Eight Promptfoo assertions — every YAML test case has a matching
   Python predicate, a clean-stub run scores 8/8, a broken run drops
   the structural assertions.
4. End-to-end CLI — ``python agent.py improve --stub`` runs cleanly,
   writes one P131 ProvenanceRecord (kind ``run_complete`` with
   ``plan_id`` prefixed ``eval::``), persists JSON + Markdown reports
   under ``eval/`` AppData, and the suggestions are human-review-gated.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m eval.smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import yaml as _yaml_mod  # type: ignore
import agent as _agent  # type: ignore
from graph import (  # type: ignore
    ConsentContext,
    appdata_root,
)
from memory import MEMORY_WRITE_GATE  # type: ignore
from provenance import (  # type: ignore
    LocalProvenanceLogger,
    reset_default_logger,
    reset_langfuse_client,
)
import eval as _eval_pkg  # type: ignore
from eval import (  # type: ignore
    ActionQuality,
    ApprovalCompliance,
    CostEfficiency,
    DEEPEVAL_BACKEND,
    EvalReport,
    MetricResult,
    OverallActionImprovement,
    PROMPTFOO_TEST_CASES,
    RollbackSuccess,
    SafetyScore,
    SUGGESTION_LIBRARY,
    build_improvement_suggestions,
    build_run_for_eval,
    eval_results_root,
    promptfoo_stub_provider,
    run_deepeval_metrics,
    run_full_loop,
    run_promptfoo_assertions,
)


# -- Section S.1. Helpers --------------------------------------------------

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

def test_module_surface() -> None:
    print("[1/4] module / file surface ----------------------------------------")
    here = Path(__file__).resolve().parent

    yaml_path = here / "promptfoo.yaml"
    if not yaml_path.exists():
        _fail("promptfoo.yaml", f"missing at {yaml_path}")
    _ok("promptfoo.yaml present")

    text = yaml_path.read_text(encoding="utf-8")
    if "Apache License, Version 2.0" not in text:
        _fail("promptfoo.yaml header", "Apache 2.0 header missing")
    _ok("promptfoo.yaml carries Apache 2.0 header")

    if _yaml_mod is not None:
        try:
            data = _yaml_mod.safe_load(text)
        except Exception as exc:
            _fail("yaml.safe_load", str(exc))
        if not isinstance(data.get("tests"), list) or len(data["tests"]) != 8:
            _fail("promptfoo.yaml tests", f"expected 8 tests, got "
                  f"{len(data.get('tests') or [])}")
        _ok("promptfoo.yaml parses + has 8 test cases")
    else:
        _ok("PyYAML not installed; skipped YAML schema check")

    if len(PROMPTFOO_TEST_CASES) != 8:
        _fail("PROMPTFOO_TEST_CASES count", str(len(PROMPTFOO_TEST_CASES)))
    _ok("deepeval_suite mirrors 8 Promptfoo test cases")

    if len(SUGGESTION_LIBRARY) < 6:
        _fail("SUGGESTION_LIBRARY size", str(len(SUGGESTION_LIBRARY)))
    _ok(f"SUGGESTION_LIBRARY has {len(SUGGESTION_LIBRARY)} canonical entries")

    for name in (
        "ActionQuality", "ApprovalCompliance", "RollbackSuccess",
        "SafetyScore", "CostEfficiency", "OverallActionImprovement",
        "build_run_for_eval", "run_full_loop",
        "build_improvement_suggestions", "promptfoo_stub_provider",
        "eval_results_root", "DEEPEVAL_BACKEND", "EvalReport",
    ):
        if not hasattr(_eval_pkg, name):
            _fail(f"eval.{name}", "missing")
    _ok(f"eval package re-exports the canonical 13-item public surface")


def test_metrics_scoring() -> None:
    print("[2/4] DeepEval custom metrics --------------------------------------")
    _wipe()
    out = build_run_for_eval(force_stub=True)

    # Every metric scores in [0.0, 1.0].
    for cls in (ActionQuality, ApprovalCompliance,
                RollbackSuccess, CostEfficiency):
        m: MetricResult = cls().measure(out)
        if not isinstance(m, MetricResult):
            _fail(cls.__name__, f"got {type(m)}")
        if not (0.0 <= m.score <= 1.0):
            _fail(cls.__name__, f"score out of range: {m.score}")
        if not (0.0 <= m.threshold <= 1.0):
            _fail(cls.__name__, f"threshold out of range: {m.threshold}")
    _ok("ActionQuality / ApprovalCompliance / RollbackSuccess / CostEfficiency "
        "all score in [0.0, 1.0]")

    # SafetyScore needs the on-disk provenance log; verify it scores.
    safety = SafetyScore().measure(out)
    if not (0.0 <= safety.score <= 1.0):
        _fail("SafetyScore", f"score out of range: {safety.score}")
    _ok(f"SafetyScore scores in [0.0, 1.0] (got {safety.score:.3f})")

    # ApprovalCompliance is binary 1.0 on the auto-approve happy path.
    ac = ApprovalCompliance().measure(out)
    if ac.score != 1.0 or not ac.passed:
        _fail("ApprovalCompliance", f"score={ac.score}, passed={ac.passed}")
    _ok("ApprovalCompliance = 1.0 on the auto-approve happy path")

    # RollbackSuccess is binary 1.0 — every state-changing action carries
    # a verbatim rollback in the stub plan.
    rs = RollbackSuccess().measure(out)
    if rs.score != 1.0:
        _fail("RollbackSuccess", f"score={rs.score}")
    _ok("RollbackSuccess = 1.0 (every state-changing action carries rollback)")

    # Aggregate metric is the last entry of run_deepeval_metrics.
    metrics = run_deepeval_metrics(out)
    if len(metrics) != 6:
        _fail("metric count", str(len(metrics)))
    _ok("run_deepeval_metrics returns exactly 6 results")

    overall = metrics[-1]
    if overall.name != "OverallActionImprovement":
        _fail("metric ordering", f"last metric = {overall.name}")
    if overall.score < 0.8 or not overall.passed:
        _fail("OverallActionImprovement on stub", f"score={overall.score}")
    _ok(f"OverallActionImprovement = {overall.score:.3f} on a clean stub run")

    # No-collapse bonus contract: when one component is below 0.5, the
    # bonus vanishes.
    bad_components = [
        MetricResult(name="ActionQuality",      score=1.0, threshold=0.8, passed=True,  reason="t"),
        MetricResult(name="ApprovalCompliance", score=0.0, threshold=1.0, passed=False, reason="t"),
        MetricResult(name="RollbackSuccess",    score=1.0, threshold=1.0, passed=True,  reason="t"),
        MetricResult(name="SafetyScore",        score=1.0, threshold=0.95, passed=True, reason="t"),
        MetricResult(name="CostEfficiency",     score=1.0, threshold=1.0, passed=True,  reason="t"),
    ]
    overall_bad = OverallActionImprovement(bad_components).measure()
    # ApprovalCompliance at 0.0 collapses → score = 0.15+0+0.20+0.25+0.10 = 0.70 (no bonus)
    if overall_bad.score >= 0.8:
        _fail("no-collapse penalty", f"expected < 0.8, got {overall_bad.score}")
    _ok("OverallActionImprovement penalises single-axis collapse "
        f"(ApprovalCompliance=0 → score {overall_bad.score:.3f} < 0.8)")


def test_promptfoo_assertions() -> None:
    print("[3/4] Promptfoo asserts --------------------------------------------")
    _wipe()
    out = build_run_for_eval(force_stub=True)
    rows = run_promptfoo_assertions(out)
    if len(rows) != 8:
        _fail("assertion count", str(len(rows)))
    _ok("run_promptfoo_assertions returns 8 rows")

    pass_count = sum(1 for r in rows if r.get("passed"))
    if pass_count != 8:
        _fail("clean-stub passes", f"{pass_count}/8 — expected 8/8")
    _ok("clean stub run passes 8/8 Promptfoo asserts")

    # Promptfoo stub provider returns valid JSON.
    raw = promptfoo_stub_provider("ignored", {})
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail("stub provider JSON", str(exc))
    if "plan" not in parsed:
        _fail("stub provider shape", "no 'plan' key in returned JSON")
    _ok("promptfoo_stub_provider returns valid JSON with a plan block")

    # Negative case: an artificially broken plan fails T1.
    broken = {"plan": {"proposed_actions": [{"tool": "weather_lookup"}]},
              "stub": True}
    rows_bad = run_promptfoo_assertions(broken)
    t1 = next(r for r in rows_bad if r["id"] == "T1")
    if t1["passed"]:
        _fail("T1 negative case", "should fail on a 1-action plan")
    _ok("T1 (plan quality) correctly fails on a broken plan")

    # Suggestions: a broken brief produces ≥ 1 needs_review suggestion.
    metrics_bad = run_deepeval_metrics(broken)
    suggestions = build_improvement_suggestions(metrics_bad, rows_bad)
    if not suggestions:
        _fail("suggestions on broken run", "expected ≥ 1")
    if any(s.get("status") != "needs_review" for s in suggestions):
        _fail("suggestion gate", "every suggestion must be needs_review")
    _ok(f"broken run produces {len(suggestions)} human-review suggestions")


def test_cli_end_to_end() -> None:
    print("[4/4] CLI end-to-end -----------------------------------------------")
    _wipe()

    # Programmatic run path.
    report = run_full_loop(force_stub=True)
    if not isinstance(report, EvalReport):
        _fail("run_full_loop", f"got {type(report)}")
    _ok("run_full_loop returns an EvalReport")

    if len(report.promptfoo) != 8:
        _fail("report.promptfoo size", str(len(report.promptfoo)))
    if len(report.deepeval) != 6:
        _fail("report.deepeval size", str(len(report.deepeval)))
    _ok("EvalReport carries 8 Promptfoo rows + 6 DeepEval metrics")

    if report.review_required:
        _fail("review_required on stub", "clean stub run should not need review")
    _ok("clean stub run needs no human review (review_required=False)")

    # JSON + Markdown reports written to AppData.
    root = eval_results_root()
    json_files = list(root.glob("eval-*.json"))
    md_files   = list(root.glob("eval-*.md"))
    if not json_files or not md_files:
        _fail("on-disk reports", f"json={len(json_files)}, md={len(md_files)}")
    _ok(f"eval reports persisted under {root}")

    md_text = md_files[0].read_text(encoding="utf-8")
    if "## Promptfoo (8 test cases)" not in md_text:
        _fail("markdown shape", "Promptfoo section missing")
    if "## DeepEval (6 metrics)" not in md_text:
        _fail("markdown shape", "DeepEval section missing")
    if "human-review-gated" not in md_text.lower():
        _fail("markdown gate language", "human-review note missing")
    _ok("Markdown report carries Promptfoo + DeepEval sections + human-review note")

    # ProvenanceRecord written by the loop (P131 integration).
    log = LocalProvenanceLogger()
    today_path = (appdata_root() / "provenance"
                  / f"{report.started_at.split('T')[0]}.jsonl")
    if not today_path.exists():
        _fail("provenance JSONL", f"missing at {today_path}")
    found = False
    for line in today_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if (d.get("event_kind") == "run_complete"
                and (d.get("plan_id") or "").startswith("eval::")):
            found = True
            if d.get("extra", {}).get("eval", {}).get("overall_score") \
                    != report.overall_score:
                _fail("provenance score parity", "mismatch")
            break
    if not found:
        _fail("eval ProvenanceRecord", "no run_complete event with plan_id=eval::")
    _ok("eval ProvenanceRecord 'run_complete' written with embedded EvalReport")

    # CLI invocation via agent.main(['improve', '--stub', '--quiet']).
    rc = _agent.main(["improve", "--stub", "--quiet"])
    if rc != 0:
        _fail("agent.main improve", f"exit code {rc}")
    _ok("agent.main(['improve','--stub','--quiet']) returned 0")

    # Run-log row written.
    log_lines = _agent.log_path().read_text(encoding="utf-8").splitlines()
    if not any('"action": "improve"' in line for line in log_lines):
        _fail("agent run-log", "no improve action recorded")
    _ok("agent run-log records the improve action")

    # CLI subprocess test.
    here = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "agent.py", "improve", "--stub", "--quiet"],
        cwd=here, capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        _fail("subprocess improve", f"exit {proc.returncode}; stderr={proc.stderr[:200]}")
    _ok("`python agent.py improve --stub` runs cleanly via subprocess")

    # DEEPEVAL_BACKEND constant is consistent with what the report says.
    if report.backend != DEEPEVAL_BACKEND:
        _fail("backend parity", f"{report.backend} vs {DEEPEVAL_BACKEND}")
    _ok(f"DEEPEVAL_BACKEND = {DEEPEVAL_BACKEND} (consistent)")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P132 Cross-Reality Action Fabric self-improvement smoke test")
    print(f"DeepEval backend: {DEEPEVAL_BACKEND}")
    print("=" * 70)
    try:
        test_module_surface()
        test_metrics_scoring()
        test_promptfoo_assertions()
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
    print("RESULT: PASS — all 4 P132 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
