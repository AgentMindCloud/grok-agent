# ui-kit

> Shared design tokens, components, and shell template for every tool in `x-platform-toolkit`.

## What's here

- `tokens.css` — CSS custom properties (colors, typography, spacing, gradients, shadows)
- `components.css` — Component primitives (brand-bar, buttons, cards, badges, inputs, tables)
- `shell.html` — HTML skeleton every LIVE tool copies and customizes

## Design system

See [docs/BRAND.md](../../docs/BRAND.md) for full palette, typography, and usage guidelines.

## Usage

LIVE tools **inline** `tokens.css` and `components.css` into their single `index.html` for portability. The shell template in `shell.html` shows the canonical header, main, and footer structure.

Backend-driven tools should instead link to the shared CSS files from a static server.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
