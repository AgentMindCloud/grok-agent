# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — NewsAPI connector (P112, Slot 4 / 1 of 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

Wraps NewsAPI's ``/v2/everything`` endpoint. NewsAPI is a curated news
aggregator covering ~80,000 sources. The connector scopes itself to
articles published since the orchestrator's ``since`` window and bounds
the page size by the orchestrator's ``per_source_limit`` (default 25).

* **Endpoint**:  ``https://newsapi.org/v2/everything``
* **Auth**:      ``X-Api-Key: $NEWSAPI_KEY`` header
* **Free tier**: 100 requests/day, 24h delay
* **Stub mode**: engages when ``NEWSAPI_KEY`` is unset or any
  ``RequestException`` is raised; emits 3 deterministic placeholder
  articles seeded by ``sha256(name|query|since)`` so smoke tests are
  reproducible.

Constitutional contract
=======================

Every emitted ``SourceItem`` carries a non-empty ``item_id`` (the article
URL — NewsAPI's natural primary key). When the upstream payload is
missing both ``url`` AND ``publishedAt``, the connector raises
``ConstitutionViolation`` rather than guessing a citation — provenance
must be intact end-to-end.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Sequence

# Soft-import the connector base from this package, with relative-then-
# absolute fallback (mirrors graph.py:182-187 + memory layer).
try:
    from . import BaseConnector  # type: ignore
    from .__init__ import _hydrate_source_item  # noqa: F401  (re-exported below for typing)
except Exception:
    here = Path(__file__).resolve().parent
    if str(here.parent) not in sys.path:
        sys.path.insert(0, str(here.parent))
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    _connectors_pkg = importlib.import_module("connectors")
    BaseConnector = _connectors_pkg.BaseConnector

# Soft-import requests; stub-only when missing.
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover — soft import
    requests = None  # type: ignore


# Re-import SourceItem + ConstitutionViolation from the orchestrator.
def _import_orchestrator():
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
SourceItem = _orch.SourceItem
ConstitutionViolation = _orch.ConstitutionViolation


class NewsApiConnector(BaseConnector):
    """NewsAPI ``/v2/everything`` connector."""

    name = "newsapi"
    base_url = "https://newsapi.org/v2"
    auth_env_var = "NEWSAPI_KEY"
    cache_ttl_seconds = 1800  # 30 min — news cycles tighter than the 1h default

    # ---- BaseConnector overrides ----------------------------------------

    def validate_response(self, raw_response: Any) -> bool:
        if not isinstance(raw_response, dict):
            return False
        if raw_response.get("status") and raw_response.get("status") != "ok":
            return False
        articles = raw_response.get("articles")
        if not isinstance(articles, list):
            return False
        return True

    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        if requests is None:
            return self._stub_fetch(query, since, limit)
        params = {
            "q":         query,
            "from":      since.astimezone(timezone.utc).isoformat(),
            "pageSize":  int(limit),
            "sortBy":    "publishedAt",
            "language":  "en",
        }
        headers = {"X-Api-Key": self.auth_token or ""}
        try:
            r = requests.get(
                f"{self.base_url}/everything",
                params=params, headers=headers, timeout=15,
            )
        except Exception:
            return self._stub_fetch(query, since, limit)
        if r.status_code != 200:
            return self._stub_fetch(query, since, limit)
        try:
            payload = r.json()
        except Exception:
            return self._stub_fetch(query, since, limit)
        if not self.validate_response(payload):
            return self._stub_fetch(query, since, limit)

        out: list[SourceItem] = []
        for art in payload.get("articles") or []:
            if not isinstance(art, dict):
                continue
            url = art.get("url") or ""
            published = art.get("publishedAt")
            title = (art.get("title") or "").strip()
            if not url and not published:
                # Hard provenance gap — refuse to emit. The orchestrator's
                # _node_ingest catches this, logs, and continues.
                raise ConstitutionViolation(
                    f"newsapi: article with empty url AND publishedAt — "
                    f"refusing to emit citation-less item."
                )
            try:
                published_dt = (
                    datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if published else None
                )
            except Exception:
                published_dt = None
            description = (art.get("description") or "").strip()
            content_excerpt = (art.get("content") or "")[:1500]
            body = (description + ("\n\n" + content_excerpt if content_excerpt else "")).strip()
            source_obj = art.get("source") or {}
            out.append(SourceItem(
                source=self.name,
                item_id=url or f"newsapi-noid-{published or title}",
                title=title or "(untitled)",
                body=body or "(empty body)",
                retrieved_at=datetime.now(timezone.utc),
                published_at=published_dt,
                url=url or None,
                extra={
                    "newsapi_source_name": source_obj.get("name"),
                    "newsapi_source_id":   source_obj.get("id"),
                    "author":              art.get("author"),
                    "stub":                False,
                },
            ))
        return out

    def _stub_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        seed = f"{self.name}|{query}|{since.isoformat()}".encode("utf-8")
        rng = Random(seed)
        n = max(1, min(3, int(limit)))
        out: list[SourceItem] = []
        for i in range(n):
            angle = rng.choice([
                "in-depth feature on", "newswire summary of",
                "investigative piece on", "opinion column on",
            ])
            value = rng.choice([
                "platform momentum", "creator monetization", "trust signals",
                "regulatory pressure", "growth metrics",
            ])
            slug = f"newsapi-stub-{hashlib.sha256(seed).hexdigest()[:8]}-{i}"
            out.append(SourceItem(
                source=self.name,
                item_id=slug,
                title=f"[stub:newsapi] {angle} {query}: {value}",
                body=(
                    f"[stub source — set NEWSAPI_KEY for real NewsAPI articles] "
                    f"This is a deterministic seeded NewsAPI placeholder. "
                    f"angle={angle!r}, value={value!r}, query={query!r}."
                ),
                retrieved_at=datetime.now(timezone.utc),
                published_at=since,
                url=f"https://example.invalid/newsapi-stub/{slug}",
                extra={
                    "newsapi_source_name": "stub-publisher",
                    "newsapi_source_id":   "stub",
                    "author":              "stub-author",
                    "stub":                True,
                },
            ))
        return out


__all__ = ("NewsApiConnector",)
