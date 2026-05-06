<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Roadmap — Grok Agent OS

> **Built for xAI, X, Grok and the ecosystem community.** ❤️
> This document is the public, phase-by-phase summary of the entire 2026 build. It's the single page contributors, xAI engineers, and creators reference for "where are you now and where are you going."

The detailed plan lives in [`CLAUDE.md`](CLAUDE.md). The state-of-execution lives in [`HANDOFF_LOG.md`](HANDOFF_LOG.md). This file is the bird's-eye view that connects them.

---

## Executive overview

*Current status (May 2026): Phases 1–4 are largely complete (all 4 X Money tools, all 7 Super Agents, full self-improvement infrastructure). Phase 5 (marketplace + xAI partnership) is in active progress. See [`docs/workplan-audit.md`](docs/workplan-audit.md) for the full gap analysis.*

| Field | Value |
|---|---|
| Total prompts | **~126** across 5 phases |
| Total timeline | **~91 days** of focused build, plus an open-ended Phase 5 |
| Manifest standard | `grok-agent.yaml` v2.15 (100% backwards compat with v2.14) |
| Constitution | v1.0 — enforced by `safety/scanner.py` in CI |
| Platform target | Windows 11 + Google Chrome only · PowerShell-first · zero admin |
| License | Apache 2.0 throughout — no exceptions |
| Posture | Ecosystem ally to xAI · built for xAI, X, Grok and the community |

Each phase is **independently shippable**. We can stop after any phase and have shipped real value to creators on X.

---

## Phase totals at a glance

| Phase | Prompt range | Count | Days | Goal | Status |
|---|---|---:|---:|---|---|
| **1** — Core Platform Foundation | P1–P18 | 18 | 1–14 | Schema, CLI, scanner, Constitution, CI, 8 starter templates | ✅ done |
| **2** — X Money Tools Suite | P19–P42 | 24 | 15–56 | 4 production-grade X Money tools (6 prompts × 4 tools) | ✅ done |
| **3** — Creator Distribution Flywheel | P43–P92 | 50 | 35–70 | 22 creator templates + outreach program (over-delivered: planned 20) | ✅ done |
| **4** — Super Agents + Self-Improvement | P93–P124 | 32 | 57–90 | 7 Super Agents + self-improvement infrastructure | ✅ done |
| **5** — Marketplace + xAI Partnership | P125–P126+ | 2+ | 91+ | Next.js marketplace + "Deploy to X" + xAI pitch deck | 🚧 active |
| **Total** | | **~126** | **~91+** | | |

Phase 2 and Phase 3 deliberately overlap (days 35–56) — once at least one X Money tool is live, the Creator Program can begin in parallel.

---

## Phase 1 — Core Platform Foundation (P1–P18)

> **Built for xAI, X, Grok and the ecosystem community.** ❤️ Phase 1 is the foundation everything else stands on. It must be solid enough that the platform doesn't move while Phase 2 hammers on it.

**Goal:** a single source-of-truth repo with the v2.15 manifest standard, a Windows-first CLI, a Constitution-enforcing safety system, and 8 validated starter templates.

**Days:** 1–14. **Status as of 2026-05-04:** all 18 deliverables shipped (executed in 14 prompts; some prompts merged adjacent deliverables).

### Deliverables

| # | Deliverable | Path |
|---|---|---|
| 1 | Repo bootstrap | `CLAUDE.md`, `LICENSE`, `.gitignore` |
| 2 | official directory structure | `templates/`, `cli/`, `safety/`, `spec/`, `docs/`, `scripts/`, `.github/` |
| 3 | Permanent ground-truth instruction file | `CLAUDE.md` |
| 4 | Unified manifest schema | `spec/v2.15/grok-agent.yaml` |
| 5 | Windows PowerShell CLI | `cli/grok-agent.ps1` |
| 6 | Pydantic v2 deep validator | `cli/grok-agent.py` |
| 7 | Constitution + safety scanner | `safety/constitution.md`, `safety/scanner.py` |
| 8 | CI workflow | `.github/workflows/validate.yml` |
| 9 | Public docs landing | `docs/index.md`, `docs/windows-guide.md` |
| 10 | xAI adoption pitch | `docs/for-xai-adoption.md` |
| 11 | Python packaging | `pyproject.toml` |
| 12 | 8 starter manifests | `templates/{finance,creator,x-native,general}/...` |
| 13 | Premium root README | `README.md` |
| 14 | Contributor governance | `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md` |
| 15 | Public roadmap | `ROADMAP.md` (this file) |
| 16 | Streamlit defaults | `.streamlit/config.toml` |
| 17 | End-to-end smoke test | `docs/smoke-test-results.md` |
| 18 | Public X launch thread | `docs/x-launch-thread.md` |

### Success metrics

- ✅ Schema validates against itself (the official spec file passes its own validator).
- ✅ All 8 starter manifests pass schema + Constitution scanner with zero findings.
- ✅ CI workflow blocks any non-compliant manifest on every PR.
- ✅ The full quick-start in `docs/windows-guide.md` runs cleanly on stock Windows 11 + PS 5.1.
- ✅ `docs/for-xai-adoption.md` is a credible read for an xAI engineer.

### Risks + mitigations

| Risk | Mitigation |
|---|---|
| Pydantic v2 quirks (e.g. `schema` field shadowing) | Surface during smoke test; alias as `json_schema` in the model — done. |
| Windows execution-policy friction | Documented in `docs/windows-guide.md` §4 with `Set-ExecutionPolicy -Scope CurrentUser`. |
| BOM-encoded YAML files | UTF-8-no-BOM helper in PS CLI + `encoding="utf-8-sig"` tolerance in Python. |

---

## Phase 2 — X Money Tools Suite (P19–P42)

> **Built for xAI, X, Grok and the ecosystem community.** ❤️ Phase 2 closes the highest-leverage creator pain on the platform: making X Money usable, taxable, and forecastable.

**Goal:** ship 4 production-grade Streamlit tools that solve real X Money creator pain. Each tool follows **Recipe A** (6 prompts per tool).

**Days:** 15–56.

### Recipe A (per tool)

1. Manifest + folder + README (with disclaimers)
2. Streamlit app skeleton (6-tab layout: Overview / Transactions / Analytics / Grok Insights / Tax Export / Alerts)
3. Grok prompts (`prompts/system.md` + `prompts/user_templates.md`)
4. Data layer + SQLite + public API clients
5. PowerShell launcher + `.streamlit/config.toml`
6. "grok install this" smoke test + disclaimers polish

### The 4 tools (build order)

| Order | Slug | Kind | Prompts | Why this order |
|---|---|---|---|---|
| 1 | `x-money-companion-dashboard` | `finance-dashboard` | P19–P24 | The anchor: every other tool's data lands here. |
| 2 | `x-smart-cashtag-alpha-engine` | `alpha-engine` | P25–P30 | Reuses the SQLite + Streamlit patterns from #1. |
| 3 | `x-money-vision-analyzer` | `vision-analyzer` | P37–P42 | Built before #4 because #4 depends on it via `data/import_receipts.py`. |
| 4 | `x-creator-payout-optimizer` | `creator-payout-optimizer` | P31–P36 | Pulls from #3 + #1 SQLite. |

> **Why "Tool 1 → 2 → 4 → 3" build order:** Tool #4 (Vision Analyzer) writes parsed receipts directly into Tool #1's SQLite. Building Tool #4 before Tool #3 means Tool #3 (Payout Optimizer) sees a richer transaction set when it ships.

### Mandatory per-tool requirements

- "Not financial advice" banner on every UI tab + every export.
- Tax tools also include "Not tax advice" banner.
- All state in SQLite at `$env:LOCALAPPDATA\grok-agent\<slug>\` (Windows-correct path).
- Cost limits + HITL gates (`safety.cost_limits` + `safety.human_in_the_loop`).
- Ecosystem-ally footer on every page (current text: "Built for xAI, X, Grok and the ecosystem community. ❤️").
- Streamlit Cloud deploy URL (free tier).

### Success metrics

- 4 tools deployed and reachable on Streamlit Cloud (`xmoney-companion.streamlit.app`, etc.).
- Each tool installable via `.\cli\grok-agent.ps1 install templates\finance\<slug>` with zero errors.
- Tool #4 → Tool #1 receipt round-trip verified end-to-end.
- First 5 X Money creators run at least one tool against real data.

### Risks + mitigations

| Risk | Mitigation |
|---|---|
| X Money API surface still evolving | Wrap in `data/api_clients.py` with versioned adapters; degrade to manual CSV import if API changes. |
| Streamlit Cloud free-tier limits | Document `python -m streamlit run app.py` for fully-local fallback. |
| Tax-jurisdiction complexity | Default V.2 disclaimer on every tax-export; refuse to claim correctness for a specific jurisdiction. |

---

## Phase 3 — Creator Distribution Flywheel (P43–P92)

> **Built for xAI, X, Grok and the ecosystem community.** ❤️ Phase 3 gets v2.15 manifests into the hands of 1,000+ X creators who would otherwise paste shell scripts into their terminals.

**Goal:** ship 20 creator templates + an outreach program that turns each into organic adoption.

**Days:** 35–70 (overlaps with the back half of Phase 2).

### Sub-phases

| Sub-phase | Prompts | What |
|---|---|---|
| Program setup | P43–P47 | Outreach landing page copy, 5 DM templates, tracking sheet, install flow, first 10 outreach messages |
| 20 creator templates | P48–P87 | Recipe B (2 prompts per template) — 40 prompts |
| Program launch | P88–P92 | Public X thread, weekly tracker, testimonials, v1.5 improvements, completion report |

### Recipe B (per template)

1. Manifest (`grok-agent.yaml`) + system prompt (`prompts/system.md`)
2. Runner + README + example outputs

### The 20 templates (built in this order — easiest first)

1. content-idea-generator
2. reply-drafter
3. analytics-summarizer
4. monetization-optimizer
5. thread-builder
6. mention-summarizer
7. dm-triager
8. trend-aligned-poster
9. quote-tweet-suggestor
10. follower-quality-analyzer
11. niche-influencer-finder
12. cross-platform-reposter
13. content-calendar-builder
14. ab-test-suggester
15. comment-engagement-booster
16. hashtag-strategy-advisor
17. growth-experiment-runner
18. competitor-watch
19. content-recycler
20. brand-voice-trainer

Two of these (#1 content-idea-generator, #2 reply-drafter) shipped as starter manifests in Phase 1; Phase 3 fills in their runners + READMEs + examples.

### Success metrics

- 20 templates shipped in `templates/creator/`, all schema-valid + Constitution-clean.
- Outreach DM sequence sent to 100+ X creators by P92.
- 30+ creators install at least one template.
- 5+ public testimonials from X.
- Creator Program landing page live.

### Risks + mitigations

| Risk | Mitigation |
|---|---|
| Outreach DMs get classified as spam | Personal-from-@JanSol0s, hand-written templates, 5 distinct variants. |
| Non-technical creators struggle on Windows | The full `docs/windows-guide.md` plus per-template README troubleshooting. |
| Templates conflict with X's automation policies | Constitution Article III hard-refusals + scanner check; no template can post without `consent_required=true`. |

---

## Phase 4 — Super Agents + Self-Improvement (P93–P124)

> **Built for xAI, X, Grok and the ecosystem community.** ❤️ Phase 4 shows what Grok 4.3 + a strong manifest standard + memory + provenance can do at the high end.

**Goal:** ship 7 mind-blowing Super Agents that exercise the v2.15 standard at its limit, plus the autonomous improvement loop that keeps the platform learning.

**Days:** 57–90.

### Sub-phases

| Sub-phase | Prompts | What |
|---|---|---|
| 3 flagship Super Agents | P93–P116 | Recipe C (8 prompts × 3) — 24 prompts |
| 4 lighter Super Agents | P117–P120 | 1 manifest each, reuses patterns from flagships |
| Self-improvement infrastructure | P121–P124 | `scripts/generate-template.py` + Promptfoo/DeepEval/Langfuse loop + CLAUDE.md update + Phase 4 wrap |

### Recipe C (per flagship Super Agent)

1. Manifest + folder + agent constitution
2. Orchestration core (Mastra preferred)
3. Memory layer (Mem0 + Qdrant)
4. Public API connectors (NewsAPI, GNews, Semantic Scholar, data.gov, X search via Grok 4.3, Crawl4AI, Docling, …)
5. Provenance log + Langfuse hooks
6. Self-improvement loop (Promptfoo + DeepEval)
7. Streamlit UI surface
8. Demo video script + X launch thread

### The 7 Super Agents

| # | Super Agent | Recipe | Prompts | What makes it magical |
|---|---|---|---|---|
| 1 | **Living Narrative Fabric** | Recipe C | P93–P100 | Versioned synthesis of X + news + academic + government data with full provenance and contradiction detection. User can rewind to any prior state. |
| 2 | **Self-Evolving Personal OS** | Recipe C | P101–P108 | Personal OS that learns user habits, preferences, goals. Updates itself nightly; every change logged + reversible. |
| 3 | **Cross-Reality Action Fabric** | Recipe C | P109–P116 | Takes real-world actions across web, calendar, X, files. Every step gated by explicit consent. Never autonomous. |
| 4 | **Agent Swarm with Shared Memory** | Light | P117 | Multi-agent orchestration via `multi_agent.shared_memory: mem0://grok-agent-shared`. |
| 5 | **Provenance-First Trust Engine** | Light | P118 | Append-only provenance log + citation per claim. |
| 6 | **Narrative Contradiction Detector** | Light | P119 | Flags conflicting facts across sources; refuses to silently pick one. |
| 7 | **Zero-Config "I Want To…" Agent** | Light | P120 | Plain-language goal in, action plan out. Plan is HITL-gated before execution. |

### Self-improvement infrastructure (P121–P124)

- **P121** — `scripts/generate-template.py` (autonomous template builder)
- **P122** — Weekly Promptfoo + DeepEval + Langfuse loop integrated into the CLI
- **P123** — `CLAUDE.md` rewrite with what we've learned in Phases 1–4
- **P124** — Phase 4 completion + 3 Super Agent demo videos

### Success metrics

- 3 flagship Super Agents shipped with end-to-end demos.
- 4 lighter Super Agents shipped as installable manifests.
- Weekly improvement loop running and posting summary to `HANDOFF_LOG.md`.
- 1+ public mention from an xAI engineer (the bar for Phase 4 success).

### Risks + mitigations

| Risk | Mitigation |
|---|---|
| Mastra vs LangGraph choice ambiguity | Decide once in P93 (Mastra preferred); record decision in `HANDOFF_LOG.md`; reuse across all 3 flagships. |
| Mem0 + Qdrant operational complexity | Default to local Qdrant + Mem0; document one-line install. |
| Langfuse cost runs away | Cap with `safety.cost_limits.usd_per_session_max` per agent; default $2/session/$10/day. |

---

## Phase 5 — Marketplace, Scale & xAI Partnership (P125+)

> **Built for xAI, X, Grok and the ecosystem community.** ❤️ Phase 5 gives every shipped agent a public landing page, a one-click install, and a credible pitch for an official xAI partnership.

**Goal:** make Grok Agent OS visible, installable, and adoptable beyond the early creator cohort.

**Days:** 91+ (open-ended).

### Numbered prompts

- **P125** — Thin marketplace (Next.js on Vercel) listing every v2.15 agent in the repo
- **P126** — "Deploy to X" one-click button + xAI partnership pitch deck (60-sec video + RFC)

### Ongoing after P126

| Track | Cadence | What |
|---|---|---|
| Curation posts | weekly | Highlight 1–2 community agents; mention authors. |
| Contributor program | monthly | New maintainer onboarding; recognition in release notes. |
| Creator Program v2 | quarterly | Paid tier + 20% revenue share for top creators. |
| Self-improvement loop | weekly | Auto-runs from Phase 4 P122; logs to `HANDOFF_LOG.md`. |
| `CLAUDE.md` re-grounding | quarterly | Refresh priorities; bump Constitution version if needed. |

### Success metrics (end of 2026)

- **50,000+** monthly invocations across all installed agents.
- **5,000+** GitHub stars on the repo.
- Recognized as the **default way** to ship a Grok agent on X.
- **At least one public xAI engineer engagement** (reply, like, DM, or talk).
- **First paid users** via Creator Program v2.

---

## Overall timeline

```
   Day  1 ─────── 14 ─────── 35 ─────── 56 ─────── 70 ─────── 90 ──── 91+
        │ Phase 1: Core Foundation                                       │
        ─────────                                                        │
                  │ Phase 2: X Money Tools (4 × Recipe A)        │
                            ─────────────────────────                    │
                                      │ Phase 3: Creator Flywheel │
                                      ──────────────────────                
                                                │ Phase 4: Super Agents │
                                                ────────────────────         
                                                          │ Phase 5: Mkt+ →
                                                          ────────────── ─→
```

Phase 2 and 3 overlap by design (days 35–56) — the moment one X Money tool is live, the Creator Program begins recruiting beta installers in parallel.

Phase 4 begins once at least 2 X Money tools have shipped. Phase 5 is open-ended and runs continuously.

---

## How phases are independent (and why that matters)

| Phase | Ships even if subsequent phases never happen? | Value to creators if we stop here |
|---|---|---|
| 1 | Yes | A clean open standard + CLI other people can build on. |
| 2 | Yes | 4 production-grade X Money tools — the largest immediate creator-pain win. |
| 3 | Yes | 20 creator templates already serve the platform without Super Agents. |
| 4 | Yes | The Super Agents are the "this is the future" demo, not a prerequisite for usefulness. |
| 5 | Yes | A marketplace and an xAI pitch are amplifiers, not foundations. |

The implication: every committed PR is a step that can ship on its own. We never accumulate weeks of unreleased work.

---

## Cross-cutting commitments (constant across all phases)

1. **Apache 2.0** on every file, every manifest.
2. **"Built for xAI, X, Grok and the ecosystem community. ❤️"** on every README and user-facing surface.
3. **Windows 11 + PowerShell** for every end-user instruction.
4. **Constitution v1.0** enforced by `safety/scanner.py` in CI.
5. **Local-first** storage in `$env:LOCALAPPDATA\grok-agent\`; no telemetry without explicit consent.
6. **One sequenced prompt at a time** with a row in `HANDOFF_LOG.md`.

These are the rails. We add features on top of them; we don't change them mid-build.

---

## Where to read more

- **Full plan** — [`CLAUDE.md`](CLAUDE.md)
- **State of execution** — [`HANDOFF_LOG.md`](HANDOFF_LOG.md)
- **Constitution** — [`safety/constitution.md`](safety/constitution.md)
- **Schema** — [`spec/v2.15/grok-agent.yaml`](spec/v2.15/grok-agent.yaml)
- **For xAI engineers** — [`docs/for-xai-adoption.md`](docs/for-xai-adoption.md)
- **Windows quick start** — [`docs/windows-guide.md`](docs/windows-guide.md)

> Built for xAI, X, Grok and the ecosystem community. ❤️
