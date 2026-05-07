/**
 * Shared constants for grok-pulse-mcp-server.
 *
 * Keep all magic numbers, URLs, and limits here — never inline them in tools.
 */

/** Server identity (reported via initialize handshake). */
export const SERVER_NAME = "grok-pulse-mcp-server";
export const SERVER_VERSION = "0.1.0";

/** GitHub REST API base. Octokit handles this internally; kept here for direct fetch fallbacks. */
export const GITHUB_API_BASE = "https://api.github.com";

/** xAI Grok API — OpenAI-compatible endpoint. */
export const XAI_API_BASE_DEFAULT = "https://api.x.ai/v1";
export const GROK_MODEL_DEFAULT = "grok-4-latest";

/** Maximum characters allowed in any tool response text content.
 *  Tools must check this and truncate with an actionable message. */
export const CHARACTER_LIMIT = 25_000;

/** Default HTTP timeout for outbound API calls. */
export const HTTP_TIMEOUT_MS = 30_000;

/** Pagination defaults — used by tools that list things. */
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

/** "Stale" PR threshold for pulse_today — your own PRs not updated in this many days. */
export const STALE_PR_DAYS_DEFAULT = 7;
