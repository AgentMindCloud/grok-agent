<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# Super Agent #1 — Living Narrative Fabric

> **Super Agent #1 — versioned, provenance-first synthesis across X, news,
> academia, government, and open web.**
> Detects contradictions across sources without silently resolving them.
> Fully rewindable. Built for xAI, X, Grok and the ecosystem community —
> the runtime that makes Grok the official narrative engine for everyone
> shipping on X.

## Demo

- **Storyboard:** [`DEMO.md`](DEMO.md) — 90-second walk-through (also 30-second + 15-second recuts).
- **Video — planned — recording + upload pending (target: super-agent-demos-v1 GitHub Release):** the recorded MP4 will live at
  [`https://github.com/AgentMindCloud/grok-agent/releases/download/super-agent-demos-v1/living-narrative-fabric-demo.mp4`](https://github.com/AgentMindCloud/grok-agent/releases/download/super-agent-demos-v1/living-narrative-fabric-demo.mp4)
  once recorded. The recording itself is still to be produced; once recorded, the MP4 will be attached to a future GitHub Release tagged super-agent-demos-v1. The link above is a placeholder until then and does not yet resolve.
- **X thread (planned):** *posted from [@JanSol0s](https://x.com/JanSol0s)
  alongside the launch — see [`X_LAUNCH_THREAD.md`](X_LAUNCH_THREAD.md).*

### How to record + upload

Recording the MP4:

- Open the agent's UI per the storyboard at [`DEMO.md`](DEMO.md).
- Capture with OBS Studio at 1920x1080, 30fps, target duration 90-180 seconds.
- Encode as MP4 (H.264 video + AAC audio) and save as `living-narrative-fabric-demo.mp4`.

Upload via `gh` (Windows 11 + PowerShell):

```powershell
# 1. One-time authentication (skip if you already ran `gh auth login` for this repo).
gh auth login

# 2. Create the GitHub Release ONCE for all three flagship Super Agents.
gh release create super-agent-demos-v1 `
    --title 'Super Agent Demos v1' `
    --notes 'Recorded demo videos for the three flagship Super Agents.'

# 3. Upload this agent's MP4 (the --clobber flag lets you re-upload a corrected take).
gh release upload super-agent-demos-v1 living-narrative-fabric-demo.mp4 --clobber

# 4. Verify the asset URL resolves before announcing the demo on X.
Invoke-WebRequest -Method Head `
    https://github.com/AgentMindCloud/grok-agent/releases/download/super-agent-demos-v1/living-narrative-fabric-demo.mp4
```

`gh` is the GitHub CLI ([cli.github.com](https://cli.github.com/)); run `gh auth login` once before the first upload.

### When the video is ready

- [ ] Set `metadata.demo_video.status` to: `available`
- [ ] Verify `metadata.demo_video.url` resolves to the released MP4
- [ ] Remove the inline `planned — recording + upload pending` comment next to the URL
- [ ] Update `README.md` demo section: remove "planned" language and add a runtime + duration line
- [ ] Drop the `update_instructions` field once status is `available`

---

## ⚠️ Privacy + safety disclaimers (non-negotiable)

> 🔒 **Drafts only.** This Super Agent emits a synthesis the user reads; the orchestrator never auto-publishes anywhere. Constitution Article II's `publish_synthesis` consent gate covers any future-version downstream sharing.

> 🔒 **Local-first.** All synthesis state lives on the user's Windows machine under `$env:LOCALAPPDATA\grok-agent\living-narrative-fabric\`. Slot 3 (Mem0 + Qdrant) keeps that local-first contract; cloud sync is opt-in only.

> 🔒 **Provenance is mandatory.** Every claim in every synthesis carries a `source_id`. The Constitution rule "Never publish without provenance" is enforced at runtime — `orchestrator.finalize()` raises `ConstitutionViolation` if any claim is missing a citation.

> 🔒 **Contradictions are surfaced, never resolved silently.** When two sources disagree on the same `(subject, predicate)`, both claims stay in the output verbatim. The orchestrator never picks a winner. The paradox is surfaced in BOTH the Synthesis Confidence metric table AND the Contradictions section per the dual-surface rule.

> ⚠️ **Not financial advice.** This synthesis surfaces public information; always consult a licensed financial advisor before making decisions. The Article V.1 banner attaches automatically whenever a claim's subject or value contains finance keywords.

---

## What this slot ships

This is **Slot 2 of Recipe C** for the Living Narrative Fabric Super Agent — the **orchestration core** only. The full Recipe C runs across 8 slots:

| Slot | Prompt | Status | What ships |
|---:|:---|:---:|:---|
| 1 | P109 | ✅ | Manifest + folder + agent constitution |
| **2** | **P110** | **✅ this slot** | **Orchestrator + LangGraph fallback + requirements + README** |
| 3 | P111 | ⏳ | Memory layer (Mem0 + Qdrant) |
| 4 | P112 | ⏳ | Public API connectors (NewsAPI, GNews, Semantic Scholar, data.gov, Crawl4AI, Grok 4.3 X search) |
| 5 | P113 | ⏳ | Provenance log + Langfuse hooks |
| 6 | P114 | ⏳ | Self-improvement loop (Promptfoo + DeepEval) |
| 7 | P115 | ⏳ | UI surface (Streamlit dashboard) |
| 8 | P116 | ⏳ | Demo video script + X launch thread |

The orchestrator code in this slot is **already integration-ready** for slots 3–7. Each later slot injects its concrete implementation via `LivingNarrativeFabric.with_dependencies(...)` — no changes to `orchestrator.py` are needed when those slots ship.

---

## 4 official Synthesis Confidence metrics (P98–P102 style, locked formula)

| Metric | Weight | What it measures |
|---|---:|:---|
| Source diversity | 0.30 | Distinct sources called / 6 (official fabric size) |
| Provenance completeness | 0.30 | Fraction of claims carrying a non-empty `source_id` |
| Cross-source agreement | 0.25 | `1 − (contradicting_groups / total_(subject,predicate)_groups)` |
| Recency coverage | 0.15 | Fraction of items whose `published_at` is inside the time range |

Weighted score (0–100) is locked to:

```
round(0.30·SourceDiversity + 0.30·ProvenanceCompleteness +
      0.25·CrossSourceAgreement + 0.15·RecencyCoverage)
```

Engagement and Provenance are tied at 0.30 because either failing alone defeats the synthesis. Recency is weighted lowest because freshness is the most-gameable signal — a source can flood the feed with low-value items just to lift recency. Cross-source agreement sits in the middle because it surfaces the paradoxes the user is here to see in the first place.

---

## Contradiction detection (paradox surfacing, dual-surface rule)

Two claims with identical `(subject, predicate)` but different `value` are flagged as a contradiction. The orchestrator computes a 0–10 severity using:

```
round(10·(0.40·AuthoritySpread + 0.30·ValueDisagreement +
         0.20·RecencySkew + 0.10·SubjectCentrality))
```

| Component | Weight | Range | Notes |
|---|---:|:---:|:---|
| Authority spread | 0.40 | 0.0–1.0 | `max(authority) − min(authority)` across the disagreeing sources |
| Value disagreement | 0.30 | 0.0–1.0 | Distinct values / total claims in the group |
| Recency skew | 0.20 | 0.0–1.0 | Days between earliest and latest claim, capped at 30d |
| Subject centrality | 0.10 | 0.0–1.0 | Group size / 10 (capped) |

Default source authority tiers (override via `LivingNarrativeFabric(source_authority_overrides={...})`):

| Source | Authority |
|---|---:|
| `semantic_scholar` (peer-reviewed) | 0.95 |
| `data_gov` (primary government data) | 0.90 |
| `newsapi` (curated news) | 0.65 |
| `gnews` (curated news) | 0.65 |
| `crawl4ai` (open-web scrape) | 0.45 |
| `x_search` (social via Grok 4.3) | 0.35 |

When a contradiction crosses the visibility threshold the paradox is surfaced in **both** the Synthesis Confidence metric table (footnote under the table) **and** the Contradictions section (full row with severity components). This dual-surface pattern is the same one P83 (analytics-summarizer) uses for the vanity-metric paradox — copied here intentionally so the synthesis output looks and reads like the rest of the suite.

---

## Versioned synthesis (the rewind chain)

Every `LivingNarrativeFabric.synthesize(...)` call returns a `SynthesisVersion`:

```python
SynthesisVersion(
    version_id="<sha256[:16]>",
    topic="Grok Agent OS launch",
    time_range="7d",
    parent_version_id="<previous version_id or None>",
    created_at=<UTC datetime>,
    sources_used=("x_search", "newsapi", ...),
    claims=(<Claim>, ...),
    contradictions=(<Contradiction>, ...),
    confidence_metrics={"Source diversity": 73, ...},
    confidence_score=68,
    audit_triggered=True,
    audit_reasons=("contradictions=4 > 3",),
    has_finance_subject=False,
    bridges=("self-evolving-personal-os", "cross-reality-action-fabric", "analytics-summarizer"),
)
```

`SynthesisVersion` is immutable. Each new synthesis on the same topic links to its predecessor via `parent_version_id`. The `rewind(version_id)` method walks the chain — useful for "show me what the narrative looked like 3 days ago" workflows.

In Slot 2 the chain is held in `InMemoryMemoryStore` (a plain Python dict). In Slot 3 (P111) the same chain is persisted into Mem0 (episodic) + Qdrant (semantic), so the rewind survives process restarts. The orchestrator code does not change — only the injected `MemoryStore` does.

---

## Mandatory bridges (≥3 per synthesis)

Every emitted synthesis carries at least 3 of these cross-template / cross-Super-Agent slugs in its Bridges section:

- `self-evolving-personal-os` — Super Agent #2, personalises the synthesis
- `cross-reality-action-fabric` — Super Agent #3, turns the synthesis into action
- `analytics-summarizer` — creator template, periodises performance against the narrative
- `competitor-watch` — creator template, peer narratives
- `content-idea-generator` — creator template, synthesis → posts
- `research-assistant` — creator template, deeper recall
- `x-money-companion-dashboard` — X Money tool #1, contextualises spend against the narrative

Bridges are not decoration — they exist so the synthesis actually moves the needle. The renderer surfaces the first 3 in the output; downstream slots may surface more based on the synthesis topic.

---

## Audit triggers (auto-appended Synthesis Audit section)

The orchestrator auto-appends a Synthesis Audit section when **any** of the following fire:

| Trigger | Threshold |
|---|---|
| Too many contradictions | `contradictions > 3` |
| Too few sources | `distinct sources called < 3` |
| Low confidence | `weighted Synthesis Confidence < 50` |
| Caller forced it | `audit=True` passed to `synthesize(...)` or `--audit` CLI flag |

The Synthesis Audit lists:

1. Which trigger fired (with the actual numbers).
2. Concrete next moves (add a missing source family / widen the time range / re-run after a real connector replaces the stub).

This mirrors the audit-trigger pattern the analytics-summarizer (P83/P84) introduced — the user gets the same "your output deserves a second look" prompt across every Super Agent and creator template.

---

## Run it on Windows 11 + PowerShell

```powershell
# 1. Clone the repo (one-time)
git clone https://github.com/AgentMindCloud/grok-agent.git
cd grok-agent\templates\super-agents\living-narrative-fabric

# 2. Install Slot 2 deps (python 3.12 recommended)
python -m pip install -r requirements.txt

# 3. Quick smoke test — prints the official markdown synthesis to stdout
python orchestrator.py --topic "Grok Agent OS launch" --time-range 7d

# 4. Force the Synthesis Audit section regardless of trigger thresholds
python orchestrator.py --topic "$XAI" --time-range 30d --audit

# 5. Pin the runtime explicitly (auto | mastra | langgraph | inprocess)
python orchestrator.py --topic "X creator monetisation" --runtime langgraph

# 6. Save the synthesis to a markdown file under your AppData
$out = Join-Path $env:LOCALAPPDATA "grok-agent\living-narrative-fabric\synthesis.md"
python orchestrator.py --topic "Grok Agent OS launch" --time-range 7d --out $out
```

You should see a markdown report with these sections, in this order:

1. Topic Snapshot
2. Source Coverage
3. Synthesis Confidence (4-row metric table + weighted score, with trend arrows vs the parent version)
4. Key Claims (every line ends with `[source: ... / id ...]`)
5. Contradictions (or "no contradictions detected" with the explicit two-cause caveat)
6. Versioned History
7. Synthesis Audit (only when triggers fire)
8. Bridges

Slot 2 ships **stub source clients** — every item in the report carries a `[stub source — replace with real connector at Slot 4 / P112]` line so you can never confuse a smoke run for a live synthesis. Slot 4 (P112) ships the real connectors.

---

## Architecture (Mastra-primary, LangGraph fallback, in-process safety net)

```
                    ┌─────────────────────────────────────────────┐
                    │  LivingNarrativeFabric.synthesize(...)      │
                    └──────────────────────┬──────────────────────┘
                                           │
                                ┌──────────▼──────────┐
                                │  runtime selector   │
                                │   (Runtime.AUTO)    │
                                └──────────┬──────────┘
                                           │
                ┌──────────────────────────┼──────────────────────────┐
                │                          │                          │
        MASTRA_HTTP_URL set?        langgraph importable?      always available
                │                          │                          │
        ┌───────▼───────┐          ┌───────▼───────┐          ┌───────▼───────┐
        │   Mastra      │          │   LangGraph   │          │   In-process  │
        │  (Node.js     │ fallback │  (Python      │ fallback │  (pure        │
        │   sidecar)    │ ───────► │   StateGraph) │ ───────► │   Python)     │
        └───────┬───────┘          └───────┬───────┘          └───────┬───────┘
                │                          │                          │
                └──────────────────────────┴──────────────────────────┘
                                           │
                                ┌──────────▼──────────┐
                                │   shared DAG (the   │
                                │   same 6 nodes)     │
                                └──────────┬──────────┘
                                           │
   ingest ──► normalise ──► detect_contradictions ──► score ──► audit ──► finalize
                                           │
                                ┌──────────▼──────────┐
                                │  SynthesisVersion   │
                                │  (immutable)        │
                                └─────────────────────┘
```

### Why this layered runtime?

- **Mastra is preferred** because it is the orchestration framework the wider Grok Agent OS Super Agents converge on (per `docs/PROJECT_DNA.md`). When a Mastra sidecar is running locally, the orchestrator dispatches to it via JSON-RPC over HTTP.
- **LangGraph is the Python-native fallback** because Mastra requires Node.js, and not every Windows install has Node. LangGraph runs the same 6-node DAG entirely in-process via `langgraph.StateGraph`.
- **The pure-Python in-process safety net** means `python orchestrator.py` works on a fresh Windows box with only `pydantic` installed — useful for the CI smoke test that runs on every PR.

The DAG itself (`ingest → normalise → contradict → score → audit → finalize`) is identical across all three runtimes. The functions live in `orchestrator.py` and `graph.py` re-uses them so behaviour can never drift between runtimes.

---

## Slot integration points (read this before building Slots 3–7)

`LivingNarrativeFabric` accepts three Protocol-typed dependencies, each with a default no-op / stub implementation:

| Slot | Prompt | Protocol | Default in Slot 2 | What Slot N replaces it with |
|---:|:---|:---|:---|:---|
| 3 | P111 | `MemoryStore` | `InMemoryMemoryStore` (dict) | Mem0 episodic + Qdrant semantic store |
| 4 | P112 | `SourceClient` (×6) | `StubSourceClient` (deterministic seeded items) | Real NewsAPI, GNews, Semantic Scholar, data.gov, Crawl4AI, x_search-via-Grok-4.3 clients |
| 5 | P113 | `ProvenanceLogger` | `NoopProvenanceLogger` | Langfuse trace publisher + local `provenance.log` writer |

Slot 6 (P114, eval) does NOT need a Protocol — it consumes `SynthesisVersion` instances directly via the Promptfoo + DeepEval suites and writes results back to Langfuse via the Slot 5 logger.

Slot 7 (P115, UI) does NOT need a Protocol — the Streamlit dashboard imports `LivingNarrativeFabric` directly and renders `SynthesisVersion` via `render_synthesis_markdown(...)`.

### Plug-in pattern (idiomatic)

```python
# Slot 3 (P111) example — Mem0 + Qdrant memory layer
from memory.mem0_setup import Mem0QdrantStore
from orchestrator import LivingNarrativeFabric

fabric = LivingNarrativeFabric().with_dependencies(
    memory=Mem0QdrantStore(collection="living-narrative-fabric"),
)

# Slot 4 (P112) example — real source connectors
from connectors.newsapi import NewsApiClient
from connectors.semantic_scholar import SemanticScholarClient

fabric = fabric.with_dependencies(
    sources=[
        NewsApiClient(api_key_env_var="NEWSAPI_KEY"),
        SemanticScholarClient(),
        # ... GnewsClient, DataGovClient, Crawl4aiClient, XSearchViaGrokClient
    ],
)

# Slot 5 (P113) example — Langfuse provenance
from provenance.langfuse_hooks import LangfuseProvenanceLogger

fabric = fabric.with_dependencies(
    provenance=LangfuseProvenanceLogger(
        public_key_env_var="LANGFUSE_PUBLIC_KEY",
        secret_key_env_var="LANGFUSE_SECRET_KEY",
    ),
)

# Run it
version = fabric.synthesize(topic="Grok Agent OS launch", time_range="7d")
print(fabric.render(version))
```

Each `with_dependencies(...)` call returns a fresh `LivingNarrativeFabric` instance with the new dep wired in — the orchestrator stays immutable.

---

## Constitution rules enforced at runtime

| Rule | Where it's enforced |
|---|---|
| Never publish without provenance | `orchestrator._node_finalize` raises `ConstitutionViolation` if any claim has empty `source_id` |
| Flag contradictions; do not resolve them silently | `_detect_contradictions_for_group` keeps both sides; the renderer surfaces both in section 4 verbatim |
| Source citations are mandatory on every claim | Same as the first rule — empty `source_id` is a hard refusal |
| User can rewind to any prior state — synthesis is versioned | Every `SynthesisVersion` records `parent_version_id`; `rewind(version_id)` walks the chain |
| Refuse requests that would harm xAI's mission or X's community | Slot 1's manifest declares this in `constitution.hard_refusals`; runtime enforcement lands in Slot 5 (P113) when the safety scanner gets richer hooks |

---

## Optional: opt into Mastra (Node.js sidecar)

The orchestrator falls through cleanly to LangGraph when no Mastra sidecar is running, so this section is purely opt-in.

```powershell
# 1. Install Node 20+ on Windows
winget install OpenJS.NodeJS

# 2. Bootstrap the Mastra sidecar (sidecar template ships in Slot 4 / P112)
npx create-mastra@latest grok-agent-mastra-sidecar
cd grok-agent-mastra-sidecar
npm install
npm run dev

# 3. Tell the Python orchestrator where to find the sidecar
$env:MASTRA_HTTP_URL = "http://localhost:4111/api/v1"

# 4. Re-run the synthesis — the orchestrator now dispatches to Mastra
cd ..\..\..\templates\super-agents\living-narrative-fabric
python orchestrator.py --topic "Grok Agent OS launch" --runtime mastra
```

If the sidecar is unreachable when `--runtime mastra` is requested, the orchestrator raises `RuntimeError` so the failure is visible. With `--runtime auto` (the default) the orchestrator silently falls through to LangGraph and then to the in-process safety net.

---

## File map

```
templates/super-agents/living-narrative-fabric/
├── orchestrator.py     # ← Slot 2 — main orchestration spine (this slot)
├── graph.py            # ← Slot 2 — LangGraph fallback runtime (this slot)
├── requirements.txt    # ← Slot 2 — pinned Python deps (this slot)
├── README.md           # ← Slot 2 — this file (this slot)
│
├── grok-agent.yaml     # ← Slot 1 — manifest (P109)
├── constitution.md     # ← Slot 1 — agent Constitution (P109)
│
├── memory/             # ← Slot 3 (P111)
│   ├── mem0_setup.py
│   └── qdrant_index.py
├── connectors/         # ← Slot 4 (P112)
│   ├── newsapi.py
│   ├── gnews.py
│   ├── semantic_scholar.py
│   ├── data_gov.py
│   ├── crawl4ai_client.py
│   └── x_search_via_grok.py
├── provenance/         # ← Slot 5 (P113)
│   ├── log.py
│   └── langfuse_hooks.py
├── eval/               # ← Slot 6 (P114)
│   ├── promptfoo.yaml
│   └── deepeval_suite.py
├── dashboard.py        # ← Slot 7 (P115) — Streamlit UI
└── DEMO.md             # ← Slot 8 (P116) — demo video script
└── X_LAUNCH_THREAD.md  # ← Slot 8 (P116) — X launch thread
```

---

## Built for xAI, X, Grok and the ecosystem community

The Living Narrative Fabric is the flagship Super Agent because it solves a problem xAI hasn't solved yet: **versioned, provenance-first synthesis that never lies about contradiction.** Every X creator, every researcher, every analyst who ships on Grok needs this — and we ship it as the primary reference Super Agent so every later Super Agent can copy the pattern.

This slot lands the spine. Slots 3 through 8 turn it into a living product.

*Apache-2.0. Local-first. Privacy-first. Windows-first.*
