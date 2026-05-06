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
"""Pytest suite for the Mon/Wed/Fri curation cadence harness.

These tests cover the four submodules (trend_analyzer, content_selector,
launch_thread_generator, retro_collector) plus the orchestrator
(weekly_curation). Persistence is redirected into pytest's `tmp_path` so the
suite never writes to a developer's real `$LOCALAPPDATA` tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest
from pydantic import ValidationError

# These imports rely on conftest.py registering the curation submodule under
# the `grok_creator_v2.curation` alias.
from grok_creator_v2.curation import (  # noqa: E402
    ContentSelection,
    RetroResponse,
    RetroSummary,
    TemplateMetrics,
    ThreadDraft,
    TrendScore,
    analyze_week,
    collect_response,
    generate_thread,
    load_selection,
    load_thread,
    preview_thread,
    run_friday,
    run_monday,
    run_wednesday,
    save_selection,
    save_thread,
    score_template,
    select_top_n,
    summarize_week,
)
from grok_creator_v2.curation import (  # noqa: E402
    content_selector,
    launch_thread_generator,
    retro_collector,
)


# --------------------------------------------------------------------------- #
# Shared fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _redirect_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every submodule's `_storage_root` into pytest's tmp_path.

    Each submodule has its own `_storage_root` because each persists a
    different artifact type. We patch all three so the suite is hermetic.
    """
    selections_dir = tmp_path / "selections"
    threads_dir = tmp_path / "threads"
    retros_dir = tmp_path / "retros"
    for d in (selections_dir, threads_dir, retros_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(content_selector, "_storage_root", lambda: selections_dir)
    monkeypatch.setattr(launch_thread_generator, "_storage_root", lambda: threads_dir)
    monkeypatch.setattr(retro_collector, "_storage_root", lambda: retros_dir)
    return tmp_path


def _sample_metrics() -> List[TemplateMetrics]:
    return [
        TemplateMetrics(
            template_id="alpha",
            installs_week=400,
            rating_avg=4.5,
            mention_velocity=80.0,
            engagement_score=0.80,
        ),
        TemplateMetrics(
            template_id="beta",
            installs_week=200,
            rating_avg=4.0,
            mention_velocity=40.0,
            engagement_score=0.50,
        ),
        TemplateMetrics(
            template_id="gamma",
            installs_week=50,
            rating_avg=3.5,
            mention_velocity=10.0,
            engagement_score=0.30,
        ),
        TemplateMetrics(
            template_id="delta",
            installs_week=10,
            rating_avg=3.0,
            mention_velocity=5.0,
            engagement_score=0.20,
        ),
    ]


# --------------------------------------------------------------------------- #
# trend_analyzer
# --------------------------------------------------------------------------- #


def test_template_metrics_validation() -> None:
    """Pydantic enforces non-negative installs and rating in [0, 5]."""
    valid = TemplateMetrics(
        template_id="ok",
        installs_week=10,
        rating_avg=4.5,
        mention_velocity=12.0,
        engagement_score=0.5,
    )
    assert valid.template_id == "ok"

    with pytest.raises(ValidationError):
        TemplateMetrics(
            template_id="bad",
            installs_week=-1,
            rating_avg=4.0,
            mention_velocity=1.0,
            engagement_score=0.5,
        )

    with pytest.raises(ValidationError):
        TemplateMetrics(
            template_id="bad",
            installs_week=10,
            rating_avg=9.0,  # exceeds 0..5
            mention_velocity=1.0,
            engagement_score=0.5,
        )

    # template_id must not contain path separators.
    with pytest.raises(ValidationError):
        TemplateMetrics(
            template_id="../etc/passwd",
            installs_week=1,
            rating_avg=1.0,
            mention_velocity=1.0,
            engagement_score=0.1,
        )


def test_trend_score_calculation_weighted_sum() -> None:
    """Composite score equals the documented 0.4/0.3/0.2/0.1 weighted sum."""
    metrics = TemplateMetrics(
        template_id="x",
        installs_week=500,  # saturates -> 1.0
        rating_avg=5.0,  # 1.0
        mention_velocity=100.0,  # 1.0
        engagement_score=1.0,  # 1.0
    )
    score = score_template(metrics)
    assert isinstance(score, TrendScore)
    assert score.score == pytest.approx(1.0)

    # Halve every input: score should be 0.5 (linear in normalized inputs).
    half = TemplateMetrics(
        template_id="y",
        installs_week=250,
        rating_avg=2.5,
        mention_velocity=50.0,
        engagement_score=0.5,
    )
    half_score = score_template(half)
    assert half_score.score == pytest.approx(0.5)
    # Breakdown reports normalized components.
    assert half_score.breakdown["installs_norm"] == pytest.approx(0.5)
    assert half_score.breakdown["rating_norm"] == pytest.approx(0.5)


def test_analyze_week_returns_sorted_descending() -> None:
    """Output is sorted by descending score, with deterministic tie-break."""
    scored = analyze_week(_sample_metrics())
    scores = [ts.score for ts in scored]
    assert scores == sorted(scores, reverse=True)
    assert scored[0].template_id == "alpha"
    assert scored[-1].template_id == "delta"

    # Empty input is handled gracefully.
    assert analyze_week([]) == []


# --------------------------------------------------------------------------- #
# content_selector
# --------------------------------------------------------------------------- #


def test_select_top_n_returns_correct_count() -> None:
    """select_top_n caps to len(scores) and rejects negative n."""
    scored = analyze_week(_sample_metrics())
    top3 = select_top_n(scored, n=3)
    assert len(top3) == 3
    assert [ts.template_id for ts in top3] == ["alpha", "beta", "gamma"]

    # n=0 yields empty.
    assert select_top_n(scored, n=0) == []

    # n exceeding length returns the whole list (no padding).
    assert len(select_top_n(scored, n=99)) == len(scored)

    with pytest.raises(ValueError):
        select_top_n(scored, n=-1)


def test_content_selection_serialization_roundtrip() -> None:
    """ContentSelection survives a model_dump_json -> model_validate_json roundtrip."""
    scored = analyze_week(_sample_metrics())
    selection = ContentSelection(week_iso="2026-W19", selections=select_top_n(scored, 3))
    payload = selection.model_dump_json()
    restored = ContentSelection.model_validate_json(payload)
    assert restored.week_iso == selection.week_iso
    assert [s.template_id for s in restored.selections] == [
        s.template_id for s in selection.selections
    ]
    # week_iso must reject path separators.
    with pytest.raises(ValidationError):
        ContentSelection(week_iso="../etc", selections=[])


def test_save_and_load_selection_roundtrip() -> None:
    """save_selection writes JSON; load_selection reads it back identically."""
    scored = analyze_week(_sample_metrics())
    selection = ContentSelection(week_iso="2026-W21", selections=select_top_n(scored, 3))
    path = save_selection(selection)
    assert path.exists()
    restored = load_selection("2026-W21")
    assert restored.week_iso == "2026-W21"
    assert len(restored.selections) == 3

    with pytest.raises(FileNotFoundError):
        load_selection("2099-W99")


# --------------------------------------------------------------------------- #
# launch_thread_generator
# --------------------------------------------------------------------------- #


def test_generate_thread_produces_5_to_7_tweets() -> None:
    """A 3-winner selection yields exactly 5 tweets (hook + 3 + CTA)."""
    scored = analyze_week(_sample_metrics())
    selection = ContentSelection(week_iso="2026-W19", selections=select_top_n(scored, 3))
    draft = generate_thread(selection)
    assert isinstance(draft, ThreadDraft)
    assert 5 <= len(draft.tweets) <= 7
    # Each tweet under the 280-char limit.
    assert all(len(t) <= 280 for t in draft.tweets)
    # Preview is non-empty and references the week.
    preview = preview_thread(draft)
    assert "2026-W19" in preview

    # Empty selection raises.
    with pytest.raises(ValueError):
        generate_thread(ContentSelection(week_iso="2026-W19", selections=[]))


def test_thread_draft_serialization_roundtrip() -> None:
    """ThreadDraft survives save -> load, and rejects unsafe week_iso."""
    scored = analyze_week(_sample_metrics())
    selection = ContentSelection(week_iso="2026-W22", selections=select_top_n(scored, 3))
    draft = generate_thread(selection)
    path = save_thread(draft)
    assert path.exists()
    restored = load_thread("2026-W22")
    assert restored.week_iso == draft.week_iso
    assert restored.tweets == draft.tweets

    with pytest.raises(ValidationError):
        ThreadDraft(week_iso="../etc", tweets=["hello"])


# --------------------------------------------------------------------------- #
# retro_collector
# --------------------------------------------------------------------------- #


def test_retro_response_sentiment_classification() -> None:
    """Keyword heuristic classifies positive/neutral/negative correctly."""
    pos = collect_response("creator-1", "This template is amazing and helpful, I love it!")
    assert pos.sentiment == "positive"

    neg = collect_response("creator-2", "Buggy and confusing, terrible experience.")
    assert neg.sentiment == "negative"

    neutral = collect_response("creator-3", "I installed the template yesterday.")
    assert neutral.sentiment == "neutral"

    # Mixed signals tied -> neutral.
    mixed = collect_response("creator-4", "great but also terrible")
    assert mixed.sentiment == "neutral"

    # creator_id must reject path separators.
    with pytest.raises(ValidationError):
        RetroResponse(
            creator_id="../etc",
            response_text="ok",
            sentiment="neutral",
        )


def test_summarize_week_aggregates_responses() -> None:
    """summarize_week tallies counts, sentiment, and surfaces top themes."""
    week = "2026-W23"
    for cid, text in [
        ("c1", "love love love this content idea generator, amazing helpful"),
        ("c2", "the analytics summarizer is great and useful, recommend"),
        ("c3", "this thread builder is broken buggy and frustrating"),
        ("c4", "saw the launch on twitter today"),
    ]:
        resp = collect_response(cid, text)
        retro_collector.save_response(week, resp)

    summary: RetroSummary = summarize_week(week)
    assert summary.response_count == 4
    assert summary.sentiment_breakdown["positive"] == 2
    assert summary.sentiment_breakdown["negative"] == 1
    assert summary.sentiment_breakdown["neutral"] == 1
    # Top themes should include some content tokens (length>=4, not stop-words).
    assert isinstance(summary.top_themes, list)
    assert all(len(t) >= 4 for t in summary.top_themes)


# --------------------------------------------------------------------------- #
# weekly_curation orchestrator
# --------------------------------------------------------------------------- #


def test_run_monday_end_to_end_with_mock_metrics() -> None:
    """run_monday with an injected fetcher pins the right templates and saves."""
    week = "2026-W24"
    selection = run_monday(week_iso=week, metrics_fetcher=lambda _w: _sample_metrics())
    assert isinstance(selection, ContentSelection)
    assert selection.week_iso == week
    assert len(selection.selections) == 3
    assert [s.template_id for s in selection.selections] == ["alpha", "beta", "gamma"]

    # Persisted to disk -> Wednesday's run_wednesday can pick it up.
    draft = run_wednesday(week)
    assert draft.week_iso == week
    assert 5 <= len(draft.tweets) <= 7

    # Friday with no responses returns a zero-count summary.
    fri = run_friday(week)
    assert fri.response_count == 0

    # Fetcher returning an empty list raises a clear error.
    with pytest.raises(RuntimeError):
        run_monday(week_iso="2026-W25", metrics_fetcher=lambda _w: [])

    # Negative top_n is rejected up front.
    with pytest.raises(ValueError):
        run_monday(week_iso="2026-W26", top_n=0)
