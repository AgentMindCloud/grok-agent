<!--
  Copyright 2026 AgentMindCloud
  Licensed under the Apache License, Version 2.0
  http://www.apache.org/licenses/LICENSE-2.0
  Template: Trend-Aligned Poster (trend-aligned-poster)
  Creator: @habitstacker
  Generated: 2026-05-05T00:00:00+00:00 (bit-identical reference output)
-->

# Sample 2 — Healthy Trend Alignment

**Scenario**: avg Trend match 68.0 < 75 threshold, avg Niche fit 77.0 > 40 floor → no paradox, no off-niche exclusion. All 5 ideas pass the guard. Clean 7-section report (no Trend Audit).

| Field | Value |
|---|---|
| Handle | `@habitstacker` |
| Window | 30d |
| Paradox | ✅ none |
| Off-niche excluded | 0 |
| Sections | 7 (no Trend Audit) |

**Regenerate this output:**

```powershell
python .\templates\creator\trend-aligned-poster\run.py `
  --handle habitstacker `
  --trends-file .\templates\creator\trend-aligned-poster\examples\sample-2-input.json `
  --days 30 `
  --no-banner
```

---

## Trend Snapshot
**@habitstacker: 30d trend window — directional period (Trend Alignment Plan Score 51/100); monitor niche fit next window.**

- **Creator handle**: @habitstacker
- **Window**: 30d
- **Comparison basis**: previous_period
- **Data source**: real X trend export from --trends-file

## Trend Alignment Plan Score

| Metric | Value | Trend | Interpretation |
|---|---|---|---|
| Trend match strength | 68.0/100 | ▬ | Inside the healthy band; trends are relevant without overwhelming the niche filter. |
| Niche fit            | 77.0/100 | ▬ | Inside the healthy band; ideas are niche-aligned with room to push relevance further. |
| Voice fidelity       | 81.4/100 | ▲ | Inside the healthy band; copy outlines preserve the creator's tone. |
| Originality          | 70.0/100 | ▲ | Inside the healthy band; ideas are sufficiently differentiated from the crowd. |

**Trend Alignment Plan Score**: 51/100

## Trend Watchlist

| Trend (paraphrased) | Velocity | Niche fit |
|---|---|---|
| Growing conversation on habit-stacking systems for knowledge workers | accelerating | tight |
| Mainstream interest in evening-routine optimisation frameworks | steady | tight |
| Adjacent surge in productivity tool comparisons for async teams | steady | adjacent |
| Decelerating thread format popularity in niche coaching content | decaying | adjacent |

## Post Ideas (5 ideas)

1. **thread** · trend: `habit-stacking-knowledge-workers` — 7-tweet breakdown of the habit-stacking system applied to knowledge-work routines
   trend match: 74 · engagement: breakout · bridges to: `thread-builder`
2. **single** · trend: `evening-routine-optimisation` — Counterintuitive evening-routine principle most people implement backwards
   trend match: 71 · engagement: high · bridges to: `content-idea-generator`
3. **quote-tweet** · trend: `productivity-tool-comparison` — Reframe of the productivity-tool comparison trend through a single-system lens
   trend match: 68 · engagement: high · bridges to: `content-idea-generator`
4. **image-post** · trend: `async-team-productivity` — Visual showing how the habit loop maps onto the three async-team failure modes
   trend match: 65 · engagement: high · bridges to: `content-idea-generator`
5. **reply-thread** · trend: `thread-format-effectiveness` — Reply-thread expanding on how decelerating thread formats still outperform single posts in niche coaching
   trend match: 62 · engagement: high · bridges to: `content-idea-generator`

## Red Flags

- **Single-period read** · severity: low — One trend window is directional, not conclusive. Treat the Trend Alignment Plan Score as a snapshot, not a trend. *Remediation:* Re-run monthly to build a baseline of trend arrows across consecutive windows.
- **Trend freshness reminder** · severity: low — Confirm trend recency before posting; trends shift faster than monthly windows capture. *Remediation:* Re-run with --window 7 to check velocity in the most recent cycle before committing to any idea.

## Recommendations

1. Extend the 5 post ideas in this plan by re-sourcing anchor posts when trends shift; keep a rolling set of 5–8 niche-aligned idea candidates. — bridges to: `content-idea-generator`
2. Expand the highest-match thread idea (trend match 74) into a structured long-form draft before publishing. — bridges to: `thread-builder`
3. Correlate the predicted engagement bands with the period's actual impression and engagement metrics next window to calibrate the model. — bridges to: `analytics-summarizer`
4. Pair each post idea with a niche-specific tag mix that fits both the trend and the creator's surface before publishing. — bridges to: `hashtag-strategy-advisor`
5. Cross-reference whether the trend is already showing in the creator's mention layer before posting — inbound mention signals lead outbound trend cycles by 24–48h. — bridges to: `mention-summarizer`

## Confidence
Confidence: medium — Trend Alignment Plan Score 51/100; widen the window or supply richer trend data to lift to high.
