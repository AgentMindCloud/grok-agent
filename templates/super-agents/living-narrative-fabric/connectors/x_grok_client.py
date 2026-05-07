# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — X search via Grok 4.3 (P112, Slot 4 / 5 of 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

Wraps xAI's Grok 4.3 API to perform X (Twitter) search. The orchestrator
references this connector as ``x_search`` (matching
``DEFAULT_SOURCE_AUTHORITY``); the Python class name is ``XGrokConnector``
to make the binding to xAI's hosted Grok runtime explicit.

Grok 4.3 exposes X-search via tool-calling on the ``/v1/chat/completions``
endpoint with a ``tools=[{type: "x_search"}]`` registration. The
connector composes a search prompt scoped to the orchestrator's topic +
``since`` window, parses the model's structured tool response into
``SourceItem``s with stable ``item_id``s (the X status URL or tweet id).

* **Endpoint**:  ``https://api.x.ai/v1/chat/completions``
* **Auth**:      ``Authorization: Bearer $XAI_API_KEY``
* **Stub mode**: engages when ``XAI_API_KEY`` is unset or any
  ``RequestException`` is raised; emits 3 deterministic seeded
  X-style placeholder posts.

Constitutional contract
=======================

Every emitted ``SourceItem`` carries a non-empty ``item_id`` (the
X status URL — e.g. ``https://x.com/<handle>/status/<tweet_id>``).
A tool-response item missing both ``url`` AND ``tweet_id`` raises
``ConstitutionViolation``.

Article V.1 disclaimer hook
===========================

Items whose ``body`` contains a ``$XAI``-style cashtag get
``extra["finance_disclaimer_required"] = True`` so the orchestrator's
``_node_finalize`` can flip ``has_finance_subject=True`` and the
renderer can attach the "Not financial advice" banner. This mirrors
the Article V.1 contract enforced across the X Money tools (P19–P42).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Sequence

#: Default xAI model used for the X-search tool call. Real xAI models include
#: ``grok-4``, ``grok-4-fast``, and ``grok-3``. Override at runtime via the
#: ``XAI_MODEL`` environment variable.
DEFAULT_XAI_MODEL = "grok-4"

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


_CASHTAG_RE = re.compile(r"\$[A-Z]{1,7}\b")


class XGrokConnector(BaseConnector):
    """X (Twitter) search via Grok 4.3."""

    name = "x_search"
    base_url = "https://api.x.ai/v1"
    auth_env_var = "XAI_API_KEY"
    cache_ttl_seconds = 600  # 10 min — X moves fast

    # ---- BaseConnector overrides ----------------------------------------

    def validate_response(self, raw_response: Any) -> bool:
        if not isinstance(raw_response, dict):
            return False
        choices = raw_response.get("choices")
        return isinstance(choices, list) and len(choices) >= 1

    def _do_fetch(
        self,
        query: str,
        since: datetime,
        limit: int,
    ) -> Sequence[SourceItem]:
        if requests is None:
            return self._stub_fetch(query, since, limit)
        model = os.environ.get("XAI_MODEL") or DEFAULT_XAI_MODEL
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an X-search agent. Return up to N posts on the "
                        "user's topic, scoped to the time window provided. Each "
                        "post must include: url, author_handle, posted_at (ISO8601), "
                        "text (verbatim), and tweet_id. Output ONE JSON object with "
                        "key 'posts' = list of those records. No prose."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Topic: {query}\n"
                        f"Since (UTC): {since.astimezone(timezone.utc).isoformat()}\n"
                        f"Max posts: {int(limit)}"
                    ),
                },
            ],
            "tools": [{"type": "x_search"}],
            "tool_choice": "auto",
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self.auth_token or ''}",
            "Content-Type":  "application/json",
        }
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=body, timeout=30,
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

        # Extract the model's posts array. xAI's chat-completions API places
        # tool-call results in ``message.tool_calls[*].function.arguments``
        # (a JSON string) when the model invokes a registered tool. The
        # ``message.content`` field is typically ``None`` in that case. We
        # check tool_calls first and fall back to free-form content only
        # when tool_calls is absent or empty.
        try:
            message = payload["choices"][0]["message"] or {}
            tool_calls = message.get("tool_calls") or []
            parsed: dict | None = None
            if tool_calls:
                first_call = tool_calls[0] or {}
                fn = first_call.get("function") or {}
                args_raw = fn.get("arguments") or ""
                if isinstance(args_raw, str) and args_raw.strip():
                    parsed = json.loads(args_raw)
                elif isinstance(args_raw, dict):
                    parsed = args_raw
            if parsed is None:
                content = message.get("content") or ""
                if content.strip():
                    parsed = json.loads(content)
            posts = (parsed or {}).get("posts") or []
        except Exception:
            return self._stub_fetch(query, since, limit)

        out: list[SourceItem] = []
        for post in posts[: int(limit)]:
            if not isinstance(post, dict):
                continue
            url = (post.get("url") or "").strip()
            tweet_id = (post.get("tweet_id") or "").strip()
            if not url and not tweet_id:
                raise ConstitutionViolation(
                    "x_search: post with empty url AND tweet_id — refusing "
                    "to emit citation-less item."
                )
            text = (post.get("text") or "").strip()
            handle = (post.get("author_handle") or "").strip()
            posted_at = post.get("posted_at")
            try:
                published_dt = (
                    datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                    if posted_at else None
                )
            except Exception:
                published_dt = None
            cashtags = _CASHTAG_RE.findall(text or "")
            out.append(SourceItem(
                source=self.name,
                item_id=url or f"x-tweet-{tweet_id}",
                title=f"@{handle}: {(text or '')[:80]}" if handle else (text or "")[:80],
                body=text or "(empty post)",
                retrieved_at=datetime.now(timezone.utc),
                published_at=published_dt,
                url=url or (f"https://x.com/{handle}/status/{tweet_id}" if handle and tweet_id else None),
                extra={
                    "author_handle": handle,
                    "tweet_id":      tweet_id,
                    "cashtags":      cashtags,
                    "finance_disclaimer_required": bool(cashtags),
                    "stub":          False,
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
        finance_query = bool(_CASHTAG_RE.search(query))
        out: list[SourceItem] = []
        for i in range(n):
            handle = rng.choice([
                "@JanSol0s", "@grok", "@xai", "@elonmusk_stub",
                "@creator_stub", "@dev_stub",
            ])
            stance = rng.choice([
                "is bullish on", "is sceptical of", "neutrally observes",
            ])
            outcome = rng.choice([
                "rapid adoption", "slow uptake", "uncertain reception",
            ])
            slug = f"x-stub-{hashlib.sha256(seed).hexdigest()[:8]}-{i}"
            text = f"{handle} {stance} {query}: {outcome}."
            cashtags = _CASHTAG_RE.findall(text)
            out.append(SourceItem(
                source=self.name,
                item_id=f"https://x.com/{handle.lstrip('@')}/status/{slug}",
                title=f"[stub:x_search] {handle} {stance} {query}",
                body=(
                    f"[stub source — set XAI_API_KEY for real X search via "
                    f"Grok 4.3] {text}"
                ),
                retrieved_at=datetime.now(timezone.utc),
                published_at=since,
                url=f"https://x.com/{handle.lstrip('@')}/status/{slug}",
                extra={
                    "author_handle":               handle,
                    "tweet_id":                    slug,
                    "cashtags":                    cashtags,
                    "finance_disclaimer_required": bool(cashtags) or finance_query,
                    "stub":                        True,
                },
            ))
        return out


__all__ = ("XGrokConnector",)
