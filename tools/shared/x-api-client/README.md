# x-api-client

> Thin Node wrapper around X API v2 for every tool in the toolkit that touches X data.

## Install

```bash
cd shared/x-api-client
npm install
```

## Usage

```js
const XApiClient = require('@x-platform-toolkit/x-api-client');

const client = new XApiClient({ bearerToken: process.env.X_BEARER_TOKEN });

const user = await client.getUserByUsername('elonmusk');
const tweets = await client.getUserTweets(user.data.id, { maxResults: 100 });
```

## Environment

Set `X_BEARER_TOKEN` in your environment, or pass `bearerToken` to the constructor.

## Methods

- `getUserByUsername(username)` — Fetch a user profile with public metrics
- `getUserTweets(userId, { maxResults })` — Fetch recent tweets for a user
- `getTweet(tweetId)` — Fetch a single tweet with public metrics
- `getFollowers(userId, { maxResults, paginationToken })` — Paginate through followers
- `request(endpoint, options)` — Raw request for endpoints not yet wrapped

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
