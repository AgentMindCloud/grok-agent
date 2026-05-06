# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""SQLite store for the X Money Companion Dashboard.

Owns the official schema (4 tables: ``schema_meta``, ``transactions``,
``alerts``, ``insights``), an idempotent migration runner, CRUD helpers,
and three of the five manifest-declared tool functions
(``categorize_transaction``, ``build_tax_export``, ``summarize_alerts``).

The two API-wrapper tools (``fetch_market_quote``, ``fetch_relevant_news``)
live in ``api_clients.py`` next to ``search_x_posts``.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from . import appdata_root, db_path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_date            TEXT    NOT NULL,
    amount             REAL    NOT NULL,
    currency           TEXT    NOT NULL DEFAULT 'USD',
    counterparty       TEXT,
    memo               TEXT,
    category           TEXT,
    confidence         REAL,
    source             TEXT    NOT NULL CHECK (source IN ('manual','vision','api')),
    raw_data           TEXT,
    receipt_image_path TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_transactions_date     ON transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_source   ON transactions(source);

CREATE TABLE IF NOT EXISTS alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    level               TEXT    NOT NULL CHECK (level IN ('warn','info')),
    title               TEXT    NOT NULL,
    body                TEXT    NOT NULL,
    category            TEXT,
    supporting_tx_ids   TEXT,
    status              TEXT    NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','dismissed','investigating')),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    dismissed_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);

CREATE TABLE IF NOT EXISTS insights (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name  TEXT    NOT NULL,
    response_md    TEXT    NOT NULL,
    model          TEXT    NOT NULL,
    input_tokens   INTEGER,
    output_tokens  INTEGER,
    cost_usd       REAL,
    feedback       TEXT,
    generated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_insights_template ON insights(template_name);
CREATE INDEX IF NOT EXISTS idx_insights_at       ON insights(generated_at);
"""


# --- Connection + migrations ----------------------------------------------

def init_db(path: Path | None = None) -> Path:
    """Create the database and run idempotent migrations.

    Safe to call on every app start. Returns the resolved DB path so callers
    can verify it without re-deriving.
    """
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(p)) as conn:
        conn.executescript(SCHEMA_SQL)
        current = _get_meta(conn, "schema_version")
        if current is None:
            _set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        elif int(current) < SCHEMA_VERSION:
            # Future incremental migrations (v2+) get applied here.
            _set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        conn.commit()
    return p


@contextmanager
def get_connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a row-factory-enabled SQLite connection."""
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


# --- Transactions CRUD -----------------------------------------------------

def insert_transaction(
    *,
    tx_date: str,
    amount: float,
    counterparty: str | None,
    memo: str | None = None,
    category: str | None = None,
    currency: str = "USD",
    source: str = "manual",
    raw_data: dict | None = None,
    receipt_image_path: str | None = None,
    confidence: float | None = None,
) -> int:
    """Insert one transaction. Returns the new row id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions
                (tx_date, amount, currency, counterparty, memo,
                 category, confidence, source, raw_data, receipt_image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_date, amount, currency, counterparty, memo,
                category, confidence, source,
                json.dumps(raw_data) if raw_data else None,
                receipt_image_path,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_transactions(
    *,
    start_date: str | None = None,
    end_date:   str | None = None,
    category:   str | None = None,
    source:     str | None = None,
    limit:      int | None = None,
) -> list[dict]:
    """Read transactions with optional filters. Returns plain dicts."""
    sql = "SELECT * FROM transactions WHERE 1=1"
    args: list[Any] = []
    if start_date:
        sql += " AND tx_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND tx_date <= ?"; args.append(end_date)
    if category:
        sql += " AND category = ?"; args.append(category)
    if source:
        sql += " AND source = ?";   args.append(source)
    sql += " ORDER BY tx_date DESC"
    if limit:
        sql += " LIMIT ?"; args.append(limit)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def update_transaction_category(
    tx_id: int, category: str, confidence: float | None = None
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE transactions SET category=?, confidence=?, updated_at=datetime('now') "
            "WHERE id=?",
            (category, confidence, tx_id),
        )
        conn.commit()


def count_transactions() -> int:
    with get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])


# --- Alerts CRUD -----------------------------------------------------------

def insert_alert(
    *,
    level: str,
    title: str,
    body: str,
    category: str | None = None,
    supporting_tx_ids: list[int] | None = None,
) -> int:
    if level not in ("warn", "info"):
        raise ValueError(f"level must be 'warn' or 'info', got '{level}'")
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO alerts (level, title, body, category, supporting_tx_ids) "
            "VALUES (?, ?, ?, ?, ?)",
            (level, title, body, category,
             json.dumps(supporting_tx_ids) if supporting_tx_ids else None),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_active_alerts(horizon_days: int | None = None) -> list[dict]:
    sql = "SELECT * FROM alerts WHERE status = 'active'"
    args: list[Any] = []
    if horizon_days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=horizon_days)).isoformat()
        sql += " AND created_at >= ?"; args.append(cutoff)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def dismiss_alert(alert_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE alerts SET status='dismissed', dismissed_at=datetime('now') WHERE id=?",
            (alert_id,),
        )
        conn.commit()


# --- Insights CRUD ---------------------------------------------------------

def insert_insight(
    *,
    template_name: str,
    response_md: str,
    model: str = "grok-4.3",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO insights "
            "(template_name, response_md, model, input_tokens, output_tokens, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (template_name, response_md, model, input_tokens, output_tokens, cost_usd),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_recent_insights(template_name: str | None = None, limit: int = 10) -> list[dict]:
    sql = "SELECT * FROM insights"
    args: list[Any] = []
    if template_name:
        sql += " WHERE template_name = ?"; args.append(template_name)
    sql += " ORDER BY generated_at DESC LIMIT ?"
    args.append(limit)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


# --- Manifest tool functions (3 store-side) -------------------------------

# Keyword heuristic for the categorize_transaction stub. Real Grok-backed
# categorization wires in P24; until then this baseline keeps the dashboard
# functional and predictable. Order matters — first hit wins.
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("subscriptions",   ("spotify", "adobe", "streamlit", "subscription", "domain")),
    ("food_drink",      ("coffee", "highlands", "starbucks", "lunch", "gofood",
                         "grab food", "restaurant")),
    ("transport",       ("grab", "taxi", "uber", "ride", "transport", "fuel")),
    ("groceries",       ("vinmart", "groceries", "supermarket")),
    ("housing",         ("rent", "vinhomes", "landlord", "mortgage")),
    ("infrastructure",  ("aws", "gcp", "azure", "vercel", "render", "agentmindcloud")),
    ("x_payouts",       ("x payments", "x payouts", "creator payout")),
    ("ad_revenue",      ("youtube", "stripe payout", "ad share", "newsletter sponsor")),
    ("taxes",           ("tax", "irs", "vat")),
]


def categorize_transaction(
    amount: float, counterparty: str, memo: str = "", **_: Any
) -> dict:
    """Manifest tool — classify a single transaction.

    This is the keyword-heuristic baseline that ships with P22; the
    Grok-backed categorizer arrives in P24 and will replace this body while
    keeping the same return shape. Until then the function is deterministic
    and offline-safe so the rest of the dashboard can be exercised end to end.

    Returns a dict matching the JSON contract in
    ``prompts/user_templates.md#transaction-categorize``.
    """
    text = f"{counterparty or ''} {memo or ''}".lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in text for k in keywords):
            return {
                "category": category,
                "confidence": "medium",
                "reasoning": f"Keyword match in counterparty/memo: '{counterparty}'.",
                "clarifying_question": "",
            }
    return {
        "category": "other",
        "confidence": "low",
        "reasoning": "No keyword hit in counterparty or memo.",
        "clarifying_question": (
            f"What category fits a {amount:+.2f} transaction with '{counterparty}'?"
        ),
    }


# Disclaimer text written verbatim into every export (Constitution Article V).
_EXPORT_V1_BANNER = (
    "# NOT FINANCIAL ADVICE. This file provides information only. "
    "Always consult a licensed financial advisor before making decisions."
)
_EXPORT_V2_BANNER = (
    "# NOT TAX ADVICE. Tax obligations vary by jurisdiction. "
    "Consult a licensed tax professional. Especially relevant for "
    "Vietnam-resident creators with international platform earnings."
)


def build_tax_export(start_date: str, end_date: str, format: str) -> dict:
    """Manifest tool — build a consent-gated tax export.

    The caller MUST have already passed the user through the consent gate
    (Constitution Article II) before invoking this function. The export
    file is written under ``appdata_root()`` and includes V.1 + V.2
    disclaimer banners as the first lines (CSV) — PDF rendering ships in
    a later prompt; today PDF requests fall back to CSV with a notice.
    """
    if format not in ("csv", "pdf"):
        raise ValueError(f"format must be 'csv' or 'pdf', got '{format}'")

    rows = get_transactions(start_date=start_date, end_date=end_date)

    out_dir = appdata_root()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tax_export_{start_date}_{end_date}.csv"

    note = ""
    if format == "pdf":
        note = " (PDF renderer arrives in a later prompt; falling back to CSV.)"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        f.write(_EXPORT_V1_BANNER + "\n")
        f.write(_EXPORT_V2_BANNER + "\n")
        f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# Range: {start_date} -> {end_date}\n")
        f.write(f"# Transaction count: {len(rows)}\n")
        f.write("#\n")
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id", "tx_date", "amount", "currency", "counterparty",
                "memo", "category", "source",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in writer.fieldnames})

    return {
        "path": str(out_path),
        "format": "csv" if format == "pdf" else format,
        "transaction_count": len(rows),
        "disclaimer_prepended": True,
        "note": note,
    }


def summarize_alerts(horizon_days: int) -> dict:
    """Manifest tool — roll up active alerts within a horizon window."""
    alerts = get_active_alerts(horizon_days=horizon_days)
    by_level = {"warn": 0, "info": 0}
    by_category: dict[str, int] = {}
    for a in alerts:
        by_level[a["level"]] = by_level.get(a["level"], 0) + 1
        cat = a.get("category") or "uncategorized"
        by_category[cat] = by_category.get(cat, 0) + 1
    return {
        "horizon_days":   horizon_days,
        "alert_count":    len(alerts),
        "by_level":       by_level,
        "by_category":    by_category,
        "alerts":         alerts,
    }
