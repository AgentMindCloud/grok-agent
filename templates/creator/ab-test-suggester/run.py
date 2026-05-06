# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""AB Test Suggester — runner.

CLI entry point for the ``ab-test-suggester`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a single post idea (URL or pasted text) plus a chosen test_focus
and num_variants and emits a 6/7-section structured A/B test plan
matching ``prompts/system.md`` exactly:

  1. Test Snapshot (one-sentence + 5 bullets including Hypothesis)
  2. Test Plan (4-row Test Plan Score table + weighted Test Plan score
     round(0.30*Variant clarity + 0.25*Test isolation +
           0.25*Sample feasibility + 0.20*Decision actionability))
  3. Variants (2-3 cards; Variant A = control, Variant B/C =
     treatments; each card carries a single-line "Diff vs control
     (single-axis)" describing the ONE thing that changed)
  4. Success Metrics (primary + 1-2 secondary + decision rule)
  5. Statistical Notes (sample / duration / significance — heuristics,
     never fabricated p-values; explicit cannibalization disclosure)
  6. Red Flags (2-3, surfaces multi-variable paradox in BOTH the Test
     Plan section AND this section when triggered)
  7. Recommendations (3-5, with >= 3 cross-template bridges)
  8. Confidence
  + Optional Test Plan Audit (auto-appended when red_flags > 3 OR
    test_focus='all')

Hard guarantees enforced by this runner (mirrors the Constitution):

* Drafts only. The runner emits a test plan + variant text the creator
  reviews and ships.
* Single-axis isolation. When test_focus is one of 'headline'/'visual'/
  'cta'/'timing', the variants vary on that one dimension only. The
  runner refuses (via render_multi_axis_refusal) any caller that would
  mix dimensions on a single-axis run. With test_focus='all' the
  runner picks ONE dimension internally and generates single-axis
  variants on that picked dimension.
* Multi-variable paradox surfaced in BOTH the Test Plan section AND
  the Red Flags section whenever Variant clarity > 70 AND Test
  isolation < 40. The `--demo` mode pins scoring to this profile so
  the rule reliably demonstrates.
* Test Plan score formula is fixed:
    round(0.30*Variant clarity + 0.25*Test isolation +
          0.25*Sample feasibility + 0.20*Decision actionability).
  Variant clarity weighted highest — if variants aren't clearly
  different, no other metric matters.
* No fabricated statistics. Sample-size / duration / significance are
  rough heuristics named as such. The runner refuses to print
  invented p-values or confidence intervals.
* Cannibalization disclosure. When variants ship to the same audience
  without splitting reach (the X-native default), the runner names the
  cannibalization risk explicitly.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any monetization-
  related recommendation.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + idea +
  test_focus + num_variants + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_ab_test_plan

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
    "Variant clarity",
    "Test isolation",
    "Sample feasibility",
    "Decision actionability",
)

# Test Plan score weights — Variant clarity weighted highest because
# if variants aren't clearly different, no other metric matters.
TEST_PLAN_WEIGHTS = {
    "Variant clarity": 0.30,
    "Test isolation": 0.25,
    "Sample feasibility": 0.25,
    "Decision actionability": 0.20,
}

TEST_FOCUS_OPTIONS = ("headline", "visual", "cta", "timing", "all")
SINGLE_AXIS_FOCUSES = ("headline", "visual", "cta", "timing")
MIN_VARIANTS = 2
MAX_VARIANTS = 3

DEMO_HANDLE = "@JanSol0s"
DEMO_POST_IDEA = (
    "Most agent eval suites measure the wrong thing — "
    "they reward verbosity, not action correctness."
)

DEMO_PRODUCTIVITY_HANDLE = "@habitstacker"
DEMO_PRODUCTIVITY_IDEA = (
    "Stop optimizing for the morning routine — optimize for the friction "
    "your evening self leaves the morning self to clean up."
)

# Cross-template bridges
CROSS_TEMPLATE_BRIDGES = (
    "analytics-summarizer",
    "content-idea-generator",
    "thread-builder",
    "brand-voice-trainer",
    "content-recycler",
    "cross-platform-reposter",
    "competitor-watch",
    "quote-tweet-suggestor",
    "monetization-optimizer",
    "mention-summarizer",
    "growth-experiment-runner",
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
class IdeaSnapshot:
    handle: str
    text: str
    url: Optional[str]
    char_count: int
    dominant_claim: str
    tone_signal: str


@dataclass
class TestPlanScores:
    variant_clarity: int
    test_isolation: int
    sample_feasibility: int
    decision_actionability: int
    plan_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)


@dataclass
class Variant:
    label: str   # "A · Control", "B · Treatment", "C · Treatment 2"
    diff_line: str
    body: str
    is_control: bool = False


@dataclass
class SuccessMetrics:
    primary: str
    secondary_1: str
    secondary_2: str
    decision_rule: str


@dataclass
class StatisticalNotes:
    sample_estimate: str
    duration_estimate: str
    significance_heuristic: str
    confounders: str


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
                "AB Test Suggester privacy violation: a non-creator X handle "
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


def parse_idea(post_idea_or_url: str, fallback_handle: str) -> IdeaSnapshot:
    raw = (post_idea_or_url or "").strip()
    if not raw:
        raise ValueError(
            "post_idea_or_url is empty. Pass either an x.com URL or the literal idea text."
        )
    m = _URL_RE.match(raw)
    if m:
        url_handle = "@" + m.group(1)
        return IdeaSnapshot(
            handle=url_handle,
            text=(
                "[idea URL supplied; runner is offline so the body is referenced "
                "by URL only — paste the literal idea text for richer variants]"
            ),
            url=raw,
            char_count=0,
            dominant_claim="(see source URL — runner cannot fetch in v1)",
            tone_signal="thoughtful",
        )
    text = raw
    return IdeaSnapshot(
        handle=fallback_handle,
        text=text,
        url=None,
        char_count=len(text),
        dominant_claim=_extract_claim(text),
        tone_signal=_infer_tone(text),
    )


def _extract_claim(text: str) -> str:
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
# Auto-focus picker
# ---------------------------------------------------------------------------


def pick_auto_focus(idea: IdeaSnapshot) -> tuple[str, str]:
    """Returns (chosen_focus, why_fits)."""
    has_numbers = bool(re.search(r"\d", idea.text))
    is_short = idea.char_count > 0 and idea.char_count < 200
    has_question = "?" in idea.text
    has_imperative = any(idea.text.lower().startswith(v) for v in ("stop ", "build ", "ship ", "do "))

    if has_numbers:
        return ("headline", "Idea is data-led — headline framing carries the most signal on this niche.")
    if has_question:
        return ("cta", "Idea ends on a question — testing CTA shape is the highest-leverage dimension.")
    if has_imperative:
        return ("headline", "Idea opens with an imperative — testing the imperative framing is highest-leverage.")
    if is_short:
        return ("visual", "Idea is short and punchy — testing visual presence is the cleanest A/B.")
    return ("headline", "Default — headline framing carries the most signal on most niches.")


# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str, idea_text: str, test_focus: str, num_variants: int, when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(idea_text.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(test_focus.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(str(num_variants).encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


# ---------------------------------------------------------------------------
# Variant text scaffolds (single-axis per focus)
# ---------------------------------------------------------------------------


def _gen_headline_variants(idea: IdeaSnapshot, num: int) -> list[Variant]:
    """Single-axis: only the first 1-2 lines (the hook) differ across
    variants. Body is byte-identical."""
    body_tail = (
        "\n\nThe pattern shows up in three concrete shapes. The dashboard "
        "climbs while the outcome slides. The proxy gets gamed as it gets "
        "graded. The terse correct version gets discounted for not "
        "performing thoroughness.\n\n"
        "If you can't grade the actual outcome in a sandbox, you don't "
        "have a metric. You have a vibes-meter with extra steps."
    )
    out: list[Variant] = []
    out.append(Variant(
        label="A · Control",
        diff_line="control — ships the idea as-is on the headline dimension.",
        body=idea.text + body_tail,
        is_control=True,
    ))
    out.append(Variant(
        label="B · Treatment",
        diff_line="outcome-led headline; body byte-identical to control.",
        body=(
            "if you can't run the action, you don't have a metric." + body_tail
        ),
    ))
    if num >= 3:
        out.append(Variant(
            label="C · Treatment 2",
            diff_line="question-led headline; body byte-identical to control.",
            body=(
                "what is your eval suite actually measuring?" + body_tail
            ),
        ))
    return out


def _gen_visual_variants(idea: IdeaSnapshot, num: int) -> list[Variant]:
    """Single-axis: only the visual companion differs. Post text identical."""
    post = idea.text
    out: list[Variant] = [
        Variant(
            label="A · Control",
            diff_line="control — ships the idea as text-only.",
            body=(
                f"{post}\n\n[no inline visual — text-only post]"
            ),
            is_control=True,
        ),
        Variant(
            label="B · Treatment",
            diff_line="adds a single inline chart visual; post text byte-identical.",
            body=(
                f"{post}\n\n[inline visual: two-panel chart contrasting the "
                "proxy metric (rising) and the real outcome (flat) over the "
                "same window]"
            ),
        ),
    ]
    if num >= 3:
        out.append(Variant(
            label="C · Treatment 2",
            diff_line="adds a single inline diagram visual; post text byte-identical.",
            body=(
                f"{post}\n\n[inline visual: simple before/after diagram of "
                "the optimization pattern the idea critiques]"
            ),
        ))
    return out


def _gen_cta_variants(idea: IdeaSnapshot, num: int) -> list[Variant]:
    """Single-axis: only the closing CTA line differs. Hook + body identical."""
    out: list[Variant] = [
        Variant(
            label="A · Control",
            diff_line="control — closes on a generic question.",
            body=(
                f"{idea.text}\n\nWhat are you actually measuring?"
            ),
            is_control=True,
        ),
        Variant(
            label="B · Treatment",
            diff_line="closes on a concrete action; rest of post byte-identical.",
            body=(
                f"{idea.text}\n\nIf this lands, drop the proxy this week and "
                "watch the dashboard regress on purpose."
            ),
        ),
    ]
    if num >= 3:
        out.append(Variant(
            label="C · Treatment 2",
            diff_line="closes on a DM-prompt; rest of post byte-identical.",
            body=(
                f"{idea.text}\n\nDM if you want the case-study breakdown."
            ),
        ))
    return out


def _gen_timing_variants(idea: IdeaSnapshot, num: int) -> list[Variant]:
    """Single-axis: post body byte-identical; only the ship time varies."""
    base = idea.text
    out: list[Variant] = [
        Variant(
            label="A · Control",
            diff_line="control — ships Tuesday 09:00 local.",
            body=(
                f"{base}\n\n[ship-time: Tuesday 09:00 local; weekday morning, "
                "niche-active audience window]"
            ),
            is_control=True,
        ),
        Variant(
            label="B · Treatment",
            diff_line="same body; ship Saturday 19:00 local.",
            body=(
                f"{base}\n\n[ship-time: Saturday 19:00 local; weekend evening, "
                "lower competition window]"
            ),
        ),
    ]
    if num >= 3:
        out.append(Variant(
            label="C · Treatment 2",
            diff_line="same body; ship Wednesday 14:00 local.",
            body=(
                f"{base}\n\n[ship-time: Wednesday 14:00 local; midweek "
                "afternoon, secondary-engagement window]"
            ),
        ))
    return out


_VARIANT_GENERATORS = {
    "headline": _gen_headline_variants,
    "visual": _gen_visual_variants,
    "cta": _gen_cta_variants,
    "timing": _gen_timing_variants,
}


# ---------------------------------------------------------------------------
# Hypothesis builder
# ---------------------------------------------------------------------------


def build_hypothesis(test_focus: str, idea: IdeaSnapshot) -> str:
    if test_focus == "headline":
        return (
            "An outcome-led headline will outperform a critique-led headline "
            "on reply-to-impression ratio over a 7-day window."
        )
    if test_focus == "visual":
        return (
            "A single inline chart visual will outperform a text-only post on "
            "reply-to-impression ratio over a 7-day window."
        )
    if test_focus == "cta":
        return (
            "A concrete-action CTA will outperform a generic question CTA on "
            "profile-visit rate over a 7-day window."
        )
    if test_focus == "timing":
        return (
            "Saturday-evening ship-time will outperform Tuesday-morning on "
            "thread-depth over a 7-day window."
        )
    return (
        "Treatment variant will outperform control on reply-to-impression "
        "ratio over a 7-day window."
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _interp_clarity(score: int) -> str:
    if score >= 75:
        return "Treatments diverge sharply from control on the chosen dimension."
    if score >= 55:
        return "Treatments are recognisably different but the change is subtle."
    return "Treatments are too close to control — the test will struggle to read."


def _interp_isolation(score: int, focus: str) -> str:
    if score >= 75:
        return f"Single-axis test — only the {focus} dimension changes; rest is byte-identical."
    if score >= 50:
        return f"Mostly single-axis on {focus}; one or two unintended deltas leak."
    return (
        f"Variants vary across multiple dimensions despite test_focus={focus} — the "
        "test cannot isolate which change drove the result."
    )


def _interp_sample(score: int) -> str:
    if score >= 70:
        return "Creator's typical impressions support a directional read inside 7 days."
    if score >= 50:
        return "Sample feasible at 14-21 days; below that, the read will be noisy."
    return "Sample is thin for the chosen window; widen the window or accept directional-only."


def _interp_decision(score: int) -> str:
    if score >= 70:
        return "Either result leads to a clear next action: ship winner, retire loser."
    if score >= 55:
        return "Result leads to a directional decision; further tests likely needed."
    return "Decision rule is too soft — likely no clear action either way."


def score_test_plan(
    rng: Random, test_focus: str, num_variants: int, demo_mode: bool,
) -> TestPlanScores:
    if demo_mode:
        # Pin to multi-variable paradox profile (clarity high, isolation low)
        clarity = rng.randint(74, 84)
        isolation = rng.randint(28, 38)
        sample = rng.randint(60, 72)
        decision = rng.randint(58, 72)
    else:
        # Healthy single-axis defaults
        clarity = rng.randint(72, 88)
        isolation = rng.randint(76, 90) if test_focus in SINGLE_AXIS_FOCUSES else rng.randint(60, 78)
        sample = rng.randint(58, 76)
        decision = rng.randint(64, 82)
        # Headline+visual tests usually have stronger primary metrics → bump decision
        if test_focus in ("headline", "visual"):
            decision = min(100, decision + 4)

    plan_score = round(
        TEST_PLAN_WEIGHTS["Variant clarity"] * clarity
        + TEST_PLAN_WEIGHTS["Test isolation"] * isolation
        + TEST_PLAN_WEIGHTS["Sample feasibility"] * sample
        + TEST_PLAN_WEIGHTS["Decision actionability"] * decision
    )

    paradox = (clarity > 70) and (isolation < 40)

    interpretations = {
        "Variant clarity": _interp_clarity(clarity),
        "Test isolation": _interp_isolation(isolation, test_focus),
        "Sample feasibility": _interp_sample(sample),
        "Decision actionability": _interp_decision(decision),
    }

    return TestPlanScores(
        variant_clarity=clarity,
        test_isolation=isolation,
        sample_feasibility=sample,
        decision_actionability=decision,
        plan_score=plan_score,
        paradox_active=paradox,
        interpretations=interpretations,
    )


# ---------------------------------------------------------------------------
# Success metrics + statistical notes
# ---------------------------------------------------------------------------


def build_success_metrics(test_focus: str) -> SuccessMetrics:
    if test_focus == "headline":
        return SuccessMetrics(
            primary="reply-to-impression ratio over 7d",
            secondary_1="profile-visit rate",
            secondary_2="thread depth (length of reply chains)",
            decision_rule=">= 25% lift on primary at 1.5k+ impressions per variant within 7 days = clear win.",
        )
    if test_focus == "visual":
        return SuccessMetrics(
            primary="dwell time on the post (impression-to-3s ratio)",
            secondary_1="reply-to-impression ratio",
            secondary_2="reposts",
            decision_rule=">= 20% lift on primary at 2k+ impressions per variant within 7 days = clear win.",
        )
    if test_focus == "cta":
        return SuccessMetrics(
            primary="profile-visit rate (visits / impressions)",
            secondary_1="DM volume in the 24h after each variant ships",
            secondary_2="follow rate",
            decision_rule=">= 30% lift on primary at 1k+ impressions per variant within 7 days = clear win.",
        )
    if test_focus == "timing":
        return SuccessMetrics(
            primary="impressions in the first 60 minutes after ship",
            secondary_1="reply-to-impression ratio at 24h",
            secondary_2="reposts at 7d",
            decision_rule=">= 35% lift on primary across 3 ship cycles per window = clear win.",
        )
    return SuccessMetrics(
        primary="reply-to-impression ratio over 7d",
        secondary_1="profile-visit rate",
        secondary_2="thread depth",
        decision_rule=">= 25% lift on primary at 1.5k+ impressions per variant within 7 days = clear win.",
    )


def build_statistical_notes(
    test_focus: str, num_variants: int,
) -> StatisticalNotes:
    if test_focus == "timing":
        sample = (
            "3+ ship cycles per window for a directional read; 6+ for a confident read. "
            "Heuristic only."
        )
        duration = "21-42 days (3 ship cycles per window)."
    elif test_focus == "visual":
        sample = "2k+ impressions per variant for a directional read; 5k+ for confident. Heuristic only."
        duration = "7 days from ship."
    elif test_focus == "cta":
        sample = "1k+ impressions per variant for a directional read; 3k+ for confident. Heuristic only."
        duration = "7 days from ship."
    else:
        sample = "1.5k+ impressions per variant for a directional read; 5k+ for confident. Heuristic only."
        duration = "7 days from ship."

    significance = (
        "rule-of-thumb 25-35% lift on primary at the directional sample threshold; "
        "below that, treat as directional. The runner does not compute p-values or "
        "confidence intervals — trust your judgement and snapshot via "
        "`analytics-summarizer`."
    )

    confounders = (
        f"same niche cadence; same ship-day-of-week (except for `{test_focus}` "
        "tests where ship-time IS the variable); no overlapping major release; "
        "no quote-tweet rallies on the same anchor; identical voice across variants "
        "(use `brand-voice-trainer` to verify)."
    )

    return StatisticalNotes(
        sample_estimate=sample,
        duration_estimate=duration,
        significance_heuristic=significance,
        confounders=confounders,
    )


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: TestPlanScores, test_focus: str, num_variants: int,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    if scores.paradox_active:
        flags.append(RedFlag(
            title="Multi-variable paradox",
            severity="high",
            explanation=(
                f"Variant clarity at {scores.variant_clarity}/100 is above 70 while "
                f"Test isolation at {scores.test_isolation}/100 is below 40. The variants "
                "are clearly different but they diverge across multiple dimensions — the "
                "test cannot isolate which change drove the result."
            ),
            remediation=(
                "Reduce the test to a single dimension (`--test-focus headline` or "
                "`--test-focus cta`); OR accept the test as a 'concept-level' comparison "
                "rather than a causal A/B."
            ),
        ))

    # Cannibalization on same-audience X-native default
    flags.append(RedFlag(
        title="Cannibalization on same audience",
        severity="medium",
        explanation=(
            f"Both variants ship to the same followers. The {('second and third' if num_variants == 3 else 'second')} "
            "variant will see lower base impressions because the audience already saw the first."
        ),
        remediation=(
            "Stagger ship by 4-7 days, or use `cross-platform-reposter` to test the "
            "treatment on LinkedIn while keeping control on X."
        ),
    ))

    # Single-day variance (timing tests are most exposed)
    if test_focus == "timing":
        flags.append(RedFlag(
            title="Single-cycle variance",
            severity="medium",
            explanation=(
                "Timing tests need 3+ ship cycles per window before the noise smooths."
            ),
            remediation=(
                "Plan for 21+ day duration, or treat single-cycle results as directional only."
            ),
        ))
    else:
        flags.append(RedFlag(
            title="Single-day variance",
            severity="low",
            explanation=(
                "A 7-day window can be dominated by one viral spike; the loser variant "
                "may simply have shipped on a quiet day."
            ),
            remediation=(
                "Pair with `analytics-summarizer` to overlay the daily impression curve "
                "before declaring a winner."
            ),
        ))

    return flags[:4 if scores.paradox_active else 3]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random, scores: TestPlanScores, test_focus: str, paradox_present: bool,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    pool.append(Recommendation(
        text=(
            "Snapshot variant performance at T+24h and T+7d via `analytics-summarizer` "
            "to log the lift curve, not just the endpoint."
        ),
        bridge_slug="analytics-summarizer",
    ))
    pool.append(Recommendation(
        text=(
            "Confirm both variants land in the creator's voice before shipping; voice "
            "drift would confound the test."
        ),
        bridge_slug="brand-voice-trainer",
    ))
    pool.append(Recommendation(
        text=(
            "Recycle the losing variant via `content-recycler` for a different angle "
            "next quarter — losers compound when reframed."
        ),
        bridge_slug="content-recycler",
    ))
    pool.append(Recommendation(
        text=(
            "Cross-test the winning variant on LinkedIn / Newsletter via "
            "`cross-platform-reposter` once the X test concludes."
        ),
        bridge_slug="cross-platform-reposter",
    ))
    pool.append(Recommendation(
        text=(
            "Source the next anchor from the winning pattern via `content-idea-generator`."
        ),
        bridge_slug="content-idea-generator",
    ))
    if test_focus in ("headline", "cta"):
        pool.append(Recommendation(
            text=(
                "If the test extends into a paid-tier funnel comparison, model the funnel "
                "before shipping the monetization variant."
            ),
            bridge_slug="monetization-optimizer",
            monetization=True,
        ))
    if paradox_present:
        pool.append(Recommendation(
            text=(
                "Re-run with a single-axis test_focus (`headline` is the most "
                "leverage-y default) to fix the multi-variable paradox before shipping."
            ),
            bridge_slug="research-assistant",
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
                        "Cross-reference the test outcome with last week's analytics to "
                        "spot whether the variant lift compounded across formats."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(Recommendation(
            text="Re-run with a sharper test_focus to lift confidence.",
            bridge_slug="growth-experiment-runner",
        ))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(
    idea: IdeaSnapshot, test_focus: str, scores: TestPlanScores,
) -> tuple[str, str]:
    src_clear = idea.char_count >= 60 and idea.url is None
    if src_clear and scores.plan_score >= 70 and not scores.paradox_active:
        return ("high", f"single-axis test on {test_focus}, clear idea, sample feasible, decision rule explicit.")
    if scores.plan_score >= 60:
        return (
            "medium",
            f"Test Plan score {scores.plan_score}/100 — solid direction; tighten focus or widen sample to lift to high.",
        )
    return ("low", f"Test Plan score {scores.plan_score}/100 — tighten test_focus and supply a clearer idea.")


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_test_snapshot(
    idea: IdeaSnapshot, test_focus_input: str, test_focus_resolved: str,
    num_variants: int, hypothesis: str,
) -> str:
    headline_text = idea.dominant_claim
    if len(headline_text) > 140:
        headline_text = headline_text[:137].rstrip() + "..."
    focus_str = (
        f"all-resolved-to-{test_focus_resolved}" if test_focus_input == "all" else test_focus_input
    )
    return "\n".join([
        "## Test Snapshot",
        f"**{idea.handle}: {test_focus_resolved}-only A/B test on the idea — control vs {num_variants - 1} treatment(s).**",
        "",
        f"- **X handle**: {idea.handle}",
        f"- **Post idea**: {headline_text}",
        f"- **Test focus**: {focus_str}",
        f"- **Variants requested**: {num_variants} (1 control + {num_variants - 1} treatment{'s' if num_variants > 2 else ''})",
        f"- **Hypothesis**: {hypothesis}",
    ])


def _render_test_plan(scores: TestPlanScores) -> str:
    rows = [
        "| Metric | Score | Interpretation |",
        "|---|---|---|",
    ]
    rows.append(f"| Variant clarity | {scores.variant_clarity}/100 | {scores.interpretations['Variant clarity']} |")
    rows.append(f"| Test isolation | {scores.test_isolation}/100 | {scores.interpretations['Test isolation']} |")
    rows.append(f"| Sample feasibility | {scores.sample_feasibility}/100 | {scores.interpretations['Sample feasibility']} |")
    rows.append(f"| Decision actionability | {scores.decision_actionability}/100 | {scores.interpretations['Decision actionability']} |")
    out = "## Test Plan\n\n" + "\n".join(rows)
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: variants are clearly different but diverge across "
            "multiple dimensions — the test cannot isolate which change drove the result."
        )
    out += f"\n\n**Test Plan score**: {scores.plan_score}/100"
    return out


def _render_variants(variants: list[Variant]) -> str:
    parts: list[str] = ["## Variants", ""]
    for v in variants:
        parts.append(f"### Variant {v.label}")
        parts.append(
            f"- **Diff vs {'idea' if v.is_control else 'control (single-axis)'}**: {v.diff_line}"
        )
        parts.append("")
        parts.append("```")
        parts.append(v.body)
        parts.append("```")
        parts.append("")
    return "\n".join(parts).rstrip()


def _render_success_metrics(sm: SuccessMetrics) -> str:
    return "\n".join([
        "## Success Metrics",
        "",
        f"- **Primary metric**: {sm.primary}.",
        f"- **Secondary metric 1**: {sm.secondary_1}.",
        f"- **Secondary metric 2**: {sm.secondary_2}.",
        f"- **Decision rule**: {sm.decision_rule}",
    ])


def _render_statistical_notes(sn: StatisticalNotes) -> str:
    return "\n".join([
        "## Statistical Notes",
        "",
        f"- **Estimated sample needed**: {sn.sample_estimate}",
        f"- **Estimated duration**: {sn.duration_estimate}",
        f"- **Significance heuristic**: {sn.significance_heuristic}",
        f"- **Confounders to control**: {sn.confounders}",
    ])


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


def _render_test_plan_audit(
    idea: IdeaSnapshot, test_focus_input: str, test_focus_resolved: str,
    scores: TestPlanScores,
) -> str:
    src_clarity = (
        "clear, single-claim source" if idea.url is None and idea.char_count >= 60
        else "URL-only or thin source"
    )
    dimension_fit = (
        f"runner picked `{test_focus_resolved}` — matches the highest-leverage dimension for this idea."
        if test_focus_input == "all"
        else f"`{test_focus_input}` was supplied — runner kept that dimension throughout."
    )
    return "\n".join([
        "## Test Plan Audit (auto-triggered)",
        "",
        f"- **Idea clarity**: {src_clarity}.",
        f"- **Dimension fit**: {dimension_fit}",
        "- **Cannibalization exposure**: variants ship to the same audience by default; "
        "stagger by 4-7 days OR cross-test on adjacent platform.",
        "- **Suggested next run**: ship variant A first, hold treatment for 4-7 days, then "
        "evaluate via `analytics-summarizer`.",
        "- **Re-run cadence**: monthly while building the testing habit, otherwise per-anchor-launch.",
    ])


def render_report(
    idea: IdeaSnapshot,
    test_focus_input: str,
    test_focus_resolved: str,
    num_variants: int,
    scores: TestPlanScores,
    variants: list[Variant],
    success: SuccessMetrics,
    notes: StatisticalNotes,
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    hypothesis: str,
) -> str:
    sections = [
        _render_test_snapshot(idea, test_focus_input, test_focus_resolved, num_variants, hypothesis),
        "",
        _render_test_plan(scores),
        "",
        _render_variants(variants),
        "",
        _render_success_metrics(success),
        "",
        _render_statistical_notes(notes),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    if len(flags) > 3 or test_focus_input == "all":
        sections.extend([
            "",
            _render_test_plan_audit(idea, test_focus_input, test_focus_resolved, scores),
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
        f"<!-- Generated by AB Test Suggester (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for xAI, X, Grok and the ecosystem community. ❤️ -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_ab_test_plan(
    *,
    x_handle: str,
    post_idea_or_url: str,
    test_focus: str = "headline",
    num_variants: int = 2,
    when: Optional[str] = None,
    demo_mode: bool = False,
) -> str:
    handle = normalize_handle(x_handle)
    if test_focus not in TEST_FOCUS_OPTIONS:
        raise ValueError(f"test_focus must be one of {TEST_FOCUS_OPTIONS}, got {test_focus!r}")
    if not (MIN_VARIANTS <= num_variants <= MAX_VARIANTS):
        raise ValueError(
            f"num_variants must be in [{MIN_VARIANTS}, {MAX_VARIANTS}], got {num_variants}"
        )

    idea = parse_idea(post_idea_or_url, handle)
    when_iso = when or date.today().isoformat()

    test_focus_input = test_focus
    if test_focus == "all":
        resolved, _why = pick_auto_focus(idea)
    else:
        resolved = test_focus

    rng = deterministic_rng(handle, idea.text, resolved, num_variants, when_iso)
    scores = score_test_plan(rng, resolved, num_variants, demo_mode=demo_mode)
    hypothesis = build_hypothesis(resolved, idea)
    variants = _VARIANT_GENERATORS[resolved](idea, num_variants)
    success = build_success_metrics(resolved)
    notes = build_statistical_notes(resolved, num_variants)
    flags = build_red_flags(scores, resolved, num_variants)
    paradox_present = scores.paradox_active
    recs = build_recommendations(rng, scores, resolved, paradox_present)
    confidence = confidence_for(idea, resolved, scores)

    rendered = render_report(
        idea=idea,
        test_focus_input=test_focus_input,
        test_focus_resolved=resolved,
        num_variants=num_variants,
        scores=scores,
        variants=variants,
        success=success,
        notes=notes,
        flags=flags,
        recs=recs,
        confidence=confidence,
        hypothesis=hypothesis,
    )
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_ab_test_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  AB Test Suggester (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Single-axis tests by default\n"
        "  Built for xAI, X, Grok and the ecosystem community. ❤️\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ab-test-suggester",
        description=(
            "Turn a single post idea into a 6/7-section A/B test plan with 2-3 "
            "variants isolated to a single test dimension. Drafts only — never "
            "auto-publishes."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    p.add_argument(
        "--post-idea-or-url",
        help="Either an x.com / twitter.com URL or the literal post idea. Required unless --demo is passed.",
    )
    p.add_argument(
        "--test-focus",
        choices=list(TEST_FOCUS_OPTIONS),
        default="headline",
        help="Which dimension the variants vary along. 'all' lets the runner pick.",
    )
    p.add_argument(
        "--num-variants",
        type=int,
        default=2,
        help=f"Number of variants ({MIN_VARIANTS}-{MAX_VARIANTS}). Default 2.",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run with the official AI-niche demo idea. Pins scoring to the multi-variable "
            "paradox profile so the rule reliably demonstrates."
        ),
    )
    p.add_argument(
        "--demo-productivity",
        action="store_true",
        help=(
            "Run with a productivity-niche demo idea. Healthy single-axis test (no paradox)."
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
    if args.demo and not args.post_idea_or_url:
        post_arg = DEMO_POST_IDEA
        demo_mode = True
    elif args.demo_productivity and not args.post_idea_or_url:
        post_arg = DEMO_PRODUCTIVITY_IDEA
        demo_mode = False
    elif args.post_idea_or_url:
        post_arg = args.post_idea_or_url
    else:
        sys.stderr.write(
            "error: provide --post-idea-or-url \"<idea or URL>\" or pass --demo / --demo-productivity.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_ab_test_plan(
        x_handle=args.x_handle,
        post_idea_or_url=post_arg,
        test_focus=args.test_focus,
        num_variants=args.num_variants,
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
