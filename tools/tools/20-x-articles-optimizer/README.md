# 20 · X Articles Optimizer

Category: AI Writing

> Your best thread is a half-written X Article. Let's complete it.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Converts a thread (pasted content or URL) into a properly structured X Article: title, subheadings, inline media references, and a conclusion — formatted for X's rich-text Article composer. You paste the output straight into X and publish.

## Why it exists

X is investing heavily in long-form Articles and actively boosting accounts that publish them, yet most creators still write only threads. The format gap is artificial: a strong thread already has the scaffolding of an article — it just needs a title, section breaks, and connective prose. This tool closes that gap in minutes and unlocks a format that X's algorithm currently favors.

## Tech stack

- Single-page web app (Vite + React)
- Optional Grok API for polish and restructuring
- Optional X API v2 for thread fetch by URL
- Tailwind UI with side-by-side thread/article view

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
