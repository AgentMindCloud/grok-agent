<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🎙️ Brand Voice Trainer

> Read a sample of your own past X posts and emit a structured voice profile + 3-5 training prompts you can paste into other Grok Agent OS templates. 4 official Voice Profile metrics, generic-polish paradox detection, sample-size double gate, ≥3 cross-template bridges. Drafts only. Trains only on your own voice.
>
> *Built for xAI, X, Grok and the ecosystem community — winning the platform battle on X. Every X creator deserves a trainer that sharpens their voice instead of flattening it into niche-default.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** Training prompts emitted by this template are text the creator pastes into other templates (`content-idea-generator`, `thread-builder`, `cross-platform-reposter`, `content-recycler`, `reply-drafter`). The runner never auto-applies, never auto-publishes.

> 🔒 **Trains only on the creator's own voice.** Sample posts must be authored by the `--x-handle` creator. The system prompt does not adapt another creator's voice — that's `niche-influencer-finder`'s problem space, not this one's.

> 🔒 **Sample-size double gate.** Below 5 posts the runner refuses to score (no profile emitted). Below 10 posts the runner emits the profile + an auto-appended Voice Audit section that flags sample reliability. At 10+ posts the runner emits the full report.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\brand-voice-trainer\`. The v1 runner makes zero external network calls — it is offline-safe.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any training prompt or recommendation that touches monetization tactics, paid-tier funnel voice, or sponsorship adaptation.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a sample of the creator's own past posts into a 6/7-section structured voice profile + a paste-able training-prompt set.

The report shape is the same every time:

1. **Voice Snapshot** — one-sentence summary + 5-bullet metadata
2. **Voice Profile** — 4-row metric table (Tone consistency / Structure consistency / Vocabulary distinctiveness / Voice cohesion) + weighted Voice Profile score `round(0.30·Tone + 0.20·Structure + 0.25·Vocabulary + 0.25·Cohesion)`
3. **Voice Signatures** — Tone / Structure / Vocabulary subsections; signature phrases extracted as verbatim n-grams from the sample (never invented)
4. **Training Prompts** — 3-5 prompts, each naming a destination cross-template slug; the creator pastes each into the named runner
5. **Red Flags** — 2-4 cards with severity, surfaces the **generic-polish paradox** in BOTH this section AND under the Voice Profile metric row when Voice cohesion > 70 AND Vocabulary distinctiveness < 35
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges
7. **Confidence** — `high | medium | low`
8. **Voice Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR sample size < 10

The generic-polish paradox is the headline insight this template exists for: a creator whose posts are tonally consistent (everyone-sounds-the-same is internally coherent) but use the niche's default vocabulary (`thought leadership`, `ecosystem`, `synergy`, `leverage`, `transform`, `scale`) is polished without being differentiated. Surfacing it in two places — the metric table and the red flag — makes it impossible to miss.

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\brand-voice-trainer\run.py --x-handle JanSol0s --demo
```

That prints the 7-section report (24 deliberately generic-polish posts pinned to the paradox profile) straight to your terminal. Add `--no-banner` to suppress the runner banner.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install brand-voice-trainer
```

### Option B — direct invocation (developer mode)

```powershell
# Train on a real sample of your own posts via inline list (separator: ||)
python .\templates\creator\brand-voice-trainer\run.py `
  --x-handle JanSol0s `
  --sample-posts "Post 1 text...||Post 2 text...||...||Post 30 text..." `
  --voice-focus all `
  --output-format both

# Train from a file (one post per block, separated by blank lines or ---)
python .\templates\creator\brand-voice-trainer\run.py `
  --x-handle JanSol0s `
  --sample-file $env:LOCALAPPDATA\grok-agent\brand-voice-trainer\my-posts.txt `
  --voice-focus vocabulary `
  --output-format both

# Productivity demo (8 posts → triggers Voice Audit auto-section)
python .\templates\creator\brand-voice-trainer\run.py `
  --x-handle habitstacker `
  --demo-productivity

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\brand-voice-trainer\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\brand-voice-trainer\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--sample-posts` | yes (or `--sample-file` / `--date-range` / `--demo` / `--demo-productivity`) | Inline post bodies separated by `\|\|` or two newlines |
| `--sample-file` | yes (alt) | Path to a file with posts separated by blank lines or `---` (lines starting with `#` ignored) |
| `--date-range` | yes (alt) | ISO date range used as deterministic seed when no inline sample is provided |
| `--voice-focus` | optional | `tone` \| `structure` \| `vocabulary` \| `all` (default `all`) |
| `--output-format` | optional | `analysis` \| `training_prompts` \| `both` (default `both`) |
| `--demo` | optional | Use the official 24-post generic-polish demo sample (paradox-pinned) |
| `--demo-productivity` | optional | Use the 8-post productivity demo sample (Voice Audit-triggered) |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr (debugging) |

---

## How the report is shaped (the 6 hard rules)

1. **Train only on the creator's own voice.** The runner's contract is unambiguous: sample posts authored by `--x-handle` only. The system prompt does not adapt another creator's voice.
2. **Drafts only.** Training prompts are text the creator pastes into other templates. Never include a `publish` action, an "auto-apply" command, or any instruction the runner could execute itself.
3. **Sample-size double gate.** Refuse outright on `< 5` posts (no profile emitted, just a refusal card). Auto-trigger Voice Audit on `< 10` posts (profile emitted with explicit caveats). Full report at `>= 10` posts.
4. **Generic-polish paradox** must surface in BOTH the Voice Profile section AND the Red Flags section when Voice cohesion > 70 AND Vocabulary distinctiveness < 35. The runner's `--demo` mode pins scoring to this profile so the rule reliably demonstrates.
5. **No fabricated signatures.** The Vocabulary subsection reports phrases observed in the sample (verbatim n-grams that occur in 2+ posts). Never invent quotes the creator did not use.
6. **Voice Profile score formula is fixed.** `round(0.30·Tone consistency + 0.20·Structure consistency + 0.25·Vocabulary distinctiveness + 0.25·Voice cohesion)`. Tone weighted highest because tone-drift is the visible kind of voice drift; Structure weighted lowest because structure repeats naturally even when voice fragments.

---

## Cross-template daily flow (Grok Agent OS for creators)

Brand Voice Trainer is the voice-anchoring layer of the Grok Agent OS creator suite. The recommended monthly flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Monthly — voice baseline                                         │
│  └─ analytics-summarizer    → pull 30 most-engaged posts          │
│       │                                                           │
│       └─ brand-voice-trainer → emit voice profile + training      │
│            │                    prompts                           │
│            │                                                      │
│            ├─ paradox flagged? → lock 2-3 signature phrases over  │
│            │                     next 30 posts                    │
│            ├─ sample < 10?     → use Voice Audit + scale sample   │
│            └─ healthy profile? → paste training prompts into      │
│                                  destination templates            │
│                                                                   │
│  Per-anchor — apply trained voice                                 │
│  └─ content-idea-generator  → next anchor in trained voice        │
│  └─ thread-builder          → thread in trained voice             │
│  └─ cross-platform-reposter → cross-post preserving voice         │
│  └─ content-recycler        → recycle preserving voice            │
│                                                                   │
│  Per-week — voice maintenance                                     │
│  └─ ab-test-suggester       → A/B voice-faithful vs voice-drift   │
│  └─ competitor-watch        → spot signatures vs niche-default    │
│                                                                   │
│  Per-quarter — re-train                                           │
│  └─ brand-voice-trainer     → re-run on the latest 30 posts;      │
│                                watch the trend arrows             │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>`, and every Training Prompt is explicitly headed `For \`<slug>\`:` so you can paste-and-go.

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `content-idea-generator` | `templates/creator/` | Use the trained voice to seed the next anchor post |
| `thread-builder` | `templates/creator/` | Build long-form threads in the trained voice |
| `cross-platform-reposter` | `templates/creator/` | Preserve voice when adapting across platforms |
| `content-recycler` | `templates/creator/` | Preserve voice when recycling old posts |
| `reply-drafter` | `templates/creator/` | Draft replies in voice rather than generic-helpful |
| `mention-summarizer` | `templates/creator/` | Filter inbound mentions by voice fit |
| `ab-test-suggester` | `templates/creator/` | A/B-test voice-faithful vs voice-drift variants |
| `competitor-watch` | `templates/creator/` | Compare signatures against competitors' to spot gaps |
| `quote-tweet-suggestor` | `templates/creator/` | Suggest voice-faithful quote-tweet lines |
| `monetization-optimizer` | `templates/creator/` | Tune monetization-content voice (carries V.1 disclaimer) |
| `analytics-summarizer` | `templates/creator/` | Snapshot voice-distinctive vs voice-drift posts |
| `research-assistant` | `templates/general/` | Background on voice influences when expanding lexicon |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\brand-voice-trainer\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\brand-voice-trainer\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\brand-voice-trainer\logs\` |
| System prompt | `templates\creator\brand-voice-trainer\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_voice_profile` (bound to `brand_voice_trainer.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, II, III, V, VII for voice training
- **5 hard refusals**: train on another creator's posts; auto-apply training prompts; fabricate signature phrases; score samples below the 5-post floor; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\brand-voice-trainer\grok-agent.yaml
python safety\scanner.py scan  templates\creator\brand-voice-trainer\grok-agent.yaml
```

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × `--demo` (24 generic-polish posts) | Generic-polish paradox firing — Cohesion high, Distinctiveness low |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × `--demo-productivity` (8 posts) | Voice Audit auto-triggered — sample size below the 10-post audit threshold |

Together the two examples cover the full surface of the template's edge cases:
- Paradox firing (AI demo)
- Sample-gate firing (productivity demo)
- Tiny-sample refusal (sample < 5; not shown in either example, but exercised by the runner's hard floor)

To regenerate either example deterministically, see the regenerate snippets at the top of each example file.

---

## v1 limitation note

The runner's signature-extraction is purely **deterministic n-gram analysis** (no LLM in v1). Verbatim phrases are real (extracted from the sample as recurring 2-4-word n-grams), but tone-tells and structure-shapes are derived from heuristic regex/length analysis rather than semantic understanding. A future v2 with Grok 4.3 in the loop would generate richer signatures while preserving the same scoring, paradox detection, sample-gate, and own-voice-only invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric scoring with weighted formula
2. The deterministic n-gram extraction (signature phrases are real, not invented)
3. The generic-polish paradox detection
4. The sample-size double gate (5 / 10 thresholds)
5. The training prompts (each named for a destination template slug)
6. The deterministic seed (re-runnable for the same inputs)

---

## Build slots (Recipe B)

Brand Voice Trainer follows the official Recipe B 2-prompt shape:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P75 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P76 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing voice-anchoring layer that turns "do I sound like myself?" from a feel into a structured monthly habit — without flattening voice, without inventing phrases, and without auto-applying anywhere.
