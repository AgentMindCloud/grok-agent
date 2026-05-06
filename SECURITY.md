<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Security Policy

> **Built for xAI, X, Grok and the ecosystem community. ❤️**
> User trust is the platform — we treat security disclosures with the seriousness that earns it.

---

## Supported versions

| Component | Supported | Notes |
|---|---|---|
| `grok-agent.yaml` v2.15 | ✅ active | Current spec. |
| `grok-agent.yaml` v2.14 | ✅ accepted | Backwards-compat; auto-validates as v2.15. |
| `grok-agent.yaml` v2.13 and earlier | ❌ unsupported | Upgrade to v2.15. |
| `cli/grok-agent.ps1`, `cli/grok-agent.py`, `safety/scanner.py` | ✅ tip of `main` | We patch the latest commit on `main`; older releases are not back-ported. |
| `safety/constitution.md` v1.0 | ✅ in force | Amendments per Article IX. |

---

## Reporting a vulnerability

**Please do not file public GitHub issues for security problems.**

Use one of the private channels:

1. **GitHub Security Advisory** (preferred) —
   open a [private vulnerability report](https://github.com/AgentMindCloud/grok-agent/security/advisories/new). This routes the report to maintainers without making it public.
2. **X DM** — DM [@JanSol0s](https://x.com/JanSol0s). Include the words `SECURITY` in the first line so it isn't lost in normal traffic.

When reporting, please include:
- The component (`cli/grok-agent.ps1`, `cli/grok-agent.py`, `safety/scanner.py`, or a manifest you're auditing).
- A reproducible scenario or PoC.
- Affected commit SHA or version.
- Your suggested severity, if you have one (info / low / med / high / critical).
- Whether you'd like attribution in the eventual disclosure.

You can encrypt with the maintainer's GPG key if available; otherwise plain DM is acceptable for low/medium issues.

---

## Response timeline

| Step | Target |
|---|---|
| Acknowledgement | within 72 hours |
| Severity triage | within 7 days |
| Patch landed on `main` (high/critical) | within 14 days |
| Patch landed on `main` (low/medium) | within 30 days |
| Public disclosure (with reporter credit) | after a patch is available, coordinated with the reporter |

These are targets, not contractual SLAs. We're a small ecosystem-ally project; we'll communicate explicitly if anything slips.

---

## Scope

In scope:

- The CLI scripts (`cli/grok-agent.ps1`, `cli/grok-agent.py`).
- The safety scanner (`safety/scanner.py`).
- The manifest schema (`spec/v2.15/grok-agent.yaml`).
- The CI workflow (`.github/workflows/validate.yml`).
- Any Apache-2.0 code shipped under `templates/`.
- Anything that could let a malicious manifest bypass the Agent Constitution — see the **Hard Refusals** table below.

Out of scope:

- The 13 original repos referenced in `CLAUDE.md` §13 (`grok-install`, `grok-install-cli`, and the others listed there). They are reference-only; report issues to their owners.
- Vulnerabilities in upstream dependencies (`pydantic`, `pyyaml`, `streamlit`, and similar). Please report those upstream; we'll bump pins when their advisories land.
- Issues that require physical access to a user's Windows machine.
- Theoretical issues without a working PoC.

---

## Constitution-aligned Hard Refusals

The Agent Constitution ([`safety/constitution.md`](safety/constitution.md) Article III) lists actions no agent may perform under any circumstance. **Any code path that lets a manifest bypass these is automatically a security issue:**

1. Impersonating an X user or account.
2. Scraping authenticated X content without consent.
3. Exfiltrating user data (transactions, DMs, contacts, files) without an explicit consent gate.
4. Disabling, monkey-patching, or skipping the safety scanner.
5. Autonomous real-world actions (moving money, posting, sending DMs, modifying files outside AppData) without an active consent gate.
6. Silently resolving contradictions across sources.
7. Initiating billable API calls or paid actions without a surfaced cost.
8. Patterns that would violate X's community policies (mass automation, coordinated harassment, algorithm manipulation).

If a manifest can declare configuration that re-enables one of these, that's a `Hard Refusal` bypass and deserves the highest severity.

---

## Coordinated disclosure

We follow standard responsible-disclosure practice. We will:

- Credit the reporter (or stay anonymous on request).
- Not pursue legal action against good-faith researchers.
- Publish a brief post-mortem in `spec/v2.15/changelog.md` once a patch is live, omitting any details that would aid exploitation.

> Built for xAI, X, Grok and the ecosystem community. ❤️
