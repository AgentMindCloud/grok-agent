<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# v2.15 Manifest Schema — Changelog

> **Backwards compatibility:** every v2.14 manifest validates as v2.15
> unchanged. v2.15 is purely additive — no fields were removed, renamed,
> or had their semantics altered. To adopt v2.15 features, edit your
> manifest directly; no migration tool is required.

---

## v2.15 — 2026-05-04

### Added

- **`metadata` section**
  - `metadata.display_name` — pretty title used by the marketplace card.
  - `metadata.tagline` — short marketplace one-liner.
  - `metadata.categories[]` — array of free-form classification tags
    (e.g. `["finance", "x-money"]`).
  - `metadata.tags[]` — searchable feature flags (e.g. `["streamlit",
    "sqlite", "vision-first"]`).
  - `metadata.icon`, `metadata.homepage`, `metadata.repository`,
    `metadata.docs`, `metadata.demo_video` — discovery URLs.
  - `metadata.language` — ISO 639-1 (default `"en"`).
  - `metadata.created`, `metadata.updated` — ISO date strings.

- **`windows` section** — Windows 11 specifics, captured fully in
  `spec/v2.15/windows-extensions.yaml`. Notable additions:
  `windows.appdata_folder`, `windows.log_folder`, `windows.cache_folder`,
  `windows.provenance_folder`, `windows.eval_folder`,
  `windows.workflows_folder`, `windows.briefings_folder`,
  `windows.default_port`, `windows.scheduled_task`, `windows.launcher`,
  `windows.launch_command`, `windows.chrome_only`,
  `windows.requires_admin`, `windows.min_powershell_version`,
  `windows.env_vars_optional[]`.

- **`grok` section** — `grok.model`, `grok.temperature`, `grok.max_tokens`,
  `grok.top_p`, `grok.system_prompt_file`, `grok.user_template_file`,
  `grok.tool_calling`, `grok.vision`, `grok.streaming`,
  `grok.fallback_model`.

- **`tools[]` array** — three permitted tool types:
  - `local_function` — `module`, `function`, `parameters.schema` (JSON
    Schema-shaped object literal).
  - `public_api` — references a `public_apis[]` entry by `api_ref` and
    declares the function call surface.
  - `mcp_server` — Model Context Protocol server reference.

- **`public_apis` section** — declares free / rate-limited APIs the
  agent uses, with `auth_env_var`, `rate_limit`, `privacy`, and
  `source_authority` fields per entry. Lets the safety scanner reason
  about external dependencies.

- **`multi_agent` section** — `multi_agent.role`,
  `multi_agent.delegates_to[]`, `multi_agent.shared_memory`,
  `multi_agent.message_bus`, `multi_agent.max_concurrent_workers`.

- **`real_time_x` section** — `real_time_x.enabled`,
  `real_time_x.reply_only`, `real_time_x.consent_required`,
  `real_time_x.triggers[]`, `real_time_x.schedule_cron`,
  `real_time_x.cashtag_threshold_pct`, `real_time_x.watched_cashtags[]`,
  `real_time_x.posts`, `real_time_x.max_posts_per_day`.

- **`memory` section** — `memory.enabled`, `memory.provider`,
  `memory.vector_store.backend`, `memory.vector_store.url`,
  `memory.vector_store.collection_prefix`, `memory.episodic`,
  `memory.semantic`, `memory.procedural`, `memory.retention_days`,
  `memory.encryption_at_rest`, `memory.fallback.*`.

- **`provenance` section** — `provenance.enabled`, `provenance.log_path`,
  `provenance.cite_sources`, `provenance.versioned_synthesis`,
  `provenance.contradiction_detection`, `provenance.append_only`,
  `provenance.langfuse.*`.

- **`constitution` section** — required for `kind: "super-agent"`.
  Contains `constitution.file` (markdown link), `constitution.rules[]`,
  `constitution.consent_gates[]`, `constitution.hard_refusals[]`.

- **`safety` section extensions** — `safety.pii_handling`,
  `safety.data_retention_days`, `safety.scanner_severity_floor`,
  `safety.forbidden_actions[]`, `safety.cost_limits.{usd_per_session_max,
  usd_per_day_max, tokens_per_session_max}`,
  `safety.human_in_the_loop.{enabled, confirm_before[],
  timeout_seconds}`,
  `safety.disclaimers.{not_financial_advice, not_tax_advice,
  real_world_action_consent, not_medical_advice}`.

- **New `kind` enum values** — `super-agent`, `x-native`,
  `creator-template`. v2.14 supported only `agent`,
  `finance-dashboard`, `alpha-engine`, `creator-payout-optimizer`, and
  `vision-analyzer`.

- **`auth: "optional"`** for public_apis — flags an external API where
  the auth env var unlocks higher rate limits but is not required.

### Strengthened

- `version` enum is now `["2.14", "2.15"]` — both accepted.
- `name` pattern is enforced as `^[a-z][a-z0-9-]*$` (kebab-case slug
  matching the parent folder name).
- `license` is required and must equal `"Apache-2.0"`.

### Not changed

- All v2.14 required fields stay required: `version`, `kind`, `name`,
  `description`, `author`, `license`.
- v2.14 default semantics for `safety.*`, `install.*` are preserved.
- No fields were removed.

---

## v2.14 — 2026-04-15 (snapshot)

The v2.14 schema lives at `spec/v2.14/grok-agent.yaml` for backwards-
compatibility testing. It contains the six required top-level fields
plus `metadata`, `install`, `safety`, and the original five-kind
enum.

---

## How to upgrade

If you only need v2.14 features, do nothing — your manifest stays
valid.

If you want to use any of the additions above, simply add the new
sections; you do not need to bump `version: "2.14"` to `"2.15"` unless
you adopt at least one v2.15-only feature. Both versions validate side
by side in the same `cli/grok-agent.py validate` run.
