<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 🔭 X Smart Cashtag Alpha Engine

> Cashtag-aware market intelligence for X — narrative momentum, contradictions across sources, and Grok-powered alpha signals with full provenance.
>
> *Built for xAI, X, Grok and the ecosystem community. ❤️*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Disclaimers (non-negotiable, Constitution Article V)

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

These banners appear on every Streamlit tab, on every Grok-generated alpha report, and as the first row / first page of any export. They are required by Constitution Article V.1 (finance) and surfaced defensively as V.2 on tabs that touch hypothetical gains. Auto-checked by `safety/scanner.py` on every install and every PR.

---

## What it is

The **alpha engine** of the Grok Agent OS suite. A local-first, Windows-native Streamlit app that:

- Tracks a watchlist of cashtags (`$XAI`, `$X`, plus whatever you add)
- Pulls live prices from yfinance (equities / FX) and CoinGecko (crypto)
- Reads the X cashtag stream via `x_search` (Grok 4.3 tool-call) — never via authenticated scraping
- Generates **Grok-powered alpha reports** that surface narrative momentum, flag contradictions across sources, and cite every claim
- Lets you run **portfolio simulations** with hypothetical positions over a date window
- Surfaces trending cashtags so you spot moves before they hit your feed
- Ships with `real_time_x` enabled for cashtag-change triggers — but **never posts to X** (`posts: false`, `max_posts_per_day: 0`)

Your watchlist, alpha reports, and simulation history never leave `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\` unless you explicitly approve a consent gate. No telemetry. No third-party trackers. (Constitution Article VII.)

---

## Quick Launch (Windows 11)

**TL;DR — one command, opens in your browser:**

```powershell
.\launcher.ps1
```

That's it. The launcher resolves Python 3.12+, installs pinned deps from `requirements.txt` on first run, ensures `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\` exists with an initialised SQLite, then opens `http://localhost:8502` in your default browser. (Port 8502 leaves 8501 free for Tool #1 — both can run side by side.) For more control, see the three options below.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install x-smart-cashtag-alpha-engine
```

The CLI resolves the manifest, validates against `spec/v2.15/grok-agent.yaml`, runs `safety/scanner.py` against the Constitution, and only on a clean pass copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder. If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — manual launch (for dev / contribution)

```powershell
cd templates\finance\x-smart-cashtag-alpha-engine
.\launcher.ps1
```

The launcher does six things in order: shows the disclaimer banner; resolves Python 3.12+ (`python` then `py -3`); runs `python -m pip install --quiet -r requirements.txt` (skip with `-SkipDeps`); creates `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\` if missing; calls `data.store.init_db()` to create the SQLite schema (idempotent — safe on every launch); then runs `streamlit run app.py` headless on port 8502 and opens the URL in your default browser (skip with `-NoBrowser`).

Optional flags:

```powershell
.\launcher.ps1 -Port 8765 -SkipDeps -NoBrowser
```

Chrome only, per the manifest's `windows.chrome_only: true`.

### Option C — direct Streamlit (developers only)

```powershell
cd templates\finance\x-smart-cashtag-alpha-engine
python -m pip install -r requirements.txt
streamlit run app.py
```

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| SQLite database | `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\data.db` |
| Logs | `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\logs\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\cache\` |
| Provenance log | `$env:LOCALAPPDATA\grok-agent\x-smart-cashtag-alpha-engine\provenance.log` (append-only — every consent-gated action + every external API call is recorded) |

These follow Constitution Article VII (local-first, privacy-first) and the repo-wide path convention in `CLAUDE.md` §9.

---

## The 6 tabs (planned)

| Tab | What it does | Disclaimer |
|---|---|---|
| 📊 **Overview** | Top movers + active alerts + portfolio P&L summary | V.1 |
| 🔭 **Watchlist** | Your cashtags with live prices and intraday deltas | V.1 |
| 📈 **Charts** | Plotly time-series + relative-strength view per cashtag | V.1 |
| 🤖 **Alpha Reports** | Grok-generated narrative + signal + contradictions per cashtag | V.1 (reinforced — AI-generated) |
| 🎯 **Portfolio Simulator** | What-if positions, hypothetical P&L over a date window | V.1 + V.2 |
| 🌊 **Trending** | Top cashtags trending on X right now via `x_search` | V.1 |

Tabs land in Slot 2 / P26 (Streamlit skeleton). The 6-tab shape adapts Recipe A's official layout for the alpha-engine surface.

---

## Cross-tool integration

This engine **composes on top of** the X Money Companion Dashboard (Tool #1). When both tools are installed, the alpha engine can:

- Read the user's transaction history from Tool #1's SQLite to seed the Portfolio Simulator with real positions (read-only, no schema modification)
- Export current holdings to Tool #1's `transactions` table via a planned `export_holdings_to_companion_dashboard` function — consent-gated and audit-logged

This is the inverse direction from Tool #4 → Tool #1: the alpha engine reads from Tool #1, the vision analyzer (Tool #4) writes into Tool #1. Tool #1 remains the official local store for X Money state.

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `alpha-engine` — the official schema enum value for cashtag / market-intelligence tools. (Your prompt §4 said `finance-dashboard`; both are valid v2.15 kinds and both auto-apply V.1+V.2 disclaimers per Article V, but `alpha-engine` is the more accurate enum for narrative-momentum + signal use cases — and matches what the Phase 1 P12 starter and the recipe-skill table both already use.)
- **5 Grok-callable tools**: `track_cashtag`, `fetch_cashtag_quote`, `fetch_cashtag_news`, `generate_alpha_report`, `simulate_portfolio`
- **4 declared public APIs**: `yfinance`, `coingecko`, `newsapi`, `x_search` (via Grok 4.3) — all `privacy: "no_pii_sent"`
- **`real_time_x` enabled** with `cashtag_change` + `schedule` triggers, weekday cron `0 9,17 * * 1-5`, and `posts: false` / `max_posts_per_day: 0` — the engine watches but never publishes
- **`provenance` enabled** with `cite_sources: true` and `contradiction_detection: true` (Article IV is alpha-critical for this tool)
- **6 Constitution rules** specializing Articles II, IV, V, VII for alpha use
- **1 consent gate**: `sync_to_cloud` (no posting / money-moving gates because the engine doesn't do those today)
- **Cost limits**: $1.00/session, $5.00/day, 500 API calls/session (Article VI.1)
- **Human-in-the-loop**: enabled, 60s timeout, confirm before cloud sync / any cost > $0.20 (Article VI.2)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\finance\x-smart-cashtag-alpha-engine\grok-agent.yaml
python safety\scanner.py scan  templates\finance\x-smart-cashtag-alpha-engine\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install.

---

## Smoke test & `grok install this` readiness

Before this engine goes near a real cashtag stream, every commit must pass the offline smoke test:

```powershell
.\smoke_test.ps1
```

The script runs 15 checks — file presence, Python interpreter, schema validation, Constitution scanner, Apache 2.0 headers, Article V.1+V.2 disclaimer presence, **Article III contradiction-flagging language presence in `system.md` + `user_templates.md`** (the alpha engine's defining capability), manifest-tool importability across `data.store` + `data.api_clients`, SQLite `track_cashtag` + watchlist round-trip, `simulate_portfolio` computation + persist, `generate_alpha_report` orchestration + persist, API offline-safety (`search_x_posts` stub shape), **cross-tool read via `fetch_companion_dashboard_holdings`** (Tool #1 SQLite, optional but verified gracefully when present), `launcher.ps1` parse, and `.streamlit/config.toml` shape with `port=8502` verified — and prints **`Tool #2 - X Smart Cashtag Alpha Engine: PASS`** when every check lands green. Exit code is `0` on PASS, `1` on FAIL. Add `-Json` for machine-readable output suitable for CI.

```powershell
.\smoke_test.ps1 -Json | Out-File smoke.json
```

### `grok install this` (X-native shorthand)

Once the smoke test is green, this engine is ready for the X-native installation primitive. In a tweet or DM that mentions `@grok`, you can write:

```
grok install this
```

…with the engine's manifest URL or template name attached. The Grok Agent OS orchestra resolves that to the equivalent local CLI flow:

```powershell
grok-agent install x-smart-cashtag-alpha-engine
```

…which runs the same Pydantic deep validator + Constitution scanner before writing any files. Both routes refuse to install if the smoke test would fail.

---

## Build slots (Recipe A)

All 6 slots are shipped on `main`; Tool #2 is **COMPLETE**:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + README | `grok-agent.yaml`, `README.md` | ✅ P25 |
| 2 — Streamlit app skeleton (6 tabs) | `app.py`, `requirements.txt` | ✅ P26 |
| 3 — Grok prompts | `prompts/system.md`, `prompts/user_templates.md` | ✅ P27 |
| 4 — Data layer + APIs | `data/__init__.py`, `data/store.py`, `data/api_clients.py` | ✅ P28 |
| 5 — Launcher + Streamlit Cloud config | `launcher.ps1`, `.streamlit/config.toml` | ✅ P29 |
| 6 — Smoke test + `grok install this` readiness | `smoke_test.ps1` (15 checks); README Smoke-test section | ✅ this prompt (P30) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win. Tool #1 is your X Money command center; this engine is its sister tool that turns the X cashtag stream into auditable, contradiction-flagged alpha you can trust.
