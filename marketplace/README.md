<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — Marketplace (v0.4)

> Built for xAI, X, Grok and the ecosystem community. ❤️

> **Phase 5 deliverable.** The marketplace landing page is generated at
> build time from the actual `grok-agent.yaml` v2.15 manifests on
> disk. No hand-maintained agent list. Add a new manifest under
> `templates/super-agents/`, `templates/finance/`, or `templates/creator/`
> and it shows up on the next build.

> 🔒 **No telemetry. No backend. No auth.** Pure static export. The
> Install button on each card copies the install one-liner to your
> clipboard so you can paste it on X.

---

## What ships in v0.4

- **Dynamic catalogue** at `/` — every Super Agent, X Money tool, and
  Creator Template with a manifest in this repo, scanned at build
  time. Current build picks up **33 agents**: 3 flagship + 4 lighter
  Super Agents, 4 X Money tools, and 22 Creator Templates.
- **Category filter** — chip row at the top of the grid filters between
  *Super Agents*, *X Money Tools*, and *Creator Templates* via URL
  query params (server-rendered, no JavaScript needed for the filter
  state itself).
- **Install on each card** — copies a ready-to-paste primer
  (`grok install this` plus a manifest link) directly to the clipboard.
- **Per-agent detail route** at `/agents/[slug]` — manifest path,
  capabilities, and consent gates pulled from the same dynamic
  catalogue. Statically pre-rendered for every agent at build time.
- **Deploy form** at `/deploy` — client-side React form that emits a
  v2.15 manifest for any of the supported kinds.
- **Retro-terminal layer** — fixed-position CRT scanline overlay (with
  `prefers-reduced-motion` honored) and a global ⌘K / Ctrl+K
  CommandPalette mounted in the root layout.
- **Static export ready** — `output: 'export'` plus
  `basePath: '/grok-agent'` plus `trailingSlash: true` so the build
  output works as a drop-in static site under any subpath. CI deploys
  it to GitHub Pages.

The manifest scanner lives in [`lib/manifests.ts`](./lib/manifests.ts).
The reusable card lives in
[`components/AgentCard.tsx`](./components/AgentCard.tsx). The build-time
prebuild script that writes a flat JSON index for client consumers
lives in [`scripts/build-agents-index.ts`](./scripts/build-agents-index.ts).

---

## Run it locally on Windows 11 (PowerShell)

```powershell
# 1. Clone the repo if you haven't already.
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\marketplace

# 2. Install Node.js 20 (one time).
winget install OpenJS.NodeJS

# 3. Install dependencies.
npm install

# 4. Run the dev server. Marketplace binds to port 3030.
npm run dev

# 5. Open the marketplace in Chrome.
Start-Process "http://localhost:3030"
```

Production build (matches what CI builds for GitHub Pages):

```powershell
npm run build           # runs prebuild → next build → marketplace/out/
npm run typecheck       # type-only check, runs no code
```

The static export lives at `marketplace/out/` after `npm run build`.
You can serve it with any static file host:

```powershell
npx serve marketplace/out
```

---

## Embed badge — `Built on Grok Agent OS`

Every shipped agent gets a static SVG badge at build time. Partners,
template authors, and integrating repos can drop one line into their
own README to advertise the install. The route is `GET /api/badge/<slug>`
(static-exported, served from `marketplace/out/api/badge/<slug>/...` on
GitHub Pages).

Markdown:

```markdown
![Built on Grok Agent OS](https://agentmindcloud.github.io/grok-agent/api/badge/x-money-companion-dashboard)
```

HTML:

```html
<a href="https://agentmindcloud.github.io/grok-agent/agents/x-money-companion-dashboard">
  <img alt="Built on Grok Agent OS"
       src="https://agentmindcloud.github.io/grok-agent/api/badge/x-money-companion-dashboard">
</a>
```

The badge is two-tone (charcoal + cinnabar) matching the Spectral v1
visual system. Width is computed from the slug length so any agent
slug renders without truncation. Apache 2.0 — embed freely.

---

## Install counter API

Every shipped agent gets a static redirect at `GET /api/install/<slug>`
that issues a `307` to the canonical `grok-agent.yaml` on GitHub. The
route is pre-baked at build time via `generateStaticParams`, so the
GitHub Pages deploy serves one tiny redirect file per slug — partners
can wire it directly into their "Install on Windows" call-to-action and
keep working even if the manifest folder is moved later. The static
deploy itself cannot count requests; per-request install counting
requires an analytics layer downstream of the redirect (Plausible,
Vercel Web Analytics, or a self-hosted endpoint that proxies the hop).
The "Trending this week" panel on the landing page reads
[`marketplace/data/install-counts.json`](./data/install-counts.json) —
seed data today, analytics-layer rollup in production. Smoke-test the
redirect from PowerShell:

```powershell
# Windows 11 + PowerShell — peek at the redirect target without following it.
Invoke-WebRequest -Uri "https://agentmindcloud.github.io/grok-agent/api/install/x-money-companion-dashboard/" -MaximumRedirection 0 -ErrorAction SilentlyContinue | Select-Object StatusCode, Headers
```

---

## Hero cards

Every shipped agent also gets a 1280x640 hero card SVG under
[`marketplace/public/hero-cards/<slug>.svg`](./public/hero-cards/) —
pure SVG with the Spectral v1 charcoal-to-cinnabar diagonal gradient,
the agent's display name, tagline, kind label, the trust-tier corner
ribbon (sourced from `docs/agent-trust-scores.json`), and a parchment
"built on Grok Agent OS" footer. No external image, font, or CSS
reference, so the same file works as an Open Graph / Twitter card image
on any deploy. Regenerate from the repo root after touching any
manifest:

```powershell
# Windows 11 + PowerShell — rebuild every hero card.
python scripts/generate-hero-card.py

# Optional: rebuild a single card by slug.
python scripts/generate-hero-card.py --slug x-money-companion-dashboard

# Drift check (used by CI).
python scripts/generate-hero-card.py --check
```

---

## How dynamic discovery works

`lib/manifests.ts` runs at build time inside the Server Component
`app/page.tsx`. It walks `../templates/super-agents/`,
`../templates/finance/`, and `../templates/creator/`, parses each
`grok-agent.yaml` with `js-yaml`, and normalises the result into an
`Agent` record:

```ts
interface Agent {
  slug: string;
  displayName: string;
  description: string;
  category: 'super-agent' | 'x-money-tool' | 'creator-template';
  tier: 'flagship' | 'lighter' | 'x-money' | 'creator';
  costLimitUsd: number | null;
  tags: string[];
  installCommand: string;
  copyText: string;       // what the Install button copies
  githubFolderUrl: string;
  githubManifestUrl: string;
  // ...
}
```

Because the parsing happens in a Server Component, the result is baked
into the build output. No request-time filesystem access, no API
route, no remote fetch.

To add a new agent to the marketplace:

1. Create a folder at `templates/<bucket>/<slug>/` where `<bucket>` is
   `super-agents`, `finance`, or `creator`.
2. Add a v2.15 `grok-agent.yaml` that validates with
   `python cli/grok-agent.py validate`.
3. Push to `main`. The
   [Deploy Marketplace to GitHub Pages](../.github/workflows/pages.yml)
   action rebuilds and redeploys the site automatically.

---

## Deploy

The repository ships with a CI-driven deploy to **GitHub Pages**:

- `.github/workflows/pages.yml` runs `npm ci && npm run build` on every
  push to `main` (when `marketplace/` or `templates/` changes), uploads
  `marketplace/out/` as the Pages artifact, and runs a smoke test
  against the deployed URL.
- The site goes to `https://agentmindcloud.github.io/grok-agent/`
  thanks to the `basePath: '/grok-agent'` setting in `next.config.js`.

### One-time repo setting

In **Settings → Pages → Source**, choose **GitHub Actions** as the
source. Re-run the workflow once after the setting flips.

### Vercel (alternative, optional)

The same Next.js app deploys to Vercel without changes. If you prefer
Vercel:

1. Visit <https://vercel.com/new> and connect the repo.
2. Set **Root directory** to `marketplace/`.
3. Leave **Framework Preset** on `Next.js`.
4. Set **Node.js Version** to `20.x`.
5. Click **Deploy**.

You'll need to clear `basePath` and `trailingSlash` from
`next.config.js` if you deploy to a Vercel subdomain root (those
settings exist for the GitHub Pages subpath); easiest is to wrap them
behind an env-var check before the cutover.

---

## File map

```
marketplace/
├── package.json                    # Next.js + js-yaml + tsx (prebuild runner)
├── package-lock.json
├── next.config.js                  # output:'export' + basePath:'/grok-agent'
├── tsconfig.json                   # ES2022 target, bundler resolution
├── README.md                       # this file
├── app/
│   ├── layout.tsx                  # Root layout + ScanlineOverlay + CommandPalette
│   ├── page.tsx                    # Dynamic grid + category filter
│   ├── globals.css                 # Cinnabar/parchment + retro-terminal CSS
│   ├── deploy/
│   │   └── page.tsx                # Manifest generator
│   ├── agents/
│   │   └── [slug]/
│   │       └── page.tsx            # Per-agent SSG detail route
│   └── api/
│       └── agents.json/
│           └── route.ts            # Static JSON endpoint
├── components/
│   ├── AgentCard.tsx               # Reusable card with copy-install
│   ├── CommandPalette.tsx          # ⌘K / Ctrl+K palette (cmdk-style)
│   ├── InstallButton.tsx
│   ├── ScanlineOverlay.tsx         # Fixed-position CRT scanline + vignette
│   ├── TelemetryStrip.tsx
│   └── TerminalHero.tsx
├── lib/
│   ├── manifests.ts                # Server-only build-time YAML scanner
│   ├── load-agents.ts              # Helper around manifests.ts
│   ├── manifest.ts                 # Form helpers (slugify, validate)
│   ├── manifests.ts (re-export)
│   ├── github-stats.ts
│   └── types.ts                    # AgentCategory + AgentTier unions, labels
├── scripts/
│   └── build-agents-index.ts       # Prebuild: writes content/agents.json
└── content/
    └── agents.json                 # Generated by prebuild — do not edit
```

---

## License

Apache 2.0. The marketplace is part of the Grok Agent OS open-source
project.
