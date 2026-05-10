<!--
Copyright 2026 AgentMindCloud
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Grok Agent OS — Public Discord Bootstrap

> Built for xAI, X, Grok and the ecosystem community. ❤️

This runbook is the source of truth for how the Grok Agent OS public Discord
is structured, who can do what, and how the auto-posted curation digest from
GitHub Actions plugs into it. Every change to channel layout, role grants, or
moderation flow lands here first as a PR before it hits Discord.

---

## Channel structure

| Channel | Purpose | Who can post |
|---|---|---|
| `#announcements` | Releases, RFCs, partnership news. Read-only for Members. | Maintainer |
| `#help` | Install / config questions, manifest validation errors, Windows-PowerShell issues. | All |
| `#showcase` | Share the agents you shipped on top of `grok-agent.yaml` v2.15. | All |
| `#curation-digest` | Auto-posted Mon/Wed/Fri digest of top trust-tier agents + creator template highlights. | Bot only |
| `#x-money-tools` | Discussion of the four X Money tools (companion-dashboard, smart-cashtag-alpha-engine, creator-payout-optimizer, money-vision-analyzer). | All |
| `#super-agents` | Living Narrative Fabric, Self-Evolving Personal OS, Cross-Reality Action Fabric, plus the four lighter Super Agents. | All |
| `#creator-templates` | The 20+ creator-template authors hang out here. | All |
| `#marketplace` | Phase 5 marketplace UX, listing requests, "Deploy to X" feedback. | All |
| `#governance` | Constitution amendments, Hard Six interpretation, escalation channel for moderation. | Maintainer + Contributor |

---

## Roles

- **Maintainer** — repo owners and the small group with merge rights on
  `AgentMindCloud/grok-agent`. Final word on Constitution disputes.
- **Contributor** — anyone with a merged PR. Can pin messages in `#help` and
  triage `#showcase` posts into the right sub-channel.
- **Builder** — granted on first verified install of any v2.15 agent (proof:
  paste the green `grok-agent validate` output in `#help`). Unlocks
  `#super-agents` posting.
- **Member** — default role on join. Can read everything except
  `#governance`, can post in `#help`, `#showcase`, `#x-money-tools`,
  `#super-agents`, `#creator-templates`, `#marketplace`.

Role transitions are manual (Maintainer-granted) until the Phase 5
marketplace ships an OAuth bridge.

---

## Welcome message template

Posted automatically when a new Member joins, via Discord's built-in
"Welcome Screen" or a tiny gateway bot. Multi-paragraph; keep verbatim.

```
Welcome to Grok Agent OS — the open Windows-first distribution layer
for deploying Grok agents on X.

Built for xAI, X, Grok and the ecosystem community. ❤️

Start here:
  1. Read the Code of Conduct: /CODE_OF_CONDUCT.md
  2. Read the Agent Constitution: /safety/constitution.md
  3. Skim the Hard Six in /CLAUDE.md (license header, ecosystem-ally
     tagline, PowerShell-only end-user commands, v2.15 manifest,
     finance disclaimers, local-first privacy).

Try it:
  - Install one agent: `grok-agent install templates/creator/reply-drafter`
  - Validate your own manifest: `python cli/grok-agent.py validate path/to/grok-agent.yaml`
  - State lives at $env:LOCALAPPDATA\grok-agent\ — never under ~/.config.

Where to ask:
  - Install / config errors -> #help
  - Show what you shipped     -> #showcase
  - X Money tool discussion   -> #x-money-tools
  - Super Agent ideas         -> #super-agents

The #curation-digest channel auto-fills Mon/Wed/Fri with the week's
top trust-tier agents and recent template highlights. No need to
subscribe; it's broadcast-only.
```

---

## Posting guidelines

All posters are expected to follow:

- The repo [Code of Conduct](/CODE_OF_CONDUCT.md). Harassment, doxxing,
  spam, and crypto-pump posts are removed on sight (see Moderation
  playbook below).
- The Hard Six from `CLAUDE.md`: Apache 2.0 headers, ecosystem-ally
  tagline, PowerShell-only end-user commands, `grok-agent.yaml` v2.15,
  finance disclaimers, local-first privacy.
- The Article VIII forbidden-phrase list — enforced by `safety/scanner.py
  forbidden-phrase-scan` and documented inline in `CLAUDE.md` (Soft
  Rules section, "Forbidden phrases when generating or executing
  prompts"). Read those there; do not paste them into Discord posts.
  When you mean "more like this", enumerate the additional items
  explicitly so the next reader has the full list.

### Finance content rule

Any post in `#x-money-tools`, `#showcase`, or anywhere else that
discusses portfolio sizing, cashtag alpha, payout strategy, or tax
treatment **must** include the verbatim banner from CLAUDE.md §12:

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

Posts about tax tooling additionally include:

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for
> Vietnam-resident creators with international platform earnings.

Posts about Super Agents that take real-world actions
(Cross-Reality Action Fabric, Self-Evolving Personal OS scheduling)
include:

> ⚠️ **This agent can take real-world actions.** Every action requires
> explicit consent. Review the action plan before approving. The agent
> never acts autonomously.

---

## Moderation playbook

Three short flows. Maintainers + Contributors can act on flow 1 and 2;
flow 3 escalates to Maintainer review in `#governance`.

- **Spam** (links, shillposts, repeated identical messages):
  delete the message, time out the author for 24 hours, drop a one-line
  note in `#governance` with the offending author ID and message
  content. Repeat offenders are banned after the second incident.
- **Off-topic** (wrong channel, but not malicious): move the message
  via reply pointer to the right channel, leave a friendly nudge, no
  timeout. If the same author keeps misposting, DM them with the
  channel layout from this doc.
- **Abuse / harassment / Code-of-Conduct violation**: remove the
  message immediately, time out the author, escalate to `#governance`
  with full screenshot context, and tag a Maintainer. The Maintainer
  team reviews within 24 hours and posts the resolution publicly in
  `#governance` (anonymized for the reporter).

---

## How the auto-digest works

The `#curation-digest` channel is fed by GitHub Actions:

- Workflow: [`.github/workflows/discord-post-curation.yml`](../.github/workflows/discord-post-curation.yml)
- Script: [`scripts/post-discord-digest.py`](../scripts/post-discord-digest.py)
- Trigger: cron mirroring [`.github/workflows/curation-cadence.yml`](../.github/workflows/curation-cadence.yml)
  — Mon/Wed/Fri at 09:00 UTC, plus `workflow_dispatch` for manual re-runs.
- Secret required: `DISCORD_WEBHOOK_URL` (configure once in repo
  Settings -> Secrets and variables -> Actions). The webhook should
  target `#curation-digest` and have no other permissions.

Every run reads `docs/agent-trust-scores.json` to pick the top-3
trust-tier agents and scans the curation output directory under
`$env:LOCALAPPDATA\grok-agent\creator-program\curation\` (in CI, the
workflow redirects `LOCALAPPDATA` to a runner-temp path so the
artifact is reachable). The digest is assembled in markdown and POSTed
to the webhook. If the webhook secret is missing or the script is
invoked with `--dry-run`, the digest prints to stdout and the workflow
exits cleanly.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
