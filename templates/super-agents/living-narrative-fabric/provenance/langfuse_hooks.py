# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Langfuse hooks (P113, Slot 5 / 2 of 2).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module is the optional cloud-side half of the Trust Engine. When
the user has a Langfuse account and exports
``LANGFUSE_PUBLIC_KEY`` + ``LANGFUSE_SECRET_KEY`` (and optionally
``LANGFUSE_HOST``), this module mirrors every Provenance Protocol call
into a Langfuse ``Trace`` so the synthesis can be inspected
side-by-side with token cost, latency, and error rates in the Langfuse
UI. When those env vars are unset OR the ``langfuse`` SDK is not
installed, every method becomes a no-op and the local JSONL log
in ``provenance/log.py`` continues to function unchanged.

Trace lifecycle
===============

* A ``Trace`` is created lazily on the first event seen for a given
  ``topic + version_id`` pair (or just topic when no version_id is
  available yet — the trace gets re-keyed once finalize fires).
* Every subsequent event becomes a ``Span`` under the trace, classified
  by the dotted ``event_type`` prefix (``ingest.``, ``connector.``,
  ``memory.``, ``synthesis.``, plus any other dotted prefix the
  orchestrator emits).
* Claims become ``Generation`` spans tagged with the source authority
  tier from ``DEFAULT_SOURCE_AUTHORITY``.
* Contradictions become ``Event`` spans with severity in metadata so
  the Langfuse UI's filter-by-metadata view can isolate them.
* The Langfuse SDK auto-flushes on a background thread; we do not call
  ``flush()`` explicitly except in a smoke-test cleanup hook.

Slot boundary contract
======================

* This module satisfies the orchestrator's ``ProvenanceLogger``
  Protocol on its own (3 methods: ``log_event``, ``log_claim``,
  ``log_contradiction``) so it CAN be injected as the sole provenance
  layer if a caller doesn't want JSONL.
* This module is composed by ``__init__.py`` alongside the local
  JSONL log; the composite fans out to both.
* This module makes ZERO changes to ``orchestrator.py``, ``graph.py``,
  the memory layer, or the connector layer.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Re-import dataclasses + exception from the orchestrator
# ---------------------------------------------------------------------------


def _import_orchestrator():
    try:
        from .. import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
DEFAULT_SOURCE_AUTHORITY = _orch.DEFAULT_SOURCE_AUTHORITY


# ---------------------------------------------------------------------------
# Soft Langfuse SDK import
# ---------------------------------------------------------------------------


try:
    from langfuse import Langfuse  # type: ignore
except Exception:  # pragma: no cover — soft import
    Langfuse = None  # type: ignore


# ---------------------------------------------------------------------------
# Recorded-call dataclass (also used by the smoke test as a no-op witness)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LangfuseCallRecord:
    """One in-memory record of every Langfuse-bound call.

    The smoke test asserts against this list so the no-op fallback path
    can prove that the right calls were *intended*, even when no SDK
    is installed and no real Langfuse trace was created.
    """

    method:       str       # "trace.create" | "span.create" | "generation.create" | "event.add" | "trace.update"
    name:         str
    metadata:     dict
    recorded_at:  datetime


# ---------------------------------------------------------------------------
# LangfuseProvenanceHooks — the cloud-side mirror
# ---------------------------------------------------------------------------


@dataclass
class LangfuseProvenanceHooks:
    """Optional Langfuse mirror of every Provenance Protocol call.

    The composite in ``__init__.py`` holds an instance of this class as
    its ``langfuse`` field.  When the SDK is installed AND the env vars
    are set, this class talks to Langfuse via its public client
    (``Langfuse(public_key=..., secret_key=...)``). Otherwise every
    public method is a no-op that records the call in
    ``recorded_calls`` so the smoke test can prove the wiring.
    """

    public_key:   Optional[str] = None
    secret_key:   Optional[str] = None
    host:         Optional[str] = None
    _client:      Optional[Any] = field(default=None, repr=False)
    _traces:      dict[str, Any] = field(default_factory=dict, repr=False)
    _spans:       dict[str, Any] = field(default_factory=dict, repr=False)
    _lock:        threading.Lock = field(default_factory=threading.Lock, repr=False)
    recorded_calls: list[LangfuseCallRecord] = field(default_factory=list, repr=False)

    # ---- construction ----------------------------------------------------

    def __post_init__(self) -> None:
        # Resolve env vars when the caller didn't override.
        self.public_key = self.public_key or os.environ.get("LANGFUSE_PUBLIC_KEY")
        self.secret_key = self.secret_key or os.environ.get("LANGFUSE_SECRET_KEY")
        self.host       = self.host       or os.environ.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"

        if Langfuse is not None and self.public_key and self.secret_key:
            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
            except Exception:
                self._client = None
        else:
            self._client = None

    # ---- introspection (used by composite + smoke test) ------------------

    @property
    def is_active(self) -> bool:
        """``True`` when a real Langfuse client is wired."""

        return self._client is not None

    @property
    def runtime_info(self) -> dict:
        return {
            "sdk_available":     Langfuse is not None,
            "public_key_set":    bool(self.public_key),
            "secret_key_set":    bool(self.secret_key),
            "host":              self.host,
            "active":            self.is_active,
            "trace_count":       len(self._traces),
            "span_count":        len(self._spans),
            "recorded_calls":    len(self.recorded_calls),
        }

    # ---- internal recording (used in both real + no-op paths) ------------

    def _record(self, method: str, name: str, metadata: dict) -> None:
        with self._lock:
            self.recorded_calls.append(LangfuseCallRecord(
                method=method,
                name=name,
                metadata=metadata,
                recorded_at=datetime.now(timezone.utc),
            ))

    # ---- trace lifecycle helpers -----------------------------------------

    def _trace_key(self, payload: dict) -> str:
        version_id = payload.get("version_id")
        topic = payload.get("topic") or "no-topic"
        # Prefer keying on version_id once available so the trace
        # corresponds 1-to-1 with one SynthesisVersion.
        return f"trace::{version_id or topic}"

    def _ensure_trace(self, payload: dict) -> Optional[Any]:
        key = self._trace_key(payload)
        with self._lock:
            existing = self._traces.get(key)
        if existing is not None:
            return existing

        meta = {
            "topic":       payload.get("topic"),
            "version_id":  payload.get("version_id"),
            "started_at":  datetime.now(timezone.utc).isoformat(),
        }
        self._record("trace.create", key, meta)

        if not self.is_active:
            placeholder = object()
            with self._lock:
                self._traces[key] = placeholder
            return placeholder

        try:
            trace = self._client.trace(  # type: ignore[union-attr]
                name=f"living-narrative-fabric::{payload.get('topic') or 'unknown'}",
                metadata=meta,
                tags=["living-narrative-fabric", "trust-engine"],
            )
            with self._lock:
                self._traces[key] = trace
            return trace
        except Exception:
            placeholder = object()
            with self._lock:
                self._traces[key] = placeholder
            return placeholder

    def _add_span(
        self,
        trace: Any,
        *,
        name: str,
        kind: str,
        metadata: dict,
        is_generation: bool = False,
    ) -> None:
        self._record(
            "generation.create" if is_generation else "span.create",
            name,
            {**metadata, "kind": kind},
        )
        if not self.is_active or trace is None:
            return
        try:
            if is_generation and hasattr(trace, "generation"):
                span = trace.generation(name=name, metadata={**metadata, "kind": kind})
            elif hasattr(trace, "span"):
                span = trace.span(name=name, metadata={**metadata, "kind": kind})
            else:
                return
            with self._lock:
                self._spans[name] = span
            # Auto-end the span at creation time — most events are
            # point-in-time, not durations. P115's UI may upgrade specific
            # spans (ingest, finalize) to time-bracketed durations later.
            try:
                if hasattr(span, "end"):
                    span.end()
            except Exception:
                pass
        except Exception:
            pass

    # ---- Protocol-required (3) ------------------------------------------

    def log_event(self, event_type: str, payload: dict) -> None:
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("log_event: event_type must be a non-empty string")
        if not isinstance(payload, dict):
            raise TypeError("log_event: payload must be a dict")
        # Constitution defense-in-depth on known fields:
        if event_type.startswith("claim.") and not (payload.get("source_id") or "").strip():
            raise ConstitutionViolation(
                f"Constitution violation: Langfuse event {event_type!r} carries an empty "
                f"source_id; provenance is mandatory."
            )

        trace = self._ensure_trace(payload)
        if event_type.startswith("synthesis.finalized"):
            # Surface the synthesis confidence + contradiction count on
            # the trace itself so Langfuse UI lists them at the top.
            self._record("trace.update", self._trace_key(payload), {
                "confidence_score":     payload.get("confidence_score"),
                "contradiction_count":  payload.get("contradiction_count"),
                "claim_count":          payload.get("claim_count"),
                "topic":                payload.get("topic"),
            })
            if self.is_active and trace is not None:
                try:
                    if hasattr(trace, "update"):
                        trace.update(metadata={
                            "confidence_score":    payload.get("confidence_score"),
                            "contradiction_count": payload.get("contradiction_count"),
                            "claim_count":         payload.get("claim_count"),
                        })
                except Exception:
                    pass

        self._add_span(
            trace,
            name=event_type,
            kind="event",
            metadata={"payload": _truncate_for_metadata(payload)},
        )

    def log_claim(self, claim: Claim, version_id: str) -> None:
        if not claim.source_id:
            raise ConstitutionViolation(
                f"Constitution violation: Langfuse log_claim refuses claim "
                f"{claim.claim_id!r} with empty source_id."
            )
        if not version_id:
            raise ValueError("log_claim: version_id must be a non-empty string")
        trace = self._ensure_trace({"version_id": version_id})
        authority = DEFAULT_SOURCE_AUTHORITY.get(claim.source, 0.5)
        self._add_span(
            trace,
            name=f"claim::{claim.source}::{claim.claim_id}",
            kind="claim",
            metadata={
                "version_id":       version_id,
                "subject":          claim.subject,
                "predicate":        claim.predicate,
                "value":            claim.value,
                "source":           claim.source,
                "source_id":        claim.source_id,
                "confidence":       float(claim.confidence),
                "source_authority": float(authority),
            },
            is_generation=True,
        )

    def log_contradiction(self, contradiction: Contradiction, version_id: str) -> None:
        if not contradiction.claim_ids:
            raise ConstitutionViolation(
                f"Constitution violation: Langfuse log_contradiction refuses "
                f"contradiction {contradiction.contradiction_id!r} with empty claim_ids."
            )
        if not version_id:
            raise ValueError("log_contradiction: version_id must be a non-empty string")
        trace = self._ensure_trace({"version_id": version_id})
        self._add_span(
            trace,
            name=f"contradiction::{contradiction.contradiction_id}",
            kind="contradiction",
            metadata={
                "version_id":          version_id,
                "subject":             contradiction.subject,
                "predicate":           contradiction.predicate,
                "claim_ids":           list(contradiction.claim_ids),
                "severity":            int(contradiction.severity),
                "severity_components": dict(contradiction.severity_components),
                "note":                contradiction.note,
            },
        )

    # ---- lifecycle -------------------------------------------------------

    def flush(self) -> None:
        """Best-effort flush of buffered Langfuse spans.

        Safe to call when the SDK isn't installed — falls through silently.
        """

        if not self.is_active:
            return
        try:
            if hasattr(self._client, "flush"):
                self._client.flush()  # type: ignore[union-attr]
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_for_metadata(payload: dict, max_chars: int = 2000) -> dict:
    """Stringify long values so Langfuse's metadata limit isn't blown."""

    out: dict = {}
    for k, v in (payload or {}).items():
        if isinstance(v, (dict, list)):
            try:
                import json as _json
                s = _json.dumps(v, ensure_ascii=False, default=str)
            except Exception:
                s = str(v)
        else:
            s = str(v)
        if len(s) > max_chars:
            s = s[:max_chars] + "...[truncated]"
        out[k] = s
    return out


__all__ = (
    "LangfuseCallRecord",
    "LangfuseProvenanceHooks",
)
