<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community. ❤️ -->

# Research Assistant

> Citations-first creator research, ready in 60 seconds. Multi-source synthesis with explicit contradictions and cross-template bridges. Local-first. Windows-native. Zero-config.

**Built for xAI, X, Grok and the ecosystem community. ❤️** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — ask a question, get a balanced summary with sources, contradictions, and concrete next steps that hand off cleanly into the rest of the suite.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\research-assistant

# 2. Run a standard-depth research pass on any question:
python run.py --x-handle @JanSol0s --query "long-context vs RAG"

# 3. Go deep (8 findings + cross-source synthesis paragraph):
python run.py --x-handle @JanSol0s --query "single-tab focus vs Pomodoro" --depth deep

# 4. Filter by source category (academic only):
python run.py --x-handle @JanSol0s --query "tax automation" --sources academic

# 5. Save to a markdown file with a Visual Aid hero card:
python run.py --x-handle @JanSol0s --query "long-context vs RAG" --suggest-visual --output today.md

# 6. Zero-config first run:
python run.py --x-handle @JanSol0s --demo ai
```

The output is a daily-deterministic markdown bundle: same handle + same query + same date = the same summary. Tomorrow on the same query you get a refreshed pass. Override the date with `--date 2026-05-04` to regenerate.

---

## What you get

- **Question** — a one-line restatement of your query, in your voice
- **Key Findings (3–8)** — each ends with an inline `[src N]` tag; bridging-only findings get `[analyst inference]` honestly
- **Contradictions Flagged** — explicit "side A says X, side B says Y" entries (or "no contradictions surfaced") so you can see the disagreement instead of having one side picked silently for you
- **Sources Cited table** — every cited source, with `weak` / `moderate` / `strong` strength labels and one of six type labels (`x`, `news`, `academic`, `gov`, `evergreen`, `analyst`)
- **Suggested Next Steps (3–5)** — concrete imperatives that bridge directly into the other 5 creator templates (CIG, reply-drafter, daily-briefing-agent, mention-summarizer, trend-aligned-poster)
- **Confidence** — qualitative-only label (`low` / `medium` / `medium-high` / `high`) plus a one-line reason; deep depth adds a cross-source synthesis paragraph
- **Visual Aid** *(optional)* — a Grok Imagine prompt suitable as a hero card when you pass `--suggest-visual`
- **Finance-adjacent guardrail** — findings touching cashtags / tokens / earnings / P&L / tax auto-tag with `Context only -- not financial advice.`
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## Depth contract

| Depth | Findings | Contradictions | Next steps | Confidence add-on |
|---|---|---|---|---|
| `quick` | 3 | omitted unless surfaced | 3 | one-line reason |
| `standard` | 5 | always emitted (or "no contradictions surfaced") | 4 | one-line reason |
| `deep` | 8 (5 sources + cross-cite + contradiction-frame + analyst inference) | always emitted with detail | 5 | + cross-source synthesis paragraph |

If your `--sources` filter narrows the available pool below what `deep` requires, the runner auto-downgrades to `standard` and notes it in Confidence — never silently faking depth it doesn't have.

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --query "owned-audience math" `
    --depth standard `
    --sources all `
    --niche "creator economy" `
    --suggest-visual `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--query` | yes* | — | The research question or topic. *Optional when `--demo` is set. |
| `--demo` | no | — | Prefab niche query — `ai`, `productivity`, `finance`, `creator`, or `fitness`. |
| `--depth` | no | `standard` | One of: `quick`, `standard`, `deep`. |
| `--sources` | no | `all` | Source-category filter — `all`, `x`, `news`, `academic`, `gov`. |
| `--niche` | no | auto | Optional niche hint to bias bucket detection. |
| `--suggest-visual` | no | off | Append a Visual Aid section. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

Niche-bucket detection is automatic — phrase your query naturally and the runner picks the right offline corpus.

---

## How it slots into the creator-template flow

The Research Assistant is the depth tool — every other creator template extends or feeds one of its outputs:

| Section | Bridge to |
|---|---|
| Suggested Next Step #1 | `content-idea-generator` to expand the strongest finding into a thread |
| Suggested Next Step #2 | `mention-summarizer` to triage the X-source mentions in this batch |
| Suggested Next Step #3 | `reply-drafter` to draft 3 voice-matched replies for the loudest contradicting voice |
| Suggested Next Step #4 | `daily-briefing-agent` to queue this query for tomorrow's brief |
| Suggested Next Step #5 *(deep only)* | `trend-aligned-poster` to ship 3 trend-aligned posts on the strongest finding |

So the daily flow is: brief → research → ideas → drafts → triage. All six templates share the same 8-angle palette, 6-verb action vocabulary, and Apache-headered output, so handoff is friction-free.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` researching *long-context vs RAG* (standard depth, all sources, with `--suggest-visual`).
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` researching *single-tab focus vs Pomodoro* (deep depth, all sources).

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --query "long-context vs RAG" --depth standard --niche "AI agents on X" --suggest-visual --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --query "single-tab focus vs Pomodoro" --depth deep --niche "Productivity systems for solopreneurs" --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled topic corpora are intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `RESEARCH_CORPUS_BY_BUCKET` with a real fetcher: X via Grok 4.3's X-search tool, news via NewsAPI / GNews, academic via Semantic Scholar / arXiv, gov via data.gov / official APIs.
2. The system prompt at `prompts/system.md` (shipped in P53, ~340 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 12 hard rules, depth contract, citation discipline, source-strength taxonomy, and cross-template bridges.
3. Replace `generate_research_summary()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged.
4. Pass the structured user message: `x_handle`, `query`, `depth`, `sources`, `niche`, `include_visual` plus the live source bundle from step 1.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding from real X / news / academic / gov sources.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate sources, citations, headlines, paper titles, dates, authors, or quotes.
2. Always emit the structured 6-section shape (or 7 with `--suggest-visual`).
3. Every Key Finding carries an inline `[src N]` tag; bridging-only findings get `[analyst inference]`.
4. Surface contradictions explicitly — never silently pick a side.
5. Confidence and source-strength are qualitative labels only — never percentages.
6. Suggested Next Steps reference the rest of the creator-template suite where useful.
7. Tag finance-adjacent findings with a context-only note.
8. Refuse policy-violating queries with a one-line reason.
9. Privacy: redact PII when surfacing X material; quote selectively.
10. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces every structural rule (#2–#7, #10). Rules #1, #8, and #9 fully land when you wire to live Grok 4.3.

---

## Files in this folder

```
research-assistant/
├── grok-agent.yaml                 # v2.15 manifest (P53)
├── prompts/
│   └── system.md                   # Grok system prompt, ~340 lines (P53)
├── run.py                          # zero-dependency CLI (P54)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P54)
│   └── niche-productivity.md       # Productivity niche sample (P54)
└── README.md                       # this file (P54)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built for xAI, X, Grok and the ecosystem community — ecosystem allies, not competitors.
