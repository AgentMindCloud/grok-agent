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
Quote Tweet Suggestor -- zero-dependency CLI demo runner.

Built for xAI, X, Grok and the ecosystem community. ❤️

This v1 runner is fully self-contained: it ships per-angle quote templates
plus auto-mode intent heuristics so creators get value the instant
`grok install this` finishes. Privacy-aware: the Original-Post-Read section
paraphrases the source post via a topic extractor, never copying verbatim.
To wire to live Grok 4.3, replace the body of `generate_quote_tweet_variants()`
with a Grok call that consumes `prompts/system.md` (auto-loaded) and returns
the same schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --original-post "tracked my first 30 days shipping AI agents"
    python run.py --x-handle @creator --original-post "5 productivity rituals" --quote-angle add_value
    python run.py --x-handle @me --original-post "long-context wins" --quote-angle contrarian --include-visual
    python run.py --x-handle @test --original-post "tracked my first 30 days shipping AI agents" --quote-angle auto --include-visual
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
TAGLINE = "Built for xAI, X, Grok and the ecosystem community. ❤️"

BANNER = (
    "============================================================\n"
    f"  QUOTE TWEET SUGGESTOR  v{VERSION}\n"
    "  2-3 quote variants in 5 seconds, distinct angles, voice-matched.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

MAX_TWEET_CHARS = 280

# ---------------------------------------------------------------------------
# Static data -- 5-angle palette specific to quote tweets
# ---------------------------------------------------------------------------

ANGLES: Tuple[str, ...] = (
    "support", "contrarian", "add_value", "question", "story-pivot",
)

INTENT_LABELS = ("claim", "question", "story", "celebration", "data", "meta")

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2")),
]
DEFAULT_BUCKET = "general"

POLICY_VIOLATING_KEYWORDS = (
    "doxx", "doxxing", "ratio them", "harass", "pile on",
    "cancel them", "ratio-bait", "expose this person",
)

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading", "earnings",
    "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
    "x money", "payout",
)

# Auto-mode angle selection by detected intent.
AUTO_ANGLE_PLAN: Dict[str, List[str]] = {
    "celebration": ["support", "add_value", "question"],
    "claim": ["contrarian", "add_value", "question"],
    "question": ["add_value", "question", "story-pivot"],
    "story": ["support", "add_value", "story-pivot"],
    "data": ["add_value", "question", "support"],
    "meta": ["support", "contrarian", "add_value"],
}

# Intent-detection keywords (lowercased).
INTENT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "celebration": ("shipped", "launched", "first", "milestone", "tracked", "done", "completed", "30 days", "week one"),
    "claim": ("wins", "beats", "table-stakes", "best", "always", "never", "the answer", "is dead", "is the one"),
    "story": ("lived", "happened", "last week", "last month", "this week", "yesterday", "story"),
    "data": ("%", "tracked", "numbers", "data", "stats"),
    "meta": ("everyone in", "this niche", "creators", "the community", "most folks", "most people"),
}

# Default to "claim" if nothing else matches; "question" if the post ends with "?"
TONE_PREPENDS: Dict[str, str] = {
    "punchy": "",
    "thoughtful": "On reflection -- ",
    "data-led": "Quick numbers: ",
    "warm": "Big fan of this -- ",
}

# Per-bucket fillers used by quote templates.
BUCKET_FILLERS: Dict[str, Dict[str, str]] = {
    "ai": {
        "expected_action": "fine-tuning",
        "artifact": "eval set",
        "check": "eval",
        "claim_phrase": "the catch-curve flattens above 20 cases, but 5 catches the dumb breaks early",
    },
    "productivity": {
        "expected_action": "to-do app stacking",
        "artifact": "weekly review",
        "check": "Friday review",
        "claim_phrase": "30-minute Friday review compounds harder than any productivity hack",
    },
    "finance": {
        "expected_action": "spreadsheet manual entry",
        "artifact": "P&L sheet",
        "check": "ledger",
        "claim_phrase": "automated tax-export saves the equivalent of one weekend per quarter",
    },
    "creator": {
        "expected_action": "follower-count chasing",
        "artifact": "content library",
        "check": "audit",
        "claim_phrase": "owned-audience math compounds once the funnel runs for 90 days",
    },
    "fitness": {
        "expected_action": "calorie counting",
        "artifact": "training log",
        "check": "log",
        "claim_phrase": "Zone 2 mitochondrial gains plateau around 16 weeks but the floor is much higher",
    },
    "general": {
        "expected_action": "the obvious move",
        "artifact": "review log",
        "check": "audit",
        "claim_phrase": "the boring move compounds when you can audit the failure mode",
    },
}

# 2 templates per angle for variety.
QUOTE_TEMPLATES_BY_ANGLE: Dict[str, List[str]] = {
    "support": [
        "+1 -- {topic_short} is the single biggest leverage move I've seen across {niche} folks shipping in v1.",
        "Co-signing this -- the {topic_short} take lands. Boring on day one, dangerous by week six.",
    ],
    "contrarian": [
        "Half-agree. {topic_short} works at v1; by v3 you're paying for {expected_action}. Worth front-loading the {check} ritual.",
        "Slight pushback: most {niche} folks who try {topic_short} skip the {check} step. That's where the edge actually lives.",
    ],
    "add_value": [
        "Adding to this: {claim_phrase}. Cheap to start, hard to argue with by week six. {check} ritual is the multiplier.",
        "Building on this -- {topic_short} compounds when you pair it with the {check} ritual. Both together is where the curve flips.",
    ],
    "question": [
        "Genuine question -- what was the smallest thing that changed your mind on {topic_short}? Curious if it was the same place I'd predict.",
        "Real question on {topic_short}: what's the one decision you'd reverse if you started over? Asking because the wrong starting axis eats most v1s in {niche}.",
    ],
    "story-pivot": [
        "Lived this -- shipped a {topic_short} thing last week and the lesson hit on day three, not day thirty. Same arc; different niche.",
        "Saw this arc last month: started thinking {expected_action} was the unlock; switched to {topic_short} on week two; haven't looked back.",
    ],
}

ANGLE_TO_ENGAGEMENT: Dict[str, str] = {
    "support": "medium-high",
    "contrarian": "high",
    "add_value": "medium-high",
    "question": "high",
    "story-pivot": "medium",
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


def detect_intent(post: str) -> str:
    s = (post or "").lower()
    if s.endswith("?") or "how do you" in s or "what's the" in s:
        return "question"
    scores: Dict[str, int] = {}
    for intent, keys in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for k in keys if k in s)
    if scores:
        best = max(scores.items(), key=lambda kv: kv[1])
        if best[1] > 0:
            return best[0]
    return "claim"


def is_finance_adjacent(text: str) -> bool:
    s = (text or "").lower()
    return any(k in s for k in FINANCE_KEYWORDS)


def violates_policy(post: str) -> bool:
    s = (post or "").lower()
    return any(k in s for k in POLICY_VIOLATING_KEYWORDS)


def deterministic_seed(x_handle: str, post: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{post.strip().lower()}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def topic_short(post: str, max_words: int = 4) -> str:
    skip = {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "is", "are", "was", "were", "be", "this", "that",
        "you", "your", "i", "my", "we", "they", "do", "does", "did", "any",
        "what", "when", "where", "why", "how", "into", "about", "than",
        "then", "so", "all", "no", "not", "yes", "thanks", "great", "love",
        "just", "really", "very", "much", "more", "some", "first", "anyone",
        "tracked", "shipping", "shipped", "build", "building", "ship",
        "days", "day", "lessons", "learned", "tips", "year", "month",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", (post or "").lower())
    keep = [w for w in words if w not in skip and len(w) > 2]
    if not keep:
        return "this"
    return " ".join(keep[:max_words])


def paraphrase_post(post: str, intent: str) -> str:
    """Generate a short paraphrase of the original post WITHOUT quoting it."""
    short = topic_short(post)
    if intent == "celebration":
        return f"A creator sharing a milestone or progress arc; takeaway centers on {short}."
    if intent == "claim":
        return f"A creator making a claim about {short} -- the assertion calls for a sharpening response."
    if intent == "question":
        return f"A creator asking the community about {short}; opens space for a value-add response."
    if intent == "story":
        return f"A creator sharing a recent lived experience around {short}; story-shaped."
    if intent == "data":
        return f"A creator sharing data or numbers around {short}; the figures are the anchor."
    if intent == "meta":
        return f"A creator commenting on community-wide patterns around {short}."
    return f"A creator's post on {short}."


def _safe_render(template: str, max_chars: int, **kwargs: str) -> str:
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


def _build_imagine_prompt(angle: str, topic: str, niche: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment illustration depicting a "
        f"'{angle}' quote-tweet response to '{topic}' in the {niche} niche. "
        "Clean composition, neon highlights, Windows 11 desktop vibe, 16:9, "
        "no text overlay."
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _select_angles(quote_angle: str, intent: str, num_variants: int, rng: random.Random) -> List[str]:
    if quote_angle == "auto":
        plan = list(AUTO_ANGLE_PLAN.get(intent, AUTO_ANGLE_PLAN["claim"]))
    else:
        plan = [quote_angle]
        # Fill with complementary angles distinct from the user pick
        complements = [a for a in ANGLES if a != quote_angle]
        rng.shuffle(complements)
        plan.extend(complements)
    # Dedup while preserving order.
    seen = set()
    out: List[str] = []
    for a in plan:
        if a not in seen:
            out.append(a)
            seen.add(a)
        if len(out) >= num_variants:
            break
    return out


def _build_variant(
    angle: str,
    fillers: Dict[str, str],
    tone: str,
    rng: random.Random,
) -> Dict[str, Any]:
    templates = QUOTE_TEMPLATES_BY_ANGLE[angle]
    chosen_idx = rng.randrange(len(templates))
    base = _safe_render(templates[chosen_idx], MAX_TWEET_CHARS, **fillers)
    toned = _apply_tone(base, tone, MAX_TWEET_CHARS)
    return {
        "angle": angle,
        "char_count": len(toned),
        "engagement": ANGLE_TO_ENGAGEMENT[angle],
        "draft": toned,
        "finance_tag": is_finance_adjacent(toned),
    }


def _spread_engagement(variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """If all variants share an engagement label, downgrade weakest by char count."""
    labels = {v["engagement"] for v in variants}
    if len(variants) >= 2 and len(labels) == 1:
        weakest = min(variants, key=lambda v: v["char_count"])
        weakest["engagement"] = "medium"
    return variants


def _build_angle_explanation(intent: str, angles: List[str]) -> str:
    intent_clause = {
        "celebration": "The original post is a milestone share, which makes `support` the natural anchor; `add_value` extends the writer's framework with concrete next-step substance; `question` opens the conversation around the unspoken decision axis.",
        "claim": "The original post is a claim, which earns a `contrarian` lead to balance the conversation publicly; `add_value` softens the contradiction with concrete substance; `question` surfaces the missing axis the claim implies but doesn't unpack.",
        "question": "The original post is itself a question, so `add_value` answers it directly with substance; `question` reframes the ask around a sharper axis; `story-pivot` grounds the answer in lived experience.",
        "story": "The original post is story-shaped, which makes `support` the natural anchor (warm + signal-amplifying); `add_value` extends the lesson with a concrete data point; `story-pivot` adds a parallel arc that resonates.",
        "data": "The original post is data-anchored, which earns an `add_value` lead with one concrete additional figure; `question` opens the methodology axis; the third angle balances the engagement spread.",
        "meta": "The original post is meta-commentary on community patterns; `support` lends signal, `contrarian` adds depth, `add_value` brings a concrete framework that operationalizes the meta point.",
    }.get(intent, "Angles selected to span at least 2 distinct response shapes for the original post's intent.")
    angle_str = " + ".join(f"`{a}`" for a in angles)
    return f"{angle_str}. {intent_clause}"


def _build_cross_template_bridges(
    angles: List[str],
    intent: str,
    niche_label: str,
    fillers: Dict[str, str],
) -> List[str]:
    bridges: List[str] = []
    if "contrarian" in angles or "add_value" in angles:
        bridges.append(
            f"If the {('contrarian' if 'contrarian' in angles else 'add_value')} variant lands hot, expand "
            f"into a full counter-thread via `thread-builder --topic \"{fillers['topic_short']}\"` -- "
            "the framework deserves a full pass."
        )
    bridges.append(
        "Triage the inbound replies on the quote via `mention-summarizer` after 24h -- "
        "the question variant will surface fresh advocate signal worth a same-day reply pass."
    )
    if intent in ("claim", "data"):
        bridges.append(
            f"Verify the quoted claim via `research-assistant --query \"{fillers['topic_short']}\" "
            "--depth quick` before posting the contrarian or add_value variant."
        )
    elif "question" in angles:
        bridges.append(
            f"After 48h, run `analytics-summarizer --time-range 7d` to confirm the quote-driven engagement "
            "compounded vs your usual baseline."
        )
    bridges.append(
        f"Spin the strongest angle into 5 follow-up post ideas via "
        f"`content-idea-generator --niche \"{niche_label}\"`."
    )
    return bridges[:5]


def _composite_engagement(variants: List[Dict[str, Any]]) -> str:
    if not variants:
        return "low"
    if any(v["engagement"] == "high" for v in variants):
        return "high"
    if all(v["engagement"] == "medium" for v in variants):
        return "medium"
    return "medium-high"


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_quote_tweet_variants(
    x_handle: str,
    original_post: str,
    quote_angle: str = "auto",
    num_variants: int = 3,
    tone: str = "punchy",
    include_visual: bool = False,
    niche: Optional[str] = None,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured quote-tweet variants dict.

    Output schema documented in P63 system prompt.
    """
    if quote_angle not in ("support", "contrarian", "add_value", "question", "story-pivot", "auto"):
        raise ValueError(
            f"quote_angle must be one of support|contrarian|add_value|question|story-pivot|auto, got {quote_angle!r}"
        )
    if num_variants < 2 or num_variants > 3:
        raise ValueError(f"num_variants must be 2 or 3, got {num_variants}")
    if tone not in TONE_PREPENDS:
        raise ValueError(f"tone must be one of {list(TONE_PREPENDS)}, got {tone!r}")
    if not original_post.strip():
        raise ValueError("original_post must be non-empty")

    today = today or _dt.date.today()

    if violates_policy(original_post):
        return {
            "refused": True,
            "warning": (
                "Original post matches policy-violating patterns (doxxing / harassment / ratio-bait). "
                "Refusing to draft quote variants per Constitution rule #7."
            ),
            "x_handle": x_handle, "today": today.isoformat(),
            "original_post": original_post,
            "headline": "", "post_paraphrase": "", "intent": "",
            "variants": [], "angle_explanation": "", "bridges": [],
            "composite_engagement": "low",
            "include_visual": include_visual,
            "visual_prompt": None,
            "niche_bucket": detect_bucket(niche or original_post),
            "niche_label": niche or "X creator",
            "quote_angle_requested": quote_angle,
        }

    rng = random.Random(deterministic_seed(x_handle, original_post, today))

    bucket = detect_bucket((niche or "") + " " + original_post)
    niche_label = niche or {
        "ai": "AI agents on X",
        "productivity": "Productivity systems for solopreneurs",
        "finance": "creator economy finance",
        "creator": "creator economy",
        "fitness": "Zone 2 training",
    }.get(bucket, "X creator")

    fillers = dict(BUCKET_FILLERS[bucket])
    fillers["topic_short"] = topic_short(original_post)
    fillers["niche"] = niche_label

    intent = detect_intent(original_post)
    angles = _select_angles(quote_angle, intent, num_variants, rng)

    variants = [_build_variant(a, fillers, tone, rng) for a in angles]
    variants = _spread_engagement(variants)

    angle_explanation = _build_angle_explanation(intent, angles)
    composite = _composite_engagement(variants)
    bridges = _build_cross_template_bridges(angles, intent, niche_label, fillers)

    visual_prompt = None
    if include_visual and variants:
        # Pick the highest-engagement variant for the visual.
        rank = {"low": 1, "medium": 2, "medium-high": 3, "high": 4}
        strongest = max(variants, key=lambda v: rank[v["engagement"]])
        visual_prompt = _build_imagine_prompt(
            strongest["angle"], fillers["topic_short"], niche_label,
        )

    headline = (
        f"{len(variants)} variants on a {intent} post: " + " + ".join(angles) +
        f"; composite engagement: {composite}."
    )

    return {
        "refused": False,
        "warning": None,
        "x_handle": x_handle,
        "today": today.isoformat(),
        "original_post_len": len(original_post),
        "post_paraphrase": paraphrase_post(original_post, intent),
        "intent": intent,
        "headline": headline,
        "variants": variants,
        "angle_explanation": angle_explanation,
        "bridges": bridges,
        "composite_engagement": composite,
        "include_visual": include_visual,
        "visual_prompt": visual_prompt,
        "niche_bucket": bucket,
        "niche_label": niche_label,
        "quote_angle_requested": quote_angle,
        "tone": tone,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_quote_tweet_variants


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
    meta = textwrap.dedent(f"""\
        # Quote Tweet Variants -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Niche bucket:** {result['niche_bucket']}
        - **Niche label:** {result['niche_label']}
        - **Quote angle (requested):** {result['quote_angle_requested']}
        - **Tone:** {result['tone']}
        - **Visuals:** {'on' if result['include_visual'] else 'off'}

        > {TAGLINE}

        > 🔒 **Privacy note:** the Original Post Read below paraphrases the source post; the runner never copies the source verbatim.

        """)

    if result["refused"]:
        body = textwrap.dedent(f"""\
            ## Refusal

            {result['warning']}

            Confidence: high -- refusal triggered before structured generation.
            """)
        return license_block + meta + body

    out: List[str] = ["## Headline", "", result["headline"], ""]

    out.append("## Original Post Read")
    out.append("")
    out.append(f"{result['post_paraphrase']} Intent: {result['intent']}.")
    out.append("")

    out.append("## Quote Tweet Variants")
    out.append("")
    for i, v in enumerate(result["variants"], start=1):
        out.append(
            f"{i}. **angle: {v['angle']}** ({v['char_count']} chars, engagement: {v['engagement']})"
        )
        out.append(f"   - \"{v['draft']}\"")
        if v["finance_tag"]:
            out.append("   Context only -- not financial advice.")
    out.append("")

    out.append("## Angle Explanation")
    out.append("")
    out.append(result["angle_explanation"])
    out.append("")

    out.append("## Cross-Template Bridges")
    out.append("")
    for b in result["bridges"]:
        out.append(f"- {b}")
    out.append("")

    confidence = (
        f"Confidence: medium-high -- {len(result['variants'])} variants spanning "
        f"{len({v['angle'] for v in result['variants']})} distinct angles, all under {MAX_TWEET_CHARS} chars; "
        f"intent detected as `{result['intent']}`. For live grounding, wire `prompts/system.md` to "
        "the xAI API (see README)."
    )
    out.append("## Confidence")
    out.append("")
    out.append(confidence)
    out.append("")

    if result.get("visual_prompt"):
        out.append("## Suggested Visual")
        out.append("")
        out.append(result["visual_prompt"])
        out.append("")

    return license_block + meta + "\n".join(out) + "\n"


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


_DEMO_POSTS: Dict[str, str] = {
    "ai": "Just tracked my first 30 days shipping AI agents. The biggest unlock was writing 5 evals on day one, not day thirty.",
    "productivity": "Single-tab focus is the most underrated productivity move in 2026. The first week feels weird, by week three it's the only way to work.",
    "finance": "Tax-export from your tool saved me a weekend this quarter. Game changer for solo creators with X Money payouts.",
    "creator": "Owned-audience math beats follower count once you cross 90 days of newsletter consistency. Most creators give up at week six.",
    "fitness": "Zone 2 for desk workers is the best longevity bet you can make this year. Cheap, boring, compounds over months.",
}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="quote-tweet-suggestor",
        description=(
            f"Quote Tweet Suggestor v{VERSION} -- 2-3 quote variants in 5 seconds. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --original-post "tracked my first 30 days shipping AI agents"
              python run.py --x-handle @creator --original-post "5 productivity rituals" --quote-angle add_value
              python run.py --x-handle @me --demo ai --include-visual
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument("--original-post", default=None, help="The X post you're quoting (in quotes). Required unless --demo is set.")
    parser.add_argument(
        "--demo", choices=sorted(_DEMO_POSTS.keys()), default=None,
        help="Use a prefab niche post for first-run demos.",
    )
    parser.add_argument(
        "--quote-angle",
        choices=("support", "contrarian", "add_value", "question", "story-pivot", "auto"),
        default="auto",
        help="Preferred angle for variants; 'auto' picks based on detected intent (default auto).",
    )
    parser.add_argument(
        "--num-variants", type=_ranged_int(2, 3), default=3,
        help="How many variants to return (2 or 3, default 3).",
    )
    parser.add_argument(
        "--tone", choices=tuple(TONE_PREPENDS.keys()), default="punchy",
        help="Voice flavor (default punchy).",
    )
    parser.add_argument("--include-visual", action="store_true",
                        help="Attach a Grok Imagine prompt to the strongest variant.")
    parser.add_argument("--niche", default=None, help="Optional niche hint (e.g. 'AI agents on X').")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument("--version", action="version", version=f"quote-tweet-suggestor {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    post = args.original_post or (_DEMO_POSTS[args.demo] if args.demo else None)
    if not post:
        sys.stderr.write(
            "X  --original-post is required (or pass --demo {ai|productivity|finance|creator|fitness})\n"
        )
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
        result = generate_quote_tweet_variants(
            x_handle=args.x_handle,
            original_post=post,
            quote_angle=args.quote_angle,
            num_variants=args.num_variants,
            tone=args.tone,
            include_visual=args.include_visual,
            niche=args.niche,
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
        n = len(result.get("variants", []))
        verb = "Refused" if result["refused"] else f"Wrote {n}-variant quote tweet package"
        sys.stdout.write(f"\nOK {verb} -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
