<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — Marketplace (v0.2)

> **Phase 5 deliverable, P150.** Polished Next.js 14+ marketplace with
> client-side search + kind filters, an improved manifest generator
> covering all eight v2.15 kinds, and clear deploy guides for Vercel +
> GitHub Pages. Built to help xAI and Grok win.

> 🔒 **No telemetry. No backend. No auth.** This release is 100%
> static + client-side rendering. Every byte you type into the deploy
> form stays in your browser tab — the X-share button just opens an X
> compose URL, the download button writes a `.yaml` straight to your
> disk.

---

## What ships in v0.2

- **Landing page** at `/` — hero strip with the three flagship Super
  Agents plus a searchable, filterable browser of every catalogued
  agent (Super Agents + featured creator templates + an x-native).
- **Per-agent detail route** at `/agents/[slug]` — manifest path,
  capabilities, consent gates, install command, and a one-click
  "Clone manifest into the Deploy form" deep-link. Statically
  generated for every entry in the catalogue.
- **Deploy form** at `/deploy` — client-side React form that emits a
  `grok-agent.yaml` manifest valid against the v2.15 schema for **all
  eight** supported kinds (`agent`, `finance-dashboard`, `alpha-engine`,
  `creator-payout-optimizer`, `vision-analyzer`, `super-agent`,
  `x-native`, `creator-template`). Per-field inline validation, kind-
  aware helper hints, copy-success toast, attribution-labelled X share.
- **Polished styling** — Cinnabar/parchment palette with dark-mode
  support via `prefers-color-scheme`, responsive grid (1/2/3 columns),
  filter chips with active states, accessible focus rings.

The catalogue lives in [`lib/agents.ts`](./lib/agents.ts); the manifest
generator + slugifier + share-URL builder lives in
[`lib/manifest.ts`](./lib/manifest.ts). The interactive search +
filter-chip browser lives in [`app/_components/AgentBrowser.tsx`](./app/_components/AgentBrowser.tsx).

---

## Run it on Windows 11 (PowerShell)

```powershell
# 1. Clone the repo if you haven't already.
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\marketplace

# 2. Install Node.js 20 (one time).
winget install OpenJS.NodeJS

# 3. Install dependencies.
npm install

# 4. Run the dev server. Marketplace binds to port 3030 to coexist with
#    the four X Money tools (8501–8504) and the three Super Agents
#    (8501 / 8502 / 8506).
npm run dev

# 5. Open the marketplace in Chrome.
Start-Process "http://localhost:3030"
```

Production build + static-friendly start:

```powershell
npm run build
npm run start

# Optional: type-only check, runs no code.
npm run typecheck
```

---

## Deploy to Vercel (recommended, ~3 minutes)

Vercel speaks Next.js natively. The marketplace deploys with **zero
config** because `next.config.js` already sets `output: 'standalone'`.

### Option A — Vercel CLI (PowerShell)

```powershell
# 1. Install the Vercel CLI globally (one time).
npm install -g vercel

# 2. From the marketplace folder, log in + deploy.
cd grok-agent\marketplace
vercel login
vercel --prod

# Vercel auto-detects:
#   - Framework: Next.js 14
#   - Build command: npm run build
#   - Output directory: .next/standalone
#   - Node runtime: 20
```

### Option B — Vercel dashboard (web UI)

1. Visit <https://vercel.com/new> and connect the
   `AgentMindCloud/grok-agent` GitHub repo.
2. Set **Root directory** to `marketplace/` so Vercel builds only the
   subfolder.
3. Leave **Framework Preset** on `Next.js`. Vercel will pick up
   `package.json` + `next.config.js` automatically.
4. Set **Node.js Version** to `20.x`. The `engines.node` field in
   `package.json` already pins this.
5. Click **Deploy**. The first build takes ~90 seconds.

### Custom domain (optional)

Once the project is live, point `marketplace.grok-agent.dev` (or any
domain you own) at Vercel via the project's **Settings → Domains** tab.
Vercel issues a free Let's Encrypt cert automatically.

---

## Deploy to GitHub Pages (free, ~5 minutes)

GitHub Pages serves only static files, so we use Next.js' built-in
static export and host the resulting `out/` folder under
`https://agentmindcloud.github.io/grok-agent/marketplace/`.

```powershell
# 1. From the marketplace folder, build a static export.
cd grok-agent\marketplace

# 2. Tell Next.js to emit a static bundle. The `output: 'export'`
#    flag must be set TEMPORARILY for static hosts; the canonical
#    next.config.js uses 'standalone' so Vercel works out of the box.
$env:NEXT_OUTPUT_MODE = "export"
npm run build

# 3. Push the resulting `out/` folder to the gh-pages branch.
#    `gh-pages` is a tiny dev dependency that wraps `git worktree`.
npm install --save-dev gh-pages
npx gh-pages --dist out --branch gh-pages

# 4. In your repo's GitHub UI, go to Settings → Pages and select
#    "Deploy from branch: gh-pages / (root)".
```

> ⚠️ The dynamic `[slug]` route is statically generated for every entry
> in the catalogue (see `generateStaticParams` in
> `app/agents/[slug]/page.tsx`), so there's no server runtime needed.
> If you add a new featured agent, re-run the export + re-push.

---

## Deploy elsewhere

Because v0.2 is fully static + client-side, any of these work too:

| Target | Notes |
|---|---|
| **Netlify** | Same as Vercel — zero-config Next.js detection. |
| **Cloudflare Pages** | Drop the `out/` folder; set Node 20 in build settings. |
| **Windows IIS** | Build with `output: 'export'`, copy `out/` to the IIS site root. |
| **AWS S3 + CloudFront** | Static export, sync to S3, point CloudFront at it. |
| **Local Windows** | `npm run build && npm run start` — binds to port 3030. |

---

## File map

```
marketplace/
├── package.json            # Next.js 14.2 + TypeScript 5.5 + React 18.3
├── next.config.js          # Strict mode, typed routes, no telemetry
├── tsconfig.json           # ES2022 target, bundler module resolution
├── .gitignore              # node_modules, .next/, .env, IDE crud
├── README.md               # this file
├── app/
│   ├── layout.tsx          # Root layout + header banner + footer
│   ├── page.tsx            # Landing — hero + Featured strip + Browser
│   ├── globals.css         # Cinnabar/parchment palette + dark mode
│   ├── _components/
│   │   └── AgentBrowser.tsx # Client-only search + kind-filter chips
│   ├── deploy/
│   │   └── page.tsx        # Manifest generator with per-field errors
│   └── agents/
│       └── [slug]/
│           └── page.tsx    # Per-agent detail route (statically rendered)
└── lib/
    ├── agents.ts           # Catalogue (3 Super Agents + 6 featured)
    └── manifest.ts         # Pure-TS v2.15 generator + helpers + KIND_HELPER
```

---

## How "Deploy to X" works

The `/deploy` route uses a client-only React form. Every keystroke
re-runs `validateDeployInput(...)` from `lib/manifest.ts` and (when
valid) regenerates the YAML via `generateManifestYaml(...)`. The
manifest:

- Carries the Apache-2.0 + xAI-ally header at the top.
- Uses `version: "2.15"` and a `kind` from the canonical 8-kind list.
- Emits `safety.human_in_the_loop` defaults (60-second timeout) and
  `safety.cost_limits` defaults ($0.50/session / $2.00/day).
- Auto-flips `not_financial_advice: true` for the four finance-shaped
  kinds and `not_tax_advice: true` for the two tax-shaped kinds.
- Auto-sets `grok.vision: true` for `vision-analyzer` (required by the
  schema).
- Lists every consent gate the user typed in
  `constitution.consent_gates`.
- Always declares ≥4 `constitution.rules` (kind-aware, augmented for
  finance, super-agent, x-native, and creator-template).
- Optionally enables `real_time_x` with reply-only + mention triggers
  when the user ticks the checkbox.

After generation, the user can:

1. **Copy YAML** — copies the manifest to the clipboard with a
   success toast.
2. **Download `grok-agent.yaml`** — writes the file straight to disk.
3. **Share on X** — opens an X compose URL prefixed with the agent
   slug, the install one-liner, and a "Manifest generated with the
   Grok Agent OS marketplace" attribution line.

The manifest is then expected to be validated locally with the
canonical CLI before shipping:

```powershell
python ..\cli\grok-agent.py validate grok-agent.yaml
```

---

## Roadmap

- **v0.1 (P149)** — featured Super Agents + manifest generator.
- **v0.2 (P150, this release)** — search, filters, polished styling,
  broader kind coverage, deploy guide, X attribution.
- **v0.3** — anonymous, opt-in install analytics
  (Article-VII-compliant).
- **v0.4** — community submissions via PR with the same v2.15 +
  Constitution validator gating merges.

---

## License

Apache 2.0. Built for xAI, Grok and the whole community on X. We're
ecosystem allies — this marketplace exists to make Grok the obvious,
default platform for deploying agents on X, not to compete with it.

---

> Built to help xAI and Grok win. 🚀
