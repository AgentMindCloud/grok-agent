<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# MERGE_PLAN.md — Phase 16 final merge status

> Built for xAI, X, Grok and the ecosystem community. ❤️

This file records the **final Tier 3 merge** of `x-platform-toolkit`
and `grok-pulse-mcp-server` into the `AgentMindCloud/grok-agent` OS
monorepo. With this fold-in complete, the OS now hosts every
first-party surface the creator ecosystem needs from a single clone.

---

## Final merge status (2026-05-07)

| # | Source repo | Destination prefix | Strategy | Squash commit | Source tip | Status |
|---|---|---|---|---|---|---|
| 1 | [`AgentMindCloud/x-platform-toolkit`](https://github.com/AgentMindCloud/x-platform-toolkit) | `tools/` | `git subtree add --prefix=tools <url> main --squash` | `18b54c2` | `1368f52` | ✅ merged |
| 2 | [`AgentMindCloud/grok-pulse-mcp-server`](https://github.com/AgentMindCloud/grok-pulse-mcp-server) | `pulse/` | `git subtree add --prefix=pulse <url> main --squash` | `df151ef` | `f542213` | ✅ merged |

The merge commits sit immediately after the squash commits in `git
log` — `7c57c87` (tools) and `3668c14` (pulse).

---

## What this means

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

---

## Why subtree (not submodule)

| Concern | `git subtree --squash` | `git submodule` |
|---|---|---|
| Clone UX | Single `git clone` — done. | Two-step (`git submodule update --init`). |
| Contributor friction | Edits land in this repo's normal flow. | Requires a separate PR per submodule. |
| History weight | One squash commit per fold-in. | Carries full upstream history forever. |
| Re-sync option | `git subtree pull` (explicit, gated). | Auto-tracking — risk of unintended drift. |

Subtree wins on every axis for the OS doctrine: **the monorepo owns
these surfaces now.**

---

## Re-syncing from upstream (reference only)

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

## Cross-references

- [`README.md`](README.md) — see the **Folded sub-projects (Phase 16)**
  section for the user-facing summary.
- [`CLAUDE.md`](CLAUDE.md) §13 — Untouchables doctrine; this fold-in
  is compliant because the source repos remain unmodified.
- [`HANDOFF_LOG.md`](HANDOFF_LOG.md) — Phase 16 entry records the same
  fact for orchestration continuity.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
