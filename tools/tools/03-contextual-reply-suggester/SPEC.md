# SPEC · 03 Contextual Reply Suggester

## Tagline

Reply suggestions ranked by likelihood of follower gain.

## Why it exists

On X the shortest path from zero to a real audience is replying under larger accounts in your niche. The mechanic is well-known and it works, but most people fail at it. They reply with agreement ("so true"), with obvious self-promotion, or with content that doesn't match the original tweet's tone. The reply gets buried and the creator gives up.

This tool closes the gap between knowing the strategy and executing it. Given any tweet, it produces five reply candidates in different voices and scores each against a predicted-virality model so the user picks the strongest one before posting.

## User journey

1. User pastes a tweet URL or raw text into the app (or clicks the extension icon on a tweet page).
2. Backend fetches the original tweet, the author's last 20 posts, and the author's bio for context.
3. Grok API receives a structured prompt with context and generates five replies in distinct tones: contrarian, value-add, humor, question, personal-story.
4. Each reply is scored by a heuristic (hook strength, length fit, tone-match with original, novelty vs. existing replies).
5. User copies the chosen reply to clipboard, edits if needed, and posts.

## Data sources

- X API v2 `GET /2/tweets/{id}` with `expansions=author_id`, `tweet.fields=context_annotations,public_metrics`
- X API v2 `GET /2/users/{id}/tweets` for author voice sampling
- Grok API `grok-2-latest` for generation, JSON mode for structured output

## Tech stack

- Frontend: single-page React app on Hostinger, plus optional Chrome MV3 extension for inline use on x.com
- Backend: Node.js + Express on Render handling API key custody and prompt assembly
- Firestore for per-user daily quota and generation history
- Grok API as primary LLM, fallback to Claude Haiku if Grok is rate-limited

## Estimated build

10–14 hours.

## Open questions / risks

- Predicted-virality scoring is inherently fuzzy. First version uses a transparent rubric rather than a trained model; may need real post-outcome data collection to improve.
- Chrome extension path requires MV3 review and can break on x.com layout changes.
- Grok API cost per generation must be capped per user per day; five variants per request is not cheap at scale.
- Users may post the raw output without editing, which creates a homogenization risk across the user base. Outputs should include small randomization.
