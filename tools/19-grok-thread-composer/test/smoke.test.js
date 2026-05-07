import { test } from 'node:test';
import assert from 'node:assert/strict';
// eslint-disable-next-line no-unused-vars
import { mockFetch } from '@x-platform-toolkit/test-utils';
import { ThreadComposer } from '../src/main.js';

test('ThreadComposer imports and instantiates without throwing', () => {
  const composer = new ThreadComposer();
  assert.ok(composer instanceof ThreadComposer);
  assert.equal(composer.state.tone, 'punchy');
  assert.equal(composer.state.length, 8);
  assert.deepEqual(composer.state.tweets, []);
});

test('main() returns a promise and resolves without DOM', async () => {
  const composer = new ThreadComposer();
  const result = composer.main();
  assert.ok(result instanceof Promise, 'main() must return a Promise');
  await assert.doesNotReject(() => result);
});
