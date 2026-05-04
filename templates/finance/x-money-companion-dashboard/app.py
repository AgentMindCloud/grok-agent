# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""X Money Companion Dashboard — Streamlit skeleton (Recipe A Slot 2 / P20).

The anchor finance tool of the Grok Agent OS suite. This module is the visual
layer; the data layer arrives in Slot 4 / P22 at ``data/store.py`` and the
Grok prompt layer arrives in Slot 3 / P21 under ``prompts/``. Until then this
skeleton renders 6 tabs with realistic placeholder content + the mandatory
Article V disclaimer on every tab.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# --- Local-first storage path (Constitution Article VII) -------------------

def appdata_root() -> Path:
    """Resolve the local-first data folder.

    Production target is Windows 11 + PowerShell, where this resolves to
    ``$env:LOCALAPPDATA\\grok-agent\\x-money-companion-dashboard``. On
    non-Windows runs (Streamlit Cloud, dev containers, CI) we fall back to
    ``~/.local/share/...`` so the skeleton boots cleanly everywhere.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-companion-dashboard"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-money-companion-dashboard"


APPDATA = appdata_root()
DB_PATH = APPDATA / "data.db"


def ensure_appdata() -> None:
    """Create AppData folder and a stub SQLite file on first run.

    Slot 4 / P22 replaces this stub with a full ``data/store.py`` module. The
    skeleton only needs the folder + a meta table so smoke tests pass and the
    user can see where their data will live.
    """
    APPDATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta ("
            " key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("skeleton_version", "0.20.0"),
        )
        conn.commit()


# --- Page config -----------------------------------------------------------

st.set_page_config(
    page_title="X Money Companion Dashboard",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_appdata()


# --- Disclaimer + footer (Constitution Articles V, I.2) --------------------

def disclaimer_banner(*, include_tax: bool = False) -> None:
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


def page_footer() -> None:
    """Render the consistent footer required on every tab."""
    st.markdown("---")
    st.caption(
        "Built to help xAI and Grok win  ·  Apache 2.0  ·  `@JanSol0s`  ·  "
        f"Data: `{DB_PATH}`"
    )


# --- Placeholder data (replaced by data/store.py in P22) -------------------

@st.cache_data
def placeholder_transactions() -> pd.DataFrame:
    """Realistic placeholder transactions for the skeleton render."""
    today = date.today()
    rows = [
        # (days_ago, amount, counterparty, memo, category, source)
        (1,  -89.00,  "Streamlit Cloud", "Pro tier — May",      "subscriptions",  "manual"),
        (1,  -12.50,  "Highlands Coffee","morning latte",       "food_drink",     "vision"),
        (2,  +750.00, "X Payments",      "creator payout #214", "x_payouts",      "api"),
        (3,  -45.00,  "Grab",            "ride to coworking",   "transport",      "manual"),
        (4,  -129.00, "Adobe Cloud",     "Photography plan",    "subscriptions",  "manual"),
        (5,  -22.40,  "GoFood",          "lunch order",         "food_drink",     "vision"),
        (6,  +320.00, "Stripe Payout",   "newsletter sponsor",  "ad_revenue",     "api"),
        (7,  -8.99,   "Spotify",         "monthly",             "subscriptions",  "manual"),
        (8,  -67.00,  "VinMart",         "groceries",           "groceries",      "vision"),
        (10, -1500.00,"Vinhomes Rent",   "May rent",            "housing",        "manual"),
        (12, +210.00, "YouTube",         "ad share",            "ad_revenue",     "api"),
        (14, -34.00,  "Highlands Coffee","working session",     "food_drink",     "vision"),
        (16, -55.00,  "Domain Renewal",  "agentmindcloud.com",  "infrastructure", "manual"),
        (18, +1100.00,"X Payments",      "creator payout #213", "x_payouts",      "api"),
        (20, -15.50,  "Highlands Coffee","afternoon",           "food_drink",     "vision"),
    ]
    df = pd.DataFrame(
        rows,
        columns=["days_ago", "amount", "counterparty", "memo", "category", "source"],
    )
    df["tx_date"] = df["days_ago"].apply(lambda d: today - timedelta(days=int(d)))
    df["currency"] = "USD"
    df = df[["tx_date", "amount", "currency", "counterparty", "memo", "category", "source"]]
    return df.sort_values("tx_date", ascending=False).reset_index(drop=True)


@st.cache_data
def placeholder_alerts() -> list[dict]:
    return [
        {
            "level": "warn",
            "title": "Subscription spend up 18% MoM",
            "body":  "Your monthly subscription footprint is $244 in May vs $207 in April. "
                     "3 active subscriptions overlap (cloud storage). One of them may be redundant.",
            "category": "subscriptions",
        },
        {
            "level": "info",
            "title": "Two transactions over $500 lack receipts",
            "body":  "Vinhomes Rent ($1500) and X Payments outflow ($720) have no attached receipts. "
                     "Add receipts in the Vision Analyzer for an audit-ready ledger.",
            "category": "audit",
        },
        {
            "level": "info",
            "title": "Coffee spend trending +3x this week",
            "body":  "5 coffee transactions in the last 7 days vs your 30-day average of 1.7. "
                     "Heads-up — not a problem, just a pattern.",
            "category": "food_drink",
        },
    ]


PLACEHOLDER_GROK_INSIGHT = (
    "Looking at your last 21 days, your **net cashflow is positive** — strong. "
    "Three drivers stand out:\n\n"
    "1. **X Payments** delivered two creator payouts ($1,100 + $750) — that's the "
    "majority of your inflow. Worth tracking week-over-week to forecast May.\n"
    "2. **Subscriptions** are your largest non-housing outflow category. Adobe Cloud "
    "+ Streamlit Pro overlap with what you already have through other tools — "
    "consider auditing.\n"
    "3. **Vision Analyzer is doing real work**: 6 of 15 transactions came from "
    "receipt scans this period (40%). The Tool #4 → Tool #1 pipeline is paying off.\n\n"
    "_Sources: local SQLite (3 weeks), no external data fetched for this insight._"
)


# --- Sidebar ---------------------------------------------------------------

with st.sidebar:
    st.title("💸 X Money Companion")
    st.caption("Your X Money command center, on Windows.")
    st.markdown("---")
    st.markdown("**Manifest** — `grok-agent.yaml` v2.15  \n**Kind** — `finance-dashboard`")
    st.markdown("**License** — Apache 2.0  \n**Constitution** — v1.0")
    st.markdown("---")
    st.markdown("**Data folder**")
    st.code(str(APPDATA), language="text")
    st.markdown("**Database**")
    st.code(str(DB_PATH), language="text")
    st.markdown("---")
    st.caption(
        "Local-first. Privacy-first. No telemetry. "
        "(Constitution Article VII)"
    )


# --- Header + tabs ---------------------------------------------------------

st.title("💸 X Money Companion Dashboard")
st.caption("_Built to help xAI and Grok win._")

tab_overview, tab_tx, tab_analytics, tab_grok, tab_export, tab_alerts = st.tabs([
    "📊 Overview",
    "💳 Transactions",
    "📈 Analytics",
    "🤖 Grok Insights",
    "📤 Tax Export",
    "🔔 Alerts",
])


# --- Tab 1: Overview -------------------------------------------------------

with tab_overview:
    disclaimer_banner()
    st.header("📊 Overview")

    df = placeholder_transactions()
    inflow  = float(df.loc[df["amount"] > 0, "amount"].sum())
    outflow = float(-df.loc[df["amount"] < 0, "amount"].sum())
    net     = inflow - outflow
    margin  = (net / outflow * 100.0) if outflow > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net cashflow (21d)", f"${net:,.2f}", delta=f"{margin:+.0f}% margin")
    c2.metric("Inflow",  f"${inflow:,.2f}")
    c3.metric("Outflow", f"${outflow:,.2f}")
    c4.metric("Active alerts", str(len(placeholder_alerts())))

    st.subheader("Top counterparties (last 21 days)")
    top_cp = (
        df.assign(abs_amount=df["amount"].abs())
          .groupby("counterparty", as_index=False)["abs_amount"].sum()
          .sort_values("abs_amount", ascending=False)
          .head(5)
    )
    st.dataframe(top_cp, use_container_width=True, hide_index=True)

    st.info(
        "_Placeholder data — the SQLite-backed views ship in Slot 4 / P22 at "
        "`data/store.py`._"
    )
    page_footer()


# --- Tab 2: Transactions ---------------------------------------------------

with tab_tx:
    disclaimer_banner()
    st.header("💳 Transactions")

    df = placeholder_transactions()

    f1, f2, f3 = st.columns([2, 2, 1])
    cats    = ["all"] + sorted(df["category"].unique().tolist())
    sources = ["all"] + sorted(df["source"].unique().tolist())
    cat_filter    = f1.selectbox("Category", cats, index=0)
    source_filter = f2.selectbox("Source",   sources, index=0)
    days_filter   = f3.slider("Last N days", min_value=1, max_value=21, value=21)

    cutoff = date.today() - timedelta(days=int(days_filter))
    filtered = df[df["tx_date"] >= cutoff].copy()
    if cat_filter != "all":
        filtered = filtered[filtered["category"] == cat_filter]
    if source_filter != "all":
        filtered = filtered[filtered["source"] == source_filter]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)} of {len(df)} transactions match the filters.")

    page_footer()


# --- Tab 3: Analytics ------------------------------------------------------

with tab_analytics:
    disclaimer_banner()
    st.header("📈 Analytics")

    df = placeholder_transactions().sort_values("tx_date").reset_index(drop=True)
    df["cumulative"] = df["amount"].cumsum()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Cashflow over time")
        fig = px.line(
            df, x="tx_date", y="cumulative",
            markers=True, title="Cumulative net cashflow (USD)",
        )
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Outflow by category")
        out = df[df["amount"] < 0].copy()
        out["abs_amount"] = out["amount"].abs()
        cat_sum = out.groupby("category", as_index=False)["abs_amount"].sum()
        fig2 = px.pie(
            cat_sum, names="category", values="abs_amount",
            title="Where your money went",
        )
        fig2.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    page_footer()


# --- Tab 4: Grok Insights --------------------------------------------------

with tab_grok:
    disclaimer_banner()
    st.warning(
        "_AI-generated content. The disclaimer above is reinforced — never act on "
        "an insight without your own judgement._"
    )
    st.header("🤖 Grok Insights")

    st.markdown("### Latest insight")
    with st.container(border=True):
        st.markdown(PLACEHOLDER_GROK_INSIGHT)
        st.caption("Generated 2 hours ago · Grok 4.3 · 412 input tokens · $0.0006")

    cols = st.columns([1, 1, 4])
    cols[0].button("👍 Helpful", disabled=True, help="Feedback loop arrives in P21")
    cols[1].button("👎 Off",     disabled=True, help="Feedback loop arrives in P21")

    st.divider()
    st.button(
        "🔄 Generate new insight",
        disabled=True,
        help="The Grok prompts (system + user templates) ship in Slot 3 / P21.",
    )
    st.caption(
        "_Placeholder Grok response. The system prompt + tool schema arrive at "
        "`prompts/system.md` in Slot 3 / P21._"
    )
    page_footer()


# --- Tab 5: Tax Export -----------------------------------------------------

with tab_export:
    disclaimer_banner(include_tax=True)
    st.header("📤 Tax Export")

    today = date.today()
    c1, c2, c3 = st.columns([2, 2, 1])
    start = c1.date_input("Start date", value=today - timedelta(days=90))
    end   = c2.date_input("End date",   value=today)
    fmt   = c3.selectbox("Format", ["csv", "pdf"], index=0)

    df = placeholder_transactions()
    in_range = df[(df["tx_date"] >= start) & (df["tx_date"] <= end)]

    st.subheader("Preview")
    st.dataframe(in_range, use_container_width=True, hide_index=True)
    st.caption(f"{len(in_range)} transactions in selected range.")

    st.divider()
    st.markdown("### Consent gate (Constitution Article II)")
    with st.container(border=True):
        export_path = APPDATA / f"tax_export_{start}_{end}.{fmt}"
        st.markdown(
            f"**Action plan**\n\n"
            f"- Build a `{fmt.upper()}` export of {len(in_range)} transactions "
            f"between **{start}** and **{end}**\n"
            f"- File written to `{export_path}`\n"
            f"- Disclaimer pages V.1 + V.2 prepended\n"
            f"- Provenance row appended to `provenance.log`\n"
            f"- Estimated cost: $0.00 (no API call)"
        )
        st.button(
            "✅ Confirm and build export",
            disabled=True,
            help="The consent-gated build pipeline ships in Slot 4 / P22.",
        )
    page_footer()


# --- Tab 6: Alerts ---------------------------------------------------------

with tab_alerts:
    disclaimer_banner()
    st.header("🔔 Alerts")
    st.caption("_In-app only — alerts are never posted to X without explicit consent._")

    for alert in placeholder_alerts():
        with st.container(border=True):
            icon = "⚠️" if alert["level"] == "warn" else "ℹ️"
            st.markdown(f"{icon} **{alert['title']}**")
            st.write(alert["body"])
            cols = st.columns([1, 1, 4])
            cols[0].button("Dismiss",     key=f"dismiss-{alert['title']}",     disabled=True)
            cols[1].button("Investigate", key=f"investigate-{alert['title']}", disabled=True)
            st.caption(f"Category: `{alert['category']}`")

    page_footer()
