# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Crawl4AI connector (P112, Slot 4 / 6 of 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

Wraps the local Crawl4AI Python package (``pip install crawl4ai``) for
open-web scraping. This is the lowest-authority tier (0.45 in
``DEFAULT_SOURCE_AUTHORITY``) but covers the long tail of public web
content that the four curated sources don't index — niche blogs,
project changelogs, GitHub READMEs, and marketing pages.

* **Library**:    ``crawl4ai`` (``AsyncWebCrawler.arun(url=...)``)
* **Auth**:       none (this is a local library, not a remote API)
* **Auth env**:   ``CRAWL4AI_SEED_URLS`` — optional, comma-separated
  list of seed URLs to crawl when the orchestrator passes a topic
  query (the orchestrator does NOT pre-resolve URLs; the connector
  composes a small candidate set from the query + the seed URLs).
* **Stub mode**:  engages when ``crawl4ai`` is not installed; emits
  3 deterministic placeholder pages.

Constitutional contract
=======================

Every emitted ``SourceItem`` carries a non-empty ``item_id`` (the
crawled URL — the natural primary key for web pages). A page result
missing the URL raises ``ConstitutionViolation`` immediately — there's
no other way to cite a web scrape.

Async-to-sync bridge
====================

``AsyncWebCrawler`` is async-only; the orchestrator's ``_node_ingest``
calls ``connector.fetch`` synchronously. This connector wraps the
async call with ``asyncio.run`` per fetch — acceptable for the current
once-per-synthesis cadence. P115 (Streamlit UI) may want a long-running
event loop; that's a Slot-7 concern, not Slot-4.
"""

from __future__ import annotations

import asyncio
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

# Soft-import the Crawl4AI library; stub-only when missing.
try:
    from crawl4ai import AsyncWebCrawler  # type: ignore
except Exception:  # pragma: no cover
    AsyncWebCrawler = None  # type: ignore


def _import_orchestrator():
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


_orch = _import_orchestrator()
SourceItem = _orch.SourceItem
ConstitutionViolation = _orch.ConstitutionViolation


class Crawl4aiConnector(BaseConnector):
    """Crawl4AI open-web scraper connector."""

    name = "crawl4ai"
    base_url = "(local crawl4ai)"
    auth_env_var = "CRAWL4AI_SEED_URLS"  # optional comma-separated seed URLs
    cache_ttl_seconds = 7200  # 2h — open web changes faster than gov data

    @property
    def is_stub_mode(self) -> bool:
        if self.force_stub:
            return True
        # Crawl4AI is keyless — stub only when the library isn't installed.
        return AsyncWebCrawler is None

    # ---- BaseConnector overrides ----------------------------------------

    def validate_response(self, raw_response: Any) -> bool:
        """Crawl4AI returns one ``CrawlResult`` per URL. Validity = the
        object exposes ``url``, ``markdown`` (or ``html``), and at least
        one of them is non-empty. We accept either a single result or
        a list of results (ours is always a list)."""

        if raw_response is None:
            return False
        results = raw_response if isinstance(raw_response, list) else [raw_response]
        for r in results:
            url = getattr(r, "url", None) or (r.get("url") if isinstance(r, dict) else None)
            md = getattr(r, "markdown", None) or (r.get("markdown") if isinstance(r, dict) else None)
            html = getattr(r, "html", None) or (r.get("html") if isinstance(r, dict) else None)
            if url and (md or html):
                return True
        return False

    def _seed_urls(self) -> list[str]:
        raw = self.auth_token or ""
        urls = [u.strip() for u in raw.split(",") if u.strip()]
        return urls

    async def _crawl(self, urls: list[str]) -> list[Any]:
        if AsyncWebCrawler is None:
            return []
        results: list[Any] = []
        try:
            async with AsyncWebCrawler() as crawler:
                for u in urls:
                    try:
                        r = await crawler.arun(url=u)
                        results.append(r)
                    except Exception:
                        continue
        except Exception:
            return []
        return results

    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        if AsyncWebCrawler is None:
            return self._stub_fetch(query, since, limit)
        urls = self._seed_urls()
        if not urls:
            # No seed URLs configured — fall through to stub. Slot 7
            # (Streamlit UI) will let the user enter URLs interactively.
            return self._stub_fetch(query, since, limit)
        try:
            results = asyncio.run(self._crawl(urls[: int(limit)]))
        except RuntimeError:
            # Already-running event loop (e.g. Streamlit) — fall back
            # to stub rather than block. Slot 7 is responsible for
            # awaiting the async path directly.
            return self._stub_fetch(query, since, limit)
        if not self.validate_response(results):
            return self._stub_fetch(query, since, limit)

        out: list[SourceItem] = []
        for r in results:
            url = getattr(r, "url", None) or (r.get("url") if isinstance(r, dict) else None)
            if not url:
                raise ConstitutionViolation(
                    "crawl4ai: scraped result with empty URL — refusing "
                    "to emit citation-less item."
                )
            md = getattr(r, "markdown", None) or (r.get("markdown") if isinstance(r, dict) else None) or ""
            title_attr = getattr(r, "metadata", None) or (r.get("metadata") if isinstance(r, dict) else None) or {}
            title = (title_attr.get("title") if isinstance(title_attr, dict) else None) or url
            body = str(md)[:1500] if md else "(empty crawl result)"
            out.append(SourceItem(
                source=self.name,
                item_id=url,
                title=title,
                body=body,
                retrieved_at=datetime.now(timezone.utc),
                published_at=None,
                url=url,
                extra={
                    "content_type": "web-page",
                    "stub":         False,
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
            kind = rng.choice([
                "blog post", "project README", "marketing page",
                "changelog entry",
            ])
            angle = rng.choice([
                "praises", "critiques", "explains", "compares",
            ])
            slug = f"crawl4ai-stub-{hashlib.sha256(seed).hexdigest()[:8]}-{i}"
            stub_url = f"https://example.invalid/crawl4ai-stub/{slug}"
            out.append(SourceItem(
                source=self.name,
                item_id=stub_url,
                title=f"[stub:crawl4ai] {kind} {angle} {query}",
                body=(
                    f"[stub source — install crawl4ai and set CRAWL4AI_SEED_URLS "
                    f"for real open-web scrapes] Deterministic seeded web-page "
                    f"placeholder. kind={kind!r}, angle={angle!r}, query={query!r}."
                ),
                retrieved_at=datetime.now(timezone.utc),
                published_at=since,
                url=stub_url,
                extra={
                    "content_type": "stub-web-page",
                    "stub":         True,
                },
            ))
        return out


__all__ = ("Crawl4aiConnector",)
