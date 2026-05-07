/**
 * Tool 19 — Grok Thread Composer
 *
 * Status: scaffold. No implementation yet. See ../SPEC.md.
 *
 * SPEC sections that map onto this file (user-journey steps renumbered here
 * so each TODO lines up 1:1 with the SPEC bullets):
 *
 *   SPEC §User journey #1 — render the input surface (topic/angle textarea)
 *   SPEC §User journey #2 — tone picker + length selector (5/8/12 tweets)
 *   SPEC §User journey #3 — POST prompt to the Node proxy (NOT direct to xAI)
 *                           and stream the response via GrokClient.chatStream
 *   SPEC §User journey #4 — render each returned tweet as an editable card
 *                           with live char counts and a drag-to-reorder handle
 *   SPEC §User journey #5 — in-place edits, per-tweet regenerate, "X-native" pass
 *   SPEC §User journey #6 — "copy thread" / "copy numbered" export
 *
 * Also per SPEC §Open questions / risks:
 *   - enforce 280-char (or 4000-premium) cap in the UI with a visible indicator
 *   - never auto-post; creator stays in the loop
 *   - wire the xAI X-context tool through explicit tools param when available,
 *     otherwise rely on system prompt
 */

// TODO[SPEC §Tech stack]: decide between the shared grok-client/browser entry
// (direct call from the browser) and a thin Node proxy. SPEC mandates the
// proxy; docs/cors.md explains why. For the scaffold this import is unused;
// a future PR wires it to the proxy URL via { baseURL } override.
// eslint-disable-next-line no-unused-vars
import GrokClient from '@x-platform-toolkit/grok-client/browser';

export class ThreadComposer {
  constructor(options = {}) {
    this.options = options;
    this.mount = options.mount ?? null;
    this.client = null;
    this.state = {
      topic: '',
      tone: 'punchy',
      length: 8,
      tweets: [],
    };
  }

  /**
   * main() — entry point. Called from index.html.
   * No DOM work happens in the constructor so that `new ThreadComposer()`
   * remains safe to call from the Node smoke test.
   */
  async main() {
    // TODO[SPEC §User journey #1]: render the composer input surface.
    // TODO[SPEC §User journey #2]: wire tone / length controls.
    // TODO[SPEC §User journey #3]: on submit, POST to the Node proxy and
    //                              consume GrokClient.chatStream tokens.
    // TODO[SPEC §User journey #4-6]: render, edit, and copy.
  }
}

export default ThreadComposer;
