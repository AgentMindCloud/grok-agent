<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win — example output of the Brand Voice Trainer. -->

# Example output — niche: productivity / habit-stacking (Voice Audit auto-trigger)

> 🔒 **Drafts only.** Training prompts below are text the creator pastes into other Grok Agent OS templates. The runner never auto-applies anything.
>
> 🔒 **Sample-size double gate.** This run uses 8 posts — above the 5-post hard floor (so a profile is emitted) but below the 10-post audit threshold (so the Voice Audit auto-section is appended). Treat all numbers as directional rather than authoritative.
>
> *Built to help xAI and Grok win — productivity creators often have distinctive voice but struggle to know whether 8 posts is enough sample to train on. The Voice Audit section answers that question explicitly: it is enough for direction, not for confidence.*

| Field | Value |
|---|---|
| Creator handle | `@habitstacker` |
| Sample size | 8 posts (productivity demo sample) |
| Voice focus | `all` |
| Output format | `both` (analysis + training prompts) |
| Sections emitted | **8** (Voice Audit auto-triggered: sample size 8 < 10) |
| Generic-polish paradox? | No (heuristic scoring on real-content-distinctive sample) |
| Equivalent rule surfaced | Voice Audit — explicit warning that the sample is below the audit threshold |

To regenerate this output deterministically:

```powershell
python .\run.py --x-handle habitstacker --demo-productivity --voice-focus all --output-format both --no-banner
```

---

## Voice Snapshot
**@habitstacker: punchy, near-uniform across the sample voice across 8 posts; voice profile below.**

- **X handle**: @habitstacker
- **Sample size**: 8 posts
- **Voice focus**: all
- **Output format**: both
- **Dominant signal**: punchy, near-uniform across the sample

## Voice Profile

| Metric | Score | Interpretation | 30d trend |
|---|---|---|---|
| Tone consistency | 84/100 | Tone is stable across the sample — variance in length and shape is tight. | n/a |
| Structure consistency | 54/100 | Structural variety is high — useful for exploration, costly for recognition. | n/a |
| Vocabulary distinctiveness | 77/100 | Lexicon clearly belongs to the creator; signature phrases are visible. | n/a |
| Voice cohesion | 69/100 | Mostly one voice; the occasional post reads as a different cadence. | ▬ |

**Voice Profile score**: 72/100

## Voice Signatures

### Tone
- **Dominant tone**: punchy, near-uniform across the sample.
- **Secondary tones**: (none clearly secondary).
- **Tone tells**: sentence-length descending cadence (long → short → punch).

### Structure
- **Common shape 1**: single-claim hook → 1-2 line unpack, used in the majority of the sample.
- **Common shape 2**: single posts dominate; threads are rare.
- **Shape that's missing**: data-anchored case-study shape (numbers up front + narrative) — absent from the sample, useful to add.

### Vocabulary
- **Signature phrases**: "before you", "the friction", "your evening".
- **Lexicon tilts**: morning, friction, productivity, before, habit — fluently used in the sample, signal of niche fluency.
- **Generic-default words to watch**: "stack" (×2) — niche-default phrases present in the sample. Compound risk: low distinctiveness.

## Training Prompts

1. **For `content-idea-generator`**: Generate 5 X post ideas in the voice of @habitstacker — punchy, near-uniform across the sample. Signature phrases to weave in when natural: "before you", "the friction". Avoid niche-default vocabulary. End each idea with a concrete recommendation, never a generic question.
2. **For `thread-builder`**: Build a 7-post thread in @habitstacker's voice (punchy, near-uniform across the sample). Open with a contrarian or specific claim, three concrete examples, two remediations, one closing payoff. Each post under 280 chars. Keep signature phrases intact.
3. **For `cross-platform-reposter`**: Adapt the next X post to LinkedIn while preserving @habitstacker's voice — multi-paragraph form, end on a concrete recommendation (not a question), 0-2 niche hashtags. Avoid niche-default phrasings entirely.
4. **For `content-recycler`**: Recycle this old post in @habitstacker's voice — keep the dominant claim and tone tells; add a fresh data point in the middle. Attribution stamp preserved.
5. **For `reply-drafter`**: Draft 3 replies in @habitstacker's voice — punchy, near-uniform across the sample, concrete observations only, never apologetic, never generic agreement.

## Red Flags

- **Structure-shape gap** · severity: low — At least one repeating shape useful in this niche is absent from the sample. *Remediation:* Try the absent shape once per week; A/B against the existing dominant shape for 4 weeks via `ab-test-suggester`.

## Recommendations

1. Try one new structural shape per week; A/B against the existing dominant shape for 4 weeks. — bridges to: `ab-test-suggester`
2. Recycle the highest-engagement post via `content-recycler` with the trained voice profile to compound the signal. — bridges to: `content-recycler`
3. Lock signature phrases by re-using them deliberately for the next 30 posts; track which ones harvest reply attention. — bridges to: `content-idea-generator`
4. If a paid-tier offer surfaces in the next quarter, model the voice carefully before publishing. — bridges to: `monetization-optimizer`

   > ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.
5. Cross-post the next anchor with `cross-platform-reposter` paired with this voice profile so platform-default voice doesn't dilute the signal. — bridges to: `cross-platform-reposter`

## Confidence
Confidence: low — 8 posts are inside the audit band (< 10) — Voice Audit auto-triggered.

## Voice Audit (auto-triggered)

- **Sample reliability**: 8 posts is below the 10-post audit threshold — treat all numbers as directional.
- **Signal gaps**: all signal is most affected at this sample size.
- **Suggested next sample**: pull 30 posts spanning the last 90 days, focus=all.
- **Re-run cadence**: monthly while distinctiveness < 50, otherwise quarterly.

---

## What this output demonstrates (audit checklist)

- [x] **4 canonical Voice Profile metrics** in fixed row order (Tone consistency / Structure consistency / Vocabulary distinctiveness / Voice cohesion) with heuristic scoring on real sample content
- [x] **Weighted Voice Profile score formula** `round(0.30·Tone + 0.20·Structure + 0.25·Vocabulary + 0.25·Cohesion)` applied to actual post content
- [x] **3 signature subsections** (Tone / Structure / Vocabulary) — verbatim n-grams extracted from the 8 productivity posts (e.g. recurring phrases that appear in 2+ posts)
- [x] **5 Training Prompts**, each naming a destination cross-template slug (`content-idea-generator`, `thread-builder`, `cross-platform-reposter`, `content-recycler`, `reply-drafter`)
- [x] **Red Flag cards** with severity (no paradox in this run; supporting flags surfaced based on heuristic scores)
- [x] **5 Recommendations**, each with a `bridges to:` cross-template slug
- [x] **5 distinct cross-template bridges** in Recommendations — exceeds the ≥3 requirement
- [x] **Voice Audit (auto-triggered)** section appears because sample size (8) is below the 10-post audit threshold — quantifies sample reliability, signal gaps, suggested next sample, and re-run cadence
- [x] **Sample-size double gate respected** — 8 posts is above the 5-post hard floor (profile emitted) AND below the 10-post audit threshold (Voice Audit auto-appended)

### Compared to the AI-niche example

| Dimension | `niche-ai-agents.md` | `niche-productivity.md` |
|---|---|---|
| Sample size | 24 (above audit threshold) | 8 (inside audit band) |
| Scoring mode | demo-pinned (paradox profile) | heuristic (real content analysis) |
| Generic-polish paradox? | Yes — surfaced in BOTH places | No — heuristic distinctiveness on the productivity sample is healthier |
| Voice Audit triggered? | No | Yes (sample < 10) |
| Demonstrates | The paradox rule firing on a curated generic-polish sample | The sample-size double gate firing on a real-but-thin sample |
| Confidence | Low-medium (paradox dominates the read) | Low (sample inside audit band) |

Same schema and rules, different inputs → different rule demonstrations. The runner's deterministic seeding makes both outputs reproducible bit-for-bit from the PowerShell snippets above. Together the two examples cover the full surface of the brand-voice-trainer's edge cases: the paradox firing (AI demo), the sample-gate firing (productivity demo), and — in the runner's tiny-sample-refusal path (sample < 5, not shown in either example) — the hard floor.

> **v1 limitation note:** the runner's signature-extraction is purely deterministic n-gram analysis (no LLM). Verbatim phrases are real (extracted from the sample), but tone-tells and structure-shapes are derived from heuristic regex/length analysis rather than semantic understanding. A future v2 with Grok 4.3 in the loop would generate richer signatures while preserving the same scoring, paradox detection, sample-gate, and own-voice-only invariants this v1 already enforces.

---

> Built to help xAI and Grok win — Apache 2.0 licensed, drafts-only, train-only-on-own-voice.
