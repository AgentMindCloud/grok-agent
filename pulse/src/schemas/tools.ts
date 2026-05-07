/**
 * Per-tool Zod input schemas.
 *
 * For each tool we export both:
 *   - a raw shape (`*Shape`) — passed to `server.registerTool({ inputSchema })`
 *   - a strict schema (`*Schema`) + inferred type — used for runtime parsing inside the handler
 */

import { z } from "zod";
import { ResponseFormatEnum } from "./common.js";

// ----------------------------------------------------------------------------
// pulse_today
// ----------------------------------------------------------------------------

export const PulseTodayInputShape = {
  user: z
    .string()
    .min(1)
    .max(100)
    .optional()
    .describe(
      "GitHub login (e.g. 'octocat') to scope the pulse to. Defaults to the authenticated user from the token."
    ),
  include_grok_summary: z
    .boolean()
    .default(true)
    .describe(
      "If true, sends the collected items to Grok for a 2-4 sentence prioritization take. Set false for raw fetch only (faster, no xAI API call)."
    ),
  max_items_per_section: z
    .number()
    .int()
    .min(1)
    .max(50)
    .default(10)
    .describe(
      "Maximum items returned per section (notifications, review_requests, assigned_issues, your_stale_prs, failing_ci). Default 10."
    ),
  stale_pr_days: z
    .number()
    .int()
    .min(1)
    .max(90)
    .default(7)
    .describe(
      "How many days a PR you authored can sit without updates before counting as 'stale'. Default 7."
    ),
  response_format: ResponseFormatEnum.default("markdown").describe(
    "Output format: 'markdown' for human-readable, 'json' for machine-readable. Default 'markdown'."
  ),
} as const;

export const PulseTodayInputSchema = z.object(PulseTodayInputShape).strict();
export type PulseTodayInput = z.infer<typeof PulseTodayInputSchema>;
