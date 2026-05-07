/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

/** @type {import('next').NextConfig} */
//
// `basePath: '/grok-agent'` + `trailingSlash: true` are required for the
// static export to load assets correctly on `https://agentmindcloud.github.io/grok-agent/`.
// Without basePath, every CSS/JS/asset URL resolves to `/` (root) and 404s
// on a project-pages deploy. trailingSlash keeps internal links pointing at
// directory-style URLs (`/foo/` instead of `/foo`) which GitHub Pages serves
// without a redirect.
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: 'export',
  basePath: '/grok-agent',
  trailingSlash: true,
  images: { unoptimized: true },
};

module.exports = nextConfig;
