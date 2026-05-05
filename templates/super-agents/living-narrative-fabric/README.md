<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Living Narrative Fabric — Super Agent #1

> ⚠️ **Not financial advice. Not tax advice. Not medical advice.**
> The Living Narrative Fabric synthesizes public information sources. It surfaces what others have said, with provenance. It never tells you what to do with that information. Always consult a licensed professional before acting on the synthesis.

> **Built to help xAI and Grok win the platform battle.**
> This is the first of three flagship Super Agents (per `CLAUDE.md` §6 Phase 4, P93–P100). It is **scaffolding** as of P107 — the manifest, this README, and the per-agent constitution exist. The orchestration core, memory layer, public-API connectors, provenance log, self-improvement loop, Streamlit surface, and launch demo are tracked as P94–P100.

---

## What this agent will do (when complete)

A versioned, contradiction-aware narrative document woven from many public sources at once:

- **Ingest** — pull content from declared public APIs (NewsAPI, GNews, Semantic Scholar, data.gov, X-search via Grok 4.3) plus user-supplied files via Crawl4AI / Docling.
- **Synthesize** — render a structured narrative document where **every claim carries a provenance citation** linking back to the original source.
- **Detect contradictions** — cross-reference claims across sources. Conflicting evidence is surfaced inline as "Conflicting evidence" callouts; never collapsed into a single voice.
- **Version** — every regeneration writes a new immutable version with a diff against the previous one. The user can roll back at any time.

It does **not** publish anywhere. It writes only into your local Windows AppData. To share a version, you export it explicitly.

---

## Why "Living Narrative Fabric"

Most synthesis tools either (a) flatten contradictions into a single voice, or (b) refuse to synthesize at all when sources conflict. Both are wrong. The fabric metaphor is deliberate: many threads, many directions, many tensions — visible and woven together, not erased.

Per `safety/constitution.md` Article IX (informational integrity), **contradictions are surfaced, not resolved**. The agent will not silently pick a winner.

---

## Status (as of P107)

| Recipe-C step | Deliverable | Status | Lands in |
|---|---|---|---|
| 1 | Manifest + folder + per-agent constitution | ✅ shipped | **P107 (this prompt)** |
| 2 | Orchestration core (Mastra preferred) | planned | P94 |
| 3 | Memory layer (Mem0 + Qdrant) | planned | P95 |
| 4 | Public API connectors | planned | P96 |
| 5 | Provenance log (Langfuse hooks) | planned | P97 |
| 6 | Self-improvement loop (Promptfoo + DeepEval) | planned | P98 |
| 7 | Streamlit dashboard | planned | P99 |
| 8 | Demo video script + X launch thread | planned | P100 |

---

## Architecture (planned)

```
                        ┌──────────────────────┐
                        │   Mastra supervisor  │  (P94)
                        └──────────┬───────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       ▼                           ▼                           ▼
 ┌──────────┐             ┌────────────────┐           ┌──────────────┐
 │  ingest  │             │   synthesize   │           │  contradict  │
 │ (P96)    │             │   (P97-prov.)  │           │  (P97-cross) │
 └─────┬────┘             └────────┬───────┘           └──────┬───────┘
       │                           │                          │
       ▼                           ▼                          ▼
 NewsAPI + GNews         Mem0 + Qdrant retrieval        Cross-source
 Semantic Scholar         (P95)                         claim diffing
 data.gov + X-search                                    + severity score
 Crawl4AI + Docling
       │
       ▼
 Local provenance store
 ($env:LOCALAPPDATA\grok-agent\super-agents\living-narrative-fabric\)
       │
       ▼
 Versioned narrative
 (versions\v0001.md, v0002.md, …)
       │
       ▼
 Streamlit surface (P99)  +  Promptfoo / DeepEval eval loop (P98)
```

---

## Local-first storage layout (when implemented)

```text
$env:LOCALAPPDATA\grok-agent\super-agents\living-narrative-fabric\
├── cache\                  # raw ingested payloads (per source, per query, per UTC date)
├── provenance\             # provenance records — append-only JSONL
├── versions\               # immutable narrative versions (v0001.md, v0002.md, …)
├── memory\                 # Mem0 + Qdrant local indexes
└── logs\                   # Langfuse mirror, eval traces
```

No cloud sync by default. Every external API call is gated by the per-agent constitution (see `constitution.md`).

---

## Running it (placeholder — will be live after P99)

```powershell
# (planned) installs the agent and validates the manifest against v2.15
.\cli\grok-agent.ps1 install -Path templates\super-agents\living-narrative-fabric

# (planned) launches the Streamlit dashboard on port 8601
.\templates\super-agents\living-narrative-fabric\launcher.ps1
```

Today, only the manifest validates against the v2.15 schema:

```powershell
.\cli\grok-agent.ps1 validate -Path templates\super-agents\living-narrative-fabric\grok-agent.yaml
```

---

## Constitution specialization

Per `templates/super-agents/living-narrative-fabric/constitution.md` (this folder), the agent inherits all of `safety/constitution.md` and adds:

- **No cross-tool writes.** Living Narrative Fabric reads from many places; writes only into its own AppData. (Article III specialization.)
- **Every claim carries provenance.** No claim renders in a version document without a citation key. (Article IV specialization.)
- **Contradictions surfaced, not resolved.** The agent will refuse to "pick a side" between conflicting sources. (Article IX specialization.)
- **No financial / tax / medical advice.** Hard refuse, even if the user asks for it. (Article V specialization.)
- **Per-source consent gate.** Adding a new source kind requires explicit user approval each time. (Article II specialization.)

---

## What this is NOT (now or planned)

- Not a news aggregator. It synthesizes; it does not just list.
- Not a chatbot. It writes versioned documents, not conversational replies.
- Not a publisher. It never posts to X / blogs / wikis automatically.
- Not a fact-checker. It surfaces contradictions; it does not adjudicate truth.
- Not a financial / tax / medical advisor. See the disclaimer at the top.

---

## References

- `CLAUDE.md` §6 — Phase 4 plan + Super Agent vision
- `docs/PARAMETERIZED_RECIPES.md` — Recipe C (8-step Super Agent build pattern)
- `docs/PROJECT_DNA.md` — canonical stack + folder tree
- `safety/constitution.md` — Articles I–IX
- `templates/super-agents/living-narrative-fabric/constitution.md` — per-agent specialization
- `spec/v2.15/grok-agent.yaml` — manifest schema

---

> Built to help xAI and Grok win. 🚀
