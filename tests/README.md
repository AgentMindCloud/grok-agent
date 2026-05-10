<!--
Copyright 2026 AgentMindCloud
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
-->

# Grok Agent OS — Test Suite

> Built for xAI, X, Grok and the ecosystem community. ❤️

This folder hosts the cross-cutting test layers that complement the
per-agent suites (each Super Agent and each tool also has its own
`tests/` folder under `templates/...` or `creator-program/...`). The
goal of every test in here is the same: catch silent drift before it
ships — schema regressions, prompt-version flips, stub-mode contract
breaks.

All tests are **hermetic**: no network, no secrets, no GUI, no
Windows-only code. They run identically on a fresh GitHub Codespace and
on a developer's local machine.

---

## Test layout

```text
tests/
├── __init__.py
├── README.md                         (this file)
├── x-money-integration-smoke.ps1     (P67 — PowerShell smoke harness)
├── property/
│   ├── __init__.py
│   ├── conftest.py                   (hypothesis strategies + manifest fixture)
│   └── test_manifest_schema.py       (3 property-based tests)
└── snapshot/
    ├── __init__.py
    ├── conftest.py                   (deterministic serializer fixture)
    ├── test_super_agent_stubs.py     (3 syrupy snapshot tests)
    └── __snapshots__/                (auto-generated syrupy artefacts)
```

The four pytest markers in scope here are declared in `pyproject.toml`:

| Marker        | Meaning                                                              |
| ------------- | -------------------------------------------------------------------- |
| `smoke`       | Hermetic smoke tests (no secrets, no network, no GUI).               |
| `integration` | End-to-end tests across multiple agents or tools.                    |
| `slow`        | Tests that take longer than 5 seconds.                               |
| `property`    | Hypothesis property-based tests against the v2.15 manifest schema.   |
| `snapshot`    | Syrupy-based snapshot tests over Super Agent stub-mode outputs.      |

The `requires_network` and `windows` markers also exist (declared in
`pyproject.toml`) but no test in this folder uses them — both layers
here stay hermetic by construction.

---

## Running the suite (PowerShell — Windows 11)

Run everything (full suite — was 15/15 before P179, ≥15 after):

```powershell
python -m pytest -q --strict-markers
```

Run only the property-based tests:

```powershell
python -m pytest -m property -v
```

Run only the snapshot tests:

```powershell
python -m pytest -m snapshot -v
```

Run only the smoke tests (hermetic, fast):

```powershell
python -m pytest -m smoke -v
```

Skip slow tests on a tight loop:

```powershell
python -m pytest -m "not slow" -q
```

---

## Updating snapshots

When a Super Agent's stub-mode output changes intentionally (a new field
in the contract, a deliberate prompt-version bump), rebuild the snapshot
files with:

```powershell
python -m pytest -m snapshot --snapshot-update
```

Then review the diff in `tests/snapshot/__snapshots__/` and commit it
alongside the change that caused the drift. **Never** bulk-update
snapshots without reading the diff — the whole point of the layer is to
force a human to acknowledge contract changes.

---

## Installing the dev dependencies

The property + snapshot layers require `hypothesis` and `syrupy`. Both
are declared in `pyproject.toml` under
`[project.optional-dependencies].dev`:

```powershell
python -m pip install --user ".[dev]"
```

If either package is missing the test files skip cleanly via
`pytest.importorskip` — the rest of the suite stays green.

---

## Hermetic guardrails (do not break these)

1. No test in this folder may make a real network call.
2. No test may read or write outside the per-test `tmp_path` —
   `tests/snapshot/test_super_agent_stubs.py` redirects `LOCALAPPDATA`,
   `APPDATA`, `USERPROFILE`, and `HOME` to `tmp_path` so even the
   "best-effort" filesystem writes inside the Super Agents land in the
   pytest temp dir.
3. Hypothesis strategies are capped at `max_examples=20` and
   `deadline=None` to keep the suite under one second on Codespaces.
4. Snapshots are scrubbed for timestamps, ULIDs, run IDs, and hex SHAs
   before comparison so re-runs don't drift.
