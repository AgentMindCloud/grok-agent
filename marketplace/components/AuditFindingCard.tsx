// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// AuditFindingCard — Client Component used by the per-slug Constitution
// Audit Log drill-down route. Renders one Finding (severity badge, check
// id, article ref, message block, copy-as-markdown button, and a deep
// link to the relevant Constitution article on GitHub).
//
// Brand palette (Spectral v1):
//   charcoal  #0A0A0A
//   cinnabar  #FF1E70
//   parchment #F4ECDA
//   teal      #00E0D5

'use client';

import { useState } from 'react';

export interface AuditFinding {
  check: string;
  severity: string;
  message: string;
  article: string;
}

interface AuditFindingCardProps {
  finding: AuditFinding;
  slug?: string;
}

const CONSTITUTION_BASE =
  'https://github.com/AgentMindCloud/grok-agent/blob/main/safety/constitution.md';

// Map a free-form article string (e.g. "Const. Art. I", "Article II", "I",
// "II.consent") to the corresponding GitHub markdown anchor on
// safety/constitution.md.
const ARTICLE_TITLES: Record<string, string> = {
  I: 'article-i-universal-rules',
  II: 'article-ii-consent-gates',
  III: 'article-iii-hard-refusals',
  IV: 'article-iv-provenance-truth',
  V: 'article-v-disclaimers',
  VI: 'article-vi-cost-limits-human-in-the-loop',
  VII: 'article-vii-local-first-privacy-first',
  VIII: 'article-viii-enforcement',
  IX: 'article-ix-amendment-versioning',
};

function deriveArticleAnchor(article: string): string {
  if (!article) return '';
  // Pull the first roman-numeral run (I-IX) from the string.
  const match = article.toUpperCase().match(/\b(IX|IV|V?I{0,3})\b/);
  if (match && ARTICLE_TITLES[match[1]]) {
    return ARTICLE_TITLES[match[1]];
  }
  // Fallback: kebab-case the whole article string.
  return article
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function severityStyle(severity: string): {
  background: string;
  color: string;
  border: string;
} {
  const s = severity.toLowerCase();
  if (s === 'error' || s === 'err') {
    return { background: '#FF1E70', color: '#F4ECDA', border: '#FF1E70' };
  }
  if (s === 'warn' || s === 'warning') {
    return { background: '#F4ECDA', color: '#0A0A0A', border: '#0A0A0A' };
  }
  return { background: '#888888', color: '#F4ECDA', border: '#888888' };
}

export default function AuditFindingCard({
  finding,
  slug,
}: AuditFindingCardProps) {
  const [copied, setCopied] = useState(false);
  const sevStyle = severityStyle(finding.severity);
  const anchor = deriveArticleAnchor(finding.article);
  const articleHref = anchor ? `${CONSTITUTION_BASE}#${anchor}` : CONSTITUTION_BASE;

  function handleCopy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return;
    const slugPart = slug ? `[${slug}] ` : '';
    const summary = `${slugPart}**${finding.severity.toUpperCase()}** \`${finding.check}\` (${finding.article}) — ${finding.message}`;
    navigator.clipboard.writeText(summary).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      },
      () => setCopied(false),
    );
  }

  return (
    <article
      className="card"
      style={{
        borderColor: sevStyle.border,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 8,
        }}
      >
        <span
          className="badge"
          style={{
            background: sevStyle.background,
            color: sevStyle.color,
            borderColor: sevStyle.border,
            padding: '2px 10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {finding.severity}
        </span>
        <code
          style={{
            background: '#0A0A0A',
            color: '#00E0D5',
            padding: '2px 8px',
            borderRadius: 3,
            fontSize: '0.9em',
          }}
        >
          {finding.check}
        </code>
        <span style={{ color: '#888', fontSize: '0.85em' }}>
          {finding.article}
        </span>
      </div>

      <pre
        className="manifest"
        style={{
          background: '#0A0A0A',
          color: '#F4ECDA',
          padding: 12,
          borderRadius: 4,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          marginTop: 4,
        }}
      >
        <code>{finding.message}</code>
      </pre>

      <div className="actions" style={{ marginTop: 12 }}>
        <button type="button" className="button" onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy as markdown'}
        </button>
        <a
          className="button secondary"
          href={articleHref}
          target="_blank"
          rel="noreferrer noopener"
        >
          View Constitution article
        </a>
      </div>
    </article>
  );
}
