# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Daily Briefing Agent -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships niche-aware offline signal
bundles (trends + mentions + news + self-posts + evergreen) plus a
deterministic 6-section synthesis pipeline so creators get value the instant
`grok install this` finishes. To wire to live Grok 4.3, replace the body of
`generate_daily_briefing()` with a Grok call that consumes `prompts/system.md`
(auto-loaded) and returns the same schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --focus-areas "AI agents on X,creator economy"
    python run.py --x-handle @creator --demo productivity --suggest-visual
    python run.py --x-handle @me --focus-areas "AI agents" --date 2026-05-04 --output today.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import random
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

VERSION = "0.1.0"
TAGLINE = "Built to help xAI and Grok win."

BANNER = (
    "============================================================\n"
    f"  DAILY BRIEFING AGENT  v{VERSION}\n"
    "  Your X day, briefed in 60 seconds.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Static data (offline signal bundles, mirrors patterns from sibling runners)
# ---------------------------------------------------------------------------

ANGLES: List[str] = [
    "contrarian", "data-led", "story-led", "list-led",
    "prediction", "comparison", "how-to", "hot-take",
]

ACTION_VERBS: Tuple[str, ...] = (
    "reply now",
    "reply within 24h",
    "mute",
    "block",
    "ignore",
    "flag for follow-up",
)

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2")),
]
DEFAULT_BUCKET = "general"

ALT_BY_BUCKET: Dict[str, str] = {
    "ai": "fine-tuning",
    "finance": "spreadsheets",
    "productivity": "to-do apps",
    "creator": "follower-count chasing",
    "fitness": "calorie counting",
    "general": "the obvious move",
}

TOPICS_BY_BUCKET: Dict[str, List[str]] = {
    "ai": [
        "tool-calling agents", "structured outputs", "long-context summarization",
        "prompt caching", "MCP servers", "Grok 4.3 vision", "RAG pipelines",
        "agent memory",
    ],
    "finance": [
        "creator payouts", "tax automation", "earnings forecasts",
        "platform-native payments", "X Money flows", "personal P&L dashboards",
    ],
    "productivity": [
        "weekly review rituals", "single-tab focus rules", "calendar tetris",
        "writing in public", "automation glue", "the 3-task day",
        "PowerShell shortcuts",
    ],
    "creator": [
        "owned-audience math", "thread cadence", "newsletter to X funnels",
        "video-first weeks", "evergreen content libraries",
    ],
    "fitness": [
        "Zone 2 training", "VO2 max for desk workers", "the 80/20 lifting split",
        "sleep-tracking ROI",
    ],
    "general": [
        "the contrarian angle", "the underrated tactic", "the missing playbook",
    ],
}

CONTENT_OPENER_BY_ANGLE: Dict[str, str] = {
    "contrarian": "Stop optimizing for {expected}. Optimize for {topic}.",
    "data-led": "3 numbers that changed how I think about {topic}.",
    "story-led": "Shipped a {topic} thing last week. The lesson nobody warned me about:",
    "list-led": "5 {topic} patterns every {niche} person should steal.",
    "prediction": "By Q4, {topic} will be table-stakes in {niche}.",
    "comparison": "{topic} vs {expected}: not even close once you ship.",
    "how-to": "How to ship {topic} for {niche} in one week. Step-by-step.",
    "hot-take": "{topic} is the most underrated thing in {niche} right now.",
}

ANGLE_TO_FORMAT: Dict[str, str] = {
    "contrarian": "single tweet",
    "data-led": "thread starter",
    "story-led": "thread starter",
    "list-led": "thread starter",
    "prediction": "single tweet",
    "comparison": "image",
    "how-to": "thread starter",
    "hot-take": "single tweet",
}

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading", "earnings",
    "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
    "x money", "payout",
)

# Per-bucket offline signal bundles. v2 will pull live X-search + NewsAPI +
# the user's recent posts + cached mentions.
SIGNAL_BUNDLE_BY_BUCKET: Dict[str, Dict[str, Any]] = {
    "ai": {
        "default_niche": "AI agents on X",
        "trends": [
            ("Grok 4.3 release week", "x_trending", "strong",
             "anchor topic for the next 5 days; high niche relevance"),
            ("MCP servers everywhere", "x_trending", "building",
             "second day on the niche trending list"),
            ("agent eval debates", "x_trending", "building",
             "evergreen-leaning conversation gaining velocity this week"),
            ("xAI ships new vision update", "news", "light",
             "release-notes drop this morning"),
        ],
        "mentions": [
            {"author": "@dev_kai", "text": "Question on tool-calling agents: how do you handle the eval loop?",
             "kind": "question", "sentiment": "neutral"},
            {"author": "@docs_fan", "text": "Love your Grok 4.3 content but the docs are lagging the releases.",
             "kind": "mixed", "sentiment": "mixed"},
            {"author": "@bug_hunter", "text": "Your prompt caching demo crashed on Windows 11. Anyone else?",
             "kind": "bug", "sentiment": "negative"},
            {"author": "@spammer42", "text": "Send DM for free crypto trading signals!",
             "kind": "spam", "sentiment": "spam"},
        ],
        "self_posts": [
            "Your Friday review thread on RAG pipelines is still drawing quote-tweets 48h later",
            "Your MCP-server explainer is in your top 3 saves for the week",
        ],
        "evergreen_signals": [
            "Solo creators keep asking about first-eval-set sizing -- evergreen content gap worth filling",
            "Agent memory is the v2 differentiator most teams skip -- you can own this niche by Q3",
            "Boring eval rituals beat smart prompt tricks by week six -- worth a thread",
        ],
    },
    "productivity": {
        "default_niche": "Productivity systems for solopreneurs",
        "trends": [
            ("single-tab focus debate", "x_trending", "strong",
             "the headline conversation in the productivity niche this week"),
            ("weekly review cadence wave", "x_trending", "building",
             "Friday-review threads spiking across multiple sub-niches"),
            ("PowerShell 7.5 launch", "news", "light",
             "automation-glue community is paying attention"),
        ],
        "mentions": [
            {"author": "@calendar_user", "text": "Question on calendar tetris: how do you handle deep-work blocks vs meetings?",
             "kind": "question", "sentiment": "neutral"},
            {"author": "@review_doer", "text": "Started doing Friday reviews -- biggest unlock in months.",
             "kind": "advocate", "sentiment": "positive"},
            {"author": "@energy_track", "text": "Love the energy-vs-time framing but I keep losing track by Wednesday.",
             "kind": "mixed", "sentiment": "mixed"},
            {"author": "@spambot99", "text": "RT to win -- comment YES for a free productivity bundle!",
             "kind": "spam", "sentiment": "spam"},
        ],
        "self_posts": [
            "Your single-tab-focus thread is the top-saved post in your last 30 days",
            "Your 3-task-day post just crossed 1k bookmarks",
        ],
        "evergreen_signals": [
            "Solopreneurs keep asking how to protect deep-work blocks from Slack -- evergreen gap",
            "Friday review rituals compound; people who start in May report wins by August",
        ],
    },
    "finance": {
        "default_niche": "creator economy finance",
        "trends": [
            ("X Money payouts week", "x_trending", "strong",
             "the dominant payout-cycle conversation this week"),
            ("creator tax season", "x_trending", "building",
             "tax-export questions spiking ahead of quarterly filings"),
            ("Vietnam creator-tax guidance update", "news", "light",
             "relevant for international creators with platform earnings"),
        ],
        "mentions": [
            {"author": "@payout_curious", "text": "How do you forecast earnings when X Money is volatile week-to-week?",
             "kind": "question", "sentiment": "neutral"},
            {"author": "@tax_anxious", "text": "Tax export from your tool saved me a weekend. Thank you.",
             "kind": "advocate", "sentiment": "positive"},
            {"author": "@compliance_q", "text": "Love the disclaimers but is there a 1099-style report planned?",
             "kind": "mixed", "sentiment": "mixed"},
            {"author": "@spamtoken", "text": "Send DM for free crypto trading signals!",
             "kind": "spam", "sentiment": "spam"},
        ],
        "self_posts": [
            "Your X Money tax-export thread is your highest-saved finance post in 90 days",
            "Your earnings-forecast explainer is drawing finance-club bookmarks",
        ],
        "evergreen_signals": [
            "Creators keep asking how to model platform-native payouts cleanly -- evergreen content gap",
            "Tax-aware payout planning compounds; the people who start in May breathe easier in March",
        ],
    },
    "creator": {
        "default_niche": "creator economy",
        "trends": [
            ("owned-audience math debate", "x_trending", "building",
             "newsletter-vs-X funnel debate is the headline topic"),
            ("thread cadence push", "x_trending", "light",
             "consistency-over-virality argument gaining traction"),
        ],
        "mentions": [
            {"author": "@audience_q", "text": "Question on funnel: how do you measure newsletter-to-X conversion?",
             "kind": "question", "sentiment": "neutral"},
            {"author": "@cadence_fan", "text": "Your thread cadence advice changed my whole posting rhythm. Thanks.",
             "kind": "advocate", "sentiment": "positive"},
            {"author": "@noise_q", "text": "Love your stuff but the cross-platform reposting feels off lately.",
             "kind": "mixed", "sentiment": "mixed"},
            {"author": "@spamcreator", "text": "RT for free growth bundle, comment YES!",
             "kind": "spam", "sentiment": "spam"},
        ],
        "self_posts": [
            "Your owned-audience-math thread is still drawing replies a week later",
        ],
        "evergreen_signals": [
            "Mid-tier creators keep asking about thread cadence vs newsletter rhythm",
        ],
    },
    "fitness": {
        "default_niche": "Zone 2 training",
        "trends": [
            ("Zone 2 wave", "x_trending", "strong",
             "the dominant training-discourse topic this week"),
            ("VO2 max for desk workers", "x_trending", "building",
             "longevity-adjacent conversation gaining traction"),
        ],
        "mentions": [
            {"author": "@zone2_q", "text": "Question on Zone 2: how do you actually measure heart rate accurately?",
             "kind": "question", "sentiment": "neutral"},
            {"author": "@vo2_fan", "text": "Your VO2 max thread changed how I structure my week.",
             "kind": "advocate", "sentiment": "positive"},
        ],
        "self_posts": [
            "Your Zone-2-for-desk-workers thread is your top-saved fitness post this month",
        ],
        "evergreen_signals": [
            "Beginners keep asking how to size a first Zone 2 block -- evergreen gap",
        ],
    },
    "general": {
        "default_niche": "X creator",
        "trends": [
            ("general engagement patterns this week", "x_trending", "light",
             "broad creator-conversation signal"),
        ],
        "mentions": [
            {"author": "@curious_one", "text": "Question on your latest post: how did you frame the angle?",
             "kind": "question", "sentiment": "neutral"},
            {"author": "@warm_reader", "text": "Saved your latest. Quietly excellent.",
             "kind": "advocate", "sentiment": "positive"},
        ],
        "self_posts": [
            "Your latest post is still drawing replies into day three",
        ],
        "evergreen_signals": [
            "Mid-tier creators keep asking what their next move should be -- evergreen gap",
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_bucket(blob: str) -> str:
    s = blob.lower()
    for bucket, keys in NICHE_BUCKETS:
        for k in keys:
            if k in s:
                return bucket
    return DEFAULT_BUCKET


def is_finance_adjacent(blob: str) -> bool:
    s = blob.lower()
    return any(k in s for k in FINANCE_KEYWORDS)


def deterministic_seed(x_handle: str, today: _dt.date, focus_blob: str) -> int:
    raw = f"{x_handle}|{today.isoformat()}|{focus_blob}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def build_imagine_prompt(headline: str, niche: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment hero card illustrating today's "
        f"creator briefing -- '{headline}' in the {niche} niche. Clean "
        "composition, neon highlights, Windows 11 desktop vibe, 16:9, "
        "no text overlay."
    )


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def _parse_focus_areas(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _redact(text: str, max_chars: int = 140) -> str:
    redacted = re.sub(r"\b\d{3}-?\d{3}-?\d{4}\b", "[redacted-phone]", text)
    redacted = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[redacted-email]", redacted)
    if len(redacted) > max_chars:
        redacted = redacted[: max_chars - 3].rstrip() + "..."
    return redacted


# ---------------------------------------------------------------------------
# Briefing assembly
# ---------------------------------------------------------------------------

def _build_signal_bullets(
    bundle: Dict[str, Any],
    rng: random.Random,
    niche_label: str,
) -> List[Dict[str, str]]:
    """Return 5-7 source-tagged signal bullets."""
    bullets: List[Dict[str, str]] = []

    trends = bundle["trends"][:]
    rng.shuffle(trends)
    for slug, source, strength, _relevance in trends[:2]:
        bullets.append({
            "label": "trend" if source == "x_trending" else source,
            "text": f"*{slug}* is {_strength_phrase(strength)} in your niche.",
        })

    mentions = [m for m in bundle["mentions"] if m["sentiment"] != "spam"]
    rng.shuffle(mentions)
    for m in mentions[:2]:
        red = _redact(m["text"], 90)
        if m["kind"] == "question":
            phr = f"{m['author']} asked: {red}"
        elif m["kind"] == "advocate":
            phr = f"{m['author']} is amplifying you: {red}"
        elif m["kind"] == "mixed":
            phr = f"{m['author']} is split on you: {red}"
        elif m["kind"] == "bug":
            phr = f"{m['author']} flagged a bug: {red}"
        else:
            phr = f"{m['author']} mentioned you: {red}"
        bullets.append({"label": "mention", "text": phr})

    self_posts: List[str] = bundle.get("self_posts", [])[:]
    if self_posts:
        rng.shuffle(self_posts)
        bullets.append({"label": "self", "text": self_posts[0]})

    evergreen: List[str] = bundle.get("evergreen_signals", [])[:]
    if evergreen:
        rng.shuffle(evergreen)
        bullets.append({"label": "evergreen", "text": evergreen[0]})

    # Niche-relevance sweep: append a focus-area framing if multiple supplied.
    if niche_label and niche_label != bundle.get("default_niche", ""):
        bullets.append({
            "label": "self",
            "text": f"Your declared focus '{niche_label}' aligns with today's top trend signals.",
        })

    return bullets[:7]


def _strength_phrase(strength: str) -> str:
    return {
        "light": "showing a light early signal",
        "building": "gaining velocity",
        "strong": "running strong (anchor signal)",
    }.get(strength, "showing chatter")


def _pick_key_trends(
    bundle: Dict[str, Any], rng: random.Random, max_picks: int = 3,
) -> List[Dict[str, str]]:
    trends = bundle["trends"][:]
    rng.shuffle(trends)
    out: List[Dict[str, str]] = []
    for slug, source, strength, relevance in trends[:max_picks]:
        out.append({
            "slug": slug,
            "source": source,
            "strength": strength,
            "relevance": relevance,
        })
    return out


def _build_action_priorities(
    bundle: Dict[str, Any],
    rng: random.Random,
    niche_label: str,
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    mentions = bundle["mentions"][:]
    rng.shuffle(mentions)

    bug = next((m for m in mentions if m.get("kind") == "bug"), None)
    if bug:
        actions.append({
            "verb": "reply now",
            "target": bug["author"],
            "reason": "actionable bug report; same-day reply prevents churn",
            "finance_tag": is_finance_adjacent(bug["text"]),
        })

    question = next((m for m in mentions if m.get("kind") == "question"), None)
    if question:
        actions.append({
            "verb": "reply within 24h",
            "target": question["author"],
            "reason": "thoughtful question; expert-signal reply lands well",
            "finance_tag": is_finance_adjacent(question["text"]),
        })

    mixed = next((m for m in mentions if m.get("kind") == "mixed"), None)
    if mixed:
        actions.append({
            "verb": "flag for follow-up",
            "target": mixed["author"],
            "reason": "mixed signal worth a status reply or thread response",
            "finance_tag": is_finance_adjacent(mixed["text"]),
        })

    spam = next((m for m in mentions if m.get("kind") == "spam"), None)
    if spam:
        actions.append({
            "verb": "block",
            "target": spam["author"],
            "reason": "DM-bait/RT-to-win pattern; recurring this week",
            "finance_tag": False,
        })

    # Trend-driven action.
    trends = bundle["trends"][:]
    rng.shuffle(trends)
    if trends:
        slug, _src, strength, _rel = trends[0]
        verb = "reply within 24h" if strength == "strong" else "flag for follow-up"
        actions.append({
            "verb": verb,
            "target": f"the '{slug}' trend",
            "reason": f"{_strength_phrase(strength)}; worth a thread by Wednesday",
            "finance_tag": is_finance_adjacent(slug),
        })

    # Cap 3-5 actions
    if len(actions) > 5:
        actions = actions[:5]
    if len(actions) < 3:
        actions.append({
            "verb": "ignore",
            "target": "the noise floor",
            "reason": "no high-signal mentions today; keep cadence and ship instead",
            "finance_tag": False,
        })
    return actions


def _build_content_ideas(
    bucket: str,
    niche_label: str,
    rng: random.Random,
    max_picks: int = 3,
) -> List[Dict[str, str]]:
    angles_pool = ANGLES[:]
    rng.shuffle(angles_pool)
    topics = TOPICS_BY_BUCKET.get(bucket, TOPICS_BY_BUCKET["general"])[:]
    rng.shuffle(topics)
    alt = ALT_BY_BUCKET.get(bucket, "the obvious move")

    out: List[Dict[str, str]] = []
    used_angles: set = set()
    for i in range(min(max_picks, len(angles_pool))):
        angle = angles_pool[i]
        if angle in used_angles:
            continue
        used_angles.add(angle)
        topic = topics[i % len(topics)]
        opener_template = CONTENT_OPENER_BY_ANGLE[angle]
        opener = opener_template.format(
            topic=topic, expected=alt, niche=niche_label,
        )
        if len(opener) > 140:
            opener = opener[:140].rstrip(",;:") + "."
        why = (
            f"tied to {bucket}-niche signals today"
            if bucket != "general" else "evergreen"
        )
        out.append({
            "angle": angle,
            "format": ANGLE_TO_FORMAT[angle],
            "why_now": why,
            "draft_opener": opener,
            "finance_tag": str(is_finance_adjacent(topic + " " + niche_label)).lower(),
        })
    return out


def _aggregate_sentiment(bundle: Dict[str, Any]) -> Tuple[str, str]:
    """Return (label, one-sentence reason)."""
    mentions = bundle["mentions"]
    pos = sum(1 for m in mentions if m["sentiment"] == "positive")
    neg = sum(1 for m in mentions if m["sentiment"] == "negative")
    mixed = sum(1 for m in mentions if m["sentiment"] == "mixed")
    spam = sum(1 for m in mentions if m["sentiment"] == "spam")
    if pos >= max(neg, 1) and pos >= mixed:
        return "positive", (
            f"mention sentiment skews positive ({pos} advocate signal(s)); "
            f"{spam} spam excluded from the read."
        )
    if neg > pos:
        return "negative", (
            f"mention sentiment skews negative ({neg} actionable critique(s)); "
            f"{spam} spam excluded."
        )
    if mixed and pos == neg:
        return "mixed", (
            f"sentiment is split: {pos} positive, {neg} negative, {mixed} mixed; "
            f"{spam} spam excluded."
        )
    return "neutral", (
        f"sentiment is neutral overall ({pos}/{neg}/{mixed} pos/neg/mixed); "
        f"{spam} spam excluded."
    )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_daily_briefing(
    x_handle: str,
    focus_areas: Optional[List[str]] = None,
    date: Optional[str] = None,
    include_visual: bool = False,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured daily briefing dict.

    Output schema:
      {
        "x_handle", "today", "niche_bucket", "niche_label",
        "headline", "top_signals" (5-7 bullets), "key_trends" (1-3),
        "action_priorities" (3-5), "content_ideas" (1-3),
        "sentiment_label", "sentiment_reason",
        "visual_prompt": str | None,
      }
    """
    if today is None:
        today = _dt.date.fromisoformat(date) if date else _dt.date.today()

    focus_list = focus_areas or []
    focus_blob = ", ".join(focus_list) if focus_list else ""
    bucket_blob = focus_blob or x_handle  # fall back to handle if nothing else
    bucket = detect_bucket(bucket_blob)
    bundle = SIGNAL_BUNDLE_BY_BUCKET.get(bucket, SIGNAL_BUNDLE_BY_BUCKET["general"])

    niche_label = focus_list[0] if focus_list else bundle.get("default_niche", "X creator")

    rng = random.Random(deterministic_seed(x_handle, today, focus_blob))

    top_signals = _build_signal_bullets(bundle, rng, niche_label)
    key_trends = _pick_key_trends(bundle, rng, max_picks=3)
    action_priorities = _build_action_priorities(bundle, rng, niche_label)
    content_ideas = _build_content_ideas(bucket, niche_label, rng, max_picks=3)
    sentiment_label, sentiment_reason = _aggregate_sentiment(bundle)

    # Headline derived from strongest trend + first action.
    if key_trends:
        strongest = max(
            key_trends,
            key=lambda t: {"light": 1, "building": 2, "strong": 3}.get(t["strength"], 0),
        )
        first_action = action_priorities[0] if action_priorities else None
        if first_action:
            headline = (
                f"Anchor signal: '{strongest['slug']}' "
                f"({strongest['strength']}); first move: {first_action['verb']} "
                f"{first_action['target']}."
            )
        else:
            headline = f"Anchor signal: '{strongest['slug']}' ({strongest['strength']})."
    else:
        headline = "Quiet morning -- evergreen mode; ship a thread instead."

    visual_prompt = build_imagine_prompt(headline, niche_label) if include_visual else None

    return {
        "x_handle": x_handle,
        "today": today.isoformat(),
        "niche_bucket": bucket,
        "niche_label": niche_label,
        "focus_areas": focus_list,
        "headline": headline,
        "top_signals": top_signals,
        "key_trends": key_trends,
        "action_priorities": action_priorities,
        "content_ideas": content_ideas,
        "sentiment_label": sentiment_label,
        "sentiment_reason": sentiment_reason,
        "visual_prompt": visual_prompt,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_daily_briefing


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_report(result: Dict[str, Any]) -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )
    focus_str = ", ".join(result["focus_areas"]) if result["focus_areas"] else "(auto-detected)"
    meta = textwrap.dedent(f"""\
        # Daily Briefing -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Niche bucket:** {result['niche_bucket']}
        - **Focus areas:** {focus_str}
        - **Niche label:** {result['niche_label']}

        > {TAGLINE}

        """)

    out: List[str] = ["## Headline", "", result["headline"], ""]

    out.append("## Today's Top Signals")
    out.append("")
    for b in result["top_signals"]:
        out.append(f"- [{b['label']}] {b['text']}")
    out.append("")

    out.append("## Key Trends")
    out.append("")
    if result["key_trends"]:
        for i, t in enumerate(result["key_trends"], start=1):
            out.append(
                f"{i}. **{t['slug']}** ({t['source']}) -- "
                f"strength: {t['strength']}; relevance: {t['relevance']}"
            )
    else:
        out.append("- No trend signals today; evergreen mode.")
    out.append("")

    out.append("## Action Priorities")
    out.append("")
    for a in result["action_priorities"]:
        line = f"- {a['verb']} {a['target']} -- {a['reason']}."
        out.append(line)
        if a.get("finance_tag"):
            out.append("  Context only -- not financial advice.")
    out.append("")

    out.append("## Suggested Content Ideas")
    out.append("")
    for i, idea in enumerate(result["content_ideas"], start=1):
        out.append(f"{i}. **{idea['angle']}** -- format: {idea['format']}")
        out.append(f"   - Why now: {idea['why_now']}")
        out.append(f"   - Draft opener: \"{idea['draft_opener']}\"")
        if idea.get("finance_tag") == "true":
            out.append("   Context only -- not financial advice.")
    out.append("")

    out.append("## Sentiment Overview")
    out.append("")
    out.append(f"{result['sentiment_label']} -- {result['sentiment_reason']}")
    out.append("")

    if result["visual_prompt"]:
        out.append("## Visual Prompt")
        out.append("")
        out.append(result["visual_prompt"])
        out.append("")

    confidence = (
        f"Confidence: medium -- offline signal bundle; "
        f"{len(result['top_signals'])} top signals, "
        f"{len(result['key_trends'])} trends, "
        f"{len(result['action_priorities'])} priorities, "
        f"{len(result['content_ideas'])} content ideas. For live grounding, "
        "wire `prompts/system.md` to the xAI API (see README)."
    )
    out.append(confidence)
    return license_block + meta + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="daily-briefing-agent",
        description=(
            f"Daily Briefing Agent v{VERSION} -- your X day briefed in 60 seconds. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --focus-areas "AI agents on X,creator economy"
              python run.py --x-handle @creator --demo productivity --suggest-visual
              python run.py --x-handle @me --focus-areas "AI agents" --date 2026-05-04 --output today.md
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument(
        "--focus-areas", default=None,
        help="Optional comma-separated focus areas (e.g. 'AI agents on X,creator economy').",
    )
    parser.add_argument(
        "--demo", choices=sorted(SIGNAL_BUNDLE_BY_BUCKET.keys()), default=None,
        help="Use a prefab niche bucket if --focus-areas is omitted.",
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override the briefing date (YYYY-MM-DD); default today.",
    )
    parser.add_argument(
        "--suggest-visual", action="store_true",
        help="Append a Visual Prompt section (Grok Imagine prompt for a hero card).",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument("--version", action="version", version=f"daily-briefing-agent {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    if args.date:
        try:
            today = _dt.date.fromisoformat(args.date)
        except ValueError:
            sys.stderr.write(f"X  Invalid --date {args.date!r}; expected YYYY-MM-DD\n")
            return 64
    else:
        today = _dt.date.today()

    focus_areas = _parse_focus_areas(args.focus_areas)
    if not focus_areas and args.demo:
        focus_areas = [SIGNAL_BUNDLE_BY_BUCKET[args.demo]["default_niche"]]

    try:
        result = generate_daily_briefing(
            x_handle=args.x_handle,
            focus_areas=focus_areas,
            date=None,
            include_visual=args.suggest_visual,
            today=today,
        )
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 64

    report = render_report(result)

    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        sys.stdout.write(
            f"\nOK Wrote briefing -> {out_path} "
            f"({len(result['top_signals'])} signals, "
            f"{len(result['action_priorities'])} priorities)\n"
        )
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
