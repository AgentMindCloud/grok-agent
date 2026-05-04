<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win — example output of the Niche Influencer Finder. -->

# Example output — niche: productivity / habit-stacking

> 🔒 **Aggregate-only.** Every Top-Influencer card below is a paraphrased archetype, never a real X account. The runner accepts no influencer handles as input — only niche keywords — and the renderer's privacy guard refuses to emit any output containing a plausibly-shaped `@handle` other than the creator's own.
>
> *Built to help xAI and Grok win — productivity creators see the engagement-pod paradox earliest because giveaway-driven growth pulls authenticity down before the Mid-tier accounts they look up to even notice.*

| Field | Value |
|---|---|
| Creator handle | `@habitstacker` |
| Niche keywords | `productivity`, `habit stacking`, `deep work` |
| Follower band | 5,000 – 200,000 (Mid-tier ceiling — Macro intentionally excluded) |
| Focus | `collaboration_potential` |
| Sections emitted | **6** (no Discovery Audit — sample ≥ 2 keywords and red flags ≤ 3) |
| Engagement-pod paradox? | **Yes** — Mid tier (Engagement-pod regular), surfaced in BOTH archetype card AND Red Flags |

To regenerate this output deterministically:

```powershell
python .\run.py --x-handle habitstacker --niche-keywords "productivity, habit stacking, deep work" --max-followers 200000 --focus collaboration_potential --no-banner
```

---

## Influencer Summary
**@habitstacker: 5 niche-aligned archetypes surfaced across 2 tier(s) — the engagement-pod paradox is active in the candidate set, verify before outreach.**

The discovery surfaced 5 archetypes (2 Micro, 3 Mid). The strongest match is the indie llm-infra founder (Tier: Micro, Match score 74/100), with Authority 85/100 and Audience fit 82/100. The dominant collaboration angle is co-authored-post, and the keyword input (3 keyword(s)) anchored the audience-fit signal. 1 archetype(s) flagged for the engagement-pod paradox.

## Top Influencers (paraphrased — no real handles)

### Micro · Indie LLM-infra founder · Match score: 74/100
- **Authority**: 85/100 — Long tenure with citations across adjacent niches.
- **Engagement**: 57/100 — Healthy mix of substantive replies and reposts.
- **Audience fit**: 82/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 70/100 — Strong collab history — accepts cross-posts and guest swaps.
- **Why this archetype matches**: Active in the same niche keywords; regularly co-authors with peers and accepts joint long-form invites.
- **Suggested first move**: co-authored-post

### Mid · Mid-tier infra blogger · Match score: 71/100
- **Authority**: 80/100 — Long tenure with citations across adjacent niches.
- **Engagement**: 57/100 — Healthy mix of substantive replies and reposts.
- **Audience fit**: 78/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 64/100 — Some collab history; openness to outreach is plausible.
- **Why this archetype matches**: Weekly long-form blog posts cross-posted to X; strong overlap on infra and tooling keywords.
- **Suggested first move**: thread-collab

### Mid · Eval-tooling researcher · Match score: 68/100
- **Authority**: 84/100 — Long tenure with citations across adjacent niches.
- **Engagement**: 49/100 — Moderate engagement with a passive-likes tail.
- **Audience fit**: 72/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 61/100 — Some collab history; openness to outreach is plausible.
- **Why this archetype matches**: Long-form posts cited by adjacent niches monthly; audience overlaps creator's niche with a research-methods tail.
- **Suggested first move**: podcast-swap

### Micro · Productivity coach + book author · Match score: 67/100
- **Authority**: 69/100 — Mid tenure with consistent depth signal in long-form posts.
- **Engagement**: 55/100 — Healthy mix of substantive replies and reposts.
- **Audience fit**: 72/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 73/100 — Strong collab history — accepts cross-posts and guest swaps.
- **Why this archetype matches**: Long tenure in the niche with a published book; guests on 3-4 niche podcasts per quarter.
- **Suggested first move**: podcast-swap

### Mid · Engagement-pod regular · Match score: 59/100
- **Authority**: 40/100 — Authority signal weak — depth not visible in recent posts.
- **Engagement**: 77/100 — Engagement far above niche peers — verify substance vs volume.
- **Audience fit**: 60/100 — Solid niche overlap; adjacent-niche tail dilutes the core.
- **Collaboration potential**: 66/100 — Strong collab history — accepts cross-posts and guest swaps.
> ⚠️ paradox: engagement is far above niche peers despite low authority signal — likely pod activity.
- **Why this archetype matches**: High aggregate engagement on every post; low authority signal and rapid follower-count climb suggest pod activity.
- **Suggested first move**: dm-intro

## Collaboration Opportunities

1. **co-authored-post** with Indie LLM-infra founder — Joint long-form on a shared niche pain-point. Creator drafts, archetype edits + signs. Expected lift: 1.5-3x typical post; ships in 2 weeks if cadence aligns.
2. **thread-collab** with Mid-tier infra blogger — Coordinated 5-post thread series; one post per author, cross-quoted on publish day. Expected lift: 2x reply volume vs solo thread; light scheduling overhead.
3. **podcast-swap** with Eval-tooling researcher — Each guest on the other's flagship show within the same month; cross-promote in advance. Expected lift: ~10% sustained follower gain; works best when audiences overlap < 40%.
4. **podcast-swap** with Productivity coach + book author — Each guest on the other's flagship show within the same month; cross-promote in advance. Expected lift: ~10% sustained follower gain; works best when audiences overlap < 40%.
5. **dm-intro** with Engagement-pod regular — Cold but specific outreach DM citing 2 of the archetype's recent posts; propose one tiny first step. Expected lift: 15-25% reply rate when DM cites concrete shared work.

## Red Flags

- **Engagement-pod paradox** · severity: high — 1 archetype(s) — Engagement-pod regular — show Engagement above 70 while Authority sits below 50. Aggregate engagement is likely amplified by pod activity. *Remediation:* Score the paradox archetype's followers via `follower-quality-analyzer` before any outreach; treat the engagement signal as unverified until then.
- **Tier-coverage gap** · severity: low — No archetypes surfaced in the Macro tier(s) despite the requested band 5,000-200,000 including them. *Remediation:* Widen `--niche-keywords` (add 1-2 adjacent terms) and re-run; sparse keywords concentrate matches in a single tier.

## Recommendations

1. Snapshot follower-count and engagement on the day of and 14 days after each collab to measure real lift, not vanity reach. — bridges to: `analytics-summarizer`
2. If any of these collabs surface a paid-placement option, model the value before negotiating sponsorship terms. — bridges to: `monetization-optimizer`

   > ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.
3. Generate 3 co-content angles per archetype before the first outreach so the DM has a concrete pitch attached, not just an introduction. — bridges to: `content-idea-generator`
4. Score each surfaced archetype's followers via `follower-quality-analyzer` before sending the first DM — confirms real reach, not pod traffic. — bridges to: `follower-quality-analyzer`
5. Build a co-authored long-form thread the highest-Match archetype can quote-tweet; this often opens the door for the next collab cycle. — bridges to: `thread-builder`

## Confidence
Confidence: high — 3 keywords cover the niche cleanly and 2 tiers are represented.

---

## What this output demonstrates (audit checklist)

- [x] **4 canonical Match Score metrics** in fixed row order (Authority / Engagement / Audience fit / Collaboration potential) on every Top-Influencer card
- [x] **Weighted Match score formula** `round(0.30A + 0.25E + 0.25F + 0.20C)` applied per card (e.g. Indie LLM-infra founder: 0.30·85 + 0.25·57 + 0.25·82 + 0.20·70 = 25.5 + 14.25 + 20.5 + 14 = 74.25 → 74)
- [x] **5 Top-Influencer cards** spanning the 2 in-band tiers (2 Micro, 3 Mid) — Macro intentionally excluded by the `--max-followers 200000` cap
- [x] **Engagement-pod paradox** raised in BOTH the archetype card (under the Engagement row) AND the Red Flags section (Engagement-pod regular: Authority 40 < 50, Engagement 77 > 70)
- [x] **5 Collaboration Opportunities**, each pairing a first-move format with a surfaced archetype
- [x] **2 Red Flag cards** with severity (Engagement-pod paradox = high, Tier-coverage gap = low)
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** in Recommendations (`analytics-summarizer`, `monetization-optimizer`, `content-idea-generator`, `follower-quality-analyzer`, `thread-builder`) — exceeds the ≥3 requirement
- [x] **Article V.1 disclaimer verbatim** under the monetization recommendation (the only one that touches paid placements / sponsorships)
- [x] **Confidence line** = high (3 keywords + 2 tiers represented)
- [x] **Aggregate-only privacy** — zero real X account handles in the report body

The Red Flag remediations cite 1 additional cross-template slug (`follower-quality-analyzer` again, plus the implicit "widen keywords" guidance), bringing the total distinct cross-template surface area in this report to **5 templates**. The `dm-intro` first move on the paradox archetype intentionally surfaces the warning as something the creator can act on without scaling outreach to it — verify first via `follower-quality-analyzer`, then escalate or drop.

### Compared to the AI-niche example

| Dimension | `niche-ai-agents.md` | `niche-productivity.md` |
|---|---|---|
| Tier coverage | 3 tiers (Micro + Mid + Macro) | 2 tiers (Micro + Mid; Macro excluded) |
| Strongest match | Newsletter operator + podcaster (Mid, 72) | Indie LLM-infra founder (Micro, 74) |
| Paradox archetype | AI-influencer commentator (Macro, Match 64) | Engagement-pod regular (Mid, Match 59) |
| Paradox severity flavour | Macro reach masking thin authority | Mid-tier giveaway-style engagement |
| Tier-coverage flag? | No (all 3 tiers populated) | Yes (Macro empty by band cap) |
| Focus nudge | none (focus=all) | +4 to Collaboration potential |

Same schema and rules, different inputs → different recommendations → different cross-template mix. The runner's deterministic seeding makes both outputs reproducible bit-for-bit from the PowerShell snippets above.

---

> Built to help xAI and Grok win — Apache 2.0 licensed, aggregate-only, local-first.
