<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 💡 Content Idea Generator

> Five fresh post ideas every morning, scored against your niche, the last 7 days of trends, and your own voice. Each idea ships with a predicted engagement band and a cross-template bridge that hands off cleanly to the next loop. Drafts only. Never auto-publishes. Never invents engagement counts.
>
> *Built for X, Grok & the ecosystem community — every X creator deserves a daily ideation layer that names where each idea is supposed to land before they hit publish.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator pastes into the X composer themselves; the runner never publishes, schedules, or DMs. Constitution Article II's `publish_to_x` consent gate covers any future-version downstream sharing.

> 🔒 **No fabricated engagement counts.** The runner refuses to print absolute like / repost / reply counts it didn't derive from the supplied input. Every idea reports a 0-100 sub-score plus a low / medium / high band — never an absolute number. When `--voice-samples-file`, `--trends-file`, or `--analytics-file` is not provided, every metric in the output is labelled `[demo metric — re-run with --voice-samples-file for real-creator scoring]` so seeded demo runs can never be mistaken for real ideation.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\content-idea-generator\`. The v1 runner makes zero external network calls — it is offline-safe and runs cleanly without any X API token.

> 🔒 **Vanity-hook paradox detection.** When any single idea has Trend alignment above 80 AND Niche fit below 50, the runner surfaces the paradox in BOTH the Idea Plan Performance section AND the Red Flags section so the creator can never accidentally publish a viral-shaped hook for the wrong audience.

> 🔒 **No financial content.** When the supplied niche crosses into revenue, paid-tier, sponsorship, ad-spend, affiliate, or cashtag territory, the runner emits a structured refusal that points the creator at `monetization-optimizer` and stops. Content-idea-generator strictly stays inside the content-engagement loop.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied niche (and optional 7-day trend snapshot + voice samples + analytics export) into the strict 6/7-section idea plan defined by the merged Slot-1 contract — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Run Snapshot** — one-sentence headline + 5-bullet metadata including the explicit data-source line
2. **Idea Plan Performance** — 4-row metric table (Niche fit / Trend alignment / Voice fidelity / Predicted engagement) + weighted Idea Plan score `round(0.30·NicheFit + 0.25·TrendAlign + 0.25·Voice + 0.20·Predicted)`
3. **The N Ideas** — 5 by default (3-10 via `--count`); each idea carries hook text, format, per-idea sub-scores, suggested publish window, why-it-works copy, and an explicit `Bridges to: <slug>` line
4. **Trend Alignment** — which 7-day trend each idea touches (when `--trends-file` is supplied)
5. **Red Flags** — 1-4 cards with severity, surfaces the **vanity-hook paradox** in BOTH this section AND the Idea Plan Performance row when triggered
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges; `analytics-summarizer` and `thread-builder` are always present
7. **Confidence**
8. **Idea Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR `--count >= 8` OR the vanity-hook paradox fires OR the run is a demo with no anchor files

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\content-idea-generator\run.py --x-handle JanSol0s --demo
```

That prints the 5-idea punchy-tone demo (niche `agent-eval tooling for X creators`) straight to the terminal with the auto-triggered Idea Audit at the bottom.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/content-idea-generator/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install content-idea-generator
```

### Option B — direct invocation (developer mode)

```powershell
# Real ideation (recommended — supply your own niche)
python .\templates\creator\content-idea-generator\run.py `
  --x-handle JanSol0s `
  --niche "agent-eval tooling for X creators" `
  --tone punchy `
  --count 5

# Anchor on real voice samples + trends + analytics for high confidence
python .\templates\creator\content-idea-generator\run.py `
  --x-handle JanSol0s `
  --niche "evening-friction audits for makers" `
  --tone thoughtful `
  --voice-samples-file $env:LOCALAPPDATA\grok-agent\content-idea-generator\voice.json `
  --trends-file       $env:LOCALAPPDATA\grok-agent\content-idea-generator\trends.json `
  --analytics-file    $env:LOCALAPPDATA\grok-agent\analytics-summarizer\last30.json

# Punchy demo (official 5-idea, no anchors)
python .\templates\creator\content-idea-generator\run.py --x-handle JanSol0s --demo

# Anchored demo (voice + trends + analytics; high-confidence run)
python .\templates\creator\content-idea-generator\run.py --x-handle habitstacker --demo-anchored

# Vanity-hook paradox demo (auto-triggers Idea Audit)
python .\templates\creator\content-idea-generator\run.py --x-handle JanSol0s --demo-paradox

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\content-idea-generator\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\content-idea-generator\reports\2026-05-05.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--niche` | yes (or `--input-file`, or one of the `--demo-*` flags) | Niche / topic anchor in plain text |
| `--tone` | optional | `punchy` \| `thoughtful` \| `data-led` \| `mixed` (default `punchy`) |
| `--count` | optional | 3-10 ideas per run (default 5; ≥8 auto-triggers Idea Audit) |
| `--voice-samples-file` | optional | Path to a JSON list of the creator's recent post bodies |
| `--trends-file` | optional | Path to a JSON list of last-7d niche trends (strings) |
| `--analytics-file` | optional | Path to an `analytics-summarizer` JSON export (anchors Predicted engagement) |
| `--input-file` | optional | Path to a brief bundle JSON (encapsulates niche + voice + trends + analytics + score overrides) |
| `--demo` | optional | Use the official 5-idea punchy-tone demo (`agent-eval tooling for X creators`) |
| `--demo-anchored` | optional | Use the high-confidence demo (voice + trends + analytics anchors) |
| `--demo-paradox` | optional | Use the vanity-hook paradox demo (auto-triggers Idea Audit) |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |
| `--when` | optional | Override the date used in the deterministic seed (ISO `YYYY-MM-DD`) — useful for reproducible example outputs |

---

## Brief-bundle schema (`--input-file`)

The runner accepts a JSON file shaped like the bundled examples (`examples/sample-1-input.json`, `sample-2-input.json`, `sample-3-input.json`). The contract:

```json
{
  "x_handle": "@<your-handle>",
  "niche": "<niche / topic anchor in plain text>",
  "tone": "punchy | thoughtful | data-led | mixed",
  "count": 5,
  "voice_samples": [
    "<one of the creator's recent post bodies>",
    "<another>"
  ],
  "trends": [
    "<last-7d trend phrase 1>",
    "<last-7d trend phrase 2>"
  ],
  "analytics_file": "<path to analytics-summarizer export, optional>",
  "data_source": "real | demo",
  "score_overrides": {
    "<idea-index>": {
      "niche_fit": <0-100>,
      "trend_align": <0-100>,
      "voice": <0-100>
    }
  }
}
```

If `data_source` is `"demo"` the runner labels every metric as a demo placeholder. Set it to `"real"` (or omit it) when supplying actual creator inputs so the report's Run Snapshot says `real voice samples + trends + analytics from --voice-samples-file / --trends-file / --analytics-file` (or the matching subset).

`score_overrides` is an optional escape hatch for examples and tests — it pins specific sub-scores for one or more idea indices so example outputs are reproducible across runs.

---

## How the report is shaped (the 7 hard rules)

1. **Drafts only.** Output is text the creator reads; the runner never publishes anywhere.
2. **No fabricated engagement counts.** Per-idea Predicted engagement is reported as a 0-100 sub-score plus a low / medium / high band — never an absolute count. Demo runs labelled explicitly.
3. **Vanity-hook paradox** must surface in BOTH the Idea Plan Performance section AND the Red Flags section when any idea has Trend alignment > 80 AND Niche fit < 50.
4. **Idea Plan score formula is fixed.** `round(0.30·NicheFit + 0.25·TrendAlign + 0.25·Voice + 0.20·Predicted)`. Niche fit weighted highest because off-niche ideas defeat the run regardless of hook quality; Trend alignment and Voice tied because either failing alone erodes audience trust; Predicted engagement weighted lowest because it is a heuristic until anchored to a real `analytics-summarizer` export.
5. **5-arrow trend bucketing** (▲▲ / ▲ / ▬ / ▼ / ▼▼) with thresholds at ±5% / ±25% vs the per-metric healthy floor.
6. **Mandatory bridges.** Every render (including the monetization-refusal path) names ≥3 cross-template bridges; `analytics-summarizer` and `thread-builder` are always included so the daily ideation loop hands off cleanly into measurement and into long-form drafting.
7. **Hook character cap of 240.** Every idea hook is enforced ≤240 characters at render time and truncated with an ellipsis if needed.

---

## Cross-template daily flow

Content Idea Generator is the **ideation layer** of the Grok Agent OS creator suite — every other template recommends it as a destination bridge for re-sourcing the next anchor topic. Reciprocally, this template's recommendations point creators forward into the suite to act on the ideas:

```
┌──────────────────────────────────────────────────────────────────┐
│  Daily — ideate                                                   │
│  └─ content-idea-generator → 5 fresh post ideas with bridges     │
│       │                                                           │
│       ├─ paradox flagged?    → drop the off-niche idea(s)        │
│       ├─ no voice samples?   → brand-voice-trainer (anchor voice) │
│       └─ best idea?          → thread-builder (build the thread)  │
│                                                                   │
│  Per-publish — measure                                            │
│  └─ analytics-summarizer    → 7/8-section period summary          │
│       │                                                           │
│       └─ winning archetype  → ab-test-suggester (single-axis A/B) │
│                                                                   │
│  Per-publish — engage                                             │
│  └─ reply-drafter           → engage with the audience the ideas  │
│                                bring in (voice-faithful)          │
│  └─ comment-engagement-     → seed the publish-day comment stack  │
│       booster                                                     │
│                                                                   │
│  Weekly                                                           │
│  └─ trend-aligned-poster    → capture next week's 7d trend file   │
│  └─ competitor-watch        → confirm angle is differentiated     │
│                                                                   │
│  Monthly                                                          │
│  └─ content-recycler        → resurface past anchors that match   │
│                                the surviving archetype            │
└──────────────────────────────────────────────────────────────────┘
```

Every Idea in this template's output ends with `Bridges to: <slug>` and every Recommendation ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\content-idea-generator\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\content-idea-generator\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\content-idea-generator\logs\` |
| System prompt | `templates\creator\content-idea-generator\prompts\system.md` (in-repo, optional) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Daily punchy 5-idea run (no anchors; audit auto-triggered) | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | High-confidence anchored run (voice + trends + analytics) | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | Vanity-hook paradox firing on idea 5 (audit auto-triggered) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete, runnable brief bundle; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py `
  --x-handle <handle> `
  --input-file .\examples\sample-N-input.json `
  --when 2026-05-05 `
  --no-banner
```

The `--when 2026-05-05` flag pins the deterministic seed so the example outputs reproduce exactly.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_post_ideas` (bound to `content_idea_generator.runner.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **Cost limits**: $0.20 per session, 50 API calls per session
- **PII handling**: `local-only`
- **Data retention**: 90 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\content-idea-generator\grok-agent.yaml
python safety\scanner.py scan       templates\creator\content-idea-generator\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it picks N archetypes from a per-tone pool, applies seeded sub-score nudges, computes the weighted Idea Plan score, detects the vanity-hook paradox, and emits the strict 6/7-section schema. A future v2 could optionally call Grok 4.3 to generate richer hook variations + per-idea why-it-works copy while preserving the same scoring, paradox detection, demo-vs-real labelling, and no-fabricated-engagement invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric weighted scoring with explicit healthy-range normalisation
2. The vanity-hook paradox detection (firing in both required places + auto-triggering the Idea Audit)
3. The 5-arrow trend bucketing with ±5% / ±25% thresholds
4. The demo-vs-real data-source labelling (creators can never confuse a demo for real ideation)
5. The deterministic seeded archetype selection + recommendation shuffle (reproducible reports)
6. The mandatory `analytics-summarizer` + `thread-builder` bridges on every render
7. The monetization-keyword refusal path (no financial content slips into the ideation loop)

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest | `grok-agent.yaml` | ✅ P12 starter (v2.15) |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P95 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built for X, Grok & the ecosystem community.
