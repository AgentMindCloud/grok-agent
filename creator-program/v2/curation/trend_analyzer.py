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
"""Weekly trend scoring for the Mon/Wed/Fri curation cadence.

The trend analyzer takes a list of `TemplateMetrics` rows (one per template
that saw activity in the past week) and emits a list of `TrendScore` rows
sorted descending by score. Monday's `weekly_curation` job then feeds the
top-N output into `content_selector.select_top_n` to choose what to pin.

Scoring is a transparent weighted sum so the heuristic can be reasoned about
and tuned without retraining a model:

    score = 0.4 * normalized(installs_week)
          + 0.3 * normalized(rating_avg)
          + 0.2 * normalized(mention_velocity)
          + 0.1 * normalized(engagement_score)

Each component is clamped to [0.0, 1.0] before combination so the final
score is also bounded in [0.0, 1.0]. Concrete normalization choices are
documented inline at the call sites.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Component weights (must sum to 1.0). Hard-coded so changes require review.
_WEIGHT_INSTALLS = 0.4
_WEIGHT_RATING = 0.3
_WEIGHT_VELOCITY = 0.2
_WEIGHT_ENGAGEMENT = 0.1

# Normalization caps. Anything above these saturates to 1.0 in its component.
_INSTALLS_CAP = 500.0  # 500 installs/week is the empirical "viral" threshold.
_RATING_MAX = 5.0  # Ratings are on a 0..5 scale.
_VELOCITY_CAP = 100.0  # Mentions/hour considered red-hot.
_ENGAGEMENT_CAP = 1.0  # Engagement is already a 0..1 ratio in upstream data.


class TemplateMetrics(BaseModel):
    """Raw weekly metrics for a single template, fed into the scorer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str = Field(..., min_length=1, max_length=128)
    installs_week: int = Field(..., ge=0)
    rating_avg: float = Field(..., ge=0.0, le=_RATING_MAX)
    mention_velocity: float = Field(..., ge=0.0)
    engagement_score: float = Field(..., ge=0.0, le=1.0)

    @field_validator("template_id")
    @classmethod
    def _no_separator_in_id(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError(f"template_id must not contain separators: {value!r}")
        return value


class TrendScore(BaseModel):
    """The output of `score_template`: a single composite score + breakdown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str = Field(..., min_length=1, max_length=128)
    score: float = Field(..., ge=0.0, le=1.0)
    breakdown: Dict[str, float] = Field(default_factory=dict)


def _clamp_unit(value: float) -> float:
    """Clamp an arbitrary float into the [0.0, 1.0] interval."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def score_template(metrics: TemplateMetrics) -> TrendScore:
    """Compute the weighted-sum composite score for a single template.

    The breakdown dict reports each pre-weight, normalized component so
    callers (and humans) can audit how the final score was assembled.
    """
    installs_norm = _clamp_unit(metrics.installs_week / _INSTALLS_CAP)
    rating_norm = _clamp_unit(metrics.rating_avg / _RATING_MAX)
    velocity_norm = _clamp_unit(metrics.mention_velocity / _VELOCITY_CAP)
    engagement_norm = _clamp_unit(metrics.engagement_score / _ENGAGEMENT_CAP)

    composite = (
        _WEIGHT_INSTALLS * installs_norm
        + _WEIGHT_RATING * rating_norm
        + _WEIGHT_VELOCITY * velocity_norm
        + _WEIGHT_ENGAGEMENT * engagement_norm
    )
    composite = _clamp_unit(composite)

    breakdown: Dict[str, float] = {
        "installs_norm": round(installs_norm, 6),
        "rating_norm": round(rating_norm, 6),
        "velocity_norm": round(velocity_norm, 6),
        "engagement_norm": round(engagement_norm, 6),
        "weight_installs": _WEIGHT_INSTALLS,
        "weight_rating": _WEIGHT_RATING,
        "weight_velocity": _WEIGHT_VELOCITY,
        "weight_engagement": _WEIGHT_ENGAGEMENT,
    }
    return TrendScore(
        template_id=metrics.template_id,
        score=round(composite, 6),
        breakdown=breakdown,
    )


def analyze_week(metrics_list: List[TemplateMetrics]) -> List[TrendScore]:
    """Score every metric row and return the list sorted by descending score.

    Ties are broken by template_id ascending so the ordering is stable across
    runs with identical data. An empty input yields an empty list.
    """
    scored = [score_template(m) for m in metrics_list]
    scored.sort(key=lambda ts: (-ts.score, ts.template_id))
    return scored
