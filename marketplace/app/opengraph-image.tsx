/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

// Root OG image — 1200×630, rendered at build time via Next.js ImageResponse.
// TODO: style with terminal/CRT aesthetic matching globals.css

import { ImageResponse } from 'next/og';

export const runtime = 'edge';
export const alt = 'Grok Agent OS — Marketplace';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function RootOGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          background: '#070B0D',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'monospace',
          color: '#00FF41',
        }}
      >
        <div style={{ fontSize: 64, fontWeight: 700, letterSpacing: 4 }}>
          GROK AGENT OS
        </div>
        <div style={{ fontSize: 28, marginTop: 16, color: '#7FCC8F' }}>
          Marketplace · v2.15 · Built for xAI, X, Grok and the ecosystem community
        </div>
      </div>
    ),
    { ...size },
  );
}
