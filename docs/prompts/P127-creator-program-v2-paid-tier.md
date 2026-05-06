<!-- Copyright 2026 AgentMindCloud · Apache 2.0 · http://www.apache.org/licenses/LICENSE-2.0 -->

# [P127] Scaffold Creator Program v2 paid-tier infrastructure

> Phase: 6 · Estimated time: 2h · Depends on: P126 (xAI partnership pitch + marketplace live)

## 1. Context

You are working on `AgentMindCloud/grok-agent`. Stack: Windows 11 + PowerShell + Python 3.12 + Streamlit + grok-agent.yaml v2.15.

Already built (from `HANDOFF_LOG.md`):
- P125 — Next.js marketplace on Vercel
- P126 — xAI partnership pitch + RFC delivered
- P88–P92 — Phase 3 Creator Program (free tier, 22 templates)
- P122 — Self-improvement loop (Promptfoo + DeepEval + Langfuse)

Phase 6 graduates the free program into a paid operation. P127 is the first executable prompt: it lays the tier model, payment-provider scaffold, and gating decorator that P128 (payouts) and P130 (contributor guide) build on. See `docs/phase-6-kickoff.md` section "P127 — Premium tier scaffolding".

Working directory: `grok-agent/`

## 2. Goal

Ship the Creator Program v2 paid-tier foundation: Pydantic tier models, an abstract `PaymentProvider` interface with a Stripe scaffold, and a `@requires_tier` gating helper — with unit tests covering tier transitions and gate behavior.

## 3. Constraints (hard — non-negotiable)

- Apache 2.0 license header at top of every code file (Python `#`-style; Markdown HTML-comment style).
- "Built for xAI, X, Grok and the ecosystem community. ❤️" footer in the README.
- Windows 11 + PowerShell only in every command shown — no bash, no macOS.
- Local-first storage path: `$env:LOCALAPPDATA\grok-agent\creator-program\` (never `~/.config/`).
- No live payment keys. Stripe scaffold reads `$env:STRIPE_API_KEY` and remains test-mode safe.
- Pricing is a target proposal, not a commitment. Frame revenue language as targets.
- Include the §12 finance + tax disclaimer banners in the README (revenue, payouts).
- Pydantic v2 for schema validation. Full files only — no ellipses or partial code.

## 4. Files to create/modify

- `creator-program/v2/__init__.py` — package marker, exports public API
- `creator-program/v2/tier_manager.py` — Pydantic `Tier`, `CreatorAccount`, feature-flag map, `upgrade()` / `downgrade()` helpers
- `creator-program/v2/payment_provider.py` — abstract `PaymentProvider` + `StripePaymentProvider` scaffold (no live calls)
- `creator-program/v2/premium_gate.py` — `@requires_tier(Tier.PREMIUM)` decorator + `gate_streamlit_tab()` helper
- `creator-program/v2/README.md` — quickstart with PowerShell commands, disclaimer banners
- `creator-program/v2/tests/test_tier_manager.py` — pytest unit tests: free→premium upgrade, downgrade, gate-allows-premium, gate-blocks-free, Stripe scaffold returns deterministic stub session

## 5. Reference material

- `docs/phase-6-kickoff.md` — sections "Free vs Premium tier structure" + "20% revenue share model"
- `CLAUDE.md` §12 (disclaimers) and §10 (PowerShell cheat sheet)
- `spec/v2.15/grok-agent.yaml` — for `safety.cost_limits` field shape
- Stripe Connect API docs: https://stripe.com/docs/connect — test-mode `Account` and `Subscription` shapes only; no live integration

## 6. Acceptance criteria

- [ ] All six files exist at the listed paths with Apache 2.0 headers.
- [ ] `python -m pytest creator-program/v2/tests/test_tier_manager.py` passes on Windows 11.
- [ ] `tier_manager.py` exposes `Tier` enum (`FREE`, `PREMIUM`), `CreatorAccount` Pydantic model, and immutable `upgrade()` / `downgrade()` helpers.
- [ ] `@requires_tier` raises `PermissionError` for `FREE` accounts and returns wrapped output for `PREMIUM`.
- [ ] Stripe scaffold reads `$env:STRIPE_API_KEY`, never calls live endpoints; abstract base accepts an alternate provider subclass (test stub).
- [ ] README contains §12 finance + tax disclaimer banners and PowerShell-only commands.

## 7. Output

1. Full content of every file listed in section 4 (no ellipses).
2. PowerShell commands to commit:
   ```powershell
   git add creator-program/v2 ; git commit -m "phase-6: add Creator Program v2 paid-tier scaffold"
   ```
3. Append this row to `HANDOFF_LOG.md`:
   ```
   | P127 | Phase 6 | Creator Program v2 paid-tier scaffold | creator-program/v2/{__init__.py, tier_manager.py, payment_provider.py, premium_gate.py, README.md, tests/test_tier_manager.py} | Pydantic v2 tier models; Stripe scaffold test-mode only; gating via decorator | done |
   ```
4. Reply with a 3-line summary: what you built + key decisions + any blockers. Nothing more.
