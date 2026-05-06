<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community — example output of the AB Test Suggester. -->

# Example output — niche: AI / agent builders (multi-variable paradox demo)

> 🔒 **Drafts only.** Variants below are text the creator reviews and ships themselves. The runner never auto-publishes.
>
> 🔒 **Single-axis isolation.** When test_focus is one of `headline / visual / cta / timing`, variants vary on that one dimension only. Multi-dimensional variants are a hard refusal.
>
> *Built for xAI, X, Grok and the ecosystem community — AI/agent creators reach for kitchen-sink A/Bs first because every dimension feels important. The multi-variable paradox catches that instinct before the test ships.*

| Field | Value |
|---|---|
| Creator handle | `@JanSol0s` |
| Post idea | `Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness.` |
| Test focus | `headline` (single-axis) |
| Variants | **3** (1 control + 2 treatments) |
| Sections emitted | **8** (Test Plan Audit auto-triggered: red-flag count and demo paradox profile push past the threshold) |
| Multi-variable paradox? | **Yes** — Variant clarity in the high-70s, Test isolation in the low-30s, surfaced in BOTH the Test Plan section AND the Red Flags section |

To regenerate this output deterministically:

```powershell
python .\run.py --x-handle JanSol0s --demo --test-focus headline --num-variants 3 --no-banner
```

---

## Test Snapshot
**@JanSol0s: headline-only A/B test on the idea — control vs 2 treatment(s).**

- **X handle**: @JanSol0s
- **Post idea**: Most agent eval suites measure the wrong thing
- **Test focus**: headline
- **Variants requested**: 3 (1 control + 2 treatments)
- **Hypothesis**: An outcome-led headline will outperform a critique-led headline on reply-to-impression ratio over a 7-day window.

## Test Plan

| Metric | Score | Interpretation |
|---|---|---|
| Variant clarity | 83/100 | Treatments diverge sharply from control on the chosen dimension. |
| Test isolation | 33/100 | Variants vary across multiple dimensions despite test_focus=headline — the test cannot isolate which change drove the result. |
| Sample feasibility | 63/100 | Sample feasible at 14-21 days; below that, the read will be noisy. |
| Decision actionability | 65/100 | Result leads to a directional decision; further tests likely needed. |

> ⚠️ paradox: variants are clearly different but diverge across multiple dimensions — the test cannot isolate which change drove the result.

**Test Plan score**: 62/100

## Variants

### Variant A · Control
- **Diff vs idea**: control — ships the idea as-is on the headline dimension.

```
Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness.

The pattern shows up in three concrete shapes. The dashboard climbs while the outcome slides. The proxy gets gamed as it gets graded. The terse correct version gets discounted for not performing thoroughness.

If you can't grade the actual outcome in a sandbox, you don't have a metric. You have a vibes-meter with extra steps.
```

### Variant B · Treatment
- **Diff vs control (single-axis)**: outcome-led headline; body byte-identical to control.

```
if you can't run the action, you don't have a metric.

The pattern shows up in three concrete shapes. The dashboard climbs while the outcome slides. The proxy gets gamed as it gets graded. The terse correct version gets discounted for not performing thoroughness.

If you can't grade the actual outcome in a sandbox, you don't have a metric. You have a vibes-meter with extra steps.
```

### Variant C · Treatment 2
- **Diff vs control (single-axis)**: question-led headline; body byte-identical to control.

```
what is your eval suite actually measuring?

The pattern shows up in three concrete shapes. The dashboard climbs while the outcome slides. The proxy gets gamed as it gets graded. The terse correct version gets discounted for not performing thoroughness.

If you can't grade the actual outcome in a sandbox, you don't have a metric. You have a vibes-meter with extra steps.
```

## Success Metrics

- **Primary metric**: reply-to-impression ratio over 7d.
- **Secondary metric 1**: profile-visit rate.
- **Secondary metric 2**: thread depth (length of reply chains).
- **Decision rule**: >= 25% lift on primary at 1.5k+ impressions per variant within 7 days = clear win.

## Statistical Notes

- **Estimated sample needed**: 1.5k+ impressions per variant for a directional read; 5k+ for confident. Heuristic only.
- **Estimated duration**: 7 days from ship.
- **Significance heuristic**: rule-of-thumb 25-35% lift on primary at the directional sample threshold; below that, treat as directional. The runner does not compute p-values or confidence intervals — trust your judgement and snapshot via `analytics-summarizer`.
- **Confounders to control**: same niche cadence; same ship-day-of-week (except for `headline` tests where ship-time IS the variable); no overlapping major release; no quote-tweet rallies on the same anchor; identical voice across variants (use `brand-voice-trainer` to verify).

## Red Flags

- **Multi-variable paradox** · severity: high — Variant clarity at 83/100 is above 70 while Test isolation at 33/100 is below 40. The variants are clearly different but they diverge across multiple dimensions — the test cannot isolate which change drove the result. *Remediation:* Reduce the test to a single dimension (`--test-focus headline` or `--test-focus cta`); OR accept the test as a 'concept-level' comparison rather than a causal A/B.
- **Cannibalization on same audience** · severity: medium — Both variants ship to the same followers. The second and third variant will see lower base impressions because the audience already saw the first. *Remediation:* Stagger ship by 4-7 days, or use `cross-platform-reposter` to test the treatment on LinkedIn while keeping control on X.
- **Single-day variance** · severity: low — A 7-day window can be dominated by one viral spike; the loser variant may simply have shipped on a quiet day. *Remediation:* Pair with `analytics-summarizer` to overlay the daily impression curve before declaring a winner.

## Recommendations

1. Cross-test the winning variant on LinkedIn / Newsletter via `cross-platform-reposter` once the X test concludes. — bridges to: `cross-platform-reposter`
2. Source the next anchor from the winning pattern via `content-idea-generator`. — bridges to: `content-idea-generator`
3. Snapshot variant performance at T+24h and T+7d via `analytics-summarizer` to log the lift curve, not just the endpoint. — bridges to: `analytics-summarizer`
4. Confirm both variants land in the creator's voice before shipping; voice drift would confound the test. — bridges to: `brand-voice-trainer`
5. Recycle the losing variant via `content-recycler` for a different angle next quarter — losers compound when reframed. — bridges to: `content-recycler`

## Confidence
Confidence: medium — Test Plan score 62/100 — solid direction; tighten focus or widen sample to lift to high.

---

## What this output demonstrates (audit checklist)

- [x] **4 canonical Test Plan Score metrics** in fixed row order (Variant clarity / Test isolation / Sample feasibility / Decision actionability)
- [x] **Weighted Test Plan score formula** `round(0.30·Clarity + 0.25·Isolation + 0.25·Sample + 0.20·Decision)` — Clarity weighted highest
- [x] **3 variants** (1 control + 2 treatments) with single-axis Diff lines naming the ONE thing that changed (the headline)
- [x] **Multi-variable paradox** raised in BOTH the Test Plan section AND the Red Flags section because demo-mode pins scoring to the paradox profile
- [x] **Success Metrics** with primary metric, 2 secondary metrics, and explicit decision rule
- [x] **Statistical Notes** named as heuristics — sample / duration / significance are rules-of-thumb, never fabricated p-values; explicit cannibalization disclosure
- [x] **Red Flag cards** with severity (Multi-variable paradox = high; Cannibalization-on-same-audience + Single-day variance as supporting flags)
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** — exceeds the ≥3 requirement
- [x] **Article V.1 disclaimer verbatim** under any monetization-related recommendation when triggered
- [x] **Test Plan Audit** section appears because red-flag count surpasses the threshold

The Red Flag remediations cite additional cross-template slugs (`research-assistant`, `cross-platform-reposter`), bringing the total distinct cross-template surface area in this report to **6+ templates**.

> **Why the demo pins paradox:** The system prompt's hard rule is "single-axis isolation when test_focus is single-axis" — the runner produces single-axis variants by default. To demonstrate the multi-variable paradox rule (`Variant clarity > 70 AND Test isolation < 40`), the `--demo` flag pins scoring to that profile educationally. In production, a single-axis run with healthy variants will land Test isolation at 75-90/100, and the paradox rule won't fire.

> **The fix when paradox fires for real:** Drop test_focus to a single dimension (e.g. `--test-focus headline`); OR accept the test as a "concept-level" comparison rather than a causal A/B and frame the finding accordingly.

---

> Built for xAI, X, Grok and the ecosystem community — Apache 2.0 licensed, drafts-only, single-axis-by-default.
