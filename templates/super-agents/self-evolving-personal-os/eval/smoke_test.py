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
"""Smoke test for the Self-Evolving Personal OS self-improvement loop (P125).

Layered on top of the 117 prior P121 + P122 + P123 + P124 checks. This
suite adds 17 new checks covering the four P125 acceptance areas:

1. Module / file surface — eval/promptfoo.yaml + eval/deepeval_suite.py
   + eval/__init__.py present, parseable, advertise the right names.
2. Five DeepEval metrics — every metric class scores in [0,1], the
   threshold is honest, and the OverallSelfImprovement aggregate matches
   its weighted-sum contract.
3. Eight Promptfoo assertions — every YAML test case has a matching
   Python predicate and a clean-brief run scores 8/8.
4. End-to-end CLI — ``python agent.py improve --stub`` runs cleanly,
   writes one ProvenanceRecord (kind ``eval.run_full_loop``) plus a
   JSON + Markdown report under ``eval/`` AppData; force_stub stays
   pass-through; suggestions are human-review-gated.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates/super-agents/self-evolving-personal-os
   python -m eval.smoke_test

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import yaml as _yaml_mod  # type: ignore  — optional; we degrade if missing
from connectors import (  # type: ignore
    ConsentContext,
    appdata_root,
)
from memory import MEMORY_WRITE_GATE  # type: ignore
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore
import agent as _agent  # type: ignore
from provenance import (  # type: ignore
    LocalProvenanceLogger,
    current_log_path,
    reset_default_logger,
    reset_langfuse_client,
)
import eval as _eval_pkg  # type: ignore  — package
from eval import (  # type: ignore
    DEEPEVAL_BACKEND,
    EvalReport,
    EvolutionQuality,
    MemoryRelevance,
    MetricResult,
    OverallSelfImprovement,
    PIISafety,
    PROMPTFOO_TEST_CASES,
    ProvenanceScore,
    SUGGESTION_LIBRARY,
    build_brief_for_eval,
    build_improvement_suggestions,
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
    """Reset the local Personal OS state so every smoke section is hermetic."""
    root = appdata_root()
    for sub in ("memory", "logs", "provenance", "eval"):
        try:
            shutil.rmtree(root / sub, ignore_errors=True)
        except OSError:
            pass
    try:
        (root / "connector_audit.db").unlink(missing_ok=True)
    except OSError:
        pass
    reset_default_logger()
    reset_langfuse_client()


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="p125-smoke",
    )


# -- Section S.2. Test cases ---------------------------------------------

def test_module_surface() -> None:
    print("[1/4] module / file surface ----------------------------------------")

    here = Path(__file__).resolve().parent
    yaml_path = here / "promptfoo.yaml"
    if not yaml_path.exists():
        _fail("promptfoo.yaml", f"missing at {yaml_path}")
    _ok(f"promptfoo.yaml present at {yaml_path.name}")

    text = yaml_path.read_text(encoding="utf-8")
    if "Apache License, Version 2.0" not in text:
        _fail("promptfoo.yaml header", "Apache 2.0 header missing")
    _ok("promptfoo.yaml carries Apache 2.0 header")

    if _yaml_mod is not None:
        try:
            data = _yaml_mod.safe_load(text)
        except Exception as exc:
            _fail("yaml.safe_load", str(exc))
        if not isinstance(data, dict):
            _fail("promptfoo.yaml shape", "top-level should be a dict")
        if not isinstance(data.get("tests"), list) or len(data["tests"]) != 8:
            _fail("promptfoo.yaml tests", f"expected 8 tests, got "
                  f"{len(data.get('tests') or [])}")
        _ok(f"promptfoo.yaml parses + has 8 test cases")
    else:
        _ok("PyYAML not installed; skipped YAML schema check")

    if len(PROMPTFOO_TEST_CASES) != 8:
        _fail("PROMPTFOO_TEST_CASES count", str(len(PROMPTFOO_TEST_CASES)))
    _ok(f"deepeval_suite mirrors 8 Promptfoo test cases")

    if len(SUGGESTION_LIBRARY) < 4:
        _fail("SUGGESTION_LIBRARY size", str(len(SUGGESTION_LIBRARY)))
    _ok(f"SUGGESTION_LIBRARY has {len(SUGGESTION_LIBRARY)} canonical entries")

    for name in (
        "ProvenanceScore", "MemoryRelevance", "PIISafety",
        "EvolutionQuality", "OverallSelfImprovement",
        "build_brief_for_eval", "run_full_loop",
        "build_improvement_suggestions", "promptfoo_stub_provider",
        "eval_results_root", "DEEPEVAL_BACKEND", "EvalReport",
    ):
        if not hasattr(_eval_pkg, name):
            _fail(f"eval.{name}", "missing")
    _ok("eval package re-exports the canonical 12-item public surface")


def test_metrics_scoring() -> None:
    print("[2/4] DeepEval custom metrics --------------------------------------")
    _wipe()
    out = build_brief_for_eval(force_stub=True)

    # Every metric scores in [0.0, 1.0].
    for cls in (ProvenanceScore, MemoryRelevance, PIISafety, EvolutionQuality):
        m: MetricResult = cls().measure(out)
        if not isinstance(m, MetricResult):
            _fail(cls.__name__, f"got {type(m)}")
        if not (0.0 <= m.score <= 1.0):
            _fail(cls.__name__, f"score out of range: {m.score}")
        if not (0.0 <= m.threshold <= 1.0):
            _fail(cls.__name__, f"threshold out of range: {m.threshold}")
    _ok("ProvenanceScore / MemoryRelevance / PIISafety / EvolutionQuality "
        "all score in [0.0, 1.0]")

    # PIISafety is binary — must be exactly 1.0 on the clean-stub brief.
    pii = PIISafety().measure(out)
    if pii.score != 1.0 or not pii.passed:
        _fail("PIISafety on clean brief", f"score={pii.score}, passed={pii.passed}")
    _ok("PIISafety = 1.0 on a clean stub brief")

    # Aggregate metric is the last entry of run_deepeval_metrics.
    metrics = run_deepeval_metrics(out)
    if len(metrics) != 5:
        _fail("metric count", str(len(metrics)))
    _ok("run_deepeval_metrics returns exactly 5 results")

    overall = metrics[-1]
    if overall.name != "OverallSelfImprovement":
        _fail("metric ordering", f"last metric = {overall.name}")
    if overall.score < 0.8 or not overall.passed:
        _fail("OverallSelfImprovement on stub", f"score={overall.score}")
    _ok(f"OverallSelfImprovement = {overall.score:.3f} on a clean stub brief")

    # No-collapse bonus contract: when one component score is below 0.5,
    # the no-collapse bonus must vanish from the aggregate.
    bad_components = [
        MetricResult(name="ProvenanceScore",  score=1.0, threshold=0.8, passed=True,  reason="t"),
        MetricResult(name="MemoryRelevance",  score=1.0, threshold=0.8, passed=True,  reason="t"),
        MetricResult(name="PIISafety",        score=0.0, threshold=1.0, passed=False, reason="t"),
        MetricResult(name="EvolutionQuality", score=1.0, threshold=0.8, passed=True,  reason="t"),
    ]
    overall_bad = OverallSelfImprovement(bad_components).measure()
    # PII collapse means score = 0.2*1 + 0.2*1 + 0.3*0 + 0.15*1 + 0 = 0.55
    if overall_bad.score >= 0.8:
        _fail("no-collapse penalty", f"PII at 0.0 should collapse score, got {overall_bad.score}")
    _ok("OverallSelfImprovement penalises single-axis collapse (PII=0 → score < 0.8)")


def test_promptfoo_assertions() -> None:
    print("[3/4] Promptfoo asserts --------------------------------------------")
    _wipe()
    out = build_brief_for_eval(force_stub=True)
    rows = run_promptfoo_assertions(out)
    if len(rows) != 8:
        _fail("assertion count", str(len(rows)))
    _ok("run_promptfoo_assertions returns 8 rows")

    pass_count = sum(1 for r in rows if r.get("passed"))
    if pass_count != 8:
        _fail("clean-brief passes", f"{pass_count}/8 — expected 8/8")
    _ok("clean stub brief passes 8/8 Promptfoo asserts")

    # Promptfoo stub provider returns valid JSON.
    raw = promptfoo_stub_provider("ignored", {})
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail("stub provider JSON", str(exc))
    if "brief" not in parsed:
        _fail("stub provider shape", "no 'brief' key in returned JSON")
    _ok("promptfoo_stub_provider returns valid JSON with a brief block")

    # Negative case: an artificially broken brief fails the structural assert.
    broken = {"brief": {"sections": {"only_one": {}}}, "stub": True}
    rows_bad = run_promptfoo_assertions(broken)
    structural = next(r for r in rows_bad if r["id"] == "T1")
    if structural["passed"]:
        _fail("T1 negative case", "should have failed on a broken brief")
    _ok("T1 (structural completeness) correctly fails on a broken brief")

    # Suggestions: a broken brief produces ≥ 1 human-review suggestion.
    metrics_bad = run_deepeval_metrics(broken)
    suggestions = build_improvement_suggestions(metrics_bad, rows_bad)
    if not suggestions:
        _fail("suggestions on broken brief", "expected ≥ 1")
    if any(s.get("status") != "needs_review" for s in suggestions):
        _fail("suggestion gate", "every suggestion must be needs_review")
    _ok(f"broken brief produces {len(suggestions)} human-review suggestions")


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
    if len(report.deepeval) != 5:
        _fail("report.deepeval size", str(len(report.deepeval)))
    _ok("EvalReport carries 8 Promptfoo rows + 5 DeepEval metrics")

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
    if "## DeepEval (5 metrics)" not in md_text:
        _fail("markdown shape", "DeepEval section missing")
    if "human-review-gated" not in md_text.lower() \
            and "human review required" not in md_text.lower():
        _fail("markdown gate language", "human-review note missing")
    _ok("Markdown report carries Promptfoo + DeepEval sections + human-review note")

    # ProvenanceRecord written by the loop.
    log = LocalProvenanceLogger()
    recs = [
        rec for rec in log.query_by_run_id(report.run_id)
    ]
    # The eval-loop's own run_id and the graph's run_id differ; the loop
    # writes ONE ProvenanceRecord at node_name=eval.run_full_loop. Find
    # it via the latest day file.
    day_path = current_log_path()
    found = False
    for line in day_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("node_name") == "eval.run_full_loop":
            found = True
            extra = d.get("extra") or {}
            if "eval" not in extra:
                _fail("provenance.extra.eval", "missing")
            if extra["eval"].get("overall_score") != report.overall_score:
                _fail("provenance score parity", "mismatch")
            break
    if not found:
        _fail("eval ProvenanceRecord", "no eval.run_full_loop record on disk")
    _ok("ProvenanceRecord 'eval.run_full_loop' written with embedded EvalReport")

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

    # CLI subprocess test via subprocess.run — the canonical PowerShell entry.
    here = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "agent.py", "improve", "--stub", "--quiet"],
        cwd=here, capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        _fail("subprocess improve", f"exit {proc.returncode}; stderr={proc.stderr[:200]}")
    _ok("`python agent.py improve --stub` runs cleanly via subprocess")

    # The DEEPEVAL_BACKEND constant is consistent with what the report says.
    if report.backend != DEEPEVAL_BACKEND:
        _fail("backend parity", f"{report.backend} vs {DEEPEVAL_BACKEND}")
    _ok(f"DEEPEVAL_BACKEND = {DEEPEVAL_BACKEND} (consistent)")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P125 Self-Evolving Personal OS self-improvement smoke test")
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
    print("RESULT: PASS — all 4 P125 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
