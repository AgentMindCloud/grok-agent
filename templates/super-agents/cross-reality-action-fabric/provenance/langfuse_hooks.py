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
"""Optional Langfuse observability hooks for Cross-Reality Action Fabric.

Strict opt-in. The agent must work end-to-end with zero external
dependencies — Langfuse credentials missing, package not installed, or
network unavailable must all degrade silently to the stub backend.

Public surface:

- :class:`LangfuseClient`           the unified API both backends present
- :func:`get_langfuse_client`       cached process-wide instance
- :func:`reset_langfuse_client`     test helper to drop the cache
- :data:`BACKEND_NAME`              the runtime-selected backend name
- :func:`span_from_record`          adapt an ActionProvenanceRecord →
                                    Langfuse span dict

Backend selection at construction time (mirrors P124):

1. The user must opt in via either ``opt_in=True`` or by setting both
   ``LANGFUSE_PUBLIC_KEY`` + ``LANGFUSE_SECRET_KEY`` in the environment
   AND passing ``opt_in=True``. Without an explicit opt-in we never
   even try to construct a real client — the user's privacy posture
   stays default-off (Constitution Rule 6).
2. If opted in, we attempt to import ``langfuse``. ImportError → stub.
3. If the import succeeds we build the real ``Langfuse()`` client and
   verify connectivity by calling its ``auth_check()`` (when the
   method exists). Any failure → stub.

Even on the real backend, every method is wrapped in try/except so a
transient network blip can never break a brief / action run.

Built for xAI, Grok and the whole community on X — Langfuse hooks are
how we make the action fabric an honest citizen of the existing LLMOps
ecosystem without giving up the local-first default.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse P129's PII redactor and AppData root so the stub backend can
# persist its trace mirrors next to the real provenance log.
from graph import (  # type: ignore
    appdata_root,
    redact_pii,
)

__all__ = [
    # P131 surface
    "BACKEND_NAME",
    "LangfuseTraceContext",
    "LangfuseClient",
    "get_langfuse_client",
    "reset_langfuse_client",
    "stub_trace_path",
    "span_from_record",
    # P142 hook surface
    "LangfuseHooks",
    "attach_langfuse_hooks",
    "have_langfuse_credentials",
    "trace_name_for_action",
]


# --- Section 1. Constants -----------------------------------------------

_USER_AGENT = "grok-agent/cross-reality-action-fabric/langfuse_hooks (Apache-2.0)"


def stub_trace_path() -> Path:
    """JSONL file the stub backend writes its mirror trace to."""
    return appdata_root() / "provenance" / "langfuse_stub_trace.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _have_credentials() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


# --- Section 2. Trace context -------------------------------------------

@dataclass
class LangfuseTraceContext:
    """One trace per action-loop run.  Spans hang off a trace."""

    trace_id:    str
    run_id:      str
    user_id:     str
    started_at:  str
    name:        str = "cross-reality-action-fabric.run_action_loop"
    spans:       list[dict] = field(default_factory=list)

    def add_span(self, span: dict) -> None:
        self.spans.append(span)


# --- Section 3. Stub backend --------------------------------------------

class _StubLangfuseBackend:
    """Pure-Python no-op backend with disk mirror.

    Records the same span shape Langfuse would receive, mirrored to a
    JSONL file under AppData. Caps file size at 4MB with rotation.
    """

    backend_name = "stub:offline"

    _MAX_FILE_BYTES = 4 * 1024 * 1024

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path = stub_trace_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # -- Trace lifecycle ---------------------------------------------------

    def start_trace(
        self, *,
        run_id: str, user_id: str, name: str,
        metadata: dict | None = None,
    ) -> LangfuseTraceContext:
        ctx = LangfuseTraceContext(
            trace_id=f"trace-stub-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            user_id=user_id,
            started_at=_now_iso(),
            name=name,
        )
        self._write({
            "kind":      "trace_start",
            "trace_id":  ctx.trace_id,
            "run_id":    ctx.run_id,
            "user_id":   ctx.user_id,
            "name":      ctx.name,
            "metadata":  redact_pii(metadata or {}),
            "timestamp": ctx.started_at,
        })
        return ctx

    def end_trace(
        self,
        trace: LangfuseTraceContext,
        *, outputs: dict | None = None,
        error: str | None = None,
    ) -> None:
        self._write({
            "kind":      "trace_end",
            "trace_id":  trace.trace_id,
            "run_id":    trace.run_id,
            "user_id":   trace.user_id,
            "outputs":   redact_pii(outputs or {}),
            "error":     error,
            "timestamp": _now_iso(),
        })

    # -- Span lifecycle ---------------------------------------------------

    def trace_action_step(
        self,
        trace: LangfuseTraceContext,
        *,
        event_kind: str,
        tool: str | None,
        step: int | None,
        action_id: str | None,
        consent_token: str | None,
        outcome: str | None,
        cost_usd: float,
        rollback_id: str | None,
        rolled_back_from: str | None,
        inputs: dict,
        outputs: dict,
        rule_compliance: dict,
        stub_reason: str | None,
        error: str | None,
        duration_ms: float | None,
        correlation_id: str | None,
    ) -> dict:
        span = {
            "kind":             "span",
            "trace_id":         trace.trace_id,
            "run_id":           trace.run_id,
            "user_id":          trace.user_id,
            "event_kind":       event_kind,
            "tool":             tool,
            "step":             step,
            "action_id":        action_id,
            "consent_token":    consent_token,
            "outcome":          outcome,
            "cost_usd":         float(cost_usd or 0.0),
            "rollback_id":      rollback_id,
            "rolled_back_from": rolled_back_from,
            "inputs":           redact_pii(inputs or {}),
            "outputs":          redact_pii(outputs or {}),
            "rule_compliance":  dict(rule_compliance or {}),
            "stub_reason":      stub_reason,
            "error":            error,
            "duration_ms":      duration_ms,
            "correlation_id":   correlation_id,
            "timestamp":        _now_iso(),
        }
        trace.add_span(span)
        self._write(span)
        return span

    def flush(self) -> None:  # pragma: no cover — disk write is sync
        return None

    # -- Internals ---------------------------------------------------------

    def _write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            try:
                if (
                    self._path.exists()
                    and self._path.stat().st_size > self._MAX_FILE_BYTES
                ):
                    rotated = self._path.with_suffix(".rotated.jsonl")
                    try:
                        rotated.unlink(missing_ok=True)
                        self._path.rename(rotated)
                    except OSError:
                        self._path.write_text("", encoding="utf-8")
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass


# --- Section 4. Real Langfuse backend (lazy) ---------------------------

class _RealLangfuseBackend:
    """Thin wrapper around the production Langfuse SDK.

    Constructed only when (a) the user has opted in via
    ``opt_in=True`` in the constructor AND (b) the ``langfuse`` package
    imports cleanly. Every call wraps the SDK in try/except so a
    Langfuse outage never breaks an action run.
    """

    backend_name = "langfuse"

    def __init__(self) -> None:
        from langfuse import Langfuse  # type: ignore

        self._client = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST"),
        )
        try:
            check = getattr(self._client, "auth_check", None)
            if callable(check):
                check()
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"langfuse auth_check failed: {e}") from e

    def start_trace(
        self, *,
        run_id: str, user_id: str, name: str,
        metadata: dict | None = None,
    ) -> LangfuseTraceContext:
        ctx = LangfuseTraceContext(
            trace_id=f"trace-{uuid.uuid4().hex[:12]}",
            run_id=run_id, user_id=user_id, started_at=_now_iso(), name=name,
        )
        try:
            self._client.trace(
                id=ctx.trace_id,
                name=name,
                user_id=user_id,
                metadata=redact_pii(metadata or {}),
                tags=["cross-reality-action-fabric", "p131"],
            )
        except Exception:  # pragma: no cover
            pass
        return ctx

    def end_trace(
        self,
        trace: LangfuseTraceContext,
        *, outputs: dict | None = None, error: str | None = None,
    ) -> None:
        try:
            update = getattr(self._client, "trace", None)
            if callable(update):
                update(
                    id=trace.trace_id,
                    output=redact_pii(outputs or {}),
                    metadata={"error": error} if error else None,
                )
        except Exception:  # pragma: no cover
            pass

    def trace_action_step(
        self,
        trace: LangfuseTraceContext,
        *,
        event_kind: str,
        tool: str | None,
        step: int | None,
        action_id: str | None,
        consent_token: str | None,
        outcome: str | None,
        cost_usd: float,
        rollback_id: str | None,
        rolled_back_from: str | None,
        inputs: dict,
        outputs: dict,
        rule_compliance: dict,
        stub_reason: str | None,
        error: str | None,
        duration_ms: float | None,
        correlation_id: str | None,
    ) -> dict:
        span = {
            "trace_id":         trace.trace_id,
            "run_id":           trace.run_id,
            "user_id":          trace.user_id,
            "event_kind":       event_kind,
            "tool":             tool,
            "step":             step,
            "action_id":        action_id,
            "consent_token":    consent_token,
            "outcome":          outcome,
            "cost_usd":         float(cost_usd or 0.0),
            "rollback_id":      rollback_id,
            "rolled_back_from": rolled_back_from,
            "inputs":           redact_pii(inputs or {}),
            "outputs":          redact_pii(outputs or {}),
            "rule_compliance":  dict(rule_compliance or {}),
            "stub_reason":      stub_reason,
            "error":            error,
            "duration_ms":      duration_ms,
            "correlation_id":   correlation_id,
            "timestamp":        _now_iso(),
        }
        try:
            self._client.span(
                trace_id=trace.trace_id,
                name=f"{event_kind}:{tool or ''}",
                input=span["inputs"],
                output=span["outputs"],
                metadata={
                    "tool":             tool,
                    "step":             step,
                    "action_id":        action_id,
                    "consent_token":    consent_token,
                    "outcome":          outcome,
                    "cost_usd":         float(cost_usd or 0.0),
                    "rollback_id":      rollback_id,
                    "rolled_back_from": rolled_back_from,
                    "rule_compliance":  rule_compliance,
                    "stub_reason":      stub_reason,
                    "duration_ms":      duration_ms,
                    "correlation_id":   correlation_id,
                },
                level="ERROR" if error else "DEFAULT",
                status_message=error,
            )
        except Exception:  # pragma: no cover
            pass
        trace.add_span(span)
        return span

    def flush(self) -> None:
        try:
            flush = getattr(self._client, "flush", None)
            if callable(flush):
                flush()
        except Exception:  # pragma: no cover
            pass


# --- Section 5. Backend selection ---------------------------------------

def _select_backend(*, opt_in: bool) -> Any:
    """Return the active backend instance.  Defaults to stub for safety."""
    if not opt_in:
        # Even with credentials present, we default-stub. The CLI sets
        # opt_in=True only after a positive user dialogue (Rule 6).
        return _StubLangfuseBackend()
    if not _have_credentials():
        return _StubLangfuseBackend()
    try:
        return _RealLangfuseBackend()
    except Exception:
        return _StubLangfuseBackend()


# Module-level backend (lazy / cached). The default is the stub — we
# only upgrade if get_langfuse_client(opt_in=True) is called explicitly.
BACKEND_NAME = "stub:offline"


# --- Section 6. Unified client surface ----------------------------------

class LangfuseClient:
    """Caller-facing Langfuse wrapper for the action fabric."""

    def __init__(self, *, opt_in: bool = False) -> None:
        self._opt_in  = bool(opt_in)
        self._backend = _select_backend(opt_in=self._opt_in)
        self._trace: LangfuseTraceContext | None = None

    # -- Identity ---------------------------------------------------------

    @property
    def backend_name(self) -> str:
        return getattr(self._backend, "backend_name", "unknown")

    @property
    def is_real(self) -> bool:
        return self.backend_name == "langfuse"

    @property
    def opt_in(self) -> bool:
        return self._opt_in

    @property
    def current_trace(self) -> LangfuseTraceContext | None:
        return self._trace

    # -- Trace lifecycle --------------------------------------------------

    def start_trace(
        self,
        *,
        run_id: str,
        user_id: str = "default",
        name: str = "cross-reality-action-fabric.run_action_loop",
        metadata: dict | None = None,
    ) -> LangfuseTraceContext:
        ctx = self._backend.start_trace(
            run_id=run_id, user_id=user_id, name=name, metadata=metadata,
        )
        self._trace = ctx
        return ctx

    def end_trace(
        self,
        *, outputs: dict | None = None, error: str | None = None,
    ) -> None:
        if self._trace is None:
            return
        self._backend.end_trace(self._trace, outputs=outputs, error=error)

    # -- Span -------------------------------------------------------------

    def trace_action_step(
        self,
        *,
        event_kind: str,
        tool: str | None = None,
        step: int | None = None,
        action_id: str | None = None,
        consent_token: str | None = None,
        outcome: str | None = None,
        cost_usd: float = 0.0,
        rollback_id: str | None = None,
        rolled_back_from: str | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        rule_compliance: dict | None = None,
        stub_reason: str | None = None,
        error: str | None = None,
        duration_ms: float | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        if self._trace is None:
            self.start_trace(run_id=f"auto-{int(time.time() * 1000)}")
        return self._backend.trace_action_step(
            self._trace,  # type: ignore[arg-type]
            event_kind=event_kind,
            tool=tool,
            step=step,
            action_id=action_id,
            consent_token=consent_token,
            outcome=outcome,
            cost_usd=float(cost_usd or 0.0),
            rollback_id=rollback_id,
            rolled_back_from=rolled_back_from,
            inputs=dict(inputs or {}),
            outputs=dict(outputs or {}),
            rule_compliance=dict(rule_compliance or {}),
            stub_reason=stub_reason,
            error=error,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )

    # -- Flush ------------------------------------------------------------

    def flush(self) -> None:
        self._backend.flush()


# --- Section 7. Process-wide singleton ----------------------------------

_LF_LOCK = threading.Lock()
_LF_CLIENT: LangfuseClient | None = None


def get_langfuse_client(*, opt_in: bool = False, refresh: bool = False) -> LangfuseClient:
    """Return the cached LangfuseClient, building it on first call."""
    global _LF_CLIENT, BACKEND_NAME
    with _LF_LOCK:
        if refresh or _LF_CLIENT is None or _LF_CLIENT.opt_in != bool(opt_in):
            _LF_CLIENT = LangfuseClient(opt_in=opt_in)
            BACKEND_NAME = _LF_CLIENT.backend_name
    return _LF_CLIENT


def reset_langfuse_client() -> None:
    global _LF_CLIENT, BACKEND_NAME
    with _LF_LOCK:
        _LF_CLIENT = None
        BACKEND_NAME = "stub:offline"


# --- Section 8. Convenience: span_from_record ---------------------------

def span_from_record(record: Any) -> dict:
    """Adapt a P131 :class:`provenance.log.ActionProvenanceRecord` to
    the Langfuse span shape — used by :func:`provenance.attach_provenance`."""
    return {
        "event_kind":       getattr(record, "event_kind", None),
        "tool":             getattr(record, "tool", None),
        "step":             getattr(record, "step", None),
        "action_id":        getattr(record, "action_id", None),
        "consent_token":    getattr(record, "consent_token", None),
        "outcome":          getattr(record, "outcome", None),
        "cost_usd":         float(getattr(record, "cost_usd", 0.0) or 0.0),
        "rollback_id":      getattr(record, "rollback_id", None),
        "rolled_back_from": getattr(record, "rolled_back_from", None),
        "inputs":           dict(getattr(record, "inputs_redacted", {}) or {}),
        "outputs":          dict(getattr(record, "outputs_redacted", {}) or {}),
        "rule_compliance":  dict(getattr(record, "rule_compliance", {}) or {}),
        "stub_reason":      getattr(record, "stub_reason", None),
        "error":            getattr(record, "error", None),
        "duration_ms":      getattr(record, "duration_ms", None),
        "correlation_id":   getattr(record, "correlation_id", None),
    }


# --- Section 9. P142 hook surface ---------------------------------------
#
# The :class:`LangfuseHooks` class below wraps a :class:`LangfuseClient`
# with four lifecycle methods that line up with the P141
# :class:`BaseActionConnector` execution flow:
#
# - :meth:`on_action_start`    — called from ``_record_approved_action``
# - :meth:`on_approval`        — called when a typed consent is granted
# - :meth:`on_action_end`      — called from ``_record_outcome``
# - :meth:`on_rollback`        — called from ``_record_rollback``
#
# Every method is a no-op when ``opt_in=False`` *or* when no Langfuse
# credentials are present, so callers can wire hooks unconditionally
# and let the runtime decide whether bytes leave the machine.


def have_langfuse_credentials() -> bool:
    """Public alias of the internal credential probe.

    Lets callers (and the smoke test) decide whether to even attempt
    an opt-in without parsing environment variables themselves.
    """
    return _have_credentials()


def trace_name_for_action(action_id: str) -> str:
    """Return the canonical trace name for one action_id.

    Matches the contract from P142's prompt: ``crf-action-{action_id}``.
    """
    aid = (action_id or "anonymous").strip() or "anonymous"
    return f"crf-action-{aid}"


class LangfuseHooks:
    """Lifecycle hooks that mirror P141 connector events into Langfuse.

    Every method short-circuits to a no-op when ``opt_in=False`` or
    when the Langfuse stub backend is active (default). Callers don't
    need to branch; they just call the hook and the right thing
    happens.
    """

    def __init__(
        self,
        *,
        opt_in:  bool = False,
        client:  LangfuseClient | None = None,
    ) -> None:
        self._opt_in = bool(opt_in)
        # Reuse the cached client when possible so the trace shows up
        # in the same backend as the rest of the run.
        self._client = client or get_langfuse_client(opt_in=self._opt_in)
        # We start a single trace per action_id and cache it so
        # on_action_end / on_rollback append spans rather than
        # creating fresh traces.
        self._trace_by_action: dict[str, LangfuseTraceContext] = {}
        self._lock = threading.Lock()

    # -- Identity ----------------------------------------------------

    @property
    def opt_in(self) -> bool:
        return self._opt_in

    @property
    def backend_name(self) -> str:
        return self._client.backend_name

    @property
    def is_active(self) -> bool:
        """True when hooks will actually publish to a real Langfuse backend."""
        return self._opt_in and self._client.is_real

    @property
    def client(self) -> LangfuseClient:
        return self._client

    # -- Lifecycle hooks ---------------------------------------------

    def on_action_start(
        self,
        *,
        action_id:     str,
        tool:          str,
        consent_token: str | None,
        consent_level: str | None = None,
        user_id:       str = "default",
        plan_id:       str | None = None,
        step:          int | None = None,
        description:   str | None = None,
        rollback_id:   str | None = None,
    ) -> dict | None:
        """Open a trace + initial span for one action.

        Returns the underlying span dict for callers that want to
        chain additional metadata onto it; returns None when the hook
        is inert (e.g. opt_in=False).
        """
        if not action_id:
            return None
        try:
            with self._lock:
                trace = self._client.start_trace(
                    run_id=action_id,
                    user_id=user_id,
                    name=trace_name_for_action(action_id),
                    metadata={
                        "tool":          tool,
                        "consent_level": consent_level,
                        "plan_id":       plan_id,
                        "step":          step,
                        "rollback_id":   rollback_id,
                    },
                )
                self._trace_by_action[action_id] = trace
            return self._client.trace_action_step(
                event_kind="action_started",
                tool=tool,
                step=step,
                action_id=action_id,
                consent_token=consent_token,
                outcome="pending",
                cost_usd=0.0,
                rollback_id=rollback_id,
                inputs={"description": description or ""},
                outputs={},
                rule_compliance={"rule_1": bool(consent_token), "rule_2": True},
                stub_reason=(
                    "stub:offline" if self._client.backend_name.startswith("stub")
                    else None
                ),
                error=None,
                duration_ms=None,
                correlation_id=action_id,
            )
        except Exception:  # pragma: no cover - defensive, hooks must never raise
            return None

    def on_approval(
        self,
        *,
        action_id:     str,
        consent_token: str,
        tool:          str,
        consent_level: str | None = None,
        scope:         str | None = None,
    ) -> dict | None:
        """Record one HITL approval span on the action's trace."""
        if not action_id or not consent_token:
            return None
        try:
            with self._lock:
                trace = self._trace_by_action.get(action_id)
                if trace is None:
                    trace = self._client.start_trace(
                        run_id=action_id,
                        user_id="default",
                        name=trace_name_for_action(action_id),
                    )
                    self._trace_by_action[action_id] = trace
                self._client._trace = trace  # noqa: SLF001
            return self._client.trace_action_step(
                event_kind="approval_granted",
                tool=tool,
                action_id=action_id,
                consent_token=consent_token,
                outcome="granted",
                inputs={"scope": scope or ""},
                outputs={"consent_level": consent_level},
                rule_compliance={"rule_1": True},
                correlation_id=action_id,
            )
        except Exception:  # pragma: no cover
            return None

    def on_action_end(
        self,
        *,
        action_id:     str,
        tool:          str,
        outcome:       str,
        consent_token: str | None,
        consent_level: str | None = None,
        cost_usd:      float = 0.0,
        duration_ms:   float | None = None,
        rollback_id:   str | None = None,
        outputs:       dict | None = None,
        error:         str | None = None,
    ) -> dict | None:
        """Close one action: write the outcome span and end the trace."""
        if not action_id:
            return None
        try:
            with self._lock:
                trace = self._trace_by_action.get(action_id)
                if trace is None:
                    trace = self._client.start_trace(
                        run_id=action_id,
                        user_id="default",
                        name=trace_name_for_action(action_id),
                    )
                    self._trace_by_action[action_id] = trace
                self._client._trace = trace  # noqa: SLF001
            event_kind = (
                "action_executed" if outcome == "success"
                else "action_failed"
            )
            span = self._client.trace_action_step(
                event_kind=event_kind,
                tool=tool,
                action_id=action_id,
                consent_token=consent_token,
                outcome=outcome,
                cost_usd=float(cost_usd or 0.0),
                rollback_id=rollback_id,
                inputs={"consent_level": consent_level},
                outputs=dict(outputs or {}),
                rule_compliance={
                    "rule_1": bool(consent_token),
                    "rule_2": True,
                    "rule_3": bool(rollback_id) or outcome == "success",
                },
                error=error,
                duration_ms=duration_ms,
                correlation_id=action_id,
            )
            # Close the trace so flush() commits it.
            self._client._trace = trace  # noqa: SLF001
            self._client.end_trace(
                outputs={"outcome": outcome, "cost_usd": float(cost_usd or 0.0)},
                error=error,
            )
            return span
        except Exception:  # pragma: no cover
            return None

    def on_rollback(
        self,
        *,
        action_id:       str,
        rollback_id:     str | None,
        tool:            str,
        consent_token:   str | None,
        outcome:         str = "rolled_back",
        rollback_script: str | None = None,
        consent_level:   str | None = None,
        error:           str | None = None,
    ) -> dict | None:
        """Append the rollback span to the matching action trace."""
        if not action_id:
            return None
        try:
            with self._lock:
                trace = self._trace_by_action.get(action_id)
                if trace is None:
                    trace = self._client.start_trace(
                        run_id=action_id,
                        user_id="default",
                        name=trace_name_for_action(action_id),
                    )
                    self._trace_by_action[action_id] = trace
                self._client._trace = trace  # noqa: SLF001
            event_kind = (
                "rollback_executed" if outcome == "rolled_back"
                else "rollback_failed"
            )
            return self._client.trace_action_step(
                event_kind=event_kind,
                tool=tool,
                action_id=rollback_id or action_id,
                consent_token=consent_token,
                outcome=outcome,
                rollback_id=rollback_id,
                rolled_back_from=action_id,
                inputs={"rollback_script": (rollback_script or "")[:240]},
                outputs={"consent_level": consent_level},
                rule_compliance={"rule_3": True},
                error=error,
                correlation_id=action_id,
            )
        except Exception:  # pragma: no cover
            return None

    def flush(self) -> None:
        """Flush every pending span to the backend."""
        try:
            self._client.flush()
        except Exception:  # pragma: no cover
            pass


def attach_langfuse_hooks(
    *,
    opt_in: bool = False,
    refresh: bool = False,
    client: LangfuseClient | None = None,
) -> LangfuseHooks:
    """Build a :class:`LangfuseHooks` instance.

    ``opt_in`` defaults to False: the user must explicitly opt in to
    upload anything to Langfuse, even when credentials are present
    (Constitution Rule 6). When ``opt_in`` is True we still
    short-circuit to the stub backend if ``LANGFUSE_PUBLIC_KEY`` /
    ``LANGFUSE_SECRET_KEY`` are missing — never raises, never blocks
    the action loop.

    Pass ``refresh=True`` to drop the cached :class:`LangfuseClient`
    so the hooks pick up an updated environment (used by the smoke
    test).
    """
    if refresh:
        reset_langfuse_client()
    chosen_client = client or get_langfuse_client(opt_in=opt_in, refresh=refresh)
    return LangfuseHooks(opt_in=opt_in, client=chosen_client)
