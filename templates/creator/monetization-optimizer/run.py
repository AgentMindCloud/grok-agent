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
"""
Monetization Optimizer -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

>>> INFORMATION ONLY -- not financial advice. <<<

This v1 runner is fully self-contained: it ships per-niche revenue-stream
bundles plus a deterministic 6/7-section synthesis pipeline that bakes the
V.1 / V.2 disclaimer chain into every money- and tax-touching output card,
matching `prompts/system.md` (auto-loaded). To wire to live Grok 4.3, replace
the body of `generate_monetization_optimization()` with a Grok call that
consumes the system prompt and returns the same schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --demo ai
    python run.py --x-handle @creator --streams-file streams.json --goals scale
    python run.py --x-handle @me --streams '[{"stream_type":"x_money","current_monthly":3400,"prev_monthly":1900,"share_percent":31}]'
    python run.py --x-handle @test --revenue-focus all --time-range 90d --goals growth
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import random
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

VERSION = "0.1.0"
TAGLINE = "Built to help xAI and Grok win."

BANNER = (
    "============================================================\n"
    f"  MONETIZATION OPTIMIZER  v{VERSION}\n"
    "  Map your revenue streams. Surface the next move.\n"
    "  >>> INFORMATION ONLY -- not financial advice. <<<\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Disclaimer constants -- the V.1 / V.2 chain
# ---------------------------------------------------------------------------

DISC_V1 = "📎 Context only -- not financial advice."
DISC_V2 = "⚠️ Not tax advice -- consult a licensed tax professional."
DISCLAIMER_BANNER = (
    "> ⚠️ **Information only -- not financial advice.** "
    "This summary surfaces patterns; it does not advise."
)

# Tokens that flip a card from finance-adjacent to tax-adjacent.
TAX_KEYWORDS = (
    "tax", "1099", "withholding", "vat", "gst", "vietnam-resident",
    "international platform earnings", "jurisdictional",
)

# Tokens that flag finance-adjacent material (the V.1 chain).
FINANCE_KEYWORDS = (
    "monetiz", "payout", "earnings", "sponsor", "cashtag", "subscription",
    "tip", "x money", "x_money", "revenue", "stream", "ltv", "mrr",
    "p&l", "share", "diversif",
)

# ---------------------------------------------------------------------------
# Static enums + bucket map
# ---------------------------------------------------------------------------

CANONICAL_STREAM_TYPES: Tuple[str, ...] = (
    "sponsorships", "x_money", "subscriptions", "tips",
)

DIRECTION_LABELS = ("up", "down", "stable")
ROI_LABELS = ("low", "medium", "medium-high", "high")
EFFORT_LABELS = ("low", "medium", "high")
SEVERITY_LABELS = ("low", "medium", "high")

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2")),
]
DEFAULT_BUCKET = "general"


# ---------------------------------------------------------------------------
# Per-bucket demo bundles. v2 will pull live X Money payouts + sponsor inbox.
# ---------------------------------------------------------------------------

DEMO_STREAM_BUNDLES: Dict[str, Dict[str, Any]] = {
    "ai": {
        "default_niche": "AI agents on X",
        "streams": [
            {"stream_type": "sponsorships", "current_monthly": 4200, "prev_monthly": 3000, "share_percent": 38, "notes": "two AI-agent advertisers concentrated"},
            {"stream_type": "x_money", "current_monthly": 3400, "prev_monthly": 1900, "share_percent": 31, "notes": "platform-native payouts climbing post-launch"},
            {"stream_type": "subscriptions", "current_monthly": 2800, "prev_monthly": 2950, "share_percent": 25, "notes": "slight slip; retention check pending"},
            {"stream_type": "tips", "current_monthly": 620, "prev_monthly": 480, "share_percent": 6, "notes": "small base; thank-you thread cadence helped"},
        ],
        "currency_symbol": "$",
        "tax_jurisdiction_hint": "international",
    },
    "productivity": {
        "default_niche": "Productivity systems for solopreneurs",
        "streams": [
            {"stream_type": "subscriptions", "current_monthly": 3600, "prev_monthly": 3200, "share_percent": 45, "notes": "paid newsletter -- the dominant stream"},
            {"stream_type": "sponsorships", "current_monthly": 1900, "prev_monthly": 1700, "share_percent": 24, "notes": "single tooling sponsor; concentration"},
            {"stream_type": "x_money", "current_monthly": 1700, "prev_monthly": 950, "share_percent": 21, "notes": "X Money rising on viral threads"},
            {"stream_type": "tips", "current_monthly": 800, "prev_monthly": 650, "share_percent": 10, "notes": "Friday-review-thread fans"},
        ],
        "currency_symbol": "$",
        "tax_jurisdiction_hint": "domestic",
    },
    "finance": {
        "default_niche": "creator economy finance",
        "streams": [
            {"stream_type": "sponsorships", "current_monthly": 5400, "prev_monthly": 4900, "share_percent": 41, "notes": "fintech advertisers, single category concentration"},
            {"stream_type": "subscriptions", "current_monthly": 3800, "prev_monthly": 3700, "share_percent": 29, "notes": "P&L-template subscriber base stable"},
            {"stream_type": "x_money", "current_monthly": 3000, "prev_monthly": 2200, "share_percent": 23, "notes": "tax-export thread spike"},
            {"stream_type": "tips", "current_monthly": 940, "prev_monthly": 720, "share_percent": 7, "notes": "supporter base growing slowly"},
        ],
        "currency_symbol": "$",
        "tax_jurisdiction_hint": "international",
    },
    "creator": {
        "default_niche": "creator economy",
        "streams": [
            {"stream_type": "subscriptions", "current_monthly": 5200, "prev_monthly": 4800, "share_percent": 42, "notes": "newsletter-funnel + Discord tier"},
            {"stream_type": "sponsorships", "current_monthly": 3300, "prev_monthly": 3500, "share_percent": 27, "notes": "slight pullback; pipeline thinning"},
            {"stream_type": "x_money", "current_monthly": 2800, "prev_monthly": 1800, "share_percent": 23, "notes": "viral-thread payouts compounding"},
            {"stream_type": "tips", "current_monthly": 980, "prev_monthly": 800, "share_percent": 8, "notes": "fan-base tipping rising"},
        ],
        "currency_symbol": "$",
        "tax_jurisdiction_hint": "domestic",
    },
    "fitness": {
        "default_niche": "Zone 2 training",
        "streams": [
            {"stream_type": "subscriptions", "current_monthly": 2400, "prev_monthly": 2100, "share_percent": 40, "notes": "paid training plan tier"},
            {"stream_type": "sponsorships", "current_monthly": 1300, "prev_monthly": 1500, "share_percent": 22, "notes": "supplement sponsor pulled back"},
            {"stream_type": "tips", "current_monthly": 980, "prev_monthly": 820, "share_percent": 16, "notes": "fan tipping after VO2 thread"},
            {"stream_type": "x_money", "current_monthly": 1300, "prev_monthly": 600, "share_percent": 22, "notes": "X Money lift on form-cue video"},
        ],
        "currency_symbol": "$",
        "tax_jurisdiction_hint": "domestic",
    },
    "general": {
        "default_niche": "X creator",
        "streams": [
            {"stream_type": "sponsorships", "current_monthly": 1800, "prev_monthly": 1600, "share_percent": 36, "notes": "small-but-stable single sponsor"},
            {"stream_type": "subscriptions", "current_monthly": 1200, "prev_monthly": 1100, "share_percent": 24, "notes": "growing slowly"},
            {"stream_type": "x_money", "current_monthly": 1500, "prev_monthly": 900, "share_percent": 30, "notes": "X Money is the fastest mover"},
            {"stream_type": "tips", "current_monthly": 500, "prev_monthly": 420, "share_percent": 10, "notes": "evergreen supporter base"},
        ],
        "currency_symbol": "$",
        "tax_jurisdiction_hint": "domestic",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_bucket(blob: str) -> str:
    s = blob.lower()
    for bucket, keys in NICHE_BUCKETS:
        for k in keys:
            if k in s:
                return bucket
    return DEFAULT_BUCKET


def is_finance_adjacent(text: str) -> bool:
    s = (text or "").lower()
    return any(k in s for k in FINANCE_KEYWORDS)


def is_tax_adjacent(text: str, jurisdiction_hint: str = "domestic") -> bool:
    s = (text or "").lower()
    if any(k in s for k in TAX_KEYWORDS):
        return True
    return False


def deterministic_seed(x_handle: str, focus: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{focus}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def _pct(current: float, prev: float) -> Optional[float]:
    if prev in (None, 0):
        return None
    return (current - prev) / prev * 100.0


def _direction(pct: Optional[float]) -> str:
    if pct is None:
        return "stable"
    if pct > 1.5:
        return "up"
    if pct < -1.5:
        return "down"
    return "stable"


def _format_pct(pct: Optional[float]) -> str:
    if pct is None:
        return "--"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _fmt_money(value: Any, symbol: str = "$") -> str:
    if value is None:
        return "--"
    return f"{symbol}{int(value):,}" if value == int(value) else f"{symbol}{value:.2f}"


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _bundle_for_bucket(bucket: str) -> Dict[str, Any]:
    return DEMO_STREAM_BUNDLES.get(bucket, DEMO_STREAM_BUNDLES["general"])


def parse_streams_input(args: argparse.Namespace, bucket: str) -> Tuple[List[Dict[str, Any]], str]:
    """Return (streams, source_label)."""
    if args.streams_file:
        text = Path(args.streams_file).read_text(encoding="utf-8")
        data = json.loads(text)
        streams = data.get("streams", []) if isinstance(data, dict) else data
        return list(streams), "file"
    if args.streams:
        s = args.streams.strip()
        return list(json.loads(s)), "inline-json"
    if args.demo:
        return list(_bundle_for_bucket(args.demo)["streams"]), "demo"
    if args.date_range:
        return list(_bundle_for_bucket(bucket)["streams"]), "date-range-fallback"
    # Spec smoke command runs without --demo / --streams / --date-range. Fall
    # back to bucket bundle so the demo always works.
    return list(_bundle_for_bucket(bucket)["streams"]), "implicit-bucket-fallback"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _enriched_streams(
    streams: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in streams:
        cur = s.get("current_monthly")
        prev = s.get("prev_monthly")
        pct = _pct(cur, prev) if cur is not None and prev not in (None, 0) else None
        delta_abs = (cur - prev) if (cur is not None and prev is not None) else None
        out.append({
            "stream_type": s.get("stream_type", "unknown"),
            "current_monthly": cur,
            "prev_monthly": prev,
            "share_percent": s.get("share_percent"),
            "notes": s.get("notes", ""),
            "delta_abs": delta_abs,
            "pct": pct,
            "direction": _direction(pct),
            "delta_quote": _format_pct(pct),
        })
    return out


def _detect_garbage(streams: List[Dict[str, Any]]) -> bool:
    if not streams:
        return True
    empty = sum(1 for s in streams if s.get("current_monthly") in (None, 0))
    return empty / len(streams) > 0.7


def _build_opportunities(
    streams: List[Dict[str, Any]],
    goals: str,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    opps: List[Dict[str, Any]] = []
    sorted_by_pct = sorted(
        [s for s in streams if s["pct"] is not None],
        key=lambda s: -s["pct"],
    )

    # 1. Strongest gainer
    if sorted_by_pct and sorted_by_pct[0]["pct"] > 5:
        s = sorted_by_pct[0]
        opps.append({
            "stream_type": s["stream_type"],
            "idea": (
                f"the {s['delta_quote']} lift is the single biggest mover; "
                f"replicate the mechanic before the trend cools."
            ),
            "roi": "high" if s["pct"] > 30 else "medium-high",
            "effort": "low" if s["stream_type"] == "x_money" else "medium",
            "confidence": "medium-high",
        })

    # 2. Second gainer (if exists and different)
    if len(sorted_by_pct) >= 2 and sorted_by_pct[1]["pct"] > 5:
        s = sorted_by_pct[1]
        opps.append({
            "stream_type": s["stream_type"],
            "idea": (
                f"{s['delta_quote']} on a smaller base; "
                f"compounds quietly if the cadence holds."
            ),
            "roi": "medium-high" if s["pct"] > 20 else "medium",
            "effort": "low",
            "confidence": "medium-high",
        })

    # 3. Diversification opportunity if any single stream >40% share
    dominant = next(
        (s for s in streams if (s.get("share_percent") or 0) >= 40),
        None,
    )
    if dominant:
        opps.append({
            "stream_type": dominant["stream_type"],
            "idea": (
                f"share is {dominant['share_percent']}% -- diversification reduces "
                "single-platform dependency without sacrificing the strongest engine."
            ),
            "roi": "medium-high" if goals == "scale" else "medium",
            "effort": "medium",
            "confidence": "medium",
        })

    # 4. Tiny-base opportunity (smallest stream growing)
    if sorted_by_pct:
        smallest = min(streams, key=lambda s: (s.get("current_monthly") or 0))
        if smallest is not sorted_by_pct[0] and (smallest.get("pct") or 0) > 10:
            opps.append({
                "stream_type": smallest["stream_type"],
                "idea": (
                    f"+{smallest.get('pct', 0):.1f}% on a small base; "
                    "a deliberate cadence keeps the upward slope without sponsor interference."
                ),
                "roi": "medium",
                "effort": "low",
                "confidence": "medium",
            })

    # Cap 3-5
    opps = opps[:5]
    if len(opps) < 3:
        opps.append({
            "stream_type": "all",
            "idea": "consolidate the analytics view first; fresh numbers reframe the next move.",
            "roi": "medium", "effort": "low", "confidence": "medium-high",
        })
    return opps[:5]


def _build_risks(
    streams: List[Dict[str, Any]],
    goals: str,
) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []

    # Concentration risk
    dominant = next(
        (s for s in streams if (s.get("share_percent") or 0) >= 40),
        None,
    )
    if dominant:
        sev = "medium" if (dominant.get("share_percent") or 0) < 50 else "high"
        risks.append({
            "severity": sev,
            "failure_mode": (
                f"single-stream concentration -- {dominant['stream_type']} is "
                f"{dominant['share_percent']}% of total revenue; a platform/policy "
                "shift would compress the largest line overnight."
            ),
            "mitigation_hint": (
                "diversify via the second-largest stream; track weekly in `x-money-companion-dashboard`."
            ),
        })

    # Declining stream
    decliner = min(
        streams, key=lambda s: (s.get("pct") if s.get("pct") is not None else 999),
    )
    if decliner.get("pct") is not None and decliner["pct"] < -3:
        sev = "low" if decliner["pct"] > -10 else "medium"
        risks.append({
            "severity": sev,
            "failure_mode": (
                f"{decliner['stream_type']} is slipping ({decliner['delta_quote']}); "
                "the slope matters more than the absolute when scaled to a year."
            ),
            "mitigation_hint": (
                f"run a 30-day retention check via `analytics-summarizer` and an "
                f"audience-question pass via `mention-summarizer`."
            ),
        })

    # X Money platform-dependency callout (always when x_money is in input)
    x_money = next((s for s in streams if s["stream_type"] == "x_money"), None)
    if x_money and x_money.get("share_percent", 0) >= 20 and len(risks) < 3:
        risks.append({
            "severity": "medium",
            "failure_mode": (
                f"x_money line is {x_money.get('share_percent', 0)}% of mix -- "
                "a platform payout policy change would compress this line directly."
            ),
            "mitigation_hint": (
                f"hedge with subscriptions or sponsor pipeline; pull receipts via "
                f"`x-money-vision-analyzer` so the tax basis stays clean."
            ),
        })

    if not risks:
        risks.append({
            "severity": "low",
            "failure_mode": "no acute concentration or decline risks surfaced this period.",
            "mitigation_hint": "stay vigilant; recheck quarterly via `analytics-summarizer`.",
        })

    return risks[:3]


def _build_recommendations(
    streams: List[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    niche_label: str,
    bucket: str,
    goals: str,
    jurisdiction_hint: str,
) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []

    recs.append({
        "text": (
            "Pull a unified payout view via `x-money-companion-dashboard` to ground "
            "the share-percent column in primary-source numbers (Tool #1 carries the "
            "same Not-financial-advice chain)."
        ),
        "tax_tag": False,
    })

    recs.append({
        "text": (
            f"Forecast next quarter via `x-creator-payout-optimizer --niche \"{niche_label}\"` -- "
            "it models content-to-payout ROI with the same disclaimer chain."
        ),
        "tax_tag": False,
    })

    if opportunities:
        top = opportunities[0]
        recs.append({
            "text": (
                f"Expand the strongest opportunity ('{top['stream_type']}') into 5 "
                f"thread ideas via `content-idea-generator --niche \"{niche_label}\"`."
            ),
            "tax_tag": False,
        })

    # Tax-adjacent recommendation when international jurisdiction is hinted
    if jurisdiction_hint == "international":
        recs.append({
            "text": (
                "Aggregate this quarter's payout receipts via `x-money-vision-analyzer` "
                "into the Companion Dashboard SQLite -- keeps the tax basis clean and "
                "the V.1 + V.2 disclaimer chain consistent across tools."
            ),
            "tax_tag": True,
        })
    else:
        recs.append({
            "text": (
                f"Triage the high-LTV sponsor inbound via `mention-summarizer` -- "
                "the monetization-relevant subset deserves a same-day reply pass."
            ),
            "tax_tag": False,
        })

    if goals in ("growth", "scale"):
        recs.append({
            "text": (
                f"Investigate the dominant gainer's drivers via `research-assistant "
                f"--query \"{niche_label} payout volatility\"` to ground the upside before extrapolating."
            ),
            "tax_tag": False,
        })
    else:
        recs.append({
            "text": (
                f"Queue tomorrow's brief on the revenue-mix shift via `daily-briefing-agent --focus-areas \"{niche_label}\"`."
            ),
            "tax_tag": False,
        })

    return recs[:5]


def _confidence(streams: List[Dict[str, Any]]) -> Tuple[str, str]:
    n = len(streams)
    n_with_prev = sum(1 for s in streams if s.get("prev_monthly") not in (None, 0))
    n_with_share = sum(1 for s in streams if s.get("share_percent") is not None)
    if n >= 4 and n_with_prev == n and n_with_share == n:
        label = "high"
    elif n >= 3 and n_with_prev >= 3:
        label = "medium-high"
    elif n >= 2:
        label = "medium"
    else:
        label = "low"
    reason = (
        f"{n} stream(s) covered; {n_with_prev} with previous-period baseline; "
        f"{n_with_share} with share-percent supplied."
    )
    return label, reason


def _build_outlook(
    streams: List[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    goals: str,
) -> Optional[str]:
    if goals not in ("growth", "scale"):
        return None
    if not opportunities:
        return None
    top = opportunities[0]
    sorted_by_pct = sorted(
        [s for s in streams if s["pct"] is not None],
        key=lambda s: -s["pct"],
    )
    biggest = sorted_by_pct[0] if sorted_by_pct else None
    if biggest:
        # Pick the second-largest *different* stream by share% so the Outlook
        # never says "X together with X".
        sorted_by_share = sorted(
            streams, key=lambda s: -(s.get("share_percent") or 0),
        )
        partner = next(
            (s for s in sorted_by_share if s["stream_type"] != biggest["stream_type"]),
            None,
        )
        if partner:
            combined = (biggest.get("share_percent") or 0) + (partner.get("share_percent") or 0)
            share_text = (
                f"{biggest['stream_type']} together with {partner['stream_type']} "
                f"would cross {combined:.0f}% of total mix"
            )
        else:
            share_text = f"{biggest['stream_type']} compounds further"
    else:
        share_text = "the dominant stream compounds further"
    return (
        f"If the {top['stream_type']} momentum compounds another 30-60 days, "
        f"{share_text} -- a concentration that earns optimization but also earns a "
        "real diversification plan. The healthy version of "
        f"'{goals}' here is replicating the mechanic into a second stream, not "
        "letting one stream dominate."
    )


def _generate_headline(
    streams: List[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    time_range: str,
) -> str:
    sorted_by_pct = sorted(
        [s for s in streams if s["pct"] is not None],
        key=lambda s: -s["pct"],
    )
    if sorted_by_pct and sorted_by_pct[0]["pct"] > 5:
        biggest = sorted_by_pct[0]
        magnitude = (
            "large" if biggest["pct"] > 30 else "moderate" if biggest["pct"] > 10 else "small"
        )
        if opportunities:
            return (
                f"{time_range} {biggest['stream_type']} up {magnitude} "
                f"({biggest['delta_quote']}); model it via x-creator-payout-optimizer "
                "(Tool #3 carries the same Not-financial-advice chain)."
            )
    return (
        f"{time_range} revenue mix mostly stable; consolidate the picture via "
        "x-money-companion-dashboard before the next move."
    )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_monetization_optimization(
    x_handle: str,
    streams: Optional[List[Dict[str, Any]]] = None,
    revenue_focus: str = "all",
    time_range: str = "90d",
    goals: str = "growth",
    niche: Optional[str] = None,
    today: Optional[_dt.date] = None,
    jurisdiction_hint: str = "domestic",
) -> Dict[str, Any]:
    """Return a structured monetization optimization dict.

    See P57 system prompt for the canonical output shape.
    """
    if revenue_focus not in ("sponsorships", "subscriptions", "tips", "x_money", "all"):
        raise ValueError(f"revenue_focus must be one of sponsorships|subscriptions|tips|x_money|all, got {revenue_focus!r}")
    if time_range not in ("30d", "90d", "12m"):
        raise ValueError(f"time_range must be 30d|90d|12m, got {time_range!r}")
    if goals not in ("growth", "stability", "scale"):
        raise ValueError(f"goals must be growth|stability|scale, got {goals!r}")
    if streams is None:
        raise ValueError("streams must not be None at API level (caller resolves input)")

    today = today or _dt.date.today()
    rng = random.Random(deterministic_seed(x_handle, revenue_focus, today))

    bucket = detect_bucket(niche or "")
    niche_label = niche or _bundle_for_bucket(bucket).get("default_niche", "X creator")

    enriched = _enriched_streams(streams)

    if _detect_garbage(enriched):
        return {
            "refused": True,
            "warning": (
                ">70% of input stream rows are empty or zero-valued. Re-export "
                "from your payout dashboard, or pass --demo for the offline pipeline."
            ),
            "x_handle": x_handle, "today": today.isoformat(),
            "revenue_focus": revenue_focus, "time_range": time_range, "goals": goals,
            "niche_bucket": bucket, "niche_label": niche_label,
            "streams": enriched, "opportunities": [], "risks": [],
            "recommendations": [], "outlook": None,
            "confidence_label": "low",
            "confidence_reason": "garbage batch detected",
            "headline": "",
        }

    if revenue_focus != "all":
        focused = [s for s in enriched if s["stream_type"] == revenue_focus]
        # Keep all streams in the table but flag the focus for opportunity ranking.
        focus_streams_for_opps = focused or enriched
    else:
        focus_streams_for_opps = enriched

    opportunities = _build_opportunities(focus_streams_for_opps, goals, rng)
    risks = _build_risks(enriched, goals)
    recommendations = _build_recommendations(
        streams=enriched, opportunities=opportunities, risks=risks,
        niche_label=niche_label, bucket=bucket, goals=goals,
        jurisdiction_hint=jurisdiction_hint,
    )
    conf_label, conf_reason = _confidence(enriched)
    outlook = _build_outlook(enriched, opportunities, goals)
    headline = _generate_headline(enriched, opportunities, time_range)

    return {
        "refused": False,
        "warning": None,
        "x_handle": x_handle,
        "today": today.isoformat(),
        "revenue_focus": revenue_focus,
        "time_range": time_range,
        "goals": goals,
        "niche_bucket": bucket,
        "niche_label": niche_label,
        "streams": enriched,
        "opportunities": opportunities,
        "risks": risks,
        "recommendations": recommendations,
        "confidence_label": conf_label,
        "confidence_reason": conf_reason,
        "outlook": outlook,
        "headline": headline,
        "jurisdiction_hint": jurisdiction_hint,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_monetization_optimization


# ---------------------------------------------------------------------------
# Rendering -- mandatory disclaimers on every money/tax card
# ---------------------------------------------------------------------------

def render_report(result: Dict[str, Any], currency_symbol: str = "$") -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n"
        "<!-- IMPORTANT: Information only -- not financial advice. -->\n\n"
    )
    meta = textwrap.dedent(f"""\
        # Monetization Summary -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Niche bucket:** {result['niche_bucket']}
        - **Niche label:** {result['niche_label']}
        - **Revenue focus:** {result['revenue_focus']}
        - **Time range:** {result['time_range']}
        - **Goals:** {result['goals']}

        > {TAGLINE}

        """)

    if result["refused"]:
        body = textwrap.dedent(f"""\
            {DISCLAIMER_BANNER}

            ## Refusal

            {result['warning']}

            Confidence: {result['confidence_label']} -- {result['confidence_reason']}.
            """)
        return license_block + meta + body

    out: List[str] = [DISCLAIMER_BANNER, "", "## Headline", "", result["headline"], ""]

    out.append("## Current Revenue Streams")
    out.append("")
    out.append("| stream_type | current_monthly | vs prev | share % | direction |")
    out.append("| ----------- | --------------- | ------- | ------- | --------- |")
    for s in result["streams"]:
        cur = _fmt_money(s["current_monthly"], currency_symbol)
        delta = (
            f"{_fmt_money(s['delta_abs'], currency_symbol)} ({s['delta_quote']})"
            if s["delta_abs"] is not None else "--"
        )
        share = f"{s['share_percent']}%" if s.get("share_percent") is not None else "--"
        out.append(f"| {s['stream_type']} | {cur} | {delta} | {share} | {s['direction']} |")
    out.append("")

    out.append("## Opportunities")
    out.append("")
    for i, op in enumerate(result["opportunities"], start=1):
        out.append(f"{i}. **{op['stream_type']}** -- {op['idea']}")
        out.append(
            f"   - ROI: {op['roi']}; effort: {op['effort']}; confidence: {op['confidence']}"
        )
        out.append(f"   {DISC_V1}")
    out.append("")

    out.append("## Risks")
    out.append("")
    for i, r in enumerate(result["risks"], start=1):
        out.append(f"{i}. **severity: {r['severity']}** -- {r['failure_mode']}")
        out.append(f"   - Mitigation: {r['mitigation_hint']}")
        out.append(f"   {DISC_V1}")
    out.append("")

    out.append("## Recommended Actions")
    out.append("")
    for rec in result["recommendations"]:
        out.append(f"- {rec['text']}")
        if rec.get("tax_tag"):
            out.append(f"  {DISC_V1}")
            out.append(f"  {DISC_V2}")
        else:
            out.append(f"  {DISC_V1}")
    out.append("")

    out.append("## Confidence")
    out.append("")
    out.append(f"{result['confidence_label']} -- {result['confidence_reason']}")
    out.append("")

    if result.get("outlook"):
        out.append("## Outlook")
        out.append("")
        out.append(result["outlook"])
        out.append("")
        out.append(DISC_V1)
        out.append("")

    return license_block + meta + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="monetization-optimizer",
        description=(
            f"Monetization Optimizer v{VERSION} -- map your revenue streams. "
            "Information only -- not financial advice. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --demo ai
              python run.py --x-handle @creator --streams-file streams.json --goals scale
              python run.py --x-handle @me --revenue-focus all --time-range 90d --goals growth
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument("--streams", default=None, help="Inline JSON list of stream records.")
    parser.add_argument("--streams-file", default=None, help="Path to a JSON file with {streams} or just a list.")
    parser.add_argument("--date-range", default=None, help="ISO range like '2026-04-05:2026-05-05' (v1: bucket fallback).")
    parser.add_argument(
        "--demo", choices=sorted(DEMO_STREAM_BUNDLES.keys()), default=None,
        help="Use a prefab niche bundle.",
    )
    parser.add_argument(
        "--revenue-focus", choices=("sponsorships", "subscriptions", "tips", "x_money", "all"),
        default="all", help="Stream category to weight (default all).",
    )
    parser.add_argument(
        "--time-range", choices=("30d", "90d", "12m"), default="90d",
        help="Look-back window label (default 90d).",
    )
    parser.add_argument(
        "--goals", choices=("growth", "stability", "scale"), default="growth",
        help="Creator's stated goal (default growth).",
    )
    parser.add_argument("--niche", default=None, help="Optional niche hint (e.g. 'AI agents on X').")
    parser.add_argument(
        "--jurisdiction", choices=("domestic", "international"), default=None,
        help="Tax-jurisdiction hint; default reads from the bucket bundle.",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument("--version", action="version", version=f"monetization-optimizer {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    if args.date:
        try:
            today = _dt.date.fromisoformat(args.date)
        except ValueError:
            sys.stderr.write(f"X  Invalid --date {args.date!r}; expected YYYY-MM-DD\n")
            return 64
    else:
        today = _dt.date.today()

    bucket_blob = (args.niche or "") + " " + (args.demo or "") + " " + (args.x_handle or "")
    bucket = detect_bucket(bucket_blob)
    if bucket == DEFAULT_BUCKET and args.demo:
        bucket = args.demo

    bundle = _bundle_for_bucket(bucket)
    jurisdiction_hint = args.jurisdiction or bundle.get("tax_jurisdiction_hint", "domestic")
    currency_symbol = bundle.get("currency_symbol", "$")

    try:
        streams, source_label = parse_streams_input(args, bucket)
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
        sys.stderr.write(f"X  failed to load streams: {e}\n")
        return 64

    try:
        result = generate_monetization_optimization(
            x_handle=args.x_handle,
            streams=streams,
            revenue_focus=args.revenue_focus,
            time_range=args.time_range,
            goals=args.goals,
            niche=args.niche,
            today=today,
            jurisdiction_hint=jurisdiction_hint,
        )
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 64

    report = render_report(result, currency_symbol=currency_symbol)

    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        n_streams = len(result["streams"])
        verb = "Refused" if result["refused"] else f"Wrote summary ({n_streams} streams, source={source_label})"
        sys.stdout.write(f"\nOK {verb} -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
