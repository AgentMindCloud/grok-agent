<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — One-Pager

> Built for xAI, X, Grok and the ecosystem community. ❤️

**The missing OS layer for Grok agents on X.** One YAML manifest. One install command. One safety scanner. Apache 2.0. Windows-first. Local-first. Built deliberately as an ecosystem ally to xAI — the runtime and distribution layer xAI has not shipped yet.

---

## The elevator pitch

Every team building a Grok-powered agent on X kept reinventing the same plumbing — install paths, safety gates, distribution channels, trust scoring. There was no standard, no scanner, no marketplace shelf. Grok Agent OS is the open answer: a unified manifest format (`grok-agent.yaml` v2.15), a Windows-native PowerShell CLI (`grok-agent.ps1`), a 33-check Agent Constitution scanner, a curated static marketplace, and a self-improving evaluation loop. Anyone can post a YAML to X, and any reader can install it on their Windows machine in seconds with `grok install this`. No app store, no accounts, no middleman fees, no royalty.

---

## Six facts to remember

1. **One YAML, one command, one scanner.** A `grok-agent.yaml` v2.15 manifest fully describes any agent. The CLI validates it with Pydantic, runs it through the 33-check Agent Constitution scanner, and copies it to `$env:LOCALAPPDATA\grok-agent\agents\<name>\`. Distribution is paste-from-X.
2. **Eleven production agents shipped by May 2026.** Four X Money tools (Companion Dashboard, Smart Cashtag Alpha Engine, Creator Payout Optimizer, Vision Analyzer), three flagship Super Agents (Living Narrative Fabric, Self-Evolving Personal OS, Cross-Reality Action Fabric), and four lighter Super Agent patterns. Plus twenty-two creator templates.
3. **Apache 2.0 throughout, no exceptions.** Schema, CLI, scanner, trust-score computer, marketplace, MCP server, tools, templates, docs — all Apache 2.0, header on every file. Forks and white-labels welcome under the grant.
4. **Windows 11 + PowerShell is the canonical surface.** The largest underserved slice of the X creator base runs Windows. CI runs Windows-runner workflows. Paths use `$env:LOCALAPPDATA`. Shell examples use PowerShell verbs. macOS and Linux ports are a community choice, not a project blocker.
5. **Safety is the install gate, not a footnote.** Every install runs the Agent Constitution scanner before files copy. Mandatory disclaimers, consent gates on real-world actions, append-only provenance, hard refusals on impersonation and exfiltration, forbidden-phrase leak detection across the whole repo.
6. **Trust scores are public and deterministic.** Every shipped agent gets a 0–100 score recomputed in CI: `0.4 * scanner + 0.3 * eval + 0.2 * provenance + 0.1 * stability`. The marketplace renders an embeddable SVG badge per agent.

---

## What ships in the repo today

| Surface | Count | Path |
|---|---|---|
| X Money tools | 4 | [`templates/finance/`](../../templates/finance/) |
| Super Agents (3 flagship + 4 lighter) | 7 | [`templates/super-agents/`](../../templates/super-agents/) |
| Creator templates | 22 | [`templates/creator/`](../../templates/creator/) |
| Manifest schema | v2.15 | [`spec/v2.15/grok-agent.yaml`](../../spec/v2.15/grok-agent.yaml) |
| CLI | PowerShell + Python fallback | [`cli/grok-agent.ps1`](../../cli/grok-agent.ps1) |
| Agent Constitution | 7 articles, 33 named checks | [`safety/constitution.md`](../../safety/constitution.md) |
| Marketplace | 33 listings, static Next.js | [`marketplace/`](../../marketplace/) |
| MCP attention server | 5 tools | [`pulse/`](../../pulse/) |

---

## The install hook

```powershell
git clone https://github.com/AgentMindCloud/grok-agent.git ; cd grok-agent
.\cli\grok-agent.ps1 install templates/finance/x-money-companion-dashboard
```

Or paste any v2.15 manifest from X directly:

```powershell
.\cli\grok-agent.ps1 install -FromStdin
```

The CLI validates, scans, copies. The agent boots from `$env:LOCALAPPDATA\grok-agent\` with no cloud roundtrip and no telemetry.

---

## Positioning, in one sentence

Grok Agent OS is to Grok agents what `npm` plus `homebrew` plus a safety review board is to web packages — the open distribution, runtime, and trust layer that lets the ecosystem ship faster while keeping the floor honest.

---

## Where to go next

- [`README.md`](../../README.md) — the canonical landing page.
- [`faq.md`](faq.md) — twelve deep-dive questions.
- [`founder-bio.md`](founder-bio.md) — three byline-ready bios for `@JanSol0s`.
- [`screenshots.md`](screenshots.md) — every marketing visual and where to grab it.
- [`brand-assets.md`](brand-assets.md) — Spectral v1 palette, logo rules, badge embeds.
- [`contact.md`](contact.md) — how to reach `@JanSol0s` and `AgentMindCloud`.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
