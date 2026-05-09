<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# grok-pulse-mcp-server

> Built for xAI, X, Grok and the ecosystem community. ❤️
>
> The first MCP server built for builders shipping in the xAI / X / Grok ecosystem. One tool call, Grok-prioritized: this is what needs your attention today. Plus: the entire Grok Agent OS catalog (33+ templates) exposed as first-class MCP tools.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-orange.svg)](https://modelcontextprotocol.io)
[![status](https://img.shields.io/badge/status-v0.1_scaffold-amber.svg)]()

> **v0.1 — scaffold only.** Server boots, tools land in v0.2. Architecture spec in [`SPEC.md`](../SPEC.md).

---

## Why this exists

Every serious builder in the xAI / X / Grok ecosystem juggles 5–20 GitHub repos, an X presence, and a stream of notifications, PR review requests, and CI failures. There is no single tool that says: **"This is what you should work on right now, and here's why."**

`grok-pulse-mcp-server` is that tool — designed as an MCP server so it works inside any compatible agent (Claude Code, Cowork, Cursor, custom builds). It pulls live signal from your GitHub repos, runs the batch through Grok for prioritization, and returns structured, agent-friendly answers.

Five tools, zero ceremony:

| Tool | What it does |
| --- | --- |
| `pulse_today` | Returns today's prioritized attention list across all your repos |
| `summarize_repo_activity` | Grok-summarized activity for one repo over a window |
| `weekly_digest` | Multi-repo Grok-synthesized week-in-review |
| `next_action` | Grok's single decisive recommendation: what to do *right now* |
| `roast_pr` | Grok roasts one of your PRs in a chosen voice. Yes, really. |

---

## Quickstart

> **Note: v0.1 is scaffold only — installable and bootable, but tools are not yet wired. v0.2 ships them.**

```bash
git clone https://github.com/AgentMindCloud/grok-pulse-mcp-server.git
cd grok-pulse-mcp-server
npm install
npm run build

cp .env.example .env
# Edit .env — fill in GITHUB_TOKEN and XAI_API_KEY

node dist/index.js
# Server boots on stdio. Connect it to your MCP client.
```

### Connecting to Claude Code

Add to your `~/.config/claude-code/mcp_servers.json`:

```json
{
  "mcpServers": {
    "grok-pulse": {
      "command": "node",
      "args": ["/absolute/path/to/grok-pulse-mcp-server/dist/index.js"],
      "env": {
        "GITHUB_TOKEN": "github_pat_…",
        "XAI_API_KEY": "xai-…"
      }
    }
  }
}
```

### Connecting to Cowork

Use the [custom MCP server flow](https://docs.claude.com) — point it at the local `dist/index.js`.

---

## Authentication

Two env vars, both validated at startup:

| Variable | Required? | Notes |
| --- | --- | --- |
| `GITHUB_TOKEN` | Yes | Fine-grained PAT, minimum read scopes: Actions, Contents, Issues, Metadata, Pull requests, Notifications, Starring. |
| `XAI_API_KEY` | Yes | From [console.x.ai](https://console.x.ai). |
| `GITHUB_USER` | No | Auto-resolved via `/user` if unset. |
| `XAI_MODEL` | No | Defaults to `grok-4-latest`. |
| `XAI_BASE_URL` | No | Defaults to `https://api.x.ai/v1`. |

Tokens never appear in tool descriptions, error messages, or logs — token-shaped substrings are masked before any output reaches the LLM client.

---

## Tool reference

> _Full I/O schemas land in v0.2 with the implementations. See [`SPEC.md`](../SPEC.md) for the locked design._

---

## MCP integration: 33 Grok agents as MCP tools

In addition to the five Grok-powered productivity tools above, `pulse` dynamically
registers **one MCP tool per Grok Agent OS template** at server boot. The
`grok-agent-tools` registrar (`src/grok-agent-tools.ts`) walks
`../templates/<category>/<slug>/grok-agent.yaml`, parses each manifest with
[`js-yaml`](https://github.com/nodeca/js-yaml), and emits a Zod-typed MCP tool
named `grok-agent-<slug>` for every entry it finds.

After this lands, any MCP client (Claude Desktop, Cursor, custom builds) sees
~33 additional tools spanning the categories:

| Category | Slug examples | Tool name format |
| --- | --- | --- |
| `super-agents` | `living-narrative-fabric`, `cross-reality-action-fabric` | `grok-agent-living-narrative-fabric` |
| `finance` | `x-money-companion-dashboard`, `x-smart-cashtag-alpha-engine` | `grok-agent-x-money-companion-dashboard` |
| `creator` | `reply-drafter`, `thread-builder`, `analytics-summarizer` | `grok-agent-reply-drafter` |
| `general` | `daily-briefing-agent`, `research-assistant` | `grok-agent-daily-briefing-agent` |
| `x-native` | `mention-summarizer`, `trend-aligned-poster` | `grok-agent-mention-summarizer` |

### Starting the server

```powershell
# Windows 11 + PowerShell (the only supported user environment)
cd pulse
npm install
npm run build
npm run dev   # tsx watch src/index.ts (development)
# or
npm start     # node dist/index.js (production)
```

On boot, the server logs to **stderr** (never stdout — that channel is the MCP
protocol):

```
[grok-pulse-mcp-server] v0.1.0 ready on stdio.
[grok-agent-tools] registered 33 grok-agent-* tools from /repo/templates.
[grok-pulse-mcp-server] grok-agent-tools: 33 agent tools registered.
```

If `templates/` is not alongside the running `pulse/` (for example when pulse
is published as a standalone npm package), set the `GROK_AGENT_TEMPLATES_DIR`
environment variable to point at it.

### Adding pulse to Claude Desktop

Edit `~/.config/Claude/claude_desktop_config.json` (Linux), or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "grok-pulse": {
      "command": "node",
      "args": ["C:\\path\\to\\grok-agent\\pulse\\dist\\index.js"],
      "env": {
        "GITHUB_TOKEN": "github_pat_...",
        "XAI_API_KEY": "xai-...",
        "GROK_AGENT_TEMPLATES_DIR": "C:\\path\\to\\grok-agent\\templates"
      }
    }
  }
}
```

After Claude Desktop restarts, you will see `pulse_today` plus every
`grok-agent-<slug>` tool in the picker.

### Tool contract: the `action` enum

Every `grok-agent-<slug>` tool accepts a single `action` argument. The enum has
exactly three values; calling with anything else returns a structured error:

| `action` value | Returns |
| --- | --- |
| `describe` | A markdown summary plus structured JSON: display name, tagline, kind, category, author, license, manifest version, Grok model, tags, public APIs declared in the manifest, and the full `description` field. |
| `install_command` | The PowerShell `grok-agent install <slug>` command, the prerequisites list, and the GitHub folder URL. Copy-paste-ready for a Windows 11 + PowerShell session. |
| `manifest_url` | The canonical raw GitHub manifest URL, the GitHub folder URL, the repo-relative path, and the install command. Useful for clients that want to fetch the raw YAML themselves. |

### Example tool calls

From an MCP client, calling `grok-agent-x-money-companion-dashboard` with
`{"action":"install_command"}`:

```markdown
# Install: X Money Companion Dashboard

## Prerequisites

- Windows 11
- Python 3.12+
- PowerShell 5.1+

## PowerShell command (Windows 11)

```powershell
grok-agent install x-money-companion-dashboard
```

Manifest folder: https://github.com/AgentMindCloud/grok-agent/tree/main/templates/finance/x-money-companion-dashboard
```

Calling the same tool with `{"action":"manifest_url"}`:

```markdown
# Manifest URLs: X Money Companion Dashboard

- **Folder (GitHub)**: https://github.com/AgentMindCloud/grok-agent/tree/main/templates/finance/x-money-companion-dashboard
- **Raw manifest (YAML)**: https://raw.githubusercontent.com/AgentMindCloud/grok-agent/main/templates/finance/x-money-companion-dashboard/grok-agent.yaml
- **Repo-relative path**: `templates/finance/x-money-companion-dashboard/grok-agent.yaml`
```

Calling with `{"action":"describe"}` returns the full manifest summary
(display name, tagline, tags, public APIs, Grok model, description) for use
inside a larger LLM context window.

### Disclaimers

The finance and tax templates surfaced through these tools carry the standard
Grok Agent OS disclaimers in their own UIs and READMEs:

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.
>
> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction. Consult a
> licensed tax professional.

The `grok-agent-*` MCP tools themselves are read-only (`describe`,
`install_command`, `manifest_url`) — they do not execute installs, do not call
Grok, and do not mutate any state. They are a discovery + provenance layer.

---

## Roadmap

- **v0.1** ✅ Scaffold + project structure + auth + error handling
- **v0.2** 🚧 Five v1 tools (`pulse_today`, `summarize_repo_activity`, `weekly_digest`, `next_action`, `roast_pr`)
- **v0.2.1** ✅ Dynamic `grok-agent-<slug>` MCP tools — every Grok Agent OS template registered automatically (`src/grok-agent-tools.ts`)
- **v0.3** Streamable HTTP transport (remote install)
- **v0.4** Optional write tools (open PR comment, label issue, close stale PR) — opt-in, separately scoped
- **v1.0** Native X (Twitter) integration once a stable X MCP exists

---

## Contributing

Issues, PRs, and roasts welcome. This is built in public — follow [@JanSol0s](https://x.com/JanSol0s) on X for build threads.

---

## License

[Apache License 2.0](LICENSE) © 2026 AgentMindCloud.
