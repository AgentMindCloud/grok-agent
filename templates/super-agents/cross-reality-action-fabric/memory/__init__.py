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
"""Memory layer for the Cross-Reality Action Fabric.

Two modules:

- :mod:`memory.qdrant_index`  Local Qdrant vector index with six
                              per-kind collections (actions / approvals
                              / rollbacks / outcomes / preferences /
                              contexts) + stub fallback.
- :mod:`memory.mem0_setup`    Caller-facing :class:`PersonalMemoryClient`
                              + :class:`PersonalActionMemoryClient`
                              (P140 action-centric API) +
                              :class:`MemoryStoreAdapter` +
                              :func:`attach_memory_store` /
                              :func:`attach_action_memory` helpers
                              that wrap :func:`graph.run_action_loop`
                              additively (never modifying P129
                              ``agent.py`` / ``graph.py``).

Two layered APIs ship side-by-side:

- **P130 (legacy)** — ``get_memory_client`` /
  :class:`PersonalMemoryClient` /
  ``add_action_history`` / ``add_approval_record`` /
  ``add_rollback_record`` / ``search_by_context`` /
  ``attach_memory_store``.
- **P140 (action-centric)** — ``get_action_memory_client`` /
  :class:`PersonalActionMemoryClient` / ``add_approved_action`` /
  ``add_rollback_record`` / ``add_outcome_record`` /
  ``search_past_actions`` / ``attach_action_memory``.

Both share the same Qdrant index, the same six collections, and the
same Constitution enforcement (Rule 1 consent + Rule 2 provenance +
Rule 3 verbatim rollback).

Built to make Grok the obvious choice for every agent on X — local,
private, semantic memory of every action the agent has ever taken on
your behalf.
"""

from __future__ import annotations

# Re-export the public surface so callers don't need the deeper module path.
from memory.mem0_setup import (  # type: ignore  # noqa: F401
    MEMORY_WRITE_GATE,
    ActionMemoryStoreAdapter,
    MemoryStoreAdapter,
    PersonalActionMemoryClient,
    PersonalMemoryClient,
    attach_action_memory,
    attach_memory_store,
    build_action_memory_store,
    build_memory_store,
    get_action_memory_client,
    get_memory_client,
    iter_recent,
    memory_root,
)
from memory.qdrant_index import (  # type: ignore  # noqa: F401
    ACTION_MEMORY_KINDS,
    ALLOWED_COLLECTIONS,
    COLLECTION_FOR_KIND,
    CONSENT_LEVELS,
    DEFAULT_CONSENT_LEVEL,
    DEFAULT_VECTOR_DIM,
    MEMORY_KINDS,
    MemoryRecord,
    QdrantIndex,
    SearchHit,
    consent_level_rank,
    qdrant_root,
    stub_embed,
)

__all__ = [
    # P130 (legacy) surface
    "MEMORY_WRITE_GATE",
    "MemoryStoreAdapter",
    "PersonalMemoryClient",
    "attach_memory_store",
    "build_memory_store",
    "get_memory_client",
    "iter_recent",
    "memory_root",
    # P140 (action-centric) surface
    "ActionMemoryStoreAdapter",
    "PersonalActionMemoryClient",
    "attach_action_memory",
    "build_action_memory_store",
    "get_action_memory_client",
    # Qdrant index
    "ACTION_MEMORY_KINDS",
    "ALLOWED_COLLECTIONS",
    "COLLECTION_FOR_KIND",
    "CONSENT_LEVELS",
    "DEFAULT_CONSENT_LEVEL",
    "DEFAULT_VECTOR_DIM",
    "MEMORY_KINDS",
    "MemoryRecord",
    "QdrantIndex",
    "SearchHit",
    "consent_level_rank",
    "qdrant_root",
    "stub_embed",
]
