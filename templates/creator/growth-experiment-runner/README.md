<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Growth Experiment Runner

> **Built for X, Grok & the ecosystem community.**
> Local-first growth experiment runner for X creators. Reads creator-supplied hypothesis bundle (or seeded demo signals) and emits a structured 7/8-section experiment plan with 4 canonical Experiment Plan Score metrics, the **small-n paradox** surfaced in BOTH the Plan Score table AND Red Flags whenever it fires, the **multi-variable guard** that excludes any experiment varying > 1 axis, the **risk-exclude guard** that excludes unsafe experiment designs, 3–6 experiment cards each with hypothesis + axis + expected effect + sample required + runtime + primary metric + success criteria, and unconditional bridges to `analytics-summarizer` + `ab-test-suggester` in every output.

> ⚠️ **No financial, cashtag, investment, sponsorship, harassment, or unsafe-experiment content.** The runner refuses these on every input field.

> ⚠️ **Drafts only.** The runner emits a plan the creator reviews before running. It never auto-runs experiments and never auto-publishes.

---

## What it is

A deterministic Python runner bound to a v2.15 `creator-template` manifest. Given a creator's X handle plus an audience size (and optionally a hypothesis bundle file), it produces a 7-section markdown plan (8 sections when the Experiment Audit auto-triggers).

- **4 canonical Experiment Plan Score metrics** — Hypothesis specificity / Single-axis isolation / Sample power / Risk avoidance, weights 0.30 / 0.25 / 0.25 / 0.20.
- **Small-n paradox** dual-surface — when avg Sample power < 40 AND avg Hypothesis specificity > 70, the paradox fires in BOTH the Plan Score table AND a high-severity Red Flag.
- **Multi-variable guard** — any experiment with `axis_count > 1` → excluded (matches `ab-test-suggester`'s single-axis isolation contract).
- **Risk-exclude guard** — any experiment with `risk_avoidance_score < 40` → excluded.
- **Sample-power model** — heuristic detection floor: `≈ 2 / sqrt(effective_n) × 100%` where `effective_n = min(audience, 0.10 × audience × runtime / 30)`.
- **Mandatory bridges** — `analytics-summarizer` (position 1) + `ab-test-suggester` (position 2).

---

## Quick launch (Windows 11 + PowerShell)

### Option A — small-n paradox demo

```powershell
python .\templates\creator\growth-experiment-runner\run.py `
    --x-handle JanSol0s `
    --demo
```

You'll see: 6 candidate experiments, small-n paradox active (specificity 78.8, sample power 29.3), 1 multi-variable excluded, 1 high-risk excluded, Experiment Audit auto-triggered.

### Option B — healthy demo

```powershell
python .\templates\creator\growth-experiment-runner\run.py `
    --x-handle habitstacker `
    --demo-healthy
```

You'll see: 4 candidate experiments, all metrics within healthy bands, no paradox, no exclusions.

### Option C — 7d-window audit demo

```powershell
python .\templates\creator\growth-experiment-runner\run.py `
    --x-handle thindata `
    --demo-7d-audit
```

You'll see: window=7d auto-triggers Experiment Audit, medium confidence.

### Option D — real hypothesis bundle

```powershell
python .\templates\creator\growth-experiment-runner\run.py `
    --x-handle JanSol0s `
    --hypothesis-file .\my-hypotheses.json `
    --audience-size 12000 `
    --window 30 `
    --max-experiments 4
```

Output to stdout by default. Add `--out plan.md` to write to file.

---

## Flag reference

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--x-handle` | string | required | Creator's X handle. |
| `--hypothesis-file` | path | (none) | Path to hypothesis JSON. Schema below. |
| `--audience-size` | int | 12000 | Reachable-audience size for sample-power calculations. |
| `--window` | int | 30 | One of 7 / 30 / 90. `7` auto-triggers Experiment Audit. |
| `--max-experiments` | int | 4 | Clamped to `[3, 6]`. |
| `--power-floor` | float | 40.0 | Sample-power threshold for Red Flag surfacing. |
| `--demo` | bool | false | Small-n paradox demo seed. |
| `--demo-healthy` | bool | false | All-within-bounds demo seed. |
| `--demo-7d-audit` | bool | false | 7d window demo seed. |
| `--out` | path | (stdout) | Write plan to file. |

---

## `--hypothesis-file` schema

```jsonc
{
  "x_handle": "@JanSol0s",
  "audience_size": 12000,
  "window": 30,
  "data_source": "real",
  "baseline_metric_name": "engagement_rate",
  "baseline_metric_value": 2.4,
  "candidate_experiments": [
    {
      "hypothesis": "Switching the opening hook from a question to a single concrete number raises engagement_rate by 0.4 percentage points",
      "axis_count": 1,
      "axis_label": "opening_hook_format",
      "expected_effect_pct": 0.4,
      "planned_runtime_days": 30,
      "primary_metric": "engagement_rate",
      "success_criteria": "engagement_rate uplift ≥ 0.4 pts vs the prior 30d baseline",
      "hypothesis_specificity_score": 88,
      "single_axis_isolation_score": 95,
      "risk_avoidance_score": 92
      // sample_power_score is optional — the runner computes it from the
      // heuristic if missing.
    }
  ],
  "previous_window_summary": {
    "avg_hypothesis_specificity": 72.0,
    "avg_single_axis_isolation": 82.0,
    "avg_sample_power": 60.0,
    "avg_risk_avoidance": 88.0
  }
}
```

### Field constraints

- `axis_count`: integer ≥ 1. Values > 1 trigger the multi-variable guard (excluded).
- `primary_metric`: one of `engagement_rate` / `impressions` / `follower_delta` / `reply_rate` / `click_rate` / `thread_completion_rate` / `monetization_channel_revenue` / `mention_quality_score`
- All scores: 0–100 numeric
- `expected_effect_pct`: numeric (% points or % multiplicative — interpretation tracked in `success_criteria`)
- `planned_runtime_days`: numeric

---

## Sample-power model (heuristic)

For an experiment with audience size `A`, predicted effect `E%`, and runtime `R` days:

```
effective_n = min(A, 0.10 × A × R / 30)
detectable_at_80%_power ≈ (2 / sqrt(effective_n)) × 100%
sample_power_score = 100 if E ≥ detectable, else 100 × (E / detectable)
```

If a creator-supplied `sample_power_score` is present in the input, the runner trusts it. Otherwise it computes from the heuristic.

---

## Cross-template flow

```
                +-----------------------+
                | growth-experiment-    |
                |   runner              |
                +---|-------|-----------+
                    |       |
        (mandatory) |       | (mandatory)
                    v       v
       analytics-summarizer  ab-test-suggester
                    |
                    v
              run experiments
                    |
                    v
       analytics-summarizer (next window — measure)
                    |
                    v
       content-idea-generator (fold winners into next batch)
```

The mandatory upstream → `analytics-summarizer` (the experiment's primary metric is measured by analytics). The mandatory downstream → `ab-test-suggester` (variant generation when the hypothesis is content-shaped, under the same single-axis isolation contract).

---

## Where data lives

| Surface | Path |
|---|---|
| AppData root | `%LOCALAPPDATA%\grok-agent\growth-experiment-runner\` |
| Cache | `%LOCALAPPDATA%\grok-agent\growth-experiment-runner\cache\` |
| Logs | `%LOCALAPPDATA%\grok-agent\growth-experiment-runner\logs\` |

---

## Examples

| File pair | Demo mode | What it shows |
|---|---|---|
| `sample-1-input.json` + `sample-1-output.md` | small-n paradox | Paradox + multi-variable excluded + high-risk excluded |
| `sample-2-input.json` + `sample-2-output.md` | healthy | All within bounds, 7-section output |
| `sample-3-input.json` + `sample-3-output.md` | 7d-audit | Experiment Audit auto-triggered |

---

## What the manifest declares

| Field | Value |
|---|---|
| `version` | `2.15` |
| `kind` | `creator-template` |
| `tools[0].name` | `generate_growth_experiment_plan` |
| `tools[0].module` | `growth_experiment_runner.run` |
| `safety.cost_limits.usd_per_session_max` | `0.30` |
| `constitution.hard_refusals[]` | auto-run · finance · sponsorship · harassment · unsafe-experiment-design · third-party-handles · scraping |

---

## v1 limitations

- No outbound network calls. Reads creator-supplied JSON.
- Sample-power model is heuristic, not a full statistical-power calculator.
- Voice profile influence not implemented in v1.
- No automated experiment running.

---

## Build slots

| Slot | Status | Files |
|---|---|---|
| Slot 1 | ✅ shipped (P109) | `grok-agent.yaml`, `prompts/system.md` |
| Slot 2 | ✅ shipped (P109) | `run.py`, `README.md`, `examples/` |

---

## License

Apache 2.0.

> Built for X, Grok & the ecosystem community.
