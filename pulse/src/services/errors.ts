/**
 * Centralized error handling.
 *
 * Tools NEVER throw to the protocol — they catch, run errors through `handleApiError`,
 * and return `{ isError: true, content: [{ type: "text", text: <msg> }] }`.
 *
 * Error messages must be:
 *   - actionable (tell the agent what to do next)
 *   - safe (never echo tokens or secrets)
 *   - concise (no stack traces or internal paths)
 */

import { AxiosError } from "axios";

const TOKEN_PATTERNS: RegExp[] = [
  /github_pat_[A-Za-z0-9_]+/g,
  /ghp_[A-Za-z0-9]+/g,
  /xai-[A-Za-z0-9_-]+/g,
  /Bearer\s+[A-Za-z0-9._-]+/gi,
];

/** Mask any token-shaped substring before returning to the LLM client. */
export function redactSecrets(s: string): string {
  let out = s;
  for (const pattern of TOKEN_PATTERNS) {
    out = out.replace(pattern, "***REDACTED***");
  }
  return out;
}

/** Map an arbitrary error into a clean, actionable string for the agent. */
export function handleApiError(error: unknown, context?: string): string {
  const prefix = context ? `[${context}] ` : "";

  // Axios errors — most common case for our HTTP-heavy server.
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const url = error.config?.url ?? "";
    const isGitHub = url.includes("github.com");
    const isXAI = url.includes("x.ai");

    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
      return `${prefix}Request timed out after 30s. Try again, reduce \`max_items_per_section\`, or narrow the date window.`;
    }

    if (status === undefined) {
      return `${prefix}Network error reaching ${url}: ${redactSecrets(error.message)}.`;
    }

    if (isGitHub) {
      return githubErrorMessage(prefix, status, error);
    }
    if (isXAI) {
      return xaiErrorMessage(prefix, status, error);
    }

    return `${prefix}HTTP ${status} from ${url}. ${redactSecrets(error.message)}`;
  }

  // Generic Error
  if (error instanceof Error) {
    return `${prefix}${redactSecrets(error.message)}`;
  }

  return `${prefix}Unexpected error: ${redactSecrets(String(error))}`;
}

function githubErrorMessage(prefix: string, status: number, err: AxiosError): string {
  switch (status) {
    case 401:
      return `${prefix}GitHub auth failed (401). Your GITHUB_TOKEN is invalid or expired. Generate a new fine-grained PAT at github.com/settings/personal-access-tokens.`;
    case 403: {
      const remaining = err.response?.headers?.["x-ratelimit-remaining"];
      const reset = err.response?.headers?.["x-ratelimit-reset"];
      if (remaining === "0") {
        const resetTime = reset ? new Date(Number(reset) * 1000).toISOString() : "unknown";
        return `${prefix}GitHub rate limit exhausted. Resets at ${resetTime}. Reduce request volume or wait.`;
      }
      return `${prefix}GitHub denied access (403). Check that your token's repository access includes the target repo and has the required Read scopes.`;
    }
    case 404:
      return `${prefix}GitHub returned 404. Check the \`owner/repo\` spelling, or that your token has access to the repository.`;
    case 422:
      return `${prefix}GitHub rejected the query (422). Likely a malformed search query — check date filters and qualifiers.`;
    default:
      return `${prefix}GitHub API error (${status}). ${redactSecrets(JSON.stringify(err.response?.data ?? {}))}`;
  }
}

function xaiErrorMessage(prefix: string, status: number, err: AxiosError): string {
  switch (status) {
    case 401:
      return `${prefix}xAI auth failed (401). Your XAI_API_KEY is invalid. Get one at console.x.ai.`;
    case 429: {
      const retryAfter = err.response?.headers?.["retry-after"];
      return `${prefix}xAI rate limit hit (429).${retryAfter ? ` Retry-After: ${retryAfter}s.` : ""} Reduce request frequency or batch fewer items per call.`;
    }
    case 400:
      return `${prefix}xAI rejected the request (400). Likely an invalid model name or malformed message — check XAI_MODEL.`;
    case 500:
    case 502:
    case 503:
      return `${prefix}xAI is temporarily unavailable (${status}). Try again in a few seconds.`;
    default:
      return `${prefix}xAI API error (${status}). ${redactSecrets(JSON.stringify(err.response?.data ?? {}))}`;
  }
}

/** Domain-specific error class — thrown by services, caught by tools. */
export class ConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigurationError";
  }
}
