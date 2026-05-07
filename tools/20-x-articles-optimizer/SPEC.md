# SPEC · 20 X Articles Optimizer

## Tagline

Your best thread is a half-written X Article. Let's complete it.

## Why it exists

X is pushing Articles as a first-class long-form surface, with premium-tier distribution advantages and a rich-text composer that supports headings, images, and formatted links. Despite this, the overwhelming majority of creators still publish only threads, leaving an easy format expansion on the table.

Threads and Articles share 80% of their structure — a hook, sequenced arguments, a conclusion — but differ in connective tissue, section headers, and prose density. Most creators know this intellectually and still do not convert, because doing it by hand feels like rewriting. This tool makes the conversion a paste-and-click so the format alignment becomes frictionless, which in turn rides X's current algorithmic tailwind for Articles.

## User journey

1. User lands on a single-page tool and either pastes thread text directly or pastes a thread URL.
2. If URL, backend fetches the thread via X API v2 using `conversation_id`; if raw text, parse tweet boundaries from blank lines or numbered prefixes.
3. Tool restructures into Article format: generates a title (with optional subtitle), inserts 3–5 subheadings that group related tweets, rewrites bullet-fragment tweets into flowing paragraphs, preserves and places inline media references, and appends a conclusion.
4. Optional "polish with Grok" button runs a second pass for tone consistency and to tighten prose.
5. Side-by-side view: original thread on the left, generated Article on the right, both editable.
6. User clicks "copy as Article-ready Markdown" — the output uses the Markdown subset X Articles supports (headings, bold, italics, links, image references, blockquotes). User pastes into X's Article composer and publishes.

## Data sources

- Manual paste (primary input, no API required)
- `GET /2/tweets/search/recent` with `conversation_id:{id}` (optional, for URL input)
- Grok API (optional) for the polish pass

## Tech stack

- Vite + React single-page frontend
- Node.js 20 proxy on Render, only used when X API or Grok is invoked
- Tailwind + shadcn/ui for the split editor
- Client-side Markdown preview via `marked`
- Deployment: Render static site for frontend, Render web service for the thin proxy

## Estimated build

6–10 hours.

## Open questions / risks

- X Articles Markdown support is not fully documented; the tool should output the documented-safe subset and let users adjust in X's native editor for anything advanced.
- Thread fetch via X API is capped at 7 days on the basic tier; raw-paste mode must remain the primary path.
- Auto-generated titles can feel generic; offer three title options rather than committing to one.
- Embedded media from threads does not carry over automatically — the Article composer requires re-upload; the tool surfaces a checklist of media URLs to re-attach.
- Strategic alignment with X's current roadmap is high, but if X changes Article policy or format, the output spec must be re-pinned.
