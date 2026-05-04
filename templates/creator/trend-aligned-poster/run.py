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
Trend-Aligned Poster -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships niche-aware offline trend
pools (x_trending + news) plus a deterministic 8-angle template library so
creators get value the instant `grok install this` finishes. To wire to live
Grok 4.3, replace the body of `generate_trend_aligned_posts()` with a Grok
call that consumes `prompts/system.md` (auto-loaded) and returns the same
3-card schema with `Tied to:` provenance lines.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --niche "AI agents on X"
    python run.py --x-handle @creator --niche "creator economy" --trend-source both --tone warm
    python run.py --x-handle @me --niche "productivity" --num-posts 5 --output today.md
    python run.py --x-handle @test --niche "AI agents" --trend-source evergreen
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
    f"  TREND-ALIGNED POSTER  v{VERSION}\n"
    "  3 trend-aware X drafts, every morning.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Static post library -- deterministic, offline, zero-dependency.
# Replace `generate_trend_aligned_posts()` body with a Grok 4.3 call to upgrade.
# ---------------------------------------------------------------------------

ANGLES: List[str] = [
    "contrarian",
    "data-led",
    "story-led",
    "list-led",
    "prediction",
    "comparison",
    "how-to",
    "hot-take",
]

LENGTH_SLOTS: List[Dict[str, Any]] = [
    {"label": "Short", "key": "short", "max_chars": 140},
    {"label": "Medium", "key": "medium", "max_chars": 220},
    {"label": "Value-add", "key": "value_add", "max_chars": 280},
]

# Default (non-value-add) format is "single tweet". Value-add picks vary.
ANGLE_TO_VALUE_ADD_FORMAT: Dict[str, str] = {
    "contrarian": "single tweet",
    "data-led": "thread starter",
    "story-led": "thread starter",
    "list-led": "thread starter",
    "prediction": "single tweet",
    "comparison": "image",
    "how-to": "thread starter",
    "hot-take": "single tweet",
}

ANGLE_TO_ENGAGEMENT: Dict[str, List[str]] = {
    # short, medium, value-add
    "contrarian":   ["medium-high", "medium-high", "high"],
    "data-led":     ["medium",      "medium-high", "medium-high"],
    "story-led":    ["medium",      "medium-high", "high"],
    "list-led":     ["medium",      "medium-high", "high"],
    "prediction":   ["medium-high", "medium-high", "high"],
    "comparison":   ["medium-high", "medium-high", "high"],
    "how-to":       ["medium",      "medium-high", "high"],
    "hot-take":     ["medium-high", "high",        "high"],
}

THREAD_PLAN_BY_ANGLE: Dict[str, str] = {
    "data-led": "{topic}: 3 data points + 1 chart",
    "story-led": "5-tweet ship-and-fix arc on {topic}",
    "list-led": "5 {topic} patterns to steal",
    "how-to": "5-step {topic} playbook",
}

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
        "creator payouts", "tax automation", "cashtag noise filters",
        "earnings forecasts", "platform-native payments", "X Money flows",
        "free public market APIs", "personal P&L dashboards",
    ],
    "productivity": [
        "weekly review rituals", "single-tab focus rules", "calendar tetris",
        "writing in public", "automation glue", "energy-vs-time budgeting",
        "the 3-task day", "PowerShell shortcuts",
    ],
    "creator": [
        "owned-audience math", "thread cadence", "reply-guy strategies",
        "bookmarks-per-post ratios", "newsletter to X funnels",
        "video-first weeks", "evergreen content libraries",
    ],
    "fitness": [
        "Zone 2 training", "cheap home gym setups", "protein math",
        "VO2 max for desk workers", "the 80/20 lifting split",
        "sleep-tracking ROI",
    ],
    "general": [
        "the contrarian angle", "the underrated tactic", "the missing playbook",
        "the unfair advantage", "the boring multiplier", "the cheap habit",
    ],
}

# Offline trend pools per niche bucket. v2 will fetch live X trending + NewsAPI.
TREND_POOLS: Dict[str, Dict[str, List[str]]] = {
    "ai": {
        "x_trending": [
            "Grok 4.3 release week",
            "MCP servers everywhere",
            "agent eval debates",
            "long-context wars",
            "structured outputs vs fine-tuning",
        ],
        "news": [
            "xAI ships new vision update",
            "agent platform consolidation report",
            "open-source eval framework launches",
            "Anthropic Claude 5 rumor cycle",
        ],
    },
    "finance": {
        "x_trending": [
            "X Money payouts week",
            "creator tax season",
            "free public market APIs",
            "fintech for solos",
        ],
        "news": [
            "Vietnam creator-tax guidance update",
            "crypto cycle update",
            "platform-native payments report",
        ],
    },
    "productivity": {
        "x_trending": [
            "single-tab focus debate",
            "weekly review cadence wave",
            "calendar tetris season",
            "energy-first scheduling",
        ],
        "news": [
            "remote work hours study",
            "deep-work productivity report",
            "PowerShell 7.5 launch",
        ],
    },
    "creator": {
        "x_trending": [
            "owned-audience math debate",
            "thread cadence push",
            "newsletter-to-X funnel wave",
        ],
        "news": [
            "creator monetization report",
            "platform algorithm update",
        ],
    },
    "fitness": {
        "x_trending": [
            "Zone 2 wave",
            "VO2 max for desk workers",
        ],
        "news": [
            "longevity study update",
        ],
    },
    "general": {
        "x_trending": [
            "general engagement patterns this week",
        ],
        "news": [
            "weekly creator roundup",
        ],
    },
}

POST_TEMPLATES_BY_ANGLE: Dict[str, Dict[str, str]] = {
    "contrarian": {
        "short": "Everyone in {niche} is chasing {expected}. The actual edge: {topic}.",
        "medium": "Hot take for {trend}: {topic} > {expected} in {niche}. Cheap to test, hard to argue with by week six.",
        "value_add": "Contrarian read on {trend}: most folks in {niche} optimize for {expected}. The actual move is {topic}. Three reasons it compounds, in 60 seconds. Save for week three.",
    },
    "data-led": {
        "short": "{trend} update: {topic} signal climbing in {niche}; {expected} flat.",
        "medium": "Numbers on {trend}: {topic} signal up sharply in {niche}, {expected} flat or down. The folks watching this closely already shifted.",
        "value_add": "Numbers thread on {trend}: {topic} is the metric most {niche} folks miss. Three data points from this week, plus the one chart that makes it obvious.",
    },
    "story-led": {
        "short": "Shipped a {topic} thing this week tied to {trend}. {niche} compounds when you stop waiting.",
        "medium": "Lived this during {trend}: shipped a {topic} project last week. What moved me from doubt to ship was one tiny eval. {niche} rewards velocity.",
        "value_add": "Thread on {trend}: shipped a {topic} project last week, broke twice, then fixed itself when I added an eval. The arc that makes {niche} compound, in 5 tweets.",
    },
    "list-led": {
        "short": "5 {topic} patterns to steal from {trend} this week.",
        "medium": "5 {topic} patterns from {trend}: write tiny evals; cap inputs; log every call; review on Fridays; ship the ugly version. Boring; works.",
        "value_add": "Thread of 5 {topic} patterns from {trend} every {niche} person should steal. Saves you a quarter; cheap to copy; works on day one.",
    },
    "prediction": {
        "short": "{trend} prediction: {topic} replaces {expected} in {niche} by Q4.",
        "medium": "Prediction tied to {trend}: {topic} becomes table-stakes in {niche} before year-end; {expected} stops mattering. Earliest signal inside the next month.",
        "value_add": "Two predictions from {trend} for {niche}: 1) {topic} wins by Q4. 2) {expected} stops mattering. Bookmark; come back in 90 days; tell me I'm wrong.",
    },
    "comparison": {
        "short": "{topic} vs {expected} in {trend}: not even close anymore.",
        "medium": "{topic} vs {expected} during {trend}: {topic} wins on auditability; {expected} wins on speed. The {niche} folks who picked already know.",
        "value_add": "{trend} side-by-side: {topic} vs {expected} in {niche}. The differentiator is whether you can audit the failure mode -- {topic} lets you do it earlier and cheaper.",
    },
    "how-to": {
        "short": "How to ship {topic} in {niche} this week, tied to {trend}. Under 5 minutes.",
        "medium": "How to use {topic} for {niche} during {trend}: cap inputs, log every call, ship a tiny eval, review Fridays. Boring playbook; reliably works.",
        "value_add": "How-to thread on {trend}: ship {topic} for {niche} in one week. 1) cap inputs 2) log every call 3) write 5 assertions 4) Friday review. Boring; effective.",
    },
    "hot-take": {
        "short": "Hot take from {trend}: {topic} is the most underrated thing in {niche} right now.",
        "medium": "Hot take tied to {trend}: most {niche} advice ignores {topic} entirely. That's exactly why it's the edge for the next 90 days.",
        "value_add": "Hot take on {trend} for {niche}: the community is sleeping on {topic}. Most chase {expected}; early movers already pivoted. Save; check back in three weeks.",
    },
}

TONE_PREPENDS: Dict[str, str] = {
    "punchy": "",
    "thoughtful": "On reflection -- ",
    "data-led": "Quick numbers: ",
    "warm": "For the folks shipping in this space -- ",
}

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading", "earnings",
    "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
    "x money", "payout",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_bucket(niche: str) -> str:
    n = niche.lower()
    for bucket, keys in NICHE_BUCKETS:
        for k in keys:
            if k in n:
                return bucket
    return DEFAULT_BUCKET


def is_finance_adjacent(niche: str, topic: str, trend: str, post_text: str) -> bool:
    blob = (niche + " " + topic + " " + trend + " " + post_text).lower()
    return any(k in blob for k in FINANCE_KEYWORDS)


def deterministic_seed(x_handle: str, niche: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{niche}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def build_imagine_prompt(topic: str, niche: str, trend: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment illustration depicting "
        f"'{topic}' tied to '{trend}' in the {niche} niche. Clean composition, "
        "neon highlights, Windows 11 desktop vibe, 16:9, no text overlay."
    )


def _safe_render(template: str, max_chars: int, **kwargs: Any) -> str:
    text = template.format(**kwargs).strip()
    if len(text) <= max_chars:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    while parts and len(" ".join(parts)) > max_chars:
        parts.pop()
    tightened = " ".join(parts).strip()
    if 0 < len(tightened) <= max_chars:
        return tightened
    cut = text[:max_chars].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(",;:")
    return cut


def _apply_tone(text: str, tone: str, max_chars: int) -> str:
    prepend = TONE_PREPENDS.get(tone, "")
    if not prepend:
        return text
    candidate = prepend + text
    return candidate if len(candidate) <= max_chars else text


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def get_active_trends(bucket: str, source: str) -> List[Tuple[str, str]]:
    """Return [(slug, source_label), ...] for the requested trend_source.

    `source` in {x_trending, news, both, evergreen}.
    """
    if source == "evergreen":
        return []
    pools = TREND_POOLS.get(bucket, TREND_POOLS["general"])
    out: List[Tuple[str, str]] = []
    if source in ("x_trending", "both"):
        for slug in pools.get("x_trending", []):
            out.append((slug, "x_trending"))
    if source in ("news", "both"):
        for slug in pools.get("news", []):
            out.append((slug, "news"))
    return out


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_trend_aligned_posts(
    x_handle: str,
    niche_keywords: str,
    trend_source: str = "x_trending",
    num_posts: int = 3,
    tone: str = "punchy",
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured result with `num_posts` post drafts.

    Output schema:
      {
        "x_handle": str, "niche": str, "tone": str,
        "trend_source_requested": str, "trend_source_used": str,
        "niche_bucket": str, "today": "YYYY-MM-DD",
        "drafts": [
          {"n", "slot", "label", "char_limit", "char_count", "angle",
           "tied_to_label", "tied_to_slug",
           "engagement", "format", "post",
           "finance_tag", "grok_imagine", "thread_plan", "poll_options"}
        ],
        "trend_sources_used": [str, ...],
      }
    """
    if num_posts < 1 or num_posts > 5:
        raise ValueError(f"num_posts must be 1..5, got {num_posts}")
    if tone not in TONE_PREPENDS:
        raise ValueError(f"tone must be one of {list(TONE_PREPENDS)}, got {tone!r}")
    if trend_source not in ("x_trending", "news", "both", "evergreen"):
        raise ValueError(
            f"trend_source must be one of x_trending|news|both|evergreen, got {trend_source!r}"
        )
    if not niche_keywords.strip():
        raise ValueError("niche_keywords must be non-empty")

    today = today or _dt.date.today()
    rng = random.Random(deterministic_seed(x_handle, niche_keywords, today))
    bucket = detect_bucket(niche_keywords)
    alt = ALT_BY_BUCKET[bucket]
    topics_pool = TOPICS_BY_BUCKET.get(bucket, TOPICS_BY_BUCKET["general"])[:]
    rng.shuffle(topics_pool)
    angles = ANGLES[:]
    rng.shuffle(angles)

    active = get_active_trends(bucket, trend_source)
    rng.shuffle(active)
    actual_source = trend_source if active else "evergreen"

    drafts: List[Dict[str, Any]] = []
    used_sources: List[str] = []
    for i in range(num_posts):
        slot = LENGTH_SLOTS[i % len(LENGTH_SLOTS)]
        angle = angles[i % len(angles)]
        topic = topics_pool[i % len(topics_pool)]
        if active:
            slug, label = active[i % len(active)]
        else:
            slug, label = "evergreen", "evergreen"
        used_sources.append(label)

        template = POST_TEMPLATES_BY_ANGLE[angle][slot["key"]]
        # In evergreen mode the slug isn't a real trend; substitute a neutral
        # phrase so the post body reads naturally. The meta `Tied to:` line
        # still records 'evergreen' honestly.
        trend_phrase = "the current cycle" if slug == "evergreen" else slug
        base = _safe_render(
            template,
            slot["max_chars"],
            topic=topic,
            niche=niche_keywords,
            expected=alt,
            trend=trend_phrase,
        )
        post = _apply_tone(base, tone, slot["max_chars"])
        engagement = ANGLE_TO_ENGAGEMENT[angle][LENGTH_SLOTS.index(slot)]

        # Format: value-add slot picks per angle; otherwise single tweet.
        if slot["key"] == "value_add":
            fmt = ANGLE_TO_VALUE_ADD_FORMAT[angle]
        else:
            fmt = "single tweet"

        grok_imagine: Optional[str] = None
        thread_plan: Optional[str] = None
        if fmt == "image":
            grok_imagine = build_imagine_prompt(topic, niche_keywords, slug)
        elif fmt == "thread starter":
            tp = THREAD_PLAN_BY_ANGLE.get(angle)
            if tp:
                thread_plan = tp.format(topic=topic, niche=niche_keywords, trend=slug)
            else:
                thread_plan = f"5-tweet expansion on {topic}"

        finance = is_finance_adjacent(niche_keywords, topic, slug, post)

        drafts.append({
            "n": i + 1,
            "slot": slot["key"],
            "label": slot["label"],
            "char_limit": slot["max_chars"],
            "char_count": len(post),
            "angle": angle,
            "tied_to_label": label,
            "tied_to_slug": slug,
            "engagement": engagement,
            "format": fmt,
            "post": post,
            "finance_tag": finance,
            "grok_imagine": grok_imagine,
            "thread_plan": thread_plan,
            "poll_options": None,  # reserved for future use
            "topic": topic,
        })

    # Spread engagement labels: if all drafts share one label, downgrade weakest.
    labels = {d["engagement"] for d in drafts}
    if len(drafts) >= 2 and len(labels) == 1:
        weakest = min(drafts, key=lambda d: d["char_count"])
        weakest["engagement"] = "medium"

    return {
        "x_handle": x_handle,
        "niche": niche_keywords,
        "tone": tone,
        "trend_source_requested": trend_source,
        "trend_source_used": actual_source,
        "niche_bucket": bucket,
        "today": today.isoformat(),
        "drafts": drafts,
        "trend_sources_used": sorted(set(used_sources)),
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_trend_aligned_posts


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_draft(draft: Dict[str, Any]) -> str:
    if draft["tied_to_label"] == "evergreen":
        tied_to = "evergreen"
    else:
        tied_to = f"{draft['tied_to_label']} -- \"{draft['tied_to_slug']}\""

    parts = [
        f"### Draft {draft['n']} -- {draft['label']} ({draft['char_count']} / {draft['char_limit']} chars)",
        "",
        f"- **Angle:** {draft['angle']}",
        f"- **Tied to:** {tied_to}",
        f"- **Engagement estimate:** {draft['engagement']}",
        f"- **Format:** {draft['format']}",
        f"- **Post:** \"{draft['post']}\"",
    ]
    if draft.get("grok_imagine"):
        parts.append(f"- **Grok Imagine prompt:** {draft['grok_imagine']}")
    if draft.get("thread_plan"):
        parts.append(f"- **Thread plan:** {draft['thread_plan']}")
    if draft.get("poll_options"):
        parts.append(f"- **Poll options:** {draft['poll_options']}")
    if draft["finance_tag"]:
        parts.append("Context only -- not financial advice.")
    return "\n".join(parts)


def render_report(result: Dict[str, Any]) -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )
    sources = ", ".join(result["trend_sources_used"]) or "evergreen"
    header = textwrap.dedent(f"""\
        # Trend-Aligned Posts -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Niche:** {result['niche']}
        - **Detected bucket:** {result['niche_bucket']}
        - **Trend source requested:** {result['trend_source_requested']}
        - **Trend source actually used:** {result['trend_source_used']}
        - **Sources cited:** {sources}
        - **Tone:** {result['tone']}
        - **Total drafts:** {len(result['drafts'])}

        > {TAGLINE}

        """)
    body = "\n\n".join(render_draft(d) for d in result["drafts"])
    confidence_caveat = (
        "drafts grounded to offline trend pool"
        if result["trend_source_used"] != "evergreen"
        else "no trend pool selected; evergreen drafts only"
    )
    confidence = (
        f"Confidence: medium -- {confidence_caveat}; for live trends + voice "
        f"matching, wire `prompts/system.md` to the xAI API (see README)."
    )
    return f"{license_block}{header}{body}\n\n{confidence}\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _ranged_int(lo: int, hi: int) -> Callable[[str], int]:
    def _fn(s: str) -> int:
        try:
            value = int(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"expected integer, got {s!r}") from None
        if value < lo or value > hi:
            raise argparse.ArgumentTypeError(f"must be between {lo} and {hi}, got {value}")
        return value
    return _fn


_DEMO_NICHES: Dict[str, str] = {
    "ai": "AI agents on X",
    "productivity": "Productivity systems for solopreneurs",
    "finance": "creator economy finance",
    "creator": "creator economy",
    "fitness": "Zone 2 training",
}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="trend-aligned-poster",
        description=(
            f"Trend-Aligned Poster v{VERSION} -- 3 trend-aware X drafts in 30 seconds. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --niche "AI agents on X"
              python run.py --x-handle @creator --niche "creator economy" --trend-source both --tone warm
              python run.py --x-handle @me --niche "productivity" --num-posts 5 --output today.md
              python run.py --x-handle @test --niche "AI agents" --trend-source evergreen
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument(
        "--niche", default=None,
        help="Niche or topic area in plain language (e.g. 'AI agents on X'). Required unless --demo is set.",
    )
    parser.add_argument(
        "--demo", choices=sorted(_DEMO_NICHES.keys()), default=None,
        help="Use a prefab niche for first-run demos. If --niche is omitted, --demo picks a representative niche string.",
    )
    parser.add_argument(
        "--trend-source", choices=("x_trending", "news", "both", "evergreen"),
        default="x_trending",
        help="Trend pool to draw from (default x_trending).",
    )
    parser.add_argument(
        "--num-posts", type=_ranged_int(1, 5), default=3,
        help="How many drafts to return (1..5, default 3).",
    )
    parser.add_argument(
        "--tone", choices=tuple(TONE_PREPENDS.keys()), default="punchy",
        help="Voice flavor (default punchy).",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument("--version", action="version", version=f"trend-aligned-poster {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    niche = args.niche or (_DEMO_NICHES[args.demo] if args.demo else None)
    if not niche:
        sys.stderr.write("X  --niche is required (or pass --demo {ai|productivity|finance|creator|fitness})\n")
        return 64

    if args.date:
        try:
            today = _dt.date.fromisoformat(args.date)
        except ValueError:
            sys.stderr.write(f"X  Invalid --date {args.date!r}; expected YYYY-MM-DD\n")
            return 64
    else:
        today = _dt.date.today()

    try:
        result = generate_trend_aligned_posts(
            x_handle=args.x_handle,
            niche_keywords=niche,
            trend_source=args.trend_source,
            num_posts=args.num_posts,
            tone=args.tone,
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
        sys.stdout.write(f"\nOK Wrote {len(result['drafts'])} draft(s) -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
