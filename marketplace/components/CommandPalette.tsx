/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

'use client';

// TODO: wire up cmdk — keyboard shortcut Ctrl+K / ⌘K, agent search + navigation
// Requires: npm install cmdk

import { useEffect, useState } from 'react';

export default function CommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape') setOpen(false);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!open) return null;

  return (
    <div className="cmd-backdrop" onClick={() => setOpen(false)}>
      <div className="cmd-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal aria-label="Command palette">
        <input className="cmd-input" placeholder="Search agents…" autoFocus />
        <p className="cmd-hint">Press Esc to close · ↑↓ to navigate</p>
      </div>
    </div>
  );
}
