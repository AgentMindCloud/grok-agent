// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Per-agent detail route. Renders any catalogued agent with its
// manifest path, install command, tags, and one-click "Deploy a copy"
// + "Share on X" call-to-actions. Reads the catalogue directly from
// lib/manifests.ts (no legacy adapter shim).

import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { findAgentBySlug, loadAllAgents } from '../../../lib/manifests';
import {
  buildDeepLink,
  buildDeployToXUrl,
  ManifestKind,
} from '../../../lib/manifest';
import { FLAGSHIP_NUMBERS, TIER_LABELS } from '../../../lib/types';

interface PageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return loadAllAgents().map((agent) => ({ slug: agent.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const agent = findAgentBySlug(params.slug);
  if (!agent) {
    return { title: 'Agent not found · Grok Agent OS' };
  }
  const number = FLAGSHIP_NUMBERS[agent.slug];
  const titlePrefix = number != null ? `Super Agent #${number} — ` : '';
  return {
    title: `${titlePrefix}${agent.displayName} · Grok Agent OS`,
    description: agent.tagline || agent.description,
  };
}

export default function AgentDetailPage({ params }: PageProps) {
  const agent = findAgentBySlug(params.slug);
  if (!agent) {
    notFound();
  }

  const number = FLAGSHIP_NUMBERS[agent.slug];
  const folder = agent.folderPath;
  const manifestUrl = agent.githubManifestUrl;
  const folderUrl = agent.githubFolderUrl;

  const deployHref = buildDeepLink({
    name: agent.slug,
    kind: agent.kind as ManifestKind,
    description: agent.tagline || agent.description,
    author: '@JanSol0s',
    defaultPort: 8510,
    consentGates: [],
    realTimeX: false,
  });

  const tweetUrl = buildDeployToXUrl({
    slug: agent.slug,
    description: agent.tagline || agent.description,
    pageUrl: folderUrl,
  });

  const capabilities =
    agent.tags.length > 0
      ? agent.tags.slice(0, 5)
      : agent.multiAgentAgents.slice(0, 5);

  const cost =
    agent.costLimitUsd != null ? `$${agent.costLimitUsd.toFixed(2)}` : '—';

  return (
    <main>
      <p>
        <Link href="/">← Back to marketplace</Link>
      </p>
      <span className="banner" style={{ display: 'inline-block' }}>
        {number != null
          ? `Super Agent #${number}`
          : TIER_LABELS[agent.tier]}
        {' · cost cap '}
        <strong>{cost}</strong>
      </span>
      <h1 style={{ marginTop: 16 }}>{agent.displayName}</h1>
      <p className="tagline">{agent.tagline || agent.description}</p>

      <h2 className="section">What it does</h2>
      <p>{agent.description}</p>

      {capabilities.length > 0 && (
        <>
          <h2 className="section">Capabilities</h2>
          <ul>
            {capabilities.map((cap) => (
              <li key={cap}>{cap}</li>
            ))}
          </ul>
        </>
      )}

      <h2 className="section">Source on GitHub</h2>
      <ul>
        <li>
          <a href={manifestUrl} target="_blank" rel="noreferrer noopener">
            {agent.manifestPath}
          </a>{' '}
          — v2.15 manifest
        </li>
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
          {agent.installCommand}
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
