<!-- Apache 2.0 License -->
<!-- Copyright 2026 AgentMindCloud -->

# Provenance-First Trust Engine

**Lighter Super Agent for Grok Agent OS**

Every answer includes a beautiful, clickable provenance report showing every source, X post, memory fragment, confidence score, and alternative viewpoints considered — delivering maximum trust and transparency on complex topics.

## Key Features

- Full Langfuse tracing on every claim
- Clickable source links with confidence scoring
- Alternative viewpoints presented when relevant
- Exportable audit reports
- Built-in contradiction highlighting

## Installation (Windows 11)

```powershell
.\cli\grok-agent.ps1 install templates/super-agents/provenance-first-trust-engine/grok-agent.yaml
```

Or post the manifest on X with the text `grok install this`.

## Usage

```powershell
.\cli\grok-agent.ps1 run provenance-first-trust-engine "What is the current scientific consensus on long-term effects of social media on adolescent mental health?"
```

The agent returns the synthesized answer plus a full provenance panel with verifiable links and scores.

## Technical Notes

- Tracing backend: Langfuse (local-first mode supported)
- Cost limit: $0.80 per session (configurable in manifest)
- Ideal for high-stakes research, policy, or fact-checking workflows where auditability matters

## License

Apache 2.0
