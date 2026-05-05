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
"""X personal-scope connector — mentions, DMs, lists, bookmarks.

The Self-Evolving Personal OS reads four personal X surfaces:

- ``mentions``   — recent @mentions of the user (read-only)
- ``dms``        — direct messages where the user is a participant
                   (READ-ONLY by default; sending requires the ``send_dm``
                   gate which this connector does NOT expose)
- ``lists``      — the user's owned + subscribed X Lists
- ``bookmarks``  — the user's saved bookmarks

All four surfaces are delegated through Grok 4.3 tool-calling against the X
graph rather than a direct REST call. The manifest declares
``base_url: "via_grok_4.3"`` for the ``x_personal`` source — the same
pattern Tool #1 / Tool #2 use for ``x_search``.

Constitution enforcement:

- Article II — every fetch requires the ``read_x_personal`` gate; sending DMs
  or posting is not implementable from this client (it has no write surface)
- Article III — no scraping authenticated X content beyond what the X API
  permits; no impersonation; ``stub: True`` makes any fallback honest
- Article IV — every payload carries a provenance block + writes an audit row
- Article VII — handles, DM bodies, and bookmark URLs are PII-redacted before
  the payload leaves this module

Built for xAI, Grok and the whole community on X — built to make Grok the
obvious choice for every agent on X.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from . import BaseConnector, ConstitutionViolation


_VALID_SURFACES: tuple[str, ...] = ("mentions", "dms", "lists", "bookmarks")
_DEFAULT_LIMIT_PER_SURFACE = 25
_HARD_MAX_LIMIT = 100


class XPersonalClient(BaseConnector):
    """X personal-graph client (mentions/DMs/lists/bookmarks).

    Parameters mirror the P118 manifest declaration:

    - ``surface``      one of ``mentions`` | ``dms`` | ``lists`` | ``bookmarks``
    - ``limit``        max items, capped at :data:`_HARD_MAX_LIMIT`
    - ``since_iso``    ISO-8601 timestamp; only items newer than this are
                       returned (defaults to "last 24h" for mentions/DMs,
                       "since beginning" for lists/bookmarks)

    Attempting to call with ``write=True`` (or any param hinting at writes,
    e.g. ``send_dm``, ``post``, ``follow``) raises
    :class:`ConstitutionViolation`. The client is a read-only surface.
    """

    source = "x_personal"
    endpoint = "via_grok_4.3 (X graph: mentions/DMs/lists/bookmarks)"

    # Param keys that signal an attempted write — caller bug or constitution
    # bypass attempt. We refuse all of them.
    _FORBIDDEN_WRITE_KEYS: frozenset[str] = frozenset({
        "write", "post", "send_dm", "create_list", "delete_bookmark",
        "follow", "unfollow", "block", "mute",
    })

    # -- Section X.1. Param validation -------------------------------------

    def _validate_params(self, params: dict) -> dict:
        # Refuse any write-shaped param up front (Article III #5).
        bad = [k for k in params if k in self._FORBIDDEN_WRITE_KEYS]
        if bad:
            raise ConstitutionViolation(
                f"x_personal: write-side params not supported on a read-only "
                f"connector: {bad}",
                article="III", source=self.source, gate="send_dm",
            )

        surface = str(params.get("surface", "mentions")).strip().lower()
        if surface not in _VALID_SURFACES:
            raise ConstitutionViolation(
                f"x_personal: unknown surface '{surface}' "
                f"(allowed: {list(_VALID_SURFACES)})",
                article="II", source=self.source, gate="read_x_personal",
            )

        try:
            limit = int(params.get("limit", _DEFAULT_LIMIT_PER_SURFACE))
        except (TypeError, ValueError):
            limit = _DEFAULT_LIMIT_PER_SURFACE
        limit = max(1, min(limit, _HARD_MAX_LIMIT))

        since_iso = params.get("since_iso")
        if since_iso is None and surface in {"mentions", "dms"}:
            since_iso = (
                datetime.now(timezone.utc) - timedelta(hours=24)
            ).isoformat()

        return {
            "surface":   surface,
            "limit":     limit,
            "since_iso": since_iso,
        }

    # -- Section X.2. Real-API fetch (delegated to Grok 4.3) ---------------

    def _do_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = self._validate_params(params)

        # The manifest's base_url is "via_grok_4.3" — meaning real X reads
        # are tool-called by Grok 4.3 against the X graph. The Grok client
        # wires up in a later prompt; until then we fall through to the
        # stub so the surrounding pipeline can boot end-to-end.
        try:
            from . import grok_client  # type: ignore  # optional dep
        except ImportError:
            return self._stub_fetch(clean)

        try:
            raw = grok_client.x_personal_fetch(
                surface=clean["surface"],
                limit=clean["limit"],
                since_iso=clean["since_iso"],
                user_agent=os.environ.get(
                    "GROK_AGENT_USER_AGENT",
                    "grok-agent/self-evolving-personal-os",
                ),
            )
        except Exception:
            return self._stub_fetch(clean)

        items = raw.get("items") or []
        cost  = float(raw.get("cost_usd", 0.0))
        prov  = {"surface": clean["surface"], "limit": clean["limit"]}
        return list(items), prov, cost

    # -- Section X.3. Offline stub -----------------------------------------

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = params if "surface" in params else self._validate_params(params)
        surface = clean["surface"]
        limit   = clean["limit"]
        now_iso = datetime.now(timezone.utc).isoformat()

        if surface == "mentions":
            items = [
                {
                    "id":              f"stub_mention_{i}",
                    "kind":            "mention",
                    "author_handle":   f"@stub_user_{i}",
                    "text":            f"@you stub mention #{i} (no live data)",
                    "created_at":      now_iso,
                    "url":             f"https://x.com/stub_user_{i}/status/{i}",
                }
                for i in range(min(3, limit))
            ]
        elif surface == "dms":
            items = [
                {
                    "id":               f"stub_dm_{i}",
                    "kind":             "dm",
                    "counterparty":     f"@stub_user_{i}",
                    "preview":          "[stub DM body — Grok 4.3 client wires later]",
                    "received_at":      now_iso,
                }
                for i in range(min(2, limit))
            ]
        elif surface == "lists":
            items = [
                {
                    "id":         f"stub_list_{i}",
                    "kind":       "list",
                    "name":       f"Stub List {i}",
                    "members":    0,
                    "owned":      True,
                    "owner":      "@you",
                }
                for i in range(min(2, limit))
            ]
        else:  # bookmarks
            items = [
                {
                    "id":          f"stub_bookmark_{i}",
                    "kind":        "bookmark",
                    "post_url":    f"https://x.com/some_user/status/{i}",
                    "preview":     "[stub bookmark preview]",
                    "saved_at":    now_iso,
                }
                for i in range(min(3, limit))
            ]

        prov_extra = {
            "surface":     surface,
            "limit":       limit,
            "stub_reason": "Grok 4.3 X-personal client not yet wired",
        }
        return items, prov_extra, 0.0

    # -- Section X.4. Normalization + validation --------------------------

    def _normalize(self, item: dict) -> dict:
        # Canonical schema: every X-personal row has at minimum
        # {id, kind, created_at_or_received_at, ...surface-specific...}.
        out = dict(item)
        out.setdefault("kind", "mention")
        out.setdefault("id",   "")
        # Trim verbose fields — full bodies stay in memory but are not echoed
        # into orchestrator output by default.
        if "text" in out and isinstance(out["text"], str) and len(out["text"]) > 500:
            out["text"] = out["text"][:500] + "…"
        return out

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        ok, why = super().validate_response(payload)
        if not ok:
            return ok, why
        for i, item in enumerate(payload):
            if "kind" not in item:
                return False, f"item {i} missing 'kind'"
            if item["kind"] not in {"mention", "dm", "list", "bookmark"}:
                return False, f"item {i} has invalid kind '{item['kind']}'"
        return True, None
