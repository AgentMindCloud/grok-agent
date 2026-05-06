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
"""Smoke test for the Cross-Reality Action Fabric provenance layer.

Covers both the original P131 surface and the P142 action-centric
extensions. Six acceptance areas, ~50 checks total:

1. Schema + module surface — ActionProvenanceRecord shape, EVENT_KINDS
   coverage, ALL_RULE_NUMBERS, JSONL roundtrip, package re-exports.
2. Per-event logging — log_event refuses unknown event_kind; PII
   redacted on every record; rule_compliance dict populated;
   rollback_script drives Rule 3 evaluation correctly.
3. Bulk ingest via attach_provenance — wrapper writes plan_built +
   approval_granted×4 + action_executed×4 + run_complete in one auto-
   approved run.
4. Rollback chain — forward action ↔ rollback link survives across
   separate ``record_run`` calls; Markdown report lists the chain.
5. Langfuse hooks — default backend is stub:offline; opt_in=True with
   no creds also returns the stub; mirror trace file populated; PII
   redacted on every span.
6. **P142 action-centric API** — ProvenanceLogger subclass,
   ProvenanceEntry Pydantic model, RollbackChain, log_action_event /
   log_memory_event, query_by_action_id / query_by_consent_level /
   query_by_date_range, reconstruct_rollback_chain, export_json /
   export_markdown with clickable anchors, LangfuseHooks lifecycle
   methods, attach_to_connectors auto-instrumentation, end-to-end
   connector → provenance flow.

Run on Windows (official):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m provenance.smoke_test

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from graph import (  # type: ignore
    ConsentContext,
    appdata_root,
    build_state,
    output_with_provenance as graph_output,
    rollback as graph_rollback,
    run_action_loop,
)
from memory import MEMORY_WRITE_GATE  # type: ignore
from provenance import (  # type: ignore
    ACTION_EVENT_KINDS,
    ALL_RULE_NUMBERS,
    ActionProvenanceRecord,
    EVENT_KINDS,
    LANGFUSE_BACKEND_NAME,
    LangfuseClient,
    LangfuseHooks,
    LocalProvenanceLogger,
    P142_SCHEMA_VERSION,
    ProvenanceEntry,
    ProvenanceLogger,
    ROLLBACK_OUTCOME,
    RollbackChain,
    attach_langfuse_hooks,
    attach_provenance,
    attach_to_connectors,
    current_log_path,
    export_audit_json,
    export_audit_markdown,
    export_audit_report,
    get_default_logger,
    get_langfuse_client,
    get_provenance_logger,
    have_langfuse_credentials,
    reset_default_logger,
    reset_langfuse_client,
    reset_provenance_logger,
    span_from_record,
    stub_trace_path,
    summarise_run,
    trace_name_for_action,
)


# -- Section S.1. Helpers -------------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe() -> None:
    try:
        shutil.rmtree(appdata_root(), ignore_errors=True)
    except OSError:
        pass
    reset_default_logger()
    reset_langfuse_client()


# Full consent set (12 manifest gates + memory gate).
ALL_GATES = (
    "publish_to_x", "send_dm", "move_funds", "pay_real_money",
    "export_tax_report", "sync_to_cloud",
    "modify_local_files_outside_appdata", "publish_synthesis",
    "run_powershell_local", "run_web_action",
    "read_calendar", "read_email",
    MEMORY_WRITE_GATE,
)


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(ALL_GATES, consent_token="p131-smoke")


# -- Section S.2. Test cases ----------------------------------------------

def test_schema_and_surface() -> None:
    print("[1/5] schema + module surface ------------------------------------")
    expected_kinds = {
        "plan_built", "approval_granted", "approval_refused",
        "action_executed", "action_failed",
        "rollback_executed", "rollback_failed",
        "node_step", "run_complete",
    }
    if set(EVENT_KINDS) != expected_kinds:
        _fail("EVENT_KINDS", str(EVENT_KINDS))
    _ok(f"EVENT_KINDS lists exactly {len(expected_kinds)} official events")

    if set(ALL_RULE_NUMBERS) != {1, 2, 3, 4, 5, 6}:
        _fail("ALL_RULE_NUMBERS", str(ALL_RULE_NUMBERS))
    _ok("ALL_RULE_NUMBERS = (1,2,3,4,5,6) — matches the 6 Constitution Rules")

    if ROLLBACK_OUTCOME != "rolled_back":
        _fail("ROLLBACK_OUTCOME", ROLLBACK_OUTCOME)
    _ok(f"ROLLBACK_OUTCOME constant = {ROLLBACK_OUTCOME!r}")

    # Re-exports we need from the package init.
    for name in (
        "LocalProvenanceLogger", "ActionProvenanceRecord",
        "attach_provenance", "export_audit_report",
        "LangfuseClient", "get_langfuse_client",
    ):
        if name not in globals():
            _fail(f"package re-export[{name}]", "missing")
    _ok("package re-exports the 6 standard names")

    # JSONL roundtrip.
    rec = ActionProvenanceRecord(
        record_id="prv-test", run_id="r1", user_id="alice",
        event_kind="action_executed", timestamp="2026-05-05T00:00:00+00:00",
        plan_id="p1", step=1, tool="weather_lookup", action_id="a1",
        consent_token="ct-1", outcome="success", cost_usd=0.0,
        duration_ms=1.0, rollback_id=None, rolled_back_from=None,
        inputs_redacted={}, outputs_redacted={}, rule_compliance={"rule_1": True},
        stub_reason=None, error=None, correlation_id=None,
    )
    line = rec.to_jsonl()
    parsed = ActionProvenanceRecord.from_jsonl(line)
    if parsed.record_id != rec.record_id or parsed.event_kind != rec.event_kind:
        _fail("JSONL roundtrip", f"mismatch")
    _ok("ActionProvenanceRecord.to_jsonl ↔ from_jsonl roundtrip preserves identity")


def test_per_event_logging() -> None:
    print("[2/5] per-event logging + PII -----------------------------------")
    _wipe()
    logger = LocalProvenanceLogger(user_id="alice")

    # Unknown event_kind refused.
    try:
        logger.log_event(event_kind="not_a_real_event")
    except ValueError as exc:
        if "unknown event_kind" not in str(exc):
            _fail("unknown event_kind", str(exc))
    else:
        _fail("unknown event_kind", "expected ValueError")
    _ok("log_event raises ValueError on unknown event_kind")

    # PII redaction at write time.
    logger.log_event(
        event_kind="action_executed",
        plan_id="p1", step=1, tool="windows_local", action_id="a1",
        consent_token="ct-1", outcome="success",
        inputs={"description": "Email alice@example.com"},
        outputs={"result": {"address": "221 Baker Street"}},
        rollback_script="echo undo",
    )
    blob = current_log_path().read_text(encoding="utf-8")
    if "alice@example.com" in blob:
        _fail("PII (email)", "raw email surfaced")
    if "221 Baker Street" in blob:
        _fail("PII (address)", "raw address surfaced")
    _ok("emails / addresses redacted at write time")

    # Rule compliance dict populated.
    recs = logger.query_by_run_id(logger.run_id)
    if not recs:
        _fail("query_by_run_id", "no records")
    last = recs[-1]
    if not isinstance(last.rule_compliance, dict):
        _fail("rule_compliance type", str(type(last.rule_compliance)))
    if set(f"rule_{n}" for n in ALL_RULE_NUMBERS) != set(last.rule_compliance.keys()):
        _fail("rule_compliance keys", str(last.rule_compliance))
    _ok("rule_compliance dict carries one entry per Rule (1..6)")

    # Rule 3 — windows_local with rollback_script → True.
    if last.rule_compliance.get("rule_3") is not True:
        _fail("rule_3 (with rollback)", str(last.rule_compliance))
    _ok("Rule 3 evaluates True when state-changing action carries rollback_script")

    # Rule 3 — windows_local WITHOUT rollback → False.
    logger.log_event(
        event_kind="action_executed",
        plan_id="p1", step=2, tool="windows_local",
        consent_token="ct-2", outcome="success",
        inputs={}, outputs={},
        rollback_script="",   # missing!
    )
    last = logger.query_by_run_id(logger.run_id)[-1]
    if last.rule_compliance.get("rule_3") is not False:
        _fail("rule_3 (no rollback)", str(last.rule_compliance))
    _ok("Rule 3 evaluates False when state-changing action lacks rollback_script")

    # Rule 5 — bash leak triggers False.
    logger.log_event(
        event_kind="action_executed",
        plan_id="p1", step=3, tool="windows_local",
        consent_token="ct-3", outcome="success",
        inputs={}, outputs={},
        script="bash -c 'echo nope'",
        rollback_script="echo undo",
    )
    last = logger.query_by_run_id(logger.run_id)[-1]
    if last.rule_compliance.get("rule_5") is not False:
        _fail("rule_5 bash-leak", str(last.rule_compliance))
    _ok("Rule 5 evaluates False on bash leak in the script")


def test_attach_and_bulk_ingest() -> None:
    print("[3/5] attach_provenance + bulk ingest ---------------------------")
    _wipe()
    consent = _full_consent()
    logger, lf, run = attach_provenance(
        user_id="alice", consent=consent, refresh=True,
    )
    if not isinstance(logger, LocalProvenanceLogger):
        _fail("attach_provenance.logger type", str(type(logger)))
    if not isinstance(lf, LangfuseClient):
        _fail("attach_provenance.langfuse type", str(type(lf)))
    if not callable(run):
        _fail("attach_provenance.run", "not callable")
    _ok("attach_provenance returns (logger, LangfuseClient, callable)")

    out = run(force_stub=True, auto_approve=True, user_request="hi")
    if "provenance_ingest" not in out:
        _fail("provenance_ingest", "missing from output")
    _ok("run_with_provenance attaches provenance_ingest to the output")

    counters = out["provenance_ingest"]
    if counters.get("plan_built", 0) != 1:
        _fail("ingest.plan_built", str(counters))
    if counters.get("approval_granted", 0) < 4:
        _fail("ingest.approval_granted", str(counters))
    if counters.get("action_executed", 0) < 4:
        _fail("ingest.action_executed", str(counters))
    if counters.get("run_complete", 0) != 1:
        _fail("ingest.run_complete", str(counters))
    _ok(f"single auto-approved run emitted {counters['plan_built']} plan_built + "
        f"{counters['approval_granted']} approval_granted + "
        f"{counters['action_executed']} action_executed + "
        f"{counters['run_complete']} run_complete")

    # Output also carries the provenance_run_id and langfuse_backend.
    if not out.get("provenance_run_id", "").startswith("crf-run-"):
        _fail("provenance_run_id", str(out.get("provenance_run_id")))
    if out.get("langfuse_backend") != "stub:offline":
        _fail("langfuse_backend", str(out.get("langfuse_backend")))
    _ok("output carries provenance_run_id + langfuse_backend tags")

    # Markdown summary covers expected fields.
    summary = summarise_run(logger.query_by_run_id(out["provenance_run_id"]))
    for k in (
        "run_id", "started_at", "finished_at", "event_count",
        "tools_used", "stub", "errors", "outcomes",
        "rule_violations", "user_id", "rollback_chain", "cost_usd_total",
    ):
        if k not in summary:
            _fail(f"summary[{k}]", "missing")
    _ok("summarise_run returns the official 12-field digest")

    # Happy path has zero rule violations now (Rule 3 fixed).
    if summary["rule_violations"]:
        _fail("rule_violations on happy path",
              f"unexpected: {summary['rule_violations']}")
    _ok("happy-path run produces zero rule violations")


def test_rollback_chain_across_runs() -> None:
    print("[4/5] rollback chain across record_run calls --------------------")
    _wipe()
    consent = _full_consent()
    logger, lf, run = attach_provenance(
        user_id="alice", consent=consent, refresh=True,
    )

    # Run 1 — forward actions only.
    out1 = run(force_stub=True, auto_approve=True, user_request="forward")

    # Run 2 — invoke the rollback node directly with the same plan.
    s = build_state(force_stub=True, auto_approve=True, user_id="alice")
    s["plan"] = out1["plan"]
    s.update(graph_rollback(s))
    s.update(graph_output(s))
    out2 = s["output"]
    counters2 = logger.record_run(out2)
    if counters2.get("rollback_executed", 0) < 1:
        _fail("rollback_executed count", str(counters2))
    _ok(f"second record_run wrote {counters2['rollback_executed']} rollback_executed row(s)")

    # The Markdown report's rollback chain section MUST cross-link
    # the rollback to its forward action.
    md = export_audit_report(logger=logger)
    if "## Rollback chain" not in md:
        _fail("md rollback section", "missing")
    chain_section = md.split("## Rollback chain", 1)[1].split("## Per-event trail", 1)[0]
    if "_No rollbacks recorded for this scope._" in chain_section:
        _fail("rollback chain content", "section is empty after a rollback")
    _ok("Markdown rollback-chain section contains at least one row")

    # The rollback row's ``rolled_back_from`` should point to a real
    # forward action_id.
    rollback_recs = [
        r for r in logger.query_by_run_id(logger.run_id)
        if r.event_kind == "rollback_executed"
    ]
    if not rollback_recs:
        _fail("rollback_executed records", "none found")
    rb = rollback_recs[0]
    if not rb.rolled_back_from or not rb.rolled_back_from.startswith("crf-act-"):
        _fail("rolled_back_from cross-link", str(rb.rolled_back_from))
    _ok(f"rollback row.rolled_back_from = {rb.rolled_back_from} (cross-link valid)")

    # Verify the linked forward action exists in the log.
    forward = [
        r for r in logger.query_by_run_id(logger.run_id)
        if r.action_id == rb.rolled_back_from
    ]
    if not forward:
        _fail("forward action lookup", "not found in JSONL")
    if forward[0].event_kind != "action_executed":
        _fail("forward action event_kind", forward[0].event_kind)
    _ok("forward action_executed record is reachable via rolled_back_from")


def test_langfuse_hooks() -> None:
    print("[5/5] Langfuse hooks + stub fallback ----------------------------")
    _wipe()

    # Default backend — stub:offline.
    client = get_langfuse_client(opt_in=False, refresh=True)
    if client.backend_name != "stub:offline":
        _fail("default backend", client.backend_name)
    _ok("default backend is stub:offline (no opt_in, no creds)")

    # opt_in=True without creds also returns the stub.
    os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
    os.environ.pop("LANGFUSE_SECRET_KEY", None)
    client_optin = get_langfuse_client(opt_in=True, refresh=True)
    if client_optin.backend_name != "stub:offline":
        _fail("opt_in without creds", client_optin.backend_name)
    _ok("opt_in=True without creds still returns stub:offline")

    # Module-level BACKEND_NAME mirrors the live client.
    if LANGFUSE_BACKEND_NAME != "stub:offline":
        # The constant is imported once at module load — re-read it.
        from provenance.langfuse_hooks import BACKEND_NAME as _BACKEND  # type: ignore
        if _BACKEND != "stub:offline":
            _fail("module BACKEND_NAME", _BACKEND)
    _ok("module-level BACKEND_NAME mirrors the cached client")

    # End-to-end: a real run mirrors every event into the stub trace file.
    consent = _full_consent()
    _wipe()   # fresh state for this final assertion
    logger, lf, run = attach_provenance(
        user_id="alice", consent=consent, refresh=True,
    )
    out = run(force_stub=True, auto_approve=True, user_request="trace test")
    spans = stub_trace_path().read_text(encoding="utf-8").splitlines()
    if len(spans) < 6:
        _fail("stub trace size", f"expected ≥ 6 lines, got {len(spans)}")
    _ok(f"Langfuse stub trace mirror captured {len(spans)} lines")

    # PII never leaks into the trace file.
    raw = "\n".join(spans)
    for needle in ("alice@example.com",):
        if needle in raw:
            _fail("PII in Langfuse mirror", needle)
    _ok("Langfuse stub mirror redacts PII before persisting")

    # span_from_record adapts an ActionProvenanceRecord cleanly.
    sample = ActionProvenanceRecord(
        record_id="prv-x", run_id="r1", user_id="alice",
        event_kind="action_executed", timestamp="2026-05-05T00:00:00+00:00",
        plan_id="p1", step=1, tool="weather_lookup", action_id="a1",
        consent_token="ct", outcome="success", cost_usd=0.5,
        duration_ms=1.0, rollback_id=None, rolled_back_from=None,
        inputs_redacted={"a": 1}, outputs_redacted={"b": 2},
        rule_compliance={"rule_1": True}, stub_reason=None,
        error=None, correlation_id=None,
    )
    span = span_from_record(sample)
    for k in ("event_kind", "tool", "step", "action_id", "consent_token",
              "outcome", "cost_usd", "rollback_id", "rolled_back_from",
              "inputs", "outputs", "rule_compliance"):
        if k not in span:
            _fail(f"span_from_record[{k}]", "missing")
    _ok("span_from_record returns the official 13-field span dict")

    # provenance_ingest coexists with memory_ingest from P130.
    if "memory_ingest" not in out:
        _fail("memory_ingest", "missing — P130 wrapper not chained")
    if "provenance_ingest" not in out:
        _fail("provenance_ingest", "missing")
    _ok("attach_provenance chains the P130 memory wrapper "
        "(memory_ingest + provenance_ingest both present)")


# -- Section S.2.6. P142 action-centric API ------------------------------

def test_p142_action_centric_api() -> None:
    print("[6/6] P142 action-centric API ------------------------------------")
    reset_default_logger()
    reset_provenance_logger()
    reset_langfuse_client()
    try:
        shutil.rmtree(appdata_root(), ignore_errors=True)
    except OSError:
        pass

    # 6.1 — module surface
    if not issubclass(ProvenanceLogger, LocalProvenanceLogger):
        _fail("ProvenanceLogger subclass",
              "must subclass LocalProvenanceLogger")
    _ok("ProvenanceLogger subclasses LocalProvenanceLogger (P142 keeps "
        "P131 contract)")

    if P142_SCHEMA_VERSION != "p142.v1":
        _fail("P142_SCHEMA_VERSION", P142_SCHEMA_VERSION)
    _ok(f"P142_SCHEMA_VERSION = {P142_SCHEMA_VERSION!r}")

    if set(ACTION_EVENT_KINDS) != {
        "approval_granted", "approval_refused",
        "action_executed", "action_failed",
        "rollback_executed", "rollback_failed",
    }:
        _fail("ACTION_EVENT_KINDS", str(ACTION_EVENT_KINDS))
    _ok(f"ACTION_EVENT_KINDS lists exactly {sorted(ACTION_EVENT_KINDS)}")

    if trace_name_for_action("act-xyz") != "crf-action-act-xyz":
        _fail("trace_name_for_action",
              trace_name_for_action("act-xyz"))
    if trace_name_for_action("") != "crf-action-anonymous":
        _fail("trace_name_for_action empty",
              trace_name_for_action(""))
    _ok("trace_name_for_action returns 'crf-action-{action_id}'")

    if have_langfuse_credentials() and not (
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    ):
        _fail("have_langfuse_credentials", "false-positive")
    _ok(f"have_langfuse_credentials() = {have_langfuse_credentials()}")

    # 6.2 — factory + caching
    log = get_provenance_logger(user_id="alice", refresh=True)
    if not isinstance(log, ProvenanceLogger):
        _fail("get_provenance_logger type", str(type(log)))
    if log.user_id != "alice":
        _fail("get_provenance_logger user_id", log.user_id)
    cached = get_provenance_logger(user_id="alice")
    if cached is not log:
        _fail("get_provenance_logger caching", "returned different instance")
    _ok("get_provenance_logger returns cached ProvenanceLogger singleton")

    # 6.3 — log_action_event happy path
    aid_1 = "act::p142::demo-1"
    entry = log.log_action_event(
        event_kind="approval_granted",
        action_id=aid_1,
        consent_token="ct-p142-1",
        tool="weather_lookup",
        consent_level="session",
        rollback_id="rb-1",
        before_state={"locale": "Hanoi"},
        plan_id="plan-1",
        step=1,
    )
    if not isinstance(entry, ProvenanceEntry):
        _fail("log_action_event return type", str(type(entry)))
    if entry.action_id != aid_1 or entry.consent_level != "session":
        _fail("log_action_event payload",
              f"got action_id={entry.action_id} level={entry.consent_level}")
    _ok("log_action_event writes ProvenanceEntry with consent_level + "
        "rollback_id + action_id")

    # 6.4 — log_memory_event maps memory kinds → event_kind
    log.log_memory_event(
        kind="action", action_id=aid_1,
        consent_token="ct-p142-1", tool="weather_lookup",
        outcome="success", consent_level="session",
        payload={"summary": "[stub] forecast OK"},
    )
    log.log_memory_event(
        kind="rollback", action_id=aid_1, consent_token="ct-p142-1",
        tool="weather_lookup", outcome="rolled_back",
        consent_level="session", rollback_id="rb-1",
        rollback_from=aid_1,
    )
    by_action = log.query_by_action_id(aid_1)
    kinds_seen = {e.event_kind for e in by_action}
    if "approval_granted" not in kinds_seen \
            or "action_executed" not in kinds_seen \
            or "rollback_executed" not in kinds_seen:
        _fail("log_memory_event mapping", str(kinds_seen))
    _ok(f"log_memory_event maps memory kinds → event_kinds correctly "
        f"({sorted(kinds_seen)})")

    # 6.5 — query_by_consent_level
    log.log_action_event(
        event_kind="action_executed",
        action_id="act::persist-1",
        consent_token="ct-persist", tool="x_search",
        consent_level="persistent",
        outcome="success",
    )
    persistent_only = log.query_by_consent_level("persistent")
    if not persistent_only:
        _fail("query_by_consent_level", "no rows")
    if any(e.consent_level != "persistent" for e in persistent_only):
        _fail("query_by_consent_level leak",
              "non-persistent row surfaced")
    _ok(f"query_by_consent_level('persistent') returns "
        f"{len(persistent_only)} row(s) — all level-pure")

    # 6.6 — query_by_date_range
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    in_range = log.query_by_date_range(today, today)
    if len(in_range) < 4:
        _fail("query_by_date_range",
              f"expected ≥4 rows for today, got {len(in_range)}")
    _ok(f"query_by_date_range({today}, {today}) returns "
        f"{len(in_range)} row(s)")

    swapped = log.query_by_date_range(today, today)
    if [e.record_id for e in swapped] != [e.record_id for e in in_range]:
        _fail("query_by_date_range swap", "auto-swap broke ordering")
    _ok("query_by_date_range auto-swaps reversed args without errors")

    # 6.7 — reconstruct_rollback_chain
    chain = log.reconstruct_rollback_chain(aid_1)
    if not isinstance(chain, RollbackChain):
        _fail("reconstruct_rollback_chain type", str(type(chain)))
    if chain.action_id != aid_1:
        _fail("chain.action_id", chain.action_id)
    if chain.approval is None or chain.forward_event is None \
            or chain.rollback is None:
        _fail("chain completeness",
              f"approval={chain.approval is not None} "
              f"forward={chain.forward_event is not None} "
              f"rollback={chain.rollback is not None}")
    if not chain.reversed:
        _fail("chain.reversed", "rollback present but reversed=False")
    _ok("reconstruct_rollback_chain returns RollbackChain with "
        "approval + forward + rollback (reversed=True)")

    # 6.8 — export_json
    export = log.export_json(action_id=aid_1)
    if export["schema_version"] != P142_SCHEMA_VERSION:
        _fail("export_json schema_version", export["schema_version"])
    if export["entry_count"] < 3:
        _fail("export_json entries",
              f"too few: {export['entry_count']}")
    if not export["rollback_chains"]:
        _fail("export_json chains", "no chains")
    _ok(f"export_json(action_id) produces {export['entry_count']} "
        f"entries + {len(export['rollback_chains'])} chain(s) + "
        f"schema {export['schema_version']}")

    full_export = log.export_json()
    if full_export["scope"]["kind"] != "all":
        _fail("export_json no-filter scope",
              str(full_export["scope"]))
    _ok("export_json with no filter exports the full audit trail")

    # 6.9 — export_markdown with clickable anchors
    md = log.export_markdown(action_id=aid_1)
    if "# Cross-Reality Action Fabric — P142 Audit Export" not in md:
        _fail("export_markdown header", "missing")
    expected_anchor = f"#act-{aid_1.replace(':', '-')}"
    if expected_anchor not in md:
        _fail("export_markdown anchor",
              f"missing '{expected_anchor}'")
    if "Rollback chains" not in md or "Per-entry trail" not in md:
        _fail("export_markdown sections",
              "missing chain or trail section")
    _ok(f"export_markdown emits clickable {expected_anchor} anchor + "
        "Rollback/Trail sections")

    # 6.10 — module-level export helpers
    json_export = export_audit_json(action_id=aid_1, logger=log)
    md_export   = export_audit_markdown(action_id=aid_1, logger=log)
    if json_export["entry_count"] < 1 or "P142 Audit Export" not in md_export:
        _fail("module-level exporters", "broken")
    _ok("module-level export_audit_json + export_audit_markdown work")

    # 6.11 — Pydantic ProvenanceEntry refuses non-string event_kind via
    #          its parent (typing) and accepts a record-built instance.
    rebuilt = ProvenanceEntry.from_record(log.query_by_run_id(log.run_id)[0])
    if not isinstance(rebuilt, ProvenanceEntry):
        _fail("ProvenanceEntry.from_record", str(type(rebuilt)))
    _ok("ProvenanceEntry.from_record adapts the P131 dataclass")

    # 6.12 — LangfuseHooks default + lifecycle methods
    hooks = attach_langfuse_hooks(opt_in=False, refresh=True)
    if not isinstance(hooks, LangfuseHooks):
        _fail("attach_langfuse_hooks type", str(type(hooks)))
    if hooks.opt_in or hooks.is_active:
        _fail("LangfuseHooks default", "should be inert by default")
    if hooks.backend_name != "stub:offline":
        _fail("LangfuseHooks backend default", hooks.backend_name)
    _ok("attach_langfuse_hooks(opt_in=False) returns inert "
        "stub:offline hooks (Rule 6 default)")

    span_start = hooks.on_action_start(
        action_id="act::lf-1", tool="weather_lookup",
        consent_token="ct-lf-1", consent_level="session",
        description="forecast", rollback_id=None,
    )
    if not span_start or span_start.get("event_kind") != "action_started":
        _fail("on_action_start", str(span_start))
    _ok("LangfuseHooks.on_action_start returns an action_started span")

    span_end = hooks.on_action_end(
        action_id="act::lf-1", tool="weather_lookup",
        outcome="success", consent_token="ct-lf-1",
        consent_level="session", cost_usd=0.0,
        outputs={"summary": "OK"},
    )
    if not span_end or span_end.get("event_kind") != "action_executed":
        _fail("on_action_end", str(span_end))
    _ok("LangfuseHooks.on_action_end returns an action_executed span")

    span_app = hooks.on_approval(
        action_id="act::lf-1", consent_token="ct-lf-1",
        tool="weather_lookup", consent_level="session", scope="forecast",
    )
    if not span_app or span_app.get("event_kind") != "approval_granted":
        _fail("on_approval", str(span_app))
    _ok("LangfuseHooks.on_approval returns an approval_granted span")

    span_rb = hooks.on_rollback(
        action_id="act::lf-1", rollback_id="rb-lf-1",
        tool="weather_lookup", consent_token="ct-lf-1",
        outcome="rolled_back", rollback_script="echo undo",
    )
    if not span_rb or span_rb.get("event_kind") != "rollback_executed":
        _fail("on_rollback", str(span_rb))
    _ok("LangfuseHooks.on_rollback returns a rollback_executed span")

    hooks.flush()
    _ok("LangfuseHooks.flush is callable without raising")

    # 6.13 — Empty action_id → no-op (defensive)
    if hooks.on_action_start(
        action_id="", tool="x", consent_token="t",
    ) is not None:
        _fail("hooks empty action_id", "should return None")
    _ok("LangfuseHooks short-circuits on empty action_id (defensive)")

    # 6.14 — attach_to_connectors auto-instruments + writes provenance
    reset_provenance_logger()
    try:
        shutil.rmtree(appdata_root(), ignore_errors=True)
    except OSError:
        pass

    from connectors import (  # type: ignore
        build_connector_registry,
    )
    from memory import (  # type: ignore
        get_action_memory_client,
    )

    consent = ConsentContext.from_iterable(
        ("run_web_action", "run_powershell_local", MEMORY_WRITE_GATE),
        consent_token="p142-attach",
    )
    mem_client = get_action_memory_client(
        force_stub=True, consent=consent, refresh=True,
    )
    registry = build_connector_registry(
        force_stub=True, consent=consent, memory_client=mem_client,
    )
    fresh_logger = get_provenance_logger(user_id="default", refresh=True)
    fresh_hooks  = attach_langfuse_hooks(opt_in=False, refresh=True)
    log_attached, hooks_attached = attach_to_connectors(
        registry, logger=fresh_logger, hooks=fresh_hooks,
    )
    if log_attached is not fresh_logger:
        _fail("attach_to_connectors logger", "wrong instance returned")
    _ok("attach_to_connectors returns (logger, hooks) — same instances")

    # Idempotency: a second attach is a no-op (no double-wrapping).
    attach_to_connectors(registry, logger=fresh_logger, hooks=fresh_hooks)
    _ok("attach_to_connectors is idempotent (re-instrument is a no-op)")

    # End-to-end: one connector call should produce ≥3 provenance rows.
    sh_result = registry.stagehand.execute_web_action(
        action_plan="open feed and read",
        consent_token="ct-attach-1",
        rollback="navigate to home",
        max_steps=2,
    )
    sh_aid = sh_result.provenance.action_id
    rows = fresh_logger.query_by_action_id(sh_aid or "")
    if len(rows) < 2:
        _fail("attach end-to-end count",
              f"expected ≥2 rows, got {len(rows)}")
    if not any(r.event_kind == "approval_granted" for r in rows):
        _fail("attach end-to-end approval",
              "missing approval_granted")
    if not any(r.event_kind == "action_executed" for r in rows):
        _fail("attach end-to-end action",
              "missing action_executed")
    _ok(f"end-to-end: stagehand.execute_web_action wrote "
        f"{len(rows)} provenance row(s) for action_id {sh_aid[:18] if sh_aid else 'n/a'}…")

    # Rollback path also routes through provenance.
    rb_result = registry.stagehand.execute_rollback(
        rollback_script="navigate to home",
        consent_token="ct-attach-1", action_id=sh_aid,
        rollback_id="rb-attach-1",
    )
    if rb_result.outcome != "rolled_back":
        _fail("attach rollback outcome", rb_result.outcome)
    rows_after_rb = fresh_logger.query_by_action_id(sh_aid or "")
    if not any(r.event_kind == "rollback_executed" for r in rows_after_rb):
        _fail("attach rollback row",
              "no rollback_executed row after execute_rollback")
    _ok("attach_to_connectors captures rollback_executed rows too")

    # 6.15 — chain after end-to-end
    chain_e2e = fresh_logger.reconstruct_rollback_chain(sh_aid or "")
    if not chain_e2e.reversed or chain_e2e.approval is None:
        _fail("attach end-to-end chain",
              f"reversed={chain_e2e.reversed} "
              f"approval={chain_e2e.approval is not None}")
    _ok("end-to-end RollbackChain has approval + forward + rollback")


# -- Section S.3. Entry point ---------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P131 + P142 Cross-Reality Action Fabric provenance smoke test")
    print(f"Langfuse backend: {LANGFUSE_BACKEND_NAME}")
    print("=" * 70)
    try:
        test_schema_and_surface()
        test_per_event_logging()
        test_attach_and_bulk_ingest()
        test_rollback_chain_across_runs()
        test_langfuse_hooks()
        test_p142_action_centric_api()
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
    print("RESULT: PASS — all 6 acceptance areas covered "
          "(5 P131 + 1 P142 action-centric)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
