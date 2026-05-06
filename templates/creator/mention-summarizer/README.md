<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🔔 Mention Summarizer

> Know what your mentions mean — before you decide what to say back. 4 official Mention Health metrics, sentiment-spike paradox detection, 3-band sentiment breakdown, priority reply queue (max 8) with troll-cluster guard, and mandatory bridges to reply-drafter and analytics-summarizer. Drafts only. Never auto-replies. Never fabricates mention statistics.
>
> *Built for X, Grok & the ecosystem community — every X creator deserves a mention layer that tells them when community sentiment is real and when it is coordinated noise.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator reads; the runner never auto-replies to any mention on X. Constitution Article II's auto-reply consent gate covers any future-version downstream action.

> 🔒 **No fabricated statistics.** The runner refuses to invent mention counts, sentiment scores, or troll-cluster membership it did not derive from the supplied input. When `--mentions-file` is not provided, every metric in the output is labelled `[demo mention — re-run with --mentions-file for real X data]` so seeded demo runs can never be mistaken for real mention data.

> 🔒 **Privacy-first.** No non-creator X handles appear in the rendered output. Mention intent is described in paraphrased terms only — never raw mention text or author handles. All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\mention-summarizer\`. The v1 runner makes zero external network calls.

> 🔒 **Troll-cluster guard active.** When ≥5 negative mentions share >60% pairwise token overlap, the runner detects the coordinated cluster, excludes all cluster members from the priority reply queue, and surfaces them as a single high-severity Red Flag. The cluster never silently inflates the negative sentiment band without a visible warning.

> 🔒 **Sentiment-spike paradox detection.** When Mention volume delta exceeds +30% AND Net sentiment score falls below 10, the runner surfaces the paradox in BOTH the Mention Health section AND the Red Flags section so the creator can never accidentally celebrate a volume spike that was actually a pile-on.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied X mention export (or seeded demo mentions) into the strict 7/8-section mention summary defined by the P89 system prompt — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Mention Snapshot** — one-sentence headline + 4-bullet metadata including the explicit data-source line
2. **Mention Health** — 4-row metric table with 5-arrow trend bucketing + weighted Mention Health score `round(0.30·Sentiment + 0.25·Volume + 0.25·Priority + 0.20·Authentic)`; sentiment-spike paradox surfaced here when triggered
3. **Sentiment Breakdown** — 3-band table (positive / neutral / negative) with counts + shares; cluster inflation flagged inline
4. **Priority Reply Queue** — up to 8 genuine mentions sorted by priority score (troll-cluster members excluded; each entry bridges to `reply-drafter`)
5. **Red Flags** — 2–4 cards with severity; always includes `Sentiment-spike paradox` when the rule fires and `Coordinated negative cluster` when a troll cluster is detected
6. **Recommendations** — 3–5 next moves; `reply-drafter` (position 1) and `analytics-summarizer` (position 2) are unconditional in every output
7. **Confidence**
8. **Mention Audit** *(optional, auto-appended)* — triggers when a troll cluster is detected OR `window = 7d`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\mention-summarizer\run.py --handle JanSol0s --demo
```

That prints the 8-section paradox-firing + troll-cluster demo report straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/mention-summarizer/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install mention-summarizer
```

### Option B — direct invocation (developer mode)

```powershell
# Real mention data (recommended — pass your X mention export as JSON)
python .\templates\creator\mention-summarizer\run.py `
  --handle JanSol0s `
  --mentions-file $env:LOCALAPPDATA\grok-agent\mention-summarizer\my-mentions.json `
  --days 30 `
  --compare-to previous_period

# Paradox + troll-cluster demo (official demo — fires both detectors)
python .\templates\creator\mention-summarizer\run.py --handle JanSol0s --demo

# Healthy community demo (positive-dominant, no paradox, no troll cluster)
python .\templates\creator\mention-summarizer\run.py --handle habitstacker --demo-healthy

# 7-day window demo (auto-triggers Mention Audit; near-paradox watch fires)
python .\templates\creator\mention-summarizer\run.py --handle JanSol0s --demo-7d --days 7

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\mention-summarizer\run.py `
  --handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\mention-summarizer\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--handle` | yes | Creator handle (with or without `@`) |
| `--mentions-file` | yes (or one of the `--demo-*` flags) | Path to a JSON mention export — see `examples/sample-1-input.json` for the schema |
| `--days` / `--window` | optional | `7` \| `30` \| `90` (default `30`; 7d auto-triggers Mention Audit) |
| `--compare-to` | optional | `previous_period` \| `benchmark` (default `previous_period`) |
| `--sentiment-baseline` | optional | Net sentiment threshold below which the paradox fires when volume also spikes (default `10`) |
| `--demo` | optional | Use the official paradox-firing + troll-cluster demo mentions |
| `--demo-healthy` | optional | Use healthy community demo (positive-dominant, no paradox, no troll cluster) |
| `--demo-7d` | optional | Use 7-day window demo mentions that auto-trigger Mention Audit |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## Mentions file schema (`--mentions-file`)

The runner accepts a JSON file shaped like the bundled examples. The contract:

```json
{
  "x_handle": "@<your-handle>",
  "window_days": 30,
  "compare_to": "previous_period",
  "data_source": "real",
  "current_period": {
    "total_mentions": <int>,
    "positive_count": <int>,
    "neutral_count": <int>,
    "negative_count": <int>,
    "authentic_mention_count": <int>
  },
  "previous_period": {
    "total_mentions": <int>,
    "positive_count": <int>,
    "neutral_count": <int>,
    "negative_count": <int>,
    "authentic_mention_count": <int>,
    "priority_mention_count": <int>
  },
  "mentions": [
    {
      "id": "<unique string>",
      "sentiment": "positive | neutral | negative",
      "intent": "<paraphrased description of mention intent — no raw text or author handles>",
      "priority_score": <int 0-100>,
      "author_followers": <int>,
      "tokens": ["<word1>", "<word2>", "..."]
    }
  ]
}
```

Key schema notes:
- `data_source`: set to `"real"` for actual X exports (or omit); set to `"demo"` to label all metrics as demo placeholders
- `mentions[]`: a representative subset of mentions used for priority queue and troll-cluster detection; does not need to include every mention in the period
- `tokens[]`: a list of meaningful words from the mention text (lowercase, stop-words stripped); used for Jaccard overlap detection in the troll-cluster guard
- `priority_score`: creator-assigned urgency 0–100; mentions with score ≥ 50 qualify for the priority queue
- `author_followers`: used to compute the `Authentic reach share` metric; the runner counts mentions where this value is provided (non-zero)
- `previous_period.priority_mention_count`: total priority mentions from the comparison period; used to compute the priority-rate trend arrow

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator reads; the runner never auto-replies anywhere.
2. **No fabricated statistics.** Demo mention counts are labelled explicitly. The runner never invents a troll cluster it didn't detect via the Jaccard algorithm.
3. **Sentiment-spike paradox** must surface in BOTH the Mention Health section AND the Red Flags section when Mention volume delta > +30% AND Net sentiment score < 10 (or the creator-supplied `--sentiment-baseline`).
4. **Mention Health score formula is fixed.** `round(0.30·Sentiment + 0.25·Volume + 0.25·Priority + 0.20·Authentic)`. Net sentiment weighted highest because volume driven entirely by negative mentions is worse than flat-volume; Authentic reach share weighted lowest because bot-floor variation is noisy in short windows.
5. **Troll-cluster guard is non-negotiable.** ≥5 negative mentions with pairwise Jaccard token overlap > 60% → excluded from priority queue + Red Flag card titled `Coordinated negative cluster` with severity `high`.
6. **Unconditional bridges.** Every output includes `reply-drafter` at position 1 and `analytics-summarizer` at position 2 in the Recommendations section. These are never shuffled out.

---

## Cross-template daily flow

Mention Summarizer sits between **what the community says** and **what the creator does next**. It feeds into the reply queue and the analytics layer simultaneously:

```
┌──────────────────────────────────────────────────────────────────┐
│  Daily — triage                                                   │
│  └─ mention-summarizer     → 7/8-section mention summary          │
│       │                                                           │
│       ├─ priority queue     → reply-drafter (draft 8 replies)     │
│       ├─ paradox flagged?   → analytics-summarizer (cross-check)  │
│       ├─ troll cluster?     → do NOT reply individually; monitor  │
│       └─ healthy sentiment? → content-idea-generator (re-source)  │
│                                                                   │
│  Weekly — measure                                                 │
│  └─ analytics-summarizer   → confirm mention trend vs engagement  │
│  └─ follower-quality-analyzer → vet new cohort if volume spiked   │
│                                                                   │
│  Monthly                                                          │
│  └─ competitor-watch       → compare sentiment vs niche peers     │
│  └─ brand-voice-trainer    → audit tone if negative trend grows   │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\mention-summarizer\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\mention-summarizer\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\mention-summarizer\logs\` |
| System prompt | `templates\creator\mention-summarizer\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Sentiment-spike paradox + troll cluster (8-section report) | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | Healthy community growth (7-section report, no paradox) | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | 7-day window (8-section report, Mention Audit auto-triggered) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete, runnable mention file; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py --handle <handle> --mentions-file .\examples\sample-N-input.json --days <N> --no-banner
```

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_mention_summary` (bound to `mention_summarizer.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **7 Constitution rules** specialising Articles I, II, III, VII for mention-triage work
- **5 hard refusals**: auto-reply without consent gate; expose non-creator handles; fabricate cluster statistics; recommend mass-blocking or pile-on engagement; scrape authenticated X content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\mention-summarizer\grok-agent.yaml
python safety\scanner.py scan  templates\creator\mention-summarizer\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it computes all metrics directly from the supplied JSON, applies the Jaccard troll-cluster algorithm, builds the priority queue, and emits the strict 7/8-section schema. A future v2 could optionally call Grok 4.3 to generate richer paraphrased interpretations of each mention cluster while preserving the same scoring, paradox detection, troll-cluster guard, and no-fabricated-statistics invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric weighted Mention Health scoring with explicit healthy-range normalisation
2. The sentiment-spike paradox detection (firing in both required places)
3. The troll-cluster guard (Jaccard algorithm, ≥5 members, >60% overlap → Red Flag + queue exclusion)
4. The demo-vs-real mention-data labelling (creators can never confuse a demo for real data)
5. The deterministic seeded recommendation shuffle (reproducible reports; no date in seed)
6. The Mention Audit auto-trigger on 7d windows or troll-cluster detection

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P89 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P90 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built for X, Grok & the ecosystem community.
