# PARAMETERIZED_RECIPES.md

This project has three classes of deliverables that repeat with the same structure. Instead of generating the prompt set from scratch every time, fill in these recipes.

---

## Recipe A: X Money Tool (Phase 2)

**Used for**: `x-money-companion-dashboard`, `x-smart-cashtag-alpha-engine`, `x-creator-payout-optimizer`, `x-money-vision-analyzer`

Each X Money tool produces 6 prompts:

### Prompt slots

| # | Slot | Files | Time |
|---|---|---|---|
| 1 | Manifest + folder | `templates/finance/{slug}/grok-agent.yaml`, `templates/finance/{slug}/README.md` | 20min |
| 2 | Streamlit app skeleton | `templates/finance/{slug}/app.py`, `templates/finance/{slug}/requirements.txt` | 45min |
| 3 | Grok prompts | `templates/finance/{slug}/prompts/system.md`, `templates/finance/{slug}/prompts/user_templates.md` | 30min |
| 4 | Data layer + APIs | `templates/finance/{slug}/data/{store}.py`, `templates/finance/{slug}/data/api_clients.py` | 60min |
| 5 | PowerShell launcher + Streamlit Cloud config | `templates/finance/{slug}/launcher.ps1`, `templates/finance/{slug}/.streamlit/config.toml` | 20min |
| 6 | "grok install this" smoke test + disclaimers polish | manifest validation, README disclaimers, end-to-end test commands | 30min |

### Parameters to fill in

```yaml
slug: x-money-companion-dashboard      # folder name
display_name: "X Money Companion Dashboard"
purpose: "Overview, transactions, analytics, Grok insights, tax export, alerts"
primary_apis:
  - x_money_api  # or whichever public API
  - yfinance
  - newsapi
data_store: sqlite                      # or duckdb
unique_features:
  - "Tax export with disclaimers"
  - "Grok-powered transaction categorization"
integration_notes: "Vision Analyzer (Tool #4) imports into this tool's SQLite via `data/import_receipts.py`"
```

### Cross-tool dependencies

- Tool #4 (Vision Analyzer) MUST import directly into Tool #1 (Companion Dashboard) SQLite. Generate Tool #1 first, then Tool #4.
- Build order: 1 → 2 → 4 → 3 (matches the project plan's week 3-8 schedule)

### Generated prompt skeleton (Slot 2 example — Streamlit app skeleton)

```markdown
# [P{N}] Build {display_name} — Streamlit app skeleton

> Phase: 2 · Estimated time: 45min · Depends on: P{N-1} (manifest + folder)

## 1. Context
[standard context block]
Already built: P{N-1} created `templates/finance/{slug}/` with manifest + README.

## 2. Goal
Build the Streamlit app skeleton for {display_name} with the 6-tab layout: Overview, Transactions, Analytics, Grok Insights, Tax Export, Alerts.

## 3. Constraints (hard)
- Apache 2.0 header
- "Built to help xAI and Grok win" footer
- "Not financial advice" banner on every page
- Windows-friendly file paths
- All state in SQLite at `~/AppData/Local/grok-agent/{slug}.db` (Windows-correct path)
- No external state — local-first

## 4. Files to create/modify
- `templates/finance/{slug}/app.py` — Streamlit entry point with 6-tab navigation
- `templates/finance/{slug}/requirements.txt`

## 5. Reference material
[reference plan section if pre-written content exists]

## 6. Acceptance criteria
- [ ] `streamlit run app.py` launches without error on Windows
- [ ] All 6 tabs render (placeholders OK for non-current tab)
- [ ] "Not financial advice" banner visible on every tab
- [ ] SQLite path uses Windows AppData correctly
- [ ] All cells include Apache 2.0 header

## 7. Output
[standard output block + handoff log line]
```

---

## Recipe B: Creator Template (Phase 3)

**Used for**: 20+ templates in `templates/creator/`

Each creator template produces 2 prompts (smaller scope than X Money tools):

### Prompt slots

| # | Slot | Files | Time |
|---|---|---|---|
| 1 | Manifest + system prompt | `templates/creator/{slug}/grok-agent.yaml`, `templates/creator/{slug}/prompts/system.md` | 20min |
| 2 | Runner + README + example outputs | `templates/creator/{slug}/run.py`, `templates/creator/{slug}/README.md`, `templates/creator/{slug}/examples/` | 30min |

### Parameters to fill in

```yaml
slug: daily-content-ideas
display_name: "Daily Content Ideas"
target_creator: "AI/tech/creator-niche, 10k+ followers"
inputs:
  - x_handle
  - niche_keywords
outputs:
  - 5_post_ideas
  - tweet_drafts
  - image_prompts_for_grok_imagine
runtime: streamlit_lite      # or cli_only
```

### The 20 templates (from project plan)

Build in this order (grouped by complexity, easiest first to validate the pattern):

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

---

## Recipe C: Super Agent (Phase 4)

**Used for**: `living-narrative-fabric`, `self-evolving-personal-os`, `cross-reality-action-fabric`

Each Super Agent produces 8 prompts (largest scope — these are flagships):

### Prompt slots

| # | Slot | Files | Time |
|---|---|---|---|
| 1 | Manifest + folder + agent constitution | `grok-agent.yaml`, `constitution.md`, `README.md` | 30min |
| 2 | Orchestration core (Mastra OR LangGraph) | `agent.py`, `graph.py` | 90min |
| 3 | Memory layer | `memory/mem0_setup.py`, `memory/qdrant_index.py` | 60min |
| 4 | Public API connector helpers | `connectors/{api1}.py`, `connectors/{api2}.py`, ... | 90min |
| 5 | Provenance log + Langfuse hooks | `provenance/log.py`, `provenance/langfuse_hooks.py` | 45min |
| 6 | Self-improvement loop (Promptfoo + DeepEval) | `eval/promptfoo.yaml`, `eval/deepeval_suite.py` | 60min |
| 7 | UI surface (Streamlit dashboard for the agent) | `dashboard.py` | 60min |
| 8 | Demo video script + X launch thread | `DEMO.md`, `X_LAUNCH_THREAD.md` | 30min |

### Parameters to fill in

```yaml
slug: living-narrative-fabric
display_name: "Living Narrative Fabric"
one_liner: "Living, versioned synthesis of X + news + academic + government + personal data with full provenance and contradiction detection"
orchestration: mastra      # or langgraph
public_apis:
  - newsapi
  - gnews
  - semantic_scholar
  - data_gov
  - x_search           # via Grok 4.3
  - crawl4ai
unique_capabilities:
  - "contradiction detection across sources"
  - "versioned synthesis (you can rewind to any prior state)"
  - "provenance trail per claim"
constitution_rules:
  - "never publish without provenance"
  - "flag contradictions, do not resolve them silently"
demo_scenario: "Track narrative around topic X over 7 days, surface 3 contradictions"
```

### Cross-Super-Agent dependencies

- Super Agent #1 (Living Narrative Fabric) is built first — it establishes the orchestration + memory + provenance patterns the others reuse
- Super Agent #2 and #3 reuse 60% of Super Agent #1's connector code → those prompts reference "extend connectors from `super-agents/living-narrative-fabric/connectors/`"

---

## How the skill USES these recipes

When the user asks for prompts for an X Money tool, creator template, or Super Agent:

1. Match the request to recipe A, B, or C
2. Pull the parameter block from `PROJECT_DNA.md` (or ask user if missing)
3. Generate the N prompts using the slot table, filling in parameters
4. Each prompt still follows the 7-section template from `PROMPT_TEMPLATE.md`
5. Number prompts globally (continue from HANDOFF_LOG)

This way the same pattern produces 4×6=24 X Money prompts, 20×2=40 creator prompts, 3×8=24 Super Agent prompts — without rewriting each from scratch.
