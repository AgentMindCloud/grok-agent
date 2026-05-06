# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""X Smart Cashtag Alpha Engine — Streamlit skeleton (Recipe A Slot 2 / P26).

The narrative-momentum + alpha-signal tool of the Grok Agent OS suite.
This module is the visual layer; the data layer ships in Slot 4 / P28
under ``data/``, the Grok prompt layer in Slot 3 / P27 under ``prompts/``.
Until then this skeleton renders 6 tabs with realistic placeholder
content + the mandatory Article V disclaimer on every tab.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# --- Local-first storage path (Constitution Article VII) -------------------

def appdata_root() -> Path:
    """Resolve the local-first data folder.

    Production target is Windows 11 + PowerShell, where this resolves to
    ``$env:LOCALAPPDATA\\grok-agent\\x-smart-cashtag-alpha-engine``. On
    non-Windows runs (Streamlit Cloud, dev containers, CI) we fall back
    to ``~/.local/share/...`` so the skeleton boots cleanly everywhere.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-smart-cashtag-alpha-engine"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-smart-cashtag-alpha-engine"


APPDATA = appdata_root()
DB_PATH = APPDATA / "data.db"


def ensure_appdata() -> None:
    """Create AppData folder + a stub SQLite file on first run.

    Slot 4 / P28 replaces this stub with a full ``data/store.py`` module.
    """
    APPDATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta ("
            " key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("skeleton_version", "0.26.0"),
        )
        conn.commit()


# --- Page config -----------------------------------------------------------

st.set_page_config(
    page_title="X Smart Cashtag Alpha Engine",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_appdata()


# --- Disclaimer + footer (Constitution Articles V, I.2) --------------------

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
            "never act on a Grok signal without your own judgement and a primary source._"
        )


def page_footer() -> None:
    """Render the consistent footer on every tab."""
    st.markdown("---")
    st.caption(
        "Built for xAI, X, Grok and the ecosystem community  ·  Apache 2.0  ·  `@JanSol0s`  ·  "
        f"Data: `{DB_PATH}`"
    )


# --- Placeholder data (replaced by data/store.py + api_clients.py in P28) -

@st.cache_data
def placeholder_watchlist() -> pd.DataFrame:
    """8 realistic cashtags spanning equities + crypto."""
    rows = [
        # cashtag,  name,                    asset_class, price,    change_pct, volume
        ("$XAI",   "xAI Corp.",              "equity",    8.42,     +12.10,    8_240_000),
        ("$X",     "X Corp.",                "equity",    150.30,   -2.10,     12_400_000),
        ("$TSLA",  "Tesla Inc.",             "equity",    245.18,   +1.82,     54_300_000),
        ("$NVDA",  "NVIDIA Corp.",           "equity",    582.04,   +3.21,     78_900_000),
        ("$SPOT",  "Spotify Technology",     "equity",    310.65,   +0.55,     1_900_000),
        ("$BABA",  "Alibaba Group",          "equity",    85.10,    -1.18,     14_200_000),
        ("$BTC",   "Bitcoin",                "crypto",    67_400.00, -0.84,    25_300_000_000),
        ("$ETH",   "Ethereum",               "crypto",    3_412.55,  +2.07,    14_100_000_000),
    ]
    df = pd.DataFrame(
        rows,
        columns=["cashtag", "name", "asset_class", "price", "change_pct", "volume_24h"],
    )
    return df


@st.cache_data
def synthetic_price_series(cashtag: str, days: int = 30, seed: int = 0) -> pd.DataFrame:
    """Reproducible random-walk close prices for one cashtag over `days`."""
    rng = random.Random(hash(cashtag) ^ seed)
    wl = placeholder_watchlist().set_index("cashtag")
    if cashtag not in wl.index:
        start_price = 100.0
    else:
        start_price = float(wl.loc[cashtag, "price"]) * 0.92  # start 8% lower so the line trends up
    today = date.today()
    rows = []
    p = start_price
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        # Daily move scaled to realistic ranges per asset class
        scale = 0.04 if cashtag.startswith("$BTC") or cashtag.startswith("$ETH") else 0.02
        delta = rng.gauss(0.003, scale)
        p = max(0.01, p * (1.0 + delta))
        rows.append({"date": d, "close": round(p, 4)})
    return pd.DataFrame(rows)


@st.cache_data
def placeholder_alpha_reports() -> list[dict]:
    """3 sample alpha-report cards with the Article-IV provenance fields baked in."""
    return [
        {
            "cashtag":    "$XAI",
            "generated":  "2 hours ago",
            "model":      "grok-4.3",
            "tokens_in":  612, "tokens_out": 280, "cost_usd": 0.0011,
            "headline":   "Narrative momentum strong; *one* unresolved valuation contradiction.",
            "body":
                "**$XAI** mentions on X are up **+18% over 24h** with 78% positive sentiment. "
                "The narrative is anchored on a fresh funding round.\n\n"
                "1. **TechCrunch** reports **$50B valuation** (12:14 UTC).\n"
                "2. **Financial Times** reports **$40B valuation** (12:08 UTC).\n"
                "3. yfinance shows after-hours trading flat — the market is not yet pricing the news.\n\n"
                "⚠️ **Contradiction flagged**: TC vs FT valuation disagree by 25%. "
                "Wait for a primary source (xAI press release) before sizing a position.",
            "confidence": "medium",
            "sources":    ["x_search via grok-4.3", "yfinance", "newsapi"],
        },
        {
            "cashtag":    "$NVDA",
            "generated":  "5 hours ago",
            "model":      "grok-4.3",
            "tokens_in":  548, "tokens_out": 240, "cost_usd": 0.0009,
            "headline":   "Earnings beat priced in; positioning crowded.",
            "body":
                "**$NVDA** posted Q1 EPS of $5.20 vs $4.85 consensus — a clean beat. "
                "After-hours bid is **+5%**, but sell-side estimates haven't refreshed yet.\n\n"
                "1. **NewsAPI** shows 14 same-day headlines, all positive.\n"
                "2. **x_search** shows long/short ratio at 1.67 — already crowded long.\n"
                "3. Volatility surface flat — options aren't pricing surprise.\n\n"
                "Crowded long + priced-in beat = low convexity. Pass unless you have a sharper edge.",
            "confidence": "low",
            "sources":    ["x_search via grok-4.3", "yfinance", "newsapi"],
        },
        {
            "cashtag":    "$BTC",
            "generated":  "1 day ago",
            "model":      "grok-4.3",
            "tokens_in":  720, "tokens_out": 310, "cost_usd": 0.0014,
            "headline":   "ETF flows neutral; on-chain mildly bearish.",
            "body":
                "Spot **BTC ETF flows** are neutral over the last 5 sessions (mean ≈ $12M/day net).\n\n"
                "1. **CoinGecko** spot price flat over the same window.\n"
                "2. **x_search** shows long/short ratio at 0.94 — mild bearish lean.\n"
                "3. NewsAPI surfaces no fresh catalysts; macro print on Friday is the next event.\n\n"
                "Multi-source agreement = **higher confidence**. Sit on hands, watch the print.",
            "confidence": "high",
            "sources":    ["x_search via grok-4.3", "coingecko", "newsapi"],
        },
    ]


@st.cache_data
def placeholder_trending() -> pd.DataFrame:
    """Top 10 trending cashtags — STUB until P28 wires real x_search via Grok 4.3."""
    rows = [
        ("$XAI",   2_150,  0.78, +18.4, "funding round"),
        ("$NVDA",  8_400,  0.62,  +5.1, "earnings beat"),
        ("$BTC",  12_500,  0.51,  -0.8, "ETF flows neutral"),
        ("$TSLA",  6_300,  0.44,  +1.8, "FSD v13 rumors"),
        ("$ETH",   4_900,  0.59,  +2.1, "Pectra upgrade"),
        ("$SPOT",  1_120,  0.66,  +0.5, "podcast deal"),
        ("$X",     3_700,  0.41,  -2.1, "ad-load reset"),
        ("$BABA",    980,  0.39,  -1.2, "Hong Kong session"),
        ("$AAPL",  5_200,  0.55,  +0.9, "vision pro lite leak"),
        ("$META",  3_300,  0.60,  +1.4, "AI assistant launch"),
    ]
    return pd.DataFrame(
        rows,
        columns=["cashtag", "mentions_24h", "sentiment", "momentum_pct", "narrative"],
    )


# --- Sidebar ---------------------------------------------------------------

with st.sidebar:
    st.title("🔭 Smart Cashtag Alpha")
    st.caption("Cashtag-aware market intelligence for X.")
    st.markdown("---")
    st.markdown("**Manifest** — `grok-agent.yaml` v2.15  \n**Kind** — `alpha-engine`")
    st.markdown("**License** — Apache 2.0  \n**Constitution** — v1.0")
    st.markdown("---")
    st.markdown("**Data folder**")
    st.code(str(APPDATA), language="text")
    st.markdown("**Database**")
    st.code(str(DB_PATH), language="text")
    st.markdown("---")
    st.caption(
        "Local-first. Privacy-first. No telemetry. Watches but never posts. "
        "(Constitution Articles II + VII)"
    )


# --- Header + tabs ---------------------------------------------------------

st.title("🔭 X Smart Cashtag Alpha Engine")
st.caption("_Built for xAI, X, Grok and the ecosystem community. ❤️_")

tab_overview, tab_watch, tab_charts, tab_alpha, tab_sim, tab_trend = st.tabs([
    "📊 Overview",
    "🔭 Watchlist",
    "📈 Charts",
    "🤖 Alpha Reports",
    "🎯 Portfolio Simulator",
    "🌊 Trending",
])


# --- Tab 1: Overview -------------------------------------------------------

with tab_overview:
    disclaimer_banner()
    st.header("📊 Overview")

    wl = placeholder_watchlist()
    movers = wl.assign(abs_change=wl["change_pct"].abs()) \
               .sort_values("abs_change", ascending=False).head(3)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Watchlist size", str(len(wl)))
    c2.metric("Active alerts", "2")
    c3.metric(
        "Top mover",
        movers.iloc[0]["cashtag"],
        delta=f"{movers.iloc[0]['change_pct']:+.2f}%",
    )
    c4.metric("Reports today", str(len(placeholder_alpha_reports())))

    st.subheader("Top 3 movers (intraday)")
    st.dataframe(
        movers[["cashtag", "name", "change_pct", "price", "asset_class"]],
        use_container_width=True, hide_index=True,
    )

    st.info(
        "_Placeholder data — the SQLite-backed views ship in Slot 4 / P28 at "
        "`data/store.py`._"
    )
    page_footer()


# --- Tab 2: Watchlist ------------------------------------------------------

with tab_watch:
    disclaimer_banner()
    st.header("🔭 Watchlist")

    wl = placeholder_watchlist()
    cls_filter = st.radio(
        "Asset class", ["all", "equity", "crypto"], horizontal=True, index=0
    )
    filtered = wl if cls_filter == "all" else wl[wl["asset_class"] == cls_filter]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)} of {len(wl)} cashtags shown.")

    a1, a2 = st.columns([3, 1])
    a1.text_input("Add cashtag (e.g. $AAPL)", placeholder="$AAPL", disabled=True)
    a2.button(
        "Add to watchlist",
        disabled=True,
        help="The track_cashtag tool wires up in Slot 4 / P28.",
    )

    page_footer()


# --- Tab 3: Charts ---------------------------------------------------------

with tab_charts:
    disclaimer_banner()
    st.header("📈 Charts")

    wl = placeholder_watchlist()
    cashtag = st.selectbox(
        "Cashtag", wl["cashtag"].tolist(), index=0, key="chart-cashtag"
    )

    series = synthetic_price_series(cashtag, days=30)
    benchmark = synthetic_price_series("$SPY", days=30, seed=1)
    benchmark = benchmark.rename(columns={"close": "benchmark_close"})

    c1, c2 = st.columns(2)

    with c1:
        st.subheader(f"{cashtag} close (30 days)")
        fig = px.line(series, x="date", y="close", markers=True)
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader(f"{cashtag} vs $SPY (relative strength)")
        # Normalize each series to 100 at series start so they compare visually.
        s = series.copy()
        s["norm"] = s["close"] / s["close"].iloc[0] * 100
        b = benchmark.copy()
        b["norm"] = b["benchmark_close"] / b["benchmark_close"].iloc[0] * 100
        rs = pd.DataFrame({
            "date": s["date"],
            cashtag: s["norm"].values,
            "$SPY": b["norm"].values,
        })
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=rs["date"], y=rs[cashtag], mode="lines+markers", name=cashtag))
        fig2.add_trace(go.Scatter(x=rs["date"], y=rs["$SPY"],   mode="lines+markers", name="$SPY"))
        fig2.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    page_footer()


# --- Tab 4: Alpha Reports --------------------------------------------------

with tab_alpha:
    disclaimer_banner(ai_reinforced=True)
    st.header("🤖 Alpha Reports")

    reports = placeholder_alpha_reports()
    for r in reports:
        with st.container(border=True):
            cols = st.columns([3, 1])
            cols[0].markdown(f"### {r['cashtag']} — {r['headline']}")
            cols[1].markdown(f"**Confidence**  \n`{r['confidence']}`")
            st.markdown(r["body"])
            st.caption(
                f"Generated {r['generated']} · {r['model']} · "
                f"{r['tokens_in']} in / {r['tokens_out']} out · ${r['cost_usd']:.4f}  ·  "
                f"sources: {', '.join(r['sources'])}"
            )

    st.divider()
    st.button(
        "🔄 Generate new alpha report",
        disabled=True,
        help="The Grok prompts (system + user templates) ship in Slot 3 / P27; the "
             "tool implementation ships in Slot 4 / P28.",
    )
    st.caption(
        "_Placeholder Grok responses. Each card carries its sources + token cost so "
        "Article IV (Provenance & Truth) is enforceable end-to-end._"
    )
    page_footer()


# --- Tab 5: Portfolio Simulator -------------------------------------------

with tab_sim:
    disclaimer_banner(include_tax=True)
    st.header("🎯 Portfolio Simulator")

    today = date.today()
    c1, c2 = st.columns([2, 2])
    start = c1.date_input("Start date", value=today - timedelta(days=30))
    end   = c2.date_input("End date",   value=today)

    st.subheader("Hypothetical positions")
    default_positions = pd.DataFrame([
        {"cashtag": "$XAI",  "qty": 100, "entry_price": 7.50},
        {"cashtag": "$NVDA", "qty":  10, "entry_price": 562.00},
        {"cashtag": "$BTC",  "qty": 0.5, "entry_price": 64_500.0},
    ])
    edited = st.data_editor(
        default_positions, num_rows="dynamic", use_container_width=True, key="sim-positions"
    )

    # Mock simulated P&L over the date window
    days = max(1, (end - start).days)
    rng = random.Random(42)
    p_curve = []
    starting = sum(row["qty"] * row["entry_price"] for _, row in edited.iterrows() if row["qty"] and row["entry_price"])
    if starting > 0:
        v = starting
        for i in range(days + 1):
            v *= (1.0 + rng.gauss(0.0008, 0.012))
            p_curve.append({"date": start + timedelta(days=i), "value": round(v, 2)})
        sim_df = pd.DataFrame(p_curve)
        ending = float(sim_df["value"].iloc[-1])
        pnl_abs = ending - starting
        pnl_pct = (pnl_abs / starting) * 100.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Starting value", f"${starting:,.2f}")
        m2.metric("Ending value",   f"${ending:,.2f}")
        m3.metric("P&L",            f"${pnl_abs:,.2f}", delta=f"{pnl_pct:+.2f}%")

        fig = px.line(sim_df, x="date", y="value", markers=True, title="Hypothetical portfolio value")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Enter at least one position with `qty` and `entry_price` to run the simulation.")

    st.button(
        "▶️ Run simulation",
        disabled=True,
        help="The simulate_portfolio tool wires up in Slot 4 / P28.",
    )

    page_footer()


# --- Tab 6: Trending -------------------------------------------------------

with tab_trend:
    disclaimer_banner()
    st.header("🌊 Trending")
    st.caption(
        "Top cashtags trending on X right now. Data source: `x_search` via "
        "Grok 4.3 tool-calling (real wiring lands in Slot 4 / P28). "
        "Until then this tab shows clearly-labeled stub data."
    )

    trend = placeholder_trending()
    fig = px.scatter(
        trend, x="mentions_24h", y="momentum_pct",
        size="mentions_24h", color="sentiment",
        hover_name="cashtag",
        hover_data=["narrative"],
        title="Trend space: mentions × momentum, color = sentiment",
        height=380,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 10 (last 24h)")
    st.dataframe(trend, use_container_width=True, hide_index=True)
    st.warning(
        "_Stub data — `x_search` via Grok 4.3 wires up in Slot 4 / P28. "
        "Until then the rows above are illustrative only._"
    )

    page_footer()
