<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community — example output of the Follower Quality Analyzer. -->

# Example output — niche: productivity / habit-stacking

> 🔒 **Aggregate-only.** Every Top-Follower card below is a paraphrased archetype, never a named account. The runner accepted 100 follower handles as input, but only the *count* and *seed-derived* aggregate signal flow into the rendered report.
>
> *Built for xAI, X, Grok and the ecosystem community — productivity creators see the bot-engagement paradox earliest because giveaway-driven growth pulls authenticity down before the headline numbers notice.*

| Field | Value |
|---|---|
| Creator handle | `@habitstacker` |
| Niche | Productivity / habit-stacking / deep work |
| Sample size | 100 followers |
| Focus | `all` |
| Niche median (engagement) | 45 (default) |
| Sections emitted | **6** (no Audience Health Audit — sample ≥ 50 and red flags ≤ 3) |
| Bot-engagement paradox? | **Yes** — borderline case, surfaced in BOTH Quality Scores AND Red Flags |

To regenerate this output deterministically:

```powershell
$lines = 300..399 | ForEach-Object { "@aggregate_$('{0:D5}' -f $_)" }
$lines | Out-File -Encoding utf8 sample.txt
python .\run.py --x-handle habitstacker --follower-file .\sample.txt --focus all --no-banner
```

---

## Headline
**@habitstacker: real audience underneath the engagement spike — but a low-authenticity tail is amplifying the headline number.**

## Quality Scores

| Metric | Score | Interpretation | 30d trend |
|---|---|---|---|
| Engagement quality | 49/100 | Healthy mix of substantive engagement and passive likes. | ▬ |
| Authenticity | 68/100 | Low-authenticity tail is large enough to skew aggregate metrics. | ▬ |
| Niche alignment | 73/100 | Sample interests overlap heavily with the creator's stated niche. | ▬ |
| Growth potential | 61/100 | Bridge-account share and high-influence cohort give strong forward signal. | ▼ |

> ⚠️ paradox: high engagement may be inflated by low-authenticity accounts.

## Top Followers (paraphrased — no PII)

- **Long-tenure quiet builder** — Cohort with 4+ year tenure, low post volume, but consistent niche-aligned likes and reposts. Bios indicate hands-on practitioners (engineers, founders, researchers). · suggested action: **Cultivate**
- **Cross-niche bridge account** — Cohort active in adjacent niches (e.g. ML x design, productivity x parenting). Acts as connective tissue that surfaces the creator's posts to wider audiences. · suggested action: **Collaborate**
- **Daily-engaging niche peer** — Aggregate cohort posting and replying daily inside the creator's stated niche. Median tenure 2-3 years, balanced followers/following ratios, technical bios. · suggested action: **Engage**
- **Reply-thread regular** — Cohort that lives in the creator's replies (4+ replies per week, substantive >30 chars). Strong signal for community depth; mostly returning accounts, not drive-bys. · suggested action: **Reply**

## Red Flags

- **Bot-engagement paradox** · severity: high — Authenticity at 68/100 is below 80 while Engagement quality at 49/100 is above the niche median. Aggregate engagement is likely inflated by low-authenticity accounts. *Remediation:* Pair `mention-summarizer` with `dm-triager` to rank inbound interaction by authenticity score before responding.
- **Single-cohort dependence** · severity: low — More than half of substantive engagement comes from a single archetype; concentration risk if that cohort drifts. *Remediation:* Diversify with `quote-tweet-suggestor` pointed at adjacent niches.

## Recommendations

1. Snapshot these scores monthly so the 30-day trend arrows in the Quality Scores table become a real baseline instead of `n/a`. — bridges to: `analytics-summarizer`
2. Drop a 2-line follow-up on the top 3 substantive replies each day to deepen the reply-thread regular cohort. — bridges to: `comment-engagement-booster`
3. Reply within 60 minutes to the top archetype's daily threads to compound the existing high-engagement signal. — bridges to: `reply-drafter`
4. Triage the inbox so DMs from the long-tenure builder cohort are surfaced first; deprioritise drive-by enthusiasts during launch weeks. — bridges to: `dm-triager`
5. Surface 5 fresh bridge accounts each week to widen the high-quality tail of the audience without diluting niche alignment. — bridges to: `niche-influencer-finder`

## Confidence
Confidence: medium — 100 samples support engagement + authenticity reliably; growth signal less stable.

---

## What this output demonstrates (audit checklist)

- [x] **4 standard metrics** in fixed row order (Engagement quality / Authenticity / Niche alignment / Growth potential)
- [x] **Bot-engagement paradox** raised in BOTH the Quality Scores section AND the Red Flags section (Authenticity 68 < 80, Engagement quality 49 > median 45 — borderline case worth catching early)
- [x] **4 paraphrased Top-Follower cards** with 4 distinct verbs from the 6-verb vocabulary (Cultivate, Collaborate, Engage, Reply)
- [x] **2 Red Flag cards** with severity (Bot-engagement paradox = high, Single-cohort dependence = low)
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** in Recommendations (`analytics-summarizer`, `comment-engagement-booster`, `reply-drafter`, `dm-triager`, `niche-influencer-finder`) — exceeds the ≥3 requirement
- [x] **No monetization recommendation** triggered (engagement quality 49 is below the 50 floor for the paid-tier suggestion) → no Article V.1 disclaimer needed in this report. The disclaimer rule fires *only* when monetization wording is present, so its absence here is correct, not a regression.
- [x] **Confidence line** at end with reason
- [x] **Aggregate-only privacy** — zero individual follower handles in the report body

The two extra cross-template references in the Red Flag remediations (`mention-summarizer`, `quote-tweet-suggestor`) bring the total distinct cross-template surface area in this report to **7 templates** — same as the AI-niche example, but with a different mix because the recommendations adapt to the score profile.

### Compared to the AI-niche example

| Dimension | `niche-ai-agents.md` | `niche-productivity.md` |
|---|---|---|
| Engagement quality | 72 (high) | 49 (just above median) |
| Authenticity | 76 (mid) | 68 (low-mid) |
| Paradox flavour | Engagement-driven (high signal masking the tail) | Authenticity-driven (creeping bot share before the eng number reacts) |
| Niche alignment | 53 (dilution flag) | 73 (healthy) |
| Top archetype mix | Drive-by + Reply + Bridge + Reposter | Builder + Bridge + Peer + Reply-regular |
| Monetization rec? | Yes (V.1 disclaimer attached) | No (engagement floor not cleared) |
| Severity profile | high + medium | high + low |

Different scores → different recommendations → different bridges. The schema and rules stay constant, the synthesis adapts.

---

> Built for xAI, X, Grok and the ecosystem community — Apache 2.0 licensed, aggregate-only, local-first.
