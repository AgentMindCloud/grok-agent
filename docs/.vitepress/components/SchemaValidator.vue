<!--
  Copyright 2026 AgentMindCloud
  Licensed under the Apache License, Version 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  SchemaValidator.vue — paste-and-validate explorer for the v2.15
  grok-agent.yaml manifest. Loads the canonical JSON Schema from
  /spec/grok-manifest.json (served by VitePress from docs/public/) and
  validates the user-pasted YAML in the browser using Ajv 8 + js-yaml 4
  loaded from esm.sh on demand. No npm dependencies are added to the
  VitePress build — the CDN modules are imported lazily on the client
  via dynamic import() so the SSR pass remains dependency-free.

  Layered checks (in order):
    1. YAML parse  (js-yaml)
    2. JSON Schema validation against the v2.15 schema (Ajv strict:false,
       allErrors:true, JSON Schema draft 2020-12 via ajv/dist/2020)
    3. Constitution warnings (client-side, mirror safety/scanner.py):
         - missing metadata.tagline
         - provenance.append_only must be exactly true
         - kind == "super-agent" requires a constitution block
         - finance kinds require safety.disclaimers.not_financial_advice

  Built for xAI, X, Grok and the ecosystem community.
-->

<script setup lang="ts">
import { ref, computed, onMounted, shallowRef } from 'vue';

// ---- reactive state ---------------------------------------------------

const yamlText = ref<string>(`# Paste your grok-agent.yaml here, or use this minimal seed.
version: 2.15
kind: creator-template
metadata:
  name: example-agent
  slug: example-agent
  description: A short description of what this agent does.
  tagline: Built for xAI, X, Grok and the ecosystem community.
  authors:
    - name: Your Name
      handle: "@yourhandle"
  license: Apache-2.0
provenance:
  source_repo: github.com/AgentMindCloud/grok-agent
  append_only: true
runtime:
  language: python
  entrypoint: app.py
`);

const ready = ref<boolean>(false);                 // CDN deps loaded
const loadError = ref<string | null>(null);        // CDN load failure
const schemaError = ref<string | null>(null);      // schema fetch failure
const yamlError = ref<string | null>(null);        // YAML parse failure
const schemaErrors = ref<Array<{ path: string; message: string }>>([]);
const constitutionWarnings = ref<string[]>([]);
const parsedDoc = shallowRef<any>(null);

const ajvValidate = shallowRef<((doc: any) => boolean) | null>(null);
const yamlLib = shallowRef<any>(null);

// ---- derived UI flags -------------------------------------------------

const isValid = computed(
  () =>
    ready.value &&
    !yamlError.value &&
    schemaErrors.value.length === 0 &&
    parsedDoc.value !== null,
);

const statusLabel = computed(() => {
  if (!ready.value) return 'Loading validator...';
  if (yamlError.value) return 'YAML parse error';
  if (schemaErrors.value.length > 0)
    return `${schemaErrors.value.length} schema error(s)`;
  if (parsedDoc.value === null) return 'No document';
  return 'Schema valid';
});

const statusClass = computed(() => {
  if (!ready.value) return 'sv-status sv-status--loading';
  if (yamlError.value || schemaErrors.value.length > 0)
    return 'sv-status sv-status--error';
  if (parsedDoc.value === null) return 'sv-status sv-status--loading';
  return 'sv-status sv-status--valid';
});

// ---- bootstrapping (client-only) --------------------------------------

async function bootstrap(): Promise<void> {
  try {
    // Ajv 2020-12 entry-point + js-yaml from esm.sh — both ESM-shimmed.
    const [ajvMod, yamlMod, schemaResp] = await Promise.all([
      import(/* @vite-ignore */ 'https://esm.sh/ajv@8.17.1/dist/2020.js'),
      import(/* @vite-ignore */ 'https://esm.sh/js-yaml@4.1.0'),
      fetch('/spec/grok-manifest.json'),
    ]);

    if (!schemaResp.ok) {
      schemaError.value = `Failed to load schema: HTTP ${schemaResp.status}`;
      return;
    }
    const schema = await schemaResp.json();

    const AjvCtor = (ajvMod as any).default || (ajvMod as any).Ajv2020;
    const ajv = new AjvCtor({
      strict: false,
      allErrors: true,
      allowUnionTypes: true,
    });

    // Some manifests reference the $id of the schema. Strip it before
    // compilation so Ajv does not register a global URI it cannot fetch.
    if (schema.$id) delete schema.$id;

    ajvValidate.value = ajv.compile(schema);
    yamlLib.value = (yamlMod as any).default || yamlMod;
    ready.value = true;
    runValidation();
  } catch (err: any) {
    loadError.value =
      'Could not load Ajv or js-yaml from esm.sh. Check your network and reload the page. Underlying error: ' +
      (err && err.message ? err.message : String(err));
  }
}

onMounted(bootstrap);

// ---- validation pipeline ----------------------------------------------

function runValidation(): void {
  if (!ready.value) return;

  yamlError.value = null;
  schemaErrors.value = [];
  constitutionWarnings.value = [];
  parsedDoc.value = null;

  const text = yamlText.value;
  if (!text || !text.trim()) {
    return;
  }

  let doc: any;
  try {
    doc = yamlLib.value.load(text);
  } catch (err: any) {
    yamlError.value = err && err.message ? err.message : String(err);
    return;
  }

  if (doc === null || typeof doc !== 'object') {
    yamlError.value = 'YAML did not parse to an object at the top level.';
    return;
  }

  parsedDoc.value = doc;

  const validator = ajvValidate.value;
  if (validator) {
    const ok = validator(doc);
    if (!ok) {
      const errs = ((validator as any).errors || []) as any[];
      schemaErrors.value = errs.map((e) => ({
        path: e.instancePath || '(root)',
        message: `${e.message || 'invalid'}${
          e.params ? ' — ' + JSON.stringify(e.params) : ''
        }`,
      }));
    }
  }

  constitutionWarnings.value = checkConstitution(doc);
}

function checkConstitution(doc: any): string[] {
  const warnings: string[] = [];

  // 1. metadata.tagline must exist
  const tagline = doc?.metadata?.tagline;
  if (!tagline || typeof tagline !== 'string' || !tagline.trim()) {
    warnings.push(
      'metadata.tagline is missing — every manifest must declare a tagline so the agent surfaces in catalogs.',
    );
  }

  // 2. provenance.append_only must be exactly boolean true
  const appendOnly = doc?.provenance?.append_only;
  if (appendOnly !== true) {
    warnings.push(
      'provenance.append_only must be exactly true — Constitution Article III requires append-only provenance for every agent.',
    );
  }

  // 3. super-agent kinds require a constitution block
  if (doc?.kind === 'super-agent') {
    const c = doc?.constitution;
    if (!c || typeof c !== 'object') {
      warnings.push(
        'kind == "super-agent" requires a top-level constitution block (rules, consent_gates, hard_refusals).',
      );
    }
  }

  // 4. finance kinds need a not_financial_advice disclaimer
  const financeKinds = new Set([
    'finance-dashboard',
    'alpha-engine',
    'creator-payout-optimizer',
    'vision-analyzer',
    'finance-tool',
  ]);
  if (financeKinds.has(doc?.kind)) {
    const nfa = doc?.safety?.disclaimers?.not_financial_advice;
    if (!nfa) {
      warnings.push(
        'Finance kind detected — safety.disclaimers.not_financial_advice must be set so the "Not financial advice" banner renders on every UI surface.',
      );
    }
  }

  return warnings;
}

function onInput(): void {
  runValidation();
}

function loadSampleSuperAgent(): void {
  yamlText.value = `version: 2.15
kind: super-agent
metadata:
  name: living-narrative-fabric
  slug: living-narrative-fabric
  description: Versioned synthesis of X, news, academic, and personal data with full provenance.
  tagline: Built for xAI, X, Grok and the ecosystem community.
  authors:
    - name: AgentMindCloud
      handle: "@JanSol0s"
  license: Apache-2.0
provenance:
  source_repo: github.com/AgentMindCloud/grok-agent
  append_only: true
constitution:
  rules:
    - Never fabricate sources.
    - Surface contradictions explicitly.
  consent_gates:
    - Real-world actions require explicit user approval.
  hard_refusals:
    - Refuse to delete provenance entries.
runtime:
  language: python
  entrypoint: app.py
`;
  runValidation();
}

function loadSampleFinance(): void {
  yamlText.value = `version: 2.15
kind: finance-dashboard
metadata:
  name: x-money-companion-dashboard
  slug: x-money-companion-dashboard
  description: Local-first dashboard for X Money creator earnings, with Grok insights.
  tagline: Built for xAI, X, Grok and the ecosystem community.
  authors:
    - name: AgentMindCloud
      handle: "@JanSol0s"
  license: Apache-2.0
provenance:
  source_repo: github.com/AgentMindCloud/grok-agent
  append_only: true
safety:
  disclaimers:
    not_financial_advice: true
    not_tax_advice: true
runtime:
  language: python
  entrypoint: app.py
`;
  runValidation();
}

function clearAll(): void {
  yamlText.value = '';
  runValidation();
}
</script>

<template>
  <div class="sv-root">
    <div class="sv-toolbar">
      <span :class="statusClass">{{ statusLabel }}</span>
      <div class="sv-toolbar-spacer" />
      <button type="button" class="sv-btn" @click="loadSampleSuperAgent">
        Load Super Agent sample
      </button>
      <button type="button" class="sv-btn" @click="loadSampleFinance">
        Load Finance sample
      </button>
      <button type="button" class="sv-btn sv-btn--ghost" @click="clearAll">
        Clear
      </button>
    </div>

    <div v-if="loadError" class="sv-load-error">
      {{ loadError }}
    </div>
    <div v-if="schemaError" class="sv-load-error">
      {{ schemaError }}
    </div>

    <div class="sv-grid">
      <section class="sv-pane sv-pane--editor" aria-label="YAML editor">
        <header class="sv-pane-head">manifest YAML</header>
        <textarea
          v-model="yamlText"
          class="sv-textarea"
          spellcheck="false"
          autocorrect="off"
          autocapitalize="off"
          rows="28"
          @input="onInput"
        />
      </section>

      <section class="sv-pane sv-pane--results" aria-label="Validation results">
        <header class="sv-pane-head">results</header>

        <div v-if="!ready && !loadError" class="sv-block sv-block--loading">
          Loading Ajv 8 and js-yaml 4 from esm.sh...
        </div>

        <div v-if="yamlError" class="sv-block sv-block--error">
          <h4>YAML parse error</h4>
          <pre class="sv-pre">{{ yamlError }}</pre>
        </div>

        <div
          v-if="ready && !yamlError && schemaErrors.length === 0 && parsedDoc"
          class="sv-block sv-block--valid"
        >
          <h4>Schema valid</h4>
          <p>
            Manifest matches the v2.15 JSON Schema. Review the Constitution
            warnings below before shipping.
          </p>
        </div>

        <div v-if="schemaErrors.length > 0" class="sv-block sv-block--error">
          <h4>Schema errors ({{ schemaErrors.length }})</h4>
          <ul class="sv-list">
            <li v-for="(e, i) in schemaErrors" :key="i">
              <code class="sv-path">{{ e.path || '(root)' }}</code>
              <span class="sv-msg">{{ e.message }}</span>
            </li>
          </ul>
        </div>

        <div
          v-if="constitutionWarnings.length > 0"
          class="sv-block sv-block--warn"
        >
          <h4>Constitution warnings ({{ constitutionWarnings.length }})</h4>
          <ul class="sv-list">
            <li v-for="(w, i) in constitutionWarnings" :key="i">{{ w }}</li>
          </ul>
        </div>

        <div
          v-if="
            ready &&
            !yamlError &&
            schemaErrors.length === 0 &&
            constitutionWarnings.length === 0 &&
            parsedDoc
          "
          class="sv-block sv-block--valid"
        >
          <h4>Constitution checks pass</h4>
          <p>
            tagline present, provenance.append_only is true, kind-specific
            disclaimers in place. Ready to commit.
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.sv-root {
  --sv-cinnabar: #ff1e70;
  --sv-cinnabar-soft: rgba(255, 30, 112, 0.12);
  --sv-parchment: #f4ecda;
  --sv-charcoal: #0a0a0a;
  --sv-warn-bg: #0a0a0a;
  --sv-warn-fg: #f4ecda;
  --sv-valid: #1f9d55;
  --sv-valid-soft: rgba(31, 157, 85, 0.12);

  font-family: var(--vp-font-family-base);
  margin: 1.25rem 0 2rem;
}

.sv-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.sv-toolbar-spacer {
  flex: 1;
}

.sv-status {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.sv-status--loading {
  background: var(--vp-c-bg-alt);
  color: var(--vp-c-text-2);
}
.sv-status--valid {
  background: var(--sv-valid-soft);
  color: var(--sv-valid);
}
.sv-status--error {
  background: var(--sv-cinnabar-soft);
  color: var(--sv-cinnabar);
}

.sv-btn {
  appearance: none;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.sv-btn:hover {
  background: var(--sv-cinnabar-soft);
  border-color: var(--sv-cinnabar);
  color: var(--sv-cinnabar);
}
.sv-btn--ghost {
  background: transparent;
}

.sv-load-error {
  background: var(--sv-cinnabar-soft);
  color: var(--sv-cinnabar);
  border: 1px solid var(--sv-cinnabar);
  padding: 0.6rem 0.85rem;
  border-radius: 6px;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}

.sv-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
@media (max-width: 900px) {
  .sv-grid {
    grid-template-columns: 1fr;
  }
}

.sv-pane {
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  background: var(--vp-c-bg-soft);
  display: flex;
  flex-direction: column;
  min-height: 420px;
  overflow: hidden;
}

.sv-pane-head {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.5rem 0.85rem;
  background: var(--vp-c-bg-alt);
  color: var(--vp-c-text-2);
  border-bottom: 1px solid var(--vp-c-divider);
}

.sv-textarea {
  flex: 1;
  width: 100%;
  border: 0;
  outline: none;
  resize: vertical;
  padding: 0.85rem;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-family: var(--vp-font-family-mono);
  font-size: 0.85rem;
  line-height: 1.5;
  min-height: 380px;
}

.sv-pane--results {
  padding: 0.85rem;
  gap: 0.75rem;
}

.sv-block {
  border-radius: 6px;
  padding: 0.7rem 0.85rem;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  font-size: 0.9rem;
}
.sv-block h4 {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  font-weight: 700;
}
.sv-block p {
  margin: 0;
}
.sv-block--loading {
  color: var(--vp-c-text-2);
}
.sv-block--valid {
  border-color: var(--sv-valid);
  background: var(--sv-valid-soft);
  color: var(--sv-valid);
}
.sv-block--error {
  border-color: var(--sv-cinnabar);
  background: var(--sv-cinnabar-soft);
  color: var(--sv-cinnabar);
}
.sv-block--warn {
  border-color: var(--sv-charcoal);
  background: var(--sv-warn-bg);
  color: var(--sv-warn-fg);
}
.sv-block--warn h4 {
  color: var(--sv-warn-fg);
}

.sv-list {
  margin: 0;
  padding-left: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.sv-path {
  font-family: var(--vp-font-family-mono);
  font-size: 0.8rem;
  background: rgba(0, 0, 0, 0.08);
  padding: 0.05rem 0.35rem;
  border-radius: 4px;
  margin-right: 0.4rem;
}
.sv-msg {
  font-size: 0.85rem;
}

.sv-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--vp-font-family-mono);
  font-size: 0.8rem;
}
</style>
