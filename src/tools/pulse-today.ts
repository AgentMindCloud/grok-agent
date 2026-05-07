/**
 * Tool: pulse_today
 *
 * The headline tool. Returns a prioritized "what needs my attention today" list across
 * all of the authenticated user's owned repos, optionally synthesized by Grok.
 *
 * Workflow tool, not a wrapper: a single call fans out to ~6 parallel GitHub queries,
 * normalizes everything into PulseItems, optionally runs the batch through Grok for
 * prioritization commentary, and returns both human-readable markdown and structured JSON.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Octokit } from "@octokit/rest";

import { CHARACTER_LIMIT } from "../constants.js";
import { formatPulseTodayMarkdown } from "../formatters/markdown.js";
import { PulseTodayInputShape, PulseTodayInputSchema, type PulseTodayInput } from "../schemas/tools.js";
import { getOctokit, resolveUser } from "../services/github.js";
import { grokComplete } from "../services/grok.js";
import { handleApiError } from "../services/errors.js";
import type { PulseItem, PulseSections, PulseTodayOutput } from "../types.js";

// ---------------------------------------------------------------------------
// GitHub fetchers — each returns a typed array of PulseItems. Errors are
// caught here so a partial failure (e.g. CI fetch fails for one repo) does
// not collapse the whole tool.
// ---------------------------------------------------------------------------

async function fetchNotifications(o: Octokit, limit: number): Promise<PulseItem[]> {
  try {
    const { data } = await o.activity.listNotificationsForAuthenticatedUser({
      all: false,
      per_page: Math.min(limit, 50),
    });
    return data.slice(0, limit).map((n) => ({
      id: `notif:${n.id}`,
      kind: "notification",
      title: n.subject?.title ?? "(no title)",
      repo: n.repository?.full_name ?? null,
      url: n.subject?.url
        ? // notification subject URLs are API URLs; convert to html_url where possible
          n.subject.url
            .replace("api.github.com/repos", "github.com")
            .replace("/pulls/", "/pull/")
        : (n.repository?.html_url ?? "https://github.com"),
      updated_at: n.updated_at,
      meta: { reason: n.reason ?? "", type: n.subject?.type ?? "" },
    }));
  } catch (err) {
    // Surface as zero items + log to stderr; main tool keeps going.
    console.error("[pulse_today] notifications fetch failed:", handleApiError(err));
    return [];
  }
}

async function fetchReviewRequests(
  o: Octokit,
  user: string,
  limit: number
): Promise<PulseItem[]> {
  try {
    const { data } = await o.search.issuesAndPullRequests({
      q: `is:pr is:open review-requested:${user}`,
      sort: "updated",
      order: "desc",
      per_page: Math.min(limit, 50),
    });
    return data.items.slice(0, limit).map((i) => ({
      id: `review:${i.id}`,
      kind: "review_request",
      title: i.title,
      repo: extractRepoFromIssueUrl(i.repository_url),
      url: i.html_url,
      updated_at: i.updated_at,
      meta: { number: i.number, author: i.user?.login ?? "" },
    }));
  } catch (err) {
    console.error("[pulse_today] review_requests fetch failed:", handleApiError(err));
    return [];
  }
}

async function fetchAssignedIssues(
  o: Octokit,
  user: string,
  limit: number
): Promise<PulseItem[]> {
  try {
    const { data } = await o.search.issuesAndPullRequests({
      q: `is:open assignee:${user}`,
      sort: "updated",
      order: "desc",
      per_page: Math.min(limit, 50),
    });
    return data.items.slice(0, limit).map((i) => ({
      id: `assigned:${i.id}`,
      kind: "assigned_issue",
      title: i.title,
      repo: extractRepoFromIssueUrl(i.repository_url),
      url: i.html_url,
      updated_at: i.updated_at,
      meta: { number: i.number, is_pr: !!i.pull_request },
    }));
  } catch (err) {
    console.error("[pulse_today] assigned_issues fetch failed:", handleApiError(err));
    return [];
  }
}

async function fetchStaleOwnPRs(
  o: Octokit,
  user: string,
  daysStale: number,
  limit: number
): Promise<PulseItem[]> {
  try {
    const cutoff = new Date(Date.now() - daysStale * 24 * 3600 * 1000)
      .toISOString()
      .slice(0, 10); // YYYY-MM-DD
    const { data } = await o.search.issuesAndPullRequests({
      q: `is:pr is:open author:${user} updated:<${cutoff}`,
      sort: "updated",
      order: "asc", // oldest first — those need attention most
      per_page: Math.min(limit, 50),
    });
    return data.items.slice(0, limit).map((i) => ({
      id: `stalepr:${i.id}`,
      kind: "stale_own_pr",
      title: i.title,
      repo: extractRepoFromIssueUrl(i.repository_url),
      url: i.html_url,
      updated_at: i.updated_at,
      meta: { number: i.number, days_stale: daysFromNow(i.updated_at) },
    }));
  } catch (err) {
    console.error("[pulse_today] stale_own_prs fetch failed:", handleApiError(err));
    return [];
  }
}

async function fetchFailingCI(
  o: Octokit,
  user: string,
  limit: number
): Promise<PulseItem[]> {
  try {
    // Top 10 most-recently-pushed owned repos.
    const reposResp = await o.repos.listForAuthenticatedUser({
      affiliation: "owner",
      sort: "pushed",
      per_page: 10,
    });
    const repos = reposResp.data;

    // Parallel CI fetch — one most-recent failed run per repo.
    const ciResults = await Promise.all(
      repos.map(async (r) => {
        try {
          const { data } = await o.actions.listWorkflowRunsForRepo({
            owner: r.owner.login,
            repo: r.name,
            status: "failure",
            per_page: 1,
          });
          if (data.workflow_runs.length === 0) return null;
          const run = data.workflow_runs[0];
          const item: PulseItem = {
            id: `ci:${run.id}`,
            kind: "ci_failure",
            title: `${run.name ?? "workflow"} failed on ${run.head_branch ?? "?"}`,
            repo: r.full_name,
            url: run.html_url,
            updated_at: run.updated_at,
            meta: {
              run_number: run.run_number,
              event: run.event,
              conclusion: run.conclusion ?? "",
            },
          };
          return item;
        } catch {
          // Per-repo CI fetch failure is silent — many repos have no Actions.
          return null;
        }
      })
    );

    return ciResults
      .filter((x): x is PulseItem => x !== null)
      .slice(0, limit);
  } catch (err) {
    console.error("[pulse_today] failing_ci fetch failed:", handleApiError(err));
    return [];
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractRepoFromIssueUrl(repoUrl: string | undefined | null): string | null {
  // GitHub search returns repository_url like "https://api.github.com/repos/{owner}/{repo}"
  if (!repoUrl) return null;
  const m = /repos\/([^/]+\/[^/]+)$/.exec(repoUrl);
  return m ? m[1] : null;
}

function daysFromNow(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / (24 * 3600 * 1000));
}

async function maybeGrokSummary(sections: PulseSections, totalItems: number): Promise<string | undefined> {
  if (totalItems === 0) return undefined;

  // Build a compact JSON representation for Grok — strip URLs and IDs, keep semantic content.
  const compact = {
    failing_ci: sections.failing_ci.map((i) => ({ repo: i.repo, title: i.title, age_days: daysFromNow(i.updated_at) })),
    review_requests: sections.review_requests.map((i) => ({ repo: i.repo, title: i.title, age_days: daysFromNow(i.updated_at) })),
    notifications: sections.notifications.map((i) => ({ repo: i.repo, title: i.title, reason: i.meta?.reason })),
    assigned_issues: sections.assigned_issues.map((i) => ({ repo: i.repo, title: i.title, age_days: daysFromNow(i.updated_at) })),
    your_stale_prs: sections.your_stale_prs.map((i) => ({ repo: i.repo, title: i.title, days_stale: i.meta?.days_stale })),
  };

  const systemPrompt = `You are a senior engineering coach for builders shipping in the xAI/X/Grok ecosystem. You receive a JSON dump of "attention items" (failing CI, PR review requests, notifications, assigned issues, your stale PRs).

Return 2-4 sentences in plain prose. No headers, no markdown lists, no preamble. Be direct and specific:
- Name 1-3 actual items by repo + title
- Say what to do FIRST and why
- If failing CI exists, it's almost always the answer
- Keep the tone sharp, opinionated, and honest. No fluff.

If everything is empty, say "Inbox zero. Go build."`;

  return await grokComplete(
    [
      { role: "system", content: systemPrompt },
      { role: "user", content: JSON.stringify(compact) },
    ],
    { temperature: 0.4, max_tokens: 350 }
  );
}

// ---------------------------------------------------------------------------
// Tool registration
// ---------------------------------------------------------------------------

const TOOL_DESCRIPTION = `Returns the prioritized "what needs your attention today" list across all your owned GitHub repositories.

Pulls in parallel: unread notifications, PRs awaiting your review, issues assigned to you, your own stale PRs (not updated in N days), and failing CI runs across your top-10 most-recently-pushed repos. Optionally runs the batch through Grok (xAI) for a 2-4 sentence prioritization commentary.

Args:
  - user (string, optional): GitHub login. Defaults to the token's authenticated user.
  - include_grok_summary (boolean, default true): Run Grok for a prioritized take. Set false for raw data only.
  - max_items_per_section (int 1-50, default 10): Cap per section.
  - stale_pr_days (int 1-90, default 7): Threshold for "stale own PR".
  - response_format ('markdown' | 'json', default 'markdown').

Returns (structured):
  {
    generated_at: ISO timestamp,
    user: string,
    sections: {
      notifications: PulseItem[],
      review_requests: PulseItem[],
      assigned_issues: PulseItem[],
      your_stale_prs: PulseItem[],
      failing_ci: PulseItem[]
    },
    totals: { total_attention_items: number, by_section: Record<...> },
    grok_summary?: string
  }

Use this tool when:
  - The user asks "what should I work on today?", "what's waiting for me?", "what's blocked?", or similar attention/triage questions.
  - The user wants a daily standup-style summary across their GitHub work.

Do NOT use for:
  - Single-repo summaries (use summarize_repo_activity instead).
  - Multi-week digests (use weekly_digest instead).
  - Mutating GitHub state (this tool is read-only).

Errors:
  - Returns a redacted error message starting with "[pulse_today]" if GITHUB_TOKEN or XAI_API_KEY are misconfigured.
  - Partial failures (one section fails to load) are logged to stderr and the section returns empty — the tool still succeeds with whatever it could fetch.`;

export function registerPulseToday(server: McpServer): void {
  server.registerTool(
    "pulse_today",
    {
      title: "Today's Attention List",
      description: TOOL_DESCRIPTION,
      inputSchema: PulseTodayInputShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (rawParams) => {
      try {
        // Strict parse — rejects unknown fields with a clear error.
        const params: PulseTodayInput = PulseTodayInputSchema.parse(rawParams);

        const o = getOctokit();
        const user = await resolveUser(params.user);
        const limit = params.max_items_per_section;

        // Fan out — five sections in parallel.
        const [notifications, review_requests, assigned_issues, your_stale_prs, failing_ci] =
          await Promise.all([
            fetchNotifications(o, limit),
            fetchReviewRequests(o, user, limit),
            fetchAssignedIssues(o, user, limit),
            fetchStaleOwnPRs(o, user, params.stale_pr_days, limit),
            fetchFailingCI(o, user, limit),
          ]);

        const sections: PulseSections = {
          notifications,
          review_requests,
          assigned_issues,
          your_stale_prs,
          failing_ci,
        };

        const totalItems =
          notifications.length +
          review_requests.length +
          assigned_issues.length +
          your_stale_prs.length +
          failing_ci.length;

        // Grok pass — only if requested AND there's something to summarize.
        let grok_summary: string | undefined;
        if (params.include_grok_summary && totalItems > 0) {
          try {
            grok_summary = await maybeGrokSummary(sections, totalItems);
          } catch (err) {
            // Grok failure should not kill the whole tool — return raw data + an error note.
            console.error("[pulse_today] grok summary failed:", handleApiError(err));
            grok_summary = `_(Grok summary unavailable: ${handleApiError(err, "grok_summary")})_`;
          }
        } else if (params.include_grok_summary && totalItems === 0) {
          grok_summary = "Inbox zero. Go build.";
        }

        const output: PulseTodayOutput = {
          generated_at: new Date().toISOString(),
          user,
          sections,
          totals: {
            total_attention_items: totalItems,
            by_section: {
              notifications: notifications.length,
              review_requests: review_requests.length,
              assigned_issues: assigned_issues.length,
              your_stale_prs: your_stale_prs.length,
              failing_ci: failing_ci.length,
            },
          },
          ...(grok_summary !== undefined ? { grok_summary } : {}),
        };

        // Format text content per response_format.
        let textContent =
          params.response_format === "markdown"
            ? formatPulseTodayMarkdown(output)
            : JSON.stringify(output, null, 2);

        // Enforce CHARACTER_LIMIT.
        if (textContent.length > CHARACTER_LIMIT) {
          output.truncated = true;
          output.truncation_message = `Response truncated from ${textContent.length} to ~${CHARACTER_LIMIT} chars. Reduce max_items_per_section or set include_grok_summary=false.`;
          // Naive truncation — drop oldest items in the largest section first.
          // For simplicity in v0.2, just clip the rendered text and append the message.
          textContent =
            textContent.slice(0, CHARACTER_LIMIT - 200) +
            `\n\n> _${output.truncation_message}_`;
        }

        return {
          content: [{ type: "text", text: textContent }],
          structuredContent: output as unknown as Record<string, unknown>,
        };
      } catch (err) {
        return {
          isError: true,
          content: [
            {
              type: "text",
              text: handleApiError(err, "pulse_today"),
            },
          ],
        };
      }
    }
  );
}
