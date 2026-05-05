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
Reply Drafter -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships a deterministic, voice-aware
draft library so creators get value the instant `grok install this` finishes,
without needing an xAI API key. To wire to live Grok 4.3, replace the body
of `generate_reply_drafts()` with a Grok call that consumes
`prompts/system.md` (auto-loaded below) and returns the same draft schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --original-post "Great thread on Grok agents!"
    python run.py --x-handle @creator --mention "Have you tried prompt caching?" --tone warm
    python run.py --x-handle @me --original-post "..." --num-drafts 3 --output today.md
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
from typing import Any, Callable, Dict, List, Optional

VERSION = "0.1.0"
TAGLINE = "Built to help xAI and Grok win."

BANNER = (
    "============================================================\n"
    f"  REPLY DRAFTER  v{VERSION}\n"
    "  3 voice-matched X reply drafts in 5 seconds.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Static draft library -- deterministic, offline, zero-dependency.
# Replace `generate_reply_drafts()` body with a Grok 4.3 call to upgrade.
# ---------------------------------------------------------------------------

ANGLES: List[str] = [
    "agree-and-amplify",
    "gentle-disagree",
    "ask-a-sharp-question",
    "add-data",
    "share-a-tip",
    "comparison",
    "story-pivot",
    "mic-drop",
]

LENGTH_SLOTS: List[Dict[str, Any]] = [
    {"label": "Short", "key": "short", "max_chars": 140},
    {"label": "Medium", "key": "medium", "max_chars": 220},
    {"label": "Value-add", "key": "value_add", "max_chars": 280},
]

# Each angle has 3 length variants. Templates use {topic}, {alt}, {niche}.
ANGLE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "agree-and-amplify": {
        "short": "+1 -- {topic} is the underrated edge here.",
        "medium": "Yes -- and the part most folks miss: {topic} compounds when you ship it weekly. Month one feels slow; month three is a different story.",
        "value_add": "Strong agree on {topic}. The piece I'd add: it only compounds if you keep a tiny eval set and review it on Fridays. Same effort, very different velocity by week six.",
    },
    "gentle-disagree": {
        "short": "Almost -- but {topic} usually loses to {alt} once volume kicks in.",
        "medium": "Half-agree. {topic} works at v1; by v3 you're really paying for {alt}. Worth front-loading the boring bit.",
        "value_add": "Slight pushback: {topic} is the right call at v1, but {alt} kicks in around v3 and the cost gets quiet then loud. Cheap fix early beats an expensive rebuild later -- worth a Friday review.",
    },
    "ask-a-sharp-question": {
        "short": "What broke first when you shipped it? That's where v2 lives.",
        "medium": "Genuine question -- what's the smallest thing that changed your mind on {topic}? Curious if it's the same place I'd predict.",
        "value_add": "Real question for you -- what's the one decision you'd reverse if you started {topic} over? Asking because the wrong starting axis is what eats most v1s in {niche}, and it's usually invisible until v2.",
    },
    "add-data": {
        "short": "Worth noting: most folks underestimate {topic} by ~2x.",
        "medium": "Quick context -- in {niche}, {topic} usually moves twice as far and roughly half as fast as v1 plans assume.",
        "value_add": "Adding a frame: in {niche}, {topic} typically lands twice as hard and about half as fast as v1 plans assume. Tracking the second number (speed) is where most teams quietly lose months.",
    },
    "share-a-tip": {
        "short": "Tip: cap inputs, log every call, eval weekly. {topic} fixes itself.",
        "medium": "If it helps -- the loop that actually works for {topic}: cap inputs, log every call, ship a tiny eval, review Fridays. Boring; works.",
        "value_add": "Tiny playbook for {topic} that's worked for me: 1) cap inputs 2) log every call 3) Promptfoo set under 20 cases 4) Friday review. Boring on day one, dangerous by week six.",
    },
    "comparison": {
        "short": "{topic} vs {alt}: not even close once you ship.",
        "medium": "{topic} vs {alt} is the wrong frame. The real question is which one survives v3 -- and {topic} usually does.",
        "value_add": "Hot take on {topic} vs {alt}: feels like a debate at v1, becomes obvious at v3. The differentiator is whether you can audit the failure mode -- {topic} just lets you do that earlier and cheaper.",
    },
    "story-pivot": {
        "short": "Shipped a similar thing last month -- same lesson on {topic}.",
        "medium": "Shipped a v1 of this last month. The thing that actually moved me from doubt to ship was {topic}. Not glamorous; very effective.",
        "value_add": "I lived this one last month. v1 felt fine, v2 wobbled, then {topic} fixed half the issues in one weekend. If you're at the wobble stage in {niche}, that's probably your next move too.",
    },
    "mic-drop": {
        "short": "{topic}. That's the whole post.",
        "medium": "{topic} is the post. Everything else is decoration. Save this for week three.",
        "value_add": "If I were rewriting this thread to one line: {topic} is the whole answer in {niche}. The rest is implementation detail. Save it; ship; come back in three weeks and tell me I'm wrong.",
    },
}

# Engagement labels per (angle, length-slot). Tuned so 3 drafts span >=2 labels.
ANGLE_TO_ENGAGEMENT: Dict[str, List[str]] = {
    "agree-and-amplify":   ["medium",      "medium",      "medium-high"],
    "gentle-disagree":     ["medium-high", "medium-high", "high"],
    "ask-a-sharp-question": ["medium-high", "medium-high", "high"],
    "add-data":            ["medium",      "medium-high", "medium-high"],
    "share-a-tip":         ["medium",      "medium-high", "high"],
    "comparison":          ["medium-high", "medium-high", "high"],
    "story-pivot":         ["medium",      "medium-high", "high"],
    "mic-drop":            ["medium-high", "high",        "high"],
}

# Niche bucket detection (mirrors content-idea-generator).
NICHE_BUCKETS: List[tuple] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar")),
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

# Tone-modifier prepends. Applied only if the result fits within the slot's
# max_chars (otherwise the base draft is used unchanged).
TONE_PREPENDS: Dict[str, str] = {
    "punchy": "",
    "thoughtful": "On reflection -- ",
    "data-led": "Quick numbers: ",
    "warm": "Big fan of this -- ",
}

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading",
    "earnings", "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
)

VISUAL_KEYWORDS = (
    "chart", "graph", "dashboard", "screenshot", "image", "video",
    "mockup", "diagram", "visualize", "viz",
)

BAIT_KEYWORDS = (
    "send dm for", "send me a dm", "click my bio link", "follow back",
    "free crypto", "free airdrop", "this person is a", "report this",
    "comment 'yes'", "comment yes for", "rt to win", "swatted",
    "rugpull", "rug pull",
)

STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "if", "while", "of", "in", "on",
    "at", "to", "for", "with", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "you", "your", "i", "my", "we", "us",
    "they", "them", "it", "its", "as", "by", "from", "have", "has", "had",
    "do", "does", "did", "should", "could", "would", "great", "thread",
    "post", "tweet", "just", "really", "very", "much", "more", "some",
    "any", "what", "when", "where", "why", "how", "who", "out", "up",
    "down", "into", "about", "than", "then", "so", "all", "no", "not",
    "yes", "ok", "thanks", "thank", "please", "hi", "hey", "hello",
    "look", "check", "see", "watch", "consider", "want", "need",
    "trying", "try", "tried", "love", "like", "first", "next", "still",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_bucket(niche_or_post: str) -> str:
    blob = niche_or_post.lower()
    for bucket, keys in NICHE_BUCKETS:
        for k in keys:
            if k in blob:
                return bucket
    return DEFAULT_BUCKET


def extract_topic(post: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", post.lower())
    content = [w for w in words if w not in STOPWORDS and len(w) > 2]
    if not content:
        return "this"
    if len(content) >= 2:
        return f"{content[0]} {content[1]}"
    return content[0]


def is_finance_adjacent(post: str, niche: str, draft_text: str) -> bool:
    blob = (post + " " + niche + " " + draft_text).lower()
    return any(k in blob for k in FINANCE_KEYWORDS)


def looks_visual(post: str) -> bool:
    p = post.lower()
    return any(k in p for k in VISUAL_KEYWORDS)


def is_bait_or_scam(post: str) -> bool:
    p = post.lower()
    return any(k in p for k in BAIT_KEYWORDS)


def deterministic_seed(x_handle: str, post: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{post.strip()}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def build_imagine_prompt(topic: str, niche: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment illustration depicting "
        f"'{topic}' in the {niche} niche. Clean composition, neon "
        "highlights, Windows 11 desktop vibe, 16:9, no text overlay."
    )


def _safe_render(template: str, max_chars: int, **kwargs: str) -> str:
    """Render `template` with kwargs; tighten if over max_chars."""
    text = template.format(**kwargs).strip()
    if len(text) <= max_chars:
        return text
    # Last-ditch tighten: drop trailing sentence-after-period chunks.
    parts = re.split(r"(?<=[.!?])\s+", text)
    while parts and len(" ".join(parts)) > max_chars:
        parts.pop()
    tightened = " ".join(parts).strip()
    if 0 < len(tightened) <= max_chars:
        return tightened
    # Hard cut as final fallback (preserves full words).
    cut = text[: max_chars].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(",;:")
    return cut


def _apply_tone(text: str, tone: str, max_chars: int) -> str:
    prepend = TONE_PREPENDS.get(tone, "")
    if not prepend:
        return text
    candidate = prepend + text
    return candidate if len(candidate) <= max_chars else text


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_reply_drafts(
    x_handle: str,
    original_post: str,
    tone: Optional[str] = None,
    niche: Optional[str] = None,
    num_drafts: int = 3,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a dict of drafts (or a refusal) for (x_handle, original_post, today).

    Deterministic: same args + same date = same drafts. Tomorrow = fresh ones.
    Output schema:
        {
          "refused": bool,
          "warning": str | None,
          "drafts": [
             {"slot": "short"|"medium"|"value_add",
              "label": "Short"|"Medium"|"Value-add",
              "char_limit": int, "char_count": int,
              "angle": str, "engagement": str,
              "format": "text reply"|"image", "reply": str,
              "finance_tag": bool, "grok_imagine": str | None}
          ],
          "tone_used": str,
          "niche_bucket": str,
          "topic": str,
        }
    """
    if num_drafts < 1 or num_drafts > 3:
        raise ValueError(f"num_drafts must be 1..3, got {num_drafts}")
    tone = tone or "punchy"
    if tone not in TONE_PREPENDS:
        raise ValueError(f"tone must be one of {list(TONE_PREPENDS)}, got {tone!r}")
    if not original_post.strip():
        raise ValueError("original_post must be non-empty")

    today = today or _dt.date.today()

    # Trap detection: refuse before drafting if the post looks like bait.
    if is_bait_or_scam(original_post):
        return {
            "refused": True,
            "warning": (
                "Original post matches bait/scam patterns "
                "(e.g. DM-bait, RT-to-win, doxx-bait). "
                "Refusing to draft per Constitution rule #7."
            ),
            "drafts": [],
            "tone_used": tone,
            "niche_bucket": detect_bucket(niche or original_post),
            "topic": "",
        }

    rng = random.Random(deterministic_seed(x_handle, original_post, today))
    bucket = detect_bucket(niche or original_post)
    alt = ALT_BY_BUCKET[bucket]
    topic = extract_topic(original_post)
    visual = looks_visual(original_post)

    # Pick `num_drafts` distinct angles deterministically.
    angles_pool = ANGLES[:]
    rng.shuffle(angles_pool)
    chosen_angles = angles_pool[:num_drafts]

    drafts: List[Dict[str, Any]] = []
    for i in range(num_drafts):
        slot = LENGTH_SLOTS[i]  # short -> medium -> value_add
        angle = chosen_angles[i]
        template = ANGLE_TEMPLATES[angle][slot["key"]]
        base = _safe_render(
            template,
            slot["max_chars"],
            topic=topic,
            alt=alt,
            niche=(niche or bucket),
        )
        reply = _apply_tone(base, tone, slot["max_chars"])
        engagement = ANGLE_TO_ENGAGEMENT[angle][i]

        # Format heuristic: image only on the value-add slot, only when the
        # original post looks visual. Polls deferred to v2.
        fmt = "text reply"
        grok_imagine: Optional[str] = None
        if slot["key"] == "value_add" and visual:
            fmt = "image"
            grok_imagine = build_imagine_prompt(topic, niche or bucket)

        finance = is_finance_adjacent(original_post, niche or bucket, reply)
        drafts.append({
            "slot": slot["key"],
            "label": slot["label"],
            "char_limit": slot["max_chars"],
            "char_count": len(reply),
            "angle": angle,
            "engagement": engagement,
            "format": fmt,
            "reply": reply,
            "finance_tag": finance,
            "grok_imagine": grok_imagine,
        })

    # Spread engagement labels: if all 3 share a label, downgrade the weakest.
    engagement_set = {d["engagement"] for d in drafts}
    if len(engagement_set) == 1 and len(drafts) >= 2:
        weakest = min(drafts, key=lambda d: d["char_count"])
        weakest["engagement"] = "medium"

    return {
        "refused": False,
        "warning": None,
        "drafts": drafts,
        "tone_used": tone,
        "niche_bucket": bucket,
        "topic": topic,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_reply_drafts


def load_system_prompt() -> str:
    """Load prompts/system.md so future Grok wiring has a one-line entrypoint."""
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_draft(idx: int, draft: Dict[str, Any]) -> str:
    parts = [
        f"### Draft {idx} -- {draft['label']} ({draft['char_count']} / {draft['char_limit']} chars)",
        "",
        f"- **Angle:** {draft['angle']}",
        f"- **Engagement estimate:** {draft['engagement']}",
        f"- **Format:** {draft['format']}",
        f"- **Reply:** \"{draft['reply']}\"",
    ]
    if draft.get("grok_imagine"):
        parts.append(f"- **Grok Imagine prompt:** {draft['grok_imagine']}")
    if draft["finance_tag"]:
        parts.append("Context only -- not financial advice.")
    return "\n".join(parts)


def render_report(
    x_handle: str,
    original_post: str,
    result: Dict[str, Any],
    today: _dt.date,
    tone: str,
) -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )

    if result["refused"]:
        body = textwrap.dedent(f"""\
            # Reply Drafts -- {today.isoformat()}

            - **Creator:** {x_handle}
            - **Tone:** {tone}
            - **Refused:** yes

            > {TAGLINE}

            ## Refusal

            {result['warning']}

            Confidence: high -- bait/scam patterns matched; no drafts generated.
            """)
        return license_block + body

    drafts_md = "\n\n".join(render_draft(i + 1, d) for i, d in enumerate(result["drafts"]))
    confidence = (
        "Confidence: medium -- offline seed library; for full Grok 4.3 voice "
        "matching, wire `prompts/system.md` to the xAI API (see README)."
    )
    header = textwrap.dedent(f"""\
        # Reply Drafts -- {today.isoformat()}

        - **Creator:** {x_handle}
        - **Original post:** "{original_post}"
        - **Detected bucket:** {result['niche_bucket']}
        - **Topic:** {result['topic']}
        - **Tone used:** {result['tone_used']}
        - **Drafts:** {len(result['drafts'])}

        > {TAGLINE}

        """)
    return f"{license_block}{header}{drafts_md}\n\n{confidence}\n"


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
        prog="reply-drafter",
        description=(
            f"Reply Drafter v{VERSION} -- 3 voice-matched X reply drafts in 5 seconds. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --original-post "Great thread on Grok agents!"
              python run.py --x-handle @creator --mention "Have you tried prompt caching?" --tone warm
              python run.py --x-handle @me --original-post "..." --num-drafts 3 --output today.md
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    post_group = parser.add_mutually_exclusive_group(required=True)
    post_group.add_argument("--original-post", help="Full text of the X post you're replying to (in quotes).")
    post_group.add_argument("--mention", help="Alias for --original-post.")
    parser.add_argument(
        "--tone", choices=("punchy", "thoughtful", "data-led", "warm"), default="punchy",
        help="Voice flavor (default punchy).",
    )
    parser.add_argument("--niche", default=None, help="Optional niche hint (e.g. 'AI tooling').")
    parser.add_argument(
        "--num-drafts", type=_ranged_int(1, 3), default=3,
        help="How many drafts to return (1..3, default 3).",
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
    parser.add_argument("--version", action="version", version=f"reply-drafter {VERSION}")
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

    post = args.original_post or args.mention
    try:
        result = generate_reply_drafts(
            x_handle=args.x_handle,
            original_post=post,
            tone=args.tone,
            niche=args.niche,
            num_drafts=args.num_drafts,
            today=today,
        )
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 64

    report = render_report(
        x_handle=args.x_handle,
        original_post=post,
        result=result,
        today=today,
        tone=args.tone,
    )

    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        n = len(result["drafts"])
        verb = "Refused" if result["refused"] else f"Wrote {n} draft(s)"
        sys.stdout.write(f"\nOK {verb} -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0 if not result["refused"] else 0  # refusal is a successful run


if __name__ == "__main__":
    sys.exit(main())
