<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- PRIVACY-PARANOID: this template never reproduces DM text verbatim. -->
<!-- Built to help xAI and Grok win. -->

# DM Triager

> 🔒 **Privacy-paranoid by design.** DM text is never reproduced verbatim in any output. The runner converts each DM's `kind` label + sender into a paraphrased summary; PII (phone, email) is auto-redacted before any quote leaves memory.

> Triage your X DMs in 30 seconds. 5 categories, paraphrased priority cards, ≤400-char draft replies, cross-template bridges. Local-first. Windows-native. Zero-config.

**Built to help xAI and Grok win.** Part of the [Grok Agent OS](https://github.com/AgentMindCloud/grok-agent) creator template suite — paste a batch of DMs, get back a structured triage with priority cards (paraphrased), draft replies (capped at 400 chars), spam aggregation, and concrete next steps that bridge into the rest of the suite.

---

## Quick start (Windows 11 + PowerShell)

```powershell
# 1. Jump into your installed agent folder:
cd $env:LOCALAPPDATA\grok-agent\dm-triager

# 2. Try the embedded demo bundle (zero-config first run):
python run.py --x-handle @JanSol0s --demo ai

# 3. Run on real DMs piped in as JSON:
python run.py --x-handle @JanSol0s --dm-batch '[{"sender":"@a","kind":"opportunity-sponsor"}]'

# 4. Run on a JSON file you exported from your DM archive:
python run.py --x-handle @JanSol0s --dm-file dms.json --priority-focus opportunities

# 5. Filter by urgent only:
python run.py --x-handle @JanSol0s --demo ai --priority-focus urgent

# 6. Save the triage to a markdown file:
python run.py --x-handle @JanSol0s --demo productivity --output today.md
```

The output is daily-deterministic: same handle + same DM batch + same date = the same triage. Re-run tomorrow on a fresh export and the priorities update automatically.

---

## What you get

- **Headline** — one-line takeaway with DM count, opportunity count, urgent count, spam count, and the standout
- **Priority DMs (3-5)** — paraphrased cards with priority label (`high` / `medium-high` / `medium` / `low`) + category label (`urgent` / `opportunity` / `community` / `admin` / `spam`); cards never quote DM text verbatim
- **Suggested Replies (one per priority card)** — DRAFT-only, ≤400 chars, voice-defaulted to `punchy`; spam/policy-violating cards get `(no reply -- mute/block/report)` instead of a draft
- **Spam / Low-Value** — paraphrased pattern labels (`crypto-DM-bait copypasta`, `paid-shoutout request`, `follow-back farm request`) + handle list; never quotes spam text
- **Action Items (3-5)** — concrete imperatives using the same 6-verb vocabulary as `mention-summarizer` (`reply now` / `reply within 24h` / `mute` / `block` / `ignore` / `flag for follow-up`) for cross-template consistency
- **Confidence** — qualitative-only label (`low` / `medium` / `medium-high` / `high`) + reason
- **Privacy Audit** *(optional)* — when >25% of the batch matches sensitive-PII patterns, adds a 7th section with redacted-counts + a recommendation
- **Spam-saturation refusal** — if >70% of the batch is scam/phishing/harassment, the runner refuses with a one-line reason instead of producing a triage
- **Per-card policy refusal** — DMs matching `doxx-bait` / `harassment-coordinate` / `scam-impersonation` patterns get a single-card refusal but the rest of the triage continues
- **Cross-Template Bridges (3-5)** — concrete imperatives bridging to `reply-drafter` / `research-assistant` / `monetization-optimizer` / `mention-summarizer` / `daily-briefing-agent` when the bridge is genuine
- **Local-first** — every run is offline-safe, no telemetry, no upload

---

## CLI reference

```powershell
python run.py `
    --x-handle @creator `
    --demo ai `
    --priority-focus all `
    --max-dms 20 `
    --output today.md
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--x-handle` | yes | — | Your X handle, e.g. `@JanSol0s`. |
| `--dm-batch` | one of | — | Inline JSON list of DM records. |
| `--dm-file` | one of | — | Path to a JSON file with `{dms: [...]}` or just a list. |
| `--date-range` | one of | — | ISO range like `2026-04-30:2026-05-04` (v1: bucket fallback). |
| `--demo` | one of | — | Prefab niche bundle: `ai`, `productivity`, `finance`, `creator`, `fitness`. |
| `--priority-focus` | no | `all` | One of: `urgent`, `opportunities`, `all`. |
| `--max-dms` | no | `20` | Cap on DMs to ingest (1-100). |
| `--niche` | no | auto | Optional niche hint to bias paraphrase library. |
| `--output` | no | stdout | Markdown file path; folders auto-created. |
| `--no-banner` | no | off | Suppress the banner header. |
| `--date` | no | today | Override the deterministic date (YYYY-MM-DD). |
| `--version` | — | — | Print version and exit. |

If no input source is supplied, the runner falls back to the auto-detected niche bucket's prefab bundle so the offline demo always works.

### DM record shape

```json
{
  "sender": "@username",
  "kind": "opportunity-sponsor",
  "text": "(optional; never reproduced verbatim)",
  "timestamp": "2026-05-04T10:00:00Z"
}
```

The `kind` label drives paraphrase + priority + category + reply selection. Canonical kinds:

- **opportunity-sponsor** | **opportunity-followup** | **opportunity-collab**
- **urgent-bug** | **urgent-deadline**
- **community-advocate** | **community-question** | **community-peer**
- **admin-platform** | **admin-billing**
- **spam-crypto** | **spam-shoutout** | **spam-followback** | **spam-copypasta** | **spam-rt-to-win**

Unknown kinds default to `community-question` with `medium` priority. The privacy guarantee holds regardless: the runner never echoes the `text` field — it derives the paraphrase from `kind` + niche bucket.

---

## How it slots into the creator-template flow

DM Triager is the inbox-clearing tool — every other creator template either feeds or extends one of its outputs:

| Section | Bridge to |
|---|---|
| Suggested Reply (top priority DM) | `reply-drafter` for a 3-variant voice-matched draft set |
| Opportunity card (sponsor inquiry) | `monetization-optimizer` to model the deal vs current stream mix |
| Opportunity card (any) | `research-assistant` to verify the sender's claim before signing |
| Priority senders' public mentions | `mention-summarizer` for cross-channel triage |
| Inbox-signal headline | `daily-briefing-agent` to thread inbox into tomorrow's brief |
| Sudden anomaly in DM volume | `analytics-summarizer` for engagement-context sanity check |

So the daily flow is: brief → research → ideas → build threads → ship → triage mentions → **triage DMs (this template)** → measure → loop. All ten templates share the same 6-verb action vocabulary, 8-angle palette, and Apache-headered output.

---

## Examples

Two realistic, copy-paste-ready outputs live in `examples/`:

- [examples/niche-ai-agents.md](examples/niche-ai-agents.md) — `@JanSol0s` 20-DM triage for *AI agents on X* (5 priority cards, 4 spam aggregated by pattern, 5 action items, 3 cross-template bridges).
- [examples/niche-productivity.md](examples/niche-productivity.md) — `@solo` 15-DM triage for *Productivity systems for solopreneurs*.

Both files were produced verbatim by:

```powershell
python run.py --x-handle @JanSol0s --demo ai --priority-focus all --max-dms 20 --niche "AI agents on X" --date 2026-05-04 --no-banner --output examples/niche-ai-agents.md
python run.py --x-handle @solo --demo productivity --priority-focus all --max-dms 15 --niche "Productivity systems for solopreneurs" --date 2026-05-04 --no-banner --output examples/niche-productivity.md
```

You can reproduce them on Windows or in CI to verify your install is healthy.

---

## Wire it to live Grok 4.3 (production upgrade)

The bundled DM data is intentionally minimal so the demo runs offline and zero-config the moment `grok install this` finishes. To upgrade to live grounding:

1. Replace `DEMO_DM_BUNDLES` with a real fetcher (X DM API when authorized) that returns the same `{sender, kind, text}` shape. Critically: the runner's privacy guarantee depends on producing paraphrases from `kind`, not from `text` — preserve that contract when wiring live data.
2. The system prompt at `prompts/system.md` (shipped in P61, ~430 lines) is auto-loaded by `load_system_prompt()` — pass it verbatim as the system message. It encodes the 13 hard rules including the privacy-paranoid mandate, structured 6/7-section schema, 5 categories, 6-verb action vocabulary, and ≥3 cross-template bridges.
3. Replace `generate_dm_triage()`'s body with a Grok call that returns the same dict shape. `render_report()` will keep working unchanged — and crucially, the privacy banner is baked into the meta header so users always see the privacy notice.
4. Pass the structured user message: `x_handle`, `dms`, `priority_focus`, `max_dms`, `niche`. Make sure the live Grok call NEVER receives raw DM text alongside the `kind` label — only one or the other, to preserve the privacy guarantee.

Once wired, every flag in the CLI flows straight into the live Grok call — same UX, real grounding from real DMs, same privacy posture.

---

## Hard rules (from the manifest's `constitution:` block)

1. **PRIVACY-PARANOID** — DM text is never reproduced verbatim. Always paraphrase. PII redacted before any quote.
2. Always emit the structured 6-section shape (or 7 with Privacy Audit when >25% sensitive-PII rate).
3. Priority + category labels are qualitative only — never percentages.
4. Refuse spam-saturated batches (>70% scam/phishing/harassment).
5. Per-card refusal for policy-violating reply suggestions; rest of triage continues.
6. Suggested replies are DRAFT-only, ≤400 chars; never auto-sent.
7. Sender-handle dedup with cumulative reasons.
8. Spam section paraphrases the pattern, never the content.
9. Tag finance-adjacent priority cards with V.1 disclaimer.
10. ≥3 cross-template bridges when bridges are genuine.
11. No silent contradictions on conflicting facts.
12. Local-first — no syncing, no upload, no telemetry.

The v1 demo runner enforces every rule structurally. The privacy guarantee is **architectural**: the runner generates paraphrases from `kind` labels, never from DM text — so even a buggy template substitution cannot leak input. Rules #4 and #5 land at the input-validation layer before any rendering happens.

---

## Files in this folder

```
dm-triager/
├── grok-agent.yaml                 # v2.15 manifest (P61)
├── prompts/
│   └── system.md                   # Grok system prompt, ~430 lines (P61)
├── run.py                          # zero-dependency CLI (P62)
├── examples/
│   ├── niche-ai-agents.md          # AI niche, 20-DM triage (P62)
│   └── niche-productivity.md       # Productivity niche, 15-DM triage (P62)
└── README.md                       # this file (P62)
```

---

## License

Apache 2.0. See `LICENSE` at the repo root.

---

> 🔒 **Privacy notice:** the runner is offline by design and never reproduces DM text verbatim. Built to help xAI and Grok win — ecosystem allies, not competitors.
