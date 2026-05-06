<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🏷️ Hashtag Strategy Advisor

> Turn any post topic into a 5-10 hashtag strategy spread across the 5 categories (broad-niche / specific-niche / trending / community / branded), with platform-specific ship caps stated explicitly. 4 official Hashtag Plan Score metrics, reach-without-relevance paradox detection, hard refusal of engagement-bait families, ≥3 cross-template bridges. Drafts only.
>
> *Built for xAI, X, Grok and the ecosystem community — sharpening the platform battle on X. Every X creator deserves hashtags with relevance, not stuffing.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits hashtag recommendations the creator pastes into their own post copy. The runner never auto-publishes anywhere.

> 🔒 **No engagement-bait hashtags.** `#FollowForFollow`, `#Like4Like`, `#FF`, `#TeamFollowBack`, `#FollowTrain` and the entire bait family are a hard refusal. The runner enforces the blocklist twice: at library-load (`_validate_library` rejects any blocklisted entry) and at output-emit (`assert_no_engagement_bait_in_render` rejects any rendered output containing one).

> 🔒 **Honest trending category check.** A hashtag is `trending` ONLY when the post topic matches its documented trigger keywords. If no honest trending tag fits, the runner emits 0 trending recommendations and notes it. Riding an unrelated trending tag is algorithm-manipulation and refused outright.

> 🔒 **Platform-specific ship caps stated in every output.** X = 0-2 hashtags per post; LinkedIn = 0-3. Even when 10 tags score above 70, the cap stays — over-stuffing is the anti-pattern.

> 🔒 **No off-niche padding.** When the topic doesn't yield enough on-niche matches to fill `--num-hashtags`, the runner returns fewer recommendations rather than padding with unrelated broad-niche tags.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\hashtag-strategy-advisor\`. The v1 runner makes zero external network calls — it is offline-safe.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches monetization tactics, paid-tier launches, or sponsorship campaigns.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns one post topic (URL or pasted text) plus a target platform into a 6/7-section structured hashtag strategy.

The report shape is the same every time:

1. **Topic Snapshot** — one-sentence summary + 5-bullet metadata including the explicit ship cap
2. **Hashtag Plan** — aggregate Hashtag Plan score across the recommendation set
3. **Recommended Hashtags** — 5-10 cards, each with the 4-row Hashtag Plan Score table (Niche relevance / Reach potential / Engagement quality / Cleanliness), the weighted Hashtag Plan score `round(0.30·Niche + 0.25·Reach + 0.25·Engagement + 0.20·Cleanliness)`, the category, why-it-fits, and a ship priority (high / medium / low)
4. **Strategy Tips** — 3-5 platform-aware posting tips
5. **Red Flags** — 2-4 cards with severity, surfaces the **reach-without-relevance paradox** in BOTH this section AND the relevant hashtag card when Reach > 70 AND Niche relevance < 35
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges
7. **Confidence**
8. **Hashtag Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR platform = `all`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\hashtag-strategy-advisor\run.py --x-handle JanSol0s --demo --platform x --num-hashtags 5
```

That prints the 7-section report (5 AI-niche tags including a `#AI` pinned to the reach-without-relevance paradox profile for educational rule demonstration).

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install hashtag-strategy-advisor
```

### Option B — direct invocation (developer mode)

```powershell
# X-only with 5 hashtags on a real topic
python .\templates\creator\hashtag-strategy-advisor\run.py `
  --x-handle JanSol0s `
  --post-topic-or-text "Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness." `
  --platform x `
  --num-hashtags 5 `
  --focus all

# LinkedIn (ship cap 0-3) with 7 hashtags
python .\templates\creator\hashtag-strategy-advisor\run.py `
  --x-handle JanSol0s `
  --post-topic-or-text "..." `
  --platform linkedin `
  --num-hashtags 7

# 'all' platforms (reports both ship caps separately; auto-triggers Hashtag Audit)
python .\templates\creator\hashtag-strategy-advisor\run.py `
  --x-handle JanSol0s `
  --demo `
  --platform all `
  --num-hashtags 8

# Productivity demo (healthy mix, no paradox)
python .\templates\creator\hashtag-strategy-advisor\run.py `
  --x-handle habitstacker `
  --demo-productivity `
  --platform linkedin `
  --num-hashtags 5

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\hashtag-strategy-advisor\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\hashtag-strategy-advisor\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--post-topic-or-text` | yes (or `--demo` / `--demo-productivity`) | Either an `x.com` URL or the literal post topic |
| `--platform` | optional | `x` \| `linkedin` \| `all` (default `x`) |
| `--num-hashtags` | optional | 5-10 (default 5) |
| `--focus` | optional | `reach` \| `engagement` \| `niche` \| `all` (default `all`) |
| `--demo` | optional | Use the official AI-niche demo topic; pins `#AI` so the paradox demonstrates |
| `--demo-productivity` | optional | Use a productivity demo topic; healthy mix (no paradox) |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator pastes into a post; the runner never publishes anything.
2. **No engagement-bait hashtags.** Blocklist enforced at library-load AND at output-emit. The output cannot contain `#FollowForFollow / #Like4Like / #FF / #TeamFollowBack` or any pattern an X policy review would treat as algorithm gaming.
3. **Reach-without-relevance paradox** must surface in BOTH the relevant hashtag card AND the Red Flags section when Reach potential > 70 AND Niche relevance < 35. The runner's `--demo` mode pins `#AI` into the set with low Niche relevance so the rule demonstrates.
4. **Hashtag Plan score formula is fixed.** `round(0.30·Niche relevance + 0.25·Reach potential + 0.25·Engagement quality + 0.20·Cleanliness)`. Niche relevance weighted highest because off-niche tags poison the audience signal more than they help reach.
5. **Ship cap stated explicitly.** Every output names the platform's hashtag count cap (X = 0-2 per post, LinkedIn = 0-3) so the creator picks the right subset to actually ship — even if 10 tags score above 70.
6. **Honest trending check.** A tag is `trending` ONLY when the topic matches its documented trigger keywords. The runner refuses to mark a hashtag as trending without honest velocity match.

---

## Cross-template daily flow (Grok Agent OS for creators)

Hashtag Strategy Advisor is the discovery-tactics layer of the Grok Agent OS creator suite. The recommended per-anchor flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Pre-launch — design the tag set                                  │
│  └─ hashtag-strategy-advisor → 5-10 scored tags + ship cap        │
│       │                                                           │
│       ├─ paradox flagged?    → skip the broad-niche tag on X      │
│       │                       → consider for LinkedIn instead     │
│       ├─ no trending fit?    → skip trending category honestly    │
│       └─ branded ready?      → use sparingly until habit locks    │
│                                                                   │
│  Launch                                                           │
│  └─ creator pastes the top 0-2 tags (X) or 0-3 (LinkedIn)         │
│  └─ ships post; remaining tags held for sibling posts             │
│                                                                   │
│  Post-launch (T+24h)                                              │
│  └─ analytics-summarizer → per-tag impressions + reply rate       │
│  └─ ab-test-suggester    → 1-tag vs 2-tag follow-up A/B           │
│                                                                   │
│  Post-launch (T+7d)                                               │
│  └─ analytics-summarizer → which tags compounded for this voice   │
│  └─ competitor-watch     → are competitors over-using these tags? │
│                                                                   │
│  Cross-platform                                                   │
│  └─ cross-platform-reposter → adapt tag set per platform cap      │
│                                X 0-2, LinkedIn 0-3, Bluesky 0-2   │
└──────────────────────────────────────────────────────────────────┘
```

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `content-idea-generator` | `templates/creator/` | Source the next anchor in the cluster of the highest-scoring tag |
| `thread-builder` | `templates/creator/` | Build the long-form thread that earns the use of a high-relevance specific-niche tag |
| `analytics-summarizer` | `templates/creator/` | Snapshot per-hashtag impressions / replies after shipping |
| `cross-platform-reposter` | `templates/creator/` | Adapt the hashtag set per platform — X 0-2, LinkedIn 0-3 |
| `competitor-watch` | `templates/creator/` | Spot which tags competitors over-use; counter-position |
| `brand-voice-trainer` | `templates/creator/` | Make the branded hashtag a genuine extension of the creator's voice |
| `ab-test-suggester` | `templates/creator/` | A/B-test 1-tag vs 2-tag posts on X over a 2-week window |
| `comment-engagement-booster` | `templates/creator/` | Pair the post with on-voice comments (no hashtag stuffing in the comment) |
| `mention-summarizer` | `templates/creator/` | Roll up which hashtag attracted the most substantive mentions |
| `monetization-optimizer` | `templates/creator/` | Tune monetization-aware hashtag campaigns separately (carries V.1 disclaimer) |
| `content-recycler` | `templates/creator/` | Recycle a high-performing tagged post under a different angle next quarter |
| `research-assistant` | `templates/general/` | Pull deeper background on a tag's history when verifying trending velocity |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\hashtag-strategy-advisor\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\hashtag-strategy-advisor\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\hashtag-strategy-advisor\logs\` |
| System prompt | `templates\creator\hashtag-strategy-advisor\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_hashtag_strategy` (bound to `hashtag_strategy_advisor.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **7 Constitution rules** specialising Articles I, II, III, V, VII for hashtag-strategy work
- **5 hard refusals**: auto-publish without consent gate; engagement-bait family tags; misleading category claims (fake `trending`); over-ship beyond the platform cap; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × `--demo` × `x` × 5 | Reach-without-relevance paradox firing on `#AI` (educational pin) |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × `--demo-productivity` × `linkedin` × 5 | Healthy 4-category mix (no paradox); runner returns 4 not 5 (no off-niche padding) |

Together the two examples cover the full surface: the paradox firing (AI demo), the clean baseline (productivity demo), the explicit ship-cap statement (both), the no-off-niche-padding behavior (productivity demo), the engagement-bait blocklist (both — neither output contains a `#FF` family tag), and the branded-tag-too-early soft warning (both).

---

## v1 limitation note

The runner's hashtag library is a **curated 15-tag set** tuned for AI/agents, productivity, and broad creator niches. Hashtags outside this library cannot be recommended in v1. A future v2 with niche-specific library extensions or LLM-assisted tag discovery would expand the surface while preserving the same scoring, paradox detection, ship-cap, anti-bait, and branded-tag-too-early invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric scoring with weighted formula
2. The deterministic library-driven recommendation set
3. The reach-without-relevance paradox detection
4. The platform-specific ship cap (stated in every output)
5. The honest trending category check (refuses to fake velocity)
6. The branded-tag-too-early soft warning
7. The engagement-bait blocklist (enforced at library + output)
8. The deterministic seed (re-runnable for the same inputs)

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P80 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P82 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing tactical-discovery layer that turns "which hashtags should I use?" from a stuffing-or-skip dilemma into a structured 5-10 scored set with explicit ship caps — without engagement-bait, without fake trending claims, without auto-publishing anywhere.
