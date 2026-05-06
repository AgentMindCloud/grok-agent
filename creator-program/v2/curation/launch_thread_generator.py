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
"""Wednesday X launch-thread builder for the curation cadence.

The Wednesday job loads the Monday-pinned `ContentSelection`, expands each
winner into one tweet, and wraps the set with a hook tweet (intro) and a
CTA tweet (closing). The output is a `ThreadDraft` that can be reviewed by
a human before it is posted — the harness intentionally never posts on its
own.

Tweet length is capped at 280 characters per item. If the assembled hook or
CTA exceeds the limit, the constructor truncates with an ellipsis so the
draft remains valid for any downstream X API client.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .content_selector import ContentSelection


_TWEET_LIMIT = 280
_HOOK_TEMPLATE = (
    "This week's top {count} Grok agent templates on the Creator Program "
    "(week {week_iso}). Built for xAI, X, Grok and the ecosystem community."
)
_WINNER_TEMPLATE = "{position}/ {template_id} - score {score:.3f}"
_CTA_TEMPLATE = (
    "Install any of these with `grok-agent install <template_id>` on Windows. "
    "Not financial advice. Pin replies for context."
)


def _truncate(text: str, limit: int = _TWEET_LIMIT) -> str:
    """Truncate a tweet body to the platform limit with a single-character ellipsis.

    The ellipsis is the U+2026 character so it counts as a single code point,
    keeping the visual length at exactly `limit` characters when truncated.
    """
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class ThreadDraft(BaseModel):
    """An ordered list of tweet bodies forming a launch thread."""

    model_config = ConfigDict(extra="forbid")

    week_iso: str = Field(..., min_length=1, max_length=32)
    tweets: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    @field_validator("week_iso")
    @classmethod
    def _safe_week_iso(cls, value: str) -> str:
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"week_iso must not contain path separators: {value!r}")
        return value

    @field_validator("tweets")
    @classmethod
    def _enforce_tweet_limits(cls, value: List[str]) -> List[str]:
        for idx, tweet in enumerate(value):
            if not tweet or not tweet.strip():
                raise ValueError(f"tweets[{idx}] is empty or whitespace-only")
            if len(tweet) > _TWEET_LIMIT:
                raise ValueError(
                    f"tweets[{idx}] is {len(tweet)} chars (max {_TWEET_LIMIT})"
                )
        return value


def generate_thread(selection: ContentSelection) -> ThreadDraft:
    """Build a 5-7 tweet launch thread from a `ContentSelection`.

    Layout: [hook, winner_1, winner_2, winner_3, ..., cta]. With the default
    top-3 selection that produces exactly 5 tweets; selections of 4 or 5
    winners produce 6 or 7 tweets respectively. Selections with fewer than 1
    or more than 5 winners raise ValueError so the cadence stays predictable.
    """
    winners = list(selection.selections)
    if not winners:
        raise ValueError(
            "ContentSelection has no selections; nothing to draft a thread for."
        )
    if len(winners) > 5:
        raise ValueError(
            f"ContentSelection has {len(winners)} selections; max 5 for a thread."
        )

    hook = _truncate(
        _HOOK_TEMPLATE.format(count=len(winners), week_iso=selection.week_iso)
    )
    body = [
        _truncate(
            _WINNER_TEMPLATE.format(
                position=idx + 1,
                template_id=winner.template_id,
                score=winner.score,
            )
        )
        for idx, winner in enumerate(winners)
    ]
    cta = _truncate(_CTA_TEMPLATE)

    tweets = [hook, *body, cta]
    return ThreadDraft(week_iso=selection.week_iso, tweets=tweets)


def preview_thread(draft: ThreadDraft) -> str:
    """Render a thread as a human-readable, copy-pasteable preview string."""
    lines = [f"Thread draft for week {draft.week_iso}", "-" * 40]
    for idx, tweet in enumerate(draft.tweets):
        lines.append(f"[{idx + 1}/{len(draft.tweets)}] {tweet}")
    return "\n".join(lines)


def _storage_root() -> Path:
    """Resolve the local-first threads directory and ensure it exists."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Local"
    threads = root / "grok-agent" / "creator-program" / "curation" / "threads"
    threads.mkdir(parents=True, exist_ok=True)
    return threads


def _thread_path(week_iso: str) -> Path:
    """Resolve the JSON file path for a thread draft, validating the week_iso."""
    if not week_iso or "/" in week_iso or "\\" in week_iso or ".." in week_iso:
        raise ValueError(f"Invalid week_iso: {week_iso!r}")
    return _storage_root() / f"{week_iso}.json"


def save_thread(draft: ThreadDraft) -> Path:
    """Persist the thread draft to disk and return the resolved Path."""
    path = _thread_path(draft.week_iso)
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_thread(week_iso: str) -> ThreadDraft:
    """Load a previously-saved thread draft from disk."""
    path = _thread_path(week_iso)
    if not path.exists():
        raise FileNotFoundError(
            f"No thread draft on disk for week_iso={week_iso!r} at {path}"
        )
    return ThreadDraft.model_validate_json(path.read_text(encoding="utf-8"))
