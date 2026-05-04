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
Content Idea Generator -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships a deterministic, niche-aware
idea library so creators get value the instant `grok install this` finishes,
without needing an xAI API key. To wire it to live Grok 4.3, replace the body
of `generate_ideas()` with a Grok call that consumes `prompts/system.md` and
returns the same idea-card schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --niche "AI agents on X"
    python run.py --x-handle @creator --niche "fintech for solopreneurs" --tone data-led
    python run.py --x-handle @me --niche "productivity" --output today.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import random
import sys
import textwrap
from pathlib import Path
from typing import Callable, Dict, List, Optional

VERSION = "0.1.0"
TAGLINE = "Built to help xAI and Grok win."

BANNER = (
    "============================================================\n"
    f"  CONTENT IDEA GENERATOR  v{VERSION}\n"
    "  5 fresh X post ideas, every morning.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

# ---------------------------------------------------------------------------
# Static idea library -- deterministic, offline, zero-dependency.
# Replace `generate_ideas()` body with a Grok 4.3 call to upgrade to live mode.
# ---------------------------------------------------------------------------

ANGLE_CYCLE: List[str] = [
    "contrarian",
    "data-led",
    "story-led",
    "list-led",
    "prediction",
    "comparison",
    "how-to",
    "hot-take",
]

ANGLE_TO_FORMAT: Dict[str, str] = {
    "contrarian": "single tweet",
    "data-led": "thread (5 tweets)",
    "story-led": "thread (7 tweets)",
    "list-led": "thread (5 tweets)",
    "prediction": "single tweet",
    "comparison": "image-led",
    "how-to": "thread (5 tweets)",
    "hot-take": "single tweet",
}

ANGLE_TO_SIGNAL: Dict[str, str] = {
    "contrarian": "likely-quotes",
    "data-led": "likely-saves",
    "story-led": "likely-replies",
    "list-led": "likely-saves",
    "prediction": "likely-quotes",
    "comparison": "likely-bookmarks",
    "how-to": "likely-bookmarks",
    "hot-take": "likely-quotes",
}

NICHE_BUCKETS: List[tuple] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2")),
]
DEFAULT_BUCKET = "general"

TOPICS_BY_BUCKET: Dict[str, Dict[str, object]] = {
    "ai": {
        "topics": [
            "tool-calling agents",
            "structured outputs",
            "long-context summarization",
            "prompt caching",
            "MCP servers",
            "Grok 4.3 vision",
            "RAG pipelines",
            "agent memory",
        ],
        "expected": "fine-tuning",
        "trend_phrase": "AI-agent chatter is up sharply on X over the last {window} days",
    },
    "finance": {
        "topics": [
            "creator payouts",
            "tax automation",
            "cashtag noise filters",
            "earnings forecasts",
            "platform-native payments",
            "X Money flows",
            "free public market APIs",
            "personal P&L dashboards",
        ],
        "expected": "spreadsheets",
        "trend_phrase": "creator-economy money chatter is heating up on X over {window} days",
    },
    "productivity": {
        "topics": [
            "weekly review rituals",
            "single-tab focus rules",
            "calendar tetris",
            "writing in public",
            "automation glue",
            "energy-vs-time budgeting",
            "the 3-task day",
            "PowerShell shortcuts",
        ],
        "expected": "to-do apps",
        "trend_phrase": "productivity threads are spiking on X this week",
    },
    "creator": {
        "topics": [
            "owned-audience math",
            "thread cadence",
            "reply-guy strategies",
            "bookmarks-per-post ratios",
            "newsletter -> X funnels",
            "video-first weeks",
            "evergreen content libraries",
        ],
        "expected": "follower count",
        "trend_phrase": "creator-monetization debates are loud on X over the last {window} days",
    },
    "fitness": {
        "topics": [
            "Zone 2 training",
            "cheap home gym setups",
            "protein math",
            "VO2 max for desk workers",
            "the 80/20 lifting split",
            "sleep-tracking ROI",
        ],
        "expected": "calorie counting",
        "trend_phrase": "VO2-max takes are trending across X this week",
    },
    "general": {
        "topics": [
            "the niche question",
            "the contrarian angle",
            "the underrated tactic",
            "the missing playbook",
            "the unfair advantage",
            "the boring multiplier",
            "the cheap habit",
        ],
        "expected": "the obvious move",
        "trend_phrase": "general engagement patterns over the last {window} days",
    },
}

HOOKS_BY_ANGLE: Dict[str, List[str]] = {
    "contrarian": [
        "Everyone in {niche} says {expected} is the answer. It isn't.",
        "Stop optimizing for {expected}. Optimize for {topic}.",
        "The hottest take in {niche}: {topic} > {expected}.",
    ],
    "data-led": [
        "I tracked {topic} for {window} days. Here's the breakdown.",
        "3 numbers that changed how I think about {topic}.",
        "{topic}: the metric most {niche} folks never show.",
    ],
    "story-led": [
        "I shipped {topic} last week. Here's what nobody warned me about.",
        "{topic} broke my workflow. Then it fixed it.",
        "How a single {topic} decision rewired my {niche}.",
    ],
    "list-led": [
        "5 {topic} patterns every {niche} person should steal.",
        "The 7 {topic} mistakes I keep seeing in {niche}.",
        "Top 3 {topic} levers nobody pulls in {niche}.",
    ],
    "prediction": [
        "By Q4, {topic} will be table-stakes in {niche}.",
        "{topic} replaces {expected} in {niche} before year-end. Bookmark this.",
        "Two predictions for {niche}: 1) {topic} wins. 2) {expected} dies.",
    ],
    "comparison": [
        "{topic} vs {expected}: not even close anymore.",
        "Why {topic} eats {expected} for breakfast in {niche}.",
        "The {topic} vs {expected} debate is over. {topic} won.",
    ],
    "how-to": [
        "How to use {topic} for {niche} in under 5 minutes.",
        "The 3-step {topic} setup most {niche} folks skip.",
        "Ship {topic} this week -- exact stack inside.",
    ],
    "hot-take": [
        "{topic} is the most underrated thing in {niche} right now.",
        "Most {niche} advice ignores {topic} entirely. That's the edge.",
        "The {niche} community is sleeping on {topic}.",
    ],
}

TONE_MODIFIER: Dict[str, Callable[[str], str]] = {
    "punchy": lambda hook: hook,
    "thoughtful": lambda hook: f"A short reflection -- {hook}",
    "data-led": lambda hook: f"Quick numbers thread: {hook}",
}

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading",
    "earnings", "money", "fintech", "defi", "invest", "p&l", "tax",
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


def is_finance_adjacent(niche: str, topic: str) -> bool:
    blob = (niche + " " + topic).lower()
    return any(k in blob for k in FINANCE_KEYWORDS)


def deterministic_seed(x_handle: str, niche: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{niche}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def build_imagine_prompt(topic: str, niche: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment illustration depicting "
        f"'{topic}' in the {niche} niche. Clean composition, neon "
        "highlights, Windows 11 desktop vibe, 16:9, no text overlay."
    )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_ideas(
    x_handle: str,
    niche: str,
    count: int = 5,
    tone: str = "punchy",
    trend_window_days: int = 7,
    today: Optional[_dt.date] = None,
) -> List[Dict[str, str]]:
    """Return `count` distinct idea cards for (x_handle, niche, today).

    Deterministic: same args + same date = same ideas. Tomorrow = fresh ideas.
    """
    if count < 1 or count > 10:
        raise ValueError(f"count must be 1..10, got {count}")
    if trend_window_days < 1 or trend_window_days > 30:
        raise ValueError(f"trend_window_days must be 1..30, got {trend_window_days}")
    if tone not in TONE_MODIFIER:
        raise ValueError(f"tone must be one of {list(TONE_MODIFIER)}, got {tone!r}")

    today = today or _dt.date.today()
    rng = random.Random(deterministic_seed(x_handle, niche, today))
    bucket = detect_bucket(niche)
    bucket_data = TOPICS_BY_BUCKET[bucket]

    topics_pool = list(bucket_data["topics"])  # type: ignore[arg-type]
    rng.shuffle(topics_pool)
    angles = ANGLE_CYCLE[:]
    rng.shuffle(angles)

    ideas: List[Dict[str, str]] = []
    for i in range(count):
        angle = angles[i % len(angles)]
        topic = topics_pool[i % len(topics_pool)]
        hook_template = rng.choice(HOOKS_BY_ANGLE[angle])
        hook = hook_template.format(
            topic=topic,
            niche=niche,
            expected=bucket_data["expected"],
            window=trend_window_days,
        )
        fmt = ANGLE_TO_FORMAT[angle]
        signal = ANGLE_TO_SIGNAL[angle]
        why_now = bucket_data["trend_phrase"].format(window=trend_window_days)  # type: ignore[union-attr]
        opener = TONE_MODIFIER[tone](hook)
        finance_tag = (
            "Context only -- not financial advice."
            if is_finance_adjacent(niche, topic) else ""
        )
        idea: Dict[str, str] = {
            "n": str(i + 1),
            "hook": hook,
            "angle": angle,
            "format": fmt,
            "why_now": why_now,
            "draft_opener": opener,
            "signal": signal,
            "topic": topic,
            "finance_tag": finance_tag,
        }
        if fmt == "image-led":
            idea["grok_imagine"] = build_imagine_prompt(topic, niche)
        ideas.append(idea)
    return ideas


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_ideas


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_idea(idea: Dict[str, str]) -> str:
    parts = [
        f"### Idea {idea['n']} -- {idea['hook']}",
        "",
        f"- **Angle:** {idea['angle']}",
        f"- **Format:** {idea['format']}",
        f"- **Why now:** {idea['why_now']}",
        f"- **Draft opener:** \"{idea['draft_opener']}\"",
        f"- **Engagement signal:** {idea['signal']}",
    ]
    if "grok_imagine" in idea:
        parts.append(f"- **Grok Imagine prompt:** {idea['grok_imagine']}")
    if idea["finance_tag"]:
        parts.append(idea["finance_tag"])
    return "\n".join(parts)


def render_report(
    x_handle: str,
    niche: str,
    ideas: List[Dict[str, str]],
    today: _dt.date,
    tone: str,
    trend_window_days: int,
) -> str:
    bucket = detect_bucket(niche)
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )
    header = textwrap.dedent(f"""\
        # Content Ideas -- {today.isoformat()}

        - **Creator:** {x_handle}
        - **Niche:** {niche}
        - **Detected bucket:** {bucket}
        - **Tone:** {tone}
        - **Trend window:** {trend_window_days} days
        - **Total ideas:** {len(ideas)}

        > {TAGLINE}

        """)
    header = license_block + header
    body = "\n\n".join(render_idea(i) for i in ideas)
    confidence = (
        "Confidence: medium -- offline seed library; for full Grok 4.3 grounding, "
        "wire `prompts/system.md` to the xAI API (see README)."
    )
    return f"{header}{body}\n\n{confidence}\n"


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


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="content-idea-generator",
        description=(
            f"Content Idea Generator v{VERSION} -- "
            "5 fresh X post ideas, every morning. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --niche "AI agents on X"
              python run.py --x-handle @creator --niche "fintech for solopreneurs" --tone data-led
              python run.py --x-handle @me --niche "productivity" --output today.md
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument("--niche", required=True, help="Niche or topic area, in quotes.")
    parser.add_argument(
        "--count", type=_ranged_int(1, 10), default=5,
        help="How many ideas to generate (1..10, default 5).",
    )
    parser.add_argument(
        "--tone", choices=("punchy", "thoughtful", "data-led"), default="punchy",
        help="Voice flavor (default punchy).",
    )
    parser.add_argument(
        "--trend-window-days", type=_ranged_int(1, 30), default=7,
        help="Trend look-back window in days (1..30, default 7).",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument(
        "--no-banner", action="store_true",
        help="Suppress the banner header (useful for piping).",
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"content-idea-generator {VERSION}",
    )
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

    try:
        ideas = generate_ideas(
            x_handle=args.x_handle,
            niche=args.niche,
            count=args.count,
            tone=args.tone,
            trend_window_days=args.trend_window_days,
            today=today,
        )
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 64

    report = render_report(
        x_handle=args.x_handle,
        niche=args.niche,
        ideas=ideas,
        today=today,
        tone=args.tone,
        trend_window_days=args.trend_window_days,
    )

    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        sys.stdout.write(f"\nOK Wrote {len(ideas)} ideas -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
