# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""X Creator Payout Optimizer — Streamlit skeleton (Recipe A Slot 2 / P38).

The forecaster + content optimizer + tax estimator of the Grok Agent OS
suite. This module is the visual layer; the data layer (with cross-tool
readers for Tool #1 and Tool #4) ships in Slot 4 / P40 under ``data/``.
The Grok prompt layer ships in Slot 3 / P39 under ``prompts/``. Until
then this skeleton renders 6 tabs with realistic placeholder content +
the mandatory Article V disclaimer on every tab (V.2 stacked on
Earnings Forecast, Tax Estimator, and Content ROI per the P37 README).

The sidebar uses a real ``cross_tool_status()`` helper that queries
Tool #1's and Tool #4's SQLite files directly (read-only) so the
"Tool #N installed: ✓ / ✗" indicator reflects actual filesystem state,
not a mock — graceful degradation if either sibling is absent.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# --- Local-first storage path (Constitution Article VII) -------------------

def appdata_root() -> Path:
    """Resolve this tool's local-first data folder."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-creator-payout-optimizer"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-creator-payout-optimizer"


def companion_db_path() -> Path:
    """Tool #1's SQLite — read-only cross-tool source for revenue rows."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-companion-dashboard" / "data.db"
    return (
        Path.home() / ".local" / "share"
        / "grok-agent" / "x-money-companion-dashboard" / "data.db"
    )


def vision_db_path() -> Path:
    """Tool #4's SQLite — read-only cross-tool source for receipt cost rows."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-vision-analyzer" / "data.db"
    return (
        Path.home() / ".local" / "share"
        / "grok-agent" / "x-money-vision-analyzer" / "data.db"
    )


APPDATA = appdata_root()
DB_PATH = APPDATA / "data.db"


def ensure_appdata() -> None:
    """Create AppData folder + SQLite stub on first run."""
    APPDATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta ("
            " key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("skeleton_version", "0.38.0"),
        )
        conn.commit()


def cross_tool_status() -> dict:
    """Check which sibling tools are installed and how much data they have.

    Returns ``{"companion": {installed, transaction_count, path},
              "vision":    {installed, receipt_count,     path}}``
    — read-only, never modifies sibling state. Empty / missing siblings
    return ``installed=False`` so the UI can render graceful-degradation
    messages.
    """
    status = {
        "companion": {"installed": False, "transaction_count": 0,
                      "path": str(companion_db_path())},
        "vision":    {"installed": False, "receipt_count":     0,
                      "path": str(vision_db_path())},
    }
    if companion_db_path().exists():
        status["companion"]["installed"] = True
        try:
            with sqlite3.connect(str(companion_db_path())) as c:
                row = c.execute("SELECT COUNT(*) FROM transactions").fetchone()
                status["companion"]["transaction_count"] = int(row[0]) if row else 0
        except sqlite3.Error:
            pass
    if vision_db_path().exists():
        status["vision"]["installed"] = True
        try:
            with sqlite3.connect(str(vision_db_path())) as c:
                row = c.execute("SELECT COUNT(*) FROM receipts").fetchone()
                status["vision"]["receipt_count"] = int(row[0]) if row else 0
        except sqlite3.Error:
            pass
    return status


# --- Page config -----------------------------------------------------------

st.set_page_config(
    page_title="X Creator Payout Optimizer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_appdata()


# --- Disclaimer + footer ---------------------------------------------------

def disclaimer_banner(*, include_tax: bool = False, ai_reinforced: bool = False) -> None:
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
            "_AI-generated forecast / suggestion. Reinforced — never act on "
            "a Grok output without your own judgement and a primary source._"
        )


def page_footer() -> None:
    st.markdown("---")
    st.caption(
        "Built to help xAI and Grok win  ·  Apache 2.0  ·  `@JanSol0s`  ·  "
        f"Data: `{DB_PATH}`"
    )


# --- Placeholder data (replaced by data/store.py + data/companion_reader.py +
#                      data/vision_reader.py in Slot 4 / P40) -------------

@st.cache_data
def placeholder_earnings_history(days: int = 90) -> pd.DataFrame:
    """90-day historical earnings curve with weekly seasonality."""
    today = date.today()
    rows = []
    base = 60.0
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        # Seasonality: weekend posts pay slightly less; mid-week peaks
        wk = d.weekday()
        season = 1.20 if 1 <= wk <= 3 else (0.85 if wk >= 5 else 1.00)
        # Light upward trend
        trend = 1.0 + (i / days) * 0.30
        rows.append({"date": d, "earnings": round(base * season * trend, 2)})
    return pd.DataFrame(rows)


@st.cache_data
def placeholder_forecast() -> dict:
    """30/60/90-day forecast band + headline drivers."""
    return {
        "horizons": [
            {"label": "30 days", "point": 3200.00, "low": 2800.00, "high": 3600.00},
            {"label": "60 days", "point": 6500.00, "low": 5800.00, "high": 7200.00},
            {"label": "90 days", "point": 9800.00, "low": 8800.00, "high": 10800.00},
        ],
        "drivers": [
            ("X Payments creator payouts", 0.45),
            ("Ad revenue",                 0.30),
            ("Subscription tips",          0.15),
            ("Other",                      0.10),
        ],
        "confidence":    "medium",
        "data_window":   "last 90 days, local Tool #1 transactions",
        "model":         "grok-4.3 (stub)",
    }


@st.cache_data
def placeholder_content_angles() -> list[dict]:
    """5 angle suggestions for a sample topic."""
    return [
        {
            "angle":        "AI tools that cut creator editing time by 50%",
            "format":       "thread (8-10 posts)",
            "predicted_engagement": 8.2,
            "predicted_revenue_usd": 240.0,
            "confidence":   "high",
            "rationale":    "Past 'AI tool X cuts time' threads averaged 7.8 engagement; +50% specificity raises confidence",
        },
        {
            "angle":        "I tested 5 Grok prompts for content ideation",
            "format":       "video (60s)",
            "predicted_engagement": 7.4,
            "predicted_revenue_usd": 180.0,
            "confidence":   "medium",
            "rationale":    "Format match: video Grok posts pay 2.3x text; topic specificity is fresh",
        },
        {
            "angle":        "The 3 X Money creator payout patterns I noticed in May",
            "format":       "thread (5-7 posts)",
            "predicted_engagement": 7.1,
            "predicted_revenue_usd": 165.0,
            "confidence":   "medium",
            "rationale":    "First-person pattern threads consistently top engagement on this account",
        },
        {
            "angle":        "Why I cancelled half my creator subscriptions last week",
            "format":       "thread (3-5 posts)",
            "predicted_engagement": 6.4,
            "predicted_revenue_usd": 110.0,
            "confidence":   "low",
            "rationale":    "Audience signal mixed; controversy potential but conversion uncertain",
        },
        {
            "angle":        "Building agents on the Grok Agent OS — week 1 lessons",
            "format":       "long-form post + video (90s)",
            "predicted_engagement": 8.7,
            "predicted_revenue_usd": 295.0,
            "confidence":   "high",
            "rationale":    "Niche fit + ecosystem-aligned topic; long-form posts pay 3x for this account",
        },
    ]


@st.cache_data
def placeholder_x_metrics() -> dict:
    """X metrics dashboard data."""
    today = date.today()
    follower_curve = []
    f = 4_820
    for i in range(30):
        d = today - timedelta(days=29 - i)
        f += 12 + (i % 4) * 6
        follower_curve.append({"date": d, "followers": f})
    return {
        "reach_24h":          12_400,
        "reach_7d":           78_300,
        "reach_30d":         298_600,
        "engagement_rate_30d":  4.21,    # %
        "follower_growth_30d":   612,
        "payout_this_month":  2_180.00,
        "follower_curve":     pd.DataFrame(follower_curve),
        "top_posts": pd.DataFrame([
            ("2026-04-21", "AI tools thread",            18_400, 1_240, 162.10),
            ("2026-04-28", "Grok 4.3 vision walkthrough", 14_200,   880, 124.50),
            ("2026-05-02", "Cashtag alpha example",       12_900,   720, 108.20),
            ("2026-05-04", "Receipt parser demo",         11_500,   640,  95.40),
            ("2026-04-15", "Vietnam creator tax tips",    10_800,   590,  82.30),
        ], columns=["post_date", "title", "reach", "engagement", "payout_usd"]),
    }


@st.cache_data
def placeholder_content_roi() -> pd.DataFrame:
    """Per-topic ROI: revenue (Tool #1) × cost (Tool #4)."""
    rows = [
        # topic,                             revenue, cost,   notes
        ("Grok Agent OS series",              412.00,  89.00, "Streamlit Pro + domain"),
        ("AI tools threads",                  280.00,  45.00, "GoFood lunch only"),
        ("Cashtag alpha walkthroughs",        198.00, 117.00, "Adobe + designer"),
        ("Receipt parser demo",               112.00, 134.00, "Adobe + props (loss)"),
        ("Vietnam creator tax content",        82.00,  12.00, "Coffee only"),
    ]
    df = pd.DataFrame(rows, columns=["topic", "revenue_usd", "cost_usd", "notes"])
    df["net_usd"] = df["revenue_usd"] - df["cost_usd"]
    df["roi_pct"] = ((df["net_usd"] / df["cost_usd"]) * 100.0).round(1)
    return df


# --- Sidebar with REAL cross-tool status -----------------------------------

with st.sidebar:
    st.title("📈 Payout Optimizer")
    st.caption("Forecast earnings. Optimize content. Estimate taxes.")
    st.markdown("---")
    st.markdown("**Manifest** — `grok-agent.yaml` v2.15  \n**Kind** — `creator-payout-optimizer`")
    st.markdown("**License** — Apache 2.0  \n**Constitution** — v1.0")
    st.markdown("---")

    status = cross_tool_status()

    st.markdown("**Cross-tool sources**")
    if status["companion"]["installed"]:
        st.success(
            f"✓ Tool #1 (Companion Dashboard): "
            f"**{status['companion']['transaction_count']}** transactions"
        )
    else:
        st.info(
            "✗ Tool #1 not installed — revenue side will be blank "
            "(graceful degradation; install x-money-companion-dashboard to fix)."
        )
    if status["vision"]["installed"]:
        st.success(
            f"✓ Tool #4 (Vision Analyzer): "
            f"**{status['vision']['receipt_count']}** receipts"
        )
    else:
        st.info(
            "✗ Tool #4 not installed — cost side will be blank "
            "(graceful degradation; install x-money-vision-analyzer to fix)."
        )

    st.markdown("---")
    st.markdown("**Data folder**")
    st.code(str(APPDATA), language="text")
    st.caption(
        "Local-first. Privacy-first. Read-only on Tool #1 + Tool #4. "
        "(Constitution Articles III + VII)"
    )


# --- Header + tabs ---------------------------------------------------------

st.title("📈 X Creator Payout Optimizer")
st.caption("_Built to help xAI and Grok win — Tool #3, the last of the X Money suite._")

tab_forecast, tab_optimize, tab_tax, tab_metrics, tab_roi, tab_settings = st.tabs([
    "📈 Earnings Forecast",
    "✍️ Content Optimizer",
    "🧮 Tax Estimator",
    "📊 X Metrics",
    "💰 Content ROI",
    "⚙️ Settings",
])


# --- Tab 1: Earnings Forecast ---------------------------------------------

with tab_forecast:
    disclaimer_banner(include_tax=True, ai_reinforced=True)
    st.header("📈 Earnings Forecast")

    fc = placeholder_forecast()
    cols = st.columns(3)
    for col, h in zip(cols, fc["horizons"]):
        col.metric(
            f"Next {h['label']}",
            f"${h['point']:,.0f}",
            delta=f"low ${h['low']:,.0f} – high ${h['high']:,.0f}",
        )

    hist = placeholder_earnings_history(90)
    today = date.today()
    fc_x = [today + timedelta(days=i) for i in range(91)]
    fc_y = [fc["horizons"][0]["point"] / 30.0 * (1 + i * 0.02) for i in range(91)]
    fc_low  = [v * 0.85 for v in fc_y]
    fc_high = [v * 1.15 for v in fc_y]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist["date"], y=hist["earnings"],
        mode="lines", name="Historical (Tool #1)",
        line=dict(color="#FF6B00"),
    ))
    fig.add_trace(go.Scatter(
        x=fc_x, y=fc_y, mode="lines", name="Forecast (point)",
        line=dict(color="#F5F5DC", dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=fc_x + fc_x[::-1], y=fc_high + fc_low[::-1],
        fill="toself", fillcolor="rgba(255,107,0,0.15)",
        line=dict(color="rgba(0,0,0,0)"), name="Forecast band",
    ))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10),
                      title="Daily earnings — last 90 days + 90-day forecast")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Headline drivers")
    drv = pd.DataFrame(fc["drivers"], columns=["driver", "share_of_forecast"])
    drv["share_of_forecast"] = (drv["share_of_forecast"] * 100).round(1)
    st.dataframe(drv, use_container_width=True, hide_index=True)
    st.caption(
        f"_Forecast confidence: **{fc['confidence']}** · model: `{fc['model']}` · "
        f"data window: {fc['data_window']}._"
    )

    page_footer()


# --- Tab 2: Content Optimizer ---------------------------------------------

with tab_optimize:
    disclaimer_banner(ai_reinforced=True)
    st.header("✍️ Content Optimizer")

    topic = st.text_input(
        "Topic to optimize",
        value="AI tools for creators",
        help="Live optimize wires up in Slot 4 / P40.",
    )

    angles = placeholder_content_angles()
    for a in angles:
        with st.container(border=True):
            cols = st.columns([5, 1])
            cols[0].markdown(f"### {a['angle']}")
            cols[1].markdown(f"**{a['confidence']}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Format",                a["format"])
            m2.metric("Predicted engagement",  f"{a['predicted_engagement']:.1f}/10")
            m3.metric("Predicted revenue",     f"${a['predicted_revenue_usd']:,.0f}")
            st.caption(f"_Rationale: {a['rationale']}_")

    st.divider()
    st.button(
        "🔄 Generate angles for new topic",
        disabled=True,
        help="The optimize_content_topic tool ships in Slot 4 / P40.",
    )
    page_footer()


# --- Tab 3: Tax Estimator -------------------------------------------------

with tab_tax:
    disclaimer_banner(include_tax=True)
    st.header("🧮 Tax Estimator")

    today = date.today()
    c1, c2, c3 = st.columns([2, 2, 2])
    start = c1.date_input("Start date",    value=today - timedelta(days=90))
    end   = c2.date_input("End date",      value=today)
    juris = c3.selectbox(
        "Jurisdiction",
        ["Vietnam (resident creator, international platform earnings)",
         "United States (1099 / Schedule C)",
         "European Union (varies by country)",
         "Other"],
        index=0,
    )

    # Mock tax computation: 17% rate for VN baseline, 24% for US, 30% for EU avg
    rate = 0.17 if juris.startswith("Vietnam") else \
           0.24 if juris.startswith("United States") else \
           0.30 if juris.startswith("European") else 0.20
    gross = 9_800.00
    tax   = round(gross * rate, 2)
    net   = round(gross - tax,  2)

    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated gross",   f"${gross:,.2f}")
    m2.metric("Estimated tax",     f"${tax:,.2f}", delta=f"~{rate*100:.0f}% rate")
    m3.metric("Estimated net",     f"${net:,.2f}")

    st.caption(
        "_Rate is a coarse jurisdictional baseline — NOT a substitute for a "
        "licensed professional's calculation. The V.2 banner above is mandatory._"
    )

    st.divider()
    st.markdown("### Consent gate (Constitution Article II)")
    with st.container(border=True):
        st.markdown(
            f"**Action plan**\n\n"
            f"- Build a tax estimate report covering **{start} → {end}** "
            f"in jurisdiction **{juris.split(' (')[0]}**\n"
            f"- File written to `{APPDATA / f'tax_estimate_{start}_{end}.csv'}`\n"
            f"- V.1 + V.2 disclaimer pages prepended\n"
            f"- Provenance log entry appended to `provenance.log`\n"
            f"- Estimated cost: $0.00 (no API call)"
        )
        st.checkbox(
            "I understand this is an estimate and not tax advice. (Article II + V.2.)",
            value=False, key="tax-consent",
        )
        st.button(
            "✅ Confirm and build estimate",
            disabled=True,
            help="The consent-gated build pipeline ships in Slot 4 / P40.",
        )

    page_footer()


# --- Tab 4: X Metrics -----------------------------------------------------

with tab_metrics:
    disclaimer_banner()
    st.header("📊 X Metrics")

    m = placeholder_x_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reach (24h)",           f"{m['reach_24h']:,}")
    c2.metric("Reach (7d)",            f"{m['reach_7d']:,}")
    c3.metric("Engagement rate (30d)", f"{m['engagement_rate_30d']:.2f}%")
    c4.metric("Payout this month",     f"${m['payout_this_month']:,.2f}",
              delta=f"+{m['follower_growth_30d']} followers (30d)")

    st.subheader("Follower growth (30 days)")
    fig = px.line(m["follower_curve"], x="date", y="followers",
                  markers=True, title=None)
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 5 posts by engagement (last 30 days)")
    st.dataframe(m["top_posts"], use_container_width=True, hide_index=True)
    st.caption(
        "_Data source: `fetch_x_metrics` via `x_search` (stub). "
        "Real wiring lands in Slot 4 / P40._"
    )

    page_footer()


# --- Tab 5: Content ROI ---------------------------------------------------

with tab_roi:
    disclaimer_banner(include_tax=True)
    st.header("💰 Content ROI")

    s = cross_tool_status()
    if not (s["companion"]["installed"] and s["vision"]["installed"]):
        st.info(
            "_Cross-tool sources missing — Content ROI joins **Tool #1 revenue rows** "
            "with **Tool #4 receipt cost rows**, so the chart below uses placeholder "
            "data until both siblings are installed. Sidebar shows current status._"
        )
    else:
        st.success(
            f"_Live read-only join: {s['companion']['transaction_count']} Tool #1 "
            f"transactions × {s['vision']['receipt_count']} Tool #4 receipts available "
            f"to the data layer once Slot 4 / P40 wires it up._"
        )

    df = placeholder_content_roi()
    st.dataframe(df, use_container_width=True, hide_index=True)

    fig = px.bar(
        df.sort_values("net_usd"), x="topic", y="net_usd",
        title="Net P&L by topic (revenue − cost)",
        color="net_usd",
        color_continuous_scale=["#FF4444", "#FFCC44", "#44CC44"],
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10),
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "_Receipt-parser demo's negative ROI is real — costs ran high (Adobe + props) "
        "for under-performing reach. The data layer in P40 will compute this from your "
        "actual Tool #1 + Tool #4 rows._"
    )
    page_footer()


# --- Tab 6: Settings ------------------------------------------------------

with tab_settings:
    disclaimer_banner()
    st.header("⚙️ Settings")

    with st.container(border=True):
        st.subheader("API keys")
        st.text_input(
            "XAI_API_KEY", value="", type="password",
            disabled=True,
            placeholder="sk-... (active in Slot 4 / P40)",
            help="Stored locally only. Never committed to git or sent to the cloud.",
        )
        st.text_input(
            "NEWSAPI_KEY", value="", type="password",
            disabled=True,
            placeholder="newsapi.org key (free tier 100/day)",
        )

    with st.container(border=True):
        st.subheader("Default jurisdiction")
        st.selectbox(
            "Tax jurisdiction default",
            ["Vietnam", "United States", "European Union", "Other"],
            index=0, disabled=True,
            help="Active in Slot 4 / P40.",
        )

    with st.container(border=True):
        st.subheader("Cross-tool source paths (read-only)")
        s = cross_tool_status()
        st.markdown(f"**Tool #1 (Companion Dashboard)** — "
                    f"{'✓ installed' if s['companion']['installed'] else '✗ missing'}")
        st.code(s["companion"]["path"], language="text")
        if s["companion"]["installed"]:
            st.caption(f"  → {s['companion']['transaction_count']} transactions visible (read-only)")
        st.markdown(f"**Tool #4 (Vision Analyzer)** — "
                    f"{'✓ installed' if s['vision']['installed'] else '✗ missing'}")
        st.code(s["vision"]["path"], language="text")
        if s["vision"]["installed"]:
            st.caption(f"  → {s['vision']['receipt_count']} receipts visible (read-only)")

    with st.container(border=True):
        st.subheader("Privacy")
        st.toggle(
            "Cloud sync (off by default)",
            value=False, disabled=True,
            help="Constitution Article VII §2: telemetry / cloud sync is opt-in only.",
        )

    with st.container(border=True):
        st.subheader("Cost limits (read-only — declared in the manifest)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Per session",     "$1.00")
        c2.metric("Per day",         "$5.00")
        c3.metric("API calls/sess.", "300")

    page_footer()
