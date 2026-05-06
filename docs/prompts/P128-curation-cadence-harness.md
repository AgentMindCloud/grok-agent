<!-- Copyright 2026 AgentMindCloud · Apache 2.0 · http://www.apache.org/licenses/LICENSE-2.0 -->

# [P128] Build Mon/Wed/Fri curation cadence harness

> Phase: 6 · Estimated time: 2h · Depends on: P127 (Creator Program v2 paid-tier scaffold)

## 1. Context

You are working on `AgentMindCloud/grok-agent`. Stack: Windows 11 + PowerShell + Python 3.12 + grok-agent.yaml v2.15.

Already built (from `HANDOFF_LOG.md`):
- P125 — Next.js marketplace on Vercel
- P126 — xAI partnership pitch + RFC delivered
- P127 — Creator Program v2 paid-tier scaffold under `creator-program/v2/`

Phase 6 commits to a weekly rhythm: Monday selection, Wednesday spotlight, Friday retro. P128 makes that rhythm executable on a schedule. See `docs/phase-6-kickoff.md` section "Weekly curation cadence".

Working directory: `grok-agent/`

## 2. Goal

Ship the Mon/Wed/Fri curation cadence harness: an orchestrator plus three day-specific modules (scoring, launch-thread generator, retro collector) wired to a GitHub Actions cron schedule, with unit tests covering scoring.

## 3. Constraints (hard — non-negotiable)

- Apache 2.0 header on every code file (Python `#`; Markdown HTML-comment; YAML `#`).
- "Built for xAI, X, Grok and the ecosystem community. ❤️" footer in the README.
- Windows 11 + PowerShell only in user-facing commands. Bash inside the workflow on `ubuntu-latest` is the CI exception.
- Local-first state path: `$env:LOCALAPPDATA\grok-agent\creator-program\curation\`.
- Pydantic v2 for scoring. Full files only — no partial code.
- Install-count, rating, and engagement numbers are **targets / heuristics**, never promises. Weights stay configurable.
- Reuse `creator-program/v2/tier_manager.py` from P127 to filter Premium creators.
- Cron: Mon/Wed/Fri 09:00 UTC plus `workflow_dispatch`. No network calls in tests — fixtures live under `tests/fixtures/`.

## 4. Files to create/modify

- `creator-program/v2/curation/__init__.py` — package marker
- `creator-program/v2/curation/cadence_runner.py` — orchestrator dispatching by weekday
- `creator-program/v2/curation/scoring.py` — Pydantic `TemplateScore` + weekly top-3 scorer
- `creator-program/v2/curation/launch_thread_generator.py` — Wednesday thread builder
- `creator-program/v2/curation/retro_collector.py` — Friday retro collector
- `creator-program/v2/curation/README.md` — quickstart, PowerShell commands, disclaimer
- `.github/workflows/curation-cadence.yml` — Mon/Wed/Fri 09:00 UTC cron + `workflow_dispatch`
- `creator-program/v2/curation/tests/test_scoring.py` — pytest top-3, tie-break, threshold

## 5. Reference material

- `docs/phase-6-kickoff.md` — sections "Weekly curation cadence" + "Free vs Premium tier structure"
- `docs/prompts/P127-creator-program-v2-paid-tier.md` — Phase 6 style + tier-model reuse
- `CLAUDE.md` §10 (PowerShell cheat sheet), §12 (disclaimers), §3 (forbidden phrases)
- `spec/v2.15/grok-agent.yaml` — `safety` and `metadata.tags` field shapes
- GitHub Actions cron docs: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule

## 6. Acceptance criteria

- [ ] All eight files exist with Apache 2.0 headers; `python -m pytest creator-program/v2/curation/tests/test_scoring.py` passes on Windows 11 with bundled fixtures and zero network calls.
- [ ] `cadence_runner.py` exposes `run(day: Literal["monday", "wednesday", "friday"])` and persists state under `$env:LOCALAPPDATA\grok-agent\creator-program\curation\`.
- [ ] `scoring.py` returns exactly 3 winners ordered by score; default weights installs 0.5 / ratings 0.3 / engagement 0.2 are documented as heuristic targets and remain configurable.
- [ ] `launch_thread_generator.py` produces ≤ 10 tweets (≤ 280 chars each) referencing Monday's selection JSON; `retro_collector.py` writes the Friday retro log and fails safely when Wednesday state is missing.
- [ ] `.github/workflows/curation-cadence.yml` schedules the three weekly crons plus `workflow_dispatch` and calls the runner with the matching `--day` flag.
- [ ] README contains the §12 finance disclaimer banner and PowerShell-only user commands.

## 7. Output

1. Full content of every file listed in section 4 (no ellipses, no "rest unchanged").
2. PowerShell commands to commit:
   ```powershell
   git add creator-program/v2/curation .github/workflows/curation-cadence.yml ; git commit -m "phase-6: add Mon/Wed/Fri curation cadence harness"
   ```
3. Append this row to `HANDOFF_LOG.md`:
   ```
   | P128 | Phase 6 | Curation cadence harness | creator-program/v2/curation/{__init__.py, cadence_runner.py, scoring.py, launch_thread_generator.py, retro_collector.py, README.md, tests/test_scoring.py}, .github/workflows/curation-cadence.yml | Mon/Wed/Fri cron + workflow_dispatch; Pydantic scoring with configurable weights; local-first state under LOCALAPPDATA | done |
   ```
4. Reply with a 3-line summary: what you built + key decisions + any blockers. Nothing more.
