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
"""Creator Program v2 — Mon/Wed/Fri curation cadence harness.

This subpackage powers the weekly curation loop layered on top of
`weekly_curation_pin` (defined in tier_manager). Three checkpoints land
each week:

  Monday    -> trend analysis + content selection (top 3 templates).
  Wednesday -> launch-thread draft for the selected templates.
  Friday    -> retrospective collection + sentiment summary.

All on-disk artifacts (selections, threads, retros) are persisted under
`$env:LOCALAPPDATA\\grok-agent\\creator-program\\curation\\` so the harness
is local-first and survives offline runs.

Public API (re-exported from the modules in this package):

  TemplateMetrics, TrendScore, score_template, analyze_week
                                                  -> trend_analyzer
  ContentSelection, select_top_n, save_selection, load_selection
                                                  -> content_selector
  ThreadDraft, generate_thread, preview_thread, save_thread, load_thread
                                                  -> launch_thread_generator
  RetroResponse, RetroSummary, collect_response, summarize_week
                                                  -> retro_collector
  run_monday, run_wednesday, run_friday, main     -> weekly_curation
"""

from .trend_analyzer import (
    TemplateMetrics,
    TrendScore,
    analyze_week,
    score_template,
)
from .content_selector import (
    ContentSelection,
    load_selection,
    save_selection,
    select_top_n,
)
from .launch_thread_generator import (
    ThreadDraft,
    generate_thread,
    load_thread,
    preview_thread,
    save_thread,
)
from .retro_collector import (
    RetroResponse,
    RetroSummary,
    collect_response,
    summarize_week,
)
from .weekly_curation import (
    main,
    run_friday,
    run_monday,
    run_wednesday,
)

__all__ = [
    "ContentSelection",
    "RetroResponse",
    "RetroSummary",
    "TemplateMetrics",
    "ThreadDraft",
    "TrendScore",
    "analyze_week",
    "collect_response",
    "generate_thread",
    "load_selection",
    "load_thread",
    "main",
    "preview_thread",
    "run_friday",
    "run_monday",
    "run_wednesday",
    "save_selection",
    "save_thread",
    "score_template",
    "select_top_n",
    "summarize_week",
]
