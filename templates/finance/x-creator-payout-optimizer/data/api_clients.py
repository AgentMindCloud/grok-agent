# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""API clients + Grok stubs for the X Creator Payout Optimizer.

Owns:

- 5 Grok-stub helpers matching the JSON schemas in
  ``prompts/user_templates.md`` (forecast, optimize, tax, metrics, ROI) so
  the surrounding pipeline persists structurally-valid rows today; real
  Grok wiring lands in a later prompt.
- Two manifest tools that don't need the local DB layer:
    * ``optimize_content_topic(topic, audience_profile)``
    * ``fetch_x_metrics(handle, period_days)``
- Per-source rate limiter and append-only provenance writer.

The other three manifest tools (``forecast_earnings``,
``estimate_tax_burden``, ``analyze_content_roi``) live in ``store.py``
because they orchestrate cross-tool reads + DB persistence; they call the
Grok stubs in this module.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from . import provenance_log_path


_USER_AGENT = "grok-agent/x-creator-payout-optimizer (Apache-2.0)"


# --- Rate limiter (process-local) ------------------------------------------

class _RateLimiter:
    def __init__(self) -> None:
        self._last_call: dict[str, float] = {}

    def throttle(self, source: str, min_interval_s: float = 0.5) -> None:
        last = self._last_call.get(source, 0.0)
        wait = min_interval_s - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_call[source] = time.monotonic()


_RATE = _RateLimiter()


# --- Provenance helpers ----------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provenance(source: str, endpoint: str, cost_usd: float = 0.0, **extra: Any) -> dict:
    return {
        "source":       source,
        "endpoint":     endpoint,
        "retrieved_at": _now_iso(),
        "cost_usd":     cost_usd,
        **extra,
    }


def _log_provenance(action: str, prov: dict, payload_summary: dict | None = None) -> None:
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


# --- 5 Grok stubs (private helpers used by store.py + api_clients) --------

def _grok_forecast_call(
    *, window_days: int, horizon_days: int, companion_summary: dict, vision_summary: dict
) -> dict:
    """STUB — Grok 4.3 earnings-forecast generator."""
    _RATE.throttle("grok-forecast", min_interval_s=0.5)
    prov = _provenance(
        source="grok-4.3 (stub)",
        endpoint="via_grok_4.3 tool-call",
        cost_usd=0.0,
        stub=True,
    )
    inflow = float(companion_summary.get("total_inflow", 0.0))
    daily  = inflow / max(window_days, 1) if inflow > 0 else 0.0
    horizons = []
    for label, days in (("30 days", 30), ("60 days", 60), ("90 days", 90)):
        point = round(daily * days * (1.0 + days / 600.0), 2)
        horizons.append({
            "label": label,
            "point": point,
            "low":   round(point * 0.85, 2),
            "high":  round(point * 1.15, 2),
        })
    return {
        "horizons":          horizons,
        "drivers": [
            {"name": "X Payments creator payouts", "share_of_forecast": 0.45},
            {"name": "Ad revenue",                 "share_of_forecast": 0.30},
            {"name": "Subscription tips",          "share_of_forecast": 0.15},
            {"name": "Other",                      "share_of_forecast": 0.10},
        ],
        "confidence":        "low",
        "confidence_reason": (
            "Grok 4.3 forecast client is stubbed in P40; real model wires later."
        ),
        "data_window":       f"last {window_days} days, local Tool #1 transactions",
        "model":             "grok-4.3 (stub)",
        "provenance":        prov,
    }


def _grok_optimize_call(*, topic: str, audience_profile: dict | None) -> dict:
    """STUB — content-angle optimizer."""
    _RATE.throttle("grok-optimize", min_interval_s=0.5)
    prov = _provenance(
        source="grok-4.3 (stub)", endpoint="via_grok_4.3 tool-call",
        cost_usd=0.0, stub=True,
    )
    return {
        "topic":  topic,
        "angles": [
            {"angle": f"Stub angle for '{topic}' — angle 1", "format": "thread",
             "predicted_engagement": 0.0, "predicted_revenue_usd": 0.0,
             "confidence": "low",
             "rationale": "Grok client stubbed in P40; real angles wire later."},
        ],
        "model":      "grok-4.3 (stub)",
        "provenance": prov,
    }


def _grok_tax_call(
    *, period: dict, jurisdiction: str, gross_income: float,
    deductible_expenses: float, expense_count: int,
) -> dict:
    """STUB — tax-burden estimator."""
    _RATE.throttle("grok-tax", min_interval_s=0.5)
    prov = _provenance(
        source="grok-4.3 (stub)", endpoint="via_grok_4.3 tool-call",
        cost_usd=0.0, stub=True,
    )
    rate = 0.17 if jurisdiction.lower().startswith("vietnam") else \
           0.24 if jurisdiction.lower().startswith("united states") else \
           0.30 if jurisdiction.lower().startswith("european") else 0.20
    taxable = max(gross_income - deductible_expenses, 0.0)
    tax     = round(taxable * rate, 2)
    net     = round(gross_income - tax, 2)
    assumptions = [
        "NOT TAX ADVICE — coarse jurisdictional baseline; consult a licensed tax professional.",
        f"Baseline rate {rate*100:.0f}% applied to taxable income (gross − deductible expenses).",
    ]
    if jurisdiction.lower().startswith("vietnam"):
        assumptions.append(
            "Vietnam-resident creator with international platform earnings: foreign-source "
            "income may have additional treatment; consult a local tax professional."
        )
    if expense_count == 0:
        assumptions.append(
            "No deductible expenses found — confidence dropped to low; install Tool #4 "
            "for receipt-backed deductions."
        )
    return {
        "jurisdiction":         jurisdiction,
        "period":               period,
        "gross_income":         round(gross_income, 2),
        "deductible_expenses":  round(deductible_expenses, 2),
        "taxable_income":       round(taxable, 2),
        "estimated_rate_pct":   round(rate * 100, 1),
        "estimated_tax_owed":   tax,
        "estimated_net":        net,
        "assumptions":          assumptions,
        "confidence":           "low" if expense_count == 0 else "medium",
        "confidence_reason":    (
            "Grok 4.3 tax client is stubbed in P40; coarse baseline rates only. "
            "Real Grok client + jurisdiction tables wire later."
        ),
        "model":                "grok-4.3 (stub)",
        "provenance":           prov,
    }


def _grok_metrics_call(*, handle: str, period_days: int) -> dict:
    """STUB — X engagement metrics fetcher."""
    _RATE.throttle("grok-metrics", min_interval_s=0.5)
    prov = _provenance(
        source="x_search via grok-4.3 (stub)",
        endpoint="via_grok_4.3 tool-call",
        cost_usd=0.0,
        stub=True,
    )
    return {
        "handle":               handle,
        "period_days":          int(period_days),
        "reach_24h":            0,
        "reach_7d":             0,
        "reach_30d":            0,
        "engagement_rate_30d":  0.0,
        "follower_growth_30d":  0,
        "payout_this_month":    0.0,
        "top_posts":            [],
        "confidence":           "low",
        "confidence_reason":    "x_search via Grok 4.3 is stubbed in P40; wires up later.",
        "provenance":           prov,
    }


def _grok_roi_call(
    *, content_topic: str, period: dict,
    revenue_usd: float, cost_usd: float,
    revenue_rows: int, cost_rows: int,
    companion_installed: bool, vision_installed: bool,
) -> dict:
    """STUB — content-ROI synthesizer."""
    prov = _provenance(
        source="grok-4.3 (stub)", endpoint="via_grok_4.3 tool-call",
        cost_usd=0.0, stub=True,
    )
    net = round(revenue_usd - cost_usd, 2)
    roi_pct = round((net / cost_usd) * 100.0, 1) if cost_usd > 0 else None
    drivers = []
    if revenue_rows:
        drivers.append({"side": "revenue", "source_rows": revenue_rows,
                        "amount_usd": round(revenue_usd, 2),
                        "summary": f"{revenue_rows} Tool #1 rows aggregated"})
    if cost_rows:
        drivers.append({"side": "cost", "source_rows": cost_rows,
                        "amount_usd": round(cost_usd, 2),
                        "summary": f"{cost_rows} Tool #4 rows aggregated"})
    return {
        "content_topic":  content_topic,
        "period":         period,
        "revenue_usd":    round(revenue_usd, 2),
        "cost_usd":       round(cost_usd, 2),
        "net_usd":        net,
        "roi_pct":        roi_pct,
        "drivers":        drivers,
        "graceful_degradation": {
            "tool1_missing": not companion_installed,
            "tool4_missing": not vision_installed,
            "implication":   _gd_implication(companion_installed, vision_installed),
        },
        "confidence":      "low" if (not companion_installed or not vision_installed)
                           else ("medium" if cost_rows == 0 else "medium"),
        "confidence_reason": (
            "Grok 4.3 ROI client is stubbed in P40; real synthesis wires later."
        ),
        "model":           "grok-4.3 (stub)",
        "provenance":      prov,
    }


def _gd_implication(companion: bool, vision: bool) -> str:
    if companion and vision:
        return "All siblings present; revenue × cost join is fully populated."
    if companion and not vision:
        return ("Tool #4 missing — cost side blank; ROI shows revenue-only. "
                "Install x-money-vision-analyzer to unlock cost-side join.")
    if vision and not companion:
        return ("Tool #1 missing — revenue side blank. "
                "Install x-money-companion-dashboard to unlock revenue-side join.")
    return ("Both siblings missing — ROI is fully blank. Install Tool #1 + Tool #4 "
            "to unlock the join.")


# --- Manifest tool: optimize_content_topic --------------------------------

def optimize_content_topic(topic: str, audience_profile: dict | None = None, **_: Any) -> dict:
    """Manifest tool — suggest content angles for a topic. Returns JSON."""
    res = _grok_optimize_call(topic=topic, audience_profile=audience_profile)
    _log_provenance(
        "optimize_content_topic", res["provenance"],
        {"topic": topic, "angle_count": len(res.get("angles", []))},
    )
    return res


# --- Manifest tool: fetch_x_metrics ---------------------------------------

def fetch_x_metrics(handle: str, period_days: int = 30, **_: Any) -> dict:
    """Manifest tool — pull X engagement / reach / payouts metrics."""
    res = _grok_metrics_call(handle=handle, period_days=period_days)
    _log_provenance(
        "fetch_x_metrics", res["provenance"],
        {"handle": handle, "period_days": int(period_days)},
    )
    return res
