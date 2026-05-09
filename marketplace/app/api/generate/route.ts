/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * POST /api/generate — turn a pasted README + chosen kind into a draft
 * v2.15 grok-agent.yaml manifest by calling the Anthropic Messages API.
 *
 * Built for xAI, X, Grok and the ecosystem community. ❤️
 *
 * ---------------------------------------------------------------------------
 * Production deploy story
 * ---------------------------------------------------------------------------
 * The marketplace is built with `output: 'export'` for static GitHub Pages
 * deploys, BUT this route opts into a server runtime via
 * `dynamic = 'force-dynamic'` because it must call the live Anthropic API
 * with a secret. To enable in production:
 *
 *   1. Deploy the marketplace to a Node-runtime host (Vercel, Netlify
 *      Functions, Cloudflare Pages with Functions, or AWS Amplify) — the
 *      static `output: 'export'` build skips this route entirely, so the
 *      same repo can ship to GitHub Pages without exposing the endpoint.
 *   2. Set the `ANTHROPIC_API_KEY` environment variable in the host's
 *      project settings. Without it, the route returns 503 with the
 *      remediation message below.
 *   3. (Optional) Set `GROK_AGENT_GENERATE_ALLOWED_ORIGIN` to the public
 *      origin of the marketplace so CORS tightens to one host. Default
 *      behaviour is same-origin only (no wildcard).
 *
 * Sibling deliverables:
 *   - GeneratorWizard UI: marketplace/app/generator/  (Agent 5.1)
 *   - ManifestPreview + GeneratorPRButton:            (Agent 5.3)
 *   - Offline prompt regression test:                 scripts/test-generator-prompt.py
 * ---------------------------------------------------------------------------
 */

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// ---------------------------------------------------------------------------
// Constants — keep aligned with cli/grok-agent.py KIND_VALUES + scripts/test-generator-prompt.py
// ---------------------------------------------------------------------------

const VALID_KINDS = [
  'agent',
  'finance-dashboard',
  'alpha-engine',
  'creator-payout-optimizer',
  'vision-analyzer',
  'super-agent',
  'x-native',
  'creator-template',
] as const;

type ValidKind = (typeof VALID_KINDS)[number];

const MIN_SOURCE_LENGTH = 100;
const MAX_SOURCE_LENGTH = 60_000; // guard against runaway prompt costs

const ANTHROPIC_MODEL = 'claude-sonnet-4-6';
const ANTHROPIC_ENDPOINT = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';
const ANTHROPIC_TIMEOUT_MS = 60_000;
const MAX_OUTPUT_TOKENS = 2048;

// ---------------------------------------------------------------------------
// Prompt — DO NOT DRIFT from scripts/test-generator-prompt.py.
//
// The offline test script reproduces this exact prompt so we can validate
// generator quality without spending API credits. If you change either copy,
// change the other too. The forbidden-phrase scanner (Article VIII of the
// Constitution) bans a handful of vague phrases — the system prompt below
// instructs the model to enumerate explicitly rather than abbreviate.
// ---------------------------------------------------------------------------

export const SYSTEM_PROMPT = [
  'You are a v2.15 grok-agent.yaml manifest author for the open Grok Agent OS',
  'distribution layer (AgentMindCloud/grok-agent). Given a project description',
  'and a manifest kind, produce a single valid YAML manifest.',
  '',
  'Hard rules:',
  '- Output YAML only. No markdown fences. No commentary before or after.',
  '- Never invent fields that are not in the v2.15 schema summary you are given.',
  '- Always declare every required top-level field: version, kind, name,',
  '  description, author, license. version must be the string "2.15".',
  '  license must be the string "Apache-2.0".',
  '- name must be kebab-case matching ^[a-z][a-z0-9-]*$.',
  '- Enumerate items explicitly. Do not abbreviate lists with vague',
  '  trailing phrases. If you do not know an item, omit it.',
  '- If kind is super-agent, include a constitution: block.',
  '- If kind is vision-analyzer, include a grok: block with vision: true.',
  '- Prefer omitting optional sections over guessing. The user can extend later.',
  '- All shell examples in any field must be PowerShell on Windows 11',
  '  (use $env:LOCALAPPDATA, semicolons, New-Item — never bash).',
].join('\n');

const SCHEMA_SUMMARY = [
  'v2.15 schema summary (use only these top-level keys):',
  '',
  'REQUIRED top-level keys:',
  '  version       string  must be "2.15"',
  '  kind          string  one of: agent, finance-dashboard, alpha-engine,',
  '                          creator-payout-optimizer, vision-analyzer,',
  '                          super-agent, x-native, creator-template',
  '  name          string  kebab-case slug, ^[a-z][a-z0-9-]*$',
  '  description   string  >= 10 chars, ends with a period',
  '  author        string  X handle with @ prefix (e.g. "@JanSol0s")',
  '  license       string  must be "Apache-2.0"',
  '',
  'OPTIONAL top-level sections (declare only what the agent uses):',
  '  metadata      mapping display_name, tagline, categories[], tags[],',
  '                          icon, homepage, repository, docs, language,',
  '                          created, updated',
  '  install       mapping one_click, install_command, post_url,',
  '                          prerequisites[], optional_prerequisites[],',
  '                          one_command_install',
  '  windows       mapping launcher, launch_command, app_data_path,',
  '                          requires_powershell',
  '  grok          mapping model (e.g. "grok-4.3"), api_base, vision (bool),',
  '                          tools[], system_prompt',
  '  tools         list    list of {name, type, description}; type is one of',
  '                          public_api, local_python, powershell, mcp',
  '  data          mapping storage (sqlite|memory), path, schema_version',
  '  ui            mapping framework (streamlit|cli|web), entry, port',
  '  safety        mapping disclaimers[], forbidden_actions[], consent_gates[]',
  '  constitution  mapping (REQUIRED for kind=super-agent) values[],',
  '                          consent_gates[], non_negotiables[]',
  '  evaluation    mapping promptfoo_config, deepeval_suite, langfuse_project',
  '  multi_agent   mapping coordinator, agents[], shared_memory',
  '  real_time_x   mapping listen_to[], post_to, rate_limit',
  '',
  'Disclaimers (mandatory when kind matches):',
  '  finance-dashboard, alpha-engine, creator-payout-optimizer:',
  '    safety.disclaimers must include "Not financial advice".',
  '  Any tool that touches taxes:',
  '    safety.disclaimers must also include "Not tax advice".',
  '  super-agent, x-native, real-world action agents:',
  '    safety.consent_gates must enumerate every external action explicitly.',
].join('\n');

function buildUserMessage(source: string, kind: ValidKind): string {
  return [
    `Kind: ${kind}`,
    '',
    SCHEMA_SUMMARY,
    '',
    'Project description (verbatim, may be a README or freeform notes):',
    '---',
    source.trim(),
    '---',
    '',
    'Produce the YAML manifest now. YAML only.',
  ].join('\n');
}

// ---------------------------------------------------------------------------
// Request validation
// ---------------------------------------------------------------------------

interface GenerateRequestBody {
  source?: unknown;
  kind?: unknown;
}

interface ValidatedInput {
  source: string;
  kind: ValidKind;
}

interface ValidationFailure {
  status: 400;
  body: { error: string; field?: string };
}

function validateInput(raw: unknown): ValidatedInput | ValidationFailure {
  if (!raw || typeof raw !== 'object') {
    return { status: 400, body: { error: 'Request body must be a JSON object.' } };
  }
  const body = raw as GenerateRequestBody;

  if (typeof body.source !== 'string') {
    return {
      status: 400,
      body: { error: 'Field "source" must be a string.', field: 'source' },
    };
  }
  if (body.source.length < MIN_SOURCE_LENGTH) {
    return {
      status: 400,
      body: {
        error: `Field "source" must be at least ${MIN_SOURCE_LENGTH} characters; received ${body.source.length}.`,
        field: 'source',
      },
    };
  }
  if (body.source.length > MAX_SOURCE_LENGTH) {
    return {
      status: 400,
      body: {
        error: `Field "source" must be at most ${MAX_SOURCE_LENGTH} characters; received ${body.source.length}.`,
        field: 'source',
      },
    };
  }
  if (typeof body.kind !== 'string') {
    return {
      status: 400,
      body: { error: 'Field "kind" must be a string.', field: 'kind' },
    };
  }
  if (!(VALID_KINDS as readonly string[]).includes(body.kind)) {
    return {
      status: 400,
      body: {
        error: `Field "kind" must be one of: ${VALID_KINDS.join(', ')}.`,
        field: 'kind',
      },
    };
  }

  return { source: body.source, kind: body.kind as ValidKind };
}

// ---------------------------------------------------------------------------
// Anthropic API call
// ---------------------------------------------------------------------------

interface AnthropicSuccess {
  ok: true;
  yaml: string;
  inputTokens: number;
  outputTokens: number;
}

interface AnthropicFailure {
  ok: false;
  status: number;
  error: string;
  detail?: string;
}

interface AnthropicContentBlock {
  type: string;
  text?: string;
}

interface AnthropicMessageResponse {
  content?: AnthropicContentBlock[];
  usage?: { input_tokens?: number; output_tokens?: number };
  type?: string;
  error?: { type?: string; message?: string };
}

async function callAnthropic(
  apiKey: string,
  source: string,
  kind: ValidKind,
): Promise<AnthropicSuccess | AnthropicFailure> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ANTHROPIC_TIMEOUT_MS);

  try {
    const upstream = await fetch(ANTHROPIC_ENDPOINT, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': ANTHROPIC_VERSION,
      },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL,
        max_tokens: MAX_OUTPUT_TOKENS,
        system: SYSTEM_PROMPT,
        messages: [{ role: 'user', content: buildUserMessage(source, kind) }],
      }),
    });

    if (!upstream.ok) {
      let detail = '';
      try {
        const errBody = (await upstream.json()) as AnthropicMessageResponse;
        detail = errBody.error?.message ?? '';
      } catch {
        try {
          detail = await upstream.text();
        } catch {
          detail = '';
        }
      }
      // Map upstream status to a sensible client-facing status.
      let mapped = 502;
      if (upstream.status === 429) mapped = 429;
      else if (upstream.status === 401 || upstream.status === 403) mapped = 502;
      else if (upstream.status >= 500) mapped = 502;

      return {
        ok: false,
        status: mapped,
        error:
          upstream.status === 429
            ? 'Anthropic API rate limit exceeded. Retry shortly.'
            : `Anthropic API returned ${upstream.status}.`,
        detail,
      };
    }

    const data = (await upstream.json()) as AnthropicMessageResponse;
    const blocks = data.content ?? [];
    const text = blocks
      .filter((b) => b.type === 'text' && typeof b.text === 'string')
      .map((b) => b.text as string)
      .join('');

    if (!text.trim()) {
      return {
        ok: false,
        status: 502,
        error: 'Anthropic API returned an empty response.',
      };
    }

    return {
      ok: true,
      yaml: stripCodeFence(text),
      inputTokens: data.usage?.input_tokens ?? 0,
      outputTokens: data.usage?.output_tokens ?? 0,
    };
  } catch (err) {
    const isAbort = err instanceof Error && err.name === 'AbortError';
    if (isAbort) {
      return {
        ok: false,
        status: 504,
        error: `Anthropic API call timed out after ${ANTHROPIC_TIMEOUT_MS}ms.`,
      };
    }
    return {
      ok: false,
      status: 502,
      error: 'Failed to reach Anthropic API.',
      detail: err instanceof Error ? err.message : String(err),
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * The system prompt forbids markdown fences, but defensively strip a leading
 * ```yaml ... ``` wrapper if the model produces one anyway.
 */
function stripCodeFence(text: string): string {
  const trimmed = text.trim();
  const fenceOpen = /^```(?:ya?ml)?\s*\n/i;
  const fenceClose = /\n```\s*$/;
  if (fenceOpen.test(trimmed) && fenceClose.test(trimmed)) {
    return trimmed.replace(fenceOpen, '').replace(fenceClose, '').trim();
  }
  return trimmed;
}

// ---------------------------------------------------------------------------
// CORS — same-origin only (no wildcard).
// ---------------------------------------------------------------------------

function corsHeaders(req: NextRequest): Record<string, string> {
  const allowed = process.env.GROK_AGENT_GENERATE_ALLOWED_ORIGIN;
  const origin = req.headers.get('origin') ?? '';
  const headers: Record<string, string> = {
    Vary: 'Origin',
  };
  if (allowed && origin === allowed) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS';
    headers['Access-Control-Allow-Headers'] = 'content-type';
  }
  // Same-origin requests carry no Origin header (or echo our own host); the
  // browser allows them without explicit CORS headers, so no extra config.
  return headers;
}

export function OPTIONS(req: NextRequest): Response {
  return new Response(null, { status: 204, headers: corsHeaders(req) });
}

// ---------------------------------------------------------------------------
// Route handler
// ---------------------------------------------------------------------------

export async function POST(req: NextRequest): Promise<Response> {
  const headers = corsHeaders(req);

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      {
        error:
          'ANTHROPIC_API_KEY not configured. Production needs a Vercel/Netlify/Node runtime with this env var set.',
      },
      { status: 503, headers },
    );
  }

  let parsed: unknown;
  try {
    parsed = await req.json();
  } catch {
    return NextResponse.json(
      { error: 'Request body must be valid JSON.' },
      { status: 400, headers },
    );
  }

  const validated = validateInput(parsed);
  if ('status' in validated) {
    return NextResponse.json(validated.body, { status: validated.status, headers });
  }

  const result = await callAnthropic(apiKey, validated.source, validated.kind);

  if (!result.ok) {
    return NextResponse.json(
      { error: result.error, detail: result.detail ?? '' },
      { status: result.status, headers },
    );
  }

  return NextResponse.json(
    {
      yaml: result.yaml,
      model: ANTHROPIC_MODEL,
      tokens_used: {
        input: result.inputTokens,
        output: result.outputTokens,
      },
    },
    { status: 200, headers },
  );
}
