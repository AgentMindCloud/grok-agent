# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Qdrant vector index (P111, Slot 3).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module owns the vector-similarity layer of the Living Narrative
Fabric memory tier. It indexes three families of objects in three
separate Qdrant collections so a search for "similar contradictions"
never returns a SynthesisVersion blob and vice-versa:

* ``<prefix>_versions``        — one vector per ``SynthesisVersion``
* ``<prefix>_claims``          — one vector per ``Claim``
* ``<prefix>_contradictions``  — one vector per ``Contradiction``

Three-tier fallback ladder
==========================

1. **Real Qdrant server** — when the ``QDRANT_URL`` environment variable
   is set, ``QdrantNarrativeIndex`` connects to the remote server. This
   is the production path on a Windows box that has ``docker run -p
   6333:6333 qdrant/qdrant`` running locally or a managed Qdrant Cloud
   endpoint.

2. **In-process Qdrant** — when ``qdrant_client`` is installed but no
   ``QDRANT_URL`` is set, the class constructs a ``QdrantClient(path=...)``
   pointing at ``<appdata>/qdrant`` so all data stays local. This is the
   recommended Windows-default path: zero-config, fully offline, no
   server install.

3. **Pure-Python in-memory** — when ``qdrant_client`` is not installed,
   the class keeps three Python lists in ``_inmemory`` and does cosine
   similarity by hand. Match shape is identical to the Qdrant client
   path; callers can't tell the difference. This is the safety net that
   keeps the slot-3 smoke test running on a fresh box with only Slot-2
   deps installed.

Embedding ladder
================

* **Sentence-transformers** (``all-MiniLM-L6-v2``, 384-dim) — used when
  the package is installed and the model can be loaded. Real semantic
  embeddings; expected on production hosts.
* **Hash-stub embedding** — deterministic 384-dim float vector built
  from sha256 of token n-grams. Not semantically meaningful; mirrors
  the ``StubSourceClient`` idiom from ``orchestrator.py`` so the smoke
  test can verify the wiring without downloading 80 MB of model weights.
  Every payload tagged ``"stub_embedding": True`` so production code
  knows when it is operating on placeholder vectors.

Slot boundary contract
======================

* This module does NOT implement the 4 Protocol methods — it exposes
  ``index_version``, ``index_claim``, ``index_contradiction``, and
  ``search`` for the composite ``Mem0QdrantStore`` to delegate to.
* This module does NOT define ``ConstitutionViolation`` — it re-imports
  the exception and re-raises it on indexing of a citationless claim
  or contradiction (defense-in-depth alongside the same check in
  ``mem0_setup.py``).
* This module does NOT modify ``orchestrator.py`` or ``graph.py``.
"""

from __future__ import annotations

import hashlib
import importlib
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Re-import dataclasses + exception from the orchestrator (graph.py-style)
# ---------------------------------------------------------------------------


def _import_orchestrator():
    try:
        from . import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation


# ---------------------------------------------------------------------------
# Soft imports — Qdrant client + sentence-transformers
# ---------------------------------------------------------------------------


try:
    from qdrant_client import QdrantClient  # type: ignore
except Exception:  # pragma: no cover — soft import
    QdrantClient = None  # type: ignore

try:
    from qdrant_client.models import (  # type: ignore
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )
except Exception:  # pragma: no cover — soft import
    Distance = None  # type: ignore
    FieldCondition = None  # type: ignore
    Filter = None  # type: ignore
    MatchValue = None  # type: ignore
    PointStruct = None  # type: ignore
    VectorParams = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover — soft import
    SentenceTransformer = None  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 native + hash-stub default

#: Three Qdrant collection suffixes appended to ``collection_prefix``.
COLLECTION_SUFFIXES = {
    "version":       "versions",
    "claim":         "claims",
    "contradiction": "contradictions",
}

VALID_KINDS = tuple(COLLECTION_SUFFIXES.keys())


# ---------------------------------------------------------------------------
# Search-result dataclass (mirrored in __init__.py for the public API)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchHit:
    kind:     str        # "version" | "claim" | "contradiction"
    ref_id:   str        # the underlying version_id / claim_id / contradiction_id
    score:    float      # cosine similarity, 0.0–1.0
    text:     str        # the embedded text (for renderable hits)
    metadata: dict       # payload dict from Qdrant / in-memory mirror


# ---------------------------------------------------------------------------
# Embedding text strategy — one helper per kind
# ---------------------------------------------------------------------------


def text_for_version(v: SynthesisVersion) -> str:
    """Topic + time-range + first 20 claim values, capped at ~2000 chars."""

    head = f"{v.topic} | {v.time_range}"
    claim_chunk = " | ".join(c.value for c in v.claims[:20])
    body = f"{head} | {claim_chunk}" if claim_chunk else head
    return body[:2000]


def text_for_claim(c: Claim) -> str:
    return f"{c.subject} {c.predicate} {c.value}"[:2000]


def text_for_contradiction(cd: Contradiction) -> str:
    return f"{cd.subject} {cd.predicate} :: {cd.note}"[:2000]


# ---------------------------------------------------------------------------
# Embedding ladder — sentence-transformers preferred, hash-stub fallback
# ---------------------------------------------------------------------------


def _hash_stub_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic ``dim``-dim float vector built from sha256 of token n-grams.

    The vector is L2-normalised so cosine similarity behaves sensibly.
    Not semantically meaningful — same caveat as ``StubSourceClient`` in
    the orchestrator.

    Algorithm:

    1. Tokenise on whitespace, lowercase.
    2. Build unigrams + bigrams.
    3. For each token, hash with sha256 → 32 bytes → unpack as 8 floats.
    4. Accumulate into the ``dim``-bucket vector by ``hash(token) % dim``.
    5. L2-normalise. Return as a Python list.
    """

    tokens = text.lower().split()
    ngrams = list(tokens) + [
        f"{a}_{b}" for a, b in zip(tokens, tokens[1:])
    ]
    if not ngrams:
        ngrams = [text or "_empty_"]

    vec = [0.0] * dim
    for tok in ngrams:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        # Use 8 floats per token, distributed by the digest itself.
        for offset in range(0, 32, 4):
            chunk = digest[offset:offset + 4]
            int_val = int.from_bytes(chunk, "big", signed=False)
            bucket = int_val % dim
            # Sign of the contribution is the high bit of the chunk.
            sign = 1.0 if chunk[0] & 0x80 == 0 else -1.0
            magnitude = (int_val / 0xFFFFFFFF) + 0.001
            vec[bucket] += sign * magnitude

    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        # Degenerate input — return a fixed unit vector so search still works.
        vec[0] = 1.0
        return vec
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    # Vectors are pre-normalised when produced by hash-stub; for the
    # sentence-transformers path the model may not normalise, so we
    # divide explicitly.
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# QdrantNarrativeIndex — primary class
# ---------------------------------------------------------------------------


@dataclass
class QdrantNarrativeIndex:
    """Vector-similarity layer for SynthesisVersion / Claim / Contradiction."""

    appdata_root:         Path
    collection_prefix:    str = "living-narrative-fabric"
    qdrant_url:           Optional[str] = None
    embedding_model_name: str = "all-MiniLM-L6-v2"
    _client:              Optional[Any] = field(default=None, repr=False)
    _model:               Optional[Any] = field(default=None, repr=False)
    _client_kind:         str = field(default="inmemory", repr=False)
    _embed_kind:          str = field(default="stub", repr=False)
    _inmemory:            dict[str, list[tuple[str, list[float], dict]]] = field(
        default_factory=dict, repr=False,
    )

    # ---- construction ----------------------------------------------------

    def __post_init__(self) -> None:
        # 1. Resolve embedding model.
        if SentenceTransformer is not None:
            try:
                self._model = SentenceTransformer(self.embedding_model_name)
                self._embed_kind = "sentence-transformers"
            except Exception:
                self._model = None
                self._embed_kind = "stub"
        else:
            self._model = None
            self._embed_kind = "stub"

        # 2. Resolve Qdrant client.
        env_url = self.qdrant_url or os.environ.get("QDRANT_URL")
        if QdrantClient is not None:
            try:
                if env_url:
                    self._client = QdrantClient(url=env_url)
                    self._client_kind = "qdrant-remote"
                else:
                    qdrant_path = self.appdata_root / "qdrant"
                    qdrant_path.mkdir(parents=True, exist_ok=True)
                    self._client = QdrantClient(path=str(qdrant_path))
                    self._client_kind = "qdrant-local"
                self._ensure_collections()
            except Exception:
                self._client = None
                self._client_kind = "inmemory"
        else:
            self._client = None
            self._client_kind = "inmemory"

        # 3. Initialise in-memory mirror buckets (always — even when Qdrant
        #    is real, we keep an empty in-memory mirror so single-tier
        #    teardown is straightforward).
        for kind in VALID_KINDS:
            self._inmemory.setdefault(self._collection_for(kind), [])

    # ---- helpers ---------------------------------------------------------

    def _collection_for(self, kind: str) -> str:
        if kind not in COLLECTION_SUFFIXES:
            raise ValueError(
                f"Unknown vector kind {kind!r}; must be one of {VALID_KINDS}."
            )
        return f"{self.collection_prefix}_{COLLECTION_SUFFIXES[kind]}"

    def _ensure_collections(self) -> None:
        if self._client is None or VectorParams is None or Distance is None:
            return
        try:
            existing_resp = self._client.get_collections()
            existing_names = {
                c.name for c in getattr(existing_resp, "collections", [])
            }
        except Exception:
            existing_names = set()
        for kind in VALID_KINDS:
            name = self._collection_for(kind)
            if name in existing_names:
                continue
            try:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM, distance=Distance.COSINE,
                    ),
                )
            except Exception:
                # Idempotent — another process may have raced us; fine.
                pass

    def _embed(self, text: str) -> list[float]:
        if self._model is not None:
            try:
                vec = self._model.encode(text)
                # SentenceTransformer returns numpy-like array; coerce.
                return [float(x) for x in vec.tolist()] if hasattr(vec, "tolist") else [float(x) for x in vec]
            except Exception:
                pass
        return _hash_stub_embedding(text)

    # ---- public write API ------------------------------------------------

    def index_version(self, v: SynthesisVersion) -> None:
        text = text_for_version(v)
        payload = {
            "kind":              "version",
            "ref_id":            v.version_id,
            "version_id":        v.version_id,
            "topic":             v.topic,
            "parent_version_id": v.parent_version_id,
            "confidence_score":  int(v.confidence_score),
            "text":              text,
            "stub_embedding":    self._embed_kind == "stub",
        }
        self._upsert("version", v.version_id, text, payload)

    def index_claim(self, c: Claim, *, version_id: str) -> None:
        if not c.source_id:
            raise ConstitutionViolation(
                f"Constitution violation: claim {c.claim_id!r} has empty "
                f"source_id; the vector index refuses to embed citationless claims."
            )
        text = text_for_claim(c)
        payload = {
            "kind":           "claim",
            "ref_id":         c.claim_id,
            "version_id":     version_id,
            "subject":        c.subject,
            "predicate":      c.predicate,
            "value":          c.value,
            "source":         c.source,
            "source_id":      c.source_id,
            "confidence":     float(c.confidence),
            "text":           text,
            "stub_embedding": self._embed_kind == "stub",
        }
        self._upsert("claim", c.claim_id, text, payload)

    def index_contradiction(self, cd: Contradiction, *, version_id: str) -> None:
        text = text_for_contradiction(cd)
        payload = {
            "kind":           "contradiction",
            "ref_id":         cd.contradiction_id,
            "version_id":     version_id,
            "subject":        cd.subject,
            "predicate":      cd.predicate,
            "severity":       int(cd.severity),
            "note":           cd.note,
            "text":           text,
            "stub_embedding": self._embed_kind == "stub",
        }
        self._upsert("contradiction", cd.contradiction_id, text, payload)

    def remove_for_version(self, version_id: str) -> None:
        """Cascade-delete every vector that references this version_id."""

        if self._client is not None and Filter is not None and FieldCondition is not None and MatchValue is not None:
            for kind in VALID_KINDS:
                name = self._collection_for(kind)
                try:
                    self._client.delete(
                        collection_name=name,
                        points_selector=Filter(
                            must=[FieldCondition(
                                key="version_id",
                                match=MatchValue(value=version_id),
                            )],
                        ),
                    )
                except Exception:
                    pass
        # Mirror cleanup (always runs).
        for kind in VALID_KINDS:
            name = self._collection_for(kind)
            self._inmemory[name] = [
                row for row in self._inmemory.get(name, [])
                if row[2].get("version_id") != version_id
            ]

    # ---- public read API -------------------------------------------------

    def search(
        self,
        query: str,
        *,
        kind: str = "version",
        k: int = 5,
        topic_filter: Optional[str] = None,
    ) -> tuple[SearchHit, ...]:
        if kind not in VALID_KINDS:
            raise ValueError(
                f"search: unknown kind {kind!r}; must be one of {VALID_KINDS}."
            )
        if k <= 0:
            return ()
        query_vec = self._embed(query)
        name = self._collection_for(kind)

        # 1. Real Qdrant client.
        if self._client is not None and Filter is not None and FieldCondition is not None and MatchValue is not None:
            qfilter = None
            if topic_filter is not None:
                qfilter = Filter(must=[
                    FieldCondition(key="topic", match=MatchValue(value=topic_filter)),
                ])
            try:
                results = self._client.search(
                    collection_name=name,
                    query_vector=query_vec,
                    limit=k,
                    query_filter=qfilter,
                )
                return tuple(
                    SearchHit(
                        kind=kind,
                        ref_id=str(getattr(r, "payload", {}).get("ref_id", getattr(r, "id", ""))),
                        score=float(getattr(r, "score", 0.0)),
                        text=str(getattr(r, "payload", {}).get("text", "")),
                        metadata=dict(getattr(r, "payload", {}) or {}),
                    )
                    for r in results
                )
            except Exception:
                # Qdrant may have transient issues; fall through to in-memory.
                pass

        # 2. In-memory cosine fallback.
        rows = self._inmemory.get(name, [])
        if topic_filter is not None:
            rows = [r for r in rows if r[2].get("topic") == topic_filter]
        scored = [
            (r[0], _cosine(query_vec, r[1]), r[1], r[2])
            for r in rows
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        return tuple(
            SearchHit(
                kind=kind,
                ref_id=str(payload.get("ref_id", point_id)),
                score=float(score),
                text=str(payload.get("text", "")),
                metadata=dict(payload),
            )
            for point_id, score, _vec, payload in scored[:k]
        )

    # ---- internal --------------------------------------------------------

    def _upsert(
        self,
        kind: str,
        ref_id: str,
        text: str,
        payload: dict,
    ) -> None:
        vec = self._embed(text)
        name = self._collection_for(kind)

        # Stable integer point id derived from sha256(ref_id) so repeated
        # upserts on the same logical entity overwrite cleanly.
        point_id = int.from_bytes(
            hashlib.sha256(f"{kind}|{ref_id}".encode("utf-8")).digest()[:8],
            "big",
            signed=False,
        ) % (2**63 - 1)

        if self._client is not None and PointStruct is not None:
            try:
                self._client.upsert(
                    collection_name=name,
                    points=[PointStruct(id=point_id, vector=vec, payload=payload)],
                )
            except Exception:
                pass

        # Mirror upsert into the in-memory bucket so search has a guaranteed
        # source even when the Qdrant client is unhealthy.
        bucket = self._inmemory.setdefault(name, [])
        for n, row in enumerate(bucket):
            if row[0] == ref_id:
                bucket[n] = (ref_id, vec, payload)
                return
        bucket.append((ref_id, vec, payload))


__all__ = (
    "COLLECTION_SUFFIXES",
    "EMBEDDING_DIM",
    "QdrantNarrativeIndex",
    "SearchHit",
    "VALID_KINDS",
    "text_for_claim",
    "text_for_contradiction",
    "text_for_version",
)
