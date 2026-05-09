// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Built for xAI, X, Grok and the ecosystem community.
//
// Options page logic for the Grok Agent OS browser extension.
//
// Persists user preferences in chrome.storage.sync so they roam across
// the user's signed-in Chrome profiles. Three settings are stored:
//   - install_path     (string, must be non-empty)
//   - notifications    (boolean)
//   - install_method   (one of: powershell-stdin, one-liner, manifest-url)
//
// Pure browser JS. Zero npm deps. No remote calls.

(function () {
  "use strict";

  const STORAGE_KEY = "grok.options.v1";

  const DEFAULTS = Object.freeze({
    install_path: "$env:LOCALAPPDATA\\grok-agent\\agents",
    notifications: true,
    install_method: "powershell-stdin",
  });

  const VALID_METHODS = new Set([
    "powershell-stdin",
    "one-liner",
    "manifest-url",
  ]);

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    document.getElementById("g-save-btn").addEventListener("click", onSave);
    document.getElementById("g-reset-btn").addEventListener("click", onReset);
    loadSettings();
  }

  function loadSettings() {
    chrome.storage.sync.get([STORAGE_KEY], (result) => {
      const stored = (result && result[STORAGE_KEY]) || {};
      const merged = Object.assign({}, DEFAULTS, stored);
      applyToForm(merged);
    });
  }

  function applyToForm(settings) {
    document.getElementById("g-install-path").value = String(
      settings.install_path || DEFAULTS.install_path
    );
    document.getElementById("g-notifications").checked = Boolean(
      settings.notifications
    );

    const method = VALID_METHODS.has(settings.install_method)
      ? settings.install_method
      : DEFAULTS.install_method;
    const radioId =
      method === "one-liner"
        ? "g-method-oneliner"
        : method === "manifest-url"
          ? "g-method-url"
          : "g-method-stdin";
    const radio = document.getElementById(radioId);
    if (radio) radio.checked = true;
  }

  function readForm() {
    const installPath = document
      .getElementById("g-install-path")
      .value.trim();
    const notifications = Boolean(
      document.getElementById("g-notifications").checked
    );
    const checked = document.querySelector(
      'input[name="install_method"]:checked'
    );
    const method = checked && VALID_METHODS.has(checked.value)
      ? checked.value
      : DEFAULTS.install_method;
    return {
      install_path: installPath,
      notifications,
      install_method: method,
    };
  }

  function onSave() {
    const settings = readForm();
    if (!settings.install_path) {
      setStatus("Install path cannot be empty.", true);
      return;
    }
    chrome.storage.sync.set({ [STORAGE_KEY]: settings }, () => {
      if (chrome.runtime.lastError) {
        setStatus("Save failed: " + chrome.runtime.lastError.message, true);
        return;
      }
      setStatus("Saved.", false);
    });
  }

  function onReset() {
    chrome.storage.sync.remove([STORAGE_KEY], () => {
      applyToForm(DEFAULTS);
      setStatus("Restored defaults.", false);
    });
  }

  function setStatus(message, isError) {
    const status = document.getElementById("g-status");
    if (!status) return;
    status.textContent = message;
    status.classList.toggle("error", Boolean(isError));
  }
})();
