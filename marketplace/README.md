<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — Marketplace (v0.3)

> **Phase 5 deliverable, P155.** The marketplace landing page is now
> generated dynamically from the actual `grok-agent.yaml` v2.15
> manifests on disk. No hand-maintained agent list. Add a new manifest
> under `templates/super-agents/` or `templates/finance/` and it shows
> up on the next build.

> 🔒 **No telemetry. No backend. No auth.** All rendering is local +
> static. The Install button on each card copies the install one-liner
> to your clipboard so you can paste it on X.

---

## What ships in v0.3

- **Dynamic catalogue** at `/` — every Super Agent and X Money tool
  with a manifest in this repo, scanned at build time. The current
  build picks up **11 agents**: 3 flagship + 4 lighter Super Agents
  and 4 X Money tools.
- **Category filter** — chip row at the top of the grid filters
  between *Super Agents* and *X Money Tools* via URL query params
  (server-rendered, no JavaScript needed).
- **Install on each card** — copies a ready-to-paste primer
  (`grok install this` plus a manifest link) directly to the
  clipboard.
- **Per-agent detail route** at `/agents/[slug]` — manifest path,
  capabilities, and consent gates pulled from the same dynamic
  catalogue.
- **Deploy form** at `/deploy` — client-side React form that emits a
  v2.15 manifest for any of the eight kinds.

The manifest scanner lives in [`lib/manifests.ts`](./lib/manifests.ts).
The reusable card lives in
[`components/AgentCard.tsx`](./components/AgentCard.tsx). The legacy
adapter that exposes the scanned data as `FeaturedAgent[]` for the
detail page lives in [`lib/agents.ts`](./lib/agents.ts).

---

## Run it on Windows 11 (PowerShell)

```powershell
# 1. Clone the repo if you haven't already.
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\marketplace

# 2. Install Node.js 20 (one time).
winget install OpenJS.NodeJS

# 3. Install dependencies (now includes js-yaml for manifest parsing).
npm install

# 4. Run the dev server. Marketplace binds to port 3030.
npm run dev

# 5. Open the marketplace in Chrome.
Start-Process "http://localhost:3030"
```

Production build + start:

```powershell
npm run build
npm run start

# Optional: type-only check, runs no code.
npm run typecheck
```

---

## How dynamic discovery works

`lib/manifests.ts` runs at build time inside the Server Component
`app/page.tsx`. It walks `../templates/super-agents/` and
`../templates/finance/`, parses each `grok-agent.yaml` with `js-yaml`,
and normalises the result into an `Agent` record:

```ts
interface Agent {
  slug: string;
  displayName: string;
  description: string;
  category: 'super-agent' | 'x-money-tool';
  tier: 'flagship' | 'lighter' | 'x-money';
  costLimitUsd: number | null;
  tags: string[];
  installCommand: string;
  copyText: string;       // what the Install button copies
  githubFolderUrl: string;
  githubManifestUrl: string;
  // …
}
```

Because the parsing happens in a Server Component, the result is baked
into the build output. No request-time filesystem access, no API
route, no remote fetch.

To add a new agent to the marketplace:

1. Create a folder at `templates/super-agents/<slug>/` or
   `templates/finance/<slug>/`.
2. Add a v2.15 `grok-agent.yaml` that validates with
   `python cli/grok-agent.py validate`.
3. Re-run `npm run build`. The new agent appears in the grid
   automatically.

---

## Deploy to Vercel (recommended, ~3 minutes)

Vercel speaks Next.js natively. Set the project's **Root Directory**
to `marketplace/` so Vercel only builds the subfolder. The scanner
walks `../templates/` from inside `marketplace/`, which works because
Vercel clones the entire repository.

### Option A — Vercel CLI (PowerShell)

```powershell
# 1. Install the Vercel CLI globally (one time).
npm install -g vercel

# 2. From the marketplace folder, log in + deploy.
cd grok-agent\marketplace
vercel login
vercel --prod
```

### Option B — Vercel dashboard

1. Visit <https://vercel.com/new> and connect the
   `AgentMindCloud/grok-agent` GitHub repo.
2. Set **Root directory** to `marketplace/`.
3. Leave **Framework Preset** on `Next.js`.
4. Set **Node.js Version** to `20.x`.
5. Click **Deploy**.

### Custom domain (optional)

Once the project is live, point any domain you own at Vercel via the
project's **Settings → Domains** tab.

---

## File map

```
marketplace/
├── package.json            # Adds js-yaml + @types/js-yaml in v0.3
├── next.config.js          # Strict mode, typed routes, no telemetry
├── tsconfig.json           # ES2022 target, bundler module resolution
├── README.md               # this file
├── app/
│   ├── layout.tsx          # Root layout + header banner + footer
│   ├── page.tsx            # NEW: dynamic grid + category filter
│   ├── globals.css         # Cinnabar/parchment palette + dark mode
│   ├── _components/
│   │   └── AgentBrowser.tsx # legacy interactive search/filter
│   ├── deploy/
│   │   └── page.tsx        # Manifest generator
│   └── agents/
│       └── [slug]/
│           └── page.tsx    # Per-agent detail route
├── components/
│   └── AgentCard.tsx       # NEW: reusable card with copy-install
└── lib/
    ├── manifests.ts        # NEW: build-time YAML scanner
    ├── agents.ts           # FeaturedAgent adapter for legacy routes
    └── manifest.ts         # Form helpers (slugify, validate, etc.)
```

---

## License

Apache 2.0. The marketplace is part of the Grok Agent OS open-source
project.
