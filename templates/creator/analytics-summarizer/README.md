<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# Analytics Summarizer

> Your X numbers, briefed in 60 seconds. 4 canonical metrics, 3-5 trends with strict 3+3 vocabulary, top-3 winners, cross-template recommendations. Local-first. Windows-native. Zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — paste your X analytics, get back a structured summary that bridges directly into the rest of the suite.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\analytics-summarizer

# 2. Try the embedded demo bundle (no input needed):
python run.py --x-handle @JanSol0s --demo ai

# 3. Run on real metrics piped in as JSON:
python run.py --x-handle @JanSol0s --metrics '[{"metric":"impressions","current":412000,"prev":348000}]'

# 4. Run on a JSON file you exported from X analytics:
python run.py --x-handle @JanSol0s --metrics-file metrics.json --compare-to previous_period

# 5. Pass metric names + a date range (uses the niche's default bundle):
python run.py --x-handle @JanSol0s --metrics impressions,engagement,reach,follower_delta --date-range 2026-04-05:2026-05-05 --demo ai

# 6. Compare against a niche benchmark instead of previous period (adds the 7th section):
python run.py --x-handle @JanSol0s --demo productivity --compare-to benchmark

# 7. Save the summary to a markdown file:
python run.py --x-handle @JanSol0s --demo ai --output today.md
```

The output is daily-deterministic: same handle + same metric input + same date = the same summary. Re-run tomorrow on a fresh export and the trend deltas update automatically. Use `--date 2026-05-04` to regenerate a past view.

---

## What you get

- **Headline** — one-line takeaway: dominant metric movement + first concrete next move
- **Key Metrics table** — exactly **4 canonical rows** (`impressions`, `engagement`, `reach`, `follower_delta`) showing current value, comparison value, delta, and direction; missing rows render as placeholders so the table shape is stable
- **Trends (3–5)** — each tagged with strict labels: direction (`up` / `down` / `stable`) + magnitude (`small` / `moderate` / `large`) + verbatim numerical delta from input
- **Top Performing Content (up to 3)** — each post carries format, headline metric, and a one-line "why this won" grounded in its own metric mix
- **Recommendations (3–5)** — concrete imperatives that bridge directly into the other 6 creator templates (CIG, reply-drafter, mention-summarizer, trend-aligned-poster, daily-briefing-agent, research-assistant) when the bridge is genuine
- **Confidence** — qualitative-only label (`low` / `medium` / `medium-high` / `high`) with a one-sentence reason
- **Benchmark Comparison** *(optional)* — when `--compare-to benchmark`, adds a 7th section with `well below` / `below` / `at` / `above` / `well above` gap labels per metric, plus a benchmark source citation
- **Garbage-batch refusal** — if >70% of input rows are empty/null/zero, the runner refuses with a one-line reason instead of faking a summary
- **Finance-adjacent guardrail** — recommendations touching monetization / payouts / cashtags auto-tag with `Context only -- not financial advice.`
- **Privacy** — aggregate-only; never exposes individual follower IDs or DM-content
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --demo ai `
    --metric-focus engagement `
    --time-range 30d `
    --compare-to previous_period `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--metrics` | one of | — | Inline JSON list of metric records OR comma-separated metric names. |
| `--metrics-file` | one of | — | Path to a JSON file with `{metrics, top_posts}` or just a metrics list. |
| `--date-range` | one of | — | ISO range like `2026-04-05:2026-05-05` (v1: falls back to bucket bundle). |
| `--demo` | one of | — | Prefab niche bundle: `ai`, `productivity`, `finance`, `creator`, or `fitness`. |
| `--metric-focus` | no | `all` | One of: `impressions`, `engagement`, `reach`, `all`. |
| `--time-range` | no | `30d` | One of: `7d`, `30d`, `90d`. |
| `--compare-to` | no | `previous_period` | One of: `previous_period`, `benchmark`, `none`. |
| `--niche` | no | auto | Optional niche hint to bias bucket detection. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

The first three input flags (`--metrics`, `--metrics-file`, `--date-range`) are mutually-favored — pass whichever fits your workflow. `--demo` adds prefab values when `--metrics` is given as comma-separated names but no values.

### Mention/metric-record shape

```json
{
  "metric": "engagement",
  "current": 31200,
  "prev": 24600
}
```

`prev` is optional when `--compare-to=none`. The `--metrics-file` form may also include `"top_posts": [{...}]` so the Top Performing Content section is grounded.

---

## How it slots into the creator-template flow

Analytics Summarizer is the measurement tool — every other creator template either feeds or extends one of its outputs:

| Section | Bridge to |
|---|---|
| Top Performing Content | `content-idea-generator` to expand the winning angle into 5 more ideas |
| Trends (with follower velocity up) | `mention-summarizer` to triage the new audience surfaced by the spike |
| Trends (with up + moderate/large magnitude) | `trend-aligned-poster` to ship 3 posts on the measured uplift |
| Headline + dominant signal | `daily-briefing-agent` to thread the analytics signal into tomorrow's brief |
| Sudden anomaly in a metric | `research-assistant` to investigate with multi-source synthesis |
| Replies to high-engagement post | `reply-drafter` to draft 3 voice-matched replies for the viral mention thread |

So the daily flow is: brief → research → ideas → drafts → triage → measure (this template) → loop. All seven templates share the same 8-angle palette, 6-verb action vocabulary, 3+3 trend taxonomy, and Apache-headered output.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` 30-day analytics for *AI agents on X* with `--compare-to previous_period`.
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` 30-day analytics for *Productivity systems for solopreneurs* with `--compare-to benchmark` (showcases the 7th Benchmark Comparison section).

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --demo ai --niche "AI agents on X" --compare-to previous_period --time-range 30d --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --demo productivity --niche "Productivity systems for solopreneurs" --compare-to benchmark --time-range 30d --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled metric pools are intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `DEMO_METRIC_BUNDLES` with a real fetcher: pull metrics directly from X analytics, top posts from the user's recent timeline, benchmarks from a niche cohort cache.
2. The system prompt at `prompts/system.md` (shipped in P55, ~280 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 12 hard rules, structured 6-section schema, 4 canonical metric rows, 3+3 trend vocabulary, and cross-template bridge candidates.
3. Replace `generate_analytics_summary()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged.
4. Pass the structured user message: `x_handle`, `metrics`, `top_posts`, `metric_focus`, `time_range`, `compare_to`, `niche`.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding from real X analytics.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate metric values, percentages, post titles, or follower counts.
2. Always emit the structured 6-section shape (or 7 with `--compare-to benchmark`).
3. Trend direction is one of `up` / `down` / `stable`; magnitude is one of `small` / `moderate` / `large`.
4. Top Performing Content is exactly 3 when input allows; each entry carries an inline "why this won".
5. Recommendations bridge to sibling templates only when the bridge is genuine.
6. Refuse garbage batches (>70% empty/zero rows) with a one-line reason.
7. Tag finance-adjacent recommendations with a context-only note.
8. Privacy: aggregate-only; never expose individual follower IDs.
9. Confidence is qualitative only — never percentages.
10. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces every structural rule (#2–#7, #9, #10). Rules #1 and #8 fully land when you wire to live Grok 4.3.

---

## Files in this folder

```
analytics-summarizer/
├── grok-agent.yaml                 # v2.15 manifest (P55)
├── prompts/
│   └── system.md                   # Grok system prompt, ~280 lines (P55)
├── run.py                          # zero-dependency CLI (P56)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P56)
│   └── niche-productivity.md       # Productivity niche sample, with benchmark (P56)
└── README.md                       # this file (P56)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built to help xAI and Grok win — ecosystem allies, not competitors.
