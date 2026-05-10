<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# MERGE_PLAN.md — Cross-repo Merge & Visual Identity Tracker

> Built for xAI, X, Grok and the ecosystem community. ❤️

This file is the single source-of-truth for two related streams of
work that consolidate the OS:

- **Tier 3 — Repo fold-ins.** Bringing first-party surfaces
  (`x-platform-toolkit`, `grok-pulse-mcp-server`) into the OS monorepo
  via `git subtree --squash` so the creator ecosystem ships from one
  clone.
- **Tier 4 — Visual identity passes.** Applying the Spectral v1
  cyberpunk palette across `grok-install`, `grok-build-bridge`, and
  `grok-agent` so the three repos read as one continuous system.

This file is intentionally short. It is not a roadmap, not a prompt
log, and not a marketing pitch. Those live elsewhere:

- Roadmap → [`ROADMAP.md`](ROADMAP.md)
- Prompt log → [`HANDOFF_LOG.md`](HANDOFF_LOG.md)
- Audit → [`docs/workplan-audit.md`](docs/workplan-audit.md)
- xAI pitch → [`docs/pitch/xai-partnership-pitch.md`](docs/pitch/xai-partnership-pitch.md)

---

## Tier 3 — Phase 16 fold-in (`tools/` + `pulse/`)

### Final merge status

| # | Source repo | Destination prefix | Strategy | Squash commit | Source tip | Status |
|---|---|---|---|---|---|---|
| 1 | [`AgentMindCloud/x-platform-toolkit`](https://github.com/AgentMindCloud/x-platform-toolkit) | `tools/` | `git subtree add --prefix=tools <url> main --squash` | `18b54c2` | `1368f52` | ✅ merged |
| 2 | [`AgentMindCloud/grok-pulse-mcp-server`](https://github.com/AgentMindCloud/grok-pulse-mcp-server) | `pulse/` | `git subtree add --prefix=pulse <url> main --squash` | `df151ef` | `f542213` | ✅ merged |

The merge commits sit immediately after the squash commits in `git
log` — `7c57c87` (tools) and `3668c14` (pulse). The `--no-ff`
integration commit landing both into `main` from
`origin/claude/merge-toolkit-mcp-server-QbaPH` is `feat: merge Phase
16 Tier 3 fold-in (tools/ + pulse/)`.

### What this means

- **History preserved.** Both folds landed via `git subtree add
  --squash`. The source-repo tip SHAs above are the canonical pointer
  back if anyone needs to reconstruct lineage. Nothing was rewritten.
- **License intact.** Each sub-project keeps its own Apache 2.0
  `LICENSE` file at its directory root. The repo-root `LICENSE`
  continues to apply to everything outside `tools/` and `pulse/`.
- **Independent packages.** `tools/` and `pulse/` each carry their
  own `package.json`, `README.md`, and build configuration and stay
  buildable in isolation. They are not wired into the OS CLI yet —
  they live as drop-in surfaces.
- **Provenance recoverable.** Per [`CLAUDE.md`](CLAUDE.md) §13, the
  original `x-platform-toolkit` repo at
  `github.com/AgentMindCloud/x-platform-toolkit` was untouched — only
  a snapshot was copied into `tools/`. The same applies to
  `grok-pulse-mcp-server` (not §13-listed, but treated identically).

### Why subtree (not submodule)

| Concern | `git subtree --squash` | `git submodule` |
|---|---|---|
| Clone UX | Single `git clone` — done. | Two-step (`git submodule update --init`). |
| Contributor friction | Edits land in this repo's normal flow. | Requires a separate PR per submodule. |
| History weight | One squash commit per fold-in. | Carries full upstream history forever. |
| Re-sync option | `git subtree pull` (explicit, gated). | Auto-tracking — risk of unintended drift. |

Subtree wins on every axis for the OS doctrine: **the monorepo owns
these surfaces now.**

### Re-syncing from upstream (reference only)

If the original repos ever ship a tagged release worth pulling in,
the PowerShell commands are:

```powershell
# tools/ — pull upstream main into the tools/ subtree
git subtree pull --prefix=tools `
    https://github.com/AgentMindCloud/x-platform-toolkit.git main --squash

# pulse/ — pull upstream main into the pulse/ subtree
git subtree pull --prefix=pulse `
    https://github.com/AgentMindCloud/grok-pulse-mcp-server.git main --squash
```

> ⚠️ **Default policy: no upstream re-pulls.** The OS owns these
> directories from Phase 16 onward. Re-pull only with explicit creator
> approval and a fresh `MERGE_PLAN.md` row recording the new tip SHA.

---

## Tier 4 — Spectral v1 visual identity

### System tokens

| Token            | Value      | Role                                                |
|------------------|------------|-----------------------------------------------------|
| Plasma           | `#FF1E70`  | Primary — hero, badges, contradictions, primary CTA |
| Aurora           | `#00E0D5`  | Accent — live indicators, success states, links     |
| Dark             | `#0A0A0A`  | Canvas — backgrounds, badge label fields            |
| Parchment text   | `#F4ECDA`  | Hero / footer text on dark canvas                   |
| Inter            | font       | Headings, hero, taglines                            |
| JetBrains Mono   | font       | Code, terminal blocks, typing-SVG                   |

Effects layered on the tokens:

- **Chromatic aberration** — Plasma → Dark → Aurora ribbon on hero +
  footer capsule-render `waving` images. Top of page leads Plasma,
  bottom leads Aurora; the two halves frame the README.
- **Halftone** — capsule-render `rect` thin gradients (height ≤ 4px)
  used as section dividers between major hero block and content blocks.
- **Nebula circles** — radial Plasma / Aurora gradients reserved for
  per-section sub-heroes (the "Tools" tab marker in this README is the
  reference implementation).
- **Aurora live indicator** — `● live` shields.io badge in
  `for-the-badge` style on Dark, used wherever a section reflects
  real-time state (the "Pulse" tab marker above
  `## What's shipped (May 2026)`).

### Tier 4 — `grok-agent` OS — Phase 20 (this repo)

| Field           | Value                                                              |
|-----------------|--------------------------------------------------------------------|
| Date            | 2026-05-07                                                         |
| Branch          | `claude/spectral-visual-identity-GXpU5`                            |
| Merge commit    | `feat: Tier 4 Spectral visual identity (Phase 20)` (`--no-ff`)     |
| Status          | applied + merged into `main`                                       |

#### Scope (what changed)

- Root [`README.md`](README.md) hero capsule re-tinted Plasma → Dark →
  Aurora, parchment fontColor — chromatic-aberration ribbon for the
  consumer cathedral.
- Typing-SVG colour `#FF6B00` → `#FF1E70`; font `Fira Code` →
  `JetBrains Mono` so the type stack matches the Spectral system.
- Badge row recoloured: License + 11 agents = Plasma; Windows 11 +
  Python + Phase 5 active = Aurora; manifest = Dark with Plasma label;
  new `spectral · v1` system badge.
- Spectral chromatic-aberration thin divider (capsule-render `rect`
  4px) inserted between hero block and `## TL;DR`.
- "Tools" tab analog (`## The 11 agents`): Spectral nebula sub-hero
  banner, ◆ glyph row prefix on every agent table, and a one-line
  blockquote tagging the section as the consumer-cathedral Tools tab.
- "Pulse" tab analog (above `## What's shipped (May 2026)`):
  Aurora `● live — Phase 5 active` for-the-badge indicator plus a
  Plasma `◇ pulse — real-time` companion badge.
- Mermaid architecture diagram given Plasma + Aurora + Dark + Stop
  classDefs so schema/install/run nodes carry the system colours and
  the two stop nodes glow Plasma against the dark canvas.
- Stack table extended with explicit "Type system" row (Inter +
  JetBrains Mono) and a "Visual identity" row pointing at Spectral v1.
- Footer capsule mirrored: Aurora → Dark → Plasma, so the page closes
  with the chromatic-aberration ribbon flipped vs. the hero — the
  full README reads as one continuous halftone gradient top-to-bottom.
- This `MERGE_PLAN.md` added at repo root.

#### Out of scope (intentionally NOT touched)

- `marketplace/app/globals.css` — keeps Cinnabar / parchment per
  [`CLAUDE.md` §3](CLAUDE.md) branding rule. Spectral is for READMEs;
  Cinnabar / parchment is for in-app visual assets (Residual
  Frequencies system).
- `safety/scanner.py`, manifest schemas, Constitution, CI workflows,
  Python implementation code — purely a visual-identity pass, no
  behaviour changes.
- The 13 untouchable repos enumerated in [`CLAUDE.md` §13](CLAUDE.md).
- `tools/` and `pulse/` subtrees — owned by the Tier 3 fold-in above;
  their internal READMEs are out of scope for the Spectral pass and
  remain in their original style.

### Tier 4 — `grok-install` (reference only)

Spectral pass already applied earlier. README hero, badges, and
"install primitive" section use the same Plasma + Aurora + Dark
tokens. No changes from this repo.

### Tier 4 — `grok-build-bridge` (reference only)

Spectral pass already applied earlier. README hero + section
dividers + footer use the same tokens. No changes from this repo.

---

## Cohesion checklist

These items are what make the three repos feel like one continuous
visual system. Each box is verified per repo at merge time.

- [x] Same hex values for Plasma / Aurora / Dark
- [x] Same type stack (Inter + JetBrains Mono)
- [x] Capsule-render `waving` header on the hero, `waving` footer
- [x] Chromatic-aberration ribbon: Plasma → Dark → Aurora top, mirrored
      Aurora → Dark → Plasma bottom
- [x] Aurora `● live` indicator wherever a section reflects live state
- [x] Plasma + Aurora classDefs on every Mermaid diagram
- [x] Apache 2.0 header at the top of every code/config file
- [x] Ecosystem-ally tagline (`Built for xAI, X, Grok and the
      ecosystem community. ❤️`) on every README

---

## Cross-references

- [`README.md`](README.md) — see the **Folded sub-projects (Phase 16)**
  section for the user-facing summary of `tools/` + `pulse/`, and the
  Spectral hero / Tools / Pulse markers for the Phase 20 visual pass.
- [`CLAUDE.md`](CLAUDE.md) §13 — Untouchables doctrine; the Tier 3
  fold-in is compliant because the source repos remain unmodified.
- [`CLAUDE.md`](CLAUDE.md) §3 — Branding rules separating Spectral
  (READMEs) from Cinnabar / parchment (in-app visual assets).
- [`HANDOFF_LOG.md`](HANDOFF_LOG.md) — Phase 16 and Phase 20 entries
  record both passes for orchestration continuity.

---

## What this file is NOT

- Not a marketplace launch plan (the Next.js marketplace already ships
  in [`marketplace/`](marketplace/)).
- Not a v2.16 manifest spec (none planned; v2.15 is current).
- Not a license-header rewriter (the Apache 2.0 header rule is in
  [`CLAUDE.md` §2](CLAUDE.md) and the
  [`grok-agent-conventions`](.claude/skills/grok-agent-conventions/SKILL.md)
  skill — both unchanged by Tier 3 or Tier 4).

It is only the cross-repo merge + visual-identity tracker.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
