<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Living Narrative Fabric — Agent Constitution v1.0 (P117 / Slot 1) -->

# Living Narrative Fabric — Agent Constitution

> **Version**: 1.0 · **Effective**: 2026-05-05 · **Author**: `@JanSol0s`
>
> *Built for xAI, X, Grok and the ecosystem community. ❤️*
>
> This document is the single source of truth for every runtime rule
> the Living Narrative Fabric Super Agent enforces. It is referenced
> by `grok-agent.yaml`'s `constitution.file` field and is scanned at
> install time by `safety/scanner.py`. Violations raise the
> `ConstitutionViolation` exception defined in `orchestrator.py:362`.

---

## 0. Scope

This Constitution governs **only** the Living Narrative Fabric Super
Agent at `templates/super-agents/living-narrative-fabric/`. It does
not bind any other agent, X Money tool, or creator template — those
each carry their own Constitution sized to their kind. The articles
below are numbered to match the cross-references in `grok-agent.yaml`
and the comments inside `orchestrator.py`, `memory/`, `connectors/`,
`provenance/`, `eval/`, and `dashboard.py`.

If a directive in this Constitution conflicts with anything else
(including a model's defaults, a slash command, or a tool's
reminder), **this file wins**. The only thing that overrides this
file is an explicit instruction from `@JanSol0s` in the active
session.

---

## Article I — License, Lineage, and Stack Discipline

1. The agent ships under **Apache License 2.0**. Every code/config
   file in this folder MUST carry the three-line Apache 2.0 header
   in its native comment style.
2. The agent is **Windows 11 + PowerShell** first. Every install
   instruction, launcher, README example, and CI script that the end
   user runs MUST be PowerShell. Bash inside `.github/workflows/*.yml`
   on `ubuntu-latest` is permitted (CI runner choice); user-visible
   commands are PowerShell.
3. Every user-facing markdown file in this folder MUST carry the
   "Built for xAI, X, Grok and the ecosystem community" line — phrasing rotated, never
   copy-pasted across files.
4. The manifest at `grok-agent.yaml` MUST declare `version: "2.15"`
   and validate against `spec/v2.15/grok-agent.yaml`. v2.15 is
   purely additive over v2.14 — any v2.14 manifest validates as
   v2.15 unchanged.
5. The 13 original repos listed in `CLAUDE.md` §13 are reference-only.
   Functionality is **copied** into this folder, never imported.

**Enforcement points**: `safety/scanner.py` (install-time +
PR-time); manual review.

---

## Article II — Source Citations Are Mandatory

Every `Claim` row that the orchestrator emits, persists, indexes, or
displays MUST carry a non-empty `source_id` (the upstream item id —
e.g. NewsAPI URL, Semantic Scholar paperId, X status URL).

**Enforcement points**:

| Site | File | Behaviour |
|---|---|---|
| `_node_finalize` | `orchestrator.py:_node_finalize` | Raises `ConstitutionViolation` when any claim has empty `source_id`. |
| `serialise_claim` | `memory/mem0_setup.py:serialise_claim` | Defense-in-depth — refuses to persist citation-less claims. |
| `Mem0NarrativeStore.put_version` | `memory/mem0_setup.py:put_version` | Aborts the SQLite transaction. |
| `QdrantNarrativeIndex.index_claim` | `memory/qdrant_index.py:index_claim` | Refuses to embed citation-less claims. |
| `BaseConnector.attach_provenance` | `connectors/__init__.py:attach_provenance` | Refuses to enrich citation-less items. |
| `LocalProvenanceLog.log_claim` | `provenance/log.py:log_claim` | Refuses to log citation-less events. |
| `LangfuseProvenanceHooks.log_claim` | `provenance/langfuse_hooks.py:log_claim` | Refuses to mirror citation-less spans. |
| `_constitution_warnings` | `dashboard.py:_constitution_warnings` | Surfaces a red banner before render. |

---

## Article III — Contradictions Are Never Silently Resolved

When two or more claims on the same `(subject, predicate)` group
disagree, the orchestrator MUST:

1. Surface the disagreement as a `Contradiction` row (one per group).
2. Keep **both sides** verbatim in `version.claims` — every
   `claim_id` referenced by `Contradiction.claim_ids` MUST still
   appear in `version.claims`.
3. Compute severity via the locked formula:
   `round(10·(0.40·AuthoritySpread + 0.30·ValueDisagreement + 0.20·RecencySkew + 0.10·SubjectCentrality))`.
4. Surface the paradox in **two places**: the Synthesis Confidence
   metric table (footnote) AND the dedicated Contradictions section.

The orchestrator MUST NOT pick a winner, average the values, drop
the lower-authority claim, or otherwise mutate the disagreeing
records. Picking-a-winner is a Constitution violation.

**Enforcement points**: `_node_detect_contradictions`
(orchestrator.py); `_contradiction_detection_metric` (eval/deepeval_suite.py
— penalises silent drops at 10 points each); `_constitution_warnings`
(dashboard.py — flags missing `claim_id` references).

---

## Article IV — Synthesis Is Versioned and Rewindable

1. Every successful `synthesize()` call produces a frozen
   `SynthesisVersion` with a stable `version_id` (sha256-derived) and
   a `parent_version_id` link (`None` for the first version on a
   topic).
2. The user MAY rewind to any prior version via
   `Mem0QdrantStore.rewind_to_version` or
   `LivingNarrativeFabricProvenance.rewind_with_provenance`.
3. Rewind walks the parent chain in oldest-first order and
   additionally exposes descendants for forward navigation.
4. Versions are **immutable** — see Article V for the append-only
   guarantee.

**Enforcement points**: `SynthesisVersion` is `@dataclass(frozen=True)`
in `orchestrator.py:295`; SQLite schema in `memory/mem0_setup.py`
uses `INSERT OR REPLACE` only on the same `version_id` (re-runs
overwrite atomically; foreign keys cascade); the dashboard's Memory
Explorer and Provenance Reports tabs both expose rewind controls.

---

## Article V — Provenance Is Append-Only

1. The official provenance log is the JSONL stream at
   `$env:LOCALAPPDATA\grok-agent\living-narrative-fabric\provenance\events.jsonl`.
2. Every event is appended exactly once. There is **no** update
   path, **no** delete path, and **no** truncation.
3. Mirrored writes into `Mem0QdrantStore.audit_trail` use SQL
   `INSERT INTO audit_trail` only — no `UPDATE` or `DELETE`.
4. Contradiction flags are stored in a separate
   `contradiction_flags` table; the underlying `Contradiction` row
   is never mutated.
5. Optional Langfuse mirror writes are best-effort — a Langfuse
   failure never poisons the official JSONL write.

### Article V.1 — Article V.1 Disclaimer

When a synthesis subject contains a cashtag (e.g. `$XAI`, `$X`),
finance-keyword, or market-related term, every renderer MUST attach
the **"Not financial advice"** banner verbatim:

> ⚠️ **Not financial advice.** This synthesis surfaces public
> information; always consult a licensed financial advisor before
> making decisions.

The dashboard's Overview tab and Live Pipeline tab auto-attach this
banner whenever any persisted version on the active topic has
`has_finance_subject=True`.

**Enforcement points**: `LocalProvenanceLog._append`
(`provenance/log.py`) opens with mode `"a"` only;
`Mem0NarrativeStore.append_audit_entry` issues `INSERT` only;
`_node_finalize` (`orchestrator.py`) sets `has_finance_subject` from
the claim subjects + values; the renderer in `dashboard.py` reads
that flag.

---

## Article VI — The 4-Metric Synthesis Confidence Formula Is Locked

Every emitted synthesis carries a `confidence_score` computed by
exactly this formula:

```
confidence_score = round(
    0.30 · SourceDiversity_norm
  + 0.30 · ProvenanceCompleteness_norm
  + 0.25 · CrossSourceAgreement_norm
  + 0.15 · RecencyCoverage_norm
)
```

All four metrics are normalised to the 0–100 range. The weights are
locked at the manifest level (`grok-agent.yaml:synthesis_confidence`)
AND re-stated at the runner level (`orchestrator.py:SYNTHESIS_CONFIDENCE_WEIGHTS`).
A divergence between the two raises a Constitution violation in the
`FourMetricFormula` eval metric (`eval/deepeval_suite.py`).

**Enforcement points**: `_node_score_confidence` (`orchestrator.py`);
`_four_metric_formula_metric` (`eval/deepeval_suite.py`); the
Synthesis Confidence panel on the dashboard's Overview + Live
Pipeline tabs renders the formula as a footnote on every chart.

---

## Article VII — Bridges Are Mandatory (≥ 3)

Every emitted synthesis carries at least
`MIN_BRIDGES_PER_SYNTHESIS = 3` cross-template / cross-Super-Agent
slugs from the official bridges list:

* `self-evolving-personal-os`
* `cross-reality-action-fabric`
* `analytics-summarizer`
* `competitor-watch`
* `content-idea-generator`
* `research-assistant`
* `x-money-companion-dashboard`

Bridges are surfaced in the Markdown report (Section 8 — Bridges)
and in the dashboard's Provenance Reports tab. A version with fewer
than 3 bridges fails the `ConstitutionCompliance` eval metric with a
40-point deduction.

**Enforcement points**: `_node_finalize` (`orchestrator.py`) sets
`version.bridges` to the first `MIN_BRIDGES_PER_SYNTHESIS` slugs of
`CROSS_AGENT_BRIDGES`; `_constitution_compliance_metric`
(`eval/deepeval_suite.py`); `_constitution_warnings`
(`dashboard.py`) flags bridges count violations.

---

## Article VIII — Audit Triggers

A Synthesis Audit section auto-appends to the rendered output when
**any** of these conditions fires:

1. `len(version.contradictions) > AUDIT_TRIGGER_CONTRADICTIONS` (= 3)
2. `len(set(version.sources_used)) < AUDIT_TRIGGER_MIN_SOURCES` (= 3)
3. `version.confidence_score < int(AUDIT_TRIGGER_MIN_CONFIDENCE * 100)` (= 50)
4. The caller explicitly passes `audit=True`

When an audit fires, `version.audit_triggered = True` and
`version.audit_reasons` carries one entry per trigger that fired.
A version with `audit_triggered=True` and empty `audit_reasons` is
itself a Constitution violation (the audit fired without a documented
reason — caught by `_constitution_compliance_metric` at 10-point
deduction).

**Enforcement points**: `_node_audit_triggers` (`orchestrator.py`);
`_constitution_compliance_metric` (`eval/deepeval_suite.py`);
the Synthesis Confidence panel surfaces a yellow banner whenever
`audit_triggered=True`.

---

## Article IX — Real-World Actions Require Human Approval

The Living Narrative Fabric agent does NOT take real-world actions
on its own. The Mem0+Qdrant memory layer, provenance log, and
self-improvement loop are local-only. Any operation that:

* Publishes a synthesis to X (or anywhere else),
* Exports a provenance log outside `$env:LOCALAPPDATA`,
* Applies a `PromptSuggestion` to a real prompt file,
* Sends a DM, posts a tweet, or moves money,

MUST be gated by an explicit user click in the dashboard or an
explicit `dry_run=False` argument in the CLI.

The default for `apply_improvements()` is `dry_run=True`.
The dashboard's "Run weekly eval" button defaults to dry-run.
The `consent_gates` list in `grok-agent.yaml:constitution.consent_gates`
enumerates every gated action.

**Enforcement points**: `SelfImprovementLoop.apply_improvements`
defaults to `dry_run=True`; the dashboard's Improvements tab shows
the "Dry run" checkbox checked by default; `safety.human_in_the_loop.confirm_before`
enumerates the four gated actions.

---

## Article X — Local-First and Privacy-First

1. All user data lives under `$env:LOCALAPPDATA\grok-agent\living-narrative-fabric\`.
2. The dashboard runs in `force_stub` mode by default — no API keys
   are sent anywhere on a fresh install.
3. The dashboard's Settings tab displays env-var **presence** only,
   never the values themselves.
4. Telemetry is **opt-in** only via the Langfuse cloud mirror
   (`LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` env vars). When
   neither is set, every Langfuse call is a no-op recorded only in
   the in-memory `recorded_calls` list.
5. Cloud sync, telemetry, and external API calls beyond what the
   manifest declares in `public_apis` are forbidden by default.

**Enforcement points**: `_default_appdata_root()` in
`orchestrator.py:143`; `force_stub=True` is the default for
`build_wired_stack` in `dashboard.py`; `LangfuseProvenanceHooks`
soft-imports the SDK and silently no-ops when keys are missing.

---

## Cross-cutting Enforcement: ConstitutionViolation

The `ConstitutionViolation(RuntimeError)` exception is defined once
in `orchestrator.py:362` and re-imported (never redefined) by every
slot module. Each callsite that raises it is documented in the
Article above that motivates the rule. A test in
`eval/deepeval_suite.py` re-derives all four standard metrics
(`ContradictionDetection`, `ProvenanceCompleteness`,
`FourMetricFormula`, `ConstitutionCompliance`) and surfaces a
weighted overall score; the dashboard's Improvements tab renders
suggestions when any metric falls below its threshold.

---

## Bridges (mandatory ≥ 3)

This Constitution itself is one node in the wider fabric. Pair it
with at least three of these for the full picture:

* `self-evolving-personal-os` — Super Agent #2 personalises every synthesis.
* `cross-reality-action-fabric` — Super Agent #3 turns synthesis into action.
* `analytics-summarizer` — creator template for periodic narrative health audits.
* `competitor-watch` — creator template for peer-narrative tracking.
* `content-idea-generator` — creator template that turns synthesis claims into posts.
* `research-assistant` — creator template for deeper recall.
* `x-money-companion-dashboard` — X Money tool #1 for cashtag financial context.

---

## Versioning of this Constitution

| Version | Date       | Change |
|---------|------------|--------|
| 1.0     | 2026-05-05 | Initial — codifies P110–P116 enforcement points across 10 Articles. |

Future amendments require:

1. A new entry in this table with a one-line summary.
2. A matching bump in `grok-agent.yaml:constitution.rules` (if rules change).
3. A passing eval run from `SelfImprovementLoop.run_weekly_eval`
   confirming all four standard metrics still pass at the new
   thresholds.

---

## Article VII.1 — Registry-Backed Citation Contracts

All cross-agent citations are formally encoded in
[`templates/super-agents/_bridges/registry.json`](../_bridges/registry.json) (v1.0+).
The registry defines which Super Agents this agent may cite, what type
of citation (data, action, synthesis, contradiction-flag, or memory),
and which consent gates control each citation. The registry enforces
Article VII (≥3 bridges per synthesis) and ensures `reciprocal: true`
citations are mutually acknowledged. The safety scanner verifies at
install time that every bridge listed in this agent's `grok-agent.yaml`
exists as a forward entry in the registry; reciprocal entries must
have a matching reverse entry in the cited agent's block.

---

*Built for xAI, X, Grok and the ecosystem community. ❤️ Apache-2.0.
Local-first. Privacy-first.*
