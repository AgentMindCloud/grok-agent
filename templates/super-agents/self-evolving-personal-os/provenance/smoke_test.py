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
"""Smoke test for the Self-Evolving Personal OS provenance layer (P124).

Layered on top of the 92 prior P121 + P122 + P123 checks. This suite
adds 14 checks covering the four P124 acceptance areas:

1. ProvenanceRecord schema + LocalProvenanceLogger persistence
2. Langfuse hooks + stub-fallback selection
3. graph.py wrapper produces records on every node + final run_complete
4. export_audit_report Markdown shape + PII redaction at write time

Run on Windows (official):

.. code-block:: powershell

   cd templates/super-agents/self-evolving-personal-os
   python -m provenance.smoke_test

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

import agent as _agent  # type: ignore
import graph as _graph  # type: ignore
from connectors import (  # type: ignore
    ConsentContext,
    appdata_root,
)
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore
from memory import MEMORY_WRITE_GATE  # type: ignore
from provenance import (  # type: ignore
    LANGFUSE_BACKEND_NAME,
    LangfuseClient,
    LocalProvenanceLogger,
    ProvenanceRecord,
    current_log_path,
    export_audit_report,
    get_default_logger,
    get_langfuse_client,
    log_path_for,
    make_run_id,
    provenance_root,
    reset_default_logger,
    reset_langfuse_client,
    span_from_record,
    stub_trace_path,
    summarise_run,
)


# -- Section S.1. Helpers --------------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe() -> None:
    """Reset the local Personal OS state so every smoke section is hermetic."""
    root = appdata_root()
    for sub in ("memory", "logs", "provenance"):
        try:
            shutil.rmtree(root / sub, ignore_errors=True)
        except OSError:
            pass
    try:
        (root / "connector_audit.db").unlink(missing_ok=True)
    except OSError:
        pass
    reset_default_logger()
    reset_langfuse_client()


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="p124-smoke",
    )


# -- Section S.2. Test cases ---------------------------------------------

def test_logger_schema_and_persistence() -> None:
    print("[1/4] logger schema + persistence ----------------------------------")
    _wipe()
    logger = LocalProvenanceLogger(user_id="alice", run_id="run-test-1")
    if logger.user_id != "alice" or logger.run_id != "run-test-1":
        _fail("logger identity", f"got user_id={logger.user_id!r}, run_id={logger.run_id!r}")
    _ok("LocalProvenanceLogger constructed with explicit user_id + run_id")

    record = logger.log_step(
        node_name="test_node",
        state={"force_stub": True, "fetched": {}, "prompt_version": "v9"},
        update={"fetched": {"gcal": {"items": [{"kind": "calendar_event"}],
                                       "provenance": {"stub": True}}}},
        force_stub=True,
        duration_ms=12.34,
        error=None,
    )
    if not isinstance(record, ProvenanceRecord):
        _fail("log_step return", f"expected ProvenanceRecord, got {type(record)}")
    if not record.record_id.startswith("prv-"):
        _fail("record_id prefix", record.record_id)
    if record.run_id != "run-test-1":
        _fail("record.run_id", record.run_id)
    if record.confidence is None:
        _fail("confidence", "expected confidence to be set under force_stub")
    if record.stub_reason is None:
        _fail("stub_reason", "expected stub_reason to be populated")
    if record.memory_version != "v9":
        _fail("memory_version", record.memory_version)
    if "gcal" not in record.sources:
        _fail("sources detection", str(record.sources))
    _ok("ProvenanceRecord populated with id/run_id/confidence/stub_reason/sources/memory_version")

    # JSONL roundtrip
    line = record.to_jsonl()
    parsed = ProvenanceRecord.from_jsonl(line)
    if parsed.record_id != record.record_id:
        _fail("jsonl roundtrip", f"id mismatch")
    _ok("ProvenanceRecord JSONL serialise/parse roundtrip preserves identity")

    # File on disk
    path = current_log_path()
    if not path.exists():
        _fail("disk write", f"expected {path}, missing")
    line_count = sum(1 for _ in open(path, "r", encoding="utf-8"))
    if line_count != 1:
        _fail("line count", f"expected 1, got {line_count}")
    _ok(f"single record persisted to {path.name}")

    # Query API
    by_run = logger.query_by_run_id("run-test-1")
    if len(by_run) != 1:
        _fail("query_by_run_id", str(len(by_run)))
    _ok("query_by_run_id returns the persisted record")

    by_source = logger.query_by_source("gcal")
    if len(by_source) != 1:
        _fail("query_by_source", str(len(by_source)))
    _ok("query_by_source(gcal) finds the record via sources field")


def test_langfuse_stub_fallback() -> None:
    print("[2/4] Langfuse hooks + stub fallback -------------------------------")
    _wipe()
    client = get_langfuse_client(opt_in=False, refresh=True)
    if not isinstance(client, LangfuseClient):
        _fail("get_langfuse_client", f"got {type(client)}")
    if client.is_real:
        _fail("is_real", "stub backend should report is_real=False")
    if client.backend_name != "stub:offline":
        _fail("backend_name", client.backend_name)
    _ok("default backend is stub:offline (no opt-in, no env)")

    if LANGFUSE_BACKEND_NAME != client.backend_name:
        _fail("module BACKEND_NAME", LANGFUSE_BACKEND_NAME)
    _ok(f"module-level LANGFUSE_BACKEND_NAME mirrors client: {LANGFUSE_BACKEND_NAME}")

    trace = client.start_trace(run_id="run-lf-1", user_id="alice")
    if not trace.trace_id.startswith("trace-stub-"):
        _fail("trace_id prefix", trace.trace_id)
    _ok("start_trace produces a trace_id with the stub prefix")

    span = client.trace_step(
        node_name="x_node",
        inputs={"foo": "alice@example.com"},   # email should be redacted
        outputs={"bar": 1},
        confidence="medium",
        sources=["gmail"],
        stub_reason="force_stub",
    )
    if "alice@example.com" in json.dumps(span):
        _fail("trace_step PII", "raw email leaked into span")
    _ok("trace_step redacts PII before persisting")

    client.end_trace(outputs={"summary": "done"})
    client.flush()
    if not stub_trace_path().exists():
        _fail("stub trace file", "missing")
    _ok(f"stub trace file written at {stub_trace_path().name}")
    line_count = sum(1 for _ in open(stub_trace_path(), "r", encoding="utf-8"))
    if line_count < 3:  # trace_start + span + trace_end
        _fail("stub trace lines", str(line_count))
    _ok(f"stub trace contains {line_count} lines (trace_start + span + trace_end)")


def test_graph_wrapper_produces_records() -> None:
    print("[3/4] graph wrapper produces records -------------------------------")
    _wipe()
    out = _graph.run_daily_brief(force_stub=True, consent=_full_consent())
    if not out:
        _fail("run_daily_brief", "no output returned")
    _ok("run_daily_brief returned a brief")

    log_path = current_log_path()
    if not log_path.exists():
        _fail("provenance log", "JSONL file not written by graph wrapper")
    records = [
        ProvenanceRecord.from_jsonl(line)
        for line in open(log_path, "r", encoding="utf-8")
        if line.strip()
    ]
    if len(records) < 6:
        _fail("record count", f"expected ≥ 6, got {len(records)}")
    _ok(f"graph wrapper wrote {len(records)} ProvenanceRecord(s) (≥ 6 = 5 nodes + run_complete)")

    nodes = {r.node_name for r in records}
    expected_nodes = {
        "ingest_all_sources", "remember_personal", "evolve_workflows",
        "generate_brief", "output_with_provenance", "run_complete",
    }
    missing = expected_nodes - nodes
    if missing:
        _fail("nodes covered", f"missing: {sorted(missing)}")
    _ok(f"every expected node has at least one record: {sorted(nodes)}")

    if not all(r.stub_reason for r in records):
        _fail("force_stub propagation", "some records missing stub_reason")
    _ok("force_stub propagated stub_reason into every record")

    if not all(r.run_id == records[0].run_id for r in records):
        _fail("run_id consistency", "records carry different run_ids")
    _ok(f"all records share one run_id: {records[0].run_id}")

    durations = [r.duration_ms for r in records if r.duration_ms is not None]
    if not durations or any(d < 0 for d in durations):
        _fail("durations", f"got {durations}")
    _ok(f"per-node duration_ms populated and non-negative ({len(durations)} entries)")

    # Langfuse stub trace mirror should have been populated too.
    if not stub_trace_path().exists():
        _fail("langfuse mirror", "stub trace file missing after graph run")
    lf_lines = sum(1 for _ in open(stub_trace_path(), "r", encoding="utf-8"))
    if lf_lines < 6:
        _fail("langfuse mirror lines", str(lf_lines))
    _ok(f"Langfuse stub mirror captured {lf_lines} spans during graph run")


def test_audit_export_and_pii() -> None:
    print("[4/4] audit export + PII redaction ---------------------------------")
    _wipe()
    out = _graph.run_daily_brief(force_stub=True, consent=_full_consent())  # noqa: F841

    # Markdown audit report
    md = export_audit_report()
    if not md.startswith("# Self-Evolving Personal OS — Provenance Audit"):
        _fail("md header", md[:80])
    _ok("export_audit_report starts with the official Markdown header")
    if "## Per-node trail" not in md:
        _fail("md section", "missing per-node trail")
    _ok("Markdown report includes the per-node trail section")
    if "| # | Node |" not in md:
        _fail("md table", "missing trail table header")
    _ok("Markdown report includes a node-by-node table")

    # PII redaction at write time: inject leaky text and verify the JSONL
    # file does not contain the raw value.
    logger = get_default_logger()
    logger.log_step(
        node_name="leak_check",
        state={"force_stub": True, "leak": "Email me at bob@example.com or @bob_handle"},
        update={"reply": "I live at 221 Baker Street."},
        force_stub=True,
    )
    blob = current_log_path().read_text(encoding="utf-8")
    if "bob@example.com" in blob:
        _fail("PII leak (email)", "raw email surfaced in JSONL")
    if "@bob_handle" in blob and "@[REDACTED_HANDLE]" not in blob:
        _fail("PII leak (handle)", "raw X handle surfaced in JSONL")
    if "221 Baker Street" in blob:
        _fail("PII leak (address)", "raw address surfaced in JSONL")
    _ok("logger redacts emails / handles / addresses at write time")

    # latest_run + summarise_run
    recs = logger.latest_run()
    if not recs:
        _fail("latest_run", "no records returned")
    summary = summarise_run(recs)
    for k in ("run_id", "started_at", "finished_at", "node_count",
              "sources_seen", "stub", "errors", "confidences"):
        if k not in summary:
            _fail(f"summary[{k}]", "missing")
    _ok("summarise_run returns the official 8-field digest")

    # CSV-friendly: confidence breakdown is monotonic.
    if not summary["confidences"]:
        _fail("confidences", "empty")
    _ok(f"confidence distribution captured: {summary['confidences']}")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P124 Self-Evolving Personal OS provenance smoke test")
    print(f"Langfuse backend: {LANGFUSE_BACKEND_NAME}")
    print("=" * 70)
    try:
        test_logger_schema_and_persistence()
        test_langfuse_stub_fallback()
        test_graph_wrapper_produces_records()
        test_audit_export_and_pii()
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
    print("RESULT: PASS — all 4 P124 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
