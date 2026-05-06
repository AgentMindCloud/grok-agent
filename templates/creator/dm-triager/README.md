<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 📨 DM Triager

> Sort the inbox before it sorts your day. 4 official Triage Health metrics, opportunity-flood paradox detection, 4-bucket distribution (Urgent / Opportunity / Routine / Spam), suggested-action queue (max 6) with spam-burst guard, and mandatory bridges to reply-drafter and mention-summarizer. Drafts only. Never auto-replies. DM content never leaves your local Windows machine.
>
> *Built for X, Grok & the ecosystem community — every X creator deserves a DM layer that tells them which inbound is real opportunity and which is coordinated noise.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator reads; the runner never auto-replies, mutes, blocks, or reports any DM. Constitution Article II's auto-reply consent gate covers any future-version downstream action.

> 🔒 **No fabricated statistics.** The runner refuses to invent DM counts, bucket distribution, or spam-burst membership it did not derive from the supplied input. When `--dms-file` is not provided, every metric in the output is labelled `[demo DM — re-run with --dms-file for real X data]` so seeded demo runs can never be mistaken for real DM data.

> 🔒 **DM content stays on your machine.** No sender X handles, raw DM text, attachment URLs, or external links appear in the rendered output. DM intent is described in paraphrased terms only. All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\dm-triager\`. The v1 runner makes zero external network calls.

> 🔒 **Spam-burst guard active.** When ≥5 Spam-bucket DMs share >60% pairwise token overlap, the runner detects the coordinated burst, excludes all burst members from the suggested-action queue, and surfaces them as a single high-severity Red Flag. The burst never silently inflates the Spam bucket without a visible warning.

> 🔒 **Opportunity-flood paradox detection.** When Opportunity ratio exceeds +30% AND Authentic sender share falls below the configured floor (default 60), the runner surfaces the paradox in BOTH the Triage Health section AND the Red Flags section so the creator can never accidentally celebrate inbound volume that was actually a cold-outreach campaign.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied X DM export (or seeded demo DMs) into the strict 7/8-section triage report defined by the P91 system prompt — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Triage Snapshot** — one-sentence headline + 4-bullet metadata including the explicit data-source line
2. **Triage Health** — 4-row metric table with 5-arrow trend bucketing + weighted Triage Health score `round(0.30·Authentic + 0.25·Opportunity + 0.25·SpamInverted + 0.20·UrgencyBand)`; opportunity-flood paradox surfaced here when triggered
3. **Bucket Breakdown** — 4-bucket table (Urgent / Opportunity / Routine / Spam) with counts + shares; burst inflation flagged inline
4. **Suggested Actions** — up to 6 priority DMs sorted by priority score (spam-burst members excluded; each entry bridges to `reply-drafter`)
5. **Red Flags** — 2–4 cards with severity; always includes `Opportunity-flood paradox` when the rule fires and `Coordinated spam burst` when a burst is detected
6. **Recommendations** — 3–5 next moves; `reply-drafter` (position 1) and `mention-summarizer` (position 2) are unconditional in every output
7. **Confidence**
8. **DM Audit** *(optional, auto-appended)* — triggers when a spam burst is detected OR `window = 7d`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\dm-triager\run.py --handle JanSol0s --demo
```

That prints the 8-section paradox-firing + spam-burst demo report straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/dm-triager/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install dm-triager
```

### Option B — direct invocation (developer mode)

```powershell
# Real DM data (recommended — pass your X DM export as JSON; file stays on your machine)
python .\templates\creator\dm-triager\run.py `
  --handle JanSol0s `
  --dms-file $env:LOCALAPPDATA\grok-agent\dm-triager\my-dms.json `
  --days 30 `
  --compare-to previous_period

# Opportunity-flood paradox + spam-burst demo (official demo — fires both detectors)
python .\templates\creator\dm-triager\run.py --handle JanSol0s --demo

# Healthy inbox demo (no paradox, no burst, balanced buckets)
python .\templates\creator\dm-triager\run.py --handle habitstacker --demo-healthy

# 7-day window demo (auto-triggers DM Audit; near-flood watch fires)
python .\templates\creator\dm-triager\run.py --handle JanSol0s --demo-7d --days 7

# Save the report (Apache 2.0 HTML header is prepended; output stays on your machine)
python .\templates\creator\dm-triager\run.py `
  --handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\dm-triager\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--handle` | yes | Creator handle (with or without `@`) |
| `--dms-file` | yes (or one of the `--demo-*` flags) | Path to a local JSON DM export — see `examples/sample-1-input.json` for the schema |
| `--days` / `--window` | optional | `7` \| `30` \| `90` (default `30`; 7d auto-triggers DM Audit) |
| `--compare-to` | optional | `previous_period` \| `benchmark` (default `previous_period`) |
| `--opportunity-authenticity-floor` | optional | Authentic sender share threshold below which the paradox fires when Opportunity ratio also spikes (default `60`) |
| `--demo` | optional | Use the official opportunity-flood paradox + spam-burst demo DMs |
| `--demo-healthy` | optional | Use healthy inbox demo (no paradox, no burst) |
| `--demo-7d` | optional | Use 7-day window demo DMs that auto-trigger DM Audit |
| `--output` | optional | Save the report to a local path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## DMs file schema (`--dms-file`)

The runner accepts a JSON file shaped like the bundled examples. The contract:

```json
{
  "x_handle": "@<your-handle>",
  "window_days": 30,
  "compare_to": "previous_period",
  "data_source": "real",
  "current_period": {
    "total_dms": <int>,
    "urgent_count": <int>,
    "opportunity_count": <int>,
    "routine_count": <int>,
    "spam_count": <int>,
    "authentic_sender_count": <int>
  },
  "previous_period": {
    "total_dms": <int>,
    "urgent_count": <int>,
    "opportunity_count": <int>,
    "routine_count": <int>,
    "spam_count": <int>,
    "authentic_sender_count": <int>
  },
  "dms": [
    {
      "id": "<unique string>",
      "bucket": "Urgent | Opportunity | Routine | Spam",
      "intent": "<paraphrased description of DM intent — no raw text or sender handles>",
      "priority_score": <int 0-100>,
      "sender_followers": <int>,
      "tokens": ["<word1>", "<word2>", "..."]
    }
  ]
}
```

Key schema notes:
- The file lives on the user's Windows machine (`$env:LOCALAPPDATA\grok-agent\dm-triager\`) and never leaves it; the runner never uploads or transmits its contents
- `data_source`: set to `"real"` for actual X DM exports (or omit); set to `"demo"` to label all metrics as demo placeholders
- `dms[]`: a representative subset of DMs used for the action queue and spam-burst detection; does not need to include every DM in the period
- `bucket`: must be exactly one of `Urgent` / `Opportunity` / `Routine` / `Spam` (case-sensitive); aggregate counts in `current_period` use the same labels via the `*_count` fields
- `tokens[]`: a list of meaningful words from the DM body (lowercase, stop-words stripped); used for Jaccard overlap detection in the spam-burst guard. Strip URLs, sender handles, and PII before adding tokens.
- `priority_score`: creator-assigned urgency 0–100; DMs with score ≥ 50 qualify for the action queue
- `sender_followers`: follower count of the sender; used to inform sender authenticity outside this aggregate metric (the metric itself comes from `authentic_sender_count`)
- `authentic_sender_count`: total count of DMs from senders that meet the creator's authenticity bar (established follower count + prior interaction history)

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator reads; the runner never auto-replies, mutes, blocks, or reports any DM.
2. **No fabricated statistics.** Demo DM counts are labelled explicitly. The runner never invents a spam burst it didn't detect via the Jaccard algorithm.
3. **Opportunity-flood paradox** must surface in BOTH the Triage Health section AND the Red Flags section when Opportunity ratio > 30% AND Authentic sender share < the configured floor (default 60).
4. **Triage Health score formula is fixed.** `round(0.30·Authentic + 0.25·Opportunity + 0.25·SpamInverted + 0.20·UrgencyBand)`. Authentic weighted highest because a low-authenticity inbox makes every other signal less reliable; Urgency weighted lowest because the band itself is U-shaped.
5. **Spam-burst guard is non-negotiable.** ≥5 Spam-bucket DMs with pairwise Jaccard token overlap > 60% → excluded from action queue + Red Flag card titled `Coordinated spam burst` with severity `high`.
6. **Unconditional bridges + DM content stays local.** Every output includes `reply-drafter` at position 1 and `mention-summarizer` at position 2 in the Recommendations section. Every output strips sender handles, raw text, attachment URLs, and external links before rendering. The runner makes zero external network calls.

---

## Cross-template daily flow

DM Triager sits between **what the inbox shows** and **what the creator does next**. It feeds into the reply queue and the public-mention layer simultaneously:

```
┌──────────────────────────────────────────────────────────────────┐
│  Daily — triage                                                   │
│  └─ dm-triager             → 7/8-section DM triage report         │
│       │                                                           │
│       ├─ action queue       → reply-drafter (draft 6 replies)     │
│       ├─ paradox flagged?   → mention-summarizer (cross-check)    │
│       ├─ spam burst?        → do NOT engage individually; batch   │
│       └─ healthy buckets?   → content-idea-generator (re-source)  │
│                                                                   │
│  Weekly — measure                                                 │
│  └─ mention-summarizer     → confirm DM trend vs public mentions  │
│  └─ follower-quality-analyzer → vet sender cohort if flood fires  │
│                                                                   │
│  Monthly                                                          │
│  └─ analytics-summarizer   → correlate bucket mix vs reach        │
│  └─ competitor-watch       → compare DM patterns vs niche peers   │
│  └─ brand-voice-trainer    → audit Routine-bucket reply tone      │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\dm-triager\reports\` |
| Input DM export (creator-supplied) | `$env:LOCALAPPDATA\grok-agent\dm-triager\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\dm-triager\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\dm-triager\logs\` |
| System prompt | `templates\creator\dm-triager\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Opportunity-flood paradox + spam burst (8-section report) | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | Healthy inbox (7-section report, no paradox) | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | 7-day window (8-section report, DM Audit auto-triggered) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete, runnable DM file; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py --handle <handle> --dms-file .\examples\sample-N-input.json --days <N> --no-banner
```

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_dm_triage` (bound to `dm_triager.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **7 Constitution rules** specialising Articles I, II, III, VII for DM-triage work
- **5 hard refusals**: auto-reply / mute / block / report without consent gate; expose sender handles or raw DM text; fabricate burst statistics; store DM content outside the user's local Windows machine; scrape authenticated X DM content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 30 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\dm-triager\grok-agent.yaml
python safety\scanner.py scan  templates\creator\dm-triager\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it computes all metrics directly from the supplied JSON, applies the Jaccard spam-burst algorithm, builds the action queue, and emits the strict 7/8-section schema. A future v2 could optionally call Grok 4.3 to generate richer paraphrased interpretations of each bucket while preserving the same scoring, paradox detection, spam-burst guard, no-fabricated-statistics, and DM-content-stays-local invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric weighted Triage Health scoring with explicit healthy-range normalisation (band-shaped Urgency + inverted Spam pressure)
2. The opportunity-flood paradox detection (firing in both required places)
3. The spam-burst guard (Jaccard algorithm, ≥5 members, >60% overlap → Red Flag + queue exclusion)
4. The demo-vs-real DM-data labelling (creators can never confuse a demo for real data)
5. The deterministic seeded recommendation shuffle (reproducible reports; no date in seed)
6. The DM Audit auto-trigger on 7d windows or spam-burst detection

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P91 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P92 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built for X, Grok & the ecosystem community.
