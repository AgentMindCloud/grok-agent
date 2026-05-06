<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community. ❤️ -->

# Quote Tweet Suggestor

> 2-3 quote tweet variants in 5 seconds, distinct angles, voice-matched, with optional Grok Imagine visual. Local-first. Windows-native. Zero-config.

**Built for xAI, X, Grok and the ecosystem community. ❤️** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — paste any X post, get back 2-3 angle-spanning quote variants and concrete next steps that bridge into the rest of the suite.

> 🔒 **Privacy note:** the Original Post Read section paraphrases the source; the runner never copies the original post verbatim.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\quote-tweet-suggestor

# 2. Auto-mode: 3 variants picked by detected intent:
python run.py --x-handle @JanSol0s --original-post "tracked my first 30 days shipping AI agents"

# 3. Force a specific angle (quote-tweet-specific 5-angle palette):
python run.py --x-handle @JanSol0s --original-post "long-context wins" --quote-angle contrarian

# 4. Add a Grok Imagine visual (7-section output):
python run.py --x-handle @JanSol0s --original-post "5 productivity rituals" --include-visual

# 5. Zero-config first run with a prefab post:
python run.py --x-handle @JanSol0s --demo ai

# 6. Save the package to a markdown file:
python run.py --x-handle @JanSol0s --demo productivity --output today.md
```

The output is daily-deterministic: same handle + same original post + same date = the same variants. Re-run tomorrow on the same post and the variant pool refreshes automatically.

---

## What you get

- **Headline** — names the variant set's angle mix + the original post's detected intent + composite engagement
- **Original Post Read** — paraphrased one-liner + intent label (`claim` / `question` / `story` / `celebration` / `data` / `meta`); the source post is never quoted verbatim
- **Quote Tweet Variants (2-3)** — each card has angle, char count (≤280), engagement label, and the actual quote draft
- **Angle Explanation** — one paragraph naming which signal in the original post drove each angle pick
- **Cross-Template Bridges (3-5)** — concrete imperatives bridging to `thread-builder` (full thread expansion), `mention-summarizer` (post-quote inbound triage), `analytics-summarizer` (24-48h engagement check), `content-idea-generator` (spin angle into more posts), `research-assistant` (verify quoted claims), `reply-drafter` (non-quote responses to the same post)
- **Confidence** — qualitative-only label (`low` / `medium` / `medium-high` / `high`) + reason
- **Suggested Visual** *(optional)* — when `--include-visual`, adds a 7th section with a Grok Imagine prompt for the strongest variant
- **Strict ≤280-char enforcement** — `_safe_render` truncates with last-sentence-drop fallback; nothing ever emits over the limit
- **Policy refusal** — original posts with doxx/ratio-bait/harass keywords get a one-line refusal instead of variants
- **Privacy guard** — the Original Post Read paraphrases via topic-extraction; the source post never appears verbatim in the output, including in saved files
- **Finance-adjacent guardrail** — variants touching cashtags/tokens/earnings auto-tag with `Context only -- not financial advice.`
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## The 5-angle quote-tweet palette

Quote tweets respond to existing posts, so the palette is response-shaped (distinct from the 8-angle origination palette used by `content-idea-generator` and `thread-builder`):

| Angle | When to use |
|---|---|
| **support** | Agree-and-amplify; nodding + adding a sharp emphasis. Best on posts you genuinely agree with. |
| **contrarian** | Gentle pushback on one specific axis without being combative. Highest-engagement angle when calibrated honestly. |
| **add_value** | Bring a concrete tip / data point / framework that extends the original. Lands when the original left a gap. |
| **question** | Ask a sharp follow-up that opens a thread or surfaces a missing axis. Best when the original is a claim. |
| **story-pivot** | Turn the quoted post into a one-line lived experience that resonates. Use sparingly. |

The runner's `auto` mode picks angles by detected intent: celebration → support+add_value+question; claim → contrarian+add_value+question; question → add_value+question+story-pivot; story → support+add_value+story-pivot; data → add_value+question+support; meta → support+contrarian+add_value.

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --original-post "long-context wins" `
    --quote-angle auto `
    --num-variants 3 `
    --tone punchy `
    --include-visual `
    --niche "AI agents on X" `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--original-post` | yes* | — | Full text of the X post you're quoting. *Optional when `--demo` is set. |
| `--demo` | no | — | Prefab niche post: `ai`, `productivity`, `finance`, `creator`, or `fitness`. |
| `--quote-angle` | no | `auto` | One of: `support`, `contrarian`, `add_value`, `question`, `story-pivot`, `auto`. |
| `--num-variants` | no | `3` | Number of variants (2 or 3). |
| `--tone` | no | `punchy` | One of: `punchy`, `thoughtful`, `data-led`, `warm`. |
| `--include-visual` | no | off | Attach a Grok Imagine prompt to the strongest variant. |
| `--niche` | no | auto | Optional niche hint to bias bucket detection + bridge ideation. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

---

## How it slots into the creator-template flow

Quote Tweet Suggestor is the response tool — every other creator template either feeds or extends one of its outputs:

| Section | Bridge to |
|---|---|
| Strongest variant (contrarian or add_value) | `thread-builder` for a full counter-thread expansion |
| Inbound replies post-quote | `mention-summarizer` for 24h triage of advocate signal |
| 48h post-quote | `analytics-summarizer` to confirm engagement vs baseline |
| Quoted claim or data point | `research-assistant` to verify before posting the contrarian variant |
| Strongest angle | `content-idea-generator` to spin into 5 more post ideas |
| Non-quote response option | `reply-drafter` for replies in the same thread |
| Trend-tied posts | `trend-aligned-poster` if the quote ties to a current trend |

So the daily flow is: brief → research → ideas → build threads → ship → triage mentions → triage DMs → **drop quote tweets** (this template) → measure → loop. All eleven templates share the same Apache-headered output and unified taxonomy.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` quote-tweet variants for a celebration-shaped post about *shipping AI agents*; 3 variants (support/add_value/question), `--include-visual` on.
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` quote-tweet variants for a claim-shaped post about *single-tab focus*; 3 variants picked by `auto` mode, `thoughtful` tone.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --original-post "Just tracked my first 30 days shipping AI agents. The biggest unlock was writing 5 evals on day one, not day thirty." --quote-angle auto --num-variants 3 --tone punchy --include-visual --niche "AI agents on X" --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --original-post "Single-tab focus is the most underrated productivity move in 2026. The first week feels weird, by week three it's the only way to work." --quote-angle auto --num-variants 3 --tone thoughtful --niche "Productivity systems for solopreneurs" --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled quote templates are intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `QUOTE_TEMPLATES_BY_ANGLE` with a Grok call that returns the same `[{angle, char_count, engagement, draft}]` shape, grounded to the user's actual voice samples and the original post's specifics.
2. The system prompt at `prompts/system.md` (shipped in P63, ~330 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 14 hard rules including the privacy-paranoid Original-Post-Read paraphrase rule, ≤280 char limit, ≥2-angle distinctness, and ≥3 cross-template bridges.
3. Replace `generate_quote_tweet_variants()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged — including the auto-counted character labels.
4. Pass the structured user message: `x_handle`, `original_post`, `quote_angle`, `num_variants`, `tone`, `include_visual`, `niche`. Make sure the system prompt's privacy rule (paraphrase, never copy) survives — Grok 4.3 should generate the paraphrase + variants in one pass, not echo the original post.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding from the user's voice and the post's specifics.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never impersonate the original poster, another creator, or a public figure.
2. Never fabricate stats / quotes / claims about people, products, or events.
3. Always emit the structured 6-section shape (or 7 with `--include-visual`).
4. Strict ≤280 char per variant — counted before emission.
5. Variants span ≥2 different angles from the 5-angle palette.
6. Refuse engagement-bait variants (false outrage, hate, harassment, doxxing, ratio-bait).
7. Privacy: don't expand initials into full names; don't expose private info from the original poster.
8. Tag finance-adjacent variants with a context-only note.
9. Engagement labels are qualitative only (low / medium / medium-high / high) — never percentages.
10. Visual prompts only when `--include-visual=true`.
11. Cross-Template Bridges section cites ≥3 sibling templates by name when bridges are genuine.
12. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces every structural rule plus the ≤280 char limit at the **render** layer (`_safe_render` is the spine — variants physically cannot exceed the limit). Rules #2 and #6 fully land when you wire to live Grok 4.3.

---

## Files in this folder

```
quote-tweet-suggestor/
├── grok-agent.yaml                 # v2.15 manifest (P63)
├── prompts/
│   └── system.md                   # Grok system prompt, ~330 lines (P63)
├── run.py                          # zero-dependency CLI (P64)
├── examples/
│   ├── niche-ai-agents.md          # AI niche, celebration-intent post (P64)
│   └── niche-productivity.md       # Productivity niche, claim-intent post (P64)
└── README.md                       # this file (P64)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built for xAI, X, Grok and the ecosystem community — ecosystem allies, not competitors.
