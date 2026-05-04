# HANDOFF_LOG.md (template — copy this to your repo root and update as you go)

> This file is the **single source of truth** for which prompts have run. Every Claude Code prompt ends with an instruction to append a row here. Before generating new prompts, the orchestrator skill reads this file to know what's done.

## How to use

1. Copy this file to the root of `grok-agent/` (or keep it locally).
2. After running each prompt in Claude Code, the prompt itself outputs the row to append. Paste it.
3. When you want next prompts, paste the FULL `HANDOFF_LOG.md` into Claude.ai with the orchestrator skill — it will pick up where you left off.

## Status legend

- ✅ done — prompt executed, files committed
- 🚧 in-progress — currently running
- ⚠️ blocked — needs input or has bug
- ⏭️ skipped — intentionally deferred
- 🔁 redo — needs re-run after upstream change

## Log

| # | Phase | Title | Files touched | Decisions / blockers | Status |
|---|---|---|---|---|---|
| P1 | Phase 1 | Bootstrap repo | CLAUDE.md, LICENSE, .gitignore | Apache 2.0 confirmed; instruction file is ground truth; full 126-prompt plan loaded | ✅ done |
| P2 | Phase 1 | Create canonical directory structure | .github/, cli/, docs/, safety/, spec/, templates/ (all subfolders + .gitkeep) | Exact match to PROJECT_DNA.md file tree; .gitkeep added for Git tracking | ✅ done |
| P3 | Phase 1 | Write permanent CLAUDE.md | CLAUDE.md (full replacement) | Complete ground-truth file with vision, 126-prompt plan, file tree, and all rules | ✅ done |
| P4 | Phase 1 | Create v2.15 unified manifest schema | spec/v2.15/grok-agent.yaml | Full schema with public_api, windows, multi_agent, constitution, backwards compat | ✅ done |
| P5 | Phase 1 | Create PowerShell CLI | cli/grok-agent.ps1 | Full CLI with install/new/validate/list/run + grok install this + schema validation | ✅ done |
| P6 | Phase 1 | Create Python fallback validator | cli/grok-agent.py | Pydantic v2 validator callable from PowerShell CLI | ✅ done |
| P7 | Phase 1 | Create safety system | safety/scanner.py, safety/constitution.md | Scanner + Constitution enforcing Hard Six + disclaimers | ✅ done |

<!--
Add new rows above this line as prompts complete.
Format reference: | P{N} | Phase {N} | {short title} | {files touched} | {key decisions in 1 line} | ✅ done |
-->

## Notes

- **Cross-prompt decisions** (things you decide once that affect later prompts): record in the "Decisions" column. Examples:
  - "Mastra chosen over LangGraph for super agent orchestration"
  - "SQLite chosen over DuckDB for local data store"
  - "Streamlit Cloud free tier confirmed working from Vietnam"

- **Blockers**: if a prompt blocks (e.g. API key missing, dependency conflict), use status `⚠️ blocked` and write the blocker in the Decisions column. The orchestrator will see it and either suggest a workaround prompt or route around it.

- **Branch tracking** (optional): if you're using feature branches, add a `Branch` column. For solo Windows work, main branch is usually fine.

## Phase progress dashboard (auto-update by counting rows)

```
Phase 1 (Foundation):       [ /18]  __% complete
Phase 2 (X Money Tools):    [ /24]  __% complete
Phase 3 (Creator Distrib):  [ /45]  __% complete  (40 templates + 5 program prompts)
Phase 4 (Super Agents):     [ /27]  __% complete  (24 super agent prompts + 3 self-improvement)
Phase 5 (Marketplace):      [ /12]  __% complete

Total estimated:            ~126 prompts
```

> Numbers are estimates from PARAMETERIZED_RECIPES + PROJECT_DNA. Actual count will drift ±15%.
