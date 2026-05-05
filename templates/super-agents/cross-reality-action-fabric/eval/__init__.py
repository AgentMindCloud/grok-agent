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
"""Self-improvement evaluation package for Cross-Reality Action Fabric (P132).

Two artefacts:

- :mod:`eval.deepeval_suite`  Python harness for the 6 custom metrics +
                              CLI runner + Promptfoo-mirror predicates +
                              suggestion library.
- ``eval/promptfoo.yaml``     YAML config consumed by the real
                              ``promptfoo`` CLI; mirrored at runtime by
                              :data:`eval.deepeval_suite.PROMPTFOO_TEST_CASES`.

Both default to local-first + stub-friendly so the weekly improve loop
runs on Windows without ever phoning home unless the user opts in via
``LANGFUSE_*`` env + ``opt_in=True`` (consistent with P131).

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

__all__ = [
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
]
