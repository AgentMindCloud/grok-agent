<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Super Agent #2 — Self-Evolving Personal OS

> **Super Agent #2 — a personal second brain on Windows that learns,
> remembers, and quietly improves itself.**
> Morning briefings, long-term personal + X memory, auto-evolving workflows,
> full rewind, and explicit-consent gates on every real-world action.
> Built to help xAI and Grok win — the personal-OS layer xAI hasn't shipped
> yet.

> 🔒 **User data is sacred.** Every byte of personal data lives under
> `$env:LOCALAPPDATA\grok-agent\self-evolving-personal-os\`. PII is redacted
> at three boundaries (connector → memory → provenance log) before it ever
> touches disk. Cloud sync, telemetry, and Langfuse traces are opt-in only.

> ⚠️ **This agent can take real-world actions.** Every calendar edit, email
> send, X post, file write, or workflow change requires an explicit typed
> approval — the agent never acts autonomously.

---

## What it does

Where the Living Narrative Fabric (Super Agent #1) **synthesises** and the
Cross-Reality Action Fabric (Super Agent #3) **acts**, the Self-Evolving
Personal OS **reads + remembers + evolves** — every day, on the user's
Windows machine, with full provenance:

| Capability | What ships | Example |
|---|---|---|
| **Morning brief** | A 4-metric Briefing Trust Score with full provenance, dual-surface paradox detection, and ≥3 cross-template bridges. | "Give me my 9 AM brief — calendar, mentions, weather, and what changed since yesterday." |
| **Personal memory** | Mem0 (episodic) + Qdrant (semantic) over six personal sources, DPAPI-encrypted at rest, parent-version-id chain for rewind. | "What did I commit to last Tuesday in DMs?" — recall hits the local store, never the network. |
| **Workflow evolution** | Promptfoo + DeepEval weekly loop proposes prompt deltas; every change is human-review-gated before it lands. | After a week of briefings, the loop suggests a new "weekend mode" prompt and flags it for the user's approval. |
| **Rewind** | Every brief carries a `parent_version_id`; `rewind_briefing` walks the chain so the user can see what the brief looked like 3 days ago. | "Show me Tuesday's brief verbatim — including the contradictions surfaced that day." |

Six connectors feed the personal layer (`x_personal`, `gcal`, `gmail`,
`local_notes`, `weather`, `news_personal`). Eight consent gates govern
every action that touches the real world (`publish_briefing`,
`modify_calendar`, `send_email`, `post_to_x`, `send_dm`,
`modify_local_files_outside_appdata`, `apply_workflow_change`,
`export_personal_log`). See [`constitution.md`](./constitution.md) for
the ten enforceable Articles.

---

## Install (Windows 11, PowerShell)

The canonical one-line install — paste-able into a Grok reply on X:

```powershell
grok install this
```

Or, equivalently, after cloning the repo:

```powershell
cd templates\super-agents\self-evolving-personal-os
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8502
```

The dashboard binds to `127.0.0.1:8502` by default. Port 8502 is reserved
for Super Agent #2 so it can coexist alongside the Living Narrative Fabric
(8501) and the Cross-Reality Action Fabric (8506).

> 📦 **Pre-flight checklist** — before you `pip install`:
>
> - Windows 11 with PowerShell ≥ 5.1 (PowerShell 7.4 recommended).
> - Python 3.12 in `PATH`.
> - Google Chrome installed (used by the dashboard's preview tab).
> - Optional: `XAI_API_KEY` for live Grok 4.3 personalisation, plus the
>   per-source keys (`OPENWEATHER_API_KEY`, `NEWSAPI_KEY`, etc.) only if
>   you want live data; every connector has a stub fallback so the agent
>   runs offline-clean by default.

---

## First run

```powershell
# 1. Clone the repo (or pull latest if you already have it).
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\templates\super-agents\self-evolving-personal-os

# 2. Install Python deps.
python -m pip install -r requirements.txt

# 3. Validate the manifest against the v2.15 schema.
python ..\..\..\cli\grok-agent.py validate grok-agent.yaml

# 4. Read the Constitution before approving any action.
Get-Content constitution.md | more

# 5. Run the local smoke test (offline, no API keys required).
python smoke_test.py

# 6. Generate today's morning brief in stub mode (no network calls).
python agent.py morning-brief --stub
```

Expected output of step 3 once Pydantic ≥ 2.7 is installed:

```
OK   templates\super-agents\self-evolving-personal-os\grok-agent.yaml
     valid v2.15 manifest (kind=super-agent, name=self-evolving-personal-os)
```

---

## Folder layout

```
self-evolving-personal-os/
├── grok-agent.yaml              # v2.15 manifest
├── constitution.md              # ten enforceable Articles
├── agent.py                     # CLI entry point (morning-brief, recall, evolve, rewind)
├── orchestrator.py              # 6-node DAG with Mastra / LangGraph / in-process runtimes
├── graph.py                     # LangGraph fallback runtime (same DAG)
├── dashboard.py                 # Streamlit UI (port 8502)
├── requirements.txt             # pinned Python deps
├── smoke_test.py                # offline end-to-end smoke test
├── dashboard_smoke_test.py      # Streamlit-free dashboard helper checks
├── connectors/                  # 6 personal sources, all consent-gated + PII-redacted
│   ├── x_personal_client.py
│   ├── gcal_client.py
│   ├── gmail_client.py
│   ├── local_notes_client.py
│   ├── weather_news_client.py
│   └── smoke_test.py
├── memory/                      # Mem0 + Qdrant — local, encrypted, rewind-aware
│   ├── mem0_setup.py
│   ├── qdrant_index.py
│   └── smoke_test.py
├── provenance/                  # JSONL audit log + opt-in Langfuse hooks
│   ├── log.py
│   ├── langfuse_hooks.py
│   └── smoke_test.py
├── eval/                        # Promptfoo + DeepEval weekly self-improve loop
│   ├── promptfoo.yaml
│   ├── deepeval_suite.py
│   └── smoke_test.py
├── DEMO.md                      # 90-second offline demo script
└── X_LAUNCH_THREAD.md           # 10-tweet public launch thread
```

---

## Quick mental model

The agent is built around three intertwined guarantees, repeated in ten
different ways across the Constitution:

1. **User data is sacred.** PII is redacted at the connector boundary,
   redacted again at the memory boundary, and redacted a third time at
   the provenance boundary. Three passes, no exceptions.
2. **Memory is versioned + rewindable.** Every brief, every recall,
   every workflow change records a `parent_version_id`. The user can
   walk back any state to any prior point.
3. **Self-improvement is conservative.** The weekly Promptfoo + DeepEval
   loop produces *suggestions* — never auto-applied. The user approves
   or declines each prompt delta before it lands in `prompts/`.

If any of those guarantees feels weakened by a future contributor, the
install MUST be blocked at the scanner layer.

---

## Read the Constitution

Before you let any agent learn from your inbox, your calendar, or your
mentions, read the ten Articles:

[`./constitution.md`](./constitution.md)

The TL;DR is the same as the other two Super Agents: no shortcut, no
"trust this once" toggle, no "remember my answer for next time" feature.
That strictness is the whole point — without it, an agent that
remembers everything you do is a liability, not an asset.

---

## What's next

Self-Evolving Personal OS is built across an 8-slot Recipe-C pattern
(Slot 1 = manifest + Constitution; Slots 2–8 = orchestrator, memory,
connectors, provenance, eval, UI, demo). Every slot is shipped:

| Slot | Prompt | Status | What it ships |
|---:|:---|:---:|:---|
| 1 | P118 | ✅ | Manifest + folder + Constitution v1.0 |
| 2 | P119 | ✅ | Orchestrator + LangGraph fallback + in-process safety net |
| 3 | P120 | ✅ | Memory layer (Mem0 + Qdrant) — local, encrypted, rewindable |
| 4 | P121 | ✅ | Connector helpers (6 personal sources) |
| 5 | P124 | ✅ | Provenance log + Langfuse hooks (default OFF) |
| 6 | P125 | ✅ | Self-improvement loop (Promptfoo + DeepEval) |
| 7 | P126 | ✅ | UI surface — Streamlit dashboard on port 8502 |
| 8 | P127 | ✅ | Demo video script + X launch thread |

Each slot is purely additive — no slot modifies a prior slot's contract.
The Constitution and the manifest are binding; the rest of the slots
fill in the implementation.

---

## License + ecosystem stance

Apache 2.0. Built for xAI, Grok and the whole community on X. We're
ecosystem allies — Self-Evolving Personal OS exists to make Grok the
obvious, default platform for deploying personal-data agents on X, not
to compete with it.

If you ship something on top of Self-Evolving Personal OS, tag
`#GrokAgentOS` and we'll boost. PRs welcome at
[github.com/AgentMindCloud/grok-agent](https://github.com/AgentMindCloud/grok-agent).

---

> Built to help xAI and Grok win. 🚀
