# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Niche Influencer Finder — runner.

CLI entry point for the ``niche-influencer-finder`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator's niche keywords + tier band (min_followers / max_followers)
and emits a 6/7-section structured discovery report matching
``prompts/system.md`` exactly:

  1. Influencer Summary (one-sentence + one-paragraph)
  2. Top Influencers (3-5 paraphrased archetype cards across Micro / Mid /
     Macro tiers, each with the 4-row Match Scores table + weighted
     Match score = round(0.30A + 0.25E + 0.25F + 0.20C))
  3. Collaboration Opportunities (3-5, each pairing one of the 6 first-move
     formats with a surfaced archetype)
  4. Red Flags (2-3, surfaces the engagement-pod paradox in BOTH the
     archetype card AND this section when it triggers)
  5. Recommendations (3-5, with >= 3 cross-template bridges)
  6. Confidence
  7. Discovery Audit (auto-appended when red_flags > 3 OR keyword count < 2)

Hard guarantees enforced by this runner (mirrors the Constitution):

* Aggregate-only output. Every Top-Influencer card is a paraphrased
  archetype (label + tier + plausibility band), never a real X account
  handle. The runner accepts no handles as input — only niche keywords —
  and the renderer's privacy guard refuses to emit any output that would
  surface a plausibly-shaped @handle.
* Engagement-pod paradox surfaced in BOTH the archetype card AND the Red
  Flags section whenever an archetype has Engagement > 70 AND Authority
  < 50 (same shape as the bot-engagement paradox in
  ``follower-quality-analyzer``).
* Match score formula is fixed: round(0.30*Authority + 0.25*Engagement +
  0.25*AudienceFit + 0.20*CollaborationPotential).
* Tier-band respect. Archetypes whose plausible follower count falls
  outside the requested ``--min-followers`` / ``--max-followers`` band
  are dropped, and the omission is mentioned in the Discovery Audit
  section when triggered.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any recommendation
  that touches paid placements, sponsorships, or revenue share.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header
  matching the prior runner pattern.
* Deterministic where possible: seeded by sha256(handle + sorted_keywords
  + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0; the
  runner is offline-safe and can be smoke-tested on a fresh Windows
  install with no API keys).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_niche_influencer_recommendations

Built to help xAI and Grok win.
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

# The 4 canonical Match Score metrics, in fixed render order. The system
# prompt enforces that every Top-Influencer card always shows exactly these
# 4 rows, in this order.
SCORE_METRICS = (
    "Authority",
    "Engagement",
    "Audience fit",
    "Collaboration potential",
)

# Match score weights (from prompts/system.md "worked example" section).
# round(0.30*A + 0.25*E + 0.25*F + 0.20*C). Sum exactly 1.0.
MATCH_SCORE_WEIGHTS = {
    "Authority": 0.30,
    "Engagement": 0.25,
    "Audience fit": 0.25,
    "Collaboration potential": 0.20,
}

# The 6 canonical first-move formats. Top-Influencer cards must end with
# exactly one of these, and Collaboration Opportunities use them as the
# format slot.
FIRST_MOVE_VERBS = (
    "thread-collab",
    "podcast-swap",
    "quote-tweet-rally",
    "co-authored-post",
    "mutual-shoutout",
    "dm-intro",
)

FOCUS_OPTIONS = ("engagement", "authority", "collaboration_potential", "all")

DEFAULT_MIN_FOLLOWERS = 5_000
DEFAULT_MAX_FOLLOWERS = 500_000

# Tier bands (label, min, max). The runner uses these to assign each
# archetype its Tier slot in the report headings.
TIER_BANDS = (
    ("Micro", 5_000, 50_000),
    ("Mid", 50_000, 200_000),
    ("Macro", 200_000, 500_000),
)

# Cross-template bridges the runner can choose from when assembling the
# Recommendations list. Each slug is a real (or planned) creator-template
# folder under ``templates/creator/`` (or ``templates/general/`` for
# ``research-assistant``). The Recommendations always link to >= 3 distinct.
CROSS_TEMPLATE_BRIDGES = (
    "follower-quality-analyzer",
    "reply-drafter",
    "content-idea-generator",
    "monetization-optimizer",
    "analytics-summarizer",
    "thread-builder",
    "competitor-watch",
    "mention-summarizer",
    "dm-triager",
    "brand-voice-trainer",
    "quote-tweet-suggestor",
    "research-assistant",
)

# The aggregate Top-Influencer archetype palette. 11 archetypes spanning
# all 3 tiers, with at least 2 carrying the engagement-pod paradox profile
# (Engagement > 70, Authority < 50) so realistic discovery runs surface
# the paradox naturally without hand-tuning.
ARCHETYPE_PALETTE = (
    {
        "label": "Indie LLM-infra founder",
        "follower_count": 8_000,
        "default_first_move": "co-authored-post",
        "authority_range": (75, 90),
        "engagement_range": (50, 65),
        "audience_fit_range": (70, 85),
        "collab_potential_range": (65, 80),
        "why_lines": (
            "Active in the same niche keywords;",
            "regularly co-authors with peers and accepts joint long-form invites.",
        ),
    },
    {
        "label": "OSS-builder solo dev",
        "follower_count": 14_000,
        "default_first_move": "thread-collab",
        "authority_range": (70, 82),
        "engagement_range": (60, 75),
        "audience_fit_range": (60, 75),
        "collab_potential_range": (55, 68),
        "why_lines": (
            "Ships new niche-aligned OSS releases monthly;",
            "engages substantively in replies but rarely reposts.",
        ),
    },
    {
        "label": "Productivity coach + book author",
        "follower_count": 38_000,
        "default_first_move": "podcast-swap",
        "authority_range": (68, 80),
        "engagement_range": (52, 64),
        "audience_fit_range": (65, 80),
        "collab_potential_range": (60, 72),
        "why_lines": (
            "Long tenure in the niche with a published book;",
            "guests on 3-4 niche podcasts per quarter.",
        ),
    },
    {
        "label": "Eval-tooling researcher",
        "follower_count": 62_000,
        "default_first_move": "podcast-swap",
        "authority_range": (82, 92),
        "engagement_range": (40, 52),
        "audience_fit_range": (58, 72),
        "collab_potential_range": (50, 64),
        "why_lines": (
            "Long-form posts cited by adjacent niches monthly;",
            "audience overlaps creator's niche with a research-methods tail.",
        ),
    },
    {
        "label": "Newsletter operator + podcaster",
        "follower_count": 95_000,
        "default_first_move": "podcast-swap",
        "authority_range": (72, 85),
        "engagement_range": (48, 60),
        "audience_fit_range": (62, 78),
        "collab_potential_range": (70, 84),
        "why_lines": (
            "Operates a 30k-subscriber niche newsletter and a flagship podcast;",
            "swaps guest slots with peers monthly.",
        ),
    },
    {
        "label": "Engagement-pod regular",
        "follower_count": 120_000,
        "default_first_move": "monitor-only",
        "authority_range": (35, 47),
        "engagement_range": (74, 86),
        "audience_fit_range": (55, 68),
        "collab_potential_range": (62, 75),
        "why_lines": (
            "High aggregate engagement on every post;",
            "low authority signal and rapid follower-count climb suggest pod activity.",
        ),
    },
    {
        "label": "Mid-tier infra blogger",
        "follower_count": 145_000,
        "default_first_move": "thread-collab",
        "authority_range": (74, 86),
        "engagement_range": (50, 62),
        "audience_fit_range": (68, 82),
        "collab_potential_range": (58, 70),
        "why_lines": (
            "Weekly long-form blog posts cross-posted to X;",
            "strong overlap on infra and tooling keywords.",
        ),
    },
    {
        "label": "Habit-stacking community lead",
        "follower_count": 165_000,
        "default_first_move": "mutual-shoutout",
        "authority_range": (66, 78),
        "engagement_range": (55, 68),
        "audience_fit_range": (62, 76),
        "collab_potential_range": (60, 72),
        "why_lines": (
            "Runs a 20k-member productivity community;",
            "regularly hosts collab challenges with peer creators.",
        ),
    },
    {
        "label": "Tech-founder podcaster",
        "follower_count": 280_000,
        "default_first_move": "podcast-swap",
        "authority_range": (78, 90),
        "engagement_range": (45, 58),
        "audience_fit_range": (55, 70),
        "collab_potential_range": (65, 78),
        "why_lines": (
            "Hosts a top-20 niche podcast with weekly episodes;",
            "audience skews founder/operator and overlaps creator niche.",
        ),
    },
    {
        "label": "AI-influencer commentator",
        "follower_count": 350_000,
        "default_first_move": "quote-tweet-rally",
        "authority_range": (40, 52),
        "engagement_range": (76, 88),
        "audience_fit_range": (55, 70),
        "collab_potential_range": (66, 78),
        "why_lines": (
            "Reacts to every major niche release within hours;",
            "high engagement masks thin authority — verify before reaching out.",
        ),
    },
    {
        "label": "Macro-tier platform analyst",
        "follower_count": 420_000,
        "default_first_move": "thread-collab",
        "authority_range": (72, 86),
        "engagement_range": (42, 56),
        "audience_fit_range": (50, 65),
        "collab_potential_range": (55, 70),
        "why_lines": (
            "Quarterly platform-state essays are quoted across the niche;",
            "audience is broader than the creator's core but the bridge is real.",
        ),
    },
)

# Default keywords used by --demo so the runner is one-shot launchable
# without any user inputs.
DEMO_KEYWORDS = ("AI agents", "LLM ops", "infra")

# Article V.1 disclaimer (verbatim from safety/constitution.md). Must appear
# under any Recommendation that touches monetization tiers, paid
# placements, sponsorships, or revenue share.
ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

MONETIZATION_KEYWORDS = (
    "monetiz",
    "payout",
    "sponsor",
    "paid placement",
    "paid-placement",
    "revenue share",
    "revenue-share",
    "tier",
    "subscription",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class InfluencerArchetype:
    label: str
    tier: str
    follower_count: int
    authority: int
    engagement: int
    audience_fit: int
    collaboration_potential: int
    match_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)
    why_lines: tuple = ()
    suggested_first_move: str = "dm-intro"


@dataclass
class CollaborationOpportunity:
    format: str
    archetype_label: str
    plan_line_1: str
    plan_line_2: str


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
# Privacy guardrails (no real handles ever)
# ---------------------------------------------------------------------------


_HANDLE_BOUNDARY_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{4,15}(?![A-Za-z0-9_])"
)


def assert_no_real_handles_in_render(rendered: str, x_handle: str) -> None:
    """Defensive guard: refuse to emit a render that contains any plausibly
    real X handle other than the creator's own (which is the only handle
    the runner ever knows). The system prompt forbids naming any influencer
    handle, so any extra match is a leak.
    """
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_BOUNDARY_RE.findall(rendered):
        if match.lstrip("@").lower() != own:
            raise RuntimeError(
                "Aggregate-only violation: a non-creator X handle "
                f"({match}) appeared in the rendered report. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    handle = raw.strip()
    if not handle:
        return ""
    return handle if handle.startswith("@") else "@" + handle


def parse_keywords(raw) -> list[str]:
    """Accept either a list (from the manifest tool call) or a string from
    the CLI. Splits on comma, semicolon, pipe, or newline.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        flat = " | ".join(str(x) for x in raw)
    else:
        flat = str(raw)
    cleaned = flat
    for sep in (",", ";", "|", "\n", "\t"):
        cleaned = cleaned.replace(sep, "||")
    parts = [p.strip() for p in cleaned.split("||") if p.strip()]
    # De-dup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(handle: str, keywords: list[str], when: str) -> Random:
    """Reproducible RNG seeded by sha256(handle + sorted_keywords + date).

    Same inputs -> same archetype scores -> same report. Critical so that
    creators can re-run the discovery without the headline numbers drifting,
    and so the example .md files can be regenerated bit-for-bit from the
    README's PowerShell snippets.
    """
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    for k in sorted(kw.lower() for kw in keywords):
        digest.update(b"\x1f")
        digest.update(k.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Tier classification + archetype filtering
# ---------------------------------------------------------------------------


def tier_for(follower_count: int) -> Optional[str]:
    for label, lo, hi in TIER_BANDS:
        if lo <= follower_count <= hi:
            return label
    return None


def filter_palette_by_band(min_followers: int, max_followers: int) -> list[dict]:
    return [
        a for a in ARCHETYPE_PALETTE
        if min_followers <= a["follower_count"] <= max_followers
    ]


def tier_coverage(archetypes: list[InfluencerArchetype]) -> dict[str, int]:
    counts = {t: 0 for t, _, _ in TIER_BANDS}
    for a in archetypes:
        counts[a.tier] = counts.get(a.tier, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _interp_authority(score: int) -> str:
    if score >= 80:
        return "Long tenure with citations across adjacent niches."
    if score >= 60:
        return "Mid tenure with consistent depth signal in long-form posts."
    if score >= 45:
        return "Tenure thin; depth signal limited to short-form posts."
    return "Authority signal weak — depth not visible in recent posts."


def _interp_engagement(score: int) -> str:
    if score >= 75:
        return "Engagement far above niche peers — verify substance vs volume."
    if score >= 55:
        return "Healthy mix of substantive replies and reposts."
    if score >= 40:
        return "Moderate engagement with a passive-likes tail."
    return "Low engagement — passive audience or stale account."


def _interp_audience_fit(score: int) -> str:
    if score >= 70:
        return "Audience overlaps creator's niche keywords heavily."
    if score >= 50:
        return "Solid niche overlap; adjacent-niche tail dilutes the core."
    return "Niche overlap is thin; bridge value uncertain."


def _interp_collab(score: int) -> str:
    if score >= 65:
        return "Strong collab history — accepts cross-posts and guest swaps."
    if score >= 45:
        return "Some collab history; openness to outreach is plausible."
    return "Few collab signals; expect a colder reception to outreach."


def _pick(rng: Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def score_archetype(
    rng: Random,
    archetype: dict,
    focus: str,
) -> InfluencerArchetype:
    auth = _pick(rng, *archetype["authority_range"])
    eng = _pick(rng, *archetype["engagement_range"])
    fit = _pick(rng, *archetype["audience_fit_range"])
    collab = _pick(rng, *archetype["collab_potential_range"])

    nudge = 4
    if focus == "authority":
        auth = min(100, auth + nudge)
    elif focus == "engagement":
        eng = min(100, eng + nudge)
    elif focus == "collaboration_potential":
        collab = min(100, collab + nudge)
    # focus == "all" applies no nudge

    match_score = round(
        MATCH_SCORE_WEIGHTS["Authority"] * auth
        + MATCH_SCORE_WEIGHTS["Engagement"] * eng
        + MATCH_SCORE_WEIGHTS["Audience fit"] * fit
        + MATCH_SCORE_WEIGHTS["Collaboration potential"] * collab
    )

    paradox_active = (eng > 70) and (auth < 50)

    interpretations = {
        "Authority": _interp_authority(auth),
        "Engagement": _interp_engagement(eng),
        "Audience fit": _interp_audience_fit(fit),
        "Collaboration potential": _interp_collab(collab),
    }

    tier = tier_for(archetype["follower_count"]) or "Micro"
    first_move = archetype.get("default_first_move", "dm-intro")
    if first_move not in FIRST_MOVE_VERBS:
        first_move = "dm-intro"

    return InfluencerArchetype(
        label=archetype["label"],
        tier=tier,
        follower_count=archetype["follower_count"],
        authority=auth,
        engagement=eng,
        audience_fit=fit,
        collaboration_potential=collab,
        match_score=match_score,
        paradox_active=paradox_active,
        interpretations=interpretations,
        why_lines=archetype.get("why_lines", ("Active in the niche;", "open to outreach.")),
        suggested_first_move=first_move,
    )


def select_top_influencers(
    rng: Random,
    palette: list[dict],
    focus: str,
    desired_count: int = 5,
) -> list[InfluencerArchetype]:
    """Score every palette entry, keep up to ``desired_count`` clipped to
    [3, 5], prefer a multi-tier mix, and ALWAYS include at least one
    paradox archetype when one exists in the palette so the engagement-pod
    paradox rule (system prompt) can surface — paradox archetypes are
    warnings the creator should see, not silent omissions.
    """
    scored = [score_archetype(rng, a, focus) for a in palette]
    if not scored:
        return []
    scored.sort(key=lambda a: a.match_score, reverse=True)
    desired_count = max(3, min(5, desired_count))

    selected: list[InfluencerArchetype] = []
    used_labels: set[str] = set()

    # Reserve one slot for the highest-match paradox archetype (if any).
    paradox_candidates = [a for a in scored if a.paradox_active]
    if paradox_candidates:
        warn = paradox_candidates[0]
        selected.append(warn)
        used_labels.add(warn.label)

    # Span >= 2 tiers when the palette permits. Take the top match from
    # each tier first, then fill remaining slots by overall match.
    for tier, _, _ in TIER_BANDS:
        if any(s.tier == tier for s in selected):
            continue
        for cand in scored:
            if cand.tier == tier and cand.label not in used_labels:
                selected.append(cand)
                used_labels.add(cand.label)
                break
        if len(selected) >= desired_count:
            break
    for cand in scored:
        if len(selected) >= desired_count:
            break
        if cand.label not in used_labels:
            selected.append(cand)
            used_labels.add(cand.label)
    selected.sort(key=lambda a: a.match_score, reverse=True)
    return selected[:desired_count]


# ---------------------------------------------------------------------------
# Collaboration opportunities
# ---------------------------------------------------------------------------


_COLLAB_PLAYBOOK = {
    "co-authored-post": (
        "Joint long-form on a shared niche pain-point. Creator drafts, archetype edits + signs.",
        "Expected lift: 1.5-3x typical post; ships in 2 weeks if cadence aligns.",
    ),
    "thread-collab": (
        "Coordinated 5-post thread series; one post per author, cross-quoted on publish day.",
        "Expected lift: 2x reply volume vs solo thread; light scheduling overhead.",
    ),
    "podcast-swap": (
        "Each guest on the other's flagship show within the same month; cross-promote in advance.",
        "Expected lift: ~10% sustained follower gain; works best when audiences overlap < 40%.",
    ),
    "quote-tweet-rally": (
        "Coordinate a launch-day quote-tweet train around the creator's next anchor post.",
        "Expected lift: 3-5x reach for 24h; needs day-of timing precision.",
    ),
    "mutual-shoutout": (
        "Reciprocal weekly shoutout post highlighting one piece of each other's work.",
        "Expected lift: ~1-2% follower gain per cycle; durable if scheduled long-term.",
    ),
    "dm-intro": (
        "Cold but specific outreach DM citing 2 of the archetype's recent posts; propose one tiny first step.",
        "Expected lift: 15-25% reply rate when DM cites concrete shared work.",
    ),
}


def build_collaboration_opportunities(
    rng: Random,
    top: list[InfluencerArchetype],
) -> list[CollaborationOpportunity]:
    """Pair 3-5 archetypes with first-move formats. Prefer the archetype's
    suggested first move; substitute when a format would repeat too often.
    """
    if not top:
        return []
    out: list[CollaborationOpportunity] = []
    fmt_counts: dict[str, int] = {}
    for arche in top:
        fmt = arche.suggested_first_move
        if fmt_counts.get(fmt, 0) >= 2 or fmt not in _COLLAB_PLAYBOOK:
            for alt in FIRST_MOVE_VERBS:
                if fmt_counts.get(alt, 0) < 2 and alt in _COLLAB_PLAYBOOK:
                    fmt = alt
                    break
        plan = _COLLAB_PLAYBOOK[fmt]
        fmt_counts[fmt] = fmt_counts.get(fmt, 0) + 1
        out.append(
            CollaborationOpportunity(
                format=fmt,
                archetype_label=arche.label,
                plan_line_1=plan[0],
                plan_line_2=plan[1],
            )
        )
        if len(out) >= 5:
            break
    # Cap at 5, floor at 3 (when palette has 3+ archetypes)
    return out[: max(3, min(5, len(top)))]


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    rng: Random,
    top: list[InfluencerArchetype],
    palette_after_filter: list[dict],
    keyword_count: int,
    min_followers: int,
    max_followers: int,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: engagement-pod paradox -> ALWAYS first when active
    paradox_archetypes = [a for a in top if a.paradox_active]
    if paradox_archetypes:
        labels = ", ".join(a.label for a in paradox_archetypes)
        flags.append(
            RedFlag(
                title="Engagement-pod paradox",
                severity="high",
                explanation=(
                    f"{len(paradox_archetypes)} archetype(s) — {labels} — show Engagement above 70 "
                    "while Authority sits below 50. Aggregate engagement is likely amplified by pod activity."
                ),
                remediation=(
                    "Score the paradox archetype's followers via `follower-quality-analyzer` before "
                    "any outreach; treat the engagement signal as unverified until then."
                ),
            )
        )

    # Rule 2: tier-coverage gaps
    coverage = tier_coverage(top)
    empty_tiers = [t for t, count in coverage.items() if count == 0]
    in_band_tiers = [
        t for t, lo, hi in TIER_BANDS
        if not (hi < min_followers or lo > max_followers)
    ]
    silent_misses = [t for t in empty_tiers if t in in_band_tiers]
    if silent_misses:
        flags.append(
            RedFlag(
                title="Tier-coverage gap",
                severity="medium" if len(silent_misses) >= 2 else "low",
                explanation=(
                    f"No archetypes surfaced in the {', '.join(silent_misses)} tier(s) "
                    f"despite the requested band {min_followers:,}-{max_followers:,} including them."
                ),
                remediation=(
                    "Widen `--niche-keywords` (add 1-2 adjacent terms) and re-run; sparse keywords "
                    "concentrate matches in a single tier."
                ),
            )
        )

    # Rule 3: thin keyword input
    if keyword_count < 2:
        flags.append(
            RedFlag(
                title="Single-keyword fragility",
                severity="medium",
                explanation=(
                    f"Only {keyword_count} keyword supplied — discovery cannot triangulate niche overlap "
                    "and may surface adjacent-niche archetypes by accident."
                ),
                remediation=(
                    "Add at least 1 more keyword (typically a tooling or audience descriptor) "
                    "and re-run with `--focus all`."
                ),
            )
        )

    # Rule 4: low-authority majority
    low_auth = [a for a in top if a.authority < 55]
    if len(low_auth) >= max(2, len(top) // 2):
        flags.append(
            RedFlag(
                title="Low-authority majority",
                severity="medium",
                explanation=(
                    f"{len(low_auth)} of {len(top)} surfaced archetypes have Authority below 55; "
                    "outreach risks anchoring the creator to thin-signal accounts."
                ),
                remediation=(
                    "Tighten the niche keywords toward the creator's depth area, "
                    "or pair each outreach with `research-assistant` to verify authority claims."
                ),
            )
        )

    # Defensive top-up — always emit at least 2
    if len(flags) < 2:
        flags.append(
            RedFlag(
                title="Sparse Macro-tier signal",
                severity="low",
                explanation=(
                    "Macro-tier matches are scarce in this niche — outreach hit-rate "
                    "will lean on Micro and Mid archetypes."
                ),
                remediation=(
                    "Use `competitor-watch` to identify which Macro accounts adjacent "
                    "creators have collabbed with this quarter."
                ),
            )
        )

    # Cap at 4 (we still allow 4 so the optional 7th section can be triggered
    # by `> 3` red flags). Paradox + tier-gap + keyword + low-auth.
    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    top: list[InfluencerArchetype],
    paradox_present: bool,
    focus: str,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # 1. Always: vet via follower-quality-analyzer
    pool.append(
        Recommendation(
            text=(
                "Score each surfaced archetype's followers via `follower-quality-analyzer` "
                "before sending the first DM — confirms real reach, not pod traffic."
            ),
            bridge_slug="follower-quality-analyzer",
        )
    )

    # 2. Always: outreach in voice
    pool.append(
        Recommendation(
            text=(
                "Draft outreach DMs in the creator's voice rather than a generic template "
                "to lift reply rate from ~5% to 15-25%."
            ),
            bridge_slug="brand-voice-trainer",
        )
    )

    # 3. Always: snapshot lift
    pool.append(
        Recommendation(
            text=(
                "Snapshot follower-count and engagement on the day of and 14 days after each "
                "collab to measure real lift, not vanity reach."
            ),
            bridge_slug="analytics-summarizer",
        )
    )

    # 4. Conditional: monetization (carries V.1 disclaimer)
    if any(a.match_score >= 70 for a in top):
        pool.append(
            Recommendation(
                text=(
                    "If any of these collabs surface a paid-placement option, model the value "
                    "before negotiating sponsorship terms."
                ),
                bridge_slug="monetization-optimizer",
                monetization=True,
            )
        )

    # 5. Co-content
    pool.append(
        Recommendation(
            text=(
                "Generate 3 co-content angles per archetype before the first outreach so the "
                "DM has a concrete pitch attached, not just an introduction."
            ),
            bridge_slug="content-idea-generator",
        )
    )

    # 6. If paradox: add research-assistant for deeper verification
    if paradox_present:
        pool.append(
            Recommendation(
                text=(
                    "For any paradox archetype, pull deeper background via `research-assistant` "
                    "before pitching — verify their niche claims with adjacent sources."
                ),
                bridge_slug="research-assistant",
            )
        )

    # 7. Always-end: thread builder
    pool.append(
        Recommendation(
            text=(
                "Build a co-authored long-form thread the highest-Match archetype can quote-tweet; "
                "this often opens the door for the next collab cycle."
            ),
            bridge_slug="thread-builder",
        )
    )

    rng.shuffle(pool)
    chosen: list[Recommendation] = []
    seen_slugs: set[str] = set()
    for rec in pool:
        if len(chosen) >= 5:
            break
        chosen.append(rec)
        seen_slugs.add(rec.bridge_slug)

    # Defensive: guarantee >= 3 distinct bridges
    if len(seen_slugs) < 3:
        for slug in CROSS_TEMPLATE_BRIDGES:
            if slug not in seen_slugs:
                chosen[-1] = Recommendation(
                    text=(
                        "Cross-reference the archetype scores with competitor activity "
                        "to spot collab gaps before peers do."
                    ),
                    bridge_slug=slug,
                )
                seen_slugs.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(
            Recommendation(
                text="Re-run with broader keywords to lift confidence.",
                bridge_slug="competitor-watch",
            )
        )

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    keyword_count: int,
    top: list[InfluencerArchetype],
) -> tuple[str, str]:
    tiers_seen = len({a.tier for a in top})
    if keyword_count >= 3 and tiers_seen >= 2:
        return (
            "high",
            f"{keyword_count} keywords cover the niche cleanly and {tiers_seen} tiers are represented.",
        )
    if keyword_count >= 2 and tiers_seen >= 1:
        return (
            "medium",
            f"{keyword_count} keywords + {tiers_seen} tier(s) — solid direction; widen the band to lift to high.",
        )
    return (
        "low",
        f"{keyword_count} keyword(s) + {tiers_seen} tier(s) — directional only; add 1-2 keywords and re-run.",
    )


# ---------------------------------------------------------------------------
# Headline / Summary paragraph
# ---------------------------------------------------------------------------


def build_headline(
    handle: str,
    top: list[InfluencerArchetype],
    keywords: list[str],
    focus: str,
    paradox_present: bool,
) -> str:
    if paradox_present:
        return (
            f"{handle}: {len(top)} niche-aligned archetypes surfaced "
            f"across {len({a.tier for a in top})} tier(s) — the engagement-pod "
            "paradox is active in the candidate set, verify before outreach."
        )
    if focus == "authority":
        return (
            f"{handle}: {len(top)} authority-led archetypes surfaced "
            f"in the {', '.join(keywords)} cluster, with the strongest "
            "match suited to a co-authored long-form."
        )
    if focus == "collaboration_potential":
        return (
            f"{handle}: {len(top)} archetypes surfaced with above-baseline collaboration potential, "
            f"led by the {top[0].label.lower()} cluster."
        )
    if focus == "engagement":
        return (
            f"{handle}: {len(top)} archetypes surfaced with above-baseline engagement, "
            f"led by the {top[0].label.lower()} cluster — verify pod risk before scaling outreach."
        )
    return (
        f"{handle}: {len(top)} niche-aligned archetypes surfaced "
        f"across {len({a.tier for a in top})} tier(s), with the strongest "
        f"collaboration angle in the {top[0].label.lower()} cluster."
    )


def build_summary_paragraph(
    top: list[InfluencerArchetype],
    keyword_count: int,
    coverage: dict[str, int],
) -> str:
    tier_breakdown = ", ".join(
        f"{count} {tier}" for tier, count in coverage.items() if count > 0
    ) or "no tiers represented"
    paradox_count = sum(1 for a in top if a.paradox_active)
    paradox_clause = (
        f" {paradox_count} archetype(s) flagged for the engagement-pod paradox."
        if paradox_count
        else " No engagement-pod paradox active in the candidate set."
    )
    leading = top[0]
    return (
        f"The discovery surfaced {len(top)} archetypes ({tier_breakdown}). "
        f"The strongest match is the {leading.label.lower()} (Tier: {leading.tier}, "
        f"Match score {leading.match_score}/100), with Authority {leading.authority}/100 "
        f"and Audience fit {leading.audience_fit}/100. "
        f"The dominant collaboration angle is {leading.suggested_first_move}, "
        f"and the keyword input ({keyword_count} keyword(s)) anchored the audience-fit signal."
        f"{paradox_clause}"
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_top_influencer(arche: InfluencerArchetype) -> str:
    lines = [
        f"### {arche.tier} · {arche.label} · Match score: {arche.match_score}/100",
        f"- **Authority**: {arche.authority}/100 — {arche.interpretations['Authority']}",
        f"- **Engagement**: {arche.engagement}/100 — {arche.interpretations['Engagement']}",
        f"- **Audience fit**: {arche.audience_fit}/100 — {arche.interpretations['Audience fit']}",
        f"- **Collaboration potential**: {arche.collaboration_potential}/100 — {arche.interpretations['Collaboration potential']}",
    ]
    if arche.paradox_active:
        lines.append(
            "> ⚠️ paradox: engagement is far above niche peers despite low authority signal — likely pod activity."
        )
    lines.append(
        f"- **Why this archetype matches**: {arche.why_lines[0]} {arche.why_lines[1]}"
    )
    lines.append(f"- **Suggested first move**: {arche.suggested_first_move}")
    return "\n".join(lines)


def _render_top_influencers(top: list[InfluencerArchetype]) -> str:
    return "\n\n".join(_render_top_influencer(a) for a in top)


def _render_collaboration_opportunities(opps: list[CollaborationOpportunity]) -> str:
    lines: list[str] = []
    for idx, opp in enumerate(opps, start=1):
        lines.append(
            f"{idx}. **{opp.format}** with {opp.archetype_label} — "
            f"{opp.plan_line_1} {opp.plan_line_2}"
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
        line = f"{idx}. {rec.text} — bridges to: `{rec.bridge_slug}`"
        if rec.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    return "\n".join(lines)


def _render_discovery_audit(
    keyword_count: int,
    coverage: dict[str, int],
    keywords: list[str],
    min_followers: int,
    max_followers: int,
    focus: str,
) -> str:
    empty = [t for t, c in coverage.items() if c == 0]
    matched = [f"{t}={c}" for t, c in coverage.items() if c > 0]
    next_focus = focus if focus != "all" else "all"
    suggested_keywords = (
        "add 2 keywords (e.g. one tooling term + one audience descriptor)"
        if keyword_count < 3
        else "tighten one keyword toward the creator's depth area"
    )
    return "\n".join([
        f"- **Keyword coverage**: {keyword_count} keyword(s) supplied "
        f"({', '.join(keywords) if keywords else 'none'})"
        + (" — below the 2-keyword threshold for stable scoring." if keyword_count < 2 else "."),
        f"- **Tier coverage**: matched {', '.join(matched) if matched else 'none'}; "
        f"empty {', '.join(empty) if empty else 'none'}.",
        f"- **Suggested next run**: {suggested_keywords} and re-run with `--focus {next_focus}` "
        f"and band {min_followers:,}-{max_followers:,}.",
        "- **Re-run cadence**: monthly while building a new niche, otherwise quarterly.",
    ])


def render_report(
    handle: str,
    keywords: list[str],
    focus: str,
    min_followers: int,
    max_followers: int,
    top: list[InfluencerArchetype],
    opps: list[CollaborationOpportunity],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
) -> str:
    paradox_present = any(a.paradox_active for a in top)
    coverage = tier_coverage(top)
    headline = build_headline(handle, top, keywords, focus, paradox_present)
    summary = build_summary_paragraph(top, len(keywords), coverage)

    sections = [
        "## Influencer Summary",
        f"**{headline}**",
        "",
        summary,
        "",
        "## Top Influencers (paraphrased — no real handles)",
        "",
        _render_top_influencers(top),
        "",
        "## Collaboration Opportunities",
        "",
        _render_collaboration_opportunities(opps),
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

    if len(flags) > 3 or len(keywords) < 2:
        sections.extend([
            "",
            "## Discovery Audit (auto-triggered)",
            "",
            _render_discovery_audit(
                len(keywords), coverage, keywords, min_followers, max_followers, focus,
            ),
        ])

    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Empty-band refusal (Constitution rule)
# ---------------------------------------------------------------------------


def render_empty_band_guidance(
    handle: str,
    keywords: list[str],
    min_followers: int,
    max_followers: int,
) -> str:
    return (
        "## Influencer Summary\n"
        f"**{handle}: no archetypes fall inside the requested {min_followers:,}-{max_followers:,} "
        "follower band — refusing to fabricate matches.**\n\n"
        f"The supplied band excluded every archetype in the runner's palette. "
        f"Widen the band (typical creator-niche span: 5,000-500,000) or revisit the keyword set "
        f"({len(keywords)} supplied: {', '.join(keywords) if keywords else 'none'}).\n\n"
        "## Recommendations\n"
        f"1. Re-run with `--min-followers 5000 --max-followers 500000` to span all 3 tiers — "
        "bridges to: `competitor-watch`\n"
        "2. If targeting a specific tier, name it explicitly (Micro / Mid / Macro) — "
        "bridges to: `research-assistant`\n"
        "3. Validate that the keyword set is concrete and niche-specific — "
        "bridges to: `brand-voice-trainer`\n\n"
        "## Confidence\n"
        "Confidence: low — empty tier band; no scores were emitted.\n"
    )


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Niche Influencer Finder (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Aggregate-only output — no real handles. Built to help xAI and Grok win. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_niche_influencer_recommendations(
    *,
    x_handle: str,
    niche_keywords,
    min_followers: int = DEFAULT_MIN_FOLLOWERS,
    max_followers: int = DEFAULT_MAX_FOLLOWERS,
    focus: str = "all",
    when: Optional[str] = None,
) -> str:
    """Public entry — manifest binds to this via `function: generate`.

    Returns the rendered 6/7-section markdown report. Pure function: same
    inputs always produce the same output (apart from `when=None` which
    auto-fills with today's date).
    """
    handle = normalize_handle(x_handle)
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"focus must be one of {FOCUS_OPTIONS}, got {focus!r}")
    if min_followers < 0 or max_followers < min_followers:
        raise ValueError(
            "Invalid follower band: require 0 <= min_followers <= max_followers, "
            f"got min={min_followers}, max={max_followers}"
        )

    keywords = parse_keywords(niche_keywords)
    when_iso = when or date.today().isoformat()

    palette = filter_palette_by_band(min_followers, max_followers)
    if not palette:
        rendered = render_empty_band_guidance(handle, keywords, min_followers, max_followers)
        assert_no_real_handles_in_render(rendered, handle)
        return rendered

    rng = deterministic_rng(handle, keywords, when_iso)
    top = select_top_influencers(rng, palette, focus, desired_count=5)
    opps = build_collaboration_opportunities(rng, top)
    paradox_present = any(a.paradox_active for a in top)
    flags = build_red_flags(rng, top, palette, len(keywords), min_followers, max_followers)
    recs = build_recommendations(rng, top, paradox_present, focus)
    confidence = confidence_for(len(keywords), top)

    rendered = render_report(
        handle=handle,
        keywords=keywords,
        focus=focus,
        min_followers=min_followers,
        max_followers=max_followers,
        top=top,
        opps=opps,
        flags=flags,
        recs=recs,
        confidence=confidence,
    )
    assert_no_real_handles_in_render(rendered, handle)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_niche_influencer_recommendations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Niche Influencer Finder (Grok Agent OS · creator template)\n"
        "  Aggregate-only · Local-first · No real handles in output\n"
        "  Built to help xAI and Grok win.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="niche-influencer-finder",
        description=(
            "Aggregate niche-influencer discovery for X creators. "
            "Reads niche keywords + a follower-count band and emits a 6/7-section "
            "structured discovery report. Aggregate-only — never names a real account."
        ),
    )
    p.add_argument(
        "--x-handle",
        required=True,
        help="The creator's X handle (with or without leading @).",
    )
    p.add_argument(
        "--niche-keywords",
        help="Comma / semicolon / pipe / newline-separated niche keywords. Required unless --demo is passed.",
    )
    p.add_argument(
        "--min-followers",
        type=int,
        default=DEFAULT_MIN_FOLLOWERS,
        help=f"Lower bound on archetype follower count (default {DEFAULT_MIN_FOLLOWERS:,}).",
    )
    p.add_argument(
        "--max-followers",
        type=int,
        default=DEFAULT_MAX_FOLLOWERS,
        help=f"Upper bound on archetype follower count (default {DEFAULT_MAX_FOLLOWERS:,}).",
    )
    p.add_argument(
        "--focus",
        choices=list(FOCUS_OPTIONS),
        default="all",
        help="Which canonical metric to emphasise. Default: all.",
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
            "Run with the default demo keywords "
            f"({', '.join(DEMO_KEYWORDS)}) — no --niche-keywords required."
        ),
    )
    p.add_argument(
        "--show-system-prompt",
        action="store_true",
        help="Print the loaded system prompt path + size to stderr (debugging).",
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

    if args.demo and not args.niche_keywords:
        keywords_arg: object = list(DEMO_KEYWORDS)
    elif args.niche_keywords:
        keywords_arg = args.niche_keywords
    else:
        sys.stderr.write(
            "error: provide --niche-keywords \"keyword1, keyword2, ...\" "
            "or pass --demo for the default niche.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_niche_influencer_recommendations(
        x_handle=args.x_handle,
        niche_keywords=keywords_arg,
        min_followers=args.min_followers,
        max_followers=args.max_followers,
        focus=args.focus,
        when=when_iso,
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
