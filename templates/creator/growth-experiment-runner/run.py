# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Growth Experiment Runner — runner.

CLI entry point for the ``growth-experiment-runner`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads creator-supplied hypothesis bundle (JSON) — or seeded demo data
when no file is provided — and emits the strict 7/8-section experiment
plan defined by the system prompt:

  1. Experiment Snapshot
  2. Experiment Plan Score (4-row metric table + weighted score)
  3. Sample-Power Profile
  4. Experiment Cards (3-6 entries)
  5. Red Flags (2-4, surfaces small-n paradox + multi-variable guard
     + risk-exclude guard)
  6. Recommendations (3-5, mandatory bridges to analytics-summarizer
     and ab-test-suggester)
  7. Confidence
  + Optional Experiment Audit (auto-appended when window=7d, paradox
    fires, or multi-variable guard fires)

Hard guarantees:

* Drafts only — never auto-runs.
* No fabricated statistics. Demo metrics carry an explicit
  `[demo experiment — re-run with --hypothesis-file for real audience data]`
  label.
* Small-n paradox surfaced in BOTH the Plan Score section AND the
  Red Flags section whenever average Sample power < 40 AND average
  Hypothesis specificity > 70.
* Multi-variable guard: any experiment with axis_count > 1 →
  excluded + Red Flag.
* Risk-exclude guard: any experiment with risk_avoidance_score < 40 →
  excluded + Red Flag.
* Plan Score formula:
    round(0.30*HypothesisSpecificity_norm + 0.25*SingleAxisIsolation_norm +
          0.25*SamplePower_norm + 0.20*RiskAvoidance_norm).
* Unconditional bridges to analytics-summarizer (position 1) and
  ab-test-suggester (position 2).
* No finance / cashtag / sponsorship / harassment / unsafe-experiment
  content.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic: seeded by sha256(handle + audience + window + date).
* Zero external network calls in v1.

Manifest contract::

    generate = generate_growth_experiment_plan

Built for X, Grok & the ecosystem community.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
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
    "Hypothesis specificity",
    "Single-axis isolation",
    "Sample power",
    "Risk avoidance",
)

PLAN_SCORE_WEIGHTS = {
    "Hypothesis specificity": 0.30,
    "Single-axis isolation": 0.25,
    "Sample power": 0.25,
    "Risk avoidance": 0.20,
}

HEALTHY_RANGES = {
    "Hypothesis specificity": (60.0, 95.0),
    "Single-axis isolation": (70.0, 100.0),
    "Sample power": (50.0, 95.0),
    "Risk avoidance": (70.0, 100.0),
}

WINDOW_OPTIONS = (7, 30, 90)

# Small-n paradox.
PARADOX_SAMPLE_POWER_THRESHOLD = 40.0
PARADOX_HYPOTHESIS_SPECIFICITY_THRESHOLD = 70.0

DEFAULT_RISK_FLOOR = 40.0
DEFAULT_POWER_FLOOR = 40.0

EXPERIMENT_COUNT_MIN = 3
EXPERIMENT_COUNT_MAX = 6
DEFAULT_MAX_EXPERIMENTS = 4
DEFAULT_AUDIENCE_SIZE = 12000

VALID_PRIMARY_METRICS = (
    "engagement_rate",
    "impressions",
    "follower_delta",
    "reply_rate",
    "click_rate",
    "thread_completion_rate",
    "monetization_channel_revenue",
    "mention_quality_score",
)

CROSS_TEMPLATE_BRIDGES = (
    "analytics-summarizer",
    "ab-test-suggester",
    "content-idea-generator",
    "competitor-watch",
    "follower-quality-analyzer",
    "brand-voice-trainer",
    "thread-builder",
    "mention-summarizer",
    "monetization-optimizer",
)

MANDATORY_BRIDGES = ("analytics-summarizer", "ab-test-suggester")

DEMO_LABEL = (
    "[demo experiment — re-run with --hypothesis-file for real audience data]"
)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_PARADOX = {
    "x_handle": "@JanSol0s",
    "audience_size": 12000,
    "window": 30,
    "data_source": "demo",
    "baseline_metric_name": "engagement_rate",
    "baseline_metric_value": 2.4,
    "previous_window_summary": {
        "avg_hypothesis_specificity": 72.0,
        "avg_single_axis_isolation": 82.0,
        "avg_sample_power": 60.0,
        "avg_risk_avoidance": 88.0,
    },
    "candidate_experiments": [
        # Tight specificity but sample power too low — this fires the small-n paradox
        {
            "hypothesis": "Switching the opening hook from a question to a single concrete number raises engagement_rate by 0.4 percentage points",
            "axis_count": 1,
            "axis_label": "opening_hook_format",
            "expected_effect_pct": 0.4,
            "planned_runtime_days": 30,
            "primary_metric": "engagement_rate",
            "success_criteria": "engagement_rate uplift ≥ 0.4 pts vs the prior 30d baseline",
            "hypothesis_specificity_score": 88,
            "single_axis_isolation_score": 95,
            "sample_power_score": 28,  # too low for 0.4 pt detection at this audience size
            "risk_avoidance_score": 92,
        },
        {
            "hypothesis": "Adding a one-line creator-experience anchor at the bottom of long threads raises thread_completion_rate by 1 percentage point",
            "axis_count": 1,
            "axis_label": "thread_anchor_position",
            "expected_effect_pct": 1.0,
            "planned_runtime_days": 30,
            "primary_metric": "thread_completion_rate",
            "success_criteria": "thread_completion_rate uplift ≥ 1.0 pt vs the prior 30d baseline",
            "hypothesis_specificity_score": 82,
            "single_axis_isolation_score": 90,
            "sample_power_score": 30,
            "risk_avoidance_score": 90,
        },
        {
            "hypothesis": "Moving image-post timing from afternoon to evening lifts impressions by 1 percentage point",
            "axis_count": 1,
            "axis_label": "image_post_time_tier",
            "expected_effect_pct": 1.0,
            "planned_runtime_days": 30,
            "primary_metric": "impressions",
            "success_criteria": "impressions uplift ≥ 1% vs the prior 30d baseline",
            "hypothesis_specificity_score": 75,
            "single_axis_isolation_score": 88,
            "sample_power_score": 25,
            "risk_avoidance_score": 88,
        },
        {
            "hypothesis": "Increasing posting cadence and switching the opening hook simultaneously will lift engagement_rate by 1 percentage point",
            "axis_count": 2,  # → multi-variable, excluded
            "axis_label": "cadence + opening_hook (two axes)",
            "expected_effect_pct": 1.0,
            "planned_runtime_days": 30,
            "primary_metric": "engagement_rate",
            "success_criteria": "engagement_rate uplift ≥ 1.0 pt",
            "hypothesis_specificity_score": 70,
            "single_axis_isolation_score": 25,
            "sample_power_score": 35,
            "risk_avoidance_score": 80,
        },
        {
            "hypothesis": "Running aggressive dunk-style quote-tweets on competitor posts raises follower_delta by 0.5 percentage points",
            "axis_count": 1,
            "axis_label": "quote_tweet_stance",
            "expected_effect_pct": 0.5,
            "planned_runtime_days": 30,
            "primary_metric": "follower_delta",
            "success_criteria": "follower_delta uplift ≥ 0.5 pts",
            "hypothesis_specificity_score": 78,
            "single_axis_isolation_score": 90,
            "sample_power_score": 30,
            "risk_avoidance_score": 25,  # → high-risk, excluded
        },
        {
            "hypothesis": "Pinning the top weekly thread to the profile lifts reply_rate by 0.3 percentage points",
            "axis_count": 1,
            "axis_label": "pinned_post_format",
            "expected_effect_pct": 0.3,
            "planned_runtime_days": 30,
            "primary_metric": "reply_rate",
            "success_criteria": "reply_rate uplift ≥ 0.3 pt",
            "hypothesis_specificity_score": 80,
            "single_axis_isolation_score": 92,
            "sample_power_score": 28,
            "risk_avoidance_score": 90,
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "audience_size": 24000,
    "window": 30,
    "data_source": "demo",
    "baseline_metric_name": "engagement_rate",
    "baseline_metric_value": 4.0,
    "previous_window_summary": {
        "avg_hypothesis_specificity": 80.0,
        "avg_single_axis_isolation": 92.0,
        "avg_sample_power": 75.0,
        "avg_risk_avoidance": 92.0,
    },
    "candidate_experiments": [
        {
            "hypothesis": "Replacing the opening question with a one-line claim raises engagement_rate by 1 percentage point",
            "axis_count": 1,
            "axis_label": "opening_hook_format",
            "expected_effect_pct": 1.0,
            "planned_runtime_days": 30,
            "primary_metric": "engagement_rate",
            "success_criteria": "engagement_rate uplift ≥ 1.0 pt vs the prior 30d baseline",
            "hypothesis_specificity_score": 88,
            "single_axis_isolation_score": 95,
            "sample_power_score": 78,
            "risk_avoidance_score": 95,
        },
        {
            "hypothesis": "Adding a personal-anecdote anchor to friction-audit threads lifts thread_completion_rate by 2 percentage points",
            "axis_count": 1,
            "axis_label": "thread_anchor_format",
            "expected_effect_pct": 2.0,
            "planned_runtime_days": 30,
            "primary_metric": "thread_completion_rate",
            "success_criteria": "thread_completion_rate uplift ≥ 2.0 pts",
            "hypothesis_specificity_score": 84,
            "single_axis_isolation_score": 92,
            "sample_power_score": 80,
            "risk_avoidance_score": 92,
        },
        {
            "hypothesis": "Swapping the weekly numbers post for a numbers-led case study raises impressions by 8 percentage points",
            "axis_count": 1,
            "axis_label": "weekly_numbers_format",
            "expected_effect_pct": 8.0,
            "planned_runtime_days": 30,
            "primary_metric": "impressions",
            "success_criteria": "impressions uplift ≥ 8% vs the prior 30d baseline",
            "hypothesis_specificity_score": 82,
            "single_axis_isolation_score": 90,
            "sample_power_score": 78,
            "risk_avoidance_score": 92,
        },
        {
            "hypothesis": "Moving the friction-audit thread from Monday to Wednesday lifts reply_rate by 0.8 percentage points",
            "axis_count": 1,
            "axis_label": "thread_post_day",
            "expected_effect_pct": 0.8,
            "planned_runtime_days": 30,
            "primary_metric": "reply_rate",
            "success_criteria": "reply_rate uplift ≥ 0.8 pt",
            "hypothesis_specificity_score": 78,
            "single_axis_isolation_score": 92,
            "sample_power_score": 72,
            "risk_avoidance_score": 92,
        },
    ],
}

DEMO_7D_AUDIT = {
    "x_handle": "@thindata",
    "audience_size": 8000,
    "window": 7,
    "data_source": "demo",
    "baseline_metric_name": "engagement_rate",
    "baseline_metric_value": 2.0,
    "previous_window_summary": {
        "avg_hypothesis_specificity": 76.0,
        "avg_single_axis_isolation": 85.0,
        "avg_sample_power": 60.0,
        "avg_risk_avoidance": 88.0,
    },
    "candidate_experiments": [
        {
            "hypothesis": "Switching the methodology-callout format from prose to bullet list lifts engagement_rate by 0.5 percentage points",
            "axis_count": 1,
            "axis_label": "callout_format",
            "expected_effect_pct": 0.5,
            "planned_runtime_days": 7,
            "primary_metric": "engagement_rate",
            "success_criteria": "engagement_rate uplift ≥ 0.5 pt",
            "hypothesis_specificity_score": 78,
            "single_axis_isolation_score": 88,
            "sample_power_score": 50,
            "risk_avoidance_score": 90,
        },
        {
            "hypothesis": "Adding an explicit limitation-line at the bottom of paper-interpretation threads lifts thread_completion_rate by 1 percentage point",
            "axis_count": 1,
            "axis_label": "thread_limitation_line",
            "expected_effect_pct": 1.0,
            "planned_runtime_days": 7,
            "primary_metric": "thread_completion_rate",
            "success_criteria": "thread_completion_rate uplift ≥ 1.0 pt",
            "hypothesis_specificity_score": 75,
            "single_axis_isolation_score": 90,
            "sample_power_score": 52,
            "risk_avoidance_score": 88,
        },
        {
            "hypothesis": "Pinning the divergence post to the profile lifts impressions by 4 percentage points",
            "axis_count": 1,
            "axis_label": "pinned_post_choice",
            "expected_effect_pct": 4.0,
            "planned_runtime_days": 7,
            "primary_metric": "impressions",
            "success_criteria": "impressions uplift ≥ 4% vs prior 7d",
            "hypothesis_specificity_score": 76,
            "single_axis_isolation_score": 90,
            "sample_power_score": 48,
            "risk_avoidance_score": 90,
        },
    ],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GrowthExperimentRunnerError(RuntimeError):
    """Raised for any creator-facing input or guard failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_handle(raw: str) -> str:
    handle = raw.strip().lstrip("@")
    if not handle:
        raise GrowthExperimentRunnerError("x_handle is required.")
    if " " in handle or len(handle) > 15:
        raise GrowthExperimentRunnerError(
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


def _validate_window(window: int) -> int:
    if window not in WINDOW_OPTIONS:
        raise GrowthExperimentRunnerError(
            f"window={window!r} is invalid — choose one of {WINDOW_OPTIONS}."
        )
    return window


def _clamp_max_experiments(target: int) -> int:
    return max(EXPERIMENT_COUNT_MIN, min(EXPERIMENT_COUNT_MAX, int(target)))


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
        raise GrowthExperimentRunnerError(
            f"refusing {label}: forbidden token(s) {flagged!r}"
        )


# ---------------------------------------------------------------------------
# Sample-power model
# ---------------------------------------------------------------------------


def _detection_floor(audience_size: int, runtime_days: int) -> float:
    """Return the smallest detectable effect (% pts) at ~80% power for the
    given audience and runtime, using a simple normal-approx heuristic."""
    effective_n = min(audience_size, 0.10 * audience_size * runtime_days / 30.0)
    if effective_n < 50:
        return 100.0  # not detectable; effectively saturate
    # 2 / sqrt(n), expressed as %.
    return 2.0 / math.sqrt(effective_n) * 100.0


def _heuristic_sample_power_score(audience_size: int, runtime_days: int, expected_effect_pct: float) -> float:
    floor_pct = _detection_floor(audience_size, runtime_days)
    if floor_pct <= 0:
        return 0.0
    if expected_effect_pct >= floor_pct:
        return 100.0
    # Linearly scale below the floor.
    return max(0.0, min(100.0, expected_effect_pct / floor_pct * 100.0))


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


@dataclass
class ExperimentInput:
    x_handle: str
    audience_size: int
    window: int
    data_source: str
    max_experiments: int
    risk_floor: float
    power_floor: float
    candidate_experiments: list[dict]
    previous_window_summary: dict
    baseline_metric_name: str
    baseline_metric_value: float
    hypothesis_file: Optional[str] = None


def _load_demo(mode: str) -> dict:
    if mode == "paradox":
        return json.loads(json.dumps(DEMO_PARADOX))
    if mode == "healthy":
        return json.loads(json.dumps(DEMO_HEALTHY))
    if mode == "7d-audit":
        return json.loads(json.dumps(DEMO_7D_AUDIT))
    raise GrowthExperimentRunnerError(f"unknown demo mode {mode!r}")


def _validate_experiment(e: dict, idx: int, audience: int) -> dict:
    required = (
        "hypothesis", "axis_count", "axis_label",
        "expected_effect_pct", "planned_runtime_days",
        "primary_metric", "success_criteria",
        "hypothesis_specificity_score", "single_axis_isolation_score",
        "risk_avoidance_score",
    )
    missing = [k for k in required if k not in e]
    if missing:
        raise GrowthExperimentRunnerError(f"experiment[{idx}] missing keys: {missing}")
    if not isinstance(e["axis_count"], int):
        raise GrowthExperimentRunnerError(
            f"experiment[{idx}].axis_count must be int; got {type(e['axis_count']).__name__}"
        )
    if e["axis_count"] < 1:
        raise GrowthExperimentRunnerError(
            f"experiment[{idx}].axis_count={e['axis_count']} invalid — must be >= 1"
        )
    if e["primary_metric"] not in VALID_PRIMARY_METRICS:
        raise GrowthExperimentRunnerError(
            f"experiment[{idx}].primary_metric={e['primary_metric']!r} invalid — choose {VALID_PRIMARY_METRICS}"
        )
    for k in ("expected_effect_pct", "planned_runtime_days"):
        v = e[k]
        if not isinstance(v, (int, float)):
            raise GrowthExperimentRunnerError(
                f"experiment[{idx}].{k} must be numeric; got {type(v).__name__}"
            )
    for score_key in (
        "hypothesis_specificity_score", "single_axis_isolation_score",
        "risk_avoidance_score",
    ):
        v = e[score_key]
        if not isinstance(v, (int, float)):
            raise GrowthExperimentRunnerError(
                f"experiment[{idx}].{score_key} must be numeric; got {type(v).__name__}"
            )
        if v < 0 or v > 100:
            raise GrowthExperimentRunnerError(
                f"experiment[{idx}].{score_key}={v} outside 0-100"
            )
    # sample_power_score is optional; if missing or out-of-range, we'll
    # compute it from the heuristic below.
    sp = e.get("sample_power_score")
    if sp is None or not isinstance(sp, (int, float)) or sp < 0 or sp > 100:
        e["sample_power_score"] = round(
            _heuristic_sample_power_score(audience, int(e["planned_runtime_days"]), float(e["expected_effect_pct"])),
            1,
        )
    _refuse_if_forbidden(f"experiment[{idx}].hypothesis", str(e["hypothesis"]))
    _refuse_if_forbidden(f"experiment[{idx}].axis_label", str(e["axis_label"]))
    _refuse_if_forbidden(f"experiment[{idx}].success_criteria", str(e["success_criteria"]))
    return e


def _validate_input(payload: dict, args: argparse.Namespace) -> ExperimentInput:
    handle = _normalise_handle(payload.get("x_handle", args.x_handle or ""))
    audience = int(payload.get("audience_size", args.audience_size))
    if audience < 100:
        raise GrowthExperimentRunnerError(
            f"audience_size={audience} too small — must be >= 100"
        )
    window = _validate_window(int(payload.get("window", args.window)))
    data_source = payload.get("data_source", "real")
    if data_source not in ("real", "demo"):
        raise GrowthExperimentRunnerError(
            f"data_source={data_source!r} invalid — choose 'real' or 'demo'"
        )

    experiments_raw = payload.get("candidate_experiments") or []
    if len(experiments_raw) < EXPERIMENT_COUNT_MIN:
        raise GrowthExperimentRunnerError(
            f"candidate_experiments count {len(experiments_raw)} below floor {EXPERIMENT_COUNT_MIN}"
        )
    experiments = [_validate_experiment(e, i, audience) for i, e in enumerate(experiments_raw)]

    return ExperimentInput(
        x_handle=handle,
        audience_size=audience,
        window=window,
        data_source=data_source,
        max_experiments=_clamp_max_experiments(args.max_experiments),
        risk_floor=DEFAULT_RISK_FLOOR,
        power_floor=float(args.power_floor),
        candidate_experiments=experiments,
        previous_window_summary=payload.get("previous_window_summary") or {},
        baseline_metric_name=str(payload.get("baseline_metric_name", "engagement_rate")),
        baseline_metric_value=float(payload.get("baseline_metric_value", 2.5)),
        hypothesis_file=str(args.hypothesis_file) if args.hypothesis_file else None,
    )


# ---------------------------------------------------------------------------
# Multi-variable + risk-exclude guards + scoring
# ---------------------------------------------------------------------------


@dataclass
class ExperimentCard:
    raw: dict
    excluded: bool
    excluded_reason: Optional[str]
    detection_band: str  # "within-power" | "borderline" | "underpowered"


@dataclass
class PlanScore:
    metric_values: dict
    metric_arrows: dict
    plan_score: int
    paradox_active: bool
    avg_hypothesis_specificity: float
    avg_single_axis_isolation: float
    avg_sample_power: float
    avg_risk_avoidance: float


def _detection_band_for(score: float) -> str:
    if score >= 75:
        return "within-power"
    if score >= 40:
        return "borderline"
    return "underpowered"


def _annotate_experiments(experiments: list[dict], risk_floor: float) -> tuple[list[ExperimentCard], int, int]:
    """Returns (annotated, multi_variable_excluded, risk_excluded)."""
    annotated: list[ExperimentCard] = []
    mv_excluded = 0
    risk_excluded = 0
    for e in experiments:
        if e["axis_count"] > 1:
            annotated.append(
                ExperimentCard(
                    raw=e,
                    excluded=True,
                    excluded_reason=f"axis_count {e['axis_count']} > 1 (multi-variable)",
                    detection_band="underpowered",
                )
            )
            mv_excluded += 1
            continue
        if e["risk_avoidance_score"] < risk_floor:
            annotated.append(
                ExperimentCard(
                    raw=e,
                    excluded=True,
                    excluded_reason=(
                        f"risk_score {e['risk_avoidance_score']:.0f} < risk_floor {int(risk_floor)}"
                    ),
                    detection_band="underpowered",
                )
            )
            risk_excluded += 1
            continue
        band = _detection_band_for(e["sample_power_score"])
        annotated.append(
            ExperimentCard(raw=e, excluded=False, excluded_reason=None, detection_band=band)
        )
    return annotated, mv_excluded, risk_excluded


def _select_experiments(annotated: list[ExperimentCard], target: int) -> list[ExperimentCard]:
    eligible = [a for a in annotated if not a.excluded]
    eligible.sort(
        key=lambda a: (
            -a.raw["hypothesis_specificity_score"],
            -a.raw["sample_power_score"],
            -a.raw["risk_avoidance_score"],
        )
    )
    n = min(EXPERIMENT_COUNT_MAX, max(EXPERIMENT_COUNT_MIN, target), len(eligible))
    return eligible[:n]


def _avg(items: list[float]) -> float:
    if not items:
        return 0.0
    return sum(items) / len(items)


def _compute_plan_score(annotated: list[ExperimentCard]) -> PlanScore:
    pool = annotated  # full candidate pool
    hs = _avg([a.raw["hypothesis_specificity_score"] for a in pool])
    sa = _avg([a.raw["single_axis_isolation_score"] for a in pool])
    sp = _avg([a.raw["sample_power_score"] for a in pool])
    ra = _avg([a.raw["risk_avoidance_score"] for a in pool])

    metric_values = {
        "Hypothesis specificity": round(hs, 1),
        "Single-axis isolation": round(sa, 1),
        "Sample power": round(sp, 1),
        "Risk avoidance": round(ra, 1),
    }

    norms = {m: _normalise_metric(metric_values[m], m) for m in SCORE_METRICS}
    plan = round(
        PLAN_SCORE_WEIGHTS["Hypothesis specificity"] * norms["Hypothesis specificity"]
        + PLAN_SCORE_WEIGHTS["Single-axis isolation"] * norms["Single-axis isolation"]
        + PLAN_SCORE_WEIGHTS["Sample power"] * norms["Sample power"]
        + PLAN_SCORE_WEIGHTS["Risk avoidance"] * norms["Risk avoidance"]
    )

    paradox = (
        sp < PARADOX_SAMPLE_POWER_THRESHOLD
        and hs > PARADOX_HYPOTHESIS_SPECIFICITY_THRESHOLD
    )

    return PlanScore(
        metric_values=metric_values,
        metric_arrows={},
        plan_score=plan,
        paradox_active=paradox,
        avg_hypothesis_specificity=hs,
        avg_single_axis_isolation=sa,
        avg_sample_power=sp,
        avg_risk_avoidance=ra,
    )


def _arrows_against_basis(score: PlanScore, prev: dict) -> dict:
    return {
        "Hypothesis specificity": _arrow_for_delta(
            score.metric_values["Hypothesis specificity"],
            float(prev.get("avg_hypothesis_specificity", score.metric_values["Hypothesis specificity"])),
        ),
        "Single-axis isolation": _arrow_for_delta(
            score.metric_values["Single-axis isolation"],
            float(prev.get("avg_single_axis_isolation", score.metric_values["Single-axis isolation"])),
        ),
        "Sample power": _arrow_for_delta(
            score.metric_values["Sample power"],
            float(prev.get("avg_sample_power", score.metric_values["Sample power"])),
        ),
        "Risk avoidance": _arrow_for_delta(
            score.metric_values["Risk avoidance"],
            float(prev.get("avg_risk_avoidance", score.metric_values["Risk avoidance"])),
        ),
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _demo_suffix(data_source: str) -> str:
    return f" {DEMO_LABEL}" if data_source == "demo" else ""


def _interpretation_for(metric: str, value: float, score: PlanScore, mv_excluded: int, risk_excluded: int) -> str:
    if metric == "Hypothesis specificity":
        if value > 90:
            return "Hypotheses are precise — clear cause-effect, named axes, testable thresholds."
        if value > 60:
            return "Hypotheses are tight — clear cause/effect on a single axis."
        return "Hypothesis specificity below the floor — sharpen the claim before designing the test."
    if metric == "Single-axis isolation":
        if mv_excluded > 0:
            return f"Strong single-axis isolation; {mv_excluded} multi-variable experiment(s) excluded."
        if value > 95:
            return "Single-axis isolation near-perfect — every test varies one factor."
        if value > 70:
            return "Single-axis isolation in the healthy band."
        return "Single-axis isolation below the floor — multi-variable tests pollute the read."
    if metric == "Sample power":
        if score.paradox_active:
            return "Below the 40 floor — predicted effects are too small for the audience to detect."
        if value > 90:
            return "Sample power high — every experiment can detect its predicted effect at 80% power."
        if value > 50:
            return "Sample power inside the healthy band."
        return "Sample power borderline — verify each experiment's runtime against detection floor."
    if metric == "Risk avoidance":
        if risk_excluded > 0:
            return f"Risk avoidance acceptable; {risk_excluded} high-risk experiment(s) excluded."
        if value > 95:
            return "Risk avoidance excellent — every experiment passes the audience-distress + policy + burnout floor."
        if value > 70:
            return "Risk avoidance in the healthy band."
        return "Risk avoidance below the floor — re-design experiments before running."
    return ""


def _render_snapshot(inp: ExperimentInput, score: PlanScore) -> str:
    headline_bits = [f"{inp.audience_size}-audience experiment cycle"]
    if score.paradox_active:
        headline_bits.append(
            f"small-n paradox active; specificity {score.avg_hypothesis_specificity:.1f} but sample power only {score.avg_sample_power:.1f}"
        )
    else:
        headline_bits.append(
            f"plan score {score.plan_score}/100; specificity holding at {score.avg_hypothesis_specificity:.1f}"
        )
    headline = f"**{inp.x_handle}: " + " — ".join(headline_bits) + ".**"

    if inp.data_source == "demo":
        ds = "seeded demo experiments — re-run with --hypothesis-file for real audience data"
    else:
        ds = f"real X export from --hypothesis-file {inp.hypothesis_file}"

    body = [
        "## Experiment Snapshot",
        headline,
        "",
        f"- **Creator handle**: {inp.x_handle}",
        f"- **Audience size**: {inp.audience_size}",
        f"- **Window**: {inp.window}d",
        f"- **Data source**: {ds}",
    ]
    return "\n".join(body)


def _render_plan_score(inp: ExperimentInput, score: PlanScore, arrows: dict, mv_excl: int, risk_excl: int) -> str:
    lines = [
        "## Experiment Plan Score",
        "",
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
    ]
    suffix = _demo_suffix(inp.data_source)
    for metric in SCORE_METRICS:
        v = score.metric_values[metric]
        arrow = arrows[metric]
        interp = _interpretation_for(metric, v, score, mv_excl, risk_excl)
        lines.append(f"| {metric} | {v}/100{suffix} | {arrow} | {interp} |")
    if score.paradox_active:
        lines.append("")
        lines.append(
            "> ⚠️ paradox: experiments are well-specified but cannot statistically detect their "
            "predicted effect — running them would burn cycles for inconclusive reads."
        )
    lines.append("")
    lines.append(f"**Experiment Plan Score**: {score.plan_score}/100")
    return "\n".join(lines)


def _render_sample_profile(inp: ExperimentInput, selected: list[ExperimentCard]) -> str:
    if selected:
        avg_runtime = _avg([a.raw["planned_runtime_days"] for a in selected])
    else:
        avg_runtime = inp.window
    floor = _detection_floor(inp.audience_size, int(round(avg_runtime)))
    return "\n".join([
        "## Sample-Power Profile",
        "",
        f"- **Audience size**: {inp.audience_size}",
        "- **Reach assumption**: ~10% over 30d, scaled by runtime",
        f"- **Detection floor at {int(round(avg_runtime))}d runtime**: ≈ {floor:.2f}% effect at 80% power",
        f"- **Baseline metric**: {inp.baseline_metric_name} = {inp.baseline_metric_value}",
    ])


def _render_experiment_cards(inp: ExperimentInput, selected: list[ExperimentCard], total: int, mv_excl: int, risk_excl: int) -> str:
    notes = []
    if mv_excl > 0:
        notes.append(f"{mv_excl} multi-variable excluded")
    if risk_excl > 0:
        notes.append(f"{risk_excl} high-risk excluded")
    note = (" — " + ", ".join(notes)) if notes else ""
    header = f"## Experiment Cards ({len(selected)} of {total} candidate experiments{note})"
    lines = [header, ""]
    for n, sc in enumerate(selected, start=1):
        e = sc.raw
        lines.append(f"{n}. **{e['hypothesis']}**")
        lines.append(
            f"   axis: `{e['axis_label']}` · expected effect: {e['expected_effect_pct']}% · "
            f"runtime: {e['planned_runtime_days']}d · primary metric: `{e['primary_metric']}`"
        )
        lines.append(f"   success criteria: {e['success_criteria']}")
        lines.append(
            f"   hypothesis specificity: {e['hypothesis_specificity_score']:.0f}/100 · "
            f"single-axis: {e['single_axis_isolation_score']:.0f}/100 · "
            f"sample power: {e['sample_power_score']:.0f}/100 · "
            f"risk: {e['risk_avoidance_score']:.0f}/100 · "
            f"detection: {sc.detection_band}"
        )
    return "\n".join(lines)


def _render_red_flags(
    score: PlanScore,
    inp: ExperimentInput,
    annotated: list[ExperimentCard],
    selected: list[ExperimentCard],
    mv_excl: int,
    risk_excl: int,
) -> str:
    flags: list[tuple[str, str, str, str]] = []

    if score.paradox_active:
        flags.append((
            "Small-n paradox",
            "high",
            (
                f"Average hypothesis specificity {score.avg_hypothesis_specificity:.1f} > 70 while "
                f"average sample power {score.avg_sample_power:.1f} < 40 — experiments are well-specified "
                "but cannot statistically detect their predicted effect."
            ),
            (
                "Reduce predicted effect-size claims until the available audience can detect them, "
                "OR lengthen runtime to accumulate sample, OR skip this experiment cycle and "
                "use the planning time for `content-idea-generator`."
            ),
        ))

    if mv_excl > 0:
        mv_experiments = [a for a in annotated if a.excluded and "multi-variable" in (a.excluded_reason or "")]
        axes = "; ".join(
            f"experiment {i+1}: '{a.raw['axis_label']}'" for i, a in enumerate(mv_experiments[:3])
        )
        flags.append((
            "Multi-variable experiments excluded",
            "high",
            (
                f"{mv_excl} experiment(s) excluded for axis_count > 1 ({axes}). They do not occupy "
                f"any of the {EXPERIMENT_COUNT_MIN}-{EXPERIMENT_COUNT_MAX} experiment slots."
            ),
            (
                "Split each multi-variable experiment into N single-axis experiments using "
                "`ab-test-suggester`, which enforces the same single-axis contract."
            ),
        ))

    if risk_excl > 0:
        risk_experiments = [
            a for a in annotated
            if a.excluded and "risk_floor" in (a.excluded_reason or "")
        ]
        risk_summary = "; ".join(
            f"experiment {i+1}: risk {a.raw['risk_avoidance_score']:.0f}"
            for i, a in enumerate(risk_experiments[:3])
        )
        flags.append((
            "High-risk experiments excluded",
            "high",
            (
                f"{risk_excl} experiment(s) excluded for risk_score below floor ({risk_summary}). "
                "Risk includes audience-distress patterns, policy-violation, creator-burnout cadences, "
                "and unsafe experiment designs."
            ),
            (
                "Re-design the excluded experiments — lower the risk profile, shorten runtime, or "
                "drop them from the cycle entirely."
            ),
        ))

    # Pool below floor
    if len(selected) < EXPERIMENT_COUNT_MIN:
        flags.append((
            "Experiment pool below floor",
            "high",
            (
                f"Only {len(selected)} experiment(s) selected after both guards — eligible pool was "
                f"insufficient for the {EXPERIMENT_COUNT_MIN} floor."
            ),
            "Add more candidate experiments to the input file, or relax the risk_floor.",
        ))

    if not flags:
        flags.append((
            "No structural red flags",
            "low",
            "Plan stays within healthy bands; review remains creator-side qualitative judgement.",
            "Proceed; verify the success criteria with the creator before kicking off the cycle.",
        ))

    lines = ["## Red Flags", ""]
    for title, sev, body, rem in flags:
        lines.append(f"- **{title}** · severity: {sev} — {body}. *Remediation:* {rem}")
    return "\n".join(lines)


def _render_recommendations(
    inp: ExperimentInput,
    selected: list[ExperimentCard],
    score: PlanScore,
    mv_excl: int,
    risk_excl: int,
) -> str:
    lines = ["## Recommendations", ""]

    # Position 1 — analytics-summarizer (mandatory)
    if score.paradox_active:
        lines.append(
            "1. Pull the period analytics first to confirm the baseline metric value before "
            "running underpowered experiments — analytics-summarizer is the source of truth. "
            "— bridges to: `analytics-summarizer`"
        )
    else:
        lines.append(
            "1. After each experiment ends, pull period analytics to compute the metric delta "
            "vs the success criteria. — bridges to: `analytics-summarizer`"
        )

    # Position 2 — ab-test-suggester (mandatory)
    if mv_excl > 0:
        lines.append(
            f"2. Split the {mv_excl} multi-variable experiment(s) into N single-axis experiments "
            "via ab-test-suggester, which enforces the same single-axis contract. — bridges to: `ab-test-suggester`"
        )
    else:
        thread_axes = sum(
            1 for a in selected
            if "format" in a.raw["axis_label"].lower() or "thread" in a.raw["axis_label"].lower()
        )
        if thread_axes:
            lines.append(
                "2. Hand format/thread-axis experiments to ab-test-suggester for variant generation "
                "under the same single-axis contract. — bridges to: `ab-test-suggester`"
            )
        else:
            lines.append(
                "2. For each content-shaped hypothesis, generate the variant pair via ab-test-suggester "
                "before scheduling the test. — bridges to: `ab-test-suggester`"
            )

    # Position 3 — context-aware
    if score.paradox_active:
        lines.append(
            "3. Use the planning time freed by skipping underpowered experiments to source a "
            "fresh idea batch. — bridges to: `content-idea-generator`"
        )
    elif risk_excl > 0:
        lines.append(
            "3. Sanity-check the surviving experiments against follower quality before launch — "
            "high-risk experiments often correlate with low-quality follower spikes. — bridges to: `follower-quality-analyzer`"
        )
    else:
        # Look for voice-axis experiments
        voice_axis = any("voice" in a.raw["axis_label"].lower() or "tone" in a.raw["axis_label"].lower() for a in selected)
        if voice_axis:
            lines.append(
                "3. Voice/tone-axis experiments must clear the trainer first — re-anchor before "
                "launching. — bridges to: `brand-voice-trainer`"
            )
        else:
            lines.append(
                "3. Confirm each hypothesis's niche relevance against competitor patterns before "
                "running. — bridges to: `competitor-watch`"
            )

    # Position 4 — context-aware
    metrics_in_use = {a.raw["primary_metric"] for a in selected}
    if "monetization_channel_revenue" in metrics_in_use:
        lines.append(
            "4. Monetization-channel experiments inherit V.1 + V.2 disclaimers — route to "
            "monetization-optimizer for plan integration. — bridges to: `monetization-optimizer`"
        )
    elif "mention_quality_score" in metrics_in_use:
        lines.append(
            "4. Mention-quality experiments source their primary metric from mention-summarizer — "
            "verify the upstream signal is fresh. — bridges to: `mention-summarizer`"
        )
    elif "thread_completion_rate" in metrics_in_use:
        lines.append(
            "4. Thread-completion experiments hand the thread variant to thread-builder for "
            "structured drafting. — bridges to: `thread-builder`"
        )
    else:
        lines.append(
            "4. Sanity-check follower quality before treating follower-delta experiments as "
            "credible signals. — bridges to: `follower-quality-analyzer`"
        )

    # Position 5 — measurement loop
    lines.append(
        "5. After each cycle, fold the winning hypotheses into the next idea batch's archetype "
        "anchors so the gain compounds. — bridges to: `content-idea-generator`"
    )

    return "\n".join(lines)


def _render_confidence(
    inp: ExperimentInput,
    score: PlanScore,
    selected: list[ExperimentCard],
    mv_excl: int,
    risk_excl: int,
) -> str:
    if inp.data_source == "demo":
        level = "low"
        reason = (
            "demo data only — re-run with --hypothesis-file pointing at real audience signals. "
            "Plan Score is illustrative."
        )
    elif score.paradox_active:
        level = "low"
        reason = (
            "real signals, but small-n paradox active — running these experiments would produce "
            "inconclusive reads. Reduce effect-size claims or lengthen runtime."
        )
    elif mv_excl > 0:
        level = "medium"
        reason = (
            f"real signals; {mv_excl} multi-variable experiment(s) excluded — split them via "
            "ab-test-suggester before re-batching."
        )
    elif risk_excl > 0:
        level = "medium"
        reason = (
            f"real signals; {risk_excl} high-risk experiment(s) excluded — re-design or drop them."
        )
    elif inp.window == 7:
        level = "medium"
        reason = "7d window over-indexes on single-day variance — re-run with 30d to confirm."
    else:
        level = "high"
        reason = "real signals, all metrics inside healthy bands, no exclusions."
    return f"## Confidence\nConfidence: {level} — {reason}"


def _render_audit(
    inp: ExperimentInput,
    score: PlanScore,
    annotated: list[ExperimentCard],
    mv_excl: int,
    risk_excl: int,
) -> Optional[str]:
    triggers = []
    if inp.window == 7:
        triggers.append("window=7d — single-day variance dominates short-runtime tests")
    if score.paradox_active:
        triggers.append("small-n paradox active")
    if mv_excl > 0:
        triggers.append("multi-variable guard fired")

    if not triggers:
        return None

    underpowered = sum(
        1 for a in annotated
        if not a.excluded and a.detection_band == "underpowered"
    )

    lines = [
        "## Experiment Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {inp.window}d window is "
        + ("under-powered for the audience size" if inp.window == 7 else "adequate"),
        f"- **Data source confidence**: "
        + ("demo data — re-run with real export" if inp.data_source == "demo"
           else "real signals — proceed"),
        f"- **Sample-power impact**: {underpowered} of {len(annotated)} eligible experiments below the power floor",
        f"- **Multi-variable impact**: {mv_excl} excluded",
        f"- **Risk-exclude impact**: {risk_excl} excluded",
        "- **Suggested next sample**: lengthen runtime to 45d to lift sample power on the borderline experiments",
        "- **Re-run cadence**: re-plan after each completed experiment cycle",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_growth_experiment_plan(
    *,
    x_handle: str,
    hypothesis_file: Optional[str] = None,
    audience_size: int = DEFAULT_AUDIENCE_SIZE,
    window: int = 30,
    max_experiments: int = DEFAULT_MAX_EXPERIMENTS,
    power_floor: float = DEFAULT_POWER_FLOOR,
    payload: Optional[dict] = None,
    args: Optional[argparse.Namespace] = None,
) -> str:
    if args is None:
        args = argparse.Namespace(
            x_handle=x_handle,
            hypothesis_file=hypothesis_file,
            audience_size=audience_size,
            window=window,
            max_experiments=max_experiments,
            power_floor=power_floor,
        )
    inp = _validate_input(payload or {}, args)

    seed = _seed_from(
        inp.x_handle,
        str(inp.audience_size),
        str(inp.window),
        _utcnow_date(),
    )
    Random(seed)

    annotated, mv_excl, risk_excl = _annotate_experiments(inp.candidate_experiments, inp.risk_floor)
    selected = _select_experiments(annotated, inp.max_experiments)
    score = _compute_plan_score(annotated)
    arrows = _arrows_against_basis(score, inp.previous_window_summary)
    score.metric_arrows = arrows

    parts: list[str] = []
    parts.append(_render_snapshot(inp, score))
    parts.append(_render_plan_score(inp, score, arrows, mv_excl, risk_excl))
    parts.append(_render_sample_profile(inp, selected))
    parts.append(_render_experiment_cards(inp, selected, len(inp.candidate_experiments), mv_excl, risk_excl))
    parts.append(_render_red_flags(score, inp, annotated, selected, mv_excl, risk_excl))
    parts.append(_render_recommendations(inp, selected, score, mv_excl, risk_excl))
    parts.append(_render_confidence(inp, score, selected, mv_excl, risk_excl))
    audit = _render_audit(inp, score, annotated, mv_excl, risk_excl)
    if audit is not None:
        parts.append(audit)

    return "\n\n".join(parts) + "\n"


generate = generate_growth_experiment_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_FILE_HEADER = (
    "<!-- Copyright 2026 AgentMindCloud -->\n"
    "<!-- Licensed under the Apache License, Version 2.0 -->\n"
    "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
    "<!-- Generated by growth-experiment-runner/run.py — built for X, Grok & the ecosystem community. -->\n"
    "\n"
)


def _maybe_load_payload(args: argparse.Namespace) -> Optional[dict]:
    if args.demo:
        return _load_demo("paradox")
    if args.demo_healthy:
        return _load_demo("healthy")
    if args.demo_7d_audit:
        return _load_demo("7d-audit")
    if args.hypothesis_file:
        p = Path(args.hypothesis_file)
        if not p.exists():
            raise GrowthExperimentRunnerError(f"hypothesis_file {p} does not exist")
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="growth-experiment-runner",
        description=(
            "Local-first growth experiment runner for X creators. Drafts only — never auto-runs. "
            "Built for X, Grok & the ecosystem community."
        ),
    )
    parser.add_argument("--x-handle", required=True, help="Creator's X handle.")
    parser.add_argument("--hypothesis-file", default=None, help="Path to hypothesis JSON.")
    parser.add_argument(
        "--audience-size",
        type=int,
        default=DEFAULT_AUDIENCE_SIZE,
        help="Reachable audience size (default 12000).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=30,
        help="Experiment window in days (7 / 30 / 90).",
    )
    parser.add_argument(
        "--max-experiments",
        type=int,
        default=DEFAULT_MAX_EXPERIMENTS,
        help="Target experiment count, clamped to [3, 6].",
    )
    parser.add_argument(
        "--power-floor",
        type=float,
        default=DEFAULT_POWER_FLOOR,
        help="Sample-power floor (default 40).",
    )
    parser.add_argument("--demo", action="store_true", help="Run small-n paradox demo seed.")
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
        rendered = generate_growth_experiment_plan(
            x_handle=args.x_handle,
            hypothesis_file=args.hypothesis_file,
            audience_size=args.audience_size,
            window=args.window,
            max_experiments=args.max_experiments,
            power_floor=args.power_floor,
            payload=payload,
            args=args,
        )
    except GrowthExperimentRunnerError as exc:
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
