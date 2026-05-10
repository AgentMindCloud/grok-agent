// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Constitution Audit Log dashboard. Server Component — reads
// docs/audit-log.json (produced by scripts/build-audit-log.py) at build
// time and renders a hero + scoreboard + sortable findings table.
// Falls back to a friendly empty-state when the JSON is missing so a
// fresh clone (or a build that runs before the audit script) still ships
// a valid static page.
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5. Per-slug drill-down routes are owned by the
// sibling worker and rendered under /audit-dashboard/<slug>/.

import fs from 'node:fs';
import path from 'node:path';
import Link from 'next/link';
import AuditLogTable from '../../components/AuditLogTable';

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

interface AuditLog {
  computed_at: string;
  scanner_version: string;
  constitution_version: string;
  manifest_count: number;
  summary: {
    total_findings: number;
    by_severity: { error: number; warn: number; info: number };
    by_article: Record<string, number>;
    by_check: Record<string, number>;
    manifests_clean: number;
    manifests_with_findings: number;
  };
  by_manifest: Record<string, AuditManifestEntry>;
  findings: AuditFinding[];
}

const AUDIT_LOG_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'audit-log.json',
);

function loadAuditLog(): AuditLog | null {
  try {
    const raw = fs.readFileSync(AUDIT_LOG_PATH, 'utf-8');
    return JSON.parse(raw) as AuditLog;
  } catch {
    return null;
  }
}

function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(date);
  } catch {
    return iso;
  }
}

interface ScoreCardProps {
  label: string;
  value: number;
  accent: string;
  textOnAccent?: string;
  hint?: string;
}

function ScoreCard({ label, value, accent, textOnAccent, hint }: ScoreCardProps) {
  return (
    <div
      style={{
        background: 'var(--parchment)',
        border: '1px solid var(--rule)',
        borderRadius: 'var(--radius)',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        minWidth: 0,
      }}
    >
      <span
        style={{
          fontSize: '0.78rem',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--muted)',
        }}
      >
        {label}
      </span>
      <span
        style={{
          background: accent,
          color: textOnAccent ?? '#F4ECDA',
          alignSelf: 'flex-start',
          padding: '2px 12px',
          borderRadius: 'var(--radius)',
          fontSize: '1.6rem',
          fontWeight: 700,
          lineHeight: 1.15,
          fontFamily: 'var(--mono-stack)',
        }}
      >
        {value.toLocaleString('en-US')}
      </span>
      {hint ? (
        <span style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>{hint}</span>
      ) : null}
    </div>
  );
}

function EmptyState() {
  return (
    <main>
      <section className="hero">
        <h1>Constitution Audit Log</h1>
        <p className="tagline">
          The audit log file <code>docs/audit-log.json</code> was not
          found at build time. The dashboard renders once the audit
          script has been executed against the manifests in this repo.
        </p>
        <div className="banner" role="note">
          Run{' '}
          <code>python scripts/build-audit-log.py</code>{' '}
          from the repo root to generate the log, then rebuild the
          marketplace.
        </div>
      </section>
      <section>
        <h2 className="section">What this page will show</h2>
        <p>
          A scoreboard of every Article-keyed Constitution finding
          across every <code>grok-agent.yaml</code> in the repository,
          a sortable + filterable findings table, and a drill-down link
          per slug. The data layer is the same scanner the CLI uses on
          install, so what you see here is exactly what end users see
          when they run <code>grok install this</code>.
        </p>
      </section>
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
        borderTop: '1px solid var(--rule)',
        color: 'var(--muted)',
        fontSize: '0.9rem',
      }}
      aria-label="Built for xAI, X, Grok and the ecosystem community. ❤️"
    >
      <p style={{ margin: '0 0 8px' }}>
        Sources:{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/safety/scanner.py"
          target="_blank"
          rel="noreferrer noopener"
        >
          safety/scanner.py
        </a>{' '}
        ·{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/safety/constitution.md"
          target="_blank"
          rel="noreferrer noopener"
        >
          safety/constitution.md
        </a>
      </p>
      <p style={{ margin: 0 }}>
        Click any slug in the table to open a per-manifest drill-down
        with every finding grouped by Article. Built for xAI, X, Grok
        and the ecosystem community. ❤️
      </p>
    </footer>
  );
}

export default function AuditDashboardPage() {
  const auditLog = loadAuditLog();

  if (!auditLog) {
    return <EmptyState />;
  }

  const { summary } = auditLog;
  const lastUpdated = formatTimestamp(auditLog.computed_at);

  return (
    <main>
      <section className="hero">
        <h1>Constitution Audit Log</h1>
        <p className="tagline">
          Every Article-keyed Constitution finding across{' '}
          <strong>{auditLog.manifest_count}</strong>{' '}
          <code>grok-agent.yaml</code> manifests. Generated by{' '}
          <code>safety/scanner.py</code> v{auditLog.scanner_version}{' '}
          against Constitution v{auditLog.constitution_version}.
        </p>
        <p className="meta">
          Last updated <strong>{lastUpdated}</strong>
        </p>

        <div
          className="scoreboard"
          role="group"
          aria-label="Audit scoreboard"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '14px',
            margin: '20px 0 8px',
          }}
        >
          <ScoreCard
            label="Total findings"
            value={summary.total_findings}
            accent="#0A0A0A"
            textOnAccent="#F4ECDA"
            hint={`${summary.manifests_with_findings} manifest(s) flagged`}
          />
          <ScoreCard
            label="Errors"
            value={summary.by_severity.error}
            accent="#FF1E70"
            textOnAccent="#F4ECDA"
            hint="Block install"
          />
          <ScoreCard
            label="Warnings"
            value={summary.by_severity.warn}
            accent="#F4ECDA"
            textOnAccent="#0A0A0A"
            hint="Surface but allow install"
          />
          <ScoreCard
            label="Manifests clean"
            value={summary.manifests_clean}
            accent="#00E0D5"
            textOnAccent="#0A0A0A"
            hint="Zero findings"
          />
        </div>
      </section>

      <AuditLogTable
        findings={auditLog.findings}
        byManifest={auditLog.by_manifest}
      />

      <Footer />
    </main>
  );
}
