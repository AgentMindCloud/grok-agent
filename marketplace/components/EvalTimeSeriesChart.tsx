// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// EvalTimeSeriesChart — Client Component used by the per-slug eval
// drill-down route (/eval/<slug>/). Renders a pure-SVG, zero-dependency
// time-series chart of DeepEval metric scores over time, with:
//   - one polyline per metric (color-cycled through Spectral v1)
//   - hoverable data points with a tooltip showing run_id + metric + value
//   - a click-to-toggle legend
//   - dashed strokes for the 5th+ metric (color-blind safe redundancy)
//   - graceful empty-state when runs.length === 0
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5. No npm chart dependency by design.

'use client';

import { useMemo, useState } from 'react';

export interface EvalRun {
  ts: string;
  run_id?: string;
  metrics: Record<string, number>;
}

export interface EvalTimeSeriesChartProps {
  runs: EvalRun[];
  metrics: string[];
}

interface PointTooltip {
  metric: string;
  runId: string;
  ts: string;
  value: number;
  cx: number;
  cy: number;
}

const SPECTRAL_BASE_HUES: string[] = [
  '#FF1E70', // cinnabar
  '#00E0D5', // teal
  '#0A0A0A', // charcoal
  '#A06CFF', // accent violet (distinct from base palette but readable)
];

// Stroke dash patterns paired with the color cycle: the 5th+ metric falls
// back to a dashed stroke + hash-derived hue so colour-blind viewers can
// still tell series apart.
const DASH_PATTERNS: string[] = ['', '', '', '', '6 4', '2 4', '8 2 2 2'];

function hashHue(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) {
    h = (h * 31 + name.charCodeAt(i)) >>> 0;
  }
  // Distribute deterministically around the wheel, skipping ranges that
  // collide with cinnabar / teal already used in the base cycle.
  const hue = (h % 280) + 30; // 30..309 — avoids the cinnabar red band
  return `hsl(${hue} 70% 45%)`;
}

function colorFor(metric: string, idx: number): string {
  if (idx < SPECTRAL_BASE_HUES.length) return SPECTRAL_BASE_HUES[idx];
  return hashHue(metric);
}

function dashFor(idx: number): string {
  if (idx < DASH_PATTERNS.length) return DASH_PATTERNS[idx];
  return '4 3';
}

function safeMetricValue(run: EvalRun, metric: string): number | null {
  const v = run.metrics?.[metric];
  if (typeof v !== 'number' || Number.isNaN(v)) return null;
  // Clamp to [0, 1] for charting, but the tooltip shows the raw value.
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

function formatTs(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toISOString().replace('T', ' ').slice(0, 16) + 'Z';
  } catch {
    return iso;
  }
}

const VIEW_W = 720;
const VIEW_H = 280;
const PAD_L = 44;
const PAD_R = 16;
const PAD_T = 18;
const PAD_B = 32;

export default function EvalTimeSeriesChart({
  runs,
  metrics,
}: EvalTimeSeriesChartProps) {
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [tooltip, setTooltip] = useState<PointTooltip | null>(null);

  const series = useMemo(() => {
    return metrics.map((metric, idx) => ({
      metric,
      color: colorFor(metric, idx),
      dash: dashFor(idx),
      idx,
    }));
  }, [metrics]);

  if (!runs || runs.length === 0) {
    return (
      <section
        aria-label="Eval time-series chart"
        style={{
          background: '#F4ECDA',
          color: '#0A0A0A',
          border: '1px solid #0A0A0A',
          borderRadius: 6,
          padding: 32,
          margin: '12px 0 24px 0',
          textAlign: 'center',
          fontWeight: 600,
        }}
      >
        No runs yet. Once <code>scripts/build-eval-history.py</code>{' '}
        records a run, this chart will populate automatically.
      </section>
    );
  }

  // Sort runs by timestamp so the polyline reads left-to-right in time.
  const sortedRuns = [...runs].sort((a, b) => {
    const ta = new Date(a.ts).getTime();
    const tb = new Date(b.ts).getTime();
    return (Number.isNaN(ta) ? 0 : ta) - (Number.isNaN(tb) ? 0 : tb);
  });

  const innerW = VIEW_W - PAD_L - PAD_R;
  const innerH = VIEW_H - PAD_T - PAD_B;
  const n = sortedRuns.length;
  const xFor = (i: number): number =>
    n <= 1 ? PAD_L + innerW / 2 : PAD_L + (i / (n - 1)) * innerW;
  const yFor = (v: number): number => PAD_T + (1 - v) * innerH;

  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  function toggle(metric: string) {
    setHidden((prev) => ({ ...prev, [metric]: !prev[metric] }));
  }

  return (
    <section
      aria-label="Eval time-series chart"
      style={{ position: 'relative', margin: '12px 0 24px 0' }}
    >
      {/* Legend — click swatches to toggle visibility */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 8,
          fontSize: '0.9em',
        }}
      >
        {series.map(({ metric, color, dash }) => {
          const isHidden = !!hidden[metric];
          return (
            <button
              key={metric}
              type="button"
              onClick={() => toggle(metric)}
              aria-pressed={!isHidden}
              title={
                isHidden
                  ? `Show ${metric}`
                  : `Hide ${metric}`
              }
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: 'transparent',
                border: '1px solid #0A0A0A',
                borderRadius: 4,
                padding: '2px 8px',
                cursor: 'pointer',
                color: '#0A0A0A',
                opacity: isHidden ? 0.45 : 1,
                fontFamily: 'inherit',
              }}
            >
              <svg width="22" height="10" aria-hidden="true">
                <line
                  x1="0"
                  y1="5"
                  x2="22"
                  y2="5"
                  stroke={color}
                  strokeWidth="3"
                  strokeDasharray={dash || undefined}
                />
              </svg>
              <span style={{ fontWeight: 600 }}>{metric}</span>
            </button>
          );
        })}
      </div>

      <div style={{ position: 'relative', width: '100%' }}>
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          width="100%"
          height="auto"
          role="img"
          aria-label={`Time-series chart of ${metrics.length} metric(s) across ${n} run(s)`}
          style={{
            border: '1px solid #0A0A0A',
            borderRadius: 6,
            background: '#F4ECDA',
            display: 'block',
          }}
        >
          {/* Y axis grid + labels */}
          {yTicks.map((t) => (
            <g key={`y-${t}`}>
              <line
                x1={PAD_L}
                x2={VIEW_W - PAD_R}
                y1={yFor(t)}
                y2={yFor(t)}
                stroke="#0A0A0A"
                strokeOpacity={t === 0 ? 0.6 : 0.12}
                strokeWidth={t === 0 ? 1 : 1}
              />
              <text
                x={PAD_L - 6}
                y={yFor(t) + 4}
                fontSize="10"
                textAnchor="end"
                fill="#0A0A0A"
                fontFamily="JetBrains Mono, Consolas, monospace"
              >
                {t.toFixed(2)}
              </text>
            </g>
          ))}

          {/* X axis labels: first, middle, last (avoid clutter) */}
          {(() => {
            const labelIdxs = n <= 1
              ? [0]
              : n === 2
              ? [0, n - 1]
              : [0, Math.floor((n - 1) / 2), n - 1];
            return labelIdxs.map((i) => (
              <text
                key={`x-${i}`}
                x={xFor(i)}
                y={VIEW_H - PAD_B + 16}
                fontSize="10"
                textAnchor="middle"
                fill="#0A0A0A"
                fontFamily="JetBrains Mono, Consolas, monospace"
              >
                {formatTs(sortedRuns[i].ts)}
              </text>
            ));
          })()}

          {/* Polylines + points per metric */}
          {series.map(({ metric, color, dash }) => {
            if (hidden[metric]) return null;
            const pts: Array<{ x: number; y: number; v: number; i: number }> = [];
            sortedRuns.forEach((run, i) => {
              const v = safeMetricValue(run, metric);
              if (v == null) return;
              pts.push({ x: xFor(i), y: yFor(v), v, i });
            });
            if (pts.length === 0) return null;
            const d = pts
              .map((p, idx) => `${idx === 0 ? 'M' : 'L'}${p.x},${p.y}`)
              .join(' ');
            return (
              <g key={metric}>
                <path
                  d={d}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  strokeDasharray={dash || undefined}
                />
                {pts.map((p) => {
                  const run = sortedRuns[p.i];
                  const rawV = run.metrics?.[metric];
                  const runId = run.run_id ?? `run-${p.i + 1}`;
                  return (
                    <circle
                      key={`${metric}-${p.i}`}
                      cx={p.x}
                      cy={p.y}
                      r={4}
                      fill={color}
                      stroke="#0A0A0A"
                      strokeWidth="1"
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={() =>
                        setTooltip({
                          metric,
                          runId,
                          ts: run.ts,
                          value: typeof rawV === 'number' ? rawV : p.v,
                          cx: p.x,
                          cy: p.y,
                        })
                      }
                      onMouseLeave={() => setTooltip(null)}
                      onFocus={() =>
                        setTooltip({
                          metric,
                          runId,
                          ts: run.ts,
                          value: typeof rawV === 'number' ? rawV : p.v,
                          cx: p.x,
                          cy: p.y,
                        })
                      }
                      onBlur={() => setTooltip(null)}
                      tabIndex={0}
                      aria-label={`${metric} ${runId} value ${(typeof rawV === 'number' ? rawV : p.v).toFixed(3)}`}
                    >
                      <title>
                        {`${metric} · ${runId} · ${formatTs(run.ts)} · ${(typeof rawV === 'number' ? rawV : p.v).toFixed(3)}`}
                      </title>
                    </circle>
                  );
                })}
              </g>
            );
          })}
        </svg>

        {tooltip ? (
          <div
            role="tooltip"
            style={{
              position: 'absolute',
              left: `calc(${(tooltip.cx / VIEW_W) * 100}% + 6px)`,
              top: `calc(${(tooltip.cy / VIEW_H) * 100}% - 8px)`,
              transform: 'translate(0, -100%)',
              background: '#0A0A0A',
              color: '#F4ECDA',
              padding: '6px 10px',
              borderRadius: 4,
              fontSize: '0.8em',
              pointerEvents: 'none',
              maxWidth: 260,
              fontFamily: 'JetBrains Mono, Consolas, monospace',
              boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
              whiteSpace: 'nowrap',
            }}
          >
            <div style={{ fontWeight: 700 }}>{tooltip.metric}</div>
            <div>{tooltip.runId}</div>
            <div>{formatTs(tooltip.ts)}</div>
            <div>value: {tooltip.value.toFixed(3)}</div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
