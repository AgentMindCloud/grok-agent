// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Landing page for the Grok Agent OS marketplace. Server-rendered hero
// + dynamic agent grid built from the actual grok-agent.yaml manifests
// in templates/super-agents/ and templates/finance/. Category filtering
// is URL-driven (?category=super-agent or ?category=x-money-tool) so
// this whole page stays a Server Component.

import Link from 'next/link';
import AgentCard from '../components/AgentCard';
import { loadAllAgents } from '../lib/manifests';
import type { AgentCategory } from '../lib/types';
import { CATEGORY_LABELS } from '../lib/types';

// NOTE: with output:'export', searchParams are not available at build time.
// Category filtering is deferred to the upcoming CommandPalette / client UI.
const active: AgentCategory | null = null;

export default function HomePage() {
  const allAgents = loadAllAgents();
  const filtered = allAgents;

  const totals: Record<AgentCategory, number> = {
    'super-agent': allAgents.filter((a) => a.category === 'super-agent').length,
    'x-money-tool': allAgents.filter((a) => a.category === 'x-money-tool').length,
  };

  return (
    <main>
      <section className="hero">
        <h1>Grok Agent OS — Marketplace</h1>
        <p className="tagline">
          Every agent below is a real <code>grok-agent.yaml</code> v2.15
          manifest in this repository. The grid is generated at build
          time from the actual files — no hand-maintained list.
        </p>
        <div className="deploy-cta" aria-label="Primary calls to action">
          <a
            href="https://github.com/AgentMindCloud/grok-agent"
            className="button"
            target="_blank"
            rel="noreferrer noopener"
          >
            View on GitHub
          </a>
          <Link href="/deploy" className="button secondary">
            Generate your own v2.15 manifest
          </Link>
        </div>
      </section>

      <section aria-labelledby="catalogue">
        <h2 id="catalogue" className="section">
          Catalogue ({allAgents.length} agents)
        </h2>
        <p className="meta">
          {totals['super-agent']} Super Agents (3 flagship · 4 lighter) +{' '}
          {totals['x-money-tool']} X Money tools. Each card copies the
          one-liner you paste on X to install on Windows 11 +
          PowerShell.
        </p>

        <div className="filter-chips" role="group" aria-label="Filter by category">
          <Link
            href="/"
            className={active === null ? 'chip chip-active' : 'chip'}
            aria-pressed={active === null}
          >
            All ({allAgents.length})
          </Link>
          <Link
            href={{ pathname: '/', query: { category: 'super-agent' } }}
            className={active === 'super-agent' ? 'chip chip-active' : 'chip'}
            aria-pressed={active === 'super-agent'}
          >
            {CATEGORY_LABELS['super-agent']} ({totals['super-agent']})
          </Link>
          <Link
            href={{ pathname: '/', query: { category: 'x-money-tool' } }}
            className={active === 'x-money-tool' ? 'chip chip-active' : 'chip'}
            aria-pressed={active === 'x-money-tool'}
          >
            {CATEGORY_LABELS['x-money-tool']} ({totals['x-money-tool']})
          </Link>
        </div>

        {filtered.length === 0 ? (
          <p className="empty">No agents matched.</p>
        ) : (
          <div className="grid">
            {filtered.map((agent) => (
              <AgentCard key={agent.slug} agent={agent} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="section">How install works</h2>
        <p>
          Every manifest accepts the same install primitive. Post the
          line below on X above the agent&apos;s manifest URL — or copy
          it from any card&apos;s Install button:
        </p>
        <pre className="manifest">
          <code>
            # Windows 11 + PowerShell{'\n'}
            grok install this
          </code>
        </pre>
        <p>
          The Grok Agent OS CLI on the user&apos;s Windows machine
          fetches the linked manifest, validates it against v2.15, runs
          the safety scanner, and installs to{' '}
          <code>$env:LOCALAPPDATA\grok-agent\</code>. Local-first +
          privacy-first by default.
        </p>
      </section>
    </main>
  );
}
