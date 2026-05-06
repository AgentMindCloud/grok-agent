<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Phase 6 Kickoff — Creator Program v2 + Sustainable Growth

> **Built for xAI, X, Grok and the ecosystem community. ❤️**
> Phase 6 turns the foundations shipped in Phases 1–5 (manifest standard, X Money tools, 22 creator templates, 7 Super Agents, marketplace, xAI partnership pitch) into a **sustainable creator economy** running on Grok Agent OS.

---

## Status & scope

Phases 1–4 are complete. Phase 5 (marketplace + xAI partnership) is active — `docs/workplan-audit.md` tracks the gap. Phase 6 begins **once Phase 5 P125–P126 ship** (Next.js marketplace live on Vercel + xAI pitch deck delivered) and runs across **Q3–Q4 2026**.

Phase 6 covers four workstreams:

1. **Creator Program v2** — paid tier, revenue share, weekly curation rhythm.
2. **Contributor program** — external developers shipping templates against a published quality bar.
3. **Self-improvement loop hardening** — the Promptfoo + DeepEval + Langfuse cadence shipped in P122 runs continuously.
4. **xAI partnership follow-through** — turn the P126 pitch into recurring engagement.

All four operate on the same rails defined in `CLAUDE.md`: Apache 2.0 throughout, ecosystem-ally tagline on every surface, Windows 11 + PowerShell for every user-facing command, local-first storage under `$env:LOCALAPPDATA\grok-agent\`, Constitution v1.0 enforced in CI.

---

## Creator Program v2

The Phase 3 program (free, hand-onboarded, 22 templates) proved the flywheel. Phase 6 graduates it into a sustainable operation that compensates the creators who carry the platform.

### Free vs Premium tier structure

Pricing is a **target proposal** for community feedback, not a commitment. Final numbers land after the first 30 days of public-marketplace data.

| Capability | Free | Premium (target) |
|---|---|---|
| `grok-agent install` from public marketplace | yes | yes |
| `grok-agent run` for any installed agent | yes | yes |
| Use any of the 22 Phase 3 creator templates | yes | yes |
| Public marketplace listing for templates you publish | yes | yes (with featured slot eligibility) |
| Advanced templates (private + cross-template orchestration) | no | yes |
| Priority support response window | best-effort | target 24h on weekdays |
| Personal analytics dashboard (install counts, retention, payout history) | basic | extended |
| Weekly curation eligibility (paid spotlight) | no | yes |
| Revenue share on installs of your templates | no | yes (see below) |

Target Premium price: **$19/month** for individual creators, **$49/month** for teams of up to 5. These figures are proposals; they will be finalized once Phase 5 marketplace metrics are in.

### 20% revenue share model

Premium creators publishing templates to the marketplace earn **20% of net revenue** attributable to their templates. "Net" means after payment-processor fees and any pass-through API costs the agent declares in `safety.cost_limits`.

Payout mechanics (target — subject to refinement before P127 ships):

- **Reporting** — Each Premium creator sees a payout dashboard at the marketplace `/creator/payouts` page. Every install, run, and revenue event ties back to a manifest hash and a Langfuse trace ID for auditability.
- **Cadence** — Monthly payouts on the 5th business day of the following month.
- **Threshold** — Minimum payout of **$25** (smaller balances roll forward).
- **Method** — Default fiat via Stripe Connect. **Opt-in stablecoin payouts** in USDC for creators who prefer crypto rails.
- **Transparency** — Quarterly aggregate revenue numbers published in `docs/creator-program/quarterly-report.md` so the community sees real metrics, not hand-waving.

> ⚠️ **Not financial advice.** The revenue-share figures above are program targets for the AgentMindCloud-operated marketplace. They are not investment guidance. Tax obligations vary by jurisdiction.
>
> ⚠️ **Not tax advice.** Creator payouts are taxable income in most jurisdictions. Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

### Weekly curation cadence

A predictable rhythm beats sporadic announcements. Phase 6 commits to a published weekly cycle:

- **Monday** — The curation team (initially `@JanSol0s` plus 2 community curators) reviews the prior week's marketplace activity and selects **3 winning templates of the week**. Selection criteria: manifest quality, Constitution-clean scan, install retention, and net new value to creators on X.
- **Wednesday** — Public **launch thread** on X spotlighting the 3 winners. Each gets a 2-tweet quote summary, an install command, and creator attribution.
- **Friday** — Public **retro + community vote** in the GitHub Discussions board. Community members upvote which template they want featured the following week, plus open feedback on the program itself.

The curation log lives at `docs/creator-program/curation-log.md` and ships its first entry the week P127 lands.

### Contributor program

Phase 3 onboarded creators as **users** of templates. Phase 6 onboards external developers as **builders** of templates against a published quality bar.

- **Onramp** — `docs/creator-program/contributor-guide.md` (ships in P130) walks a developer from fork to first PR. Companion **mentorship onramp**: each new contributor pairs with an existing maintainer for their first merged template.
- **Quality bar** — A PR is mergeable only when (1) the manifest validates against `spec/v2.15/grok-agent.yaml`, (2) `safety/scanner.py` reports zero findings, (3) at least one runner example is offline-deterministic, (4) all required disclaimers are present, (5) CI on `.github/workflows/validate.yml` passes.
- **Code review** — Every contributor PR gets at least one review from a designated maintainer. Reviews check the five quality-bar items above plus tone, naming conventions, and Windows-first command usage.
- **Attribution** — Contributors are credited in three places: the template's `grok-agent.yaml` `author` field, the `CONTRIBUTORS.md` ledger, and the weekly curation thread when their template wins a spotlight.
- **CLA** — A lightweight CLA confirms the contributor has the right to license under Apache 2.0. The CLA bot runs on every PR.

---

## Success metrics for Phase 6

These are **targets** for community accountability, not promises. They are revised at the end of each quarter against actual data.

| Metric | Target by end of Q4 2026 |
|---|---|
| Active creators (≥ 1 install/week) | 100 |
| Templates in public marketplace | 500 |
| Premium subscribers | 200 (target — pricing not yet finalized) |
| Monthly recurring revenue (target) | $4k (a directional figure, not a forecast) |
| Weekly invocations across all installed agents | 10,000 |
| External contributor PRs merged | 50 |
| Public xAI engineer engagement events | 3 |

> ⚠️ **Not financial advice.** All revenue and subscriber numbers are program targets, not financial projections or investment guidance.

---

## Timeline — Q3–Q4 2026 milestone calendar

| Month | Milestone |
|---|---|
| **July 2026** | P127–P131 ship: Premium tier scaffolding, marketplace billing integration, curation log v1, contributor guide v1, first public weekly thread. |
| **August 2026** | First 50 Premium creators onboarded. First payouts processed (test mode). Curation log has 4 weekly entries. |
| **September 2026** | First production payout cycle. Contributor program launches publicly. CLA bot live on every PR. 25 external PRs merged. |
| **October 2026** | First quarterly transparency report published. Stablecoin payout opt-in launches. Curation team expands to 5 community curators. |
| **November 2026** | Mid-program review against Q4 targets. Pricing finalized based on first 90 days of marketplace data. xAI partnership follow-up call. |
| **December 2026** | Phase 6 retro + Phase 7 plan published. Annual transparency report shipped. Year-end community recognition for top contributors. |

---

## First 5 prompts of Phase 6 (P127–P131)

Each prompt is sized to the standard `docs/PROMPT_TEMPLATE.md` 7-section structure and ships in order.

### P127 — Premium tier scaffolding

- **Goal:** Add the data model + marketplace surfaces required for Premium subscriptions.
- **Primary deliverable:** `marketplace/premium/` directory with subscription schema (Pydantic), Stripe Connect adapter scaffold, and a Streamlit-rendered `/creator/billing` page.
- **Recipe:** none (Phase 6 is post-Recipe; falls back to PROMPT_TEMPLATE.md).

### P128 — Revenue share calculator + payout dashboard

- **Goal:** Implement the 20% revenue-share calculation and surface a per-creator payout dashboard.
- **Primary deliverable:** `marketplace/premium/payouts.py` (calculator), `/creator/payouts` page (dashboard), unit tests covering threshold, currency, and stablecoin opt-in paths.
- **Recipe:** none.

### P129 — Curation log v1 + first weekly thread

- **Goal:** Establish the Monday/Wednesday/Friday curation rhythm with a public log and the first launch thread template.
- **Primary deliverable:** `docs/creator-program/curation-log.md` (first entry) + `docs/creator-program/curation-thread-template.md` (Wednesday-thread reusable shell).
- **Recipe:** none.

### P130 — Contributor guide + CLA bot integration

- **Goal:** Publish the developer onramp and wire the CLA bot into every PR.
- **Primary deliverable:** `docs/creator-program/contributor-guide.md` + `.github/workflows/cla.yml` + `CONTRIBUTORS.md` ledger seed.
- **Recipe:** none.

### P131 — Phase 6 public X launch thread

- **Goal:** Announce Creator Program v2 to the X creator audience and pin the thread.
- **Primary deliverable:** `docs/creator-program/v2-launch-thread.md` containing a ≤ 10-tweet thread (each ≤ 280 chars) plus the standalone amplifier post for cross-platform sharing.
- **Recipe:** none.

---

## Where to read more

- **Phase 5 status** — `docs/workplan-audit.md`
- **Master plan** — `CLAUDE.md` (sections 6 + 14)
- **Roadmap context** — `ROADMAP.md`
- **Phase 3 launch precedent** — `docs/creator-program/launch-thread.md`
- **Manifest standard** — `spec/v2.15/grok-agent.yaml`

> Built for xAI, X, Grok and the ecosystem community. ❤️
