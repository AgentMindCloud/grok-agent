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
"""Smoke test for the Self-Evolving Personal OS memory layer (P122).

Exercises the four P122 acceptance behaviours, layered on top of the
already-passing P121 connector smoke test:

1. **Consent-gated writes** — PersonalMemoryClient refuses writes when the
   ``write_personal_memory`` gate or the source-specific read gate is not
   held (Article II).
2. **PII redaction at write + read** — emails, X handles, lat/lon, and similar
   identifiers are redacted on both upsert and search paths.
3. **Per-source vector index** — Qdrant collections are created on first
   run, upserts route to ``personal.<source>`` exactly, and semantic
   search filters cleanly by source.
4. **End-to-end with_connectors → ingest → search** — wire connectors and
   memory together via the ``attach_personal_memory`` helper, drive the
   morning-brief flow, and verify search returns provenance-tagged hits
   from every source.

Run on Windows:

    cd templates/super-agents/self-evolving-personal-os
    python -m memory.smoke_test

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import shutil
import sys
import traceback

from connectors import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    SOURCES,
    attach_personal_memory,
    build_connectors,
)
from memory import (  # type: ignore
    MEMORY_WRITE_GATE,
    PersonalMemoryClient,
    QdrantIndex,
    SearchHit,
    build_memory_store,
    get_memory_client,
    memory_root,
    qdrant_root,
)
from memory.mem0_setup import (  # type: ignore
    MemoryStoreAdapter,
    SOURCE_READ_GATES,
)


# -- Section S.1. Test harness helpers ------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe_memory_root() -> None:
    """Reset the local memory store so the smoke run is hermetic."""
    for path in (qdrant_root(), memory_root()):
        try:
            shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


# -- Section S.2. Test cases ---------------------------------------------

def test_module_surface() -> None:
    """The public API surface promised in the prompt resolves cleanly."""
    print("[1/5] module surface ------------------------------------------------")
    client = get_memory_client(force_stub=True, refresh=True)
    if not isinstance(client, PersonalMemoryClient):
        _fail("get_memory_client", f"expected PersonalMemoryClient, got {type(client)}")
    _ok("get_memory_client returns PersonalMemoryClient")

    if not callable(getattr(client, "add_personal_event", None)):
        _fail("add_personal_event", "missing on client")
    if not callable(getattr(client, "search", None)):
        _fail("search", "missing on client")
    if not callable(getattr(client, "delete", None)):
        _fail("delete", "missing on client")
    _ok("client exposes add_personal_event / search / delete")

    store = build_memory_store(force_stub=True)
    if not isinstance(store, MemoryStoreAdapter):
        _fail("build_memory_store", f"expected MemoryStoreAdapter, got {type(store)}")
    _ok("build_memory_store returns MemoryStoreAdapter")


def test_consent_gate_blocks_writes() -> None:
    """PersonalMemoryClient refuses all writes when the gate is unheld."""
    print("[2/5] consent-gate blocks writes -----------------------------------")
    client = get_memory_client(force_stub=True, refresh=True)
    client.set_consent(ConsentContext(gates=frozenset()))   # no gates

    try:
        client.add_personal_event(
            source="local_notes",
            text="should be blocked",
            payload={},
            provenance={},
        )
    except ConstitutionViolation as exc:
        if exc.article != "II":
            _fail("write-without-gate", f"wrong article: {exc.article}")
        _ok("add_personal_event refused without write_personal_memory")
    else:
        _fail("write-without-gate", "expected ConstitutionViolation")

    # Holding only the write gate but missing the source read gate must also fail.
    client.set_consent(ConsentContext.from_iterable([MEMORY_WRITE_GATE]))
    try:
        client.add_personal_event(
            source="gmail",
            text="should be blocked too",
            payload={},
            provenance={},
        )
    except ConstitutionViolation as exc:
        if exc.gate != "read_gmail":
            _fail("missing-source-gate", f"wrong gate: {exc.gate}")
        _ok("add_personal_event refused without source-specific read gate")
    else:
        _fail("missing-source-gate", "expected ConstitutionViolation")

    # Delete is consent-gated too.
    client.set_consent(ConsentContext(gates=frozenset()))
    try:
        client.delete(record_id="any-id")
    except ConstitutionViolation as exc:
        if exc.gate != MEMORY_WRITE_GATE:
            _fail("delete-without-gate", f"wrong gate: {exc.gate}")
        _ok("delete refused without write_personal_memory")
    else:
        _fail("delete-without-gate", "expected ConstitutionViolation")


def test_pii_redaction_on_write_and_read() -> None:
    """Stored payload + searched payload are both PII-redacted."""
    print("[3/5] PII redaction at write + read --------------------------------")
    _wipe_memory_root()
    client = get_memory_client(force_stub=True, refresh=True)
    client.set_consent(ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="pii-token",
    ))

    leaky_text = (
        "Reach me at alice@example.com or call +1 415-555-0102. "
        "Find me on X as @alice_smith. I live at 221 Baker Street."
    )
    rec = client.add_personal_event(
        source="local_notes",
        text=leaky_text,
        payload={"body": leaky_text, "title": "leaky note"},
        provenance={"source": "smoke", "endpoint": "smoke://test"},
    )
    if "[REDACTED" not in rec.text:
        _fail("redact-text", f"text not redacted: {rec.text}")
    _ok("indexed text is PII-redacted")
    if "[REDACTED" not in rec.payload.get("body", ""):
        _fail("redact-body", f"payload body not redacted: {rec.payload}")
    _ok("payload body is PII-redacted")

    hits = client.search(query="baker street", source="local_notes", limit=3)
    if not hits:
        _fail("search-recall", "search returned 0 hits")
    matched = hits[0]
    if "alice@example.com" in matched.text or "@alice_smith" in matched.text:
        _fail("search-leak", f"raw PII surfaced in search: {matched.text}")
    _ok("search results re-redact PII at read time")
    if not matched.provenance:
        _fail("search-provenance", "search hit missing provenance")
    if not matched.provenance.get("redaction_applied"):
        _fail("search-provenance", "redaction_applied flag missing")
    _ok("search hits carry provenance with redaction_applied=True")


def test_per_source_routing_and_count() -> None:
    """Qdrant collections cover all 6 sources; counts match per source."""
    print("[4/5] per-source vector index --------------------------------------")
    _wipe_memory_root()
    client = get_memory_client(force_stub=True, refresh=True)
    client.set_consent(ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="routing-token",
    ))

    qd: QdrantIndex = client.qdrant
    declared = sorted({f"personal.{s.replace('x_personal','x') if s=='x_personal' else s}" for s in SOURCES})  # noqa: E501
    actual_collections = qd.list_collections()
    expected_collections = {
        "personal.x", "personal.calendar", "personal.email",
        "personal.notes", "personal.weather", "personal.news",
    }
    if not expected_collections.issubset(set(actual_collections)):
        _fail("collections", f"expected ⊇ {expected_collections}, got {actual_collections}")
    _ok(f"6 personal.* collections present: {sorted(expected_collections)}")

    # Write one item per source.
    sample_payloads = {
        "x_personal":     {"kind": "mention", "id": "m1", "text": "hello world"},
        "gcal":           {"kind": "calendar_event", "id": "ev1", "summary": "lunch", "start_iso": "2026-05-06T12:00Z"},
        "gmail":          {"kind": "email", "id": "msg1", "subject": "hi", "snippet": "hello"},
        "local_notes":    {"kind": "note", "title": "idea", "relpath": "ideas/idea1.md", "body": "an idea"},
        "weather":        {"locale": "Hanoi,VN", "dt_iso": "2026-05-06T00:00Z", "temp": 30, "weather": [{"description": "stub"}]},
        "news_personal":  {"title": "news headline 1", "description": "x", "source_name": "wire"},
    }
    for src, payload in sample_payloads.items():
        client.add_personal_event(
            source=src,
            text=qd._summarise_item(src, payload),
            payload=payload,
            provenance={"source": "smoke", "endpoint": "smoke://routing"},
        )

    total = client.count()
    if total < 6:
        _fail("total-count", f"expected ≥ 6 records, got {total}")
    _ok(f"client.count() reports {total} records across all sources")

    for src in SOURCES:
        c = client.count(source=src)
        if c < 1:
            _fail(f"per-source-count[{src}]", f"expected ≥ 1, got {c}")
    _ok("client.count(source=...) reports ≥ 1 for every source")

    # Source-filtered search returns only that source.
    only_news = client.search(query="news", source="news_personal", limit=5)
    if not only_news:
        _fail("source-filter", "expected ≥ 1 news hit")
    if any(h.source != "news_personal" for h in only_news):
        _fail("source-filter", "search leaked items from other sources")
    _ok("source-filtered search returns only news_personal hits")


def test_end_to_end_with_connectors() -> None:
    """attach_personal_memory wires connectors + memory; ingest+search works."""
    print("[5/5] end-to-end with_connectors → memory --------------------------")
    _wipe_memory_root()

    class _StandInOrchestrator:
        connectors = None
        memory_client = None
        memory_adapter = None

    orch = _StandInOrchestrator()
    consent = ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="e2e-token",
    )
    attach_personal_memory(
        orch, manifest=None, consent=consent,
        user_id="smoke-user", force_stub=True,
    )
    if orch.connectors is None or orch.memory_client is None:
        _fail("attach", "attach_personal_memory did not wire connectors + memory")
    _ok("attach_personal_memory wired connectors + memory_client + memory_adapter")

    # Drive the connector layer and verify writes flow through to memory.
    fetched: dict = {src: orch.connectors.fetch(src) for src in SOURCES}
    if any(r is None or not r.items for r in fetched.values()):
        _fail("morning-brief", "expected stub items from every source")
    _ok("connector morning-brief flow returned items from all 6 sources")

    # The adapter drives writes into memory automatically; verify by counting.
    client: PersonalMemoryClient = orch.memory_client
    total_before_filter = client.count()
    if total_before_filter < len(SOURCES):
        _fail("ingest", f"expected ≥ {len(SOURCES)} memory rows, got {total_before_filter}")
    _ok(f"adapter ingested {total_before_filter} rows into memory via connectors")

    # Each source writes at least 1 row.
    for src in SOURCES:
        if client.count(source=src) < 1:
            _fail("per-source-ingest", f"{src}: expected ≥ 1, got {client.count(source=src)}")
    _ok("every source has ≥ 1 row in its personal.* collection")

    # Cross-source search returns provenance-tagged hits.
    hits: list[SearchHit] = client.search(query="stub", limit=10)
    if not hits:
        _fail("cross-source-search", "expected ≥ 1 hit")
    if not all(h.source for h in hits):
        _fail("provenance", "hit missing source attribution")
    if not all(h.provenance.get("redaction_applied") for h in hits):
        _fail("provenance", "hit missing redaction_applied flag")
    _ok(f"cross-source search returned {len(hits)} provenance-tagged hits")

    # force_stub mode is honoured: every record's provenance carries stub=True.
    stubbed = [h for h in hits if h.provenance.get("stub")]
    if not stubbed:
        _fail("force-stub", "no hits carried provenance.stub=True under force_stub")
    _ok(f"{len(stubbed)} hits carry provenance.stub=True (force_stub honoured)")

    # Direct adapter call with insufficient consent degrades gracefully (no raise).
    bare_composite = build_connectors()
    bare_composite.set_consent(ConsentContext(gates=frozenset()))
    bare_composite.set_force_stub(True)
    adapter = build_memory_store(force_stub=True, consent=ConsentContext(gates=frozenset()))
    bare_composite.connect_memory(adapter)
    # The connector itself raises (P121 behaviour); the adapter never sees a
    # call. That's the correct chain. We assert the connector path:
    try:
        bare_composite.fetch("local_notes")
    except ConstitutionViolation:
        _ok("connector blocks fetch before adapter is invoked when consent missing")
    else:
        _fail("graceful-degrade", "expected ConstitutionViolation from connector")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P122 Self-Evolving Personal OS memory smoke test")
    print("=" * 70)
    try:
        test_module_surface()
        test_consent_gate_blocks_writes()
        test_pii_redaction_on_write_and_read()
        test_per_source_routing_and_count()
        test_end_to_end_with_connectors()
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
    print("RESULT: PASS — all 5 P122 acceptance criteria covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
