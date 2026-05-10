#!/usr/bin/env node
/**
 * grok-pulse-mcp-server -- main entry point.
 *
 * Boots an MCP server over stdio. Tool registration is delegated to src/tools/*.
 * Each tool exports a register*(server) function -- keeps index.ts short and
 * makes it trivial to add or remove tools without merge conflicts.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { SERVER_NAME, SERVER_VERSION } from "./constants.js";
import { registerPulseToday } from "./tools/pulse-today.js";
import { buildGrokAgentTools } from "./grok-agent-tools.js";

/**
 * Validate required environment up-front. Fast-fail with clear stderr messages
 * is much friendlier than a cryptic auth error on the first tool call.
 *
 * NOTE: stdio MCP servers MUST NOT log to stdout -- that channel is the protocol.
 *       Always log to stderr.
 */
function validateEnvironment(): void {
  const missing: string[] = [];
  if (!process.env.GITHUB_TOKEN) missing.push("GITHUB_TOKEN");
  if (!process.env.XAI_API_KEY) missing.push("XAI_API_KEY");

  if (missing.length > 0) {
    console.error(
      "[" + SERVER_NAME + "] ERROR: required environment variables not set: " + missing.join(", ")
    );
    console.error("[" + SERVER_NAME + "] See .env.example for setup instructions.");
    process.exit(1);
  }
}

async function main(): Promise<void> {
  validateEnvironment();

  const server = new McpServer({
    name: SERVER_NAME,
    version: SERVER_VERSION,
  });

  // ---- Tool registration --------------------------------------------------
  registerPulseToday(server);

  // Dynamic registration: every Grok Agent OS template under `templates/`
  // becomes one MCP tool named `grok-agent-<slug>`. Failures inside
  // buildGrokAgentTools are caught and logged to stderr so the core pulse
  // tools still come up if the templates directory is missing.
  try {
    const grokAgentToolCount = buildGrokAgentTools(server);
    if (grokAgentToolCount > 0) {
      console.error(
        "[" + SERVER_NAME + "] grok-agent-tools: " + grokAgentToolCount + " agent tools registered."
      );
    }
  } catch (err) {
    console.error("[" + SERVER_NAME + "] grok-agent-tools registration failed:", err);
  }
  // (additional tools land here as they ship)
  // -------------------------------------------------------------------------

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[" + SERVER_NAME + "] v" + SERVER_VERSION + " ready on stdio.");
}

main().catch((err) => {
  console.error("[" + SERVER_NAME + "] fatal:", err);
  process.exit(1);
});
