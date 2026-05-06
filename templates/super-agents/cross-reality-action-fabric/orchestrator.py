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
"""Cross-Reality Action Fabric — orchestrator module.

Top-level orchestration entry point for Super Agent #3. Exists for
parity with ``living-narrative-fabric/orchestrator.py`` and
``self-evolving-personal-os/orchestrator.py`` so external callers can
follow the same import shape across all three flagships:

.. code-block:: python

    from orchestrator import CrossRealityActionFabric, daily_plan, \
        execute_action, search, approve_pending, rollback_last, info

The actual orchestration graph lives in ``graph.py`` and the
PowerShell-friendly CLI lives in ``agent.py``. This module re-exports
the public surface so consumers don't have to know which file holds
which piece.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""
from __future__ import annotations

# Re-export the user-facing functions from agent.py.
from agent import (  # noqa: F401  (re-export)
    build_default_consent,
    daily_plan,
    describe_connectors,
    describe_eval_status,
    describe_provenance,
    execute_action,
    info,
    register_connectors,
    register_eval_loop,
    register_provenance,
    rollback_last,
    search,
    approve_pending,
)

# Re-export the LangGraph wrapper from graph.py if available; fall back
# silently so this module can still be imported when graph.py was
# trimmed in a slim install.
try:
    from graph import build_graph, GraphState  # noqa: F401  (re-export)
except Exception:  # pragma: no cover - optional path
    build_graph = None  # type: ignore[assignment]
    GraphState = None  # type: ignore[assignment]


class CrossRealityActionFabric:
    """Thin facade around the agent.py + graph.py public API.

    Every method here delegates to a function in ``agent.py`` so the
    interface stays in lockstep with the user-visible CLI. This class
    exists purely to mirror the
    ``LivingNarrativeFabric`` / ``SelfEvolvingPersonalOS`` shape used
    by Super Agents #1 and #2.
    """

    @staticmethod
    def daily_plan(*args, **kwargs):
        return daily_plan(*args, **kwargs)

    @staticmethod
    def execute_action(*args, **kwargs):
        return execute_action(*args, **kwargs)

    @staticmethod
    def search(*args, **kwargs):
        return search(*args, **kwargs)

    @staticmethod
    def approve_pending(*args, **kwargs):
        return approve_pending(*args, **kwargs)

    @staticmethod
    def rollback_last(*args, **kwargs):
        return rollback_last(*args, **kwargs)

    @staticmethod
    def info(*args, **kwargs):
        return info(*args, **kwargs)


__all__ = [
    "CrossRealityActionFabric",
    "daily_plan",
    "execute_action",
    "search",
    "approve_pending",
    "rollback_last",
    "info",
    "build_default_consent",
    "describe_connectors",
    "describe_eval_status",
    "describe_provenance",
    "register_connectors",
    "register_eval_loop",
    "register_provenance",
    "build_graph",
    "GraphState",
]


if __name__ == "__main__":  # pragma: no cover
    # Minimal smoke check: print the registered surface.
    print("CrossRealityActionFabric orchestrator module")
    print("Public API:")
    for name in __all__:
        print(f"  - {name}")
