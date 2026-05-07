# SPEC · 17 Post Necromancer

## Tagline

Your old posts had good ideas. Reincarnate them with today's vocabulary.

## Why it exists

Creators sit on an archive of posts that earned real engagement but are now buried past the scroll. The ideas inside them are often evergreen — the phrasing, hooks, and platform conventions are not. Reposting verbatim feels lazy and flags as duplicate content; rewriting from memory loses the original signal about what resonated.

This tool treats the post archive as a proprietary dataset. It ranks your own history by engagement-per-impression (a fairer signal than raw likes, since follower count varies over time), then asks Grok — which has live X access — to re-express each winning idea in today's voice. The output respects your original insight while updating the wrapper so it reads as a current post, not a throwback.

## User journey

1. User connects X via OAuth (scopes: `tweet.read`, `users.read`).
2. Backend fetches posts from 90 to 365 days ago, pulling per-post impression and engagement counts.
3. Compute score = (likes + reposts + replies + bookmarks) / impressions, filter for originals (no replies, no quotes), and surface the top 20.
4. For each top post, Grok generates three rewrites: one updating the hook to a currently-trending format, one compressing for modern short-form pacing, and one expanding into a thread opener.
5. User sees a card stack: original on top, three variants below, with approve / skip / edit actions.
6. Approved variants land in a "ready to post" queue (Firestore) with a copy-to-clipboard button and a suggested post date; user schedules manually via their preferred scheduler — no auto-post.

## Data sources

- `GET /2/users/{id}/tweets` with `tweet.fields=public_metrics,non_public_metrics,created_at` (non-public metrics require user-context auth)
- `GET /2/tweets/{id}` for deeper metrics where needed
- Grok API for rewriting — prompt includes the original post, its metrics, and an instruction to use current X vocabulary

## Tech stack

- Node.js 20 + Express backend, hosted on Render
- Firestore for the approval queue and user session state
- React frontend with a card-review UI
- Grok API via xAI SDK
- X OAuth 2.0 PKCE for read-only auth

## Estimated build

12–16 hours.

## Open questions / risks

- X API `non_public_metrics` (impressions) is only available for the authenticated user's own posts and only for posts under 30 days old on some tiers; for older posts, fall back to ranking by public metrics alone.
- Historical pagination caps at 3,200 recent tweets via user timeline; accounts posting daily will hit that ceiling before reaching 365 days — offer a "upload archive" path using X's official data export as a fallback.
- The tool intentionally does not auto-post to preserve creator voice and avoid engagement manipulation patterns; this is a product principle, not a technical limit.
- Grok rewrites can drift too far from the original idea; prompt must anchor on preserving the core claim and only updating the wrapper.
- Surfacing a "your old self vs your new self" delta could become a side feature but is scoped out of v1.
