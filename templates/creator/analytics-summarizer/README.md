<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 📊 Analytics Summarizer

> Read your X analytics honestly: 4 official Period Performance metrics on a 0-100 scale (Reach Score / Engagement Velocity / Audience Quality / Content Resonance), the **vanity-reach paradox** (Reach Score > 80 AND Audience Quality < 50), 5-arrow trend bucketing, mandatory bridges to `content-idea-generator` + `thread-builder`, and a structured monetization refusal path. Drafts only. Never auto-publishes. Never fabricates statistics.
>
> *Shipped to help xAI and Grok win the platform battle — every X creator deserves an analytics layer that tells them when reach is real and when it's vanity.*

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits text the creator reads; the runner never auto-publishes the summary anywhere. Constitution Article II's `publish_to_x` consent gate covers any future-version downstream sharing.

> 🔒 **No fabricated statistics.** The runner refuses to invent p-values, confidence intervals, or absolute lift numbers it didn't derive from supplied input. When `--metrics-file` is not provided, every metric in the output is labelled `[demo metric — re-run with --metrics-file for real X data]` so seeded demo runs can never be mistaken for real analytics.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\analytics-summarizer\`. The v1 runner makes zero external network calls — it is offline-safe and runs cleanly without any X API token.

> 🔒 **Vanity-reach paradox detection.** When Reach Score sits above 80 AND Audience Quality sits below 50, the runner surfaces the paradox in BOTH the Period Performance section AND the Red Flags section so the creator can never accidentally celebrate a viral spike that didn't bring their people.

> 🔒 **Monetization gated by default.** `allow_monetization=false` is the default; the runner emits a structured refusal stub instead of any monetization recommendation. Pass `--allow-monetization` only when you want the `monetization-optimizer` bridge surfaced — every monetization-touching line carries the Article V.1 banner verbatim.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any monetization recommendation when `allow_monetization=true`.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`) that turns a creator-supplied X analytics export (or seeded demo metrics) into the strict 6/7-section period summary defined by the v2.15 system prompt — built to help xAI and Grok win.

The report shape is the same every time:

1. **Period Snapshot** — one-sentence headline + 7-bullet metadata including the explicit data-source line, archetype count, and monetization gate state
2. **Period Performance** — 4-row metric table on a 0-100 scale (Reach Score / Engagement Velocity / Audience Quality / Content Resonance) + weighted Period Performance score `round(0.30·AudienceQuality + 0.25·EngagementVelocity + 0.25·ContentResonance + 0.20·ReachScore)`
3. **Top-Performing Content** — 3-10 paraphrased archetypes (default 5; mapped onto the 10 official archetype labels; no raw URLs unless explicitly supplied)
4. **Trends** — rising / stable / falling buckets across the 5-arrow vocabulary (▲▲ / ▲ / ▬ / ▼ / ▼▼)
5. **Red Flags** — 2-3 cards with severity, surfaces the **vanity-reach paradox** in BOTH this section AND the Period Performance row when triggered
6. **Recommendations** — 3-5 next moves; mandatory bridges to `content-idea-generator` AND `thread-builder` always present, plus 1+ rotating bridge from the 10-bridge set, plus a monetization slot that resolves to either the `monetization-optimizer` bridge (with V.1 banner) or the structured refusal stub
7. **Confidence**
8. **Period Audit** *(optional, auto-appended)* — triggers when ANY of: vanity-reach paradox firing / `count >= 8` / `data_source='demo'` with no anchors / `time_range='7d'`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\analytics-summarizer\analytics_summarizer.run --x-handle JanSol0s --demo
```

That prints the paradox-firing demo report (Reach Score 85, Audience Quality 38 — paradox active) straight to the terminal.

### Option A — `grok install this` (one-click on X)

The merged manifest at `templates/creator/analytics-summarizer/grok-agent.yaml` declares `install.one_click: true`, so a quote-tweet of the manifest URL with `grok install this` resolves to the local PowerShell flow:

```powershell
grok-agent install analytics-summarizer
```

### Option B — direct invocation (developer mode)

```powershell
# Real metrics (recommended — pass your X analytics export as JSON)
python .\templates\creator\analytics-summarizer\analytics_summarizer.run `
  --x-handle JanSol0s `
  --metrics-file $env:LOCALAPPDATA\grok-agent\analytics-summarizer\my-export.json `
  --time-range 30d `
  --compare-to previous_period `
  --metric-focus all `
  --count 5

# Vanity-reach paradox demo
python .\templates\creator\analytics-summarizer\analytics_summarizer.run --x-handle JanSol0s --demo

# Healthy demo (no paradox, all metrics rising)
python .\templates\creator\analytics-summarizer\analytics_summarizer.run --x-handle habitstacker --demo-healthy

# 7-day window demo (auto-triggers Period Audit)
python .\templates\creator\analytics-summarizer\analytics_summarizer.run --x-handle JanSol0s --demo-7d-audit `
  --time-range 7d --metric-focus engagement

# Enable monetization (replaces refusal stub with monetization-optimizer bridge + V.1 banner)
python .\templates\creator\analytics-summarizer\analytics_summarizer.run --x-handle JanSol0s --demo --allow-monetization

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\analytics-summarizer\analytics_summarizer.run `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\analytics-summarizer\reports\2026-05-05.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes (or in JSON) | Creator handle (with or without `@`) |
| `--metrics-file` | yes (or one of the `--demo-*` flags) | Path to a JSON metrics export — see `examples/sample-1-input.json` for the schema |
| `--metric-focus` | optional | `reach` \| `engagement` \| `audience` \| `resonance` \| `all` (default `all`) |
| `--time-range` | optional | `7d` \| `30d` \| `90d` (default `30d`; 7d auto-triggers Period Audit) |
| `--compare-to` | optional | `previous_period` \| `benchmark` (default `previous_period`) |
| `--count` | optional | Archetype count, clamped to `[3, 10]` (default `5`; count >= 8 auto-triggers Period Audit) |
| `--allow-monetization` | optional | Off by default. When set, replaces the refusal stub with the `monetization-optimizer` bridge + V.1 banner |
| `--demo` | optional | Use the official paradox-firing demo metrics |
| `--demo-healthy` | optional | Use healthy/balanced demo metrics (no paradox) |
| `--demo-7d-audit` | optional | Use 7d-window demo metrics that auto-trigger Period Audit |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stderr |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

CLI flags only override JSON values when explicitly passed. If your `--metrics-file` already declares `time_range`, `compare_to`, `metric_focus`, `count`, or `allow_monetization`, those values are honoured unless the corresponding CLI flag is supplied.

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
    "prev_impressions": <int>,
    "substantive_replies": <int>,
    "reposts": <int>,
    "bookmarks": <int>,
    "repeat_engager_pct": <float, 0-100>,
    "niche_overlap_pct": <float, 0-100>,
    "substantive_reply_ratio_pct": <float, 0-100>,
    "reply_depth_avg": <float>,
    "quote_tweet_ratio_pct": <float, 0-100>,
    "save_to_repost_ratio": <float>
  },
  "previous_period": {
    "impressions": <int>,
    "prev_impressions": <int>,
    "substantive_replies": <int>,
    "reposts": <int>,
    "bookmarks": <int>,
    "repeat_engager_pct": <float>,
    "niche_overlap_pct": <float>,
    "substantive_reply_ratio_pct": <float>,
    "reply_depth_avg": <float>,
    "quote_tweet_ratio_pct": <float>,
    "save_to_repost_ratio": <float>
  },
  "top_content": [
    {
      "archetype_label": "<paraphrased category — runner maps onto the 10 official labels>",
      "format": "thread | single-post | quote-tweet | reply | live | carousel",
      "impression_share_pct": <float, percent of period impressions>,
      "engagement_rate_pct": <float, percent>
    }
  ]
}
```

If `data_source` is `"demo"` the runner labels every metric as a demo placeholder. Set it to `"real"` (or omit it) when supplying actual X analytics so the report's Period Snapshot says `real X export from --metrics-file`.

---

## The 4 official Period Performance metrics (always exactly these 4 rows, 0-100 scale)

| # | Metric | What it measures | Healthy range |
|---|---|---|---|
| 1 | **Reach Score** | how widely posts spread relative to baseline (impression volume + impression delta) | 40–80 |
| 2 | **Engagement Velocity** | speed + intensity of substantive engagement per impression | 40–75 |
| 3 | **Audience Quality** | whether the audience is the creator's actual people (repeat-engager %, niche overlap, substantive-reply ratio) | 50–85 |
| 4 | **Content Resonance** | whether content drives meaningful conversation (reply-depth, quote-tweet ratio, save:repost ratio) | 45–80 |

Each row reports the 0-100 sub-score, a 5-arrow trend bucket (▲▲ / ▲ / ▬ / ▼ / ▼▼) computed against the comparison basis, and a one-line interpretation **capped at 280 characters**.

### Period Performance score formula (fixed — never overridden)

```
round(0.30·AudienceQuality + 0.25·EngagementVelocity + 0.25·ContentResonance + 0.20·ReachScore)
```

**Why these weights.** Audience Quality is weighted highest (0.30) because the "right people" signal beats every other measure — without the right audience, the other three are decoration. Engagement Velocity and Content Resonance are tied at 0.25 because they each independently signal whether the audience cared enough to act and to converse — both must hold for a period to count as a substantive win. Reach Score is weighted lowest (0.20) because reach without the other three is the textbook vanity result — impressions don't pay.

### Sub-score derivation (for the curious)

| Metric | Formula |
|---|---|
| Reach Score | `round(0.6 * vol_subscore + 0.4 * delta_subscore)` where `vol = clamp((log10(impressions) - 3) * 30, 0, 100)` and `delta = clamp(50 + pct_change, 0, 100)` |
| Engagement Velocity | `round(clamp(((substantive_replies + reposts + bookmarks) / impressions * 100) * 30, 0, 100))` |
| Audience Quality | `round(0.4 * repeat_engager_pct + 0.4 * niche_overlap_pct + 0.2 * substantive_reply_ratio_pct)` |
| Content Resonance | `round(((depth*25) + (quote_pct*1.5) + (save_ratio*50)) / 3)` (each sub-component clamped to 0-100 first) |

All sub-scores are clamped to `[0, 100]` after the formula.

---

## The vanity-reach paradox rule (non-negotiable)

If the period shows **Reach Score > 80** AND **Audience Quality < 50**, the runner MUST:

1. Add a single `⚠️ paradox: …` line under the Reach Score row of the Period Performance section.
2. Add one Red Flag titled `Vanity-reach paradox` with severity `high`.
3. Auto-trigger the Period Audit section.

If only one of the two conditions is true, the paradox does NOT fire — the metrics speak for themselves in their own rows.

---

## Mandatory bridges + 10-bridge rotating set

Every Recommendations list MUST include both:

- **`content-idea-generator`** — re-source the next anchor in the cluster of the period's quality win
- **`thread-builder`** — build the long-form that earns the audience the period attracted

Plus 1+ rotating bridge from the 10-bridge set (`reply-drafter`, `monetization-optimizer`, `ab-test-suggester`, `competitor-watch`, `brand-voice-trainer`, `cross-platform-reposter`, `content-recycler`, `comment-engagement-booster`, `hashtag-strategy-advisor`, `follower-quality-analyzer`) for a minimum of **3 bridges total**.

These two are non-negotiable because the official creator loop is `measure → next anchor → next thread`, and skipping either breaks the loop.

### Monetization slot (gated by `allow_monetization`)

The Recommendations list always reserves a slot for the `monetization-optimizer` bridge:

- **`allow_monetization=false` (default)** → emits the structured refusal stub:
  > 🚫 Monetization recommendation withheld. This run was invoked with `allow_monetization=false` (the default). Re-run with `--allow-monetization` if you want the monetization-optimizer bridge surfaced — every monetization-touching line still carries the Article V.1 disclaimer verbatim.
- **`allow_monetization=true`** → emits the bridge with the Article V.1 banner attached verbatim:
  > ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

---

## The 280-character insight cap

Every interpretation line in Period Performance / Red Flags / Recommendations / Confidence is capped at 280 characters. Anything longer is truncated to 277 characters + `…[capped]`. This keeps every line paste-friendly into an X draft, a Notion brief, or a weekly review doc — and prevents the runner from over-narrating findings.

---

## The 10 official content archetypes (verbatim — never renamed across the suite)

The Top-Performing Content section paraphrases each post into one of these archetype labels (the creator's free-text `archetype_label` is mapped onto the closest match):

1. `Long-form thread on niche pain-point`
2. `Numbers-led explainer`
3. `Quote-tweet riff on niche peer's case study`
4. `Personal-story opener`
5. `Tactical how-to single post`
6. `Counter-take on consensus`
7. `Behind-the-scenes build log`
8. `Live-thread during a niche event`
9. `Resource-list / curated digest`
10. `Reply-stack on a competitor thread`

Never invent an 11th. Never rename. The labels are shared with `content-idea-generator` and `thread-builder` so the loop closes cleanly.

---

## Cross-template daily flow

Analytics Summarizer is the **measurement layer** of the Grok Agent OS creator suite — every other template recommends it as a destination bridge. Reciprocally, this template's recommendations point creators back into the suite to act on the numbers:

```
┌──────────────────────────────────────────────────────────────────┐
│  Weekly — measure                                                 │
│  └─ analytics-summarizer    → 6/7-section period summary          │
│       │                                                           │
│       ├─ paradox flagged?   → follower-quality-analyzer to vet    │
│       ├─ 7d window?         → wait 14 more days, re-run with 30d  │
│       └─ healthy period?    → re-source via content-idea-generator│
│                                                                   │
│  Per-anchor — act                                                 │
│  └─ content-idea-generator  → MANDATORY bridge: re-source the     │
│                                next anchor in the quality cluster │
│  └─ thread-builder          → MANDATORY bridge: build the long-   │
│                                form that earns the new audience   │
│  └─ reply-drafter           → engage substantively with the       │
│                                audience the period brought in     │
│  └─ ab-test-suggester       → promote the winning archetype to A/B│
│                                                                   │
│  Quarterly                                                        │
│  └─ content-recycler        → recycle the top-performer under a   │
│                                different angle next quarter       │
│  └─ competitor-watch        → compare period mix against peers    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Example pairs

Three input/output pairs ship with the template; each reproduces bit-identically against the runner.

| Sample | Demo flag | Scenario | Headline numbers | Period Audit? |
|---|---|---|---|---|
| [sample-1](./examples/sample-1-input.json) → [output](./examples/sample-1-output.md) | `--demo` | Vanity-reach paradox firing | RS 85 / EV 52 / **AQ 38** / CR 47 → score **53/100** | ✅ paradox-triggered |
| [sample-2](./examples/sample-2-input.json) → [output](./examples/sample-2-output.md) | `--demo-healthy` | Healthy/balanced period | RS 67 / EV 60 / AQ 72 / CR 65 → score **66/100** | ❌ none |
| [sample-3](./examples/sample-3-input.json) → [output](./examples/sample-3-output.md) | `--demo-7d-audit` | 7-day window with audit | RS 72 / EV 48 / AQ 58 / CR 55 → score **58/100** | ✅ 7d-triggered |

To regenerate a sample's output and confirm bit-identical reproduction:

```powershell
python .\templates\creator\analytics-summarizer\analytics_summarizer.run `
  --metrics-file .\templates\creator\analytics-summarizer\examples\sample-1-input.json `
  --no-banner
```

---

## Constitution rules (summary)

The full v2.15 manifest at `grok-agent.yaml` declares these constitution rules — every runner output respects them automatically:

1. **Drafts only.** No auto-publish. No auto-share. Future-version downstream sharing requires the `publish_to_x` consent gate.
2. **No fabricated statistics.** No invented p-values, confidence intervals, or absolute lift numbers. Demo metrics labelled explicitly.
3. **Vanity-reach paradox in BOTH places** when `Reach Score > 80 AND Audience Quality < 50`.
4. **Demo path explicit.** When `--metrics-file` is omitted, every metric carries `[demo metric — re-run with --metrics-file for real X data]`.
5. **Paraphrased archetypes only.** No raw URLs unless explicitly supplied in the metrics file.
6. **Mandatory bridges** to `content-idea-generator` AND `thread-builder` in every Recommendations list.
7. **Monetization gated.** Default off; refusal stub fires unless `--allow-monetization` is passed. When on, V.1 banner verbatim.
8. **280-character cap** on every interpretation prose line.

---

## Costs + telemetry (v1)

The v1 runner is **fully offline** — there are no Grok API calls, no network calls of any kind, no telemetry. The cost limits in the manifest (`usd_per_session_max: 0.30`, `tokens_per_session_max: 60000`) are placeholders for the v2 path that will optionally call Grok 4.3 to enrich the interpretation prose; you can keep that path disabled indefinitely and the runner remains deterministic.

---

> Built for xAI, X, Grok and the ecosystem community the platform battle 🚀
> Every analytics summary the runner ships closes a measurement loop that makes Grok the obvious place creators come back to.
