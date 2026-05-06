# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Memory Layer (P111, Recipe C Slot 3).

Built for xAI, X, Grok and the ecosystem community. ❤️

This package is the durable, semantic-search-capable replacement for the
default ``InMemoryMemoryStore`` shipped with P110's orchestration core.
It composes two siblings:

* ``mem0_setup.Mem0NarrativeStore`` — the standard structured store
  (Mem0 primary, direct SQLite fallback). Owns the SynthesisVersion
  blob + indexed relational rows for fast lookup by source_id, topic,
  and parent_version_id.
* ``qdrant_index.QdrantNarrativeIndex`` — the vector-similarity layer
  (Qdrant primary, in-memory cosine fallback; sentence-transformers
  primary, hash-stub fallback). Owns three collections — versions,
  claims, contradictions — for "find me other things that look like
  this" workflows.

Slot boundary contract
======================

* This module satisfies the ``MemoryStore`` Protocol from P110's
  ``orchestrator.py`` exactly (4 methods: ``remember``, ``recall``,
  ``latest_version_for``, ``history_for``). The orchestrator wires the
  store in via ``LivingNarrativeFabric.with_dependencies(memory=...)``.
* On the SAME class, this module exposes 6 additional rich methods
  for slots 5 / 6 / 7 to call directly: ``store_narrative_fragment``,
  ``retrieve_by_provenance``, ``search_similar_fragments``,
  ``flag_contradiction``, ``rewind_to_version``, ``get_audit_trail``.
* This module makes ZERO changes to ``orchestrator.py`` or ``graph.py``.
  Every dependency on those modules is via re-import only — see
  ``mem0_setup._import_orchestrator`` and ``qdrant_index._import_orchestrator``
  for the exact relative-then-absolute idiom (mirrors ``graph.py``
  lines 182-187).

Layered fallback (zero-install smoke test)
==========================================

The package is designed to run on a fresh Windows 11 box with only the
Slot-2 deps installed (``pydantic``, ``langgraph``, ``httpx``, ``pyyaml``).
When ``mem0``, ``qdrant_client``, and ``sentence_transformers`` are all
missing, the structured tier degrades to direct SQLite, the vector
tier degrades to an in-memory cosine list, and the embedding tier
degrades to a deterministic sha256-bucket pseudo-vector. The 10-check
smoke test below works in every fallback combination.

CLI smoke test
==============

::

    cd templates\\super-agents\\living-narrative-fabric
    python memory\\__init__.py

Prints ``P111 memory layer smoke OK`` on success; raises
``AssertionError`` on any check failure. The smoke test exercises every
public method and the full ``LivingNarrativeFabric`` integration loop.

Plug-in pattern
===============

::

    from memory import build_memory_store
    from orchestrator import LivingNarrativeFabric

    fabric = LivingNarrativeFabric().with_dependencies(
        memory=build_memory_store(),                     # Mem0+Qdrant composite
    )
    v1 = fabric.synthesize(topic="Grok Agent OS launch", time_range="7d")
    v2 = fabric.synthesize(topic="Grok Agent OS launch", time_range="30d")

    # 6 rich methods are available on the store directly
    store = fabric.memory
    hits = store.search_similar_fragments("Grok Agent OS", kind="version", k=3)
    rewind = store.rewind_to_version(v2.version_id)
    audit  = store.get_audit_trail(v2.version_id, full_chain=True)
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence, Union

# ---------------------------------------------------------------------------
# Re-import from orchestrator (relative-then-absolute idiom)
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
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
MemoryStore = _orch.MemoryStore
LivingNarrativeFabric = _orch.LivingNarrativeFabric
_default_appdata_root = _orch._default_appdata_root


# ---------------------------------------------------------------------------
# Sibling imports — these must work when the package is loaded normally
# (i.e. ``from memory import ...``) AND when ``__init__.py`` is run
# directly via ``python memory/__init__.py`` for the smoke test.
# ---------------------------------------------------------------------------


def _import_siblings():
    try:
        from . import mem0_setup as _mod_mem0  # type: ignore
        from . import qdrant_index as _mod_qdrant  # type: ignore
        return _mod_mem0, _mod_qdrant
    except Exception:
        pass
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    return (
        importlib.import_module("mem0_setup"),
        importlib.import_module("qdrant_index"),
    )


_mod_mem0, _mod_qdrant = _import_siblings()
Mem0NarrativeStore = _mod_mem0.Mem0NarrativeStore
QdrantNarrativeIndex = _mod_qdrant.QdrantNarrativeIndex
SearchHit = _mod_qdrant.SearchHit
AuditEntry = _mod_mem0.AuditEntry
serialise_synthesis_version = _mod_mem0.serialise_synthesis_version
serialise_claim = _mod_mem0.serialise_claim


# ---------------------------------------------------------------------------
# Public result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceHits:
    """The return shape of ``retrieve_by_provenance``.

    Carries both the matching claims AND the SynthesisVersions those
    claims belong to so callers in slots 5 / 6 / 7 can render a full
    "where did this source_id show up" view in a single round-trip.
    """

    claims:   tuple[Claim, ...]
    versions: tuple[SynthesisVersion, ...]


@dataclass(frozen=True)
class RewindResult:
    """The return shape of ``rewind_to_version``.

    * ``version`` — the target SynthesisVersion (verbatim).
    * ``parent_chain`` — every ancestor in oldest-first order
      ``(root, ..., grandparent, parent)``. Empty tuple when the target
      is itself the first version on its topic.
    * ``descendants`` — every later version that links back to this one
      through ``parent_version_id`` (oldest-first within each branch).
    """

    version:      SynthesisVersion
    parent_chain: tuple[SynthesisVersion, ...]
    descendants:  tuple[SynthesisVersion, ...]


# ---------------------------------------------------------------------------
# Mem0QdrantStore — composite that satisfies MemoryStore + offers rich API
# ---------------------------------------------------------------------------


#: Type alias for what ``store_narrative_fragment`` accepts.
Fragment = Union[SynthesisVersion, Claim, Contradiction]


@dataclass
class Mem0QdrantStore:
    """The composite memory store the orchestrator wires in via ``with_dependencies``.

    Implements the ``MemoryStore`` Protocol exactly:
      * ``remember(version)``
      * ``recall(version_id)``
      * ``latest_version_for(topic)``
      * ``history_for(topic)``

    Plus 6 rich methods for slots 5 / 6 / 7:
      * ``store_narrative_fragment(fragment, *, version_id, kind="auto")``
      * ``retrieve_by_provenance(source_id)``
      * ``search_similar_fragments(query, *, kind="version", k=5, topic_filter=None)``
      * ``flag_contradiction(contradiction_id, *, reason, flagged_by="user")``
      * ``rewind_to_version(version_id)``
      * ``get_audit_trail(version_id, *, full_chain=True)``

    Construction goes through the ``build_memory_store`` factory below
    rather than this class's ``__init__`` so the layered fallback +
    appdata-path resolution stay in one place.
    """

    structured:        Mem0NarrativeStore
    vectors:           QdrantNarrativeIndex
    appdata_root:      Path
    collection_prefix: str = "living-narrative-fabric"

    # ---- Protocol-required (4) -------------------------------------------

    def remember(self, version: SynthesisVersion) -> None:
        """Persist a SynthesisVersion to the official store + vector index.

        Order of operations:

        1. ``structured.put_version`` — atomic SQLite transaction. Raises
           ``ConstitutionViolation`` immediately if any claim has empty
           ``source_id``; nothing is written, the call aborts.
        2. ``vectors.index_version`` — one vector for the whole version.
        3. ``vectors.index_claim`` — one vector per claim.
        4. ``vectors.index_contradiction`` — one vector per contradiction.

        If step 1 raises, steps 2-4 never run. If any of steps 2-4 raises
        on a vector backend issue (e.g. Qdrant unreachable), we propagate
        so the caller knows the indexing was partial — but the official
        SQLite write is already durable.
        """

        self.structured.put_version(version)
        self.vectors.index_version(version)
        for c in version.claims:
            self.vectors.index_claim(c, version_id=version.version_id)
        for cd in version.contradictions:
            self.vectors.index_contradiction(cd, version_id=version.version_id)

    def recall(self, version_id: str) -> Optional[SynthesisVersion]:
        return self.structured.get_version(version_id)

    def latest_version_for(self, topic: str) -> Optional[SynthesisVersion]:
        return self.structured.latest_for_topic(topic)

    def history_for(self, topic: str) -> Sequence[SynthesisVersion]:
        return self.structured.history_for_topic(topic)

    # ---- Rich API (6) ----------------------------------------------------

    def store_narrative_fragment(
        self,
        fragment: Fragment,
        *,
        version_id: Optional[str] = None,
        kind: str = "auto",
    ) -> str:
        """Store a single fragment (Version, Claim, or Contradiction).

        ``kind`` defaults to ``"auto"`` which infers via ``isinstance``.
        Returns the fragment's stable id (``version_id`` /
        ``claim_id`` / ``contradiction_id``).

        Constitution rule: ``Claim`` fragments with empty ``source_id``
        raise ``ConstitutionViolation`` (re-raised by ``serialise_claim``).
        """

        if kind == "auto":
            if isinstance(fragment, SynthesisVersion):
                kind = "version"
            elif isinstance(fragment, Claim):
                kind = "claim"
            elif isinstance(fragment, Contradiction):
                kind = "contradiction"
            else:
                raise TypeError(
                    f"store_narrative_fragment: cannot infer kind for "
                    f"{type(fragment).__name__!r}; pass kind= explicitly."
                )

        if kind == "version":
            assert isinstance(fragment, SynthesisVersion)
            self.remember(fragment)
            return fragment.version_id
        if kind == "claim":
            assert isinstance(fragment, Claim)
            if version_id is None:
                raise ValueError(
                    "store_narrative_fragment(kind='claim') requires version_id="
                )
            self.vectors.index_claim(fragment, version_id=version_id)
            return fragment.claim_id
        if kind == "contradiction":
            assert isinstance(fragment, Contradiction)
            if version_id is None:
                raise ValueError(
                    "store_narrative_fragment(kind='contradiction') requires version_id="
                )
            self.vectors.index_contradiction(fragment, version_id=version_id)
            return fragment.contradiction_id
        raise ValueError(f"store_narrative_fragment: unknown kind {kind!r}")

    def retrieve_by_provenance(self, source_id: str) -> ProvenanceHits:
        if not source_id:
            raise ConstitutionViolation(
                "Constitution violation: retrieve_by_provenance refuses to "
                "search for empty source_id; citations are mandatory."
            )
        claims = self.structured.claims_by_source_id(source_id)
        versions = self.structured.versions_by_source_id(source_id)
        return ProvenanceHits(claims=claims, versions=versions)

    def search_similar_fragments(
        self,
        query: str,
        *,
        kind: str = "version",
        k: int = 5,
        topic_filter: Optional[str] = None,
    ) -> tuple[SearchHit, ...]:
        return self.vectors.search(
            query, kind=kind, k=k, topic_filter=topic_filter,
        )

    def flag_contradiction(
        self,
        contradiction_id: str,
        *,
        reason: str,
        flagged_by: str = "user",
    ) -> str:
        return self.structured.append_flag(
            contradiction_id=contradiction_id,
            reason=reason,
            flagged_by=flagged_by,
        )

    def rewind_to_version(self, version_id: str) -> Optional[RewindResult]:
        version = self.structured.get_version(version_id)
        if version is None:
            return None
        parent_chain = self.structured.walk_chain(version_id)
        descendants = self.structured.descendants_of(version_id)
        return RewindResult(
            version=version,
            parent_chain=parent_chain,
            descendants=descendants,
        )

    def get_audit_trail(
        self,
        version_id: str,
        *,
        full_chain: bool = True,
    ) -> tuple[AuditEntry, ...]:
        return self.structured.audit_trail_for(version_id, full_chain=full_chain)

    # ---- introspection (used by smoke test + slots 5/6/7) ---------------

    @property
    def runtime_info(self) -> dict:
        """Surface the active fallback tier in each layer."""

        return {
            "structured_backend": (
                "mem0+sqlite"
                if self.structured._mem0_client is not None
                else "sqlite-only"
            ),
            "vector_backend":    self.vectors._client_kind,
            "embedding_backend": self.vectors._embed_kind,
            "appdata_root":      str(self.appdata_root),
            "collection_prefix": self.collection_prefix,
        }


# ---------------------------------------------------------------------------
# Factory + convenience wirers
# ---------------------------------------------------------------------------


def build_memory_store(
    *,
    appdata_root:        Optional[Path] = None,
    collection_prefix:   str = "living-narrative-fabric",
    qdrant_url:          Optional[str] = None,
    embedding_model:     str = "all-MiniLM-L6-v2",
    sqlite_filename:     str = "narrative.sqlite3",
) -> Mem0QdrantStore:
    """Build a fully-wired ``Mem0QdrantStore`` with sensible defaults.

    Parameters
    ----------
    appdata_root :
        Local data directory. When ``None``, resolves via
        ``orchestrator._default_appdata_root()`` (Windows-correct on
        Windows, ``~/.local/share`` elsewhere).
    collection_prefix :
        Qdrant collection prefix; the three real collection names become
        ``f"{prefix}_versions"``, ``f"{prefix}_claims"``, and
        ``f"{prefix}_contradictions"``.
    qdrant_url :
        Optional Qdrant server URL; takes precedence over
        ``QDRANT_URL`` env var. When both are unset, the index uses an
        in-process ``QdrantClient(path=...)`` if ``qdrant_client`` is
        installed, otherwise an in-memory cosine list.
    embedding_model :
        Sentence-transformers model name; defaults to ``all-MiniLM-L6-v2``.
        When ``sentence-transformers`` is not installed, the index falls
        through to the deterministic hash-stub embedding.
    sqlite_filename :
        Filename for the official SQLite store, relative to
        ``<appdata_root>/mem0/``.
    """

    root = appdata_root if appdata_root is not None else _default_appdata_root()
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    sqlite_path = root / "mem0" / sqlite_filename

    structured = Mem0NarrativeStore(
        appdata_root=root,
        sqlite_path=sqlite_path,
    )
    vectors = QdrantNarrativeIndex(
        appdata_root=root,
        collection_prefix=collection_prefix,
        qdrant_url=qdrant_url,
        embedding_model_name=embedding_model,
    )
    return Mem0QdrantStore(
        structured=structured,
        vectors=vectors,
        appdata_root=root,
        collection_prefix=collection_prefix,
    )


def with_memory_layer(
    fabric: LivingNarrativeFabric,
    **kwargs: Any,
) -> LivingNarrativeFabric:
    """Return a copy of ``fabric`` with a fresh ``Mem0QdrantStore`` injected."""

    return fabric.with_dependencies(memory=build_memory_store(**kwargs))


# ---------------------------------------------------------------------------
# Smoke test (zero-install — runs on the Slot-2 deps alone)
# ---------------------------------------------------------------------------


def _build_fixture_versions(store: Mem0QdrantStore, topic: str) -> tuple[SynthesisVersion, SynthesisVersion]:
    """Build two real SynthesisVersions on the same topic via the orchestrator."""

    fabric = LivingNarrativeFabric().with_dependencies(memory=store)
    v1 = fabric.synthesize(topic=topic, time_range="7d")
    v2 = fabric.synthesize(topic=topic, time_range="30d")
    return v1, v2


def run_smoke_test(*, verbose: bool = True) -> None:
    """Self-contained 10-check smoke test for the memory layer.

    Uses a temporary directory under the user's appdata so it never
    pollutes a production database. Cleans up on exit.
    """

    import shutil
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="lnf-memory-smoke-"))
    try:
        store = build_memory_store(appdata_root=tmp_root)

        info = store.runtime_info
        if verbose:
            print(f"[smoke] runtime_info = {info}")

        # ---- (1) Protocol satisfaction -----------------------------------
        # ``MemoryStore`` is a runtime_checkable Protocol on the orchestrator.
        assert isinstance(store, MemoryStore), (
            "Mem0QdrantStore does not satisfy the MemoryStore Protocol."
        )

        # ---- (2)+(3)+(4) versioning + recall ----------------------------
        topic = "lnf-smoke-topic"
        v1, v2 = _build_fixture_versions(store, topic)

        recalled_v1 = store.recall(v1.version_id)
        assert recalled_v1 is not None, "recall(v1.id) returned None."
        assert recalled_v1.version_id == v1.version_id
        assert recalled_v1.topic == topic

        latest = store.latest_version_for(topic)
        assert latest is not None and latest.version_id == v2.version_id, (
            f"latest_version_for(topic) returned {latest!r}; expected {v2.version_id}."
        )

        history = tuple(store.history_for(topic))
        assert len(history) == 2 and history[0].version_id == v1.version_id, (
            f"history_for(topic) returned {len(history)} versions; expected 2 ordered (v1, v2)."
        )
        assert history[1].version_id == v2.version_id

        # ---- (5) ConstitutionViolation on empty source_id -----------------
        bad_claim = Claim(
            claim_id="bad-claim-id",
            subject="x", predicate="y", value="z",
            source="x_search",
            source_id="",  # ← Constitution violation
            confidence=0.5,
            extracted_at=datetime.now(timezone.utc),
            sentiment=None,
        )
        try:
            store.store_narrative_fragment(
                bad_claim, version_id=v1.version_id, kind="claim",
            )
            raise AssertionError(
                "store_narrative_fragment accepted a claim with empty source_id; "
                "ConstitutionViolation should have been raised."
            )
        except ConstitutionViolation:
            pass  # expected

        # ---- (6) retrieve_by_provenance ----------------------------------
        # Pick a real source_id from v1's claims.
        assert v1.claims, "fixture v1 has no claims; cannot test provenance."
        sample_source_id = v1.claims[0].source_id
        prov = store.retrieve_by_provenance(sample_source_id)
        assert any(c.source_id == sample_source_id for c in prov.claims), (
            f"retrieve_by_provenance({sample_source_id!r}) did not return the "
            f"matching claim."
        )
        assert any(v.version_id == v1.version_id for v in prov.versions), (
            f"retrieve_by_provenance({sample_source_id!r}) did not include v1 "
            f"in its versions tuple."
        )

        # ---- (7) flag_contradiction + audit_trail -----------------------
        # Use a contradiction from whichever fixture has one.
        contradictions = list(v2.contradictions) + list(v1.contradictions)
        if contradictions:
            cd = contradictions[0]
            flag_id = store.flag_contradiction(
                cd.contradiction_id,
                reason="smoke-test user disagrees",
                flagged_by="smoke-runner",
            )
            assert flag_id, "flag_contradiction returned empty flag_id."

            # find which version owns the flagged contradiction
            owner_version_id = (
                v2.version_id if any(c.contradiction_id == cd.contradiction_id for c in v2.contradictions)
                else v1.version_id
            )
            audit = store.get_audit_trail(owner_version_id, full_chain=True)
            assert any(
                "smoke-test user disagrees" in entry.reason
                and entry.kind == "user-flag"
                for entry in audit
            ), (
                f"get_audit_trail did not contain the user-flag entry; got {audit}."
            )
        else:
            if verbose:
                print("[smoke] (7) no contradictions in fixture; skipping flag check.")

        # ---- (8) rewind_to_version --------------------------------------
        rewind = store.rewind_to_version(v2.version_id)
        assert rewind is not None, "rewind_to_version(v2.id) returned None."
        assert rewind.version.version_id == v2.version_id
        assert rewind.parent_chain and rewind.parent_chain[-1].version_id == v1.version_id, (
            f"rewind.parent_chain[-1] should be v1; got {rewind.parent_chain!r}."
        )

        # ---- (9) search_similar_fragments -------------------------------
        hits = store.search_similar_fragments(topic, kind="version", k=2)
        assert len(hits) >= 1, (
            f"search_similar_fragments returned no hits; expected >= 1."
        )

        # ---- (10) integration (already covered by the fixture builder) --
        # Re-prove the orchestrator integration by calling history_for one
        # more time and confirming the persisted state survives a fresh
        # LivingNarrativeFabric instance pointed at the same store.
        fresh_fabric = LivingNarrativeFabric().with_dependencies(memory=store)
        survived = tuple(fresh_fabric.history(topic))
        assert len(survived) == 2, (
            f"integration check failed: a fresh LivingNarrativeFabric pointed "
            f"at the same store sees {len(survived)} versions; expected 2."
        )

        if verbose:
            print("P111 memory layer smoke OK")
    finally:
        # Best-effort cleanup of the temp dir; ignore Windows file-locking edge cases.
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = (
    "AuditEntry",
    "ConstitutionViolation",
    "Mem0QdrantStore",
    "MemoryStore",
    "ProvenanceHits",
    "RewindResult",
    "SearchHit",
    "build_memory_store",
    "run_smoke_test",
    "with_memory_layer",
)


if __name__ == "__main__":  # pragma: no cover
    run_smoke_test()
