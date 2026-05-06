# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — data.gov connector (P112, Slot 4 / 4 of 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

Wraps the data.gov CKAN catalogue search at
``https://catalog.data.gov/api/3/action/package_search``. data.gov is
the official US-government primary-data source we use for
high-authority claims (0.90 in ``DEFAULT_SOURCE_AUTHORITY``) — second
only to Semantic Scholar. The CKAN endpoint is keyless; the optional
``DATA_GOV_KEY`` is used only when the orchestrator's caller routes
specific dataset reads through ``api.data.gov`` proxied APIs.

* **Endpoint**:  ``https://catalog.data.gov/api/3/action/package_search``
* **Auth**:      keyless on the CKAN search; ``DATA_GOV_KEY`` optional
  for proxied-API reads.
* **Stub mode**: engages when ``requests`` is missing or any network
  failure occurs.

Constitutional contract
=======================

Every emitted ``SourceItem`` carries a non-empty ``item_id`` (the CKAN
``id`` UUID — stable). A package missing both ``id`` AND ``name`` raises
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


class DataGovConnector(BaseConnector):
    """data.gov CKAN package_search connector."""

    name = "data_gov"
    base_url = "https://catalog.data.gov/api/3/action"
    auth_env_var = "DATA_GOV_KEY"  # optional
    cache_ttl_seconds = 21600  # 6h — government datasets update slowly

    @property
    def is_stub_mode(self) -> bool:
        if self.force_stub:
            return True
        # CKAN is keyless; stub only when requests is missing.
        return requests is None

    # ---- BaseConnector overrides ----------------------------------------

    def validate_response(self, raw_response: Any) -> bool:
        if not isinstance(raw_response, dict):
            return False
        if not raw_response.get("success"):
            return False
        result = raw_response.get("result")
        if not isinstance(result, dict):
            return False
        return isinstance(result.get("results"), list)

    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        if requests is None:
            return self._stub_fetch(query, since, limit)
        params = {"q": query, "rows": int(limit)}
        headers = {}
        if self.auth_token:
            # data.gov proxied APIs accept an api_key query param OR
            # X-Api-Key header; CKAN itself ignores both. We forward
            # the header so future proxied-route subclasses can lean on it.
            headers["X-Api-Key"] = self.auth_token
        try:
            r = requests.get(
                f"{self.base_url}/package_search",
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
        for pkg in (payload.get("result") or {}).get("results") or []:
            if not isinstance(pkg, dict):
                continue
            pkg_id = (pkg.get("id") or "").strip()
            pkg_name = (pkg.get("name") or "").strip()
            if not pkg_id and not pkg_name:
                raise ConstitutionViolation(
                    "data_gov: package with empty id AND name — refusing "
                    "to emit citation-less item."
                )
            title = (pkg.get("title") or pkg_name or "(untitled dataset)").strip()
            notes = (pkg.get("notes") or "").strip()
            modified = pkg.get("metadata_modified")
            try:
                modified_dt = (
                    datetime.fromisoformat(modified.replace("Z", "+00:00"))
                    if modified else None
                )
            except Exception:
                modified_dt = None
            organization = (pkg.get("organization") or {}).get("title")
            url = f"https://catalog.data.gov/dataset/{pkg_name}" if pkg_name else None
            out.append(SourceItem(
                source=self.name,
                item_id=pkg_id or f"datagov-noid-{pkg_name}",
                title=title,
                body=notes[:1500] or "(no description)",
                retrieved_at=datetime.now(timezone.utc),
                published_at=modified_dt,
                url=url,
                extra={
                    "organization":   organization,
                    "license":        pkg.get("license_title"),
                    "num_resources":  pkg.get("num_resources"),
                    "stub":           False,
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
            agency = rng.choice([
                "Bureau of Economic Analysis", "U.S. Census Bureau",
                "Department of Commerce", "Federal Trade Commission",
            ])
            kind = rng.choice([
                "longitudinal dataset on", "annual survey of",
                "administrative-records release on", "monthly indicator of",
            ])
            slug = f"datagov-stub-{hashlib.sha256(seed).hexdigest()[:8]}-{i}"
            out.append(SourceItem(
                source=self.name,
                item_id=slug,
                title=f"[stub:data_gov] {agency} — {kind} {query}",
                body=(
                    f"[stub source — install requests for real CKAN search at "
                    f"catalog.data.gov] Deterministic seeded government "
                    f"dataset placeholder. agency={agency!r}, kind={kind!r}, "
                    f"query={query!r}."
                ),
                retrieved_at=datetime.now(timezone.utc),
                published_at=since,
                url=f"https://example.invalid/data-gov-stub/{slug}",
                extra={
                    "organization":  agency,
                    "license":       "us-pd",
                    "num_resources": rng.randint(1, 20),
                    "stub":          True,
                },
            ))
        return out


__all__ = ("DataGovConnector",)
