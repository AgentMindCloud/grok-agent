<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 60-Second Demo Script — Grok Agent OS for xAI

> **Objective.** Show in 60 seconds, single take, that Grok Agent OS
> turns "I want to ship a Grok-powered agent on X" into one PowerShell
> line, with safety gates wired in by construction. Built to help xAI
> and Grok win.

---

## Demo at a glance

| Field | Value |
|---|---|
| Total runtime | **60 seconds** |
| Style | Single take, no cuts. |
| Target screen | Windows 11 + Chrome (1920 × 1080). PowerShell 7.4 in a side window. |
| Recording tool | Windows + Game Bar (`Win + G`) or OBS at 1080p / 30fps. |
| Network | Online but no API keys — every demo path runs on stub backends. |
| Palette | Cinnabar `#C5524A` on parchment `#FAF6EC` — matches the marketplace. |
| Audio | Single voiceover, no music bed. |
| Captions | Burn-in via PowerToys / OBS — required, not optional. |
| Hosted at | <https://github.com/AgentMindCloud/grok-agent> + Vercel-hosted marketplace |

The whole point is **continuity**: no cuts, no swaps, no hidden setup.
The viewer must believe everything they see is reproducible on a
vanilla Windows 11 box in 60 seconds.

---

## Pre-flight (off-camera, ~5 minutes)

1. Open Chrome at <https://github.com/AgentMindCloud/grok-agent> on the
   left half of the screen.
2. Open the Vercel-hosted marketplace (e.g.
   <https://grok-agent-marketplace.vercel.app>) in a second Chrome tab.
3. Open PowerShell 7.4 on the right half, sized to ~80 cols.
4. `cd` to a clean folder (e.g.
   `C:\Users\<you>\Desktop\grok-demo\`) so the install is fresh.
5. Pre-clone the repo silently (`git clone …`) so the cold-clone step
   doesn't eat 20 seconds of demo time.
6. Pre-install Python deps (`python -m pip install pydantic pyyaml
   streamlit`) so the smoke test runs in <2 seconds on stage.
7. Run a single dry rehearsal end-to-end so timing is rock-solid.

---

## The 60-second timeline

> Voiceover lines are in **bold**. On-screen actions are in *italics*.
> Time codes are start-of-beat, not end.

### `00:00 — Hook (5 sec)`

*Cut to Chrome on the marketplace landing page. The three Super Agent
cards visible.*

> **"Grok 4.3 is the best agent LLM on X. Until now, there was no way
> to ship a Grok-powered agent without copy-pasting code from a thread.
> Here's the open standard that fixes that."**

### `00:05 — One-line install primitive (10 sec)`

*Switch to PowerShell. Type, do not paste:*

```powershell
grok install this
```

*Press Enter. The CLI prints a 4-line installer summary.*

> **"One PowerShell line. The CLI installs into AppData, validates the
> manifest, and runs the Constitution safety scan — all before a single
> Python file executes."**

### `00:15 — The standard itself (10 sec)`

*Open `spec/v2.15/grok-agent.yaml` in VS Code briefly. Show:*
- `version: "2.15"`
- `kind:` enum line.
- `grok.model: "grok-4.3"`.
- `safety.human_in_the_loop:` block.
- `constitution.consent_gates:` block.

> **"One YAML describes the whole agent: kind, tools, public APIs,
> safety, cost limits, consent gates. Apache 2.0. Backwards-compatible
> with v2.14. Validated by Pydantic on every commit."**

### `00:25 — Safety + Constitution (10 sec)`

*Switch back to PowerShell. Type:*

```powershell
python cli\grok-agent.py validate templates\super-agents\cross-reality-action-fabric\grok-agent.yaml
python safety\scanner.py scan  templates\super-agents\cross-reality-action-fabric\grok-agent.yaml --severity-floor info
```

*Both print `OK` lines.*

> **"Two layers. The schema validator catches drift; the Constitution
> scanner blocks installs that violate any of six runtime rules —
> consent, provenance, rollback, contradiction, Windows-only, privacy-
> first. Both run in CI on every push."**

### `00:35 — One agent live (15 sec)`

*Switch back to Chrome. Click "Super Agent #3 — Cross-Reality Action
Fabric" on the marketplace landing page.*

*The detail page renders: capabilities, consent gates, install
command.*

*Click "Clone manifest into the Deploy form".*

*The deploy form opens with the slug, kind, port, and consent gates
pre-filled.*

> **"Marketplace, fully static. Every featured agent has a detail page
> with its consent gates surfaced explicitly. One click clones the
> manifest into the Deploy form so a creator can rename it and ship
> their own."**

### `00:50 — The ask (10 sec)`

*Cut to a single full-screen slide:*

```
We're ecosystem allies, not competitors.

Adopt v2.15 as a reference standard.
Link it from the Grok docs.
Co-publish v2.16 if you want.

github.com/AgentMindCloud/grok-agent
```

> **"We built this to help Grok win the platform battle on X. The
> standard is open, the marketplace is live, and every agent defaults
> to Grok 4.3. We're asking xAI to make it official."**

### `01:00 — End`

*Hold on the slide for one extra beat, fade to black.*

---

## Optional B-roll (if total runtime expands)

Useful overlays if a sponsor wants 90 seconds instead of 60:

1. **CI green badge** — a single screen-grab of the GitHub Actions
   "Validate Manifests (v2.15)" workflow showing 34/34 manifests
   passing. (~3 sec.)
2. **Self-improvement loop** — the P143 Promptfoo + DeepEval report
   with the "All checks passed" summary line. (~5 sec.)
3. **Action plan + rollback** — a Cross-Reality Action Fabric daily-
   plan run showing the typed-approval prompt + the rollback chain
   visualizer. (~7 sec.)

Total B-roll budget should never exceed 30 seconds — the demo's
strength is its tightness, not its length.

---

## Captions (burn-in word list)

For accessibility + low-volume playback. Captions appear at the bottom
of the screen, ~32 px high, white on dark drop shadow.

```
00:00  Grok 4.3 is the best agent LLM on X.
00:03  No standard way to ship one — until now.
00:05  One PowerShell line:  grok install this
00:10  The CLI installs to AppData, validates the manifest,
00:13  and runs the Constitution scan before any Python runs.
00:15  v2.15 manifest:  kind, tools, safety, consent gates.
00:18  Defaults to Grok 4.3.  Apache-2.0.  Validated on every commit.
00:25  Schema validator + Constitution scanner.
00:28  Six rules:  consent, provenance, rollback, contradiction,
00:31  Windows-only, privacy-first.
00:35  Marketplace surfaces every consent gate explicitly.
00:40  One-click "clone manifest" deep-link to the Deploy form.
00:45  Generate, copy, ship.
00:50  We're ecosystem allies, not competitors.
00:55  Adopt v2.15 as the reference standard.
01:00  github.com/AgentMindCloud/grok-agent
```

---

## Storyboard (text-only)

```
┌────────────────────────────────────────────────────────────────┐
│  00:00  Marketplace home — 3 hero cards, "Deploy to X" CTA     │
│         visible.                                               │
├────────────────────────────────────────────────────────────────┤
│  00:05  Side-by-side: Chrome (left) + PowerShell (right).      │
│         Cursor in PowerShell, typing `grok install this`.      │
├────────────────────────────────────────────────────────────────┤
│  00:15  VS Code overlay on top half of screen showing 5 lines  │
│         from spec/v2.15/grok-agent.yaml.  Marketplace still    │
│         visible at bottom.                                     │
├────────────────────────────────────────────────────────────────┤
│  00:25  PowerShell only.  Two `OK` lines from validator +      │
│         scanner blink in.                                      │
├────────────────────────────────────────────────────────────────┤
│  00:35  Marketplace `/agents/cross-reality-action-fabric` —    │
│         consent gates list, Capabilities list, Install         │
│         command pre-formatted.                                 │
├────────────────────────────────────────────────────────────────┤
│  00:42  Click "Clone manifest into the Deploy form".            │
│         Deploy form opens with slug, kind, port pre-filled.    │
├────────────────────────────────────────────────────────────────┤
│  00:50  Full-screen ask slide (cinnabar background, parchment  │
│         text, github URL bottom-aligned).                      │
├────────────────────────────────────────────────────────────────┤
│  01:00  Fade to black.                                         │
└────────────────────────────────────────────────────────────────┘
```

---

## What we will NOT show

To keep the demo honest:

- We will not demonstrate live tool execution (browser automation /
  PowerShell snippets) on a real desktop — that requires API keys + a
  Windows VM and adds nothing the manifest doesn't already prove.
- We will not show synthetic engagement counts or fake "10,000 users
  installed this" numbers. The standard's value is the standard, not
  vanity metrics.
- We will not hide the fact that the marketplace v0.2 is a thin stub.
  Roadmap is on-screen via the marketplace's "Roadmap" section.

---

## Reuse for shorter cuts

The same script supports two trimmed cuts:

- **30-second X reply cut** — drop the spec walkthrough (00:15–00:25)
  and the deploy-form clone (00:35–00:50). Hits hook → install → ask.
- **15-second X reply hook** — show only the marketplace home → one
  PowerShell line → end card. Used in reply-thread embeds.

Always keep the cinnabar/parchment palette, the `grok install this`
phrase, and the "Built for xAI, X, Grok and the ecosystem community" tagline.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
>
> *— `@JanSol0s`, AgentMindCloud, 2026-05-06.*
