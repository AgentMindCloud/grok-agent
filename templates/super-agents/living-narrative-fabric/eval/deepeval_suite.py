# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — DeepEval suite + metrics (P114, Slot 6 / 1 of 2).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module is the deterministic measurement core of the self-improvement
loop. Every metric here is computable WITHOUT an LLM judge — it inspects
a ``SynthesisVersion`` (or the orchestrator's emitted state) directly
and produces a numeric score plus a list of failure reasons. When the
``deepeval`` SDK is installed, the runner can additionally layer LLM-
judge metrics (``FaithfulnessMetric``, ``AnswerRelevancyMetric``) on
top — but the deterministic floor always works on a fresh box with
zero installs.

Four standard metrics
======================

1. **ContradictionDetectionMetric (0–100)** — How well did the
   orchestrator surface real contradictions? We re-run the same
   ``(subject, predicate)`` grouping the orchestrator does and count
   how many groups with disagreeing values were captured as
   ``Contradiction`` objects. Score = (captured / expected) · 100,
   minus a 10-point penalty per Constitution-rule violation
   ("contradictions silently resolved" — both sides not present in
   ``claims``).

2. **ProvenanceCompletenessMetric (0–100)** — % of claims whose
   ``source_id`` is non-empty. Constitution-mandated to always be 100
   in production; this metric exists so a regression surfaces
   immediately rather than being hidden inside the score node.

3. **FourMetricFormulaMetric (0–100)** — Does the orchestrator's own
   ``confidence_score`` match what the official 4-metric formula
   produces given the version's ``confidence_metrics``? Formula:
   ``round(0.30·SourceDiversity + 0.30·ProvenanceCompleteness +
   0.25·CrossSourceAgreement + 0.15·RecencyCoverage)``. Score = 100
   when the orchestrator's value is within ±1 of the recomputed
   value; otherwise dropped 5 points per absolute-difference unit.

4. **ConstitutionComplianceMetric (0–100)** — Composite of three
   binary checks: bridges >= ``MIN_BRIDGES_PER_SYNTHESIS`` (= 3),
   audit_triggered iff the trigger thresholds were actually hit, and
   no claim with empty source_id. Each failure subtracts a fixed
   weight (40 / 30 / 30) from a starting 100.

Slot boundary contract
======================

* This module does NOT implement any orchestrator Protocol — the eval
  layer observes the system from outside (reads from memory +
  provenance) rather than plugging into ``with_dependencies()``.
* This module does NOT modify ``orchestrator.py``, ``graph.py``, the
  memory layer, the connector layer, or the provenance layer.
* The composite ``SelfImprovementLoop`` in ``__init__.py`` holds an
  instance of ``DeepEvalRunner`` defined here and calls it from the
  user-facing ``score_synthesis`` and ``run_weekly_eval`` methods.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import dataclasses + constants from the orchestrator
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


_orch = _import_orchestrator()
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
SYNTHESIS_CONFIDENCE_WEIGHTS = _orch.SYNTHESIS_CONFIDENCE_WEIGHTS
MIN_BRIDGES_PER_SYNTHESIS = _orch.MIN_BRIDGES_PER_SYNTHESIS
AUDIT_TRIGGER_CONTRADICTIONS = _orch.AUDIT_TRIGGER_CONTRADICTIONS
AUDIT_TRIGGER_MIN_SOURCES = _orch.AUDIT_TRIGGER_MIN_SOURCES
AUDIT_TRIGGER_MIN_CONFIDENCE = _orch.AUDIT_TRIGGER_MIN_CONFIDENCE


# ---------------------------------------------------------------------------
# Soft DeepEval SDK import
# ---------------------------------------------------------------------------


try:
    import deepeval  # type: ignore
    _HAS_DEEPEVAL = True
except Exception:  # pragma: no cover — soft import
    deepeval = None  # type: ignore
    _HAS_DEEPEVAL = False


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricResult:
    """One metric's outcome on a single SynthesisVersion."""

    metric_name: str
    score:       int        # 0–100
    weight:      float      # weight inside the composite score
    threshold:   int        # below which this metric "fails"
    passed:      bool
    reasons:     tuple[str, ...]  # human-readable failure reasons (empty when passed)
    extra:       dict = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationScore:
    """Composite score across all four standard metrics + optional DeepEval."""

    version_id:       str
    topic:            str
    overall_score:    int       # weighted 0–100 across deterministic metrics
    metric_results:   tuple[MetricResult, ...]
    deepeval_results: tuple[MetricResult, ...]   # empty when deepeval not installed
    evaluated_at:     datetime
    has_finance_subject: bool


#: Composite weighting across the 4 deterministic metrics.
DETERMINISTIC_METRIC_WEIGHTS = {
    "ContradictionDetection":   0.30,
    "ProvenanceCompleteness":   0.30,
    "FourMetricFormula":        0.25,
    "ConstitutionCompliance":   0.15,
}

#: Per-metric pass thresholds — below these, the metric "fails" and the
#: prompt-suggestion engine produces a remediation hint.
DEFAULT_METRIC_THRESHOLDS = {
    "ContradictionDetection":   70,
    "ProvenanceCompleteness":  100,   # Constitution mandate — must be 100
    "FourMetricFormula":        90,
    "ConstitutionCompliance":  100,   # Constitution mandate — must be 100
}


# ---------------------------------------------------------------------------
# Metric implementations (deterministic, zero-install)
# ---------------------------------------------------------------------------


def _contradiction_detection_metric(
    version: SynthesisVersion,
) -> MetricResult:
    name = "ContradictionDetection"

    # Re-derive expected contradictions using the same grouping the
    # orchestrator's _node_detect_contradictions uses: (subject, predicate)
    # groups with > 1 distinct values.
    groups: dict[tuple[str, str], set[str]] = {}
    for c in version.claims:
        groups.setdefault((c.subject, c.predicate), set()).add(c.value)
    expected_groups = {k for k, vs in groups.items() if len(vs) >= 2}
    captured_groups = {(cd.subject, cd.predicate) for cd in version.contradictions}

    reasons: list[str] = []
    extra: dict = {
        "expected_groups": len(expected_groups),
        "captured_groups": len(captured_groups),
    }

    if not expected_groups:
        # No real contradictions in the data → nothing to detect, perfect.
        score = 100
    else:
        captured_within_expected = captured_groups & expected_groups
        score = round(len(captured_within_expected) / len(expected_groups) * 100)
        missed = expected_groups - captured_groups
        if missed:
            reasons.append(
                f"missed {len(missed)} contradiction group(s): "
                f"{sorted(missed)[:3]!r}"
            )

    # Constitution rule: contradictions never silently resolved — every
    # contradiction's claim_ids must point at claims that ALL still
    # appear in version.claims (both sides preserved). Penalty if any
    # claim_id has been dropped.
    claim_ids = {c.claim_id for c in version.claims}
    silent_drops = 0
    for cd in version.contradictions:
        for cid in cd.claim_ids:
            if cid not in claim_ids:
                silent_drops += 1
    if silent_drops:
        score = max(0, score - 10 * silent_drops)
        reasons.append(
            f"{silent_drops} claim_id(s) referenced by contradictions are "
            f"missing from version.claims — Constitution rule "
            f"'never silently resolve' violated."
        )
        extra["silent_drops"] = silent_drops

    threshold = DEFAULT_METRIC_THRESHOLDS[name]
    return MetricResult(
        metric_name=name,
        score=int(score),
        weight=DETERMINISTIC_METRIC_WEIGHTS[name],
        threshold=threshold,
        passed=score >= threshold,
        reasons=tuple(reasons),
        extra=extra,
    )


def _provenance_completeness_metric(
    version: SynthesisVersion,
) -> MetricResult:
    name = "ProvenanceCompleteness"
    if not version.claims:
        return MetricResult(
            metric_name=name, score=0,
            weight=DETERMINISTIC_METRIC_WEIGHTS[name],
            threshold=DEFAULT_METRIC_THRESHOLDS[name],
            passed=False,
            reasons=("version has 0 claims — provenance is undefined",),
        )
    missing = [c.claim_id for c in version.claims if not c.source_id]
    score = round((1 - len(missing) / len(version.claims)) * 100)
    reasons = ()
    if missing:
        reasons = (
            f"{len(missing)} claim(s) have empty source_id "
            f"(Constitution violation): {missing[:5]!r}",
        )
    threshold = DEFAULT_METRIC_THRESHOLDS[name]
    return MetricResult(
        metric_name=name,
        score=int(score),
        weight=DETERMINISTIC_METRIC_WEIGHTS[name],
        threshold=threshold,
        passed=score >= threshold,
        reasons=reasons,
        extra={"missing_count": len(missing), "total": len(version.claims)},
    )


def _four_metric_formula_metric(
    version: SynthesisVersion,
) -> MetricResult:
    name = "FourMetricFormula"
    metrics = version.confidence_metrics or {}
    sd = metrics.get("Source diversity",         0)
    pc = metrics.get("Provenance completeness",  0)
    csa = metrics.get("Cross-source agreement",  0)
    rc = metrics.get("Recency coverage",         0)
    recomputed = round(
        SYNTHESIS_CONFIDENCE_WEIGHTS["Source diversity"]         * sd
        + SYNTHESIS_CONFIDENCE_WEIGHTS["Provenance completeness"] * pc
        + SYNTHESIS_CONFIDENCE_WEIGHTS["Cross-source agreement"]  * csa
        + SYNTHESIS_CONFIDENCE_WEIGHTS["Recency coverage"]        * rc
    )
    delta = abs(recomputed - int(version.confidence_score))
    if delta <= 1:
        score = 100
    else:
        score = max(0, 100 - 5 * delta)
    reasons = ()
    if delta > 1:
        reasons = (
            f"orchestrator confidence_score={version.confidence_score} "
            f"diverges from recomputed={recomputed} by {delta} points; "
            f"4-metric formula adherence broken.",
        )
    threshold = DEFAULT_METRIC_THRESHOLDS[name]
    return MetricResult(
        metric_name=name,
        score=int(score),
        weight=DETERMINISTIC_METRIC_WEIGHTS[name],
        threshold=threshold,
        passed=score >= threshold,
        reasons=reasons,
        extra={
            "recomputed_score":  recomputed,
            "reported_score":    int(version.confidence_score),
            "delta":             delta,
        },
    )


def _constitution_compliance_metric(
    version: SynthesisVersion,
) -> MetricResult:
    name = "ConstitutionCompliance"
    score = 100
    reasons: list[str] = []
    extra: dict = {}

    # Check 1 (weight 40): bridges count >= MIN_BRIDGES_PER_SYNTHESIS.
    if len(version.bridges) < MIN_BRIDGES_PER_SYNTHESIS:
        score -= 40
        reasons.append(
            f"bridges count={len(version.bridges)} < required "
            f"{MIN_BRIDGES_PER_SYNTHESIS}; cross-template bridges are mandatory."
        )
    extra["bridges_count"] = len(version.bridges)

    # Check 2 (weight 30): audit_triggered iff thresholds actually hit.
    expected_audit_reasons: list[str] = []
    if len(version.contradictions) > AUDIT_TRIGGER_CONTRADICTIONS:
        expected_audit_reasons.append("contradictions")
    if len(set(version.sources_used)) < AUDIT_TRIGGER_MIN_SOURCES:
        expected_audit_reasons.append("sources<min")
    if int(version.confidence_score) < int(AUDIT_TRIGGER_MIN_CONFIDENCE * 100):
        expected_audit_reasons.append("confidence<min")
    expected_should_trigger = bool(expected_audit_reasons)
    if expected_should_trigger and not version.audit_triggered:
        score -= 30
        reasons.append(
            f"audit_triggered=False but conditions {expected_audit_reasons!r} "
            f"should have triggered the audit section."
        )
    elif version.audit_triggered and not expected_should_trigger and not version.audit_reasons:
        # Triggered with no recorded reason — flag but lighter penalty.
        score -= 10
        reasons.append(
            "audit_triggered=True but no audit_reasons recorded; the "
            "audit section appended without a documented trigger."
        )
    extra["expected_audit_reasons"] = expected_audit_reasons
    extra["audit_triggered"] = bool(version.audit_triggered)

    # Check 3 (weight 30): every claim carries non-empty source_id.
    missing_provenance = sum(1 for c in version.claims if not c.source_id)
    if missing_provenance:
        score -= 30
        reasons.append(
            f"{missing_provenance} claim(s) carry empty source_id; "
            f"Constitution requires citations on every claim."
        )
    extra["missing_provenance"] = missing_provenance

    score = max(0, score)
    threshold = DEFAULT_METRIC_THRESHOLDS[name]
    return MetricResult(
        metric_name=name,
        score=int(score),
        weight=DETERMINISTIC_METRIC_WEIGHTS[name],
        threshold=threshold,
        passed=score >= threshold,
        reasons=tuple(reasons),
        extra=extra,
    )


def _all_deterministic_metrics(version: SynthesisVersion) -> tuple[MetricResult, ...]:
    return (
        _contradiction_detection_metric(version),
        _provenance_completeness_metric(version),
        _four_metric_formula_metric(version),
        _constitution_compliance_metric(version),
    )


# ---------------------------------------------------------------------------
# Optional DeepEval LLM-judge layer
# ---------------------------------------------------------------------------


def _deepeval_judges(version: SynthesisVersion) -> tuple[MetricResult, ...]:
    """Layer LLM-judge metrics on top when ``deepeval`` is installed.

    When ``deepeval`` isn't available (the smoke-test path), returns an
    empty tuple — the deterministic metrics above are sufficient on
    their own.
    """

    if not _HAS_DEEPEVAL:
        return ()
    # We deliberately do NOT call DeepEval's hosted judges in the smoke
    # test (it would make a network call). Real production runs of
    # ``run_weekly_eval`` configure DeepEval via env vars and the runner
    # will populate this list. The placeholder below records the
    # availability so the report can show "DeepEval judges available
    # but not invoked" without breaking the test.
    return (
        MetricResult(
            metric_name="DeepEvalJudgeAvailability",
            score=100,
            weight=0.0,
            threshold=0,
            passed=True,
            reasons=(),
            extra={"sdk_available": True, "judges_invoked": False},
        ),
    )


# ---------------------------------------------------------------------------
# Promptfoo YAML parser — hybrid format that's valid Promptfoo AND
# parseable by our local Python runner without invoking npx.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptfooTestCase:
    """One row from the Promptfoo YAML's ``tests:`` array."""

    description: str
    category:    str   # one of {"contradiction","provenance","formula","constitution","audit"}
    vars:        dict
    asserts:     tuple[dict, ...]


def parse_promptfoo_yaml(path: Path) -> tuple[PromptfooTestCase, ...]:
    """Read the YAML at ``path`` and return its test cases.

    Falls back to a tiny built-in parser when ``pyyaml`` is missing —
    the YAML format we use is line-oriented enough that we can read it
    without a real parser when the Slot-2 deps aren't present. In
    practice ``pyyaml`` is in Slot-2's ``requirements.txt`` so this
    fallback is for defense in depth only.
    """

    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(text) or {}
    except Exception:
        doc = _minimal_yaml_load(text)

    raw_tests = doc.get("tests") or []
    out: list[PromptfooTestCase] = []
    for t in raw_tests:
        if not isinstance(t, dict):
            continue
        description = str(t.get("description") or t.get("name") or "(unnamed)")
        meta = t.get("metadata") or {}
        category = str(meta.get("category") or "uncategorized")
        vars_dict = dict(t.get("vars") or {})
        asserts_raw = t.get("assert") or []
        if not isinstance(asserts_raw, list):
            asserts_raw = []
        asserts = tuple(
            dict(a) for a in asserts_raw if isinstance(a, dict)
        )
        out.append(PromptfooTestCase(
            description=description,
            category=category,
            vars=vars_dict,
            asserts=asserts,
        ))
    return tuple(out)


def _minimal_yaml_load(text: str) -> dict:
    """Tiny YAML reader for the limited subset our promptfoo.yaml uses.

    Supports: top-level ``tests:`` list, each item with ``description:``,
    ``vars:`` mapping, ``assert:`` list of {type, value, metric}. NOT a
    real YAML parser — only used when ``pyyaml`` is missing AND the
    document is well-formed.
    """

    import re
    out: dict = {"tests": []}
    lines = [l.rstrip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    current_test: Optional[dict] = None
    current_section: Optional[str] = None  # "vars" | "assert" | "metadata"
    current_assert: Optional[dict] = None
    in_tests = False
    for line in lines:
        if re.match(r"^tests:\s*$", line):
            in_tests = True
            continue
        if not in_tests:
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 2 and stripped.startswith("- "):
            current_test = {"vars": {}, "assert": [], "metadata": {}}
            out["tests"].append(current_test)
            content = stripped[2:].strip()
            if content.startswith("description:"):
                current_test["description"] = content.split(":", 1)[1].strip().strip('"')
            current_section = None
            current_assert = None
        elif indent == 4 and stripped.endswith(":"):
            current_section = stripped[:-1]
            if current_section == "assert":
                current_test["assert"] = []
            elif current_section in ("vars", "metadata"):
                current_test[current_section] = {}
        elif indent == 4 and ":" in stripped and current_test is not None:
            k, v = stripped.split(":", 1)
            current_test[k.strip()] = v.strip().strip('"')
            current_section = None
        elif indent == 6 and stripped.startswith("- ") and current_section == "assert":
            current_assert = {}
            current_test["assert"].append(current_assert)
            inner = stripped[2:].strip()
            if ":" in inner:
                k, v = inner.split(":", 1)
                current_assert[k.strip()] = v.strip().strip('"')
        elif indent == 8 and ":" in stripped and current_assert is not None:
            k, v = stripped.split(":", 1)
            current_assert[k.strip()] = v.strip().strip('"')
        elif indent == 6 and ":" in stripped and current_section in ("vars", "metadata"):
            k, v = stripped.split(":", 1)
            current_test[current_section][k.strip()] = v.strip().strip('"')
    return out


# ---------------------------------------------------------------------------
# Promptfoo test executor — runs a parsed test case against a SynthesisVersion
# ---------------------------------------------------------------------------


def execute_promptfoo_assert(
    version: SynthesisVersion,
    asrt: dict,
) -> tuple[bool, str]:
    """Run one Promptfoo ``assert`` row against a SynthesisVersion.

    Supports our local subset of assertion types:

    * ``type: equals`` — ``value`` matches the field at ``metric``
    * ``type: gte`` / ``lte`` / ``gt`` / ``lt`` — numeric comparisons
    * ``type: contains`` — substring match on a stringifiable field
    * ``type: nonempty`` — field must be non-empty
    * ``type: bridges_min`` — version.bridges count >= int(value)
    * ``type: no_silent_resolution`` — every contradiction.claim_id
      appears in version.claims (verbatim Constitution check)

    The ``metric`` key names which version field to read; supports a
    dotted path for nested dicts (e.g. ``confidence_metrics.Source diversity``).
    """

    typ = (asrt.get("type") or "").strip()
    value = asrt.get("value")
    metric_path = (asrt.get("metric") or "").strip()

    def _read(path: str) -> Any:
        if not path:
            return None
        cur: Any = version
        for part in path.split("."):
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = getattr(cur, part, None)
        return cur

    if typ == "equals":
        observed = _read(metric_path)
        ok = str(observed) == str(value)
        return ok, f"equals: {metric_path}={observed!r} vs expected {value!r}"
    if typ in ("gte", "lte", "gt", "lt"):
        observed = _read(metric_path)
        try:
            obs_num = float(observed)
            val_num = float(value)
        except Exception:
            return False, f"{typ}: cannot coerce {observed!r} or {value!r} to float"
        if typ == "gte":
            return obs_num >= val_num, f"gte: {metric_path}={obs_num} >= {val_num}"
        if typ == "lte":
            return obs_num <= val_num, f"lte: {metric_path}={obs_num} <= {val_num}"
        if typ == "gt":
            return obs_num > val_num,  f"gt: {metric_path}={obs_num} > {val_num}"
        if typ == "lt":
            return obs_num < val_num,  f"lt: {metric_path}={obs_num} < {val_num}"
    if typ == "contains":
        observed = _read(metric_path)
        ok = str(value) in str(observed)
        return ok, f"contains: {metric_path} contains {value!r}"
    if typ == "nonempty":
        observed = _read(metric_path)
        ok = bool(observed)
        return ok, f"nonempty: {metric_path} is {'non-empty' if ok else 'EMPTY'}"
    if typ == "bridges_min":
        try:
            min_n = int(value)
        except Exception:
            return False, f"bridges_min: cannot coerce {value!r} to int"
        ok = len(version.bridges) >= min_n
        return ok, f"bridges_min: bridges count={len(version.bridges)} >= {min_n}"
    if typ == "no_silent_resolution":
        claim_ids = {c.claim_id for c in version.claims}
        for cd in version.contradictions:
            for cid in cd.claim_ids:
                if cid not in claim_ids:
                    return False, (
                        f"no_silent_resolution: contradiction "
                        f"{cd.contradiction_id} references missing claim_id {cid!r}."
                    )
        return True, "no_silent_resolution: every contradiction's claim_ids resolve"
    return False, f"unknown assertion type {typ!r}"


# ---------------------------------------------------------------------------
# DeepEvalRunner — top-level entry point used by the SelfImprovementLoop
# ---------------------------------------------------------------------------


@dataclass
class DeepEvalRunner:
    """Owns the deterministic metrics + optional DeepEval judges."""

    deepeval_enabled: bool = field(default=_HAS_DEEPEVAL)

    def score(self, version: SynthesisVersion) -> EvaluationScore:
        deterministic = _all_deterministic_metrics(version)
        deepeval_results = _deepeval_judges(version) if self.deepeval_enabled else ()

        # Composite weighted score over deterministic metrics only.
        weights_total = sum(m.weight for m in deterministic) or 1.0
        overall = round(
            sum(m.score * m.weight for m in deterministic) / weights_total
        )

        return EvaluationScore(
            version_id=version.version_id,
            topic=version.topic,
            overall_score=int(overall),
            metric_results=deterministic,
            deepeval_results=deepeval_results,
            evaluated_at=datetime.now(timezone.utc),
            has_finance_subject=bool(version.has_finance_subject),
        )

    def run_promptfoo_suite(
        self,
        version: SynthesisVersion,
        promptfoo_yaml_path: Path,
    ) -> tuple[dict, ...]:
        """Run every applicable test case from ``promptfoo.yaml`` against
        ``version`` and return one result dict per test case.

        Each result has shape::

            {
                "description": "...",
                "category":    "contradiction" | ... | "uncategorized",
                "passed":      bool,
                "asserts":     [(assert_dict, passed, message), ...],
            }
        """

        cases = parse_promptfoo_yaml(promptfoo_yaml_path)
        out: list[dict] = []
        for case in cases:
            assert_results: list[tuple[dict, bool, str]] = []
            all_passed = True
            for asrt in case.asserts:
                passed, msg = execute_promptfoo_assert(version, asrt)
                assert_results.append((asrt, passed, msg))
                if not passed:
                    all_passed = False
            out.append({
                "description": case.description,
                "category":    case.category,
                "passed":      all_passed,
                "asserts":     assert_results,
            })
        return tuple(out)


__all__ = (
    "DETERMINISTIC_METRIC_WEIGHTS",
    "DEFAULT_METRIC_THRESHOLDS",
    "DeepEvalRunner",
    "EvaluationScore",
    "MetricResult",
    "PromptfooTestCase",
    "execute_promptfoo_assert",
    "parse_promptfoo_yaml",
)
