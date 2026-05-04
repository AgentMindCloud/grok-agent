<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 💸 Monetization Optimizer

> Plan your X creator runway honestly: 4 canonical Monetization Plan Score metrics, single-channel-dependence paradox detection, wide-band earnings forecasts (never point estimates), paraphrased sponsorship archetypes, tax & expense reserve notes, and ≥3 cross-template bridges that turn the plan into next moves. Drafts only. Never auto-publishes. Never gives financial or tax advice.
>
> *Built for X, Grok & the ecosystem community — every X creator deserves a monetization layer that catches the concentration cliff before it catches them.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator reads, edits, and acts on themselves; the runner never auto-publishes, auto-pitches a sponsor, or auto-files a tax return. Constitution Article II's `publish_to_x` consent gate covers any future-version downstream sharing.

> 🔒 **No fabricated dollar amounts.** The runner refuses to invent absolute revenue projections it didn't derive from supplied input. Forecasts are reported as **wide bands**, never point estimates. When `--revenue-file` is not provided, every signal in the output is labelled `[demo signal — re-run with --revenue-file for real-ledger forecast]` so seeded demo runs can never be mistaken for real planning data.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\monetization-optimizer\`. The v1 runner makes zero external network calls — it is offline-safe and runs cleanly without any X API token, payment-processor key, or tax-software integration.

> 🔒 **Single-channel-dependence paradox detection.** When the top channel's share of revenue exceeds the configured concentration threshold (default 60%) AND Earnings forecast confidence is medium-or-higher (≥60), the runner surfaces the paradox in BOTH the Plan Performance section AND the Red Flags section so the creator can never accidentally celebrate a confident forecast that's brittle to a single platform shift.

> 🔒 **No specific brand names** in sponsorship recommendations unless the creator pasted them into `--revenue-file`. The runner only emits paraphrased sponsor archetypes (e.g. `dev-tools company with technical-founder audience`), never specific brands.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction. Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

The Article V.1 banner attaches automatically to the head of the Earnings Forecast section AND to every recommendation that derives a monetization tactic from the analytics or revenue file. The Article V.2 banner attaches to the head of the Tax & Expense Notes section verbatim, including the Vietnam-resident-creator addendum since many Grok Agent OS users are exactly that demographic.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator-supplied X revenue ledger (or seeded demo signals) into the strict 7/8-section monetization plan defined by the merged P85 system prompt — built for X, Grok & the ecosystem community.

The report shape is the same every time:

1. **Plan Snapshot** — one-sentence headline + 5-bullet metadata including the explicit data-source line
2. **Plan Performance** — 4-row metric table (Earnings forecast confidence / Revenue diversification / Sponsorship fit alignment / Tax-and-expense readiness) + weighted Monetization Plan score `round(0.30·Diversification + 0.25·EarningsConf + 0.25·SponsorshipFit + 0.20·TaxReadiness)`
3. **Earnings Forecast** — 30d / 90d / 365d wide bands (never point estimates) + Article V.1 banner at the head + channel mix at the chosen horizon
4. **Sponsorship Fit Analysis** — substantive niche match, trust risk, 3 paraphrased archetypes, archetypes to avoid
5. **Tax & Expense Notes** — Article V.2 banner at the head + reserve heuristic + expense-tracking gaps + documentation suggestions + jurisdiction caveat
6. **Red Flags** — 2-5 cards with severity, surfaces the **single-channel-dependence paradox** in BOTH this section AND the Plan Performance row when triggered
7. **Recommendations** — 3-5 prioritized moves across the 5-channel mix (paid_tier / creator_fund / sponsorships / digital_products / affiliate); ≥3 distinct cross-template bridges; bridges always include `analytics-summarizer` and `content-idea-generator`; V.1 disclaimer on every monetization rec
8. **Confidence**
9. **Plan Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR `projection_horizon = 365d` OR `data_source = demo`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\monetization-optimizer\run.py --x-handle JanSol0s --demo
```

That prints the 7/8-section paradox-firing demo plan (sponsorships at 73% of 90d revenue, Earnings forecast confidence 74/100 — both above the paradox thresholds) straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/monetization-optimizer/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install monetization-optimizer
```

### Option B — direct invocation (developer mode)

```powershell
# Real revenue ledger (recommended — pass your x-money-companion-dashboard SQLite export as JSON)
python .\templates\creator\monetization-optimizer\run.py `
  --x-handle JanSol0s `
  --revenue-file $env:LOCALAPPDATA\grok-agent\monetization-optimizer\my-ledger.json `
  --analytics-file $env:LOCALAPPDATA\grok-agent\analytics-summarizer\my-export.json `
  --projection-horizon 90d `
  --channel-focus all `
  --jurisdiction VN

# Paradox demo (single-channel-dependence firing on a 90d horizon)
python .\templates\creator\monetization-optimizer\run.py --x-handle JanSol0s --demo

# Healthy demo (diversified stack across all 5 channels; no paradox)
python .\templates\creator\monetization-optimizer\run.py --x-handle habitstacker --demo-healthy

# 365d-horizon thin-data audit demo (auto-triggers Plan Audit; concentration without forecast confidence)
python .\templates\creator\monetization-optimizer\run.py --x-handle JanSol0s --demo-365d-audit

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\monetization-optimizer\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\monetization-optimizer\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--revenue-file` | yes (or one of the `--demo-*` flags) | Path to a JSON revenue ledger — see `examples/sample-1-input.json` for the schema |
| `--analytics-file` | optional | Path to an `analytics-summarizer` JSON export to anchor the forecast |
| `--projection-horizon` | optional | `30d` \| `90d` \| `365d` (default `90d`; 365d auto-triggers Plan Audit) |
| `--channel-focus` | optional | `paid_tier` \| `creator_fund` \| `sponsorships` \| `digital_products` \| `affiliate` \| `all` (default `all`) |
| `--jurisdiction` | optional | ISO country code (e.g. `VN`, `US`, `SG`) used to caveat the tax/expense notes |
| `--concentration-threshold` | optional | Top-channel-share threshold for the paradox (default `0.60`) |
| `--demo` | optional | Use the canonical paradox-firing demo signals |
| `--demo-healthy` | optional | Use healthy-stack demo signals (diversified, no paradox) |
| `--demo-365d-audit` | optional | Use 365d-horizon thin-data demo signals that auto-trigger the Plan Audit |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## Revenue ledger schema (`--revenue-file`)

The runner accepts a JSON file shaped like the bundled examples (`examples/sample-1-input.json`, `sample-2-input.json`, `sample-3-input.json`). The contract:

```json
{
  "x_handle": "@<your-handle>",
  "projection_horizon": "90d",
  "channel_focus": "all",
  "jurisdiction": "VN",
  "data_source": "real",
  "currency": "USD",
  "channels": [
    {"channel": "sponsorships",     "gross_90d": <float>},
    {"channel": "paid_tier",        "gross_90d": <float>},
    {"channel": "creator_fund",     "gross_90d": <float>},
    {"channel": "digital_products", "gross_90d": <float>},
    {"channel": "affiliate",        "gross_90d": <float>}
  ],
  "history_depth_days": <int>,
  "analytics_file_present": <bool>,
  "sponsorship_signals": {
    "recent_sponsor_niche": "<paraphrased niche label>",
    "creator_niche": "<paraphrased niche label>",
    "audience_substantive_overlap_pct": <int 0-100>,
    "audience_size_match_only_pct":     <int 0-100>
  },
  "tax_expense_signals": {
    "expense_tracking_active": <bool>,
    "reserve_pct_set_aside":   <int 0-100>,
    "documentation_quality":   "high | medium | low"
  }
}
```

If `data_source` is `"demo"` the runner labels every signal as a demo placeholder. Set it to `"real"` (or omit it) when supplying actual ledger data so the report's Plan Snapshot says `real revenue ledger from --revenue-file`.

The recommended source for `channels[*].gross_90d` is the X Money Companion Dashboard's local SQLite (`templates/finance/x-money-companion-dashboard/`) — that Phase 2 tool is the canonical revenue-ledger surface for Grok Agent OS, and this runner is built to read its export shape.

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator reads; the runner never publishes, pitches, or files anywhere.
2. **No fabricated dollar amounts.** Forecasts are wide bands, never point estimates. Demo signals labelled explicitly. The runner refuses to invent absolute revenue projections.
3. **Single-channel-dependence paradox** must surface in BOTH the Plan Performance section AND the Red Flags section when top-channel revenue share > the concentration threshold (default 0.60) AND Earnings forecast confidence ≥ 60.
4. **Monetization Plan score formula is fixed.** `round(0.30·Diversification + 0.25·EarningsConf + 0.25·SponsorshipFit + 0.20·TaxReadiness)`. Diversification weighted highest because concentration is the killer; Earnings confidence and Sponsorship fit tied at 0.25 because either failing alone defeats the plan; Tax readiness weighted lowest because it is documentation hygiene, not filing.
5. **5-arrow trend bucketing** (▲▲ / ▲ / ▬ / ▼ / ▼▼) with thresholds at ±5% / ±25% relative to the sub-score healthy floor.
6. **Sponsorship archetypes are paraphrased.** Format / cluster descriptors only. Never specific brand names unless the creator explicitly pastes them in the revenue file.

---

## The 5-channel mix

Every recommendation in the Recommendations section is tagged with one channel from this canonical set. The runner enforces diversification across the recommendation list (no more than 2 recommendations against the same channel unless that channel is explicitly the `--channel-focus`):

| Channel | What it is | Typical effort |
|---|---|---|
| `paid_tier` | X Premium subscriptions, paid Spaces, paid newsletter | medium — pricing + cadence experiments |
| `creator_fund` | X creator revenue share, ad-revenue share, X Money payouts | low effort — passive once eligible |
| `sponsorships` | brand deals, sponsored posts, sponsored threads | high effort — pitch + brief + disclosure |
| `digital_products` | guides, templates, courses, paid downloads | high effort — build once, sell many |
| `affiliate` | affiliate links, referral codes, partner programs | low effort — placement matters more than volume |

---

## Cross-template daily flow

Monetization Optimizer is the **revenue-planning layer** of the Grok Agent OS creator suite — it pairs with the **measurement layer** (analytics-summarizer) on the input side and the **content layer** (content-idea-generator) on the output side. The Phase 2 X Money tools provide the ledger:

```
┌──────────────────────────────────────────────────────────────────┐
│  Quarterly — plan                                                 │
│  └─ monetization-optimizer  → 7/8-section monetization plan       │
│       │                                                           │
│       ├─ paradox flagged?   → activate a dormant channel          │
│       │                       (analytics-summarizer + content-idea-│
│       │                        generator drive the new anchor)    │
│       ├─ tax-ambush risk?   → start a 25% reserve from next       │
│       │                       inbound invoice; consult locally    │
│       └─ healthy stack?     → A/B price points via                │
│                                ab-test-suggester                  │
│                                                                   │
│  Per-rec — act                                                    │
│  └─ analytics-summarizer    → measurement layer for the forecast  │
│  └─ content-idea-generator  → next anchor in the high-EV niche    │
│  └─ niche-influencer-finder → sponsor candidates / collaborators  │
│  └─ follower-quality-analyzer → validate paid-tier conversion     │
│                                                                   │
│  Phase 2 X Money companions                                       │
│  └─ x-money-companion-dashboard → SQLite revenue ledger source    │
│  └─ x-creator-payout-optimizer  → full Streamlit deep-analysis    │
│  └─ x-money-vision-analyzer     → receipt OCR for tax notes       │
│                                                                   │
│  Monthly                                                          │
│  └─ monetization-optimizer  → re-run and watch Plan score trend   │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next runner.

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\monetization-optimizer\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\monetization-optimizer\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\monetization-optimizer\logs\` |
| Revenue ledger source | `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\money.db` (Phase 2 tool) |
| System prompt | `templates\creator\monetization-optimizer\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## Examples

Three realistic, paste-ready input/output pairs ship in [`examples/`](./examples/):

| Pair | Scenario | Input → Output |
|---|---|---|
| 1 | Single-channel-dependence paradox firing | [`sample-1-input.json`](./examples/sample-1-input.json) → [`sample-1-output.md`](./examples/sample-1-output.md) |
| 2 | Healthy diversified stack (no paradox) | [`sample-2-input.json`](./examples/sample-2-input.json) → [`sample-2-output.md`](./examples/sample-2-output.md) |
| 3 | 365d-horizon thin-data Plan Audit (concentration without forecast confidence) | [`sample-3-input.json`](./examples/sample-3-input.json) → [`sample-3-output.md`](./examples/sample-3-output.md) |

Each `sample-N-input.json` is a complete, runnable revenue ledger; each `sample-N-output.md` is the bit-identical render produced by:

```powershell
python .\run.py --x-handle <handle> --revenue-file .\examples\sample-N-input.json --no-banner
```

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_monetization_plan` (bound to `monetization_optimizer.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **8 Constitution rules** specialising Articles I, II, III, V.1, V.2, VII for monetization work
- **7 hard refusals**: auto-publish / auto-pitch / auto-file without consent gate; fabricate absolute dollar projections; give jurisdiction-specific tax filing advice; recommend specific sponsor brand names; recommend trust-eroding monetization tactics; scrape authenticated X content / payment-processor accounts; expose another creator's revenue ledger
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days
- **Disclaimers declared**: `not_financial_advice: true`, `not_tax_advice: true`

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\monetization-optimizer\grok-agent.yaml
python safety\scanner.py scan  templates\creator\monetization-optimizer\grok-agent.yaml
```

---

## v1 limitation note

The runner is **fully offline and deterministic** — it computes sub-scores directly from the supplied JSON, applies the weighted formula, buckets trends with the 5-arrow vocabulary, projects wide bands at 30d / 90d / 365d, and emits the strict 7/8-section schema. A future v2 could optionally call Grok 4.3 to generate richer interpretations of each metric row while preserving the same scoring, paradox detection, demo-vs-real labelling, paraphrased-only sponsor archetypes, V.1 / V.2 disclaimer placement, and no-fabricated-dollars invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric weighted scoring with explicit healthy-range normalisation
2. The single-channel-dependence paradox detection (firing in both required places)
3. The wide-band forecasts at 30d / 90d / 365d with explicit cone-of-uncertainty width
4. The paraphrased sponsor-archetype layer (no specific brand names, ever)
5. The Article V.1 + V.2 disclaimer placement at section heads AND per monetization recommendation
6. The demo-vs-real data-source labelling (creators can never confuse a demo for real data)
7. The deterministic seeded recommendation shuffle (reproducible plans)
8. The Plan Audit auto-trigger on 365d horizons, demo data sources, or red-flag overflow

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P85 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` (3 pairs) | ✅ P86 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> Built for X, Grok & the ecosystem community.
