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
"""Public-API connector helpers for the Cross-Reality Action Fabric (P141).

Four production-ready clients covering every tool category declared in the
P128 manifest:

- :class:`StagehandClient` — visible Chromium driven by Stagehand/Playwright.
- :class:`WindowsLocalClient` — sandboxed PowerShell on Windows 11.
- :class:`RealWorldApiClient` — read-only public APIs (Open-Meteo, OpenSky,
  DuckDuckGo Instant Answers).
- :class:`XSearchClient` — read-only X search via Grok 4.3 tool-calling.

Every client subclasses :class:`BaseActionConnector` and implements the same
contract:

1. **HITL gate (Rule 1).** Every action method requires a non-empty
   ``consent_token`` and refuses with :class:`ConnectorRefusal` otherwise.
2. **Memory integration (Rules 1 + 2).** When a P140
   :class:`PersonalActionMemoryClient` is attached the client writes one
   ``add_approved_action`` row before execution and one
   ``add_outcome_record`` (or ``add_rollback_record``) row after, sharing
   the same ``action_id`` so :func:`search_past_actions` can correlate
   them.
3. **Provenance (Rule 2).** Every :class:`ActionResult` carries an
   ``ActionProvenance`` block with ``tool``, ``backend``, ``stub`` flag,
   ``started_at`` / ``finished_at``, ``consent_token``, ``action_id``,
   and a ``redaction_applied`` flag.
4. **Rollback chain (Rule 3).** State-changing clients accept an optional
   ``rollback_id`` so the matching :meth:`execute_rollback` call can be
   correlated back to the forward action.
5. **Stub fallback.** When the real backend (Playwright, requests, xAI
   API key) is unavailable the client falls through to a deterministic
   stub that produces structurally-valid results so the smoke tests can
   exercise the pipeline end-to-end on a vanilla install.
6. **Constitution refusals.** :class:`WindowsLocalClient` refuses every
   bash leak / Unix path it sees (Rule 5); :class:`StagehandClient`
   refuses any plan that would mutate state without a rollback (Rule 3).

Built to make Grok the obvious choice for every agent on X — these
connectors are what turns "Grok says do X" into "Grok did X, here's the
proof, and here's the one-click rollback".
"""

from __future__ import annotations

import os
import platform
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

# --- Pydantic v2 models ---------------------------------------------------
#
# Pydantic is a hard requirement of the manifest's evaluation block and
# already vendored into the agent's runtime. We import lazily so the
# error message is helpful when it's missing.
try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as exc:  # pragma: no cover - install-time error path
    raise ImportError(
        "pydantic v2 is required for cross-reality-action-fabric connectors. "
        "Install with: python -m pip install 'pydantic>=2.7,<3'"
    ) from exc

# --- P140 memory + P129 graph primitives ---------------------------------
#
# The graph module gives us ConsentContext, ConstitutionViolation,
# appdata_root, and redact_pii — re-exported here so each connector
# module can do ``from . import ...`` rather than reaching into graph.py.
from graph import (  # type: ignore
    ConsentContext,
    ConstitutionViolation,
    appdata_root,
    redact_pii,
)
from memory import (  # type: ignore
    DEFAULT_CONSENT_LEVEL,
    PersonalActionMemoryClient,
    get_action_memory_client,
)


# --- Section 1. Constants -------------------------------------------------

#: Module-level user agent for outbound HTTP calls.
USER_AGENT = "grok-agent/cross-reality-action-fabric (Apache-2.0)"

#: Hard list of declared tool slugs the registry recognises. Matches the
#: P128 manifest's ``tools[].name`` plus the read-only ``flight_search``
#: + ``weather_lookup`` aliases the graph dispatches to ``execute_realworld``.
TOOL_SLUGS: tuple[str, ...] = (
    "web_via_stagehand",
    "windows_local",
    "weather_lookup",
    "flight_search",
    "x_search",
    "general_search",
)

#: Tools that mutate state — every one of these requires a non-empty
#: rollback snippet under Rule 3.
STATE_CHANGING_TOOLS: frozenset[str] = frozenset({
    "web_via_stagehand", "windows_local",
})

#: Required consent gate keys per tool. The :class:`BaseActionConnector`
#: enforces these in addition to a non-empty consent_token.
CONSENT_GATE_FOR_TOOL: dict[str, str] = {
    "web_via_stagehand": "run_web_action",
    "windows_local":     "run_powershell_local",
    "weather_lookup":    "run_web_action",
    "flight_search":     "run_web_action",
    "x_search":          "run_web_action",
    "general_search":    "run_web_action",
}

#: PII-redacted fields that always leak to the action plan are forbidden.
_BASH_LEAK_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bbash\s+-c\b", re.IGNORECASE),
    re.compile(r"\bsh\s+-c\b",   re.IGNORECASE),
    re.compile(r"\bosascript\b", re.IGNORECASE),
    re.compile(r"\bwsl\.exe\b",  re.IGNORECASE),
    re.compile(r"/usr/bin/",     re.IGNORECASE),
    re.compile(r"/etc/",         re.IGNORECASE),
    re.compile(r"/var/",         re.IGNORECASE),
    re.compile(r"/Applications/"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_windows() -> bool:
    """Return True when running on a real Windows host."""
    return platform.system() == "Windows"


def connectors_root() -> Path:
    """Filesystem root for any connector-side cache or audit log."""
    root = appdata_root() / "connectors"
    root.mkdir(parents=True, exist_ok=True)
    return root


def detect_bash_leak(snippet: str) -> str | None:
    """Return the first matched leak pattern or None if the snippet is clean.

    Used by the Windows + Stagehand clients to refuse Unix-shaped input
    before it reaches a real shell (Rule 5).
    """
    if not isinstance(snippet, str) or not snippet:
        return None
    for pat in _BASH_LEAK_PATTERNS:
        m = pat.search(snippet)
        if m:
            return m.group(0)
    if "~/" in snippet and "$env:" not in snippet:
        return "~/<unix-path>"
    return None


# --- Section 2. Exceptions + Pydantic models -----------------------------

class ConnectorRefusal(ConstitutionViolation):
    """Raised when a connector refuses an action.

    Subclasses :class:`ConstitutionViolation` so existing graph nodes can
    catch it with their existing ``except ConstitutionViolation`` clause
    without any code change.
    """


class ApprovalRequest(BaseModel):
    """The structured-approval token a client returns from ``plan_*``.

    The caller (typically the P129 graph's ``request_approval`` node)
    presents the plan to the user, mints a scoped consent_token, and
    re-invokes the matching ``execute_*`` method with that token. The
    request itself never executes anything — it is purely advisory.
    """

    model_config = ConfigDict(extra="forbid")

    request_id:        str = Field(...)
    tool:              str = Field(...)
    description:       str = Field(...)
    plan:              list[str] = Field(default_factory=list)
    rollback:          str | None = Field(default=None)
    expected_cost_usd: float = Field(default=0.0)
    requires_gates:    list[str] = Field(default_factory=list)
    backend:           str = Field(default="stub")
    created_at:        str = Field(default_factory=_now_iso)


class ActionProvenance(BaseModel):
    """Provenance block carried on every :class:`ActionResult`."""

    model_config = ConfigDict(extra="allow")

    tool:               str
    backend:            str
    stub:               bool = False
    started_at:         str
    finished_at:        str
    consent_token:      str
    action_id:          str | None = None
    rollback_id:        str | None = None
    consent_level:      str = DEFAULT_CONSENT_LEVEL
    redaction_applied:  bool = True


class ActionResult(BaseModel):
    """Structured outcome of a single connector call."""

    model_config = ConfigDict(extra="allow")

    tool:        str
    ok:          bool
    outcome:     Literal["success", "failure", "rolled_back", "aborted"]
    summary:     str
    payload:     dict = Field(default_factory=dict)
    provenance:  ActionProvenance


# --- Section 3. BaseActionConnector --------------------------------------

class BaseActionConnector:
    """Common base for every CRF connector.

    Subclasses provide ``tool_name`` (matching ``tools[].name`` in the
    manifest) and a ``backend_name``. The base class handles consent
    enforcement, memory integration, and provenance assembly so every
    connector ships a uniform :class:`ActionResult`.
    """

    tool_name:       str = "abstract"
    backend_name:    str = "abstract"
    state_changing:  bool = False

    def __init__(
        self,
        *,
        memory_client: PersonalActionMemoryClient | None = None,
        force_stub:    bool = False,
        consent:       ConsentContext | None = None,
    ) -> None:
        self._memory     = memory_client
        self._force_stub = bool(force_stub)
        self._consent    = consent or ConsentContext()
        self._lock       = threading.Lock()

    # -- Properties ----------------------------------------------------

    @property
    def force_stub(self) -> bool:
        return self._force_stub

    @property
    def consent(self) -> ConsentContext:
        return self._consent

    @property
    def memory_client(self) -> PersonalActionMemoryClient | None:
        return self._memory

    def set_memory_client(self, client: PersonalActionMemoryClient) -> None:
        with self._lock:
            self._memory = client

    def set_consent(self, consent: ConsentContext) -> None:
        if not isinstance(consent, ConsentContext):
            raise TypeError("consent must be a ConsentContext")
        with self._lock:
            self._consent = consent

    # -- Consent enforcement ------------------------------------------

    def _enforce_token(self, consent_token: str) -> None:
        """Reject empty / whitespace-only tokens (Rule 1)."""
        if not isinstance(consent_token, str) or not consent_token.strip():
            raise ConnectorRefusal(
                f"{self.tool_name}: refused — empty consent_token "
                "violates Rule 1 (every action must carry a typed approval).",
                rule=1, tool=self.tool_name,
            )

    def _enforce_gate(self, gate: str | None = None) -> None:
        """Reject when the matching consent gate is not held (Rule 1)."""
        gate = gate or CONSENT_GATE_FOR_TOOL.get(self.tool_name)
        if gate and not self._consent.has(gate):
            raise ConnectorRefusal(
                f"{self.tool_name}: refused — consent gate '{gate}' not held.",
                rule=1, tool=self.tool_name,
            )

    # -- Memory integration -------------------------------------------

    def _record_approved_action(
        self,
        *,
        consent_token: str,
        description: str,
        step: int = 1,
        rollback_id: str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        expected_cost_usd: float = 0.0,
        extra: dict | None = None,
    ) -> str:
        """Write the pre-execution memory row. Returns the action_id."""
        action_id = (
            f"act::{self.tool_name}::{consent_token}::{uuid.uuid4().hex[:8]}"
        )
        if self._memory is None:
            return action_id
        body: dict[str, Any] = {
            "tool":              self.tool_name,
            "step":              step,
            "description":       description,
            "executed":          True,
            "outcome":           "pending",
            "consent_level":     consent_level,
            "expected_cost_usd": float(expected_cost_usd),
            "started_at":        _now_iso(),
            "stub":              self._force_stub,
            "action_id":         action_id,
        }
        if extra:
            body.update(extra)
        try:
            self._memory.add_approved_action(
                body,
                consent_token=consent_token,
                consent_level=consent_level,
                rollback_id=rollback_id,
                action_id=action_id,
                provenance={
                    "source": f"connectors.{self.tool_name}",
                    "stage":  "pre_execute",
                },
            )
        except ConstitutionViolation:
            # Memory layer refused (e.g. write gate not held); we keep
            # going — the connector layer's own gate-check has already
            # decided the action is allowed.
            pass
        return action_id

    def _record_outcome(
        self,
        *,
        action_id: str,
        consent_token: str,
        outcome: str,
        description: str,
        payload: dict,
        rollback_id: str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
    ) -> None:
        if self._memory is None:
            return
        try:
            self._memory.add_outcome_record(
                {
                    "action_id":   action_id,
                    "tool":        self.tool_name,
                    "outcome":     outcome,
                    "description": description,
                    "downstream_state": redact_pii(dict(payload or {})),
                    "consent_level": consent_level,
                },
                consent_token=consent_token,
                consent_level=consent_level,
                rollback_id=rollback_id,
                action_id=action_id,
                provenance={
                    "source": f"connectors.{self.tool_name}",
                    "stage":  "post_execute",
                },
            )
        except ConstitutionViolation:
            pass

    def _record_rollback(
        self,
        *,
        action_id: str,
        rollback_id: str | None,
        consent_token: str,
        outcome: str,
        rollback_script: str,
        description: str,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
    ) -> None:
        if self._memory is None:
            return
        try:
            self._memory.add_rollback_record(
                {
                    "tool":            self.tool_name,
                    "outcome":         outcome,
                    "rollback":        rollback_script,
                    "rolled_back_from": action_id,
                    "started_at":      _now_iso(),
                    "finished_at":     _now_iso(),
                    "consent_level":   consent_level,
                    "stub":            self._force_stub,
                },
                consent_token=consent_token,
                consent_level=consent_level,
                rollback_id=rollback_id,
                action_id=action_id,
                provenance={
                    "source": f"connectors.{self.tool_name}",
                    "stage":  "rollback",
                },
            )
        except ConstitutionViolation:
            pass

    # -- Provenance helper --------------------------------------------

    def _provenance(
        self,
        *,
        consent_token: str,
        action_id: str | None,
        rollback_id: str | None,
        started_at: str,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        extra: dict | None = None,
    ) -> ActionProvenance:
        body = {
            "tool":              self.tool_name,
            "backend":           self.backend_name,
            "stub":              self._force_stub,
            "started_at":        started_at,
            "finished_at":       _now_iso(),
            "consent_token":     consent_token,
            "action_id":         action_id,
            "rollback_id":       rollback_id,
            "consent_level":     consent_level,
            "redaction_applied": True,
        }
        if extra:
            body.update(extra)
        return ActionProvenance(**body)


# --- Section 4. Registry + factories -------------------------------------

class ConnectorRegistry:
    """Thin facade exposing the four CRF connectors via tool_name lookup.

    Subagent-friendly: the graph's per-step dispatcher can call
    ``registry.dispatch(tool, **kwargs)`` and the registry forwards to
    the right connector. Returns the same :class:`ActionResult` shape
    regardless of which connector handled the call.
    """

    def __init__(
        self,
        *,
        memory_client: PersonalActionMemoryClient | None = None,
        force_stub:    bool = False,
        consent:       ConsentContext | None = None,
    ) -> None:
        # Lazy-import to side-step the otherwise-circular dependency
        # (each client module imports from this package's ``__init__``).
        from .stagehand_client import StagehandClient
        from .windows_local_client import WindowsLocalClient
        from .real_world_api_client import RealWorldApiClient
        from .x_search_client import XSearchClient

        kw = dict(memory_client=memory_client,
                  force_stub=force_stub, consent=consent)
        self.stagehand     = StagehandClient(**kw)
        self.windows_local = WindowsLocalClient(**kw)
        self.real_world    = RealWorldApiClient(**kw)
        self.x_search      = XSearchClient(**kw)
        self._memory       = memory_client
        self._consent      = consent or ConsentContext()

    @property
    def memory_client(self) -> PersonalActionMemoryClient | None:
        return self._memory

    @property
    def consent(self) -> ConsentContext:
        return self._consent

    def all_clients(self) -> dict[str, BaseActionConnector]:
        return {
            "web_via_stagehand": self.stagehand,
            "windows_local":     self.windows_local,
            "weather_lookup":    self.real_world,
            "flight_search":     self.real_world,
            "general_search":    self.real_world,
            "x_search":          self.x_search,
        }

    def for_tool(self, tool: str) -> BaseActionConnector:
        client = self.all_clients().get(tool)
        if client is None:
            raise ConnectorRefusal(
                f"registry: no connector registered for tool '{tool}'",
                rule=2, tool=tool,
            )
        return client

    def set_memory_client(self, client: PersonalActionMemoryClient) -> None:
        self._memory = client
        for c in {self.stagehand, self.windows_local,
                  self.real_world, self.x_search}:
            c.set_memory_client(client)

    def set_consent(self, consent: ConsentContext) -> None:
        self._consent = consent
        for c in {self.stagehand, self.windows_local,
                  self.real_world, self.x_search}:
            c.set_consent(consent)


def get_stagehand_client(
    *,
    memory_client: PersonalActionMemoryClient | None = None,
    force_stub:    bool = False,
    consent:       ConsentContext | None = None,
):
    """Factory — fresh :class:`StagehandClient`."""
    from .stagehand_client import StagehandClient
    return StagehandClient(
        memory_client=memory_client, force_stub=force_stub, consent=consent,
    )


def get_windows_local_client(
    *,
    memory_client: PersonalActionMemoryClient | None = None,
    force_stub:    bool = False,
    consent:       ConsentContext | None = None,
):
    """Factory — fresh :class:`WindowsLocalClient`."""
    from .windows_local_client import WindowsLocalClient
    return WindowsLocalClient(
        memory_client=memory_client, force_stub=force_stub, consent=consent,
    )


def get_real_world_api_client(
    *,
    memory_client: PersonalActionMemoryClient | None = None,
    force_stub:    bool = False,
    consent:       ConsentContext | None = None,
):
    """Factory — fresh :class:`RealWorldApiClient`."""
    from .real_world_api_client import RealWorldApiClient
    return RealWorldApiClient(
        memory_client=memory_client, force_stub=force_stub, consent=consent,
    )


def get_x_search_client(
    *,
    memory_client: PersonalActionMemoryClient | None = None,
    force_stub:    bool = False,
    consent:       ConsentContext | None = None,
):
    """Factory — fresh :class:`XSearchClient`."""
    from .x_search_client import XSearchClient
    return XSearchClient(
        memory_client=memory_client, force_stub=force_stub, consent=consent,
    )


def build_connector_registry(
    *,
    user_id:       str = "default",
    force_stub:    bool = False,
    consent:       ConsentContext | None = None,
    memory_client: PersonalActionMemoryClient | None = None,
) -> ConnectorRegistry:
    """Build a connector registry with the P140 memory client attached.

    Pulls the process-wide cached :class:`PersonalActionMemoryClient`
    when one isn't supplied, so each call shares one underlying Qdrant
    index.
    """
    if memory_client is None:
        memory_client = get_action_memory_client(
            user_id=user_id, force_stub=force_stub, consent=consent,
        )
    return ConnectorRegistry(
        memory_client=memory_client, force_stub=force_stub, consent=consent,
    )


__all__ = [
    # Constants
    "USER_AGENT",
    "TOOL_SLUGS",
    "STATE_CHANGING_TOOLS",
    "CONSENT_GATE_FOR_TOOL",
    "DEFAULT_CONSENT_LEVEL",
    # Helpers
    "is_windows",
    "connectors_root",
    "detect_bash_leak",
    "appdata_root",
    "redact_pii",
    "ConsentContext",
    # Models + exceptions
    "ConstitutionViolation",
    "ConnectorRefusal",
    "ApprovalRequest",
    "ActionProvenance",
    "ActionResult",
    # Base + registry
    "BaseActionConnector",
    "ConnectorRegistry",
    # Factories
    "get_stagehand_client",
    "get_windows_local_client",
    "get_real_world_api_client",
    "get_x_search_client",
    "build_connector_registry",
]
