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
"""Smoke test for the Self-Evolving Personal OS connector helpers (P121).

Exercises the four non-negotiable behaviours required by P121:

1. **Consent-gate blocks** — every connector raises ConstitutionViolation
   when its required gate is not held.
2. **PII redaction** — emails, X handles, phone numbers, lat/lon, credit
   cards, and street addresses are redacted before items leave the connector.
3. **force_stub mode** — every connector returns a structurally-valid stub
   payload when force_stub=True, with provenance.stub == True.
4. **P119 + P120 integration** — ``with_connectors`` attaches a fully-wired
   composite to a stand-in orchestrator; the orchestrator's
   ``morning_brief`` and ``remember_personal`` paths read through the
   composite without the composite seeing the orchestrator's internals.

Run on Windows:

    cd templates/super-agents/self-evolving-personal-os
    python -m connectors.smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import sys
import traceback
from typing import Any

from . import (
    ConsentContext,
    ConstitutionViolation,
    FetchResult,
    MemoryStore,
    PersonalOSConnectors,
    SOURCES,
    build_connectors,
    redact_pii,
    with_connectors,
)


# -- Section S.1. Lightweight stand-ins for P119 / P120 -------------------

class _StandInMemory:
    """Minimal MemoryStore stand-in matching the P120 contract surface."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, FetchResult]] = []

    def upsert_fetch(self, collection: str, result: FetchResult) -> int:
        self.writes.append((collection, result))
        return len(result.items)


class _StandInOrchestrator:
    """Stand-in for the P119 PersonalOSOrchestrator.

    Mirrors the two integration points P121 must satisfy without modifying
    the real P119 file:

    - ``morning_brief()`` walks every source and calls ``connectors.fetch``
    - ``remember_personal()`` writes everything fetched into memory
    """

    def __init__(self) -> None:
        self.connectors: PersonalOSConnectors | None = None

    def morning_brief(self) -> dict[str, FetchResult]:
        assert self.connectors is not None, "connectors must be wired first"
        out: dict[str, FetchResult] = {}
        for src in self.connectors.sources:
            out[src] = self.connectors.fetch(src)
        return out

    def remember_personal(self, fetched: dict[str, FetchResult]) -> int:
        # The composite already writes to memory inside fetch(); the
        # orchestrator's job here is to count for the user-visible report.
        return sum(len(r.items) for r in fetched.values())


# -- Section S.2. Test cases ---------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def test_consent_gate_blocks() -> None:
    """Every connector raises ConstitutionViolation when its gate is unheld."""
    print("[1/4] consent gate blocks ------------------------------------------")
    composite = build_connectors()
    composite.set_consent(ConsentContext(gates=frozenset()))  # no gates
    composite.set_force_stub(True)
    for src in SOURCES:
        try:
            composite.fetch(src)
        except ConstitutionViolation as exc:
            if exc.article != "II":
                _fail(src, f"wrong article {exc.article}")
            if exc.source != src:
                _fail(src, f"wrong source attribution {exc.source}")
            _ok(f"{src} — gate refused with article II")
        else:
            _fail(src, "expected ConstitutionViolation but fetch returned cleanly")


def test_pii_redaction() -> None:
    """The PII redactor scrubs every flagged pattern."""
    print("[2/4] PII redaction ------------------------------------------------")
    raw = {
        "email":   "alice.smith@example.com",
        "phone":   "+1 415-555-0102",
        "card":    "4111 1111 1111 1111",
        "ssn":     "123-45-6789",
        "handle":  "Reach me at @alice_smith on X",
        "geo":     "10.7769, 106.7009",
        "street":  "I live at 221 Baker Street.",
    }
    out = redact_pii(raw)
    # Field-name rule: when the key is itself sensitive, the whole value is
    # replaced with the generic "[REDACTED]" token. The geo field is field-
    # name-redacted before the lat/lon regex ever fires.
    assert out["email"] == "[REDACTED]",                            out
    assert out["phone"] == "[REDACTED]",                            out
    assert out["card"]  == "[REDACTED]",                            out
    assert out["ssn"]   == "[REDACTED]",                            out
    assert out["geo"]   == "[REDACTED]",                            out
    # Free-text rule: regex catches the pattern inside a non-flagged field.
    assert "@[REDACTED_HANDLE]" in out["handle"],                   out
    assert "[REDACTED_ADDRESS]"  in out["street"],                  out
    _ok("email/phone/card/ssn/geo redacted by field-name rule")
    _ok("X handle redacted by regex")
    _ok("street address redacted by regex")

    # Defence-in-depth: nested structures are walked.
    nested = {
        "items": [
            {"text": "Forward to bob@corp.com please."},
            {"meta": {"address": "742 Evergreen Terrace, Springfield"}},
        ]
    }
    nested_out = redact_pii(nested)
    assert "[REDACTED_EMAIL]" in nested_out["items"][0]["text"], nested_out
    assert nested_out["items"][1]["meta"]["address"] == "[REDACTED]", nested_out
    _ok("nested PII walked recursively")


def test_force_stub_mode() -> None:
    """Every connector returns a runnable stub with provenance.stub=True."""
    print("[3/4] force_stub mode ----------------------------------------------")
    composite = build_connectors()
    composite.set_consent(ConsentContext.from_iterable(
        [
            "read_x_personal", "read_gcal", "read_gmail",
            "read_local_notes", "read_weather", "read_news_personal",
        ],
        consent_token="smoke-token",
    ))
    composite.set_force_stub(True)
    for src in SOURCES:
        result = composite.fetch(src)
        if not isinstance(result, FetchResult):
            _fail(src, f"expected FetchResult, got {type(result)}")
        if not result.provenance.get("stub"):
            _fail(src, f"provenance.stub != True: {result.provenance}")
        if not result.redaction_applied:
            _fail(src, "redaction_applied should be True even in stub mode")
        if result.error is not None:
            _fail(src, f"unexpected error: {result.error}")
        if not result.items:
            _fail(src, "stub should return at least one item")
        item = result.items[0]
        if "provenance" not in item:
            _fail(src, "stub item missing provenance block")
        _ok(f"{src} — stub returned {len(result.items)} item(s) with provenance")


def test_orchestrator_integration() -> None:
    """``with_connectors`` wires the composite into a stand-in orchestrator
    and ``morning_brief`` + ``remember_personal`` work end-to-end."""
    print("[4/4] P119 + P120 integration --------------------------------------")
    memory = _StandInMemory()
    orch   = _StandInOrchestrator()
    consent = ConsentContext.from_iterable(
        [
            "read_x_personal", "read_gcal", "read_gmail",
            "read_local_notes", "read_weather", "read_news_personal",
        ],
        consent_token="integration-token",
    )

    with_connectors(
        orch,
        manifest=None,
        memory_store=memory,
        consent=consent,
        force_stub=True,
    )
    assert orch.connectors is not None, "with_connectors did not attach .connectors"
    _ok("with_connectors attached PersonalOSConnectors to orchestrator")

    fetched = orch.morning_brief()
    if set(fetched.keys()) != set(SOURCES):
        _fail("morning_brief", f"missing sources: {set(SOURCES) - set(fetched.keys())}")
    _ok(f"morning_brief returned {len(fetched)} sources")

    total = orch.remember_personal(fetched)
    if total <= 0:
        _fail("remember_personal", "no items remembered")
    _ok(f"remember_personal counted {total} items across all sources")

    if len(memory.writes) == 0:
        _fail("memory wiring", "no writes reached the stand-in MemoryStore")
    written_collections = sorted({c for c, _ in memory.writes})
    _ok(f"memory store received writes on collections: {written_collections}")

    # Article III defence in depth: write-side params on a read-only client
    # must raise even with full consent and force_stub on.
    try:
        orch.connectors.fetch("local_notes", write=True)
    except ConstitutionViolation as exc:
        if exc.article != "III":
            _fail("write-refusal", f"wrong article: {exc.article}")
        _ok("read-only client refuses write-side params with article III")
    else:
        _fail("write-refusal", "expected ConstitutionViolation for write=True")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P121 Self-Evolving Personal OS connector smoke test")
    print("=" * 70)
    try:
        test_consent_gate_blocks()
        test_pii_redaction()
        test_force_stub_mode()
        test_orchestrator_integration()
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
    print("RESULT: PASS — all 4 P121 acceptance criteria covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
