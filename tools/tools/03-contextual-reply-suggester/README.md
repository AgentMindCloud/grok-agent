# 03 · Contextual Reply Suggester

Category: AI Writing

> Reply suggestions ranked by likelihood of follower gain.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Contextual Reply Suggester takes a tweet URL or pasted text, pulls the author's recent context, and generates five reply variants in different tones. Each reply is scored by predicted virality based on hook strength, length, and alignment with the original thread's angle.

## Why it exists

Replying under bigger accounts is the fastest organic growth lever on X, but most creators reply badly. Generic agreement, late timing, wrong tone, or an obvious self-promotion kills the post before it gets seen. This tool writes reply candidates that actually fit the conversation and ranks them so the user doesn't have to guess which one to send.

## Tech stack

- Single-page web app or Chrome MV3 extension
- Node.js backend for Grok API key handling
- X API v2 for original tweet and author profile lookup
- Firestore for usage logs and rate limiting
- Hosted on Render + Hostinger

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
