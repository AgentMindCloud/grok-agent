import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch, loadFixture } from '@x-platform-toolkit/test-utils';
import GrokClient from '../src/index.js';

test('chat() posts the right body and returns content string', async () => {
  const restore = mockFetch({ body: loadFixture('grok-chat.json') });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    const reply = await client.chat(
      [{ role: 'user', content: 'give me a take' }],
      { temperature: 0.5, maxTokens: 128 }
    );

    assert.equal(typeof reply, 'string');
    assert.equal(reply, 'Hot takes usually age like milk. Ship and let the feed decide.');

    assert.equal(restore.calls.length, 1);
    const [{ url, init }] = restore.calls;
    assert.equal(url, 'https://api.x.ai/v1/chat/completions');
    assert.equal(init.method, 'POST');
    assert.equal(init.headers.Authorization, 'Bearer sk-test-123');
    assert.equal(init.headers['Content-Type'], 'application/json');

    const sent = JSON.parse(init.body);
    assert.equal(sent.model, 'grok-2-latest');
    assert.equal(sent.temperature, 0.5);
    assert.equal(sent.max_tokens, 128);
    assert.deepEqual(sent.messages, [{ role: 'user', content: 'give me a take' }]);
    assert.equal(sent.tools, undefined);
  } finally {
    restore();
  }
});

test('complete() wraps the prompt as a user message', async () => {
  const restore = mockFetch({ body: loadFixture('grok-chat.json') });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    await client.complete('one-liner please');
    const sent = JSON.parse(restore.calls[0].init.body);
    assert.deepEqual(sent.messages, [{ role: 'user', content: 'one-liner please' }]);
  } finally {
    restore();
  }
});

test('chat() throws with status and body on non-2xx', async () => {
  const restore = mockFetch({ status: 429, body: 'rate limited' });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    await assert.rejects(
      () => client.chat([{ role: 'user', content: 'hi' }]),
      /Grok API 429: rate limited/
    );
  } finally {
    restore();
  }
});

test('constructor throws when neither apiKey nor XAI_API_KEY is set', () => {
  const prior = process.env.XAI_API_KEY;
  delete process.env.XAI_API_KEY;
  try {
    assert.throws(() => new GrokClient(), /XAI_API_KEY required/);
  } finally {
    if (prior !== undefined) process.env.XAI_API_KEY = prior;
  }
});
