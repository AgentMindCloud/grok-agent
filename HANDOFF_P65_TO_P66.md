<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# HANDOFF — P65 → P66 (mid-Phase-3 chat switch)

> Bridge from this chat (which executed P43–P65, twelve creator templates) to the next fresh Claude Code chat (which will execute **P66 — Follower Quality Analyzer runner + README + examples**, the Recipe B Slot 2 partner of P65).
>
> The next session does NOT need to read the prior chat. It needs this file + the 3 critical reads in §6.

---

## 1. Where we are

| Field | Value |
|---|---|
| Repo | `github.com/AgentMindCloud/grok-agent` |
| Active branch | `claude/complete-x-money-tools-XrgAL` |
| Last commit | `14fb7cc` — `phase-3: add manifest + system prompt for follower-quality-analyzer` |
| Working dir | `/home/user/grok-agent` |
| Phase 3 progress | **22/40 P-prompts of the 20-template flywheel done = 55%.** P65 just shipped the manifest+system-prompt for the 12th template (`follower-quality-analyzer`). |
| Next prompt | **P66 — runner + README + examples for `follower-quality-analyzer`** |

---

## 2. The 11 templates already shipped end-to-end (Slots 1+2 each)

In order (per the kickoff order from `HANDOFF_PHASE2_TO_PHASE3.md`):

1. `content-idea-generator` (P43-P44)
2. `reply-drafter` (P45-P46)
3. `mention-summarizer` (P47-P48)
4. `trend-aligned-poster` (P49-P50)
5. `daily-briefing-agent` (P51-P52)
6. `research-assistant` (P53-P54)
7. `analytics-summarizer` (P55-P56)
8. `monetization-optimizer` (P57-P58)
9. `thread-builder` (P59-P60)
10. `dm-triager` (P61-P62)
11. `quote-tweet-suggestor` (P63-P64)

Then **P65 alone** (Slot 1 of the 12th):

12. `follower-quality-analyzer` (P65 done; **P66 is the runner+README+examples**)

All 12 manifests pass v2.15 validator + 0 scanner findings. Live at `templates/creator/`.

---

## 3. P66 brief (what the next prompt will ask for)

The pattern for every Slot-2 prompt (which P66 will be) is identical:

**Files to create:**
- `templates/creator/follower-quality-analyzer/run.py` — full self-contained CLI
- `templates/creator/follower-quality-analyzer/README.md` — premium README
- `templates/creator/follower-quality-analyzer/examples/niche-ai-agents.md` — sample output
- `templates/creator/follower-quality-analyzer/examples/niche-productivity.md` — sample output

**Constraints (every Slot-2 follows these):**
- Apache 2.0 header on every code/markdown file
- "Built to help xAI and Grok win" in every README/markdown
- Windows 11 + PowerShell only (PowerShell examples in README, no bash)
- Local-first; zero external calls in v1
- Runner exposes `generate = generate_follower_quality_analysis` alias to match P65 manifest's `tools[0].function`
- Saved output files prepend Apache 2.0 HTML-comment header (matches P44/P46/P48/P50/P52/P54/P56/P58/P60/P62/P64 pattern)
- Deterministic seeding: sha256(handle + sample_blob + date)
- Strict 6-section schema from P65 system prompt (or 7 with Audience Health Audit when red-flag count > 3 OR sample size < 50)

**Output schema P66 must produce (from P65 system prompt):**
1. Headline
2. Quality Scores (4-row table with `engagement_quality` / `authenticity` / `growth_potential` / `monetization_alignment`, qualitative labels only)
3. Top Followers (3-5 paraphrased cards with public handle + why_they_matter + suggested_action from the 6-verb vocabulary)
4. Red Flags (2-3 with severity + failure_mode + mitigation_hint)
5. Recommendations (3-5 bridging to sibling templates)
6. Confidence
7. (optional) Audience Health Audit when red-flag count > 3 OR sample size < 50

**Spec smoke command** (for acceptance):
```powershell
python run.py --x-handle @test --follower-sample "..." --focus all --sample-size 100
```

---

## 4. Quality bar to match (look at any of these for reference)

The prior 11 runners share an identical architecture. Pick the closest match:

- **Closest analog: `analytics-summarizer/run.py`** — same 4-canonical-row table pattern, qualitative-only scoring, cross-template bridges
- **Closest privacy analog: `dm-triager/run.py`** — aggregate-only / paraphrase-only architecture; relevant because P65 is also privacy-aware
- **Generic Slot-2 pattern: any of P44/P46/P48/P50/P52/P54/P56/P58/P60/P62/P64**

All runners follow the same `_safe_render` / `load_system_prompt` / `render_report` / `parse_args` / `main` pattern. The Apache HTML-comment header is baked into `render_report()` so saved files always carry it.

---

## 5. Repo state sanity (run before starting P66)

```powershell
# Branch state
git status                                           # expect: working tree clean
git log --oneline -3                                 # last commit: 14fb7cc

# Validator + scanner across all 12 manifests
python cli/grok-agent.py validate templates/creator/follower-quality-analyzer/grok-agent.yaml
python safety/scanner.py scan-all templates/         # expect: 0 findings on all manifests
```

If any of these fail, stop and investigate before P66.

---

## 6. Critical reads (in priority order)

1. **`templates/creator/follower-quality-analyzer/grok-agent.yaml`** — P65 manifest with the 12-rule constitution and the manifest schema P66 must consume
2. **`templates/creator/follower-quality-analyzer/prompts/system.md`** — P65 system prompt; defines the exact 6-section output schema, 4 canonical metrics, 6-verb action vocabulary, and ≥3 cross-template bridges
3. **`templates/creator/analytics-summarizer/run.py`** — closest architectural analog (4-row metric table + qualitative scoring + cross-template bridges)

Optional supporting reads:
- `templates/creator/dm-triager/run.py` — closest privacy-architecture analog
- `CLAUDE.md` §6 — Phase 3 plan + Recipe B slot pattern
- `HANDOFF_LOG.md` — single source of truth for prompt completion (P65 row already appended)

---

## 7. Cross-template bridge cheat sheet

P66's runner should generate Recommendations bridging to:
- `analytics-summarizer` — confirm engagement_quality signals match real metrics (most common bridge)
- `monetization-optimizer` — align follower-quality with revenue mix (when monetization_alignment is high)
- `research-assistant` — verify red-flag patterns or audience claims (when red flags present)
- `mention-summarizer` — triage advocate-tier inbound (when high-engagement advocates surface)
- `daily-briefing-agent` — thread follower-signal into tomorrow's brief
- `content-idea-generator` — produce content tailored to top-follower niche overlap

Mandatory ≥3 in every output (per P65 constitution rule #8).

---

## 8. The 6-verb action vocabulary (cross-template consistency)

P66 Top-Follower cards MUST use one of these six verbs only — same as `mention-summarizer`, `dm-triager`:

`reply now` | `reply within 24h` | `mute` | `block` | `ignore` | `flag for follow-up`

Never invent new verbs.

---

## 9. Privacy guarantee to preserve

P65 declared rule #1 as AGGREGATE-ONLY. P66 must enforce architecturally:
- Top-follower `why_they_matter` field is generated by the runner from input fields (`engagement_signal` + `niche_overlap`), NEVER copied from a follower's bio text
- No individual email / phone / location / employer / DM-content / political-alignment ever exposed
- Spam/inauthentic clusters surface in Red Flags as paraphrased patterns + handle lists, not by quoting bios

This mirrors `dm-triager`'s privacy architecture exactly.

---

## 10. Deliverable summary on completion

When P66 is done, the next prompt-row in `HANDOFF_LOG.md` will be:

```
| P66 | Phase 3 | Follower Quality Analyzer runner + README + examples | templates/creator/follower-quality-analyzer/run.py, README.md, examples/ | Deterministic offline runner matching P44–P64 quality bar + P65 system prompt schema + 4-canonical-metric table + aggregate-only privacy + cross-template bridges | ✅ done |
```

After P66, the project will be at **23/40 P-prompts of the 20-template flywheel = 57.5% complete**, twelve templates fully shipped end-to-end. The 13th template (`niche-influencer-finder`) starts at P67.

---

> Built to help xAI and Grok win. Pick this up, ship P66, append the row, push to `claude/complete-x-money-tools-XrgAL`, move on to P67.
