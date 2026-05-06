// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Per-agent detail route. Renders any catalogued agent with its manifest
// path, capabilities, and consent gates, and offers "Deploy a copy" /
// "Share on X" call-to-actions. Built for xAI, X, Grok and the ecosystem community. ❤️

import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { FEATURED_AGENTS, getFeaturedAgent } from '../../../lib/agents';
import {
  buildDeepLink,
  buildDeployToXUrl,
  ManifestKind,
} from '../../../lib/manifest';

interface PageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return FEATURED_AGENTS.map((agent) => ({ slug: agent.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const agent = getFeaturedAgent(params.slug);
  if (!agent) {
    return { title: 'Agent not found · Grok Agent OS' };
  }
  const titlePrefix =
    agent.number != null ? `Super Agent #${agent.number} — ` : '';
  return {
    title: `${titlePrefix}${agent.name} · Grok Agent OS`,
    description: agent.tagline,
  };
}

export default function AgentDetailPage({ params }: PageProps) {
  const agent = getFeaturedAgent(params.slug);
  if (!agent) {
    notFound();
  }

  const folder = agent.manifestPath.split('/').slice(0, -1).join('/');
  const manifestUrl = `https://github.com/AgentMindCloud/grok-agent/blob/main/${agent.manifestPath}`;
  const folderUrl = `https://github.com/AgentMindCloud/grok-agent/tree/main/${folder}`;
  const constitutionUrl = agent.constitutionPath
    ? `https://github.com/AgentMindCloud/grok-agent/blob/main/${agent.constitutionPath}`
    : null;

  const deployHref = buildDeepLink({
    name: agent.slug,
    kind: agent.kind as ManifestKind,
    description: agent.tagline,
    author: '@JanSol0s',
    defaultPort: agent.port ?? 8510,
    consentGates: agent.consentGates,
    realTimeX: false,
  });

  const tweetUrl = buildDeployToXUrl({
    slug: agent.slug,
    description: agent.tagline,
    pageUrl: folderUrl,
  });

  return (
    <main>
      <p>
        <Link href="/">← Back to marketplace</Link>
      </p>
      <span className="banner" style={{ display: 'inline-block' }}>
        {agent.number != null
          ? `Super Agent #${agent.number}`
          : `Kind: ${agent.kind}`}
        {agent.port ? <> · port {agent.port}</> : null}
        {' · status '}
        <strong>{agent.status}</strong>
      </span>
      <h1 style={{ marginTop: 16 }}>{agent.name}</h1>
      <p className="tagline">{agent.tagline}</p>

      <h2 className="section">What it does</h2>
      <p>{agent.description}</p>

      <h2 className="section">Capabilities</h2>
      <ul>
        {agent.capabilities.map((cap) => (
          <li key={cap}>{cap}</li>
        ))}
      </ul>

      <h2 className="section">Consent gates ({agent.consentGates.length})</h2>
      <p className="meta">
        Every gate below requires an explicit, scoped, typed user approval
        at runtime. The agent never persists "remember my choice" toggles.
      </p>
      {agent.consentGates.length === 0 ? (
        <p>
          <em>None declared — this agent emits drafts only.</em>
        </p>
      ) : (
        <pre className="manifest">
          <code>{agent.consentGates.map((g) => `- ${g}`).join('\n')}</code>
        </pre>
      )}

      <h2 className="section">Source on GitHub</h2>
      <ul>
        <li>
          <a href={manifestUrl} target="_blank" rel="noreferrer noopener">
            {agent.manifestPath}
          </a>{' '}
          — v2.15 manifest
        </li>
        {agent.constitutionPath && constitutionUrl ? (
          <li>
            <a href={constitutionUrl} target="_blank" rel="noreferrer noopener">
              {agent.constitutionPath}
            </a>{' '}
            — agent Constitution
          </li>
        ) : null}
        <li>
          <a href={folderUrl} target="_blank" rel="noreferrer noopener">
            {folder}/
          </a>{' '}
          — full source tree
        </li>
      </ul>

      <h2 className="section">Install on Windows 11</h2>
      <pre className="manifest">
        <code>
          {`cd ${folder.replace(/\//g, '\\')}\n`}
          {'python -m pip install -r requirements.txt\n'}
          {agent.port
            ? `streamlit run dashboard.py --server.port ${agent.port}`
            : 'python run.py --help'}
        </code>
      </pre>

      <div className="deploy-cta">
        <Link href={deployHref as `/deploy?${string}`} className="button">
          Clone manifest into the Deploy form
        </Link>
        <a
          href={tweetUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="button secondary"
        >
          Share on X
        </a>
        <a
          href={folderUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="button secondary"
        >
          View on GitHub
        </a>
      </div>
    </main>
  );
}
