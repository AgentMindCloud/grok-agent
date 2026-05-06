# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Semantic Scholar connector (P112, Slot 4 / 3 of 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

Wraps the Semantic Scholar Graph API ``/paper/search`` endpoint. This is
the connector that gives the synthesis its highest-authority tier
(0.95 in ``DEFAULT_SOURCE_AUTHORITY``) — peer-reviewed academic claims
that the contradiction detector weights heavily when scoring authority
spread for the contradiction-severity formula.

* **Endpoint**:  ``https://api.semanticscholar.org/graph/v1/paper/search``
* **Auth**:      optional ``x-api-key`` header (the public free tier
  works keyless but is rate-limited to 100 req/5min).
* **Stub mode**: engages on any network failure or when
  ``SEMANTIC_SCHOLAR_KEY`` is unset AND the keyless rate limit was hit
  recently. The base class' ``is_stub_mode`` returns ``False`` for
  keyless connectors by default; we override here so stub kicks in when
  ``requests`` is missing.

Constitutional contract
=======================

Every emitted ``SourceItem`` carries a non-empty ``item_id`` (the
Semantic Scholar ``paperId`` — a stable hash, not a fragile URL). A
paper missing both ``paperId`` AND ``title`` raises
``ConstitutionViolation``.
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


class SemanticScholarConnector(BaseConnector):
    """Semantic Scholar Graph API ``/paper/search`` connector."""

    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1"
    auth_env_var = "SEMANTIC_SCHOLAR_KEY"  # optional — keyless tier works too
    cache_ttl_seconds = 86400  # 24h — academic papers don't move

    @property
    def is_stub_mode(self) -> bool:
        if self.force_stub:
            return True
        # Keyless tier is allowed; stub only when ``requests`` is missing.
        return requests is None

    # ---- BaseConnector overrides ----------------------------------------

    def validate_response(self, raw_response: Any) -> bool:
        if not isinstance(raw_response, dict):
            return False
        data = raw_response.get("data")
        return isinstance(data, list)

    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        if requests is None:
            return self._stub_fetch(query, since, limit)
        params = {
            "query":  query,
            "limit":  int(limit),
            "fields": "paperId,title,abstract,year,authors,url,publicationDate,venue",
        }
        headers = {}
        if self.auth_token:
            headers["x-api-key"] = self.auth_token
        try:
            r = requests.get(
                f"{self.base_url}/paper/search",
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

        cutoff_year = since.astimezone(timezone.utc).year
        out: list[SourceItem] = []
        for paper in payload.get("data") or []:
            if not isinstance(paper, dict):
                continue
            paper_id = (paper.get("paperId") or "").strip()
            title = (paper.get("title") or "").strip()
            if not paper_id and not title:
                raise ConstitutionViolation(
                    "semantic_scholar: paper with empty paperId AND title — "
                    "refusing to emit citation-less item."
                )
            year = paper.get("year")
            if isinstance(year, int) and year < cutoff_year - 5:
                # Older than 5y before our window — skip; the synthesis
                # is about *current* narrative, not deep history.
                continue
            try:
                pub_date_str = paper.get("publicationDate")
                published_dt = (
                    datetime.fromisoformat(pub_date_str)
                    if pub_date_str else None
                )
            except Exception:
                published_dt = None
            authors = paper.get("authors") or []
            author_names = [
                a.get("name") for a in authors
                if isinstance(a, dict) and a.get("name")
            ][:5]
            abstract = (paper.get("abstract") or "").strip()
            url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
            out.append(SourceItem(
                source=self.name,
                item_id=paper_id or f"ss-noid-{title[:32]}",
                title=title or "(untitled paper)",
                body=abstract[:1500] or "(no abstract published)",
                retrieved_at=datetime.now(timezone.utc),
                published_at=published_dt,
                url=url,
                extra={
                    "authors":     author_names,
                    "year":        year,
                    "venue":       paper.get("venue"),
                    "stub":        False,
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
                "empirical study of", "longitudinal analysis of",
                "controlled-experiment investigation of",
                "literature review on",
            ])
            finding = rng.choice([
                "supports the platform-effect hypothesis",
                "contradicts prior consensus",
                "yields mixed results",
                "shows statistically-significant effect",
            ])
            slug = f"ss-stub-{hashlib.sha256(seed).hexdigest()[:8]}-{i}"
            out.append(SourceItem(
                source=self.name,
                item_id=slug,
                title=f"[stub:semantic_scholar] {angle} {query} ({finding})",
                body=(
                    f"[stub source — install requests + optionally set "
                    f"SEMANTIC_SCHOLAR_KEY for real Semantic Scholar papers] "
                    f"Deterministic seeded academic placeholder. "
                    f"angle={angle!r}, finding={finding!r}, query={query!r}."
                ),
                retrieved_at=datetime.now(timezone.utc),
                published_at=since,
                url=f"https://example.invalid/semantic-scholar-stub/{slug}",
                extra={
                    "authors":  ["stub-author-a", "stub-author-b"],
                    "year":     since.year,
                    "venue":    "stub-venue",
                    "stub":     True,
                },
            ))
        return out


__all__ = ("SemanticScholarConnector",)
