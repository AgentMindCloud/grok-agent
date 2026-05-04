<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🧵 Thread Builder

> Draft 3-5 ready-to-post X threads in the creator's voice, score them with 4 canonical Thread Plan metrics, surface the hook-without-payoff paradox, ship 4-6 alternate hooks (≤ 240 chars each), forecast content-engagement bands (never absolute counts), and bridge into ≥ 3 sister templates — always including `analytics-summarizer` and `content-idea-generator`. Drafts only. Never auto-publishes. Never copies competitors.
>
> *Built for X, Grok & the ecosystem community — every X creator deserves a long-form drafting layer that earns the read instead of clickbaiting it.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator pastes into the X composer themselves. The runner never auto-publishes, never auto-schedules, never DMs a draft. The Constitution Article II `publish_to_x` consent gate covers any future-version downstream sharing.

> 🔒 **Variant cap of 5.** Cognitive load on the creator above 5 variants destroys the value of A/B selection. The runner refuses `--variants > 5` with a hard error.

> 🔒 **Hook character cap of 240.** Every hook (Post 1) and every Hook Variation entry is enforced ≤ 240 characters at render time so it composes inside an X post body.

> 🔒 **Voice fidelity is creator-only.** The runner accepts voice samples via `--voice-samples-file` (a JSON list of the creator's own posts). It never scores voice against samples authored by a different handle, and it never copy-pastes a competitor's hook, signature phrasing, or thread structure into a variant.

> 🔒 **Content-engagement bands only.** Predicted engagement is reported as a 0-100 sub-score plus a `low` / `medium` / `high` band — never an absolute like / repost / reply count. Revenue, paid-tier conversion, sponsorship dollars, ad spend, and affiliate splits are out of scope and routed to `monetization-optimizer`.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\thread-builder\`. The v1 runner makes zero external network calls — it is offline-safe and runs cleanly without any X API token.

> 🔒 **Hook-without-payoff paradox detection.** When any variant shows Hook strength > 80 AND Narrative arc coherence < 50, the runner surfaces the paradox in BOTH the Thread Plan Performance section AND the Red Flags section so the creator can never accidentally ship a clickbait thread that erodes trust over time.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied topic / goal (and optional voice samples + analytics export) into the strict 6/7-section thread plan defined by the merged P87 system prompt — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Thread Snapshot** — one-sentence headline + 6-bullet metadata including the explicit data-source line
2. **Thread Plan Performance** — 4-row metric table (Hook strength / Narrative arc coherence / Voice fidelity / Predicted engagement) + weighted Thread Plan score `round(0.30·Hook + 0.25·Arc + 0.25·Voice + 0.20·PredictedEngagement)`
3. **Thread Variants (3-5; drafts only)** — each with a per-variant header `(Hook X · Arc X · Voice X)`, a `Hook (Post 1)` line ≤ 240 chars, a numbered `Arc beats` list, and a `Why this lands` 2-line case
4. **Hook Variations** — 4 alternates for `variant_count ≤ 4`, 6 alternates when `variant_count = 5`, each ≤ 240 chars, drawn from the canonical style set (`numbers-led` · `contrarian-claim` · `question-led` · `story-cold-open` · `list-tease` · `personal-anecdote`)
5. **Engagement Forecast** — `low` / `medium` / `high` band + sub-score + drivers + `Anchored to analytics-summarizer?` + `Highest-EV variant`
6. **Red Flags** — 2-5 cards with severity, surfaces the **hook-without-payoff paradox** in BOTH this section AND the Thread Plan Performance row when triggered
7. **Recommendations** — 3-5 next moves, ≥ 3 distinct cross-template bridges, `analytics-summarizer` + `content-idea-generator` always present
8. **Confidence**
9. **Thread Audit** *(optional, auto-appended)* — fires when red-flag count > 3 OR `variant_count == 5` OR data source is seeded demo with no voice samples

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\thread-builder\run.py --x-handle JanSol0s --demo
```

That prints the canonical 3-variant healthy demo report (analytical / personal / tactical registers on `agent-eval failure modes`) straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/thread-builder/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install thread-builder
```

### Option B — direct invocation (developer mode)

```powershell
# Real run with the creator's own topic + voice samples + analytics export
python .\templates\creator\thread-builder\run.py `
  --x-handle JanSol0s `
  --topic "agent-eval failure modes" `
  --voice-samples-file $env:LOCALAPPDATA\grok-agent\thread-builder\my-voice.json `
  --analytics-file   $env:LOCALAPPDATA\grok-agent\thread-builder\my-analytics.json `
  --variants 3 `
  --thread-length medium `
  --tone all

# Healthy 3-variant demo (analytical / personal / tactical)
python .\templates\creator\thread-builder\run.py --x-handle JanSol0s --demo

# Hook-without-payoff paradox demo (Variant 1 rigged Hook 88 + Arc 42)
python .\templates\creator\thread-builder\run.py --x-handle JanSol0s --demo-paradox

# 5-variant cap demo (auto-triggers Thread Audit; all 4 canonical registers)
python .\templates\creator\thread-builder\run.py --x-handle habitstacker --demo-five-variants

# Save the report to the agent's AppData folder (Apache 2.0 HTML header is prepended)
python .\templates\creator\thread-builder\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\thread-builder\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--topic` (alias `--topic-or-goal`, `--goal`) | yes (or one of the `--demo-*` flags or `--input-file`) | Thread topic / thesis / goal in plain text |
| `--voice-samples-file` | optional | Path to a JSON list of the creator's own recent post bodies (anchors Voice fidelity) |
| `--analytics-file` | optional | Path to an `analytics-summarizer` JSON export (anchors Predicted engagement) |
| `--variants` (alias `--variant-count`) | optional | 3-5 (default 3); the runner refuses anything outside this band |
| `--thread-length` | optional | `short` (5 posts) \| `medium` (8) \| `long` (12); default `medium` |
| `--tone` (alias `--tone-focus`) | optional | `analytical` \| `personal` \| `tactical` \| `narrative` \| `all`; default `all` |
| `--input-file` | optional | Path to a brief-bundle JSON (encapsulates topic + voice + analytics + counts) |
| `--demo` | optional | Canonical 3-variant healthy demo (`agent-eval failure modes`) |
| `--demo-paradox` | optional | Paradox-firing demo (`creator burnout patterns`, Variant 1 rigged Hook 88 + Arc 42) |
| `--demo-five-variants` | optional | 5-variant cap demo (`weekly maker rituals`, all 4 registers) |
| `--output` | optional | Save the rendered report to a path (Apache 2.0 HTML header prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## Brief-bundle JSON schema (`--input-file`)

The runner accepts a JSON bundle shaped like the bundled examples (`examples/sample-1-input.json`, `sample-2-input.json`, `sample-3-input.json`):

```json
{
  "x_handle": "@<your-handle>",
  "topic_or_goal": "<plain-text topic / thesis / goal>",
  "variant_count": 3,
  "thread_length": "medium",
  "tone_focus": "all",
  "voice_samples": [
    "<recent post body authored by --x-handle>",
    "<another recent post body — 5-10 samples is the healthy band>"
  ],
  "analytics_file": "C:/path/to/analytics-export.json",
  "data_source": "real",
  "score_overrides": {
    "1": {"hook": 88, "arc": 42, "voice": 64}
  }
}
```

`data_source` is `"real"` for a real run or `"demo"` to label every metric with `[demo metric — re-run with --voice-samples-file for real-creator scoring]`. `score_overrides` is reserved for paradox / edge-case demos and should not be used in real runs.

---

## How the report is shaped (the 11 hard rules)

1. **Drafts only.** Output is text the creator copy-pastes into X themselves; the runner never publishes, schedules, or DMs.
2. **No fabricated engagement absolutes.** Predicted engagement is reported as a 0-100 sub-score + band (`low` / `medium` / `high`). Demo runs are labelled explicitly. The runner refuses to print absolute like / repost / reply / bookmark counts it cannot derive from the supplied analytics file.
3. **Hook-without-payoff paradox** must surface in BOTH the Thread Plan Performance section AND the Red Flags section when any variant shows Hook strength > 80 AND Narrative arc coherence < 50.
4. **Thread Plan score formula is fixed.** `round(0.30·Hook + 0.25·Arc + 0.25·Voice + 0.20·PredictedEngagement)`. Hook weighted highest because the first post determines whether the thread is read at all; Arc and Voice tied at 0.25 because either failing alone defeats the thread; Predicted engagement weighted lowest because it is a heuristic — the real read happens after publish.
5. **5-arrow trend bucketing** (`▲▲ / ▲ / ▬ / ▼ / ▼▼`) computed against each metric's healthy floor (60 for Hook / Arc / Voice; 50 for Predicted engagement), with thresholds at ±5 / ±25 sub-score points.
6. **Voice fidelity is creator-only.** The runner refuses to score voice against samples authored by a handle other than `--x-handle`, and refuses to copy a competitor's hook, signature phrasing, or thread structure into any variant.
7. **Variant cap of 5.** The runner never emits more than 5 variants; cognitive load above 5 destroys the value of A/B selection.
8. **Hook character cap of 240.** Every hook (Post 1) and every Hook Variation entry is enforced ≤ 240 characters at render time so each composes inside an X post body.
9. **Out-of-scope refusal.** If the topic crosses into monetization, paid-tier, sponsorship, ad-revenue, or affiliate territory, the runner emits a structured refusal that names `monetization-optimizer` and stops — it never improvises a revenue projection.
10. **Mandatory bridges.** Every render (including the refusal path) names ≥ 3 cross-template bridges; `analytics-summarizer` and `content-idea-generator` are always present.
11. **Honesty about data source.** Every Thread Snapshot names whether the data is from real voice samples + analytics OR seeded demo. The two paths are visibly distinguishable.

---

## Cross-template daily flow

Thread Builder is the **long-form drafting layer** of the Grok Agent OS creator suite. Reciprocally, this template's recommendations point creators back into the suite to act on the drafts:

```
┌──────────────────────────────────────────────────────────────────┐
│  Per-anchor — draft                                               │
│  └─ thread-builder          → 3-5 variants + 4-6 alternate hooks  │
│       │                                                           │
│       ├─ paradox flagged?   → rebuild middle posts OR soften hook │
│       ├─ voice samples thin?→ brand-voice-trainer for a profile   │
│       └─ winning variant?   → ab-test-suggester (single-axis A/B) │
│                                                                   │
│  Pre-publish                                                      │
│  └─ competitor-watch        → confirm tone register is unique     │
│  └─ hashtag-strategy-advisor→ pick 0-2 substantive tags (X cap)   │
│                                                                   │
│  Publish-day                                                      │
│  └─ comment-engagement-     → comment-stack plan to anchor the    │
│     booster                   algorithmic surface                  │
│  └─ reply-drafter           → engage substantively with new replies│
│                                                                   │
│  Post-publish (7d)                                                │
│  └─ analytics-summarizer    → measure the actual read            │
│  └─ content-idea-generator  → source the next anchor in cluster   │
│                                                                   │
│  Quarterly                                                        │
│  └─ content-recycler        → recycle the winning thread under a  │
│                                fresh angle                         │
│  └─ cross-platform-reposter → adapt to LinkedIn / Newsletter       │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\thread-builder\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\thread-builder\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\thread-builder\logs\` |
| System prompt | `templates\creator\thread-builder\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Healthy 3-variant draft (analytical / personal / tactical) | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | Hook-without-payoff paradox firing on Variant 1 | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | 5-variant cap (Thread Audit auto-triggered; all 4 registers) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete brief bundle; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py --x-handle <handle> --input-file .\examples\sample-N-input.json --no-banner
```

(Equivalent demo flags also reproduce each pair: `--demo`, `--demo-paradox`, `--demo-five-variants`.)

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_thread_plan` (bound to `thread_builder.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **8 Constitution rules** specialising Articles I, II, III, V, VII for thread-drafting work
- **7 hard refusals**: auto-publish / auto-schedule / auto-DM; fabricate absolute engagement counts; score voice against another creator's posts; copy a competitor's hook or signature phrasing; emit > 5 variants; scrape authenticated X content; predict revenue / paid-tier / sponsorship dollars
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\thread-builder\grok-agent.yaml
python safety\scanner.py scan  templates\creator\thread-builder\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it shapes variants from a per-register template set, applies the weighted scoring formula, surfaces the paradox in both required places, builds 4-6 alternate hooks under the 240-character cap, and emits the strict 6/7-section schema. A future v2 could optionally call Grok 4.3 to generate richer per-variant copy while preserving the same scoring, paradox detection, demo-vs-real labelling, variant cap, hook cap, monetization refusal, and mandatory-bridge invariants this v1 already enforces.

The value the runner adds in v1:

1. The 4-metric weighted scoring with explicit per-variant Hook / Arc / Voice rows
2. The hook-without-payoff paradox detection (firing in both required places)
3. The 5-arrow trend bucketing with 60 / 50 healthy floors
4. The 4 canonical tone registers, with the runner enforcing diversity when `tone_focus = all`
5. The Hook Variations bank (4-6 alternates ≤ 240 chars each, drawn from the canonical style set)
6. The hard variant cap of 5 + hard hook cap of 240
7. The monetization-topic guard with structured refusal + mandatory bridges
8. The mandatory `analytics-summarizer` + `content-idea-generator` bridges in every render
9. The deterministic seeded recommendation shuffle (reproducible reports across runs)
10. The Thread Audit auto-trigger (red-flag overflow / 5-variant cap / demo with no voice samples)

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P87 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P88 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built for X, Grok & the ecosystem community.
