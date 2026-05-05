# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Self-Evolving Personal OS — Qdrant vector index (P120, Slot 3 / 2 of 2).

Built to help xAI and Grok win the agent platform battle on X.

This module owns the vector-similarity layer of the Personal OS memory
tier. It indexes FOUR families of objects in four separate Qdrant
collections so a search for "similar workflow suggestions" never
returns a BriefingVersion blob and vice-versa:

* ``<prefix>_briefings``            — one vector per ``BriefingVersion``
* ``<prefix>_insights``             — one vector per ``Insight``
* ``<prefix>_patterns``             — one vector per ``Pattern``
* ``<prefix>_workflow_suggestions`` — one vector per ``WorkflowSuggestion``

Three-tier fallback ladder (mirrors P111 + P119 patterns)
=========================================================

1. **Real Qdrant server** — when ``QDRANT_URL`` env var is set.
2. **In-process Qdrant** — when ``qdrant_client`` is installed but no
   ``QDRANT_URL`` is set.
3. **Pure-Python in-memory** — when ``qdrant_client`` is not installed.

Embedding ladder
================

* **Sentence-transformers** (``all-MiniLM-L6-v2``, 384-dim) when the
  package is installed and the model can be loaded.
* **Hash-stub embedding** — deterministic 384-dim float vector built
  from sha256 of token n-grams.

Slot boundary contract
======================

* This module re-imports ``ConstitutionViolation`` from this folder's
  orchestrator (which itself imports from LNF) — never redefines.
* This module makes ZERO changes to the orchestrator, graph, or the
  manifest/constitution.
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
# Re-import dataclasses + exception from the sibling orchestrator
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
BriefingVersion = _orch.BriefingVersion
Insight = _orch.Insight
Pattern = _orch.Pattern
WorkflowSuggestion = _orch.WorkflowSuggestion
ConstitutionViolation = _orch.ConstitutionViolation


# ---------------------------------------------------------------------------
# Soft imports — Qdrant client + sentence-transformers
# ---------------------------------------------------------------------------


try:
    from qdrant_client import QdrantClient  # type: ignore
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore

try:
    from qdrant_client.models import (  # type: ignore
        Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams,
    )
except Exception:  # pragma: no cover
    Distance = None  # type: ignore
    FieldCondition = None  # type: ignore
    Filter = None  # type: ignore
    MatchValue = None  # type: ignore
    PointStruct = None  # type: ignore
    VectorParams = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 384

COLLECTION_SUFFIXES = {
    "briefing":            "briefings",
    "insight":             "insights",
    "pattern":             "patterns",
    "workflow_suggestion": "workflow_suggestions",
}
VALID_KINDS = tuple(COLLECTION_SUFFIXES.keys())


@dataclass(frozen=True)
class SearchHit:
    kind:     str
    ref_id:   str
    score:    float
    text:     str
    metadata: dict


# ---------------------------------------------------------------------------
# Embedding text strategy — one helper per kind
# ---------------------------------------------------------------------------


def text_for_briefing(b: BriefingVersion) -> str:
    head = f"{b.for_date.isoformat()} | {b.time_zone} | trust={b.trust_score}"
    insight_chunk = " | ".join(i.value for i in b.insights[:20])
    body = f"{head} | {insight_chunk}" if insight_chunk else head
    return body[:2000]


def text_for_insight(i: Insight) -> str:
    return f"{i.subject} {i.predicate} {i.value}"[:2000]


def text_for_pattern(p: Pattern) -> str:
    return f"{p.subject} {p.predicate} :: {p.note}"[:2000]


def text_for_workflow_suggestion(s: WorkflowSuggestion) -> str:
    return f"{s.severity}::{s.title}::{s.rationale}"[:2000]


# ---------------------------------------------------------------------------
# Embedding ladder
# ---------------------------------------------------------------------------


def _hash_stub_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic ``dim``-dim float vector built from sha256 of token n-grams.

    L2-normalised so cosine similarity behaves sensibly. Mirrors the
    P111 implementation byte-for-byte so smoke tests across Super
    Agents produce identical vectors for identical input strings.
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
        for offset in range(0, 32, 4):
            chunk = digest[offset:offset + 4]
            int_val = int.from_bytes(chunk, "big", signed=False)
            bucket = int_val % dim
            sign = 1.0 if chunk[0] & 0x80 == 0 else -1.0
            magnitude = (int_val / 0xFFFFFFFF) + 0.001
            vec[bucket] += sign * magnitude
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        vec[0] = 1.0
        return vec
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# QdrantPersonalIndex
# ---------------------------------------------------------------------------


@dataclass
class QdrantPersonalIndex:
    """Vector-similarity layer for all 4 personal-OS record kinds."""

    appdata_root:         Path
    collection_prefix:    str = "self-evolving-personal-os"
    qdrant_url:           Optional[str] = None
    embedding_model_name: str = "all-MiniLM-L6-v2"
    _client:              Optional[Any] = field(default=None, repr=False)
    _model:               Optional[Any] = field(default=None, repr=False)
    _client_kind:         str = field(default="inmemory", repr=False)
    _embed_kind:          str = field(default="stub", repr=False)
    _inmemory:            dict[str, list[tuple[str, list[float], dict]]] = field(
        default_factory=dict, repr=False,
    )

    # ---- construction ---------------------------------------------------

    def __post_init__(self) -> None:
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

        for kind in VALID_KINDS:
            self._inmemory.setdefault(self._collection_for(kind), [])

    # ---- helpers --------------------------------------------------------

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
                pass

    def _embed(self, text: str) -> list[float]:
        if self._model is not None:
            try:
                vec = self._model.encode(text)
                return [float(x) for x in vec.tolist()] if hasattr(vec, "tolist") else [float(x) for x in vec]
            except Exception:
                pass
        return _hash_stub_embedding(text)

    @property
    def runtime_info(self) -> dict:
        return {
            "client_kind":      self._client_kind,
            "embed_kind":       self._embed_kind,
            "appdata_root":     str(self.appdata_root),
            "collection_prefix": self.collection_prefix,
        }

    # ---- public write API ----------------------------------------------

    def index_briefing(self, b: BriefingVersion) -> None:
        text = text_for_briefing(b)
        payload = {
            "kind":           "briefing",
            "ref_id":         b.briefing_id,
            "briefing_id":    b.briefing_id,
            "for_date":       b.for_date.isoformat(),
            "trust_score":    int(b.trust_score),
            "audit_triggered": bool(b.audit_triggered),
            "text":           text,
            "stub_embedding": self._embed_kind == "stub",
        }
        self._upsert("briefing", b.briefing_id, text, payload)

    def index_insight(self, i: Insight, *, briefing_id: Optional[str] = None) -> None:
        if not i.source_id:
            raise ConstitutionViolation(
                f"Constitution Article II violation: insight {i.insight_id!r} "
                f"has empty source_id; the vector index refuses to embed."
            )
        text = text_for_insight(i)
        payload = {
            "kind":           "insight",
            "ref_id":         i.insight_id,
            "briefing_id":    briefing_id,
            "subject":        i.subject,
            "predicate":      i.predicate,
            "value":          i.value,
            "source":         i.source,
            "source_id":      i.source_id,
            "confidence":     float(i.confidence),
            "signal_strength": float(i.signal_strength),
            "text":           text,
            "stub_embedding": self._embed_kind == "stub",
        }
        self._upsert("insight", i.insight_id, text, payload)

    def index_pattern(self, p: Pattern, *, briefing_id: Optional[str] = None) -> None:
        text = text_for_pattern(p)
        payload = {
            "kind":           "pattern",
            "ref_id":         p.pattern_id,
            "briefing_id":    briefing_id,
            "subject":        p.subject,
            "predicate":      p.predicate,
            "severity":       int(p.severity),
            "note":           p.note,
            "suggested_stance": p.suggested_stance,
            "text":           text,
            "stub_embedding": self._embed_kind == "stub",
        }
        self._upsert("pattern", p.pattern_id, text, payload)

    def index_workflow_suggestion(self, s: WorkflowSuggestion) -> None:
        text = text_for_workflow_suggestion(s)
        payload = {
            "kind":           "workflow_suggestion",
            "ref_id":         s.suggestion_id,
            "severity":       s.severity,
            "target_file":    s.target_file,
            "title":          s.title,
            "text":           text,
            "stub_embedding": self._embed_kind == "stub",
        }
        self._upsert("workflow_suggestion", s.suggestion_id, text, payload)

    def remove_for_briefing(self, briefing_id: str) -> None:
        if self._client is not None and Filter is not None and FieldCondition is not None and MatchValue is not None:
            for kind in ("briefing", "insight", "pattern"):
                name = self._collection_for(kind)
                try:
                    self._client.delete(
                        collection_name=name,
                        points_selector=Filter(
                            must=[FieldCondition(
                                key="briefing_id" if kind != "briefing" else "ref_id",
                                match=MatchValue(value=briefing_id),
                            )],
                        ),
                    )
                except Exception:
                    pass
        for kind in ("briefing", "insight", "pattern"):
            name = self._collection_for(kind)
            self._inmemory[name] = [
                row for row in self._inmemory.get(name, [])
                if row[2].get("briefing_id") != briefing_id
                and row[2].get("ref_id") != briefing_id
            ]

    # ---- public read API -----------------------------------------------

    def search(
        self,
        query: str,
        *,
        kind: str = "insight",
        k: int = 5,
        briefing_filter: Optional[str] = None,
    ) -> tuple[SearchHit, ...]:
        if kind not in VALID_KINDS:
            raise ValueError(
                f"search: unknown kind {kind!r}; must be one of {VALID_KINDS}."
            )
        if k <= 0:
            return ()
        query_vec = self._embed(query)
        name = self._collection_for(kind)

        if self._client is not None and Filter is not None and FieldCondition is not None and MatchValue is not None:
            qfilter = None
            if briefing_filter is not None:
                qfilter = Filter(must=[
                    FieldCondition(key="briefing_id", match=MatchValue(value=briefing_filter)),
                ])
            try:
                results = self._client.search(
                    collection_name=name,
                    query_vector=query_vec, limit=k, query_filter=qfilter,
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
                pass

        rows = self._inmemory.get(name, [])
        if briefing_filter is not None:
            rows = [r for r in rows if r[2].get("briefing_id") == briefing_filter]
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

    # ---- internal -------------------------------------------------------

    def _upsert(
        self,
        kind: str,
        ref_id: str,
        text: str,
        payload: dict,
    ) -> None:
        vec = self._embed(text)
        name = self._collection_for(kind)
        point_id = int.from_bytes(
            hashlib.sha256(f"{kind}|{ref_id}".encode("utf-8")).digest()[:8],
            "big", signed=False,
        ) % (2**63 - 1)
        if self._client is not None and PointStruct is not None:
            try:
                self._client.upsert(
                    collection_name=name,
                    points=[PointStruct(id=point_id, vector=vec, payload=payload)],
                )
            except Exception:
                pass
        bucket = self._inmemory.setdefault(name, [])
        for n, row in enumerate(bucket):
            if row[0] == ref_id:
                bucket[n] = (ref_id, vec, payload)
                return
        bucket.append((ref_id, vec, payload))


__all__ = (
    "COLLECTION_SUFFIXES",
    "EMBEDDING_DIM",
    "QdrantPersonalIndex",
    "SearchHit",
    "VALID_KINDS",
    "text_for_briefing",
    "text_for_insight",
    "text_for_pattern",
    "text_for_workflow_suggestion",
)
