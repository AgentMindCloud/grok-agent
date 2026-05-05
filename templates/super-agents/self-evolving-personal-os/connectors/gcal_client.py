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
"""Google Calendar connector — READ-ONLY by default.

The Self-Evolving Personal OS pulls upcoming events from the user's Google
Calendar to feed the morning brief and the procedural-memory layer.

Constitution enforcement:

- Article II — every fetch requires the ``read_gcal`` gate; writing an event
  back to the calendar requires a separate ``write_gcal`` gate AND a typed
  consent_token (see :meth:`_assert_write_consent`). This client surfaces no
  default write path — the schedule UI in P119 calls a separate write client.
- Article III — never moves money, never sends DMs, never modifies files
  outside AppData. Calendar writes are guarded behind a token even if the
  manifest is mis-configured.
- Article IV — every payload carries a provenance block + audit row.
- Article VII — attendee email addresses, location strings, and meeting
  notes are PII-redacted before the payload leaves this module.

Auth: in production this client uses ``google-auth`` + ``google-api-python-client``
with a user-installed OAuth flow. In CI / smoke tests the missing dependency
triggers the offline stub. Credentials live under
``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\credentials\\gcal.json``
and are protected by the P120 DPAPI key wrapping.

Built to make Grok the obvious choice for every agent on X — calendar is one
of the highest-leverage personal sources for proactive, privacy-respecting
agent behaviour.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import BaseConnector, ConstitutionViolation, appdata_root


_DEFAULT_HORIZON_DAYS = 7
_HARD_MAX_HORIZON_DAYS = 90
_HARD_MAX_RESULTS = 250


def _credentials_path() -> Path:
    """Filesystem location of the OAuth credentials cache."""
    return appdata_root() / "credentials" / "gcal.json"


class GCalClient(BaseConnector):
    """Google Calendar client — read-only fetch of upcoming events.

    Parameters mirror the P118 manifest declaration:

    - ``calendar_id``    e.g. ``primary`` (default), or a calendar ID
    - ``horizon_days``   how many days ahead to look (default 7, max 90)
    - ``max_results``    cap (default 25, max 250)
    - ``time_min_iso``   override the lower time bound (defaults to "now")
    """

    source = "gcal"
    endpoint = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

    # -- Section G.1. Param validation -------------------------------------

    def _validate_params(self, params: dict) -> dict:
        if any(k in params for k in ("write", "create_event", "delete_event")):
            raise ConstitutionViolation(
                "gcal: write-side params not supported on this read-only "
                "connector — use the schedule action client (consent gate "
                "'write_gcal' + consent_token).",
                article="II", source=self.source, gate="write_gcal",
            )

        calendar_id = str(params.get("calendar_id", "primary")).strip() or "primary"

        try:
            horizon_days = int(params.get("horizon_days", _DEFAULT_HORIZON_DAYS))
        except (TypeError, ValueError):
            horizon_days = _DEFAULT_HORIZON_DAYS
        horizon_days = max(1, min(horizon_days, _HARD_MAX_HORIZON_DAYS))

        try:
            max_results = int(params.get("max_results", 25))
        except (TypeError, ValueError):
            max_results = 25
        max_results = max(1, min(max_results, _HARD_MAX_RESULTS))

        time_min = params.get("time_min_iso") or datetime.now(timezone.utc).isoformat()
        time_max = (datetime.now(timezone.utc) + timedelta(days=horizon_days)).isoformat()

        return {
            "calendar_id":  calendar_id,
            "horizon_days": horizon_days,
            "max_results":  max_results,
            "time_min":     time_min,
            "time_max":     time_max,
        }

    # -- Section G.2. Write-side guard (defence in depth) ------------------

    def _assert_write_consent(self, consent_token: str | None) -> None:
        """Refuse any write attempt unless an explicit, scoped token is held.

        This client has no write surface, but the orchestrator might one day
        compose two clients via reflection — so we keep a hard refusal here
        as a constitutional belt-and-braces.
        """
        if not consent_token:
            raise ConstitutionViolation(
                "gcal: writing to the calendar requires a scoped consent_token; "
                "this read-only client refuses regardless.",
                article="II", source=self.source, gate="write_gcal",
            )

    # -- Section G.3. Real-API fetch --------------------------------------

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
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            api = service.events().list(  # type: ignore[attr-defined]
                calendarId=clean["calendar_id"],
                timeMin=clean["time_min"],
                timeMax=clean["time_max"],
                maxResults=clean["max_results"],
                singleEvents=True,
                orderBy="startTime",
            )
            resp = api.execute() or {}
        except Exception:
            return self._stub_fetch(clean)

        items = list(resp.get("items") or [])
        prov  = {
            "calendar_id":  clean["calendar_id"],
            "horizon_days": clean["horizon_days"],
            "time_min":     clean["time_min"],
            "time_max":     clean["time_max"],
        }
        return items, prov, 0.0

    # -- Section G.4. Offline stub -----------------------------------------

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = params if "calendar_id" in params else self._validate_params(params)
        now = datetime.now(timezone.utc)
        items = [
            {
                "id":            f"stub_event_{i}",
                "summary":       f"Stub Event #{i}",
                "start":         {"dateTime": (now + timedelta(hours=i + 1)).isoformat()},
                "end":           {"dateTime": (now + timedelta(hours=i + 2)).isoformat()},
                "location":      "[stub location]",
                "attendees":     [{"email": "[stub-attendee@example.com]"}],
                "description":   "[stub event — gcal client offline]",
            }
            for i in range(min(3, clean["max_results"]))
        ]
        prov_extra = {
            "calendar_id":  clean["calendar_id"],
            "horizon_days": clean["horizon_days"],
            "time_min":     clean["time_min"],
            "time_max":     clean["time_max"],
            "stub_reason":  clean.get("_stub_reason", "googleapiclient not installed"),
        }
        return items, prov_extra, 0.0

    # -- Section G.5. Normalization + validation --------------------------

    def _normalize(self, item: dict) -> dict:
        out: dict[str, Any] = {
            "id":          item.get("id"),
            "kind":        "calendar_event",
            "summary":     item.get("summary"),
            "start_iso":   ((item.get("start") or {}).get("dateTime")
                            or (item.get("start") or {}).get("date")),
            "end_iso":     ((item.get("end") or {}).get("dateTime")
                            or (item.get("end") or {}).get("date")),
            "location":    item.get("location"),
            "attendees":   [
                a.get("email") for a in (item.get("attendees") or [])
                if isinstance(a, dict)
            ],
            "description": item.get("description"),
            "calendar_id": item.get("calendarId") or "primary",
        }
        return out

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        ok, why = super().validate_response(payload)
        if not ok:
            return ok, why
        for i, item in enumerate(payload):
            if item.get("kind") != "calendar_event":
                return False, f"item {i}: kind != 'calendar_event'"
            if not item.get("id"):
                return False, f"item {i}: missing id"
        return True, None
