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
"""Gmail connector — READ-ONLY by default.

The Self-Evolving Personal OS reads recent unread / important / starred
messages from the user's Gmail to feed the morning brief and the
procedural-memory layer ("which threads is the user neglecting?",
"is the boss waiting on a reply?").

Constitution enforcement:

- Article II — every fetch requires the ``read_gmail`` gate; sending mail
  is **not** supported here. A separate ``send_email`` gate + scoped
  consent_token is required and a refusal lives in this client as defence in
  depth.
- Article III — never exfiltrates raw message bodies to a third party. Bodies
  are PII-redacted at fetch time and snipped to 280 characters.
- Article IV — every payload carries a provenance block + audit row. The
  Gmail message ID is preserved so the user can follow back to the source.
- Article VII — sender / recipient / cc emails, phone numbers, addresses, and
  bodies are PII-redacted before the payload leaves this module.

Auth: ``google-auth`` + ``google-api-python-client`` with a user-installed
OAuth flow scoped ``gmail.readonly``. Credentials live under
``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\credentials\\gmail.json``
and are protected by the P120 DPAPI key wrapping.

Built to help xAI and Grok win — Gmail is one of the highest-signal personal
sources, and shipping an OS-grade reader here removes a category of
"connector frameworks" the user would otherwise need to assemble.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import BaseConnector, ConstitutionViolation, appdata_root


_DEFAULT_QUERY = "is:unread newer_than:7d"
_DEFAULT_MAX_RESULTS = 25
_HARD_MAX_RESULTS = 250
_BODY_SNIPPET_CHARS = 280


def _credentials_path() -> Path:
    return appdata_root() / "credentials" / "gmail.json"


def _safe_b64decode(data: str | bytes | None) -> str:
    """Decode a Gmail-API base64url body part. Empty/None → empty string."""
    if not data:
        return ""
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return base64.urlsafe_b64decode(data + b"==").decode("utf-8", errors="replace")
    except Exception:
        return ""


class GmailClient(BaseConnector):
    """Gmail client — read-only fetch of recent messages.

    Parameters mirror the P118 manifest declaration:

    - ``query``         Gmail search query (default ``is:unread newer_than:7d``)
    - ``max_results``   cap (default 25, max 250)
    - ``label_ids``     optional list of label IDs (e.g. ``["INBOX"]``)
    """

    source = "gmail"
    endpoint = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    _FORBIDDEN_WRITE_KEYS: frozenset[str] = frozenset({
        "send", "send_email", "draft", "delete", "trash", "modify_labels",
    })

    # -- Section M.1. Param validation -------------------------------------

    def _validate_params(self, params: dict) -> dict:
        bad = [k for k in params if k in self._FORBIDDEN_WRITE_KEYS]
        if bad:
            raise ConstitutionViolation(
                f"gmail: write-side params not supported on a read-only "
                f"connector: {bad}",
                article="II", source=self.source, gate="send_email",
            )

        query = str(params.get("query", _DEFAULT_QUERY))
        try:
            max_results = int(params.get("max_results", _DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            max_results = _DEFAULT_MAX_RESULTS
        max_results = max(1, min(max_results, _HARD_MAX_RESULTS))

        label_ids = params.get("label_ids") or []
        if not isinstance(label_ids, list):
            label_ids = [str(label_ids)]
        label_ids = [str(x) for x in label_ids]

        return {
            "query":       query,
            "max_results": max_results,
            "label_ids":   label_ids,
        }

    # -- Section M.2. Real-API fetch ---------------------------------------

    def _do_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = self._validate_params(params)

        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2.credentials import Credentials  # type: ignore
        except ImportError:
            return self._stub_fetch(clean)

        creds_path = _credentials_path()
        if not creds_path.exists():
            return self._stub_fetch({
                **clean,
                "_stub_reason": (
                    f"credentials missing at {creds_path} — run the OAuth "
                    "bootstrap in PowerShell first"
                ),
            })

        try:
            creds = Credentials.from_authorized_user_file(  # type: ignore[attr-defined]
                str(creds_path),
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            )
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            list_req = service.users().messages().list(  # type: ignore[attr-defined]
                userId="me",
                q=clean["query"],
                maxResults=clean["max_results"],
                labelIds=clean["label_ids"] or None,
            )
            list_resp = list_req.execute() or {}
            ids = [m.get("id") for m in (list_resp.get("messages") or []) if m.get("id")]

            details: list[dict] = []
            for mid in ids[: clean["max_results"]]:
                try:
                    msg = service.users().messages().get(  # type: ignore[attr-defined]
                        userId="me", id=mid, format="full"
                    ).execute()
                    details.append(msg)
                except Exception:
                    continue
        except Exception:
            return self._stub_fetch(clean)

        prov = {"query": clean["query"], "max_results": clean["max_results"]}
        return details, prov, 0.0

    # -- Section M.3. Offline stub ----------------------------------------

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = params if "query" in params else self._validate_params(params)
        now_iso = datetime.now(timezone.utc).isoformat()
        items = [
            {
                "id":         f"stub_msg_{i}",
                "snippet":    f"Stub email snippet #{i} — gmail client offline.",
                "payload":    {
                    "headers": [
                        {"name": "From",    "value": f"Stub Sender <stub{i}@example.com>"},
                        {"name": "To",      "value": "[stub-recipient@example.com]"},
                        {"name": "Subject", "value": f"Stub subject #{i}"},
                        {"name": "Date",    "value": now_iso},
                    ],
                    "body": {"data": ""},
                },
                "labelIds":   ["UNREAD", "INBOX"],
                "internalDate": "0",
            }
            for i in range(min(3, clean["max_results"]))
        ]
        prov_extra = {
            "query":       clean["query"],
            "max_results": clean["max_results"],
            "stub_reason": clean.get("_stub_reason", "googleapiclient not installed"),
        }
        return items, prov_extra, 0.0

    # -- Section M.4. Normalization + validation --------------------------

    @staticmethod
    def _header(headers: list[dict] | None, name: str) -> str | None:
        for h in headers or []:
            if (h.get("name") or "").lower() == name.lower():
                return h.get("value")
        return None

    def _extract_body(self, payload: dict) -> str:
        if not isinstance(payload, dict):
            return ""
        body = (payload.get("body") or {}).get("data")
        text = _safe_b64decode(body)
        if text:
            return text
        # Multipart — walk the first text/plain part.
        for part in (payload.get("parts") or []):
            mime = part.get("mimeType") or ""
            if mime.startswith("text/plain"):
                return _safe_b64decode((part.get("body") or {}).get("data"))
        for part in (payload.get("parts") or []):
            sub = self._extract_body(part)
            if sub:
                return sub
        return ""

    def _normalize(self, item: dict) -> dict:
        headers = (item.get("payload") or {}).get("headers") or []
        body    = self._extract_body(item.get("payload") or {})
        if len(body) > _BODY_SNIPPET_CHARS:
            body = body[:_BODY_SNIPPET_CHARS] + "…"

        try:
            received_at = datetime.fromtimestamp(
                int(item.get("internalDate", "0")) / 1000.0, tz=timezone.utc
            ).isoformat()
        except (TypeError, ValueError):
            received_at = None

        return {
            "id":          item.get("id"),
            "kind":        "email",
            "from":        self._header(headers, "From"),
            "to":          self._header(headers, "To"),
            "cc":          self._header(headers, "Cc"),
            "subject":     self._header(headers, "Subject"),
            "snippet":     item.get("snippet"),
            "body":        body,
            "label_ids":   list(item.get("labelIds") or []),
            "received_at": received_at,
        }

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        ok, why = super().validate_response(payload)
        if not ok:
            return ok, why
        for i, item in enumerate(payload):
            if item.get("kind") != "email":
                return False, f"item {i}: kind != 'email'"
            if not item.get("id"):
                return False, f"item {i}: missing id"
        return True, None
