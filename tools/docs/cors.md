# CORS and Proxy Patterns

Two shapes of tool in this toolkit, two different deployment stories.

## The shapes

| Shape | Example tools | Talks to xAI / X directly? |
|---|---|---|
| **Static frontend** (single-file HTML, no backend) | 04, 05, 07, 09, 12, 18 | No — these tools are heuristic-only and touch no API |
| **Static frontend that calls an API** | 19, 20 (Grok-backed) | **No — must proxy** |
| **Node backend** | 01, 02, 03, 08, 10, 11, 13, 14, 16, 17 | Yes — server-to-server is fine |
| **Next.js / Firebase** | 06 | Yes — server components / API routes |

## Why you need a proxy for browser-based Grok tools

The xAI API (and X API v2) do not send permissive CORS headers. A direct `fetch('https://api.x.ai/...')` from a page on your domain gets blocked by the browser:

```
Access to fetch at 'https://api.x.ai/v1/chat/completions' from origin
'https://example.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin'
header is present on the requested resource.
```

You cannot fix this on the client. There is also a second, equally important reason to proxy: **putting `XAI_API_KEY` in a browser bundle exposes it to every user of the site.** A proxy keeps the key server-side and the browser gets no CORS rejection because the response now comes from your own origin.

**Rule:** any tool whose frontend talks to xAI or X API v2 ships with a tiny server-side proxy. The proxy holds the key, forwards the request, streams the response back.

## Recommended proxy patterns

### Vercel Edge Function

One file, deploys with `vercel deploy`. Put it next to your `index.html` in a Vercel project:

```js
// api/grok.js
export const config = { runtime: 'edge' };

export default async function handler(req) {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }
  const upstream = await fetch('https://api.x.ai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${process.env.XAI_API_KEY}`,
    },
    body: await req.text(),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
```

Set `XAI_API_KEY` in the Vercel project's environment. The frontend hits `/api/grok` instead of `api.x.ai`.

### Cloudflare Worker

```js
// worker.js
export default {
  async fetch(request, env) {
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });
    const upstream = await fetch('https://api.x.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${env.XAI_API_KEY}`,
      },
      body: request.body,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    });
  },
};
```

Bind `XAI_API_KEY` as a Worker secret (`wrangler secret put XAI_API_KEY`).

### Cloudflare Pages Functions

Same shape, named file under `functions/api/grok.js`. Syntax matches the Worker example above. Pick Pages if your static site is already there.

### X API v2 proxy

Same pattern, swap the URL and the header:

```js
const upstream = await fetch(`https://api.x.com/2/${encodeURI(path)}`, {
  headers: { Authorization: `Bearer ${env.X_BEARER_TOKEN}` },
});
```

Expose only the endpoints your tool needs. Don't make it a generic pass-through — that becomes an abuse vector.

## Rate-limit passthrough

When the upstream returns `429`, return it **unchanged** to your frontend. Preserve these headers so the client can back off intelligently:

- `Retry-After`
- `x-ratelimit-limit`
- `x-ratelimit-remaining`
- `x-ratelimit-reset`

Example:

```js
const passthrough = ['retry-after', 'x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-reset'];
const headers = new Headers({ 'Access-Control-Allow-Origin': '*' });
for (const h of passthrough) {
  const v = upstream.headers.get(h);
  if (v) headers.set(h, v);
}
```

Don't silently retry on the proxy — you burn quota without the client knowing. Let the client decide.

## Hardening the proxy

Before you ship:

- **Restrict origins.** `Access-Control-Allow-Origin: *` is fine for open tools; switch to your specific origin if the proxy is for one deployment.
- **Validate the method and body shape.** Only pass through requests that match your tool's contract.
- **Rate-limit your own proxy.** One key, many users = easy way to burn your quota. Cloudflare Workers have `RATE_LIMIT` bindings; Vercel has `edge-config`-based approaches.
- **Log sparingly.** You do not want to log bearer tokens. You do want to log upstream status codes and errors.
- **Cache where it helps.** Grok responses for identical prompts can be cached briefly (use with care — freshness vs. cost).

## What about local file:// tools?

The six heuristic Live tools (04, 05, 07, 09, 12, 18) work offline. They never talk to xAI or X, so CORS and keys simply don't apply. Open the HTML, use it, done.

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
