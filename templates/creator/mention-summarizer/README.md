<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# Mention Summarizer

> Triage your X mentions in 30 seconds. Structured 5-section summary, niche-aware, Windows-native, zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — paste a batch of mentions, get a clean action plan back.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\mention-summarizer

# 2. Try it on the embedded demo batch (no input needed):
python run.py --x-handle @JanSol0s --demo ai

# 3. Run on real mentions piped in as JSON:
python run.py --x-handle @JanSol0s --mentions '[{"author":"@a","text":"Great work on Grok agents"},{"author":"@b","text":"Bug: prompt caching crashed on Windows 11"}]'

# 4. Run on a JSON file you exported from your X archive or an X-search tool:
python run.py --x-handle @JanSol0s --mentions-file mentions.json --suggest-replies

# 5. Save the summary to a markdown file:
python run.py --x-handle @JanSol0s --demo productivity --output today.md
```

The output is a daily-deterministic markdown bundle: same handle + same mention batch + same date = the same summary. Re-run tomorrow on a fresh batch and the priority list updates automatically. Use `--date 2026-05-04` to regenerate yesterday's view.

---

## What you get

- **Headline** — one-line takeaway summarizing the batch's mood and action surface
- **3–5 Themes** — keyword-clustered topics with count, sentiment, and the most theme-relevant representative quote
- **Sentiment table** — qualitative-only labels (`positive`, `neutral`, `negative`, `mixed`) — never percentages
- **Top-3 Priority mentions** — automatically deduped by author, scored qualitatively (`high` / `medium-high` / `medium` / `low`), with a one-line reason and one of the six fixed actions: `reply now` | `reply within 24h` | `mute` | `block` | `ignore` | `flag for follow-up`
- **3–5 Action Items** — concrete imperative next-steps (reply this, block that, ship a thread on…)
- **Optional Reply Suggestions** — pass `--suggest-replies` to surface 1–3 high-leverage drafts (each ≤140 chars)
- **Refusals** — the runner refuses to summarize if the batch is >70% spam, or if `--date-range` is used without a local cache, with a one-line reason
- **Finance-adjacent guardrail** — priority cards touching cashtags / tokens / earnings / P&L / tax auto-tag with `Context only -- not financial advice.`
- **Privacy** — representative quotes auto-redact phone numbers and email addresses before display
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --demo ai `
    --niche "AI tooling" `
    --max-mentions 50 `
    --suggest-replies `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--mentions` | one of | — | Inline JSON list of mention objects: `[{"author":"@a","text":"..."}, ...]`. |
| `--mentions-file` | one of | — | Path to a JSON file with the same shape. |
| `--demo` | one of | — | Use the embedded demo batch — `ai`, `productivity`, or `finance`. |
| `--date-range` | one of | — | ISO range like `2026-05-01..2026-05-04` (local-cache lookup; v2 feature, v1 returns a clear refusal). |
| `--max-mentions` | no | `50` | Cap on mentions to ingest per run (1–200). |
| `--niche` | no | auto-detect | Optional niche hint (e.g. `AI tooling`). |
| `--suggest-replies` | no | off | Surface 1–3 high-leverage reply drafts. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

The four input sources (`--mentions`, `--mentions-file`, `--demo`, `--date-range`) are mutually exclusive. Niche detection is automatic — phrase your `--niche` (or let the runner infer it from mention text) and the right theme buckets activate.

### Mention object shape

```json
{
  "author": "@username",
  "text": "the mention text",
  "timestamp": "2026-05-04T10:00:00Z"
}
```

`timestamp` is optional. If `author` is missing, the runner auto-numbers as `@user_N`.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` summarizing 12 AI-niche mentions (Grok 4.3, RAG, evals, prompt caching).
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` summarizing 12 productivity-niche mentions (focus, calendar, rituals, automation).

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --demo ai --niche "AI tooling" --suggest-replies --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --demo productivity --niche "Productivity systems for solopreneurs" --suggest-replies --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled summary pipeline is intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Open `run.py` and replace the body of `generate_mention_summary()` with an xAI API call to Grok 4.3.
2. The system prompt at `prompts/system.md` (shipped in P47, ~250 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 10 hard rules, structured 5-section schema, qualitative scoring vocabulary, six-verb action list, and finance-adjacent tagging.
3. Pass the structured user message: `x_handle`, `mentions`, `max_mentions`, `niche`, `suggest_replies`.
4. Keep `render_report()` intact — its output already matches the system prompt's schema, so the live model's structured response drops in untouched.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding, real semantic theme clustering instead of keyword groups.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate mention text, author handles, sentiment, or engagement numbers.
2. Always emit the structured 5-section shape (or 6 with `--suggest-replies`).
3. Sentiment and priority are qualitative labels only — never percentages.
4. Every priority tag carries a one-line reason grounded in the source mention.
5. Refuse pure-spam / scam / coordinated-harassment batches with a one-line reason.
6. Tag finance-adjacent priority cards with a context-only note.
7. Privacy: redact PII (phone, email) before quoting; quote selectively.
8. Dedup people: same author across multiple mentions appears once with a cumulative reason.

The v1 demo runner enforces every rule above. Rule #1 lands fully when you wire to live Grok 4.3 (the v1 keyword pipeline never invents text — it only clusters real input).

---

## Files in this folder

```
mention-summarizer/
├── grok-agent.yaml                 # v2.15 manifest (P47)
├── prompts/
│   └── system.md                   # Grok system prompt, ~250 lines (P47)
├── run.py                          # zero-dependency CLI (P48)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P48)
│   └── niche-productivity.md       # Productivity niche sample (P48)
└── README.md                       # this file (P48)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built to help xAI and Grok win — ecosystem allies, not competitors.
