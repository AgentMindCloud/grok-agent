# 13 · Thread-to-Newsletter Auto-Converter

Category: Automation

> Your thread is half a newsletter. Let's finish the job.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Takes any X thread and restructures it into a publication-ready newsletter. It groups related tweets into sections, writes a hook intro, adds a closing CTA, and either exports Markdown or pushes directly to Beehiiv or Substack via their APIs.

## Why it exists

Creators spend hours on a thread, then stare at a blank newsletter editor that same week. The thread already contains the ideas, the voice, and the reader-tested structure — it just needs reformatting for long-form. This tool closes the gap between "thread went off" and "newsletter shipped" so creators compound a single piece of writing across two channels without duplicating work.

## Tech stack

- Node.js backend (Express)
- Grok API for restructuring and intro/CTA generation
- X API v2 for thread retrieval
- Beehiiv API and Substack API for optional direct publishing
- Minimal static frontend (HTML + Tailwind)

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
