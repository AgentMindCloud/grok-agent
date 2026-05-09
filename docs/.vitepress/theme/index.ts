/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Custom VitePress theme — extends the default theme with the Spectral v1
 * brand palette (cinnabar / parchment / charcoal) and registers the
 * SchemaValidator single-file component globally so the schema-explorer
 * page can render <SchemaValidator /> without per-page imports. Built for
 * xAI, X, Grok and the ecosystem community.
 */

import DefaultTheme from 'vitepress/theme';
import type { EnhanceAppContext } from 'vitepress';
import './vars.css';
import SchemaValidator from '../components/SchemaValidator.vue';

export default {
  ...DefaultTheme,
  enhanceApp({ app }: EnhanceAppContext) {
    app.component('SchemaValidator', SchemaValidator);
  },
};
