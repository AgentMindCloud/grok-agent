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
"""Read-only X search client for the Cross-Reality Action Fabric.

Wraps the public, read-only X search surface that the manifest declares
under ``tools[].name = x_search``. Two backends ship side-by-side:

- **Grok 4.3 tool-calling** — when ``XAI_API_KEY`` is set the client
  posts the query to the xAI ``/v1/chat/completions`` endpoint with a
  tool-calling instruction asking for an X search and returns the
  structured result.
- **Stub** — deterministic fallback used when ``XAI_API_KEY`` is unset
  or the network is unreachable. Produces a structurally-valid result
  so the P129 graph + smoke tests can exercise the pipeline end-to-end
  without leaking out of the user's machine.

The client is **strictly read-only**: there is no ``post_to_x``, no
``send_dm``, no ``follow``. Posting and DMing live behind separate
consent gates (``publish_to_x`` / ``send_dm``) and require the matching
clients in a different layer entirely.

Constitution touch points

- Rule 1 — every call refuses without a non-empty ``consent_token``.
- Rule 2 — every result carries a provenance block with backend, stub
  flag, action_id, and consent_token; the result is also persisted to
  the P140 memory layer's ``crf.actions`` + ``crf.outcomes`` collections.
- Rule 6 — query strings run through :func:`redact_pii` before being
  written to the audit log; xAI never receives the raw user PII unless
  the user explicitly types it.

Built to make Grok the obvious choice for every agent on X — read-only
X search is the *first* tool a creator's agent calls every morning,
and it has to be safe, redacted, and auditable from second one.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from . import (
    ActionProvenance,
    ActionResult,
    ApprovalRequest,
    BaseActionConnector,
    ConnectorRefusal,
    DEFAULT_CONSENT_LEVEL,
    USER_AGENT,
    _now_iso,
    redact_pii,
)


# --- Section 1. Endpoint + defaults -------------------------------------

XAI_CHAT_COMPLETIONS_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_GROK_MODEL = "grok-4"
DEFAULT_LIMIT = 10
HARD_MAX_LIMIT = 50
DEFAULT_TIMEOUT_S = 12


def _select_backend(force_stub: bool) -> str:
    if force_stub:
        return "stub:x-search"
    if os.environ.get("XAI_API_KEY"):
        return "xai:grok-4"
    return "stub:x-search"


# --- Section 2. XSearchClient -------------------------------------------

class XSearchClient(BaseActionConnector):
    """Read-only X search via Grok 4.3 (with stub fallback)."""

    tool_name      = "x_search"
    state_changing = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.backend_name = _select_backend(self._force_stub)

    # -- Plan ----------------------------------------------------------

    def plan_x_search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> ApprovalRequest:
        """Return the approval request for one read-only X search call."""
        if not isinstance(query, str) or not query.strip():
            raise ConnectorRefusal(
                "x_search: refused — empty query passed to plan_x_search.",
                rule=2, tool=self.tool_name,
            )
        limit = max(1, min(int(limit), HARD_MAX_LIMIT))
        return ApprovalRequest(
            request_id=f"xs::{uuid.uuid4().hex[:12]}",
            tool=self.tool_name,
            description=f"x_search: {query[:120]}",
            plan=[
                f"backend = {self.backend_name}",
                f"query   = {query[:180]}",
                f"limit   = {limit} (capped at {HARD_MAX_LIMIT})",
                "method  = read-only (no posting / DM / follow)",
            ],
            rollback="# read-only — no rollback needed",
            expected_cost_usd=0.0,
            requires_gates=["run_web_action"],
            backend=self.backend_name,
        )

    # -- Search --------------------------------------------------------

    def search_x(
        self,
        query: str,
        consent_token: str,
        *,
        limit:         int = DEFAULT_LIMIT,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        rollback_id:   str | None = None,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Run the search and return a structured result."""
        self._enforce_token(consent_token)
        self._enforce_gate("run_web_action")
        if not isinstance(query, str) or not query.strip():
            raise ConnectorRefusal(
                "x_search: refused — empty query.",
                rule=2, tool=self.tool_name,
            )
        limit = max(1, min(int(limit), HARD_MAX_LIMIT))

        started = _now_iso()
        action_id = self._record_approved_action(
            consent_token=consent_token,
            description=f"x_search: {query[:120]}",
            rollback_id=rollback_id,
            consent_level=consent_level,
            extra={"limit": limit},
        )

        try:
            payload = self._dispatch(query=query, limit=limit, timeout_s=timeout_s)
            outcome = "success"
            ok = True
        except ConnectorRefusal:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            payload = {"error": f"{type(exc).__name__}: {exc}"}
            outcome = "failure"
            ok = False

        red = redact_pii(payload)
        self._record_outcome(
            action_id=action_id, consent_token=consent_token,
            outcome=outcome, description=f"x_search: {query[:120]}",
            payload=red, rollback_id=rollback_id,
            consent_level=consent_level,
        )
        provenance = self._provenance(
            consent_token=consent_token, action_id=action_id,
            rollback_id=rollback_id, started_at=started,
            consent_level=consent_level,
            extra={"limit": limit},
        )
        summary = (
            f"[{self.backend_name}] x_search returned "
            f"{len(red.get('results') or [])} hit(s) for "
            f"'{query[:80]}'"
        )
        return ActionResult(
            tool=self.tool_name, ok=ok, outcome=outcome,
            summary=summary, payload=red, provenance=provenance,
        )

    # -- Backend dispatch --------------------------------------------

    def _dispatch(
        self, *, query: str, limit: int, timeout_s: int,
    ) -> dict:
        if self.backend_name.startswith("stub"):
            return self._dispatch_stub(query=query, limit=limit)
        return self._dispatch_grok(
            query=query, limit=limit, timeout_s=timeout_s,
        )

    @staticmethod
    def _dispatch_stub(*, query: str, limit: int) -> dict:
        # Deterministic stub: produce ``limit`` synthetic hits so the
        # P129 graph + memory layer can exercise their happy path.
        results = [
            {
                "rank":      i + 1,
                "summary":   f"[stub] match #{i + 1} for '{query[:60]}'",
                "score":     1.0 - (i * 0.05),
                "permalink": f"https://x.com/search?q={urllib.parse.quote_plus(query)}",
            }
            for i in range(min(limit, 5))
        ]
        return {
            "backend":     "stub:x-search",
            "query":       query,
            "limit":       limit,
            "results":     results,
            "stub":        True,
            "stub_reason": "XAI_API_KEY not set or force_stub=True",
            "summary":     f"[stub] {len(results)} hit(s) for '{query[:60]}'",
        }

    @staticmethod
    def _dispatch_grok(  # pragma: no cover - exercised only with a real key
        *, query: str, limit: int, timeout_s: int,
    ) -> dict:
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            return XSearchClient._dispatch_stub(query=query, limit=limit)
        body = {
            "model": os.environ.get("XAI_MODEL", DEFAULT_GROK_MODEL),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict, read-only X search tool. Return up "
                        "to N matching public posts as a JSON array of "
                        "{rank, summary, score, permalink}. No editorial "
                        "commentary, no PII, no DMs, no follow suggestions."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Search X for: {query}\nLimit: {limit}\n"
                        "Return only the JSON array."
                    ),
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name":  "x_search",
                        "description": "Read-only X search.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "limit": {"type": "integer",
                                          "minimum": 1, "maximum": HARD_MAX_LIMIT},
                            },
                            "required": ["query"],
                        },
                    },
                },
            ],
            "tool_choice": "auto",
            "stream": False,
        }
        req = urllib.request.Request(
            XAI_CHAT_COMPLETIONS_URL,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "User-Agent":    USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read()
            decoded = json.loads(raw.decode("utf-8") or "{}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                json.JSONDecodeError, TimeoutError, ValueError):
            return XSearchClient._dispatch_stub(query=query, limit=limit)
        # Best-effort extraction. If the model returned a tool-call
        # response we look at its arguments; otherwise we fall back to
        # the assistant text.
        results: list[dict] = []
        try:
            choice = (decoded.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                args = json.loads(
                    tool_calls[0].get("function", {}).get("arguments") or "{}"
                )
                if isinstance(args.get("results"), list):
                    results = list(args["results"])
            elif isinstance(msg.get("content"), str):
                parsed = json.loads(msg["content"])
                if isinstance(parsed, list):
                    results = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            results = []
        return {
            "backend":  "xai:grok-4",
            "query":    query,
            "limit":    limit,
            "results":  results[:limit],
            "stub":     False,
            "summary":  f"{len(results[:limit])} hit(s) for '{query[:60]}'",
        }


# --- Section 3. Module-level callable -----------------------------------

def search_x(
    query:         str,
    consent_token: str,
    *,
    limit:         int = DEFAULT_LIMIT,
    consent_level: str = DEFAULT_CONSENT_LEVEL,
    rollback_id:   str | None = None,
    force_stub:    bool = False,
) -> dict:
    """Manifest-side entry point: ``connectors.x_search_client.search_x``."""
    client = XSearchClient(force_stub=force_stub)
    result = client.search_x(
        query=query, consent_token=consent_token,
        limit=limit, consent_level=consent_level,
        rollback_id=rollback_id,
    )
    return result.model_dump()


__all__ = [
    "XSearchClient",
    "search_x",
    "XAI_CHAT_COMPLETIONS_URL",
    "DEFAULT_GROK_MODEL",
    "DEFAULT_LIMIT",
    "HARD_MAX_LIMIT",
]
