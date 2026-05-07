# SPEC · 16 Follower Migration Assistant

## Tagline

Pivoting your account? See who'll stay and who'll leave.

## Why it exists

Audience pivots are one of the most common and most anxiety-inducing decisions on X. A creator who built a following around one topic wants to shift into an adjacent one, but has no visibility into how much of their audience actually overlaps with the new direction. The fear of "losing everyone" is often worse than the reality — or sometimes much better than reality — and guessing leads to either paralysis or a botched pivot.

This tool replaces the guess with data. By scoring every follower's likelihood to stay based on their own stated interests and posting behavior, it hands the creator a forecast before they change a single line of their bio.

## User journey

1. User connects X via OAuth and enters two inputs: a description of their current positioning, and a description of their proposed new positioning.
2. Backend paginates through the user's followers, pulling each follower's bio plus their 20 most recent original posts.
3. Grok scores each follower on two axes: relevance to old positioning, relevance to new positioning, returning a retention bucket (high / medium / low).
4. Dashboard renders aggregate stats (retained count, at-risk count, lost count), a retention heatmap by follower cohort (date followed), and a sample list of each bucket.
5. User clicks "generate pivot announcement" — Grok drafts 3 post angles tuned to keep medium-bucket followers from churning (framing the pivot as continuity, not rupture).
6. User can export the retention list as CSV for manual outreach to high-value at-risk accounts.

## Data sources

- `GET /2/users/{id}/followers` with `user.fields=description,public_metrics` (paginated)
- `GET /2/users/{id}/tweets` per follower, max 20 recent posts, filtered to originals
- Grok API for relevance scoring — batched 20 followers per call to control cost

## Tech stack

- Node.js 20 + Express backend, hosted on Render
- BullMQ + Redis for batched follower-processing jobs
- Firestore for analysis results and user positioning inputs
- React + Recharts frontend dashboard
- Grok API via xAI SDK

## Estimated build

12–16 hours.

## Open questions / risks

- X API follower iteration is rate-limited and slow; for accounts above 10k followers the full scan needs to run asynchronously over hours with progress UI.
- A random sample (e.g. 500 followers) gives a usable estimate at a fraction of the cost and time; offer sampled mode as the default and full-scan as an opt-in.
- Grok scoring accuracy depends on bio and post quality; accounts with empty bios and no recent posts fall into a "cannot assess" bucket that must be surfaced honestly.
- The tool should not store follower post content beyond the analysis window (enforce a 7-day TTL).
- Predictions are probabilistic; UI language should avoid overclaiming ("will unfollow") in favor of calibrated framing ("low relevance to new direction").
