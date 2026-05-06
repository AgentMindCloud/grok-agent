# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Content Recycler — runner.

CLI entry point for the ``content-recycler`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads an old X post the creator authored (URL or pasted text) plus a
chosen recycle angle and target format, and emits a 6/7-section
structured set of variants matching ``prompts/system.md`` exactly:

  1. Source Snapshot
  2. Recycle Angle Analysis (chosen / why-fits / what-changes / what-stays)
  3. Recycled Variants (2-3 per single format, or 4 — one per format —
     when target_format='all'; each card has the 4-row Recycle Score table
     + weighted Recycle score = round(0.30*Freshness + 0.25*Format +
     0.25*Engagement + 0.20*Differentiation) + the variant body in a
     code-fence + the verbatim attribution stamp)
  4. Engagement Prediction (lift vs static repost / best+worst case)
  5. Red Flags (2-3, surfaces the stale-rehash paradox in BOTH the
     variant card AND this section when triggered)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Recycle Audit (auto-appended when red_flags > 3 OR target_format='all')

Hard guarantees enforced by this runner (mirrors the Constitution):

* Drafts only. The runner never publishes a variant.
* Recycle only the creator's own content. When the source is supplied as
  an x.com URL whose handle does not match `--x-handle`, the runner
  REFUSES the run and emits a 3-section guidance card. Recycling another
  account's content is impersonation by another name.
* Attribution stamp preserved on every variant:
    `— originally posted on X by @<handle> on <date> · recycled <today>`
  The renderer never strips it; the creator may strip it manually before
  posting. The stamp lives in a single grep-able function (`_recycle_stamp`).
* Stale-rehash paradox surfaced in BOTH the variant card AND the Red
  Flags section whenever a variant has Format fit > 70 AND Freshness
  lift < 35.
* Recycle score formula is fixed:
    round(0.30*Freshness lift + 0.25*Format fit +
          0.25*Engagement potential + 0.20*Differentiation).
  Freshness weighted highest because a variant that adds no new value
  is just a repost.
* No fabricated freshness. When `recycle_angle = update` the runner
  inserts an explicit `[insert refreshed metric here]` placeholder
  rather than inventing numbers.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + source_text +
  angle + target_format + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_recycled_variants

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
    "Freshness lift",
    "Format fit",
    "Engagement potential",
    "Differentiation",
)

# Recycle score weights — Freshness weighted highest because a variant
# that adds no new value is just a repost.
RECYCLE_SCORE_WEIGHTS = {
    "Freshness lift": 0.30,
    "Format fit": 0.25,
    "Engagement potential": 0.25,
    "Differentiation": 0.20,
}

ANGLE_OPTIONS = ("update", "expand", "threadify", "repurpose", "auto")
FORMAT_OPTIONS = ("tweet", "thread", "carousel", "newsletter", "all")
SINGLE_FORMATS = ("tweet", "thread", "carousel", "newsletter")

# Variant counts when a single target_format is requested. When
# target_format='all', the runner emits 4 variants — one per format.
VARIANT_COUNT_BY_FORMAT = {
    "tweet": 3,
    "thread": 3,
    "carousel": 2,
    "newsletter": 2,
}

# Approximate length budgets for sanity-checking output.
LENGTH_BUDGETS = {
    "tweet": (240, 280),       # chars
    "thread": (1400, 2800),    # total chars across thread
    "carousel": (8, 10),       # slide count
    "newsletter": (600, 1500), # words (approx)
}

DEMO_HANDLE = "@JanSol0s"
DEMO_SOURCE_TEXT = (
    "Most agent eval suites measure the wrong thing — "
    "they reward verbosity, not action correctness."
)
DEMO_ORIGINAL_DATE = "2025-09-12"

CROSS_TEMPLATE_BRIDGES = (
    "thread-builder",
    "cross-platform-reposter",
    "quote-tweet-suggestor",
    "analytics-summarizer",
    "content-calendar-builder",
    "content-idea-generator",
    "brand-voice-trainer",
    "monetization-optimizer",
    "ab-test-suggester",
    "competitor-watch",
    "mention-summarizer",
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
class SourceSnapshot:
    handle: str
    text: str
    url: Optional[str]
    char_count: int
    source_format: str
    dominant_claim: str
    tone_signal: str
    original_date: str  # ISO date string or "(date unknown)"


@dataclass
class Variant:
    target_format: str
    index: int  # 1-based
    angle_used: str
    template_id: str
    freshness_lift: int
    format_fit: int
    engagement_potential: int
    differentiation: int
    recycle_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)
    body: str = ""
    visual_suggestion: Optional[str] = None
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


@dataclass
class AngleAnalysis:
    chosen: str
    why_fits: str
    what_changes: str
    what_stays: str


# ---------------------------------------------------------------------------
# Privacy / handle guards
# ---------------------------------------------------------------------------


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Content Recycler privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def parse_target_format(raw: Optional[str]) -> str:
    if not raw:
        return "thread"
    f = raw.strip().lower()
    if f not in FORMAT_OPTIONS:
        raise ValueError(f"target_format must be one of {FORMAT_OPTIONS}, got {raw!r}")
    return f


def parse_recycle_angle(raw: Optional[str]) -> str:
    if not raw:
        return "auto"
    a = raw.strip().lower()
    if a not in ANGLE_OPTIONS:
        raise ValueError(f"recycle_angle must be one of {ANGLE_OPTIONS}, got {raw!r}")
    return a


def parse_source(
    post_url_or_text: str,
    fallback_handle: str,
    original_date: Optional[str],
) -> tuple[SourceSnapshot, Optional[str]]:
    """Returns (SourceSnapshot, mismatch_handle_or_None).
    When the source is a URL whose handle does NOT match fallback_handle,
    mismatch_handle_or_None is set to the URL's handle so the caller can
    refuse the run with a clear guidance card.
    """
    raw = (post_url_or_text or "").strip()
    if not raw:
        raise ValueError(
            "old_post_url_or_text is empty. Pass either an x.com URL or the literal post text."
        )

    date_str = original_date.strip() if original_date else "(date unknown)"

    m = _URL_RE.match(raw)
    if m:
        url_handle = "@" + m.group(1)
        mismatch = None
        if url_handle.lower() != fallback_handle.lower():
            mismatch = url_handle
        return (
            SourceSnapshot(
                handle=fallback_handle,
                text=(
                    "[source URL supplied; runner is offline so the body is referenced "
                    "by URL only — paste the original text for richer recycled variants]"
                ),
                url=raw,
                char_count=0,
                source_format="single-post",
                dominant_claim="(see source URL — runner cannot fetch in v1)",
                tone_signal="thoughtful",
                original_date=date_str,
            ),
            mismatch,
        )

    text = raw
    return (
        SourceSnapshot(
            handle=fallback_handle,
            text=text,
            url=None,
            char_count=len(text),
            source_format=_infer_source_format(text),
            dominant_claim=_extract_dominant_claim(text),
            tone_signal=_infer_tone(text),
            original_date=date_str,
        ),
        None,
    )


def _infer_source_format(text: str) -> str:
    if text.count("\n\n") >= 2 or len(text) > 700:
        return "thread"
    if text.startswith(">") or text.startswith("RT @"):
        return "quote-tweet"
    if text.startswith("@"):
        return "reply"
    return "single-post"


def _extract_dominant_claim(text: str) -> str:
    candidate = re.split(r"(?<=[.!?])\s+|\s+—\s+", text.strip(), maxsplit=1)[0].strip()
    if len(candidate) > 160:
        candidate = candidate[:157].rstrip() + "..."
    return candidate or text.strip()[:160]


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
# Angle picker (auto)
# ---------------------------------------------------------------------------


def pick_auto_angle(source: SourceSnapshot) -> tuple[str, str]:
    """Returns (chosen_angle, why_fits)."""
    has_numbers = bool(re.search(r"\d", source.text))
    is_short = source.char_count > 0 and source.char_count < 200
    is_long = source.char_count >= 700
    is_dated = source.original_date != "(date unknown)" and source.original_date < (
        "2025-12-01"
    )

    if has_numbers and is_dated:
        return (
            "update",
            "Source contains numbers/data and is older than ~6 months — refreshing "
            "the data is the highest-leverage angle.",
        )
    if is_short and source.char_count > 0:
        return (
            "expand",
            "Source is a punchy short post that left readers wanting more — adding "
            "depth + examples is the cleanest angle.",
        )
    if is_long:
        return (
            "repurpose",
            "Source is long-form and would compound by shifting format (long-form "
            "thread → tweet + carousel) rather than copying length.",
        )
    return (
        "expand",
        "Source is mid-length and direct — expanding into a structured follow-on is "
        "the most reliable default angle.",
    )


def angle_what_changes(angle: str, target_format: str) -> str:
    if angle == "update":
        return (
            "Numbers, references, and any time-sensitive claims are refreshed; tone and "
            "voice stay anchored to the original."
        )
    if angle == "expand":
        return (
            "Single-line claim becomes a structured follow-on with concrete examples "
            "and one closing call to action."
        )
    if angle == "threadify":
        return (
            "Single post is decomposed into a hook / develop / payoff thread that "
            "preserves the dominant claim across the structure."
        )
    if angle == "repurpose":
        return (
            f"Original format is converted to {target_format}; substance preserved, "
            "structure rebuilt for the target format."
        )
    return "Runner-picked angle — see the why-fits line."


def angle_what_stays(source: SourceSnapshot) -> str:
    return f"The dominant claim — {source.dominant_claim} — anchors every variant."


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str,
    source_text: str,
    angle: str,
    target_format: str,
    when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(source_text.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(angle.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(target_format.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


def _per_variant_rng(seed_rng: Random, fmt: str, idx: int) -> Random:
    digest = hashlib.sha256()
    digest.update(fmt.encode("utf-8"))
    digest.update(str(idx).encode("utf-8"))
    digest.update(seed_rng.randbytes(8))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Variant text scaffolds (offline, source-agnostic)
# ---------------------------------------------------------------------------


def _recycle_stamp(handle: str, original_date: str, today: str) -> str:
    """The verbatim attribution stamp required by Constitution rule 3.
    Single grep-able function so the invariant has one chokepoint."""
    return f"— originally posted on X by {handle} on {original_date} · recycled {today}"


def _gen_tweet_variant(
    idx: int, source: SourceSnapshot, angle: str,
) -> tuple[str, str, Optional[str]]:
    """idx 1: high-quality recycle. idx 2: stale-rehash paradox profile.
    idx 3: alternative angle. Returns (template_id, body_no_stamp, visual)."""
    if idx == 1:
        if angle == "update":
            template_id = "tw-update-v1"
            body = (
                f"{source.text}\n\n"
                "Refreshed take: [insert refreshed metric here] — same claim, new evidence."
            )
        else:
            template_id = "tw-condense-v1"
            body = (
                f"{source.text}\n\n"
                "still the punch line."
            )
        visual = "Mobile-first photo: simple chart contrasting old vs refreshed signal."
    elif idx == 2:
        # Stale-rehash paradox profile: word-for-word repackaging
        template_id = "tw-stale-rehash-v2"
        body = f"Reminder: {source.text}"
        visual = "Generic stock photo with text overlay — adds zero visual signal."
    else:  # idx == 3
        template_id = "tw-counter-frame-v3"
        body = (
            "the popular advice tells you to optimise the metric. here's a less popular take:\n\n"
            f"{source.text}"
        )
        visual = None
    return template_id, body, visual


def _gen_thread_variant(
    idx: int, source: SourceSnapshot, angle: str,
) -> tuple[str, str, Optional[str]]:
    if idx == 1:
        template_id = "th-expand-v1"
        body = (
            f"[1/7] {('Last year' if source.original_date != '(date unknown)' else 'Earlier')}"
            f" I posted: {source.text}\n\n"
            "Today: three concrete failure modes that prove the point.\n\n"
            "[2/7] Failure mode 1 — the dashboard climbs while the real outcome slides.\n"
            "Teams ship a change that lifts every surface metric. A few weeks later, the "
            "thing they actually cared about has gotten worse.\n\n"
            "[3/7] Failure mode 2 — the work gets noisier as it gets better-graded.\n"
            "Each iteration scores higher on the proxy and adds more surface area without "
            "improving outcomes.\n\n"
            "[4/7] Failure mode 3 — the terse correct version is discounted.\n"
            "A candidate ships short, correct work. The grader marks it down for not "
            "'showing reasoning'. The team passes.\n\n"
            "[5/7] Remediation 1 — grade the outcome in a sandbox.\n"
            "If you can't run the action, you don't have a metric.\n\n"
            "[6/7] Remediation 2 — outcome-graded > surface-graded, every time.\n"
            "Treat the dashboard regression as a cost of moving to the right metric.\n\n"
            "[7/7] If your eval suite can't run the action, it isn't the metric you "
            "think it is. The dashboards will look worse for a quarter; the work will "
            "be better forever."
        )
        visual = "Inline image on post 2: chart with proxy metric rising and outcome metric flat."
    elif idx == 2:
        # Stale-rehash paradox profile: thread-shaped wrapper around the same content
        template_id = "th-stale-rehash-v2"
        body = (
            f"[1/3] Repost worth pinning: {source.text}\n\n"
            f"[2/3] Same claim, same framing — still true.\n\n"
            f"[3/3] If you missed it last time, here it is again."
        )
        visual = None
    else:  # idx == 3
        template_id = "th-counter-take-v3"
        body = (
            f"[1/5] Most folks tell you to optimise the metric. Here's a less popular take:\n\n"
            f"{source.text}\n\n"
            "[2/5] The metric is the proxy. The outcome is the thing. Confusing the two "
            "is how teams burn six months in the wrong direction.\n\n"
            "[3/5] What goes wrong: the proxy gets gamed. Surface improves, substance "
            "drifts. By the time you notice, you've shipped optimisations nobody wanted.\n\n"
            "[4/5] What works: outcome graders. Run the action. Score the result. Drop "
            "the proxy that made you grade the surface in the first place.\n\n"
            "[5/5] Boring. Durable. The only kind of metric work that compounds."
        )
        visual = None
    return template_id, body, visual


def _gen_carousel_variant(
    idx: int, source: SourceSnapshot, angle: str,
) -> tuple[str, str, Optional[str]]:
    if idx == 1:
        template_id = "ca-slides-v1"
        body = (
            "Slide 1 (cover) — Title: \"Most {niche} measurement is grading the surface, "
            "not the outcome\" · subtitle: the recycle of an X claim into structure.\n"
            "Slide 2 — \"The original claim\": " + source.text + "\n"
            "Slide 3 — \"Failure mode 1\": dashboard climbs, real outcome slides.\n"
            "Slide 4 — \"Failure mode 2\": surface gets richer; substance drifts.\n"
            "Slide 5 — \"Failure mode 3\": the terse correct version gets discounted.\n"
            "Slide 6 — \"Remediation 1\": grade the outcome in a sandbox.\n"
            "Slide 7 — \"Remediation 2\": outcome > surface, every time.\n"
            "Slide 8 — \"If you can't run the action, you don't have a metric.\"\n"
            "Slide 9 (closer) — Call: pin the original X post + follow for the full thread."
        )
        visual = (
            "Slide-by-slide image prompts: cover = bold typography on dark background; "
            "slides 2-7 = single illustration per slide (chart / diagram / icon); slide 8 "
            "= big-text quote card; slide 9 = X-handle + post-link visual."
        )
    else:  # idx == 2 — stale-rehash paradox profile (perfect format, zero new value)
        template_id = "ca-stale-rehash-v2"
        body = (
            "Slide 1 (cover) — Title: " + source.text + "\n"
            "Slide 2 — Same claim, different background.\n"
            "Slide 3 — Same claim, different colour scheme.\n"
            "Slide 4 — Same claim, different font.\n"
            "Slide 5 — Same claim, with quote marks.\n"
            "Slide 6 — Same claim, in italics.\n"
            "Slide 7 — Same claim, centered.\n"
            "Slide 8 (closer) — Same claim, with a CTA arrow."
        )
        visual = (
            "8 slides of the same claim restyled — the visual equivalent of stale-rehash. "
            "Looks like a carousel; reads like a copy-paste."
        )
    return template_id, body, visual


def _gen_newsletter_variant(
    idx: int, source: SourceSnapshot, angle: str,
) -> tuple[str, str, Optional[str]]:
    if idx == 1:
        template_id = "nl-extended-v1"
        body = (
            f"### Recycling an old X claim into a longer read\n\n"
            f"> {source.text}\n\n"
            f"This claim landed punchy on X back on {source.original_date}. The post got "
            f"engagement; what it didn't get was the structure that would make it durable. "
            f"This section recycles the claim into the long-form treatment it always "
            f"wanted.\n\n"
            "The pattern shows up in three concrete shapes. First, the dashboard "
            "climbs while the outcome slides. Second, the surface gets noisier as the "
            "score climbs. Third, the terse correct version gets marked down for not "
            "performing thoroughness.\n\n"
            "The remediation in all three cases is the same. Move the metric from the "
            "surface to the outcome. If you cannot grade the result, do not let the easy "
            "proxy be the thing you optimise. Replace it with an outcome grader that "
            "runs the work and checks the result. The dashboards will look worse for a "
            "quarter; the work will be better forever.\n\n"
            "*Reply to this email if you've seen the same pattern in your stack — happy "
            "to compare notes.*"
        )
        visual = (
            "Header image: chart contrasting proxy score (rising) vs real outcome (flat). "
            "Inline diagram: outcome-grading flow vs surface-grading flow."
        )
    else:  # idx == 2 — stale-rehash paradox
        template_id = "nl-stale-rehash-v2"
        body = (
            f"### Pinned this on X — pinning it here too\n\n"
            f"> {source.text}\n\n"
            "I've said this before. I'll say it again. The claim hasn't changed because "
            "the situation hasn't changed.\n\n"
            "If you read this on X already, this is the same content in a longer container. "
            "If you didn't, here it is in newsletter form. Either way, the dominant claim "
            "stays put."
        )
        visual = "Header image: re-used hero from the original X post (same imagery)."
    return template_id, body, visual


_VARIANT_GENERATORS = {
    "tweet": _gen_tweet_variant,
    "thread": _gen_thread_variant,
    "carousel": _gen_carousel_variant,
    "newsletter": _gen_newsletter_variant,
}


# ---------------------------------------------------------------------------
# Per-variant scoring
# ---------------------------------------------------------------------------

# Score profiles — variant 2 of each format is the stale-rehash paradox
# profile (low Freshness, high Format fit) so the rule reliably surfaces.
_VARIANT_SCORE_PROFILES = {
    ("tweet", 1): {
        "freshness_lift_range": (52, 68),
        "format_fit_range": (74, 84),
        "engagement_potential_range": (44, 58),
        "differentiation_range": (58, 72),
    },
    ("tweet", 2): {  # PARADOX
        "freshness_lift_range": (18, 30),
        "format_fit_range": (74, 84),
        "engagement_potential_range": (40, 54),
        "differentiation_range": (28, 42),
    },
    ("tweet", 3): {
        "freshness_lift_range": (50, 62),
        "format_fit_range": (70, 80),
        "engagement_potential_range": (42, 56),
        "differentiation_range": (62, 76),
    },
    ("thread", 1): {
        "freshness_lift_range": (66, 80),
        "format_fit_range": (76, 88),
        "engagement_potential_range": (58, 72),
        "differentiation_range": (68, 82),
    },
    ("thread", 2): {  # PARADOX
        "freshness_lift_range": (20, 32),
        "format_fit_range": (74, 84),
        "engagement_potential_range": (40, 54),
        "differentiation_range": (24, 38),
    },
    ("thread", 3): {
        "freshness_lift_range": (60, 74),
        "format_fit_range": (74, 84),
        "engagement_potential_range": (54, 68),
        "differentiation_range": (66, 78),
    },
    ("carousel", 1): {
        "freshness_lift_range": (62, 76),
        "format_fit_range": (78, 88),
        "engagement_potential_range": (58, 70),
        "differentiation_range": (66, 80),
    },
    ("carousel", 2): {  # PARADOX
        "freshness_lift_range": (15, 28),
        "format_fit_range": (76, 86),
        "engagement_potential_range": (38, 52),
        "differentiation_range": (20, 34),
    },
    ("newsletter", 1): {
        "freshness_lift_range": (66, 80),
        "format_fit_range": (78, 88),
        "engagement_potential_range": (52, 66),
        "differentiation_range": (68, 82),
    },
    ("newsletter", 2): {  # PARADOX
        "freshness_lift_range": (18, 30),
        "format_fit_range": (76, 86),
        "engagement_potential_range": (40, 54),
        "differentiation_range": (24, 38),
    },
}


def _interp_freshness(score: int) -> str:
    if score >= 60:
        return "Variant adds new framing, examples, or context absent in the original."
    if score >= 40:
        return "Variant adds light freshness; the dominant claim still carries the post."
    return "Variant adds little new value — close to a re-publish of the original."


def _interp_format_fit(score: int, fmt: str) -> str:
    if score >= 75:
        return f"Length, structure, and {fmt} conventions all match cleanly."
    if score >= 55:
        return f"Solid {fmt} shape with one or two off-cadence beats."
    return f"Variant under-tuned for {fmt} — structure or length off-pattern."


def _interp_engagement(score: int) -> str:
    if score >= 60:
        return "Predicted lift well above a static repost."
    if score >= 45:
        return "Healthy lift over a static repost."
    return "Modest lift; competing variants will outperform."


def _interp_differentiation(score: int) -> str:
    if score >= 65:
        return "Reads as a deeper take, not a copy-paste with new wrapping."
    if score >= 45:
        return "Recognisably distinct, but the original framing dominates."
    return "Too close to the original — risks cannibalizing the still-circulating source."


def score_variant(
    rng: Random, fmt: str, idx: int, angle: str,
) -> tuple[int, int, int, int, int, bool, dict]:
    profile = _VARIANT_SCORE_PROFILES.get((fmt, idx)) or {
        "freshness_lift_range": (50, 70),
        "format_fit_range": (60, 78),
        "engagement_potential_range": (45, 60),
        "differentiation_range": (55, 70),
    }
    freshness = rng.randint(*profile["freshness_lift_range"])
    fmt_fit = rng.randint(*profile["format_fit_range"])
    eng = rng.randint(*profile["engagement_potential_range"])
    diff = rng.randint(*profile["differentiation_range"])

    # Angle nudges
    if angle == "update":
        freshness = min(100, freshness + 4)
    elif angle == "expand":
        freshness = min(100, freshness + 2)
        diff = min(100, diff + 2)
    elif angle == "threadify" and fmt == "thread":
        fmt_fit = min(100, fmt_fit + 3)
    elif angle == "repurpose":
        diff = min(100, diff + 4)

    score = round(
        RECYCLE_SCORE_WEIGHTS["Freshness lift"] * freshness
        + RECYCLE_SCORE_WEIGHTS["Format fit"] * fmt_fit
        + RECYCLE_SCORE_WEIGHTS["Engagement potential"] * eng
        + RECYCLE_SCORE_WEIGHTS["Differentiation"] * diff
    )

    paradox = (fmt_fit > 70) and (freshness < 35)

    interp = {
        "Freshness lift": _interp_freshness(freshness),
        "Format fit": _interp_format_fit(fmt_fit, fmt),
        "Engagement potential": _interp_engagement(eng),
        "Differentiation": _interp_differentiation(diff),
    }
    return freshness, fmt_fit, eng, diff, score, paradox, interp


def build_variants(
    seed_rng: Random,
    source: SourceSnapshot,
    target_format: str,
    angle: str,
) -> list[Variant]:
    out: list[Variant] = []
    if target_format == "all":
        # 1 variant per format
        for fmt in SINGLE_FORMATS:
            v_rng = _per_variant_rng(seed_rng, fmt, 1)
            template_id, body, visual = _VARIANT_GENERATORS[fmt](1, source, angle)
            f, ff, e, d, s, p, interp = score_variant(v_rng, fmt, 1, angle)
            out.append(Variant(
                target_format=fmt, index=1, angle_used=angle, template_id=template_id,
                freshness_lift=f, format_fit=ff, engagement_potential=e,
                differentiation=d, recycle_score=s, paradox_active=p,
                interpretations=interp, body=body, visual_suggestion=visual,
                char_count=len(body),
            ))
    else:
        count = VARIANT_COUNT_BY_FORMAT.get(target_format, 2)
        for idx in range(1, count + 1):
            v_rng = _per_variant_rng(seed_rng, target_format, idx)
            template_id, body, visual = _VARIANT_GENERATORS[target_format](
                idx, source, angle,
            )
            f, ff, e, d, s, p, interp = score_variant(v_rng, target_format, idx, angle)
            out.append(Variant(
                target_format=target_format, index=idx, angle_used=angle,
                template_id=template_id, freshness_lift=f, format_fit=ff,
                engagement_potential=e, differentiation=d, recycle_score=s,
                paradox_active=p, interpretations=interp, body=body,
                visual_suggestion=visual, char_count=len(body),
            ))
    return out


# ---------------------------------------------------------------------------
# Engagement prediction
# ---------------------------------------------------------------------------


def build_engagement_prediction(
    variants: list[Variant], target_format: str, angle: str,
) -> dict[str, str]:
    if not variants:
        return {
            "lift": "n/a — no variants generated",
            "best_case": "n/a",
            "worst_case": "n/a",
        }
    best = max(variants, key=lambda v: v.recycle_score)
    worst = min(variants, key=lambda v: v.recycle_score)
    fmt_word = "thread" if target_format == "thread" else target_format if target_format != "all" else "format"
    return {
        "lift": (
            f"{1.4 + 0.05*best.recycle_score:.1f}x typical-{fmt_word} engagement on the strongest "
            f"variant ({best.target_format} variant {best.index}, score {best.recycle_score}/100); "
            f"weakest variant scores {worst.recycle_score}/100 and risks underperforming a static repost."
        ),
        "best_case": (
            f"Recycled variant ships on a window where the niche is hungry for the "
            f"refreshed angle ({angle}) and the original's audience is still active."
        ),
        "worst_case": (
            "Recycle window collides with a competing major release in the niche — "
            "the original got buried then, and the recycled variant might too."
        ),
    }


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    variants: list[Variant], target_format: str, source: SourceSnapshot, angle: str,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    paradox = [v for v in variants if v.paradox_active]
    if paradox:
        names = ", ".join(
            f"{v.target_format.capitalize()} variant {v.index}" for v in paradox
        )
        flags.append(RedFlag(
            title="Stale-rehash paradox",
            severity="high",
            explanation=(
                f"{len(paradox)} variant(s) — {names} — show Format fit above 70 while "
                "Freshness lift sits below 35. That is a re-publish, not a recycle."
            ),
            remediation=(
                "Either choose a different recycle_angle (typically `update` or `expand`) "
                "or simply re-pin the original X post for visibility."
            ),
        ))

    # Cannibalization risk — when differentiation is low across multiple variants
    low_diff = [v for v in variants if v.differentiation < 45]
    if len(low_diff) >= 2:
        flags.append(RedFlag(
            title="Cannibalization risk",
            severity="medium",
            explanation=(
                f"{len(low_diff)} variant(s) score below 45/100 on Differentiation — "
                "they're close enough to the original that shipping both could split engagement."
            ),
            remediation=(
                "Unpin the original before pinning a recycled variant; or hold the "
                "low-differentiation variant for a future quarter."
            ),
        ))

    # Update angle without fresh data
    if angle == "update" and source.url and source.char_count == 0:
        flags.append(RedFlag(
            title="Update-angle without fresh data",
            severity="medium",
            explanation=(
                "Recycle angle is `update` but the runner has no fresh data to inject "
                "(source supplied as URL only; runner is offline). Variants contain "
                "`[insert refreshed metric here]` placeholders."
            ),
            remediation=(
                "Pair with `research-assistant` to pull updated stats; OR switch the "
                "angle to `expand` if no fresh data is available."
            ),
        ))

    # Source-date unknown
    if source.original_date == "(date unknown)":
        flags.append(RedFlag(
            title="Original post date unknown",
            severity="low",
            explanation=(
                "The original post date wasn't supplied — the attribution stamp falls "
                "back to '(date unknown)', which weakens the recycle's provenance."
            ),
            remediation=(
                "Pass `--original-post-date YYYY-MM-DD` on the next run for cleaner attribution."
            ),
        ))

    # Defensive top-up
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Voice-drift watch",
            severity="low",
            explanation=(
                "Recycling can drift voice toward the format-default tone, especially "
                "for newsletter and carousel variants."
            ),
            remediation=(
                "Pair with `brand-voice-trainer` before shipping any newsletter or "
                "carousel variant."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    variants: list[Variant],
    target_format: str,
    angle: str,
    paradox_present: bool,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    pool.append(Recommendation(
        text=(
            "Re-anchor voice via `brand-voice-trainer` before shipping any variant — "
            "recycling is the easiest place for tone to drift toward format-default."
        ),
        bridge_slug="brand-voice-trainer",
    ))
    pool.append(Recommendation(
        text=(
            "Schedule the recycled variant on `content-calendar-builder` for a window "
            "that doesn't overlap with the original's resurface cycle."
        ),
        bridge_slug="content-calendar-builder",
    ))
    pool.append(Recommendation(
        text=(
            "Snapshot the original's engagement at T-7d and the recycled variant's at "
            "T+7d to measure compounding rather than vanity reach."
        ),
        bridge_slug="analytics-summarizer",
    ))
    if any(v.target_format != "tweet" for v in variants):
        pool.append(Recommendation(
            text=(
                "After the X variant ships, cross-post the closing payoff to LinkedIn / "
                "Threads / Newsletter via `cross-platform-reposter`."
            ),
            bridge_slug="cross-platform-reposter",
        ))
    if angle == "update":
        pool.append(Recommendation(
            text=(
                "Pull fresh data, citations, and updated references via `research-assistant` "
                "before swapping in the `[insert refreshed metric here]` placeholders."
            ),
            bridge_slug="research-assistant",
        ))
    pool.append(Recommendation(
        text=(
            "If a paid-tier follow-on emerges from the recycled variant, model the "
            "funnel before launching."
        ),
        bridge_slug="monetization-optimizer",
        monetization=True,
    ))
    pool.append(Recommendation(
        text=(
            "A/B-test variant 1 vs variant 3 of the same recycle angle over a 2-week "
            "window — variant 2 fails the freshness gate."
            if paradox_present
            else "A/B-test variant 1 vs variant 2 of the same recycle angle over 2 weeks."
        ),
        bridge_slug="ab-test-suggester",
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
                        "Cross-reference the recycle scores with last week's analytics "
                        "to spot the angle that compounds best for this voice."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(Recommendation(
            text="Re-run with a clearer source post or different angle to lift confidence.",
            bridge_slug="content-idea-generator",
        ))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    source: SourceSnapshot,
    angle: str,
    target_format: str,
    variants: list[Variant],
) -> tuple[str, str]:
    src_clear = source.char_count >= 60 and source.url is None
    avg_score = (
        sum(v.recycle_score for v in variants) // max(1, len(variants))
        if variants else 0
    )
    if src_clear and avg_score >= 65 and target_format != "all":
        return ("high", f"source is clear, the {angle} angle averaged {avg_score}/100 across {len(variants)} variants.")
    if avg_score >= 55:
        return ("medium", f"average Recycle score {avg_score}/100; widen / pick a sharper angle to lift to high.")
    return ("low", f"average Recycle score {avg_score}/100 — pick a different angle or supply richer source text.")


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_source_snapshot(src: SourceSnapshot) -> str:
    headline = src.dominant_claim
    if len(headline) > 140:
        headline = headline[:137].rstrip() + "..."
    return "\n".join([
        "## Source Snapshot",
        f"**{src.handle}: {headline}**",
        "",
        f"- **X handle**: {src.handle}",
        f"- **Originally posted**: {src.original_date}",
        f"- **Source length**: {src.char_count} chars",
        f"- **Source format**: {src.source_format}",
        f"- **Dominant claim**: {src.dominant_claim}",
        f"- **Tone signal**: {src.tone_signal}",
    ])


def _render_angle_analysis(an: AngleAnalysis) -> str:
    return "\n".join([
        "## Recycle Angle Analysis",
        "",
        f"- **Chosen angle**: {an.chosen}",
        f"- **Why this angle fits**: {an.why_fits}",
        f"- **What changes vs original**: {an.what_changes}",
        f"- **What stays the same**: {an.what_stays}",
    ])


def _render_variant(v: Variant, handle: str, original_date: str, today: str) -> str:
    stamp = _recycle_stamp(handle, original_date, today)
    body_with_stamp = v.body.rstrip() + "\n\n" + stamp
    lines = [
        f"### {v.target_format.capitalize()} · Variant {v.index} · Recycle score: {v.recycle_score}/100",
        f"- **Freshness lift**: {v.freshness_lift}/100 — {v.interpretations['Freshness lift']}",
        f"- **Format fit**: {v.format_fit}/100 — {v.interpretations['Format fit']}",
        f"- **Engagement potential**: {v.engagement_potential}/100 — {v.interpretations['Engagement potential']}",
        f"- **Differentiation**: {v.differentiation}/100 — {v.interpretations['Differentiation']}",
    ]
    if v.paradox_active:
        lines.append(
            "> ⚠️ paradox: variant is well-formatted but adds no new value vs the original — that is a re-publish, not a recycle."
        )
    lines.append("")
    lines.append("```")
    lines.append(body_with_stamp)
    lines.append("```")
    if v.visual_suggestion:
        lines.append("")
        lines.append(f"**Visual suggestion**: {v.visual_suggestion}")
    return "\n".join(lines)


def _render_variants(variants: list[Variant], src: SourceSnapshot, today: str) -> str:
    return "\n\n".join(
        _render_variant(v, src.handle, src.original_date, today) for v in variants
    )


def _render_engagement_prediction(pred: dict[str, str]) -> str:
    return "\n".join([
        "## Engagement Prediction",
        "",
        f"- **Predicted lift vs static repost**: {pred['lift']}",
        f"- **Best-case driver**: {pred['best_case']}",
        f"- **Worst-case driver**: {pred['worst_case']}",
    ])


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


def _render_recycle_audit(
    src: SourceSnapshot, variants: list[Variant], target_format: str, angle: str,
) -> str:
    paradox_count = sum(1 for v in variants if v.paradox_active)
    low_diff = sum(1 for v in variants if v.differentiation < 50)
    freshness_assessment = (
        "source is older than 6 months" if src.original_date != "(date unknown)" and src.original_date < "2025-12-01"
        else "source is recent or undated"
    )
    angle_alt = "update" if angle != "update" else "expand"
    return "\n".join([
        f"- **Source freshness**: {freshness_assessment} — refresh signals are {'available' if angle == 'update' else 'partially gated by angle choice'}.",
        f"- **Angle viability**: chosen angle is `{angle}`; an alternative `{angle_alt}` run could score higher when source data permits.",
        f"- **Cannibalization exposure**: {low_diff} variant(s) score < 50 on Differentiation; manage by sequencing not parallel-shipping.",
        f"- **Suggested next run**: ship the highest-scoring variant first; hold paradox / low-Diff variants for a different angle next quarter.",
        f"- **Re-run cadence**: monthly while back-catalog has evergreen anchors, otherwise quarterly.",
    ])


def render_report(
    source: SourceSnapshot,
    angle_analysis: AngleAnalysis,
    variants: list[Variant],
    target_format: str,
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    pred: dict[str, str],
    today: str,
) -> str:
    sections = [
        _render_source_snapshot(source),
        "",
        _render_angle_analysis(angle_analysis),
        "",
        "## Recycled Variants",
        "",
        _render_variants(variants, source, today),
        "",
        _render_engagement_prediction(pred),
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

    if len(flags) > 3 or target_format == "all":
        sections.extend([
            "",
            "## Recycle Audit (auto-triggered)",
            "",
            _render_recycle_audit(source, variants, target_format, angle_analysis.chosen),
        ])

    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Refusal cards
# ---------------------------------------------------------------------------


def render_handle_mismatch_refusal(
    creator: str, source_handle: str,
) -> str:
    return (
        "## Source Snapshot\n"
        f"**Handle mismatch — refusing to recycle.**\n\n"
        f"The source post was authored by {source_handle}, but this runner was invoked "
        f"with --x-handle {creator}. Content Recycler refuses to adapt a post the creator "
        f"did not author — recycling another account's content is impersonation by another "
        f"name (Constitution Article III).\n\n"
        "## Recommendations\n"
        f"1. Re-run with --x-handle {source_handle} if {source_handle} is the creator. — bridges to: `brand-voice-trainer`\n"
        f"2. Re-run with a different source post that {creator} did author. — bridges to: `content-idea-generator`\n"
        "3. If you want to riff on someone else's post, use `quote-tweet-suggestor` "
        "instead — it preserves attribution explicitly. — bridges to: `quote-tweet-suggestor`\n\n"
        "## Confidence\n"
        "Confidence: low — handle mismatch; no recycled variants were emitted.\n"
    )


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Content Recycler (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for xAI, X, Grok and the ecosystem community. ❤️ -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_recycled_variants(
    *,
    x_handle: str,
    old_post_url_or_text: str,
    recycle_angle: str = "auto",
    target_format: str = "thread",
    original_post_date: Optional[str] = None,
    when: Optional[str] = None,
) -> str:
    handle = normalize_handle(x_handle)
    angle = parse_recycle_angle(recycle_angle)
    target_fmt = parse_target_format(target_format)

    source, mismatch = parse_source(old_post_url_or_text, handle, original_post_date)
    if mismatch is not None:
        rendered = render_handle_mismatch_refusal(handle, mismatch)
        # Privacy guard tolerates the mismatch handle on a refusal card,
        # since it's the creator's own input being echoed back as guidance.
        return rendered

    when_iso = when or date.today().isoformat()

    # Resolve auto angle
    chosen_angle = angle
    why_fits = ""
    if angle == "auto":
        chosen_angle, why_fits = pick_auto_angle(source)
    else:
        # Generate a why-fits explanation for the manually-chosen angle
        why_fits_map = {
            "update": "Creator chose `update` — angle prioritises refreshing data, numbers, and time-sensitive references.",
            "expand": "Creator chose `expand` — angle adds depth, examples, and follow-on context the original lacked.",
            "threadify": "Creator chose `threadify` — angle decomposes the source into a hook / develop / payoff thread.",
            "repurpose": "Creator chose `repurpose` — angle shifts the source into a different format while preserving substance.",
        }
        why_fits = why_fits_map.get(chosen_angle, "Manual angle selection.")

    angle_analysis = AngleAnalysis(
        chosen=chosen_angle,
        why_fits=why_fits,
        what_changes=angle_what_changes(chosen_angle, target_fmt),
        what_stays=angle_what_stays(source),
    )

    seed_rng = deterministic_rng(handle, source.text, chosen_angle, target_fmt, when_iso)
    variants = build_variants(seed_rng, source, target_fmt, chosen_angle)
    flags = build_red_flags(variants, target_fmt, source, chosen_angle)
    paradox_present = any(v.paradox_active for v in variants)
    recs = build_recommendations(seed_rng, variants, target_fmt, chosen_angle, paradox_present)
    confidence = confidence_for(source, chosen_angle, target_fmt, variants)
    pred = build_engagement_prediction(variants, target_fmt, chosen_angle)

    rendered = render_report(
        source=source,
        angle_analysis=angle_analysis,
        variants=variants,
        target_format=target_fmt,
        flags=flags,
        recs=recs,
        confidence=confidence,
        pred=pred,
        today=when_iso,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_recycled_variants


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Content Recycler (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Attribution stamp preserved\n"
        "  Built for xAI, X, Grok and the ecosystem community. ❤️\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="content-recycler",
        description=(
            "Recycle an old X post the creator authored into 2-3 variants tuned to a "
            "target format under a chosen recycle angle. Drafts only — never auto-publishes."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    p.add_argument(
        "--old-post-url-or-text",
        help="Either an x.com / twitter.com URL or the literal post text. Required unless --demo is passed.",
    )
    p.add_argument(
        "--recycle-angle",
        choices=list(ANGLE_OPTIONS),
        default="auto",
        help="Refresh angle. Default 'auto' lets the runner pick.",
    )
    p.add_argument(
        "--target-format",
        choices=list(FORMAT_OPTIONS),
        default="thread",
        help="Target format. 'all' generates one variant per format (4 total).",
    )
    p.add_argument(
        "--original-post-date",
        help="Optional ISO date (YYYY-MM-DD) of the original post; preserved in the attribution stamp.",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run with the canonical demo source post — no --old-post-url-or-text required. "
            "Variant 2 of any single-format run is pinned to the stale-rehash paradox profile "
            "so the rule always demonstrates."
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

    if args.demo and not args.old_post_url_or_text:
        post_arg = DEMO_SOURCE_TEXT
        original_date = DEMO_ORIGINAL_DATE
    elif args.old_post_url_or_text:
        post_arg = args.old_post_url_or_text
        original_date = args.original_post_date
    else:
        sys.stderr.write(
            "error: provide --old-post-url-or-text \"<post text or URL>\" or pass --demo.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_recycled_variants(
        x_handle=args.x_handle,
        old_post_url_or_text=post_arg,
        recycle_angle=args.recycle_angle,
        target_format=args.target_format,
        original_post_date=original_date,
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
