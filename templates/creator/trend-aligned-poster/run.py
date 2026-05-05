# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Trend-Aligned Poster — runner.

CLI entry point for the ``trend-aligned-poster`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads creator-supplied X trend data (JSON) — or seeded demo trends
when no file is provided — and emits the strict 7/8-section trend-
aligned post plan defined by the system prompt:

  1. Trend Snapshot
  2. Trend Alignment Plan Score (4-row metric table + weighted score)
  3. Trend Watchlist (3-5 paraphrased trends)
  4. Post Ideas (4-6 entries, off-niche excluded)
  5. Red Flags (2-4, surfaces trend-chasing paradox + off-niche guard)
  6. Recommendations (3-5, mandatory bridges to content-idea-generator
     and thread-builder)
  7. Confidence
  + Optional Trend Audit (auto-appended when window=7d, off-niche
    guard fires, or every trend in the watchlist is stale)

Hard guarantees enforced by this runner (mirrors the system prompt):

* Drafts only — never auto-publishes.
* No fabricated statistics. Demo trend velocity and engagement bands
  carry an explicit `[demo trend — re-run with --trends-file for
  real X data]` label.
* Trend-chasing paradox surfaced in BOTH the Plan Score section AND
  the Red Flags section whenever average Trend match > 75 AND
  average Niche fit < niche_fit_floor (default 40).
* Off-niche guard: any idea with trend_match >= 75 AND niche_fit < 40
  is excluded from Post Ideas and consolidated as a single Red Flag.
* Plan Score formula is fixed:
    round(0.30*TrendMatch_norm + 0.25*NicheFit_norm +
          0.25*Voice_norm + 0.20*Originality_norm).
* 5-arrow trend vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼).
* Unconditional bridges to content-idea-generator (position 1) and
  thread-builder (position 2) in every Recommendations list.
* Privacy-first: source-post handles, raw trend post text, attachment
  URLs, and external links are never echoed.
* No finance / cashtag / sponsorship / harassment content.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic: seeded by sha256(handle + trends + window + date).
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_trend_aligned_post_plan

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
    "Trend match strength",
    "Niche fit",
    "Voice fidelity",
    "Originality",
)

# Per the system prompt: Trend match weighted highest because the template's
# core job is trend alignment; Niche fit weighted equal-second because
# chasing off-niche trends is exactly how creators dilute audience.
PLAN_SCORE_WEIGHTS = {
    "Trend match strength": 0.30,
    "Niche fit": 0.25,
    "Voice fidelity": 0.25,
    "Originality": 0.20,
}

# Healthy-range bounds used to normalise each metric to a 0-100 sub-score.
HEALTHY_RANGES = {
    "Trend match strength": (50.0, 85.0),
    "Niche fit": (60.0, 95.0),
    "Voice fidelity": (65.0, 95.0),
    "Originality": (50.0, 90.0),
}

WINDOW_OPTIONS = (7, 30, 90)
COMPARE_OPTIONS = ("previous_period", "benchmark")

# 5-arrow trend bucketing thresholds (relative + absolute on 0-100).
TREND_THRESHOLDS = {
    "strong_rise_pct": 25.0,
    "strong_rise_pts": 15.0,
    "rise_pct": 5.0,
    "rise_pts": 5.0,
    "fall_pct": -5.0,
    "fall_pts": -5.0,
    "strong_fall_pct": -25.0,
    "strong_fall_pts": -15.0,
}

# Trend-chasing paradox: avg Trend match > 75 AND avg Niche fit < floor.
PARADOX_TREND_MATCH_THRESHOLD = 75.0
DEFAULT_NICHE_FIT_FLOOR = 40.0

# Off-niche idea-level guard: trend_match >= 75 AND niche_fit < 40.
OFFNICHE_TRENDMATCH_THRESHOLD = 75.0
OFFNICHE_NICHEFIT_THRESHOLD = 40.0

# Post Ideas count is clamped to [4, 6] after off-niche filter.
IDEA_COUNT_MIN = 4
IDEA_COUNT_MAX = 6
DEFAULT_TARGET_IDEA_COUNT = 5

VALID_FORMATS = ("single", "thread", "quote-tweet", "image-post", "reply-thread")
ENGAGEMENT_BANDS = ("low", "medium", "high", "breakout")
VELOCITY_VALUES = ("accelerating", "steady", "decaying", "stale")
NICHE_FIT_VALUES = ("tight", "adjacent", "loose", "off")

CROSS_TEMPLATE_BRIDGES = (
    "content-idea-generator",   # mandatory position 1
    "thread-builder",           # mandatory position 2
    "hashtag-strategy-advisor",
    "ab-test-suggester",
    "comment-engagement-booster",
    "brand-voice-trainer",
    "analytics-summarizer",
    "mention-summarizer",
    "dm-triager",
    "competitor-watch",
    "cross-platform-reposter",
    "content-recycler",
)

MANDATORY_BRIDGES = ("content-idea-generator", "thread-builder")

DEMO_LABEL = "[demo trend — re-run with --trends-file for real X data]"

# ---------------------------------------------------------------------------
# Demo data — paradox + off-niche guard firing
# ---------------------------------------------------------------------------

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "window": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "niche_label": "ai-agents + creator-tools",
    "trends": [
        {
            "trend_paraphrase": "celebrity-led debate on the day's top news cycle",
            "velocity": "accelerating",
            "niche_fit_label": "off",
            "hours_old": 6,
        },
        {
            "trend_paraphrase": "viral consumer-app meme with no enterprise angle",
            "velocity": "accelerating",
            "niche_fit_label": "loose",
            "hours_old": 10,
        },
        {
            "trend_paraphrase": "open-source agent eval framework crossing benchmark thresholds",
            "velocity": "steady",
            "niche_fit_label": "tight",
            "hours_old": 18,
        },
        {
            "trend_paraphrase": "thread genre about agent-failure post-mortems gaining traction",
            "velocity": "steady",
            "niche_fit_label": "adjacent",
            "hours_old": 30,
        },
        {
            "trend_paraphrase": "quote-tweet wave riffing on a peer benchmark publication",
            "velocity": "decaying",
            "niche_fit_label": "tight",
            "hours_old": 22,
        },
    ],
    "candidate_ideas": [
        # 7 off-niche trend-chasers — these will fail the off-niche guard
        # AND drag the period averages into paradox territory (avg NF < 40).
        {
            "format": "single",
            "trend_tag": "celebrity-news-cycle",
            "copy_outline": "react to the top news headline with a punchy take",
            "trend_match_score": 92,
            "niche_fit_score": 8,
            "voice_fidelity_score": 65,
            "originality_score": 28,
        },
        {
            "format": "quote-tweet",
            "trend_tag": "viral-consumer-meme",
            "copy_outline": "quote the viral consumer-app meme with a brand-tilted angle",
            "trend_match_score": 88,
            "niche_fit_score": 12,
            "voice_fidelity_score": 60,
            "originality_score": 30,
        },
        {
            "format": "single",
            "trend_tag": "celebrity-news-cycle",
            "copy_outline": "react to the second day's news cycle with a hot take",
            "trend_match_score": 95,
            "niche_fit_score": 5,
            "voice_fidelity_score": 55,
            "originality_score": 25,
        },
        {
            "format": "quote-tweet",
            "trend_tag": "off-niche-sports-clip",
            "copy_outline": "quote a sports highlight with a 'productivity lesson' angle",
            "trend_match_score": 85,
            "niche_fit_score": 15,
            "voice_fidelity_score": 58,
            "originality_score": 30,
        },
        {
            "format": "image-post",
            "trend_tag": "viral-consumer-meme",
            "copy_outline": "lift the viral meme template with a generic creator caption",
            "trend_match_score": 82,
            "niche_fit_score": 10,
            "voice_fidelity_score": 50,
            "originality_score": 22,
        },
        {
            "format": "single",
            "trend_tag": "off-niche-pop-culture",
            "copy_outline": "comment on the pop culture controversy of the week",
            "trend_match_score": 80,
            "niche_fit_score": 18,
            "voice_fidelity_score": 60,
            "originality_score": 35,
        },
        {
            "format": "quote-tweet",
            "trend_tag": "celebrity-news-cycle",
            "copy_outline": "quote a celeb post and shoehorn a creator-tools angle",
            "trend_match_score": 78,
            "niche_fit_score": 16,
            "voice_fidelity_score": 55,
            "originality_score": 28,
        },
        # 4 on-niche ideas — these survive the off-niche guard and fill
        # the Post Ideas section.
        {
            "format": "thread",
            "trend_tag": "agent-eval-benchmark",
            "copy_outline": "walk through the eval framework's contribution and where it falls short",
            "trend_match_score": 72,
            "niche_fit_score": 88,
            "voice_fidelity_score": 82,
            "originality_score": 70,
        },
        {
            "format": "single",
            "trend_tag": "agent-failure-post-mortem",
            "copy_outline": "share a one-paragraph post-mortem from a recent build with the lesson up front",
            "trend_match_score": 70,
            "niche_fit_score": 90,
            "voice_fidelity_score": 80,
            "originality_score": 75,
        },
        {
            "format": "quote-tweet",
            "trend_tag": "peer-benchmark-publication",
            "copy_outline": "quote a paraphrased peer benchmark and add the missing context the chart elides",
            "trend_match_score": 68,
            "niche_fit_score": 82,
            "voice_fidelity_score": 78,
            "originality_score": 65,
        },
        {
            "format": "reply-thread",
            "trend_tag": "agent-failure-post-mortem",
            "copy_outline": "reply to two niche peers' threads with concrete failure-mode counter-examples",
            "trend_match_score": 65,
            "niche_fit_score": 80,
            "voice_fidelity_score": 78,
            "originality_score": 60,
        },
    ],
    "previous_window_summary": {
        "avg_trend_match_score": 64.0,
        "avg_niche_fit_score": 70.0,
        "avg_voice_fidelity_score": 76.0,
        "avg_originality_score": 68.0,
    },
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "window": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "niche_label": "habit-design + behavioural-engineering",
    "trends": [
        {
            "trend_paraphrase": "morning-routine debate trending across productivity feed",
            "velocity": "accelerating",
            "niche_fit_label": "tight",
            "hours_old": 5,
        },
        {
            "trend_paraphrase": "evening-friction audits format gaining steady volume",
            "velocity": "steady",
            "niche_fit_label": "tight",
            "hours_old": 14,
        },
        {
            "trend_paraphrase": "habit-stacking case-study format with concrete numbers",
            "velocity": "steady",
            "niche_fit_label": "tight",
            "hours_old": 20,
        },
        {
            "trend_paraphrase": "behaviour-design framework debate among researchers and writers",
            "velocity": "accelerating",
            "niche_fit_label": "adjacent",
            "hours_old": 8,
        },
    ],
    "candidate_ideas": [
        {
            "format": "thread",
            "trend_tag": "morning-routine-debate",
            "copy_outline": "five-tweet thread on why most morning routines fail at the friction-audit step",
            "trend_match_score": 78,
            "niche_fit_score": 88,
            "voice_fidelity_score": 84,
            "originality_score": 76,
        },
        {
            "format": "single",
            "trend_tag": "evening-friction-audit",
            "copy_outline": "single post sharing a one-week evening-friction audit with the smallest fix that worked",
            "trend_match_score": 72,
            "niche_fit_score": 90,
            "voice_fidelity_score": 86,
            "originality_score": 78,
        },
        {
            "format": "thread",
            "trend_tag": "habit-stacking-case-study",
            "copy_outline": "case-study thread with measured retention numbers from a three-month stack",
            "trend_match_score": 74,
            "niche_fit_score": 92,
            "voice_fidelity_score": 88,
            "originality_score": 80,
        },
        {
            "format": "quote-tweet",
            "trend_tag": "behaviour-design-debate",
            "copy_outline": "quote a paraphrased researcher post and add the practitioner-side counter-experience",
            "trend_match_score": 65,
            "niche_fit_score": 80,
            "voice_fidelity_score": 82,
            "originality_score": 70,
        },
        {
            "format": "image-post",
            "trend_tag": "evening-friction-audit",
            "copy_outline": "share a creator-drawn diagram of the friction-audit loop",
            "trend_match_score": 60,
            "niche_fit_score": 82,
            "voice_fidelity_score": 80,
            "originality_score": 72,
        },
    ],
    "previous_window_summary": {
        "avg_trend_match_score": 64.0,
        "avg_niche_fit_score": 84.0,
        "avg_voice_fidelity_score": 82.0,
        "avg_originality_score": 74.0,
    },
}

DEMO_7D_AUDIT = {
    "x_handle": "@thindata",
    "window": 7,
    "compare_to": "previous_period",
    "data_source": "demo",
    "niche_label": "applied-ml + research-tooling",
    "trends": [
        {
            "trend_paraphrase": "research-paper interpretation thread on a two-day-old finding",
            "velocity": "decaying",
            "niche_fit_label": "tight",
            "hours_old": 30,
        },
        {
            "trend_paraphrase": "tooling launch from an adjacent niche with limited overlap",
            "velocity": "stale",
            "niche_fit_label": "adjacent",
            "hours_old": 40,
        },
        {
            "trend_paraphrase": "podcast clip resharing a familiar argument",
            "velocity": "stale",
            "niche_fit_label": "adjacent",
            "hours_old": 56,
        },
    ],
    "candidate_ideas": [
        {
            "format": "thread",
            "trend_tag": "research-paper-interpretation",
            "copy_outline": "thread interpreting the paper's headline result in plain language",
            "trend_match_score": 60,
            "niche_fit_score": 78,
            "voice_fidelity_score": 78,
            "originality_score": 60,
        },
        {
            "format": "single",
            "trend_tag": "research-paper-interpretation",
            "copy_outline": "single post calling out the under-discussed limitation in the paper's evaluation",
            "trend_match_score": 58,
            "niche_fit_score": 80,
            "voice_fidelity_score": 76,
            "originality_score": 66,
        },
        {
            "format": "quote-tweet",
            "trend_tag": "tooling-launch",
            "copy_outline": "quote a paraphrased launch announcement and surface the missing benchmark angle",
            "trend_match_score": 52,
            "niche_fit_score": 70,
            "voice_fidelity_score": 74,
            "originality_score": 58,
        },
        {
            "format": "reply-thread",
            "trend_tag": "research-paper-interpretation",
            "copy_outline": "reply on three peer threads with the unaddressed methodological angle",
            "trend_match_score": 50,
            "niche_fit_score": 76,
            "voice_fidelity_score": 75,
            "originality_score": 55,
        },
    ],
    "previous_window_summary": {
        "avg_trend_match_score": 58.0,
        "avg_niche_fit_score": 72.0,
        "avg_voice_fidelity_score": 76.0,
        "avg_originality_score": 60.0,
    },
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TrendAlignedPosterError(RuntimeError):
    """Raised for any creator-facing input or guard failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_handle(raw: str) -> str:
    handle = raw.strip().lstrip("@")
    if not handle:
        raise TrendAlignedPosterError("x_handle is required and cannot be empty.")
    if " " in handle or len(handle) > 15:
        raise TrendAlignedPosterError(
            f"x_handle {raw!r} is invalid — X handles are at most 15 chars, no spaces."
        )
    return f"@{handle}"


def _seed_from(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _utcnow_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalise_metric(value: float, metric: str) -> float:
    """Project a raw 0-100 metric into its healthy-range sub-score."""
    low, high = HEALTHY_RANGES[metric]
    if high <= low:
        return 0.0
    norm = (value - low) / (high - low) * 100.0
    return max(0.0, min(100.0, norm))


def _arrow_for_delta(curr: float, prev: float) -> str:
    if prev <= 0:
        # Treat absolute change as the only signal when prev is 0.
        delta_pts = curr - prev
        if delta_pts >= TREND_THRESHOLDS["strong_rise_pts"]:
            return "▲▲"
        if delta_pts >= TREND_THRESHOLDS["rise_pts"]:
            return "▲"
        if delta_pts <= TREND_THRESHOLDS["strong_fall_pts"]:
            return "▼▼"
        if delta_pts <= TREND_THRESHOLDS["fall_pts"]:
            return "▼"
        return "▬"
    pct = (curr - prev) / prev * 100.0
    pts = curr - prev
    if pct >= TREND_THRESHOLDS["strong_rise_pct"] or pts >= TREND_THRESHOLDS["strong_rise_pts"]:
        return "▲▲"
    if pct >= TREND_THRESHOLDS["rise_pct"] or pts >= TREND_THRESHOLDS["rise_pts"]:
        return "▲"
    if pct <= TREND_THRESHOLDS["strong_fall_pct"] or pts <= TREND_THRESHOLDS["strong_fall_pts"]:
        return "▼▼"
    if pct <= TREND_THRESHOLDS["fall_pct"] or pts <= TREND_THRESHOLDS["fall_pts"]:
        return "▼"
    return "▬"


def _engagement_band_for(trend_match: float, niche_fit: float, voice: float) -> str:
    """Predicted engagement band for a single idea."""
    composite = 0.5 * trend_match + 0.3 * niche_fit + 0.2 * voice
    if composite >= 88:
        return "breakout"
    if composite >= 70:
        return "high"
    if composite >= 55:
        return "medium"
    return "low"


def _validate_window(window: int) -> int:
    if window not in WINDOW_OPTIONS:
        raise TrendAlignedPosterError(
            f"window={window!r} is invalid — choose one of {WINDOW_OPTIONS}."
        )
    return window


def _validate_compare(compare_to: str) -> str:
    if compare_to not in COMPARE_OPTIONS:
        raise TrendAlignedPosterError(
            f"compare_to={compare_to!r} is invalid — choose one of {COMPARE_OPTIONS}."
        )
    return compare_to


def _clamp_target_count(target: int) -> int:
    return max(IDEA_COUNT_MIN, min(IDEA_COUNT_MAX, int(target)))


# ---------------------------------------------------------------------------
# Forbidden-content scanner
# ---------------------------------------------------------------------------

# Per the system prompt + manifest hard refusals: refuse cashtag /
# investment / sponsored / harassment content. The scan is conservative
# and runs over the trend paraphrases AND idea copy outlines.
FORBIDDEN_PATTERNS = (
    re.compile(r"\$[A-Z]{2,5}\b"),                  # cashtag / ticker
    re.compile(r"\b(buy|sell|long|short)\s+\$"),    # trading hints
    re.compile(r"\b(invest(ment)?|portfolio|hedge)\b", re.I),
    re.compile(r"\b(sponsor(ed|ship)?|paid\s+promotion|\#ad)\b", re.I),
    re.compile(r"\b(harass|defame|dox|slur)\w*\b", re.I),
)


def _scan_forbidden(text: str) -> list[str]:
    flagged: list[str] = []
    for pat in FORBIDDEN_PATTERNS:
        m = pat.search(text)
        if m:
            flagged.append(m.group(0))
    return flagged


def _refuse_if_forbidden(label: str, text: str) -> None:
    flagged = _scan_forbidden(text)
    if flagged:
        raise TrendAlignedPosterError(
            f"refusing {label}: forbidden token(s) {flagged!r} (cashtag / "
            "investment / sponsorship / harassment content is not generated by this template)"
        )


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


@dataclass
class TrendInput:
    x_handle: str
    window: int
    compare_to: str
    niche_fit_floor: float
    target_idea_count: int
    niche_label: str
    data_source: str  # "real" | "demo"
    trends: list[dict]
    candidate_ideas: list[dict]
    previous_window_summary: dict
    trends_file: Optional[str] = None


def _load_demo(mode: str) -> dict:
    if mode == "paradox":
        return json.loads(json.dumps(DEMO_PARADOX))
    if mode == "healthy":
        return json.loads(json.dumps(DEMO_HEALTHY))
    if mode == "7d-audit":
        return json.loads(json.dumps(DEMO_7D_AUDIT))
    raise TrendAlignedPosterError(f"unknown demo mode {mode!r}")


def _validate_trend(t: dict, idx: int) -> dict:
    required = ("trend_paraphrase", "velocity", "niche_fit_label", "hours_old")
    missing = [k for k in required if k not in t]
    if missing:
        raise TrendAlignedPosterError(f"trend[{idx}] missing keys: {missing}")
    if t["velocity"] not in VELOCITY_VALUES:
        raise TrendAlignedPosterError(
            f"trend[{idx}].velocity={t['velocity']!r} invalid — choose {VELOCITY_VALUES}"
        )
    if t["niche_fit_label"] not in NICHE_FIT_VALUES:
        raise TrendAlignedPosterError(
            f"trend[{idx}].niche_fit_label={t['niche_fit_label']!r} invalid — choose {NICHE_FIT_VALUES}"
        )
    _refuse_if_forbidden(f"trend[{idx}]", str(t.get("trend_paraphrase", "")))
    return t


def _validate_idea(i: dict, idx: int) -> dict:
    required = (
        "format", "trend_tag", "copy_outline",
        "trend_match_score", "niche_fit_score",
        "voice_fidelity_score", "originality_score",
    )
    missing = [k for k in required if k not in i]
    if missing:
        raise TrendAlignedPosterError(f"idea[{idx}] missing keys: {missing}")
    if i["format"] not in VALID_FORMATS:
        raise TrendAlignedPosterError(
            f"idea[{idx}].format={i['format']!r} invalid — choose {VALID_FORMATS}"
        )
    for score_key in (
        "trend_match_score", "niche_fit_score",
        "voice_fidelity_score", "originality_score",
    ):
        v = i[score_key]
        if not isinstance(v, (int, float)):
            raise TrendAlignedPosterError(
                f"idea[{idx}].{score_key} must be a number; got {type(v).__name__}"
            )
        if v < 0 or v > 100:
            raise TrendAlignedPosterError(
                f"idea[{idx}].{score_key}={v} outside 0-100"
            )
    _refuse_if_forbidden(f"idea[{idx}]", str(i.get("copy_outline", "")))
    _refuse_if_forbidden(f"idea[{idx}].trend_tag", str(i.get("trend_tag", "")))
    return i


def _validate_input(payload: dict, args: argparse.Namespace) -> TrendInput:
    handle = _normalise_handle(payload.get("x_handle", args.x_handle or ""))
    window = _validate_window(int(payload.get("window", args.window)))
    compare_to = _validate_compare(payload.get("compare_to", args.compare_to))
    niche_label = (payload.get("niche_label") or "general creator").strip()[:80]
    data_source = payload.get("data_source", "real")
    if data_source not in ("real", "demo"):
        raise TrendAlignedPosterError(
            f"data_source={data_source!r} invalid — choose 'real' or 'demo'"
        )
    trends_raw = payload.get("trends") or []
    if not (3 <= len(trends_raw) <= 8):
        raise TrendAlignedPosterError(
            f"trends count {len(trends_raw)} outside 3..8 — please supply 3-8 trends"
        )
    trends = [_validate_trend(t, i) for i, t in enumerate(trends_raw)]
    ideas_raw = payload.get("candidate_ideas") or []
    if len(ideas_raw) < IDEA_COUNT_MIN:
        raise TrendAlignedPosterError(
            f"candidate_ideas count {len(ideas_raw)} below floor {IDEA_COUNT_MIN}"
        )
    ideas = [_validate_idea(i, idx) for idx, i in enumerate(ideas_raw)]

    return TrendInput(
        x_handle=handle,
        window=window,
        compare_to=compare_to,
        niche_fit_floor=float(args.niche_fit_floor),
        target_idea_count=_clamp_target_count(args.target_idea_count),
        niche_label=niche_label,
        data_source=data_source,
        trends=trends,
        candidate_ideas=ideas,
        previous_window_summary=payload.get("previous_window_summary") or {},
        trends_file=str(args.trends_file) if args.trends_file else None,
    )


# ---------------------------------------------------------------------------
# Off-niche guard + scoring
# ---------------------------------------------------------------------------


@dataclass
class IdeaScore:
    raw: dict
    excluded: bool
    excluded_reason: Optional[str]
    engagement_band: str


@dataclass
class PlanScore:
    metric_values: dict
    metric_arrows: dict
    plan_score: int
    paradox_active: bool
    avg_trend_match: float
    avg_niche_fit: float


def _is_off_niche(idea: dict) -> bool:
    return (
        idea["trend_match_score"] >= OFFNICHE_TRENDMATCH_THRESHOLD
        and idea["niche_fit_score"] < OFFNICHE_NICHEFIT_THRESHOLD
    )


def _apply_off_niche_guard(ideas: list[dict]) -> tuple[list[IdeaScore], int]:
    """Return (annotated, excluded_count). The excluded ideas are kept in
    the list for audit but flagged so the renderer drops them from the
    Post Ideas section."""
    annotated: list[IdeaScore] = []
    excluded = 0
    for i in ideas:
        if _is_off_niche(i):
            annotated.append(
                IdeaScore(
                    raw=i,
                    excluded=True,
                    excluded_reason=(
                        f"trend_match {i['trend_match_score']:.0f} ≥ 75 AND "
                        f"niche_fit {i['niche_fit_score']:.0f} < 40"
                    ),
                    engagement_band="low",
                )
            )
            excluded += 1
        else:
            band = _engagement_band_for(
                i["trend_match_score"],
                i["niche_fit_score"],
                i["voice_fidelity_score"],
            )
            annotated.append(
                IdeaScore(raw=i, excluded=False, excluded_reason=None, engagement_band=band)
            )
    return annotated, excluded


def _select_post_ideas(
    annotated: list[IdeaScore], target: int
) -> list[IdeaScore]:
    eligible = [a for a in annotated if not a.excluded]
    eligible.sort(
        key=lambda a: (
            -a.raw["trend_match_score"],
            -a.raw["niche_fit_score"],
            -a.raw["originality_score"],
        )
    )
    n = max(IDEA_COUNT_MIN, min(target, IDEA_COUNT_MAX, len(eligible)))
    return eligible[:n]


def _avg(items: list[float]) -> float:
    if not items:
        return 0.0
    return sum(items) / len(items)


def _compute_plan_score(
    annotated: list[IdeaScore], niche_fit_floor: float
) -> PlanScore:
    # Per the system prompt the Plan Score reflects the full candidate
    # pool — the off-niche guard filters which ideas appear in the Post
    # Ideas SECTION, but the score must surface the period's overall
    # trend-chasing tendency. Otherwise the guard would silently mask
    # the paradox the creator most needs to see.
    pool = annotated

    tm = _avg([a.raw["trend_match_score"] for a in pool])
    nf = _avg([a.raw["niche_fit_score"] for a in pool])
    vf = _avg([a.raw["voice_fidelity_score"] for a in pool])
    org = _avg([a.raw["originality_score"] for a in pool])

    metric_values = {
        "Trend match strength": round(tm, 1),
        "Niche fit": round(nf, 1),
        "Voice fidelity": round(vf, 1),
        "Originality": round(org, 1),
    }

    norms = {
        "Trend match strength": _normalise_metric(tm, "Trend match strength"),
        "Niche fit": _normalise_metric(nf, "Niche fit"),
        "Voice fidelity": _normalise_metric(vf, "Voice fidelity"),
        "Originality": _normalise_metric(org, "Originality"),
    }
    plan = round(
        PLAN_SCORE_WEIGHTS["Trend match strength"] * norms["Trend match strength"]
        + PLAN_SCORE_WEIGHTS["Niche fit"] * norms["Niche fit"]
        + PLAN_SCORE_WEIGHTS["Voice fidelity"] * norms["Voice fidelity"]
        + PLAN_SCORE_WEIGHTS["Originality"] * norms["Originality"]
    )

    paradox = (tm > PARADOX_TREND_MATCH_THRESHOLD) and (nf < niche_fit_floor)

    return PlanScore(
        metric_values=metric_values,
        metric_arrows={},  # filled in by the renderer using compare basis
        plan_score=plan,
        paradox_active=paradox,
        avg_trend_match=tm,
        avg_niche_fit=nf,
    )


def _arrows_against_basis(score: PlanScore, prev: dict) -> dict:
    """Compute 5-arrow buckets against the comparison basis."""
    return {
        "Trend match strength": _arrow_for_delta(
            score.metric_values["Trend match strength"],
            float(prev.get("avg_trend_match_score", score.metric_values["Trend match strength"])),
        ),
        "Niche fit": _arrow_for_delta(
            score.metric_values["Niche fit"],
            float(prev.get("avg_niche_fit_score", score.metric_values["Niche fit"])),
        ),
        "Voice fidelity": _arrow_for_delta(
            score.metric_values["Voice fidelity"],
            float(prev.get("avg_voice_fidelity_score", score.metric_values["Voice fidelity"])),
        ),
        "Originality": _arrow_for_delta(
            score.metric_values["Originality"],
            float(prev.get("avg_originality_score", score.metric_values["Originality"])),
        ),
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _demo_suffix(data_source: str) -> str:
    return f" {DEMO_LABEL}" if data_source == "demo" else ""


def _interpretation_for(metric: str, value: float, arrow: str, paradox: bool, niche_fit_floor: float) -> str:
    if metric == "Trend match strength":
        if paradox and value > PARADOX_TREND_MATCH_THRESHOLD:
            return "High match — but verify niche fit before treating the score as a quality signal."
        if value > 85:
            return "Trend coverage is strong; monitor for over-saturation in the next window."
        if value > 50:
            return "Trend match in healthy range — within the band where niche fit dominates outcome."
        return "Trend match below 50 — most ideas would launch into thin trend volume."
    if metric == "Niche fit":
        if value < niche_fit_floor:
            return f"Below the {int(niche_fit_floor)} floor; ideas chase virality at the cost of audience focus."
        if value > 95:
            return "Tight niche alignment — every idea reads as on-brand for the audience."
        if value > 60:
            return "Niche fit in healthy range — ideas hold the audience the prior window built."
        return "Niche fit between 40 and 60 — borderline; one stronger filter would lift outcomes."
    if metric == "Voice fidelity":
        if value > 95:
            return "Exceptional voice match — verify it isn't hiding generic-polish."
        if value > 65:
            return "Inside the healthy band; copy outlines preserve the creator's tone."
        return "Voice fidelity below the floor — drafts read flat; brand-voice-trainer should re-anchor before posting."
    if metric == "Originality":
        if value > 90:
            return "High originality — guard against sounding contrarian-for-its-own-sake."
        if value > 50:
            return "Originality acceptable — paired with niche fit, this is the core healthy band."
        return "Borderline — trend-chasing tends to homogenise voice; raise the originality bar before posting."
    return ""


def _render_snapshot(inp: TrendInput, score: PlanScore) -> str:
    headline_bits = [f"{inp.window}d trend window"]
    if score.paradox_active:
        headline_bits.append(
            f"trend-chasing paradox active; Trend match strength {score.avg_trend_match:.1f} but Niche fit only {score.avg_niche_fit:.1f}"
        )
    else:
        headline_bits.append(
            f"plan score {score.plan_score}/100; niche fit holding at {score.avg_niche_fit:.1f}"
        )
    headline = f"**{inp.x_handle}: " + " — ".join(headline_bits) + ".**"

    if inp.data_source == "demo":
        ds = "seeded demo trends — re-run with --trends-file for real X data"
    else:
        ds = f"real X export from --trends-file {inp.trends_file}"

    body = [
        "## Trend Snapshot",
        headline,
        "",
        f"- **Creator handle**: {inp.x_handle}",
        f"- **Window**: {inp.window}d",
        f"- **Comparison basis**: {inp.compare_to}",
        f"- **Niche label**: {inp.niche_label}",
        f"- **Data source**: {ds}",
    ]
    return "\n".join(body)


def _render_plan_score(inp: TrendInput, score: PlanScore, arrows: dict) -> str:
    lines = [
        "## Trend Alignment Plan Score",
        "",
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    for metric in SCORE_METRICS:
        v = score.metric_values[metric]
        arrow = arrows[metric]
        interp = _interpretation_for(
            metric, v, arrow, score.paradox_active, inp.niche_fit_floor
        )
        lines.append(f"| {metric} | {v}/100{suffix} | {arrow} | {interp} |")
    if score.paradox_active:
        lines.append("")
        lines.append(
            "> ⚠️ paradox: trend match is high but niche fit is below the floor — "
            "the plan would inflate volume by chasing off-niche virality and dilute "
            "the creator's audience over time."
        )
    lines.append("")
    lines.append(f"**Trend Alignment Plan Score**: {score.plan_score}/100")
    return "\n".join(lines)


def _render_watchlist(inp: TrendInput) -> str:
    lines = [
        "## Trend Watchlist",
        "",
        "| Trend (paraphrased) | Velocity | Niche fit |",
        "|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    # Take 3-5 trends, sorted: tight/adjacent first, then by velocity, then by recency.
    trends = list(inp.trends)
    fit_rank = {"tight": 0, "adjacent": 1, "loose": 2, "off": 3}
    vel_rank = {"accelerating": 0, "steady": 1, "decaying": 2, "stale": 3}
    trends.sort(
        key=lambda t: (
            fit_rank.get(t["niche_fit_label"], 9),
            vel_rank.get(t["velocity"], 9),
            t.get("hours_old", 0),
        )
    )
    take = min(5, max(3, len(trends)))
    for t in trends[:take]:
        is_stale = t["velocity"] == "stale" or (
            t.get("hours_old", 0) > 24 and t["velocity"] != "accelerating"
        )
        para = t["trend_paraphrase"]
        if suffix:
            para = f"{para}{suffix}"
        if is_stale:
            para += " — informational only — do not drive idea generation"
        lines.append(f"| {para} | {t['velocity']} | {t['niche_fit_label']} |")
    return "\n".join(lines)


def _render_post_ideas(inp: TrendInput, selected: list[IdeaScore], excluded_count: int, total_candidates: int) -> str:
    note = ""
    if excluded_count > 0:
        note = f" — {excluded_count} off-niche trend-chaser(s) excluded — see Red Flags"
    header = f"## Post Ideas ({len(selected)} of {total_candidates} candidate ideas{note})"
    lines = [header, ""]
    suffix = _demo_suffix(inp.data_source)
    for n, sc in enumerate(selected, start=1):
        idea = sc.raw
        bridge = (
            "thread-builder" if idea["format"] == "thread" else "content-idea-generator"
        )
        lines.append(
            f"{n}. **{idea['format']}** · trend: `{idea['trend_tag']}` — {idea['copy_outline']}"
        )
        lines.append(
            f"   trend match: {idea['trend_match_score']:.0f}{suffix} · "
            f"engagement: {sc.engagement_band} · bridges to: `{bridge}`"
        )
    return "\n".join(lines)


def _render_red_flags(
    score: PlanScore,
    excluded_count: int,
    inp: TrendInput,
    annotated: list[IdeaScore],
) -> tuple[str, list[str]]:
    flags: list[tuple[str, str, str, str]] = []  # (title, severity, line, remediation)

    if score.paradox_active:
        flags.append((
            "Trend-chasing paradox",
            "high",
            (
                f"Average trend match {score.avg_trend_match:.1f} > 75 while "
                f"average niche fit {score.avg_niche_fit:.1f} < {int(inp.niche_fit_floor)} floor "
                "— posting now would inflate volume by chasing off-niche virality."
            ),
            (
                "Tighten the trend filter to niche-relevant only for the next window, "
                "OR accept the period as a quiet-trend stretch and wait for niche-aligned trends "
                "before posting."
            ),
        ))

    if excluded_count > 0:
        excluded_ideas = [a for a in annotated if a.excluded]
        gap_text = "; ".join(
            f"trend_match {a.raw['trend_match_score']:.0f} vs niche_fit {a.raw['niche_fit_score']:.0f}"
            for a in excluded_ideas[:3]
        )
        flags.append((
            "Off-niche trend-chasers excluded",
            "high",
            (
                f"{excluded_count} idea(s) excluded for trend_match ≥ 75 AND niche_fit < 40 "
                f"({gap_text}). They do not occupy any of the {IDEA_COUNT_MIN}-{IDEA_COUNT_MAX} "
                "Post Ideas slots."
            ),
            (
                "Do not retroactively add the excluded ideas back into the queue. "
                "If the trend persists across two consecutive windows AND a niche-aligned "
                "angle emerges, re-evaluate next period."
            ),
        ))

    # Stale-trend dominance flag
    stale = sum(
        1 for t in inp.trends
        if t["velocity"] == "stale" or (t.get("hours_old", 0) > 24 and t["velocity"] != "accelerating")
    )
    if stale and stale >= max(2, len(inp.trends) // 2):
        flags.append((
            "Stale trends dominate watchlist",
            "medium",
            (
                f"{stale} of {len(inp.trends)} trends are stale (>24h old AND not accelerating). "
                "Idea generation built on stale trends carries weak signal-to-noise."
            ),
            "Re-pull trend data closer to posting time, or wait for niche-aligned trends to surface.",
        ))

    if not flags:
        flags.append((
            "No structural red flags",
            "low",
            "Plan stays within healthy bands; review remains creator-side qualitative judgement.",
            "Proceed; spot-check voice fidelity on the highest-match thread before posting.",
        ))

    titles = [f[0] for f in flags]
    lines = ["## Red Flags", ""]
    for title, sev, body, rem in flags:
        lines.append(f"- **{title}** · severity: {sev} — {body}. *Remediation:* {rem}")
    return "\n".join(lines), titles


def _render_recommendations(
    inp: TrendInput,
    selected: list[IdeaScore],
    score: PlanScore,
    excluded_count: int,
) -> str:
    lines = ["## Recommendations", ""]

    # Position 1 — content-idea-generator (mandatory)
    if score.paradox_active:
        lines.append(
            "1. Re-source the next anchor post in a tighter niche cluster — the current trend layer "
            "rewards volume over fit. — bridges to: `content-idea-generator`"
        )
    else:
        # pick the first non-thread idea's trend tag
        non_thread = [s for s in selected if s.raw["format"] != "thread"]
        tag = non_thread[0].raw["trend_tag"] if non_thread else (selected[0].raw["trend_tag"] if selected else "tight-niche")
        lines.append(
            f"1. Re-source the next anchor post in the cluster that drove `{tag}` — preserve "
            "niche fit while the trend window stays warm. — bridges to: `content-idea-generator`"
        )

    # Position 2 — thread-builder (mandatory)
    thread_ideas = [s for s in selected if s.raw["format"] == "thread"]
    if thread_ideas:
        top = thread_ideas[0]
        lines.append(
            f"2. Expand the highest-match thread idea (`{top.raw['trend_tag']}`) into a "
            "structured long-form draft. — bridges to: `thread-builder`"
        )
    else:
        lines.append(
            "2. Promote the highest-trend-match single into a structured thread — long-form "
            "carries the trend wave further than singles. — bridges to: `thread-builder`"
        )

    # Position 3 — context-aware
    if score.paradox_active or excluded_count > 0:
        lines.append(
            "3. Audit voice fidelity on every drafted variant before posting — paradox conditions "
            "tend to homogenise tone. — bridges to: `brand-voice-trainer`"
        )
    elif score.metric_values["Originality"] < 60:
        lines.append(
            "3. A/B test the format type that scored highest match against the next window's "
            "similar trends to isolate which variant carries weight. — bridges to: `ab-test-suggester`"
        )
    else:
        lines.append(
            "3. Pair each idea with a tag mix that fits both the trend and the niche surface "
            "before posting. — bridges to: `hashtag-strategy-advisor`"
        )

    # Position 4 — context-aware
    if score.metric_values["Voice fidelity"] < 70:
        lines.append(
            "4. Voice-check every draft against the last 25 high-engagement posts before publishing — "
            "the period is exposed to drift. — bridges to: `brand-voice-trainer`"
        )
    else:
        lines.append(
            "4. Correlate predicted engagement bands with actual impression and engagement metrics "
            "next window. — bridges to: `analytics-summarizer`"
        )

    # Position 5 — niche-coverage check
    lines.append(
        "5. Confirm the trend is broadly relevant to the niche, not just one peer's surface, "
        "before scheduling more variants. — bridges to: `competitor-watch`"
    )

    return "\n".join(lines)


def _render_confidence(
    inp: TrendInput,
    excluded_count: int,
    score: PlanScore,
) -> str:
    if inp.data_source == "demo":
        level = "low"
        reason = (
            "demo data only — re-run with --trends-file pointing at a real X export. "
            "Plan Score and arrows are illustrative."
        )
    elif score.paradox_active or excluded_count > 0:
        level = "medium"
        reason = (
            "real data, but paradox or off-niche guard active — voice fidelity audit "
            "before posting will raise confidence."
        )
    elif inp.window == 7:
        level = "medium"
        reason = "7d window over-indexes on single-day variance — re-run with 30d to confirm."
    else:
        level = "high"
        reason = "real data, all metrics inside healthy bands, no guard fired."
    return f"## Confidence\nConfidence: {level} — {reason}"


def _render_audit(
    inp: TrendInput, excluded_count: int, score: PlanScore
) -> Optional[str]:
    stale = sum(
        1 for t in inp.trends
        if t["velocity"] == "stale" or (t.get("hours_old", 0) > 24 and t["velocity"] != "accelerating")
    )
    all_stale = stale >= len(inp.trends) and len(inp.trends) > 0
    triggers = []
    if inp.window == 7:
        triggers.append("window=7d — single-day variance dominates trend velocity reads")
    if excluded_count > 0:
        triggers.append("off-niche guard fired — trend layer included off-niche surfaces")
    if all_stale:
        triggers.append("every watchlist trend is stale — trend layer is decaying")

    if not triggers:
        return None

    lines = [
        "## Trend Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {inp.window}d window is "
        + ("under-powered for trend velocity" if inp.window == 7 else "adequate")
        + ".",
        f"- **Data source confidence**: "
        + ("demo data — re-run with --trends-file for real X data" if inp.data_source == "demo" else "real X export — proceed"),
        f"- **Off-niche guard impact**: "
        + (f"{excluded_count} idea(s) excluded; Post Ideas count clamped to remaining eligible pool" if excluded_count > 0 else "none excluded"),
        f"- **Trend freshness**: {stale} of {len(inp.trends)} trends stale; "
        + ("wait for niche-aligned trends to surface" if all_stale else "watchlist still carries fresh signal"),
        "- **Suggested next sample**: re-run in 7 days when the niche trend cycle refreshes",
        "- **Re-run cadence**: weekly during active trend cycles, otherwise bi-weekly",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_trend_aligned_post_plan(
    *,
    x_handle: str,
    trends_file: Optional[str] = None,
    window: int = 30,
    compare_to: str = "previous_period",
    niche_fit_floor: float = DEFAULT_NICHE_FIT_FLOOR,
    target_idea_count: int = DEFAULT_TARGET_IDEA_COUNT,
    payload: Optional[dict] = None,
    args: Optional[argparse.Namespace] = None,
) -> str:
    """Render the full trend-aligned post plan markdown.

    Either ``payload`` (a parsed JSON dict) is supplied OR ``trends_file``
    is read from disk OR a demo seed is used (when neither is provided).
    """
    if args is None:
        args = argparse.Namespace(
            x_handle=x_handle,
            trends_file=trends_file,
            window=window,
            compare_to=compare_to,
            niche_fit_floor=niche_fit_floor,
            target_idea_count=target_idea_count,
        )
    inp = _validate_input(payload or {}, args)

    # Deterministic seed (reserved — used in future Grok-call variants).
    seed = _seed_from(
        inp.x_handle,
        json.dumps(inp.trends, sort_keys=True),
        str(inp.window),
        _utcnow_date(),
    )
    Random(seed)  # touch — keeps the seeding pathway alive for future use

    annotated, excluded_count = _apply_off_niche_guard(inp.candidate_ideas)
    selected = _select_post_ideas(annotated, inp.target_idea_count)
    score = _compute_plan_score(annotated, inp.niche_fit_floor)
    arrows = _arrows_against_basis(score, inp.previous_window_summary)
    score.metric_arrows = arrows

    parts: list[str] = []
    parts.append(_render_snapshot(inp, score))
    parts.append(_render_plan_score(inp, score, arrows))
    parts.append(_render_watchlist(inp))
    parts.append(_render_post_ideas(inp, selected, excluded_count, len(inp.candidate_ideas)))
    rf, _titles = _render_red_flags(score, excluded_count, inp, annotated)
    parts.append(rf)
    parts.append(_render_recommendations(inp, selected, score, excluded_count))
    parts.append(_render_confidence(inp, excluded_count, score))
    audit = _render_audit(inp, excluded_count, score)
    if audit is not None:
        parts.append(audit)

    return "\n\n".join(parts) + "\n"


# Manifest alias — required by grok-agent.yaml v2.15 tools[].function
generate = generate_trend_aligned_post_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_FILE_HEADER = (
    "<!-- Copyright 2026 AgentMindCloud -->\n"
    "<!-- Licensed under the Apache License, Version 2.0 -->\n"
    "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
    "<!-- Generated by trend-aligned-poster/run.py — built for X, Grok & the ecosystem community. -->\n"
    "\n"
)


def _maybe_load_payload(args: argparse.Namespace) -> Optional[dict]:
    if args.demo:
        return _load_demo("paradox")
    if args.demo_healthy:
        return _load_demo("healthy")
    if args.demo_7d_audit:
        return _load_demo("7d-audit")
    if args.trends_file:
        p = Path(args.trends_file)
        if not p.exists():
            raise TrendAlignedPosterError(f"trends_file {p} does not exist")
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trend-aligned-poster",
        description=(
            "Local-first trend-aligned poster for X creators. Drafts only — "
            "never auto-publishes. Built for X, Grok & the ecosystem community."
        ),
    )
    parser.add_argument("--x-handle", required=True, help="Creator's X handle (with or without @).")
    parser.add_argument("--trends-file", default=None, help="Path to a JSON trends export.")
    parser.add_argument("--window", type=int, default=30, help="Period window in days (7 / 30 / 90).")
    parser.add_argument(
        "--compare-to",
        default="previous_period",
        choices=COMPARE_OPTIONS,
        help="Comparison basis for trend deltas.",
    )
    parser.add_argument(
        "--niche-fit-floor",
        type=float,
        default=DEFAULT_NICHE_FIT_FLOOR,
        help="Niche fit threshold below which the trend-chasing paradox fires (default 40).",
    )
    parser.add_argument(
        "--target-idea-count",
        type=int,
        default=DEFAULT_TARGET_IDEA_COUNT,
        help="Target post idea count (clamped to [4, 6]).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the paradox + off-niche-guard demo seed (no real data).",
    )
    parser.add_argument(
        "--demo-healthy",
        action="store_true",
        help="Run the all-within-bounds demo seed.",
    )
    parser.add_argument(
        "--demo-7d-audit",
        action="store_true",
        help="Run the window=7d demo seed that auto-triggers the Trend Audit section.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the rendered plan to this path (default stdout).",
    )

    args = parser.parse_args(argv)

    selected_demos = sum(1 for f in (args.demo, args.demo_healthy, args.demo_7d_audit) if f)
    if selected_demos > 1:
        raise SystemExit("ERROR: choose at most one of --demo / --demo-healthy / --demo-7d-audit")

    payload = _maybe_load_payload(args)
    # Demo modes override the user-supplied window argument so the audit
    # demo can target window=7 even if the user passed --window=30.
    if args.demo_7d_audit:
        args.window = 7

    try:
        rendered = generate_trend_aligned_post_plan(
            x_handle=args.x_handle,
            trends_file=args.trends_file,
            window=args.window,
            compare_to=args.compare_to,
            niche_fit_floor=args.niche_fit_floor,
            target_idea_count=args.target_idea_count,
            payload=payload,
            args=args,
        )
    except TrendAlignedPosterError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(_FILE_HEADER + rendered, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
