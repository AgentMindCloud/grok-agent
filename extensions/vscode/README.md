<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — VS Code extension

> Built for xAI, X, Grok and the ecosystem community. ❤️

Inline schema validation, autocomplete, and hover docs for `grok-agent.yaml` v2.15 manifests inside Visual Studio Code.

This is the **v0.1** ship — a pure schema-contribution extension. It piggybacks on the canonical [Red Hat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) (declared as an `extensionDependency`) so you get full JSON Schema 2020-12 validation, completion, and hover documentation for every field in the v2.15 manifest — without bundling a custom language server.

## What you get

- Red squiggles on missing required fields (`version`, `kind`, `name`, `description`, `author`, `license`).
- Autocomplete for every section: `metadata`, `install`, `windows`, `grok`, `tools`, `public_apis`, `multi_agent`, `real_time_x`, `memory`, `provenance`, `constitution`, `safety`, `dependencies`, `evaluation`.
- Enum hints on every typed field — `kind`, `windows.min_powershell_version`, `tools[].type`, `tools[].api.method`, `tools[].api.auth`, `safety.scanner_severity_floor`, `memory.provider`, `provenance.langfuse.host`, `real_time_x.triggers[]`.
- Inline hover docs sourced from the Pydantic `Field(..., description=...)` tags in [`cli/grok-agent.py`](https://github.com/AgentMindCloud/grok-agent/blob/main/cli/grok-agent.py).

## Install

### From the VS Code Marketplace (when published)

```
ext install AgentMindCloud.vscode-grok-agent
```

### From source (today)

1. `cd extensions/vscode`
2. `npx --yes vsce package` produces `vscode-grok-agent-0.1.0.vsix`.
3. `code --install-extension vscode-grok-agent-0.1.0.vsix`.

The Red Hat YAML extension installs automatically as a dependency.

## What it validates

Every file matching `**/grok-agent.yaml` is validated against [`schemas/grok-manifest.json`](schemas/grok-manifest.json), which is auto-generated from the canonical Pydantic v2.15 model in [`cli/grok-agent.py`](https://github.com/AgentMindCloud/grok-agent/blob/main/cli/grok-agent.py) by [`scripts/export-openapi.py`](https://github.com/AgentMindCloud/grok-agent/blob/main/scripts/export-openapi.py).

Drift between the schema and the Python model is impossible because the same export script writes both:

- `spec/v2.15/schema.json` (canonical JSON Schema 2020-12)
- `spec/v2.15/openapi.yaml` (OpenAPI 3.1 envelope)
- `extensions/vscode/schemas/grok-manifest.json` (this extension's bundled schema)

The CI workflow runs `python scripts/export-openapi.py --check` on every PR; any drift fails the build.

## What it does NOT validate

Schema validation only catches structural and type errors. It does **not** run the Constitution scanner ([`safety/scanner.py`](https://github.com/AgentMindCloud/grok-agent/blob/main/safety/scanner.py)) — that requires a Python runtime. To get full Constitution compliance, run:

```powershell
python safety/scanner.py scan path\to\grok-agent.yaml
```

A Constitution-lint contribution that surfaces scanner findings as VS Code diagnostics is on the v0.2 roadmap.

## Roadmap

- **v0.2** — bundle the Constitution scanner findings as VS Code diagnostics (requires a small language-server contribution that shells out to Python).
- **v0.3** — `grok install this` CodeLens on every YAML file with a v2.15 manifest header (one-click install via `code:command:grok.install`).
- **v0.4** — snippet catalogue for the 4 X Money tool kinds, 7 Super Agent patterns, 22 creator templates.
- **v0.5** — submit to the official VS Code Marketplace.

## Contributing

This extension lives inside the main `AgentMindCloud/grok-agent` repo at [`extensions/vscode/`](https://github.com/AgentMindCloud/grok-agent/tree/main/extensions/vscode). Open issues and PRs against the main repo.

When changing the schema, run `python scripts/export-openapi.py` from the repo root — that regenerates `schemas/grok-manifest.json` here too.

## License

Apache-2.0. See [LICENSE](https://github.com/AgentMindCloud/grok-agent/blob/main/LICENSE).

Built for xAI, X, Grok and the ecosystem community. ❤️
