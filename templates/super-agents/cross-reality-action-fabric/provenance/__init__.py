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
"""Provenance package for Cross-Reality Action Fabric (P131 + P142).

Two modules:

- :mod:`provenance.log`             local-first JSONL action audit logger
                                    + Markdown report exporter with
                                    rollback chains. P142 added an
                                    action-centric :class:`ProvenanceLogger`
                                    subclass with ``query_by_action_id`` /
                                    ``query_by_consent_level`` /
                                    ``query_by_date_range`` and JSON +
                                    Markdown exporters with clickable
                                    action_id anchors.
- :mod:`provenance.langfuse_hooks`  optional Langfuse observability with
                                    full stub fallback (default OFF) plus
                                    P142 :class:`LangfuseHooks` lifecycle
                                    methods (``on_action_start`` /
                                    ``on_approval`` / ``on_action_end`` /
                                    ``on_rollback``).

This package re-exports the most-used names so callers can write
``from provenance import ProvenanceLogger`` rather than chasing the
deeper module paths.

It exposes two attach helpers:

- :func:`attach_provenance` — the canonical P131 bridge that wires the
  logger + (optional) memory into :func:`graph.run_action_loop`.
- :func:`attach_to_connectors` — P142 helper that auto-instruments a
  :class:`connectors.ConnectorRegistry` so every connector call writes
  one provenance entry per stage (approval / outcome / rollback) and
  fires the matching :class:`LangfuseHooks` callback.

Both helpers are **additive** — they never modify ``agent.py``,
``graph.py``, the memory package, or the connectors package source.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

from typing import Any, Callable

# P131 modules
from provenance.log import (  # type: ignore  # noqa: F401
    ACTION_EVENT_KINDS,
    ActionProvenanceRecord,
    ALL_RULE_NUMBERS,
    EVENT_KINDS,
    LocalProvenanceLogger,
    P142_SCHEMA_VERSION,
    ProvenanceEntry,
    ProvenanceLogger,
    ROLLBACK_OUTCOME,
    RollbackChain,
    current_log_path,
    export_audit_json,
    export_audit_markdown,
    export_audit_report,
    get_default_logger,
    get_provenance_logger,
    log_path_for,
    make_action_id,
    make_rollback_id,
    make_run_id,
    provenance_root,
    reset_default_logger,
    reset_provenance_logger,
    summarise_run,
)
from provenance.langfuse_hooks import (  # type: ignore  # noqa: F401
    LangfuseClient,
    LangfuseHooks,
    LangfuseTraceContext,
    attach_langfuse_hooks,
    get_langfuse_client,
    have_langfuse_credentials,
    reset_langfuse_client,
    span_from_record,
    stub_trace_path,
    trace_name_for_action,
)
from provenance.langfuse_hooks import BACKEND_NAME as LANGFUSE_BACKEND_NAME  # type: ignore  # noqa: F401,E501

# P129 + P130 imports for the attach helper
from graph import run_action_loop as _graph_run_action_loop  # type: ignore
from memory import attach_memory_store as _memory_attach  # type: ignore
from memory import MEMORY_WRITE_GATE  # type: ignore

__all__ = [
    # log — P131
    "ActionProvenanceRecord",
    "ALL_RULE_NUMBERS",
    "EVENT_KINDS",
    "LocalProvenanceLogger",
    "ROLLBACK_OUTCOME",
    "current_log_path",
    "export_audit_report",
    "get_default_logger",
    "log_path_for",
    "make_action_id",
    "make_rollback_id",
    "make_run_id",
    "provenance_root",
    "reset_default_logger",
    "summarise_run",
    # log — P142
    "ACTION_EVENT_KINDS",
    "P142_SCHEMA_VERSION",
    "ProvenanceEntry",
    "ProvenanceLogger",
    "RollbackChain",
    "export_audit_json",
    "export_audit_markdown",
    "get_provenance_logger",
    "reset_provenance_logger",
    # langfuse — P131
    "LangfuseClient",
    "LangfuseTraceContext",
    "get_langfuse_client",
    "reset_langfuse_client",
    "span_from_record",
    "stub_trace_path",
    "LANGFUSE_BACKEND_NAME",
    # langfuse — P142
    "LangfuseHooks",
    "attach_langfuse_hooks",
    "have_langfuse_credentials",
    "trace_name_for_action",
    # bridges
    "attach_provenance",
    "attach_to_connectors",
]


# --- The attach bridge --------------------------------------------------

def attach_provenance(
    *,
    user_id: str = "default",
    consent: Any = None,
    langfuse_opt_in: bool = False,
    with_memory: bool = True,
    refresh: bool = False,
) -> tuple[LocalProvenanceLogger, LangfuseClient, Callable[..., dict]]:
    """Wire the provenance layer + (optional) memory layer into
    :func:`graph.run_action_loop`.

    Returns ``(logger, langfuse_client, run_with_provenance)``:

    - ``logger`` writes one ActionProvenanceRecord per Constitution
      event to ``$env:LOCALAPPDATA\\grok-agent\\
      cross-reality-action-fabric\\provenance\\YYYY-MM-DD.jsonl``.
    - ``langfuse_client`` mirrors every event into the Langfuse
      backend (real if opted in + creds present, otherwise stub).
    - ``run_with_provenance`` is a drop-in replacement for
      :func:`graph.run_action_loop` that:
        1. starts a Langfuse trace,
        2. runs the action loop (optionally through the P130 memory
           wrapper so memory writes happen first),
        3. ingests every action / approval / rollback row through
           the JSONL logger,
        4. mirrors each event into Langfuse,
        5. ends the trace + flushes.

    Importantly, the wrapper is **additive**. It never touches
    ``agent.py``, ``graph.py``, or the memory package.

    Caller-facing example
    ---------------------

    .. code-block:: python

        from provenance import attach_provenance, LANGFUSE_BACKEND_NAME
        from memory import MEMORY_WRITE_GATE
        from graph import ConsentContext

        consent = ConsentContext.from_iterable(
            [..., MEMORY_WRITE_GATE], consent_token="cli-...",
        )
        logger, lf, run = attach_provenance(
            user_id="alice", consent=consent, langfuse_opt_in=False,
        )
        out = run(force_stub=True, auto_approve=True, user_request="hi")
        # out['memory_ingest']     -> per-kind counters (P130)
        # out['provenance_ingest'] -> per-event-kind counters (P131)

    The default ``langfuse_opt_in=False`` keeps every byte on the
    user's machine (Constitution Rule 6). Pass ``langfuse_opt_in=True``
    only after a typed user dialogue.
    """
    logger = LocalProvenanceLogger(user_id=user_id)
    if refresh:
        reset_langfuse_client()
    langfuse = get_langfuse_client(opt_in=langfuse_opt_in, refresh=refresh)

    if with_memory:
        memory_client, run_with_memory = _memory_attach(
            user_id=user_id, force_stub=True, consent=consent,
        )
    else:
        memory_client = None
        run_with_memory = None

    def run_with_provenance(**kwargs: Any) -> dict:
        # 1. Start a fresh Langfuse trace per run.
        run_id = logger.new_run()
        langfuse.start_trace(
            run_id=run_id,
            user_id=user_id,
            metadata={
                "user_request":  kwargs.get("user_request"),
                "force_stub":    kwargs.get("force_stub"),
                "auto_approve":  kwargs.get("auto_approve"),
            },
        )

        # 2. Run the action loop. Prefer the memory-attached wrapper so
        #    P130 memory writes happen first; fall back to bare graph.
        if run_with_memory is not None:
            out = run_with_memory(**kwargs)
        else:
            out = _graph_run_action_loop(**kwargs)

        # 3. Bulk-ingest every Constitution-relevant event into JSONL.
        ingest = logger.record_run(out)
        out.setdefault("provenance_ingest", ingest)

        # 4. Mirror every just-written record into the Langfuse backend.
        for record in logger.query_by_run_id(run_id):
            langfuse.trace_action_step(**span_from_record(record))

        # 5. End the trace + flush.
        langfuse.end_trace(
            outputs={
                "successful":  (out.get("provenance") or {}).get("successful"),
                "aborted":     (out.get("provenance") or {}).get("aborted"),
                "cost_usd":    (out.get("provenance") or {}).get("cost_usd"),
                "violations":  len(out.get("violations") or []),
            },
            error=None,
        )
        langfuse.flush()

        # Tag the run with the logger's run_id so callers can replay it.
        out.setdefault("provenance_run_id", run_id)
        out.setdefault("langfuse_backend",  langfuse.backend_name)
        return out

    return logger, langfuse, run_with_provenance


# --- P142 connector auto-instrumentation -------------------------------

def _instrument_connector(
    connector: Any,
    *,
    logger: ProvenanceLogger,
    hooks:  LangfuseHooks | None,
) -> Any:
    """Wrap one :class:`BaseActionConnector`'s memory-side hooks so every
    pre-execute / post-execute / rollback event also writes a P142
    provenance row + (when active) fires the matching Langfuse hook.

    Idempotent: re-instrumenting the same connector is a no-op.
    Returns the same connector for chaining.
    """
    if getattr(connector, "_p142_instrumented", False):
        return connector

    original_pre  = connector._record_approved_action  # noqa: SLF001
    original_out  = connector._record_outcome          # noqa: SLF001
    original_rb   = connector._record_rollback         # noqa: SLF001
    tool          = getattr(connector, "tool_name", "unknown")

    def _wrapped_pre(**kwargs: Any) -> str:
        action_id = original_pre(**kwargs)
        try:
            logger.log_action_event(
                event_kind="approval_granted",
                action_id=action_id,
                consent_token=kwargs.get("consent_token"),
                tool=tool,
                consent_level=kwargs.get("consent_level"),
                rollback_id=kwargs.get("rollback_id"),
                step=kwargs.get("step"),
                before_state=kwargs.get("extra") or {},
                stub_reason=(
                    "force_stub=True" if connector.force_stub else None
                ),
            )
        except Exception:  # pragma: no cover - logging must never break execution
            pass
        if hooks is not None:
            hooks.on_approval(
                action_id=action_id,
                consent_token=kwargs.get("consent_token") or "",
                tool=tool,
                consent_level=kwargs.get("consent_level"),
                scope=kwargs.get("description"),
            )
            hooks.on_action_start(
                action_id=action_id,
                tool=tool,
                consent_token=kwargs.get("consent_token"),
                consent_level=kwargs.get("consent_level"),
                description=kwargs.get("description"),
                rollback_id=kwargs.get("rollback_id"),
                step=kwargs.get("step"),
            )
        return action_id

    def _wrapped_out(**kwargs: Any) -> None:
        original_out(**kwargs)
        try:
            logger.log_action_event(
                event_kind=(
                    "action_executed"
                    if kwargs.get("outcome") == "success"
                    else "action_failed"
                ),
                action_id=kwargs.get("action_id") or "",
                consent_token=kwargs.get("consent_token"),
                tool=tool,
                consent_level=kwargs.get("consent_level"),
                rollback_id=kwargs.get("rollback_id"),
                outcome=kwargs.get("outcome"),
                after_state=kwargs.get("payload") or {},
                stub_reason=(
                    "force_stub=True" if connector.force_stub else None
                ),
            )
        except Exception:  # pragma: no cover
            pass
        if hooks is not None:
            hooks.on_action_end(
                action_id=kwargs.get("action_id") or "",
                tool=tool,
                outcome=kwargs.get("outcome") or "success",
                consent_token=kwargs.get("consent_token"),
                consent_level=kwargs.get("consent_level"),
                rollback_id=kwargs.get("rollback_id"),
                outputs=kwargs.get("payload") or {},
            )

    def _wrapped_rb(**kwargs: Any) -> None:
        original_rb(**kwargs)
        try:
            logger.log_action_event(
                event_kind=(
                    "rollback_executed"
                    if kwargs.get("outcome") == "rolled_back"
                    else "rollback_failed"
                ),
                action_id=kwargs.get("rollback_id") or kwargs.get("action_id") or "",
                consent_token=kwargs.get("consent_token"),
                tool=tool,
                consent_level=kwargs.get("consent_level"),
                rollback_id=kwargs.get("rollback_id"),
                rolled_back_from=kwargs.get("action_id"),
                outcome=kwargs.get("outcome"),
                rollback_script=kwargs.get("rollback_script"),
                stub_reason=(
                    "force_stub=True" if connector.force_stub else None
                ),
            )
        except Exception:  # pragma: no cover
            pass
        if hooks is not None:
            hooks.on_rollback(
                action_id=kwargs.get("action_id") or "",
                rollback_id=kwargs.get("rollback_id"),
                tool=tool,
                consent_token=kwargs.get("consent_token"),
                outcome=kwargs.get("outcome") or "rolled_back",
                rollback_script=kwargs.get("rollback_script"),
                consent_level=kwargs.get("consent_level"),
            )

    connector._record_approved_action = _wrapped_pre   # type: ignore[method-assign]
    connector._record_outcome         = _wrapped_out   # type: ignore[method-assign]
    connector._record_rollback        = _wrapped_rb    # type: ignore[method-assign]
    connector._p142_instrumented      = True            # type: ignore[attr-defined]
    return connector


def attach_to_connectors(
    registry: Any,
    *,
    logger:  ProvenanceLogger | None = None,
    hooks:   LangfuseHooks | None = None,
    user_id: str = "default",
) -> tuple[ProvenanceLogger, LangfuseHooks | None]:
    """Auto-instrument every connector in a :class:`ConnectorRegistry`.

    Walks :meth:`ConnectorRegistry.all_clients` and wraps each
    connector's memory-side lifecycle methods so every action writes
    one provenance row per stage (approval → outcome → optional
    rollback) and fires the matching Langfuse hook.

    Returns ``(logger, hooks)`` so the caller can keep references to
    the active singletons.
    """
    log = logger or get_provenance_logger(user_id=user_id)
    seen: set[int] = set()
    for client in registry.all_clients().values():
        if id(client) in seen:
            continue
        seen.add(id(client))
        _instrument_connector(client, logger=log, hooks=hooks)
    return log, hooks
