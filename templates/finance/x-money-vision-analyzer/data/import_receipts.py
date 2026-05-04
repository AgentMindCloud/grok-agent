# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Cross-tool writer — X Money Vision Analyzer → X Money Companion Dashboard.

This is the ONLY Constitution-permitted write path between Grok Agent OS
tools (Article III). It opens Tool #1's SQLite at the canonical AppData
path and appends rows into ``transactions`` with ``source='vision'`` and
``receipt_image_path`` set to the local image — no other cross-tool writes
are permitted by the manifest.

Public surface:

- ``import_receipts_to_companion(parsed_items, target_db=None)`` — bulk
  import; opens the companion DB read/write, appends one row per parsed
  item, writes a provenance entry to BOTH tools' logs, returns a structured
  result dict (never raises).

The caller (``api_clients.import_to_companion_dashboard``) is responsible
for the Article II consent gate; this module assumes the user has already
approved the action plan.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import (
    companion_db_path,
    companion_provenance_log_path,
    provenance_log_path,
)


# Confidence text → float mapping for Tool #1's transactions.confidence column
# (Tool #1 stores a 0..1 float; Tool #4 stores 'high'/'medium'/'low' text.)
_CONFIDENCE_TO_FLOAT: dict[str, float] = {
    "high":   0.90,
    "medium": 0.65,
    "low":    0.35,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_both_provenance(
    action: str,
    payload: dict,
    *,
    own_log:       Path | None = None,
    companion_log: Path | None = None,
) -> None:
    """Append one JSON line to BOTH provenance logs in lock-step.

    Best-effort — disk errors on either log do not break the import. Both
    sides matter: the analyzer needs to know what it wrote, the dashboard
    needs to know what was written into it.
    """
    own_log       = own_log       or provenance_log_path()
    companion_log = companion_log or companion_provenance_log_path()
    entry = {
        "timestamp": _now_iso(),
        "action":    action,
        **payload,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    for path in (own_log, companion_log):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            # Provenance is best-effort; an unwritable log must not block the import.
            pass


def _validate_companion_schema(conn: sqlite3.Connection) -> str | None:
    """Return None if Tool #1's transactions table has the expected shape,
    or a human-readable error string explaining what's missing.
    """
    try:
        cur = conn.execute("PRAGMA table_info(transactions)")
        cols = {row[1] for row in cur.fetchall()}
    except sqlite3.Error as e:
        return f"Could not read companion `transactions` schema: {e}"

    needed = {
        "tx_date", "amount", "currency", "counterparty", "memo",
        "category", "confidence", "source", "raw_data", "receipt_image_path",
    }
    missing = needed - cols
    if missing:
        return (
            f"Companion DB schema is missing required column(s): "
            f"{sorted(missing)}. Re-install Tool #1 to refresh the schema."
        )
    return None


def import_receipts_to_companion(
    parsed_items: list[dict],
    *,
    target_db: Path | None = None,
) -> dict:
    """Bulk-import parsed receipts into Tool #1's transactions table.

    Each ``parsed_item`` should match the JSON shape from
    ``prompts/user_templates.md#parse-receipt`` — at minimum: ``vendor``,
    ``tx_date``, ``total``, plus optional ``currency``, ``category_suggested``,
    ``confidence``, ``provenance.image_path``, ``notes``.

    Behaviour:
    - Receipts are outflows by default — ``transactions.amount`` is set to
      ``-abs(total)``. (Receipts that are actually refunds can be edited
      after import.)
    - Idempotent on ``receipt_image_path``: if a transaction with the same
      image path already exists in the companion DB, the new row is skipped
      and reported in the result.
    - Best-effort provenance: a JSON entry is appended to BOTH the
      analyzer's and Tool #1's ``provenance.log`` for every successful write.
    - Never raises: on any failure the dict's ``error`` field is set.
    """
    db = Path(target_db) if target_db else companion_db_path()
    started = _now_iso()

    result: dict[str, Any] = {
        "started_at":     started,
        "target_db":      str(db),
        "requested":      len(parsed_items),
        "imported":       0,
        "skipped":        0,
        "failed":         0,
        "imported_rows":  [],     # list of {parsed_image_path, target_tx_id}
        "skipped_rows":   [],     # list of {parsed_image_path, reason}
        "failed_rows":    [],     # list of {parsed_image_path, error}
        "error":          None,
    }

    if not db.exists():
        result["error"] = (
            f"Companion DB not found at {db}. "
            "Install x-money-companion-dashboard first."
        )
        _log_both_provenance(
            "import_to_companion_dashboard.preflight",
            {"status": "abort", "reason": result["error"]},
        )
        return result

    try:
        conn = sqlite3.connect(str(db))
    except sqlite3.Error as e:
        result["error"] = f"Could not open companion DB: {e}"
        return result

    try:
        schema_err = _validate_companion_schema(conn)
        if schema_err:
            result["error"] = schema_err
            _log_both_provenance(
                "import_to_companion_dashboard.preflight",
                {"status": "abort", "reason": schema_err},
            )
            return result

        for item in parsed_items:
            image_path = (item.get("provenance") or {}).get("image_path") \
                         or item.get("image_path")

            # Dedup on receipt_image_path
            if image_path:
                exists = conn.execute(
                    "SELECT id FROM transactions WHERE receipt_image_path = ? LIMIT 1",
                    (image_path,),
                ).fetchone()
                if exists:
                    result["skipped"] += 1
                    result["skipped_rows"].append({
                        "image_path": image_path,
                        "reason":     f"already imported as transactions.id={exists[0]}",
                    })
                    continue

            try:
                tx_date  = item.get("tx_date") or ""
                vendor   = item.get("vendor") or ""
                memo     = item.get("notes") or ""
                category = item.get("category_suggested") or item.get("category") or "other"
                currency = item.get("currency") or "USD"
                total    = float(item.get("total") or 0)
                amount   = -abs(total)  # receipts default to outflows
                conf     = (item.get("confidence") or "low").lower()
                conf_num = _CONFIDENCE_TO_FLOAT.get(conf, 0.35)

                raw_blob = json.dumps({
                    "parsed_receipt": item,
                    "imported_via":   "x-money-vision-analyzer/data/import_receipts.py",
                    "imported_at":    _now_iso(),
                }, ensure_ascii=False)

                cur = conn.execute(
                    """
                    INSERT INTO transactions
                        (tx_date, amount, currency, counterparty, memo,
                         category, confidence, source, raw_data, receipt_image_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'vision', ?, ?)
                    """,
                    (tx_date, amount, currency, vendor, memo,
                     category, conf_num, raw_blob, image_path),
                )
                tx_id = int(cur.lastrowid)
                result["imported"] += 1
                result["imported_rows"].append({
                    "image_path":    image_path,
                    "target_tx_id":  tx_id,
                    "amount":        amount,
                    "tx_date":       tx_date,
                    "vendor":        vendor,
                    "category":      category,
                })

                _log_both_provenance(
                    "import_to_companion_dashboard.row",
                    {
                        "status":         "ok",
                        "target_tx_id":   tx_id,
                        "image_path":     image_path,
                        "tx_date":        tx_date,
                        "vendor":         vendor,
                        "amount":         amount,
                        "currency":       currency,
                        "category":       category,
                        "confidence":     conf,
                        "source":         "vision",
                    },
                )
            except sqlite3.Error as e:
                result["failed"] += 1
                result["failed_rows"].append({
                    "image_path": image_path,
                    "error":      f"{type(e).__name__}: {e}",
                })

        conn.commit()
    finally:
        conn.close()

    _log_both_provenance(
        "import_to_companion_dashboard.summary",
        {
            "imported":  result["imported"],
            "skipped":   result["skipped"],
            "failed":    result["failed"],
            "target_db": str(db),
        },
    )
    return result
