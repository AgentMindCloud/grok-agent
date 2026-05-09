// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Sortable + filterable Constitution Audit Log table. Client Component —
// receives the raw findings list and the by-manifest summary from the
// parent /audit-dashboard server route, then derives the visible rows
// via useMemo on every (filter, sort) change. Per-slug links point at
// the drill-down route owned by the sibling worker.
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5. Severity badges use those exact accents so
// the table matches the scoreboard cards in the parent page.

'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

interface AuditFinding {
  manifest_path: string;
  slug: string;
  category: string;
  check: string;
  severity: string;
  message: string;
  article: string;
}

interface AuditManifestEntry {
  manifest_path: string;
  category: string;
  kind: string;
  max_severity: string;
  has_errors: boolean;
  findings: Array<{
    check: string;
    severity: string;
    message: string;
    article: string;
  }>;
}

interface AuditLogTableProps {
  findings: AuditFinding[];
  byManifest: Record<string, AuditManifestEntry>;
}

type SortKey =
  | 'slug'
  | 'category'
  | 'check'
  | 'severity'
  | 'article'
  | 'message';
type SortDir = 'asc' | 'desc';

const SEVERITY_RANK: Record<string, number> = {
  error: 0,
  warn: 1,
  info: 2,
};

const SEVERITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all', label: 'All severities' },
  { value: 'error', label: 'Error only' },
  { value: 'warn', label: 'Warning only' },
  { value: 'info', label: 'Info only' },
];

function severityBadgeStyle(severity: string): React.CSSProperties {
  const normalised = severity.toLowerCase();
  if (normalised === 'error') {
    return {
      background: '#FF1E70',
      color: '#F4ECDA',
    };
  }
  if (normalised === 'warn' || normalised === 'warning') {
    return {
      background: '#F4ECDA',
      color: '#0A0A0A',
      border: '1px solid #0A0A0A',
    };
  }
  return {
    background: '#888888',
    color: '#F4ECDA',
  };
}

function truncate(input: string, max = 80): string {
  if (input.length <= max) return input;
  return `${input.slice(0, max - 1).trimEnd()}…`;
}

function buildMarkdownLine(f: AuditFinding): string {
  // Single-line markdown summary so a creator can paste a finding into
  // a GitHub issue, X reply, or PR description without reformatting.
  return `- \`${f.slug}\` [${f.severity}] **${f.check}** (${f.article}) — ${f.message} (${f.manifest_path})`;
}

export default function AuditLogTable({
  findings,
  byManifest,
}: AuditLogTableProps) {
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [checkFilter, setCheckFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('severity');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const categoryOptions = useMemo(() => {
    const seen = new Set<string>();
    findings.forEach((f) => seen.add(f.category));
    return ['all', ...Array.from(seen).sort((a, b) => a.localeCompare(b))];
  }, [findings]);

  const checkOptions = useMemo(() => {
    const seen = new Set<string>();
    findings.forEach((f) => seen.add(f.check));
    return ['all', ...Array.from(seen).sort((a, b) => a.localeCompare(b))];
  }, [findings]);

  const visible = useMemo(() => {
    const filtered = findings.filter((f) => {
      if (severityFilter !== 'all' && f.severity !== severityFilter) {
        return false;
      }
      if (categoryFilter !== 'all' && f.category !== categoryFilter) {
        return false;
      }
      if (checkFilter !== 'all' && f.check !== checkFilter) return false;
      return true;
    });

    const sorted = [...filtered].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'severity') {
        const ra = SEVERITY_RANK[a.severity] ?? 99;
        const rb = SEVERITY_RANK[b.severity] ?? 99;
        cmp = ra - rb;
      } else {
        const av = a[sortKey] ?? '';
        const bv = b[sortKey] ?? '';
        cmp = String(av).localeCompare(String(bv));
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return sorted;
  }, [findings, severityFilter, categoryFilter, checkFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return '↕';
    return sortDir === 'asc' ? '▲' : '▼';
  }

  function handleCopy(rowKey: string, finding: AuditFinding) {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return;
    navigator.clipboard.writeText(buildMarkdownLine(finding)).then(
      () => {
        setCopiedKey(rowKey);
        window.setTimeout(() => setCopiedKey(null), 1600);
      },
      () => setCopiedKey(null),
    );
  }

  const totalCount = findings.length;
  const visibleCount = visible.length;
  const manifestCount = Object.keys(byManifest).length;

  if (totalCount === 0) {
    return (
      <section
        aria-labelledby="audit-table"
        style={{ marginTop: '32px' }}
      >
        <h2 id="audit-table" className="section">
          Findings
        </h2>
        <p className="empty">
          Zero findings across {manifestCount} manifest(s). The repo is
          fully clean against the current Constitution version.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="audit-table" style={{ marginTop: '32px' }}>
      <h2 id="audit-table" className="section">
        Findings
      </h2>
      <p className="meta" aria-live="polite">
        Showing <strong>{visibleCount}</strong> of{' '}
        <strong>{totalCount}</strong> findings across{' '}
        <strong>{manifestCount}</strong> manifest(s).
      </p>

      <div
        className="browser-controls"
        role="group"
        aria-label="Audit log filters"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '12px',
        }}
      >
        <div>
          <label htmlFor="audit-severity">Severity</label>
          <select
            id="audit-severity"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            {SEVERITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="audit-category">Category</label>
          <select
            id="audit-category"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            {categoryOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt === 'all' ? 'All categories' : opt}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="audit-check">Check name</label>
          <select
            id="audit-check"
            value={checkFilter}
            onChange={(e) => setCheckFilter(e.target.value)}
          >
            {checkOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt === 'all' ? 'All checks' : opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div
        style={{
          marginTop: '16px',
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
              {(
                [
                  ['slug', 'Slug'],
                  ['category', 'Category'],
                  ['check', 'Check'],
                  ['severity', 'Severity'],
                  ['article', 'Article'],
                  ['message', 'Message'],
                ] as Array<[SortKey, string]>
              ).map(([key, label]) => (
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
              <th
                scope="col"
                style={{
                  textAlign: 'left',
                  padding: '10px 12px',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}
              >
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  style={{
                    padding: '24px',
                    textAlign: 'center',
                    color: 'var(--muted)',
                  }}
                >
                  No findings match the current filters.
                </td>
              </tr>
            ) : (
              visible.map((f, idx) => {
                const rowKey = `${f.manifest_path}::${f.check}::${idx}`;
                const isCopied = copiedKey === rowKey;
                return (
                  <tr
                    key={rowKey}
                    style={{
                      borderTop: '1px solid var(--rule)',
                      background:
                        idx % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.025)',
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
                      <Link href={`/audit-dashboard/${f.slug}/`}>
                        {f.slug}
                      </Link>
                    </td>
                    <td style={{ padding: '10px 12px' }}>{f.category}</td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontFamily: 'var(--mono-stack)',
                        fontSize: '0.85rem',
                      }}
                    >
                      {f.check}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 10px',
                          borderRadius: '999px',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                          ...severityBadgeStyle(f.severity),
                        }}
                      >
                        {f.severity}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontFamily: 'var(--mono-stack)',
                        fontSize: '0.85rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {f.article}
                    </td>
                    <td
                      style={{ padding: '10px 12px' }}
                      title={f.message}
                    >
                      {truncate(f.message, 80)}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <button
                        type="button"
                        className="button secondary"
                        style={{ fontSize: '0.8rem', padding: '4px 10px' }}
                        onClick={() => handleCopy(rowKey, f)}
                        aria-live="polite"
                      >
                        {isCopied ? '✓ Copied!' : 'Copy as markdown'}
                      </button>
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
