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
"""Smoke test for the Cross-Reality Action Fabric provenance layer (P131).

Layered on top of the 221 prior P121–P130 checks. This suite adds 22
new checks across five acceptance areas:

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

Run on Windows (canonical):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m provenance.smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
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
    ALL_RULE_NUMBERS,
    ActionProvenanceRecord,
    EVENT_KINDS,
    LANGFUSE_BACKEND_NAME,
    LangfuseClient,
    LocalProvenanceLogger,
    ROLLBACK_OUTCOME,
    attach_provenance,
    current_log_path,
    export_audit_report,
    get_default_logger,
    get_langfuse_client,
    reset_default_logger,
    reset_langfuse_client,
    span_from_record,
    stub_trace_path,
    summarise_run,
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
    _ok(f"EVENT_KINDS lists exactly {len(expected_kinds)} canonical events")

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
    _ok("package re-exports the 6 canonical names")

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
    _ok("summarise_run returns the canonical 12-field digest")

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
    _ok("span_from_record returns the canonical 13-field span dict")

    # provenance_ingest coexists with memory_ingest from P130.
    if "memory_ingest" not in out:
        _fail("memory_ingest", "missing — P130 wrapper not chained")
    if "provenance_ingest" not in out:
        _fail("provenance_ingest", "missing")
    _ok("attach_provenance chains the P130 memory wrapper "
        "(memory_ingest + provenance_ingest both present)")


# -- Section S.3. Entry point ---------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P131 Cross-Reality Action Fabric provenance smoke test")
    print(f"Langfuse backend: {LANGFUSE_BACKEND_NAME}")
    print("=" * 70)
    try:
        test_schema_and_surface()
        test_per_event_logging()
        test_attach_and_bulk_ingest()
        test_rollback_chain_across_runs()
        test_langfuse_hooks()
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
    print("RESULT: PASS — all 5 P131 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
