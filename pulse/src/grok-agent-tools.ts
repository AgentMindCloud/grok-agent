// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Built for xAI, X, Grok and the ecosystem community. ❤️
//
// Dynamic MCP tool registration for every Grok Agent OS template.
//
// Walks `../templates/<category>/<slug>/grok-agent.yaml` at server boot,
// parses each manifest with js-yaml, and emits one MCP tool per agent
// named `grok-agent-<slug>`. Each tool exposes a single `action` enum:
//
//   - "describe"        -> returns the parsed manifest summary (display name,
//                          tagline, description, kind, category, prerequisites,
//                          tags, public APIs, safety profile fields).
//   - "install_command" -> returns the PowerShell-first install command and
//                          the prerequisites list copy-pasteable to a Windows
//                          11 + PowerShell session.
//   - "manifest_url"    -> returns the canonical GitHub raw + folder URLs for
//                          the manifest plus the install command.
//
// This file is the bridge that lets any MCP client (Claude Desktop, Cursor,
// custom) discover the full Grok Agent OS catalog as first-class tools.
//
// Pattern lineage: the directory walk + yaml.load + category derivation
// pattern is copied from marketplace/lib/manifests.ts (same repo, same
// author). It is not imported because pulse must stay self-contained per
// the Hard Six rule (Windows-native, no cross-package coupling at runtime).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";
import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

// ---------------------------------------------------------------------------
// Types — minimal local view of the v2.15 manifest. Intentionally permissive
// (`unknown` for nested blocks we do not surface) so a future v2.16 field
// addition does not break tool registration.
// ---------------------------------------------------------------------------

/** The v2.15 manifest categories we surface in pulse. */
export type GrokAgentCategory =
  | "super-agents"
  | "finance"
  | "creator"
  | "general"
  | "x-native";

/** Parsed manifest shape — only the fields this tool reads. */
export interface GrokAgentManifest {
  version?: string;
  kind?: string;
  name?: string;
  description?: string;
  author?: string;
  license?: string;
  metadata?: {
    display_name?: string;
    tagline?: string;
    categories?: string[];
    tags?: string[];
    language?: string;
  };
  install?: {
    one_click?: boolean;
    install_command?: string;
    command?: string;
    prerequisites?: string[];
  };
  windows?: {
    launcher?: string;
    appdata_folder?: string;
    log_folder?: string;
    cache_folder?: string;
    min_powershell_version?: string;
    requires_admin?: boolean;
    chrome_only?: boolean;
  };
  grok?: {
    model?: string;
    temperature?: number;
    max_tokens?: number;
    vision?: boolean;
    tool_calling?: boolean;
  };
  public_apis?: Array<{ name?: string; url?: string }>;
  safety?: Record<string, unknown>;
}

/** Normalized record built once per manifest at boot time. */
export interface GrokAgentEntry {
  slug: string;
  category: GrokAgentCategory;
  displayName: string;
  tagline: string;
  description: string;
  manifestPath: string; // absolute on disk
  repoRelativePath: string; // e.g. templates/finance/x-money-companion-dashboard/grok-agent.yaml
  installCommand: string;
  prerequisites: string[];
  githubFolderUrl: string;
  githubManifestUrl: string;
  manifest: GrokAgentManifest;
}

/** Action enum — kept narrow on purpose so MCP clients see a clear contract. */
export const GrokAgentActionSchema = z.enum([
  "describe",
  "install_command",
  "manifest_url",
]);
export type GrokAgentAction = z.infer<typeof GrokAgentActionSchema>;

// ---------------------------------------------------------------------------
// Repo discovery
// ---------------------------------------------------------------------------

/** Default GitHub coordinates — overridable via env vars for forks. */
const DEFAULT_GITHUB_OWNER = "AgentMindCloud";
const DEFAULT_GITHUB_REPO = "grok-agent";
const DEFAULT_GITHUB_BRANCH = "main";

/** Categories scanned, in priority order for catalog display. */
const CATEGORIES: GrokAgentCategory[] = [
  "super-agents",
  "finance",
  "creator",
  "general",
  "x-native",
];

/**
 * Resolve the templates root.
 *
 * Order of resolution:
 *   1. `GROK_AGENT_TEMPLATES_DIR` env var (explicit override).
 *   2. `<this-file>/../../../templates` relative to the compiled output
 *      (works for both `tsx watch src/index.ts` and `node dist/index.js`).
 *   3. `<cwd>/templates` (final fallback for unusual launches).
 *
 * Returns null if no candidate exists — registration becomes a no-op so the
 * rest of the server still boots even if pulse is published standalone.
 */
export function resolveTemplatesRoot(): string | null {
  const envOverride = process.env.GROK_AGENT_TEMPLATES_DIR;
  if (envOverride && fs.existsSync(envOverride)) return envOverride;

  // Walk upward from this module's directory looking for `templates/`.
  // Handles dev (src/) and prod (dist/) layouts uniformly.
  try {
    const here = path.dirname(fileURLToPath(import.meta.url));
    const candidates = [
      path.resolve(here, "..", "..", "templates"),
      path.resolve(here, "..", "..", "..", "templates"),
      path.resolve(here, "..", "templates"),
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) return candidate;
    }
  } catch {
    // import.meta.url unavailable in some sandboxed runners — fall through.
  }

  const cwdCandidate = path.resolve(process.cwd(), "templates");
  if (fs.existsSync(cwdCandidate)) return cwdCandidate;

  return null;
}

function deriveDisplayName(manifest: GrokAgentManifest, slug: string): string {
  const explicit = manifest.metadata?.display_name;
  if (explicit && typeof explicit === "string") return explicit;
  const name = manifest.name;
  if (name && /[A-Z\s]/.test(name)) return name;
  return slug
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function deriveTagline(manifest: GrokAgentManifest): string {
  const tagline = manifest.metadata?.tagline;
  if (typeof tagline === "string" && tagline.trim().length > 0) return tagline;
  const description = manifest.description;
  if (typeof description === "string" && description.trim().length > 0) {
    // First sentence of description, capped at 200 chars.
    const firstSentence = description.split(/(?<=[.!?])\s/)[0] ?? description;
    return firstSentence.slice(0, 200);
  }
  return "Grok Agent OS template.";
}

function deriveInstallCommand(manifest: GrokAgentManifest, slug: string): string {
  const explicit = manifest.install?.install_command ?? manifest.install?.command;
  if (typeof explicit === "string" && explicit.trim().length > 0) return explicit;
  return `grok-agent install ${slug}`;
}

function derivePrerequisites(manifest: GrokAgentManifest): string[] {
  const prereqs = manifest.install?.prerequisites;
  if (Array.isArray(prereqs)) {
    return prereqs.filter((p): p is string => typeof p === "string");
  }
  return ["Windows 11", "Python 3.12+", "PowerShell 5.1+"];
}

function buildGithubUrls(
  category: GrokAgentCategory,
  slug: string,
  owner: string,
  repo: string,
  branch: string
): { folder: string; manifest: string } {
  const folder = `https://github.com/${owner}/${repo}/tree/${branch}/templates/${category}/${slug}`;
  const manifestUrl = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/templates/${category}/${slug}/grok-agent.yaml`;
  return { folder, manifest: manifestUrl };
}

/**
 * Walk every category folder, read every grok-agent.yaml, return the full
 * normalized catalog. Failures (unparseable YAML, missing manifest) are
 * logged to stderr and skipped — one bad template must not block the rest.
 */
export function loadGrokAgentCatalog(
  templatesRoot: string,
  options: { owner?: string; repo?: string; branch?: string } = {}
): GrokAgentEntry[] {
  const owner = options.owner ?? process.env.GROK_AGENT_GH_OWNER ?? DEFAULT_GITHUB_OWNER;
  const repo = options.repo ?? process.env.GROK_AGENT_GH_REPO ?? DEFAULT_GITHUB_REPO;
  const branch = options.branch ?? process.env.GROK_AGENT_GH_BRANCH ?? DEFAULT_GITHUB_BRANCH;

  const entries: GrokAgentEntry[] = [];

  for (const category of CATEGORIES) {
    const categoryDir = path.join(templatesRoot, category);
    if (!fs.existsSync(categoryDir)) continue;

    let slugs: string[];
    try {
      slugs = fs
        .readdirSync(categoryDir, { withFileTypes: true })
        .filter((d) => d.isDirectory() && !d.name.startsWith("_") && !d.name.startsWith("."))
        .map((d) => d.name);
    } catch (err) {
      console.error(`[grok-agent-tools] failed to list ${categoryDir}:`, err);
      continue;
    }

    for (const slug of slugs) {
      const manifestPath = path.join(categoryDir, slug, "grok-agent.yaml");
      if (!fs.existsSync(manifestPath)) continue;

      let manifest: GrokAgentManifest;
      try {
        const raw = fs.readFileSync(manifestPath, "utf8");
        const parsed = yaml.load(raw);
        if (!parsed || typeof parsed !== "object") {
          console.error(`[grok-agent-tools] skipping ${manifestPath}: empty or non-object manifest`);
          continue;
        }
        manifest = parsed as GrokAgentManifest;
      } catch (err) {
        console.error(`[grok-agent-tools] failed to parse ${manifestPath}:`, err);
        continue;
      }

      const urls = buildGithubUrls(category, slug, owner, repo, branch);
      const repoRelativePath = path.posix.join("templates", category, slug, "grok-agent.yaml");

      entries.push({
        slug,
        category,
        displayName: deriveDisplayName(manifest, slug),
        tagline: deriveTagline(manifest),
        description:
          typeof manifest.description === "string" ? manifest.description : "",
        manifestPath,
        repoRelativePath,
        installCommand: deriveInstallCommand(manifest, slug),
        prerequisites: derivePrerequisites(manifest),
        githubFolderUrl: urls.folder,
        githubManifestUrl: urls.manifest,
        manifest,
      });
    }
  }

  return entries;
}

// ---------------------------------------------------------------------------
// Tool builder
// ---------------------------------------------------------------------------

/**
 * Build the per-action response for a single agent entry.
 *
 * Returned strings are markdown — they render cleanly in MCP clients that
 * surface the response as text content.
 */
export function handleGrokAgentTool(entry: GrokAgentEntry, action: GrokAgentAction): {
  text: string;
  data: Record<string, unknown>;
} {
  switch (action) {
    case "describe": {
      const lines: string[] = [
        `# ${entry.displayName}`,
        "",
        `> ${entry.tagline}`,
        "",
        `- **Slug**: \`${entry.slug}\``,
        `- **Category**: ${entry.category}`,
        `- **Kind**: ${entry.manifest.kind ?? "unspecified"}`,
        `- **Author**: ${entry.manifest.author ?? "@JanSol0s"}`,
        `- **License**: ${entry.manifest.license ?? "Apache-2.0"}`,
        `- **Manifest version**: ${entry.manifest.version ?? "unknown"}`,
      ];
      if (entry.manifest.grok?.model) {
        lines.push(`- **Grok model**: ${entry.manifest.grok.model}`);
      }
      const tags = entry.manifest.metadata?.tags ?? [];
      if (tags.length > 0) {
        lines.push(`- **Tags**: ${tags.join(", ")}`);
      }
      const apis = entry.manifest.public_apis ?? [];
      if (apis.length > 0) {
        const apiNames = apis.map((a) => a.name ?? "(unnamed)").join(", ");
        lines.push(`- **Public APIs**: ${apiNames}`);
      }
      if (entry.description) {
        lines.push("", "## Description", "", entry.description);
      }
      return {
        text: lines.join("\n"),
        data: {
          slug: entry.slug,
          category: entry.category,
          display_name: entry.displayName,
          tagline: entry.tagline,
          description: entry.description,
          kind: entry.manifest.kind ?? null,
          author: entry.manifest.author ?? null,
          license: entry.manifest.license ?? null,
          manifest_version: entry.manifest.version ?? null,
          tags: tags,
          public_apis: apis.map((a) => a.name ?? null),
          grok_model: entry.manifest.grok?.model ?? null,
        },
      };
    }
    case "install_command": {
      const prereqs = entry.prerequisites
        .map((p) => `- ${p}`)
        .join("\n");
      const text = [
        `# Install: ${entry.displayName}`,
        "",
        "## Prerequisites",
        "",
        prereqs,
        "",
        "## PowerShell command (Windows 11)",
        "",
        "```powershell",
        entry.installCommand,
        "```",
        "",
        `Manifest folder: ${entry.githubFolderUrl}`,
      ].join("\n");
      return {
        text,
        data: {
          slug: entry.slug,
          install_command: entry.installCommand,
          prerequisites: entry.prerequisites,
          github_folder_url: entry.githubFolderUrl,
        },
      };
    }
    case "manifest_url": {
      const text = [
        `# Manifest URLs: ${entry.displayName}`,
        "",
        `- **Folder (GitHub)**: ${entry.githubFolderUrl}`,
        `- **Raw manifest (YAML)**: ${entry.githubManifestUrl}`,
        `- **Repo-relative path**: \`${entry.repoRelativePath}\``,
        "",
        "## Install command",
        "",
        "```powershell",
        entry.installCommand,
        "```",
      ].join("\n");
      return {
        text,
        data: {
          slug: entry.slug,
          github_folder_url: entry.githubFolderUrl,
          github_manifest_url: entry.githubManifestUrl,
          repo_relative_path: entry.repoRelativePath,
          install_command: entry.installCommand,
        },
      };
    }
  }
}

/**
 * Register every Grok Agent OS template as an MCP tool on the given server.
 *
 * Side-effects only — the function does the file system walk and the
 * `server.registerTool(...)` calls. Returns the count of tools registered
 * so the caller can log it to stderr (stdio MCP servers must not log to
 * stdout — that channel is the protocol).
 *
 * If the templates root cannot be resolved (e.g. pulse is published as a
 * standalone npm package without the grok-agent repo alongside), this
 * function logs a single notice and returns 0 instead of throwing.
 */
export function buildGrokAgentTools(server: McpServer): number {
  const templatesRoot = resolveTemplatesRoot();
  if (!templatesRoot) {
    console.error(
      "[grok-agent-tools] templates/ directory not found — skipping dynamic tool registration. Set GROK_AGENT_TEMPLATES_DIR to enable."
    );
    return 0;
  }

  const entries = loadGrokAgentCatalog(templatesRoot);
  if (entries.length === 0) {
    console.error(
      `[grok-agent-tools] no manifests found under ${templatesRoot} — registered 0 tools.`
    );
    return 0;
  }

  for (const entry of entries) {
    const toolName = `grok-agent-${entry.slug}`;
    const description = entry.tagline ?? entry.description;

    server.registerTool(
      toolName,
      {
        title: entry.displayName,
        description,
        inputSchema: {
          action: GrokAgentActionSchema.describe(
            "Which view of the agent to return: 'describe' for full manifest summary, 'install_command' for the PowerShell install command, 'manifest_url' for canonical GitHub URLs."
          ),
        },
        annotations: {
          readOnlyHint: true,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: false,
        },
      },
      async (rawParams) => {
        try {
          const parsed = z
            .object({ action: GrokAgentActionSchema })
            .strict()
            .parse(rawParams);
          const result = handleGrokAgentTool(entry, parsed.action);
          return {
            content: [{ type: "text", text: result.text }],
            structuredContent: result.data,
          };
        } catch (err) {
          const message =
            err instanceof Error ? err.message : "unknown error";
          return {
            isError: true,
            content: [
              {
                type: "text",
                text: `[${toolName}] failed: ${message}`,
              },
            ],
          };
        }
      }
    );
  }

  console.error(
    `[grok-agent-tools] registered ${entries.length} grok-agent-* tools from ${templatesRoot}.`
  );
  return entries.length;
}
