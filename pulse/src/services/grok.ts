/**
 * Grok service layer — wraps the xAI chat-completions endpoint.
 *
 * xAI exposes an OpenAI-compatible API. We use plain axios rather than the OpenAI SDK
 * to keep dependencies minimal and the request shape transparent.
 */

import axios, { AxiosInstance } from "axios";
import {
  GROK_MODEL_DEFAULT,
  HTTP_TIMEOUT_MS,
  XAI_API_BASE_DEFAULT,
} from "../constants.js";
import { ConfigurationError } from "./errors.js";

export interface GrokMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface GrokCompletionOptions {
  /** Model override. Defaults to env XAI_MODEL or grok-4-latest. */
  model?: string;
  /** Sampling temperature. Defaults to 0.4 — slightly creative, mostly grounded. */
  temperature?: number;
  /** Max tokens to generate. Defaults to 800 — enough for paragraph-length summaries. */
  max_tokens?: number;
}

let _client: AxiosInstance | null = null;

function getClient(): AxiosInstance {
  if (_client) return _client;

  const apiKey = process.env.XAI_API_KEY;
  if (!apiKey) {
    throw new ConfigurationError(
      "XAI_API_KEY environment variable is required. Get one at console.x.ai."
    );
  }

  const baseURL = process.env.XAI_BASE_URL || XAI_API_BASE_DEFAULT;

  _client = axios.create({
    baseURL,
    timeout: HTTP_TIMEOUT_MS,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });
  return _client;
}

/** Run a chat completion against Grok. Returns the assistant message text. */
export async function grokComplete(
  messages: GrokMessage[],
  options: GrokCompletionOptions = {}
): Promise<string> {
  const model = options.model || process.env.XAI_MODEL || GROK_MODEL_DEFAULT;

  const response = await getClient().post("/chat/completions", {
    model,
    messages,
    temperature: options.temperature ?? 0.4,
    max_tokens: options.max_tokens ?? 800,
  });

  const text = response.data?.choices?.[0]?.message?.content;
  if (typeof text !== "string") {
    throw new Error(
      `Unexpected Grok response shape — no choices[0].message.content. Got: ${JSON.stringify(response.data).slice(0, 200)}`
    );
  }
  return text;
}

export function _resetGrokCacheForTests(): void {
  _client = null;
}
