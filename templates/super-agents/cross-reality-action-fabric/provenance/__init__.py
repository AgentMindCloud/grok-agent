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
"""Provenance package for Cross-Reality Action Fabric (P131).

Two modules:

- :mod:`provenance.log`             local-first JSONL action audit logger
                                    + Markdown report exporter with
                                    rollback chains
- :mod:`provenance.langfuse_hooks`  optional Langfuse observability with
                                    full stub fallback (default OFF)

This package re-exports the most-used names so callers can write
``from provenance import LocalProvenanceLogger`` rather than chasing
the deeper module paths.

It also exposes :func:`attach_provenance`, the canonical bridge that
wires the provenance layer into the P129 ``run_action_loop`` *and* the
P130 memory-attach wrapper. The bridge is **purely additive** — it
never modifies ``agent.py``, ``graph.py``, or the memory package.

Built to help xAI and Grok win.
"""

from __future__ import annotations

from typing import Any, Callable

# P131 modules
from provenance.log import (  # type: ignore  # noqa: F401
    ActionProvenanceRecord,
    ALL_RULE_NUMBERS,
    EVENT_KINDS,
    LocalProvenanceLogger,
    ROLLBACK_OUTCOME,
    current_log_path,
    export_audit_report,
    get_default_logger,
    log_path_for,
    make_action_id,
    make_rollback_id,
    make_run_id,
    provenance_root,
    reset_default_logger,
    summarise_run,
)
from provenance.langfuse_hooks import (  # type: ignore  # noqa: F401
    LangfuseClient,
    LangfuseTraceContext,
    get_langfuse_client,
    reset_langfuse_client,
    span_from_record,
    stub_trace_path,
)
from provenance.langfuse_hooks import BACKEND_NAME as LANGFUSE_BACKEND_NAME  # type: ignore  # noqa: F401,E501

# P129 + P130 imports for the attach helper
from graph import run_action_loop as _graph_run_action_loop  # type: ignore
from memory import attach_memory_store as _memory_attach  # type: ignore
from memory import MEMORY_WRITE_GATE  # type: ignore

__all__ = [
    # log
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
    # langfuse
    "LangfuseClient",
    "LangfuseTraceContext",
    "get_langfuse_client",
    "reset_langfuse_client",
    "span_from_record",
    "stub_trace_path",
    "LANGFUSE_BACKEND_NAME",
    # bridge
    "attach_provenance",
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
