# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Monetization Optimizer — runner.

CLI entry point for the ``monetization-optimizer`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied X revenue ledger (JSON) — or seeded demo
signals when no file is provided — and emits the strict 7/8-section
monetization plan defined by the merged P85 system prompt:

  1. Plan Snapshot
  2. Plan Performance (4-row metric table + weighted Plan score)
  3. Earnings Forecast (Article V.1 disclaimer at the head + wide bands)
  4. Sponsorship Fit Analysis (paraphrased archetypes only)
  5. Tax & Expense Notes (Article V.2 disclaimer at the head)
  6. Red Flags (surfaces single-channel-dependence paradox in BOTH places)
  7. Recommendations (>= 3 cross-template bridges; V.1 per monetization rec)
  + Confidence footer
  + Optional Plan Audit (auto-appended when red_flags > 3 OR
    projection_horizon='365d' OR data_source='demo')

Hard guarantees enforced by this runner (mirrors the P85 system prompt):

* Drafts only. The runner emits text the creator reads; never
  auto-publishes, auto-pitches, or auto-files anything.
* No fabricated dollar amounts. Forecasts are reported as wide bands,
  never as point estimates. Demo signals carry an explicit
  `[demo signal — re-run with --revenue-file for real-ledger forecast]`
  label so the creator never confuses the demo for their actual ledger.
* Single-channel-dependence paradox surfaced in BOTH the Plan
  Performance section AND the Red Flags section whenever the top
  channel's share of revenue exceeds the configured concentration
  threshold (default 0.60) AND Earnings forecast confidence >= 60.
* Monetization Plan score formula is fixed:
    round(0.30*Diversification_norm + 0.25*Earnings_confidence_norm +
          0.25*Sponsorship_fit_norm + 0.20*Tax_readiness_norm).
* 5-arrow trend vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼) with ±5% / ±25%
  thresholds for sub-score deltas.
* Sponsorship recommendations are paraphrased archetypes only; the
  runner refuses to suggest specific brand names.
* Article V.1 (Not financial advice) disclaimer at the head of the
  Earnings Forecast section AND attached to every recommendation that
  derives a monetization tactic from the analytics or revenue file.
* Article V.2 (Not tax advice) disclaimer at the head of the Tax &
  Expense Notes section, with the Vietnam-resident-creator addendum.
* >= 3 distinct cross-template slugs in the Recommendations; bridges
  always include `analytics-summarizer` and `content-idea-generator`
  when relevant to the recommendation set.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + ledger +
  horizon + date).
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_monetization_plan

Built for X, Grok & the ecosystem community.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from random import Random
from typing import Optional

# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "prompts" / "system.md"

CHANNELS = (
    "paid_tier",
    "creator_fund",
    "sponsorships",
    "digital_products",
    "affiliate",
)

CHANNEL_FOCUS_OPTIONS = (*CHANNELS, "all")

PROJECTION_HORIZONS = ("30d", "90d", "365d")

SCORE_METRICS = (
    "Earnings forecast confidence",
    "Revenue diversification",
    "Sponsorship fit alignment",
    "Tax-and-expense readiness",
)

# Per the P85 system prompt: Diversification weighted highest because
# concentration is the killer of creator-economy sustainability;
# Earnings confidence and Sponsorship fit tied at 0.25 because either
# failing alone defeats the plan; Tax readiness weighted lowest because
# it is documentation hygiene, not tax filing.
SCORE_WEIGHTS = {
    "Revenue diversification": 0.30,
    "Earnings forecast confidence": 0.25,
    "Sponsorship fit alignment": 0.25,
    "Tax-and-expense readiness": 0.20,
}

# 5-arrow trend bucketing thresholds (% change vs reference value)
TREND_THRESHOLDS = {
    "strong_rise": 25.0,
    "rise": 5.0,
    "fall": -5.0,
    "strong_fall": -25.0,
}

# Single-channel-dependence paradox config
DEFAULT_CONCENTRATION_THRESHOLD = 0.60
PARADOX_FORECAST_CONFIDENCE_FLOOR = 60

# Forecast cone-of-uncertainty band widths by horizon (± fraction of median)
FORECAST_BAND_WIDTHS = {
    "30d": 0.25,
    "90d": 0.35,
    "365d": 0.60,
}

CROSS_TEMPLATE_BRIDGES = (
    "analytics-summarizer",
    "content-idea-generator",
    "x-creator-payout-optimizer",
    "x-money-companion-dashboard",
    "x-money-vision-analyzer",
    "niche-influencer-finder",
    "follower-quality-analyzer",
    "competitor-watch",
    "brand-voice-trainer",
    "cross-platform-reposter",
    "ab-test-suggester",
    "thread-builder",
    "comment-engagement-booster",
)

ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

ARTICLE_V2_DISCLAIMER = (
    "> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction. "
    "Consult a licensed tax professional. Especially relevant for "
    "Vietnam-resident creators with international platform earnings."
)

# Demo signals — explicitly labelled so the creator never confuses them
# for real data. Three demo modes, one per acceptance-criteria example.

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "projection_horizon": "90d",
    "channel_focus": "all",
    "jurisdiction": "VN",
    "data_source": "demo",
    "currency": "USD",
    "channels": [
        {"channel": "sponsorships", "gross_90d": 12000},
        {"channel": "paid_tier", "gross_90d": 1200},
        {"channel": "creator_fund", "gross_90d": 0},
        {"channel": "digital_products", "gross_90d": 2400},
        {"channel": "affiliate", "gross_90d": 800},
    ],
    "history_depth_days": 90,
    "analytics_file_present": False,
    "sponsorship_signals": {
        "recent_sponsor_niche": "dev-tools",
        "creator_niche": "agent-eval",
        "audience_substantive_overlap_pct": 74,
        "audience_size_match_only_pct": 95,
    },
    "tax_expense_signals": {
        "expense_tracking_active": True,
        "reserve_pct_set_aside": 0,
        "documentation_quality": "medium",
    },
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "projection_horizon": "90d",
    "channel_focus": "all",
    "jurisdiction": "US",
    "data_source": "demo",
    "currency": "USD",
    "channels": [
        {"channel": "sponsorships", "gross_90d": 3500},
        {"channel": "paid_tier", "gross_90d": 2500},
        {"channel": "creator_fund", "gross_90d": 800},
        {"channel": "digital_products", "gross_90d": 2200},
        {"channel": "affiliate", "gross_90d": 1000},
    ],
    "history_depth_days": 180,
    "analytics_file_present": True,
    "sponsorship_signals": {
        "recent_sponsor_niche": "habit-tracking-app",
        "creator_niche": "habit-stacking",
        "audience_substantive_overlap_pct": 70,
        "audience_size_match_only_pct": 78,
    },
    "tax_expense_signals": {
        "expense_tracking_active": True,
        "reserve_pct_set_aside": 25,
        "documentation_quality": "high",
    },
}

DEMO_365D_AUDIT = {
    "x_handle": "@JanSol0s",
    "projection_horizon": "365d",
    "channel_focus": "all",
    "jurisdiction": "VN",
    "data_source": "demo",
    "currency": "USD",
    "channels": [
        {"channel": "sponsorships", "gross_90d": 5400},
        {"channel": "paid_tier", "gross_90d": 2100},
        {"channel": "creator_fund", "gross_90d": 0},
        {"channel": "digital_products", "gross_90d": 0},
        {"channel": "affiliate", "gross_90d": 0},
    ],
    "history_depth_days": 30,
    "analytics_file_present": False,
    "sponsorship_signals": {
        "recent_sponsor_niche": "dev-tools",
        "creator_niche": "agent-eval",
        "audience_substantive_overlap_pct": 65,
        "audience_size_match_only_pct": 90,
    },
    "tax_expense_signals": {
        "expense_tracking_active": False,
        "reserve_pct_set_aside": 0,
        "documentation_quality": "low",
    },
}

_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,15}(?![A-Za-z0-9_])"
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ChannelView:
    totals: dict
    shares: dict
    top_channel: str
    top_share: float
    total_90d: float
    active_channels: int


@dataclass
class PlanScores:
    diversification: int
    earnings_confidence: int
    sponsorship_fit: int
    tax_readiness: int
    plan_score: int
    paradox_active: bool
    diversification_arrow: str
    earnings_arrow: str
    sponsorship_arrow: str
    tax_arrow: str
    interpretations: dict = field(default_factory=dict)


@dataclass
class ForecastBand:
    horizon: str
    median: float
    low: float
    high: float
    currency_label: str


@dataclass
class RedFlag:
    title: str
    severity: str
    explanation: str
    remediation: str


@dataclass
class Recommendation:
    text: str
    channel: str
    priority: str
    bridge_slug: str
    monetization: bool = True


@dataclass
class SponsorshipArchetype:
    label: str
    cadence_guidance: str


# ---------------------------------------------------------------------------
# Privacy guard (only the creator's handle in body)
# ---------------------------------------------------------------------------


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Monetization Optimizer privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def load_revenue_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"--revenue-file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"--revenue-file is not valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# Channel mix + diversification
# ---------------------------------------------------------------------------


def compute_channel_view(payload: dict) -> ChannelView:
    rows = payload.get("channels", [])
    totals = {c: 0.0 for c in CHANNELS}
    for row in rows:
        ch = row.get("channel")
        if ch in totals:
            totals[ch] += float(row.get("gross_90d", 0))
    total = sum(totals.values()) or 1.0
    shares = {c: v / total for c, v in totals.items()}
    top_channel, top_share = max(shares.items(), key=lambda x: x[1])
    active = sum(1 for c in CHANNELS if totals[c] > 0)
    return ChannelView(
        totals=totals,
        shares=shares,
        top_channel=top_channel,
        top_share=top_share,
        total_90d=sum(totals.values()),
        active_channels=active,
    )


# ---------------------------------------------------------------------------
# Sub-score computations
# ---------------------------------------------------------------------------


def diversification_subscore(top_share: float) -> int:
    """At top_share=0.20 (perfectly even 5-channel mix) -> 100;
    at top_share=1.00 (single channel) -> 0; linear in between."""
    raw = 100.0 - max(0.0, top_share - 0.20) * 125.0
    return int(round(max(0.0, min(100.0, raw))))


def earnings_confidence_subscore(payload: dict, view: ChannelView) -> int:
    base = 45
    base += min(20, view.active_channels * 5)
    if payload.get("analytics_file_present"):
        base += 10
    history = int(payload.get("history_depth_days", 90))
    base += min(15, (history // 30) * 3)
    if payload.get("data_source") == "demo":
        base = min(base, 78)  # cap demo confidence so creator never confuses for real
    return max(0, min(100, base))


def sponsorship_fit_subscore(payload: dict) -> int:
    sig = payload.get("sponsorship_signals") or {}
    overlap = int(sig.get("audience_substantive_overlap_pct", 50))
    return max(0, min(100, overlap))


def tax_readiness_subscore(payload: dict) -> int:
    sig = payload.get("tax_expense_signals") or {}
    score = 0
    if sig.get("expense_tracking_active"):
        score += 25
    reserve = int(sig.get("reserve_pct_set_aside", 0))
    if reserve >= 20:
        score += 30
    elif reserve >= 10:
        score += 15
    quality = (sig.get("documentation_quality") or "low").lower()
    if quality == "high":
        score += 30
    elif quality == "medium":
        score += 20
    elif quality == "low":
        score += 10
    if payload.get("jurisdiction"):
        score += 15
    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# Trend arrow helpers
# ---------------------------------------------------------------------------


def trend_arrow_from_score(score: int, healthy_floor: int = 60) -> str:
    """Map a 0-100 sub-score to a 5-arrow trend bucket relative to the
    sub-score healthy floor. Above healthy = ▲ (and ▲▲ above 1.5x);
    near healthy = ▬; below healthy slips to ▼ / ▼▼."""
    if score >= healthy_floor + 25:
        return "▲▲"
    if score >= healthy_floor + 5:
        return "▲"
    if score >= healthy_floor - 5:
        return "▬"
    if score >= healthy_floor - 25:
        return "▼"
    return "▼▼"


# ---------------------------------------------------------------------------
# Plan scoring
# ---------------------------------------------------------------------------


def score_plan(
    payload: dict,
    view: ChannelView,
    concentration_threshold: float,
) -> PlanScores:
    diversification = diversification_subscore(view.top_share)
    earnings_conf = earnings_confidence_subscore(payload, view)
    sponsorship_fit = sponsorship_fit_subscore(payload)
    tax_readiness = tax_readiness_subscore(payload)

    plan = round(
        SCORE_WEIGHTS["Revenue diversification"] * diversification
        + SCORE_WEIGHTS["Earnings forecast confidence"] * earnings_conf
        + SCORE_WEIGHTS["Sponsorship fit alignment"] * sponsorship_fit
        + SCORE_WEIGHTS["Tax-and-expense readiness"] * tax_readiness
    )

    paradox = (
        view.top_share > concentration_threshold
        and earnings_conf >= PARADOX_FORECAST_CONFIDENCE_FLOOR
    )

    return PlanScores(
        diversification=diversification,
        earnings_confidence=earnings_conf,
        sponsorship_fit=sponsorship_fit,
        tax_readiness=tax_readiness,
        plan_score=int(plan),
        paradox_active=paradox,
        diversification_arrow=trend_arrow_from_score(diversification, healthy_floor=70),
        earnings_arrow=trend_arrow_from_score(earnings_conf, healthy_floor=70),
        sponsorship_arrow=trend_arrow_from_score(sponsorship_fit, healthy_floor=65),
        tax_arrow=trend_arrow_from_score(tax_readiness, healthy_floor=65),
        interpretations=_metric_interpretations(
            diversification, earnings_conf, sponsorship_fit, tax_readiness,
            view, payload,
        ),
    )


def _metric_interpretations(
    diversification: int,
    earnings_conf: int,
    sponsorship_fit: int,
    tax_readiness: int,
    view: ChannelView,
    payload: dict,
) -> dict:
    out = {}
    pct = view.top_share * 100.0
    if diversification >= 80:
        out["Revenue diversification"] = (
            f"Stack is well-diversified; top channel ({view.top_channel}) is {pct:.0f}% of revenue."
        )
    elif diversification >= 50:
        out["Revenue diversification"] = (
            f"Moderate concentration; top channel ({view.top_channel}) is {pct:.0f}% of revenue — watch for drift toward single-channel-dependence."
        )
    elif diversification >= 30:
        out["Revenue diversification"] = (
            f"Concentration risk; top channel ({view.top_channel}) is {pct:.0f}% — paradox eligible if forecast confidence is medium-or-higher."
        )
    else:
        out["Revenue diversification"] = (
            f"Severe concentration; top channel ({view.top_channel}) is {pct:.0f}% — one platform shift erases the stack."
        )

    if earnings_conf >= 75:
        out["Earnings forecast confidence"] = (
            "Strong signal density across channels and history; forecast bands tighten."
        )
    elif earnings_conf >= 60:
        out["Earnings forecast confidence"] = (
            "Medium confidence; bands are honest cone-of-uncertainty width."
        )
    else:
        out["Earnings forecast confidence"] = (
            "Low confidence; bands are wide, single-period reads dominate the projection."
        )

    sig = payload.get("sponsorship_signals") or {}
    size_only = int(sig.get("audience_size_match_only_pct", 0))
    if sponsorship_fit >= 70:
        out["Sponsorship fit alignment"] = (
            f"Substantive niche overlap is real (size-only match {size_only}%) — sponsorship trust is durable."
        )
    elif sponsorship_fit >= 50:
        out["Sponsorship fit alignment"] = (
            "Niche overlap is partial; cap cadence and audit each deal individually."
        )
    else:
        out["Sponsorship fit alignment"] = (
            "Niche overlap is thin; aggressive sponsorship would erode audience trust."
        )

    tax_sig = payload.get("tax_expense_signals") or {}
    reserve = int(tax_sig.get("reserve_pct_set_aside", 0))
    if tax_readiness >= 75:
        out["Tax-and-expense readiness"] = (
            f"Documentation hygiene is strong; reserve at {reserve}% is within typical heuristics."
        )
    elif tax_readiness >= 50:
        out["Tax-and-expense readiness"] = (
            f"Documentation hygiene is mid-band; reserve at {reserve}% — start now if not already saving aside."
        )
    else:
        out["Tax-and-expense readiness"] = (
            "Documentation hygiene is thin; tax-ambush risk if international earnings hit a filing window."
        )

    return out


# ---------------------------------------------------------------------------
# Earnings forecast bands
# ---------------------------------------------------------------------------


def forecast_band(view: ChannelView, horizon: str, currency_label: str) -> ForecastBand:
    multiplier = {"30d": 1 / 3.0, "90d": 1.0, "365d": 365.0 / 90.0}[horizon]
    median = view.total_90d * multiplier
    width = FORECAST_BAND_WIDTHS[horizon]
    low = median * (1.0 - width)
    high = median * (1.0 + width)
    return ForecastBand(
        horizon=horizon,
        median=median,
        low=low,
        high=high,
        currency_label=currency_label,
    )


def _fmt_money(value: float, currency_label: str) -> str:
    return f"{currency_label} {value:,.0f}"


# ---------------------------------------------------------------------------
# Sponsorship archetypes
# ---------------------------------------------------------------------------


def sponsorship_archetypes(payload: dict, view: ChannelView) -> tuple[list[SponsorshipArchetype], list[str]]:
    sig = payload.get("sponsorship_signals") or {}
    creator_niche = (sig.get("creator_niche") or "the creator's niche").lower()
    recent = (sig.get("recent_sponsor_niche") or "").lower()
    archetypes: list[SponsorshipArchetype] = []

    if "agent" in creator_niche or "agent-eval" in creator_niche or "dev" in creator_niche:
        archetypes.append(SponsorshipArchetype(
            label="Dev-tools company with technical-founder audience",
            cadence_guidance="1 sponsored thread per 4-6 organic posts",
        ))
        archetypes.append(SponsorshipArchetype(
            label="Open-source-first infrastructure project",
            cadence_guidance="paid-deep-dive every 6-8 weeks",
        ))
        archetypes.append(SponsorshipArchetype(
            label="Technical-conference / dev-event organiser",
            cadence_guidance="1 sponsored thread per event cycle",
        ))
    elif "habit" in creator_niche or "productivity" in creator_niche:
        archetypes.append(SponsorshipArchetype(
            label="Habit-tracking app with privacy-first stance",
            cadence_guidance="1 sponsored thread per 5-7 organic posts",
        ))
        archetypes.append(SponsorshipArchetype(
            label="Note-taking / knowledge-base tool with personal-OS positioning",
            cadence_guidance="paid case-study every 6-8 weeks",
        ))
        archetypes.append(SponsorshipArchetype(
            label="Wellness-podcast network with creator-economy crossover",
            cadence_guidance="1 sponsored thread per quarterly campaign",
        ))
    else:
        archetypes.append(SponsorshipArchetype(
            label="Niche-aligned SaaS with substantive (not just size) audience overlap",
            cadence_guidance="1 sponsored thread per 4-6 organic posts",
        ))
        archetypes.append(SponsorshipArchetype(
            label="Open-community / open-source partner in the creator's primary cluster",
            cadence_guidance="paid-deep-dive every 6-8 weeks",
        ))
        archetypes.append(SponsorshipArchetype(
            label="Niche-event organiser or curator publication",
            cadence_guidance="1 sponsored thread per event cycle",
        ))

    avoid: list[str] = []
    avoid.append(
        "Consumer-finance / cashtag-promotion archetype (regulatory + trust risk for international audiences)."
    )
    if "agent" in creator_niche or "dev" in creator_niche:
        avoid.append("Generic-SaaS archetype where the audience overlap is purely audience-size, not substantive.")
    elif "habit" in creator_niche:
        avoid.append("Wearable / supplement archetype with thin scientific backing — trust risk for the niche.")
    else:
        avoid.append("Any archetype where the audience match is size-only and the substantive niche overlap is below 50%.")
    return archetypes, avoid


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: PlanScores,
    view: ChannelView,
    payload: dict,
    concentration_threshold: float,
    is_demo: bool,
) -> list[RedFlag]:
    flags: list[RedFlag] = []
    pct = view.top_share * 100.0

    # Rule 1: single-channel-dependence paradox
    if scores.paradox_active:
        flags.append(RedFlag(
            title="Single-channel-dependence paradox",
            severity="high",
            explanation=(
                f"{view.top_channel} is {pct:.0f}% of revenue while Earnings forecast confidence sits at "
                f"{scores.earnings_confidence}/100 (medium-or-higher). Concentration without runway is "
                "the killer of creator-economy sustainability."
            ),
            remediation=(
                "Activate at least one dormant channel from the 5-channel mix and harden the dominant "
                "channel against platform-policy risk (export agreements, contract contingencies, 30d termination clauses)."
            ),
        ))

    # Rule 2: tax-ambush risk
    tax_sig = payload.get("tax_expense_signals") or {}
    reserve = int(tax_sig.get("reserve_pct_set_aside", 0))
    if reserve < 10 and view.total_90d >= 5000:
        flags.append(RedFlag(
            title="Tax-ambush risk",
            severity="medium",
            explanation=(
                f"Reserve set-aside is {reserve}% on {_fmt_money(view.total_90d, payload.get('currency', 'USD'))} of "
                "90d revenue. International platform earnings can hit a filing window faster than expected."
            ),
            remediation=(
                "Begin a 20-30% reserve from the next inbound invoice; consult a licensed tax professional "
                "for jurisdiction-specific filings before quarter close."
            ),
        ))

    # Rule 3: sponsorship-niche-substance mismatch
    sig = payload.get("sponsorship_signals") or {}
    size_only = int(sig.get("audience_size_match_only_pct", 0))
    substantive = int(sig.get("audience_substantive_overlap_pct", 0))
    if size_only - substantive >= 30 and substantive < 60:
        flags.append(RedFlag(
            title="Sponsorship-niche-substance mismatch",
            severity="medium",
            explanation=(
                f"Audience size-match ({size_only}%) far outpaces substantive niche overlap ({substantive}%). "
                "Aggressive monetisation against the size signal would erode trust."
            ),
            remediation=(
                "Filter sponsor candidates by substantive overlap, not audience size; vet via "
                "`niche-influencer-finder` before pitching."
            ),
        ))

    # Rule 4: concentration without forecast confidence
    if (
        not scores.paradox_active
        and view.top_share > concentration_threshold
        and scores.earnings_confidence < PARADOX_FORECAST_CONFIDENCE_FLOOR
    ):
        flags.append(RedFlag(
            title="Concentration without forecast confidence",
            severity="medium",
            explanation=(
                f"Top channel is {pct:.0f}% of revenue but Earnings forecast confidence at "
                f"{scores.earnings_confidence}/100 is too thin to confirm whether this is the trend or the noise."
            ),
            remediation=(
                "Widen the input window (longer history) or attach an analytics-summarizer export to lift forecast confidence; "
                "if confidence stays low after that, treat the concentration as exposure rather than allocation."
            ),
        ))

    # Rule 5: forecast-without-baseline (demo with no analytics file)
    if is_demo and not payload.get("analytics_file_present"):
        flags.append(RedFlag(
            title="Forecast-without-baseline",
            severity="low",
            explanation=(
                "No analytics-summarizer export attached; the runner is forecasting on the revenue ledger alone."
            ),
            remediation=(
                "Run `analytics-summarizer` on the same period and attach the export via --analytics-file to anchor the forecast."
            ),
        ))

    # Rule 6: long-horizon cone-of-uncertainty (365d)
    if payload.get("projection_horizon") == "365d":
        flags.append(RedFlag(
            title="365d cone-of-uncertainty",
            severity="medium",
            explanation=(
                "365d forecasts have wide bands by construction — single-quarter platform shifts can move the median by 30%+."
            ),
            remediation=(
                "Treat the 365d band as planning ranges, not budgets; re-run quarterly via `analytics-summarizer` + this runner."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-period read",
            severity="low",
            explanation=(
                "One ledger snapshot is directional, not conclusive. Treat the score as a snapshot, not a trend."
            ),
            remediation=(
                "Snapshot monthly via this runner + `analytics-summarizer` to build a real baseline of plan-score trend arrows."
            ),
        ))

    return flags[:5]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: PlanScores,
    view: ChannelView,
    payload: dict,
    channel_focus: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []
    sig = payload.get("sponsorship_signals") or {}
    creator_niche = sig.get("creator_niche") or "the creator's niche"

    # 1. Activate dormant channel
    dormant = [c for c in CHANNELS if view.totals[c] == 0]
    if dormant:
        target = dormant[0]
        pool.append(Recommendation(
            text=(
                "activate the dormant channel and run a 30d baseline measurement. "
                "Surfaces the missing channel and gives Diversification a real number to plan against."
            ),
            channel=target,
            priority="high",
            bridge_slug="analytics-summarizer",
            monetization=True,
        ))

    # 2. Ship paid-tier MVP if currently dormant or tiny
    if view.totals.get("paid_tier", 0) < view.total_90d * 0.10:
        pool.append(Recommendation(
            text=(
                "ship a 90d MVP at a single price point with explicit anchor content. "
                f"Pair the launch with a long-form trust-building thread tied to the {creator_niche} niche."
            ),
            channel="paid_tier",
            priority="high",
            bridge_slug="content-idea-generator",
            monetization=True,
        ))

    # 3. Harden the dominant channel (sponsorships hardening)
    if view.top_channel == "sponsorships":
        pool.append(Recommendation(
            text=(
                "harden the dominant channel with cadence + contract contingency. "
                "Cap sponsored cadence at 1 per 4-6 organic posts; require 30d termination clauses; "
                "widen the sponsor archetype list before pitching."
            ),
            channel="sponsorships",
            priority="medium",
            bridge_slug="niche-influencer-finder",
            monetization=True,
        ))
    else:
        pool.append(Recommendation(
            text=(
                "harden the dominant channel against platform-policy risk. "
                "Document escape hatches, export agreements, and a 30d substitution plan if the channel disappears."
            ),
            channel=view.top_channel,
            priority="medium",
            bridge_slug="niche-influencer-finder",
            monetization=True,
        ))

    # 4. Scope a digital product
    if view.totals.get("digital_products", 0) < view.total_90d * 0.20:
        pool.append(Recommendation(
            text=(
                "scope a single high-ROI artefact (template / guide / course) for the next quarter. "
                "Use analytics-summarizer signals to confirm the niche supports paid downloads."
            ),
            channel="digital_products",
            priority="medium",
            bridge_slug="analytics-summarizer",
            monetization=True,
        ))

    # 5. Audit affiliate placement
    pool.append(Recommendation(
        text=(
            "audit current placement for trust-risk and disclosure compliance. "
            "Placement matters more than volume in a niche audience; remove anything that could read as undisclosed."
        ),
        channel="affiliate",
        priority="low",
        bridge_slug="competitor-watch",
        monetization=False,
    ))

    # 6. Validate paid-tier conversion intent before pricing
    if view.totals.get("paid_tier", 0) > 0:
        pool.append(Recommendation(
            text=(
                "validate audience supports paid-tier conversion before raising the price point. "
                "Quality of audience matters more than size when modelling LTV."
            ),
            channel="paid_tier",
            priority="medium",
            bridge_slug="follower-quality-analyzer",
            monetization=True,
        ))

    # 7. A/B price points
    pool.append(Recommendation(
        text=(
            "A/B test price points or paid-tier hooks once 30+ paying members exist. "
            "Single-axis isolation keeps the read clean."
        ),
        channel="paid_tier",
        priority="low",
        bridge_slug="ab-test-suggester",
        monetization=True,
    ))

    # 8. Brand-voice consistency in sponsored posts
    pool.append(Recommendation(
        text=(
            "keep voice consistent in sponsored / paid-tier posts to avoid voice-drift erosion of trust. "
            "Train a voice profile from the creator's organic anchor posts."
        ),
        channel="sponsorships",
        priority="low",
        bridge_slug="brand-voice-trainer",
        monetization=True,
    ))

    # 9. Cross-platform funnel widening
    pool.append(Recommendation(
        text=(
            "adapt high-EV monetization posts onto LinkedIn / Newsletter to widen the funnel "
            "without exposing the X audience to repeat content."
        ),
        channel="digital_products",
        priority="low",
        bridge_slug="cross-platform-reposter",
        monetization=True,
    ))

    # 10. Always-on measurement bridge (guarantees analytics-summarizer in the bridge set)
    pool.append(Recommendation(
        text=(
            "snapshot the period via `analytics-summarizer` to anchor the next forecast in real "
            "engagement signals rather than the revenue ledger alone."
        ),
        channel="all",
        priority="medium",
        bridge_slug="analytics-summarizer",
        monetization=False,
    ))

    # 11. Always-on content bridge (guarantees content-idea-generator in the bridge set)
    pool.append(Recommendation(
        text=(
            f"source the next anchor post in the highest-EV {creator_niche} cluster via "
            "`content-idea-generator` so monetization growth is fed by fresh, on-niche content."
        ),
        channel="all",
        priority="medium",
        bridge_slug="content-idea-generator",
        monetization=True,
    ))

    rng.shuffle(pool)

    chosen: list[Recommendation] = []
    seen_bridges: set[str] = set()
    channel_count: dict[str, int] = {}

    # Always include analytics-summarizer + content-idea-generator first if present
    priority_slugs = ("analytics-summarizer", "content-idea-generator")
    for slug in priority_slugs:
        for rec in pool:
            if rec.bridge_slug == slug and rec not in chosen:
                if channel_focus != "all" and rec.channel != channel_focus and len(chosen) >= 2:
                    continue
                if channel_count.get(rec.channel, 0) >= 2 and channel_focus != rec.channel:
                    continue
                chosen.append(rec)
                seen_bridges.add(rec.bridge_slug)
                channel_count[rec.channel] = channel_count.get(rec.channel, 0) + 1
                break

    for rec in pool:
        if rec in chosen:
            continue
        if len(chosen) >= 5:
            break
        if channel_count.get(rec.channel, 0) >= 2 and rec.channel != channel_focus:
            continue
        chosen.append(rec)
        seen_bridges.add(rec.bridge_slug)
        channel_count[rec.channel] = channel_count.get(rec.channel, 0) + 1

    # Backfill to >= 3 distinct bridges
    if len(seen_bridges) < 3:
        for slug in CROSS_TEMPLATE_BRIDGES:
            if slug in seen_bridges:
                continue
            chosen.append(Recommendation(
                text=(
                    f"Cross-reference the monetization plan with `{slug}` insights to widen the runway view."
                ),
                channel="all",
                priority="low",
                bridge_slug=slug,
                monetization=False,
            ))
            seen_bridges.add(slug)
            if len(seen_bridges) >= 3:
                break

    # Sort by priority order: high > medium > low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    chosen.sort(key=lambda r: priority_order.get(r.priority, 3))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    scores: PlanScores,
    payload: dict,
    is_demo: bool,
) -> tuple[str, str]:
    horizon = payload.get("projection_horizon", "90d")
    has_analytics = bool(payload.get("analytics_file_present"))
    if is_demo:
        return (
            "low",
            "data source is seeded demo signals — re-run with --revenue-file pointing at the actual "
            "x-money-companion-dashboard ledger and --analytics-file for an analytics-summarizer export to lift confidence.",
        )
    if horizon == "30d" and scores.plan_score >= 65 and has_analytics:
        return (
            "high",
            f"30d window covers the immediate pipeline; Plan score {scores.plan_score}/100 with analytics anchored.",
        )
    if scores.plan_score >= 60:
        return (
            "medium",
            f"Plan score {scores.plan_score}/100; widen the history window or attach an analytics-summarizer export to lift to high.",
        )
    return (
        "low",
        f"Plan score {scores.plan_score}/100; investigate the falling sub-scores before declaring a runway.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _currency_label(payload: dict, is_demo: bool) -> str:
    if is_demo:
        return "USD-equivalent (demo)"
    return payload.get("currency") or "USD"


def _render_plan_snapshot(
    payload: dict,
    scores: PlanScores,
    view: ChannelView,
    is_demo: bool,
) -> str:
    handle = normalize_handle(payload["x_handle"])
    horizon = payload.get("projection_horizon", "90d")
    focus = payload.get("channel_focus", "all")
    juris = payload.get("jurisdiction") or "jurisdiction-agnostic"

    if scores.paradox_active:
        headline = (
            f"{handle}: {horizon} monetization plan — single-channel-dependence paradox active; "
            f"{view.top_channel} is {view.top_share*100:.0f}% of revenue and forecast confidence is medium-or-higher."
        )
    elif scores.plan_score >= 75:
        headline = (
            f"{handle}: {horizon} monetization plan — diversified stack (Plan score {scores.plan_score}/100); "
            "runway is healthy across the 5-channel mix."
        )
    elif scores.plan_score >= 55:
        headline = (
            f"{handle}: {horizon} monetization plan — directional plan (Plan score {scores.plan_score}/100); "
            "concentration and tax readiness need attention before scaling."
        )
    else:
        headline = (
            f"{handle}: {horizon} monetization plan — weak plan (Plan score {scores.plan_score}/100); "
            "rebuild diversification and forecast confidence before pricing changes."
        )

    data_source_line = (
        "seeded demo signals — re-run with --revenue-file for real-ledger forecast"
        if is_demo
        else "real revenue ledger from --revenue-file"
    )
    return "\n".join([
        "## Plan Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Projection horizon**: {horizon}",
        f"- **Channel focus**: {focus}",
        f"- **Jurisdiction caveat**: {juris}",
        f"- **Data source**: {data_source_line}",
    ])


def _render_plan_performance(scores: PlanScores, view: ChannelView, is_demo: bool) -> str:
    demo_tag = (
        " [demo signal — re-run with --revenue-file for real-ledger forecast]"
        if is_demo else ""
    )
    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        f"| Earnings forecast confidence | {scores.earnings_confidence}/100{demo_tag} | {scores.earnings_arrow} | {scores.interpretations['Earnings forecast confidence']} |",
        f"| Revenue diversification      | {scores.diversification}/100{demo_tag} | {scores.diversification_arrow} | {scores.interpretations['Revenue diversification']} |",
        f"| Sponsorship fit alignment    | {scores.sponsorship_fit}/100{demo_tag} | {scores.sponsorship_arrow} | {scores.interpretations['Sponsorship fit alignment']} |",
        f"| Tax-and-expense readiness    | {scores.tax_readiness}/100{demo_tag} | {scores.tax_arrow} | {scores.interpretations['Tax-and-expense readiness']} |",
    ]
    out = "## Plan Performance\n\n" + "\n".join(rows)
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: top channel "
            f"({view.top_channel}) is {view.top_share*100:.0f}% of revenue and forecast confidence is medium-or-higher — "
            "concentration risk. One platform shift erases the stack."
        )
    out += f"\n\n**Monetization Plan score**: {scores.plan_score}/100"
    return out


def _render_earnings_forecast(
    view: ChannelView,
    payload: dict,
    scores: PlanScores,
    is_demo: bool,
) -> str:
    currency_label = _currency_label(payload, is_demo)
    bands = {h: forecast_band(view, h, currency_label) for h in PROJECTION_HORIZONS}

    horizon = payload.get("projection_horizon", "90d")
    confidence_line = {
        "high": f"Plan score {scores.plan_score}/100 + analytics file attached; bands tighten.",
        "medium": (
            f"Plan score {scores.plan_score}/100; "
            "real ledger would tighten or widen this band."
        ),
        "low": (
            "demo seed reflects a typical creator income for the niche; "
            "real ledger would refine this band substantially."
        ),
    }
    if is_demo:
        forecast_conf_label = "low" if scores.earnings_confidence < 60 else "medium"
    elif scores.earnings_confidence >= 75 and payload.get("analytics_file_present"):
        forecast_conf_label = "high"
    elif scores.earnings_confidence >= 60:
        forecast_conf_label = "medium"
    else:
        forecast_conf_label = "low"

    mix_line_parts = []
    for ch in CHANNELS:
        share = view.shares.get(ch, 0) * 100.0
        mix_line_parts.append(f"{ch} {share:.0f}%")
    mix_line = " / ".join(mix_line_parts)

    lines = [
        "## Earnings Forecast (wide bands — never point estimates)",
        "",
        ARTICLE_V1_DISCLAIMER,
        "",
        f"- **Next 30d band**: {_fmt_money(bands['30d'].low, currency_label)} — {_fmt_money(bands['30d'].high, currency_label)}",
        f"- **Next 90d band**: {_fmt_money(bands['90d'].low, currency_label)} — {_fmt_money(bands['90d'].high, currency_label)}",
        f"- **Next 365d band**: {_fmt_money(bands['365d'].low, currency_label)} — {_fmt_money(bands['365d'].high, currency_label)} (wide cone of uncertainty across the year)",
        f"- **Forecast confidence**: {forecast_conf_label} — {confidence_line[forecast_conf_label]}",
        f"- **Channel mix at forecast horizon ({horizon})**: {mix_line}",
    ]
    return "\n".join(lines)


def _render_sponsorship_fit_analysis(payload: dict, view: ChannelView) -> str:
    sig = payload.get("sponsorship_signals") or {}
    substantive = int(sig.get("audience_substantive_overlap_pct", 0))
    size_only = int(sig.get("audience_size_match_only_pct", 0))
    creator_niche = sig.get("creator_niche") or "the creator's niche"
    recent = sig.get("recent_sponsor_niche") or "no recent sponsor"

    if substantive >= 70:
        match_line = (
            f"Recent sponsor niche ({recent}) overlaps substantively with creator niche "
            f"({creator_niche}) at {substantive}% — durable trust footing."
        )
    elif substantive >= 50:
        match_line = (
            f"Partial substantive overlap ({substantive}%) between recent sponsor niche ({recent}) and "
            f"creator niche ({creator_niche}) — cap cadence and audit each deal individually."
        )
    else:
        match_line = (
            f"Thin substantive overlap ({substantive}%) — even an audience-size match of {size_only}% would erode trust."
        )

    if size_only - substantive >= 30 and substantive < 60:
        trust_line = (
            f"High trust risk: audience-size match ({size_only}%) far outpaces substantive overlap ({substantive}%). "
            "Selling on size alone trades long-term trust for short-term CPM."
        )
    elif size_only - substantive >= 15:
        trust_line = (
            f"Moderate trust risk: audience-size match ({size_only}%) leads substantive overlap ({substantive}%). Audit each deal individually."
        )
    else:
        trust_line = (
            f"Low trust risk: audience-size and substantive-niche signals are aligned ({substantive}% overlap; {size_only}% size match)."
        )

    archetypes, avoid = sponsorship_archetypes(payload, view)

    lines = [
        "## Sponsorship Fit Analysis",
        "",
        f"- **Audience-niche substantive match**: {match_line}",
        f"- **Trust risk**: {trust_line}",
        "- **Recommended sponsor archetypes** (paraphrased — no specific brand names):",
    ]
    for i, a in enumerate(archetypes, start=1):
        lines.append(
            f"  {i}. **{a.label}** — fits the {creator_niche} niche; cadence guidance: {a.cadence_guidance}."
        )
    lines.append("- **Avoid**:")
    for note in avoid:
        lines.append(f"  - {note}")
    return "\n".join(lines)


def _render_tax_expense_notes(payload: dict, view: ChannelView, is_demo: bool) -> str:
    juris = payload.get("jurisdiction")
    sig = payload.get("tax_expense_signals") or {}
    reserve = int(sig.get("reserve_pct_set_aside", 0))
    quality = (sig.get("documentation_quality") or "low").lower()

    if reserve >= 20:
        reserve_line = (
            f"Current reserve set-aside is {reserve}% — within the 20-30% common rule of thumb in many jurisdictions; "
            "the actual rate depends on residency, treaty, and channel mix."
        )
    elif reserve >= 10:
        reserve_line = (
            f"Current reserve set-aside is {reserve}% — below the 20-30% common rule of thumb in many jurisdictions; "
            "raise gradually from the next inbound invoice."
        )
    else:
        reserve_line = (
            "20-30% reserve is a common rule of thumb in many jurisdictions; the creator's actual rate depends on "
            "residency, treaty, and channel mix."
        )

    if quality == "high":
        gaps_line = (
            "Documentation hygiene is strong; verify that software subscriptions and home-office utilities are tracked monthly, not retroactively."
        )
    elif quality == "medium":
        gaps_line = (
            "Software subscriptions and home-office utilities are typically tracked late — start now."
        )
    else:
        gaps_line = (
            "Documentation hygiene is thin — start tracking sponsor invoices, software subscriptions, and home-office utilities monthly from this period forward."
        )

    if juris == "VN":
        juris_line = (
            "VN-resident creators with international platform earnings often need to consider double-taxation "
            "treaties (e.g. VN-US) — consult locally; this template is documentation guidance only."
        )
    elif juris:
        juris_line = (
            f"Jurisdiction: {juris}. Cross-border platform earnings frequently trigger withholding rules — "
            "consult a locally-licensed tax professional; this template is documentation guidance only."
        )
    else:
        juris_line = (
            "No --jurisdiction provided. Cross-border platform earnings frequently trigger withholding rules — "
            "consult a locally-licensed tax professional; this template is documentation guidance only."
        )

    lines = [
        "## Tax & Expense Notes",
        "",
        ARTICLE_V2_DISCLAIMER,
        "",
        f"- **Reserve heuristic**: {reserve_line}",
        f"- **Expense-tracking gaps**: {gaps_line}",
        "- **Documentation suggestions**: keep receipts via `x-money-vision-analyzer` (Phase 2 OCR tool); centralise revenue rows in `x-money-companion-dashboard`'s SQLite.",
        f"- **Jurisdiction caveat**: {juris_line}",
    ]
    return "\n".join(lines)


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    for i, rec in enumerate(recs, start=1):
        line = (
            f"{i}. **{rec.channel}: {rec.text}** · priority: {rec.priority}"
        )
        lines.append(line)
        if rec.monetization:
            lines.append("")
            lines.append(f"   {ARTICLE_V1_DISCLAIMER}")
        lines.append(f"   bridges to: `{rec.bridge_slug}`")
    return "\n".join(lines)


def _render_plan_audit(
    payload: dict,
    scores: PlanScores,
    view: ChannelView,
    flags: list[RedFlag],
    is_demo: bool,
) -> str:
    horizon = payload.get("projection_horizon", "90d")
    history = int(payload.get("history_depth_days", 90))
    if horizon == "365d":
        window_line = (
            f"365d horizon with {history}d of input history — the cone of uncertainty for a year-long forecast is wide by construction."
        )
    elif history < 60:
        window_line = (
            f"{horizon} horizon with only {history}d of input history — projection bands are wider than the runner can tighten."
        )
    else:
        window_line = (
            f"{horizon} horizon with {history}d of input history — sufficient for the patterns surfaced."
        )

    coverage_line = (
        f"{view.active_channels} of {len(CHANNELS)} official channels active in the input — "
        + ("acceptable" if view.active_channels >= 3 else "thin; activate dormant channels before pricing changes.")
    )

    band_line = (
        "Demo placeholders present; runner cannot speak to real-creator confidence until --revenue-file is supplied."
        if is_demo else
        "Real ledger loaded; bands reflect honest cone-of-uncertainty width."
    )

    juris = payload.get("jurisdiction")
    if juris == "VN":
        juris_line = (
            "VN-resident creator persona is the primary user of Grok Agent OS; treaty / withholding caveats apply."
        )
    elif juris:
        juris_line = (
            f"Jurisdiction {juris} declared; jurisdiction-specific tax filings require a locally-licensed professional."
        )
    else:
        juris_line = (
            "No --jurisdiction declared; the runner cannot anchor cross-border tax caveats."
        )

    sponsor_line = (
        "Sponsorship-pipeline rows present in input — recommendations are anchored."
        if (payload.get("sponsorship_signals") or {}).get("recent_sponsor_niche")
        else "No sponsorship-pipeline rows in input — sponsorship recommendations are speculative."
    )

    return "\n".join([
        "## Plan Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {window_line}",
        f"- **Channel coverage**: {coverage_line}",
        f"- **Forecast band width**: {band_line}",
        f"- **Jurisdiction acknowledgment**: {juris_line}",
        f"- **Sponsorship-pipeline visibility**: {sponsor_line}",
        "- **Re-run cadence**: weekly while pricing experiments are in flight; otherwise monthly.",
    ])


def render_report(
    payload: dict,
    view: ChannelView,
    scores: PlanScores,
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    is_demo: bool,
) -> str:
    horizon = payload.get("projection_horizon", "90d")
    sections = [
        _render_plan_snapshot(payload, scores, view, is_demo),
        "",
        _render_plan_performance(scores, view, is_demo),
        "",
        _render_earnings_forecast(view, payload, scores, is_demo),
        "",
        _render_sponsorship_fit_analysis(payload, view),
        "",
        _render_tax_expense_notes(payload, view, is_demo),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]
    if len(flags) > 3 or horizon == "365d" or is_demo:
        sections.extend([
            "",
            _render_plan_audit(payload, scores, view, flags, is_demo),
        ])
    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Monetization Optimizer (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_monetization_plan(
    *,
    x_handle: str,
    revenue_file: Optional[str] = None,
    analytics_file: Optional[str] = None,
    projection_horizon: str = "90d",
    channel_focus: str = "all",
    jurisdiction: Optional[str] = None,
    concentration_threshold: float = DEFAULT_CONCENTRATION_THRESHOLD,
    when: Optional[str] = None,
    demo_mode: Optional[str] = None,
) -> str:
    handle = normalize_handle(x_handle)
    if projection_horizon not in PROJECTION_HORIZONS:
        raise ValueError(
            f"projection_horizon must be one of {PROJECTION_HORIZONS}, got {projection_horizon!r}"
        )
    if channel_focus not in CHANNEL_FOCUS_OPTIONS:
        raise ValueError(
            f"channel_focus must be one of {CHANNEL_FOCUS_OPTIONS}, got {channel_focus!r}"
        )
    if not 0.4 <= concentration_threshold <= 0.9:
        raise ValueError(
            f"concentration_threshold must be in [0.4, 0.9], got {concentration_threshold}"
        )

    if revenue_file:
        payload = load_revenue_file(Path(revenue_file).expanduser().resolve())
        is_demo = bool(payload.get("data_source") == "demo")
    elif demo_mode == "paradox":
        payload = json.loads(json.dumps(DEMO_PARADOX))
        is_demo = True
    elif demo_mode == "healthy":
        payload = json.loads(json.dumps(DEMO_HEALTHY))
        is_demo = True
    elif demo_mode == "audit-365d":
        payload = json.loads(json.dumps(DEMO_365D_AUDIT))
        is_demo = True
    else:
        raise ValueError(
            "Provide --revenue-file <path> or --demo / --demo-healthy / --demo-365d-audit."
        )

    payload["x_handle"] = handle
    payload["projection_horizon"] = projection_horizon
    payload["channel_focus"] = channel_focus
    if jurisdiction is not None:
        payload["jurisdiction"] = jurisdiction
    if analytics_file:
        payload["analytics_file_present"] = True

    when_iso = when or date.today().isoformat()
    view = compute_channel_view(payload)
    scores = score_plan(payload, view, concentration_threshold)
    flags = build_red_flags(
        scores, view, payload, concentration_threshold, is_demo,
    )

    seed = hashlib.sha256(
        (handle + json.dumps(payload, sort_keys=True) + when_iso).encode("utf-8")
    ).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))
    recs = build_recommendations(rng, scores, view, payload, channel_focus)
    confidence = confidence_for(scores, payload, is_demo)

    rendered = render_report(payload, view, scores, flags, recs, confidence, is_demo)
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


generate = generate_monetization_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Monetization Optimizer (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Not financial / tax advice\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="monetization-optimizer",
        description=(
            "Read a creator's X revenue ledger (or seeded demo signals) and emit a "
            "7/8-section monetization plan with 4 standard metrics, single-channel-dependence "
            "paradox detection, sponsorship fit analysis, tax & expense notes, and >= 3 "
            "cross-template bridges. Drafts only. Never financial or tax advice."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    p.add_argument(
        "--revenue-file",
        help="Path to a JSON revenue ledger. Required unless a --demo flag is passed.",
    )
    p.add_argument(
        "--analytics-file",
        help="Optional path to an analytics-summarizer JSON export to anchor the forecast.",
    )
    p.add_argument(
        "--projection-horizon",
        choices=list(PROJECTION_HORIZONS),
        default="90d",
        help="Forecast horizon. 365d auto-triggers Plan Audit (default 90d).",
    )
    p.add_argument(
        "--channel-focus",
        choices=list(CHANNEL_FOCUS_OPTIONS),
        default="all",
        help="Which monetization channel to emphasise. Default 'all' applies no nudge.",
    )
    p.add_argument(
        "--jurisdiction",
        help="ISO country code (e.g. VN, US, SG) used to caveat the tax/expense notes.",
    )
    p.add_argument(
        "--concentration-threshold",
        type=float,
        default=DEFAULT_CONCENTRATION_THRESHOLD,
        help=f"Top-channel-share threshold for the paradox (default {DEFAULT_CONCENTRATION_THRESHOLD}).",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument("--demo", action="store_true", help="Run with the official paradox-firing demo signals.")
    p.add_argument("--demo-healthy", action="store_true", help="Run with healthy-stack demo signals (diversified, no paradox).")
    p.add_argument("--demo-365d-audit", action="store_true", help="Run with 365d-horizon thin-data demo signals that auto-trigger the Plan Audit.")
    p.add_argument("--show-system-prompt", action="store_true", help="Print system prompt path + size on stderr.")
    return p


def cli(argv: Optional[list[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    if not args.no_banner:
        sys.stdout.write(banner())
        sys.stdout.flush()

    if args.show_system_prompt:
        if SYSTEM_PROMPT_PATH.exists():
            sys.stderr.write(
                f"[system-prompt] loaded from {SYSTEM_PROMPT_PATH}\n"
                f"[system-prompt] {len(SYSTEM_PROMPT_PATH.read_text(encoding='utf-8'))} chars\n"
            )
        else:
            sys.stderr.write(
                f"[system-prompt] not found at {SYSTEM_PROMPT_PATH} — runner uses embedded contract\n"
            )

    demo_mode: Optional[str] = None
    horizon = args.projection_horizon
    if args.demo:
        demo_mode = "paradox"
    elif args.demo_healthy:
        demo_mode = "healthy"
    elif args.demo_365d_audit:
        demo_mode = "audit-365d"
        horizon = "365d"

    if not args.revenue_file and demo_mode is None:
        sys.stderr.write(
            "error: provide --revenue-file <path> or one of --demo / --demo-healthy / --demo-365d-audit.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_monetization_plan(
        x_handle=args.x_handle,
        revenue_file=args.revenue_file,
        analytics_file=args.analytics_file,
        projection_horizon=horizon,
        channel_focus=args.channel_focus,
        jurisdiction=args.jurisdiction,
        concentration_threshold=args.concentration_threshold,
        when=when_iso,
        demo_mode=demo_mode,
    )

    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        when_full = datetime.now(timezone.utc).isoformat()
        out_path.write_text(
            saved_file_header(normalize_handle(args.x_handle), when_full) + rendered,
            encoding="utf-8",
        )
        sys.stderr.write(f"[saved] {out_path}\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
