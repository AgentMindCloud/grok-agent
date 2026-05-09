<!-- Apache 2.0 License -->
<!-- Copyright 2026 AgentMindCloud -->

> ⚠️ **This is a manifest-only template — no runnable code yet.**
> Use as a structural reference for building your own version of this pattern.
> The flagship agents (`living-narrative-fabric`, `self-evolving-personal-os`,
> `cross-reality-action-fabric`) ship complete, runnable implementations.

# Agent Swarm with Shared Memory

**Lighter Super Agent for Grok Agent OS**

A collaborative swarm of six specialized Grok agents (Researcher, Skeptic, Creator, Executor, Archivist, Orchestrator) that share long-term memory via Mem0 + Qdrant and engage in visible real-time debate to produce superior collective intelligence on complex tasks.

## Key Features

- Shared long-term memory across all swarm members
- Visible expert-style debate process in every response
- Mandatory inclusion of dissenting opinions for balanced output
- Memory evolves and improves with each session
- Supports up to 6 collaborating agents with clear role separation

## Installation (Windows 11)

```powershell
.\cli\grok-agent.ps1 install templates/super-agents/agent-swarm-with-shared-memory/grok-agent.yaml
```

Or post the manifest on X with the text `grok install this`.

## Usage

```powershell
.\cli\grok-agent.ps1 run agent-swarm-with-shared-memory "Evaluate the long-term societal impact of widespread AI adoption with evidence from multiple domains"
```

The swarm returns a synthesized answer that includes the full debate trace, dissenting views, and memory-backed reasoning.

## Technical Notes

- Memory backend: Mem0 + Qdrant (local-first, private)
- Cost limit: $1.20 per session (configurable in manifest)
- Designed for complex, multi-perspective questions where collective reasoning outperforms single-agent output

## License

Apache 2.0

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
