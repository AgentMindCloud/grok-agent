#!/usr/bin/env node
/**
 * Assert that each tool folder matches its declared status.
 *
 * Live tools MUST have:  index.html + README.md  (no SPEC.md)
 * Spec'd tools MUST have: SPEC.md + README.md    (no index.html)
 *
 * Exits non-zero on any mismatch.
 */

import { readdirSync, existsSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const TOOLS_DIR = join(ROOT, 'tools');

// ---- Source of truth: tool status map ----
const TOOL_STATUS = {
  '01-thread-decay-tracker': 'spec',
  '02-follower-intent-classifier': 'spec',
  '03-contextual-reply-suggester': 'spec',
  '04-pre-post-virality-scorer': 'live',
  '05-pinned-post-ab-rotator': 'live',
  '06-digital-product-storefront': 'spec',
  '07-content-compound-calculator': 'live',
  '08-follow-unfollow-velocity-map': 'spec',
  '09-engagement-quality-score': 'live',
  '10-cross-account-niche-benchmarker': 'spec',
  '11-ghostwriter-mode-with-memory': 'spec',
  '12-controversy-detector': 'live',
  '13-thread-to-newsletter-converter': 'spec',
  '14-warm-introduction-mapper': 'spec',
  '15-spaces-recorder-clips': 'spec',
  '16-follower-migration-assistant': 'spec',
  '17-post-necromancer': 'spec',
  '18-emotional-tone-trend-tracker': 'live',
  '19-grok-thread-composer': 'spec',
  '20-x-articles-optimizer': 'spec',
};

const REQUIREMENTS = {
  live: { required: ['index.html', 'README.md'], forbidden: ['SPEC.md'] },
  spec: { required: ['SPEC.md', 'README.md'], forbidden: ['index.html'] },
};

function listToolDirs() {
  return readdirSync(TOOLS_DIR)
    .filter((name) => {
      const p = join(TOOLS_DIR, name);
      return statSync(p).isDirectory();
    })
    .sort();
}

function checkTool(toolName, status) {
  const dir = join(TOOLS_DIR, toolName);
  const rules = REQUIREMENTS[status];
  const errors = [];

  for (const f of rules.required) {
    if (!existsSync(join(dir, f))) {
      errors.push(`missing required file: ${f}`);
    }
  }
  for (const f of rules.forbidden) {
    if (existsSync(join(dir, f))) {
      errors.push(`unexpected file for ${status} tool: ${f}`);
    }
  }
  return errors;
}

function main() {
  const toolDirs = listToolDirs();
  const declared = new Set(Object.keys(TOOL_STATUS));
  const present = new Set(toolDirs);
  const problems = [];

  for (const name of toolDirs) {
    if (!declared.has(name)) {
      problems.push(`tool folder not in status map: ${name}`);
    }
  }
  for (const name of declared) {
    if (!present.has(name)) {
      problems.push(`declared tool folder missing on disk: ${name}`);
    }
  }

  for (const [name, status] of Object.entries(TOOL_STATUS)) {
    if (!present.has(name)) continue;
    const errors = checkTool(name, status);
    for (const e of errors) {
      problems.push(`${name} (${status}): ${e}`);
    }
  }

  if (problems.length) {
    console.error('Tool categorization check FAILED:');
    for (const p of problems) console.error(`  - ${p}`);
    console.error(`\n${problems.length} problem(s) found.`);
    process.exit(1);
  }

  const liveCount = Object.values(TOOL_STATUS).filter((s) => s === 'live').length;
  const specCount = Object.values(TOOL_STATUS).filter((s) => s === 'spec').length;
  console.log(
    `Tool categorization OK: ${toolDirs.length} tools (${liveCount} live, ${specCount} spec'd).`
  );
}

main();
