/**
 * mock-fetch — replace globalThis.fetch with a scripted responder.
 *
 * Accepts one of three `responses` shapes:
 *
 *   1. An object:   every fetch() call returns the same response.
 *   2. An array:    the i-th fetch() call returns responses[i]. Throws if
 *                   the caller runs off the end.
 *   3. A function:  (url, init) => response — receives the request and
 *                   returns whatever the test wants.
 *
 * A "response" object has shape { status?, headers?, body? }.
 * `body` may be:
 *   - a string              (returned as-is via Response.text())
 *   - a plain object        (JSON-stringified, Content-Type set to JSON)
 *   - a ReadableStream      (returned as the response body, enables
 *                            streaming tests)
 *
 * Returns a `restore()` function that puts the original fetch back and
 * exposes `.calls` — an array of { url, init } recorded for assertions.
 */

export function mockFetch(responses) {
  const original = globalThis.fetch;
  const calls = [];
  let index = 0;

  const resolve = (url, init) => {
    if (typeof responses === 'function') {
      return responses(url, init);
    }
    if (Array.isArray(responses)) {
      if (index >= responses.length) {
        throw new Error(
          `mockFetch: no response scripted for call #${index + 1} (url=${String(url)})`
        );
      }
      return responses[index++];
    }
    return responses;
  };

  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init: init ?? {} });
    const spec = resolve(url, init) ?? {};
    return buildResponse(spec);
  };

  const restore = () => {
    globalThis.fetch = original;
  };
  restore.calls = calls;
  return restore;
}

function buildResponse(spec) {
  const status = spec.status ?? 200;
  const headers = new Headers(spec.headers ?? {});
  const body = spec.body;

  if (body == null) {
    return new Response(null, { status, headers });
  }
  if (typeof body === 'string') {
    return new Response(body, { status, headers });
  }
  if (body instanceof ReadableStream) {
    return new Response(body, { status, headers });
  }
  // plain object -> JSON
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  return new Response(JSON.stringify(body), { status, headers });
}

/**
 * sseStream(text) — wrap a raw SSE transcript in a ReadableStream.
 * Tests feed `grok-stream.txt` through this to simulate streaming replies.
 */
export function sseStream(text) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}
