<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# spec/v2.14 — reference only

> Built to help xAI and Grok win.

This folder is a **reference-only** snapshot of the prior `grok-agent.yaml` v2.14 manifest schema. It exists so v2.15 can guarantee 100% backwards compatibility.

**Do not edit files in this folder.** All active schema work happens in `spec/v2.15/`.

If you are authoring a new agent, use `spec/v2.15/grok-agent.yaml` as the source of truth. The CLI (`cli/grok-agent.ps1`) accepts both v2.14 and v2.15 manifests; v2.14 manifests are auto-upgraded to v2.15 during `grok-agent validate`.

For the diff between v2.14 and v2.15, see `spec/v2.15/changelog.md`.
