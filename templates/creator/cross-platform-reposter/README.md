<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🔁 Cross-Platform Reposter

> Turn a single X post into 2-3 high-fidelity variants per target platform — LinkedIn, Threads, Bluesky, Newsletter — with 4 official Variant Score metrics, voice-drift paradox detection, and ≥3 cross-template bridges. Drafts only. Attribution always preserved.
>
> *Built for xAI, X, Grok and the ecosystem community the platform battle on X — every X creator deserves a cross-poster that respects their voice and their attribution, not an auto-publisher that flattens both.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template never publishes a variant to any platform. Every output is text the creator reviews and ships themselves. Constitution Article II's `publish_to_x` consent gate applies identically to LinkedIn / Threads / Bluesky / Newsletter — no sibling-platform auto-publish path exists in v1, period.

> 🔒 **Attribution always preserved.** Every variant ends with the verbatim attribution footer `— originally posted to X by @<handle> · <source URL or "see X feed for original">`. The creator may strip it before posting; the runner never strips it. The renderer's `_attribution_footer` function is the only place the footer is written, and it's grep-able for audit.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\cross-platform-reposter\`. The v1 runner makes zero external network calls — it is offline-safe.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches monetization tactics, paid-tier funnels, sponsored-content adaptation, or cross-platform paid placements.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a single X post (URL or pasted text) plus a target-platform list into a 6/7-section structured set of variants you can review and ship.

The report shape is the same every time:

1. **Source Snapshot** — one-sentence headline + 5-bullet summary of the X post
2. **Platform Variants** — 2-3 cards per requested platform, each with the 4-row Variant Score table (Voice fidelity / Platform fit / Engagement potential / Attribution clarity), the weighted Variant score `round(0.30·V + 0.30·P + 0.25·E + 0.15·A)`, the actual variant body inside a code-fence, and the verbatim attribution footer
3. **Platform Adaptations** — length / tone / hashtag posture / CTA shape per requested platform
4. **Engagement Tips** — 3-5 platform-aware shipping tips
5. **Red Flags** — 2-4 cards with severity, surfaces the **voice-drift paradox** in BOTH this section AND the relevant variant card when Platform fit > 70 AND Voice fidelity < 40
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges in `templates/creator/` (or `templates/general/` for `research-assistant`)
7. **Adaptation Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR target-platform count > 3

The voice-drift paradox is the headline insight this template exists for: a variant that's perfectly tuned to LinkedIn's engagement-bait conventions (multi-emoji opener, "comment AGREE below" CTA, 4 hashtags) but reads nothing like the creator's X voice will harvest reach in the short term and erode brand consistency over the long term. Surfacing it in two places — the variant card and the red flag — makes it impossible to ship by accident.

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\cross-platform-reposter\run.py --x-handle JanSol0s --demo --include-visual
```

That prints the 8-section report (4 platforms triggers Adaptation Audit) straight to your terminal, using the official demo source post that the system prompt's worked example references. Add `--no-banner` to suppress the runner banner if you want clean stdout for piping.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install cross-platform-reposter
```

### Option B — direct invocation (developer mode)

```powershell
# Standard 3-platform run with literal source text
python .\templates\creator\cross-platform-reposter\run.py `
  --x-handle JanSol0s `
  --post-url-or-text "Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness." `
  --target-platforms "linkedin,threads,newsletter" `
  --tone match-source `
  --include-visual

# URL-mode (runner is offline; falls back to URL-only attribution + placeholder body)
python .\templates\creator\cross-platform-reposter\run.py `
  --x-handle JanSol0s `
  --post-url-or-text "https://x.com/JanSol0s/status/1234567890" `
  --target-platforms "threads,bluesky"

# Save the report (Apache 2.0 HTML header is prepended automatically)
python .\templates\creator\cross-platform-reposter\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\cross-platform-reposter\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--post-url-or-text` | yes (or `--demo`) | Either an `x.com` URL or the literal post text |
| `--target-platforms` | optional | Comma-separated: `linkedin`, `threads`, `bluesky`, `newsletter`, `all` (default `all`) |
| `--tone` | optional | `match-source` \| `professional` \| `casual` \| `thoughtful` \| `punchy` (default `match-source`) |
| `--include-visual` | optional | Append a 1-line visual / image / chart suggestion per variant |
| `--demo` | optional | Use the official demo source post; LinkedIn variant 2 is pinned to the voice-drift paradox profile so the rule always demonstrates |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr (debugging) |

### Per-platform variant counts

| Platform | Variants | Why this count |
|---|---|---|
| LinkedIn | **3** | Most authoring leverage — high length budget allows three structurally distinct angles (pattern / engagement-bait / counter-take) |
| Threads | **3** | Three short variants ship cheaply; mobile-first audiences A/B-test by feel |
| Bluesky | **2** | 300-char ceiling caps useful variation at 2 |
| Newsletter | **2** | Long form is expensive to generate; 2 distinct shapes (extended section / case-study) cover the spread |

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** The runner emits text. It does not call any platform's publish API. It does not generate a "click here to post" URL. Constitution Article II's `publish_to_x` consent gate covers sibling platforms identically.
2. **Attribution always preserved.** Every variant ends with the footer `— originally posted to X by @<handle> · <source URL or "see X feed for original">`. The renderer never strips it. The creator may strip it manually before posting — that's their call, but the runner won't make it for them.
3. **Voice-drift paradox** must surface in BOTH the variant card AND the Red Flags section when Platform fit > 70 AND Voice fidelity < 40. The runner's `--demo` mode pins LinkedIn variant 2 to the paradox profile so this rule always demonstrates.
4. **Variant score formula is fixed.** `round(0.30·Voice fidelity + 0.30·Platform fit + 0.25·Engagement potential + 0.15·Attribution clarity)`. Voice + Platform tied at 0.30 each because either failing alone defeats the variant.
5. **≥3 distinct cross-template bridges** in the Recommendations list. Each bridge points to a real (or planned) template slug under `templates/creator/` (or `templates/general/` for `research-assistant`).
6. **Privacy guard.** The renderer's `assert_only_creator_handle_in_render` refuses to emit any output containing a plausibly-shaped `@handle` other than the creator's own. The runner has no concept of "competitors" or "other creators" — it adapts only the creator's own voice.

---

## Cross-template daily flow (Grok Agent OS for creators)

Cross-Platform Reposter is the distribution layer of the Grok Agent OS creator suite. The recommended weekly flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Tuesday — anchor X post lands                                    │
│  └─ thread-builder           → ship the long-form X post first    │
│       │                                                           │
│       └─ cross-platform-reposter → 2-3 variants per sibling platform │
│            │                                                      │
│            ├─ paradox flagged? → brand-voice-trainer to re-anchor │
│            ├─ attribution-eroded? → pin the X post for 48h        │
│            └─ monetization rec? → monetization-optimizer (V.1 gated) │
│                                                                   │
│  Wednesday — staggered ship                                       │
│  └─ content-calendar-builder → space ship times by 2-4 hours      │
│  └─ ship LinkedIn variant 1 first; hold variant 2 for A/B         │
│                                                                   │
│  Thursday — Threads + Bluesky                                     │
│  └─ ship Threads variant 1; reply within 30 min to first 5 replies│
│  └─ ship Bluesky variant 1; verify alt text                       │
│                                                                   │
│  Friday — Newsletter section                                      │
│  └─ ship newsletter variant; tease next-week follow-up            │
│                                                                   │
│  Following Tuesday — measure                                      │
│  └─ analytics-summarizer    → per-platform deltas vs anchor X post│
│  └─ ab-test-suggester       → graduate variant 1 → variant 3 if  │
│                                LinkedIn voice-fidelity holds      │
│                                                                   │
│  Monthly                                                          │
│  └─ content-recycler        → pull older anchors through the same │
│                                adaptation flow for compounding    │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next `python .\templates\creator\<slug>\run.py` (or `templates\general\<slug>` for `research-assistant`) command.

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `brand-voice-trainer` | `templates/creator/` | Re-anchor voice before pasting any variant — the only thing the runner can't repair after the fact is voice drift |
| `thread-builder` | `templates/creator/` | Build the long-form X anchor that this template adapts |
| `quote-tweet-suggestor` | `templates/creator/` | Riff on responses that come back from the cross-platform variants |
| `analytics-summarizer` | `templates/creator/` | Snapshot per-platform engagement at T+24h and T+7d |
| `content-calendar-builder` | `templates/creator/` | Stagger ship times across platforms (avoid same-window multi-post) |
| `content-recycler` | `templates/creator/` | Pull older niche-anchor X posts forward through this same flow |
| `content-idea-generator` | `templates/creator/` | Generate the next anchor post on the platform that responded best |
| `mention-summarizer` | `templates/creator/` | Roll up per-platform mentions after shipping; spot which platform converted to follow-on conversation |
| `monetization-optimizer` | `templates/creator/` | Model cross-platform paid-tier funnels (carries V.1 disclaimer) |
| `ab-test-suggester` | `templates/creator/` | Run an explicit A/B between variant 1 and variant 3 over a 2-week window |
| `competitor-watch` | `templates/creator/` | See which platforms competitors are winning on this week |
| `research-assistant` | `templates/general/` | Pull supporting evidence for the Newsletter variant |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\cross-platform-reposter\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\cross-platform-reposter\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\cross-platform-reposter\logs\` |
| System prompt | `templates\creator\cross-platform-reposter\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`, and the path is consent-gated by Constitution Article II if it's outside the AppData folder above.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_cross_platform_variants` (bound to `cross_platform_reposter.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, II, III, V, VII for cross-platform repost authoring
- **5 hard refusals**: auto-publish without consent gate; strip the attribution footer; claim platform-exclusivity; clone another creator's voice; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session (Article VI.1)
- **Human-in-the-loop**: enabled, 60-second timeout, confirm before exporting outside AppData (Article VI.2)
- **PII handling**: `local-only` (Article VII)
- **Data retention**: 90 days (auto-prune)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\cross-platform-reposter\grok-agent.yaml
python safety\scanner.py scan  templates\creator\cross-platform-reposter\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install. CI (`.github\workflows\validate.yml`) runs the same checks on every push and PR to `main`.

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × 4 platforms via `--demo`, `--include-visual` | All 4 platforms, 10 variants, LinkedIn variant 2 paradox, Adaptation Audit triggered by platform-count |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × 3 platforms, `match-source` tone | 3 platforms (no Bluesky), 8 variants, LinkedIn variant 2 paradox + Adaptation Audit triggered by red-flag-count |

Both demonstrate the voice-drift paradox surfaced in BOTH the variant card AND the Red Flags section, ≥3 distinct cross-template bridges in Recommendations, the verbatim attribution footer on every single variant body, and source-agnostic scaffolds that wrap the source text without leaking demo-content.

To regenerate either example deterministically, see the regenerate snippets at the top of each example file.

---

## v1 limitation note

The runner's variant scaffolds are **deterministic and source-agnostic** — they wrap the source text with platform-specific framing (e.g. "A pattern I keep seeing:" for LinkedIn, mobile-first phrasing for Threads, "When the proxy gets the attention the outcome should have had" for Newsletter), but they do not paraphrase the substance of the source. A future v2 with Grok 4.3 in the loop would generate fully paraphrased variants while preserving the same structure, scoring, and attribution invariants this v1 already enforces.

Until then, treat the variant body as a *scaffold* the creator polishes — the value the runner adds is:
1. The structure (4 metrics + weighted score + paradox detection)
2. The platform-specific adaptation notes
3. The verbatim attribution footer (preserved on every variant)
4. The cross-template bridges (≥3 distinct per output)
5. The deterministic seed (re-runnable for the same inputs)

---

## Build slots (Recipe B)

Cross-Platform Reposter follows the official Recipe B 2-prompt shape:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P71 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P72 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing distribution layer that turns "should I cross-post this?" from a one-shot decision into a structured weekly habit — without flattening voice, without losing attribution, and without auto-publishing anywhere.
