# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Content Idea Generator — runner.

CLI entry point for the ``content-idea-generator`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads creator-supplied performance + voice + trend signals (JSON) — or
seeded demo signals when no files are provided — and emits the strict
7/8-section idea batch defined by the system prompt:

  1. Idea Snapshot
  2. Idea Plan Score (4-row metric table + weighted score)
  3. Top-Performing Archetypes (informing this batch)
  4. Idea Cards (4-6 entries; voice-drift candidates flagged inline)
  5. Red Flags (2-4, surfaces derivative-and-thin paradox + voice-drift)
  6. Recommendations (3-5, mandatory bridges to analytics-summarizer
     and brand-voice-trainer)
  7. Confidence
  + Optional Idea Audit (auto-appended when window=7d, paradox fires,
    or every candidate scores below the originality floor)

Hard guarantees enforced by this runner (mirrors the system prompt):

* Drafts only — never auto-publishes.
* No fabricated statistics. Demo niche-fit / originality / voice-fidelity
  / engagement bands carry an explicit `[demo idea — re-run with
  --analytics-file / --voice-profile-file / --trend-signals-file for
  real X data]` label.
* Derivative-and-thin paradox surfaced in BOTH the Plan Score section
  AND the Red Flags section whenever average Originality < 40 AND
  average Voice fidelity < 60.
* Voice-drift surfacing — any individual idea with voice_fidelity_score
  < 50 stays in the batch but carries `⚠️ voice-drift candidate` and
  triggers a Red Flag with severity `medium`.
* Plan Score formula is fixed:
    round(0.30*NicheFit_norm + 0.25*Voice_norm +
          0.25*Originality_norm + 0.20*Engageability_norm).
* 5-arrow trend vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼).
* Unconditional bridges to analytics-summarizer (position 1) and
  brand-voice-trainer (position 2) in every Recommendations list.
* Privacy-first: source-post handles, raw post text, attachment URLs,
  and external links are never echoed.
* No finance / cashtag / sponsorship / harassment content.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic: seeded by sha256(handle + niche + tone + window + date).
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_post_idea_batch

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
    "Niche fit",
    "Voice fidelity",
    "Originality",
    "Engageability",
)

# Per the system prompt: Niche fit weighted highest because off-niche
# ideation dilutes the audience the creator built. Engageability lowest
# because predicted engagement is the most-uncertain forward signal.
PLAN_SCORE_WEIGHTS = {
    "Niche fit": 0.30,
    "Voice fidelity": 0.25,
    "Originality": 0.25,
    "Engageability": 0.20,
}

HEALTHY_RANGES = {
    "Niche fit": (60.0, 95.0),
    "Voice fidelity": (65.0, 95.0),
    "Originality": (50.0, 90.0),
    "Engageability": (50.0, 85.0),
}

WINDOW_OPTIONS = (7, 30, 90)
TONE_OPTIONS = ("punchy", "thoughtful", "data-led", "story-led", "playful")

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

# Derivative-and-thin paradox: avg Originality < 40 AND avg Voice fidelity < 60.
PARADOX_ORIGINALITY_THRESHOLD = 40.0
PARADOX_VOICE_THRESHOLD = 60.0

# Per-idea voice-drift surfacing: voice_fidelity_score < 50.
VOICE_DRIFT_THRESHOLD = 50.0

# Originality-floor audit trigger: every candidate < 50.
ORIGINALITY_AUDIT_FLOOR = 50.0

IDEA_COUNT_MIN = 4
IDEA_COUNT_MAX = 6
DEFAULT_TARGET_IDEA_COUNT = 5

VALID_FORMATS = ("single", "thread", "quote-tweet", "image-post", "reply-thread")
ENGAGEMENT_BANDS = ("low", "medium", "high", "breakout")

CROSS_TEMPLATE_BRIDGES = (
    "analytics-summarizer",   # mandatory position 1
    "brand-voice-trainer",    # mandatory position 2
    "thread-builder",
    "ab-test-suggester",
    "hashtag-strategy-advisor",
    "trend-aligned-poster",
    "content-recycler",
    "competitor-watch",
    "cross-platform-reposter",
    "mention-summarizer",
    "monetization-optimizer",
    "comment-engagement-booster",
)

MANDATORY_BRIDGES = ("analytics-summarizer", "brand-voice-trainer")

DEMO_LABEL = (
    "[demo idea — re-run with --analytics-file / --voice-profile-file / "
    "--trend-signals-file for real X data]"
)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "niche": "ai-agents",
    "tone": "thoughtful",
    "window": 30,
    "data_source": "demo",
    "previous_window_summary": {
        "avg_niche_fit_score": 80.0,
        "avg_voice_fidelity_score": 72.0,
        "avg_originality_score": 60.0,
        "avg_engageability_score": 60.0,
    },
    "top_archetypes": [
        {
            "archetype_label": "generic productivity tip",
            "format": "single",
            "rationale": "ranked top by impressions but flagged for low engagement rate (1.2%)",
        },
        {
            "archetype_label": "list of trending agent tools",
            "format": "thread",
            "rationale": "shipped twice; both runs read as familiar in the analytics archetype clusters",
        },
        {
            "archetype_label": "rephrased peer take on benchmark drift",
            "format": "quote-tweet",
            "rationale": "engagement above baseline but voice fidelity below the trainer floor",
        },
    ],
    "candidate_ideas": [
        {
            "format": "single",
            "copy_outline": "share a generic tip on agent ergonomics that any creator could publish",
            "niche_fit_score": 78,
            "originality_score": 30,
            "voice_fidelity_score": 48,
            "engageability_score": 62,
        },
        {
            "format": "thread",
            "copy_outline": "list five agent-tools without a unifying argument — pure curation, no shape",
            "niche_fit_score": 80,
            "originality_score": 32,
            "voice_fidelity_score": 50,
            "engageability_score": 58,
        },
        {
            "format": "quote-tweet",
            "copy_outline": "rephrase a peer's benchmark take with a softening adverb",
            "niche_fit_score": 76,
            "originality_score": 28,
            "voice_fidelity_score": 45,
            "engageability_score": 60,
        },
        {
            "format": "single",
            "copy_outline": "echo the consensus framing on a current AI debate",
            "niche_fit_score": 74,
            "originality_score": 35,
            "voice_fidelity_score": 52,
            "engageability_score": 55,
        },
        {
            "format": "image-post",
            "copy_outline": "share a stock-style infographic that does not carry the creator's tone",
            "niche_fit_score": 70,
            "originality_score": 38,
            "voice_fidelity_score": 55,
            "engageability_score": 58,
        },
        {
            "format": "reply-thread",
            "copy_outline": "polite, non-specific replies on three peer threads — no concrete experience added",
            "niche_fit_score": 72,
            "originality_score": 40,
            "voice_fidelity_score": 50,
            "engageability_score": 60,
        },
        {
            "format": "thread",
            "copy_outline": "summarise a familiar concept without adding the creator's experience",
            "niche_fit_score": 78,
            "originality_score": 32,
            "voice_fidelity_score": 55,
            "engageability_score": 62,
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "niche": "habit-design",
    "tone": "story-led",
    "window": 30,
    "data_source": "demo",
    "previous_window_summary": {
        "avg_niche_fit_score": 82.0,
        "avg_voice_fidelity_score": 80.0,
        "avg_originality_score": 70.0,
        "avg_engageability_score": 65.0,
    },
    "top_archetypes": [
        {
            "archetype_label": "personal anecdote on evening-friction audits",
            "format": "thread",
            "rationale": "engagement rate 6.8% — top archetype in the period's analytics",
        },
        {
            "archetype_label": "habit-stacking case study with concrete numbers",
            "format": "single",
            "rationale": "follower delta +1.4% on every ship; archetype carries authority",
        },
        {
            "archetype_label": "framework comparison from creator's own practice",
            "format": "thread",
            "rationale": "voice fidelity 92 — the trainer flags this as the creator's signature shape",
        },
    ],
    "candidate_ideas": [
        {
            "format": "thread",
            "copy_outline": "five-tweet thread on the evening-friction audit that surfaced the smallest fix that worked",
            "niche_fit_score": 90,
            "originality_score": 78,
            "voice_fidelity_score": 88,
            "engageability_score": 80,
        },
        {
            "format": "single",
            "copy_outline": "a one-paragraph lesson from a three-month habit stack with the retention numbers attached",
            "niche_fit_score": 92,
            "originality_score": 80,
            "voice_fidelity_score": 86,
            "engageability_score": 75,
        },
        {
            "format": "thread",
            "copy_outline": "compare two behaviour-design frameworks the creator has actually run, not just read",
            "niche_fit_score": 88,
            "originality_score": 82,
            "voice_fidelity_score": 90,
            "engageability_score": 70,
        },
        {
            "format": "quote-tweet",
            "copy_outline": "quote a paraphrased researcher post and add the practitioner-side counter-experience",
            "niche_fit_score": 80,
            "originality_score": 72,
            "voice_fidelity_score": 84,
            "engageability_score": 65,
        },
        {
            "format": "image-post",
            "copy_outline": "share the creator-drawn diagram of the friction-audit loop with an annotated caption",
            "niche_fit_score": 82,
            "originality_score": 75,
            "voice_fidelity_score": 80,
            "engageability_score": 60,
        },
    ],
}

DEMO_7D_AUDIT = {
    "x_handle": "@thindata",
    "niche": "applied-ml",
    "tone": "data-led",
    "window": 7,
    "data_source": "demo",
    "previous_window_summary": {
        "avg_niche_fit_score": 70.0,
        "avg_voice_fidelity_score": 70.0,
        "avg_originality_score": 60.0,
        "avg_engageability_score": 55.0,
    },
    "top_archetypes": [
        {
            "archetype_label": "headline-result interpretation of a fresh research paper",
            "format": "thread",
            "rationale": "tight-niche signal but only one ship in the 7d window — small sample",
        },
        {
            "archetype_label": "limitation callout on an under-discussed evaluation",
            "format": "single",
            "rationale": "engagement rate 4.4% in the 7d window — promising but noisy",
        },
    ],
    "candidate_ideas": [
        {
            "format": "thread",
            "copy_outline": "thread interpreting the paper's headline result in plain language",
            "niche_fit_score": 78,
            "originality_score": 65,
            "voice_fidelity_score": 76,
            "engageability_score": 60,
        },
        {
            "format": "single",
            "copy_outline": "single post calling out the under-discussed limitation in the paper's evaluation",
            "niche_fit_score": 80,
            "originality_score": 70,
            "voice_fidelity_score": 78,
            "engageability_score": 62,
        },
        {
            "format": "quote-tweet",
            "copy_outline": "quote a paraphrased launch announcement and surface the missing benchmark angle",
            "niche_fit_score": 70,
            "originality_score": 65,
            "voice_fidelity_score": 74,
            "engageability_score": 58,
        },
        {
            "format": "reply-thread",
            "copy_outline": "reply on three peer threads with the unaddressed methodological angle",
            "niche_fit_score": 76,
            "originality_score": 60,
            "voice_fidelity_score": 75,
            "engageability_score": 55,
        },
    ],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ContentIdeaGeneratorError(RuntimeError):
    """Raised for any creator-facing input or guard failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_handle(raw: str) -> str:
    handle = raw.strip().lstrip("@")
    if not handle:
        raise ContentIdeaGeneratorError("x_handle is required and cannot be empty.")
    if " " in handle or len(handle) > 15:
        raise ContentIdeaGeneratorError(
            f"x_handle {raw!r} is invalid — X handles are at most 15 chars, no spaces."
        )
    return f"@{handle}"


def _seed_from(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _utcnow_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalise_metric(value: float, metric: str) -> float:
    low, high = HEALTHY_RANGES[metric]
    if high <= low:
        return 0.0
    norm = (value - low) / (high - low) * 100.0
    return max(0.0, min(100.0, norm))


def _arrow_for_delta(curr: float, prev: float) -> str:
    if prev <= 0:
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


def _engagement_band_for(niche_fit: float, originality: float, voice: float, engageability: float) -> str:
    composite = 0.30 * niche_fit + 0.25 * originality + 0.25 * voice + 0.20 * engageability
    if composite >= 88:
        return "breakout"
    if composite >= 70:
        return "high"
    if composite >= 55:
        return "medium"
    return "low"


def _validate_window(window: int) -> int:
    if window not in WINDOW_OPTIONS:
        raise ContentIdeaGeneratorError(
            f"window={window!r} is invalid — choose one of {WINDOW_OPTIONS}."
        )
    return window


def _validate_tone(tone: str) -> str:
    if tone not in TONE_OPTIONS:
        raise ContentIdeaGeneratorError(
            f"tone={tone!r} is invalid — choose one of {TONE_OPTIONS}."
        )
    return tone


def _clamp_target_count(target: int) -> int:
    return max(IDEA_COUNT_MIN, min(IDEA_COUNT_MAX, int(target)))


# ---------------------------------------------------------------------------
# Forbidden-content scanner
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = (
    re.compile(r"\$[A-Z]{2,5}\b"),
    re.compile(r"\b(buy|sell|long|short)\s+\$"),
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
        raise ContentIdeaGeneratorError(
            f"refusing {label}: forbidden token(s) {flagged!r} (cashtag / "
            "investment / sponsorship / harassment content is not generated by this template)"
        )


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


@dataclass
class IdeaInput:
    x_handle: str
    niche: str
    tone: str
    window: int
    data_source: str
    target_idea_count: int
    candidate_ideas: list[dict]
    top_archetypes: list[dict]
    previous_window_summary: dict
    analytics_file: Optional[str] = None
    voice_profile_file: Optional[str] = None
    trend_signals_file: Optional[str] = None


def _load_demo(mode: str) -> dict:
    if mode == "paradox":
        return json.loads(json.dumps(DEMO_PARADOX))
    if mode == "healthy":
        return json.loads(json.dumps(DEMO_HEALTHY))
    if mode == "7d-audit":
        return json.loads(json.dumps(DEMO_7D_AUDIT))
    raise ContentIdeaGeneratorError(f"unknown demo mode {mode!r}")


def _validate_archetype(a: dict, idx: int) -> dict:
    required = ("archetype_label", "format", "rationale")
    missing = [k for k in required if k not in a]
    if missing:
        raise ContentIdeaGeneratorError(f"archetype[{idx}] missing keys: {missing}")
    if a["format"] not in VALID_FORMATS:
        raise ContentIdeaGeneratorError(
            f"archetype[{idx}].format={a['format']!r} invalid — choose {VALID_FORMATS}"
        )
    _refuse_if_forbidden(f"archetype[{idx}]", str(a.get("archetype_label", "")))
    return a


def _validate_idea(i: dict, idx: int) -> dict:
    required = (
        "format", "copy_outline",
        "niche_fit_score", "originality_score",
        "voice_fidelity_score", "engageability_score",
    )
    missing = [k for k in required if k not in i]
    if missing:
        raise ContentIdeaGeneratorError(f"idea[{idx}] missing keys: {missing}")
    if i["format"] not in VALID_FORMATS:
        raise ContentIdeaGeneratorError(
            f"idea[{idx}].format={i['format']!r} invalid — choose {VALID_FORMATS}"
        )
    for score_key in (
        "niche_fit_score", "originality_score",
        "voice_fidelity_score", "engageability_score",
    ):
        v = i[score_key]
        if not isinstance(v, (int, float)):
            raise ContentIdeaGeneratorError(
                f"idea[{idx}].{score_key} must be a number; got {type(v).__name__}"
            )
        if v < 0 or v > 100:
            raise ContentIdeaGeneratorError(
                f"idea[{idx}].{score_key}={v} outside 0-100"
            )
    _refuse_if_forbidden(f"idea[{idx}]", str(i.get("copy_outline", "")))
    return i


def _validate_input(payload: dict, args: argparse.Namespace) -> IdeaInput:
    handle = _normalise_handle(payload.get("x_handle", args.x_handle or ""))
    # niche: payload wins, else CLI, else "general creator"
    niche_raw = payload.get("niche") or args.niche or "general creator"
    niche = niche_raw.strip()[:80]
    _refuse_if_forbidden("niche", niche)
    tone_raw = payload.get("tone") or args.tone
    tone = _validate_tone(tone_raw)
    _refuse_if_forbidden("tone", tone)
    window = _validate_window(int(payload.get("window", args.window)))
    data_source = payload.get("data_source", "real")
    if data_source not in ("real", "demo"):
        raise ContentIdeaGeneratorError(
            f"data_source={data_source!r} invalid — choose 'real' or 'demo'"
        )

    # target count: --count and --target-idea-count are aliases.
    target = args.count if args.count is not None else args.target_idea_count
    target = _clamp_target_count(target if target is not None else DEFAULT_TARGET_IDEA_COUNT)

    archetypes_raw = payload.get("top_archetypes") or []
    if archetypes_raw:
        archetypes = [_validate_archetype(a, i) for i, a in enumerate(archetypes_raw)]
    else:
        archetypes = []

    ideas_raw = payload.get("candidate_ideas") or []
    if len(ideas_raw) < IDEA_COUNT_MIN:
        raise ContentIdeaGeneratorError(
            f"candidate_ideas count {len(ideas_raw)} below floor {IDEA_COUNT_MIN}"
        )
    ideas = [_validate_idea(i, idx) for idx, i in enumerate(ideas_raw)]

    return IdeaInput(
        x_handle=handle,
        niche=niche,
        tone=tone,
        window=window,
        data_source=data_source,
        target_idea_count=target,
        candidate_ideas=ideas,
        top_archetypes=archetypes,
        previous_window_summary=payload.get("previous_window_summary") or {},
        analytics_file=str(args.analytics_file) if args.analytics_file else None,
        voice_profile_file=str(args.voice_profile_file) if args.voice_profile_file else None,
        trend_signals_file=str(args.trend_signals_file) if args.trend_signals_file else None,
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass
class IdeaCard:
    raw: dict
    voice_drift: bool
    engagement_band: str


@dataclass
class PlanScore:
    metric_values: dict
    metric_arrows: dict
    plan_score: int
    paradox_active: bool
    avg_niche_fit: float
    avg_voice_fidelity: float
    avg_originality: float
    avg_engageability: float


def _annotate_ideas(ideas: list[dict]) -> list[IdeaCard]:
    out: list[IdeaCard] = []
    for i in ideas:
        drift = i["voice_fidelity_score"] < VOICE_DRIFT_THRESHOLD
        band = _engagement_band_for(
            i["niche_fit_score"],
            i["originality_score"],
            i["voice_fidelity_score"],
            i["engageability_score"],
        )
        out.append(IdeaCard(raw=i, voice_drift=drift, engagement_band=band))
    return out


def _select_top_ideas(annotated: list[IdeaCard], target: int) -> list[IdeaCard]:
    sortkey = lambda a: (
        -a.raw["niche_fit_score"],
        -a.raw["originality_score"],
        -a.raw["voice_fidelity_score"],
    )
    ranked = sorted(annotated, key=sortkey)
    n = min(IDEA_COUNT_MAX, max(IDEA_COUNT_MIN, target), len(ranked))
    return ranked[:n]


def _avg(items: list[float]) -> float:
    if not items:
        return 0.0
    return sum(items) / len(items)


def _compute_plan_score(annotated: list[IdeaCard]) -> PlanScore:
    pool = annotated
    nf = _avg([a.raw["niche_fit_score"] for a in pool])
    vf = _avg([a.raw["voice_fidelity_score"] for a in pool])
    org = _avg([a.raw["originality_score"] for a in pool])
    eng = _avg([a.raw["engageability_score"] for a in pool])

    metric_values = {
        "Niche fit": round(nf, 1),
        "Voice fidelity": round(vf, 1),
        "Originality": round(org, 1),
        "Engageability": round(eng, 1),
    }

    norms = {m: _normalise_metric(metric_values[m], m) for m in SCORE_METRICS}
    plan = round(
        PLAN_SCORE_WEIGHTS["Niche fit"] * norms["Niche fit"]
        + PLAN_SCORE_WEIGHTS["Voice fidelity"] * norms["Voice fidelity"]
        + PLAN_SCORE_WEIGHTS["Originality"] * norms["Originality"]
        + PLAN_SCORE_WEIGHTS["Engageability"] * norms["Engageability"]
    )

    paradox = (
        org < PARADOX_ORIGINALITY_THRESHOLD
        and vf < PARADOX_VOICE_THRESHOLD
    )

    return PlanScore(
        metric_values=metric_values,
        metric_arrows={},
        plan_score=plan,
        paradox_active=paradox,
        avg_niche_fit=nf,
        avg_voice_fidelity=vf,
        avg_originality=org,
        avg_engageability=eng,
    )


def _arrows_against_basis(score: PlanScore, prev: dict) -> dict:
    return {
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
        "Engageability": _arrow_for_delta(
            score.metric_values["Engageability"],
            float(prev.get("avg_engageability_score", score.metric_values["Engageability"])),
        ),
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _demo_suffix(data_source: str) -> str:
    return f" {DEMO_LABEL}" if data_source == "demo" else ""


def _interpretation_for(metric: str, value: float, score: PlanScore) -> str:
    if metric == "Niche fit":
        if value < 60:
            return "Below the 60 floor — ideas drift outside the niche the audience subscribed for."
        if value > 95:
            return "Tight niche alignment — every idea reads as on-brand for the audience."
        return "Niche fit holding — the batch lands inside the audience the prior window built."
    if metric == "Voice fidelity":
        if score.paradox_active and value < PARADOX_VOICE_THRESHOLD:
            return "Below the floor — copy outlines drift toward generic-helpful phrasing."
        if value > 95:
            return "Exceptional voice match — verify it isn't hiding generic-polish."
        if value > 65:
            return "Inside the healthy band; copy outlines preserve the creator's tone."
        return "Voice fidelity below the trainer floor — re-anchor with brand-voice-trainer before posting."
    if metric == "Originality":
        if score.paradox_active and value < PARADOX_ORIGINALITY_THRESHOLD:
            return "Derivative — the batch reads as familiar even before it ships."
        if value > 90:
            return "High originality — guard against sounding contrarian-for-its-own-sake."
        if value > 50:
            return "Originality acceptable — paired with niche fit, this is the core healthy band."
        return "Borderline — add a concrete creator experience to each draft before posting."
    if metric == "Engageability":
        if value < 50:
            return "Engageability prior is below the floor — outcome rests on fresh archetypes."
        if value > 85:
            return "High engageability prior — verify the prior is not over-fitted to one viral ship."
        return "Engageability prior is moderate; outcome rests on whether the rewrites land."
    return ""


def _render_snapshot(inp: IdeaInput, score: PlanScore) -> str:
    headline_bits = [f"{inp.niche} niche, {inp.tone} tone"]
    if score.paradox_active:
        headline_bits.append(
            f"derivative-and-thin paradox active; Originality {score.avg_originality:.1f} and Voice fidelity {score.avg_voice_fidelity:.1f}"
        )
    else:
        headline_bits.append(
            f"plan score {score.plan_score}/100; niche fit holding at {score.avg_niche_fit:.1f}"
        )
    headline = f"**{inp.x_handle}: " + " — ".join(headline_bits) + ".**"

    if inp.data_source == "demo":
        ds = "seeded demo signals — re-run with --analytics-file / --voice-profile-file / --trend-signals-file for real X data"
    else:
        files = []
        if inp.analytics_file:
            files.append(f"analytics={inp.analytics_file}")
        if inp.voice_profile_file:
            files.append(f"voice={inp.voice_profile_file}")
        if inp.trend_signals_file:
            files.append(f"trends={inp.trend_signals_file}")
        ds = "real X exports — " + (", ".join(files) if files else "(no files supplied)")

    body = [
        "## Idea Snapshot",
        headline,
        "",
        f"- **Creator handle**: {inp.x_handle}",
        f"- **Niche**: {inp.niche}",
        f"- **Tone**: {inp.tone}",
        f"- **Window**: {inp.window}d",
        f"- **Data source**: {ds}",
    ]
    return "\n".join(body)


def _render_plan_score(inp: IdeaInput, score: PlanScore, arrows: dict) -> str:
    lines = [
        "## Idea Plan Score",
        "",
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    for metric in SCORE_METRICS:
        v = score.metric_values[metric]
        arrow = arrows[metric]
        interp = _interpretation_for(metric, v, score)
        lines.append(f"| {metric} | {v}/100{suffix} | {arrow} | {interp} |")
    if score.paradox_active:
        lines.append("")
        lines.append(
            "> ⚠️ paradox: ideas score derivative AND thin — the batch would dilute "
            "the creator's unique shape into generic helpful posts."
        )
    lines.append("")
    lines.append(f"**Idea Plan Score**: {score.plan_score}/100")
    return "\n".join(lines)


def _render_archetypes(inp: IdeaInput) -> str:
    if not inp.top_archetypes:
        return (
            "## Top-Performing Archetypes (informing this batch)\n\n"
            "_(no archetype signals supplied — re-run with --analytics-file to surface period top archetypes)_"
        )
    lines = [
        "## Top-Performing Archetypes (informing this batch)",
        "",
        "| Archetype (paraphrased) | Format | Why it informs this batch |",
        "|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    for a in inp.top_archetypes[:4]:
        label = f"{a['archetype_label']}{suffix}"
        lines.append(f"| {label} | {a['format']} | {a['rationale']} |")
    return "\n".join(lines)


def _render_idea_cards(inp: IdeaInput, selected: list[IdeaCard], total: int) -> str:
    voice_drift_count = sum(1 for s in selected if s.voice_drift)
    note = ""
    if voice_drift_count > 0:
        note = f" — {voice_drift_count} voice-drift candidate(s) flagged inline"
    header = f"## Idea Cards ({len(selected)} of {total} candidate ideas{note})"
    lines = [header, ""]
    suffix = _demo_suffix(inp.data_source)
    for n, sc in enumerate(selected, start=1):
        idea = sc.raw
        bridge = "thread-builder" if idea["format"] == "thread" else "analytics-summarizer"
        drift_flag = " ⚠️ voice-drift candidate" if sc.voice_drift else ""
        lines.append(f"{n}. **{idea['format']}**{drift_flag} — {idea['copy_outline']}")
        lines.append(
            f"   niche fit: {idea['niche_fit_score']:.0f}/100{suffix} · "
            f"originality: {idea['originality_score']:.0f}/100{suffix} · "
            f"voice fidelity: {idea['voice_fidelity_score']:.0f}/100{suffix} · "
            f"engagement: {sc.engagement_band} · bridges to: `{bridge}`"
        )
    return "\n".join(lines)


def _render_red_flags(
    score: PlanScore,
    inp: IdeaInput,
    selected: list[IdeaCard],
    annotated: list[IdeaCard],
) -> str:
    flags: list[tuple[str, str, str, str]] = []  # (title, severity, line, remediation)

    if score.paradox_active:
        flags.append((
            "Derivative-and-thin paradox",
            "high",
            (
                f"Average originality {score.avg_originality:.1f} < 40 AND "
                f"average voice fidelity {score.avg_voice_fidelity:.1f} < 60 — "
                "the batch would dilute the creator's unique shape into generic helpful posts."
            ),
            (
                "Re-run with a richer voice profile from `brand-voice-trainer`, OR tighten "
                f"`--niche` to a sharper subset of '{inp.niche}' and wait one window for the "
                "creator's analytics to register a fresh archetype before re-batching."
            ),
        ))

    drift_count = sum(1 for s in selected if s.voice_drift)
    if drift_count > 0:
        flags.append((
            "Voice-drift candidates surfaced",
            "medium",
            (
                f"{drift_count} idea(s) score voice fidelity < 50 — they remain in the batch "
                "but are flagged inline so the creator rewrites before posting."
            ),
            "Hand each voice-drift candidate to brand-voice-trainer for a re-anchored draft before publishing.",
        ))

    # Originality floor
    all_below_originality_floor = all(
        a.raw["originality_score"] < ORIGINALITY_AUDIT_FLOOR for a in annotated
    )
    if all_below_originality_floor and len(annotated) > 0:
        flags.append((
            "Candidate pool uniformly thin",
            "high",
            (
                f"Every one of {len(annotated)} candidate ideas scored below the {int(ORIGINALITY_AUDIT_FLOOR)} "
                "originality floor — no idea card carries a unique creator-shape signal."
            ),
            "Pause this batch. Re-source archetypes from analytics-summarizer's top 10 by engagement "
            "rate before re-batching.",
        ))

    # Pool-too-small Red Flag — when fewer ideas than the target.
    if len(selected) < min(IDEA_COUNT_MIN, inp.target_idea_count):
        flags.append((
            "Idea pool below floor",
            "high",
            (
                f"Only {len(selected)} idea(s) selected out of a {inp.target_idea_count}-target — "
                f"candidate pool was {len(annotated)} (floor is {IDEA_COUNT_MIN})."
            ),
            "Add more candidate ideas to the input file, or relax the niche filter and re-run.",
        ))

    if not flags:
        flags.append((
            "No structural red flags",
            "low",
            "Plan stays within healthy bands; review remains creator-side qualitative judgement.",
            "Proceed; spot-check voice fidelity on the highest-engageability draft before posting.",
        ))

    lines = ["## Red Flags", ""]
    for title, sev, body, rem in flags:
        lines.append(f"- **{title}** · severity: {sev} — {body}. *Remediation:* {rem}")
    return "\n".join(lines)


def _render_recommendations(
    inp: IdeaInput,
    selected: list[IdeaCard],
    score: PlanScore,
) -> str:
    lines = ["## Recommendations", ""]

    # Position 1 — analytics-summarizer (mandatory)
    if score.paradox_active:
        lines.append(
            "1. Re-source the next batch from the period's highest-engagement archetype rather "
            "than this run's pool — current pool reads derivative. — bridges to: `analytics-summarizer`"
        )
    else:
        archetype_hint = (
            f"`{inp.top_archetypes[0]['archetype_label']}`"
            if inp.top_archetypes
            else "the period's top engagement-rate archetype"
        )
        lines.append(
            f"1. Source the next batch from {archetype_hint} — close the loop on which ideas "
            "actually shipped + landed. — bridges to: `analytics-summarizer`"
        )

    # Position 2 — brand-voice-trainer (mandatory)
    drift_count = sum(1 for s in selected if s.voice_drift)
    if drift_count > 0 or score.paradox_active:
        lines.append(
            f"2. Voice-check every draft before posting — {max(drift_count, 1)} candidate(s) "
            "flagged for drift; re-anchor them through the trainer before publishing. — bridges to: `brand-voice-trainer`"
        )
    else:
        lines.append(
            "2. Voice-check every draft before posting — the trainer's input signal is exactly "
            "this batch's voice fidelity floor. — bridges to: `brand-voice-trainer`"
        )

    # Position 3 — context-aware
    thread_ideas = [s for s in selected if s.raw["format"] == "thread"]
    if thread_ideas:
        top_thread = thread_ideas[0]
        outline = top_thread.raw["copy_outline"][:60]
        lines.append(
            f"3. Expand the highest niche-fit thread (`{outline}…`) into a structured "
            "long-form draft. — bridges to: `thread-builder`"
        )
    elif score.metric_values["Originality"] < 60:
        lines.append(
            "3. A/B test two variants of the highest-engageability format to isolate which copy "
            "axis carries weight before scaling the batch. — bridges to: `ab-test-suggester`"
        )
    else:
        lines.append(
            "3. Pair each card with a tag mix that matches both the niche surface and the "
            "predicted engagement band before publishing. — bridges to: `hashtag-strategy-advisor`"
        )

    # Position 4 — context-aware
    if score.metric_values["Engageability"] >= 70:
        lines.append(
            "4. Once the highest-engageability card lands, rotate it into the evergreen "
            "rotation for next quarter. — bridges to: `content-recycler`"
        )
    else:
        lines.append(
            "4. Confirm the chosen archetype is broadly relevant to the niche, not just one "
            "peer's surface, before scaling more cards. — bridges to: `competitor-watch`"
        )

    # Position 5 — niche cross-coverage
    lines.append(
        "5. When a trend window opens that fits any card's archetype, reuse the copy outline "
        "as a trend-aligned variant. — bridges to: `trend-aligned-poster`"
    )

    return "\n".join(lines)


def _render_confidence(
    inp: IdeaInput,
    score: PlanScore,
    selected: list[IdeaCard],
) -> str:
    drift_count = sum(1 for s in selected if s.voice_drift)
    if inp.data_source == "demo":
        level = "low"
        reason = (
            "demo signals only — re-run with --analytics-file / --voice-profile-file / "
            "--trend-signals-file pointing at real X exports. Plan Score and arrows are illustrative."
        )
    elif score.paradox_active:
        level = "low"
        reason = (
            "real signals, but derivative-and-thin paradox active — re-anchor voice + originality "
            "before treating the score as a publish signal."
        )
    elif drift_count > 0:
        level = "medium"
        reason = (
            f"real signals; {drift_count} voice-drift candidate(s) require trainer re-anchor "
            "before posting."
        )
    elif inp.window == 7:
        level = "medium"
        reason = "7d window over-indexes on single-day variance — re-run with 30d to confirm."
    else:
        level = "high"
        reason = "real signals, all metrics inside healthy bands, no drift surfaced."
    return f"## Confidence\nConfidence: {level} — {reason}"


def _render_audit(inp: IdeaInput, score: PlanScore, annotated: list[IdeaCard]) -> Optional[str]:
    triggers = []
    if inp.window == 7:
        triggers.append("window=7d — single-day variance dominates engagement reads")
    if score.paradox_active:
        triggers.append("derivative-and-thin paradox active")
    all_thin = all(a.raw["originality_score"] < ORIGINALITY_AUDIT_FLOOR for a in annotated)
    if all_thin and annotated:
        triggers.append("every candidate scored below the originality floor")

    if not triggers:
        return None

    drift_share = sum(1 for a in annotated if a.voice_drift) / max(1, len(annotated)) * 100.0
    thin_share = sum(
        1 for a in annotated if a.raw["originality_score"] < ORIGINALITY_AUDIT_FLOOR
    ) / max(1, len(annotated)) * 100.0

    lines = [
        "## Idea Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {inp.window}d window is "
        + ("under-powered for engageability priors" if inp.window == 7 else "adequate"),
        f"- **Data source confidence**: "
        + ("demo signals — re-run with real exports" if inp.data_source == "demo"
           else "real signals — proceed"),
        f"- **Originality floor impact**: {thin_share:.0f}% of candidates below the originality floor",
        f"- **Voice-drift signal**: {drift_share:.0f}% of candidates carry the drift flag — "
        + ("hand them to brand-voice-trainer before re-batching" if drift_share > 0
           else "no drift surfaced"),
        "- **Suggested next sample**: re-run after a 30d analytics window to refresh engageability priors",
        "- **Re-run cadence**: weekly during ideation sprints; otherwise tied to brand-voice-trainer cadence",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_post_idea_batch(
    *,
    x_handle: str,
    niche: Optional[str] = None,
    tone: str = "thoughtful",
    count: Optional[int] = None,
    trend_signals_file: Optional[str] = None,
    voice_profile_file: Optional[str] = None,
    analytics_file: Optional[str] = None,
    window: int = 30,
    target_idea_count: Optional[int] = None,
    payload: Optional[dict] = None,
    args: Optional[argparse.Namespace] = None,
) -> str:
    """Render the full idea batch markdown."""
    if args is None:
        args = argparse.Namespace(
            x_handle=x_handle,
            niche=niche,
            tone=tone,
            count=count,
            trend_signals_file=trend_signals_file,
            voice_profile_file=voice_profile_file,
            analytics_file=analytics_file,
            window=window,
            target_idea_count=target_idea_count,
        )
    inp = _validate_input(payload or {}, args)

    seed = _seed_from(
        inp.x_handle,
        inp.niche,
        inp.tone,
        str(inp.window),
        _utcnow_date(),
    )
    Random(seed)

    annotated = _annotate_ideas(inp.candidate_ideas)
    selected = _select_top_ideas(annotated, inp.target_idea_count)
    score = _compute_plan_score(annotated)
    arrows = _arrows_against_basis(score, inp.previous_window_summary)
    score.metric_arrows = arrows

    parts: list[str] = []
    parts.append(_render_snapshot(inp, score))
    parts.append(_render_plan_score(inp, score, arrows))
    parts.append(_render_archetypes(inp))
    parts.append(_render_idea_cards(inp, selected, len(inp.candidate_ideas)))
    parts.append(_render_red_flags(score, inp, selected, annotated))
    parts.append(_render_recommendations(inp, selected, score))
    parts.append(_render_confidence(inp, score, selected))
    audit = _render_audit(inp, score, annotated)
    if audit is not None:
        parts.append(audit)

    return "\n\n".join(parts) + "\n"


# Manifest alias
generate = generate_post_idea_batch


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_FILE_HEADER = (
    "<!-- Copyright 2026 AgentMindCloud -->\n"
    "<!-- Licensed under the Apache License, Version 2.0 -->\n"
    "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
    "<!-- Generated by content-idea-generator/run.py — built for X, Grok & the ecosystem community. -->\n"
    "\n"
)


def _maybe_load_payload(args: argparse.Namespace) -> Optional[dict]:
    if args.demo:
        return _load_demo("paradox")
    if args.demo_healthy:
        return _load_demo("healthy")
    if args.demo_7d_audit:
        return _load_demo("7d-audit")
    # Otherwise: build a minimal payload from any supplied files plus
    # CLI args. The user can supply 1-3 files in any combination.
    files_present = any((args.analytics_file, args.voice_profile_file, args.trend_signals_file))
    if not files_present:
        return None

    # Real-data path: aggregate signals from supplied files.
    payload: dict = {"data_source": "real"}
    if args.analytics_file:
        ap = Path(args.analytics_file)
        if not ap.exists():
            raise ContentIdeaGeneratorError(f"analytics_file {ap} does not exist")
        with ap.open("r", encoding="utf-8") as f:
            adata = json.load(f)
        # We expect the same shape analytics-summarizer consumes.
        if "top_content" in adata:
            payload["top_archetypes"] = [
                {
                    "archetype_label": item.get("archetype_label", "(unlabeled archetype)"),
                    "format": item.get("format", "single"),
                    "rationale": (
                        f"impression_share {item.get('impression_share_pct', '?')}% · "
                        f"engagement_rate {item.get('engagement_rate_pct', '?')}%"
                    ),
                }
                for item in adata.get("top_content", [])[:4]
            ]
    if args.trend_signals_file:
        tp = Path(args.trend_signals_file)
        if not tp.exists():
            raise ContentIdeaGeneratorError(f"trend_signals_file {tp} does not exist")
        with tp.open("r", encoding="utf-8") as f:
            tdata = json.load(f)
        # Lift candidate_ideas from the trend file when present (output of
        # trend-aligned-poster's plan).
        if "candidate_ideas" in tdata:
            payload["candidate_ideas"] = [
                {
                    "format": ci.get("format", "single"),
                    "copy_outline": ci.get("copy_outline", "(no outline)"),
                    "niche_fit_score": ci.get("niche_fit_score", 70),
                    "originality_score": ci.get("originality_score", 65),
                    "voice_fidelity_score": ci.get("voice_fidelity_score", 70),
                    "engageability_score": _engagement_band_to_score(ci.get("engagement_band", "medium")),
                }
                for ci in tdata["candidate_ideas"]
            ]
    if args.voice_profile_file:
        vp = Path(args.voice_profile_file)
        if not vp.exists():
            raise ContentIdeaGeneratorError(f"voice_profile_file {vp} does not exist")
        with vp.open("r", encoding="utf-8") as f:
            vdata = json.load(f)
        # Voice profile influences the data path more than the runner;
        # we surface it in the snapshot. No transformation needed beyond
        # confirming the file parses.
        if not isinstance(vdata, dict):
            raise ContentIdeaGeneratorError(
                f"voice_profile_file {vp} must contain a JSON object"
            )

    if "candidate_ideas" not in payload:
        # If only analytics was supplied, the user must also supply candidate
        # ideas in a separate file or via the trend signals file. Fall back
        # to demo if absolutely nothing is present.
        raise ContentIdeaGeneratorError(
            "no candidate_ideas could be sourced from the supplied files. "
            "Supply --trend-signals-file with candidate_ideas[], or use --demo."
        )

    return payload


def _engagement_band_to_score(band: str) -> int:
    return {"low": 45, "medium": 60, "high": 75, "breakout": 85}.get(band, 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="content-idea-generator",
        description=(
            "Local-first content idea generator for X creators. Drafts only — "
            "never auto-publishes. Built for X, Grok & the ecosystem community."
        ),
    )
    parser.add_argument("--x-handle", required=True, help="Creator's X handle.")
    parser.add_argument("--niche", default=None, help="Free-text niche (max 80 chars).")
    parser.add_argument(
        "--tone",
        default="thoughtful",
        choices=TONE_OPTIONS,
        help="Tone vector for the idea batch.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Target idea count, clamped to [4, 6].",
    )
    parser.add_argument(
        "--target-idea-count",
        type=int,
        default=DEFAULT_TARGET_IDEA_COUNT,
        help="Alias for --count (P12 starter compatibility).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=30,
        help="Period window in days (7 / 30 / 90).",
    )
    parser.add_argument("--analytics-file", default=None, help="Path to analytics export.")
    parser.add_argument("--voice-profile-file", default=None, help="Path to voice profile export.")
    parser.add_argument("--trend-signals-file", default=None, help="Path to trend signals export.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the derivative-and-thin paradox demo seed.",
    )
    parser.add_argument(
        "--demo-healthy",
        action="store_true",
        help="Run the all-within-bounds demo seed.",
    )
    parser.add_argument(
        "--demo-7d-audit",
        action="store_true",
        help="Run the window=7d demo seed that auto-triggers the Idea Audit.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Write to file (default stdout).")

    args = parser.parse_args(argv)

    selected_demos = sum(1 for f in (args.demo, args.demo_healthy, args.demo_7d_audit) if f)
    if selected_demos > 1:
        raise SystemExit("ERROR: choose at most one of --demo / --demo-healthy / --demo-7d-audit")

    payload = _maybe_load_payload(args)
    if args.demo_7d_audit:
        args.window = 7

    try:
        rendered = generate_post_idea_batch(
            x_handle=args.x_handle,
            niche=args.niche,
            tone=args.tone,
            count=args.count,
            trend_signals_file=args.trend_signals_file,
            voice_profile_file=args.voice_profile_file,
            analytics_file=args.analytics_file,
            window=args.window,
            target_idea_count=args.target_idea_count,
            payload=payload,
            args=args,
        )
    except ContentIdeaGeneratorError as exc:
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
