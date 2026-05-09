/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * VitePress site config for the Grok Agent OS documentation site.
 * Built for xAI, X, Grok and the ecosystem community.
 *
 * Local dev:    cd docs && npm install && npm run docs:dev
 * Build:        cd docs && npm run docs:build
 * Preview:      cd docs && npm run docs:preview
 *
 * The site reads the existing top-level docs/*.md files in place — no
 * file reorganisation, no broken GitHub-rendered links. The sidebar
 * groups them into four logical sections: Getting Started, Standards,
 * Reports, Adoption.
 */

import { defineConfig } from 'vitepress';

export default defineConfig({
  title: 'Grok Agent OS',
  description:
    'The open Windows-first distribution layer for deploying Grok agents on X. Built for xAI, X, Grok and the ecosystem community.',
  lang: 'en-US',
  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: true, // existing docs intentionally link to GitHub-rendered URLs

  head: [
    ['link', { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' }],
    ['meta', { name: 'theme-color', content: '#FF1E70' }],
    ['meta', { property: 'og:title', content: 'Grok Agent OS' }],
    [
      'meta',
      {
        property: 'og:description',
        content:
          'One YAML manifest, one PowerShell command, one safety scanner — the open standard for shipping Grok agents on X.',
      },
    ],
  ],

  themeConfig: {
    siteTitle: 'Grok Agent OS',
    logo: { src: '/logo.svg', width: 24, height: 24, alt: 'Grok Agent OS' },

    nav: [
      { text: 'Guide', link: '/windows-guide' },
      { text: 'Standards', link: '/PROJECT_DNA' },
      { text: 'For xAI', link: '/for-xai-adoption' },
      {
        text: 'v0.1',
        items: [
          { text: 'Spec v2.15', link: 'https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/grok-agent.yaml' },
          { text: 'JSON Schema', link: 'https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/schema.json' },
          { text: 'OpenAPI', link: 'https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/openapi.yaml' },
          { text: 'Changelog', link: 'https://github.com/AgentMindCloud/grok-agent/blob/main/spec/v2.15/changelog.md' },
        ],
      },
      { text: 'GitHub', link: 'https://github.com/AgentMindCloud/grok-agent' },
    ],

    sidebar: [
      {
        text: 'Getting Started',
        collapsed: false,
        items: [
          { text: 'Overview', link: '/' },
          { text: 'Windows install guide', link: '/windows-guide' },
          { text: 'X launch thread', link: '/x-launch-thread' },
        ],
      },
      {
        text: 'Standards & Conventions',
        collapsed: false,
        items: [
          { text: 'Project DNA', link: '/PROJECT_DNA' },
          { text: 'Constraints (Hard Six)', link: '/CONSTRAINTS' },
          { text: 'Parameterized Recipes', link: '/PARAMETERIZED_RECIPES' },
          { text: 'Prompt Template', link: '/PROMPT_TEMPLATE' },
          { text: 'Sources Map', link: '/SOURCES' },
          { text: 'Schema Explorer', link: '/schema-explorer' },
        ],
      },
      {
        text: 'For xAI',
        collapsed: false,
        items: [
          { text: 'Adoption pitch', link: '/for-xai-adoption' },
          { text: 'Phase 6 kickoff', link: '/phase-6-kickoff' },
        ],
      },
      {
        text: 'Audit & Reports',
        collapsed: true,
        items: [
          { text: 'Workplan audit', link: '/workplan-audit' },
          { text: 'Audit 2026-05-06', link: '/audit-2026-05-06' },
          { text: 'Bug-fix plan 2026-05-06', link: '/bug-fix-plan-2026-05-06' },
          { text: 'Phase 3 completion report', link: '/phase-3-completion-report' },
          { text: 'Phase 3 verification report', link: '/phase-3-verification-report' },
          { text: 'Phase 4 completion report', link: '/phase-4-completion-report' },
          { text: 'Smoke-test results', link: '/smoke-test-results' },
        ],
      },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/AgentMindCloud/grok-agent' },
      { icon: 'x', link: 'https://x.com/JanSol0s' },
    ],

    footer: {
      message:
        'Apache-2.0 — built for xAI, X, Grok and the ecosystem community. ❤️',
      copyright: 'Copyright © 2026 AgentMindCloud',
    },

    editLink: {
      pattern:
        'https://github.com/AgentMindCloud/grok-agent/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    search: { provider: 'local' },

    outline: { level: [2, 3] },
  },

  // VitePress reads from the directory you point at when invoking. We
  // default to docs/ (where this config lives), so VitePress will
  // process .md files from this directory tree.
});
