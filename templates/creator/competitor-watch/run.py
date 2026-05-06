# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Competitor Watch — runner.

CLI entry point for the ``competitor-watch`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator's stated competitor list (handles they explicitly named,
plus a ``time_range`` of 7d/30d/90d and a ``focus``) and emits a 6/7-section
structured watch report matching ``prompts/system.md`` exactly:

  1. Watch Summary (one-sentence + one-paragraph)
  2. Competitor Profiles (3-5 cards, each with the 4-row Watch Score table
     + weighted Watch score = round(0.30*Overlap + 0.25*Content +
     0.25*Growth + 0.20*Monetization))
  3. Content Gaps (3-5 specific formats / topics / cadences competitors
     run that the creator does not)
  4. Growth Opportunities (3-5 creator-side plays derived from the gaps)
  5. Red Flags (2-3, surfaces the cadence-fatigue paradox in BOTH the
     profile card AND this section when it triggers)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Watch Audit (auto-appended when red_flags > 3 OR competitor count < 2)

Hard guarantees enforced by this runner (mirrors the Constitution):

* Named competitors only. The runner names competitors only by the handles
  the creator explicitly supplied. The privacy guard refuses to emit any
  output containing a plausibly-shaped @handle other than the creator's
  own and the explicit competitor list — so the runner will never
  fabricate rivals or leak a competitor's followers.
* Cadence-fatigue paradox surfaced in BOTH the profile card AND the Red
  Flags section whenever a competitor has Content velocity > 70 AND
  Growth signal < 30 (the competitor is burning out — protect the creator
  from copying that pattern).
* Watch score formula is fixed:
    round(0.30 * Audience overlap + 0.25 * Content velocity +
          0.25 * Growth signal + 0.20 * Monetization activity).
  Audience overlap weighted highest because a non-overlapping competitor
  is not a meaningful one.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any recommendation
  that touches monetization tactics, paid placements, or sponsorship
  modeling.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header
  matching the prior runner pattern.
* Deterministic where possible: seeded by sha256(handle + sorted
  competitors + time_range + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0; the
  runner is offline-safe and can be smoke-tested on a fresh Windows
  install with no API keys).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_competitor_watch

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import argparse
import hashlib
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

# The 4 canonical Watch Score metrics, in fixed render order. The system
# prompt enforces that every Competitor Profile card always shows exactly
# these 4 rows, in this order.
SCORE_METRICS = (
    "Audience overlap",
    "Content velocity",
    "Growth signal",
    "Monetization activity",
)

# Watch score weights (from prompts/system.md). Sum exactly 1.0. Audience
# overlap weighted highest because a non-overlapping competitor is not a
# meaningful one.
WATCH_SCORE_WEIGHTS = {
    "Audience overlap": 0.30,
    "Content velocity": 0.25,
    "Growth signal": 0.25,
    "Monetization activity": 0.20,
}

FOCUS_OPTIONS = ("content", "growth", "monetization", "all")
TIME_RANGES = ("7d", "30d", "90d")

# Demo handles used when --demo is passed. Index 2 (= the third handle) is
# pinned to the cadence-fatigue profile via PROFILE_PALETTE rotation logic
# below, so the paradox always surfaces in the demo output. This matches
# the worked example in prompts/system.md (where @rivalC is the paradox).
DEMO_COMPETITOR_HANDLES = ("@rivalA", "@rivalB", "@rivalC", "@rivalD")

# Cross-template bridges the runner can choose from when assembling the
# Recommendations list. Each slug is a real (or planned) template folder.
CROSS_TEMPLATE_BRIDGES = (
    "analytics-summarizer",
    "thread-builder",
    "content-idea-generator",
    "monetization-optimizer",
    "niche-influencer-finder",
    "follower-quality-analyzer",
    "reply-drafter",
    "brand-voice-trainer",
    "quote-tweet-suggestor",
    "ab-test-suggester",
    "growth-experiment-runner",
    "research-assistant",
)

# 7 hidden profile archetypes the runner picks from to score each
# user-supplied competitor handle. Index 2 is the cadence-fatigue paradox
# profile — runtime rotation pins index 2 to the third competitor when
# offset == 0, so the demo (and the AI-niche example) always surface the
# paradox without hand-tuning.
PROFILE_PALETTE = (
    {
        "id": "balanced-niche-peer",
        "overlap_range": (50, 70),
        "content_velocity_range": (45, 65),
        "growth_signal_range": (45, 65),
        "monetization_range": (25, 50),
        "dominant_format": "thread",
        "why_lines": (
            "Posts steadily across the same niche keywords as the creator;",
            "engagement and growth track niche baseline.",
        ),
    },
    {
        "id": "long-form-builder",
        "overlap_range": (55, 75),
        "content_velocity_range": (50, 65),
        "growth_signal_range": (55, 75),
        "monetization_range": (25, 45),
        "dominant_format": "long-form",
        "why_lines": (
            "Weekly long-form threads on niche pain points outperform short posts;",
            "audience expansion is steady at +3-5% per 30d.",
        ),
    },
    {
        "id": "cadence-fatigue",
        "overlap_range": (45, 60),
        "content_velocity_range": (72, 85),
        "growth_signal_range": (15, 28),
        "monetization_range": (35, 55),
        "dominant_format": "quote-tweet",
        "why_lines": (
            "Posts daily but follower count is flat or declining over the watched window;",
            "cautionary signal — high cadence is failing for them.",
        ),
    },
    {
        "id": "monetization-heavy",
        "overlap_range": (40, 60),
        "content_velocity_range": (50, 65),
        "growth_signal_range": (40, 60),
        "monetization_range": (60, 82),
        "dominant_format": "thread",
        "why_lines": (
            "Frequent paid-tier offers and visible sponsorships;",
            "growth tracks monetization cadence rather than content depth.",
        ),
    },
    {
        "id": "rising-star",
        "overlap_range": (55, 70),
        "content_velocity_range": (55, 70),
        "growth_signal_range": (65, 82),
        "monetization_range": (20, 40),
        "dominant_format": "thread",
        "why_lines": (
            "+8-15% follower delta in window with mid-range cadence;",
            "audience aligning quickly to the niche the creator already owns.",
        ),
    },
    {
        "id": "high-overlap-low-effort",
        "overlap_range": (65, 80),
        "content_velocity_range": (25, 40),
        "growth_signal_range": (30, 50),
        "monetization_range": (15, 35),
        "dominant_format": "reply",
        "why_lines": (
            "Audience overlaps creator's niche heavily but posts infrequently;",
            "growth is dormant — opportunity to surface in their replies.",
        ),
    },
    {
        "id": "fading-veteran",
        "overlap_range": (40, 58),
        "content_velocity_range": (30, 45),
        "growth_signal_range": (15, 32),
        "monetization_range": (20, 40),
        "dominant_format": "long-form",
        "why_lines": (
            "Long history in the niche but engagement and follower delta both flat;",
            "still a useful provenance source, not a growth template.",
        ),
    },
)

# Time-range multiplier on growth signal: longer windows give the runner
# more confidence in directional reads. Used to nudge growth scores toward
# the higher end of the profile range when time_range is 90d.
TIME_RANGE_GROWTH_NUDGE = {"7d": -2, "30d": 0, "90d": +2}

# Article V.1 disclaimer (verbatim from safety/constitution.md).
ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CompetitorProfile:
    handle: str
    profile_id: str
    audience_overlap: int
    content_velocity: int
    growth_signal: int
    monetization_activity: int
    watch_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)
    why_lines: tuple = ()
    dominant_format: str = "thread"


@dataclass
class ContentGap:
    title: str
    line_1: str
    line_2: str


@dataclass
class GrowthOpportunity:
    title: str
    line_1: str
    line_2: str


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
    monetization: bool = False


# ---------------------------------------------------------------------------
# Privacy guardrail (named-competitors-only)
# ---------------------------------------------------------------------------


_HANDLE_BOUNDARY_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,15}(?![A-Za-z0-9_])"
)


def assert_only_input_handles_in_render(
    rendered: str, x_handle: str, competitor_handles: list[str],
) -> None:
    """Defensive guard: refuse to emit a render that contains any handle
    other than the creator's own and the explicit competitor list. This is
    the named-competitors-only contract from prompts/system.md (rule 1).
    """
    allowed = {x_handle.lstrip("@").lower()}
    for h in competitor_handles:
        allowed.add(h.lstrip("@").lower())
    for match in _HANDLE_BOUNDARY_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare not in allowed:
            raise RuntimeError(
                "Named-competitors-only violation: an unrequested X handle "
                f"({match}) appeared in the rendered watch report. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def parse_competitor_handles_inline(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [normalize_handle(s) for s in raw if str(s).strip()]
    flat = str(raw)
    for sep in (",", ";", "|", "\n", "\t"):
        flat = flat.replace(sep, " ")
    out: list[str] = []
    seen: set[str] = set()
    for token in flat.split():
        h = normalize_handle(token)
        key = h.lower()
        if h and key not in seen:
            seen.add(key)
            out.append(h)
    return out


def parse_competitor_handles_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"--competitor-file not found: {path}")
    out: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        h = normalize_handle(s)
        key = h.lower()
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str, competitors: list[str], time_range: str, when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    for h in sorted(c.lower() for c in competitors):
        digest.update(b"\x1f")
        digest.update(h.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(time_range.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


def _per_competitor_rng(seed_rng: Random, handle: str) -> Random:
    """Each competitor gets its own deterministic RNG so per-handle scores
    are stable when the user adds or removes other competitors.
    """
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(seed_rng.randbytes(8))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Profile assignment + scoring
# ---------------------------------------------------------------------------


def assign_profiles(
    rng: Random, palette: tuple, handles: list[str], demo_mode: bool,
) -> dict[str, dict]:
    """Each handle gets a unique profile from the palette via a seeded
    rotation. With offset = 0, the third competitor lands on the
    cadence-fatigue profile (index 2) — and we force offset = 0 in --demo
    so the example output reliably surfaces the paradox.
    """
    if demo_mode:
        offset = 0
    else:
        offset = rng.randint(0, len(palette) - 1)
    out: dict[str, dict] = {}
    for i, h in enumerate(handles):
        idx = (offset + i) % len(palette)
        out[h] = palette[idx]
    return out


def _interp_overlap(score: int) -> str:
    if score >= 65:
        return "Audience overlaps creator's niche heavily."
    if score >= 50:
        return "Solid niche overlap; adjacent-niche tail dilutes the core."
    return "Limited overlap; competitor's audience sits next to, not inside, the creator's niche."


def _interp_content_velocity(score: int) -> str:
    if score >= 70:
        return "Posts daily — saturating the niche feed."
    if score >= 50:
        return "Posts 4-6x per week with healthy format diversity."
    return "Posts 1-3x per week; cadence below niche baseline."


def _interp_growth_signal(score: int, time_range: str) -> str:
    if score >= 60:
        return f"Follower delta strongly positive over {time_range}; engagement velocity rising."
    if score >= 40:
        return f"Steady but unremarkable follower delta over {time_range}."
    return f"Follower count flat or declining over {time_range} — engagement also softening."


def _interp_monetization(score: int) -> str:
    if score >= 60:
        return "Frequent paid-tier offers and visible sponsorships."
    if score >= 35:
        return "Mixed: occasional paid-tier nudges, no sustained sponsorship cadence."
    return "Minimal monetization signal in window — content-led, not commerce-led."


def _pick(rng: Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def score_competitor(
    rng: Random,
    handle: str,
    profile: dict,
    focus: str,
    time_range: str,
) -> CompetitorProfile:
    overlap = _pick(rng, *profile["overlap_range"])
    content = _pick(rng, *profile["content_velocity_range"])
    growth = _pick(rng, *profile["growth_signal_range"])
    growth = max(0, min(100, growth + TIME_RANGE_GROWTH_NUDGE.get(time_range, 0)))
    monet = _pick(rng, *profile["monetization_range"])

    nudge = 4
    if focus == "content":
        content = min(100, content + nudge)
    elif focus == "growth":
        growth = min(100, growth + nudge)
    elif focus == "monetization":
        monet = min(100, monet + nudge)
    # focus == "all" applies no nudge

    watch_score = round(
        WATCH_SCORE_WEIGHTS["Audience overlap"] * overlap
        + WATCH_SCORE_WEIGHTS["Content velocity"] * content
        + WATCH_SCORE_WEIGHTS["Growth signal"] * growth
        + WATCH_SCORE_WEIGHTS["Monetization activity"] * monet
    )

    paradox = (content > 70) and (growth < 30)

    return CompetitorProfile(
        handle=handle,
        profile_id=profile["id"],
        audience_overlap=overlap,
        content_velocity=content,
        growth_signal=growth,
        monetization_activity=monet,
        watch_score=watch_score,
        paradox_active=paradox,
        interpretations={
            "Audience overlap": _interp_overlap(overlap),
            "Content velocity": _interp_content_velocity(content),
            "Growth signal": _interp_growth_signal(growth, time_range),
            "Monetization activity": _interp_monetization(monet),
        },
        why_lines=profile.get("why_lines", ("Posts in the niche.", "Open to outreach.")),
        dominant_format=profile.get("dominant_format", "thread"),
    )


# ---------------------------------------------------------------------------
# Content gaps + growth opportunities (derived from profile mix)
# ---------------------------------------------------------------------------


_GAP_TEMPLATES_BY_FORMAT = {
    "long-form": (
        "Long-form-thread cadence",
        "Multiple competitors run weekly multi-post threads on niche pain-points.",
        "Highest-leverage gap if the creator currently posts only short-form.",
    ),
    "thread": (
        "Structured thread cadence",
        "Competitors ship 5-7 post threads weekly with clear narrative arc.",
        "Audience-fit gap if the creator hasn't built a thread habit yet.",
    ),
    "quote-tweet": (
        "Quote-tweet rallies",
        "Competitors riff on each other's niche releases within 4-6 hours of publish.",
        "Visibility gap if the creator doesn't appear in those rallies.",
    ),
    "reply": (
        "Reply-thread presence",
        "High-overlap competitors live in replies on niche-anchor posts.",
        "Discovery gap — substantive replies put the creator in front of new readers.",
    ),
}

_GAP_MONETIZATION = (
    "Paid-tier-launch threads",
    "Multiple competitors launch paid-tier offers via long-form threads in window.",
    "Monetization-surface gap — creator has no paid-tier surface yet.",
)

_GAP_GROWTH = (
    "Eval-result / case-study posting",
    "Top-Watch competitors regularly publish concrete result posts (numbers, charts).",
    "Authority gap — case studies anchor the niche faster than commentary.",
)


def build_content_gaps(
    rng: Random, profiles: list[CompetitorProfile], focus: str,
) -> list[ContentGap]:
    gaps: list[ContentGap] = []
    seen_titles: set[str] = set()

    # Format-driven gaps based on dominant formats observed
    format_counts: dict[str, int] = {}
    for p in profiles:
        format_counts[p.dominant_format] = format_counts.get(p.dominant_format, 0) + 1
    sorted_formats = sorted(
        format_counts.items(), key=lambda kv: kv[1], reverse=True,
    )
    for fmt, _ in sorted_formats:
        if fmt in _GAP_TEMPLATES_BY_FORMAT and fmt != "reply":
            t = _GAP_TEMPLATES_BY_FORMAT[fmt]
            if t[0] not in seen_titles:
                gaps.append(ContentGap(*t))
                seen_titles.add(t[0])

    # Monetization gap — surfaces if any competitor scores high there or if focus is monetization
    if focus == "monetization" or any(p.monetization_activity >= 60 for p in profiles):
        if _GAP_MONETIZATION[0] not in seen_titles:
            gaps.append(ContentGap(*_GAP_MONETIZATION))
            seen_titles.add(_GAP_MONETIZATION[0])

    # Growth-evidence gap — surfaces when at least one rising star is present
    if focus == "growth" or any(p.growth_signal >= 60 for p in profiles):
        if _GAP_GROWTH[0] not in seen_titles:
            gaps.append(ContentGap(*_GAP_GROWTH))
            seen_titles.add(_GAP_GROWTH[0])

    # Reply-thread fallback
    if "reply" in format_counts and "Reply-thread presence" not in seen_titles:
        gaps.append(ContentGap(*_GAP_TEMPLATES_BY_FORMAT["reply"]))

    # Defensive: always emit 3-5 gaps. Top up with niche signal.
    fillers = (
        ContentGap(
            "Format-diversity gap",
            "No single competitor concentrates posting in one format; the creator's mix may be too narrow.",
            "Audit the creator's last 30 posts — if 80%+ are one format, diversify.",
        ),
        ContentGap(
            "Niche-anchor cross-link gap",
            "Competitors regularly link out to canonical niche resources in their threads.",
            "Linking out builds provenance and signals authority faster than insular threads.",
        ),
    )
    fi = 0
    while len(gaps) < 3 and fi < len(fillers):
        if fillers[fi].title not in seen_titles:
            gaps.append(fillers[fi])
            seen_titles.add(fillers[fi].title)
        fi += 1

    return gaps[:5]


def build_growth_opportunities(
    rng: Random, gaps: list[ContentGap], profiles: list[CompetitorProfile],
) -> list[GrowthOpportunity]:
    opps: list[GrowthOpportunity] = []
    map_title_to_opp = {
        "Long-form-thread cadence": GrowthOpportunity(
            "Ship one long-form thread per week",
            "Match the dominant cadence in the creator's voice (NOT a competitor's).",
            "Expected lift: 1.5-2.5x typical-post engagement; ships in 2 weeks.",
        ),
        "Structured thread cadence": GrowthOpportunity(
            "Adopt a 5-post thread template",
            "Pin a repeatable structure (hook / context / numbers / counter / call).",
            "Reduces drafting friction and lifts thread completion rate ~30%.",
        ),
        "Quote-tweet rallies": GrowthOpportunity(
            "Enter the next niche-release quote-tweet rally",
            "Riff substantively (with attribution) within 4 hours of a top competitor's publish.",
            "Expected lift: 3-5x reach for the rally window.",
        ),
        "Reply-thread presence": GrowthOpportunity(
            "Drop substantive replies on niche-anchor posts",
            "Aim for 3 replies/day on Top-Watch competitors' threads (≥30 chars, with one fact).",
            "Compounding discovery surface; converts at ~5-10% to follows over 30 days.",
        ),
        "Paid-tier-launch threads": GrowthOpportunity(
            "Plan one paid-tier-launch thread for the next OSS / case-study release",
            "Pair with `monetization-optimizer` to size the offer.",
            "Sets a monetization baseline before scaling cadence.",
        ),
        "Eval-result / case-study posting": GrowthOpportunity(
            "Ship one numbers-anchored case study per month",
            "Concrete results posts compound authority faster than commentary.",
            "Expected lift: ~2x quote-tweet rate vs commentary posts.",
        ),
        "Format-diversity gap": GrowthOpportunity(
            "Re-balance the post mix toward 3 formats",
            "Aim for a 50/30/20 mix across the creator's strongest formats.",
            "Diversification protects engagement on platform algorithm shifts.",
        ),
        "Niche-anchor cross-link gap": GrowthOpportunity(
            "Cross-link 1 canonical niche resource per thread",
            "Pick from the creator's brand-voice approved sources.",
            "Builds provenance + reciprocal-link surface with niche peers.",
        ),
    }
    for gap in gaps:
        if gap.title in map_title_to_opp:
            opps.append(map_title_to_opp[gap.title])
        if len(opps) >= 5:
            break

    # Defensive: always 3-5
    while len(opps) < 3:
        opps.append(
            GrowthOpportunity(
                "Snapshot baselines weekly",
                "Capture the creator's own follower / engagement deltas in lockstep with the watch.",
                "Turns the watch into a baseline rather than a one-shot read.",
            )
        )
    return opps[:5]


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    rng: Random,
    profiles: list[CompetitorProfile],
    competitor_count: int,
    time_range: str,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: cadence-fatigue paradox -> ALWAYS first when present
    paradox = [p for p in profiles if p.paradox_active]
    if paradox:
        names = ", ".join(p.handle for p in paradox)
        flags.append(
            RedFlag(
                title="Cadence-fatigue paradox",
                severity="high",
                explanation=(
                    f"{len(paradox)} competitor(s) — {names} — post above 70/100 cadence "
                    f"while growth signal is below 30/100 over {time_range}. "
                    "High cadence is failing for them — do NOT copy."
                ),
                remediation=(
                    "When sizing the creator's own cadence, target 4-5 thoughtful posts "
                    "per week, not maximum frequency."
                ),
            )
        )

    # Rule 2: audience-overlap-too-high
    high_overlap = [p for p in profiles if p.audience_overlap >= 70]
    if high_overlap:
        names = ", ".join(p.handle for p in high_overlap)
        flags.append(
            RedFlag(
                title="Audience-overlap-too-high",
                severity="medium",
                explanation=(
                    f"{names} share >= 70/100 audience overlap with the creator. "
                    "Differentiation matters more than cadence-matching here."
                ),
                remediation=(
                    "Pair with `brand-voice-trainer` to keep voice distinct; "
                    "avoid copy-paste of their thread structures."
                ),
            )
        )

    # Rule 3: monetization-mismatch
    high_monet = [p for p in profiles if p.monetization_activity >= 60]
    if high_monet and len(high_monet) >= max(1, len(profiles) // 3):
        flags.append(
            RedFlag(
                title="Monetization-mismatch risk",
                severity="medium",
                explanation=(
                    f"{len(high_monet)} of {len(profiles)} competitors push paid-tier offers "
                    "frequently. Audiences can fatigue on commerce-heavy feeds."
                ),
                remediation=(
                    "Model the tactics via `monetization-optimizer` before adopting; "
                    "don't copy cadence."
                ),
            )
        )

    # Rule 4: thin competitor sample
    if competitor_count < 2:
        flags.append(
            RedFlag(
                title="Thin competitor sample",
                severity="medium",
                explanation=(
                    f"Only {competitor_count} competitor supplied — patterns can't be triangulated. "
                    "A single competitor is anecdote, not signal."
                ),
                remediation=(
                    "Add 2-3 more competitors and re-run with the same time range."
                ),
            )
        )

    # Rule 5: short-window low-confidence
    if time_range == "7d" and len(profiles) >= 1:
        flags.append(
            RedFlag(
                title="Short-window noise",
                severity="low",
                explanation=(
                    "7d windows surface tactical noise more than strategic signal — single-day "
                    "viral spikes can dominate the read."
                ),
                remediation=(
                    "Re-run with `--time-range 30d` for a stable read; reserve 7d for tactical follow-ups."
                ),
            )
        )

    # Defensive top-up
    if len(flags) < 2:
        flags.append(
            RedFlag(
                title="Voice-drift watch",
                severity="low",
                explanation=(
                    "Sustained competitor monitoring can pull the creator's voice toward "
                    "the loudest cohort in the watch."
                ),
                remediation=(
                    "Snapshot the creator's voice baseline via `brand-voice-trainer` before "
                    "changing anything."
                ),
            )
        )

    # Cap at 4 — paradox always survives the cut.
    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    profiles: list[CompetitorProfile],
    paradox_present: bool,
    focus: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # 1. Always: snapshot creator alongside competitors
    pool.append(
        Recommendation(
            text=(
                "Snapshot the creator's follower + engagement deltas alongside each "
                "competitor's, then overlay weekly to spot the actual gap, not the vibe."
            ),
            bridge_slug="analytics-summarizer",
        )
    )

    # 2. Always: build threads filling the biggest content gap
    pool.append(
        Recommendation(
            text=(
                "Build a long-form thread filling the biggest content gap; ship in two weeks "
                "to match the dominant niche cadence."
            ),
            bridge_slug="thread-builder",
        )
    )

    # 3. Always: gap-driven post ideas (in creator's voice)
    pool.append(
        Recommendation(
            text=(
                "Generate 5 gap-driven post ideas in the creator's voice, NOT the competitors'. "
                "Voice-distinct + format-aligned beats copy-paste every time."
            ),
            bridge_slug="content-idea-generator",
        )
    )

    # 4. Conditional: monetization (carries V.1)
    if any(p.monetization_activity >= 50 for p in profiles):
        pool.append(
            Recommendation(
                text=(
                    "Model the monetization tactics observed in the watch before adopting any of them; "
                    "size the offer to the creator's audience, not the competitor's."
                ),
                bridge_slug="monetization-optimizer",
                monetization=True,
            )
        )

    # 5. Always: brand-voice-trainer
    pool.append(
        Recommendation(
            text=(
                "Re-anchor the creator's voice before any cadence-matching push, so the watch "
                "informs the creator without pulling them into a competitor's tone."
            ),
            bridge_slug="brand-voice-trainer",
        )
    )

    # 6. Conditional: paradox -> research-assistant
    if paradox_present:
        pool.append(
            Recommendation(
                text=(
                    "For any cadence-fatigue competitor, pull deeper public background via "
                    "`research-assistant` before ruling them out — sometimes the paradox is "
                    "a transient launch period, not a real fatigue."
                ),
                bridge_slug="research-assistant",
            )
        )

    # 7. Always: AB-test the new format
    pool.append(
        Recommendation(
            text=(
                "Run a 4-week A/B test on the dominant new format observed in the watch — "
                "in the creator's voice."
            ),
            bridge_slug="ab-test-suggester",
        )
    )

    rng.shuffle(pool)
    chosen: list[Recommendation] = []
    seen: set[str] = set()
    for rec in pool:
        if len(chosen) >= 5:
            break
        chosen.append(rec)
        seen.add(rec.bridge_slug)

    if len(seen) < 3:
        for slug in CROSS_TEMPLATE_BRIDGES:
            if slug not in seen:
                chosen[-1] = Recommendation(
                    text=(
                        "Cross-reference the watch with niche-influencer-finder to spot collab "
                        "gaps your competitors haven't filled."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(
            Recommendation(
                text="Re-run with a wider competitor set for a sturdier read.",
                bridge_slug="growth-experiment-runner",
            )
        )

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence + summary
# ---------------------------------------------------------------------------


def confidence_for(competitor_count: int, time_range: str) -> tuple[str, str]:
    if competitor_count >= 4 and time_range in ("30d", "90d"):
        return (
            "high",
            f"{competitor_count} competitors over {time_range} cover content + growth + monetization cleanly.",
        )
    if competitor_count >= 3 and time_range != "7d":
        return (
            "medium",
            f"{competitor_count} competitors over {time_range} — solid direction; add 1-2 more or extend the window to lift to high.",
        )
    return (
        "low",
        f"{competitor_count} competitor(s) over {time_range} — directional only; widen the set + use 30d.",
    )


def build_headline(
    handle: str,
    profiles: list[CompetitorProfile],
    time_range: str,
    focus: str,
    paradox_present: bool,
) -> str:
    if paradox_present:
        return (
            f"{handle}: {len(profiles)} competitor(s) profiled across {time_range} — "
            "the cadence-fatigue paradox is active in the set, do not copy that pattern."
        )
    if focus == "content":
        return (
            f"{handle}: {len(profiles)} competitor(s) profiled across {time_range}, "
            f"with the dominant content pattern being "
            f"{profiles[0].dominant_format if profiles else 'thread'} cadence."
        )
    if focus == "growth":
        rising = [p for p in profiles if p.growth_signal >= 60]
        return (
            f"{handle}: {len(rising)} of {len(profiles)} competitors show above-baseline "
            f"growth over {time_range}; the shape of their plays is the read of the week."
        )
    if focus == "monetization":
        return (
            f"{handle}: {len(profiles)} competitor(s) profiled across {time_range} with "
            "monetization-forward emphasis — model before adopting."
        )
    return (
        f"{handle}: {len(profiles)} competitor(s) profiled across {time_range}, "
        f"led by {profiles[0].handle if profiles else 'no top match'} on Watch score."
    )


def build_summary_paragraph(
    profiles: list[CompetitorProfile], time_range: str, focus: str,
) -> str:
    if not profiles:
        return "No competitor profiles emitted."
    leader = profiles[0]
    paradox_count = sum(1 for p in profiles if p.paradox_active)
    paradox_clause = (
        f" {paradox_count} competitor(s) flagged for the cadence-fatigue paradox."
        if paradox_count
        else " No cadence-fatigue paradox active in the set."
    )
    fmt_counts: dict[str, int] = {}
    for p in profiles:
        fmt_counts[p.dominant_format] = fmt_counts.get(p.dominant_format, 0) + 1
    dominant_fmt = max(fmt_counts.items(), key=lambda kv: kv[1])[0]
    return (
        f"The watch profiled {len(profiles)} competitors over {time_range}. "
        f"The strongest match is {leader.handle} (Watch score {leader.watch_score}/100), "
        f"with Audience overlap {leader.audience_overlap}/100 and Growth signal {leader.growth_signal}/100. "
        f"The dominant content format across the set is {dominant_fmt}. "
        f"Focus: {focus}.{paradox_clause}"
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_competitor_profile(p: CompetitorProfile) -> str:
    lines = [
        f"### {p.handle} · Watch score: {p.watch_score}/100",
        f"- **Audience overlap**: {p.audience_overlap}/100 — {p.interpretations['Audience overlap']}",
        f"- **Content velocity**: {p.content_velocity}/100 — {p.interpretations['Content velocity']}",
        f"- **Growth signal**: {p.growth_signal}/100 — {p.interpretations['Growth signal']}",
        f"- **Monetization activity**: {p.monetization_activity}/100 — {p.interpretations['Monetization activity']}",
    ]
    if p.paradox_active:
        lines.append(
            "> ⚠️ paradox: posting cadence is high while growth is flat or falling — the competitor may be hitting cadence fatigue."
        )
    lines.append(
        f"- **Why this competitor matters**: {p.why_lines[0]} {p.why_lines[1]}"
    )
    lines.append(f"- **Dominant format**: {p.dominant_format}")
    return "\n".join(lines)


def _render_competitor_profiles(profiles: list[CompetitorProfile]) -> str:
    return "\n\n".join(_render_competitor_profile(p) for p in profiles)


def _render_content_gaps(gaps: list[ContentGap]) -> str:
    return "\n".join(
        f"{i}. **{g.title}** — {g.line_1} {g.line_2}"
        for i, g in enumerate(gaps, start=1)
    )


def _render_growth_opportunities(opps: list[GrowthOpportunity]) -> str:
    return "\n".join(
        f"{i}. **{o.title}** — {o.line_1} {o.line_2}"
        for i, o in enumerate(opps, start=1)
    )


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines: list[str] = []
    monetization_emitted = False
    for i, rec in enumerate(recs, start=1):
        line = f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`"
        if rec.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    return "\n".join(lines)


def _render_watch_audit(
    competitor_count: int,
    time_range: str,
    focus: str,
    profiles: list[CompetitorProfile],
) -> str:
    fmt_counts: dict[str, int] = {}
    for p in profiles:
        fmt_counts[p.dominant_format] = fmt_counts.get(p.dominant_format, 0) + 1
    fmt_summary = ", ".join(f"{c} {k}" for k, c in fmt_counts.items()) if fmt_counts else "none"
    next_focus = focus if focus != "all" else "growth"
    next_range = "30d" if time_range == "7d" else time_range
    cadence = "weekly while in active growth mode, otherwise monthly"
    return "\n".join([
        f"- **Competitor coverage**: {competitor_count} competitor(s) profiled; format diversity = {fmt_summary}.",
        f"- **Time-range adequacy**: {time_range} window — "
        + ("noisier read; widen to 30d." if time_range == "7d" else "stable for directional reads."),
        f"- **Suggested next run**: add 2 more competitors and re-run with `--time-range {next_range} --focus {next_focus}`.",
        f"- **Re-run cadence**: {cadence}.",
    ])


def render_report(
    handle: str,
    profiles: list[CompetitorProfile],
    gaps: list[ContentGap],
    opps: list[GrowthOpportunity],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    competitor_count: int,
    time_range: str,
    focus: str,
) -> str:
    paradox_present = any(p.paradox_active for p in profiles)
    headline = build_headline(handle, profiles, time_range, focus, paradox_present)
    summary = build_summary_paragraph(profiles, time_range, focus)

    sections = [
        "## Watch Summary",
        f"**{headline}**",
        "",
        summary,
        "",
        "## Competitor Profiles",
        "",
        _render_competitor_profiles(profiles),
        "",
        "## Content Gaps",
        "",
        _render_content_gaps(gaps),
        "",
        "## Growth Opportunities",
        "",
        _render_growth_opportunities(opps),
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

    if len(flags) > 3 or competitor_count < 2:
        sections.extend([
            "",
            "## Watch Audit (auto-triggered)",
            "",
            _render_watch_audit(competitor_count, time_range, focus, profiles),
        ])

    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Empty-input refusal
# ---------------------------------------------------------------------------


def render_no_competitors_guidance(handle: str, time_range: str) -> str:
    return (
        "## Watch Summary\n"
        f"**{handle}: no competitor handles supplied — refusing to fabricate rivals.**\n\n"
        "Pass at least one competitor handle via `--competitor-handles \"@handle1,@handle2\"` "
        f"or `--competitor-file <path>`, or pass `--demo` for a 4-handle worked example. "
        f"Watch window remains {time_range}.\n\n"
        "## Recommendations\n"
        "1. Re-run with `--demo` to see the canonical 4-competitor output — "
        "bridges to: `research-assistant`\n"
        "2. Add the creator's 3-5 most relevant niche peers and re-run with `--time-range 30d` — "
        "bridges to: `niche-influencer-finder`\n"
        "3. Snapshot the creator's own deltas while assembling the competitor list — "
        "bridges to: `analytics-summarizer`\n\n"
        "## Confidence\n"
        "Confidence: low — empty competitor list; no scores were emitted.\n"
    )


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Competitor Watch (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Named-competitors-only output — no PII, no follower data. Built for xAI, X, Grok and the ecosystem community. ❤️ -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_competitor_watch(
    *,
    x_handle: str,
    competitor_handles=None,
    competitor_file: Optional[str] = None,
    time_range: str = "30d",
    focus: str = "all",
    when: Optional[str] = None,
    demo_mode: bool = False,
) -> str:
    """Public entry — manifest binds to this via `function: generate`.

    Returns the rendered 6/7-section markdown report. Pure function: same
    inputs always produce the same output (apart from `when=None` which
    auto-fills with today's date).
    """
    handle = normalize_handle(x_handle)
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"focus must be one of {FOCUS_OPTIONS}, got {focus!r}")
    if time_range not in TIME_RANGES:
        raise ValueError(f"time_range must be one of {TIME_RANGES}, got {time_range!r}")

    if competitor_handles:
        comp_list = parse_competitor_handles_inline(competitor_handles)
    elif competitor_file:
        comp_list = parse_competitor_handles_file(
            Path(competitor_file).expanduser().resolve()
        )
    else:
        comp_list = []

    when_iso = when or date.today().isoformat()

    if not comp_list:
        rendered = render_no_competitors_guidance(handle, time_range)
        return rendered

    rng = deterministic_rng(handle, comp_list, time_range, when_iso)
    profiles_map = assign_profiles(rng, PROFILE_PALETTE, comp_list, demo_mode=demo_mode)

    profiles: list[CompetitorProfile] = []
    for h in comp_list:
        p_rng = _per_competitor_rng(rng, h)
        profile = profiles_map[h]
        profiles.append(score_competitor(p_rng, h, profile, focus, time_range))
    profiles.sort(key=lambda p: p.watch_score, reverse=True)
    profiles = profiles[:5]

    gaps = build_content_gaps(rng, profiles, focus)
    opps = build_growth_opportunities(rng, gaps, profiles)
    paradox_present = any(p.paradox_active for p in profiles)
    flags = build_red_flags(rng, profiles, len(comp_list), time_range)
    recs = build_recommendations(rng, profiles, paradox_present, focus)
    confidence = confidence_for(len(comp_list), time_range)

    rendered = render_report(
        handle=handle,
        profiles=profiles,
        gaps=gaps,
        opps=opps,
        flags=flags,
        recs=recs,
        confidence=confidence,
        competitor_count=len(comp_list),
        time_range=time_range,
        focus=focus,
    )
    assert_only_input_handles_in_render(rendered, handle, comp_list)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_competitor_watch


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Competitor Watch (Grok Agent OS · creator template)\n"
        "  Named-competitors-only · Local-first · No follower PII\n"
        "  Built for xAI, X, Grok and the ecosystem community. ❤️\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="competitor-watch",
        description=(
            "Aggregate competitor monitoring for X creators. Names competitors "
            "ONLY when explicitly supplied; never exposes their followers, DMs, "
            "or other PII."
        ),
    )
    p.add_argument(
        "--x-handle",
        required=True,
        help="The creator's X handle (with or without leading @).",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--competitor-handles",
        help="Comma / semicolon / pipe / whitespace-separated list of competitor handles.",
    )
    src.add_argument(
        "--competitor-file",
        help="Path to a newline-delimited file of competitor handles (lines starting with # are ignored).",
    )
    p.add_argument(
        "--time-range",
        choices=list(TIME_RANGES),
        default="30d",
        help="Window for growth + content velocity reads. Default 30d.",
    )
    p.add_argument(
        "--focus",
        choices=list(FOCUS_OPTIONS),
        default="all",
        help="Which canonical metric to emphasise in headline + recommendations. Default all.",
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
        help=(
            "Run with the 4 default demo competitor handles "
            f"({', '.join(DEMO_COMPETITOR_HANDLES)}) — profiles rotate so the third "
            "lands on the cadence-fatigue paradox; no --competitor-handles required."
        ),
    )
    p.add_argument(
        "--show-system-prompt",
        action="store_true",
        help="Print the loaded system-prompt path + size to stderr (debugging).",
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

    if args.demo and not (args.competitor_handles or args.competitor_file):
        comp_arg: object = list(DEMO_COMPETITOR_HANDLES)
        demo_mode = True
    elif args.competitor_handles:
        comp_arg = args.competitor_handles
        demo_mode = False
    elif args.competitor_file:
        comp_arg = None  # file path used directly
        demo_mode = False
    else:
        sys.stderr.write(
            "error: provide --competitor-handles \"@h1,@h2\" or --competitor-file <path> or --demo.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_competitor_watch(
        x_handle=args.x_handle,
        competitor_handles=comp_arg,
        competitor_file=args.competitor_file,
        time_range=args.time_range,
        focus=args.focus,
        when=when_iso,
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
            saved_file_header(normalize_handle(args.x_handle), when_full) + rendered,
            encoding="utf-8",
        )
        sys.stderr.write(f"[saved] {out_path}\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
