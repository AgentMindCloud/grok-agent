# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Self-Evolving Personal OS — LangGraph StateGraph (P119, Slot 2).

Built to help xAI and Grok win the agent platform battle on X.

This module is the LangGraph fallback runtime for the Personal OS
6-node DAG. The orchestrator's ``_dispatch`` calls ``build_runner``
when ``MASTRA_HTTP_URL`` is unset and ``langgraph`` is importable;
otherwise the orchestrator's pure-Python in-process safety net runs
the same DAG sequentially.

Mirrors the proven Living Narrative Fabric pattern at
``templates/super-agents/living-narrative-fabric/graph.py``: imports
the same node functions from the sibling ``orchestrator.py`` so node
behaviour cannot drift between runtimes.
"""

from __future__ import annotations

import importlib
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Import the sibling orchestrator (relative-then-absolute idiom)
# ---------------------------------------------------------------------------


def _import_orchestrator():
    try:
        from . import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
SourceItem = _orch.SourceItem
Insight = _orch.Insight
Pattern = _orch.Pattern
PersonalSourceClient = _orch.PersonalSourceClient
PersonalProvenanceLogger = _orch.PersonalProvenanceLogger
NoopPersonalProvenanceLogger = _orch.NoopPersonalProvenanceLogger
StubPersonalSourceClient = _orch.StubPersonalSourceClient
DEFAULT_PER_SOURCE_LIMIT = _orch.DEFAULT_PER_SOURCE_LIMIT
DEFAULT_SOURCE_AUTHORITY = _orch.DEFAULT_SOURCE_AUTHORITY

_node_ingest_personal = _orch._node_ingest_personal
_node_normalise_to_insights = _orch._node_normalise_to_insights
_node_detect_patterns = _orch._node_detect_patterns
_node_score_briefing_trust = _orch._node_score_briefing_trust
_node_audit_triggers = _orch._node_audit_triggers


# ---------------------------------------------------------------------------
# Soft LangGraph import — module is a no-op when langgraph is missing
# ---------------------------------------------------------------------------


try:
    from langgraph.graph import StateGraph, END  # type: ignore
    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover — soft import
    StateGraph = None  # type: ignore
    END = "__end__"
    _HAS_LANGGRAPH = False


# ---------------------------------------------------------------------------
# Wire-shape (de)serialisation — JSON-safe state for the LangGraph runtime
# ---------------------------------------------------------------------------


def _serialize_state_to_wire(state: dict) -> dict:
    return {
        "query":            state["query"],
        "for_date":         state["for_date"].isoformat()
                            if isinstance(state["for_date"], date) else state["for_date"],
        "time_zone":        state["time_zone"],
        "since":            state["since"].isoformat()
                            if isinstance(state["since"], datetime) else state["since"],
        "source_authority": state["source_authority"],
        "raw_items": [
            {
                "source":      i.source,
                "item_id":     i.item_id,
                "title":       i.title,
                "body":        i.body,
                "captured_at": i.captured_at.isoformat(),
                "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
                "url":         i.url,
                "extra":       dict(i.extra or {}),
            }
            for i in state.get("raw_items", [])
        ],
        "sources_called": list(state.get("sources_called", [])),
        "insights": [
            {
                "insight_id":    ins.insight_id,
                "subject":       ins.subject,
                "predicate":     ins.predicate,
                "value":         ins.value,
                "source":        ins.source,
                "source_id":     ins.source_id,
                "confidence":    float(ins.confidence),
                "captured_at":   ins.captured_at.isoformat(),
                "sentiment":     ins.sentiment,
                "pii_redacted":  bool(ins.pii_redacted),
                "signal_strength": float(ins.signal_strength),
            }
            for ins in state.get("insights", [])
        ],
        "patterns": [
            {
                "pattern_id":          p.pattern_id,
                "subject":             p.subject,
                "predicate":           p.predicate,
                "insight_ids":         list(p.insight_ids),
                "severity":            int(p.severity),
                "severity_components": dict(p.severity_components),
                "note":                p.note,
                "suggested_stance":    p.suggested_stance,
            }
            for p in state.get("patterns", [])
        ],
        "trust_metrics":  dict(state.get("trust_metrics", {})),
        "trust_score":    int(state.get("trust_score", 0)),
        "audit_triggered": bool(state.get("audit_triggered", False)),
        "audit_reasons":  list(state.get("audit_reasons", [])),
    }


def _hydrate_wire_state(wire: dict) -> dict:
    return {
        "query":     wire["query"],
        "for_date":  date.fromisoformat(wire["for_date"]),
        "time_zone": wire["time_zone"],
        "since":     datetime.fromisoformat(wire["since"]),
        "source_authority": dict(wire.get("source_authority") or {}),
        "raw_items": [],
        "sources_called": [],
        "insights": [],
        "patterns": [],
        "trust_metrics": {},
        "trust_score": 0,
        "audit_triggered": False,
        "audit_reasons": [],
    }


# ---------------------------------------------------------------------------
# Node wrappers — let LangGraph call into the orchestrator's exact functions
# ---------------------------------------------------------------------------


def _make_default_sources(state: dict) -> tuple[PersonalSourceClient, ...]:
    """When the wire state names sources but doesn't carry instances, build
    stubs by name. Slot 4 will pass real connector instances via the
    orchestrator's local in-process path — this graph is the fallback."""

    return tuple(
        StubPersonalSourceClient(name=name)
        for name in ("x_personal", "gcal", "gmail", "local_notes", "weather", "news_personal")
    )


def _wrap_ingest(state: dict) -> dict:
    sources = _make_default_sources(state)
    logger = NoopPersonalProvenanceLogger()
    return _node_ingest_personal(
        state, sources=sources, per_source_limit=DEFAULT_PER_SOURCE_LIMIT, logger=logger,
    )


def _wrap_normalise(state: dict) -> dict:
    return _node_normalise_to_insights(state, logger=NoopPersonalProvenanceLogger())


def _wrap_detect_patterns(state: dict) -> dict:
    return _node_detect_patterns(state, logger=NoopPersonalProvenanceLogger())


def _wrap_score(state: dict) -> dict:
    return _node_score_briefing_trust(state)


def _wrap_audit(state: dict) -> dict:
    return _node_audit_triggers(state, force_audit=False)


# ---------------------------------------------------------------------------
# Build the LangGraph StateGraph
# ---------------------------------------------------------------------------


def build_graph() -> Optional[Any]:
    """Construct and compile the LangGraph StateGraph. Returns ``None`` when
    ``langgraph`` is not installed."""

    if not _HAS_LANGGRAPH:
        return None
    g = StateGraph(dict)  # type: ignore[call-arg]
    g.add_node("ingest_personal",      _wrap_ingest)
    g.add_node("normalise",            _wrap_normalise)
    g.add_node("detect_patterns",      _wrap_detect_patterns)
    g.add_node("score_briefing_trust", _wrap_score)
    g.add_node("audit",                _wrap_audit)
    g.set_entry_point("ingest_personal")
    g.add_edge("ingest_personal",      "normalise")
    g.add_edge("normalise",            "detect_patterns")
    g.add_edge("detect_patterns",      "score_briefing_trust")
    g.add_edge("score_briefing_trust", "audit")
    g.add_edge("audit",                END)
    return g.compile()


def build_runner(state_in: dict):
    """Entry point used by ``orchestrator._dispatch``.

    Returns the wire-shaped output state on success, or ``None`` when
    LangGraph is unavailable so the orchestrator falls through to its
    pure-Python in-process safety net.
    """

    runner = build_graph()
    if runner is None:
        return None
    state = _hydrate_wire_state(state_in)
    out = runner.invoke(state)
    return _serialize_state_to_wire(out)


__all__ = (
    "build_graph",
    "build_runner",
)
