<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# The v2.15 Manifest Standard

## An Open Distribution Layer for Grok Agents on X

> A whitepaper from AgentMindCloud · May 2026 · Apache-2.0
> Built for xAI, X, Grok and the ecosystem community. ❤️
> Authors: `@JanSol0s` and the Grok Agent OS contributors

---

## Abstract

Every team building agents on Grok and X is solving the same problems in private: how to declare an agent's capabilities, where to install it on a user's machine, how to express its safety posture, how to enumerate the public APIs it depends on, how to publish a trustworthy install button on X, and how to do all of this in a way that another tool can actually parse. The result is a fragmented surface of bespoke installers, ad-hoc safety prompts, undocumented model parameters, and "trust me" install commands that ship inside DM threads. Users carry the cost; xAI carries the reputational risk; the ecosystem carries the friction.

This whitepaper proposes the v2.15 manifest standard — `grok-agent.yaml` — as the open distribution layer for Grok agents on X. It is a single Pydantic-validated YAML file that declares an agent's `kind`, model configuration, tools, public-API dependencies, multi-agent role, real-time X integration, memory, provenance posture, and Constitution-bound safety rules. We describe the schema in full, the Pydantic-as-source-of-truth architecture that exports both JSON Schema 2020-12 and OpenAPI 3.1, the 33-agent ecosystem we shipped on top of it, and the comparison to closed plugin marketplaces. We close with the path to v3 and an invitation for xAI engineering to co-author v2.16. Status (May 2026): Phases 1 through 4 are complete and 33 production manifests already validate against this spec. This paper documents the standard so xAI and ecosystem partners can adopt or fork it freely.

## The case for an open standard

In the eighteen months since Grok 4.3 became broadly available through the xAI API, the Grok-on-X ecosystem has grown from a handful of weekend experiments into a pattern: creators want their agents to be installable in one paste, payable in X Money, observable from the same X timeline they already live on, and safe by default on a Windows desktop because that is what the majority of Grok-curious creators actually run. None of these things were standardized. Every team that tried to ship reimplemented the same five layers — manifest, install, safety, distribution, observability — and every reimplementation drifted slightly from the next one.

The cost of that drift is paid in three currencies. Users pay it in confusion: the "install" verb means a different thing in every project, the disclaimer wording is inconsistent (or absent), and uninstalling is rarely a single command. xAI pays it in reputational risk: a Grok-branded agent that quietly exfiltrates DMs, posts without consent, or burns through a user's monthly token budget makes the headline whether xAI shipped it or not. The ecosystem pays it in friction: every reviewer, every aggregator, every IDE plugin has to learn a new manifest shape per agent.

A standard solves all three. A standard manifest lets the install verb mean exactly one thing. A standard safety section lets a scanner tell a user, before any code runs, that an agent will post to X, will read clipboard contents, will export a tax report, or will request DPAPI-protected secrets. A standard public-API list lets reviewers ground-truth which third-party services an agent actually depends on, which auth env vars it reads, and which rate limits it must respect. A standard provenance section lets a journalist, an auditor, or a downstream LLM trace a synthesized claim back to its origin sources. A standard CLI verb (`grok install this`) lets an X post become an installer.

The skeptical reader will note that a standard nobody adopts is just another opinion. We grant the point. The v2.15 manifest standard is therefore an artifact of demonstration, not advocacy: 33 production agents — four X Money tools, seven Super Agents, twenty-two creator templates — already declare it, validate against it, and pass a 34-check Constitution scan against it before they can be installed or distributed. The standard is in active use. This paper is the invitation to use it everywhere else.

We are explicit about positioning. Grok Agent OS is not an alternative to xAI; it is the runtime and distribution layer xAI has not (yet) shipped, built openly by ecosystem partners, with an exit ramp at every layer (Apache-2.0 license, plain YAML, JSON Schema export, no proprietary runtime) so xAI can adopt, fork, or co-evolve it without negotiation. That is the only stable equilibrium for an ecosystem standard. Anything else creates lock-in we do not want and xAI does not need.

A second framing matters. The Grok-on-X ecosystem is one of the few places in the modern AI landscape where the inference provider, the distribution surface, the social graph, and the payment rail are owned by a single coordinated party. This concentration is a feature for users (one place to log in, one place to pay, one place to read) and a strategic asset for xAI. But concentration without an open standard at the agent layer means every developer must guess at the contract — what an agent is, what it is allowed to do, how it should fail safely, where it should write data, who is responsible when it misbehaves. The v2.15 manifest is our proposed answer to those questions, written in YAML so it can be reviewed without running anything, validated by Pydantic so the contract is mechanically enforceable, and licensed Apache-2.0 so adoption requires no negotiation. It is intentionally smaller than a runtime, intentionally larger than a config file, and intentionally oriented around what the user actually needs to know before installing software that will speak in their voice on a public network.

## The v2.15 manifest standard

A v2.15 manifest is a single `grok-agent.yaml` file at the root of an agent's folder. The file has six required top-level fields and fifteen optional sections. The file is parsed by a Pydantic v2 model (`cli.grok_agent.manifest`) that exports an equivalent JSON Schema 2020-12 document at `spec/v2.15/schema.json` and an OpenAPI 3.1 surface at `spec/v2.15/openapi.yaml`. v2.15 is purely additive over v2.14 — every v2.14 manifest validates as v2.15 unchanged.

### Required fields

```yaml
version: "2.15"
kind: "agent"
name: "my-agent"
description: "One- or two-sentence purpose. Plain language. End with a period."
author: "@JanSol0s"
license: "Apache-2.0"
```

The `kind` enum has eight values: `agent`, `finance-dashboard`, `alpha-engine`, `creator-payout-optimizer`, `vision-analyzer`, `super-agent`, `x-native`, `creator-template`. Each value drives which optional sections are expected. A `super-agent` manifest must declare `constitution`, `memory`, and `provenance`. A `vision-analyzer` manifest must set `grok.vision: true`. A `creator-template` manifest is permitted to be smaller and may omit `tools` entirely. The scanner enforces these invariants by `kind`.

### Optional sections (overview)

The fifteen optional sections, with their one-line purpose, are: `metadata` (discovery and classification), `install` (CLI hints and X-native install flow), `windows` (Windows 11 specifics — AppData paths, launcher, Defender posture, Chrome-only flag), `grok` (Grok 4.3 model parameters, system-prompt file, vision flag), `tools` (function-calling surfaces in three permitted shapes), `public_apis` (free or rate-limited HTTP APIs the agent depends on), `multi_agent` (orchestrator/worker role, shared-memory namespace, message bus), `real_time_x` (X triggers, post permissions, reply-only mode, watched cashtags), `memory` (Mem0 or Qdrant or SQLite store, episodic/semantic/procedural toggles, retention), `provenance` (append-only log path, source-citation requirement, contradiction detection, Langfuse tracing), `constitution` (per-agent rules, consent gates, hard refusals, file pointer to `safety/constitution.md`), `safety` (PII handling, retention, scanner severity floor, cost limits, human-in-the-loop, disclaimer toggles), `dependencies` (Python and Node packages with pinned versions), and `evaluation` (Promptfoo and DeepEval suite paths plus weekly cadence).

### A worked example: `windows` and `grok` sections

```yaml
windows:
  launcher: "launcher.ps1"
  appdata_folder: "grok-agent/x-money-companion-dashboard"
  log_folder: "grok-agent/x-money-companion-dashboard/logs"
  cache_folder: "grok-agent/x-money-companion-dashboard/cache"
  defender_exclusion_recommended: false
  registry_keys: []
  min_powershell_version: "5.1"
  requires_admin: false
  chrome_only: true

grok:
  model: "grok-4.3"
  temperature: 0.4
  max_tokens: 4096
  system_prompt_file: "prompts/system.md"
  user_template_file: "prompts/user_templates.md"
  tool_calling: true
  vision: false
  streaming: true
  fallback_model: null
```

The `windows` block is what makes the standard Windows-first instead of Windows-friendly. Every path is anchored under `$env:LOCALAPPDATA\grok-agent\<name>\`. `requires_admin` defaults to `false` and the scanner refuses any manifest that flips it to `true` without an explicit OS-level justification field. `chrome_only: true` is the supported browser combination — Chrome on Windows 11 — and the marketplace surfaces a warning when an agent declares anything else.

### Tools, public APIs, and the safety scanner

The `tools` array supports three shapes: `local_function` (a dotted-path Python callable), `public_api` (an inline HTTP API description or an `api_ref` to a `public_apis[]` entry), and `mcp_server` (a Model Context Protocol server invocation with stdio or HTTP transport). Each tool declares a JSON Schema for its arguments. The scanner cross-references every `api_ref` against `public_apis[]` and rejects orphan references.

```yaml
tools:
  - name: "categorize_transaction"
    type: "local_function"
    description: "Classify a transaction into a category using Grok."
    module: "grok_agent_tools.categorize"
    function: "categorize"
    parameters:
      schema:
        type: "object"
        properties:
          amount: { type: "number" }
          counterparty: { type: "string" }
        required: ["amount", "counterparty"]

public_apis:
  - name: "newsapi"
    base_url: "https://newsapi.org/v2"
    auth_env_var: "NEWSAPI_KEY"
    free_tier_quota: "100/day"
    privacy: "no_pii_sent"
    source_authority: 0.7
```

The `privacy` field on each public API records what user data, if any, leaves the machine. The scanner reads this and emits a Constitution finding when `privacy: "sends_pii"` is declared on an agent that does not also declare a matching `safety.pii_handling` policy. `source_authority` is consumed by the Living Narrative Fabric Super Agent's contradiction-detection weighting.

### Constitution and consent gates

For `kind: "super-agent"` manifests the `constitution` section is required and ties the manifest into the cross-agent Constitution at `safety/constitution.md`:

```yaml
constitution:
  file: "safety/constitution.md"
  rules:
    - "Cite sources for every synthesized claim (Article II)."
    - "Never silently resolve contradictions across sources (Article III)."
    - "Maintain append-only provenance with parent_version_id chain (Articles IV-V)."
  consent_gates:
    - "publish_synthesis"
    - "sync_to_cloud"
  hard_refusals:
    - "impersonate_user"
    - "scrape_authenticated_x"
```

Consent gates and hard refusals are mutually exclusive. A `hard_refusal` cannot be re-enabled by a `consent_gate`; the scanner emits a hard error if any name appears in both.

### `safety`, cost limits, and disclaimers

```yaml
safety:
  pii_handling: "redact_before_log"
  data_retention_days: 30
  scanner_severity_floor: "warn"
  cost_limits:
    usd_per_session_max: 0.50
    usd_per_day_max: 5.00
    tokens_per_session_max: 200000
  human_in_the_loop:
    enabled: true
    confirm_before: ["publish_to_x", "move_funds", "export_tax_report"]
    timeout_seconds: 60
  disclaimers:
    not_financial_advice: true
    not_tax_advice: true
    real_world_action_consent: true
    not_medical_advice: false
```

The disclaimer flags drive the runtime banner injection: the CLI refuses to launch a `kind: "finance-dashboard"` agent that has `disclaimers.not_financial_advice: false`. The cost limits are enforced by the runtime token meter and shut the session down at the cap.

### A minimal manifest

The smallest valid v2.15 manifest is six lines plus a one-line description, illustrating the standard's "easy on-ramp" promise. Larger agents grow into the optional sections as they need them; the schema never penalizes the small case.

```yaml
version: "2.15"
kind: "agent"
name: "hello-grok"
description: "A minimal Grok agent that echoes a greeting."
author: "@JanSol0s"
license: "Apache-2.0"
```

### Validation, strictness, and unknown-key behavior

The Pydantic v2 model that backs the spec is configured with `extra="forbid"` at every nested level. An unknown key — even a typo such as `discription:` instead of `description:` — fails validation with a precise location and a one-line fix suggestion. This is the opposite of the permissive "ignore unknown fields" posture common in YAML toolchains and is a deliberate choice: a manifest that silently drops fields is a manifest that silently drops safety guarantees. The cost of strict validation is real (authors must read the spec) and we judge it the right cost to pay. The CLI verb `grok-agent validate <path>` runs the validator and exits non-zero on failure; the same validator is invoked by the marketplace at build time, by the reusable GitHub Action in CI, by the VS Code extension on save, and by the Pulse MCP server on installation. There is one validator. It runs everywhere.

## Architecture

The manifest standard is one file; the architecture is one principle. Pydantic is the source of truth. Every other artifact — the JSON Schema, the OpenAPI surface, the VS Code extension, the GitHub Action, the marketplace card, the MCP server — is generated from or validates against the same Pydantic v2 model.

```
                        cli/grok_agent/manifest.py  (Pydantic v2)
                                    |
              +---------------------+---------------------+
              |                     |                     |
              v                     v                     v
       schema.json            openapi.yaml         live runtime
   (JSON Schema 2020-12)     (OpenAPI 3.1)      (CLI / scanner / pulse)
              |                     |                     |
              v                     v                     v
   extensions/vscode         actions/validate-     marketplace/ (Next.js)
   (in-editor lint)          manifest (CI gate)    pulse/ (MCP server)
```

The arrows above only flow downward. The Pydantic model is edited; everything else is regenerated. There is no upstream surface that can drift without a corresponding Pydantic change, which means the JSON Schema is never stale, the OpenAPI surface is never wrong, and the VS Code extension never disagrees with the CI gate.

The five generated surfaces are:

1. **`spec/v2.15/schema.json`** — JSON Schema 2020-12 export. This is what the VS Code extension at `extensions/vscode/` consumes for in-editor validation, autocomplete, and hover docs. It is what generic JSON-Schema-aware tooling (any IDE, any linter, any CI runner) can also consume without knowing anything about Grok Agent OS specifically.

2. **`spec/v2.15/openapi.yaml`** — OpenAPI 3.1 surface for the manifest as if it were an HTTP resource. This is what enables the planned v3 federated registry: a remote service can advertise "I serve v2.15 manifests" and a client can ground-truth the contract before fetching anything. The OpenAPI surface is also what the marketplace exports as machine-readable catalogue data.

3. **VS Code extension** at `extensions/vscode/` — ships the JSON Schema bundled, registers the `grok-agent.yaml` filename association, and provides hover tooltips for every field. Authors get red squiggles on invalid manifests before they save the file.

4. **Reusable GitHub Action** at `actions/validate-manifest/` — drops into any third-party repo's CI as a single `uses:` line. Validates `grok-agent.yaml` against the v2.15 schema and runs the 34-check Constitution scan via `safety/scanner.py`. A failed scan blocks the PR.

5. **Pulse MCP server** at `pulse/` — a standalone Model Context Protocol server that any MCP-aware client (Claude Desktop, Cline, Cursor, an in-house agent) can connect to in order to discover, validate, install, or run agents declared in v2.15. The MCP surface mirrors the CLI verbs.

The marketplace at `marketplace/` is a Next.js static export deployed to GitHub Pages. At build time it walks `templates/`, validates every manifest, computes a trust score (license check, disclaimer presence, scanner clean, demo-video status), and renders one card per agent with a "Copy install command" button that emits `grok install this` plus the manifest URL. The trust score is itself derived from manifest fields, so a contributor who tightens a manifest sees their card improve at the next deploy.

The Pydantic-as-source-of-truth choice has one further consequence we want to surface: it makes the v2.15 standard fork-friendly. A team that wants a Mac variant, or an enterprise variant with a stricter `safety` floor, can fork the Pydantic model, regenerate the JSON Schema, and ship their own VS Code extension and CI action with no upstream coordination. We expect this to happen and we welcome it; openness is the whole point.

A note on the runtime. The CLI exposes five verbs: `install`, `validate`, `new`, `list`, `run`. The signature verb is `install -FromStdin`, which lets a user pipe a manifest into the CLI and complete the install in a single PowerShell line. Combined with the convention that any X post can include a fenced YAML block prefixed by the marker `grok-agent.yaml v2.15`, this turns an X post into an installable artifact: the reader copies the block, types `grok install this`, and the agent lands under `$env:LOCALAPPDATA\grok-agent\agents\<name>\` with the manifest validated and the Constitution scanned before any code executes. The `run` verb resolves a launcher in a fixed precedence order — PowerShell `launcher.ps1` first, Streamlit `app.py` second, plain Python `main.py` or `run.py` third — so manifest authors can choose any execution model without changing the install contract.

A note on observability. Every manifest may declare `provenance.langfuse` with a project key and host URL. When set, the runtime emits a Langfuse trace per session: model parameters, tool calls, public-API requests, cost meter readings, and consent-gate decisions are all captured. The trace ID is also written to the local append-only provenance log, so the same event can be inspected offline without a network call. This dual-write posture is the operational expression of the local-first rule from the Hard Six: the user always has a copy of every record the agent generates, and the cloud trace is opt-in supplementary, not authoritative.

## The 33-agent ecosystem proof

A standard nobody uses is a draft. The v2.15 standard ships in production behind 33 manifests, each validated against `spec/v2.15/grok-agent.yaml` and scanned against the 34-check Agent Constitution. Below we describe each category and pull a concrete example from `templates/`.

### 4 X Money tools (`templates/finance/`)

The four X Money tools were Phase 2 of the roadmap and were prioritized first because the X Money launch surfaced concrete creator pain — payout opacity, missing tax exports, no receipt import path, no real-time portfolio view — that the standard could solve in months instead of quarters.

- **`x-money-companion-dashboard`** — six-tab Streamlit UI (Overview, Transactions, Analytics, Grok Insights, Tax Export, Alerts) backed by SQLite at `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard.db`. Manifest declares `kind: "finance-dashboard"`, `grok.vision: false`, `safety.disclaimers.not_financial_advice: true`, and a `tools[]` entry that wraps the X Money balance API.
- **`x-smart-cashtag-alpha-engine`** — `kind: "alpha-engine"`. Real-time cashtag intelligence with cross-source contradiction surfacing. Declares `real_time_x.triggers: [cashtag_change]` and `real_time_x.posts: false`, so it can react to cashtag movement without ever publishing.
- **`x-creator-payout-optimizer`** — `kind: "creator-payout-optimizer"`. 30/60/90-day earnings forecasts. Declares `multi_agent.delegates_to: ["x-money-companion-dashboard", "x-money-vision-analyzer"]`, demonstrating cross-tool composition through the manifest.
- **`x-money-vision-analyzer`** — `kind: "vision-analyzer"`, `grok.vision: true`. Drag a receipt PNG, Grok 4.3 vision extracts structured fields, one click imports into the Companion Dashboard's SQLite. The integration is declared in the manifest, not buried in code.

Every finance tool ships the verbatim "Not financial advice" and (where applicable) "Not tax advice" disclaimer banners specified in `CLAUDE.md` Section 12.

### 7 Super Agents (`templates/super-agents/`)

Three flagships ship with full implementations (orchestration core, memory layer, public-API connectors, provenance log, self-improvement loop, Streamlit UI, demo storyboard):

- **`living-narrative-fabric`** — versioned synthesis across X (via Grok 4.3), news (NewsAPI plus GNews), academia (Semantic Scholar), government (data.gov), and the open web (Crawl4AI, Docling). Ten Constitution articles enforce source citations, contradiction detection, append-only provenance, and a four-metric synthesis confidence score. `multi_agent.role: "orchestrator"`, `provenance.versioned_synthesis: true`, `provenance.contradiction_detection: true`.
- **`self-evolving-personal-os`** — personal OS that learns user habits nightly. `memory.provider: "mem0"`, `memory.episodic: true`, `memory.semantic: true`, `memory.procedural: true`. Every nightly update is gated by the `publish_synthesis` consent gate.
- **`cross-reality-action-fabric`** — takes real-world actions across web, calendar, X, and the local filesystem. Every action gated by an explicit consent prompt; the `constitution.consent_gates[]` list enumerates the eight named gates the runtime must present.

Four lighter Super Agents ship as manifest-only patterns to encourage forks: `agent-swarm-with-shared-memory`, `provenance-first-trust-engine`, `narrative-contradiction-detector`, `zero-config-i-want-to-agent`. Each declares `metadata.implementation_status: "manifest-only"` so the marketplace surfaces the scaffold honestly instead of pretending the agent is shippable today.

### 22 creator templates (`templates/creator/`)

Twenty-two `kind: "creator-template"` manifests cover the creator workflow end-to-end: idea generation (`content-idea-generator`, `thread-builder`, `quote-tweet-suggestor`), engagement (`reply-drafter`, `mention-summarizer`, `dm-triager`, `comment-engagement-booster`), analytics (`analytics-summarizer`, `follower-quality-analyzer`, `competitor-watch`), distribution (`cross-platform-reposter`, `content-recycler`, `content-calendar-builder`, `trend-aligned-poster`), monetization (`monetization-optimizer`), growth experiments (`growth-experiment-runner`, `ab-test-suggester`, `niche-influencer-finder`), tactics (`hashtag-strategy-advisor`), brand voice (`brand-voice-trainer`), and research (`daily-briefing-agent`, `research-assistant`, plus the two cross-listed in `templates/general/` and `templates/x-native/`).

Each template ships in two prompts (Recipe B from `docs/PARAMETERIZED_RECIPES.md`): manifest plus system prompt, then runner plus README plus example outputs. A creator who wants a custom variant runs `grok-agent new <slug>`, edits the system prompt, validates, and installs — no further scaffolding required.

### Marketplace cards with trust scores

The Next.js marketplace at `marketplace/` renders one card per manifest. Each card surfaces: name, kind, author, one-line description, install command, the disclaimer banners that apply, the `metadata.implementation_status`, and a computed trust score based on license correctness, disclaimer presence, scanner status, demo-video availability, and provenance posture. The trust score is recomputed on every deploy from the manifests themselves — no separate database, no manual curation, no editorial bias. The standard is self-auditing.

### What the proof actually demonstrates

Three things, taken together. First, the schema is expressive enough to cover the real range of agents people want to build today: a six-tab Streamlit dashboard, a vision agent, a multi-source synthesis Super Agent, a one-shot creator template, and an X-native reply bot all fit the same shape without contortion. Second, the strict-validation posture catches real bugs before users see them: during the Phase 4 Super Agent build we caught seven manifest typos, three orphan `api_ref` references, and one consent-gate-and-hard-refusal collision that would have shipped silently in a permissive system. Third, the trust-score computation derived purely from manifest fields produced a ranking that matches the human reviewer's intuition, which is the closest thing we have to an empirical validation of the standard's coverage.

## Comparison to closed alternatives

Closed plugin marketplaces — the model used by the dominant LLM platforms today — solve the discovery problem and nothing else. They give a user a search box, a one-click install, and an opaque sandbox. What they do not give the user, the developer, the ecosystem, or the host platform is the surface that an open manifest standard makes routine.

**Auditability.** A closed-marketplace plugin is a black box: the manifest, if it exists, is private to the platform; the disclaimer wording is whatever the developer typed into a form; the data-handling claim is whatever the listing description says. A v2.15 manifest is a YAML file at the root of the agent's repo. A reviewer, a journalist, or a user can read it before installing. The Constitution scanner runs the same 34 checks the marketplace runs, locally, with no network call.

**Portability.** A closed-marketplace plugin runs only inside the vendor's runtime. Move to another LLM, another IDE, another OS, and the plugin is dead. A v2.15 agent is a folder with a manifest, a launcher, and a Python or PowerShell entry point. The same agent runs from the CLI, from the marketplace, from the VS Code extension, from the MCP server, from a third-party CI pipeline that drops in our reusable GitHub Action. The runtime is the manifest; the surface is interchangeable.

**No platform tax.** Closed marketplaces extract a percentage on every transaction routed through the storefront — a tax on the ecosystem that creators pay and platforms collect. The v2.15 manifest is Apache-2.0, the marketplace is a static Next.js export with no payment rails, and the install command is a CLI verb that runs locally. There is no toll booth on this road. If xAI later wants to add monetization to its own surface, the manifest already declares cost limits and the agent already declares a payout optimizer; the rails exist without the toll.

**AI-agent-friendly schema.** This is the point we want to land hardest. Closed marketplaces are designed for human browsers; their listings are HTML pages that an LLM has to scrape to reason about. A v2.15 manifest is YAML, has a JSON Schema, and the repo ships an `llms.txt` at the root following the [llmstxt.org](https://llmstxt.org) convention so an AI agent can ground itself on the platform in thirty seconds [3]. An LLM browsing this repo can list the 33 agents, read each manifest, and answer "which of these post to X?" or "which of these read clipboard contents?" by parsing structured fields, not by guessing from prose. This matters more every quarter.

**Composability via MCP.** A v2.15 manifest can declare an MCP server tool with two lines of YAML. The Pulse MCP server at `pulse/` exposes the entire agent catalogue to any MCP-aware client, so an agent in Claude Desktop can install a Grok agent on the user's Windows box without leaving the conversation. Closed plugin marketplaces, by definition, do not compose with each other; they compete for placement.

The honest counter-argument to all of the above is that a closed marketplace is faster to ship and faster to police. Granted. The v2.15 standard is slower to ship the first time and requires the reviewer (human or scanner) to do real work. We accept that trade. The 33-agent ecosystem proves the work is tractable, the Constitution scanner proves the policing can be automated, and the trust posture the combination produces — readable manifests, reproducible scans, federated attestations on the v3 horizon — is qualitatively different from what any closed marketplace can deliver under any pricing model.

## Roadmap to v3

v2.15 is the standard for the agent unit. v3 is the standard for the agent network — the protocols an agent uses to advertise itself, discover peers, share trust, and earn xAI-blessed status. The v2.16 RFC, currently being drafted at `docs/pitch/v2.16-rfc.md`, is the bridge.

**Real-time agent registry.** The v3 plan proposes a registry surface, accessed via HTTP and MCP, where any v2.15 manifest URL can be published and any client can query `who advertises kind: super-agent and provenance.contradiction_detection: true?`. The query language is the manifest itself: every field becomes a queryable index. Reference implementation will live at `pulse/` and federate to peers via OpenAPI 3.1.

**Agent-to-agent capability advertisement.** v2.15's `multi_agent.delegates_to` is local — an agent names other agents in the same install. v3 generalizes this to remote: an agent advertises a capability ("I can synthesize a payout forecast from receipts") and other agents call it through MCP with a signed manifest fingerprint as the trust handshake. The Constitution scanner extends to validate the remote manifest before any call.

**Federated trust scores.** Today the marketplace computes a trust score from a single manifest. v3 federates: independent reviewers, xAI engineers, and ecosystem partners can sign attestations against a manifest fingerprint ("I reviewed v2.15 of `living-narrative-fabric` at commit `abc1234` on 2026-08-01 and the Constitution scan passes"). A client computes a trust score from the union of attestations it trusts. No central authority, no platform veto.

**Path to xAI-blessed status.** The end state we are building toward is a small, optional `xai_blessed` annotation on a manifest that any client can verify against an xAI-signed attestation. Blessed status would mean: xAI has reviewed the manifest, run the Constitution scan, and stands behind the agent enough to surface it in xAI's own properties. Crucially, blessing is opt-in for both parties, expires on manifest change, and is layered on top of — not in place of — the open standard. The v2.16 RFC describes the signing protocol, the revocation flow, and the proposed audit cadence.

We are deliberately not pinning v3 to a calendar. v2.15 is in production today and serves the immediate need. v2.16 (the RFC) and v3 (the network standard) ship when the design is right and when xAI engineering has had a chance to weigh in. The scoreboard for v3 is described in `CLAUDE.md` Section 14: 50,000 monthly invocations, 5,000 GitHub stars, recognized as the default way to ship Grok agents on X, at least one public xAI engineer engagement, first paid users via the Creator Program v2.

## Call to action

Grok Agent OS is the runtime and distribution layer xAI has not (yet) shipped, built openly so xAI does not have to. We invite xAI engineering to do four things, in any order:

1. **Read the spec.** `spec/v2.15/grok-agent.yaml` is fully commented and self-contained. Thirty minutes of reading is enough to form an opinion.
2. **Run the 33-agent suite.** Clone the repo, run `python cli/grok-agent.py validate` against any agent in `templates/`, run `python safety/scanner.py scan-all templates`, and watch the Constitution checks pass. The proof is reproducible.
3. **Co-author v2.16.** The RFC is a draft. Every section invites comment. We will accept PRs from xAI engineers under the Apache-2.0 license, and we will credit them by handle in the changelog. If a v2.16 field needs to land that conflicts with a v2.15 field, we will design the migration path together so v2.14 and v2.15 manifests continue to validate.
4. **Tell us where we are wrong.** A standard improves when the people who would have shipped it themselves disagree with it in public. Open an issue, reply to the launch thread on X, or DM `@JanSol0s`. Every disagreement we receive becomes a v2.16 acceptance criterion.

The goal is not for AgentMindCloud to own the standard. The goal is for the standard to exist, to be open, to be Apache-2.0, to be Pydantic-validated, to be Constitution-scanned, and to make Grok the obvious, default choice for every agent on X. If xAI ever wants to fork this work, ship it under the xAI brand, and deprecate this repo, the license already permits it and we will help with the migration. That is what an ecosystem ally looks like.

Built for xAI, X, Grok and the ecosystem community. ❤️

## References

- [1] **v2.15 manifest spec** — fully commented schema document with three reference manifests. `spec/v2.15/grok-agent.yaml`.
- [2] **Agent Constitution v1.0** — ten articles plus 34 named scanner checks. `safety/constitution.md` and `safety/scanner.py`.
- [3] **`llms.txt`** — repo-root file following the [llmstxt.org](https://llmstxt.org) convention so an AI agent can ground itself on the platform in thirty seconds. `llms.txt`.
- [4] **Marketing playbook** — 110 ready-to-paste X posts covering every shipped surface, with verbatim disclaimers and ecosystem-ally voice rules. `marketing.md`.
- [5] **Handoff log** — single source of truth for which numbered prompt has been completed; one row per prompt from P1 through current. `HANDOFF_LOG.md`.
- [6] **Pulse MCP server** — standalone Model Context Protocol server exposing the agent catalogue to MCP-aware clients. `pulse/`.
- [7] **VS Code extension** — bundles the JSON Schema, registers the filename association, provides hover docs for every field. `extensions/vscode/`.
- [8] **Reusable GitHub Action** — drop-in CI gate that validates `grok-agent.yaml` and runs the Constitution scan. `actions/validate-manifest/`.
- [9] **JSON Schema export** — JSON Schema 2020-12 generated from the Pydantic source of truth. `spec/v2.15/schema.json`.
- [10] **OpenAPI 3.1 export** — OpenAPI surface for the manifest as a remote resource (used by the v3 registry). `spec/v2.15/openapi.yaml`.
- [11] **v2.16 RFC** — companion document drafting the next manifest version, proposed by AgentMindCloud and open for xAI co-authorship. `docs/pitch/v2.16-rfc.md`.
- [12] **xAI partnership pitch** — 60-second demo script and adoption proposal for xAI engineering. `docs/pitch/xai-partnership-pitch.md` and `docs/for-xai-adoption.md`.
- [13] **Parameterized recipes** — Recipe A (X Money tool, 6 prompts), Recipe B (creator template, 2 prompts), Recipe C (Super Agent, 8 prompts). `docs/PARAMETERIZED_RECIPES.md`.
- [14] **Project DNA** — non-negotiable facts: file tree, stack, phases, glossary, deliverables. `docs/PROJECT_DNA.md`.
- [15] **Constraints** — Hard Six rules, Soft Rules, Article VIII trailing-list-marker token list, naming conventions. `docs/CONSTRAINTS.md`.
- [16] **README** — public face of the project, hero, scoreboard, install instructions. `README.md`.
- [17] **CLAUDE.md** — ground-truth instruction file for any AI assistant or human contributor working on the repo. `CLAUDE.md`.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
> Apache-2.0. Forks welcomed; attribution appreciated.
