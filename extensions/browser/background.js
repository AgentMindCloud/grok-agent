// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Built for xAI, X, Grok and the ecosystem community.
//
// Service worker for the Grok Agent OS browser extension.
//
// Responsibilities:
//   1. Register the "Install with Grok Agent OS" right-click menu on X
//      (x.com + twitter.com), scoped to text selections so users can
//      right-click a highlighted v2.15 manifest snippet from any post.
//   2. Forward the selected text to the active tab's content script
//      (Agent 6.2 — content/detect-yaml.js) which renders the in-page
//      install-flow overlay.
//   3. Maintain a rolling history of the last 10 install requests in
//      chrome.storage.local so the popup (Agent 6.3 — popup/popup.html)
//      can render a recent-activity list.
//
// Pure ES module. Zero npm deps. Browser APIs only.

const CONTEXT_MENU_ID = 'grok-install-yaml';
const HOST_PATTERNS = ['https://x.com/*', 'https://twitter.com/*'];
const STORAGE_KEY = 'grok.install.history';
const HISTORY_LIMIT = 10;

// ---------------------------------------------------------------------------
// Install / startup: register the context menu entry.
// ---------------------------------------------------------------------------

chrome.runtime.onInstalled.addListener(() => {
  // Always remove first so repeated installs (dev reloads) don't throw
  // a duplicate-id error.
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: CONTEXT_MENU_ID,
      title: 'Install with Grok Agent OS',
      contexts: ['selection'],
      documentUrlPatterns: HOST_PATTERNS,
    });
  });
});

// ---------------------------------------------------------------------------
// Context menu click → push the selection into the active tab's content
// script via chrome.scripting.executeScript. The content script reads
// window.__grokInstallPayload and renders the overlay.
// ---------------------------------------------------------------------------

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== CONTEXT_MENU_ID) return;
  if (!tab || typeof tab.id !== 'number') return;

  const snippet = (info.selectionText || '').trim();
  if (!snippet) return;

  chrome.scripting
    .executeScript({
      target: { tabId: tab.id },
      func: (payload) => {
        // Hand the snippet to the page-side content script. The content
        // script (Agent 6.2) listens on the custom event below.
        window.__grokInstallPayload = payload;
        window.dispatchEvent(
          new CustomEvent('grok-agent:install-request', { detail: payload })
        );
      },
      args: [{ snippet, sourceUrl: tab.url || '', timestamp: Date.now() }],
    })
    .catch((err) => {
      console.warn('[grok-agent] executeScript failed:', err);
    });

  recordHistory({
    snippet: snippet.slice(0, 4096),
    sourceUrl: tab.url || '',
    timestamp: Date.now(),
    via: 'context-menu',
  });
});

// ---------------------------------------------------------------------------
// Message router. Content + popup talk to the worker through here.
//   - INSTALL_REQUEST: log a manifest snippet so the popup can show it.
//   - GET_HISTORY:     return the last HISTORY_LIMIT install requests.
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== 'object') {
    sendResponse({ ok: false, error: 'invalid-message' });
    return false;
  }

  if (message.type === 'INSTALL_REQUEST') {
    const entry = {
      snippet: String(message.snippet || '').slice(0, 4096),
      sourceUrl: String(message.sourceUrl || ''),
      timestamp: Number(message.timestamp) || Date.now(),
      via: String(message.via || 'content-script'),
    };
    recordHistory(entry).then(() => sendResponse({ ok: true, entry }));
    return true; // async
  }

  if (message.type === 'GET_HISTORY') {
    chrome.storage.local.get([STORAGE_KEY], (result) => {
      const history = Array.isArray(result[STORAGE_KEY])
        ? result[STORAGE_KEY]
        : [];
      sendResponse({ ok: true, history });
    });
    return true; // async
  }

  sendResponse({ ok: false, error: 'unknown-type' });
  return false;
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function recordHistory(entry) {
  return new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEY], (result) => {
      const prior = Array.isArray(result[STORAGE_KEY])
        ? result[STORAGE_KEY]
        : [];
      const next = [entry, ...prior].slice(0, HISTORY_LIMIT);
      chrome.storage.local.set({ [STORAGE_KEY]: next }, () => resolve(next));
    });
  });
}

// Exported for unit tests (Node side can stub chrome.* and require this file
// after a light shim). No effect inside the service worker.
export { CONTEXT_MENU_ID, HOST_PATTERNS, STORAGE_KEY, HISTORY_LIMIT, recordHistory };
