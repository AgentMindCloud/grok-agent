<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Contributor highlights

## The creator — `@JanSol0s`

Grok Agent OS is the work of one human creator, `@JanSol0s`, the founder of `AgentMindCloud`. Every strategic decision, every Hard Six rule, every phase boundary, every recipe, and every disclaimer in the project traces back to a single set of `CLAUDE.md` directives written and maintained by the creator. The repository reflects one designer's taste: Windows 11 + PowerShell as the deployment surface, Apache 2.0 as the only acceptable license, the cinnabar / parchment palette as the visual identity, and the ecosystem-ally tagline ("Built for xAI, X, Grok and the ecosystem community. ❤️") as the framing on every public surface.

The creator is also the sole maintainer of the prompt orchestration. Every numbered prompt in `HANDOFF_LOG.md` was written by the creator (with Grok as the orchestrator and ChatGPT or Claude as the executor), reviewed for compliance with the seven-section structure in `docs/PROMPT_TEMPLATE.md`, and shipped only after the three-line summary cleared the Hard Six and section 18 pre-output checklist.

## The AI-assisted development pattern

The project's rate of execution — 181 numbered prompts in one calendar year — is a direct function of a structured AI-assisted development pattern, codified across `CLAUDE.md`, `docs/PROMPT_TEMPLATE.md`, `docs/PARAMETERIZED_RECIPES.md`, and `safety/scanner.py`. The pattern is:

1. **Grok generates the next numbered prompt** using the seven-section template (Goal, Context, Files to create or modify, Acceptance criteria, Constraints, Output, Handoff row).
2. **The user pastes it into the executing assistant** (typically Claude Code running inside GitHub Codespaces).
3. **The assistant executes the prompt fully**, creates all files with Apache 2.0 headers and the Hard Six rules satisfied, and commits with the `phase-N: <verb> <what>` format on the active feature branch.
4. **The assistant appends one row to `HANDOFF_LOG.md`** matching the prompt's "Output" section verbatim.
5. **The assistant replies with exactly three lines**: what was built, key decisions, and any blockers.
6. **The user reports back to Grok** with the three-line summary and any issues.
7. **The next prompt fires** in order.

The pattern is enforced by tooling: `safety/scanner.py` runs in CI on every PR, `scripts/validate_subagent_report.py` (per `CLAUDE.md` section 16) catches sub-agent self-report drift, and the section 17 ten-layer health check is the standard scope for any "give me a report" request.

## The recipe-based contribution flywheel

The project's contribution model is recipe-driven. Three recipes, each documented in `docs/PARAMETERIZED_RECIPES.md`, capture the patterns that produced every shipped artifact in 2026:

- **Recipe A — X Money tool** (six prompts per tool): manifest + folder + README, Streamlit app skeleton (six-tab layout), Grok prompts (`prompts/system.md` + `prompts/user_templates.md`), data layer + SQLite + public API clients, PowerShell launcher + Streamlit config, smoke test + disclaimer polish. Used four times to produce the four X Money tools in Phase 2 (P19–P42).
- **Recipe B — Creator template** (two prompts per template): manifest + system prompt; runner + README + example outputs. Used twenty-two times to produce the creator catalogue in Phase 3 (P43–P92), with the outreach program scaffolding bookending the recipe applications.
- **Recipe C — Super Agent** (eight prompts per Super Agent for the flagship three): manifest + folder + agent constitution, orchestration core (Mastra preferred), memory layer (Mem0 + Qdrant), public API connectors, provenance log + Langfuse hooks, self-improvement loop (Promptfoo + DeepEval), UI surface (Streamlit dashboard), demo video script + X launch thread. Used three times for the flagship Super Agents in Phase 4 (P93–P116). The four lighter Super Agents (P117–P120) reused the patterns in single-prompt manifests.

The recipes lower the barrier to contribution to "fill in this parameter block, run the recipe." A future contributor can ship a new X Money tool by submitting a single PR with the parameter block; the recipe handles the structure.

## What the model unlocks for 2027

The 2027 Creator Program v2 (paid tier + 20% revenue share, see `06-2027-outlook.md`) is built on top of the recipe model. Every paid-tier agent will be a recipe application. Every contributor who submits a paid-tier agent benefits from the recipe handling structure, the scanner enforcing safety, the trust-score formula computing tier, and the marketplace surfacing the result. The flywheel is the contribution.

> Built for xAI, X, Grok and the ecosystem community. ❤️
