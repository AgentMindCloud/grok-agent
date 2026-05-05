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
"""Optional Langfuse observability hooks for the Self-Evolving Personal OS.

Langfuse is opt-in. The agent must work end-to-end with zero external
dependencies — Langfuse credentials missing, package not installed, or
network unavailable must all degrade silently to the stub backend.

Public surface:

- :class:`LangfuseClient`           the unified API both backends present
- :func:`get_langfuse_client`       cached process-wide instance
- :func:`reset_langfuse_client`     test helper to drop the cache
- :data:`BACKEND_NAME`              the runtime-selected backend name

Backend selection at import time:

1. The user must opt in via either a constructor flag (``opt_in=True``)
   or by setting ``LANGFUSE_PUBLIC_KEY`` + ``LANGFUSE_SECRET_KEY`` in
   the environment. Without opt-in we never even try to construct a
   real client — the user's privacy posture stays default-off.
2. If opted in, we attempt to import ``langfuse``. On ImportError we
   return the stub.
3. If the import succeeds we build the real ``Langfuse()`` client and
   verify connectivity by calling its ``auth_check()`` (when the method
   exists). Any failure → stub.

Even on the real backend, a per-call try/except wraps every Langfuse
method so a transient network blip can never break a brief run.

Built for xAI, Grok and the whole community on X — Langfuse hooks are
how we make the Personal OS an honest citizen of the existing LLMOps
ecosystem without giving up the local-first default.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse P121's PII redactor and AppData root so the stub backend can
# persist its trace mirrors next to the real provenance log.
from connectors import (  # type: ignore
    appdata_root,
    redact_pii,
)

__all__ = [
    "BACKEND_NAME",
    "LangfuseTraceContext",
    "LangfuseClient",
    "get_langfuse_client",
    "reset_langfuse_client",
    "stub_trace_path",
]


# --- Section 1. Constants ------------------------------------------------

_USER_AGENT = "grok-agent/self-evolving-personal-os/langfuse_hooks (Apache-2.0)"


def stub_trace_path() -> Path:
    """JSONL file the stub backend writes its mirror trace to."""
    return appdata_root() / "provenance" / "langfuse_stub_trace.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _have_credentials() -> bool:
    """Return True iff the minimum opt-in env vars are present."""
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


# --- Section 2. Trace context -------------------------------------------

@dataclass
class LangfuseTraceContext:
    """One trace per run.  Spans hang off a trace."""

    trace_id:    str
    run_id:      str
    user_id:     str
    started_at:  str
    name:        str = "self-evolving-personal-os.daily_brief"
    spans:       list[dict] = field(default_factory=list)

    def add_span(self, span: dict) -> None:
        self.spans.append(span)


# --- Section 3. Stub backend --------------------------------------------

class _StubLangfuseBackend:
    """Pure-Python no-op backend with disk mirror.

    The stub does three things:

    - Records the same span shape Langfuse would receive, mirrored to a
      JSONL file under AppData. This keeps the smoke test exercising the
      whole code path without network access.
    - Reports ``backend_name == 'stub:offline'`` so callers can render an
      honest UI badge.
    - Caps the trace file at a sane size so it never grows unbounded.
    """

    backend_name = "stub:offline"

    _MAX_FILE_BYTES = 4 * 1024 * 1024  # 4MB

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path = stub_trace_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ---- Trace lifecycle -------------------------------------------------

    def start_trace(
        self,
        *,
        run_id: str,
        user_id: str,
        name: str,
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
        *,
        outputs: dict | None = None,
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

    # ---- Span lifecycle --------------------------------------------------

    def trace_step(
        self,
        trace: LangfuseTraceContext,
        *,
        node_name: str,
        inputs: dict,
        outputs: dict,
        confidence: str | None,
        stub_reason: str | None,
        sources: list[str],
        duration_ms: float | None,
        error: str | None,
        correlation_id: str | None,
    ) -> dict:
        span = {
            "kind":           "span",
            "trace_id":       trace.trace_id,
            "run_id":         trace.run_id,
            "user_id":        trace.user_id,
            "node_name":      node_name,
            "inputs":         redact_pii(inputs or {}),
            "outputs":        redact_pii(outputs or {}),
            "confidence":     confidence,
            "stub_reason":    stub_reason,
            "sources":        list(sources or []),
            "duration_ms":    duration_ms,
            "error":          error,
            "correlation_id": correlation_id,
            "timestamp":      _now_iso(),
        }
        trace.add_span(span)
        self._write(span)
        return span

    def flush(self) -> None:  # pragma: no cover — disk write is sync
        return None

    # ---- Internals -------------------------------------------------------

    def _write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            try:
                # Cap the stub trace file to keep AppData footprint bounded.
                if (
                    self._path.exists()
                    and self._path.stat().st_size > self._MAX_FILE_BYTES
                ):
                    rotated = self._path.with_suffix(".rotated.jsonl")
                    try:
                        rotated.unlink(missing_ok=True)
                        self._path.rename(rotated)
                    except OSError:
                        # If we can't rotate, truncate by overwriting.
                        self._path.write_text("", encoding="utf-8")
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                # Stub-mirror writes are best-effort. A disk error must not
                # break the surrounding graph run.
                pass


# --- Section 4. Real Langfuse backend (lazy) ----------------------------

class _RealLangfuseBackend:
    """Thin wrapper around the production Langfuse SDK.

    Constructed only when (a) the user has opted in via env or constructor
    and (b) the ``langfuse`` package imports cleanly. Every call wraps the
    underlying SDK in try/except and falls back to a no-op on failure, so
    a Langfuse outage never breaks the agent.
    """

    backend_name = "langfuse"

    def __init__(self) -> None:
        from langfuse import Langfuse  # type: ignore

        self._client = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST"),
        )
        # Some SDK versions expose auth_check(); guard for the rest.
        try:
            check = getattr(self._client, "auth_check", None)
            if callable(check):
                check()
        except Exception as e:  # pragma: no cover — runtime failure path
            raise RuntimeError(f"langfuse auth_check failed: {e}") from e

    def start_trace(
        self,
        *,
        run_id: str,
        user_id: str,
        name: str,
        metadata: dict | None = None,
    ) -> LangfuseTraceContext:
        ctx = LangfuseTraceContext(
            trace_id=f"trace-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            user_id=user_id,
            started_at=_now_iso(),
            name=name,
        )
        try:
            self._client.trace(
                id=ctx.trace_id,
                name=name,
                user_id=user_id,
                metadata=redact_pii(metadata or {}),
                tags=["self-evolving-personal-os", "p124"],
            )
        except Exception:  # pragma: no cover — defensive
            pass
        return ctx

    def end_trace(
        self,
        trace: LangfuseTraceContext,
        *,
        outputs: dict | None = None,
        error: str | None = None,
    ) -> None:
        try:
            update = getattr(self._client, "trace", None)
            if callable(update):
                update(
                    id=trace.trace_id,
                    output=redact_pii(outputs or {}),
                    metadata={"error": error} if error else None,
                )
        except Exception:  # pragma: no cover — defensive
            pass

    def trace_step(
        self,
        trace: LangfuseTraceContext,
        *,
        node_name: str,
        inputs: dict,
        outputs: dict,
        confidence: str | None,
        stub_reason: str | None,
        sources: list[str],
        duration_ms: float | None,
        error: str | None,
        correlation_id: str | None,
    ) -> dict:
        span = {
            "trace_id":       trace.trace_id,
            "run_id":         trace.run_id,
            "user_id":        trace.user_id,
            "node_name":      node_name,
            "inputs":         redact_pii(inputs or {}),
            "outputs":        redact_pii(outputs or {}),
            "confidence":     confidence,
            "stub_reason":    stub_reason,
            "sources":        list(sources or []),
            "duration_ms":    duration_ms,
            "error":          error,
            "correlation_id": correlation_id,
            "timestamp":      _now_iso(),
        }
        try:
            self._client.span(
                trace_id=trace.trace_id,
                name=node_name,
                input=span["inputs"],
                output=span["outputs"],
                metadata={
                    "confidence":  confidence,
                    "stub_reason": stub_reason,
                    "sources":     sources,
                    "duration_ms": duration_ms,
                    "correlation_id": correlation_id,
                },
                level="ERROR" if error else "DEFAULT",
                status_message=error,
            )
        except Exception:  # pragma: no cover — defensive
            pass
        trace.add_span(span)
        return span

    def flush(self) -> None:
        try:
            flush = getattr(self._client, "flush", None)
            if callable(flush):
                flush()
        except Exception:  # pragma: no cover — defensive
            pass


# --- Section 5. Backend selection ---------------------------------------

def _select_backend(*, opt_in: bool) -> Any:
    """Return the active backend instance.

    ``opt_in`` defaults to False at the module entry; the caller is the
    one that decides whether the user has agreed to send any data to a
    cloud observability service.
    """
    if not opt_in and not _have_credentials():
        return _StubLangfuseBackend()
    if not opt_in and _have_credentials():
        # Credentials present but user did not pass opt_in=True — we
        # still default-stub for safety. The CLI would set opt_in=True
        # only after a positive user dialogue.
        return _StubLangfuseBackend()
    try:
        return _RealLangfuseBackend()
    except Exception:
        return _StubLangfuseBackend()


# Module-level backend (lazy/cached). The default is the stub — we only
# upgrade if get_langfuse_client(opt_in=True) is called explicitly.
BACKEND_NAME = "stub:offline"


# --- Section 6. Unified client surface ----------------------------------

class LangfuseClient:
    """Caller-facing Langfuse wrapper.

    Forwards calls to the active backend (real or stub) and exposes an
    extra :meth:`is_real` flag so callers can decide whether to render a
    "Tracing live" UI badge.
    """

    def __init__(self, *, opt_in: bool = False) -> None:
        self._opt_in  = bool(opt_in)
        self._backend = _select_backend(opt_in=self._opt_in)
        self._trace: LangfuseTraceContext | None = None

    # ---- Identity -------------------------------------------------------

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

    # ---- Trace lifecycle ------------------------------------------------

    def start_trace(
        self,
        *,
        run_id: str,
        user_id: str = "default",
        name: str = "self-evolving-personal-os.daily_brief",
        metadata: dict | None = None,
    ) -> LangfuseTraceContext:
        ctx = self._backend.start_trace(
            run_id=run_id, user_id=user_id, name=name, metadata=metadata,
        )
        self._trace = ctx
        return ctx

    def end_trace(
        self,
        *,
        outputs: dict | None = None,
        error: str | None = None,
    ) -> None:
        if self._trace is None:
            return
        self._backend.end_trace(self._trace, outputs=outputs, error=error)

    # ---- Span ------------------------------------------------------------

    def trace_step(
        self,
        *,
        node_name: str,
        inputs: dict,
        outputs: dict,
        confidence: str | None = None,
        stub_reason: str | None = None,
        sources: list[str] | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        if self._trace is None:
            # Auto-start a trace so callers don't have to remember to call
            # ``start_trace`` first. The ``run_id`` is synthesised here.
            self.start_trace(run_id=f"auto-{int(time.time()*1000)}")
        return self._backend.trace_step(
            self._trace,  # type: ignore[arg-type]
            node_name=node_name,
            inputs=inputs,
            outputs=outputs,
            confidence=confidence,
            stub_reason=stub_reason,
            sources=list(sources or []),
            duration_ms=duration_ms,
            error=error,
            correlation_id=correlation_id,
        )

    # ---- Flush ----------------------------------------------------------

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
    """Drop the cached client (used by smoke tests for hermeticity)."""
    global _LF_CLIENT, BACKEND_NAME
    with _LF_LOCK:
        _LF_CLIENT = None
        BACKEND_NAME = "stub:offline"


# --- Section 8. Convenience: span_from_record ---------------------------

def span_from_record(record: Any) -> dict:
    """Adapt a P124 :class:`provenance.log.ProvenanceRecord` to Langfuse.

    Used by :mod:`graph` so the same wrapper that writes the JSONL row
    can pass the canonical dict through to whichever Langfuse backend
    (real or stub) the user has opted into.
    """
    return {
        "node_name":      getattr(record, "node_name", None),
        "inputs":         dict(getattr(record, "inputs_redacted", {}) or {}),
        "outputs":        dict(getattr(record, "outputs_redacted", {}) or {}),
        "confidence":     getattr(record, "confidence", None),
        "stub_reason":    getattr(record, "stub_reason", None),
        "sources":        list(getattr(record, "sources", []) or []),
        "duration_ms":    getattr(record, "duration_ms", None),
        "error":          getattr(record, "error", None),
        "correlation_id": getattr(record, "correlation_id", None),
    }
