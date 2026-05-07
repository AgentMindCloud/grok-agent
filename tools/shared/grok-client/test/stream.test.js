import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch, sseStream, loadFixture } from '@x-platform-toolkit/test-utils';
import GrokClient from '../src/index.js';

test('chatStream() yields content tokens in order and stops on [DONE]', async () => {
  const transcript = loadFixture('grok-stream.txt');
  const restore = mockFetch({
    body: sseStream(transcript),
    headers: { 'Content-Type': 'text/event-stream' },
  });

  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    const tokens = [];
    for await (const tok of client.chatStream([{ role: 'user', content: 'stream me' }])) {
      tokens.push(tok);
    }

    assert.deepEqual(tokens, ['Hot', ' takes', ' age', ' fast.']);

    const sent = JSON.parse(restore.calls[0].init.body);
    assert.equal(sent.stream, true);
    assert.equal(sent.model, 'grok-2-latest');
  } finally {
    restore();
  }
});

test('chatStream() survives a split frame across chunks', async () => {
  const encoder = new TextEncoder();
  const parts = [
    'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
    'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
    'data: [DONE]\n\n',
  ];
  const mid = Math.floor(parts[0].length / 2);
  const chunkA = parts[0].slice(0, mid);
  const chunkB = parts[0].slice(mid) + parts[1] + parts[2];

  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(chunkA));
      controller.enqueue(encoder.encode(chunkB));
      controller.close();
    },
  });

  const restore = mockFetch({ body: stream });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    const tokens = [];
    for await (const tok of client.chatStream([{ role: 'user', content: 'hi' }])) {
      tokens.push(tok);
    }
    assert.deepEqual(tokens, ['Hel', 'lo']);
  } finally {
    restore();
  }
});

test('chatStream() throws on non-2xx', async () => {
  const restore = mockFetch({ status: 500, body: 'boom' });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    await assert.rejects(async () => {
      // eslint-disable-next-line no-unused-vars
      for await (const _tok of client.chatStream([{ role: 'user', content: 'hi' }])) {
        // should never yield
      }
    }, /Grok API 500: boom/);
  } finally {
    restore();
  }
});
