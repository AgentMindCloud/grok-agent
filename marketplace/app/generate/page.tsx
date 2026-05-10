// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// AI Agent Generator wizard route. Server Component shell that hosts a
// Client Component wizard (<GeneratorWizard />) for the multi-step flow:
// paste a README → pick a v2.15 kind → call Claude via /api/generate →
// preview the draft manifest → open a one-click PR.
//
// IMPORTANT runtime note: this page is NOT compatible with a pure Next.js
// static export (`output: 'export'`). The wizard performs a client-side
// `fetch('/api/generate', ...)` against an authenticated, server-side API
// route owned by a sibling worker. That route requires a Node runtime in
// production — Vercel Functions, Netlify Functions, or any Node host. Do
// NOT enable static export for the /generate sub-tree without first
// providing an alternative hosted API surface.
//
// Spectral v1 brand palette: charcoal #0A0A0A, cinnabar #FF1E70,
// parchment #F4ECDA, teal #00E0D5. The wizard component re-uses the same
// CSS variables already defined in marketplace/app/globals.css so this
// page does not introduce any new design tokens.

import GeneratorWizard from '../../components/GeneratorWizard';

export const metadata = {
  title: 'Generate a Grok Agent OS manifest from a README',
  description:
    'Multi-step wizard that turns an existing README, project description, ' +
    'or feature spec into a draft grok-agent.yaml v2.15 manifest, then opens ' +
    'a one-click pull request against AgentMindCloud/grok-agent.',
};

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
      aria-label="Built for xAI, X, Grok and the ecosystem community."
    >
      <p style={{ margin: '0 0 8px' }}>
        Sources:{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/grok-agent.yaml"
          target="_blank"
          rel="noreferrer noopener"
        >
          spec/v2.15/grok-agent.yaml
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

export default function GeneratePage() {
  return (
    <main>
      <section className="hero">
        <h1>Generate a Grok Agent OS manifest from a README</h1>
        <p className="tagline">
          Paste an existing README, project description, or feature spec.
          Claude drafts a <code>grok-agent.yaml</code> v2.15 manifest, runs
          a preview against the live schema, and offers a one-click pull
          request into <code>AgentMindCloud/grok-agent</code>. Every draft
          is reviewable before merge — nothing ships without a human in the
          loop.
        </p>
        <p className="meta">
          The wizard runs entirely in your browser and only contacts the{' '}
          <code>/api/generate</code> route on this site. No model keys are
          ever shipped to the client; generation happens server-side under
          the marketplace&apos;s own credentials.
        </p>
      </section>

      <GeneratorWizard />

      <Footer />
    </main>
  );
}
