<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community — example output of the Hashtag Strategy Advisor. -->

# Example output — niche: productivity / habit-stacking (healthy 4-category mix)

> 🔒 **Drafts only.** Hashtag recommendations below are text the creator pastes into their own post copy. The runner never auto-publishes.
>
> 🔒 **Ship cap stated explicitly.** LinkedIn = 0-3 hashtags per post. The recommendation set returns 4 tags scoring across 4 categories; the creator picks the right subset for the cap.
>
> *Built for xAI, X, Grok and the ecosystem community — productivity creators tend to over-stuff posts with `#Productivity`, `#Habits`, `#Mindset`, `#Growth` etc. The 4-category mix below shows what a tight, on-niche set looks like instead.*

| Field | Value |
|---|---|
| Creator handle | `@habitstacker` |
| Topic | `Stop optimizing for the morning routine — optimize for the friction your evening self leaves the morning self to clean up.` |
| Target platform | `linkedin` (ship cap 0-3) |
| Variants requested | **5** hashtags |
| Focus | `all` |
| Sections emitted | **7** (no Hashtag Audit — single platform and red flags ≤ 3) |
| Reach-without-relevance paradox? | **No** — heuristic scoring on the productivity-focused recommendation set keeps Niche relevance comfortably above 35 across all picks |
| Categories represented | **4** (specific-niche × 1, broad-niche × 1, community × 1, branded × 1) |
| Tags returned | **4** (one less than requested — runner refuses to pad with off-niche tags rather than inflate the count) |

To regenerate this output deterministically:

```powershell
python .\run.py --x-handle habitstacker --demo-productivity --platform linkedin --num-hashtags 5 --focus all --no-banner
```

---

## Topic Snapshot
**@habitstacker: hashtags should land in the niche cluster, not the wider conversation.**

- **Creator handle**: @habitstacker
- **Topic / post**: Stop optimizing for the morning routine
- **Target platform**: linkedin
- **Ship cap**: 0-3 (LinkedIn)
- **Focus**: all

## Hashtag Plan

**Aggregate Hashtag Plan score**: 66/100 — averaged across 4 recommendations.

## Recommended Hashtags

### #HabitStacking · category: specific-niche · Hashtag Plan score: 74/100
- **Niche relevance**: 87/100 — Sits inside the creator's stated cluster.
- **Reach potential**: 53/100 — Small but rapidly engaged audience; initial reach is the creator's followers.
- **Engagement quality**: 71/100 — Niche-active accounts dominate; substantive replies common.
- **Cleanliness**: 86/100 — Low spam exposure.
- **Why this fits**: Direct semantic match to the topic; pairs with adjacent specific-niche tags.
- **Ship priority**: high

### #habitstackerNotes · category: branded · Hashtag Plan score: 69/100
- **Niche relevance**: 92/100 — By definition aligned to the creator's niche.
- **Reach potential**: 25/100 — Small but rapidly engaged audience; initial reach is the creator's followers.
- **Engagement quality**: 70/100 — Niche-active accounts dominate; substantive replies common.
- **Cleanliness**: 89/100 — Low spam exposure.
- **Why this fits**: Builds long-term branded-tag equity through consistent use across the creator's posts.
- **Ship priority**: low

### #WriteEveryDay · category: community · Hashtag Plan score: 64/100
- **Niche relevance**: 57/100 — Solid niche overlap; adjacent-niche tail dilutes the core.
- **Reach potential**: 64/100 — Moderate audience; growing.
- **Engagement quality**: 63/100 — Mixed engagement; substantive + drive-by likes both present.
- **Cleanliness**: 77/100 — Low spam exposure.
- **Why this fits**: Tribal / culture tag — fits the creator's posting style and signals tribe membership.
- **Ship priority**: medium

### #Productivity · category: broad-niche · Hashtag Plan score: 56/100
- **Niche relevance**: 45/100 — Too broad; pulls in non-niche audience.
- **Reach potential**: 88/100 — Massive audience; high impression potential.
- **Engagement quality**: 41/100 — Drive-by likes dominate; low substantive reply density.
- **Cleanliness**: 50/100 — Heavy bot / engagement-pod traffic — tag carries reputation risk.
- **Why this fits**: Broad-niche audience; useful when paired with at least one specific-niche tag.
- **Ship priority**: medium

## Strategy Tips

1. **Ship 1 specific-niche tag, not 2** — On X, one well-chosen specific-niche tag often outperforms a paired stack — the algorithm penalises hashtag-heavy posts.
2. **Hold broad-niche tags for LinkedIn** — LinkedIn's longer post format absorbs broad-niche tags better than X's reply surface; reserve broad-niche for the LinkedIn variant via cross-platform-reposter.
3. **Build the branded-tag habit slowly** — Branded tags compound only when used consistently across 4-6+ months. Use sparingly until the habit is locked.
4. **Community tags work best on the post that earns them** — Don't bolt a community tag onto a post that doesn't actually speak to the tribe — community moderation reads off-topic stuffing as noise.
5. **No honest trending tag fit this topic** — The runner found no trending tag whose trigger keywords match the topic. Riding an unrelated trending tag is algorithm-manipulation and refused outright.

## Red Flags

- **Branded-tag-too-early** · severity: low — #habitstackerNotes is the creator's own tag; initial reach is just the existing follower base. Branded tags compound only after 4-6+ months of consistent use. *Remediation:* Use the branded tag sparingly until follower count and consistent-use habit are both locked.

## Recommendations

1. Adapt the hashtag set when cross-posting via `cross-platform-reposter` — X 0-2, LinkedIn 0-3, Bluesky 0-2, Newsletter 0. — bridges to: `cross-platform-reposter`
2. If the post leads to a paid-tier launch, pair the strategy with `monetization-optimizer` before scaling the tag set. — bridges to: `monetization-optimizer`

   > ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.
3. Watch competitor formats via `competitor-watch` to see whether the broad-niche tags this report flagged are over-used in the niche. — bridges to: `competitor-watch`
4. Source the next anchor post in the cluster of the highest-scoring tag via `content-idea-generator`. — bridges to: `content-idea-generator`
5. Snapshot per-hashtag impressions and reply rate at T+24h via `analytics-summarizer` to log which tags compound for this audience. — bridges to: `analytics-summarizer`

## Confidence
Confidence: high — clear topic, 4 hashtags spanning 4 categories, ship cap stated explicitly.

---

## What this output demonstrates (audit checklist)

- [x] **4 canonical Hashtag Plan Score metrics** in fixed row order (Niche relevance / Reach potential / Engagement quality / Cleanliness) with HEALTHY scores — Niche relevance comfortably above 35 across all picks
- [x] **Weighted Hashtag Plan score formula** applied per the same `round(0.30·Niche + 0.25·Reach + 0.25·Engagement + 0.20·Cleanliness)` formula as example 1
- [x] **4 hashtags spanning 4 categories** (specific-niche / broad-niche / community / branded) — `#HabitStacking` and `#WriteEveryDay` both pulled in by the topic's "morning routine" keyword overlap
- [x] **No reach-without-relevance paradox** — production-mode heuristic scoring kept all Niche relevance scores above 35; this is the canonical healthy baseline
- [x] **Ship cap stated explicitly** — `0-3 (LinkedIn)` named in the Topic Snapshot; LinkedIn's longer format permits 1 more tag than X
- [x] **Honest trending category check** — runner found no trending tag whose trigger keywords match the topic; trending category intentionally empty
- [x] **Branded-tag-too-early soft warning** — `#habitstackerNotes` ships as `low` priority with an educational note about consistent-use compounding
- [x] **No off-niche padding** — runner returned 4 tags (1 less than the requested 5) rather than padding with unrelated broad-niche tags; this is the correct behavior
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** — exceeds the ≥3 requirement
- [x] **Anti-bait blocklist enforced** — output contains zero engagement-bait hashtags

### Compared to the AI-niche example

| Dimension | `niche-ai-agents.md` | `niche-productivity.md` |
|---|---|---|
| Platform | `x` (cap 0-2) | `linkedin` (cap 0-3) |
| Hashtags returned | 5 | 4 (runner refused to pad with off-niche tags) |
| Reach-without-relevance paradox? | Yes — `#AI` pinned in demo for educational rule firing | No — heuristic scoring on real topic stays in healthy bands |
| Trending category populated? | No (no honest velocity match for the topic) | No (no honest velocity match for the topic) |
| Ship priority distribution | high × 2 (specific-niche), medium × 1, low × 2 (paradox + branded) | high × 1, medium × 1, low × 2 (under-cap-comfortable + branded) |
| Demonstrates | The paradox firing path (educational) | The healthy-but-thin recommendation set (production-typical) |

Same schema and rules, different inputs → different rule demonstrations. Together the two examples cover the full surface of the hashtag-strategy-advisor's edge cases: the paradox firing (AI demo), the clean baseline (productivity demo), the ship-cap explicit-statement (both), the no-off-niche-padding behavior (productivity demo), and the engagement-bait blocklist (both — neither output contains a `#FF` family tag).

> **v1 limitation note:** the runner's hashtag library is a curated 15-tag set tuned for AI/agents, productivity, and broad creator niches. Hashtags outside this library cannot be recommended in v1 — a future v2 with niche-specific library extensions or LLM-assisted tag discovery would expand the surface while preserving the same scoring, paradox detection, ship-cap, anti-bait, and branded-tag-too-early invariants this v1 already enforces.

---

> Built for xAI, X, Grok and the ecosystem community — Apache 2.0 licensed, drafts-only, no-engagement-bait-by-default.
