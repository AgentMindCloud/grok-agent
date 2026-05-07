import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch } from '@x-platform-toolkit/test-utils';
import XApiClient from '../src/index.js';

test('request() sets Authorization + JSON content type, decodes JSON response', async () => {
  const restore = mockFetch({ body: { ok: true, echo: 'hi' } });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    const json = await client.request('/ping');
    assert.deepEqual(json, { ok: true, echo: 'hi' });

    const [{ url, init }] = restore.calls;
    assert.equal(url, 'https://api.x.com/2/ping');
    assert.equal(init.headers.Authorization, 'Bearer AAAA-test');
    assert.equal(init.headers['Content-Type'], 'application/json');
  } finally {
    restore();
  }
});

test('request() merges caller-provided headers without clobbering Authorization', async () => {
  const restore = mockFetch({ body: {} });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    await client.request('/echo', { headers: { 'X-Custom': 'abc' } });
    const { init } = restore.calls[0];
    assert.equal(init.headers['X-Custom'], 'abc');
    assert.equal(init.headers.Authorization, 'Bearer AAAA-test');
  } finally {
    restore();
  }
});

test('request() throws with status + body on non-2xx', async () => {
  const restore = mockFetch({ status: 401, body: 'Unauthorized' });
  try {
    const client = new XApiClient({ bearerToken: 'bad' });
    await assert.rejects(() => client.request('/users/me'), /X API 401: Unauthorized/);
  } finally {
    restore();
  }
});

test('constructor throws when neither bearerToken nor X_BEARER_TOKEN is set', () => {
  const prior = process.env.X_BEARER_TOKEN;
  delete process.env.X_BEARER_TOKEN;
  try {
    assert.throws(() => new XApiClient(), /X_BEARER_TOKEN required/);
  } finally {
    if (prior !== undefined) process.env.X_BEARER_TOKEN = prior;
  }
});
