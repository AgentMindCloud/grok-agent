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

# grok-paradoxes

<p>
  <img src="https://img.shields.io/pypi/v/grok-paradoxes.svg?color=FF1E70&labelColor=0A0A0A" alt="PyPI version" />
  <img src="https://img.shields.io/badge/License-Apache_2.0-FF1E70.svg?labelColor=0A0A0A" alt="Apache 2.0" />
  <img src="https://img.shields.io/badge/python-3.10+-00E0D5.svg?labelColor=0A0A0A" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/types-pydantic_v2-FF1E70.svg?labelColor=0A0A0A" alt="Pydantic v2" />
  <img src="https://img.shields.io/badge/extracted_from-living--narrative--fabric-00E0D5.svg?labelColor=0A0A0A" alt="extracted from Living Narrative Fabric" />
</p>

> **Detect contradictions across sources. Reconcile by authority. Never silently resolve.**
> A small, typed, dependency-light Python library that takes a list of
> `Claim` objects from independent `Source`s, finds where they disagree,
> rates the severity, and proposes a reconciliation grounded in source
> authority — without collapsing the disagreement out of existence.

`grok-paradoxes` is the contradiction-detection and authority-weighting core
extracted from the Living Narrative Fabric Super Agent in
`AgentMindCloud/grok-agent`. It exists because every multi-source synthesis
pipeline eventually hits the same problem: two sources, two values, and a
silent `last-write-wins` that hides the disagreement from the user. This
package gives you the typed primitives to keep the disagreement visible, rank
it, and decide what to do — programmatically.

---

## Installation

From PyPI (recommended for downstream apps):

```powershell
python -m pip install grok-paradoxes
```

From source inside the `AgentMindCloud/grok-agent` monorepo (recommended for
contributors):

```powershell
python -m pip install -e packages/grok-paradoxes/
```

Both install paths give you the same importable module:

```python
from grok_paradoxes import (
    ContradictionDetector,
    Source,
    Claim,
    Contradiction,
    ReconciliationSuggestion,
    weight_authorities,
)
```

Requires Python 3.10 or newer. The only runtime dependencies are `pydantic>=2.7`
and `pyyaml`.

---

## Quickstart

Three short scripts — each is also shipped under `examples/`.

### 1. Two-source contradiction

```python
from grok_paradoxes import ContradictionDetector, Source, Claim

s1 = Source(name="x_post", authority=0.6)
s2 = Source(name="news_wire", authority=0.7)
claims = [
    Claim(subject="BTC", predicate="price", value=10, source=s1, confidence=0.8),
    Claim(subject="BTC", predicate="price", value=15, source=s2, confidence=0.8),
]
detector = ContradictionDetector(min_severity="minor")
for c in detector.detect(claims):
    print(c.severity, c.rationale)
```

### 2. Authority-weighted reconciliation

```python
from grok_paradoxes import Source, Claim, weight_authorities

high = Source(name="sec_filing", authority=0.9)
low = Source(name="rumor_account", authority=0.4)
claims = [
    Claim(subject="ACME", predicate="revenue", value=120, source=high, confidence=0.85),
    Claim(subject="ACME", predicate="revenue", value=180, source=low, confidence=0.85),
]
suggestion = weight_authorities(claims)
print(suggestion.preferred_claim.value, suggestion.rationale)
```

### 3. Three-way consensus

```python
from grok_paradoxes import ContradictionDetector, Source, Claim

sources = [Source(name=f"src_{i}", authority=0.7) for i in range(3)]
claims = [
    Claim(subject="EU_CPI", predicate="rate", value=2.4, source=s, confidence=0.9)
    for s in sources
]
detector = ContradictionDetector()
contradictions = detector.detect(claims)
print(detector.summary(contradictions))  # 0 contradictions => consensus
```

---

## API reference

### `Source`

Pydantic model. Identifies where a claim came from.

| field | type | notes |
|---|---|---|
| `name` | `str` | Unique identifier — e.g. `"x_post"`, `"sec_filing"`, `"news_wire"`. |
| `authority` | `float` | In `[0.0, 1.0]`. Higher = more authoritative. Used by `weight_authorities`. |
| `scope` | `str \| None` | Optional domain hint — e.g. `"finance"`, `"academic"`. |

### `Claim`

Pydantic model. One factual assertion attributed to one `Source`.

| field | type | notes |
|---|---|---|
| `subject` | `str` | The entity the claim is about. |
| `predicate` | `str` | The attribute. |
| `value` | `Any` | The asserted value. Numeric, string, or bool. |
| `source` | `Source` | The originating source. |
| `confidence` | `float` | Source-self-reported confidence in `[0.0, 1.0]`. |
| `timestamp` | `datetime \| None` | Optional capture time. |

### `Contradiction`

Pydantic model. Emitted by `ContradictionDetector.detect`.

| field | type | notes |
|---|---|---|
| `claim_a` | `Claim` | First conflicting claim. |
| `claim_b` | `Claim` | Second conflicting claim. |
| `severity` | `Literal["minor","moderate","major"]` | Bucketed by value-distance and confidence overlap. |
| `rationale` | `str` | One-sentence human-readable explanation. |

### `ReconciliationSuggestion`

Pydantic model. Emitted by `weight_authorities`.

| field | type | notes |
|---|---|---|
| `preferred_claim` | `Claim` | The claim the function recommends keeping. |
| `rationale` | `str` | Why — typically references the authority gap. |
| `confidence_delta` | `float` | How much more confident the suggestion is than a coin-flip. |

### `ContradictionDetector`

```python
ContradictionDetector(min_severity: Literal["minor","moderate","major"] = "minor")
```

- `detect(claims: list[Claim]) -> list[Contradiction]` — pairwise scan over
  claims sharing the same `(subject, predicate)`. Returns only contradictions
  at or above `min_severity`.
- `summary(contradictions: list[Contradiction]) -> dict` — counts by severity
  plus a stable list of `(subject, predicate)` keys, useful for dashboards.

### `weight_authorities`

```python
weight_authorities(claims: list[Claim]) -> ReconciliationSuggestion
```

Picks the claim whose `source.authority * claim.confidence` product is
highest. Ties break to the most recent `timestamp`, then alphabetically by
`source.name` for determinism.

---

## Where this came from

The `living-narrative-fabric` Super Agent (see
`templates/super-agents/living-narrative-fabric/orchestrator.py` in
`AgentMindCloud/grok-agent`) is a versioned, provenance-first synthesis
engine that pulls from X (via Grok 4.3), news wires, academic search,
government data, and the open web — then refuses to silently resolve
disagreements between them. The orchestrator's contradiction detector and
authority weighter were the two pieces of that pipeline that downstream users
kept asking to use standalone, outside the full Super Agent.

`grok-paradoxes` is that extraction. The types are the same Pydantic v2
shapes the Super Agent uses internally, the detection logic is the same
pairwise scan, and the authority weighter is byte-for-byte the same
preference function. Lifting it into its own package lets any Python
codebase — Streamlit dashboards, FastAPI services, evaluator harnesses —
import the primitives without taking the full Super Agent dependency
footprint.

---

## Citation

If you use `grok-paradoxes` in academic work, please cite the parent project:

**BibTeX**

```bibtex
@software{grok_paradoxes_2026,
  author  = {{AgentMindCloud}},
  title   = {grok-paradoxes: contradiction detection and authority-weighted
             reconciliation for multi-source synthesis},
  year    = {2026},
  url     = {https://github.com/AgentMindCloud/grok-agent/tree/main/packages/grok-paradoxes},
  version = {0.1.0}
}
```

**APA**

> AgentMindCloud. (2026). *grok-paradoxes: contradiction detection and
> authority-weighted reconciliation for multi-source synthesis* (Version 0.1.0)
> [Computer software]. https://github.com/AgentMindCloud/grok-agent

---

## Roadmap

**v0.2** — planned:

- Pluggable severity scorers (override the default value-distance heuristic
  with a domain-specific function for prices, rates, percentages).
- `temporal` mode — when two claims share `(subject, predicate)` but differ
  by timestamp, treat as an update rather than a contradiction.
- A small CLI: `grok-paradoxes detect claims.json` for shell pipelines.
- A `to_provenance_event()` adapter so each `Contradiction` round-trips
  cleanly into the parent agent's provenance log.

---

## License

Apache License 2.0. See `LICENSE` in the package root and the matching
`LICENSE` at the monorepo root for the full text.

---

<p align="center">
  <i>Built for xAI, X, Grok and the ecosystem community. ❤️</i>
</p>
