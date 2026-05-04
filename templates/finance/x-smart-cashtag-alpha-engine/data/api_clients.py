# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Public-API client wrappers for the X Smart Cashtag Alpha Engine.

Four thin wrappers backed by the APIs declared in ``grok-agent.yaml``:

- ``fetch_cashtag_quote(cashtag)``     — yfinance (equity / FX) or
                                         coingecko (crypto), routed by symbol
- ``fetch_cashtag_news(cashtag, ...)`` — NewsAPI headlines for the underlying
                                         ticker / company / project
- ``search_x_posts(query, ...)``       — STUB until P30+ wires real x_search
                                         via Grok 4.3 tool-calling
- ``_generate_alpha_via_grok(...)``    — Grok 4.3 alpha-report stub; the real
                                         Grok client wires in a later prompt

Every call returns a dict with a ``provenance`` block (Constitution Article IV)
and an ``error`` field; failures never raise so the surrounding UI / Grok
layer / store.py can render a consistent empty state rather than handling
exceptions. A line is also appended to the agent's append-only provenance
log at ``$env:LOCALAPPDATA\\grok-agent\\x-smart-cashtag-alpha-engine\\
provenance.log``.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from . import provenance_log_path


_USER_AGENT = "grok-agent/x-smart-cashtag-alpha-engine (Apache-2.0)"

# Known crypto cashtags routed to CoinGecko. Equity cashtags are routed to
# yfinance after stripping the leading '$'. Unknown cashtags fall through to
# yfinance and the wrapper surfaces a clean error if the symbol doesn't resolve.
_COINGECKO_MAP: dict[str, str] = {
    "$BTC":  "bitcoin",
    "$ETH":  "ethereum",
    "$SOL":  "solana",
    "$DOGE": "dogecoin",
    "$ADA":  "cardano",
    "$XRP":  "ripple",
    "$AVAX": "avalanche-2",
    "$MATIC": "matic-network",
}


# --- Rate limiter (process-local) -----------------------------------------

class _RateLimiter:
    """Tiny per-source minimum-interval throttle. Adequate for app use."""

    def __init__(self) -> None:
        self._last_call: dict[str, float] = {}

    def throttle(self, source: str, min_interval_s: float = 0.5) -> None:
        last = self._last_call.get(source, 0.0)
        wait = min_interval_s - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_call[source] = time.monotonic()


_RATE = _RateLimiter()


# --- Provenance helpers ---------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provenance(
    source: str, endpoint: str, cost_usd: float = 0.0, **extra: Any
) -> dict:
    """Build a provenance block per Constitution Article IV."""
    return {
        "source":       source,
        "endpoint":     endpoint,
        "retrieved_at": _now_iso(),
        "cost_usd":     cost_usd,
        **extra,
    }


def _log_provenance(action: str, prov: dict, payload_summary: dict | None = None) -> None:
    """Append one JSON line to the agent's provenance log (best-effort)."""
    log_path = provenance_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": prov.get("retrieved_at", _now_iso()),
        "action":    action,
        **prov,
        "payload":   payload_summary or {},
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


# --- Manifest tool: fetch_cashtag_quote -----------------------------------

def fetch_cashtag_quote(cashtag: str) -> dict:
    """Pull a live quote for a cashtag.

    Crypto cashtags (per ``_COINGECKO_MAP``) route to CoinGecko; everything
    else routes to yfinance with the ``$`` stripped. Failures return a
    structured dict with ``error`` populated rather than raising.
    """
    if cashtag in _COINGECKO_MAP and _COINGECKO_MAP[cashtag]:
        return _fetch_via_coingecko(cashtag, _COINGECKO_MAP[cashtag])
    return _fetch_via_yfinance(cashtag)


def _fetch_via_yfinance(cashtag: str) -> dict:
    _RATE.throttle("yfinance", min_interval_s=0.5)
    prov = _provenance(
        source="yfinance",
        endpoint="https://query2.finance.yahoo.com",
        cost_usd=0.0,
    )
    ticker = cashtag.lstrip("$").upper()
    result: dict[str, Any] = {
        "cashtag":       cashtag,
        "asset_class":   "equity",
        "ticker":        ticker,
        "price":         None,
        "currency":      None,
        "name":          None,
        "change_pct_1d": None,
        "provenance":    prov,
        "error":         None,
    }
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        result.update(
            price=price,
            currency=info.get("currency") or "USD",
            name=info.get("shortName") or info.get("longName") or ticker,
            change_pct_1d=info.get("regularMarketChangePercent"),
        )
        if price is None:
            result["error"] = f"No price field returned for ticker '{ticker}'."
    except ImportError:
        result["error"] = "yfinance not installed — run `python -m pip install -r requirements.txt`."
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    _log_provenance(
        "fetch_cashtag_quote/yfinance", prov,
        {"cashtag": cashtag, "price": result["price"], "error": result["error"]},
    )
    return result


def _fetch_via_coingecko(cashtag: str, coin_id: str) -> dict:
    _RATE.throttle("coingecko", min_interval_s=2.0)  # 30 req/min cap
    prov = _provenance(
        source="coingecko",
        endpoint="https://api.coingecko.com/api/v3/simple/price",
        cost_usd=0.0,
    )
    result: dict[str, Any] = {
        "cashtag":       cashtag,
        "asset_class":   "crypto",
        "coin_id":       coin_id,
        "price":         None,
        "currency":      "USD",
        "name":          None,
        "change_pct_1d": None,
        "provenance":    prov,
        "error":         None,
    }
    try:
        import requests
        r = requests.get(
            prov["endpoint"],
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get(coin_id, {})
        result.update(
            price=data.get("usd"),
            change_pct_1d=data.get("usd_24h_change"),
            name=coin_id,
        )
        if data.get("usd") is None:
            result["error"] = f"No usd price returned for coin '{coin_id}'."
    except ImportError:
        result["error"] = "requests not installed — run `python -m pip install -r requirements.txt`."
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    _log_provenance(
        "fetch_cashtag_quote/coingecko", prov,
        {"cashtag": cashtag, "price": result["price"], "error": result["error"]},
    )
    return result


# --- Manifest tool: fetch_cashtag_news ------------------------------------

def fetch_cashtag_news(
    cashtag: str, limit: int = 5, from_date: str | None = None
) -> dict:
    """Pull NewsAPI headlines relevant to a cashtag.

    Requires the ``NEWSAPI_KEY`` environment variable. Free-tier quota is
    100 requests/day per the manifest's ``public_apis`` declaration.
    The query is built from ``cashtag.lstrip('$')`` plus the cashtag's
    `name` if known via the local ``cashtags`` table; for the skeleton we
    keep it simple and just pass the stripped cashtag.
    """
    _RATE.throttle("newsapi", min_interval_s=1.0)
    prov = _provenance(
        source="newsapi",
        endpoint="https://newsapi.org/v2/everything",
        cost_usd=0.0,
    )
    result: dict[str, Any] = {
        "cashtag":       cashtag,
        "articles":      [],
        "total_results": 0,
        "provenance":    prov,
        "error":         None,
    }

    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        result["error"] = "NEWSAPI_KEY environment variable not set."
        _log_provenance("fetch_cashtag_news", prov, {"cashtag": cashtag, "error": result["error"]})
        return result

    try:
        import requests
        params: dict[str, Any] = {
            "q":        cashtag.lstrip("$"),
            "pageSize": max(1, min(int(limit), 100)),
            "sortBy":   "publishedAt",
        }
        if from_date:
            params["from"] = from_date
        r = requests.get(
            prov["endpoint"],
            params=params,
            headers={"X-Api-Key": api_key, "User-Agent": _USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        articles = []
        for a in data.get("articles", [])[: int(limit)]:
            articles.append({
                "title":        a.get("title"),
                "source":       (a.get("source") or {}).get("name"),
                "published_at": a.get("publishedAt"),
                "url":          a.get("url"),
            })
        result["articles"]      = articles
        result["total_results"] = int(data.get("totalResults", 0))
    except ImportError:
        result["error"] = "requests not installed — run `python -m pip install -r requirements.txt`."
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    _log_provenance(
        "fetch_cashtag_news", prov,
        {"cashtag": cashtag, "article_count": len(result["articles"]), "error": result["error"]},
    )
    return result


# --- Internal helper: search_x_posts (STUB) -------------------------------

def search_x_posts(query: str, limit: int = 10) -> dict:
    """STUB — x_search via Grok 4.3 tool-calling.

    Real Grok 4.3 wiring lands in a later prompt; this stub keeps Article IV
    honest by flagging itself with ``provenance.stub: True`` so any UI
    surface that depends on X data renders an honest empty state.
    """
    prov = _provenance(
        source="x_search via grok-4.3",
        endpoint="via_grok_4.3 tool-calling",
        cost_usd=0.0,
        stub=True,
    )
    result = {
        "query":      query,
        "posts":      [],
        "provenance": prov,
        "error":      "STUB: x_search via Grok 4.3 wires up in a later prompt.",
    }
    _log_provenance("search_x_posts", prov, {"query": query, "limit": int(limit)})
    return result


# --- Internal helper: _generate_alpha_via_grok (STUB) ---------------------

def _generate_alpha_via_grok(
    cashtag: str,
    quote: dict,
    news: dict,
    x_search_result: dict,
    window_hours: int,
) -> dict:
    """STUB — Grok 4.3 alpha-report generator.

    Returns a dict matching the JSON schema in
    ``prompts/user_templates.md#alpha-report-card`` so the surrounding
    ``store.generate_alpha_report`` can persist a structurally-valid row
    today, and the real Grok client can drop in later without changing
    the call site.

    The stub deliberately:
    - Sets ``confidence: "low"`` and a clear ``confidence_reason``
    - Names ``stub: True`` in provenance
    - Returns an empty ``contradictions`` array unless the upstream data
      contains an obvious conflict (e.g. ``quote.error`` set + non-empty
      news), in which case it surfaces that conflict honestly
    """
    prov = _provenance(
        source="grok-4.3 (stub)",
        endpoint="via_grok_4.3 tool-calling",
        cost_usd=0.0,
        stub=True,
    )
    contradictions = []
    if quote.get("error") and news.get("articles"):
        contradictions.append({
            "claim_a": {"source": "yfinance/coingecko",
                        "value":  f"price unavailable: {quote.get('error')}"},
            "claim_b": {"source": "newsapi",
                        "value":  f"{len(news.get('articles', []))} fresh headlines"},
            "delta_summary": "Price feed errored but news flow is active — primary source needed.",
        })

    body_lines = [f"**Stub alpha report** for `{cashtag}` ({window_hours}h window)."]
    if quote.get("price") is not None:
        body_lines.append(f"- yfinance/coingecko quote: ${quote['price']}")
    if news.get("articles"):
        body_lines.append(f"- {len(news['articles'])} headlines from NewsAPI")
    body_lines.append(
        "- x_search via Grok 4.3: stub (real wiring in a later prompt)"
    )

    return {
        "cashtag":           cashtag,
        "headline":          f"Stub alpha report for {cashtag} — Grok client not yet wired.",
        "body":              "\n".join(body_lines),
        "confidence":        "low",
        "confidence_reason": "Grok 4.3 client is stubbed in P28; real reports ship in a later prompt.",
        "sources":           [s for s in [
            quote.get("provenance", {}).get("source"),
            news.get("provenance",  {}).get("source"),
            x_search_result.get("provenance", {}).get("source"),
        ] if s],
        "contradictions":    contradictions,
        "model":             "grok-4.3 (stub)",
        "input_tokens":      0,
        "output_tokens":     0,
        "cost_usd":          0.0,
        "provenance":        prov,
    }
