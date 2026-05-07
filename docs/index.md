<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS

> **Built for xAI, X, Grok and the ecosystem community. ❤️**
> the official open standard + Windows-first distribution layer that makes Grok the easiest, most powerful, and most magical platform for deploying agents.

`AgentMindCloud/grok-agent` is the missing OS layer for Grok agents. One YAML manifest (`grok-agent.yaml` v2.15) plus one command (`grok install this` or `.\cli\grok-agent.ps1 install`) gets a Grok-powered agent installed safely on Windows 11 with full provenance, public-API power, and the disclaimers required by the Agent Constitution.

We are ecosystem allies to xAI. Everything in this repo exists to make Grok the obvious, default platform — never to compete with it.

---

## Why this exists

Grok 4.3 is the best agent LLM on X. The thing missing is a **distribution layer** — a place agents can be authored, validated, installed, and run with safety baked in. That gap has slowed adoption. We close it.

What you get with Grok Agent OS:

- **One open standard** — `grok-agent.yaml` v2.15 (100% backwards compatible with v2.14)
- **A Windows-first CLI** — `cli/grok-agent.ps1` (PowerShell, zero admin)
- **A Pydantic validator** — `cli/grok-agent.py` (deep schema checking)
- **A safety scanner** — `safety/scanner.py` enforcing the Agent Constitution
- **An Agent Constitution** — `safety/constitution.md` (consent gates, hard refusals, mandatory disclaimers)
- **A CI workflow** — `.github/workflows/validate.yml` that blocks non-compliant manifests
- **Templates** — finance dashboards, creator tools, x-native agents, super agents (rolling out)

Every piece runs on **Windows 11 + Google Chrome only**. No macOS instructions. No Linux-only commands. PowerShell-first throughout.

---

## Quick start (60 seconds on Windows)

Open PowerShell and run:

```powershell
# Clone
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent

# Install Python deps once
python -m pip install --user 'pydantic>=2.7,<3' 'pyyaml>=6.0'

# Show CLI help
.\cli\grok-agent.ps1 help

# Scaffold a new agent in the current folder
.\cli\grok-agent.ps1 new my-first-agent

# Validate any manifest against v2.15
.\cli\grok-agent.ps1 validate spec\v2.15\grok-agent.yaml

# Install + run an agent (after you've authored or downloaded one)
.\cli\grok-agent.ps1 install path\to\agent-folder
.\cli\grok-agent.ps1 run my-first-agent
```

For the full Windows walkthrough including PowerShell execution policy, AppData paths, troubleshooting, and the "grok install this" paste flow, see [windows-guide.md](windows-guide.md).

---

## The "grok install this" primitive

When a user posts a manifest on X with the phrase **"grok install this"**, anyone can paste the YAML into:

```powershell
.\cli\grok-agent.ps1 install -FromStdin
# paste the YAML, then Ctrl-Z then Enter
```

The CLI validates against v2.15, runs the Constitution scanner, and on success copies the agent into `$env:LOCALAPPDATA\grok-agent\agents\<name>\`. No admin required. No surprises.

---

## What lives where

| Path | What |
|---|---|
| `cli/grok-agent.ps1` | Primary Windows CLI (install / new / validate / list / run) |
| `cli/grok-agent.py` | Pydantic v2 deep validator (called from the PS CLI) |
| `safety/scanner.py` | Agent Constitution enforcer (33 named checks) |
| `safety/constitution.md` | The Agent Constitution v1.0 |
| `spec/v2.15/grok-agent.yaml` | official schema (v2.15 unified) |
| `spec/v2.14/` | Reference-only snapshot of the prior schema |
| `templates/finance/` | X Money tools (dashboard, alpha engine, payout optimizer, vision analyzer) |
| `templates/creator/` | 20+ creator templates (Phase 3) |
| `templates/super-agents/` | Living Narrative Fabric, Self-Evolving Personal OS, Cross-Reality Action Fabric (Phase 4) |
| `.github/workflows/validate.yml` | CI: schema + Constitution scan on every PR |
| `CLAUDE.md` | Ground-truth instruction file for any AI working on this repo |
| `HANDOFF_LOG.md` | State tracker — which prompts have completed |

For the full official tree see [`PROJECT_DNA.md`](PROJECT_DNA.md).

---

## The roadmap (~126 prompts across 5 phases)

| Phase | Range | Goal | Status |
|---|---|---|---|
| 1 | P1–P18 | Core platform foundation | complete |
| 2 | P19–P42 | X Money tools suite (4 tools × 6 prompts) | complete |
| 3 | P43–P92 | Creator distribution flywheel (20 templates) | complete |
| 4 | P93–P124 | 7 Super Agents + self-improvement loop | complete |
| 5 | P125+ | Marketplace + xAI partnership | active |

Each prompt is self-contained, atomic, and adds one row to `HANDOFF_LOG.md`. The full sequence is documented in [`CLAUDE.md`](../CLAUDE.md).

---

## Safety in one paragraph

Every manifest is validated twice on every push and PR: once for **structure** (`cli/grok-agent.py`) and once for **Constitution compliance** (`safety/scanner.py`). Finance and tax tools must show "Not financial advice" / "Not tax advice" disclaimers. Real-world-action agents must declare consent gates. Super Agents must enable provenance. Local-first storage and no-admin install are non-negotiable. Read the full Agent Constitution at [`safety/constitution.md`](../safety/constitution.md).

---

## Get involved

- **Read the Constitution** — [`safety/constitution.md`](../safety/constitution.md)
- **Browse the schema** — [`spec/v2.15/grok-agent.yaml`](../spec/v2.15/grok-agent.yaml)
- **For xAI engineers** — [`for-xai-adoption.md`](for-xai-adoption.md) (a short pitch for adopting v2.15 as a community-maintained standard)
- **License** — Apache 2.0 (see [`LICENSE`](../LICENSE))
- **Author** — [@JanSol0s](https://x.com/JanSol0s)

Built for xAI, X, Grok and the ecosystem community.

> Built for xAI, X, Grok and the ecosystem community. ❤️
