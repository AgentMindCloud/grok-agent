---
name: grok-agent-conventions
description: Use this skill whenever creating, editing, or reviewing ANY file in the AgentMindCloud/grok-agent repository — including manifests, Python code, PowerShell scripts, markdown docs, READMEs, configs, or templates. Triggers on any work in `grok-agent/`, `templates/finance/`, `templates/creator/`, `templates/x-native/`, `templates/general/`, `templates/super-agents/`, `cli/`, `safety/`, `spec/`, `docs/`, `scripts/`, or any file that needs Apache 2.0 license headers, "Built to help xAI and Grok win" positioning, PowerShell-first commands (not bash), finance disclaimers, or `phase-N: <verb> <what>` commit message format. Fires before file content is finalized to enforce conventions consistently.
---

# grok-agent-conventions

The convention enforcer for the entire grok-agent repo. Every file you create or modify must follow these rules. They override defaults that would otherwise leak in (bash commands, no license header, generic positioning).

## The Hard Six

1. **Apache 2.0 license header at the top of every code/config file.** Format depends on file type — see headers section below.
2. **"Built to help xAI and Grok win" line** in every README and user-facing markdown.
3. **Windows 11 + PowerShell only** in any shell command. Never bash, never macOS, never Apple anything.
4. **Every agent declares `grok-agent.yaml` v2.15** — backwards compat with v2.14 must hold.
5. **Strong disclaimers** on finance/tax/real-world-action tools: "Not financial advice", "Not tax advice", consent gates.
6. **Local-first + privacy-first**: user data on user's Windows machine by default. Cloud sync opt-in.

## License headers (use exact format per file type)

### Python (`.py`)
```python
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

### PowerShell (`.ps1`)
```powershell
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
```

### YAML (`.yaml`, `.yml`)
```yaml
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
```

### Markdown (`.md`)
```markdown
<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
```

### TOML (`.toml`)
```toml
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
```

### TypeScript / JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`)
```typescript
/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */
```

## "Help xAI win" positioning

Every README and user-facing markdown file includes a line like one of these (rotate naturally, don't copy verbatim every time):
- "Built to help xAI and Grok win the platform battle."
- "We're ecosystem allies — built to help xAI and Grok win."
- "Built to make Grok the obvious choice for every agent on X."

NEVER position grok-agent as competing with xAI. Always as ecosystem ally filling a gap (the distribution + runtime layer xAI hasn't shipped yet).

## PowerShell-first (the bash-leak problem)

When writing shell commands, examples, install instructions, or CI scripts:

| ❌ Wrong (bash defaults) | ✅ Right (PowerShell) |
|---|---|
| `mkdir -p foo/bar` | `New-Item -Path foo/bar -ItemType Directory -Force` |
| `cd foo && ls` | `cd foo ; Get-ChildItem` |
| `cmd1 && cmd2` | `cmd1 ; cmd2` (or `cmd1; if ($LASTEXITCODE -eq 0) { cmd2 }`) |
| `export VAR=x` | `$env:VAR = "x"` |
| `~/foo` | `$env:USERPROFILE\foo` or `~\foo` |
| `~/AppData` | `$env:LOCALAPPDATA` |
| `chmod +x file` | (PowerShell doesn't need this — skip) |
| `cat file` | `Get-Content file` |
| `rm -rf folder` | `Remove-Item folder -Recurse -Force` |

Exceptions where bash is OK:
- Inside `.github/workflows/*.yml` running on `ubuntu-latest` (CI runner choice)
- Comments referencing what bash users might know — but always provide the PowerShell equivalent

## Finance / tax disclaimers (mandatory wording)

Every UI page, README, and export of finance or tax tools includes:

```markdown
> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.
```

For tax-specific tools, ADD:

```markdown
> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.
```

For real-world-action agents (Cross-Reality Action Fabric, etc.):

```markdown
> ⚠️ **This agent can take real-world actions.** Every action requires explicit consent.
> Review the action plan before approving. The agent never acts autonomously.
```

## Commit message format

```
phase-{N}: <verb> <what>
```

Verbs (use one): `add`, `extend`, `fix`, `refactor`, `remove`, `update`, `bootstrap`, `ship`, `polish`, `test`.

Examples:
- `phase-1: bootstrap repo with governance + context files`
- `phase-1: add v2.15 unified manifest schema`
- `phase-2: ship X Money Companion Dashboard MVP`
- `phase-2: extend cashtag engine with portfolio simulator`
- `phase-4: add Living Narrative Fabric memory layer`

NEVER use:
- Past tense ("added X")
- Generic verbs ("update stuff", "misc changes")
- Phase tag missing
- Issue numbers as the entire message

## File naming conventions

- Folders: `kebab-case` (`x-money-companion-dashboard/`, `super-agents/`)
- Python files: `snake_case.py` (`api_clients.py`, `import_receipts.py`)
- PowerShell files: `kebab-case.ps1` (`grok-agent.ps1`, `launcher.ps1`)
- YAML files: `kebab-case.yaml` (`grok-agent.yaml`, `windows-extensions.yaml`)
- Markdown docs: `UPPER-KEBAB.md` for governance (`CLAUDE.md`, `HANDOFF_LOG.md`), `lower-kebab.md` for content (`windows-guide.md`)

## Path conventions (Windows-correct)

- App data: `$env:LOCALAPPDATA\grok-agent\` (NOT `~/.grok-agent/`)
- Configs: `$env:APPDATA\grok-agent\config\`
- Logs: `$env:LOCALAPPDATA\grok-agent\logs\`
- Cache: `$env:LOCALAPPDATA\grok-agent\cache\`
- User home in Python: `pathlib.Path.home() / "AppData" / "Local" / "grok-agent"`
- Avoid hardcoded `C:\` paths — use env vars.

## Untouchables (the 13 original repos)

These repos are reference-only. NEVER instruct modifications to:
- `grok-install`, `grok-install-cli`, `grok-install-action`, `grok-yaml-standards`, `vscode-grok-yaml`, `grok-agents-marketplace`, `awesome-grok-agents`, `grok-docs`, `x-platform-toolkit`, `grok-build-bridge`, `grok-agent-orchestra`, `universal-spawn` (+ any older ones)

If a file in `grok-agent/` needs functionality from one of these, COPY the relevant pattern, don't import from or modify the original.

## Pre-commit checklist (run mentally before finishing any file)

- [ ] Apache 2.0 header at top (correct format for file type)
- [ ] If user-facing: "help xAI win" line present
- [ ] If shell: PowerShell syntax (no bash leaks)
- [ ] If finance/tax: disclaimer banner
- [ ] If manifest: declares v2.15, validates against schema
- [ ] Paths are Windows-correct (`$env:LOCALAPPDATA`, not `~/.config`)
- [ ] No mention of macOS, Linux-only tools, or the 13 original repos as modifiable
- [ ] Commit message follows `phase-N: <verb> <what>`

If any box fails → fix before output.
