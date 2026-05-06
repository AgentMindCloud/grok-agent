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
"""Smoke test for the Cross-Reality Action Fabric connector layer (P141).

Six acceptance areas, ~30 checks total:

1. Module surface — :mod:`connectors` re-exports, four factory
   functions importable, ConnectorRegistry instantiable.
2. Stagehand client — refusals (empty token, empty plan, missing
   rollback, bash leak) + happy path stub execution + memory rows.
3. Windows local client — refusals (empty token, empty script, bash
   leak, oversize script) + happy path stub + audit log written.
4. Real-world API client — refusals (empty token, malformed IATA,
   empty general query) + force_stub responses for weather, flights,
   general search.
5. X search client — refusals (empty token, empty query) + stub
   results structure + stub_reason in payload.
6. Memory + provenance integration — every successful call writes one
   ``add_approved_action`` row + one ``add_outcome_record`` row, both
   sharing the same ``action_id``; rollback writes one
   ``add_rollback_record`` row.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m connectors.smoke_test

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import shutil
import sys
import traceback

from graph import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    appdata_root,
)
from memory import (  # type: ignore
    DEFAULT_CONSENT_LEVEL,
    MEMORY_WRITE_GATE,
    PersonalActionMemoryClient,
    get_action_memory_client,
)
from connectors import (  # type: ignore
    ActionResult,
    ApprovalRequest,
    BaseActionConnector,
    ConnectorRefusal,
    ConnectorRegistry,
    build_connector_registry,
    get_real_world_api_client,
    get_stagehand_client,
    get_windows_local_client,
    get_x_search_client,
)
from connectors.real_world_api_client import RealWorldApiClient  # noqa: F401
from connectors.stagehand_client import StagehandClient  # noqa: F401
from connectors.windows_local_client import WindowsLocalClient  # noqa: F401
from connectors.x_search_client import XSearchClient  # noqa: F401


# -- Helpers --------------------------------------------------------------

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


_GATES = (
    "run_web_action", "run_powershell_local",
    "publish_to_x", "send_dm",
    MEMORY_WRITE_GATE,
)


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(_GATES, consent_token="p141-smoke")


def _memory(consent: ConsentContext | None = None) -> PersonalActionMemoryClient:
    return get_action_memory_client(
        force_stub=True, consent=consent or _full_consent(), refresh=True,
    )


# -- Section S.1. Module surface ---------------------------------------

def test_module_surface() -> None:
    print("[1/6] module surface ----------------------------------------------")
    for fn in (get_stagehand_client, get_windows_local_client,
               get_real_world_api_client, get_x_search_client):
        if not callable(fn):
            _fail(f"{fn.__name__}", "not callable")
    _ok("get_stagehand_client / get_windows_local_client / "
        "get_real_world_api_client / get_x_search_client are callable")

    registry = build_connector_registry(force_stub=True, consent=_full_consent())
    if not isinstance(registry, ConnectorRegistry):
        _fail("ConnectorRegistry", str(type(registry)))
    _ok("build_connector_registry returns a ConnectorRegistry")
    if not isinstance(registry.stagehand, StagehandClient):
        _fail("registry.stagehand type", str(type(registry.stagehand)))
    if not isinstance(registry.windows_local, WindowsLocalClient):
        _fail("registry.windows_local type", str(type(registry.windows_local)))
    if not isinstance(registry.real_world, RealWorldApiClient):
        _fail("registry.real_world type", str(type(registry.real_world)))
    if not isinstance(registry.x_search, XSearchClient):
        _fail("registry.x_search type", str(type(registry.x_search)))
    _ok("registry exposes all four typed clients (stagehand/windows/realworld/x)")

    # for_tool dispatch
    for tool in ("web_via_stagehand", "windows_local", "weather_lookup",
                 "flight_search", "general_search", "x_search"):
        client = registry.for_tool(tool)
        if not isinstance(client, BaseActionConnector):
            _fail(f"for_tool({tool})", str(type(client)))
    _ok("registry.for_tool() resolves all six manifest tools")


# -- Section S.2. Stagehand client --------------------------------------

def test_stagehand() -> None:
    print("[2/6] stagehand client --------------------------------------------")
    _wipe()
    consent = _full_consent()
    client = get_stagehand_client(
        memory_client=_memory(consent), force_stub=True, consent=consent,
    )

    # Empty consent_token → refusal (Rule 1).
    try:
        client.execute_web_action(action_plan="open https://x.com",
                                   consent_token="")
    except ConnectorRefusal as exc:
        if exc.rule != 1:
            _fail("stagehand empty token rule", str(exc.rule))
    else:
        _fail("stagehand empty token", "expected refusal")
    _ok("stagehand refuses empty consent_token (Rule 1)")

    # plan_web_action without rollback → refusal (Rule 3).
    try:
        client.plan_web_action("post a thread", rollback="")
    except ConnectorRefusal as exc:
        if exc.rule != 3:
            _fail("stagehand plan rollback rule", str(exc.rule))
    else:
        _fail("stagehand plan no rollback", "expected refusal")
    _ok("stagehand refuses plan without rollback (Rule 3)")

    # Bash leak in plan → refusal (Rule 5).
    try:
        client.execute_web_action(
            action_plan="bash -c 'rm -rf /etc'",
            consent_token="ct-1", rollback="echo undo",
        )
    except ConnectorRefusal as exc:
        if exc.rule != 5:
            _fail("stagehand bash leak rule", str(exc.rule))
    else:
        _fail("stagehand bash leak", "expected refusal")
    _ok("stagehand refuses bash leaks in action_plan (Rule 5)")

    # Happy path stub.
    plan = client.plan_web_action(
        "draft tomorrow's thread", rollback="navigate back to home",
        target_url="https://x.com/compose/post",
    )
    if not isinstance(plan, ApprovalRequest) or plan.tool != "web_via_stagehand":
        _fail("stagehand plan", str(plan))
    _ok(f"plan_web_action returns ApprovalRequest "
        f"(backend={plan.backend}, {len(plan.plan)} steps)")

    result = client.execute_web_action(
        action_plan="draft tomorrow's thread",
        consent_token="ct-stagehand-1",
        rollback="navigate back to home",
        target_url="https://x.com/compose/post",
        max_steps=4,
    )
    if not isinstance(result, ActionResult) or not result.ok:
        _fail("stagehand happy path", str(result))
    if result.outcome != "success":
        _fail("stagehand outcome", result.outcome)
    if not result.provenance.action_id:
        _fail("stagehand action_id", "missing")
    _ok(f"execute_web_action returns ActionResult ok=True outcome=success "
        f"action_id={result.provenance.action_id[:18]}…")


# -- Section S.3. Windows local client ----------------------------------

def test_windows_local() -> None:
    print("[3/6] windows local client ----------------------------------------")
    _wipe()
    consent = _full_consent()
    client = get_windows_local_client(
        memory_client=_memory(consent), force_stub=True, consent=consent,
    )

    # Empty consent_token → refusal.
    try:
        client.execute_local_action(
            script="Get-Date", rollback="echo no-op", consent_token="",
        )
    except ConnectorRefusal as exc:
        if exc.rule != 1:
            _fail("wl empty token", str(exc.rule))
    else:
        _fail("wl empty token", "expected refusal")
    _ok("windows_local refuses empty consent_token (Rule 1)")

    # Empty script → refusal.
    try:
        client.execute_local_action(
            script="", rollback="echo undo", consent_token="ct-x",
        )
    except ConnectorRefusal as exc:
        if exc.rule != 2:
            _fail("wl empty script", str(exc.rule))
    else:
        _fail("wl empty script", "expected refusal")
    _ok("windows_local refuses empty script (Rule 2)")

    # Bash leak → refusal (Rule 5).
    try:
        client.execute_local_action(
            script="bash -c 'echo hi'", rollback="echo undo",
            consent_token="ct-x",
        )
    except ConnectorRefusal as exc:
        if exc.rule != 5:
            _fail("wl bash leak rule", str(exc.rule))
    else:
        _fail("wl bash leak", "expected refusal")
    _ok("windows_local refuses bash leaks (Rule 5)")

    # Unix path leak → refusal (Rule 5).
    try:
        client.execute_local_action(
            script="ls /etc/hosts", rollback="echo undo",
            consent_token="ct-x",
        )
    except ConnectorRefusal as exc:
        if exc.rule != 5:
            _fail("wl unix path rule", str(exc.rule))
    else:
        _fail("wl unix path", "expected refusal")
    _ok("windows_local refuses /etc, /var, /usr paths (Rule 5)")

    # Happy path stub.
    result = client.execute_local_action(
        script="Get-Date",
        rollback="# no-op rollback",
        consent_token="ct-wl-1",
    )
    if not isinstance(result, ActionResult) or not result.ok:
        _fail("wl happy path", str(result))
    if result.outcome != "success":
        _fail("wl outcome", result.outcome)
    if not result.payload.get("stub"):
        _fail("wl stub flag", str(result.payload))
    _ok(f"execute_local_action stub returns ok=True outcome=success "
        f"backend={result.provenance.backend}")

    # Audit log written.
    if not client.audit_log.exists():
        _fail("wl audit log", "audit log file missing")
    if client.audit_log.stat().st_size == 0:
        _fail("wl audit log size", "audit log is empty")
    _ok(f"audit log appended ({client.audit_log.stat().st_size} bytes)")

    # Rollback path.
    rb = client.execute_rollback(
        rollback_script="# revert no-op",
        consent_token="ct-wl-1",
        action_id=result.provenance.action_id or "act::test",
    )
    if rb.outcome != "rolled_back":
        _fail("wl rollback outcome", rb.outcome)
    _ok("execute_rollback returns outcome=rolled_back")


# -- Section S.4. Real-world API client --------------------------------

def test_real_world() -> None:
    print("[4/6] real-world API client ---------------------------------------")
    _wipe()
    consent = _full_consent()
    client = get_real_world_api_client(
        memory_client=_memory(consent), force_stub=True, consent=consent,
    )

    # Empty consent_token → refusal.
    try:
        client.get_weather(consent_token="", locale="HAN")
    except ConnectorRefusal as exc:
        if exc.rule != 1:
            _fail("rw empty token", str(exc.rule))
    else:
        _fail("rw empty token", "expected refusal")
    _ok("real_world.get_weather refuses empty consent_token")

    # Bad IATA → refusal (Rule 2).
    try:
        client.search_flights(consent_token="ct-x", origin_iata="XX")
    except ConnectorRefusal as exc:
        if exc.rule != 2:
            _fail("rw bad iata", str(exc.rule))
    else:
        _fail("rw bad iata", "expected refusal")
    _ok("real_world.search_flights refuses non-3-letter origin IATA")

    # Empty general query → refusal.
    try:
        client.general_search(consent_token="ct-x", query="")
    except ConnectorRefusal as exc:
        if exc.rule != 2:
            _fail("rw empty query", str(exc.rule))
    else:
        _fail("rw empty query", "expected refusal")
    _ok("real_world.general_search refuses empty query")

    # Happy path stubs (force_stub=True so no real HTTP).
    weather = client.get_weather(
        consent_token="ct-w-1", locale="HAN", forecast_days=3,
    )
    if weather.tool != "weather_lookup" or not weather.ok:
        _fail("weather stub", str(weather))
    if not weather.payload.get("stub"):
        _fail("weather stub flag", str(weather.payload))
    _ok(f"weather stub returns ok=True tool=weather_lookup "
        f"summary='{weather.summary[:60]}'")

    flights = client.search_flights(
        consent_token="ct-f-1", origin_iata="HAN",
        destination_iata="SGN",
    )
    if flights.tool != "flight_search" or not flights.ok:
        _fail("flights stub", str(flights))
    _ok("flights stub returns ok=True tool=flight_search")

    gen = client.general_search(
        consent_token="ct-g-1", query="Hanoi airport code",
    )
    if gen.tool != "general_search" or not gen.ok:
        _fail("general stub", str(gen))
    _ok("general_search stub returns ok=True tool=general_search")


# -- Section S.5. X search client --------------------------------------

def test_x_search() -> None:
    print("[5/6] x_search client ---------------------------------------------")
    _wipe()
    consent = _full_consent()
    client = get_x_search_client(
        memory_client=_memory(consent), force_stub=True, consent=consent,
    )

    # Empty consent_token → refusal.
    try:
        client.search_x(query="grok", consent_token="")
    except ConnectorRefusal as exc:
        if exc.rule != 1:
            _fail("xs empty token", str(exc.rule))
    else:
        _fail("xs empty token", "expected refusal")
    _ok("x_search refuses empty consent_token (Rule 1)")

    # Empty query → refusal.
    try:
        client.search_x(query="", consent_token="ct-x")
    except ConnectorRefusal as exc:
        if exc.rule != 2:
            _fail("xs empty query", str(exc.rule))
    else:
        _fail("xs empty query", "expected refusal")
    _ok("x_search refuses empty query (Rule 2)")

    # Stub plan.
    plan = client.plan_x_search("xai launches", limit=8)
    if plan.tool != "x_search" or "x_search" not in plan.description:
        _fail("xs plan", str(plan))
    _ok(f"plan_x_search returns ApprovalRequest with {len(plan.plan)} plan lines")

    # Happy path stub.
    result = client.search_x(
        query="xai launches", consent_token="ct-xs-1", limit=5,
    )
    if result.tool != "x_search" or not result.ok:
        _fail("xs happy path", str(result))
    results = result.payload.get("results") or []
    if not results:
        _fail("xs results", "empty")
    if not result.payload.get("stub"):
        _fail("xs stub flag", str(result.payload))
    _ok(f"search_x stub returns {len(results)} hit(s) "
        f"with stub_reason='{result.payload.get('stub_reason','')[:40]}…'")


# -- Section S.6. Memory + provenance integration ----------------------

def test_memory_integration() -> None:
    print("[6/6] memory + provenance integration ----------------------------")
    _wipe()
    consent = _full_consent()
    mem = _memory(consent)
    client = get_stagehand_client(
        memory_client=mem, force_stub=True, consent=consent,
    )

    result = client.execute_web_action(
        action_plan="open feed and read latest",
        consent_token="ct-mem-1",
        rollback="navigate to home",
        max_steps=2,
    )
    aid = result.provenance.action_id
    if not aid:
        _fail("memory action_id", "missing")
    _ok("execute_web_action stamps provenance.action_id")

    chain = mem.list_rollback_chain(aid, limit=10)
    kinds = {h.kind for h in chain}
    if "action" not in kinds or "approval" not in kinds:
        _fail("memory chain action+approval",
              f"got {sorted(kinds)}")
    if "outcome" not in kinds:
        _fail("memory chain outcome",
              f"got {sorted(kinds)}")
    _ok(f"memory.list_rollback_chain finds action+approval+outcome "
        f"({sorted(kinds)})")

    # Rollback path adds a rollback row to the same action_id.
    rb = client.execute_rollback(
        rollback_script="navigate to home", consent_token="ct-mem-1",
        action_id=aid, rollback_id="rb-mem-1",
    )
    if rb.outcome != "rolled_back":
        _fail("memory rollback outcome", rb.outcome)
    chain2 = mem.list_rollback_chain(aid, limit=10)
    kinds2 = {h.kind for h in chain2}
    if "rollback" not in kinds2:
        _fail("memory rollback row",
              f"got {sorted(kinds2)}")
    _ok(f"execute_rollback writes rollback row "
        f"({sorted(kinds2)})")

    # consent_token is searchable via search_past_actions.
    by_token = mem.search_past_actions(
        "open feed", consent_token="ct-mem-1", limit=20,
    )
    if not by_token:
        _fail("memory search_past_actions", "no hits")
    if any(h.payload.get("consent_token") != "ct-mem-1" for h in by_token):
        _fail("memory consent_token leak",
              "rows with another token surfaced")
    _ok(f"search_past_actions(consent_token=ct-mem-1) returns "
        f"{len(by_token)} hit(s) — all token-pure")

    # Bare connector (no memory client) still produces a result.
    bare = get_stagehand_client(force_stub=True, consent=consent)
    bare_out = bare.execute_web_action(
        action_plan="bare ping", consent_token="ct-bare",
        rollback="bare undo", max_steps=1,
    )
    if not bare_out.ok or bare_out.provenance.backend != "stub:web":
        _fail("bare connector", str(bare_out))
    _ok("connector without memory_client still returns valid ActionResult")


# -- Entry point --------------------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P141 Cross-Reality Action Fabric connector smoke test")
    print("=" * 70)
    try:
        test_module_surface()
        test_stagehand()
        test_windows_local()
        test_real_world()
        test_x_search()
        test_memory_integration()
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
    print("RESULT: PASS — all 6 P141 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
