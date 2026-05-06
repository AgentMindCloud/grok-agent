/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

// Build-time fetch for GitHub repo stats (stars, forks).
// Call only from Server Components or prebuild scripts — never client-side.

export interface GitHubStats {
  stars: number;
  forks: number;
  fetchedAt: string;
}

// TODO: honour GITHUB_TOKEN env var to avoid rate-limits in CI
export async function fetchGitHubStats(
  repo = 'AgentMindCloud/grok-agent',
): Promise<GitHubStats> {
  try {
    const res = await fetch(`https://api.github.com/repos/${repo}`, {
      headers: { Accept: 'application/vnd.github+json' },
      next: { revalidate: 3600 },
    });
    if (!res.ok) throw new Error(`GitHub API ${res.status}`);
    const data = (await res.json()) as { stargazers_count: number; forks_count: number };
    return {
      stars: data.stargazers_count ?? 0,
      forks: data.forks_count ?? 0,
      fetchedAt: new Date().toISOString(),
    };
  } catch {
    return { stars: 0, forks: 0, fetchedAt: new Date().toISOString() };
  }
}
