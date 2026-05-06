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
"""Self-improvement evaluation package for Cross-Reality Action Fabric.

Three artefacts:

- :mod:`eval.deepeval_suite`     Python harness for the 6 custom metrics
                                 + CLI runner + Promptfoo-mirror
                                 predicates + suggestion library (P132).
- ``eval/promptfoo.yaml``        YAML config consumed by the real
                                 ``promptfoo`` CLI; mirrored at runtime
                                 by :data:`eval.deepeval_suite.PROMPTFOO_TEST_CASES`.
- :mod:`eval.improvement_loop`   Weekly self-improvement loop layered on
                                 top of P132. Pulls historical
                                 performance from the P140 memory
                                 client and the P142 provenance logger,
                                 produces typed Pydantic
                                 :class:`Suggestion` rows with
                                 ``before``/``after`` diffs, persists
                                 reports to AppData, and writes one
                                 P142 ``run_complete`` provenance row
                                 per loop run (P143).

All three default to local-first + stub-friendly so the weekly improve
loop runs on Windows without ever phoning home unless the user opts in
via ``LANGFUSE_*`` env + ``opt_in=True`` (consistent with P131 / P142).

Built to help xAI and Grok win.
"""

from __future__ import annotations

from eval.deepeval_suite import (  # type: ignore  # noqa: F401
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
from eval.improvement_loop import (  # type: ignore  # noqa: F401
    APPROVALS_RELATIVE,
    DEFAULT_LOOKBACK_DAYS,
    LoopReport,
    MAX_LOOKBACK_DAYS,
    Suggestion,
    WeeklyImprovementLoop,
    approvals_root,
    get_default_loop,
    loop_results_root,
    loop_status,
    reset_default_loop,
    run_loop,
)

__all__ = [
    # P132 surface
    "ActionQuality",
    "ApprovalCompliance",
    "CostEfficiency",
    "DEEPEVAL_BACKEND",
    "EvalReport",
    "MetricResult",
    "OverallActionImprovement",
    "PROMPTFOO_TEST_CASES",
    "RollbackSuccess",
    "SafetyScore",
    "SUGGESTION_LIBRARY",
    "build_improvement_suggestions",
    "build_run_for_eval",
    "eval_results_root",
    "promptfoo_stub_provider",
    "run_deepeval_metrics",
    "run_full_loop",
    "run_promptfoo_assertions",
    # P143 self-improvement loop
    "APPROVALS_RELATIVE",
    "DEFAULT_LOOKBACK_DAYS",
    "MAX_LOOKBACK_DAYS",
    "LoopReport",
    "Suggestion",
    "WeeklyImprovementLoop",
    "approvals_root",
    "get_default_loop",
    "loop_results_root",
    "loop_status",
    "reset_default_loop",
    "run_loop",
]
