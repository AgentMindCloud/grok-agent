# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Read-only cross-tool reader: X Money Companion Dashboard (Tool #1).

This module is the ONLY way the X Creator Payout Optimizer touches Tool #1's
SQLite. It opens the companion DB in **SQLite-level read-only mode** via the
``file:...?mode=ro`` URI — any accidental write attempt raises
``sqlite3.OperationalError: attempt to write a readonly database`` rather
than silently mutating Tool #1's state. That's defense-in-depth for
Constitution Article III (cross-tool READS only by this manifest),
complementing the manifest's rule + the scanner check + the system-prompt
rule.

Public surface:

- ``is_installed()`` — bool
- ``get_companion_summary()`` — high-level dict (counts, totals, date range)
- ``read_transactions(...)`` — filtered list of transaction dicts
- ``read_revenue_rows(...)`` — convenience: rows with ``amount > 0``
- ``read_cost_rows(...)``    — convenience: rows with ``amount < 0``

Every function returns a structured dict that includes a ``provenance``
block (Constitution Article IV) and never raises — failures populate the
``error`` field so the surrounding UI / Grok layer can render a graceful
"Tool #1 not installed" state.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import companion_db_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_readonly(path: Path) -> sqlite3.Connection:
    """Open Tool #1's SQLite in true read-only mode (defense-in-depth)."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def is_installed() -> bool:
    """Whether Tool #1's SQLite exists at the canonical path."""
    return companion_db_path().exists()


def get_companion_summary() -> dict:
    """High-level summary of the user's Companion Dashboard data.

    Returns a dict with ``installed``, transaction count, totals, the
    date range covered, the categories seen, and a ``provenance`` block.
    Never raises — sets ``error`` instead.
    """
    db = companion_db_path()
    prov = {
        "source":       "x-money-companion-dashboard (read-only)",
        "endpoint":     str(db),
        "retrieved_at": _now_iso(),
        "mode":         "sqlite_readonly_uri",
    }
    result: dict[str, Any] = {
        "installed":         False,
        "transaction_count": 0,
        "total_inflow":      0.0,
        "total_outflow":     0.0,
        "net":               0.0,
        "categories":        [],
        "earliest_tx":       None,
        "latest_tx":         None,
        "path":              str(db),
        "provenance":        prov,
        "error":             None,
    }

    if not db.exists():
        result["error"] = (
            f"Companion DB not found at {db}. "
            "Install x-money-companion-dashboard to enable revenue-side context."
        )
        return result

    result["installed"] = True
    try:
        with _open_readonly(db) as conn:
            count_row = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()
            result["transaction_count"] = int(count_row[0]) if count_row else 0

            agg = conn.execute(
                "SELECT "
                " COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS inflow, "
                " COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) AS outflow, "
                " MIN(tx_date) AS earliest, "
                " MAX(tx_date) AS latest "
                "FROM transactions"
            ).fetchone()
            if agg:
                result["total_inflow"]  = float(agg["inflow"]  or 0.0)
                result["total_outflow"] = float(agg["outflow"] or 0.0)
                result["net"]           = result["total_inflow"] - result["total_outflow"]
                result["earliest_tx"]   = agg["earliest"]
                result["latest_tx"]     = agg["latest"]

            cats = conn.execute(
                "SELECT DISTINCT category FROM transactions "
                "WHERE category IS NOT NULL ORDER BY category"
            )
            result["categories"] = [r["category"] for r in cats]
    except sqlite3.Error as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def read_transactions(
    *,
    start_date: str | None = None,
    end_date:   str | None = None,
    category:   str | None = None,
    source:     str | None = None,
    only_inflow:  bool     = False,
    only_outflow: bool     = False,
    limit:      int | None = None,
) -> dict:
    """Read transactions from Tool #1 with the requested filters.

    Returns ``{"installed", "rows": [...], "row_count", "provenance",
    "error"}``. Rows are dicts with the same shape as Tool #1's
    ``transactions`` table.
    """
    db = companion_db_path()
    prov = {
        "source":       "x-money-companion-dashboard (read-only)",
        "endpoint":     str(db),
        "retrieved_at": _now_iso(),
        "mode":         "sqlite_readonly_uri",
    }
    result: dict[str, Any] = {
        "installed":  False,
        "rows":       [],
        "row_count":  0,
        "provenance": prov,
        "error":      None,
    }
    if not db.exists():
        result["error"] = "Companion DB not installed."
        return result
    result["installed"] = True

    sql  = "SELECT * FROM transactions WHERE 1=1"
    args: list[Any] = []
    if start_date:
        sql += " AND tx_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND tx_date <= ?"; args.append(end_date)
    if category:
        sql += " AND category = ?"; args.append(category)
    if source:
        sql += " AND source = ?";   args.append(source)
    if only_inflow:
        sql += " AND amount > 0"
    if only_outflow:
        sql += " AND amount < 0"
    sql += " ORDER BY tx_date DESC"
    if limit is not None:
        sql += " LIMIT ?"; args.append(int(limit))

    try:
        with _open_readonly(db) as conn:
            rows = [dict(r) for r in conn.execute(sql, args)]
        result["rows"] = rows
        result["row_count"] = len(rows)
    except sqlite3.Error as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def read_revenue_rows(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Convenience: positive-amount transactions in the window."""
    return read_transactions(start_date=start_date, end_date=end_date, only_inflow=True)


def read_cost_rows(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Convenience: negative-amount transactions in the window."""
    return read_transactions(start_date=start_date, end_date=end_date, only_outflow=True)
