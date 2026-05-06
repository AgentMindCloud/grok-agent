# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — GNews connector (P112, Slot 4 / 2 of 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

Wraps GNews's ``/api/v4/search`` endpoint. GNews is a parallel news
aggregator we use alongside NewsAPI so the contradiction detector has
two independent curated streams to compare — the consistent style from
P98–P102 (paradox surfacing in BOTH places) requires at least two
independent sources at the same authority tier.

* **Endpoint**:  ``https://gnews.io/api/v4/search``
* **Auth**:      ``?apikey=$GNEWS_KEY`` query parameter
* **Free tier**: 100 requests/day
* **Stub mode**: engages when ``GNEWS_KEY`` is unset; emits 3
  deterministic placeholder articles seeded by ``sha256(name|query|since)``.

Constitutional contract
=======================

Every emitted ``SourceItem`` carries a non-empty ``item_id`` (the GNews
article URL). Articles missing both ``url`` AND ``publishedAt`` raise
``ConstitutionViolation`` so a citation-less item never leaves the
connector — defense-in-depth alongside the same check in the base class.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Sequence

try:
    from . import BaseConnector  # type: ignore
except Exception:
    here = Path(__file__).resolve().parent
    if str(here.parent) not in sys.path:
        sys.path.insert(0, str(here.parent))
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    BaseConnector = importlib.import_module("connectors").BaseConnector

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


def _import_orchestrator():
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
SourceItem = _orch.SourceItem
ConstitutionViolation = _orch.ConstitutionViolation


class GnewsConnector(BaseConnector):
    """GNews ``/api/v4/search`` connector."""

    name = "gnews"
    base_url = "https://gnews.io/api/v4"
    auth_env_var = "GNEWS_KEY"
    cache_ttl_seconds = 1800

    # ---- BaseConnector overrides ----------------------------------------

    def validate_response(self, raw_response: Any) -> bool:
        if not isinstance(raw_response, dict):
            return False
        articles = raw_response.get("articles")
        return isinstance(articles, list)

    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        if requests is None:
            return self._stub_fetch(query, since, limit)
        params = {
            "q":      query,
            "from":   since.astimezone(timezone.utc).isoformat(),
            "max":    int(limit),
            "lang":   "en",
            "apikey": self.auth_token or "",
        }
        try:
            r = requests.get(
                f"{self.base_url}/search", params=params, timeout=15,
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
                raise ConstitutionViolation(
                    f"gnews: article with empty url AND publishedAt — "
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
                item_id=url or f"gnews-noid-{published or title}",
                title=title or "(untitled)",
                body=body or "(empty body)",
                retrieved_at=datetime.now(timezone.utc),
                published_at=published_dt,
                url=url or None,
                extra={
                    "gnews_source_name": source_obj.get("name"),
                    "gnews_source_url":  source_obj.get("url"),
                    "image":             art.get("image"),
                    "stub":              False,
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
                "global wire on", "regional perspective on",
                "longform analysis of", "weekly recap of",
            ])
            value = rng.choice([
                "platform momentum", "creator monetization",
                "regulatory pressure", "engagement metrics",
            ])
            slug = f"gnews-stub-{hashlib.sha256(seed).hexdigest()[:8]}-{i}"
            out.append(SourceItem(
                source=self.name,
                item_id=slug,
                title=f"[stub:gnews] {angle} {query}: {value}",
                body=(
                    f"[stub source — set GNEWS_KEY for real GNews articles] "
                    f"Deterministic seeded GNews placeholder. "
                    f"angle={angle!r}, value={value!r}, query={query!r}."
                ),
                retrieved_at=datetime.now(timezone.utc),
                published_at=since,
                url=f"https://example.invalid/gnews-stub/{slug}",
                extra={
                    "gnews_source_name": "stub-publisher",
                    "gnews_source_url":  "https://example.invalid",
                    "image":             None,
                    "stub":              True,
                },
            ))
        return out


__all__ = ("GnewsConnector",)
