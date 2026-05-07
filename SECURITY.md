# Security Policy

This project takes security seriously. If you find a vulnerability — in the tooling, in the shared clients, or in any Live tool — please report it privately before disclosing publicly.

## Reporting a vulnerability

Email **security@agentmindcloud.dev** with:

- A clear description of the issue and its impact
- Steps or a minimal proof-of-concept to reproduce
- Affected tool(s) or package(s) and the version / commit SHA
- Your preferred contact for follow-up

**Expected response:** we aim to acknowledge within **72 hours** and provide a remediation timeline within one week. Please do not open a public GitHub issue for security reports.

## Scope

- The root monorepo and its build/CI tooling
- Every tool under `tools/`
- Every shared package under `shared/`
- Example code and templates shipped in this repo

Out of scope: third-party services this toolkit integrates with (X API, xAI Grok API, hosting platforms). Report issues in those to their vendors.

## Supported versions

The project is pre-1.0. Only the latest `0.1.x` minor line receives security fixes; older snapshots are archived.

| Version | Supported |
|---|---|
| `0.1.x` | Yes |
| `< 0.1` | No  |

Once we reach `1.0`, this table will expand to cover the active major line plus the previous one.

## Token handling posture

Secrets (`XAI_API_KEY`, `X_BEARER_TOKEN`, any OAuth tokens) must follow these rules:

- **Never committed.** `.env` and `.env.*` are gitignored. The repo ships only `.env.example` placeholders with no real values.
- **Server-side:** load from environment variables at process start. Never log, never serialize into responses, never cache to disk.
- **Client-side (browser):** session-only. A user may paste a token into a tool's input field for that page load, but the tool must not persist it — no `localStorage`, no cookies, no query strings. The token lives in memory until the tab closes.
- **Live tools with no backend** (04, 05, 07, 09, 12, 18) do not accept tokens at all; they operate on public data or local heuristics only.
- **Spec'd tools** that need tokens proxy them through a serverless function or Node backend — never directly from the browser. See [`docs/cors.md`](docs/cors.md) for why.

See [`docs/tokens.md`](docs/tokens.md) for setup, rotation, and per-tool requirements.

## What counts as a vulnerability

- Secret exfiltration, token leakage in logs/responses/errors
- XSS, CSRF, clickjacking, or prototype pollution in any Live tool
- Prompt-injection paths that coerce a Grok-backed tool into unintended actions
- Dependency issues with known CVEs in shipped `package.json` trees
- CI or supply-chain weaknesses (misconfigured actions, stale pinned versions with known issues)

## Safe-harbor

Good-faith security research on your own fork or self-hosted copy is welcome. Please avoid testing against shared infrastructure you don't own, and never access data that isn't yours.

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
