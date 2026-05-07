/**
 * GitHub service layer — wraps Octokit and exposes only the calls our tools need.
 *
 * Keeping this thin and explicit makes it easy to swap auth modes (PAT vs OAuth)
 * later, and it gives us a single place to mock for tests.
 */

import { Octokit } from "@octokit/rest";
import { ConfigurationError } from "./errors.js";

let _octokit: Octokit | null = null;
let _cachedUser: string | null = null;

/** Lazily construct the Octokit instance from env. Throws ConfigurationError if no token. */
export function getOctokit(): Octokit {
  if (_octokit) return _octokit;

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    throw new ConfigurationError(
      "GITHUB_TOKEN environment variable is required. See .env.example."
    );
  }

  _octokit = new Octokit({
    auth: token,
    userAgent: "grok-pulse-mcp-server/0.1.0",
    request: { timeout: 30_000 },
  });
  return _octokit;
}

/** Resolve the GitHub user we operate as — env override first, then /user lookup. */
export async function resolveUser(override?: string): Promise<string> {
  if (override) return override;
  if (process.env.GITHUB_USER) return process.env.GITHUB_USER;
  if (_cachedUser) return _cachedUser;

  const { data } = await getOctokit().users.getAuthenticated();
  _cachedUser = data.login;
  return _cachedUser;
}

/** Reset cached state — used in tests. */
export function _resetGitHubCacheForTests(): void {
  _octokit = null;
  _cachedUser = null;
}
