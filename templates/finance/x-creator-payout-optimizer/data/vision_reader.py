# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Read-only cross-tool reader: X Money Vision Analyzer (Tool #4).

This module is the ONLY way the X Creator Payout Optimizer touches Tool #4's
SQLite. SQLite-level read-only enforcement via the ``file:...?mode=ro`` URI —
defense-in-depth for Constitution Article III (cross-tool READS only by
this manifest). Same posture as ``companion_reader.py``.

Public surface:

- ``is_installed()`` — bool
- ``get_vision_summary()`` — high-level dict (receipt count, totals, status mix)
- ``read_receipts(...)`` — filtered list of receipt dicts
- ``read_parsed_items_for_receipt(receipt_id)`` — line items joined to a receipt

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import vision_db_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_readonly(path: Path) -> sqlite3.Connection:
    """Open Tool #4's SQLite in true read-only mode (defense-in-depth)."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def is_installed() -> bool:
    return vision_db_path().exists()


def get_vision_summary() -> dict:
    """High-level summary of the user's Vision Analyzer data."""
    db = vision_db_path()
    prov = {
        "source":       "x-money-vision-analyzer (read-only)",
        "endpoint":     str(db),
        "retrieved_at": _now_iso(),
        "mode":         "sqlite_readonly_uri",
    }
    result: dict[str, Any] = {
        "installed":      False,
        "receipt_count":  0,
        "total_outflow":  0.0,
        "by_status":      {},
        "earliest_tx":    None,
        "latest_tx":      None,
        "path":           str(db),
        "provenance":     prov,
        "error":          None,
    }

    if not db.exists():
        result["error"] = (
            f"Vision Analyzer DB not found at {db}. "
            "Install x-money-vision-analyzer to enable cost-side context."
        )
        return result

    result["installed"] = True
    try:
        with _open_readonly(db) as conn:
            count_row = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()
            result["receipt_count"] = int(count_row[0]) if count_row else 0

            agg = conn.execute(
                "SELECT "
                " COALESCE(SUM(total), 0) AS outflow, "
                " MIN(tx_date) AS earliest, "
                " MAX(tx_date) AS latest "
                "FROM receipts WHERE status != 'discarded'"
            ).fetchone()
            if agg:
                result["total_outflow"] = float(agg["outflow"] or 0.0)
                result["earliest_tx"]   = agg["earliest"]
                result["latest_tx"]     = agg["latest"]

            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM receipts GROUP BY status ORDER BY status"
            )
            result["by_status"] = {r["status"]: int(r["n"]) for r in status_rows}
    except sqlite3.Error as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def read_receipts(
    *,
    start_date: str | None = None,
    end_date:   str | None = None,
    status:     str | None = None,
    limit:      int | None = None,
) -> dict:
    """Read receipts from Tool #4 with optional filters."""
    db = vision_db_path()
    prov = {
        "source":       "x-money-vision-analyzer (read-only)",
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
        result["error"] = "Vision Analyzer DB not installed."
        return result
    result["installed"] = True

    sql  = "SELECT * FROM receipts WHERE 1=1"
    args: list[Any] = []
    if start_date:
        sql += " AND tx_date >= ?"; args.append(start_date)
    if end_date:
        sql += " AND tx_date <= ?"; args.append(end_date)
    if status:
        sql += " AND status = ?"; args.append(status)
    sql += " ORDER BY uploaded_at DESC"
    if limit is not None:
        sql += " LIMIT ?"; args.append(int(limit))

    try:
        with _open_readonly(db) as conn:
            rows = [dict(r) for r in conn.execute(sql, args)]
        result["rows"]      = rows
        result["row_count"] = len(rows)
    except sqlite3.Error as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def read_parsed_items_for_receipt(receipt_id: int) -> dict:
    """Line items for a single receipt — useful for detailed cost breakdown."""
    db = vision_db_path()
    prov = {
        "source":       "x-money-vision-analyzer (read-only)",
        "endpoint":     str(db),
        "retrieved_at": _now_iso(),
        "mode":         "sqlite_readonly_uri",
    }
    result: dict[str, Any] = {
        "installed":   False,
        "receipt_id":  int(receipt_id),
        "items":       [],
        "provenance":  prov,
        "error":       None,
    }
    if not db.exists():
        result["error"] = "Vision Analyzer DB not installed."
        return result
    result["installed"] = True

    try:
        with _open_readonly(db) as conn:
            rows = list(conn.execute(
                "SELECT * FROM parsed_items WHERE receipt_id = ? ORDER BY id",
                (int(receipt_id),),
            ))
        result["items"] = [dict(r) for r in rows]
    except sqlite3.Error as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result
