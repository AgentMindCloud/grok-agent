// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Per-slug Constitution Audit Log drill-down route. Server Component.
// Reads docs/audit-log.json + docs/agent-trust-scores.json at build time
// (via fs.readFileSync) and renders, for one agent slug:
//   - a header with displayName, tier badge, trust score number, manifest
//     GitHub link;
//   - a <AuditSummaryStats> panel (errors / warnings / infos + per-article
//     breakdown bar chart);
//   - a list of <AuditFindingCard> cards, one per finding.
// Mirrors the generateStaticParams pattern from
// marketplace/app/agents/[slug]/page.tsx so the static export pre-bakes
// one drill-down page per catalogued agent.
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5.

import fs from 'node:fs';
import path from 'node:path';
import Link from 'next/link';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { findAgentBySlug, loadAllAgents } from '../../../lib/manifests';
import { TIER_LABELS } from '../../../lib/types';
import AuditFindingCard, {
  type AuditFinding,
} from '../../../components/AuditFindingCard';
import AuditSummaryStats from '../../../components/AuditSummaryStats';

interface PageProps {
  params: { slug: string };
}

interface AuditManifestEntry {
  manifest_path: string;
  category: string;
  kind: string;
  max_severity: string;
  has_errors: boolean;
  findings: AuditFinding[];
}

interface AuditLog {
  computed_at?: string;
  scanner_version?: string;
  constitution_version?: string;
  manifest_count?: number;
  checks_per_manifest?: number;
  by_manifest: Record<string, AuditManifestEntry>;
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

const AUDIT_LOG_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'audit-log.json',
);

const TRUST_SCORES_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'agent-trust-scores.json',
);

const DEFAULT_TOTAL_CHECKS = 34;

function loadAuditLog(): AuditLog | null {
  try {
    const raw = fs.readFileSync(AUDIT_LOG_PATH, 'utf-8');
    return JSON.parse(raw) as AuditLog;
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

export function generateStaticParams() {
  return loadAllAgents().map((agent) => ({ slug: agent.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const agent = findAgentBySlug(params.slug);
  if (!agent) {
    return { title: 'Audit drill-down not found · Grok Agent OS' };
  }
  return {
    title: `${agent.displayName} — Constitution Audit · Grok Agent OS`,
    description: `Per-finding Constitution Audit Log drill-down for ${agent.displayName}.`,
  };
}

function tierAccent(tier: string): { bg: string; fg: string } {
  const t = tier.toUpperCase();
  if (t === 'A') return { bg: '#00E0D5', fg: '#0A0A0A' };
  if (t === 'B') return { bg: '#F4ECDA', fg: '#0A0A0A' };
  if (t === 'C') return { bg: '#FF1E70', fg: '#F4ECDA' };
  return { bg: '#0A0A0A', fg: '#F4ECDA' };
}

export default function AuditDrillDownPage({ params }: PageProps) {
  const agent = findAgentBySlug(params.slug);
  if (!agent) {
    notFound();
  }

  const auditLog = loadAuditLog();
  const trustScores = loadTrustScores();

  // Empty-state path: the audit log is missing (Agent 3.1 has not run yet
  // or the file failed to deserialise).
  if (!auditLog) {
    return (
      <main>
        <p>
          <Link href="/audit-dashboard/">← Back to dashboard</Link>
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
          The audit log file <code>docs/audit-log.json</code> was not
          found at build time. Run{' '}
          <code>python scripts/build-audit-log.py</code> from the repo
          root, then rebuild the marketplace to populate this drill-down.
        </section>
        <Footer />
      </main>
    );
  }

  const entry = auditLog.by_manifest?.[agent.slug];
  const agentFindings: AuditFinding[] = entry?.findings ?? [];
  const totalChecks =
    auditLog.checks_per_manifest && auditLog.checks_per_manifest > 0
      ? auditLog.checks_per_manifest
      : DEFAULT_TOTAL_CHECKS;

  const trust = trustScores?.agents?.[agent.slug];
  const trustScore = trust?.score ?? null;
  const trustTier = trust?.tier ?? null;
  const tierStyle = trustTier ? tierAccent(trustTier) : null;

  return (
    <main>
      <p>
        <Link href="/audit-dashboard/">← Back to dashboard</Link>
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
          {entry?.kind ?? agent.kind} · {entry?.category ?? agent.category}
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
          <code>{entry?.manifest_path ?? agent.manifestPath}</code>
        </a>
      </p>

      <AuditSummaryStats
        findings={agentFindings}
        totalChecks={totalChecks}
      />

      <h2 className="section">Findings</h2>
      {agentFindings.length === 0 ? (
        <section
          style={{
            background: '#00E0D5',
            color: '#0A0A0A',
            border: '1px solid #0A0A0A',
            borderRadius: 6,
            padding: 16,
            margin: '12px 0 24px 0',
            fontWeight: 600,
          }}
        >
          Clean slate — zero Constitution findings against this manifest.
          All {totalChecks} checks passed.
        </section>
      ) : (
        <div>
          {agentFindings.map((finding, idx) => (
            <AuditFindingCard
              key={`${finding.check}-${idx}`}
              finding={finding}
              slug={agent.slug}
            />
          ))}
        </div>
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
        Built for xAI, X, Grok and the ecosystem community. ❤️
      </p>
    </footer>
  );
}
