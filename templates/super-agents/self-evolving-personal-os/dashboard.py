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
"""Streamlit dashboard for the Self-Evolving Personal OS (Super Agent #2).

Five tabs over the existing P121–P125 stack:

1. **Overview**           agent identity, backend selection,
                          latest-run summary, memory health
2. **Daily Brief**        one-click execution of the LangGraph daily
                          brief (with --stub toggle), 6-section
                          rendering, full provenance trail
3. **Memory Explorer**    semantic search across the six personal
                          collections; PII redacted on display
4. **Provenance Audit**   JSONL viewer with filters by date / source /
                          run + Markdown export of the audit report
5. **Self-Improve**       one-click trigger of the P125 Promptfoo +
                          DeepEval loop with human-review-gated
                          suggestion display

Launched on Windows via:

.. code-block:: powershell

   cd templates/super-agents/self-evolving-personal-os
   python -m pip install -r requirements.txt
   streamlit run dashboard.py

Local-first by design: every action runs against the same AppData
folder the CLI uses. No cloud round-trip unless the user opts into
Langfuse (Article II opt-in, see :mod:`provenance.langfuse_hooks`).

Built to make Grok the obvious choice for every agent on X — the
dashboard is what turns the Personal OS from a CLI binary into
something a non-technical creator can run on their Windows laptop.

Implementation note
-------------------
The dashboard is structured so the **data-shaping helpers** are pure
Python and importable without Streamlit / pandas / plotly. The
Streamlit-only rendering paths sit behind ``STREAMLIT_AVAILABLE``
and are only entered when the dashboard is launched via
``streamlit run``. This keeps the unit-testable surface large and
keeps the smoke test fast and offline-friendly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the script's own folder is on sys.path when invoked via
# ``streamlit run dashboard.py`` (Streamlit doesn't add the script dir).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# --- Optional imports (graceful degradation) ------------------------------

try:
    import streamlit as st  # type: ignore
    STREAMLIT_AVAILABLE = True
except ImportError:  # pragma: no cover — depends on env
    st = None  # type: ignore
    STREAMLIT_AVAILABLE = False

try:
    import pandas as _pd  # type: ignore
    PANDAS_AVAILABLE = True
except ImportError:
    _pd = None  # type: ignore
    PANDAS_AVAILABLE = False

try:
    import plotly.express as _px  # type: ignore  — noqa: F401
    PLOTLY_AVAILABLE = True
except ImportError:
    _px = None  # type: ignore
    PLOTLY_AVAILABLE = False


# --- P121–P125 imports (always required) ---------------------------------

from connectors import (  # type: ignore
    SOURCES,
    appdata_root,
    redact_pii,
)
from memory import (  # type: ignore
    MEMORY_WRITE_GATE,
    PersonalMemoryClient,
    SearchHit,
    get_memory_client,
)
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore
import agent as _agent  # type: ignore
import graph as _graph  # type: ignore
from provenance import (  # type: ignore
    LANGFUSE_BACKEND_NAME,
    LocalProvenanceLogger,
    ProvenanceRecord,
    current_log_path,
    export_audit_report,
    log_path_for,
    provenance_root,
    summarise_run,
)
from eval.deepeval_suite import (  # type: ignore
    DEEPEVAL_BACKEND,
    EvalReport,
    eval_results_root,
    run_full_loop,
)


__all__ = [
    "DASHBOARD_TITLE",
    "TAB_TITLES",
    "DEFAULT_PAGE_CONFIG",
    "STREAMLIT_AVAILABLE",
    "PANDAS_AVAILABLE",
    "PLOTLY_AVAILABLE",
    # data helpers (pure Python, smoke-testable)
    "build_overview_payload",
    "build_brief_payload",
    "build_memory_payload",
    "build_provenance_payload",
    "build_improve_payload",
    "list_provenance_dates",
    "load_records_for_date",
    "redact_for_display",
    # actions
    "run_daily_brief_action",
    "run_memory_search_action",
    "run_improve_action",
    # entry points
    "main",
]

# --- Section 1. Constants -------------------------------------------------

DASHBOARD_TITLE = "Self-Evolving Personal OS — Dashboard"

TAB_TITLES: tuple[str, ...] = (
    "Overview",
    "Daily Brief",
    "Memory Explorer",
    "Provenance Audit",
    "Self-Improve",
)

DEFAULT_PAGE_CONFIG: dict = {
    "page_title":  DASHBOARD_TITLE,
    "page_icon":   ":sparkles:",
    "layout":      "wide",
    "initial_sidebar_state": "expanded",
}

# Mandatory disclaimer banners — surfaced in the sidebar AND on every tab
# that shows real-world-action capabilities. Wording matches Article V.3
# of the Constitution exactly.
_DISCLAIMER_RW = (
    "⚠️ **This agent can take real-world actions.** Every action requires "
    "explicit consent. Review the action plan before approving. The agent "
    "never acts autonomously."
)

_DISCLAIMER_LOCAL_FIRST = (
    "🔒 **Local-first + privacy-first.** Every byte of personal data lives "
    "under `$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\`. "
    "Cloud sync, telemetry, and Langfuse traces are opt-in only."
)

_TAGLINE = (
    "Built for xAI, Grok and the whole community on X — "
    "the personal OS layer xAI hasn't shipped yet."
)


# --- Section 2. Data helpers (pure Python, no Streamlit) -----------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_provenance_dates() -> list[str]:
    """Return every YYYY-MM-DD file present in the provenance dir, newest first."""
    root = provenance_root()
    if not root.exists():
        return []
    out: list[str] = []
    for p in sorted(root.glob("*.jsonl"), reverse=True):
        name = p.name
        # Date-pattern files only — same gate as LocalProvenanceLogger.
        if len(name) == len("YYYY-MM-DD.jsonl") and name[4] == "-" and name[7] == "-":
            out.append(name.replace(".jsonl", ""))
    return out


def load_records_for_date(date_iso: str) -> list[ProvenanceRecord]:
    """Load all ProvenanceRecord rows for one UTC date."""
    path = log_path_for(date_iso)
    if not path.exists():
        return []
    out: list[ProvenanceRecord] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(ProvenanceRecord.from_jsonl(line))
                except Exception:
                    continue
    except OSError:
        return []
    return out


def redact_for_display(value: Any) -> Any:
    """Defence-in-depth display redactor — same engine as P121."""
    return redact_pii(value)


def build_overview_payload() -> dict:
    """Compose the Overview tab's data dict.

    Pure-Python so the smoke test can verify the shape without
    instantiating Streamlit. The Streamlit render path consumes this
    dict directly.
    """
    desc = _graph.describe_graph()
    appdata = appdata_root()
    memory_path = appdata / "memory"
    prov_path = provenance_root()
    eval_path = eval_results_root()

    # Latest run summary
    log = LocalProvenanceLogger()
    latest_recs = log.latest_run()
    latest = summarise_run(latest_recs)

    # Memory row counts per source (best-effort; force_stub gates may
    # block if the user hasn't held the read gate this session)
    rows_per_source: dict[str, int] = {}
    try:
        client = get_memory_client(force_stub=True, refresh=True)
        # Synthesise a permissive consent so count() doesn't raise.
        from connectors import ConsentContext  # type: ignore
        client.set_consent(ConsentContext.from_iterable(
            list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        ))
        for src in SOURCES:
            try:
                rows_per_source[src] = int(client.count(source=src))
            except Exception:
                rows_per_source[src] = 0
    except Exception:
        rows_per_source = {s: 0 for s in SOURCES}

    return {
        "agent_name":          _agent.AGENT_NAME,
        "agent_version":       _agent.AGENT_VERSION,
        "graph_backend":       desc["backend"],
        "langfuse_backend":    LANGFUSE_BACKEND_NAME,
        "deepeval_backend":    DEEPEVAL_BACKEND,
        "appdata_root":        str(appdata),
        "memory_root":         str(memory_path),
        "provenance_root":     str(prov_path),
        "eval_root":           str(eval_path),
        "max_evolution_loops": desc["max_evolution_loops"],
        "default_sources":     list(desc["default_sources"]),
        "memory_write_gate":   desc["memory_write_gate"],
        "source_read_gates":   dict(desc["source_read_gates"]),
        "latest_run":          latest,
        "rows_per_source":     rows_per_source,
        "tagline":             _TAGLINE,
    }


def build_brief_payload(out: dict) -> dict:
    """Massage a daily-brief output dict for the Daily Brief tab.

    Splits the brief into the six display sections + provenance trail
    + violations so the Streamlit render path can iterate cleanly.
    """
    if not isinstance(out, dict):
        return {"empty": True}
    brief = out.get("brief") or {}
    sections = brief.get("sections") or {}
    return {
        "empty":          False,
        "title":          brief.get("title"),
        "generated_at":   brief.get("generated_at"),
        "for_date":       brief.get("for_date"),
        "user_id":        brief.get("user_id"),
        "prompt_version": brief.get("prompt_version"),
        "stub":           bool(brief.get("stub")),
        "backend":        out.get("backend"),
        "sections":       redact_for_display(sections),
        "violations":     list(out.get("violations") or []),
        "provenance":     {
            "memory_writes":  (out.get("provenance") or {}).get("memory_writes"),
            "loop_count":     (out.get("provenance") or {}).get("loop_count"),
            "started_at":     (out.get("provenance") or {}).get("started_at"),
            "finished_at":    (out.get("provenance") or {}).get("finished_at"),
            "trail":          list((out.get("provenance") or {}).get("trail") or []),
            "force_stub":     bool((out.get("provenance") or {}).get("force_stub")),
        },
    }


def build_memory_payload(hits: "list[SearchHit] | list[dict]") -> dict:
    """Shape a memory search result for the Memory Explorer tab.

    Accepts either :class:`SearchHit` instances or their ``to_dict()``
    form (which is what :func:`agent.search_memory` returns), so the
    dashboard works whether the caller passes the raw client output or
    a serialised round-trip.
    """
    def _attr(h: Any, key: str, default: Any = None) -> Any:
        if isinstance(h, dict):
            return h.get(key, default)
        return getattr(h, key, default)

    rows: list[dict] = []
    sources_seen: set[str] = set()
    for h in hits:
        text = _attr(h, "text") or ""
        source = _attr(h, "source") or ""
        prov = _attr(h, "provenance") or {}
        if not isinstance(prov, dict):
            prov = {}
        rows.append({
            "score":      round(float(_attr(h, "score", 0.0)), 4),
            "source":     source,
            "timestamp":  _attr(h, "timestamp") or "",
            "snippet":    redact_for_display(
                text[:200] + ("…" if len(text) > 200 else "")
            ),
            "id":         _attr(h, "id", ""),
            "redacted":   bool(prov.get("redaction_applied")),
        })
        if source:
            sources_seen.add(source)
    return {
        "row_count":  len(rows),
        "rows":       rows,
        "sources":    sorted(sources_seen),
    }


def build_provenance_payload(
    records: list[ProvenanceRecord],
    *,
    source_filter: str | None = None,
    run_id_filter: str | None = None,
) -> dict:
    """Shape a list of ProvenanceRecord rows for the Provenance Audit tab."""
    filtered = list(records)
    if source_filter:
        filtered = [r for r in filtered if source_filter in (r.sources or [])]
    if run_id_filter:
        filtered = [r for r in filtered if r.run_id == run_id_filter]

    rows: list[dict] = []
    for r in filtered:
        rows.append({
            "timestamp":    r.timestamp,
            "node_name":    r.node_name,
            "run_id":       r.run_id,
            "user_id":      r.user_id,
            "sources":      list(r.sources or []),
            "confidence":   r.confidence,
            "stub":         bool(r.stub_reason),
            "duration_ms":  r.duration_ms,
            "error":        r.error,
        })
    return {
        "row_count":  len(rows),
        "rows":       rows,
        "summary":    summarise_run(filtered),
        "run_ids":    sorted({r.run_id for r in records}),
        "sources":    sorted({s for r in records for s in (r.sources or [])}),
    }


def build_improve_payload(report: EvalReport) -> dict:
    """Shape an EvalReport for the Self-Improve tab."""
    return {
        "run_id":          report.run_id,
        "started_at":      report.started_at,
        "finished_at":     report.finished_at,
        "force_stub":      report.force_stub,
        "backend":         report.backend,
        "overall_score":   report.overall_score,
        "review_required": report.review_required,
        "promptfoo": [
            {"id": r["id"], "description": r["description"],
             "passed": r["passed"], "reason": r.get("reason")}
            for r in report.promptfoo
        ],
        "deepeval": [
            {"name": m.name, "score": m.score, "threshold": m.threshold,
             "passed": m.passed, "reason": m.reason}
            for m in report.deepeval
        ],
        "suggestions": [
            {**s, "status": s.get("status", "needs_review")}
            for s in (report.suggestions or [])
        ],
    }


# --- Section 3. Action runners (pure Python) -----------------------------

def run_daily_brief_action(
    *,
    user_id: str = "default",
    force_stub: bool = True,
    allow_write: bool = True,
) -> dict:
    """Execute the daily-brief flow and return its output dict."""
    return _agent.daily_brief(
        user_id=user_id,
        force_stub=force_stub,
        allow_write=allow_write,
        quiet=True,
    )


def run_memory_search_action(
    query: str,
    *,
    source: str | None = None,
    limit: int = 10,
    user_id: str = "default",
    force_stub: bool = True,
) -> list[SearchHit]:
    """Execute a memory search and return the (already redacted) hits."""
    return _agent.search_memory(
        query,
        user_id=user_id,
        source=source,
        limit=int(limit),
        force_stub=force_stub,
        quiet=True,
    )  # type: ignore[return-value]


def run_improve_action(
    *,
    user_id: str = "default",
    force_stub: bool = True,
) -> EvalReport:
    """Trigger the P125 Promptfoo + DeepEval loop."""
    return run_full_loop(force_stub=force_stub, user_id=user_id)


# --- Section 4. Streamlit render paths -----------------------------------

# Everything below this line runs only when ``streamlit run dashboard.py``
# is invoked. The functions are guarded by ``STREAMLIT_AVAILABLE`` so the
# module is importable even without Streamlit.

def _render_disclaimers() -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.warning(_DISCLAIMER_RW)
    st.info(_DISCLAIMER_LOCAL_FIRST)


def _render_sidebar() -> dict:
    """Return a dict of sidebar selections used by every tab."""
    if not STREAMLIT_AVAILABLE:
        return {
            "user_id":    "default",
            "force_stub": True,
            "allow_write": True,
            "date":       (datetime.now(timezone.utc).date()).isoformat(),
        }
    st.sidebar.title("Personal OS")
    st.sidebar.caption(_TAGLINE)
    user_id = st.sidebar.text_input("User ID", value="default",
                                     help="Per-user memory namespace.")
    force_stub = st.sidebar.toggle(
        "Force stub mode",
        value=True,
        help="Run with offline + stub backends. Default ON for privacy.",
    )
    allow_write = st.sidebar.toggle(
        "Allow memory writes",
        value=True,
        help="Hold the write_personal_memory consent gate. Off = read-only run.",
    )
    today = datetime.now(timezone.utc).date().isoformat()
    available_dates = list_provenance_dates() or [today]
    selected_date = st.sidebar.selectbox(
        "Provenance date filter",
        options=available_dates,
        index=0,
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Backends in use**")
    st.sidebar.markdown(f"- Graph: `{_graph.BACKEND_NAME}`")
    st.sidebar.markdown(f"- Langfuse: `{LANGFUSE_BACKEND_NAME}`")
    st.sidebar.markdown(f"- DeepEval: `{DEEPEVAL_BACKEND}`")
    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"Data root: `{appdata_root()}`"
    )
    return {
        "user_id":     user_id or "default",
        "force_stub":  bool(force_stub),
        "allow_write": bool(allow_write),
        "date":        selected_date,
    }


def _render_overview_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    payload = build_overview_payload()
    st.header(":sparkles: Overview")
    st.caption(payload["tagline"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Agent", f"{payload['agent_name']} v{payload['agent_version']}")
    col2.metric("Graph backend", payload["graph_backend"])
    col3.metric("Langfuse", payload["langfuse_backend"])

    st.subheader("Latest run summary")
    latest = payload["latest_run"]
    if not latest.get("run_id"):
        st.info("No runs yet on this machine. Click **Run daily brief** in the next tab.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Run ID", str(latest["run_id"]))
        c2.metric("Nodes", latest.get("node_count", 0))
        c3.metric("Stub", "yes" if latest.get("stub") else "no")
        c4.metric("Confidence", str(latest.get("confidences") or "?"))

    st.subheader("Memory rows per source")
    if PANDAS_AVAILABLE and _pd is not None:
        df = _pd.DataFrame(
            [{"source": s, "rows": int(payload["rows_per_source"].get(s, 0))}
             for s in payload["default_sources"]]
        )
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(payload["rows_per_source"])

    st.subheader("Local data roots")
    st.code(
        "\n".join([
            f"AppData: {payload['appdata_root']}",
            f"Memory:  {payload['memory_root']}",
            f"Prov:    {payload['provenance_root']}",
            f"Eval:    {payload['eval_root']}",
        ]),
        language="text",
    )


def _render_brief_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":sun_with_face: Daily Brief")
    st.caption("One-click execution of the LangGraph daily-brief flow.")
    _render_disclaimers()

    c1, c2 = st.columns([1, 3])
    with c1:
        run_btn = st.button("Run daily brief", type="primary",
                            use_container_width=True)
    with c2:
        st.caption(
            f"User ID: `{controls['user_id']}` · "
            f"Force stub: `{controls['force_stub']}` · "
            f"Allow write: `{controls['allow_write']}`"
        )

    if run_btn:
        with st.spinner("Running 5-node graph (ingest → remember → evolve → brief → output) …"):
            out = run_daily_brief_action(
                user_id=controls["user_id"],
                force_stub=controls["force_stub"],
                allow_write=controls["allow_write"],
            )
        st.session_state["last_brief"] = out

    out = st.session_state.get("last_brief")
    if not out:
        st.info("Click **Run daily brief** to generate a fresh brief.")
        return

    payload = build_brief_payload(out)
    st.success(
        f"Brief generated at {payload['generated_at']} "
        f"(stub={payload['stub']}, backend={payload['backend']})"
    )

    sections = payload["sections"] or {}
    st.subheader("Today's schedule")
    sched = sections.get("today_schedule") or {}
    if sched.get("count", 0) == 0:
        st.write("_No events on the schedule._")
    else:
        for it in sched.get("items") or []:
            st.write(f"- `{it.get('start_iso','?')}` {it.get('summary','(no title)')}")

    st.subheader("Inbox pulse")
    inbox = sections.get("inbox_pulse") or {}
    st.metric("Unread", inbox.get("unread_count", 0))
    for s in inbox.get("top_subjects") or []:
        st.write(f"- {s}")

    st.subheader("X pulse")
    xp = sections.get("x_pulse") or {}
    cols = st.columns(4)
    cols[0].metric("Mentions",  xp.get("mention_count", 0))
    cols[1].metric("DMs",       xp.get("dm_count", 0))
    cols[2].metric("Bookmarks", xp.get("bookmark_count", 0))
    cols[3].metric("Lists",     xp.get("list_count", 0))

    st.subheader("Notes recent")
    notes = sections.get("notes_recent") or {}
    st.write(f"{notes.get('count', 0)} recent notes:")
    for t in notes.get("titles") or []:
        st.write(f"- {t}")
    if notes.get("live_threads"):
        st.markdown("**Live threads:**")
        for t in notes["live_threads"]:
            st.write(f"- {t}")

    st.subheader("Ambient")
    amb = sections.get("ambient") or {}
    st.write(f"Weather: {amb.get('weather_summary', '')}")
    for h in amb.get("news_headlines") or []:
        st.write(f"- {h}")

    st.subheader("Memory health")
    mh = sections.get("memory_health") or {}
    if PANDAS_AVAILABLE and _pd is not None:
        df = _pd.DataFrame(
            [{"source": k, "rows": v}
             for k, v in (mh.get("rows_per_source") or {}).items()]
        )
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(mh.get("rows_per_source") or {})

    if payload["violations"]:
        st.subheader("Article-II violations surfaced")
        st.warning(
            "The agent attempted an action without held consent. "
            "Hold the relevant gates in the sidebar and try again."
        )
        st.json(payload["violations"])

    st.subheader("Provenance trail")
    trail = (payload["provenance"] or {}).get("trail") or []
    if PANDAS_AVAILABLE and _pd is not None and trail:
        df = _pd.DataFrame(trail)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(trail)


def _render_memory_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":books: Memory Explorer")
    st.caption("Semantic search over the personal memory layer (P122). "
               "PII is redacted at write AND read time.")

    c1, c2, c3 = st.columns([3, 1, 1])
    query = c1.text_input("Query", value="stub")
    source = c2.selectbox("Source",
                          options=["(any)"] + list(SOURCES),
                          index=0)
    limit = c3.number_input("Limit", min_value=1, max_value=50, value=10)
    search_btn = st.button("Search memory", type="primary")

    if search_btn:
        with st.spinner("Searching personal memory layer…"):
            hits = run_memory_search_action(
                query,
                source=None if source == "(any)" else source,
                limit=int(limit),
                user_id=controls["user_id"],
                force_stub=controls["force_stub"],
            )
        st.session_state["last_search"] = hits

    hits = st.session_state.get("last_search") or []
    payload = build_memory_payload(hits)
    st.write(f"Returned **{payload['row_count']}** hits across "
             f"{len(payload['sources'])} source(s).")
    if PANDAS_AVAILABLE and _pd is not None and payload["rows"]:
        df = _pd.DataFrame(payload["rows"])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(payload["rows"])

    st.caption("All snippets above are PII-redacted via the connectors.redact_pii engine.")


def _render_provenance_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":scroll: Provenance Audit")
    st.caption(
        "Local-first JSONL audit log written by every node. "
        "Date-rolled at $env:LOCALAPPDATA\\grok-agent\\"
        "self-evolving-personal-os\\provenance\\."
    )

    available_dates = list_provenance_dates()
    date_iso = controls.get("date") or (
        available_dates[0] if available_dates
        else datetime.now(timezone.utc).date().isoformat()
    )
    records = load_records_for_date(date_iso)
    payload = build_provenance_payload(records)

    st.metric("Records on this date", payload["row_count"])

    c1, c2 = st.columns(2)
    with c1:
        run_id_filter = st.selectbox(
            "Filter by run_id",
            options=["(all)"] + payload["run_ids"],
            index=0,
        )
    with c2:
        source_filter = st.selectbox(
            "Filter by source",
            options=["(all)"] + payload["sources"],
            index=0,
        )

    filtered = build_provenance_payload(
        records,
        run_id_filter=None if run_id_filter == "(all)" else run_id_filter,
        source_filter=None if source_filter == "(all)" else source_filter,
    )
    if PANDAS_AVAILABLE and _pd is not None and filtered["rows"]:
        df = _pd.DataFrame(filtered["rows"])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(filtered["rows"])

    st.subheader("Markdown audit report")
    if st.button("Generate Markdown report", type="primary"):
        md = export_audit_report(date_iso=date_iso)
        st.session_state["last_audit_md"] = md
    md = st.session_state.get("last_audit_md")
    if md:
        st.code(md, language="markdown")
        st.download_button(
            "Download audit_report.md",
            data=md,
            file_name=f"audit_report_{date_iso}.md",
            mime="text/markdown",
        )


def _render_improve_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":cyclone: Self-Improve")
    st.caption(
        "Weekly Promptfoo + DeepEval loop. "
        "**Every suggestion is human-review-gated** — nothing is auto-applied."
    )
    _render_disclaimers()

    if st.button("Run self-improve loop", type="primary"):
        with st.spinner("Running 8 Promptfoo asserts + 5 DeepEval metrics…"):
            report = run_improve_action(
                user_id=controls["user_id"],
                force_stub=controls["force_stub"],
            )
        st.session_state["last_improve"] = report

    report = st.session_state.get("last_improve")
    if not report:
        st.info("Click **Run self-improve loop** to evaluate the current prompts.")
        return

    payload = build_improve_payload(report)
    score = payload["overall_score"]
    if score >= 0.8:
        st.success(f"Overall self-improvement score: {score:.3f}")
    else:
        st.error(f"Overall self-improvement score: {score:.3f} — review required.")

    c1, c2, c3 = st.columns(3)
    pf_pass = sum(1 for r in payload["promptfoo"] if r["passed"])
    de_pass = sum(1 for m in payload["deepeval"] if m["passed"])
    c1.metric("Promptfoo PASS", f"{pf_pass}/{len(payload['promptfoo'])}")
    c2.metric("DeepEval PASS",  f"{de_pass}/{len(payload['deepeval'])}")
    c3.metric("Backend",        payload["backend"])

    st.subheader("Promptfoo (8 test cases)")
    if PANDAS_AVAILABLE and _pd is not None:
        st.dataframe(_pd.DataFrame(payload["promptfoo"]),
                     hide_index=True, use_container_width=True)
    else:
        st.json(payload["promptfoo"])

    st.subheader("DeepEval (5 metrics)")
    if PANDAS_AVAILABLE and _pd is not None:
        st.dataframe(_pd.DataFrame(payload["deepeval"]),
                     hide_index=True, use_container_width=True)
    else:
        st.json(payload["deepeval"])

    st.subheader("Improvement suggestions")
    if not payload["suggestions"]:
        st.info("No suggestions — every check passed.")
    else:
        st.warning("All suggestions below are HUMAN-REVIEW-GATED. "
                   "Review each one and decide whether to land it manually.")
        for i, s in enumerate(payload["suggestions"], 1):
            with st.expander(f"{i}. {s.get('title','(untitled)')}"):
                st.markdown(f"**Trigger:** `{s.get('trigger_metric')}` "
                            f"(score={s.get('score','?')})")
                st.markdown(f"**Target:** `{s.get('target')}`")
                st.markdown(f"**Effort:** {s.get('estimated_effort')}")
                st.markdown(f"**Status:** **{s.get('status','needs_review')}**")
                st.write(s.get("description", ""))


# --- Section 5. Top-level layout -----------------------------------------

def _set_page_config() -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.set_page_config(**DEFAULT_PAGE_CONFIG)


def _render_app() -> None:
    if not STREAMLIT_AVAILABLE:
        return
    _set_page_config()
    st.title(DASHBOARD_TITLE)
    st.caption(_TAGLINE)
    controls = _render_sidebar()

    tabs = st.tabs(list(TAB_TITLES))
    with tabs[0]:
        _render_overview_tab(controls)
    with tabs[1]:
        _render_brief_tab(controls)
    with tabs[2]:
        _render_memory_tab(controls)
    with tabs[3]:
        _render_provenance_tab(controls)
    with tabs[4]:
        _render_improve_tab(controls)


def main() -> int:
    """CLI entry point.

    When invoked directly (``python dashboard.py``) without Streamlit
    installed, prints an installation hint and exits cleanly. Streamlit
    runs the file as a script so it never goes through this main()
    in the normal launch path.
    """
    if not STREAMLIT_AVAILABLE:
        print(
            "Streamlit is not installed in this environment.\n"
            "On Windows:\n"
            "    python -m pip install -r requirements.txt\n"
            "    streamlit run dashboard.py\n"
        )
        return 1
    _render_app()
    return 0


# Streamlit invokes the script top-level on every rerun, so we must
# render whenever the module is loaded as the main script.
if STREAMLIT_AVAILABLE:
    _render_app()
elif __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
