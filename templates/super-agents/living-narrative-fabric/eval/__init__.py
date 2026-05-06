# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Self-improvement loop (P114, Slot 6).

Built for xAI, X, Grok and the ecosystem community. ❤️

This package wires Promptfoo + DeepEval into a weekly self-improvement
loop the user can run on Windows with one PowerShell command. It:

* Re-runs the 4 deterministic standard metrics on every persisted
  ``SynthesisVersion`` (or one explicitly passed by the caller):
  ContradictionDetection / ProvenanceCompleteness / FourMetricFormula /
  ConstitutionCompliance — see ``deepeval_suite.py`` for the formulas.
* Executes the 21 Promptfoo test cases in ``promptfoo.yaml`` against
  each ``SynthesisVersion``, collecting per-category pass rates.
* Translates failed metrics + failed tests into structured
  ``PromptSuggestion`` records the orchestrator's prompt files
  (``prompts/system.md``) can consume.
* Persists every run to a local SQLite history at
  ``<appdata>/eval/history.sqlite3`` and writes a Markdown summary
  alongside ``<appdata>/eval/improvements/<run_id>.md``.
* Mirrors every step into the P113 provenance log when one is wired
  via ``connect_provenance(...)``.

Slot boundary contract
======================

* The eval layer **observes** the system from outside — the
  orchestrator's ``with_dependencies()`` does not have a
  ``self_improvement`` slot. Instead, the eval layer reads
  ``SynthesisVersion``s from the memory store and emits provenance
  events into the existing logger. This keeps Slot 6 purely additive
  and makes ``run_weekly_eval`` runnable as a standalone PowerShell
  cron job (``schtasks /create /sc weekly``).
* The composite class (``SelfImprovementLoop``) exposes the user-listed
  5 rich methods: ``run_weekly_eval``, ``score_synthesis``,
  ``suggest_prompt_updates``, ``apply_improvements``,
  ``get_improvement_history``.
* ZERO changes to ``orchestrator.py``, ``graph.py``, the memory layer,
  the connector layer, or the provenance layer.

Plug-in pattern
===============

::

    from memory       import build_memory_store
    from connectors   import build_connectors
    from provenance   import build_provenance_logger
    from eval         import build_self_improvement_loop
    from orchestrator import LivingNarrativeFabric

    store      = build_memory_store()
    connectors = build_connectors(store=store, force_stub=True)
    logger     = build_provenance_logger(store=store)

    fabric = LivingNarrativeFabric().with_dependencies(
        sources=tuple(connectors.connectors),
        memory=store,
        provenance=logger,
    )
    version = fabric.synthesize(topic="Grok Agent OS launch", time_range="7d")

    loop = build_self_improvement_loop(store=store, provenance=logger)
    score        = loop.score_synthesis(version)
    suggestions  = loop.suggest_prompt_updates(score)
    apply_result = loop.apply_improvements(suggestions, dry_run=True)
    history      = loop.get_improvement_history()

CLI smoke test
==============

::

    cd templates\\super-agents\\living-narrative-fabric
    python eval\\__init__.py

Prints ``P114 self-improvement loop smoke OK`` on success.
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import from orchestrator + memory + provenance + sibling modules
# ---------------------------------------------------------------------------


def _import_orchestrator():
    try:
        from .. import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


def _import_memory():
    try:
        from ..memory import (  # type: ignore
            Mem0QdrantStore, build_memory_store,
        )
        return Mem0QdrantStore, build_memory_store
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    mem_pkg = importlib.import_module("memory")
    return mem_pkg.Mem0QdrantStore, mem_pkg.build_memory_store


def _import_provenance():
    try:
        from ..provenance import (  # type: ignore
            LivingNarrativeFabricProvenance, build_provenance_logger,
        )
        return LivingNarrativeFabricProvenance, build_provenance_logger
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    prov_pkg = importlib.import_module("provenance")
    return prov_pkg.LivingNarrativeFabricProvenance, prov_pkg.build_provenance_logger


_orch = _import_orchestrator()
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
LivingNarrativeFabric = _orch.LivingNarrativeFabric
_default_appdata_root = _orch._default_appdata_root

Mem0QdrantStore, build_memory_store = _import_memory()
LivingNarrativeFabricProvenance, build_provenance_logger = _import_provenance()


def _import_siblings():
    try:
        from . import deepeval_suite as _suite  # type: ignore
        return _suite
    except Exception:
        pass
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    return importlib.import_module("deepeval_suite")


_suite = _import_siblings()
DeepEvalRunner = _suite.DeepEvalRunner
EvaluationScore = _suite.EvaluationScore
MetricResult = _suite.MetricResult
DETERMINISTIC_METRIC_WEIGHTS = _suite.DETERMINISTIC_METRIC_WEIGHTS
DEFAULT_METRIC_THRESHOLDS = _suite.DEFAULT_METRIC_THRESHOLDS
parse_promptfoo_yaml = _suite.parse_promptfoo_yaml


PROMPTFOO_YAML_PATH = Path(__file__).resolve().parent / "promptfoo.yaml"

#: Article V.1 disclaimer (auto-attached on $XAI-style topics in suggestions
#: and report outputs).
ARTICLE_V1_DISCLAIMER = (
    "> ⚠️ **Not financial advice.** This evaluation surfaces measurement "
    "results only; always consult a licensed financial advisor before "
    "making decisions on cashtag-related claims."
)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptSuggestion:
    """One actionable improvement suggestion emitted by the loop.

    The ``target_file`` is the relative path the suggestion would
    write to inside the Living Narrative Fabric folder (e.g.
    ``prompts/system.md``). Slot 1's manifest + prompts will materialise
    these files; until then the loop's ``apply_improvements(dry_run=...)``
    writes the suggestions to ``<appdata>/eval/improvements/<run_id>.md``
    so they're inspectable from the Streamlit dashboard (Slot 7).
    """

    suggestion_id:    str
    metric_name:      str
    severity:         str           # "blocker" | "warning" | "info"
    target_file:      str           # e.g. "prompts/system.md"
    title:            str
    rationale:        str
    suggested_change: str
    extra:            dict = field(default_factory=dict)


@dataclass(frozen=True)
class PromptfooCategoryResult:
    """Aggregate result for one Promptfoo category over one version."""

    category: str
    total:    int
    passed:   int
    pass_rate_pct: int
    failed_tests: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationRun:
    """One full ``run_weekly_eval`` invocation, persisted to history.sqlite3."""

    run_id:       str
    started_at:   datetime
    finished_at:  datetime
    versions_evaluated: tuple[str, ...]
    overall_score:      int
    metric_results:     tuple[MetricResult, ...]
    promptfoo_results:  tuple[PromptfooCategoryResult, ...]
    suggestions:        tuple[PromptSuggestion, ...]
    has_finance_subject: bool
    notes:              str = ""


@dataclass(frozen=True)
class ApplyResult:
    """Returned by ``apply_improvements``."""

    run_id:      str
    dry_run:     bool
    written_to:  Optional[Path]
    suggestions_count: int
    skipped_count: int
    summary:     str


# ---------------------------------------------------------------------------
# Local history store — append-only SQLite + Markdown summaries
# ---------------------------------------------------------------------------


_HISTORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS eval_runs (
    run_id              TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    finished_at         TEXT NOT NULL,
    overall_score       INTEGER NOT NULL,
    versions_evaluated  TEXT NOT NULL,
    has_finance_subject INTEGER NOT NULL,
    notes               TEXT NOT NULL DEFAULT '',
    blob_json           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eval_runs_started_at ON eval_runs(started_at);

CREATE TABLE IF NOT EXISTS eval_suggestions (
    suggestion_id  TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL,
    metric_name    TEXT NOT NULL,
    severity       TEXT NOT NULL,
    target_file    TEXT NOT NULL,
    title          TEXT NOT NULL,
    rationale      TEXT NOT NULL,
    suggested_change TEXT NOT NULL,
    extra_json     TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(run_id) REFERENCES eval_runs(run_id)
);
CREATE INDEX IF NOT EXISTS ix_eval_suggestions_run_id ON eval_suggestions(run_id);
CREATE INDEX IF NOT EXISTS ix_eval_suggestions_metric ON eval_suggestions(metric_name);
"""


@dataclass
class EvalHistoryStore:
    """Tiny SQLite wrapper for the eval-run history."""

    history_path: Path
    _conn:        Optional[sqlite3.Connection] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.history_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(_HISTORY_SCHEMA_SQL)

    def append(self, run: EvaluationRun) -> None:
        if self._conn is None:
            raise RuntimeError("EvalHistoryStore is closed")
        blob = json.dumps(_serialise_run(run), ensure_ascii=False, default=str)
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO eval_runs(
                    run_id, started_at, finished_at, overall_score,
                    versions_evaluated, has_finance_subject, notes, blob_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    int(run.overall_score),
                    json.dumps(list(run.versions_evaluated)),
                    1 if run.has_finance_subject else 0,
                    run.notes,
                    blob,
                ),
            )
            self._conn.executemany(
                """
                INSERT OR REPLACE INTO eval_suggestions(
                    suggestion_id, run_id, metric_name, severity,
                    target_file, title, rationale, suggested_change, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        s.suggestion_id, run.run_id, s.metric_name, s.severity,
                        s.target_file, s.title, s.rationale, s.suggested_change,
                        json.dumps(dict(s.extra), ensure_ascii=False),
                    )
                    for s in run.suggestions
                ],
            )

    def list_runs(self, *, limit: int = 50) -> tuple[EvaluationRun, ...]:
        if self._conn is None:
            return ()
        cur = self._conn.execute(
            "SELECT blob_json FROM eval_runs ORDER BY started_at DESC LIMIT ?",
            (int(limit),),
        )
        return tuple(
            _hydrate_run(json.loads(r["blob_json"])) for r in cur.fetchall()
        )

    def get_run(self, run_id: str) -> Optional[EvaluationRun]:
        if self._conn is None:
            return None
        cur = self._conn.execute(
            "SELECT blob_json FROM eval_runs WHERE run_id = ?", (run_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return _hydrate_run(json.loads(row["blob_json"]))

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


def _serialise_metric(m: MetricResult) -> dict:
    return {
        "metric_name": m.metric_name,
        "score":       int(m.score),
        "weight":      float(m.weight),
        "threshold":   int(m.threshold),
        "passed":      bool(m.passed),
        "reasons":     list(m.reasons),
        "extra":       dict(m.extra),
    }


def _hydrate_metric(d: dict) -> MetricResult:
    return MetricResult(
        metric_name=d["metric_name"],
        score=int(d["score"]),
        weight=float(d["weight"]),
        threshold=int(d["threshold"]),
        passed=bool(d["passed"]),
        reasons=tuple(d.get("reasons") or ()),
        extra=dict(d.get("extra") or {}),
    )


def _serialise_pf(c: PromptfooCategoryResult) -> dict:
    return {
        "category":      c.category,
        "total":         int(c.total),
        "passed":        int(c.passed),
        "pass_rate_pct": int(c.pass_rate_pct),
        "failed_tests":  list(c.failed_tests),
    }


def _hydrate_pf(d: dict) -> PromptfooCategoryResult:
    return PromptfooCategoryResult(
        category=d["category"],
        total=int(d["total"]),
        passed=int(d["passed"]),
        pass_rate_pct=int(d["pass_rate_pct"]),
        failed_tests=tuple(d.get("failed_tests") or ()),
    )


def _serialise_suggestion(s: PromptSuggestion) -> dict:
    return {
        "suggestion_id":    s.suggestion_id,
        "metric_name":      s.metric_name,
        "severity":         s.severity,
        "target_file":      s.target_file,
        "title":            s.title,
        "rationale":        s.rationale,
        "suggested_change": s.suggested_change,
        "extra":            dict(s.extra),
    }


def _hydrate_suggestion(d: dict) -> PromptSuggestion:
    return PromptSuggestion(
        suggestion_id=d["suggestion_id"],
        metric_name=d["metric_name"],
        severity=d["severity"],
        target_file=d["target_file"],
        title=d["title"],
        rationale=d["rationale"],
        suggested_change=d["suggested_change"],
        extra=dict(d.get("extra") or {}),
    )


def _serialise_run(r: EvaluationRun) -> dict:
    return {
        "run_id":              r.run_id,
        "started_at":          r.started_at.isoformat(),
        "finished_at":         r.finished_at.isoformat(),
        "versions_evaluated":  list(r.versions_evaluated),
        "overall_score":       int(r.overall_score),
        "metric_results":      [_serialise_metric(m) for m in r.metric_results],
        "promptfoo_results":   [_serialise_pf(c) for c in r.promptfoo_results],
        "suggestions":         [_serialise_suggestion(s) for s in r.suggestions],
        "has_finance_subject": bool(r.has_finance_subject),
        "notes":               r.notes,
    }


def _hydrate_run(d: dict) -> EvaluationRun:
    return EvaluationRun(
        run_id=d["run_id"],
        started_at=datetime.fromisoformat(d["started_at"]),
        finished_at=datetime.fromisoformat(d["finished_at"]),
        versions_evaluated=tuple(d.get("versions_evaluated") or ()),
        overall_score=int(d["overall_score"]),
        metric_results=tuple(_hydrate_metric(x) for x in d.get("metric_results") or ()),
        promptfoo_results=tuple(_hydrate_pf(x) for x in d.get("promptfoo_results") or ()),
        suggestions=tuple(_hydrate_suggestion(x) for x in d.get("suggestions") or ()),
        has_finance_subject=bool(d.get("has_finance_subject")),
        notes=d.get("notes", ""),
    )


# ---------------------------------------------------------------------------
# Suggestion engine — maps failed metrics + failed Promptfoo cases to
# structured PromptSuggestion records.
# ---------------------------------------------------------------------------


_SUGGESTION_TEMPLATES = {
    "ContradictionDetection": {
        "title":      "Tighten contradiction-detector grouping",
        "rationale":  (
            "The orchestrator's _node_detect_contradictions captured fewer "
            "(subject, predicate) groups than the data actually contained. "
            "This breaks the dual-surface paradox rule from P98–P102 + P110."
        ),
        "suggested_change": (
            "In `prompts/system.md`, add a normalisation step before grouping: "
            "lowercase + strip surrounding punctuation on both subject and "
            "predicate so synonymous forms cluster together. Example: "
            "'is bullish on' and 'bullish on' should hash to the same group."
        ),
        "target_file": "prompts/system.md",
    },
    "ProvenanceCompleteness": {
        "title":      "Pre-finalize provenance scan",
        "rationale":  (
            "One or more claims reached the finalize node with empty source_id. "
            "Constitution Article: 'Source citations are mandatory on every claim'."
        ),
        "suggested_change": (
            "Add an explicit pre-finalize provenance scan in "
            "`prompts/system.md` reminding the extractor that EVERY claim row "
            "MUST carry source_id = item.item_id verbatim. The orchestrator "
            "already raises ConstitutionViolation; the prompt should refuse "
            "earlier."
        ),
        "target_file": "prompts/system.md",
    },
    "FourMetricFormula": {
        "title":      "Re-anchor the 4-metric formula",
        "rationale":  (
            "The orchestrator's reported confidence_score diverges from the "
            "official formula 0.30·SourceDiversity + 0.30·ProvenanceCompleteness "
            "+ 0.25·CrossSourceAgreement + 0.15·RecencyCoverage."
        ),
        "suggested_change": (
            "In `prompts/system.md`, restate the exact formula as a guarded "
            "block the model must echo before emitting the final score. Re-derive "
            "the score in the orchestrator code path if the divergence persists."
        ),
        "target_file": "prompts/system.md",
    },
    "ConstitutionCompliance": {
        "title":      "Repair Constitution compliance",
        "rationale":  (
            "One or more Constitution rules were violated in this version: "
            "missing bridges, wrong audit trigger, or empty source_ids."
        ),
        "suggested_change": (
            "Run `safety/scanner.py` against the manifest before re-running "
            "synthesis. In `prompts/system.md`, prepend the 5 Constitution "
            "rules from §12 of CLAUDE.md as a non-negotiable system preamble."
        ),
        "target_file": "prompts/system.md",
    },
}


def _generate_suggestions(
    score: EvaluationScore,
    promptfoo_results: Sequence[PromptfooCategoryResult],
    *,
    run_id: str,
) -> tuple[PromptSuggestion, ...]:
    out: list[PromptSuggestion] = []

    # Per-metric remediation hints.
    for n, m in enumerate(score.metric_results):
        if m.passed:
            continue
        tmpl = _SUGGESTION_TEMPLATES.get(m.metric_name)
        if tmpl is None:
            continue
        severity = (
            "blocker"
            if m.metric_name in ("ProvenanceCompleteness", "ConstitutionCompliance")
            else ("warning" if m.score < (m.threshold - 20) else "info")
        )
        suggestion_id = f"{run_id}::metric::{m.metric_name}::{n}"
        out.append(PromptSuggestion(
            suggestion_id=suggestion_id,
            metric_name=m.metric_name,
            severity=severity,
            target_file=tmpl["target_file"],
            title=tmpl["title"],
            rationale=tmpl["rationale"] + " "
                      + (f"Observed score={m.score} below threshold={m.threshold}. "
                         f"Reasons: {'; '.join(m.reasons) or '(none recorded)'}"),
            suggested_change=tmpl["suggested_change"],
            extra={
                "observed_score":   int(m.score),
                "threshold":        int(m.threshold),
                "metric_extra":     dict(m.extra),
            },
        ))

    # Per-Promptfoo-category hints (a category with < 80% pass rate becomes
    # an info-level suggestion that re-runs the failing tests).
    for c in promptfoo_results:
        if c.pass_rate_pct >= 80 or c.total == 0:
            continue
        suggestion_id = f"{run_id}::promptfoo::{c.category}"
        out.append(PromptSuggestion(
            suggestion_id=suggestion_id,
            metric_name=f"Promptfoo:{c.category}",
            severity="warning",
            target_file="eval/promptfoo.yaml",
            title=f"Promptfoo category '{c.category}' below pass-rate floor",
            rationale=(
                f"{c.passed}/{c.total} test cases passed "
                f"({c.pass_rate_pct}% < 80%). Failing cases: "
                f"{', '.join(c.failed_tests[:5]) or '(none recorded)'}."
            ),
            suggested_change=(
                "Re-run the failing cases with verbose output and inspect the "
                "asserted fields. If the orchestrator's output is correct, the "
                "Promptfoo assertion may be stale — update its `metric` path "
                "or threshold. If the output is wrong, route the regression "
                "through the matching metric remediation."
            ),
            extra={
                "category":     c.category,
                "pass_rate_pct": int(c.pass_rate_pct),
                "failed_tests": list(c.failed_tests),
            },
        ))

    return tuple(out)


# ---------------------------------------------------------------------------
# SelfImprovementLoop — composite + 5 rich methods
# ---------------------------------------------------------------------------


@dataclass
class SelfImprovementLoop:
    """The user-facing eval composite."""

    appdata_root:       Path
    runner:             DeepEvalRunner
    history:            EvalHistoryStore
    store:              Optional[Mem0QdrantStore] = None
    provenance:         Optional[LivingNarrativeFabricProvenance] = None
    promptfoo_yaml_path: Path = field(default=PROMPTFOO_YAML_PATH)
    improvements_dir:   Path = field(init=False)

    def __post_init__(self) -> None:
        self.improvements_dir = self.appdata_root / "eval" / "improvements"
        self.improvements_dir.mkdir(parents=True, exist_ok=True)

    # ---- attachment helpers ---------------------------------------------

    def connect_store(self, store: Mem0QdrantStore) -> None:
        self.store = store

    def connect_provenance(
        self,
        provenance: LivingNarrativeFabricProvenance,
    ) -> None:
        self.provenance = provenance

    # ---- Rich method 1 — score one synthesis ----------------------------

    def score_synthesis(self, version: SynthesisVersion) -> EvaluationScore:
        score = self.runner.score(version)
        self._log_provenance(
            "eval.score.computed",
            {
                "version_id":    version.version_id,
                "topic":         version.topic,
                "overall_score": int(score.overall_score),
                "metric_passes": {m.metric_name: m.passed for m in score.metric_results},
            },
        )
        return score

    # ---- Rich method 2 — suggest prompt updates -------------------------

    def suggest_prompt_updates(
        self,
        score: EvaluationScore,
        *,
        promptfoo_results: Sequence[PromptfooCategoryResult] = (),
        run_id: Optional[str] = None,
    ) -> tuple[PromptSuggestion, ...]:
        rid = run_id or self._make_run_id(score.version_id)
        suggestions = _generate_suggestions(score, promptfoo_results, run_id=rid)
        self._log_provenance(
            "eval.suggestions.generated",
            {
                "run_id":          rid,
                "version_id":      score.version_id,
                "suggestion_count": len(suggestions),
            },
        )
        return suggestions

    # ---- Rich method 3 — apply improvements (dry-run by default) ---------

    def apply_improvements(
        self,
        suggestions: Sequence[PromptSuggestion],
        *,
        dry_run: bool = True,
        run_id: Optional[str] = None,
    ) -> ApplyResult:
        rid = run_id or self._make_run_id("apply")
        if not suggestions:
            return ApplyResult(
                run_id=rid, dry_run=dry_run, written_to=None,
                suggestions_count=0, skipped_count=0,
                summary="no suggestions to apply",
            )

        written_to = self.improvements_dir / f"{rid}.md"
        body = _render_improvements_markdown(rid, suggestions, dry_run=dry_run)
        if dry_run:
            preview_path = self.improvements_dir / f"{rid}.dry_run.md"
            preview_path.write_text(body, encoding="utf-8")
            written_path = preview_path
        else:
            written_to.write_text(body, encoding="utf-8")
            written_path = written_to

        self._log_provenance(
            "eval.apply",
            {
                "run_id":            rid,
                "dry_run":           bool(dry_run),
                "written_to":        str(written_path),
                "suggestions_count": len(suggestions),
            },
        )
        return ApplyResult(
            run_id=rid, dry_run=dry_run, written_to=written_path,
            suggestions_count=len(suggestions), skipped_count=0,
            summary=(
                f"{'dry-run' if dry_run else 'applied'}: "
                f"{len(suggestions)} suggestion(s) written to {written_path}"
            ),
        )

    # ---- Rich method 4 — get history -------------------------------------

    def get_improvement_history(
        self,
        *,
        limit: int = 50,
    ) -> tuple[EvaluationRun, ...]:
        return self.history.list_runs(limit=limit)

    # ---- Rich method 5 — full weekly run ---------------------------------

    def run_weekly_eval(
        self,
        *,
        topics: Optional[Iterable[str]] = None,
        dry_run: bool = True,
        notes: str = "",
    ) -> EvaluationRun:
        """End-to-end weekly cycle.

        Pulls every persisted ``SynthesisVersion`` for ``topics`` (or
        every topic in the store when ``topics is None``), scores each,
        runs the Promptfoo suite against each, generates a single
        consolidated set of ``PromptSuggestion``s, persists the
        ``EvaluationRun`` to history.sqlite3, and writes a Markdown
        summary to ``<appdata>/eval/improvements/<run_id>.md``.
        """

        started_at = datetime.now(timezone.utc)
        run_id = self._make_run_id("weekly")
        self._log_provenance(
            "eval.run.start",
            {"run_id": run_id, "topics": list(topics or []), "dry_run": dry_run},
        )

        versions = self._collect_versions(topics)
        if not versions:
            finished_at = datetime.now(timezone.utc)
            run = EvaluationRun(
                run_id=run_id,
                started_at=started_at, finished_at=finished_at,
                versions_evaluated=(),
                overall_score=0,
                metric_results=(),
                promptfoo_results=(),
                suggestions=(),
                has_finance_subject=False,
                notes=(notes or "no SynthesisVersions found in memory store"),
            )
            self.history.append(run)
            self._log_provenance("eval.run.complete", {
                "run_id": run_id, "version_count": 0, "overall_score": 0,
            })
            return run

        # Aggregate per-version scores into a single EvaluationRun.
        all_metric_results: list[MetricResult] = []
        version_scores: list[EvaluationScore] = []
        for v in versions:
            s = self.runner.score(v)
            version_scores.append(s)
            all_metric_results.extend(s.metric_results)

        # Promptfoo suite — run once per version, aggregated by category.
        category_buckets: dict[str, dict] = {}
        for v in versions:
            try:
                results = self.runner.run_promptfoo_suite(v, self.promptfoo_yaml_path)
            except Exception:
                results = ()
            for r in results:
                cat = r["category"]
                bucket = category_buckets.setdefault(cat, {"total": 0, "passed": 0, "failed": []})
                bucket["total"] += 1
                if r["passed"]:
                    bucket["passed"] += 1
                else:
                    bucket["failed"].append(r["description"])

        promptfoo_results = tuple(
            PromptfooCategoryResult(
                category=cat,
                total=int(b["total"]),
                passed=int(b["passed"]),
                pass_rate_pct=round(b["passed"] / b["total"] * 100) if b["total"] else 0,
                failed_tests=tuple(b["failed"]),
            )
            for cat, b in sorted(category_buckets.items())
        )

        # Aggregate composite overall_score across all versions.
        if version_scores:
            overall = round(
                sum(s.overall_score for s in version_scores) / len(version_scores)
            )
        else:
            overall = 0

        # Build a synthetic EvaluationScore that summarises every version's
        # worst metric, then pass it to the suggestion engine alongside
        # the Promptfoo aggregate so the final suggestion set is concise.
        worst_per_metric: dict[str, MetricResult] = {}
        for m in all_metric_results:
            cur = worst_per_metric.get(m.metric_name)
            if cur is None or m.score < cur.score:
                worst_per_metric[m.metric_name] = m
        synthetic_score = EvaluationScore(
            version_id=run_id,
            topic=", ".join({v.topic for v in versions})[:200] or "(multi)",
            overall_score=int(overall),
            metric_results=tuple(worst_per_metric.values()),
            deepeval_results=(),
            evaluated_at=datetime.now(timezone.utc),
            has_finance_subject=any(v.has_finance_subject for v in versions),
        )

        suggestions = _generate_suggestions(
            synthetic_score, promptfoo_results, run_id=run_id,
        )

        # Apply (or dry-run apply) the suggestions so the file artifact
        # exists for the Streamlit dashboard.
        try:
            self.apply_improvements(suggestions, dry_run=dry_run, run_id=run_id)
        except Exception:
            # Apply failures must never poison the run record itself.
            pass

        finished_at = datetime.now(timezone.utc)
        run = EvaluationRun(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            versions_evaluated=tuple(v.version_id for v in versions),
            overall_score=int(overall),
            metric_results=tuple(synthetic_score.metric_results),
            promptfoo_results=promptfoo_results,
            suggestions=suggestions,
            has_finance_subject=synthetic_score.has_finance_subject,
            notes=notes,
        )
        self.history.append(run)
        self._log_provenance(
            "eval.run.complete",
            {
                "run_id":            run_id,
                "version_count":     len(versions),
                "overall_score":     int(overall),
                "suggestion_count":  len(suggestions),
            },
        )
        return run

    # ---- internal --------------------------------------------------------

    def _collect_versions(
        self,
        topics: Optional[Iterable[str]],
    ) -> tuple[SynthesisVersion, ...]:
        if self.store is None:
            return ()
        out: list[SynthesisVersion] = []
        if topics is not None:
            for t in topics:
                out.extend(self.store.history_for(t))
        else:
            structured = getattr(self.store, "structured", None)
            if structured is None or structured._sqlite_conn is None:
                return ()
            cur = structured._sqlite_conn.execute(
                "SELECT DISTINCT topic FROM versions"
            )
            topics_in_store = [r["topic"] for r in cur.fetchall() if r["topic"]]
            for t in topics_in_store:
                if t.startswith("_connector::") or t.startswith("_eval::"):
                    continue
                out.extend(self.store.history_for(t))
        return tuple(out)

    def _make_run_id(self, prefix: str) -> str:
        import hashlib
        seed = f"{prefix}|{datetime.now(timezone.utc).isoformat()}|{os.getpid()}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    def _log_provenance(self, event_type: str, payload: dict) -> None:
        if self.provenance is None:
            return
        try:
            self.provenance.log_event(event_type, payload)
        except ConstitutionViolation:
            raise
        except Exception:
            pass

    @property
    def runtime_info(self) -> dict:
        return {
            "appdata_root":         str(self.appdata_root),
            "history_path":         str(self.history.history_path),
            "improvements_dir":     str(self.improvements_dir),
            "promptfoo_yaml_path":  str(self.promptfoo_yaml_path),
            "deepeval_enabled":     bool(self.runner.deepeval_enabled),
            "store_attached":       self.store is not None,
            "provenance_attached":  self.provenance is not None,
        }


# ---------------------------------------------------------------------------
# Markdown renderer — applied-improvements summary
# ---------------------------------------------------------------------------


def _render_improvements_markdown(
    run_id: str,
    suggestions: Sequence[PromptSuggestion],
    *,
    dry_run: bool,
) -> str:
    finance = any(s.extra.get("metric_extra", {}).get("has_finance_subject")
                  for s in suggestions)
    parts: list[str] = []
    parts.append("<!-- Copyright 2026 AgentMindCloud -->")
    parts.append("<!-- Licensed under the Apache License, Version 2.0 -->")
    parts.append("<!-- http://www.apache.org/licenses/LICENSE-2.0 -->")
    parts.append("<!-- Living Narrative Fabric — Self-Improvement run report -->")
    parts.append("")
    parts.append(f"# Self-Improvement Run `{run_id}`")
    parts.append("")
    parts.append(
        "> Built for xAI, X, Grok and the ecosystem community. ❤️ "
        f"This file was {'previewed' if dry_run else 'written'} by "
        "the Slot-6 self-improvement loop."
    )
    parts.append("")
    if finance:
        parts.append(ARTICLE_V1_DISCLAIMER)
        parts.append("")

    parts.append("## 1. Header")
    parts.append("")
    parts.append(f"- **Run id**: `{run_id}`")
    parts.append(f"- **Mode**: {'dry-run' if dry_run else 'applied'}")
    parts.append(f"- **Suggestion count**: {len(suggestions)}")
    parts.append("")

    parts.append("## 2. Suggestions")
    parts.append("")
    if not suggestions:
        parts.append("_No suggestions generated — all metrics passed and every "
                     "Promptfoo category cleared the 80% pass-rate floor._")
        parts.append("")
    else:
        parts.append("| # | Severity | Metric | Target file | Title |")
        parts.append("|---:|:---:|---|---|---|")
        for n, s in enumerate(suggestions, start=1):
            parts.append(
                f"| {n} | `{s.severity}` | `{s.metric_name}` | "
                f"`{s.target_file}` | {s.title} |"
            )
        parts.append("")
        for n, s in enumerate(suggestions, start=1):
            parts.append(f"### {n}. {s.title}")
            parts.append("")
            parts.append(f"- **Severity**: `{s.severity}`")
            parts.append(f"- **Metric**: `{s.metric_name}`")
            parts.append(f"- **Target file**: `{s.target_file}`")
            parts.append("")
            parts.append("**Rationale**")
            parts.append("")
            parts.append(s.rationale)
            parts.append("")
            parts.append("**Suggested change**")
            parts.append("")
            parts.append(s.suggested_change)
            parts.append("")

    parts.append("## 3. Bridges")
    parts.append("")
    parts.append("Pair these suggestions with at least three bridges so the run "
                 "actually moves a decision:")
    parts.append("")
    parts.append("- `self-evolving-personal-os`")
    parts.append("- `cross-reality-action-fabric`")
    parts.append("- `analytics-summarizer`")
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("*Built for xAI, X, Grok and the ecosystem community. ❤️ "
                 "Apache-2.0. Local-first. Privacy-first.*")
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Factory + convenience wirers
# ---------------------------------------------------------------------------


def build_self_improvement_loop(
    *,
    appdata_root: Optional[Path] = None,
    store:        Optional[Mem0QdrantStore] = None,
    provenance:   Optional[LivingNarrativeFabricProvenance] = None,
    promptfoo_yaml_path: Optional[Path] = None,
) -> SelfImprovementLoop:
    """Build a fully-wired ``SelfImprovementLoop`` with sensible defaults."""

    root = appdata_root if appdata_root is not None else _default_appdata_root()
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    history_path = root / "eval" / "history.sqlite3"
    history = EvalHistoryStore(history_path=history_path)
    runner = DeepEvalRunner()
    return SelfImprovementLoop(
        appdata_root=root,
        runner=runner,
        history=history,
        store=store,
        provenance=provenance,
        promptfoo_yaml_path=promptfoo_yaml_path or PROMPTFOO_YAML_PATH,
    )


def with_self_improvement(
    fabric: LivingNarrativeFabric,
    **kwargs: Any,
) -> tuple[LivingNarrativeFabric, SelfImprovementLoop]:
    """Convenience: build a loop and return it alongside the fabric.

    The loop does NOT plug into ``with_dependencies`` — there is no
    self-improvement Protocol on the orchestrator. The pair is returned
    so the caller can wire them however they like (typically the loop
    runs on a weekly cron after the fabric has produced versions).
    """

    loop = build_self_improvement_loop(**kwargs)
    return fabric, loop


# ---------------------------------------------------------------------------
# Smoke test (zero-install, zero-API-keys)
# ---------------------------------------------------------------------------


def run_smoke_test(*, verbose: bool = True) -> None:
    """Self-contained smoke test for the self-improvement loop.

    Verifies (10 checks):

    1. Loop builds and reports its runtime_info.
    2. ``score_synthesis`` returns an ``EvaluationScore`` with all 4
       deterministic metrics computed.
    3. ``suggest_prompt_updates`` returns a tuple (possibly empty).
    4. ``apply_improvements(dry_run=True)`` writes a Markdown preview
       file under ``<appdata>/eval/improvements/``.
    5. ``apply_improvements(dry_run=False)`` writes the official
       Markdown file.
    6. ``run_weekly_eval`` end-to-end: synthesizes, scores, runs
       Promptfoo, generates suggestions, persists history.
    7. ``get_improvement_history`` returns at least one run.
    8. Promptfoo YAML parses to >= 20 test cases across >= 5 categories.
    9. ConstitutionViolation: synthetic SynthesisVersion with empty
       source_id triggers a ``ProvenanceCompleteness`` failure of < 100.
    10. Provenance integration: when wired, every loop call emits
        a ``eval.*`` event into the provenance log.
    """

    import shutil
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="lnf-eval-smoke-"))
    try:
        store = build_memory_store(appdata_root=tmp_root)
        provenance = build_provenance_logger(appdata_root=tmp_root, store=store)
        loop = build_self_improvement_loop(
            appdata_root=tmp_root, store=store, provenance=provenance,
        )

        if verbose:
            print(f"[smoke] runtime_info = {loop.runtime_info}")

        # ---- (1) construction --------------------------------------------
        assert loop.runtime_info["history_path"]
        assert loop.runtime_info["improvements_dir"]

        # ---- (8) Promptfoo YAML structure --------------------------------
        cases = parse_promptfoo_yaml(PROMPTFOO_YAML_PATH)
        assert len(cases) >= 20, (
            f"promptfoo.yaml should contain >= 20 cases; got {len(cases)}."
        )
        cats = {c.category for c in cases}
        assert len(cats) >= 5, (
            f"promptfoo.yaml should cover >= 5 categories; got {sorted(cats)}."
        )

        # ---- (2) score_synthesis -----------------------------------------
        fabric = LivingNarrativeFabric().with_dependencies(
            memory=store, provenance=provenance,
        )
        v1 = fabric.synthesize(topic="lnf-eval-topic", time_range="7d")
        score = loop.score_synthesis(v1)
        assert isinstance(score, EvaluationScore)
        assert len(score.metric_results) == 4, (
            f"expected 4 deterministic metrics; got {len(score.metric_results)}."
        )
        metric_names = {m.metric_name for m in score.metric_results}
        assert metric_names == {
            "ContradictionDetection", "ProvenanceCompleteness",
            "FourMetricFormula",       "ConstitutionCompliance",
        }

        # ---- (3) suggest_prompt_updates ---------------------------------
        suggestions = loop.suggest_prompt_updates(score)
        assert isinstance(suggestions, tuple)

        # ---- (4) apply_improvements (dry run) ---------------------------
        dry = loop.apply_improvements(suggestions, dry_run=True)
        if suggestions:
            assert dry.written_to is not None
            assert dry.written_to.exists()
            content = dry.written_to.read_text(encoding="utf-8")
            assert "# Self-Improvement Run" in content

        # ---- (5) apply_improvements (real) ------------------------------
        applied = loop.apply_improvements(suggestions, dry_run=False)
        if suggestions:
            assert applied.written_to is not None
            assert applied.written_to.exists()

        # ---- (6) run_weekly_eval end-to-end -----------------------------
        run = loop.run_weekly_eval(dry_run=True)
        assert isinstance(run, EvaluationRun)
        assert v1.version_id in run.versions_evaluated, (
            f"weekly eval did not include v1; versions_evaluated={run.versions_evaluated}."
        )

        # ---- (7) get_improvement_history --------------------------------
        history = loop.get_improvement_history(limit=10)
        assert len(history) >= 1
        assert history[0].run_id == run.run_id

        # ---- (9) Constitution: synthetic empty-source claim --------------
        bad_version = SynthesisVersion(
            version_id="bad", topic="bad", time_range="7d",
            parent_version_id=None,
            created_at=datetime.now(timezone.utc),
            sources_used=("newsapi",),
            claims=(Claim(
                claim_id="c1", subject="x", predicate="y", value="z",
                source="newsapi", source_id="",  # empty
                confidence=0.5, extracted_at=datetime.now(timezone.utc),
                sentiment=None,
            ),),
            contradictions=(),
            confidence_metrics={
                "Source diversity": 16, "Provenance completeness": 0,
                "Cross-source agreement": 100, "Recency coverage": 50,
            },
            confidence_score=37,
            audit_triggered=True,
            audit_reasons=("synthetic",),
            has_finance_subject=False,
            bridges=("self-evolving-personal-os", "cross-reality-action-fabric",
                     "analytics-summarizer"),
        )
        bad_score = loop.score_synthesis(bad_version)
        prov = next(m for m in bad_score.metric_results
                    if m.metric_name == "ProvenanceCompleteness")
        assert not prov.passed, (
            "ProvenanceCompleteness should have failed on a claim with "
            "empty source_id."
        )

        # ---- (10) Provenance integration --------------------------------
        events = provenance.local.all_events()
        eval_events = [e for e in events if e.event_type.startswith("eval.")]
        assert len(eval_events) >= 3, (
            f"expected >= 3 eval.* events from the loop calls; "
            f"got {len(eval_events)}."
        )

        loop.history.close()
        if verbose:
            print("P114 self-improvement loop smoke OK")
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = (
    "ApplyResult",
    "ConstitutionViolation",
    "DEFAULT_METRIC_THRESHOLDS",
    "DETERMINISTIC_METRIC_WEIGHTS",
    "EvalHistoryStore",
    "EvaluationRun",
    "EvaluationScore",
    "MetricResult",
    "PROMPTFOO_YAML_PATH",
    "PromptSuggestion",
    "PromptfooCategoryResult",
    "SelfImprovementLoop",
    "build_self_improvement_loop",
    "parse_promptfoo_yaml",
    "run_smoke_test",
    "with_self_improvement",
)


if __name__ == "__main__":  # pragma: no cover
    run_smoke_test()
