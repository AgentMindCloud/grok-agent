# SPEC · 13 Thread-to-Newsletter Auto-Converter

## Tagline

Your thread is half a newsletter. Let's finish the job.

## Why it exists

Most creators treat threads and newsletters as separate products, which doubles the writing workload and leaves ideas stranded on one platform. A thread that earned engagement has already been reader-tested; it deserves a second life in a longer, searchable, owned-channel format.

This tool removes the structural friction. Instead of re-writing from scratch, the creator feeds in a thread URL and receives a newsletter draft with proper prose flow, headings, and a call-to-action that fits newsletter conventions (subscribe, reply, share) rather than X conventions (like, repost, follow).

## User journey

1. Creator pastes a thread URL (root tweet) into the tool.
2. Backend fetches the full conversation via X API v2 using `conversation_id` filter, ordering tweets chronologically and filtering to the author.
3. Grok restructures the tweets: generates a hook intro paragraph, groups related tweets into 3–5 body sections with subheadings, rewrites bullet-style tweets into flowing prose, and appends a CTA block.
4. Creator reviews the draft in a side-by-side editor (original thread left, newsletter right) and can edit either column.
5. Export options: download Markdown, copy HTML, or push directly to Beehiiv or Substack via API using a stored OAuth token.

## Data sources

- `GET /2/tweets/search/recent` with `conversation_id:{id}` for thread retrieval
- `GET /2/tweets/{id}` for root tweet metadata
- Grok API (`grok-4` or current default) for prose restructuring
- Beehiiv API: `POST /publications/{id}/posts` for draft creation
- Substack API: post draft endpoint (unofficial, email-import fallback)

## Tech stack

- Node.js 20 + Express backend, hosted on Render
- Grok API via xAI SDK
- Firestore for storing drafts and OAuth tokens
- Static frontend (HTML + Tailwind + HTMX) served from the same Node process
- Deployment: single Render web service, environment-scoped secrets

## Estimated build

8–12 hours.

## Open questions / risks

- X API thread retrieval is capped at 7 days of history on the basic tier; older threads require the root author's timeline scan as a fallback.
- Substack has no stable public write API; email-to-publish import is the realistic path and should be presented as a configuration step.
- Beehiiv API requires a per-user API key; onboarding flow must handle key rotation and scope.
- Grok output length can exceed newsletter norms; enforce a max-token budget and offer a "tighten" pass.
- Thread media (images, videos) must be referenced by URL in Markdown since newsletter platforms re-host uploads differently.
