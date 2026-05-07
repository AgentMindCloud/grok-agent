# 05 · Pinned Post A/B Rotator

Category: Analytics

> Rotate your pinned post on a schedule. Find your best converter.

![Status](https://img.shields.io/badge/Status-Live-a3e635?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Manages up to 5 candidate pinned posts, schedules rotations on a chosen interval, and tracks conversion (follows per 1k impressions) per candidate so a winner emerges.

## Why it exists

Your pinned post is your highest-leverage real estate on X. Most people set it once and forget. A systematic rotation beats a guessed winner every time.

## Tech stack

- Vanilla JS + LocalStorage
- No dependencies, no build step

## Install

```bash
cd tools/05-pinned-post-ab-rotator
open index.html
```

## Usage

1. Add candidate posts (up to 5)
2. Set an interval (24h / 48h / 72h / weekly)
3. Mark one candidate active and pin it on X manually
4. When the countdown hits zero, click ROTATE NOW and log the previous candidate's metrics
5. Let the table sort itself — the top row is your winner

## Note

This tool tracks and recommends. You manually update your pinned post on X each rotation.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
