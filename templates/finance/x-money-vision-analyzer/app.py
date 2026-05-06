# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""X Money Vision Analyzer — Streamlit skeleton (Recipe A Slot 2 / P32).

The vision-tool of the Grok Agent OS suite. This module is the visual
layer; the data layer + the cross-tool importer ship in Slot 4 / P34
under ``data/`` (including ``data/import_receipts.py`` which writes
parsed receipts directly into Tool #1's SQLite). The Grok prompt layer
ships in Slot 3 / P33 under ``prompts/``. Until then this skeleton
renders 6 tabs with realistic placeholder extractions + the mandatory
Article V disclaimer on every tab (V.2 stacked on Parsed Preview and
Import to Tool #1, since both tabs touch tax-relevant numbers).

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st


# --- Local-first storage path (Constitution Article VII) -------------------

def appdata_root() -> Path:
    """Resolve the local-first data folder for this analyzer.

    Production target is Windows 11 + PowerShell, where this resolves to
    ``$env:LOCALAPPDATA\\grok-agent\\x-money-vision-analyzer``. On
    non-Windows runs (Streamlit Cloud, dev containers, CI) we fall back
    to ``~/.local/share/...`` so the skeleton boots cleanly everywhere.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-vision-analyzer"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-money-vision-analyzer"


def companion_db_path() -> Path:
    """Tool #1's official SQLite path — the cross-tool write target."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-companion-dashboard" / "data.db"
    return (
        Path.home() / ".local" / "share"
        / "grok-agent" / "x-money-companion-dashboard" / "data.db"
    )


APPDATA = appdata_root()
DB_PATH = APPDATA / "data.db"
RECEIPTS_DIR = APPDATA / "receipts"


def ensure_appdata() -> None:
    """Create AppData folder + receipts/ subfolder + SQLite stub on first run.

    Slot 4 / P34 replaces this stub with a full ``data/store.py`` module
    plus the cross-tool ``data/import_receipts.py`` writer. The skeleton
    only needs the folders + a meta table so smoke tests pass and the
    user can see where their data will live.
    """
    APPDATA.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta ("
            " key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("skeleton_version", "0.32.0"),
        )
        conn.commit()


# --- Page config -----------------------------------------------------------

st.set_page_config(
    page_title="X Money Vision Analyzer",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_appdata()


# --- Disclaimer + footer ---------------------------------------------------

def disclaimer_banner(*, include_tax: bool = False, ai_reinforced: bool = False) -> None:
    """Render the mandatory Article V disclaimers. Called on every tab."""
    st.warning(
        "**NOT FINANCIAL ADVICE.** This tool provides information only. "
        "Always consult a licensed financial advisor before making decisions."
    )
    if include_tax:
        st.error(
            "**NOT TAX ADVICE.** Tax obligations vary by jurisdiction. "
            "Consult a licensed tax professional. Especially relevant for "
            "Vietnam-resident creators with international platform earnings."
        )
    if ai_reinforced:
        st.warning(
            "_AI-generated content. The disclaimer above is reinforced — "
            "never act on a Grok extraction without checking the original receipt._"
        )


def page_footer() -> None:
    st.markdown("---")
    st.caption(
        "Built for xAI, X, Grok and the ecosystem community  ·  Apache 2.0  ·  `@JanSol0s`  ·  "
        f"Data: `{DB_PATH}`  ·  Receipts: `{RECEIPTS_DIR}`"
    )


# --- Placeholder data (replaced by data/store.py + api_clients.py in P34) -

@st.cache_data
def placeholder_receipts() -> list[dict]:
    """3 realistic parsed-receipt mocks covering equity / food / SaaS."""
    return [
        {
            "id": "rcp-001",
            "filename": "highlands-2026-04-28.jpg",
            "uploaded_at": "2026-04-28 09:14",
            "vendor":  "Highlands Coffee",
            "tx_date": "2026-04-28",
            "currency": "USD",
            "subtotal":  11.45,
            "tax":        1.05,
            "total":     12.50,
            "category_suggested": "food_drink",
            "confidence": "high",
            "line_items": [
                {"item": "Phin Sữa Đá Latte", "qty": 1, "price":  4.50},
                {"item": "Almond croissant",  "qty": 1, "price":  3.25},
                {"item": "Drip filter coffee","qty": 1, "price":  3.70},
            ],
            "status": "parsed",
        },
        {
            "id": "rcp-002",
            "filename": "vinmart-2026-04-25.jpg",
            "uploaded_at": "2026-04-25 17:42",
            "vendor":  "VinMart",
            "tx_date": "2026-04-25",
            "currency": "USD",
            "subtotal":  60.90,
            "tax":        6.10,
            "total":     67.00,
            "category_suggested": "groceries",
            "confidence": "medium",
            "line_items": [
                {"item": "Rice (5 kg)",       "qty": 1, "price": 12.00},
                {"item": "Eggs (30 ct)",      "qty": 1, "price":  6.40},
                {"item": "Vegetables mix",    "qty": 3, "price":  3.50},
                {"item": "Chicken breast",    "qty": 1, "price": 14.20},
                {"item": "Household supplies","qty": 1, "price": 17.80},
            ],
            "status": "parsed",
        },
        {
            "id": "rcp-003",
            "filename": "adobe-2026-05-02.png",
            "uploaded_at": "2026-05-02 11:00",
            "vendor":  "Adobe Cloud",
            "tx_date": "2026-05-02",
            "currency": "USD",
            "subtotal": 117.27,
            "tax":       11.73,
            "total":    129.00,
            "category_suggested": "subscriptions",
            "confidence": "high",
            "line_items": [
                {"item": "Photography plan (monthly)", "qty": 1, "price": 117.27},
            ],
            "status": "parsed",
        },
    ]


@st.cache_data
def placeholder_validation_runs() -> list[dict]:
    """3 double-vision-pass results with intentional contradictions."""
    return [
        {
            "receipt_id": "rcp-001",
            "vendor":     "Highlands Coffee",
            "delta":      "total $0.05",
            "pass_1":     {"vendor": "Highlands Coffee", "total": 12.50, "tx_date": "2026-04-28"},
            "pass_2":     {"vendor": "Highlands Coffee", "total": 12.45, "tx_date": "2026-04-28"},
            "verdict":    "minor — likely OCR rounding on the cents column",
            "flag":       "warn",
        },
        {
            "receipt_id": "rcp-002",
            "vendor":     "VinMart",
            "delta":      "vendor casing",
            "pass_1":     {"vendor": "Vinmart",  "total": 67.00, "tx_date": "2026-04-25"},
            "pass_2":     {"vendor": "VinMart",  "total": 67.00, "tx_date": "2026-04-25"},
            "verdict":    "cosmetic — vendor name capitalisation differs (downstream normalize on import)",
            "flag":       "info",
        },
        {
            "receipt_id": "rcp-003",
            "vendor":     "Adobe Cloud",
            "delta":      "tx_date 10 days",
            "pass_1":     {"vendor": "Adobe Cloud", "total": 129.00, "tx_date": "2026-05-02"},
            "pass_2":     {"vendor": "Adobe Cloud", "total": 129.00, "tx_date": "2026-05-12"},
            "verdict":    "**material — surface BOTH dates, do NOT silently resolve. Article III.**",
            "flag":       "error",
        },
    ]


@st.cache_data
def placeholder_history() -> pd.DataFrame:
    """8 past parse rows with mixed import statuses."""
    today = date.today()
    rows = [
        # (days_ago, vendor, total, status)
        (0,   "Highlands Coffee", 12.50,  "imported"),
        (0,   "Adobe Cloud",     129.00,  "import_pending"),
        (1,   "VinMart",          67.00,  "imported"),
        (3,   "Streamlit Cloud",  89.00,  "imported"),
        (5,   "Grab",             45.00,  "imported"),
        (7,   "Mystery receipt",   0.00,  "failed_low_confidence"),
        (9,   "Spotify",            8.99, "imported"),
        (12,  "Domain Renewal",   55.00,  "imported"),
    ]
    df = pd.DataFrame(rows, columns=["days_ago", "vendor", "total_usd", "status"])
    df["parsed_on"] = df["days_ago"].apply(lambda d: today - timedelta(days=int(d)))
    return df[["parsed_on", "vendor", "total_usd", "status"]]


# --- Sidebar ---------------------------------------------------------------

with st.sidebar:
    st.title("🧾 Vision Analyzer")
    st.caption("Drag, drop, parse, import.")
    st.markdown("---")
    st.markdown("**Manifest** — `grok-agent.yaml` v2.15  \n**Kind** — `vision-analyzer`")
    st.markdown("**License** — Apache 2.0  \n**Constitution** — v1.0")
    st.markdown("---")
    st.markdown("**Data folder**")
    st.code(str(APPDATA), language="text")
    st.markdown("**Receipts folder**")
    st.code(str(RECEIPTS_DIR), language="text")
    st.markdown("**Companion DB (cross-tool target)**")
    st.code(str(companion_db_path()), language="text")
    st.markdown("---")
    st.caption(
        "Local-first. Privacy-first. `pii_handling: redacted-cloud` "
        "(vision calls leave the box for Grok 4.3; nothing else does)."
    )


# --- Header + tabs ---------------------------------------------------------

st.title("🧾 X Money Vision Analyzer")
st.caption("_Built for xAI, X, Grok and the ecosystem community — Tool #4 of the X Money suite._")

tab_drop, tab_preview, tab_validate, tab_import, tab_history, tab_settings = st.tabs([
    "📥 Drop Files",
    "🔍 Parsed Preview",
    "🔁 Validate",
    "📤 Import to Tool #1",
    "📜 History",
    "⚙️ Settings",
])


# --- Tab 1: Drop Files -----------------------------------------------------

with tab_drop:
    disclaimer_banner()
    st.header("📥 Drop Files")

    uploaded = st.file_uploader(
        "Drag-drop receipts (JPG / PNG / HEIC) or statements (PDF / image)",
        type=["jpg", "jpeg", "png", "heic", "pdf"],
        accept_multiple_files=True,
        help="Files are saved locally under the receipts/ subfolder; nothing is uploaded until you parse + import.",
    )

    st.subheader("Recently dropped (placeholders)")
    receipts = placeholder_receipts()
    drop_table = pd.DataFrame([
        {
            "filename":    r["filename"],
            "uploaded_at": r["uploaded_at"],
            "size":        "~80 KB",
            "status":      r["status"],
        }
        for r in receipts
    ])
    st.dataframe(drop_table, use_container_width=True, hide_index=True)

    cols = st.columns([1, 1, 4])
    cols[0].button(
        "🔍 Parse all",
        disabled=True,
        help="The Grok 4.3 vision client wires up in Slot 4 / P34 (data/api_clients.py).",
    )
    cols[1].button(
        "🗑️ Clear queue",
        disabled=True,
        help="Active in Slot 4 / P34.",
    )
    st.info(
        "_Placeholder list. Real uploads land under_ "
        f"`{RECEIPTS_DIR}` _and trigger `parse_receipt` / `parse_statement` in P34._"
    )
    page_footer()


# --- Tab 2: Parsed Preview -------------------------------------------------

with tab_preview:
    disclaimer_banner(include_tax=True)
    st.header("🔍 Parsed Preview")

    receipts = placeholder_receipts()
    rcp_id = st.selectbox(
        "Receipt", [r["id"] for r in receipts],
        format_func=lambda i: f"{i} — {next(r['vendor'] for r in receipts if r['id'] == i)}",
        index=0, key="preview-rcp",
    )
    r = next(r for r in receipts if r["id"] == rcp_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total",      f"${r['total']:.2f}")
    c2.metric("Subtotal",   f"${r['subtotal']:.2f}")
    c3.metric("Tax",        f"${r['tax']:.2f}")
    c4.metric("Confidence", r["confidence"])

    st.markdown(f"**Vendor**: `{r['vendor']}`  \n"
                f"**Date**: `{r['tx_date']}`  \n"
                f"**Currency**: `{r['currency']}`  \n"
                f"**Suggested category**: `{r['category_suggested']}`")

    st.subheader("Line items (editable)")
    items_df = pd.DataFrame(r["line_items"])
    edited = st.data_editor(
        items_df, num_rows="dynamic", use_container_width=True,
        key=f"preview-items-{rcp_id}",
    )

    st.caption(
        "_Editing is local-only until you confirm the import in Tab 4. "
        "Article IV: every parsed field is a Grok claim, not a fact — "
        "verify against the original receipt before approving._"
    )
    page_footer()


# --- Tab 3: Validate -------------------------------------------------------

with tab_validate:
    disclaimer_banner(ai_reinforced=True)
    st.header("🔁 Validate")
    st.caption(
        "_Second vision pass surfaces disagreements between two extractions. "
        "Article III prohibits silent contradiction-resolution — both readings stay visible._"
    )

    runs = placeholder_validation_runs()
    for run in runs:
        with st.container(border=True):
            head = f"**{run['receipt_id']}** — {run['vendor']}  ·  Δ {run['delta']}"
            if run["flag"] == "error":
                st.error(head)
            elif run["flag"] == "warn":
                st.warning(head)
            else:
                st.info(head)

            cols = st.columns(2)
            cols[0].markdown("**Pass 1**")
            cols[0].json(run["pass_1"], expanded=False)
            cols[1].markdown("**Pass 2**")
            cols[1].json(run["pass_2"], expanded=False)

            st.markdown(f"**Verdict** — {run['verdict']}")
            cb = st.columns([1, 1, 4])
            cb[0].button("Accept Pass 1", key=f"a1-{run['receipt_id']}", disabled=True,
                         help="Wires up in Slot 4 / P34.")
            cb[1].button("Accept Pass 2", key=f"a2-{run['receipt_id']}", disabled=True,
                         help="Wires up in Slot 4 / P34.")

    st.divider()
    st.button(
        "🔁 Re-validate all",
        disabled=True,
        help="The validate_extraction tool ships in Slot 4 / P34.",
    )
    page_footer()


# --- Tab 4: Import to Tool #1 ----------------------------------------------

with tab_import:
    disclaimer_banner(include_tax=True)
    st.header("📤 Import to Tool #1")
    st.caption(
        "_The X Money Companion Dashboard (Tool #1) is the official local store. "
        "This tab is the **only** Constitution-permitted cross-tool write path._"
    )

    receipts = placeholder_receipts()
    approved_df = pd.DataFrame([
        {
            "id":                  r["id"],
            "vendor":              r["vendor"],
            "tx_date":             r["tx_date"],
            "total_usd":           r["total"],
            "category_suggested":  r["category_suggested"],
            "confidence":          r["confidence"],
        }
        for r in receipts
    ])
    st.subheader("Approved for import")
    st.dataframe(approved_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Consent gate (Constitution Article II)")
    with st.container(border=True):
        total = sum(r["total"] for r in receipts)
        target_db = companion_db_path()
        st.markdown(
            f"**Action plan**\n\n"
            f"- Write **{len(receipts)}** receipts (total **${total:,.2f}**) into Tool #1's "
            f"`transactions` table\n"
            f"- Target file: `{target_db}`\n"
            f"- Each row: `source = 'vision'`, `receipt_image_path` set to the local image\n"
            f"- Disclaimer pages V.1 + V.2 prepended on any subsequent export\n"
            f"- Provenance log entry appended to `provenance.log` on **both** tools\n"
            f"- Estimated cost: $0.00 (no API call for the import itself)"
        )
        agree = st.checkbox(
            "I understand this writes into Tool #1's database. (Article II consent gate.)",
            value=False, key="import-consent",
        )
        st.button(
            "✅ Confirm and import",
            disabled=True,
            help="Disabled in the skeleton. The consent-gated write pipeline "
                 "(`data/import_receipts.py`) ships in Slot 4 / P34.",
        )

    st.markdown("---")
    st.markdown(
        "**Constitution rule baked into this manifest:**\n\n"
        "> *\"Tool #4 writes to Tool #1's SQLite via data/import_receipts.py only. "
        "No other cross-tool writes are permitted by this manifest (Article III).\"*"
    )
    page_footer()


# --- Tab 5: History --------------------------------------------------------

with tab_history:
    disclaimer_banner()
    st.header("📜 History")

    df = placeholder_history()
    f1, f2 = st.columns([2, 1])
    statuses = ["all"] + sorted(df["status"].unique().tolist())
    status_filter = f1.selectbox("Status", statuses, index=0, key="hist-status")
    days_filter   = f2.slider("Last N days", min_value=1, max_value=14, value=14, key="hist-days")

    cutoff = date.today() - timedelta(days=int(days_filter))
    filtered = df[df["parsed_on"] >= cutoff]
    if status_filter != "all":
        filtered = filtered[filtered["status"] == status_filter]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)} of {len(df)} parses match the filters.")

    page_footer()


# --- Tab 6: Settings -------------------------------------------------------

with tab_settings:
    disclaimer_banner()
    st.header("⚙️ Settings")

    with st.container(border=True):
        st.subheader("Grok 4.3 vision API")
        st.text_input(
            "XAI_API_KEY", value="", type="password",
            help="Stored locally only. Never written to git or the cloud.",
            disabled=True,
            placeholder="sk-... (active in Slot 4 / P34)",
        )

    with st.container(border=True):
        st.subheader("Privacy")
        st.selectbox(
            "PII redaction policy",
            ["Redact PII before sending to vision API (default — Article VII)",
             "Send the full image (not recommended)"],
            index=0,
            disabled=True,
            help="Active in Slot 4 / P34.",
        )
        st.toggle(
            "Cloud sync (off by default)",
            value=False,
            disabled=True,
            help="Constitution Article VII §2: telemetry / cloud sync is opt-in only.",
        )

    with st.container(border=True):
        st.subheader("Cost limits (read-only — declared in the manifest)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Per session",  "$1.00")
        c2.metric("Per day",      "$5.00")
        c3.metric("API calls/sess.", "100")
        st.caption(
            "_Vision calls are bigger than text — the per-session count is "
            "intentionally lower than Tool #2's 500._"
        )

    page_footer()
