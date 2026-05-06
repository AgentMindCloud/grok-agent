<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community — example output of the AB Test Suggester. -->

# Example output — niche: productivity / habit-stacking (healthy single-axis CTA test)

> 🔒 **Drafts only.** Variants below are text the creator reviews and ships themselves. The runner never auto-publishes.
>
> 🔒 **Single-axis isolation.** This run targets the `cta` dimension only — the hook and body are byte-identical across all 3 variants; only the closing line changes.
>
> *Built for xAI, X, Grok and the ecosystem community — productivity creators feel CTA tests first because the audience is in a self-improvement frame, and the gap between question-CTA and concrete-action-CTA is large.*

| Field | Value |
|---|---|
| Creator handle | `@habitstacker` |
| Post idea | `Stop optimizing for the morning routine — optimize for the friction your evening self leaves the morning self to clean up.` |
| Test focus | `cta` (single-axis — closing line only) |
| Variants | **3** (1 control + 2 treatments) |
| Sections emitted | **8** (no Test Plan Audit — clean single-axis test on a clear idea) |
| Multi-variable paradox? | **No** — Test isolation high (single-axis enforced), Variant clarity high; equivalent rule (cannibalization-on-same-audience) surfaced as a Red Flag |

To regenerate this output deterministically:

```powershell
python .\run.py --x-handle habitstacker --demo-productivity --test-focus cta --num-variants 3 --no-banner
```

---

## Test Snapshot
**@habitstacker: cta-only A/B test on the idea — control vs 2 treatment(s).**

- **X handle**: @habitstacker
- **Post idea**: Stop optimizing for the morning routine
- **Test focus**: cta
- **Variants requested**: 3 (1 control + 2 treatments)
- **Hypothesis**: A concrete-action CTA will outperform a generic question CTA on profile-visit rate over a 7-day window.

## Test Plan

| Metric | Score | Interpretation |
|---|---|---|
| Variant clarity | 85/100 | Treatments diverge sharply from control on the chosen dimension. |
| Test isolation | 86/100 | Single-axis test — only the cta dimension changes; rest is byte-identical. |
| Sample feasibility | 69/100 | Sample feasible at 14-21 days; below that, the read will be noisy. |
| Decision actionability | 67/100 | Result leads to a directional decision; further tests likely needed. |

**Test Plan score**: 78/100

## Variants

### Variant A · Control
- **Diff vs idea**: control — closes on a generic question.

```
Stop optimizing for the morning routine — optimize for the friction your evening self leaves the morning self to clean up.

What are you actually measuring?
```

### Variant B · Treatment
- **Diff vs control (single-axis)**: closes on a concrete action; rest of post byte-identical.

```
Stop optimizing for the morning routine — optimize for the friction your evening self leaves the morning self to clean up.

If this lands, drop the proxy this week and watch the dashboard regress on purpose.
```

### Variant C · Treatment 2
- **Diff vs control (single-axis)**: closes on a DM-prompt; rest of post byte-identical.

```
Stop optimizing for the morning routine — optimize for the friction your evening self leaves the morning self to clean up.

DM if you want the case-study breakdown.
```

## Success Metrics

- **Primary metric**: profile-visit rate (visits / impressions).
- **Secondary metric 1**: DM volume in the 24h after each variant ships.
- **Secondary metric 2**: follow rate.
- **Decision rule**: >= 30% lift on primary at 1k+ impressions per variant within 7 days = clear win.

## Statistical Notes

- **Estimated sample needed**: 1k+ impressions per variant for a directional read; 3k+ for confident. Heuristic only.
- **Estimated duration**: 7 days from ship.
- **Significance heuristic**: rule-of-thumb 25-35% lift on primary at the directional sample threshold; below that, treat as directional. The runner does not compute p-values or confidence intervals — trust your judgement and snapshot via `analytics-summarizer`.
- **Confounders to control**: same niche cadence; same ship-day-of-week (except for `cta` tests where ship-time IS the variable); no overlapping major release; no quote-tweet rallies on the same anchor; identical voice across variants (use `brand-voice-trainer` to verify).

## Red Flags

- **Cannibalization on same audience** · severity: medium — Both variants ship to the same followers. The second and third variant will see lower base impressions because the audience already saw the first. *Remediation:* Stagger ship by 4-7 days, or use `cross-platform-reposter` to test the treatment on LinkedIn while keeping control on X.
- **Single-day variance** · severity: low — A 7-day window can be dominated by one viral spike; the loser variant may simply have shipped on a quiet day. *Remediation:* Pair with `analytics-summarizer` to overlay the daily impression curve before declaring a winner.

## Recommendations

1. Source the next anchor from the winning pattern via `content-idea-generator`. — bridges to: `content-idea-generator`
2. Recycle the losing variant via `content-recycler` for a different angle next quarter — losers compound when reframed. — bridges to: `content-recycler`
3. Cross-test the winning variant on LinkedIn / Newsletter via `cross-platform-reposter` once the X test concludes. — bridges to: `cross-platform-reposter`
4. Confirm both variants land in the creator's voice before shipping; voice drift would confound the test. — bridges to: `brand-voice-trainer`
5. Snapshot variant performance at T+24h and T+7d via `analytics-summarizer` to log the lift curve, not just the endpoint. — bridges to: `analytics-summarizer`

## Confidence
Confidence: high — single-axis test on cta, clear idea, sample feasible, decision rule explicit.

---

## What this output demonstrates (audit checklist)

- [x] **4 canonical Test Plan Score metrics** in fixed row order with HEALTHY scores — Variant clarity in the high-70s, Test isolation in the high-70s, no paradox fires
- [x] **Weighted Test Plan score formula** `round(0.30·Clarity + 0.25·Isolation + 0.25·Sample + 0.20·Decision)` applied per the same formula as example 1
- [x] **3 variants** (1 control + 2 treatments) with single-axis Diff lines naming the ONE thing that changed (the closing CTA)
- [x] **No multi-variable paradox** in this run — single-axis isolation kept Test isolation above 70, so the rule doesn't fire (this is the canonical healthy baseline)
- [x] **Equivalent rule surfaced** — Cannibalization-on-same-audience flag fires because the variants ship to the same followers (system-prompt-required disclosure)
- [x] **Success Metrics** with primary metric (profile-visit rate), 2 secondary metrics, and explicit decision rule
- [x] **Statistical Notes** named as heuristics — sample / duration / significance are rules-of-thumb only
- [x] **Red Flag cards** with severity (Cannibalization = medium, Single-day variance = low)
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** — exceeds the ≥3 requirement
- [x] **Article V.1 disclaimer** attaches verbatim if a monetization-related recommendation fires

### Compared to the AI-niche example

| Dimension | `niche-ai-agents.md` | `niche-productivity.md` |
|---|---|---|
| Test focus | `headline` (paradox-pinned demo mode) | `cta` (heuristic scoring, healthy) |
| Variants | 3 (single-axis on headline) | 3 (single-axis on closing line) |
| Multi-variable paradox? | Yes — surfaced in BOTH places | No — single-axis isolation holds |
| Test Plan Audit triggered? | Yes (high red-flag count) | No (clean test) |
| Equivalent rule | Paradox + cannibalization + single-day variance | Cannibalization-on-same-audience + single-day variance |
| Demonstrates | The paradox firing path (educational) | The healthy baseline path (production-ready) |

Same schema and rules, different inputs → different rule demonstrations. Together the two examples cover the full surface of the ab-test-suggester's edge cases: the paradox firing (AI demo), the healthy single-axis baseline (productivity demo), and the cannibalization disclosure on the same-audience X-native default (both examples).

> **v1 limitation note:** like the prior templates, the runner's variant scaffolds are deterministic per-focus templates — they wrap the source idea with single-axis variant framing but they do not paraphrase the substance of the idea. A future v2 with Grok 4.3 in the loop would generate fully paraphrased variants while preserving the same scoring, paradox detection, single-axis enforcement, statistical-honesty, and cannibalization-disclosure invariants this v1 already enforces.

---

> Built for xAI, X, Grok and the ecosystem community — Apache 2.0 licensed, drafts-only, single-axis-by-default.
