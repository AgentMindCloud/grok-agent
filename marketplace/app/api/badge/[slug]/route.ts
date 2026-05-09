/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Build-time SVG badge route: GET /api/badge/<slug>
 *
 * Built for xAI, X, Grok and the ecosystem community. ❤️
 *
 * Each known agent slug pre-bakes one SVG badge at build time. Partners
 * embed it in their READMEs / blog posts:
 *
 *   ![Built on Grok Agent OS](https://<pages>/api/badge/x-money-companion-dashboard)
 *
 * Brand palette mirrors README.md (Spectral v1):
 *   left side  — `0A0A0A` charcoal with `F4ECDA` parchment text
 *   right side — `FF1E70` cinnabar with `F4ECDA` parchment text
 *
 * The slug is rendered verbatim. Width is computed from a fixed-width
 * approximation (8px per char + padding) so the SVG renders identically
 * everywhere without external font metrics.
 */

import { loadAllAgents } from '../../../../lib/manifests';

export const dynamic = 'force-static';

// Static-export pre-build: emit one badge file per known slug.
export function generateStaticParams() {
  return loadAllAgents().map((agent) => ({ slug: agent.slug }));
}

// Approximate width per character at the chosen font size (10px).
// Verdana / DejaVu Sans Mono fall on roughly 6.5px per char; pad for safety.
const CHAR_PX = 6.6;
const PADDING = 8;
const HEIGHT = 20;

const LEFT_LABEL = 'built on';
const RIGHT_PREFIX = 'grok-agent-os';

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function buildSvg(slug: string): string {
  const safeSlug = escapeXml(slug);
  const rightLabel = `${RIGHT_PREFIX} · ${safeSlug}`;

  const leftWidth = Math.ceil(LEFT_LABEL.length * CHAR_PX) + PADDING * 2;
  const rightWidth = Math.ceil(rightLabel.length * CHAR_PX) + PADDING * 2;
  const totalWidth = leftWidth + rightWidth;

  // Two flat rects (no gradient — matches the brand's clean two-tone look).
  // Text uses inline font-family fallback chain; black-text-shadow trick gives
  // the classic shields.io readability without an external CSS sheet.
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="${HEIGHT}" role="img" aria-label="Built on Grok Agent OS — ${safeSlug}">
  <title>Built on Grok Agent OS — ${safeSlug}</title>
  <linearGradient id="smooth" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="round">
    <rect width="${totalWidth}" height="${HEIGHT}" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#round)">
    <rect width="${leftWidth}" height="${HEIGHT}" fill="#0A0A0A"/>
    <rect x="${leftWidth}" width="${rightWidth}" height="${HEIGHT}" fill="#FF1E70"/>
    <rect width="${totalWidth}" height="${HEIGHT}" fill="url(#smooth)"/>
  </g>
  <g fill="#F4ECDA" text-anchor="middle" font-family="Verdana,DejaVu Sans,Geneva,sans-serif" font-size="11">
    <text x="${leftWidth / 2}" y="14">${LEFT_LABEL}</text>
    <text x="${leftWidth + rightWidth / 2}" y="14">${rightLabel}</text>
  </g>
</svg>`;
}

export function GET(
  _request: Request,
  { params }: { params: { slug: string } },
): Response {
  const svg = buildSvg(params.slug);
  return new Response(svg, {
    status: 200,
    headers: {
      'Content-Type': 'image/svg+xml; charset=utf-8',
      // Heavy caching is safe — the build regenerates every deploy.
      'Cache-Control': 'public, max-age=86400, immutable',
    },
  });
}
