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

# Changelog

All notable changes to `grok-paradoxes` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-05-09

### Added

- Initial release. Extracted contradiction-detection + authority-weighting
  from `templates/super-agents/living-narrative-fabric/orchestrator.py` in
  the `AgentMindCloud/grok-agent` monorepo.
- Public Pydantic v2 types: `Source`, `Claim`, `Contradiction`,
  `ReconciliationSuggestion`.
- `ContradictionDetector` with `detect(claims)` pairwise scan and
  `summary(contradictions)` aggregation, plus a `min_severity` threshold
  argument (`"minor" | "moderate" | "major"`).
- `weight_authorities(claims)` reconciler that prefers the claim with the
  highest `source.authority * claim.confidence` product; deterministic tie
  breaks on `timestamp` then `source.name`.
- Three runnable examples under `examples/` covering two-source
  contradictions, authority-weighted reconciliation, and three-way
  consensus.
- Apache 2.0 license, Python 3.10+ support, `py.typed` marker for downstream
  type-checkers.

[0.1.0]: https://github.com/AgentMindCloud/grok-agent/tree/main/packages/grok-paradoxes
