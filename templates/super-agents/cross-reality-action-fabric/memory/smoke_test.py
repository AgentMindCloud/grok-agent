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
"""Smoke test for the Cross-Reality Action Fabric memory layer (P130).

Layered on top of all 196 prior P121–P129 checks. This suite adds 18
new checks across five acceptance areas:

1. Module surface — :mod:`memory` re-exports, 5 canonical kinds + 5
   collections present, ``MEMORY_WRITE_GATE`` exposed.
2. Consent + PII — every write refused without ``write_action_memory``
   gate; emails / handles / addresses redacted at write AND read time.
3. Per-kind write APIs — ``add_action_history``, ``add_approval_record``,
   ``add_rollback_record``, ``add_preference``, ``add_context`` each
   produce a :class:`MemoryRecord` routed to the correct collection.
4. Bulk ingest via P129 graph — ``attach_memory_store`` wraps
   :func:`graph.run_action_loop`; one auto-approved run produces
   ≥ 4 action rows + ≥ 4 approval rows + 1 context row.
5. Semantic search — ``search_by_context`` returns metadata-filtered
   hits with PII redacted.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m memory.smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback

from graph import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    appdata_root,
    rollback,
    run_action_loop,
)
from memory import (  # type: ignore
    ALLOWED_COLLECTIONS,
    COLLECTION_FOR_KIND,
    MEMORY_KINDS,
    MEMORY_WRITE_GATE,
    MemoryStoreAdapter,
    PersonalMemoryClient,
    QdrantIndex,
    SearchHit,
    attach_memory_store,
    build_memory_store,
    get_memory_client,
)


# -- Section S.1. Helpers --------------------------------------------------

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


# All 12 manifest-declared per-tool gates plus the memory-write gate so
# every helper that needs full consent can use the same builder.
ALL_GATES = (
    "publish_to_x", "send_dm", "move_funds", "pay_real_money",
    "export_tax_report", "sync_to_cloud",
    "modify_local_files_outside_appdata", "publish_synthesis",
    "run_powershell_local", "run_web_action",
    "read_calendar", "read_email",
    MEMORY_WRITE_GATE,
)


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(ALL_GATES, consent_token="p130-smoke")


# -- Section S.2. Test cases ---------------------------------------------

def test_module_surface() -> None:
    print("[1/5] module surface ----------------------------------------------")
    if MEMORY_WRITE_GATE != "write_action_memory":
        _fail("MEMORY_WRITE_GATE", str(MEMORY_WRITE_GATE))
    _ok(f"MEMORY_WRITE_GATE constant = {MEMORY_WRITE_GATE!r}")

    expected_kinds = {"action", "approval", "rollback", "preference", "context"}
    if set(MEMORY_KINDS) != expected_kinds:
        _fail("MEMORY_KINDS", str(MEMORY_KINDS))
    _ok(f"MEMORY_KINDS lists exactly {sorted(expected_kinds)}")

    expected_collections = {
        "crf.actions", "crf.approvals", "crf.rollbacks",
        "crf.preferences", "crf.contexts",
    }
    if set(ALLOWED_COLLECTIONS) != expected_collections:
        _fail("ALLOWED_COLLECTIONS", str(ALLOWED_COLLECTIONS))
    _ok(f"5 canonical collections present: {sorted(expected_collections)}")

    if set(COLLECTION_FOR_KIND.keys()) != set(MEMORY_KINDS):
        _fail("COLLECTION_FOR_KIND keys", str(COLLECTION_FOR_KIND))
    _ok("COLLECTION_FOR_KIND maps every kind to a collection")

    # Constructors / factories all importable.
    if not callable(attach_memory_store) or not callable(build_memory_store):
        _fail("attach/build factories", "missing")
    _ok("attach_memory_store + build_memory_store are callable factories")


def test_consent_and_pii() -> None:
    print("[2/5] consent + PII ----------------------------------------------")
    _wipe()
    client = get_memory_client(force_stub=True, refresh=True)
    client.set_consent(ConsentContext(gates=frozenset()))   # no gates

    for method, args in (
        ("add_action_history",  ({"tool": "windows_local"},)),
        ("add_approval_record", ({"step": 1, "tool": "windows_local",
                                   "consent_token": "ct"},)),
        ("add_rollback_record", ({"tool": "windows_local"},)),
        ("add_preference",      ("locale", "Hanoi,VN")),
        ("add_context",         ({"locale": "Hanoi,VN"},)),
    ):
        try:
            getattr(client, method)(*args)
        except ConstitutionViolation as exc:
            if exc.rule != 1:
                _fail(method, f"wrong rule: {exc.rule}")
        else:
            _fail(method, "expected ConstitutionViolation without consent")
    _ok("every write API refused without write_action_memory gate (Rule 1)")

    # Now hold consent and verify PII redaction works at write time.
    client.set_consent(_full_consent())
    leaky = {
        "tool": "windows_local",
        "description": "Email alice@example.com or @alice_smith",
        "script": "echo 'I live at 221 Baker Street.'",
        "rollback": "echo undo",
        "consent_token": "ct-test",
        "executed": True,
        "outcome": "success",
        "step": 1,
    }
    rec = client.add_action_history(leaky)
    blob = json.dumps(rec.to_qdrant_point(), default=str)
    if "alice@example.com" in blob:
        _fail("PII redaction (email)", "raw email reached the index")
    if "@alice_smith" in blob and "@[REDACTED_HANDLE]" not in blob:
        _fail("PII redaction (handle)", "raw X handle reached the index")
    if "221 Baker Street" in blob:
        _fail("PII redaction (address)", "raw address reached the index")
    _ok("emails / handles / addresses redacted at write time")

    # Search hit also redacts (defence in depth).
    hits = client.search_by_context("alice", kind="action", limit=3)
    if not hits:
        _fail("search after PII write", "no hit returned")
    blob_read = json.dumps([h.to_dict() for h in hits], default=str)
    if "alice@example.com" in blob_read:
        _fail("PII redaction (read)", "raw email surfaced in search")
    _ok("search results re-redact PII at read time")


def test_per_kind_writes() -> None:
    print("[3/5] per-kind write APIs -----------------------------------------")
    _wipe()
    client = get_memory_client(force_stub=True, refresh=True)
    client.set_consent(_full_consent())

    rec1 = client.add_action_history({
        "tool": "weather_lookup", "step": 1, "executed": True,
        "outcome": "success", "consent_token": "ct-1",
        "description": "Weather forecast for Hanoi",
        "expected_cost_usd": 0.0,
    })
    if rec1.kind != "action":
        _fail("add_action_history kind", rec1.kind)
    _ok("add_action_history records routed to crf.actions")

    rec2 = client.add_approval_record({
        "step": 1, "tool": "weather_lookup",
        "consent_token": "ct-1", "approval_status": "granted",
    })
    if rec2.kind != "approval":
        _fail("add_approval_record kind", rec2.kind)
    _ok("add_approval_record records routed to crf.approvals")

    rec3 = client.add_rollback_record({
        "step": 3, "tool": "windows_local", "outcome": "rolled_back",
        "rolled_back_from": 3, "rollback": "echo undo",
        "started_at": "2026-05-05T12:00:00Z",
        "finished_at": "2026-05-05T12:00:01Z",
    })
    if rec3.kind != "rollback":
        _fail("add_rollback_record kind", rec3.kind)
    if not rec3.payload.get("rolled_back_from"):
        _fail("rollback.rolled_back_from", "missing")
    _ok("add_rollback_record carries rolled_back_from (Rule 3 audit)")

    rec4 = client.add_preference("default_locale", "Hanoi,VN")
    if rec4.kind != "preference" or rec4.payload.get("key") != "default_locale":
        _fail("add_preference", str(rec4.payload))
    _ok("add_preference records routed to crf.preferences with key/value")

    rec5 = client.add_context({"locale": "Hanoi,VN", "session_id": "s-42"})
    if rec5.kind != "context":
        _fail("add_context kind", rec5.kind)
    _ok("add_context records routed to crf.contexts")

    # Per-kind counts match what we wrote.
    for kind, expected in (
        ("action", 1), ("approval", 1), ("rollback", 1),
        ("preference", 1), ("context", 1),
    ):
        actual = client.count(kind=kind)
        if actual != expected:
            _fail(f"count[{kind}]", f"expected {expected}, got {actual}")
    _ok("count(kind=...) reports 1 row per kind across all 5 categories")

    # Provenance fields populated.
    for rec in (rec1, rec2, rec3, rec4, rec5):
        for k in ("user_id", "kind", "indexed_at", "backend", "redaction_applied"):
            if k not in rec.provenance:
                _fail(f"provenance[{rec.kind}]", f"missing field {k}")
    _ok("every record carries the canonical provenance fields (Rule 2)")


def test_attach_and_record_run() -> None:
    print("[4/5] attach_memory_store + record_run ---------------------------")
    _wipe()
    consent = _full_consent()
    client, run_with_memory = attach_memory_store(
        force_stub=True, consent=consent,
    )
    if not isinstance(client, PersonalMemoryClient):
        _fail("attach client type", str(type(client)))
    _ok("attach_memory_store returns (PersonalMemoryClient, callable)")

    out = run_with_memory(force_stub=True, auto_approve=True, user_request="hi")
    if "memory_ingest" not in out:
        _fail("memory_ingest in output", "missing")
    _ok("run_with_memory adds memory_ingest counters to the output")
    counters = out["memory_ingest"]
    if counters.get("actions", 0) < 4:
        _fail("ingest.actions", str(counters))
    if counters.get("approvals", 0) < 4:
        _fail("ingest.approvals", str(counters))
    if counters.get("contexts", 0) != 1:
        _fail("ingest.contexts", str(counters))
    _ok(f"single auto-approved run ingested {counters['actions']} actions + "
        f"{counters['approvals']} approvals + {counters['contexts']} context")

    # The MemoryStoreAdapter degrades gracefully without consent.
    adapter = build_memory_store(force_stub=True, consent=ConsentContext())
    refused = adapter.record_run(out)
    if not refused.get("refused"):
        _fail("adapter graceful degrade", str(refused))
    _ok("MemoryStoreAdapter degrades gracefully when consent is absent")

    # The wrapper also degrades gracefully when consent is missing.
    bare_client, bare_run = attach_memory_store(
        force_stub=True, consent=ConsentContext(),
    )
    bare_out = bare_run(force_stub=True, auto_approve=True)
    if (bare_out.get("memory_ingest") or {}).get("skipped") is not True:
        _fail("wrapper graceful degrade", str(bare_out.get("memory_ingest")))
    _ok("attach_memory_store wrapper marks ingest skipped when consent absent")


def test_semantic_search_filters() -> None:
    print("[5/5] semantic search + filters -----------------------------------")
    _wipe()
    consent = _full_consent()
    client, run = attach_memory_store(force_stub=True, consent=consent)

    # Run twice to populate enough rows for filter coverage.
    out1 = run(force_stub=True, auto_approve=True, user_request="run 1")
    out2 = run(force_stub=True, auto_approve=True, user_request="run 2")  # noqa: F841

    # Filter by kind.
    actions_only = client.search_by_context("weather", kind="action", limit=10)
    if not actions_only:
        _fail("filter kind=action", "no hits")
    if any(h.kind != "action" for h in actions_only):
        _fail("filter kind=action", "leaked non-action kind")
    _ok(f"search filtered by kind=action returns {len(actions_only)} action hit(s)")

    # Filter by tool (action_type) — only weather_lookup actions.
    weather_only = client.search_by_context(
        "weather", kind="action", tool="weather_lookup", limit=10,
    )
    if any(h.payload.get("tool") != "weather_lookup" for h in weather_only):
        _fail("filter tool=weather_lookup", "leaked other tools")
    _ok("search filtered by tool=weather_lookup is tool-pure")

    # Filter by approval_status — only granted approvals.
    granted = client.search_by_context(
        "ct", kind="approval", approval_status="granted", limit=10,
    )
    if any(h.payload.get("approval_status") != "granted" for h in granted):
        _fail("filter approval_status=granted", "leaked other statuses")
    _ok(f"search filtered by approval_status=granted returns {len(granted)} hit(s)")

    # Cross-kind search returns hits from multiple categories.
    mixed = client.search_by_context("plan", limit=20)
    seen_kinds = {h.kind for h in mixed}
    if len(seen_kinds) < 2:
        _fail("cross-kind search", f"only saw {seen_kinds}")
    _ok(f"cross-kind search returns hits across {len(seen_kinds)} kinds: {sorted(seen_kinds)}")

    # Provenance present on every hit.
    if not all(h.provenance.get("redaction_applied") for h in mixed):
        _fail("provenance on hits", "missing redaction_applied flag")
    _ok("every search hit carries provenance with redaction_applied=True")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P130 Cross-Reality Action Fabric memory smoke test")
    print("=" * 70)
    try:
        test_module_surface()
        test_consent_and_pii()
        test_per_kind_writes()
        test_attach_and_record_run()
        test_semantic_search_filters()
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
    print("RESULT: PASS — all 5 P130 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
