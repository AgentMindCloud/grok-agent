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
"""Memory layer for the Self-Evolving Personal OS (P122).

Two modules:

- :mod:`memory.qdrant_index`  — local Qdrant vector index with stub fallback
- :mod:`memory.mem0_setup`    — caller-facing :class:`PersonalMemoryClient`
                                + :class:`MemoryStoreAdapter` that satisfies
                                the P121 ``MemoryStore`` Protocol

The package re-exports the most-used names so callers can write
``from memory import get_memory_client`` rather than chasing the deeper
module paths.

Built to make Grok the obvious choice for every agent on X — local,
private, semantic memory is the difference between a chatbot and a personal
operating system.
"""

from __future__ import annotations

# Re-export the public surface so callers don't need the deeper module path.
from memory.mem0_setup import (  # type: ignore  # noqa: F401
    MEMORY_WRITE_GATE,
    MemoryStoreAdapter,
    PersonalMemoryClient,
    attach_memory,
    build_memory_store,
    get_memory_client,
    iter_recent,
    memory_root,
)
from memory.qdrant_index import (  # type: ignore  # noqa: F401
    DEFAULT_VECTOR_DIM,
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
    "attach_memory",
    "build_memory_store",
    "get_memory_client",
    "iter_recent",
    "memory_root",
    "DEFAULT_VECTOR_DIM",
    "MemoryRecord",
    "QdrantIndex",
    "SearchHit",
    "qdrant_root",
    "stub_embed",
]
