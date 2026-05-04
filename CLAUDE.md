<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# CLAUDE.md — Permanent Instruction File for Grok Agent OS

> **Built to help xAI and Grok win the platform battle.**
> We are ecosystem allies to xAI. Everything we build exists to make Grok the obvious, default choice for every agent on X.

This file is the ground truth for any AI assistant (Claude, Grok, Cursor, etc.) working on `AgentMindCloud/grok-agent`. Read it first. Re-read it before generating any prompt or file. The rules here override every default behavior.

---

## 1. What we are building

**Grok Agent OS** — the missing OS layer for Grok agents on X.

**Core idea:** one YAML manifest (`grok-agent.yaml` v2.15) → one command (`grok install this` or `grok-agent install`) → instant, safe, Windows-native deployment with full provenance, public API power, and mind-blowing capabilities.

**Repo:** `github.com/AgentMindCloud/grok-agent`
**Org:** `AgentMindCloud` (creator: `@JanSol0s`)
**Codename:** Grok Agent OS
**License:** Apache 2.0 (everywhere, no exceptions)
**Manifest version:** `grok-agent.yaml` v2.15 (100% backwards compat with v2.14)

## 2. The Hard Six (non-negotiable rules)

1. **Apache 2.0 license header at the top of every code/config file.** Format depends on file type — see `.claude/skills/grok-agent-conventions/SKILL.md` for the canonical headers.
2. **"Built to help xAI and Grok win" line** in every README and user-facing markdown. Rotate phrasing; never copy verbatim.
3. **Windows 11 + PowerShell only** in every shell command, install instruction, and CI script. Never bash, never macOS, never Apple anything. Exception: bash inside `.github/workflows/*.yml` running on `ubuntu-latest` is OK (CI runner choice).
4. **Every agent declares `grok-agent.yaml` v2.15** — backwards compat with v2.14 must hold.
5. **Strong disclaimers** on finance/tax/real-world-action tools: "Not financial advice", "Not tax advice", explicit consent gates.
6. **Local-first + privacy-first.** User data lives on the user's Windows machine by default. Cloud sync is opt-in.

If any of the Hard Six fails → fix before output.

## 3. Stack (default — only deviate if explicitly required)

| Layer | Choice |
|---|---|
| OS target | Windows 11 + Google Chrome ONLY |
| Shell | PowerShell (no bash, no zsh) |
| Language (apps) | Python 3.12 |
| App framework | Streamlit (for X Money tools) |
| Data | SQLite (local-first) |
| Schema | YAML (Pydantic for validation) |
| Orchestration (super agents) | Mastra OR LangGraph |
| Memory | Mem0 + Qdrant |
| Web automation | Stagehand |
| Tracing/eval | Langfuse + Promptfoo + DeepEval |
| Web scraping | Crawl4AI |
| Doc parsing | Docling |
| LLM | Grok 4.3 (via xAI API) |
| Marketplace (Phase 5) | Next.js on Vercel |
| Execution env | GitHub Codespaces or Actions (no local Python builds required) |

## 4. Canonical file tree

Every prompt must reference and respect this tree. Folders may be created lazily when a phase reaches them, but layout never changes.

```
grok-agent/
├── .github/
│   └── workflows/
│       └── validate.yml
├── cli/
│   ├── grok-agent.ps1            # primary CLI: install/new/validate/list/run
│   └── grok-agent.py             # fallback
├── docs/
│   ├── index.md
│   ├── windows-guide.md
│   ├── for-xai-adoption.md
│   ├── CONSTRAINTS.md
│   ├── PARAMETERIZED_RECIPES.md
│   ├── PROJECT_DNA.md
│   ├── PROMPT_TEMPLATE.md
│   ├── SOURCES.md
│   └── live-validator/
├── safety/
│   ├── scanner.py
│   └── constitution.md
├── scripts/
│   └── generate-template.py      # autonomous builder (Phase 4)
├── spec/
│   ├── v2.14/                    # reference only
│   └── v2.15/
│       ├── grok-agent.yaml
│       ├── changelog.md
│       └── windows-extensions.yaml
├── templates/
│   ├── finance/
│   │   ├── x-money-companion-dashboard/
│   │   ├── x-smart-cashtag-alpha-engine/
│   │   ├── x-creator-payout-optimizer/
│   │   └── x-money-vision-analyzer/
│   ├── creator/                  # 20+ templates (Phase 3)
│   ├── x-native/
│   ├── general/
│   └── super-agents/
│       ├── living-narrative-fabric/
│       ├── self-evolving-personal-os/
│       └── cross-reality-action-fabric/
├── .gitignore
├── CLAUDE.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── HANDOFF_LOG.md
├── LICENSE                       # Apache 2.0
├── pyproject.toml
├── README.md
├── ROADMAP.md
└── SECURITY.md
```

## 5. The 5-phase roadmap (~126 prompts total)

We execute one numbered prompt at a time. The orchestrator (Grok) generates each prompt using `docs/PROMPT_TEMPLATE.md`. Claude Code executes it fully, commits with the correct format, appends a row to `HANDOFF_LOG.md`, and replies with a 3-line summary.

### Phase 1 — Core Platform Foundation (P1–P18) — Days 1–14

Goal: single source-of-truth repo with v2.15 standard, Windows CLI, safety system, starter templates.

- **P1** Bootstrap repo with `CLAUDE.md`, `LICENSE`, `.gitignore`
- **P2** Create full canonical directory structure
- **P3** Write permanent `CLAUDE.md` instruction file (this file — refined in P3)
- **P4** Create `spec/v2.15/grok-agent.yaml` (unified manifest schema)
- **P5** Create `cli/grok-agent.ps1` (PowerShell CLI: install/new/validate/list/run)
- **P6** Create `cli/grok-agent.py` (fallback)
- **P7** Create `safety/scanner.py` + `safety/constitution.md`
- **P8** Create `.github/workflows/validate.yml`
- **P9** Create `docs/index.md` + `docs/windows-guide.md`
- **P10** Create `docs/for-xai-adoption.md`
- **P11** Create `pyproject.toml` + root metadata
- **P12** Create 8 starter templates (2 finance skeleton, 2 creator, 2 x-native, 2 general) — manifests only
- **P13** Premium root `README.md` (with Super Agents vision)
- **P14** `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- **P15** `ROADMAP.md` (full phase summary)
- **P16** `.streamlit/config.toml` + Streamlit Cloud-ready files
- **P17** End-to-end smoke test in GitHub Codespaces (`grok-agent new` → `validate` → `run`)
- **P18** First X launch thread + repo public announcement

### Phase 2 — X Money Tools Suite (P19–P42) — 24 prompts (Recipe A: 6 prompts per tool)

Highest-priority phase. Solves real creator pain from the X Money launch. Each tool follows the same 6-prompt recipe.

- **P19–P24** `x-money-companion-dashboard` (manifest + Streamlit skeleton + Grok prompts + data layer + launcher + smoke test)
- **P25–P30** `x-smart-cashtag-alpha-engine`
- **P31–P36** `x-creator-payout-optimizer`
- **P37–P42** `x-money-vision-analyzer` (must one-click import into Tool #1 SQLite)

Every tool ships with: "Not financial advice" banner on every tab + export, Windows AppData Local SQLite path (`$env:LOCALAPPDATA\grok-agent\`), "Built to help xAI and Grok win" footer.

### Phase 3 — Creator Distribution Flywheel (P43–P92) — 50 prompts

Goal: 20+ creator templates + outreach program for organic traction.

**Program setup (P43–P47):** outreach landing page copy, 5 DM templates, tracking sheet, install flow, thin landing page, first 10 outreach messages.

**20 creator templates (P48–P87)** — Recipe B (2 prompts per template), built easiest-first:

content-idea-generator, reply-drafter, analytics-summarizer, monetization-optimizer, thread-builder, mention-summarizer, dm-triager, trend-aligned-poster, quote-tweet-suggestor, follower-quality-analyzer, niche-influencer-finder, cross-platform-reposter, content-calendar-builder, ab-test-suggester, comment-engagement-booster, hashtag-strategy-advisor, growth-experiment-runner, competitor-watch, content-recycler, brand-voice-trainer.

**Program launch (P88–P92):** public X launch, outreach tracker, testimonial system, v1.5 improvements, completion report.

### Phase 4 — Super Agents + Self-Improvement (P93–P124) — 32 prompts

Goal: 7 mind-blowing Super Agents + autonomous improvement loop. Recipe C (8 prompts per Super Agent for the first 3).

- **P93–P100** Super Agent #1 — `living-narrative-fabric`
- **P101–P108** Super Agent #2 — `self-evolving-personal-os`
- **P109–P116** Super Agent #3 — `cross-reality-action-fabric`

Each uses 8 prompts: manifest + folder + constitution → orchestration core (Mastra) → memory layer (Mem0 + Qdrant) → public API connectors → provenance log + Langfuse hooks → self-improvement loop (Promptfoo + DeepEval) → Streamlit UI dashboard → demo video script + X launch thread.

**Lighter Super Agents (P117–P120)** — 1-prompt manifests reusing patterns:
- P117 Agent Swarm with Shared Memory
- P118 Provenance-First Trust Engine
- P119 Narrative Contradiction Detector
- P120 Zero-Config "I Want To…" Agent

**Self-improvement infra (P121–P124):**
- P121 `scripts/generate-template.py` (autonomous builder)
- P122 Weekly Promptfoo + DeepEval + Langfuse loop in CLI
- P123 Update `CLAUDE.md` with new priorities
- P124 Phase 4 completion + 3 Super Agent demo videos

### Phase 5 — Marketplace, Scale & xAI Partnership (P125–P126+, ongoing)

- **P125** Thin Next.js marketplace on Vercel listing all v2.15 agents
- **P126** "Deploy to X" one-click + xAI partnership pitch deck (60-sec video + RFC)

Ongoing after P126: weekly curation posts, contributor program, Creator Program v2 (paid tier + 20% revenue share), continuous self-improvement loop.

## 6. The execution protocol

1. Grok generates the next numbered prompt using `docs/PROMPT_TEMPLATE.md` (the 7-section structure).
2. The user pastes it into Claude Code.
3. Claude Code executes the prompt fully, creates all files with Apache 2.0 headers, commits with `phase-N: <verb> <what>` format.
4. Claude Code appends one row to `HANDOFF_LOG.md` matching the prompt's "Output" section.
5. Claude Code replies with exactly 3 lines: what was built + key decisions + any blockers.
6. The user reports back to Grok with the 3-line summary + any issues.
7. We move to the next prompt in order.

No deviations. We stay strictly sequential. Every prompt is self-contained but references prior state via `HANDOFF_LOG.md`.

## 7. Commit message format

```
phase-{N}: <verb> <what>
```

Verbs (use one): `add`, `extend`, `fix`, `refactor`, `remove`, `update`, `bootstrap`, `ship`, `polish`, `test`.

Examples:
- `phase-1: bootstrap repo with CLAUDE.md, LICENSE, .gitignore`
- `phase-1: add v2.15 unified manifest schema`
- `phase-2: ship X Money Companion Dashboard MVP`
- `phase-4: add Living Narrative Fabric memory layer`

Never use past tense, generic verbs, or commits missing the phase tag.

## 8. File naming conventions

- Folders: `kebab-case` (`x-money-companion-dashboard/`, `super-agents/`)
- Python files: `snake_case.py` (`api_clients.py`, `import_receipts.py`)
- PowerShell files: `kebab-case.ps1` (`grok-agent.ps1`, `launcher.ps1`)
- YAML files: `kebab-case.yaml` (`grok-agent.yaml`, `windows-extensions.yaml`)
- Markdown docs: `UPPER-KEBAB.md` for governance (`CLAUDE.md`, `HANDOFF_LOG.md`), `lower-kebab.md` for content (`windows-guide.md`)

## 9. Path conventions (Windows-correct)

- App data: `$env:LOCALAPPDATA\grok-agent\` (NOT `~/.grok-agent/`)
- Configs: `$env:APPDATA\grok-agent\config\`
- Logs: `$env:LOCALAPPDATA\grok-agent\logs\`
- Cache: `$env:LOCALAPPDATA\grok-agent\cache\`
- User home in Python: `pathlib.Path.home() / "AppData" / "Local" / "grok-agent"`
- Avoid hardcoded `C:\` paths — use env vars.

## 10. PowerShell-first cheat sheet

| ❌ Wrong (bash) | ✅ Right (PowerShell) |
|---|---|
| `mkdir -p foo/bar` | `New-Item -Path foo/bar -ItemType Directory -Force` |
| `cd foo && ls` | `cd foo ; Get-ChildItem` |
| `cmd1 && cmd2` | `cmd1 ; cmd2` |
| `export VAR=x` | `$env:VAR = "x"` |
| `~/AppData` | `$env:LOCALAPPDATA` |
| `cat file` | `Get-Content file` |
| `rm -rf folder` | `Remove-Item folder -Recurse -Force` |

## 11. Mandatory disclaimers

**Finance / investment tools** — every UI page, README, and export:

```markdown
> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.
```

**Tax tools** — also include:

```markdown
> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.
```

**Real-world-action agents** (Cross-Reality Action Fabric, etc.):

```markdown
> ⚠️ **This agent can take real-world actions.** Every action requires explicit consent.
> Review the action plan before approving. The agent never acts autonomously.
```

## 12. Untouchables — the 13 original repos

These are reference-only. NEVER instruct modifications to:
`grok-install`, `grok-install-cli`, `grok-install-action`, `grok-yaml-standards`, `vscode-grok-yaml`, `grok-agents-marketplace`, `awesome-grok-agents`, `grok-docs`, `x-platform-toolkit`, `grok-build-bridge`, `grok-agent-orchestra`, `universal-spawn` (+ any older ones).

If a file in `grok-agent/` needs functionality from one of these, COPY the relevant pattern, don't import from or modify the original.

## 13. Success vision (end of 2026)

- 50k+ monthly invocations
- 5k+ GitHub stars
- Recognized as the default way to ship Grok agents on X
- At least one public xAI engineer engagement
- First paid users via Creator Program v2

## 14. Pre-output checklist (run mentally before finishing any file)

- [ ] Apache 2.0 header at top (correct format for file type)
- [ ] If user-facing: "help xAI win" line present
- [ ] If shell: PowerShell syntax (no bash leaks)
- [ ] If finance/tax: disclaimer banner
- [ ] If manifest: declares v2.15, validates against schema
- [ ] Paths are Windows-correct (`$env:LOCALAPPDATA`, not `~/.config`)
- [ ] No mention of macOS, Linux-only tools, or the 13 original repos as modifiable
- [ ] Commit message follows `phase-N: <verb> <what>`
- [ ] HANDOFF_LOG row appended exactly as specified by the prompt

If any box fails → fix before output.

---

> Built to help xAI and Grok win. 🚀
