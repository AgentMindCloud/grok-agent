<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Content Idea Generator

> **Built for X, Grok & the ecosystem community.**
> Local-first content idea generator for X creators. Reads creator-supplied performance + voice + trend signals (or seeded demo signals) and emits a structured 7/8-section idea batch with 4 canonical Idea Plan Score metrics, the **derivative-and-thin paradox** surfaced in BOTH the Plan Score table AND Red Flags whenever it fires, voice-drift candidates flagged inline on the cards, 4–6 production-quality idea cards, and unconditional bridges to `analytics-summarizer` + `brand-voice-trainer` in every output.

> ⚠️ **No financial, cashtag, investment, or sponsorship content.** This template refuses to generate trading, ticker, portfolio, or paid-promotion copy. The runner errors out with a forbidden-token message if any niche, tone, archetype, or copy outline contains a cashtag (e.g. `$TSLA`), the words `invest`/`portfolio`/`hedge`, or `sponsor`/`#ad` markers without creator-supplied disclosure copy.

> ⚠️ **Drafts only.** The runner emits a batch the creator reads before posting. It never auto-publishes, schedules, or queues posts.

---

## What it is

A deterministic Python runner bound to a v2.15 `creator-template` manifest. Given a creator's X handle plus optional analytics / voice profile / trend signals files, it produces a 7-section markdown batch (8 sections when the Idea Audit auto-triggers). Every output ships with:

- **4 canonical Idea Plan Score metrics** — Niche fit / Voice fidelity / Originality / Engageability, with the fixed weighted formula `round(0.30·NicheFit + 0.25·Voice + 0.25·Originality + 0.20·Engageability)` over healthy-range-normalised sub-scores.
- **Derivative-and-thin paradox** dual-surface rule — when avg Originality < 40 AND avg Voice fidelity < 60, the paradox fires in BOTH the Plan Score table AND a high-severity Red Flag.
- **Voice-drift candidate surfacing** — any idea with `voice_fidelity_score < 50` stays in the batch but carries `⚠️ voice-drift candidate` inline AND triggers a Red Flag titled `Voice-drift candidates surfaced` (severity `medium`).
- **Mandatory bridges** — every output's Recommendations list includes at least one bridge to `analytics-summarizer` (position 1) and one to `brand-voice-trainer` (position 2).
- **5-arrow trend vocabulary** — `▲▲ ▲ ▬ ▼ ▼▼` for every metric vs the previous-period baseline.
- **Demo labels** — when no real data files are supplied the runner seeds explicit demo data marked `[demo idea — re-run with --analytics-file / --voice-profile-file / --trend-signals-file for real X data]` on every metric so creators never confuse seeded data for real X signal.

---

## Quick launch (Windows 11 + PowerShell)

### Option A — paradox-firing demo (recommended first run)

```powershell
python .\templates\creator\content-idea-generator\run.py `
    --x-handle JanSol0s `
    --niche "ai-agents" `
    --tone thoughtful `
    --demo
```

You'll see: paradox firing (avg Originality 33.6, avg Voice fidelity 50.7), 2 voice-drift candidates flagged inline, Idea Audit auto-triggered, all 7 mandatory plan sections plus the audit (8 total).

### Option B — healthy demo

```powershell
python .\templates\creator\content-idea-generator\run.py `
    --x-handle habitstacker `
    --niche "habit-design" `
    --tone story-led `
    --demo-healthy
```

You'll see: all metrics inside healthy bands, no paradox, no voice-drift, no audit auto-triggered (7-section output).

### Option C — 7d-window audit demo

```powershell
python .\templates\creator\content-idea-generator\run.py `
    --x-handle thindata `
    --niche "applied-ml" `
    --tone data-led `
    --demo-7d-audit
```

You'll see: window=7d auto-triggers the Idea Audit, medium-confidence label.

### Option D — real X signals

```powershell
python .\templates\creator\content-idea-generator\run.py `
    --x-handle JanSol0s `
    --niche "ai-agents" `
    --tone thoughtful `
    --count 5 `
    --analytics-file .\my-analytics.json `
    --trend-signals-file .\my-trends.json `
    --voice-profile-file .\my-voice.json `
    --window 30
```

Output goes to stdout by default. Add `--out batch.md` to write a markdown file with the Apache 2.0 HTML-comment header pre-pended.

---

## Flag reference

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--x-handle` | string | required | Creator's X handle, with or without `@`. Privacy anchor — only this handle appears in the output. |
| `--niche` | string | `general creator` | Free-text creator niche (max 80 chars). Drives demo seeding + snapshot label. |
| `--tone` | string | `thoughtful` | One of `punchy` / `thoughtful` / `data-led` / `story-led` / `playful`. |
| `--count` | int | (unset) | Target idea count, clamped to `[4, 6]`. |
| `--target-idea-count` | int | 5 | Alias for `--count` (P12 starter compatibility). |
| `--window` | int | 30 | One of 7 / 30 / 90. `7` auto-triggers the Idea Audit section. |
| `--analytics-file` | path | (none) | Path to analytics export (the JSON `analytics-summarizer` consumes). |
| `--voice-profile-file` | path | (none) | Path to voice profile (the JSON `brand-voice-trainer` emits). |
| `--trend-signals-file` | path | (none) | Path to trend signals (the JSON `trend-aligned-poster`'s plan emits). |
| `--demo` | bool | false | Derivative-and-thin paradox-firing seeded data. |
| `--demo-healthy` | bool | false | All-within-bounds seeded data. |
| `--demo-7d-audit` | bool | false | 7d window seeded data that auto-triggers Idea Audit. |
| `--out` | path | (stdout) | Write batch to file. The Apache 2.0 HTML-comment header is prepended automatically. |

---

## Input file schemas

### `--analytics-file` (optional)

The same JSON shape `analytics-summarizer` consumes. The runner lifts `top_content[]` into the batch's `Top-Performing Archetypes` section:

```jsonc
{
  "top_content": [
    {
      "archetype_label": "personal anecdote on evening-friction audits",
      "format": "thread",
      "impression_share_pct": 38,
      "engagement_rate_pct": 6.8
    }
  ]
}
```

### `--trend-signals-file` (optional)

The same JSON shape `trend-aligned-poster`'s plan emits. The runner lifts `candidate_ideas[]` directly:

```jsonc
{
  "candidate_ideas": [
    {
      "format": "thread",
      "copy_outline": "five-tweet thread on the evening-friction audit",
      "niche_fit_score": 90,
      "originality_score": 78,
      "voice_fidelity_score": 88,
      "engagement_band": "high"
    }
  ]
}
```

### `--voice-profile-file` (optional)

A `brand-voice-trainer` JSON export. The runner reads it for parse-validation only in v1; the voice profile influences interpretation, not score arithmetic.

### Field constraints

- `format`: one of `single` / `thread` / `quote-tweet` / `image-post` / `reply-thread`
- All scores: 0–100 numeric

The runner refuses any archetype label, copy outline, niche, or tone that contains forbidden tokens — cashtags (`$TSLA`), trading hints (`buy $`, `sell $`, `long $`, `short $`), `invest`/`portfolio`/`hedge`, or `sponsor`/`#ad` without disclosure. This is a hard refusal per the manifest.

---

## How the batch is shaped (6 hard rules from the system prompt)

1. **Drafts only** — the runner emits text the creator reads; never an auto-publish action.
2. **No fabricated statistics** — demo metrics carry the `[demo idea — re-run with --analytics-file / --voice-profile-file / --trend-signals-file for real X data]` label.
3. **Derivative-and-thin paradox dual-surface** — when avg Originality < 40 AND avg Voice fidelity < 60, the paradox appears in BOTH the Plan Score table AND a high-severity Red Flag.
4. **Plan Score formula is fixed** — `round(0.30·NicheFit + 0.25·Voice + 0.25·Originality + 0.20·Engageability)` over healthy-range-normalised sub-scores.
5. **Voice-drift surfacing** — any idea with `voice_fidelity_score < 50` carries `⚠️ voice-drift candidate` inline AND triggers a Red Flag.
6. **Unconditional bridges** — every Recommendations list includes at least `analytics-summarizer` (position 1) and `brand-voice-trainer` (position 2).

---

## Cross-template daily flow

```
                        +------------------+
                        |  analytics-      |
                        |  summarizer      |  (period-end measurement)
                        +--------|---------+
                                 |  feeds top archetypes
                                 v
                  +--------------+--------------+
                  |  content-idea-generator     |
                  +--------------+--------------+
                          |              |
              (mandatory) |              | (mandatory)
                          v              v
                analytics-summarizer  brand-voice-trainer
                                          |
                                          v
                              re-anchored drafts → publish
```

When the paradox fires, the runner steers Recommendations toward `brand-voice-trainer` to re-anchor voice + originality. When voice-drift candidates are flagged, the runner promotes them through the trainer before they reach the publish queue.

---

## Where data lives (Windows paths)

| Surface | Path |
|---|---|
| AppData root | `%LOCALAPPDATA%\grok-agent\content-idea-generator\` |
| Cache | `%LOCALAPPDATA%\grok-agent\content-idea-generator\cache\` |
| Logs | `%LOCALAPPDATA%\grok-agent\content-idea-generator\logs\` |

The runner does not write to these paths in v1 (no caching, no log files). They are reserved for future versions.

---

## Examples

The `examples/` folder ships three input/output pairs covering every demo mode:

| File pair | Demo mode | What it shows |
|---|---|---|
| `sample-1-input.json` + `sample-1-output.md` | paradox-firing | Derivative-and-thin paradox active + 2 voice-drift candidates surfaced + Idea Audit auto-triggered |
| `sample-2-input.json` + `sample-2-output.md` | healthy | All metrics within bounds + no paradox + no drift + no audit |
| `sample-3-input.json` + `sample-3-output.md` | 7d-audit | window=7d auto-triggers the Idea Audit + medium confidence |

Reproduce each from the command line with the matching demo flag (see Quick launch above).

---

## What the manifest declares

| Manifest field | Value |
|---|---|
| `version` | `2.15` |
| `kind` | `creator-template` |
| `windows.appdata_folder` | `grok-agent/content-idea-generator` |
| `tools[0].name` | `generate_post_idea_batch` |
| `tools[0].module` | `content_idea_generator.run` |
| `tools[0].function` | `generate` |
| `safety.cost_limits.usd_per_session_max` | `0.30` |
| `safety.cost_limits.usd_per_day_max` | `1.00` |
| `safety.human_in_the_loop.enabled` | `true` |
| `constitution.hard_refusals[]` | auto-publish · finance · sponsorship · third-party-handles · scraping |

The full manifest is at `templates/creator/content-idea-generator/grok-agent.yaml`. The system prompt (Slot 1) is at `templates/creator/content-idea-generator/prompts/system.md`.

---

## v1 limitations

- No real-time X signal ingestion. The runner reads creator-supplied JSON files; pulls from xAI's public API are scheduled for a future version.
- No outbound network calls. Article VII of the project Constitution (local-first) takes precedence in v1.
- No automated publishing. Idea cards are drafts only.
- Voice profile influences interpretation, not score arithmetic, in v1. The full voice-distance computation lands when `brand-voice-trainer` v2 ships.

---

## Build slots (Recipe B)

| Slot | Status | Files |
|---|---|---|
| Slot 1 | ✅ shipped (P108 — supersedes the P12 starter manifest) | `grok-agent.yaml`, `prompts/system.md` |
| Slot 2 | ✅ shipped (P108) | `run.py`, `README.md`, `examples/` |

---

## License

Apache 2.0 — see the repository root `LICENSE` file. Every code and config file in this template carries an Apache 2.0 header.

> Built for X, Grok & the ecosystem community.
