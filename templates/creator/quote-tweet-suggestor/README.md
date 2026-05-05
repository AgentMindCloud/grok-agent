<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Quote-Tweet Suggestor

> **Built for X, Grok & the ecosystem community.**
> Local-first quote-tweet suggestor for X creators. Reads a creator-supplied source post (or seeded demo source) and emits a structured 7/8-section variant plan with 4 canonical Quote-Tweet Plan Score metrics, the **dunk-bait paradox** surfaced in BOTH the Plan Score table AND Red Flags whenever it fires, the **risk-exclude guard** that keeps unsafe variants out of the plan, voice-drift candidates flagged inline, 4–6 production-quality quote-tweet variants, and unconditional bridges to `brand-voice-trainer` + `content-idea-generator` in every output.

> ⚠️ **No financial, cashtag, investment, sponsorship, harassment, or dunk-bait content.** This template refuses to generate quote-tweets in any of these categories. The runner errors out on forbidden tokens (cashtag patterns, `invest`/`portfolio`, `sponsor`/`#ad`, harassment-pattern terms) and on third-party @-handles or URLs in any paraphrased field.

> ⚠️ **No impersonation.** Variants speak in the creator's voice. The runner refuses any variant that claims to be the source-post author.

> ⚠️ **Drafts only.** The runner emits a plan the creator reads before posting. It never auto-publishes.

---

## What it is

A deterministic Python runner bound to a v2.15 `creator-template` manifest. Given a creator's X handle plus a JSON source-post file (and optional voice profile), it produces a 7-section markdown plan (8 sections when the Variant Audit auto-triggers).

- **4 canonical Quote-Tweet Plan Score metrics** — Source-fit / Voice fidelity / Originality / Engageability, weights 0.30 / 0.25 / 0.25 / 0.20.
- **Dunk-bait paradox** dual-surface — when avg Engageability > 70 AND avg Source-fit < 40, the paradox fires in BOTH the Plan Score table AND a high-severity Red Flag.
- **Risk-exclude guard** — variants with `risk_avoidance_score < 40` (configurable via `--risk-floor`) are excluded and surfaced as a single Red Flag.
- **Voice-drift surfacing** — variants with `voice_fidelity_score < 50` carry `⚠️ voice-drift candidate` inline AND trigger a Red Flag.
- **Mandatory bridges** — `brand-voice-trainer` (position 1) and `content-idea-generator` (position 2).
- **5-arrow vocabulary** — `▲▲ ▲ ▬ ▼ ▼▼` against the previous-window baseline.
- **Demo labels** — `[demo variant — re-run with --source-post-file / --voice-profile-file for real X data]`.

---

## Quick launch (Windows 11 + PowerShell)

### Option A — paradox-firing demo

```powershell
python .\templates\creator\quote-tweet-suggestor\run.py `
    --x-handle JanSol0s `
    --demo
```

You'll see: dunk-bait paradox active (Engageability 78.3, Source-fit 29.7), 2 high-risk variants excluded, Variant Audit auto-triggered, all 8 sections.

### Option B — healthy demo

```powershell
python .\templates\creator\quote-tweet-suggestor\run.py `
    --x-handle habitstacker `
    --demo-healthy
```

You'll see: all metrics inside healthy bands, no paradox, no exclusions, no audit.

### Option C — 7d-window audit demo

```powershell
python .\templates\creator\quote-tweet-suggestor\run.py `
    --x-handle thindata `
    --demo-7d-audit
```

You'll see: window=7d auto-triggers the Variant Audit, medium confidence.

### Option D — real source post

```powershell
python .\templates\creator\quote-tweet-suggestor\run.py `
    --x-handle JanSol0s `
    --source-post-file .\my-source.json `
    --voice-profile-file .\my-voice.json `
    --max-variants 5 `
    --window 30
```

Output goes to stdout by default. Add `--out plan.md` to write a markdown file with the Apache 2.0 HTML-comment header pre-pended.

---

## Flag reference

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--x-handle` | string | required | Creator's X handle, with or without `@`. |
| `--source-post-file` | path | (none) | Local JSON path. Schema below. |
| `--voice-profile-file` | path | (none) | Local JSON from brand-voice-trainer. Influences interpretation only in v1. |
| `--max-variants` | int | 5 | Clamped to `[4, 6]`. |
| `--window` | int | 30 | One of 7 / 30 / 90. `7` auto-triggers the Variant Audit. |
| `--risk-floor` | float | 40.0 | Below this risk_avoidance_score, variants are excluded. |
| `--demo` | bool | false | Dunk-bait paradox + risk-exclude demo. |
| `--demo-healthy` | bool | false | All-within-bounds seeded data. |
| `--demo-7d-audit` | bool | false | 7d-window seeded data. |
| `--out` | path | (stdout) | Write plan to file. |

---

## `--source-post-file` schema

```jsonc
{
  "x_handle": "@JanSol0s",
  "window": 30,
  "data_source": "real",
  "source": {
    "paraphrased_excerpt": "paraphrased pitch of an open-source agent eval framework",
    "source_topic": "agent-eval-framework",
    "source_sentiment": "positive",
    "source_intent": "commentary",
    "source_argument": "the new framework lowers the eval-cost bar for indie agent builders"
  },
  "candidate_variants": [
    {
      "format": "thread-quote",
      "stance": "agree-and-extend",
      "copy_outline": "extend the framework with the creator's own measurement protocol",
      "source_fit_score": 88,
      "voice_fidelity_score": 86,
      "originality_score": 78,
      "engageability_score": 70,
      "risk_avoidance_score": 95
    }
  ],
  "previous_window_summary": {
    "avg_source_fit_score": 70.0,
    "avg_voice_fidelity_score": 72.0,
    "avg_originality_score": 65.0,
    "avg_engageability_score": 70.0
  }
}
```

### Field constraints

- `source_sentiment`: `positive` / `neutral` / `negative`
- `source_intent`: `commentary` / `question` / `call-to-action` / `personal-update` / `data-share` / `general`
- `format`: `single-quote` / `thread-quote` only
- `stance`: `agree-and-extend` / `disagree-and-explain` / `reframe` / `add-data` / `personal-reaction`
- All scores: 0–100 numeric
- `paraphrased_excerpt` capped at 120 chars; **no third-party @-handles, no URLs**

---

## Cross-template flow

```
            +-------------------+
            | source post (X)   |
            +---------|---------+
                      | paraphrased
                      v
            +-------------------+
            | quote-tweet-      |
            |   suggestor       |
            +---|-----|---------+
                |     |
    (mandatory) |     | (mandatory)
                v     v
brand-voice-trainer  content-idea-generator
                |
                v
         publish-ready variants
```

When the dunk-bait paradox fires or the risk guard excludes variants, the recommendations route the creator to **content-idea-generator** for a standalone post — explicitly avoiding the quote-tweet altogether when the source-fit floor cannot be met.

---

## Where data lives

| Surface | Path |
|---|---|
| AppData root | `%LOCALAPPDATA%\grok-agent\quote-tweet-suggestor\` |
| Cache | `%LOCALAPPDATA%\grok-agent\quote-tweet-suggestor\cache\` |
| Logs | `%LOCALAPPDATA%\grok-agent\quote-tweet-suggestor\logs\` |

---

## Examples

| File pair | Demo mode | What it shows |
|---|---|---|
| `sample-1-input.json` + `sample-1-output.md` | paradox-firing | Dunk-bait paradox + 2 high-risk variants excluded + Variant Audit |
| `sample-2-input.json` + `sample-2-output.md` | healthy | All within bounds, 7-section output |
| `sample-3-input.json` + `sample-3-output.md` | 7d-audit | Variant Audit auto-triggered |

---

## What the manifest declares

| Field | Value |
|---|---|
| `version` | `2.15` |
| `kind` | `creator-template` |
| `tools[0].name` | `generate_quote_tweet_variants` |
| `tools[0].module` | `quote_tweet_suggestor.run` |
| `safety.cost_limits.usd_per_session_max` | `0.30` |
| `safety.cost_limits.usd_per_day_max` | `1.00` |
| `constitution.hard_refusals[]` | auto-publish · finance · sponsorship · harassment · dunk-bait · third-party-handles · impersonation · scraping |

---

## v1 limitations

- No real-time mention/source ingestion. v1 reads from a `source_post_file`.
- Voice profile influences interpretation, not score arithmetic, in v1.
- No outbound network calls.
- No automated publishing.

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
