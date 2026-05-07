/**
 * Markdown formatters — convert structured pulse outputs to human-readable text.
 *
 * Markdown is the default response_format because most agent UIs render it nicely
 * and it preserves more semantic structure than raw text without overwhelming the agent.
 */

import type { PulseItem, PulseSections, PulseTodayOutput } from "../types.js";

/** Friendly relative-time string for an ISO timestamp. */
function relativeAge(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffMs = Date.now() - then;
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function formatItemLine(item: PulseItem): string {
  const repoLabel = item.repo ? `**${item.repo}**` : "**(global)**";
  const meta = item.meta?.number ? `#${item.meta.number}` : "";
  const ageLabel = relativeAge(item.updated_at);
  const titleLine = `${repoLabel}${meta ? ` ${meta}` : ""} — ${item.title} _(${ageLabel})_`;
  return `- ${titleLine} · [open](${item.url})`;
}

function formatSection(emoji: string, title: string, items: PulseItem[]): string {
  if (items.length === 0) return "";
  const lines = [`### ${emoji} ${title} (${items.length})`, ""];
  for (const item of items) lines.push(formatItemLine(item));
  lines.push("");
  return lines.join("\n");
}

/** Render a `PulseTodayOutput` to a markdown string. */
export function formatPulseTodayMarkdown(output: PulseTodayOutput): string {
  const lines: string[] = [];
  const total = output.totals.total_attention_items;

  lines.push(`# Pulse Today — @${output.user}`);
  lines.push(
    `*Generated ${new Date(output.generated_at).toUTCString()} · **${total}** item${total === 1 ? "" : "s"} need attention.*`
  );
  lines.push("");

  if (output.grok_summary) {
    lines.push("## Grok says");
    lines.push(output.grok_summary.trim());
    lines.push("");
  }

  // Order: highest-priority sections first.
  const sectionOrder: Array<{
    key: keyof PulseSections;
    emoji: string;
    title: string;
  }> = [
    { key: "failing_ci", emoji: "⚠️", title: "Failing CI" },
    { key: "review_requests", emoji: "🔍", title: "Review requests" },
    { key: "notifications", emoji: "🔔", title: "Notifications" },
    { key: "assigned_issues", emoji: "📌", title: "Assigned issues" },
    { key: "your_stale_prs", emoji: "🕒", title: "Stale PRs of yours" },
  ];

  for (const { key, emoji, title } of sectionOrder) {
    lines.push(formatSection(emoji, title, output.sections[key]));
  }

  if (total === 0) {
    lines.push("Nothing waiting. Go build something.");
    lines.push("");
  }

  if (output.truncated && output.truncation_message) {
    lines.push(`> _${output.truncation_message}_`);
  }

  return lines.join("\n").trimEnd();
}
