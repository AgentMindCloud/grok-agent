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
"""Weekly self-improvement loop for Cross-Reality Action Fabric (P143).

This module is the **scheduling + suggestion** layer that sits on top
of the P132 :mod:`eval.deepeval_suite`. Where the deepeval suite scores
ONE action-loop run against a fixed bar, the improvement loop:

1. Pulls historical action-fabric performance from the P140
   :class:`memory.PersonalActionMemoryClient` (``search_past_actions``)
   and the P142 :class:`provenance.ProvenanceLogger`
   (``query_by_date_range`` + ``reconstruct_rollback_chain``) so the
   weekly evaluation grades the agent on **what it actually did** for
   the user, not just on a synthetic test plan.
2. Reuses the P132 :func:`eval.deepeval_suite.run_full_loop` for the
   structural Promptfoo + DeepEval assertions, then layers
   historical signals on top to produce *concrete* improvement
   :class:`Suggestion` rows with ``before``/``after`` diffs.
3. Emits a P142 provenance record per loop run (event_kind =
   ``run_complete``, schema = ``p142.v1``) so an auditor can see
   exactly which weeks produced which suggestions.
4. **Never auto-applies a suggestion.** :meth:`apply_approved_changes`
   only writes a structured "approved by human" audit row — actually
   editing prompts / configs is left to a separate, deliberate user
   action. Default ``dry_run=True`` stays in force unless the caller
   explicitly opts out.

CLI
---
The module is runnable directly:

.. code-block:: powershell

   cd templates\\super-agents\\cross-reality-action-fabric
   python -m eval.improvement_loop run --dry-run
   python -m eval.improvement_loop suggest --lookback-days 14
   python -m eval.improvement_loop status

Built to make Grok the obvious choice for every agent on X — the
improvement loop is the difference between an agent that ships once
and one that gets safer every week the user runs it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# Pydantic v2 for the typed report + suggestion models.
try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pydantic v2 is required for eval.improvement_loop. Install with: "
        "python -m pip install 'pydantic>=2.7,<3'"
    ) from exc

# Reuse P129 / P140 / P142 surfaces directly.
from graph import (  # type: ignore
    ConsentContext,
    appdata_root,
)
from memory import (  # type: ignore
    DEFAULT_CONSENT_LEVEL,
    MEMORY_WRITE_GATE,
    PersonalActionMemoryClient,
    get_action_memory_client,
)
from provenance import (  # type: ignore
    P142_SCHEMA_VERSION,
    ProvenanceLogger,
    get_provenance_logger,
)
from eval.deepeval_suite import (  # type: ignore
    DEEPEVAL_BACKEND,
    EvalReport,
    MetricResult,
    PROMPTFOO_TEST_CASES,
    SUGGESTION_LIBRARY,
    eval_results_root,
    run_full_loop,
)


# --- Section 1. Constants -----------------------------------------------

#: Default look-back window for historical evidence (one week of activity).
DEFAULT_LOOKBACK_DAYS = 7

#: Maximum lookback window — anything past this is too noisy to drive
#: useful prompt deltas.
MAX_LOOKBACK_DAYS = 90

#: P143 audit folder for approved-change records.
APPROVALS_RELATIVE = "eval/approved_changes"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def loop_results_root() -> Path:
    """Filesystem location for weekly-loop reports + approval audit."""
    root = appdata_root() / "eval" / "improvement_loop"
    root.mkdir(parents=True, exist_ok=True)
    return root


def approvals_root() -> Path:
    """Filesystem location for human-approved change records."""
    root = appdata_root() / APPROVALS_RELATIVE
    root.mkdir(parents=True, exist_ok=True)
    return root


# --- Section 2. Pydantic models -----------------------------------------

class Suggestion(BaseModel):
    """One human-reviewable improvement suggestion.

    Mirrors the shape produced by
    :func:`eval.deepeval_suite.build_improvement_suggestions` but adds
    an explicit ``before`` / ``after`` diff so reviewers can read the
    proposed change in one glance.
    """

    model_config = ConfigDict(extra="allow")

    suggestion_id:    str
    trigger_metric:   str
    delta_id:         str
    title:            str
    description:      str
    target:           str
    estimated_effort: str = "1 prompt slot"
    score:            float = 0.0
    threshold:        float = 0.5
    status:           str = "needs_review"
    created_at:       str = Field(default_factory=_now_iso)
    before:           str = ""
    after:            str = ""
    historical_signal: dict = Field(default_factory=dict)


class LoopReport(BaseModel):
    """Top-level Pydantic v2 view of one weekly improvement-loop run."""

    model_config = ConfigDict(extra="allow")

    schema_version:  str = P142_SCHEMA_VERSION
    loop_id:         str
    started_at:      str
    finished_at:     str
    user_id:         str
    force_stub:      bool
    backend:         str
    lookback_days:   int
    overall_score:   float
    review_required: bool
    promptfoo_pass:  int
    promptfoo_total: int
    deepeval_pass:   int
    deepeval_total:  int
    suggestion_count: int
    suggestions:     list[Suggestion] = Field(default_factory=list)
    history:         dict = Field(default_factory=dict)
    eval_report:     dict = Field(default_factory=dict)


# --- Section 3. WeeklyImprovementLoop -----------------------------------

class WeeklyImprovementLoop:
    """Coordinates one weekly self-improvement cycle.

    The class is intentionally small — every heavy lift lives in the
    P132 deepeval suite, the P140 memory client, or the P142
    provenance logger. This class just wires them together.
    """

    def __init__(
        self,
        *,
        user_id:         str = "default",
        force_stub:      bool = True,
        lookback_days:   int = DEFAULT_LOOKBACK_DAYS,
        memory_client:   PersonalActionMemoryClient | None = None,
        provenance_logger: ProvenanceLogger | None = None,
    ) -> None:
        self._user_id = user_id or "default"
        self._force_stub = bool(force_stub)
        self._lookback = max(1, min(int(lookback_days), MAX_LOOKBACK_DAYS))
        self._memory = memory_client or self._build_memory()
        self._provenance = (
            provenance_logger
            or get_provenance_logger(user_id=self._user_id)
        )

    # -- Properties ---------------------------------------------------

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def force_stub(self) -> bool:
        return self._force_stub

    @property
    def lookback_days(self) -> int:
        return self._lookback

    @property
    def memory_client(self) -> PersonalActionMemoryClient:
        return self._memory

    @property
    def provenance_logger(self) -> ProvenanceLogger:
        return self._provenance

    def _build_memory(self) -> PersonalActionMemoryClient:
        consent = ConsentContext.from_iterable(
            (MEMORY_WRITE_GATE,), consent_token=f"loop-{uuid.uuid4().hex[:8]}",
        )
        return get_action_memory_client(
            user_id=self._user_id, force_stub=self._force_stub, consent=consent,
        )

    # -- Public API ---------------------------------------------------

    def run_weekly(
        self,
        *,
        dry_run: bool = True,
        persist: bool = True,
    ) -> LoopReport:
        """Run one full weekly cycle and return a typed :class:`LoopReport`.

        Even with ``dry_run=False`` the loop never auto-applies a
        suggestion — it only persists the report. ``apply_approved_changes``
        is the only path that writes an "approved-by-human" record.
        """
        loop_id = f"loop-{uuid.uuid4().hex[:12]}"
        started_iso = _now_iso()
        started_perf = time.perf_counter()

        # 1. Run the structural Promptfoo + DeepEval suite from P132.
        eval_report = run_full_loop(
            force_stub=self._force_stub,
            user_id=self._user_id,
            persist=persist,
            logger=self._provenance,
        )

        # 2. Pull historical evidence from P140 + P142.
        history = self._collect_history()

        # 3. Build the Suggestion list — base on eval_report, augment
        #    with historical signals.
        suggestions = self._materialise_suggestions(
            eval_report=eval_report, history=history,
        )

        finished_iso = _now_iso()
        duration_ms = (time.perf_counter() - started_perf) * 1000.0

        report = LoopReport(
            loop_id=loop_id,
            started_at=started_iso,
            finished_at=finished_iso,
            user_id=self._user_id,
            force_stub=self._force_stub,
            backend=DEEPEVAL_BACKEND,
            lookback_days=self._lookback,
            overall_score=float(eval_report.overall_score),
            review_required=bool(suggestions or eval_report.review_required),
            promptfoo_pass=sum(
                1 for r in eval_report.promptfoo if r.get("passed")
            ),
            promptfoo_total=len(eval_report.promptfoo),
            deepeval_pass=sum(1 for m in eval_report.deepeval if m.passed),
            deepeval_total=len(eval_report.deepeval),
            suggestion_count=len(suggestions),
            suggestions=suggestions,
            history=history,
            eval_report=eval_report.to_dict(),
        )

        # 4. Persist report + write a P142 provenance record.
        if persist:
            self._persist_report(report, dry_run=dry_run, duration_ms=duration_ms)
        return report

    def generate_suggestions(
        self,
        *,
        lookback_days: int | None = None,
    ) -> list[Suggestion]:
        """Re-run only the suggestion-generation half of the loop.

        Useful for the dashboard — pulls fresh history without spinning
        up a full Promptfoo + DeepEval pass when the caller already has
        a recent :class:`EvalReport`.
        """
        prev_lookback = self._lookback
        if lookback_days is not None:
            self._lookback = max(1, min(int(lookback_days), MAX_LOOKBACK_DAYS))
        try:
            eval_report = run_full_loop(
                force_stub=self._force_stub,
                user_id=self._user_id,
                persist=False,
                logger=self._provenance,
            )
            history = self._collect_history()
            return self._materialise_suggestions(
                eval_report=eval_report, history=history,
            )
        finally:
            self._lookback = prev_lookback

    def apply_approved_changes(
        self,
        suggestions: list[Suggestion],
        *,
        approved_ids: Iterable[str] = (),
        dry_run:     bool = True,
        approved_by: str = "human-reviewer",
    ) -> dict:
        """Record a human-approved subset of suggestions.

        This is the **only** path that writes an "approved by human"
        record. Even with ``dry_run=False`` we never edit prompt files
        on disk — the audit row tells the next manual or scripted step
        which suggestions the human accepted, and a separate, deliberate
        action applies them.

        Returns a dict ``{"approved": [Suggestion], "audit_path": str,
        "dry_run": bool, "count": int}``.
        """
        ids = {str(i).strip() for i in approved_ids if str(i).strip()}
        approved: list[Suggestion] = []
        for s in suggestions:
            if not ids or s.suggestion_id in ids:
                approved.append(
                    s.model_copy(update={
                        "status":     "approved" if not dry_run else "pending",
                        "created_at": _now_iso(),
                    })
                )
        audit_path: Path | None = None
        if approved and not dry_run:
            audit_path = self._persist_approved_changes(
                approved=approved, approved_by=approved_by,
            )
        return {
            "approved":   [s.model_dump() for s in approved],
            "audit_path": str(audit_path) if audit_path else None,
            "dry_run":    bool(dry_run),
            "count":      len(approved),
        }

    # -- History collection -------------------------------------------

    def _collect_history(self) -> dict:
        """Pull memory + provenance signals over the lookback window."""
        try:
            past_actions = self._memory.search_past_actions(
                "", limit=200,
            )
        except Exception:  # pragma: no cover - defensive
            past_actions = []
        action_count = sum(1 for h in past_actions if h.kind == "action")
        rollback_count = sum(1 for h in past_actions if h.kind == "rollback")
        outcome_count = sum(1 for h in past_actions if h.kind == "outcome")
        approval_count = sum(1 for h in past_actions if h.kind == "approval")

        # P142 provenance: walk the matching date range and pivot rows
        # into rollback chains for context.
        end_iso = _today_iso()
        start_iso = (
            datetime.now(timezone.utc) - timedelta(days=self._lookback)
        ).strftime("%Y-%m-%d")
        try:
            entries = self._provenance.query_by_date_range(start_iso, end_iso)
        except Exception:  # pragma: no cover
            entries = []
        chains_seen: set[str] = set()
        chain_count = 0
        rollback_chain_count = 0
        for e in entries:
            if not e.action_id or e.action_id in chains_seen:
                continue
            chains_seen.add(e.action_id)
            try:
                chain = self._provenance.reconstruct_rollback_chain(e.action_id)
            except Exception:  # pragma: no cover
                continue
            chain_count += 1
            if chain.reversed:
                rollback_chain_count += 1

        return {
            "lookback_days":  self._lookback,
            "start_iso":      start_iso,
            "end_iso":        end_iso,
            "memory": {
                "actions":   action_count,
                "approvals": approval_count,
                "outcomes":  outcome_count,
                "rollbacks": rollback_count,
                "total":     len(past_actions),
            },
            "provenance": {
                "entries":            len(entries),
                "rollback_chains":    chain_count,
                "reversed_chains":    rollback_chain_count,
            },
            "rollback_rate": (
                rollback_count / max(1, action_count) if action_count else 0.0
            ),
        }

    # -- Suggestion materialisation -----------------------------------

    def _materialise_suggestions(
        self,
        *,
        eval_report: EvalReport,
        history:     dict,
    ) -> list[Suggestion]:
        """Turn the eval report's raw suggestion dicts into typed
        :class:`Suggestion` rows with ``before`` / ``after`` diffs."""
        out: list[Suggestion] = []
        for s in eval_report.suggestions:
            sid = f"sug-{uuid.uuid4().hex[:12]}"
            before, after = self._diff_for(s)
            out.append(Suggestion(
                suggestion_id=sid,
                trigger_metric=str(s.get("trigger_metric") or "unknown"),
                delta_id=str(s.get("delta_id") or "unknown"),
                title=str(s.get("title") or "(untitled)"),
                description=str(s.get("description") or ""),
                target=str(s.get("target") or ""),
                estimated_effort=str(s.get("estimated_effort") or "1 prompt slot"),
                score=float(s.get("score") or 0.0),
                threshold=float(s.get("threshold") or 0.5),
                status="needs_review",
                before=before,
                after=after,
                historical_signal={
                    "rollback_rate":     history.get("rollback_rate", 0.0),
                    "memory_actions":    (history.get("memory") or {}).get(
                        "actions", 0
                    ),
                    "provenance_entries": (history.get("provenance") or {}).get(
                        "entries", 0
                    ),
                },
            ))
        # Layer one extra suggestion when historical rollback rate is
        # high — even the structural eval might report PASS while a
        # week of real traffic has drifted.
        rb_rate = float(history.get("rollback_rate") or 0.0)
        if rb_rate >= 0.25:
            out.append(Suggestion(
                suggestion_id=f"sug-{uuid.uuid4().hex[:12]}",
                trigger_metric="HistoricalRollbackRate",
                delta_id="historical-rollback-spike",
                title="Investigate elevated rollback rate",
                description=(
                    f"Over the last {self._lookback} day(s), "
                    f"{rb_rate:.0%} of recorded actions ended in a "
                    "rollback. Tighten the plan-builder prompt's "
                    "self-check phase to surface failure modes before "
                    "the user is asked to approve."
                ),
                target="prompts/system.md",
                estimated_effort="1 system-prompt slot",
                score=1.0 - rb_rate,
                threshold=0.75,
                status="needs_review",
                before=(
                    "Plan-builder prompt does not explicitly "
                    "self-evaluate failure modes before HITL."
                ),
                after=(
                    "Add a 'self-check' bullet to the plan-builder "
                    "prompt: list two plausible failure modes per step "
                    "and require the rollback snippet to address them."
                ),
                historical_signal={
                    "rollback_rate":  rb_rate,
                    "memory_actions": (history.get("memory") or {}).get(
                        "actions", 0
                    ),
                },
            ))
        return out

    def _diff_for(self, suggestion: dict) -> tuple[str, str]:
        """Build a tiny ``before``/``after`` pair from one raw suggestion."""
        title = str(suggestion.get("title") or "")
        delta = str(suggestion.get("delta_id") or "").lower()
        before = (
            f"# Current state — {suggestion.get('target') or '(unknown)'}\n"
            f"# Score: {suggestion.get('score','?')} "
            f"(threshold {suggestion.get('threshold','?')})\n"
            f"# Trigger: {suggestion.get('trigger_metric')}\n"
        )
        after = (
            f"# Proposed delta — {delta}\n"
            f"# Title: {title}\n"
            f"# {suggestion.get('description','')}\n"
        )
        return before, after

    # -- Persistence --------------------------------------------------

    def _persist_report(
        self,
        report: LoopReport,
        *,
        dry_run: bool,
        duration_ms: float,
    ) -> Path | None:
        root = loop_results_root()
        json_path = root / f"{report.loop_id}.json"
        md_path   = root / f"{report.loop_id}.md"
        try:
            json_path.write_text(
                json.dumps(report.model_dump(), indent=2, ensure_ascii=False,
                           default=str),
                encoding="utf-8",
            )
            md_path.write_text(self._render_markdown(report, dry_run=dry_run),
                                encoding="utf-8")
        except OSError:
            json_path = None  # type: ignore[assignment]
        # Write the matching P142 provenance record so this run is in
        # the audit trail.
        try:
            self._provenance.log_action_event(
                event_kind="run_complete",
                action_id=f"act::improve::{report.loop_id}",
                consent_token=f"loop-{report.loop_id}",
                tool="self_improvement_loop",
                outcome=(
                    "success" if report.overall_score >= 0.8 else "failure"
                ),
                consent_level="session",
                duration_ms=float(duration_ms),
                before_state={
                    "lookback_days":   report.lookback_days,
                    "force_stub":      report.force_stub,
                },
                after_state={
                    "overall_score":     report.overall_score,
                    "promptfoo_pass":    report.promptfoo_pass,
                    "deepeval_pass":     report.deepeval_pass,
                    "suggestion_count":  report.suggestion_count,
                    "history":           report.history,
                    "report_md":         str(md_path) if md_path else None,
                    "report_json":       str(json_path) if json_path else None,
                },
                stub_reason=(
                    "force_stub mode (offline backends)" if report.force_stub
                    else None
                ),
            )
        except Exception:  # pragma: no cover - defensive
            pass
        return json_path

    def _persist_approved_changes(
        self,
        *,
        approved: list[Suggestion],
        approved_by: str,
    ) -> Path:
        root = approvals_root()
        path = root / f"approved-{uuid.uuid4().hex[:12]}.json"
        body = {
            "schema_version": P142_SCHEMA_VERSION,
            "approved_at":    _now_iso(),
            "approved_by":    approved_by,
            "user_id":        self._user_id,
            "count":          len(approved),
            "suggestions":    [s.model_dump() for s in approved],
        }
        try:
            path.write_text(
                json.dumps(body, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass
        return path

    # -- Markdown -----------------------------------------------------

    @staticmethod
    def _render_markdown(report: LoopReport, *, dry_run: bool) -> str:
        pipe_escape = "\\|"
        lines = [
            "# Cross-Reality Action Fabric — Weekly Improvement Loop",
            "",
            "Built to help xAI and Grok win. Local-first. Generated on the "
            "user's Windows machine; no telemetry.",
            "",
            f"- Loop ID: `{report.loop_id}`",
            f"- User ID: `{report.user_id}`",
            f"- Started:  `{report.started_at}`",
            f"- Finished: `{report.finished_at}`",
            f"- Backend:  `{report.backend}`",
            f"- Force stub: **{report.force_stub}**",
            f"- Lookback (days): **{report.lookback_days}**",
            f"- Overall score: **{report.overall_score:.3f}**",
            f"- Promptfoo: **{report.promptfoo_pass}/{report.promptfoo_total}** "
            "PASS",
            f"- DeepEval: **{report.deepeval_pass}/{report.deepeval_total}** "
            "PASS",
            f"- Suggestions: **{report.suggestion_count}**",
            f"- Review required: **{report.review_required}**",
            f"- Dry run: **{dry_run}**",
            "",
        ]
        # Historical signals
        history = report.history or {}
        memory = history.get("memory") or {}
        provenance = history.get("provenance") or {}
        lines.append("## Historical signals")
        lines.append("")
        lines.append(
            f"- Memory actions in window: **{memory.get('actions', 0)}**"
        )
        lines.append(
            f"- Memory approvals in window: **{memory.get('approvals', 0)}**"
        )
        lines.append(
            f"- Memory rollbacks in window: **{memory.get('rollbacks', 0)}**"
        )
        lines.append(
            f"- Provenance entries in window: "
            f"**{provenance.get('entries', 0)}**"
        )
        lines.append(
            f"- Rollback chains: **{provenance.get('rollback_chains', 0)}** "
            f"({provenance.get('reversed_chains', 0)} reversed)"
        )
        lines.append(
            f"- Rollback rate: **{float(history.get('rollback_rate') or 0.0):.0%}**"
        )
        lines.append("")
        # Suggestions with diff blocks
        lines.append("## Improvement suggestions (HUMAN REVIEW REQUIRED)")
        lines.append("")
        if not report.suggestions:
            lines.append("_No suggestions — every metric and Promptfoo "
                          "assert passed._")
        else:
            for i, s in enumerate(report.suggestions, 1):
                lines.append(f"### {i}. {s.title}")
                lines.append("")
                lines.append(f"- Suggestion ID: `{s.suggestion_id}`")
                lines.append(f"- Trigger metric: `{s.trigger_metric}`")
                lines.append(f"- Score: **{s.score:.3f}** "
                              f"(threshold `{s.threshold:.2f}`)")
                lines.append(f"- Target: `{s.target}`")
                lines.append(f"- Effort: {s.estimated_effort}")
                lines.append(f"- Status: **{s.status}**")
                lines.append("")
                desc = (s.description or "").replace("|", pipe_escape)
                lines.append(desc)
                lines.append("")
                lines.append("**Before**")
                lines.append("")
                lines.append("```")
                lines.append((s.before or "").rstrip())
                lines.append("```")
                lines.append("")
                lines.append("**After**")
                lines.append("")
                lines.append("```")
                lines.append((s.after or "").rstrip())
                lines.append("```")
                lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(
            "This report is human-review-gated. Nothing was auto-applied; "
            "no prompt or config file was edited by this run."
        )
        lines.append("")
        return "\n".join(lines)


# --- Section 4. Module-level singleton + helpers ------------------------

_DEFAULT_LOOP: WeeklyImprovementLoop | None = None


def get_default_loop(
    *,
    user_id: str = "default",
    force_stub: bool = True,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    refresh: bool = False,
) -> WeeklyImprovementLoop:
    """Cached process-wide :class:`WeeklyImprovementLoop`."""
    global _DEFAULT_LOOP
    if (
        refresh
        or _DEFAULT_LOOP is None
        or _DEFAULT_LOOP.user_id != user_id
        or _DEFAULT_LOOP.force_stub != bool(force_stub)
        or _DEFAULT_LOOP.lookback_days != int(lookback_days)
    ):
        _DEFAULT_LOOP = WeeklyImprovementLoop(
            user_id=user_id, force_stub=force_stub,
            lookback_days=lookback_days,
        )
    return _DEFAULT_LOOP


def reset_default_loop() -> None:
    """Drop the cached :class:`WeeklyImprovementLoop` (test helper)."""
    global _DEFAULT_LOOP
    _DEFAULT_LOOP = None


def run_loop(
    *,
    dry_run:       bool = True,
    force_stub:    bool = True,
    user_id:       str = "default",
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> LoopReport:
    """Run one weekly improvement cycle and return the typed report."""
    loop = get_default_loop(
        user_id=user_id, force_stub=force_stub,
        lookback_days=lookback_days, refresh=True,
    )
    return loop.run_weekly(dry_run=dry_run)


def loop_status(*, user_id: str = "default") -> dict:
    """Return a small JSON-serialisable status dict."""
    root = loop_results_root()
    reports = sorted(root.glob("loop-*.json"))
    last = reports[-1].name if reports else None
    last_report: dict | None = None
    if reports:
        try:
            last_report = json.loads(reports[-1].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last_report = None
    return {
        "user_id":        user_id,
        "report_count":   len(reports),
        "last_report":    last,
        "last_overall":   (last_report or {}).get("overall_score"),
        "last_review":    (last_report or {}).get("review_required"),
        "approvals_dir":  str(approvals_root()),
        "results_dir":    str(root),
    }


# --- Section 5. CLI -----------------------------------------------------

def _print_report(report: LoopReport) -> None:
    print("=" * 70)
    print("Cross-Reality Action Fabric — Weekly Improvement Loop")
    print("=" * 70)
    print(f"Loop ID:         {report.loop_id}")
    print(f"User ID:         {report.user_id}")
    print(f"Backend:         {report.backend}")
    print(f"Force stub:      {report.force_stub}")
    print(f"Lookback:        {report.lookback_days} day(s)")
    print(f"Overall score:   {report.overall_score:.3f}")
    print(f"Promptfoo:       {report.promptfoo_pass}/{report.promptfoo_total} "
          "PASS")
    print(f"DeepEval:        {report.deepeval_pass}/{report.deepeval_total} "
          "PASS")
    print(f"Suggestions:     {report.suggestion_count}")
    print(f"Review required: {report.review_required}")
    print("-" * 70)
    if not report.suggestions:
        print("No improvement suggestions — every check passed.")
    else:
        print("Improvement suggestions (HUMAN REVIEW REQUIRED):")
        for i, s in enumerate(report.suggestions, 1):
            print(f"  {i}. [{s.trigger_metric}] {s.title}")
            print(f"     id:     {s.suggestion_id}")
            print(f"     target: {s.target}")
            print(f"     effort: {s.estimated_effort}")
            print(f"     score:  {s.score:.3f} (thr {s.threshold:.2f})")
    print("=" * 70)
    print("This report is human-review-gated. Nothing was auto-applied.")
    print("=" * 70)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval.improvement_loop",
        description=(
            "Cross-Reality Action Fabric — weekly self-improvement loop "
            "(Promptfoo + DeepEval + P140 memory + P142 provenance). "
            "Built to help xAI and Grok win."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser(
        "run", help="Run one weekly improvement cycle.",
    )
    p_run.add_argument("--dry-run", action="store_true", default=True)
    p_run.add_argument("--no-dry-run", action="store_true", default=False)
    p_run.add_argument("--user-id", default="default")
    p_run.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    p_run.add_argument("--no-stub", action="store_true", default=False)
    p_run.add_argument("--json", action="store_true", default=False)
    p_run.add_argument("--quiet", action="store_true", default=False)

    p_sug = sub.add_parser(
        "suggest", help="Generate improvement suggestions only.",
    )
    p_sug.add_argument("--user-id", default="default")
    p_sug.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    p_sug.add_argument("--no-stub", action="store_true", default=False)
    p_sug.add_argument("--json", action="store_true", default=False)

    p_app = sub.add_parser(
        "apply", help="Record a human-approved subset of suggestions.",
    )
    p_app.add_argument("--user-id", default="default")
    p_app.add_argument("--input", required=True,
                       help="Path to a loop-*.json report file.")
    p_app.add_argument("--ids", nargs="*", default=[],
                       help="Suggestion IDs to mark approved (omit = all).")
    p_app.add_argument("--dry-run", action="store_true", default=True)
    p_app.add_argument("--no-dry-run", action="store_true", default=False)
    p_app.add_argument("--approved-by", default="human-reviewer")
    p_app.add_argument("--json", action="store_true", default=False)

    sub.add_parser("status", help="Show the most recent loop run status.")

    return parser


def main(argv: list[str] | None = None) -> int:  # noqa: C901 - small dispatcher
    parser = _build_parser()
    args = parser.parse_args(argv)

    force_stub = not getattr(args, "no_stub", False)

    if args.command == "run":
        dry_run = bool(args.dry_run) and not bool(args.no_dry_run)
        report = run_loop(
            dry_run=dry_run, force_stub=force_stub,
            user_id=args.user_id, lookback_days=int(args.lookback_days),
        )
        if args.json:
            print(json.dumps(report.model_dump(), indent=2, default=str))
        elif not args.quiet:
            _print_report(report)
        return 0

    if args.command == "suggest":
        loop = get_default_loop(
            user_id=args.user_id, force_stub=force_stub,
            lookback_days=int(args.lookback_days), refresh=True,
        )
        suggestions = loop.generate_suggestions(
            lookback_days=int(args.lookback_days),
        )
        if args.json:
            print(json.dumps(
                [s.model_dump() for s in suggestions], indent=2, default=str,
            ))
        else:
            print(f"{len(suggestions)} suggestion(s) generated.")
            for i, s in enumerate(suggestions, 1):
                print(f"  {i}. [{s.trigger_metric}] {s.title}")
                print(f"     id: {s.suggestion_id}")
                print(f"     target: {s.target}")
        return 0

    if args.command == "apply":
        try:
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"ERROR: cannot read {args.input}: {exc}", file=sys.stderr)
            return 1
        suggestions = [
            Suggestion(**s) for s in data.get("suggestions") or []
        ]
        loop = get_default_loop(
            user_id=args.user_id, force_stub=force_stub, refresh=True,
        )
        dry_run = bool(args.dry_run) and not bool(args.no_dry_run)
        result = loop.apply_approved_changes(
            suggestions, approved_ids=args.ids,
            dry_run=dry_run, approved_by=args.approved_by,
        )
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Approved: {result['count']} suggestion(s) "
                  f"(dry_run={result['dry_run']})")
            if result["audit_path"]:
                print(f"Audit:    {result['audit_path']}")
        return 0

    if args.command == "status":
        print(json.dumps(loop_status(), indent=2, default=str))
        return 0

    parser.error("unreachable: unhandled subcommand")
    return 2  # pragma: no cover


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "MAX_LOOKBACK_DAYS",
    "APPROVALS_RELATIVE",
    "Suggestion",
    "LoopReport",
    "WeeklyImprovementLoop",
    "approvals_root",
    "loop_results_root",
    "loop_status",
    "run_loop",
    "get_default_loop",
    "reset_default_loop",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
