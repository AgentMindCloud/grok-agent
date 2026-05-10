<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Changelog — Grok Agent OS VS Code extension

> Built for xAI, X, Grok and the ecosystem community. ❤️

All notable changes to this extension are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-05-09

### Added

- Initial release. Schema-only contribution covering `**/grok-agent.yaml` files.
- Bundled `schemas/grok-manifest.json` (auto-generated from the canonical Pydantic v2.15 model in `cli/grok-agent.py` via `scripts/export-openapi.py`).
- `extensionDependencies` on `redhat.vscode-yaml` so the Red Hat YAML extension installs automatically.
- `vscode:prepublish` self-check entry point.
- Apache-2.0 license. Repository pointer to [`AgentMindCloud/grok-agent/extensions/vscode`](https://github.com/AgentMindCloud/grok-agent/tree/main/extensions/vscode).
