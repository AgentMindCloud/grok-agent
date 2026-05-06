<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🛰️ Competitor Watch

> Aggregate competitor monitoring for X creators — 4 official Watch Score metrics per competitor, content gaps + growth opportunities derived from format mix, cadence-fatigue paradox detection, and ≥3 cross-template bridges. Names only the competitors you explicitly chose to track.
>
> *Built for xAI, X, Grok and the ecosystem community the platform battle on X — every creator deserves a watch that respects who they actually picked, not who an algorithm thinks they should fear.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy disclaimer (non-negotiable, Constitution Article VII)

> 🔒 **Named-competitors-only.** This template names competitors only when the creator explicitly passes them as input. The runner never invents rivals, never crawls "the network", never imports a leaderboard. The output references **only** the handles in `--competitor-handles` (or `--competitor-file`) — plus the creator's own handle.

> 🔒 **No competitor PII.** The watch is on PUBLIC posting patterns only — content cadence, format mix, growth direction, monetization signal. The runner never exposes a competitor's followers, DMs, mutuals, mentions, email patterns, or any other PII. The renderer's privacy guard refuses to emit any output containing a plausibly-shaped `@handle` outside the explicit input set.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\competitor-watch\`. Nothing is uploaded. The v1 runner makes zero external network calls — it is offline-safe and can be smoke-tested on a fresh Windows install with no API keys.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches monetization tactics, paid placements, or sponsorship modeling.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator's chosen competitor list + a `time_range` into a 6/7-section structured watch report you can paste into a brief, a Notion doc, or your weekly creator review.

The report shape is the same every time:

1. **Watch Summary** — one-sentence headline + one-paragraph synthesis tied to the requested focus
2. **Competitor Profiles** — 3-5 cards, each with the 4-row Watch Score table (Audience overlap / Content velocity / Growth signal / Monetization activity), the weighted Watch score `round(0.30·Overlap + 0.25·Content + 0.25·Growth + 0.20·Monetization)`, why-this-competitor-matters lines, and a dominant format
3. **Content Gaps** — 3-5 specific topics / formats / cadences competitors are running that the creator is not
4. **Growth Opportunities** — 3-5 creator-side plays mapped 1:1 from the gap analysis
5. **Red Flags** — 2-3 cards with severity, surfaces the **cadence-fatigue paradox** in BOTH this section AND the relevant Competitor Profile card when a competitor shows Content velocity > 70 AND Growth signal < 30
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges in `templates/creator/` (or `templates/general/` for `research-assistant`)
7. **Watch Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR competitor count < 2

The cadence-fatigue paradox is the core insight this template exists for: a competitor running 70+ posts/week cadence on a sub-30 growth signal is burning out — that pattern is failing for them, and a creator who copies it will burn out too. Surfacing the paradox in two places — the profile card and the red flag — makes it impossible to copy by accident.

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\competitor-watch\run.py --x-handle JanSol0s --demo --time-range 30d --focus all
```

That prints the 6-section report straight to your terminal, using 4 demo competitor handles seeded so the third lands on the cadence-fatigue paradox. Add `--no-banner` to suppress the runner banner if you want clean stdout for piping.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install competitor-watch
```

The CLI:

1. Resolves the manifest at `templates\creator\competitor-watch\grok-agent.yaml`
2. Validates it against `spec\v2.15\grok-agent.yaml` (Pydantic deep validator)
3. Runs `safety\scanner.py` against the Agent Constitution
4. Only on a clean pass — copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder

If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — direct invocation (developer mode)

```powershell
# Standard watch — 4 competitors, 30d window, all-focus
python .\templates\creator\competitor-watch\run.py `
  --x-handle JanSol0s `
  --competitor-handles "@rivalA, @rivalB, @rivalC, @rivalD" `
  --time-range 30d `
  --focus all

# File-based competitor list (one handle per line, # for comments)
python .\templates\creator\competitor-watch\run.py `
  --x-handle JanSol0s `
  --competitor-file $env:LOCALAPPDATA\grok-agent\competitor-watch\competitors.txt `
  --time-range 90d `
  --focus growth

# Save the report (Apache 2.0 HTML header is prepended automatically)
python .\templates\creator\competitor-watch\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\competitor-watch\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--competitor-handles` | yes (or `--competitor-file` or `--demo`) | Comma / semicolon / pipe / whitespace-separated competitor handles |
| `--competitor-file` | yes (alt) | Path to a newline-delimited file (one handle per line, `#` comments) |
| `--time-range` | optional | `7d` \| `30d` \| `90d` (default `30d`) |
| `--focus` | optional | `content` \| `growth` \| `monetization` \| `all` (default `all`) |
| `--demo` | optional | Use the 4 default demo handles (`@rivalA`-`@rivalD`); rotation pins the third to the paradox profile |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr (debugging) |

---

## How the report is shaped (the 6 hard rules)

1. **Named competitors only.** Every competitor reference in the body is a handle the creator explicitly supplied. The runner has no concept of "find me competitors" — that's `niche-influencer-finder`'s job. If you didn't pass them, they don't appear.
2. **No competitor PII.** Every render passes a final guard (`assert_only_input_handles_in_render`) that uses word-boundary regex matching to refuse any output containing an `@handle` outside the explicit input set. The check is intentionally strict — it would rather fail loudly than ship a leak about a competitor's followers.
3. **Watch score formula is fixed.** `round(0.30 · Audience overlap + 0.25 · Content velocity + 0.25 · Growth signal + 0.20 · Monetization activity)`. Audience overlap weighted highest because a non-overlapping competitor isn't a meaningful one — the watch is *for the creator*, not a leaderboard.
4. **Cadence-fatigue paradox** must surface in BOTH the profile card AND the Red Flags section when Content velocity > 70 AND Growth signal < 30. Surfacing in only one place is a hard fail, and the runner's `--demo` mode pins the third competitor to the paradox profile so the rule always demonstrates correctly.
5. **≥3 distinct cross-template bridges** in the Recommendations list. Each bridge points to a real (or planned) template slug under `templates/creator/` (or `templates/general/` for `research-assistant`).
6. **No abusive plays.** The Constitution refuses any recommendation that would involve coordinated harassment, mass automated engagement, report-brigading, scraping authenticated content, or impersonating a competitor. The runner doesn't generate them, and the system prompt won't echo them either.

---

## Cross-template daily flow (Grok Agent OS for creators)

Competitor Watch is the situational-awareness layer of the Grok Agent OS creator suite. The recommended weekly flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Monday morning — situational awareness                           │
│  └─ competitor-watch         → 4 profiles + gaps + opportunities  │
│       │                                                           │
│       ├─ paradox flagged?    → research-assistant for context     │
│       ├─ overlap-too-high?   → brand-voice-trainer to differentiate│
│       ├─ monetization gap?   → monetization-optimizer (V.1 gated) │
│       └─ content gap?        → content-idea-generator + thread-builder │
│                                                                   │
│  Tuesday — voice-anchored execution                               │
│  └─ brand-voice-trainer      → re-anchor before any cadence push  │
│  └─ content-idea-generator   → 5 gap-driven post ideas            │
│                                                                   │
│  Mid-week — ship                                                  │
│  └─ thread-builder           → long-form thread filling top gap   │
│  └─ ab-test-suggester        → 4-week test on dominant new format │
│                                                                   │
│  Friday close-out                                                 │
│  └─ analytics-summarizer     → snapshot creator's deltas vs watch │
│                                                                   │
│  Monthly                                                          │
│  └─ niche-influencer-finder  → spot collab gaps competitors have  │
│  └─ follower-quality-analyzer → vet your own audience vs theirs   │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next `python .\templates\creator\<slug>\run.py` (or `templates\general\<slug>` for `research-assistant`) command.

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `analytics-summarizer` | `templates/creator/` | Snapshot creator's deltas alongside competitor deltas — turn the watch into a baseline |
| `thread-builder` | `templates/creator/` | Build the long-form thread that fills the biggest content gap |
| `content-idea-generator` | `templates/creator/` | Generate gap-driven post ideas in the creator's voice (NOT the competitor's) |
| `monetization-optimizer` | `templates/creator/` | Model monetization tactics observed without copying cadence (carries V.1 disclaimer) |
| `niche-influencer-finder` | `templates/creator/` | Spot collab targets your competitors are missing — counter-positioning |
| `follower-quality-analyzer` | `templates/creator/` | Compare creator's audience quality against competitors' growth surface |
| `reply-drafter` | `templates/creator/` | Draft thoughtful, on-voice replies in competitors' threads — never harassment |
| `brand-voice-trainer` | `templates/creator/` | Re-anchor voice before any cadence-matching push |
| `quote-tweet-suggestor` | `templates/creator/` | Riff substantively on a competitor's post (with attribution) |
| `ab-test-suggester` | `templates/creator/` | Test one new format the competitor is running, in the creator's voice |
| `growth-experiment-runner` | `templates/creator/` | Set up a 4-week experiment around the dominant growth play observed |
| `research-assistant` | `templates/general/` | Pull deeper public background on a paid placement before modelling |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\competitor-watch\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\competitor-watch\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\competitor-watch\logs\` |
| System prompt | `templates\creator\competitor-watch\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`, and the path is consent-gated by Constitution Article II if it's outside the AppData folder above.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template` — the official schema enum value for creator-flow templates
- **1 Grok-callable tool**: `generate_competitor_watch` (bound to `competitor_watch.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, III, V, VII for named-competitor monitoring
- **5 hard refusals**: scrape authenticated competitor content; impersonate a competitor; coordinated harassment; expose competitor follower PII; fabricate metrics or invent rival handles
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session (Article VI.1)
- **Human-in-the-loop**: enabled, 60-second timeout, confirm before exporting outside AppData (Article VI.2)
- **PII handling**: `local-only` (Article VII)
- **Data retention**: 90 days (auto-prune)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\competitor-watch\grok-agent.yaml
python safety\scanner.py scan  templates\creator\competitor-watch\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install. CI (`.github\workflows\validate.yml`) runs the same checks on every push and PR to `main`.

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × 4 competitors via `--demo`, 30d, focus=all | `@rivalC` shows the cadence-fatigue paradox; @rivalD is monetization-heavy without overlap |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × 4 competitors, 30d, focus=growth | `@routinemaster` paradox + `@deepworkdaily` overlap-too-high — full V.1 disclaimer surfaces |

Both demonstrate the cadence-fatigue paradox surfaced in the Competitor Profile card AND the Red Flags section, ≥3 distinct cross-template bridges in Recommendations, 4 competitor profile cards with the 4-row Watch Score table, and named-competitors-only privacy.

To regenerate either example deterministically:

```powershell
# niche-ai-agents.md
python .\run.py --x-handle JanSol0s --demo --time-range 30d --focus all --no-banner

# niche-productivity.md
python .\run.py --x-handle habitstacker --competitor-handles "@deepworkdaily,@routinemaster,@productivpro,@habitcoach" --time-range 30d --focus growth --no-banner
```

---

## Build slots (Recipe B)

Competitor Watch follows the official Recipe B 2-prompt shape:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P69 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P70 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing situational-awareness layer that turns "what are competitors doing?" from doomscrolling into a structured weekly read.
