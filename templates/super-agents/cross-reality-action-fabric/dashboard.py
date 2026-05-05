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
"""Streamlit dashboard for the Cross-Reality Action Fabric (Super Agent #3).

Six tabs over the existing P128–P132 stack:

1. **Overview**          agent identity, backend selection, latest-run
                          summary, memory health, V.3 real-world-action
                          banner.
2. **Action Planner**     one-click "Run Daily Plan" + plan rendering
                          + Article-V.3 banner + per-step description /
                          script / rollback preview.
3. **Pending Approvals**  HITL approval queue with one-click approve
                          (mints a consent_token) and reject buttons;
                          re-runs the plan after each approval and
                          surfaces the updated provenance.
4. **Action History**     semantic search over the P130 memory layer
                          across actions / approvals / rollbacks /
                          preferences / contexts; PII redacted.
5. **Provenance Audit**   P131 JSONL viewer with date / run_id / event
                          filters AND the rollback-chain visualizer
                          (forward action ↔ rollback table).
6. **Self-Improve**       one-click trigger of the P132 Promptfoo +
                          DeepEval loop with human-review-gated
                          suggestion display.

Launched on Windows via:

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m pip install -r requirements.txt
   streamlit run dashboard.py --server.port 8506

Local-first by design: every action runs against the same AppData
folder the CLI uses. No cloud round-trip unless the user opts into
Langfuse (Article II opt-in, see :mod:`provenance.langfuse_hooks`).

Built to make Grok the obvious choice for every agent on X — the
dashboard is what turns the action fabric from a CLI binary into
something a non-technical user can run safely on their Windows
laptop. Every tab that triggers a real-world action surfaces the
V.3 banner from `constitution.md`.

Implementation note
-------------------
Same shape as P126: pure-Python data helpers below the
``STREAMLIT_AVAILABLE`` guard, Streamlit-only render paths gated by
the flag. The smoke test exercises every helper without launching a
Streamlit server.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the script's own folder is on sys.path when invoked via
# ``streamlit run dashboard.py`` (Streamlit doesn't add the script dir).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# --- Optional imports (graceful degradation) -----------------------------

try:
    import streamlit as st  # type: ignore
    STREAMLIT_AVAILABLE = True
except ImportError:  # pragma: no cover
    st = None  # type: ignore
    STREAMLIT_AVAILABLE = False

try:
    import pandas as _pd  # type: ignore
    PANDAS_AVAILABLE = True
except ImportError:
    _pd = None  # type: ignore
    PANDAS_AVAILABLE = False

try:
    import plotly.express as _px  # type: ignore  # noqa: F401
    PLOTLY_AVAILABLE = True
except ImportError:
    _px = None  # type: ignore
    PLOTLY_AVAILABLE = False


# --- P128–P132 imports ---------------------------------------------------

import agent as _agent  # type: ignore
import graph as _graph  # type: ignore
from graph import (  # type: ignore
    ALLOWED_TOOLS,
    BACKEND_NAME,
    ConsentContext,
    ConstitutionViolation,
    READ_ONLY_TOOLS,
    STATE_CHANGING_TOOLS,
    appdata_root,
    redact_pii,
)
from memory import (  # type: ignore
    COLLECTION_FOR_KIND,
    MEMORY_KINDS,
    MEMORY_WRITE_GATE,
    PersonalMemoryClient,
    SearchHit,
    get_memory_client,
)
from provenance import (  # type: ignore
    LANGFUSE_BACKEND_NAME,
    LocalProvenanceLogger,
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
    "build_plan_payload",
    "build_pending_payload",
    "build_history_payload",
    "build_provenance_payload",
    "build_improve_payload",
    "list_provenance_dates",
    "load_records_for_date",
    "rollback_chain_rows",
    "redact_for_display",
    # actions
    "run_daily_plan_action",
    "approve_pending_action",
    "rollback_last_action",
    "run_memory_search_action",
    "run_improve_action",
    # disclaimers
    "DISCLAIMER_RW",
    "DISCLAIMER_LOCAL_FIRST",
    # entry points
    "main",
]


# --- Section 1. Constants ------------------------------------------------

DASHBOARD_TITLE = "Cross-Reality Action Fabric — Dashboard"

TAB_TITLES: tuple[str, ...] = (
    "Overview",
    "Action Planner",
    "Pending Approvals",
    "Action History",
    "Provenance Audit",
    "Self-Improve",
)

DEFAULT_PAGE_CONFIG: dict = {
    "page_title":  DASHBOARD_TITLE,
    "page_icon":   ":sparkles:",
    "layout":      "wide",
    "initial_sidebar_state": "expanded",
}

# Article V.3 real-world-action banner (constitution.md exact wording).
DISCLAIMER_RW = (
    "⚠️ **This agent can take real-world actions.** Every action requires "
    "explicit consent. Review the action plan before approving. The agent "
    "never acts autonomously."
)

# Article VII / Rule 6 local-first reassurance.
DISCLAIMER_LOCAL_FIRST = (
    "🔒 **Local-first + privacy-first.** Every byte of personal data lives "
    "under `$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\`. "
    "Cloud sync, telemetry, and Langfuse traces are opt-in only."
)

_TAGLINE = (
    "Built for xAI, Grok and the whole community on X — "
    "the missing 'do something for me' layer for every agent on X."
)


# --- Section 2. Data helpers (pure Python, no Streamlit) ----------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_provenance_dates() -> list[str]:
    """Every YYYY-MM-DD JSONL file present in provenance/, newest first."""
    root = provenance_root()
    if not root.exists():
        return []
    out: list[str] = []
    for p in sorted(root.glob("*.jsonl"), reverse=True):
        name = p.name
        if (
            len(name) == len("YYYY-MM-DD.jsonl")
            and name[4] == "-" and name[7] == "-"
        ):
            out.append(name.replace(".jsonl", ""))
    return out


def load_records_for_date(date_iso: str) -> list:
    """Load all ActionProvenanceRecord rows for one UTC date."""
    from provenance.log import ActionProvenanceRecord  # type: ignore
    path = log_path_for(date_iso)
    if not path.exists():
        return []
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(ActionProvenanceRecord.from_jsonl(line))
                except Exception:
                    continue
    except OSError:
        return []
    return out


def rollback_chain_rows(records: list) -> list[dict]:
    """Build the rollback-chain visualizer rows from a record list.

    Pairs every ``rollback_executed`` record with the forward
    ``action_executed`` record it points to via ``rolled_back_from``.
    """
    by_action_id = {}
    for r in records:
        if getattr(r, "action_id", None):
            by_action_id[r.action_id] = r
    chain: list[dict] = []
    for r in records:
        if getattr(r, "event_kind", None) == "rollback_executed" \
                and getattr(r, "rolled_back_from", None):
            forward = by_action_id.get(r.rolled_back_from)
            chain.append({
                "forward_action_id": r.rolled_back_from,
                "forward_tool":      forward.tool if forward else None,
                "forward_step":      forward.step if forward else None,
                "rollback_id":       r.rollback_id,
                "rollback_step":     r.step,
                "rollback_outcome":  r.outcome,
                "timestamp":         r.timestamp,
            })
    return chain


def redact_for_display(value: Any) -> Any:
    """Defence-in-depth display redactor (mirrors P126)."""
    return redact_pii(value)


# --- Section 3. Payload builders ----------------------------------------

def build_overview_payload() -> dict:
    """Compose the Overview tab's data dict."""
    desc = _graph.describe_graph()
    appdata = appdata_root()
    memory_path = appdata / "memory"
    prov_path = provenance_root()
    eval_path = eval_results_root()

    # Latest run summary from the P131 audit log
    log = LocalProvenanceLogger()
    latest_recs = log.latest_run()
    latest = summarise_run(latest_recs)

    # Memory rows per kind
    rows_per_kind: dict[str, int] = {}
    try:
        client = get_memory_client(force_stub=True, refresh=True)
        client.set_consent(ConsentContext.from_iterable(
            list(_agent.ALL_GATES) + [MEMORY_WRITE_GATE],
        ))
        for kind in MEMORY_KINDS:
            try:
                rows_per_kind[kind] = int(client.count(kind=kind))
            except Exception:
                rows_per_kind[kind] = 0
    except Exception:
        rows_per_kind = {k: 0 for k in MEMORY_KINDS}

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
        "max_actions":         desc["max_actions"],
        "max_plan_loops":      desc["max_plan_loops"],
        "tools":               list(desc["tools"]),
        "state_changing":      list(desc["state_changing"]),
        "read_only":           list(desc["read_only"]),
        "latest_run":          latest,
        "rows_per_kind":       rows_per_kind,
        "tagline":             _TAGLINE,
    }


def build_plan_payload(out: dict) -> dict:
    """Massage a daily-plan output dict for the Action Planner tab."""
    if not isinstance(out, dict):
        return {"empty": True}
    plan = out.get("plan") or {}
    actions = plan.get("proposed_actions") or []
    return {
        "empty":           not bool(plan),
        "plan_id":         plan.get("plan_id"),
        "user_request":    plan.get("user_request"),
        "stub":            bool(out.get("stub")),
        "backend":         out.get("backend"),
        "actions":         [redact_for_display(a) for a in actions],
        "violations":      list(out.get("violations") or []),
        "executions":      list(out.get("executions") or []),
        "rollbacks":       list(out.get("rollbacks") or []),
        "provenance":      dict(out.get("provenance") or {}),
        "memory_ingest":   dict(out.get("memory_ingest") or {}),
        "provenance_ingest": dict(out.get("provenance_ingest") or {}),
    }


def build_pending_payload(plan: dict | None) -> dict:
    """Shape the persisted pending plan for the Pending Approvals tab."""
    if not isinstance(plan, dict):
        return {"empty": True, "rows": [], "count": 0}
    actions = plan.get("proposed_actions") or []
    pending = [
        a for a in actions
        if not a.get("executed")
        and not a.get("consent_token")
        and (a.get("refusal_reason") or "").startswith("missing consent_token")
    ]
    rows = [
        {
            "step":             a.get("step"),
            "tool":             a.get("tool"),
            "description":      redact_for_display(a.get("description") or ""),
            "script":           redact_for_display((a.get("script") or "")[:200]),
            "rollback":         redact_for_display((a.get("rollback") or "")[:200]),
            "expected_cost_usd": float(a.get("expected_cost_usd") or 0.0),
            "state_changing":   a.get("tool") in STATE_CHANGING_TOOLS,
            "has_rollback":     bool((a.get("rollback") or "").strip()),
        }
        for a in pending
    ]
    return {
        "empty":         not pending,
        "plan_id":       plan.get("plan_id"),
        "user_request":  plan.get("user_request"),
        "rows":          rows,
        "count":         len(rows),
    }


def build_history_payload(hits: "list[SearchHit] | list[dict]") -> dict:
    """Shape a memory search result for the Action History tab.

    Accepts either :class:`SearchHit` instances or their ``to_dict()``
    form (the agent.search command returns dicts).
    """
    def _attr(h: Any, key: str, default: Any = None) -> Any:
        if isinstance(h, dict):
            return h.get(key, default)
        return getattr(h, key, default)

    rows: list[dict] = []
    kinds_seen: set[str] = set()
    for h in hits:
        text = _attr(h, "text") or ""
        kind = _attr(h, "kind") or ""
        prov = _attr(h, "provenance") or {}
        if not isinstance(prov, dict):
            prov = {}
        rows.append({
            "score":      round(float(_attr(h, "score", 0.0)), 4),
            "kind":       kind,
            "timestamp":  _attr(h, "timestamp") or "",
            "snippet":    redact_for_display(
                text[:200] + ("…" if len(text) > 200 else "")
            ),
            "id":         _attr(h, "id", ""),
            "redacted":   bool(prov.get("redaction_applied")),
        })
        if kind:
            kinds_seen.add(kind)
    return {
        "row_count":  len(rows),
        "rows":       rows,
        "kinds":      sorted(kinds_seen),
    }


def build_provenance_payload(
    records: list,
    *,
    event_kind_filter: str | None = None,
    run_id_filter: str | None = None,
    tool_filter: str | None = None,
) -> dict:
    """Shape ActionProvenanceRecord rows for the Provenance Audit tab."""
    filtered = list(records)
    if event_kind_filter:
        filtered = [r for r in filtered if getattr(r, "event_kind", None) == event_kind_filter]
    if run_id_filter:
        filtered = [r for r in filtered if getattr(r, "run_id", None) == run_id_filter]
    if tool_filter:
        filtered = [r for r in filtered if getattr(r, "tool", None) == tool_filter]

    rows: list[dict] = []
    for r in filtered:
        rows.append({
            "timestamp":      getattr(r, "timestamp", ""),
            "event_kind":     getattr(r, "event_kind", ""),
            "step":           getattr(r, "step", None),
            "tool":           getattr(r, "tool", None),
            "outcome":        getattr(r, "outcome", None),
            "consent_token":  bool(getattr(r, "consent_token", None)),
            "cost_usd":       float(getattr(r, "cost_usd", 0.0) or 0.0),
            "stub":           bool(getattr(r, "stub_reason", None)),
            "error":          getattr(r, "error", None),
            "rollback_id":    getattr(r, "rollback_id", None),
            "rolled_back_from": getattr(r, "rolled_back_from", None),
        })

    return {
        "row_count":   len(rows),
        "rows":        rows,
        "summary":     summarise_run(filtered),
        "run_ids":     sorted({getattr(r, "run_id", None)
                                for r in records if getattr(r, "run_id", None)}),
        "event_kinds": sorted({getattr(r, "event_kind", None)
                                for r in records if getattr(r, "event_kind", None)}),
        "tools":       sorted({getattr(r, "tool", None)
                                for r in records if getattr(r, "tool", None)}),
        "rollback_chain": rollback_chain_rows(records),
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


# --- Section 4. Action runners ------------------------------------------

def run_daily_plan_action(
    *,
    user_id: str = "default",
    force_stub: bool = True,
    auto_approve: bool = False,
) -> dict:
    """Execute the daily-plan flow and return its output dict."""
    return _agent.daily_plan(
        user_id=user_id,
        force_stub=force_stub,
        auto_approve=auto_approve,
        quiet=True,
    )


def approve_pending_action(
    *,
    accept_steps: list[int] | None = None,
    user_id: str = "default",
    force_stub: bool = True,
) -> dict:
    """Approve the pending plan steps and re-run the loop."""
    return _agent.approve_pending(
        accept_steps=accept_steps,
        user_id=user_id,
        force_stub=force_stub,
        quiet=True,
    )


def rollback_last_action(
    *,
    user_id: str = "default",
    force_stub: bool = True,
) -> dict:
    """Run the verbatim rollback for the most-recent state-changing action."""
    return _agent.rollback_last(
        user_id=user_id,
        force_stub=force_stub,
        quiet=True,
    )


def run_memory_search_action(
    query: str,
    *,
    kind: str | None = None,
    limit: int = 10,
    user_id: str = "default",
    force_stub: bool = True,
) -> "list[SearchHit] | list[dict]":
    """Execute a memory search across kinds (actions / approvals / etc.)."""
    client = get_memory_client(force_stub=force_stub, refresh=True)
    client.set_consent(ConsentContext.from_iterable(
        list(_agent.ALL_GATES) + [MEMORY_WRITE_GATE],
    ))
    return client.search_by_context(query=query, kind=kind, limit=int(limit))


def run_improve_action(
    *,
    user_id: str = "default",
    force_stub: bool = True,
) -> EvalReport:
    """Trigger the P132 Promptfoo + DeepEval loop."""
    return run_full_loop(force_stub=force_stub, user_id=user_id)


# --- Section 5. Streamlit render paths ----------------------------------

def _render_disclaimers() -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.warning(DISCLAIMER_RW)
    st.info(DISCLAIMER_LOCAL_FIRST)


def _render_sidebar() -> dict:
    if not STREAMLIT_AVAILABLE:
        return {
            "user_id":      "default",
            "force_stub":   True,
            "auto_approve": False,
            "date":         datetime.now(timezone.utc).date().isoformat(),
        }
    st.sidebar.title("Action Fabric")
    st.sidebar.caption(_TAGLINE)
    user_id = st.sidebar.text_input("User ID", value="default")
    force_stub = st.sidebar.toggle(
        "Force stub mode",
        value=True,
        help="Run with offline + stub backends. Default ON for privacy.",
    )
    auto_approve = st.sidebar.toggle(
        "Auto-approve (CI only)",
        value=False,
        help=(
            "Skip the typed HITL approval prompt. Never use interactively — "
            "this flag exists for CI runs only. Article II requires typed "
            "approval for every real-world action."
        ),
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
    st.sidebar.markdown(f"- Graph: `{BACKEND_NAME}`")
    st.sidebar.markdown(f"- Langfuse: `{LANGFUSE_BACKEND_NAME}`")
    st.sidebar.markdown(f"- DeepEval: `{DEEPEVAL_BACKEND}`")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Data root: `{appdata_root()}`")
    return {
        "user_id":      user_id or "default",
        "force_stub":   bool(force_stub),
        "auto_approve": bool(auto_approve),
        "date":         selected_date,
    }


def _render_overview_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    payload = build_overview_payload()
    st.header(":sparkles: Overview")
    st.caption(payload["tagline"])
    _render_disclaimers()

    c1, c2, c3 = st.columns(3)
    c1.metric("Agent", f"{payload['agent_name']} v{payload['agent_version']}")
    c2.metric("Graph backend", payload["graph_backend"])
    c3.metric("Langfuse", payload["langfuse_backend"])

    st.subheader("Latest run summary")
    latest = payload["latest_run"]
    if not latest.get("run_id"):
        st.info("No runs yet. Open the **Action Planner** tab and click "
                "**Run Daily Plan**.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Run ID",        str(latest.get("run_id")))
        c2.metric("Event count",   latest.get("event_count", 0))
        c3.metric("Stub",          "yes" if latest.get("stub") else "no")
        c4.metric("Cost USD total", f"{latest.get('cost_usd_total', 0.0):.2f}")

    st.subheader("Memory rows per kind")
    if PANDAS_AVAILABLE and _pd is not None:
        df = _pd.DataFrame(
            [{"kind": k, "rows": int(payload["rows_per_kind"].get(k, 0))}
             for k in MEMORY_KINDS]
        )
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(payload["rows_per_kind"])

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


def _render_planner_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":compass: Action Planner")
    st.caption("One-click execution of the LangGraph daily-plan flow.")
    _render_disclaimers()

    c1, c2 = st.columns([1, 3])
    with c1:
        run_btn = st.button("Run Daily Plan", type="primary",
                            use_container_width=True)
    with c2:
        st.caption(
            f"User: `{controls['user_id']}` · "
            f"Force stub: `{controls['force_stub']}` · "
            f"Auto-approve: `{controls['auto_approve']}`"
        )

    if run_btn:
        with st.spinner("Running 8-node action graph (plan → approve → execute → output) …"):
            out = run_daily_plan_action(
                user_id=controls["user_id"],
                force_stub=controls["force_stub"],
                auto_approve=controls["auto_approve"],
            )
        st.session_state["last_plan"] = out

    out = st.session_state.get("last_plan")
    if not out:
        st.info("Click **Run Daily Plan** to generate today's action plan.")
        return

    payload = build_plan_payload(out)
    st.success(
        f"Plan {payload['plan_id']} generated "
        f"(stub={payload['stub']}, backend={payload['backend']})"
    )

    st.subheader("Proposed actions")
    if PANDAS_AVAILABLE and _pd is not None and payload["actions"]:
        df = _pd.DataFrame([
            {
                "step":         a.get("step"),
                "tool":         a.get("tool"),
                "description":  (a.get("description") or "")[:80],
                "executed":     a.get("executed"),
                "outcome":      a.get("outcome"),
                "has_rollback": bool((a.get("rollback") or "").strip()),
                "consent_token": "yes" if a.get("consent_token") else "no",
            }
            for a in payload["actions"]
        ])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(payload["actions"])

    if payload["violations"]:
        st.subheader("Article-II violations surfaced")
        st.warning(
            "The agent attempted an action without held consent. "
            "Hold the relevant gates in the sidebar and try again."
        )
        st.json(payload["violations"])

    if payload["executions"]:
        st.subheader("Executions")
        if PANDAS_AVAILABLE and _pd is not None:
            st.dataframe(_pd.DataFrame(payload["executions"]),
                         hide_index=True, use_container_width=True)
        else:
            st.json(payload["executions"])

    if payload["rollbacks"]:
        st.subheader("Rollbacks (Rule 3)")
        if PANDAS_AVAILABLE and _pd is not None:
            st.dataframe(_pd.DataFrame(payload["rollbacks"]),
                         hide_index=True, use_container_width=True)
        else:
            st.json(payload["rollbacks"])


def _render_pending_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":hourglass_flowing_sand: Pending Approvals")
    st.caption(
        "Article II HITL queue. Type the displayed token below to approve "
        "individual steps (or all). The agent never acts without typed "
        "approval per step."
    )
    _render_disclaimers()

    pending_path = _agent.pending_plan_path()
    plan = None
    if pending_path.exists():
        try:
            plan = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            plan = None

    payload = build_pending_payload(plan)
    if payload["empty"]:
        st.info("No pending approvals. Run **Run Daily Plan** in the previous tab.")
        return

    st.write(f"**Plan ID:** `{payload['plan_id']}` · "
             f"**{payload['count']}** step(s) awaiting approval")

    if PANDAS_AVAILABLE and _pd is not None:
        df = _pd.DataFrame(payload["rows"])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.json(payload["rows"])

    st.markdown("**Approve specific steps (comma-separated):**")
    selection = st.text_input(
        "Steps to approve",
        value=", ".join(str(r["step"]) for r in payload["rows"]),
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Approve selected & re-run", type="primary",
                     use_container_width=True):
            try:
                steps = [int(s.strip()) for s in selection.split(",")
                         if s.strip()]
            except ValueError:
                st.error("Step list must be comma-separated integers.")
                return
            with st.spinner("Approving + re-running plan…"):
                result = approve_pending_action(
                    accept_steps=steps,
                    user_id=controls["user_id"],
                    force_stub=controls["force_stub"],
                )
            st.session_state["last_plan"] = result.get("output")
            st.success(
                f"Approved {result.get('approved')} step(s) — "
                f"{result.get('executed')} executed."
            )

    with c2:
        if st.button("Roll back the most recent action",
                     use_container_width=True):
            with st.spinner("Running rollback…"):
                result = rollback_last_action(
                    user_id=controls["user_id"],
                    force_stub=controls["force_stub"],
                )
            st.session_state["last_plan"] = result.get("output")
            st.success(
                f"Rolled back {result.get('rolled_back')} action(s)."
            )


def _render_history_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":books: Action History")
    st.caption(
        "Semantic search over the P130 memory layer. PII is redacted at "
        "write AND read time."
    )

    c1, c2, c3 = st.columns([3, 1, 1])
    query = c1.text_input("Query", value="weather")
    kind = c2.selectbox(
        "Kind", options=["(any)"] + list(MEMORY_KINDS), index=0,
    )
    limit = c3.number_input("Limit", min_value=1, max_value=50, value=10)
    search_btn = st.button("Search history", type="primary")

    if search_btn:
        with st.spinner("Searching memory…"):
            hits = run_memory_search_action(
                query,
                kind=None if kind == "(any)" else kind,
                limit=int(limit),
                user_id=controls["user_id"],
                force_stub=controls["force_stub"],
            )
        st.session_state["last_history_search"] = hits

    hits = st.session_state.get("last_history_search") or []
    payload = build_history_payload(hits)
    st.write(
        f"Returned **{payload['row_count']}** hit(s) across "
        f"{len(payload['kinds'])} kind(s)."
    )
    if PANDAS_AVAILABLE and _pd is not None and payload["rows"]:
        st.dataframe(_pd.DataFrame(payload["rows"]),
                     hide_index=True, use_container_width=True)
    else:
        st.json(payload["rows"])

    st.caption("All snippets above are PII-redacted via "
               "connectors.redact_pii (the same engine the connectors use).")


def _render_provenance_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":scroll: Provenance Audit")
    st.caption(
        "Local-first JSONL audit log. Every Constitution event the agent "
        "emits gets one ActionProvenanceRecord row — date-rolled at "
        "$env:LOCALAPPDATA\\grok-agent\\cross-reality-action-fabric\\"
        "provenance\\."
    )

    available_dates = list_provenance_dates()
    date_iso = controls.get("date") or (
        available_dates[0] if available_dates
        else datetime.now(timezone.utc).date().isoformat()
    )
    records = load_records_for_date(date_iso)

    payload = build_provenance_payload(records)
    st.metric("Records on this date", payload["row_count"])

    c1, c2, c3 = st.columns(3)
    with c1:
        run_id_filter = st.selectbox(
            "Filter by run_id",
            options=["(all)"] + payload["run_ids"],
            index=0,
        )
    with c2:
        event_filter = st.selectbox(
            "Filter by event_kind",
            options=["(all)"] + payload["event_kinds"],
            index=0,
        )
    with c3:
        tool_filter = st.selectbox(
            "Filter by tool",
            options=["(all)"] + payload["tools"],
            index=0,
        )

    filtered = build_provenance_payload(
        records,
        run_id_filter=None if run_id_filter == "(all)" else run_id_filter,
        event_kind_filter=None if event_filter == "(all)" else event_filter,
        tool_filter=None if tool_filter == "(all)" else tool_filter,
    )
    if PANDAS_AVAILABLE and _pd is not None and filtered["rows"]:
        st.dataframe(_pd.DataFrame(filtered["rows"]),
                     hide_index=True, use_container_width=True)
    else:
        st.json(filtered["rows"])

    # --- Rollback chain visualizer ---------------------------------------
    st.subheader("Rollback chain visualizer (Rule 3)")
    chain = filtered.get("rollback_chain") or []
    if not chain:
        st.write("_No rollbacks recorded for this scope._")
    else:
        st.write(f"**{len(chain)}** rollback(s) cross-linked to forward action(s):")
        if PANDAS_AVAILABLE and _pd is not None:
            st.dataframe(_pd.DataFrame(chain),
                         hide_index=True, use_container_width=True)
        else:
            st.json(chain)

    # --- Markdown export -------------------------------------------------
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
            file_name=f"crf_audit_{date_iso}.md",
            mime="text/markdown",
        )


def _render_improve_tab(controls: dict) -> None:
    if not STREAMLIT_AVAILABLE:
        return
    st.header(":cyclone: Self-Improve")
    st.caption(
        "Weekly Promptfoo + DeepEval loop. **Every suggestion is "
        "human-review-gated** — nothing is auto-applied."
    )
    _render_disclaimers()

    if st.button("Run self-improve loop", type="primary"):
        with st.spinner("Running 8 Promptfoo asserts + 6 DeepEval metrics…"):
            report = run_improve_action(
                user_id=controls["user_id"],
                force_stub=controls["force_stub"],
            )
        st.session_state["last_improve"] = report

    report = st.session_state.get("last_improve")
    if not report:
        st.info("Click **Run self-improve loop** to evaluate the current "
                "action-fabric prompts.")
        return

    payload = build_improve_payload(report)
    score = payload["overall_score"]
    if score >= 0.8:
        st.success(f"Overall action-improvement score: {score:.3f}")
    else:
        st.error(f"Overall action-improvement score: {score:.3f} — review required.")

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

    st.subheader("DeepEval (6 metrics)")
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


# --- Section 6. Top-level layout ----------------------------------------

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
        _render_planner_tab(controls)
    with tabs[2]:
        _render_pending_tab(controls)
    with tabs[3]:
        _render_history_tab(controls)
    with tabs[4]:
        _render_provenance_tab(controls)
    with tabs[5]:
        _render_improve_tab(controls)


def main() -> int:
    """CLI entry point."""
    if not STREAMLIT_AVAILABLE:
        print(
            "Streamlit is not installed in this environment.\n"
            "On Windows:\n"
            "    python -m pip install -r requirements.txt\n"
            "    streamlit run dashboard.py --server.port 8506\n"
        )
        return 1
    _render_app()
    return 0


# Streamlit invokes the script top-level on every rerun.
if STREAMLIT_AVAILABLE:
    _render_app()
elif __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
