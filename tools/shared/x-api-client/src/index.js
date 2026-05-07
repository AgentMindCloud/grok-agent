/**
 * x-api-client — Shared X API v2 wrapper for x-platform-toolkit
 * Part of the grok-install family · Apache 2.0
 */

const API_BASE = 'https://api.x.com/2';

class XApiClient {
  constructor({ bearerToken } = {}) {
    this.bearerToken = bearerToken || process.env.X_BEARER_TOKEN;
    if (!this.bearerToken) {
      throw new Error('X_BEARER_TOKEN required. Set env var or pass bearerToken option.');
    }
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.bearerToken}`,
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`X API ${res.status}: ${body}`);
    }
    return res.json();
  }

  async getUserByUsername(username) {
    return this.request(`/users/by/username/${username}?user.fields=public_metrics,description,created_at`);
  }

  async getUserTweets(userId, { maxResults = 100 } = {}) {
    return this.request(`/users/${userId}/tweets?max_results=${maxResults}&tweet.fields=public_metrics,created_at,conversation_id`);
  }

  async getTweet(tweetId) {
    return this.request(`/tweets/${tweetId}?tweet.fields=public_metrics,created_at,conversation_id`);
  }

  async getFollowers(userId, { maxResults = 100, paginationToken } = {}) {
    const params = new URLSearchParams({ max_results: maxResults });
    if (paginationToken) params.set('pagination_token', paginationToken);
    return this.request(`/users/${userId}/followers?${params}`);
  }
}

module.exports = XApiClient;
