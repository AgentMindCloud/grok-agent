# Brand

> The visual system for `x-platform-toolkit` and every tool in the grok-install family.

The source of truth for these tokens is [`shared/ui-kit/tokens.css`](../shared/ui-kit/tokens.css). This doc explains *how* and *why* each token is used.

## Palette

Pure black backgrounds, neon cyan/purple/magenta accents. Never a light theme.

| Token | Hex | Usage |
|---|---|---|
| `--bg-pure` | `#000000` | Page background. No exceptions. |
| `--bg-soft` | `#0a0a0f` | Header bars, subtle surfaces |
| `--bg-card` | `#111118` | Cards, panels, inputs in context |
| `--bg-elevated` | `#16161f` | Hover states, emphasized rows |
| `--border-subtle` | `#1f1f2e` | Default borders |
| `--border-glow` | `rgba(34, 211, 238, 0.2)` | Focused / active borders |
| `--neon-cyan` | `#22d3ee` | Primary accent, primary actions |
| `--neon-purple` | `#a855f7` | Secondary accent, family color |
| `--neon-magenta` | `#ec4899` | Highlights, "hot" actions |
| `--neon-lime` | `#a3e635` | Success, winning rows, "live" |
| `--neon-amber` | `#fbbf24` | Warning, caution |
| `--text-primary` | `#ffffff` | Body text |
| `--text-secondary` | `#a1a1aa` | Secondary copy |
| `--text-muted` | `#52525b` | Footer, metadata |

### Swatches

| | Cyan | Purple | Magenta | Lime | Amber |
|---|---|---|---|---|---|
| <svg width="40" height="40"><rect width="40" height="40" fill="#22d3ee"/></svg> | <svg width="40" height="40"><rect width="40" height="40" fill="#a855f7"/></svg> | <svg width="40" height="40"><rect width="40" height="40" fill="#ec4899"/></svg> | <svg width="40" height="40"><rect width="40" height="40" fill="#a3e635"/></svg> | <svg width="40" height="40"><rect width="40" height="40" fill="#fbbf24"/></svg> | |

### Gradients

- `--gradient-primary` — `linear-gradient(135deg, #22d3ee → #a855f7)` — use for titles, logos, big numbers
- `--gradient-magenta` — `linear-gradient(135deg, #a855f7 → #ec4899)` — secondary emphasis
- `--gradient-warm` — `linear-gradient(135deg, #ec4899 → #fbbf24)` — heat / risk visualizations

## Typography

- **Display / headings:** Space Grotesk (600, 700)
- **Mono / code / badges / UI labels:** JetBrains Mono (400, 500, 700)
- **Body:** Inter (400, 500)

Load from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
```

### Scale

| Element | Size | Family | Weight |
|---|---|---|---|
| h1 | 48px | Space Grotesk | 700 |
| h2 | 32px | Space Grotesk | 700 |
| h3 | 22px | Space Grotesk | 700 |
| body | 15px | Inter | 400 |
| mono | 14px | JetBrains Mono | 500 |
| badge | 11px | JetBrains Mono | 600 / uppercase / letter-spacing 0.08em |

## Effects

- Glow on focused/active elements: `box-shadow: 0 0 20px rgba(34, 211, 238, 0.15);`
- Gradient text on titles: see `.gradient-text`
- Border-radius: `4px` sm, `6px` md, `8px` lg — **never pill-shaped**
- Subtle scanline overlay on hero sections (`.scanlines` utility)
- All hover transitions: `150ms ease`

## Iconography

- **No emojis** in UI copy, tool docs, commit messages, issue templates, or anywhere outside the root `README.md`.
- The one exception: the root `README.md` may use emojis in section headers only (e.g. `### 📊 Analytics`), as visual wayfinding for GitHub's rendered landing page. Body copy, tables, and code blocks stay emoji-free.
- Use SVG icons or geometric unicode: `▲ ▼ ◆ ◇ ● ○ → ← ↗ ⚡ ⌘ §`
- Status indicators: small SVG dots (8px) with neon fill + glow

## Usage examples

### Brand bar

```html
<div class="brand-bar">
  <div class="brand-mark">
    <span class="icon">X</span>
    <span class="name">x-platform-toolkit</span>
  </div>
  <div class="brand-mark">
    <span class="badge mono">04</span>
    <span class="text-muted mono">grok-install family</span>
  </div>
</div>
```

### Gradient title

```html
<h1 class="gradient-text">Pre-Post Virality Scorer</h1>
```

### Badge family

```html
<span class="badge">Live</span>
<span class="badge badge-purple">AI</span>
<span class="badge badge-magenta">Hot</span>
<span class="badge badge-lime">Passing</span>
```

## Do / don't

**Do**
- Pure black backgrounds on every page
- Neon accents on focused or "live" elements only — accents are precious
- Mono for numbers, labels, badges

**Don't**
- Light themes, off-white backgrounds, or low-contrast grays
- Rounded pill badges, rounded buttons > 8px
- Bootstrap, Material Design, or recognizable framework aesthetics
- Emojis in UI copy, tool docs, commit messages, issue templates, or root README body (section headers only are allowed)

---

Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit). Apache 2.0.
