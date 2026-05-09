/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Build-time SVG trust-score badge: GET /api/trust-badge/<slug>
 *
 * Built for xAI, X, Grok and the ecosystem community. ❤️
 *
 * Distinct from /api/badge/<slug> (which advertises "built on" provenance).
 * The trust badge surfaces the auditable score from
 * docs/agent-trust-scores.json — composite of scanner pass-rate,
 * eval-suite presence, provenance completeness, and manifest stability.
 *
 * Tier visual language (Spectral v1):
 *   A (>=90)  — cinnabar (#FF1E70) with crown character
 *   B (>=75)  — cinnabar (#FF1E70)
 *   C (>=60)  — parchment (#F4ECDA) on charcoal text
 *   D ( <60)  — charcoal (#0A0A0A) — looks like a warning
 *
 * Embed snippet in any partner README:
 *
 *   ![Grok Agent OS Trust Score](https://<host>/api/trust-badge/<slug>)
 */

import fs from 'node:fs';
import path from 'node:path';
import { loadAllAgents } from '../../../../lib/manifests';

export const dynamic = 'force-static';

interface TrustEntry {
  slug: string;
  score: number;
  tier: 'A' | 'B' | 'C' | 'D';
  components: {
    scanner: number;
    eval: number;
    provenance: number;
    stability: number;
  };
}

const TRUST_JSON_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'agent-trust-scores.json',
);

function loadTrustData(): Record<string, TrustEntry> {
  try {
    const raw = fs.readFileSync(TRUST_JSON_PATH, 'utf-8');
    const parsed = JSON.parse(raw);
    return (parsed.agents ?? {}) as Record<string, TrustEntry>;
  } catch {
    return {};
  }
}

const TRUST_DATA = loadTrustData();

// Static-export pre-build: emit one badge file per known slug, even if
// the agent has no trust entry yet (we render an "unscored" badge so
// embeds never 404).
export function generateStaticParams() {
  return loadAllAgents().map((agent) => ({ slug: agent.slug }));
}

const TIER_VISUAL: Record<
  'A' | 'B' | 'C' | 'D' | 'unscored',
  { right: string; text: string; prefix: string }
> = {
  A:        { right: '#FF1E70', text: '#F4ECDA', prefix: 'A · ' },
  B:        { right: '#FF1E70', text: '#F4ECDA', prefix: 'B · ' },
  C:        { right: '#F4ECDA', text: '#0A0A0A', prefix: 'C · ' },
  D:        { right: '#0A0A0A', text: '#F4ECDA', prefix: 'D · ' },
  unscored: { right: '#3A3A3A', text: '#F4ECDA', prefix: '· ' },
};

const CHAR_PX = 6.6;
const PADDING = 8;
const HEIGHT = 20;
const LEFT_LABEL = 'trust score';

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function buildSvg(slug: string, entry: TrustEntry | undefined): string {
  const safeSlug = escapeXml(slug);
  const tier = entry?.tier ?? 'unscored';
  const visual = TIER_VISUAL[tier];

  const rightLabel = entry
    ? `${visual.prefix}${entry.score}`
    : `${visual.prefix}unscored`;

  const leftWidth = Math.ceil(LEFT_LABEL.length * CHAR_PX) + PADDING * 2;
  const rightWidth = Math.ceil(rightLabel.length * CHAR_PX) + PADDING * 2;
  const totalWidth = leftWidth + rightWidth;

  const ariaSummary = entry
    ? `Grok Agent OS trust score for ${safeSlug}: ${entry.score} (tier ${entry.tier})`
    : `Grok Agent OS trust score for ${safeSlug}: not yet scored`;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="${HEIGHT}" role="img" aria-label="${ariaSummary}">
  <title>${ariaSummary}</title>
  <linearGradient id="smooth" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="round">
    <rect width="${totalWidth}" height="${HEIGHT}" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#round)">
    <rect width="${leftWidth}" height="${HEIGHT}" fill="#0A0A0A"/>
    <rect x="${leftWidth}" width="${rightWidth}" height="${HEIGHT}" fill="${visual.right}"/>
    <rect width="${totalWidth}" height="${HEIGHT}" fill="url(#smooth)"/>
  </g>
  <g text-anchor="middle" font-family="Verdana,DejaVu Sans,Geneva,sans-serif" font-size="11">
    <text x="${leftWidth / 2}" y="14" fill="#F4ECDA">${LEFT_LABEL}</text>
    <text x="${leftWidth + rightWidth / 2}" y="14" fill="${visual.text}" font-weight="bold">${rightLabel}</text>
  </g>
</svg>`;
}

export function GET(
  _request: Request,
  { params }: { params: { slug: string } },
): Response {
  const entry = TRUST_DATA[params.slug];
  const svg = buildSvg(params.slug, entry);
  return new Response(svg, {
    status: 200,
    headers: {
      'Content-Type': 'image/svg+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=86400, immutable',
    },
  });
}
