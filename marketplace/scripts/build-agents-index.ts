/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

// Prebuild script: walks templates/super-agents/ and templates/finance/,
// parses every grok-agent.yaml, and writes content/agents.json.
// Run via: npx ts-node --esm scripts/build-agents-index.ts
// Or add to package.json: "prebuild": "ts-node scripts/build-agents-index.ts"

import fs from 'node:fs';
import path from 'node:path';

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const OUT_FILE = path.resolve(__dirname, '..', 'content', 'agents.json');

// TODO: implement full YAML walk + normalisation (reuse logic from lib/manifests.ts)
function main() {
  // eslint-disable-next-line no-console
  console.log('[build-agents-index] TODO: implement YAML scan');
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify([], null, 2) + '\n');
  // eslint-disable-next-line no-console
  console.log(`[build-agents-index] wrote ${OUT_FILE}`);
  void REPO_ROOT; // suppress unused warning until implemented
}

main();
