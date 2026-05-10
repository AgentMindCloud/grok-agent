<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->

---
title: Schema Explorer
description: Paste a grok-agent.yaml manifest and validate it live against the v2.15 JSON Schema, with Constitution warnings rendered alongside.
aside: false
---

# Schema Explorer

Paste any `grok-agent.yaml` manifest into the editor below to validate it live against the canonical v2.15 JSON Schema (the same `spec/v2.15/schema.json` shipped in the repo). The validator runs entirely in your browser — no manifest text leaves the page, no telemetry is collected, and nothing is written to disk. Ajv 8 and js-yaml 4 are loaded on demand from `esm.sh`, so the static VitePress build stays dependency-free.

Schema errors render in cinnabar on the right-hand pane. Constitution warnings — missing `metadata.tagline`, `provenance.append_only` not set to `true`, a `super-agent` kind without a `constitution` block, or a finance kind without a `not_financial_advice` disclaimer — render on charcoal so you cannot miss them. Use the sample buttons to load a Super Agent or finance dashboard skeleton, then edit and watch the results update on every keystroke. To validate a local file from PowerShell instead, run `python cli/grok-agent.py validate <path>` from the repo root, with results stored under `$env:LOCALAPPDATA\grok-agent\logs\`.

<SchemaValidator />

> Built for xAI, X, Grok and the ecosystem community. ❤️
