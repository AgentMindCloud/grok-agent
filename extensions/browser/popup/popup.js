// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Built for xAI, X, Grok and the ecosystem community.
//
// Popup logic for the Grok Agent OS browser extension.
//
// Responsibilities:
//   1. On DOMContentLoaded, ask the service worker for the rolling
//      install-request history via { type: 'GET_HISTORY' }.
//   2. Render the last 10 entries (timestamp + 60-char YAML snippet +
//      "Re-open install flow" button per item).
//   3. Wire the marketplace + settings buttons.
//
// Pure browser JS. Zero npm deps. No remote calls beyond explicit user
// clicks (footer GitHub link + "Open marketplace" button).

(function () {
  "use strict";

  const HISTORY_LIMIT = 10;
  const SNIPPET_CHARS = 60;
  const MARKETPLACE_URL = "https://agentmindcloud.github.io/grok-agent/";

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    bindActions();
    loadHistory();
  }

  function bindActions() {
    const marketBtn = document.getElementById("g-open-marketplace");
    if (marketBtn) {
      marketBtn.addEventListener("click", () => {
        chrome.tabs.create({ url: MARKETPLACE_URL });
      });
    }

    const settingsBtn = document.getElementById("g-open-settings");
    if (settingsBtn) {
      settingsBtn.addEventListener("click", () => {
        if (chrome.runtime.openOptionsPage) {
          chrome.runtime.openOptionsPage();
        } else {
          chrome.tabs.create({ url: "options/options.html" });
        }
      });
    }
  }

  function loadHistory() {
    const list = document.getElementById("g-history-list");
    if (!list) return;

    chrome.runtime.sendMessage({ type: "GET_HISTORY" }, (response) => {
      list.setAttribute("aria-busy", "false");
      list.innerHTML = "";

      if (chrome.runtime.lastError) {
        renderEmpty(list, "Could not reach the background worker.");
        return;
      }

      const history =
        response && Array.isArray(response.history) ? response.history : [];

      if (history.length === 0) {
        renderEmpty(list, "No install requests yet.");
        return;
      }

      history.slice(0, HISTORY_LIMIT).forEach((entry) => {
        list.appendChild(renderItem(entry));
      });
    });
  }

  function renderEmpty(list, message) {
    const li = document.createElement("li");
    li.className = "g-history-empty";
    li.textContent = message;
    list.appendChild(li);
  }

  function renderItem(entry) {
    const li = document.createElement("li");
    li.className = "g-history-item";

    const time = document.createElement("span");
    time.className = "g-history-time";
    time.textContent = formatTimestamp(entry.timestamp);
    li.appendChild(time);

    const snippet = document.createElement("p");
    snippet.className = "g-history-snippet";
    snippet.textContent = truncate(String(entry.snippet || ""), SNIPPET_CHARS);
    li.appendChild(snippet);

    const reopenBtn = document.createElement("button");
    reopenBtn.type = "button";
    reopenBtn.className = "g-reopen-btn";
    reopenBtn.textContent = "Re-open install flow";
    reopenBtn.setAttribute(
      "aria-label",
      "Re-open install flow for this manifest"
    );
    reopenBtn.addEventListener("click", () => reopenFlow(entry));
    li.appendChild(reopenBtn);

    return li;
  }

  function reopenFlow(entry) {
    const targetUrl = entry && entry.sourceUrl ? entry.sourceUrl : "";
    chrome.tabs.create({ url: targetUrl || MARKETPLACE_URL }, (tab) => {
      if (!tab || typeof tab.id !== "number") return;
      const payload = {
        snippet: String(entry.snippet || ""),
        sourceUrl: String(entry.sourceUrl || ""),
        timestamp: Date.now(),
        via: "popup-reopen",
      };
      chrome.runtime.sendMessage({ type: "INSTALL_REQUEST", ...payload });
    });
  }

  function truncate(text, max) {
    if (text.length <= max) return text;
    return text.slice(0, max - 1) + "…";
  }

  function formatTimestamp(ts) {
    const ms = Number(ts);
    if (!Number.isFinite(ms)) return "unknown time";
    const d = new Date(ms);
    return d.toLocaleString();
  }
})();
