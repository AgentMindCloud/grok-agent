<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Grok Agent OS — Marketplace (v0.1 stub)

> **Phase 5 deliverable, P149.** Thin Next.js 14+ marketplace stub for the
> Grok Agent OS platform — featured Super Agents + a "Deploy to X"
> manifest generator that emits a valid `grok-agent.yaml` v2.15 file.
> Built to help xAI and Grok win.

> 🔒 **No telemetry. No backend. No auth.** This stub is 100% client-side
> rendering plus static catalog data. Every byte you type into the deploy
> form stays in your browser tab — the X-share button just opens an X
> compose URL, the download button writes a `.yaml` straight to your disk.

---

## What ships in v0.1

- **Landing page** at `/` — three flagship Super Agents (Living Narrative
  Fabric, Self-Evolving Personal OS, Cross-Reality Action Fabric) with
  "View detail" + "Deploy to X" actions per card.
- **Per-agent detail route** at `/agents/[slug]` — manifest path,
  capabilities, consent gates, install command, and a one-click "Clone
  manifest into the Deploy form" deep-link.
- **Deploy form** at `/deploy` — a tiny client-side Next.js page that
  generates a v2.15 manifest from a small structured form. The form
  validates input live, renders the resulting YAML inline, and offers
  Copy / Download / Share-on-X buttons.

The catalogue lives in [`lib/agents.ts`](./lib/agents.ts); the manifest
generator + slugifier + share-URL builder live in
[`lib/manifest.ts`](./lib/manifest.ts).

---

## Run it on Windows 11 (PowerShell)

```powershell
# 1. Clone the repo if you haven't already.
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\marketplace

# 2. Install the Node.js dependencies.
#    Windows install of Node 20 (one time):
#       winget install OpenJS.NodeJS
npm install

# 3. Run the dev server. Marketplace binds to port 3030 to coexist with
#    the four X Money tools (8501–8504) and the three Super Agents
#    (8501 / 8502 / 8506).
npm run dev

# 4. Open the marketplace in Chrome.
Start-Process "http://localhost:3030"
```

Production build + static-friendly start:

```powershell
npm run build
npm run start
```

The TypeScript build is pure client + static — `output: 'standalone'` in
`next.config.js` so the marketplace deploys cleanly to Vercel, GitHub
Pages (with `next export` after a small config tweak), S3, or Windows
IIS without a server runtime requirement.

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
│   ├── page.tsx            # Landing page — featured agents grid
│   ├── globals.css         # Cinnabar/parchment palette per CLAUDE.md
│   ├── deploy/
│   │   └── page.tsx        # Deploy-to-X manifest generator
│   └── agents/
│       └── [slug]/
│           └── page.tsx    # Per-agent detail route (statically rendered)
└── lib/
    ├── agents.ts           # Featured-agent catalogue (3 Super Agents)
    └── manifest.ts         # Pure-TS v2.15 manifest generator + helpers
```

---

## How "Deploy to X" works

The `/deploy` route uses a client-only React form. Every keystroke
re-runs `validateDeployInput(...)` from `lib/manifest.ts` and (when
valid) regenerates the YAML via `generateManifestYaml(...)`. The
manifest:

- Carries the Apache-2.0 + xAI-ally header at the top.
- Uses `version: "2.15"` and a `kind` from the canonical 8-kind list
  (`agent`, `finance-dashboard`, `alpha-engine`, `creator-payout-optimizer`,
  `vision-analyzer`, `super-agent`, `x-native`, `creator-template`).
- Emits `safety.human_in_the_loop` defaults (60-second timeout) and
  `safety.cost_limits` defaults ($0.50 per session / $2.00 per day).
- Lists every consent gate the user typed in `constitution.consent_gates`.
- Optionally enables `real_time_x` with reply-only + mention triggers
  when the user ticks the checkbox.

After generation, the user can:

1. **Copy YAML** — copies the manifest to the clipboard.
2. **Download `grok-agent.yaml`** — writes the file straight to disk.
3. **Share on X** — opens an X compose URL that includes a one-line
   install hint. The agent doesn't post for the user; the user posts
   for themselves.

The manifest is then expected to be validated locally with the canonical
CLI before shipping:

```powershell
python ..\cli\grok-agent.py validate grok-agent.yaml
```

---

## Why is this a stub?

The full marketplace plan (Phase 5+) is bigger:

- v0.2 — list every creator template (20+ ready-to-use templates from
  `templates/creator/`) alongside the three Super Agents.
- v0.3 — anonymous, opt-in install analytics (Article-VII-compliant).
- v0.4 — community submissions via PR with the same v2.15 + Constitution
  validator gating merges.

This v0.1 stub is the smallest thing that lets a creator browse the
canonical Super Agents, generate a manifest, and post the result to X.
It has zero backend, zero auth, zero secrets — and that's deliberate.

---

## License

Apache 2.0. Built for xAI, Grok and the whole community on X. We're
ecosystem allies — this marketplace exists to make Grok the obvious,
default platform for deploying agents on X, not to compete with it.

---

> Built to help xAI and Grok win. 🚀
