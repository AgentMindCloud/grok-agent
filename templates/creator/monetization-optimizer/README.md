<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- IMPORTANT: Information only -- not financial advice. -->
<!-- Built to help xAI and Grok win. -->

# Monetization Optimizer

> ⚠️ **Information only -- not financial advice.** This tool surfaces patterns and bridges; it does not advise. Always consult a licensed financial / tax professional before making decisions. Tax obligations vary by jurisdiction; this is especially relevant for creators with international platform earnings.

> Map your revenue streams. Surface the next move. Niche-aware, Windows-native, zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — paste your revenue streams, get back a structured summary that bridges directly into the X Money tool suite and the rest of the creator-template flow, with the V.1 / V.2 disclaimer chain preserved on every output card.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\monetization-optimizer

# 2. Try the embedded demo bundle (zero-config first run):
python run.py --x-handle @JanSol0s --demo ai

# 3. Run on real streams piped in as JSON:
python run.py --x-handle @JanSol0s --streams '[{"stream_type":"x_money","current_monthly":3400,"prev_monthly":1900,"share_percent":31}]'

# 4. Run on a JSON file you exported from your payout dashboard:
python run.py --x-handle @JanSol0s --streams-file streams.json --goals scale

# 5. Bias toward growth + visualize the Outlook section (7-section output):
python run.py --x-handle @JanSol0s --demo ai --goals growth

# 6. Save the summary to a markdown file:
python run.py --x-handle @JanSol0s --demo finance --output today.md
```

The output is daily-deterministic: same handle + same revenue input + same date = the same summary. Re-run tomorrow on a fresh export and the deltas update automatically.

---

## What you get

- **Headline** — one-line takeaway: dominant stream movement + first concrete next move
- **Current Revenue Streams table** — one row per stream the input contains; columns: `stream_type`, `current_monthly`, `vs prev`, `share %`, `direction`
- **Opportunities (3–5)** — ranked by qualitative ROI labels (`low` / `medium` / `medium-high` / `high`) + effort + confidence; every card carries `📎 Context only -- not financial advice.`
- **Risks (2–3)** — severity (`low` / `medium` / `high`) + concrete failure mode + mitigation hint with a sibling-tool bridge; every card carries the V.1 disclaimer
- **Recommended Actions (3–5)** — concrete imperatives bridging into the X Money tool suite (`x-money-companion-dashboard`, `x-creator-payout-optimizer`, `x-smart-cashtag-alpha-engine`, `x-money-vision-analyzer`) and the creator-template suite (`content-idea-generator`, `reply-drafter`, `mention-summarizer`, `trend-aligned-poster`, `daily-briefing-agent`, `research-assistant`, `analytics-summarizer`); every action carries V.1 + tax-touching actions ALSO carry `⚠️ Not tax advice -- consult a licensed tax professional.`
- **Confidence** — qualitative-only label (`low` / `medium` / `medium-high` / `high`) with a one-sentence reason
- **Outlook** *(optional)* — when `--goals growth` or `--goals scale`, adds a 7th forward-looking paragraph + V.1 disclaimer line
- **Garbage-batch refusal** — if >70% of input rows are empty/null/zero, the runner refuses with a one-line reason instead of faking a summary
- **Aggregate-only privacy** — never exposes individual sponsor names, contract terms, supporter identities, or DM-content
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --demo ai `
    --revenue-focus all `
    --time-range 90d `
    --goals growth `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--streams` | one of | — | Inline JSON list of stream records. |
| `--streams-file` | one of | — | Path to a JSON file with `{streams: [...]}` or just a list. |
| `--date-range` | one of | — | ISO range like `2026-04-05:2026-05-05` (v1: bucket fallback). |
| `--demo` | one of | — | Prefab niche bundle: `ai`, `productivity`, `finance`, `creator`, or `fitness`. |
| `--revenue-focus` | no | `all` | One of: `sponsorships`, `subscriptions`, `tips`, `x_money`, `all`. |
| `--time-range` | no | `90d` | One of: `30d`, `90d`, `12m`. |
| `--goals` | no | `growth` | One of: `growth`, `stability`, `scale`. |
| `--niche` | no | auto | Optional niche hint. |
| `--jurisdiction` | no | bucket-default | `domestic` or `international` — flips the V.2 disclaimer chain on tax-touching actions. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

If no input source is supplied, the runner falls back to the auto-detected niche bucket's prefab bundle so the offline demo always works. Goals=`growth` and `goals=scale` add the 7th Outlook section; `stability` keeps it to 6.

### Stream record shape

```json
{
  "stream_type": "x_money",
  "current_monthly": 3400,
  "prev_monthly": 1900,
  "share_percent": 31,
  "notes": "platform-native payouts climbing post-launch"
}
```

Canonical stream types: `sponsorships`, `subscriptions`, `tips`, `x_money`. The runner gracefully renders any type the input contains; unknown types appear in the table with their input label.

---

## How it slots into the creator-template + X Money tool flow

Monetization Optimizer is the revenue tool — it deliberately bridges to **both** sibling halves of the platform:

| Section | X Money tool bridge |
|---|---|
| Headline + Recommendation #1 | `x-money-companion-dashboard` for unified payout / transactions view |
| Recommendation #2 | `x-creator-payout-optimizer` to forecast next quarter's payouts |
| Risks (when x_money line ≥20%) | `x-money-vision-analyzer` to import receipts into Companion Dashboard SQLite |
| Opportunities (cashtag-correlated) | `x-smart-cashtag-alpha-engine` for market-data context |

| Section | Creator-template bridge |
|---|---|
| Top opportunity expansion | `content-idea-generator` to spin the angle into 5 ideas |
| High-LTV inbound triage | `mention-summarizer` for sponsor / subscriber inbox |
| Risk mitigation (declining stream) | `analytics-summarizer` for retention check |
| Goal=growth/scale | `research-assistant` to investigate the dominant gainer's drivers |
| Daily handoff | `daily-briefing-agent` to thread the revenue-mix shift into tomorrow's brief |

Every bridge mentions that the destination tool carries the same `Not financial advice` chain — the warning travels with the user across tools.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` 90-day analysis for *AI agents on X* with `--goals growth` (showcases the 7th Outlook section + tax-touching action with V.1 + V.2 disclaimers).
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` 90-day analysis for *Productivity systems for solopreneurs* with `--goals stability` (canonical 6-section shape, paid-newsletter-led mix).

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --demo ai --niche "AI agents on X" --goals growth --time-range 90d --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --demo productivity --niche "Productivity systems for solopreneurs" --goals stability --time-range 90d --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled stream data is intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `DEMO_STREAM_BUNDLES` with a real fetcher: pull stream values directly from the user's payout dashboards, X Money payouts via the X API, sponsor contracts via a private CRM, etc.
2. The system prompt at `prompts/system.md` (shipped in P57, ~370 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 12 hard rules (with V.1/V.2 disclaimer mandates), structured 6/7-section schema, ROI/effort/severity vocabularies, and 11 cross-tool bridge candidates.
3. Replace `generate_monetization_optimization()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged — and crucially, it bakes the V.1 / V.2 disclaimers into every money/tax card automatically, so the live model can never silently drop them.
4. Pass the structured user message: `x_handle`, `streams`, `revenue_focus`, `time_range`, `goals`, `niche`, plus the live stream bundle from step 1.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding, real V.1/V.2 chain.

---

## Hard rules (from the manifest's `constitution:` block)

1. **INFORMATION ONLY** — every money-touching card carries `📎 Context only -- not financial advice.`
2. **TAX guardrail** — tax-related cards ALSO carry `⚠️ Not tax advice -- consult a licensed tax professional.`
3. Never fabricate revenue numbers, payout rates, sponsor names, or platform-specific economic claims.
4. Always emit the structured 6-section shape (or 7 with `goals=growth|scale`).
5. ROI / effort / severity / confidence are qualitative labels only — never percentages.
6. Refuse garbage batches (>70% empty/zero rows) with a one-line reason.
7. Privacy: aggregate-only; never expose individual sponsor / supporter identities.
8. Cross-tool bridges mention that destination tools carry the same disclaimer chain.
9. Local-first — no syncing, no upload, no telemetry.
10. No silent contradictions — opposite-direction streams appear in BOTH Opportunities and Risks.

The v1 demo runner enforces every structural rule plus the V.1 / V.2 disclaimer mandate at the **render** layer (the disclaimers are baked into `render_report()` and cannot be silently dropped). Rules #3 and #7 fully land when you wire to live Grok 4.3 — the v1 keyword pipeline never invents stream values.

---

## Files in this folder

```
monetization-optimizer/
├── grok-agent.yaml                 # v2.15 manifest (P57)
├── prompts/
│   └── system.md                   # Grok system prompt, ~370 lines (P57)
├── run.py                          # zero-dependency CLI (P58)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample, growth goals, 7-section (P58)
│   └── niche-productivity.md       # Productivity niche sample, stability goals (P58)
└── README.md                       # this file (P58)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> ⚠️ **Information only -- not financial advice.** Built to help xAI and Grok win — ecosystem allies, not competitors.
