# test-utils

> Shared test helpers and fixtures for every workspace package and tool in `x-platform-toolkit`.

Zero dependencies. ESM-only. Intended for use inside `node:test` suites.

## What's here

- `mockFetch(responses)` — replace `globalThis.fetch` with a scripted responder. Returns a `restore()` function (also exposing `.calls` for assertions).
- `sseStream(text)` — wrap a raw SSE transcript in a `ReadableStream`, for streaming tests.
- `loadFixture(name)` — read a file under `./fixtures/`. `.json` files are parsed; everything else is returned as UTF-8 text.
- Canonical fixtures under `./fixtures/`:
  - `grok-chat.json` — non-streaming chat completion
  - `grok-chat-tools.json` — chat completion with a populated `tool_calls`
  - `grok-stream.txt` — SSE transcript ending in `data: [DONE]`
  - `x-followers.json` — representative `getFollowers` page

## Install

Linked automatically via npm workspaces. In another workspace's `package.json`:

```json
"devDependencies": {
  "@x-platform-toolkit/test-utils": "*"
}
```

Then run `npm install` at the monorepo root.

## Usage

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch, sseStream, loadFixture } from '@x-platform-toolkit/test-utils';

test('returns a string for plain chat', async () => {
  const restore = mockFetch({ body: loadFixture('grok-chat.json') });
  try {
    // ... call your client ...
    assert.equal(restore.calls.length, 1);
  } finally {
    restore();
  }
});

test('streams tokens', async () => {
  const stream = sseStream(loadFixture('grok-stream.txt'));
  const restore = mockFetch({ body: stream, headers: { 'Content-Type': 'text/event-stream' } });
  // ... iterate your chatStream() generator ...
  restore();
});
```

### Per-call scripting

`mockFetch` accepts an array to script one response per call, or a function for dynamic behavior:

```js
const restore = mockFetch([
  { body: { data: [] } },
  { status: 429, body: { title: 'Too Many Requests' } },
]);

const restore2 = mockFetch((url, init) => ({
  body: url.includes('/users') ? loadFixture('x-followers.json') : { ok: true },
}));
```

## Direct fixture access

Consumers can also load fixtures by subpath without going through `loadFixture`:

```js
import chat from '@x-platform-toolkit/test-utils/fixtures/grok-chat.json' with { type: 'json' };
```

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
