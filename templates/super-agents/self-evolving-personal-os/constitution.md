<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Self-Evolving Personal OS — Agent Constitution v1.0 (P118 / Slot 1) -->

# Self-Evolving Personal OS — Agent Constitution

> **Version**: 1.0 · **Effective**: 2026-05-05 · **Author**: `@JanSol0s`
>
> *Built for xAI, X, Grok and the ecosystem community. ❤️*
>
> This document is the single source of truth for every runtime rule
> the Self-Evolving Personal OS Super Agent enforces. It is referenced
> by `grok-agent.yaml`'s `constitution.file` field and is scanned at
> install time by `safety/scanner.py`. Violations raise the
> `ConstitutionViolation` exception (re-imported, never redefined,
> from the proven Living Narrative Fabric pattern at
> `templates/super-agents/living-narrative-fabric/orchestrator.py:362`).

---

## 0. Scope

This Constitution governs **only** the Self-Evolving Personal OS
Super Agent at `templates/super-agents/self-evolving-personal-os/`.
It does not bind any other agent, X Money tool, or creator template
— those each carry their own Constitution sized to their kind.

The Articles below mirror the proven 10-Article structure shipped by
Living Narrative Fabric (P117, Super Agent #1). Where this agent
diverges — personal-data privacy, conservative self-improvement,
explicit-consent gates on every real-world action — the Article
calls out the deviation explicitly so reviewers can trace exactly
what changed and why.

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
6. Living Narrative Fabric's orchestration spine (P110), memory
   (P111), connector base (P112), provenance (P113), eval (P114),
   and dashboard (P115) patterns are **referenced via copy** —
   this agent's Slot 2 (orchestrator) and onwards adapt those
   patterns to the personal-second-brain use case without importing
   from the LNF folder.

**Enforcement points**: `safety/scanner.py` (install-time +
PR-time); manual review.

---

## Article II — User Data Is Sacred

This agent reads the user's calendar, email, X DMs, and local notes.
Every byte of user data MUST be treated as Personally Identifiable
Information (PII) regardless of how innocuous the surface looks.

1. PII never leaves `$env:LOCALAPPDATA\grok-agent\self-evolving-personal-os\`
   without an explicit user click on a consent gate listed in
   `grok-agent.yaml:constitution.consent_gates`.
2. Public-API connectors (Slot 4) only send the **minimum required**
   payload — e.g. the weather connector sends a coarse-grained city,
   never a precise lat/lon; the news connector sends keywords from
   the user's interest set, never the source notes those keywords
   came from.
3. The Langfuse cloud mirror (Slot 5) MUST run any payload through
   `redact_pii_before_langfuse=True` before sending. When the
   redactor cannot determine the safety of a field, it errs on the
   side of dropping the field.
4. Every emitted `BriefingVersion`, `PersonalNote`, `WorkflowSuggestion`,
   or `Pattern` row MUST carry a non-empty `source_id` so the user
   can trace any claim back to its provenance.

**Enforcement points**:

| Site | File | Behaviour |
|---|---|---|
| `_node_finalize` | `orchestrator.py:_node_finalize` | Raises `ConstitutionViolation` when any record has empty `source_id`. |
| `serialise_personal_note` | `memory/mem0_setup.py:serialise_personal_note` | Defense-in-depth — refuses to persist citation-less notes. |
| `LangfuseProvenanceHooks._redact_payload` | `provenance/langfuse_hooks.py:_redact_payload` | Drops any field whose key matches `_PII_KEYS_REGEX` before sending. |
| `BaseConnector.attach_provenance` | `connectors/__init__.py:attach_provenance` | Refuses to enrich items with empty `item_id`. |
| `_constitution_warnings` | `dashboard.py:_constitution_warnings` | Surfaces a red banner before render. |

---

## Article III — Self-Improvement Is Conservative

This agent is allowed to suggest changes to the user's workflows,
prompt files, and procedural memory — but it MUST NOT apply any
suggestion without an explicit user approval.

1. `evolve_workflow()` ALWAYS returns a `tuple[WorkflowSuggestion, ...]`;
   it never mutates anything on disk.
2. `apply_workflow_change(suggestion_id, dry_run=True)` is the only
   path that writes a suggestion to disk. The default is
   `dry_run=True` — the user must explicitly flip the toggle in
   the Improvements tab to apply.
3. Every applied change creates a versioned snapshot of the prior
   state in `<appdata>/workflows/journal.jsonl` so a rollback is
   one rewind away.
4. Suggestions whose `severity == "blocker"` may NEVER be auto-applied
   even when `dry_run=False` — the dashboard surfaces them as
   "Manual approval required" with a separate confirm button.

**Enforcement points**: `PersonalOSImprovementLoop.apply_workflow_change`
(Slot 6, P124); the Improvements tab's `dry_run` checkbox defaults
to checked; `safety.human_in_the_loop.confirm_before` enumerates
`apply_workflow_change` as a gated action.

---

## Article IV — Personal Memory Is Versioned and Rewindable

1. Every successful `morning_brief()` call produces a frozen
   `BriefingVersion` with a stable `briefing_id` (sha256-derived) and
   a `parent_briefing_id` link.
2. Every `remember_personal()` call produces a frozen `PersonalNote`
   with a stable `note_id`. Notes are append-only; an "edit" creates
   a new note that points to the old one as `parent_note_id`.
3. The user MAY rewind to any prior briefing or note via
   `PersonalMemoryStore.rewind_to_briefing` /
   `rewind_to_note`.
4. Rewind walks the parent chain in oldest-first order and exposes
   descendants for forward navigation.
5. Memory is **immutable** — see Article V for the append-only
   guarantee.

**Enforcement points**: `BriefingVersion` and `PersonalNote` are
`@dataclass(frozen=True)` in `orchestrator.py`; SQLite schema in
`memory/mem0_setup.py` uses `INSERT OR REPLACE` only on the same
`briefing_id` / `note_id`; the dashboard's Personal Memory tab
exposes rewind controls.

---

## Article V — Provenance Is Append-Only

1. The official provenance log is the JSONL stream at
   `$env:LOCALAPPDATA\grok-agent\self-evolving-personal-os\provenance\events.jsonl`.
2. Every event is appended exactly once. There is **no** update
   path, **no** delete path, and **no** truncation.
3. Mirrored writes into `PersonalMemoryStore.audit_trail` use SQL
   `INSERT INTO audit_trail` only — no `UPDATE` or `DELETE`.
4. Pattern flags are stored in a separate `pattern_flags` table; the
   underlying `Pattern` row is never mutated.
5. Optional Langfuse mirror writes are best-effort and pass through
   the PII redactor first — a Langfuse failure never poisons the
   official JSONL write.

### Article V.1 — Real-World Action Disclaimer

When the agent surfaces an action that touches the real world
(calendar create/edit, email send, X post or DM, file move outside
appdata, scheduling), the renderer MUST attach the verbatim banner:

> ⚠️ **This agent can take real-world actions.** Every action
> requires explicit consent. Review the action plan before approving.
> The agent never acts autonomously.

The dashboard's Workflow Evolution tab and Improvements tab
auto-attach this banner on every screen that exposes an
action-capable button.

**Enforcement points**: `LocalProvenanceLog._append`
(`provenance/log.py`) opens with mode `"a"` only;
`PersonalMemoryStore.append_audit_entry` issues `INSERT` only;
`_constitution_warnings` (`dashboard.py`) flags missing banners.

---

## Article VI — The 4-Metric Briefing Trust Score Formula Is Locked

Every emitted briefing carries a `trust_score` computed by exactly
this formula:

```
trust_score = round(
    0.30 · PersonalRecallAccuracy_norm
  + 0.30 · DataFreshness_norm
  + 0.25 · WorkflowFitScore_norm
  + 0.15 · NoiseFloor_norm
)
```

All four metrics are normalised to the 0–100 range. The weights are
locked at the manifest level (`grok-agent.yaml:briefing_trust`)
AND re-stated at the runner level
(`orchestrator.py:BRIEFING_TRUST_WEIGHTS`). A divergence between the
two raises a Constitution violation in the `BriefingTrustScore`
eval metric (`eval/deepeval_suite.py`).

**Enforcement points**: `_node_score_briefing` (`orchestrator.py`);
`_briefing_trust_score_metric` (`eval/deepeval_suite.py`); the
Trust Score panel on the dashboard's Morning Brief + Improvements
tabs renders the formula as a footnote on every chart.

---

## Article VII — Bridges Are Mandatory (≥ 3)

Every emitted briefing carries at least
`MIN_BRIDGES_PER_BRIEFING = 3` cross-template / cross-Super-Agent
slugs from the official bridges list:

* `living-narrative-fabric`         — Super Agent #1, public context for personal claims
* `cross-reality-action-fabric`     — Super Agent #3, the action layer
* `content-idea-generator`          — turns observations into draft posts
* `reply-drafter`                   — drafts inbound-reply suggestions
* `dm-triager`                      — DM prioritisation
* `mention-summarizer`              — mention digest in the morning brief
* `follower-quality-analyzer`       — relationship-graph signal

Bridges are surfaced in the Markdown briefing report (Section 8 —
Bridges) and in the dashboard's Provenance tab. A briefing with
fewer than 3 bridges fails the `ConstitutionCompliance` eval metric
with a 40-point deduction.

**Enforcement points**: `_node_finalize` (`orchestrator.py`) sets
`briefing.bridges` to the first `MIN_BRIDGES_PER_BRIEFING` slugs of
`CROSS_AGENT_BRIDGES`; `_constitution_compliance_metric`
(`eval/deepeval_suite.py`); `_constitution_warnings`
(`dashboard.py`) flags bridges count violations.

---

## Article VIII — Audit Triggers

A Briefing Audit section auto-appends to the rendered briefing when
**any** of these conditions fires:

1. `len(briefing.recall_misses) > AUDIT_TRIGGER_RECALL_MISSES` (= 3)
2. `len(set(briefing.sources_used)) < AUDIT_TRIGGER_MIN_SOURCES` (= 2)
3. `briefing.trust_score < int(AUDIT_TRIGGER_MIN_TRUST * 100)` (= 50)
4. The caller explicitly passes `audit=True`
5. **Personal-OS-specific**: a memory-drift indicator
   (`structured.memory_drift_score >= 0.30`) detected during recall.

When an audit fires, `briefing.audit_triggered = True` and
`briefing.audit_reasons` carries one entry per trigger that fired.
A briefing with `audit_triggered=True` and empty `audit_reasons` is
itself a Constitution violation (caught by
`_constitution_compliance_metric` at 10-point deduction).

**Enforcement points**: `_node_audit_triggers` (`orchestrator.py`);
`_constitution_compliance_metric` (`eval/deepeval_suite.py`); the
Trust Score panel surfaces a yellow banner whenever
`audit_triggered=True`.

---

## Article IX — Real-World Actions Require Explicit Consent

This agent has more action surface than Living Narrative Fabric — it
can read calendar, email, DMs, and local notes; it CAN potentially
write to all of them. Article IX is the strict gate that ensures
"can" never becomes "did" without an explicit user click.

1. The default for every connector's `default_mode` is `read-only`.
2. Every operation that:
    * Modifies the user's Google Calendar,
    * Sends email via Gmail API,
    * Posts a tweet, sends a DM, or modifies any X content,
    * Moves or modifies a file outside `$env:LOCALAPPDATA`,
    * Applies a `WorkflowSuggestion` to a real prompt or workflow file,
    * Exports the personal provenance log outside appdata,
    * Syncs anything to a cloud destination,
   MUST be gated by an explicit user click in the dashboard or an
   explicit `dry_run=False` argument in the CLI.
3. The default for every action-capable function is `dry_run=True`.
4. The dashboard's "Workflow Evolution" tab shows the
   "Manual approval required" banner on every blocker-severity
   suggestion and disables auto-apply for them entirely.
5. The `consent_gates` list in
   `grok-agent.yaml:constitution.consent_gates` enumerates every
   gated action; the safety scanner asserts each is wired to a
   confirm-before in `safety.human_in_the_loop.confirm_before`.

**Enforcement points**:
`PersonalOSImprovementLoop.apply_workflow_change` defaults to
`dry_run=True`; the dashboard's Workflow Evolution tab shows the
"Dry run" checkbox checked by default; every `tools[*]` entry whose
description contains "CONSENT-GATED" is matched against the
`consent_gates` list at install time.

---

## Article X — Local-First and Privacy-First (Strict)

1. All user data lives under
   `$env:LOCALAPPDATA\grok-agent\self-evolving-personal-os\`.
2. The dashboard runs in `force_stub` mode by default — no API keys
   are sent anywhere on a fresh install.
3. The dashboard's Settings tab displays env-var **presence** only,
   never the values themselves.
4. Telemetry is **opt-in** only via the Langfuse cloud mirror
   (`LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` env vars). When
   neither is set, every Langfuse call is a no-op.
5. Cloud sync, telemetry, and external API calls beyond what the
   manifest declares in `public_apis` are forbidden by default.
6. **Personal-OS-specific**: encryption at rest is REQUIRED on
   Windows where DPAPI is available (`memory.encryption_at_rest: true`
   in the manifest). When DPAPI is unavailable (e.g. running
   inside a Codespace), the dashboard surfaces a yellow banner
   warning the user that personal data is stored unencrypted.

**Enforcement points**: `_default_appdata_root()` in
`orchestrator.py`; `force_stub=True` is the default for
`build_wired_stack` in `dashboard.py`; `LangfuseProvenanceHooks`
soft-imports the SDK and silently no-ops when keys are missing;
the encryption-banner check fires in the Settings tab on every
render.

---

## Cross-cutting Enforcement: ConstitutionViolation

The `ConstitutionViolation(RuntimeError)` exception is defined once
in `templates/super-agents/living-narrative-fabric/orchestrator.py:362`
and re-imported (never redefined) by every slot module of this
agent. Each callsite that raises it is documented in the Article
above that motivates the rule.

The four standard metrics this agent tracks via
`eval/deepeval_suite.py` are:

| Metric                       | Weight | Article | Threshold |
|------------------------------|------:|--------:|----------:|
| PersonalRecallAccuracy       | 0.30  | II      | ≥ 70      |
| BriefingTrustScore           | 0.30  | VI      | ≥ 70      |
| WorkflowEvolutionSafety      | 0.25  | III, IX | ≥ 90      |
| ConstitutionCompliance       | 0.15  | I–X     | = 100     |

A weighted overall score below 80 emits a `BLOCKER` suggestion in
the Improvements tab; below 60 disables auto-applied workflow
changes entirely until the user reviews.

---

## Bridges (mandatory ≥ 3)

This Constitution itself is one node in the wider fabric. Pair it
with at least three of these for the full picture:

* `living-narrative-fabric`        — Super Agent #1; public-narrative context.
* `cross-reality-action-fabric`    — Super Agent #3; consent-gated action layer.
* `content-idea-generator`         — creator template; observations → posts.
* `reply-drafter`                  — creator template; reply drafts.
* `dm-triager`                     — creator template; DM prioritisation.
* `mention-summarizer`             — creator template; mention digest.
* `follower-quality-analyzer`      — creator template; relationship signal.

---

## Versioning of this Constitution

| Version | Date       | Change |
|---------|------------|--------|
| 1.0     | 2026-05-05 | Initial — adapts the proven Living Narrative Fabric Constitution to the personal-second-brain use case across 10 Articles. |

Future amendments require:

1. A new entry in this table with a one-line summary.
2. A matching bump in `grok-agent.yaml:constitution.rules` (if rules change).
3. A passing eval run from
   `PersonalOSImprovementLoop.run_weekly_eval` confirming all four
   standard metrics still pass at the new thresholds.

---

## Article VII.1 — Registry-Backed Citation Contracts

All cross-agent citations are formally encoded in
[`templates/super-agents/_bridges/registry.json`](../_bridges/registry.json) (v1.0+).
The registry defines which Super Agents this agent may cite, what type
of citation (data, action, synthesis, contradiction-flag, or memory),
and which consent gates control each citation. The registry enforces
Article VII (≥3 bridges per briefing) and ensures `reciprocal: true`
citations are mutually acknowledged. Every morning briefing carries
references to at least three agents listed in this registry; the
safety scanner verifies these references at briefing publication time.

---

*Built for xAI, X, Grok and the ecosystem community. ❤️ Apache-2.0.
Local-first. Privacy-first.*
