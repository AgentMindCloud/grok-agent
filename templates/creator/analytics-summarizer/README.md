<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 📊 Analytics Summarizer

> Read your X analytics honestly: 4 canonical Period Performance metrics, vanity-metric paradox detection, 5-arrow trend bucketing, and ≥3 cross-template bridges that turn the numbers into next moves. Drafts only. Never auto-publishes. Never fabricates statistics.
>
> *Built for X, Grok & the ecosystem community — every X creator deserves an analytics layer that tells them when reach is real and when it's vanity.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator reads; the runner never auto-publishes the summary anywhere. Constitution Article II's `publish_to_x` consent gate covers any future-version downstream sharing.

> 🔒 **No fabricated statistics.** The runner refuses to invent p-values, confidence intervals, or absolute lift numbers it didn't derive from supplied input. When `--metrics-file` is not provided, every metric in the output is labelled `[demo metric — re-run with --metrics-file for real X data]` so seeded demo runs can never be mistaken for real analytics.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\analytics-summarizer\`. The v1 runner makes zero external network calls — it is offline-safe and runs cleanly without any X API token.

> 🔒 **Vanity-metric paradox detection.** When Impressions delta is above +20% AND Engagement rate is below the 2.5% niche baseline, the runner surfaces the paradox in BOTH the Period Performance section AND the Red Flags section so the creator can never accidentally celebrate a viral spike that didn't bring their people.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation derived from the analytics that touches monetization tactics, paid-tier funnels, or sponsorship pricing.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied X analytics export (or seeded demo metrics) into the strict 7/8-section period summary defined by the merged P83 system prompt — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Period Snapshot** — one-sentence headline + 5-bullet metadata including the explicit data-source line
2. **Period Performance** — 4-row metric table (Impressions delta / Engagement rate / Follower delta / Content velocity) + weighted Period Performance score `round(0.30·Engagement + 0.30·Impressions + 0.25·Follower + 0.15·Velocity)`
3. **Top-Performing Content** — 3-5 paraphrased archetypes (no raw URLs unless explicitly supplied)
4. **Trends** — rising / stable / falling buckets across the 5-arrow vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼)
5. **Red Flags** — 2-4 cards with severity, surfaces the **vanity-metric paradox** in BOTH this section AND the Period Performance row when triggered
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges
7. **Confidence**
8. **Period Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR `time_range = 7d`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\analytics-summarizer\run.py --x-handle JanSol0s --demo
```

That prints the 7-section paradox-firing demo report (Impressions delta +34.5%, Engagement rate 1.78% — below the 2.5% niche baseline) straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/analytics-summarizer/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install analytics-summarizer
```

### Option B — direct invocation (developer mode)

```powershell
# Real metrics (recommended — pass your X analytics export as JSON)
python .\templates\creator\analytics-summarizer\run.py `
  --x-handle JanSol0s `
  --metrics-file $env:LOCALAPPDATA\grok-agent\analytics-summarizer\my-export.json `
  --time-range 30d `
  --compare-to previous_period `
  --metric-focus all

# Paradox demo (vanity-metric firing)
python .\templates\creator\analytics-summarizer\run.py --x-handle JanSol0s --demo

# Healthy demo (no paradox; all metrics rising)
python .\templates\creator\analytics-summarizer\run.py --x-handle habitstacker --demo-healthy

# 7-day window demo (auto-triggers Period Audit)
python .\templates\creator\analytics-summarizer\run.py --x-handle JanSol0s --demo-7d-audit --time-range 7d --metric-focus engagement

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\analytics-summarizer\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\analytics-summarizer\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--metrics-file` | yes (or one of the `--demo-*` flags) | Path to a JSON metrics export — see `examples/sample-1-input.json` for the schema |
| `--metric-focus` | optional | `impressions` \| `engagement` \| `reach` \| `all` (default `all`) |
| `--time-range` | optional | `7d` \| `30d` \| `90d` (default `30d`; 7d auto-triggers Period Audit) |
| `--compare-to` | optional | `previous_period` \| `benchmark` (default `previous_period`) |
| `--engagement-baseline` | optional | Niche-baseline engagement rate in % (default `2.5`) |
| `--demo` | optional | Use the canonical paradox-firing demo metrics |
| `--demo-healthy` | optional | Use healthy-growth demo metrics (no paradox) |
| `--demo-7d-audit` | optional | Use 7d-window demo metrics that auto-trigger Period Audit |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## Metrics file schema (`--metrics-file`)

The runner accepts a JSON file shaped like the bundled examples (`examples/sample-1-input.json`, `sample-2-input.json`, `sample-3-input.json`). The contract:

```json
{
  "x_handle": "@<your-handle>",
  "time_range": "30d",
  "compare_to": "previous_period",
  "metric_focus": "all",
  "data_source": "real",
  "current_period": {
    "impressions": <int>,
    "engagements": <int>,
    "follower_delta_pct": <float, percent>,
    "posts_per_week": <float>
  },
  "previous_period": {
    "impressions": <int>,
    "engagements": <int>,
    "follower_delta_pct": <float, percent>,
    "posts_per_week": <float>
  },
  "top_content": [
    {
      "archetype_label": "<paraphrased category, NOT a raw post URL>",
      "format": "thread | single-post | quote-tweet | reply | live | carousel",
      "impression_share_pct": <float, percent of period impressions>,
      "engagement_rate_pct": <float, percent>
    }
  ]
}
```

If `data_source` is `"demo"` the runner labels every metric as a demo placeholder. Set it to `"real"` (or omit it) when supplying actual X analytics so the report's Period Snapshot says `real X export from --metrics-file`.

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator reads; the runner never publishes anywhere.
2. **No fabricated statistics.** Sample-size, duration, and significance estimates are heuristics named as such. Demo metrics labelled explicitly. The runner refuses to invent p-values.
3. **Vanity-metric paradox** must surface in BOTH the Period Performance section AND the Red Flags section when Impressions delta > +20% AND Engagement rate < 2.5% (or the niche baseline supplied via `--engagement-baseline`).
4. **Period Performance score formula is fixed.** `round(0.30·Engagement + 0.30·Impressions + 0.25·Follower + 0.15·Velocity)`. Engagement and Impressions tied at 0.30 each because either failing alone defeats the period; Content velocity weighted lowest because cadence is the most-gameable signal.
5. **5-arrow trend bucketing** (▲▲ / ▲ / ▬ / ▼ / ▼▼) with thresholds at ±5% / ±25% vs the comparison basis. Follower delta uses tighter ±0.5% / ±1% / ±5% bands because creator follower deltas are typically small in absolute %.
6. **Top-Performing Content archetypes are paraphrased.** Format / cluster descriptors only. Never raw URLs unless the creator explicitly supplies them in the metrics file.

---

## Cross-template daily flow

Analytics Summarizer is the **measurement layer** of the Grok Agent OS creator suite — every other template recommends it as a destination bridge. Reciprocally, this template's recommendations point creators back into the suite to act on the numbers:

```
┌──────────────────────────────────────────────────────────────────┐
│  Weekly — measure                                                 │
│  └─ analytics-summarizer    → 7/8-section period summary          │
│       │                                                           │
│       ├─ paradox flagged?   → follower-quality-analyzer to vet    │
│       ├─ 7d window?         → wait 14 more days, re-run with 30d  │
│       └─ healthy period?    → re-source via content-idea-generator│
│                                                                   │
│  Per-anchor — act                                                 │
│  └─ thread-builder          → build the long-form that earns the  │
│                                audience the period attracted      │
│  └─ reply-drafter           → engage with the audience the period │
│                                brought in                         │
│  └─ ab-test-suggester       → promote the winning archetype to A/B│
│                                                                   │
│  Quarterly                                                        │
│  └─ competitor-watch        → compare your metric mix vs peers    │
│  └─ monetization-optimizer  → model the funnel from the analytics │
│                                                                   │
│  Monthly                                                          │
│  └─ analytics-summarizer    → re-snapshot to build a real baseline│
│                                of trend arrows                    │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\analytics-summarizer\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\analytics-summarizer\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\analytics-summarizer\logs\` |
| System prompt | `templates\creator\analytics-summarizer\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Vanity-metric paradox firing | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | Healthy growth (no paradox) | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | 7-day window (Period Audit auto-triggered) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete, runnable metrics file; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py --x-handle <handle> --metrics-file .\examples\sample-N-input.json --no-banner
```

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_analytics_summary` (bound to `analytics_summarizer.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **7 Constitution rules** specialising Articles I, II, III, V, VII for analytics work
- **5 hard refusals**: auto-publish without consent gate; fabricate p-values / confidence intervals; recommend algorithm-gaming tactics; expose other creators' analytics; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\analytics-summarizer\grok-agent.yaml
python safety\scanner.py scan  templates\creator\analytics-summarizer\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it computes metrics directly from the supplied JSON, applies the weighted formula, buckets trends with the 5-arrow vocabulary, and emits the strict 7/8-section schema. A future v2 could optionally call Grok 4.3 to generate richer interpretations of each metric row while preserving the same scoring, paradox detection, demo-vs-real labelling, and no-fabricated-statistics invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric weighted scoring with explicit healthy-range normalisation
2. The vanity-metric paradox detection (firing in both required places)
3. The 5-arrow trend bucketing with ±5% / ±25% thresholds
4. The demo-vs-real data-source labelling (creators can never confuse a demo for real data)
5. The deterministic seeded recommendation shuffle (reproducible reports)
6. The Period Audit auto-trigger on 7d windows or red-flag overflow

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P83 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P84 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built for X, Grok & the ecosystem community.
