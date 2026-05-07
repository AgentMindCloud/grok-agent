/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Prebuild script: walks templates/super-agents/, templates/finance/, and
 * templates/creator/, parses every grok-agent.yaml, and writes
 * marketplace/content/agents.json.
 *
 * Wired as `prebuild` in package.json so `npm run build` runs it before
 * `next build`. The generated JSON lives at
 * `marketplace/content/agents.json` and is intended for client-side
 * consumers (CommandPalette search, future TelemetryStrip aggregation)
 * that cannot import the server-only `lib/manifests.ts` directly.
 *
 * ESM-safe: derives the script's own directory via `import.meta.url` +
 * `fileURLToPath` rather than `__dirname` (which is undefined under
 * `tsx` / `ts-node --esm` execution).
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

// ESM-safe `__dirname`. The audit flagged the previous stub for using
// the bare `__dirname` token, which is undefined when the script runs
// under ESM loaders. fileURLToPath(import.meta.url) is the standard
// ESM idiom and works under both tsx and ts-node --esm.
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const TEMPLATES_ROOT = path.join(REPO_ROOT, 'templates');
const SCAN_DIRS = [
  { absPath: path.join(TEMPLATES_ROOT, 'super-agents'), category: 'super-agent' as const },
  { absPath: path.join(TEMPLATES_ROOT, 'finance'),      category: 'x-money-tool' as const },
  { absPath: path.join(TEMPLATES_ROOT, 'creator'),      category: 'creator-template' as const },
];
const OUT_FILE = path.resolve(__dirname, '..', 'content', 'agents.json');

const FLAGSHIP_SLUGS = new Set([
  'living-narrative-fabric',
  'self-evolving-personal-os',
  'cross-reality-action-fabric',
]);

interface IndexEntry {
  slug: string;
  category: 'super-agent' | 'x-money-tool' | 'creator-template';
  tier: 'flagship' | 'lighter' | 'x-money' | 'creator';
  displayName: string;
  tagline: string;
  description: string;
  kind: string;
  installCommand: string;
  manifestPath: string;
  folderPath: string;
}

interface RawManifest {
  name?: string;
  kind?: string;
  description?: string;
  metadata?: { display_name?: string; tagline?: string };
  install?: { command?: string; install_command?: string };
}

function deriveTier(category: IndexEntry['category'], slug: string): IndexEntry['tier'] {
  if (category === 'x-money-tool') return 'x-money';
  if (category === 'creator-template') return 'creator';
  return FLAGSHIP_SLUGS.has(slug) ? 'flagship' : 'lighter';
}

function deriveDisplayName(manifest: RawManifest, slug: string): string {
  if (manifest.metadata?.display_name) return manifest.metadata.display_name;
  if (manifest.name && /[A-Z\s]/.test(manifest.name)) return manifest.name;
  return slug
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function deriveInstallCommand(manifest: RawManifest, slug: string): string {
  if (manifest.install?.install_command) return manifest.install.install_command;
  if (manifest.install?.command) return manifest.install.command;
  return `grok-agent install ${slug}`;
}

function scanDir(dir: string, category: IndexEntry['category']): IndexEntry[] {
  if (!fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const out: IndexEntry[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const slug = entry.name;
    const folder = path.join(dir, slug);
    const manifestFile = path.join(folder, 'grok-agent.yaml');
    if (!fs.existsSync(manifestFile)) continue;
    const raw = fs.readFileSync(manifestFile, 'utf8');
    let manifest: RawManifest;
    try {
      manifest = (yaml.load(raw) as RawManifest) ?? {};
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn(`[build-agents-index] skip ${slug}: ${(err as Error).message}`);
      continue;
    }
    const tagline = manifest.metadata?.tagline ?? manifest.description ?? '';
    const description = manifest.description ?? tagline;
    const relativeFolder = path.relative(REPO_ROOT, folder).split(path.sep).join('/');
    out.push({
      slug,
      category,
      tier: deriveTier(category, slug),
      displayName: deriveDisplayName(manifest, slug),
      tagline,
      description,
      kind: manifest.kind ?? 'agent',
      installCommand: deriveInstallCommand(manifest, slug),
      manifestPath: `${relativeFolder}/grok-agent.yaml`,
      folderPath: relativeFolder,
    });
  }
  return out;
}

function tierWeight(tier: IndexEntry['tier']): number {
  switch (tier) {
    case 'flagship':  return 0;
    case 'lighter':   return 1;
    case 'x-money':   return 2;
    case 'creator':   return 3;
  }
}

function main() {
  const agents: IndexEntry[] = [];
  for (const { absPath, category } of SCAN_DIRS) {
    agents.push(...scanDir(absPath, category));
  }
  agents.sort((a, b) => {
    const w = tierWeight(a.tier) - tierWeight(b.tier);
    return w !== 0 ? w : a.displayName.localeCompare(b.displayName);
  });

  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(agents, null, 2) + '\n');

  // eslint-disable-next-line no-console
  console.log(`[build-agents-index] wrote ${agents.length} agent entries to ${OUT_FILE}`);
}

main();
