<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Creator Agent Program — Outreach Tracker + Weekly Report

> ⚠️ **Not financial advice. Not tax advice.**
> Outreach for the `monetization-optimizer` template carries the standard Vietnam-resident creator addendum on every delivery DM. Always consult a licensed local advisor before acting on any financial output. This tool tracks outreach metadata only — it gives no business, legal, financial, or tax advice itself.

> **Built to help xAI and Grok win the platform battle.**
> Local-first, privacy-respecting infrastructure for the @JanSol0s outreach flow. Every DM, response, and delivered agent is logged on **your Windows machine only** — nothing is synced, telemetered, or sent to any third party.

---

## What this is

The operational backbone of the Creator Agent Program (per `CLAUDE.md` §6 Phase 3 P89 + the launch thread at `docs/creator-program/launch-thread.md`). It tracks the funnel from initial DM → response → custom-tuned manifest delivery, and renders a weekly markdown report you can paste into your private review doc or publish (redacted) to X.

| File | Purpose |
|---|---|
| `outreach-tracker.py` | CLI to log/respond/deliver/list/stats |
| `weekly-report.py` | Renders a clean markdown weekly report |
| `launcher.ps1` | Windows 11 + PowerShell launcher (one entry point for both) |
| `examples/weekly-report-sample.md` | What the rendered report looks like |

---

## Privacy contract (read before using)

1. **Inbound consent only.** The tracker refuses to log an X handle without the `--consent` flag. Use it **only** when the creator has DM'd YOU first. Don't scrape; don't pre-emptively log; don't add handles you found in someone else's reply thread.
2. **Local-only data.** Every byte lives at `$env:LOCALAPPDATA\grok-agent\creator-program\` on your Windows machine. No cloud, no telemetry, no outbound network calls.
3. **Notes are local-only.** The `--notes` field never leaves your machine and never appears in published versions of the report (when you redact handles for an X progress thread, redact notes too).
4. **Right to deletion.** A creator who asks to be removed: open the JSON store and delete their entry by ID. There is no other copy.

---

## Setup (Windows 11)

```powershell
# 1. Make sure Python 3.12+ is on PATH
python --version    # → Python 3.12.x

# 2. (Optional) cd into the program folder for shorter commands
cd templates\creator-program

# 3. Confirm the launcher works
.\launcher.ps1 stats
# → "(no outreach logged yet)" on first run
```

The AppData folder (`$env:LOCALAPPDATA\grok-agent\creator-program\`) is created automatically on first write.

---

## Daily workflow

### When a creator DMs you (inbound)

```powershell
.\launcher.ps1 log `
    --handle JanSol0s `
    --niche "ai-agents" `
    --followers 12500 `
    --template content-idea-generator `
    --consent `
    --notes "Asked about brand-voice fit; wants weekly cadence"
# → Logged outreach OR-0001 for @JanSol0s → content-idea-generator (12,500 followers).
```

### When they reply to your follow-up

```powershell
.\launcher.ps1 respond --id OR-0001 --notes "Confirmed niche; sent intake form"
```

### When you ship the custom-tuned manifest

```powershell
.\launcher.ps1 deliver --id OR-0001 --notes "Sent manifest + 60s install Loom"
```

### If they go cold or decline

```powershell
.\launcher.ps1 decline --id OR-0001 --notes "Pivoted to a different stack"
```

### Live status anytime

```powershell
.\launcher.ps1 list      # most-recent-first table
.\launcher.ps1 stats     # response rate, delivery rate, top templates
```

---

## Weekly review

Every Sunday afternoon, run:

```powershell
.\launcher.ps1 report-7
# → Wrote ...\reports\weekly-report-7d-2026-05-12.md
```

The report includes:

- **Funnel snapshot** — outreach → responded → delivered, with rates
- **Top niches** — what kinds of creators are actually responding
- **Most-requested templates** — which of the 20 templates is winning
- **Recent deliveries** — last 10, with handle + template + follower count
- **Stale outreach** — pending >7 days; nudge or mark `decline` to keep the funnel honest
- **Suggested next actions** — auto-generated based on the current state

Use the `report-30` action for a monthly cumulative view.

---

## The 20 valid `--template` values

Mirrors `templates/creator/` on disk. Any other value is rejected by the tracker.

**Content creation:** `content-idea-generator`, `thread-builder`, `content-recycler`, `trend-aligned-poster`, `content-calendar-builder`

**Engagement & replies:** `reply-drafter`, `comment-engagement-booster`, `mention-summarizer`, `dm-triager`, `quote-tweet-suggestor`

**Analytics & growth:** `analytics-summarizer`, `ab-test-suggester`, `growth-experiment-runner`, `hashtag-strategy-advisor`

**Audience & network:** `follower-quality-analyzer`, `niche-influencer-finder`, `competitor-watch`

**Brand & distribution:** `brand-voice-trainer`, `cross-platform-reposter`

**Monetization:** `monetization-optimizer` ⚠️ (delivery DM **must** include the V.1 + V.2 disclaimers + Vietnam-resident addendum — the tracker will remind you on the `log` and `deliver` calls)

---

## Storage layout

```text
$env:LOCALAPPDATA\grok-agent\creator-program\
├── outreach.json             # the single source of truth
└── reports\
    ├── weekly-report-7d-2026-05-12.md
    ├── weekly-report-7d-2026-05-19.md
    └── weekly-report-30d-2026-05-31.md
```

The JSON schema is intentionally simple so you can hand-edit it in any text editor (e.g. to redact a handle on request). Each entry has:

```json
{
  "id": "OR-0001",
  "handle": "JanSol0s",
  "niche": "ai-agents",
  "follower_count": 12500,
  "chosen_template": "content-idea-generator",
  "logged_at": "2026-05-05T14:23:11Z",
  "responded_at": null,
  "delivered_at": null,
  "status": "pending",
  "notes": "Asked about brand-voice fit",
  "consent_recorded": true
}
```

---

## Eligibility rules (enforced by the tracker)

- **Follower floor:** 10,000 (the program's stated mid-tier focus). The tracker rejects `--followers` below this.
- **Inbound DM only:** the tracker requires `--consent` to log a handle (privacy contract item 1).
- **One template per outreach:** if a creator wants two, log two entries; bundle delivery in one DM.

---

## What this is NOT

- Not a CRM. No pipelines, no lead scoring, no automation.
- Not a recommender. The tracker doesn't suggest who to DM next.
- Not a financial / tax / legal advice tool. Read the disclaimer at the top.
- Not a replacement for the launch-thread DM funnel — it's the bookkeeping layer underneath.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Python 3 is required` | Install Python 3.12 from python.org; re-open PowerShell. |
| `unknown template 'foo'` | Run `.\launcher.ps1 stats` to see valid templates listed in the tracker error message; spelling must match `templates/creator/<slug>/`. |
| `follower_count below program floor` | The Creator Program targets 10k+ creators. If you want to track sub-10k separately, fork this folder. |
| Tracker outputs to a path not on Windows | You're running outside Windows; `$env:LOCALAPPDATA` is unset. Set it manually for tests: `$env:LOCALAPPDATA = "$HOME\AppData\Local"`. |
| Want to reset the store | Delete `$env:LOCALAPPDATA\grok-agent\creator-program\outreach.json`. |

---

## Related

- The public X launch thread: `docs/creator-program/launch-thread.md` (P103)
- The 20 creator templates: `templates/creator/` (P43–P102)
- Constitution Articles V.1 + V.2 (mandatory disclaimers): `safety/constitution.md`
- Roadmap: `ROADMAP.md` Phase 3 (P88–P92 outreach program)

> Built to help xAI and Grok win. 🚀
