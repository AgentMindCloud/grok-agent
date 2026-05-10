// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// Grok Agent OS - Browser Extension Content Script: detect-yaml.js
// Built for xAI, X, Grok and the ecosystem community.
//
// Scans x.com / twitter.com pages for v2.15 manifest YAML blocks and
// injects a floating "Install with Grok Agent OS" button next to each
// match. Click handler hands the YAML to install-flow.js for overlay UI.
//
// Triggers at document_idle per the manifest declaration. Uses a
// MutationObserver throttled to 500ms to keep the scan cheap on the
// X timeline (which mutates aggressively).
//
// No npm dependencies; pure browser APIs only (Chrome MV3 / Firefox).

(function () {
  'use strict';

  /**
   * v2.15 manifest signature - matches lines that begin with the
   * canonical version field (quoted or bare) or the kind: agent header.
   * The detector is intentionally conservative: false positives create
   * noisy buttons; false negatives just mean the user copies by hand.
   */
  const MANIFEST_SIGNATURE_RE = /^(?:version:\s*["']?2\.15["']?|kind:\s*["']?agent["']?)/m;

  /** DOM marker we set on each scanned node so we never re-inject. */
  const DETECTED_ATTR = 'data-grok-detected';

  /** Selectors we look at for each scan pass. */
  const TARGET_SELECTORS = ['pre', 'code', 'article'];

  /** Throttle window for MutationObserver-driven re-scans (ms). */
  const SCAN_THROTTLE_MS = 500;

  /** Floating button class - kept in sync with install-flow.css. */
  const FLOATING_BTN_CLASS = 'grok-install-floating-btn';

  let scanScheduled = false;
  let lastScanAt = 0;

  /**
   * Inspect an element's text content and return true when it looks like
   * a v2.15 manifest. We require the signature regex to match within the
   * first 4 KB of text - manifests are usually <2 KB and we don't want
   * to scan giant code blocks for nothing.
   *
   * @param {Element} el
   * @returns {boolean}
   */
  function looksLikeManifest(el) {
    if (!el || !el.textContent) {
      return false;
    }
    const text = el.textContent.slice(0, 4096);
    return MANIFEST_SIGNATURE_RE.test(text);
  }

  /**
   * Build the floating "Install with Grok Agent OS" button. Styling is
   * controlled by install-flow.css (.grok-install-floating-btn).
   *
   * @param {string} yamlSnippet
   * @returns {HTMLButtonElement}
   */
  function buildFloatingButton(yamlSnippet) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = FLOATING_BTN_CLASS;
    btn.textContent = 'Install with Grok Agent OS';
    btn.setAttribute('aria-label', 'Install this manifest with Grok Agent OS');
    btn.addEventListener('click', function (evt) {
      evt.preventDefault();
      evt.stopPropagation();
      onInstallClick(yamlSnippet);
    });
    return btn;
  }

  /**
   * Wrap a target node with a relative-positioned container so the
   * absolutely positioned button can anchor to its top-right.
   *
   * @param {Element} target
   * @param {HTMLButtonElement} btn
   */
  function attachButton(target, btn) {
    const wrapper = document.createElement('span');
    wrapper.className = 'grok-install-anchor';
    wrapper.style.position = 'relative';
    wrapper.style.display = 'inline-block';
    wrapper.style.width = '100%';

    const parent = target.parentNode;
    if (!parent) {
      return;
    }
    parent.insertBefore(wrapper, target);
    wrapper.appendChild(target);
    wrapper.appendChild(btn);
  }

  /**
   * Click handler: ask the install-flow module to render its overlay,
   * and notify the background service worker so it can record the
   * install request.
   *
   * @param {string} yamlSnippet
   */
  function onInstallClick(yamlSnippet) {
    try {
      if (typeof window.GrokInstallFlow !== 'undefined' &&
          typeof window.GrokInstallFlow.showInstallOverlay === 'function') {
        window.GrokInstallFlow.showInstallOverlay(yamlSnippet);
      } else {
        // install-flow.js loads as a separate content script; if it's
        // missing we fall back to a copy-to-clipboard prompt so the
        // user is never stuck.
        window.prompt('Copy this YAML and paste into the CLI:', yamlSnippet);
      }
    } catch (err) {
      // Defensive: never let a UI error bubble into the page.
      console.warn('[grok-agent] overlay failed to open:', err);
    }
    try {
      if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage({
          type: 'INSTALL_REQUEST',
          yaml: yamlSnippet,
          url: window.location.href,
        });
      }
    } catch (err) {
      // The background SW may be in restart; not fatal.
      console.warn('[grok-agent] background message failed:', err);
    }
  }

  /**
   * Scan the live DOM for unprocessed manifest blocks. Called on a
   * throttled cadence by the MutationObserver and once at startup.
   */
  function scanDocument() {
    lastScanAt = Date.now();
    scanScheduled = false;

    const selector = TARGET_SELECTORS
      .map(function (s) { return s + ':not([' + DETECTED_ATTR + '])'; })
      .join(',');

    let candidates;
    try {
      candidates = document.querySelectorAll(selector);
    } catch (err) {
      return;
    }

    for (let i = 0; i < candidates.length; i += 1) {
      const node = candidates[i];
      // Always mark the node first so subsequent scans skip it even if
      // it is not a manifest. This bounds the work per element to one.
      node.setAttribute(DETECTED_ATTR, '1');
      if (!looksLikeManifest(node)) {
        continue;
      }
      const snippet = (node.textContent || '').trim();
      if (!snippet) {
        continue;
      }
      const btn = buildFloatingButton(snippet);
      attachButton(node, btn);
    }
  }

  /**
   * Throttled scheduler: collapse rapid-fire DOM mutations into one
   * scan every SCAN_THROTTLE_MS so X's timeline scroll doesn't pin
   * the CPU.
   */
  function scheduleScan() {
    if (scanScheduled) {
      return;
    }
    const elapsed = Date.now() - lastScanAt;
    const delay = elapsed >= SCAN_THROTTLE_MS ? 0 : SCAN_THROTTLE_MS - elapsed;
    scanScheduled = true;
    window.setTimeout(scanDocument, delay);
  }

  /**
   * Wire up the MutationObserver and run an initial pass.
   */
  function bootstrap() {
    try {
      scanDocument();
    } catch (err) {
      console.warn('[grok-agent] initial scan failed:', err);
    }
    const observer = new MutationObserver(function () {
      scheduleScan();
    });
    try {
      observer.observe(document.body, { childList: true, subtree: true });
    } catch (err) {
      console.warn('[grok-agent] observer attach failed:', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap, { once: true });
  } else {
    bootstrap();
  }
})();
