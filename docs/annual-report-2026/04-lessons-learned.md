<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Lessons learned

This is the honest section. The wins are documented in the rest of the report. Here we cover what broke, why it broke, and the structural changes we made so it does not break the same way again. Every lesson maps to a `HANDOFF_LOG.md` row so it is auditable.

## Lesson 1 — A one-character routing bug can hide for two prompts (the SEPOS story)

The Self-Evolving Personal OS (SEPOS) ships a conditional router (`templates/super-agents/self-evolving-personal-os/graph.py`) that decides whether to loop back to the ingest node based on a `loop_count` cap. P174 shipped the router with `loop_count < cap` — the wrong direction. The `evolve_workflows` step increments `loop_count` *before* the router runs, so the cap check needs `<=` to allow the first loop-back. The bug surfaced in P177 when SEPOS was wired into `.github/workflows/tests.yml` and `templates/super-agents/self-evolving-personal-os/smoke_test.py:355` failed: it asserted `_graph.NODE_INGEST` for the conditional router but received `'generate_brief'`.

The fix landed in P178: changed `<` to `<=` and added four unit tests in `templates/super-agents/self-evolving-personal-os/tests/test_router.py` (happy-loop, cap-exceeded, no-loop, missing-keys). The four tests are now permanent guards. The structural lesson: any single-character comparison in a router or guard is one of the most failure-prone shapes in the codebase, and the fix is to lock it in with a focused unit test the same prompt that fixes it.

## Lesson 2 — Parallel sub-agents catch what a serial pass misses (the P176 8-agent audit)

Audits done by a single agent kept missing real problems. P176 dispatched eight Explore sub-agents in parallel with disjoint scopes (manifest + Constitution + forbidden-phrase / finance / Super Agents / creator templates / CLI + shell / marketplace + JS / CI + tests / docs + spot-checks). The swarm surfaced eleven critical issues that a single audit would not have caught: six manifests missing `provenance.append_only=true` (Article III), one TypeScript JSDoc forbidden-phrase leak in `pulse/src/types.ts:24`, and four lighter Super Agent READMEs missing the canonical ecosystem-ally tagline.

The structural lesson: the cost of dispatching N sub-agents in parallel is roughly the same as dispatching one (one round-trip), but the coverage scales. Audits worth doing should be parallel by default. P176 also refuted two prior-audit claims (lighter-agent v2.15 strict failures and an InstallButton clipboard-payload bug) — proof that the swarm catches false positives as well as false negatives.

## Lesson 3 — Sub-agent self-reports must be verified against `git diff --stat`

P168's Fix 5 sub-agent self-reported "no edits" while `git diff --stat` showed +174 lines added. The feature still worked, but the inaccurate self-report would have hidden a real problem in a less-friendly scenario. P173 codified the rule into `CLAUDE.md` section 16: every sub-agent must report files actually modified (full repo-relative paths), line counts (output of `git diff --stat <file>` captured *after* the final edit), and verification commands run with pass / fail status. The main agent must verify the report before committing by running `python scripts/validate_subagent_report.py --claimed <file1> <file2>` and flagging discrepancies in the audit report.

The structural lesson: trust but verify is not a slogan, it is a script. The validator script makes verification a single command instead of a manual diff comparison.

## Lesson 4 — The manifest scanner is one signal, not the whole truth (CLAUDE.md section 17)

For most of Phase 5 the project's "is the repo healthy?" reports were based on `safety/scanner.py` running clean. P173's audit revealed that the scanner was missing entire categories of bugs: Python implementation drift, JS / TS build failures, shell-script defects, CI workflow misconfiguration, and end-to-end claim drift. The project codified the fix into `CLAUDE.md` section 17: a real "is the repo healthy?" report covers ten layers (manifest schema, Constitution rules, forbidden phrases, Python implementation, JS / TS build, shell scripts, CI workflows, tests, docs, and five-claim spot-checks). Status reports must explicitly enumerate what was checked AND what was not checked. "All green" is only acceptable if every layer above was checked.

The structural lesson: a single-signal health check is a confidence laundromat. Honest reports list the surface that was audited and the surface that was deferred.

## Lesson 5 — The Article VIII trailing-list-marker rule means the rule itself cannot quote the rule

`safety/scanner.py` enforces an Article VIII rule about certain trailing-list-marker tokens that signal a vague spec. The first version of the scanner ran clean against itself but flagged every governance file that quoted the rule — `CLAUDE.md`, `docs/CONSTRAINTS.md`, both X launch threads, and the launch-thread mirrors. P172 introduced the marker-based exemption system (`SCANNER:EXEMPT`) that lets governance files quote the rule without tripping it. P176 surfaced one more leak (a TypeScript JSDoc comment in `pulse/src/types.ts:24` literally enumerated the tokens) and P179 surfaced another (`extensions/vscode/README.md:17`). Both were fixed by rewriting to enumerate explicitly instead of using the trailing marker.

The structural lesson: any rule that forbids a textual pattern eventually gets quoted by a doc explaining the rule. The exemption system has to exist from day one.

## Lesson 6 — The Tier-1 / Tier-2 / Tier-3 strategic ladder beats a flat backlog

By the middle of Phase 5 the backlog had thirty-plus candidate features and no good way to choose between them. The Tier-1 / Tier-2 / Tier-3 ladder (introduced via the 10-agent strategic analysis that produced P178, P179, and P180) sorted every candidate into a tier by impact and effort. Tier 1 was the polish sweep (DX wins, standards exports, distribution surfaces, quality gates) — the things that make the project look professional to xAI in a single screenshot. Tier 2 was the strategic surfaces (trust scores, VS Code extension, GitHub Action, VitePress, MCP server, install counter, hero cards, Discord, eval-delta, property + snapshot tests) — the things that compound. Tier 3 is 2027's moonshot work — paid marketplace, xAI partnership, agent-to-agent capability advertisement (RFC v2.16), 50,000 monthly invocations, 5,000 stars.

The structural lesson: a flat backlog is a tax on every prioritization conversation. A tier ladder collapses the conversation to "which tier are we in this week?"

## Lesson 7 — Stop-hook discipline keeps reports honest

The harness ships a stop hook that runs at the end of every session. The hook surfaces partial work, missing verifications, and uncommitted edits. The discipline is to read the hook output and address it before the session closes. The reports that drifted from reality were almost always reports that ignored the stop-hook output.

The structural lesson: tooling that catches drift only works if you read what the tooling tells you.

## Lesson 8 — AI-assisted execution is a multiplier, not a replacement

The project executed 181 numbered prompts in one calendar year with one human creator. That is only possible because every prompt is structured (the seven-section template at `docs/PROMPT_TEMPLATE.md`), every output is verifiable (the scanner + the test suite + the layer-10 health check), and every commit message follows `phase-N: <verb> <what>`. The structural lesson: AI-assisted execution scales linearly with how rigorously the human structures the prompts and verifies the outputs. A loose prompt produces a loose output produces a loose system.

> Not financial advice. References to X Money tools throughout this section are descriptive only.
