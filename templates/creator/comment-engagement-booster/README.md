<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 💬 Comment Engagement Booster

> Turn any post into 3-5 distinct, on-voice comment variants under 240 chars each, spanning a chosen boost focus (question / controversy / story / poll / all). 4 canonical Comment Plan Score metrics, hook-without-substance paradox detection, anti-spam token-overlap guard, ≥3 cross-template bridges. Drafts only. Never mass-identical.
>
> *Built to help xAI and Grok win the platform battle on X — every X creator deserves comments with substance, not stuffing.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This template emits comment text the creator reviews and ships themselves. The runner never auto-publishes. Constitution Article II's `publish_to_x` consent gate covers every variant.

> 🔒 **Anti-spam guard.** The runner refuses to emit two variants that share more than 60% token overlap, AND requires every variant to score ≥ 60/100 on the Distinct angle metric. Mass-identical comments are X-policy abuse and a hard refusal in this template.

> 🔒 **No misrepresentation.** When commenting on another creator's post, the runner never puts words in their mouth, never claims authorship of their idea, never frames the comment as if they agreed with a position they didn't take.

> 🔒 **Comment length cap.** Every variant body is ≤ 240 characters before any attribution wrapping. X reply UI rewards readable density — the runner does NOT pad to 280.

> 🔒 **Local-first.** All input and output stays on your Windows machine under `$env:LOCALAPPDATA\grok-agent\comment-engagement-booster\`. The v1 runner makes zero external network calls — it is offline-safe.

> ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

The Article V.1 banner above attaches automatically to any recommendation that touches monetization tactics, paid-tier funnel comments, or sponsorship-content adaptations.

---

## What it is

A **CLI-only creator-template** (`grok-agent.yaml` v2.15, `kind: creator-template`, `runtime: cli_only`) that turns one post (URL or pasted text) plus a chosen `boost_focus` into a 6/7-section structured set of 3-5 distinct comment variants.

The report shape is the same every time:

1. **Post Snapshot** — one-sentence summary + 5-bullet metadata
2. **Comment Plan** — aggregate Comment Plan score across the variant set
3. **Comment Variants** — 3-5 cards, each with the 4-row Comment Plan Score table (Hook strength / Conversation potential / Voice fidelity / Distinct angle), the weighted Comment Plan score `round(0.30·Hook + 0.25·Conv + 0.25·Voice + 0.20·Distinct)`, and a code-fenced comment body under 240 chars
4. **Engagement Tips** — 3-5 concrete posting moves (reply velocity, self-thread follow-up, pin pattern)
5. **Red Flags** — 2-4 cards with severity, surfaces the **hook-without-substance paradox** in BOTH this section AND the relevant variant card when Hook strength > 70 AND Conversation potential < 30
6. **Recommendations** — 3-5 next moves, each linking to ≥3 distinct cross-template bridges
7. **Confidence**
8. **Boost Audit** *(optional, auto-appended)* — triggers when red-flag count > 3 OR boost_focus = `all`

---

## Quick Launch (Windows 11 + PowerShell)

**TL;DR — one PowerShell line, no install:**

```powershell
python .\templates\creator\comment-engagement-booster\run.py --x-handle JanSol0s --demo --boost-focus question --num-comments 4
```

That prints the 7-section report (4 distinct question variants — variant 2 pinned to the hook-without-substance paradox profile for educational rule demonstration) straight to your terminal.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install comment-engagement-booster
```

### Option B — direct invocation (developer mode)

```powershell
# Question-focused 4 variants on a real post
python .\templates\creator\comment-engagement-booster\run.py `
  --x-handle JanSol0s `
  --post-url-or-text "Most agent eval suites measure the wrong thing — they reward verbosity, not action correctness." `
  --boost-focus question `
  --num-comments 4

# Story-focused on a productivity post
python .\templates\creator\comment-engagement-booster\run.py `
  --x-handle habitstacker `
  --demo-productivity `
  --boost-focus story `
  --num-comments 3

# Controversy variants on a strong-claim post
python .\templates\creator\comment-engagement-booster\run.py `
  --x-handle JanSol0s `
  --post-url-or-text "..." `
  --boost-focus controversy `
  --num-comments 5

# 'all' focus (runner picks the best angle for the post)
python .\templates\creator\comment-engagement-booster\run.py `
  --x-handle JanSol0s `
  --demo `
  --boost-focus all

# Save the report (Apache 2.0 HTML header is prepended)
python .\templates\creator\comment-engagement-booster\run.py `
  --x-handle JanSol0s `
  --demo `
  --output $env:LOCALAPPDATA\grok-agent\comment-engagement-booster\reports\2026-05-04.md
```

### Flag reference

| Flag | Required? | What it does |
|---|---|---|
| `--x-handle` | yes | Creator handle (with or without `@`) |
| `--post-url-or-text` | yes (or `--demo` / `--demo-productivity`) | Either an `x.com` URL or the literal post text |
| `--boost-focus` | optional | `question` \| `controversy` \| `story` \| `poll` \| `all` (default `question`) |
| `--num-comments` | optional | 3–5 (default 3) |
| `--demo` | optional | Use the canonical AI-niche demo post; pins variant 2 to the paradox profile educationally |
| `--demo-productivity` | optional | Use a productivity demo post; healthy variants (no paradox) |
| `--output` | optional | Save the report to a path (Apache 2.0 HTML header is prepended) |
| `--no-banner` | optional | Suppress the runner banner on stdout |
| `--show-system-prompt` | optional | Print loaded system-prompt path + size on stderr |

---

## How the report is shaped (the 6 hard rules)

1. **Drafts only.** Output is text the creator pastes into a comment box; the runner never publishes anything.
2. **Anti-spam guard.** Inter-variant token overlap > 60% triggers a `RuntimeError` from the runner before the report renders. Every variant scores ≥ 60/100 on Distinct angle. The runner refuses to emit comment-spam stacks even when called with high `num_comments`.
3. **Hook-without-substance paradox** must surface in BOTH the variant card AND the Red Flags section when Hook strength > 70 AND Conversation potential < 30. The runner's `--demo` mode pins variant 2 to this profile so the rule reliably demonstrates.
4. **Comment Plan score formula is fixed.** `round(0.30·Hook + 0.25·Conv + 0.25·Voice + 0.20·Distinct)`. Hook strength weighted highest because if the opener doesn't stop the scroll, no other metric matters.
5. **Comment-length cap = 240 chars.** Each variant body is enforced ≤ 240 characters by the runner before attribution wrap. Tight beats long in reply UI surfaces.
6. **No misrepresentation.** The runner generates comments that respond to the post being commented on; it never puts words in another creator's mouth or claims their ideas as the user's own.

---

## Cross-template daily flow (Grok Agent OS for creators)

Comment Engagement Booster is the conversation-velocity layer of the Grok Agent OS creator suite. The recommended per-anchor flow:

```
┌──────────────────────────────────────────────────────────────────┐
│  Pre-comment — design the variants                                │
│  └─ comment-engagement-booster → 3-5 distinct variants            │
│       │                                                           │
│       ├─ paradox flagged?      → ship as quote-tweet, not comment │
│       ├─ voice drift?          → brand-voice-trainer to re-anchor │
│       └─ all clean?            → pick variant 1, hold the rest    │
│                                                                   │
│  Ship                                                             │
│  └─ creator pastes variant 1 into the X reply box                 │
│  └─ ship within 30 minutes of the post going live                 │
│                                                                   │
│  Mid-comment-life (T+6h)                                          │
│  └─ self-thread follow-up question to keep the chain alive        │
│  └─ pin if a substantive reply chain forms                        │
│                                                                   │
│  Post-comment (T+24h, T+7d)                                       │
│  └─ analytics-summarizer → reply rate per variant                 │
│  └─ ab-test-suggester    → promote the best 2 variants to A/B     │
│  └─ thread-builder       → if a variant lands hard, build a thread│
│                                                                   │
│  Per-week                                                         │
│  └─ rotate the held variants into sibling posts (one per anchor)  │
│  └─ never ship all 3-5 to the same anchor (anti-spam Rule 2)      │
└──────────────────────────────────────────────────────────────────┘
```

The bridges this template knows about (every output uses ≥3 distinct):

| Bridge slug | Folder | Why this template links to it |
|---|---|---|
| `thread-builder` | `templates/creator/` | Build a follow-on long-form thread when a comment lands hard |
| `quote-tweet-suggestor` | `templates/creator/` | Promote a paradox-flagged hook from comment to quote-tweet |
| `analytics-summarizer` | `templates/creator/` | Snapshot reply-rate per variant at T+24h and T+7d |
| `brand-voice-trainer` | `templates/creator/` | Verify all variants land in voice; voice drift confounds the variant set |
| `reply-drafter` | `templates/creator/` | Draft on-voice replies to the comments the variants attract |
| `mention-summarizer` | `templates/creator/` | Roll up which variant attracted the most substantive mentions |
| `ab-test-suggester` | `templates/creator/` | Promote a 2-variant comparison into a structured A/B once one wins |
| `competitor-watch` | `templates/creator/` | Spot which angles competitors over-use; counter-position |
| `content-idea-generator` | `templates/creator/` | Source the next post in the cluster of the comment that won |
| `monetization-optimizer` | `templates/creator/` | Tune monetization-aware comments separately (carries V.1 disclaimer) |
| `cross-platform-reposter` | `templates/creator/` | Adapt a winning comment angle into a LinkedIn / Newsletter section |
| `research-assistant` | `templates/general/` | Background when the controversy angle requires sourcing |

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| Saved reports | `$env:LOCALAPPDATA\grok-agent\comment-engagement-booster\reports\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\comment-engagement-booster\cache\` |
| Logs | `$env:LOCALAPPDATA\grok-agent\comment-engagement-booster\logs\` |
| System prompt | `templates\creator\comment-engagement-booster\prompts\system.md` (in-repo) |

The runner does not write anything by default. Saved reports only land on disk when you pass `--output <path>`.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-template`
- **1 Grok-callable tool**: `generate_comment_variants` (bound to `comment_engagement_booster.run.generate`)
- **0 declared public APIs**: v1 is fully offline; the runner makes no network calls
- **6 Constitution rules** specialising Articles I, II, III, V, VII for comment-engagement work
- **5 hard refusals**: auto-publish without consent gate; mass-identical comments (>60% token overlap); coordinated mass-engagement / report-brigading; misrepresenting the post being commented on; scrape authenticated content
- **Cost limits**: $0.30 per session, $1.00 per day, 60k tokens, 80 API calls per session
- **Human-in-the-loop**: enabled, 60-second timeout
- **PII handling**: `local-only`
- **Data retention**: 90 days

---

## Examples

Two realistic, copy-paste-ready outputs ship in [`examples/`](./examples/):

| File | Niche | Inputs | Headline insight |
|---|---|---|---|
| [`examples/niche-ai-agents.md`](./examples/niche-ai-agents.md) | AI / agent builders | `@JanSol0s` × `--demo` × `question` × 4 variants | Hook-without-substance paradox firing (variant 2 pinned for educational demo) |
| [`examples/niche-productivity.md`](./examples/niche-productivity.md) | Productivity / habit-stacking | `@habitstacker` × `--demo-productivity` × `story` × 3 variants | Healthy story-angle baseline (no paradox; story focus naturally lifts Conversation potential) |

Together the two examples cover the full surface: the paradox firing (AI demo), the clean baseline (productivity demo), the anti-spam guard (both — no pair shares >60% token overlap), and the 240-char comment cap (every variant in both examples).

---

## v1 limitation note

Like the prior runners in the suite, the variant scaffolds are **deterministic per-focus templates** — they wrap a 240-char comment around a single-axis framing (clarifying question / personal anecdote / respectful counter-take / etc.). A future v2 with Grok 4.3 in the loop would generate fully paraphrased comment variants while preserving the same scoring, paradox detection, anti-spam enforcement, length-cap, and no-misrepresentation invariants this v1 already enforces.

The value the runner adds in v1:
1. The 4-metric scoring with weighted formula
2. The deterministic per-focus variant library (5 distinct angles per focus, picked by `num_comments`)
3. The hook-without-substance paradox detection
4. The anti-spam token-overlap guard (refuses to emit pairs > 60% similar)
5. The comment-length cap enforcement (≤ 240 chars)
6. The deterministic seed (re-runnable for the same inputs)

---

## Build slots (Recipe B)

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + system prompt | `grok-agent.yaml`, `prompts/system.md` | ✅ P79 |
| 2 — Runner + README + examples | `run.py`, `README.md`, `examples/` | ✅ P81 (this prompt) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win the agent platform battle on X. This template is the missing conversation-velocity layer that turns "what should I comment?" from a vibes-check into a structured 3-5 variant set with explicit anti-spam enforcement — without bait-without-follow-through, without mass-identical stacks, without auto-publishing anywhere.
