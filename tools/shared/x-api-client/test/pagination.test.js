import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch } from '@x-platform-toolkit/test-utils';
import XApiClient from '../src/index.js';

test('getFollowers() omits pagination_token on first page', async () => {
  const restore = mockFetch({ body: { data: [], meta: {} } });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    await client.getFollowers('12345', { maxResults: 25 });
    const url = restore.calls[0].url;
    assert.ok(url.includes('max_results=25'));
    assert.ok(!url.includes('pagination_token'));
  } finally {
    restore();
  }
});

test('getFollowers() appends pagination_token when supplied', async () => {
  const restore = mockFetch({ body: { data: [], meta: {} } });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    await client.getFollowers('12345', {
      maxResults: 100,
      paginationToken: 'CURSOR_abc123',
    });
    const url = restore.calls[0].url;
    assert.ok(url.includes('max_results=100'));
    assert.ok(url.includes('pagination_token=CURSOR_abc123'));
  } finally {
    restore();
  }
});

test('getFollowers() url-encodes the cursor value', async () => {
  const restore = mockFetch({ body: { data: [], meta: {} } });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    await client.getFollowers('12345', { paginationToken: 'a/b c+d' });
    const url = restore.calls[0].url;
    assert.ok(url.includes('pagination_token=a%2Fb+c%2Bd') || url.includes('pagination_token=a%2Fb%20c%2Bd'));
  } finally {
    restore();
  }
});
