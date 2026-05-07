/**
 * x-api-client — browser / ESM entry for x-platform-toolkit.
 * Part of the grok-install family · Apache 2.0
 *
 * Import only from a bundler context (Vite / esbuild / Rollup / Webpack).
 * Node consumers should import the package's main CJS entry instead.
 *
 * No `process.env`, no node-only APIs. Constructor requires `bearerToken`.
 *
 * Reminder: browser-side use of a bearer token is almost never what you
 * want — see docs/cors.md. Prefer a serverless proxy and call that.
 */

const API_BASE = 'https://api.x.com/2';

export default class XApiClient {
  constructor({ bearerToken, baseURL = API_BASE } = {}) {
    if (!bearerToken) {
      throw new Error(
        'bearerToken is required. Pass it explicitly — browser builds never read env vars.'
      );
    }
    this.bearerToken = bearerToken;
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.bearerToken}`,
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`X API ${res.status}: ${body}`);
    }
    return res.json();
  }

  async getUserByUsername(username) {
    return this.request(
      `/users/by/username/${username}?user.fields=public_metrics,description,created_at`
    );
  }

  async getUserTweets(userId, { maxResults = 100 } = {}) {
    return this.request(
      `/users/${userId}/tweets?max_results=${maxResults}&tweet.fields=public_metrics,created_at,conversation_id`
    );
  }

  async getTweet(tweetId) {
    return this.request(
      `/tweets/${tweetId}?tweet.fields=public_metrics,created_at,conversation_id`
    );
  }

  async getFollowers(userId, { maxResults = 100, paginationToken } = {}) {
    const params = new URLSearchParams({ max_results: String(maxResults) });
    if (paginationToken) params.set('pagination_token', paginationToken);
    return this.request(`/users/${userId}/followers?${params}`);
  }
}
