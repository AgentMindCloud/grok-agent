/**
 * Shared Zod schemas used across multiple tool input definitions.
 */

import { z } from "zod";

/** Output format toggle — every tool that returns data accepts this. */
export const ResponseFormatEnum = z.enum(["markdown", "json"]);
export type ResponseFormatT = z.infer<typeof ResponseFormatEnum>;

/** Standard pagination block — applies to listing tools. */
export const PaginationSchema = z.object({
  limit: z.number().int().min(1).max(100).default(20)
    .describe("Maximum results to return per section (1-100, default 20)."),
  offset: z.number().int().min(0).default(0)
    .describe("Number of results to skip for pagination (default 0)."),
});
