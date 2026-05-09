<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# FAQ — Grok Agent OS

> Built for xAI, X, Grok and the ecosystem community. ❤️

Twelve frequently-asked questions for journalists, partners, conference organizers, and analysts. Concise answers, all releasable under Apache 2.0. If a fact here ever drifts from the upstream repo, the repo wins — see [`README.md`](../../README.md), [`HANDOFF_LOG.md`](../../HANDOFF_LOG.md), and [`safety/constitution.md`](../../safety/constitution.md).

---

## 1. What is Grok Agent OS?

Grok Agent OS is the missing operating-system layer for Grok agents on X. The core idea is one YAML manifest (`grok-agent.yaml` v2.15) and one command (`grok install this`), producing an instant, safe, Windows-native deployment with full provenance and access to a curated public-API surface. Built under the `AgentMindCloud` GitHub organization by `@JanSol0s`, the project ships a unified manifest standard, a PowerShell-first CLI, a 33-check Agent Constitution scanner, four production X Money tools, twenty-two creator templates, seven Super Agents, a static Next.js marketplace, and a self-improvement loop powered by Promptfoo, DeepEval, and Langfuse. Everything is Apache 2.0, local-first, and explicitly framed as ecosystem-ally infrastructure for xAI.

## 2. Why Windows-first?

Most agent frameworks assume macOS or Linux developers. The audience that matters most for X creators — independent posters, small businesses, regional creators outside Silicon Valley — is overwhelmingly on Windows 11. Building Windows-first means PowerShell instead of bash, `$env:LOCALAPPDATA` instead of `~/.config`, and install scripts that respect the Windows file-system layout. It also means CI runs Windows-runner workflows alongside Linux ones to catch path and shell drift early. The choice reduces friction for the largest underserved slice of the X creator base, and it removes a class of bugs that hit creators when an agent designed on macOS lands on a Windows box. macOS and Linux ports remain a community choice; the canonical surface stays Windows.

## 3. Is this competing with xAI?

No. Grok Agent OS is the runtime and distribution layer xAI has not shipped yet, and the project is positioned as an ecosystem ally in every README, every commit message, and every X post. xAI ships the model and the platform; Grok Agent OS ships the install pipeline, the safety gate, the marketplace shelf, and the manifest contract that lets any builder distribute a Grok-powered agent on X without reinventing the plumbing. The license is Apache 2.0 with no royalty, no exclusivity, and no fork strategy. If xAI ever ships an official agent runtime, Grok Agent OS converges on that surface or hands the work over — whichever serves builders best. The framing is consistent: alongside xAI, never against.

## 4. What's the v2.15 manifest standard?

`grok-agent.yaml` v2.15 is the unified manifest format every Grok Agent OS agent declares. It is a 100% backwards-compatible extension of v2.14 — every v2.14 manifest validates as v2.15 unchanged. The schema lives at [`spec/v2.15/grok-agent.yaml`](../../spec/v2.15/grok-agent.yaml) and is enforced by Pydantic models in the CLI. v2.15 adds a Windows extension block (AppData paths, launcher commands, scheduled tasks), a `multi_agent` block for swarm role declarations, a `real_time_x` block for cashtag triggers and reply-only modes, and a richer `provenance` block with append-only and contradiction-handling fields. Validation runs at install time, in CI on every pull request, and inside VS Code via a published JSON schema.

## 5. How do I install an agent?

On Windows 11 with PowerShell:

```powershell
git clone https://github.com/AgentMindCloud/grok-agent.git ; cd grok-agent
.\cli\grok-agent.ps1 install templates/finance/x-money-companion-dashboard
```

Or paste a manifest from X directly into stdin:

```powershell
.\cli\grok-agent.ps1 install -FromStdin
```

The CLI validates the YAML against the v2.15 schema, runs the 33-check Constitution scanner, copies the agent to `$env:LOCALAPPDATA\grok-agent\agents\<name>\`, and registers a launcher. From the marketplace, every agent card has a one-click "Copy install command" button that emits the canonical paste-from-X invocation. No accounts, no app-store review, no middleman fees.

## 6. What's the scoreboard target?

The end-of-2026 success vision (CLAUDE.md §14) is the public scoreboard: 50,000 monthly invocations across all shipped agents; 5,000 GitHub stars on the `AgentMindCloud/grok-agent` repo; recognition as the default way to ship a Grok agent on X; at least one public engagement from an xAI engineer; and the first paying users via Creator Program v2. These five numbers are the only metrics treated as load-bearing. Vanity counts (followers, impressions, downloads-without-invocation) are tracked but not scoreboard items. Every prompt and every shipped file is plausibly traceable to one of the five — work that is not is decoration, not progress, and gets cut.

## 7. What's a Super Agent vs Creator Template?

A **Creator Template** is a focused, single-purpose agent built for one X-creator workflow — a thread builder, a reply drafter, an analytics summarizer. Twenty-two ship in [`templates/creator/`](../../templates/creator/). Each is one v2.15 manifest, one system prompt, one runner, and example outputs. A **Super Agent** is a multi-step, memory-aware, often multi-agent system that coordinates several capabilities to feel like magic — Living Narrative Fabric synthesizes contradictions across six source families with full provenance; Self-Evolving Personal OS learns user habits and updates itself nightly; Cross-Reality Action Fabric takes consent-gated actions across calendar, files, and X. Seven Super Agents ship under [`templates/super-agents/`](../../templates/super-agents/) — three flagships and four lighter manifest-only patterns.

## 8. How do trust scores work?

Every shipped agent gets a public, deterministic 0–100 trust score recomputed in CI by [`scripts/compute-trust-score.py`](../../scripts/compute-trust-score.py). The formula is `composite = 0.4 * scanner + 0.3 * eval + 0.2 * provenance + 0.1 * stability`. The **scanner** component reflects how many Constitution-check errors the manifest produces. The **eval** component rewards agents that ship a Promptfoo or DeepEval suite. The **provenance** component averages three booleans (enabled, append-only, cite-sources). The **stability** component is manifest age in days, capped at 90, divided by 90. Tiers map to A (≥90), B (≥75), C (≥60), and D (<60). The marketplace's badge endpoint reads the resulting JSON at build time and renders an embeddable SVG.

## 9. What's pulse and the MCP integration?

`grok-pulse-mcp-server` is the first MCP-compatible attention server built for the xAI / X / Grok ecosystem. It pulls live signal from a builder's GitHub repos, runs the batch through Grok for prioritization, and answers a single load-bearing question — "what should I work on right now, and why?" — through Model Context Protocol tools that drop into Claude Code, Cursor, Cowork, or any MCP-compatible agent. Five tools ship: `pulse_today`, `summarize_repo_activity`, `weekly_digest`, `next_action`, and `roast_pr`. The full spec lives at [`pulse/README.md`](../../pulse/README.md). It folded into the `grok-agent` monorepo via `git subtree`, so the entire ecosystem ships from one source of truth — provenance preserved in [`MERGE_PLAN.md`](../../MERGE_PLAN.md).

## 10. How do I contribute?

Read [`CONTRIBUTING.md`](../../CONTRIBUTING.md) first. Every new agent follows one of three reusable recipes documented in [`docs/PARAMETERIZED_RECIPES.md`](../PARAMETERIZED_RECIPES.md): Recipe A (six prompts) for X Money tools, Recipe B (two prompts) for creator templates, Recipe C (eight prompts) for Super Agents. Pick the matching recipe, fill the parameter block, draft the manifest, run `python cli/grok-agent.py validate <manifest>`, run `python safety/scanner.py scan <manifest>`, and open a pull request. CI runs the schema check, the Constitution scanner, the trust-score computer, and the forbidden-phrase leak detector. PRs that pass on green merge fast. The thirteen original reference repos listed in CLAUDE.md §13 are read-only — copy patterns, never modify them.

## 11. What's the licensing?

Apache 2.0 throughout, no exceptions. The full license text lives in [`LICENSE`](../../LICENSE) at the repo root. Every code, config, and markdown file in the repo carries an Apache 2.0 header at the top — the format varies by file type (Python comment, PowerShell comment, YAML comment, Markdown HTML comment) and the canonical headers are documented in `.claude/skills/grok-agent-conventions/SKILL.md`. The license applies to the manifest schema, the CLI, the safety scanner, the trust-score computer, the marketplace, the pulse server, every X Money tool, every Super Agent, every creator template, and every page of documentation. Forks, white-labels, derivative marketplaces, and commercial integrations are explicitly welcome under the Apache 2.0 grant.

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

The disclaimer above ships verbatim on every X Money tool surface and every press-kit answer that touches the X Money tools — it is the wording mandated by CLAUDE.md §12 and the Agent Constitution Article V.

## 12. Where can I follow updates?

Three canonical surfaces. The **GitHub repository** at [`github.com/AgentMindCloud/grok-agent`](https://github.com/AgentMindCloud/grok-agent) is the source of truth — watch for releases, follow `HANDOFF_LOG.md` for the running shipping log, and subscribe to discussions for design conversations. The **marketplace** at [`agentmindcloud.github.io/grok-agent`](https://agentmindcloud.github.io/grok-agent) lists every shipped agent with one-click install commands, trust badges, and category filters. The **X handle** [`@JanSol0s`](https://x.com/JanSol0s) posts launches, threads, and ecosystem replies on a steady drumbeat — the marketing playbook in [`marketing.md`](../../marketing.md) lists the rotating bank of single posts, threads, and reply templates. Newsletter, RSS, and podcast surfaces are deliberately out of scope until they are needed.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
