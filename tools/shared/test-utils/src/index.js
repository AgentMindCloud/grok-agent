/**
 * @x-platform-toolkit/test-utils — entry point.
 * Re-exports mockFetch + sseStream, and a tiny fixture loader.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

export { mockFetch, sseStream } from './mock-fetch.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = join(__dirname, '..', 'fixtures');

/**
 * loadFixture(name) — read a fixture file under ./fixtures/.
 * Returns parsed JSON for .json files, raw UTF-8 text otherwise.
 */
export function loadFixture(name) {
  const raw = readFileSync(join(FIXTURES_DIR, name), 'utf8');
  if (name.endsWith('.json')) return JSON.parse(raw);
  return raw;
}
