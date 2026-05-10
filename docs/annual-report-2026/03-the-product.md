<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# The product

Grok Agent OS is not one tool. It is a portfolio of surfaces — a CLI, a manifest standard, a safety scanner, a marketplace, an MCP server, a VS Code extension, a GitHub Action, a documentation site, a trust-score formula, hero cards, an install counter, a Discord bootstrap, and a CI eval-delta workflow — all unified by one principle: a creator on Windows 11 should be able to type one PowerShell command and end up with a working Grok agent on X.

This section walks every shipped surface.

## The CLI (`cli/grok-agent.ps1`, 1,174 lines)

The CLI is the front door. It is PowerShell-first by design — Windows 11 + PowerShell is the OS that the broadest base of X creators actually run, and PowerShell is the shell that ships with every default Windows install. There is a Python fallback at `cli/grok-agent.py` for non-Windows hosts and CI environments.

The CLI exposes the verbs `install`, `new`, `validate`, `list`, `run`, `doctor`, and `explain`. It is dispatched as `grok-agent <verb> [...]`. The end-of-year polish sweep at P178 added two new affordances:

- **`Invoke-Doctor`** runs six health checks (PowerShell version, Python on PATH, pydantic + pyyaml importable, AppData writable, ExecutionPolicy, repo layout sanity). It is the first thing a confused user should run.
- **`Invoke-Explain` plus the `-Explain <E-XXXX-NNN>` parameter** reads `cli/error-codes.md` for any of twelve documented codes spanning E-CLI / E-INSTALL / E-VALIDATE / E-SCANNER / E-RUN / E-INTERNAL. Every code carries an Article reference, a cause, a fix, and an exit code. The unknown-command branch emits `[E-CLI-001]` so users discover the system without prompting.

`Invoke-Install` also gained an ASCII install-flow recap printed after every successful install — Unicode box-drawing with check-marks visualizing the four install steps (download manifest, validate, scan, persist). This single visual is now the most-screenshotted artifact in the marketing assets.

## The v2.15 manifest standard (`spec/v2.15/`)

Every agent in the repository declares `version: 2.15` and validates against `spec/v2.15/grok-agent.yaml`. The standard accepts any valid v2.14 manifest unchanged (auto-upgrade during `grok-agent validate`), preserving backwards compatibility while extending the schema with the seven Super Agent surfaces, the `windows` extension block, the `multi_agent` orchestration block, the `real_time_x` X-firehose block, and a typed `DemoVideo` Pydantic model that replaces the prior loosely-typed field.

P178 also exported the schema as JSON Schema 2020-12 (`spec/v2.15/schema.json`, 21 top-level properties + 27 `$defs`) and an OpenAPI 3.1 envelope (`spec/v2.15/openapi.yaml`) via `scripts/export-openapi.py`. The script supports `--check` mode for CI drift detection. The same JSON Schema file is bundled into the VS Code extension and the VitePress schema explorer so editor, browser, and CLI all validate identically.

## The safety scanner (`safety/scanner.py`, 34 checks)

The scanner is the contract that holds the project to its own rules. It registers 34 distinct checks (one `@register` decorator each), covering Articles I through VIII of `safety/constitution.md`, the Hard Six rules from `CLAUDE.md`, the verbatim section 12 disclaimers (Not financial advice, Not tax advice, real-world-action consent banner), schema drift between manifests and `spec/v2.15/grok-agent.yaml`, and the Article VIII trailing-list-marker rule.

P172 introduced the marker-based exemption system (`SCANNER:EXEMPT`) so governance files that quote the rules themselves do not trigger the rules. P176 audited the entire repo via an eight-sub-agent parallel swarm and surfaced eleven critical fixes — six manifests gained `provenance.append_only=true` (Article III), one TypeScript JSDoc leak was rewritten to enumerate explicitly, and four lighter Super Agent READMEs gained the canonical ecosystem-ally tagline.

## The marketplace (`marketplace/`, Next.js, 33 agents)

The marketplace is a static-exported Next.js site listing every v2.15 agent in the repository. P175 flipped the `pages.yml` deploy from a hand-written static HTML site to the Next.js build — `next build` now produces 40 static pages (3 super-agents + 4 lighters + 4 finance + 22 creator + system pages). The smoke test in CI asserts five canonical markers in the built output.

The marketplace surfaces:

- **Per-agent install button** (`marketplace/components/InstallButton.tsx`) with a clipboard-safe payload.
- **Trending This Week block** (`marketplace/components/TrendingThisWeek.tsx`) showing the top five agents by seed install count.
- **Per-slug install-count API** (`marketplace/app/api/install/[slug]/route.ts`) — a 307 redirect to the GitHub manifest URL with `force-static` and `generateStaticParams`.
- **Per-slug trust-score badge SVG** (`marketplace/app/api/trust-badge/[slug]/route.ts`) — Spectral v1 cinnabar / parchment / charcoal palette mapped to tiers A / B / C / D.
- **Per-slug hero card SVG** (`marketplace/public/hero-cards/<slug>.svg`, 33 files) — generated by `scripts/generate-hero-card.py` with a charcoal-to-cinnabar diagonal gradient, display name, tagline, kind label, trust-tier corner ribbon, and a parchment "built on Grok Agent OS" footer.
- **Command palette and CRT scanline overlay** for the cyberpunk visual identity.

## The pulse MCP server (`pulse/`)

`pulse/` exposes every template in the repository as a Claude desktop MCP tool. `pulse/src/grok-agent-tools.ts` (493 lines) registers `grok-agent-<slug>` per template with an `action` enum of `describe` / `install_command` / `manifest_url`. Wiring to the MCP runtime is in `pulse/src/index.ts`. The README documents the Claude desktop config snippet to drop into `~/.config/Claude/claude_desktop_config.json`.

## The VS Code extension (`extensions/vscode/`)

A schema-only VS Code extension at v0.1: `package.json` declares `extensionDependencies: ["redhat.vscode-yaml"]` plus `contributes.yamlValidation` mapping every `**/grok-agent.yaml` file to the bundled JSON Schema. The schema is kept in sync with `spec/v2.15/schema.json` by an extension to `scripts/export-openapi.py` that writes a third output and checks it in `--check` mode. The v0.2 through v0.5 roadmap is documented in the extension README.

## The reusable GitHub Action (`actions/validate-manifest/`)

A composite GitHub Action with five inputs (`path`, `strict`, `scanner`, `severity-floor`, `python-version`) and two outputs (`manifest-count`, `status`). It uses `${{ github.action_path }}/../../cli/grok-agent.py` and `safety/scanner.py` to avoid shipping duplicate validators — pinning the action to `@v1` automatically pins both the validator and the scanner.

## The VitePress documentation site (`docs/.vitepress/`)

A VitePress MVP with sidebar groups for Getting Started, Standards, For xAI, and Audit / Reports; a Spectral v1 cinnabar + parchment palette mapped through `--vp-c-brand-*` and `--vp-c-bg-*` for both light and dark modes; nav links to spec v2.15 + schema.json + openapi.yaml; local search; and an edit-on-GitHub link. P180 added the interactive schema explorer at `docs/schema-explorer.md` — a single-file Vue component that loads ajv@8 and js-yaml@4 from esm.sh so it has zero npm runtime dependencies and validates manifests entirely client-side.

## Trust scores (`docs/agent-trust-scores.json`, 33 agents)

The trust-score formula is documented at the top of `docs/agent-trust-scores.json`: `0.4*scanner + 0.3*eval + 0.2*provenance + 0.1*stability`. The script (`scripts/compute-trust-score.py`) supports `--check` for CI drift detection (it ignores `computed_at` so re-runs on the same commit do not trigger drift).

## Hero cards (`marketplace/public/hero-cards/`, 33 SVGs)

`scripts/generate-hero-card.py` walks `templates/*/*/grok-agent.yaml` and emits a 1280x640 SVG per agent (110,093 bytes total, 3.3 KB average). The script supports `--slug` for single-target regeneration and `--check` for drift detection.

## Install counter (`marketplace/data/install-counts.json`)

A seeded JSON file with 33-slug counts — explicitly documented as a seed in the `_note` field. A 2027 production analytics layer will replace this.

## Discord bootstrap (`community/discord-bootstrap.md`)

Ships the channel structure, role taxonomy, welcome template, posting guidelines, moderation playbook, and an explanation of the auto-curation digest workflow.

## The eval-delta workflow (`.github/workflows/eval-delta.yml`)

Triggers on every PR that touches `templates/super-agents/*/eval/**` or `*/prompts/**`, runs `scripts/compute-eval-delta.py` per affected Super Agent (with `git stash` plus `checkout-base` plus run plus restore), and posts a per-metric markdown table as a sticky PR comment via `GITHUB_TOKEN`. It gracefully degrades if Promptfoo or DeepEval is not installed.

## The X Money tools (`templates/finance/`, 4 tools)

Four Streamlit tools — `x-money-companion-dashboard`, `x-smart-cashtag-alpha-engine`, `x-money-vision-analyzer`, `x-creator-payout-optimizer` — built end to end with cross-tool integration (the vision analyzer's `data/import_receipts.py` writes directly into the companion dashboard's SQLite schema).

> Not financial advice. The X Money tools provide information only — portfolio, cashtag, payout, and tax features are descriptive, not advisory. Always consult a licensed financial advisor before making decisions.

> Built for xAI, X, Grok and the ecosystem community. ❤️
