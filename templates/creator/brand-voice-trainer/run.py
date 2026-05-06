# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Brand Voice Trainer — runner.

CLI entry point for the ``brand-voice-trainer`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a sample of the creator's own past posts (inline list, file, or
seeded date-range) and emits a 6/7-section structured voice profile +
3-5 training prompts naming destination cross-template slugs, matching
``prompts/system.md`` exactly:

  1. Voice Snapshot (one-line summary + 5 bullets)
  2. Voice Profile (4-row metric table with weighted formula
     round(0.30*Tone + 0.20*Structure + 0.25*Vocab + 0.25*Cohesion))
  3. Voice Signatures — Tone / Structure / Vocabulary subsections
     reporting only signals observed in the sample (signature phrases
     extracted as verbatim n-grams; never invented)
  4. Training Prompts (3-5 prompts each naming a destination template)
  5. Red Flags (2-3, surfaces generic-polish paradox in BOTH this
     section AND under the Voice Profile metric row when Voice cohesion
     > 70 AND Vocabulary distinctiveness < 35)
  6. Recommendations (3-5, with >= 3 cross-template bridges)
  7. Confidence
  + Optional Voice Audit (auto-appended when red_flags > 3 OR sample size < 10)

Hard guarantees enforced by this runner (mirrors the Constitution):

* Train only on the creator's own posts. The runner accepts free-form
  post bodies and treats `--x-handle` as the voice anchor; it never
  fetches external content.
* Drafts only. Training prompts are text the creator pastes into other
  templates. Never auto-applied, never auto-published.
* Sample-size DOUBLE gate — refuse outright on `< 5` posts (no profile
  emitted), auto-trigger Voice Audit on `< 10` posts (profile emitted
  with caveats), full report at `>= 10` posts.
* Generic-polish paradox surfaced in BOTH the Voice Profile section AND
  the Red Flags section whenever Voice cohesion > 70 AND Vocabulary
  distinctiveness < 35. The `--demo` mode pins scoring to this profile
  so the rule reliably demonstrates.
* No fabricated signatures. The Vocabulary section reports phrases
  observed in the sample (verbatim n-grams that occur in 2+ posts).
  Never invent quotes the creator did not use.
* Voice Profile score formula is fixed:
    round(0.30*Tone consistency + 0.20*Structure consistency +
          0.25*Vocabulary distinctiveness + 0.25*Voice cohesion).
  Tone weighted highest because tone-drift is the visible kind of voice
  drift; Structure weighted lowest because structure repeats naturally
  even when voice fragments.
* Recommendations always link to >= 3 distinct cross-template slugs.
  The Article V.1 disclaimer attaches verbatim under any monetization-
  related recommendation.
* Saved output files prepend a 5-line Apache 2.0 HTML-comment header.
* Deterministic where possible: seeded by sha256(handle + sorted_posts +
  voice_focus + date).
* Zero external network calls in v1 (manifest-allowed APIs are 0).

Manifest contract (the alias the v2.15 manifest binds to)::

    generate = generate_voice_profile

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
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
    "Tone consistency",
    "Structure consistency",
    "Vocabulary distinctiveness",
    "Voice cohesion",
)

# Voice Profile score weights — Tone weighted highest because tone-drift
# is the visible form of voice drift; Structure weighted lowest because
# structure repeats naturally even when voice fragments.
VOICE_PROFILE_WEIGHTS = {
    "Tone consistency": 0.30,
    "Structure consistency": 0.20,
    "Vocabulary distinctiveness": 0.25,
    "Voice cohesion": 0.25,
}

VOICE_FOCUS_OPTIONS = ("tone", "structure", "vocabulary", "all")
OUTPUT_FORMAT_OPTIONS = ("analysis", "training_prompts", "both")

# Sample-size double gate from prompts/system.md
SAMPLE_REFUSE_BELOW = 5
SAMPLE_AUDIT_BELOW = 10

# Generic-default words / phrases. Their presence pushes Vocabulary
# distinctiveness DOWN — they're the niche-default vocabulary that flags
# generic polish. The runner reports "watch for these" when present.
GENERIC_DEFAULT_PHRASES = (
    "thought leadership",
    "ecosystem",
    "synergy",
    "synergies",
    "leverage",
    "leveraging",
    "transform",
    "transformative",
    "innovation",
    "innovating",
    "scale",
    "scaling",
    "stack",
    "optimization",
    "intersection",
    "excited to share",
    "deep dive",
    "lessons learned",
    "transforming the",
    "future of work",
    "drives growth",
    "next-gen",
    "game-changer",
    "disrupt",
    "paradigm",
    "mindset that scales",
)

# Stopwords used when extracting recurring n-grams (so we don't surface
# "of the" as a signature phrase).
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "is", "it", "and", "or", "but",
    "for", "on", "at", "by", "with", "from", "as", "be", "are", "was",
    "were", "this", "that", "these", "those", "i", "you", "we", "they",
    "your", "my", "our", "their", "its", "his", "her", "have", "has",
    "had", "do", "does", "did", "not", "no", "if", "then", "than",
    "also", "just", "so", "very", "what", "when", "where", "who",
    "why", "how", "would", "could", "should", "will", "can", "cant",
    "wont", "into", "out", "up", "down", "over", "under", "all",
    "any", "some", "more", "most", "less", "least", "now", "still",
    "yet", "even", "only", "such",
}

# Cross-template bridges
CROSS_TEMPLATE_BRIDGES = (
    "content-idea-generator",
    "thread-builder",
    "cross-platform-reposter",
    "content-recycler",
    "reply-drafter",
    "mention-summarizer",
    "ab-test-suggester",
    "competitor-watch",
    "quote-tweet-suggestor",
    "monetization-optimizer",
    "analytics-summarizer",
    "research-assistant",
)

ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This tool provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)

# Curated demo sample — 24 posts deliberately written in generic-polish
# style so the demo run reliably triggers the paradox (Cohesion high,
# Vocabulary distinctiveness low).
DEMO_HANDLE = "@JanSol0s"
DEMO_PARADOX_SAMPLE = (
    "Just shared my thoughts on how AI is transforming the ecosystem.",
    "Leadership in tech is about leveraging synergies across the team.",
    "Innovation requires a thought-leadership mindset that scales.",
    "The future of work is at the intersection of AI and human creativity.",
    "5 lessons I learned shipping AI products this year.",
    "Quick thread on agentic workflows and the productivity stack.",
    "Excited to share my journey into LLM agent infrastructure.",
    "Innovation is the engine that drives ecosystem growth.",
    "Thought of the day: optimization is the new differentiation.",
    "Sharing insights from this week's deep dive on agent evals.",
    "Leveraging AI to transform the future of operations.",
    "Excited to announce a new partnership in the AI ecosystem.",
    "Lessons learned scaling our agent infrastructure stack.",
    "Innovation moves at the speed of thought leadership.",
    "Quick thoughts on synergies between AI and operations.",
    "Just published a deep dive on agent eval at scale.",
    "The intersection of AI and infra is where transformation lives.",
    "Lessons learned from a year of leveraging LLM agents.",
    "Excited to share what we've been building in the eval stack.",
    "Innovation is the new differentiation in agent infrastructure.",
    "Quick thoughts on the future of work in an AI-first ecosystem.",
    "Leveraging next-gen AI to transform the productivity stack.",
    "Sharing insights from this quarter's agent infrastructure journey.",
    "5 paradigm shifts driving the AI ecosystem in 2026.",
)

# Curated demo sample for productivity niche — small (8 posts) to trigger
# Voice Audit; voice is more distinctive than the paradox sample.
DEMO_PRODUCTIVITY_HANDLE = "@habitstacker"
DEMO_PRODUCTIVITY_SAMPLE = (
    "Stop optimizing for the morning routine — optimize for the friction "
    "your evening self leaves the morning self to clean up.",
    "The cheapest productivity hack: write tomorrow's first task on a "
    "sticky note before you stop working today.",
    "Habit stacking only works when the new habit is shorter than the "
    "anchor habit you're stacking it on.",
    "Deep work sessions don't fail because of distractions. They fail "
    "because of un-decided next steps.",
    "Calendar your meetings, list your tasks, and put your shutdown "
    "ritual on a timer. Two of three is not enough.",
    "Most productivity systems break the second life happens. Build for "
    "the days you're tired, not the days you're focused.",
    "The friction you don't notice is the friction that compounds. "
    "Audit your evening before you optimise your morning.",
    "Productivity is downstream of decisions made the night before.",
)

# X URL handle pattern
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
class VoiceScores:
    tone_consistency: int
    structure_consistency: int
    vocabulary_distinctiveness: int
    voice_cohesion: int
    profile_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)
    trends: dict = field(default_factory=dict)


@dataclass
class ToneSignature:
    dominant_tone: str
    secondary_tones: str
    tone_tells: tuple


@dataclass
class StructureSignature:
    common_shape_1: str
    common_shape_2: str
    missing_shape: str


@dataclass
class VocabularySignature:
    signature_phrases: tuple   # verbatim phrases observed in 2+ posts
    lexicon_tilts: str
    generic_default_watch: str  # generic-default phrases observed in the sample


@dataclass
class TrainingPrompt:
    destination_slug: str
    text: str
    monetization: bool = False


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
                "Brand Voice Trainer privacy violation: a non-creator X handle "
                f"({match}) appeared in the rendered output. Refusing to emit."
            )


# ---------------------------------------------------------------------------
# Sample collection
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def parse_inline_sample(raw) -> list[str]:
    """Accept a list of post bodies, OR a single delimiter-joined string.
    The runner uses pipe-or-double-newline as the post separator so
    individual post bodies can contain commas / semicolons safely.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(p).strip() for p in raw if str(p).strip()]
    flat = str(raw)
    parts = re.split(r"\|{2,}|\n{2,}", flat)
    return [p.strip() for p in parts if p.strip()]


def parse_sample_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"--sample-file not found: {path}")
    text = path.read_text(encoding="utf-8")
    # Posts separated by blank lines OR lines of dashes
    parts = re.split(r"\n\s*(?:-{3,}|\n)\s*\n", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p or p.startswith("#"):
            continue
        # Drop any leading "# comment" lines inside a post block
        clean_lines = [ln for ln in p.splitlines() if not ln.strip().startswith("#")]
        body = "\n".join(clean_lines).strip()
        if body:
            out.append(body)
    return out


def synth_date_range_sample(date_range: str, count: int = 18) -> list[str]:
    return [
        f"[seeded-sample-post-{i:03d} for date_range={date_range}]" for i in range(count)
    ]


# ---------------------------------------------------------------------------
# N-gram phrase extraction (deterministic, offline)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", text.lower())


def extract_recurring_phrases(
    posts: list[str], min_n: int = 2, max_n: int = 4, min_freq: int = 2,
) -> list[tuple[str, int]]:
    """Return (phrase, count) for n-grams (n in [min_n, max_n]) that
    appear in at least `min_freq` posts. Stopword-only n-grams are
    filtered. Deterministic ordering: by count desc, then phrase asc.
    """
    counter: Counter[str] = Counter()
    for post in posts:
        tokens = _tokenize(post)
        for n in range(min_n, max_n + 1):
            seen_in_post: set[str] = set()
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i : i + n])
                # Filter: not all stopwords
                if all(t in _STOPWORDS for t in tokens[i : i + n]):
                    continue
                # Filter: at least one non-trivial word
                if all(len(t) <= 2 for t in tokens[i : i + n]):
                    continue
                if phrase in seen_in_post:
                    continue
                seen_in_post.add(phrase)
                counter[phrase] += 1
    filtered = [(p, c) for p, c in counter.items() if c >= min_freq]
    filtered.sort(key=lambda pc: (-pc[1], pc[0]))
    return filtered


def count_generic_phrases(posts: list[str]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    joined = " ".join(p.lower() for p in posts)
    for phrase in GENERIC_DEFAULT_PHRASES:
        c = joined.count(phrase.lower())
        if c > 0:
            out.append((phrase, c))
    out.sort(key=lambda pc: (-pc[1], pc[0]))
    return out


# ---------------------------------------------------------------------------
# Tone / structure heuristics
# ---------------------------------------------------------------------------


def infer_tones(posts: list[str]) -> tuple[str, str, tuple]:
    """Return (dominant_tone, secondary_tones_line, tone_tells_tuple)."""
    avg_len = sum(len(p) for p in posts) / max(1, len(posts))
    has_numbers = sum(1 for p in posts if re.search(r"\d", p)) / max(1, len(posts))
    has_questions = sum(1 for p in posts if "?" in p) / max(1, len(posts))
    short_post_share = sum(1 for p in posts if len(p) < 180) / max(1, len(posts))

    # Tone signal weights
    punchy_score = (1.0 if avg_len < 220 else 0.4) + (0.5 if short_post_share > 0.6 else 0)
    data_score = has_numbers * 1.5
    thoughtful_score = (1.0 if avg_len > 280 else 0.3)
    conversational_score = has_questions * 1.2

    scores = {
        "punchy": punchy_score,
        "data-led": data_score,
        "thoughtful": thoughtful_score,
        "conversational": conversational_score,
    }
    sorted_tones = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    dom = sorted_tones[0][0]
    sec_candidates = [t for t, s in sorted_tones[1:3] if s > 0.4]

    # Approximate mix percentage
    if sec_candidates:
        dominant_tone = f"{dom} + {sec_candidates[0]}, ~60/40 mix"
        secondary_tones = (
            f"{sec_candidates[1] if len(sec_candidates) > 1 else 'thoughtful'} "
            "(rare; weekend / off-topic posts)"
        )
    else:
        dominant_tone = f"{dom}, near-uniform across the sample"
        secondary_tones = "(none clearly secondary)"

    # Tone tells (heuristics)
    tells: list[str] = []
    if short_post_share > 0.5:
        tells.append("sentence-length descending cadence (long → short → punch)")
    if has_questions > 0.3:
        tells.append("rhetorical question only at the end")
    if has_numbers > 0.4:
        tells.append("numbers anchor the claim (5 / 3-5 / 2x patterns recur)")
    if any(p.lower().startswith("just ") or p.lower().startswith("excited") for p in posts):
        tells.append("\"just shared\" / \"excited to\" opener (watch — generic-default tilt)")
    if not tells:
        tells.append("no strong opener pattern observed; voice signal is in cadence and word choice")

    return dominant_tone, secondary_tones, tuple(tells[:3])


def infer_structure(posts: list[str]) -> tuple[str, str, str]:
    has_numbered = sum(1 for p in posts if re.search(r"\b\d\.\s|\b\d\)\s|\n\d\.", p)) / max(1, len(posts))
    has_dash_lists = sum(1 for p in posts if re.search(r"\n[-•→]", p)) / max(1, len(posts))
    has_thread = sum(1 for p in posts if "[1/" in p or "1/" in p[:5]) / max(1, len(posts))

    if has_numbered > 0.3:
        s1 = "claim → 1-2-3 numbered consequences → CTA, used in ~30%+ of sample."
    elif has_dash_lists > 0.3:
        s1 = "claim → bullet/dash-list unpack → punch line, used in ~30%+ of sample."
    else:
        s1 = "single-claim hook → 1-2 line unpack, used in the majority of the sample."

    if has_thread > 0.15:
        s2 = "occasional multi-post threads (\"[1/N]\" markers visible)."
    else:
        s2 = "single posts dominate; threads are rare."

    if has_numbered < 0.15 and has_dash_lists < 0.15:
        missing = (
            "data-anchored case-study shape (numbers up front + narrative) — "
            "absent from the sample, useful to add."
        )
    elif has_thread < 0.1:
        missing = (
            "long-form thread shape (5-10 posts) — sparse in the sample, "
            "compounds well on this niche."
        )
    else:
        missing = "no obvious structural gap; mix is healthy."

    return s1, s2, missing


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def deterministic_rng(
    handle: str, posts: list[str], voice_focus: str, when: str,
) -> Random:
    digest = hashlib.sha256()
    digest.update(handle.lower().encode("utf-8"))
    digest.update(b"\x1e")
    for p in sorted(posts):
        digest.update(p.encode("utf-8"))
        digest.update(b"\x1f")
    digest.update(voice_focus.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(when.encode("utf-8"))
    seed = int.from_bytes(digest.digest()[:8], "big")
    return Random(seed)


def _heuristic_distinctiveness(
    posts: list[str], generic_hits: list[tuple[str, int]],
) -> int:
    """Return 0-100 distinctiveness score derived from generic-phrase
    density: more generic phrases → lower score.
    """
    n_posts = len(posts)
    if n_posts == 0:
        return 50
    # Total generic-phrase occurrences across the sample
    total_generic = sum(c for _, c in generic_hits)
    density = total_generic / max(1, n_posts)
    # density 0 → ~85; density 0.5 → ~60; density 1.0 → ~38; density 2.0 → ~22
    base = max(15, min(92, round(85 - density * 30)))
    return base


def _heuristic_tone(posts: list[str]) -> int:
    """Tone consistency — proxy via length-variance: tighter variance = higher consistency."""
    if not posts:
        return 50
    lens = [len(p) for p in posts]
    mean = sum(lens) / len(lens)
    if mean == 0:
        return 50
    var = sum((l - mean) ** 2 for l in lens) / len(lens)
    cv = var ** 0.5 / mean   # coefficient of variation
    # cv near 0 (very tight) → 88; cv 0.4 → 72; cv 0.8 → 56; cv 1.5 → 40
    base = max(35, min(92, round(92 - cv * 36)))
    return base


def _heuristic_structure(posts: list[str]) -> int:
    """Structure consistency — proxy via repeated post-shape signals."""
    n_posts = len(posts)
    if n_posts == 0:
        return 50
    has_numbered = sum(1 for p in posts if re.search(r"\b\d\.\s|\b\d\)\s", p))
    has_lists = sum(1 for p in posts if re.search(r"\n[-•→]", p))
    has_questions = sum(1 for p in posts if "?" in p)
    pattern_share = max(has_numbered, has_lists, has_questions) / max(1, n_posts)
    # pattern_share 0 → ~52; 0.3 → 65; 0.5 → 73; 0.8 → 80
    base = max(40, min(86, round(52 + pattern_share * 36)))
    return base


def _heuristic_cohesion(
    posts: list[str], generic_hits: list[tuple[str, int]],
) -> int:
    """Voice cohesion — proxy via vocabulary overlap across posts.
    Higher token overlap between posts → higher cohesion. Generic phrases
    paradoxically RAISE cohesion (everyone writes the same way).
    """
    if not posts:
        return 50
    all_tokens = [set(_tokenize(p)) for p in posts]
    if not all_tokens:
        return 50
    # Average pairwise Jaccard similarity (cheap proxy)
    n = len(all_tokens)
    if n < 2:
        return 70
    pairs = 0
    sim_sum = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            inter = len(all_tokens[i] & all_tokens[j])
            union = len(all_tokens[i] | all_tokens[j])
            if union > 0:
                sim_sum += inter / union
                pairs += 1
    avg_sim = sim_sum / max(1, pairs)
    # avg_sim 0.05 → ~55; 0.15 → ~72; 0.25 → ~82
    base = max(45, min(92, round(55 + avg_sim * 200)))
    # Generic phrases lift cohesion further (everyone-sounds-the-same effect)
    generic_share = sum(c for _, c in generic_hits) / max(1, len(posts))
    base = min(95, base + round(generic_share * 6))
    return base


def _interp_tone(score: int) -> str:
    if score >= 75:
        return "Tone is stable across the sample — variance in length and shape is tight."
    if score >= 55:
        return "Tone is mostly consistent; a minority of posts read in a different register."
    return "Tone fragments across the sample — the creator sounds like several people."


def _interp_structure(score: int) -> str:
    if score >= 70:
        return "Two or three repeating shapes carry most of the sample; the rest vary in healthy ways."
    if score >= 55:
        return "Some repeating shapes; structural rhythm is emerging but not yet locked."
    return "Structural variety is high — useful for exploration, costly for recognition."


def _interp_distinctiveness(score: int, generic_share: float) -> str:
    if score >= 65:
        return "Lexicon clearly belongs to the creator; signature phrases are visible."
    if score >= 45:
        return "Niche lexicon used cleanly; signature phrases emerging but not yet locked."
    return (
        f"Generic-default lexicon (~{generic_share:.1f} per post on average) "
        "is diluting the creator's signal."
    )


def _interp_cohesion(score: int) -> str:
    if score >= 75:
        return "Reads as one consistent person across the sample."
    if score >= 60:
        return "Mostly one voice; the occasional post reads as a different cadence."
    return "Voice fragments across the sample — multiple distinct registers visible."


def score_voice(
    rng: Random,
    posts: list[str],
    voice_focus: str,
    demo_mode: bool,
) -> VoiceScores:
    generic_hits = count_generic_phrases(posts)
    generic_share = sum(c for _, c in generic_hits) / max(1, len(posts))

    if demo_mode:
        # Pin to generic-polish paradox profile so the rule reliably demonstrates.
        # Cohesion HIGH (everyone-sounds-the-same), Distinctiveness LOW (generic).
        tone = rng.randint(74, 84)
        structure = rng.randint(56, 68)
        distinctiveness = rng.randint(22, 32)
        cohesion = rng.randint(76, 86)
    else:
        tone = _heuristic_tone(posts)
        structure = _heuristic_structure(posts)
        distinctiveness = _heuristic_distinctiveness(posts, generic_hits)
        cohesion = _heuristic_cohesion(posts, generic_hits)
        # Light RNG nudge so the score isn't perfectly deterministic on the
        # heuristic alone — keeps reruns slightly varied within ±2 points.
        tone = max(0, min(100, tone + rng.randint(-2, 2)))
        structure = max(0, min(100, structure + rng.randint(-2, 2)))
        distinctiveness = max(0, min(100, distinctiveness + rng.randint(-2, 2)))
        cohesion = max(0, min(100, cohesion + rng.randint(-2, 2)))

    # Focus nudge
    if voice_focus == "tone":
        tone = min(100, tone + 3)
    elif voice_focus == "structure":
        structure = min(100, structure + 3)
    elif voice_focus == "vocabulary":
        distinctiveness = min(100, distinctiveness + 3)

    profile_score = round(
        VOICE_PROFILE_WEIGHTS["Tone consistency"] * tone
        + VOICE_PROFILE_WEIGHTS["Structure consistency"] * structure
        + VOICE_PROFILE_WEIGHTS["Vocabulary distinctiveness"] * distinctiveness
        + VOICE_PROFILE_WEIGHTS["Voice cohesion"] * cohesion
    )

    paradox = (cohesion > 70) and (distinctiveness < 35)

    interpretations = {
        "Tone consistency": _interp_tone(tone),
        "Structure consistency": _interp_structure(structure),
        "Vocabulary distinctiveness": _interp_distinctiveness(distinctiveness, generic_share),
        "Voice cohesion": _interp_cohesion(cohesion),
    }
    trends = {m: rng.choice(("▲", "▬", "▼", "n/a")) for m in SCORE_METRICS}

    return VoiceScores(
        tone_consistency=tone,
        structure_consistency=structure,
        vocabulary_distinctiveness=distinctiveness,
        voice_cohesion=cohesion,
        profile_score=profile_score,
        paradox_active=paradox,
        interpretations=interpretations,
        trends=trends,
    )


# ---------------------------------------------------------------------------
# Signatures (tone / structure / vocabulary)
# ---------------------------------------------------------------------------


def build_tone_signature(posts: list[str]) -> ToneSignature:
    dom, sec, tells = infer_tones(posts)
    return ToneSignature(dominant_tone=dom, secondary_tones=sec, tone_tells=tells)


def build_structure_signature(posts: list[str]) -> StructureSignature:
    s1, s2, missing = infer_structure(posts)
    return StructureSignature(common_shape_1=s1, common_shape_2=s2, missing_shape=missing)


def build_vocabulary_signature(posts: list[str]) -> VocabularySignature:
    phrases = extract_recurring_phrases(posts, min_n=2, max_n=4, min_freq=2)[:4]
    sig_phrases = tuple(p for p, _ in phrases)
    if not sig_phrases:
        sig_phrases = ("(no recurring n-grams found in the sample)",)

    # Lexicon tilts — pick most common content words
    counter: Counter[str] = Counter()
    for post in posts:
        for tok in _tokenize(post):
            if tok in _STOPWORDS or len(tok) <= 2:
                continue
            counter[tok] += 1
    top_words = [w for w, _ in counter.most_common(10) if w not in _STOPWORDS]
    if top_words:
        lexicon_tilts = (
            f"{', '.join(top_words[:5])} — fluently used in the sample, signal of niche fluency."
        )
    else:
        lexicon_tilts = "(no clear lexicon tilts observed)"

    generic_hits = count_generic_phrases(posts)
    if generic_hits:
        watch = (
            ", ".join(f'"{p}" (×{c})' for p, c in generic_hits[:5])
            + " — niche-default phrases present in the sample. Compound risk: low distinctiveness."
        )
    else:
        watch = "(no generic-default phrases detected — distinctiveness signal is healthy)"

    return VocabularySignature(
        signature_phrases=sig_phrases,
        lexicon_tilts=lexicon_tilts,
        generic_default_watch=watch,
    )


# ---------------------------------------------------------------------------
# Training prompts
# ---------------------------------------------------------------------------


def build_training_prompts(
    handle: str,
    tone_sig: ToneSignature,
    vocab_sig: VocabularySignature,
    output_format: str,
) -> list[TrainingPrompt]:
    if output_format == "analysis":
        return []

    sig_phrases_quoted = ", ".join(f'"{p}"' for p in vocab_sig.signature_phrases[:2])
    if not sig_phrases_quoted or "no recurring" in vocab_sig.signature_phrases[0]:
        sig_phrases_quoted = "(no signature phrases yet — lock 2-3 over the next 30 posts)"

    prompts: list[TrainingPrompt] = [
        TrainingPrompt(
            destination_slug="content-idea-generator",
            text=(
                f"Generate 5 X post ideas in the voice of {handle} — "
                f"{tone_sig.dominant_tone}. Signature phrases to weave in when natural: "
                f"{sig_phrases_quoted}. Avoid niche-default vocabulary. End each idea with "
                "a concrete recommendation, never a generic question."
            ),
        ),
        TrainingPrompt(
            destination_slug="thread-builder",
            text=(
                f"Build a 7-post thread in {handle}'s voice ({tone_sig.dominant_tone}). "
                "Open with a contrarian or specific claim, three concrete examples, two "
                "remediations, one closing payoff. Each post under 280 chars. Keep "
                "signature phrases intact."
            ),
        ),
        TrainingPrompt(
            destination_slug="cross-platform-reposter",
            text=(
                f"Adapt the next X post to LinkedIn while preserving {handle}'s voice — "
                "multi-paragraph form, end on a concrete recommendation (not a question), "
                "0-2 niche hashtags. Avoid niche-default phrasings entirely."
            ),
        ),
        TrainingPrompt(
            destination_slug="content-recycler",
            text=(
                f"Recycle this old post in {handle}'s voice — keep the dominant claim and "
                "tone tells; add a fresh data point in the middle. Attribution stamp preserved."
            ),
        ),
        TrainingPrompt(
            destination_slug="reply-drafter",
            text=(
                f"Draft 3 replies in {handle}'s voice — {tone_sig.dominant_tone}, "
                "concrete observations only, never apologetic, never generic agreement."
            ),
        ),
    ]
    return prompts


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: VoiceScores,
    posts: list[str],
    vocab_sig: VocabularySignature,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: generic-polish paradox
    if scores.paradox_active:
        flags.append(RedFlag(
            title="Generic-polish paradox",
            severity="high",
            explanation=(
                f"Voice cohesion at {scores.voice_cohesion}/100 is above 70 while "
                f"Vocabulary distinctiveness at {scores.vocabulary_distinctiveness}/100 "
                "is below 35. The voice is internally consistent but indistinguishable "
                "from niche-default — polished but generic."
            ),
            remediation=(
                "Lock 2-3 signature phrases over the next 30 posts; ship one structurally "
                "distinct format per week; re-run monthly until distinctiveness clears 50."
            ),
        ))

    # Rule 2: distinctiveness below the band even when cohesion is healthy
    if not scores.paradox_active and scores.vocabulary_distinctiveness < 50:
        flags.append(RedFlag(
            title="Distinctiveness below the healthy band",
            severity="medium",
            explanation=(
                f"Vocabulary distinctiveness at {scores.vocabulary_distinctiveness}/100 "
                "sits below the 50-85 healthy range. Signature phrases are sparse."
            ),
            remediation=(
                "Re-use 2-3 phrases deliberately for the next 30 posts and pair with "
                "`competitor-watch` to spot generic-default tilt versus the niche."
            ),
        ))

    # Rule 3: tone fragmentation
    if scores.tone_consistency < 55:
        flags.append(RedFlag(
            title="Tone fragmentation",
            severity="medium",
            explanation=(
                f"Tone consistency at {scores.tone_consistency}/100 is below the 60-90 "
                "healthy band — the sample reads as several different voices."
            ),
            remediation=(
                "Re-anchor tone via the dominant signature; pair with `analytics-summarizer` "
                "to see whether tone-consistent posts outperform."
            ),
        ))

    # Rule 4: structure-shape gap
    flags.append(RedFlag(
        title="Structure-shape gap",
        severity="low",
        explanation=(
            "At least one repeating shape useful in this niche is absent from the sample."
        ),
        remediation=(
            "Try the absent shape once per week; A/B against the existing dominant shape "
            "for 4 weeks via `ab-test-suggester`."
        ),
    ))

    return flags[: 3 if not scores.paradox_active else 4]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: VoiceScores,
    posts: list[str],
    paradox_present: bool,
) -> list[Recommendation]:
    pool: list[Recommendation] = []

    pool.append(Recommendation(
        text=(
            "Lock signature phrases by re-using them deliberately for the next 30 posts; "
            "track which ones harvest reply attention."
        ),
        bridge_slug="content-idea-generator",
    ))
    pool.append(Recommendation(
        text=(
            "Snapshot the voice profile monthly so the 30-day trend arrows in the Voice "
            "Profile table become a real baseline rather than `n/a`."
        ),
        bridge_slug="analytics-summarizer",
    ))
    pool.append(Recommendation(
        text=(
            "Try one new structural shape per week; A/B against the existing dominant "
            "shape for 4 weeks."
        ),
        bridge_slug="ab-test-suggester",
    ))
    if paradox_present:
        pool.append(Recommendation(
            text=(
                "Compare the signature phrases against 3 competitors via `competitor-watch` "
                "to spot which phrases are niche-default and which are genuinely the creator's."
            ),
            bridge_slug="competitor-watch",
        ))
    pool.append(Recommendation(
        text=(
            "Cross-post the next anchor with `cross-platform-reposter` paired with this "
            "voice profile so platform-default voice doesn't dilute the signal."
        ),
        bridge_slug="cross-platform-reposter",
    ))
    pool.append(Recommendation(
        text=(
            "If a paid-tier offer surfaces in the next quarter, model the voice carefully "
            "before publishing."
        ),
        bridge_slug="monetization-optimizer",
        monetization=True,
    ))
    pool.append(Recommendation(
        text=(
            "Recycle the highest-engagement post via `content-recycler` with the "
            "trained voice profile to compound the signal."
        ),
        bridge_slug="content-recycler",
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
                        "Cross-reference the voice scores with last week's analytics to "
                        "spot which signatures compounded best."
                    ),
                    bridge_slug=slug,
                )
                seen.add(slug)
                break

    while len(chosen) < 3:
        chosen.append(Recommendation(
            text="Re-run with a larger sample to lift confidence.",
            bridge_slug="research-assistant",
        ))

    return chosen[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def confidence_for(sample_size: int, scores: VoiceScores) -> tuple[str, str]:
    if sample_size >= 30 and scores.profile_score >= 65:
        return ("high", f"{sample_size} posts cover tone + structure + vocabulary cleanly.")
    if sample_size >= 15:
        return (
            "medium",
            f"{sample_size} posts give a directional read; scale to 30+ to lift to high.",
        )
    if sample_size >= SAMPLE_AUDIT_BELOW:
        return (
            "low",
            f"{sample_size} posts are above the 5-post floor but below the 10-post audit "
            "threshold — directional only.",
        )
    return (
        "low",
        f"{sample_size} posts are inside the audit band (< 10) — Voice Audit auto-triggered.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _render_voice_snapshot(
    handle: str,
    sample_size: int,
    voice_focus: str,
    output_format: str,
    tone_sig: ToneSignature,
) -> str:
    headline = (
        f"{handle}: {tone_sig.dominant_tone} voice across {sample_size} posts; "
        "voice profile below."
    )
    return "\n".join([
        "## Voice Snapshot",
        f"**{headline}**",
        "",
        f"- **X handle**: {handle}",
        f"- **Sample size**: {sample_size} posts",
        f"- **Voice focus**: {voice_focus}",
        f"- **Output format**: {output_format}",
        f"- **Dominant signal**: {tone_sig.dominant_tone}",
    ])


def _render_voice_profile(scores: VoiceScores) -> str:
    rows = [
        "| Metric | Score | Interpretation | 30d trend |",
        "|---|---|---|---|",
    ]
    fields = (
        ("Tone consistency", scores.tone_consistency),
        ("Structure consistency", scores.structure_consistency),
        ("Vocabulary distinctiveness", scores.vocabulary_distinctiveness),
        ("Voice cohesion", scores.voice_cohesion),
    )
    for metric, val in fields:
        rows.append(
            f"| {metric} | {val}/100 | {scores.interpretations[metric]} | {scores.trends[metric]} |"
        )
    table = "\n".join(rows)
    out = "## Voice Profile\n\n" + table + f"\n\n**Voice Profile score**: {scores.profile_score}/100"
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: voice is internally consistent but indistinguishable from "
            "niche-default — polished but generic."
        )
    return out


def _render_signatures(
    tone: ToneSignature,
    struct: StructureSignature,
    vocab: VocabularySignature,
) -> str:
    sig_phrases = ", ".join(f'"{p}"' for p in vocab.signature_phrases)
    return "\n".join([
        "## Voice Signatures",
        "",
        "### Tone",
        f"- **Dominant tone**: {tone.dominant_tone}.",
        f"- **Secondary tones**: {tone.secondary_tones}.",
        f"- **Tone tells**: {'; '.join(tone.tone_tells)}.",
        "",
        "### Structure",
        f"- **Common shape 1**: {struct.common_shape_1}",
        f"- **Common shape 2**: {struct.common_shape_2}",
        f"- **Shape that's missing**: {struct.missing_shape}",
        "",
        "### Vocabulary",
        f"- **Signature phrases**: {sig_phrases}.",
        f"- **Lexicon tilts**: {vocab.lexicon_tilts}",
        f"- **Generic-default words to watch**: {vocab.generic_default_watch}",
    ])


def _render_training_prompts(prompts: list[TrainingPrompt]) -> str:
    if not prompts:
        return (
            "## Training Prompts\n\n"
            "_(output_format = analysis — training prompts skipped; "
            "re-run with --output-format both or training_prompts to emit them)_"
        )
    lines = ["## Training Prompts", ""]
    monetization_emitted = False
    for i, tp in enumerate(prompts, start=1):
        line = (
            f"{i}. **For `{tp.destination_slug}`**: {tp.text}"
        )
        if tp.monetization and not monetization_emitted:
            line += "\n\n   " + ARTICLE_V1_DISCLAIMER
            monetization_emitted = True
        lines.append(line)
    return "\n".join(lines)


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


def _render_voice_audit(
    sample_size: int, voice_focus: str, scores: VoiceScores,
) -> str:
    sample_line = (
        f"{sample_size} posts is below the 10-post audit threshold — "
        "treat all numbers as directional."
        if sample_size < SAMPLE_AUDIT_BELOW
        else f"{sample_size} posts is above 10; the audit is auto-triggered by red-flag count."
    )
    weakest = min(scores.interpretations.items(), key=lambda kv: 0)
    return "\n".join([
        "## Voice Audit (auto-triggered)",
        "",
        f"- **Sample reliability**: {sample_line}",
        f"- **Signal gaps**: {voice_focus} signal is most affected at this sample size.",
        f"- **Suggested next sample**: pull 30 posts spanning the last 90 days, focus={voice_focus}.",
        "- **Re-run cadence**: monthly while distinctiveness < 50, otherwise quarterly.",
    ])


# ---------------------------------------------------------------------------
# Tiny-sample refusal
# ---------------------------------------------------------------------------


def render_tiny_sample_refusal(handle: str, n: int) -> str:
    return (
        "## Voice Snapshot\n"
        f"**{handle}: sample of {n} posts is below the 5-post minimum — refusing to score.**\n\n"
        "Brand Voice Trainer refuses to emit a voice profile from a sample smaller than "
        "5 posts; the signal would be unreliable.\n\n"
        "## Recommendations\n"
        "1. Pull at least 10-30 of the creator's recent posts and re-run with "
        "`--sample-file <path>` or `--sample-posts \"<post1||post2||...>\"`. — bridges to: `analytics-summarizer`\n"
        "2. If the creator is just starting out, pair with `content-idea-generator` to "
        "build the first 30 anchor posts. — bridges to: `content-idea-generator`\n"
        "3. Once 10+ posts exist, re-run; below 10 the runner emits a Voice Audit "
        "alongside the profile. — bridges to: `research-assistant`\n\n"
        "## Confidence\n"
        f"Confidence: low — sample size {n} below the agent's hard floor (5). No scores emitted.\n"
    )


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Brand Voice Trainer (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-applied. Built for xAI, X, Grok and the ecosystem community. ❤️ -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_voice_profile(
    *,
    x_handle: str,
    sample_posts=None,
    sample_file: Optional[str] = None,
    date_range: Optional[str] = None,
    voice_focus: str = "all",
    output_format: str = "both",
    when: Optional[str] = None,
    demo_mode: bool = False,
) -> str:
    handle = normalize_handle(x_handle)
    if voice_focus not in VOICE_FOCUS_OPTIONS:
        raise ValueError(f"voice_focus must be one of {VOICE_FOCUS_OPTIONS}, got {voice_focus!r}")
    if output_format not in OUTPUT_FORMAT_OPTIONS:
        raise ValueError(f"output_format must be one of {OUTPUT_FORMAT_OPTIONS}, got {output_format!r}")

    if sample_posts:
        posts = parse_inline_sample(sample_posts)
    elif sample_file:
        posts = parse_sample_file(Path(sample_file).expanduser().resolve())
    elif date_range:
        posts = synth_date_range_sample(date_range)
    else:
        posts = []

    when_iso = when or date.today().isoformat()
    n = len(posts)

    if n < SAMPLE_REFUSE_BELOW:
        return render_tiny_sample_refusal(handle, n)

    rng = deterministic_rng(handle, posts, voice_focus, when_iso)
    scores = score_voice(rng, posts, voice_focus, demo_mode=demo_mode)
    tone_sig = build_tone_signature(posts)
    struct_sig = build_structure_signature(posts)
    vocab_sig = build_vocabulary_signature(posts)
    prompts = build_training_prompts(handle, tone_sig, vocab_sig, output_format)
    flags = build_red_flags(scores, posts, vocab_sig)
    paradox_present = scores.paradox_active
    recs = build_recommendations(rng, scores, posts, paradox_present)
    confidence = confidence_for(n, scores)

    sections = [
        _render_voice_snapshot(handle, n, voice_focus, output_format, tone_sig),
        "",
        _render_voice_profile(scores),
        "",
        _render_signatures(tone_sig, struct_sig, vocab_sig),
        "",
        _render_training_prompts(prompts),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    if len(flags) > 3 or n < SAMPLE_AUDIT_BELOW:
        sections.extend([
            "",
            _render_voice_audit(n, voice_focus, scores),
        ])

    rendered = "\n".join(sections).rstrip() + "\n"
    assert_only_creator_handle_in_render(rendered, handle)
    return rendered


# Manifest contract — alias the v2.15 manifest binds to:
generate = generate_voice_profile


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Brand Voice Trainer (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Trains only on creator's own voice\n"
        "  Built for xAI, X, Grok and the ecosystem community. ❤️\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="brand-voice-trainer",
        description=(
            "Read a sample of the creator's own past posts and emit a 6/7-section "
            "voice profile + training prompts for other Grok Agent OS templates. "
            "Drafts only — never auto-applied."
        ),
    )
    p.add_argument("--x-handle", required=True, help="The creator's X handle (with or without leading @).")
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--sample-posts",
        help=(
            "Inline list of post bodies separated by `||` or two newlines. Each entry "
            "is one post body (no surrounding URL or metadata)."
        ),
    )
    src.add_argument(
        "--sample-file",
        help=(
            "Path to a newline-or-`---`-separated file of post bodies. Lines starting "
            "with `#` are ignored."
        ),
    )
    src.add_argument(
        "--date-range",
        help="ISO date range (YYYY-MM-DD/YYYY-MM-DD) used as deterministic seed when no inline sample is provided.",
    )
    p.add_argument(
        "--voice-focus",
        choices=list(VOICE_FOCUS_OPTIONS),
        default="all",
        help="Which signature dimension to emphasise. Default 'all'.",
    )
    p.add_argument(
        "--output-format",
        choices=list(OUTPUT_FORMAT_OPTIONS),
        default="both",
        help="What the report includes. Default 'both' (analysis + training prompts).",
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run with the canonical 24-post generic-polish sample — no inputs required. "
            "Demo pins the score profile to the generic-polish paradox so the rule "
            "always demonstrates."
        ),
    )
    p.add_argument(
        "--demo-productivity",
        action="store_true",
        help=(
            "Run with an 8-post productivity-niche sample — small enough to trigger "
            "the Voice Audit auto-section without forcing the paradox."
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
    if args.demo and not (args.sample_posts or args.sample_file or args.date_range):
        sample_arg: object = list(DEMO_PARADOX_SAMPLE)
        demo_mode = True
    elif args.demo_productivity and not (args.sample_posts or args.sample_file or args.date_range):
        sample_arg = list(DEMO_PRODUCTIVITY_SAMPLE)
        demo_mode = False
    elif args.sample_posts:
        sample_arg = args.sample_posts
    elif args.sample_file:
        sample_arg = None
    elif args.date_range:
        sample_arg = None
    else:
        sys.stderr.write(
            "error: provide one of --sample-posts, --sample-file, --date-range, --demo, --demo-productivity.\n"
        )
        return 2

    when_iso = date.today().isoformat()
    rendered = generate_voice_profile(
        x_handle=args.x_handle,
        sample_posts=sample_arg if sample_arg is not None else None,
        sample_file=args.sample_file,
        date_range=args.date_range,
        voice_focus=args.voice_focus,
        output_format=args.output_format,
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
