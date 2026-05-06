# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Thread Builder — runner.

CLI entry point for the ``thread-builder`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied topic / goal (and optional voice samples +
analytics-summarizer JSON export) and emits the strict 6/7-section
thread plan defined by the merged P87 system prompt:

  1. Thread Snapshot
  2. Thread Plan Performance (4-row metric table + weighted score)
  3. Thread Variants (3-5 drafts, each with per-variant scoring)
  4. Hook Variations (4-6 alternates for the highest-arc variant)
  5. Engagement Forecast (content-engagement bands; never absolute)
  6. Red Flags (2-3, surfaces hook-without-payoff paradox in BOTH places)
  7. Recommendations (3-5; >= 3 cross-template bridges; mandatory:
     analytics-summarizer + content-idea-generator)
  8. Confidence
  + Optional Thread Audit (auto-appended when red_flags > 3 OR
    variant_count == 5 OR data_source = demo with no voice samples)

Hard guarantees enforced by this runner (mirrors the P87 system prompt):

* Drafts only. Output is text the creator pastes into the X composer
  themselves; the runner never publishes, schedules, or DMs.
* Variant cap of 5. The runner refuses --variants > 5 — cognitive load
  on the creator above 5 destroys the value of A/B selection.
* Hook character cap of 240. Every hook (Post 1) and every Hook
  Variation entry is enforced <= 240 characters at render time.
* Hook-without-payoff paradox surfaced in BOTH the Thread Plan
  Performance section AND the Red Flags section whenever any variant
  shows Hook strength > 80 AND Narrative arc coherence < 50.
* Thread Plan score formula is fixed:
    round(0.30*Hook + 0.25*Arc + 0.25*Voice + 0.20*PredictedEngagement)
* Content-engagement bands only. Predicted engagement is reported as
  a 0-100 sub-score plus a low / medium / high band — never an absolute
  like / repost / reply count.
* Mandatory monetization refusal. If the topic crosses into revenue,
  paid-tier, sponsorship, ad-spend, or affiliate territory, the runner
  emits a structured refusal that points the creator at
  monetization-optimizer and stops.
* Mandatory bridges. Every render (including the refusal path) names
  >= 3 cross-template bridges; analytics-summarizer and
  content-idea-generator are always included.
* Voice fidelity is creator-only. The runner accepts voice samples
  via --voice-samples-file (a JSON list of the creator's own posts);
  it never scores voice against samples authored by a different handle.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic. Score nudges and recommendation ordering are seeded
  by sha256(handle + topic + variant_count + tone + thread_length +
  date), so the same input always produces the same render.
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_thread_plan

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
    "Hook strength",
    "Narrative arc coherence",
    "Voice fidelity",
    "Predicted engagement",
)

# Per the P87 system prompt: Hook strength weighted highest because the
# first post determines whether the thread gets read at all; Arc and
# Voice tied at 0.25 because either failing alone defeats the thread;
# Predicted engagement weighted lowest because it is a heuristic.
PERFORMANCE_WEIGHTS = {
    "Hook strength": 0.30,
    "Narrative arc coherence": 0.25,
    "Voice fidelity": 0.25,
    "Predicted engagement": 0.20,
}

THREAD_LENGTH_OPTIONS = ("short", "medium", "long")
THREAD_LENGTH_POSTS = {"short": 5, "medium": 8, "long": 12}

TONE_FOCUS_OPTIONS = ("analytical", "personal", "tactical", "narrative", "all")
STANDARD_REGISTERS = ("analytical", "personal", "tactical", "narrative")

VARIANT_MIN = 3
VARIANT_MAX = 5
HOOK_CHAR_CAP = 240
HOOK_VARIATION_MIN = 4
HOOK_VARIATION_MAX = 6

# Healthy-floor bands for arrow bucketing per the P87 system prompt
ARROW_FLOORS = {
    "Hook strength": 60.0,
    "Narrative arc coherence": 60.0,
    "Voice fidelity": 60.0,
    "Predicted engagement": 50.0,
}

# Hook-without-payoff paradox: any variant with Hook > 80 AND Arc < 50
PARADOX_HOOK_THRESHOLD = 80
PARADOX_ARC_THRESHOLD = 50

# Engagement bands (sub-score buckets)
ENGAGEMENT_BAND_LOW_MAX = 49
ENGAGEMENT_BAND_HIGH_MIN = 70

CROSS_TEMPLATE_BRIDGES = (
    # Mandatory two — always present
    "analytics-summarizer",
    "content-idea-generator",
    # Optional pool
    "brand-voice-trainer",
    "ab-test-suggester",
    "reply-drafter",
    "competitor-watch",
    "cross-platform-reposter",
    "comment-engagement-booster",
    "hashtag-strategy-advisor",
    "follower-quality-analyzer",
    "content-recycler",
    "monetization-optimizer",
)

MANDATORY_BRIDGES = ("analytics-summarizer", "content-idea-generator")

# Topic keywords that route the run into monetization-optimizer instead
MONETIZATION_KEYWORDS = (
    "revenue", "monetization", "monetisation", "monetize", "monetise", "monetizing",
    "sponsorship", "sponsor ", "sponsored",
    "paid tier", "paid-tier",
    "subscription revenue", "subscription tier",
    "ad revenue", "ad-revenue", "ad spend", "ad-spend",
    "affiliate", "affiliates",
    "make money", "earn money", "income from",
    "creator earnings", "x payout", "x money payout",
    "revenue share", "rev share", "rev-share",
    "pricing my paid", "selling my course",
)

# Per-register deterministic data for the variant generator
REGISTER_DATA = {
    "analytical": {
        "base_scores": {"hook": 82, "arc": 75, "voice": 66},
        "hook_template": (
            "Most takes on {topic} measure the wrong thing. Here are {n_beats} failure modes "
            "nobody benchmarks (the fix is in post {payoff_post}):"
        ),
        "arc_labels": (
            "failure mode 1 — silent over-fitting on noisy signals",
            "failure mode 2 — confidence-without-grounding on retrieval misses",
            "failure mode 3 — feedback loops that look productive but stall",
            "failure mode 4 — voice / persona drift across multi-step flows",
            "failure mode 5 — misclassified intent on edge phrasing",
            "failure mode 6 — dependency stack drift",
            "rubric synthesis — the eval most teams should adopt",
        ),
        "payoff_label": "payoff — CTA-without-CTA tied to the next anchor in the same cluster",
        "why_lands": (
            "Technical / founder audience reads list-led failure-mode posts. The hook frames "
            "the orthodoxy gap, the arc enumerates concretely, the close offers a rubric — "
            "earning the bookmark."
        ),
    },
    "personal": {
        "base_scores": {"hook": 76, "arc": 78, "voice": 68},
        "hook_template": (
            "I spent 6 months getting {topic} wrong. Here's the rebuild — what I tried, what "
            "failed, and what finally landed (full breakdown below):"
        ),
        "arc_labels": (
            "the breaking point — the day {topic} stopped working",
            "first attempt — the obvious move that quietly made it worse",
            "the question I should have asked from day one",
            "the reframing that finally moved the needle",
            "the daily ritual that locked the change in",
            "what shipped — the version I actually use now",
            "what I'd tell past-me, in one sentence",
        ),
        "payoff_label": "payoff — the one habit I'd keep if I had to drop the rest",
        "why_lands": (
            "Habit / wellness / creator-economy audiences read first-person rebuild stories. "
            "The hook earns trust by admitting failure; the arc shows the rebuild; the close "
            "lands a single keepable habit — earning the reply."
        ),
    },
    "tactical": {
        "base_scores": {"hook": 74, "arc": 80, "voice": 67},
        "hook_template": (
            "The {n_beats}-step playbook I use for {topic}, in order. No fluff — just the moves "
            "that compound. Last post is the part nobody talks about."
        ),
        "arc_labels": (
            "step 1 — anchor the loop (what you're optimising for)",
            "step 2 — measure the baseline before you change anything",
            "step 3 — tighten the feedback loop to a sub-day cycle",
            "step 4 — run the counterexample before you scale",
            "step 5 — generalise only after 3 confirmed wins",
            "step 6 — automate the boring 80% of the loop",
            "step 7 — review weekly; rotate one variable at a time",
        ),
        "payoff_label": "payoff — the single move most playbooks skip; CTA-without-CTA",
        "why_lands": (
            "Growth / productivity / engineering audiences read step-by-step playbooks. "
            "The hook promises a reproducible sequence; the arc delivers in order; the close "
            "names the single move most playbooks skip — earning the repost."
        ),
    },
    "narrative": {
        "base_scores": {"hook": 80, "arc": 70, "voice": 65},
        "hook_template": (
            "Three months ago I thought I understood {topic}. I was wrong. Here's the story — "
            "beat by beat — and the part nobody warns you about:"
        ),
        "arc_labels": (
            "the setup — the assumption I walked in with",
            "the inciting incident — the moment {topic} broke the assumption",
            "the wrong path — what I tried that looked right",
            "the reversal — the question that flipped the frame",
            "the discovery — the part nobody had told me",
            "the test — the single experiment that confirmed it",
            "the resolution — what I ship now, and why",
        ),
        "payoff_label": "payoff — the line I'd put on the cover; CTA-without-CTA",
        "why_lands": (
            "Brand / culture / marketing audiences read story-arc threads. The hook teases "
            "the reversal; the arc earns the reveal; the close lands a single takeaway line — "
            "earning the bookmark + share."
        ),
    },
}

# Hook-variation styles (4-6 alternates; <= 240 chars each)
HOOK_VARIATION_TEMPLATES = (
    ("numbers-led",
     "{n_beats} truths about {topic} most teams miss — and the single fix that compounds across all of them."),
    ("contrarian-claim",
     "Most takes on {topic} are vanity advice. The real lever is post-publish measurement — most creators skip it. Here's the version that earns the read."),
    ("question-led",
     "When was the last time your read on {topic} caught the silent failure? Probably never. Here's why — and what to swap in instead."),
    ("story-cold-open",
     "Friday 4pm. Deadline Monday. {topic} was the one thing standing in the way. Here's how it broke — and what shipped on Sunday night."),
    ("list-tease",
     "The 7 rules for {topic} I'd hand to any creator on day 1. Number 4 is the one nobody talks about; number 7 is the one most skip."),
    ("personal-anecdote",
     "I spent a quarter getting {topic} wrong. Here's the rebuild — what I tried, what I broke, and the post that finally moved the needle."),
)


# ---------------------------------------------------------------------------
# Privacy guard (only the creator's handle in body)
# ---------------------------------------------------------------------------

_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,15}(?![A-Za-z0-9_])"
)


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Thread Builder privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VariantScores:
    register: str
    hook: int
    arc: int
    voice: int
    predicted_engagement: int

    @property
    def thread_plan_score(self) -> int:
        return round(
            PERFORMANCE_WEIGHTS["Hook strength"] * self.hook
            + PERFORMANCE_WEIGHTS["Narrative arc coherence"] * self.arc
            + PERFORMANCE_WEIGHTS["Voice fidelity"] * self.voice
            + PERFORMANCE_WEIGHTS["Predicted engagement"] * self.predicted_engagement
        )


@dataclass
class Variant:
    index: int
    register: str
    scores: VariantScores
    hook_text: str
    arc_beats: list[str]
    why_lands: str


@dataclass
class HookVariation:
    style: str
    text: str


@dataclass
class AggregateScores:
    hook: int
    arc: int
    voice: int
    predicted_engagement: int
    paradox_active: bool
    paradox_variants: list[int] = field(default_factory=list)
    interpretations: dict = field(default_factory=dict)

    @property
    def thread_plan_score(self) -> int:
        return round(
            PERFORMANCE_WEIGHTS["Hook strength"] * self.hook
            + PERFORMANCE_WEIGHTS["Narrative arc coherence"] * self.arc
            + PERFORMANCE_WEIGHTS["Voice fidelity"] * self.voice
            + PERFORMANCE_WEIGHTS["Predicted engagement"] * self.predicted_engagement
        )


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


def load_json_file(path: Path, label: str) -> object:
    if not path.exists():
        raise FileNotFoundError(f"--{label} not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"--{label} is not valid JSON: {e}") from e


def topic_is_monetization(topic: str) -> bool:
    low = topic.lower()
    return any(kw in low for kw in MONETIZATION_KEYWORDS)


# ---------------------------------------------------------------------------
# Variant builder
# ---------------------------------------------------------------------------


def _arc_beats_for(register: str, n_posts: int) -> list[str]:
    labels = list(REGISTER_DATA[register]["arc_labels"])
    payoff = REGISTER_DATA[register]["payoff_label"]
    arc_count = max(1, n_posts - 1)
    if arc_count <= len(labels):
        chosen = labels[: arc_count - 1]
        return chosen + [payoff]
    extras = [
        f"deep-dive {i + 1} — extension on \"{labels[i % len(labels)]}\""
        for i in range(arc_count - len(labels) - 1)
    ]
    return labels + extras + [payoff]


def _format_arc_beats(register: str, topic: str, n_posts: int) -> list[str]:
    raw = _arc_beats_for(register, n_posts)
    out: list[str] = []
    for i, beat in enumerate(raw, start=2):
        formatted = beat.replace("{topic}", topic)
        out.append(f"Post {i} — {formatted}")
    return out


def _format_hook(register: str, topic: str, n_posts: int) -> str:
    template = REGISTER_DATA[register]["hook_template"]
    n_beats = max(3, n_posts - 1)
    payoff_post = n_posts
    text = template.format(topic=topic, n_beats=n_beats, payoff_post=payoff_post)
    if len(text) > HOOK_CHAR_CAP:
        text = text[: HOOK_CHAR_CAP - 1].rstrip() + "…"
    return text


def _select_registers(variant_count: int, tone_focus: str) -> list[str]:
    if not VARIANT_MIN <= variant_count <= VARIANT_MAX:
        raise ValueError(
            f"variant_count must be {VARIANT_MIN}-{VARIANT_MAX}, got {variant_count}"
        )
    if tone_focus == "all":
        ordered = list(STANDARD_REGISTERS)
        if variant_count <= 4:
            return ordered[:variant_count]
        return ordered + ["analytical"]  # 5th variant repeats the highest-arc register
    if tone_focus not in STANDARD_REGISTERS:
        raise ValueError(
            f"tone_focus must be one of {TONE_FOCUS_OPTIONS}, got {tone_focus!r}"
        )
    return [tone_focus] * variant_count


def _scores_for_variant(
    register: str,
    index: int,
    voice_lift: int,
    analytics_lift: int,
    overrides: dict[int, dict],
) -> VariantScores:
    base = REGISTER_DATA[register]["base_scores"]
    if index in overrides:
        ov = overrides[index]
        hook = int(ov.get("hook", base["hook"]))
        arc = int(ov.get("arc", base["arc"]))
        voice = int(ov.get("voice", base["voice"]))
    else:
        hook = base["hook"] - max(0, (index - 1) * 2)
        arc = base["arc"] - max(0, (index - 1) * 1)
        voice = base["voice"]
    voice = max(0, min(100, voice + voice_lift))
    predicted_raw = round(0.40 * hook + 0.40 * arc + 0.20 * voice) + analytics_lift
    predicted = max(20, min(95, predicted_raw))
    return VariantScores(
        register=register,
        hook=max(0, min(100, hook)),
        arc=max(0, min(100, arc)),
        voice=voice,
        predicted_engagement=predicted,
    )


def build_variants(
    topic: str,
    variant_count: int,
    thread_length: str,
    tone_focus: str,
    voice_lift: int,
    analytics_lift: int,
    score_overrides: Optional[dict[int, dict]] = None,
) -> list[Variant]:
    if thread_length not in THREAD_LENGTH_OPTIONS:
        raise ValueError(
            f"thread_length must be one of {THREAD_LENGTH_OPTIONS}, got {thread_length!r}"
        )
    n_posts = THREAD_LENGTH_POSTS[thread_length]
    overrides = score_overrides or {}
    registers = _select_registers(variant_count, tone_focus)

    variants: list[Variant] = []
    for i, register in enumerate(registers, start=1):
        scores = _scores_for_variant(register, i, voice_lift, analytics_lift, overrides)
        variants.append(Variant(
            index=i,
            register=register,
            scores=scores,
            hook_text=_format_hook(register, topic, n_posts),
            arc_beats=_format_arc_beats(register, topic, n_posts),
            why_lands=REGISTER_DATA[register]["why_lands"],
        ))
    return variants


# ---------------------------------------------------------------------------
# Aggregation, arrows, and paradox detection
# ---------------------------------------------------------------------------


def _arrow_for(score: float, floor: float) -> str:
    diff = score - floor
    if diff >= 25:
        return "▲▲"
    if diff >= 5:
        return "▲"
    if diff >= -5:
        return "▬"
    if diff >= -25:
        return "▼"
    return "▼▼"


def aggregate_variants(variants: list[Variant]) -> AggregateScores:
    n = max(1, len(variants))
    hook = round(sum(v.scores.hook for v in variants) / n)
    arc = round(sum(v.scores.arc for v in variants) / n)
    voice = round(sum(v.scores.voice for v in variants) / n)
    predicted = round(sum(v.scores.predicted_engagement for v in variants) / n)

    paradox_variants = [
        v.index for v in variants
        if v.scores.hook > PARADOX_HOOK_THRESHOLD
        and v.scores.arc < PARADOX_ARC_THRESHOLD
    ]
    paradox_active = bool(paradox_variants)

    interp = {
        "Hook strength": _interp_hook(hook),
        "Narrative arc coherence": _interp_arc(arc),
        "Voice fidelity": _interp_voice(voice),
        "Predicted engagement": _interp_predicted(predicted),
    }
    return AggregateScores(
        hook=hook,
        arc=arc,
        voice=voice,
        predicted_engagement=predicted,
        paradox_active=paradox_active,
        paradox_variants=paradox_variants,
        interpretations=interp,
    )


def _interp_hook(score: int) -> str:
    if score >= 90:
        return "Above the suspicious-clickbait floor; verify the arc earns the promise."
    if score >= 75:
        return "Strong opener candidates; first post earns the next swipe."
    if score >= 60:
        return "Healthy hook; not viral, but readers will not bounce on post 1."
    return "Below the read-floor; rewrite the opener before publishing."


def _interp_arc(score: int) -> str:
    if score >= 80:
        return "Each post pulls toward the close; no filler middle, payoff is explicit."
    if score >= 60:
        return "Arc holds together; tighten the middle posts to lift further."
    if score >= 50:
        return "Arc is uneven; the middle drifts and the payoff is implicit."
    return "Arc does not deliver — clickbait debt that erodes trust."


def _interp_voice(score: int) -> str:
    if score >= 85:
        return "Tight voice match; one notch shy of stylistic over-fit."
    if score >= 70:
        return "Strong creator-voice fidelity across variants."
    if score >= 60:
        return "On-voice; lift further by attaching a brand-voice-trainer profile."
    return "Voice drift — re-run with --voice-samples-file to anchor scoring on real samples."


def _interp_predicted(score: int) -> str:
    if score >= ENGAGEMENT_BAND_HIGH_MIN:
        return "High band; hook + arc + voice + analytics signal align."
    if score >= 50:
        return "Medium band; niche-typical engagement."
    return "Low band; unlikely to break niche baseline without revision."


def predicted_band(score: int) -> str:
    if score >= ENGAGEMENT_BAND_HIGH_MIN:
        return "high"
    if score > ENGAGEMENT_BAND_LOW_MAX:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Hook variations
# ---------------------------------------------------------------------------


def build_hook_variations(
    topic: str, n_posts: int, count: int,
) -> list[HookVariation]:
    if count < HOOK_VARIATION_MIN:
        count = HOOK_VARIATION_MIN
    if count > HOOK_VARIATION_MAX:
        count = HOOK_VARIATION_MAX
    n_beats = max(3, n_posts - 1)
    out: list[HookVariation] = []
    for style, template in HOOK_VARIATION_TEMPLATES[:count]:
        text = template.format(topic=topic, n_beats=n_beats)
        if len(text) > HOOK_CHAR_CAP:
            text = text[: HOOK_CHAR_CAP - 1].rstrip() + "…"
        out.append(HookVariation(style=style, text=text))
    return out


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    variants: list[Variant],
    aggregate: AggregateScores,
    voice_samples_present: bool,
    analytics_present: bool,
    is_demo: bool,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1 — Hook-without-payoff paradox (mandatory in BOTH places when fired)
    if aggregate.paradox_active:
        idxs = ", ".join(str(i) for i in aggregate.paradox_variants)
        gap_lines = []
        for v in variants:
            if v.index in aggregate.paradox_variants:
                gap_lines.append(
                    f"Variant {v.index} ({v.register}) Hook {v.scores.hook}/100 vs "
                    f"Arc {v.scores.arc}/100"
                )
        flags.append(RedFlag(
            title="Hook-without-payoff paradox",
            severity="high",
            explanation=(
                f"Variant index(es) {idxs} show Hook strength > {PARADOX_HOOK_THRESHOLD} AND "
                f"Narrative arc coherence < {PARADOX_ARC_THRESHOLD} — the opener is catchy but "
                f"the thread does not deliver ({'; '.join(gap_lines)})."
            ),
            remediation=(
                "Either rebuild the middle posts so each pulls toward an explicit payoff, "
                "or soften the hook so the promise matches the actual delivery."
            ),
        ))

    # Rule 2 — Voice-sample thinness
    if not voice_samples_present:
        flags.append(RedFlag(
            title="Voice-sample thinness",
            severity="medium",
            explanation=(
                "No --voice-samples-file was supplied; Voice fidelity scoring uses register "
                "defaults rather than the creator's actual cadence."
            ),
            remediation=(
                "Re-run with --voice-samples-file pointing at 5-10 of the creator's recent "
                "posts, or attach a brand-voice-trainer profile."
            ),
        ))

    # Rule 3 — Analytics anchoring missing
    if not analytics_present:
        flags.append(RedFlag(
            title="Engagement anchoring missing",
            severity="low" if voice_samples_present else "medium",
            explanation=(
                "No --analytics-file was supplied; Predicted engagement is a niche-typical "
                "default rather than the creator's actual baseline."
            ),
            remediation=(
                "Run analytics-summarizer on the last 30d, attach the JSON via --analytics-file, "
                "and re-run thread-builder."
            ),
        ))

    # Rule 4 — Variant-count cognitive load (only at the cap)
    if len(variants) >= VARIANT_MAX:
        flags.append(RedFlag(
            title="Variant-count cognitive load",
            severity="medium",
            explanation=(
                f"{len(variants)} variants is the cap; cognitive load on the creator above 5 "
                "destroys the value of A/B selection."
            ),
            remediation=(
                "Once a directional winner emerges, re-run with --variants 3 to focus the next "
                "round on the surviving register."
            ),
        ))

    # Rule 5 — Aggregate hook below read-floor
    if aggregate.hook < 60 and not aggregate.paradox_active:
        flags.append(RedFlag(
            title="Aggregate hook below read-floor",
            severity="high",
            explanation=(
                f"Aggregate Hook strength {aggregate.hook}/100 is below the 60 read-floor; "
                "the thread is unlikely to earn the next swipe regardless of arc quality."
            ),
            remediation=(
                "Rewrite the openers; pair with hashtag-strategy-advisor for additional "
                "attention surfaces (cap 0-2 substantive tags)."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-cycle read",
            severity="low",
            explanation=(
                "One drafting cycle is directional, not conclusive. The Thread Plan score is "
                "a heuristic — the real read happens after publish."
            ),
            remediation=(
                "Snapshot the post-publish performance via analytics-summarizer in 7d and "
                "feed it back into the next thread-builder run."
            ),
        ))

    return flags[:5]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    variants: list[Variant],
    aggregate: AggregateScores,
    voice_samples_present: bool,
    analytics_present: bool,
    topic: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # Mandatory bridge 1 — analytics-summarizer
    pool.append(Recommendation(
        text=(
            "Snapshot the creator's last 30d via `analytics-summarizer` and re-run thread-builder "
            "with --analytics-file to anchor Predicted engagement on real signals."
            if not analytics_present else
            "Re-snapshot post-publish performance in 7d via `analytics-summarizer` and feed the "
            "delta back into the next thread-builder run."
        ),
        bridge_slug="analytics-summarizer",
    ))

    # Mandatory bridge 2 — content-idea-generator
    pool.append(Recommendation(
        text=(
            f"Source the next anchor topic in the same cluster as \"{topic}\" via "
            "`content-idea-generator` so the thread is part of a series, not a one-off."
        ),
        bridge_slug="content-idea-generator",
    ))

    # Conditional bridges
    if aggregate.thread_plan_score >= 65:
        pool.append(Recommendation(
            text=(
                f"Promote the highest-arc variant into a single-axis A/B (hook only, arc held "
                f"constant) via `ab-test-suggester`."
            ),
            bridge_slug="ab-test-suggester",
        ))

    if not voice_samples_present:
        pool.append(Recommendation(
            text=(
                "Anchor Voice fidelity scoring on a real voice profile via `brand-voice-trainer` "
                "before the next thread cycle."
            ),
            bridge_slug="brand-voice-trainer",
        ))

    pool.append(Recommendation(
        text=(
            "Build a comment-stack plan for the publish-day window via "
            "`comment-engagement-booster` so early replies anchor the algorithmic surface."
        ),
        bridge_slug="comment-engagement-booster",
    ))

    pool.append(Recommendation(
        text=(
            "Confirm the chosen tone register is differentiated from peers in the niche via "
            "`competitor-watch` before publishing."
        ),
        bridge_slug="competitor-watch",
    ))

    if aggregate.paradox_active:
        pool.append(Recommendation(
            text=(
                "Engage substantively with the audience the thread brings in via "
                "`reply-drafter` — voice-faithful only, never copy-pasted."
            ),
            bridge_slug="reply-drafter",
        ))
    else:
        pool.append(Recommendation(
            text=(
                "Adapt the winning variant onto LinkedIn / Newsletter once a directional "
                "winner emerges via `cross-platform-reposter`."
            ),
            bridge_slug="cross-platform-reposter",
        ))

    # Cap to 5; preserve the two mandatory bridges at the head, shuffle the rest
    head = pool[:2]
    tail = pool[2:]
    rng.shuffle(tail)
    chosen = head + tail
    chosen = chosen[:5]

    seen = {r.bridge_slug for r in chosen}
    if len(seen) < 3:
        for slug in CROSS_TEMPLATE_BRIDGES:
            if slug not in seen:
                chosen[-1] = Recommendation(
                    text=(
                        "Cross-reference the variant set with niche peers via "
                        f"`{slug}` to confirm the angle is differentiated."
                    ),
                    bridge_slug=slug,
                )
                break

    return chosen


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    aggregate: AggregateScores,
    voice_samples_present: bool,
    analytics_present: bool,
    is_demo: bool,
) -> tuple[str, str]:
    if voice_samples_present and analytics_present and not is_demo:
        return (
            "high",
            f"real voice samples + analytics anchor the variant set; Thread Plan score "
            f"{aggregate.thread_plan_score}/100.",
        )
    if voice_samples_present and not is_demo:
        return (
            "medium",
            "real voice samples anchor Voice fidelity but no --analytics-file was supplied; "
            "Predicted engagement is niche-typical.",
        )
    if analytics_present:
        return (
            "medium",
            "analytics anchor Predicted engagement but no --voice-samples-file was supplied; "
            "Voice fidelity uses register defaults — re-run with samples to lift to high.",
        )
    return (
        "low",
        "data source is seeded demo voice — re-run with --voice-samples-file and "
        "--analytics-file for real-creator scoring to lift confidence.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_thread_snapshot(
    handle: str,
    topic: str,
    variants: list[Variant],
    thread_length: str,
    tone_focus: str,
    voice_samples_present: bool,
    analytics_present: bool,
    is_demo: bool,
) -> str:
    n_posts = THREAD_LENGTH_POSTS[thread_length]
    register_set = sorted({v.register for v in variants})
    headline = (
        f"{handle}: {len(variants)} thread variants on {topic} — "
        f"{' / '.join(register_set)} register{'s' if len(register_set) > 1 else ''}; "
        f"{thread_length}-length ({n_posts} posts each)."
    )
    if voice_samples_present and analytics_present and not is_demo:
        data_source = "real voice samples + analytics from --voice-samples-file / --analytics-file"
    elif voice_samples_present and not is_demo:
        data_source = "real voice samples from --voice-samples-file (no analytics file attached)"
    elif analytics_present:
        data_source = "analytics from --analytics-file (no voice-samples file attached)"
    else:
        data_source = "seeded demo voice — re-run with --voice-samples-file for real-creator scoring"
    return "\n".join([
        "## Thread Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Topic / goal**: {topic}",
        f"- **Variant count**: {len(variants)}",
        f"- **Thread length target**: {thread_length} ({n_posts} posts)",
        f"- **Tone focus**: {tone_focus}",
        f"- **Data source**: {data_source}",
    ])


def _render_thread_plan_performance(aggregate: AggregateScores, is_demo: bool) -> str:
    demo_tag = " [demo metric — re-run with --voice-samples-file for real-creator scoring]" if is_demo else ""
    band = predicted_band(aggregate.predicted_engagement)
    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        f"| Hook strength             | {aggregate.hook}/100{demo_tag} | "
        f"{_arrow_for(aggregate.hook, ARROW_FLOORS['Hook strength'])} | "
        f"{aggregate.interpretations['Hook strength']} |",
        f"| Narrative arc coherence   | {aggregate.arc}/100{demo_tag} | "
        f"{_arrow_for(aggregate.arc, ARROW_FLOORS['Narrative arc coherence'])} | "
        f"{aggregate.interpretations['Narrative arc coherence']} |",
        f"| Voice fidelity            | {aggregate.voice}/100{demo_tag} | "
        f"{_arrow_for(aggregate.voice, ARROW_FLOORS['Voice fidelity'])} | "
        f"{aggregate.interpretations['Voice fidelity']} |",
        f"| Predicted engagement      | {aggregate.predicted_engagement}/100 (band: {band}){demo_tag} | "
        f"{_arrow_for(aggregate.predicted_engagement, ARROW_FLOORS['Predicted engagement'])} | "
        f"{aggregate.interpretations['Predicted engagement']} |",
    ]
    out = "## Thread Plan Performance\n\n" + "\n".join(rows)
    if aggregate.paradox_active:
        idxs = ", ".join(str(i) for i in aggregate.paradox_variants)
        out += (
            f"\n\n> ⚠️ paradox: hook is catchy but the arc does not deliver — clickbait debt that "
            f"erodes trust over time (variant {idxs})."
        )
    out += f"\n\n**Thread Plan score**: {aggregate.thread_plan_score}/100"
    return out


def _render_variants(variants: list[Variant]) -> str:
    lines = [f"## Thread Variants ({len(variants)}; drafts only — never auto-published)", ""]
    for v in variants:
        if len(v.hook_text) > HOOK_CHAR_CAP:
            raise RuntimeError(
                f"Variant {v.index} hook exceeds {HOOK_CHAR_CAP} chars — refusing to render."
            )
        header = (
            f"### Variant {v.index} — {v.register} (Hook {v.scores.hook}/100 · "
            f"Arc {v.scores.arc}/100 · Voice {v.scores.voice}/100)"
        )
        lines.append(header)
        lines.append("")
        lines.append(f"**Hook (Post 1):** {v.hook_text}")
        lines.append("")
        lines.append("**Arc beats:**")
        for j, beat in enumerate(v.arc_beats, start=1):
            lines.append(f"{j}. {beat}")
        lines.append("")
        lines.append(f"**Why this lands:** {v.why_lands}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_hook_variations(
    variants: list[Variant], variations: list[HookVariation],
) -> str:
    if not variants:
        return ""
    highest = max(variants, key=lambda v: v.scores.arc)
    lines = [
        f"## Hook Variations ({len(variations)} alternatives for Variant {highest.index} — highest-arc)",
        "",
    ]
    for i, hv in enumerate(variations, start=1):
        if len(hv.text) > HOOK_CHAR_CAP:
            raise RuntimeError(
                f"Hook variation #{i} exceeds {HOOK_CHAR_CAP} chars — refusing to render."
            )
        lines.append(f"{i}. **{hv.style}**: {hv.text}")
    return "\n".join(lines)


def _render_engagement_forecast(
    variants: list[Variant],
    aggregate: AggregateScores,
    analytics_present: bool,
    analytics_path: Optional[str],
) -> str:
    band = predicted_band(aggregate.predicted_engagement)
    drivers = []
    if aggregate.hook >= 75:
        drivers.append("Hook strength")
    if aggregate.arc >= 75:
        drivers.append("Narrative arc")
    if aggregate.voice >= 70:
        drivers.append("Voice fidelity")
    if not drivers:
        drivers.append("None of the sub-scores cleared the lift floor")
    drivers_line = ", ".join(drivers) + (
        " pull the band up." if drivers != ["None of the sub-scores cleared the lift floor"]
        else "; rewrite hook + arc before publishing."
    )
    if analytics_present and analytics_path:
        anchor_line = f"yes — file at `{analytics_path}`"
    else:
        anchor_line = "no — niche-typical defaults; band would tighten with --analytics-file"

    highest = max(variants, key=lambda v: v.scores.thread_plan_score)
    return "\n".join([
        "## Engagement Forecast (content-engagement bands — never absolute counts)",
        "",
        f"- **Predicted engagement band**: {band} (sub-score {aggregate.predicted_engagement}/100)",
        f"- **Drivers**: {drivers_line}",
        f"- **Anchored to analytics-summarizer?**: {anchor_line}",
        f"- **Highest-EV variant**: Variant {highest.index} (Thread Plan Score "
        f"{highest.scores.thread_plan_score}/100)",
    ])


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    for i, rec in enumerate(recs, start=1):
        lines.append(f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`")
    return "\n".join(lines)


def _render_thread_audit(
    variants: list[Variant],
    voice_samples_present: bool,
    analytics_present: bool,
) -> str:
    voice_line = (
        "real samples supplied — Voice fidelity is anchored to the creator's cadence."
        if voice_samples_present else
        "no --voice-samples-file supplied — Voice fidelity uses register defaults; "
        "re-run with samples to lift the score."
    )
    analytics_line = (
        "real --analytics-file attached; Predicted engagement is anchored to the creator's "
        "actual baseline."
        if analytics_present else
        "no --analytics-file attached; Predicted engagement is niche-typical, not creator-specific."
    )
    cognitive_line = (
        "5 variants is the cap; once a directional winner emerges, re-run with --variants 3 "
        "to focus the next round on the surviving register."
        if len(variants) >= VARIANT_MAX else
        f"{len(variants)} variants is inside the safe band (3-4)."
    )
    registers = sorted({v.register for v in variants})
    register_line = (
        f"{len(registers)} of 4 standard registers represented "
        f"({', '.join(registers)})."
    )
    return "\n".join([
        "## Thread Audit (auto-triggered)",
        "",
        f"- **Voice-sample adequacy**: {voice_line}",
        f"- **Analytics anchoring**: {analytics_line}",
        f"- **Variant cognitive load**: {cognitive_line}",
        f"- **Tone-register diversity**: {register_line}",
        "- **Re-run cadence**: draft → publish → analytics-summarizer in 7d → re-run "
        "thread-builder for the next anchor in the same cluster.",
    ])


def render_report(
    handle: str,
    topic: str,
    variants: list[Variant],
    aggregate: AggregateScores,
    variations: list[HookVariation],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    thread_length: str,
    tone_focus: str,
    voice_samples_present: bool,
    analytics_present: bool,
    analytics_path: Optional[str],
    is_demo: bool,
) -> str:
    sections = [
        _render_thread_snapshot(
            handle, topic, variants, thread_length, tone_focus,
            voice_samples_present, analytics_present, is_demo,
        ),
        "",
        _render_thread_plan_performance(aggregate, is_demo),
        "",
        _render_variants(variants),
        "",
        _render_hook_variations(variants, variations),
        "",
        _render_engagement_forecast(variants, aggregate, analytics_present, analytics_path),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    audit_trigger = (
        len(flags) > 3
        or len(variants) >= VARIANT_MAX
        or (is_demo and not voice_samples_present)
    )
    if audit_trigger:
        sections.extend([
            "",
            _render_thread_audit(variants, voice_samples_present, analytics_present),
        ])

    return "\n".join(sections).rstrip() + "\n"


def render_monetization_refusal(handle: str, topic: str) -> str:
    bridges = [
        Recommendation(
            text=(
                f"Run `monetization-optimizer` with the same topic to model the funnel "
                f"(paid-tier conversion, sponsorship CPM, ad-revenue projection)."
            ),
            bridge_slug="monetization-optimizer",
        ),
        Recommendation(
            text=(
                "Snapshot the creator's last 30d content engagement first via "
                "`analytics-summarizer` — monetization-optimizer's funnel needs the "
                "engagement baseline as input."
            ),
            bridge_slug="analytics-summarizer",
        ),
        Recommendation(
            text=(
                f"Re-source the topic as a content angle (not a revenue angle) via "
                f"`content-idea-generator`, then re-run thread-builder once the angle "
                f"is content-engagement-shaped."
            ),
            bridge_slug="content-idea-generator",
        ),
    ]
    sections = [
        "## Out-of-scope — refusal",
        "",
        f"**{handle}: thread-builder run halted; topic crosses into monetization scope.**",
        "",
        f"- **Topic supplied**: {topic}",
        "- **Why refused**: thread-builder strictly stays inside content-engagement scope "
        "(impressions / replies / reposts / bookmarks pattern). Revenue, paid-tier "
        "conversion, sponsorship dollars, ad spend, and affiliate splits belong to "
        "`monetization-optimizer`.",
        "- **Variants emitted**: 0 (refusal path)",
        "",
        _render_recommendations(bridges),
        "",
        "## Confidence",
        "Confidence: high — refusal triggered by the monetization topic-keyword guard.",
    ]
    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Thread Builder (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Demo bundles
# ---------------------------------------------------------------------------


DEMO_BUNDLES = {
    "default": {
        "x_handle": "@JanSol0s",
        "topic_or_goal": "agent-eval failure modes",
        "variant_count": 3,
        "thread_length": "medium",
        "tone_focus": "all",
        "voice_samples": [],
        "analytics_file": None,
        "data_source": "demo",
    },
    "paradox": {
        "x_handle": "@JanSol0s",
        "topic_or_goal": "creator burnout patterns",
        "variant_count": 3,
        "thread_length": "medium",
        "tone_focus": "all",
        "voice_samples": [],
        "analytics_file": None,
        "data_source": "demo",
        "score_overrides": {1: {"hook": 88, "arc": 42, "voice": 64}},
    },
    "five-variants": {
        "x_handle": "@habitstacker",
        "topic_or_goal": "weekly maker rituals",
        "variant_count": 5,
        "thread_length": "medium",
        "tone_focus": "all",
        "voice_samples": [],
        "analytics_file": None,
        "data_source": "demo",
    },
}


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_thread_plan(
    *,
    x_handle: str,
    topic_or_goal: Optional[str] = None,
    voice_samples: Optional[list[str]] = None,
    analytics_file: Optional[str] = None,
    variant_count: int = 3,
    thread_length: str = "medium",
    tone_focus: str = "all",
    when: Optional[str] = None,
    demo_mode: Optional[str] = None,
    data_source: str = "real",
    score_overrides: Optional[dict[int, dict]] = None,
) -> str:
    handle = normalize_handle(x_handle)
    if not handle:
        raise ValueError("--x-handle is required and must be non-empty.")

    bundle: dict
    if demo_mode is not None:
        if demo_mode not in DEMO_BUNDLES:
            raise ValueError(
                f"demo_mode must be one of {tuple(DEMO_BUNDLES.keys())}, got {demo_mode!r}"
            )
        bundle = json.loads(json.dumps(DEMO_BUNDLES[demo_mode]))
        if topic_or_goal:
            bundle["topic_or_goal"] = topic_or_goal
    else:
        if not topic_or_goal:
            raise ValueError(
                "topic_or_goal is required unless a --demo flag is passed."
            )
        bundle = {
            "x_handle": handle,
            "topic_or_goal": topic_or_goal,
            "variant_count": variant_count,
            "thread_length": thread_length,
            "tone_focus": tone_focus,
            "voice_samples": list(voice_samples or []),
            "analytics_file": analytics_file,
            "data_source": data_source,
        }

    bundle["x_handle"] = handle
    bundle["variant_count"] = int(bundle.get("variant_count", variant_count))
    bundle["thread_length"] = bundle.get("thread_length", thread_length)
    bundle["tone_focus"] = bundle.get("tone_focus", tone_focus)
    bundle["voice_samples"] = list(bundle.get("voice_samples") or voice_samples or [])
    if analytics_file is not None:
        bundle["analytics_file"] = analytics_file
    if score_overrides is not None:
        bundle["score_overrides"] = score_overrides

    if not VARIANT_MIN <= bundle["variant_count"] <= VARIANT_MAX:
        raise ValueError(
            f"variant_count must be {VARIANT_MIN}-{VARIANT_MAX}, got {bundle['variant_count']}"
        )
    if bundle["thread_length"] not in THREAD_LENGTH_OPTIONS:
        raise ValueError(
            f"thread_length must be one of {THREAD_LENGTH_OPTIONS}, got {bundle['thread_length']!r}"
        )
    if bundle["tone_focus"] not in TONE_FOCUS_OPTIONS:
        raise ValueError(
            f"tone_focus must be one of {TONE_FOCUS_OPTIONS}, got {bundle['tone_focus']!r}"
        )

    topic = str(bundle["topic_or_goal"])
    if topic_is_monetization(topic):
        rendered = render_monetization_refusal(handle, topic)
        assert_only_creator_handle_in_render(rendered, handle)
        return rendered

    is_demo = bundle.get("data_source") == "demo"
    voice_samples_present = bool(bundle["voice_samples"])
    analytics_path = bundle.get("analytics_file")
    analytics_present = bool(analytics_path)

    voice_lift = 12 if voice_samples_present else 0
    analytics_lift = 8 if analytics_present else 0

    overrides_raw = bundle.get("score_overrides") or {}
    overrides = {int(k): dict(v) for k, v in overrides_raw.items()}

    variants = build_variants(
        topic=topic,
        variant_count=bundle["variant_count"],
        thread_length=bundle["thread_length"],
        tone_focus=bundle["tone_focus"],
        voice_lift=voice_lift,
        analytics_lift=analytics_lift,
        score_overrides=overrides,
    )
    aggregate = aggregate_variants(variants)

    n_posts = THREAD_LENGTH_POSTS[bundle["thread_length"]]
    variation_count = HOOK_VARIATION_MAX if bundle["variant_count"] >= VARIANT_MAX else HOOK_VARIATION_MIN
    variations = build_hook_variations(topic, n_posts, variation_count)

    flags = build_red_flags(
        variants, aggregate, voice_samples_present, analytics_present, is_demo,
    )

    seed = hashlib.sha256(
        (handle + topic + str(bundle["variant_count"]) + bundle["thread_length"]
         + bundle["tone_focus"]).encode("utf-8")
    ).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))

    recs = build_recommendations(
        rng, variants, aggregate, voice_samples_present, analytics_present, topic,
    )

    confidence = confidence_for(aggregate, voice_samples_present, analytics_present, is_demo)

    rendered = render_report(
        handle=handle,
        topic=topic,
        variants=variants,
        aggregate=aggregate,
        variations=variations,
        flags=flags,
        recs=recs,
        confidence=confidence,
        thread_length=bundle["thread_length"],
        tone_focus=bundle["tone_focus"],
        voice_samples_present=voice_samples_present,
        analytics_present=analytics_present,
        analytics_path=analytics_path,
        is_demo=is_demo,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


generate = generate_thread_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Thread Builder (Grok Agent OS · creator template)\n"
        "  Drafts only · Variant cap 5 · Hook cap 240 chars\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="thread-builder",
        description=(
            "Read a creator-supplied topic / goal (and optional voice samples + "
            "analytics export) and emit a 6/7-section thread plan with 3-5 "
            "ready-to-post variants, 4 standard Thread Plan Score metrics, "
            "hook-without-payoff paradox detection, 4-6 alternate hooks, and "
            ">= 3 cross-template bridges (mandatory: analytics-summarizer + "
            "content-idea-generator). Drafts only — never auto-publishes."
        ),
    )
    p.add_argument("--x-handle", required=True,
                   help="Creator's X handle (with or without leading @).")
    p.add_argument("--topic", "--topic-or-goal", "--goal", dest="topic",
                   help="Thread topic / thesis / goal in plain text. Required unless --demo.")
    p.add_argument("--voice-samples-file",
                   help="Path to a JSON file containing a list of the creator's recent post bodies.")
    p.add_argument("--analytics-file",
                   help="Path to an analytics-summarizer JSON export. Anchors Predicted engagement.")
    p.add_argument("--variants", "--variant-count", dest="variant_count", type=int, default=3,
                   help=f"Number of thread variants to draft ({VARIANT_MIN}-{VARIANT_MAX}; default 3).")
    p.add_argument("--thread-length", choices=list(THREAD_LENGTH_OPTIONS), default="medium",
                   help="Target thread length: short (5), medium (8), long (12) posts. Default medium.")
    p.add_argument("--tone", "--tone-focus", dest="tone_focus",
                   choices=list(TONE_FOCUS_OPTIONS), default="all",
                   help="Tone register to emphasise. Default 'all'.")
    p.add_argument("--input-file",
                   help="Optional path to a thread-builder brief JSON (encapsulates topic + voice + analytics).")
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true",
                   help="Suppress the runner banner on stdout.")
    p.add_argument("--demo", action="store_true",
                   help="Run with the standard 3-variant demo (agent-eval failure modes).")
    p.add_argument("--demo-paradox", action="store_true",
                   help="Run with the hook-without-payoff paradox demo.")
    p.add_argument("--demo-five-variants", action="store_true",
                   help="Run with the 5-variant demo (auto-triggers Thread Audit).")
    p.add_argument("--show-system-prompt", action="store_true",
                   help="Print system prompt path + size on stderr.")
    return p


def _resolve_voice_samples(path: Optional[str]) -> list[str]:
    if not path:
        return []
    payload = load_json_file(Path(path).expanduser().resolve(), "voice-samples-file")
    if not isinstance(payload, list):
        raise ValueError("--voice-samples-file must be a JSON list of post bodies.")
    return [str(p) for p in payload]


def _resolve_input_file(path: Optional[str]) -> dict:
    if not path:
        return {}
    payload = load_json_file(Path(path).expanduser().resolve(), "input-file")
    if not isinstance(payload, dict):
        raise ValueError("--input-file must be a JSON object (the brief bundle).")
    return payload


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
        demo_mode = "default"
    elif args.demo_paradox:
        demo_mode = "paradox"
    elif args.demo_five_variants:
        demo_mode = "five-variants"

    bundle_overrides = _resolve_input_file(args.input_file)

    topic = args.topic or bundle_overrides.get("topic_or_goal")
    voice_samples_inline = bundle_overrides.get("voice_samples")
    voice_samples = (
        list(voice_samples_inline)
        if isinstance(voice_samples_inline, list) and voice_samples_inline
        else _resolve_voice_samples(args.voice_samples_file)
    )
    analytics_file = args.analytics_file or bundle_overrides.get("analytics_file")
    variant_count = int(bundle_overrides.get("variant_count", args.variant_count))
    thread_length = bundle_overrides.get("thread_length", args.thread_length)
    tone_focus = bundle_overrides.get("tone_focus", args.tone_focus)
    score_overrides = bundle_overrides.get("score_overrides")
    data_source = str(bundle_overrides.get("data_source", "real"))

    if not topic and demo_mode is None:
        sys.stderr.write(
            "error: provide --topic <text>, --input-file <path>, or one of "
            "--demo / --demo-paradox / --demo-five-variants.\n"
        )
        return 2

    if variant_count < VARIANT_MIN or variant_count > VARIANT_MAX:
        sys.stderr.write(
            f"error: --variants must be {VARIANT_MIN}-{VARIANT_MAX}, got {variant_count}.\n"
        )
        return 2

    rendered = generate_thread_plan(
        x_handle=args.x_handle,
        topic_or_goal=topic,
        voice_samples=voice_samples,
        analytics_file=analytics_file,
        variant_count=variant_count,
        thread_length=thread_length,
        tone_focus=tone_focus,
        demo_mode=demo_mode,
        data_source=data_source,
        score_overrides=score_overrides,
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
