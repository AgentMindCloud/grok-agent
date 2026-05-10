// Copyright 2026 AgentMindCloud
// Licensed under the Apache License, Version 2.0
// http://www.apache.org/licenses/LICENSE-2.0
//
// Eval Dashboard index page. Server Component — reads BOTH
// docs/agent-trust-scores.json (33 scored agents) AND
// docs/eval-history.json (per-agent metric run history written by
// scripts/build-eval-history.py) at build time via fs.readFileSync,
// then mounts the sortable <EvalLeaderboard> client component.
//
// Falls back to a friendly empty-state when the trust-score JSON is
// missing so a fresh clone (or a build that runs before the score
// builder has executed) still ships a valid static page. The eval
// history file is treated as optional: if absent, the leaderboard
// renders with zero runs / dash sparklines per agent.
//
// Per-slug drill-down routes are owned by the sibling worker and
// rendered under /eval/<slug>/. The leaderboard component links to
// that route from the Agent column.
//
// Spectral v1 brand: charcoal #0A0A0A, cinnabar #FF1E70, parchment
// #F4ECDA, teal #00E0D5.

import fs from 'node:fs';
import path from 'node:path';
import EvalLeaderboard, {
  type LeaderboardAgent,
  type LeaderboardHistory,
  type LeaderboardHistoryRun,
} from '../../components/EvalLeaderboard';

interface TrustScoreAgent {
  slug: string;
  category: string;
  kind: string;
  score: number;
  tier: string;
  components?: Record<string, number>;
  details?: Record<string, unknown>;
  manifest_path: string;
}

interface TrustScores {
  computed_at: string;
  constitution_version: string;
  scanner_version: string;
  formula?: string;
  weights?: Record<string, number>;
  tier_thresholds?: Record<string, number>;
  manifest_count: number;
  agents: Record<string, TrustScoreAgent>;
}

interface EvalHistoryRun {
  run_id?: string;
  ts: string;
  metrics: Record<string, number>;
  stub?: boolean;
}

interface EvalHistoryAgent {
  category?: string;
  kind?: string;
  metrics_declared?: string[];
  runs?: EvalHistoryRun[];
  latest_metrics?: Record<string, number>;
  trend_7d?: Record<string, number>;
}

interface EvalHistory {
  computed_at?: string;
  schema_version?: string;
  agent_count?: number;
  metric_count?: number;
  summary?: {
    total_runs?: number;
    agents_with_history?: number;
    agents_no_history?: number;
  };
  agents?: Record<string, EvalHistoryAgent>;
}

const TRUST_SCORES_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'agent-trust-scores.json',
);

const EVAL_HISTORY_PATH = path.resolve(
  process.cwd(),
  '..',
  'docs',
  'eval-history.json',
);

function loadTrustScores(): TrustScores | null {
  try {
    const raw = fs.readFileSync(TRUST_SCORES_PATH, 'utf-8');
    return JSON.parse(raw) as TrustScores;
  } catch {
    return null;
  }
}

function loadEvalHistory(): EvalHistory | null {
  try {
    const raw = fs.readFileSync(EVAL_HISTORY_PATH, 'utf-8');
    return JSON.parse(raw) as EvalHistory;
  } catch {
    return null;
  }
}

function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(date);
  } catch {
    return iso;
  }
}

// Reduce a metrics map (each value in 0..1) to a single 0..100 aggregate
// that lines up with the leaderboard's "score" column. Stub runs from
// build-eval-history.py emit normalised metric values, so a simple mean
// keeps the sparkline shape intact while staying inside the same scale
// the trust-score column already uses.
function aggregateRunScore(metrics: Record<string, number>): number {
  const values = Object.values(metrics).filter(
    (v) => typeof v === 'number' && !Number.isNaN(v),
  );
  if (values.length === 0) return 0;
  const mean = values.reduce((acc, v) => acc + v, 0) / values.length;
  // Clamp before scaling so a noisy metric never blows past 100.
  const clamped = Math.max(0, Math.min(1, mean));
  return Math.round(clamped * 100);
}

function buildLeaderboardInputs(
  scores: TrustScores,
  history: EvalHistory | null,
): { agents: LeaderboardAgent[]; history: LeaderboardHistory } {
  const agents: LeaderboardAgent[] = Object.values(scores.agents).map(
    (a) => ({
      slug: a.slug,
      category: a.category,
      kind: a.kind,
      score: a.score,
      tier: a.tier,
      manifest_path: a.manifest_path,
    }),
  );

  const adapted: LeaderboardHistory = {};
  if (history?.agents) {
    for (const [slug, entry] of Object.entries(history.agents)) {
      const runs = (entry.runs ?? []).filter(
        (r) => r && typeof r.ts === 'string' && r.metrics,
      );
      const adaptedRuns: LeaderboardHistoryRun[] = runs.map((r) => ({
        run_at: r.ts,
        score: aggregateRunScore(r.metrics ?? {}),
      }));
      adapted[slug] = { runs: adaptedRuns };
    }
  }

  return { agents, history: adapted };
}

interface ScoreCardProps {
  label: string;
  value: number | string;
  accent: string;
  textOnAccent?: string;
  hint?: string;
}

function ScoreCard({
  label,
  value,
  accent,
  textOnAccent,
  hint,
}: ScoreCardProps) {
  return (
    <div
      style={{
        background: 'var(--parchment)',
        border: '1px solid var(--rule)',
        borderRadius: 'var(--radius)',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        minWidth: 0,
      }}
    >
      <span
        style={{
          fontSize: '0.78rem',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--muted)',
        }}
      >
        {label}
      </span>
      <span
        style={{
          background: accent,
          color: textOnAccent ?? '#F4ECDA',
          alignSelf: 'flex-start',
          padding: '2px 12px',
          borderRadius: 'var(--radius)',
          fontSize: '1.6rem',
          fontWeight: 700,
          lineHeight: 1.15,
          fontFamily: 'var(--mono-stack)',
        }}
      >
        {typeof value === 'number' ? value.toLocaleString('en-US') : value}
      </span>
      {hint ? (
        <span style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}

function Footer() {
  return (
    <footer
      style={{
        marginTop: '48px',
        paddingTop: '20px',
        borderTop: '1px solid var(--rule)',
        color: 'var(--muted)',
        fontSize: '0.9rem',
      }}
      aria-label="Built for xAI, X, Grok and the ecosystem community."
    >
      <p style={{ margin: '0 0 8px' }}>
        Sources:{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/docs/agent-trust-scores.json"
          target="_blank"
          rel="noreferrer noopener"
        >
          docs/agent-trust-scores.json
        </a>{' '}
        ·{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/docs/eval-history.json"
          target="_blank"
          rel="noreferrer noopener"
        >
          docs/eval-history.json
        </a>{' '}
        ·{' '}
        <a
          href="https://github.com/AgentMindCloud/grok-agent/blob/main/docs/whitepaper-manifest-standard.md"
          target="_blank"
          rel="noreferrer noopener"
        >
          whitepaper-manifest-standard.md
        </a>
      </p>
      <p style={{ margin: 0 }}>
        Click any agent slug in the leaderboard to open the per-agent
        eval drill-down. Built for xAI, X, Grok and the ecosystem
        community. ❤️
      </p>
    </footer>
  );
}

function EmptyState() {
  return (
    <main>
      <section className="hero">
        <h1>Eval Dashboard</h1>
        <p className="tagline">
          The trust-score file <code>docs/agent-trust-scores.json</code>{' '}
          was not found at build time. The leaderboard renders once the
          score builder has populated the roster.
        </p>
        <div className="banner" role="note">
          Run{' '}
          <code>python scripts/build-trust-scores.py</code>{' '}
          from the repo root to generate the score file, then rebuild
          the marketplace.
        </div>
      </section>
      <section>
        <h2 className="section">What this page will show</h2>
        <p>
          A four-card scoreboard summarising the roster (total agents,
          agents with eval history, total recorded eval runs, and the
          mean trust score), followed by a sortable trust-score
          leaderboard with per-agent tier badge, run count, last-run
          timestamp, and a 7-day sparkline. The leaderboard links each
          slug to the per-agent eval drill-down route.
        </p>
        <p>
          See{' '}
          <a
            href="https://github.com/AgentMindCloud/grok-agent/blob/main/docs/whitepaper-manifest-standard.md"
            target="_blank"
            rel="noreferrer noopener"
          >
            docs/whitepaper-manifest-standard.md
          </a>{' '}
          for how the trust score is computed.
        </p>
      </section>
      <Footer />
    </main>
  );
}

export default function EvalDashboardPage() {
  const trustScores = loadTrustScores();

  if (!trustScores) {
    return <EmptyState />;
  }

  const evalHistory = loadEvalHistory();
  const { agents, history } = buildLeaderboardInputs(trustScores, evalHistory);

  const totalAgents = agents.length;
  const agentsWithHistory = Object.values(history).filter(
    (h) => h.runs.length > 0,
  ).length;
  const totalRuns = Object.values(history).reduce(
    (acc, h) => acc + h.runs.length,
    0,
  );
  const avgScore =
    totalAgents === 0
      ? 0
      : Math.round(
          agents.reduce((acc, a) => acc + (a.score ?? 0), 0) / totalAgents,
        );

  const lastUpdated = formatTimestamp(
    evalHistory?.computed_at ?? trustScores.computed_at,
  );
  const evalSchemaTag = evalHistory?.schema_version
    ? ` · eval schema v${evalHistory.schema_version}`
    : ' · eval history not yet populated';

  return (
    <main>
      <section className="hero">
        <h1>Eval Dashboard</h1>
        <p className="tagline">
          Aggregate trust score and DeepEval run history for{' '}
          <strong>{trustScores.manifest_count}</strong>{' '}
          <code>grok-agent.yaml</code> manifests in the repo. Computed by{' '}
          <code>safety/scanner.py</code> v{trustScores.scanner_version}{' '}
          against Constitution v{trustScores.constitution_version}
          {evalSchemaTag}.
        </p>
        <p className="meta">
          Last updated <strong>{lastUpdated}</strong> · See the{' '}
          <a
            href="https://github.com/AgentMindCloud/grok-agent/blob/main/docs/whitepaper-manifest-standard.md"
            target="_blank"
            rel="noreferrer noopener"
          >
            manifest-standard whitepaper
          </a>{' '}
          for the trust-score formula.
        </p>

        <div
          className="scoreboard"
          role="group"
          aria-label="Eval scoreboard"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '14px',
            margin: '20px 0 8px',
          }}
        >
          <ScoreCard
            label="Agents tracked"
            value={totalAgents}
            accent="#0A0A0A"
            textOnAccent="#F4ECDA"
            hint="Scored against v2.15 manifests"
          />
          <ScoreCard
            label="With eval history"
            value={agentsWithHistory}
            accent="#FF1E70"
            textOnAccent="#F4ECDA"
            hint={`${Math.max(totalAgents - agentsWithHistory, 0)} pending first run`}
          />
          <ScoreCard
            label="Total eval runs"
            value={totalRuns}
            accent="#00E0D5"
            textOnAccent="#0A0A0A"
            hint="Recorded across the roster"
          />
          <ScoreCard
            label="Average trust score"
            value={avgScore}
            accent="#F4ECDA"
            textOnAccent="#0A0A0A"
            hint="Mean across all tracked agents"
          />
        </div>
      </section>

      <EvalLeaderboard agents={agents} history={history} />

      <Footer />
    </main>
  );
}
