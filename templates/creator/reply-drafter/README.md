<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community. ❤️ -->

# Reply Drafter

> 3 voice-matched X reply drafts in 5 seconds. Niche-aware, tone-aware, Windows-native, zero-config.

**Built for xAI, X, Grok and the ecosystem community. ❤️** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — paste a mention, get back three replies you'd actually post.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\reply-drafter

# 2. Draft 3 replies for any X post:
python run.py --x-handle @JanSol0s --original-post "Great thread on Grok agents!"

# 3. Use the --mention alias if that reads better:
python run.py --x-handle @creator --mention "Have you tried prompt caching?" --tone warm

# 4. Save the bundle to a markdown file you can paste anywhere:
python run.py --x-handle @JanSol0s --original-post "Crypto markets feel weird this week" --output today.md
```

The output is a daily-deterministic markdown bundle: same handle + same post + same date = the same 3 drafts. Tomorrow you get 3 fresh angles automatically. Override the date with `--date 2026-05-04` to regenerate yesterday's set.

---

## What you get

- **3 distinct drafts per run** — escalating depth: Short (≤140 chars), Medium (≤220 chars), Value-add (≤280 chars)
- **8 angle archetypes** rotated per run: agree-and-amplify, gentle-disagree, ask-a-sharp-question, add-data, share-a-tip, comparison, story-pivot, mic-drop — no two drafts share an angle in a single run
- **Voice matching** — niche bucket detection (`ai`, `finance`, `productivity`, `creator`, `fitness`, `general`) picks the right counter-concept for `comparison` and `gentle-disagree` angles
- **Tone control** — `punchy` (default), `thoughtful`, `data-led`, or `warm` — applied as a light prepend that respects each char limit
- **Engagement scoring** — qualitative labels only (low / medium / medium-high / high), spread across the 3 drafts so every set has variety
- **Format suggestions** — value-add slot flips to `image` with a Grok Imagine prompt when the original post mentions visuals (chart, dashboard, screenshot, and similar)
- **Trap detection** — the runner refuses to draft when the original post matches DM-bait, RT-to-win, scam, or doxx-bait patterns (Constitution rule #7)
- **Finance-adjacent guardrail** — drafts touching cashtags / tokens / earnings / P&L / tax auto-tag with `Context only -- not financial advice.`
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --original-post "Just shipped a new agent" `
    --tone warm `
    --niche "AI tooling" `
    --num-drafts 3 `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--original-post` | one of | — | Full text of the X post you're replying to (in quotes). |
| `--mention` | one of | — | Alias for `--original-post`. |
| `--tone` | no | `punchy` | One of: `punchy`, `thoughtful`, `data-led`, `warm`. |
| `--niche` | no | auto-detect | Optional niche hint (`AI tooling`, `creator economy`, or similar). |
| `--num-drafts` | no | `3` | How many drafts to return (1–3). |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

Niche detection is automatic — phrase your `--original-post` (or `--niche`) naturally and the runner will route to the right counter-concept pool.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` replying to *"Just shipped my first AI agent on X. Not sure what to build next."*
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` replying to *"Tried single-tab focus this week. Workflow feels weirdly different."*, `thoughtful` tone.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --original-post "Just shipped my first AI agent on X. Not sure what to build next. Suggestions?" --niche "AI tooling" --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --original-post "Tried single-tab focus this week. Workflow feels weirdly different." --tone thoughtful --niche "Productivity systems for solopreneurs" --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled draft library is intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Open `run.py` and replace the body of `generate_reply_drafts()` with an xAI API call to Grok 4.3.
2. The system prompt at `prompts/system.md` (shipped in P45, ~150 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 10 hard rules, 8-angle distinctness, char limits, qualitative engagement scoring, finance-adjacent tagging, and trap detection.
3. Pass the structured user message: `x_handle`, `original_post`, `tone`, `niche`, `num_drafts`.
4. Keep the `render_report()` shape intact — it already matches the system prompt's draft-card schema, so the live model's output drops in untouched.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding, real voice matching from the user's prior posts.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never impersonate the original poster, another creator, or a public figure.
2. Never fabricate stats, quotes, or claims.
3. Always produce 3 distinct drafts (short / medium / value-add) within strict char limits.
4. Refuse policy-violating drafts (hate, harassment, doxxing, pile-ons, ratio-bait).
5. Tag finance-adjacent drafts with a context-only note.
6. Surface engagement scores as qualitative labels only — never percentages.
7. Refuse to draft for bait, grief-bait, or scam posts.

The v1 demo runner enforces #3 (hard char-count check + 8-angle rotation), #5 (finance-keyword detection), #6 (label-only engagement), and #7 (bait-keyword refusal). Rules #1, #2, and #4 fully land when you wire to live Grok 4.3 in the step above.

---

## Files in this folder

```
reply-drafter/
├── grok-agent.yaml                 # v2.15 manifest (P45)
├── prompts/
│   └── system.md                   # Grok system prompt, 150+ lines (P45)
├── run.py                          # zero-dependency CLI (P46)
├── examples/
│   ├── niche-ai-agents.md          # AI niche sample (P46)
│   └── niche-productivity.md       # Productivity niche sample (P46)
└── README.md                       # this file (P46)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built for xAI, X, Grok and the ecosystem community — ecosystem allies, not competitors.
