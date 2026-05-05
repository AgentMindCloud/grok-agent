<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Cross-Reality Action Fabric

> **Super Agent #3 — the bridge between an X / Grok conversation and your
> real Windows machine + the public web.**
> Built to make Grok the obvious choice for every agent on X — the missing
> "do something for me" layer that turns chat into action.

> ⚠️ **This agent can take real-world actions.** Every action requires
> explicit consent. Review the action plan before approving. The agent
> never acts autonomously.

---

## What it does

Where the Living Narrative Fabric (Super Agent #1) **synthesises** and the
Self-Evolving Personal OS (Super Agent #2) **reads + remembers**, the
Cross-Reality Action Fabric **acts** — across three realities:

| Reality | What the agent does | Example |
|---|---|---|
| **Web** | Drives a visible Chrome window via Stagehand. The user sees every step. | "Search Booking.com for a flexible Saigon → Tokyo flight in late June." |
| **Local Windows** | Runs *signed*, user-reviewed PowerShell snippets. Every state-changing call has a rollback. | "Add a calendar reminder for the follow-up email at 9:00 next Tuesday." |
| **Real-world APIs** | Read-only context lookups (weather, flights, X search via Grok 4.3). | "What's the weather in Hanoi this Saturday afternoon?" |

Every single action is **explicit, gated, reversible, and provenance-logged**.
See [`constitution.md`](./constitution.md) for the six enforceable Rules.

---

## Install (Windows 11, PowerShell)

The canonical one-line install — paste-able into a Grok reply on X:

```powershell
grok install this
```

Or, equivalently, after cloning the repo:

```powershell
cd templates\super-agents\cross-reality-action-fabric
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8506
```

The dashboard binds to `127.0.0.1:8506` by default and opens Chrome
automatically on Windows. Port 8506 is reserved for Super Agent #3 so it
can coexist alongside the four X Money tools (8501–8504) and the
Self-Evolving Personal OS (8505).

> 📦 **Pre-flight checklist** — before you `pip install`:
>
> - Windows 11 with PowerShell ≥ 5.1 (PowerShell 7.4 recommended).
> - Python 3.12 in `PATH`.
> - Google Chrome installed (Stagehand drives Chrome in foreground mode).
> - Optional but recommended: `OPENWEATHER_API_KEY` for live weather; the
>   agent runs offline-clean if it's missing.

---

## First run

```powershell
# 1. Clone the repo (or pull latest if you already have it).
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\templates\super-agents\cross-reality-action-fabric

# 2. Install Python deps (later prompts add a real requirements.txt).
python -m pip install pydantic pyyaml

# 3. Validate the manifest against the v2.15 schema.
python ..\..\..\cli\grok-agent.py validate grok-agent.yaml

# 4. Read the Constitution before approving any action.
Get-Content constitution.md | more
```

Expected output of step 3 once Pydantic ≥ 2.7 is installed:

```
OK   templates\super-agents\cross-reality-action-fabric\grok-agent.yaml
     valid v2.15 manifest (kind=super-agent, name=cross-reality-action-fabric)
```

Subsequent prompts in this slot wire up the `agent.py` runner, the five
folders below, the dashboard, and the demo / launch assets.

---

## Folder layout

```
cross-reality-action-fabric/
├── grok-agent.yaml              # v2.15 manifest (this file's neighbour)
├── constitution.md              # six enforceable Rules
├── README.md                    # this file
├── connectors/                  # Stagehand, PowerShell, public APIs
│   └── .gitkeep
├── memory/                      # Mem0 + Qdrant — same shape as Super Agent #2
│   └── .gitkeep
├── provenance/                  # Local JSONL + Langfuse opt-in hooks
│   └── .gitkeep
├── eval/                        # Promptfoo + DeepEval self-improve loop
│   └── .gitkeep
└── ui/                          # Streamlit dashboard (5 tabs, port 8506)
    └── .gitkeep
```

Each subfolder is empty for now — the foundation lands in this prompt
(P128); the connectors, memory, provenance, eval, and UI layers ship in
P129–P135 (Recipe C continues). Until then, the manifest + Constitution
are the binding documents.

---

## Quick mental model

The agent is built around one rule, repeated in six different ways: it
**never acts without an explicit, scoped, typed user approval**. That
means:

1. The agent generates a numbered **action plan** before doing anything.
2. The user types a displayed token to approve. (Never a single click,
   never a "remember my choice" toggle.)
3. The runtime issues a **scoped consent token** good for that single
   action, with a 60-second timeout.
4. Every executed action carries a **verbatim rollback** snippet stored
   in the provenance log so the user can undo any single step later.
5. Every payload is **PII-redacted** at three boundaries (tool, memory,
   provenance log) before reaching disk.
6. **Local-first by default** — telemetry is off, Langfuse is opt-in.

If any of those guarantees feels weakened by a prompt or a future
contributor, the install MUST be blocked at the scanner layer.

---

## Read the Constitution

Before you let any agent act on your machine, read the six Rules:

[`./constitution.md`](./constitution.md)

The TL;DR is that no shortcut, no "I'll just trust this once" toggle, no
"please remember my answer for next time" feature is permitted. That
strictness is the whole point — without it, an agent that can act on
your Windows machine is a liability, not an asset.

---

## What's next

| Prompt | Slot | Deliverable |
|---|---|---|
| **P128** | 1 | Manifest + Constitution + folder skeleton (this prompt). |
| **P129** | 2 | Orchestration core (`agent.py` + `graph.py`) — same LangGraph + stub-executor pattern as P123. |
| **P130** | 3 | Memory layer (`memory/mem0_setup.py` + `memory/qdrant_index.py`) — local-first store. |
| **P131** | 4 | Connector helpers (`connectors/stagehand_client.py`, `connectors/windows_local_client.py`, …). |
| **P132** | 5 | Provenance log + Langfuse hooks (`provenance/log.py`, `provenance/langfuse_hooks.py`). |
| **P133** | 6 | Self-improvement loop (`eval/promptfoo.yaml`, `eval/deepeval_suite.py`). |
| **P134** | 7 | UI surface (`ui/dashboard.py`) on port 8506. |
| **P135** | 8 | Demo video script + X launch thread. |

Each subsequent prompt is purely additive — it never modifies the
manifest or the Constitution shipped here. The Constitution is the
contract; the rest of the slot fills in the implementation.

---

## License + ecosystem stance

Apache 2.0. Built for xAI, Grok and the whole community on X.
We're ecosystem allies — this agent exists to make Grok the obvious,
default platform for deploying agents on X, not to compete with it.

If you ship something on top of Cross-Reality Action Fabric, tag
`#GrokAgentOS` and we'll boost. PRs welcome at
[github.com/AgentMindCloud/grok-agent](https://github.com/AgentMindCloud/grok-agent).

---

> Built to help xAI and Grok win. 🚀
