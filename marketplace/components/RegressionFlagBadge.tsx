// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// RegressionFlagBadge — Client Component used by the per-slug eval
// dashboard to surface 7-day metric drift at a glance. Reads the
// `trend_7d` map (metric name -> delta in [-1..1]) and renders a small
// pill badge:
//   - cinnabar  if any metric delta < -threshold   (regression)
//   - teal      if any metric delta > +0.05        (improvement)
//   - parchment otherwise                          (stable)
// Hover tooltip lists the affected metrics + their signed deltas, and
// the aria-label encodes the full state for screen readers.
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

interface RegressionFlagBadgeProps {
  trend7d: Record<string, number>;
  threshold?: number;
}

interface BadgeState {
  variant: 'regression' | 'improvement' | 'stable';
  count: number;
  affected: Array<{ metric: string; delta: number }>;
  background: string;
  color: string;
  border: string;
  symbol: string;
  label: string;
  ariaLabel: string;
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? '+' : '';
  return `${sign}${delta.toFixed(3)}`;
}

export default function RegressionFlagBadge({
  trend7d,
  threshold = -0.05,
}: RegressionFlagBadgeProps) {
  const [tooltipOpen, setTooltipOpen] = useState(false);

  const state: BadgeState = useMemo(() => {
    const entries = Object.entries(trend7d ?? {});
    const regressions = entries
      .filter(([, delta]) => delta < threshold)
      .map(([metric, delta]) => ({ metric, delta }));
    const improvements = entries
      .filter(([, delta]) => delta > 0.05)
      .map(([metric, delta]) => ({ metric, delta }));

    if (regressions.length > 0) {
      const sorted = [...regressions].sort((a, b) => a.delta - b.delta);
      const noun = regressions.length === 1 ? 'regression' : 'regressions';
      return {
        variant: 'regression',
        count: regressions.length,
        affected: sorted,
        background: '#FF1E70',
        color: '#F4ECDA',
        border: '#FF1E70',
        symbol: '⚠',
        label: `${regressions.length} ${noun}`,
        ariaLabel: `${regressions.length} metric ${noun} below threshold ${threshold.toFixed(
          2,
        )}: ${sorted
          .map((r) => `${r.metric} ${formatDelta(r.delta)}`)
          .join(', ')}`,
      };
    }

    if (improvements.length > 0) {
      const sorted = [...improvements].sort((a, b) => b.delta - a.delta);
      const noun = improvements.length === 1 ? 'improvement' : 'improvements';
      return {
        variant: 'improvement',
        count: improvements.length,
        affected: sorted,
        background: '#00E0D5',
        color: '#0A0A0A',
        border: '#00E0D5',
        symbol: '▲',
        label: `${improvements.length} ${noun}`,
        ariaLabel: `${improvements.length} metric ${noun} above +0.05: ${sorted
          .map((r) => `${r.metric} ${formatDelta(r.delta)}`)
          .join(', ')}`,
      };
    }

    return {
      variant: 'stable',
      count: 0,
      affected: [],
      background: '#F4ECDA',
      color: '#0A0A0A',
      border: '#0A0A0A',
      symbol: '=',
      label: 'stable',
      ariaLabel:
        entries.length === 0
          ? 'No 7-day trend data available'
          : `All ${entries.length} metrics stable within ±0.05 over 7 days`,
    };
  }, [trend7d, threshold]);

  return (
    <span
      role="status"
      aria-label={state.ariaLabel}
      onMouseEnter={() => setTooltipOpen(true)}
      onMouseLeave={() => setTooltipOpen(false)}
      onFocus={() => setTooltipOpen(true)}
      onBlur={() => setTooltipOpen(false)}
      tabIndex={0}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 999,
        background: state.background,
        color: state.color,
        border: `1px solid ${state.border}`,
        fontSize: '0.78rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        lineHeight: 1.4,
        cursor: 'default',
        whiteSpace: 'nowrap',
      }}
    >
      <span aria-hidden="true">{state.symbol}</span>
      <span>{state.label}</span>
      {tooltipOpen && state.affected.length > 0 && (
        <span
          role="tooltip"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 20,
            background: '#0A0A0A',
            color: '#F4ECDA',
            border: `1px solid ${state.border}`,
            borderRadius: 4,
            padding: '8px 10px',
            fontSize: '0.78rem',
            fontWeight: 500,
            textTransform: 'none',
            letterSpacing: 'normal',
            minWidth: 200,
            maxWidth: 320,
            boxShadow: '0 4px 12px rgba(0,0,0,0.35)',
          }}
        >
          <strong
            style={{
              display: 'block',
              marginBottom: 4,
              color: state.background === '#FF1E70' ? '#FF1E70' : '#00E0D5',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              fontSize: '0.72rem',
            }}
          >
            {state.variant === 'regression'
              ? 'Affected metrics'
              : 'Improving metrics'}
          </strong>
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {state.affected.map((row) => (
              <li
                key={row.metric}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  fontFamily: 'var(--mono-stack, monospace)',
                  fontSize: '0.75rem',
                }}
              >
                <span>{row.metric}</span>
                <span
                  style={{
                    color:
                      row.delta < 0 ? '#FF1E70' : '#00E0D5',
                    fontWeight: 700,
                  }}
                >
                  {formatDelta(row.delta)}
                </span>
              </li>
            ))}
          </ul>
        </span>
      )}
    </span>
  );
}
