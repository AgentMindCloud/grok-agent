/**
 * Copyright 2026 AgentMindCloud
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *     http://www.apache.org/licenses/LICENSE-2.0
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *
 * GeneratorWizard — Client Component for the AI Agent Generator wizard.
 *
 * Four numbered steps:
 *   1. Paste source (README / spec / description; min 100 chars)
 *   2. Choose kind (8 v2.15 kinds with one-line tooltips)
 *   3. Generate + preview (POST /api/generate, render <ManifestPreview/>)
 *   4. Submit as PR (render <GeneratorPRButton/>)
 *
 * The preview + PR-button components are owned by a sibling worker. We
 * dynamic-import them so this file builds even before those components
 * land — a friendly placeholder renders in the meantime.
 *
 * Spectral v1 colors are applied via inline styles (charcoal #0A0A0A,
 * cinnabar #FF1E70, parchment #F4ECDA, teal #00E0D5) so the wizard works
 * without globals.css edits.
 */

'use client';

import { useReducer, useState } from 'react';
import dynamic from 'next/dynamic';

// ---------------------------------------------------------------------------
// Spectral v1 palette (inlined so this component is self-contained)
// ---------------------------------------------------------------------------
const SPECTRAL = {
  charcoal: '#0A0A0A',
  cinnabar: '#FF1E70',
  parchment: '#F4ECDA',
  teal: '#00E0D5',
  rule: 'rgba(10, 10, 10, 0.18)',
  muted: '#5A5A5F',
  cinnabarFade: 'rgba(255, 30, 112, 0.10)',
} as const;

// ---------------------------------------------------------------------------
// Lazy sibling components (owned elsewhere). Graceful placeholders render
// while those files are still under construction.
// ---------------------------------------------------------------------------
const ManifestPreview = dynamic<{ yaml: string }>(
  () =>
    import('./ManifestPreview').catch(() => ({
      default: function ManifestPreviewFallback({ yaml }: { yaml: string }) {
        return (
          <pre
            style={{
              background: SPECTRAL.charcoal,
              color: SPECTRAL.parchment,
              padding: '16px',
              borderRadius: 8,
              overflowX: 'auto',
              fontSize: '0.85rem',
              lineHeight: 1.5,
            }}
          >
            <code>{yaml}</code>
          </pre>
        );
      },
    })),
  { ssr: false, loading: () => <p style={{ color: SPECTRAL.muted }}>Loading preview…</p> },
);

const GeneratorPRButton = dynamic<{ yaml: string; kind: string }>(
  () =>
    import('./GeneratorPRButton').catch(() => ({
      default: function GeneratorPRButtonFallback() {
        return (
          <button
            type="button"
            disabled
            style={{
              background: SPECTRAL.muted,
              color: SPECTRAL.parchment,
              padding: '12px 18px',
              borderRadius: 6,
              border: 'none',
              cursor: 'not-allowed',
            }}
          >
            Open pull request (component not yet available)
          </button>
        );
      },
    })),
  { ssr: false, loading: () => <p style={{ color: SPECTRAL.muted }}>Loading submit button…</p> },
);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type StepIndex = 1 | 2 | 3 | 4;

type ManifestKind =
  | 'agent'
  | 'finance-dashboard'
  | 'alpha-engine'
  | 'creator-payout-optimizer'
  | 'vision-analyzer'
  | 'super-agent'
  | 'x-native'
  | 'creator-template';

interface KindOption {
  value: ManifestKind;
  label: string;
  tooltip: string;
}

const KIND_OPTIONS: KindOption[] = [
  {
    value: 'agent',
    label: 'agent',
    tooltip: 'Generic single-purpose agent — the catch-all v2.15 kind.',
  },
  {
    value: 'finance-dashboard',
    label: 'finance-dashboard',
    tooltip: 'Streamlit-style dashboard for X Money creator finances (companion view).',
  },
  {
    value: 'alpha-engine',
    label: 'alpha-engine',
    tooltip: 'Cashtag / market signal engine over public APIs and X search.',
  },
  {
    value: 'creator-payout-optimizer',
    label: 'creator-payout-optimizer',
    tooltip: 'Optimizer that ranks payout strategies for X creators.',
  },
  {
    value: 'vision-analyzer',
    label: 'vision-analyzer',
    tooltip: 'Multimodal analyzer for receipts, charts, and screenshots.',
  },
  {
    value: 'super-agent',
    label: 'super-agent',
    tooltip: 'Multi-tool orchestrated agent with memory and self-improvement.',
  },
  {
    value: 'x-native',
    label: 'x-native',
    tooltip: 'Agent that lives natively on X (DMs, mentions, replies).',
  },
  {
    value: 'creator-template',
    label: 'creator-template',
    tooltip: 'Lightweight reusable template for creator workflows.',
  },
];

interface GeneratedResult {
  yaml: string;
}

interface WizardState {
  step: StepIndex;
  source: string;
  kind: ManifestKind;
  loading: boolean;
  result: GeneratedResult | null;
  error: { message: string; detail: string } | null;
}

type WizardAction =
  | { type: 'goto'; step: StepIndex }
  | { type: 'set-source'; value: string }
  | { type: 'set-kind'; value: ManifestKind }
  | { type: 'generate-start' }
  | { type: 'generate-success'; result: GeneratedResult }
  | { type: 'generate-fail'; message: string; detail: string }
  | { type: 'reset-error' };

const INITIAL_STATE: WizardState = {
  step: 1,
  source: '',
  kind: 'agent',
  loading: false,
  result: null,
  error: null,
};

const MIN_SOURCE_CHARS = 100;

function reducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'goto':
      return { ...state, step: action.step };
    case 'set-source':
      return { ...state, source: action.value };
    case 'set-kind':
      return { ...state, kind: action.value };
    case 'generate-start':
      return { ...state, loading: true, error: null, result: null };
    case 'generate-success':
      return { ...state, loading: false, result: action.result, error: null };
    case 'generate-fail':
      return {
        ...state,
        loading: false,
        result: null,
        error: { message: action.message, detail: action.detail },
      };
    case 'reset-error':
      return { ...state, error: null };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Stepper UI
// ---------------------------------------------------------------------------
const STEP_LABELS: Record<StepIndex, string> = {
  1: 'Paste source',
  2: 'Choose kind',
  3: 'Generate + preview',
  4: 'Submit as PR',
};

function Stepper({ active }: { active: StepIndex }) {
  const steps: StepIndex[] = [1, 2, 3, 4];
  return (
    <ol
      role="list"
      aria-label="Wizard progress"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '12px',
        listStyle: 'none',
        padding: 0,
        margin: '0 0 24px',
      }}
    >
      {steps.map((n) => {
        const isActive = n === active;
        const isDone = n < active;
        return (
          <li
            key={n}
            aria-current={isActive ? 'step' : undefined}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flex: '1 1 180px',
              minWidth: 0,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: isActive
                  ? SPECTRAL.cinnabar
                  : isDone
                  ? SPECTRAL.teal
                  : SPECTRAL.parchment,
                color: isActive || isDone ? SPECTRAL.parchment : SPECTRAL.charcoal,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                border: `1px solid ${SPECTRAL.rule}`,
                flexShrink: 0,
              }}
            >
              {n}
            </span>
            <span
              style={{
                color: isActive ? SPECTRAL.charcoal : SPECTRAL.muted,
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.95rem',
              }}
            >
              {STEP_LABELS[n]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Disclaimer banner
// ---------------------------------------------------------------------------
function DisclaimerBanner() {
  return (
    <div
      role="note"
      style={{
        background: SPECTRAL.cinnabarFade,
        border: `1px solid ${SPECTRAL.cinnabar}`,
        color: SPECTRAL.charcoal,
        padding: '12px 16px',
        borderRadius: 6,
        margin: '0 0 24px',
        fontSize: '0.92rem',
        lineHeight: 1.5,
      }}
    >
      <strong>Beta.</strong> Manifests need human review before merge. Not
      legal/financial advice.
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step bodies
// ---------------------------------------------------------------------------
function StepPasteSource({
  source,
  onChange,
}: {
  source: string;
  onChange: (v: string) => void;
}) {
  const charCount = source.length;
  const meetsMin = charCount >= MIN_SOURCE_CHARS;
  return (
    <section aria-labelledby="step-1-heading">
      <h2 id="step-1-heading" style={{ marginTop: 0 }}>
        Step 1 — Paste source
      </h2>
      <p style={{ color: SPECTRAL.muted }}>
        Paste an existing README, project description, or feature spec. The
        more concrete the source, the better the draft manifest.
      </p>
      <label
        htmlFor="source-input"
        style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}
      >
        Source text
      </label>
      <textarea
        id="source-input"
        value={source}
        onChange={(e) => onChange(e.target.value)}
        rows={14}
        placeholder="# My agent&#10;A short description of what the agent does, who it serves, and which APIs it talks to..."
        style={{
          width: '100%',
          background: SPECTRAL.parchment,
          color: SPECTRAL.charcoal,
          border: `1px solid ${SPECTRAL.rule}`,
          borderRadius: 6,
          padding: '12px 14px',
          fontFamily: 'var(--mono-stack, ui-monospace, SFMono-Regular, monospace)',
          fontSize: '0.9rem',
          lineHeight: 1.5,
          resize: 'vertical',
        }}
      />
      <p
        aria-live="polite"
        style={{
          marginTop: 8,
          fontSize: '0.85rem',
          color: meetsMin ? SPECTRAL.muted : SPECTRAL.cinnabar,
        }}
      >
        {charCount.toLocaleString('en-US')} characters
        {meetsMin
          ? ' — ready to advance.'
          : ` — need at least ${MIN_SOURCE_CHARS} to advance.`}
      </p>
    </section>
  );
}

function StepChooseKind({
  kind,
  onChange,
}: {
  kind: ManifestKind;
  onChange: (k: ManifestKind) => void;
}) {
  return (
    <section aria-labelledby="step-2-heading">
      <h2 id="step-2-heading" style={{ marginTop: 0 }}>
        Step 2 — Choose kind
      </h2>
      <p style={{ color: SPECTRAL.muted }}>
        Pick the v2.15 kind that best fits the agent. Hover any option for a
        one-line description.
      </p>
      <fieldset
        style={{
          border: `1px solid ${SPECTRAL.rule}`,
          borderRadius: 6,
          padding: '14px 16px',
          margin: 0,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '10px',
        }}
      >
        <legend
          style={{
            padding: '0 6px',
            color: SPECTRAL.muted,
            fontSize: '0.85rem',
          }}
        >
          v2.15 kind
        </legend>
        {KIND_OPTIONS.map((opt) => {
          const checked = kind === opt.value;
          return (
            <label
              key={opt.value}
              title={opt.tooltip}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '10px 12px',
                border: `1px solid ${checked ? SPECTRAL.cinnabar : SPECTRAL.rule}`,
                background: checked ? SPECTRAL.cinnabarFade : 'transparent',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              <input
                type="radio"
                name="manifest-kind"
                value={opt.value}
                checked={checked}
                onChange={() => onChange(opt.value)}
                style={{ marginTop: 4 }}
              />
              <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <code style={{ fontWeight: 700, color: SPECTRAL.charcoal }}>
                  {opt.label}
                </code>
                <span style={{ fontSize: '0.85rem', color: SPECTRAL.muted }}>
                  {opt.tooltip}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>
    </section>
  );
}

function Spinner() {
  return (
    <span
      role="status"
      aria-label="Generating"
      style={{
        display: 'inline-block',
        width: 18,
        height: 18,
        border: `3px solid ${SPECTRAL.parchment}`,
        borderTopColor: SPECTRAL.cinnabar,
        borderRadius: '50%',
        animation: 'spin 0.9s linear infinite',
        verticalAlign: 'middle',
      }}
    />
  );
}

function StepGenerate({
  state,
  onGenerate,
}: {
  state: WizardState;
  onGenerate: () => void;
}) {
  return (
    <section aria-labelledby="step-3-heading">
      <h2 id="step-3-heading" style={{ marginTop: 0 }}>
        Step 3 — Generate + preview
      </h2>
      <p style={{ color: SPECTRAL.muted }}>
        Calls <code>/api/generate</code> with your source text and the
        selected kind. Drafts are produced server-side; nothing is sent to
        any third-party from your browser.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, margin: '12px 0 18px' }}>
        <button
          type="button"
          onClick={onGenerate}
          disabled={state.loading}
          style={{
            background: state.loading ? SPECTRAL.muted : SPECTRAL.cinnabar,
            color: SPECTRAL.parchment,
            padding: '10px 18px',
            border: 'none',
            borderRadius: 6,
            fontWeight: 700,
            cursor: state.loading ? 'wait' : 'pointer',
          }}
        >
          {state.loading ? 'Generating…' : 'Generate manifest'}
        </button>
        {state.loading ? <Spinner /> : null}
      </div>

      {state.error ? (
        <div
          role="alert"
          style={{
            background: SPECTRAL.cinnabarFade,
            border: `1px solid ${SPECTRAL.cinnabar}`,
            color: SPECTRAL.charcoal,
            padding: '12px 16px',
            borderRadius: 6,
            marginBottom: 16,
          }}
        >
          <p style={{ margin: '0 0 6px', fontWeight: 700 }}>{state.error.message}</p>
          <details>
            <summary style={{ cursor: 'pointer', color: SPECTRAL.muted }}>
              Error detail
            </summary>
            <pre
              style={{
                marginTop: 8,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontSize: '0.82rem',
                color: SPECTRAL.charcoal,
              }}
            >
              {state.error.detail}
            </pre>
          </details>
        </div>
      ) : null}

      {state.result ? (
        <div>
          <h3 style={{ margin: '0 0 8px' }}>Draft manifest preview</h3>
          <ManifestPreview yaml={state.result.yaml} />
        </div>
      ) : (
        !state.loading && (
          <p style={{ color: SPECTRAL.muted, fontStyle: 'italic' }}>
            No draft yet. Click <strong>Generate manifest</strong> to produce one.
          </p>
        )
      )}
    </section>
  );
}

function StepSubmit({ state }: { state: WizardState }) {
  return (
    <section aria-labelledby="step-4-heading">
      <h2 id="step-4-heading" style={{ marginTop: 0 }}>
        Step 4 — Submit as PR
      </h2>
      <p style={{ color: SPECTRAL.muted }}>
        Open a pull request against{' '}
        <code>AgentMindCloud/grok-agent</code> with the draft manifest as
        the proposed file. A maintainer will review before merge.
      </p>
      {state.result ? (
        <GeneratorPRButton yaml={state.result.yaml} kind={state.kind} />
      ) : (
        <p style={{ color: SPECTRAL.cinnabar }}>
          No generated draft to submit. Go back to step 3 and generate one
          first.
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Wizard root
// ---------------------------------------------------------------------------
export default function GeneratorWizard() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  // Keep an explicit "submitted at least once" flag so we don't show the
  // empty-result hint on first render.
  const [, setHasGenerated] = useState(false);

  const canAdvance = (): boolean => {
    if (state.step === 1) return state.source.trim().length >= MIN_SOURCE_CHARS;
    if (state.step === 2) return Boolean(state.kind);
    if (state.step === 3) return Boolean(state.result);
    return false;
  };

  const goto = (step: StepIndex) => dispatch({ type: 'goto', step });

  async function runGenerate() {
    dispatch({ type: 'generate-start' });
    setHasGenerated(true);
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ source: state.source, kind: state.kind }),
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status} ${res.statusText}`;
        try {
          const body = await res.text();
          if (body) detail = body;
        } catch {
          // swallow — fall back to status text
        }
        dispatch({
          type: 'generate-fail',
          message:
            'The generator service returned an error. Please review the detail below and try again.',
          detail,
        });
        return;
      }
      const json = (await res.json()) as { yaml?: string };
      if (!json?.yaml) {
        dispatch({
          type: 'generate-fail',
          message: 'The generator service returned a response with no manifest YAML.',
          detail: JSON.stringify(json, null, 2),
        });
        return;
      }
      dispatch({ type: 'generate-success', result: { yaml: json.yaml } });
    } catch (err) {
      dispatch({
        type: 'generate-fail',
        message: 'Could not reach the generator service. Check your network and retry.',
        detail: err instanceof Error ? `${err.name}: ${err.message}` : String(err),
      });
    }
  }

  return (
    <section
      aria-label="AI Agent Generator wizard"
      style={{
        background: SPECTRAL.parchment,
        border: `1px solid ${SPECTRAL.rule}`,
        borderRadius: 8,
        padding: '24px',
        margin: '24px 0',
        color: SPECTRAL.charcoal,
      }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <DisclaimerBanner />
      <Stepper active={state.step} />

      {state.step === 1 ? (
        <StepPasteSource
          source={state.source}
          onChange={(v) => dispatch({ type: 'set-source', value: v })}
        />
      ) : null}
      {state.step === 2 ? (
        <StepChooseKind
          kind={state.kind}
          onChange={(k) => dispatch({ type: 'set-kind', value: k })}
        />
      ) : null}
      {state.step === 3 ? <StepGenerate state={state} onGenerate={runGenerate} /> : null}
      {state.step === 4 ? <StepSubmit state={state} /> : null}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          marginTop: 24,
          paddingTop: 16,
          borderTop: `1px solid ${SPECTRAL.rule}`,
        }}
      >
        <button
          type="button"
          onClick={() => state.step > 1 && goto((state.step - 1) as StepIndex)}
          disabled={state.step === 1}
          style={{
            background: 'transparent',
            color: state.step === 1 ? SPECTRAL.muted : SPECTRAL.charcoal,
            border: `1px solid ${SPECTRAL.rule}`,
            padding: '8px 14px',
            borderRadius: 6,
            cursor: state.step === 1 ? 'not-allowed' : 'pointer',
          }}
        >
          ← Previous
        </button>

        <span style={{ color: SPECTRAL.muted, fontSize: '0.9rem' }}>
          Step {state.step} of 4
        </span>

        <button
          type="button"
          onClick={() => state.step < 4 && canAdvance() && goto((state.step + 1) as StepIndex)}
          disabled={state.step === 4 || !canAdvance()}
          style={{
            background:
              state.step === 4 || !canAdvance() ? SPECTRAL.muted : SPECTRAL.cinnabar,
            color: SPECTRAL.parchment,
            border: 'none',
            padding: '8px 14px',
            borderRadius: 6,
            fontWeight: 700,
            cursor: state.step === 4 || !canAdvance() ? 'not-allowed' : 'pointer',
          }}
        >
          Next →
        </button>
      </div>
    </section>
  );
}
