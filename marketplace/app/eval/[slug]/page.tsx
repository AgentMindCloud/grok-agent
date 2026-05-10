// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Per-slug DeepEval drill-down route. Server Component.
// Reads docs/eval-history.json + docs/agent-trust-scores.json + the
// agent's grok-agent.yaml at build time (via fs.readFileSync) and
// renders, for one agent slug:
//   - a header with displayName, tier badge, trust score number, manifest
//     GitHub link;
//   - a latest-run scoreboard (per-metric current value + 7-day arrow);
//   - the <EvalTimeSeriesChart> client component;
//   - the agent's declared evaluation.deepeval.metrics list;
//   - graceful empty-state when history is missing.
// Mirrors the generateStaticParams pattern from
// marketplace/app/audit-dashboard/[slug]/page.tsx so the static export
// pre-bakes one drill-down page per catalogued agent.
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5.

import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import Link from 'next/link';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { findAgentBySlug, loadAllAgents } from '../../../lib/manifests';
import { TIER_LABELS } from '../../../lib/types';
import EvalTimeSeriesChart, {
  type EvalRun,
} from '../../../components/EvalTimeSeriesChart';

interface PageProps {
  params: { slug: string };
}

interface EvalAgentEntry {
  category?: string;
  kind?: string;
  metrics_declared?: string[];
  runs?: EvalRun[];
  latest_metrics?: Record<string, number>;
  trend_7d?: Record<string, number>;
}

interface EvalHistory {
  computed_at?: string;
  schema_version?: string;
  agent_count?: number;
  metric_count?: number;
  summary?: {
    total_runs?: number;
    agents_with_history?: number;
    agents_no_history?: number;
  };
  agents?: Record<string, EvalAgentEntry>;
}

interface TrustScoreEntry {
  slug: string;
  category: string;
  kind: string;
  score: number;
  tier: string;
  components?: {
    scanner?: number;
    eval?: number;
    provenance?: number;
    stability?: number;
  };
}

interface TrustScores {
  agents: Record<string, TrustScoreEntry>;
}

const REPO_ROOT = path.resolve(process.cwd(), '..');
const EVAL_HISTORY_PATH = path.join(REPO_ROOT, 'docs', 'eval-history.json');
const TRUST_SCORES_PATH = path.join(
  REPO_ROOT,
  'docs',
  'agent-trust-scores.json',
);

function loadEvalHistory(): EvalHistory | null {
  try {
    const raw = fs.readFileSync(EVAL_HISTORY_PATH, 'utf-8');
    return JSON.parse(raw) as EvalHistory;
  } catch {
    return null;
  }
}

function loadTrustScores(): TrustScores | null {
  try {
    const raw = fs.readFileSync(TRUST_SCORES_PATH, 'utf-8');
    return JSON.parse(raw) as TrustScores;
  } catch {
    return null;
  }
}

function loadDeclaredMetricsFromManifest(manifestRelPath: string): string[] {
  try {
    const manifestAbs = path.join(REPO_ROOT, manifestRelPath);
    const raw = fs.readFileSync(manifestAbs, 'utf-8');
    const parsed = yaml.load(raw) as Record<string, unknown> | undefined;
    if (!parsed || typeof parsed !== 'object') return [];
    const evaluation = (parsed as { evaluation?: Record<string, unknown> })
      .evaluation;
    if (!evaluation || typeof evaluation !== 'object') return [];
    const deepeval = (evaluation as { deepeval?: Record<string, unknown> })
      .deepeval;
    if (!deepeval || typeof deepeval !== 'object') return [];
    const metrics = (deepeval as { metrics?: unknown }).metrics;
    if (!Array.isArray(metrics)) return [];
    return metrics.filter((m): m is string => typeof m === 'string');
  } catch {
    return [];
  }
}

export function generateStaticParams() {
  return loadAllAgents().map((agent) => ({ slug: agent.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const agent = findAgentBySlug(params.slug);
  if (!agent) {
    return { title: 'Eval drill-down not found · Grok Agent OS' };
  }
  return {
    title: `${agent.displayName} — DeepEval History · Grok Agent OS`,
    description: `Per-metric DeepEval run history for ${agent.displayName}.`,
  };
}

function tierAccent(tier: string): { bg: string; fg: string } {
  const t = tier.toUpperCase();
  if (t === 'A') return { bg: '#00E0D5', fg: '#0A0A0A' };
  if (t === 'B') return { bg: '#F4ECDA', fg: '#0A0A0A' };
  if (t === 'C') return { bg: '#FF1E70', fg: '#F4ECDA' };
  return { bg: '#0A0A0A', fg: '#F4ECDA' };
}

function trendArrow(delta: number | undefined): {
  symbol: string;
  color: string;
  label: string;
} {
  if (delta == null || Number.isNaN(delta)) {
    return { symbol: '·', color: '#888888', label: 'no trend data' };
  }
  if (delta > 0.005) {
    return {
      symbol: '▲',
      color: '#00E0D5',
      label: `up ${(delta * 100).toFixed(2)}pp over 7d`,
    };
  }
  if (delta < -0.005) {
    return {
      symbol: '▼',
      color: '#FF1E70',
      label: `down ${(Math.abs(delta) * 100).toFixed(2)}pp over 7d`,
    };
  }
  return { symbol: '►', color: '#0A0A0A', label: 'flat over 7d' };
}

export default function EvalDrillDownPage({ params }: PageProps) {
  const agent = findAgentBySlug(params.slug);
  if (!agent) {
    notFound();
  }

  const history = loadEvalHistory();
  const trustScores = loadTrustScores();
  const declaredFromManifest = loadDeclaredMetricsFromManifest(
    agent.manifestPath,
  );

  const trust = trustScores?.agents?.[agent.slug];
  const trustScore = trust?.score ?? null;
  const trustTier = trust?.tier ?? null;
  const tierStyle = trustTier ? tierAccent(trustTier) : null;

  // Empty-state path: history JSON missing entirely.
  if (!history) {
    return (
      <main>
        <p>
          <Link href="/eval/">← Back to dashboard</Link>
        </p>
        <h1 style={{ marginTop: 16 }}>{agent.displayName}</h1>
        <p className="tagline">{agent.tagline || agent.description}</p>
        <section
          className="banner"
          role="note"
          style={{
            background: '#F4ECDA',
            color: '#0A0A0A',
            border: '1px solid #0A0A0A',
            borderRadius: 6,
            padding: 16,
            margin: '20px 0',
          }}
        >
          The eval history file <code>docs/eval-history.json</code> was not
          found at build time. Run{' '}
          <code>python scripts/build-eval-history.py --seed</code> from the
          repo root, then rebuild the marketplace to populate this
          drill-down with demo data.
        </section>
        <Footer />
      </main>
    );
  }

  const entry: EvalAgentEntry = history.agents?.[agent.slug] ?? {};
  const runs: EvalRun[] = Array.isArray(entry.runs) ? entry.runs : [];
  const latestMetrics: Record<string, number> = entry.latest_metrics ?? {};
  const trend7d: Record<string, number> = entry.trend_7d ?? {};

  // Prefer the manifest-declared metric list; fall back to whatever the
  // history JSON saw, then to the keys present in the latest run.
  const declared: string[] =
    declaredFromManifest.length > 0
      ? declaredFromManifest
      : Array.isArray(entry.metrics_declared) && entry.metrics_declared.length > 0
      ? entry.metrics_declared
      : Object.keys(latestMetrics);

  const hasRuns = runs.length > 0;

  return (
    <main>
      <p>
        <Link href="/eval/">← Back to dashboard</Link>
      </p>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 10,
          marginTop: 16,
        }}
      >
        <span
          className="badge"
          style={{
            background: '#0A0A0A',
            color: '#F4ECDA',
            padding: '2px 10px',
            fontWeight: 600,
            letterSpacing: '0.04em',
          }}
        >
          {TIER_LABELS[agent.tier]}
        </span>
        {trustScore != null && tierStyle ? (
          <span
            className="badge"
            style={{
              background: tierStyle.bg,
              color: tierStyle.fg,
              padding: '2px 10px',
              fontWeight: 700,
              letterSpacing: '0.04em',
            }}
            title={`Trust score: ${trustScore} · Tier ${trustTier}`}
          >
            Trust {trustScore} · Tier {trustTier}
          </span>
        ) : null}
        <span style={{ color: '#888', fontSize: '0.9em' }}>
          {entry.kind ?? agent.kind} · {entry.category ?? agent.category}
        </span>
      </div>

      <h1 style={{ marginTop: 16 }}>{agent.displayName}</h1>
      <p className="tagline">{agent.tagline || agent.description}</p>

      <p>
        Manifest:{' '}
        <a
          href={agent.githubManifestUrl}
          target="_blank"
          rel="noreferrer noopener"
        >
          <code>{agent.manifestPath}</code>
        </a>
      </p>

      <h2 className="section">Latest-run scoreboard</h2>
      {hasRuns && Object.keys(latestMetrics).length > 0 ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns:
              'repeat(auto-fill, minmax(200px, 1fr))',
            gap: 12,
            margin: '12px 0 24px 0',
          }}
        >
          {Object.entries(latestMetrics).map(([metric, value]) => {
            const arrow = trendArrow(trend7d[metric]);
            return (
              <div
                key={metric}
                style={{
                  border: '1px solid #0A0A0A',
                  borderRadius: 6,
                  padding: 12,
                  background: '#F4ECDA',
                  color: '#0A0A0A',
                }}
              >
                <div
                  style={{
                    fontSize: '0.8em',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                  }}
                >
                  {metric}
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: 8,
                    marginTop: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: '1.6em',
                      fontWeight: 700,
                      fontFamily:
                        'JetBrains Mono, Consolas, monospace',
                    }}
                  >
                    {value.toFixed(3)}
                  </span>
                  <span
                    aria-label={arrow.label}
                    title={arrow.label}
                    style={{
                      color: arrow.color,
                      fontWeight: 700,
                    }}
                  >
                    {arrow.symbol}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <section
          style={{
            background: '#F4ECDA',
            color: '#0A0A0A',
            border: '1px solid #0A0A0A',
            borderRadius: 6,
            padding: 16,
            margin: '12px 0 24px 0',
          }}
        >
          No eval runs recorded yet. Run{' '}
          <code>python scripts/build-eval-history.py --seed</code> for demo
          data.
        </section>
      )}

      <h2 className="section">Run history</h2>
      <EvalTimeSeriesChart runs={runs} metrics={declared} />

      <h2 className="section">Declared DeepEval metrics</h2>
      {declared.length === 0 ? (
        <p style={{ color: '#888' }}>
          This manifest declares no <code>evaluation.deepeval.metrics</code>{' '}
          block yet.
        </p>
      ) : (
        <ul>
          {declared.map((m) => (
            <li key={m}>
              <code>{m}</code>
            </li>
          ))}
        </ul>
      )}

      <Footer />
    </main>
  );
}

function Footer() {
  return (
    <footer
      style={{
        marginTop: '48px',
        paddingTop: '20px',
        borderTop: '1px solid #0A0A0A',
        color: '#888888',
        fontSize: '0.9rem',
      }}
      aria-label="Built for xAI, X, Grok and the ecosystem community."
    >
      <p style={{ margin: '0 0 8px' }}>
        Sources:{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/scripts/build-eval-history.py"
          target="_blank"
          rel="noreferrer noopener"
        >
          scripts/build-eval-history.py
        </a>{' '}
        ·{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/docs/eval-history.json"
          target="_blank"
          rel="noreferrer noopener"
        >
          docs/eval-history.json
        </a>
      </p>
      <p style={{ margin: 0 }}>
        Built for xAI, X, Grok and the ecosystem community. ❤️
      </p>
    </footer>
  );
}
