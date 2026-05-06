---
name: x-money-tool-recipe
description: Use this skill whenever building, extending, or debugging any of the four X Money tools — `x-money-companion-dashboard`, `x-smart-cashtag-alpha-engine`, `x-creator-payout-optimizer`, or `x-money-vision-analyzer` — or when creating a new finance-dashboard / alpha-engine / creator-payout-optimizer / vision-analyzer kind agent. Triggers on phrases like "build x-money-*", "add to companion dashboard", "cashtag tool", "payout optimizer", "vision analyzer", or any task in `templates/finance/`. The skill encodes the reference 6-file pattern every X Money tool follows so you don't reinvent structure on each tool.
---

# x-money-tool-recipe

The reference pattern for X Money tools. All 4 tools share the same skeleton — the differences are content, not architecture. Use this skill to ensure consistency across the suite.

## The 6-file pattern

Every X Money tool lives at `templates/finance/{slug}/` and contains exactly these 6 files:

```
templates/finance/{slug}/
├── grok-agent.yaml         # Manifest (v2.15)
├── app.py                  # Streamlit entry point
├── launcher.ps1            # PowerShell one-click launcher
├── requirements.txt        # Python deps
├── README.md               # Tool docs (with disclaimers)
├── prompts/
│   ├── system.md           # Grok system prompt
│   └── user_templates.md   # Reusable user prompt templates
├── data/
│   ├── store.py            # SQLite layer
│   └── api_clients.py      # External API wrappers
└── .streamlit/
    └── config.toml         # Streamlit theming
```

## The 4 tools (parameters table)

| Slug | Display Name | Kind | Primary APIs | Unique features |
|---|---|---|---|---|
| `x-money-companion-dashboard` | "X Money Companion Dashboard" | `finance-dashboard` | x_money_api, yfinance, newsapi | Tax export with disclaimers; Grok categorization |
| `x-smart-cashtag-alpha-engine` | "Smart Cashtag Alpha Engine" | `alpha-engine` | yfinance, coingecko, x_search via grok | Watchlist, Alpha Reports from X, portfolio simulator |
| `x-creator-payout-optimizer` | "Creator Payout Optimizer" | `creator-payout-optimizer` | x_metrics_api, yfinance | Earnings forecast, content optimization, tax estimator |
| `x-money-vision-analyzer` | "X Money Vision Analyzer" | `vision-analyzer` | grok-4.3 vision | Drag-drop receipts, imports into Tool #1 SQLite |

**Build order**: 1 → 2 → 4 → 3 (matches project plan weeks 3-8).

**Cross-tool integration**: Tool #4 (Vision Analyzer) MUST write directly into Tool #1's SQLite at `$env:LOCALAPPDATA\grok-agent\x-money-companion-dashboard\data.db`. Use `data/import_receipts.py` in Tool #1 to receive.

## Official templates (use these as base, parameterize per tool)

### `grok-agent.yaml` template

```yaml
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
version: "2.15"
kind: "{KIND}"                                # finance-dashboard | alpha-engine | or another v2.15 finance kind
name: "{slug}"                                # e.g. x-money-companion-dashboard
description: "{ONE_LINER}"
author: "@JanSol0s"
license: "Apache-2.0"

windows:
  launcher: "launcher.ps1"
  appdata_folder: "grok-agent/{slug}"
  min_powershell_version: "5.1"
  requires_admin: false

grok:
  model: "grok-4.3"
  temperature: 0.3
  max_tokens: 4096
  system_prompt_file: "prompts/system.md"
  tool_calling: true
  vision: {VISION_BOOL}                       # true ONLY for vision-analyzer

constitution:
  rules:
    - "Always show 'Not financial advice' banner on every page"
    - "Never share transaction data outside local SQLite without explicit consent"
    - "Tax export includes 'Not tax advice' disclaimer"
  consent_gates:
    - export_tax_report
    - sync_to_cloud
    - send_alert_via_x

safety:
  pii_handling: "local-only"
  data_retention_days: 365
  scanner_severity_floor: "warn"

dependencies:
  python:
    version: "^3.12"
    packages:
      - "streamlit ^1.33"
      - "pandas ^2.2"
      - "plotly ^5.22"
      - "pydantic ^2.7"
      # tool-specific packages added here
```

### `app.py` skeleton (Streamlit)

```python
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
"""
{DISPLAY_NAME}
{ONE_LINER}

Built for xAI, X, Grok and the ecosystem community. ❤️
"""
import streamlit as st
from pathlib import Path

# Tool-specific imports
from data.store import init_db, get_connection
from data.api_clients import GrokClient

# Windows AppData path (correct for Windows users)
APPDATA = Path.home() / "AppData" / "Local" / "grok-agent" / "{slug}"
APPDATA.mkdir(parents=True, exist_ok=True)
DB_PATH = APPDATA / "data.db"

# Page config
st.set_page_config(
    page_title="{DISPLAY_NAME}",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize SQLite on first run
init_db(DB_PATH)

# MANDATORY disclaimer banner
def disclaimer_banner():
    st.warning(
        "⚠️ **Not financial advice.** This tool provides information only. "
        "Always consult a licensed financial advisor before making decisions."
    )

# Header
st.title("💸 {DISPLAY_NAME}")
st.caption("Built for xAI, X, Grok and the ecosystem community. ❤️")
disclaimer_banner()

# Tab navigation (6 tabs is official for Tool #1; adjust per tool)
tab_overview, tab_transactions, tab_analytics, tab_grok, tab_export, tab_alerts = st.tabs([
    "📊 Overview",
    "💳 Transactions",
    "📈 Analytics",
    "🤖 Grok Insights",
    "📤 Tax Export",
    "🔔 Alerts",
])

with tab_overview:
    st.header("Overview")
    # ... tool-specific content
    pass

with tab_transactions:
    st.header("Transactions")
    pass

with tab_analytics:
    st.header("Analytics")
    pass

with tab_grok:
    st.header("Grok Insights")
    disclaimer_banner()  # Reinforce on AI-generated content
    pass

with tab_export:
    st.header("Tax Export")
    st.error(
        "⚠️ **Not tax advice.** Tax obligations vary by jurisdiction. "
        "Consult a licensed tax professional."
    )
    pass

with tab_alerts:
    st.header("Alerts")
    pass

# Footer
st.markdown("---")
st.caption("Built for xAI, X, Grok and the ecosystem community. ❤️ | Apache 2.0 | @JanSol0s")
```

### `launcher.ps1` template

```powershell
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# Launcher for {DISPLAY_NAME}

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Banner
Write-Host ""
Write-Host "  ╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║   {DISPLAY_NAME}" -ForegroundColor Cyan
Write-Host "  ║   Built for xAI, X, Grok and the ecosystem community. ❤️" -ForegroundColor DarkCyan
Write-Host "  ╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python 3.12+ required. Install from python.org" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python: $pythonVersion" -ForegroundColor Green

# Check Streamlit
$streamlitCheck = python -c "import streamlit" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "→ Installing dependencies..." -ForegroundColor Yellow
    python -m pip install -r "$scriptDir\requirements.txt" --quiet
}
Write-Host "✓ Dependencies ready" -ForegroundColor Green

# Launch
Write-Host ""
Write-Host "→ Launching at http://localhost:8501" -ForegroundColor Yellow
Write-Host ""
Set-Location $scriptDir
streamlit run app.py
```

### `data/store.py` skeleton

```python
# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
"""SQLite layer for {DISPLAY_NAME}. Local-first, privacy-first."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Schema version — bump when migration needed
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Tool-specific tables go here
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_date TEXT NOT NULL,            -- ISO 8601
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    counterparty TEXT,
    memo TEXT,
    category TEXT,
    source TEXT NOT NULL,             -- 'manual' | 'vision' | 'api'
    raw_data TEXT,                    -- JSON blob for source data
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
"""

def init_db(db_path: Path) -> None:
    """Initialize the database schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )
        conn.commit()

@contextmanager
def get_connection(db_path: Path):
    """Context manager for SQLite connections."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

### `prompts/system.md` template

```markdown
<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->

# System Prompt — {DISPLAY_NAME}

You are the **{DISPLAY_NAME}** — a Grok-powered assistant inside the user's local {DISPLAY_NAME}.

## Your role
- Help the user understand their {DOMAIN} ({transactions / portfolio / earnings / receipts})
- Categorize, summarize, and surface insights
- Suggest actions but NEVER take real-world actions without explicit user consent

## Hard rules
1. **You are NOT a financial advisor.** Every output where the user might act on it includes "Not financial advice."
2. **Never share user data outside the local environment.** No cloud calls without explicit consent.
3. **Be direct and useful.** No padding, no sycophancy, no excessive caveats beyond the mandatory disclaimer.
4. **Source any claim about market data.** Cite the API source ({API_LIST}).
5. **Respect privacy.** If the user shares sensitive info, never repeat it in summaries unnecessarily.

## What you have access to
- The user's local SQLite at `{DB_PATH}` (read-only unless function call requests write)
- {API_LIST}
- The user's stated context (Vietnam-resident creator, X handle @JanSol0s, and similar profile facts)

## Output style
- Tight bullets when listing
- Numbers with units ($, %, days)
- Highlight surprises ("⚠️ This is 3x your usual spend")
- Never assume what the user wants — ask if ambiguous

## Built for xAI, X, Grok and the ecosystem community. ❤️
```

## Step-by-step build order per tool (6 prompts each)

When Grok produces prompts for a single X Money tool, expect them in this order:

1. **Manifest + folder + README** (20min) — `grok-agent.yaml` + `README.md` (with disclaimers)
2. **Streamlit app skeleton** (45min) — `app.py` + `requirements.txt` + `.streamlit/config.toml`
3. **Grok prompts** (30min) — `prompts/system.md` + `prompts/user_templates.md`
4. **Data layer + APIs** (60min) — `data/store.py` + `data/api_clients.py`
5. **Launcher + cloud config** (20min) — `launcher.ps1` + Streamlit Cloud deploy config
6. **Smoke test + polish** (30min) — manifest validation, README disclaimer audit, end-to-end run

If a Grok prompt is bigger than this slot, split it. If smaller, combine.

## Cross-tool integration spec

### Tool #4 → Tool #1 (Vision Analyzer feeds Companion Dashboard)

**On Vision Analyzer (Tool #4) side:**
```python
# data/exporter.py
import sqlite3
from pathlib import Path

def import_to_companion_dashboard(parsed_receipt: dict) -> int:
    """Write a parsed receipt directly into Companion Dashboard SQLite."""
    companion_db = Path.home() / "AppData" / "Local" / "grok-agent" / "x-money-companion-dashboard" / "data.db"

    if not companion_db.exists():
        raise FileNotFoundError(
            "Companion Dashboard SQLite not found. "
            "Install x-money-companion-dashboard first."
        )

    with sqlite3.connect(str(companion_db)) as conn:
        cursor = conn.execute(
            """
            INSERT INTO transactions (tx_date, amount, currency, counterparty, memo, category, source, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, 'vision', ?)
            """,
            (
                parsed_receipt["date"],
                parsed_receipt["amount"],
                parsed_receipt.get("currency", "USD"),
                parsed_receipt.get("vendor", ""),
                parsed_receipt.get("memo", ""),
                parsed_receipt.get("category", "uncategorized"),
                str(parsed_receipt),  # raw JSON blob
            ),
        )
        conn.commit()
        return cursor.lastrowid
```

This is the reference pattern — direct SQLite writes, no API layer between tools, local-first.

## Streamlit Cloud deployment notes

All 4 tools deploy to Streamlit Cloud free tier. Each gets its own app:
- `xmoney-companion.streamlit.app`
- `xmoney-cashtag.streamlit.app`
- `xmoney-payout.streamlit.app`
- `xmoney-vision.streamlit.app`

`.streamlit/config.toml`:
```toml
# Copyright 2026 AgentMindCloud
[theme]
base = "dark"
primaryColor = "#FF6B00"           # cinnabar (Residual Frequencies palette)
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1A1F2E"
textColor = "#F5F5DC"               # parchment
font = "monospace"

[server]
headless = true
enableCORS = false

[browser]
gatherUsageStats = false
```

Secrets handling: every secret goes in `.streamlit/secrets.toml` (gitignored). Reference in code as `st.secrets["API_KEY"]`.

## Pre-ship checklist for each tool

- [ ] Manifest validates (`python cli/grok-agent.py validate ...`)
- [ ] "Not financial advice" banner on every Streamlit tab
- [ ] Launcher works on stock Windows 11 PowerShell 5.1
- [ ] `streamlit run app.py` starts without error
- [ ] SQLite writes to `$env:LOCALAPPDATA\grok-agent\{slug}\` (Windows-correct path)
- [ ] Apache 2.0 header on every code file
- [ ] README has "Built for xAI, X, Grok and the ecosystem community"
- [ ] Tool deployed to Streamlit Cloud and accessible via URL
- [ ] "grok install this" smoke test passes
- [ ] Tool #4 specifically: import-to-Tool-#1 round-trip verified
