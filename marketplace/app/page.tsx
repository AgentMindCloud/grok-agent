// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Landing page for the Grok Agent OS marketplace. Server-rendered hero +
// Featured Super Agents strip, with a client-only AgentBrowser below it
// that handles search + kind-filter chips. Built to help xAI and Grok
// win.

import Link from 'next/link';
import {
  FEATURED_AGENTS,
  FEATURED_SUPER_AGENTS,
  listKinds,
} from '../lib/agents';
import { buildDeployToXUrl } from '../lib/manifest';
import AgentBrowser from './_components/AgentBrowser';

export default function HomePage() {
  return (
    <main>
      <section className="hero">
        <h1>Grok Agent OS — Marketplace</h1>
        <p className="tagline">
          Three flagship Super Agents and a growing library of creator
          templates. One v2.15 manifest schema. Apache-2.0, local-first,
          Windows-first. Built to help xAI and Grok win.
        </p>

        <div className="deploy-cta" aria-label="Primary calls to action">
          <Link href="/deploy" className="button">
            Deploy your own — generate a v2.15 manifest
          </Link>
          <a
            href={buildDeployToXUrl({
              slug: 'grok-agent-os',
              description:
                'Local-first, Windows-native agent platform on the v2.15 ' +
                'manifest standard. Three flagship Super Agents shipped.',
              pageUrl: 'https://github.com/AgentMindCloud/grok-agent',
            })}
            className="button secondary"
            target="_blank"
            rel="noreferrer noopener"
          >
            Share the platform on X
          </a>
          <a
            href="https://github.com/AgentMindCloud/grok-agent"
            className="button secondary"
            target="_blank"
            rel="noreferrer noopener"
          >
            View on GitHub
          </a>
        </div>
      </section>

      <section aria-labelledby="featured-super-agents">
        <h2 id="featured-super-agents" className="section">
          Featured Super Agents
        </h2>
        <p className="meta">
          Three flagship runtimes — synthesis, personal OS, real-world
          action — that demonstrate the v2.15 standard end-to-end.
        </p>
        <div className="grid hero-grid">
          {FEATURED_SUPER_AGENTS.map((agent) => (
            <article key={agent.slug} className="card hero-card">
              <span className="badge">Super Agent #{agent.number}</span>
              <h3>{agent.name}</h3>
              <p className="meta">{agent.tagline}</p>
              <p className="meta">
                Port <code>{agent.port}</code> · Consent gates:{' '}
                <strong>{agent.consentGates.length}</strong>
              </p>
              <div className="actions">
                <Link
                  href={`/agents/${agent.slug}` as `/agents/${string}`}
                  className="button"
                >
                  View detail
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="browse-everything">
        <h2 id="browse-everything" className="section">
          Browse the catalogue
        </h2>
        <p className="meta">
          Search across name, capabilities, consent gates, or tags. Filter
          by kind to scope to Super Agents, creator templates, or x-native
          agents.
        </p>
        <AgentBrowser agents={FEATURED_AGENTS} kinds={listKinds()} />
      </section>

      <section>
        <h2 className="section">Why a marketplace?</h2>
        <p>
          Every Grok Agent OS template is one valid <code>grok-agent.yaml</code>{' '}
          v2.15 file plus a folder of code that the canonical CLI installs in
          one PowerShell line:
        </p>
        <pre className="manifest">
          <code>
            # Windows 11 + PowerShell{'\n'}
            grok install this
          </code>
        </pre>
        <p>
          The marketplace just makes that link discoverable. Every action
          stays local: no telemetry, no auto-publish, no remote tool
          execution. The v2.15 schema is enforced by the same{' '}
          <code>cli/grok-agent.py</code> validator the CI workflow runs on
          every push.
        </p>
      </section>

      <section>
        <h2 className="section">Roadmap</h2>
        <ul>
          <li>
            <strong>v0.1 (P149)</strong> — featured Super Agents +
            Deploy-to-X manifest generator.
          </li>
          <li>
            <strong>v0.2 (P150, this release)</strong> — search + kind
            filters, polished styling, broader generator coverage, Vercel +
            GitHub Pages deploy guide, xAI partnership pitch.
          </li>
          <li>
            <strong>v0.3</strong> — anonymous, opt-in install analytics
            (Article-VII-compliant).
          </li>
          <li>
            <strong>v0.4</strong> — community submissions via PR, gated by
            the same v2.15 + Constitution validator the CI workflow runs.
          </li>
        </ul>
      </section>
    </main>
  );
}
