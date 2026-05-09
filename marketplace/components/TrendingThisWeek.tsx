// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Trending-this-week section. Server Component — reads
// marketplace/data/install-counts.json at build time and renders the top
// five agents by install count alongside the catalogue. The counts are
// SEED DATA today (see install-counts.json `_note`); production swaps in
// an analytics-layer rollup. The component degrades to "no data" if the
// JSON is missing so a fresh clone still builds.

import fs from 'node:fs';
import path from 'node:path';
import Link from 'next/link';
import type { Agent } from '../lib/types';
import { TIER_LABELS } from '../lib/types';

interface InstallCountsPayload {
  _note?: string;
  computed_at?: string;
  source?: string;
  counts?: Record<string, number>;
}

const COUNTS_PATH = path.resolve(
  process.cwd(),
  'data',
  'install-counts.json',
);

function loadCounts(): Record<string, number> {
  try {
    const raw = fs.readFileSync(COUNTS_PATH, 'utf-8');
    const parsed = JSON.parse(raw) as InstallCountsPayload;
    return parsed.counts ?? {};
  } catch {
    return {};
  }
}

function formatCount(n: number): string {
  // Compact display so a 4-digit count still fits the small chip card.
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

interface TrendingThisWeekProps {
  agents: Agent[];
}

export default function TrendingThisWeek({ agents }: TrendingThisWeekProps) {
  const counts = loadCounts();
  const ranked = agents
    .filter((agent) => counts[agent.slug] != null)
    .map((agent) => ({ agent, count: counts[agent.slug] }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  if (ranked.length === 0) {
    // Build still succeeds with no install-counts.json on disk.
    return null;
  }

  return (
    <section
      aria-labelledby="trending"
      className="trending-section"
      style={{ margin: '24px 0 36px' }}
    >
      <h2 id="trending" className="section">
        Trending this week
      </h2>
      <p className="meta">
        Top 5 agents by install hits in the last 7 days. Counts are seed
        data today — production wires this to the analytics layer behind
        the <code>/api/install/&lt;slug&gt;</code> redirect. See the
        marketplace README section &ldquo;Install counter API&rdquo; for
        the deployment path.
      </p>
      <ol
        className="trending-list"
        style={{
          listStyle: 'none',
          padding: 0,
          margin: '12px 0 0',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '12px',
        }}
      >
        {ranked.map(({ agent, count }, index) => (
          <li key={agent.slug} className="card" style={{ padding: '14px' }}>
            <span className="badge">{TIER_LABELS[agent.tier]}</span>
            <h3 style={{ margin: '6px 0 4px', fontSize: '1rem' }}>
              <span aria-hidden="true" style={{ opacity: 0.6 }}>
                #{index + 1}
              </span>{' '}
              {agent.displayName}
            </h3>
            <p className="meta" style={{ margin: 0 }}>
              <strong>{formatCount(count)}</strong> installs
            </p>
            <div className="actions" style={{ marginTop: '10px' }}>
              <Link
                href={`/agents/${agent.slug}/`}
                className="button secondary"
              >
                View agent
              </Link>
              <a
                className="button"
                href={`/grok-agent/api/install/${agent.slug}/`}
              >
                Install
              </a>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
