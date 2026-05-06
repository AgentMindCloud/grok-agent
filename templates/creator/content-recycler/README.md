<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# ♻️ Content Recycler

> Turn an old X post you authored into 2-3 high-quality variants tuned to a chosen format (tweet / thread / carousel / newsletter / all) under a chosen recycle angle (update / expand / threadify / repurpose / auto). 4 official Recycle Score metrics, stale-rehash paradox detection, ≥3 cross-template bridges. Drafts only. Attribution stamp always preserved.
>
> *Built for xAI, X, Grok and the ecosystem community the platform battle on X — every X creator deserves a recycler that compounds their back catalog without copy-pasting them.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template never publishes a variant to any platform. Every output is text the creator reviews and ships themselves. Constitution Article II's `publish_to_x` consent gate covers every variant.

> 🔒 **Recycle only your own content.** When the source is supplied as an `x.com` URL whose handle does not match `--x-handle`, the runner **refuses** the run and emits a 3-section guidance card. Recycling another account's content is impersonation by another name.

> 🔒 **Attribution stamp preserved.** Every variant ends with the verbatim stamp `— originally posted on X by @<handle> on <date> · recycled <today>`. The renderer's `_recycle_stamp` function is the only place the stamp is written, and it never strips it. The creator may strip it manually before posting; the runner never makes that choice for them.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\content-recycler\`. The v1 runner makes zero external network calls — it is offline-safe.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches monetization tactics, paid-tier funnel recycling, or sponsorship adaptation.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a single old X post (URL or pasted text) plus a recycle angle and target format into a 6/7-section structured set of recycled variants you can review and ship.

The report shape is the same every time:

1. **Source Snapshot** — one-sentence headline + 6-bullet summary including the original post date
2. **Recycle Angle Analysis** — chosen angle / why-it-fits / what-changes / what-stays
3. **Recycled Variants** — 2-3 cards per single format (or 4 — one per format — when `target_format=all`), each with the 4-row Recycle Score table (Freshness lift / Format fit / Engagement potential / Differentiation), the weighted Recycle score `round(0.30·F + 0.25·Fmt + 0.25·E + 0.20·D)`, the variant body inside a code-fence, and the verbatim attribution stamp
4. **Engagement Prediction** — predicted lift vs static repost + best-case + worst-case drivers
5. **Red Flags** — 2-4 cards with severity, surfaces the **stale-rehash paradox** in BOTH this section AND the relevant variant card when Format fit > 70 AND Freshness lift < 35
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges
7. **Recycle Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR target_format='all'

The stale-rehash paradox is the headline insight this template exists for: a variant that's perfectly tuned to a format (8-slide carousel, 5-post thread, 1500-word newsletter section) but adds no new value vs the original is a re-publish, not a recycle. Surfacing it in two places makes it impossible to ship by accident.

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\content-recycler\run.py --x-handle JanSol0s --demo --target-format thread
```

That prints the 7-section report (3 thread variants — variant 2 pinned to the stale-rehash paradox profile) straight to your terminal.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install content-recycler
```

### Option B — direct invocation (developer mode)

```powershell
# Single-format thread recycle with explicit angle
python .\templates\creator\content-recycler\run.py `
  --x-handle JanSol0s `
  --old-post-url-or-text "Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness." `
  --recycle-angle expand `
  --target-format thread `
  --original-post-date 2025-09-12

# All formats — generates one variant per format (tweet / thread / carousel / newsletter)
python .\templates\creator\content-recycler\run.py `
  --x-handle JanSol0s `
  --demo `
  --target-format all

# URL-mode (the runner verifies handle match; refuses on mismatch)
python .\templates\creator\content-recycler\run.py `
  --x-handle JanSol0s `
  --old-post-url-or-text "https://x.com/JanSol0s/status/1234567890" `
  --recycle-angle update

# Save the report (Apache 2.0 HTML header is prepended automatically)
python .\templates\creator\content-recycler\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\content-recycler\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`). Must match the source-post handle when supplied as URL — otherwise the run is refused. |
| `--old-post-url-or-text` | yes (or `--demo`) | Either an `x.com` URL or the literal post text |
| `--recycle-angle` | optional | `update` \| `expand` \| `threadify` \| `repurpose` \| `auto` (default `auto` — runner picks) |
| `--target-format` | optional | `tweet` \| `thread` \| `carousel` \| `newsletter` \| `all` (default `thread`) |
| `--original-post-date` | optional | ISO date (`YYYY-MM-DD`); preserved in the attribution stamp |
| `--demo` | optional | Use the official demo source post; variant 2 of any single-format run is pinned to the paradox profile so the rule always demonstrates |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr (debugging) |

### Per-format variant counts

| Format | Variants (single-format mode) | Length budget |
|---|---|---|
| tweet | **3** | 240-280 chars |
| thread | **3** | 1400-2800 chars across 5-10 posts |
| carousel | **2** | 8-10 slides |
| newsletter | **2** | 600-1500 words |

When `target_format=all`, the runner emits **4 variants** total — one per format — so the creator can see the full cross-format spread at once. The Recycle Audit section auto-triggers on this mode.

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** The output is text the creator reviews and ships. Never include a `publish` action, a Zapier-style URL, or any instruction the runner could execute itself.
2. **Recycle only the creator's own content.** When the source URL's handle differs from `--x-handle`, the runner refuses with a 3-section guidance card. Recycling another account is impersonation by another name.
3. **Attribution stamp preserved.** Every variant ends with `— originally posted on X by @<handle> on <date> · recycled <today>`. The renderer's `_recycle_stamp` function is the only writer of the stamp — single grep-able chokepoint.
4. **Stale-rehash paradox** must surface in BOTH the variant card AND the Red Flags section when Format fit > 70 AND Freshness lift < 35. The runner's `--demo` mode pins variant 2 of any single-format run to the paradox profile so this rule always demonstrates.
5. **Recycle score formula is fixed.** `round(0.30·Freshness lift + 0.25·Format fit + 0.25·Engagement potential + 0.20·Differentiation)`. Freshness weighted highest because a variant that adds no new value is just a repost.
6. **No fabricated freshness.** When `recycle_angle = update` and the runner has no fresh data (e.g. URL-only source), variants emit explicit `[insert refreshed metric here]` placeholders rather than inventing numbers.

---

## Cross-template daily flow (Grok Agent OS for creators)

Content Recycler is the back-catalog-compounding layer of the Grok Agent OS creator suite. The recommended monthly flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Monthly — back-catalog audit                                     │
│  └─ analytics-summarizer    → spot the X posts that scored hardest│
│       │                                                           │
│       └─ content-recycler   → recycle each one under the right    │
│            │                  angle (update / expand / threadify) │
│            │                                                      │
│            ├─ paradox flagged? → swap angle to update or expand   │
│            ├─ update angle?    → research-assistant for new data  │
│            └─ all-format mode? → review the per-format spread     │
│                                                                   │
│  Mid-week — pre-ship checks                                       │
│  └─ brand-voice-trainer     → re-anchor voice (recycling drifts!) │
│  └─ content-calendar-builder → schedule away from original's      │
│                                resurface cycle                    │
│                                                                   │
│  Ship-day                                                         │
│  └─ thread-builder          → polish the variant-1 thread before  │
│                                shipping                           │
│  └─ ab-test-suggester       → A/B variant 1 vs variant 3          │
│                                                                   │
│  After ship                                                       │
│  └─ cross-platform-reposter → cross-post the closing payoff       │
│  └─ analytics-summarizer    → snapshot original (T-7d) and        │
│                                recycled (T+7d) deltas             │
│                                                                   │
│  Quarterly                                                        │
│  └─ competitor-watch        → are competitors recycling similar   │
│                                content? Counter-position next     │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next `python .\templates\creator\<slug>\run.py` (or `templates\general\<slug>` for `research-assistant`) command.

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `thread-builder` | `templates/creator/` | Build the long-form thread when angle = `threadify` or `expand` |
| `cross-platform-reposter` | `templates/creator/` | Cross-post the recycled variant to LinkedIn / Threads / Bluesky / Newsletter |
| `quote-tweet-suggestor` | `templates/creator/` | Riff on the original when re-pinning beats recycling |
| `analytics-summarizer` | `templates/creator/` | Snapshot the original's engagement pre/post-recycle to measure compounding |
| `content-calendar-builder` | `templates/creator/` | Schedule the recycled variant away from the original's resurface cycle |
| `content-idea-generator` | `templates/creator/` | Generate the next anchor when no recycle angle scores ≥ 70 |
| `brand-voice-trainer` | `templates/creator/` | Re-anchor voice — recycling drifts toward format-default tone |
| `monetization-optimizer` | `templates/creator/` | Model paid-tier funnel recycling (carries V.1 disclaimer) |
| `ab-test-suggester` | `templates/creator/` | A/B-test variant 1 vs variant 3 of the same recycle angle |
| `competitor-watch` | `templates/creator/` | See whether competitors recycled similar content recently |
| `mention-summarizer` | `templates/creator/` | Roll up mentions on the original to spot the angle that scored hardest |
| `research-assistant` | `templates/general/` | Pull updated data / sources for `update`-angle recycles |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\content-recycler\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\content-recycler\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\content-recycler\logs\` |
| System prompt | `templates\creator\content-recycler\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`, and the path is consent-gated by Constitution Article II if it's outside the AppData folder above.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_recycled_variants` (bound to `content_recycler.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, II, III, V, VII for content recycling
- **6 hard refusals**: recycle a post the creator did not author; auto-publish without consent gate; strip the attribution stamp; claim a recycled variant is original content; fabricate freshness; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\content-recycler\grok-agent.yaml
python safety\scanner.py scan  templates\creator\content-recycler\grok-agent.yaml
```

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × `expand` × `thread` (3 variants) | Thread variant 2 paradox demonstrated; 5 cross-template bridges |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × `auto` × `all` (4 variants — one per format) | Recycle Audit auto-triggered; cannibalization-risk + voice-drift surfaced |

Both demonstrate the 4-metric scoring with the weighted formula, ≥3 distinct cross-template bridges in Recommendations, the verbatim attribution stamp on every variant body, and source-agnostic scaffolds that wrap the source text without leaking demo content.

To regenerate either example deterministically, see the regenerate snippets at the top of each example file.

---

## v1 limitation note

The runner's variant scaffolds are **deterministic and source-agnostic** — they wrap the source text with format-specific framing (thread hook/develop/payoff, carousel slide titles, newsletter section structure) but they do not paraphrase the substance of the source. A future v2 with Grok 4.3 in the loop would generate fully paraphrased variants while preserving the same structure, scoring, paradox detection, handle-mismatch refusal, and attribution-stamp invariants this v1 already enforces.

Until then, treat the variant body as a *scaffold* the creator polishes — the value the runner adds is:
1. The structure (4 metrics + weighted score + paradox detection)
2. The recycle-angle analysis (chosen / why / what-changes / what-stays)
3. The verbatim attribution stamp (preserved on every variant)
4. The handle-mismatch refusal (impersonation guard)
5. The cross-template bridges (≥3 distinct per output)
6. The deterministic seed (re-runnable for the same inputs)

---

## Build slots (Recipe B)

Content Recycler follows the official Recipe B 2-prompt shape:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P73 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P74 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing back-catalog-compounding layer that turns "should I recycle this old post?" from a one-shot decision into a structured monthly habit — without flattening voice, without losing attribution, and without auto-publishing anywhere.
