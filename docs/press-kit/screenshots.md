<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Screenshots & marketing visuals

A descriptive index of the visual surfaces a journalist, partner, or conference organizer can grab to illustrate a story about Grok Agent OS. Every asset is releasable under Apache 2.0. Disk paths are repo-root-relative.

---

## 1. Marketplace landing screenshot

The Next.js static-export marketplace at [`agentmindcloud.github.io/grok-agent`](https://agentmindcloud.github.io/grok-agent) renders a scanline-overlaid grid of every shipped agent — Super Agents, X Money tools, and creator templates. The hero strip carries the cinnabar Spectral v1 palette and the ecosystem-ally tagline. To capture: open the marketplace URL in Google Chrome at 1440 x 900, screenshot the above-the-fold region. Source code: [`marketplace/app/page.tsx`](../../marketplace/app/page.tsx).

## 2. CLI install-flow recap output

Running `.\cli\grok-agent.ps1 install templates/finance/x-money-companion-dashboard` in PowerShell produces a structured recap: schema-validation pass, Constitution-scanner pass with finding count, AppData copy summary, launcher registration, and a final install-complete banner with the agent's local path. Recordings of this flow live as numbered terminal frames under `docs/screenshots/cli-install-recap-*.png` once captured. The CLI source is [`cli/grok-agent.ps1`](../../cli/grok-agent.ps1).

## 3. Hero cards (per-agent SVGs)

Every shipped agent has a stand-alone hero SVG card sized for X-post embedding. Path pattern: `marketplace/public/hero-cards/<slug>.svg`. Examples: [`marketplace/public/hero-cards/living-narrative-fabric.svg`](../../marketplace/public/hero-cards/living-narrative-fabric.svg), [`marketplace/public/hero-cards/x-money-companion-dashboard.svg`](../../marketplace/public/hero-cards/x-money-companion-dashboard.svg), [`marketplace/public/hero-cards/cross-reality-action-fabric.svg`](../../marketplace/public/hero-cards/cross-reality-action-fabric.svg). Each card shows the agent name, slug, kind, and trust tier in the Spectral v1 palette. Open the SVG in any browser; export to PNG at 1200 x 630 for X.

## 4. Trust-badge embeds

The marketplace exposes per-agent trust badges via a Next.js dynamic route at `marketplace/app/api/badge/<slug>` (returns SVG). Embed in any README with a markdown image tag pointing at the deployed URL — for example, `![trust](https://agentmindcloud.github.io/grok-agent/api/badge/x-money-companion-dashboard.svg)`. The badge text is the score and tier. Source: [`marketplace/app/api/badge/[slug]/route.ts`](../../marketplace/app/api/badge/[slug]/route.ts).

## 5. VS Code schema validation

Open any `grok-agent.yaml` in VS Code with the YAML extension installed; the v2.15 JSON Schema published from [`spec/v2.15/`](../../spec/v2.15/) provides inline autocompletion, hover tooltips, and red-underline diagnostics on schema violations. Capture by opening a manifest with a deliberate error (such as missing `version` or unknown `kind`). Source: the schema-extraction pipeline in [`scripts/`](../../scripts/) plus the published `.vscode/settings.json` snippet in [`docs/windows-guide.md`](../windows-guide.md).

---

## How to request additional visuals

Open an issue on [`github.com/AgentMindCloud/grok-agent`](https://github.com/AgentMindCloud/grok-agent) tagged `press-kit` describing the visual you need. Pull requests adding new screenshots to `docs/screenshots/` are welcome under the Apache 2.0 grant.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
