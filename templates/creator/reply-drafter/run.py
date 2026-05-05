# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Reply Drafter — runner.

CLI entry point for the ``reply-drafter`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads creator-supplied X mention data (JSON) — or seeded demo mentions
when no file is provided — plus an optional voice profile, and emits
the strict 7/8-section reply plan defined by the system prompt:

  1. Reply Snapshot
  2. Reply Plan Score (4-row metric table + weighted score)
  3. Mention Queue Snapshot (top 6-8 mentions, paraphrased)
  4. Drafts (4-6 entries; voice-drift candidates flagged inline)
  5. Red Flags (2-4, surfaces helpful-but-off-voice paradox + risk-exclude guard)
  6. Recommendations (3-5, mandatory bridges to brand-voice-trainer
     and mention-summarizer)
  7. Confidence
  + Optional Reply Audit (auto-appended when window=7d, risk-exclude
    guard fires, or paradox fires)

Hard guarantees enforced by this runner (mirrors the system prompt):

* Drafts only — never auto-publishes. v1 has no auto-publish path.
* Never impersonate the mention author or any third party.
* No fabricated statistics. Demo metrics carry an explicit
  `[demo reply — re-run with --mentions-file / --voice-profile-file
  for real X data]` label.
* Helpful-but-off-voice paradox surfaced in BOTH the Plan Score section
  AND the Red Flags section whenever average Substance > 70 AND
  average Voice fidelity < 55.
* Risk-exclude guard: any draft with risk_score < risk_floor (default
  40) is excluded from the Drafts section and surfaced as a single
  Red Flag.
* Voice-drift surfacing — drafts with voice_fidelity_score < 50 stay
  in the plan but carry `⚠️ voice-drift candidate` inline.
* Plan Score formula is fixed:
    round(0.30*VoiceFidelity_norm + 0.25*Substance_norm +
          0.25*ToneCalibration_norm + 0.20*RiskAvoidance_norm).
* 5-arrow trend vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼).
* Unconditional bridges to brand-voice-trainer (position 1) and
  mention-summarizer (position 2) in every Recommendations list.
* Privacy-first: third-party @-handles, raw mention text, attachment
  URLs, and external links are never echoed — only paraphrased excerpts
  capped at 80 chars.
* No finance / cashtag / sponsorship / harassment / X-policy-violation
  content.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic: seeded by sha256(handle + mentions + window + date).
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_reply_drafts

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
    "Voice fidelity",
    "Substance",
    "Tone calibration",
    "Risk avoidance",
)

PLAN_SCORE_WEIGHTS = {
    "Voice fidelity": 0.30,
    "Substance": 0.25,
    "Tone calibration": 0.25,
    "Risk avoidance": 0.20,
}

HEALTHY_RANGES = {
    "Voice fidelity": (60.0, 95.0),
    "Substance": (55.0, 90.0),
    "Tone calibration": (60.0, 90.0),
    "Risk avoidance": (70.0, 100.0),
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

# Helpful-but-off-voice paradox: avg Substance > 70 AND avg Voice fidelity < 55.
PARADOX_SUBSTANCE_THRESHOLD = 70.0
PARADOX_VOICE_THRESHOLD = 55.0

# Risk-exclude guard: any draft with risk_score < risk_floor.
DEFAULT_RISK_FLOOR = 40.0

# Voice-drift inline surfacing.
VOICE_DRIFT_THRESHOLD = 50.0

DRAFT_COUNT_MIN = 4
DRAFT_COUNT_MAX = 6
DEFAULT_MAX_DRAFTS = 5

VALID_FORMATS = ("single", "thread-reply")
ENGAGEMENT_BANDS = ("low", "medium", "high", "breakout")

VALID_SENTIMENTS = ("positive", "neutral", "negative")
VALID_INTENTS = ("question", "praise", "criticism", "promotion-attempt", "collaboration-ask", "general")

# Tie-breaker: positive > question > criticism > general > praise > promotion-attempt
INTENT_TIEBREAK = {
    "question": 0,
    "collaboration-ask": 1,
    "criticism": 2,
    "general": 3,
    "praise": 4,
    "promotion-attempt": 5,
}

CROSS_TEMPLATE_BRIDGES = (
    "brand-voice-trainer",     # mandatory position 1
    "mention-summarizer",      # mandatory position 2
    "thread-builder",
    "content-idea-generator",
    "dm-triager",
    "comment-engagement-booster",
    "analytics-summarizer",
    "competitor-watch",
    "follower-quality-analyzer",
    "niche-influencer-finder",
)

MANDATORY_BRIDGES = ("brand-voice-trainer", "mention-summarizer")

DEMO_LABEL = (
    "[demo reply — re-run with --mentions-file / --voice-profile-file for real X data]"
)


# ---------------------------------------------------------------------------
# Demo data — paradox + risk-exclude guard firing
# ---------------------------------------------------------------------------

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "window": 30,
    "data_source": "demo",
    "previous_window_summary": {
        "avg_voice_fidelity_score": 70.0,
        "avg_substance_score": 70.0,
        "avg_tone_calibration_score": 75.0,
        "avg_risk_avoidance_score": 88.0,
    },
    "mentions": [
        {
            "id": "m-001",
            "paraphrased_excerpt": "asks for the eval-framework setup that surfaced the agent regression",
            "sentiment": "positive",
            "intent": "question",
            "priority_score": 92,
            "author_followers": 12000,
        },
        {
            "id": "m-002",
            "paraphrased_excerpt": "praises the creator's last benchmark thread but asks for a follow-up",
            "sentiment": "positive",
            "intent": "praise",
            "priority_score": 78,
            "author_followers": 8500,
        },
        {
            "id": "m-003",
            "paraphrased_excerpt": "criticism on a recent take — asks the creator to reconsider an assumption",
            "sentiment": "negative",
            "intent": "criticism",
            "priority_score": 84,
            "author_followers": 22000,
        },
        {
            "id": "m-004",
            "paraphrased_excerpt": "collaboration ask — proposes co-running an eval study",
            "sentiment": "positive",
            "intent": "collaboration-ask",
            "priority_score": 88,
            "author_followers": 35000,
        },
        {
            "id": "m-005",
            "paraphrased_excerpt": "shares an unrelated personal story under a creator post",
            "sentiment": "neutral",
            "intent": "general",
            "priority_score": 35,
            "author_followers": 800,
        },
        {
            "id": "m-006",
            "paraphrased_excerpt": "promotion attempt — pitches a paid newsletter unrelated to the niche",
            "sentiment": "neutral",
            "intent": "promotion-attempt",
            "priority_score": 22,
            "author_followers": 4000,
        },
        {
            "id": "m-007",
            "paraphrased_excerpt": "hostile pile-on reply attacking the creator's work without specifics",
            "sentiment": "negative",
            "intent": "criticism",
            "priority_score": 70,
            "author_followers": 1500,
        },
        {
            "id": "m-008",
            "paraphrased_excerpt": "neutral question about benchmark methodology",
            "sentiment": "neutral",
            "intent": "question",
            "priority_score": 65,
            "author_followers": 6000,
        },
    ],
    "candidate_drafts": [
        {
            "mention_id": "m-001",
            "format": "single",
            "draft_outline": "share the exact setup with a one-line caveat about edge-case behaviour",
            "voice_fidelity_score": 48,
            "substance_score": 82,
            "tone_calibration_score": 75,
            "risk_avoidance_score": 90,
        },
        {
            "mention_id": "m-002",
            "format": "thread-reply",
            "draft_outline": "thank the mention author and tease the follow-up thread with two specific angles",
            "voice_fidelity_score": 50,
            "substance_score": 75,
            "tone_calibration_score": 78,
            "risk_avoidance_score": 88,
        },
        {
            "mention_id": "m-003",
            "format": "single",
            "draft_outline": "acknowledge the criticism and concede the assumption with a paraphrased re-statement",
            "voice_fidelity_score": 52,
            "substance_score": 78,
            "tone_calibration_score": 70,
            "risk_avoidance_score": 85,
        },
        {
            "mention_id": "m-004",
            "format": "thread-reply",
            "draft_outline": "outline the eval-study collaboration scope in 4 tweets with concrete deliverables",
            "voice_fidelity_score": 45,
            "substance_score": 80,
            "tone_calibration_score": 72,
            "risk_avoidance_score": 92,
        },
        {
            "mention_id": "m-008",
            "format": "single",
            "draft_outline": "answer the methodology question with a one-paragraph explanation and a public link to the methodology post",
            "voice_fidelity_score": 50,
            "substance_score": 76,
            "tone_calibration_score": 68,
            "risk_avoidance_score": 82,
        },
        {
            "mention_id": "m-007",
            "format": "single",
            "draft_outline": "engage the hostile pile-on with a public counter-argument",
            "voice_fidelity_score": 40,
            "substance_score": 68,
            "tone_calibration_score": 50,
            "risk_avoidance_score": 25,  # → excluded by risk-exclude guard
        },
        {
            "mention_id": "m-006",
            "format": "single",
            "draft_outline": "respond to the promotion-attempt with a polite redirect",
            "voice_fidelity_score": 55,
            "substance_score": 60,
            "tone_calibration_score": 70,
            "risk_avoidance_score": 30,  # → excluded by risk-exclude guard (promotion-attempt risk)
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "window": 30,
    "data_source": "demo",
    "previous_window_summary": {
        "avg_voice_fidelity_score": 80.0,
        "avg_substance_score": 75.0,
        "avg_tone_calibration_score": 80.0,
        "avg_risk_avoidance_score": 92.0,
    },
    "mentions": [
        {
            "id": "m-101",
            "paraphrased_excerpt": "asks about the evening-friction audit framework specifics",
            "sentiment": "positive",
            "intent": "question",
            "priority_score": 90,
            "author_followers": 15000,
        },
        {
            "id": "m-102",
            "paraphrased_excerpt": "shares their own habit-stacking experiment with concrete numbers",
            "sentiment": "positive",
            "intent": "praise",
            "priority_score": 75,
            "author_followers": 9000,
        },
        {
            "id": "m-103",
            "paraphrased_excerpt": "collaboration ask on a behaviour-design study",
            "sentiment": "positive",
            "intent": "collaboration-ask",
            "priority_score": 85,
            "author_followers": 25000,
        },
        {
            "id": "m-104",
            "paraphrased_excerpt": "thoughtful pushback on a single claim from a recent thread",
            "sentiment": "neutral",
            "intent": "criticism",
            "priority_score": 70,
            "author_followers": 12000,
        },
        {
            "id": "m-105",
            "paraphrased_excerpt": "asks for the diagram source from the friction-audit post",
            "sentiment": "positive",
            "intent": "question",
            "priority_score": 65,
            "author_followers": 7000,
        },
    ],
    "candidate_drafts": [
        {
            "mention_id": "m-101",
            "format": "single",
            "draft_outline": "share the framework with a concrete one-week example from the creator's own practice",
            "voice_fidelity_score": 86,
            "substance_score": 82,
            "tone_calibration_score": 84,
            "risk_avoidance_score": 95,
        },
        {
            "mention_id": "m-103",
            "format": "thread-reply",
            "draft_outline": "outline the collaboration scope in three tweets with concrete deliverables",
            "voice_fidelity_score": 88,
            "substance_score": 80,
            "tone_calibration_score": 86,
            "risk_avoidance_score": 92,
        },
        {
            "mention_id": "m-102",
            "format": "single",
            "draft_outline": "amplify the mention's experiment with a thoughtful follow-up question",
            "voice_fidelity_score": 84,
            "substance_score": 75,
            "tone_calibration_score": 88,
            "risk_avoidance_score": 95,
        },
        {
            "mention_id": "m-104",
            "format": "single",
            "draft_outline": "engage the pushback by re-stating the assumption and explaining the evidence",
            "voice_fidelity_score": 82,
            "substance_score": 78,
            "tone_calibration_score": 82,
            "risk_avoidance_score": 90,
        },
        {
            "mention_id": "m-105",
            "format": "single",
            "draft_outline": "share the diagram source path and offer a quick walkthrough as a follow-up",
            "voice_fidelity_score": 80,
            "substance_score": 70,
            "tone_calibration_score": 84,
            "risk_avoidance_score": 95,
        },
    ],
}

DEMO_7D_AUDIT = {
    "x_handle": "@thindata",
    "window": 7,
    "data_source": "demo",
    "previous_window_summary": {
        "avg_voice_fidelity_score": 70.0,
        "avg_substance_score": 70.0,
        "avg_tone_calibration_score": 75.0,
        "avg_risk_avoidance_score": 85.0,
    },
    "mentions": [
        {
            "id": "m-201",
            "paraphrased_excerpt": "asks for the methodology behind a recent 7d benchmark write-up",
            "sentiment": "positive",
            "intent": "question",
            "priority_score": 80,
            "author_followers": 5000,
        },
        {
            "id": "m-202",
            "paraphrased_excerpt": "thoughtful pushback on a single statistical claim",
            "sentiment": "neutral",
            "intent": "criticism",
            "priority_score": 72,
            "author_followers": 8000,
        },
        {
            "id": "m-203",
            "paraphrased_excerpt": "shares their own replication and asks for the data path",
            "sentiment": "positive",
            "intent": "question",
            "priority_score": 78,
            "author_followers": 3500,
        },
        {
            "id": "m-204",
            "paraphrased_excerpt": "general supportive comment with no specific question",
            "sentiment": "positive",
            "intent": "praise",
            "priority_score": 50,
            "author_followers": 1200,
        },
    ],
    "candidate_drafts": [
        {
            "mention_id": "m-201",
            "format": "single",
            "draft_outline": "answer the methodology question with a one-paragraph explanation and a link to the methodology post",
            "voice_fidelity_score": 78,
            "substance_score": 75,
            "tone_calibration_score": 76,
            "risk_avoidance_score": 88,
        },
        {
            "mention_id": "m-202",
            "format": "single",
            "draft_outline": "engage the pushback by paraphrasing the original claim and explaining the evidence",
            "voice_fidelity_score": 76,
            "substance_score": 80,
            "tone_calibration_score": 78,
            "risk_avoidance_score": 86,
        },
        {
            "mention_id": "m-203",
            "format": "single",
            "draft_outline": "share the data path and ask the replication for any flagged divergences",
            "voice_fidelity_score": 75,
            "substance_score": 72,
            "tone_calibration_score": 75,
            "risk_avoidance_score": 90,
        },
        {
            "mention_id": "m-204",
            "format": "single",
            "draft_outline": "thank the supportive comment and tease the next deeper post",
            "voice_fidelity_score": 72,
            "substance_score": 60,
            "tone_calibration_score": 80,
            "risk_avoidance_score": 95,
        },
    ],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReplyDrafterError(RuntimeError):
    """Raised for any creator-facing input or guard failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_handle(raw: str) -> str:
    handle = raw.strip().lstrip("@")
    if not handle:
        raise ReplyDrafterError("x_handle is required and cannot be empty.")
    if " " in handle or len(handle) > 15:
        raise ReplyDrafterError(
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


def _engagement_band_for(voice: float, substance: float, tone: float) -> str:
    composite = 0.4 * voice + 0.35 * substance + 0.25 * tone
    if composite >= 88:
        return "breakout"
    if composite >= 70:
        return "high"
    if composite >= 55:
        return "medium"
    return "low"


def _validate_window(window: int) -> int:
    if window not in WINDOW_OPTIONS:
        raise ReplyDrafterError(
            f"window={window!r} is invalid — choose one of {WINDOW_OPTIONS}."
        )
    return window


def _clamp_max_drafts(target: int) -> int:
    return max(DRAFT_COUNT_MIN, min(DRAFT_COUNT_MAX, int(target)))


def _derive_priority_score(intent: str, author_followers: int) -> int:
    """Fallback priority score for mentions without an explicit one."""
    intent_weight = {
        "collaboration-ask": 90,
        "question": 80,
        "criticism": 70,
        "praise": 50,
        "general": 40,
        "promotion-attempt": 20,
    }.get(intent, 50)
    # Followers normalised to 0-100 with 50k as soft cap.
    followers_norm = min(100.0, (author_followers or 0) / 500.0)
    return int(round(intent_weight * 0.6 + followers_norm * 0.4))


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

# Privacy pattern — refuse third-party @-handles in raw paraphrases
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
        raise ReplyDrafterError(
            f"refusing {label}: forbidden token(s) {flagged!r} (cashtag / "
            "investment / sponsorship / harassment content is not generated by this template)"
        )


def _refuse_if_privacy_leak(label: str, text: str, allow_creator_handle: str) -> None:
    """Block third-party handles + raw URLs in paraphrased fields. The
    creator's own handle (e.g. @JanSol0s) is allowed."""
    handles = HANDLE_PATTERN.findall(text)
    creator_lower = allow_creator_handle.lower()
    third_party = [h for h in handles if h.lower() != creator_lower]
    if third_party:
        raise ReplyDrafterError(
            f"refusing {label}: third-party handle(s) {third_party!r} in paraphrased field. "
            "Replace with a paraphrased referent (e.g. 'the mention author')."
        )
    if URL_PATTERN.search(text):
        raise ReplyDrafterError(
            f"refusing {label}: URL detected in paraphrased field. "
            "Replace with a paraphrased pointer (e.g. 'the public methodology post')."
        )


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


@dataclass
class ReplyInput:
    x_handle: str
    window: int
    data_source: str
    max_drafts: int
    risk_floor: float
    mentions: list[dict]
    candidate_drafts: list[dict]
    previous_window_summary: dict
    mentions_file: Optional[str] = None
    voice_profile_file: Optional[str] = None


def _load_demo(mode: str) -> dict:
    if mode == "paradox":
        return json.loads(json.dumps(DEMO_PARADOX))
    if mode == "healthy":
        return json.loads(json.dumps(DEMO_HEALTHY))
    if mode == "7d-audit":
        return json.loads(json.dumps(DEMO_7D_AUDIT))
    raise ReplyDrafterError(f"unknown demo mode {mode!r}")


def _validate_mention(m: dict, idx: int, creator_handle: str) -> dict:
    required = ("id", "sentiment", "intent")
    missing = [k for k in required if k not in m]
    if missing:
        raise ReplyDrafterError(f"mention[{idx}] missing keys: {missing}")
    if m["sentiment"] not in VALID_SENTIMENTS:
        raise ReplyDrafterError(
            f"mention[{idx}].sentiment={m['sentiment']!r} invalid — choose {VALID_SENTIMENTS}"
        )
    if m["intent"] not in VALID_INTENTS:
        raise ReplyDrafterError(
            f"mention[{idx}].intent={m['intent']!r} invalid — choose {VALID_INTENTS}"
        )
    excerpt = m.get("paraphrased_excerpt", "")
    if excerpt:
        _refuse_if_forbidden(f"mention[{idx}].paraphrased_excerpt", str(excerpt))
        _refuse_if_privacy_leak(
            f"mention[{idx}].paraphrased_excerpt", str(excerpt), creator_handle
        )
        # Cap excerpt at 80 chars per privacy rule
        m["paraphrased_excerpt"] = str(excerpt)[:80]
    if "priority_score" not in m:
        m["priority_score"] = _derive_priority_score(
            m["intent"], int(m.get("author_followers", 0) or 0)
        )
    elif not isinstance(m["priority_score"], (int, float)):
        raise ReplyDrafterError(
            f"mention[{idx}].priority_score must be a number; got {type(m['priority_score']).__name__}"
        )
    return m


def _validate_draft(d: dict, idx: int, mention_ids: set[str], creator_handle: str) -> dict:
    required = (
        "mention_id", "format", "draft_outline",
        "voice_fidelity_score", "substance_score",
        "tone_calibration_score", "risk_avoidance_score",
    )
    missing = [k for k in required if k not in d]
    if missing:
        raise ReplyDrafterError(f"draft[{idx}] missing keys: {missing}")
    if d["format"] not in VALID_FORMATS:
        raise ReplyDrafterError(
            f"draft[{idx}].format={d['format']!r} invalid — choose {VALID_FORMATS}"
        )
    if d["mention_id"] not in mention_ids:
        raise ReplyDrafterError(
            f"draft[{idx}].mention_id={d['mention_id']!r} not in mentions[]"
        )
    for score_key in (
        "voice_fidelity_score", "substance_score",
        "tone_calibration_score", "risk_avoidance_score",
    ):
        v = d[score_key]
        if not isinstance(v, (int, float)):
            raise ReplyDrafterError(
                f"draft[{idx}].{score_key} must be a number; got {type(v).__name__}"
            )
        if v < 0 or v > 100:
            raise ReplyDrafterError(
                f"draft[{idx}].{score_key}={v} outside 0-100"
            )
    outline = str(d.get("draft_outline", ""))
    _refuse_if_forbidden(f"draft[{idx}].draft_outline", outline)
    _refuse_if_privacy_leak(f"draft[{idx}].draft_outline", outline, creator_handle)
    return d


def _validate_input(payload: dict, args: argparse.Namespace) -> ReplyInput:
    handle = _normalise_handle(payload.get("x_handle", args.x_handle or ""))
    window = _validate_window(int(payload.get("window", args.window)))
    data_source = payload.get("data_source", "real")
    if data_source not in ("real", "demo"):
        raise ReplyDrafterError(
            f"data_source={data_source!r} invalid — choose 'real' or 'demo'"
        )

    mentions_raw = payload.get("mentions") or []
    if len(mentions_raw) < 2:
        raise ReplyDrafterError(
            f"mentions count {len(mentions_raw)} below floor 2 — please supply 2+ mentions"
        )
    mentions = [_validate_mention(m, i, handle) for i, m in enumerate(mentions_raw)]
    mention_ids = {m["id"] for m in mentions}

    drafts_raw = payload.get("candidate_drafts") or []
    if len(drafts_raw) < DRAFT_COUNT_MIN:
        raise ReplyDrafterError(
            f"candidate_drafts count {len(drafts_raw)} below floor {DRAFT_COUNT_MIN}"
        )
    drafts = [_validate_draft(d, idx, mention_ids, handle) for idx, d in enumerate(drafts_raw)]

    return ReplyInput(
        x_handle=handle,
        window=window,
        data_source=data_source,
        max_drafts=_clamp_max_drafts(args.max_drafts),
        risk_floor=float(args.risk_floor),
        mentions=mentions,
        candidate_drafts=drafts,
        previous_window_summary=payload.get("previous_window_summary") or {},
        mentions_file=str(args.mentions_file) if args.mentions_file else None,
        voice_profile_file=str(args.voice_profile_file) if args.voice_profile_file else None,
    )


# ---------------------------------------------------------------------------
# Risk-exclude guard + scoring
# ---------------------------------------------------------------------------


@dataclass
class DraftCard:
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
    avg_voice: float
    avg_substance: float
    avg_tone: float
    avg_risk: float


def _annotate_drafts(drafts: list[dict], risk_floor: float) -> tuple[list[DraftCard], int]:
    annotated: list[DraftCard] = []
    excluded = 0
    for d in drafts:
        if d["risk_avoidance_score"] < risk_floor:
            annotated.append(
                DraftCard(
                    raw=d,
                    excluded=True,
                    excluded_reason=(
                        f"risk_score {d['risk_avoidance_score']:.0f} < risk_floor {int(risk_floor)}"
                    ),
                    voice_drift=False,
                    engagement_band="low",
                )
            )
            excluded += 1
        else:
            drift = d["voice_fidelity_score"] < VOICE_DRIFT_THRESHOLD
            band = _engagement_band_for(
                d["voice_fidelity_score"],
                d["substance_score"],
                d["tone_calibration_score"],
            )
            annotated.append(
                DraftCard(
                    raw=d,
                    excluded=False,
                    excluded_reason=None,
                    voice_drift=drift,
                    engagement_band=band,
                )
            )
    return annotated, excluded


def _select_drafts(
    annotated: list[DraftCard],
    mentions_by_id: dict[str, dict],
    target: int,
) -> list[DraftCard]:
    eligible = [a for a in annotated if not a.excluded]
    eligible.sort(
        key=lambda a: (
            -mentions_by_id[a.raw["mention_id"]]["priority_score"],
            INTENT_TIEBREAK.get(mentions_by_id[a.raw["mention_id"]]["intent"], 9),
        )
    )
    n = min(DRAFT_COUNT_MAX, max(DRAFT_COUNT_MIN, target), len(eligible))
    return eligible[:n]


def _avg(items: list[float]) -> float:
    if not items:
        return 0.0
    return sum(items) / len(items)


def _compute_plan_score(annotated: list[DraftCard]) -> PlanScore:
    pool = annotated  # full candidate pool drives the period averages.
    voice = _avg([a.raw["voice_fidelity_score"] for a in pool])
    sub = _avg([a.raw["substance_score"] for a in pool])
    tone = _avg([a.raw["tone_calibration_score"] for a in pool])
    risk = _avg([a.raw["risk_avoidance_score"] for a in pool])

    metric_values = {
        "Voice fidelity": round(voice, 1),
        "Substance": round(sub, 1),
        "Tone calibration": round(tone, 1),
        "Risk avoidance": round(risk, 1),
    }

    norms = {m: _normalise_metric(metric_values[m], m) for m in SCORE_METRICS}
    plan = round(
        PLAN_SCORE_WEIGHTS["Voice fidelity"] * norms["Voice fidelity"]
        + PLAN_SCORE_WEIGHTS["Substance"] * norms["Substance"]
        + PLAN_SCORE_WEIGHTS["Tone calibration"] * norms["Tone calibration"]
        + PLAN_SCORE_WEIGHTS["Risk avoidance"] * norms["Risk avoidance"]
    )

    paradox = (
        sub > PARADOX_SUBSTANCE_THRESHOLD
        and voice < PARADOX_VOICE_THRESHOLD
    )

    return PlanScore(
        metric_values=metric_values,
        metric_arrows={},
        plan_score=plan,
        paradox_active=paradox,
        avg_voice=voice,
        avg_substance=sub,
        avg_tone=tone,
        avg_risk=risk,
    )


def _arrows_against_basis(score: PlanScore, prev: dict) -> dict:
    return {
        "Voice fidelity": _arrow_for_delta(
            score.metric_values["Voice fidelity"],
            float(prev.get("avg_voice_fidelity_score", score.metric_values["Voice fidelity"])),
        ),
        "Substance": _arrow_for_delta(
            score.metric_values["Substance"],
            float(prev.get("avg_substance_score", score.metric_values["Substance"])),
        ),
        "Tone calibration": _arrow_for_delta(
            score.metric_values["Tone calibration"],
            float(prev.get("avg_tone_calibration_score", score.metric_values["Tone calibration"])),
        ),
        "Risk avoidance": _arrow_for_delta(
            score.metric_values["Risk avoidance"],
            float(prev.get("avg_risk_avoidance_score", score.metric_values["Risk avoidance"])),
        ),
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _demo_suffix(data_source: str) -> str:
    return f" {DEMO_LABEL}" if data_source == "demo" else ""


def _interpretation_for(metric: str, value: float, score: PlanScore, excluded_count: int) -> str:
    if metric == "Voice fidelity":
        if score.paradox_active and value < PARADOX_VOICE_THRESHOLD:
            return "Below the 55 floor; drafts read helpful but generic — voice has drifted."
        if value > 95:
            return "Exceptional voice match — verify it isn't hiding generic-polish."
        if value > 60:
            return "Inside the healthy band; drafts preserve the creator's tone."
        return "Voice fidelity below the trainer floor — re-anchor before posting."
    if metric == "Substance":
        if score.paradox_active and value > PARADOX_SUBSTANCE_THRESHOLD:
            return "Drafts add specifics — but off-voice, the substance lands as someone else's voice."
        if value > 90:
            return "High substance — drafts add specifics the audience cannot find elsewhere."
        if value > 55:
            return "Substance acceptable — paired with voice, this is the core healthy band."
        return "Borderline — drafts read generic; add a concrete creator experience to each."
    if metric == "Tone calibration":
        if value > 90:
            return "Exceptional tone calibration — drafts mirror sentiment without amplifying negativity."
        if value > 60:
            return "Tone calibration in the healthy band — drafts mirror mention sentiment without amplifying negativity."
        return "Tone calibration below the floor — drafts risk amplifying mention negativity."
    if metric == "Risk avoidance":
        if excluded_count > 0:
            return f"Risk avoidance acceptable — {excluded_count} draft(s) excluded as high-risk; remaining set safe to ship."
        if value > 95:
            return "Risk avoidance excellent — every draft passes the policy + harassment + over-promise floor."
        if value > 70:
            return "Risk avoidance in the healthy band — no excluded drafts."
        return "Risk avoidance below the floor — re-classify mentions before drafting."
    return ""


def _render_snapshot(inp: ReplyInput, score: PlanScore) -> str:
    headline_bits = [f"{inp.window}d mention window"]
    if score.paradox_active:
        headline_bits.append(
            f"helpful-but-off-voice paradox active; Substance {score.avg_substance:.1f} but Voice fidelity {score.avg_voice:.1f}"
        )
    else:
        headline_bits.append(
            f"plan score {score.plan_score}/100; voice fidelity holding at {score.avg_voice:.1f}"
        )
    headline = f"**{inp.x_handle}: " + " — ".join(headline_bits) + ".**"

    if inp.data_source == "demo":
        ds = "seeded demo mentions — re-run with --mentions-file for real X data"
    else:
        files = []
        if inp.mentions_file:
            files.append(f"mentions={inp.mentions_file}")
        if inp.voice_profile_file:
            files.append(f"voice={inp.voice_profile_file}")
        ds = "real X export — " + (", ".join(files) if files else "(no files supplied)")

    body = [
        "## Reply Snapshot",
        headline,
        "",
        f"- **Creator handle**: {inp.x_handle}",
        f"- **Window**: {inp.window}d",
        f"- **Mention queue size**: {len(inp.mentions)}",
        f"- **Data source**: {ds}",
    ]
    return "\n".join(body)


def _render_plan_score(inp: ReplyInput, score: PlanScore, arrows: dict, excluded_count: int) -> str:
    lines = [
        "## Reply Plan Score",
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
            "> ⚠️ paradox: drafts are substantive but off-voice — well-intentioned helpfulness eroding brand voice."
        )
    lines.append("")
    lines.append(f"**Reply Plan Score**: {score.plan_score}/100")
    return "\n".join(lines)


def _render_mention_queue(inp: ReplyInput, excluded_mention_ids: set[str]) -> str:
    lines = [
        "## Mention Queue Snapshot",
        "",
        "| Mention (paraphrased) | Sentiment | Intent | Priority |",
        "|---|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    sorted_mentions = sorted(inp.mentions, key=lambda m: -m["priority_score"])
    for m in sorted_mentions[:8]:
        excerpt = m.get("paraphrased_excerpt") or "(no excerpt supplied)"
        excerpt_str = f"{excerpt}{suffix}"
        if m["id"] in excluded_mention_ids:
            excerpt_str += " [risk-excluded]"
        lines.append(
            f"| {excerpt_str} | {m['sentiment']} | {m['intent']} | {int(m['priority_score'])} |"
        )
    return "\n".join(lines)


def _render_drafts(
    inp: ReplyInput,
    selected: list[DraftCard],
    excluded_count: int,
    mentions_by_id: dict[str, dict],
) -> str:
    note = ""
    if excluded_count > 0:
        note = f" — {excluded_count} high-risk draft(s) excluded — see Red Flags"
    voice_drift = sum(1 for s in selected if s.voice_drift)
    if voice_drift > 0:
        note += f" — {voice_drift} voice-drift candidate(s) flagged inline"
    header = f"## Drafts ({len(selected)} of {len(inp.mentions)} mentions in window{note})"
    lines = [header, ""]
    suffix = _demo_suffix(inp.data_source)
    for n, sc in enumerate(selected, start=1):
        d = sc.raw
        bridge = "thread-builder" if d["format"] == "thread-reply" else "mention-summarizer"
        drift_flag = " ⚠️ voice-drift candidate" if sc.voice_drift else ""
        mention = mentions_by_id[d["mention_id"]]
        excerpt = mention.get("paraphrased_excerpt") or "(no excerpt supplied)"
        lines.append(
            f"{n}. **{d['format']}**{drift_flag} — replying to: {excerpt}{suffix}"
        )
        lines.append(f"   draft outline: {d['draft_outline']}")
        lines.append(
            f"   voice fidelity: {d['voice_fidelity_score']:.0f}/100 · "
            f"substance: {d['substance_score']:.0f}/100 · "
            f"tone: {d['tone_calibration_score']:.0f}/100 · "
            f"risk: {d['risk_avoidance_score']:.0f}/100 · "
            f"engagement: {sc.engagement_band} · bridges to: `{bridge}`"
        )
    return "\n".join(lines)


def _render_red_flags(
    score: PlanScore,
    excluded_count: int,
    annotated: list[DraftCard],
    selected: list[DraftCard],
) -> str:
    flags: list[tuple[str, str, str, str]] = []

    if score.paradox_active:
        flags.append((
            "Helpful-but-off-voice paradox",
            "high",
            (
                f"Average substance {score.avg_substance:.1f} > 70 while "
                f"average voice fidelity {score.avg_voice:.1f} < 55 — drafts add specifics "
                "but lose the creator's voice."
            ),
            (
                "Re-run with a richer voice profile from `brand-voice-trainer`, OR reduce the "
                "draft set to mentions where the creator's voice has the strongest historical match."
            ),
        ))

    if excluded_count > 0:
        excluded_drafts = [a for a in annotated if a.excluded]
        risk_summary = "; ".join(
            f"draft for {a.raw['mention_id']}: risk {a.raw['risk_avoidance_score']:.0f}"
            for a in excluded_drafts[:3]
        )
        flags.append((
            "High-risk drafts excluded",
            "high",
            (
                f"{excluded_count} draft(s) excluded for risk_score below floor "
                f"({risk_summary}). They do not occupy any of the {DRAFT_COUNT_MIN}-{DRAFT_COUNT_MAX} "
                "drafts slots."
            ),
            (
                "Hand the underlying mentions back to mention-summarizer for re-classification, "
                "then re-batch only the non-risk subset."
            ),
        ))

    drift_count = sum(1 for s in selected if s.voice_drift)
    if drift_count > 0:
        flags.append((
            "Voice-drift candidates surfaced",
            "medium",
            (
                f"{drift_count} draft(s) score voice fidelity < 50 — they remain in the plan "
                "but are flagged inline so the creator rewrites before posting."
            ),
            "Hand each voice-drift candidate to brand-voice-trainer for a re-anchored draft.",
        ))

    # Pool below floor
    if len(selected) < min(DRAFT_COUNT_MIN, _ := DRAFT_COUNT_MIN):
        flags.append((
            "Drafts below floor",
            "high",
            (
                f"Only {len(selected)} draft(s) selected after risk-exclude guard — eligible "
                f"pool was insufficient for the {DRAFT_COUNT_MIN} floor."
            ),
            "Lower --risk-floor or add more candidate drafts to the input file.",
        ))

    if not flags:
        flags.append((
            "No structural red flags",
            "low",
            "Plan stays within healthy bands; review remains creator-side qualitative judgement.",
            "Proceed; spot-check voice fidelity on the highest-substance draft before posting.",
        ))

    lines = ["## Red Flags", ""]
    for title, sev, body, rem in flags:
        lines.append(f"- **{title}** · severity: {sev} — {body}. *Remediation:* {rem}")
    return "\n".join(lines)


def _render_recommendations(
    inp: ReplyInput,
    selected: list[DraftCard],
    score: PlanScore,
    excluded_count: int,
) -> str:
    lines = ["## Recommendations", ""]

    # Position 1 — brand-voice-trainer (mandatory)
    if score.paradox_active:
        lines.append(
            "1. Voice-check every draft with a richer profile before posting — paradox active "
            "means the trainer's anchor is the only path back. — bridges to: `brand-voice-trainer`"
        )
    else:
        drift_count = sum(1 for s in selected if s.voice_drift)
        if drift_count > 0:
            lines.append(
                f"1. Re-anchor {drift_count} voice-drift candidate(s) through the trainer before "
                "publishing — voice fidelity floor is the creator-trust signal. — bridges to: `brand-voice-trainer`"
            )
        else:
            lines.append(
                "1. Voice-check every draft before posting — the trainer's input signal is "
                "exactly this batch's voice fidelity floor. — bridges to: `brand-voice-trainer`"
            )

    # Position 2 — mention-summarizer (mandatory)
    if excluded_count > 0:
        lines.append(
            "2. Hand the high-risk mentions back to mention-summarizer for re-classification "
            "before they re-enter the reply queue. — bridges to: `mention-summarizer`"
        )
    else:
        lines.append(
            "2. Refresh the mention priority queue next window — feed this run's response "
            "deltas back into mention-summarizer's signal. — bridges to: `mention-summarizer`"
        )

    # Position 3 — context-aware
    thread_drafts = [s for s in selected if s.raw["format"] == "thread-reply"]
    if thread_drafts:
        lines.append(
            f"3. Expand the highest-substance thread-reply into a structured long-form draft "
            "when the reply warrants standalone amplification. — bridges to: `thread-builder`"
        )
    elif score.metric_values["Substance"] >= 70:
        lines.append(
            "3. When a mention surfaces a recurring content gap, source the next anchor post "
            "from the gap rather than just replying. — bridges to: `content-idea-generator`"
        )
    else:
        lines.append(
            "3. Coordinate the mention queue with the DM queue — drafts and DMs from the same "
            "author should not double-up. — bridges to: `dm-triager`"
        )

    # Position 4 — context-aware
    if score.metric_values["Risk avoidance"] < 75:
        lines.append(
            "4. Audit follower quality on negative mentions before drafting next batch — "
            "low-quality follower spikes inflate the risk floor. — bridges to: `follower-quality-analyzer`"
        )
    else:
        lines.append(
            "4. Convert reply chains into structured comment plans on adjacent creator posts "
            "when the substance carries forward. — bridges to: `comment-engagement-booster`"
        )

    # Position 5 — measurement
    lines.append(
        "5. Correlate post-reply engagement deltas with the period's analytics next window "
        "to confirm the draft set landed. — bridges to: `analytics-summarizer`"
    )

    return "\n".join(lines)


def _render_confidence(
    inp: ReplyInput,
    score: PlanScore,
    selected: list[DraftCard],
    excluded_count: int,
) -> str:
    drift_count = sum(1 for s in selected if s.voice_drift)
    if inp.data_source == "demo":
        level = "low"
        reason = (
            "demo signals only — re-run with --mentions-file pointing at real X data and "
            "--voice-profile-file from brand-voice-trainer. Plan Score is illustrative."
        )
    elif score.paradox_active:
        level = "low"
        reason = (
            "real signals, but helpful-but-off-voice paradox active — re-anchor voice "
            "before treating the score as a publish signal."
        )
    elif excluded_count > 0:
        level = "medium"
        reason = (
            f"real signals; {excluded_count} draft(s) excluded by risk guard — re-classify "
            "the underlying mentions before next batch."
        )
    elif drift_count > 0:
        level = "medium"
        reason = (
            f"real signals; {drift_count} voice-drift candidate(s) require trainer re-anchor."
        )
    elif inp.window == 7:
        level = "medium"
        reason = "7d window over-indexes on single-day variance — re-run with 30d to confirm."
    else:
        level = "high"
        reason = "real signals, all metrics inside healthy bands, no exclusions."
    return f"## Confidence\nConfidence: {level} — {reason}"


def _render_audit(
    inp: ReplyInput, score: PlanScore, annotated: list[DraftCard], excluded_count: int
) -> Optional[str]:
    triggers = []
    if inp.window == 7:
        triggers.append("window=7d — single-day variance dominates mention volume")
    if excluded_count > 0:
        triggers.append("risk-exclude guard fired")
    if score.paradox_active:
        triggers.append("helpful-but-off-voice paradox active")

    if not triggers:
        return None

    drift_share = sum(1 for a in annotated if a.voice_drift) / max(1, len(annotated)) * 100.0

    lines = [
        "## Reply Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {inp.window}d window is "
        + ("under-powered for mention queue volume" if inp.window == 7 else "adequate"),
        f"- **Data source confidence**: "
        + ("demo signals — re-run with real exports" if inp.data_source == "demo"
           else "real signals — proceed"),
        f"- **Risk-exclude impact**: "
        + (f"{excluded_count} draft(s) excluded — review the underlying mentions" if excluded_count > 0
           else "none excluded"),
        f"- **Voice-drift signal**: {drift_share:.0f}% of drafts carry the drift flag — "
        + ("hand them to brand-voice-trainer before posting" if drift_share > 0
           else "no drift surfaced"),
        "- **Suggested next sample**: re-run after 7 days of new mentions to refresh the priority queue",
        "- **Re-run cadence**: daily during active mention surges; otherwise weekly",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_reply_drafts(
    *,
    x_handle: str,
    mentions_file: Optional[str] = None,
    voice_profile_file: Optional[str] = None,
    max_drafts: int = DEFAULT_MAX_DRAFTS,
    window: int = 30,
    risk_floor: float = DEFAULT_RISK_FLOOR,
    payload: Optional[dict] = None,
    args: Optional[argparse.Namespace] = None,
) -> str:
    """Render the full reply plan markdown."""
    if args is None:
        args = argparse.Namespace(
            x_handle=x_handle,
            mentions_file=mentions_file,
            voice_profile_file=voice_profile_file,
            max_drafts=max_drafts,
            window=window,
            risk_floor=risk_floor,
        )
    inp = _validate_input(payload or {}, args)

    seed = _seed_from(
        inp.x_handle,
        json.dumps([m["id"] for m in inp.mentions], sort_keys=True),
        str(inp.window),
        _utcnow_date(),
    )
    Random(seed)

    annotated, excluded_count = _annotate_drafts(inp.candidate_drafts, inp.risk_floor)
    mentions_by_id = {m["id"]: m for m in inp.mentions}
    selected = _select_drafts(annotated, mentions_by_id, inp.max_drafts)
    score = _compute_plan_score(annotated)
    arrows = _arrows_against_basis(score, inp.previous_window_summary)
    score.metric_arrows = arrows

    excluded_mention_ids = {a.raw["mention_id"] for a in annotated if a.excluded}

    parts: list[str] = []
    parts.append(_render_snapshot(inp, score))
    parts.append(_render_plan_score(inp, score, arrows, excluded_count))
    parts.append(_render_mention_queue(inp, excluded_mention_ids))
    parts.append(_render_drafts(inp, selected, excluded_count, mentions_by_id))
    parts.append(_render_red_flags(score, excluded_count, annotated, selected))
    parts.append(_render_recommendations(inp, selected, score, excluded_count))
    parts.append(_render_confidence(inp, score, selected, excluded_count))
    audit = _render_audit(inp, score, annotated, excluded_count)
    if audit is not None:
        parts.append(audit)

    return "\n\n".join(parts) + "\n"


# Manifest alias
generate = generate_reply_drafts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_FILE_HEADER = (
    "<!-- Copyright 2026 AgentMindCloud -->\n"
    "<!-- Licensed under the Apache License, Version 2.0 -->\n"
    "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
    "<!-- Generated by reply-drafter/run.py — built for X, Grok & the ecosystem community. -->\n"
    "\n"
)


def _maybe_load_payload(args: argparse.Namespace) -> Optional[dict]:
    if args.demo:
        return _load_demo("paradox")
    if args.demo_healthy:
        return _load_demo("healthy")
    if args.demo_7d_audit:
        return _load_demo("7d-audit")
    if args.mentions_file:
        p = Path(args.mentions_file)
        if not p.exists():
            raise ReplyDrafterError(f"mentions_file {p} does not exist")
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reply-drafter",
        description=(
            "Local-first reply drafter for X creators. Drafts only — never auto-publishes. "
            "v1 is offline-only; real_time_x.posts in the manifest is a future-version flag. "
            "Built for X, Grok & the ecosystem community."
        ),
    )
    parser.add_argument("--x-handle", required=True, help="Creator's X handle.")
    parser.add_argument("--mentions-file", default=None, help="Path to mentions JSON.")
    parser.add_argument("--voice-profile-file", default=None, help="Path to voice profile JSON.")
    parser.add_argument(
        "--max-drafts",
        type=int,
        default=DEFAULT_MAX_DRAFTS,
        help="Target draft count, clamped to [4, 6].",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=30,
        help="Mention window in days (7 / 30 / 90).",
    )
    parser.add_argument(
        "--risk-floor",
        type=float,
        default=DEFAULT_RISK_FLOOR,
        help="Risk avoidance threshold below which a draft is excluded (default 40).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the helpful-but-off-voice paradox + risk-exclude guard demo seed.",
    )
    parser.add_argument(
        "--demo-healthy",
        action="store_true",
        help="Run the all-within-bounds demo seed.",
    )
    parser.add_argument(
        "--demo-7d-audit",
        action="store_true",
        help="Run the window=7d demo seed that auto-triggers the Reply Audit.",
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
        rendered = generate_reply_drafts(
            x_handle=args.x_handle,
            mentions_file=args.mentions_file,
            voice_profile_file=args.voice_profile_file,
            max_drafts=args.max_drafts,
            window=args.window,
            risk_floor=args.risk_floor,
            payload=payload,
            args=args,
        )
    except ReplyDrafterError as exc:
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
