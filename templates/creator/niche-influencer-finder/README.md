<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🤝 Niche Influencer Finder

> Aggregate niche-influencer discovery for X creators — 4 official match scores per archetype, 3-tier follower bands (Micro / Mid / Macro), engagement-pod paradox detection, and ≥3 cross-template bridges. Aggregate-only — never names a real X account.
>
> *Built for xAI, X, Grok and the ecosystem community — leveling the platform battle on X. Every creator deserves a discovery layer that respects who they actually want to reach out to.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy disclaimer (non-negotiable, Constitution Article VII)

> 🔒 **Aggregate-only output.** This template never prints, logs, or exports a real X account handle. Every Top-Influencer card is a paraphrased archetype (label + tier + follower count band + 4-row score table) the creator can use as a brief when *they* decide who to actually reach out to. The runner accepts no influencer handles as input — only niche keywords — and the renderer's privacy guard refuses to emit any output that would surface a plausibly-shaped `@handle` other than the creator's own.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\niche-influencer-finder\`. Nothing is uploaded. The v1 runner makes zero external network calls — it is offline-safe and can be smoke-tested on a fresh Windows install with no API keys.

These banners are required by Constitution Article VII (local-first / privacy-first) and Articles III.1 + III.3 (no impersonation, no exfiltration). They are checked by `safety/scanner.py` on every install and every PR.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches paid placements, sponsorships, revenue share, or paid-tier conversion.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns a creator's niche keywords + a follower-count band into a 6/7-section structured discovery report you can paste into a brief, a Notion doc, or your weekly creator review.

The report shape is the same every time:

1. **Influencer Summary** — one-sentence headline + one-paragraph synthesis tied to the requested focus
2. **Top Influencers** — 3-5 paraphrased archetype cards spanning the Micro (5k-50k) / Mid (50k-200k) / Macro (200k-500k) tiers, each with the 4-row Match Scores table (Authority / Engagement / Audience fit / Collaboration potential), the weighted Match score `round(0.30A + 0.25E + 0.25F + 0.20C)`, why-it-matches lines, and a suggested first move from the 6-format vocabulary (`thread-collab`, `podcast-swap`, `quote-tweet-rally`, `co-authored-post`, `mutual-shoutout`, `dm-intro`)
3. **Collaboration Opportunities** — 3-5 specific format-x-archetype plays with concrete plans + expected lift
4. **Red Flags** — 2-3 cards with severity, surfaces the **engagement-pod paradox** in BOTH this section AND the relevant Top-Influencer card when an archetype shows Engagement > 70 AND Authority < 50
5. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges in `templates/creator/` (or `templates/general/` for `research-assistant`)
6. **Confidence** — `high | medium | low` with the reason
7. **Discovery Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR niche-keyword count < 2

The engagement-pod paradox is the headline insight this template exists for: a candidate showing 80+ engagement on a sub-50 authority signal is almost always pod activity. Surfacing it in two places — the archetype card and the red flag — makes it impossible to miss before you waste an outreach DM on it.

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\niche-influencer-finder\run.py --x-handle JanSol0s --demo --focus all
```

That prints the 6/7-section report straight to your terminal, seeded by the default demo niche keywords (`AI agents`, `LLM ops`, `infra`). Add `--no-banner` to suppress the runner banner if you want clean stdout for piping.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install niche-influencer-finder
```

The CLI:

1. Resolves the manifest at `templates\creator\niche-influencer-finder\grok-agent.yaml`
2. Validates it against `spec\v2.15\grok-agent.yaml` (Pydantic deep validator)
3. Runs `safety\scanner.py` against the Agent Constitution
4. Only on a clean pass — copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder

If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — direct invocation (developer mode)

```powershell
# Standard discovery — 3 keywords, default 5k-500k band, all-focus
python .\templates\creator\niche-influencer-finder\run.py `
  --x-handle JanSol0s `
  --niche-keywords "AI agents, LLM ops, infra" `
  --focus all

# Tight band — Mid tier only (50k-200k); great for first-collab targeting
python .\templates\creator\niche-influencer-finder\run.py `
  --x-handle JanSol0s `
  --niche-keywords "AI agents, LLM ops, infra" `
  --min-followers 50000 `
  --max-followers 200000 `
  --focus collaboration_potential

# Save the report (Apache 2.0 HTML header is prepended automatically)
python .\templates\creator\niche-influencer-finder\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\niche-influencer-finder\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--niche-keywords` | yes (or `--demo`) | Comma / semicolon / pipe / newline-separated keywords |
| `--min-followers` | optional | Lower bound on archetype follower count (default 5,000 — Micro tier floor) |
| `--max-followers` | optional | Upper bound on archetype follower count (default 500,000 — Macro tier ceiling) |
| `--focus` | optional | `engagement` \| `authority` \| `collaboration_potential` \| `all` (default `all`) |
| `--demo` | optional | Use the default demo keywords (`AI agents`, `LLM ops`, `infra`) — no `--niche-keywords` required |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr (debugging) |

---

## How the report is shaped (the 5 hard rules)

1. **No real handles.** Every render passes a final guard (`assert_no_real_handles_in_render`) that uses word-boundary regex matching to refuse any output containing a plausibly-shaped `@handle` other than the creator's own. The check is intentionally strict — it would rather fail loudly than ship a leak.
2. **Match score formula is fixed.** `round(0.30 * Authority + 0.25 * Engagement + 0.25 * Audience fit + 0.20 * Collaboration potential)`. Authority weighted highest because thin authority is the cheapest signal to fake.
3. **Engagement-pod paradox** must surface in BOTH the archetype card AND the Red Flags section when Engagement > 70 AND Authority < 50. Surfacing in only one place is a hard fail and the renderer would refuse it. The selector intentionally reserves a slot for paradox archetypes when they exist in the palette — they are warnings the creator should see, not silent omissions.
4. **Tier-band respect.** Archetypes whose plausible follower count would fall outside the requested `--min-followers` / `--max-followers` band are dropped — never invented into range. If the band excludes a whole tier, the omission is mentioned in the Discovery Audit when it triggers.
5. **≥3 distinct cross-template bridges** in the Recommendations list. Each bridge points to a real (or planned) creator-template slug under `templates/creator/` (or `templates/general/` for `research-assistant`).

A 6th rule worth calling out: **empty-band refusal.** When the supplied `--min-followers` / `--max-followers` band excludes every archetype in the runner's palette, the runner refuses to score and emits a 3-section guidance card instead of fabricating matches.

---

## Cross-template daily flow (Grok Agent OS for creators)

This template is the discovery layer of the creator collaboration flywheel. The recommended weekly flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Monday morning — discovery + planning                            │
│  └─ niche-influencer-finder  → 5 paraphrased archetypes + scores  │
│       │                                                           │
│       ├─ paradox flagged?    → follower-quality-analyzer to vet   │
│       ├─ Macro tier empty?   → widen band + re-run                │
│       ├─ low-auth majority?  → research-assistant for background  │
│       └─ high match score?   → content-idea-generator for pitch   │
│                                                                   │
│  Tuesday — outreach in voice                                      │
│  └─ brand-voice-trainer      → DM drafts that sound like creator  │
│  └─ reply-drafter            → first reply / DM (HITL gated)      │
│                                                                   │
│  Mid-week — collab build                                          │
│  └─ thread-builder           → joint long-form draft              │
│  └─ content-idea-generator   → 3 co-content angles per target     │
│                                                                   │
│  Friday close-out                                                 │
│  └─ analytics-summarizer     → snapshot follower + engagement     │
│  └─ analytics-summarizer (T+14) → measure real lift, not vanity   │
│                                                                   │
│  Monthly                                                          │
│  └─ competitor-watch         → who did peers collab with this mo? │
└──────────────────────────────────────────────────────────────────┘
```

Every Recommendation in this template's output ends with `bridges to: <slug>` so you can copy-paste the slug straight into the next `python .\templates\creator\<slug>\run.py` (or `templates\general\<slug>` for `research-assistant`) command.

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `follower-quality-analyzer` | `templates/creator/` | Vet the archetype's audience before reaching out — confirms real reach, not pod traffic |
| `reply-drafter` | `templates/creator/` | Draft the first reply or DM in the creator's voice |
| `content-idea-generator` | `templates/creator/` | Generate co-content ideas tailored to both creator and influencer |
| `monetization-optimizer` | `templates/creator/` | Estimate paid-placement value before negotiating sponsorship (carries V.1 disclaimer) |
| `analytics-summarizer` | `templates/creator/` | Snapshot follower + engagement before/after a collab to measure real lift |
| `thread-builder` | `templates/creator/` | Build a co-authored long-form thread the influencer can quote-tweet |
| `competitor-watch` | `templates/creator/` | Watch which influencers competitors collab with — surfaces gaps in your network |
| `mention-summarizer` | `templates/creator/` | After a collab, summarise which mentions came from the influencer's audience |
| `dm-triager` | `templates/creator/` | Prioritise DMs from collab targets when they reply |
| `brand-voice-trainer` | `templates/creator/` | Make sure outreach DMs sound like the creator, not a template |
| `quote-tweet-suggestor` | `templates/creator/` | Suggest the right quote-tweet line when an influencer posts something co-relevant |
| `research-assistant` | `templates/general/` | Pull deeper background on an archetype's niche claims before pitching a podcast |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\niche-influencer-finder\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\niche-influencer-finder\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\niche-influencer-finder\logs\` |
| System prompt | `templates\creator\niche-influencer-finder\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`, and the path is consent-gated by Constitution Article II if it is outside the AppData folder above.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template` — the official schema enum value for creator-flow templates
- **1 Grok-callable tool**: `generate_niche_influencer_recommendations` (bound to `niche_influencer_finder.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, III, V, VII for aggregate-only influencer discovery
- **4 hard refusals**: name a real X account; fabricate metrics; scrape authenticated X content; recommend influencers as a "must follow" list
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session (Article VI.1)
- **Human-in-the-loop**: enabled, 60-second timeout, confirm before exporting outside AppData (Article VI.2)
- **PII handling**: `local-only` (Article VII)
- **Data retention**: 90 days (auto-prune)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\creator\niche-influencer-finder\grok-agent.yaml
python safety\scanner.py scan  templates\creator\niche-influencer-finder\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install. CI (`.github\workflows\validate.yml`) runs the same checks on every push and PR to `main`.

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × 3 keywords, full 5k-500k band | Macro paradox archetype: high engagement masks thin authority — verify before scaling outreach |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × 3 keywords, 5k-200k band, focus=collaboration_potential | Mid-tier paradox archetype + tier-coverage gap (Macro empty) — wake-up call before scaling |

Both demonstrate the engagement-pod paradox surfaced in the Top-Influencer card AND the Red Flags section, ≥3 distinct cross-template bridges in Recommendations, the Article V.1 disclaimer attached to the monetization recommendation, and 5 paraphrased Top-Influencer cards spanning multiple tiers.

To regenerate either example deterministically:

```powershell
# niche-ai-agents.md
python .\run.py --x-handle JanSol0s --niche-keywords "AI agents, LLM ops, infra" --focus all --no-banner

# niche-productivity.md
python .\run.py --x-handle habitstacker --niche-keywords "productivity, habit stacking, deep work" --max-followers 200000 --focus collaboration_potential --no-banner
```

---

## Build slots (Recipe B)

Niche Influencer Finder follows the official Recipe B 2-prompt shape:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P67 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P68 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing aggregate-only discovery layer that turns "who should I collab with?" from a vibes-check into a structured weekly habit.
