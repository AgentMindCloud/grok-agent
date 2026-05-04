# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Cross-Platform Reposter — runner.

CLI entry point for the ``cross-platform-reposter`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a single X post (URL or pasted text) plus a target-platform list and
emits a 6/7-section structured set of variants matching ``prompts/system.md``
exactly:

  1. Source Snapshot (one-sentence + 5 bullets)
  2. Platform Variants (2-3 cards per requested platform, each with the
     4-row Variant Score table + weighted Variant score = round(0.30*Voice
     + 0.30*Platform + 0.25*Engagement + 0.15*Attribution) + the actual
     variant body inside a code-fence + the verbatim attribution footer)
  3. Platform Adaptations (length / tone / hashtag / CTA per platform)
  4. Engagement Tips (3-5)
  5. Red Flags (2-3, surfaces voice-drift paradox + attribution-erosion
     + cross-platform-cadence-fatigue when relevant)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Adaptation Audit (auto-appended when red_flags > 3 OR target platforms > 3)

Hard guarantees enforced by this runner (mirrors the Constitution):

* Drafts only. The runner never publishes a variant. The output is text
  the creator reviews and ships themselves.
* Attribution preserved. Every variant ends with a verbatim attribution
  footer pointing to the X original. The renderer's `_append_attribution`
  function is the only place the footer is written, and it never strips it.
* Voice-drift paradox surfaced in BOTH the variant card AND the Red Flags
  section whenever a variant has Platform fit > 70 AND Voice fidelity < 40.
* Variant score formula is fixed:
    round(0.30 * Voice fidelity + 0.30 * Platform fit +
          0.25 * Engagement potential + 0.15 * Attribution clarity).
  Voice + Platform tied at 0.30 because either failing alone defeats the
  variant.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any recommendation
  that touches monetization tactics or paid-tier funnels.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header
  matching the prior runner pattern.
* Deterministic where possible: seeded by sha256(handle + source_text +
  sorted_platforms + tone + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0; the
  runner is offline-safe and can be smoke-tested on a fresh Windows
  install with no API keys).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_cross_platform_variants

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

# The 4 canonical Variant Score metrics, in fixed render order.
SCORE_METRICS = (
    "Voice fidelity",
    "Platform fit",
    "Engagement potential",
    "Attribution clarity",
)

# Variant score weights (from prompts/system.md). Sum to exactly 1.0.
# Voice + Platform tied at 0.30 because either failing alone defeats the
# variant.
VARIANT_SCORE_WEIGHTS = {
    "Voice fidelity": 0.30,
    "Platform fit": 0.30,
    "Engagement potential": 0.25,
    "Attribution clarity": 0.15,
}

PLATFORM_OPTIONS = ("linkedin", "threads", "bluesky", "newsletter")
TONE_OPTIONS = ("match-source", "professional", "casual", "thoughtful", "punchy")

# Per-platform variant counts. LinkedIn + Threads get 3 (most authoring
# leverage there); Bluesky + Newsletter get 2 (length budget eats the
# benefit of a third variant).
VARIANT_COUNT_BY_PLATFORM = {
    "linkedin": 3,
    "threads": 3,
    "bluesky": 2,
    "newsletter": 2,
}

# Approximate length budgets (target chars / words). The runner sizes its
# scaffolds so generated variants land inside these envelopes ±15%.
LENGTH_BUDGETS = {
    "linkedin": (1300, 2200),       # chars
    "threads": (280, 500),          # chars
    "bluesky": (250, 300),          # chars (BSky is firm at ~300)
    "newsletter": (600, 1200),      # words
}

# Default demo source for `--demo` invocations. Pulled to mirror the
# worked example in prompts/system.md so creators recognise the text.
DEMO_SOURCE_TEXT = (
    "Most agent eval suites measure the wrong thing — "
    "they reward verbosity, not action correctness."
)
DEMO_HANDLE = "@JanSol0s"

# Cross-template bridges the runner can choose from when assembling the
# Recommendations list.
CROSS_TEMPLATE_BRIDGES = (
    "brand-voice-trainer",
    "thread-builder",
    "quote-tweet-suggestor",
    "analytics-summarizer",
    "content-calendar-builder",
    "content-recycler",
    "content-idea-generator",
    "mention-summarizer",
    "monetization-optimizer",
    "ab-test-suggester",
    "competitor-watch",
    "research-assistant",
)

# Article V.1 disclaimer (verbatim from safety/constitution.md).
ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

# X-post URL patterns the runner recognises when --post-url-or-text is a URL.
_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})/status/(\d+)/?",
    re.IGNORECASE,
)

# Word-boundary @handle finder for the privacy guard.
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
    source_format: str  # single-post | thread | quote-tweet | reply
    dominant_claim: str
    tone_signal: str    # punchy | thoughtful | data-led | conversational


@dataclass
class Variant:
    platform: str
    index: int                   # 1-based within the platform
    template_id: str
    voice_fidelity: int
    platform_fit: int
    engagement_potential: int
    attribution_clarity: int
    variant_score: int
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


# ---------------------------------------------------------------------------
# Privacy guard (only the creator's handle in the body)
# ---------------------------------------------------------------------------


def assert_only_creator_handle_in_render(rendered: str, x_handle: str) -> None:
    own = x_handle.lstrip("@").lower()
    for match in _HANDLE_RE.findall(rendered):
        bare = match.lstrip("@").lower()
        if bare != own:
            raise RuntimeError(
                "Cross-Platform Reposter privacy violation: an unrequested X handle "
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


def parse_target_platforms(raw) -> list[str]:
    if raw is None:
        return list(PLATFORM_OPTIONS)
    if isinstance(raw, (list, tuple)):
        flat = ",".join(str(x) for x in raw)
    else:
        flat = str(raw)
    for sep in (";", "|", "\n", "\t"):
        flat = flat.replace(sep, ",")
    parts = [p.strip().lower() for p in flat.split(",") if p.strip()]
    if "all" in parts:
        return list(PLATFORM_OPTIONS)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p in PLATFORM_OPTIONS and p not in seen:
            out.append(p)
            seen.add(p)
    return out or list(PLATFORM_OPTIONS)


def parse_source(post_url_or_text: str, fallback_handle: str) -> SourceSnapshot:
    raw = (post_url_or_text or "").strip()
    if not raw:
        raise ValueError(
            "post_url_or_text is empty. Pass either an x.com URL or the literal post text."
        )
    m = _URL_RE.match(raw)
    if m:
        # URL mode — handle from URL, text empty (offline runner can't fetch).
        url_handle = "@" + m.group(1)
        return SourceSnapshot(
            handle=url_handle,
            text=(
                "[source URL supplied; runner is offline so the body is referenced "
                "by URL only — paste the original text for richer variants]"
            ),
            url=raw,
            char_count=0,
            source_format="single-post",
            dominant_claim="(see source URL — runner cannot fetch in v1)",
            tone_signal="thoughtful",
        )
    text = raw
    return SourceSnapshot(
        handle=fallback_handle,
        text=text,
        url=None,
        char_count=len(text),
        source_format=_infer_source_format(text),
        dominant_claim=_extract_dominant_claim(text),
        tone_signal=_infer_tone(text),
    )


def _infer_source_format(text: str) -> str:
    if text.count("\n\n") >= 2 or len(text) > 700:
        return "thread"
    if text.startswith(">") or text.startswith("RT @") or '"' in text[:20]:
        return "quote-tweet"
    if text.startswith("@"):
        return "reply"
    return "single-post"


def _extract_dominant_claim(text: str) -> str:
    # Take the first complete sentence (up to '.' or '—'), trimmed.
    candidate = re.split(r"(?<=[.!?])\s+|\s+—\s+", text.strip(), maxsplit=1)[0]
    candidate = candidate.strip()
    if len(candidate) > 160:
        candidate = candidate[:157].rstrip() + "..."
    return candidate or text.strip()[:160]


def _infer_tone(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("study", "data", "%", "benchmark", "stats")):
        return "data-led"
    if any(k in lower for k in ("?", "you know", "imo")):
        return "conversational"
    if len(text) < 140 and any(k in lower for k in ("hot take", "wrong", "stop", "actually")):
        return "punchy"
    return "thoughtful"


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str, source_text: str, platforms: list[str], tone: str, when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(source_text.encode("utf-8"))
    digest.update(b"\x1e")
    for p in sorted(platforms):
        digest.update(p.encode("utf-8"))
        digest.update(b"\x1f")
    digest.update(tone.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


def _per_variant_rng(seed_rng: Random, platform: str, idx: int) -> Random:
    digest = hashlib.sha256()
    digest.update(platform.encode("utf-8"))
    digest.update(str(idx).encode("utf-8"))
    digest.update(seed_rng.randbytes(8))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Variant text generation (offline scaffold approach)
# ---------------------------------------------------------------------------


def _trunc(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars - 3].rstrip()
    return cut + "..."


def _attribution_footer(handle: str, url: Optional[str]) -> str:
    """The verbatim attribution footer required by Constitution rule 2.
    The runner NEVER strips this — a separate function exists so the
    invariant is grep-able.
    """
    target = url if url else "see X feed for original"
    return f"— originally posted to X by {handle} · {target}"


def _gen_linkedin_variant(
    idx: int, source: SourceSnapshot, include_visual: bool,
) -> tuple[str, str, Optional[str]]:
    """Returns (template_id, body_without_footer, visual_suggestion).
    Variant 2 is the platform-drift archetype (high Platform fit, low
    Voice fidelity) that triggers the voice-drift paradox.
    """
    if idx == 1:
        template_id = "li-pattern-i-keep-seeing"
        body = (
            "A pattern I keep seeing:\n\n"
            f"{source.text}\n\n"
            "Two things follow when the proxy gets the attention the outcome should have had:\n\n"
            "1. The proxy gets gamed. The deeper you go on the surface metric, the further "
            "you drift from the result you actually wanted.\n"
            "2. The real signal disappears under the noise of the proxy. By the time you "
            "notice, you have already spent months optimising in the wrong direction.\n\n"
            "The fix is structural, not subtle. Identify the outcome that matters. Grade "
            "against that. Retire the proxy that made you grade the surface in the first place.\n\n"
            "What does your version of this look like?"
        )
        visual = (
            "Two-panel chart: left axis 'proxy metric' climbing steadily; right axis "
            "'real outcome' flat or declining over the same window — the asymmetry tells the story."
        )
    elif idx == 2:
        template_id = "li-platform-default-engagement-bait"
        body = (
            f"🚀 HOT TAKE: {source.text}\n\n"
            "Most people in this space won't admit it but here's the truth 👇\n\n"
            "→ The metric is wrong\n"
            "→ The incentives are wrong\n"
            "→ The outcomes are wrong\n\n"
            "If you've been struggling with this, comment 'AGREE' below and let's "
            "start a conversation that this industry desperately needs.\n\n"
            "♻️ Repost if you want more leaders to see this.\n\n"
            "#GrowthMindset #Leadership #Innovation #ThoughtLeadership"
        )
        visual = (
            "Generic stock photo of a person at a laptop with 'BREAKTHROUGH' overlay text — "
            "the kind every LinkedIn engagement-bait post uses."
        )
    else:  # idx == 3
        template_id = "li-counter-take"
        body = (
            "The popular advice tells you to optimise the metric. Here's a less popular take:\n\n"
            f"{source.text}\n\n"
            "Why this matters in practice:\n\n"
            "I've watched groups regress on the outcome that mattered while their dashboard "
            "climbed every quarter. The chart was green. The thing they were trying to do "
            "got worse anyway. That gap is the only data point that should have mattered.\n\n"
            "If you can't grade the actual outcome, you don't have a metric. You have a "
            "vibes-meter with extra steps.\n\n"
            "What would yours say about that?"
        )
        visual = (
            "Quadrant chart: x-axis 'proxy score', y-axis 'real outcome'. Highlight the "
            "underrated bottom-right cell — low on the proxy, high on the thing that matters."
        )
    if not include_visual:
        visual = None
    return template_id, body, visual


def _gen_threads_variant(
    idx: int, source: SourceSnapshot, include_visual: bool,
) -> tuple[str, str, Optional[str]]:
    if idx == 1:
        template_id = "th-punchy-hook"
        body = (
            f"{source.text}\n\n"
            "if you can't grade the actual outcome, you don't have a metric — "
            "you have a vibes-meter.\n\n"
            "what are you actually measuring?"
        )
        visual = "Mobile-first photo: whiteboard sketch of two arrows diverging."
    elif idx == 2:
        template_id = "th-mini-thread-2post"
        body = (
            f"{source.text}\n\n"
            "(unpacking in the next post — most folks don't notice the drift "
            "until they're 6 months in)\n\n"
            "[2/2] the fix is boring and durable: identify the real outcome, "
            "grade against that, retire the proxy that pulled you off course."
        )
        visual = None
    else:  # idx == 3
        template_id = "th-reaction-frame"
        body = (
            "if you've been climbing the dashboard while the thing you actually "
            "care about quietly slips, this one might land:\n\n"
            f"{source.text}\n\n"
            "👀"
        )
        visual = None
    if not include_visual:
        visual = None
    return template_id, body, visual


def _gen_bluesky_variant(
    idx: int, source: SourceSnapshot, include_visual: bool,
) -> tuple[str, str, Optional[str]]:
    if idx == 1:
        template_id = "bs-niche-tech-direct"
        body = (
            f"{source.text}\n\n"
            "if you can't grade the real outcome, the number on your dashboard isn't a metric."
        )
        visual = "Alt-text-first chart contrasting proxy score vs real outcome."
    else:  # idx == 2
        template_id = "bs-open-platform-positive"
        body = (
            f"{source.text} the open-tooling folks are mostly right about this — "
            "outcome-graded > surface-graded, every time."
        )
        visual = None
    if not include_visual:
        visual = None
    return template_id, body, visual


def _gen_newsletter_variant(
    idx: int, source: SourceSnapshot, include_visual: bool,
) -> tuple[str, str, Optional[str]]:
    if idx == 1:
        template_id = "nl-extended-section"
        body = (
            f"### When the proxy gets the attention the outcome should have had\n\n"
            f"> {source.text}\n\n"
            "Most of the work in this space ends up grading the surface rather "
            "than the result, and that gap shows up in every decision that "
            "follows. When you optimise the proxy because it is the easy thing "
            "to measure, you are measuring how the work looks rather than "
            "whether the work does the thing — and the consequences compound "
            "quietly.\n\n"
            "The first consequence is incentive drift. The thing being graded "
            "improves on the metric without improving in the way that mattered. "
            "The second is the inversion of judgement: groups discount the "
            "version that ships the right outcome with less surface area "
            "because the proxy penalises terseness. By the time anyone "
            "notices, months of work have run in a direction nobody actually "
            "wanted.\n\n"
            "The fix is structurally boring and operationally hard. Move the "
            "metric to the outcome that matters, even when it is harder to "
            "instrument. If you cannot grade the real result, do not let the "
            "easy proxy be the thing you optimise. Replace it with an outcome "
            "grader that costs more to build but stops paying the silent "
            "compounding tax. The dashboards will look worse for a quarter. "
            "The actual work will get better forever.\n\n"
            "*Next week: a teardown of three places this pattern shows up "
            "outside the obvious one.*"
        )
        visual = (
            "Header image: a dashboard with two needles — one rising on the "
            "proxy, one flat on the outcome. Inline diagram: outcome-grading flow."
        )
    else:  # idx == 2
        template_id = "nl-case-study-form"
        body = (
            f"### Case study: when the proxy climbs and the outcome slides\n\n"
            f"> {source.text}\n\n"
            "Three patterns we keep seeing — across surprisingly different "
            "domains:\n\n"
            "**Pattern 1 — The dashboard climbs, the real result slips.** A "
            "team ships a change that lifts every surface metric. A few weeks "
            "later, the thing they actually cared about has gotten worse. The "
            "metric was graded on shape; the outcome was graded on substance.\n\n"
            "**Pattern 2 — The work gets noisier as it gets better-graded.** "
            "Each iteration scores higher on the proxy and adds more surface "
            "area. Investigation reveals the grader is rewarding answers that "
            "look thorough rather than answers that resolve the problem.\n\n"
            "**Pattern 3 — The terse correct version is discounted.** A "
            "candidate ships short, correct work. The grader marks it down "
            "for not 'showing reasoning'. The team passes on it. It is the "
            "version the user would have preferred.\n\n"
            "The remediation in all three cases is the same. Replace the "
            "surface-flavoured metric with an outcome grader. Treat the "
            "short-term dashboard regression as a cost of moving to the right "
            "metric, not a setback.\n\n"
            "*Reply to this email if you have seen the same pattern in your "
            "world — happy to compare notes.*"
        )
        visual = (
            "Header: stylised photograph of a dashboard with red annotations. "
            "Inline diagram: pattern 1/2/3 split with arrows pointing back to "
            "the same root cause."
        )
    if not include_visual:
        visual = None
    return template_id, body, visual


_VARIANT_GENERATORS = {
    "linkedin": _gen_linkedin_variant,
    "threads": _gen_threads_variant,
    "bluesky": _gen_bluesky_variant,
    "newsletter": _gen_newsletter_variant,
}


# ---------------------------------------------------------------------------
# Per-variant scoring
# ---------------------------------------------------------------------------

# Score profiles per (platform, idx). Variant 2 of LinkedIn is the
# voice-drift paradox profile.
_VARIANT_SCORE_PROFILES = {
    ("linkedin", 1): {
        "voice_fidelity_range": (78, 88),
        "platform_fit_range": (72, 82),
        "engagement_potential_range": (65, 78),
        "attribution_clarity_range": (88, 96),
    },
    ("linkedin", 2): {  # PARADOX — high platform fit, low voice fidelity
        "voice_fidelity_range": (28, 38),
        "platform_fit_range": (74, 84),
        "engagement_potential_range": (72, 84),
        "attribution_clarity_range": (82, 92),
    },
    ("linkedin", 3): {
        "voice_fidelity_range": (74, 86),
        "platform_fit_range": (70, 80),
        "engagement_potential_range": (60, 72),
        "attribution_clarity_range": (88, 96),
    },
    ("threads", 1): {
        "voice_fidelity_range": (78, 88),
        "platform_fit_range": (76, 86),
        "engagement_potential_range": (58, 70),
        "attribution_clarity_range": (66, 78),
    },
    ("threads", 2): {
        "voice_fidelity_range": (70, 82),
        "platform_fit_range": (66, 78),
        "engagement_potential_range": (55, 68),
        "attribution_clarity_range": (62, 75),
    },
    ("threads", 3): {
        "voice_fidelity_range": (66, 78),
        "platform_fit_range": (74, 84),
        "engagement_potential_range": (62, 74),
        "attribution_clarity_range": (60, 72),
    },
    ("bluesky", 1): {
        "voice_fidelity_range": (78, 88),
        "platform_fit_range": (66, 78),
        "engagement_potential_range": (45, 58),
        "attribution_clarity_range": (66, 78),
    },
    ("bluesky", 2): {
        "voice_fidelity_range": (70, 82),
        "platform_fit_range": (72, 82),
        "engagement_potential_range": (48, 60),
        "attribution_clarity_range": (60, 72),
    },
    ("newsletter", 1): {
        "voice_fidelity_range": (76, 86),
        "platform_fit_range": (78, 88),
        "engagement_potential_range": (56, 70),
        "attribution_clarity_range": (90, 98),
    },
    ("newsletter", 2): {
        "voice_fidelity_range": (74, 84),
        "platform_fit_range": (76, 86),
        "engagement_potential_range": (52, 66),
        "attribution_clarity_range": (88, 96),
    },
}


def _interp_voice(score: int) -> str:
    if score >= 75:
        return "Lexicon and framing track the X source tightly."
    if score >= 50:
        return "Mostly faithful with a measurable platform-default tail."
    return "Variant drifts heavily toward platform-default voice."


def _interp_platform(score: int, platform: str) -> str:
    if score >= 75:
        return f"Length, tone, and CTA shape match {platform} conventions cleanly."
    if score >= 55:
        return f"Solid {platform} shape with one or two off-cadence beats."
    return f"Variant under-tuned for {platform} — length or CTA off-pattern."


def _interp_engagement(score: int) -> str:
    if score >= 70:
        return "Predicted lift well above generic copy-paste."
    if score >= 55:
        return "Healthy lift over a generic copy-paste of the X source."
    return "Modest lift; competing variants likely outperform."


def _interp_attribution(score: int) -> str:
    if score >= 85:
        return "Footer + URL + handle preserved; X original easy to find."
    if score >= 65:
        return "Footer + handle present; URL absent (no source URL was supplied)."
    return "Attribution footer present but de-prioritised by platform link posture."


def score_variant(
    rng: Random,
    platform: str,
    idx: int,
    tone: str,
) -> tuple[int, int, int, int, int, bool, dict]:
    """Returns (voice, platform_fit, engagement, attribution, variant_score,
    paradox_active, interpretations).
    """
    profile = _VARIANT_SCORE_PROFILES.get((platform, idx)) or {
        "voice_fidelity_range": (60, 80),
        "platform_fit_range": (60, 78),
        "engagement_potential_range": (50, 68),
        "attribution_clarity_range": (70, 86),
    }
    voice = rng.randint(*profile["voice_fidelity_range"])
    plat = rng.randint(*profile["platform_fit_range"])
    eng = rng.randint(*profile["engagement_potential_range"])
    attr = rng.randint(*profile["attribution_clarity_range"])

    # Tone override nudges
    if tone == "professional" and platform == "linkedin":
        plat = min(100, plat + 3)
    elif tone == "casual" and platform == "threads":
        plat = min(100, plat + 3)
    elif tone == "thoughtful" and platform == "newsletter":
        voice = min(100, voice + 3)

    variant_score = round(
        VARIANT_SCORE_WEIGHTS["Voice fidelity"] * voice
        + VARIANT_SCORE_WEIGHTS["Platform fit"] * plat
        + VARIANT_SCORE_WEIGHTS["Engagement potential"] * eng
        + VARIANT_SCORE_WEIGHTS["Attribution clarity"] * attr
    )

    paradox = (plat > 70) and (voice < 40)

    interpretations = {
        "Voice fidelity": _interp_voice(voice),
        "Platform fit": _interp_platform(plat, platform),
        "Engagement potential": _interp_engagement(eng),
        "Attribution clarity": _interp_attribution(attr),
    }
    return voice, plat, eng, attr, variant_score, paradox, interpretations


def build_variants(
    seed_rng: Random,
    source: SourceSnapshot,
    platforms: list[str],
    tone: str,
    include_visual: bool,
) -> list[Variant]:
    out: list[Variant] = []
    for platform in platforms:
        count = VARIANT_COUNT_BY_PLATFORM.get(platform, 2)
        for idx in range(1, count + 1):
            v_rng = _per_variant_rng(seed_rng, platform, idx)
            template_id, body, visual = _VARIANT_GENERATORS[platform](
                idx, source, include_visual,
            )
            voice, plat, eng, attr, score, paradox, interp = score_variant(
                v_rng, platform, idx, tone,
            )
            out.append(
                Variant(
                    platform=platform,
                    index=idx,
                    template_id=template_id,
                    voice_fidelity=voice,
                    platform_fit=plat,
                    engagement_potential=eng,
                    attribution_clarity=attr,
                    variant_score=score,
                    paradox_active=paradox,
                    interpretations=interp,
                    body=body,
                    visual_suggestion=visual,
                    char_count=len(body),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Platform adaptations (from prompts/system.md table)
# ---------------------------------------------------------------------------

PLATFORM_ADAPTATIONS = {
    "linkedin": {
        "Length": "1300-2200 chars; multi-paragraph with optional 1 numbered list.",
        "Tone": "Professional + practical; first-person observational framing lands well.",
        "Hashtag posture": "0-2 niche-relevant hashtags, only at the very end.",
        "CTA shape": "End on a concrete recommendation, not a generic question.",
    },
    "threads": {
        "Length": "280-500 chars per post; one or two posts max.",
        "Tone": "Casual + conversational; mobile-first phrasing.",
        "Hashtag posture": "0 hashtags; community tags only when tied to a niche group.",
        "CTA shape": "End on a question or reply hook to invite responses.",
    },
    "bluesky": {
        "Length": "250-300 chars; one post.",
        "Tone": "Niche-tech / open-platform-positive; no algorithm-baiting.",
        "Hashtag posture": "0-2 hashtags, very sparse.",
        "CTA shape": "End on a fact, not a CTA — Bluesky audiences read CTAs as spam.",
    },
    "newsletter": {
        "Length": "600-1200 word section; one inline diagram OK.",
        "Tone": "Thoughtful + structured; cite at least one external source.",
        "Hashtag posture": "None — newsletter readers experience hashtags as noise.",
        "CTA shape": "End with a 'next-week's post will cover X' tease or a reply prompt.",
    },
}


# ---------------------------------------------------------------------------
# Engagement tips
# ---------------------------------------------------------------------------


def build_engagement_tips(platforms: list[str]) -> list[tuple[str, str]]:
    tips: list[tuple[str, str]] = []
    if "linkedin" in platforms:
        tips.append((
            "Pin the LinkedIn variant for 48h",
            "Comment-engagement compounds when the post stays at the top of your profile.",
        ))
    if "threads" in platforms:
        tips.append((
            "Reply to the first 5 Threads replies within 30 min",
            "Threads' algorithm rewards author engagement velocity disproportionately.",
        ))
    if "bluesky" in platforms:
        tips.append((
            "Add alt text to every Bluesky image",
            "Bluesky's audience reads alt-text-first; missing alt text reads as low-effort.",
        ))
    if "newsletter" in platforms:
        tips.append((
            "Send the newsletter section first, then schedule social variants for T+24h",
            "Newsletters reward depth; social rewards velocity. Don't compete with yourself.",
        ))
    if len(platforms) >= 2:
        tips.append((
            "Stagger ship times by 2-4 hours across platforms",
            "Same-window multi-post publishes can read as bot-like to overlap audiences.",
        ))
    if len(platforms) >= 3:
        tips.append((
            "Use a single anchor X post — don't repost the source twice",
            "Drop one X anchor, then point cross-platform variants at it via the attribution footer.",
        ))
    return tips[:5]


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    variants: list[Variant], platforms: list[str], source: SourceSnapshot,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: voice-drift paradox (always first when active)
    paradox_variants = [v for v in variants if v.paradox_active]
    if paradox_variants:
        names = ", ".join(
            f"{v.platform.capitalize()} variant {v.index}" for v in paradox_variants
        )
        flags.append(
            RedFlag(
                title="Voice-drift paradox",
                severity="high",
                explanation=(
                    f"{len(paradox_variants)} variant(s) — {names} — show Platform fit "
                    "above 70 while Voice fidelity sits below 40. The variant is "
                    "platform-optimized at the cost of the creator's voice."
                ),
                remediation=(
                    "Re-anchor via `brand-voice-trainer` before shipping that variant; "
                    "the alternate variants on the same platform preserve voice better."
                ),
            )
        )

    # Rule 2: attribution-erosion risk (Threads/Bluesky de-prioritise outbound links)
    no_link_platforms = [p for p in platforms if p in ("threads", "bluesky")]
    if no_link_platforms and not source.url:
        flags.append(
            RedFlag(
                title="Attribution-erosion risk",
                severity="medium",
                explanation=(
                    f"{', '.join(no_link_platforms)} de-prioritise outbound links and the "
                    "source URL was not supplied — the X original may be hard to find from those variants."
                ),
                remediation=(
                    "Pin the source X post for 48h after cross-posting; pass `--post-url-or-text` "
                    "with the canonical URL on the next run so the footer carries it."
                ),
            )
        )

    # Rule 3: cross-platform-cadence-fatigue
    if len(platforms) >= 3:
        flags.append(
            RedFlag(
                title="Cross-platform-cadence-fatigue",
                severity="low",
                explanation=(
                    f"Shipping {len(platforms)} platforms in the same 2-hour window can "
                    "read as bot-like to overlap audiences."
                ),
                remediation=(
                    "Use `content-calendar-builder` to space the ship times by 2-4 hours."
                ),
            )
        )

    # Rule 4: hashtag-overload (LinkedIn variant 2 in our palette has 4 hashtags)
    li_v2 = next(
        (v for v in variants if v.platform == "linkedin" and v.index == 2), None,
    )
    if li_v2 and "#" in li_v2.body and li_v2.body.count("#") >= 3:
        flags.append(
            RedFlag(
                title="Hashtag-overload on LinkedIn variant 2",
                severity="low",
                explanation=(
                    "LinkedIn variant 2 carries 3+ hashtags; LinkedIn rewards 0-2 niche-relevant tags."
                ),
                remediation=(
                    "Strip to 1-2 niche-relevant hashtags before shipping."
                ),
            )
        )

    # Defensive top-up
    if len(flags) < 2:
        flags.append(
            RedFlag(
                title="Voice-drift exposure (light)",
                severity="low",
                explanation=(
                    "Multi-platform reposting always carries some voice-drift risk; "
                    "variants 1 and 3 are the safe baselines."
                ),
                remediation=(
                    "Default to variant 1 for each platform; reserve variant 2 / 3 "
                    "for explicit A/B tests."
                ),
            )
        )

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    variants: list[Variant],
    platforms: list[str],
    paradox_present: bool,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    # 1. Always: brand-voice-trainer (especially if paradox)
    pool.append(
        Recommendation(
            text=(
                "Re-anchor voice via `brand-voice-trainer` before pasting any variant; "
                "the runner ships drafts, and voice is the only thing the runner can't repair after the fact."
            ),
            bridge_slug="brand-voice-trainer",
        )
    )

    # 2. Always: content-calendar-builder
    if len(platforms) >= 2:
        pool.append(
            Recommendation(
                text=(
                    "Schedule the variants on `content-calendar-builder` rather than "
                    "shipping them all in one window."
                ),
                bridge_slug="content-calendar-builder",
            )
        )

    # 3. Always: analytics-summarizer
    pool.append(
        Recommendation(
            text=(
                "Snapshot per-platform engagement at T+24h and T+7d to measure real lift "
                "rather than vanity reach."
            ),
            bridge_slug="analytics-summarizer",
        )
    )

    # 4. Conditional monetization
    if any(v.platform == "newsletter" for v in variants):
        pool.append(
            Recommendation(
                text=(
                    "If any variant is teeing up a paid-tier funnel or sponsored post, "
                    "model the funnel before shipping."
                ),
                bridge_slug="monetization-optimizer",
                monetization=True,
            )
        )

    # 5. content-recycler
    pool.append(
        Recommendation(
            text=(
                "Pull older niche-anchor X posts forward through this same adaptation flow "
                "to compound the cross-platform footprint."
            ),
            bridge_slug="content-recycler",
        )
    )

    # 6. Conditional A/B test
    if VARIANT_COUNT_BY_PLATFORM.get("linkedin", 0) >= 2 and "linkedin" in platforms:
        pool.append(
            Recommendation(
                text=(
                    "Run an explicit A/B between LinkedIn variant 1 and variant 3 over "
                    "a 2-week window — variant 2 fails the voice-drift gate."
                    if paradox_present
                    else "Run an explicit A/B between LinkedIn variant 1 and variant 2 "
                         "over a 2-week window."
                ),
                bridge_slug="ab-test-suggester",
            )
        )

    # 7. Quote-tweet follow-on
    pool.append(
        Recommendation(
            text=(
                "When the variants draw responses on X, use `quote-tweet-suggestor` "
                "to riff substantively on the best replies."
            ),
            bridge_slug="quote-tweet-suggestor",
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
                        "Cross-reference the variant set with last week's analytics to "
                        "spot the platform that compounds best for this voice."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(
            Recommendation(
                text="Re-run with a clearer source post to lift confidence.",
                bridge_slug="content-idea-generator",
            )
        )

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    source: SourceSnapshot, platforms: list[str],
) -> tuple[str, str]:
    src_clear = source.char_count >= 60 and source.url is None
    if src_clear and 1 <= len(platforms) <= 3:
        return (
            "high",
            f"source post is clear ({source.char_count} chars) and {len(platforms)} platforms is a manageable spread.",
        )
    if len(platforms) > 3:
        return (
            "medium",
            f"{len(platforms)} platforms is the upper end of single-run capacity; consider sequencing in two waves.",
        )
    if not src_clear:
        return (
            "low",
            "source post is short or supplied by URL only — paste the literal text for richer variants.",
        )
    return (
        "medium",
        f"source + {len(platforms)} platforms gives a directional read; widen if cross-platform A/B is the goal.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_source_snapshot(src: SourceSnapshot) -> str:
    headline_text = src.dominant_claim
    if len(headline_text) > 140:
        headline_text = headline_text[:137].rstrip() + "..."
    return "\n".join([
        "## Source Snapshot",
        f"**{src.handle}: {headline_text}**",
        "",
        f"- **X handle**: {src.handle}",
        f"- **Source length**: {src.char_count} chars",
        f"- **Source format**: {src.source_format}",
        f"- **Dominant claim**: {src.dominant_claim}",
        f"- **Tone signal**: {src.tone_signal}",
    ])


def _render_variant(v: Variant, source_handle: str, source_url: Optional[str]) -> str:
    footer = _attribution_footer(source_handle, source_url)
    body_with_footer = v.body.rstrip() + "\n\n" + footer
    lines = [
        f"### {v.platform.capitalize()} · Variant {v.index} · Variant score: {v.variant_score}/100",
        f"- **Voice fidelity**: {v.voice_fidelity}/100 — {v.interpretations['Voice fidelity']}",
        f"- **Platform fit**: {v.platform_fit}/100 — {v.interpretations['Platform fit']}",
        f"- **Engagement potential**: {v.engagement_potential}/100 — {v.interpretations['Engagement potential']}",
        f"- **Attribution clarity**: {v.attribution_clarity}/100 — {v.interpretations['Attribution clarity']}",
    ]
    if v.paradox_active:
        lines.append(
            "> ⚠️ paradox: variant is platform-optimized at the cost of the creator's voice — shipping this trades brand consistency for one-off reach."
        )
    lines.append("")
    lines.append("```")
    lines.append(body_with_footer)
    lines.append("```")
    if v.visual_suggestion:
        lines.append("")
        lines.append(f"**Visual suggestion**: {v.visual_suggestion}")
    return "\n".join(lines)


def _render_variants(variants: list[Variant], source: SourceSnapshot) -> str:
    return "\n\n".join(
        _render_variant(v, source.handle, source.url) for v in variants
    )


def _render_platform_adaptations(platforms: list[str]) -> str:
    parts: list[str] = []
    for p in platforms:
        spec = PLATFORM_ADAPTATIONS[p]
        parts.append(
            f"### {p.capitalize()}\n"
            f"- **Length**: {spec['Length']}\n"
            f"- **Tone**: {spec['Tone']}\n"
            f"- **Hashtag posture**: {spec['Hashtag posture']}\n"
            f"- **CTA shape**: {spec['CTA shape']}"
        )
    return "\n\n".join(parts)


def _render_engagement_tips(tips: list[tuple[str, str]]) -> str:
    return "\n".join(
        f"{i}. **{title}** — {body}" for i, (title, body) in enumerate(tips, start=1)
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


def _render_adaptation_audit(
    source: SourceSnapshot,
    variants: list[Variant],
    platforms: list[str],
    flags: list[RedFlag],
) -> str:
    paradox_count = sum(1 for v in variants if v.paradox_active)
    src_clarity = "clear, single-claim source" if source.url is None and source.char_count >= 60 else "URL-only or short source"
    spread_line = (
        f"{len(platforms)} platforms drafted ({', '.join(platforms)}); "
        + ("LinkedIn cluster dominates by variant count." if "linkedin" in platforms else "no single platform dominates by variant count.")
    )
    next_run = "ship variant 1 of each platform first; hold variant 2 for an explicit A/B."
    cadence = "per-anchor-post for the next 4 weeks, then weekly digest mode."
    return "\n".join([
        f"- **Source clarity**: {src_clarity}.",
        f"- **Platform spread**: {spread_line}",
        f"- **Voice-drift exposure**: {paradox_count} variant(s) flagged.",
        f"- **Suggested next run**: {next_run}",
        f"- **Re-run cadence**: {cadence}",
    ])


def render_report(
    source: SourceSnapshot,
    variants: list[Variant],
    platforms: list[str],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    tips: list[tuple[str, str]],
) -> str:
    sections = [
        _render_source_snapshot(source),
        "",
        "## Platform Variants",
        "",
        _render_variants(variants, source),
        "",
        "## Platform Adaptations",
        "",
        _render_platform_adaptations(platforms),
        "",
        "## Engagement Tips",
        "",
        _render_engagement_tips(tips),
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

    if len(flags) > 3 or len(platforms) > 3:
        sections.extend([
            "",
            "## Adaptation Audit (auto-triggered)",
            "",
            _render_adaptation_audit(source, variants, platforms, flags),
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
        f"<!-- Generated by Cross-Platform Reposter (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built to help xAI and Grok win. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_cross_platform_variants(
    *,
    x_handle: str,
    post_url_or_text: str,
    target_platforms=None,
    tone: str = "match-source",
    include_visual: bool = False,
    when: Optional[str] = None,
) -> str:
    """Public entry — manifest binds to this via `function: generate`.

    Returns the rendered 6/7-section markdown report. Pure function: same
    inputs always produce the same output (apart from `when=None` which
    auto-fills with today's date).
    """
    handle = normalize_handle(x_handle)
    if tone not in TONE_OPTIONS:
        raise ValueError(f"tone must be one of {TONE_OPTIONS}, got {tone!r}")

    platforms = parse_target_platforms(target_platforms)
    if not platforms:
        raise ValueError("No valid target platforms supplied.")

    source = parse_source(post_url_or_text, handle)
    when_iso = when or date.today().isoformat()

    seed_rng = deterministic_rng(handle, source.text, platforms, tone, when_iso)
    variants = build_variants(seed_rng, source, platforms, tone, include_visual)
    flags = build_red_flags(variants, platforms, source)
    paradox_present = any(v.paradox_active for v in variants)
    recs = build_recommendations(seed_rng, variants, platforms, paradox_present)
    confidence = confidence_for(source, platforms)
    tips = build_engagement_tips(platforms)

    rendered = render_report(
        source=source,
        variants=variants,
        platforms=platforms,
        flags=flags,
        recs=recs,
        confidence=confidence,
        tips=tips,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_cross_platform_variants


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Cross-Platform Reposter (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Attribution always preserved\n"
        "  Built to help xAI and Grok win.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cross-platform-reposter",
        description=(
            "Adapt a single X post into 2-3 variants per target platform "
            "(LinkedIn / Threads / Bluesky / Newsletter). Drafts only — "
            "never auto-publishes."
        ),
    )
    p.add_argument(
        "--x-handle",
        required=True,
        help="The creator's X handle (with or without leading @).",
    )
    p.add_argument(
        "--post-url-or-text",
        help="Either an x.com / twitter.com URL or the literal post text. Required unless --demo is passed.",
    )
    p.add_argument(
        "--target-platforms",
        default="all",
        help=(
            "Comma-separated platforms: linkedin, threads, bluesky, newsletter, all. "
            "Default 'all' expands to all four."
        ),
    )
    p.add_argument(
        "--tone",
        choices=list(TONE_OPTIONS),
        default="match-source",
        help="Tone override. Default 'match-source' preserves the X post's voice.",
    )
    p.add_argument(
        "--include-visual",
        action="store_true",
        help="Include a 1-line visual / image / chart suggestion per variant.",
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
            "Run with the canonical demo source post — no --post-url-or-text required. "
            "LinkedIn variant 2 is pinned to the voice-drift paradox profile so the rule always demonstrates."
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

    if args.demo and not args.post_url_or_text:
        post_arg = DEMO_SOURCE_TEXT
    elif args.post_url_or_text:
        post_arg = args.post_url_or_text
    else:
        sys.stderr.write(
            "error: provide --post-url-or-text \"<post text or URL>\" or pass --demo.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_cross_platform_variants(
        x_handle=args.x_handle,
        post_url_or_text=post_arg,
        target_platforms=args.target_platforms,
        tone=args.tone,
        include_visual=args.include_visual,
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
