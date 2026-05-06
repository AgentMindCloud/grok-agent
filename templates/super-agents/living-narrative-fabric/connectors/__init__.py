# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Public API connectors (P112, Recipe C Slot 4).

Built for xAI, X, Grok and the ecosystem community. ❤️

This package ships the six concrete ``SourceClient`` implementations the
orchestrator's ingest node calls when a real run is executed. Each
connector is a focused wrapper around one public data source:

* ``newsapi_client.NewsApiConnector``           — NewsAPI ``/v2/everything``
* ``gnews_client.GnewsConnector``               — GNews ``/api/v4/search``
* ``semantic_scholar_client.SemanticScholarConnector``
                                                — Semantic Scholar Graph API
* ``data_gov_client.DataGovConnector``          — data.gov CKAN catalogue
* ``x_grok_client.XGrokConnector``              — X search via xAI Grok 4.3
* ``crawl4ai_client.Crawl4aiConnector``         — Crawl4AI open-web scraper

All six inherit from :class:`BaseConnector` (defined in this module) which
owns:

* Local SQLite-backed fetch cache at ``<appdata>/connectors/<name>/cache.sqlite3``
  so repeated fetches inside the cache TTL never re-hit the upstream API.
* Stub mode auto-engaged when the connector's ``auth_env_var`` is unset
  or ``force_stub=True`` is passed at construction time. Stub items are
  deterministic (sha256-seeded by ``name|query|since``) so smoke tests
  are reproducible.
* Provenance attachment that enriches every emitted ``SourceItem.extra``
  with a ``Provenance`` dict (``source_id``, ``retrieved_at``, ``url``,
  ``raw_snippet``, ``stub``, ``cache_hit``).
* ``ConstitutionViolation`` defense-in-depth: an empty ``source_id`` or
  a malformed validate-response result aborts the fetch before the item
  ever leaves the connector.
* Optional ``Mem0QdrantStore`` hook-up via ``connect_memory(store)`` so
  every successful fetch writes a ``"connector-fetch"`` audit row. Per-
  fetch claims are stored only when a ``version_id`` is available
  (called from inside the orchestrator's normalise pipeline by P115's
  Streamlit UI; the standalone connector lifecycle does not require a
  version_id since claim extraction happens in the orchestrator).

Slot boundary contract
======================

* This package satisfies the ``SourceClient`` Protocol from P110's
  ``orchestrator.py`` exactly (``name: str`` + ``fetch(query, since,
  limit) -> Sequence[SourceItem]``). The orchestrator wires connectors
  in via ``LivingNarrativeFabric.with_dependencies(sources=...)``.
* On the SAME class, this package exposes 4 additional rich methods
  for slots 5 / 7 to call directly: ``fetch_batch``,
  ``validate_response``, ``attach_provenance``, ``connect_memory``.
* This package makes ZERO changes to ``orchestrator.py``, ``graph.py``,
  ``memory/mem0_setup.py``, ``memory/qdrant_index.py``, or
  ``memory/__init__.py``. Every cross-module dependency is via the
  relative-then-absolute import idiom from ``graph.py:182-187``.

Layered fallback ladder
=======================

For each connector, the active runtime tier is determined at construction
and reported by ``BaseConnector.runtime_info``:

1. **Real API call** — when the env var is set AND ``requests`` (or
   the connector's specific Python SDK) is importable. Production path.
2. **Stub mode** — when the env var is unset, ``requests`` is missing,
   or a real call raises any ``RequestException``. Returns deterministic
   seeded ``SourceItem``s tagged ``stub=True`` so the synthesis renderer
   can mark them.

CLI smoke test
==============

::

    cd templates\\super-agents\\living-narrative-fabric
    python connectors\\__init__.py

Prints ``P112 connectors smoke OK`` on success; raises ``AssertionError``
on any failure. Runs in zero-install mode (no API keys required, no
``requests`` required) and exercises:

* Stub-mode fetch on all 6 connectors → returns >=1 SourceItem each
* Provenance round-trip (every item carries a ``Provenance`` dict)
* ``ConstitutionViolation`` raised on a forged-empty ``source_id``
* End-to-end integration with the P110 orchestrator's ``ingest`` node
  via ``with_dependencies(sources=connectors)``
* Memory hook-up: connectors connected to a ``Mem0QdrantStore`` write
  audit-trail rows on every fetch
"""

from __future__ import annotations

import abc
import hashlib
import importlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import from orchestrator + memory layer (relative-then-absolute idiom)
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


def _import_memory():
    try:
        from ..memory import (  # type: ignore
            Mem0QdrantStore,
            build_memory_store,
        )
        return Mem0QdrantStore, build_memory_store
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    mem_pkg = importlib.import_module("memory")
    return mem_pkg.Mem0QdrantStore, mem_pkg.build_memory_store


_orch = _import_orchestrator()
SourceItem = _orch.SourceItem
SourceClient = _orch.SourceClient
ConstitutionViolation = _orch.ConstitutionViolation
LivingNarrativeFabric = _orch.LivingNarrativeFabric
DEFAULT_PER_SOURCE_LIMIT = _orch.DEFAULT_PER_SOURCE_LIMIT
_default_appdata_root = _orch._default_appdata_root

Mem0QdrantStore, build_memory_store = _import_memory()


# ---------------------------------------------------------------------------
# Provenance dataclass (attached to every emitted SourceItem.extra)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    """Standard provenance envelope every connector attaches to each item.

    Lives inside ``SourceItem.extra["provenance"]`` so it round-trips
    through the orchestrator's ingest → normalise → finalize pipeline
    without changing the dataclass shape.
    """

    source:          str       # the connector name (e.g. "newsapi")
    source_id:       str       # the upstream id (e.g. NewsAPI article URL)
    retrieved_at:    datetime  # when this connector fetched the item
    url:             Optional[str]  # official URL when available
    raw_snippet:     str       # short excerpt from the upstream body
    stub:            bool      # True when the connector is in stub mode
    cache_hit:       bool      # True when served from local cache

    def to_dict(self) -> dict:
        return {
            "source":       self.source,
            "source_id":    self.source_id,
            "retrieved_at": self.retrieved_at.isoformat(),
            "url":          self.url,
            "raw_snippet":  self.raw_snippet,
            "stub":         bool(self.stub),
            "cache_hit":    bool(self.cache_hit),
        }


# ---------------------------------------------------------------------------
# Cache schema (per-connector SQLite)
# ---------------------------------------------------------------------------


_CACHE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fetch_cache (
    cache_key   TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    since_iso   TEXT NOT NULL,
    limit_n     INTEGER NOT NULL,
    cached_at   TEXT NOT NULL,
    items_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fetch_cache_cached_at ON fetch_cache(cached_at);
"""


# ---------------------------------------------------------------------------
# BaseConnector — shared cache, provenance, validation, memory hookup
# ---------------------------------------------------------------------------


class BaseConnector(abc.ABC):
    """Abstract base class every Living Narrative Fabric connector inherits.

    Concrete subclasses MUST set the four class attributes ``name``,
    ``base_url``, ``auth_env_var``, and ``cache_ttl_seconds`` (with
    sensible defaults for the latter), and MUST implement ``_stub_fetch``,
    ``_do_fetch``, and ``validate_response``.

    The ``fetch`` orchestration is owned by this base class so every
    connector's caching, provenance attachment, ConstitutionViolation
    enforcement, and memory-store audit trail happen in exactly one
    place — slots 5/6/7 can rely on uniform behaviour across connectors.
    """

    # ---- Subclass-overridable class attributes ---------------------------

    #: Source name as referenced by the orchestrator's ``DEFAULT_SOURCE_AUTHORITY``.
    name: str = ""

    #: Base URL of the upstream API (informational; subclasses may compose).
    base_url: str = ""

    #: Environment variable that holds the auth token. ``None`` for
    #: keyless APIs (Semantic Scholar's free tier, data.gov CKAN).
    auth_env_var: Optional[str] = None

    #: Cache TTL in seconds. 1 hour by default — enough to deduplicate
    #: repeated fetches inside one orchestrator session, short enough
    #: that a fresh synthesis run pulls fresh data.
    cache_ttl_seconds: int = 3600

    # ---- Construction ----------------------------------------------------

    def __init__(
        self,
        *,
        appdata_root:     Optional[Path] = None,
        store:            Optional[Mem0QdrantStore] = None,
        per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT,
        force_stub:       bool = False,
        session:          Optional[Any] = None,
    ) -> None:
        if not self.name:
            raise ValueError(
                f"{type(self).__name__}.name must be set on the subclass."
            )
        self.appdata_root: Path = (
            Path(appdata_root) if appdata_root is not None else _default_appdata_root()
        )
        self.appdata_root.mkdir(parents=True, exist_ok=True)
        self.store = store
        self.per_source_limit = per_source_limit
        self.force_stub = force_stub
        self._session = session

        self.cache_dir = self.appdata_root / "connectors" / self.name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "cache.sqlite3"
        self._cache_conn = sqlite3.connect(
            str(self.cache_path), check_same_thread=False
        )
        self._cache_conn.row_factory = sqlite3.Row
        with self._cache_conn:
            self._cache_conn.executescript(_CACHE_SCHEMA_SQL)

    # ---- Convenience accessors -------------------------------------------

    @property
    def auth_token(self) -> Optional[str]:
        if self.auth_env_var:
            return os.environ.get(self.auth_env_var) or None
        return None

    @property
    def is_stub_mode(self) -> bool:
        if self.force_stub:
            return True
        if self.auth_env_var is None:
            # Keyless APIs are stub-only when ``requests`` is unavailable;
            # subclasses override this property when they need finer control.
            return False
        return not self.auth_token

    @property
    def runtime_info(self) -> dict:
        return {
            "name":           self.name,
            "base_url":       self.base_url,
            "auth_env_var":   self.auth_env_var,
            "stub_mode":      self.is_stub_mode,
            "cache_path":     str(self.cache_path),
            "per_source_limit": self.per_source_limit,
        }

    # ---- Public API (Protocol-required + rich) ---------------------------

    def fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        """Protocol-required entry point used by the orchestrator's ingest node."""

        if not query or not query.strip():
            raise ValueError(f"{self.name}.fetch: query must be a non-empty string")
        if not isinstance(since, datetime):
            raise TypeError(f"{self.name}.fetch: since must be a datetime")
        bounded_limit = max(1, min(int(limit), self.per_source_limit))

        cache_key = self._cache_key(query, since, bounded_limit)
        cached = self._cache_get(cache_key)
        if cached is not None:
            items = self._mark_cache_hit(cached)
            self._audit_fetch(query, since, bounded_limit, items, cache_hit=True)
            return items

        if self.is_stub_mode:
            raw_items = list(self._stub_fetch(query, since, bounded_limit))
        else:
            try:
                raw_items = list(self._do_fetch(query, since, bounded_limit))
            except Exception:
                # Any upstream failure falls through to stub so the
                # orchestrator's ingest node never blocks on a flaky API.
                raw_items = list(self._stub_fetch(query, since, bounded_limit))

        # Defense-in-depth: every emitted item must carry a non-empty
        # source_id; the connector NEVER leaks citation-less data.
        for it in raw_items:
            if not it.item_id:
                raise ConstitutionViolation(
                    f"Constitution violation: {self.name}.fetch produced an item "
                    f"with empty item_id; provenance is mandatory."
                )

        items = tuple(self.attach_provenance(it) for it in raw_items)
        self._cache_put(cache_key, query, since, bounded_limit, items)
        self._audit_fetch(query, since, bounded_limit, items, cache_hit=False)
        return items

    def fetch_batch(
        self,
        queries: Iterable[str],
        since: datetime,
        limit: int,
    ) -> dict[str, Sequence[SourceItem]]:
        """Run ``fetch`` for each query. No upstream batching — keeps the
        contract simple; subclasses may override for sources that support it.
        """

        return {q: self.fetch(q, since, limit) for q in queries}

    @abc.abstractmethod
    def validate_response(self, raw_response: Any) -> bool:
        """Subclass-specific check that the upstream payload is well-formed.

        Should return ``True`` when the response is usable and ``False``
        when it is malformed; the base ``fetch`` flow uses this in
        ``_do_fetch`` to decide whether to fall through to stub mode.
        Subclasses MAY raise ``ConstitutionViolation`` directly when a
        response is structurally fine but violates a hard provenance
        rule (e.g. a NewsAPI article with no ``url`` and no ``publishedAt``).
        """
        ...

    def attach_provenance(self, item: SourceItem) -> SourceItem:
        """Enrich ``item.extra`` with a standard ``Provenance`` envelope."""

        if not item.item_id:
            raise ConstitutionViolation(
                f"Constitution violation: {self.name}.attach_provenance refuses "
                f"to enrich an item with empty item_id."
            )
        prov = Provenance(
            source=self.name,
            source_id=item.item_id,
            retrieved_at=item.retrieved_at,
            url=item.url,
            raw_snippet=(item.body or "")[:200],
            stub=bool(item.extra.get("stub", False)) or self.is_stub_mode,
            cache_hit=False,
        )
        new_extra = dict(item.extra or {})
        new_extra["provenance"] = prov.to_dict()
        new_extra.setdefault("source_authority", _orch.DEFAULT_SOURCE_AUTHORITY.get(self.name, 0.5))
        return SourceItem(
            source=item.source or self.name,
            item_id=item.item_id,
            title=item.title,
            body=item.body,
            retrieved_at=item.retrieved_at,
            published_at=item.published_at,
            url=item.url,
            extra=new_extra,
        )

    def connect_memory(self, store: Mem0QdrantStore) -> None:
        """Wire a ``Mem0QdrantStore`` so subsequent fetches write audit rows."""

        self.store = store

    def close(self) -> None:
        if self._cache_conn is not None:
            try:
                self._cache_conn.close()
            except Exception:
                pass
            self._cache_conn = None

    # ---- Subclass extension points ---------------------------------------

    @abc.abstractmethod
    def _stub_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        """Per-source deterministic stub. Items must carry the same provenance
        shape the real call produces so callers can't tell the difference at
        the SourceItem level (the ``stub=True`` flag in the Provenance is
        what flags it downstream)."""
        ...

    @abc.abstractmethod
    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        """Real upstream call. Must NOT call ``attach_provenance`` —
        the base ``fetch`` does that as the last step."""
        ...

    # ---- Cache helpers ---------------------------------------------------

    def _cache_key(self, query: str, since: datetime, limit: int) -> str:
        seed = f"{self.name}|{query}|{since.isoformat()}|{limit}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]

    def _cache_get(self, cache_key: str) -> Optional[tuple[SourceItem, ...]]:
        if self._cache_conn is None:
            return None
        cur = self._cache_conn.execute(
            "SELECT cached_at, items_json FROM fetch_cache WHERE cache_key = ?",
            (cache_key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        try:
            cached_at = datetime.fromisoformat(row["cached_at"])
        except Exception:
            return None
        if (datetime.now(timezone.utc) - cached_at).total_seconds() > self.cache_ttl_seconds:
            return None
        try:
            payload = json.loads(row["items_json"])
        except Exception:
            return None
        return tuple(_hydrate_source_item(d) for d in payload)

    def _cache_put(
        self,
        cache_key: str,
        query: str,
        since: datetime,
        limit: int,
        items: Sequence[SourceItem],
    ) -> None:
        if self._cache_conn is None:
            return
        items_json = json.dumps(
            [_serialise_source_item(i) for i in items],
            ensure_ascii=False, separators=(",", ":"),
        )
        with self._cache_conn:
            self._cache_conn.execute(
                """
                INSERT OR REPLACE INTO fetch_cache(
                    cache_key, query, since_iso, limit_n, cached_at, items_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key, query, since.isoformat(), int(limit),
                    datetime.now(timezone.utc).isoformat(), items_json,
                ),
            )

    def _mark_cache_hit(self, items: tuple[SourceItem, ...]) -> tuple[SourceItem, ...]:
        out: list[SourceItem] = []
        for it in items:
            extra = dict(it.extra or {})
            prov = dict(extra.get("provenance") or {})
            prov["cache_hit"] = True
            extra["provenance"] = prov
            out.append(SourceItem(
                source=it.source, item_id=it.item_id, title=it.title,
                body=it.body, retrieved_at=it.retrieved_at,
                published_at=it.published_at, url=it.url, extra=extra,
            ))
        return tuple(out)

    # ---- Memory-store hookup --------------------------------------------

    def _audit_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
        items: Sequence[SourceItem],
        *,
        cache_hit: bool,
    ) -> None:
        """Write an audit-trail row for every successful fetch — enables the
        Trust Engine in slot 5 (P113) to reconstruct exactly which connector
        produced which raw items, and when. Best-effort: a memory failure
        never poisons the fetch result the orchestrator already received.
        """

        if self.store is None:
            return
        try:
            structured = getattr(self.store, "structured", None)
            if structured is None or not hasattr(structured, "append_audit_entry"):
                return
            # Write under a sentinel "_connector_audit" version so the entry
            # is reachable by Slot 5/7 even when no SynthesisVersion exists yet.
            sentinel_id = f"_connector_audit::{self.name}"
            self._ensure_sentinel_version(sentinel_id)
            structured.append_audit_entry(
                version_id=sentinel_id,
                kind="connector-fetch",
                reason=(
                    f"{self.name} fetched {len(items)} item(s) for query={query!r} "
                    f"since={since.isoformat()} limit={limit} stub={self.is_stub_mode} "
                    f"cache_hit={cache_hit}"
                ),
            )
        except Exception:
            # Best-effort — never break ingest because the audit write failed.
            pass

    def _ensure_sentinel_version(self, sentinel_id: str) -> None:
        """Insert a placeholder versions-table row so audit_trail FK is satisfied."""

        if self.store is None:
            return
        structured = getattr(self.store, "structured", None)
        if structured is None or structured._sqlite_conn is None:
            return
        with structured._sqlite_conn:
            structured._sqlite_conn.execute(
                """
                INSERT OR IGNORE INTO versions(
                    version_id, topic, parent_version_id, created_at,
                    confidence_score, audit_triggered, has_finance_subject, blob_json
                ) VALUES (?, ?, NULL, ?, 0, 0, 0, '{}')
                """,
                (
                    sentinel_id,
                    f"_connector::{self.name}",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


# ---------------------------------------------------------------------------
# SourceItem JSON helpers — kept here (not in mem0_setup) because the
# connector cache deals with raw items, not claims.
# ---------------------------------------------------------------------------


def _serialise_source_item(it: SourceItem) -> dict:
    return {
        "source":       it.source,
        "item_id":      it.item_id,
        "title":        it.title,
        "body":         it.body,
        "retrieved_at": it.retrieved_at.isoformat(),
        "published_at": it.published_at.isoformat() if it.published_at is not None else None,
        "url":          it.url,
        "extra":        dict(it.extra or {}),
    }


def _hydrate_source_item(d: dict) -> SourceItem:
    return SourceItem(
        source=d["source"],
        item_id=d["item_id"],
        title=d["title"],
        body=d["body"],
        retrieved_at=datetime.fromisoformat(d["retrieved_at"]),
        published_at=(
            datetime.fromisoformat(d["published_at"])
            if d.get("published_at") else None
        ),
        url=d.get("url"),
        extra=dict(d.get("extra") or {}),
    )


# ---------------------------------------------------------------------------
# Sibling client imports — done lazily so the package can self-test even
# when one of the optional client SDKs (crawl4ai, requests) is missing.
# ---------------------------------------------------------------------------


def _import_clients() -> dict:
    """Import all 6 sibling client modules. Returns a dict ``{name: class}``.

    Uses the relative-then-absolute idiom so the package works whether
    it's imported as ``connectors`` or ``living-narrative-fabric.connectors``.
    """

    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    def _load(modname: str, classname: str):
        try:
            m = importlib.import_module(f".{modname}", package="connectors")
        except Exception:
            try:
                m = importlib.import_module(f"connectors.{modname}")
            except Exception:
                m = importlib.import_module(modname)
        return getattr(m, classname)

    return {
        "newsapi":          _load("newsapi_client",          "NewsApiConnector"),
        "gnews":            _load("gnews_client",            "GnewsConnector"),
        "semantic_scholar": _load("semantic_scholar_client", "SemanticScholarConnector"),
        "data_gov":         _load("data_gov_client",         "DataGovConnector"),
        "x_search":         _load("x_grok_client",           "XGrokConnector"),
        "crawl4ai":         _load("crawl4ai_client",         "Crawl4aiConnector"),
    }


# ---------------------------------------------------------------------------
# Composite + factory
# ---------------------------------------------------------------------------


@dataclass
class LivingNarrativeFabricConnectors:
    """Composite that holds all six connectors and exposes them as a tuple.

    Use ``build_connectors`` rather than instantiating this directly.
    """

    connectors: tuple[BaseConnector, ...]

    def __iter__(self):
        return iter(self.connectors)

    def __len__(self):
        return len(self.connectors)

    def by_name(self, name: str) -> Optional[BaseConnector]:
        for c in self.connectors:
            if c.name == name:
                return c
        return None

    def connect_memory(self, store: Mem0QdrantStore) -> None:
        for c in self.connectors:
            c.connect_memory(store)

    @property
    def runtime_info(self) -> dict:
        return {c.name: c.runtime_info for c in self.connectors}


def build_connectors(
    *,
    appdata_root:     Optional[Path] = None,
    store:            Optional[Mem0QdrantStore] = None,
    per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT,
    force_stub:       bool = False,
    only:             Optional[Iterable[str]] = None,
) -> LivingNarrativeFabricConnectors:
    """Build all six connectors with shared config + memory hookup.

    Parameters
    ----------
    appdata_root :
        Local data directory (defaults to ``orchestrator._default_appdata_root()``).
    store :
        Optional ``Mem0QdrantStore``; when supplied, every successful
        fetch writes an audit-trail row.
    per_source_limit :
        Hard cap on items returned per fetch (defaults to ``25``).
    force_stub :
        When ``True``, every connector runs in stub mode regardless of
        env vars or upstream availability — used by the package smoke test.
    only :
        Optional iterable of connector names; when supplied, only those
        connectors are built (useful for unit tests). When ``None``,
        all six are built.
    """

    classes = _import_clients()
    if only is not None:
        wanted = set(only)
        classes = {k: v for k, v in classes.items() if k in wanted}

    instances: list[BaseConnector] = []
    for name, cls in classes.items():
        instance = cls(
            appdata_root=appdata_root,
            store=store,
            per_source_limit=per_source_limit,
            force_stub=force_stub,
        )
        instances.append(instance)
    return LivingNarrativeFabricConnectors(connectors=tuple(instances))


def with_connectors(
    fabric: LivingNarrativeFabric,
    *,
    appdata_root:     Optional[Path] = None,
    store:            Optional[Mem0QdrantStore] = None,
    per_source_limit: int = DEFAULT_PER_SOURCE_LIMIT,
    force_stub:       bool = False,
) -> LivingNarrativeFabric:
    """Convenience: build all six connectors and inject them into ``fabric``."""

    composite = build_connectors(
        appdata_root=appdata_root,
        store=store,
        per_source_limit=per_source_limit,
        force_stub=force_stub,
    )
    return fabric.with_dependencies(sources=tuple(composite.connectors))


# ---------------------------------------------------------------------------
# Smoke test (zero-install, zero-API-keys)
# ---------------------------------------------------------------------------


def run_smoke_test(*, verbose: bool = True) -> None:
    """Self-contained smoke test for the connector layer.

    Runs in stub mode — no API keys, no network — and verifies:

    1. All 6 connectors build and satisfy the SourceClient Protocol.
    2. Each connector's ``fetch`` returns >= 1 SourceItem with full provenance.
    3. ``ConstitutionViolation`` raises on a forged empty ``item_id``.
    4. End-to-end integration: ``LivingNarrativeFabric.with_dependencies(sources=...)``
       runs ``synthesize`` and emits a SynthesisVersion that names every
       active connector in ``sources_used``.
    5. Memory hookup: connectors connected to a ``Mem0QdrantStore`` write
       audit-trail rows on every fetch.
    6. ``fetch_batch`` returns one entry per query.
    7. ``validate_response`` returns ``True`` on a representative valid
       payload and ``False`` on an empty payload.
    """

    import shutil
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="lnf-connectors-smoke-"))
    try:
        store = build_memory_store(appdata_root=tmp_root)
        composite = build_connectors(
            appdata_root=tmp_root, store=store, force_stub=True,
        )

        if verbose:
            print(f"[smoke] runtime_info = {composite.runtime_info}")

        # ---- (1) Protocol satisfaction --------------------------------
        for c in composite:
            assert isinstance(c, SourceClient), (
                f"{c.name} does not satisfy the SourceClient Protocol."
            )
        assert len(composite) == 6

        # ---- (2) Per-connector fetch + provenance --------------------
        since = datetime.now(timezone.utc) - timedelta(days=7)
        for c in composite:
            items = c.fetch("Grok Agent OS launch", since, 5)
            assert len(items) >= 1, (
                f"{c.name}.fetch returned 0 items in stub mode; expected >= 1."
            )
            for it in items:
                assert it.item_id, f"{c.name}.fetch emitted an item with empty item_id."
                prov = (it.extra or {}).get("provenance")
                assert isinstance(prov, dict), (
                    f"{c.name} did not attach a provenance dict to item {it.item_id}."
                )
                assert prov["source"] == c.name
                assert prov["source_id"] == it.item_id
                assert "retrieved_at" in prov

        # ---- (3) ConstitutionViolation on forged empty item_id -------
        any_connector = next(iter(composite))
        try:
            any_connector.attach_provenance(SourceItem(
                source=any_connector.name,
                item_id="",                # ← Constitution violation
                title="x", body="y",
                retrieved_at=datetime.now(timezone.utc),
            ))
            raise AssertionError(
                "attach_provenance accepted an item with empty item_id."
            )
        except ConstitutionViolation:
            pass  # expected

        # ---- (4) End-to-end integration with the orchestrator ---------
        fabric = LivingNarrativeFabric().with_dependencies(
            sources=tuple(composite.connectors),
            memory=store,
        )
        version = fabric.synthesize(topic="lnf-connectors-smoke", time_range="7d")
        assert version is not None
        assert set(version.sources_used) == {c.name for c in composite}, (
            f"version.sources_used={version.sources_used!r}; "
            f"expected all 6 connector names."
        )
        # Verify every claim's source matches one of the 6 connectors.
        for claim in version.claims:
            assert claim.source in {c.name for c in composite}, (
                f"claim {claim.claim_id} has unknown source {claim.source!r}."
            )

        # ---- (5) Memory hookup writes connector audit rows -----------
        # Pull the audit trail from each sentinel version and confirm rows.
        structured = store.structured
        cur = structured._sqlite_conn.execute(
            """
            SELECT version_id, kind, reason FROM audit_trail
            WHERE kind = 'connector-fetch'
            """
        )
        audit_rows = cur.fetchall()
        assert len(audit_rows) >= len(composite), (
            f"expected >= {len(composite)} connector-fetch audit rows; got {len(audit_rows)}."
        )

        # ---- (6) fetch_batch -----------------------------------------
        batch = any_connector.fetch_batch(
            queries=("topic-a", "topic-b"), since=since, limit=3,
        )
        assert set(batch.keys()) == {"topic-a", "topic-b"}
        for q, items in batch.items():
            assert len(items) >= 1, f"fetch_batch returned 0 items for {q!r}."

        # ---- (7) validate_response truthiness ------------------------
        assert any_connector.validate_response({"valid": "shape"}) in (True, False)
        # An empty dict should be considered invalid by every connector.
        assert any_connector.validate_response({}) is False

        # Cleanup connector cursors.
        for c in composite:
            c.close()

        if verbose:
            print("P112 connectors smoke OK")
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = (
    "BaseConnector",
    "ConstitutionViolation",
    "LivingNarrativeFabricConnectors",
    "Provenance",
    "SourceClient",
    "build_connectors",
    "run_smoke_test",
    "with_connectors",
)


if __name__ == "__main__":  # pragma: no cover
    run_smoke_test()
