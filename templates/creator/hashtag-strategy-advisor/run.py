# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Hashtag Strategy Advisor — runner.

CLI entry point for the ``hashtag-strategy-advisor`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a single post topic (URL or pasted text) plus a target platform and
emits a 6/7-section structured hashtag strategy matching ``prompts/system.md``
exactly:

  1. Topic Snapshot
  2. Hashtag Plan (aggregate score across the recommendation set)
  3. Recommended Hashtags (5-10 cards, each with the 4-row Hashtag Plan
     Score table + weighted Hashtag Plan score = round(0.30*Niche +
     0.25*Reach + 0.25*Engagement + 0.20*Cleanliness) + category +
     ship priority)
  4. Strategy Tips (3-5)
  5. Red Flags (2-3, surfaces the reach-without-relevance paradox in
     BOTH the recommendation card AND this section when triggered)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Confidence
  + Optional Hashtag Audit (auto-appended when red_flags > 3 OR
    platform='all')

Hard guarantees enforced by this runner (mirrors the Constitution):

* Drafts only. The runner emits hashtag recommendations the creator
  pastes into their own post copy. Constitution Article II's
  `publish_to_x` consent gate covers the parent post.
* No engagement-bait hashtags. The runner refuses to recommend
  `#FollowForFollow`, `#Like4Like`, `#FF`, `#TeamFollowBack`, or any
  pattern an X policy review would treat as algorithm gaming. The
  blocklist is enforced both on the library (none can be added) and
  on the final output (assert no blocklisted tag appears in the
  rendered text).
* Reach-without-relevance paradox surfaced in BOTH the recommendation
  card AND the Red Flags section whenever Reach potential > 70 AND
  Niche relevance < 35. The `--demo` mode pins `#AI` into the set
  with low Niche relevance so the rule reliably demonstrates.
* Platform-specific ship caps (X = 0-2, LinkedIn = 0-3) stated in
  every output even when the analysis surfaces 10 tags scoring above
  70 — over-stuffing is the anti-pattern.
* Honest `trending` category check. A tag is `trending` only when the
  post topic matches the tag's documented trigger keywords; otherwise
  the trending category is intentionally empty in the recommendation
  set and the audit notes it.
* Branded-tag-too-early as a soft warning. The runner generates a
  branded tag from the creator's handle (e.g. `#JanSol0sNotes`) and
  marks it `low` ship priority + emits a note explaining that branded
  tags compound only after 4-6+ months of consistent use.
* Hashtag Plan score formula is fixed:
    round(0.30*Niche relevance + 0.25*Reach potential +
          0.25*Engagement quality + 0.20*Cleanliness).
  Niche relevance weighted highest because off-niche tags poison the
  audience signal more than they help reach.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any monetization-
  related recommendation.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + topic +
  platform + num_hashtags + focus + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_hashtag_strategy

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

SCORE_METRICS = (
    "Niche relevance",
    "Reach potential",
    "Engagement quality",
    "Cleanliness",
)

# Hashtag Plan score weights — Niche relevance weighted highest because
# off-niche tags poison the audience signal more than they help reach.
HASHTAG_PLAN_WEIGHTS = {
    "Niche relevance": 0.30,
    "Reach potential": 0.25,
    "Engagement quality": 0.25,
    "Cleanliness": 0.20,
}

PLATFORM_OPTIONS = ("x", "linkedin", "all")
FOCUS_OPTIONS = ("reach", "engagement", "niche", "all")

# Per-platform ship caps (lower, upper). Stated in every output even
# when the analysis surfaces more tags scoring above 70.
PLATFORM_SHIP_CAPS = {
    "x": (0, 2),
    "linkedin": (0, 3),
}

MIN_HASHTAGS = 5
MAX_HASHTAGS = 10

CATEGORIES = (
    "broad-niche",
    "specific-niche",
    "trending",
    "community",
    "branded",
)

# Engagement-bait hashtags that are a HARD REFUSAL — never recommend.
# The blocklist is enforced both at library-load and at output-emit.
ENGAGEMENT_BAIT_BLOCKLIST = frozenset({
    "#followforfollow", "#follow4follow", "#f4f",
    "#likeforlike", "#like4like", "#l4l",
    "#ff", "#followfriday",
    "#teamfollowback", "#tfb",
    "#followtrain", "#followback",
    "#like4tag", "#likebackalways",
})

# Cross-template bridges
CROSS_TEMPLATE_BRIDGES = (
    "content-idea-generator",
    "thread-builder",
    "analytics-summarizer",
    "cross-platform-reposter",
    "competitor-watch",
    "brand-voice-trainer",
    "ab-test-suggester",
    "comment-engagement-booster",
    "mention-summarizer",
    "monetization-optimizer",
    "content-recycler",
    "research-assistant",
)

ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

DEMO_HANDLE = "@JanSol0s"
DEMO_POST_TOPIC = (
    "Most agent eval suites measure the wrong thing — "
    "they reward verbosity, not action correctness."
)

DEMO_PRODUCTIVITY_HANDLE = "@habitstacker"
DEMO_PRODUCTIVITY_TOPIC = (
    "Stop optimizing for the morning routine — optimize for the friction "
    "your evening self leaves the morning self to clean up."
)

# X URL pattern with handle capture
_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})/status/(\d+)/?",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,15}(?![A-Za-z0-9_])"
)
_HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")


# ---------------------------------------------------------------------------
# Hashtag library
# ---------------------------------------------------------------------------

# Each entry:
#   tag                 — the hashtag (with `#`)
#   category            — one of CATEGORIES
#   niche_keywords      — keywords the runner matches against the topic
#                         to decide whether this tag is relevant
#   trigger_keywords    — for `trending` category: the runner only includes
#                         a trending tag when the topic matches one of these.
#                         Empty for non-trending categories.
#   base_relevance      — typical Niche relevance baseline (0-100)
#   base_reach          — typical Reach potential baseline
#   base_engagement     — typical Engagement quality baseline
#   base_cleanliness    — typical anti-spam Cleanliness baseline
#
# These bases are nudged by the deterministic RNG by ±3 points and by the
# focus-flag (+4 to the matching metric). Keeping the library curated and
# tight (~25 entries) means the runner can hit a 5-category mix on common
# creator topics while honestly admitting when a category has no fit.
HASHTAG_LIBRARY = (
    # broad-niche — wide audience, moderate relevance
    {
        "tag": "#AI",
        "category": "broad-niche",
        "niche_keywords": ("ai", "model", "agent", "llm", "ml", "intelligence"),
        "trigger_keywords": (),
        "base_relevance": 28,
        "base_reach": 90,
        "base_engagement": 38,
        "base_cleanliness": 30,
    },
    {
        "tag": "#Productivity",
        "category": "broad-niche",
        "niche_keywords": ("productivity", "habit", "routine", "deep", "focus", "work"),
        "trigger_keywords": (),
        "base_relevance": 48,
        "base_reach": 85,
        "base_engagement": 44,
        "base_cleanliness": 50,
    },
    {
        "tag": "#Tech",
        "category": "broad-niche",
        "niche_keywords": ("tech", "software", "engineer", "code", "build"),
        "trigger_keywords": (),
        "base_relevance": 36,
        "base_reach": 88,
        "base_engagement": 36,
        "base_cleanliness": 32,
    },
    # specific-niche — high relevance, moderate reach
    {
        "tag": "#LLMOps",
        "category": "specific-niche",
        "niche_keywords": ("agent", "llm", "eval", "infra", "ops", "ai", "model"),
        "trigger_keywords": (),
        "base_relevance": 88,
        "base_reach": 60,
        "base_engagement": 76,
        "base_cleanliness": 84,
    },
    {
        "tag": "#AgentEval",
        "category": "specific-niche",
        "niche_keywords": ("agent", "eval", "llm", "benchmark", "metric", "correctness"),
        "trigger_keywords": (),
        "base_relevance": 90,
        "base_reach": 50,
        "base_engagement": 78,
        "base_cleanliness": 86,
    },
    {
        "tag": "#HabitStacking",
        "category": "specific-niche",
        "niche_keywords": ("habit", "stack", "routine", "morning", "evening", "stacking"),
        "trigger_keywords": (),
        "base_relevance": 90,
        "base_reach": 52,
        "base_engagement": 74,
        "base_cleanliness": 84,
    },
    {
        "tag": "#DeepWork",
        "category": "specific-niche",
        "niche_keywords": ("deep", "focus", "work", "concentration", "attention"),
        "trigger_keywords": (),
        "base_relevance": 86,
        "base_reach": 56,
        "base_engagement": 72,
        "base_cleanliness": 82,
    },
    {
        "tag": "#AgentInfra",
        "category": "specific-niche",
        "niche_keywords": ("agent", "infra", "infrastructure", "platform", "ops"),
        "trigger_keywords": (),
        "base_relevance": 88,
        "base_reach": 48,
        "base_engagement": 74,
        "base_cleanliness": 84,
    },
    {
        "tag": "#PromptEng",
        "category": "specific-niche",
        "niche_keywords": ("prompt", "llm", "engineering", "model", "ai"),
        "trigger_keywords": (),
        "base_relevance": 84,
        "base_reach": 62,
        "base_engagement": 70,
        "base_cleanliness": 78,
    },
    # trending — gated on topic matching trigger_keywords
    {
        "tag": "#XMoney",
        "category": "trending",
        "niche_keywords": ("money", "payment", "creator", "economy", "tier", "monetiz"),
        "trigger_keywords": ("money", "payment", "monetiz", "creator economy"),
        "base_relevance": 80,
        "base_reach": 78,
        "base_engagement": 70,
        "base_cleanliness": 72,
    },
    {
        "tag": "#GrokAgents",
        "category": "trending",
        "niche_keywords": ("grok", "agent", "ai"),
        "trigger_keywords": ("grok", "xai"),
        "base_relevance": 86,
        "base_reach": 70,
        "base_engagement": 72,
        "base_cleanliness": 78,
    },
    # community — culture / movement tags
    {
        "tag": "#BuildInPublic",
        "category": "community",
        "niche_keywords": ("ship", "build", "launch", "public", "iterate"),
        "trigger_keywords": (),
        "base_relevance": 64,
        "base_reach": 72,
        "base_engagement": 70,
        "base_cleanliness": 76,
    },
    {
        "tag": "#100DaysOfCode",
        "category": "community",
        "niche_keywords": ("code", "build", "learn"),
        "trigger_keywords": (),
        "base_relevance": 56,
        "base_reach": 70,
        "base_engagement": 64,
        "base_cleanliness": 74,
    },
    {
        "tag": "#IndieHacker",
        "category": "community",
        "niche_keywords": ("indie", "ship", "build", "founder", "solo"),
        "trigger_keywords": (),
        "base_relevance": 60,
        "base_reach": 66,
        "base_engagement": 68,
        "base_cleanliness": 72,
    },
    {
        "tag": "#WriteEveryDay",
        "category": "community",
        "niche_keywords": ("write", "writing", "essay", "habit", "routine"),
        "trigger_keywords": (),
        "base_relevance": 60,
        "base_reach": 64,
        "base_engagement": 66,
        "base_cleanliness": 74,
    },
)


# Branded-tag template — the runner generates `#<HandleNotes>` for the
# creator from their --x-handle, with low-but-honest scores.
def _branded_tag_for(handle: str) -> dict:
    bare = handle.lstrip("@")
    tag = f"#{bare}Notes"
    return {
        "tag": tag,
        "category": "branded",
        "niche_keywords": (),  # always picked when explicitly slotted
        "trigger_keywords": (),
        "base_relevance": 92,   # by definition the creator's own
        "base_reach": 24,       # initial reach is just the creator's audience
        "base_engagement": 70,
        "base_cleanliness": 90,
    }


# ---------------------------------------------------------------------------
# Library invariants — engagement-bait blocklist enforced at import
# ---------------------------------------------------------------------------


def _validate_library() -> None:
    for entry in HASHTAG_LIBRARY:
        if entry["tag"].lower() in ENGAGEMENT_BAIT_BLOCKLIST:
            raise RuntimeError(
                f"Hashtag library contains a blocklisted engagement-bait tag: "
                f"{entry['tag']}. Constitution rule 2 violation."
            )
        if entry["category"] not in CATEGORIES:
            raise RuntimeError(
                f"Hashtag library entry {entry['tag']} has invalid category "
                f"{entry['category']!r}; must be one of {CATEGORIES}."
            )


_validate_library()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TopicSnapshot:
    handle: str
    text: str
    url: Optional[str]
    char_count: int
    summary: str
    tone_signal: str
    tokens: tuple


@dataclass
class HashtagRecommendation:
    tag: str
    category: str
    niche_relevance: int
    reach_potential: int
    engagement_quality: int
    cleanliness: int
    plan_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)
    why_fits: str = ""
    ship_priority: str = "low"


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
# Privacy guard + engagement-bait output guard
# ---------------------------------------------------------------------------


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Hashtag Strategy Advisor privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


def assert_no_engagement_bait_in_render(rendered: str) -> None:
    for tag in _HASHTAG_RE.findall(rendered):
        if tag.lower() in ENGAGEMENT_BAIT_BLOCKLIST:
            raise RuntimeError(
                f"Hashtag Strategy Advisor refused: engagement-bait tag {tag} "
                "appeared in the rendered output (Constitution rule 2)."
            )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def parse_topic(post_topic_or_text: str, fallback_handle: str) -> TopicSnapshot:
    raw = (post_topic_or_text or "").strip()
    if not raw:
        raise ValueError(
            "post_topic_or_text is empty. Pass either an x.com URL or the literal post topic."
        )
    m = _URL_RE.match(raw)
    if m:
        url_handle = "@" + m.group(1)
        return TopicSnapshot(
            handle=url_handle,
            text=(
                "[topic URL supplied; runner is offline so the body is referenced "
                "by URL only — paste the literal topic text for richer recommendations]"
            ),
            url=raw,
            char_count=0,
            summary="(see source URL — runner cannot fetch in v1)",
            tone_signal="thoughtful",
            tokens=(),
        )
    text = raw
    return TopicSnapshot(
        handle=fallback_handle,
        text=text,
        url=None,
        char_count=len(text),
        summary=_extract_summary(text),
        tone_signal=_infer_tone(text),
        tokens=tuple(_tokenize(text)),
    )


def _extract_summary(text: str) -> str:
    candidate = re.split(r"(?<=[.!?])\s+|\s+—\s+", text.strip(), maxsplit=1)[0].strip()
    if len(candidate) > 140:
        candidate = candidate[:137].rstrip() + "..."
    return candidate or text.strip()[:140]


def _infer_tone(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("study", "data", "%", "benchmark", "stats", "numbers")):
        return "data-led"
    if any(k in lower for k in ("?", "you know", "imo")):
        return "conversational"
    if len(text) < 180 and any(k in lower for k in ("hot take", "wrong", "stop", "actually")):
        return "punchy"
    return "thoughtful"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", text.lower())


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str, topic_text: str, platform: str, num_hashtags: int,
    focus: str, when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(topic_text.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(platform.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(str(num_hashtags).encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(focus.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Hashtag selection (topic-matching + category spread)
# ---------------------------------------------------------------------------


def keyword_match_score(tokens: tuple, niche_keywords: tuple) -> int:
    """Count of niche_keywords that appear (substring or whole-token)
    in the topic tokens. Returns 0 if no match.
    """
    if not niche_keywords:
        return 0
    score = 0
    token_set = set(tokens)
    joined = " ".join(tokens)
    for kw in niche_keywords:
        kw_lower = kw.lower()
        if kw_lower in token_set or kw_lower in joined:
            score += 1
    return score


def select_hashtags(
    rng: Random,
    topic: TopicSnapshot,
    handle: str,
    num: int,
    demo_paradox: bool,
) -> list[dict]:
    """Pick `num` hashtag entries. Ensures category spread (3+ when
    library + topic permit) and includes the branded tag for the creator.
    In demo_paradox mode, force-include #AI even if the topic doesn't
    fully match — so the reach-without-relevance paradox demonstrates.
    """
    num = max(MIN_HASHTAGS, min(MAX_HASHTAGS, num))

    # Score every library entry against the topic
    scored: list[tuple[int, dict]] = []
    for entry in HASHTAG_LIBRARY:
        # Honest trending check — only include trending tag if topic
        # matches its trigger keywords
        if entry["category"] == "trending":
            if entry["trigger_keywords"]:
                if not any(
                    trig.lower() in topic.text.lower()
                    for trig in entry["trigger_keywords"]
                ):
                    continue
            else:
                # No trigger keywords means no honest trending claim
                continue
        match = keyword_match_score(topic.tokens, entry["niche_keywords"])
        if match > 0:
            scored.append((match, entry))

    # Sort by match desc, then deterministic shuffle within match-ties
    scored.sort(key=lambda x: (-x[0], x[1]["tag"]))

    # Always include the branded tag (low ship priority)
    branded = _branded_tag_for(handle)

    # Build the selection — prefer category spread
    selected: list[dict] = []
    used_tags: set[str] = set()
    used_categories: set[str] = set()

    # First pass: pick top scorer from each non-branded category
    for category in ("specific-niche", "broad-niche", "community", "trending"):
        for _score, entry in scored:
            if entry["tag"] in used_tags:
                continue
            if entry["category"] == category:
                selected.append(entry)
                used_tags.add(entry["tag"])
                used_categories.add(category)
                break

    # If demo_paradox and #AI not yet selected, force-include it
    if demo_paradox:
        ai_entry = next((e for e in HASHTAG_LIBRARY if e["tag"] == "#AI"), None)
        if ai_entry and ai_entry["tag"] not in used_tags:
            selected.append(ai_entry)
            used_tags.add(ai_entry["tag"])
            used_categories.add(ai_entry["category"])

    # Always include branded
    if branded["tag"] not in used_tags:
        selected.append(branded)
        used_tags.add(branded["tag"])
        used_categories.add("branded")

    # Fill remaining slots from highest-scoring unused entries (only entries
    # that genuinely matched the topic — never pad with off-niche tags)
    for _score, entry in scored:
        if len(selected) >= num:
            break
        if entry["tag"] not in used_tags:
            selected.append(entry)
            used_tags.add(entry["tag"])

    # If still short (e.g. very narrow topic), the runner emits fewer than
    # `num` recommendations rather than padding with off-niche tags. The
    # confidence line and Hashtag Audit will note the thin spread.

    # Stable order — keep first-pick precedence (already by score+category)
    return selected[:num]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_hashtag(
    rng: Random,
    entry: dict,
    topic: TopicSnapshot,
    focus: str,
) -> HashtagRecommendation:
    # Nudge ±3 around the base
    relevance = entry["base_relevance"] + rng.randint(-3, 3)
    reach = entry["base_reach"] + rng.randint(-3, 3)
    engagement = entry["base_engagement"] + rng.randint(-3, 3)
    cleanliness = entry["base_cleanliness"] + rng.randint(-3, 3)

    # Focus nudge (+4 to the focused metric)
    if focus == "niche":
        relevance = min(100, relevance + 4)
    elif focus == "reach":
        reach = min(100, reach + 4)
    elif focus == "engagement":
        engagement = min(100, engagement + 4)
    # focus == "all" applies no nudge

    # Clamp 0-100
    relevance = max(0, min(100, relevance))
    reach = max(0, min(100, reach))
    engagement = max(0, min(100, engagement))
    cleanliness = max(0, min(100, cleanliness))

    plan_score = round(
        HASHTAG_PLAN_WEIGHTS["Niche relevance"] * relevance
        + HASHTAG_PLAN_WEIGHTS["Reach potential"] * reach
        + HASHTAG_PLAN_WEIGHTS["Engagement quality"] * engagement
        + HASHTAG_PLAN_WEIGHTS["Cleanliness"] * cleanliness
    )

    paradox = (reach > 70) and (relevance < 35)

    interp = {
        "Niche relevance": _interp_relevance(relevance, entry["category"]),
        "Reach potential": _interp_reach(reach),
        "Engagement quality": _interp_engagement(engagement),
        "Cleanliness": _interp_cleanliness(cleanliness),
    }

    why = _why_fits(entry, topic, paradox)

    return HashtagRecommendation(
        tag=entry["tag"],
        category=entry["category"],
        niche_relevance=relevance,
        reach_potential=reach,
        engagement_quality=engagement,
        cleanliness=cleanliness,
        plan_score=plan_score,
        paradox_active=paradox,
        interpretations=interp,
        why_fits=why,
        ship_priority="medium",  # filled later by ship-priority pass
    )


def _interp_relevance(score: int, category: str) -> str:
    if category == "branded":
        return "By definition aligned to the creator's niche."
    if score >= 70:
        return "Sits inside the creator's stated cluster."
    if score >= 50:
        return "Solid niche overlap; adjacent-niche tail dilutes the core."
    return "Too broad; pulls in non-niche audience."


def _interp_reach(score: int) -> str:
    if score >= 75:
        return "Massive audience; high impression potential."
    if score >= 55:
        return "Moderate audience; growing."
    return "Small but rapidly engaged audience; initial reach is the creator's followers."


def _interp_engagement(score: int) -> str:
    if score >= 70:
        return "Niche-active accounts dominate; substantive replies common."
    if score >= 50:
        return "Mixed engagement; substantive + drive-by likes both present."
    return "Drive-by likes dominate; low substantive reply density."


def _interp_cleanliness(score: int) -> str:
    if score >= 75:
        return "Low spam exposure."
    if score >= 55:
        return "Moderate spam exposure; community moderation visible."
    return "Heavy bot / engagement-pod traffic — tag carries reputation risk."


def _why_fits(entry: dict, topic: TopicSnapshot, paradox: bool) -> str:
    if entry["category"] == "branded":
        return (
            "Builds long-term branded-tag equity through consistent use across the "
            "creator's posts."
        )
    if paradox:
        return (
            "Tag is technically related to the topic but the audience is misaligned — "
            "broad-niche tags pull in drive-bys rather than niche peers."
        )
    if entry["category"] == "trending":
        return "Documented current velocity — pairs well with the post topic this week."
    if entry["category"] == "community":
        return "Tribal / culture tag — fits the creator's posting style and signals tribe membership."
    if entry["category"] == "specific-niche":
        return "Direct semantic match to the topic; pairs with adjacent specific-niche tags."
    return "Broad-niche audience; useful when paired with at least one specific-niche tag."


# ---------------------------------------------------------------------------
# Ship priority assignment (per platform cap)
# ---------------------------------------------------------------------------


def assign_ship_priorities(
    recs: list[HashtagRecommendation], platform: str,
) -> None:
    """Mark ship priority high/medium/low. The platform's ship cap
    (X = 0-2, LinkedIn = 0-3, all = both) determines how many can be
    `high` priority simultaneously.
    """
    # Sort by Hashtag Plan score desc
    sorted_idx = sorted(
        range(len(recs)), key=lambda i: -recs[i].plan_score,
    )

    if platform == "all":
        # Use LinkedIn's larger cap (0-3) for assigning highs
        high_cap = 3
    else:
        high_cap = PLATFORM_SHIP_CAPS.get(platform, (0, 2))[1]

    # Branded always low ship priority for first-time use
    high_count = 0
    for i in sorted_idx:
        rec = recs[i]
        if rec.category == "branded":
            rec.ship_priority = "low"
            continue
        if rec.paradox_active:
            rec.ship_priority = "low"
            continue
        if high_count < high_cap and rec.plan_score >= 65:
            rec.ship_priority = "high"
            high_count += 1
        elif rec.plan_score >= 55:
            rec.ship_priority = "medium"
        else:
            rec.ship_priority = "low"


# ---------------------------------------------------------------------------
# Strategy tips
# ---------------------------------------------------------------------------


def build_strategy_tips(
    platform: str,
    recs: list[HashtagRecommendation],
) -> list[tuple[str, str]]:
    tips = []

    has_branded = any(r.category == "branded" for r in recs)
    has_specific = any(r.category == "specific-niche" for r in recs)
    has_broad = any(r.category == "broad-niche" for r in recs)
    has_community = any(r.category == "community" for r in recs)
    has_trending = any(r.category == "trending" for r in recs)

    if has_specific:
        tips.append((
            "Ship 1 specific-niche tag, not 2",
            "On X, one well-chosen specific-niche tag often outperforms a paired stack — "
            "the algorithm penalises hashtag-heavy posts.",
        ))
    if has_broad and platform in ("linkedin", "all"):
        tips.append((
            "Hold broad-niche tags for LinkedIn",
            "LinkedIn's longer post format absorbs broad-niche tags better than X's reply "
            "surface; reserve broad-niche for the LinkedIn variant via cross-platform-reposter.",
        ))
    if has_branded:
        tips.append((
            "Build the branded-tag habit slowly",
            "Branded tags compound only when used consistently across 4-6+ months. Use "
            "sparingly until the habit is locked.",
        ))
    if has_community:
        tips.append((
            "Community tags work best on the post that earns them",
            "Don't bolt a community tag onto a post that doesn't actually speak to the "
            "tribe — community moderation reads off-topic stuffing as noise.",
        ))
    if has_trending:
        tips.append((
            "Verify trending velocity before shipping",
            "Trending tags fade fast; check the documented velocity in the last 24h before "
            "pinning your post to one.",
        ))
    if not has_trending:
        tips.append((
            "No honest trending tag fit this topic",
            "The runner found no trending tag whose trigger keywords match the topic. "
            "Riding an unrelated trending tag is algorithm-manipulation and refused outright.",
        ))

    return tips[:5]


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    recs: list[HashtagRecommendation],
    platform: str,
    topic: TopicSnapshot,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: reach-without-relevance paradox
    paradox_recs = [r for r in recs if r.paradox_active]
    if paradox_recs:
        names = ", ".join(r.tag for r in paradox_recs)
        flags.append(RedFlag(
            title="Reach-without-relevance paradox",
            severity="high",
            explanation=(
                f"{names} score Reach potential above 70 while Niche relevance sits "
                "below 35. Using these tags brings drive-by impressions, not the creator's "
                "people."
            ),
            remediation=(
                f"Skip {names} on X (cap 0-2 means every slot must earn its place); "
                "consider on LinkedIn where the format absorbs broader tags."
            ),
        ))

    # Rule 2: branded-tag-too-early (educational soft warning)
    branded = [r for r in recs if r.category == "branded"]
    if branded:
        flags.append(RedFlag(
            title="Branded-tag-too-early",
            severity="low",
            explanation=(
                f"{branded[0].tag} is the creator's own tag; initial reach is just the "
                "existing follower base. Branded tags compound only after 4-6+ months of "
                "consistent use."
            ),
            remediation=(
                "Use the branded tag sparingly until follower count and consistent-use "
                "habit are both locked."
            ),
        ))

    # Rule 3: trending category empty (when the topic could plausibly carry one)
    has_trending = any(r.category == "trending" for r in recs)
    if not has_trending and topic.tokens:
        # Only mention if topic has at least one trending-related word; otherwise quiet
        trending_hints = ("money", "agent", "ai", "grok", "creator")
        if any(hint in topic.text.lower() for hint in trending_hints):
            flags.append(RedFlag(
                title="No honest trending tag fits",
                severity="low",
                explanation=(
                    "The runner found no trending tag whose documented current velocity "
                    "matches the post topic. Riding an unrelated trending tag would be "
                    "algorithm-manipulation."
                ),
                remediation=(
                    "Skip trending tags this round; revisit when a niche-aligned launch "
                    "actually trends."
                ),
            ))

    # Rule 4: over-stuffing risk if the user requested num_hashtags > platform cap
    cap = PLATFORM_SHIP_CAPS.get(platform, (0, 3))[1] if platform != "all" else 3
    if len(recs) > cap + 2:
        flags.append(RedFlag(
            title="Over-stuffing risk",
            severity="medium" if len(recs) > cap + 4 else "low",
            explanation=(
                f"The runner surfaced {len(recs)} tags but the {platform} ship cap is "
                f"0-{cap}. Posting more than {cap} tags is the over-stuffing anti-pattern."
            ),
            remediation=(
                f"Pick the top {cap} `high` priority tags from the recommendation set; "
                "hold the rest for sibling posts in the same week."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    recs: list[HashtagRecommendation],
    platform: str,
    paradox_present: bool,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    pool.append(Recommendation(
        text=(
            "Snapshot per-hashtag impressions and reply rate at T+24h via "
            "`analytics-summarizer` to log which tags compound for this audience."
        ),
        bridge_slug="analytics-summarizer",
    ))
    if any(r.category == "specific-niche" for r in recs):
        specific_tags = [r for r in recs if r.category == "specific-niche"][:2]
        if len(specific_tags) >= 2:
            pool.append(Recommendation(
                text=(
                    f"A/B-test single-tag ({specific_tags[0].tag}) vs paired-tag "
                    f"({specific_tags[0].tag} {specific_tags[1].tag}) over 2 weeks via `ab-test-suggester`."
                ),
                bridge_slug="ab-test-suggester",
            ))
        else:
            pool.append(Recommendation(
                text=(
                    "A/B-test 1-tag vs 2-tag posts on X over a 2-week window via "
                    "`ab-test-suggester`."
                ),
                bridge_slug="ab-test-suggester",
            ))
    pool.append(Recommendation(
        text=(
            "Watch competitor formats via `competitor-watch` to see whether the "
            "broad-niche tags this report flagged are over-used in the niche."
        ),
        bridge_slug="competitor-watch",
    ))
    if platform == "all" or platform == "linkedin":
        pool.append(Recommendation(
            text=(
                "Adapt the hashtag set when cross-posting via `cross-platform-reposter` "
                "— X 0-2, LinkedIn 0-3, Bluesky 0-2, Newsletter 0."
            ),
            bridge_slug="cross-platform-reposter",
        ))
    pool.append(Recommendation(
        text=(
            "Source the next anchor post in the cluster of the highest-scoring tag via "
            "`content-idea-generator`."
        ),
        bridge_slug="content-idea-generator",
    ))
    if paradox_present:
        pool.append(Recommendation(
            text=(
                "For paradox-flagged tags, verify audience quality via "
                "`follower-quality-analyzer` before choosing to ship them anyway."
            ),
            bridge_slug="follower-quality-analyzer",
        ))
    pool.append(Recommendation(
        text=(
            "If the post leads to a paid-tier launch, pair the strategy with "
            "`monetization-optimizer` before scaling the tag set."
        ),
        bridge_slug="monetization-optimizer",
        monetization=True,
    ))

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
                        "Cross-reference the hashtag scores with last week's analytics "
                        "to spot which tags compounded best for this voice."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(Recommendation(
            text="Re-run with a sharper post topic to lift confidence.",
            bridge_slug="brand-voice-trainer",
        ))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence + aggregate score
# ---------------------------------------------------------------------------


def aggregate_plan_score(recs: list[HashtagRecommendation]) -> int:
    if not recs:
        return 0
    return round(sum(r.plan_score for r in recs) / len(recs))


def confidence_for(
    topic: TopicSnapshot,
    recs: list[HashtagRecommendation],
    platform: str,
) -> tuple[str, str]:
    src_clear = topic.char_count >= 60 and topic.url is None
    avg = aggregate_plan_score(recs)
    categories_seen = len({r.category for r in recs})
    if src_clear and avg >= 65 and categories_seen >= 3:
        return ("high", f"clear topic, {len(recs)} hashtags spanning {categories_seen} categories, ship cap stated explicitly.")
    if avg >= 55:
        return ("medium", f"average Hashtag Plan score {avg}/100 — solid direction; tighten focus or paste literal topic for higher confidence.")
    return ("low", f"average Hashtag Plan score {avg}/100 — supply richer topic text or pick a specific niche.")


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _ship_cap_line(platform: str) -> str:
    if platform == "all":
        return "0-2 (X) · 0-3 (LinkedIn) — both reported separately"
    cap = PLATFORM_SHIP_CAPS.get(platform, (0, 3))
    plat_name = "X" if platform == "x" else "LinkedIn"
    return f"0-{cap[1]} ({plat_name})"


def _render_topic_snapshot(
    topic: TopicSnapshot, platform: str, focus: str,
) -> str:
    headline = topic.summary
    if len(headline) > 140:
        headline = headline[:137].rstrip() + "..."
    return "\n".join([
        "## Topic Snapshot",
        f"**{topic.handle}: hashtags should land in the niche cluster, not the wider conversation.**",
        "",
        f"- **Creator handle**: {topic.handle}",
        f"- **Topic / post**: {headline}",
        f"- **Target platform**: {platform}",
        f"- **Ship cap**: {_ship_cap_line(platform)}",
        f"- **Focus**: {focus}",
    ])


def _render_hashtag_plan(recs: list[HashtagRecommendation]) -> str:
    avg = aggregate_plan_score(recs)
    return "\n".join([
        "## Hashtag Plan",
        "",
        f"**Aggregate Hashtag Plan score**: {avg}/100 — averaged across {len(recs)} recommendations.",
    ])


def _render_recommendation_card(r: HashtagRecommendation) -> str:
    lines = [
        f"### {r.tag} · category: {r.category} · Hashtag Plan score: {r.plan_score}/100",
        f"- **Niche relevance**: {r.niche_relevance}/100 — {r.interpretations['Niche relevance']}",
        f"- **Reach potential**: {r.reach_potential}/100 — {r.interpretations['Reach potential']}",
        f"- **Engagement quality**: {r.engagement_quality}/100 — {r.interpretations['Engagement quality']}",
        f"- **Cleanliness**: {r.cleanliness}/100 — {r.interpretations['Cleanliness']}",
    ]
    if r.paradox_active:
        lines.append(
            "> ⚠️ paradox: hashtag has audience but it's the wrong audience — using it brings drive-bys, not the creator's people."
        )
    lines.append(f"- **Why this fits**: {r.why_fits}")
    lines.append(f"- **Ship priority**: {r.ship_priority}")
    return "\n".join(lines)


def _render_recommended_hashtags(recs: list[HashtagRecommendation]) -> str:
    return "## Recommended Hashtags\n\n" + "\n\n".join(
        _render_recommendation_card(r) for r in recs
    )


def _render_strategy_tips(tips: list[tuple[str, str]]) -> str:
    return "## Strategy Tips\n\n" + "\n".join(
        f"{i}. **{t[0]}** — {t[1]}" for i, t in enumerate(tips, start=1)
    )


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs_pool: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    monetization_emitted = False
    for i, rec in enumerate(recs_pool, start=1):
        line = f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`"
        if rec.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    return "\n".join(lines)


def _render_hashtag_audit(
    topic: TopicSnapshot,
    recs: list[HashtagRecommendation],
    platform: str,
) -> str:
    categories_seen = sorted({r.category for r in recs})
    branded = next((r for r in recs if r.category == "branded"), None)
    has_trending = any(r.category == "trending" for r in recs)
    return "\n".join([
        "## Hashtag Audit (auto-triggered)",
        "",
        f"- **Topic clarity**: {'clear, single-claim topic' if topic.url is None and topic.char_count >= 60 else 'URL-only or thin topic source'}.",
        f"- **Category spread**: {len(categories_seen)} categories ({', '.join(categories_seen)}); spread is "
        + ("healthy" if len(categories_seen) >= 3 else "concentrated — widen via more specific-niche or community tags") + ".",
        f"- **Branded-tag readiness**: {('branded tag ' + branded.tag + ' included with low ship priority — held for habit-building') if branded else 'no branded tag in this set'}.",
        f"- **Suggested next run**: ship 1 specific-niche tag on X; add 1 community tag on LinkedIn; "
        + ("verify trending tag's velocity before shipping" if has_trending else "no honest trending fit, skip the trending category") + ".",
        "- **Re-run cadence**: monthly while building niche presence, otherwise per-major-launch.",
    ])


def render_report(
    topic: TopicSnapshot,
    platform: str,
    focus: str,
    recs: list[HashtagRecommendation],
    flags: list[RedFlag],
    bridges: list[Recommendation],
    confidence: tuple[str, str],
    tips: list[tuple[str, str]],
) -> str:
    sections = [
        _render_topic_snapshot(topic, platform, focus),
        "",
        _render_hashtag_plan(recs),
        "",
        _render_recommended_hashtags(recs),
        "",
        _render_strategy_tips(tips),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(bridges),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    if len(flags) > 3 or platform == "all":
        sections.extend([
            "",
            _render_hashtag_audit(topic, recs, platform),
        ])

    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Hashtag Strategy Advisor (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for xAI, X, Grok and the ecosystem community. ❤️ -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_hashtag_strategy(
    *,
    x_handle: str,
    post_topic_or_text: str,
    platform: str = "x",
    num_hashtags: int = 5,
    focus: str = "all",
    when: Optional[str] = None,
    demo_paradox: bool = False,
) -> str:
    handle = normalize_handle(x_handle)
    if platform not in PLATFORM_OPTIONS:
        raise ValueError(f"platform must be one of {PLATFORM_OPTIONS}, got {platform!r}")
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"focus must be one of {FOCUS_OPTIONS}, got {focus!r}")
    if not (MIN_HASHTAGS <= num_hashtags <= MAX_HASHTAGS):
        raise ValueError(
            f"num_hashtags must be in [{MIN_HASHTAGS}, {MAX_HASHTAGS}], got {num_hashtags}"
        )

    topic = parse_topic(post_topic_or_text, handle)
    when_iso = when or date.today().isoformat()

    rng = deterministic_rng(handle, topic.text, platform, num_hashtags, focus, when_iso)
    selected = select_hashtags(rng, topic, handle, num_hashtags, demo_paradox)

    # Score each selected hashtag with a per-tag RNG fork
    recs: list[HashtagRecommendation] = []
    for entry in selected:
        # Fork RNG for per-tag determinism with stable order
        per_tag_seed = hashlib.sha256(
            (rng.randbytes(8).hex() + entry["tag"]).encode("utf-8")
        ).digest()[:8]
        per_tag_rng = Random(int.from_bytes(per_tag_seed, "big"))
        recs.append(score_hashtag(per_tag_rng, entry, topic, focus))

    # Assign ship priorities given platform cap
    assign_ship_priorities(recs, platform)

    # Sort by plan_score desc for presentation
    recs.sort(key=lambda r: -r.plan_score)

    flags = build_red_flags(recs, platform, topic)
    paradox_present = any(r.paradox_active for r in recs)
    bridges = build_recommendations(rng, recs, platform, paradox_present)
    confidence = confidence_for(topic, recs, platform)
    tips = build_strategy_tips(platform, recs)

    rendered = render_report(
        topic=topic,
        platform=platform,
        focus=focus,
        recs=recs,
        flags=flags,
        bridges=bridges,
        confidence=confidence,
        tips=tips,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    assert_no_engagement_bait_in_render(rendered)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_hashtag_strategy


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Hashtag Strategy Advisor (Grok Agent OS · creator template)\n"
        "  Drafts only · Ship caps explicit · No engagement-bait tags\n"
        "  Built for xAI, X, Grok and the ecosystem community. ❤️\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hashtag-strategy-advisor",
        description=(
            "Turn a post topic into a 5-10 hashtag strategy spread across the "
            "5 categories (broad-niche / specific-niche / trending / community / "
            "branded). States the ship cap explicitly. Refuses engagement-bait "
            "tags outright."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    p.add_argument(
        "--post-topic-or-text",
        help="Either an x.com URL or the literal post topic. Required unless --demo / --demo-productivity is passed.",
    )
    p.add_argument(
        "--platform",
        choices=list(PLATFORM_OPTIONS),
        default="x",
        help="Target platform — drives the ship cap (X = 0-2, LinkedIn = 0-3). 'all' reports both.",
    )
    p.add_argument(
        "--num-hashtags",
        type=int,
        default=5,
        help=f"Number of hashtags to score ({MIN_HASHTAGS}-{MAX_HASHTAGS}). Default 5.",
    )
    p.add_argument(
        "--focus",
        choices=list(FOCUS_OPTIONS),
        default="all",
        help="Which canonical metric to emphasise. Default 'all' applies no nudge.",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run with the canonical AI-niche demo topic. Forces #AI into the set "
            "with low Niche relevance so the reach-without-relevance paradox demonstrates."
        ),
    )
    p.add_argument(
        "--demo-productivity",
        action="store_true",
        help="Run with a productivity-niche demo topic. Healthy mix (no paradox).",
    )
    p.add_argument("--show-system-prompt", action="store_true", help="Print system prompt path + size on stderr.")
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

    demo_paradox = False
    if args.demo and not args.post_topic_or_text:
        topic_arg = DEMO_POST_TOPIC
        demo_paradox = True
    elif args.demo_productivity and not args.post_topic_or_text:
        topic_arg = DEMO_PRODUCTIVITY_TOPIC
        demo_paradox = False
    elif args.post_topic_or_text:
        topic_arg = args.post_topic_or_text
    else:
        sys.stderr.write(
            "error: provide --post-topic-or-text \"<topic or URL>\" or pass --demo / --demo-productivity.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_hashtag_strategy(
        x_handle=args.x_handle,
        post_topic_or_text=topic_arg,
        platform=args.platform,
        num_hashtags=args.num_hashtags,
        focus=args.focus,
        when=when_iso,
        demo_paradox=demo_paradox,
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
