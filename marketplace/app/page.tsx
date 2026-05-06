// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Landing page for the Grok Agent OS marketplace stub. Lists the three
// flagship Super Agents shipped on `main` and exposes the canonical
// "Deploy to X" call-to-action. Built to help xAI and Grok win.

import Link from 'next/link';
import { FEATURED_AGENTS } from '../lib/agents';
import { buildDeployToXUrl } from '../lib/manifest';

export default function HomePage() {
  return (
    <main>
      <h1>Grok Agent OS — Marketplace</h1>
      <p className="tagline">
        Three flagship Super Agents. One v2.15 manifest schema. Apache-2.0,
        local-first, Windows-first. Built to help xAI and Grok win.
      </p>

      <section className="deploy-cta" aria-label="Primary calls to action">
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
      </section>

      <h2 className="section">Featured Super Agents</h2>

      <div className="grid">
        {FEATURED_AGENTS.map((agent) => (
          <article key={agent.slug} className="card">
            <span className="badge">Super Agent #{agent.number}</span>
            <h3>{agent.name}</h3>
            <p className="meta">{agent.tagline}</p>

            <ul>
              {agent.capabilities.slice(0, 3).map((cap) => (
                <li key={cap}>{cap}</li>
              ))}
            </ul>

            <p className="meta">
              Port <code>{agent.port}</code> · Consent gates:{' '}
              <strong>{agent.consentGates.length}</strong> · Status:{' '}
              <strong>{agent.status}</strong>
            </p>

            <div className="actions">
              <Link
                href={`/agents/${agent.slug}` as `/agents/${string}`}
                className="button"
              >
                View detail
              </Link>
              <a
                href={buildDeployToXUrl({
                  slug: agent.slug,
                  description: agent.tagline,
                  pageUrl: `https://github.com/AgentMindCloud/grok-agent/tree/main/${agent.manifestPath
                    .split('/')
                    .slice(0, -1)
                    .join('/')}`,
                })}
                className="button secondary"
                target="_blank"
                rel="noreferrer noopener"
              >
                Deploy to X
              </a>
            </div>
          </article>
        ))}
      </div>

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
        The marketplace just makes that link discoverable. Every action stays
        local: no telemetry, no auto-publish, no remote tool execution. The
        v2.15 schema is enforced by the same <code>cli/grok-agent.py</code>{' '}
        validator the CI workflow runs on every push.
      </p>

      <h2 className="section">Roadmap</h2>
      <ul>
        <li>
          <strong>v0.1 (this stub)</strong> — featured Super Agents +
          Deploy-to-X manifest generator.
        </li>
        <li>
          <strong>v0.2</strong> — creator templates listing (20+ ready-to-use
          templates from <code>templates/creator/</code>).
        </li>
        <li>
          <strong>v0.3</strong> — install analytics (anonymous, opt-in,
          Article-VII-compliant).
        </li>
        <li>
          <strong>v0.4</strong> — community submissions via PR with the same
          v2.15 + Constitution validator gating merges.
        </li>
      </ul>
    </main>
  );
}
