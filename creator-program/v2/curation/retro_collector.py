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
#
# Built for xAI, X, Grok and the ecosystem community.
"""Friday retrospective collector + weekly summarizer.

The Friday job in the curation cadence collects free-form text from creators
about how the launched templates performed during the week, classifies each
response with a transparent keyword-based sentiment heuristic, and persists
the responses for later aggregation. `summarize_week` then rolls up every
response for a given week into a `RetroSummary` (count, sentiment breakdown,
naive top-themes from word frequency) so the harness can post a public retro.

Design notes:

  * Sentiment classification is intentionally rule-based. The harness must be
    auditable end-to-end without a network round-trip; an LLM-based classifier
    would violate the local-first contract for the Friday cron run.
  * Top-themes extraction is also rule-based: stop-words are removed, the
    remaining tokens are counted, and the highest-frequency tokens (length >=
    4 to skip short connective words) are reported. This is good enough to
    surface 1-2 word recurring themes; richer NLP can be layered later
    without a schema break.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_POSITIVE_KEYWORDS = frozenset(
    {
        "great",
        "love",
        "awesome",
        "amazing",
        "excellent",
        "fantastic",
        "good",
        "helpful",
        "useful",
        "win",
        "winning",
        "easy",
        "smooth",
        "fast",
        "happy",
        "satisfied",
        "recommend",
        "perfect",
        "wonderful",
        "outstanding",
    }
)
_NEGATIVE_KEYWORDS = frozenset(
    {
        "bad",
        "terrible",
        "awful",
        "broken",
        "buggy",
        "slow",
        "confusing",
        "hate",
        "useless",
        "frustrating",
        "frustrated",
        "annoying",
        "crash",
        "crashed",
        "crashes",
        "fail",
        "failed",
        "failing",
        "poor",
        "disappointed",
        "disappointing",
    }
)
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "have",
        "been",
        "were",
        "your",
        "their",
        "they",
        "them",
        "what",
        "when",
        "where",
        "which",
        "would",
        "could",
        "should",
        "about",
        "very",
        "just",
        "also",
        "than",
        "then",
    }
)
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]+")
_WEEK_ISO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


SentimentLabel = Literal["positive", "neutral", "negative"]


def _classify_sentiment(text: str) -> SentimentLabel:
    """Classify free-form text using positive/negative keyword counts.

    Tokens are lowercased. The label is positive if positives strictly
    outnumber negatives, negative if negatives strictly outnumber positives,
    and neutral otherwise (including when both counts are zero).
    """
    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    pos = sum(1 for tok in tokens if tok in _POSITIVE_KEYWORDS)
    neg = sum(1 for tok in tokens if tok in _NEGATIVE_KEYWORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _extract_themes(texts: List[str], top_k: int = 5) -> List[str]:
    """Return the top-k highest-frequency content tokens across the texts."""
    counter: Counter[str] = Counter()
    for body in texts:
        for raw in _TOKEN_RE.findall(body):
            tok = raw.lower()
            if len(tok) < 4:
                continue
            if tok in _STOPWORDS:
                continue
            counter[tok] += 1
    return [token for token, _ in counter.most_common(top_k)]


class RetroResponse(BaseModel):
    """A single creator's retro feedback for a given week."""

    model_config = ConfigDict(extra="forbid")

    creator_id: str = Field(..., min_length=1, max_length=128)
    response_text: str = Field(..., min_length=1, max_length=4096)
    sentiment: SentimentLabel
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    @field_validator("creator_id")
    @classmethod
    def _safe_creator_id(cls, value: str) -> str:
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"creator_id must not contain path separators: {value!r}")
        return value


class RetroSummary(BaseModel):
    """Aggregated retro for a single week."""

    model_config = ConfigDict(extra="forbid")

    week_iso: str = Field(..., min_length=1, max_length=32)
    response_count: int = Field(..., ge=0)
    sentiment_breakdown: Dict[str, int] = Field(default_factory=dict)
    top_themes: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    @field_validator("week_iso")
    @classmethod
    def _safe_week_iso(cls, value: str) -> str:
        if not _WEEK_ISO_RE.match(value):
            raise ValueError(f"week_iso has unsafe characters: {value!r}")
        return value


def collect_response(creator_id: str, response_text: str) -> RetroResponse:
    """Build and return a `RetroResponse` with the heuristic sentiment label.

    This function is pure — callers persist the result via `save_response`.
    Splitting classification from persistence keeps the function unit-testable
    without disk side effects.
    """
    sentiment = _classify_sentiment(response_text)
    return RetroResponse(
        creator_id=creator_id,
        response_text=response_text,
        sentiment=sentiment,
    )


def _storage_root() -> Path:
    """Resolve the local-first retros directory and ensure it exists."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Local"
    retros = root / "grok-agent" / "creator-program" / "curation" / "retros"
    retros.mkdir(parents=True, exist_ok=True)
    return retros


def _week_dir(week_iso: str) -> Path:
    """Resolve the per-week directory under the retros root, creating it."""
    if not week_iso or not _WEEK_ISO_RE.match(week_iso):
        raise ValueError(f"Invalid week_iso: {week_iso!r}")
    target = _storage_root() / week_iso
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_response(week_iso: str, response: RetroResponse) -> Path:
    """Persist a single `RetroResponse` under the given week's directory.

    Filenames are `<creator_id>.json` so re-submissions overwrite cleanly.
    """
    week_dir = _week_dir(week_iso)
    target = week_dir / f"{response.creator_id}.json"
    target.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    return target


def load_responses(week_iso: str) -> List[RetroResponse]:
    """Load every retro response saved for a given week.

    Returns an empty list if the week directory does not exist yet.
    """
    if not week_iso or not _WEEK_ISO_RE.match(week_iso):
        raise ValueError(f"Invalid week_iso: {week_iso!r}")
    week_dir = _storage_root() / week_iso
    if not week_dir.exists():
        return []
    out: List[RetroResponse] = []
    for path in sorted(week_dir.glob("*.json")):
        if path.name.startswith("_summary"):
            continue
        out.append(RetroResponse.model_validate_json(path.read_text(encoding="utf-8")))
    return out


def summarize_week(week_iso: str) -> RetroSummary:
    """Aggregate every response for a week into a `RetroSummary`."""
    responses = load_responses(week_iso)
    breakdown: Dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
    for resp in responses:
        breakdown[resp.sentiment] = breakdown.get(resp.sentiment, 0) + 1
    themes = _extract_themes([r.response_text for r in responses])
    summary = RetroSummary(
        week_iso=week_iso,
        response_count=len(responses),
        sentiment_breakdown=breakdown,
        top_themes=themes,
    )
    save_summary(summary)
    return summary


def save_summary(summary: RetroSummary) -> Path:
    """Persist the rolled-up summary alongside the per-creator responses."""
    week_dir = _week_dir(summary.week_iso)
    target = week_dir / "_summary.json"
    target.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return target


def load_summary(week_iso: str) -> RetroSummary:
    """Load a previously-saved `RetroSummary` for a given week."""
    if not week_iso or not _WEEK_ISO_RE.match(week_iso):
        raise ValueError(f"Invalid week_iso: {week_iso!r}")
    target = _storage_root() / week_iso / "_summary.json"
    if not target.exists():
        raise FileNotFoundError(
            f"No retro summary on disk for week_iso={week_iso!r} at {target}"
        )
    return RetroSummary.model_validate_json(target.read_text(encoding="utf-8"))
