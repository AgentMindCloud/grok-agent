<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Deferred: per-agent `opengraph-image.tsx`

The original spec called for `app/agents/[slug]/opengraph-image.tsx` rendering
a per-agent OG card via `next/og`'s `ImageResponse`. It is intentionally
**not present** in this skeleton.

## Why

Next.js 14.2's metadata-route loader strips `generateStaticParams` (and
`generateImageMetadata`) from metadata files inside dynamic segments
(`[slug]`) when `next.config.js` sets `output: 'export'`. The build fails
with:

```
Error: Page "/agents/[slug]/opengraph-image" is missing "generateStaticParams()"
so it cannot be used with "output: export" config.
```

Reproduced on `next@14.2.5` with `output: 'export'` + `dynamicParams = false`
+ explicit `generateStaticParams`. Tracking upstream.

## Workaround in place

Every per-agent page falls back to the **root** `app/opengraph-image.tsx`
which renders a static "Grok Agent OS — Marketplace" card. Good enough for
the skeleton.

## Restoration plan

When the upstream fix lands (or we drop `output: 'export'`):

1. Recreate `app/agents/[slug]/opengraph-image.tsx`.
2. Read `findAgentBySlug(params.slug)` from `lib/manifests.ts`.
3. Render `agent.displayName` + `agent.tagline` over the terminal background.
4. Re-add `export function generateStaticParams()` returning every agent slug.
