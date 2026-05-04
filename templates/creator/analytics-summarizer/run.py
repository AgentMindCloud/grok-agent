# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Analytics Summarizer — runner.

CLI entry point for the ``analytics-summarizer`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied X analytics export (JSON) — or seeded demo
metrics when no file is provided — and emits the strict 7/8-section
period summary defined by the merged P83 system prompt:

  1. Period Snapshot
  2. Period Performance (4-row metric table + weighted score)
  3. Top-Performing Content (3-5 paraphrased archetypes)
  4. Trends (rising / stable / falling buckets)
  5. Red Flags (2-3, surfaces vanity-metric paradox in BOTH places)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Confidence
  + Optional Period Audit (auto-appended when red_flags > 3 OR
    time_range='7d')

Hard guarantees enforced by this runner (mirrors the P83 system prompt):

* Drafts only. The runner emits text the creator reads; never
  auto-publishes anywhere.
* No fabricated statistics. The runner does not invent p-values or
  confidence intervals. Demo metrics carry an explicit
  `[demo metric — re-run with --metrics-file for real X data]` label
  so the creator never confuses the demo for their actual analytics.
* Vanity-metric paradox surfaced in BOTH the Period Performance
  section AND the Red Flags section whenever Impressions delta > +20%
  AND Engagement rate < 2.5% (the niche baseline; configurable via
  --engagement-baseline).
* Period Performance score formula is fixed:
    round(0.30*Engagement_rate_norm + 0.30*Impressions_delta_norm +
          0.25*Follower_delta_norm + 0.15*Content_velocity_norm).
* 5-arrow trend vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼) with ±5% / ±25%
  thresholds vs the comparison basis.
* Top-Performing Content archetypes are paraphrased categories
  supplied by the creator (or demo defaults); never raw URLs unless
  the metrics file explicitly contains them.
* >= 3 distinct cross-template slugs in the Recommendations.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + metrics +
  time_range + date).
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_analytics_summary

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

SCORE_METRICS = (
    "Impressions delta",
    "Engagement rate",
    "Follower delta",
    "Content velocity",
)

# Per the P83 system prompt: Engagement and Impressions tied at 0.30 each
# because either failing alone defeats the period; Content velocity
# weighted lowest because cadence is the most-gameable signal.
PERFORMANCE_WEIGHTS = {
    "Engagement rate": 0.30,
    "Impressions delta": 0.30,
    "Follower delta": 0.25,
    "Content velocity": 0.15,
}

METRIC_FOCUS_OPTIONS = ("impressions", "engagement", "reach", "all")
TIME_RANGE_OPTIONS = ("7d", "30d", "90d")
COMPARE_OPTIONS = ("previous_period", "benchmark")

# 5-arrow trend bucketing thresholds (% change vs comparison basis)
TREND_THRESHOLDS = {
    "strong_rise": 25.0,
    "rise": 5.0,
    "fall": -5.0,
    "strong_fall": -25.0,
}

# Vanity-metric paradox: Impressions delta > +20% AND Engagement rate
# < 2.5% (default niche baseline).
PARADOX_IMPRESSIONS_THRESHOLD = 20.0
DEFAULT_ENGAGEMENT_BASELINE_PCT = 2.5

CROSS_TEMPLATE_BRIDGES = (
    "content-idea-generator",
    "thread-builder",
    "reply-drafter",
    "monetization-optimizer",
    "ab-test-suggester",
    "competitor-watch",
    "brand-voice-trainer",
    "cross-platform-reposter",
    "content-recycler",
    "comment-engagement-booster",
    "hashtag-strategy-advisor",
    "follower-quality-analyzer",
    "research-assistant",
)

ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

# Demo metrics — explicitly labelled so the creator never confuses them
# for real data. Three demo modes, one per acceptance-criteria example.
DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "time_range": "30d",
    "compare_to": "previous_period",
    "metric_focus": "all",
    "data_source": "demo",
    "current_period": {
        "impressions": 152000,
        "engagements": 2710,
        "follower_delta_pct": 1.2,
        "posts_per_week": 5,
    },
    "previous_period": {
        "impressions": 113000,
        "engagements": 2375,
        "follower_delta_pct": 0.9,
        "posts_per_week": 5,
    },
    "top_content": [
        {
            "archetype_label": "Long-form thread on agent-eval failure modes",
            "format": "thread",
            "impression_share_pct": 60,
            "engagement_rate_pct": 1.4,
        },
        {
            "archetype_label": "Quote-tweet riff on niche peer's case study",
            "format": "quote-tweet",
            "impression_share_pct": 12,
            "engagement_rate_pct": 3.8,
        },
        {
            "archetype_label": "Numbers-led explainer on benchmark drift",
            "format": "single-post",
            "impression_share_pct": 8,
            "engagement_rate_pct": 4.2,
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "time_range": "30d",
    "compare_to": "previous_period",
    "metric_focus": "all",
    "data_source": "demo",
    "current_period": {
        "impressions": 96500,
        "engagements": 5500,
        "follower_delta_pct": 3.2,
        "posts_per_week": 5,
    },
    "previous_period": {
        "impressions": 84000,
        "engagements": 4200,
        "follower_delta_pct": 2.4,
        "posts_per_week": 4,
    },
    "top_content": [
        {
            "archetype_label": "Personal-anecdote thread on evening-friction audits",
            "format": "thread",
            "impression_share_pct": 38,
            "engagement_rate_pct": 6.8,
        },
        {
            "archetype_label": "Habit-stacking case study with concrete numbers",
            "format": "single-post",
            "impression_share_pct": 22,
            "engagement_rate_pct": 7.4,
        },
        {
            "archetype_label": "Reply-thread on deep-work shutdown rituals",
            "format": "reply",
            "impression_share_pct": 14,
            "engagement_rate_pct": 5.9,
        },
    ],
}

DEMO_7D_AUDIT = {
    "x_handle": "@JanSol0s",
    "time_range": "7d",
    "compare_to": "previous_period",
    "metric_focus": "engagement",
    "data_source": "demo",
    "current_period": {
        "impressions": 38000,
        "engagements": 1100,
        "follower_delta_pct": 0.4,
        "posts_per_week": 6,
    },
    "previous_period": {
        "impressions": 41000,
        "engagements": 1280,
        "follower_delta_pct": 0.6,
        "posts_per_week": 5,
    },
    "top_content": [
        {
            "archetype_label": "Mid-week long-form thread on infra tooling",
            "format": "thread",
            "impression_share_pct": 42,
            "engagement_rate_pct": 3.1,
        },
        {
            "archetype_label": "Quote-tweet rally on a niche launch",
            "format": "quote-tweet",
            "impression_share_pct": 18,
            "engagement_rate_pct": 2.7,
        },
        {
            "archetype_label": "Numbers post (small sample, single-day spike)",
            "format": "single-post",
            "impression_share_pct": 11,
            "engagement_rate_pct": 4.0,
        },
    ],
}

_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,15}(?![A-Za-z0-9_])"
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PeriodMetrics:
    impressions_delta_pct: float
    engagement_rate_pct: float
    follower_delta_pct: float
    posts_per_week: float


@dataclass
class PerformanceScores:
    impressions_delta_pct: float
    engagement_rate_pct: float
    follower_delta_pct: float
    posts_per_week: float
    impressions_arrow: str
    engagement_arrow: str
    follower_arrow: str
    velocity_arrow: str
    period_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)


@dataclass
class TopContent:
    archetype_label: str
    format: str
    impression_share_pct: float
    engagement_rate_pct: float


@dataclass
class RedFlag:
    title: str
    severity: str
    explanation: str
    remediation: str


@dataclass
class Recommendation:
    text: str
    bridge_slug: str
    monetization: bool = False


# ---------------------------------------------------------------------------
# Privacy guard (only the creator's handle in body)
# ---------------------------------------------------------------------------


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Analytics Summarizer privacy violation: a non-creator X handle "
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


def load_metrics_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"--metrics-file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"--metrics-file is not valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_metrics(payload: dict) -> PeriodMetrics:
    cur = payload["current_period"]
    prev = payload["previous_period"]

    cur_imp = float(cur["impressions"])
    prev_imp = float(prev["impressions"]) if prev["impressions"] else 1.0
    impressions_delta_pct = ((cur_imp - prev_imp) / prev_imp) * 100.0

    cur_eng = float(cur["engagements"])
    engagement_rate_pct = (cur_eng / cur_imp) * 100.0 if cur_imp > 0 else 0.0

    follower_delta_pct = float(cur["follower_delta_pct"])
    posts_per_week = float(cur["posts_per_week"])

    return PeriodMetrics(
        impressions_delta_pct=impressions_delta_pct,
        engagement_rate_pct=engagement_rate_pct,
        follower_delta_pct=follower_delta_pct,
        posts_per_week=posts_per_week,
    )


def trend_arrow(value_pct: float) -> str:
    """5-arrow bucketing per the P83 system prompt thresholds."""
    if value_pct >= TREND_THRESHOLDS["strong_rise"]:
        return "▲▲"
    if value_pct >= TREND_THRESHOLDS["rise"]:
        return "▲"
    if value_pct >= TREND_THRESHOLDS["fall"]:
        return "▬"
    if value_pct >= TREND_THRESHOLDS["strong_fall"]:
        return "▼"
    return "▼▼"


def follower_trend_arrow(value_pct: float) -> str:
    """Follower delta uses tighter thresholds: a +1% follower gain in
    30 days is genuinely rising for a creator. Map the absolute follower
    delta to arrow vocabulary with smaller bands."""
    if value_pct >= 5.0:
        return "▲▲"
    if value_pct >= 1.0:
        return "▲"
    if value_pct >= -0.5:
        return "▬"
    if value_pct >= -3.0:
        return "▼"
    return "▼▼"


def velocity_trend_arrow(current: float, previous: float) -> str:
    if previous <= 0:
        return "▬"
    delta_pct = ((current - previous) / previous) * 100.0
    return trend_arrow(delta_pct)


# ---------------------------------------------------------------------------
# Normalised sub-scores → weighted Period Performance score
# ---------------------------------------------------------------------------


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    n = (value - lo) / (hi - lo) * 100.0
    return max(0.0, min(100.0, n))


def normalize_metrics(metrics: PeriodMetrics) -> dict:
    # Healthy ranges from the P83 system prompt:
    #   Impressions delta -10% .. +50%
    #   Engagement rate    1.5% .. 5.0%
    #   Follower delta    +0.5% .. +5.0%
    #   Content velocity  3 .. 7 posts/week
    return {
        "Impressions delta": _norm(metrics.impressions_delta_pct, -10.0, 50.0),
        "Engagement rate": _norm(metrics.engagement_rate_pct, 1.5, 5.0),
        "Follower delta": _norm(metrics.follower_delta_pct, 0.5, 5.0),
        "Content velocity": _norm(metrics.posts_per_week, 3.0, 7.0),
    }


def score_period(
    metrics: PeriodMetrics,
    payload: dict,
    engagement_baseline_pct: float,
) -> PerformanceScores:
    norm = normalize_metrics(metrics)
    score = round(
        PERFORMANCE_WEIGHTS["Engagement rate"] * norm["Engagement rate"]
        + PERFORMANCE_WEIGHTS["Impressions delta"] * norm["Impressions delta"]
        + PERFORMANCE_WEIGHTS["Follower delta"] * norm["Follower delta"]
        + PERFORMANCE_WEIGHTS["Content velocity"] * norm["Content velocity"]
    )

    paradox = (
        metrics.impressions_delta_pct > PARADOX_IMPRESSIONS_THRESHOLD
        and metrics.engagement_rate_pct < engagement_baseline_pct
    )

    prev_velocity = float(payload["previous_period"]["posts_per_week"])

    return PerformanceScores(
        impressions_delta_pct=metrics.impressions_delta_pct,
        engagement_rate_pct=metrics.engagement_rate_pct,
        follower_delta_pct=metrics.follower_delta_pct,
        posts_per_week=metrics.posts_per_week,
        impressions_arrow=trend_arrow(metrics.impressions_delta_pct),
        engagement_arrow=trend_arrow(
            (metrics.engagement_rate_pct - engagement_baseline_pct) / max(engagement_baseline_pct, 0.1) * 100.0
        ),
        follower_arrow=follower_trend_arrow(metrics.follower_delta_pct),
        velocity_arrow=velocity_trend_arrow(metrics.posts_per_week, prev_velocity),
        period_score=score,
        paradox_active=paradox,
        interpretations=_metric_interpretations(metrics, engagement_baseline_pct),
    )


def _metric_interpretations(
    m: PeriodMetrics, baseline_pct: float,
) -> dict:
    out = {}
    # Impressions
    if m.impressions_delta_pct >= 25:
        out["Impressions delta"] = (
            "Strong rise — verify the spike is from the creator's primary niche, not a one-off viral hit."
        )
    elif m.impressions_delta_pct >= 5:
        out["Impressions delta"] = "Rising; the trend supports the current cadence."
    elif m.impressions_delta_pct >= -5:
        out["Impressions delta"] = "Stable vs the comparison basis; no cadence change needed."
    elif m.impressions_delta_pct >= -25:
        out["Impressions delta"] = "Falling; check whether the prior period had a viral outlier."
    else:
        out["Impressions delta"] = "Strong fall; investigate algorithm reach changes or content shift."

    # Engagement
    if m.engagement_rate_pct >= baseline_pct * 1.5:
        out["Engagement rate"] = (
            f"Well above the {baseline_pct}% niche baseline; substantive interaction is real."
        )
    elif m.engagement_rate_pct >= baseline_pct:
        out["Engagement rate"] = (
            f"At or just above the {baseline_pct}% niche baseline; healthy."
        )
    else:
        out["Engagement rate"] = (
            f"Below the {baseline_pct}% niche baseline; reach attracted drive-bys, not niche peers."
        )

    # Follower delta
    if m.follower_delta_pct >= 3:
        out["Follower delta"] = "Strong follower growth; verify quality before scaling outreach."
    elif m.follower_delta_pct >= 1:
        out["Follower delta"] = "Healthy net positive; tracks the broader engagement signal."
    elif m.follower_delta_pct >= -0.5:
        out["Follower delta"] = "Net flat; no growth-decline alarm but no progress either."
    else:
        out["Follower delta"] = "Net negative; audit recent posts for off-niche cadence."

    # Content velocity
    if m.posts_per_week >= 7:
        out["Content velocity"] = "Above the healthy 3-7 band; check for cadence-fatigue signals."
    elif m.posts_per_week >= 3:
        out["Content velocity"] = "Inside the healthy 3-7 band; cadence is not the bottleneck."
    else:
        out["Content velocity"] = "Below the healthy 3-7 band; ramp slowly to 4-5 posts/week."

    return out


# ---------------------------------------------------------------------------
# Top-performing content
# ---------------------------------------------------------------------------


def parse_top_content(payload: dict) -> list[TopContent]:
    raw = payload.get("top_content", [])
    out: list[TopContent] = []
    for entry in raw[:5]:
        out.append(TopContent(
            archetype_label=str(entry.get("archetype_label", "(unlabelled archetype)")),
            format=str(entry.get("format", "single-post")),
            impression_share_pct=float(entry.get("impression_share_pct", 0)),
            engagement_rate_pct=float(entry.get("engagement_rate_pct", 0)),
        ))
    return out


# ---------------------------------------------------------------------------
# Trends bucketing
# ---------------------------------------------------------------------------


def bucket_trends(scores: PerformanceScores) -> tuple[list[str], list[str], list[str]]:
    rising: list[str] = []
    stable: list[str] = []
    falling: list[str] = []
    pairs = (
        ("Impressions delta", scores.impressions_arrow),
        ("Engagement rate", scores.engagement_arrow),
        ("Follower delta", scores.follower_arrow),
        ("Content velocity", scores.velocity_arrow),
    )
    for name, arrow in pairs:
        if arrow in ("▲▲", "▲"):
            rising.append(f"{name} ({arrow})")
        elif arrow == "▬":
            stable.append(f"{name} ({arrow})")
        else:
            falling.append(f"{name} ({arrow})")
    return rising, stable, falling


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: PerformanceScores,
    payload: dict,
    engagement_baseline_pct: float,
    time_range: str,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: vanity-metric paradox
    if scores.paradox_active:
        flags.append(RedFlag(
            title="Vanity-metric paradox",
            severity="high",
            explanation=(
                f"Impressions delta at +{scores.impressions_delta_pct:.0f}% sits above the "
                f"+{int(PARADOX_IMPRESSIONS_THRESHOLD)}% threshold while Engagement rate at "
                f"{scores.engagement_rate_pct:.1f}% is below the {engagement_baseline_pct}% niche "
                "baseline. Reach attracted drive-bys, not niche peers."
            ),
            remediation=(
                "Inspect which post drove the spike; if it is not in the creator's primary niche, "
                "accept the period as a reach-only win and retarget next period for engagement."
            ),
        ))

    # Rule 2: follower-quality watch (positive follower delta paired with paradox)
    if scores.paradox_active and scores.follower_delta_pct > 0.5:
        flags.append(RedFlag(
            title="Follower-quality watch",
            severity="medium",
            explanation=(
                f"Net-positive follower delta ({scores.follower_delta_pct:+.1f}%) is tracking the "
                "impressions spike, suggesting new followers came from the viral surface."
            ),
            remediation=(
                "Vet the new cohort via `follower-quality-analyzer` before assuming the period grew the right audience."
            ),
        ))

    # Rule 3: 7-day single-day variance
    if time_range == "7d":
        flags.append(RedFlag(
            title="Single-day variance exposure",
            severity="medium",
            explanation=(
                "A 7d window is dominated by single-day variance; one viral or one quiet day "
                "can flip every trend arrow."
            ),
            remediation=(
                "Re-run with `--time-range 30d` once 14+ more days have passed before declaring directional reads."
            ),
        ))

    # Rule 4: cadence-fatigue watch (high posts_per_week + falling impressions)
    if scores.posts_per_week > 7 and scores.impressions_arrow in ("▼", "▼▼"):
        flags.append(RedFlag(
            title="Cadence-fatigue watch",
            severity="medium",
            explanation=(
                f"Posting cadence {scores.posts_per_week:.1f} posts/week is above the healthy 3-7 "
                "band while impressions are falling — likely cadence fatigue."
            ),
            remediation=(
                "Drop cadence to 4-5 posts/week and re-measure in 30d; pair with `competitor-watch` to spot peers."
            ),
        ))

    # Rule 5: declining engagement on stable cadence
    if (
        not scores.paradox_active
        and scores.engagement_arrow in ("▼", "▼▼")
        and scores.velocity_arrow == "▬"
    ):
        flags.append(RedFlag(
            title="Engagement decline on stable cadence",
            severity="medium",
            explanation=(
                f"Engagement rate {scores.engagement_rate_pct:.1f}% is falling vs baseline while "
                "cadence stayed flat — voice or topic drift is the most likely cause."
            ),
            remediation=(
                "Pair with `brand-voice-trainer` to confirm voice is steady; with `competitor-watch` to spot niche shifts."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-period read",
            severity="low",
            explanation=(
                "One period is directional, not conclusive. Treat the score as a snapshot, not a trend."
            ),
            remediation=(
                "Snapshot monthly via `analytics-summarizer` to build a real baseline of trend arrows."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: PerformanceScores,
    top: list[TopContent],
    metric_focus: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # 1. Re-source from highest-engagement archetype
    if top:
        winner = max(top, key=lambda c: c.engagement_rate_pct)
        pool.append(Recommendation(
            text=(
                f"Re-source the next anchor in the cluster of \"{winner.archetype_label}\" "
                f"({winner.engagement_rate_pct:.1f}% engagement rate)."
            ),
            bridge_slug="content-idea-generator",
        ))

    # 2. Build a long-form thread that earns the audience the period attracted
    pool.append(Recommendation(
        text=(
            "Build the long-form thread that earns the audience this period attracted; "
            "match the dominant winning format."
        ),
        bridge_slug="thread-builder",
    ))

    # 3. Engage with the audience the period brought in
    pool.append(Recommendation(
        text=(
            "Reply substantively to the highest-quality replies the period generated; voice-faithful only."
        ),
        bridge_slug="reply-drafter",
    ))

    # 4. Vet new follower cohort if paradox or strong follower delta
    if scores.paradox_active or scores.follower_delta_pct >= 3:
        pool.append(Recommendation(
            text=(
                "Vet the new follower cohort before assuming the period grew the right audience."
            ),
            bridge_slug="follower-quality-analyzer",
        ))

    # 5. Compare against competitors
    pool.append(Recommendation(
        text=(
            "Compare the period's metric mix against competitor patterns to confirm the read isn't niche-narrow."
        ),
        bridge_slug="competitor-watch",
    ))

    # 6. Monetization (V.1 disclaimer)
    if scores.engagement_rate_pct >= 3.0 and scores.follower_delta_pct >= 1.0:
        pool.append(Recommendation(
            text=(
                "If the period's engagement supports a paid-tier test, model the funnel before shipping."
            ),
            bridge_slug="monetization-optimizer",
            monetization=True,
        ))

    # 7. AB test the winning format
    if top:
        pool.append(Recommendation(
            text=(
                "Promote the winning archetype into a structured 2-week A/B against an alternate format."
            ),
            bridge_slug="ab-test-suggester",
        ))

    rng.shuffle(pool)
    chosen: list[Recommendation] = []
    seen: set[str] = set()
    for rec in pool:
        if len(chosen) >= 5:
            break
        chosen.append(rec)
        seen.add(rec.bridge_slug)

    if len(seen) < 3:
        for slug in CROSS_TEMPLATE_BRIDGES:
            if slug not in seen:
                chosen[-1] = Recommendation(
                    text=(
                        "Cross-reference the analytics with brand-voice signatures to spot voice-drift."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(Recommendation(
            text="Re-run with a longer time-range to lift confidence.",
            bridge_slug="research-assistant",
        ))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    scores: PerformanceScores,
    time_range: str,
    is_demo: bool,
) -> tuple[str, str]:
    if is_demo:
        return (
            "low",
            f"data source is seeded demo metrics — re-run with --metrics-file pointing at the actual X analytics export to lift confidence.",
        )
    if time_range == "30d" and scores.period_score >= 65:
        return (
            "high",
            f"30d window covers the main signals; Period Performance score {scores.period_score}/100.",
        )
    if scores.period_score >= 50:
        return (
            "medium",
            f"Period Performance score {scores.period_score}/100; widen the window or supply richer top-content data to lift to high.",
        )
    return (
        "low",
        f"Period Performance score {scores.period_score}/100; investigate the falling metrics before declaring a trend.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_period_snapshot(
    payload: dict, scores: PerformanceScores, is_demo: bool,
) -> str:
    handle = normalize_handle(payload["x_handle"])
    if scores.paradox_active:
        headline = (
            f"{handle}: {payload['time_range']} period vs {payload['compare_to']} — "
            "vanity-metric paradox active; reach spiked but engagement is below the niche baseline."
        )
    elif scores.period_score >= 70:
        headline = (
            f"{handle}: {payload['time_range']} period vs {payload['compare_to']} — "
            f"strong period (Period Performance {scores.period_score}/100)."
        )
    elif scores.period_score >= 50:
        headline = (
            f"{handle}: {payload['time_range']} period vs {payload['compare_to']} — "
            f"directional period (Period Performance {scores.period_score}/100)."
        )
    else:
        headline = (
            f"{handle}: {payload['time_range']} period vs {payload['compare_to']} — "
            "weak period; investigate falling metrics before scaling cadence."
        )
    data_source_line = (
        "seeded demo metrics — re-run with --metrics-file for real X data"
        if is_demo
        else "real X export from --metrics-file"
    )
    return "\n".join([
        "## Period Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Time range**: {payload['time_range']}",
        f"- **Comparison basis**: {payload['compare_to']}",
        f"- **Metric focus**: {payload.get('metric_focus', 'all')}",
        f"- **Data source**: {data_source_line}",
    ])


def _render_period_performance(scores: PerformanceScores, is_demo: bool) -> str:
    demo_tag = (
        " [demo metric — re-run with --metrics-file for real X data]"
        if is_demo else ""
    )
    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        f"| Impressions delta | {scores.impressions_delta_pct:+.1f}%{demo_tag} | {scores.impressions_arrow} | {scores.interpretations['Impressions delta']} |",
        f"| Engagement rate   | {scores.engagement_rate_pct:.1f}%{demo_tag} | {scores.engagement_arrow} | {scores.interpretations['Engagement rate']} |",
        f"| Follower delta    | {scores.follower_delta_pct:+.1f}%{demo_tag} | {scores.follower_arrow} | {scores.interpretations['Follower delta']} |",
        f"| Content velocity  | {scores.posts_per_week:.1f} posts/week{demo_tag} | {scores.velocity_arrow} | {scores.interpretations['Content velocity']} |",
    ]
    out = "## Period Performance\n\n" + "\n".join(rows)
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: impressions spiked but engagement is below the niche "
            "baseline — vanity reach without substantive interaction."
        )
    out += f"\n\n**Period Performance score**: {scores.period_score}/100"
    return out


def _render_top_content(top: list[TopContent]) -> str:
    if not top:
        return (
            "## Top-Performing Content (paraphrased — no raw URLs unless supplied)\n\n"
            "_(no top-content data supplied; pass `top_content[]` in --metrics-file to populate this section)_"
        )
    lines = ["## Top-Performing Content (paraphrased — no raw URLs unless supplied)", ""]
    for i, c in enumerate(top, start=1):
        lines.append(
            f"{i}. **{c.archetype_label}** — {c.format}; drove {c.impression_share_pct:.0f}% of period impressions "
            f"with {c.engagement_rate_pct:.1f}% engagement rate."
        )
    return "\n".join(lines)


def _render_trends(scores: PerformanceScores) -> str:
    rising, stable, falling = bucket_trends(scores)
    return "\n".join([
        "## Trends",
        "",
        f"- **Rising (▲▲ / ▲)**: {', '.join(rising) if rising else 'none'}.",
        f"- **Stable (▬)**: {', '.join(stable) if stable else 'none'}.",
        f"- **Falling (▼ / ▼▼)**: {', '.join(falling) if falling else 'none'}.",
    ])


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    monetization_emitted = False
    for i, rec in enumerate(recs, start=1):
        line = f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`"
        if rec.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    return "\n".join(lines)


def _render_period_audit(
    payload: dict, scores: PerformanceScores, flags: list[RedFlag], is_demo: bool,
) -> str:
    window_line = (
        "7d window is dominated by single-day variance; treat all reads as directional."
        if payload["time_range"] == "7d"
        else f"{payload['time_range']} window is sufficient for the patterns surfaced."
    )
    data_line = (
        "seeded demo placeholders — runner cannot speak to real-creator confidence until --metrics-file is supplied."
        if is_demo else "real metrics file loaded; runner has no missing-field gaps."
    )
    return "\n".join([
        "## Period Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {window_line}",
        f"- **Data source confidence**: {data_line}",
        f"- **Single-day variance exposure**: {'high (7d window)' if payload['time_range'] == '7d' else 'low (30d+ window absorbs variance)'}.",
        "- **Suggested next sample**: re-run when 14+ more days have passed; widen to 30d if currently on 7d.",
        "- **Re-run cadence**: weekly while building the analytics habit, otherwise monthly.",
    ])


def render_report(
    payload: dict,
    scores: PerformanceScores,
    top: list[TopContent],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    is_demo: bool,
) -> str:
    sections = [
        _render_period_snapshot(payload, scores, is_demo),
        "",
        _render_period_performance(scores, is_demo),
        "",
        _render_top_content(top),
        "",
        _render_trends(scores),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    if len(flags) > 3 or payload["time_range"] == "7d":
        sections.extend([
            "",
            _render_period_audit(payload, scores, flags, is_demo),
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
        f"<!-- Generated by Analytics Summarizer (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_analytics_summary(
    *,
    x_handle: str,
    metrics_file: Optional[str] = None,
    metric_focus: str = "all",
    time_range: str = "30d",
    compare_to: str = "previous_period",
    engagement_baseline_pct: float = DEFAULT_ENGAGEMENT_BASELINE_PCT,
    when: Optional[str] = None,
    demo_mode: Optional[str] = None,
) -> str:
    handle = normalize_handle(x_handle)
    if metric_focus not in METRIC_FOCUS_OPTIONS:
        raise ValueError(f"metric_focus must be one of {METRIC_FOCUS_OPTIONS}, got {metric_focus!r}")
    if time_range not in TIME_RANGE_OPTIONS:
        raise ValueError(f"time_range must be one of {TIME_RANGE_OPTIONS}, got {time_range!r}")
    if compare_to not in COMPARE_OPTIONS:
        raise ValueError(f"compare_to must be one of {COMPARE_OPTIONS}, got {compare_to!r}")

    if metrics_file:
        payload = load_metrics_file(Path(metrics_file).expanduser().resolve())
        is_demo = bool(payload.get("data_source") == "demo")
    elif demo_mode == "paradox":
        payload = json.loads(json.dumps(DEMO_PARADOX))
        is_demo = True
    elif demo_mode == "healthy":
        payload = json.loads(json.dumps(DEMO_HEALTHY))
        is_demo = True
    elif demo_mode == "audit-7d":
        payload = json.loads(json.dumps(DEMO_7D_AUDIT))
        is_demo = True
    else:
        raise ValueError(
            "Provide --metrics-file <path> or --demo / --demo-healthy / --demo-7d-audit."
        )

    # Override payload meta with caller intent (CLI flags win over demo defaults)
    payload["x_handle"] = handle
    payload["time_range"] = time_range
    payload["compare_to"] = compare_to
    payload["metric_focus"] = metric_focus

    when_iso = when or date.today().isoformat()
    metrics = compute_metrics(payload)
    scores = score_period(metrics, payload, engagement_baseline_pct)
    top = parse_top_content(payload)
    flags = build_red_flags(scores, payload, engagement_baseline_pct, time_range)

    seed = hashlib.sha256(
        (handle + json.dumps(payload, sort_keys=True) + when_iso).encode("utf-8")
    ).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))
    recs = build_recommendations(rng, scores, top, metric_focus)
    confidence = confidence_for(scores, time_range, is_demo)

    rendered = render_report(payload, scores, top, flags, recs, confidence, is_demo)
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


generate = generate_analytics_summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Analytics Summarizer (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · No fabricated stats\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="analytics-summarizer",
        description=(
            "Read creator-supplied X analytics (or seeded demo metrics) and emit a "
            "7/8-section period summary with 4 canonical metrics, vanity-metric "
            "paradox detection, and >= 3 cross-template bridges. Drafts only."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    p.add_argument(
        "--metrics-file",
        help="Path to a JSON metrics export. Required unless a --demo flag is passed.",
    )
    p.add_argument(
        "--metric-focus",
        choices=list(METRIC_FOCUS_OPTIONS),
        default="all",
        help="Which canonical metric to emphasise. Default 'all' applies no nudge.",
    )
    p.add_argument(
        "--time-range",
        choices=list(TIME_RANGE_OPTIONS),
        default="30d",
        help="Period covered by the summary. 7d auto-triggers Period Audit.",
    )
    p.add_argument(
        "--compare-to",
        choices=list(COMPARE_OPTIONS),
        default="previous_period",
        help="Comparison basis for delta calculation. Default previous_period.",
    )
    p.add_argument(
        "--engagement-baseline",
        type=float,
        default=DEFAULT_ENGAGEMENT_BASELINE_PCT,
        help=f"Engagement-rate niche baseline in percent (default {DEFAULT_ENGAGEMENT_BASELINE_PCT}).",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument("--demo", action="store_true", help="Run with the canonical paradox-firing demo metrics.")
    p.add_argument("--demo-healthy", action="store_true", help="Run with healthy growth demo metrics.")
    p.add_argument("--demo-7d-audit", action="store_true", help="Run with 7d-window demo metrics that auto-trigger the Period Audit.")
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
    if args.demo:
        demo_mode = "paradox"
    elif args.demo_healthy:
        demo_mode = "healthy"
    elif args.demo_7d_audit:
        demo_mode = "audit-7d"

    if not args.metrics_file and demo_mode is None:
        sys.stderr.write(
            "error: provide --metrics-file <path> or one of --demo / --demo-healthy / --demo-7d-audit.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_analytics_summary(
        x_handle=args.x_handle,
        metrics_file=args.metrics_file,
        metric_focus=args.metric_focus,
        time_range=args.time_range,
        compare_to=args.compare_to,
        engagement_baseline_pct=args.engagement_baseline,
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
