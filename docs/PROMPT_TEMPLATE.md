# PROMPT_TEMPLATE.md

The exact shape every Claude Code prompt this skill generates must follow. Stick to this structure rigidly so prompts are predictable and trackable.

## The 7 sections

```markdown
# [P{N}] {Short title in imperative — verb first}

> Phase: {1-5} · Estimated time: {15min / 30min / 60min / 2h} · Depends on: {P{X}, P{Y} or "none"}

## 1. Context

You are working on `AgentMindCloud/grok-agent` — the official Grok Agent Platform repo. Stack: Windows 11 + PowerShell + Python 3.12 + Streamlit + grok-agent.yaml v2.15.

Already built (from HANDOFF_LOG.md):
- {Bullet list of relevant prior prompts and what they produced — only the relevant ones, not the full history}

Working directory: `grok-agent/`

## 2. Goal

{One sentence describing the single deliverable. Concrete and verifiable.}

## 3. Constraints (hard — non-negotiable)

- Apache 2.0 license header at top of every code file
- "Built for xAI, X, Grok and the ecosystem community" line in every README/markdown
- Windows 11 + PowerShell only — no bash, no macOS, no Apple anything
- grok-agent.yaml v2.15 backwards compatible with v2.14
- {Disclaimer rule if finance/tax — else omit}
- Local-first + privacy-first
- No partial code — full files only
- {Any prompt-specific constraint, e.g. "use Pydantic for schema validation"}

## 4. Files to create/modify

- `path/to/primary-file.ext` — {one-line purpose}
- `path/to/secondary-file.ext` — {one-line purpose}

## 5. Reference material

{If the project plan MD already contains pre-written content for this:}
Use the artifact in section "{section name}" of `Grok_Agent_Platform___Full_Sequential_Project_Plan.md` (around lines {X}–{Y}) as the starting point. Adjust per the constraints above.

{Else:}
{Link or describe the spec / inspiration / API docs to consult.}

## 6. Acceptance criteria

- [ ] {Testable bullet 1 — usually "file exists at correct path with correct content"}
- [ ] {Testable bullet 2 — usually a behavioral check, e.g. "running `.\\cli\\grok-agent.ps1 validate templates/finance/foo` returns OK"}
- [ ] {Testable bullet 3}
- [ ] All files include Apache 2.0 header
- [ ] Commit message follows `phase-{N}: <verb> <what>` format

## 7. Output

1. Full content of every file listed above (no ellipses, no "rest unchanged" — full files)
2. PowerShell commands to commit:
   ```powershell
   git add . ; git commit -m "phase-{N}: {verb} {what}"
   ```
3. Append this row to `HANDOFF_LOG.md`:
   ```
   | P{N} | Phase {N} | {short title} | {files touched, comma-sep} | {key decisions in 1 line} | ✅ done |
   ```
4. Reply to me with a 3-line summary: what you built + any decisions made + any blockers. Nothing more.
```

## Worked example (Prompt P1)

```markdown
# [P1] Initialize repo with CLAUDE.md, LICENSE, .gitignore

> Phase: 1 · Estimated time: 15min · Depends on: none

## 1. Context

You are starting `AgentMindCloud/grok-agent` from scratch. Stack: Windows 11 + PowerShell + Python 3.12 + Streamlit + grok-agent.yaml v2.15.

Already built: nothing — this is the first commit.

Working directory: `grok-agent/` (will be created).

## 2. Goal

Bootstrap the repository with the three files that govern every subsequent prompt: `CLAUDE.md` (instruction file), `LICENSE` (Apache 2.0), and `.gitignore`.

## 3. Constraints (hard)

- Apache 2.0 license — full text of Apache 2.0 in `LICENSE`
- "Built for xAI, X, Grok and the ecosystem community" line in CLAUDE.md
- Windows 11 + PowerShell only
- No partial code — full files only
- CLAUDE.md must enumerate the official file tree (see PROJECT_DNA)

## 4. Files to create/modify

- `CLAUDE.md` — permanent instruction file for any AI working on this repo
- `LICENSE` — full Apache 2.0 license text
- `.gitignore` — Python + Windows + Streamlit + secrets

## 5. Reference material

Use the CLAUDE.md and .gitignore content from section "1. CLAUDE.md (Updated, Push-Ready)" and "4. .gitignore" of `Grok_Agent_Platform___Full_Sequential_Project_Plan.md` as starting points. The Apache 2.0 LICENSE is the standard text from https://www.apache.org/licenses/LICENSE-2.0.txt.

## 6. Acceptance criteria

- [ ] `CLAUDE.md` exists and includes the official file tree
- [ ] `LICENSE` contains complete Apache 2.0 text (no truncation)
- [ ] `.gitignore` covers Python, Windows, Streamlit, secrets, IDEs
- [ ] All files committed
- [ ] Commit message: `phase-1: bootstrap repo with CLAUDE.md, LICENSE, .gitignore`

## 7. Output

1. Full content of `CLAUDE.md`, `LICENSE`, `.gitignore`
2. PowerShell commands:
   ```powershell
   git init ; git add . ; git commit -m "phase-1: bootstrap repo with CLAUDE.md, LICENSE, .gitignore"
   ```
3. Append to `HANDOFF_LOG.md`:
   ```
   | P1 | Phase 1 | Bootstrap repo | CLAUDE.md, LICENSE, .gitignore | Apache 2.0 confirmed; instruction file is ground truth | ✅ done |
   ```
4. Reply with 3-line summary.
```

## Bad prompt examples (do NOT generate these)

❌ "Build the CLI" — too broad, multiple files, multiple deliverables
❌ "Add tests" — no specific file, no acceptance criteria
❌ "Set up the repo and start the schema" — two deliverables in one
❌ "Make it look good" — not testable
❌ Anything missing section 7 (handoff log line) — breaks state tracking
