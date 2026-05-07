# 11 · Ghostwriter Mode with Memory

Category: AI Writing

> AI writer that learns your voice from your last 500 posts.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Ghostwriter Mode with Memory ingests your last 500 X posts and builds a durable voice profile: vocabulary frequencies, hook patterns, sentence rhythm, recurring themes, and emoji usage. When you give it a topic, it generates posts that sound like you wrote them, not like generic AI output.

## Why it exists

Every AI writing tool on X — Hypefury, Tweet Hunter, Tweetdeck AI — uses the same generic templates and the same LLM output voice. Readers learn to recognize it in a glance and scroll past. A ghostwriter is only useful if it sounds like the person it writes for. This tool solves that by treating your own post archive as the training signal and regenerating the voice profile weekly so quality compounds over time.

## Tech stack

- Node.js backend with Grok API integration (Claude API as fallback)
- Firestore for durable voice profiles, refreshed weekly
- Chat-style UI for prompt and regenerate flow
- X API v2 for post ingestion
- Render for backend, Hostinger for frontend

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
