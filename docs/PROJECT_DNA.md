# PROJECT_DNA.md

The non-negotiable facts about the Grok Agent Platform. Treat these as ground truth in every prompt generated.

## Identity

- **Repo**: `github.com/AgentMindCloud/grok-agent`
- **Org**: `AgentMindCloud` (creator: `@JanSol0s`)
- **Codename**: Grok Agent OS
- **Tagline**: "The official standards + distribution layer that makes Grok the easiest, most powerful, and most magical platform for deploying agents on X."
- **License**: Apache 2.0 (everywhere, no exceptions)
- **Manifest version**: `grok-agent.yaml` v2.15 (100% backwards compat with v2.14)

## Stack (default — only deviate if explicitly required)

| Layer | Choice |
|---|---|
| OS target | Windows 11 + Google Chrome ONLY |
| Shell | PowerShell (no bash, no zsh) |
| Language (apps) | Python 3.12 |
| App framework | Streamlit (for X Money tools) |
| Data | SQLite (local-first) |
| Schema | YAML (Pydantic for validation) |
| Orchestration (super agents) | Mastra OR LangGraph |
| Memory | Mem0 + Qdrant |
| Web automation | Stagehand |
| Tracing/eval | Langfuse + Promptfoo + DeepEval |
| Web scraping | Crawl4AI |
| Doc parsing | Docling |
| LLM | Grok 4.3 (via xAI API) |
| Marketplace (Phase 5) | Next.js on Vercel |
| Execution env | GitHub Codespaces or Actions (no local Python builds required) |

## File tree (official — every prompt references this)

```
grok-agent/
├── .github/
│   └── workflows/
│       └── validate.yml
├── cli/
│   ├── grok-agent.ps1            # primary
│   └── grok-agent.py             # fallback
├── docs/
│   ├── index.md
│   ├── windows-guide.md
│   ├── for-xai-adoption.md
│   └── live-validator/
├── safety/
│   ├── scanner.py
│   └── constitution.md
├── scripts/
│   └── generate-template.py      # ClaudeX-style autonomous builder (Phase 4)
├── spec/
│   ├── v2.14/                    # reference only
│   └── v2.15/
│       ├── grok-agent.yaml
│       ├── changelog.md
│       └── windows-extensions.yaml
├── templates/
│   ├── finance/
│   │   ├── x-money-companion-dashboard/
│   │   ├── x-smart-cashtag-alpha-engine/
│   │   ├── x-creator-payout-optimizer/
│   │   └── x-money-vision-analyzer/
│   ├── creator/                  # 20+ templates (Phase 3)
│   ├── x-native/
│   ├── general/
│   └── super-agents/
│       ├── living-narrative-fabric/
│       ├── self-evolving-personal-os/
│       └── cross-reality-action-fabric/
├── .gitignore
├── CLAUDE.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE                       # Apache 2.0
├── pyproject.toml
├── README.md
├── README-OLD-REPOS.md
└── SECURITY.md
```

## Phases (with dependency graph)

| Phase | Name | Days | Depends on | Parallelizable with |
|---|---|---|---|---|
| 1 | Core Foundation | 1–14 | — | — |
| 2 | X Money Tools Suite | 15–56 | Phase 1 | Phase 3 (after day 35) |
| 3 | Creator Distribution | 35–70 | Phase 1 + at least 1 X Money tool live | Phase 2 (overlap days 35–56) |
| 4 | Super Agents | 57–90 | Phase 1, Phase 2 (≥2 tools shipped) | — |
| 5 | Marketplace & Scale | 91+ | Phase 4 | — |

## Key deliverables per phase

### Phase 1 (Foundation)
1. Repo + CLAUDE.md + LICENSE + .gitignore
2. Directory skeleton
3. `pyproject.toml`
4. `spec/v2.15/grok-agent.yaml` (unified schema)
5. `spec/v2.15/changelog.md` + `windows-extensions.yaml`
6. `cli/grok-agent.ps1` (primary CLI: install/new/validate/list/run)
7. `cli/grok-agent.py` (fallback)
8. `safety/scanner.py` + `safety/constitution.md`
9. 8 starter templates (2 finance, 2 creator, 2 x-native, 2 general)
10. Premium `README.md`
11. `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
12. `.github/workflows/validate.yml`
13. `docs/` (windows-guide, for-xai-adoption, index)
14. End-to-end smoke test
15. First X launch thread

### Phase 2 (X Money Tools — same recipe x4)
For each of: `x-money-companion-dashboard`, `x-smart-cashtag-alpha-engine`, `x-creator-payout-optimizer`, `x-money-vision-analyzer`:
- `app.py` (Streamlit)
- `grok-agent.yaml` (manifest)
- `prompts/` (Grok system prompts)
- `launcher.ps1`
- `README.md` with disclaimers
- Streamlit Cloud deploy
- "grok install this" smoke test

Vision Analyzer must one-click import into Companion Dashboard SQLite.

### Phase 3 (Creator Distribution)
- 20 creator templates in `templates/creator/`
- Landing page (GitHub Pages or thin Next.js)
- Outreach DM sequence (5 templates ready)
- Tracking sheet (Google Sheets or local SQLite)
- Public launch thread

### Phase 4 (Super Agents — same recipe x3)
For each of `living-narrative-fabric`, `self-evolving-personal-os`, `cross-reality-action-fabric`:
- `agent.py` (Mastra/LangGraph orchestration)
- `grok-agent.yaml` (super-agent kind)
- Memory layer (Mem0 + Qdrant)
- Public API connector helpers
- Provenance log
- Demo video script

Plus: `scripts/generate-template.py` (autonomous builder) + weekly Promptfoo+DeepEval+Langfuse loop.

### Phase 5 (Marketplace & Scale)
- Next.js marketplace on Vercel
- "Deploy to X" one-click button
- xAI partnership pitch (60-sec video + RFC doc)
- Creator Program v2 (paid tier + 20% rev share)

## Source references

The full project plan lives in `Grok_Agent_Platform___Full_Sequential_Project_Plan.md` (2,321 lines). When generating a prompt, if the plan already contains pre-written code/content for a deliverable, reference it as:

> "Use the artifact in [section name / line range] of the plan as the starting point. Adjust per the constraints below."

Pre-written artifacts in the plan include: full README.md, full CLAUDE.md, full pyproject.toml, partial `grok-agent.yaml` v2.15 schema, creator outreach templates, ROADMAP.md, SECURITY.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md.

## Glossary

- **"grok install this"** — the X-native install primitive (paste manifest + post → installs)
- **v2.15** — current manifest version (backwards compat with v2.14)
- **Super Agent** — flagship agent that orchestrates Grok + multiple public APIs + memory + provenance
- **Agent Constitution** — safety layer enforcing rules per agent
- **Public APIs** — the 1,400+ free API set Super Agents pull from (NewsAPI, GNews, Semantic Scholar, data.gov, yfinance, CoinGecko, and the rest of the catalog)
