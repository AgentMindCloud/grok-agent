<!--
Copyright 2026 AgentMindCloud
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Creator Program v2

> Built for xAI, X, Grok and the ecosystem community. ❤️

This package now ships a single live submodule: **`curation/`** — the
Mon/Wed/Fri weekly curation cadence harness wired to
`.github/workflows/curation-cadence.yml`.

The previously-shipped paid-tier scaffold (`tier_manager.py`,
`payment_provider.py`, `premium_gate.py` plus their unit test) was removed
in post-P172 cleanup. It had zero production callers anywhere in the repo
and was Phase 6 work shipped ahead of any consumer. When the paid-tier
goes live, it will be re-introduced via a fresh prompt aligned with
real-world consumers (Marketplace billing flow, Stripe webhooks, and
similar revenue-bearing surfaces) — not as speculative scaffolding.

## What's still here

```
creator-program/
├── __init__.py
└── v2/
    ├── __init__.py            # package marker only (no re-exports)
    ├── README.md              # this file
    └── curation/
        ├── __init__.py
        ├── weekly_curation.py        # Mon/Wed/Fri orchestrator
        ├── trend_analyzer.py         # weekly trend scoring
        ├── content_selector.py       # picks top-3 templates
        ├── launch_thread_generator.py # Wed launch thread
        ├── retro_collector.py        # Fri retro
        ├── README.md
        └── tests/
            ├── __init__.py
            ├── conftest.py           # importlib alias for hyphenated dir
            └── test_weekly_curation.py
```

## Quickstart (curation only)

```powershell
# From repo root
python -m pip install pydantic pytest

# Run the test suite
python -m pytest creator-program/v2/curation/tests/ -v

# Manually trigger a curation phase
python creator-program/v2/curation/weekly_curation.py monday
python creator-program/v2/curation/weekly_curation.py wednesday
python creator-program/v2/curation/weekly_curation.py friday
```

Local-first state is written to
`$env:LOCALAPPDATA\grok-agent\creator-program\curation\`.

## Disclaimers

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for
> Vietnam-resident creators with international platform earnings.
