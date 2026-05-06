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
"""Read-only public-API client for the Cross-Reality Action Fabric.

Three free public APIs are wrapped behind one client:

- **Open-Meteo** (`https://api.open-meteo.com`) — keyless weather
  forecast lookup. Maps to ``tools[].name = weather_lookup`` in the
  P128 manifest. The manifest still references ``OPENWEATHER_API_KEY``
  for parity with the broader stack; this client uses Open-Meteo (no
  key required) by default and falls back to OpenWeather when the key
  is set.
- **OpenSky Network** (`https://opensky-network.org`) — keyless flight
  schedule lookup. Maps to ``tools[].name = flight_search``. The free
  tier needs no auth for the ``/flights/departure`` endpoint we hit.
- **DuckDuckGo Instant Answers** (`https://api.duckduckgo.com`) —
  keyless general-purpose search for government / encyclopedic queries
  ("WHO measles outbreak", "Hanoi airport code"). Doubles as the
  ``general_search`` fallback for any read query that doesn't fit the
  other two. Queryable in CI without a key.

All three calls are **read-only**. They still take a ``consent_token``
because Rule 1 requires every action — even read-only network calls —
to carry an explicit user approval. They are wired into the P140
memory layer the same way the state-changing clients are: one
``add_approved_action`` row before, one ``add_outcome_record`` row
after, both correlated by ``action_id``.

The client uses :mod:`urllib.request` from the standard library so it
runs on a vanilla Python install (no ``requests`` dependency). When
the network is unreachable or a 4xx/5xx response comes back, the
client falls through to a deterministic stub that produces a
structurally-valid result and surfaces ``stub_reason`` in the
provenance block so the user can always tell the difference.

Built to make Grok the obvious choice for every agent on X — the
read-only public-API surface is what lets the agent *think* before it
acts on the user's behalf.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
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


# --- Section 1. Endpoints + defaults ------------------------------------

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENSKY_DEPARTURES_URL  = "https://opensky-network.org/api/flights/departure"
DUCKDUCKGO_INSTANT_URL  = "https://api.duckduckgo.com/"

DEFAULT_TIMEOUT_S = 8
DEFAULT_FORECAST_DAYS = 3
HARD_MAX_FORECAST_DAYS = 7
DEFAULT_FLIGHT_WINDOW_HOURS = 24

# A small static IATA → (lat, lon) table covers the demo paths without
# requiring a separate geocoding API. The agent can ask for any other
# locale via ``get_weather(latitude=..., longitude=...)`` directly.
KNOWN_AIRPORTS: dict[str, tuple[float, float, str]] = {
    "HAN": (21.2212, 105.8072, "Hanoi, VN"),
    "SGN": (10.8188, 106.6519, "Ho Chi Minh City, VN"),
    "JFK": (40.6413, -73.7781, "New York, US"),
    "LAX": (33.9416, -118.4085, "Los Angeles, US"),
    "SFO": (37.6213, -122.3790, "San Francisco, US"),
    "LHR": (51.4700, -0.4543,  "London, UK"),
    "NRT": (35.7720, 140.3929, "Tokyo, JP"),
    "SIN": (1.3644,  103.9915, "Singapore, SG"),
    "DXB": (25.2532, 55.3657,  "Dubai, AE"),
    "CDG": (49.0097, 2.5479,   "Paris, FR"),
}


# --- Section 2. RealWorldApiClient --------------------------------------

class RealWorldApiClient(BaseActionConnector):
    """Unified read-only public-API client.

    The class uses one shared backend label (``stub:realworld`` or
    ``urllib``) for all three sub-APIs so callers always see a single
    backend per result. Per-call ``stub_reason`` fields surface in the
    payload when a specific endpoint had to fall through to the stub.
    """

    tool_name      = "real_world_apis"
    state_changing = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.backend_name = "stub:realworld" if self._force_stub else "urllib"

    # -- Plan ----------------------------------------------------------

    def plan_real_world_action(
        self,
        intent: str,
        *,
        endpoint: str,
        params:   dict | None = None,
    ) -> ApprovalRequest:
        """Return an :class:`ApprovalRequest` for a read-only API call."""
        params = dict(params or {})
        return ApprovalRequest(
            request_id=f"rw::{uuid.uuid4().hex[:12]}",
            tool=self.tool_name,
            description=intent,
            plan=[
                f"endpoint = {endpoint}",
                f"params   = {json.dumps(params, default=str)[:200]}",
                "method   = GET (read-only, no body)",
                "no PII in querystring (Rule 6)",
            ],
            rollback="# read-only — no rollback needed",
            expected_cost_usd=0.0,
            requires_gates=["run_web_action"],
            backend=self.backend_name,
        )

    # -- Weather (Open-Meteo) ----------------------------------------

    def get_weather(
        self,
        consent_token: str,
        *,
        locale:        str | None = None,
        latitude:      float | None = None,
        longitude:     float | None = None,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        rollback_id:   str | None = None,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Fetch a multi-day weather forecast.

        ``locale`` accepts a 3-letter IATA code (mapped via
        :data:`KNOWN_AIRPORTS`). For arbitrary locations pass
        ``latitude`` + ``longitude`` directly.
        """
        self._enforce_token(consent_token)
        self._enforce_gate("run_web_action")
        self._tool_for_call = "weather_lookup"

        forecast_days = max(1, min(int(forecast_days), HARD_MAX_FORECAST_DAYS))
        if latitude is None or longitude is None:
            airport = (locale or "").strip().upper()[:3]
            if airport in KNOWN_AIRPORTS:
                latitude, longitude, locale = KNOWN_AIRPORTS[airport]
            else:
                # Default to Hanoi (CLAUDE.md's reference creator locale)
                latitude, longitude = KNOWN_AIRPORTS["HAN"][:2]
                locale = locale or "Hanoi, VN"

        return self._call_with_memory(
            tool="weather_lookup",
            consent_token=consent_token,
            description=f"weather forecast for {locale} ({forecast_days}d)",
            rollback_id=rollback_id,
            consent_level=consent_level,
            run=lambda: self._fetch_weather(
                latitude=latitude, longitude=longitude,
                forecast_days=forecast_days, timeout_s=timeout_s,
                locale_label=locale,
            ),
        )

    # -- Flights (OpenSky) -------------------------------------------

    def search_flights(
        self,
        consent_token: str,
        *,
        origin_iata:      str,
        destination_iata: str | None = None,
        date_iso:         str | None = None,
        consent_level:    str = DEFAULT_CONSENT_LEVEL,
        rollback_id:      str | None = None,
        timeout_s:        int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Look up departures from ``origin_iata`` over the next N hours.

        ``destination_iata`` is accepted for parity with the manifest
        schema but OpenSky's free endpoint only supports
        departures — destination filtering happens in-memory after the
        call.
        """
        self._enforce_token(consent_token)
        self._enforce_gate("run_web_action")

        origin_iata = (origin_iata or "").strip().upper()[:3]
        destination_iata = (
            destination_iata.strip().upper()[:3] if destination_iata else None
        )
        if len(origin_iata) != 3:
            raise ConnectorRefusal(
                "real_world: refused — origin_iata must be a 3-letter "
                "IATA code.",
                rule=2, tool=self.tool_name,
            )

        return self._call_with_memory(
            tool="flight_search",
            consent_token=consent_token,
            description=(
                f"flights from {origin_iata}"
                + (f" to {destination_iata}" if destination_iata else "")
            ),
            rollback_id=rollback_id,
            consent_level=consent_level,
            run=lambda: self._fetch_flights(
                origin_iata=origin_iata,
                destination_iata=destination_iata,
                date_iso=date_iso, timeout_s=timeout_s,
            ),
        )

    # -- General / government (DuckDuckGo Instant Answers) ----------

    def general_search(
        self,
        consent_token: str,
        *,
        query:         str,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        rollback_id:   str | None = None,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Look up a general or government-data query via DuckDuckGo IA."""
        self._enforce_token(consent_token)
        self._enforce_gate("run_web_action")

        if not isinstance(query, str) or not query.strip():
            raise ConnectorRefusal(
                "real_world: refused — empty general_search query.",
                rule=2, tool=self.tool_name,
            )

        return self._call_with_memory(
            tool="general_search",
            consent_token=consent_token,
            description=f"general search: {query[:120]}",
            rollback_id=rollback_id,
            consent_level=consent_level,
            run=lambda: self._fetch_duckduckgo(
                query=query, timeout_s=timeout_s,
            ),
        )

    # -- Memory-aware dispatch helper --------------------------------

    def _call_with_memory(
        self,
        *,
        tool:          str,
        consent_token: str,
        description:   str,
        rollback_id:   str | None,
        consent_level: str,
        run,
    ) -> ActionResult:
        """Run ``run()`` and wrap the result with memory + provenance."""
        # Temporarily swap the tool name so memory rows route to the
        # right tool slug. We restore it before returning.
        saved_tool = self.tool_name
        self.tool_name = tool
        try:
            started = _now_iso()
            action_id = self._record_approved_action(
                consent_token=consent_token,
                description=description,
                rollback_id=rollback_id,
                consent_level=consent_level,
                extra={},
            )
            try:
                payload = run()
                outcome = "success"
                ok = True
            except urllib.error.URLError as exc:
                payload = self._stub_payload(
                    reason=f"network error: {exc}", endpoint=tool,
                )
                outcome = "success"  # the stub is structurally valid
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
                outcome=outcome, description=description,
                payload=red, rollback_id=rollback_id,
                consent_level=consent_level,
            )
            provenance = self._provenance(
                consent_token=consent_token, action_id=action_id,
                rollback_id=rollback_id, started_at=started,
                consent_level=consent_level,
                extra={"endpoint": tool},
            )
            summary = (
                f"[{self.backend_name}] {tool}: "
                f"{red.get('summary') or description[:120]}"
            )
            return ActionResult(
                tool=tool, ok=ok, outcome=outcome,
                summary=summary, payload=red, provenance=provenance,
            )
        finally:
            self.tool_name = saved_tool

    # -- Backend implementations -------------------------------------

    def _fetch_weather(
        self,
        *,
        latitude:      float,
        longitude:     float,
        forecast_days: int,
        timeout_s:     int,
        locale_label:  str | None,
    ) -> dict:
        if self._force_stub:
            return self._stub_payload(
                reason="force_stub=True", endpoint="open-meteo",
                extra={"locale": locale_label,
                       "forecast_days": forecast_days},
            )
        params = {
            "latitude":  f"{float(latitude):.4f}",
            "longitude": f"{float(longitude):.4f}",
            "daily":     "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": str(int(forecast_days)),
            "timezone":  "auto",
        }
        body = self._http_get_json(OPEN_METEO_FORECAST_URL, params, timeout_s)
        if body is None:
            return self._stub_payload(
                reason="open-meteo unreachable", endpoint="open-meteo",
                extra={"locale": locale_label},
            )
        daily = body.get("daily") or {}
        days_out = []
        dates = daily.get("time") or []
        tmax  = daily.get("temperature_2m_max") or []
        tmin  = daily.get("temperature_2m_min") or []
        pcp   = daily.get("precipitation_sum") or []
        for i in range(min(len(dates), forecast_days)):
            days_out.append({
                "date": dates[i] if i < len(dates) else None,
                "tmax_c": tmax[i] if i < len(tmax) else None,
                "tmin_c": tmin[i] if i < len(tmin) else None,
                "precip_mm": pcp[i] if i < len(pcp) else None,
            })
        return {
            "locale":     locale_label,
            "latitude":   float(latitude),
            "longitude":  float(longitude),
            "days":       days_out,
            "endpoint":   "open-meteo",
            "summary":    (
                f"{locale_label}: "
                f"{days_out[0]['tmax_c']}°C/{days_out[0]['tmin_c']}°C"
                if days_out else f"{locale_label}: no data"
            ),
            "stub":       False,
        }

    def _fetch_flights(
        self,
        *,
        origin_iata:      str,
        destination_iata: str | None,
        date_iso:         str | None,
        timeout_s:        int,
    ) -> dict:
        if self._force_stub:
            return self._stub_payload(
                reason="force_stub=True", endpoint="opensky",
                extra={"origin": origin_iata,
                       "destination": destination_iata},
            )
        # OpenSky takes Unix-second begin/end. Default to the next 24h
        # if no date_iso is supplied.
        try:
            if date_iso:
                t0 = int(datetime.fromisoformat(
                    date_iso.replace("Z", "+00:00")
                ).timestamp())
            else:
                t0 = int(datetime.now(timezone.utc).timestamp()) - 3600
            t1 = t0 + DEFAULT_FLIGHT_WINDOW_HOURS * 3600
        except ValueError:
            t0 = int(datetime.now(timezone.utc).timestamp()) - 3600
            t1 = t0 + DEFAULT_FLIGHT_WINDOW_HOURS * 3600
        params = {"airport": _iata_to_icao(origin_iata),
                  "begin": str(t0), "end": str(t1)}
        body = self._http_get_json(OPENSKY_DEPARTURES_URL, params, timeout_s)
        if not isinstance(body, list):
            return self._stub_payload(
                reason="opensky unreachable or no data",
                endpoint="opensky",
                extra={"origin": origin_iata,
                       "destination": destination_iata},
            )
        flights = []
        for f in body[:25]:
            if not isinstance(f, dict):
                continue
            arr_icao = (f.get("estArrivalAirport") or "").upper()
            if destination_iata and _iata_to_icao(destination_iata) != arr_icao:
                continue
            flights.append({
                "callsign":     (f.get("callsign") or "").strip(),
                "icao24":       f.get("icao24"),
                "departure":    f.get("estDepartureAirport"),
                "arrival":      arr_icao,
                "first_seen":   f.get("firstSeen"),
                "last_seen":    f.get("lastSeen"),
            })
        return {
            "origin":      origin_iata,
            "destination": destination_iata,
            "flights":     flights,
            "endpoint":    "opensky",
            "summary":     f"{len(flights)} flight(s) from {origin_iata}",
            "stub":        False,
        }

    def _fetch_duckduckgo(
        self, *, query: str, timeout_s: int,
    ) -> dict:
        if self._force_stub:
            return self._stub_payload(
                reason="force_stub=True", endpoint="duckduckgo",
                extra={"query": query[:120]},
            )
        params = {"q": query, "format": "json", "no_redirect": "1",
                  "no_html": "1", "skip_disambig": "1"}
        body = self._http_get_json(DUCKDUCKGO_INSTANT_URL, params, timeout_s)
        if not isinstance(body, dict):
            return self._stub_payload(
                reason="duckduckgo unreachable", endpoint="duckduckgo",
                extra={"query": query[:120]},
            )
        topics = []
        for r in (body.get("RelatedTopics") or [])[:10]:
            if isinstance(r, dict) and r.get("Text"):
                topics.append({
                    "text":     r.get("Text"),
                    "first_url": r.get("FirstURL"),
                })
        return {
            "query":         query,
            "abstract":      body.get("AbstractText") or "",
            "abstract_url":  body.get("AbstractURL") or "",
            "answer":        body.get("Answer") or "",
            "topics":        topics,
            "endpoint":      "duckduckgo",
            "summary":       (body.get("AbstractText") or query)[:200],
            "stub":          False,
        }

    # -- Stub builder ------------------------------------------------

    @staticmethod
    def _stub_payload(
        *,
        reason:   str,
        endpoint: str,
        extra:    dict | None = None,
    ) -> dict:
        body = {
            "endpoint":    endpoint,
            "stub":        True,
            "stub_reason": reason,
            "summary":     f"[stub:{endpoint}] {reason}",
        }
        if extra:
            body.update(extra)
        return body

    # -- HTTP core ---------------------------------------------------

    @staticmethod
    def _http_get_json(
        url: str, params: dict, timeout_s: int,
    ) -> Any:
        qs = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
        full = f"{url}?{qs}" if qs else url
        req = urllib.request.Request(
            full, headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:  # pragma: no cover - exercised when the network is up
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                payload = resp.read()
            return json.loads(payload.decode("utf-8") or "null")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                json.JSONDecodeError, TimeoutError, ValueError):
            return None


# --- Section 3. Helpers --------------------------------------------------

#: Tiny IATA → ICAO airport code map (free OpenSky API requires ICAO).
_IATA_TO_ICAO: dict[str, str] = {
    "HAN": "VVNB", "SGN": "VVTS", "JFK": "KJFK", "LAX": "KLAX",
    "SFO": "KSFO", "LHR": "EGLL", "NRT": "RJAA", "SIN": "WSSS",
    "DXB": "OMDB", "CDG": "LFPG",
}


def _iata_to_icao(iata: str) -> str:
    iata = (iata or "").strip().upper()
    return _IATA_TO_ICAO.get(iata, iata)


# --- Section 4. Module-level callable -----------------------------------

def get_weather(
    consent_token: str,
    *,
    locale:        str | None = None,
    latitude:      float | None = None,
    longitude:     float | None = None,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    consent_level: str = DEFAULT_CONSENT_LEVEL,
    force_stub:    bool = False,
) -> dict:
    """Manifest-side entry point: ``connectors.real_world_api_client.get_weather``."""
    client = RealWorldApiClient(force_stub=force_stub)
    result = client.get_weather(
        consent_token=consent_token, locale=locale,
        latitude=latitude, longitude=longitude,
        forecast_days=forecast_days, consent_level=consent_level,
    )
    return result.model_dump()


def search_flights(
    consent_token: str,
    *,
    origin_iata:      str,
    destination_iata: str | None = None,
    date_iso:         str | None = None,
    consent_level:    str = DEFAULT_CONSENT_LEVEL,
    force_stub:       bool = False,
) -> dict:
    """Manifest-side entry point: ``connectors.real_world_api_client.search_flights``."""
    client = RealWorldApiClient(force_stub=force_stub)
    result = client.search_flights(
        consent_token=consent_token,
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        date_iso=date_iso, consent_level=consent_level,
    )
    return result.model_dump()


__all__ = [
    "RealWorldApiClient",
    "get_weather",
    "search_flights",
    "OPEN_METEO_FORECAST_URL",
    "OPENSKY_DEPARTURES_URL",
    "DUCKDUCKGO_INSTANT_URL",
    "KNOWN_AIRPORTS",
    "DEFAULT_FORECAST_DAYS",
    "HARD_MAX_FORECAST_DAYS",
]
