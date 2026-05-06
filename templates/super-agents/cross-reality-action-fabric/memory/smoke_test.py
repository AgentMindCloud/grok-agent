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
"""Smoke test for the Cross-Reality Action Fabric memory layer.

Covers both the original P130 surface and the P140 action-centric API.
Six acceptance areas, ~40 checks total:

1. Module surface — :mod:`memory` re-exports, 6 canonical kinds + 6
   collections present, ``MEMORY_WRITE_GATE`` exposed,
   ``CONSENT_LEVELS`` exposed.
2. Consent + PII — every write refused without ``write_action_memory``
   gate; emails / handles / addresses redacted at write AND read time.
3. Per-kind write APIs — ``add_action_history``, ``add_approval_record``,
   ``add_rollback_record``, ``add_outcome_record``, ``add_preference``,
   ``add_context`` each produce a :class:`MemoryRecord` routed to the
   correct collection.
4. Bulk ingest via P129 graph — ``attach_memory_store`` wraps
   :func:`graph.run_action_loop`; one auto-approved run produces
   ≥ 4 action rows + ≥ 4 approval rows + 1 context row.
5. Semantic search — ``search_by_context`` returns metadata-filtered
   hits with PII redacted.
6. **P140 action-centric API** — ``PersonalActionMemoryClient``,
   ``add_approved_action`` (with consent_token + consent_level +
   rollback_id), ``add_outcome_record``, ``search_past_actions``
   (consent_token / consent_level / action_id filters),
   ``attach_action_memory`` wrapper, force_stub provenance.

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
    ACTION_MEMORY_KINDS,
    ALLOWED_COLLECTIONS,
    COLLECTION_FOR_KIND,
    CONSENT_LEVELS,
    DEFAULT_CONSENT_LEVEL,
    MEMORY_KINDS,
    MEMORY_WRITE_GATE,
    ActionMemoryStoreAdapter,
    MemoryStoreAdapter,
    PersonalActionMemoryClient,
    PersonalMemoryClient,
    QdrantIndex,
    SearchHit,
    attach_action_memory,
    attach_memory_store,
    build_action_memory_store,
    build_memory_store,
    consent_level_rank,
    get_action_memory_client,
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

    # P140 added the ``outcome`` kind on top of the original five from
    # P130. Both old subsets must remain present.
    expected_kinds = {
        "action", "approval", "rollback", "outcome", "preference", "context",
    }
    if set(MEMORY_KINDS) != expected_kinds:
        _fail("MEMORY_KINDS", str(MEMORY_KINDS))
    _ok(f"MEMORY_KINDS lists exactly {sorted(expected_kinds)}")

    expected_collections = {
        "crf.actions", "crf.approvals", "crf.rollbacks", "crf.outcomes",
        "crf.preferences", "crf.contexts",
    }
    if set(ALLOWED_COLLECTIONS) != expected_collections:
        _fail("ALLOWED_COLLECTIONS", str(ALLOWED_COLLECTIONS))
    _ok(f"6 canonical collections present: {sorted(expected_collections)}")

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

    rec6 = client.add_outcome_record({
        "action_id":   "act::1::ct-1",
        "step":        1,
        "tool":        "weather_lookup",
        "outcome":     "success",
        "description": "Returned 28C / partly cloudy.",
        "side_effects": [],
    })
    if rec6.kind != "outcome":
        _fail("add_outcome_record kind", rec6.kind)
    if not rec6.payload.get("action_id"):
        _fail("add_outcome_record action_id", "missing")
    _ok("add_outcome_record records routed to crf.outcomes with action_id")

    # Per-kind counts match what we wrote.
    for kind, expected in (
        ("action", 1), ("approval", 1), ("rollback", 1),
        ("outcome", 1), ("preference", 1), ("context", 1),
    ):
        actual = client.count(kind=kind)
        if actual != expected:
            _fail(f"count[{kind}]", f"expected {expected}, got {actual}")
    _ok("count(kind=...) reports 1 row per kind across all 6 categories")

    # Provenance fields populated.
    for rec in (rec1, rec2, rec3, rec4, rec5, rec6):
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


def test_p140_action_centric_api() -> None:
    print("[6/6] P140 action-centric API ------------------------------------")
    _wipe()

    # 6.1 — Constants exposed.
    if tuple(CONSENT_LEVELS) != ("session", "persistent", "shared"):
        _fail("CONSENT_LEVELS", str(CONSENT_LEVELS))
    _ok(f"CONSENT_LEVELS exposes {list(CONSENT_LEVELS)}")
    if DEFAULT_CONSENT_LEVEL != "session":
        _fail("DEFAULT_CONSENT_LEVEL", DEFAULT_CONSENT_LEVEL)
    _ok(f"DEFAULT_CONSENT_LEVEL = {DEFAULT_CONSENT_LEVEL!r}")
    if (consent_level_rank("session") != 0
            or consent_level_rank("persistent") != 1
            or consent_level_rank("shared") != 2
            or consent_level_rank("typo") != 0):
        _fail("consent_level_rank", "ordering broken")
    _ok("consent_level_rank: session=0 < persistent=1 < shared=2 (typo=0)")

    # 6.2 — Subclass relationship + factory return type.
    if not issubclass(PersonalActionMemoryClient, PersonalMemoryClient):
        _fail("PersonalActionMemoryClient subclass",
              "must subclass PersonalMemoryClient")
    _ok("PersonalActionMemoryClient subclasses PersonalMemoryClient")

    consent = _full_consent()
    client = get_action_memory_client(
        force_stub=True, consent=consent, refresh=True,
    )
    if not isinstance(client, PersonalActionMemoryClient):
        _fail("get_action_memory_client type", str(type(client)))
    _ok("get_action_memory_client returns PersonalActionMemoryClient")

    # 6.3 — add_approved_action requires non-empty consent_token (Rule 1).
    try:
        client.add_approved_action(
            {"step": 1, "tool": "windows_local",
             "executed": True, "outcome": "success",
             "description": "noop"},
            consent_token="",
        )
    except ConstitutionViolation as exc:
        if exc.rule != 1:
            _fail("add_approved_action empty token rule", str(exc.rule))
    else:
        _fail("add_approved_action empty token",
              "expected ConstitutionViolation")
    _ok("add_approved_action refuses empty consent_token (Rule 1)")

    # 6.4 — Without write gate, add_approved_action also refused.
    no_consent_client = PersonalActionMemoryClient(
        force_stub=True, consent=ConsentContext(),
    )
    try:
        no_consent_client.add_approved_action(
            {"step": 1, "tool": "windows_local",
             "executed": True, "outcome": "success"},
            consent_token="ct-x",
        )
    except ConstitutionViolation as exc:
        if exc.rule != 1:
            _fail("add_approved_action gate-rule", str(exc.rule))
    else:
        _fail("add_approved_action no gate",
              "expected ConstitutionViolation")
    _ok("add_approved_action refused without write_action_memory gate")

    # 6.5 — Successful add_approved_action writes BOTH action+approval.
    pair = client.add_approved_action(
        {
            "step":        1,
            "tool":        "weather_lookup",
            "executed":    True,
            "outcome":     "success",
            "description": "Forecast for Hanoi.",
            "expected_cost_usd": 0.0,
        },
        consent_token="ct-p140-1",
        consent_level="session",
        rollback_id="rb::demo::step1",
    )
    if pair["action"].kind != "action" or pair["approval"].kind != "approval":
        _fail("add_approved_action lock-step",
              str((pair["action"].kind, pair["approval"].kind)))
    _ok("add_approved_action writes action + approval rows in lock-step")

    if pair["action_id"] != pair["action"].payload.get("action_id"):
        _fail("action_id correlation",
              f"action.payload.action_id="
              f"{pair['action'].payload.get('action_id')}")
    if pair["action"].payload.get("action_id") != \
            pair["approval"].payload.get("action_id"):
        _fail("action_id linkage",
              "action and approval rows do not share action_id")
    _ok("add_approved_action shares action_id between action+approval rows")

    if pair["action"].payload.get("consent_level") != "session":
        _fail("consent_level on action", str(pair["action"].payload))
    if pair["approval"].payload.get("consent_level") != "session":
        _fail("consent_level on approval", str(pair["approval"].payload))
    if pair["action"].payload.get("rollback_id") != "rb::demo::step1":
        _fail("rollback_id on action", str(pair["action"].payload))
    _ok("add_approved_action stamps consent_level + rollback_id metadata")

    if pair["action"].payload.get("consent_token") != "ct-p140-1":
        _fail("consent_token on action", str(pair["action"].payload))
    _ok("add_approved_action carries consent_token onto action row")

    # 6.6 — Outcome record correlates back via action_id.
    out_rec = client.add_outcome_record(
        {
            "action_id":   pair["action_id"],
            "tool":        "weather_lookup",
            "outcome":     "success",
            "description": "API returned 28C.",
            "side_effects": [],
        },
        consent_token="ct-p140-1",
        consent_level="session",
        rollback_id="rb::demo::step1",
    )
    if out_rec.kind != "outcome":
        _fail("outcome.kind", out_rec.kind)
    if out_rec.payload.get("action_id") != pair["action_id"]:
        _fail("outcome.action_id linkage", str(out_rec.payload))
    _ok("add_outcome_record correlates back via action_id")

    # 6.7 — Rollback record carries explicit rollback_id + action_id.
    rb_rec = client.add_rollback_record(
        {
            "step": 1, "tool": "weather_lookup",
            "outcome": "rolled_back",
            "rollback": "echo undo",
            "rolled_back_from": 1,
        },
        consent_token="ct-p140-1",
        consent_level="session",
        rollback_id="rb::demo::step1",
        action_id=pair["action_id"],
    )
    if rb_rec.payload.get("rollback_id") != "rb::demo::step1":
        _fail("rollback.rollback_id", str(rb_rec.payload))
    if rb_rec.payload.get("action_id") != pair["action_id"]:
        _fail("rollback.action_id", str(rb_rec.payload))
    _ok("add_rollback_record carries rollback_id + action_id chain")

    # 6.8 — search_past_actions filtered by consent_token returns only
    # records tagged with that token.
    by_token = client.search_past_actions(
        "weather", consent_token="ct-p140-1", limit=20,
    )
    if not by_token:
        _fail("search_past_actions consent_token", "no hits")
    if any(h.payload.get("consent_token") != "ct-p140-1" for h in by_token):
        _fail("search_past_actions consent_token leak",
              "found rows tagged with another token")
    _ok(f"search_past_actions filtered by consent_token returns "
        f"{len(by_token)} hit(s) — all token-pure")

    # 6.9 — list_rollback_chain returns all four kinds for the same
    # action_id (action + approval + rollback + outcome).
    chain = client.list_rollback_chain(pair["action_id"], limit=20)
    chain_kinds = {h.kind for h in chain}
    expected_chain = {"action", "approval", "rollback", "outcome"}
    if not expected_chain.issubset(chain_kinds):
        _fail("list_rollback_chain kinds",
              f"missing: {expected_chain - chain_kinds}")
    _ok(f"list_rollback_chain returns the full chain "
        f"({sorted(chain_kinds)})")

    # 6.10 — max_consent_level filter hides higher-retention rows.
    client.add_approved_action(
        {
            "step":        2,
            "tool":        "weather_lookup",
            "executed":    True,
            "outcome":     "success",
            "description": "Forecast for Saigon.",
        },
        consent_token="ct-p140-2",
        consent_level="persistent",
    )
    session_only = client.search_past_actions(
        "weather",
        max_consent_level="session",
        kinds=("action",),
        limit=50,
    )
    if any(h.payload.get("consent_level") == "persistent" for h in session_only):
        _fail("max_consent_level hierarchy",
              "persistent row leaked into session search")
    if not any(h.payload.get("consent_level") == "session" for h in session_only):
        _fail("max_consent_level hierarchy",
              "session rows missing")
    _ok("search_past_actions(max_consent_level=session) hides persistent rows")

    persistent_search = client.search_past_actions(
        "weather",
        max_consent_level="persistent",
        kinds=("action",),
        limit=50,
    )
    levels_seen = {h.payload.get("consent_level") for h in persistent_search}
    if not {"session", "persistent"}.issubset(levels_seen):
        _fail("max_consent_level=persistent",
              f"only saw {levels_seen}")
    _ok("search_past_actions(max_consent_level=persistent) covers "
        "session + persistent rows")

    # 6.11 — Without the write gate, search is implicitly capped at the
    # most-restrictive level (session-only).
    capped_client = PersonalActionMemoryClient(
        force_stub=True, consent=ConsentContext(),
    )
    capped_search = capped_client.search_past_actions("weather", limit=50)
    if any(h.payload.get("consent_level") == "persistent" for h in capped_search):
        _fail("implicit cap without consent",
              "persistent rows leaked to a no-consent caller")
    _ok("search_past_actions caps retention to session-only when "
        "consent gate is absent")

    # 6.12 — attach_action_memory + run wrapper.
    _wipe()
    consent = _full_consent()
    a_client, a_run = attach_action_memory(
        force_stub=True, consent=consent,
    )
    if not isinstance(a_client, PersonalActionMemoryClient):
        _fail("attach_action_memory client type", str(type(a_client)))
    _ok("attach_action_memory returns (PersonalActionMemoryClient, callable)")

    out = a_run(
        force_stub=True, auto_approve=True, user_request="run-1",
        consent_level="persistent",
    )
    if "memory_ingest" not in out:
        _fail("attach_action_memory ingest", "missing memory_ingest")
    counters = out["memory_ingest"]
    for key in ("actions", "approvals", "outcomes"):
        if int(counters.get(key) or 0) < 1:
            _fail(f"action ingest[{key}]", str(counters))
    if counters.get("consent_level") != "persistent":
        _fail("ingest.consent_level", str(counters))
    _ok(f"run_with_action_memory ingested {counters['actions']} actions + "
        f"{counters['approvals']} approvals + {counters['outcomes']} outcomes "
        f"@ consent_level={counters['consent_level']!r}")

    # 6.13 — search_past_actions(kinds=("outcome",)) returns the
    # newly-written outcome rows.
    outcomes = a_client.search_past_actions(
        "", kinds=("outcome",), limit=50,
    )
    if not outcomes:
        _fail("outcome rows after run", "none indexed")
    if any(h.kind != "outcome" for h in outcomes):
        _fail("outcome kind purity", "leaked another kind")
    _ok(f"search_past_actions(kinds=outcome) returns "
        f"{len(outcomes)} outcome row(s) after the run")

    # 6.14 — graceful skip when consent gate absent.
    bare_client, bare_run = attach_action_memory(
        force_stub=True, consent=ConsentContext(),
    )
    bare_out = bare_run(force_stub=True, auto_approve=True)
    if (bare_out.get("memory_ingest") or {}).get("skipped") is not True:
        _fail("attach_action_memory skip",
              str(bare_out.get("memory_ingest")))
    _ok("attach_action_memory skips ingest when consent gate absent")

    # 6.15 — force_stub mode propagates to provenance.
    if a_client.qdrant.backend_name and \
            "stub" not in a_client.qdrant.backend_name:
        # not necessarily an error — a real qdrant install would say
        # "qdrant-client:local" here. We only assert on the FORCED case.
        pass
    forced_stub_client = PersonalActionMemoryClient(
        force_stub=True, consent=_full_consent(),
    )
    pair2 = forced_stub_client.add_approved_action(
        {
            "step": 1, "tool": "weather_lookup",
            "executed": True, "outcome": "success",
            "description": "stub-mode forecast",
        },
        consent_token="ct-stub", consent_level="session",
    )
    if not pair2["action"].provenance.get("stub"):
        _fail("force_stub provenance.stub", str(pair2["action"].provenance))
    if "stub_reason" not in pair2["action"].provenance:
        _fail("force_stub provenance.stub_reason",
              str(pair2["action"].provenance))
    _ok("force_stub=True stamps provenance.stub + provenance.stub_reason")

    # 6.16 — ActionMemoryStoreAdapter.client is correctly typed.
    adapter = build_action_memory_store(
        force_stub=True, consent=_full_consent(),
    )
    if not isinstance(adapter, ActionMemoryStoreAdapter):
        _fail("build_action_memory_store type", str(type(adapter)))
    if not isinstance(adapter.client, PersonalActionMemoryClient):
        _fail("ActionMemoryStoreAdapter.client type",
              str(type(adapter.client)))
    _ok("build_action_memory_store returns ActionMemoryStoreAdapter "
        "with PersonalActionMemoryClient.client")

    # 6.17 — ACTION_MEMORY_KINDS excludes preference + context.
    if set(ACTION_MEMORY_KINDS) != {"action", "approval", "rollback", "outcome"}:
        _fail("ACTION_MEMORY_KINDS", str(ACTION_MEMORY_KINDS))
    _ok(f"ACTION_MEMORY_KINDS = {sorted(ACTION_MEMORY_KINDS)} "
        "(no preference / context leakage)")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P130 + P140 Cross-Reality Action Fabric memory smoke test")
    print("=" * 70)
    try:
        test_module_surface()
        test_consent_and_pii()
        test_per_kind_writes()
        test_attach_and_record_run()
        test_semantic_search_filters()
        test_p140_action_centric_api()
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
          "(5 P130 + 1 P140 action-centric)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
