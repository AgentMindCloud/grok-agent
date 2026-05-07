# Audit Report: x-platform-toolkit

**Date:** 2026-05-07
**Auditor:** Claude Code
**Org:** AgentMindCloud
**Ecosystem Role:** Single-file HTML demo monorepo of 12 X/Grok-native productivity tools — the "live showcase" sibling to the grok-install spec/CLI/marketplace family.

---

## 1. Snapshot

- **Stars / forks / open issues:** unknown (gh CLI unauthenticated in audit env)
- **Last commit:** 2026-05-05 by AgentMindCloud (`87ce5d3` — "Revise tool count from 20 to 12 in README")
- **Primary language(s):** JavaScript (Node CJS + browser ESM), HTML, CSS. No TypeScript, no Python despite audit allowlist.
- **Total LOC:** ~3,690 across `.js / .ts / .tsx / .py / .html / .css` (excluding `node_modules`)
- **Dependencies health:** **vulnerable + broken install state.** `npm audit` reports 1 high (`basic-ftp ≤5.3.0` DoS) and 1 moderate (`ip-address ≤10.1.0` XSS). `npm ls --depth=0` errors with `ELSPROBLEMS` — all 7 declared devDeps and all 5 workspace packages are `UNMET DEPENDENCY` in the audit environment.
- **CI status:** **Currently broken.** Single workflow `validate.yml` has 5 jobs (lint-and-test, validate-html, validate-css, link-check, assert-categorization). The `assert-categorization` job runs `scripts/assert-tool-status.mjs`, which declares 20 tools but only 12 exist on disk → CI exits 1 on every push until the script is updated.
- **License:** Apache-2.0 — full canonical text present at `/LICENSE`. ✓
- **Required files present:** README.md ✓, LICENSE ✓, CHANGELOG.md ✓ (stale), CONTRIBUTING.md ✓, .gitignore ✓, CODE_OF_CONDUCT.md ✓, SECURITY.md ✓

---

## 2. File-by-File Findings

### Critical

- `README.md:14` vs `README.md:19,24,33,55,106` — root README internally contradicts itself: tagline says "12 tools," badges/typing-SVG/anchor/header all say "20 Tools." Mid-edit shipped to `main`. — **Severity:** Critical
- `README.md:111` — table row links to `tools/02-follower-intent-classifier/`, which was deleted in commit `206c231`. Click-through is a 404. — **Severity:** Critical
- `README.md:110` — first table row "| 01 |" is empty/truncated, producing a malformed table cell in the published README. — **Severity:** Critical
- `CHANGELOG.md:13-17` — claims "6 LIVE tools shipped" listing `04, 05, 07, 09, 12, 18`. Tools 09 and 18 have no folders on disk; CHANGELOG ships demonstrably false repo-state claims. — **Severity:** Critical
- `scripts/assert-tool-status.mjs:20-41` — `TOOL_STATUS` map declares all 20 numbered tools; only 12 exist. The `declared.has(name) / present.has(name)` cross-check exits non-zero in CI. — **Severity:** Critical

### High

- `README.md:60,63,144-145` — "6 Live / 14 Spec'd" stated three times in copy plus the Mermaid diagram. Reality: 4 LIVE `index.html` files (04, 05, 07, 12), 8 SPEC.md files, 1 scaffold (19). — **Severity:** High
- `docs/ROADMAP.md:13-32` — references unbuilt tools 01, 02, 08, 10 as if they're in the spec; these folders were deleted in recent commits (`a4637ff`, `206c231`, `0633a2d`, `bc85825`). — **Severity:** High
- `docs/tokens.md:101-122` — per-tool requirements table lists 20 tools including 01, 02, 08, 09, 10, 14, 15, 18, 19. Most of these directories don't exist. — **Severity:** High
- `tools/05-pinned-post-ab-rotator/index.html:327` — "Clear all data" calls `localStorage.clear()`, wiping every key on the origin instead of the tool's own `xpt-pinned-rotator-v1` key. Will trash neighboring tools' state if hosted on a shared origin. — **Severity:** High
- `tools/12-controversy-detector/index.html:834` — same `localStorage.clear()` blast-radius bug. — **Severity:** High
- `tools/05-pinned-post-ab-rotator/index.html:163,167` — `if (!(imp > 0))` and `if (!(fol > 0))` block legitimately recording 0-follow / 0-impression results, breaking the "find your worst converter" use case. — **Severity:** High
- `tools/19-grok-thread-composer/README.md:22-24` (and `SPEC.md`) — claims tech stack is "Vite + React + Tailwind"; `tools/19-grok-thread-composer/package.json` declares zero React/Vite/Tailwind dependencies. Reality is a static `serve`-based scaffold. — **Severity:** High
- `tools/19-grok-thread-composer/src/index.html:14-15` — `<link href="/shared/ui-kit/tokens.css">` only resolves when the tool is served from the repo root via the bespoke `npm run dev` script; opening the file directly or serving the tool dir alone yields 404s. No build step bundles. — **Severity:** High
- `tools/19-grok-thread-composer/package.json:9` — `dev` script depends on the `serve` package, which isn't a declared dependency. Relies on `npx` network fetch every run. — **Severity:** High
- `package.json` (root) — `npm audit` reports 2 vulnerabilities: `basic-ftp ≤5.3.0` (high — DoS via unbounded multiline FTP buffering) and `ip-address ≤10.1.0` (moderate — XSS in Address6 HTML emitters). Fix available via `npm audit fix`. — **Severity:** High
- `CODE_OF_CONDUCT.md:21` says `conduct@AgentMindCloud.com`; `SECURITY.md:7` says `security@agentmindcloud.dev`. Two different domains; one is likely fake or unmaintained. — **Severity:** High
- `README.md:113,114,119` vs `tools/04/README.md:3`, `tools/05/README.md:3`, `tools/12/README.md:3` — root table labels tools 04 ("AI Analytics" vs tool's "Analytics"), 05 ("Automation" vs tool's "Analytics"), 12 ("AI Analytics" vs tool's "AI Writing"). Category drift across docs. — **Severity:** High
- `README.md:84` (Categories block) vs `tools/13-thread-to-newsletter-converter/README.md:3` and `README.md:121` — newsletter converter is "AI Writing" in one place, "Automation" in two others. — **Severity:** High
- `.github/workflows/validate.yml:35` — `npx html-validate "tools/*/index.html"` only globs the top level. Tool 19's HTML at `tools/19-grok-thread-composer/src/index.html` is silently skipped. — **Severity:** High

### Medium

- `package.json:17` requires `node >=20`, but `shared/x-api-client/package.json:18` and `shared/grok-client/package.json:18` say `node >=18`. `README.md:165-166` documents "Node ≥18". Developers on Node 18 will fail at the root install. — **Severity:** Medium
- `tools/19-grok-thread-composer/SPEC.md:24` and `tools/13-thread-to-newsletter-converter/SPEC.md:25` reference default model `grok-4`; everywhere else (`README.md:155`, `docs/tokens.md:27`, both fixture JSONs, SPECs for 03 and 11) uses `grok-2-latest`. Model version drift. — **Severity:** Medium
- `tools/04-pre-post-virality-scorer/index.html:486-500` — `scoreFormat` is logically dead-coded: line 488 `if (text.indexOf("\n") !== -1) return 15;` short-circuits before the multi-line for-loop on lines 490-498 can ever execute. — **Severity:** Medium
- `tools/05-pinned-post-ab-rotator/index.html:201-208` — `changeInterval` recomputes `nextSwapAt = startedAt + new interval`, which can leave `nextSwapAt < Date.now()`. The countdown sticks at `00:00:00` until the user manually clicks "Rotate Now". — **Severity:** Medium
- `tools/12-controversy-detector/index.html:551,555` — `DEFAULT_KEYWORDS` declared as empty object literal but never read; `state.keywords` is initialized inline on line 555. Dead constant. — **Severity:** Medium
- `tools/04-pre-post-virality-scorer/index.html:380`, `tools/05-pinned-post-ab-rotator/index.html`, `tools/12-controversy-detector/index.html:507` — `<textarea>` and `<input>` controls without associated `<label for>`. Tool 07 is the only one that does it correctly. — **Severity:** Medium
- `tools/04, 05, 07, 12 — index.html (top of file)` — each tool re-inlines its own copy of `:root` design tokens and component classes instead of consuming `shared/ui-kit/*.css`. Future token changes require editing every live tool. — **Severity:** Medium
- `tools/05-pinned-post-ab-rotator/index.html:12` — inlined token block is missing `--neon-amber`, `--gradient-magenta`, `--gradient-warm`, `--glow-magenta`, `--radius-sm`, `--transition-*`, and the `--space-*` scale that exist in `shared/ui-kit/tokens.css`. Token drift, magic numbers used downstream. — **Severity:** Medium
- `tools/05-pinned-post-ab-rotator/index.html:160,164` — uses blocking `prompt()` for impressions/follows entry. Rough UX for a tool presented as polished. — **Severity:** Medium
- `tools/07-content-compound-calculator/index.html:491` — Chart.js loaded from `cdn.jsdelivr.net/npm/chart.js` with no version pin and no `integrity` (SRI). Supply-chain risk; behavior can change without a code change. — **Severity:** Medium
- `shared/ui-kit/components.css:5` (and every live tool) — Google Fonts loaded synchronously from `fonts.googleapis.com`. Privacy concern (third-party network), perf cost, and breaks fully offline use. — **Severity:** Medium
- `shared/grok-client/src/index.js:64` — `complete(prompt, options)` forwards `options` to `chat()`; when callers pass `tools`, `chat()` returns `{content, tool_calls}` shape, so `complete()` returns an object instead of a string. Not documented in JSDoc. — **Severity:** Medium
- `shared/x-api-client/src/index.js:35` — `getUserByUsername(username)` interpolates `username` directly into the URL with no `encodeURIComponent`. — **Severity:** Medium
- `assets/banner.svg`, `assets/icon.svg` — exist on disk but no markdown references them. README uses external `capsule-render.vercel.app` URL instead. Dead assets and unnecessary third-party dependency. — **Severity:** Medium
- `shared/ui-kit/shell.html:13-16` — empty `<style>` block with comment "INLINE tokens.css and components.css here", never used by any tool. Dead template. — **Severity:** Medium
- `.github/workflows/validate.yml:47` — `stylelint "tools/**/*.css"` matches zero files because all CSS is inlined in HTML. Misleading glob. — **Severity:** Medium
- `tools/04-pre-post-virality-scorer/index.html:447-457` — `scoreHook` `break`s after the first power-phrase match, so power phrases don't stack despite the comment suggesting `signals++` accumulation. — **Severity:** Medium
- `shared/x-api-client/src/index.js:47` — `URLSearchParams({ max_results: maxResults })` passes a number; the browser-mjs build (line 64) explicitly does `String(maxResults)`. Inconsistent stringification approach across builds. — **Severity:** Medium
- `shared/grok-client/src/index.js:11` and `shared/grok-client/browser.mjs:14` — default model `grok-2-latest` hardcoded in two places. Future model deprecation requires two-file change. — **Severity:** Medium
- `tools/19-grok-thread-composer/src/main.js:51-55` — User journey items #1-6 are all TODO stubs; the tool is non-functional despite being scaffolded into the workspace. — **Severity:** Medium
- `README.md:101-103` — Categories block lists "Warm-introduction mapper" and "Spaces recorder with auto-clips" under Network + Media; neither folder exists on disk. — **Severity:** Medium

### Low

- `tools/04-pre-post-virality-scorer/index.html:497` — `if (lines.length > 1)` block follows the dead branch above and would never produce a different return. — **Severity:** Low
- `tools/12-controversy-detector/index.html:597` — `lerpColor` uses local var `b2` for blue channel because parameter `b` shadows it. Readability nit. — **Severity:** Low
- `tools/19-grok-thread-composer/src/main.js:30` and `tools/19-grok-thread-composer/test/smoke.test.js:4` — `eslint-disable-next-line no-unused-vars` annotations papering over scaffold TODO state. Pollutes lint signal. — **Severity:** Low
- `shared/ui-kit/tokens.css:54-62` — `--space-1`, `--space-12`, `--space-16` defined but unused anywhere in the shipped CSS. — **Severity:** Low
- `tools/05-pinned-post-ab-rotator/index.html:283` — empty content shows as the literal string `(no content)` in the active card. Works, but a dedicated empty-state would be cleaner. — **Severity:** Low
- `README.md:264` — stray `</p>` close tag at end of file; nothing visible to pair. — **Severity:** Low
- `tools/13-thread-to-newsletter-converter/README.md:1` — heading uses "Auto-Converter"; root README and `docs/tokens.md` call it "Converter" (no "Auto-"). Naming drift. — **Severity:** Low
- `.github/workflows/validate.yml:16,17,29,30,...` — actions pinned to major tags (`@v4`) rather than commit SHAs. Standard practice but worth noting for a security-conscious repo. — **Severity:** Low
- `tools/04-pre-post-virality-scorer/index.html:599` — IIFE wraps the script but no `'use strict'`. Tools 07/12 do declare strict mode. — **Severity:** Low
- `tools/12-controversy-detector/index.html:583` vs `tools/05-pinned-post-ab-rotator/index.html` (`escapeHtml` vs `esc`) vs `tools/04-pre-post-virality-scorer/index.html` (no escape, only static inserts) — three different approaches to HTML escaping across live tools. — **Severity:** Low

### Nit

- `shared/ui-kit/components.css:8` — universal `* { margin: 0; padding: 0; }` reset is heavy-handed in 2026. — **Severity:** Nit
- `docs/BRAND.md:32` — swatch row has 5 column headers but 6 cells. Cosmetic table imbalance. — **Severity:** Nit
- `tools/19-grok-thread-composer/README.md:5` — uses unicode arrow `→` in the status string `Spec'd → Scaffold`; one-off pattern not repeated elsewhere. — **Severity:** Nit
- `README.md:23-29` — badges are static `img.shields.io` URLs (not dynamic shields tied to repo state). — **Severity:** Nit

(Long tail: dozens of cosmetic CSS duplications between the four live tools' inlined component blocks, repeated `box-sizing` resets, and minor mono-font-stack inconsistencies. None functionally significant.)

---

## 3. Cross-Cutting Issues

- **Unescaped `@grok` mentions:** **0 occurrences.** Cross-checked across `.md`, `.html`, `.yaml`, `.yml`, `.txt` files. This repo is clean on the org-wide @grok auto-link issue.
- **Schema/version drift:** No `spec_version` keys, no `manifest.json`, no `action.yml`, no `.well-known/`, no `grok-install.yaml` in this repo — it's a code monorepo, not a spec repo. **However:** package `version` is uniformly `0.1.0` across all 6 `package.json` files (good), but Node engine drifts between `>=20` (root, tool 19) and `>=18` (shared/grok-client, shared/x-api-client). Grok model drifts between `grok-2-latest` (canonical) and `grok-4` (SPECs for tools 13 and 19). Tool count drifts between `12` (one line of README) and `20` (everywhere else, plus CHANGELOG, ROADMAP, tokens.md, assert-tool-status.mjs).
- **Documentation freshness:** **Bad.** The most recent commit (`87ce5d3`) is titled "Revise tool count from 20 to 12 in README" but only updated one line of README; CHANGELOG, ROADMAP, tokens.md, the assert script, and the rest of README are all stale. Eight tool folders were deleted in commits `a4637ff` through `9a42137` without corresponding doc updates. The repo is mid-rev shipped to `main`.
- **Brand/visual consistency:** Doc-side is **strong** — every markdown file ends with the exact same footer (`Part of the [grok-install family]... Apache 2.0.`), per-tool README scaffolding (tagline → status badges → What/Why/Tech/Install/License) is uniform across all 12, and badge color tokens are consistent. Code-side is **mid** — each live tool re-inlines its own copy of design tokens and the inlines have already drifted (tool 05 dropped half the `--space-*` and `--gradient-*` system).
- **Dead code / orphan files:** `assets/banner.svg` and `assets/icon.svg` (unreferenced); `shared/ui-kit/shell.html` (empty template, never used); `tools/12-controversy-detector/index.html:551` `DEFAULT_KEYWORDS` (declared, never read); `tools/04-pre-post-virality-scorer/index.html:486-500` `scoreFormat` multi-line branch (unreachable); `shared/ui-kit/tokens.css:54-62` (`--space-1/12/16` unused).
- **Test coverage:** `shared/grok-client` has substantive tests (chat 4 cases, stream 3 cases including SSE split-frame, tool-use 2 cases). `shared/x-api-client` covers headers, error path, missing-token throw, per-endpoint URLs, and pagination including URL-encoded cursors. `shared/test-utils` exercised indirectly. Tool 19 has a smoke test that only verifies the constructor and that `main()` is awaitable. **Zero tests for any of the four LIVE tools (04, 05, 07, 12).** Their inline JS — scoring math, regex builders, controversy meter logic, compound calculator — is entirely untested. No DOM/jsdom runner. No coverage in CI.
- **Security posture:** Generally good for the size. No `eval`, no `new Function`, no string-form `setTimeout`, no `document.write`, no `outerHTML`, no `insertAdjacentHTML`. User text is escaped via `escapeHtml`/`esc` helpers in the two tools that need it. `.env.example` files are placeholders only. Browser builds explicitly refuse to read `process.env` and document the rationale. **Concrete gaps:** Chart.js CDN load with no SRI (tool 07), Google Fonts external load on every page, two known-vulnerable transitive deps flagged by `npm audit` (basic-ftp high, ip-address moderate), no CSP meta in any tool, no version pin on third-party CDN scripts.

---

## 4. What's Working Well

- **Real shared-package tests, not snapshot theater.** `shared/grok-client/test/stream.test.js:30` deliberately tests SSE split-frame parsing — the kind of edge case most projects skip. `shared/x-api-client/test/pagination.test.js:35` verifies URL-encoding of cursor tokens, defending against a real X API quirk.
- **Browser/Node split with explicit security guards.** Both API clients ship separate `src/index.js` (CJS, env-aware) and `browser.mjs` (ESM, throws if you try to read `process.env`) entry points, with comment headers calling out "do not embed bearers in untrusted browser contexts." Adult engineering choice.
- **Doc template consistency across 22+ markdown files.** Identical footer line, identical per-tool scaffolding, consistent badge color tokens, consistent voice. Looks like a product, not a hack project.
- **`scripts/assert-tool-status.mjs` is a clever hygiene tool.** Cross-checks README claims against folder reality. Concept is exactly right; it's currently broken only because the cleanup didn't update it (which is the *point* — it caught the drift).
- **License is the full canonical Apache 2.0 text** with copyright owner filled in (per commit `4a4d0df`), not a stub or placeholder.

---

## 5. Top 5 Improvements (Ranked by Impact ÷ Effort)

| # | Improvement | Impact (1-10) | Effort (hours) | Why it matters |
|---|---|---|---|---|
| 1 | Finish the 12-vs-20 cleanup across README, CHANGELOG, ROADMAP, docs/tokens.md, and `scripts/assert-tool-status.mjs`. Delete row 01 and the broken row 02 link from README. Update Mermaid diagram, badges, anchors, big-number block. | 9 | 2 | Unblocks CI (currently failing on `assert-categorization`), removes the headline credibility hit ("their own README contradicts itself"), makes the repo shippable to a wider audience. |
| 2 | Replace `localStorage.clear()` with targeted `localStorage.removeItem(STORAGE_KEY)` in tools 05 and 12, and reconcile the 0-impressions/0-follows guards in tool 05. | 7 | 0.5 | Silent data-destruction bug for any user running multiple tools on the same origin (e.g., a hosted demo). Plus a UX correctness fix that costs minutes. |
| 3 | Promote design tokens to a single shared CSS file and have each live tool consume it (build step or inline-include script). Eliminate the four divergent inlined `:root` blocks. | 7 | 4 | Token drift is already happening (tool 05 dropped half the system). Without this, every new tool ships its own snowflake of tokens and the design system silently rots. |
| 4 | `npm audit fix`; pin Chart.js to a specific version with `integrity` (SRI); add a minimal CSP meta tag to live tool HTMLs; switch Google Fonts to self-hosted or `font-display: swap` with subsetted woff2. | 6 | 1.5 | Closes two known CVEs flagged by audit, removes the supply-chain attack surface from CDN scripts, removes third-party network calls from "production" tools. |
| 5 | Convert 2-3 SPECs to LIVE tools (e.g., 03 contextual-reply-suggester, 11 ghostwriter-mode-with-memory, 13 thread-to-newsletter-converter). Add at least one inline-JS unit test per LIVE tool using the existing Node test runner with jsdom. | 9 | 16-24 | The "20 tools" narrative is inflated; 4 LIVE is the actual selling point. Moving to 6-7 LIVE shifts the repo from "promising scaffold with broken numbers" to "actual showcase of working tools" — which is the unique value vs the rest of the grok-install family. |

---

## 6. Quick Wins (≤30 min each)

- **`README.md:19,24,33,55,106` → replace "20" with "12"** (and update Mermaid diagram counts at `README.md:144-145` from "6 LIVE / 14 Spec'd" to "4 LIVE / 8 Spec'd"). Also update typing-SVG URL `lines=` parameter at line 19.
- **Delete `README.md:110` (empty row)** and **`README.md:111` (broken link to `tools/02-follower-intent-classifier/`)**. Renumber the remaining table rows or drop the leading column.
- **Update `CHANGELOG.md:13-17`** — remove tools 09 and 18 from the "6 LIVE tools shipped" list (or change count to 4).
- **Update `scripts/assert-tool-status.mjs:20-41`** — prune `TOOL_STATUS` map to the 12 actually-present tools so `assert-categorization` job goes green.
- **Update `docs/ROADMAP.md:13-32`** and **`docs/tokens.md:101-122`** — remove rows for tools 01, 02, 08, 09, 10, 14, 15, 18.
- **Run `npm audit fix`** at repo root to close `basic-ftp` (high) and `ip-address` (moderate) vulnerabilities.
- **`tools/05-pinned-post-ab-rotator/index.html:327`** — replace `localStorage.clear();` with `localStorage.removeItem('xpt-pinned-rotator-v1');`.
- **`tools/12-controversy-detector/index.html:834`** — replace `localStorage.clear();` with `localStorage.removeItem('xpt-controversy-detector-v1');` (verify exact key from line ~545).
- **`shared/grok-client/package.json:18`** and **`shared/x-api-client/package.json:18`** — change `"node": ">=18"` to `"node": ">=20"` to match root and `README.md:165`.
- **`tools/13-thread-to-newsletter-converter/SPEC.md:25`** and **`tools/19-grok-thread-composer/SPEC.md:24`** — change `grok-4` to `grok-2-latest` to match the rest of the repo.
- **`.github/workflows/validate.yml:35`** — change `tools/*/index.html` to `tools/**/index.html` so html-validate covers tool 19.
- **`README.md:113,114,119,121` and `README.md:84` Categories block** — reconcile categories with `tools/04/README.md:3` (Analytics), `tools/05/README.md:3` (Analytics), `tools/12/README.md:3` (AI Writing), `tools/13/README.md:3` (Automation). Pick one source of truth.
- **`CODE_OF_CONDUCT.md:21` vs `SECURITY.md:7`** — pick one canonical email domain (recommend `agentmindcloud.dev` since it appears in Markdown badges and is more likely the dev-facing domain).
- **`shared/ui-kit/shell.html`** — either populate the empty `<style>` block with shared styles or delete the file.
- **`assets/banner.svg`, `assets/icon.svg`** — either reference from `README.md` (replacing the `capsule-render.vercel.app` external URL) or delete.
- **`tools/04-pre-post-virality-scorer/index.html:486-500`** — delete the unreachable `for` loop and `if (lines.length > 1)` branch in `scoreFormat`. The single `return 15;` line covers all multi-line cases.
- **`tools/12-controversy-detector/index.html:551`** — delete the unused `DEFAULT_KEYWORDS = {}` constant.

---

## 7. Ecosystem Potential Statement

This repo is the proof-of-life for the entire `grok-install` family — while sibling repos define specs, CLIs, marketplaces, and orchestration, `x-platform-toolkit` is the only one shipping actual end-user-facing tools that prove the ecosystem produces real things. The single-file HTML demo pattern (each LIVE tool is a 600-1000 line self-contained `index.html` with inlined CSS+JS) is genuinely differentiated against the broader "AI for X" repo space, where most projects are services or libraries rather than instantly-runnable artifacts. **Maturity: alpha, mid-rev** — the repo is in an unfinished cleanup (commit `87ce5d3` deleted 8 tool folders but updated only one line of README, leaving CHANGELOG, ROADMAP, tokens.md, and the CI assert-script all advertising tools that no longer exist; CI is currently broken on every push). Realistic 6-month potential with discipline: 200-600 stars on a clean launch (tweet from @JanSol0s + a Show HN with the compound calculator and controversy detector demoed live), strong portfolio signal for AgentMindCloud as "the org that ships, not just specs," and a credible revenue path via hosted SaaS versions of the top 2-3 tools (compound calculator and virality scorer have the clearest willingness-to-pay surface). **The single biggest unlock:** finish the 12-vs-20 cleanup so the repo presents truthfully, then convert 2-3 SPECs to LIVE so the "tools you can use today" count crosses 6 — that turns this from "broken showcase of an unbuilt vision" into "small but real toolkit you can pin to your bookmarks bar." **Resource verdict: invest a focused 10-20 hours on the cleanup + ship-2-more-LIVE arc, then re-evaluate.** The bones (real tests, browser/Node split with security thinking, doc template consistency) are good enough that another disciplined sprint converts this into the ecosystem's flagship demo; without that sprint, the README's own credibility undercuts everything else in the org.

`POTENTIAL_TAG: DOUBLE_DOWN — flagship live-demo proof-of-life for grok-install ecosystem; needs cleanup completion plus 2-3 more LIVE tools`
