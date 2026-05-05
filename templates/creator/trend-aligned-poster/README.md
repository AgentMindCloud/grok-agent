<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Trend-Aligned Poster

> **Built for X, Grok & the ecosystem community.**
> Local-first trend-aligned poster for X creators. Reads creator-supplied trend data (or seeded demo trends) and emits a structured 7/8-section trend-aligned post plan with 4 canonical Trend Alignment Plan Score metrics, the trend-chasing paradox surfaced in BOTH the Plan Score table AND Red Flags whenever it fires, an idea-level off-niche guard, 4–6 production-quality post ideas, and unconditional bridges to `content-idea-generator` + `thread-builder` in every output.

> ⚠️ **No financial, cashtag, investment, or sponsorship content.** This template refuses to generate trading, ticker, portfolio, or paid-promotion copy. The runner errors out with a forbidden-token message if any trend or idea contains a cashtag (e.g. `$TSLA`), the words `invest`/`portfolio`/`hedge`, or `sponsor`/`#ad` markers without creator-supplied disclosure copy.

> ⚠️ **Drafts only.** The runner emits a plan the creator reads before posting. It never auto-publishes, schedules, or queues posts.

---

## What it is

A deterministic Python runner bound to a v2.15 `creator-template` manifest. Given a creator's X handle plus an optional JSON trends file, it produces a 7-section markdown plan (8 sections when the Trend Audit auto-triggers). Every output ships with:

- **4 canonical Trend Alignment Plan Score metrics** — Trend match strength / Niche fit / Voice fidelity / Originality, with the fixed weighted formula `round(0.30·TrendMatch + 0.25·NicheFit + 0.25·Voice + 0.20·Originality)` over healthy-range-normalised sub-scores.
- **Trend-chasing paradox** dual-surface rule — when avg Trend match > 75 AND avg Niche fit < the configured floor (default 40), the paradox fires in BOTH the Plan Score table AND a high-severity Red Flag.
- **Off-niche guard** — any individual idea with `trend_match ≥ 75` AND `niche_fit < 40` is excluded from Post Ideas and consolidated into a single Red Flag titled `Off-niche trend-chasers excluded`.
- **Mandatory bridges** — every output's Recommendations list includes at least one bridge to `content-idea-generator` (position 1) and one to `thread-builder` (position 2). These are non-negotiable per the system prompt.
- **5-arrow trend vocabulary** — `▲▲ ▲ ▬ ▼ ▼▼` for every metric vs the comparison basis.
- **Demo labels** — when no `--trends-file` is supplied the runner seeds explicit demo data marked `[demo trend — re-run with --trends-file for real X data]` on every metric so creators never confuse seeded data for real X signal.

---

## Quick launch (Windows 11 + PowerShell)

### Option A — paradox-firing demo (recommended first run)

```powershell
python .\templates\creator\trend-aligned-poster\run.py `
    --x-handle JanSol0s `
    --demo
```

You'll see: paradox firing (avg TM 79.5, avg NF 38.5), 6 off-niche ideas excluded, Trend Audit auto-triggered, all 7 mandatory plan sections plus the audit (8 total).

### Option B — healthy demo

```powershell
python .\templates\creator\trend-aligned-poster\run.py `
    --x-handle habitstacker `
    --demo-healthy
```

You'll see: all metrics inside healthy bands, no paradox, no off-niche excluded, no audit auto-triggered (7-section output).

### Option C — 7d-window audit demo

```powershell
python .\templates\creator\trend-aligned-poster\run.py `
    --x-handle thindata `
    --demo-7d-audit
```

You'll see: window=7d auto-triggers the Trend Audit, stale watchlist surfaced, medium-confidence label.

### Option D — real X trend data

```powershell
python .\templates\creator\trend-aligned-poster\run.py `
    --x-handle JanSol0s `
    --trends-file .\my-trends.json `
    --window 30 `
    --compare-to previous_period
```

Output goes to stdout by default. Add `--out plan.md` to write a markdown file with the Apache 2.0 HTML-comment header pre-pended.

---

## Flag reference

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--x-handle` | string | required | Creator's X handle, with or without `@`. Privacy anchor — only this handle appears in the output. |
| `--trends-file` | path | (none) | Local JSON path. When omitted, demo data seeds with explicit labels. |
| `--window` | int | 30 | One of 7 / 30 / 90. `7` auto-triggers the Trend Audit section. |
| `--compare-to` | string | `previous_period` | One of `previous_period` / `benchmark`. Drives the 5-arrow buckets. |
| `--niche-fit-floor` | float | 40.0 | Below this average Niche fit, the trend-chasing paradox fires. |
| `--target-idea-count` | int | 5 | Target post idea count, clamped to `[4, 6]`. |
| `--demo` | bool | false | Paradox-firing seeded data. |
| `--demo-healthy` | bool | false | All-within-bounds seeded data. |
| `--demo-7d-audit` | bool | false | 7d window seeded data that auto-triggers Trend Audit. |
| `--out` | path | (stdout) | Write plan to file. The Apache 2.0 HTML-comment header is prepended automatically. |

---

## `--trends-file` schema

The runner accepts a JSON object matching this shape:

```jsonc
{
  "x_handle": "@JanSol0s",
  "window": 30,
  "compare_to": "previous_period",
  "data_source": "real",
  "niche_label": "ai-agents + creator-tools",
  "trends": [
    {
      "trend_paraphrase": "open-source agent eval framework crossing benchmark thresholds",
      "velocity": "accelerating",
      "niche_fit_label": "tight",
      "hours_old": 18
    }
    // 3-8 trends total
  ],
  "candidate_ideas": [
    {
      "format": "thread",
      "trend_tag": "agent-eval-benchmark",
      "copy_outline": "walk through the eval framework's contribution and where it falls short",
      "trend_match_score": 78,
      "niche_fit_score": 88,
      "voice_fidelity_score": 80,
      "originality_score": 70
    }
    // >= 4 candidate ideas; runner picks 4-6 after off-niche guard
  ],
  "previous_window_summary": {
    "avg_trend_match_score": 64.0,
    "avg_niche_fit_score": 70.0,
    "avg_voice_fidelity_score": 76.0,
    "avg_originality_score": 68.0
  }
}
```

### Field constraints

- `velocity`: one of `accelerating` / `steady` / `decaying` / `stale`
- `niche_fit_label`: one of `tight` / `adjacent` / `loose` / `off`
- `format`: one of `single` / `thread` / `quote-tweet` / `image-post` / `reply-thread`
- All scores: 0–100 numeric

The runner refuses any trend or idea that contains forbidden tokens — cashtags (`$TSLA`), trading hints (`buy $`, `sell $`, `long $`, `short $`), `invest`/`portfolio`/`hedge`, or `sponsor`/`#ad` without disclosure. This is a hard refusal per the manifest.

---

## How the plan is shaped (6 hard rules from the system prompt)

1. **Drafts only** — the runner emits text the creator reads; never an auto-publish action.
2. **No fabricated statistics** — demo metrics carry the `[demo trend — re-run with --trends-file for real X data]` label.
3. **Trend-chasing paradox dual-surface** — when avg TM > 75 AND avg NF < `--niche-fit-floor`, the paradox appears in BOTH the Plan Score table AND the Red Flags section.
4. **Plan Score formula is fixed** — `round(0.30·TrendMatch + 0.25·NicheFit + 0.25·Voice + 0.20·Originality)` over healthy-range-normalised sub-scores.
5. **Off-niche guard is non-negotiable** — `trend_match ≥ 75 AND niche_fit < 40` excludes the idea from Post Ideas and consolidates as a single Red Flag.
6. **Unconditional bridges** — every Recommendations list includes at least `content-idea-generator` (position 1) and `thread-builder` (position 2).

---

## Cross-template daily flow

```
                    +------------------------+
                    |   trend-aligned-poster |
                    +------------------------+
                          |              |
            (mandatory)   |              |  (mandatory)
                          v              v
            content-idea-generator   thread-builder
                          |
                          | (optional, on-paradox)
                          v
                    brand-voice-trainer
                          |
                          v
                    analytics-summarizer (next window)
```

When the paradox fires, the runner steers Recommendations toward `brand-voice-trainer` to prevent voice drift while the creator is in trend-chasing territory. When it doesn't, it pivots toward `analytics-summarizer` for next-window measurement.

---

## Where data lives (Windows paths)

| Surface | Path |
|---|---|
| AppData root | `%LOCALAPPDATA%\grok-agent\trend-aligned-poster\` |
| Cache | `%LOCALAPPDATA%\grok-agent\trend-aligned-poster\cache\` |
| Logs | `%LOCALAPPDATA%\grok-agent\trend-aligned-poster\logs\` |

The runner does not write to these paths in v1 (no caching, no log files). They are reserved for future versions and declared in the manifest's `windows` block so the safety scanner can validate the storage contract.

---

## Examples

The `examples/` folder ships three input/output pairs covering every demo mode:

| File pair | Demo mode | What it shows |
|---|---|---|
| `sample-1-input.json` + `sample-1-output.md` | paradox-firing | Trend-chasing paradox active + off-niche guard fires + Trend Audit auto-triggered |
| `sample-2-input.json` + `sample-2-output.md` | healthy | All metrics within bounds + no paradox + no audit |
| `sample-3-input.json` + `sample-3-output.md` | 7d-audit | window=7d auto-triggers the Trend Audit + stale watchlist + medium confidence |

Reproduce each from the command line with the matching demo flag (see Quick launch above).

---

## What the manifest declares

| Manifest field | Value |
|---|---|
| `version` | `2.15` |
| `kind` | `creator-template` |
| `windows.appdata_folder` | `grok-agent/trend-aligned-poster` |
| `tools[0].name` | `generate_trend_aligned_post_plan` |
| `tools[0].module` | `trend_aligned_poster.run` |
| `tools[0].function` | `generate` |
| `safety.cost_limits.usd_per_session_max` | `0.30` |
| `safety.cost_limits.usd_per_day_max` | `1.00` |
| `safety.human_in_the_loop.enabled` | `true` |
| `constitution.hard_refusals[]` | auto-publish · finance · sponsorship · third-party-handles · scraping |

The full manifest is at `templates/creator/trend-aligned-poster/grok-agent.yaml`. The system prompt (Slot 1) is at `templates/creator/trend-aligned-poster/prompts/system.md`.

---

## v1 limitations

- No real-time X-trend ingestion. The runner reads a creator-supplied JSON; trend pulls from xAI's public API are scheduled for a future version.
- No outbound network calls. Article VII of the project Constitution (local-first) takes precedence in v1.
- No automated publishing. Post Ideas are drafts only; the creator decides what to publish.
- Predicted engagement bands are heuristic (composite of TM/NF/Voice). They are not statistical predictions.

---

## Build slots (Recipe B)

| Slot | Status | Files |
|---|---|---|
| Slot 1 | ✅ shipped (P93) | `grok-agent.yaml`, `prompts/system.md` |
| Slot 2 | ✅ shipped (P108) | `run.py`, `README.md`, `examples/` |

---

## License

Apache 2.0 — see the repository root `LICENSE` file. Every code and config file in this template carries an Apache 2.0 header.

> Built for X, Grok & the ecosystem community.
