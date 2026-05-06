# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""SQLite store for the X Money Vision Analyzer.

Owns the canonical schema (5 tables: ``schema_meta``, ``receipts``,
``parsed_items``, ``contradictions``, ``import_log``), an idempotent
migration runner, CRUD helpers, and three of the five manifest-declared
tool functions: ``parse_receipt``, ``validate_extraction``, and
``categorize_parsed_receipt``. The other two (``parse_statement`` and
``import_to_companion_dashboard``) live in ``api_clients.py`` next to
the Grok 4.3 vision stub.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import appdata_root, db_path, receipts_dir
from .api_clients import _grok_vision_call


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path            TEXT    NOT NULL UNIQUE,
    file_hash            TEXT,
    file_size_bytes      INTEGER,
    file_format          TEXT,
    uploaded_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    vendor               TEXT,
    tx_date              TEXT,
    currency             TEXT,
    subtotal             REAL,
    tax                  REAL,
    total                REAL,
    category_suggested   TEXT,
    confidence           TEXT    CHECK (confidence IN ('high','medium','low')),
    confidence_reason    TEXT,
    notes                TEXT,
    status               TEXT    NOT NULL DEFAULT 'parsed'
                          CHECK (status IN ('parsed','imported','import_pending',
                                            'failed_low_confidence','discarded')),
    last_parsed_at       TEXT,
    vision_passes_count  INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT
);
CREATE INDEX IF NOT EXISTS idx_receipts_status   ON receipts(status);
CREATE INDEX IF NOT EXISTS idx_receipts_vendor   ON receipts(vendor);
CREATE INDEX IF NOT EXISTS idx_receipts_date     ON receipts(tx_date);

CREATE TABLE IF NOT EXISTS parsed_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id  INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    item_name   TEXT    NOT NULL,
    qty         REAL    NOT NULL DEFAULT 1.0,
    price       REAL    NOT NULL,
    confidence  TEXT    CHECK (confidence IN ('high','medium','low')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_parsed_items_receipt ON parsed_items(receipt_id);

CREATE TABLE IF NOT EXISTS contradictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id    INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    field         TEXT    NOT NULL,
    pass_1_value  TEXT    NOT NULL,
    pass_2_value  TEXT    NOT NULL,
    delta_summary TEXT    NOT NULL,
    severity      TEXT    NOT NULL CHECK (severity IN ('info','warn','error')),
    detected_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_at   TEXT,
    resolution    TEXT
);
CREATE INDEX IF NOT EXISTS idx_contradictions_receipt ON contradictions(receipt_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_severity ON contradictions(severity);

CREATE TABLE IF NOT EXISTS import_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id    INTEGER NOT NULL REFERENCES receipts(id),
    target_db     TEXT    NOT NULL,
    target_tx_id  INTEGER,
    imported_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    status        TEXT    NOT NULL DEFAULT 'success'
                    CHECK (status IN ('success','failed','rolled_back')),
    error_message TEXT,
    consent_user  TEXT
);
CREATE INDEX IF NOT EXISTS idx_import_log_receipt ON import_log(receipt_id);
"""


# --- Connection + migrations ----------------------------------------------

def init_db(path: Path | None = None) -> Path:
    """Create the database and run idempotent migrations."""
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    receipts_dir().mkdir(parents=True, exist_ok=True)
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


# --- Receipts CRUD --------------------------------------------------------

def upsert_receipt_from_extraction(image_path: str, extraction: dict) -> int:
    """Persist (or update) a receipt row from a Grok extraction dict."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM receipts WHERE file_path = ?", (image_path,)
        ).fetchone()
        prov = extraction.get("provenance") or {}
        line_items = extraction.get("line_items") or []

        fields = (
            extraction.get("vendor"),
            extraction.get("tx_date"),
            extraction.get("currency") or "USD",
            extraction.get("subtotal"),
            extraction.get("tax"),
            extraction.get("total"),
            extraction.get("category_suggested"),
            (extraction.get("confidence") or "low").lower(),
            extraction.get("confidence_reason"),
            extraction.get("notes"),
            "parsed",
            _now_iso(),
            int(prov.get("vision_pass_index") or 1),
        )

        if existing:
            rid = int(existing[0])
            conn.execute(
                """
                UPDATE receipts SET
                    vendor=?, tx_date=?, currency=?, subtotal=?, tax=?, total=?,
                    category_suggested=?, confidence=?, confidence_reason=?, notes=?,
                    status=?, last_parsed_at=?, vision_passes_count=?,
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (*fields, rid),
            )
            # Refresh line items: replace the receipt's items with the new set
            conn.execute("DELETE FROM parsed_items WHERE receipt_id = ?", (rid,))
        else:
            cur = conn.execute(
                """
                INSERT INTO receipts
                    (file_path, vendor, tx_date, currency, subtotal, tax, total,
                     category_suggested, confidence, confidence_reason, notes,
                     status, last_parsed_at, vision_passes_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (image_path, *fields),
            )
            rid = int(cur.lastrowid)

        for li in line_items:
            conn.execute(
                "INSERT INTO parsed_items (receipt_id, item_name, qty, price, confidence) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    rid,
                    li.get("item") or li.get("item_name") or "",
                    float(li.get("qty") or 1.0),
                    float(li.get("price") or 0.0),
                    (li.get("confidence") or "medium").lower(),
                ),
            )
        conn.commit()
        return rid


def get_receipt(receipt_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["line_items"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM parsed_items WHERE receipt_id = ? ORDER BY id",
                (receipt_id,),
            )
        ]
        d["contradictions"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM contradictions WHERE receipt_id = ? ORDER BY detected_at DESC",
                (receipt_id,),
            )
        ]
        return d


def list_receipts(
    status: str | None = None, limit: int | None = None
) -> list[dict]:
    sql = "SELECT * FROM receipts"
    args: list[Any] = []
    if status:
        sql += " WHERE status = ?"; args.append(status)
    sql += " ORDER BY uploaded_at DESC"
    if limit:
        sql += " LIMIT ?"; args.append(limit)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def update_receipt_status(receipt_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE receipts SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, receipt_id),
        )
        conn.commit()


# --- Contradictions CRUD --------------------------------------------------

def insert_contradiction(
    *, receipt_id: int, field: str, pass_1_value: Any, pass_2_value: Any,
    delta_summary: str, severity: str,
) -> int:
    if severity not in ("info", "warn", "error"):
        raise ValueError(f"severity must be info|warn|error, got {severity!r}")
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO contradictions
                (receipt_id, field, pass_1_value, pass_2_value, delta_summary, severity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id, field,
                json.dumps(pass_1_value, ensure_ascii=False, default=str),
                json.dumps(pass_2_value, ensure_ascii=False, default=str),
                delta_summary, severity,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


# --- Import log CRUD ------------------------------------------------------

def insert_import_log(
    *,
    receipt_id:    int,
    target_db:     str,
    target_tx_id:  int | None,
    status:        str = "success",
    error_message: str | None = None,
    consent_user:  str | None = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO import_log
                (receipt_id, target_db, target_tx_id, status, error_message, consent_user)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (receipt_id, target_db, target_tx_id, status, error_message, consent_user),
        )
        conn.commit()
        return int(cur.lastrowid)


# --- Helpers --------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Keyword heuristic for the categorize_parsed_receipt baseline. Same vocabulary
# as Tool #1's categorize_transaction (P22) so cross-tool import is a clean
# append rather than a translation step.
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


# --- Manifest tool: parse_receipt -----------------------------------------

def parse_receipt(image_path: str, **_: Any) -> dict:
    """Manifest tool — parse one receipt image and persist."""
    extraction = _grok_vision_call(image_path, mode="receipt", vision_pass_index=1)
    rid = upsert_receipt_from_extraction(image_path, extraction)
    return {
        "id":         rid,
        "image_path": image_path,
        "extraction": extraction,
        "stored_at":  _now_iso(),
    }


# --- Manifest tool: validate_extraction -----------------------------------

def validate_extraction(image_path: str, parsed_result: dict, **_: Any) -> dict:
    """Manifest tool — second vision pass + persist contradictions.

    Compares the new extraction's ``vendor``, ``tx_date``, and ``total``
    against ``parsed_result`` and writes one row to ``contradictions`` per
    disagreement. Article III: the user sees BOTH readings — never resolved
    silently.
    """
    rid = parsed_result.get("id") or upsert_receipt_from_extraction(image_path, parsed_result)
    pass_2 = _grok_vision_call(image_path, mode="receipt", vision_pass_index=2)

    contradictions: list[dict] = []
    for field in ("vendor", "tx_date", "total"):
        v1 = parsed_result.get(field)
        v2 = pass_2.get(field)
        if v1 == v2:
            continue
        # Severity heuristic: tax-relevant fields default to error; other → warn.
        if field == "total":
            try:
                delta = abs(float(v1 or 0) - float(v2 or 0))
                severity = "warn" if delta <= 0.10 else "error"
                summary = f"total drift ${delta:.2f}"
            except (TypeError, ValueError):
                severity, summary = "error", f"total values incomparable: {v1!r} vs {v2!r}"
        elif field == "tx_date":
            severity = "error"
            summary  = f"tx_date drift: {v1!r} vs {v2!r}"
        elif field == "vendor":
            if isinstance(v1, str) and isinstance(v2, str) and v1.lower() == v2.lower():
                severity, summary = "info", "vendor capitalisation only"
            else:
                severity, summary = "warn", f"vendor mismatch: {v1!r} vs {v2!r}"
        else:
            severity, summary = "warn", f"{field} differs"

        contradictions.append({
            "field":         field,
            "claim_a":       {"source": "vision-pass-1", "value": v1},
            "claim_b":       {"source": "vision-pass-2", "value": v2},
            "delta_summary": summary,
            "severity":      severity,
        })
        insert_contradiction(
            receipt_id=int(rid), field=field,
            pass_1_value=v1, pass_2_value=v2,
            delta_summary=summary, severity=severity,
        )

    # Recommendation: any error → review; only warn/info → import OK
    if any(c["severity"] == "error" for c in contradictions):
        recommend = "review"
    elif any(c["severity"] == "warn" for c in contradictions):
        recommend = "review"
    else:
        recommend = "import"

    return {
        "image_path":     image_path,
        "receipt_id":     int(rid),
        "pass_1":         {k: parsed_result.get(k) for k in ("vendor","tx_date","total")},
        "pass_2":         {k: pass_2.get(k)         for k in ("vendor","tx_date","total")},
        "contradictions": contradictions,
        "verdict":        f"{len(contradictions)} disagreement(s) detected",
        "recommend":      recommend,
        "confidence":     "low" if recommend == "review" else parsed_result.get("confidence", "medium"),
        "provenance":     pass_2.get("provenance"),
    }


# --- Manifest tool: categorize_parsed_receipt -----------------------------

def categorize_parsed_receipt(parsed_receipt: dict, **_: Any) -> dict:
    """Manifest tool — assign a category to a parsed receipt.

    Keyword-heuristic baseline matching Tool #1's vocabulary. The Grok
    categorizer wires in a later prompt; this body keeps the dashboard
    deterministic and offline-safe for now.
    """
    vendor = (parsed_receipt.get("vendor") or "").lower()
    notes  = (parsed_receipt.get("notes")  or "").lower()
    items  = " ".join(
        (li.get("item") or li.get("item_name") or "")
        for li in (parsed_receipt.get("line_items") or [])
    ).lower()
    text = f"{vendor} {notes} {items}"

    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in text for k in keywords):
            return {
                "category":            category,
                "confidence":          "medium",
                "reasoning":           f"Keyword hit on vendor/items: '{parsed_receipt.get('vendor')}'.",
                "clarifying_question": "",
            }

    return {
        "category":            "other",
        "confidence":          "low",
        "reasoning":           "No keyword hit on vendor / items / notes.",
        "clarifying_question": (
            f"What category best fits a {parsed_receipt.get('total')} "
            f"{parsed_receipt.get('currency','USD')} receipt from "
            f"'{parsed_receipt.get('vendor')}'?"
        ),
    }
