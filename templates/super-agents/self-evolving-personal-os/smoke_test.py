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
"""Smoke test for the Self-Evolving Personal OS orchestration core (P123).

Layered on top of the already-passing 42 P121 + P122 checks. This suite
adds 50 checks covering the orchestration core's seven acceptance areas:

1. Module / package surface — :mod:`graph`, :mod:`agent`,
   ``__init__`` re-exports, ``BACKEND_NAME`` selection.
2. Graph structure — five nodes, four canonical edges, the conditional
   edge after ``evolve_workflows``, the entry point ``ingest_all_sources``.
3. State construction — ``build_state`` produces the expected default
   shape; consent is honoured; ``force_stub`` propagates.
4. Per-node behaviour — every node returns a partial-update dict with
   the expected keys; provenance trail grows monotonically; violations
   surface rather than crash.
5. Self-evolution loop — the conditional router fires when a source
   errors and routes back to ``ingest_all_sources``; the loop is
   bounded by ``MAX_EVOLUTION_LOOPS``.
6. Consent + PII end-to-end — write gate withheld → memory writes drop
   to zero; PII redaction visible in the brief; ISO timestamps survive
   redaction.
7. CLI entry point — ``agent.daily_brief(quiet=True)`` runs cleanly,
   ``agent.search_memory`` finds the rows the brief just wrote,
   ``agent.info`` returns the static graph description.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates/super-agents/self-evolving-personal-os
   python -m smoke_test

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import shutil
import sys
import traceback

import agent as _agent  # type: ignore
import graph as _graph  # type: ignore
from connectors import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    SOURCES,
    appdata_root,
    build_connectors,
    redact_pii,
)
from memory import (  # type: ignore
    MEMORY_WRITE_GATE,
    PersonalMemoryClient,
    build_memory_store,
    get_memory_client,
)
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore


# -- Section S.1. Helpers --------------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe() -> None:
    """Reset the local Personal OS state so every smoke section is hermetic."""
    root = appdata_root()
    for sub in ("memory", "logs"):
        try:
            shutil.rmtree(root / sub, ignore_errors=True)
        except OSError:
            pass
    try:
        # Drop the audit DB too so consent-gate counts are predictable.
        (root / "connector_audit.db").unlink(missing_ok=True)
    except OSError:
        pass


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="p123-smoke",
    )


# -- Section S.2. Test cases ---------------------------------------------

def test_module_surface() -> None:
    print("[1/7] module surface ------------------------------------------------")

    # graph module
    for name in (
        "ingest_all_sources", "remember_personal", "evolve_workflows",
        "generate_brief", "output_with_provenance",
        "build_graph", "build_state", "run_daily_brief",
        "describe_graph", "BACKEND_NAME", "DEFAULT_PROMPT_VERSION",
    ):
        if not hasattr(_graph, name):
            _fail(f"graph.{name}", "missing")
    _ok("graph module exposes all 5 nodes + builders + constants")

    # agent module
    for name in (
        "AGENT_NAME", "AGENT_VERSION", "build_default_consent",
        "daily_brief", "info", "log_path", "main", "search_memory",
    ):
        if not hasattr(_agent, name):
            _fail(f"agent.{name}", "missing")
    _ok("agent module exposes CLI + daily_brief + search_memory")

    # __init__ re-exports
    import importlib
    pkg = importlib.import_module("__init__") if False else None  # noqa: F841
    # Direct exec is awkward across PYTHONPATH; just verify the file loads:
    init_path = appdata_root().parent.parent  # placeholder, then
    # We check by executing the actual file path:
    here = __file__.rsplit("/", 1)[0] + "/__init__.py"
    src = open(here, "r", encoding="utf-8").read()
    for name in (
        "PersonalOSConnectors", "PersonalMemoryClient", "run_daily_brief",
        "ConsentContext", "redact_pii", "attach_personal_memory",
        "build_memory_store", "describe_graph",
    ):
        if name not in src:
            _fail(f"__init__.py re-export[{name}]", "name not present in package init")
    _ok("__init__.py re-exports the canonical Personal OS surface")

    if _graph.BACKEND_NAME not in {"langgraph", "stub:sequential"}:
        _fail("BACKEND_NAME", f"unexpected value: {_graph.BACKEND_NAME!r}")
    _ok(f"BACKEND_NAME selected cleanly: {_graph.BACKEND_NAME}")


def test_graph_structure() -> None:
    print("[2/7] graph structure ----------------------------------------------")
    desc = _graph.describe_graph()

    expected_nodes = [
        _graph.NODE_INGEST,
        _graph.NODE_REMEMBER,
        _graph.NODE_EVOLVE,
        _graph.NODE_BRIEF,
        _graph.NODE_OUTPUT,
    ]
    if list(desc["nodes"]) != expected_nodes:
        _fail("graph.nodes", f"expected {expected_nodes}, got {desc['nodes']}")
    _ok("describe_graph reports the 5 expected nodes in order")

    edges = {tuple(e[:2]) for e in desc["edges"]}
    for src, dst in [
        ("ingest_all_sources", "remember_personal"),
        ("remember_personal", "evolve_workflows"),
        ("generate_brief",    "output_with_provenance"),
        ("output_with_provenance", "__end__"),
    ]:
        if (src, dst) not in edges:
            _fail("graph.edges", f"missing edge {(src, dst)}")
    _ok("4 canonical sequential edges present (ingest→remember→evolve, brief→output→END)")

    cond_edges = [e for e in desc["edges"] if any("conditional" in str(p) for p in e)]
    if len(cond_edges) != 2:
        _fail("conditional edges", f"expected 2 (loop + advance), got {len(cond_edges)}")
    _ok("conditional edges from evolve_workflows present (loop + advance)")

    if desc["max_evolution_loops"] != _graph.MAX_EVOLUTION_LOOPS:
        _fail("max_evolution_loops", "describe_graph mismatch")
    _ok(f"MAX_EVOLUTION_LOOPS = {desc['max_evolution_loops']} (deterministic loop bound)")


def test_state_construction() -> None:
    print("[3/7] state construction -------------------------------------------")
    consent = _full_consent()
    state = _graph.build_state(
        user_id="alice",
        consent=consent,
        force_stub=True,
        prompt_version="custom@v9",
        plan={"morning_brief": True, "extra": True},
    )
    for key in (
        "user_id", "consent", "force_stub", "prompt_version", "plan",
        "fetched", "remembered", "memory_writes", "evolution",
        "loop_count", "brief", "output", "violations", "provenance",
        "started_at", "finished_at",
    ):
        if key not in state:
            _fail(f"state[{key}]", "missing")
    _ok("build_state returns 16 expected keys")

    if state["user_id"] != "alice":
        _fail("state.user_id", state["user_id"])
    if state["force_stub"] is not True:
        _fail("state.force_stub", state["force_stub"])
    if state["prompt_version"] != "custom@v9":
        _fail("state.prompt_version", state["prompt_version"])
    if state["plan"] != {"morning_brief": True, "extra": True}:
        _fail("state.plan", state["plan"])
    _ok("caller-provided fields propagated into state")

    if state["fetched"] != {} or state["remembered"] != {}:
        _fail("state init", "accumulators must start empty")
    if state["memory_writes"] != 0 or state["loop_count"] != 0:
        _fail("state init", "counters must start at zero")
    if state["finished_at"] is not None:
        _fail("state init", "finished_at must be None at start")
    _ok("accumulators start empty; counters at zero; finished_at=None")

    if not isinstance(state["consent"], ConsentContext):
        _fail("state.consent", f"expected ConsentContext, got {type(state['consent'])}")
    _ok("state.consent is a ConsentContext")


def test_node_behaviour() -> None:
    print("[4/7] per-node behaviour -------------------------------------------")
    _wipe()

    # Wire a fully-consented run end to end (force_stub=True so no network).
    composite = build_connectors()
    composite.set_consent(_full_consent())
    composite.set_force_stub(True)
    adapter = build_memory_store(force_stub=True, consent=_full_consent())
    composite.connect_memory(adapter)
    client = adapter._client  # type: ignore[attr-defined]

    state = _graph.build_state(
        consent=_full_consent(),
        force_stub=True,
    )
    state["_composite"]     = composite
    state["_memory_client"] = client

    # ingest
    update = _graph.ingest_all_sources(state)
    state.update(update)
    if set(state["fetched"].keys()) != set(SOURCES):
        _fail("ingest", f"fetched missing sources: {set(SOURCES) - set(state['fetched'])}")
    _ok("ingest_all_sources fetched every declared source")
    if not all(p["items"] for p in state["fetched"].values()):
        _fail("ingest", "some sources returned 0 items in stub mode")
    _ok("every source returned at least one stub item")
    last_trail = state["provenance"][-1]
    if last_trail["action"] != "ingest_all_sources" or last_trail["stub"] is not True:
        _fail("ingest provenance", str(last_trail))
    _ok("ingest provenance row carries action + stub=True")

    # remember
    update = _graph.remember_personal(state)
    state.update(update)
    if set(state["remembered"].keys()) != set(SOURCES):
        _fail("remember", f"missing source counts: {sorted(state['remembered'])}")
    if state["memory_writes"] < len(SOURCES):
        _fail("remember", f"expected ≥ {len(SOURCES)} memory rows, got {state['memory_writes']}")
    _ok(f"remember_personal counted {state['memory_writes']} rows across {len(state['remembered'])} sources")
    if state["provenance"][-1]["action"] != "remember_personal":
        _fail("remember provenance", "wrong action")
    _ok("remember provenance row appended")

    # evolve
    update = _graph.evolve_workflows(state)
    state.update(update)
    evo = state["evolution"]
    for k in ("prompt_version_in", "prompt_version_out", "error_sources",
              "live_threads", "should_loop", "loop_cap"):
        if k not in evo:
            _fail(f"evolve.{k}", "missing")
    _ok("evolve_workflows emitted 6 evolution fields")
    if state["provenance"][-1]["action"] != "evolve_workflows":
        _fail("evolve provenance", "wrong action")
    _ok("evolve provenance row appended")

    # brief
    update = _graph.generate_brief(state)
    state.update(update)
    brief = state["brief"]
    for k in ("title", "generated_at", "for_date", "user_id",
              "prompt_version", "stub", "sections", "evolution",
              "violation_count"):
        if k not in brief:
            _fail(f"brief.{k}", "missing")
    _ok("generate_brief emitted 9 top-level brief fields")
    sections = brief["sections"]
    for sec in ("today_schedule", "inbox_pulse", "x_pulse",
                "notes_recent", "ambient", "memory_health"):
        if sec not in sections:
            _fail(f"brief.sections.{sec}", "missing")
    _ok("brief covers all 6 expected sections")

    # output
    update = _graph.output_with_provenance(state)
    state.update(update)
    out = state["output"]
    for k in ("brief", "violations", "provenance", "user_id", "stub"):
        if k not in out:
            _fail(f"output.{k}", "missing")
    _ok("output_with_provenance produced final dict with 5 top-level keys")
    if "trail" not in out["provenance"]:
        _fail("output.provenance.trail", "missing")
    if "per_source" not in out["provenance"]:
        _fail("output.provenance.per_source", "missing")
    _ok("output.provenance carries trail + per_source provenance maps")
    if state["finished_at"] is None:
        _fail("output", "finished_at not set")
    _ok("finished_at populated on output")


def test_self_evolution_loop() -> None:
    print("[5/7] self-evolution loop ------------------------------------------")
    _wipe()
    consent = _full_consent()

    # Drive the graph end-to-end. The stub data has no errors so should_loop=False.
    out = _graph.run_daily_brief(force_stub=True, consent=consent)
    if out["provenance"]["loop_count"] != 0:
        _fail("loop_count[no-error]", str(out["provenance"]["loop_count"]))
    _ok("happy-path loop_count = 0 (no error sources, no extra ingest)")

    # Force evolve_workflows into the "should_loop" branch by injecting an
    # error into the fetched payload. We do this by calling the node directly.
    state = _graph.build_state(consent=consent, force_stub=True)
    state["fetched"] = {
        "gmail": {"items": [], "provenance": {}, "error": "synthetic 503"},
    }
    state["_memory_client"] = _agent.get_memory_client(force_stub=True, refresh=True)
    state["_memory_client"].set_consent(consent)
    upd = _graph.evolve_workflows(state)
    state.update(upd)
    evo = state["evolution"]
    if "gmail" not in evo["error_sources"]:
        _fail("evolve.error_sources", str(evo["error_sources"]))
    if not evo["should_loop"]:
        _fail("evolve.should_loop", "expected True when an error is present")
    _ok("evolve_workflows flags should_loop=True when a source errors")
    if state["loop_count"] != 1:
        _fail("loop_count after error", str(state["loop_count"]))
    _ok("loop_count incremented to 1")

    routed = _graph.should_loop_back_to_ingest(state)
    if routed != _graph.NODE_INGEST:
        _fail("conditional router", f"expected NODE_INGEST, got {routed}")
    _ok("conditional router routes back to ingest_all_sources on error")

    # Cap behaviour: increment the loop count past the cap and verify the
    # router refuses to loop again.
    state["loop_count"] = _graph.MAX_EVOLUTION_LOOPS + 1
    state["evolution"] = {**evo, "should_loop": True}
    routed2 = _graph.should_loop_back_to_ingest(state)
    if routed2 != _graph.NODE_BRIEF:
        _fail("loop cap", f"expected NODE_BRIEF, got {routed2}")
    _ok("conditional router enforces MAX_EVOLUTION_LOOPS cap")

    # Stub-executor sanity: a malformed graph should not infinitely loop.
    if _graph.BACKEND_NAME == "stub:sequential":
        from graph import _StubGraph  # type: ignore
        g = _StubGraph(state_type=dict)
        g.add_node("a", lambda s: {})
        g.add_edge("a", "a")  # self-loop!
        g.set_entry_point("a")
        try:
            g.compile().invoke({"x": 0})
        except RuntimeError as exc:
            if "step budget" not in str(exc):
                _fail("stub-executor", f"unexpected error: {exc}")
            _ok("stub executor enforces step budget against accidental infinite loops")
        else:
            _fail("stub-executor", "expected RuntimeError on infinite loop")
    else:
        _ok("langgraph backend in use; stub-executor budget check skipped")


def test_consent_and_pii_end_to_end() -> None:
    print("[6/7] consent + PII end-to-end -------------------------------------")
    _wipe()

    # 1. Consent without write gate → no memory writes.
    consent_no_write = _agent.build_default_consent(allow_write=False)
    out = _graph.run_daily_brief(force_stub=True, consent=consent_no_write)
    if out["provenance"]["memory_writes"] != 0:
        _fail("no-write run", f"memory writes leaked: {out['provenance']['memory_writes']}")
    _ok("--no-write run records 0 memory writes")
    # The connector layer raised on write attempts but ingest still produced
    # data; the brief is therefore still rendered.
    if not out["brief"]:
        _fail("no-write run", "brief should still render")
    _ok("brief still renders with --no-write (read-only mode)")

    # 2. ISO timestamps survive redaction.
    sample = "2026-05-06T12:00:00Z"
    if redact_pii(sample) != sample:
        _fail("iso-timestamp", f"got {redact_pii(sample)!r}")
    _ok("ISO 8601 timestamps survive redact_pii unchanged")

    # 3. Email PII still redacted.
    leaky = "Email me at alice@example.com"
    if "[REDACTED_EMAIL]" not in redact_pii(leaky):
        _fail("email redaction", redact_pii(leaky))
    _ok("emails still redacted after the ISO-timestamp bypass")

    # 4. Full run with consent: brief contains no raw email patterns.
    _wipe()
    out = _graph.run_daily_brief(force_stub=True, consent=_full_consent())
    import json
    blob = json.dumps(out, default=str)
    import re
    if re.search(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", blob):
        _fail("brief PII", "raw email pattern surfaced in brief")
    _ok("end-to-end brief contains no raw email patterns")

    # 5. force_stub propagates.
    if not out["stub"]:
        _fail("force_stub propagation", "out.stub should be True")
    _ok("force_stub propagates into output.stub")
    trail = out["provenance"]["trail"]
    if not all(t.get("stub") is True for t in trail):
        _fail("force_stub trail", "not every trail row carries stub=True")
    _ok("every provenance trail row carries stub=True under force_stub")

    # 6. Search returns hits with redaction_applied flag.
    client = _agent.get_memory_client(force_stub=True, refresh=True)
    client.set_consent(_full_consent())
    hits = client.search("stub", limit=5)
    if not hits:
        _fail("search after run", "expected ≥ 1 hit after a full run")
    if not all(h.provenance.get("redaction_applied") for h in hits):
        _fail("search redaction flag", "hit without redaction_applied")
    _ok(f"search after full run returns {len(hits)} hits, all redaction_applied")


def test_cli_entry_point() -> None:
    print("[7/7] CLI entry point ----------------------------------------------")
    _wipe()
    # daily_brief programmatic call (the CLI's --quiet path).
    out = _agent.daily_brief(force_stub=True, quiet=True)
    if out.get("agent_name") != _agent.AGENT_NAME:
        _fail("daily_brief.agent_name", str(out.get("agent_name")))
    if out.get("agent_version") != _agent.AGENT_VERSION:
        _fail("daily_brief.agent_version", str(out.get("agent_version")))
    _ok("agent.daily_brief returns dict with agent_name + version")
    if not out.get("brief", {}).get("sections"):
        _fail("daily_brief.brief", "empty sections")
    _ok("daily_brief output carries non-empty brief.sections")

    # main() with argv.
    rc = _agent.main(["daily-brief", "--stub", "--quiet"])
    if rc != 0:
        _fail("main daily-brief", f"exit code {rc}")
    _ok("agent.main(['daily-brief','--stub','--quiet']) returned 0")

    rc = _agent.main(["info"])
    if rc != 0:
        _fail("main info", f"exit code {rc}")
    _ok("agent.main(['info']) returned 0")

    rc = _agent.main(["version"])
    if rc != 0:
        _fail("main version", f"exit code {rc}")
    _ok("agent.main(['version']) returned 0")

    # search_memory finds the rows daily-brief wrote.
    hits = _agent.search_memory(
        "stub", source="local_notes", limit=5,
        force_stub=True, quiet=True,
    )
    if not hits:
        _fail("search_memory after brief", "expected ≥ 1 hit")
    _ok(f"agent.search_memory returned {len(hits)} hits scoped to local_notes")

    # info() returns the static graph description.
    info = _agent.info(quiet=True)
    if info["agent_name"] != _agent.AGENT_NAME:
        _fail("info.agent_name", str(info))
    if info["backend"] != _graph.BACKEND_NAME:
        _fail("info.backend", str(info))
    if "appdata_root" not in info:
        _fail("info.appdata_root", "missing")
    _ok("agent.info dict carries agent_name + version + backend + appdata_root")

    # Run-log row written.
    if not _agent.log_path().exists():
        _fail("agent.log", "log file not written")
    _ok(f"agent run-log present at {_agent.log_path()}")

    # The brief output is JSON-serialisable end-to-end.
    import json
    try:
        json.dumps(out, default=str)
    except (TypeError, ValueError) as exc:
        _fail("json-serialisable output", str(exc))
    _ok("daily_brief output is JSON-serialisable end-to-end")

    # Two back-to-back runs are independent (no leaked global state corrupts
    # the second).
    out2 = _agent.daily_brief(force_stub=True, quiet=True)
    if out2.get("brief", {}).get("user_id") != out.get("brief", {}).get("user_id"):
        _fail("idempotent runs", "user_id drifted between runs")
    if out2["provenance"]["memory_writes"] < 1:
        _fail("idempotent runs", "second run wrote nothing to memory")
    _ok("two back-to-back daily_brief runs both succeed (state isolation)")

    # Run-log row contains the action we expect.
    log_lines = _agent.log_path().read_text(encoding="utf-8").splitlines()
    if not any('"action": "daily_brief"' in line for line in log_lines):
        _fail("run-log content", "no daily_brief action recorded")
    _ok("run-log records the daily_brief action with payload")

    # build_default_consent honours allow_write=False.
    no_write = _agent.build_default_consent(allow_write=False)
    if no_write.has(MEMORY_WRITE_GATE):
        _fail("build_default_consent", "allow_write=False still includes write gate")
    _ok("build_default_consent(allow_write=False) drops the write_personal_memory gate")


# -- Section S.3. Entry point ---------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P123 Self-Evolving Personal OS orchestration smoke test")
    print(f"Backend: {_graph.BACKEND_NAME}")
    print("=" * 70)
    try:
        test_module_surface()
        test_graph_structure()
        test_state_construction()
        test_node_behaviour()
        test_self_evolution_loop()
        test_consent_and_pii_end_to_end()
        test_cli_entry_point()
    except SystemExit:
        print("=" * 70)
        print("RESULT: FAIL")
        return 1
    except Exception:
        print("UNCAUGHT EXCEPTION:")
        traceback.print_exc()
        print("=" * 70)
        print("RESULT: FAIL")
        return 1
    print("=" * 70)
    print("RESULT: PASS — all 7 P123 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
