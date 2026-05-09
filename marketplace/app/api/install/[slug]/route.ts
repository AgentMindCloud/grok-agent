/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Build-time install redirect: GET /api/install/<slug>
 *
 * Built for xAI, X, Grok and the ecosystem community. ❤️
 *
 * Each known agent slug pre-bakes one tiny HTML/redirect file at build
 * time that issues a 307 to the canonical githubManifestUrl. Embed in
 * partner posts as the install affordance:
 *
 *   <a href="https://agentmindcloud.github.io/grok-agent/api/install/x-money-companion-dashboard">
 *     Install on Windows 11 + PowerShell
 *   </a>
 *
 * IMPORTANT — counting limitation:
 *
 *   This is a static export (output: 'export' + GitHub Pages). The route
 *   runs at BUILD time, not request time. Real per-request counting
 *   requires an analytics layer downstream of the redirect:
 *
 *     - Plausible Analytics (`data-domain` script on the partner page)
 *     - Vercel Web Analytics (if redeployed on Vercel)
 *     - A self-hosted endpoint that proxies the redirect
 *
 *   The seed counts in `marketplace/data/install-counts.json` are
 *   placeholder data for the "Trending this week" UI surface. Production
 *   replaces them with an analytics-layer rollup. See the README section
 *   "Install counter API" for the deployment path.
 *
 * The slug list mirrors the badge route's generateStaticParams pattern
 * so every catalogue agent gets exactly one redirect file at
 * `marketplace/out/api/install/<slug>/index.html` after `npm run build`.
 */

import { loadAllAgents } from '../../../../lib/manifests';

export const dynamic = 'force-static';

// Static-export pre-build: emit one redirect per known slug.
export function generateStaticParams() {
  return loadAllAgents().map((agent) => ({ slug: agent.slug }));
}

// Fallback target if a slug is unknown at build time. Should never fire
// because generateStaticParams() pre-filters to known slugs.
const FALLBACK_URL =
  'https://github.com/AgentMindCloud/grok-agent/tree/main/templates';

function targetFor(slug: string): string {
  const agent = loadAllAgents().find((entry) => entry.slug === slug);
  return agent?.githubManifestUrl ?? FALLBACK_URL;
}

export function GET(
  _request: Request,
  { params }: { params: { slug: string } },
): Response {
  const location = targetFor(params.slug);
  // 307 (Temporary Redirect) preserves the request method and body, which
  // is important for partners who want to A/B test redirect targets later
  // without changing semantics. A 302 would also work; 301 is too sticky
  // (browsers cache it aggressively and ignore future updates).
  return new Response(null, {
    status: 307,
    headers: {
      Location: location,
      // Short cache: a redirect is cheap to recompute, and we want
      // partners to pick up new manifest URLs on the next deploy.
      'Cache-Control': 'public, max-age=300, s-maxage=3600',
    },
  });
}
