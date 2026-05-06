// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Client-side browser with a search bar + kind filter chips. Hydrates
// from the static `FEATURED_AGENTS` catalogue passed in as a prop, so
// the landing page itself can stay a server component for the parts
// that don't need interactivity. Built to help xAI and Grok win.

'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import {
  AgentKind,
  FeaturedAgent,
  filterAgents,
} from '../../lib/agents';
import { buildDeployToXUrl } from '../../lib/manifest';

interface AgentBrowserProps {
  agents: FeaturedAgent[];
  kinds: AgentKind[];
}

const KIND_LABEL: Record<AgentKind, string> = {
  'super-agent': 'Super Agent',
  'creator-template': 'Creator template',
  'x-native': 'X-native',
  'finance-dashboard': 'Finance dashboard',
  'alpha-engine': 'Alpha engine',
  'creator-payout-optimizer': 'Payout optimizer',
  'vision-analyzer': 'Vision analyzer',
  'agent': 'General agent',
};

export default function AgentBrowser({ agents, kinds }: AgentBrowserProps) {
  const [query, setQuery] = useState('');
  const [activeKinds, setActiveKinds] = useState<AgentKind[]>([]);

  const filtered = useMemo(
    () => filterAgents(agents, query, activeKinds),
    [agents, query, activeKinds],
  );

  function toggleKind(kind: AgentKind) {
    setActiveKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind],
    );
  }

  function clearFilters() {
    setQuery('');
    setActiveKinds([]);
  }

  return (
    <div className="browser">
      <div className="browser-controls" role="search">
        <label htmlFor="agent-search" className="visually-hidden">
          Search agents
        </label>
        <input
          id="agent-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, capability, consent gate, or tag…"
          autoComplete="off"
          spellCheck={false}
        />
        <div className="filter-chips" role="group" aria-label="Filter by kind">
          {kinds.map((kind) => {
            const active = activeKinds.includes(kind);
            return (
              <button
                key={kind}
                type="button"
                onClick={() => toggleKind(kind)}
                className={active ? 'chip chip-active' : 'chip'}
                aria-pressed={active}
              >
                {KIND_LABEL[kind] ?? kind}
              </button>
            );
          })}
          {(query || activeKinds.length > 0) && (
            <button
              type="button"
              onClick={clearFilters}
              className="chip chip-clear"
            >
              Clear
            </button>
          )}
        </div>
        <p className="meta browser-summary">
          Showing <strong>{filtered.length}</strong> of {agents.length} agent
          {agents.length === 1 ? '' : 's'}.
        </p>
      </div>

      {filtered.length === 0 ? (
        <p className="empty">
          No agents matched. Try clearing filters or broadening the search.
        </p>
      ) : (
        <div className="grid">
          {filtered.map((agent) => (
            <article key={agent.slug} className="card">
              <span className="badge">
                {agent.number != null
                  ? `Super Agent #${agent.number}`
                  : KIND_LABEL[agent.kind] ?? agent.kind}
              </span>
              <h3>{agent.name}</h3>
              <p className="meta">{agent.tagline}</p>
              <ul>
                {agent.capabilities.slice(0, 3).map((cap) => (
                  <li key={cap}>{cap}</li>
                ))}
              </ul>
              <p className="meta">
                {agent.port ? (
                  <>
                    Port <code>{agent.port}</code> ·{' '}
                  </>
                ) : null}
                Consent gates:{' '}
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
      )}
    </div>
  );
}
