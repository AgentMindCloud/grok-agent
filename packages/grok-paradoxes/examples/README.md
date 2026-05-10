<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 (the "License"); -->
<!-- you may not use this file except in compliance with the License. -->
<!-- You may obtain a copy of the License at -->
<!--     http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Unless required by applicable law or agreed to in writing, software -->
<!-- distributed under the License is distributed on an "AS IS" BASIS, -->
<!-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. -->
<!-- See the License for the specific language governing permissions and -->
<!-- limitations under the License. -->

# grok-paradoxes — examples

> Built for xAI, X, Grok and the ecosystem community. ❤️

Three runnable scripts that exercise every public symbol in the
`grok_paradoxes` package. Each script is standalone — no shared
fixtures, no hidden state, no network calls. Run any one of them in
isolation to verify your install.

## Index

| # | Script | What it shows |
|---|---|---|
| 01 | [`01_two_source_contradiction.py`](01_two_source_contradiction.py) | Two sources, two prices for the same asset, similar confidence. The detector surfaces the disagreement at `severity="minor"` instead of silently picking one. |
| 02 | [`02_authority_weighted_reconciliation.py`](02_authority_weighted_reconciliation.py) | High-authority SEC filing vs. low-authority rumor account on revenue. `weight_authorities` returns a `ReconciliationSuggestion` preferring the filing, with rationale and a positive `confidence_delta`. |
| 03 | [`03_three_way_consensus.py`](03_three_way_consensus.py) | Three independent sources agree on a CPI rate. The detector returns zero contradictions and the `summary` helper reports an empty bucket — the consensus signal. |

## Running

Install the package first (from the monorepo root):

```powershell
python -m pip install -e packages/grok-paradoxes/
```

Or from PyPI:

```powershell
python -m pip install grok-paradoxes
```

Then run any example directly with Python:

```powershell
python packages/grok-paradoxes/examples/01_two_source_contradiction.py
python packages/grok-paradoxes/examples/02_authority_weighted_reconciliation.py
python packages/grok-paradoxes/examples/03_three_way_consensus.py
```

Each script prints its findings to stdout and exits 0 on success.

## What to read next

- The package [`README.md`](../README.md) — full API reference.
- The package [`CHANGELOG.md`](../CHANGELOG.md) — version history.
- The parent Super Agent at
  [`templates/super-agents/living-narrative-fabric/`](../../../templates/super-agents/living-narrative-fabric/)
  in the `AgentMindCloud/grok-agent` monorepo — the original home of
  the contradiction detector and authority weighter.

---

<p align="center">
  <i>Built for xAI, X, Grok and the ecosystem community. ❤️</i>
</p>
