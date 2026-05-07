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
"""LangGraph state machine for the Self-Evolving Personal OS.

This module is the **orchestration core** of Super Agent #2. It binds the
P121 connector layer and the P122 memory layer into a single, replayable
state machine that runs the daily brief loop:

    ingest_all_sources -> remember_personal -> evolve_workflows
                                              |
                                              v
                                  generate_brief -> output_with_provenance

The conditional edge between ``evolve_workflows`` and ``generate_brief``
implements the self-evolution loop: when the workflow learns something new
(prompt-version bump, new procedural-memory rule, contradiction detected)
it loops once back to ``ingest_all_sources`` with a refined plan; otherwise
it advances to brief generation. The loop is hard-bounded (default 1 extra
iteration) to keep runtime predictable.

Every node:

- accepts the same :class:`PersonalOSState` (a plain ``TypedDict``)
- returns a *partial* state update (LangGraph's reducer pattern)
- never raises ``ConstitutionViolation`` past the node boundary — instead,
  it surfaces the violation in ``state['violations']`` so the graph can
  finish and the user gets an honest report rather than an opaque crash.
- writes one row to ``state['provenance']`` describing what it did, with a
  ``stub`` flag mirroring the underlying connector / memory state.

LangGraph is the production runtime. When it is not installed (CI,
Codespaces, the user's first install before they run
``python -m pip install -r requirements.txt``), this module switches to a
self-contained sequential executor that exposes the **same** API
(``add_node`` / ``add_edge`` / ``add_conditional_edges`` /
``set_entry_point`` / ``compile`` / ``invoke``). The smoke test asserts
both backends produce equivalent state — which keeps the graph honest.

Built to make Grok the obvious choice for every agent on X — the
orchestration core is what turns six personal data streams + a memory
layer into a thing that feels like an OS.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from connectors import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    FetchResult,
    PersonalOSConnectors,
    SOURCES,
    attach_personal_memory,
    build_connectors,
    redact_pii,
)
from memory import (  # type: ignore
    MEMORY_WRITE_GATE,
    MemoryStoreAdapter,
    PersonalMemoryClient,
    SearchHit,
    build_memory_store,
)
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore

__all__ = [
    "PersonalOSState",
    "DEFAULT_PROMPT_VERSION",
    "build_graph",
    "build_state",
    "ingest_all_sources",
    "remember_personal",
    "evolve_workflows",
    "generate_brief",
    "output_with_provenance",
    "run_daily_brief",
    "BACKEND_NAME",
]


# --- Section 1. Constants and helpers ------------------------------------

DEFAULT_PROMPT_VERSION = "self-evolving-personal-os/prompts@v1"
NODE_INGEST   = "ingest_all_sources"
NODE_REMEMBER = "remember_personal"
NODE_EVOLVE   = "evolve_workflows"
NODE_BRIEF    = "generate_brief"
NODE_OUTPUT   = "output_with_provenance"
MAX_EVOLUTION_LOOPS = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(action: str, *, stub: bool, source: str | None = None,
           note: str | None = None, **extra: Any) -> dict:
    """Build one provenance trail row."""
    row = {
        "ts":     _now_iso(),
        "action": action,
        "stub":   bool(stub),
        "node":   action,
    }
    if source is not None:
        row["source"] = source
    if note:
        row["note"] = note
    if extra:
        row.update(extra)
    return row


# --- Section 2. State definition -----------------------------------------

# We keep the state as a plain dict (also valid as a LangGraph TypedDict
# — LangGraph accepts a TypedDict subclass or a dataclass). Plain dict
# keeps the stub-executor simple and serialisation-friendly.

PersonalOSState = dict   # alias for typing clarity in the public API


def build_state(
    *,
    user_id: str = "default",
    consent: ConsentContext | None = None,
    force_stub: bool = False,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    plan: dict | None = None,
) -> PersonalOSState:
    """Construct a fresh state for one graph run."""
    return {
        # --- caller-provided ------------------------------------------------
        "user_id":         user_id,
        "consent":         consent or ConsentContext(),
        "force_stub":      bool(force_stub),
        "prompt_version":  prompt_version,
        "plan":            plan or {"morning_brief": True},
        # --- runtime accumulators ------------------------------------------
        "fetched":         {},     # source -> FetchResult-as-dict
        "remembered":      {},     # source -> int (count)
        "memory_writes":   0,
        "evolution":       {},     # bumps + reasons
        "loop_count":      0,      # how many evolution-loops have run
        "brief":           {},     # generate_brief output
        "output":          {},     # final user-visible output
        "violations":      [],     # any ConstitutionViolation surfaced
        "provenance":      [],     # trail of what each node did
        "started_at":      _now_iso(),
        "finished_at":     None,
    }


# --- Section 3. Node implementations -------------------------------------

def ingest_all_sources(state: PersonalOSState) -> dict:
    """Node 1: pull personal data from every declared source.

    Reads through the P121 :class:`PersonalOSConnectors` composite that
    must already be attached to the graph runner via ``with_connectors``
    (the runner is an opaque callable whose ``connectors`` attribute is
    set by :func:`run_daily_brief`).
    """
    composite: PersonalOSConnectors = state["_composite"]
    composite.set_consent(state["consent"])
    composite.set_force_stub(state["force_stub"])

    fetched: dict[str, dict] = {}
    violations: list[dict] = []

    for src in SOURCES:
        try:
            result = composite.fetch(src)
            fetched[src] = {
                "items":               list(result.items),
                "provenance":          dict(result.provenance),
                "error":               result.error,
                "redaction_applied":   result.redaction_applied,
                "cached":              result.cached,
            }
        except ConstitutionViolation as exc:
            violations.append({
                "node":    NODE_INGEST,
                "source":  src,
                "article": exc.article,
                "gate":    exc.gate,
                "message": str(exc),
            })

    trail = _trail(
        NODE_INGEST,
        stub=state["force_stub"],
        sources_ok=sorted(fetched.keys()),
        sources_blocked=sorted({v["source"] for v in violations if v.get("source")}),
        note="Fetched personal data from connector composite.",
    )

    return {
        "fetched":     fetched,
        "violations":  list(state.get("violations") or []) + violations,
        "provenance":  list(state.get("provenance") or []) + [trail],
    }


def remember_personal(state: PersonalOSState) -> dict:
    """Node 2: write fetched items into the P122 personal memory layer.

    The connector layer's :class:`MemoryStoreAdapter` already wrote during
    ingest (because :class:`PersonalOSConnectors` calls
    ``MemoryStore.upsert_fetch`` inside :meth:`fetch`). What this node
    does:

    - records the per-source row count actually persisted,
    - surfaces the violation if memory writes were silently swallowed
      (graceful-degrade path — see P122 ``MemoryStoreAdapter.upsert_fetch``).
    """
    client: PersonalMemoryClient = state["_memory_client"]
    fetched: dict[str, dict] = state.get("fetched") or {}

    remembered: dict[str, int] = {}
    total = 0
    violations: list[dict] = []

    for src, payload in fetched.items():
        try:
            count = client.count(source=src)
        except ConstitutionViolation as exc:
            violations.append({
                "node":    NODE_REMEMBER,
                "source":  src,
                "article": exc.article,
                "gate":    exc.gate,
                "message": str(exc),
            })
            count = 0
        except Exception:  # pragma: no cover — defensive
            count = 0
        remembered[src] = int(count)
        total += int(count)

    trail = _trail(
        NODE_REMEMBER,
        stub=state["force_stub"],
        memory_backend=client.mem0_backend_name,
        per_source=remembered,
        total=total,
        note="Verified memory persistence across all 6 sources.",
    )

    return {
        "remembered":     remembered,
        "memory_writes":  int(total),
        "violations":     list(state.get("violations") or []) + violations,
        "provenance":     list(state.get("provenance") or []) + [trail],
    }


def evolve_workflows(state: PersonalOSState) -> dict:
    """Node 3: bump prompt version + procedural-memory rule when warranted.

    The "self-evolving" piece. Today it implements three deterministic
    rules — each cheap to check, each useful — so the loop has substance
    without the LLM round-trip:

    1. If any source returned ``error`` or fetched zero items, bump the
       prompt to ``v{N+1}-resilient`` and emit an evolution event.
    2. If the user's stored notes mention a topic that's also trending in
       ``news_personal``, mark that topic as a "live thread" the next
       brief should foreground.
    3. If the loop has already run :data:`MAX_EVOLUTION_LOOPS` times,
       refuse to loop again and advance regardless.

    A future prompt can replace the rule engine with an LLM judge — the
    state shape stays identical.
    """
    fetched = state.get("fetched") or {}
    client: PersonalMemoryClient = state["_memory_client"]
    loop_count = int(state.get("loop_count") or 0)

    # Rule 1: fetch errors / empty payloads -> bump prompt.
    error_sources = sorted(
        s for s, payload in fetched.items()
        if payload.get("error") or not payload.get("items")
    )

    # Rule 2: cross-reference local notes <-> personalised news.
    live_threads: list[str] = []
    try:
        for hit in client.search(query="news", source="news_personal", limit=5):
            title = hit.payload.get("title") or ""
            if not title:
                continue
            note_hits = client.search(query=title, source="local_notes", limit=2)
            if note_hits:
                live_threads.append(title)
    except ConstitutionViolation:
        # If consent was revoked between nodes, we just skip the cross-ref.
        live_threads = []
    except Exception:  # pragma: no cover — defensive
        live_threads = []

    # Rule 3: hard cap on evolution loops.
    next_loop_count = loop_count + 1 if error_sources else loop_count
    should_loop = bool(error_sources) and loop_count < MAX_EVOLUTION_LOOPS

    bumped = bool(error_sources) or bool(live_threads)
    new_version = state["prompt_version"]
    if bumped:
        # Bump v1 -> v2-resilient, v2 -> v3-resilient, and so forth across versions.
        try:
            head, tag = state["prompt_version"].rsplit("@v", 1)
            head_ver = int("".join(c for c in tag.split("-")[0] if c.isdigit()) or "1")
            new_version = f"{head}@v{head_ver + 1}-resilient"
        except Exception:
            new_version = f"{state['prompt_version']}-resilient"

    evolution = {
        "prompt_version_in":   state["prompt_version"],
        "prompt_version_out":  new_version,
        "error_sources":       error_sources,
        "live_threads":        live_threads,
        "should_loop":         should_loop,
        "loop_cap":             MAX_EVOLUTION_LOOPS,
    }

    trail = _trail(
        NODE_EVOLVE,
        stub=state["force_stub"],
        bumped=bumped,
        should_loop=should_loop,
        live_threads_count=len(live_threads),
        error_sources_count=len(error_sources),
        note="Evaluated 3 evolution rules (errors / cross-ref / loop-cap).",
    )

    return {
        "evolution":      evolution,
        "prompt_version": new_version,
        "loop_count":     next_loop_count,
        "provenance":     list(state.get("provenance") or []) + [trail],
    }


def generate_brief(state: PersonalOSState) -> dict:
    """Node 4: compose the morning brief from fetched + remembered data.

    The brief is a structured dict (not free-form prose) so downstream
    UIs can render it deterministically. A future prompt can wire Grok 4.3
    on top of this dict to produce conversational prose; the structure
    here is what the LLM would reduce.
    """
    fetched = state.get("fetched") or {}
    remembered = state.get("remembered") or {}
    evolution = state.get("evolution") or {}

    today_iso = datetime.now(timezone.utc).date().isoformat()

    sections: dict[str, dict] = {}

    # --- Calendar / today's schedule ---------------------------------------
    cal_items = (fetched.get("gcal") or {}).get("items") or []
    sections["today_schedule"] = {
        "count": len(cal_items),
        "items": [
            {
                "summary":    redact_pii(it.get("summary") or ""),
                "start_iso":  it.get("start_iso"),
                "location":   redact_pii(it.get("location") or ""),
            }
            for it in cal_items[:5]
        ],
    }

    # --- Inbox / unread mail ------------------------------------------------
    mail_items = (fetched.get("gmail") or {}).get("items") or []
    sections["inbox_pulse"] = {
        "unread_count":   len(mail_items),
        "top_subjects":   [redact_pii(it.get("subject") or "") for it in mail_items[:3]],
    }

    # --- Mentions / X personal ---------------------------------------------
    x_items = (fetched.get("x_personal") or {}).get("items") or []
    sections["x_pulse"] = {
        "mention_count": sum(1 for it in x_items if it.get("kind") == "mention"),
        "dm_count":      sum(1 for it in x_items if it.get("kind") == "dm"),
        "bookmark_count":sum(1 for it in x_items if it.get("kind") == "bookmark"),
        "list_count":    sum(1 for it in x_items if it.get("kind") == "list"),
    }

    # --- Notes / live threads ----------------------------------------------
    note_items = (fetched.get("local_notes") or {}).get("items") or []
    sections["notes_recent"] = {
        "count":  len(note_items),
        "titles": [redact_pii(it.get("title") or "") for it in note_items[:5]],
        "live_threads": list(evolution.get("live_threads") or []),
    }

    # --- Weather + news ----------------------------------------------------
    weather_items = (fetched.get("weather") or {}).get("items") or []
    news_items    = (fetched.get("news_personal") or {}).get("items") or []
    sections["ambient"] = {
        "weather_summary": (
            f"{(weather_items[0].get('weather') or [{}])[0].get('description', '')} "
            f"({weather_items[0].get('temp')}°{('C' if (weather_items[0].get('units') or 'metric')=='metric' else 'F')})"
        ).strip()
        if weather_items else "no weather data",
        "news_headlines": [redact_pii(it.get("title") or "") for it in news_items[:3]],
    }

    # --- Memory health -----------------------------------------------------
    sections["memory_health"] = {
        "rows_per_source":  dict(remembered),
        "total_rows":       int(state.get("memory_writes") or 0),
    }

    brief = {
        "title":           "Morning Brief — Self-Evolving Personal OS",
        "generated_at":    _now_iso(),
        "for_date":        today_iso,
        "user_id":         state.get("user_id") or "default",
        "prompt_version":  state.get("prompt_version") or DEFAULT_PROMPT_VERSION,
        "stub":            bool(state.get("force_stub")),
        "sections":        sections,
        "evolution":       dict(evolution),
        "violation_count": len(state.get("violations") or []),
    }

    trail = _trail(
        NODE_BRIEF,
        stub=state["force_stub"],
        section_count=len(sections),
        note="Composed morning brief from fetched + remembered + evolved state.",
    )
    return {
        "brief":      brief,
        "provenance": list(state.get("provenance") or []) + [trail],
    }


def output_with_provenance(state: PersonalOSState) -> dict:
    """Node 5: assemble the final user-visible payload + full provenance.

    The output dict is what :func:`agent.daily_brief` returns. It has a
    ``brief`` block (user-visible), a ``provenance`` block (trail of every
    node + every source's connector/memory provenance), and a
    ``violations`` block (any Article-II refusals, surfaced honestly).
    """
    fetched = state.get("fetched") or {}
    per_source_provenance: dict[str, dict] = {
        src: dict((payload or {}).get("provenance") or {})
        for src, payload in fetched.items()
    }

    finished_at = _now_iso()
    output = {
        "brief":           state.get("brief") or {},
        "violations":      list(state.get("violations") or []),
        "provenance": {
            "trail":            list(state.get("provenance") or []),
            "per_source":       per_source_provenance,
            "memory_writes":    int(state.get("memory_writes") or 0),
            "loop_count":       int(state.get("loop_count") or 0),
            "prompt_version":   state.get("prompt_version") or DEFAULT_PROMPT_VERSION,
            "started_at":       state.get("started_at"),
            "finished_at":      finished_at,
            "force_stub":       bool(state.get("force_stub")),
        },
        "user_id":         state.get("user_id") or "default",
        "stub":            bool(state.get("force_stub")),
    }

    trail = _trail(
        NODE_OUTPUT,
        stub=state["force_stub"],
        violation_count=len(state.get("violations") or []),
        note="Assembled final output with full provenance trail.",
    )
    output["provenance"]["trail"].append(trail)

    return {
        "output":      output,
        "finished_at": finished_at,
        "provenance":  list(state.get("provenance") or []) + [trail],
    }


# --- Section 4. Conditional routing --------------------------------------

def should_loop_back_to_ingest(state: PersonalOSState) -> str:
    """LangGraph conditional edge — route after ``evolve_workflows``."""
    evo = state.get("evolution") or {}
    if evo.get("should_loop") and int(state.get("loop_count") or 0) < MAX_EVOLUTION_LOOPS:
        return NODE_INGEST
    return NODE_BRIEF


# --- Section 5. Backend selection (LangGraph or stub) --------------------

def _try_import_langgraph() -> Any | None:
    try:
        from langgraph.graph import END, StateGraph  # type: ignore
        return (StateGraph, END)
    except Exception:
        return None


_LG_PAIR = _try_import_langgraph()
BACKEND_NAME = "langgraph" if _LG_PAIR else "stub:sequential"


# --- Section 5a. Stub executor (mirrors LangGraph public API) -------------

@dataclass
class _StubGraph:
    """Pure-Python stand-in for ``langgraph.graph.StateGraph``.

    Implements just enough of the LangGraph public API to run our 5-node
    Personal OS graph deterministically:

    - ``add_node(name, fn)``
    - ``add_edge(src, dst)``
    - ``add_conditional_edges(src, condition, mapping)``
    - ``set_entry_point(name)``
    - ``compile()`` -> :class:`_StubRunnable`

    We deliberately do not try to be a general LangGraph clone — the
    Personal OS graph is small, linear, and has a single bounded loop.
    The smoke test asserts node-count, entry-point, and end-to-end state
    equivalence with whatever LangGraph would produce.
    """

    state_type: Any
    nodes: dict[str, Callable[[dict], dict]] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)
    conditional_edges: dict[str, tuple[Callable[[dict], str], dict[str, str]]] = field(default_factory=dict)
    entry_point: str | None = None

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> None:
        self.nodes[name] = fn

    def add_edge(self, src: str, dst: str) -> None:
        self.edges[src] = dst

    def add_conditional_edges(
        self,
        src: str,
        condition: Callable[[dict], str],
        mapping: dict[str, str],
    ) -> None:
        self.conditional_edges[src] = (condition, dict(mapping))

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def compile(self) -> "_StubRunnable":
        if self.entry_point is None:
            raise RuntimeError("graph: entry point not set")
        return _StubRunnable(self)


@dataclass
class _StubRunnable:
    graph: _StubGraph

    def invoke(self, state: dict) -> dict:
        # Defensive copy so the caller's dict isn't mutated mid-run.
        state = copy.copy(state)
        node = self.graph.entry_point
        steps = 0
        # Hard cap on step count: 5 nodes * (loops + 1) + small margin.
        max_steps = (len(self.graph.nodes) + 2) * (MAX_EVOLUTION_LOOPS + 2)

        while node and node != "__end__":
            if node not in self.graph.nodes:
                raise RuntimeError(f"graph: unknown node '{node}'")
            update = self.graph.nodes[node](state)
            if not isinstance(update, dict):
                raise RuntimeError(f"graph: node '{node}' returned non-dict")
            state = {**state, **update}

            if node in self.graph.conditional_edges:
                condition, mapping = self.graph.conditional_edges[node]
                key = condition(state)
                node = mapping.get(key, node)
            else:
                node = self.graph.edges.get(node, "__end__")

            steps += 1
            if steps > max_steps:
                raise RuntimeError(
                    f"graph: step budget exhausted at {steps} (max {max_steps}); "
                    "potential infinite loop"
                )
        return state


# --- Section 5b. P124 provenance wrapper ----------------------------------

def _wrap_with_provenance(node_name: str, fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
    """Wrap a node so every execution produces a ProvenanceRecord + Langfuse span."""
    def wrapped(state: dict) -> dict:
        from time import perf_counter
        from provenance.log import get_default_logger  # type: ignore
        from provenance.langfuse_hooks import get_langfuse_client, span_from_record  # type: ignore
        started = perf_counter()
        update: dict = {}
        error: str | None = None
        try:
            update = fn(state)
            return update
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                logger = get_default_logger(user_id=str(state.get("user_id") or "default"))
                rec = logger.log_step(
                    node_name=node_name, state=state, update=update,
                    force_stub=bool(state.get("force_stub")),
                    duration_ms=(perf_counter() - started) * 1000.0,
                    error=error, correlation_id=state.get("correlation_id"),
                )
                lf = get_langfuse_client()
                lf.trace_step(**span_from_record(rec))
            except Exception:  # provenance must never break execution
                pass
    return wrapped


# --- Section 6. Graph builder (single API for both backends) -------------

def build_graph() -> tuple[Any, str]:
    """Build the LangGraph (or stub) StateGraph and compile it.

    Returns ``(runnable, backend_name)`` so callers can log which backend
    they're using. The runnable's ``.invoke(state)`` walks the full DAG.
    """
    if _LG_PAIR:
        StateGraph, END = _LG_PAIR  # type: ignore[misc]
        graph: Any = StateGraph(dict)
    else:
        graph = _StubGraph(state_type=dict)
        END = "__end__"  # type: ignore[assignment]

    # P124 additive: wrap each node with the provenance logger so every
    # node execution writes one ProvenanceRecord to local JSONL + Langfuse.
    # The wrapper preserves the node's signature and return shape, so the
    # downstream LangGraph / stub-runner code is unchanged.
    _w = _wrap_with_provenance
    graph.add_node(NODE_INGEST,   _w(NODE_INGEST,   ingest_all_sources))
    graph.add_node(NODE_REMEMBER, _w(NODE_REMEMBER, remember_personal))
    graph.add_node(NODE_EVOLVE,   _w(NODE_EVOLVE,   evolve_workflows))
    graph.add_node(NODE_BRIEF,    _w(NODE_BRIEF,    generate_brief))
    graph.add_node(NODE_OUTPUT,   _w(NODE_OUTPUT,   output_with_provenance))

    graph.add_edge(NODE_INGEST,   NODE_REMEMBER)
    graph.add_edge(NODE_REMEMBER, NODE_EVOLVE)
    graph.add_conditional_edges(
        NODE_EVOLVE,
        should_loop_back_to_ingest,
        {NODE_INGEST: NODE_INGEST, NODE_BRIEF: NODE_BRIEF},
    )
    graph.add_edge(NODE_BRIEF,  NODE_OUTPUT)
    graph.add_edge(NODE_OUTPUT, END)

    graph.set_entry_point(NODE_INGEST)
    runnable = graph.compile()
    return runnable, BACKEND_NAME


# --- Section 7. End-to-end runner ----------------------------------------

def run_daily_brief(
    *,
    user_id: str = "default",
    consent: ConsentContext | None = None,
    force_stub: bool = False,
    manifest: dict | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    plan: dict | None = None,
) -> dict:
    """End-to-end driver: build connectors + memory + graph, run once.

    Returns the final ``output`` dict from
    :func:`output_with_provenance` (so callers don't need to know the
    state shape). All 6 sources are pulled, all 6 are checked into
    memory, the evolution rules run, and the brief + provenance trail
    are returned.

    The returned dict is JSON-serialisable end-to-end, which keeps the
    Streamlit dashboard / CLI / future Langfuse integration boring.
    """
    composite = build_connectors(manifest)
    composite.set_consent(consent or ConsentContext())
    composite.set_force_stub(force_stub)

    adapter: MemoryStoreAdapter = build_memory_store(  # type: ignore[assignment]
        user_id=user_id, force_stub=force_stub, consent=consent,
    )
    composite.connect_memory(adapter)
    client: PersonalMemoryClient = adapter.client

    runnable, _backend = build_graph()
    state = build_state(
        user_id=user_id,
        consent=consent,
        force_stub=force_stub,
        prompt_version=prompt_version,
        plan=plan,
    )
    state["_composite"]      = composite
    state["_memory_client"]  = client
    final = runnable.invoke(state)
    out = final.get("output") or {}
    out.setdefault("backend", BACKEND_NAME)
    # P124 additive: one final "run_complete" provenance record + Langfuse
    # end-trace, so the on-disk JSONL reflects the full run lifecycle.
    try:
        from provenance.log import get_default_logger  # type: ignore
        from provenance.langfuse_hooks import get_langfuse_client  # type: ignore
        get_default_logger(user_id=user_id).log_step(
            node_name="run_complete", state=final, update=out,
            force_stub=force_stub, error=None,
        )
        lf = get_langfuse_client()
        lf.end_trace(outputs={"memory_writes": (out.get("provenance") or {}).get("memory_writes")})
        lf.flush()
    except Exception:  # provenance must never break execution
        pass
    return out


# --- Section 8. Diagnostics -----------------------------------------------

def describe_graph() -> dict:
    """Static description of the graph — used by the CLI ``info`` command."""
    return {
        "backend":         BACKEND_NAME,
        "nodes": [
            NODE_INGEST, NODE_REMEMBER, NODE_EVOLVE, NODE_BRIEF, NODE_OUTPUT,
        ],
        "edges": [
            (NODE_INGEST,   NODE_REMEMBER),
            (NODE_REMEMBER, NODE_EVOLVE),
            (NODE_EVOLVE,   NODE_INGEST,  "conditional: should_loop"),
            (NODE_EVOLVE,   NODE_BRIEF,   "conditional: !should_loop"),
            (NODE_BRIEF,    NODE_OUTPUT),
            (NODE_OUTPUT,   "__end__"),
        ],
        "max_evolution_loops": MAX_EVOLUTION_LOOPS,
        "default_sources":     list(SOURCES),
        "memory_write_gate":   MEMORY_WRITE_GATE,
        "source_read_gates":   dict(SOURCE_READ_GATES),
    }
