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
"""Content selector — picks the top-N templates from a TrendScore list.

The Monday job's last step is to call `select_top_n` on the analyzer output,
wrap the result in a `ContentSelection` model, and persist it to disk so the
Wednesday job can load and turn it into a launch thread.

Persistence is local-first: each week's selection lives at
`$env:LOCALAPPDATA\\grok-agent\\creator-program\\curation\\selections\\<week_iso>.json`
with a Linux-friendly fallback for CI runners.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .trend_analyzer import TrendScore


class ContentSelection(BaseModel):
    """A frozen snapshot of the top-N templates picked for a given week."""

    model_config = ConfigDict(extra="forbid")

    week_iso: str = Field(..., min_length=1, max_length=32)
    selections: List[TrendScore] = Field(default_factory=list)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    @field_validator("week_iso")
    @classmethod
    def _safe_week_iso(cls, value: str) -> str:
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"week_iso must not contain path separators: {value!r}")
        return value


def select_top_n(scores: List[TrendScore], n: int = 3) -> List[TrendScore]:
    """Return the first `n` items from a (presumed sorted) score list.

    Defensive against unsorted input: re-sorts by descending score, ascending
    template_id (matches `analyze_week`). If `n` exceeds the list length, the
    full list is returned without padding.
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    sorted_scores = sorted(scores, key=lambda ts: (-ts.score, ts.template_id))
    return sorted_scores[:n]


def _storage_root() -> Path:
    """Resolve the local-first selections directory and ensure it exists.

    Honors `$env:LOCALAPPDATA` on Windows; falls back to
    `~/AppData/Local/grok-agent/creator-program/curation/selections` so CI
    runners on Linux see the same path shape.
    """
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Local"
    selections = root / "grok-agent" / "creator-program" / "curation" / "selections"
    selections.mkdir(parents=True, exist_ok=True)
    return selections


def _selection_path(week_iso: str) -> Path:
    """Resolve the JSON file path for a given week_iso, validating the value."""
    if not week_iso or "/" in week_iso or "\\" in week_iso or ".." in week_iso:
        raise ValueError(f"Invalid week_iso: {week_iso!r}")
    return _storage_root() / f"{week_iso}.json"


def save_selection(selection: ContentSelection) -> Path:
    """Persist the selection to disk as JSON and return the resolved Path."""
    path = _selection_path(selection.week_iso)
    path.write_text(selection.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_selection(week_iso: str) -> ContentSelection:
    """Load a previously-saved selection from disk."""
    path = _selection_path(week_iso)
    if not path.exists():
        raise FileNotFoundError(
            f"No selection on disk for week_iso={week_iso!r} at {path}"
        )
    return ContentSelection.model_validate_json(path.read_text(encoding="utf-8"))
