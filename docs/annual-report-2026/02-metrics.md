<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Metrics

This section reports what we actually measured in 2026. Every number below is sourced from a file in the repository — no estimates, no aspirational targets. The point is to make the report falsifiable: if you clone the repo and run the same commands, you will see the same numbers.

## Headline counts

| Metric | Value | Source of truth |
|---|---|---|
| Numbered prompts executed (P1 -> P181) | 181 | `HANDOFF_LOG.md` |
| Marketplace agents (manifest count) | 33 | `docs/agent-trust-scores.json` -> `manifest_count` |
| Pytest suites passing | 21 | `pyproject.toml` testpaths + `python -m pytest -q --strict-markers` |
| Constitution / scanner checks registered | 34 | `safety/scanner.py` -> count of `@register` decorators |
| CLI source lines (PowerShell) | 1,174 | `cli/grok-agent.ps1` |
| Ready-to-paste X posts | 110 | `marketing.md` |
| Forbidden-phrase leaks repo-wide | 0 | `safety/scanner.py forbidden-phrase-scan` |
| Trust-tier-A agents | 3 | `docs/agent-trust-scores.json` |
| Creator templates | 22 | `templates/creator/` |
| X Money tools | 4 | `templates/finance/` |
| Super Agents (3 flagship + 4 lighter) | 7 | `templates/super-agents/` |

## Marketplace composition (33 agents)

| Tier | Count | Definition |
|---|---|---|
| A (>= 90) | 3 | All three flagship Super Agents (`living-narrative-fabric`, `self-evolving-personal-os`, `cross-reality-action-fabric`) |
| B (>= 75) | 0 | No agent in the B band yet — the gap between flagship Super Agents and creator scaffolds is the work of 2027 |
| C (>= 60) | 10 | Mid-tier agents that have evaluation suites or strong provenance but not both |
| D (< 60) | 20 | Creator-template scaffolds without evaluation suites yet |

The trust-score formula, documented at the top of `docs/agent-trust-scores.json`, is `0.4*scanner + 0.3*eval + 0.2*provenance + 0.1*stability`. Every component is independently auditable: the scanner score comes from `safety/scanner.py` error counts, the eval score reads `eval/promptfoo.yaml` and `eval/deepeval_suite.py` presence, the provenance score averages `enabled` / `append_only` / `cite_sources` from each manifest, and stability tracks the manifest's first-commit age clipped to ninety days.

## Test surface (21 passing)

| Suite | Count | Path |
|---|---|---|
| Creator program weekly curation | 11 | `creator-program/v2/curation/tests/` |
| SEPOS router unit tests | 4 | `templates/super-agents/self-evolving-personal-os/tests/test_router.py` |
| Property-based manifest schema tests | 3 | `tests/property/` |
| Snapshot tests for super-agent stubs | 3 | `tests/snapshot/` |
| Total | 21 | `pyproject.toml` testpaths |

The 21-test baseline is up from 11 at the start of Phase 5. The four-test SEPOS router suite (P178) and the six-test property + snapshot bundle (P180–P181) closed the silent prompt-version-drift failure mode that had produced the SEPOS routing bug.

In addition to the unit suite, the repository runs eleven hermetic super-agent smoke scripts in CI via `.github/workflows/tests.yml` (Cross-Reality Action Fabric main + dashboard + four sub-folder smokes; Self-Evolving Personal OS dashboard + connectors via `python -m connectors.smoke_test`; SEPOS memory + provenance + eval via `PYTHONPATH=.`), plus the X Money cross-tool integration smoke driven by `pwsh` against `tests/x-money-integration-smoke.ps1`.

## Safety surface (34 scanner checks, 0 leaks)

`safety/scanner.py` registers 34 distinct checks via the `@register` decorator. They cover Articles I through VIII of the Constitution, the Hard Six rules from `CLAUDE.md`, the verbatim section 12 disclaimers, schema drift between manifests and `spec/v2.15/grok-agent.yaml`, and the trailing-list-marker rule from Article VIII. The repo-wide `forbidden-phrase-scan` reports zero leaks across all source files (985 exempt lines whitelisted via the marker-based exemption system added in P172).

## CLI surface (1,174 lines, 24 functions)

`cli/grok-agent.ps1` ended the year at 1,174 lines and 24 named functions, up from 974 lines and 22 functions before the P178 polish sweep. The two new functions are `Invoke-Doctor` (six health checks: PowerShell version, Python on PATH, pydantic + pyyaml importable, AppData writable, ExecutionPolicy, repo layout sanity) and `Invoke-Explain` (reads `cli/error-codes.md` for any of twelve documented codes). The unknown-command branch now emits `[E-CLI-001]` so users can self-discover the help system.

The CLI is verified bash-leak-free: `grep -E '\&\&|\|\||mkdir -p|rm -rf|chmod \+x|export [A-Z]|which python'` returns empty against `cli/grok-agent.ps1`.

## Marketing surface (110 X posts)

`marketing.md` ships 110 ready-to-paste X posts across ten sections: hero singles plus an eight-tweet launch thread, four X Money tools at seven tweets each, a seven-tweet Super Agent fly-by plus seven singles, a five-tweet creator templates intro plus six themed cluster posts, a six-tweet CLI walkthrough plus four v2.15 singles, a four-tweet marketplace thread plus three singles, four safety singles plus a five-tweet Constitution thread, four roadmap singles, six reply-template scaffolds, and six image captions. Every post is verified at most 280 characters via the fenced-block char-count loop. Every post that touches finance carries the verbatim short-form section 12 disclaimer.

## What we did not measure

Honesty matters. Three numbers we want for the 2027 report but do not have credible 2026 data on:

- **Real install counts.** `marketplace/data/install-counts.json` is a 33-slug seed file, not a production analytics layer. The `_note` field in the JSON makes this explicit.
- **Eval suite pass rates outside Promptfoo runs.** Only the three flagship Super Agents have `eval/promptfoo.yaml` and `eval/deepeval_suite.py` — the lighter four and the twenty-two creator templates do not yet have eval suites.
- **External contributor count.** The repo is currently a single-creator project (`@JanSol0s`) with AI-assisted execution; the Creator Program v2 in 2027 is the explicit play to change this.

> Not financial advice. The X Money tool counts above describe shipped surfaces, not investment guidance. Always consult a licensed financial advisor before making decisions.
