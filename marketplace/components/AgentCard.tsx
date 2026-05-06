// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Reusable agent card. Renders a single Agent with its name, kind badge,
// description, tag chips, cost limit, and an Install button that copies
// the "grok install this" primer plus a manifest link to the clipboard.

'use client';

import { useState } from 'react';
import type { Agent } from '../lib/types';
import { TIER_LABELS } from '../lib/types';

interface AgentCardProps {
  agent: Agent;
}

export default function AgentCard({ agent }: AgentCardProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return;
    navigator.clipboard.writeText(agent.copyText).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      },
      () => setCopied(false),
    );
  }

  const cost =
    agent.costLimitUsd != null ? `$${agent.costLimitUsd.toFixed(2)}` : '—';

  return (
    <article className="card" data-tier={agent.tier}>
      <span className="badge">{TIER_LABELS[agent.tier]}</span>
      <h3>{agent.displayName}</h3>
      <p className="meta">{agent.description}</p>
      {agent.tags.length > 0 && (
        <ul className="tag-row" aria-label="Tags">
          {agent.tags.slice(0, 4).map((tag) => (
            <li key={tag} className="chip">
              {tag}
            </li>
          ))}
        </ul>
      )}
      <p className="meta">
        Kind <code>{agent.kind}</code> · Cost cap{' '}
        <strong>{cost}</strong>
        {agent.multiAgentRole ? (
          <>
            {' · Role '}
            <code>{agent.multiAgentRole}</code>
          </>
        ) : null}
      </p>
      <div className="actions">
        <button type="button" className="button" onClick={handleCopy}>
          {copied ? 'Copied!' : 'Install — copy "grok install this"'}
        </button>
        <a
          className="button secondary"
          href={agent.githubFolderUrl}
          target="_blank"
          rel="noreferrer noopener"
        >
          View on GitHub
        </a>
      </div>
    </article>
  );
}
