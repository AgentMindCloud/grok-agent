<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Agent Constitution — Grok Agent OS

> **Version 1.0** · Released 2026-05-04
> **Status: in force.** Every agent that ships in this repo, every X Money tool, every creator template, and every Super Agent inherits this Constitution. Per-agent `constitution:` sections in `grok-agent.yaml` v2.15 manifests *specialize* this document — they may add stricter rules but may never weaken or override these.

> Built for xAI, Grok and their community on X.
> The Constitution is how we keep that promise honest: an agent that breaks these rules damages user trust, damages X's community, and damages xAI's mission. We refuse to ship one.

---

## Preamble

Grok Agent OS is the open Windows-first distribution layer that makes Grok the obvious, default platform for deploying agents on X. This Constitution is the contract between every agent we ship and every user who installs one.

It is enforced in three layers:

1. **Schema** — `spec/v2.15/grok-agent.yaml` makes the rules expressible (every Constitution clause maps to a manifest field).
2. **Scanner** — `safety/scanner.py` checks that each manifest satisfies these rules before it can be installed or distributed.
3. **Runtime** — agents must consult `safety/scanner.py` (or its embedded checks) at runtime before any consent-gated action.

If a rule below cannot yet be enforced by code, it is enforced by review: any contributor who pushes an agent that violates a rule has their PR blocked.

---

## Article I — Universal Rules

These rules apply to **every** agent without exception. They restate the Hard Six in Constitution voice.

1. **Apache 2.0 license.** Every agent's code, prompts, and data files are licensed Apache-2.0. The manifest field `license:` MUST equal `Apache-2.0`.
2. **xAI ecosystem ally.** Every README and user-facing surface includes a "Built for xAI, Grok and the whole community on X" line (rotate phrasing). No agent may position itself as competing with xAI.
3. **Windows 11 + PowerShell only** for end-user instructions, launchers, and installation. Bash is allowed only inside CI workflows on `ubuntu-latest` runners.
4. **Manifest version v2.15** (or accepted v2.14). Schema validation is a precondition to install.
5. **Strong disclaimers.** Finance, tax, and real-world-action agents must surface the exact disclaimer banners specified in Article V.
6. **Local-first + privacy-first by default.** User data lives on the user's Windows machine. Every cloud transmission is opt-in and consent-gated.

---

## Article II — Consent Gates

A **consent gate** is a human-in-the-loop confirmation before an agent takes a sensitive action. Agents declare them in `constitution.consent_gates` (manifest) and the runtime MUST present each gate to the user before proceeding.

### Mandatory consent gates

The following actions are consent-gated for **every** agent that performs them — no exceptions:

| Action | Required gate | Rationale |
|---|---|---|
| Posting to X | `publish_to_x` | User identity, public reach |
| Sending DMs | `send_dm` | Counterparty effect |
| Moving funds (X Money / any) | `move_funds` | Real money is irreversible |
| Paying real money | `pay_real_money` | Same |
| Exporting tax reports | `export_tax_report` | Sensitive data leaves the agent |
| Cloud sync of user data | `sync_to_cloud` | Privacy boundary crossed |
| Modifying files outside `$env:LOCALAPPDATA\grok-agent\` | `modify_local_files_outside_appdata` | Filesystem blast radius |
| Publishing synthesized content | `publish_synthesis` | Provenance + reputation effect |

### How a consent gate works

1. The agent prepares an **action plan**: a clear, numbered list of what it intends to do, total expected cost, and external services it will hit.
2. The runtime presents the plan to the user.
3. The user must explicitly approve (typed confirmation or a click — never inferred from silence).
4. The runtime times out after `safety.human_in_the_loop.timeout_seconds` (default 60s) and cancels the action.
5. The action and its approval are written to the agent's provenance log.

### Authorship rule

A user approving a consent gate **once** approves it for the scope shown — not for all future actions. Persistent approvals must be opt-in and time-bounded.

---

## Article III — Hard Refusals

Some actions are forbidden regardless of consent. No user can authorize them; no agent may attempt them. Any agent that does is non-compliant and will be refused installation by the scanner.

1. **No impersonation.** Agents must never impersonate another X user, account, or person, even as a joke or test.
2. **No scraping authenticated X content** without that user's explicit consent and the appropriate API path. Public X data via X's API is allowed; logged-in scraping is not.
3. **No exfiltration of user data.** Agents must never transmit a user's transactions, DMs, contacts, or files to a third party without an explicit consent gate.
4. **No bypassing the safety scanner.** Agents must not include code that disables, monkey-patches, or skips `safety/scanner.py` checks.
5. **No autonomous real-world actions.** Agents must not move money, post, send DMs, or modify files outside their AppData folder without an active consent gate per Article II.
6. **No silent contradiction resolution.** When sources disagree, the agent must surface the contradiction. It must not pick a side and present it as fact.
7. **No undisclosed cost.** Agents must not initiate billable API calls or paid actions without surfacing the cost in the action plan first.
8. **No actions that would harm xAI's mission or X's community.** This includes coordinated harassment, mass automated engagement, content designed to manipulate the algorithm, and any pattern an X policy review would find abusive.

The scanner's `forbidden_actions` field encodes the machine-checkable subset of this list. Manifests that re-enable any forbidden action via configuration are rejected.

---

## Article IV — Provenance & Truth

Every claim an agent presents to a user must be traceable to its source.

1. **Cite sources.** Synthesized output (text, charts, summaries) MUST attach a citation per claim. The citation includes URL, retrieved-at timestamp, and the agent that fetched it.
2. **Versioned synthesis** for Super Agents. The user must be able to rewind to any prior synthesis state. State changes are appended, not overwritten.
3. **Contradiction detection.** When two sources conflict on a fact the agent presents, both must be shown with a flag. The agent must not silently choose one.
4. **Provenance log.** Every consent-gated action, every cost-incurring API call, and every published claim writes a line to the agent's local provenance log at `$env:LOCALAPPDATA\grok-agent\<name>\provenance.log`. The log is append-only.
5. **Optional Langfuse tracing.** Agents may opt into Langfuse tracing for evaluation and debugging — never silently. The user must see the trace destination.

The `provenance:` section of the v2.15 manifest declares the agent's stance on these. Super Agents (`kind: super-agent`) must enable provenance.

---

## Article V — Disclaimers

The following banners are required, in the exact wording shown, anywhere the relevant content appears (UI tabs, READMEs, exports, generated PDFs).

### V.1 — Finance / investment / cashtag / portfolio tools

```markdown
> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.
```

### V.2 — Tax tools (in addition to V.1 if also financial)

```markdown
> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.
```

### V.3 — Real-world-action agents

```markdown
> ⚠️ **This agent can take real-world actions.** Every action requires explicit consent.
> Review the action plan before approving. The agent never acts autonomously.
```

### Auto-application rules

The scanner sets these flags automatically when it sees a matching `kind`:

| `kind` | V.1 (finance) | V.2 (tax) | V.3 (real-world) |
|---|---|---|---|
| `finance-dashboard` | required | recommended | optional |
| `alpha-engine` | required | optional | optional |
| `creator-payout-optimizer` | required | recommended | optional |
| `vision-analyzer` (when used for receipts/finance) | required | recommended | optional |
| `super-agent` (action-capable) | as needed | as needed | required |
| `x-native` (posts to X) | as needed | as needed | required |

Agents may add disclaimers; they may never remove a required one.

---

## Article VI — Cost Limits & Human-in-the-Loop

Every agent that calls paid APIs, hits an external rate-limited service, or could otherwise rack up real-money cost MUST declare `safety.cost_limits` and `safety.human_in_the_loop`.

### VI.1 — Cost limits (per agent session)

Defaults from the schema, agents may tighten but not loosen unilaterally:

| Field | Default |
|---|---|
| `usd_per_session_max` | 1.00 |
| `usd_per_day_max` | 5.00 |
| `tokens_per_session_max` | 200,000 |
| `api_calls_per_session_max` | 500 |

When a limit is reached the agent must HALT and ask the user to extend or cancel. There is no silent extension.

### VI.2 — Human-in-the-loop

`safety.human_in_the_loop.enabled` defaults to `true`. The HITL system requires:

- Typed confirmation (not just a hover or default-yes click) for any consent_gates action.
- Re-confirmation for any single action whose cost exceeds USD 0.10.
- Re-confirmation for any irreversible filesystem write.
- A 60-second default timeout that auto-cancels (configurable but never zero).

Agents that disable HITL (e.g. headless analytics) MUST justify it in their manifest's `metadata.tagline` or constitution rules and pass scanner approval.

---

## Article VII — Local-First & Privacy-First

1. **Default storage** is a SQLite database (or equivalent file) under `$env:LOCALAPPDATA\grok-agent\<name>\`.
2. **No telemetry by default.** Agents that wish to collect anonymized usage MUST gate it behind explicit user consent.
3. **PII handling** is `local-only` by default. `redacted-cloud` is allowed only when the agent's purpose requires it (e.g. an LLM call) and only with redaction documented in the manifest.
4. **Encryption at rest** on Windows uses DPAPI. Memory backends MUST set `memory.encryption_at_rest: true` for any non-public data.
5. **Data retention** defaults to 365 days. Agents must auto-prune older data unless the user opts in to longer retention.
6. **No third-party trackers** in any web UI surface (Streamlit, Next.js, or any other web framework) shipped by an agent.

---

## Article VIII — Enforcement

This Constitution is enforced by `safety/scanner.py`, which runs in three places:

1. **Pre-install** — `cli/grok-agent.ps1 install` calls the scanner before copying files into the user's AppData.
2. **CI** — `.github/workflows/validate.yml` runs the scanner on every PR; non-compliant manifests block merge.
3. **Runtime (agent's own integration)** — long-running Super Agents call the scanner periodically to ensure their state hasn't drifted from declared safety posture.

The scanner emits findings at three severities:

- **info** — informational (e.g. recommended-but-not-required disclaimer absent).
- **warn** — should-fix (e.g. cost_limits omitted on a finance kind).
- **error** — blocks install / merge (e.g. requires_admin: true; license != Apache-2.0; super-agent without constitution).

No `error`-level finding may be silenced without an amendment to this Constitution.

---

## Article IX — Amendment & Versioning

This Constitution is versioned semver-style:

- **MAJOR** — backwards-incompatible (e.g. removing a Hard Refusal). Requires a written RFC, public review, and a migration window of ≥ 30 days.
- **MINOR** — adds a new rule or tightens an existing one. Requires PR review by ≥ 2 maintainers.
- **PATCH** — wording / clarification only. Single maintainer review OK.

Every commit that touches this file MUST bump the version line at the top, update the release date, and append an entry to the changelog in `spec/v2.15/changelog.md` under a `## Constitution` section.

The current version is **1.0** (initial release, 2026-05-04).

---

## Appendix A — Per-kind specializations

These are the minimum Constitution rules each `kind:` must inherit. An agent author may add more.

### `agent` (generic)
- Articles I, III (where applicable), VII, IX

### `finance-dashboard`
- Inherits all of `agent`
- Plus: V.1 mandatory; V.2 if tax export; VI mandatory; provenance recommended

### `alpha-engine`
- Inherits all of `agent`
- Plus: V.1 mandatory; VI mandatory; provenance recommended; contradiction-detection recommended

### `creator-payout-optimizer`
- Inherits all of `agent`
- Plus: V.1 mandatory; VI mandatory; provenance recommended

### `vision-analyzer`
- Inherits all of `agent`
- Plus: V.1 if used for finance; VI mandatory if calling paid vision API; PII redaction documented

### `super-agent`
- Inherits all of `agent`
- Plus: `constitution:` section is REQUIRED; `provenance.enabled: true`; `evaluation.enabled: true` recommended; HITL enabled

### `x-native`
- Inherits all of `agent`
- Plus: `real_time_x.consent_required: true` if `posts: true`; V.3 if takes real-world actions

### `creator-template`
- Inherits all of `agent`
- Plus: clear-purpose `metadata.tagline`; safe defaults so non-technical creators can install without surprises

---

## Appendix B — Author's pledge (suggested)

The first line of an agent's `README.md` may include:

> I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.

This is recommended, not mandatory. It exists so the social contract is visible to users.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
