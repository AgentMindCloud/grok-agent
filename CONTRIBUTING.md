# Contributing

Thanks for your interest in `x-platform-toolkit`.

## Quick rules

- One tool per PR
- Follow the design tokens in `shared/ui-kit/tokens.css` — no design drift
- Match the README template in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Apache 2.0 only — no GPL or restricted code
- ToS-respecting only — no scraping, no fake engagement, no auto-DMs

## Adding a new tool

1. Open an issue using the `tool-request` template
2. Get a green light from a maintainer
3. Fork and create folder: `tools/NN-tool-name/`
4. Build per spec, add README + SPEC.md
5. Update root README table + CHANGELOG.md
6. Open PR

## Improving an existing tool

- Bug fixes: open issue with reproduction, then PR
- Features: discuss in issue first
- Visual changes: must align with `docs/BRAND.md`

## Code style

- Frontend: vanilla JS preferred, Tailwind CDN allowed
- Backend: Node.js >=18, ESM or CJS both fine
- No Bootstrap, no jQuery, no Material Design
- No emojis in UI or commit messages

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
