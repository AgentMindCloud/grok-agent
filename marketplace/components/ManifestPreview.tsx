// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// ManifestPreview — Client Component used by the AI manifest generator
// wizard to preview the generated grok-agent.yaml v2.15 document. The
// component:
//
//   1. Renders the YAML in a fenced <pre><code> block with lightweight
//      CSS-class colorization for keys vs strings vs numbers vs booleans
//      vs comments. No syntax-highlighting library is bundled — the
//      tokenizer is a small inline regex pipeline so the marketplace
//      build stays dependency-free.
//   2. Lazily loads Ajv 8 (JSON Schema 2020-12) and js-yaml 4 from
//      esm.sh on mount, mirroring the docs SchemaValidator.vue pattern,
//      then validates the parsed YAML against the canonical v2.15
//      schema fetched from the GitHub raw URL.
//
//      Schema source choice (documented for reviewers):
//        We fetch the schema from
//          https://raw.githubusercontent.com/AgentMindCloud/grok-agent/main/spec/v2.15/schema.json
//        rather than bundling the schema inside the marketplace app or
//        relying on a marketplace-served copy. This keeps the marketplace
//        build deps at zero and guarantees the preview validates against
//        the same schema that the CLI uses. The fallback is a minimal
//        inline schema (name + version + kind only) so the preview still
//        renders a useful status if the network blocks the fetch.
//   3. Surfaces a status panel below the YAML: green "valid" when the
//      schema passes, red error list when it fails, and yellow soft-rule
//      warnings (provenance.append_only missing, finance kind without
//      not_financial_advice, super-agent without constitution block,
//      missing metadata.tagline).
//   4. Exposes "Copy YAML" (clipboard, mirrors InstallButton) and
//      "Download .yaml" (Blob + createObjectURL) actions.
//
// Brand palette (Spectral v1):
//   charcoal  #0A0A0A
//   cinnabar  #FF1E70
//   parchment #F4ECDA
//   teal      #00E0D5

'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

interface ManifestPreviewProps {
  yaml: string;
}

interface SchemaError {
  path: string;
  message: string;
}

type Status = 'loading' | 'valid' | 'invalid' | 'parse-error' | 'idle';

const SCHEMA_URL =
  'https://raw.githubusercontent.com/AgentMindCloud/grok-agent/main/spec/v2.15/schema.json';

const AJV_CDN = 'https://esm.sh/ajv@8.17.1/dist/2020.js';
const YAML_CDN = 'https://esm.sh/js-yaml@4.1.0';

// Minimal fallback schema used only when the network fetch fails. Keeps
// the preview useful offline by validating the three load-bearing fields.
const FALLBACK_SCHEMA = {
  type: 'object',
  required: ['version', 'kind', 'metadata'],
  properties: {
    version: { type: ['number', 'string'] },
    kind: { type: 'string' },
    metadata: {
      type: 'object',
      required: ['name'],
      properties: {
        name: { type: 'string' },
        slug: { type: 'string' },
        description: { type: 'string' },
        tagline: { type: 'string' },
        license: { type: 'string' },
      },
    },
  },
};

const FINANCE_KINDS = new Set([
  'finance-dashboard',
  'alpha-engine',
  'creator-payout-optimizer',
  'vision-analyzer',
  'finance-tool',
]);

// ---- tokenizer (zero-dep YAML colorizer) -----------------------------------
//
// We do not parse YAML for highlighting — a line-level regex pipeline is
// sufficient for the keys/strings/numbers/booleans/comments split that the
// preview needs. Block scalars (`|`, `>`) are treated as plain strings.

interface Token {
  text: string;
  cls: string;
}

function tokenizeLine(line: string): Token[] {
  const out: Token[] = [];
  // Comment splits the line — everything from `#` to EOL is a comment if
  // not inside a quoted string. We do a light scan for the first un-quoted #.
  let inSingle = false;
  let inDouble = false;
  let commentAt = -1;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === "'" && !inDouble) inSingle = !inSingle;
    else if (ch === '"' && !inSingle) inDouble = !inDouble;
    else if (ch === '#' && !inSingle && !inDouble) {
      commentAt = i;
      break;
    }
  }

  const code = commentAt >= 0 ? line.slice(0, commentAt) : line;
  const comment = commentAt >= 0 ? line.slice(commentAt) : '';

  // key: value pattern — capture indentation, key, separator, value.
  const m = code.match(/^(\s*-?\s*)([A-Za-z_][\w.-]*)(\s*:\s*)(.*)$/);
  if (m) {
    const [, indent, key, sep, rest] = m;
    if (indent) out.push({ text: indent, cls: 'mp-tok-plain' });
    out.push({ text: key, cls: 'mp-tok-key' });
    out.push({ text: sep, cls: 'mp-tok-plain' });
    if (rest) out.push(...tokenizeValue(rest));
  } else {
    out.push(...tokenizeValue(code));
  }

  if (comment) out.push({ text: comment, cls: 'mp-tok-comment' });
  return out;
}

function tokenizeValue(value: string): Token[] {
  const trimmed = value.trim();
  if (trimmed === '') return [{ text: value, cls: 'mp-tok-plain' }];

  const leading = value.slice(0, value.length - value.trimStart().length);
  const trailing = value.slice(value.trimEnd().length);

  let cls = 'mp-tok-plain';
  if (/^"[^"]*"$/.test(trimmed) || /^'[^']*'$/.test(trimmed)) {
    cls = 'mp-tok-string';
  } else if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    cls = 'mp-tok-number';
  } else if (/^(true|false|null|~|yes|no|on|off)$/i.test(trimmed)) {
    cls = 'mp-tok-bool';
  } else if (/^[|>][+-]?$/.test(trimmed)) {
    cls = 'mp-tok-block';
  }

  const out: Token[] = [];
  if (leading) out.push({ text: leading, cls: 'mp-tok-plain' });
  out.push({ text: trimmed, cls });
  if (trailing) out.push({ text: trailing, cls: 'mp-tok-plain' });
  return out;
}

// ---- soft-rule checks (mirror docs SchemaValidator.vue) --------------------

function softRuleWarnings(doc: unknown): string[] {
  const warnings: string[] = [];
  if (!doc || typeof doc !== 'object') return warnings;
  const d = doc as Record<string, unknown>;
  const meta = (d.metadata ?? {}) as Record<string, unknown>;
  const provenance = (d.provenance ?? {}) as Record<string, unknown>;
  const safety = (d.safety ?? {}) as Record<string, unknown>;
  const disclaimers = (safety.disclaimers ?? {}) as Record<string, unknown>;

  if (!meta.tagline || typeof meta.tagline !== 'string' || !meta.tagline.toString().trim()) {
    warnings.push(
      'metadata.tagline is missing — every manifest must declare a tagline so the agent surfaces in catalogs.',
    );
  }

  if (provenance.append_only !== true) {
    warnings.push(
      'provenance.append_only must be exactly true — Constitution Article III requires append-only provenance for every agent.',
    );
  }

  if (d.kind === 'super-agent') {
    if (!d.constitution || typeof d.constitution !== 'object') {
      warnings.push(
        'kind == "super-agent" requires a top-level constitution block (rules, consent_gates, hard_refusals).',
      );
    }
  }

  if (typeof d.kind === 'string' && FINANCE_KINDS.has(d.kind)) {
    if (!disclaimers.not_financial_advice) {
      warnings.push(
        'Finance kind detected — safety.disclaimers.not_financial_advice must be set so the "Not financial advice" banner renders on every UI surface.',
      );
    }
  }

  return warnings;
}

// ---- component -------------------------------------------------------------

export default function ManifestPreview({ yaml }: ManifestPreviewProps) {
  const [status, setStatus] = useState<Status>('loading');
  const [errors, setErrors] = useState<SchemaError[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [usingFallbackSchema, setUsingFallbackSchema] = useState(false);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle');

  // Holds the compiled validator + yaml lib across renders.
  const validatorRef = useRef<((doc: unknown) => boolean) | null>(null);
  const yamlLibRef = useRef<{ load: (text: string) => unknown } | null>(null);
  const validatorErrorsRef = useRef<unknown>(null);

  // Bootstrap CDN deps + schema once on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [ajvMod, yamlMod, schemaResp] = await Promise.all([
          import(/* webpackIgnore: true */ AJV_CDN),
          import(/* webpackIgnore: true */ YAML_CDN),
          fetch(SCHEMA_URL).catch(() => null),
        ]);
        if (cancelled) return;

        let schema: Record<string, unknown> = FALLBACK_SCHEMA as Record<string, unknown>;
        let usedFallback = true;
        if (schemaResp && schemaResp.ok) {
          try {
            schema = (await schemaResp.json()) as Record<string, unknown>;
            usedFallback = false;
          } catch {
            schema = FALLBACK_SCHEMA as Record<string, unknown>;
            usedFallback = true;
          }
        }
        if (cancelled) return;
        setUsingFallbackSchema(usedFallback);

        const ajvAny = ajvMod as Record<string, unknown>;
        const AjvCtor =
          (ajvAny.default as new (opts: unknown) => unknown) ||
          (ajvAny.Ajv2020 as new (opts: unknown) => unknown);
        const ajv = new AjvCtor({
          strict: false,
          allErrors: true,
          allowUnionTypes: true,
        }) as { compile: (s: unknown) => (doc: unknown) => boolean };

        // The schema may declare a $id Ajv would try to resolve. Strip it.
        if (schema && typeof schema === 'object' && '$id' in schema) {
          delete (schema as Record<string, unknown>).$id;
        }

        validatorRef.current = ajv.compile(schema);
        const yamlAny = yamlMod as Record<string, unknown>;
        yamlLibRef.current =
          (yamlAny.default as { load: (text: string) => unknown }) ||
          (yamlAny as unknown as { load: (text: string) => unknown });

        runValidation(yaml);
      } catch (err) {
        if (cancelled) return;
        setLoadError(
          'Could not load Ajv or js-yaml from esm.sh. The preview will still render the YAML, but schema validation is unavailable. ' +
            (err instanceof Error ? err.message : String(err)),
        );
        setStatus('idle');
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-validate whenever the YAML prop changes (after deps are ready).
  useEffect(() => {
    if (validatorRef.current && yamlLibRef.current) {
      runValidation(yaml);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yaml]);

  function runValidation(text: string): void {
    setParseError(null);
    setErrors([]);
    setWarnings([]);

    if (!text || !text.trim()) {
      setStatus('idle');
      return;
    }

    let doc: unknown;
    try {
      doc = yamlLibRef.current?.load(text) ?? null;
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
      setStatus('parse-error');
      return;
    }

    if (doc === null || typeof doc !== 'object') {
      setParseError('YAML did not parse to an object at the top level.');
      setStatus('parse-error');
      return;
    }

    const validator = validatorRef.current;
    if (!validator) {
      setStatus('idle');
      return;
    }

    const ok = validator(doc);
    if (!ok) {
      const rawErrs = ((validator as unknown as { errors?: unknown[] }).errors ||
        []) as Array<{
        instancePath?: string;
        message?: string;
        params?: unknown;
      }>;
      validatorErrorsRef.current = rawErrs;
      setErrors(
        rawErrs.map((e) => ({
          path: e.instancePath || '(root)',
          message: `${e.message || 'invalid'}${
            e.params ? ' — ' + JSON.stringify(e.params) : ''
          }`,
        })),
      );
      setWarnings(softRuleWarnings(doc));
      setStatus('invalid');
      return;
    }

    setWarnings(softRuleWarnings(doc));
    setStatus('valid');
  }

  const tokenizedLines = useMemo(() => {
    const lines = (yaml || '').split('\n');
    return lines.map((line, idx) => ({ idx, tokens: tokenizeLine(line) }));
  }, [yaml]);

  function handleCopy(): void {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      setCopyState('error');
      window.setTimeout(() => setCopyState('idle'), 1800);
      return;
    }
    navigator.clipboard.writeText(yaml || '').then(
      () => {
        setCopyState('copied');
        window.setTimeout(() => setCopyState('idle'), 1800);
      },
      () => {
        setCopyState('error');
        window.setTimeout(() => setCopyState('idle'), 1800);
      },
    );
  }

  function handleDownload(): void {
    if (typeof window === 'undefined') return;
    const blob = new Blob([yaml || ''], { type: 'text/yaml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'grok-agent.yaml';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  // Status banner styling (Spectral v1).
  const banner = (() => {
    if (status === 'loading') {
      return { bg: '#0A0A0A', fg: '#F4ECDA', border: '#888888', label: 'Loading validator…' };
    }
    if (status === 'idle') {
      return { bg: '#0A0A0A', fg: '#F4ECDA', border: '#888888', label: 'Awaiting manifest' };
    }
    if (status === 'parse-error') {
      return { bg: '#FF1E70', fg: '#F4ECDA', border: '#FF1E70', label: 'YAML parse error' };
    }
    if (status === 'invalid') {
      return {
        bg: '#FF1E70',
        fg: '#F4ECDA',
        border: '#FF1E70',
        label: `${errors.length} schema error${errors.length === 1 ? '' : 's'}`,
      };
    }
    return {
      bg: '#00E0D5',
      fg: '#0A0A0A',
      border: '#00E0D5',
      label: '✓ Valid v2.15 manifest',
    };
  })();

  return (
    <section
      aria-label="Manifest preview"
      style={{
        border: '1px solid #0A0A0A',
        borderRadius: 6,
        background: '#F4ECDA',
        padding: 16,
        marginBottom: 16,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 12,
        }}
      >
        <span
          aria-live="polite"
          style={{
            background: banner.bg,
            color: banner.fg,
            border: `1px solid ${banner.border}`,
            padding: '4px 12px',
            borderRadius: 999,
            fontWeight: 700,
            fontSize: '0.85em',
            letterSpacing: '0.04em',
          }}
        >
          {banner.label}
        </span>
        {usingFallbackSchema && status !== 'loading' && (
          <span
            style={{
              fontSize: '0.8em',
              color: '#0A0A0A',
              background: 'rgba(0,0,0,0.06)',
              padding: '2px 8px',
              borderRadius: 4,
            }}
            title="Schema fetch from raw.githubusercontent.com failed; using minimal inline schema."
          >
            offline schema
          </span>
        )}
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={handleCopy}
          className="button"
          style={{
            background: '#0A0A0A',
            color: '#F4ECDA',
            border: '1px solid #0A0A0A',
            padding: '6px 14px',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          {copyState === 'copied'
            ? '✓ Copied!'
            : copyState === 'error'
              ? '✗ Failed'
              : 'Copy YAML'}
        </button>
        <button
          type="button"
          onClick={handleDownload}
          className="button secondary"
          style={{
            background: '#F4ECDA',
            color: '#0A0A0A',
            border: '1px solid #0A0A0A',
            padding: '6px 14px',
            borderRadius: 4,
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          Download .yaml
        </button>
      </header>

      <pre
        className="manifest"
        style={{
          background: '#0A0A0A',
          color: '#F4ECDA',
          padding: 14,
          borderRadius: 4,
          margin: 0,
          overflowX: 'auto',
          fontFamily:
            'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
          fontSize: '0.85em',
          lineHeight: 1.5,
        }}
      >
        <code>
          {tokenizedLines.map(({ idx, tokens }) => (
            <span key={idx} style={{ display: 'block' }}>
              {tokens.length === 0 ? (
                <span>&nbsp;</span>
              ) : (
                tokens.map((t, ti) => (
                  <span key={ti} className={t.cls} style={tokenStyle(t.cls)}>
                    {t.text}
                  </span>
                ))
              )}
            </span>
          ))}
        </code>
      </pre>

      {loadError && (
        <div
          role="alert"
          style={{
            marginTop: 12,
            background: '#FF1E70',
            color: '#F4ECDA',
            border: '1px solid #FF1E70',
            padding: '10px 14px',
            borderRadius: 4,
            fontSize: '0.9em',
          }}
        >
          {loadError}
        </div>
      )}

      {status === 'parse-error' && parseError && (
        <div
          role="alert"
          style={{
            marginTop: 12,
            background: '#FF1E70',
            color: '#F4ECDA',
            border: '1px solid #FF1E70',
            padding: '10px 14px',
            borderRadius: 4,
            fontSize: '0.9em',
          }}
        >
          <strong>YAML parse error:</strong>
          <pre
            style={{
              margin: '6px 0 0',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'inherit',
            }}
          >
            {parseError}
          </pre>
        </div>
      )}

      {status === 'invalid' && errors.length > 0 && (
        <div
          role="alert"
          style={{
            marginTop: 12,
            background: 'rgba(255, 30, 112, 0.12)',
            color: '#0A0A0A',
            border: '1px solid #FF1E70',
            padding: '10px 14px',
            borderRadius: 4,
            fontSize: '0.9em',
          }}
        >
          <strong style={{ color: '#FF1E70' }}>
            Schema errors ({errors.length})
          </strong>
          <ul style={{ margin: '8px 0 0', paddingLeft: '1.2em' }}>
            {errors.map((e, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                <code
                  style={{
                    background: '#0A0A0A',
                    color: '#00E0D5',
                    padding: '1px 6px',
                    borderRadius: 3,
                    marginRight: 6,
                    fontSize: '0.9em',
                  }}
                >
                  {e.path || '(root)'}
                </code>
                <span>{e.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {status === 'valid' && (
        <div
          style={{
            marginTop: 12,
            background: 'rgba(0, 224, 213, 0.18)',
            color: '#0A0A0A',
            border: '1px solid #00E0D5',
            padding: '10px 14px',
            borderRadius: 4,
            fontSize: '0.9em',
          }}
        >
          <strong>✓ Valid v2.15 manifest.</strong> Schema checks pass. Review
          any soft-rule warnings below before submitting a pull request.
        </div>
      )}

      {warnings.length > 0 && (
        <div
          style={{
            marginTop: 12,
            background: '#F4ECDA',
            color: '#0A0A0A',
            border: '1px dashed #0A0A0A',
            padding: '10px 14px',
            borderRadius: 4,
            fontSize: '0.9em',
          }}
        >
          <strong>Soft-rule warnings ({warnings.length})</strong>
          <ul style={{ margin: '8px 0 0', paddingLeft: '1.2em' }}>
            {warnings.map((w, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function tokenStyle(cls: string): React.CSSProperties {
  switch (cls) {
    case 'mp-tok-key':
      return { color: '#00E0D5', fontWeight: 600 };
    case 'mp-tok-string':
      return { color: '#F4ECDA' };
    case 'mp-tok-number':
      return { color: '#FF8FB1' };
    case 'mp-tok-bool':
      return { color: '#FF1E70', fontWeight: 600 };
    case 'mp-tok-block':
      return { color: '#FF1E70' };
    case 'mp-tok-comment':
      return { color: '#888888', fontStyle: 'italic' };
    default:
      return { color: '#F4ECDA' };
  }
}
