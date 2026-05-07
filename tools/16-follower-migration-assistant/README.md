# 16 · Follower Migration Assistant

Category: Analytics

> Pivoting your account? See who'll stay and who'll leave.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Analyzes your current follower base against a proposed new account positioning and predicts which followers will stay engaged, which will drift, and which will unfollow. It then suggests pivot-announcement post angles designed to maximize retention, and estimates your carried-over audience size.

## Why it exists

Every creator eventually pivots — from dev to founder, from coach to investor, from generalist to niche. Pivots feel risky because the downside (losing a built audience) is invisible until it happens. This tool makes the downside visible before the pivot, letting creators choose between a full swap, a gradual bridge, or two separate accounts with data behind the decision.

## Tech stack

- Node.js backend
- X API v2 for follower bios and recent posts
- Grok API for relevance scoring per follower
- Firestore for batched analysis results
- React dashboard with retention heatmap

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
