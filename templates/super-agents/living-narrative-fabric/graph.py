# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — LangGraph fallback runtime (P110, Slot 2 sibling).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module is the optional LangGraph runtime for the Living Narrative Fabric
orchestrator. The orchestrator (``orchestrator.py``) prefers Mastra as the
primary runtime when ``MASTRA_HTTP_URL`` is set, otherwise it imports
``build_runner`` from this module and runs the same DAG as a
``langgraph.StateGraph``.

Why a separate runtime file?
============================

The DAG itself (ingest → normalise → contradiction-detect → confidence-score
→ audit-triggers → finalize) is defined in ``orchestrator.py`` as plain
Python functions. This file's only job is to:

1. Re-shape those functions into a ``langgraph.StateGraph``.
2. Expose a single ``build_runner(state_in: dict) -> dict`` entry point that
   accepts the JSON-safe state dict the orchestrator emits, runs the graph,
   and returns the JSON-safe state dict the orchestrator merges back.
3. Fail cleanly when ``langgraph`` is not installed so the orchestrator can
   keep falling through to its in-process safety net.

That separation keeps ``orchestrator.py`` runnable on a fresh Windows box
with only ``pydantic`` installed (the in-process path), while still letting
power users opt into LangGraph by ``pip install langgraph``.

Slot boundary
=============

This file does NOT replace the in-process implementation in
``orchestrator.py``. It mirrors it. If the two ever drift, ``orchestrator.py``
is the source of truth and this file must be brought back in line. The
contradiction-detection, scoring, and audit-trigger logic is imported from
``orchestrator.py`` so a single change there propagates here automatically.
"""

from __future__ import annotations

import importlib
from datetime import datetime
from typing import Any, Optional

# We import the orchestrator module lazily inside ``build_runner`` so that
# importing ``graph.py`` directly never triggers a circular import when the
# orchestrator imports us.


# ---------------------------------------------------------------------------
# State schema (mirrors the orchestrator's in-process state dict)
# ---------------------------------------------------------------------------

#: Keys carried through the LangGraph state. We use a plain ``dict`` (the
#: native LangGraph state shape) rather than a TypedDict so we can stay
#: compatible with multiple LangGraph minor versions without breaking on
#: import.
GRAPH_STATE_KEYS = (
    "topic",
    "time_range",
    "since",
    "source_authority",
    "source_names",          # list[str] passed in by orchestrator
    "per_source_limit",
    "raw_items",
    "sources_called",
    "claims",
    "contradictions",
    "confidence_metrics",
    "confidence_score",
    "audit_triggered",
    "audit_reasons",
)


# ---------------------------------------------------------------------------
# Helpers — re-hydrate the orchestrator's dataclasses from / to JSON
# ---------------------------------------------------------------------------


def _hydrate_state_from_wire(wire: dict) -> dict:
    """Convert the JSON-safe state from the orchestrator into a state dict
    whose ``raw_items``, ``claims``, ``contradictions`` are the orchestrator's
    own dataclass instances. We never reach this with non-empty raw_items —
    the LangGraph runtime starts at the ``ingest`` node — so the conversion
    is mostly about ``since`` and ``source_authority``.
    """

    state = dict(wire)
    if isinstance(state.get("since"), str):
        state["since"] = datetime.fromisoformat(state["since"])
    state.setdefault("raw_items", [])
    state.setdefault("sources_called", [])
    state.setdefault("claims", [])
    state.setdefault("contradictions", [])
    return state


def _serialize_state_to_wire(state: dict) -> dict:
    """Convert the orchestrator-dataclass-bearing state dict back into a
    JSON-safe wire dict the orchestrator can consume in
    ``LivingNarrativeFabric._merge_remote_state``.
    """

    out: dict = {}
    out["topic"] = state["topic"]
    out["time_range"] = state["time_range"]
    out["since"] = state["since"].isoformat() if isinstance(state.get("since"), datetime) else state.get("since")
    out["source_authority"] = state.get("source_authority", {})
    out["source_names"] = list(state.get("source_names") or [])
    out["per_source_limit"] = state.get("per_source_limit")

    out["raw_items"] = [
        {
            "source": ri.source,
            "item_id": ri.item_id,
            "title": ri.title,
            "body": ri.body,
            "retrieved_at": ri.retrieved_at.isoformat(),
            "published_at": ri.published_at.isoformat() if ri.published_at else None,
            "url": ri.url,
            "extra": dict(ri.extra) if ri.extra else {},
        }
        for ri in state.get("raw_items", [])
    ]
    out["sources_called"] = list(state.get("sources_called") or [])
    out["claims"] = [
        {
            "claim_id": c.claim_id,
            "subject": c.subject,
            "predicate": c.predicate,
            "value": c.value,
            "source": c.source,
            "source_id": c.source_id,
            "confidence": c.confidence,
            "extracted_at": c.extracted_at.isoformat(),
            "sentiment": c.sentiment,
        }
        for c in state.get("claims", [])
    ]
    out["contradictions"] = [
        {
            "contradiction_id": cd.contradiction_id,
            "subject": cd.subject,
            "predicate": cd.predicate,
            "claim_ids": list(cd.claim_ids),
            "severity": cd.severity,
            "severity_components": dict(cd.severity_components),
            "note": cd.note,
        }
        for cd in state.get("contradictions", [])
    ]
    out["confidence_metrics"] = dict(state.get("confidence_metrics") or {})
    out["confidence_score"] = state.get("confidence_score")
    out["audit_triggered"] = bool(state.get("audit_triggered"))
    out["audit_reasons"] = list(state.get("audit_reasons") or [])
    return out


# ---------------------------------------------------------------------------
# Public entry point — orchestrator.py calls this when MASTRA_HTTP_URL is unset
# ---------------------------------------------------------------------------


def build_runner(state_in: dict) -> Optional[dict]:
    """Run the Living Narrative Fabric DAG via LangGraph and return the wire state.

    Returns ``None`` when ``langgraph`` is not installed so the orchestrator
    can fall through cleanly to its in-process safety net.
    """

    try:
        langgraph_graph = importlib.import_module("langgraph.graph")
    except Exception:
        return None

    # Lazy-import the orchestrator to reuse its dataclasses + node functions.
    try:
        from . import orchestrator as orch  # type: ignore
    except Exception:
        try:
            import orchestrator as orch  # type: ignore
        except Exception:
            return None

    StateGraph = getattr(langgraph_graph, "StateGraph", None)
    END = getattr(langgraph_graph, "END", "__end__")
    if StateGraph is None:
        return None

    state = _hydrate_state_from_wire(state_in)

    # Reconstruct the source clients from their names so the ingest node
    # can call them. We only know names on the wire; the LangGraph runtime
    # uses the same StubSourceClient class as the in-process path. Slot 4
    # (P112) will replace this construction with a registry lookup.
    sources = tuple(
        orch.StubSourceClient(name=name) for name in (state.get("source_names") or [])
    )
    if not sources:
        sources = orch._default_stub_sources()

    logger = orch.NoopProvenanceLogger()
    per_source_limit = int(state.get("per_source_limit") or orch.DEFAULT_PER_SOURCE_LIMIT)

    # ---- Node wrappers ----------------------------------------------------
    # LangGraph nodes must be callables that accept and return a state dict.
    # Each one delegates to the orchestrator's pure-function node.

    def node_ingest(s: dict) -> dict:
        return orch._node_ingest(
            s,
            sources=sources,
            per_source_limit=per_source_limit,
            logger=logger,
        )

    def node_normalise(s: dict) -> dict:
        return orch._node_normalise_to_claims(s, logger=logger)

    def node_contradict(s: dict) -> dict:
        return orch._node_detect_contradictions(s, logger=logger)

    def node_score(s: dict) -> dict:
        return orch._node_score_confidence(s)

    def node_audit(s: dict) -> dict:
        return orch._node_audit_triggers(s, force_audit=False)

    # ---- StateGraph wiring ------------------------------------------------
    # We use ``dict`` as the schema rather than a TypedDict because the
    # node return type is a partial state update and LangGraph merges by key.
    builder: Any = StateGraph(dict)

    builder.add_node("ingest", node_ingest)
    builder.add_node("normalise", node_normalise)
    builder.add_node("contradict", node_contradict)
    builder.add_node("score", node_score)
    builder.add_node("audit", node_audit)

    builder.set_entry_point("ingest")
    builder.add_edge("ingest", "normalise")
    builder.add_edge("normalise", "contradict")
    builder.add_edge("contradict", "score")
    builder.add_edge("score", "audit")
    builder.add_edge("audit", END)

    try:
        compiled = builder.compile()
        result = compiled.invoke(state)
    except Exception:
        return None

    if not isinstance(result, dict):
        return None
    return _serialize_state_to_wire(result)


__all__ = (
    "GRAPH_STATE_KEYS",
    "build_runner",
)
