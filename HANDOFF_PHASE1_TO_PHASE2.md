# CLAUDE.md — Chat Handoff (Phase 1 → Phase 2)

> **Built for xAI, X, Grok and the ecosystem community. ❤️**
> This file is the bridge between this Claude Code chat (which executed all of Phase 1, P1–P18) and the next fresh Claude Code chat (which will execute Phase 2, starting with P19 — `x-money-companion-dashboard` manifest + folder + README).
>
> The next session does **not** need to read this entire chat history. It needs to read this file + the four "critical reads" listed in §11.

---

## 1. Quick orientation

| Field | Value |
|---|---|
| Repo | `github.com/AgentMindCloud/grok-agent` |
| Org | `AgentMindCloud` (creator: `@JanSol0s`) |
| Active branch | `claude/grok-agent-os-blueprint-Fpsr8` |
| Last commit before handoff | `104e2bb` — `phase-18: first X launch thread + Phase 1 complete` |
| Working directory in container | `/home/user/grok-agent` |
| Phase status | **Phase 1 OFFICIALLY CLOSED on 2026-05-04.** 18 prompts → 18 deliverables shipped. |
| Next prompt | **P19** — `x-money-companion-dashboard` manifest + folder + README (slot 1 of Recipe A) |

---

## 2. What was built in this chat (Phase 1, P1–P18)

| # | Title | Key files | One-line decision |
|---|---|---|---|
| P1 | Bootstrap repo with CLAUDE.md, LICENSE, .gitignore | `CLAUDE.md`, `LICENSE`, `.gitignore` | LICENSE was already full Apache 2.0; .gitignore already had Grok-specific section |
| P2 | Create canonical directory structure | `.github/`, `cli/`, `docs/live-validator/`, `safety/`, `scripts/`, `spec/v2.{14,15}/`, `templates/{finance,creator,x-native,general,super-agents}/` | 12 empty placeholders + 7 `.gitkeep` + 1 note (spec/v2.14/README.md); `scripts/` included per PROJECT_DNA.md even though prompt §4 omitted it |
| P3 | Permanent CLAUDE.md instruction file | `CLAUDE.md` (full rewrite, 15 sections) | Established explicit precedence rule (CLAUDE.md > matching skill > CONSTRAINTS/PROJECT_DNA > active prompt) |
| P4 | v2.15 unified manifest schema | `spec/v2.15/grok-agent.yaml` (596 lines) | "Schema-by-example" YAML reference doc with inline `# REQUIRED · type · default` annotations + 3 commented canonical examples + v2.14 backwards-compat appendix |
| P5 | Windows PowerShell CLI | `cli/grok-agent.ps1` (~750 lines) | 6 commands (help/new/install/validate/list/run); two-tier validation (PS surface check + Python deep delegate); 3 install paths (file/folder, `-Yaml`, `-FromStdin`) |
| P6 | Python Pydantic v2 deep validator | `cli/grok-agent.py` (633 lines) | Mirrors every v2.15 section; `extra="forbid"` so typos surface; cross-field validators for tools/posts-consent/super-agent constitution+provenance/vision-analyzer; sysexit codes 0/65/66/69/70 |
| P7 | Safety scanner + Constitution v1.0 | `safety/scanner.py` (489 lines), `safety/constitution.md` (332 lines) | 15 named checks (I.1–VII), Constitution articles map 1:1 to scanner findings, scanner exits 1 only on errors (warns non-blocking) |
| P8 | GitHub Actions CI workflow | `.github/workflows/validate.yml` (122 lines) | Runs both schema + Constitution scan in two loops; accumulates FAIL across all manifests so contributors see every problem in one CI run; bash on `ubuntu-latest` is the documented exception to PowerShell-only |
| P9 | Core docs (overview + Windows guide) | `docs/index.md` (113 lines), `docs/windows-guide.md` (354 lines) | Windows-only with zero macOS/Linux references; troubleshooting maps each error to a Constitution article when applicable |
| P10 | xAI adoption pitch | `docs/for-xai-adoption.md` (628 words) | TL;DR + gap + what-we-built table + 5 differentiators + 3-tier asks (read/signal/conversation); "footnote = win" framing keeps ally posture honest |
| P11 | pyproject.toml + governance docs | `pyproject.toml`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md` | setuptools backend with empty `packages` (tooling repo, not library); merged the originally-planned P14 governance docs into this prompt |
| P12 | 8 starter template manifests | 8× `templates/{kind}/{slug}/grok-agent.yaml` | All 8 pass schema + Constitution scanner with **zero findings**; X Money tools have V.1+V.2 disclaimers up-front; tool-name regex `^[a-z][a-z0-9_]*$` (snake_case), agent-name regex `^[a-z][a-z0-9-]*$` (kebab-case) |
| P13 | Premium root README | `README.md` (234 lines) | Capsule-render banner + typing-svg + 6 shields.io badges + Mermaid install-flow diagram + 7 Super Agents section + 5-phase roadmap |
| P14 | First end-to-end smoke test (Python layer) | `docs/smoke-test-results.md` (run #1), `docs/x-launch-thread.md` (initial 7-tweet draft) | Ran via Python validators (pwsh not yet installed at this point); 7 remaining Windows-only checks documented |
| P15 | ROADMAP.md | `ROADMAP.md` (366 lines) | Phase-by-phase tables + ASCII Gantt showing Phase 2/3 overlap (days 35–56) + "How phases are independent" framing |
| P16 | Streamlit defaults + secrets example | `.streamlit/config.toml`, `.streamlit/secrets.toml.example` | Cinnabar/parchment palette matching the README banner; `gatherUsageStats=false` per Constitution Article VII; secrets.toml.example tracked, secrets.toml correctly gitignored |
| P17 | End-to-end smoke test (real PowerShell) | `docs/smoke-test-results.md` (run #2) + 3 bug fixes in `cli/grok-agent.ps1` | **Installed PowerShell 7.4.6 on the runner** then exercised every command via real `pwsh`; 3 real defects surfaced and were fixed (see §6 below) |
| P18 | First X launch thread + Phase 1 close | `docs/x-launch-thread.md` (refreshed) | 7-tweet thread + 1 standalone single-tweet announcement + 4 quote-tweet variants (incl. new "what's the catch" skeptic variant); all 12 posts verified ≤280 chars by Python script |

**Total commits on the branch in this session:** 18 commits, all named `phase-N: <verb> <what>` per format. Latest hash: `104e2bb`.

---

## 3. The Hard Six (non-negotiable, restated for the next session)

1. **Apache 2.0 license header** at the top of every code/config file (format depends on file type — Python `# Copyright 2026 AgentMindCloud / Licensed under Apache 2.0...`, YAML/TOML `#`, Markdown `<!-- ... -->`, PowerShell `#`).
2. **"Built for xAI, X, Grok and the ecosystem community"** in every README and user-facing markdown. **Rotate phrasing**; never copy a single sentence verbatim across files.
3. **Windows 11 + PowerShell only** in every shell command, install instruction, README example, launcher script. The one exception: bash inside `.github/workflows/*.yml` running on `ubuntu-latest`.
4. **Every agent declares `grok-agent.yaml` v2.15** (or v2.14 — backwards compat must hold).
5. **Strong disclaimers** on finance/tax/real-world-action tools — exact wording in `safety/constitution.md` Article V.
6. **Local-first + privacy-first.** User data lives at `$env:LOCALAPPDATA\grok-agent\` by default. Cloud sync, telemetry, external API calls beyond what the manifest declares — opt-in only.

If any of these fails the pre-output checklist → fix before submitting.

---

## 4. v2.15 schema (the heart of the project)

Required top-level fields (all 6):

```yaml
version: "2.15"      # accepts "2.14" too
kind: "agent"        # one of: agent | finance-dashboard | alpha-engine |
                     #         creator-payout-optimizer | vision-analyzer |
                     #         super-agent | x-native | creator-template
name: "my-agent"     # kebab-case, must match folder name
description: "..."   # min_length 10
author: "@JanSol0s"
license: "Apache-2.0"
```

Optional sections (declare only what you need): `metadata`, `install`, `windows`, `grok`, `tools`, `public_apis`, `multi_agent`, `real_time_x`, `memory`, `provenance`, `constitution`, `safety` (with `cost_limits` + `human_in_the_loop` + `disclaimers` sub-sections), `dependencies`, `evaluation`.

Cross-field validators baked into the Pydantic model (`cli/grok-agent.py`):
- `tools[].type=='public_api'` requires `tools[].api`
- `tools[].type=='local_function'` requires `tools[].module` + `tools[].function`
- `tools[].type=='mcp_server'` requires `tools[].server`
- `windows.requires_admin: true` is rejected (Hard Six)
- `real_time_x.posts: true` requires `real_time_x.consent_required: true`
- `kind: super-agent` requires a `constitution:` section
- `kind: vision-analyzer` requires `grok.vision: true` (when grok declared)

`schema:` field on `tools[].parameters` is aliased to Python attribute `json_schema` to avoid Pydantic's BaseModel.schema() shadow warning.

---

## 5. Agent Constitution v1.0 + 15 scanner checks

| Check ID | Article | Severity | What it enforces |
|---|---|---|---|
| `I.1-license` | I.1 | error | `license == "Apache-2.0"` |
| `I.2-xai-positioning` | I.2 | error | description / metadata.tagline must not contain anti-xAI positioning ("compete with xai", "alternative to grok", etc.) |
| `I.3-windows-requires-admin` | I.3 | error | `windows.requires_admin == false` |
| `I.4-version` | I.4 | error+info | `version` ∈ {2.14, 2.15}; v2.14 emits info nudge to upgrade |
| `II.posts-consent` | II | error | `real_time_x.posts=true` requires `consent_required=true` |
| `II.publish-gate` | II | error | `real_time_x.posts=true` requires `publish_to_x` in `constitution.consent_gates` |
| `III.no-forbidden-actions-flipped` | III | error | An action listed in `safety.forbidden_actions` cannot also appear in `constitution.consent_gates` |
| `IV.super-agent-provenance` | IV | error | `kind: super-agent` requires `provenance.enabled: true` |
| `IV.super-agent-constitution` | IV | error | `kind: super-agent` requires a `constitution:` section with at least 1 rule |
| `V.1-finance-disclaimer` | V.1 | error | finance kinds must have `safety.disclaimers.not_financial_advice: true` |
| `V.2-tax-disclaimer` | V.2 | warn | finance-dashboard / creator-payout-optimizer should set `not_tax_advice: true` |
| `V.3-real-world-action-disclaimer` | V.3 | warn | agent declaring real-world consent gates should set `real_world_action_consent: true` |
| `VI.1-cost-limits-for-finance-and-super-agent` | VI.1 | warn | finance + super-agent kinds should declare `safety.cost_limits` |
| `VI.2-hitl-for-consent-gated-agents` | VI.2 | warn+error | Consent-gated agents need HITL configured (warn); HITL.enabled=false with consent_gates is error |
| `VII.pii-default` | VII | warn | finance/vision/super-agent kinds with `pii_handling="none"` is too permissive |

**Scanner exit semantics:** info/warn → exit 0 (non-blocking), error → exit 1 (blocks install + CI merge).

---

## 6. The 3 PowerShell defects surfaced + fixed in P17 (carry forward as learnings)

These caught real issues that Phase-1's Python-only smoke test couldn't have surfaced. The next session should be aware so any P19+ launcher scripts don't repeat them.

### Bug 1 — `Join-Path $env:LOCALAPPDATA` ran eagerly at script-load

**Symptom:** Script crashed before the dispatcher could route any command (even `help`) on any non-Windows pwsh, with `Cannot bind argument to parameter 'Path' because it is null`.

**Fix in `cli/grok-agent.ps1`:** 4-step fallback chain — try `LOCALAPPDATA` → `USERPROFILE\AppData\Local` → `HOME/.grok-agent` → `/tmp/grok-agent-fallback`. On real Windows nothing changes. On non-Windows the script loads.

### Bug 2 — `Format-Table -AutoSize` rendered nothing in non-TTY pwsh

**Symptom:** `list` showed `Installed agents (2):` then blank rows.

**Fix:** Replaced `Format-Table` with manual `-f` formatter — `'  {0,-32}  {1,-26}  {2,-7}  {3}' -f ...` — and an 80-char description truncation with `...` suffix.

### Bug 3 — `$input` capture under `[CmdletBinding()]` blocks on TTY

**Symptom:** Initial fix tried `$Script:PipelineInput = @($input)` at script top so Invoke-Install could see PS pipeline input; under `[CmdletBinding()]` this blocked when no pipeline was actually feeding the script.

**Fix:** Dropped the `$input` capture entirely. `-FromStdin` now reads `[Console]::In.ReadToEnd()` only, gated by `[Console]::IsInputRedirected` for the prompt hint. Documented Linux-pwsh quirk: `Get-Content x.yaml | & script.ps1 install -FromStdin` doesn't redirect to OS stdin on Linux pwsh; on Windows pwsh it works (matches the Hard Six platform target). For cross-platform pasting, recommend `install -Yaml @"…"@` (verified working).

---

## 7. Verified CLI command surface (after P17 fixes)

Ran via real `pwsh -File /home/user/grok-agent/cli/grok-agent.ps1 ...` on PowerShell 7.4.6:

| Command | Status | Notes |
|---|---|---|
| `help` | ✅ | Banner + 6 commands + 6 examples + paths + spec + xAI tagline |
| `validate <file>` | ✅ | Surface check + Python deep validation |
| `validate <folder>` | ✅ | Folder→`grok-agent.yaml` resolution |
| `new <name>` | ✅ | Scaffolds `grok-agent.yaml` + `README.md` in cwd |
| `install <path>` | ✅ | Surface + Python validation + folder copy to `~/.grok-agent/agents/` |
| `install -Yaml @"..."@` | ✅ | Inline-string install path |
| `install -FromStdin` (Windows pwsh) | ✅ (target) | Works on Windows pwsh per design |
| `install -FromStdin` (Linux pwsh PS pipeline) | ⚠️ | Documented quirk — non-target platform |
| `list` | ✅ | Manual `-f` table renders rows correctly |
| `run <name>` | ✅ | 4-fallback launcher chain (windows.launcher → launcher.ps1 → app.py → main.py/run.py) with friendly error |

---

## 8. CI state

Workflow at `.github/workflows/validate.yml` runs on every push + PR to `main` + `workflow_dispatch`:

1. Checkout
2. Setup Python 3.12 (with pip cache)
3. Install pinned deps (`pydantic>=2.7,<3` + `pyyaml>=6.0`)
4. Self-test (`python cli/grok-agent.py info` + `python safety/scanner.py info`)
5. **Discover** every `grok-agent.yaml` (find with .git/node_modules excluded)
6. **Schema validate** every manifest (loop accumulates FAIL across all)
7. **Constitution scan** every manifest (warns non-blocking, errors fail CI)
8. Fallback "no manifests" step

Both loops use GitHub Actions `::group::` / `::endgroup::` for collapsible per-manifest output and `::error file=path::` annotations for inline PR-diff failures.

Currently scans 9 manifests (1 spec + 8 starter templates) — all green.

---

## 9. Phase 2 — what P19 starts

**P19** is the first prompt of **Recipe A** (the X Money tool recipe), applied to the first of 4 tools.

### Recipe A (per X Money tool — 6 prompts)

| Slot | What | Files | Time |
|---|---|---|---|
| 1 | Manifest + folder + README | `templates/finance/<slug>/grok-agent.yaml`, `templates/finance/<slug>/README.md` | 20min |
| 2 | Streamlit app skeleton (6-tab) | `templates/finance/<slug>/app.py`, `templates/finance/<slug>/requirements.txt`, `templates/finance/<slug>/.streamlit/config.toml` | 45min |
| 3 | Grok prompts | `templates/finance/<slug>/prompts/system.md`, `templates/finance/<slug>/prompts/user_templates.md` | 30min |
| 4 | Data layer + APIs | `templates/finance/<slug>/data/store.py`, `templates/finance/<slug>/data/api_clients.py` | 60min |
| 5 | PowerShell launcher | `templates/finance/<slug>/launcher.ps1` | 20min |
| 6 | "grok install this" smoke test + disclaimers polish | manifest validation, README disclaimer audit, end-to-end test | 30min |

### The 4 X Money tools — build order

| Order | Slug | Kind | Prompts | Why this order |
|---|---|---|---|---|
| 1 | `x-money-companion-dashboard` | `finance-dashboard` | **P19–P24** | The anchor: every other tool's data lands in this tool's SQLite |
| 2 | `x-smart-cashtag-alpha-engine` | `alpha-engine` | P25–P30 | Reuses SQLite + Streamlit patterns from #1 |
| 3 | `x-money-vision-analyzer` | `vision-analyzer` | P37–P42 | Built before #4 because #4 depends on it via `data/import_receipts.py` (writes parsed receipts directly into Tool #1's SQLite) |
| 4 | `x-creator-payout-optimizer` | `creator-payout-optimizer` | P31–P36 | Pulls from #1 + #3 SQLite |

> **Note the build order** — Tool #4 (Vision Analyzer) writes directly into Tool #1 (Companion Dashboard) SQLite at `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\data.db`. Build #1 → #2 → #4 → #3 so Tool #3 sees a richer transaction set when it ships.

### What's already done that P19 builds on

- The starter manifest at `templates/finance/x-money-companion-dashboard/grok-agent.yaml` already exists from P12. **P19 expands it** (or polishes it if no expansion is needed) and adds a proper `README.md` with all 3 disclaimer banners (V.1 finance + V.2 tax) and the "Built for xAI, X, Grok and the ecosystem community" footer.
- The `.streamlit/config.toml` defaults at the repo root (P16) are inherited by every Streamlit tool — P20 (slot 2) only needs a per-tool `.streamlit/config.toml` if it deviates from defaults.
- The Constitution scanner already has the V.1 + V.2 + cost_limits + HITL checks ready — P19's manifest must satisfy them.

---

## 10. The execution protocol (unchanged from Phase 1)

1. **Grok generates the next numbered prompt** using `docs/PROMPT_TEMPLATE.md` (the 7-section structure: Context / Goal / Constraints / Files / Reference / Acceptance / Output).
2. **User pastes it into Claude Code.**
3. **Claude Code executes** the prompt fully, creates files with Apache 2.0 headers, commits with `phase-N: <verb> <what>` format on `claude/grok-agent-os-blueprint-Fpsr8`.
4. **Claude Code appends one row to `HANDOFF_LOG.md`** matching the prompt's "Output" section.
5. **Claude Code replies with exactly 3 lines:** what was built + key decisions + any blockers.
6. **User reports back to Grok** with the 3-line summary.
7. **Move to the next prompt.**

Commit message verbs (use one): `add` / `extend` / `fix` / `refactor` / `remove` / `update` / `bootstrap` / `ship` / `polish` / `test`.

---

## 11. Critical reads for the new session (in this order)

The next Claude Code instance should read these 4 files first, then await the P19 prompt from Grok:

1. `CLAUDE.md` (repo root) — the permanent ground-truth instruction file (15 sections including Hard Six, file tree, full ~126-prompt plan, commit format, mandatory disclaimers, pre-output checklist).
2. `HANDOFF_LOG.md` — the state-of-execution table; Phase 1 closure note at the bottom names the explicit Phase 2 build order.
3. `safety/constitution.md` — Constitution v1.0 (9 articles + per-kind specializations); P19's manifest must satisfy V.1 (finance disclaimer) and VI.1 (cost limits) at error/warn level.
4. `templates/finance/x-money-companion-dashboard/grok-agent.yaml` — the existing starter manifest from P12 that P19 will expand.

Optional but useful skills (auto-load on file work):
- `.claude/skills/grok-agent-conventions/SKILL.md` — universal enforcer (Apache headers, PowerShell, disclaimers)
- `.claude/skills/grok-yaml-v215/SKILL.md` — v2.15 schema reference
- `.claude/skills/x-money-tool-recipe/SKILL.md` — the 6-file pattern every X Money tool follows (loads automatically when working under `templates/finance/`)

---

## 12. Open Windows-only checks (deferred from P17, run before tagging v0.1.0)

These exercise the PowerShell-only surface that the Linux-runner P17 smoke test couldn't directly drive. Each is a 1-2 minute manual check on a Windows 11 box:

- [ ] `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` then `.\cli\grok-agent.ps1 help` shows the banner.
- [ ] `Get-Content paste.yaml | .\cli\grok-agent.ps1 install -FromStdin` accepts piped input on Windows pwsh (Linux pwsh quirk doesn't apply).
- [ ] CI green: open a PR on this branch → `.github/workflows/validate.yml` runs schema + Constitution scan and passes.
- [ ] `streamlit run app.py` for a Phase-2 X Money tool launches in Chrome on stock Windows 11.

---

## 13. Conventions reminders for P19+

- **Folder name = manifest `name` field** (kebab-case). For P19: folder is `templates/finance/x-money-companion-dashboard/`, manifest declares `name: "x-money-companion-dashboard"`.
- **Tool names** in `tools[]` use `^[a-z][a-z0-9_]*$` (snake_case). Agent `name` field uses `^[a-z][a-z0-9-]*$` (kebab-case).
- **AppData paths in PowerShell:** `$env:LOCALAPPDATA\grok-agent\<slug>\` — never `~/.grok-agent`, never `~/AppData`, always `$env:LOCALAPPDATA`.
- **AppData paths in Python:** `pathlib.Path.home() / "AppData" / "Local" / "grok-agent" / "<slug>"` for cross-platform safety, or just `Path(os.environ["LOCALAPPDATA"]) / "grok-agent" / "<slug>"` if Windows-only.
- **Disclaimer wording** is exact and lives in Constitution Article V — copy it verbatim, don't paraphrase.
- **UTF-8-no-BOM** when writing YAML/MD from PowerShell — use the `Write-Utf8NoBom` helper already in `cli/grok-agent.ps1` rather than `Set-Content -Encoding UTF8` (which writes a BOM on PS 5.1).

---

## 14. Suggested 3-line opener for the next session

When the new chat starts and receives the P19 prompt, a good opening response shape:

> Reading the 4 critical files (`CLAUDE.md`, `HANDOFF_LOG.md`, `safety/constitution.md`, `templates/finance/x-money-companion-dashboard/grok-agent.yaml`) to confirm Phase 1 state before executing P19.
>
> Plan: invoke the `grok-agent-conventions` and `x-money-tool-recipe` skills, expand the starter manifest from P12 with the full Recipe A slot 1 structure (manifest polish + README with V.1/V.2 disclaimers + repo-relative paths), validate with `python cli/grok-agent.py validate`, scan with `python safety/scanner.py scan`, commit `phase-2: ship X Money Companion Dashboard manifest + README`.

---

## 15. Final Phase-1 numbers (for the next session's first sanity check)

After running `cd /home/user/grok-agent && git log --oneline -20`, the new session should see:

```
104e2bb phase-18: first X launch thread + Phase 1 complete
da078f3 phase-17: end-to-end smoke test in GitHub Codespaces
6c23f98 phase-16: add .streamlit/config.toml defaults + Streamlit Cloud ready files
6a9ecc2 phase-15: create ROADMAP.md full phase-by-phase summary
104e2bb (or successor) is the head of `claude/grok-agent-os-blueprint-Fpsr8`.
```

`HANDOFF_LOG.md` should show 18 rows P1–P18, all `✅ done`, with the "Phase 1 — OFFICIALLY CLOSED on 2026-05-04" comment block immediately below the table.

`python safety/scanner.py scan-all templates/` should return 8 manifests scanned, **0 findings of any severity**.

`python cli/grok-agent.py validate spec/v2.15/grok-agent.yaml` should return `OK Valid v2.15 manifest: name='my-agent' kind='agent' version='2.15'`.

If any of those three checks differ, something has drifted between sessions and the new instance should investigate before executing P19.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
> Phase 1 closed. Phase 2 begins with P19. Ship it.
