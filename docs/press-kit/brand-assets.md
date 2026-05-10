<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Brand assets — Spectral v1

The Grok Agent OS visual identity is **Spectral v1**: a four-color palette, a single typographic mood, and a small set of badge embeds. Everything here is releasable under Apache 2.0.

---

## Palette swatches

| Role | Name | Hex | Usage |
|---|---|---|---|
| Background / ink | Charcoal | `#0A0A0A` | Page background on dark surfaces; primary text on light surfaces. |
| Accent / brand | Cinnabar | `#FF1E70` | Primary call-to-action, brand glyphs, hero stripe, A-tier trust crown. |
| Surface / paper | Parchment | `#F4ECDA` | Page background on light surfaces; card stock on dark surfaces. |
| Highlight / signal | Teal | `#00E0D5` | Secondary accent, link underline, scanner-OK glyphs. |

CSS custom-property reference (drop straight into any stylesheet):

```css
:root {
  --spectral-charcoal:  #0A0A0A;
  --spectral-cinnabar:  #FF1E70;
  --spectral-parchment: #F4ECDA;
  --spectral-teal:      #00E0D5;
}
```

The marketplace ships a CRT-scanline overlay on top of these four; the overlay is a CSS gradient and is not part of the brand palette.

---

## Logo usage rules

The wordmark is `Grok Agent OS` set in a monospaced display face (the marketplace uses `JetBrains Mono`). The first-pass mark places the wordmark in cinnabar on charcoal, with the ecosystem-ally tagline in parchment beneath it at half the wordmark size.

**Do:**

- Use the wordmark exactly as styled — no abbreviation, no rearrangement.
- Maintain at least 1x wordmark-height of clear space on every side.
- Pair with the cinnabar/parchment palette on dark backgrounds, charcoal/parchment on light backgrounds.

**Do not:**

- Combine the Grok Agent OS wordmark with any official xAI, X, or Grok mark in a way that suggests endorsement. The project is an ecosystem ally, not a partnership product (yet).
- Recolor the wordmark outside the Spectral v1 palette.
- Add drop shadows, gradients, or 3D effects.

---

## Badge embed snippets

Every shipped agent has a trust badge available at `https://agentmindcloud.github.io/grok-agent/api/badge/<slug>.svg`.

**Markdown:**

```markdown
[![Grok Agent OS trust](https://agentmindcloud.github.io/grok-agent/api/badge/x-money-companion-dashboard.svg)](https://github.com/AgentMindCloud/grok-agent)
```

**HTML:**

```html
<a href="https://github.com/AgentMindCloud/grok-agent">
  <img src="https://agentmindcloud.github.io/grok-agent/api/badge/x-money-companion-dashboard.svg"
       alt="Grok Agent OS trust badge — x-money-companion-dashboard" />
</a>
```

The license badge is the standard Shields.io Apache 2.0 badge:

```markdown
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/AgentMindCloud/grok-agent/blob/main/LICENSE)
```

---

## Visual mood

Spectral v1 deliberately echoes early-1980s terminal aesthetics — Apple IIe meets cinnabar. CRT scanlines, monospaced display type, sharp 1px borders, no rounded card corners larger than 4px. The mood is concrete and slightly defiant, matching the project voice: open source, Windows-first, ecosystem-ally, no SaaS lock-in.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
