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
"""Trend-Aligned Poster — runner.

CLI entry point for the ``trend-aligned-poster`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied X trend export (JSON) — or seeded demo trends when
no file is provided — and emits the strict 7/8-section trend-aligned post plan
defined by the P93 system prompt:

  1. Trend Snapshot
  2. Trend Alignment Plan Score (4-row metric table + weighted score + paradox if active)
  3. Trend Watchlist (3–5 curated trend entries with velocity + niche fit)
  4. Post Ideas (4–6 entries; off-niche trend-chasers excluded + Red Flagged)
  5. Red Flags (2–4 cards; paradox + off-niche guard + others)
  6. Recommendations (3–5; content-idea-generator + thread-builder unconditional)
  7. Confidence
  + Optional Trend Audit (auto-appended when window=7d OR off-niche guard
    excluded ≥1 idea OR all watchlist trends are stale)

Hard guarantees enforced by this runner:

* Drafts only. Never auto-publishes, schedules, or queues posts.
* No fabricated statistics. Demo trends carry an explicit
  `[demo trend — re-run with --trends-file for real X data]` label.
* Trend-chasing paradox surfaced in BOTH the Trend Alignment Plan Score
  section AND the Red Flags section whenever average Trend match > 75 AND
  average Niche fit < the configured floor (default 40).
* Plan Score formula is fixed:
    round(0.30*TrendMatch_norm + 0.25*NicheFit_norm +
          0.25*VoiceFidelity_norm + 0.20*Originality_norm)
* Off-niche guard: any idea with trend_match >= 75 AND niche_fit < 40 is
  excluded from Post Ideas + consolidated Red Flag. Excluded ideas do NOT
  count toward the 4–6 cap.
* Post Ideas capped at 4–6 after off-niche filter (target configurable,
  clamped to [4, 6]).
* Unconditional bridges: content-idea-generator (position 1) and
  thread-builder (position 2) in every Recommendations section.
* Privacy-first: no source-post handles, raw trend text, attachment URLs, or
  external links in rendered output. Trends and copy outlines are paraphrased.
* No financial, cashtag, investment, sponsorship, or harassment content.
* Deterministic: seeded by sha256(handle + sorted-payload-json + window).
  Date is NOT included in the seed so examples remain reproducible.
* Zero external network calls in v1.

Manifest contract::

    generate = generate_trend_aligned_poster

Built for X, Grok & the ecosystem community.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Optional

# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "prompts" / "system.md"

# Trend Alignment Plan Score metric weights (must sum to 1.0)
TREND_WEIGHTS = {
    "Trend match strength": 0.30,
    "Niche fit":            0.25,
    "Voice fidelity":       0.25,
    "Originality":          0.20,
}

# Healthy ranges for sub-score normalisation (lo, hi → 0–100)
TREND_HEALTHY_RANGES = {
    "Trend match strength": (50.0, 85.0),
    "Niche fit":            (60.0, 95.0),
    "Voice fidelity":       (65.0, 95.0),
    "Originality":          (50.0, 90.0),
}

# Trend-chasing paradox thresholds
PARADOX_TREND_MATCH_THRESHOLD = 75.0   # avg Trend match > 75
DEFAULT_NICHE_FIT_FLOOR       = 40.0   # avg Niche fit < floor

# Post Ideas constraints
MIN_POST_IDEAS           = 4
MAX_POST_IDEAS           = 6
DEFAULT_TARGET_IDEA_COUNT = 5

# A trend is considered stale if velocity == "stale" in the payload
# (runners with real data may also check last_seen_iso vs this threshold)
STALE_TREND_HOURS = 24

WINDOW_OPTIONS  = (7, 30, 90)
COMPARE_OPTIONS = ("previous_period", "benchmark")

ENGAGEMENT_BANDS  = ("low", "medium", "high", "breakout")
IDEA_FORMATS      = ("single", "thread", "quote-tweet", "image-post", "reply-thread")
VELOCITY_BUCKETS  = ("accelerating", "steady", "decaying", "stale")
NICHE_FIT_BUCKETS = ("tight", "adjacent", "loose", "off")

DEMO_LABEL = "[demo trend — re-run with --trends-file for real X data]"

# ---------------------------------------------------------------------------
# Demo data — 3 seeded modes (embedded so the runner is offline-safe)
# ---------------------------------------------------------------------------

# DEMO_PARADOX: avg Trend match = 79.4 (> 75 threshold)
#               avg Niche fit   = 36.1 (< 40 floor)
# → trend-chasing paradox fires in Plan Score AND Red Flags
# → 2 off-niche ideas (trend_match >= 75 AND niche_fit < 40) excluded
# → Trend Audit auto-triggered by off-niche exclusion
DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "window_days": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "previous_period": {
        "avg_trend_match":    68.2,
        "avg_niche_fit":      52.0,
        "avg_voice_fidelity": 68.5,
        "avg_originality":    54.2,
    },
    "trends": [
        {
            "id": "t001",
            "description": "Emerging discourse on lightweight agent orchestration patterns",
            "velocity": "accelerating",
            "niche_fit": "tight",
        },
        {
            "id": "t002",
            "description": "Viral debate on real-time X analytics tooling for independent creators",
            "velocity": "accelerating",
            "niche_fit": "adjacent",
        },
        {
            "id": "t003",
            "description": "Trending commentary on AI-generated content disclosure norms",
            "velocity": "steady",
            "niche_fit": "adjacent",
        },
        {
            "id": "t004",
            "description": "Broad conversation on creator monetisation models beyond sponsorships",
            "velocity": "steady",
            "niche_fit": "loose",
        },
        {
            "id": "t005",
            "description": "Off-niche viral wave around consumer gadget unboxing formats",
            "velocity": "accelerating",
            "niche_fit": "off",
        },
    ],
    "ideas": [
        # --- 2 off-niche trend-chasers (trend_match >= 75 AND niche_fit < 40) ---
        {
            "id": "o001",
            "format": "single",
            "trend_match": 88,
            "niche_fit": 22,
            "voice_fidelity": 72,
            "originality": 55,
            "copy_outline": "Hot-take angle on the gadget unboxing wave mapped to creator workflows",
            "trend_tag": "gadget-unboxing-creator-angle",
        },
        {
            "id": "o002",
            "format": "quote-tweet",
            "trend_match": 85,
            "niche_fit": 25,
            "voice_fidelity": 69,
            "originality": 60,
            "copy_outline": "Reframe of the AI-disclosure debate through a non-niche productivity lens",
            "trend_tag": "ai-disclosure-productivity",
        },
        # --- 5 kept ideas (niche_fit >= 40 satisfies the guard) ---
        {
            "id": "k001",
            "format": "thread",
            "trend_match": 79,
            "niche_fit": 41,
            "voice_fidelity": 75,
            "originality": 62,
            "copy_outline": "5-step breakdown of lightweight orchestration patterns for solo agent builders",
            "trend_tag": "agent-orchestration-patterns",
        },
        {
            "id": "k002",
            "format": "single",
            "trend_match": 76,
            "niche_fit": 42,
            "voice_fidelity": 73,
            "originality": 60,
            "copy_outline": "Counterpoint to the analytics-tooling hype: the one signal creators actually need",
            "trend_tag": "x-analytics-tooling-hype",
        },
        {
            "id": "k003",
            "format": "quote-tweet",
            "trend_match": 74,
            "niche_fit": 40,
            "voice_fidelity": 70,
            "originality": 58,
            "copy_outline": "Nuanced take on AI disclosure norms from a solo-builder perspective",
            "trend_tag": "ai-content-disclosure",
        },
        {
            "id": "k004",
            "format": "image-post",
            "trend_match": 79,
            "niche_fit": 40,
            "voice_fidelity": 70,
            "originality": 57,
            "copy_outline": "Visual framework mapping monetisation models to audience-trust curves",
            "trend_tag": "creator-monetisation-models",
        },
        {
            "id": "k005",
            "format": "reply-thread",
            "trend_match": 75,
            "niche_fit": 43,
            "voice_fidelity": 68,
            "originality": 58,
            "copy_outline": "Reply-thread diving into the edge cases of monetisation beyond direct sponsorship",
            "trend_tag": "creator-monetisation-models",
        },
    ],
}

# DEMO_HEALTHY: avg Trend match = 68.0 (< 75 — no paradox)
#              avg Niche fit   = 77.0 (> 40 floor — no paradox, no near-paradox)
# → clean 7-section report; no flags beyond defensive top-up
DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "window_days": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "previous_period": {
        "avg_trend_match":    65.0,
        "avg_niche_fit":      74.0,
        "avg_voice_fidelity": 77.0,
        "avg_originality":    65.8,
    },
    "trends": [
        {
            "id": "t001",
            "description": "Growing conversation on habit-stacking systems for knowledge workers",
            "velocity": "accelerating",
            "niche_fit": "tight",
        },
        {
            "id": "t002",
            "description": "Mainstream interest in evening-routine optimisation frameworks",
            "velocity": "steady",
            "niche_fit": "tight",
        },
        {
            "id": "t003",
            "description": "Adjacent surge in productivity tool comparisons for async teams",
            "velocity": "steady",
            "niche_fit": "adjacent",
        },
        {
            "id": "t004",
            "description": "Decelerating thread format popularity in niche coaching content",
            "velocity": "decaying",
            "niche_fit": "adjacent",
        },
    ],
    "ideas": [
        {
            "id": "h001",
            "format": "thread",
            "trend_match": 74,
            "niche_fit": 82,
            "voice_fidelity": 86,
            "originality": 74,
            "copy_outline": "7-tweet breakdown of the habit-stacking system applied to knowledge-work routines",
            "trend_tag": "habit-stacking-knowledge-workers",
        },
        {
            "id": "h002",
            "format": "single",
            "trend_match": 71,
            "niche_fit": 79,
            "voice_fidelity": 83,
            "originality": 72,
            "copy_outline": "Counterintuitive evening-routine principle most people implement backwards",
            "trend_tag": "evening-routine-optimisation",
        },
        {
            "id": "h003",
            "format": "quote-tweet",
            "trend_match": 68,
            "niche_fit": 77,
            "voice_fidelity": 81,
            "originality": 70,
            "copy_outline": "Reframe of the productivity-tool comparison trend through a single-system lens",
            "trend_tag": "productivity-tool-comparison",
        },
        {
            "id": "h004",
            "format": "image-post",
            "trend_match": 65,
            "niche_fit": 74,
            "voice_fidelity": 79,
            "originality": 68,
            "copy_outline": "Visual showing how the habit loop maps onto the three async-team failure modes",
            "trend_tag": "async-team-productivity",
        },
        {
            "id": "h005",
            "format": "reply-thread",
            "trend_match": 62,
            "niche_fit": 73,
            "voice_fidelity": 78,
            "originality": 66,
            "copy_outline": "Reply-thread expanding on how decelerating thread formats still outperform single posts in niche coaching",
            "trend_tag": "thread-format-effectiveness",
        },
    ],
}

# DEMO_7D: window=7d, avg Trend match = 72.0 (> 65 — near-paradox range),
#          avg Niche fit = 42.0 (< 50 = floor + 10 — near-paradox watch fires)
# → Trend Audit auto-triggered by window=7d
# → Near-paradox watch Red Flag fires (trend_match in (65,75] AND niche_fit < 50)
# → NO full paradox (trend_match = 72 <= 75)
# → One stale watchlist trend (informational-only note)
DEMO_7D = {
    "x_handle": "@JanSol0s",
    "window_days": 7,
    "compare_to": "previous_period",
    "data_source": "demo",
    "previous_period": {
        "avg_trend_match":    69.0,
        "avg_niche_fit":      48.0,
        "avg_voice_fidelity": 67.0,
        "avg_originality":    58.5,
    },
    "trends": [
        {
            "id": "t001",
            "description": "Emerging week-over-week spike in agent-eval workflow discourse",
            "velocity": "accelerating",
            "niche_fit": "tight",
        },
        {
            "id": "t002",
            "description": "Short-lived surge around a specific open-source tooling release",
            "velocity": "steady",
            "niche_fit": "adjacent",
        },
        {
            "id": "t003",
            "description": "Older thread-format commentary that peaked two weeks ago",
            "velocity": "stale",
            "niche_fit": "adjacent",
        },
    ],
    "ideas": [
        {
            "id": "j001",
            "format": "thread",
            "trend_match": 74,
            "niche_fit": 44,
            "voice_fidelity": 72,
            "originality": 63,
            "copy_outline": "5-part thread on agent-eval patterns surfaced by this week's discourse spike",
            "trend_tag": "agent-eval-workflow",
        },
        {
            "id": "j002",
            "format": "single",
            "trend_match": 73,
            "niche_fit": 42,
            "voice_fidelity": 70,
            "originality": 61,
            "copy_outline": "Hot take on the open-source tooling release and what it actually ships vs what the thread claims",
            "trend_tag": "oss-tooling-release",
        },
        {
            "id": "j003",
            "format": "quote-tweet",
            "trend_match": 71,
            "niche_fit": 41,
            "voice_fidelity": 69,
            "originality": 60,
            "copy_outline": "Nuanced reframe of the thread-format debate from a niche-builder perspective",
            "trend_tag": "thread-format-commentary",
        },
        {
            "id": "j004",
            "format": "image-post",
            "trend_match": 70,
            "niche_fit": 41,
            "voice_fidelity": 68,
            "originality": 58,
            "copy_outline": "Visual comparing agent-eval approaches before and after the tooling release",
            "trend_tag": "agent-eval-workflow",
        },
    ],
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TrendEntry:
    id: str
    description: str
    velocity: str
    niche_fit: str
    is_stale: bool


@dataclass
class PostIdea:
    id: str
    format: str
    trend_match: int
    niche_fit: int
    voice_fidelity: int
    originality: int
    copy_outline: str
    trend_tag: str
    engagement_band: str
    bridge_slug: str
    is_off_niche: bool
    is_demo: bool


@dataclass
class TrendPlanMetrics:
    avg_trend_match:    float
    avg_niche_fit:      float
    avg_voice_fidelity: float
    avg_originality:    float
    prev_trend_match:   float
    prev_niche_fit:     float
    prev_voice_fidelity: float
    prev_originality:   float


@dataclass
class TrendPlanScores:
    avg_trend_match:    float
    avg_niche_fit:      float
    avg_voice_fidelity: float
    avg_originality:    float
    trend_match_arrow:    str
    niche_fit_arrow:      str
    voice_fidelity_arrow: str
    originality_arrow:    str
    plan_score:     int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)


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


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def load_trends_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"--trends-file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--trends-file is not valid JSON: {exc}") from exc


def _is_stale(trend: dict) -> bool:
    if trend.get("velocity") == "stale":
        return True
    last_seen = trend.get("last_seen_iso")
    if last_seen:
        try:
            dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            return age_hours > STALE_TREND_HOURS and trend.get("velocity") != "accelerating"
        except ValueError:
            pass
    return False


# ---------------------------------------------------------------------------
# Off-niche guard
# ---------------------------------------------------------------------------


def _is_off_niche_idea(idea: dict, niche_fit_floor: float) -> bool:
    """A post idea is off-niche when trend_match >= 75 AND niche_fit < floor."""
    return (
        int(idea.get("trend_match", 0)) >= 75
        and int(idea.get("niche_fit", 100)) < niche_fit_floor
    )


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_plan_metrics(payload: dict) -> TrendPlanMetrics:
    ideas = payload.get("ideas", [])
    n = max(len(ideas), 1)

    avg_tm  = sum(int(i.get("trend_match",    0)) for i in ideas) / n
    avg_nf  = sum(int(i.get("niche_fit",      0)) for i in ideas) / n
    avg_vf  = sum(int(i.get("voice_fidelity", 0)) for i in ideas) / n
    avg_og  = sum(int(i.get("originality",    0)) for i in ideas) / n

    prev = payload.get("previous_period", {})
    prev_tm = float(prev.get("avg_trend_match",    avg_tm  * 0.9))
    prev_nf = float(prev.get("avg_niche_fit",      avg_nf  * 0.9))
    prev_vf = float(prev.get("avg_voice_fidelity", avg_vf  * 0.9))
    prev_og = float(prev.get("avg_originality",    avg_og  * 0.9))

    return TrendPlanMetrics(
        avg_trend_match=avg_tm,
        avg_niche_fit=avg_nf,
        avg_voice_fidelity=avg_vf,
        avg_originality=avg_og,
        prev_trend_match=prev_tm,
        prev_niche_fit=prev_nf,
        prev_voice_fidelity=prev_vf,
        prev_originality=prev_og,
    )


# ---------------------------------------------------------------------------
# Normalisation + scoring
# ---------------------------------------------------------------------------


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def _pct_arrow(delta_pct: float) -> str:
    """Standard ±5% / ±25% thresholds for relative-change comparisons."""
    if delta_pct >= 25.0:
        return "▲▲"
    if delta_pct >= 5.0:
        return "▲"
    if delta_pct >= -5.0:
        return "▬"
    if delta_pct >= -25.0:
        return "▼"
    return "▼▼"


def _rel_delta(cur: float, prev: float) -> float:
    return (cur - prev) / max(abs(prev), 0.01) * 100.0


def score_plan(m: TrendPlanMetrics, niche_fit_floor: float) -> TrendPlanScores:
    norm_tm = _norm(m.avg_trend_match,    *TREND_HEALTHY_RANGES["Trend match strength"])
    norm_nf = _norm(m.avg_niche_fit,      *TREND_HEALTHY_RANGES["Niche fit"])
    norm_vf = _norm(m.avg_voice_fidelity, *TREND_HEALTHY_RANGES["Voice fidelity"])
    norm_og = _norm(m.avg_originality,    *TREND_HEALTHY_RANGES["Originality"])

    plan_score = round(
        TREND_WEIGHTS["Trend match strength"] * norm_tm
        + TREND_WEIGHTS["Niche fit"]            * norm_nf
        + TREND_WEIGHTS["Voice fidelity"]       * norm_vf
        + TREND_WEIGHTS["Originality"]          * norm_og
    )

    tm_arrow = _pct_arrow(_rel_delta(m.avg_trend_match,    m.prev_trend_match))
    nf_arrow = _pct_arrow(_rel_delta(m.avg_niche_fit,      m.prev_niche_fit))
    vf_arrow = _pct_arrow(_rel_delta(m.avg_voice_fidelity, m.prev_voice_fidelity))
    og_arrow = _pct_arrow(_rel_delta(m.avg_originality,    m.prev_originality))

    paradox = (
        m.avg_trend_match > PARADOX_TREND_MATCH_THRESHOLD
        and m.avg_niche_fit < niche_fit_floor
    )

    return TrendPlanScores(
        avg_trend_match=m.avg_trend_match,
        avg_niche_fit=m.avg_niche_fit,
        avg_voice_fidelity=m.avg_voice_fidelity,
        avg_originality=m.avg_originality,
        trend_match_arrow=tm_arrow,
        niche_fit_arrow=nf_arrow,
        voice_fidelity_arrow=vf_arrow,
        originality_arrow=og_arrow,
        plan_score=plan_score,
        paradox_active=paradox,
        interpretations=_build_plan_interpretations(m, niche_fit_floor),
    )


def _build_plan_interpretations(m: TrendPlanMetrics, floor: float) -> dict:
    out: dict[str, str] = {}

    tm = m.avg_trend_match
    lo_tm, hi_tm = TREND_HEALTHY_RANGES["Trend match strength"]
    if tm > PARADOX_TREND_MATCH_THRESHOLD:
        out["Trend match strength"] = (
            "High match — but verify niche fit before treating the score as a quality signal."
        )
    elif tm >= lo_tm:
        out["Trend match strength"] = (
            "Inside the healthy band; trends are relevant without overwhelming the niche filter."
        )
    else:
        out["Trend match strength"] = (
            "Below the healthy floor; trends are loosely relevant — consider sourcing more niche-aligned trends."
        )

    nf = m.avg_niche_fit
    lo_nf = TREND_HEALTHY_RANGES["Niche fit"][0]
    if nf < floor:
        out["Niche fit"] = (
            f"Below the {floor:.0f} floor; ideas chase virality at the cost of audience focus."
        )
    elif nf < lo_nf:
        out["Niche fit"] = (
            "Borderline — above the off-niche guard floor but below the healthy range; "
            "the plan sits in a caution zone."
        )
    elif nf >= 85.0:
        out["Niche fit"] = (
            "Excellent niche alignment; every idea reinforces the creator's core audience."
        )
    else:
        out["Niche fit"] = (
            "Inside the healthy band; ideas are niche-aligned with room to push relevance further."
        )

    vf = m.avg_voice_fidelity
    lo_vf = TREND_HEALTHY_RANGES["Voice fidelity"][0]
    if vf >= 85.0:
        out["Voice fidelity"] = (
            "Strong voice fidelity; copy outlines preserve the creator's distinctive tone."
        )
    elif vf >= lo_vf:
        out["Voice fidelity"] = (
            "Inside the healthy band; copy outlines preserve the creator's tone."
        )
    else:
        out["Voice fidelity"] = (
            "Below the healthy floor; trend-chasing may be homogenising the voice — "
            "raise the originality bar before posting."
        )

    og = m.avg_originality
    lo_og = TREND_HEALTHY_RANGES["Originality"][0]
    if og >= 75.0:
        out["Originality"] = (
            "High originality; ideas avoid generic trend-chasing and bring a fresh angle."
        )
    elif og >= lo_og:
        out["Originality"] = (
            "Inside the healthy band; ideas are sufficiently differentiated from the crowd."
        )
    else:
        out["Originality"] = (
            "Borderline — trend-chasing tends to homogenise voice; raise the originality bar before posting."
        )

    return out


# ---------------------------------------------------------------------------
# Engagement band
# ---------------------------------------------------------------------------


def _engagement_band(trend_match: int, niche_fit: int) -> str:
    """Predict engagement band from trend_match + niche_fit composite."""
    composite = 0.6 * trend_match + 0.4 * niche_fit
    if composite >= 75.0:
        return "breakout"
    if composite >= 62.0:
        return "high"
    if composite >= 48.0:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Post Ideas building (with off-niche guard)
# ---------------------------------------------------------------------------


def build_post_ideas(
    ideas_raw: list[dict],
    niche_fit_floor: float,
    target_idea_count: int,
    is_demo: bool,
) -> tuple[list[PostIdea], list[PostIdea]]:
    """Return (kept_ideas, excluded_ideas).

    kept_ideas: top N after off-niche filter, sorted by (trend_match desc, niche_fit desc, originality desc)
    excluded_ideas: ideas where trend_match >= 75 AND niche_fit < floor
    """
    target = max(MIN_POST_IDEAS, min(MAX_POST_IDEAS, target_idea_count))
    kept_raw = []
    excluded_raw = []

    for raw in ideas_raw:
        if _is_off_niche_idea(raw, niche_fit_floor):
            excluded_raw.append(raw)
        else:
            kept_raw.append(raw)

    kept_raw.sort(
        key=lambda d: (
            int(d.get("trend_match", 0)),
            int(d.get("niche_fit", 0)),
            int(d.get("originality", 0)),
        ),
        reverse=True,
    )

    def _to_post_idea(raw: dict, off_niche: bool) -> PostIdea:
        fmt = str(raw.get("format", "single"))
        tm  = int(raw.get("trend_match", 0))
        nf  = int(raw.get("niche_fit", 0))
        slug = "thread-builder" if fmt == "thread" else "content-idea-generator"
        return PostIdea(
            id=str(raw.get("id", "")),
            format=fmt,
            trend_match=tm,
            niche_fit=nf,
            voice_fidelity=int(raw.get("voice_fidelity", 0)),
            originality=int(raw.get("originality", 0)),
            copy_outline=str(raw.get("copy_outline", "(paraphrased copy outline)")),
            trend_tag=str(raw.get("trend_tag", "trend")),
            engagement_band=_engagement_band(tm, nf),
            bridge_slug=slug,
            is_off_niche=off_niche,
            is_demo=is_demo,
        )

    kept    = [_to_post_idea(r, False) for r in kept_raw[:target]]
    excluded = [_to_post_idea(r, True)  for r in excluded_raw]
    return kept, excluded


# ---------------------------------------------------------------------------
# Trend Watchlist
# ---------------------------------------------------------------------------


def build_trend_watchlist(trends_raw: list[dict], is_demo: bool) -> list[TrendEntry]:
    """Return 3–5 trend watchlist entries."""
    entries: list[TrendEntry] = []
    for raw in trends_raw[:5]:
        stale = _is_stale(raw)
        entries.append(TrendEntry(
            id=str(raw.get("id", "")),
            description=str(raw.get("description", "(paraphrased trend)")),
            velocity=str(raw.get("velocity", "steady")),
            niche_fit=str(raw.get("niche_fit", "adjacent")),
            is_stale=stale,
        ))
    return entries


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: TrendPlanScores,
    excluded: list[PostIdea],
    watchlist: list[TrendEntry],
    window: int,
    niche_fit_floor: float,
) -> list[RedFlag]:
    flags: list[RedFlag] = []
    all_stale = bool(watchlist) and all(e.is_stale for e in watchlist)

    # Rule 1: Trend-chasing paradox (dual surfacing — also appears in Plan Score section)
    if scores.paradox_active:
        flags.append(RedFlag(
            title="Trend-chasing paradox",
            severity="high",
            explanation=(
                f"Average Trend match strength at {scores.avg_trend_match:.1f} sits above the "
                f"{int(PARADOX_TREND_MATCH_THRESHOLD)} threshold while average Niche fit at "
                f"{scores.avg_niche_fit:.1f} is below the {niche_fit_floor:.0f} floor. "
                "The plan would inflate volume by chasing off-niche virality and dilute the "
                "creator's audience over time."
            ),
            remediation=(
                "Option A: tighten the trend filter to niche-relevant trends only for the next window "
                "before posting. Option B: accept the period as a quiet-trend stretch and wait for "
                "niche-aligned trends to surface rather than chasing off-niche virality."
            ),
        ))

    # Rule 2: Off-niche trend-chasers excluded
    if excluded:
        n = len(excluded)
        plural = "idea" if n == 1 else "ideas"
        flags.append(RedFlag(
            title="Off-niche trend-chasers excluded",
            severity="high",
            explanation=(
                f"{n} post {plural} scored trend_match ≥ 75 AND niche_fit < {niche_fit_floor:.0f} — "
                "excluded from the Post Ideas section. These ideas chase viral trends that sit outside "
                "the creator's established niche, risking audience dilution for a short-term impression spike."
            ),
            remediation=(
                "Do not retroactively add the excluded ideas back into the queue. If the trend persists "
                "across two consecutive windows AND a niche-aligned angle emerges, re-evaluate next period."
            ),
        ))

    # Rule 3: All-trends-stale watch
    if all_stale:
        flags.append(RedFlag(
            title="All watchlist trends are stale",
            severity="medium",
            explanation=(
                "Every trend in the watchlist is marked stale (>24h old and not accelerating). "
                "Idea scores derived from stale trends carry inflated trend_match readings that "
                "do not reflect the current cycle."
            ),
            remediation=(
                "Pause idea generation until fresher trend data is available. "
                "Re-run with --trends-file sourced from the current X Trending API cycle."
            ),
        ))

    # Rule 4: Near-paradox watch (trend_match in (65, 75] AND niche_fit < floor + 10)
    near_paradox = (
        not scores.paradox_active
        and 65.0 < scores.avg_trend_match <= PARADOX_TREND_MATCH_THRESHOLD
        and scores.avg_niche_fit < (niche_fit_floor + 10.0)
    )
    if near_paradox:
        flags.append(RedFlag(
            title="Near-paradox watch",
            severity="low",
            explanation=(
                f"Average Trend match strength at {scores.avg_trend_match:.1f} is approaching the "
                f"{int(PARADOX_TREND_MATCH_THRESHOLD)} paradox threshold while average Niche fit at "
                f"{scores.avg_niche_fit:.1f} is below the {niche_fit_floor + 10:.0f} watch level — "
                "one more trend-heavy window could trigger the trend-chasing paradox."
            ),
            remediation=(
                "Run `mention-summarizer` to confirm whether the same low-niche pattern is showing in "
                "public mentions — divergence here is an early-warning signal to rebalance the trend mix."
            ),
        ))

    # Rule 5: Single-window variance exposure (7d window)
    if window == 7:
        flags.append(RedFlag(
            title="Single-window variance exposure",
            severity="medium",
            explanation=(
                "A 7d trend window is dominated by single-day variance; one viral post or one quiet "
                "day can flip every trend arrow and engagement band reading."
            ),
            remediation=(
                "Re-run with --window 30 once 14+ more days have passed before declaring directional reads."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-period read",
            severity="low",
            explanation=(
                "One trend window is directional, not conclusive. "
                "Treat the Trend Alignment Plan Score as a snapshot, not a trend."
            ),
            remediation=(
                "Re-run monthly to build a baseline of trend arrows across consecutive windows."
            ),
        ))

    if len(flags) < 2:
        flags.append(RedFlag(
            title="Trend freshness reminder",
            severity="low",
            explanation=(
                "Confirm trend recency before posting; trends shift faster than monthly windows capture."
            ),
            remediation=(
                "Re-run with --window 7 to check velocity in the most recent cycle before committing to any idea."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations (mandatory: content-idea-generator + thread-builder always first)
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: TrendPlanScores,
    kept_ideas: list[PostIdea],
    excluded: list[PostIdea],
    window: int,
) -> list[Recommendation]:
    queue_count = len(kept_ideas)

    # Mandatory position 1: content-idea-generator
    if scores.paradox_active or excluded:
        cig_text = (
            f"Re-source the next anchor post ideas from a niche-aligned trend set before "
            f"posting any of the {queue_count} current ideas — the current trend mix carries "
            "off-niche risk."
        )
    else:
        cig_text = (
            f"Extend the {queue_count} post ideas in this plan by re-sourcing anchor posts "
            "when trends shift; keep a rolling set of 5–8 niche-aligned idea candidates."
        )
    mandatory_cig = Recommendation(text=cig_text, bridge_slug="content-idea-generator")

    # Mandatory position 2: thread-builder
    thread_ideas = [i for i in kept_ideas if i.format == "thread"]
    if thread_ideas:
        top_thread = thread_ideas[0]
        tb_text = (
            f"Expand the highest-match thread idea (trend match {top_thread.trend_match}) "
            "into a structured long-form draft before publishing."
        )
    else:
        tb_text = (
            "No thread format idea in the current plan; use thread-builder to reformat "
            "the highest-match single idea into a multi-tweet structure."
        )
    mandatory_tb = Recommendation(text=tb_text, bridge_slug="thread-builder")

    # Optional pool (seeded shuffle)
    optional_pool: list[Recommendation] = []

    optional_pool.append(Recommendation(
        text=(
            "Pair each post idea with a niche-specific tag mix that fits both the trend and "
            "the creator's surface before publishing."
        ),
        bridge_slug="hashtag-strategy-advisor",
    ))

    if scores.paradox_active or excluded:
        optional_pool.append(Recommendation(
            text=(
                "Audit the voice fidelity of the proposed copy outlines — trend-chasing periods "
                "tend to homogenise the creator's voice."
            ),
            bridge_slug="brand-voice-trainer",
        ))

    if not scores.paradox_active and queue_count >= 4:
        optional_pool.append(Recommendation(
            text=(
                "A/B test the format type that scored the highest trend match against the next "
                "window's similar trends to confirm the format lifts authentic engagement."
            ),
            bridge_slug="ab-test-suggester",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Correlate the predicted engagement bands with the period's actual impression and "
            "engagement metrics next window to calibrate the model."
        ),
        bridge_slug="analytics-summarizer",
    ))

    optional_pool.append(Recommendation(
        text=(
            "Cross-reference whether the trend is already showing in the creator's mention layer "
            "before posting — inbound mention signals lead outbound trend cycles by 24–48h."
        ),
        bridge_slug="mention-summarizer",
    ))

    if scores.paradox_active or excluded:
        optional_pool.append(Recommendation(
            text=(
                "Confirm the off-niche trend is broadly relevant to the niche, not just one peer's "
                "surface — competitor patterns reveal whether this is a niche-wide shift."
            ),
            bridge_slug="competitor-watch",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Adapt the highest-match idea to adjacent platforms to confirm niche fit before "
            "investing in thread production."
        ),
        bridge_slug="cross-platform-reposter",
    ))

    if queue_count >= 4 and not scores.paradox_active:
        optional_pool.append(Recommendation(
            text=(
                "Convert reply-thread ideas into structured comment plans on adjacent creator posts "
                "to boost engagement without producing new anchor content."
            ),
            bridge_slug="comment-engagement-booster",
        ))

    # Shuffle optional pool with seeded RNG
    rng.shuffle(optional_pool)

    # De-duplicate bridge slugs
    seen_optional: set[str] = {"content-idea-generator", "thread-builder"}
    deduped: list[Recommendation] = []
    for rec in optional_pool:
        if rec.bridge_slug not in seen_optional:
            deduped.append(rec)
            seen_optional.add(rec.bridge_slug)

    result = [mandatory_cig, mandatory_tb] + deduped[:3]
    return result[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def build_confidence(
    scores: TrendPlanScores,
    excluded: list[PostIdea],
    all_stale: bool,
    window: int,
    is_demo: bool,
) -> tuple[str, str]:
    if is_demo:
        return (
            "low",
            "data source is seeded demo trends — re-run with --trends-file pointing at the actual X "
            "trend export to lift confidence.",
        )
    if scores.paradox_active or excluded:
        return (
            "low",
            f"Trend Alignment Plan Score {scores.plan_score}/100; paradox or off-niche guard active — "
            "investigate the niche-fit gap and re-source trend data before posting.",
        )
    if window == 30 and scores.plan_score >= 55 and not all_stale:
        return (
            "high",
            f"30d window covers the main trend signals; Trend Alignment Plan Score {scores.plan_score}/100 "
            "with no paradox or stale-trend interference.",
        )
    if scores.plan_score >= 40:
        return (
            "medium",
            f"Trend Alignment Plan Score {scores.plan_score}/100; widen the window or supply richer "
            "trend data to lift to high.",
        )
    return (
        "low",
        f"Trend Alignment Plan Score {scores.plan_score}/100; investigate the falling metrics "
        "and stale-trend interference before declaring a direction.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _demo_tag(is_demo: bool) -> str:
    return f" {DEMO_LABEL}" if is_demo else ""


def _render_snapshot(
    payload: dict,
    scores: TrendPlanScores,
    excluded: list[PostIdea],
    is_demo: bool,
) -> str:
    handle  = normalize_handle(payload["x_handle"])
    window  = int(payload["window_days"])
    compare = payload.get("compare_to", "previous_period")

    if scores.paradox_active:
        headline = (
            f"{handle}: {window}d trend window — trend-chasing paradox active; "
            f"Trend match strength {scores.avg_trend_match:.1f} but Niche fit only "
            f"{scores.avg_niche_fit:.1f}."
        )
    elif excluded:
        headline = (
            f"{handle}: {window}d trend window — {len(excluded)} off-niche idea(s) excluded; "
            f"Trend Alignment Plan Score {scores.plan_score}/100 after guard."
        )
    elif scores.plan_score >= 60:
        headline = (
            f"{handle}: {window}d trend window — healthy trend alignment "
            f"(Trend Alignment Plan Score {scores.plan_score}/100)."
        )
    elif scores.plan_score >= 40:
        headline = (
            f"{handle}: {window}d trend window — directional period "
            f"(Trend Alignment Plan Score {scores.plan_score}/100); monitor niche fit next window."
        )
    else:
        headline = (
            f"{handle}: {window}d trend window — weak alignment "
            f"(Trend Alignment Plan Score {scores.plan_score}/100); re-source niche-aligned trends."
        )

    data_line = (
        "seeded demo trends — re-run with --trends-file for real X data"
        if is_demo
        else "real X trend export from --trends-file"
    )

    return "\n".join([
        "## Trend Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Window**: {window}d",
        f"- **Comparison basis**: {compare}",
        f"- **Data source**: {data_line}",
    ])


def _render_plan_score(
    scores: TrendPlanScores,
    is_demo: bool,
    excluded_count: int,
) -> str:
    dt = _demo_tag(is_demo)
    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        (
            f"| Trend match strength | {scores.avg_trend_match:.1f}/100{dt} | "
            f"{scores.trend_match_arrow} | {scores.interpretations['Trend match strength']} |"
        ),
        (
            f"| Niche fit            | {scores.avg_niche_fit:.1f}/100{dt} | "
            f"{scores.niche_fit_arrow} | {scores.interpretations['Niche fit']} |"
        ),
        (
            f"| Voice fidelity       | {scores.avg_voice_fidelity:.1f}/100{dt} | "
            f"{scores.voice_fidelity_arrow} | {scores.interpretations['Voice fidelity']} |"
        ),
        (
            f"| Originality          | {scores.avg_originality:.1f}/100{dt} | "
            f"{scores.originality_arrow} | {scores.interpretations['Originality']} |"
        ),
    ]
    out = "## Trend Alignment Plan Score\n\n" + "\n".join(rows)
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: trend match is high but niche fit is below the floor — "
            "the plan would inflate volume by chasing off-niche virality and dilute the "
            "creator's audience over time."
        )
    out += f"\n\n**Trend Alignment Plan Score**: {scores.plan_score}/100"
    return out


def _render_trend_watchlist(watchlist: list[TrendEntry], is_demo: bool) -> str:
    dt = _demo_tag(is_demo)
    rows = [
        "| Trend (paraphrased) | Velocity | Niche fit |",
        "|---|---|---|",
    ]
    for entry in watchlist:
        stale_note = " *(informational only — do not drive idea generation)*" if entry.is_stale else ""
        rows.append(
            f"| {entry.description}{dt}{stale_note} | {entry.velocity} | {entry.niche_fit} |"
        )
    return "## Trend Watchlist\n\n" + "\n".join(rows)


def _render_post_ideas(
    kept: list[PostIdea],
    excluded: list[PostIdea],
    is_demo: bool,
) -> str:
    total_candidates = len(kept) + len(excluded)
    dt = _demo_tag(is_demo)

    if excluded:
        header = (
            f"## Post Ideas ({len(kept)} of {total_candidates} candidate ideas — "
            f"{len(excluded)} off-niche trend-chaser(s) excluded; see Red Flags)"
        )
    else:
        header = f"## Post Ideas ({len(kept)} ideas)"

    if not kept:
        return header + "\n\n_(all candidate ideas excluded by off-niche guard — re-source niche-aligned trends)_"

    lines = [header, ""]
    for i, idea in enumerate(kept, start=1):
        lines.append(
            f"{i}. **{idea.format}** · trend: `{idea.trend_tag}` — {idea.copy_outline}"
        )
        lines.append(
            f"   trend match: {idea.trend_match}{dt} · engagement: {idea.engagement_band} "
            f"· bridges to: `{idea.bridge_slug}`"
        )
    return "\n".join(lines)


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} "
        f"*Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    for i, rec in enumerate(recs, start=1):
        lines.append(f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`")
    return "\n".join(lines)


def _render_trend_audit(
    payload: dict,
    excluded: list[PostIdea],
    watchlist: list[TrendEntry],
    is_demo: bool,
) -> str:
    window = int(payload["window_days"])
    all_stale = bool(watchlist) and all(e.is_stale for e in watchlist)

    window_line = (
        "7d window is dominated by single-day variance; treat all reads as directional — "
        "re-run with --window 30 once 14+ more days have passed."
        if window == 7
        else f"{window}d window is appropriate for the trend patterns surfaced; "
             "single-window reads are still directional rather than conclusive."
    )
    data_line = (
        "seeded demo placeholders — runner cannot speak to real-creator confidence until "
        "--trends-file is supplied."
        if is_demo
        else "real trend export loaded; verify that all ideas and trends reflect the current window."
    )
    if excluded:
        exc_line = (
            f"{len(excluded)} off-niche idea(s) removed from Post Ideas; "
            "available slots reduced accordingly — re-source niche-aligned ideas to refill."
        )
    else:
        exc_line = "none excluded — all candidate ideas passed the off-niche guard."

    if all_stale:
        freshness_line = (
            "All watchlist trends are stale (>24h old, not accelerating); "
            "pause idea generation and re-run when fresh trend data is available."
        )
        next_sample = "immediately — re-source trend data before committing to any idea in this plan."
    else:
        stale_count = sum(1 for e in watchlist if e.is_stale)
        if stale_count > 0:
            freshness_line = (
                f"{stale_count} of {len(watchlist)} watchlist trend(s) are stale; "
                "ideas based on those trends carry inflated match scores."
            )
        else:
            freshness_line = (
                "All watchlist trends are fresh; engagement band predictions reflect current velocity."
            )
        next_sample = (
            "re-run in 7 days to catch the next velocity cycle."
            if window == 7
            else "re-run in 14 days to build consecutive-window trend data."
        )

    return "\n".join([
        "## Trend Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {window_line}",
        f"- **Data source confidence**: {data_line}",
        f"- **Off-niche guard impact**: {exc_line}",
        f"- **Trend freshness**: {freshness_line}",
        f"- **Suggested next sample**: {next_sample}",
        "- **Re-run cadence**: weekly during active trend cycles, otherwise bi-weekly.",
    ])


def render_report(
    payload: dict,
    scores: TrendPlanScores,
    kept_ideas: list[PostIdea],
    excluded_ideas: list[PostIdea],
    watchlist: list[TrendEntry],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    is_demo: bool,
) -> str:
    all_stale = bool(watchlist) and all(e.is_stale for e in watchlist)
    sections = [
        _render_snapshot(payload, scores, excluded_ideas, is_demo),
        "",
        _render_plan_score(scores, is_demo, len(excluded_ideas)),
        "",
        _render_trend_watchlist(watchlist, is_demo),
        "",
        _render_post_ideas(kept_ideas, excluded_ideas, is_demo),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    audit_trigger = bool(excluded_ideas) or int(payload["window_days"]) == 7 or all_stale
    if audit_trigger:
        sections.extend([
            "",
            _render_trend_audit(payload, excluded_ideas, watchlist, is_demo),
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
        f"<!-- Generated by Trend-Aligned Poster (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — trend data stays on your machine. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_trend_aligned_poster(
    *,
    x_handle: str,
    trends_file: Optional[str] = None,
    window: int = 30,
    compare_to: str = "previous_period",
    niche_fit_floor: float = DEFAULT_NICHE_FIT_FLOOR,
    target_idea_count: int = DEFAULT_TARGET_IDEA_COUNT,
    demo_mode: Optional[str] = None,
) -> str:
    handle = normalize_handle(x_handle)
    if window not in WINDOW_OPTIONS:
        raise ValueError(f"window must be one of {WINDOW_OPTIONS}, got {window!r}")
    if compare_to not in COMPARE_OPTIONS:
        raise ValueError(f"compare_to must be one of {COMPARE_OPTIONS}, got {compare_to!r}")

    if trends_file:
        payload = load_trends_file(Path(trends_file).expanduser().resolve())
        is_demo = bool(payload.get("data_source") == "demo")
    elif demo_mode == "paradox":
        payload = json.loads(json.dumps(DEMO_PARADOX))
        is_demo = True
    elif demo_mode == "healthy":
        payload = json.loads(json.dumps(DEMO_HEALTHY))
        is_demo = True
    elif demo_mode == "7d":
        payload = json.loads(json.dumps(DEMO_7D))
        is_demo = True
    else:
        raise ValueError(
            "Provide --trends-file <path> or one of --demo / --demo-healthy / --demo-7d."
        )

    # CLI flags override payload meta
    payload["x_handle"]   = handle
    payload["window_days"] = window
    payload["compare_to"]  = compare_to

    ideas_raw  = payload.get("ideas", [])
    trends_raw = payload.get("trends", [])

    # Metrics and scoring
    metrics = compute_plan_metrics(payload)
    scores  = score_plan(metrics, niche_fit_floor)

    # Seeded RNG: sha256(handle + sorted-json + window); date excluded for reproducibility
    seed_str = handle + json.dumps(payload, sort_keys=True) + str(window)
    seed = hashlib.sha256(seed_str.encode("utf-8")).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))

    # Build watchlist
    watchlist = build_trend_watchlist(trends_raw, is_demo)

    # Build post ideas (with off-niche filter)
    kept_ideas, excluded_ideas = build_post_ideas(
        ideas_raw, niche_fit_floor, target_idea_count, is_demo
    )

    all_stale = bool(watchlist) and all(e.is_stale for e in watchlist)

    flags      = build_red_flags(scores, excluded_ideas, watchlist, window, niche_fit_floor)
    recs       = build_recommendations(rng, scores, kept_ideas, excluded_ideas, window)
    confidence = build_confidence(scores, excluded_ideas, all_stale, window, is_demo)

    return render_report(
        payload, scores, kept_ideas, excluded_ideas,
        watchlist, flags, recs, confidence, is_demo,
    )


generate = generate_trend_aligned_poster


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Trend-Aligned Poster (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Off-niche-guarded\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trend-aligned-poster",
        description=(
            "Read creator-supplied X trend data (or seeded demo trends) and emit a 7/8-section "
            "trend-aligned post plan with 4 official Trend Alignment Plan Score metrics, "
            "trend-chasing paradox detection, off-niche guard (trend_match >= 75 AND "
            "niche_fit < floor → excluded + Red Flag), 3–5 trend watchlist entries, "
            "4–6 post ideas with predicted engagement bands, and mandatory bridges to "
            "content-idea-generator + thread-builder. Drafts only. No financial content."
        ),
    )
    p.add_argument(
        "--handle", required=True,
        help="The creator's X handle (with or without leading @).",
    )
    p.add_argument(
        "--trends-file",
        help="Path to a JSON trend export. Required unless a --demo flag is passed.",
    )
    p.add_argument(
        "--days", "--window", dest="window", type=int, choices=list(WINDOW_OPTIONS),
        default=30,
        help="Period window in days (7, 30, or 90). 7d auto-triggers Trend Audit. Default 30.",
    )
    p.add_argument(
        "--compare-to", choices=list(COMPARE_OPTIONS), default="previous_period",
        help="Comparison basis for trend arrows. Default previous_period.",
    )
    p.add_argument(
        "--niche-fit-floor", type=float, default=DEFAULT_NICHE_FIT_FLOOR,
        help=(
            f"Niche fit threshold (0–100) below which the trend-chasing paradox fires "
            f"when average Trend match > {int(PARADOX_TREND_MATCH_THRESHOLD)} "
            f"(default {DEFAULT_NICHE_FIT_FLOOR}). Also governs the off-niche guard."
        ),
    )
    p.add_argument(
        "--target-idea-count", type=int, default=DEFAULT_TARGET_IDEA_COUNT,
        help=(
            f"Target number of post ideas to emit after the off-niche filter "
            f"(clamped to [{MIN_POST_IDEAS}, {MAX_POST_IDEAS}], default {DEFAULT_TARGET_IDEA_COUNT})."
        ),
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo", action="store_true",
        help="Run with the official trend-chasing paradox + off-niche guard demo trends.",
    )
    p.add_argument(
        "--demo-healthy", action="store_true",
        help="Run with healthy trend demo data (no paradox, no off-niche exclusion).",
    )
    p.add_argument(
        "--demo-7d", action="store_true",
        help="Run with 7-day window demo trends (auto-triggers Trend Audit + near-paradox watch).",
    )
    p.add_argument(
        "--show-system-prompt", action="store_true",
        help="Print system prompt path + size on stderr.",
    )
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
    elif args.demo_7d:
        demo_mode = "7d"
        # Auto-set window to 7 when demo-7d is used and the user didn't override
        if args.window == 30:
            args.window = 7

    if not args.trends_file and demo_mode is None:
        sys.stderr.write(
            "error: provide --trends-file <path> or one of --demo / --demo-healthy / --demo-7d.\n"
        )
        return 2

    rendered = generate_trend_aligned_poster(
        x_handle=args.handle,
        trends_file=args.trends_file,
        window=args.window,
        compare_to=args.compare_to,
        niche_fit_floor=args.niche_fit_floor,
        target_idea_count=args.target_idea_count,
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
            saved_file_header(normalize_handle(args.handle), when_full) + rendered,
            encoding="utf-8",
        )
        sys.stderr.write(f"[saved] {out_path}\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
