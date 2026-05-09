<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# marketing.md — Ready-to-paste X posts for Grok Agent OS

> Built for xAI, X, Grok and the ecosystem community. ❤️

A curated bank of single posts, threads, reply templates, and image captions for promoting every shipped surface of the repo: 4 X Money tools, 7 Super Agents, 22 creator templates, the v2.15 manifest standard, the Windows-first PowerShell CLI, the safety system, and the static marketplace. Every entry is ≤ 280 characters, ready to copy-paste straight into X.

---

## How to use this file

- Each fenced code block is **one post**. Copy the contents of the block, paste into X, post.
- Threads are numbered `N/M`. Paste each tweet in order, replying to the previous one.
- `{placeholders}` mean fill-in-the-blank. Replace before posting.
- The ⚠️ disclaimer lines (`Not financial advice`, `Not tax advice`, `Explicit consent required`) are **verbatim from CLAUDE.md §12**. Never edit them out — char-limit shortening of the surrounding copy is fine, but the disclaimer line stays.
- Position the project **alongside xAI**, never against. We are an ecosystem ally — the distribution + runtime layer xAI hasn't shipped yet.

## Voice & rules

- **Light emoji**, 1–2 per post max. On-brand glyphs: ⚡ 🛡️ 🪟 🧠 🧪 🧰 ❤️.
- **Disclaimers verbatim** on every finance / tax / real-world-action post. The long form (CLAUDE.md §12) lives in READMEs — X posts use the short callout because of the 280-char limit, but the spirit is preserved.
- **No forbidden phrases**: avoid the vague placeholders listed in CLAUDE.md §3 (Article VIII — the safety scanner blocks them in code; we apply the same discipline to outbound copy).
- **No AI-leak phrases**: no `Let me know if you need`, no `Hope this helps`, no `Feel free to`, no `You can now`.
- **Ecosystem-ally framing always**: "the layer xAI hasn't shipped yet", "built for xAI, X, Grok", "every agent shipping on Grok inherits the safety gate". Never "compete", never "alternative to xAI", never sycophantic praise.

---

## Section 1 — Hero / Launch posts

### 1.1 Single — the elevator pitch

```
Grok Agent OS — one YAML, one install command, one safety scanner.

4 X Money tools. 7 Super Agents. 22 creator templates. 33 agents in the marketplace.

Windows-first. Apache 2.0. Local-first by default.

Built for xAI, X, Grok and the ecosystem community ❤️
```

### 1.2 Single — the install hook

```
Post a YAML to X. Anyone reads it, types `grok install this`, and the agent lands on their Windows machine.

No app store. No accounts. No middleman.

One YAML, one command. ⚡

github.com/AgentMindCloud/grok-agent
```

### 1.3 Single — the safety hook

```
Every Grok Agent OS manifest passes through a 34-check Constitution scanner before it can install.

No invisible posting. No mutable provenance. No silent contradictions.

Safety is the install gate, not a footnote. 🛡️
```

### 1.4 Single — the philosophy

```
Grok Agent OS isn't a competitor to xAI. It's the distribution + runtime layer they haven't shipped yet.

Ship the YAML. We handle install, the safety gate, and the marketplace shelf.

Apache 2.0. Built for xAI, X, Grok ❤️
```

### 1.5 Single — the proof point

```
11 production agents. 22 creator templates. 33 marketplace entries. 34 safety checks. 4 GitHub Actions workflows guarding it all.

Open source under Apache 2.0. Windows-first. Local-first.

Built for xAI, X, Grok and the ecosystem community ❤️
```

### 1.6 Thread — main launch (8 tweets)

```
1/ Grok Agent OS just shipped Phase 5.

The missing OS layer for Grok agents on X.

One YAML, one install command, one safety scanner.

Built for xAI, X, Grok and the ecosystem community ❤️

Thread 👇
```

```
2/ The problem we kept hitting:

Every team building on Grok reinvented the same plumbing. Different install paths. Different safety. Different distribution.

No standard. No safety gate. No marketplace.

So we built one.
```

```
3/ The format is one YAML — `grok-agent.yaml` v2.15.

It declares everything: model, tools, public APIs, multi-agent role, safety rules, cost limits, HITL gates.

Compatible with v2.14. Validates with Pydantic. Scans against the Agent Constitution.
```

```
4/ What ships in the repo today:

⚡ 4 X Money tools (your X earnings command center)
🧠 7 Super Agents (incl. 3 flagship: Living Narrative Fabric, Self-Evolving Personal OS, Cross-Reality Action Fabric)
🧰 22 creator templates
🪟 Windows-first PowerShell CLI
```

```
5/ The Agent Constitution has 7 articles + 34 named checks.

Mandatory: consent gates for real-world actions. Append-only provenance. Source citations on every claim. Disclaimers on every finance/tax surface.

No silent contradictions. 🛡️
```

```
6/ Distribution is the killer feature.

Post a manifest on X. Anyone copies the YAML, types `grok install this`, and the agent installs on their Windows box in seconds.

33 agents already on the static marketplace.
```

```
7/ Apache 2.0. Windows 11 + PowerShell. Local-first by default.

Your data stays on your machine under $env:LOCALAPPDATA\grok-agent\.

Telemetry, cloud sync, external APIs beyond what each agent declares — opt-in only.
```

```
8/ Try it now:

github.com/AgentMindCloud/grok-agent

Or post a manifest on X and tag @JanSol0s — we'll run it through the install gate live.

Built for xAI, X, Grok and the ecosystem community ❤️
```

---

## Section 2 — X Money Tools

Four tools. The order is the build order: companion-dashboard → smart-cashtag-alpha-engine → vision-analyzer → creator-payout-optimizer (so #4's importer can target #1's already-shipped schema, and #3 reads from both).

### 2.1 X Money Companion Dashboard (Tool #1)

#### 2.1.1 Single — launch

```
Your X Money dashboard, on Windows.

Track every transaction, categorize with Grok 4.3, generate tax exports, set alerts — all local under $env:LOCALAPPDATA\grok-agent\.

⚠️ Not financial advice.

grok install x-money-companion-dashboard ⚡
```

#### 2.1.2 Thread — 5 tweets

```
1/ The X Money Companion Dashboard is live. Free, open, Windows-first.

Every transaction in one place. Grok-powered categorization. Tax export. Alerts.

Local-first SQLite under $env:LOCALAPPDATA\grok-agent\.

Thread 👇
```

```
2/ Six tabs:

Overview · Transactions · Analytics · Grok Insights · Tax Export · Alerts

Each tab uses the same local SQLite. Add a transaction once, every tab refreshes.
```

```
3/ The Vision Analyzer (Tool #4) writes parsed receipts directly into this dashboard's SQLite via data/import_receipts.py.

Drop a receipt image → Grok 4.3 parses → one-click import → the dashboard sees it.

No exports. No CSVs. Just SQLite.
```

```
4/ ⚠️ Not financial advice. This tool provides information only. Always consult a licensed financial advisor before making decisions.

⚠️ Not tax advice. Tax obligations vary by jurisdiction. Consult a licensed tax professional.
```

```
5/ Install on Windows 11:

.\cli\grok-agent.ps1 install templates/finance/x-money-companion-dashboard

Or paste the manifest on X with `grok install this` — installs on anyone's Windows machine.

Built for xAI, X, Grok ❤️
```

#### 2.1.3 Single — reply-bait

```
Most "X Money trackers" send your data to a SaaS. We send it to a SQLite file in your AppData folder.

🪟 Local-first.
🔒 No cloud sync unless you ask.
⚡ Grok 4.3 categorization.

⚠️ Not financial advice. github.com/AgentMindCloud/grok-agent
```

### 2.2 X Smart Cashtag Alpha Engine (Tool #2)

#### 2.2.1 Single — launch

```
Real-time cashtag intelligence on X.

Narrative momentum. Cross-source contradictions. Grok-powered alpha signals — every signal cited.

When sources disagree, you see both.

⚠️ Not financial advice.

grok install x-smart-cashtag-alpha-engine
```

#### 2.2.2 Thread — 5 tweets

```
1/ The X Smart Cashtag Alpha Engine is live.

Watch cashtags. Spot narrative shifts. Get alpha reports backed by yfinance + CoinGecko + NewsAPI + X search via Grok 4.3.

When sources disagree, the report shows both sides — never silently picks one.

Thread 👇
```

```
2/ Six tabs:

Overview · Watchlist · Charts · Alpha Reports · Portfolio Simulator · Trending

Watchlist threshold alerts. Portfolio what-if simulator. Alpha reports with confidence scoring + provenance on every signal.
```

```
3/ Real-time mode is opt-in only.

Cron 9am + 5pm weekdays. 5% cashtag move trigger. Reply-only mode (zero auto-posts). Max posts per day: 0.

Triggers fire alerts in-app. Posting requires your explicit consent every time.
```

```
4/ Every other "alpha tool" silently averages contradicting sources. We surface them.

Authority spread + value disagreement + recency skew + subject centrality → 0–10 severity score.

Article IV: never resolve silently.
```

```
5/ ⚠️ Not financial advice. This tool provides information only. Always consult a licensed financial advisor before making decisions.

Install: grok install x-smart-cashtag-alpha-engine

Apache 2.0. Windows-first. github.com/AgentMindCloud/grok-agent
```

#### 2.2.3 Single — reply-bait

```
"What's $XAI doing this week?"

The X Smart Cashtag Alpha Engine pulls X chatter via Grok, news via NewsAPI, prices via yfinance, and gives you a cited alpha report — with contradictions surfaced, not smoothed.

⚠️ Not financial advice. ⚡
```

### 2.3 X Creator Payout Optimizer (Tool #3)

#### 2.3.1 Single — launch

```
Forecast your X creator earnings 30/60/90 days out.

Reads revenue from the Companion Dashboard + costs from the Vision Analyzer. Estimates tax by jurisdiction. Cites every assumption.

⚠️ Not financial advice. Not tax advice.

grok install x-creator-payout-optimizer
```

#### 2.3.2 Thread — 5 tweets

```
1/ The X Creator Payout Optimizer is live.

The first creator earnings forecaster that reads from your local Companion Dashboard SQLite (revenue) AND your Vision Analyzer SQLite (parsed receipts).

No spreadsheets. No exports. Just cross-tool reads.

Thread 👇
```

```
2/ Six tabs:

Earnings Forecast · Content Optimizer · Tax Estimator · X Metrics · Content ROI · Settings

Forecast by window + horizon. Optimize by topic. Estimate tax for any date range + jurisdiction.
```

```
3/ Cross-tool READS only.

Tool #3 never writes back to Tool #1 or Tool #4. Their SQLites stay theirs.

Constitution Article III: no manifest-violating cross-tool writes. Every read is logged.
```

```
4/ Tax estimation is the killer feature for creators outside the US.

Especially relevant for Vietnam-resident creators with international platform earnings — declare jurisdiction once, get a date-range estimate.

⚠️ Not tax advice. Consult a tax professional.
```

```
5/ ⚠️ Not financial advice. Not tax advice.

Install on Windows 11:
grok install x-creator-payout-optimizer

Apache 2.0. Local-first. SQLite under $env:LOCALAPPDATA\grok-agent\.

Built for xAI, X, Grok ❤️
```

#### 2.3.3 Single — reply-bait

```
X creator earnings forecasting that actually reads your real numbers from a real local DB — instead of asking you to upload a CSV to someone's SaaS.

Local-first. Open source. Windows-first.

⚠️ Not financial advice. Not tax advice.
```

### 2.4 X Money Vision Analyzer (Tool #4)

#### 2.4.1 Single — launch

```
Drag a receipt → Grok 4.3 vision parses it → one-click import into the Companion Dashboard.

Double-pass validation flags vision-vs-vision contradictions. No silent OCR errors.

⚠️ Not financial advice.

grok install x-money-vision-analyzer
```

#### 2.4.2 Thread — 5 tweets

```
1/ The X Money Vision Analyzer is live.

Drop receipts and statements onto the Streamlit UI. Grok 4.3 vision extracts fields. You review. You import.

Tool #4 is the ONLY tool permitted to write into Tool #1's SQLite. And only via data/import_receipts.py.

Thread 👇
```

```
2/ Six tabs:

Drop Files · Parsed Preview · Validate · Import to Tool #1 · History · Settings

Drop one receipt or a multi-page statement. Vision pass extracts fields. Second pass validates. Disagreements get surfaced, not silently resolved.
```

```
3/ Privacy: pii_handling = redacted-cloud.

The image leaves the box (vision needs the LLM) but documented redaction strips obvious PII before send. Receipt files stay local.

Cloud sync is opt-in only.
```

```
4/ Why double-pass validation matters:

Vision OCR makes mistakes. The fix isn't to hide them — it's to flag them.

When pass 1 says $42.50 and pass 2 says $42.30, you see both. You decide which import.

Article IV: never silently resolve.
```

```
5/ ⚠️ Not financial advice. ⚠️ Not tax advice.

Install: grok install x-money-vision-analyzer

Apache 2.0. Windows-first. Receipts stay under $env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\receipts.

github.com/AgentMindCloud/grok-agent
```

#### 2.4.3 Single — reply-bait

```
Receipts → Grok vision → SQLite, in 3 clicks.

No "upload to our cloud, get an API key, parse, download CSV, import elsewhere" loop.

Drop, parse, import. Two-line install. Local-first.

⚠️ Not financial advice.
```

---

## Section 3 — Super Agents

### 3.1 Thread — 7-tweet fly-by (one tweet per agent)

```
1/ Grok Agent OS ships 7 Super Agents.

3 flagships with full implementations. 4 lighter manifest-only patterns you can extend.

Each gets its own thread. This is the fly-by.

🧠
```

```
2/ Living Narrative Fabric (flagship #1)

Versioned, provenance-first synthesis across X + news + academic + government.

When sources contradict, both stay in the output. Synthesis is rewindable.

Confidence score on every report.
```

```
3/ Self-Evolving Personal OS (flagship #2)

A personal OS that learns your habits + preferences + goals.

Auto-evolves nightly. Every change logged + reversible. Consent gates on real-world actions.

Feels like magic. Acts like an audit trail.
```

```
4/ Cross-Reality Action Fabric (flagship #3)

The bridge between Grok and your Windows machine.

Calendar, files, X, DMs — every action HITL-gated. Every action reversible. Every action provenance-logged.

⚠️ Real-world actions require explicit consent.
```

```
5/ Lighter Super Agents (manifest-only patterns):

· Agent Swarm with Shared Memory — 6 agents (researcher/skeptic/creator/executor/archivist/orchestrator) on Mem0+Qdrant
· Provenance-First Trust Engine — every claim cited + scored
```

```
6/ More lighter patterns:

· Narrative Contradiction Detector — surfaces conflicts across X, news, gov, academic
· Zero-Config "I Want To…" Agent — plain-language goal in, action plan out

Each ships v2.15-valid manifests with consent gates.
```

```
7/ All 7 Super Agents are Apache 2.0, Windows-first, local-first.

Mem0 + Qdrant for memory. Langfuse for tracing. Promptfoo + DeepEval for evals.

Each runs against the Agent Constitution before install.

Built for xAI, X, Grok ❤️
```

### 3.2 Singles — one per agent

#### 3.2.1 Living Narrative Fabric

```
Living Narrative Fabric — versioned synthesis with full provenance on every claim.

6 source families. Contradictions surfaced (not silently resolved). Rewindable history. Synthesis Confidence score 0–100.

Apache 2.0. Windows 11.

grok install living-narrative-fabric
```

#### 3.2.2 Self-Evolving Personal OS

```
Self-Evolving Personal OS.

Learns your habits. Updates nightly. Every change logged + reversible.

Real-world actions HITL-gated by Constitution Article II — agent never acts autonomously.

⚠️ Real-world actions require explicit consent.

grok install self-evolving-personal-os
```

#### 3.2.3 Cross-Reality Action Fabric

```
Cross-Reality Action Fabric.

Connects Grok to your Windows machine — calendar, files, X, DMs.

Every action: explicit consent · reversible · provenance-logged.

Article II isn't a footnote, it's the runtime.

⚠️ Explicit consent required.
```

#### 3.2.4 Agent Swarm with Shared Memory

```
Agent Swarm with Shared Memory.

6 specialized Grok agents (Researcher, Skeptic, Creator, Executor, Archivist, Orchestrator) sharing Mem0 + Qdrant memory.

Visible debate. Mandatory dissent. Memory evolves with each session.

Apache 2.0. ⚡
```

#### 3.2.5 Provenance-First Trust Engine

```
Provenance-First Trust Engine.

Every answer ships with a clickable provenance report. Every source. Every confidence score. Every alternative viewpoint considered.

Built for high-stakes research, journalism, fact-checking. 🛡️

Apache 2.0. Windows-first.
```

#### 3.2.6 Narrative Contradiction Detector

```
Narrative Contradiction Detector.

Hunts contradictions across X + news + gov + academic + your memory. Presents both sides with primary links.

"Choose your narrative" mode lets you pick the branch to explore.

No smoothing. Just surfacing.
```

#### 3.2.7 Zero-Config "I Want To…" Agent

```
Zero-Config "I Want To…" Agent.

Say "I want to launch a weekly newsletter about AI agents with research summaries and Grok-generated visuals" — the agent assembles tools, APIs, memory, UI, and asks for consent before any action.

Apache 2.0. ⚡
```

### 3.3 Demo CTAs

#### 3.3.1 Demo CTA — Living Narrative Fabric

```
Want to see Living Narrative Fabric live?

90-second walkthrough storyboarded in DEMO.md. Recording lands on GitHub Releases tagged super-agent-demos-v1.

Repo: github.com/AgentMindCloud/grok-agent

Built for xAI, X, Grok ❤️
```

#### 3.3.2 Demo CTA — fork the lighters

```
Building your own Super Agent? Start with the lighter manifests:

· agent-swarm-with-shared-memory
· narrative-contradiction-detector
· provenance-first-trust-engine
· zero-config-i-want-to-agent

Each is a v2.15 manifest pattern. Apache 2.0.
```

---

## Section 4 — Creator Templates

### 4.1 Thread — 5-tweet intro

```
1/ 22 creator templates ship with Grok Agent OS.

Every template: one v2.15 manifest + a system prompt + working examples + a `run.py`.

No SaaS. No accounts. Run them on your Windows box with `grok-agent run <template-name>`.

Thread 👇
```

```
2/ The big categories:

· Content generation (idea-gen, thread-builder, reply-drafter, quote-tweet)
· Analytics (analytics-summarizer, follower-quality, competitor-watch)
· Engagement (mention-summarizer, dm-triager, comment-engagement)
```

```
3/ More:

· Growth (ab-test, growth-experiment, content-calendar, hashtag-strategy, trend-aligned-poster)
· Distribution (cross-platform-reposter, content-recycler, niche-influencer-finder)
· Creator economy (monetization-optimizer w/ ⚠️ finance disclaimer)
```

```
4/ Plus daily-briefing-agent + research-assistant for the workflows that aren't strictly creator but every creator wants.

Voice profiles. Brand voice training from your past posts. Multi-source research with contradiction flags.
```

```
5/ All 22 are Apache 2.0, local-first, Windows-first.

No template phones home. No template auto-posts. Every action that touches X is HITL-gated.

Pick one, fork the manifest, ship your variant.

Built for xAI, X, Grok ❤️
```

### 4.2 Themed cluster posts (6 themes)

#### 4.2.1 Content generation

```
Stuck on what to post? 4 templates have you covered:

· content-idea-generator — batch idea cards scored on niche + originality + voice fidelity
· thread-builder — multi-variant threads with hook strength scoring
· quote-tweet-suggestor
· reply-drafter
```

#### 4.2.2 Analytics

```
Want to know what's actually working?

· analytics-summarizer — weekly metrics + audience-quality paradox detection
· follower-quality-analyzer — bot detection + top-follower archetypes
· competitor-watch — content gaps from named competitors

Apache 2.0. ⚡
```

#### 4.2.3 Engagement

```
Drowning in mentions and DMs? 3 triage templates:

· mention-summarizer — 100+ mentions sorted into 3 bands + priority queue + troll-cluster guard
· dm-triager — 4 buckets (urgent/opportunity/routine/spam)
· comment-engagement-booster — 3–5 comment variants
```

#### 4.2.4 Growth

```
Want to grow without guessing?

· ab-test-suggester — single-axis test plans
· growth-experiment-runner — hypothesis-driven cards w/ sample power
· content-calendar-builder — 4–12 weeks w/ over-scheduling paradox
· hashtag-strategy-advisor
```

#### 4.2.5 Distribution

```
Stop reinventing every post:

· cross-platform-reposter — adapt one X post to LI/Threads/Bluesky/Newsletter w/ voice drift guard
· content-recycler — refresh old posts into 2–3 variants
· niche-influencer-finder — micro/mid/macro collab discovery
```

#### 4.2.6 Creator economy

```
Two creator-economy templates ship Apache 2.0:

· monetization-optimizer — diversification score, sponsor fit, channel mix paradox detection
· brand-voice-trainer — voice profile from your past posts + paste-anywhere training prompt

⚠️ Not financial advice.
```

---

## Section 5 — CLI + v2.15 Manifest Standard

### 5.1 Thread — 6-tweet CLI walkthrough

```
1/ Grok Agent OS ships a Windows-first CLI.

grok-agent.ps1: install · validate · new · list · run

One command per verb. PowerShell-only. Apache 2.0.

Thread 👇 ⚡
```

```
2/ `install` is the killer command.

.\cli\grok-agent.ps1 install <path-or-url>

Or paste-from-stdin:

.\cli\grok-agent.ps1 install -FromStdin

Then paste the YAML, hit Ctrl-Z + Enter. Validates → scans → copies to AppData. Done.
```

```
3/ `validate` runs the v2.15 schema check via Pydantic.

.\cli\grok-agent.ps1 validate <manifest>

Catches schema errors before install. Same check that runs in CI on every PR.

Run safety/scanner.py separately for the 34-check Constitution sweep.
```

```
4/ `new <name>` scaffolds a fresh agent.

Creates the folder. Writes the v2.15 manifest skeleton. Drops the disclaimers in the right place.

Edit, validate, install. Ship.
```

```
5/ `list` shows installed agents + their manifests + their last-run timestamp.

`run <name>` resolves the launcher (PowerShell .ps1 or python app.py) and starts the agent.

All state under $env:LOCALAPPDATA\grok-agent\agents\<name>\.
```

```
6/ The whole CLI is one .ps1 file — readable, hackable, Apache 2.0.

1300+ lines of PowerShell that nobody is going to ship as proprietary.

github.com/AgentMindCloud/grok-agent/blob/main/cli/grok-agent.ps1

Built for xAI, X, Grok ❤️
```

### 5.2 Singles

#### 5.2.1 The paste-flow

```
Post a YAML to X.

Anyone reading replies with `grok install this`.

The CLI has -FromStdin. Pipe the manifest in. Ctrl-Z + Enter to commit. Validates → scans → installs.

No app store. No accounts. No middleman. ⚡
```

#### 5.2.2 v2.15 highlights

```
grok-agent.yaml v2.15 highlights:

· windows extension (appdata, launcher, scheduled tasks)
· multi_agent block (role, delegates_to, shared_memory)
· real_time_x (cashtag triggers, reply-only, max-posts-per-day)
· provenance (append-only, contradictions)
```

#### 5.2.3 v2.14 backwards compat

```
v2.15 is a 100% backwards-compat upgrade over v2.14.

Every v2.14 manifest validates as v2.15 unchanged. The v2.15 schema only adds — never removes, never renames.

grok-agent validate auto-handles the upgrade.
```

#### 5.2.4 Pick your kind

```
Building a new agent kind?

Pick `kind: "agent"` for general, or one of the specialized kinds (super-agent, finance-dashboard, alpha-engine, vision-analyzer, creator-template, …).

Each kind has its own constitution rules and disclaimer requirements.
```

---

## Section 6 — Marketplace

### 6.1 Thread — 4 tweets

```
1/ The Grok Agent OS marketplace just shipped.

33 agents. Static Next.js export. Deployed to GitHub Pages.

No login. No telemetry. No backend. Every agent is one click from install.

Thread 👇 🪟
```

```
2/ Categories:

· Super Agents (7) — flagships + lighter patterns
· X Money Tools (4) — finance / alpha / payout / vision
· Creator Templates (22) — content, growth, analytics, engagement

Filter by category. Search by Ctrl+K. Static-fast.
```

```
3/ One-click install:

Every card has a "Copy install command" button. Pastes:

  grok install this

  Manifest: <github raw URL>

Paste it on X. Anyone running the CLI on Windows installs the agent in seconds.
```

```
4/ Static export → GitHub Pages.

No auth. No accounts. No middleman fees. Just a curated catalog of every v2.15 agent in the repo.

Open the URL → pick an agent → install.

Built for xAI, X, Grok ❤️
```

### 6.2 Singles

#### 6.2.1 The deploy form

```
Want to add your agent to the marketplace?

The /deploy form on the marketplace site is a client-side React app that emits a v2.15 manifest. Fill the fields, copy the YAML, post it on X.

Apache 2.0. Build-time scan. No backend.
```

#### 6.2.2 Search + filters

```
Marketplace UX:

· Ctrl+K command palette — fuzzy search across all 33 agents
· Category chips — Super Agents / X Money Tools / Creator Templates
· CRT scanline overlay — because the brand is Apple-IIe-meets-cinnabar

🪟⚡
```

#### 6.2.3 The open shelf claim

```
Most agent marketplaces gate distribution behind accounts + revenue share.

Ours gates it behind: does your YAML pass the safety scanner?

If yes, you're on the shelf. Apache 2.0. Static export. Free forever for the catalogue itself.
```

---

## Section 7 — Safety / Constitution / Provenance

### 7.1 Singles

#### 7.1.1 Constitution one-liner

```
The Agent Constitution has 7 articles + 34 named checks.

Apache 2.0. Windows-first. Disclaimers mandatory. Consent gates non-negotiable. Provenance append-only. Hard refusals enforced.

Every install runs the scanner before the file copies. 🛡️
```

#### 7.1.2 Consent gates (Article II)

```
Article II — every real-world action requires explicit consent.

Post to X · send DM · move funds · export tax · sync cloud · modify files · publish synthesis.

No auto-fire. No timeouts that default to yes. Always-explicit always-on.
```

#### 7.1.3 Hard refusals (Article III)

```
Article III — hard refusals.

No impersonation. No authenticated scraping. No data exfiltration. No safety-scanner bypass. No autonomous real-world actions. No silent contradictions. No harm to xAI / X.

The scanner blocks installs that violate.
```

#### 7.1.4 Provenance (Article IV)

```
Article IV — provenance.

Cite sources. Version syntheses. Flag contradictions. Append-only log.

No claim ships without a source_id. No synthesis ships without a confidence score. No contradiction gets silently resolved.
```

### 7.2 Thread — 5 tweets

```
1/ Why the Agent Constitution exists.

"Be careful" doesn't scale. "Mandatory disclaimers + consent gates + provenance + scanner" does.

7 articles. 34 named checks. Every install gated.

Thread 👇 🛡️
```

```
2/ Article I — license, ally framing, Windows-first, v2.15 schema, strong disclaimers, local-first privacy.

Article II — consent gates on every real-world action.

Article III — hard refusals (no impersonation, no scraping, no exfiltration).
```

```
3/ Article IV — provenance. Cite sources, version syntheses, flag contradictions, append-only logs.

Article V — mandatory disclaimers. "Not financial advice." "Not tax advice." "Real-world actions require consent." Verbatim wording.
```

```
4/ Article VI — cost limits + HITL gates with timeouts.

Article VII — PII handling tiers (local-only / redacted-cloud / external-required).

No agent declares these as future work. Every manifest declares the relevant tier upfront.
```

```
5/ Article VIII (forbidden phrases) was added when the scanner caught vague language in production code.

Vague rules become broken rules. The Constitution is concrete.

The scanner blocks vague placeholders. Specificity is enforced, not requested.
```

---

## Section 8 — Roadmap / Phase 5 / xAI Partnership

### 8.1 Phase 5 status

```
Grok Agent OS is in Phase 5.

Phases 1–4 complete. 4 X Money tools, 7 Super Agents, 22 creator templates, full self-improvement infra all shipped.

Phase 5 is the marketplace + the xAI partnership pitch.

Built for xAI, X, Grok ❤️
```

### 8.2 The vision

```
The end-of-2026 scoreboard:

· 50k+ monthly invocations
· 5k+ GitHub stars
· The default way to ship Grok agents on X
· ≥1 public xAI engineer engagement
· First paid users via Creator Program v2
```

### 8.3 The xAI partnership pitch

```
To xAI: we built the OS layer for Grok agents on X that you haven't shipped yet.

Apache 2.0. No royalty. No exclusivity. No fork strategy. Just a layer for everyone shipping on Grok.

Read the pitch: docs/for-xai-adoption.md
```

### 8.4 Creator Program v2

```
Creator Program v2 ships in Phase 5.

Mon/Wed/Fri curation cadence. Trend analyzer. Top-3 template selector. Launch-thread generator. Retro collector — all in CI.

Open source so creators can fork the entire program.
```

---

## Section 9 — Engagement / Quote-Tweet / Reply Templates

These are templates with `{placeholders}` you fill in before posting. Don't paste blind.

### 9.1 Reply when xAI ships something

```
Template — when xAI ships [feature]:

"Big day for the ecosystem. Grok Agent OS already ships {your_use_of_X}. v2.15 manifests can declare {feature} so every agent shipping on Grok inherits it. Apache 2.0, repo in bio."
```

### 9.2 Reply when a creator vents about earnings tracking

```
Template — when a creator vents about X earnings tracking:

"Built a free open-source dashboard for exactly this — categorizes transactions with Grok 4.3, exports tax CSVs, all local SQLite. ⚠️ Not financial advice. Search 'x-money-companion-dashboard'."
```

### 9.3 Reply to "we need agent standards"

```
Template — when someone posts a 'we need agent standards' take:

"Building this as Grok Agent OS — one YAML, one install command, one safety scanner. v2.15 schema is open. Apache 2.0. github.com/AgentMindCloud/grok-agent."
```

### 9.4 Reply to alpha-trader posts

```
Template — when an alpha thread surfaces (cashtag-heavy):

"If you want this with cited sources + contradictions surfaced (not silently resolved), the X Smart Cashtag Alpha Engine ships free under Apache 2.0. ⚠️ Not financial advice."
```

### 9.5 Quote-tweet for ecosystem launches

```
Quote-tweet template — for ecosystem launches you want to amplify:

"{author}'s {project} is exactly the kind of thing Grok Agent OS is built to host. v2.15 manifests welcome. PR / paste-on-X / install-via-CLI — pick your distribution."
```

### 9.6 Reply to a closed-source tool that should be open

```
Template — when someone posts a closed-source tool that should be open:

"Adjacent open-source pattern: Grok Agent OS ships {nearest-template} under Apache 2.0. Local-first, Windows-first, runs against the Agent Constitution. Repo in bio."
```

---

## Section 10 — Image-post Captions

Short captions to pair with screenshots, diagrams, or marketing visuals.

### 10.1 CLI screenshot

```
The whole grok-agent CLI on one screen.
install · validate · new · list · run.
One PowerShell file. Apache 2.0. ⚡
```

### 10.2 Marketplace screenshot

```
The Grok Agent OS marketplace — 33 agents, static export, Ctrl+K to search. 🪟
```

### 10.3 Architecture diagram

```
Grok Agent OS architecture: one YAML → Pydantic → Constitution scanner → Windows AppData install. No middleman. 🛡️
```

### 10.4 Living Narrative Fabric synthesis screenshot

```
Living Narrative Fabric in action: 6 sources, contradictions surfaced, confidence score on the synthesis, full rewind history.
```

### 10.5 X Money Companion Dashboard screenshot

```
X Money Companion Dashboard — 6 tabs, all running off one local SQLite under $env:LOCALAPPDATA\grok-agent\.

⚠️ Not financial advice.
```

### 10.6 The ecosystem-ally line as a wallpaper

```
Built for xAI, X, Grok and the ecosystem community ❤️

github.com/AgentMindCloud/grok-agent
```

---

## Posting cadence (suggested, not mandatory)

A guideline for spacing the bank above without over-saturating the timeline.

- **Week 1**: Section 1 hero singles (5 posts) + the main launch thread (1).
- **Week 2**: Section 2 — one X Money tool per day (Mon/Wed/Fri launch single + thread on the next day; reply-bait single on weekend).
- **Week 3**: Section 3 Super Agents — 7-tweet fly-by Mon, then one single per agent across the week + 2 demo CTAs Sat/Sun.
- **Week 4**: Section 4 Creator Templates — intro thread Mon, themed cluster posts Tue–Sat.
- **Week 5+**: Sections 5–8 (CLI, Marketplace, Safety, Roadmap) — pick one thread per week, one single per day.
- **Always-on**: Section 9 reply templates and Section 10 image captions — fire when the moment matches.

Don't post all at once. The goal is steady drumbeat, not flood.

---

## Final checklist before posting

Run through this list once per post. It's the same discipline the safety scanner enforces on manifests.

- [ ] ≤ 280 characters (X enforces; thread tweets each ≤ 280)
- [ ] §12 disclaimer present on every finance / tax / real-world-action post (verbatim short form: `⚠️ Not financial advice.` / `⚠️ Not tax advice.` / `⚠️ Real-world actions require explicit consent.`)
- [ ] No forbidden phrases (the Article VIII list — see CLAUDE.md §3 for the exact set)
- [ ] No AI-leak phrases (no `Let me know`, no `Hope this helps`, no `Feel free to`, no `You can now`)
- [ ] Ecosystem-ally framing (never "compete with xAI"; always "the layer xAI hasn't shipped yet" or "built for xAI, X, Grok")
- [ ] 1–2 emojis max, on-brand glyphs only
- [ ] Placeholders replaced (no raw `{your_handle}` or `{nearest-template}` shipped)
- [ ] Repo link is `github.com/AgentMindCloud/grok-agent`
- [ ] Install commands use the canonical form: `grok install <slug>` or `.\cli\grok-agent.ps1 install <path>`

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
