# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""SQLite store for the X Creator Payout Optimizer.

Owns the official schema (5 tables: ``schema_meta``, ``forecasts``,
``content_ideas``, ``tax_estimates``, ``roi_records``), an idempotent
migration runner, CRUD helpers, and three of the five manifest-declared
tool functions: ``forecast_earnings``, ``estimate_tax_burden``, and
``analyze_content_roi``. The other two (``optimize_content_topic`` and
``fetch_x_metrics``) live in ``api_clients.py`` next to the Grok stubs.

Each store-side manifest tool orchestrates:
  1. Read-only cross-tool data via ``companion_reader`` and ``vision_reader``
  2. A Grok stub call from ``api_clients`` (private ``_grok_*`` helpers)
  3. Persistence into the appropriate table with full provenance

Constitution Article III is enforced by the cross-tool readers' SQLite-
level read-only mode plus this manifest's "READS only" rule.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import db_path
from .api_clients import (
    _grok_forecast_call, _grok_tax_call, _grok_roi_call,
)
from .companion_reader import (
    get_companion_summary, read_revenue_rows, read_cost_rows,
)
from .vision_reader import (
    get_vision_summary, read_receipts,
)


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forecasts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    horizon_label       TEXT    NOT NULL,
    point_value         REAL    NOT NULL,
    low_value           REAL    NOT NULL,
    high_value          REAL    NOT NULL,
    drivers             TEXT    NOT NULL,
    confidence          TEXT    NOT NULL CHECK (confidence IN ('high','medium','low')),
    confidence_reason   TEXT,
    data_window         TEXT    NOT NULL,
    model               TEXT    NOT NULL DEFAULT 'grok-4.3',
    tool1_rows_used     INTEGER NOT NULL DEFAULT 0,
    tool4_rows_used     INTEGER NOT NULL DEFAULT 0,
    generated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_forecasts_at ON forecasts(generated_at);

CREATE TABLE IF NOT EXISTS content_ideas (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    topic                  TEXT    NOT NULL,
    angle                  TEXT    NOT NULL,
    format                 TEXT,
    predicted_engagement   REAL,
    predicted_revenue_usd  REAL,
    confidence             TEXT    CHECK (confidence IN ('high','medium','low')),
    rationale              TEXT,
    status                 TEXT    NOT NULL DEFAULT 'suggested'
                            CHECK (status IN ('suggested','accepted','rejected','published')),
    user_feedback          TEXT,
    generated_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_content_ideas_topic   ON content_ideas(topic);
CREATE INDEX IF NOT EXISTS idx_content_ideas_status  ON content_ideas(status);

CREATE TABLE IF NOT EXISTS tax_estimates (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start          TEXT    NOT NULL,
    period_end            TEXT    NOT NULL,
    jurisdiction          TEXT    NOT NULL,
    gross_income          REAL    NOT NULL,
    deductible_expenses   REAL    NOT NULL DEFAULT 0,
    taxable_income        REAL,
    estimated_rate_pct    REAL,
    estimated_tax_owed    REAL,
    estimated_net         REAL,
    assumptions           TEXT,
    confidence            TEXT    CHECK (confidence IN ('high','medium','low')),
    confidence_reason     TEXT,
    tool1_rows_used       INTEGER NOT NULL DEFAULT 0,
    tool4_rows_used       INTEGER NOT NULL DEFAULT 0,
    generated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tax_estimates_at ON tax_estimates(generated_at);

CREATE TABLE IF NOT EXISTS roi_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    content_topic     TEXT    NOT NULL,
    period_start      TEXT    NOT NULL,
    period_end        TEXT    NOT NULL,
    revenue_usd       REAL    NOT NULL,
    cost_usd          REAL    NOT NULL,
    net_usd           REAL    NOT NULL,
    roi_pct           REAL,
    drivers           TEXT,
    confidence        TEXT    CHECK (confidence IN ('high','medium','low')),
    tool1_rows_used   INTEGER NOT NULL DEFAULT 0,
    tool4_rows_used   INTEGER NOT NULL DEFAULT 0,
    generated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_roi_records_topic ON roi_records(content_topic);
CREATE INDEX IF NOT EXISTS idx_roi_records_at    ON roi_records(generated_at);
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Forecasts CRUD -------------------------------------------------------

def insert_forecast_horizons(
    *,
    horizons: list[dict],
    drivers: list[dict],
    confidence: str,
    confidence_reason: str | None,
    data_window: str,
    model: str = "grok-4.3",
    tool1_rows_used: int = 0,
    tool4_rows_used: int = 0,
) -> list[int]:
    """Insert one row per horizon (30/60/90); return the new ids."""
    drivers_json = json.dumps(drivers, ensure_ascii=False)
    ids: list[int] = []
    with get_connection() as conn:
        for h in horizons:
            cur = conn.execute(
                """
                INSERT INTO forecasts
                    (horizon_label, point_value, low_value, high_value, drivers,
                     confidence, confidence_reason, data_window, model,
                     tool1_rows_used, tool4_rows_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    h["label"], float(h["point"]), float(h["low"]), float(h["high"]),
                    drivers_json, confidence, confidence_reason,
                    data_window, model, int(tool1_rows_used), int(tool4_rows_used),
                ),
            )
            ids.append(int(cur.lastrowid))
        conn.commit()
    return ids


def get_recent_forecasts(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = []
        for r in conn.execute(
            "SELECT * FROM forecasts ORDER BY generated_at DESC LIMIT ?", (limit,)
        ):
            d = dict(r)
            d["drivers"] = json.loads(d.get("drivers") or "[]")
            rows.append(d)
        return rows


# --- Content ideas CRUD ---------------------------------------------------

def insert_content_idea(
    *,
    topic: str, angle: str, format: str | None = None,
    predicted_engagement: float | None = None,
    predicted_revenue_usd: float | None = None,
    confidence: str | None = None,
    rationale: str | None = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO content_ideas
                (topic, angle, format, predicted_engagement, predicted_revenue_usd,
                 confidence, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic, angle, format, predicted_engagement, predicted_revenue_usd,
                (confidence or "low").lower(), rationale,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_recent_content_ideas(topic: str | None = None, limit: int = 20) -> list[dict]:
    sql = "SELECT * FROM content_ideas"
    args: list[Any] = []
    if topic:
        sql += " WHERE topic = ?"; args.append(topic)
    sql += " ORDER BY generated_at DESC LIMIT ?"
    args.append(limit)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


# --- Tax estimates CRUD ---------------------------------------------------

def insert_tax_estimate(estimate: dict) -> int:
    """Persist a tax-estimate dict as returned by the Grok tax stub."""
    period = estimate.get("period") or {}
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO tax_estimates
                (period_start, period_end, jurisdiction, gross_income,
                 deductible_expenses, taxable_income, estimated_rate_pct,
                 estimated_tax_owed, estimated_net, assumptions, confidence,
                 confidence_reason, tool1_rows_used, tool4_rows_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                period.get("start"), period.get("end"),
                estimate.get("jurisdiction"),
                float(estimate.get("gross_income") or 0.0),
                float(estimate.get("deductible_expenses") or 0.0),
                float(estimate.get("taxable_income") or 0.0),
                float(estimate.get("estimated_rate_pct") or 0.0),
                float(estimate.get("estimated_tax_owed") or 0.0),
                float(estimate.get("estimated_net") or 0.0),
                json.dumps(estimate.get("assumptions") or [], ensure_ascii=False),
                (estimate.get("confidence") or "low").lower(),
                estimate.get("confidence_reason"),
                int(estimate.get("provenance", {}).get("tool1_rows_used") or 0),
                int(estimate.get("provenance", {}).get("tool4_rows_used") or 0),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


# --- ROI records CRUD -----------------------------------------------------

def insert_roi_record(record: dict) -> int:
    period = record.get("period") or {}
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO roi_records
                (content_topic, period_start, period_end, revenue_usd, cost_usd,
                 net_usd, roi_pct, drivers, confidence,
                 tool1_rows_used, tool4_rows_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("content_topic"),
                period.get("start"), period.get("end"),
                float(record.get("revenue_usd") or 0.0),
                float(record.get("cost_usd") or 0.0),
                float(record.get("net_usd") or 0.0),
                record.get("roi_pct"),
                json.dumps(record.get("drivers") or [], ensure_ascii=False),
                (record.get("confidence") or "low").lower(),
                int(record.get("provenance", {}).get("tool1_rows_used") or 0),
                int(record.get("provenance", {}).get("tool4_rows_used") or 0),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


# --- Manifest tool: forecast_earnings -------------------------------------

def forecast_earnings(window_days: int, horizon_days: int = 90, **_: Any) -> dict:
    """Manifest tool — forecast next-N-day earnings.

    Reads Tool #1 + Tool #4 read-only via the cross-tool readers, calls the
    Grok stub, persists the 30/60/90 horizons, and returns the full result
    with provenance + the persisted ids.
    """
    companion = get_companion_summary()
    vision    = get_vision_summary()
    res = _grok_forecast_call(
        window_days=int(window_days), horizon_days=int(horizon_days),
        companion_summary=companion, vision_summary=vision,
    )

    res["provenance"]["tool1_rows_used"] = int(companion.get("transaction_count") or 0)
    res["provenance"]["tool4_rows_used"] = int(vision.get("receipt_count") or 0)
    res["provenance"]["companion_installed"] = bool(companion.get("installed"))
    res["provenance"]["vision_installed"]    = bool(vision.get("installed"))

    if not companion.get("installed"):
        res["confidence"] = "low"
        res["confidence_reason"] = (
            "Tool #1 not installed — revenue history blank. "
            "Install x-money-companion-dashboard to enable real forecasts."
        )

    forecast_ids = insert_forecast_horizons(
        horizons=res["horizons"],
        drivers=res["drivers"],
        confidence=res["confidence"],
        confidence_reason=res.get("confidence_reason"),
        data_window=res["data_window"],
        model=res.get("model", "grok-4.3"),
        tool1_rows_used=res["provenance"]["tool1_rows_used"],
        tool4_rows_used=res["provenance"]["tool4_rows_used"],
    )
    res["forecast_ids"] = forecast_ids
    res["stored_at"] = _now_iso()
    return res


# --- Manifest tool: estimate_tax_burden -----------------------------------

def estimate_tax_burden(
    start_date: str, end_date: str, jurisdiction: str, **_: Any
) -> dict:
    """Manifest tool — estimate tax burden for a date range + jurisdiction."""
    rev = read_revenue_rows(start_date=start_date, end_date=end_date)
    rcs = read_receipts(start_date=start_date, end_date=end_date)
    gross_income       = sum(float(r.get("amount") or 0) for r in rev.get("rows", []))
    expense_count      = int(rcs.get("row_count") or 0)
    deductible_expenses = sum(float(r.get("total") or 0) for r in rcs.get("rows", []))

    res = _grok_tax_call(
        period={"start": start_date, "end": end_date},
        jurisdiction=jurisdiction,
        gross_income=gross_income,
        deductible_expenses=deductible_expenses,
        expense_count=expense_count,
    )

    res["provenance"]["tool1_rows_used"] = int(rev.get("row_count") or 0)
    res["provenance"]["tool4_rows_used"] = expense_count
    res["provenance"]["companion_installed"] = bool(rev.get("installed"))
    res["provenance"]["vision_installed"]    = bool(rcs.get("installed"))

    res["id"] = insert_tax_estimate(res)
    res["stored_at"] = _now_iso()
    return res


# --- Manifest tool: analyze_content_roi -----------------------------------

def analyze_content_roi(
    start_date: str, end_date: str, content_topic: str = "all", **_: Any
) -> dict:
    """Manifest tool — compute content ROI by joining Tool #1 revenue × Tool #4 costs."""
    rev = read_revenue_rows(start_date=start_date, end_date=end_date)
    rcs = read_receipts(start_date=start_date, end_date=end_date)
    revenue_usd  = sum(float(r.get("amount") or 0) for r in rev.get("rows", []))
    cost_usd     = sum(float(r.get("total")  or 0) for r in rcs.get("rows", []))
    revenue_rows = int(rev.get("row_count") or 0)
    cost_rows    = int(rcs.get("row_count") or 0)

    res = _grok_roi_call(
        content_topic=content_topic,
        period={"start": start_date, "end": end_date},
        revenue_usd=revenue_usd, cost_usd=cost_usd,
        revenue_rows=revenue_rows, cost_rows=cost_rows,
        companion_installed=bool(rev.get("installed")),
        vision_installed=bool(rcs.get("installed")),
    )

    res["provenance"]["tool1_rows_used"] = revenue_rows
    res["provenance"]["tool4_rows_used"] = cost_rows
    res["provenance"]["companion_installed"] = bool(rev.get("installed"))
    res["provenance"]["vision_installed"]    = bool(rcs.get("installed"))

    res["id"] = insert_roi_record(res)
    res["stored_at"] = _now_iso()
    return res
