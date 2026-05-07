import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mockFetch, loadFixture } from '@x-platform-toolkit/test-utils';
import XApiClient from '../src/index.js';

test('getUserByUsername() hits the right URL and returns decoded body', async () => {
  const restore = mockFetch({
    body: { data: { id: '12345', username: 'elonmusk', name: 'Elon' } },
  });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    const res = await client.getUserByUsername('elonmusk');
    assert.equal(res.data.username, 'elonmusk');

    const url = restore.calls[0].url;
    assert.ok(url.startsWith('https://api.x.com/2/users/by/username/elonmusk?'));
    assert.ok(url.includes('user.fields=public_metrics'));
    assert.ok(url.includes('description'));
    assert.ok(url.includes('created_at'));
  } finally {
    restore();
  }
});

test('getUserTweets() sends max_results and tweet.fields in the query string', async () => {
  const restore = mockFetch({ body: { data: [], meta: { result_count: 0 } } });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    await client.getUserTweets('12345', { maxResults: 50 });
    const url = restore.calls[0].url;
    assert.ok(url.startsWith('https://api.x.com/2/users/12345/tweets?'));
    assert.ok(url.includes('max_results=50'));
    assert.ok(url.includes('tweet.fields=public_metrics'));
    assert.ok(url.includes('conversation_id'));
  } finally {
    restore();
  }
});

test('getTweet() hits the /tweets/:id endpoint with expected fields', async () => {
  const restore = mockFetch({ body: { data: { id: '999', text: 'hello' } } });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    await client.getTweet('999');
    const url = restore.calls[0].url;
    assert.ok(url.startsWith('https://api.x.com/2/tweets/999?'));
    assert.ok(url.includes('tweet.fields=public_metrics'));
  } finally {
    restore();
  }
});

test('getFollowers() returns the followers fixture unchanged', async () => {
  const fixture = loadFixture('x-followers.json');
  const restore = mockFetch({ body: fixture });
  try {
    const client = new XApiClient({ bearerToken: 'AAAA-test' });
    const res = await client.getFollowers('12345');
    assert.equal(res.data.length, 3);
    assert.equal(res.meta.next_token, 'NEXTPAGE_cursor_token_abc123');
  } finally {
    restore();
  }
});
