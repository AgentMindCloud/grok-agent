# Architecture

## Monorepo conventions

```
x-platform-toolkit/
├── shared/        # Reusable code across tools
├── tools/         # One folder per tool, numbered 01-20
├── docs/          # Conceptual docs
├── assets/        # Brand assets (banner, icon)
└── README.md      # The showcase entry point
```

## Tool folder conventions

Every tool folder is self-contained:

- `README.md` — required, follows the shared template
- `SPEC.md` — required for `Spec'd` status tools only. Live tools document their design inline in `README.md`.
- `index.html` — for single-file frontend tools (LIVE)
- `package.json` + `src/` — for Node-based tools
- `.env.example` — for any tool requiring API keys

## Tool status lifecycle

`Spec'd` → `Beta` → `Live`

- **Spec'd:** Design complete, no code yet. Ship the SPEC.md.
- **Beta:** Functional but rough. README warns of limitations.
- **Live:** Production-ready. Tested. Documented.

## Shared utilities

- `shared/ui-kit/` — Design tokens, components.css, shell.html template
- `shared/x-api-client/` — X API v2 wrapper (Node)
- `shared/grok-client/` — xAI Grok API wrapper (Node)

LIVE tools may inline shared CSS for single-file portability. Backend tools should import shared utilities.

## Deployment targets

- **Single-file HTML tools:** Open locally or host on any static server (Hostinger, Netlify, Vercel, GitHub Pages)
- **Node backends:** Render (recommended) or any Node host
- **Firebase:** Auth, Firestore, Storage where needed

## Adding a new tool

1. Create folder: `tools/NN-tool-name/`
2. Add README from template
3. Add SPEC.md if not yet built
4. Update root README table
5. Update CHANGELOG.md

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
