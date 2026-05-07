# grok-pulse-mcp-server

> The first MCP server built for builders shipping in the xAI / X / Grok ecosystem. One tool call, Grok-prioritized: this is what needs your attention today.

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

## Roadmap

- **v0.1** ✅ Scaffold + project structure + auth + error handling
- **v0.2** 🚧 Five v1 tools (`pulse_today`, `summarize_repo_activity`, `weekly_digest`, `next_action`, `roast_pr`)
- **v0.3** Streamable HTTP transport (remote install)
- **v0.4** Optional write tools (open PR comment, label issue, close stale PR) — opt-in, separately scoped
- **v1.0** Native X (Twitter) integration once a stable X MCP exists

---

## Contributing

Issues, PRs, and roasts welcome. This is built in public — follow [@JanSol0s](https://x.com/JanSol0s) on X for build threads.

---

## License

[Apache License 2.0](LICENSE) © 2026 AgentMindCloud.
