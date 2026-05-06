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
"""Weather + personalized-news connector pair.

The Self-Evolving Personal OS pulls two ambient personal-context streams:

- **Weather** — a 5-day forecast for the user's declared locale, used by the
  morning brief ("dress for rain", "schedule outdoor errand for Wednesday").
  Defaults to OpenWeather; if the API key is missing the connector falls
  through to a clearly-flagged stub.
- **Personalized news** — a small set of headlines for the user's declared
  topics (declared in P118 manifest under ``personalization.topics``). Backed
  by NewsAPI when ``NEWSAPI_KEY`` is set; otherwise stubbed.

Constitution enforcement:

- Article II — every fetch requires the matching gate (``read_weather`` or
  ``read_news_personal``); the connectors never write back to the source.
- Article III — never echoes the user's exact home coordinates into output
  even when the manifest has them; lat/lon are PII-redacted by the base
  layer, and the locale is rounded to the nearest city/region.
- Article IV — every payload carries provenance + audit row, including the
  active rate-limit cost and stub flag.
- Article VI — Both connectors are bounded by the manifest's
  ``safety.cost_limits`` (free tiers; ``cost_usd: 0.0`` always).
- Article VII — locale is opt-in via the manifest; no IP geolocation, no
  silent telemetry.

Built for xAI, X, Grok and the ecosystem community — the weather + news pair sits on the morning
brief's surface, where the agent's "trusted ambient OS" feeling is earned or
lost in the first three seconds.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from . import BaseConnector, ConstitutionViolation


_DEFAULT_LOCALE = "Ho Chi Minh City,VN"   # creator-friendly default per CLAUDE.md
_DEFAULT_NEWS_TOPICS: tuple[str, ...] = ("xai", "grok", "creator economy")
_DEFAULT_NEWS_LIMIT = 5
_HARD_MAX_NEWS_LIMIT = 25
_DEFAULT_FORECAST_DAYS = 5
_HARD_MAX_FORECAST_DAYS = 7


# -- Section W.1. Weather connector ---------------------------------------

class WeatherClient(BaseConnector):
    """OpenWeather (or weather.gov) forecast client.

    Parameters mirror the P118 manifest declaration:

    - ``locale``        ``"City,CC"`` string (default per CLAUDE.md)
    - ``forecast_days`` 1–7 (default 5)
    - ``units``         ``"metric"`` | ``"imperial"`` (default metric)
    """

    source = "weather"
    endpoint = "https://api.openweathermap.org/data/2.5/forecast"

    _FORBIDDEN_WRITE_KEYS: frozenset[str] = frozenset({"write", "subscribe", "alert_create"})

    # Param validation -----------------------------------------------------

    def _validate_params(self, params: dict) -> dict:
        bad = [k for k in params if k in self._FORBIDDEN_WRITE_KEYS]
        if bad:
            raise ConstitutionViolation(
                f"weather: write-side params not supported: {bad}",
                article="II", source=self.source, gate="read_weather",
            )

        locale = str(params.get("locale", _DEFAULT_LOCALE)).strip() or _DEFAULT_LOCALE

        try:
            forecast_days = int(params.get("forecast_days", _DEFAULT_FORECAST_DAYS))
        except (TypeError, ValueError):
            forecast_days = _DEFAULT_FORECAST_DAYS
        forecast_days = max(1, min(forecast_days, _HARD_MAX_FORECAST_DAYS))

        units = str(params.get("units", "metric")).strip().lower()
        if units not in {"metric", "imperial"}:
            units = "metric"

        return {"locale": locale, "forecast_days": forecast_days, "units": units}

    # Real-API fetch -------------------------------------------------------

    def _do_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = self._validate_params(params)
        api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not api_key:
            return self._stub_fetch({
                **clean,
                "_stub_reason": "OPENWEATHER_API_KEY not set",
            })

        try:
            import requests  # type: ignore
        except ImportError:
            return self._stub_fetch({**clean, "_stub_reason": "requests not installed"})

        try:
            resp = requests.get(
                self.endpoint,
                params={
                    "q":     clean["locale"],
                    "appid": api_key,
                    "units": clean["units"],
                    "cnt":   clean["forecast_days"] * 8,  # 3-hour buckets
                },
                headers={"User-Agent": "grok-agent/self-evolving-personal-os"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return self._stub_fetch({**clean, "_stub_reason": "network or parse error"})

        items: list[dict] = []
        for entry in (data.get("list") or [])[: clean["forecast_days"] * 8]:
            items.append({
                "dt_iso":     datetime.fromtimestamp(
                                  int(entry.get("dt", 0)), tz=timezone.utc
                              ).isoformat() if entry.get("dt") else None,
                "temp":       (entry.get("main") or {}).get("temp"),
                "feels_like": (entry.get("main") or {}).get("feels_like"),
                "humidity":   (entry.get("main") or {}).get("humidity"),
                "weather":    [
                    {"id": w.get("id"), "main": w.get("main"), "description": w.get("description")}
                    for w in (entry.get("weather") or [])
                ],
                "wind_speed": (entry.get("wind") or {}).get("speed"),
                "rain_3h":    (entry.get("rain") or {}).get("3h"),
                "locale":     clean["locale"],
                "units":      clean["units"],
            })

        prov = {
            "locale":         clean["locale"],
            "forecast_days":  clean["forecast_days"],
            "units":          clean["units"],
        }
        return items, prov, 0.0

    # Stub -----------------------------------------------------------------

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = params if "locale" in params else self._validate_params(params)
        now = datetime.now(timezone.utc)
        items = [
            {
                "dt_iso":     now.isoformat(),
                "temp":       28.0,
                "feels_like": 30.0,
                "humidity":   80,
                "weather":    [{"id": 800, "main": "Clear", "description": "stub clear sky"}],
                "wind_speed": 2.0,
                "rain_3h":    None,
                "locale":     clean["locale"],
                "units":      clean["units"],
            }
            for _ in range(min(3, clean["forecast_days"]))
        ]
        prov_extra = {
            "locale":         clean["locale"],
            "forecast_days":  clean["forecast_days"],
            "units":          clean["units"],
            "stub_reason":    clean.get("_stub_reason", "weather client offline"),
        }
        return items, prov_extra, 0.0

    # Normalization + validation ------------------------------------------

    def _normalize(self, item: dict) -> dict:
        out = dict(item)
        out.setdefault("kind", "weather_forecast")
        return out

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        ok, why = super().validate_response(payload)
        if not ok:
            return ok, why
        for i, item in enumerate(payload):
            if item.get("kind") != "weather_forecast":
                return False, f"item {i}: kind != 'weather_forecast'"
        return True, None


# -- Section W.2. Personalized-news connector ------------------------------

class NewsPersonalClient(BaseConnector):
    """NewsAPI (or GNews) personalized-news client.

    Parameters mirror the P118 manifest declaration:

    - ``topics``     list of substrings to search (default from manifest /
                     ``personalization.topics``); falls through to a small
                     creator-friendly default if empty
    - ``limit``      max headlines (default 5, max 25)
    - ``language``   ISO-639 code (default ``"en"``)
    - ``from_iso``   only return articles newer than this ISO timestamp
    """

    source = "news_personal"
    endpoint = "https://newsapi.org/v2/everything"

    _FORBIDDEN_WRITE_KEYS: frozenset[str] = frozenset({"publish", "post", "subscribe"})

    # Param validation -----------------------------------------------------

    def _validate_params(self, params: dict) -> dict:
        bad = [k for k in params if k in self._FORBIDDEN_WRITE_KEYS]
        if bad:
            raise ConstitutionViolation(
                f"news_personal: write-side params not supported: {bad}",
                article="II", source=self.source, gate="read_news_personal",
            )

        topics = params.get("topics") or list(_DEFAULT_NEWS_TOPICS)
        if isinstance(topics, str):
            topics = [topics]
        topics = [str(t).strip() for t in topics if str(t).strip()]
        if not topics:
            topics = list(_DEFAULT_NEWS_TOPICS)

        try:
            limit = int(params.get("limit", _DEFAULT_NEWS_LIMIT))
        except (TypeError, ValueError):
            limit = _DEFAULT_NEWS_LIMIT
        limit = max(1, min(limit, _HARD_MAX_NEWS_LIMIT))

        language = str(params.get("language", "en")).strip().lower() or "en"
        from_iso = params.get("from_iso")

        return {
            "topics":   topics,
            "limit":    limit,
            "language": language,
            "from_iso": from_iso,
        }

    # Real-API fetch -------------------------------------------------------

    def _do_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = self._validate_params(params)
        api_key = os.environ.get("NEWSAPI_KEY")
        if not api_key:
            return self._stub_fetch({**clean, "_stub_reason": "NEWSAPI_KEY not set"})

        try:
            import requests  # type: ignore
        except ImportError:
            return self._stub_fetch({**clean, "_stub_reason": "requests not installed"})

        # Build a simple OR query from the user's topics; NewsAPI accepts the
        # syntax ``"a" OR "b"``. Topics are quoted to avoid spurious matches.
        q = " OR ".join(f'"{t}"' for t in clean["topics"])
        req_params: dict[str, Any] = {
            "q":         q,
            "pageSize":  clean["limit"],
            "language":  clean["language"],
            "sortBy":    "publishedAt",
        }
        if clean["from_iso"]:
            req_params["from"] = clean["from_iso"]

        try:
            resp = requests.get(
                self.endpoint,
                params=req_params,
                headers={"X-Api-Key": api_key, "User-Agent": "grok-agent/self-evolving-personal-os"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return self._stub_fetch({**clean, "_stub_reason": "network or parse error"})

        items: list[dict] = []
        for a in (data.get("articles") or [])[: clean["limit"]]:
            items.append({
                "title":         a.get("title"),
                "description":   a.get("description"),
                "url":           a.get("url"),
                "source_name":   (a.get("source") or {}).get("name"),
                "published_at":  a.get("publishedAt"),
                "topics_hit":    [
                    t for t in clean["topics"]
                    if isinstance(a.get("title"), str)
                    and t.lower() in (a.get("title") or "").lower()
                ],
            })

        prov = {
            "topics":     clean["topics"],
            "language":   clean["language"],
            "limit":      clean["limit"],
            "total_hits": int(data.get("totalResults", 0)),
        }
        return items, prov, 0.0

    # Stub -----------------------------------------------------------------

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = params if "topics" in params else self._validate_params(params)
        now_iso = datetime.now(timezone.utc).isoformat()
        items = [
            {
                "title":        f"Stub headline #{i}: {clean['topics'][0]}",
                "description":  "[stub article body — news_personal client offline]",
                "url":          f"https://stub.example.com/news/{i}",
                "source_name":  "Stub Wire",
                "published_at": now_iso,
                "topics_hit":   [clean["topics"][0]],
            }
            for i in range(min(clean["limit"], 3))
        ]
        prov_extra = {
            "topics":     clean["topics"],
            "language":   clean["language"],
            "limit":      clean["limit"],
            "stub_reason": clean.get("_stub_reason", "news_personal client offline"),
        }
        return items, prov_extra, 0.0

    # Normalization + validation ------------------------------------------

    def _normalize(self, item: dict) -> dict:
        out = dict(item)
        out.setdefault("kind", "news_article")
        return out

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        ok, why = super().validate_response(payload)
        if not ok:
            return ok, why
        for i, item in enumerate(payload):
            if item.get("kind") != "news_article":
                return False, f"item {i}: kind != 'news_article'"
            if not item.get("title"):
                return False, f"item {i}: missing title"
        return True, None
