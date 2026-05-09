<!--
  Copyright 2026 AgentMindCloud
  Licensed under the Apache License, Version 2.0
  http://www.apache.org/licenses/LICENSE-2.0
-->

# Browser extension icons

> Built for xAI, X, Grok and the ecosystem community.

This folder ships SVG sources only. Chrome MV3 manifests do **not** accept
SVG icons — the `icons` block in `../manifest.json` references PNG paths
(`icon-16.png`, `icon-32.png`, `icon-48.png`, `icon-128.png`) that must be
generated locally before packing the `.crx`.

## Brand

- Background: `#1A1A1A` (charcoal)
- Mark: `#E34234` (cinnabar)
- Accent: `#F4E9D8` (parchment) — Spectral v1 / Residual Frequencies palette

## Source files

| File             | Purpose                                  |
|------------------|------------------------------------------|
| `icon.svg`       | 128×128 master, full cog + G composition |
| `icon-128.svg`   | 128×128 export-ready variant             |
| `icon-48.svg`    | 48×48 export-ready variant               |
| `icon-32.svg`    | 32×32 export-ready variant (heavier stroke for readability) |
| `icon-16.svg`    | 16×16 export-ready variant (G only, no cog) |

## One-time PNG conversion (Windows + ImageMagick)

PowerShell, from the repo root:

```powershell
cd extensions\browser\icons
magick icon-16.svg  -background none -resize 16x16   icon-16.png
magick icon-32.svg  -background none -resize 32x32   icon-32.png
magick icon-48.svg  -background none -resize 48x48   icon-48.png
magick icon-128.svg -background none -resize 128x128 icon-128.png
```

If you do not have ImageMagick, install it once with:

```powershell
winget install ImageMagick.ImageMagick
```

After conversion, `Get-ChildItem *.png` should list all four PNGs. Commit
the PNG outputs alongside the SVG sources before publishing the extension.

## Why SVG sources are kept in-repo

- The SVGs are the canonical brand artifact — PNGs are derived.
- Re-rendering at new sizes (e.g. a future 256×256 store listing) is a
  one-line ImageMagick call.
- SVG diffs are reviewable in PRs; PNG diffs are opaque.
