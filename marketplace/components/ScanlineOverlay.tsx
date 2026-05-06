/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

'use client';

// Fixed-position CRT scanline + vignette overlay. Pointer-events: none.
export default function ScanlineOverlay() {
  return <div className="scanline-overlay" aria-hidden="true" />;
}
