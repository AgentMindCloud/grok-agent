# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Public-API client wrappers for the X Money Companion Dashboard.

Three thin wrappers backed by the APIs declared in ``grok-agent.yaml``:

- ``fetch_market_quote(ticker)`` — yfinance equity / FX / crypto quote
- ``fetch_relevant_news(query, limit, from_date)`` — NewsAPI headlines
- ``search_x_posts(query, limit)`` — STUB until P24 wires real x_search
  via Grok 4.3 tool-calling

Every call returns a dict with a ``provenance`` block (Constitution Article IV)
and an ``error`` field; failures never raise so the surrounding UI / Grok
layer can render a consistent empty state rather than handling exceptions.

A line is also appended to the agent's append-only provenance log at
``$env:LOCALAPPDATA\\grok-agent\\x-money-companion-dashboard\\provenance.log``.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from . import provenance_log_path

# Naming note: the v2.15 manifest declares the parameter as ``ticker`` (the
# financial-canonical term). The user-prompt prose calls it ``symbol`` —
# we go with ``ticker`` so Grok's tool-call against the manifest schema
# binds correctly at runtime.

_USER_AGENT = "grok-agent/x-money-companion-dashboard (Apache-2.0)"


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
    source: str,
    endpoint: str,
    cost_usd: float = 0.0,
    **extra: Any,
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
    """Append one JSON line to the agent's provenance log."""
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
        # The provenance log is best-effort. A disk error must not break the call.
        pass


# --- Manifest tool: fetch_market_quote ------------------------------------

def fetch_market_quote(ticker: str) -> dict:
    """Pull a live yfinance quote (equity, FX, or crypto).

    The wrapper is offline-safe: any failure (no network, missing
    yfinance, unknown ticker) returns a structured dict with ``error``
    populated rather than raising — so the Grok layer can cite the
    failure cleanly.
    """
    _RATE.throttle("yfinance", min_interval_s=0.5)

    prov = _provenance(
        source="yfinance",
        endpoint="https://query2.finance.yahoo.com",
        cost_usd=0.0,
    )

    result: dict[str, Any] = {
        "ticker":        ticker,
        "price":         None,
        "currency":      None,
        "name":          None,
        "change_pct_1d": None,
        "provenance":    prov,
        "error":         None,
    }

    try:
        import yfinance as yf  # lazy: keeps store.py importable without yfinance
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
        result["error"] = (
            "yfinance not installed — run "
            "`python -m pip install -r requirements.txt`."
        )
    except Exception as e:  # network, parse, etc.
        result["error"] = f"{type(e).__name__}: {e}"

    _log_provenance(
        "fetch_market_quote", prov,
        {"ticker": ticker, "price": result["price"], "error": result["error"]},
    )
    return result


# --- Manifest tool: fetch_relevant_news -----------------------------------

def fetch_relevant_news(
    query: str, limit: int = 5, from_date: str | None = None
) -> dict:
    """Pull NewsAPI headlines relevant to a query.

    Requires the ``NEWSAPI_KEY`` environment variable. Free-tier quota is
    100 requests/day per the manifest's ``public_apis`` declaration.
    """
    _RATE.throttle("newsapi", min_interval_s=1.0)

    prov = _provenance(
        source="newsapi",
        endpoint="https://newsapi.org/v2/everything",
        cost_usd=0.0,
    )

    result: dict[str, Any] = {
        "query":         query,
        "articles":      [],
        "total_results": 0,
        "provenance":    prov,
        "error":         None,
    }

    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        result["error"] = "NEWSAPI_KEY environment variable not set."
        _log_provenance("fetch_relevant_news", prov, {"query": query, "error": result["error"]})
        return result

    try:
        import requests  # lazy
        params: dict[str, Any] = {
            "q":        query,
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
        "fetch_relevant_news", prov,
        {"query": query, "article_count": len(result["articles"]), "error": result["error"]},
    )
    return result


# --- Internal helper: search_x_posts (STUB) -------------------------------

def search_x_posts(query: str, limit: int = 10) -> dict:
    """STUB — x_search via Grok 4.3 tool-calling.

    The v2.15 manifest declares ``x_search`` with ``base_url:
    "via_grok_4.3"`` — meaning real X search is delegated to Grok 4.3's
    own tool-calling against the X graph rather than a direct REST call.
    The Grok client is wired in P24 (smoke test + polish); until then
    this returns a clearly-labeled stub with ``stub: True`` in
    provenance, so any UI rendering or downstream insight that depends
    on X data can render an honest empty state rather than fake content.
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
        "error":      "STUB: x_search via Grok 4.3 wires up in P24.",
    }
    _log_provenance("search_x_posts", prov, {"query": query, "limit": int(limit)})
    return result
