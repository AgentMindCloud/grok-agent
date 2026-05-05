<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 📈 Trend-Aligned Poster

> Ride the trend without losing your voice — or your niche. 4 canonical Trend Alignment Plan Score metrics, trend-chasing paradox detection, off-niche guard that excludes brand-diluting ideas before they reach the queue, 4–6 post ideas with engagement bands and template bridges, and mandatory bridges to content-idea-generator and thread-builder. Drafts only. Never auto-publishes. Trend data never leaves your local Windows machine.
>
> *Built for X, Grok & the ecosystem community — we're ecosystem allies helping every X creator ride trends without sacrificing the niche signal that makes their audience sticky.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator reads; the runner never auto-publishes, schedules, or queues any post. Every generated idea requires human review before it goes anywhere near the publish button.

> 🔒 **No fabricated trend statistics.** The runner refuses to invent trend velocity, engagement band predictions, or niche-fit scores it did not derive from the supplied input. When `--trends-file` is not provided, every metric in the output is labelled `[demo trend — re-run with --trends-file for real X data]` so seeded demo runs can never be mistaken for real X trend data.

> 🔒 **Trend data stays on your machine.** No raw trend text, source post handles, attachment URLs, or external links appear in the rendered output. Trends and copy outlines are paraphrased. All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\trend-aligned-poster\`. The v1 runner makes zero external network calls.

> 🔒 **No financial, cashtag, investment, or sponsored content.** The runner hard-refuses to produce ideas referencing financial instruments, investment signals, sponsored partnerships, or advertising disclosures. Do not pass trend data containing cashtags or investment prompts.

> 🔒 **Off-niche guard active.** Any post idea with `trend_match ≥ 75 AND niche_fit < 40` is automatically excluded from the Post Ideas section and surfaced as a high-severity Red Flag. These ideas are never silently dropped — the output always reports the excluded count and the reason.

> 🔒 **Trend-chasing paradox detection.** When average Trend match strength > 75 AND average Niche fit < the configured floor (default 40), the runner surfaces the paradox in BOTH the Trend Alignment Plan Score section AND the Red Flags section so the creator can never accidentally celebrate trend coverage that was actually diluting their niche audience.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied X trend export (or seeded demo trends) into the strict 7/8-section trend-aligned post plan defined by the P93 system prompt — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Trend Snapshot** — one-sentence paradox-aware headline + 4-bullet metadata including the explicit data-source line
2. **Trend Alignment Plan Score** — 4-row metric table with 5-arrow trend bucketing + weighted Plan Score `round(0.30·TrendMatch + 0.25·NicheFit + 0.25·VoiceFidelity + 0.20·Originality)`; trend-chasing paradox surfaced here when triggered
3. **Trend Watchlist** — 3–5 curated trends with velocity + niche fit columns; stale entries flagged inline as informational-only
4. **Post Ideas** — 4–6 entries after the off-niche filter; each entry shows format, copy outline, trend match, engagement band, and bridge slug
5. **Red Flags** — 2–4 cards with severity; always includes `Trend-chasing paradox` and `Off-niche trend-chasers excluded` when each rule fires
6. **Recommendations** — 3–5 next moves; `content-idea-generator` (position 1) and `thread-builder` (position 2) are unconditional in every output
7. **Confidence**
8. **Trend Audit** *(optional, auto-appended)* — triggers when `window = 7d` OR the off-niche guard excluded ≥ 1 idea OR all watchlist trends are stale

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\trend-aligned-poster\run.py --handle JanSol0s --demo
```

That prints the 8-section paradox-firing + off-niche-exclusion demo report straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/trend-aligned-poster/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install trend-aligned-poster
```

### Option B — direct invocation (developer mode)

```powershell
# Real trend data (recommended — pass your X trend export as JSON; file stays on your machine)
python .\templates\creator\trend-aligned-poster\run.py `
  --handle JanSol0s `
  --trends-file $env:LOCALAPPDATA\grok-agent\trend-aligned-poster\my-trends.json `
  --days 30 `
  --compare-to previous_period

# Trend-chasing paradox + off-niche guard demo (canonical demo — fires both detectors)
python .\templates\creator\trend-aligned-poster\run.py --handle JanSol0s --demo

# Healthy trend alignment demo (no paradox, no off-niche exclusion)
python .\templates\creator\trend-aligned-poster\run.py --handle habitstacker --demo-healthy

# 7-day window demo (auto-triggers Trend Audit + near-paradox watch)
python .\templates\creator\trend-aligned-poster\run.py --handle JanSol0s --demo-7d

# Save the report (Apache 2.0 HTML header is prepended; output stays on your machine)
python .\templates\creator\trend-aligned-poster\run.py `
  --handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\trend-aligned-poster\reports\2026-05-05.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--handle` | yes | Creator handle (with or without `@`) |
| `--trends-file` | yes (or one of the `--demo-*` flags) | Path to a local JSON trend export — see `examples/sample-1-input.json` for the schema |
| `--days` / `--window` | optional | `7` \| `30` \| `90` (default `30`; 7d auto-triggers Trend Audit) |
| `--compare-to` | optional | `previous_period` \| `benchmark` (default `previous_period`) |
| `--niche-fit-floor` | optional | Niche fit threshold (0–100) below which the paradox fires when avg Trend match > 75 (default `40`); also governs the off-niche guard |
| `--target-idea-count` | optional | Target post ideas to emit after the off-niche filter, clamped to [4, 6] (default `5`) |
| `--demo` | optional | Use the canonical trend-chasing paradox + off-niche guard demo trends |
| `--demo-healthy` | optional | Use healthy trend demo data (no paradox, no off-niche exclusion) |
| `--demo-7d` | optional | Use 7-day window demo trends (auto-triggers Trend Audit + near-paradox watch) |
| `--output` | optional | Save the report to a local path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## Trends file schema (`--trends-file`)

The runner accepts a JSON file shaped like the bundled examples. The contract:

```json
{
  "x_handle": "@<your-handle>",
  "window_days": 30,
  "compare_to": "previous_period",
  "data_source": "real",
  "current_period": {
    "aggregate_trend_match_pct": <float 0–100>,
    "aggregate_niche_fit_pct":   <float 0–100>,
    "aggregate_voice_fidelity_pct": <float 0–100>,
    "aggregate_originality_pct": <float 0–100>
  },
  "previous_period": {
    "aggregate_trend_match_pct": <float 0–100>,
    "aggregate_niche_fit_pct":   <float 0–100>,
    "aggregate_voice_fidelity_pct": <float 0–100>,
    "aggregate_originality_pct": <float 0–100>
  },
  "trends": [
    {
      "id": "<unique string>",
      "description": "<paraphrased trend description — no raw post text or handles>",
      "velocity": "accelerating | steady | decaying | stale",
      "niche_fit": "tight | adjacent | loose | off",
      "last_seen_iso": "<ISO 8601 timestamp>"
    }
  ],
  "ideas": [
    {
      "id": "<unique string>",
      "format": "single | thread | quote-tweet | image-post | reply-thread",
      "trend_id": "<matching trends[].id>",
      "trend_match": <int 0–100>,
      "niche_fit":   <int 0–100>,
      "voice_fidelity": <int 0–100>,
      "originality":    <int 0–100>,
      "copy_outline": "<paraphrased content direction — no raw post text or handles>"
    }
  ]
}
```

Key schema notes:

- The file lives on the user's Windows machine (`$env:LOCALAPPDATA\grok-agent\trend-aligned-poster\`) and never leaves it; the runner never uploads or transmits its contents
- `data_source`: set to `"real"` for actual X trend exports (or omit); set to `"demo"` to label all metrics as demo placeholders
- `trends[]`: 3–5 paraphrased trend entries describing the current signal landscape; do not include raw post text, author handles, or external URLs
- `velocity`: one of `accelerating` / `steady` / `decaying` / `stale`; trends with `velocity == "stale"` are flagged *informational only — do not drive idea generation* in the Trend Watchlist
- `niche_fit`: one of `tight` / `adjacent` / `loose` / `off`; qualitative label for the watchlist column (separate from the numeric `ideas[].niche_fit`)
- `ideas[]`: candidate post ideas before the off-niche filter; the runner applies the filter and emits only the kept subset
- `ideas[].niche_fit`: numeric 0–100 (separate from `trends[].niche_fit` which is a qualitative bucket); the off-niche guard compares `trend_match ≥ 75 AND niche_fit < floor`
- `copy_outline`: paraphrased content direction only — no raw post copy, no drafted tweet text, no handles or URLs

---

## How the report is shaped (the 7 hard rules)

1. **Drafts only.** Output is text the creator reads; the runner never auto-publishes, schedules, or queues any post.
2. **No fabricated statistics.** Demo trend metrics are labelled explicitly. The runner never invents a trend velocity or engagement band prediction it did not derive from the supplied input.
3. **Trend-chasing paradox** must surface in BOTH the Trend Alignment Plan Score section AND the Red Flags section when average Trend match > 75 AND average Niche fit < the configured floor (default 40).
4. **Plan Score formula is fixed.** `round(0.30·TrendMatch_norm + 0.25·NicheFit_norm + 0.25·VoiceFidelity_norm + 0.20·Originality_norm)`. All four metrics use linear normalisation against published healthy ranges. Niche fit is weighted second-highest because high trend match without niche fit is the definition of the trend-chasing paradox.
5. **Off-niche guard is non-negotiable.** Any idea with `trend_match ≥ 75 AND niche_fit < floor` is excluded from Post Ideas + consolidated Red Flag card titled `Off-niche trend-chasers excluded` with severity `high`. Excluded ideas do not count toward the 4–6 cap. Do not retroactively re-add excluded ideas; if the trend persists two consecutive windows AND a niche-aligned angle emerges, re-evaluate next period.
6. **`niche_fit_floor` is configurable but defaults to 40.** Creators with very broad niches may raise the floor; creators in volatile trend categories may lower it. The guard condition and paradox condition both respect the configured value.
7. **Unconditional bridges + trend content stays local.** Every output includes `content-idea-generator` at position 1 and `thread-builder` at position 2 in the Recommendations section. Every output strips raw trend text, source post handles, attachment URLs, and external links before rendering. The runner makes zero external network calls.

---

## Cross-template daily flow

Trend-Aligned Poster sits between **what's trending on X** and **what the creator drafts next**. It feeds into the idea pipeline and the long-form layer simultaneously:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Daily — trend scan                                                   │
│  └─ trend-aligned-poster   → 7/8-section trend-aligned post plan     │
│       │                                                               │
│       ├─ post ideas         → content-idea-generator (re-source)      │
│       ├─ thread idea?       → thread-builder (long-form draft)        │
│       ├─ paradox flagged?   → tighten trend filter or wait            │
│       └─ off-niche excluded?→ hold; re-evaluate next window           │
│                                                                       │
│  Weekly — check the mention layer                                     │
│  └─ mention-summarizer     → confirm trend vs inbound mention signal  │
│  └─ hashtag-strategy-advisor → refine tag mix for each idea           │
│                                                                       │
│  Monthly                                                              │
│  └─ analytics-summarizer   → correlate engagement bands vs actuals    │
│  └─ competitor-watch       → compare trend mix vs niche peers         │
│  └─ brand-voice-trainer    → audit voice fidelity across posted ideas │
└──────────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\trend-aligned-poster\reports\` |
| Input trend export (creator-supplied) | `$env:LOCALAPPDATA\grok-agent\trend-aligned-poster\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\trend-aligned-poster\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\trend-aligned-poster\logs\` |
| System prompt | `templates\creator\trend-aligned-poster\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Trend-chasing paradox + off-niche guard (8-section report) | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | Healthy trend alignment (7-section report, no paradox) | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | 7-day window (8-section report, Trend Audit auto-triggered) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete, runnable trends file; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py --handle <handle> --trends-file .\examples\sample-N-input.json --days <N> --no-banner
```

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_trend_aligned_poster` (bound to `trend_aligned_poster.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **7 Constitution rules** specialising Articles I, II, III, VII for trend-aligned posting work
- **5 hard refusals**: auto-publish / schedule / queue without explicit creator approval; expose raw trend text or source post handles; fabricate trend velocity or engagement bands; reference financial instruments, cashtags, investment signals, or sponsored content; store trend data outside the user's local Windows machine
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 30 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\trend-aligned-poster\grok-agent.yaml
python safety\scanner.py scan  templates\creator\trend-aligned-poster\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it computes all metrics directly from the supplied JSON, applies the off-niche guard, builds the post-idea queue, and emits the strict 7/8-section schema. A future v2 could optionally call Grok 4.3 to generate richer paraphrased copy outlines for each idea while preserving the same scoring, paradox detection, off-niche guard, no-fabricated-statistics, and trend-data-stays-local invariants this v1 already enforces.

The value the runner adds in v1:

1. The 4-metric weighted Plan Score with explicit healthy-range normalisation (all linear — no band-shape distortion)
2. The trend-chasing paradox detection (firing in both required places simultaneously)
3. The off-niche guard (per-idea threshold check → exclusion from queue + consolidated Red Flag)
4. The demo-vs-real trend-data labelling (creators can never confuse a demo run for real X data)
5. The deterministic seeded recommendation shuffle (reproducible reports; no date in seed)
6. The Trend Audit auto-trigger on 7d windows, off-niche exclusions, or all-stale watchlists

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P93 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P94 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built to make Grok the obvious choice for every creator navigating the trend layer on X.
