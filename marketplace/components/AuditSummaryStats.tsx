// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// AuditSummaryStats — Client Component for the per-slug Constitution
// Audit Log drill-down route. Renders a compact stats panel:
//   - "X of Y checks passed" headline.
//   - Severity counters (errors / warnings / infos) coloured per Spectral
//     v1 brand palette.
//   - Per-Constitution-article breakdown rendered as plain CSS bars
//     (zero new npm deps; one <div> per article).
//
// Brand palette (Spectral v1):
//   charcoal  #0A0A0A
//   cinnabar  #FF1E70
//   parchment #F4ECDA
//   teal      #00E0D5

'use client';

import type { AuditFinding } from './AuditFindingCard';

interface AuditSummaryStatsProps {
  findings: AuditFinding[];
  totalChecks: number;
}

function severityColor(severity: string): string {
  const s = severity.toLowerCase();
  if (s === 'error' || s === 'err') return '#FF1E70';
  if (s === 'warn' || s === 'warning') return '#F4ECDA';
  return '#888888';
}

function severityTextColor(severity: string): string {
  const s = severity.toLowerCase();
  if (s === 'warn' || s === 'warning') return '#0A0A0A';
  return '#F4ECDA';
}

export default function AuditSummaryStats({
  findings,
  totalChecks,
}: AuditSummaryStatsProps) {
  const uniqueChecks = new Set(findings.map((f) => f.check));
  const failed = uniqueChecks.size;
  const passed = Math.max(0, totalChecks - failed);

  const errorCount = findings.filter(
    (f) => ['error', 'err'].includes(f.severity.toLowerCase()),
  ).length;
  const warnCount = findings.filter(
    (f) => ['warn', 'warning'].includes(f.severity.toLowerCase()),
  ).length;
  const infoCount = findings.filter(
    (f) => !['error', 'err', 'warn', 'warning'].includes(f.severity.toLowerCase()),
  ).length;

  // Per-article breakdown: count findings per article string.
  const perArticle = new Map<string, number>();
  for (const f of findings) {
    const key = f.article || 'unspecified';
    perArticle.set(key, (perArticle.get(key) ?? 0) + 1);
  }
  const articleEntries = Array.from(perArticle.entries()).sort(
    (a, b) => b[1] - a[1],
  );
  const maxArticleCount = articleEntries.reduce(
    (acc, [, count]) => Math.max(acc, count),
    1,
  );

  const passRate = totalChecks > 0 ? Math.round((passed / totalChecks) * 100) : 100;

  return (
    <section
      style={{
        background: '#F4ECDA',
        color: '#0A0A0A',
        border: '1px solid #0A0A0A',
        borderRadius: 6,
        padding: 20,
        margin: '16px 0 24px 0',
      }}
    >
      <h2 className="section" style={{ marginTop: 0, color: '#0A0A0A' }}>
        Audit summary
      </h2>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 16,
          marginBottom: 20,
        }}
      >
        <div>
          <div
            style={{
              fontSize: '2.4em',
              fontWeight: 800,
              lineHeight: 1.1,
              color: failed === 0 ? '#00E0D5' : '#FF1E70',
            }}
          >
            {passed} <span style={{ color: '#0A0A0A', fontWeight: 500 }}>of</span> {totalChecks}
          </div>
          <div style={{ fontSize: '0.95em', color: '#0A0A0A' }}>
            checks passed ({passRate}%)
          </div>
        </div>

        <div>
          <div
            style={{
              fontSize: '2.4em',
              fontWeight: 800,
              lineHeight: 1.1,
              color: '#FF1E70',
            }}
          >
            {errorCount}
          </div>
          <div style={{ fontSize: '0.95em' }}>errors</div>
        </div>

        <div>
          <div
            style={{
              fontSize: '2.4em',
              fontWeight: 800,
              lineHeight: 1.1,
              color: '#0A0A0A',
            }}
          >
            {warnCount}
          </div>
          <div style={{ fontSize: '0.95em' }}>warnings</div>
        </div>

        <div>
          <div
            style={{
              fontSize: '2.4em',
              fontWeight: 800,
              lineHeight: 1.1,
              color: '#888888',
            }}
          >
            {infoCount}
          </div>
          <div style={{ fontSize: '0.95em' }}>infos</div>
        </div>
      </div>

      {articleEntries.length > 0 && (
        <div>
          <h3
            style={{
              fontSize: '1em',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 8,
              color: '#0A0A0A',
            }}
          >
            Per-article breakdown
          </h3>
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            {articleEntries.map(([article, count]) => {
              const widthPct = Math.round((count / maxArticleCount) * 100);
              const dominantSev = findings
                .filter((f) => (f.article || 'unspecified') === article)
                .reduce((acc, f) => {
                  const s = f.severity.toLowerCase();
                  if (s === 'error' || s === 'err') return 'error';
                  if (acc === 'error') return acc;
                  if (s === 'warn' || s === 'warning') return 'warn';
                  return acc;
                }, 'info');
              const barColor = severityColor(dominantSev);
              const barTextColor = severityTextColor(dominantSev);
              return (
                <li
                  key={article}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 1fr 40px',
                    gap: 8,
                    alignItems: 'center',
                  }}
                >
                  <span
                    style={{
                      fontSize: '0.9em',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={article}
                  >
                    {article}
                  </span>
                  <div
                    style={{
                      background: '#0A0A0A',
                      borderRadius: 3,
                      height: 18,
                      position: 'relative',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${widthPct}%`,
                        background: barColor,
                        color: barTextColor,
                        height: '100%',
                        paddingLeft: 6,
                        fontSize: '0.75em',
                        lineHeight: '18px',
                        fontWeight: 700,
                      }}
                    >
                      {widthPct >= 20 ? `${count}` : ''}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '0.85em',
                      textAlign: 'right',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {count}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
