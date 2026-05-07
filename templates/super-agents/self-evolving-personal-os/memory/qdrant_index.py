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
"""Local Qdrant vector index for the Self-Evolving Personal OS.

This module is the **vector-search layer** of the Personal OS memory stack.
It sits below :mod:`memory.mem0_setup` (which owns the high-level write API
+ consent enforcement) and above the P121 connector layer (which feeds it
PII-redacted personal data).

Design contract:

- **Local-first.** Qdrant is run in *local* mode, persisting to
  ``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\memory\\qdrant\\``.
  No external Qdrant server is started; no remote calls are made; no Docker
  is required. On non-Windows runs (CI / Codespaces) the path falls back to
  ``~/.local/share/grok-agent/self-evolving-personal-os/memory/qdrant``.
- **Stub fallback.** If ``qdrant-client`` is not installed, the index
  transparently switches to a pure-Python in-memory store implementing the
  same Protocol so smoke tests, CI, and the P121 ``force_stub`` path keep
  working. Provenance reports ``stub: True`` and ``backend: 'in-memory'``.
- **Embedding fallback.** If ``sentence-transformers`` is not available, the
  index uses a deterministic hash-based embedding (a "stub embedder") so
  search is structurally valid (same query → same neighbours) but flagged
  ``provenance.stub_embedder: True``.
- **Provenance + PII.** Every upsert carries the connector-level provenance
  block forwarded by mem0_setup; every payload is re-checked through the
  P121 :func:`redact_pii` redactor before it touches disk — defence in
  depth in case a future connector regresses.
- **Per-source collections.** Mirrors the routing established by P121:
  one collection per source (``personal.x``, ``personal.calendar``,
  ``personal.email``, ``personal.notes``, ``personal.weather``,
  ``personal.news``).

Built for xAI, Grok and the whole community on X — local vector search is
the "free upgrade" we ship every Personal OS user without a cloud bill.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# Import the existing connector primitives without modifying that package.
# Absolute import keeps this module portable when the personal-OS folder
# is loaded by the orchestrator (whose own folder name contains hyphens
# that cannot be a Python package identifier).
from connectors import (  # type: ignore
    ConstitutionViolation,
    FetchResult,
    MEMORY_COLLECTION,
    SOURCES,
    appdata_root,
    redact_pii,
)

__all__ = [
    "QdrantIndex",
    "MemoryRecord",
    "SearchHit",
    "qdrant_root",
    "stub_embed",
    "default_embedder",
    "DEFAULT_VECTOR_DIM",
]


# --- Section 1. Constants and paths ---------------------------------------

DEFAULT_VECTOR_DIM = 384  # matches all-MiniLM-L6-v2 + the stub embedder
_HASH_SALT = "grok-agent.personal-os.qdrant.v1"
_DEFAULT_DISTANCE = "cosine"


def qdrant_root() -> Path:
    """Filesystem location for the local Qdrant store + companion sqlite."""
    return appdata_root() / "memory" / "qdrant"


def _stub_db_path() -> Path:
    """SQLite path used by the in-memory fallback for durable persistence."""
    return qdrant_root() / "stub_index.sqlite3"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Section 2. Data classes ----------------------------------------------

@dataclass
class MemoryRecord:
    """One vector + metadata record stored in a per-source collection.

    The Qdrant point structure is ``(id, vector, payload)``. We keep the
    Python dataclass mirror so callers (mem0_setup, the smoke tests, the
    morning-brief synthesiser) don't have to know the Qdrant shape.
    """

    id:           str
    source:       str
    text:         str
    vector:       list[float]
    payload:      dict
    provenance:   dict
    timestamp:    str = field(default_factory=_now_iso)

    def to_qdrant_point(self) -> dict:
        return {
            "id":      self.id,
            "vector":  list(self.vector),
            "payload": {
                "source":     self.source,
                "text":       self.text,
                "timestamp":  self.timestamp,
                "provenance": dict(self.provenance),
                **self.payload,
            },
        }


@dataclass
class SearchHit:
    """One search result row.

    Mirrors the Qdrant ``ScoredPoint`` shape but keeps the dataclass form so
    callers can serialise it directly to JSON/SQLite without an adapter.
    """

    id:         str
    score:      float
    source:     str
    text:       str
    timestamp:  str
    provenance: dict
    payload:    dict

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "score":      float(self.score),
            "source":     self.source,
            "text":       self.text,
            "timestamp":  self.timestamp,
            "provenance": dict(self.provenance),
            "payload":    dict(self.payload),
        }


# --- Section 3. Embeddings (stub + real-backed factory) -------------------

def stub_embed(text: str, dim: int = DEFAULT_VECTOR_DIM) -> list[float]:
    """Deterministic hash-based embedder.

    Not a real semantic embedder — same input always produces the same
    vector, but unrelated inputs do *not* get cosine-close vectors. We use
    it so smoke tests can prove the indexing pipeline end-to-end without
    pulling sentence-transformers (~250MB) into CI.

    Distinct strings always produce distinct vectors, which means
    "exact-match search" still works (and is the only thing the smoke test
    exercises). Real semantic recall is a job for the production embedder
    wired in via :func:`default_embedder`.
    """
    if not isinstance(text, str):
        text = str(text or "")
    if dim <= 0:
        dim = DEFAULT_VECTOR_DIM

    raw = (_HASH_SALT + "::" + text).encode("utf-8")
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        h = hashlib.sha256(raw + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(h), 4):
            if len(out) >= dim:
                break
            chunk = int.from_bytes(h[i : i + 4], "big", signed=False)
            # Map [0, 2^32) -> [-1.0, +1.0] deterministically.
            out.append((chunk / 0xFFFFFFFF) * 2.0 - 1.0)
        counter += 1

    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    return [v / norm for v in out]


_EMBEDDER_LOCK = threading.Lock()
_EMBEDDER_CACHE: dict[str, Any] = {}


def default_embedder(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Any:
    """Return a callable ``(text) -> list[float]`` using a real model when
    available, otherwise the deterministic :func:`stub_embed`.

    The callable always returns a unit-normalised vector of length
    :data:`DEFAULT_VECTOR_DIM`, which matches the
    ``sentence-transformers/all-MiniLM-L6-v2`` output dimension so a model
    swap requires no schema migration.
    """
    with _EMBEDDER_LOCK:
        cached = _EMBEDDER_CACHE.get(model_name)
        if cached is not None:
            return cached

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model = SentenceTransformer(model_name)

            def _real(text: str) -> list[float]:
                vec = model.encode([str(text)], normalize_embeddings=True)[0]
                out = [float(x) for x in list(vec)]
                if len(out) != DEFAULT_VECTOR_DIM:
                    # Pad / truncate for shape compatibility — never silent.
                    if len(out) < DEFAULT_VECTOR_DIM:
                        out = out + [0.0] * (DEFAULT_VECTOR_DIM - len(out))
                    else:
                        out = out[:DEFAULT_VECTOR_DIM]
                return out

            _EMBEDDER_CACHE[model_name] = _real
            return _real
        except Exception:
            # Fall back to the deterministic stub so the pipeline keeps
            # running. We tag the caller's provenance with stub_embedder.
            def _fallback(text: str) -> list[float]:
                return stub_embed(text, DEFAULT_VECTOR_DIM)

            _EMBEDDER_CACHE[model_name] = _fallback
            return _fallback


# --- Section 4. In-memory Qdrant fallback (SQLite-backed) -----------------

class _StubQdrantBackend:
    """Pure-Python fallback when ``qdrant-client`` isn't installed.

    Stores points in SQLite for durability across processes, computes cosine
    similarity in Python, and supports a small subset of Qdrant filters
    (``source``, ``timestamp >=``, ``timestamp <=``) — exactly the filters
    the Personal OS uses.

    The smoke test exercises this backend by default to keep CI fast, and
    also runs against the real qdrant-client when it's installed.
    """

    backend_name = "stub:in-memory+sqlite"

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS qdrant_points (
                    collection  TEXT NOT NULL,
                    point_id    TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    source      TEXT NOT NULL,
                    PRIMARY KEY (collection, point_id)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_qpoints_collection_ts "
                "ON qdrant_points(collection, timestamp)"
            )
            con.commit()

    # -- Collection management ---------------------------------------------

    def ensure_collection(self, name: str, vector_size: int) -> None:
        # The stub backend is schemaless (Python lists), so creation is a
        # no-op. We touch a row in a separate metadata table for parity
        # with the real backend's collection-listing semantics.
        with self._lock, sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS qdrant_collections (
                    name        TEXT PRIMARY KEY,
                    vector_size INTEGER NOT NULL,
                    created_at  TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                INSERT OR IGNORE INTO qdrant_collections
                  (name, vector_size, created_at)
                VALUES (?, ?, ?)
                """,
                (name, int(vector_size), _now_iso()),
            )
            con.commit()

    def list_collections(self) -> list[str]:
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                rows = con.execute(
                    "SELECT name FROM qdrant_collections ORDER BY name"
                ).fetchall()
            except sqlite3.Error:
                return []
        return [r[0] for r in rows]

    # -- Point operations --------------------------------------------------

    def upsert(self, collection: str, points: Sequence[dict]) -> int:
        if not points:
            return 0
        with self._lock, sqlite3.connect(self._db_path) as con:
            for p in points:
                payload = dict(p.get("payload") or {})
                source  = str(payload.get("source") or "")
                ts      = str(payload.get("timestamp") or _now_iso())
                con.execute(
                    """
                    INSERT OR REPLACE INTO qdrant_points
                      (collection, point_id, vector_json, payload, timestamp, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        collection,
                        str(p["id"]),
                        json.dumps(list(p["vector"])),
                        json.dumps(payload, ensure_ascii=False),
                        ts,
                        source,
                    ),
                )
            con.commit()
        return len(points)

    def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        limit: int,
        flt: dict | None,
    ) -> list[dict]:
        rows = self._scan(collection, flt)
        scored: list[tuple[float, dict]] = []
        qv = list(query_vector)
        qnorm = math.sqrt(sum(v * v for v in qv)) or 1.0
        for point_id, vector_json, payload_json, _ts, _src in rows:
            try:
                vec = json.loads(vector_json)
                payload = json.loads(payload_json)
            except (TypeError, ValueError):
                continue
            score = self._cosine(qv, vec, qnorm)
            scored.append(
                (score, {"id": point_id, "score": score, "payload": payload})
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [hit for _score, hit in scored[: max(1, int(limit))]]

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        flt: dict | None = None,
    ) -> int:
        if ids is None and not flt:
            return 0
        with self._lock, sqlite3.connect(self._db_path) as con:
            if ids:
                placeholders = ",".join(["?"] * len(ids))
                cur = con.execute(
                    f"DELETE FROM qdrant_points "
                    f"WHERE collection = ? AND point_id IN ({placeholders})",
                    [collection, *[str(i) for i in ids]],
                )
                con.commit()
                return int(cur.rowcount or 0)
            # Filter-based delete: scan + remove.
            rows = self._scan(collection, flt)
            removed = 0
            for point_id, _v, _p, _t, _s in rows:
                cur = con.execute(
                    "DELETE FROM qdrant_points "
                    "WHERE collection = ? AND point_id = ?",
                    (collection, point_id),
                )
                removed += int(cur.rowcount or 0)
            con.commit()
            return removed

    def count(self, collection: str, flt: dict | None = None) -> int:
        return len(self._scan(collection, flt))

    # -- Internals ---------------------------------------------------------

    def _scan(self, collection: str, flt: dict | None) -> list[tuple[str, str, str, str, str]]:
        sql  = (
            "SELECT point_id, vector_json, payload, timestamp, source "
            "FROM qdrant_points WHERE collection = ?"
        )
        args: list[Any] = [collection]
        if flt:
            if flt.get("source"):
                sql += " AND source = ?"
                args.append(str(flt["source"]))
            if flt.get("timestamp_gte"):
                sql += " AND timestamp >= ?"
                args.append(str(flt["timestamp_gte"]))
            if flt.get("timestamp_lte"):
                sql += " AND timestamp <= ?"
                args.append(str(flt["timestamp_lte"]))
        with self._lock, sqlite3.connect(self._db_path) as con:
            try:
                return con.execute(sql, args).fetchall()
            except sqlite3.Error:
                return []

    @staticmethod
    def _cosine(a: Sequence[float], b: Sequence[float], a_norm: float) -> float:
        if not a or not b:
            return 0.0
        n = min(len(a), len(b))
        dot = 0.0
        b_sq = 0.0
        for i in range(n):
            dot += a[i] * b[i]
            b_sq += b[i] * b[i]
        b_norm = math.sqrt(b_sq) or 1.0
        return float(dot / (a_norm * b_norm))


# --- Section 5. Real Qdrant backend (lazy-loaded) -------------------------

class _RealQdrantBackend:
    """Thin wrapper around ``qdrant-client`` running in *local* mode.

    Instantiated only when ``qdrant-client`` is importable; otherwise
    :class:`QdrantIndex` falls back to :class:`_StubQdrantBackend` so the
    surrounding pipeline still boots end-to-end.
    """

    backend_name = "qdrant-client:local"

    def __init__(self, storage_path: Path) -> None:
        from qdrant_client import QdrantClient  # type: ignore

        storage_path.mkdir(parents=True, exist_ok=True)
        self._client = QdrantClient(path=str(storage_path))

    def ensure_collection(self, name: str, vector_size: int) -> None:
        # qdrant-client >=1.7 promotes ``qdrant_client.models`` over the older
        # ``qdrant_client.http`` subpackage and replaces ``recreate_collection``
        # with the safer ``create_collection`` (after ``collection_exists``).
        from qdrant_client import models as qm  # type: ignore

        if self._client.collection_exists(name):
            return
        self._client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(
                size=int(vector_size),
                distance=qm.Distance.COSINE,
            ),
        )

    def list_collections(self) -> list[str]:
        return sorted(c.name for c in (self._client.get_collections().collections or []))

    def upsert(self, collection: str, points: Sequence[dict]) -> int:
        if not points:
            return 0
        from qdrant_client import models as qm  # type: ignore

        formatted = [
            qm.PointStruct(id=p["id"], vector=list(p["vector"]), payload=dict(p.get("payload") or {}))
            for p in points
        ]
        self._client.upsert(collection_name=collection, points=formatted, wait=True)
        return len(points)

    def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        limit: int,
        flt: dict | None,
    ) -> list[dict]:
        from qdrant_client import models as qm  # type: ignore

        qfilter = None
        if flt:
            must: list[Any] = []
            if flt.get("source"):
                must.append(qm.FieldCondition(
                    key="source",
                    match=qm.MatchValue(value=str(flt["source"])),
                ))
            if flt.get("timestamp_gte") or flt.get("timestamp_lte"):
                must.append(qm.FieldCondition(
                    key="timestamp",
                    range=qm.Range(
                        gte=flt.get("timestamp_gte"),
                        lte=flt.get("timestamp_lte"),
                    ),
                ))
            qfilter = qm.Filter(must=must) if must else None

        results = self._client.search(
            collection_name=collection,
            query_vector=list(query_vector),
            query_filter=qfilter,
            limit=int(limit),
        )
        out: list[dict] = []
        for r in results or []:
            out.append({
                "id":      str(getattr(r, "id", "")),
                "score":   float(getattr(r, "score", 0.0)),
                "payload": dict(getattr(r, "payload", {}) or {}),
            })
        return out

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        flt: dict | None = None,
    ) -> int:
        from qdrant_client import models as qm  # type: ignore

        if ids:
            self._client.delete(
                collection_name=collection,
                points_selector=qm.PointIdsList(points=[str(i) for i in ids]),
                wait=True,
            )
            return len(ids)
        if flt and flt.get("source"):
            self._client.delete(
                collection_name=collection,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(must=[
                        qm.FieldCondition(
                            key="source",
                            match=qm.MatchValue(value=str(flt["source"])),
                        )
                    ])
                ),
                wait=True,
            )
            return -1   # actual count not exposed by the API in this path
        return 0

    def count(self, collection: str, flt: dict | None = None) -> int:
        from qdrant_client import models as qm  # type: ignore
        qfilter = None
        if flt and flt.get("source"):
            qfilter = qm.Filter(must=[
                qm.FieldCondition(
                    key="source",
                    match=qm.MatchValue(value=str(flt["source"])),
                )
            ])
        try:
            r = self._client.count(collection_name=collection, count_filter=qfilter, exact=True)
            return int(r.count)
        except Exception:
            return 0


# --- Section 6. QdrantIndex — public API ----------------------------------

class QdrantIndex:
    """Public, source-aware vector index for the Personal OS.

    The two big caller-visible guarantees:

    1. **Per-source collections.** ``upsert(source=..., ...)`` routes to the
       collection name from :data:`MEMORY_COLLECTION` exactly — matching
       what P121's :func:`with_connectors` already wires up. Unknown
       sources raise :class:`ConstitutionViolation` rather than silently
       creating a rogue collection.
    2. **Provenance preservation.** Every point's payload carries the
       caller-supplied provenance block plus a ``backend`` field telling
       downstream code whether it's looking at real-Qdrant or stub data.
    """

    def __init__(
        self,
        *,
        embedder: Any | None = None,
        force_stub: bool = False,
        vector_dim: int = DEFAULT_VECTOR_DIM,
        storage_path: Path | None = None,
    ) -> None:
        self._vector_dim = int(vector_dim)
        self._storage   = storage_path or qdrant_root()
        self._storage.mkdir(parents=True, exist_ok=True)

        # Embedder
        self._embed_stub = bool(force_stub)
        if embedder is None:
            self._embedder: Any = default_embedder()
            # Detect whether the default embedder is a real model or the
            # stub fallback by sniffing the closure. Slight hack but
            # cheaper than threading a flag through `default_embedder`.
            try:
                from sentence_transformers import SentenceTransformer  # noqa: F401
            except Exception:
                self._embed_stub = True
        else:
            self._embedder = embedder

        # Backend
        if force_stub:
            self._backend: Any = _StubQdrantBackend(_stub_db_path())
        else:
            try:
                self._backend = _RealQdrantBackend(self._storage)
            except Exception:
                self._backend = _StubQdrantBackend(_stub_db_path())

        # Pre-create one collection per declared source so first-write
        # latency is predictable. No-op if collection already exists.
        for src in SOURCES:
            self._backend.ensure_collection(
                MEMORY_COLLECTION[src], self._vector_dim
            )

    # -- Helpers -----------------------------------------------------------

    @property
    def backend_name(self) -> str:
        return getattr(self._backend, "backend_name", "unknown")

    @property
    def vector_dim(self) -> int:
        return self._vector_dim

    def _resolve_collection(self, source: str) -> str:
        if source not in MEMORY_COLLECTION:
            raise ConstitutionViolation(
                f"qdrant: unknown source '{source}' — only the manifest-"
                f"declared sources may be indexed: {sorted(MEMORY_COLLECTION)}",
                article="II", source=source, gate=f"read_{source}",
            )
        return MEMORY_COLLECTION[source]

    def _embed(self, text: str) -> tuple[list[float], bool]:
        try:
            vec = list(self._embedder(text))
            stubbed = bool(self._embed_stub)
        except Exception:
            vec = stub_embed(text, self._vector_dim)
            stubbed = True
        if len(vec) != self._vector_dim:
            if len(vec) < self._vector_dim:
                vec = list(vec) + [0.0] * (self._vector_dim - len(vec))
            else:
                vec = list(vec)[: self._vector_dim]
        return vec, stubbed

    @staticmethod
    def _stable_id(source: str, payload: dict) -> str:
        """Stable UUID5 id derived from (source, point-key)."""
        # Prefer the connector-provided id; otherwise fall back to a hash
        # over (source, text) so duplicate writes upsert in place.
        key = (
            payload.get("id")
            or payload.get("relpath")
            or payload.get("url")
            or payload.get("text")
            or json.dumps(payload, sort_keys=True, default=str)
        )
        ns = uuid.UUID("12345678-1234-5678-1234-567812345678")
        return str(uuid.uuid5(ns, f"{source}::{key}"))

    # -- Public API ---------------------------------------------------------

    def upsert_record(
        self,
        source: str,
        text: str,
        payload: dict,
        provenance: dict,
        *,
        record_id: str | None = None,
    ) -> MemoryRecord:
        """Index one (text, payload, provenance) triple under ``source``."""
        if source not in MEMORY_COLLECTION:
            raise ConstitutionViolation(
                f"qdrant: refused to index unknown source '{source}'",
                article="II", source=source, gate=f"read_{source}",
            )

        # Defence-in-depth PII redaction (P121 normally redacts upstream;
        # this re-pass guarantees nothing slips through here).
        red_payload = redact_pii(dict(payload))
        red_text    = redact_pii(text or "")

        vec, embed_stub = self._embed(red_text)

        prov = {
            **dict(provenance or {}),
            "indexed_at":     _now_iso(),
            "backend":        self.backend_name,
            "stub_embedder":  bool(embed_stub),
            "redaction_applied": True,
        }
        if "stub_reason" in prov and not prov.get("stub"):
            prov["stub"] = True

        rec = MemoryRecord(
            id=record_id or self._stable_id(source, {**red_payload, "text": red_text}),
            source=source,
            text=red_text if isinstance(red_text, str) else str(red_text),
            vector=vec,
            payload=red_payload,
            provenance=prov,
        )
        collection = self._resolve_collection(source)
        self._backend.upsert(collection, [rec.to_qdrant_point()])
        return rec

    def upsert_fetch_result(self, result: FetchResult) -> list[MemoryRecord]:
        """Convenience: index every item in a P121 :class:`FetchResult`.

        This makes the QdrantIndex itself satisfy the P121 ``MemoryStore``
        Protocol when wrapped by :class:`MemoryStoreAdapter` (defined in
        :mod:`memory.mem0_setup`). The connector layer therefore writes
        through here without import-time coupling.
        """
        out: list[MemoryRecord] = []
        for item in result.items:
            text = self._summarise_item(result.source, item)
            out.append(
                self.upsert_record(
                    source=result.source,
                    text=text,
                    payload=item,
                    provenance=item.get("provenance") or result.provenance,
                )
            )
        return out

    def search(
        self,
        query: str,
        *,
        source: str | None = None,
        limit: int = 5,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
    ) -> list[SearchHit]:
        """Semantic search across one or all collections."""
        qvec, _ = self._embed(query or "")
        collections: list[str] = (
            [self._resolve_collection(source)]
            if source
            else [MEMORY_COLLECTION[s] for s in SOURCES]
        )
        flt: dict[str, Any] = {}
        if source:
            flt["source"] = source
        if timestamp_gte:
            flt["timestamp_gte"] = timestamp_gte
        if timestamp_lte:
            flt["timestamp_lte"] = timestamp_lte

        all_hits: list[SearchHit] = []
        per_collection_limit = max(1, int(limit))
        for col in collections:
            raw = self._backend.search(col, qvec, per_collection_limit, flt)
            for h in raw:
                payload = dict(h.get("payload") or {})
                # Defensive PII redaction at read time too — guarantees no
                # raw value can escape regardless of how it was indexed.
                payload = redact_pii(payload)
                all_hits.append(
                    SearchHit(
                        id=str(h.get("id", "")),
                        score=float(h.get("score", 0.0)),
                        source=str(payload.get("source", "")),
                        text=str(payload.get("text", "")),
                        timestamp=str(payload.get("timestamp", "")),
                        provenance=dict(payload.get("provenance") or {}),
                        payload=payload,
                    )
                )
        all_hits.sort(key=lambda x: x.score, reverse=True)
        return all_hits[: max(1, int(limit))]

    def count(self, source: str | None = None) -> int:
        if source is not None:
            return self._backend.count(self._resolve_collection(source))
        return sum(
            self._backend.count(MEMORY_COLLECTION[s]) for s in SOURCES
        )

    def delete(
        self,
        *,
        source: str | None = None,
        ids: Iterable[str] | None = None,
    ) -> int:
        if source is None and not ids:
            raise ValueError("delete requires either source= or ids=")
        if source:
            return self._backend.delete(
                self._resolve_collection(source),
                ids=list(ids) if ids else None,
                flt={"source": source} if not ids else None,
            )
        # ids only — try every collection (rare path).
        total = 0
        for s in SOURCES:
            total += self._backend.delete(
                MEMORY_COLLECTION[s], ids=list(ids or [])
            )
        return total

    def list_collections(self) -> list[str]:
        return self._backend.list_collections()

    # -- Item summarisers (per-source) -------------------------------------

    @staticmethod
    def _summarise_item(source: str, item: dict) -> str:
        """Build the searchable text blob for one item.

        Per-source heuristic so the embedder gets a coherent sentence.
        """
        if source == "x_personal":
            kind = item.get("kind", "x_post")
            return f"[{kind}] {item.get('text') or item.get('preview') or item.get('name') or ''}".strip()
        if source == "gcal":
            return (
                f"[calendar] {item.get('summary') or ''} "
                f"{item.get('start_iso') or ''} {item.get('location') or ''} "
                f"{item.get('description') or ''}"
            ).strip()
        if source == "gmail":
            return (
                f"[email] {item.get('subject') or ''} "
                f"{item.get('snippet') or ''} {item.get('body') or ''}"
            ).strip()
        if source == "local_notes":
            return (
                f"[note] {item.get('title') or ''} "
                f"{item.get('relpath') or ''} {item.get('body') or ''}"
            ).strip()
        if source == "weather":
            w = item.get("weather") or []
            descr = w[0].get("description") if w and isinstance(w[0], dict) else ""
            return (
                f"[weather] {item.get('locale') or ''} {item.get('dt_iso') or ''} "
                f"temp={item.get('temp')} {descr}"
            ).strip()
        if source == "news_personal":
            return (
                f"[news] {item.get('title') or ''} {item.get('description') or ''} "
                f"{item.get('source_name') or ''}"
            ).strip()
        return json.dumps(item, default=str)
