// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Pure types, label maps, and the filterAgents helper. No filesystem
// access — safe to import from Client Components and Server Components
// alike. Server-only modules (lib/manifests.ts, lib/agents-data.ts)
// import from this file.

export type AgentCategory = 'super-agent' | 'x-money-tool' | 'creator-template';

export type AgentTier = 'flagship' | 'lighter' | 'x-money' | 'creator';

export interface ManifestRaw {
  version?: string;
  kind?: string;
  name?: string;
  description?: string;
  metadata?: {
    display_name?: string;
    tagline?: string;
    categories?: string[];
    category?: string;
    tags?: string[];
    repository?: string;
  };
  install?: {
    command?: string;
    install_command?: string;
    one_click?: boolean;
  };
  safety?: {
    cost_limits?: {
      usd_per_session_max?: number;
      usd_per_day_max?: number;
    };
  };
  safety_profile?: {
    cost_limit_usd?: number;
  };
  multi_agent?: {
    role?: string;
    agents?: string[];
    max_agents?: number;
    delegates_to?: string[];
  };
  memory?: { enabled?: boolean };
  provenance?: { enabled?: boolean };
  [key: string]: unknown;
}

export interface Agent {
  slug: string;
  displayName: string;
  rawName: string;
  description: string;
  tagline: string;
  kind: string;
  category: AgentCategory;
  tier: AgentTier;
  costLimitUsd: number | null;
  tags: string[];
  manifestPath: string;
  folderPath: string;
  installCommand: string;
  copyText: string;
  githubFolderUrl: string;
  githubManifestUrl: string;
  multiAgentRole: string | null;
  multiAgentAgents: string[];
}

export type AgentKind =
  | 'super-agent'
  | 'creator-template'
  | 'x-native'
  | 'finance-dashboard'
  | 'alpha-engine'
  | 'creator-payout-optimizer'
  | 'vision-analyzer'
  | 'agent';

export interface FeaturedAgent {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  kind: AgentKind;
  number?: number;
  port?: number;
  consentGates: string[];
  status: string;
  capabilities: string[];
  manifestPath: string;
  constitutionPath?: string;
}

export type ManifestKind = AgentKind;

export interface DeployFormInput {
  name: string;
  kind: ManifestKind;
  description: string;
  author: string;
  defaultPort: number;
  realTimeX: boolean;
  consentGates: string[];
}

export interface ValidationResult {
  ok: boolean;
  errors: string[];
  fields: {
    name?: string;
    kind?: string;
    description?: string;
    author?: string;
    defaultPort?: string;
    consentGates?: string;
  };
}

export const FLAGSHIP_SLUGS = new Set([
  'living-narrative-fabric',
  'self-evolving-personal-os',
  'cross-reality-action-fabric',
]);

export const FLAGSHIP_NUMBERS: Record<string, number> = {
  'living-narrative-fabric': 1,
  'self-evolving-personal-os': 2,
  'cross-reality-action-fabric': 3,
};

export const CATEGORY_LABELS: Record<AgentCategory, string> = {
  'super-agent': 'Super Agents',
  'x-money-tool': 'X Money Tools',
  'creator-template': 'Creator Templates',
};

export const TIER_LABELS: Record<AgentTier, string> = {
  flagship: 'Flagship Super Agent',
  lighter: 'Lighter Super Agent',
  'x-money': 'X Money Tool',
  creator: 'Creator Template',
};

export const MANIFEST_KIND_OPTIONS: ManifestKind[] = [
  'super-agent',
  'creator-template',
  'x-native',
  'finance-dashboard',
  'alpha-engine',
  'creator-payout-optimizer',
  'vision-analyzer',
  'agent',
];

export const KIND_HELPER: Record<ManifestKind, string> = {
  'super-agent': 'Flagship orchestrated agent with multi-agent + memory blocks.',
  'creator-template': 'Lightweight creator workflow template.',
  'x-native': 'Runs primarily through "grok install this" on X.',
  'finance-dashboard': 'Streamlit-based finance UI (X Money Companion Dashboard).',
  'alpha-engine': 'Cashtag intelligence + market signal agent.',
  'creator-payout-optimizer': 'Earnings forecasting and content optimization.',
  'vision-analyzer': 'Image and document vision agent (e.g. receipt parsing).',
  'agent': 'Generic agent — smallest valid manifest.',
};

export const DEFAULT_PORT_FOR_KIND: Record<ManifestKind, number> = {
  'super-agent': 8510,
  'creator-template': 8520,
  'x-native': 8530,
  'finance-dashboard': 8501,
  'alpha-engine': 8502,
  'creator-payout-optimizer': 8503,
  'vision-analyzer': 8504,
  'agent': 8540,
};

export const DEFAULT_CONSENT_GATES: Record<ManifestKind, string[]> = {
  'super-agent': ['publish_synthesis', 'export_provenance_log'],
  'creator-template': ['publish_post'],
  'x-native': ['reply_on_x'],
  'finance-dashboard': ['export_tax_report', 'sync_to_cloud'],
  'alpha-engine': ['publish_alert'],
  'creator-payout-optimizer': ['export_tax_report'],
  'vision-analyzer': ['import_receipt'],
  'agent': [],
};

export function filterAgents(
  agents: FeaturedAgent[],
  query: string,
  kinds: AgentKind[],
): FeaturedAgent[] {
  const trimmed = query.trim().toLowerCase();
  return agents.filter((agent) => {
    if (kinds.length > 0 && !kinds.includes(agent.kind)) return false;
    if (!trimmed) return true;
    const haystack = [
      agent.slug,
      agent.name,
      agent.tagline,
      agent.description,
      ...agent.capabilities,
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(trimmed);
  });
}
