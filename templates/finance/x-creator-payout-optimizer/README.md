<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 📈 X Creator Payout Optimizer

> Earnings forecasting, content optimization, and tax estimator for X creators. Reads from the X Money Companion Dashboard (Tool #1) and the X Money Vision Analyzer (Tool #4) for the richest possible local data.
>
> *Built to help xAI and Grok win the platform battle on X.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Disclaimers (non-negotiable, Constitution Article V)

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

These banners appear on every Streamlit tab, every Grok-generated forecast and tax-estimator output, and as the first row / first page of any export. The **V.2 banner is mandatory on every page** of this tool — the tax estimator is a primary feature, not a side feature, so the banner travels everywhere. Auto-checked by `safety/scanner.py` on every install and every PR.

---

## What it is

The **earnings + content + tax tool** of the Grok Agent OS suite — and the **last** of the four X Money tools per the build order. A local-first, Windows-native Streamlit app that:

- Forecasts your next-30/60/90-day creator earnings using your local transaction history (from Tool #1) and recent X engagement metrics
- Optimizes content topics by surfacing angles correlated with the highest historical engagement and payout
- Estimates your tax burden on creator earnings for a date range, with explicit jurisdiction handling and the V.2 disclaimer baked into every export
- Tracks X engagement / reach / payout metrics in one dashboard
- Computes per-topic content ROI by joining your revenue rows (Tool #1's `transactions`) with your cost rows (Tool #4's parsed receipts for editing fees, software subscriptions, props, etc.)

All earnings, receipt, and forecast data stays under `$env:LOCALAPPDATA\grok-agent\x-creator-payout-optimizer\` unless you explicitly approve a consent gate. No telemetry. No third-party trackers. **Read-only on Tool #1 and Tool #4** — this tool composes on top of its siblings without ever modifying them.

---

## Quick Launch (Windows 11)

**TL;DR — one command, opens in your browser:**

```powershell
.\launcher.ps1
```

That's it. The launcher resolves Python 3.12+, installs pinned deps from `requirements.txt` on first run, ensures `$env:LOCALAPPDATA\grok-agent\x-creator-payout-optimizer\` exists with an initialised SQLite, then opens `http://localhost:8503` in your default browser. (Port 8503 fits the suite layout: Tool #1=8501, Tool #2=8502, Tool #3=8503, Tool #4=8504 — all four X Money tools coexist.) For more control, see the three options below.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install x-creator-payout-optimizer
```

The CLI resolves the manifest, validates against `spec/v2.15/grok-agent.yaml`, runs `safety/scanner.py` against the Constitution, and only on a clean pass copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder. If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — manual launch (for dev / contribution)

```powershell
cd templates\finance\x-creator-payout-optimizer
.\launcher.ps1
```

The launcher ships in Slot 5 / P41 and follows Tools #1 / #2 / #4's pattern: Python 3.12+ resolution, idempotent dependency install, AppData + SQLite init via `data.store.init_db()`, then headless Streamlit on `http://localhost:8503`.

### Option C — direct Streamlit (developers only)

```powershell
cd templates\finance\x-creator-payout-optimizer
python -m pip install -r requirements.txt
streamlit run app.py
```

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| SQLite database (forecasts, metrics, ROI history) | `$env:LOCALAPPDATA\grok-agent\x-creator-payout-optimizer\data.db` |
| Logs | `$env:LOCALAPPDATA\grok-agent\x-creator-payout-optimizer\logs\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\x-creator-payout-optimizer\cache\` |
| Provenance log | `$env:LOCALAPPDATA\grok-agent\x-creator-payout-optimizer\provenance.log` (append-only — every consent-gated action + every cross-tool read is recorded) |

These follow Constitution Article VII (local-first, privacy-first) and the repo-wide path convention in `CLAUDE.md` §9.

---

## The 6 tabs (planned)

| Tab | What it does | Disclaimer |
|---|---|---|
| 📈 **Earnings Forecast** | Predicted next-30/60/90-day creator earnings from local Tool #1 history + X metrics | V.1 + V.2 (forecasts touch tax-relevant numbers) |
| ✍️ **Content Optimizer** | Topic suggestions with predicted engagement based on past payouts | V.1 |
| 🧮 **Tax Estimator** | Date-range tax burden estimate; consent-gated export with full V.1+V.2 banners | V.1 + V.2 |
| 📊 **X Metrics** | Engagement / reach / payouts dashboard (via `fetch_x_metrics` → `x_search`) | V.1 |
| 💰 **Content ROI** | Per-topic profitability — Tool #1 revenue × Tool #4 receipt costs in one view | V.1 + V.2 |
| ⚙️ **Settings** | API keys, default jurisdiction, cross-tool source paths, cloud-sync opt-in (default off) | V.1 |

Tabs land in Slot 2 / P38 (Streamlit skeleton). The 6-tab shape adapts Recipe A's canonical layout for the creator-payout surface — heavier on synthesis (forecast / ROI) than on ingestion.

---

## Cross-tool integration (Tool #3 → Tool #1 + Tool #4, read-only)

This tool **composes on top of** the X Money Companion Dashboard (Tool #1) and the X Money Vision Analyzer (Tool #4). When all three tools are installed, the optimizer can:

**Read from Tool #1** (`transactions` table at `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\data.db`):

- Revenue rows tagged `x_payouts` / `ad_revenue` for the earnings-forecast input
- Subscription / infrastructure / food_drink rows for the cost-side of content ROI
- Read-only — never modifies the schema, never writes a row

**Read from Tool #4** (`receipts` + `parsed_items` tables at `$env:LOCALAPPDATA\grok-agent\x-money-vision-analyzer\data.db`):

- Parsed receipt rows for content-production cost detail (editing fees, software, props)
- Line-item granularity that Tool #1's `transactions` table doesn't carry

**Both reads are read-only** — Constitution Article III is enforced by this manifest's rule:

> *"Cross-tool READS only. Tool #1 (transactions) and Tool #4 (receipts + parsed_items) are read-only targets. No cross-tool writes are permitted by this manifest (Article III)."*

If either sibling tool is not installed, the optimizer degrades gracefully: forecasts run on whatever local history exists, ROI shows revenue-only or cost-only depending on which DB is present, and the Settings tab surfaces a clear "Tool #N not installed" warning rather than crashing.

This is the **inverse direction from Tool #4 → Tool #1** (which writes via the Constitution-permitted `data/import_receipts.py` cross-tool writer): Tool #3 only reads. The cross-tool integration map for the X Money suite as of Tool #3:

```
Tool #4 ── writes (parsed receipts) ──► Tool #1
Tool #2 ── reads  (transactions)    ──► Tool #1
Tool #3 ── reads  (transactions)    ──► Tool #1
Tool #3 ── reads  (receipts/items)  ──► Tool #4
```

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `creator-payout-optimizer` — the canonical schema enum value for this exact tool category. (Your prompt §4 said `finance-dashboard`; both are valid v2.15 kinds and both auto-apply V.1 disclaimers per Article V, but `creator-payout-optimizer` is the more accurate enum and matches the recipe-skill table for this slug; V.2 is mandatory in this manifest regardless because the tax estimator is a primary feature, not a side feature.)
- **5 Grok-callable tools**: `forecast_earnings`, `optimize_content_topic`, `estimate_tax_burden`, `fetch_x_metrics`, `analyze_content_roi`
- **3 declared public APIs**: `x_search` (via Grok 4.3), `yfinance`, `newsapi` — all `privacy: "no_pii_sent"`
- **`pii_handling: "local-only"`** — this tool reads but does not send PII to any cloud (vision is the only X Money tool with `redacted-cloud`)
- **`provenance` enabled** with `cite_sources: true` (every forecast cites its data window + sources)
- **6 Constitution rules** specializing Articles III, IV, V.1, V.2, VII for creator-payout use
- **2 consent gates**: `export_tax_estimate`, `sync_to_cloud` (no cross-tool write gates because this tool reads only)
- **Cost limits**: $1.00/session, $5.00/day, **300 API calls/session** (between Tool #1's 200 and Tool #2's 500 — forecast queries are mid-weight) — Article VI.1
- **Human-in-the-loop**: enabled, 60s timeout, confirm before tax-export / cloud sync / any cost > $0.20 (Article VI.2)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\finance\x-creator-payout-optimizer\grok-agent.yaml
python safety\scanner.py scan  templates\finance\x-creator-payout-optimizer\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install.

---

## Build slots (Recipe A)

This is **Slot 1 of 6** — manifest + folder + README. The remaining slots populate this folder over P38–P42:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + README | `grok-agent.yaml`, `README.md` | ✅ this prompt (P37) |
| 2 — Streamlit app skeleton (6 tabs) | `app.py`, `requirements.txt` | ⏭️ P38 |
| 3 — Grok prompts | `prompts/system.md`, `prompts/user_templates.md` | ⏭️ P39 |
| 4 — Data layer + APIs (with cross-tool readers for Tool #1 + Tool #4) | `data/__init__.py`, `data/store.py`, `data/api_clients.py`, `data/companion_reader.py`, `data/vision_reader.py` | ⏭️ P40 |
| 5 — Launcher + Streamlit Cloud config | `launcher.ps1`, `.streamlit/config.toml` | ⏭️ P41 |
| 6 — Smoke test + `grok install this` readiness | `smoke_test.ps1` | ⏭️ P42 |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win. With Tool #1 (the command center), Tool #2 (the alpha brain), Tool #4 (the front door for receipts), and now this Tool #3 (the forecaster + content optimizer + tax estimator), the X Money tool suite is feature-complete: every dollar a creator earns and every dollar they spend is local, audit-able, and Grok-aware.
