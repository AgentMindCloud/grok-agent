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
"""Top-level orchestrator for the Mon/Wed/Fri Creator Program curation cadence.

Three subcommands are exposed both as Python functions (for in-process use by
tests and other modules) and as `argparse` subcommands so the GitHub Actions
workflow can invoke them with a single shell line.

  monday     -> fetch metrics, score, select top-3, persist `ContentSelection`.
  wednesday  -> load Monday's selection, draft a 5-7 tweet thread, persist.
  friday     -> roll up retros into a `RetroSummary`.

The metrics fetcher is pluggable. The default `_default_metrics_fetcher`
returns a small, deterministic mock dataset so the harness is operational in
CI and in local dry-runs without external services. Production deployments
override the fetcher by injecting a callable into `run_monday`.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional


def _bootstrap_script_mode_package() -> object:
    """When this file is run directly (not via `-m`), build a synthetic
    parent package for the curation directory under the alias
    `grok_curation_pkg` and load the four submodules into it so their
    relative imports (e.g. `from .trend_analyzer import ...`) resolve.

    Returns the synthetic package module. The package's own `__init__.py` is
    deliberately NOT executed here because it imports `weekly_curation` —
    re-entering this file mid-execution would deadlock the import. Loading
    the four leaf submodules covers everything `weekly_curation` needs.
    """
    alias = "grok_curation_pkg"
    if alias in sys.modules:
        return sys.modules[alias]

    curation_dir = Path(__file__).resolve().parent
    pkg_spec = importlib.util.spec_from_loader(
        alias,
        loader=None,
        is_package=True,
    )
    if pkg_spec is None:
        raise RuntimeError(f"Failed to build synthetic package spec for {alias}")
    pkg_module = importlib.util.module_from_spec(pkg_spec)
    pkg_module.__path__ = [str(curation_dir)]
    sys.modules[alias] = pkg_module

    # Order matters: trend_analyzer has zero internal deps, the others depend
    # on it (and on each other for content_selector -> launch_thread_generator).
    for submodule in (
        "trend_analyzer",
        "content_selector",
        "launch_thread_generator",
        "retro_collector",
    ):
        sub_path = curation_dir / f"{submodule}.py"
        sub_spec = importlib.util.spec_from_file_location(
            f"{alias}.{submodule}",
            sub_path,
        )
        if sub_spec is None or sub_spec.loader is None:
            raise RuntimeError(f"Failed to build spec for {sub_path}")
        sub_module = importlib.util.module_from_spec(sub_spec)
        sys.modules[f"{alias}.{submodule}"] = sub_module
        setattr(pkg_module, submodule, sub_module)
        sub_spec.loader.exec_module(sub_module)

    return pkg_module


def _resolve_imports():
    """Import the four submodules whether this file runs as a package member
    or as a bare script.

    When invoked via `python -m grok_creator_v2.curation.weekly_curation`, the
    relative-import form is correct. When the README's PowerShell example
    invokes `python creator-program\\v2\\curation\\weekly_curation.py`, the
    file is loaded with `__package__ == ""` and relative imports fail; we
    bootstrap the curation directory as a fresh package so its submodules
    (which import from each other relatively) resolve.
    """
    if __package__:
        from .content_selector import (
            ContentSelection,
            save_selection,
            select_top_n,
        )
        from .launch_thread_generator import (
            ThreadDraft,
            generate_thread,
            preview_thread,
            save_thread,
        )
        from .retro_collector import RetroSummary, summarize_week
        from .trend_analyzer import TemplateMetrics, analyze_week
    else:  # pragma: no cover - exercised via the script entrypoint, not pytest.
        pkg = _bootstrap_script_mode_package()
        ContentSelection = pkg.content_selector.ContentSelection
        save_selection = pkg.content_selector.save_selection
        select_top_n = pkg.content_selector.select_top_n
        ThreadDraft = pkg.launch_thread_generator.ThreadDraft
        generate_thread = pkg.launch_thread_generator.generate_thread
        preview_thread = pkg.launch_thread_generator.preview_thread
        save_thread = pkg.launch_thread_generator.save_thread
        RetroSummary = pkg.retro_collector.RetroSummary
        summarize_week = pkg.retro_collector.summarize_week
        TemplateMetrics = pkg.trend_analyzer.TemplateMetrics
        analyze_week = pkg.trend_analyzer.analyze_week
    return {
        "ContentSelection": ContentSelection,
        "save_selection": save_selection,
        "select_top_n": select_top_n,
        "ThreadDraft": ThreadDraft,
        "generate_thread": generate_thread,
        "preview_thread": preview_thread,
        "save_thread": save_thread,
        "RetroSummary": RetroSummary,
        "summarize_week": summarize_week,
        "TemplateMetrics": TemplateMetrics,
        "analyze_week": analyze_week,
    }


_IMPORTS = _resolve_imports()
ContentSelection = _IMPORTS["ContentSelection"]
save_selection = _IMPORTS["save_selection"]
select_top_n = _IMPORTS["select_top_n"]
ThreadDraft = _IMPORTS["ThreadDraft"]
generate_thread = _IMPORTS["generate_thread"]
preview_thread = _IMPORTS["preview_thread"]
save_thread = _IMPORTS["save_thread"]
RetroSummary = _IMPORTS["RetroSummary"]
summarize_week = _IMPORTS["summarize_week"]
TemplateMetrics = _IMPORTS["TemplateMetrics"]
analyze_week = _IMPORTS["analyze_week"]


_LOG = logging.getLogger(__name__)


MetricsFetcher = Callable[[str], List[TemplateMetrics]]


def _current_week_iso() -> str:
    """Return today's ISO week tag (e.g. '2026-W19') in UTC.

    Using UTC keeps the cadence aligned with the GitHub Actions cron schedule
    which fires at 09:00 UTC every Mon/Wed/Fri.
    """
    today = datetime.now(tz=timezone.utc).date()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _default_metrics_fetcher(week_iso: str) -> List[TemplateMetrics]:
    """Return a deterministic mock metrics set for dry-runs and CI.

    This dataset is intentionally small but realistic: scores cover the full
    [0,1] band so analyzer + selector behavior is exercised end-to-end.
    Production callers should pass their own fetcher into `run_monday`.
    """
    _LOG.info("Using default mock metrics fetcher for week=%s", week_iso)
    return [
        TemplateMetrics(
            template_id="content-idea-generator",
            installs_week=420,
            rating_avg=4.6,
            mention_velocity=72.0,
            engagement_score=0.84,
        ),
        TemplateMetrics(
            template_id="reply-drafter",
            installs_week=305,
            rating_avg=4.4,
            mention_velocity=58.0,
            engagement_score=0.71,
        ),
        TemplateMetrics(
            template_id="analytics-summarizer",
            installs_week=210,
            rating_avg=4.5,
            mention_velocity=33.0,
            engagement_score=0.62,
        ),
        TemplateMetrics(
            template_id="thread-builder",
            installs_week=180,
            rating_avg=4.2,
            mention_velocity=41.0,
            engagement_score=0.58,
        ),
        TemplateMetrics(
            template_id="dm-triager",
            installs_week=95,
            rating_avg=4.1,
            mention_velocity=22.0,
            engagement_score=0.49,
        ),
    ]


def run_monday(
    week_iso: Optional[str] = None,
    metrics_fetcher: Optional[MetricsFetcher] = None,
    top_n: int = 3,
) -> ContentSelection:
    """Monday checkpoint: score the week and pin the top-N templates."""
    if top_n <= 0:
        raise ValueError(f"top_n must be positive, got {top_n}")
    week = week_iso or _current_week_iso()
    fetcher = metrics_fetcher or _default_metrics_fetcher
    metrics = fetcher(week)
    if not metrics:
        raise RuntimeError(
            f"Metrics fetcher returned no rows for week={week!r}; aborting."
        )
    scored = analyze_week(metrics)
    winners = select_top_n(scored, n=top_n)
    selection = ContentSelection(week_iso=week, selections=winners)
    saved_to = save_selection(selection)
    _LOG.info("Saved Monday selection for week=%s to %s", week, saved_to)
    return selection


def run_wednesday(week_iso: str) -> ThreadDraft:
    """Wednesday checkpoint: draft the launch thread from Monday's pin."""
    if __package__:
        from .content_selector import load_selection
    else:  # pragma: no cover - script-mode path tested via smoke run.
        load_selection = sys.modules["grok_curation_pkg.content_selector"].load_selection

    selection = load_selection(week_iso)
    draft = generate_thread(selection)
    saved_to = save_thread(draft)
    _LOG.info("Saved Wednesday thread draft for week=%s to %s", week_iso, saved_to)
    return draft


def run_friday(week_iso: str) -> RetroSummary:
    """Friday checkpoint: roll up creator retros for the week."""
    summary = summarize_week(week_iso)
    _LOG.info(
        "Friday retro summary for week=%s: %d responses, sentiment=%s",
        week_iso,
        summary.response_count,
        summary.sentiment_breakdown,
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="weekly_curation",
        description=(
            "Mon/Wed/Fri curation cadence orchestrator for the Creator Program."
        ),
    )
    sub = parser.add_subparsers(dest="day", required=True)

    p_mon = sub.add_parser("monday", help="Score the week and pin the top-3.")
    p_mon.add_argument(
        "week_iso",
        nargs="?",
        default=None,
        help="ISO week tag (e.g. 2026-W19); defaults to current UTC week.",
    )
    p_mon.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="How many templates to pin (default: 3).",
    )

    p_wed = sub.add_parser("wednesday", help="Draft the launch thread.")
    p_wed.add_argument("week_iso", help="ISO week tag matching Monday's selection.")

    p_fri = sub.add_parser("friday", help="Summarize the week's retros.")
    p_fri.add_argument("week_iso", help="ISO week tag for the retro to summarize.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint. Returns a process exit code (0 on success)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.day == "monday":
        selection = run_monday(week_iso=args.week_iso, top_n=args.top_n)
        print(f"Pinned {len(selection.selections)} templates for {selection.week_iso}.")
        for rank, ts in enumerate(selection.selections, start=1):
            print(f"  {rank}. {ts.template_id} (score={ts.score:.3f})")
        return 0
    if args.day == "wednesday":
        draft = run_wednesday(args.week_iso)
        print(preview_thread(draft))
        return 0
    if args.day == "friday":
        summary = run_friday(args.week_iso)
        print(
            f"Retro for {summary.week_iso}: {summary.response_count} responses; "
            f"breakdown={summary.sentiment_breakdown}; themes={summary.top_themes}"
        )
        return 0

    # argparse with required=True should make this unreachable.
    parser.error(f"Unknown subcommand: {args.day!r}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
