# 07 · Content Compound Calculator

Category: Analytics

> See your true cumulative reach over 12 months. Not just one-day impressions.

![Status](https://img.shields.io/badge/Status-Live-a3e635?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Models how your posts accumulate impressions beyond their first day. Given posting cadence, average impressions per post, and retention curves, it projects cumulative reach across 52 weeks and lets you see the uplift from posting one more time per week.

## Why it exists

X analytics shows first-day numbers. It hides the compounding. One post keeps earning for weeks. Over 12 months that compounding is usually the *bigger* number, and most creators never see it.

## Tech stack

- Vanilla JS
- Chart.js (CDN)
- No build step, no dependencies

## Install

```bash
cd tools/07-content-compound-calculator
open index.html
```

## Usage

1. Set your posting frequency and average impressions per post
2. Adjust retention sliders to match your own historical decay
3. Toggle "+1 post per week" to see the compounded uplift

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
