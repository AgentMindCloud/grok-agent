<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🧪 AB Test Suggester

> Turn any post idea into a ready-to-run A/B test plan with 2-3 variants isolated to a single test dimension (headline / visual / cta / timing). 4 official Test Plan Score metrics, multi-variable paradox detection, statistical heuristics (no fabricated p-values), explicit cannibalization disclosure, ≥3 cross-template bridges. Drafts only. Single-axis by default.
>
> *Built for xAI, X, Grok and the ecosystem community — winning the platform battle on X. Every X creator deserves a tester that decides on signal, not vibes.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits a test plan + variant text that the creator reviews and ships themselves. The runner never auto-publishes anywhere. Constitution Article II's `publish_to_x` consent gate covers every variant.

> 🔒 **Single-axis isolation.** When test_focus is one of `headline / visual / cta / timing`, variants vary on that one dimension only — body byte-identical across variants. Multi-dimensional variation is a hard refusal because it invalidates the test (you can't isolate which change drove the result).

> 🔒 **No fabricated statistics.** Sample-size, duration, and significance estimates are rough heuristics named as such. The runner refuses to print invented p-values, confidence intervals, or absolute lift numbers.

> 🔒 **Cannibalization disclosure.** When variants ship to the same audience without splitting reach (the X-native default), the runner names the cannibalization risk explicitly — variants compete for impressions in that mode.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\ab-test-suggester\`. The v1 runner makes zero external network calls — it is offline-safe.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any test or recommendation that touches monetization tactics or paid-tier funnels.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns one post idea (URL or pasted text) plus a chosen test_focus into a 6/7-section structured A/B test plan.

The report shape is the same every time:

1. **Test Snapshot** — one-sentence summary + 5-bullet metadata including the testable Hypothesis
2. **Test Plan** — 4-row metric table (Variant clarity / Test isolation / Sample feasibility / Decision actionability) + weighted Test Plan score `round(0.30·Clarity + 0.25·Isolation + 0.25·Sample + 0.20·Decision)`
3. **Variants** — 2-3 cards (1 control + 1-2 treatments), each with a single-axis Diff line and a code-fenced post body
4. **Success Metrics** — primary + 1-2 secondary + explicit decision rule
5. **Statistical Notes** — sample / duration / significance heuristics + confounders to control + cannibalization disclosure
6. **Red Flags** — 2-4 cards with severity, surfaces the **multi-variable paradox** in BOTH this section AND the Test Plan section when Variant clarity > 70 AND Test isolation < 40
7. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges
8. **Confidence**
9. **Test Plan Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR test_focus = `all`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\ab-test-suggester\run.py --x-handle JanSol0s --demo --test-focus headline --num-variants 3
```

That prints the 8-section report (3 single-axis headline variants with paradox-pinned scoring for educational purposes) straight to your terminal.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install ab-test-suggester
```

### Option B — direct invocation (developer mode)

```powershell
# Headline-focused single-axis test on a real idea
python .\templates\creator\ab-test-suggester\run.py `
  --x-handle JanSol0s `
  --post-idea-or-url "Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness." `
  --test-focus headline `
  --num-variants 3

# CTA test (single-axis closing-line only)
python .\templates\creator\ab-test-suggester\run.py `
  --x-handle habitstacker `
  --demo-productivity `
  --test-focus cta `
  --num-variants 3

# Timing test (same body, different ship times)
python .\templates\creator\ab-test-suggester\run.py `
  --x-handle JanSol0s `
  --post-idea-or-url "..." `
  --test-focus timing `
  --num-variants 2

# 'all' focus (runner picks the best dimension)
python .\templates\creator\ab-test-suggester\run.py `
  --x-handle JanSol0s `
  --demo `
  --test-focus all

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\ab-test-suggester\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\ab-test-suggester\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--post-idea-or-url` | yes (or `--demo` / `--demo-productivity`) | Either an `x.com` URL or the literal idea text |
| `--test-focus` | optional | `headline` \| `visual` \| `cta` \| `timing` \| `all` (default `headline`) |
| `--num-variants` | optional | 2 or 3 (default 2) |
| `--demo` | optional | Use the official AI demo idea; pins paradox profile educationally |
| `--demo-productivity` | optional | Use a productivity demo idea; healthy single-axis (no paradox) |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator reviews and ships. Never includes a `publish` action or anything the runner could execute.
2. **Single-axis isolation.** When `test_focus` is one of `headline / visual / cta / timing`, the runner's variant scaffolds change exactly that one dimension. Body is byte-identical across variants for `headline` / `visual` / `cta` / `timing`.
3. **Multi-variable paradox** must surface in BOTH the Test Plan section AND the Red Flags section when Variant clarity > 70 AND Test isolation < 40. The runner's `--demo` mode pins scoring to this profile so the rule reliably demonstrates.
4. **Test Plan score formula is fixed.** `round(0.30·Variant clarity + 0.25·Test isolation + 0.25·Sample feasibility + 0.20·Decision actionability)`. Variant clarity weighted highest because if you can't tell variants apart, no other metric matters.
5. **No fabricated statistics.** Sample-size / duration / significance are heuristics named as such. Refuses to invent p-values or absolute lift numbers.
6. **Cannibalization disclosure.** When variants ship to the same audience, the Red Flags section names the risk explicitly. Remediation: stagger ship by 4-7 days OR cross-test on adjacent platform via `cross-platform-reposter`.

---

## Cross-template daily flow (Grok Agent OS for creators)

AB Test Suggester is the experimentation layer of the Grok Agent OS creator suite. The recommended per-anchor flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Pre-launch — design the test                                     │
│  └─ ab-test-suggester       → 6/7-section test plan + variants    │
│       │                                                           │
│       ├─ paradox flagged?   → drop test_focus to single dimension │
│       ├─ cannibalization?   → stagger ship OR cross-platform-test │
│       └─ ready to ship?     → confirm voice via brand-voice-trainer│
│                                                                   │
│  Launch                                                           │
│  └─ thread-builder          → polish each variant body            │
│  └─ analytics-summarizer    → snapshot baseline at T-0            │
│                                                                   │
│  Mid-test (T+24h)                                                 │
│  └─ analytics-summarizer    → log lift curve, not just endpoint   │
│                                                                   │
│  Post-test (T+7d)                                                 │
│  └─ analytics-summarizer    → declare winner per decision rule    │
│  └─ content-recycler        → recycle losing variant for next     │
│                                quarter (different angle)          │
│  └─ content-idea-generator  → next anchor in winning pattern      │
│  └─ cross-platform-reposter → cross-test winner on LinkedIn       │
│                                                                   │
│  Quarterly                                                        │
│  └─ growth-experiment-runner → promote winning A/B to 4-week      │
│                                 growth experiment                 │
└──────────────────────────────────────────────────────────────────┘
```

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `analytics-summarizer` | `templates/creator/` | Snapshot variants at T+24h and T+7d to log lift curve, not just endpoint |
| `content-idea-generator` | `templates/creator/` | Source the next anchor in the winning pattern |
| `thread-builder` | `templates/creator/` | Polish each variant body before shipping |
| `brand-voice-trainer` | `templates/creator/` | Confirm both variants land in the creator's voice (voice drift = confound) |
| `content-recycler` | `templates/creator/` | Recycle the losing variant for a different angle next quarter |
| `cross-platform-reposter` | `templates/creator/` | Cross-test the winning variant on adjacent platforms |
| `competitor-watch` | `templates/creator/` | Confirm the win wasn't niche-narrow |
| `quote-tweet-suggestor` | `templates/creator/` | Riff on the winning variant via quote-tweet |
| `monetization-optimizer` | `templates/creator/` | Tune monetization tests separately (carries V.1 disclaimer) |
| `mention-summarizer` | `templates/creator/` | Spot which variant converted to follow-on conversation |
| `growth-experiment-runner` | `templates/creator/` | Promote winning A/B to 4-week experiment with larger sample |
| `research-assistant` | `templates/general/` | Background on statistical heuristics for unfamiliar metrics |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\ab-test-suggester\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\ab-test-suggester\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\ab-test-suggester\logs\` |
| System prompt | `templates\creator\ab-test-suggester\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_ab_test_plan` (bound to `ab_test_suggester.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, II, V, VII for A/B test design
- **5 hard refusals**: auto-publish without consent gate; multi-axis variants on single-axis runs; fabricated statistical significance; algorithm-manipulation tests; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × `--demo` × `headline` × 3 variants | Multi-variable paradox firing (demo educational pin) |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × `--demo-productivity` × `cta` × 3 variants | Healthy single-axis CTA test (no paradox; cannibalization disclosed) |

Together the two examples cover the full surface: the paradox firing (AI demo), the clean single-axis baseline (productivity demo), and the cannibalization disclosure on the same-audience X-native default (both examples).

---

## v1 limitation note

Like the prior templates in the suite, the runner's variant scaffolds are **deterministic per-focus templates** — they wrap the source idea with single-axis variant framing (only the chosen dimension changes). A future v2 with Grok 4.3 in the loop would generate fully paraphrased variants while preserving the same scoring, paradox detection, single-axis enforcement, statistical-honesty, and cannibalization-disclosure invariants this v1 already enforces.

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P77 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P78 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing experimentation layer that turns "should I post the punchy or the thoughtful version?" from a vibes-check into a structured single-axis A/B with explicit decision rules — without inventing p-values, without auto-publishing, and without flattening voice across variants.
