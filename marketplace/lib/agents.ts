// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// SERVER-ONLY adapter that turns the raw Agent[] from lib/manifests.ts
// into the FeaturedAgent shape consumed by the legacy detail route at
// /agents/[slug]. Pure types and the filterAgents helper now live in
// lib/types.ts and are imported there directly by Client Components.

import 'server-only';
import { loadAllAgents } from './manifests';
import {
  Agent,
  AgentKind,
  AgentTier,
  FeaturedAgent,
  FLAGSHIP_NUMBERS,
} from './types';

export type { AgentKind, FeaturedAgent } from './types';
export { filterAgents } from './types';

const TIER_STATUS: Record<AgentTier, string> = {
  flagship: 'shipping',
  lighter: 'shipping',
  'x-money': 'shipping',
};

function asAgentKind(kind: string): AgentKind {
  const allowed: AgentKind[] = [
    'super-agent',
    'creator-template',
    'x-native',
    'finance-dashboard',
    'alpha-engine',
    'creator-payout-optimizer',
    'vision-analyzer',
    'agent',
  ];
  return (allowed as string[]).includes(kind) ? (kind as AgentKind) : 'agent';
}

function adapt(agent: Agent): FeaturedAgent {
  const number = FLAGSHIP_NUMBERS[agent.slug];
  const capabilities = agent.tags.length > 0
    ? agent.tags.slice(0, 5)
    : agent.multiAgentAgents.slice(0, 5);
  return {
    slug: agent.slug,
    name: agent.displayName,
    tagline: agent.tagline || agent.description,
    description: agent.description,
    kind: asAgentKind(agent.kind),
    number,
    port: undefined,
    consentGates: [],
    status: TIER_STATUS[agent.tier],
    capabilities,
    manifestPath: agent.manifestPath,
    constitutionPath: undefined,
  };
}

export const FEATURED_AGENTS: FeaturedAgent[] = loadAllAgents().map(adapt);

export const FEATURED_SUPER_AGENTS: FeaturedAgent[] = FEATURED_AGENTS
  .filter((agent) => agent.number != null)
  .sort((a, b) => (a.number ?? 0) - (b.number ?? 0));

export function listKinds(): AgentKind[] {
  const seen = new Set<AgentKind>();
  for (const agent of FEATURED_AGENTS) seen.add(agent.kind);
  return Array.from(seen);
}

export function getFeaturedAgent(slug: string): FeaturedAgent | undefined {
  return FEATURED_AGENTS.find((agent) => agent.slug === slug);
}
