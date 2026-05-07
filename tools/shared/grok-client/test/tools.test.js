import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch, loadFixture } from '@x-platform-toolkit/test-utils';
import GrokClient from '../src/index.js';

const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'score_virality',
      description: 'Return a virality score for a draft post.',
      parameters: {
        type: 'object',
        properties: {
          draft: { type: 'string' },
          niche: { type: 'string' },
        },
        required: ['draft'],
      },
    },
  },
];

test('chat() with tools returns { content, tool_calls }', async () => {
  const restore = mockFetch({ body: loadFixture('grok-chat-tools.json') });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    const result = await client.chat(
      [{ role: 'user', content: 'score: "ship fast or die slow" (builder niche)' }],
      { tools: TOOLS, toolChoice: 'auto' }
    );

    assert.equal(typeof result, 'object');
    assert.equal(result.content, null);
    assert.equal(result.tool_calls.length, 1);

    const call = result.tool_calls[0];
    assert.equal(call.id, 'call_fixture_1');
    assert.equal(call.type, 'function');
    assert.equal(call.function.name, 'score_virality');

    const args = JSON.parse(call.function.arguments);
    assert.deepEqual(args, { draft: 'ship fast or die slow', niche: 'builder' });

    const sent = JSON.parse(restore.calls[0].init.body);
    assert.deepEqual(sent.tools, TOOLS);
    assert.equal(sent.tool_choice, 'auto');
  } finally {
    restore();
  }
});

test('chat() without tools still returns a bare string (back-compat)', async () => {
  const restore = mockFetch({ body: loadFixture('grok-chat.json') });
  try {
    const client = new GrokClient({ apiKey: 'sk-test-123' });
    const result = await client.chat([{ role: 'user', content: 'hi' }]);
    assert.equal(typeof result, 'string');
  } finally {
    restore();
  }
});
