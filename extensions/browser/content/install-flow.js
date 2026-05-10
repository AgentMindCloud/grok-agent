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
// Grok Agent OS - Browser Extension Content Script: install-flow.js
// Built for xAI, X, Grok and the ecosystem community.
//
// Renders a centered modal overlay describing three install paths
// (PowerShell, one-liner, manifest URL) for a v2.15 manifest detected
// by detect-yaml.js. Exposed on window.GrokInstallFlow for the sibling
// content script. All visual styling lives in install-flow.css.
//
// No npm dependencies; pure browser APIs only.

(function () {
  'use strict';

  /** Stable IDs so we never inject twice. */
  const BACKDROP_ID = 'grok-install-overlay-backdrop';
  const MODAL_ID = 'grok-install-overlay-modal';

  /** Marketplace + repo URLs surfaced inside the overlay. */
  const MARKETPLACE_INSTALL_URL = 'https://github.com/AgentMindCloud/grok-agent#install';
  const PR_NEW_URL = 'https://github.com/AgentMindCloud/grok-agent/new/main';

  /** PowerShell install command. Forward slashes inside the quoted arg
   *  read cleanly across PowerShell, pwsh, and copy-paste contexts. */
  const PWSH_COMMAND = 'pwsh -c ".\\cli\\grok-agent.ps1 install -FromStdin"';

  /** Marketplace one-liner string. */
  const ONE_LINER = 'grok install this';

  /**
   * Build a DOM element from a tag and attribute bag. Helper to keep
   * showInstallOverlay readable.
   *
   * @param {string} tag
   * @param {Object<string,string>} [attrs]
   * @param {string} [text]
   * @returns {HTMLElement}
   */
  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'class') {
          node.className = attrs[k];
        } else {
          node.setAttribute(k, attrs[k]);
        }
      });
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  /**
   * Render a single install card with a "Copy" button.
   *
   * @param {{title:string, body:string, copyValue:string, link?:string}} cfg
   * @returns {HTMLElement}
   */
  function buildCard(cfg) {
    const card = el('div', { class: 'grok-install-card' });
    card.appendChild(el('h3', { class: 'grok-install-card-title' }, cfg.title));
    card.appendChild(el('p', { class: 'grok-install-card-body' }, cfg.body));

    const cmd = el('code', { class: 'grok-install-card-cmd' }, cfg.copyValue);
    card.appendChild(cmd);

    const actions = el('div', { class: 'grok-install-card-actions' });
    const copyBtn = el('button', {
      type: 'button',
      class: 'grok-install-copy-btn',
    }, 'Copy');
    copyBtn.addEventListener('click', function () {
      copyToClipboard(cfg.copyValue, copyBtn);
    });
    actions.appendChild(copyBtn);

    if (cfg.link) {
      const link = el('a', {
        class: 'grok-install-card-link',
        href: cfg.link,
        target: '_blank',
        rel: 'noopener noreferrer',
      }, 'Open');
      actions.appendChild(link);
    }
    card.appendChild(actions);
    return card;
  }

  /**
   * Copy text to the clipboard and flash the button label.
   *
   * @param {string} value
   * @param {HTMLButtonElement} btn
   */
  function copyToClipboard(value, btn) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(function () {
          flashCopied(btn);
        }).catch(function () {
          flashCopied(btn, 'Copy failed');
        });
        return;
      }
    } catch (err) {
      // fall through to fallback below
    }
    // Fallback for older browsers without async clipboard.
    try {
      const ta = document.createElement('textarea');
      ta.value = value;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      flashCopied(btn);
    } catch (err) {
      flashCopied(btn, 'Copy failed');
    }
  }

  function flashCopied(btn, label) {
    const original = btn.textContent;
    btn.textContent = label || 'Copied!';
    btn.disabled = true;
    window.setTimeout(function () {
      btn.textContent = original;
      btn.disabled = false;
    }, 1500);
  }

  /**
   * Tear down the overlay and remove every listener it registered.
   */
  function closeOverlay() {
    const backdrop = document.getElementById(BACKDROP_ID);
    if (backdrop && backdrop.parentNode) {
      backdrop.parentNode.removeChild(backdrop);
    }
    document.removeEventListener('keydown', onKeydown, true);
  }

  function onKeydown(evt) {
    if (evt.key === 'Escape') {
      evt.preventDefault();
      closeOverlay();
    }
  }

  /**
   * Public entry point. Render the install overlay for a given YAML
   * snippet. Called from detect-yaml.js when the floating button is
   * clicked.
   *
   * @param {string} yaml
   */
  function showInstallOverlay(yaml) {
    if (typeof yaml !== 'string' || !yaml.trim()) {
      return;
    }
    closeOverlay(); // make idempotent

    const backdrop = el('div', {
      id: BACKDROP_ID,
      class: 'grok-install-overlay-backdrop',
      role: 'presentation',
    });
    backdrop.addEventListener('click', function (evt) {
      if (evt.target === backdrop) {
        closeOverlay();
      }
    });

    const modal = el('div', {
      id: MODAL_ID,
      class: 'grok-install-overlay-modal',
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'grok-install-overlay-title',
    });

    const closeBtn = el('button', {
      type: 'button',
      class: 'grok-install-close-btn',
      'aria-label': 'Close',
    }, '×');
    closeBtn.addEventListener('click', closeOverlay);
    modal.appendChild(closeBtn);

    modal.appendChild(el('h2', {
      id: 'grok-install-overlay-title',
      class: 'grok-install-overlay-title',
    }, 'Install with Grok Agent OS'));

    const yamlBlock = el('pre', { class: 'grok-install-yaml' });
    yamlBlock.appendChild(el('code', null, yaml));
    modal.appendChild(yamlBlock);

    const cards = el('div', { class: 'grok-install-cards' });
    cards.appendChild(buildCard({
      title: 'Windows + PowerShell',
      body: 'Copy the command, run it, then paste the YAML when prompted.',
      copyValue: PWSH_COMMAND,
    }));
    cards.appendChild(buildCard({
      title: 'One-liner',
      body: 'Use the Grok Agent OS marketplace install shortcut.',
      copyValue: ONE_LINER,
      link: MARKETPLACE_INSTALL_URL,
    }));
    cards.appendChild(buildCard({
      title: 'Manifest URL',
      body: 'Open a pull request to add this manifest to the public repository.',
      copyValue: PR_NEW_URL,
      link: PR_NEW_URL,
    }));
    modal.appendChild(cards);

    modal.appendChild(el('p', {
      class: 'grok-install-disclaimer',
    }, 'Beta. Verify the manifest source before installing.'));

    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
    document.addEventListener('keydown', onKeydown, true);
  }

  // Expose the public API on window so detect-yaml.js can call it.
  window.GrokInstallFlow = {
    showInstallOverlay: showInstallOverlay,
    closeOverlay: closeOverlay,
  };
})();
