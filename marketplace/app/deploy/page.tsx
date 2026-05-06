// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// "Deploy to X" — a thin manifest generator that emits a valid
// `grok-agent.yaml` v2.15 file from a small form. The form is fully
// client-side: no data leaves the browser. Built to help xAI and Grok
// win.

'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  DEFAULT_CONSENT_GATES,
  DeployFormInput,
  MANIFEST_KIND_OPTIONS,
  ManifestKind,
  buildDeployToXUrl,
  generateManifestYaml,
  slugify,
  validateDeployInput,
} from '../../lib/manifest';

const DEFAULT_KIND: ManifestKind = 'super-agent';

interface FormState {
  name: string;
  kind: ManifestKind;
  description: string;
  author: string;
  defaultPort: string;
  realTimeX: boolean;
  gatesCsv: string;
}

const INITIAL_STATE: FormState = {
  name: 'my-agent',
  kind: DEFAULT_KIND,
  description:
    'Local-first Windows agent generated from the Grok Agent OS marketplace. ' +
    'Edit before publishing.',
  author: '@JanSol0s',
  defaultPort: '8510',
  realTimeX: false,
  gatesCsv: DEFAULT_CONSENT_GATES[DEFAULT_KIND].join(', '),
};

function readPort(raw: string): number {
  const n = Number.parseInt(raw, 10);
  if (Number.isNaN(n)) return 0;
  return n;
}

function gatesFromCsv(csv: string): string[] {
  return csv
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function DeployForm() {
  const params = useSearchParams();
  const [state, setState] = useState<FormState>(() => seedFromParams(params));
  const [copied, setCopied] = useState(false);

  // When the URL params change (e.g. user navigates from a Super Agent
  // detail page with prefill data), reset the form. The deep-link
  // contract is described in `lib/manifest.ts:buildDeepLink`.
  useEffect(() => {
    setState(seedFromParams(params));
  }, [params]);

  const input: DeployFormInput = useMemo(
    () => ({
      name: slugify(state.name),
      kind: state.kind,
      description: state.description,
      author: state.author,
      defaultPort: readPort(state.defaultPort),
      realTimeX: state.realTimeX,
      consentGates: gatesFromCsv(state.gatesCsv),
    }),
    [state]
  );

  const validation = useMemo(() => validateDeployInput(input), [input]);
  const yamlOut = useMemo(
    () => (validation.ok ? generateManifestYaml(input) : ''),
    [input, validation.ok]
  );

  const tweetUrl = useMemo(
    () =>
      buildDeployToXUrl({
        slug: input.name,
        description: input.description.slice(0, 220),
        pageUrl: 'https://github.com/AgentMindCloud/grok-agent',
      }),
    [input]
  );

  function copyToClipboard() {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      return;
    }
    navigator.clipboard.writeText(yamlOut).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      },
      () => setCopied(false)
    );
  }

  function downloadManifest() {
    if (!yamlOut) return;
    const blob = new Blob([yamlOut], { type: 'text/yaml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'grok-agent.yaml';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function onKindChange(kind: ManifestKind) {
    setState((prev) => ({
      ...prev,
      kind,
      gatesCsv: DEFAULT_CONSENT_GATES[kind].join(', '),
    }));
  }

  return (
    <main>
      <h1>Deploy to X — v2.15 manifest generator</h1>
      <p className="tagline">
        Fill the form to generate a valid <code>grok-agent.yaml</code>{' '}
        manifest. The form is 100% client-side; no data is sent to a server.
      </p>

      <div className="banner">
        <strong>Local-first.</strong> Every byte you type stays in this
        browser tab. The download button writes the file straight to your
        Downloads folder; the X-share button only opens an X compose URL —
        we never proxy your post.
      </div>

      <form
        onSubmit={(event) => event.preventDefault()}
        aria-label="Deploy form"
      >
        <label htmlFor="name">Agent name (kebab-case)</label>
        <input
          id="name"
          type="text"
          value={state.name}
          onChange={(e) =>
            setState((prev) => ({ ...prev, name: e.target.value }))
          }
          autoComplete="off"
          spellCheck={false}
          required
        />

        <label htmlFor="kind">Kind</label>
        <select
          id="kind"
          value={state.kind}
          onChange={(e) => onKindChange(e.target.value as ManifestKind)}
        >
          {MANIFEST_KIND_OPTIONS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>

        <label htmlFor="description">Description (≥ 12 chars)</label>
        <textarea
          id="description"
          value={state.description}
          onChange={(e) =>
            setState((prev) => ({ ...prev, description: e.target.value }))
          }
          required
        />

        <label htmlFor="author">Author</label>
        <input
          id="author"
          type="text"
          value={state.author}
          onChange={(e) =>
            setState((prev) => ({ ...prev, author: e.target.value }))
          }
          autoComplete="off"
          required
        />

        <label htmlFor="port">Default Streamlit port (1024–65535)</label>
        <input
          id="port"
          type="number"
          min={1024}
          max={65535}
          value={state.defaultPort}
          onChange={(e) =>
            setState((prev) => ({ ...prev, defaultPort: e.target.value }))
          }
          required
        />

        <label htmlFor="gates">
          Consent gates (comma-separated; the form seeds defaults per kind)
        </label>
        <input
          id="gates"
          type="text"
          value={state.gatesCsv}
          onChange={(e) =>
            setState((prev) => ({ ...prev, gatesCsv: e.target.value }))
          }
          autoComplete="off"
          spellCheck={false}
        />

        <label>
          <input
            type="checkbox"
            checked={state.realTimeX}
            onChange={(e) =>
              setState((prev) => ({ ...prev, realTimeX: e.target.checked }))
            }
            style={{ width: 'auto', marginRight: 8 }}
          />
          Enable <code>real_time_x</code> (mention-triggered, reply-only)
        </label>
      </form>

      {!validation.ok && (
        <div className="error" role="alert">
          <strong>Cannot generate manifest:</strong>
          <ul>
            {validation.errors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <h2 className="section">Generated manifest</h2>
      {validation.ok ? (
        <>
          <pre className="manifest">
            <code>{yamlOut}</code>
          </pre>
          <div className="deploy-cta">
            <button type="button" onClick={copyToClipboard}>
              {copied ? 'Copied!' : 'Copy YAML'}
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={downloadManifest}
            >
              Download grok-agent.yaml
            </button>
            <a
              className="button"
              href={tweetUrl}
              target="_blank"
              rel="noreferrer noopener"
            >
              Share on X
            </a>
          </div>
          <p className="meta">
            Validate with the canonical CLI before shipping:{' '}
            <code>python cli/grok-agent.py validate grok-agent.yaml</code>
          </p>
        </>
      ) : (
        <p className="meta">Fix the form errors above to generate a manifest.</p>
      )}
    </main>
  );
}

function seedFromParams(params: URLSearchParams | null): FormState {
  if (!params) return { ...INITIAL_STATE };
  const next: FormState = { ...INITIAL_STATE };
  const kindParam = params.get('kind');
  if (
    kindParam &&
    (MANIFEST_KIND_OPTIONS as string[]).includes(kindParam)
  ) {
    next.kind = kindParam as ManifestKind;
    next.gatesCsv = DEFAULT_CONSENT_GATES[next.kind].join(', ');
  }
  const name = params.get('name');
  if (name) next.name = name;
  const description = params.get('description');
  if (description) next.description = description;
  const author = params.get('author');
  if (author) next.author = author;
  const port = params.get('port');
  if (port) next.defaultPort = port;
  const gates = params.get('gates');
  if (gates) next.gatesCsv = gates.split(',').map((g) => g.trim()).join(', ');
  const rtx = params.get('rtx');
  if (rtx === '1') next.realTimeX = true;
  if (rtx === '0') next.realTimeX = false;
  return next;
}

export default function DeployPage() {
  return (
    <Suspense fallback={<main><p>Loading deploy form…</p></main>}>
      <DeployForm />
    </Suspense>
  );
}
