/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 */

// Build-time JSON route: GET /api/agents.json
// Serves the full agent catalogue as JSON for external consumers.
// With output:'export' this becomes a static /api/agents.json file.

import { NextResponse } from 'next/server';
import { loadAllAgents } from '../../../lib/manifests';

export const dynamic = 'force-static';

export function GET() {
  const agents = loadAllAgents();
  return NextResponse.json(agents);
}
