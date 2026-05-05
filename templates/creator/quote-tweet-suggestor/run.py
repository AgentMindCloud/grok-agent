# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Quote-Tweet Suggestor — runner.

CLI entry point for the ``quote-tweet-suggestor`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied source post (JSON) — or seeded demo source
when no file is provided — plus an optional voice profile, and emits
the strict 7/8-section variant plan defined by the system prompt:

  1. Source Snapshot
  2. Quote-Tweet Plan Score (4-row metric table + weighted score)
  3. Source-fit Profile
  4. Variants (4-6 entries; voice-drift candidates flagged inline)
  5. Red Flags (2-4, surfaces dunk-bait paradox + risk-exclude guard)
  6. Recommendations (3-5, mandatory bridges to brand-voice-trainer
     and content-idea-generator)
  7. Confidence
  + Optional Variant Audit (auto-appended when window=7d, risk-exclude
    guard fires, or paradox fires)

Hard guarantees:

* Drafts only — never auto-publishes.
* Never impersonate the source-post author or any third party.
* No fabricated statistics. Demo metrics carry an explicit
  `[demo variant — re-run with --source-post-file / --voice-profile-file
  for real X data]` label.
* Dunk-bait paradox surfaced in BOTH the Plan Score section AND the
  Red Flags section whenever average Engageability > 70 AND average
  Source-fit < 40.
* Risk-exclude guard: any variant with risk_score < risk_floor (default
  40) is excluded.
* Voice-drift surfacing — drafts with voice_fidelity_score < 50 stay
  in the plan but carry `⚠️ voice-drift candidate` inline.
* Plan Score formula:
    round(0.30*SourceFit_norm + 0.25*Voice_norm +
          0.25*Originality_norm + 0.20*Engageability_norm).
* 5-arrow trend vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼).
* Unconditional bridges to brand-voice-trainer (position 1) and
  content-idea-generator (position 2).
* Privacy-first: third-party @-handles, raw source-post text,
  attachment URLs, and external links are never echoed.
* No finance / cashtag / sponsorship / harassment / dunk-bait /
  impersonation content.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic: seeded by sha256(handle + source + window + date).
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_quote_tweet_variants

Built for X, Grok & the ecosystem community.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Optional

# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "prompts" / "system.md"

SCORE_METRICS = (
    "Source-fit",
    "Voice fidelity",
    "Originality",
    "Engageability",
)

PLAN_SCORE_WEIGHTS = {
    "Source-fit": 0.30,
    "Voice fidelity": 0.25,
    "Originality": 0.25,
    "Engageability": 0.20,
}

HEALTHY_RANGES = {
    "Source-fit": (60.0, 95.0),
    "Voice fidelity": (60.0, 95.0),
    "Originality": (50.0, 90.0),
    "Engageability": (50.0, 85.0),
}

WINDOW_OPTIONS = (7, 30, 90)

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

# Dunk-bait paradox thresholds.
PARADOX_ENGAGEABILITY_THRESHOLD = 70.0
PARADOX_SOURCE_FIT_THRESHOLD = 40.0

DEFAULT_RISK_FLOOR = 40.0
VOICE_DRIFT_THRESHOLD = 50.0

VARIANT_COUNT_MIN = 4
VARIANT_COUNT_MAX = 6
DEFAULT_MAX_VARIANTS = 5

VALID_FORMATS = ("single-quote", "thread-quote")
VALID_STANCES = (
    "agree-and-extend",
    "disagree-and-explain",
    "reframe",
    "add-data",
    "personal-reaction",
)
VALID_SOURCE_SENTIMENTS = ("positive", "neutral", "negative")
VALID_SOURCE_INTENTS = (
    "commentary", "question", "call-to-action", "personal-update", "data-share", "general",
)
ENGAGEMENT_BANDS = ("low", "medium", "high", "breakout")

CROSS_TEMPLATE_BRIDGES = (
    "brand-voice-trainer",
    "content-idea-generator",
    "thread-builder",
    "reply-drafter",
    "analytics-summarizer",
    "competitor-watch",
    "mention-summarizer",
    "ab-test-suggester",
    "hashtag-strategy-advisor",
)

MANDATORY_BRIDGES = ("brand-voice-trainer", "content-idea-generator")

DEMO_LABEL = (
    "[demo variant — re-run with --source-post-file / --voice-profile-file for real X data]"
)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "window": 30,
    "data_source": "demo",
    "source": {
        "paraphrased_excerpt": "paraphrased pitch of an open-source agent eval framework",
        "source_topic": "agent-eval-framework",
        "source_sentiment": "positive",
        "source_intent": "commentary",
        "source_argument": "the new framework lowers the eval-cost bar for indie agent builders",
    },
    "previous_window_summary": {
        "avg_source_fit_score": 70.0,
        "avg_voice_fidelity_score": 72.0,
        "avg_originality_score": 65.0,
        "avg_engageability_score": 70.0,
    },
    "candidate_variants": [
        {
            "format": "single-quote",
            "stance": "disagree-and-explain",
            "copy_outline": "snark on a tangential weakness in the framework's UI rather than the eval methodology",
            "source_fit_score": 25,
            "voice_fidelity_score": 65,
            "originality_score": 60,
            "engageability_score": 85,
            "risk_avoidance_score": 70,
        },
        {
            "format": "single-quote",
            "stance": "personal-reaction",
            "copy_outline": "lift a viral phrasing pattern unrelated to the source's actual argument",
            "source_fit_score": 30,
            "voice_fidelity_score": 70,
            "originality_score": 55,
            "engageability_score": 82,
            "risk_avoidance_score": 65,
        },
        {
            "format": "single-quote",
            "stance": "disagree-and-explain",
            "copy_outline": "publicly criticise the source author's track record instead of the framework",
            "source_fit_score": 20,
            "voice_fidelity_score": 60,
            "originality_score": 50,
            "engageability_score": 80,
            "risk_avoidance_score": 25,  # → risk-excluded
        },
        {
            "format": "thread-quote",
            "stance": "reframe",
            "copy_outline": "reframe the framework's contribution into the creator's own benchmark methodology",
            "source_fit_score": 45,
            "voice_fidelity_score": 75,
            "originality_score": 70,
            "engageability_score": 75,
            "risk_avoidance_score": 88,
        },
        {
            "format": "single-quote",
            "stance": "add-data",
            "copy_outline": "share a contrasting data point from the creator's own runs without engaging the source claim",
            "source_fit_score": 35,
            "voice_fidelity_score": 72,
            "originality_score": 65,
            "engageability_score": 76,
            "risk_avoidance_score": 80,
        },
        {
            "format": "single-quote",
            "stance": "agree-and-extend",
            "copy_outline": "agree at headline level and pivot to a self-promotion of the creator's own tooling",
            "source_fit_score": 38,
            "voice_fidelity_score": 60,
            "originality_score": 50,
            "engageability_score": 72,
            "risk_avoidance_score": 78,
        },
        {
            "format": "thread-quote",
            "stance": "personal-reaction",
            "copy_outline": "post a hostile pile-on attacking the source author's motives",
            "source_fit_score": 15,
            "voice_fidelity_score": 50,
            "originality_score": 40,
            "engageability_score": 78,
            "risk_avoidance_score": 20,  # → risk-excluded
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "window": 30,
    "data_source": "demo",
    "source": {
        "paraphrased_excerpt": "paraphrased thread on evening-friction audits in productivity stacks",
        "source_topic": "evening-friction-audit",
        "source_sentiment": "positive",
        "source_intent": "commentary",
        "source_argument": "the evening-friction audit surfaces the 1-2 sticking points that dominate next-morning behaviour",
    },
    "previous_window_summary": {
        "avg_source_fit_score": 80.0,
        "avg_voice_fidelity_score": 80.0,
        "avg_originality_score": 70.0,
        "avg_engageability_score": 65.0,
    },
    "candidate_variants": [
        {
            "format": "thread-quote",
            "stance": "agree-and-extend",
            "copy_outline": "extend the audit framework with the creator's own three-week measurement protocol",
            "source_fit_score": 90,
            "voice_fidelity_score": 88,
            "originality_score": 78,
            "engageability_score": 70,
            "risk_avoidance_score": 95,
        },
        {
            "format": "single-quote",
            "stance": "add-data",
            "copy_outline": "share the creator's own audit numbers from three months and how they confirm the source argument",
            "source_fit_score": 88,
            "voice_fidelity_score": 86,
            "originality_score": 75,
            "engageability_score": 68,
            "risk_avoidance_score": 95,
        },
        {
            "format": "single-quote",
            "stance": "reframe",
            "copy_outline": "reframe the audit pattern through a behaviour-design lens with concrete examples",
            "source_fit_score": 82,
            "voice_fidelity_score": 84,
            "originality_score": 80,
            "engageability_score": 65,
            "risk_avoidance_score": 92,
        },
        {
            "format": "thread-quote",
            "stance": "personal-reaction",
            "copy_outline": "personal-reaction thread on running the audit during a creator burnout stretch",
            "source_fit_score": 78,
            "voice_fidelity_score": 86,
            "originality_score": 76,
            "engageability_score": 60,
            "risk_avoidance_score": 90,
        },
        {
            "format": "single-quote",
            "stance": "agree-and-extend",
            "copy_outline": "agree and extend with a specific beginner trap the source did not mention",
            "source_fit_score": 80,
            "voice_fidelity_score": 82,
            "originality_score": 72,
            "engageability_score": 62,
            "risk_avoidance_score": 92,
        },
    ],
}

DEMO_7D_AUDIT = {
    "x_handle": "@thindata",
    "window": 7,
    "data_source": "demo",
    "source": {
        "paraphrased_excerpt": "paraphrased single post on a recent applied-ml benchmark divergence",
        "source_topic": "applied-ml-benchmark",
        "source_sentiment": "neutral",
        "source_intent": "data-share",
        "source_argument": "the benchmark's divergence is concentrated in the long-tail evaluation slice",
    },
    "previous_window_summary": {
        "avg_source_fit_score": 70.0,
        "avg_voice_fidelity_score": 72.0,
        "avg_originality_score": 64.0,
        "avg_engageability_score": 60.0,
    },
    "candidate_variants": [
        {
            "format": "single-quote",
            "stance": "add-data",
            "copy_outline": "share the creator's own divergence numbers on the same long-tail slice",
            "source_fit_score": 78,
            "voice_fidelity_score": 76,
            "originality_score": 65,
            "engageability_score": 60,
            "risk_avoidance_score": 88,
        },
        {
            "format": "thread-quote",
            "stance": "reframe",
            "copy_outline": "reframe the divergence through a methodology lens — what would change the result?",
            "source_fit_score": 80,
            "voice_fidelity_score": 75,
            "originality_score": 70,
            "engageability_score": 58,
            "risk_avoidance_score": 86,
        },
        {
            "format": "single-quote",
            "stance": "agree-and-extend",
            "copy_outline": "agree with the headline and extend with the second-order question the post leaves open",
            "source_fit_score": 76,
            "voice_fidelity_score": 74,
            "originality_score": 62,
            "engageability_score": 56,
            "risk_avoidance_score": 90,
        },
        {
            "format": "single-quote",
            "stance": "disagree-and-explain",
            "copy_outline": "respectfully push back on the divergence framing with a counter-example",
            "source_fit_score": 72,
            "voice_fidelity_score": 72,
            "originality_score": 60,
            "engageability_score": 55,
            "risk_avoidance_score": 84,
        },
    ],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class QuoteTweetSuggestorError(RuntimeError):
    """Raised for any creator-facing input or guard failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_handle(raw: str) -> str:
    handle = raw.strip().lstrip("@")
    if not handle:
        raise QuoteTweetSuggestorError("x_handle is required and cannot be empty.")
    if " " in handle or len(handle) > 15:
        raise QuoteTweetSuggestorError(
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


def _engagement_band_for(source_fit: float, voice: float, originality: float, engage: float) -> str:
    composite = 0.30 * source_fit + 0.25 * voice + 0.25 * originality + 0.20 * engage
    if composite >= 88:
        return "breakout"
    if composite >= 70:
        return "high"
    if composite >= 55:
        return "medium"
    return "low"


def _validate_window(window: int) -> int:
    if window not in WINDOW_OPTIONS:
        raise QuoteTweetSuggestorError(
            f"window={window!r} is invalid — choose one of {WINDOW_OPTIONS}."
        )
    return window


def _clamp_max_variants(target: int) -> int:
    return max(VARIANT_COUNT_MIN, min(VARIANT_COUNT_MAX, int(target)))


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

HANDLE_PATTERN = re.compile(r"@[A-Za-z0-9_]{1,15}\b")
URL_PATTERN = re.compile(r"https?://", re.I)


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
        raise QuoteTweetSuggestorError(
            f"refusing {label}: forbidden token(s) {flagged!r} (cashtag / "
            "investment / sponsorship / harassment content is not generated by this template)"
        )


def _refuse_if_privacy_leak(label: str, text: str, allow_creator_handle: str) -> None:
    handles = HANDLE_PATTERN.findall(text)
    creator_lower = allow_creator_handle.lower()
    third_party = [h for h in handles if h.lower() != creator_lower]
    if third_party:
        raise QuoteTweetSuggestorError(
            f"refusing {label}: third-party handle(s) {third_party!r} in paraphrased field. "
            "Replace with a paraphrased referent (e.g. 'the source author')."
        )
    if URL_PATTERN.search(text):
        raise QuoteTweetSuggestorError(
            f"refusing {label}: URL detected in paraphrased field. "
            "Replace with a paraphrased pointer (e.g. 'the source post')."
        )


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


@dataclass
class QuoteTweetInput:
    x_handle: str
    window: int
    data_source: str
    max_variants: int
    risk_floor: float
    source: dict
    candidate_variants: list[dict]
    previous_window_summary: dict
    source_post_file: Optional[str] = None
    voice_profile_file: Optional[str] = None


def _load_demo(mode: str) -> dict:
    if mode == "paradox":
        return json.loads(json.dumps(DEMO_PARADOX))
    if mode == "healthy":
        return json.loads(json.dumps(DEMO_HEALTHY))
    if mode == "7d-audit":
        return json.loads(json.dumps(DEMO_7D_AUDIT))
    raise QuoteTweetSuggestorError(f"unknown demo mode {mode!r}")


def _validate_source(s: dict, creator_handle: str) -> dict:
    required = ("paraphrased_excerpt", "source_topic", "source_sentiment", "source_intent")
    missing = [k for k in required if k not in s]
    if missing:
        raise QuoteTweetSuggestorError(f"source missing keys: {missing}")
    if s["source_sentiment"] not in VALID_SOURCE_SENTIMENTS:
        raise QuoteTweetSuggestorError(
            f"source.source_sentiment={s['source_sentiment']!r} invalid — choose {VALID_SOURCE_SENTIMENTS}"
        )
    if s["source_intent"] not in VALID_SOURCE_INTENTS:
        raise QuoteTweetSuggestorError(
            f"source.source_intent={s['source_intent']!r} invalid — choose {VALID_SOURCE_INTENTS}"
        )
    excerpt = str(s.get("paraphrased_excerpt", ""))
    _refuse_if_forbidden("source.paraphrased_excerpt", excerpt)
    _refuse_if_privacy_leak("source.paraphrased_excerpt", excerpt, creator_handle)
    s["paraphrased_excerpt"] = excerpt[:120]
    arg = str(s.get("source_argument", ""))
    if arg:
        _refuse_if_forbidden("source.source_argument", arg)
        _refuse_if_privacy_leak("source.source_argument", arg, creator_handle)
    return s


def _validate_variant(v: dict, idx: int, creator_handle: str) -> dict:
    required = (
        "format", "stance", "copy_outline",
        "source_fit_score", "voice_fidelity_score",
        "originality_score", "engageability_score", "risk_avoidance_score",
    )
    missing = [k for k in required if k not in v]
    if missing:
        raise QuoteTweetSuggestorError(f"variant[{idx}] missing keys: {missing}")
    if v["format"] not in VALID_FORMATS:
        raise QuoteTweetSuggestorError(
            f"variant[{idx}].format={v['format']!r} invalid — choose {VALID_FORMATS}"
        )
    if v["stance"] not in VALID_STANCES:
        raise QuoteTweetSuggestorError(
            f"variant[{idx}].stance={v['stance']!r} invalid — choose {VALID_STANCES}"
        )
    for score_key in (
        "source_fit_score", "voice_fidelity_score",
        "originality_score", "engageability_score", "risk_avoidance_score",
    ):
        sv = v[score_key]
        if not isinstance(sv, (int, float)):
            raise QuoteTweetSuggestorError(
                f"variant[{idx}].{score_key} must be a number; got {type(sv).__name__}"
            )
        if sv < 0 or sv > 100:
            raise QuoteTweetSuggestorError(
                f"variant[{idx}].{score_key}={sv} outside 0-100"
            )
    outline = str(v.get("copy_outline", ""))
    _refuse_if_forbidden(f"variant[{idx}].copy_outline", outline)
    _refuse_if_privacy_leak(f"variant[{idx}].copy_outline", outline, creator_handle)
    return v


def _validate_input(payload: dict, args: argparse.Namespace) -> QuoteTweetInput:
    handle = _normalise_handle(payload.get("x_handle", args.x_handle or ""))
    window = _validate_window(int(payload.get("window", args.window)))
    data_source = payload.get("data_source", "real")
    if data_source not in ("real", "demo"):
        raise QuoteTweetSuggestorError(
            f"data_source={data_source!r} invalid — choose 'real' or 'demo'"
        )

    source_raw = payload.get("source") or {}
    if not source_raw:
        raise QuoteTweetSuggestorError("source object is required")
    source = _validate_source(source_raw, handle)

    variants_raw = payload.get("candidate_variants") or []
    if len(variants_raw) < VARIANT_COUNT_MIN:
        raise QuoteTweetSuggestorError(
            f"candidate_variants count {len(variants_raw)} below floor {VARIANT_COUNT_MIN}"
        )
    variants = [_validate_variant(v, idx, handle) for idx, v in enumerate(variants_raw)]

    return QuoteTweetInput(
        x_handle=handle,
        window=window,
        data_source=data_source,
        max_variants=_clamp_max_variants(args.max_variants),
        risk_floor=float(args.risk_floor),
        source=source,
        candidate_variants=variants,
        previous_window_summary=payload.get("previous_window_summary") or {},
        source_post_file=str(args.source_post_file) if args.source_post_file else None,
        voice_profile_file=str(args.voice_profile_file) if args.voice_profile_file else None,
    )


# ---------------------------------------------------------------------------
# Risk-exclude guard + scoring
# ---------------------------------------------------------------------------


@dataclass
class VariantCard:
    raw: dict
    excluded: bool
    excluded_reason: Optional[str]
    voice_drift: bool
    engagement_band: str


@dataclass
class PlanScore:
    metric_values: dict
    metric_arrows: dict
    plan_score: int
    paradox_active: bool
    avg_source_fit: float
    avg_voice: float
    avg_originality: float
    avg_engageability: float


def _annotate_variants(variants: list[dict], risk_floor: float) -> tuple[list[VariantCard], int]:
    annotated: list[VariantCard] = []
    excluded = 0
    for v in variants:
        if v["risk_avoidance_score"] < risk_floor:
            annotated.append(
                VariantCard(
                    raw=v,
                    excluded=True,
                    excluded_reason=(
                        f"risk_score {v['risk_avoidance_score']:.0f} < risk_floor {int(risk_floor)}"
                    ),
                    voice_drift=False,
                    engagement_band="low",
                )
            )
            excluded += 1
        else:
            drift = v["voice_fidelity_score"] < VOICE_DRIFT_THRESHOLD
            band = _engagement_band_for(
                v["source_fit_score"],
                v["voice_fidelity_score"],
                v["originality_score"],
                v["engageability_score"],
            )
            annotated.append(
                VariantCard(
                    raw=v,
                    excluded=False,
                    excluded_reason=None,
                    voice_drift=drift,
                    engagement_band=band,
                )
            )
    return annotated, excluded


def _select_variants(annotated: list[VariantCard], target: int) -> list[VariantCard]:
    eligible = [a for a in annotated if not a.excluded]
    eligible.sort(
        key=lambda a: (
            -a.raw["source_fit_score"],
            -a.raw["voice_fidelity_score"],
            -a.raw["originality_score"],
        )
    )
    n = min(VARIANT_COUNT_MAX, max(VARIANT_COUNT_MIN, target), len(eligible))
    return eligible[:n]


def _avg(items: list[float]) -> float:
    if not items:
        return 0.0
    return sum(items) / len(items)


def _compute_plan_score(annotated: list[VariantCard]) -> PlanScore:
    pool = annotated  # full candidate pool drives the period averages
    sf = _avg([a.raw["source_fit_score"] for a in pool])
    vf = _avg([a.raw["voice_fidelity_score"] for a in pool])
    org = _avg([a.raw["originality_score"] for a in pool])
    eng = _avg([a.raw["engageability_score"] for a in pool])

    metric_values = {
        "Source-fit": round(sf, 1),
        "Voice fidelity": round(vf, 1),
        "Originality": round(org, 1),
        "Engageability": round(eng, 1),
    }

    norms = {m: _normalise_metric(metric_values[m], m) for m in SCORE_METRICS}
    plan = round(
        PLAN_SCORE_WEIGHTS["Source-fit"] * norms["Source-fit"]
        + PLAN_SCORE_WEIGHTS["Voice fidelity"] * norms["Voice fidelity"]
        + PLAN_SCORE_WEIGHTS["Originality"] * norms["Originality"]
        + PLAN_SCORE_WEIGHTS["Engageability"] * norms["Engageability"]
    )

    paradox = (
        eng > PARADOX_ENGAGEABILITY_THRESHOLD
        and sf < PARADOX_SOURCE_FIT_THRESHOLD
    )

    return PlanScore(
        metric_values=metric_values,
        metric_arrows={},
        plan_score=plan,
        paradox_active=paradox,
        avg_source_fit=sf,
        avg_voice=vf,
        avg_originality=org,
        avg_engageability=eng,
    )


def _arrows_against_basis(score: PlanScore, prev: dict) -> dict:
    return {
        "Source-fit": _arrow_for_delta(
            score.metric_values["Source-fit"],
            float(prev.get("avg_source_fit_score", score.metric_values["Source-fit"])),
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


def _interpretation_for(metric: str, value: float, score: PlanScore, excluded_count: int) -> str:
    if metric == "Source-fit":
        if score.paradox_active and value < PARADOX_SOURCE_FIT_THRESHOLD:
            return "Below the 40 floor; variants drift away from the source's argument toward generic creator commentary."
        if value > 95:
            return "Source-fit excellent — variants engage the source's actual argument."
        if value > 60:
            return "Source-fit in the healthy band — variants land inside the source's argument."
        return "Source-fit borderline — verify each variant engages the source claim before posting."
    if metric == "Voice fidelity":
        if value > 95:
            return "Exceptional voice match — verify it isn't hiding generic-polish."
        if value > 60:
            return "Inside the healthy band; variants preserve the creator's tone."
        return "Voice fidelity below the floor — re-anchor with brand-voice-trainer before posting."
    if metric == "Originality":
        if score.paradox_active:
            return "Originality acceptable — but originality without source-fit produces dunk-bait."
        if value > 90:
            return "High originality — paired with source-fit, this is the strongest variant shape."
        if value > 50:
            return "Originality acceptable — paired with source-fit, this is the core healthy band."
        return "Borderline — variants risk reading as derivative restatements of the source."
    if metric == "Engageability":
        if score.paradox_active and value > PARADOX_ENGAGEABILITY_THRESHOLD:
            return "High engageability — exactly the dunk-bait failure pattern."
        if value > 85:
            return "High engageability prior — verify no dunk-bait masking."
        if value > 50:
            return "Engageability prior is moderate; outcome rests on whether the source-fit holds."
        return "Engageability prior is low — variant set may need a tighter source-fit angle."
    return ""


def _render_snapshot(inp: QuoteTweetInput, score: PlanScore) -> str:
    headline_bits = [f"source post on {inp.source['source_topic']}"]
    if score.paradox_active:
        headline_bits.append(
            f"dunk-bait paradox active; Engageability {score.avg_engageability:.1f} but Source-fit only {score.avg_source_fit:.1f}"
        )
    else:
        headline_bits.append(
            f"plan score {score.plan_score}/100; source-fit holding at {score.avg_source_fit:.1f}"
        )
    headline = f"**{inp.x_handle}: " + " — ".join(headline_bits) + ".**"

    if inp.data_source == "demo":
        ds = "seeded demo source — re-run with --source-post-file for real X data"
    else:
        ds = f"real X export from --source-post-file {inp.source_post_file}"

    body = [
        "## Source Snapshot",
        headline,
        "",
        f"- **Creator handle**: {inp.x_handle}",
        f"- **Source post**: {inp.source['paraphrased_excerpt']}{_demo_suffix(inp.data_source)}",
        f"- **Source topic**: {inp.source['source_topic']}",
        f"- **Source sentiment / intent**: {inp.source['source_sentiment']} / {inp.source['source_intent']}",
        f"- **Window**: {inp.window}d",
        f"- **Data source**: {ds}",
    ]
    return "\n".join(body)


def _render_plan_score(inp: QuoteTweetInput, score: PlanScore, arrows: dict, excluded_count: int) -> str:
    lines = [
        "## Quote-Tweet Plan Score",
        "",
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    for metric in SCORE_METRICS:
        v = score.metric_values[metric]
        arrow = arrows[metric]
        interp = _interpretation_for(metric, v, score, excluded_count)
        lines.append(f"| {metric} | {v}/100{suffix} | {arrow} | {interp} |")
    if score.paradox_active:
        lines.append("")
        lines.append(
            "> ⚠️ paradox: variants score high on engageability but low on source-fit — "
            "this is the dunk-bait pattern, where engagement comes from gotchas rather than "
            "substantive engagement with the source."
        )
    lines.append("")
    lines.append(f"**Quote-Tweet Plan Score**: {score.plan_score}/100")
    return "\n".join(lines)


def _render_source_profile(inp: QuoteTweetInput) -> str:
    s = inp.source
    arg = s.get("source_argument", "(not supplied)")
    return "\n".join([
        "## Source-fit Profile",
        "",
        f"- **Source argument (paraphrased)**: {arg}{_demo_suffix(inp.data_source)}",
        f"- **Source sentiment**: {s['source_sentiment']}",
        f"- **Source intent**: {s['source_intent']}",
        "- **Quote-tweet stance options**: agree-and-extend / disagree-and-explain / reframe / add-data / personal-reaction",
    ])


def _render_variants(inp: QuoteTweetInput, selected: list[VariantCard], excluded_count: int) -> str:
    note = ""
    if excluded_count > 0:
        note = f" — {excluded_count} high-risk variant(s) excluded — see Red Flags"
    drift = sum(1 for s in selected if s.voice_drift)
    if drift > 0:
        note += f" — {drift} voice-drift candidate(s) flagged inline"
    header = f"## Variants ({len(selected)} of {len(inp.candidate_variants)} candidate variants{note})"
    lines = [header, ""]
    suffix = _demo_suffix(inp.data_source)
    for n, sc in enumerate(selected, start=1):
        v = sc.raw
        if v["format"] == "thread-quote":
            bridge = "thread-builder"
        else:
            # Single-quote: route to content-idea-generator when source-fit is borderline
            # (signals a content-gap), otherwise brand-voice-trainer.
            bridge = "content-idea-generator" if v["source_fit_score"] < 70 else "brand-voice-trainer"
        drift_flag = " ⚠️ voice-drift candidate" if sc.voice_drift else ""
        lines.append(
            f"{n}. **{v['format']}**{drift_flag} · stance: {v['stance']}"
        )
        lines.append(f"   draft outline: {v['copy_outline']}")
        lines.append(
            f"   source-fit: {v['source_fit_score']:.0f}/100{suffix} · "
            f"voice fidelity: {v['voice_fidelity_score']:.0f}/100 · "
            f"originality: {v['originality_score']:.0f}/100 · "
            f"engageability: {v['engageability_score']:.0f}/100 · "
            f"risk: {v['risk_avoidance_score']:.0f}/100 · "
            f"engagement: {sc.engagement_band} · bridges to: `{bridge}`"
        )
    return "\n".join(lines)


def _render_red_flags(
    score: PlanScore,
    inp: QuoteTweetInput,
    selected: list[VariantCard],
    annotated: list[VariantCard],
    excluded_count: int,
) -> str:
    flags: list[tuple[str, str, str, str]] = []

    if score.paradox_active:
        flags.append((
            "Dunk-bait paradox",
            "high",
            (
                f"Average engageability {score.avg_engageability:.1f} > 70 while "
                f"average source-fit {score.avg_source_fit:.1f} < 40 — engagement would "
                "come from gotchas rather than substantive engagement with the source."
            ),
            (
                "Re-run with a richer voice profile from `brand-voice-trainer` to surface "
                "non-dunk variants, OR skip this source post — when the source-fit floor "
                "cannot be met, the right move is not to quote-tweet at all."
            ),
        ))

    if excluded_count > 0:
        excluded_variants = [a for a in annotated if a.excluded]
        risk_summary = "; ".join(
            f"variant {i}: {a.raw['stance']} risk {a.raw['risk_avoidance_score']:.0f}"
            for i, a in enumerate(excluded_variants[:3])
        )
        flags.append((
            "High-risk variants excluded",
            "high",
            (
                f"{excluded_count} variant(s) excluded for risk_score below floor "
                f"({risk_summary}). They do not occupy any of the {VARIANT_COUNT_MIN}-{VARIANT_COUNT_MAX} "
                "variants slots."
            ),
            (
                "Do not retroactively add the excluded variants back into the queue. "
                "If the source post still warrants a response, hand the source paraphrase to "
                "`content-idea-generator` for a standalone post instead of a quote-tweet."
            ),
        ))

    drift_count = sum(1 for s in selected if s.voice_drift)
    if drift_count > 0:
        flags.append((
            "Voice-drift candidates surfaced",
            "medium",
            (
                f"{drift_count} variant(s) score voice fidelity < 50 — they remain in the plan "
                "but are flagged inline so the creator rewrites before posting."
            ),
            "Hand each voice-drift variant to brand-voice-trainer for a re-anchored draft.",
        ))

    if len(selected) < VARIANT_COUNT_MIN:
        flags.append((
            "Variants below floor",
            "high",
            (
                f"Only {len(selected)} variant(s) selected after risk-exclude guard — eligible "
                f"pool was insufficient for the {VARIANT_COUNT_MIN} floor."
            ),
            "Lower --risk-floor or supply more candidate variants in --source-post-file.",
        ))

    if not flags:
        flags.append((
            "No structural red flags",
            "low",
            "Plan stays within healthy bands; review remains creator-side qualitative judgement.",
            "Proceed; spot-check voice fidelity on the highest-source-fit variant before posting.",
        ))

    lines = ["## Red Flags", ""]
    for title, sev, body, rem in flags:
        lines.append(f"- **{title}** · severity: {sev} — {body}. *Remediation:* {rem}")
    return "\n".join(lines)


def _render_recommendations(
    inp: QuoteTweetInput,
    selected: list[VariantCard],
    score: PlanScore,
    excluded_count: int,
) -> str:
    lines = ["## Recommendations", ""]

    # Position 1 — brand-voice-trainer (mandatory)
    if score.paradox_active:
        lines.append(
            "1. Voice-check every variant with a richer profile before posting — paradox "
            "active means dunk-bait risk is high. — bridges to: `brand-voice-trainer`"
        )
    else:
        lines.append(
            "1. Voice-check every variant before posting — quote-tweets are exposed to drift "
            "because the source's tone tugs the variant off-voice. — bridges to: `brand-voice-trainer`"
        )

    # Position 2 — content-idea-generator (mandatory)
    if score.paradox_active or excluded_count > 0:
        lines.append(
            "2. When the source post warrants a response but the variant set fails source-fit, "
            "hand the source paraphrase to content-idea-generator for a standalone post instead "
            "of a quote-tweet. — bridges to: `content-idea-generator`"
        )
    else:
        lines.append(
            "2. When the source surfaces a recurring content gap, source the next anchor post "
            "from the gap rather than just quote-tweeting. — bridges to: `content-idea-generator`"
        )

    # Position 3 — context-aware
    thread_q = [s for s in selected if s.raw["format"] == "thread-quote"]
    if thread_q:
        lines.append(
            "3. Expand the highest-source-fit thread-quote into a structured long-form draft "
            "when the response warrants standalone amplification. — bridges to: `thread-builder`"
        )
    else:
        lines.append(
            "3. When a single-quote would land better as a reply (low source-fit but high "
            "reply-fit), route to the reply drafter instead. — bridges to: `reply-drafter`"
        )

    # Position 4 — context-aware
    if score.metric_values["Engageability"] >= 70 and not score.paradox_active:
        lines.append(
            "4. A/B test agree-and-extend vs reframe variants on similar sources to isolate "
            "which stance carries weight. — bridges to: `ab-test-suggester`"
        )
    else:
        lines.append(
            "4. Confirm the source post is broadly relevant to the niche before scaling more "
            "variants on similar sources. — bridges to: `competitor-watch`"
        )

    # Position 5 — measurement
    lines.append(
        "5. Correlate post-publish engagement deltas with the period's analytics next window "
        "to confirm the variant set landed. — bridges to: `analytics-summarizer`"
    )

    return "\n".join(lines)


def _render_confidence(
    inp: QuoteTweetInput,
    score: PlanScore,
    selected: list[VariantCard],
    excluded_count: int,
) -> str:
    drift_count = sum(1 for s in selected if s.voice_drift)
    if inp.data_source == "demo":
        level = "low"
        reason = (
            "demo source only — re-run with --source-post-file pointing at a real X export "
            "and --voice-profile-file from brand-voice-trainer. Plan Score is illustrative."
        )
    elif score.paradox_active:
        level = "low"
        reason = (
            "real source, but dunk-bait paradox active — skip this quote-tweet target or "
            "re-anchor voice before treating the score as a publish signal."
        )
    elif excluded_count > 0:
        level = "medium"
        reason = (
            f"real source; {excluded_count} variant(s) excluded by risk guard — verify "
            "the surviving set before posting."
        )
    elif drift_count > 0:
        level = "medium"
        reason = (
            f"real source; {drift_count} voice-drift candidate(s) require trainer re-anchor."
        )
    elif inp.window == 7:
        level = "medium"
        reason = "7d window over-indexes on single-day variance — verify next window."
    else:
        level = "high"
        reason = "real source, all metrics inside healthy bands, no exclusions."
    return f"## Confidence\nConfidence: {level} — {reason}"


def _render_audit(
    inp: QuoteTweetInput, score: PlanScore, annotated: list[VariantCard], excluded_count: int
) -> Optional[str]:
    triggers = []
    if inp.window == 7:
        triggers.append("window=7d — single-day variance dominates engagement priors")
    if excluded_count > 0:
        triggers.append("risk-exclude guard fired")
    if score.paradox_active:
        triggers.append("dunk-bait paradox active")

    if not triggers:
        return None

    drift_share = sum(1 for a in annotated if a.voice_drift) / max(1, len(annotated)) * 100.0

    lines = [
        "## Variant Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {inp.window}d window is "
        + ("under-powered for engagement priors" if inp.window == 7 else "adequate"),
        f"- **Data source confidence**: "
        + ("demo source — re-run with real export" if inp.data_source == "demo"
           else "real source — proceed"),
        f"- **Risk-exclude impact**: "
        + (f"{excluded_count} variant(s) excluded" if excluded_count > 0 else "none excluded"),
        f"- **Voice-drift signal**: {drift_share:.0f}% of variants carry the drift flag — "
        + ("hand them to brand-voice-trainer before posting" if drift_share > 0
           else "no drift surfaced"),
        "- **Suggested next sample**: skip this source post and surface a fresh quote-tweet target via mention-summarizer",
        "- **Re-run cadence**: ad-hoc per source post; never run a quote-tweet template on a schedule",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_quote_tweet_variants(
    *,
    x_handle: str,
    source_post_file: Optional[str] = None,
    voice_profile_file: Optional[str] = None,
    max_variants: int = DEFAULT_MAX_VARIANTS,
    window: int = 30,
    risk_floor: float = DEFAULT_RISK_FLOOR,
    payload: Optional[dict] = None,
    args: Optional[argparse.Namespace] = None,
) -> str:
    if args is None:
        args = argparse.Namespace(
            x_handle=x_handle,
            source_post_file=source_post_file,
            voice_profile_file=voice_profile_file,
            max_variants=max_variants,
            window=window,
            risk_floor=risk_floor,
        )
    inp = _validate_input(payload or {}, args)

    seed = _seed_from(
        inp.x_handle,
        inp.source["source_topic"],
        str(inp.window),
        _utcnow_date(),
    )
    Random(seed)

    annotated, excluded_count = _annotate_variants(inp.candidate_variants, inp.risk_floor)
    selected = _select_variants(annotated, inp.max_variants)
    score = _compute_plan_score(annotated)
    arrows = _arrows_against_basis(score, inp.previous_window_summary)
    score.metric_arrows = arrows

    parts: list[str] = []
    parts.append(_render_snapshot(inp, score))
    parts.append(_render_plan_score(inp, score, arrows, excluded_count))
    parts.append(_render_source_profile(inp))
    parts.append(_render_variants(inp, selected, excluded_count))
    parts.append(_render_red_flags(score, inp, selected, annotated, excluded_count))
    parts.append(_render_recommendations(inp, selected, score, excluded_count))
    parts.append(_render_confidence(inp, score, selected, excluded_count))
    audit = _render_audit(inp, score, annotated, excluded_count)
    if audit is not None:
        parts.append(audit)

    return "\n\n".join(parts) + "\n"


generate = generate_quote_tweet_variants


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_FILE_HEADER = (
    "<!-- Copyright 2026 AgentMindCloud -->\n"
    "<!-- Licensed under the Apache License, Version 2.0 -->\n"
    "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
    "<!-- Generated by quote-tweet-suggestor/run.py — built for X, Grok & the ecosystem community. -->\n"
    "\n"
)


def _maybe_load_payload(args: argparse.Namespace) -> Optional[dict]:
    if args.demo:
        return _load_demo("paradox")
    if args.demo_healthy:
        return _load_demo("healthy")
    if args.demo_7d_audit:
        return _load_demo("7d-audit")
    if args.source_post_file:
        p = Path(args.source_post_file)
        if not p.exists():
            raise QuoteTweetSuggestorError(f"source_post_file {p} does not exist")
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quote-tweet-suggestor",
        description=(
            "Local-first quote-tweet suggestor for X creators. Drafts only — never auto-publishes. "
            "Built for X, Grok & the ecosystem community."
        ),
    )
    parser.add_argument("--x-handle", required=True, help="Creator's X handle.")
    parser.add_argument("--source-post-file", default=None, help="Path to source post JSON.")
    parser.add_argument("--voice-profile-file", default=None, help="Path to voice profile JSON.")
    parser.add_argument(
        "--max-variants",
        type=int,
        default=DEFAULT_MAX_VARIANTS,
        help="Target variant count, clamped to [4, 6].",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=30,
        help="Comparison window in days (7 / 30 / 90).",
    )
    parser.add_argument(
        "--risk-floor",
        type=float,
        default=DEFAULT_RISK_FLOOR,
        help="Risk avoidance threshold below which a variant is excluded (default 40).",
    )
    parser.add_argument("--demo", action="store_true", help="Run dunk-bait paradox + risk-exclude demo seed.")
    parser.add_argument("--demo-healthy", action="store_true", help="Run all-within-bounds demo seed.")
    parser.add_argument("--demo-7d-audit", action="store_true", help="Run window=7d demo seed.")
    parser.add_argument("--out", type=Path, default=None, help="Write to file (default stdout).")

    args = parser.parse_args(argv)

    selected_demos = sum(1 for f in (args.demo, args.demo_healthy, args.demo_7d_audit) if f)
    if selected_demos > 1:
        raise SystemExit("ERROR: choose at most one of --demo / --demo-healthy / --demo-7d-audit")

    payload = _maybe_load_payload(args)
    if args.demo_7d_audit:
        args.window = 7

    try:
        rendered = generate_quote_tweet_variants(
            x_handle=args.x_handle,
            source_post_file=args.source_post_file,
            voice_profile_file=args.voice_profile_file,
            max_variants=args.max_variants,
            window=args.window,
            risk_floor=args.risk_floor,
            payload=payload,
            args=args,
        )
    except QuoteTweetSuggestorError as exc:
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
