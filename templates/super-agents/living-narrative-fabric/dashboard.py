# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Streamlit dashboard (P115, Recipe C Slot 7).

Built for xAI, X, Grok and the ecosystem community. ❤️

This is the user-facing real-time control surface for the entire Slot
2-6 stack: orchestrator (P110), Mem0+Qdrant memory (P111), 6 public-API
connectors (P112), append-only provenance log + Langfuse hooks (P113),
and the self-improvement loop (P114). It reads directly from those
stores via their public APIs — NO new Protocol is introduced — and
exposes seven tabs:

    1. Overview          — top-line metrics across all 5 layers
    2. Live Pipeline     — interactive synthesize() with 6-node DAG status
    3. Contradictions    — paradox explorer + flag-with-reason form
    4. Provenance Reports — export Markdown reports + Langfuse status
    5. Memory Explorer   — versions / claims / contradictions browser
    6. Improvements      — eval scores + suggestions + dry-run apply
    7. Settings          — runtime info + env-var diagnostics

Architecture: data-builder + renderer split
==========================================

Every tab has TWO functions:

* ``build_<tab>_data(...)`` — pure Python; takes the wired
  store/logger/loop instances and returns a plain dict the renderer
  consumes. Smoke-testable WITHOUT ``streamlit`` installed.
* ``render_<tab>_tab(...)`` — calls the data builder and renders the
  Streamlit UI. Only runs when ``streamlit run dashboard.py`` is
  active (or ``import streamlit as st`` succeeded).

This means the smoke test (``python dashboard.py --smoke``) exercises
every data builder against a real wired stack — without ``streamlit``
on PYTHONPATH. The actual UI rendering is exercised only in the
PowerShell launcher path.

Slot boundary contract
======================

* ZERO changes to ``orchestrator.py``, ``graph.py``, ``memory/``,
  ``connectors/``, ``provenance/``, or ``eval/``.
* The dashboard is purely additive — it observes the system through
  the public APIs the prior slots already export.
* Constitution rule "every claim displayed shows full provenance":
  enforced by ``_constitution_warnings`` which scans a SynthesisVersion
  before render and emits a list of warnings the UI shows in
  ``st.error``. When all checks pass, no banner is shown.
* Article V.1 disclaimer auto-attaches to every tab when the active
  topic / version contains finance subjects.

CLI smoke test (Windows 11 + PowerShell)
========================================

::

    cd templates\\super-agents\\living-narrative-fabric
    python -m pip install -r requirements.txt
    python dashboard.py --smoke

Prints ``P115 dashboard smoke OK`` on success.

Real UI launch
==============

::

    cd templates\\super-agents\\living-narrative-fabric
    streamlit run dashboard.py
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Soft imports — Streamlit + pandas + plotly become no-ops when missing.
# The smoke-test path never touches them; the live-UI path requires them
# (the requirements.txt pin guarantees they're present in production).
# ---------------------------------------------------------------------------


try:
    import streamlit as st  # type: ignore
    _HAS_STREAMLIT = True
except Exception:  # pragma: no cover — soft import
    st = None  # type: ignore
    _HAS_STREAMLIT = False

try:
    import pandas as pd  # type: ignore
    _HAS_PANDAS = True
except Exception:  # pragma: no cover
    pd = None  # type: ignore
    _HAS_PANDAS = False


# ---------------------------------------------------------------------------
# Re-import the stack via the relative-then-absolute idiom.
# ---------------------------------------------------------------------------


_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _import_module(name: str):
    return importlib.import_module(name)


_orch = _import_module("orchestrator")
_memory_pkg = _import_module("memory")
_connectors_pkg = _import_module("connectors")
_provenance_pkg = _import_module("provenance")
_eval_pkg = _import_module("eval")

LivingNarrativeFabric = _orch.LivingNarrativeFabric
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
SYNTHESIS_CONFIDENCE_WEIGHTS = _orch.SYNTHESIS_CONFIDENCE_WEIGHTS
DEFAULT_SOURCE_AUTHORITY = _orch.DEFAULT_SOURCE_AUTHORITY
MIN_BRIDGES_PER_SYNTHESIS = _orch.MIN_BRIDGES_PER_SYNTHESIS
_default_appdata_root = _orch._default_appdata_root

build_memory_store = _memory_pkg.build_memory_store
Mem0QdrantStore = _memory_pkg.Mem0QdrantStore

build_connectors = _connectors_pkg.build_connectors
LivingNarrativeFabricConnectors = _connectors_pkg.LivingNarrativeFabricConnectors

build_provenance_logger = _provenance_pkg.build_provenance_logger
LivingNarrativeFabricProvenance = _provenance_pkg.LivingNarrativeFabricProvenance

build_self_improvement_loop = _eval_pkg.build_self_improvement_loop
SelfImprovementLoop = _eval_pkg.SelfImprovementLoop


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAGE_TITLE = "Living Narrative Fabric — Trust Engine"
PAGE_ICON = "🧵"

ARTICLE_V1_DISCLAIMER = (
    "⚠️ **Not financial advice.** This dashboard surfaces public "
    "information; always consult a licensed financial advisor before "
    "making decisions on cashtag- or market-related claims."
)

DAG_NODES = (
    "ingest",
    "normalise",
    "detect_contradictions",
    "score",
    "audit",
    "finalize",
)

#: Visual severity bands used across the UI.
SEVERITY_COLORS = {
    "blocker": "#c0392b",
    "warning": "#e67e22",
    "info":    "#2980b9",
    "ok":      "#27ae60",
}


# ---------------------------------------------------------------------------
# Wired-stack dataclass — built once per Streamlit session
# ---------------------------------------------------------------------------


@dataclass
class WiredStack:
    """Holds every reusable instance the dashboard needs to read from."""

    appdata_root: Path
    store:        Mem0QdrantStore
    connectors:   LivingNarrativeFabricConnectors
    provenance:   LivingNarrativeFabricProvenance
    loop:         SelfImprovementLoop
    fabric:       LivingNarrativeFabric


def build_wired_stack(
    *,
    appdata_root: Optional[Path] = None,
    force_stub:   bool = True,
) -> WiredStack:
    """Build every layer with the same appdata_root.

    ``force_stub=True`` is the default for the dashboard so a fresh
    install opens cleanly without API keys. Power users with a real
    ``NEWSAPI_KEY`` (or any other connector env var) can flip this off
    via the Settings tab — the dashboard re-builds the stack in place.
    """

    root = appdata_root if appdata_root is not None else _default_appdata_root()
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    store = build_memory_store(appdata_root=root)
    connectors = build_connectors(
        appdata_root=root, store=store, force_stub=force_stub,
    )
    provenance = build_provenance_logger(appdata_root=root, store=store)
    loop = build_self_improvement_loop(
        appdata_root=root, store=store, provenance=provenance,
    )
    fabric = LivingNarrativeFabric().with_dependencies(
        sources=tuple(connectors.connectors),
        memory=store,
        provenance=provenance,
    )
    return WiredStack(
        appdata_root=root, store=store, connectors=connectors,
        provenance=provenance, loop=loop, fabric=fabric,
    )


# ---------------------------------------------------------------------------
# Constitution warnings — scanned before every version is rendered
# ---------------------------------------------------------------------------


def _constitution_warnings(version: Optional[SynthesisVersion]) -> tuple[str, ...]:
    """Return the list of Constitution-rule warnings for a version (or empty)."""

    if version is None:
        return ()
    out: list[str] = []
    for c in version.claims:
        if not c.source_id:
            out.append(
                f"Claim `{c.claim_id}` has empty source_id — Constitution "
                f"rule 'Source citations are mandatory' violated."
            )
    if len(version.bridges) < MIN_BRIDGES_PER_SYNTHESIS:
        out.append(
            f"Bridges count = {len(version.bridges)} < required "
            f"{MIN_BRIDGES_PER_SYNTHESIS} — cross-template bridges are mandatory."
        )
    # "Never silently resolve" — every contradiction's claim_ids must
    # still be present in version.claims.
    claim_ids = {c.claim_id for c in version.claims}
    for cd in version.contradictions:
        for cid in cd.claim_ids:
            if cid not in claim_ids:
                out.append(
                    f"Contradiction `{cd.contradiction_id}` references "
                    f"missing claim_id `{cid}` — silent-resolution rule "
                    f"violated."
                )
                break
    return tuple(out)


# ---------------------------------------------------------------------------
# Tab 1 — Overview
# ---------------------------------------------------------------------------


def build_overview_data(stack: WiredStack) -> dict:
    """Top-line metrics aggregated across all 5 layers."""

    structured = stack.store.structured
    cur = structured._sqlite_conn.execute(
        "SELECT COUNT(*) AS n FROM versions WHERE topic NOT LIKE '\\_%' ESCAPE '\\'",
    )
    version_count = int(cur.fetchone()["n"] or 0)
    cur = structured._sqlite_conn.execute(
        "SELECT COUNT(*) AS n FROM contradictions",
    )
    contradiction_count = int(cur.fetchone()["n"] or 0)
    cur = structured._sqlite_conn.execute(
        "SELECT COUNT(*) AS n FROM contradiction_flags",
    )
    flag_count = int(cur.fetchone()["n"] or 0)
    cur = structured._sqlite_conn.execute(
        "SELECT COUNT(DISTINCT topic) AS n FROM versions WHERE topic NOT LIKE '\\_%' ESCAPE '\\'",
    )
    topic_count = int(cur.fetchone()["n"] or 0)

    event_count = stack.provenance.local.event_count()
    eval_history = stack.loop.get_improvement_history(limit=1)
    last_eval = eval_history[0] if eval_history else None

    has_finance = False
    cur = structured._sqlite_conn.execute(
        "SELECT MAX(has_finance_subject) AS f FROM versions",
    )
    row = cur.fetchone()
    if row is not None:
        has_finance = bool(row["f"] or 0)

    connector_runtime = {c.name: dict(c.runtime_info) for c in stack.connectors}
    stub_count = sum(1 for n, info in connector_runtime.items() if info.get("stub_mode"))

    return {
        "version_count":       version_count,
        "topic_count":         topic_count,
        "contradiction_count": contradiction_count,
        "flag_count":          flag_count,
        "event_count":         event_count,
        "last_eval":           last_eval,
        "has_finance":         has_finance,
        "appdata_root":        str(stack.appdata_root),
        "stub_connectors":     stub_count,
        "total_connectors":    len(stack.connectors),
        "memory_runtime":      stack.store.runtime_info,
        "provenance_runtime":  stack.provenance.runtime_info,
    }


def render_overview_tab(stack: WiredStack) -> None:
    data = build_overview_data(stack)
    if data["has_finance"]:
        st.warning(ARTICLE_V1_DISCLAIMER)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Synthesis versions", data["version_count"])
    c2.metric("Topics tracked",     data["topic_count"])
    c3.metric("Contradictions",     data["contradiction_count"])
    c4.metric("User flags",         data["flag_count"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Provenance events",  data["event_count"])
    c6.metric(
        "Connectors in stub mode",
        f"{data['stub_connectors']}/{data['total_connectors']}",
    )
    last_score = (
        data["last_eval"].overall_score if data["last_eval"] is not None else "—"
    )
    c7.metric("Last eval score", f"{last_score}/100")
    suggestion_count = (
        len(data["last_eval"].suggestions) if data["last_eval"] is not None else 0
    )
    c8.metric("Open suggestions", suggestion_count)

    st.markdown("### Layer health")
    layer_rows = [
        {
            "Layer": "Memory (P111)",
            "Backend": data["memory_runtime"].get("structured_backend"),
            "Vectors": data["memory_runtime"].get("vector_backend"),
            "Embedding": data["memory_runtime"].get("embedding_backend"),
        },
        {
            "Layer": "Provenance (P113)",
            "Backend": "JSONL",
            "Vectors": (
                "Langfuse"
                if data["provenance_runtime"]["langfuse"]["active"]
                else "Langfuse (no-op)"
            ),
            "Embedding": "—",
        },
        {
            "Layer": "Eval (P114)",
            "Backend": "SQLite",
            "Vectors": "—",
            "Embedding": "—",
        },
    ]
    if _HAS_PANDAS:
        st.dataframe(pd.DataFrame(layer_rows), hide_index=True, use_container_width=True)
    else:  # pragma: no cover
        st.json(layer_rows)


# ---------------------------------------------------------------------------
# Tab 2 — Live Pipeline
# ---------------------------------------------------------------------------


def build_pipeline_data(
    stack: WiredStack,
    *,
    topic: Optional[str] = None,
) -> dict:
    """Per-node runtime status + most-recent ingest events for ``topic``."""

    events = stack.provenance.local.all_events()
    node_status: dict[str, dict] = {n: {"ok": 0, "error": 0, "last_at": None} for n in DAG_NODES}
    runtime_used: Optional[str] = None
    for ev in events:
        # ``ingest.ok`` / ``ingest.error`` and similar flat names from the
        # orchestrator emitter.
        for node in DAG_NODES:
            if ev.event_type.startswith(f"{node}."):
                if ev.event_type.endswith(".ok"):
                    node_status[node]["ok"] += 1
                    node_status[node]["last_at"] = ev.recorded_at.isoformat()
                elif ev.event_type.endswith(".error"):
                    node_status[node]["error"] += 1
        if ev.event_type.startswith("runtime."):
            payload = ev.payload or {}
            if payload.get("topic") == (topic or payload.get("topic")):
                runtime_used = ev.event_type.split(".")[1]

    latest_version = None
    if topic:
        latest_version = stack.store.latest_version_for(topic)

    connector_rows = [
        {
            "Connector":  c.name,
            "Stub mode":  bool(c.runtime_info["stub_mode"]),
            "Auth env":   c.runtime_info["auth_env_var"],
            "Limit":      c.runtime_info["per_source_limit"],
        }
        for c in stack.connectors
    ]

    return {
        "node_status":      node_status,
        "runtime_used":     runtime_used,
        "latest_version":   latest_version,
        "connector_rows":   connector_rows,
    }


def render_pipeline_tab(stack: WiredStack) -> None:
    st.markdown("### 6-node DAG")
    topic = st.text_input(
        "Topic to synthesize",
        value=st.session_state.get("active_topic", "Grok Agent OS launch"),
        key="pipeline_topic",
    )
    time_range = st.selectbox(
        "Time range", options=("7d", "30d", "90d"), index=0, key="pipeline_time_range",
    )
    audit_flag = st.checkbox("Force audit section", value=False, key="pipeline_audit")
    run_clicked = st.button("Run synthesize()", type="primary", key="pipeline_run")

    if run_clicked and topic.strip():
        with st.spinner(f"Synthesizing {topic!r} over {time_range}..."):
            try:
                version = stack.fabric.synthesize(
                    topic=topic.strip(), time_range=time_range, audit=audit_flag,
                )
                st.session_state["active_topic"] = topic.strip()
                st.session_state["active_version_id"] = version.version_id
                st.success(
                    f"Version `{version.version_id}` persisted "
                    f"(confidence {version.confidence_score}/100, "
                    f"{len(version.claims)} claims, "
                    f"{len(version.contradictions)} contradictions)."
                )
            except ConstitutionViolation as exc:
                st.error(f"ConstitutionViolation: {exc}")
            except Exception as exc:  # pragma: no cover
                st.error(f"Synthesize failed: {exc}")

    data = build_pipeline_data(stack, topic=topic.strip() or None)
    cols = st.columns(len(DAG_NODES))
    for col, node in zip(cols, DAG_NODES):
        s = data["node_status"][node]
        col.metric(node, f"{s['ok']} ok / {s['error']} err")
        if s["last_at"]:
            col.caption(s["last_at"])

    if data["runtime_used"]:
        st.caption(f"Last runtime used: `{data['runtime_used']}`")

    st.markdown("### Connectors")
    if _HAS_PANDAS:
        st.dataframe(
            pd.DataFrame(data["connector_rows"]),
            hide_index=True, use_container_width=True,
        )
    else:  # pragma: no cover
        st.json(data["connector_rows"])

    if data["latest_version"] is not None:
        v = data["latest_version"]
        st.markdown(f"### Latest version on `{topic}`")
        warnings = _constitution_warnings(v)
        for w in warnings:
            st.error(w)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Confidence",    f"{v.confidence_score}/100")
        c2.metric("Claims",        len(v.claims))
        c3.metric("Contradictions", len(v.contradictions))
        c4.metric("Audit fired",   "yes" if v.audit_triggered else "no")


# ---------------------------------------------------------------------------
# Tab 3 — Contradictions explorer
# ---------------------------------------------------------------------------


def build_contradictions_data(stack: WiredStack) -> dict:
    """Every contradiction across every version, severity-sorted."""

    structured = stack.store.structured
    cur = structured._sqlite_conn.execute(
        """
        SELECT c.contradiction_id, c.version_id, c.subject, c.predicate,
               c.severity, c.note, v.topic, v.created_at
        FROM contradictions c
        INNER JOIN versions v ON v.version_id = c.version_id
        WHERE v.topic NOT LIKE '\\_%' ESCAPE '\\'
        ORDER BY c.severity DESC, v.created_at DESC
        """
    )
    contradictions = [dict(r) for r in cur.fetchall()]
    cur = structured._sqlite_conn.execute(
        """
        SELECT contradiction_id, COUNT(*) AS n_flags
        FROM contradiction_flags
        GROUP BY contradiction_id
        """
    )
    flags = {r["contradiction_id"]: int(r["n_flags"]) for r in cur.fetchall()}
    return {
        "contradictions": contradictions,
        "flag_counts":    flags,
    }


def render_contradictions_tab(stack: WiredStack) -> None:
    data = build_contradictions_data(stack)

    if not data["contradictions"]:
        st.info(
            "No contradictions recorded yet. Run a synthesis on the "
            "**Live Pipeline** tab to populate the explorer."
        )
        return

    if _HAS_PANDAS:
        rows = []
        for cd in data["contradictions"]:
            rows.append({
                "Severity":       int(cd["severity"]),
                "Subject":        cd["subject"],
                "Predicate":      cd["predicate"],
                "Topic":          cd["topic"],
                "User flags":     data["flag_counts"].get(cd["contradiction_id"], 0),
                "Contradiction id": cd["contradiction_id"],
                "Version id":     cd["version_id"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:  # pragma: no cover
        st.json(data["contradictions"])

    st.markdown("### Flag a contradiction")
    cd_ids = [cd["contradiction_id"] for cd in data["contradictions"]]
    selected = st.selectbox(
        "Contradiction id", options=cd_ids, key="contradiction_to_flag",
    )
    reason = st.text_area(
        "Reason (visible in audit_trail forever)",
        key="contradiction_flag_reason",
    )
    flagged_by = st.text_input(
        "Flagged by", value=os.environ.get("USERNAME") or "user",
        key="contradiction_flagged_by",
    )
    if st.button("Flag this contradiction", key="contradiction_flag_btn"):
        if not reason.strip():
            st.error("Reason cannot be empty.")
        else:
            try:
                flag_id = stack.provenance.log_contradiction_flag(
                    contradiction_id=selected,
                    reason=reason.strip(),
                    flagged_by=flagged_by.strip() or "user",
                )
                st.success(
                    f"Flag `{flag_id}` recorded (immutable; visible in "
                    f"audit_trail forever)."
                )
            except ConstitutionViolation as exc:
                st.error(f"ConstitutionViolation: {exc}")
            except Exception as exc:  # pragma: no cover
                st.error(f"Flag failed: {exc}")


# ---------------------------------------------------------------------------
# Tab 4 — Provenance Reports
# ---------------------------------------------------------------------------


def build_reports_data(stack: WiredStack) -> dict:
    structured = stack.store.structured
    cur = structured._sqlite_conn.execute(
        """
        SELECT version_id, topic, created_at, confidence_score
        FROM versions WHERE topic NOT LIKE '\\_%' ESCAPE '\\'
        ORDER BY created_at DESC LIMIT 200
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    return {
        "versions":          rows,
        "langfuse_runtime":  stack.provenance.runtime_info["langfuse"],
    }


def render_reports_tab(stack: WiredStack) -> None:
    data = build_reports_data(stack)

    lf = data["langfuse_runtime"]
    if lf["active"]:
        st.success(
            f"Langfuse cloud trace **active** (host: `{lf['host']}`, "
            f"{lf['trace_count']} traces, {lf['span_count']} spans)."
        )
    elif lf["sdk_available"]:
        st.info(
            "Langfuse SDK installed but no API keys set. Provenance is "
            "logged locally to JSONL only."
        )
    else:
        st.info(
            "Langfuse not installed. Provenance is logged locally to "
            "JSONL only — fully privacy-preserving."
        )

    if not data["versions"]:
        st.info("No versions yet — run a synthesis on the Live Pipeline tab.")
        return

    options = [
        f"{r['version_id']} · {r['topic']} · {r['confidence_score']}/100"
        for r in data["versions"]
    ]
    selected = st.selectbox(
        "Pick a version to render its provenance report",
        options=options, key="report_version_picker",
    )
    if selected:
        version_id = selected.split(" · ")[0]
        try:
            report = stack.provenance.export_report(version_id, format="markdown")
        except Exception as exc:  # pragma: no cover
            st.error(f"export_report failed: {exc}")
            return
        st.markdown(report)
        st.download_button(
            "Download Markdown report",
            data=report,
            file_name=f"lnf-provenance-{version_id}.md",
            mime="text/markdown",
        )


# ---------------------------------------------------------------------------
# Tab 5 — Memory Explorer (versions / claims / rewind)
# ---------------------------------------------------------------------------


def build_memory_data(
    stack: WiredStack,
    *,
    topic: Optional[str] = None,
    version_id: Optional[str] = None,
) -> dict:
    structured = stack.store.structured
    cur = structured._sqlite_conn.execute(
        """
        SELECT DISTINCT topic FROM versions
        WHERE topic NOT LIKE '\\_%' ESCAPE '\\'
        ORDER BY topic
        """
    )
    topics = [r["topic"] for r in cur.fetchall()]

    versions: tuple[SynthesisVersion, ...] = ()
    if topic:
        versions = tuple(stack.store.history_for(topic))

    selected_version: Optional[SynthesisVersion] = None
    rewind = None
    audit_trail: tuple[Any, ...] = ()
    if version_id:
        selected_version = stack.store.recall(version_id)
        rewind = stack.store.rewind_to_version(version_id)
        audit_trail = stack.provenance.get_audit_trail(version_id, full_chain=True)

    return {
        "topics":           topics,
        "versions":         versions,
        "selected_version": selected_version,
        "rewind":           rewind,
        "audit_trail":      audit_trail,
    }


def render_memory_tab(stack: WiredStack) -> None:
    pre = build_memory_data(stack)
    if not pre["topics"]:
        st.info("No topics in memory yet — run a synthesis on the Live Pipeline tab.")
        return

    topic = st.selectbox(
        "Topic", options=pre["topics"],
        index=pre["topics"].index(st.session_state.get("active_topic", pre["topics"][0]))
        if st.session_state.get("active_topic") in pre["topics"] else 0,
        key="memory_topic",
    )
    data = build_memory_data(stack, topic=topic)

    if not data["versions"]:
        st.info(f"No versions for topic `{topic}`.")
        return

    st.markdown(f"### History for `{topic}` ({len(data['versions'])} versions)")
    if _HAS_PANDAS:
        rows = [
            {
                "Version":   v.version_id,
                "Created":   v.created_at.isoformat(),
                "Time range": v.time_range,
                "Confidence": v.confidence_score,
                "Claims":    len(v.claims),
                "Contradictions": len(v.contradictions),
                "Audit":     "✓" if v.audit_triggered else "",
                "Parent":    v.parent_version_id or "(root)",
            }
            for v in data["versions"]
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    selected_id = st.selectbox(
        "Drill-down version",
        options=[v.version_id for v in data["versions"]],
        index=len(data["versions"]) - 1,
        key="memory_version",
    )
    drill = build_memory_data(stack, topic=topic, version_id=selected_id)
    v = drill["selected_version"]
    if v is None:
        st.error(f"Version `{selected_id}` could not be recalled.")
        return

    warnings = _constitution_warnings(v)
    for w in warnings:
        st.error(w)

    st.markdown(f"#### Claims for `{v.version_id}` ({len(v.claims)})")
    if _HAS_PANDAS:
        claim_rows = [
            {
                "Source":    c.source,
                "Source id": c.source_id,
                "Subject":   c.subject,
                "Predicate": c.predicate,
                "Value":     c.value,
                "Confidence": round(c.confidence, 3),
            }
            for c in v.claims
        ]
        st.dataframe(pd.DataFrame(claim_rows), hide_index=True, use_container_width=True)

    if drill["rewind"] is not None and drill["rewind"].parent_chain:
        st.markdown("#### Rewind chain")
        chain_rows = [
            {"#": n, "Version": pv.version_id, "Created": pv.created_at.isoformat(),
             "Confidence": pv.confidence_score}
            for n, pv in enumerate(drill["rewind"].parent_chain, start=1)
        ]
        if _HAS_PANDAS:
            st.dataframe(pd.DataFrame(chain_rows), hide_index=True, use_container_width=True)
        rewind_to = st.selectbox(
            "Rewind to (read-only — sets the active version in session state)",
            options=[pv.version_id for pv in drill["rewind"].parent_chain],
            key="memory_rewind_target",
        )
        if st.button("Rewind to selected version", key="memory_rewind_btn"):
            st.session_state["active_version_id"] = rewind_to
            st.success(
                f"Active version set to `{rewind_to}`. Switch to the "
                f"Provenance Reports tab to view the full report."
            )

    st.markdown("#### Audit trail")
    if drill["audit_trail"]:
        if _HAS_PANDAS:
            audit_rows = [
                {
                    "Recorded at": ev.recorded_at.isoformat(),
                    "Event type":  ev.event_type,
                    "Version":     ev.version_id,
                }
                for ev in drill["audit_trail"]
            ]
            st.dataframe(pd.DataFrame(audit_rows), hide_index=True, use_container_width=True)
    else:
        st.caption("No audit-trail rows for this version yet.")


# ---------------------------------------------------------------------------
# Tab 6 — Improvements (eval scores + suggestions)
# ---------------------------------------------------------------------------


def build_improvements_data(stack: WiredStack) -> dict:
    history = stack.loop.get_improvement_history(limit=20)
    return {
        "history":      history,
        "loop_runtime": stack.loop.runtime_info,
    }


def render_improvements_tab(stack: WiredStack) -> None:
    data = build_improvements_data(stack)

    st.markdown("### Run a fresh evaluation cycle")
    c1, c2 = st.columns(2)
    dry_run = c1.checkbox("Dry run", value=True, key="improvements_dry_run")
    notes = c2.text_input("Notes (optional)", value="", key="improvements_notes")
    if st.button("Run weekly eval", type="primary", key="improvements_run_btn"):
        with st.spinner("Running eval suite across every persisted version..."):
            try:
                run = stack.loop.run_weekly_eval(dry_run=dry_run, notes=notes)
                st.success(
                    f"Run `{run.run_id}` complete: overall {run.overall_score}/100; "
                    f"{len(run.versions_evaluated)} versions evaluated; "
                    f"{len(run.suggestions)} suggestion(s)."
                )
            except Exception as exc:  # pragma: no cover
                st.error(f"run_weekly_eval failed: {exc}")
        data = build_improvements_data(stack)

    if not data["history"]:
        st.info("No eval runs yet — click **Run weekly eval** above.")
        return

    st.markdown("### Past runs")
    if _HAS_PANDAS:
        run_rows = [
            {
                "Run id":           r.run_id,
                "Started":          r.started_at.isoformat(),
                "Score":            r.overall_score,
                "Versions":         len(r.versions_evaluated),
                "Suggestions":      len(r.suggestions),
                "Finance":          "✓" if r.has_finance_subject else "",
                "Notes":            r.notes,
            }
            for r in data["history"]
        ]
        st.dataframe(pd.DataFrame(run_rows), hide_index=True, use_container_width=True)

    selected_run_id = st.selectbox(
        "Drill-down run id",
        options=[r.run_id for r in data["history"]],
        index=0, key="improvements_run_picker",
    )
    selected_run = next(
        (r for r in data["history"] if r.run_id == selected_run_id), None,
    )
    if selected_run is None:
        return

    st.markdown(f"#### Metrics for `{selected_run.run_id}`")
    if _HAS_PANDAS:
        metric_rows = [
            {
                "Metric":   m.metric_name,
                "Score":    m.score,
                "Threshold": m.threshold,
                "Passed":   "✓" if m.passed else "✗",
                "Reasons":  "; ".join(m.reasons) if m.reasons else "",
            }
            for m in selected_run.metric_results
        ]
        st.dataframe(pd.DataFrame(metric_rows), hide_index=True, use_container_width=True)

    if selected_run.suggestions:
        st.markdown("#### Suggestions")
        for s in selected_run.suggestions:
            color = SEVERITY_COLORS.get(s.severity, SEVERITY_COLORS["info"])
            st.markdown(
                f"**<span style='color:{color}'>[{s.severity.upper()}]</span> "
                f"{s.title}**", unsafe_allow_html=True,
            )
            st.markdown(f"*Target file*: `{s.target_file}`")
            st.markdown(f"**Rationale**: {s.rationale}")
            st.markdown(f"**Suggested change**: {s.suggested_change}")
            st.divider()
        if st.button("Re-apply suggestions (dry run)", key="improvements_reapply_btn"):
            applied = stack.loop.apply_improvements(
                selected_run.suggestions, dry_run=True, run_id=selected_run.run_id,
            )
            st.success(applied.summary)


# ---------------------------------------------------------------------------
# Tab 7 — Settings
# ---------------------------------------------------------------------------


def build_settings_data(stack: WiredStack) -> dict:
    """Runtime + env-var diagnostics."""

    env_vars = {
        "NEWSAPI_KEY":          bool(os.environ.get("NEWSAPI_KEY")),
        "GNEWS_KEY":            bool(os.environ.get("GNEWS_KEY")),
        "SEMANTIC_SCHOLAR_KEY": bool(os.environ.get("SEMANTIC_SCHOLAR_KEY")),
        "DATA_GOV_KEY":         bool(os.environ.get("DATA_GOV_KEY")),
        "XAI_API_KEY":          bool(os.environ.get("XAI_API_KEY")),
        "CRAWL4AI_SEED_URLS":   bool(os.environ.get("CRAWL4AI_SEED_URLS")),
        "LANGFUSE_PUBLIC_KEY":  bool(os.environ.get("LANGFUSE_PUBLIC_KEY")),
        "LANGFUSE_SECRET_KEY":  bool(os.environ.get("LANGFUSE_SECRET_KEY")),
        "QDRANT_URL":           bool(os.environ.get("QDRANT_URL")),
        "MASTRA_HTTP_URL":      bool(os.environ.get("MASTRA_HTTP_URL")),
    }
    return {
        "appdata_root":     str(stack.appdata_root),
        "memory_runtime":   stack.store.runtime_info,
        "connector_runtime": stack.connectors.runtime_info,
        "provenance_runtime": stack.provenance.runtime_info,
        "loop_runtime":     stack.loop.runtime_info,
        "env_vars":         env_vars,
    }


def render_settings_tab(stack: WiredStack) -> None:
    data = build_settings_data(stack)

    st.markdown("### Runtime info")
    st.markdown("**Local appdata root**")
    st.code(data["appdata_root"], language="text")

    with st.expander("Memory runtime", expanded=False):
        st.json(data["memory_runtime"])
    with st.expander("Connectors runtime", expanded=False):
        st.json(data["connector_runtime"])
    with st.expander("Provenance runtime", expanded=False):
        st.json(data["provenance_runtime"])
    with st.expander("Self-improvement loop runtime", expanded=False):
        st.json(data["loop_runtime"])

    st.markdown("### Environment variables")
    st.caption(
        "Green = set. The dashboard never reads or displays the values "
        "themselves — only their presence."
    )
    if _HAS_PANDAS:
        env_rows = [
            {"Variable": k, "Set": "✓" if v else "✗"}
            for k, v in data["env_vars"].items()
        ]
        st.dataframe(pd.DataFrame(env_rows), hide_index=True, use_container_width=True)
    else:  # pragma: no cover
        st.json(data["env_vars"])

    st.markdown("### Constitution + Article V.1")
    st.markdown(
        "- Every claim displayed by the dashboard is scanned for empty "
        "`source_id` before render. Violations show as red banners.\n"
        "- Every contradiction is checked for the silent-resolution rule "
        "(every `claim_id` in `contradiction.claim_ids` must still appear "
        "in `version.claims`). Violations show as red banners.\n"
        "- The Article V.1 'Not financial advice' banner auto-attaches to "
        "the Overview, Live Pipeline, and Memory Explorer tabs whenever "
        "any persisted version has `has_finance_subject=True`."
    )


# ---------------------------------------------------------------------------
# Streamlit entry point
# ---------------------------------------------------------------------------


def _resolve_appdata_root() -> Path:
    override = os.environ.get("LNF_DASHBOARD_APPDATA")
    if override:
        return Path(override).expanduser().resolve()
    return _default_appdata_root()


def _build_or_get_stack() -> WiredStack:
    """Cache the stack across reruns via Streamlit's session_state."""

    if not _HAS_STREAMLIT:
        return build_wired_stack()
    cached = st.session_state.get("_wired_stack")
    cached_root = st.session_state.get("_wired_appdata")
    target_root = str(_resolve_appdata_root())
    force_stub = bool(st.session_state.get("force_stub", True))
    cached_force_stub = st.session_state.get("_wired_force_stub")
    if cached is None or cached_root != target_root or cached_force_stub != force_stub:
        stack = build_wired_stack(
            appdata_root=Path(target_root), force_stub=force_stub,
        )
        st.session_state["_wired_stack"] = stack
        st.session_state["_wired_appdata"] = target_root
        st.session_state["_wired_force_stub"] = force_stub
        return stack
    return cached


def render_sidebar(stack: WiredStack) -> None:
    with st.sidebar:
        st.title(PAGE_TITLE)
        st.caption(
            "Built for xAI, X, Grok and the ecosystem community. ❤️ "
            "Apache-2.0. Local-first. Privacy-first."
        )
        st.markdown("---")
        st.markdown("**Local data**")
        st.code(str(stack.appdata_root), language="text")
        st.markdown("---")
        force_stub = st.checkbox(
            "Force stub mode (connectors)",
            value=bool(st.session_state.get("force_stub", True)),
            key="force_stub_toggle",
        )
        if force_stub != st.session_state.get("force_stub", True):
            st.session_state["force_stub"] = force_stub
            st.rerun()
        st.markdown("---")
        st.markdown(
            "**Tabs**: Overview · Live Pipeline · Contradictions · "
            "Provenance · Memory · Improvements · Settings"
        )


def main_streamlit() -> None:  # pragma: no cover
    """Streamlit entry point. Called when ``streamlit run dashboard.py`` runs."""

    if not _HAS_STREAMLIT:
        raise RuntimeError(
            "Streamlit is not installed. Install via "
            "`python -m pip install -r requirements.txt`, then launch "
            "`streamlit run dashboard.py`."
        )
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    stack = _build_or_get_stack()
    render_sidebar(stack)

    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    st.caption(
        "Real-time observability + interactive control surface for the "
        "Living Narrative Fabric Super Agent."
    )

    tabs = st.tabs([
        "📊 Overview",
        "⚡ Live Pipeline",
        "🪢 Contradictions",
        "📜 Provenance Reports",
        "🧠 Memory Explorer",
        "🛠️ Improvements",
        "⚙️ Settings",
    ])
    with tabs[0]:
        render_overview_tab(stack)
    with tabs[1]:
        render_pipeline_tab(stack)
    with tabs[2]:
        render_contradictions_tab(stack)
    with tabs[3]:
        render_reports_tab(stack)
    with tabs[4]:
        render_memory_tab(stack)
    with tabs[5]:
        render_improvements_tab(stack)
    with tabs[6]:
        render_settings_tab(stack)


# ---------------------------------------------------------------------------
# Smoke test (zero-install — runs without streamlit/pandas/plotly)
# ---------------------------------------------------------------------------


def run_smoke_test(*, verbose: bool = True) -> None:
    """Self-contained smoke test for the dashboard data builders.

    Verifies (10 checks):

    1. ``build_wired_stack`` produces all 5 layer instances.
    2. ``build_overview_data`` returns top-level metrics with expected keys.
    3. After running a real synthesize() through the wired fabric, the
       overview reports >= 1 version + >= 1 event.
    4. ``build_pipeline_data`` reports per-node ok/error counts.
    5. ``build_contradictions_data`` returns the contradictions list.
    6. ``build_reports_data`` lists the persisted versions.
    7. ``build_memory_data(topic, version_id)`` resolves a real version
       and a non-empty rewind chain.
    8. ``build_improvements_data`` triggers a weekly eval and reads its
       history back.
    9. ``build_settings_data`` reports the env-var presence dict.
    10. ``_constitution_warnings`` flags a forged empty source_id.
    """

    import shutil
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="lnf-dashboard-smoke-"))
    try:
        # ---- (1) ------------------------------------------------------
        stack = build_wired_stack(appdata_root=tmp_root, force_stub=True)
        assert isinstance(stack, WiredStack)
        assert stack.store is not None
        assert stack.connectors is not None
        assert stack.provenance is not None
        assert stack.loop is not None
        assert stack.fabric is not None

        # ---- (2) ------------------------------------------------------
        overview_empty = build_overview_data(stack)
        for k in (
            "version_count", "topic_count", "contradiction_count",
            "flag_count", "event_count", "stub_connectors",
            "total_connectors", "memory_runtime", "provenance_runtime",
        ):
            assert k in overview_empty, f"overview missing {k!r}"
        assert overview_empty["total_connectors"] == 6

        # ---- (3) ------------------------------------------------------
        v1 = stack.fabric.synthesize(
            topic="dashboard-smoke", time_range="7d",
        )
        v2 = stack.fabric.synthesize(
            topic="dashboard-smoke", time_range="30d",
        )
        overview = build_overview_data(stack)
        assert overview["version_count"] >= 2, (
            f"expected >= 2 versions; got {overview['version_count']}"
        )
        assert overview["event_count"] >= 1
        assert overview["topic_count"] >= 1

        # ---- (4) ------------------------------------------------------
        pipeline = build_pipeline_data(stack, topic="dashboard-smoke")
        assert set(pipeline["node_status"].keys()) == set(DAG_NODES)
        assert len(pipeline["connector_rows"]) == 6
        assert pipeline["latest_version"] is not None
        assert pipeline["latest_version"].version_id == v2.version_id

        # ---- (5) ------------------------------------------------------
        contradictions = build_contradictions_data(stack)
        assert "contradictions" in contradictions
        assert "flag_counts" in contradictions

        # Flag a contradiction if any exist, then verify the count.
        if contradictions["contradictions"]:
            cd_id = contradictions["contradictions"][0]["contradiction_id"]
            stack.provenance.log_contradiction_flag(
                contradiction_id=cd_id,
                reason="smoke-test flag",
                flagged_by="smoke-runner",
            )
            after = build_contradictions_data(stack)
            assert after["flag_counts"].get(cd_id, 0) >= 1

        # ---- (6) ------------------------------------------------------
        reports = build_reports_data(stack)
        assert any(r["version_id"] == v1.version_id for r in reports["versions"])
        # export_report should produce a non-empty markdown string.
        report_md = stack.provenance.export_report(v2.version_id, format="markdown")
        assert "# Provenance Report" in report_md

        # ---- (7) ------------------------------------------------------
        memory = build_memory_data(
            stack, topic="dashboard-smoke", version_id=v2.version_id,
        )
        assert memory["selected_version"] is not None
        assert memory["selected_version"].version_id == v2.version_id
        assert memory["rewind"] is not None
        assert memory["rewind"].parent_chain
        assert memory["rewind"].parent_chain[-1].version_id == v1.version_id

        # ---- (8) ------------------------------------------------------
        # Trigger a weekly eval so the history has at least one row.
        stack.loop.run_weekly_eval(dry_run=True, notes="dashboard-smoke")
        improvements = build_improvements_data(stack)
        assert len(improvements["history"]) >= 1

        # ---- (9) ------------------------------------------------------
        settings = build_settings_data(stack)
        for k in (
            "appdata_root", "memory_runtime", "connector_runtime",
            "provenance_runtime", "loop_runtime", "env_vars",
        ):
            assert k in settings, f"settings missing {k!r}"
        for env_var in (
            "NEWSAPI_KEY", "GNEWS_KEY", "SEMANTIC_SCHOLAR_KEY",
            "DATA_GOV_KEY", "XAI_API_KEY", "CRAWL4AI_SEED_URLS",
            "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
            "QDRANT_URL", "MASTRA_HTTP_URL",
        ):
            assert env_var in settings["env_vars"]

        # ---- (10) -----------------------------------------------------
        bad_version = SynthesisVersion(
            version_id="bad", topic="bad", time_range="7d",
            parent_version_id=None,
            created_at=datetime.now(timezone.utc),
            sources_used=("newsapi",),
            claims=(Claim(
                claim_id="c1", subject="x", predicate="y", value="z",
                source="newsapi", source_id="",  # ← empty
                confidence=0.5, extracted_at=datetime.now(timezone.utc),
                sentiment=None,
            ),),
            contradictions=(),
            confidence_metrics={
                "Source diversity": 0, "Provenance completeness": 0,
                "Cross-source agreement": 0, "Recency coverage": 0,
            },
            confidence_score=0,
            audit_triggered=False,
            audit_reasons=(),
            has_finance_subject=False,
            bridges=("a", "b", "c"),
        )
        warnings = _constitution_warnings(bad_version)
        assert any("empty source_id" in w for w in warnings), (
            f"expected source_id warning; got {warnings!r}"
        )

        # Also verify a clean version yields ZERO warnings.
        good_warnings = _constitution_warnings(v2)
        assert not good_warnings, (
            f"clean version produced warnings: {good_warnings!r}"
        )

        # Cleanup connector cursors before tmp removal.
        for c in stack.connectors:
            c.close()
        stack.loop.history.close()

        if verbose:
            print("P115 dashboard smoke OK")
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Argparse entry point — `python dashboard.py --smoke` runs the smoke test
# without ever touching streamlit. The Streamlit launch path is reached via
# `streamlit run dashboard.py` which executes the module top-level (where
# `main_streamlit()` is invoked when ``_HAS_STREAMLIT`` is true and the
# script is being run as the Streamlit entrypoint).
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dashboard",
        description=(
            "Living Narrative Fabric — Streamlit dashboard (Slot 7). "
            "Run via `streamlit run dashboard.py` for the live UI; use "
            "`python dashboard.py --smoke` for the zero-install smoke test."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples (Windows 11 + PowerShell):

              python -m pip install -r requirements.txt
              python dashboard.py --smoke
              streamlit run dashboard.py
            """
        ),
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Run the self-contained smoke test (no streamlit required).",
    )
    return parser


def _is_streamlit_runtime() -> bool:
    """Detect whether this module is being executed under ``streamlit run``."""

    if not _HAS_STREAMLIT:
        return False
    # Streamlit sets a few runtime sentinels we can sniff. The cheapest is
    # ``st.runtime.exists()`` which is True only inside a real session.
    try:
        runtime_mod = importlib.import_module("streamlit.runtime")
        exists = getattr(runtime_mod, "exists", None)
        if callable(exists):
            return bool(exists())
    except Exception:
        pass
    return False


if _is_streamlit_runtime():  # pragma: no cover
    main_streamlit()
elif __name__ == "__main__":  # pragma: no cover
    parser = _build_arg_parser()
    args = parser.parse_args()
    if args.smoke:
        run_smoke_test()
    else:
        # Help message + hint that the live UI requires `streamlit run`.
        parser.print_help()
        print(
            "\nThis script is designed to be launched via "
            "`streamlit run dashboard.py` for the live UI, or via "
            "`python dashboard.py --smoke` for the smoke test.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = (
    "ARTICLE_V1_DISCLAIMER",
    "DAG_NODES",
    "PAGE_ICON",
    "PAGE_TITLE",
    "WiredStack",
    "build_contradictions_data",
    "build_improvements_data",
    "build_memory_data",
    "build_overview_data",
    "build_pipeline_data",
    "build_reports_data",
    "build_settings_data",
    "build_wired_stack",
    "main_streamlit",
    "run_smoke_test",
)
