<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Contributing to Grok Agent OS

> **Built for xAI, X, Grok and the ecosystem community. ❤️**
> If you're here, you're an ecosystem ally. Welcome — your work makes Grok the obvious place to ship agents on X.

This file is the short guide. The ground-truth instruction set for everyone (humans and AIs) working on this repo is [`CLAUDE.md`](CLAUDE.md). Read that before opening a PR.

---

## 1. The Hard Six (non-negotiable)

Every contribution must satisfy all six. The CI scanner blocks anything that doesn't.

1. **Apache 2.0 license header** at the top of every code/config file. Format depends on file type — see `.claude/skills/grok-agent-conventions/SKILL.md`.
2. **"Built for xAI, X, Grok and the ecosystem community"** line in every README and user-facing markdown. Rotate phrasing; no two files use the exact same sentence.
3. **Windows 11 + PowerShell only** in every shell command, install instruction, and end-user example. Bash is allowed only inside `.github/workflows/*.yml` running on `ubuntu-latest`.
4. **Every agent declares `grok-agent.yaml` v2.15** (or v2.14 — backwards compat is mandatory).
5. **Strong disclaimers** on every finance, tax, or real-world-action tool. Exact wording lives in [`safety/constitution.md`](safety/constitution.md) Article V.
6. **Local-first + privacy-first.** User data lives under `$env:LOCALAPPDATA\grok-agent\`. Cloud sync is opt-in.

---

## 2. Before you start

1. **Read [`CLAUDE.md`](CLAUDE.md)** — the full vision, the 5-phase ~126-prompt plan, and the precedence rules when guidance conflicts.
2. **Read [`safety/constitution.md`](safety/constitution.md)** — the rule book every shipped agent inherits.
3. **Skim [`spec/v2.15/grok-agent.yaml`](spec/v2.15/grok-agent.yaml)** — the schema and three reference examples.
4. **Skim [`docs/PROMPT_TEMPLATE.md`](docs/PROMPT_TEMPLATE.md)** — the 7-section structure every prompt and PR description follows.
5. **Set up Windows tooling** — see [`docs/windows-guide.md`](docs/windows-guide.md) sections 1–4.

---

## 3. The development loop

```powershell
# Clone + branch
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent
git checkout -b your-feature

# Install dev deps
python -m pip install --user --upgrade pip
python -m pip install --user '.[dev]'

# Validate every manifest you touch
.\cli\grok-agent.ps1 validate path\to\grok-agent.yaml

# Run the Constitution scanner before pushing
python safety\scanner.py scan-all .
```

If both pass locally, CI on push will too.

---

## 4. Commit message format

```
phase-{N}: <verb> <what>
```

- **Verbs:** `add`, `extend`, `fix`, `refactor`, `remove`, `update`, `bootstrap`, `ship`, `polish`, `test`.
- **Tense:** present-tense, imperative.
- **Phase tag:** required (`phase-1`, `phase-2`, `phase-3`, `phase-4`, `phase-5`); pick the phase the work belongs to.

Examples:
- `phase-2: ship X Money Companion Dashboard MVP`
- `phase-3: add reply-drafter creator template`
- `phase-4: extend Living Narrative Fabric with contradiction detector`
- `phase-1: fix scanner false positive on PII-redacted-cloud kinds`

Bad examples (rejected on review):
- `update stuff` (no phase tag, vague verb)
- `Added the dashboard` (past tense)
- `phase-2: WIP` (not a deliverable)

---

## 5. The HANDOFF_LOG protocol

If your contribution corresponds to a numbered prompt from the master plan, append one row to [`HANDOFF_LOG.md`](HANDOFF_LOG.md) in the format documented at the top of that file. AI assistants working from `CLAUDE.md` do this automatically; humans should do it manually.

```
| P{N} | Phase {N} | {short title} | {files touched} | {key decisions in 1 line} | ✅ done |
```

For freeform contributions outside the numbered plan, no log entry is required — just a clear PR description.

---

## 6. How to add a new template

Use the right recipe in [`docs/PARAMETERIZED_RECIPES.md`](docs/PARAMETERIZED_RECIPES.md):

| Recipe | Used for | Prompts per unit |
|---|---|---|
| **A** — X Money tool | `templates/finance/<slug>/` | 6 |
| **B** — Creator template | `templates/creator/<slug>/` | 2 |
| **C** — Super Agent | `templates/super-agents/<slug>/` | 8 |

Every template ships with:
- `grok-agent.yaml` declaring `version: "2.15"`
- `README.md` with the matching disclaimer banner from Constitution Article V
- `prompts/system.md` (Grok system prompt)
- A launcher (`launcher.ps1` or `app.py`)

The CI scanner blocks any template missing the required disclaimers for its `kind:`.

---

## 7. Pull request checklist

- [ ] All new/changed files have an Apache 2.0 header.
- [ ] User-facing markdown has a "Built for xAI, X, Grok and the ecosystem community" line.
- [ ] Shell snippets are PowerShell (no bash leaks outside `.github/workflows/`).
- [ ] Every touched manifest declares `version: "2.15"` (or "2.14") and validates with `cli/grok-agent.ps1 validate`.
- [ ] If the change touches finance/tax/real-world-action behavior, the relevant Constitution Article V disclaimer is present.
- [ ] CI is green (schema + Constitution scanner).
- [ ] PR description follows the 7-section prompt-template shape (Context / Goal / Constraints / Files / Reference / Acceptance / Output).

---

## 8. What we won't merge

- Anti-xAI positioning — we're allies, not competitors.
- macOS- or Linux-only end-user instructions (CI workflows excepted).
- Manifests that disable the safety scanner or flip a Hard Refusal via configuration.
- Code that requires admin to install (`windows.requires_admin: true`).
- Telemetry, tracking, or cloud sync without an explicit consent gate.
- Anything that violates [`safety/constitution.md`](safety/constitution.md).

---

## 9. Reporting bugs and security issues

- **Functional bugs** — open a [GitHub issue](https://github.com/AgentMindCloud/grok-agent/issues).
- **Security issues** — see [`SECURITY.md`](SECURITY.md). Do **not** disclose publicly first.
- **Constitution violations** spotted in shipped agents — open an issue tagged `constitution`.

---

## 10. License

All contributions are licensed Apache 2.0. By submitting a PR you agree the work is yours to license, or you have authority to license it on behalf of its owner.

> Built for xAI, X, Grok and the ecosystem community. ❤️
