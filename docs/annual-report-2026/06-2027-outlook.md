<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 2027 outlook

2026 was the foundation year. 2027 is the leverage year. The work below is the Tier-3 moonshot ladder — every item is selected because, if it lands, it changes the size of the project's potential by an order of magnitude rather than a percentage.

## Goal 1 — Marketplace v2 with a paid tier (Q1–Q2)

The current marketplace at `marketplace/` is a static-exported Next.js site listing 33 agents under Apache 2.0, all free. Marketplace v2 ships:

- **A paid tier with a 20% revenue share back to contributors.** The 80/20 split is deliberately generous; the goal is to make Grok Agent OS the obvious place to publish a Grok agent that earns money. Every paid agent stays Apache 2.0 — the paid tier sells the hosted runtime, the support contract, and the trust-score guarantee, not the source.
- **Stripe Connect-based payouts** with the same disclaimer surface as the X Money tools (Not financial advice, Not tax advice — see `CLAUDE.md` section 12).
- **A submission flow built on top of the Recipe A / B / C model from `docs/PARAMETERIZED_RECIPES.md`.** Contributors submit a parameter block; the recipe + the scanner + the trust-score formula handle the rest.
- **Per-contributor dashboards** showing install counts (real, not seeded), trust-tier history, eval-delta trends, and revenue.

The detailed paid-tier scaffold was prototyped earlier in Phase 5, deferred for redesign at user direction in P173, and will return as the centerpiece of the 2027 plan.

## Goal 2 — The xAI partnership (Q1–Q3)

The pitch already exists at `docs/pitch/xai-partnership-pitch.md`, the 60-second demo script at `docs/pitch/60-second-demo-script.md`, and the press kit will land in parallel with this annual report. The 2027 work is the relationship: at least one public xAI engineer engagement, an attempt at a co-marketing pilot for the X Money tools (which directly help X creators capitalize on the X Money launch), and an exploration of upstreaming the v2.15 manifest standard into xAI's official Grok agent docs.

The framing remains ecosystem-ally throughout: Grok Agent OS is not a competitor to xAI. It is the Windows-native distribution + runtime + safety layer xAI has not shipped yet, and the project's success is measured by how often Grok is the obvious LLM choice for an agent on X.

## Goal 3 — Agent-to-agent capability advertisement (RFC v2.16, Q2–Q3)

The v2.15 manifest standard is human-facing: it describes an agent so a creator can find and install it. The v2.16 RFC at `docs/pitch/v2.16-rfc.md` extends the standard to be agent-facing: every agent declares its capabilities in a structured form that other agents can query and consume. The end state is a network where the Cross-Reality Action Fabric can ask "who can summarize my mentions today?", get a structured answer, and call the Mention Summarizer over a manifest-defined contract.

The technical surfaces 2027 needs to ship for this:

- A capabilities block in `spec/v2.16/grok-agent.yaml` that declares what an agent can do, what it expects as input, and what it returns.
- A capability-discovery API surface in the marketplace (extends the existing `marketplace/app/api/install/[slug]/route.ts` pattern).
- A capability-handshake protocol in `pulse/` so the MCP server is the in-process router for agent-to-agent calls.
- A backwards-compatibility path: every v2.15 manifest must auto-upgrade to v2.16 unchanged, the same way every v2.14 manifest auto-upgrades to v2.15 today.

## Goal 4 — Hit 50,000 monthly invocations

The end-of-2026 install counter is a 33-slug seed file (`marketplace/data/install-counts.json`); honest numbers do not exist for 2026 because the production analytics layer was deferred. 2027 ships:

- **A real install-counter backend** (Cloudflare Workers or Vercel Edge Functions, stays free-tier compatible at the 50K target) that increments on every `grok-agent install` and every marketplace install button click.
- **An opt-in usage telemetry channel** (per `CLAUDE.md` rule 6, telemetry is opt-in only) that counts monthly invocations across the CLI, the MCP server, the VS Code extension, and the GitHub Action.
- **A public dashboard** at the marketplace landing page so 50K monthly invocations is a number the world can see.

## Goal 5 — Hit 5,000 GitHub stars

The contributor program (`05-contributor-highlights.md`), the Tier-1 polish surfaces (the install-flow ASCII recap, the `doctor` and `--explain` commands, the trust badges, the hero cards), and the marketing.md catalogue (110 ready-to-paste X posts) are the ammunition. The 2027 plan is:

- **Weekly curation posts.** The auto-curation digest workflow at `.github/workflows/discord-post-curation.yml` already ships; the X-side equivalent will fire weekly via a similar cadence file.
- **A monthly "What shipped" newsletter** mirroring the structure of `01-the-year-in-review.md` but at one-month granularity.
- **A contributor program** (separate from the paid tier) that highlights every external contribution on the marketplace landing page.

## Goal 6 — First paid users

This is the lagging indicator that proves Marketplace v2 works. The 2027 target is the first paid Creator Program v2 user — proof that the recipe-driven contribution flywheel can produce an agent good enough that another human pays for it.

## How we will measure 2027

Every metric in `02-metrics.md` will be re-measured with the same methodology in the 2027 annual report. The four new metrics that will join the table:

- Real monthly invocations (target 50K).
- GitHub stars (target 5K).
- Paid-tier agents shipped (target > 0).
- xAI engineer engagements (target > 0).

The repo state on 2026-12-31 — 181 prompts, 33 agents, 21 tests, 34 scanner checks, 1,174 CLI lines, 110 X posts, 0 forbidden-phrase leaks, 3 trust-tier-A agents — is the baseline.

> Not financial advice. References to the paid tier, revenue share, payouts, and Stripe integration above are descriptive of a planned product surface, not financial guidance. Always consult a licensed financial advisor before making decisions.

> Built for xAI, X, Grok and the ecosystem community. ❤️
