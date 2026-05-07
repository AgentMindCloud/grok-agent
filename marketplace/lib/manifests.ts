// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// SERVER-ONLY build-time manifest scanner. Walks templates/super-agents,
// templates/finance, and templates/creator, parses every grok-agent.yaml
// with js-yaml, and returns a normalized Agent[]. Imported only from
// Server Components or other server-only modules — never from a Client
// Component.

import 'server-only';
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import {
  Agent,
  AgentCategory,
  AgentTier,
  FLAGSHIP_SLUGS,
  ManifestRaw,
} from './types';

export type { Agent, AgentCategory, AgentTier, ManifestRaw } from './types';
export {
  CATEGORY_LABELS,
  TIER_LABELS,
} from './types';

const REPO_ROOT = path.resolve(process.cwd(), '..');
const TEMPLATES_ROOT = path.join(REPO_ROOT, 'templates');
const SUPER_AGENTS_DIR = path.join(TEMPLATES_ROOT, 'super-agents');
const FINANCE_DIR = path.join(TEMPLATES_ROOT, 'finance');
const CREATOR_DIR = path.join(TEMPLATES_ROOT, 'creator');

function readManifest(folderPath: string): ManifestRaw | null {
  const manifestFile = path.join(folderPath, 'grok-agent.yaml');
  if (!fs.existsSync(manifestFile)) return null;
  const raw = fs.readFileSync(manifestFile, 'utf8');
  const parsed = yaml.load(raw) as ManifestRaw | undefined;
  if (!parsed || typeof parsed !== 'object') return null;
  return parsed;
}

function deriveDisplayName(manifest: ManifestRaw, slug: string): string {
  if (manifest.metadata?.display_name) return manifest.metadata.display_name;
  if (manifest.name && /[A-Z\s]/.test(manifest.name)) return manifest.name;
  return slug
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function deriveCostLimit(manifest: ManifestRaw): number | null {
  const sessionMax = manifest.safety?.cost_limits?.usd_per_session_max;
  if (typeof sessionMax === 'number') return sessionMax;
  const flat = manifest.safety_profile?.cost_limit_usd;
  if (typeof flat === 'number') return flat;
  return null;
}

function deriveTags(manifest: ManifestRaw): string[] {
  const tags = manifest.metadata?.tags;
  if (Array.isArray(tags)) return tags;
  return [];
}

function deriveInstallCommand(manifest: ManifestRaw, slug: string): string {
  if (manifest.install?.install_command) return manifest.install.install_command;
  if (manifest.install?.command) return manifest.install.command;
  return `grok-agent install ${slug}`;
}

function deriveCategory(folderRoot: string): AgentCategory {
  if (folderRoot === SUPER_AGENTS_DIR) return 'super-agent';
  if (folderRoot === CREATOR_DIR) return 'creator-template';
  return 'x-money-tool';
}

function deriveTier(category: AgentCategory, slug: string): AgentTier {
  if (category === 'x-money-tool') return 'x-money';
  if (category === 'creator-template') return 'creator';
  return FLAGSHIP_SLUGS.has(slug) ? 'flagship' : 'lighter';
}

function scanFolder(folderRoot: string): Agent[] {
  if (!fs.existsSync(folderRoot)) return [];
  const entries = fs.readdirSync(folderRoot, { withFileTypes: true });
  const agents: Agent[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const slug = entry.name;
    const folderPath = path.join(folderRoot, slug);
    const manifest = readManifest(folderPath);
    if (!manifest) continue;
    const category = deriveCategory(folderRoot);
    const tier = deriveTier(category, slug);
    const displayName = deriveDisplayName(manifest, slug);
    const tagline = manifest.metadata?.tagline ?? manifest.description ?? '';
    const description = manifest.description ?? tagline;
    const installCommand = deriveInstallCommand(manifest, slug);
    const relativeFolder = path
      .relative(REPO_ROOT, folderPath)
      .split(path.sep)
      .join('/');
    const githubFolderUrl =
      `https://github.com/AgentMindCloud/grok-agent/tree/main/${relativeFolder}`;
    const githubManifestUrl =
      `https://github.com/AgentMindCloud/grok-agent/blob/main/${relativeFolder}/grok-agent.yaml`;
    const copyText =
      installCommand === 'grok install this'
        ? `grok install this\n\nManifest: ${githubManifestUrl}`
        : `${installCommand}\n\nManifest: ${githubManifestUrl}`;

    agents.push({
      slug,
      displayName,
      rawName: manifest.name ?? slug,
      description,
      tagline,
      kind: manifest.kind ?? 'agent',
      category,
      tier,
      costLimitUsd: deriveCostLimit(manifest),
      tags: deriveTags(manifest),
      manifestPath: `${relativeFolder}/grok-agent.yaml`,
      folderPath: relativeFolder,
      installCommand,
      copyText,
      githubFolderUrl,
      githubManifestUrl,
      multiAgentRole: manifest.multi_agent?.role ?? null,
      multiAgentAgents: manifest.multi_agent?.agents ?? [],
    });
  }
  return agents;
}

function tierWeight(tier: AgentTier): number {
  switch (tier) {
    case 'flagship':
      return 0;
    case 'lighter':
      return 1;
    case 'x-money':
      return 2;
    case 'creator':
      return 3;
  }
}

export function loadAllAgents(): Agent[] {
  const all = [
    ...scanFolder(SUPER_AGENTS_DIR),
    ...scanFolder(FINANCE_DIR),
    ...scanFolder(CREATOR_DIR),
  ];
  all.sort((a, b) => {
    const tierDiff = tierWeight(a.tier) - tierWeight(b.tier);
    if (tierDiff !== 0) return tierDiff;
    return a.displayName.localeCompare(b.displayName);
  });
  return all;
}

export function loadAgentsByCategory(category: AgentCategory): Agent[] {
  return loadAllAgents().filter((agent) => agent.category === category);
}

export function findAgentBySlug(slug: string): Agent | undefined {
  return loadAllAgents().find((agent) => agent.slug === slug);
}
