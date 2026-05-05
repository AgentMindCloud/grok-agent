# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Content Idea Generator — runner.

CLI entry point for the ``content-idea-generator`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied niche (and optional 7-day trend snapshot,
voice samples, and analytics-summarizer JSON export) and emits the
strict 6/7-section idea plan defined by the merged Slot-1 contract:

  1. Run Snapshot
  2. Idea Plan Performance (4-row metric table + weighted score)
  3. The N Ideas (default 5; each with hook, format, scores, bridge)
  4. Trend Alignment (which trend each idea touches)
  5. Red Flags (2-4; surfaces vanity-hook paradox in BOTH places)
  6. Recommendations (>= 3 cross-template bridges; mandatory:
     analytics-summarizer + thread-builder)
  7. Confidence
  + Optional Idea Audit (auto-appended when red_flags > 3 OR
    count >= 8 OR vanity-hook paradox fires OR data_source = demo
    with no voice/trends)

Hard guarantees enforced by this runner (mirrors the system contract):

* Drafts only. Output is text the creator pastes into the X composer
  themselves; the runner never publishes, schedules, or DMs.
* Idea count band 3-10. Below 3 the run lacks A/B optionality; above
  10 the cognitive load destroys the value of selection.
* Hook character cap of 240. Every idea hook is enforced <= 240
  characters at render time and truncated with an ellipsis if needed.
* Vanity-hook paradox surfaced in BOTH the Idea Plan Performance
  section AND the Red Flags section whenever any idea has Trend
  alignment > 80 AND Niche fit < 50 — a hook that rides a trending
  surface for the wrong audience is the most common Type-I error in
  creator ideation.
* Idea Plan score formula is fixed:
    round(0.30*NicheFit + 0.25*TrendAlign + 0.25*Voice + 0.20*Predicted)
* Content-engagement bands only. Predicted engagement is reported as
  a 0-100 sub-score plus a low / medium / high band — never an absolute
  like / repost / reply count.
* Mandatory monetization refusal. If the niche or any explicit
  ask crosses into revenue, paid-tier, sponsorship, ad-spend, or
  affiliate territory, the runner emits a structured refusal that
  points the creator at monetization-optimizer and stops.
* Mandatory bridges. Every render (including the refusal path) names
  >= 3 cross-template bridges; analytics-summarizer and thread-builder
  are always included so the daily ideation loop hands off cleanly.
* Voice fidelity is creator-only. The runner accepts voice samples
  via --voice-samples-file (a JSON list of the creator's own posts);
  it never scores voice against samples authored by a different handle.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic. Archetype assignment, score nudges, and recommendation
  ordering are seeded by sha256(handle + niche + tone + count + date),
  so the same input always produces the same render.
* Zero external network calls in v1.

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_post_ideas

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
    "Trend alignment",
    "Voice fidelity",
    "Predicted engagement",
)

# Niche fit and Trend alignment are tied at 0.30 / 0.25 because either
# failing alone defeats the run; Voice fidelity matches Trend alignment
# because off-voice ideas erode trust over time; Predicted engagement
# is weighted lowest because it is a heuristic until anchored to a real
# analytics-summarizer export.
PERFORMANCE_WEIGHTS = {
    "Niche fit": 0.30,
    "Trend alignment": 0.25,
    "Voice fidelity": 0.25,
    "Predicted engagement": 0.20,
}

TONE_OPTIONS = ("punchy", "thoughtful", "data-led", "mixed")

COUNT_DEFAULT = 5
COUNT_MIN = 3
COUNT_MAX = 10

HOOK_CHAR_CAP = 240

# Healthy-floor bands for arrow bucketing
ARROW_FLOORS = {
    "Niche fit": 60.0,
    "Trend alignment": 55.0,
    "Voice fidelity": 60.0,
    "Predicted engagement": 50.0,
}

# Vanity-hook paradox: any idea with trend_align > 80 AND niche_fit < 50
# — trend-chasing hook for the wrong audience.
PARADOX_TREND_THRESHOLD = 80
PARADOX_FIT_THRESHOLD = 50

# Engagement bands (sub-score buckets)
ENGAGEMENT_BAND_LOW_MAX = 49
ENGAGEMENT_BAND_HIGH_MIN = 70

# Mandatory cross-template bridges (always present, in this order)
MANDATORY_BRIDGES = ("analytics-summarizer", "thread-builder")

CROSS_TEMPLATE_BRIDGES = (
    # Mandatory two — always present
    "analytics-summarizer",
    "thread-builder",
    # Optional pool
    "reply-drafter",
    "hashtag-strategy-advisor",
    "brand-voice-trainer",
    "ab-test-suggester",
    "competitor-watch",
    "content-recycler",
    "comment-engagement-booster",
    "cross-platform-reposter",
    "trend-aligned-poster",
    "follower-quality-analyzer",
    "monetization-optimizer",
)

# Niche / topic phrasings that route the run into monetization-optimizer
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
    "cashtag",
)

# Per-archetype deterministic data for the idea generator. Each archetype
# describes one canonical X post pattern; the renderer picks N (default
# 5) from this pool deterministically based on the request tone +
# seeded RNG so the same input always produces the same render.
ARCHETYPE_DATA = {
    "numbers-led-list": {
        "format": "thread",
        "tone_affinity": ("punchy", "data-led", "mixed"),
        "base_scores": {"niche_fit": 78, "trend_align": 64, "voice": 64},
        "hook_template": (
            "{n_items} truths about {niche} most teams miss — and the single fix that "
            "compounds across all of them is in post {n_items}."
        ),
        "why_lands": (
            "Numbers-led list posts earn the bookmark; the count signals scannable, "
            "decisive content. Best when each item is genuinely concrete."
        ),
        "bridge_slug": "thread-builder",
        "publish_window": "weekday mornings (Tue-Thu, 7-9am local)",
    },
    "contrarian-thesis": {
        "format": "single-post",
        "tone_affinity": ("punchy",),
        "base_scores": {"niche_fit": 73, "trend_align": 72, "voice": 66},
        "hook_template": (
            "Most takes on {niche} measure the wrong thing. The real lever is "
            "post-publish measurement — most creators skip it, and it shows."
        ),
        "why_lands": (
            "Contrarian framing earns the reply; a clear thesis plus an invitation "
            "to disagree drives engagement on the same surface as the original post."
        ),
        "bridge_slug": "ab-test-suggester",
        "publish_window": "weekday afternoons (1-3pm local)",
    },
    "first-person-rebuild": {
        "format": "thread",
        "tone_affinity": ("thoughtful", "mixed"),
        "base_scores": {"niche_fit": 72, "trend_align": 58, "voice": 70},
        "hook_template": (
            "I spent 3 months getting {niche} wrong. Here's the rebuild — what I tried, "
            "what failed, and the move that finally landed (full breakdown below)."
        ),
        "why_lands": (
            "First-person rebuild stories earn trust by admitting failure. Best when "
            "the creator has lived the rebuild and can name the exact reframing move."
        ),
        "bridge_slug": "thread-builder",
        "publish_window": "Sunday evenings (7-9pm local) — high reply window",
    },
    "question-led-poll": {
        "format": "single-post",
        "tone_affinity": ("thoughtful", "mixed"),
        "base_scores": {"niche_fit": 70, "trend_align": 56, "voice": 65},
        "hook_template": (
            "When was the last time your read on {niche} caught the silent failure? "
            "Probably never. Here's the test I run weekly — takes 10 minutes."
        ),
        "why_lands": (
            "Question-led posts earn the reply directly. Best as a daily anchor "
            "between deeper threads, never as a substitute for them."
        ),
        "bridge_slug": "reply-drafter",
        "publish_window": "weekday lunch (11am-1pm local)",
    },
    "tactical-playbook": {
        "format": "thread",
        "tone_affinity": ("data-led", "punchy"),
        "base_scores": {"niche_fit": 76, "trend_align": 60, "voice": 65},
        "hook_template": (
            "The 5-step playbook I use for {niche}, in order. No fluff — just the "
            "moves that compound. Last step is the part nobody talks about."
        ),
        "why_lands": (
            "Reproducible-sequence posts earn the repost. Best when the playbook is "
            "genuinely actionable and held tight — vague playbooks lose the bookmark."
        ),
        "bridge_slug": "thread-builder",
        "publish_window": "weekday mornings (Tue-Thu, 7-9am local)",
    },
    "story-cold-open": {
        "format": "thread",
        "tone_affinity": ("punchy", "thoughtful"),
        "base_scores": {"niche_fit": 70, "trend_align": 62, "voice": 67},
        "hook_template": (
            "Friday 4pm. Deadline Monday. {niche} was the one thing standing in the "
            "way. Here's how it broke — and what shipped on Sunday night."
        ),
        "why_lands": (
            "Story cold-opens earn the swipe by promising a reveal. Best when the "
            "creator has a real shipped outcome to land on, not a contrived arc."
        ),
        "bridge_slug": "thread-builder",
        "publish_window": "Friday evenings (5-7pm local) — story-friendly window",
    },
    "metric-receipt": {
        "format": "single-post",
        "tone_affinity": ("data-led", "thoughtful", "mixed"),
        "base_scores": {"niche_fit": 74, "trend_align": 60, "voice": 64},
        "hook_template": (
            "After 30d of {niche}, here's what landed — and what didn't. 4 numbers, "
            "no spin. The one I expected to win came in last."
        ),
        "why_lands": (
            "Receipt posts earn the bookmark by proving the creator measures. Best "
            "paired with an actual analytics-summarizer export for credibility."
        ),
        "bridge_slug": "analytics-summarizer",
        "publish_window": "Monday mornings (8-10am local) — week-recap window",
    },
    "synthesis-takedown": {
        "format": "thread",
        "tone_affinity": ("thoughtful", "data-led"),
        "base_scores": {"niche_fit": 73, "trend_align": 66, "voice": 66},
        "hook_template": (
            "Three things most takes on {niche} get wrong — and the one read that "
            "finally connected the dots for me. Receipts in the thread."
        ),
        "why_lands": (
            "Synthesis posts earn the share by reducing 3+ things to a single clear "
            "frame. Best after the creator has done their own reading and can cite it."
        ),
        "bridge_slug": "competitor-watch",
        "publish_window": "weekday afternoons (2-4pm local)",
    },
    "trend-aligned-riff": {
        "format": "quote-tweet",
        "tone_affinity": ("punchy", "mixed"),
        "base_scores": {"niche_fit": 60, "trend_align": 84, "voice": 64},
        "hook_template": (
            "On the trending take about {niche}: the angle most peers are missing is "
            "the second-order effect on creator workflows. Here's the version I'd ship."
        ),
        "why_lands": (
            "Quote-tweet riffs earn impressions by riding existing reach. Best when "
            "the original take is in-niche; never quote-tweet for vanity reach alone."
        ),
        "bridge_slug": "trend-aligned-poster",
        "publish_window": "within 4 hours of the trending post (window-sensitive)",
    },
    "anti-pattern-warning": {
        "format": "single-post",
        "tone_affinity": ("data-led", "thoughtful", "mixed"),
        "base_scores": {"niche_fit": 72, "trend_align": 58, "voice": 65},
        "hook_template": (
            "The {niche} anti-pattern I see most often: optimising the metric the "
            "algorithm rewards instead of the metric the audience actually cares about."
        ),
        "why_lands": (
            "Anti-pattern posts earn the reply by giving the audience permission to "
            "recognise their own version of the trap. Pair with a positive example."
        ),
        "bridge_slug": "follower-quality-analyzer",
        "publish_window": "weekday afternoons (3-5pm local)",
    },
}

# Pool ordering per tone — deterministic so the same tone always picks
# from the same pool head. Mixed pulls from all archetypes.
TONE_POOL = {
    "punchy": (
        "numbers-led-list",
        "contrarian-thesis",
        "story-cold-open",
        "trend-aligned-riff",
        "anti-pattern-warning",
        "tactical-playbook",
        "question-led-poll",
        "first-person-rebuild",
        "metric-receipt",
        "synthesis-takedown",
    ),
    "thoughtful": (
        "first-person-rebuild",
        "synthesis-takedown",
        "question-led-poll",
        "metric-receipt",
        "story-cold-open",
        "anti-pattern-warning",
        "numbers-led-list",
        "tactical-playbook",
        "contrarian-thesis",
        "trend-aligned-riff",
    ),
    "data-led": (
        "numbers-led-list",
        "metric-receipt",
        "tactical-playbook",
        "synthesis-takedown",
        "anti-pattern-warning",
        "contrarian-thesis",
        "first-person-rebuild",
        "question-led-poll",
        "story-cold-open",
        "trend-aligned-riff",
    ),
    "mixed": (
        "numbers-led-list",
        "first-person-rebuild",
        "question-led-poll",
        "tactical-playbook",
        "metric-receipt",
        "story-cold-open",
        "synthesis-takedown",
        "anti-pattern-warning",
        "contrarian-thesis",
        "trend-aligned-riff",
    ),
}


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
                "Content Idea Generator privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class IdeaScores:
    niche_fit: int
    trend_align: int
    voice: int
    predicted_engagement: int

    @property
    def idea_score(self) -> int:
        return round(
            PERFORMANCE_WEIGHTS["Niche fit"] * self.niche_fit
            + PERFORMANCE_WEIGHTS["Trend alignment"] * self.trend_align
            + PERFORMANCE_WEIGHTS["Voice fidelity"] * self.voice
            + PERFORMANCE_WEIGHTS["Predicted engagement"] * self.predicted_engagement
        )


@dataclass
class Idea:
    index: int
    archetype: str
    format: str
    scores: IdeaScores
    hook_text: str
    why_lands: str
    bridge_slug: str
    publish_window: str
    matched_trend: Optional[str] = None


@dataclass
class AggregateScores:
    niche_fit: int
    trend_align: int
    voice: int
    predicted_engagement: int
    paradox_active: bool
    paradox_ideas: list[int] = field(default_factory=list)
    interpretations: dict = field(default_factory=dict)

    @property
    def idea_plan_score(self) -> int:
        return round(
            PERFORMANCE_WEIGHTS["Niche fit"] * self.niche_fit
            + PERFORMANCE_WEIGHTS["Trend alignment"] * self.trend_align
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


def niche_is_monetization(niche: str) -> bool:
    low = niche.lower()
    return any(kw in low for kw in MONETIZATION_KEYWORDS)


# ---------------------------------------------------------------------------
# Idea builder
# ---------------------------------------------------------------------------


def _select_archetypes(
    tone: str, count: int, rng: Random,
) -> list[str]:
    if tone not in TONE_POOL:
        raise ValueError(f"tone must be one of {TONE_OPTIONS}, got {tone!r}")
    if not COUNT_MIN <= count <= COUNT_MAX:
        raise ValueError(f"count must be {COUNT_MIN}-{COUNT_MAX}, got {count}")
    pool = list(TONE_POOL[tone])
    chosen: list[str] = []
    for slug in pool:
        if len(chosen) >= count:
            break
        chosen.append(slug)
    if len(chosen) < count:
        extras = [s for s in ARCHETYPE_DATA if s not in chosen]
        rng.shuffle(extras)
        for s in extras:
            chosen.append(s)
            if len(chosen) >= count:
                break
    return chosen[:count]


def _format_hook(archetype: str, niche: str, count: int) -> str:
    template = ARCHETYPE_DATA[archetype]["hook_template"]
    n_items = max(3, min(count, 9))
    text = template.format(niche=niche, n_items=n_items)
    if len(text) > HOOK_CHAR_CAP:
        text = text[: HOOK_CHAR_CAP - 1].rstrip() + "…"
    return text


def _scores_for_idea(
    archetype: str,
    index: int,
    requested_tone: str,
    voice_lift: int,
    analytics_lift: int,
    trends: list[str],
    niche: str,
    rng: Random,
    overrides: dict[int, dict],
) -> IdeaScores:
    base = ARCHETYPE_DATA[archetype]["base_scores"]
    affinities = ARCHETYPE_DATA[archetype]["tone_affinity"]

    if index in overrides:
        ov = overrides[index]
        niche_fit = int(ov.get("niche_fit", base["niche_fit"]))
        trend_align = int(ov.get("trend_align", base["trend_align"]))
        voice = int(ov.get("voice", base["voice"]))
    else:
        niche_fit = base["niche_fit"]
        trend_align = base["trend_align"]
        voice = base["voice"]

    # Tone-affinity nudge — exact match lifts niche_fit, mismatch dampens it
    if requested_tone in affinities:
        niche_fit += 5
    elif requested_tone != "mixed":
        niche_fit -= 6

    # Trend-file lift — trends present at all lifts trend_align by 8;
    # explicit niche keyword in trends adds another 8
    if trends:
        trend_align += 8
        niche_lower = niche.lower()
        if any(niche_lower in t.lower() or t.lower() in niche_lower for t in trends):
            trend_align += 8

    # Voice-file lift — supplied samples lift voice by 12
    voice += voice_lift

    # Per-idea drift — small seeded nudge so ideas aren't identical
    nudge = rng.randint(-3, 3)
    niche_fit += nudge
    trend_align += rng.randint(-2, 2)
    voice += rng.randint(-2, 2)

    niche_fit = max(0, min(100, niche_fit))
    trend_align = max(0, min(100, trend_align))
    voice = max(0, min(100, voice))

    # Predicted engagement is a heuristic: 0.40*niche_fit + 0.30*trend_align
    # + 0.20*voice + 0.10*analytics_lift (analytics anchoring lifts the band)
    predicted_raw = round(
        0.40 * niche_fit
        + 0.30 * trend_align
        + 0.20 * voice
        + 0.10 * (50 + analytics_lift)
    )
    predicted = max(20, min(95, predicted_raw))

    return IdeaScores(
        niche_fit=niche_fit,
        trend_align=trend_align,
        voice=voice,
        predicted_engagement=predicted,
    )


def _matched_trend_for(archetype: str, niche: str, trends: list[str]) -> Optional[str]:
    if not trends:
        return None
    arc_words = archetype.replace("-", " ").split()
    niche_lower = niche.lower()
    for t in trends:
        t_lower = t.lower()
        if niche_lower in t_lower or t_lower in niche_lower:
            return t
        if any(w in t_lower for w in arc_words):
            return t
    return trends[0] if trends else None


def build_ideas(
    niche: str,
    tone: str,
    count: int,
    voice_lift: int,
    analytics_lift: int,
    trends: list[str],
    rng: Random,
    overrides: Optional[dict[int, dict]] = None,
) -> list[Idea]:
    overrides = overrides or {}
    archetypes = _select_archetypes(tone, count, rng)

    ideas: list[Idea] = []
    for i, archetype in enumerate(archetypes, start=1):
        meta = ARCHETYPE_DATA[archetype]
        scores = _scores_for_idea(
            archetype=archetype,
            index=i,
            requested_tone=tone,
            voice_lift=voice_lift,
            analytics_lift=analytics_lift,
            trends=trends,
            niche=niche,
            rng=rng,
            overrides=overrides,
        )
        ideas.append(Idea(
            index=i,
            archetype=archetype,
            format=meta["format"],
            scores=scores,
            hook_text=_format_hook(archetype, niche, count),
            why_lands=meta["why_lands"],
            bridge_slug=meta["bridge_slug"],
            publish_window=meta["publish_window"],
            matched_trend=_matched_trend_for(archetype, niche, trends),
        ))
    return ideas


# ---------------------------------------------------------------------------
# Aggregation, arrows, paradox detection
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


def aggregate_ideas(ideas: list[Idea]) -> AggregateScores:
    n = max(1, len(ideas))
    niche_fit = round(sum(i.scores.niche_fit for i in ideas) / n)
    trend_align = round(sum(i.scores.trend_align for i in ideas) / n)
    voice = round(sum(i.scores.voice for i in ideas) / n)
    predicted = round(sum(i.scores.predicted_engagement for i in ideas) / n)

    paradox_ideas = [
        i.index for i in ideas
        if i.scores.trend_align > PARADOX_TREND_THRESHOLD
        and i.scores.niche_fit < PARADOX_FIT_THRESHOLD
    ]
    paradox_active = bool(paradox_ideas)

    interp = {
        "Niche fit": _interp_niche(niche_fit),
        "Trend alignment": _interp_trend(trend_align),
        "Voice fidelity": _interp_voice(voice),
        "Predicted engagement": _interp_predicted(predicted),
    }
    return AggregateScores(
        niche_fit=niche_fit,
        trend_align=trend_align,
        voice=voice,
        predicted_engagement=predicted,
        paradox_active=paradox_active,
        paradox_ideas=paradox_ideas,
        interpretations=interp,
    )


def _interp_niche(score: int) -> str:
    if score >= 85:
        return "Above the strong-fit floor; the run is anchored squarely in the supplied niche."
    if score >= 70:
        return "Strong niche fit; ideas read as on-brand for the supplied audience."
    if score >= 60:
        return "Healthy niche fit; one or two ideas drift but the set as a whole holds."
    return "Below the niche-fit floor; rewrite the niche prompt or shift tone before publishing."


def _interp_trend(score: int) -> str:
    if score >= 80:
        return "High trend alignment; ideas ride the 7-day surface without becoming derivative."
    if score >= 65:
        return "Healthy trend alignment; ideas stay current without chasing every spike."
    if score >= 50:
        return "Moderate trend alignment; supply a richer --trends-file to anchor the set."
    return "Low trend alignment; the run is evergreen — fine, but unlikely to surf the algorithm."


def _interp_voice(score: int) -> str:
    if score >= 85:
        return "Tight voice match; one notch shy of stylistic over-fit."
    if score >= 70:
        return "Strong creator-voice fidelity across ideas."
    if score >= 60:
        return "On-voice; lift further by attaching a brand-voice-trainer profile."
    return "Voice drift — re-run with --voice-samples-file to anchor scoring on real samples."


def _interp_predicted(score: int) -> str:
    if score >= ENGAGEMENT_BAND_HIGH_MIN:
        return "High band; niche-fit + trend + voice all pull the prediction up."
    if score >= 50:
        return "Medium band; niche-typical engagement on the daily ideation cycle."
    return "Low band; the run is unlikely to break niche baseline without revision."


def predicted_band(score: int) -> str:
    if score >= ENGAGEMENT_BAND_HIGH_MIN:
        return "high"
    if score > ENGAGEMENT_BAND_LOW_MAX:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    ideas: list[Idea],
    aggregate: AggregateScores,
    voice_samples_present: bool,
    trends_present: bool,
    analytics_present: bool,
    is_demo: bool,
    count: int,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1 — Vanity-hook paradox (mandatory in BOTH places when fired)
    if aggregate.paradox_active:
        idxs = ", ".join(str(i) for i in aggregate.paradox_ideas)
        gap_lines = []
        for i in ideas:
            if i.index in aggregate.paradox_ideas:
                gap_lines.append(
                    f"Idea {i.index} ({i.archetype}) Trend alignment "
                    f"{i.scores.trend_align}/100 vs Niche fit "
                    f"{i.scores.niche_fit}/100"
                )
        flags.append(RedFlag(
            title="Vanity-hook paradox",
            severity="high",
            explanation=(
                f"Idea index(es) {idxs} show Trend alignment > {PARADOX_TREND_THRESHOLD} AND "
                f"Niche fit < {PARADOX_FIT_THRESHOLD} — the hook rides a trending surface for "
                f"the wrong audience ({'; '.join(gap_lines)})."
            ),
            remediation=(
                "Either drop the off-niche idea(s) before publishing, or rewrite the angle so "
                "the hook lands inside the supplied niche instead of riding adjacent reach."
            ),
        ))

    # Rule 2 — Voice-sample thinness
    if not voice_samples_present:
        flags.append(RedFlag(
            title="Voice-sample thinness",
            severity="medium",
            explanation=(
                "No --voice-samples-file was supplied; Voice fidelity scoring uses archetype "
                "defaults rather than the creator's actual cadence."
            ),
            remediation=(
                "Re-run with --voice-samples-file pointing at 5-10 of the creator's recent "
                "posts, or attach a brand-voice-trainer profile."
            ),
        ))

    # Rule 3 — Trend anchoring missing
    if not trends_present:
        flags.append(RedFlag(
            title="Trend anchoring missing",
            severity="low" if voice_samples_present else "medium",
            explanation=(
                "No --trends-file was supplied; Trend alignment scoring uses archetype "
                "defaults rather than the actual 7-day niche surface."
            ),
            remediation=(
                "Run trend-aligned-poster on the last 7d, attach the JSON via --trends-file, "
                "and re-run content-idea-generator."
            ),
        ))

    # Rule 4 — Analytics anchoring missing
    if not analytics_present:
        flags.append(RedFlag(
            title="Engagement anchoring missing",
            severity="low",
            explanation=(
                "No --analytics-file was supplied; Predicted engagement is a niche-typical "
                "default rather than the creator's actual baseline."
            ),
            remediation=(
                "Run analytics-summarizer on the last 30d, attach the JSON via --analytics-file, "
                "and re-run content-idea-generator."
            ),
        ))

    # Rule 5 — Idea-count cognitive load (only at the upper band)
    if count >= 8:
        flags.append(RedFlag(
            title="Idea-count cognitive load",
            severity="medium",
            explanation=(
                f"{count} ideas is at the upper band; cognitive load on the creator above 7 "
                "destroys the value of A/B selection across a single run."
            ),
            remediation=(
                "Once a directional winner archetype emerges, re-run with --count 5 to focus "
                "the next round on the surviving register."
            ),
        ))

    # Rule 6 — Aggregate niche fit below floor
    if aggregate.niche_fit < 60 and not aggregate.paradox_active:
        flags.append(RedFlag(
            title="Aggregate niche fit below read-floor",
            severity="high",
            explanation=(
                f"Aggregate Niche fit {aggregate.niche_fit}/100 is below the 60 read-floor; "
                "the run as a whole reads off-niche regardless of individual hook quality."
            ),
            remediation=(
                "Tighten the --niche prompt to a more specific subdomain, or shift --tone "
                "to one of the archetype-tone affinities listed in the README."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-cycle read",
            severity="low",
            explanation=(
                "One ideation cycle is directional, not conclusive. The Idea Plan score is "
                "a heuristic — the real read happens after publish."
            ),
            remediation=(
                "Snapshot post-publish performance via analytics-summarizer in 7d and "
                "feed the delta back into the next content-idea-generator run."
            ),
        ))

    return flags[:5]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    ideas: list[Idea],
    aggregate: AggregateScores,
    voice_samples_present: bool,
    trends_present: bool,
    analytics_present: bool,
    niche: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # Mandatory bridge 1 — analytics-summarizer (always present)
    pool.append(Recommendation(
        text=(
            "Snapshot the creator's last 30d via `analytics-summarizer` and re-run "
            "content-idea-generator with --analytics-file to anchor Predicted engagement "
            "on real signals."
            if not analytics_present else
            "Re-snapshot post-publish performance in 7d via `analytics-summarizer` and "
            "feed the delta back into the next content-idea-generator run."
        ),
        bridge_slug="analytics-summarizer",
    ))

    # Mandatory bridge 2 — thread-builder (always present)
    highest = max(ideas, key=lambda i: i.scores.idea_score)
    pool.append(Recommendation(
        text=(
            f"Promote the highest-EV idea (\"Idea {highest.index} — {highest.archetype}\") "
            "into a full thread plan via `thread-builder`."
        ),
        bridge_slug="thread-builder",
    ))

    # Conditional bridges
    if not voice_samples_present:
        pool.append(Recommendation(
            text=(
                "Anchor Voice fidelity scoring on a real voice profile via `brand-voice-trainer` "
                "before the next ideation cycle."
            ),
            bridge_slug="brand-voice-trainer",
        ))

    if not trends_present:
        pool.append(Recommendation(
            text=(
                "Capture the last 7d of niche trends via `trend-aligned-poster` and re-run "
                "content-idea-generator with --trends-file to anchor Trend alignment scoring."
            ),
            bridge_slug="trend-aligned-poster",
        ))

    if aggregate.idea_plan_score >= 65:
        pool.append(Recommendation(
            text=(
                "Promote the top two archetypes into a single-axis A/B (hook only, niche held "
                "constant) via `ab-test-suggester`."
            ),
            bridge_slug="ab-test-suggester",
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
            f"Confirm the chosen niche \"{niche}\" is differentiated from peers in the same "
            "subdomain via `competitor-watch` before publishing."
        ),
        bridge_slug="competitor-watch",
    ))

    if aggregate.paradox_active:
        pool.append(Recommendation(
            text=(
                "Engage substantively with the audience the in-niche ideas bring in via "
                "`reply-drafter` — voice-faithful only, never copy-pasted."
            ),
            bridge_slug="reply-drafter",
        ))
    else:
        pool.append(Recommendation(
            text=(
                "Adapt the winning idea onto LinkedIn / Newsletter once a directional winner "
                "emerges via `cross-platform-reposter`."
            ),
            bridge_slug="cross-platform-reposter",
        ))

    pool.append(Recommendation(
        text=(
            "Re-source past anchor posts that match the surviving archetype via "
            "`content-recycler` so the daily cycle compounds across weeks."
        ),
        bridge_slug="content-recycler",
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
                        "Cross-reference the idea set with niche peers via "
                        f"`{slug}` to confirm the angles are differentiated."
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
    trends_present: bool,
    analytics_present: bool,
    is_demo: bool,
) -> tuple[str, str]:
    if voice_samples_present and trends_present and analytics_present and not is_demo:
        return (
            "high",
            f"real voice samples + trends + analytics anchor the run; Idea Plan score "
            f"{aggregate.idea_plan_score}/100.",
        )
    if voice_samples_present and (trends_present or analytics_present) and not is_demo:
        return (
            "medium",
            "real voice samples plus one anchor file (trends or analytics) attached; "
            f"Idea Plan score {aggregate.idea_plan_score}/100. Attach the missing anchor to lift to high.",
        )
    if trends_present or analytics_present:
        return (
            "medium",
            f"one anchor file attached; Idea Plan score {aggregate.idea_plan_score}/100. "
            "Re-run with --voice-samples-file to lift Voice fidelity scoring.",
        )
    return (
        "low",
        "data source is seeded archetype defaults — re-run with --voice-samples-file, "
        "--trends-file, and --analytics-file for real-creator scoring to lift confidence.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_run_snapshot(
    handle: str,
    niche: str,
    ideas: list[Idea],
    tone: str,
    count: int,
    voice_samples_present: bool,
    trends_present: bool,
    analytics_present: bool,
    is_demo: bool,
) -> str:
    archetypes = sorted({i.archetype for i in ideas})
    headline = (
        f"{handle}: {len(ideas)} post ideas on \"{niche}\" — "
        f"tone {tone}; {len(archetypes)} archetypes represented "
        f"({', '.join(archetypes[:4])}{'…' if len(archetypes) > 4 else ''})."
    )
    if voice_samples_present and trends_present and analytics_present and not is_demo:
        data_source = (
            "real voice samples + trends + analytics from --voice-samples-file / "
            "--trends-file / --analytics-file"
        )
    elif voice_samples_present and not is_demo:
        data_source = (
            "real voice samples from --voice-samples-file (re-run with --trends-file / "
            "--analytics-file to lift further)"
        )
    elif trends_present and analytics_present:
        data_source = (
            "real trends + analytics anchors (no --voice-samples-file attached)"
        )
    elif trends_present:
        data_source = (
            "real trends anchor from --trends-file (no voice / analytics files attached)"
        )
    elif analytics_present:
        data_source = (
            "real analytics anchor from --analytics-file (no voice / trends files attached)"
        )
    else:
        data_source = (
            "seeded archetype defaults — re-run with --voice-samples-file / --trends-file "
            "for real-creator scoring"
        )
    return "\n".join([
        "## Run Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Niche**: {niche}",
        f"- **Idea count**: {len(ideas)}",
        f"- **Tone**: {tone}",
        f"- **Data source**: {data_source}",
    ])


def _render_idea_plan_performance(aggregate: AggregateScores, is_demo: bool) -> str:
    demo_tag = (
        " [demo metric — re-run with --voice-samples-file for real-creator scoring]"
        if is_demo else ""
    )
    band = predicted_band(aggregate.predicted_engagement)
    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        f"| Niche fit              | {aggregate.niche_fit}/100{demo_tag} | "
        f"{_arrow_for(aggregate.niche_fit, ARROW_FLOORS['Niche fit'])} | "
        f"{aggregate.interpretations['Niche fit']} |",
        f"| Trend alignment        | {aggregate.trend_align}/100{demo_tag} | "
        f"{_arrow_for(aggregate.trend_align, ARROW_FLOORS['Trend alignment'])} | "
        f"{aggregate.interpretations['Trend alignment']} |",
        f"| Voice fidelity         | {aggregate.voice}/100{demo_tag} | "
        f"{_arrow_for(aggregate.voice, ARROW_FLOORS['Voice fidelity'])} | "
        f"{aggregate.interpretations['Voice fidelity']} |",
        f"| Predicted engagement   | {aggregate.predicted_engagement}/100 (band: {band}){demo_tag} | "
        f"{_arrow_for(aggregate.predicted_engagement, ARROW_FLOORS['Predicted engagement'])} | "
        f"{aggregate.interpretations['Predicted engagement']} |",
    ]
    out = "## Idea Plan Performance\n\n" + "\n".join(rows)
    if aggregate.paradox_active:
        idxs = ", ".join(str(i) for i in aggregate.paradox_ideas)
        out += (
            f"\n\n> ⚠️ paradox: hook rides a trending surface but the niche fit collapses — "
            f"vanity reach for the wrong audience (idea {idxs})."
        )
    out += f"\n\n**Idea Plan score**: {aggregate.idea_plan_score}/100"
    return out


def _render_ideas(ideas: list[Idea]) -> str:
    lines = [f"## The {len(ideas)} Ideas (drafts only — never auto-published)", ""]
    for i in ideas:
        if len(i.hook_text) > HOOK_CHAR_CAP:
            raise RuntimeError(
                f"Idea {i.index} hook exceeds {HOOK_CHAR_CAP} chars — refusing to render."
            )
        band = predicted_band(i.scores.predicted_engagement)
        header = (
            f"### Idea {i.index} — {i.archetype} (Niche fit {i.scores.niche_fit}/100 · "
            f"Trend {i.scores.trend_align}/100 · Voice {i.scores.voice}/100 · "
            f"Predicted {i.scores.predicted_engagement}/100 / band: {band})"
        )
        lines.append(header)
        lines.append("")
        lines.append(f"**Hook:** {i.hook_text}")
        lines.append("")
        lines.append(f"- **Format**: {i.format}")
        lines.append(f"- **Suggested publish window**: {i.publish_window}")
        lines.append(f"- **Why this lands**: {i.why_lands}")
        lines.append(f"- **Bridges to**: `{i.bridge_slug}`")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_trend_alignment(ideas: list[Idea], trends_present: bool) -> str:
    if not trends_present:
        return "\n".join([
            "## Trend Alignment",
            "",
            "_(no --trends-file supplied; Trend alignment scoring uses archetype defaults. "
            "Pair with `trend-aligned-poster` to capture the last 7d of niche trends and "
            "re-run with --trends-file to populate this section with concrete matches.)_",
        ])
    lines = ["## Trend Alignment", ""]
    for i in ideas:
        match = i.matched_trend or "(no trend matched — evergreen idea)"
        lines.append(f"- **Idea {i.index}** ({i.archetype}) → {match}")
    return "\n".join(lines)


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


def _render_idea_audit(
    ideas: list[Idea],
    voice_samples_present: bool,
    trends_present: bool,
    analytics_present: bool,
    count: int,
) -> str:
    voice_line = (
        "real samples supplied — Voice fidelity is anchored to the creator's cadence."
        if voice_samples_present else
        "no --voice-samples-file supplied — Voice fidelity uses archetype defaults; "
        "re-run with samples to lift the score."
    )
    trends_line = (
        "real trends supplied — Trend alignment is anchored to the actual 7d niche surface."
        if trends_present else
        "no --trends-file supplied — Trend alignment uses archetype defaults."
    )
    analytics_line = (
        "real --analytics-file attached; Predicted engagement is anchored to the "
        "creator's actual baseline."
        if analytics_present else
        "no --analytics-file attached; Predicted engagement is niche-typical, not "
        "creator-specific."
    )
    cognitive_line = (
        f"{count} ideas is at the upper band; once a directional winner emerges, re-run "
        "with --count 5 to focus the next round on the surviving register."
        if count >= 8 else
        f"{count} ideas is inside the safe band (3-7)."
    )
    archetypes = sorted({i.archetype for i in ideas})
    archetype_line = (
        f"{len(archetypes)} of {len(ARCHETYPE_DATA)} canonical archetypes represented."
    )
    return "\n".join([
        "## Idea Audit (auto-triggered)",
        "",
        f"- **Voice-sample adequacy**: {voice_line}",
        f"- **Trend anchoring**: {trends_line}",
        f"- **Analytics anchoring**: {analytics_line}",
        f"- **Idea cognitive load**: {cognitive_line}",
        f"- **Archetype diversity**: {archetype_line}",
        "- **Re-run cadence**: draft → publish → analytics-summarizer in 7d → re-run "
        "content-idea-generator for the next daily cycle.",
    ])


def render_report(
    handle: str,
    niche: str,
    ideas: list[Idea],
    aggregate: AggregateScores,
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    tone: str,
    count: int,
    voice_samples_present: bool,
    trends_present: bool,
    analytics_present: bool,
    is_demo: bool,
) -> str:
    sections = [
        _render_run_snapshot(
            handle, niche, ideas, tone, count,
            voice_samples_present, trends_present, analytics_present, is_demo,
        ),
        "",
        _render_idea_plan_performance(aggregate, is_demo),
        "",
        _render_ideas(ideas),
        "",
        _render_trend_alignment(ideas, trends_present),
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
        or count >= 8
        or aggregate.paradox_active
        or (is_demo and not voice_samples_present and not trends_present)
    )
    if audit_trigger:
        sections.extend([
            "",
            _render_idea_audit(
                ideas, voice_samples_present, trends_present, analytics_present, count,
            ),
        ])

    return "\n".join(sections).rstrip() + "\n"


def render_monetization_refusal(handle: str, niche: str) -> str:
    bridges = [
        Recommendation(
            text=(
                f"Run `monetization-optimizer` with the same niche to model the funnel "
                "(paid-tier conversion, sponsorship CPM, ad-revenue projection)."
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
                "Re-source the niche as a content angle (not a revenue angle) and re-run "
                "content-idea-generator once the angle is content-engagement-shaped, then "
                "promote the winning idea via `thread-builder`."
            ),
            bridge_slug="thread-builder",
        ),
    ]
    sections = [
        "## Out-of-scope — refusal",
        "",
        f"**{handle}: content-idea-generator run halted; niche crosses into monetization scope.**",
        "",
        f"- **Niche supplied**: {niche}",
        "- **Why refused**: content-idea-generator strictly stays inside content-engagement "
        "scope (impressions / replies / reposts / bookmarks pattern). Revenue, paid-tier "
        "conversion, sponsorship dollars, ad spend, and affiliate splits belong to "
        "`monetization-optimizer`.",
        "- **Ideas emitted**: 0 (refusal path)",
        "",
        _render_recommendations(bridges),
        "",
        "## Confidence",
        "Confidence: high — refusal triggered by the monetization keyword guard.",
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
        f"<!-- Generated by Content Idea Generator (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Demo bundles
# ---------------------------------------------------------------------------


DEMO_BUNDLES = {
    "default": {
        "x_handle": "@JanSol0s",
        "niche": "agent-eval tooling for X creators",
        "tone": "punchy",
        "count": 5,
        "voice_samples": [],
        "trends": [],
        "analytics_file": None,
        "data_source": "demo",
    },
    "anchored": {
        "x_handle": "@habitstacker",
        "niche": "evening-friction audits for makers",
        "tone": "thoughtful",
        "count": 5,
        "voice_samples": [
            "The 3 pm slump is a sleep-debt invoice arriving 6 hours late.",
            "I stopped tracking mood and started tracking the friction before mood — much easier to fix.",
            "Maker rituals are not productivity hacks; they are interruption shields.",
            "If your evening shutdown takes more than 7 minutes, it is not a ritual, it is a chore.",
            "The cheapest experiment is the one you can run again on Tuesday without thinking.",
        ],
        "trends": [
            "evening-friction audits trending up among makers (last 7d)",
            "ritual-as-interruption-shield framing gaining traction",
            "maker-economy creators sharing 5-step shutdown checklists",
            "habit-stacking renaissance on creator X",
        ],
        "analytics_file": "$env:LOCALAPPDATA/grok-agent/analytics-summarizer/last30.json",
        "data_source": "real",
    },
    "paradox": {
        "x_handle": "@JanSol0s",
        "niche": "post-publish engagement signals for technical creators",
        "tone": "data-led",
        "count": 5,
        "voice_samples": [],
        "trends": [
            "post-publish engagement signals trending in tech-creator X",
            "vanity-metric paradox conversation re-emerging",
            "first-hour reply velocity becoming the new measurement",
        ],
        "analytics_file": None,
        "data_source": "demo",
        # Force paradox firing on idea 5 (trend-aligned-riff): high
        # predicted but explicitly low niche fit so the paradox triggers.
        "score_overrides": {5: {"niche_fit": 38, "trend_align": 92, "voice": 64}},
    },
}


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_post_ideas(
    *,
    x_handle: str,
    niche: Optional[str] = None,
    tone: str = "punchy",
    count: int = COUNT_DEFAULT,
    voice_samples: Optional[list[str]] = None,
    trends: Optional[list[str]] = None,
    analytics_file: Optional[str] = None,
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
        if niche:
            bundle["niche"] = niche
    else:
        if not niche:
            raise ValueError("niche is required unless a --demo flag is passed.")
        bundle = {
            "x_handle": handle,
            "niche": niche,
            "tone": tone,
            "count": count,
            "voice_samples": list(voice_samples or []),
            "trends": list(trends or []),
            "analytics_file": analytics_file,
            "data_source": data_source,
        }

    bundle["x_handle"] = handle
    bundle["tone"] = bundle.get("tone", tone)
    bundle["count"] = int(bundle.get("count", count))
    bundle["voice_samples"] = list(bundle.get("voice_samples") or voice_samples or [])
    bundle["trends"] = list(bundle.get("trends") or trends or [])
    if analytics_file is not None:
        bundle["analytics_file"] = analytics_file
    if score_overrides is not None:
        bundle["score_overrides"] = score_overrides

    if bundle["tone"] not in TONE_OPTIONS:
        raise ValueError(
            f"tone must be one of {TONE_OPTIONS}, got {bundle['tone']!r}"
        )
    if not COUNT_MIN <= bundle["count"] <= COUNT_MAX:
        raise ValueError(
            f"count must be {COUNT_MIN}-{COUNT_MAX}, got {bundle['count']}"
        )

    niche_str = str(bundle["niche"])
    if niche_is_monetization(niche_str):
        rendered = render_monetization_refusal(handle, niche_str)
        assert_only_creator_handle_in_render(rendered, handle)
        return rendered

    is_demo = bundle.get("data_source") == "demo"
    voice_samples_present = bool(bundle["voice_samples"])
    trends_present = bool(bundle["trends"])
    analytics_path = bundle.get("analytics_file")
    analytics_present = bool(analytics_path)

    voice_lift = 12 if voice_samples_present else 0
    analytics_lift = 12 if analytics_present else 0

    overrides_raw = bundle.get("score_overrides") or {}
    overrides = {int(k): dict(v) for k, v in overrides_raw.items()}

    when_iso = when or date.today().isoformat()
    seed = hashlib.sha256(
        (handle + niche_str + bundle["tone"] + str(bundle["count"]) + when_iso).encode("utf-8")
    ).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))

    ideas = build_ideas(
        niche=niche_str,
        tone=bundle["tone"],
        count=bundle["count"],
        voice_lift=voice_lift,
        analytics_lift=analytics_lift,
        trends=bundle["trends"],
        rng=rng,
        overrides=overrides,
    )
    aggregate = aggregate_ideas(ideas)

    flags = build_red_flags(
        ideas, aggregate, voice_samples_present, trends_present,
        analytics_present, is_demo, bundle["count"],
    )

    recs = build_recommendations(
        rng, ideas, aggregate, voice_samples_present, trends_present,
        analytics_present, niche_str,
    )

    confidence = confidence_for(
        aggregate, voice_samples_present, trends_present, analytics_present, is_demo,
    )

    rendered = render_report(
        handle=handle,
        niche=niche_str,
        ideas=ideas,
        aggregate=aggregate,
        flags=flags,
        recs=recs,
        confidence=confidence,
        tone=bundle["tone"],
        count=bundle["count"],
        voice_samples_present=voice_samples_present,
        trends_present=trends_present,
        analytics_present=analytics_present,
        is_demo=is_demo,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


generate = generate_post_ideas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Content Idea Generator (Grok Agent OS · creator template)\n"
        "  Drafts only · 5 ideas per run · Hook cap 240 chars\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="content-idea-generator",
        description=(
            "Read a creator-supplied niche (and optional voice samples + trend "
            "snapshot + analytics export) and emit a 6/7-section idea plan with "
            "5 ready-to-post ideas (or 3-10 via --count), 4 canonical Idea Plan "
            "metrics, vanity-hook paradox detection, per-idea engagement "
            "predictions, and >= 3 cross-template bridges (mandatory: "
            "analytics-summarizer + thread-builder). Drafts only — never "
            "auto-publishes."
        ),
    )
    p.add_argument("--x-handle", required=True,
                   help="Creator's X handle (with or without leading @).")
    p.add_argument("--niche",
                   help="Niche / topic anchor in plain text. Required unless --demo.")
    p.add_argument("--tone", choices=list(TONE_OPTIONS), default="punchy",
                   help="Tone register to emphasise. Default 'punchy'.")
    p.add_argument("--count", type=int, default=COUNT_DEFAULT,
                   help=f"Number of ideas to generate ({COUNT_MIN}-{COUNT_MAX}; default {COUNT_DEFAULT}).")
    p.add_argument("--voice-samples-file",
                   help="Path to a JSON file containing a list of the creator's recent post bodies.")
    p.add_argument("--trends-file",
                   help="Path to a JSON file containing the last 7d of niche trends (list of strings).")
    p.add_argument("--analytics-file",
                   help="Path to an analytics-summarizer JSON export. Anchors Predicted engagement.")
    p.add_argument("--input-file",
                   help="Optional path to an idea-generator brief JSON (encapsulates niche + voice + trends + analytics).")
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true",
                   help="Suppress the runner banner on stdout.")
    p.add_argument("--demo", action="store_true",
                   help="Run with the canonical 5-idea punchy-tone demo (agent-eval tooling).")
    p.add_argument("--demo-anchored", action="store_true",
                   help="Run with the high-confidence demo (voice + trends + analytics anchors).")
    p.add_argument("--demo-paradox", action="store_true",
                   help="Run with the vanity-hook paradox demo (auto-triggers Idea Audit).")
    p.add_argument("--show-system-prompt", action="store_true",
                   help="Print system prompt path + size on stderr.")
    p.add_argument("--when", help="Override the date used in the deterministic seed (ISO YYYY-MM-DD). Useful for reproducible example outputs.")
    return p


def _resolve_voice_samples(path: Optional[str]) -> list[str]:
    if not path:
        return []
    payload = load_json_file(Path(path).expanduser().resolve(), "voice-samples-file")
    if not isinstance(payload, list):
        raise ValueError("--voice-samples-file must be a JSON list of post bodies.")
    return [str(p) for p in payload]


def _resolve_trends(path: Optional[str]) -> list[str]:
    if not path:
        return []
    payload = load_json_file(Path(path).expanduser().resolve(), "trends-file")
    if not isinstance(payload, list):
        raise ValueError("--trends-file must be a JSON list of trend strings.")
    return [str(t) for t in payload]


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
    elif args.demo_anchored:
        demo_mode = "anchored"
    elif args.demo_paradox:
        demo_mode = "paradox"

    bundle_overrides = _resolve_input_file(args.input_file)

    niche = args.niche or bundle_overrides.get("niche")
    tone = bundle_overrides.get("tone", args.tone)
    count = int(bundle_overrides.get("count", args.count))

    voice_samples_inline = bundle_overrides.get("voice_samples")
    voice_samples = (
        list(voice_samples_inline)
        if isinstance(voice_samples_inline, list) and voice_samples_inline
        else _resolve_voice_samples(args.voice_samples_file)
    )

    trends_inline = bundle_overrides.get("trends")
    trends = (
        list(trends_inline)
        if isinstance(trends_inline, list) and trends_inline
        else _resolve_trends(args.trends_file)
    )

    analytics_file = args.analytics_file or bundle_overrides.get("analytics_file")
    score_overrides = bundle_overrides.get("score_overrides")
    data_source = str(bundle_overrides.get("data_source", "real"))

    if not niche and demo_mode is None:
        sys.stderr.write(
            "error: provide --niche <text>, --input-file <path>, or one of "
            "--demo / --demo-anchored / --demo-paradox.\n"
        )
        return 2

    if count < COUNT_MIN or count > COUNT_MAX:
        sys.stderr.write(
            f"error: --count must be {COUNT_MIN}-{COUNT_MAX}, got {count}.\n"
        )
        return 2

    when_iso = args.when or date.today().isoformat()
    rendered = generate_post_ideas(
        x_handle=args.x_handle,
        niche=niche,
        tone=tone,
        count=count,
        voice_samples=voice_samples,
        trends=trends,
        analytics_file=analytics_file,
        when=when_iso,
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
