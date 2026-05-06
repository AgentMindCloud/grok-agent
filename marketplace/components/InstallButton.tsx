/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

'use client';

import { useState } from 'react';

interface InstallButtonProps {
  copyText: string;
  label?: string;
}

// TODO: replace inline toast with a proper toast component
export default function InstallButton({ copyText, label = 'Install — copy command' }: InstallButtonProps) {
  const [state, setState] = useState<'idle' | 'copied' | 'error'>('idle');

  function handleClick() {
    if (!navigator?.clipboard) { setState('error'); return; }
    navigator.clipboard.writeText(copyText).then(
      () => { setState('copied'); setTimeout(() => setState('idle'), 1800); },
      () => { setState('error'); setTimeout(() => setState('idle'), 1800); },
    );
  }

  return (
    <button type="button" className="install-btn" onClick={handleClick} aria-live="polite">
      {state === 'copied' ? '✓ Copied!' : state === 'error' ? '✗ Failed' : label}
    </button>
  );
}
