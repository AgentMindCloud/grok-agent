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
"""Cross-Reality Action Fabric — Super Agent #3.

This is the package re-exporter for the third (and final) flagship Super
Agent in the Grok Agent OS roadmap. It pulls the public surface of the
two building blocks into a single import line:

- :mod:`graph`   LangGraph state machine with HITL gate + rollback
- :mod:`agent`   PowerShell-friendly CLI that drives the graph

Subsequent prompts (P130 memory, P131 connectors, P132 provenance,
P133 self-improve, P134 dashboard, P135 demo + launch thread) will
re-export their own surfaces from this same module.

Caller-facing example:

.. code-block:: python

    from cross_reality_action_fabric import (
        ConsentContext,
        run_action_loop,
        daily_plan,
    )

    out = run_action_loop(force_stub=True, user_request="hello")

The folder name on disk is ``cross-reality-action-fabric/`` (kebab-case
to match the Hard Rules in CLAUDE.md), so this package is normally
imported with the folder added to ``sys.path`` rather than as a dotted
name. The :mod:`agent` module's ``__main__`` guard handles that
automatically when the script is invoked directly.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

# --- P129 graph + agent -----------------------------------------------------
from graph import (  # type: ignore  # noqa: F401
    AGENT_NAME,
    ALLOWED_TOOLS,
    BACKEND_NAME,
    ConsentContext,
    ConstitutionViolation,
    CrossRealityState,
    DEFAULT_PROMPT_VERSION,
    MAX_ACTIONS_PER_PLAN,
    MAX_PLAN_LOOPS,
    READ_ONLY_TOOLS,
    STATE_CHANGING_TOOLS,
    ActionPlan,
    ActionStep,
    appdata_root,
    build_graph,
    build_state,
    describe_graph,
    execute_realworld,
    execute_web,
    execute_windows,
    execute_x,
    make_consent_token,
    make_run_id,
    output_with_provenance,
    plan_actions,
    redact_pii,
    request_approval,
    rollback,
    route_after_approval,
    route_after_execution,
    run_action_loop,
)
from agent import (  # type: ignore  # noqa: F401
    AGENT_VERSION,
    ALL_GATES,
    approve_pending,
    build_default_consent,
    daily_plan,
    execute_action,
    info,
    log_path,
    main,
    pending_plan_path,
    rollback_last,
    runs_dir,
    search,
)

__all__ = [
    # graph constants + classes
    "AGENT_NAME",
    "AGENT_VERSION",
    "ALLOWED_TOOLS",
    "ALL_GATES",
    "BACKEND_NAME",
    "ConsentContext",
    "ConstitutionViolation",
    "CrossRealityState",
    "DEFAULT_PROMPT_VERSION",
    "MAX_ACTIONS_PER_PLAN",
    "MAX_PLAN_LOOPS",
    "READ_ONLY_TOOLS",
    "STATE_CHANGING_TOOLS",
    "ActionPlan",
    "ActionStep",
    # graph functions
    "appdata_root",
    "build_graph",
    "build_state",
    "describe_graph",
    "execute_realworld",
    "execute_web",
    "execute_windows",
    "execute_x",
    "make_consent_token",
    "make_run_id",
    "output_with_provenance",
    "plan_actions",
    "redact_pii",
    "request_approval",
    "rollback",
    "route_after_approval",
    "route_after_execution",
    "run_action_loop",
    # CLI commands
    "approve_pending",
    "build_default_consent",
    "daily_plan",
    "execute_action",
    "info",
    "log_path",
    "main",
    "pending_plan_path",
    "rollback_last",
    "runs_dir",
    "search",
]
