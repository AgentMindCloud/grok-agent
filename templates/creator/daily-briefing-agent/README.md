<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community. ❤️ -->

# Daily Briefing Agent

> Your X day, briefed in 60 seconds. Niche-aware, structured 6-section synthesis, Windows-native, zero-config.

**Built for xAI, X, Grok and the ecosystem community. ❤️** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — wake up, run one command, ship the rest of the day with focus.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\daily-briefing-agent

# 2. Brief today's day with your focus areas:
python run.py --x-handle @JanSol0s --focus-areas "AI agents on X,creator economy"

# 3. Zero-config first run with a prefab niche:
python run.py --x-handle @JanSol0s --demo ai

# 4. Add a Visual Prompt for a hero-card image:
python run.py --x-handle @JanSol0s --demo productivity --suggest-visual

# 5. Save the brief to a markdown file:
python run.py --x-handle @JanSol0s --focus-areas "creator economy" --output today.md
```

The output is a daily-deterministic markdown bundle: same handle + same focus areas + same date = the same briefing. Tomorrow you get a fresh synthesis automatically. Override the date with `--date 2026-05-04` if you want to regenerate yesterday's view.

---

## What you get

- **Headline** — one-line anchor: today's strongest trend signal + your first concrete move
- **5–7 source-tagged Top Signals** — every bullet carries an inline source label (`[trend]`, `[mention]`, `[news]`, `[self]`, `[evergreen]`) so you can verify before acting
- **1–3 Key Trends** — each tagged with strength (`light` / `building` / `strong`) and a niche-relevance one-liner
- **3–5 Action Priorities** — concrete imperatives using the same 6-verb vocabulary as the mention summarizer (`reply now` / `reply within 24h` / `mute` / `block` / `ignore` / `flag for follow-up`)
- **1–3 Suggested Content Ideas** — each picks a distinct angle from the 8-archetype palette (contrarian / data-led / story-led / list-led / prediction / comparison / how-to / hot-take), with a ≤140-char draft opener you can paste directly into X compose
- **Sentiment Overview** — qualitative-only label (`positive` / `neutral` / `negative` / `mixed`) plus a one-sentence reason
- **Visual Prompt** *(optional)* — a Grok Imagine prompt suitable as a hero card when you pass `--suggest-visual`
- **Finance-adjacent guardrail** — priorities and content ideas touching cashtags / tokens / earnings / P&L / tax auto-tag with `Context only -- not financial advice.`
- **Privacy** — phone numbers and email addresses redacted before quoting; mention text quoted selectively
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --focus-areas "AI agents on X,creator economy" `
    --suggest-visual `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--focus-areas` | no | auto | Comma-separated niches (e.g. `"AI agents on X,creator economy"`). Drives bucket detection. |
| `--demo` | no | — | Prefab niche bucket — `ai`, `productivity`, `finance`, `creator`, or `fitness`. Used as fallback when `--focus-areas` is omitted. |
| `--date` | no | today | Override the briefing date (YYYY-MM-DD). |
| `--suggest-visual` | no | off | Append a 7th Visual Prompt section. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--version` | — | — | Print version and exit. |

Niche-bucket detection is automatic — phrase your focus areas naturally and the runner picks the right offline signal bundle.

---

## How the briefing fits with the other 4 creator templates

The Daily Briefing Agent is the morning entry point; every other creator template extends one of its sections:

| Section | Bridge to |
|---|---|
| Today's Top Signals (mentions) | `mention-summarizer` for a deeper triage |
| Key Trends | `trend-aligned-poster` to draft 3 posts tied to a chosen trend |
| Suggested Content Ideas | `content-idea-generator` to expand a single angle into 5+ ideas |
| Action Priorities (replies) | `reply-drafter` to generate 3 voice-matched drafts per pick |

So the daily flow is: brief → pick one section → drop into the matching tool. All five share the same 8-angle palette, 6-verb vocabulary, and Apache-headered output, so handoff is friction-free.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` briefing for *AI agents on X* + *creator economy* during a Grok-4.3-release-week trend cycle (with `--suggest-visual`).
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` briefing for *Productivity systems for solopreneurs* + *creator economy*.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --focus-areas "AI agents on X,creator economy" --date 2026-05-04 --suggest-visual --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --focus-areas "Productivity systems for solopreneurs,creator economy" --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled signal libraries are intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `SIGNAL_BUNDLE_BY_BUCKET` with a real fetcher: trends via Grok 4.3's X-search, mentions via your local mention cache (or sibling `mention-summarizer`'s SQLite), news via NewsAPI / GNews, self-posts via Grok 4.3's user-timeline tool, evergreen from your own niche notebook.
2. The system prompt at `prompts/system.md` (shipped in P51, ~330 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 12 hard rules, structured 6-section schema, inline source tags, trend-strength taxonomy, 6-verb action vocabulary, and 8-angle content-idea palette.
3. Replace `generate_daily_briefing()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged.
4. Pass the structured user message: `x_handle`, `focus_areas`, `date`, `include_visual` plus the live signal bundle from step 1.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding, real synthesis.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate signals, trends, headlines, mention text, or engagement numbers.
2. Always emit the structured 6-section shape (or 7 with `--suggest-visual`).
3. Every Top Signal bullet carries an inline source label.
4. Action Priorities use only the 6 fixed verbs.
5. Suggested Content Ideas use the 8-angle palette, never repeating an angle.
6. Sentiment + trend strength are qualitative labels only — never percentages.
7. Refuse spam-saturated days with a one-line reason.
8. Tag finance-adjacent priorities/ideas with a context-only note.
9. Privacy: redact PII; quote selectively.
10. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces every structural rule (#2–#6, #8, #10). Rules #1, #7, and #9 fully land when you wire to live Grok 4.3.

---

## Files in this folder

```
daily-briefing-agent/
├── grok-agent.yaml                 # v2.15 manifest (P51)
├── prompts/
│   └── system.md                   # Grok system prompt, ~330 lines (P51)
├── run.py                          # zero-dependency CLI (P52)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P52)
│   └── niche-productivity.md       # Productivity niche sample (P52)
└── README.md                       # this file (P52)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built for xAI, X, Grok and the ecosystem community — ecosystem allies, not competitors.
