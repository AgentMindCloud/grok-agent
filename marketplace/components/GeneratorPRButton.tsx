// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// GeneratorPRButton — Client Component used by the AI manifest generator
// wizard to ship the previewed grok-agent.yaml v2.15 directly into a
// GitHub pull request via the new-file URL pattern:
//
//   https://github.com/<org>/<repo>/new/<branch>
//     ?filename=templates/<bucket>/<slug>/grok-agent.yaml
//     &value=<urlencoded yaml>
//
// GitHub's `new` route opens its in-browser file editor pre-filled with
// the manifest, then routes the contributor through the standard
// "propose change" flow — yielding a fully formed PR with zero CLI work.
// Every PR still goes through human review before merge; the button is
// strictly a draft entry point, never a one-click merge.
//
// Bucket derivation (CLAUDE.md §5 file tree):
//   super-agent                         → super-agents
//   finance-dashboard, alpha-engine,
//   creator-payout-optimizer,
//   vision-analyzer                     → finance
//   creator-template                    → creator
//   x-native                            → x-native
//   anything else                       → general
//
// Slug derivation:
//   1. Parse the YAML body for a top-level `name:` field via a small
//      regex (no js-yaml dep here — the wizard already validates the
//      manifest via ManifestPreview, so we only need the name token).
//   2. If the name is missing or unparseable, fall back to
//      `<kind>-draft-<unix-seconds>` so the URL is always well-formed.
//
// Brand palette (Spectral v1):
//   charcoal  #0A0A0A
//   cinnabar  #FF1E70
//   parchment #F4ECDA
//   teal      #00E0D5

'use client';

import { useMemo } from 'react';

interface GeneratorPRButtonProps {
  yaml: string;
  kind: string;
}

const REPO_BASE = 'https://github.com/AgentMindCloud/grok-agent/new/main';

const FINANCE_KINDS = new Set([
  'finance-dashboard',
  'alpha-engine',
  'creator-payout-optimizer',
  'vision-analyzer',
]);

function deriveBucket(kind: string): string {
  const k = (kind || '').trim().toLowerCase();
  if (k === 'super-agent') return 'super-agents';
  if (FINANCE_KINDS.has(k)) return 'finance';
  if (k === 'creator-template') return 'creator';
  if (k === 'x-native') return 'x-native';
  return 'general';
}

// Tiny YAML name extractor. Looks for a top-level (zero-indent) `name:`
// inside `metadata:`, falling back to any zero-indent `name:` line. We
// deliberately avoid pulling js-yaml here because ManifestPreview already
// owns parsing/validation, and this component must remain dependency-free.
function extractName(yaml: string): string | null {
  if (!yaml) return null;
  const lines = yaml.split('\n');

  // Pass 1: find a `metadata:` block, then the first `name:` inside it.
  let inMetadata = false;
  let metadataIndent = -1;
  for (const raw of lines) {
    const line = raw.replace(/\r$/, '');
    if (!line.trim() || line.trim().startsWith('#')) continue;

    const indent = line.length - line.trimStart().length;
    const stripped = line.trim();

    if (!inMetadata) {
      if (/^metadata\s*:\s*$/.test(stripped) && indent === 0) {
        inMetadata = true;
        metadataIndent = indent;
        continue;
      }
    } else {
      // Leaving metadata block when we hit a sibling key at <= its indent.
      if (indent <= metadataIndent && /^[A-Za-z_][\w.-]*\s*:/.test(stripped)) {
        inMetadata = false;
      } else {
        const m = stripped.match(/^name\s*:\s*(.+)$/);
        if (m) {
          return cleanScalar(m[1]);
        }
      }
    }
  }

  // Pass 2: any top-level `name:` line.
  for (const raw of lines) {
    const line = raw.replace(/\r$/, '');
    const stripped = line.trim();
    const m = stripped.match(/^name\s*:\s*(.+)$/);
    if (m) return cleanScalar(m[1]);
  }
  return null;
}

function cleanScalar(value: string): string | null {
  let v = value.trim();
  // Drop trailing inline comments.
  const hashIdx = findUnquotedHash(v);
  if (hashIdx >= 0) v = v.slice(0, hashIdx).trim();
  // Strip surrounding quotes.
  if (
    (v.startsWith('"') && v.endsWith('"')) ||
    (v.startsWith("'") && v.endsWith("'"))
  ) {
    v = v.slice(1, -1);
  }
  v = v.trim();
  return v || null;
}

function findUnquotedHash(s: string): number {
  let inSingle = false;
  let inDouble = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === "'" && !inDouble) inSingle = !inSingle;
    else if (ch === '"' && !inSingle) inDouble = !inDouble;
    else if (ch === '#' && !inSingle && !inDouble) return i;
  }
  return -1;
}

// Slug-safe subset of the manifest name. Mirrors the convention used by
// templates/<bucket>/<slug>/ folders elsewhere in the repo.
function sluggify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
}

function deriveSlug(yaml: string, kind: string): string {
  const name = extractName(yaml);
  if (name) {
    const slug = sluggify(name);
    if (slug) return slug;
  }
  const safeKind = sluggify(kind || 'agent') || 'agent';
  return `${safeKind}-draft-${Math.floor(Date.now() / 1000)}`;
}

// Quick parseability gate — empty YAML, or YAML that has no `:` lines at
// all, disables the button so we never open a junk PR draft.
function looksParseable(yaml: string): boolean {
  if (!yaml || !yaml.trim()) return false;
  const hasKey = yaml
    .split('\n')
    .some((l) => /^[\s-]*[A-Za-z_][\w.-]*\s*:/.test(l));
  return hasKey;
}

export default function GeneratorPRButton({ yaml, kind }: GeneratorPRButtonProps) {
  const parseable = useMemo(() => looksParseable(yaml), [yaml]);
  const bucket = useMemo(() => deriveBucket(kind), [kind]);
  const slug = useMemo(() => deriveSlug(yaml, kind), [yaml, kind]);

  const href = useMemo(() => {
    if (!parseable) return '#';
    const params = new URLSearchParams({
      filename: `templates/${bucket}/${slug}/grok-agent.yaml`,
      value: yaml,
    });
    return `${REPO_BASE}?${params.toString()}`;
  }, [parseable, bucket, slug, yaml]);

  const tooltip = parseable
    ? 'Opens GitHub in a new tab. Manifests need human review before merge.'
    : 'Add a parseable manifest above to enable this action.';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        marginTop: 16,
      }}
    >
      <a
        role="button"
        href={parseable ? href : undefined}
        target={parseable ? '_blank' : undefined}
        rel="noreferrer noopener"
        aria-disabled={!parseable}
        title={tooltip}
        onClick={(e) => {
          if (!parseable) e.preventDefault();
        }}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          background: parseable ? '#FF1E70' : '#888888',
          color: '#F4ECDA',
          border: `1px solid ${parseable ? '#FF1E70' : '#888888'}`,
          padding: '10px 18px',
          borderRadius: 4,
          fontWeight: 700,
          fontSize: '0.95em',
          textDecoration: 'none',
          letterSpacing: '0.02em',
          cursor: parseable ? 'pointer' : 'not-allowed',
          opacity: parseable ? 1 : 0.7,
          alignSelf: 'flex-start',
        }}
      >
        Submit as Pull Request
      </a>

      <div
        style={{
          fontSize: '0.8em',
          color: '#0A0A0A',
          opacity: 0.75,
          maxWidth: 520,
          lineHeight: 1.45,
        }}
      >
        <div>
          Target path:{' '}
          <code
            style={{
              background: '#0A0A0A',
              color: '#00E0D5',
              padding: '1px 6px',
              borderRadius: 3,
              fontSize: '0.95em',
            }}
          >
            templates/{bucket}/{slug}/grok-agent.yaml
          </code>
        </div>
        <div style={{ marginTop: 6, fontStyle: 'italic' }}>
          Beta. AI-generated manifests are starting points — not production-ready.
        </div>
      </div>
    </div>
  );
}
