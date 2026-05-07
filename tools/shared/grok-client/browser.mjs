/**
 * grok-client — browser / ESM entry for x-platform-toolkit.
 * Part of the grok-install family · Apache 2.0
 *
 * Import only from a bundler context (Vite / esbuild / Rollup / Webpack).
 * Node consumers should import the package's main CJS entry instead.
 *
 * No `process.env`, no node-only APIs. Constructor requires `apiKey`.
 */

const API_BASE = 'https://api.x.ai/v1';

export default class GrokClient {
  constructor({ apiKey, model = 'grok-2-latest', baseURL = API_BASE } = {}) {
    if (!apiKey) {
      throw new Error('apiKey is required. Pass it explicitly — browser builds never read env vars.');
    }
    this.apiKey = apiKey;
    this.model = model;
    this.baseURL = baseURL;
  }

  async chat(messages, { temperature = 0.7, maxTokens = 1024, tools, toolChoice } = {}) {
    const body = {
      model: this.model,
      messages,
      temperature,
      max_tokens: maxTokens,
    };
    if (tools) body.tools = tools;
    if (toolChoice) body.tool_choice = toolChoice;

    const res = await fetch(`${this.baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errBody = await res.text();
      throw new Error(`Grok API ${res.status}: ${errBody}`);
    }

    const data = await res.json();
    const message = data.choices[0].message;

    if (tools) {
      return { content: message.content ?? null, tool_calls: message.tool_calls ?? [] };
    }
    return message.content;
  }

  async complete(prompt, options = {}) {
    return this.chat([{ role: 'user', content: prompt }], options);
  }

  async *chatStream(messages, { temperature = 0.7, maxTokens = 1024 } = {}) {
    const res = await fetch(`${this.baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        temperature,
        max_tokens: maxTokens,
        stream: true,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      throw new Error(`Grok API ${res.status}: ${errBody}`);
    }
    if (!res.body) {
      throw new Error('Grok API stream: response body is empty.');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          const line = frame.trim();
          if (!line.startsWith('data:')) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          if (payload === '[DONE]') return;

          let event;
          try {
            event = JSON.parse(payload);
          } catch (_err) {
            continue;
          }
          const token = event?.choices?.[0]?.delta?.content;
          if (token) yield token;
        }
      }
    } finally {
      try {
        reader.releaseLock();
      } catch (_err) {
        // reader already released
      }
    }
  }
}
