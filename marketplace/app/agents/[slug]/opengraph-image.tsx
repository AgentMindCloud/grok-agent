/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

// Per-agent OG image — 1200×630, generated at build time.
// TODO: render agent name + tagline with terminal styling

import { ImageResponse } from 'next/og';
import { findAgentBySlug } from '../../../lib/manifests';

export const runtime = 'edge';
export const alt = 'Grok Agent OS — Agent detail';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function AgentOGImage({ params }: { params: { slug: string } }) {
  const agent = findAgentBySlug(params.slug);
  const name = agent?.displayName ?? params.slug;
  const tagline = agent?.tagline ?? '';

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
          padding: 64,
        }}
      >
        <div style={{ fontSize: 52, fontWeight: 700, textAlign: 'center' }}>{name}</div>
        {tagline && (
          <div style={{ fontSize: 24, marginTop: 20, color: '#7FCC8F', textAlign: 'center' }}>
            {tagline}
          </div>
        )}
        <div style={{ fontSize: 18, marginTop: 32, color: '#3A7048' }}>
          grok install this · Grok Agent OS Marketplace
        </div>
      </div>
    ),
    { ...size },
  );
}
