# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""SQLite store for the X Smart Cashtag Alpha Engine.

Owns the canonical schema (5 tables: ``schema_meta``, ``cashtags``,
``watchlist``, ``alpha_reports``, ``portfolio_simulations``), an
idempotent migration runner, CRUD helpers, and three of the five
manifest-declared tool functions: ``track_cashtag``, ``simulate_portfolio``,
and ``generate_alpha_report`` (the latter orchestrates the API + Grok-stub
calls in ``api_clients.py`` and persists the structured result here).

The two API-wrapper tools (``fetch_cashtag_quote``, ``fetch_cashtag_news``)
live in ``api_clients.py`` next to the ``search_x_posts`` and
``_generate_alpha_via_grok`` stubs.

A read-only cross-tool helper ``fetch_companion_dashboard_holdings`` reads
Tool #1's transactions table without modifying it, supporting the
"engine reads from Companion Dashboard" cross-tool note in P25's README.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from . import appdata_root, db_path
from .api_clients import (
    fetch_cashtag_quote,
    fetch_cashtag_news,
    search_x_posts,
    _generate_alpha_via_grok,
)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cashtags (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    cashtag              TEXT    NOT NULL UNIQUE,
    name                 TEXT,
    asset_class          TEXT    NOT NULL DEFAULT 'unknown'
                          CHECK (asset_class IN ('equity','crypto','fx','commodity','unknown')),
    last_quote_price     REAL,
    last_quote_currency  TEXT,
    last_quote_timestamp TEXT,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cashtags_asset_class ON cashtags(asset_class);

CREATE TABLE IF NOT EXISTS watchlist (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cashtag       TEXT    NOT NULL UNIQUE,
    threshold_pct REAL    DEFAULT 5.0,
    notes         TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    added_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    removed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watchlist(is_active);

CREATE TABLE IF NOT EXISTS alpha_reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cashtag           TEXT    NOT NULL,
    headline          TEXT    NOT NULL,
    body              TEXT    NOT NULL,
    confidence        TEXT    NOT NULL CHECK (confidence IN ('high','medium','low')),
    confidence_reason TEXT,
    sources           TEXT    NOT NULL,
    contradictions    TEXT,
    model             TEXT    NOT NULL DEFAULT 'grok-4.3',
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    cost_usd          REAL,
    feedback          TEXT,
    generated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alpha_reports_cashtag ON alpha_reports(cashtag);
CREATE INDEX IF NOT EXISTS idx_alpha_reports_at      ON alpha_reports(generated_at);

CREATE TABLE IF NOT EXISTS portfolio_simulations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date      TEXT    NOT NULL,
    end_date        TEXT    NOT NULL,
    positions       TEXT    NOT NULL,
    starting_value  REAL    NOT NULL,
    ending_value    REAL    NOT NULL,
    pnl_abs         REAL    NOT NULL,
    pnl_pct         REAL    NOT NULL,
    contributors    TEXT,
    seed            INTEGER,
    generated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sims_dates ON portfolio_simulations(start_date, end_date);
"""


# --- Connection + migrations ----------------------------------------------

def init_db(path: Path | None = None) -> Path:
    """Create the database and run idempotent migrations."""
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(p)) as conn:
        conn.executescript(SCHEMA_SQL)
        current = _get_meta(conn, "schema_version")
        if current is None or int(current) < SCHEMA_VERSION:
            _set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        conn.commit()
    return p


@contextmanager
def get_connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    cur = conn.execute("SELECT value FROM schema_meta WHERE key = ?", (key,))
    row = cur.fetchone()
    return row[0] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


# --- Cashtags CRUD --------------------------------------------------------

def upsert_cashtag(
    cashtag: str,
    *,
    name: str | None = None,
    asset_class: str = "unknown",
    last_quote: dict | None = None,
) -> None:
    """Register or update a cashtag in the master list."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM cashtags WHERE cashtag = ?", (cashtag,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE cashtags SET name=COALESCE(?, name), asset_class=? "
                " WHERE cashtag=?",
                (name, asset_class, cashtag),
            )
        else:
            conn.execute(
                "INSERT INTO cashtags (cashtag, name, asset_class) VALUES (?, ?, ?)",
                (cashtag, name, asset_class),
            )
        if last_quote and last_quote.get("price") is not None:
            conn.execute(
                "UPDATE cashtags "
                " SET last_quote_price=?, last_quote_currency=?, last_quote_timestamp=? "
                " WHERE cashtag=?",
                (
                    float(last_quote["price"]),
                    last_quote.get("currency") or "USD",
                    last_quote.get("provenance", {}).get("retrieved_at"),
                    cashtag,
                ),
            )
        conn.commit()


def get_cashtag(cashtag: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cashtags WHERE cashtag = ?", (cashtag,)
        ).fetchone()
        return dict(row) if row else None


def list_cashtags(asset_class: str | None = None) -> list[dict]:
    sql = "SELECT * FROM cashtags"
    args: list[Any] = []
    if asset_class:
        sql += " WHERE asset_class = ?"
        args.append(asset_class)
    sql += " ORDER BY cashtag"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


# --- Watchlist CRUD -------------------------------------------------------

def add_to_watchlist(
    cashtag: str, threshold_pct: float | None = None, notes: str | None = None
) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, is_active FROM watchlist WHERE cashtag = ?", (cashtag,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE watchlist "
                " SET threshold_pct=COALESCE(?, threshold_pct), "
                "     notes=COALESCE(?, notes), "
                "     is_active=1, removed_at=NULL "
                " WHERE id=?",
                (threshold_pct, notes, row[0]),
            )
            wid = int(row[0])
        else:
            cur = conn.execute(
                "INSERT INTO watchlist (cashtag, threshold_pct, notes) VALUES (?, ?, ?)",
                (cashtag, threshold_pct, notes),
            )
            wid = int(cur.lastrowid)
        conn.commit()
        return wid


def remove_from_watchlist(cashtag: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE watchlist SET is_active=0, removed_at=datetime('now') "
            " WHERE cashtag=? AND is_active=1",
            (cashtag,),
        )
        conn.commit()
        return cur.rowcount > 0


def get_watchlist(active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM watchlist"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY added_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql)]


# --- Alpha reports CRUD ---------------------------------------------------

def insert_alpha_report(
    *,
    cashtag: str,
    headline: str,
    body: str,
    confidence: str,
    confidence_reason: str | None,
    sources: list[str],
    contradictions: list[dict] | None = None,
    model: str = "grok-4.3",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> int:
    if confidence not in ("high", "medium", "low"):
        raise ValueError(f"confidence must be high|medium|low, got {confidence!r}")
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO alpha_reports
                (cashtag, headline, body, confidence, confidence_reason,
                 sources, contradictions, model,
                 input_tokens, output_tokens, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cashtag, headline, body, confidence, confidence_reason,
                json.dumps(sources, ensure_ascii=False),
                json.dumps(contradictions or [], ensure_ascii=False),
                model, input_tokens, output_tokens, cost_usd,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_recent_alpha_reports(
    cashtag: str | None = None, limit: int = 10
) -> list[dict]:
    sql = "SELECT * FROM alpha_reports"
    args: list[Any] = []
    if cashtag:
        sql += " WHERE cashtag = ?"
        args.append(cashtag)
    sql += " ORDER BY generated_at DESC LIMIT ?"
    args.append(limit)
    with get_connection() as conn:
        rows = []
        for r in conn.execute(sql, args):
            d = dict(r)
            d["sources"]        = json.loads(d.get("sources")        or "[]")
            d["contradictions"] = json.loads(d.get("contradictions") or "[]")
            rows.append(d)
        return rows


# --- Portfolio simulations CRUD -------------------------------------------

def insert_portfolio_simulation(
    *,
    start_date: str,
    end_date: str,
    positions: list[dict],
    starting_value: float,
    ending_value: float,
    pnl_abs: float,
    pnl_pct: float,
    contributors: dict | None = None,
    seed: int | None = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO portfolio_simulations
                (start_date, end_date, positions, starting_value, ending_value,
                 pnl_abs, pnl_pct, contributors, seed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                start_date, end_date,
                json.dumps(positions, ensure_ascii=False),
                starting_value, ending_value, pnl_abs, pnl_pct,
                json.dumps(contributors or {}, ensure_ascii=False),
                seed,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_recent_simulations(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = []
        for r in conn.execute(
            "SELECT * FROM portfolio_simulations ORDER BY generated_at DESC LIMIT ?",
            (limit,),
        ):
            d = dict(r)
            d["positions"]    = json.loads(d.get("positions")    or "[]")
            d["contributors"] = json.loads(d.get("contributors") or "{}")
            rows.append(d)
        return rows


# --- Cross-tool helper: read Tool #1 (Companion Dashboard) holdings -------

def fetch_companion_dashboard_holdings(limit: int = 100) -> dict:
    """Read transactions from Tool #1's SQLite. Read-only — never modifies.

    Returns ``{"installed": bool, "transactions": list, "error": str | None}``.
    Use to seed the Portfolio Simulator with positions derived from real
    cashflow.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        companion_db = Path(base) / "grok-agent" / "x-money-companion-dashboard" / "data.db"
    else:
        companion_db = (
            Path.home() / ".local" / "share"
            / "grok-agent" / "x-money-companion-dashboard" / "data.db"
        )

    if not companion_db.exists():
        return {
            "installed":    False,
            "transactions": [],
            "companion_db": str(companion_db),
            "error": "Companion Dashboard not installed at the expected path.",
        }
    try:
        with sqlite3.connect(str(companion_db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = list(conn.execute(
                "SELECT * FROM transactions ORDER BY tx_date DESC LIMIT ?",
                (int(limit),),
            ))
        return {
            "installed":    True,
            "transactions": [dict(r) for r in rows],
            "companion_db": str(companion_db),
            "error":        None,
        }
    except Exception as e:
        return {
            "installed":    True,
            "transactions": [],
            "companion_db": str(companion_db),
            "error":        f"{type(e).__name__}: {e}",
        }


# --- Manifest tool: track_cashtag -----------------------------------------

def track_cashtag(
    cashtag: str, action: str, threshold_pct: float | None = None, **_: Any
) -> dict:
    """Manifest tool — add or remove a cashtag from the watchlist."""
    if action not in ("add", "remove"):
        return {
            "cashtag": cashtag,
            "action":  action,
            "ok":      False,
            "error":   f"action must be 'add' or 'remove', got {action!r}",
        }
    if action == "add":
        upsert_cashtag(cashtag)
        wid = add_to_watchlist(cashtag, threshold_pct=threshold_pct)
        return {
            "cashtag":       cashtag,
            "action":        "add",
            "watchlist_id":  wid,
            "threshold_pct": threshold_pct,
            "ok":            True,
            "error":         None,
        }
    removed = remove_from_watchlist(cashtag)
    return {
        "cashtag": cashtag,
        "action":  "remove",
        "ok":      removed,
        "error":   None if removed else "Cashtag not found in active watchlist.",
    }


# --- Manifest tool: simulate_portfolio ------------------------------------

def simulate_portfolio(
    positions: list[dict], start_date: str, end_date: str, **_: Any
) -> dict:
    """Manifest tool — run a what-if portfolio simulation across positions.

    The skeleton uses a seeded random walk per position. Real historical
    yfinance / coingecko backfill is a future enhancement; this contract
    keeps the JSON shape stable so the surrounding UI / Grok prompts can
    integrate now.
    """
    starting = sum(
        float(p.get("qty") or 0) * float(p.get("entry_price") or 0)
        for p in positions
    )
    if starting <= 0:
        return {
            "start_date":     start_date,
            "end_date":       end_date,
            "starting_value": 0.0,
            "ending_value":   0.0,
            "pnl_abs":        0.0,
            "pnl_pct":        0.0,
            "positions":      positions,
            "error":          "No positions provided with valid qty + entry_price.",
        }

    seed = abs(hash((start_date, end_date, json.dumps(positions, sort_keys=True)))) % (2**32)
    rng = random.Random(seed)
    try:
        s = datetime.fromisoformat(start_date).date()
        e = datetime.fromisoformat(end_date).date()
    except ValueError as ex:
        return {"error": f"Invalid date: {ex}", "positions": positions}
    days = max(1, (e - s).days)

    v = starting
    for _i in range(days + 1):
        v *= (1.0 + rng.gauss(0.0008, 0.012))
    ending = round(v, 2)
    pnl_abs = round(ending - starting, 2)
    pnl_pct = round((pnl_abs / starting) * 100.0, 4)

    sim_id = insert_portfolio_simulation(
        start_date=start_date, end_date=end_date,
        positions=positions,
        starting_value=starting, ending_value=ending,
        pnl_abs=pnl_abs, pnl_pct=pnl_pct,
        seed=seed,
    )

    return {
        "id":             sim_id,
        "start_date":     start_date,
        "end_date":       end_date,
        "days":           days,
        "positions":      positions,
        "starting_value": starting,
        "ending_value":   ending,
        "pnl_abs":        pnl_abs,
        "pnl_pct":        pnl_pct,
        "seed":           seed,
        "note":           "Seeded random-walk skeleton; historical backfill via yfinance/coingecko in a later prompt.",
        "error":          None,
    }


# --- Manifest tool: generate_alpha_report ---------------------------------

def generate_alpha_report(
    cashtag: str, window_hours: int = 24, **_: Any
) -> dict:
    """Manifest tool — orchestrate the alpha-report flow.

    Pulls the live quote, news headlines, and (stubbed) x_search excerpts;
    calls the Grok stub to produce the structured report; persists the
    result to the ``alpha_reports`` table; returns the persisted row + the
    Grok provenance block.

    Real Grok client wires in a later prompt — until then the report is
    flagged ``confidence: "low"`` with a clear stub note in the body so
    Article IV (Provenance & Truth) stays honest.
    """
    quote = fetch_cashtag_quote(cashtag)
    news  = fetch_cashtag_news(cashtag, limit=5)
    xres  = search_x_posts(cashtag, limit=5)

    upsert_cashtag(
        cashtag,
        name=quote.get("name"),
        asset_class=quote.get("asset_class") or "unknown",
        last_quote=quote,
    )

    grok = _generate_alpha_via_grok(
        cashtag=cashtag,
        quote=quote, news=news, x_search_result=xres,
        window_hours=window_hours,
    )

    report_id = insert_alpha_report(
        cashtag=cashtag,
        headline=grok["headline"],
        body=grok["body"],
        confidence=grok["confidence"],
        confidence_reason=grok.get("confidence_reason"),
        sources=grok.get("sources") or [],
        contradictions=grok.get("contradictions") or [],
        model=grok.get("model", "grok-4.3"),
        input_tokens=grok.get("input_tokens"),
        output_tokens=grok.get("output_tokens"),
        cost_usd=grok.get("cost_usd"),
    )

    return {
        "id":           report_id,
        "cashtag":      cashtag,
        "window_hours": window_hours,
        "report":       grok,
        "stored_at":    datetime.now(timezone.utc).isoformat(),
    }
