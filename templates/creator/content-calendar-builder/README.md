<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Content Calendar Builder

> **Built for X, Grok & the ecosystem community.**
> Local-first content calendar builder for X creators. Reads creator-supplied cadence + niche + optional voice + analytics signals (or seeded demo signals) and emits a structured 7/8-section calendar with 4 canonical Calendar Plan Score metrics, the **over-scheduling paradox** surfaced in BOTH the Plan Score table AND Red Flags whenever it fires, the **format-streak guard** that flags ≥3 consecutive same-format slots, the **variety floor** that flags low format diversity, voice-drift candidates flagged inline, 4–12 weeks × 3–14 slots/week organised by week, and unconditional bridges to `analytics-summarizer` + `brand-voice-trainer` in every output.

> ⚠️ **No financial, cashtag, investment, sponsorship, or harassment content.** The runner errors out on forbidden tokens in any niche, archetype, or slot field.

> ⚠️ **Drafts only.** The runner emits a calendar the creator reviews before scheduling. It never auto-publishes or auto-schedules.

---

## What it is

A deterministic Python runner bound to a v2.15 `creator-template` manifest. Given a creator's X handle, cadence, and weeks, it produces a 7-section markdown calendar (8 sections when the Calendar Audit auto-triggers).

- **4 canonical Calendar Plan Score metrics** — Cadence sustainability / Niche fit / Voice fidelity / Variety, weights 0.30 / 0.25 / 0.25 / 0.20.
- **Over-scheduling paradox** dual-surface — when avg Cadence sustainability < 50 AND posts_per_week > 7, the paradox fires in BOTH the Plan Score table AND a high-severity Red Flag.
- **Format-streak guard** — ≥ 3 consecutive same-format slots → medium-severity Red Flag (slots stay in calendar, only flagged).
- **Variety floor** — below the configured `--variety-floor` distinct format types → medium-severity Red Flag.
- **Voice-drift surfacing** — slots with `voice_fidelity_score < 50` carry `⚠️ voice-drift candidate` inline AND trigger a Red Flag.
- **Mandatory bridges** — `analytics-summarizer` (position 1) + `brand-voice-trainer` (position 2).

---

## Quick launch (Windows 11 + PowerShell)

### Option A — over-scheduling paradox demo

```powershell
python .\templates\creator\content-calendar-builder\run.py `
    --x-handle JanSol0s `
    --demo
```

You'll see: 12 posts/week × 4 weeks = 48 slots; over-scheduling paradox active (Cadence sustainability 30, posts/week 12); 4 format streaks flagged; Calendar Audit auto-triggered.

### Option B — healthy demo

```powershell
python .\templates\creator\content-calendar-builder\run.py `
    --x-handle habitstacker `
    --demo-healthy
```

You'll see: 5 posts/week × 4 weeks = 20 slots; all metrics within healthy bands; no paradox; no streaks; no audit.

### Option C — single-week audit demo

```powershell
python .\templates\creator\content-calendar-builder\run.py `
    --x-handle thindata `
    --demo-7d-audit
```

You'll see: weeks=1 auto-triggers the Calendar Audit, medium confidence.

### Option D — real signals

```powershell
python .\templates\creator\content-calendar-builder\run.py `
    --x-handle JanSol0s `
    --niche "ai-agents" `
    --cadence-per-week 5 `
    --weeks 4 `
    --voice-profile-file .\my-voice.json `
    --analytics-file .\my-analytics.json `
    --variety-floor 4
```

Output to stdout by default. Add `--out cal.md` to write to file.

---

## Flag reference

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--x-handle` | string | required | Creator's X handle. |
| `--niche` | string | `general creator` | Free-text creator niche (max 80 chars). |
| `--cadence-per-week` | int | 5 | Posts per week, clamped to `[3, 14]`. |
| `--weeks` | int | 4 | Calendar horizon in weeks, clamped to `[1, 12]`. `1` auto-triggers Calendar Audit. |
| `--voice-profile-file` | path | (none) | brand-voice-trainer JSON. Influences interpretation in v1. |
| `--analytics-file` | path | (none) | analytics-summarizer JSON. Drives engagement priors in v1. |
| `--variety-floor` | int | 4 | Minimum distinct format types in the calendar (clamped to [2, 5]). |
| `--demo` | bool | false | Over-scheduling paradox demo (12 posts/week). |
| `--demo-healthy` | bool | false | All-within-bounds demo (5 posts/week). |
| `--demo-7d-audit` | bool | false | weeks=1 demo for Calendar Audit. |
| `--out` | path | (stdout) | Write calendar to file. |

---

## What the calendar looks like

The runner produces a slot for each post, organised by week:

```
### Week 1
1. **Mon · early-morning · single** — archetype: paraphrased label
   niche fit: 82/100 · voice fidelity: 80/100 · engagement: high
2. **Tue · late-morning · thread** — archetype: paraphrased label
   ...
```

Days distribute evenly across the week based on `cadence_per_week` (e.g. cadence=5 → Mon/Tue/Wed/Thu/Fri; cadence=7 → every day; cadence=12 → every day plus extras via time tiers). Time tiers cycle: `early-morning` → `late-morning` → `midday` → `afternoon` → `evening` → `late-evening`.

---

## Cross-template flow

```
                            +--------------------+
                            | content-calendar-  |
                            |    builder         |
                            +---|------------|---+
                                |            |
                    (mandatory) |            | (mandatory)
                                v            v
                  analytics-summarizer    brand-voice-trainer
                                |            (anchors voice)
                                | (next window measurement)
                                v
                       trend-aligned-poster (swap-in)
```

The mandatory upstream → `analytics-summarizer` (calendar slots become next-window measurement points). The mandatory downstream → `brand-voice-trainer` (voice anchors every slot). When the over-scheduling paradox fires, recommendations push to reduce cadence rather than push more variants.

---

## Where data lives

| Surface | Path |
|---|---|
| AppData root | `%LOCALAPPDATA%\grok-agent\content-calendar-builder\` |
| Cache | `%LOCALAPPDATA%\grok-agent\content-calendar-builder\cache\` |
| Logs | `%LOCALAPPDATA%\grok-agent\content-calendar-builder\logs\` |

---

## Examples

| File pair | Demo mode | What it shows |
|---|---|---|
| `sample-1-input.json` + `sample-1-output.md` | over-scheduling paradox | 12 posts/week × 4 weeks; paradox + format-streak guard |
| `sample-2-input.json` + `sample-2-output.md` | healthy | 5 posts/week × 4 weeks; healthy bands |
| `sample-3-input.json` + `sample-3-output.md` | weeks=1 audit | Single-week horizon; Calendar Audit auto-triggered |

---

## What the manifest declares

| Field | Value |
|---|---|
| `version` | `2.15` |
| `kind` | `creator-template` |
| `tools[0].name` | `generate_content_calendar` |
| `tools[0].module` | `content_calendar_builder.run` |
| `safety.cost_limits.usd_per_session_max` | `0.30` |
| `safety.cost_limits.usd_per_day_max` | `1.00` |
| `constitution.hard_refusals[]` | auto-publish · finance · sponsorship · third-party-handles · scraping · harassment-pattern slots |

---

## v1 limitations

- No real-time analytics ingestion. Reads creator-supplied JSON files.
- Voice profile influences interpretation, not score arithmetic.
- No outbound network calls.
- No automated scheduling.
- Cadence sustainability is creator-history-driven and supplied via `cadence_sustainability_seed` in demo / inferred from analytics in real data; the v1 heuristic is conservative.

---

## Build slots

| Slot | Status | Files |
|---|---|---|
| Slot 1 | ✅ shipped (P109) | `grok-agent.yaml`, `prompts/system.md` |
| Slot 2 | ✅ shipped (P109) | `run.py`, `README.md`, `examples/` |

---

## License

Apache 2.0.

> Built for X, Grok & the ecosystem community.
