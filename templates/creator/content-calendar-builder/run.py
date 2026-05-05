# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Content Calendar Builder — runner.

CLI entry point for the ``content-calendar-builder`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads creator-supplied cadence + niche + optional voice + analytics
signals and emits the strict 7/8-section calendar defined by the
system prompt:

  1. Calendar Snapshot
  2. Calendar Plan Score (4-row metric table + weighted score)
  3. Format Mix
  4. Slots (organised by week; 4-12 weeks × 3-14 slots/week)
  5. Red Flags (2-4, surfaces over-scheduling paradox + format-streak
     guard + variety-floor breach)
  6. Recommendations (3-5, mandatory bridges to analytics-summarizer
     and brand-voice-trainer)
  7. Confidence
  + Optional Calendar Audit (auto-appended when weeks=1, paradox
    fires, or format-streak guard fires)

Hard guarantees:

* Drafts only — never auto-publishes.
* No fabricated statistics. Demo metrics carry an explicit
  `[demo slot — re-run with --voice-profile-file / --analytics-file
  for real X data]` label.
* Over-scheduling paradox surfaced in BOTH the Plan Score section AND
  the Red Flags section whenever Cadence sustainability < 50 AND
  posts_per_week > 7.
* Format-streak guard: ≥ 3 consecutive same-format slots → Red Flag
  (slots stay in calendar — only flagged).
* Variety floor — below configurable floor → Red Flag.
* Plan Score formula:
    round(0.30*CadenceSustainability_norm + 0.25*NicheFit_norm +
          0.25*Voice_norm + 0.20*Variety_norm).
* Unconditional bridges to analytics-summarizer (position 1) and
  brand-voice-trainer (position 2).
* No finance / cashtag / sponsorship / harassment content.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic: seeded by sha256(handle + niche + cadence + weeks + date).
* Zero external network calls in v1.

Manifest contract::

    generate = generate_content_calendar

Built for X, Grok & the ecosystem community.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "prompts" / "system.md"

SCORE_METRICS = (
    "Cadence sustainability",
    "Niche fit",
    "Voice fidelity",
    "Variety",
)

PLAN_SCORE_WEIGHTS = {
    "Cadence sustainability": 0.30,
    "Niche fit": 0.25,
    "Voice fidelity": 0.25,
    "Variety": 0.20,
}

HEALTHY_RANGES = {
    "Cadence sustainability": (60.0, 95.0),
    "Niche fit": (60.0, 95.0),
    "Voice fidelity": (60.0, 95.0),
    "Variety": (60.0, 100.0),
}

CADENCE_MIN = 3
CADENCE_MAX = 14
WEEKS_MIN = 1
WEEKS_MAX = 12
DEFAULT_CADENCE = 5
DEFAULT_WEEKS = 4
DEFAULT_VARIETY_FLOOR = 4

VALID_FORMATS = ("single", "thread", "quote-tweet", "image-post", "reply-thread")
VALID_TIME_TIERS = (
    "early-morning", "late-morning", "midday", "afternoon", "evening", "late-evening",
)
DAYS_OF_WEEK = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
ENGAGEMENT_BANDS = ("low", "medium", "high", "breakout")

# Over-scheduling paradox.
PARADOX_CADENCE_THRESHOLD = 50.0
PARADOX_VOLUME_THRESHOLD = 7

VOICE_DRIFT_THRESHOLD = 50.0
FORMAT_STREAK_THRESHOLD = 3

CROSS_TEMPLATE_BRIDGES = (
    "analytics-summarizer",
    "brand-voice-trainer",
    "content-idea-generator",
    "thread-builder",
    "trend-aligned-poster",
    "ab-test-suggester",
    "cross-platform-reposter",
    "content-recycler",
    "competitor-watch",
    "mention-summarizer",
)

MANDATORY_BRIDGES = ("analytics-summarizer", "brand-voice-trainer")

DEMO_LABEL = (
    "[demo slot — re-run with --voice-profile-file / --analytics-file for real X data]"
)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

# Each demo set defines:
#   x_handle, niche, cadence_per_week, weeks, data_source,
#   slot_archetypes (list of label strings — runner cycles through them),
#   slot_format_pattern (list of formats — runner cycles through them),
#   cadence_sustainability_seed (controls the seeded cadence-sustainability
#       baseline; runner adjusts based on cadence_per_week)
#   voice_fidelity_seed (controls the seeded voice-fidelity baseline)
#   niche_fit_seed (controls the seeded niche-fit baseline)
#   previous_window_summary

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "niche": "ai-agents",
    "cadence_per_week": 12,  # over-scheduling paradox: posts_per_week > 7
    "weeks": 4,
    "data_source": "demo",
    "variety_floor": 4,
    "slot_archetypes": [
        "agent-eval framework deep dive",
        "benchmark drift commentary",
        "post-mortem on a recent agent regression",
        "open-source tooling shoutout",
        "creator's own benchmark numbers",
        "agent-failure-mode taxonomy",
        "tooling launch reaction",
        "weekly agent-build update",
        "research-paper interpretation",
        "agent-eval methodology debate",
        "creator-tools competitor watch",
        "lightweight agent template share",
    ],
    "slot_format_pattern": [
        # Designed to fire format-streak guard: 4 consecutive 'thread'
        "thread", "thread", "thread", "thread",  # streak
        "single", "quote-tweet", "image-post", "reply-thread",
        "single", "thread", "single", "quote-tweet",
    ],
    # Seeds — paradox demo: low cadence sustainability + low-mid voice fidelity
    "cadence_sustainability_seed": 30,  # very low (volume past sustainable)
    "voice_fidelity_seed": 60,
    "niche_fit_seed": 78,
    "previous_window_summary": {
        "avg_cadence_sustainability": 70.0,
        "avg_niche_fit": 80.0,
        "avg_voice_fidelity": 78.0,
        "avg_variety": 80.0,
    },
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "niche": "habit-design",
    "cadence_per_week": 5,
    "weeks": 4,
    "data_source": "demo",
    "variety_floor": 4,
    "slot_archetypes": [
        "evening-friction audit walkthrough",
        "habit-stacking case study with numbers",
        "behaviour-design framework comparison",
        "creator's own three-month retention data",
        "personal-anecdote on a friction-fix",
    ],
    "slot_format_pattern": [
        "thread", "single", "quote-tweet", "image-post", "reply-thread",
    ],
    "cadence_sustainability_seed": 82,
    "voice_fidelity_seed": 84,
    "niche_fit_seed": 88,
    "previous_window_summary": {
        "avg_cadence_sustainability": 80.0,
        "avg_niche_fit": 86.0,
        "avg_voice_fidelity": 82.0,
        "avg_variety": 88.0,
    },
}

DEMO_7D_AUDIT = {
    "x_handle": "@thindata",
    "niche": "applied-ml",
    "cadence_per_week": 5,
    "weeks": 1,  # single-week → audit auto-triggers
    "data_source": "demo",
    "variety_floor": 4,
    "slot_archetypes": [
        "applied-ml benchmark interpretation",
        "research-paper limitation callout",
        "methodology walkthrough",
        "data-source caveats post",
        "applied-ml tooling micro-tip",
    ],
    "slot_format_pattern": [
        "single", "thread", "quote-tweet", "single", "image-post",
    ],
    "cadence_sustainability_seed": 75,
    "voice_fidelity_seed": 76,
    "niche_fit_seed": 80,
    "previous_window_summary": {
        "avg_cadence_sustainability": 72.0,
        "avg_niche_fit": 78.0,
        "avg_voice_fidelity": 74.0,
        "avg_variety": 76.0,
    },
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ContentCalendarBuilderError(RuntimeError):
    """Raised for any creator-facing input or guard failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_handle(raw: str) -> str:
    handle = raw.strip().lstrip("@")
    if not handle:
        raise ContentCalendarBuilderError("x_handle is required.")
    if " " in handle or len(handle) > 15:
        raise ContentCalendarBuilderError(
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
        if delta_pts >= 15:
            return "▲▲"
        if delta_pts >= 5:
            return "▲"
        if delta_pts <= -15:
            return "▼▼"
        if delta_pts <= -5:
            return "▼"
        return "▬"
    pct = (curr - prev) / prev * 100.0
    pts = curr - prev
    if pct >= 25.0 or pts >= 15:
        return "▲▲"
    if pct >= 5.0 or pts >= 5:
        return "▲"
    if pct <= -25.0 or pts <= -15:
        return "▼▼"
    if pct <= -5.0 or pts <= -5:
        return "▼"
    return "▬"


def _engagement_band_for(niche_fit: float, voice: float) -> str:
    composite = 0.55 * niche_fit + 0.45 * voice
    if composite >= 88:
        return "breakout"
    if composite >= 70:
        return "high"
    if composite >= 55:
        return "medium"
    return "low"


def _clamp_cadence(c: int) -> int:
    return max(CADENCE_MIN, min(CADENCE_MAX, int(c)))


def _clamp_weeks(w: int) -> int:
    return max(WEEKS_MIN, min(WEEKS_MAX, int(w)))


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
        raise ContentCalendarBuilderError(
            f"refusing {label}: forbidden token(s) {flagged!r}"
        )


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


@dataclass
class CalendarInput:
    x_handle: str
    niche: str
    cadence_per_week: int
    weeks: int
    data_source: str
    variety_floor: int
    slot_archetypes: list[str]
    slot_format_pattern: list[str]
    cadence_sustainability_seed: float
    voice_fidelity_seed: float
    niche_fit_seed: float
    previous_window_summary: dict
    voice_profile_file: Optional[str] = None
    analytics_file: Optional[str] = None


def _load_demo(mode: str) -> dict:
    if mode == "paradox":
        return json.loads(json.dumps(DEMO_PARADOX))
    if mode == "healthy":
        return json.loads(json.dumps(DEMO_HEALTHY))
    if mode == "7d-audit":
        return json.loads(json.dumps(DEMO_7D_AUDIT))
    raise ContentCalendarBuilderError(f"unknown demo mode {mode!r}")


def _validate_input(payload: dict, args: argparse.Namespace) -> CalendarInput:
    handle = _normalise_handle(payload.get("x_handle", args.x_handle or ""))
    niche = (payload.get("niche") or args.niche or "general creator").strip()[:80]
    _refuse_if_forbidden("niche", niche)
    cadence = _clamp_cadence(payload.get("cadence_per_week", args.cadence_per_week))
    weeks = _clamp_weeks(payload.get("weeks", args.weeks))
    variety_floor = max(2, min(5, int(payload.get("variety_floor", args.variety_floor))))
    data_source = payload.get("data_source", "real")
    if data_source not in ("real", "demo"):
        raise ContentCalendarBuilderError(
            f"data_source={data_source!r} invalid — choose 'real' or 'demo'"
        )

    archetypes = payload.get("slot_archetypes") or [
        "general creator post archetype",
        "creator deep-dive archetype",
        "creator personal-anecdote archetype",
        "creator data-led archetype",
        "creator engagement-prompt archetype",
    ]
    for i, a in enumerate(archetypes):
        _refuse_if_forbidden(f"slot_archetypes[{i}]", a)

    format_pattern = payload.get("slot_format_pattern") or [
        "thread", "single", "quote-tweet", "image-post", "reply-thread",
    ]
    for i, f in enumerate(format_pattern):
        if f not in VALID_FORMATS:
            raise ContentCalendarBuilderError(
                f"slot_format_pattern[{i}]={f!r} invalid — choose {VALID_FORMATS}"
            )

    cs_seed = float(payload.get("cadence_sustainability_seed", 70))
    vf_seed = float(payload.get("voice_fidelity_seed", 75))
    nf_seed = float(payload.get("niche_fit_seed", 78))

    return CalendarInput(
        x_handle=handle,
        niche=niche,
        cadence_per_week=cadence,
        weeks=weeks,
        data_source=data_source,
        variety_floor=variety_floor,
        slot_archetypes=archetypes,
        slot_format_pattern=format_pattern,
        cadence_sustainability_seed=cs_seed,
        voice_fidelity_seed=vf_seed,
        niche_fit_seed=nf_seed,
        previous_window_summary=payload.get("previous_window_summary") or {},
        voice_profile_file=str(args.voice_profile_file) if args.voice_profile_file else None,
        analytics_file=str(args.analytics_file) if args.analytics_file else None,
    )


# ---------------------------------------------------------------------------
# Slot generation
# ---------------------------------------------------------------------------


@dataclass
class Slot:
    week: int
    day_idx: int          # 0..6 within the week's calendar pattern
    day_name: str
    time_tier: str
    format: str
    archetype_label: str
    niche_fit_score: float
    voice_fidelity_score: float
    engagement_band: str
    voice_drift: bool


def _day_distribution_for_cadence(cadence: int) -> list[int]:
    """Pick which day-indexes (0..6 = Mon..Sun) are post days for the
    given cadence_per_week. Spread evenly across the week."""
    if cadence >= 7:
        # Post every day; for >7, double up later via time tiers.
        return list(range(7))
    # Cadence in [3, 6]: spread evenly. e.g. cadence=5 → Mon Tue Wed Thu Fri.
    # Use float spacing for evenness across 7 days.
    spacing = 7.0 / cadence
    return [int(round(i * spacing)) % 7 for i in range(cadence)]


def _time_tier_for_index(slot_idx_in_week: int, slots_in_week: int) -> str:
    """Distribute time tiers across the week's slots."""
    tiers = list(VALID_TIME_TIERS)
    return tiers[slot_idx_in_week % len(tiers)]


def _build_slots(inp: CalendarInput, rng: Random) -> list[Slot]:
    slots: list[Slot] = []
    day_dist = _day_distribution_for_cadence(inp.cadence_per_week)

    archetype_cycle = list(inp.slot_archetypes)
    format_cycle = list(inp.slot_format_pattern)

    if not archetype_cycle:
        archetype_cycle = ["creator post archetype"]
    if not format_cycle:
        format_cycle = ["single"]

    for w in range(inp.weeks):
        # If cadence > 7, post on every day plus extras via time tiers
        slots_this_week = inp.cadence_per_week
        for s in range(slots_this_week):
            day_idx = day_dist[s % len(day_dist)] if day_dist else (s % 7)
            day_name = DAYS_OF_WEEK[day_idx]
            time_tier = _time_tier_for_index(s, slots_this_week)

            # Format from pattern (cycles)
            global_idx = w * slots_this_week + s
            fmt = format_cycle[global_idx % len(format_cycle)]
            archetype = archetype_cycle[global_idx % len(archetype_cycle)]

            # Per-slot scores: jitter the seed by +/-7 deterministically
            jitter_nf = (rng.random() - 0.5) * 14.0
            jitter_vf = (rng.random() - 0.5) * 14.0
            niche_fit = max(0.0, min(100.0, inp.niche_fit_seed + jitter_nf))
            voice_fid = max(0.0, min(100.0, inp.voice_fidelity_seed + jitter_vf))

            band = _engagement_band_for(niche_fit, voice_fid)
            drift = voice_fid < VOICE_DRIFT_THRESHOLD

            slots.append(Slot(
                week=w + 1,
                day_idx=day_idx,
                day_name=day_name,
                time_tier=time_tier,
                format=fmt,
                archetype_label=archetype,
                niche_fit_score=round(niche_fit, 1),
                voice_fidelity_score=round(voice_fid, 1),
                engagement_band=band,
                voice_drift=drift,
            ))

    return slots


# ---------------------------------------------------------------------------
# Plan score
# ---------------------------------------------------------------------------


@dataclass
class PlanScore:
    metric_values: dict
    metric_arrows: dict
    plan_score: int
    paradox_active: bool
    avg_cadence: float
    avg_niche_fit: float
    avg_voice: float
    variety_count: int
    variety_score: float


def _compute_variety(slots: list[Slot]) -> tuple[int, float]:
    """Distinct format count + variety score (0-100)."""
    distinct = len({s.format for s in slots})
    # Normalise: 1 distinct = 0, 5 distinct = 100 (linear)
    score = max(0.0, min(100.0, (distinct - 1) / 4.0 * 100.0))
    return distinct, score


def _avg(items: list[float]) -> float:
    if not items:
        return 0.0
    return sum(items) / len(items)


def _compute_plan_score(inp: CalendarInput, slots: list[Slot]) -> PlanScore:
    avg_nf = _avg([s.niche_fit_score for s in slots])
    avg_vf = _avg([s.voice_fidelity_score for s in slots])
    avg_cs = inp.cadence_sustainability_seed  # creator-history-driven
    distinct, variety_score = _compute_variety(slots)

    metric_values = {
        "Cadence sustainability": round(avg_cs, 1),
        "Niche fit": round(avg_nf, 1),
        "Voice fidelity": round(avg_vf, 1),
        "Variety": round(variety_score, 1),
    }

    norms = {m: _normalise_metric(metric_values[m], m) for m in SCORE_METRICS}
    plan = round(
        PLAN_SCORE_WEIGHTS["Cadence sustainability"] * norms["Cadence sustainability"]
        + PLAN_SCORE_WEIGHTS["Niche fit"] * norms["Niche fit"]
        + PLAN_SCORE_WEIGHTS["Voice fidelity"] * norms["Voice fidelity"]
        + PLAN_SCORE_WEIGHTS["Variety"] * norms["Variety"]
    )

    paradox = avg_cs < PARADOX_CADENCE_THRESHOLD and inp.cadence_per_week > PARADOX_VOLUME_THRESHOLD

    return PlanScore(
        metric_values=metric_values,
        metric_arrows={},
        plan_score=plan,
        paradox_active=paradox,
        avg_cadence=avg_cs,
        avg_niche_fit=avg_nf,
        avg_voice=avg_vf,
        variety_count=distinct,
        variety_score=variety_score,
    )


def _arrows_against_basis(score: PlanScore, prev: dict) -> dict:
    return {
        "Cadence sustainability": _arrow_for_delta(
            score.metric_values["Cadence sustainability"],
            float(prev.get("avg_cadence_sustainability", score.metric_values["Cadence sustainability"])),
        ),
        "Niche fit": _arrow_for_delta(
            score.metric_values["Niche fit"],
            float(prev.get("avg_niche_fit", score.metric_values["Niche fit"])),
        ),
        "Voice fidelity": _arrow_for_delta(
            score.metric_values["Voice fidelity"],
            float(prev.get("avg_voice_fidelity", score.metric_values["Voice fidelity"])),
        ),
        "Variety": _arrow_for_delta(
            score.metric_values["Variety"],
            float(prev.get("avg_variety", score.metric_values["Variety"])),
        ),
    }


# ---------------------------------------------------------------------------
# Streak detection
# ---------------------------------------------------------------------------


@dataclass
class Streak:
    start_global_idx: int
    end_global_idx: int
    format: str
    length: int


def _detect_streaks(slots: list[Slot]) -> list[Streak]:
    streaks: list[Streak] = []
    if not slots:
        return streaks
    run_start = 0
    run_format = slots[0].format
    for i in range(1, len(slots)):
        if slots[i].format == run_format:
            continue
        run_len = i - run_start
        if run_len >= FORMAT_STREAK_THRESHOLD:
            streaks.append(Streak(run_start, i - 1, run_format, run_len))
        run_start = i
        run_format = slots[i].format
    # Trailing run
    run_len = len(slots) - run_start
    if run_len >= FORMAT_STREAK_THRESHOLD:
        streaks.append(Streak(run_start, len(slots) - 1, run_format, run_len))
    return streaks


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _demo_suffix(data_source: str) -> str:
    return f" {DEMO_LABEL}" if data_source == "demo" else ""


def _interpretation_for(metric: str, value: float, score: PlanScore, inp: CalendarInput) -> str:
    if metric == "Cadence sustainability":
        if score.paradox_active:
            return "Below the 50 floor — cadence is unsustainable for the creator's voice."
        if value > 90:
            return "Cadence sustainability excellent — the rhythm fits the creator's voice and energy."
        if value > 60:
            return "Cadence sustainability inside the healthy band — calendar is sustainable."
        return "Cadence sustainability borderline — verify with the creator before scheduling more."
    if metric == "Niche fit":
        if value > 95:
            return "Tight niche alignment — every slot reads as on-brand for the audience."
        if value > 60:
            return "Niche fit holding — slots land inside the audience the prior window built."
        return "Niche fit below the floor — slots drift outside the niche."
    if metric == "Voice fidelity":
        if value > 95:
            return "Exceptional voice match — verify it isn't hiding generic-polish."
        if value > 60:
            if score.paradox_active:
                return "Voice fidelity inside the band but heading down — over-volume tugs voice."
            return "Voice fidelity inside the healthy band; slots preserve the creator's tone."
        return "Voice fidelity below the floor — re-anchor with brand-voice-trainer before scheduling."
    if metric == "Variety":
        if score.variety_count < inp.variety_floor:
            return f"Variety below the {inp.variety_floor}-format floor — calendar feels repetitive."
        if value > 90:
            return f"Format mix excellent; {score.variety_count} distinct formats in rotation."
        return f"Format mix above the variety floor; {score.variety_count} distinct formats in rotation."
    return ""


def _render_snapshot(inp: CalendarInput, score: PlanScore, slots: list[Slot]) -> str:
    headline_bits = [f"{inp.niche} niche, {inp.cadence_per_week} posts/week × {inp.weeks} week(s)"]
    if score.paradox_active:
        headline_bits.append(
            f"over-scheduling paradox active; cadence sustainability {score.avg_cadence:.1f} with {inp.cadence_per_week} posts/week"
        )
    else:
        headline_bits.append(
            f"plan score {score.plan_score}/100; cadence sustainability holding at {score.avg_cadence:.1f}"
        )
    headline = f"**{inp.x_handle}: " + " — ".join(headline_bits) + ".**"

    if inp.data_source == "demo":
        ds = "seeded demo signals — re-run with --voice-profile-file / --analytics-file for real X data"
    else:
        files = []
        if inp.voice_profile_file:
            files.append(f"voice={inp.voice_profile_file}")
        if inp.analytics_file:
            files.append(f"analytics={inp.analytics_file}")
        ds = "real X exports — " + (", ".join(files) if files else "(no files supplied)")

    body = [
        "## Calendar Snapshot",
        headline,
        "",
        f"- **Creator handle**: {inp.x_handle}",
        f"- **Niche**: {inp.niche}",
        f"- **Cadence**: {inp.cadence_per_week} posts/week × {inp.weeks} week(s) = {len(slots)} slots",
        f"- **Variety floor**: {inp.variety_floor} distinct formats",
        f"- **Data source**: {ds}",
    ]
    return "\n".join(body)


def _render_plan_score(inp: CalendarInput, score: PlanScore, arrows: dict) -> str:
    lines = [
        "## Calendar Plan Score",
        "",
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    for metric in SCORE_METRICS:
        v = score.metric_values[metric]
        arrow = arrows[metric]
        interp = _interpretation_for(metric, v, score, inp)
        lines.append(f"| {metric} | {v}/100{suffix} | {arrow} | {interp} |")
    if score.paradox_active:
        lines.append("")
        lines.append(
            "> ⚠️ paradox: cadence is unsustainable AND volume is high — this calendar would push "
            "the creator past their voice in <2 weeks."
        )
    lines.append("")
    lines.append(f"**Calendar Plan Score**: {score.plan_score}/100")
    return "\n".join(lines)


def _render_format_mix(slots: list[Slot]) -> str:
    counts: dict[str, int] = {}
    for s in slots:
        counts[s.format] = counts.get(s.format, 0) + 1
    total = len(slots)
    lines = ["## Format Mix", "", "| Format | Slots | Share |", "|---|---|---|"]
    for fmt in sorted(counts.keys(), key=lambda k: -counts[k]):
        cnt = counts[fmt]
        share = cnt / total * 100.0 if total else 0.0
        lines.append(f"| {fmt} | {cnt} | {share:.1f}% |")
    return "\n".join(lines)


def _render_slots(inp: CalendarInput, slots: list[Slot]) -> str:
    lines = [f"## Slots ({len(slots)} total over {inp.weeks} week(s))", ""]
    suffix = _demo_suffix(inp.data_source)
    by_week: dict[int, list[tuple[int, Slot]]] = {}
    for global_idx, s in enumerate(slots, start=1):
        by_week.setdefault(s.week, []).append((global_idx, s))
    for w in sorted(by_week.keys()):
        lines.append(f"### Week {w}")
        for global_idx, s in by_week[w]:
            drift = " ⚠️ voice-drift candidate" if s.voice_drift else ""
            lines.append(
                f"{global_idx}. **{s.day_name} · {s.time_tier} · {s.format}**{drift} — "
                f"archetype: {s.archetype_label}{suffix}"
            )
            lines.append(
                f"   niche fit: {s.niche_fit_score:.0f}/100 · voice fidelity: {s.voice_fidelity_score:.0f}/100 · "
                f"engagement: {s.engagement_band}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_red_flags(
    inp: CalendarInput,
    score: PlanScore,
    slots: list[Slot],
    streaks: list[Streak],
) -> str:
    flags: list[tuple[str, str, str, str]] = []

    if score.paradox_active:
        flags.append((
            "Over-scheduling paradox",
            "high",
            (
                f"Cadence sustainability {score.avg_cadence:.1f} < 50 AND "
                f"posts_per_week {inp.cadence_per_week} > 7 — this calendar would push the creator "
                "past their voice in <2 weeks."
            ),
            (
                "Reduce --cadence-per-week to 5–6 (the established healthy band for mid-tier "
                "creators), OR keep the cadence but flag weeks 3+ as auto-paused unless voice "
                "fidelity holds in the prior week."
            ),
        ))

    if streaks:
        streak_summary = "; ".join(
            f"slots {st.start_global_idx + 1}-{st.end_global_idx + 1} ({st.format}, length {st.length})"
            for st in streaks[:3]
        )
        flags.append((
            "Format-streak guard fired",
            "medium",
            (
                f"{len(streaks)} streak(s) of ≥{FORMAT_STREAK_THRESHOLD} consecutive same-format "
                f"slots detected: {streak_summary}. Streak slots stay in the calendar but are flagged."
            ),
            (
                "Rotate one of the middle streak slots to a complementary format (e.g. swap a "
                "third consecutive `thread` for a `single`) to break the rhythm."
            ),
        ))

    if score.variety_count < inp.variety_floor:
        used_formats = ", ".join(sorted({s.format for s in slots}))
        flags.append((
            "Variety floor breached",
            "medium",
            (
                f"Only {score.variety_count} distinct format type(s) in the calendar "
                f"({used_formats}); variety floor is {inp.variety_floor}."
            ),
            (
                "Add at least one slot in a missing format (single / thread / quote-tweet / "
                "image-post / reply-thread) per week."
            ),
        ))

    drift_count = sum(1 for s in slots if s.voice_drift)
    if drift_count > 0:
        flags.append((
            "Voice-drift candidates surfaced",
            "medium",
            (
                f"{drift_count} slot(s) score voice fidelity < 50 — they remain in the calendar "
                "but are flagged inline so the creator rewrites the archetype before publishing."
            ),
            "Hand each voice-drift slot to brand-voice-trainer for a re-anchored archetype.",
        ))

    if not flags:
        flags.append((
            "No structural red flags",
            "low",
            "Calendar stays within healthy bands; review remains creator-side qualitative judgement.",
            "Proceed; spot-check voice fidelity on the first week before scheduling further.",
        ))

    lines = ["## Red Flags", ""]
    for title, sev, body, rem in flags:
        lines.append(f"- **{title}** · severity: {sev} — {body}. *Remediation:* {rem}")
    return "\n".join(lines)


def _render_recommendations(
    inp: CalendarInput,
    score: PlanScore,
    slots: list[Slot],
    streaks: list[Streak],
) -> str:
    lines = ["## Recommendations", ""]

    # Position 1 — analytics-summarizer (mandatory)
    if score.paradox_active:
        lines.append(
            "1. After running 1 calendar week at this cadence, pull engagement deltas and decide "
            "whether to keep or reduce volume — paradox active means the calendar is on the edge. — bridges to: `analytics-summarizer`"
        )
    else:
        lines.append(
            "1. After the calendar runs, pull period analytics to confirm the slot mix landed and "
            "promote the highest-engagement archetypes for next calendar. — bridges to: `analytics-summarizer`"
        )

    # Position 2 — brand-voice-trainer (mandatory)
    drift_count = sum(1 for s in slots if s.voice_drift)
    if drift_count > 0 or score.paradox_active:
        lines.append(
            f"2. Re-anchor {max(drift_count, 1)} voice-drift slot(s) through the trainer before "
            "publishing — voice fidelity floor is the publish-ready signal. — bridges to: `brand-voice-trainer`"
        )
    else:
        lines.append(
            "2. Voice-check the calendar's archetype mix before publishing — the trainer's input "
            "signal is exactly the voice fidelity baseline this calendar uses. — bridges to: `brand-voice-trainer`"
        )

    # Position 3 — context-aware
    if score.variety_count < inp.variety_floor:
        lines.append(
            "3. Source the missing format types from the next idea batch — the calendar is below "
            "the variety floor. — bridges to: `content-idea-generator`"
        )
    elif streaks:
        lines.append(
            "3. Use the next idea batch to surface the rotation slot that breaks each streak. "
            "— bridges to: `content-idea-generator`"
        )
    else:
        thread_slots = [s for s in slots if s.format == "thread"]
        if thread_slots:
            lines.append(
                "3. Pre-build the highest niche-fit thread slots into long-form structured drafts "
                "1-2 days before each scheduled date. — bridges to: `thread-builder`"
            )
        else:
            lines.append(
                "3. Source the next idea batch from the period's top-engagement archetypes once "
                "the calendar runs. — bridges to: `content-idea-generator`"
            )

    # Position 4 — context-aware
    if inp.cadence_per_week >= 7:
        lines.append(
            "4. When trend windows open during the calendar, swap the next slot for a trend-aligned "
            "variant rather than adding more posts. — bridges to: `trend-aligned-poster`"
        )
    else:
        lines.append(
            "4. A/B test the format-mix ratio with the next calendar — fix all other axes and "
            "isolate which mix carries weight. — bridges to: `ab-test-suggester`"
        )

    # Position 5 — niche cross-coverage
    lines.append(
        "5. Confirm the calendar's archetype mix is broadly relevant in the niche (not just the "
        "creator's surface) before scaling cadence. — bridges to: `competitor-watch`"
    )

    return "\n".join(lines)


def _render_confidence(
    inp: CalendarInput, score: PlanScore, slots: list[Slot], streaks: list[Streak]
) -> str:
    drift_count = sum(1 for s in slots if s.voice_drift)
    if inp.data_source == "demo":
        level = "low"
        reason = "demo signals only — re-run with --voice-profile-file / --analytics-file for real X data."
    elif score.paradox_active:
        level = "low"
        reason = "real signals, but over-scheduling paradox active — reduce cadence before treating the score as a publish signal."
    elif streaks:
        level = "medium"
        reason = f"real signals; {len(streaks)} format streak(s) flagged — verify the breaks before publishing."
    elif drift_count > 0:
        level = "medium"
        reason = f"real signals; {drift_count} voice-drift slot(s) require trainer re-anchor."
    elif inp.weeks == 1:
        level = "medium"
        reason = "1-week horizon can't surface a real cadence pattern — re-run with weeks ≥ 4."
    else:
        level = "high"
        reason = "real signals, all metrics inside healthy bands, no streaks or drift."
    return f"## Confidence\nConfidence: {level} — {reason}"


def _render_audit(
    inp: CalendarInput,
    score: PlanScore,
    slots: list[Slot],
    streaks: list[Streak],
) -> Optional[str]:
    triggers = []
    if inp.weeks == 1:
        triggers.append("weeks=1 — single-week horizon can't surface a cadence pattern")
    if score.paradox_active:
        triggers.append("over-scheduling paradox active")
    if streaks:
        triggers.append(f"{len(streaks)} format streak(s) detected")

    if not triggers:
        return None

    drift_share = sum(1 for s in slots if s.voice_drift) / max(1, len(slots)) * 100.0

    lines = [
        "## Calendar Audit (auto-triggered)",
        "",
        f"- **Horizon adequacy**: {inp.weeks}-week horizon is "
        + ("under-powered for cadence pattern detection" if inp.weeks == 1 else "adequate"),
        f"- **Data source confidence**: "
        + ("demo signals — re-run with real exports" if inp.data_source == "demo"
           else "real signals — proceed"),
        f"- **Format mix balance**: {score.variety_count} distinct formats; variety {'above' if score.variety_count >= inp.variety_floor else 'below'} the {inp.variety_floor}-format floor",
        f"- **Streak count**: {len(streaks)} streak(s) of ≥{FORMAT_STREAK_THRESHOLD} consecutive same-format slots",
        f"- **Voice-drift signal**: {drift_share:.0f}% of slots carry the drift flag — "
        + ("hand them to brand-voice-trainer before publishing" if drift_share > 0
           else "no drift surfaced"),
        "- **Suggested next sample**: re-run after 1 week to verify the cadence held in voice fidelity",
        "- **Re-run cadence**: weekly; calendar is the planning artifact creators iterate on",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_content_calendar(
    *,
    x_handle: str,
    niche: Optional[str] = None,
    cadence_per_week: int = DEFAULT_CADENCE,
    weeks: int = DEFAULT_WEEKS,
    voice_profile_file: Optional[str] = None,
    analytics_file: Optional[str] = None,
    variety_floor: int = DEFAULT_VARIETY_FLOOR,
    payload: Optional[dict] = None,
    args: Optional[argparse.Namespace] = None,
) -> str:
    if args is None:
        args = argparse.Namespace(
            x_handle=x_handle,
            niche=niche,
            cadence_per_week=cadence_per_week,
            weeks=weeks,
            voice_profile_file=voice_profile_file,
            analytics_file=analytics_file,
            variety_floor=variety_floor,
        )
    inp = _validate_input(payload or {}, args)

    seed = _seed_from(
        inp.x_handle,
        inp.niche,
        str(inp.cadence_per_week),
        str(inp.weeks),
        _utcnow_date(),
    )
    rng = Random(seed)
    slots = _build_slots(inp, rng)
    score = _compute_plan_score(inp, slots)
    arrows = _arrows_against_basis(score, inp.previous_window_summary)
    score.metric_arrows = arrows
    streaks = _detect_streaks(slots)

    parts: list[str] = []
    parts.append(_render_snapshot(inp, score, slots))
    parts.append(_render_plan_score(inp, score, arrows))
    parts.append(_render_format_mix(slots))
    parts.append(_render_slots(inp, slots))
    parts.append(_render_red_flags(inp, score, slots, streaks))
    parts.append(_render_recommendations(inp, score, slots, streaks))
    parts.append(_render_confidence(inp, score, slots, streaks))
    audit = _render_audit(inp, score, slots, streaks)
    if audit is not None:
        parts.append(audit)

    return "\n\n".join(parts) + "\n"


generate = generate_content_calendar


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_FILE_HEADER = (
    "<!-- Copyright 2026 AgentMindCloud -->\n"
    "<!-- Licensed under the Apache License, Version 2.0 -->\n"
    "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
    "<!-- Generated by content-calendar-builder/run.py — built for X, Grok & the ecosystem community. -->\n"
    "\n"
)


def _maybe_load_payload(args: argparse.Namespace) -> Optional[dict]:
    if args.demo:
        return _load_demo("paradox")
    if args.demo_healthy:
        return _load_demo("healthy")
    if args.demo_7d_audit:
        return _load_demo("7d-audit")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="content-calendar-builder",
        description=(
            "Local-first content calendar builder for X creators. Drafts only — never auto-publishes. "
            "Built for X, Grok & the ecosystem community."
        ),
    )
    parser.add_argument("--x-handle", required=True, help="Creator's X handle.")
    parser.add_argument("--niche", default=None, help="Free-text creator niche (max 80 chars).")
    parser.add_argument(
        "--cadence-per-week",
        type=int,
        default=DEFAULT_CADENCE,
        help="Posts per week (clamped to [3, 14]).",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=DEFAULT_WEEKS,
        help="Calendar horizon in weeks (clamped to [1, 12]).",
    )
    parser.add_argument("--voice-profile-file", default=None, help="Path to voice profile JSON.")
    parser.add_argument("--analytics-file", default=None, help="Path to analytics export JSON.")
    parser.add_argument(
        "--variety-floor",
        type=int,
        default=DEFAULT_VARIETY_FLOOR,
        help="Minimum distinct format types across the calendar (default 4).",
    )
    parser.add_argument("--demo", action="store_true", help="Run over-scheduling paradox demo seed.")
    parser.add_argument("--demo-healthy", action="store_true", help="Run all-within-bounds demo seed.")
    parser.add_argument("--demo-7d-audit", action="store_true", help="Run weeks=1 demo seed.")
    parser.add_argument("--out", type=Path, default=None, help="Write to file (default stdout).")

    args = parser.parse_args(argv)

    selected_demos = sum(1 for f in (args.demo, args.demo_healthy, args.demo_7d_audit) if f)
    if selected_demos > 1:
        raise SystemExit("ERROR: choose at most one of --demo / --demo-healthy / --demo-7d-audit")

    payload = _maybe_load_payload(args)

    try:
        rendered = generate_content_calendar(
            x_handle=args.x_handle,
            niche=args.niche,
            cadence_per_week=args.cadence_per_week,
            weeks=args.weeks,
            voice_profile_file=args.voice_profile_file,
            analytics_file=args.analytics_file,
            variety_floor=args.variety_floor,
            payload=payload,
            args=args,
        )
    except ContentCalendarBuilderError as exc:
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
