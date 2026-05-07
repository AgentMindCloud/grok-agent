# 12 · Controversy Detector

Category: AI Writing

> Flag risky phrasing before you post. Choose your battles.

![Status](https://img.shields.io/badge/Status-Live-a3e635?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Scans your draft post against four user-defined keyword categories (tribal markers, charged terms, absolutes, callouts), scores its risk 0–100, and highlights every match inline. Two modes: Audit (educational, shows everything) and Creator (warning-only, shows only categories above threshold).

## Why it exists

Most posts that blow up in a bad way do so for predictable reasons: tribal framing, absolutes, or callouts that make readers defensive. This tool names the pattern before you hit post.

## Important: bring your own keywords

This tool ships with **empty keyword lists**. You add the terms that matter in your niche. Your lists persist locally.

This design is deliberate. Every niche has its own risk vocabulary — a tech audience reacts to different language than a finance audience or a parenting audience. A baked-in glossary would be wrong for 99% of users. The framework is the value; the vocabulary is yours.

## Tech stack

- Vanilla JS + LocalStorage
- No dependencies, no build step

## Install

```bash
cd tools/12-controversy-detector
open index.html
```

## Usage

1. Open the tool
2. Click "Edit keywords" on each category and paste your risk vocabulary (comma-separated)
3. Paste your draft post
4. Watch the risk meter and the inline highlights
5. Apply the suggested rephrases for any category that scored high

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
