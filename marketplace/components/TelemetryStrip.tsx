/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

'use client';

// TODO: scroll ticker with live-style agent count / version / platform info

interface TelemetryStripProps {
  agentCount: number;
}

export default function TelemetryStrip({ agentCount }: TelemetryStripProps) {
  return (
    <div className="telemetry-strip" role="status" aria-label="System status">
      <span>AGENTS: {agentCount}</span>
      <span>SCHEMA: v2.15</span>
      <span>PLATFORM: Windows 11 · PowerShell</span>
      <span>STATUS: ONLINE</span>
    </div>
  );
}
