<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->

# 💸 X Money Companion Dashboard

> Your X Money command center, on Windows — overview, transactions, analytics, Grok insights, tax export, and alerts.
>
> *Built to help xAI and Grok win the platform battle on X.*

> *I, the author of this agent, agree to the Grok Agent OS Constitution v1.0. I commit to keep this agent compliant or remove it from distribution.* — `@JanSol0s`

---

## ⚠️ Disclaimers (non-negotiable, Constitution Article V)

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for Vietnam-resident creators with international platform earnings.

These banners appear on every Streamlit tab, every Grok-generated insight card, and as the first row / first page of every CSV / PDF export. They are required by Constitution Article V.1 (finance) and V.2 (tax) and are auto-checked by `safety/scanner.py` on every install and every PR.

---

## What it is

The **anchor finance tool** of the Grok Agent OS suite. A local-first, Windows-native Streamlit dashboard that:

- Tracks every X Money transaction in a private SQLite database
- Categorizes transactions with Grok 4.3 (fully local, never uploaded)
- Surfaces analytics — cashflow, top counterparties, category trends, anomalies
- Generates Grok-powered insight cards you can act on
- Builds consent-gated tax exports (CSV / PDF) you hand to your accountant
- Warns you about unusual spend or missing data (in-app alerts, never posted to X without consent)

Your data never leaves `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\` unless you explicitly approve a consent gate. No telemetry. No third-party trackers in the UI. No silent cloud sync. (Constitution Article VII.)

---

## Quick Launch (Windows 11)

**TL;DR — one command, opens in your browser:**

```powershell
.\launcher.ps1
```

That's it. The launcher resolves Python 3.12+, installs pinned deps from `requirements.txt` on first run, ensures `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\` exists with an initialised SQLite, then opens `http://localhost:8501` in your default browser. For more control, see the three options below.

### Option A — `grok-agent install` (recommended)

```powershell
grok-agent install x-money-companion-dashboard
```

The CLI:

1. Resolves the manifest at `templates/finance/x-money-companion-dashboard/grok-agent.yaml`
2. Validates it against `spec/v2.15/grok-agent.yaml` (Pydantic deep validator)
3. Runs `safety/scanner.py` against the Agent Constitution
4. Only on a clean pass — copies the agent into `~\.grok-agent\agents\` and prepares the AppData folder

If anything fails the schema or the Constitution, install is refused. No partial installs.

### Option B — manual launch (for dev / contribution)

```powershell
cd templates\finance\x-money-companion-dashboard
.\launcher.ps1
```

The launcher does six things in order: shows the disclaimer banner; resolves Python 3.12+ (`python` then `py -3`); runs `python -m pip install --quiet -r requirements.txt` (skip with `-SkipDeps`); creates `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\` if missing; runs `init_db()` to create the SQLite schema (idempotent — safe on every launch); then runs `streamlit run app.py` headless and opens `http://localhost:8501` in your default browser (skip with `-NoBrowser`).

Optional flags:

```powershell
.\launcher.ps1 -Port 8765 -SkipDeps -NoBrowser
```

Chrome only, per the manifest's `windows.chrome_only: true`.

### Option C — direct Streamlit (developers only)

```powershell
cd templates\finance\x-money-companion-dashboard
python -m pip install -r requirements.txt
streamlit run app.py
```

---

## Where data lives (Windows-correct paths)

| Purpose | Path |
|---|---|
| SQLite database | `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\data.db` |
| Logs | `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\logs\` |
| Cache | `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\cache\` |
| Provenance log | `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\provenance.log` (append-only — every consent-gated action is recorded) |

These follow Constitution Article VII (local-first, privacy-first) and the repo-wide path convention in `CLAUDE.md` §9.

---

## The 6 tabs

| Tab | What it does | Disclaimer |
|---|---|---|
| 📊 **Overview** | Headline cashflow + this-month-vs-last-month delta + active alerts | V.1 |
| 💳 **Transactions** | Browsable, sortable transaction ledger straight from SQLite | V.1 |
| 📈 **Analytics** | Plotly charts for cashflow, top counterparties, category trends | V.1 |
| 🤖 **Grok Insights** | Grok 4.3 generates plain-English insight cards over your local data | V.1 (reinforced — AI-generated) |
| 📤 **Tax Export** | Build consent-gated CSV / PDF report for your accountant | V.1 + V.2 |
| 🔔 **Alerts** | In-app warnings for unusual spend or missing data | V.1 |

The 6-tab layout is the Recipe A canonical shape — every X Money tool inherits it where the tabs make sense.

---

## Cross-tool integration

The **X Money Vision Analyzer** (Tool #4) writes parsed receipts directly into this dashboard's SQLite via `data/import_receipts.py`. That importer is the only sibling-tool entry point this dashboard accepts; the schema is intentionally fixed so Tool #4 can be installed before or after Tool #1 without breaking the round-trip.

If you install both tools, drag-drop a receipt into the Vision Analyzer → it appears as a categorized transaction in this dashboard within seconds. No sync server, no cloud — direct SQLite write across two local agents on the same Windows machine. The constitution rule:

> *"The Vision Analyzer (Tool #4) is the only sibling tool permitted to write into this SQLite, and only via data/import_receipts.py."*

is enforced by the importer's pre-write check (Slot 4 / P22 deliverable).

---

## What the manifest declares

This agent ships under `grok-agent.yaml` v2.15 with:

- **Kind**: `finance-dashboard` — the canonical schema enum value for the V.1 + V.2 auto-disclaimer mapping. (There is no `tool` kind in the v2.15 enum; `finance-dashboard` is correct.)
- **5 Grok-callable tools**: `categorize_transaction`, `fetch_market_quote`, `fetch_relevant_news`, `build_tax_export`, `summarize_alerts`
- **3 declared public APIs**: `yfinance`, `newsapi`, `x_search` (via Grok 4.3) — all `privacy: "no_pii_sent"`
- **6 Constitution rules** specializing Articles I, IV, V, VII for finance use
- **2 consent gates**: `export_tax_report`, `sync_to_cloud`
- **Cost limits**: $0.50/session, $2.00/day, 200 API calls/session (Article VI.1)
- **Human-in-the-loop**: enabled, 60s timeout, confirm before tax export / cloud sync / any cost > $0.10 (Article VI.2)
- **Provenance**: enabled with `cite_sources: true` (Article IV)

Validate the manifest yourself any time:

```powershell
python cli\grok-agent.py validate templates\finance\x-money-companion-dashboard\grok-agent.yaml
python safety\scanner.py scan  templates\finance\x-money-companion-dashboard\grok-agent.yaml
```

Both must return zero `error`-level findings before this agent is allowed to install. CI (`.github/workflows/validate.yml`) runs the same checks on every push and PR to `main`.

---

## Smoke test & `grok install this` readiness

Before this dashboard goes near a real X Money account, every commit must pass the offline smoke test:

```powershell
.\smoke_test.ps1
```

The script runs 11 checks — file presence, Python interpreter, schema validation, Constitution scanner, Apache 2.0 headers, Article V disclaimer presence in `app.py` / `prompts/system.md` / `README.md`, manifest-tool importability, SQLite round-trip, API client offline-safety, `launcher.ps1` parse, and `.streamlit/config.toml` shape + privacy posture — and prints **`Tool #1 - X Money Companion Dashboard: PASS`** when every check lands green. Exit code is `0` on PASS, `1` on FAIL. Add `-Json` for a machine-readable summary suitable for CI.

```powershell
.\smoke_test.ps1 -Json | Out-File smoke.json
```

### `grok install this` (X-native shorthand)

Once the smoke test is green, this dashboard is ready for the X-native installation primitive. In a tweet or DM that mentions `@grok`, you can write:

```
grok install this
```

…with the dashboard's manifest URL or template name attached. The Grok Agent OS orchestra resolves that to the equivalent local CLI flow:

```powershell
grok-agent install x-money-companion-dashboard
```

…which runs the same Pydantic deep validator + Constitution scanner before writing any files. Both routes refuse to install if the smoke test would fail.

---

## Build slots (Recipe A)

All 6 slots are shipped on `main`; Tool #1 is **COMPLETE**:

| Slot | Files | Status |
|---|---|---|
| 1 — Manifest + README | `grok-agent.yaml`, `README.md` | ✅ P19 |
| 2 — Streamlit app skeleton | `app.py`, `requirements.txt` | ✅ P20 |
| 3 — Grok prompts | `prompts/system.md`, `prompts/user_templates.md` | ✅ P21 |
| 4 — Data layer + APIs | `data/__init__.py`, `data/store.py`, `data/api_clients.py` (accepts `data/import_receipts.py` from Tool #4) | ✅ P22 |
| 5 — Launcher + Streamlit Cloud config | `launcher.ps1`, `.streamlit/config.toml` | ✅ P23 |
| 6 — Smoke test + `grok install this` readiness | `smoke_test.ps1` (11 checks); README Smoke-test section | ✅ this prompt (P24) |

---

## License

Apache License 2.0 — see [`LICENSE`](../../../LICENSE) at the repo root.

---

> We're ecosystem allies — built to help xAI and Grok win. This dashboard is the missing local-first finance layer that makes the X Money launch land for every creator on Windows.
