# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Self-Evolving Personal OS — xAI/Grok client for personal X reads.

Built for xAI, X, Grok and the ecosystem community. ❤️

This module exposes the small slice of the xAI chat-completions API the
Personal OS needs to delegate personal-scoped X reads (mentions, DMs,
bookmarks, lists) to Grok via tool-calling. The companion P121
:class:`XPersonalClient` imports ``grok_client.x_personal_fetch`` lazily
so the surrounding pipeline still boots when this module's optional
``requests`` dependency is missing.

Mirrors the shape of the Living Narrative Fabric ``x_grok_client.py``
(see ``../../living-narrative-fabric/connectors/x_grok_client.py``) but
adapted to the personal-scoped surfaces declared in the SEPOS manifest:

* ``mentions``  — replies + @-mentions targeting the user
* ``dms``       — direct messages and conversation previews
* ``bookmarks`` — the user's saved posts
* ``lists``     — posts from lists the user owns or follows

* **Endpoint**: ``https://api.x.ai/v1/chat/completions``
* **Auth**:     ``Authorization: Bearer $XAI_API_KEY``
* **Default model**: ``grok-4`` (override via ``$env:XAI_MODEL``)

Stub fallback engages whenever ``XAI_API_KEY`` is unset, ``requests`` is
not installed, the network call fails, or the response shape is
unexpected. The fallback returns an empty list so the calling
``XPersonalClient`` can drop straight into its own deterministic stub
without raising.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

#: Default xAI model. Real xAI models include ``grok-4``, ``grok-4-fast``,
#: and ``grok-3``. Override at runtime via the ``XAI_MODEL`` env var.
DEFAULT_XAI_MODEL = "grok-4"
DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_TIMEOUT_S = 30

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover — optional dep
    requests = None  # type: ignore


__all__ = (
    "DEFAULT_XAI_MODEL",
    "DEFAULT_BASE_URL",
    "GrokClient",
    "x_personal_fetch",
)


class GrokClient:
    """Tiny xAI chat-completions client for the Personal OS.

    Reads ``XAI_API_KEY`` and ``XAI_MODEL`` from the environment at
    construction time so callers can simply do ``GrokClient()`` and get
    a fully-configured client. The ``api_key`` / ``model`` / ``base_url``
    constructor arguments override the env values (used by tests).

    Exposes a single method, :meth:`chat_completion`, that posts an
    OpenAI-compatible payload to ``$base_url/chat/completions`` and
    returns the parsed JSON response. The client never raises on a
    non-200 response — it returns the raw payload (or ``{"error": ...}``
    when ``requests`` is missing) so the caller can fall back gracefully.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("XAI_API_KEY", "")
        self.model = model or os.environ.get("XAI_MODEL") or DEFAULT_XAI_MODEL
        self.base_url = (base_url or os.environ.get("XAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_s = float(timeout_s if timeout_s is not None else DEFAULT_TIMEOUT_S)

    @property
    def is_configured(self) -> bool:
        """True iff the client can plausibly make a real API call."""
        return bool(self.api_key) and requests is not None

    def chat_completion(
        self,
        messages: Iterable[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        extra: dict | None = None,
    ) -> dict:
        """Post one chat-completions request, return the parsed payload.

        On any failure path (no api key, ``requests`` missing, network
        error, non-200 status, malformed JSON) returns
        ``{"error": <reason>, "stub": True}`` so callers can branch on
        an error key rather than catching exceptions.
        """
        if requests is None:
            return {"error": "requests-not-installed", "stub": True}
        if not self.api_key:
            return {"error": "no-api-key", "stub": True}

        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": float(temperature),
        }
        if tools:
            body["tools"] = list(tools)
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if max_tokens is not None:
            body["max_tokens"] = int(max_tokens)
        if extra:
            body.update(extra)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=body, timeout=self.timeout_s,
            )
        except Exception as exc:  # pragma: no cover — network failures
            return {"error": f"request-failed:{type(exc).__name__}", "stub": True}

        if r.status_code != 200:
            return {"error": f"http-{r.status_code}", "stub": True}
        try:
            return r.json()
        except Exception:
            return {"error": "invalid-json", "stub": True}

    @staticmethod
    def parse_tool_arguments(payload: dict) -> dict | None:
        """Extract structured arguments from a tool-call response.

        xAI's chat-completions API places tool-call results in
        ``message.tool_calls[*].function.arguments`` (a JSON string)
        when the model invokes a registered tool. Returns ``None`` when
        the payload contains no parseable tool call.
        """
        try:
            choices = payload.get("choices") or []
            if not choices:
                return None
            message = (choices[0] or {}).get("message") or {}
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                first_call = tool_calls[0] or {}
                fn = first_call.get("function") or {}
                args_raw = fn.get("arguments")
                if isinstance(args_raw, str) and args_raw.strip():
                    return json.loads(args_raw)
                if isinstance(args_raw, dict):
                    return args_raw
            content = message.get("content") or ""
            if isinstance(content, str) and content.strip():
                return json.loads(content)
        except Exception:
            return None
        return None


# ---------------------------------------------------------------------------
# Convenience function used by ``connectors/x_personal_client.py``
# ---------------------------------------------------------------------------


def x_personal_fetch(
    *,
    surface: str,
    limit: int,
    since_iso: str,
    user_agent: str = "grok-agent/self-evolving-personal-os",
    client: GrokClient | None = None,
) -> dict:
    """Fetch personal X items (``mentions`` / ``dms`` / ``bookmarks`` / ``lists``).

    Returns ``{"items": [...], "cost_usd": float, "stub": bool, ...}``.
    The caller (``XPersonalClient._do_fetch``) treats an empty ``items``
    list as a soft failure and drops to its own offline stub.
    """
    gc = client if client is not None else GrokClient()
    if not gc.is_configured:
        return {"items": [], "cost_usd": 0.0, "stub": True, "reason": "not-configured"}

    system_prompt = (
        "You are a personal X assistant. The user has authorised reads of "
        f"their own '{surface}' surface. Return up to N items as one JSON "
        "object with key 'items' = list of records. Each record must include: "
        "id, kind, author_handle (or counterparty for DMs), text (verbatim), "
        "created_at (ISO 8601), and url. No prose."
    )
    user_prompt = (
        f"Surface: {surface}\n"
        f"Since (UTC): {since_iso}\n"
        f"Max items: {int(limit)}\n"
        f"User-Agent: {user_agent}"
    )
    tool_schema = {
        "type": "function",
        "function": {
            "name": f"x_personal_{surface}",
            "description": (
                f"Fetch up to N items from the user's authorised "
                f"{surface} surface."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
                "required": ["items"],
            },
        },
    }

    payload = gc.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        tools=[tool_schema],
        tool_choice="auto",
        temperature=0.2,
    )
    if payload.get("error"):
        return {"items": [], "cost_usd": 0.0, "stub": True, "reason": payload["error"]}

    parsed = GrokClient.parse_tool_arguments(payload) or {}
    items = parsed.get("items") or []
    cost_usd = 0.0
    usage = (payload.get("usage") or {}) if isinstance(payload, dict) else {}
    if isinstance(usage, dict):
        # Best-effort cost estimate when xAI returns token usage. Keeps the
        # number out of the stub branch above where no real call happened.
        cost_usd = float(usage.get("total_cost_usd") or 0.0)

    return {
        "items":     list(items),
        "cost_usd":  cost_usd,
        "stub":      False,
        "model":     gc.model,
        "surface":   surface,
        "limit":     int(limit),
        "since_iso": since_iso,
    }
