# 17 · Post Necromancer

Category: AI Automation

> Your old posts had good ideas. Reincarnate them with today's vocabulary.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Surfaces your top 20 highest-engagement-per-impression posts from 90 to 365 days ago, then uses Grok to rewrite each one in three variants using current trending hooks and vocabulary. You approve the rewrites you like and queue them for manual scheduling — no auto-posting.

## Why it exists

Your best ideas from last year still work. The language, the hooks, and the platform conventions that carried them do not. Grok sees what is trending on X today; you see what worked for you historically. This tool joins those two signals so high-performing evergreen ideas keep earning, without feeling like recycled content.

## Tech stack

- Node.js backend
- X API v2 for historical posts and engagement metrics
- Grok API for rewriting (Grok's live X access gives it current vocabulary)
- Firestore for the approval queue
- Simple React approval UI

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
