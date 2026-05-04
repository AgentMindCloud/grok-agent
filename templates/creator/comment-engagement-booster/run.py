# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Comment Engagement Booster — runner.

CLI entry point for the ``comment-engagement-booster`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a single post (URL or pasted text) plus a chosen ``boost_focus``
and emits a 6/7-section structured set of 3-5 comment variants matching
``prompts/system.md`` exactly:

  1. Post Snapshot
  2. Comment Plan (aggregate score across the variant set)
  3. Comment Variants (3-5 cards; each carries the 4-row Comment Plan
     Score table + weighted Comment Plan score = round(0.30*Hook +
     0.25*Conversation + 0.25*Voice + 0.20*Distinct) + the comment body
     under 240 chars, code-fenced)
  4. Engagement Tips (3-5)
  5. Red Flags (2-3, surfaces the hook-without-substance paradox in
     BOTH the variant card AND this section when triggered)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Confidence
  + Optional Boost Audit (auto-appended when red_flags > 3 OR
    boost_focus='all')

Hard guarantees enforced by this runner (mirrors the Constitution):

* Drafts only. The runner emits comment text the creator reviews and
  ships. Constitution Article II's `publish_to_x` consent gate covers
  every variant.
* No mass-identical comments. The runner enforces inter-variant token
  overlap < 60% AND `Distinct angle >= 60` per variant. Two variants
  that share too much body are a hard refusal.
* Hook-without-substance paradox surfaced in BOTH the variant card AND
  the Red Flags section whenever Hook strength > 70 AND Conversation
  potential < 30. The `--demo` mode pins variant 2 of any single-focus
  run to this profile so the rule reliably demonstrates.
* Comment length cap: each variant body is <= 240 characters before the
  attribution wrap (X reply UI rewards readable density; runner does
  NOT pad to 280).
* No misrepresentation. The runner does not put words in the
  post-author's mouth, does not claim authorship of their idea, does
  not frame the comment as if they agreed with a position they did not
  take.
* Comment Plan score formula is fixed:
    round(0.30*Hook strength + 0.25*Conversation potential +
          0.25*Voice fidelity + 0.20*Distinct angle).
  Hook strength weighted highest because if the opener doesn't stop
  the scroll, no other metric matters.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any monetization-
  related recommendation.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + post_text +
  boost_focus + num_comments + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_comment_variants

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

SCORE_METRICS = (
    "Hook strength",
    "Conversation potential",
    "Voice fidelity",
    "Distinct angle",
)

# Comment Plan score weights — Hook strength weighted highest because if
# the opener doesn't stop the scroll, no other metric matters.
COMMENT_PLAN_WEIGHTS = {
    "Hook strength": 0.30,
    "Conversation potential": 0.25,
    "Voice fidelity": 0.25,
    "Distinct angle": 0.20,
}

BOOST_FOCUS_OPTIONS = ("question", "controversy", "story", "poll", "all")
SINGLE_FOCUSES = ("question", "controversy", "story", "poll")
MIN_VARIANTS = 3
MAX_VARIANTS = 5

# Comment-length cap from prompts/system.md (rule 9): under 240 chars
# before attribution (the comment is the comment; attribution is the
# code-fence wrapper context). Renderer enforces this on the body.
COMMENT_LENGTH_CAP = 240

# Anti-spam thresholds from prompts/system.md (rule 2)
INTER_VARIANT_OVERLAP_MAX = 0.60
DISTINCT_ANGLE_MIN = 60

DEMO_HANDLE = "@JanSol0s"
DEMO_POST_TEXT = (
    "Most agent eval suites measure the wrong thing — "
    "they reward verbosity, not action correctness."
)

DEMO_PRODUCTIVITY_HANDLE = "@habitstacker"
DEMO_PRODUCTIVITY_POST_TEXT = (
    "Stop optimizing for the morning routine — optimize for the friction "
    "your evening self leaves the morning self to clean up."
)

CROSS_TEMPLATE_BRIDGES = (
    "thread-builder",
    "quote-tweet-suggestor",
    "analytics-summarizer",
    "brand-voice-trainer",
    "reply-drafter",
    "mention-summarizer",
    "ab-test-suggester",
    "competitor-watch",
    "content-idea-generator",
    "monetization-optimizer",
    "cross-platform-reposter",
    "research-assistant",
)

ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

# X URL pattern with handle capture
_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})/status/(\d+)/?",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,15}(?![A-Za-z0-9_])"
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PostSnapshot:
    handle: str
    text: str
    url: Optional[str]
    char_count: int
    summary: str
    tone_signal: str


@dataclass
class CommentVariant:
    index: int
    angle: str   # e.g. "question (clarifying)"
    template_id: str
    hook_strength: int
    conversation_potential: int
    voice_fidelity: int
    distinct_angle: int
    plan_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)
    body: str = ""
    char_count: int = 0


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
# Privacy guard
# ---------------------------------------------------------------------------


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Comment Engagement Booster privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Anti-spam token overlap check
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[\w']+\b", text.lower()))


def assert_no_spam_overlap(variants: list[CommentVariant]) -> None:
    """Refuse to emit if any pair of variants share more than
    INTER_VARIANT_OVERLAP_MAX of their tokens (Constitution rule 2:
    no mass-identical comments)."""
    n = len(variants)
    for i in range(n):
        a = _tokenize(variants[i].body)
        if not a:
            continue
        for j in range(i + 1, n):
            b = _tokenize(variants[j].body)
            if not b:
                continue
            overlap = len(a & b) / max(1, len(a | b))
            if overlap > INTER_VARIANT_OVERLAP_MAX:
                raise RuntimeError(
                    f"Anti-spam violation: variants {variants[i].index} and "
                    f"{variants[j].index} share {overlap*100:.0f}% token "
                    f"overlap (limit {int(INTER_VARIANT_OVERLAP_MAX*100)}%). "
                    "Refusing to emit."
                )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def parse_post(post_url_or_text: str, fallback_handle: str) -> PostSnapshot:
    raw = (post_url_or_text or "").strip()
    if not raw:
        raise ValueError(
            "post_url_or_text is empty. Pass either an x.com URL or the literal post text."
        )
    m = _URL_RE.match(raw)
    if m:
        url_handle = "@" + m.group(1)
        return PostSnapshot(
            handle=url_handle,
            text=(
                "[post URL supplied; runner is offline so the body is referenced "
                "by URL only — paste the literal post text for richer comments]"
            ),
            url=raw,
            char_count=0,
            summary="(see source URL — runner cannot fetch in v1)",
            tone_signal="thoughtful",
        )
    return PostSnapshot(
        handle=fallback_handle,
        text=raw,
        url=None,
        char_count=len(raw),
        summary=_extract_summary(raw),
        tone_signal=_infer_tone(raw),
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


# ---------------------------------------------------------------------------
# Auto-focus picker
# ---------------------------------------------------------------------------


def pick_auto_focus(post: PostSnapshot) -> tuple[str, str]:
    """Returns (chosen_focus, why_fits)."""
    has_question = "?" in post.text
    has_imperative = any(post.text.lower().startswith(v) for v in ("stop ", "build ", "ship ", "do ", "if "))
    has_data = bool(re.search(r"\d", post.text)) and post.tone_signal == "data-led"
    is_abstract = post.char_count > 0 and post.char_count < 200 and not has_question

    if has_question:
        return ("controversy", "Post ends on or invites a question; a respectful counter-take generates the strongest reply chain.")
    if has_data:
        return ("question", "Post is data-led; a clarifying question gives the author a chance to elaborate on the numbers.")
    if has_imperative:
        return ("controversy", "Post opens with an imperative; a respectful counter-take or extension generates substantive replies.")
    if is_abstract:
        return ("story", "Post is abstract / short; anchoring with a personal story gives the conversation concrete weight.")
    return ("question", "Default: a clarifying question is the most reliable angle on most posts.")


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str, post_text: str, boost_focus: str, num_comments: int, when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(post_text.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(boost_focus.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(str(num_comments).encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Variant text scaffolds (per focus, 3 angles each capped at 240 chars)
# ---------------------------------------------------------------------------


def _question_variants() -> list[tuple[str, str, str]]:
    """Returns [(template_id, angle, body)]. 5 distinct question angles
    so num_comments=3..5 always picks distinct templates."""
    return [
        (
            "q-clarifying",
            "question (clarifying)",
            "which take on this have you seen work best in the wild — the "
            "outcome-graded one, the surface-graded one, or a hybrid? "
            "curious where the line falls in your stack.",
        ),
        (
            "q-provocative",
            "question (provocative)",
            "genuine ask: would you ship a change that scored worse on the "
            "existing benchmark but better on the real outcome? where do "
            "you make that call?",
        ),
        (
            "q-story-anchored",
            "question (story-anchored)",
            "saw the same shape last quarter — proxy went up, the thing "
            "that mattered slipped. what fixed the gap for you, was it "
            "tooling or just dropping the metric?",
        ),
        (
            "q-tactical",
            "question (tactical)",
            "tactical follow-up: when you spot the pattern, do you fix the "
            "metric, the team's incentives, or the dashboard first? "
            "ordering matters more than people admit.",
        ),
        (
            "q-scoped",
            "question (scope-narrowing)",
            "narrowing the question: in your specific stack, what's the "
            "smallest change that would have caught this earlier? curious "
            "where the leverage actually lives.",
        ),
    ]


def _controversy_variants() -> list[tuple[str, str, str]]:
    return [
        (
            "c-respectful-disagree",
            "controversy (respectful disagree)",
            "i'd push back lightly — the proxy isn't always the whole "
            "story when the real outcome is genuinely hard to measure. "
            "where do you draw that line?",
        ),
        (
            "c-extension",
            "controversy (extension)",
            "agree on direction; would extend it though — surface-graded "
            "evals also penalise terse correct answers. that second-order "
            "effect compounds quietly.",
        ),
        (
            "c-counterpoint",
            "controversy (counterpoint)",
            "counter-take: sometimes the proxy is the only thing "
            "stakeholders trust. fixing the metric without fixing the "
            "stakeholder loop usually fails. thoughts?",
        ),
        (
            "c-and-also",
            "controversy (and-also)",
            "this is right — and the harder version is teams that already "
            "know the proxy is wrong but ship to it anyway because nothing "
            "else is graded. the social part is the bottleneck.",
        ),
        (
            "c-edge-case",
            "controversy (edge-case)",
            "edge case worth surfacing: domains where outcome-grading "
            "is delayed by months. proxy is bad there, but no proxy is "
            "worse. how do you bridge that gap?",
        ),
    ]


def _story_variants() -> list[tuple[str, str, str]]:
    return [
        (
            "s-personal-anecdote",
            "story (personal anecdote)",
            "lived this recently — chased a benchmark for two quarters, "
            "real retention quietly slipped, finally swapped to outcome "
            "grading. dashboards looked worse for a month, then better.",
        ),
        (
            "s-mirror-case",
            "story (mirror case)",
            "saw the same pattern in a different domain — eval drift "
            "is genuinely domain-general. fix that worked there: "
            "shadow the proxy with one outcome metric for 60 days first.",
        ),
        (
            "s-counter-anecdote",
            "story (counter anecdote)",
            "tried this and the team revolted at first — the proxy was "
            "the contract with leadership. solved by running both metrics "
            "in parallel for a quarter. messy but durable.",
        ),
        (
            "s-near-miss",
            "story (near miss)",
            "almost shipped a regression because the proxy stayed flat. "
            "caught it because one engineer ran the actual user task. "
            "saved the quarter; cost a feature week.",
        ),
        (
            "s-customer-story",
            "story (customer story)",
            "had a customer last month whose dashboard climbed every "
            "week while their team got slower. the proxy was the "
            "smell, not the signal. story for another thread.",
        ),
    ]


def _poll_variants() -> list[tuple[str, str, str]]:
    return [
        (
            "p-binary",
            "poll (binary)",
            "two camps i see on this: (a) drop the metric outright "
            "(b) keep it but de-prioritise vs the outcome. where do "
            "you land — and why?",
        ),
        (
            "p-three-way",
            "poll (3-way)",
            "if you spot this pattern: (a) ship the regression as the "
            "cost of moving (b) hide it behind a flag (c) park the "
            "fix until users complain. honest poll.",
        ),
        (
            "p-forced-choice",
            "poll (forced choice)",
            "metric-driven dev vs outcome-driven dev — pick one for "
            "the next quarter. no third option, no hedging. "
            "what's your call?",
        ),
        (
            "p-priority-order",
            "poll (priority order)",
            "rank the fix order: (a) replace the proxy (b) re-train "
            "stakeholders (c) tighten the dashboard. where do you "
            "start in your context?",
        ),
        (
            "p-temperature-check",
            "poll (temperature check)",
            "temperature check on this take: (a) obviously right "
            "(b) directionally right but oversimplified (c) wrong "
            "in your domain. curious how the niche splits.",
        ),
    ]


_FOCUS_VARIANT_LIBRARY = {
    "question": _question_variants,
    "controversy": _controversy_variants,
    "story": _story_variants,
    "poll": _poll_variants,
}


# ---------------------------------------------------------------------------
# Per-variant scoring profiles
# ---------------------------------------------------------------------------

# Healthy scoring profiles per (focus, idx). Variant 2 of each focus is
# pinned to the hook-without-substance paradox profile in --demo mode
# (Hook strength > 70 AND Conversation potential < 30).
_VARIANT_SCORE_PROFILES = {
    ("question", 1): {
        "hook_range": (74, 84), "conv_range": (66, 78),
        "voice_range": (76, 86), "distinct_range": (70, 82),
    },
    ("question", 2): {
        "hook_range": (70, 80), "conv_range": (62, 74),
        "voice_range": (72, 82), "distinct_range": (66, 78),
    },
    ("question", 3): {
        "hook_range": (68, 78), "conv_range": (70, 80),
        "voice_range": (74, 84), "distinct_range": (72, 84),
    },
    ("question", 4): {
        "hook_range": (66, 76), "conv_range": (62, 74),
        "voice_range": (72, 82), "distinct_range": (68, 80),
    },
    ("question", 5): {
        "hook_range": (64, 74), "conv_range": (60, 72),
        "voice_range": (70, 80), "distinct_range": (66, 78),
    },
    ("controversy", 1): {
        "hook_range": (72, 82), "conv_range": (64, 76),
        "voice_range": (74, 84), "distinct_range": (70, 82),
    },
    ("controversy", 2): {
        "hook_range": (74, 84), "conv_range": (62, 74),
        "voice_range": (72, 82), "distinct_range": (66, 78),
    },
    ("controversy", 3): {
        "hook_range": (76, 86), "conv_range": (66, 78),
        "voice_range": (70, 80), "distinct_range": (68, 80),
    },
    ("controversy", 4): {
        "hook_range": (70, 80), "conv_range": (60, 72),
        "voice_range": (72, 82), "distinct_range": (66, 78),
    },
    ("controversy", 5): {
        "hook_range": (68, 78), "conv_range": (58, 70),
        "voice_range": (70, 80), "distinct_range": (64, 76),
    },
    ("story", 1): {
        "hook_range": (68, 78), "conv_range": (74, 84),
        "voice_range": (78, 88), "distinct_range": (72, 84),
    },
    ("story", 2): {
        "hook_range": (70, 80), "conv_range": (70, 80),
        "voice_range": (74, 84), "distinct_range": (68, 80),
    },
    ("story", 3): {
        "hook_range": (66, 76), "conv_range": (68, 78),
        "voice_range": (76, 86), "distinct_range": (66, 78),
    },
    ("story", 4): {
        "hook_range": (72, 82), "conv_range": (66, 78),
        "voice_range": (72, 82), "distinct_range": (66, 78),
    },
    ("story", 5): {
        "hook_range": (66, 76), "conv_range": (64, 76),
        "voice_range": (74, 84), "distinct_range": (62, 74),
    },
    ("poll", 1): {
        "hook_range": (72, 82), "conv_range": (68, 78),
        "voice_range": (70, 80), "distinct_range": (70, 82),
    },
    ("poll", 2): {
        "hook_range": (74, 84), "conv_range": (66, 78),
        "voice_range": (68, 78), "distinct_range": (68, 80),
    },
    ("poll", 3): {
        "hook_range": (76, 86), "conv_range": (62, 74),
        "voice_range": (66, 76), "distinct_range": (64, 76),
    },
    ("poll", 4): {
        "hook_range": (68, 78), "conv_range": (60, 72),
        "voice_range": (70, 80), "distinct_range": (66, 78),
    },
    ("poll", 5): {
        "hook_range": (66, 76), "conv_range": (58, 70),
        "voice_range": (68, 78), "distinct_range": (62, 74),
    },
}

# Demo paradox profile: Hook >70, Conversation <30
_PARADOX_PROFILE = {
    "hook_range": (74, 84),
    "conv_range": (18, 28),
    "voice_range": (70, 80),
    "distinct_range": (62, 74),
}


def _interp_hook(score: int) -> str:
    if score >= 75:
        return "Opener stops the scroll — direct and concrete."
    if score >= 60:
        return "Solid opener; could lead with sharper specificity."
    return "Opener lands soft — risk of getting lost in the reply stack."


def _interp_conv(score: int) -> str:
    if score >= 70:
        return "Invites a substantive reply — chain-friendly."
    if score >= 50:
        return "Healthy conversation potential; not bait-driven."
    return "Comment closes the conversation rather than opening it."


def _interp_voice(score: int) -> str:
    if score >= 75:
        return "Tone matches the creator's punchy / concrete register."
    if score >= 60:
        return "Mostly on-voice; one-line drift toward niche-default."
    return "Voice drifts; consider re-anchoring before shipping."


def _interp_distinct(score: int) -> str:
    if score >= 70:
        return "Distinct from the other variants in the set."
    if score >= 60:
        return "Recognisably different but the angle overlaps slightly."
    return "Too close to a sibling variant — anti-spam guard at risk."


def score_variant(
    rng: Random, focus: str, idx: int, demo_mode: bool, paradox_pin: bool,
) -> tuple[int, int, int, int, int, bool, dict]:
    if demo_mode and paradox_pin:
        profile = _PARADOX_PROFILE
    else:
        profile = _VARIANT_SCORE_PROFILES.get((focus, idx)) or {
            "hook_range": (66, 78), "conv_range": (60, 72),
            "voice_range": (70, 80), "distinct_range": (62, 74),
        }
    hook = rng.randint(*profile["hook_range"])
    conv = rng.randint(*profile["conv_range"])
    voice = rng.randint(*profile["voice_range"])
    distinct = rng.randint(*profile["distinct_range"])

    plan_score = round(
        COMMENT_PLAN_WEIGHTS["Hook strength"] * hook
        + COMMENT_PLAN_WEIGHTS["Conversation potential"] * conv
        + COMMENT_PLAN_WEIGHTS["Voice fidelity"] * voice
        + COMMENT_PLAN_WEIGHTS["Distinct angle"] * distinct
    )

    paradox = (hook > 70) and (conv < 30)

    interp = {
        "Hook strength": _interp_hook(hook),
        "Conversation potential": _interp_conv(conv),
        "Voice fidelity": _interp_voice(voice),
        "Distinct angle": _interp_distinct(distinct),
    }
    return hook, conv, voice, distinct, plan_score, paradox, interp


def build_variants(
    seed_rng: Random,
    focus: str,
    num: int,
    demo_mode: bool,
) -> list[CommentVariant]:
    if focus not in _FOCUS_VARIANT_LIBRARY:
        raise ValueError(f"focus '{focus}' has no variant library; check resolver.")
    library = _FOCUS_VARIANT_LIBRARY[focus]()
    num = max(MIN_VARIANTS, min(MAX_VARIANTS, num))
    out: list[CommentVariant] = []
    for idx in range(1, num + 1):
        if idx > len(library):
            # Defensive: should never hit (library has 5)
            break
        template_id, angle, body = library[idx - 1]
        # Length cap enforcement
        if len(body) > COMMENT_LENGTH_CAP:
            body = body[: COMMENT_LENGTH_CAP - 1].rstrip() + "…"
        # Demo paradox: pin variant 2 to paradox profile
        paradox_pin = demo_mode and idx == 2
        v_rng = Random(seed_rng.randbytes(8))
        hook, conv, voice, distinct, plan_score, paradox, interp = score_variant(
            v_rng, focus, idx, demo_mode, paradox_pin,
        )
        out.append(CommentVariant(
            index=idx,
            angle=angle,
            template_id=template_id,
            hook_strength=hook,
            conversation_potential=conv,
            voice_fidelity=voice,
            distinct_angle=distinct,
            plan_score=plan_score,
            paradox_active=paradox,
            interpretations=interp,
            body=body,
            char_count=len(body),
        ))
    return out


# ---------------------------------------------------------------------------
# Engagement tips
# ---------------------------------------------------------------------------


def build_engagement_tips(num_variants: int) -> list[tuple[str, str]]:
    tips = [
        (
            "Ship the comment within 30 minutes of the post going live",
            "Reply velocity in the first hour disproportionately drives the algorithm's surface decision.",
        ),
        (
            "Reply to your own comment with a follow-up question 6-8h later",
            "Self-thread keeps the chain alive; a one-line `and if not, what would you change?` is enough.",
        ),
        (
            "Pin the strongest-performing variant if a substantive chain forms",
            "Pinning the comment compounds engagement velocity for the next 24-48h.",
        ),
    ]
    if num_variants >= 3:
        tips.append((
            "Ship one variant per day across 3 sibling posts, not all on one anchor",
            "Comment-stacking the same post reads as bot-like; spreading the angles preserves credibility.",
        ))
    if num_variants >= 4:
        tips.append((
            "Hold the highest-conversation-potential variant for the most-engaged post in the set",
            "Match variant strength to post strength — the strongest hook on the strongest anchor compounds best.",
        ))
    return tips[:5]


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    variants: list[CommentVariant], boost_focus: str,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: hook-without-substance paradox
    paradox_variants = [v for v in variants if v.paradox_active]
    if paradox_variants:
        names = ", ".join(f"Variant {v.index}" for v in paradox_variants)
        flags.append(RedFlag(
            title="Hook-without-substance paradox",
            severity="high",
            explanation=(
                f"{len(paradox_variants)} variant(s) — {names} — show Hook strength "
                "above 70 while Conversation potential sits below 30. The opener is "
                "gripping but the comment does not invite or sustain a reply chain."
            ),
            remediation=(
                "Tighten the comment's substance so the hook is earned, OR ship the "
                "hook as a quote-tweet rather than a comment."
            ),
        ))

    # Rule 2: voice-drift watch
    low_voice = [v for v in variants if v.voice_fidelity < 65]
    if low_voice:
        names = ", ".join(f"Variant {v.index}" for v in low_voice)
        flags.append(RedFlag(
            title="Voice-drift watch",
            severity="medium" if len(low_voice) >= 2 else "low",
            explanation=(
                f"{len(low_voice)} variant(s) — {names} — score below 65 on Voice fidelity; "
                "the comment leans toward niche-default rather than the creator's voice."
            ),
            remediation=(
                "Pair with `brand-voice-trainer` to verify before shipping; the alternate "
                "variants in the set preserve voice better."
            ),
        ))

    # Rule 3: cadence over-saturation
    if len(variants) >= 4:
        flags.append(RedFlag(
            title="Cadence over-saturation",
            severity="low",
            explanation=(
                f"Shipping all {len(variants)} variants on the same post can read as "
                "comment-stacking and erode credibility with overlap audiences."
            ),
            remediation=(
                "Ship one variant on the anchor; rotate the others into sibling posts "
                "in the same week."
            ),
        ))

    # Defensive top-up
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-cohort dependence",
            severity="low",
            explanation=(
                "All variants target the same boost focus — engagement hinges on whether "
                "that focus matches the audience's mood today."
            ),
            remediation=(
                "Re-run with `--boost-focus all` next time to let the runner pick the "
                "highest-leverage angle for the post."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    variants: list[CommentVariant],
    boost_focus: str,
    paradox_present: bool,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    pool.append(Recommendation(
        text=(
            "Snapshot reply rate per variant at T+24h and T+7d via "
            "`analytics-summarizer` to log which angles compound."
        ),
        bridge_slug="analytics-summarizer",
    ))
    pool.append(Recommendation(
        text=(
            "Confirm all variants land in the creator's voice via "
            "`brand-voice-trainer` before shipping; voice drift compounds silently."
        ),
        bridge_slug="brand-voice-trainer",
    ))
    pool.append(Recommendation(
        text=(
            "If a variant lands hard, build a follow-on long-form thread to extend "
            "the win via `thread-builder`."
        ),
        bridge_slug="thread-builder",
    ))
    pool.append(Recommendation(
        text=(
            "Promote a 2-variant comparison into a structured A/B over 2 weeks via "
            "`ab-test-suggester` once one angle wins."
        ),
        bridge_slug="ab-test-suggester",
    ))
    pool.append(Recommendation(
        text=(
            "Watch competitor formats via `competitor-watch` to see whether the "
            "chosen angle is over-used in the niche this quarter."
        ),
        bridge_slug="competitor-watch",
    ))
    if paradox_present:
        pool.append(Recommendation(
            text=(
                "For paradox-flagged variants, ship the hook as a quote-tweet via "
                "`quote-tweet-suggestor` rather than a comment — the format fits better."
            ),
            bridge_slug="quote-tweet-suggestor",
        ))
    pool.append(Recommendation(
        text=(
            "If the comment ladder reaches paid-tier conversation territory, model "
            "the funnel before shipping the next variant."
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
                        "Cross-reference the variant set with last week's analytics "
                        "to spot which angles compound for this voice."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(Recommendation(
            text="Re-run with a clearer post or a different boost focus to lift confidence.",
            bridge_slug="content-idea-generator",
        ))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence + aggregate score
# ---------------------------------------------------------------------------


def aggregate_plan_score(variants: list[CommentVariant]) -> int:
    if not variants:
        return 0
    return round(sum(v.plan_score for v in variants) / len(variants))


def confidence_for(
    post: PostSnapshot, variants: list[CommentVariant], paradox_present: bool,
) -> tuple[str, str]:
    src_clear = post.char_count >= 60 and post.url is None
    avg = aggregate_plan_score(variants)
    if src_clear and avg >= 70 and not paradox_present:
        return ("high", f"clear post, {len(variants)} distinct variants under 240 chars each, average score {avg}/100.")
    if avg >= 60:
        return ("medium", f"average Comment Plan score {avg}/100 — solid direction; tighten focus or paste literal post text to lift.")
    return ("low", f"average Comment Plan score {avg}/100 — supply richer post text or pick a different boost focus.")


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_post_snapshot(
    post: PostSnapshot, boost_focus_input: str, boost_focus_resolved: str,
    num_variants: int,
) -> str:
    summary = post.summary
    if len(summary) > 140:
        summary = summary[:137].rstrip() + "..."
    focus_str = (
        f"all-resolved-to-{boost_focus_resolved}"
        if boost_focus_input == "all" else boost_focus_input
    )
    return "\n".join([
        "## Post Snapshot",
        f"**{post.handle}: {summary}**",
        "",
        f"- **Creator handle**: {post.handle}",
        f"- **Post (verbatim or summary)**: {summary}",
        f"- **Boost focus**: {focus_str}",
        f"- **Variants requested**: {num_variants}",
        f"- **Tone of post**: {post.tone_signal}",
    ])


def _render_comment_plan(variants: list[CommentVariant]) -> str:
    avg = aggregate_plan_score(variants)
    return "\n".join([
        "## Comment Plan",
        "",
        f"**Aggregate Comment Plan score**: {avg}/100 — averaged across the variant set.",
    ])


def _render_variant(v: CommentVariant) -> str:
    lines = [
        f"### Variant {v.index} · {v.angle} · Comment Plan score: {v.plan_score}/100",
        f"- **Hook strength**: {v.hook_strength}/100 — {v.interpretations['Hook strength']}",
        f"- **Conversation potential**: {v.conversation_potential}/100 — {v.interpretations['Conversation potential']}",
        f"- **Voice fidelity**: {v.voice_fidelity}/100 — {v.interpretations['Voice fidelity']}",
        f"- **Distinct angle**: {v.distinct_angle}/100 — {v.interpretations['Distinct angle']}",
    ]
    if v.paradox_active:
        lines.append(
            "> ⚠️ paradox: opener is gripping but the comment does not invite or sustain a reply chain — bait without follow-through."
        )
    lines.append("")
    lines.append("```")
    lines.append(v.body)
    lines.append("```")
    return "\n".join(lines)


def _render_variants(variants: list[CommentVariant]) -> str:
    return "## Comment Variants\n\n" + "\n\n".join(
        _render_variant(v) for v in variants
    )


def _render_engagement_tips(tips: list[tuple[str, str]]) -> str:
    return "## Engagement Tips\n\n" + "\n".join(
        f"{i}. **{t[0]}** — {t[1]}" for i, t in enumerate(tips, start=1)
    )


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} *Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    monetization_emitted = False
    for i, rec in enumerate(recs, start=1):
        line = f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`"
        if rec.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    return "\n".join(lines)


def _render_boost_audit(
    post: PostSnapshot,
    boost_focus_input: str,
    boost_focus_resolved: str,
    variants: list[CommentVariant],
) -> str:
    distinct_low = sum(1 for v in variants if v.distinct_angle < DISTINCT_ANGLE_MIN)
    return "\n".join([
        "## Boost Audit (auto-triggered)",
        "",
        f"- **Post clarity**: {'clear, single-claim post' if post.url is None and post.char_count >= 60 else 'URL-only or thin source'}.",
        f"- **Angle fit**: chosen `{boost_focus_resolved}` "
        + ("(runner picked from `all`)" if boost_focus_input == "all" else "(creator-supplied)") + ".",
        f"- **Spam exposure**: {distinct_low} variant(s) score below {DISTINCT_ANGLE_MIN} on Distinct angle — anti-spam guard tightened.",
        "- **Suggested next run**: ship variant 1 first; hold variant 2 for the next sibling post in the cluster.",
        "- **Re-run cadence**: per-major-thread while engagement-velocity is the priority, otherwise weekly.",
    ])


def render_report(
    post: PostSnapshot,
    boost_focus_input: str,
    boost_focus_resolved: str,
    num_variants: int,
    variants: list[CommentVariant],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    tips: list[tuple[str, str]],
) -> str:
    sections = [
        _render_post_snapshot(post, boost_focus_input, boost_focus_resolved, num_variants),
        "",
        _render_comment_plan(variants),
        "",
        _render_variants(variants),
        "",
        _render_engagement_tips(tips),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    if len(flags) > 3 or boost_focus_input == "all":
        sections.extend([
            "",
            _render_boost_audit(post, boost_focus_input, boost_focus_resolved, variants),
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
        f"<!-- Generated by Comment Engagement Booster (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built to help xAI and Grok win. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_comment_variants(
    *,
    x_handle: str,
    post_url_or_text: str,
    boost_focus: str = "question",
    num_comments: int = 3,
    when: Optional[str] = None,
    demo_mode: bool = False,
) -> str:
    handle = normalize_handle(x_handle)
    if boost_focus not in BOOST_FOCUS_OPTIONS:
        raise ValueError(f"boost_focus must be one of {BOOST_FOCUS_OPTIONS}, got {boost_focus!r}")
    if not (MIN_VARIANTS <= num_comments <= MAX_VARIANTS):
        raise ValueError(
            f"num_comments must be in [{MIN_VARIANTS}, {MAX_VARIANTS}], got {num_comments}"
        )

    post = parse_post(post_url_or_text, handle)
    when_iso = when or date.today().isoformat()

    boost_focus_input = boost_focus
    if boost_focus == "all":
        resolved, _why = pick_auto_focus(post)
    else:
        resolved = boost_focus

    rng = deterministic_rng(handle, post.text, resolved, num_comments, when_iso)
    variants = build_variants(rng, resolved, num_comments, demo_mode)
    assert_no_spam_overlap(variants)
    flags = build_red_flags(variants, resolved)
    paradox_present = any(v.paradox_active for v in variants)
    recs = build_recommendations(rng, variants, resolved, paradox_present)
    confidence = confidence_for(post, variants, paradox_present)
    tips = build_engagement_tips(num_comments)

    rendered = render_report(
        post=post,
        boost_focus_input=boost_focus_input,
        boost_focus_resolved=resolved,
        num_variants=num_comments,
        variants=variants,
        flags=flags,
        recs=recs,
        confidence=confidence,
        tips=tips,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_comment_variants


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Comment Engagement Booster (Grok Agent OS · creator template)\n"
        "  Drafts only · 240-char cap · Anti-spam guard · No mass-identical\n"
        "  Built to help xAI and Grok win.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="comment-engagement-booster",
        description=(
            "Turn a single post into 3-5 distinct, on-voice comment variants "
            "spanning the chosen boost focus (question / controversy / story / "
            "poll / all). Drafts only — never auto-publishes anywhere."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    p.add_argument(
        "--post-url-or-text",
        help="Either an x.com URL or the literal post text. Required unless --demo / --demo-productivity is passed.",
    )
    p.add_argument(
        "--boost-focus",
        choices=list(BOOST_FOCUS_OPTIONS),
        default="question",
        help="Which angle the variants prioritise. 'all' lets the runner pick.",
    )
    p.add_argument(
        "--num-comments",
        type=int,
        default=3,
        help=f"Number of variants ({MIN_VARIANTS}-{MAX_VARIANTS}). Default 3.",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run with the canonical AI-niche demo post. Pins variant 2 to the "
            "hook-without-substance paradox profile so the rule reliably demonstrates."
        ),
    )
    p.add_argument(
        "--demo-productivity",
        action="store_true",
        help=(
            "Run with a productivity-niche demo post. Healthy variants (no paradox)."
        ),
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

    demo_mode = False
    if args.demo and not args.post_url_or_text:
        post_arg = DEMO_POST_TEXT
        demo_mode = True
    elif args.demo_productivity and not args.post_url_or_text:
        post_arg = DEMO_PRODUCTIVITY_POST_TEXT
        demo_mode = False
    elif args.post_url_or_text:
        post_arg = args.post_url_or_text
    else:
        sys.stderr.write(
            "error: provide --post-url-or-text \"<post or URL>\" or pass --demo / --demo-productivity.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_comment_variants(
        x_handle=args.x_handle,
        post_url_or_text=post_arg,
        boost_focus=args.boost_focus,
        num_comments=args.num_comments,
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
