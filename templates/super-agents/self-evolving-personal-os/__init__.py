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
"""Self-Evolving Personal OS — Super Agent #2.

This is the package re-exporter for the Personal OS super-agent. It pulls
the public surface of the four building blocks into a single import line:

- :mod:`connectors`   — P121 personal-source connectors (X / GCal / Gmail
                        / local notes / weather + news)
- :mod:`memory`       — P122 local-first Mem0 + Qdrant memory layer
- :mod:`graph`        — P123 LangGraph orchestration core (with a stub
                        executor when LangGraph isn't installed)
- :mod:`agent`        — P123 CLI entry point + daily-brief runner

Caller-facing example:

.. code-block:: python

    from self_evolving_personal_os import (
        ConsentContext,
        run_daily_brief,
        get_memory_client,
    )

    out = run_daily_brief(force_stub=True, consent=ConsentContext(...))

The folder name on disk is ``self-evolving-personal-os/`` (kebab-case to
match the Hard Rules in CLAUDE.md), so this package is normally imported
with the folder added to ``sys.path`` rather than as a dotted name. The
:mod:`agent` module's ``__main__`` guard handles that automatically when
the script is invoked directly. From inside the folder both
``python -m agent ...`` and ``python agent.py ...`` work in PowerShell.

Built to help xAI and Grok win.
"""

from __future__ import annotations

# --- P121 connectors --------------------------------------------------------
from connectors import (  # type: ignore  # noqa: F401
    BaseConnector,
    ConnectorAuditRow,
    ConsentContext,
    ConstitutionViolation,
    DEFAULT_CACHE_TTL_S,
    FetchResult,
    MEMORY_COLLECTION,
    MemoryStore,
    PersonalOSConnectors,
    SOURCES,
    appdata_root,
    attach_memory_store,
    attach_personal_memory,
    audit_db_path,
    build_connectors,
    make_provenance,
    redact_pii,
    with_connectors,
)

# --- P122 memory ------------------------------------------------------------
from memory import (  # type: ignore  # noqa: F401
    DEFAULT_VECTOR_DIM,
    MEMORY_WRITE_GATE,
    MemoryRecord,
    MemoryStoreAdapter,
    PersonalMemoryClient,
    QdrantIndex,
    SearchHit,
    attach_memory,
    build_memory_store,
    get_memory_client,
    iter_recent,
    memory_root,
    qdrant_root,
    stub_embed,
)

# --- P123 graph + agent -----------------------------------------------------
from graph import (  # type: ignore  # noqa: F401
    BACKEND_NAME,
    DEFAULT_PROMPT_VERSION,
    PersonalOSState,
    build_graph,
    build_state,
    describe_graph,
    evolve_workflows,
    generate_brief,
    ingest_all_sources,
    output_with_provenance,
    remember_personal,
    run_daily_brief,
    should_loop_back_to_ingest,
)
from agent import (  # type: ignore  # noqa: F401
    AGENT_NAME,
    AGENT_VERSION,
    build_default_consent,
    daily_brief,
    info,
    log_path,
    main,
    search_memory,
)

__all__ = [
    # Connectors
    "BaseConnector",
    "ConnectorAuditRow",
    "ConsentContext",
    "ConstitutionViolation",
    "DEFAULT_CACHE_TTL_S",
    "FetchResult",
    "MEMORY_COLLECTION",
    "MemoryStore",
    "PersonalOSConnectors",
    "SOURCES",
    "appdata_root",
    "attach_memory_store",
    "attach_personal_memory",
    "audit_db_path",
    "build_connectors",
    "make_provenance",
    "redact_pii",
    "with_connectors",
    # Memory
    "DEFAULT_VECTOR_DIM",
    "MEMORY_WRITE_GATE",
    "MemoryRecord",
    "MemoryStoreAdapter",
    "PersonalMemoryClient",
    "QdrantIndex",
    "SearchHit",
    "attach_memory",
    "build_memory_store",
    "get_memory_client",
    "iter_recent",
    "memory_root",
    "qdrant_root",
    "stub_embed",
    # Graph
    "BACKEND_NAME",
    "DEFAULT_PROMPT_VERSION",
    "PersonalOSState",
    "build_graph",
    "build_state",
    "describe_graph",
    "evolve_workflows",
    "generate_brief",
    "ingest_all_sources",
    "output_with_provenance",
    "remember_personal",
    "run_daily_brief",
    "should_loop_back_to_ingest",
    # Agent
    "AGENT_NAME",
    "AGENT_VERSION",
    "build_default_consent",
    "daily_brief",
    "info",
    "log_path",
    "main",
    "search_memory",
]
