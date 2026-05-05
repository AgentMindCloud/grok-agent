<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Reply Drafter

> **Built for X, Grok & the ecosystem community.**
> Local-first reply drafter for X creators. Reads creator-supplied mention data (or seeded demo mentions) plus an optional voice profile, and emits a structured 7/8-section reply plan with 4 canonical Reply Plan Score metrics, the **helpful-but-off-voice paradox** surfaced in BOTH the Plan Score table AND Red Flags whenever it fires, the **risk-exclude guard** that keeps unsafe drafts out of the plan, voice-drift candidates flagged inline, 4–6 production-quality reply drafts, and unconditional bridges to `brand-voice-trainer` + `mention-summarizer` in every output.

> ⚠️ **Drafts only — auto-publish is not implemented.**
> The manifest declares `real_time_x.posts: true` as a **future-version capability flag** so the template appears in real-time-X catalog filters. The v1 runner is **offline draft-generation only** — it consumes a `mentions_file` and emits markdown drafts. Auto-publish is hard-gated by the constitution and has no implementation path in v1.

> ⚠️ **No financial, cashtag, investment, sponsorship, or harassment content.** This template refuses to generate replies in any of these categories. The runner errors out with a forbidden-token message if any mention paraphrase or draft outline contains a cashtag (e.g. `$TSLA`), the words `invest`/`portfolio`/`hedge`, `sponsor`/`#ad`, or `harass`/`defame`/`dox`/`slur`-pattern terms.

> ⚠️ **No impersonation.** Drafts speak in the creator's voice. The runner refuses any third-party @-handle in paraphrased fields and any URL — both are privacy leaks that would expose the mention author or third parties.

---

## What it is

A deterministic Python runner bound to a v2.15 `creator-template` manifest. Given a creator's X handle plus an optional JSON mentions file (and optional voice profile), it produces a 7-section markdown plan (8 sections when the Reply Audit auto-triggers). Every output ships with:

- **4 canonical Reply Plan Score metrics** — Voice fidelity / Substance / Tone calibration / Risk avoidance, with the fixed weighted formula `round(0.30·Voice + 0.25·Substance + 0.25·Tone + 0.20·Risk)` over healthy-range-normalised sub-scores.
- **Helpful-but-off-voice paradox** dual-surface rule — when avg Substance > 70 AND avg Voice fidelity < 55, the paradox fires in BOTH the Plan Score table AND a high-severity Red Flag.
- **Risk-exclude guard** — any individual draft with `risk_avoidance_score < 40` (configurable via `--risk-floor`) is excluded from the Drafts section and consolidated into a single Red Flag titled `High-risk drafts excluded`.
- **Voice-drift surfacing** — drafts with `voice_fidelity_score < 50` stay in the plan but carry `⚠️ voice-drift candidate` inline AND trigger a Red Flag titled `Voice-drift candidates surfaced` (severity `medium`).
- **Mandatory bridges** — every output's Recommendations list includes at least one bridge to `brand-voice-trainer` (position 1) and one to `mention-summarizer` (position 2).
- **5-arrow trend vocabulary** — `▲▲ ▲ ▬ ▼ ▼▼` for every metric vs the previous-period baseline.
- **Demo labels** — when no `--mentions-file` is supplied, the runner seeds explicit demo data marked `[demo reply — re-run with --mentions-file / --voice-profile-file for real X data]` on every metric.

---

## Quick launch (Windows 11 + PowerShell)

### Option A — paradox-firing demo (recommended first run)

```powershell
python .\templates\creator\reply-drafter\run.py `
    --x-handle JanSol0s `
    --demo
```

You'll see: paradox firing (avg Substance 74.1, avg Voice fidelity 48.6), 2 high-risk drafts excluded, 2 voice-drift candidates flagged inline, Reply Audit auto-triggered, all 7 mandatory plan sections plus the audit (8 total).

### Option B — healthy demo

```powershell
python .\templates\creator\reply-drafter\run.py `
    --x-handle habitstacker `
    --demo-healthy
```

You'll see: all metrics inside healthy bands, no paradox, no exclusions, no audit (7-section output).

### Option C — 7d-window audit demo

```powershell
python .\templates\creator\reply-drafter\run.py `
    --x-handle thindata `
    --demo-7d-audit
```

You'll see: window=7d auto-triggers the Reply Audit, medium-confidence label.

### Option D — real X mentions + voice profile

```powershell
python .\templates\creator\reply-drafter\run.py `
    --x-handle JanSol0s `
    --mentions-file .\my-mentions.json `
    --voice-profile-file .\my-voice.json `
    --max-drafts 5 `
    --window 30
```

Output goes to stdout by default. Add `--out plan.md` to write a markdown file with the Apache 2.0 HTML-comment header pre-pended.

---

## Flag reference

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--x-handle` | string | required | Creator's X handle, with or without `@`. Privacy anchor — only this handle appears in the output. |
| `--mentions-file` | path | (none) | Local JSON path. Schema mirrors mention-summarizer's input. |
| `--voice-profile-file` | path | (none) | Local JSON path from brand-voice-trainer. Influences interpretation only in v1. |
| `--max-drafts` | int | 5 | Target draft count, clamped to `[4, 6]`. |
| `--window` | int | 30 | One of 7 / 30 / 90. `7` auto-triggers the Reply Audit section. |
| `--risk-floor` | float | 40.0 | Below this risk_avoidance_score, drafts are excluded. |
| `--demo` | bool | false | Helpful-but-off-voice paradox + risk-exclude guard demo. |
| `--demo-healthy` | bool | false | All-within-bounds seeded data. |
| `--demo-7d-audit` | bool | false | 7d window seeded data that auto-triggers Reply Audit. |
| `--out` | path | (stdout) | Write plan to file. The Apache 2.0 HTML-comment header is prepended automatically. |

---

## `--mentions-file` schema (mirrors mention-summarizer)

```jsonc
{
  "x_handle": "@JanSol0s",
  "window": 30,
  "data_source": "real",
  "mentions": [
    {
      "id": "m-001",
      "paraphrased_excerpt": "asks for the eval-framework setup that surfaced the agent regression",
      "sentiment": "positive",
      "intent": "question",
      "priority_score": 92,
      "author_followers": 12000
    }
  ],
  "candidate_drafts": [
    {
      "mention_id": "m-001",
      "format": "single",
      "draft_outline": "share the exact setup with a one-line caveat about edge-case behaviour",
      "voice_fidelity_score": 78,
      "substance_score": 82,
      "tone_calibration_score": 75,
      "risk_avoidance_score": 90
    }
  ],
  "previous_window_summary": {
    "avg_voice_fidelity_score": 70.0,
    "avg_substance_score": 70.0,
    "avg_tone_calibration_score": 75.0,
    "avg_risk_avoidance_score": 88.0
  }
}
```

### Field constraints

- `sentiment`: one of `positive` / `neutral` / `negative`
- `intent`: one of `question` / `praise` / `criticism` / `promotion-attempt` / `collaboration-ask` / `general`
- `format`: one of `single` / `thread-reply` (only — no quote-tweet / image-post / reply-thread for this template)
- All scores: 0–100 numeric
- `paraphrased_excerpt`: max 80 chars; **no third-party @-handles, no URLs**
- `priority_score` is optional — when omitted, the runner derives it from `(intent_weight × 0.6) + (author_followers_norm × 0.4)`

The runner refuses any mention or draft that contains forbidden tokens, third-party @-handles in paraphrased fields, or URLs — these are hard refusals.

---

## How the plan is shaped (6 hard rules from the system prompt)

1. **Drafts only** — the runner emits text the creator reads; never an auto-publish action. v1 has no implementation path for auto-publish.
2. **Never impersonate** — drafts speak in the creator's voice and never claim to be the mention author or any third party.
3. **No fabricated statistics** — demo metrics carry the `[demo reply — re-run with --mentions-file / --voice-profile-file for real X data]` label.
4. **Helpful-but-off-voice paradox dual-surface** — when avg Substance > 70 AND avg Voice fidelity < 55, the paradox appears in BOTH the Plan Score table AND a high-severity Red Flag.
5. **Risk-exclude guard is non-negotiable** — `risk_avoidance_score < 40` excludes the draft from the Drafts section AND surfaces a Red Flag.
6. **Unconditional bridges** — every Recommendations list includes at least `brand-voice-trainer` (position 1) and `mention-summarizer` (position 2).

---

## Cross-template daily flow

```
                    +-------------------+
                    | mention-summarizer|   (priority queue)
                    +----------|--------+
                               | feeds the mention queue
                               v
                    +-------------------+
                    |  reply-drafter    |
                    +---|------|--------+
                        |      |
            (mandatory) |      | (mandatory)
                        v      v
            brand-voice-trainer  mention-summarizer (next window)
                        |
                        v
              re-anchored drafts → publish
```

The mandatory bridge from `mention-summarizer` UP into reply-drafter (it provides the priority queue) and the mandatory bridge from reply-drafter back DOWN to `brand-voice-trainer` (every draft is voice-checked) form the core safety loop. The runner enforces both.

---

## Where data lives (Windows paths)

| Surface | Path |
|---|---|
| AppData root | `%LOCALAPPDATA%\grok-agent\reply-drafter\` |
| Cache | `%LOCALAPPDATA%\grok-agent\reply-drafter\cache\` |
| Logs | `%LOCALAPPDATA%\grok-agent\reply-drafter\logs\` |

The runner does not write to these paths in v1.

---

## Examples

| File pair | Demo mode | What it shows |
|---|---|---|
| `sample-1-input.json` + `sample-1-output.md` | paradox-firing | Helpful-but-off-voice paradox active + 2 high-risk drafts excluded + 2 voice-drift candidates + Reply Audit auto-triggered |
| `sample-2-input.json` + `sample-2-output.md` | healthy | All metrics within bounds + no paradox + no exclusions + no audit |
| `sample-3-input.json` + `sample-3-output.md` | 7d-audit | window=7d auto-triggers the Reply Audit + medium confidence |

---

## What the manifest declares

| Manifest field | Value |
|---|---|
| `version` | `2.15` |
| `kind` | `creator-template` |
| `windows.appdata_folder` | `grok-agent/reply-drafter` |
| `tools[0].name` | `generate_reply_drafts` |
| `tools[0].module` | `reply_drafter.run` |
| `tools[0].function` | `generate` |
| `real_time_x.posts` | `true` (future-version capability flag — v1 is offline-only) |
| `safety.cost_limits.usd_per_session_max` | `0.30` |
| `safety.cost_limits.usd_per_day_max` | `1.00` |
| `safety.human_in_the_loop.enabled` | `true` |
| `constitution.hard_refusals[]` | auto-publish · finance · sponsorship · harassment · third-party-handles · impersonation · scraping |

The full manifest is at `templates/creator/reply-drafter/grok-agent.yaml`. The system prompt (Slot 1) is at `templates/creator/reply-drafter/prompts/system.md`.

---

## v1 limitations

- **No auto-publish.** `real_time_x.posts: true` in the manifest is a future-version capability flag. v1 has no implementation.
- **No real-time mention listening.** v1 reads from a `mentions_file`; pulls from xAI's public API are scheduled for a future version.
- **Voice profile influences interpretation, not score arithmetic, in v1.** The full voice-distance computation lands when `brand-voice-trainer` v2 ships.
- **No outbound network calls.** Article VII of the project Constitution (local-first) takes precedence in v1.

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
