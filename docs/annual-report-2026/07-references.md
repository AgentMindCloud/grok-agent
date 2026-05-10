<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# References

Every link cited in the 2026 annual report, numbered consecutively and resolvable against the `AgentMindCloud/grok-agent` repository at the 2026-12-31 snapshot.

## Governance and standards

- [1] `CLAUDE.md` — permanent instruction file (Hard Six, Soft Rules, sections 1–18).
- [2] `LICENSE` — full Apache 2.0 text.
- [3] `HANDOFF_LOG.md` — 181-row prompt execution ledger (P1 -> P181).
- [4] `ROADMAP.md` — five-phase roadmap summary.
- [5] `CONTRIBUTING.md` — contribution model.
- [6] `SECURITY.md` — vulnerability disclosure.
- [7] `CODE_OF_CONDUCT.md` — community standards.
- [8] `docs/PROJECT_DNA.md` — official facts (file tree, stack, phases, glossary).
- [9] `docs/PROMPT_TEMPLATE.md` — seven-section prompt structure.
- [10] `docs/CONSTRAINTS.md` — Hard Six + Soft Rules + forbidden phrases.
- [11] `docs/PARAMETERIZED_RECIPES.md` — Recipes A, B, C.
- [12] `docs/SOURCES.md` — map of all reference documents.

## CLI and manifest standard

- [13] `cli/grok-agent.ps1` — primary PowerShell-first CLI, 1,174 lines, 24 functions.
- [14] `cli/grok-agent.py` — Python fallback CLI.
- [15] `cli/error-codes.md` — twelve documented error codes for `--Explain`.
- [16] `spec/v2.15/grok-agent.yaml` — unified manifest standard.
- [17] `spec/v2.15/changelog.md` — v2.14 -> v2.15 migration notes.
- [18] `spec/v2.15/windows-extensions.yaml` — Windows extension block.
- [19] `spec/v2.15/schema.json` — JSON Schema 2020-12 export (44.9 KB, 21 top-level properties, 27 `$defs`).
- [20] `spec/v2.15/openapi.yaml` — OpenAPI 3.1 envelope.
- [21] `scripts/export-openapi.py` — schema exporter with `--check` drift detection.

## Safety system

- [22] `safety/scanner.py` — 34 registered checks (`@register` decorators).
- [23] `safety/constitution.md` — Articles I through VIII.
- [24] `scripts/validate_subagent_report.py` — sub-agent self-report integrity validator (`CLAUDE.md` section 16).

## Marketplace, trust scores, and hero cards

- [25] `marketplace/` — Next.js static-exported marketplace.
- [26] `marketplace/data/install-counts.json` — 33-slug seed install counts.
- [27] `marketplace/components/InstallButton.tsx` — clipboard-safe install payload.
- [28] `marketplace/components/TrendingThisWeek.tsx` — top-five trending block.
- [29] `marketplace/app/api/install/[slug]/route.ts` — per-slug install-count API.
- [30] `marketplace/app/api/badge/[slug]/route.ts` — Spectral v1 SVG badge.
- [31] `marketplace/app/api/trust-badge/[slug]/route.ts` — per-slug trust-tier SVG.
- [32] `marketplace/public/hero-cards/` — 33 SVG hero cards (110,093 bytes total).
- [33] `scripts/compute-trust-score.py` — trust-score formula `0.4*scanner + 0.3*eval + 0.2*provenance + 0.1*stability`.
- [34] `scripts/generate-hero-card.py` — 1280x640 hero-card SVG generator.
- [35] `docs/agent-trust-scores.json` — 33-agent trust-score export.

## Pulse MCP server

- [36] `pulse/src/grok-agent-tools.ts` — MCP tool builder (493 lines).
- [37] `pulse/src/index.ts` — MCP runtime wiring.
- [38] `pulse/README.md` — Claude desktop integration guide.

## VS Code extension and GitHub Action

- [39] `extensions/vscode/package.json` — schema-only extension v0.1.
- [40] `extensions/vscode/schemas/grok-manifest.json` — bundled JSON Schema.
- [41] `extensions/vscode/README.md` — v0.2–v0.5 roadmap.
- [42] `actions/validate-manifest/action.yml` — composite GitHub Action.
- [43] `actions/validate-manifest/README.md` — action usage docs.

## VitePress documentation site

- [44] `docs/.vitepress/config.ts` — sidebar, nav, palette, search.
- [45] `docs/.vitepress/theme/index.ts` — theme entry plus global SchemaValidator component.
- [46] `docs/.vitepress/theme/vars.css` — Spectral v1 cinnabar + parchment palette.
- [47] `docs/.vitepress/components/SchemaValidator.vue` — interactive client-side schema explorer.
- [48] `docs/schema-explorer.md` — schema explorer page.
- [49] `docs/index.md` — public docs landing.
- [50] `docs/windows-guide.md` — Windows install + run instructions.
- [51] `docs/for-xai-adoption.md` — pitch to xAI for adoption.

## Templates

- [52] `templates/finance/x-money-companion-dashboard/` — X Money tool 1.
- [53] `templates/finance/x-smart-cashtag-alpha-engine/` — X Money tool 2.
- [54] `templates/finance/x-money-vision-analyzer/` — X Money tool 4.
- [55] `templates/finance/x-creator-payout-optimizer/` — X Money tool 3.
- [56] `templates/super-agents/living-narrative-fabric/` — flagship Super Agent 1.
- [57] `templates/super-agents/self-evolving-personal-os/` — flagship Super Agent 2.
- [58] `templates/super-agents/cross-reality-action-fabric/` — flagship Super Agent 3.
- [59] `templates/super-agents/agent-swarm-with-shared-memory/` — lighter Super Agent.
- [60] `templates/super-agents/provenance-first-trust-engine/` — lighter Super Agent.
- [61] `templates/super-agents/narrative-contradiction-detector/` — lighter Super Agent.
- [62] `templates/super-agents/zero-config-i-want-to-agent/` — lighter Super Agent.
- [63] `templates/creator/` — 22-template creator catalogue.

## Tests and CI

- [64] `pyproject.toml` — testpaths, pytest markers, dev deps.
- [65] `creator-program/v2/curation/tests/test_weekly_curation.py` — 11 tests.
- [66] `templates/super-agents/self-evolving-personal-os/tests/test_router.py` — 4 tests.
- [67] `tests/property/test_manifest_schema.py` — 3 hypothesis-based tests.
- [68] `tests/snapshot/test_super_agent_stubs.py` — 3 snapshot tests.
- [69] `tests/snapshot/__snapshots__/test_super_agent_stubs.ambr` — syrupy snapshots.
- [70] `tests/README.md` — test layout (smoke / property / snapshot / integration).
- [71] `.github/workflows/validate.yml` — schema + Constitution gate.
- [72] `.github/workflows/tests.yml` — three-job test runner.
- [73] `.github/workflows/pages.yml` — Next.js marketplace deploy.
- [74] `.github/workflows/eval-delta.yml` — per-PR eval delta.
- [75] `.github/workflows/discord-post-curation.yml` — auto-curation digest.
- [76] `.github/workflows/docs-lint.yml` — markdown + link lint.
- [77] `tests/x-money-integration-smoke.ps1` — pwsh-driven cross-tool smoke.

## Marketing, community, and references

- [78] `marketing.md` — 110 ready-to-paste X posts across 10 sections.
- [79] `llms.txt` — llmstxt.org-format AI-targeted summary.
- [80] `community/discord-bootstrap.md` — Discord channel structure plus moderation playbook.
- [81] `community/README.md` — community surface index.
- [82] `scripts/post-discord-digest.py` — auto-curation digest poster.
- [83] `scripts/compute-eval-delta.py` — per-Super-Agent eval-delta computer.
- [84] `scripts/generate-template.py` — autonomous template builder.

## Pitch and partnership

- [85] `docs/pitch/xai-partnership-pitch.md` — xAI partnership pitch.
- [86] `docs/pitch/60-second-demo-script.md` — 60-second demo script.
- [87] `docs/pitch/v2.16-rfc.md` — v2.16 RFC for agent-to-agent capability advertisement.
- [88] `docs/pitch/README.md` — pitch directory index.

## Audit and reports

- [89] `docs/workplan-audit.md` — current Phase 5 work plan.
- [90] `docs/audit-2026-05-06.md` — May audit snapshot.
- [91] `docs/bug-fix-plan-2026-05-06.md` — May bug-fix plan.
- [92] `docs/phase-3-completion-report.md` — Phase 3 close.
- [93] `docs/phase-3-verification-report.md` — Phase 3 verification.
- [94] `docs/phase-4-completion-report.md` — Phase 4 close.
- [95] `docs/phase-6-kickoff.md` — post-Phase 5 kickoff notes.
- [96] `docs/smoke-test-results.md` — smoke-test outputs.
- [97] `docs/x-launch-thread.md` — first public launch thread.
- [98] `docs/live-validator/` — live validator artifacts.

## Sibling deliverables in this annual-report swarm

- [99] `docs/whitepaper-manifest-standard.md` — companion whitepaper on the v2.15 manifest standard.
- [100] `docs/press-kit/` — companion press kit for journalists.

> Built for xAI, X, Grok and the ecosystem community. ❤️
