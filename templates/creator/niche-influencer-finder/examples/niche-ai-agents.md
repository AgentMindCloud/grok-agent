<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community — example output of the Niche Influencer Finder. -->

# Example output — niche: AI / agent builders

> 🔒 **Aggregate-only.** Every Top-Influencer card below is a paraphrased archetype, never a real X account. The runner accepts no influencer handles as input — only niche keywords — and the renderer's privacy guard refuses to emit any output containing a plausibly-shaped `@handle` other than the creator's own.
>
> *Built for xAI, X, Grok and the ecosystem community — this is what a healthy AI-niche discovery report looks like, with a Macro-tier engagement-pod paradox surfaced as a warning candidate.*

| Field | Value |
|---|---|
| Creator handle | `@JanSol0s` |
| Niche keywords | `AI agents`, `LLM ops`, `infra` |
| Follower band | 5,000 – 500,000 (default — all 3 tiers) |
| Focus | `all` |
| Sections emitted | **6** (no Discovery Audit — sample ≥ 2 keywords and red flags ≤ 3) |
| Engagement-pod paradox? | **Yes** — Macro tier (AI-influencer commentator), surfaced in BOTH archetype card AND Red Flags |

To regenerate this output deterministically:

```powershell
python .\run.py --x-handle JanSol0s --niche-keywords "AI agents, LLM ops, infra" --focus all --no-banner
```

---

## Influencer Summary
**@JanSol0s: 5 niche-aligned archetypes surfaced across 3 tier(s) — the engagement-pod paradox is active in the candidate set, verify before outreach.**

The discovery surfaced 5 archetypes (2 Micro, 2 Mid, 1 Macro). The strongest match is the newsletter operator + podcaster (Tier: Mid, Match score 72/100), with Authority 79/100 and Audience fit 75/100. The dominant collaboration angle is podcast-swap, and the keyword input (3 keyword(s)) anchored the audience-fit signal. 1 archetype(s) flagged for the engagement-pod paradox.

## Top Influencers (paraphrased — no real handles)

### Mid · Newsletter operator + podcaster · Match score: 72/100
- **Authority**: 79/100 — Mid tenure with consistent depth signal in long-form posts.
- **Engagement**: 51/100 — Moderate engagement with a passive-likes tail.
- **Audience fit**: 75/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 82/100 — Strong collab history — accepts cross-posts and guest swaps.
- **Why this archetype matches**: Operates a 30k-subscriber niche newsletter and a flagship podcast; swaps guest slots with peers monthly.
- **Suggested first move**: podcast-swap

### Micro · Productivity coach + book author · Match score: 71/100
- **Authority**: 79/100 — Mid tenure with consistent depth signal in long-form posts.
- **Engagement**: 54/100 — Moderate engagement with a passive-likes tail.
- **Audience fit**: 80/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 69/100 — Strong collab history — accepts cross-posts and guest swaps.
- **Why this archetype matches**: Long tenure in the niche with a published book; guests on 3-4 niche podcasts per quarter.
- **Suggested first move**: podcast-swap

### Micro · OSS-builder solo dev · Match score: 70/100
- **Authority**: 77/100 — Mid tenure with consistent depth signal in long-form posts.
- **Engagement**: 68/100 — Healthy mix of substantive replies and reposts.
- **Audience fit**: 65/100 — Solid niche overlap; adjacent-niche tail dilutes the core.
- **Collaboration potential**: 67/100 — Strong collab history — accepts cross-posts and guest swaps.
- **Why this archetype matches**: Ships new niche-aligned OSS releases monthly; engages substantively in replies but rarely reposts.
- **Suggested first move**: thread-collab

### Mid · Mid-tier infra blogger · Match score: 70/100
- **Authority**: 81/100 — Long tenure with citations across adjacent niches.
- **Engagement**: 62/100 — Healthy mix of substantive replies and reposts.
- **Audience fit**: 71/100 — Audience overlaps creator's niche keywords heavily.
- **Collaboration potential**: 61/100 — Some collab history; openness to outreach is plausible.
- **Why this archetype matches**: Weekly long-form blog posts cross-posted to X; strong overlap on infra and tooling keywords.
- **Suggested first move**: thread-collab

### Macro · AI-influencer commentator · Match score: 64/100
- **Authority**: 47/100 — Tenure thin; depth signal limited to short-form posts.
- **Engagement**: 76/100 — Engagement far above niche peers — verify substance vs volume.
- **Audience fit**: 64/100 — Solid niche overlap; adjacent-niche tail dilutes the core.
- **Collaboration potential**: 74/100 — Strong collab history — accepts cross-posts and guest swaps.
> ⚠️ paradox: engagement is far above niche peers despite low authority signal — likely pod activity.
- **Why this archetype matches**: Reacts to every major niche release within hours; high engagement masks thin authority — verify before reaching out.
- **Suggested first move**: quote-tweet-rally

## Collaboration Opportunities

1. **podcast-swap** with Newsletter operator + podcaster — Each guest on the other's flagship show within the same month; cross-promote in advance. Expected lift: ~10% sustained follower gain; works best when audiences overlap < 40%.
2. **podcast-swap** with Productivity coach + book author — Each guest on the other's flagship show within the same month; cross-promote in advance. Expected lift: ~10% sustained follower gain; works best when audiences overlap < 40%.
3. **thread-collab** with OSS-builder solo dev — Coordinated 5-post thread series; one post per author, cross-quoted on publish day. Expected lift: 2x reply volume vs solo thread; light scheduling overhead.
4. **thread-collab** with Mid-tier infra blogger — Coordinated 5-post thread series; one post per author, cross-quoted on publish day. Expected lift: 2x reply volume vs solo thread; light scheduling overhead.
5. **quote-tweet-rally** with AI-influencer commentator — Coordinate a launch-day quote-tweet train around the creator's next anchor post. Expected lift: 3-5x reach for 24h; needs day-of timing precision.

## Red Flags

- **Engagement-pod paradox** · severity: high — 1 archetype(s) — AI-influencer commentator — show Engagement above 70 while Authority sits below 50. Aggregate engagement is likely amplified by pod activity. *Remediation:* Score the paradox archetype's followers via `follower-quality-analyzer` before any outreach; treat the engagement signal as unverified until then.
- **Sparse Macro-tier signal** · severity: low — Macro-tier matches are scarce in this niche — outreach hit-rate will lean on Micro and Mid archetypes. *Remediation:* Use `competitor-watch` to identify which Macro accounts adjacent creators have collabbed with this quarter.

## Recommendations

1. Build a co-authored long-form thread the highest-Match archetype can quote-tweet; this often opens the door for the next collab cycle. — bridges to: `thread-builder`
2. If any of these collabs surface a paid-placement option, model the value before negotiating sponsorship terms. — bridges to: `monetization-optimizer`

   > ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.
3. Snapshot follower-count and engagement on the day of and 14 days after each collab to measure real lift, not vanity reach. — bridges to: `analytics-summarizer`
4. For any paradox archetype, pull deeper background via `research-assistant` before pitching — verify their niche claims with adjacent sources. — bridges to: `research-assistant`
5. Generate 3 co-content angles per archetype before the first outreach so the DM has a concrete pitch attached, not just an introduction. — bridges to: `content-idea-generator`

## Confidence
Confidence: high — 3 keywords cover the niche cleanly and 3 tiers are represented.

---

## What this output demonstrates (audit checklist)

- [x] **4 official Match Score metrics** in fixed row order (Authority / Engagement / Audience fit / Collaboration potential) on every Top-Influencer card
- [x] **Weighted Match score formula** `round(0.30A + 0.25E + 0.25F + 0.20C)` applied per card (e.g. Newsletter operator: 0.30·79 + 0.25·51 + 0.25·75 + 0.20·82 = 23.7 + 12.75 + 18.75 + 16.4 = 71.6 → 72)
- [x] **5 Top-Influencer cards** spanning all 3 tiers (2 Micro, 2 Mid, 1 Macro) — exceeds the "≥ 2 tiers when band allows" rule
- [x] **Engagement-pod paradox** raised in BOTH the archetype card (under the Engagement row) AND the Red Flags section (AI-influencer commentator: Authority 47 < 50, Engagement 76 > 70)
- [x] **5 Collaboration Opportunities**, each pairing a first-move format with a surfaced archetype
- [x] **2 Red Flag cards** with severity (Engagement-pod paradox = high, Sparse Macro-tier signal = low)
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** in Recommendations (`thread-builder`, `monetization-optimizer`, `analytics-summarizer`, `research-assistant`, `content-idea-generator`) — exceeds the ≥3 requirement
- [x] **Article V.1 disclaimer verbatim** under the monetization recommendation (the only one that touches paid placements / sponsorships)
- [x] **Confidence line** = high (3 keywords + 3 tiers represented)
- [x] **Aggregate-only privacy** — zero real X account handles in the report body

The Red Flag remediations cite 2 additional cross-template slugs (`follower-quality-analyzer`, `competitor-watch`), bringing the total distinct cross-template surface area in this report to **7 templates** — so a creator can act on every finding without leaving Grok Agent OS.

---

> Built for xAI, X, Grok and the ecosystem community — Apache 2.0 licensed, aggregate-only, local-first.
