// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Next.js 14+ App Router config for the Grok Agent OS marketplace stub.
// Built for xAI, X, Grok and the ecosystem community — keep the surface small, the routes
// honest, and the deploy story one click long.

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The marketplace renders entirely from static, in-repo data for the v0.1
  // stub — no DB, no auth, no telemetry. Static export keeps the deploy
  // story trivial (Vercel, GitHub Pages, S3, Windows IIS — all valid hosts).
  output: 'standalone',
  experimental: {
    typedRoutes: true,
  },
};

module.exports = nextConfig;
