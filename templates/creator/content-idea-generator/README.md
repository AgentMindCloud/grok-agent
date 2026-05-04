<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# Content Idea Generator

> 5 fresh X post ideas, every morning. Niche-aware, tone-aware, Windows-native, zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — install once, ship daily, never run dry.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\content-idea-generator

# 2. Generate today's 5 ideas in your niche:
python run.py --x-handle @JanSol0s --niche "AI agents on X"

# 3. Save the bundle to a markdown file you can paste anywhere:
python run.py --x-handle @JanSol0s --niche "fintech for solopreneurs" --output today.md

# 4. Try a different tone or window:
python run.py --x-handle @creator --niche "productivity" --tone thoughtful --trend-window-days 14
```

The output is a daily-deterministic markdown bundle: same handle + same niche + same date = the same 5 ideas. Tomorrow you get 5 fresh ones automatically. Override the date with `--date 2026-05-04` if you want to regenerate yesterday's set or schedule ahead.

---

## What you get

- **5 distinct ideas per run**, each a self-contained card with hook, angle, format, why-now, draft opener, and engagement signal
- **8 angle archetypes** rotated per run: contrarian, data-led, story-led, list-led, prediction, comparison, how-to, hot-take — no two cards share an angle in a single run
- **Grok Imagine prompts** auto-generated for every image-led idea, ready to paste into Grok
- **Tone control** — `punchy` (default), `thoughtful`, or `data-led` — applied to the draft opener
- **Trend window control** — 1 to 30 days; the why-now line picks up the window automatically
- **Local-first** — every run is offline-safe, no telemetry, no upload
- **Finance-adjacent guardrail** — cashtag/token/earnings-touching ideas auto-tag with a `Context only -- not financial advice.` line on the affected card

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --niche "creator economy" `
    --count 5 `
    --tone punchy `
    --trend-window-days 7 `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--niche` | yes | — | Niche or topic area, in quotes. |
| `--count` | no | `5` | Number of ideas to return (1–10). |
| `--tone` | no | `punchy` | One of: `punchy`, `thoughtful`, `data-led`. |
| `--trend-window-days` | no | `7` | Trend look-back window (1–30). |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

Niche bucket detection is automatic (`ai`, `finance`, `productivity`, `creator`, `fitness`, `general`) — phrase your `--niche` naturally and the runner will route to the right idea pool.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — 5 ideas for `@JanSol0s` in the *AI agents on X* niche.
- [examples/niche-productivity.md](examples/niche-productivity.md) — 5 ideas for `@solo` in the *Productivity systems for solopreneurs* niche, `thoughtful` tone.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --niche "AI agents on X" --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --niche "Productivity systems for solopreneurs" --tone thoughtful --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled idea library is intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Open `run.py` and replace the body of `generate_ideas()` with an xAI API call to Grok 4.3.
2. Use `prompts/system.md` (already shipped in P43) as the system message — it encodes the 8 hard rules and the idea-card output schema verbatim.
3. Pass the structured user message: `niche`, `tone`, `count`, `trend_window_days`, plus an optional trend snapshot you supply (X search via Grok 4.3, NewsAPI, etc.).
4. Keep the `render_report()` shape intact — it already matches the system-prompt's idea-card schema, so the live model's output drops in untouched.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate stats, quotes, or news headlines.
2. No two ideas may share the same hook or framing.
3. Surface trends as inspiration, never as endorsement.
4. Refuse engagement-bait that violates X policy.
5. Tag finance-adjacent ideas with a context-only note.

The v1 demo runner enforces #2 (8-angle rotation per run), #3 (neutral phrasings, no buy/sell language), and #5 (finance-keyword detection). Rules #1 and #4 fully land when you wire to live Grok 4.3 in the step above.

---

## Files in this folder

```
content-idea-generator/
├── grok-agent.yaml                 # v2.15 manifest (P43)
├── prompts/
│   └── system.md                   # Grok system prompt (P43)
├── run.py                          # zero-dependency CLI (P44)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P44)
│   └── niche-productivity.md       # Productivity niche sample (P44)
└── README.md                       # this file (P44)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built to help xAI and Grok win — ecosystem allies, not competitors.
