/*
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Built for xAI, X, Grok and the ecosystem community.
 *
 * Static marketplace bootstrap. Renders the 7 Super Agent cards plus
 * the Creator Templates teaser, wires up the search input, the
 * category filter pills, the per-card copy-to-clipboard buttons, and
 * persists the theme toggle to localStorage. No frameworks, no build
 * step, no telemetry.
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------
  // Agent catalogue (kept in sync with templates/super-agents/_bridges/registry.json
  // and templates/creator/). Update here when shipping a new agent.
  // ---------------------------------------------------------------
  var REPO_BASE =
    "https://github.com/AgentMindCloud/grok-agent/tree/main/templates";

  var AGENTS = [
    {
      slug: "living-narrative-fabric",
      name: "Living Narrative Fabric",
      tagline:
        "Versioned synthesis of X + news + academic + government + personal data with full provenance and contradiction detection.",
      kind: "super-agent",
      category: "flagship",
      tags: [
        "synthesis",
        "provenance",
        "contradictions",
        "x",
        "news",
        "academic",
        "government",
      ],
      sourceUrl: REPO_BASE + "/super-agents/living-narrative-fabric",
    },
    {
      slug: "self-evolving-personal-os",
      name: "Self-Evolving Personal OS",
      tagline:
        "Personal OS that learns user habits, preferences, and goals; updates itself nightly.",
      kind: "super-agent",
      category: "flagship",
      tags: ["personal", "memory", "habits", "evolution", "briefings"],
      sourceUrl: REPO_BASE + "/super-agents/self-evolving-personal-os",
    },
    {
      slug: "cross-reality-action-fabric",
      name: "Cross-Reality Action Fabric",
      tagline:
        "Takes real-world actions across web, calendar, X, and files — every action gated by explicit consent.",
      kind: "super-agent",
      category: "flagship",
      tags: [
        "actions",
        "web",
        "calendar",
        "x",
        "files",
        "consent",
        "powershell",
      ],
      sourceUrl: REPO_BASE + "/super-agents/cross-reality-action-fabric",
    },
    {
      slug: "agent-swarm-with-shared-memory",
      name: "Agent Swarm with Shared Memory",
      tagline:
        "Multi-agent swarm with shared memory for collective intelligence.",
      kind: "super-agent",
      category: "lighter",
      tags: ["swarm", "memory", "mem0", "qdrant", "collective"],
      sourceUrl: REPO_BASE + "/super-agents/agent-swarm-with-shared-memory",
    },
    {
      slug: "provenance-first-trust-engine",
      name: "Provenance-First Trust Engine",
      tagline:
        "Verifiable confidence scores and provenance tracking for every claim.",
      kind: "super-agent",
      category: "lighter",
      tags: ["provenance", "trust", "confidence", "citations"],
      sourceUrl: REPO_BASE + "/super-agents/provenance-first-trust-engine",
    },
    {
      slug: "narrative-contradiction-detector",
      name: "Narrative Contradiction Detector",
      tagline:
        "Surfaces contradictions across sources without silently resolving them.",
      kind: "super-agent",
      category: "lighter",
      tags: ["contradictions", "narrative", "sources", "scanner"],
      sourceUrl: REPO_BASE + "/super-agents/narrative-contradiction-detector",
    },
    {
      slug: "zero-config-i-want-to-agent",
      name: "Zero-Config I-Want-To Agent",
      tagline:
        "Zero-config natural-language agent: 'I want to ___' becomes a real workflow.",
      kind: "super-agent",
      category: "lighter",
      tags: ["zero-config", "goals", "workflow", "natural-language"],
      sourceUrl: REPO_BASE + "/super-agents/zero-config-i-want-to-agent",
    },
    {
      slug: "creator-templates",
      name: "Creator Templates (22 available)",
      tagline:
        "Ready-to-use creator agent templates: content ideas, replies, analytics, monetization, threads, mentions, DMs, growth, and more.",
      kind: "creator-templates",
      category: "creator",
      tags: [
        "creator",
        "content",
        "replies",
        "analytics",
        "monetization",
        "threads",
        "growth",
      ],
      sourceUrl: REPO_BASE + "/creator",
      isTeaser: true,
    },
  ];

  // ---------------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------------
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $all(sel, root) {
    return Array.prototype.slice.call(
      (root || document).querySelectorAll(sel),
    );
  }
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ---------------------------------------------------------------
  // Theme toggle (persists in localStorage)
  // ---------------------------------------------------------------
  var THEME_KEY = "grok-agent-marketplace.theme";
  var SUN = "☀️"; // ☀️
  var MOON = "🌙"; // 🌙

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch (err) {
      return null;
    }
  }

  function storeTheme(theme) {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch (err) {
      /* ignore storage errors (private mode or quota exceeded) */
    }
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    var icon = $("#theme-icon");
    var btn = $("#theme-toggle");
    if (theme === "light") {
      root.classList.remove("dark");
      if (icon) icon.textContent = MOON;
      if (btn) {
        btn.setAttribute("aria-pressed", "false");
        btn.setAttribute("aria-label", "Switch to dark mode");
      }
    } else {
      root.classList.add("dark");
      if (icon) icon.textContent = SUN;
      if (btn) {
        btn.setAttribute("aria-pressed", "true");
        btn.setAttribute("aria-label", "Switch to light mode");
      }
    }
  }

  function initTheme() {
    var stored = getStoredTheme();
    var theme = stored === "light" || stored === "dark" ? stored : "dark";
    applyTheme(theme);
    var btn = $("#theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var next = document.documentElement.classList.contains("dark")
          ? "light"
          : "dark";
        applyTheme(next);
        storeTheme(next);
      });
    }
  }

  // ---------------------------------------------------------------
  // Card rendering
  // ---------------------------------------------------------------
  function categoryBadge(category) {
    if (category === "flagship") {
      return (
        '<span class="inline-flex items-center gap-1 rounded-full bg-cinnabar/15 px-2.5 py-0.5 text-xs font-semibold text-cinnabar ring-1 ring-cinnabar/30">' +
        '<span class="h-1.5 w-1.5 rounded-full bg-cinnabar"></span>Flagship</span>'
      );
    }
    if (category === "lighter") {
      return (
        '<span class="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-amber-500/30 dark:text-amber-300">' +
        '<span class="h-1.5 w-1.5 rounded-full bg-amber-500"></span>Lighter</span>'
      );
    }
    return (
      '<span class="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-500/30 dark:text-emerald-300">' +
      '<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>Creator Templates</span>'
    );
  }

  function renderCard(agent) {
    var article = document.createElement("article");
    article.className =
      "agent-card group flex h-full flex-col rounded-xl border border-parchment-muted bg-white p-5 shadow-card dark:border-ink-line dark:bg-ink-soft dark:shadow-card-dark";
    article.dataset.slug = agent.slug;
    article.dataset.category = agent.category;
    article.dataset.kind = agent.kind;
    article.dataset.search = (
      agent.name +
      " " +
      agent.slug +
      " " +
      agent.tagline +
      " " +
      (agent.tags || []).join(" ")
    ).toLowerCase();

    var installCommand = "grok-agent install " + agent.slug;
    var isTeaser = agent.isTeaser === true;
    var primaryButtonHtml = isTeaser
      ? '<a href="' +
        escapeHtml(agent.sourceUrl) +
        '" class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-cinnabar px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-cinnabar-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cinnabar focus-visible:ring-offset-2 dark:focus-visible:ring-offset-ink-soft">Browse 22 templates &rarr;</a>'
      : '<button type="button" class="copy-btn inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-cinnabar bg-cinnabar px-3 py-2 font-mono text-xs font-semibold text-white shadow-sm transition hover:bg-cinnabar-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cinnabar focus-visible:ring-offset-2 dark:focus-visible:ring-offset-ink-soft" data-copy="' +
        escapeHtml(installCommand) +
        '" aria-label="Copy ' +
        escapeHtml(installCommand) +
        ' to clipboard"><span class="copy-label" aria-hidden="false">grok install this</span></button>';

    article.innerHTML =
      '<div class="mb-3 flex items-start justify-between gap-3">' +
      '<div class="flex flex-col gap-1.5">' +
      categoryBadge(agent.category) +
      "</div>" +
      "</div>" +
      '<h3 class="text-lg font-semibold leading-tight tracking-tight">' +
      escapeHtml(agent.name) +
      "</h3>" +
      (isTeaser
        ? ""
        : '<p class="mt-1 font-mono text-xs text-parchment-ink/60 dark:text-parchment/55">' +
          escapeHtml(agent.slug) +
          "</p>") +
      '<p class="mt-3 flex-1 text-sm leading-relaxed text-parchment-ink/80 dark:text-parchment/75">' +
      escapeHtml(agent.tagline) +
      "</p>" +
      '<div class="mt-5 flex items-center gap-2">' +
      primaryButtonHtml +
      '<a href="' +
      escapeHtml(agent.sourceUrl) +
      '" target="_blank" rel="noopener" class="inline-flex items-center justify-center rounded-lg border border-parchment-muted bg-parchment px-3 py-2 text-xs font-semibold text-parchment-ink shadow-sm transition hover:border-cinnabar hover:text-cinnabar focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cinnabar focus-visible:ring-offset-2 dark:border-ink-line dark:bg-ink dark:text-parchment dark:focus-visible:ring-offset-ink-soft" aria-label="View source for ' +
      escapeHtml(agent.name) +
      ' on GitHub">View source</a>' +
      "</div>";

    return article;
  }

  function renderGrid() {
    var grid = $("#grid");
    if (!grid) return;
    grid.innerHTML = "";
    AGENTS.forEach(function (agent) {
      grid.appendChild(renderCard(agent));
    });
  }

  // ---------------------------------------------------------------
  // Search + filter
  // ---------------------------------------------------------------
  var state = {
    query: "",
    filter: "all",
  };

  function applyFilters() {
    var grid = $("#grid");
    if (!grid) return;
    var cards = $all(".agent-card", grid);
    var visible = 0;
    var query = state.query.trim().toLowerCase();
    cards.forEach(function (card) {
      var matchesFilter =
        state.filter === "all" || card.dataset.category === state.filter;
      var matchesQuery = query === "" || card.dataset.search.indexOf(query) !== -1;
      var show = matchesFilter && matchesQuery;
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });
    var empty = $("#empty-state");
    if (empty) empty.classList.toggle("hidden", visible !== 0);
  }

  function initSearch() {
    var input = $("#search");
    if (!input) return;
    input.addEventListener("input", function (event) {
      state.query = event.target.value || "";
      applyFilters();
    });
  }

  function initFilters() {
    var pills = $all(".filter-pill");
    if (pills.length === 0) return;
    pills.forEach(function (pill) {
      pill.addEventListener("click", function () {
        var filter = pill.dataset.filter || "all";
        state.filter = filter;
        pills.forEach(function (other) {
          var active = other === pill;
          other.classList.toggle("is-active", active);
          other.setAttribute("aria-selected", active ? "true" : "false");
        });
        applyFilters();
      });
    });
  }

  // ---------------------------------------------------------------
  // Copy-to-clipboard
  // ---------------------------------------------------------------
  function announce(message) {
    var live = $("#sr-status");
    if (!live) return;
    live.textContent = "";
    // Re-set on next tick so SR re-announces identical messages.
    window.setTimeout(function () {
      live.textContent = message;
    }, 30);
  }

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "absolute";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (err) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  function flashCopied(button) {
    var label = $(".copy-label", button);
    var original = label ? label.textContent : button.textContent;
    button.classList.add("is-copied");
    button.disabled = true;
    if (label) {
      label.textContent = "Copied!";
    } else {
      button.textContent = "Copied!";
    }
    window.setTimeout(function () {
      button.classList.remove("is-copied");
      button.disabled = false;
      if (label) {
        label.textContent = original;
      } else {
        button.textContent = original;
      }
    }, 2000);
  }

  function initCopyButtons() {
    document.addEventListener("click", function (event) {
      var btn = event.target.closest && event.target.closest(".copy-btn");
      if (!btn) return;
      event.preventDefault();
      var text = btn.dataset.copy || "";
      if (!text) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            flashCopied(btn);
            announce("Copied: " + text);
          },
          function () {
            if (fallbackCopy(text)) {
              flashCopied(btn);
              announce("Copied: " + text);
            } else {
              announce("Copy failed. Please copy manually: " + text);
            }
          },
        );
      } else if (fallbackCopy(text)) {
        flashCopied(btn);
        announce("Copied: " + text);
      } else {
        announce("Copy failed. Please copy manually: " + text);
      }
    });
  }

  // ---------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------
  function boot() {
    initTheme();
    renderGrid();
    initSearch();
    initFilters();
    initCopyButtons();
    applyFilters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
