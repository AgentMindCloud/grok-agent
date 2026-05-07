# Audit Report: grok-pulse-mcp-server

**Date:** 2026-05-07
**Auditor:** Claude Code
**Org:** AgentMindCloud
**Ecosystem Role:** Read-only MCP server that aggregates a developer's high-signal GitHub work items across all their repos and runs them through Grok (xAI) for prioritization — positioned as the "what should I work on right now" tool for builders shipping in the xAI/X/Grok ecosystem.

---

## 1. Snapshot

- **Stars / forks / open issues:** unknown (gh CLI unavailable in audit sandbox; no API access)
- **Last commit:** `a40eb1f feat: scaffold + pulse_today tool (v0.1)` — single-commit history
- **Primary language(s):** TypeScript (strict, ES2022, Node16 modules); one PowerShell helper script
- **Total LOC:** 962 lines of TypeScript across `src/` (largest: `src/tools/pulse-today.ts` at 399 LOC, ~15 KB)
- **Dependencies health:** lean and well-chosen (4 prod: `@modelcontextprotocol/sdk` ^1.6.1, `@octokit/rest` ^21.0.2, `axios` ^1.7.9, `zod` ^3.23.8). **Outdated before first ship**: `@octokit/rest` is one major behind (21 → 22), `zod` is one major behind (3 → 4). MCP SDK is also behind (1.6.1 declared vs 1.29.0 latest). `node_modules` not present in repo (expected); `npm audit` complaints about `ip-address`/`express-rate-limit` are stale-cache noise — neither package is declared.
- **CI status:** **none configured.** No `.github/workflows/` directory exists. Zero workflow runs accessible. No build, type-check, lint, or test automation on push/PR.
- **License:** Apache-2.0 — present at root (`LICENSE`, 11260 B), 2026 AgentMindCloud copyright.
- **Required files present:** README ✓, LICENSE ✓, CHANGELOG ✗, CONTRIBUTING ✗, .gitignore ✓ (also missing: `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue/PR templates, `.github/` directory entirely).

---

## 2. File-by-File Findings

### Critical
- `.github/workflows/` — directory does not exist; no CI/CD pipeline of any kind for a TypeScript package that declares a `bin` entry and a `prepublishOnly` hook. Type errors, broken builds, and dependency drift will reach `main` undetected. — **Severity:** Critical

### High
- `README.md:9` — `[\`SPEC.md\`](../SPEC.md)` resolves to a non-existent parent-directory file. Published broken doc link in the project's most-read file. — **Severity:** High
- `README.md:91` — Second instance of the same dead `../SPEC.md` link inside the "Tool reference" section. — **Severity:** High
- `README.md:33` — Misleading claim: "v0.1 is scaffold only — installable and bootable, but tools are not yet wired." `pulse_today` IS wired and registered in `src/index.ts:45` with a 399-LOC implementation. README undersells what shipped. — **Severity:** High
- `README.md:91` — "Full I/O schemas land in v0.2 with the implementations" contradicts the present, fully-defined Zod schema in `src/schemas/tools.ts:16-52` for `pulse_today`. — **Severity:** High
- `package.json:13-19` — No `test` script declared and no test runner in `devDependencies`. `tsconfig.json:23` excludes `**/*.test.ts` while no test files exist anywhere. 962 LOC of token-handling, network-fanout TypeScript with zero coverage at v0.1.0. — **Severity:** High
- `README.md:33,98` — README claims five tools as the v0.2 deliverable but offers no acceptance criteria, schema sketches, or stub files for the four unimplemented ones (`summarize_repo_activity`, `weekly_digest`, `next_action`, `roast_pr`). Roadmap is a list of names, not a plan. — **Severity:** High

### Medium
- `README.md:69` — `[custom MCP server flow](https://docs.claude.com)` points at the docs landing page, not a real "Cowork custom MCP" walkthrough. Misleading — reader clicks expecting a guide and gets the homepage. — **Severity:** Medium
- `README.md` — No `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, or `CODE_OF_CONDUCT.md`. For a public Apache-2.0 repo soliciting contributions ("Issues, PRs, and roasts welcome", line 107), this is community-hygiene debt. — **Severity:** Medium
- `package.json:31` (`@octokit/rest ^21.0.2`) — one major version behind upstream (22.x). Decide before v0.2; pinning a stale major now means a forced upgrade at the worst time. — **Severity:** Medium
- `package.json:33` (`zod ^3.23.8`) — major version behind (4.x available). Schema layer (`src/schemas/*.ts`) is small and migration is cheap right now; cost compounds as schemas grow. — **Severity:** Medium
- `package.json:30` (`@modelcontextprotocol/sdk ^1.6.1`) — significantly behind 1.29.0; SDK has shipped notable feature/fix iterations since 1.6.1. — **Severity:** Medium
- `push.ps1` — 134-line PowerShell first-push helper committed at repo root with zero mention in README. Windows-only contributors will be confused about its purpose; macOS/Linux contributors will wonder why it's there. Either document or remove. — **Severity:** Medium
- `src/tools/pulse-today.ts` — 399 LOC, ~15 KB (over 40% of all TS source). Mixes 5 fetcher functions, URL-rewriting helpers, Grok-prompt construction, character-limit enforcement, and tool registration. Will not scale cleanly to the four additional v0.2 tools described in `README.md:23-27`; refactor into `tools/<tool>/{fetchers,prompt,formatter,index}.ts` before adding more. — **Severity:** Medium
- `src/tools/pulse-today.ts:43` — Notification-URL rewrite uses chained `.replace("api.github.com/repos", "github.com").replace("/pulls/", "/pull/")`. Silent-fail if GitHub changes path shape; no fallback, no warning. — **Severity:** Medium
- `git log` — Single commit (`a40eb1f`) covering a 962-LOC v0.1.0 release. No tags, no release notes, no incremental diffs to reason about. Future bisects will be useless. — **Severity:** Medium

### Low
- `src/types.ts:59-71` — `RepoActivitySummary` interface is fully defined but not consumed anywhere (reserved for unimplemented `summarize_repo_activity`). Either land it with a TODO marker or move to a `types/v0.2.ts` to keep v0.1 surface clean. — **Severity:** Low
- `src/schemas/common.ts:12-17` — `PaginationSchema` exported but never imported. Same dormant-for-v0.2 status as above. — **Severity:** Low
- `src/services/github.ts:45`, `src/services/grok.ts:79` — `_resetGitHubCacheForTests`/`_resetGrokCacheForTests` exports exist for test isolation, but no test infrastructure consumes them. Harmless but signals an unfinished plan. — **Severity:** Low
- `src/index.ts:22-34` — Env validation throws synchronously on missing `GITHUB_TOKEN`/`XAI_API_KEY`; error goes to stderr and process exits. Acceptable for stdio MCP, but no structured exit code for clients to differentiate auth-missing vs runtime-failure. — **Severity:** Low
- `src/tools/pulse-today.ts:294-298` — Tool annotations declare `idempotentHint: true`, but invoking the tool consumes Grok rate-limit budget and emits side effects on the xAI side. Strictly the *result-shape* is idempotent; the *operation* is not. Minor semantic stretch. — **Severity:** Low
- `src/tools/pulse-today.ts:72` — `extractRepoFromIssueUrl` regex `/repos\/([^/]+\/[^/]+)$/` assumes 2-segment owner/repo with no trailing slash; works today, brittle to GitHub URL drift. Add an inline comment explaining the assumption. — **Severity:** Low
- `package.json:7` — `bin` declares `grok-pulse-mcp-server` pointing at `dist/index.js` but `dist/index.js` has no `#!/usr/bin/env node` shebang verified in source (`src/index.ts` doesn't start with one). Will fail when installed globally. — **Severity:** Low

### Nit
- `.env.example:11` — Trailing spacing inconsistency between sections (some have a single blank line, others two). — **Severity:** Nit
- `README.md:107` — "Issues, PRs, and roasts welcome" — playful but lacks a real contribution path because no `CONTRIBUTING.md` exists. Drops a reader at a dead end. — **Severity:** Nit
- `src/constants.ts:30` — File is 30 lines for ~10 constants; could colocate with `types.ts` or `schemas/common.ts` until it earns its own module. — **Severity:** Nit

_No long-tail findings beyond what is listed; the codebase is small enough that the bullets above are exhaustive._

---

## 3. Cross-Cutting Issues

- **Unescaped `@grok` mentions:** **0 found.** `grep -rn "@grok" --include=*.md --include=*.html --include=*.yaml --include=*.yml --include=*.txt` returned nothing. The repo references "Grok" (the model) and `@JanSol0s` (the author handle on X), neither of which collide with the GitHub Sterling-Hamilton problem. Clean on this front.
- **Schema/version drift:** `package.json` `version` (0.1.0) and `src/constants.ts:SERVER_VERSION` are aligned. README badge declares "v0.1 scaffold". No internal version drift detected. There is, however, **published-vs-implemented drift**: README describes a five-tool surface, code ships one (`README.md:21-27` vs `src/index.ts:45`).
- **Documentation freshness:** README is mostly fresh — written within days of the commit — but contains three concrete inaccuracies: dead `../SPEC.md` link (×2), generic `docs.claude.com` link, and the "tools are not yet wired" claim that contradicts the shipped `pulse_today`. Update lag between code and docs is already visible at v0.1.
- **Brand/visual consistency:** N/A. No HTML, CSS, or visual assets exist (no `public/`, no `docs/`, no SVGs). The repo is server-only. README uses standard shields.io badges; consistent enough.
- **Dead code / orphan files:** No truly dead code. `RepoActivitySummary` (`types.ts:59`), `PaginationSchema` (`schemas/common.ts:12`), and the two `_resetXForTests` exports are dormant-for-v0.2 reservations — defensible if v0.2 ships within weeks, dead-code if v0.2 slips. `push.ps1` is the closest thing to an orphan: present, undocumented, platform-specific.
- **Test coverage:** **Zero.** No `test/` or `__tests__/` directory, no `*.test.ts` files, no test runner in `devDependencies`, no `test` script in `package.json`. `tsconfig.json:23` reserves the `**/*.test.ts` exclude pattern but nothing fills it. For a server that handles GitHub PATs and xAI keys and does network fanout with partial-failure semantics, this is the single most important gap.
- **Security posture:** Strong at the source level. Token redaction patterns in `src/services/errors.ts:15-20` cover `github_pat_*`, `ghp_*`, `xai-*`, and `Bearer` tokens; redaction is applied before any error reaches the LLM-bound output (`README.md:85` makes this an explicit promise). `.gitignore` correctly excludes `.env`, `*.token`, `*.pat`, `.gh_*`. `.env.example` contains only placeholder strings. `grep` for hardcoded keys returned zero hits. Env vars are validated upfront in `src/index.ts:22-34`. Weak spots: no `SECURITY.md` to direct vuln reports; no automated dependency scanning (Dependabot/Renovate config absent); no CI to enforce that `npm audit` stays clean.

---

## 4. What's Working Well

1. **Error-handling architecture in `src/services/errors.ts` is exemplary.** Token redaction is pattern-based and covers every credential class the server touches; per-API error mapping (GitHub 401/403/404/422; xAI 401/429/400/5xx) returns actionable messages instead of raw upstream errors. This is the kind of file you'd copy-paste into the next MCP server.
2. **Parallel fetch with per-section fault isolation in `src/tools/pulse-today.ts:310-316`.** Five independent GitHub queries fan out concurrently; one fails, the others still produce a useful pulse. Grok summary is wrapped so an xAI outage doesn't collapse the tool — raw data still returns with an inline error note (`pulse-today.ts:336-346`).
3. **Strict separation of internal types vs tool I/O schemas.** `src/types.ts` is implementation-shape; `src/schemas/tools.ts` is Zod-validated public contract with `.strict()` enforcement. This pattern scales cleanly to additional tools and prevents accidental output-shape drift.
4. **Lean, deliberate dependency choice.** Four prod deps (MCP SDK, Octokit, plain `axios` instead of the OpenAI SDK, Zod). No bloat, no incidental complexity. Easy to audit, easy to upgrade.
5. **Secret hygiene end-to-end.** `.env.example` is well-documented, `.gitignore` is thorough, env validation is upfront, and the README explicitly promises tokens never reach the LLM (`README.md:85`) — and the code backs it up.

---

## 5. Top 5 Improvements (Ranked by Impact ÷ Effort)

| # | Improvement | Impact (1-10) | Effort (hours) | Why it matters |
|---|---|---|---|---|
| 1 | Add `.github/workflows/ci.yml` (Node 20 matrix → `npm ci` → `tsc --noEmit` → placeholder `npm test`) | 9 | 1 | First-line defense against type/build regressions; required before shipping v0.2; signals project is alive. |
| 2 | Wire a test runner (`vitest`) and write smoke tests for `pulse-today` fetchers, error redaction, and markdown formatter | 9 | 6-8 | 962 LOC handling user PATs cannot ship to the public without a single test. The two `_resetForTests` exports already exist for this. |
| 3 | Fix the three concrete README inaccuracies: drop `../SPEC.md` links (lines 9, 91), replace `docs.claude.com` (line 69) with a real Cowork doc URL, correct line 33's "tools are not yet wired" claim | 7 | 0.25 | Public README is the front door; three broken/misleading statements undermines credibility for a repo whose pitch is "first MCP for the xAI/X/Grok ecosystem". |
| 4 | Add `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, plus a Dependabot/Renovate config | 6 | 1.5 | Closes community-hygiene gap, automates dep upgrades the audit just flagged (Octokit 21→22, Zod 3→4, MCP SDK 1.6→1.29). |
| 5 | Refactor `src/tools/pulse-today.ts` (399 LOC) into `src/tools/pulse-today/{fetchers,prompt,formatter,index}.ts` before any other tool lands | 7 | 2-3 | Doing this now is cheap; doing it after the four other tools land in `src/tools/` will be expensive and the temptation will be to copy-paste-grow. |

---

## 6. Quick Wins (≤30 min each)

- **Delete or document `push.ps1`.** Either remove from repo (one-time-use init script, already executed for `a40eb1f`) or add a README sub-section "First-time push (Windows)" referencing it. Run `git rm push.ps1` if removing.
- **Fix `README.md:9` and `README.md:91`** — change `[\`SPEC.md\`](../SPEC.md)` → either remove the link entirely or check the SPEC into this repo at `docs/SPEC.md` and link as `[\`docs/SPEC.md\`](docs/SPEC.md)`.
- **Replace `README.md:69`** `https://docs.claude.com` → the actual Cowork "custom MCP server" doc URL, or remove the link and write "follow your client's custom MCP server instructions."
- **Update `README.md:33`** — change "tools are not yet wired" to "one tool (`pulse_today`) ships in v0.1; four more land in v0.2." Reflects what actually shipped.
- **Add `CHANGELOG.md`** with a single `## [0.1.0] - 2026-05-07` entry summarizing the scaffold + `pulse_today`. Two-minute job, immediate signal of project rigor.
- **Add `SECURITY.md`** with a one-liner: report vulnerabilities to `<email>` and a 90-day disclosure window. Stops the "where do I report this?" question before it's asked.
- **Bump `@modelcontextprotocol/sdk` to `^1.29.0`** in `package.json:30` and run `npm install` locally; the API surface used (`Server`, `StdioServerTransport`, `setRequestHandler`) has been stable across that range.
- **Add a shebang to `src/index.ts`** (`#!/usr/bin/env node`) and `chmod +x` the `dist/index.js` build output via a postbuild step — the `bin` field in `package.json:7` won't work globally without it.
- **Add `.github/dependabot.yml`** with `package-ecosystem: npm` weekly updates. Keeps Octokit/Zod/MCP SDK from rotting again.
- **Inline-comment `src/tools/pulse-today.ts:43`** explaining the URL-rewrite assumptions, so the next person doesn't have to deduce them from the regex.

---

## 7. Ecosystem Potential Statement

This is the **only MCP server in the AgentMindCloud / xAI-Grok-X portfolio that closes the loop between Grok-as-LLM and a developer's actual GitHub workload** — every other agent-facing tool in the ecosystem treats Grok as a black-box completion engine, while this one uses Grok specifically for *prioritization*, which is the one thing GitHub's own UI and notification system cannot do for a multi-repo solo builder. **Maturity: late-prototype / early-alpha** — single commit, one of five advertised tools implemented, zero tests, zero CI; the *engineering quality* of what exists (error handling, fault isolation, secret hygiene) is production-grade, but the *project surface* (no CHANGELOG, no CI, no SECURITY.md, broken README links) reads as a scaffold dropped in a single push. With six months of focused investment — finish the four v0.2 tools, ship CI + tests, write one strong launch post tied to `@JanSol0s`'s X presence and a real Cowork/Claude-Code integration demo — realistic adoption sits in the **300-1500 stars range** with a credible path to becoming the default "what should I work on" MCP for the long tail of solo xAI builders; revenue path is thin (read-only OSS, no hosted tier yet) but strategic value to AgentMindCloud is high because it's the natural anchor for a future hosted "Grok Pulse" SaaS. **The single biggest unlock is a 90-second demo video** (Claude Code → `pulse_today` → Grok-prioritized output) shipped alongside a real `SPEC.md` and a working CI badge — that one bundle converts the repo from "interesting scaffold" to "obviously useful tool" and moves it past the credibility cliff that's currently keeping the star count near zero. **Resource verdict: invest decisively for ~2 weeks** to land v0.2 + tests + CI + the demo, then re-evaluate based on adoption signal; the unit economics of finishing this are excellent because the hard part (error/auth/fault-isolation architecture) is already done.

`POTENTIAL_TAG: DOUBLE_DOWN — Solid engineering core, unique ecosystem niche, two-week sprint converts scaffold into shippable v1.`
