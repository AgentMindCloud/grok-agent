# SPEC · 11 Ghostwriter Mode with Memory

## Tagline

AI writer that learns your voice from your last 500 posts.

## Why it exists

AI writing tools for X have converged on a single detectable voice. Short punchy lines, em dashes, three-part lists, aspirational framing. Experienced readers skim past it automatically, which means using a generic AI writer actively hurts the accounts that lean on it. The only way an AI-assisted post adds value is if it reads like a specific human wrote it.

This tool treats the user's own archive as the ground truth. It pulls the last 500 posts, extracts the structural and lexical signature, and constrains the LLM to operate inside that signature. The output is not a generic good post; it is a post that sounds like the user on a good day. Because the voice profile is regenerated weekly, it tracks shifts in the user's style over time.

## User journey

1. User connects X account with read scope.
2. Backend pulls the last 500 original posts (excluding replies and reposts), stores them in Firestore.
3. A voice-profile worker extracts: top-100 vocabulary frequencies, common hook patterns (first-5-tokens clustering), average sentence length and variance, punctuation style, recurring themes (topic model or Grok-assisted clustering), emoji usage rate.
4. User types a topic or brief into the chat UI.
5. Backend assembles a prompt containing the voice profile plus a few exemplar posts and requests Grok to generate three variants. User picks, edits, posts.

## Data sources

- X API v2 `GET /2/users/{id}/tweets` with `max_results=100`, paginated to 500 posts, filtered to original posts
- Grok API `grok-2-latest` (primary) or Claude Sonnet (fallback) for generation and for topic clustering
- Firestore documents for voice profile and generation history

## Tech stack

- Node.js + Express backend on Render, with a background worker for the weekly profile refresh
- Firebase Auth (X-linked) for session
- Firestore for voice profiles, post archives, and generation logs
- Chat-style frontend (vanilla JS + Tailwind) on Hostinger
- Grok API as primary LLM for cost and X-context fit

## Estimated build

14–20 hours.

## Open questions / risks

- Accounts under 500 lifetime original posts need a graceful fallback (use what exists, warn about low-fidelity profile).
- Voice profile prompt can get large; may need to distill to a compact descriptor rather than shipping raw stats.
- Weekly regeneration burns Grok tokens per user; needs a per-user cost cap.
- Users will post directly from the tool, so output should include invisible variance to avoid homogenization across users.
- Detection of "original posts" vs. reply threads is noisy around self-reply chains that the user considers originals.
