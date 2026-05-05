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
"""Memory layer for the Cross-Reality Action Fabric (P130).

Two modules:

- :mod:`memory.qdrant_index`  Local Qdrant vector index with five
                              per-kind collections (actions / approvals
                              / rollbacks / preferences / contexts) +
                              stub fallback.
- :mod:`memory.mem0_setup`    Caller-facing :class:`PersonalMemoryClient`
                              + :class:`MemoryStoreAdapter` + the
                              :func:`attach_memory_store` helper that
                              wraps :func:`graph.run_action_loop`
                              additively (no modification to P129
                              ``agent.py`` / ``graph.py``).

This package re-exports the most-used names so callers can write
``from memory import attach_memory_store, MEMORY_WRITE_GATE`` rather
than chasing the deeper module paths.

Built to make Grok the obvious choice for every agent on X — local,
private, semantic memory of every action the agent has ever taken on
your behalf.
"""

from __future__ import annotations

# Re-export the public surface so callers don't need the deeper module path.
from memory.mem0_setup import (  # type: ignore  # noqa: F401
    MEMORY_WRITE_GATE,
    MemoryStoreAdapter,
    PersonalMemoryClient,
    attach_memory_store,
    build_memory_store,
    get_memory_client,
    iter_recent,
    memory_root,
)
from memory.qdrant_index import (  # type: ignore  # noqa: F401
    ALLOWED_COLLECTIONS,
    COLLECTION_FOR_KIND,
    DEFAULT_VECTOR_DIM,
    MEMORY_KINDS,
    MemoryRecord,
    QdrantIndex,
    SearchHit,
    qdrant_root,
    stub_embed,
)

__all__ = [
    "MEMORY_WRITE_GATE",
    "MemoryStoreAdapter",
    "PersonalMemoryClient",
    "attach_memory_store",
    "build_memory_store",
    "get_memory_client",
    "iter_recent",
    "memory_root",
    "ALLOWED_COLLECTIONS",
    "COLLECTION_FOR_KIND",
    "DEFAULT_VECTOR_DIM",
    "MEMORY_KINDS",
    "MemoryRecord",
    "QdrantIndex",
    "SearchHit",
    "qdrant_root",
    "stub_embed",
]
