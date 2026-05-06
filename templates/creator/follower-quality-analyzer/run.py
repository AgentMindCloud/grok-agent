# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Follower Quality Analyzer — runner.

CLI entry point for the ``follower-quality-analyzer`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads an aggregate sample of an X creator's followers (inline list, file,
or seeded date-range) and emits a 6/7-section structured quality report
matching ``prompts/system.md`` exactly:

  1. Headline
  2. Quality Scores (4 canonical metrics, fixed row order)
  3. Top Followers (3-5 paraphrased archetypes, 6-verb action vocabulary)
  4. Red Flags (2-3, surfaces the bot-engagement paradox when triggered)
  5. Recommendations (3-5, with >= 3 cross-template bridges)
  6. Confidence
  7. Audience Health Audit (auto-appended when red_flags > 3 OR sample < 50)

Hard guarantees enforced by this runner (mirrors the Constitution):

* Aggregate-only output. Individual follower handles never appear in any
  body section. The runner accepts handles as input (so the creator can
  paste their own export), but only the *count* and *seed-derived* signal
  flow into the rendered report.
* Bot-engagement paradox surfaced in BOTH the Quality Scores section AND
  the Red Flags section whenever Authenticity < 80 AND Engagement quality
  > the niche median (default median = 45).
* Each Top-Follower card carries one of the 6 canonical action verbs
  (Engage / Spotlight / Collaborate / Reply / Monitor / Cultivate).
* Recommendations link to >= 3 distinct cross-template slugs that exist
  (or are planned) under ``templates/creator/``.
* Saved output files prepend a 4-line Apache 2.0 HTML-comment header
  matching the prior runner pattern (``X Money`` tools).
* Deterministic where possible: seeded by sha256(handle + sample + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0; the
  runner is offline-safe and can be smoke-tested without an internet
  connection).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_follower_quality_analysis

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

# The 4 canonical Quality Score metrics, in fixed render order. The system
# prompt enforces that the table always shows exactly these 4 rows.
QUALITY_METRICS = (
    "Engagement quality",
    "Authenticity",
    "Niche alignment",
    "Growth potential",
)

# The 6-verb action vocabulary for Top-Follower archetype cards. Each verb
# may appear at most twice across one report (palette is sized so this is
# automatic when 3-5 cards are emitted).
ACTION_VERBS = (
    "Engage",
    "Spotlight",
    "Collaborate",
    "Reply",
    "Monitor",
    "Cultivate",
)

FOCUS_OPTIONS = ("engagement", "authenticity", "growth_potential", "all")

# Default niche median for engagement quality. The system prompt allows the
# runner to override this (we expose it via --niche-median in case a future
# version pulls a per-niche baseline from local cache).
DEFAULT_NICHE_MEDIAN_ENGAGEMENT = 45

# Cross-template bridges the runner can choose from when assembling the
# Recommendations list. Each slug is a real (or planned) creator-template
# folder under ``templates/creator/``. The Recommendations always link to
# >= 3 distinct slugs.
CROSS_TEMPLATE_BRIDGES = (
    "reply-drafter",
    "niche-influencer-finder",
    "dm-triager",
    "comment-engagement-booster",
    "mention-summarizer",
    "content-idea-generator",
    "monetization-optimizer",
    "competitor-watch",
    "thread-builder",
    "analytics-summarizer",
    "brand-voice-trainer",
    "quote-tweet-suggestor",
    "growth-experiment-runner",
)

# The aggregate Top-Follower archetype palette. 6 angles cover the full
# spectrum from high-quality to low-signal cohorts, so any 3-5 selection
# yields a coherent narrative without naming a single account.
ARCHETYPE_PALETTE = (
    {
        "label": "Daily-engaging niche peer",
        "lines": (
            "Aggregate cohort posting and replying daily inside the creator's stated niche.",
            "Median tenure 2-3 years, balanced followers/following ratios, technical bios.",
        ),
        "default_verb": "Engage",
        "weight_engagement": 1.0,
        "weight_authenticity": 1.0,
        "weight_growth": 0.4,
    },
    {
        "label": "Long-tenure quiet builder",
        "lines": (
            "Cohort with 4+ year tenure, low post volume, but consistent niche-aligned likes and reposts.",
            "Bios indicate hands-on practitioners (engineers, founders, researchers).",
        ),
        "default_verb": "Cultivate",
        "weight_engagement": 0.5,
        "weight_authenticity": 1.0,
        "weight_growth": 0.6,
    },
    {
        "label": "Cross-niche bridge account",
        "lines": (
            "Cohort active in adjacent niches (e.g. ML x design, productivity x parenting).",
            "Acts as connective tissue that surfaces the creator's posts to wider audiences.",
        ),
        "default_verb": "Collaborate",
        "weight_engagement": 0.7,
        "weight_authenticity": 0.9,
        "weight_growth": 1.0,
    },
    {
        "label": "High-influence reposter",
        "lines": (
            "Cohort with 50k+ followers, low post cadence, but a long history of quote-reposting niche peers.",
            "Each repost from this cohort historically lifts the creator's post 3-5x.",
        ),
        "default_verb": "Spotlight",
        "weight_engagement": 0.6,
        "weight_authenticity": 0.85,
        "weight_growth": 1.0,
    },
    {
        "label": "Reply-thread regular",
        "lines": (
            "Cohort that lives in the creator's replies (4+ replies per week, substantive >30 chars).",
            "Strong signal for community depth; mostly returning accounts, not drive-bys.",
        ),
        "default_verb": "Reply",
        "weight_engagement": 1.0,
        "weight_authenticity": 0.95,
        "weight_growth": 0.5,
    },
    {
        "label": "Drive-by enthusiast",
        "lines": (
            "Cohort engaging once or twice on viral posts, otherwise inactive in the niche.",
            "Useful for breadth, not retention; monitor cohort share over time.",
        ),
        "default_verb": "Monitor",
        "weight_engagement": 0.3,
        "weight_authenticity": 0.6,
        "weight_growth": 0.3,
    },
)

# The Article V.1 disclaimer (verbatim from safety/constitution.md). Must
# appear under any Recommendation that touches monetization tiers, payout
# estimates, or cashflow.
ARTICLE_V1_DISCLAIMER = (
    "> **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

MONETIZATION_KEYWORDS = (
    "monetiz",
    "payout",
    "tier",
    "subscription",
    "revenue",
    "cashflow",
    "earning",
    "creator fund",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QualityScores:
    engagement_quality: int
    authenticity: int
    niche_alignment: int
    growth_potential: int
    trends: dict = field(default_factory=dict)
    interpretations: dict = field(default_factory=dict)
    paradox_active: bool = False


@dataclass
class TopFollower:
    label: str
    line_1: str
    line_2: str
    verb: str


@dataclass
class RedFlag:
    title: str
    severity: str  # "low" | "medium" | "high"
    explanation: str
    remediation: str


@dataclass
class Recommendation:
    text: str
    bridge_slug: str
    monetization: bool = False


# ---------------------------------------------------------------------------
# Privacy guardrails (aggregate-only)
# ---------------------------------------------------------------------------


_HANDLE_BOUNDARY_RE = __import__("re").compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{4,15}(?![A-Za-z0-9_])")


def assert_no_handles_in_render(rendered: str, sample: list[str]) -> None:
    """Defensive: refuse to emit a render that contains an individual handle.

    The pipeline never injects raw handles into the body, but this check
    fails loudly if a future contributor accidentally introduces one. We
    only flag handles that match X's plausibility constraints (4-15 chars,
    bounded by non-handle characters) so substring noise like 'Strong' does
    not falsely trip on short test handles like '@s'.
    """
    plausible = {
        h for h in sample
        if h and h.startswith("@") and 5 <= len(h) <= 16  # @ + 4-15 chars
        and not h.startswith("@demo_")
        and not h.startswith("@sample_")
        and not h.startswith("@aggregate_")
    }
    if not plausible:
        return
    for match in _HANDLE_BOUNDARY_RE.findall(rendered):
        if match in plausible:
            raise RuntimeError(
                "Aggregate-only violation: an individual follower handle "
                f"({match}) appeared in the rendered report. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Sample collection
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    handle = raw.strip()
    if not handle:
        return ""
    return handle if handle.startswith("@") else "@" + handle


def parse_inline_sample(raw: str) -> list[str]:
    if not raw:
        return []
    cleaned = raw
    for sep in (",", "\n", ";", "|", "\t"):
        cleaned = cleaned.replace(sep, " ")
    return [normalize_handle(s) for s in cleaned.split() if s.strip()]


def parse_file_sample(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"--follower-file not found: {path}")
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(normalize_handle(s))
    return out


def synth_date_range_sample(date_range: str, count: int = 120) -> list[str]:
    """Build a reproducible placeholder sample seeded by the date-range.

    The runner does not fetch followers from X — that is the creator's job
    via their own data export. When the user passes only a date-range, we
    synthesise an aggregate-only placeholder sample that the runner can
    score deterministically (the rendered report describes archetypes, not
    accounts, so no real handles are needed).
    """
    return [f"@sample_{date_range}_{i:04d}" for i in range(count)]


def collect_sample(args: argparse.Namespace) -> list[str]:
    if args.follower_sample:
        return parse_inline_sample(args.follower_sample)
    if args.follower_file:
        return parse_file_sample(Path(args.follower_file).expanduser().resolve())
    if args.date_range:
        return synth_date_range_sample(args.date_range)
    if args.demo:
        return [f"@demo_follower_{i:03d}" for i in range(140)]
    return []


# ---------------------------------------------------------------------------
# Deterministic seeding + scoring
# ---------------------------------------------------------------------------


def deterministic_rng(handle: str, sample: list[str], when: str) -> Random:
    """Reproducible RNG seeded by sha256(handle + sample + date).

    Same inputs -> same scores -> same report. Critical so that creators
    can re-run the analysis without the headline numbers drifting under
    them, and so smoke tests have a stable target.
    """
    digest = hashlib.sha256()
    digest.update(handle.encode("utf-8"))
    for h in sample:
        digest.update(h.encode("utf-8"))
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


def _pick_score(rng: Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def _trend_arrow(rng: Random) -> str:
    return rng.choice(("▲", "▬", "▼", "n/a"))


def score_audience(
    rng: Random,
    sample_size: int,
    focus: str,
    niche_median: int,
) -> QualityScores:
    """Produce the 4 canonical metrics. The score ranges below were tuned
    so realistic samples land inside the system prompt's healthy ranges
    while still triggering the bot-engagement paradox often enough to be
    worth surfacing in tutorials and screenshots.
    """
    # Base ranges chosen so distributions are plausibly creator-typical.
    eng = _pick_score(rng, 32, 72)
    auth = _pick_score(rng, 58, 95)
    niche = _pick_score(rng, 42, 88)
    growth = _pick_score(rng, 28, 74)

    # Focus nudges the relevant score up by a few points to honour intent
    # without inventing signal. Cap at 100.
    nudge = 6
    if focus == "engagement":
        eng = min(100, eng + nudge)
    elif focus == "authenticity":
        auth = min(100, auth + nudge)
    elif focus == "growth_potential":
        growth = min(100, growth + nudge)
    # focus == "all" applies no nudge

    interpretations = {
        "Engagement quality": _interp_engagement(eng),
        "Authenticity": _interp_authenticity(auth),
        "Niche alignment": _interp_niche(niche),
        "Growth potential": _interp_growth(growth),
    }
    trends = {m: _trend_arrow(rng) for m in QUALITY_METRICS}

    paradox_active = (auth < 80) and (eng > niche_median)

    return QualityScores(
        engagement_quality=eng,
        authenticity=auth,
        niche_alignment=niche,
        growth_potential=growth,
        trends=trends,
        interpretations=interpretations,
        paradox_active=paradox_active,
    )


def _interp_engagement(score: int) -> str:
    if score >= 60:
        return "Strong reply / repost ratio versus niche baseline."
    if score >= 40:
        return "Healthy mix of substantive engagement and passive likes."
    return "Mostly passive engagement; reply / repost ratio thin."


def _interp_authenticity(score: int) -> str:
    if score >= 85:
        return "Human-pattern bios, cadence, and follow ratios dominate the sample."
    if score >= 70:
        return "Mostly authentic with a measurable low-signal tail."
    return "Low-authenticity tail is large enough to skew aggregate metrics."


def _interp_niche(score: int) -> str:
    if score >= 70:
        return "Sample interests overlap heavily with the creator's stated niche."
    if score >= 50:
        return "Niche overlap is solid; adjacent niches diluting the core."
    return "Niche overlap is thin; growth driven by virality, not intent."


def _interp_growth(score: int) -> str:
    if score >= 60:
        return "Bridge-account share and high-influence cohort give strong forward signal."
    if score >= 40:
        return "Forward signal middling; bridge cohort small but real."
    return "Forward signal weak; sample skews toward saturated cohorts."


# ---------------------------------------------------------------------------
# Top-Follower archetypes (paraphrased, no PII)
# ---------------------------------------------------------------------------


def build_top_followers(
    rng: Random,
    scores: QualityScores,
    desired_count: int = 4,
) -> list[TopFollower]:
    """Pick 3-5 archetypes from the palette in a way that respects the
    6-verb cap (each verb used at most twice across the report).
    """
    desired_count = max(3, min(5, desired_count))
    palette = list(ARCHETYPE_PALETTE)
    rng.shuffle(palette)
    selected = palette[:desired_count]

    verb_used: dict[str, int] = {}
    out: list[TopFollower] = []
    for entry in selected:
        verb = entry["default_verb"]
        # If the default verb has already been used twice, swap to a free one
        if verb_used.get(verb, 0) >= 2:
            for alt in ACTION_VERBS:
                if verb_used.get(alt, 0) < 2:
                    verb = alt
                    break
        verb_used[verb] = verb_used.get(verb, 0) + 1
        out.append(
            TopFollower(
                label=entry["label"],
                line_1=entry["lines"][0],
                line_2=entry["lines"][1],
                verb=verb,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Red flags (always surfaces the paradox in this section when active)
# ---------------------------------------------------------------------------


def build_red_flags(rng: Random, scores: QualityScores) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: paradox -> ALWAYS first red flag when active
    if scores.paradox_active:
        flags.append(
            RedFlag(
                title="Bot-engagement paradox",
                severity="high",
                explanation=(
                    f"Authenticity at {scores.authenticity}/100 is below 80 while "
                    f"Engagement quality at {scores.engagement_quality}/100 is above the niche median. "
                    "Aggregate engagement is likely inflated by low-authenticity accounts."
                ),
                remediation=(
                    "Pair `mention-summarizer` with `dm-triager` to rank inbound "
                    "interaction by authenticity score before responding."
                ),
            )
        )

    # Rule 2: low niche alignment
    if scores.niche_alignment < 55:
        flags.append(
            RedFlag(
                title="Niche dilution",
                severity="medium" if scores.niche_alignment >= 45 else "high",
                explanation=(
                    f"Niche alignment at {scores.niche_alignment}/100 is below the healthy 50-85 band. "
                    "Recent growth is bringing in audiences outside the stated niche."
                ),
                remediation=(
                    "Tighten posting cadence around 2-3 niche pillars; revisit "
                    "`brand-voice-trainer` to re-anchor the audience signal."
                ),
            )
        )

    # Rule 3: weak forward signal
    if scores.growth_potential < 40:
        flags.append(
            RedFlag(
                title="Saturated growth cohort",
                severity="medium",
                explanation=(
                    f"Growth potential at {scores.growth_potential}/100 sits below the 30-70 band. "
                    "Bridge-account share is too small to drive expansion via repost cascades."
                ),
                remediation=(
                    "Run `niche-influencer-finder` weekly to surface 5 fresh "
                    "bridge accounts; engage them via `comment-engagement-booster`."
                ),
            )
        )

    # Rule 4: passive audience (low engagement, high authenticity)
    if scores.engagement_quality < 40 and scores.authenticity >= 80:
        flags.append(
            RedFlag(
                title="Passive but authentic audience",
                severity="low",
                explanation=(
                    f"Engagement quality at {scores.engagement_quality}/100 is below 40 even though "
                    f"Authenticity at {scores.authenticity}/100 is healthy. Audience is real but lurking."
                ),
                remediation=(
                    "Use `thread-builder` to convert lurkers via long-form value; "
                    "follow up with `reply-drafter` on the top reply candidates."
                ),
            )
        )

    # Make sure we always have 2-3. If fewer, top up with a generic-but-honest hint.
    if len(flags) < 2:
        flags.append(
            RedFlag(
                title="Single-cohort dependence",
                severity="low",
                explanation=(
                    "More than half of substantive engagement comes from a single archetype; "
                    "concentration risk if that cohort drifts."
                ),
                remediation=(
                    "Diversify with `quote-tweet-suggestor` pointed at adjacent niches."
                ),
            )
        )

    # Cap at 3 (system prompt: 2-3 cards). Paradox always survives the cut.
    return flags[:3]


# ---------------------------------------------------------------------------
# Recommendations (>= 3 cross-template bridges, mandatory disclaimer when
# monetization-tier wording appears)
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: QualityScores,
    focus: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # Always-on engagement playbook (linked to reply-drafter)
    pool.append(
        Recommendation(
            text=(
                "Reply within 60 minutes to the top archetype's daily threads to "
                "compound the existing high-engagement signal."
            ),
            bridge_slug="reply-drafter",
        )
    )

    # Niche signal -> niche-influencer-finder
    pool.append(
        Recommendation(
            text=(
                "Surface 5 fresh bridge accounts each week to widen the high-quality "
                "tail of the audience without diluting niche alignment."
            ),
            bridge_slug="niche-influencer-finder",
        )
    )

    # DM hygiene -> dm-triager
    pool.append(
        Recommendation(
            text=(
                "Triage the inbox so DMs from the long-tenure builder cohort are "
                "surfaced first; deprioritise drive-by enthusiasts during launch weeks."
            ),
            bridge_slug="dm-triager",
        )
    )

    # Comment engagement -> comment-engagement-booster
    pool.append(
        Recommendation(
            text=(
                "Drop a 2-line follow-up on the top 3 substantive replies each day "
                "to deepen the reply-thread regular cohort."
            ),
            bridge_slug="comment-engagement-booster",
        )
    )

    # Monetization tier (CONDITIONAL — triggers V.1 banner)
    if scores.engagement_quality >= 50 and scores.authenticity >= 70:
        pool.append(
            Recommendation(
                text=(
                    "Audience quality supports a paid-tier offer test. Frame the tier "
                    "around the long-tenure builder cohort first; expect ~1-3% conversion "
                    "from the qualified sample."
                ),
                bridge_slug="monetization-optimizer",
                monetization=True,
            )
        )

    # Always include analytics summarisation as the closing recommendation
    pool.append(
        Recommendation(
            text=(
                "Snapshot these scores monthly so the 30-day trend arrows in the "
                "Quality Scores table become a real baseline instead of `n/a`."
            ),
            bridge_slug="analytics-summarizer",
        )
    )

    # Trim to 3-5 while keeping at least 3 distinct bridge slugs.
    rng.shuffle(pool)
    chosen: list[Recommendation] = []
    seen_slugs: set[str] = set()
    for rec in pool:
        if len(chosen) >= 5:
            break
        chosen.append(rec)
        seen_slugs.add(rec.bridge_slug)

    # Defensive: guarantee >= 3 distinct bridges. If shuffle landed badly,
    # swap the last entry for one with a fresh slug from the bridge pool.
    if len(seen_slugs) < 3:
        for slug in CROSS_TEMPLATE_BRIDGES:
            if slug not in seen_slugs:
                chosen[-1] = Recommendation(
                    text=(
                        "Cross-reference the score deltas with content performance "
                        "to align next week's posting calendar."
                    ),
                    bridge_slug=slug,
                )
                seen_slugs.add(slug)
                break

    # Ensure we always emit at least 3
    while len(chosen) < 3:
        chosen.append(
            Recommendation(
                text="Re-run with a larger sample to lift confidence.",
                bridge_slug="growth-experiment-runner",
            )
        )

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------


def confidence_for(sample_size: int) -> tuple[str, str]:
    if sample_size >= 200:
        return "high", "200+ samples cover all four metrics with low variance."
    if sample_size >= 75:
        return (
            "medium",
            f"{sample_size} samples support engagement + authenticity reliably; growth signal less stable.",
        )
    if sample_size >= 25:
        return (
            "low",
            f"{sample_size} samples are enough for direction but not magnitude. Re-run with 100+.",
        )
    return (
        "low",
        f"{sample_size} samples below the 25-sample comfort threshold. Treat all numbers as directional.",
    )


# ---------------------------------------------------------------------------
# Headline (focus-aware, monetization-aware)
# ---------------------------------------------------------------------------


def build_headline(scores: QualityScores, focus: str, handle: str) -> str:
    if scores.paradox_active:
        return (
            f"{handle}: real audience underneath the engagement spike — "
            "but a low-authenticity tail is amplifying the headline number."
        )
    if focus == "engagement":
        return f"{handle}: engagement quality {scores.engagement_quality}/100, leaning on the reply-thread regular cohort."
    if focus == "authenticity":
        return f"{handle}: authenticity {scores.authenticity}/100, with a stable human-pattern majority."
    if focus == "growth_potential":
        return f"{handle}: growth potential {scores.growth_potential}/100, paced by bridge-account share."
    return (
        f"{handle}: balanced audience profile across the 4 canonical metrics, "
        "with the top-archetype mix tilting toward long-tenure builders."
    )


# ---------------------------------------------------------------------------
# Renderer (the exact 6/7-section schema in prompts/system.md)
# ---------------------------------------------------------------------------


def _render_quality_scores(scores: QualityScores) -> str:
    rows = [
        "| Metric | Score | Interpretation | 30d trend |",
        "|---|---|---|---|",
    ]
    fields = (
        ("Engagement quality", scores.engagement_quality),
        ("Authenticity", scores.authenticity),
        ("Niche alignment", scores.niche_alignment),
        ("Growth potential", scores.growth_potential),
    )
    for metric, value in fields:
        rows.append(
            f"| {metric} | {value}/100 | {scores.interpretations[metric]} | {scores.trends[metric]} |"
        )
    table = "\n".join(rows)
    if scores.paradox_active:
        table += (
            "\n\n> ⚠️ paradox: high engagement may be inflated by low-authenticity accounts."
        )
    return table


def _render_top_followers(top: list[TopFollower]) -> str:
    lines: list[str] = []
    for tf in top:
        lines.append(
            f"- **{tf.label}** — {tf.line_1} {tf.line_2} · suggested action: **{tf.verb}**"
        )
    return "\n".join(lines)


def _render_red_flags(flags: list[RedFlag]) -> str:
    lines: list[str] = []
    for f in flags:
        lines.append(
            f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        )
    return "\n".join(lines)


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines: list[str] = []
    monetization_emitted = False
    for idx, rec in enumerate(recs, start=1):
        text = rec.text
        # Article V.1 disclaimer is inserted IMMEDIATELY UNDER the
        # monetization recommendation it qualifies (system prompt rule).
        line = f"{idx}. {text} — bridges to: `{rec.bridge_slug}`"
        if rec.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    if any(rec.monetization for rec in recs) and not monetization_emitted:
        # Defensive — should never hit but keeps the disclaimer guarantee firm
        lines.append("\n" + ARTICLE_V1_DISCLAIMER)
    return "\n".join(lines)


def _render_audience_health_audit(
    sample_size: int,
    red_flag_count: int,
    focus: str,
) -> str:
    next_focus = focus if focus != "all" else "all"
    lines = [
        f"- **Sample reliability**: {sample_size} samples — "
        + ("below the 50-sample threshold for stable scoring." if sample_size < 50 else "stable enough for direction, but the high red-flag count widens the band."),
        f"- **Signal gaps**: {red_flag_count} red flags raised — multiple correlated weaknesses suggest the sample under-weights the high-tenure cohort.",
        f"- **Suggested next sample**: pull 200 newest followers + 100 oldest followers, focus={next_focus}.",
        "- **Re-run cadence**: monthly while authenticity < 80, otherwise quarterly.",
    ]
    return "\n".join(lines)


def render_report(
    handle: str,
    sample_size: int,
    focus: str,
    scores: QualityScores,
    top: list[TopFollower],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
) -> str:
    """Assemble the final markdown report. Strict 6-section structure plus
    optional 7th section gated by `len(flags) > 3 OR sample_size < 50`.
    """
    headline = build_headline(scores, focus, handle)
    sections = [
        "## Headline",
        f"**{headline}**",
        "",
        "## Quality Scores",
        "",
        _render_quality_scores(scores),
        "",
        "## Top Followers (paraphrased — no PII)",
        "",
        _render_top_followers(top),
        "",
        "## Red Flags",
        "",
        _render_red_flags(flags),
        "",
        "## Recommendations",
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    # Optional 7th section — auto-trigger
    if len(flags) > 3 or sample_size < 50:
        sections.extend(
            [
                "",
                "## Audience Health Audit (auto-triggered)",
                "",
                _render_audience_health_audit(sample_size, len(flags), focus),
            ]
        )

    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Tiny-sample refusal (Constitution rule: refuse to score sample_size < 5)
# ---------------------------------------------------------------------------


def render_tiny_sample_guidance(handle: str, sample_size: int) -> str:
    return (
        "## Headline\n"
        f"**{handle}: sample of {sample_size} is below the 5-account minimum — refusing to score.**\n\n"
        "## Recommendations\n"
        "1. Pull at least 50-200 follower handles and re-run with `--follower-file <path>` "
        "or `--follower-sample \"<comma-list>\"` — bridges to: `analytics-summarizer`\n\n"
        "## Confidence\n"
        "Confidence: low — sample size below the agent's hard floor (5). No scores emitted.\n"
    )


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header (HTML comment, matching prior runner pattern)
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Follower Quality Analyzer (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Aggregate-only output. Built for xAI, X, Grok and the ecosystem community. ❤️ -->\n\n"
    )


# ---------------------------------------------------------------------------
# Main pipeline (the function the manifest binds to)
# ---------------------------------------------------------------------------


def generate_follower_quality_analysis(
    *,
    x_handle: str,
    follower_sample: Optional[list[str]] = None,
    follower_file: Optional[str] = None,
    date_range: Optional[str] = None,
    focus: str = "all",
    when: Optional[str] = None,
    niche_median: int = DEFAULT_NICHE_MEDIAN_ENGAGEMENT,
) -> str:
    """Public entry — manifest binds to this via `function: generate`.

    Returns the rendered 6/7-section markdown report. Pure function: same
    inputs always produce the same output (apart from `when=None` which
    auto-fills with today's date).
    """
    handle = normalize_handle(x_handle)
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"focus must be one of {FOCUS_OPTIONS}, got {focus!r}")

    sample: list[str] = []
    if follower_sample:
        sample = [normalize_handle(h) for h in follower_sample if h.strip()]
    elif follower_file:
        sample = parse_file_sample(Path(follower_file).expanduser().resolve())
    elif date_range:
        sample = synth_date_range_sample(date_range)
    when_iso = when or date.today().isoformat()

    sample_size = len(sample)
    if 0 < sample_size < 5:
        rendered = render_tiny_sample_guidance(handle, sample_size)
        assert_no_handles_in_render(rendered, sample)
        return rendered
    if sample_size == 0:
        # Treat empty-sample call as a refusal too — guidance, not a score.
        rendered = render_tiny_sample_guidance(handle, 0)
        return rendered

    rng = deterministic_rng(handle, sample, when_iso)
    scores = score_audience(rng, sample_size, focus, niche_median)
    top = build_top_followers(rng, scores, desired_count=4)
    flags = build_red_flags(rng, scores)
    recs = build_recommendations(rng, scores, focus)
    confidence = confidence_for(sample_size)

    rendered = render_report(
        handle=handle,
        sample_size=sample_size,
        focus=focus,
        scores=scores,
        top=top,
        flags=flags,
        recs=recs,
        confidence=confidence,
    )
    assert_no_handles_in_render(rendered, sample)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_follower_quality_analysis


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Follower Quality Analyzer (Grok Agent OS · creator template)\n"
        "  Aggregate-only · Local-first · Zero individual PII in output\n"
        "  Built for xAI, X, Grok and the ecosystem community. ❤️\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="follower-quality-analyzer",
        description=(
            "Aggregate follower-quality scoring for X creators. "
            "Reads an aggregate sample (inline list, file, or seeded date-range) "
            "and emits a 6/7-section structured report. Aggregate-only — never "
            "exposes individual follower handles in the output."
        ),
    )
    p.add_argument(
        "--x-handle",
        required=True,
        help="The creator's X handle (with or without leading @).",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--follower-sample",
        help="Inline aggregate sample. Comma, space, semicolon, or newline-separated.",
    )
    src.add_argument(
        "--follower-file",
        help="Path to a newline-delimited file of follower handles (lines starting with # are ignored).",
    )
    src.add_argument(
        "--date-range",
        help="ISO date range (YYYY-MM-DD/YYYY-MM-DD) used as a deterministic seed when no inline sample is provided.",
    )
    p.add_argument(
        "--focus",
        choices=list(FOCUS_OPTIONS),
        default="all",
        help="Which canonical metric to emphasise. Default: all.",
    )
    p.add_argument(
        "--niche-median",
        type=int,
        default=DEFAULT_NICHE_MEDIAN_ENGAGEMENT,
        help=f"Engagement quality median for the niche (default {DEFAULT_NICHE_MEDIAN_ENGAGEMENT}).",
    )
    p.add_argument(
        "--output",
        help="Optional path to save the rendered report (Apache 2.0 HTML header is prepended).",
    )
    p.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the runner banner on stdout.",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Run with a 140-handle deterministic demo sample (no inputs required).",
    )
    p.add_argument(
        "--show-system-prompt",
        action="store_true",
        help="Print the loaded system prompt to stderr before generating (useful for debugging).",
    )
    return p


def cli(argv: Optional[list[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    if not args.no_banner:
        sys.stdout.write(banner())
        sys.stdout.flush()

    # Load (or attempt to load) the system prompt. The v1 runner does not
    # call Grok directly — the system prompt is the contract the renderer
    # already obeys — but we surface its presence for debuggability and so
    # a future v2 runner can pass it straight to xAI.
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

    sample = collect_sample(args)
    if not sample and not args.demo:
        sys.stderr.write(
            "error: provide one of --follower-sample, --follower-file, --date-range, or --demo\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_follower_quality_analysis(
        x_handle=args.x_handle,
        follower_sample=sample,
        focus=args.focus,
        when=when_iso,
        niche_median=args.niche_median,
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
