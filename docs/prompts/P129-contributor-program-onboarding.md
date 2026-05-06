<!-- Copyright 2026 AgentMindCloud · Apache 2.0 · http://www.apache.org/licenses/LICENSE-2.0 -->

# [P129] Build contributor program onboarding infrastructure

> Phase: 6 · Estimated time: 2h · Depends on: P127, P128

## 1. Context

You are working on `AgentMindCloud/grok-agent`. Stack: Windows 11 + PowerShell + Python 3.12 + grok-agent.yaml v2.15.

Already built (from `HANDOFF_LOG.md`):
- P127 — Creator Program v2 paid-tier scaffold (`creator-program/v2/`)
- P128 — curation cadence harness (`creator-program/v2/curation/`)

Phase 6 onboards external developers as builders against a published quality bar. See `docs/phase-6-kickoff.md` section "Contributor program".

Working directory: `grok-agent/`

## 2. Goal

Ship contributor onboarding: Pydantic state machine, CLA acceptance + persistence, attribution recording, automated quality-bar gate, plus a pytest suite of ≥10 tests.

## 3. Constraints (hard — non-negotiable)

- Apache 2.0 header on every code file (Python `#`; Markdown HTML-comment).
- "Built for xAI, X, Grok and the ecosystem community. ❤️" footer in README.
- Windows 11 + PowerShell only in user-facing commands.
- Local-first state: `$env:LOCALAPPDATA\grok-agent\contributor-program\`.
- Pydantic v2. Full files only.
- Revenue-share figures are **targets**, not promises.
- Include §12 finance + tax banners verbatim in README and `CLA.md` (revenue share is finance-adjacent):

  > ⚠️ **Not financial advice.** This tool provides information only. Always consult a licensed financial advisor before making decisions.

  > ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction. Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

- Quality gate shells `cli/grok-agent.py validate --strict` + `safety/scanner.py forbidden-phrase-scan`; both must exit 0.
- No network in tests — fixtures under `contributor-program/tests/fixtures/`.

## 4. Files to create/modify

- `contributor-program/__init__.py` — package marker + public exports
- `contributor-program/onboarding.py` — Pydantic v2 state machine (`INVITED → CLA_PENDING → CLA_SIGNED → QUALITY_GATE → ATTRIBUTED → MERGED`)
- `contributor-program/cla.py` — CLA acceptance + LOCALAPPDATA SQLite ledger
- `contributor-program/attribution.py` — attribution recorder
- `contributor-program/quality_bar.py` — gate wrapping `validate --strict` + `forbidden-phrase-scan`
- `contributor-program/README.md` — quickstart + free vs Creator Program table + §12 banners
- `contributor-program/CLA.md` — plain-English Apache 2.0 CLA
- `contributor-program/tests/__init__.py` — test package marker
- `contributor-program/tests/test_onboarding.py` — pytest suite (≥10 tests)

## 5. Reference material

- `creator-program/v2/tier_manager.py` — Pydantic style to mirror
- `docs/prompts/P127-creator-program-v2-paid-tier.md` + `P128-curation-cadence-harness.md` — Phase 6 tone
- `docs/phase-6-kickoff.md` — section "Contributor program"
- `CLAUDE.md` §3, §10, §12
- Apache 2.0 ICLA precedent: https://www.apache.org/licenses/contributor-agreements.html (plain-English rewrite)

## 6. Acceptance criteria

- [ ] Nine files exist with Apache 2.0 headers; `python -m pytest contributor-program/tests/test_onboarding.py` passes on Windows 11.
- [ ] `onboarding.py` exposes the six-state enum + immutable `transition()` rejecting illegal jumps; `cla.py` persists signatures to `cla.sqlite` keyed by GitHub handle.
- [ ] `quality_bar.py` returns `QualityGateResult` by shelling both subcommands; both exit codes must be 0.
- [ ] `attribution.py` appends to `CONTRIBUTORS.md` and writes the handle to manifest `author` without mutating other fields.
- [ ] `README.md` carries both §12 banners verbatim, a free vs Creator Program table, and PowerShell commands; `CLA.md` is plain-English Apache 2.0-compatible.
- [ ] Tests (≥10) cover legal/illegal transitions, CLA idempotent re-sign, attribution writes, gate pass, validate failure, scanner failure.

## 7. Output

1. Full content of every file listed in section 4 (no ellipses).
2. PowerShell commands to commit:
   ```powershell
   git add contributor-program ; git commit -m "phase-6: add contributor program onboarding infrastructure"
   ```
3. Append this row to `HANDOFF_LOG.md`:
   ```
   | P129 | Phase 6 | Contributor program onboarding | contributor-program/{__init__.py, onboarding.py, cla.py, attribution.py, quality_bar.py, README.md, CLA.md, tests/__init__.py, tests/test_onboarding.py} | Pydantic v2 state machine; CLA persisted to LOCALAPPDATA SQLite; quality gate wraps validate --strict + safety scanner; ≥10 pytest cases | done |
   ```
4. Reply with a 3-line summary: what you built + key decisions + any blockers. Nothing more.
