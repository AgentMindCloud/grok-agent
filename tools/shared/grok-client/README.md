# grok-client

> Minimal Node wrapper around xAI's Grok API. Used by every AI-writing tool in the toolkit.

## Install

```bash
cd shared/grok-client
npm install
```

## Usage

```js
const GrokClient = require('@x-platform-toolkit/grok-client');

const grok = new GrokClient({ apiKey: process.env.XAI_API_KEY });

const reply = await grok.complete('Write a sharp X reply to: "Hot take, remote work killed innovation"');
console.log(reply);
```

## Environment

Set `XAI_API_KEY` in your environment, or pass `apiKey` to the constructor.

## Methods

- `chat(messages, { temperature, maxTokens })` — Full chat-completions call
- `complete(prompt, options)` — Shortcut for single-user-turn completions

## Why Grok

Grok has native access to the X firehose. Other LLMs don't. For X-native tools, Grok is the correct default.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
