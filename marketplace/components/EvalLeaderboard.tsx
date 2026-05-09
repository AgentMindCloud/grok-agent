// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Sortable + filterable Eval Trust-Score Leaderboard. Client Component —
// receives the full agent roster (from docs/agent-trust-scores.json) and
// the optional eval-history map (from docs/eval-history.json, written by
// scripts/build-eval-history.py) from the parent /eval server route, then
// derives visible rows via useMemo on every (filter, sort) change.
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5. Tier badges colour-coded per the brand spec
// (A=cinnabar with a crown glyph, B=cinnabar, C=parchment, D=charcoal).
// Per-row Slug links point at the per-slug detail route owned by the
// sibling worker, mounted at /eval/<slug>/.

'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

export interface LeaderboardAgent {
  slug: string;
  category: string;
  kind: string;
  score: number;
  tier: string;
  manifest_path: string;
}

export interface LeaderboardHistoryRun {
  // ISO 8601 timestamp of the run; used as the sparkline x-axis ordering.
  run_at: string;
  // Aggregated trust-score (or eval pass-rate) at the time of the run,
  // in the same 0–100 range as the leaderboard column.
  score: number;
}

export interface LeaderboardHistoryEntry {
  runs: LeaderboardHistoryRun[];
}

export type LeaderboardHistory = Record<string, LeaderboardHistoryEntry>;

interface EvalLeaderboardProps {
  agents: LeaderboardAgent[];
  history: LeaderboardHistory;
}

type SortKey =
  | 'rank'
  | 'slug'
  | 'tier'
  | 'score'
  | 'runs'
  | 'lastRun'
  | 'trend';
type SortDir = 'asc' | 'desc';

interface CategoryChip {
  value: string;
  label: string;
}

const CATEGORY_CHIPS: CategoryChip[] = [
  { value: 'all', label: 'All' },
  { value: 'super-agents', label: 'Super Agents' },
  { value: 'finance', label: 'X Money Tools' },
  { value: 'creator', label: 'Creator Templates' },
  { value: 'general', label: 'General' },
  { value: 'x-native', label: 'X-native' },
];

const TIER_RANK: Record<string, number> = {
  A: 0,
  B: 1,
  C: 2,
  D: 3,
};

interface TierStyle {
  background: string;
  color: string;
  border?: string;
  glyph?: string;
}

function tierStyle(tier: string): TierStyle {
  const t = tier.toUpperCase();
  if (t === 'A') {
    return {
      background: '#FF1E70',
      color: '#F4ECDA',
      glyph: '♛',
    };
  }
  if (t === 'B') {
    return {
      background: '#FF1E70',
      color: '#F4ECDA',
    };
  }
  if (t === 'C') {
    return {
      background: '#F4ECDA',
      color: '#0A0A0A',
      border: '1px solid #0A0A0A',
    };
  }
  return {
    background: '#0A0A0A',
    color: '#F4ECDA',
  };
}

function formatTimestampShort(iso: string | null): string {
  if (!iso) return '—';
  try {
    const date = new Date(iso);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    }).format(date);
  } catch {
    return iso;
  }
}

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
}

function Sparkline({
  values,
  width = 60,
  height = 16,
  stroke = '#FF1E70',
}: SparklineProps) {
  if (values.length === 0) {
    return (
      <span
        aria-label="No trend data"
        style={{ color: 'var(--muted)', fontSize: '0.8rem' }}
      >
        —
      </span>
    );
  }
  if (values.length === 1) {
    // Single point — render a flat dash so the column never collapses.
    const cy = height / 2;
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Single sample at ${values[0].toFixed(0)}`}
      >
        <line
          x1={2}
          y1={cy}
          x2={width - 2}
          y2={cy}
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
        />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = (width - 4) / (values.length - 1);
  const points = values
    .map((v, i) => {
      const x = 2 + i * stepX;
      const norm = (v - min) / range;
      // Invert Y because SVG origin is top-left.
      const y = height - 2 - norm * (height - 4);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`7-day trend, ${values.length} samples, range ${min.toFixed(0)}–${max.toFixed(0)}`}
    >
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

interface RowDerived {
  agent: LeaderboardAgent;
  runCount: number;
  lastRunIso: string | null;
  lastRunMs: number;
  sparkValues: number[];
  trendDelta: number;
}

function lastSevenDayRuns(
  runs: LeaderboardHistoryRun[],
): LeaderboardHistoryRun[] {
  if (runs.length === 0) return [];
  const sorted = [...runs].sort(
    (a, b) => new Date(a.run_at).getTime() - new Date(b.run_at).getTime(),
  );
  const newestMs = new Date(sorted[sorted.length - 1].run_at).getTime();
  const cutoffMs = newestMs - 7 * 24 * 60 * 60 * 1000;
  const window = sorted.filter(
    (r) => new Date(r.run_at).getTime() >= cutoffMs,
  );
  return window.length > 0 ? window : sorted.slice(-1);
}

export default function EvalLeaderboard({
  agents,
  history,
}: EvalLeaderboardProps) {
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const derived = useMemo<RowDerived[]>(() => {
    return agents.map((agent) => {
      const entry = history[agent.slug];
      const runs = entry?.runs ?? [];
      const window = lastSevenDayRuns(runs);
      const sparkValues = window.map((r) => r.score);
      const lastRun =
        runs.length > 0
          ? runs.reduce((acc, r) => (r.run_at > acc ? r.run_at : acc), runs[0].run_at)
          : null;
      const trendDelta =
        sparkValues.length >= 2
          ? sparkValues[sparkValues.length - 1] - sparkValues[0]
          : 0;
      return {
        agent,
        runCount: runs.length,
        lastRunIso: lastRun,
        lastRunMs: lastRun ? new Date(lastRun).getTime() : 0,
        sparkValues,
        trendDelta,
      };
    });
  }, [agents, history]);

  const filtered = useMemo<RowDerived[]>(() => {
    if (categoryFilter === 'all') return derived;
    return derived.filter((row) => row.agent.category === categoryFilter);
  }, [derived, categoryFilter]);

  // Stable rank baseline: descending score across the full roster, with
  // slug as the deterministic tiebreaker so the rank does not jitter
  // when two agents share a score.
  const rankMap = useMemo<Map<string, number>>(() => {
    const ordered = [...derived].sort((a, b) => {
      if (b.agent.score !== a.agent.score) {
        return b.agent.score - a.agent.score;
      }
      return a.agent.slug.localeCompare(b.agent.slug);
    });
    const map = new Map<string, number>();
    ordered.forEach((row, i) => map.set(row.agent.slug, i + 1));
    return map;
  }, [derived]);

  const visible = useMemo<RowDerived[]>(() => {
    const sorted = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'rank':
          cmp =
            (rankMap.get(a.agent.slug) ?? 0) -
            (rankMap.get(b.agent.slug) ?? 0);
          break;
        case 'slug':
          cmp = a.agent.slug.localeCompare(b.agent.slug);
          break;
        case 'tier': {
          const ra = TIER_RANK[a.agent.tier.toUpperCase()] ?? 99;
          const rb = TIER_RANK[b.agent.tier.toUpperCase()] ?? 99;
          cmp = ra - rb;
          break;
        }
        case 'score':
          cmp = a.agent.score - b.agent.score;
          break;
        case 'runs':
          cmp = a.runCount - b.runCount;
          break;
        case 'lastRun':
          cmp = a.lastRunMs - b.lastRunMs;
          break;
        case 'trend':
          cmp = a.trendDelta - b.trendDelta;
          break;
        default:
          cmp = 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [filtered, sortKey, sortDir, rankMap]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      // Numeric columns default to descending so the leader sits on top.
      const numericDefaults: SortKey[] = ['score', 'runs', 'lastRun', 'trend'];
      setSortDir(numericDefaults.includes(key) ? 'desc' : 'asc');
    }
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return '↕';
    return sortDir === 'asc' ? '▲' : '▼';
  }

  const totalCount = derived.length;
  const visibleCount = visible.length;

  if (totalCount === 0) {
    return (
      <section
        aria-labelledby="eval-leaderboard"
        style={{ marginTop: '32px' }}
      >
        <h2 id="eval-leaderboard" className="section">
          Trust-score leaderboard
        </h2>
        <p className="empty">
          No agents found in <code>docs/agent-trust-scores.json</code>.
          Run the trust-score builder to populate the leaderboard.
        </p>
      </section>
    );
  }

  const columns: Array<[SortKey, string]> = [
    ['rank', 'Rank'],
    ['slug', 'Agent'],
    ['tier', 'Tier'],
    ['score', 'Trust Score'],
    ['runs', 'Eval Runs'],
    ['lastRun', 'Last Run'],
    ['trend', '7-day Trend'],
  ];

  return (
    <section
      aria-labelledby="eval-leaderboard"
      style={{ marginTop: '32px' }}
    >
      <h2 id="eval-leaderboard" className="section">
        Trust-score leaderboard
      </h2>
      <p className="meta" aria-live="polite">
        Showing <strong>{visibleCount}</strong> of{' '}
        <strong>{totalCount}</strong> agents.
      </p>

      <div
        role="group"
        aria-label="Filter by category"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          margin: '8px 0 16px',
        }}
      >
        {CATEGORY_CHIPS.map((chip) => {
          const isActive = chip.value === categoryFilter;
          return (
            <button
              key={chip.value}
              type="button"
              onClick={() => setCategoryFilter(chip.value)}
              aria-pressed={isActive}
              style={{
                padding: '6px 14px',
                borderRadius: '999px',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
                border: isActive
                  ? '1px solid #FF1E70'
                  : '1px solid var(--rule)',
                background: isActive ? '#FF1E70' : 'var(--parchment)',
                color: isActive ? '#F4ECDA' : '#0A0A0A',
              }}
            >
              {chip.label}
            </button>
          );
        })}
      </div>

      <div
        style={{
          overflowX: 'auto',
          border: '1px solid var(--rule)',
          borderRadius: 'var(--radius)',
          background: 'var(--parchment-dark)',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.92rem',
          }}
        >
          <thead>
            <tr style={{ background: '#0A0A0A', color: '#F4ECDA' }}>
              {columns.map(([key, label]) => (
                <th
                  key={key}
                  scope="col"
                  style={{
                    textAlign: 'left',
                    padding: '10px 12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    userSelect: 'none',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => toggleSort(key)}
                    aria-label={`Sort by ${label}`}
                    aria-sort={
                      sortKey === key
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                    style={{
                      background: 'transparent',
                      border: 0,
                      color: 'inherit',
                      padding: 0,
                      font: 'inherit',
                      cursor: 'pointer',
                    }}
                  >
                    {label}{' '}
                    <span aria-hidden="true" style={{ opacity: 0.7 }}>
                      {sortIndicator(key)}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  style={{
                    padding: '24px',
                    textAlign: 'center',
                    color: 'var(--muted)',
                  }}
                >
                  No agents match the current filter.
                </td>
              </tr>
            ) : (
              visible.map((row, idx) => {
                const tier = row.agent.tier.toUpperCase();
                const ts = tierStyle(tier);
                const rank = rankMap.get(row.agent.slug) ?? 0;
                return (
                  <tr
                    key={row.agent.slug}
                    style={{
                      borderTop: '1px solid var(--rule)',
                      background:
                        idx % 2 === 0
                          ? 'transparent'
                          : 'rgba(0,0,0,0.025)',
                    }}
                  >
                    <td
                      style={{
                        padding: '10px 12px',
                        fontFamily: 'var(--mono-stack)',
                        fontSize: '0.86rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      #{rank}
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontFamily: 'var(--mono-stack)',
                        fontSize: '0.86rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <Link href={`/eval/${row.agent.slug}/`}>
                        {row.agent.slug}
                      </Link>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '2px 10px',
                          borderRadius: '999px',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                          background: ts.background,
                          color: ts.color,
                          border: ts.border,
                        }}
                        aria-label={`Tier ${tier}`}
                      >
                        {ts.glyph ? (
                          <span aria-hidden="true">{ts.glyph}</span>
                        ) : null}
                        {tier}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontFamily: 'var(--mono-stack)',
                        fontWeight: 700,
                      }}
                    >
                      {row.agent.score}
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontFamily: 'var(--mono-stack)',
                        fontSize: '0.86rem',
                      }}
                    >
                      {row.runCount}
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontSize: '0.86rem',
                        whiteSpace: 'nowrap',
                      }}
                      title={row.lastRunIso ?? 'No runs recorded'}
                    >
                      {formatTimestampShort(row.lastRunIso)}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <Sparkline values={row.sparkValues} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
