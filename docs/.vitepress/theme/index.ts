/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Custom VitePress theme — extends the default theme with the Spectral v1
 * brand palette (cinnabar / parchment / charcoal). No Vue components are
 * registered yet; this is a thin styling layer that keeps the upgrade
 * path simple. Built for xAI, X, Grok and the ecosystem community.
 */

import DefaultTheme from 'vitepress/theme';
import './vars.css';

export default {
  ...DefaultTheme,
};
