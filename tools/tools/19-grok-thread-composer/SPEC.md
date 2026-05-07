# SPEC · 19 Grok Thread Composer

## Tagline

Write threads grounded in what's actually happening on X right now.

## Why it exists

Every general-purpose LLM writes threads that feel slightly off — they lack awareness of what is actually being discussed on X in the current hour. Grok is structurally different: xAI's model has live access to X's firehose, which means it can reference real posts, real framings, and real trending arguments that occurred minutes ago.

This tool is designed specifically around that capability. It is not a generic AI writer with an X theme; it is a thin, fast surface on top of Grok's live-context advantage, aimed at creators who want threads that land inside the conversation instead of alongside it. Strategically, it drives Grok API usage and showcases xAI's differentiation versus OpenAI and Anthropic directly.

## User journey

1. User lands on a single page and enters a topic, angle, or rough thesis into a textarea.
2. Optionally, user picks a tone (punchy / analytical / storytelling) and a target length (5, 8, 12 tweets).
3. User clicks "compose" — a thin Node proxy forwards the prompt to the Grok API with a system prompt instructing Grok to pull current X context on the topic and cite it in reasoning.
4. Grok returns a structured thread as an array of tweets; the UI renders each as an editable card with live character counts and a drag handle to reorder.
5. User edits in place, regenerates individual tweets, or asks for a "make this more X-native" pass.
6. User clicks "copy thread" to get a formatted blob they paste into X, or "copy numbered" to paste one-by-one.

## Data sources

- Grok API (xAI) — default model `grok-4` or current production model, with X-context tool enabled
- No direct X API calls; Grok handles the live-context lookup internally

## Tech stack

- Vite + React single-page frontend
- Node.js 20 proxy (minimal Express) to hold the xAI API key, hosted on Render
- Tailwind + shadcn/ui for the editor
- Deployment: static frontend on Render static site, proxy as a Render web service

## Estimated build

6–10 hours.

## Open questions / risks

- Grok API pricing and rate limits define unit economics; build with streaming and per-request budgets from day one.
- If the xAI SDK exposes the X-context tool as an explicit parameter, wire it through; otherwise rely on system-prompt instructions and model defaults.
- Client-side key handling is tempting for simplicity but leaks the key; the thin Node proxy is non-negotiable even though it adds a deployment target.
- Thread length caps (280 characters per tweet, or 4000 for premium) must be enforced in the UI with a clear indicator of which post will truncate.
- The tool should not auto-post; the goal is to keep the creator in the loop for voice and judgment, consistent with the rest of the toolkit.
- Strategic value increases as Grok's X-context quality improves; the tool is a natural early adopter of new xAI capabilities.
