/**
 * Shared types used across services and tools.
 *
 * These describe the *internal* shapes we pass around. Tool input/output schemas
 * live with each tool in `src/tools/*.ts` to keep tool contracts colocated.
 */

/** A single item in any pulse section — normalized across notifications, issues, PRs, CI runs. */
export interface PulseItem {
  /** Stable identifier — for issues/PRs this is the html_url, for notifs the thread_id. */
  id: string;
  /** Human-readable kind (e.g. "pr_review_request", "issue_assigned", "ci_failure"). */
  kind: PulseItemKind;
  /** Short title — e.g. PR title, issue title, notification subject. */
  title: string;
  /** owner/repo or null for global notifications. */
  repo: string | null;
  /** Direct URL to view the item on github.com. */
  url: string;
  /** ISO timestamp of last activity / update. */
  updated_at: string;
  /** Optional priority hint set by the server before Grok sees it (1=highest). */
  priority?: number;
  /** Free-form extra context (issue number, run id, conclusion, etc.) — passed to Grok verbatim. */
  meta?: Record<string, string | number | boolean | null>;
}

export type PulseItemKind =
  | "notification"
  | "review_request"
  | "assigned_issue"
  | "stale_own_pr"
  | "ci_failure";

/** Per-section grouping returned by pulse_today. */
export interface PulseSections {
  notifications: PulseItem[];
  review_requests: PulseItem[];
  assigned_issues: PulseItem[];
  your_stale_prs: PulseItem[];
  failing_ci: PulseItem[];
}

/** Output shape of pulse_today (also referenced by next_action). */
export interface PulseTodayOutput {
  generated_at: string;
  user: string;
  sections: PulseSections;
  totals: {
    total_attention_items: number;
    by_section: Record<keyof PulseSections, number>;
  };
  grok_summary?: string;
  truncated?: boolean;
  truncation_message?: string;
}

/** Compact repo-activity rollup used by summarize_repo_activity / weekly_digest. */
export interface RepoActivitySummary {
  repo: string;
  window_days: number;
  raw_counts: {
    commits: number;
    merged_prs: number;
    opened_issues: number;
    closed_issues: number;
    releases: number;
  };
  top_contributors: Array<{ login: string; commits: number }>;
  grok_summary?: string;
}

/** Response format toggle — every tool that returns data accepts this. */
export type ResponseFormat = "markdown" | "json";
