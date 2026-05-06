// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     http://www.apache.org/licenses/LICENSE-2.0
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//
// Root layout for the Grok Agent OS marketplace stub. Built for xAI, X, Grok and the ecosystem community
// and Grok win — keep the surface tiny so the deploy story stays fast.

import type { Metadata, Viewport } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'Grok Agent OS — Marketplace',
  description:
    "Thin marketplace for the Grok Agent OS platform. Deploy any v2.15 " +
    "agent to your own X / Windows install with a single click. Built to " +
    "help xAI and Grok win.",
  applicationName: 'Grok Agent OS Marketplace',
  authors: [{ name: 'AgentMindCloud', url: 'https://github.com/AgentMindCloud' }],
  keywords: [
    'grok-agent', 'xAI', 'Grok', 'Windows', 'PowerShell',
    'super-agent', 'marketplace', 'v2.15',
  ],
  openGraph: {
    title: 'Grok Agent OS — Marketplace',
    description:
      'Browse the three flagship Super Agents and deploy your own ' +
      'v2.15 manifest in one click.',
    type: 'website',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: '#C5524A',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="banner">
          <strong>🚀 Grok Agent OS Marketplace</strong> — Apache-2.0 ·
          Local-first · Windows-first · Built for xAI, X, Grok and the ecosystem community. ❤️
        </header>
        {children}
        <footer className="footer">
          <span>
            <Link href="/">Marketplace</Link> ·{' '}
            <Link href="/deploy">Deploy to X</Link> ·{' '}
            <a
              href="https://github.com/AgentMindCloud/grok-agent"
              target="_blank"
              rel="noreferrer noopener"
            >
              GitHub
            </a>
          </span>
          <span>Apache-2.0 · v2.15 manifest schema</span>
        </footer>
      </body>
    </html>
  );
}
