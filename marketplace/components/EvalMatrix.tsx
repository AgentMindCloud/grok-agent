// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// EvalMatrix — Client Component for the eval-history dashboard.
// Renders an agent x metric heatmap grid backed by the JSON shape
// produced by `scripts/build-eval-history.py` (Agent 2.1's brief):
//
//   {
//     agents: {
//       <slug>: {
//         metrics_declared: string[],
//         runs: Array<{ ... }>,
//         latest_metrics: Record<metric, number>,    // 0..1
//         trend_7d: Record<metric, number>           // signed delta
//       }
//     }
//   }
//
// Cells are coloured by the latest_metrics value, overlay the numeric
// score, and mark a regression with a small down-arrow when trend_7d
// drops below -0.05 (or an up-arrow above +0.05). A filter chip shows
// only rows that contain at least one regression cell, and a sort
// dropdown switches between alphabetical / by-tier / by-worst-cell
// orderings. Pure CSS grid, zero new npm deps.
//
// Brand palette (Spectral v1):
//   charcoal  #0A0A0A
//   cinnabar  #FF1E70
//   parchment #F4ECDA
//   teal      #00E0D5
//   success   #00C896
//   warning   #FF6B35

'use client';

import { useMemo, useState } from 'react';
import type { Agent, AgentTier } from '../lib/types';
import { TIER_LABELS } from '../lib/types';

export interface AgentEvalHistory {
  metrics_declared: string[];
  runs?: unknown[];
  latest_metrics: Record<string, number>;
  trend_7d: Record<string, number>;
}

export interface EvalHistoryFile {
  agents: Record<string, AgentEvalHistory>;
}

interface EvalMatrixProps {
  agents: Agent[];
  history: EvalHistoryFile;
}

type SortMode = 'alphabetical' | 'by-tier' | 'by-worst-cell';

const REGRESSION_THRESHOLD = -0.05;
const IMPROVEMENT_THRESHOLD = 0.05;

const TIER_RANK: Record<AgentTier, number> = {
  flagship: 0,
  lighter: 1,
  'x-money': 2,
  creator: 3,
};

const TIER_BADGE_BG: Record<AgentTier, string> = {
  flagship: '#FF1E70',
  lighter: '#00E0D5',
  'x-money': '#00C896',
  creator: '#FF6B35',
};

const TIER_BADGE_FG: Record<AgentTier, string> = {
  flagship: '#F4ECDA',
  lighter: '#0A0A0A',
  'x-money': '#0A0A0A',
  creator: '#0A0A0A',
};

function cellColor(value: number | null): {
  background: string;
  color: string;
} {
  if (value === null || Number.isNaN(value)) {
    return { background: '#0A0A0A', color: '#888888' };
  }
  if (value >= 0.85) return { background: '#FF1E70', color: '#F4ECDA' };
  if (value >= 0.7) return { background: '#00E0D5', color: '#0A0A0A' };
  if (value >= 0.5) return { background: '#F4ECDA', color: '#0A0A0A' };
  return { background: '#0A0A0A', color: '#F4ECDA' };
}

function trendArrow(delta: number | null): {
  symbol: string;
  color: string;
  label: string;
} | null {
  if (delta === null || Number.isNaN(delta)) return null;
  if (delta < REGRESSION_THRESHOLD) {
    return {
      symbol: '▼',
      color: '#FF1E70',
      label: `regression ${delta.toFixed(3)}`,
    };
  }
  if (delta > IMPROVEMENT_THRESHOLD) {
    return {
      symbol: '▲',
      color: '#00C896',
      label: `improvement +${delta.toFixed(3)}`,
    };
  }
  return null;
}

function formatScore(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '—';
  return value.toFixed(2);
}

function formatDelta(delta: number | null): string {
  if (delta === null || Number.isNaN(delta)) return 'no trend';
  const sign = delta > 0 ? '+' : '';
  return `${sign}${delta.toFixed(3)}`;
}

interface MatrixRow {
  agent: Agent;
  history: AgentEvalHistory | null;
  worstCellScore: number;
  regressionCount: number;
}

export default function EvalMatrix({ agents, history }: EvalMatrixProps) {
  const [showOnlyRegressions, setShowOnlyRegressions] = useState(false);
  const [sortMode, setSortMode] = useState<SortMode>('by-tier');
  const [hoveredCell, setHoveredCell] = useState<string | null>(null);

  const historyAgents = history?.agents ?? {};

  const metricColumns = useMemo(() => {
    const seen = new Set<string>();
    Object.values(historyAgents).forEach((entry) => {
      (entry?.metrics_declared ?? []).forEach((m) => seen.add(m));
      Object.keys(entry?.latest_metrics ?? {}).forEach((m) => seen.add(m));
    });
    return Array.from(seen).sort((a, b) => a.localeCompare(b));
  }, [historyAgents]);

  const rows: MatrixRow[] = useMemo(() => {
    return agents.map((agent) => {
      const entry = historyAgents[agent.slug] ?? null;
      const latest = entry?.latest_metrics ?? {};
      const trend = entry?.trend_7d ?? {};
      let worst = Number.POSITIVE_INFINITY;
      let regressionCount = 0;
      for (const metric of metricColumns) {
        const value = latest[metric];
        if (typeof value === 'number' && !Number.isNaN(value)) {
          if (value < worst) worst = value;
        }
        const delta = trend[metric];
        if (
          typeof delta === 'number' &&
          !Number.isNaN(delta) &&
          delta < REGRESSION_THRESHOLD
        ) {
          regressionCount += 1;
        }
      }
      return {
        agent,
        history: entry,
        worstCellScore: Number.isFinite(worst) ? worst : 1,
        regressionCount,
      };
    });
  }, [agents, historyAgents, metricColumns]);

  const visibleRows = useMemo(() => {
    let filtered = rows;
    if (showOnlyRegressions) {
      filtered = filtered.filter((r) => r.regressionCount > 0);
    }
    const sorted = [...filtered].sort((a, b) => {
      if (sortMode === 'alphabetical') {
        return a.agent.slug.localeCompare(b.agent.slug);
      }
      if (sortMode === 'by-worst-cell') {
        return a.worstCellScore - b.worstCellScore;
      }
      const ta = TIER_RANK[a.agent.tier] ?? 99;
      const tb = TIER_RANK[b.agent.tier] ?? 99;
      if (ta !== tb) return ta - tb;
      return a.agent.slug.localeCompare(b.agent.slug);
    });
    return sorted;
  }, [rows, showOnlyRegressions, sortMode]);

  const totalRegressions = useMemo(
    () => rows.reduce((acc, r) => acc + r.regressionCount, 0),
    [rows],
  );

  if (Object.keys(historyAgents).length === 0 || metricColumns.length === 0) {
    return (
      <section
        aria-labelledby="eval-matrix"
        style={{
          padding: 24,
          border: '1px dashed #0A0A0A',
          borderRadius: 6,
          background: '#F4ECDA',
          color: '#0A0A0A',
        }}
      >
        <h2 id="eval-matrix" className="section" style={{ marginTop: 0 }}>
          Eval matrix
        </h2>
        <p>
          No metric data yet — run{' '}
          <code
            style={{
              background: '#0A0A0A',
              color: '#00E0D5',
              padding: '2px 8px',
              borderRadius: 3,
            }}
          >
            python scripts/build-eval-history.py --seed
          </code>{' '}
          to populate <code>docs/eval-history.json</code>.
        </p>
      </section>
    );
  }

  // Layout: first column is the row header (slug + tier badge), then one
  // column per metric. Use auto for the header and minmax(72px, 1fr) for
  // every metric column so the grid stays responsive but readable.
  const gridTemplateColumns = `minmax(220px, 1fr) repeat(${metricColumns.length}, minmax(72px, 1fr))`;

  return (
    <section aria-labelledby="eval-matrix" style={{ marginTop: 24 }}>
      <h2 id="eval-matrix" className="section">
        Eval matrix
      </h2>
      <p className="meta" aria-live="polite">
        Showing <strong>{visibleRows.length}</strong> of{' '}
        <strong>{rows.length}</strong> agents across{' '}
        <strong>{metricColumns.length}</strong> metric(s).{' '}
        <strong>{totalRegressions}</strong> regression cell(s) detected
        (delta {REGRESSION_THRESHOLD.toFixed(2)} over 7 days).
      </p>

      <div
        role="group"
        aria-label="Eval matrix filters"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <button
          type="button"
          onClick={() => setShowOnlyRegressions((v) => !v)}
          aria-pressed={showOnlyRegressions}
          style={{
            background: showOnlyRegressions ? '#FF1E70' : '#F4ECDA',
            color: showOnlyRegressions ? '#F4ECDA' : '#0A0A0A',
            border: '1px solid #0A0A0A',
            borderRadius: 999,
            padding: '4px 12px',
            fontSize: '0.85rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          {showOnlyRegressions ? '✓ ' : ''}Show only regressions
        </button>

        <label
          htmlFor="eval-matrix-sort"
          style={{ fontSize: '0.85rem', color: '#0A0A0A' }}
        >
          Sort by{' '}
          <select
            id="eval-matrix-sort"
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as SortMode)}
            style={{
              marginLeft: 6,
              padding: '4px 8px',
              border: '1px solid #0A0A0A',
              borderRadius: 4,
              background: '#F4ECDA',
              color: '#0A0A0A',
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            <option value="by-tier">Tier (flagship first)</option>
            <option value="alphabetical">Slug (alphabetical)</option>
            <option value="by-worst-cell">Worst cell score</option>
          </select>
        </label>
      </div>

      <div
        role="table"
        aria-label="Agent by metric heatmap"
        style={{
          display: 'grid',
          gridTemplateColumns,
          gap: 4,
          background: '#0A0A0A',
          padding: 4,
          borderRadius: 6,
          overflowX: 'auto',
        }}
      >
        <div
          role="columnheader"
          style={{
            background: '#0A0A0A',
            color: '#F4ECDA',
            padding: '8px 12px',
            fontWeight: 700,
            fontSize: '0.8rem',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Agent
        </div>
        {metricColumns.map((metric) => (
          <div
            key={`head-${metric}`}
            role="columnheader"
            title={metric}
            style={{
              background: '#0A0A0A',
              color: '#F4ECDA',
              padding: '8px 6px',
              fontWeight: 700,
              fontSize: '0.72rem',
              textTransform: 'uppercase',
              letterSpacing: '0.03em',
              textAlign: 'center',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {metric}
          </div>
        ))}

        {visibleRows.length === 0 ? (
          <div
            role="cell"
            style={{
              gridColumn: `1 / span ${metricColumns.length + 1}`,
              padding: 24,
              textAlign: 'center',
              color: '#888888',
              background: '#0A0A0A',
            }}
          >
            No agents match the current filter.
          </div>
        ) : (
          visibleRows.map((row) => {
            const tier = row.agent.tier;
            const tierBg = TIER_BADGE_BG[tier] ?? '#888888';
            const tierFg = TIER_BADGE_FG[tier] ?? '#F4ECDA';
            return (
              <FragmentRow
                key={row.agent.slug}
                row={row}
                metricColumns={metricColumns}
                tierBg={tierBg}
                tierFg={tierFg}
                hoveredCell={hoveredCell}
                onHover={setHoveredCell}
              />
            );
          })
        )}
      </div>

      <p
        className="meta"
        style={{ marginTop: 12, fontSize: '0.78rem', color: '#888' }}
      >
        Cell colours: cinnabar &ge; 0.85, teal &ge; 0.70, parchment &ge; 0.50,
        charcoal &lt; 0.50. Down-arrow flags 7-day delta below{' '}
        {REGRESSION_THRESHOLD.toFixed(2)}; up-arrow flags delta above +
        {IMPROVEMENT_THRESHOLD.toFixed(2)}.
      </p>
    </section>
  );
}

interface FragmentRowProps {
  row: MatrixRow;
  metricColumns: string[];
  tierBg: string;
  tierFg: string;
  hoveredCell: string | null;
  onHover: (key: string | null) => void;
}

function FragmentRow({
  row,
  metricColumns,
  tierBg,
  tierFg,
  hoveredCell,
  onHover,
}: FragmentRowProps) {
  const latest = row.history?.latest_metrics ?? {};
  const trend = row.history?.trend_7d ?? {};
  return (
    <>
      <div
        role="rowheader"
        style={{
          background: '#F4ECDA',
          color: '#0A0A0A',
          padding: '8px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          minWidth: 0,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--mono-stack, monospace)',
            fontWeight: 700,
            fontSize: '0.85rem',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={row.agent.slug}
        >
          {row.agent.slug}
        </span>
        <span
          style={{
            display: 'inline-block',
            padding: '1px 8px',
            background: tierBg,
            color: tierFg,
            border: '1px solid #0A0A0A',
            borderRadius: 999,
            fontSize: '0.66rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            alignSelf: 'flex-start',
          }}
        >
          {TIER_LABELS[row.agent.tier] ?? row.agent.tier}
        </span>
      </div>
      {metricColumns.map((metric) => {
        const rawValue = latest[metric];
        const value =
          typeof rawValue === 'number' && !Number.isNaN(rawValue)
            ? rawValue
            : null;
        const rawDelta = trend[metric];
        const delta =
          typeof rawDelta === 'number' && !Number.isNaN(rawDelta)
            ? rawDelta
            : null;
        const colors = cellColor(value);
        const arrow = trendArrow(delta);
        const cellKey = `${row.agent.slug}::${metric}`;
        const isHovered = hoveredCell === cellKey;
        const tooltipId = `tip-${row.agent.slug}-${metric}`.replace(
          /[^a-zA-Z0-9_-]/g,
          '_',
        );
        return (
          <div
            key={cellKey}
            role="cell"
            tabIndex={0}
            aria-describedby={isHovered ? tooltipId : undefined}
            aria-label={`${row.agent.slug} ${metric} score ${formatScore(
              value,
            )} trend ${formatDelta(delta)}`}
            onMouseEnter={() => onHover(cellKey)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(cellKey)}
            onBlur={() => onHover(null)}
            style={{
              position: 'relative',
              background: colors.background,
              color: colors.color,
              padding: '10px 6px',
              minHeight: 56,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              gap: 2,
              fontFamily: 'var(--mono-stack, monospace)',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: 'default',
              outline: isHovered ? '2px solid #00E0D5' : 'none',
              outlineOffset: -2,
            }}
          >
            <span>{formatScore(value)}</span>
            {arrow && (
              <span
                aria-hidden="true"
                style={{
                  fontSize: '0.85rem',
                  color: arrow.color,
                  textShadow: '0 0 2px rgba(0,0,0,0.6)',
                }}
              >
                {arrow.symbol}
              </span>
            )}
            {isHovered && (
              <span
                role="tooltip"
                id={tooltipId}
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 4px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  background: '#0A0A0A',
                  color: '#F4ECDA',
                  border: '1px solid #00E0D5',
                  borderRadius: 4,
                  padding: '6px 10px',
                  fontSize: '0.72rem',
                  fontWeight: 500,
                  fontFamily: 'var(--mono-stack, monospace)',
                  whiteSpace: 'nowrap',
                  zIndex: 10,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.45)',
                }}
              >
                <div>
                  <strong style={{ color: '#00E0D5' }}>
                    {row.agent.slug}
                  </strong>
                </div>
                <div>metric: {metric}</div>
                <div>score: {formatScore(value)}</div>
                <div>
                  7d trend:{' '}
                  <span
                    style={{
                      color: arrow
                        ? arrow.color
                        : '#F4ECDA',
                    }}
                  >
                    {formatDelta(delta)}
                    {arrow ? ` ${arrow.symbol}` : ''}
                  </span>
                </div>
              </span>
            )}
          </div>
        );
      })}
    </>
  );
}
