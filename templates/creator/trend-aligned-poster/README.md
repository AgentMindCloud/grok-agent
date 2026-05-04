<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# Trend-Aligned Poster

> 3 trend-aware X drafts, every morning. Niche-aware, tone-aware, Windows-native, zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — input your niche, get back three drafts naturally tied to current X trends with full provenance.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\trend-aligned-poster

# 2. Get 3 drafts tied to today's X trending in your niche:
python run.py --x-handle @JanSol0s --niche "AI agents on X"

# 3. Try a different trend source (news headlines instead of X trending):
python run.py --x-handle @creator --niche "creator economy" --trend-source news

# 4. Skip trend grounding entirely (evergreen-only drafts):
python run.py --x-handle @me --niche "AI agents" --trend-source evergreen

# 5. Save the bundle to a markdown file:
python run.py --x-handle @JanSol0s --niche "fintech for solopreneurs" --output today.md

# 6. Zero-config first-run with the embedded demo niche:
python run.py --x-handle @JanSol0s --demo ai
```

The output is a daily-deterministic markdown bundle: same handle + same niche + same date = the same 3 drafts tied to the same trend slugs. Tomorrow you get 3 fresh angles automatically. Override the date with `--date 2026-05-04` if you want to regenerate yesterday's set.

---

## What you get

- **3 drafts per run** — escalating depth: Short (≤140 chars), Medium (≤220 chars), Value-add (≤280 chars or thread starter)
- **8 angle archetypes** rotated per run: contrarian, data-led, story-led, list-led, prediction, comparison, how-to, hot-take — no two drafts share an angle
- **`Tied to:` provenance** — every card carries an inline citation (`x_trending — "trend slug"`, `news — "headline slug"`, or `evergreen`) so you can verify before posting
- **Trend-source control** — `x_trending` (default), `news`, `both`, or `evergreen`; if the requested pool has no signal the runner falls back to evergreen and says so
- **Tone control** — `punchy` (default), `thoughtful`, `data-led`, or `warm` — applied as a light prepend that respects each char limit
- **Engagement scoring** — qualitative labels only (low / medium / medium-high / high), spread across the drafts
- **Format suggestions** — value-add slot promotes to `image` (with a Grok Imagine prompt) or `thread starter` (with a 5-tweet plan teaser) when the angle benefits
- **Finance-adjacent guardrail** — drafts touching cashtags / tokens / earnings / P&L / tax auto-tag with `Context only -- not financial advice.`
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --niche "AI agents on X" `
    --trend-source x_trending `
    --num-posts 3 `
    --tone punchy `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--niche` | yes* | — | Niche or topic area in plain language. *Optional when `--demo` is set. |
| `--demo` | no | — | Prefab niche bucket: `ai`, `productivity`, `finance`, `creator`, or `fitness`. |
| `--trend-source` | no | `x_trending` | One of: `x_trending`, `news`, `both`, `evergreen`. |
| `--num-posts` | no | `3` | How many drafts to return (1–5). 4 and 5 cycle back to Short and Medium. |
| `--tone` | no | `punchy` | One of: `punchy`, `thoughtful`, `data-led`, `warm`. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

Niche-bucket detection is automatic (`ai`, `finance`, `productivity`, `creator`, `fitness`, `general`) and drives both topic selection and trend-pool routing — phrase your `--niche` naturally and the runner picks the right offline pool.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` in *AI agents on X* niche during a Grok-4.3-release-week trend cycle.
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` in *Productivity systems for solopreneurs* niche with `--trend-source both` and `thoughtful` tone.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --niche "AI agents on X" --trend-source x_trending --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --niche "Productivity systems for solopreneurs" --trend-source both --tone thoughtful --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled trend pools and templates are intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Open `run.py` and replace the body of `generate_trend_aligned_posts()` with an xAI API call to Grok 4.3.
2. Replace `get_active_trends()` with a real fetcher: X trending via Grok 4.3's X-search tool, news via NewsAPI / GNews, etc. Return the same `[(slug, source_label), ...]` shape.
3. The system prompt at `prompts/system.md` (shipped in P49, ~270 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 11 hard rules, 8-angle distinctness, char limits, qualitative scoring, format-gating, finance-adjacent tagging, and the worked @JanSol0s example.
4. Pass the structured user message: `x_handle`, `niche_keywords`, `trend_source`, `num_posts`, `tone`, plus the live trend pool you fetched in step 2.
5. Keep `render_report()` intact — its output already matches the system prompt's 3-card schema with `Tied to:` lines, so the live model's structured response drops in untouched.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding from real X trends and real news headlines.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate trends, hashtags, headlines, or stats — `evergreen` is always the honest fallback.
2. N distinct angles per run from the 8-angle palette; no two drafts share a hook.
3. Every draft cites its trend source inline so the user can verify before posting.
4. Surface trends as inspiration, never as endorsement.
5. Refuse engagement-bait that violates X policy.
6. Tag finance-adjacent drafts with a context-only note.
7. Strict char limits enforced before emission.
8. Engagement scoring is qualitative only — never percentages.
9. Format suggestions (image / thread / poll) only when they outperform a single tweet.
10. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces #2 (8-angle rotation), #3 (inline `Tied to:` line on every card), #4 (neutral phrasings — no "you should buy X"), #6 (finance-keyword detection), #7 (hard char-count check + `_safe_render` truncation), #8 (qualitative-only labels), #9 (format gating per angle), and #10 (offline). Rules #1 and #5 fully land when you wire to live Grok 4.3 in the step above.

---

## Files in this folder

```
trend-aligned-poster/
├── grok-agent.yaml                 # v2.15 manifest (P49)
├── prompts/
│   └── system.md                   # Grok system prompt, ~270 lines (P49)
├── run.py                          # zero-dependency CLI (P50)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P50)
│   └── niche-productivity.md       # Productivity niche sample (P50)
└── README.md                       # this file (P50)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built to help xAI and Grok win — ecosystem allies, not competitors.
