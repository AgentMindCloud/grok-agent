# Tokens and Secrets

This toolkit integrates with two upstream APIs. This doc explains how to get credentials, how to store them safely, and which tool needs which token.

## TL;DR

| Token | Source | Scope | Where it lives |
|---|---|---|---|
| `XAI_API_KEY` | [console.x.ai](https://console.x.ai) | xAI Grok API | **Server-side only.** Never shipped to the browser. |
| `X_BEARER_TOKEN` | [developer.x.com](https://developer.x.com) | X API v2 | **Server-side only.** Bearer tokens auth your app — leaking one leaks your quota. |

Copy `.env.example` from `shared/grok-client/` or `shared/x-api-client/` into a sibling `.env`, fill in the values, and start the tool. `.env` is gitignored.

---

## XAI_API_KEY

### Getting one

1. Sign in at [console.x.ai](https://console.x.ai) with your X account.
2. Open **API Keys** and create a new key. Name it after the tool or deployment using it (e.g. `xpt-ghostwriter-prod`).
3. Copy the key **once** — the console will not show it again.

### Limits and billing

- xAI charges per token. Free tiers and credits change; check the pricing page the day you deploy.
- Grok-2 family models (`grok-2-latest` is the client's default) have per-minute rate limits. Back off on `429` responses; the shared `grok-client` does this automatically.
- Long-context requests (>32k input tokens) cost materially more. The AI-writing tools in this toolkit keep prompts tight by default.

### How to use it

```bash
# .env in your tool's directory
XAI_API_KEY=xai-...
```

```js
const GrokClient = require('@x-platform-toolkit/grok-client');
const grok = new GrokClient({ apiKey: process.env.XAI_API_KEY });
```

### What not to do

- **Never bundle it into a static frontend.** If your tool's `index.html` ships to a CDN, the key ends up in the browser — assume it is public within minutes. Proxy through a serverless function instead. See [`cors.md`](cors.md).
- Never log the key. The shared client masks it in error messages; don't print `process.env.XAI_API_KEY` from your own code either.
- Never embed it in a URL (query strings leak to referer headers and access logs).

---

## X_BEARER_TOKEN

### Getting one

1. Apply for a developer account at [developer.x.com](https://developer.x.com).
2. Create a Project and within it an App.
3. Under **Keys and tokens**, generate a Bearer Token. Name the app so you know which tool it belongs to.

### API tier implications

X's API has paid tiers. The toolkit assumes **Basic** or above unless the tool's README says otherwise.

| Tier | Monthly cap | What works here |
|---|---|---|
| Free | Write-only + very limited reads | Almost nothing in this toolkit |
| Basic | ~10k reads/mo | Most analytics tools for a single account |
| Pro | ~1M reads/mo | Comfortable for cross-account and niche benchmarking |
| Enterprise | Custom | Everything, at scale |

The per-tool requirements table below flags which tier is realistic for each tool.

### Storage

- Bearer tokens are app-level credentials. Treat them like passwords.
- Rotate if you suspect exposure (see **Rotation** below).
- For local dev, keep them in `shared/x-api-client/.env`. For production, set them as environment variables on your host (Render, Railway, Fly, Vercel — wherever).

### How to use it

```bash
# .env
X_BEARER_TOKEN=AAAA...
```

```js
const XApiClient = require('@x-platform-toolkit/x-api-client');
const client = new XApiClient({ bearerToken: process.env.X_BEARER_TOKEN });
```

---

## Rotation and lifetime

- **Rotate on schedule:** every 90 days is a reasonable default. Calendar it.
- **Rotate immediately on:** suspected leak, departing collaborator, compromised dev machine, unexpected quota burn.
- **Revoke first, then rotate.** In both consoles you can revoke the old token as you issue the new one — this prevents a window where both work.
- **Zero-downtime rotations:** deploy the new env var first, verify the tool works, then revoke the old token.
- **Short-lived tokens > long-lived tokens.** Prefer per-tool / per-environment credentials over one global key. Blast radius drops.

## Per-tool token requirements

| # | Tool | Status | `XAI_API_KEY` | `X_BEARER_TOKEN` | Notes |
|---|---|---|---|---|---|
| 03 | Contextual Reply Suggester | Spec'd | Required | — | Grok only |
| 04 | Pre-Post Virality Scorer | Live | — | — | Heuristic, no network |
| 05 | Pinned Post A/B Rotator | Live | — | — | Local storage only |
| 06 | Digital Product Storefront | Spec'd | — | — | Firebase; no X / Grok |
| 07 | Content Compound Calculator | Live | — | — | Heuristic, no network |
| 11 | Ghostwriter Mode with Memory | Spec'd | Required | — | Grok only |
| 12 | Controversy Detector | Live | — | — | Heuristic, no network |
| 13 | Thread-to-Newsletter Converter | Spec'd | Required | — | Grok only |
| 16 | Follower Migration Assistant | Spec'd | Required | — | Grok only |
| 17 | Post Necromancer | Spec'd | Required | — | Grok only |
| 19 | Grok Thread Composer | Spec'd | Required | — | Proxy required for browser use |
| 20 | X Articles Optimizer | Spec'd | Required | — | Proxy required for browser use |

Legend: **Required** = tool will not function without it. **—** = tool does not need it.

---

## When something leaks

1. **Revoke** the affected token in its console immediately.
2. **Rotate** — issue a replacement and redeploy.
3. **Audit** recent usage dashboards for anomalous calls.
4. **Report** per [`SECURITY.md`](../SECURITY.md) if the leak originated in this repo.
5. **Post-mortem** — how did it get out? Commit message? Log file? Screenshot? Fix the class of mistake.

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
