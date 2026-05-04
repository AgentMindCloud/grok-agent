<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# Thread Builder

> Topic in, thread out — under 60 seconds, ready to ship. 8-angle parent-arc, ≤280-char drafts with live counts, optional Grok Imagine visuals, and cross-template bridges. Local-first. Windows-native. Zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — give it a topic, get back a hook-variant set, full per-tweet drafts, and concrete next steps that bridge into the rest of the suite.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\thread-builder

# 2. Default standard-length how-to thread:
python run.py --x-handle @JanSol0s --topic "shipping a Grok agent in a week"

# 3. Long-form thread with Grok Imagine visuals:
python run.py --x-handle @JanSol0s --topic "5 productivity rituals" --thread-length long --include-visuals

# 4. Different parent angle, different tone:
python run.py --x-handle @JanSol0s --topic "long-context vs RAG" --tone data-led

# 5. Zero-config first run:
python run.py --x-handle @JanSol0s --demo ai

# 6. Save the package to a markdown file:
python run.py --x-handle @JanSol0s --topic "owned-audience math" --output today.md
```

The output is daily-deterministic: same handle + same topic + same date = the same thread package. Tomorrow you get a fresh one. Override the date with `--date 2026-05-04` to regenerate.

---

## What you get

- **Headline** — names the parent angle + topic in one line
- **Hook Variants (2-3)** — alternate openers spanning ≥2 different angles for built-in A/B testing; each labeled with angle + char count
- **Thread Outline** — narrative-arc role mapping (hook → payoff → evidence → CTA) before the prose
- **Full Drafts (per tweet)** — every tweet shows: position, role, character count (≤280, computed before emission), engagement label, and the actual draft text
- **Visual prompts** — when `--include-visuals`, attach a Grok Imagine prompt (cinnabar-and-parchment / Windows-11 vibe / 16:9) to the hook + every 3rd tweet
- **Engagement Tips (4-5)** — concrete imperatives specific to thread mechanics (pin for 48h, first-3-quote replies, scheduling window) + 1 niche-specific tip
- **Cross-Template Bridges (3-5)** — concrete imperatives bridging to sibling templates (CIG, mention-summarizer, analytics-summarizer, reply-drafter, daily-briefing-agent)
- **Composite engagement label** — `low` / `medium` / `medium-high` / `high` for the whole thread
- **Strict 280-char enforcement** — `_safe_render` truncates with last-sentence-drop fallback; nothing ever emits over the limit
- **Policy refusal** — topic with doxx/ratio-bait/harass keywords gets a one-line refusal instead of drafts
- **Finance-adjacent guardrail** — tweets touching cashtags / tokens / earnings / P&L / tax auto-tag with `Context only -- not financial advice.`
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## Length contract

| `--thread-length` | Total tweets | Slot pattern |
|---|---|---|
| `short` | 5 | hook + payoff + 2 body + CTA |
| `standard` | 8 | hook + payoff + 4 body + outcome + CTA |
| `long` | 12 | standard 8 + 4 angle-specific extras |
| `auto` | 5 or 8 | `hot-take`/`contrarian` → 5; everything else → 8 |

The runner picks the parent angle automatically from topic keywords; you can let it pick or pre-bias by phrasing your topic with the angle's signal words ("how to ...", "5 ...", "stop ...", "3 numbers ...", "shipped my first ...", "predictions for ...", "X vs Y", "underrated ...").

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --topic "shipping a Grok agent in a week" `
    --thread-length standard `
    --tone punchy `
    --include-visuals `
    --niche "AI agents on X" `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--topic` | yes* | — | Thread topic in plain language. *Optional when `--demo` is set. |
| `--demo` | no | — | Prefab niche topic: `ai`, `productivity`, `finance`, `creator`, or `fitness`. |
| `--thread-length` | no | `standard` | One of: `short`, `standard`, `long`, `auto`. |
| `--tone` | no | `punchy` | One of: `punchy`, `thoughtful`, `data-led`, `warm`. |
| `--include-visuals` | no | off | Attach Grok Imagine prompt to hook + every 3rd tweet. |
| `--niche` | no | auto | Optional niche hint to bias bucket detection + bridge ideation. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header (handy for piping). |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

---

## How it slots into the creator-template flow

Thread Builder is the creation tool — every other creator template either feeds or extends one of its outputs:

| Section | Bridge to |
|---|---|
| Strongest body tweet | `content-idea-generator` to expand the angle into 5 follow-up ideas |
| Inbound mentions on the thread | `mention-summarizer` for triaging high-LTV asks after CTA goes live |
| 7d post-launch | `analytics-summarizer` to confirm engagement signal vs baseline |
| Loudest contradicting reply | `reply-drafter` to draft 3 voice-matched responses |
| Contrarian/hot-take/prediction angles | `daily-briefing-agent` to queue the take into tomorrow's brief |
| Topic discovery | `research-assistant` to investigate a topic before drafting |
| Trending angle reinforcement | `trend-aligned-poster` to ride a measured uplift with 3 more posts |

So the daily flow is: research → ideas → **build the thread** → ship → triage → measure → loop. All eight templates share the same 8-angle palette, 6-verb action vocabulary, and Apache-headered output — handoff is friction-free.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` 8-tweet how-to thread on *shipping a Grok agent in a week* with `--include-visuals` (visual prompts on tweets 1, 4, 7).
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` 12-tweet long-form list-led thread on *5 productivity rituals for solopreneurs* with `thoughtful` tone.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --topic "shipping a Grok agent in a week" --thread-length standard --tone punchy --include-visuals --niche "AI agents on X" --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --topic "5 productivity rituals for solopreneurs" --thread-length long --tone thoughtful --niche "Productivity systems for solopreneurs" --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled body templates are intentionally tight so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `BODY_TEMPLATES_BY_ANGLE` and `LONG_EXTRAS_BY_ANGLE` with a Grok call that returns the same `[(role, draft), ...]` shape, grounded to the user's actual voice samples and recent thread performance.
2. The system prompt at `prompts/system.md` (shipped in P59, ~390 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 14 hard rules, 8-angle parent-arc requirement, ≤280-char enforcement, ≥2-angle hook-variant rule, and ≥3 cross-template bridges.
3. Replace `generate_thread_outline()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged — including the auto-counted character labels in headings.
4. Pass the structured user message: `x_handle`, `topic`, `thread_length`, `tone`, `include_visuals`, `niche`.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding from the user's voice and the latest niche signals.

---

## Hard rules (from the manifest's `constitution:` block)

1. Never fabricate stats, quotes, or named-source citations inside thread drafts.
2. Always emit the structured 6-section shape (or 7 with `--ab-variants`).
3. Strict ≤280 char limit per tweet — counted before emission, never split.
4. 8-angle parent-arc: the whole thread takes one of the canonical 8 angles.
5. Hook Variants span ≥2 different angles for built-in A/B testing.
6. Visual prompts only when `--include-visuals=true`.
7. Engagement labels are qualitative only (`low`/`medium`/`medium-high`/`high`) — never percentages.
8. Refuse engagement-bait drafts (false outrage, hate, harassment, doxxing, ratio-bait).
9. Tag finance-adjacent tweets with a context-only note.
10. Cross-Template Bridges section cites ≥3 sibling templates by name when bridges are genuine.
11. Topic refusal: vague topics get one clarifying question, no structured output.
12. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces every structural rule plus the ≤280 char limit at the **render** layer (`_safe_render` is the spine — drafts physically cannot exceed the limit). Rules #1, #8, and #11 fully land when you wire to live Grok 4.3.

---

## Files in this folder

```
thread-builder/
├── grok-agent.yaml                 # v2.15 manifest (P59)
├── prompts/
│   └── system.md                   # Grok system prompt, ~390 lines (P59)
├── run.py                          # zero-dependency CLI (P60)
├── examples/
│   ├── niche-ai-agents.md          # AI niche, 8-tweet how-to with visuals (P60)
│   └── niche-productivity.md       # Productivity niche, 12-tweet list-led, thoughtful tone (P60)
└── README.md                       # this file (P60)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> Built to help xAI and Grok win — ecosystem allies, not competitors.
