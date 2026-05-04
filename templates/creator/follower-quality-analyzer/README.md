<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 👥 Follower Quality Analyzer

> Aggregate follower-quality scoring for X creators — 4 canonical metrics, paraphrased top-follower archetypes, bot-engagement paradox detection, and ≥3 cross-template bridges. Aggregate-only, local-first, zero individual PII in the output.
>
> *Built to help xAI and Grok win the platform battle on X — every creator deserves to see their real audience without exposing a single handle.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy disclaimer (non-negotiable, Constitution Article VII)

> 🔒 **Aggregate-only output.** This template never prints, logs, or exports an individual follower's handle, display name, bio, or any other PII. The runner accepts handles as input so you can paste your own data export, but only the *count* and *seed-derived* aggregate signal flow into the rendered report. Every Top-Follower card is a paraphrased archetype, never a named account.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\follower-quality-analyzer\`. Nothing is uploaded. The v1 runner makes zero external network calls — it is offline-safe and can be smoke-tested on a fresh Windows install with no API keys.

These banners are required by Constitution Article VII (local-first / privacy-first) and Articles III.1 + III.3 (no impersonation, no exfiltration). They are checked by `safety/scanner.py` on every install and every PR.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches monetization tiers, payout estimates, or cashflow.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a list of follower handles into a 6/7-section structured quality report you can paste into a brief, a Notion doc, or your weekly creator review.

The report is the same shape every time:

1. **Headline** — one-sentence takeaway, focus-aware
2. **Quality Scores** — exactly 4 canonical metrics (Engagement quality / Authenticity / Niche alignment / Growth potential), each 0–100 with interpretation + 30-day trend arrow
3. **Top Followers** — 3–5 paraphrased archetype cards (`Daily-engaging niche peer`, `Long-tenure quiet builder`, etc.) — never a named account — each with one of the 6 canonical action verbs (`Engage`, `Spotlight`, `Collaborate`, `Reply`, `Monitor`, `Cultivate`)
4. **Red Flags** — 2–3 cards with severity, surfaces the **bot-engagement paradox** in BOTH this section AND the Quality Scores section when it triggers (Authenticity < 80 AND Engagement quality > niche median)
5. **Recommendations** — 3–5 next moves, each linking to ≥3 distinct cross-template bridges in `templates/creator/`
6. **Confidence** — `high | medium | low` with the reason
7. **Audience Health Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR sample size < 50

The bot-engagement paradox is the headline insight this template exists for: high engagement on a low-authenticity tail looks great in dashboards but rots community depth. Surfacing it in two places — the score row and the red flag — makes it impossible to miss.

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\follower-quality-analyzer\run.py --x-handle JanSol0s --demo --focus all
```

That prints the 6/7-section report straight to your terminal, seeded by a deterministic 140-handle demo sample (no real follower data needed). Add `--no-banner` to suppress the runner banner if you want clean stdout for piping.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install follower-quality-analyzer
```

The CLI:

1. Resolves the manifest at `templates\creator\follower-quality-analyzer\grok-agent.yaml`
2. Validates it against `spec\v2.15\grok-agent.yaml` (Pydantic deep validator)
3. Runs `safety\scanner.py` against the Agent Constitution
4. Only on a clean pass — copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder

If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — direct invocation (developer mode)

Three input modes the runner accepts (mutually exclusive):

```powershell
# 1. Inline sample (comma, space, semicolon, newline, or pipe-separated)
python .\templates\creator\follower-quality-analyzer\run.py `
  --x-handle JanSol0s `
  --follower-sample "@alice42, @bob_smith, @carol_dev, @dan_writer, @eve_designer" `
  --focus engagement

# 2. File of handles (one per line, lines starting with # ignored)
python .\templates\creator\follower-quality-analyzer\run.py `
  --x-handle JanSol0s `
  --follower-file $env:USERPROFILE\followers.txt `
  --focus all

# 3. Date-range seed (synthesises a deterministic 120-handle aggregate sample)
python .\templates\creator\follower-quality-analyzer\run.py `
  --x-handle JanSol0s `
  --date-range "2026-04-01/2026-04-30" `
  --focus authenticity
```

Save the report to disk (Apache 2.0 HTML header is prepended automatically):

```powershell
python .\templates\creator\follower-quality-analyzer\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\follower-quality-analyzer\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--follower-sample` | one of these | Inline list of handles (comma / space / semicolon / pipe / newline separators) |
| `--follower-file` | one of these | Path to a newline-delimited handles file |
| `--date-range` | one of these | ISO date range used as a deterministic seed for a synthesised sample |
| `--demo` | optional | 140-handle deterministic demo sample, no inputs needed |
| `--focus` | optional | `engagement` \| `authenticity` \| `growth_potential` \| `all` (default `all`) |
| `--niche-median` | optional | Engagement-quality median for the niche (default 45) — controls when the paradox triggers |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr (debugging) |

---

## How the report is shaped (the 4 hard rules)

1. **Aggregate-only output.** Every render passes a final guard (`assert_no_handles_in_render`) that uses word-boundary regex matching to refuse any output that would print a real follower handle. The check is intentionally strict — it would rather fail loudly than ship a leak.
2. **Bot-engagement paradox** must surface in BOTH the Quality Scores section AND the Red Flags section when Authenticity < 80 AND Engagement quality > the niche median (default 45). Surfacing in only one place is a hard fail and the renderer would refuse it.
3. **6-verb action vocabulary** on Top-Follower cards. Each verb may be used at most twice across one report — the archetype palette is sized so this is automatic when 3–5 cards are emitted.
4. **≥3 distinct cross-template bridges** in the Recommendations list. Each bridge points to a real (or planned) creator-template slug under `templates/creator/`.

A 5th rule worth calling out: **tiny-sample refusal.** When the sample is `< 5` handles, the runner refuses to score and emits a single Headline + Recommendations item asking for a larger sample. Small-but-not-tiny samples (`< 50`) DO get scored, but trigger the optional 7th section so you know the numbers are directional.

---

## Cross-template daily flow (Grok Agent OS for creators)

This template is the audience-signal layer of the creator flywheel. The recommended daily flow:

```
┌─────────────────────────────────────────────────────────────────┐
│  06:00 morning                                                   │
│  └─ content-idea-generator   → 5 fresh post angles              │
│                                                                  │
│  09:00 publish + scan                                            │
│  └─ analytics-summarizer     → yesterday's numbers               │
│                                                                  │
│  10:00 audience signal (this template)                           │
│  └─ follower-quality-analyzer → 4 metrics + paradox check        │
│       │                                                          │
│       ├─ paradox triggered?  → mention-summarizer + dm-triager   │
│       ├─ niche dilution?      → brand-voice-trainer              │
│       ├─ low growth?          → niche-influencer-finder          │
│       └─ high engagement?     → reply-drafter                    │
│                                                                  │
│  16:00 reply window                                              │
│  └─ reply-drafter            → on-brand drafts (HITL gated)      │
│                                                                  │
│  21:00 close-out                                                 │
│  └─ analytics-summarizer     → snapshot + trend baseline         │
└─────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next `python .\templates\creator\<slug>\run.py` command.

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Why this template links to it |
|---|---|
| `reply-drafter` | High-engagement audiences reward fast on-brand replies |
| `niche-influencer-finder` | Low growth potential → find more bridge accounts |
| `dm-triager` | Paradox triggered → triage inbound by authenticity |
| `comment-engagement-booster` | Reply-thread regular cohort → deepen via 2-line follow-ups |
| `mention-summarizer` | Pair with `dm-triager` to rank mentions by quality |
| `monetization-optimizer` | Eng + auth healthy → paid-tier test (carries V.1 disclaimer) |
| `brand-voice-trainer` | Niche dilution → re-anchor the audience signal |
| `analytics-summarizer` | Snapshot scores monthly to populate trend arrows |
| `quote-tweet-suggestor` | Single-cohort dependence → diversify via adjacent niches |
| `competitor-watch` | Compare your follower quality vs peer creators |
| `thread-builder` | Convert lurkers via long-form value posts |
| `content-idea-generator` | Use top-archetype interests as content seeds |
| `growth-experiment-runner` | Tiny-sample refusal → run a sampling experiment |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\follower-quality-analyzer\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\follower-quality-analyzer\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\follower-quality-analyzer\logs\` |
| System prompt | `templates\creator\follower-quality-analyzer\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`, and the path is consent-gated by Constitution Article II if it is outside the AppData folder above.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template` — the canonical schema enum value for templates that target creator workflows
- **1 Grok-callable tool**: `generate_follower_quality_analysis` (bound to `follower_quality_analyzer.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, III, V, VII for aggregate-only follower analysis
- **2 hard refusals**: expose individual follower handles; score followers as "low-value" / "block-worthy"
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session (Article VI.1)
- **Human-in-the-loop**: enabled, 60-second timeout, confirm before exporting outside AppData (Article VI.2)
- **PII handling**: `local-only` (Article VII)
- **Data retention**: 90 days (auto-prune)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\follower-quality-analyzer\grok-agent.yaml
python safety\scanner.py scan  templates\creator\follower-quality-analyzer\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install. CI (`.github\workflows\validate.yml`) runs the same checks on every push and PR to `main`.

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Sample | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × 100 followers | Engagement-driven paradox: real audience underneath a low-authenticity tail |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × 100 followers | Borderline paradox + single-cohort dependence — wake-up call before scaling |

Both demonstrate the bot-engagement paradox surfaced in the Quality Scores section AND the Red Flags section, ≥3 distinct cross-template bridges, the Article V.1 disclaimer attached to the monetization recommendation, and 4 paraphrased Top-Follower cards with the 6-verb vocabulary.

To regenerate either example deterministically:

```powershell
# niche-ai-agents.md
$lines = 400..499 | ForEach-Object { "@aggregate_$('{0:D5}' -f $_)" }
$lines | Out-File -Encoding utf8 sample.txt
python .\run.py --x-handle JanSol0s --follower-file .\sample.txt --focus all --no-banner

# niche-productivity.md
$lines = 300..399 | ForEach-Object { "@aggregate_$('{0:D5}' -f $_)" }
$lines | Out-File -Encoding utf8 sample.txt
python .\run.py --x-handle habitstacker --follower-file .\sample.txt --focus all --no-banner
```

---

## Build slots (Recipe B)

Follower Quality Analyzer follows the canonical Recipe B 2-prompt shape:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P65 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P66 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing aggregate-only audience signal layer that makes follower-quality conversation an everyday creator habit, not a quarterly audit.
