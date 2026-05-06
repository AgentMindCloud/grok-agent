/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

'use client';

// TODO: boot-sequence typewriter, ASCII logo, blinking cursor

export default function TerminalHero() {
  return (
    <section className="terminal-hero">
      <pre className="ascii-logo">{`
 ██████╗ ██████╗  ██████╗ ██╗  ██╗
██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝
██║  ███╗██████╔╝██║   ██║█████╔╝
██║   ██║██╔══██╗██║   ██║██╔═██╗
╚██████╔╝██║  ██║╚██████╔╝██║  ██╗
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝
AGENT OS — MARKETPLACE`}</pre>
      <p className="terminal-prompt">
        <span className="prompt-prefix">$</span>{' '}
        <span className="prompt-text">grok install this</span>
        <span className="cursor blink">█</span>
      </p>
    </section>
  );
}
