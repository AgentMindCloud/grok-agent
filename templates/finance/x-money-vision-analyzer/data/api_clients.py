# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Public-API + Grok-vision client wrappers for the X Money Vision Analyzer.

Owns:

- ``_grok_vision_call(image_path, mode, vision_pass_index)`` — Grok 4.3 vision
  STUB matching the JSON schemas in ``prompts/user_templates.md`` so the
  surrounding pipeline persists structurally-valid rows today; the real
  Grok client wires in a later prompt.
- Two manifest tools:
    * ``parse_statement(image_paths)``         — multi-page statement → JSON
    * ``import_to_companion_dashboard(...)``    — Article II consent-gated
      cross-tool write into Tool #1's SQLite via
      ``import_receipts.import_receipts_to_companion``.
- Per-source rate limiter and append-only provenance writer.

Every call returns a dict with a ``provenance`` block (Constitution
Article IV) and an ``error`` field; failures never raise.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from . import provenance_log_path
from .import_receipts import import_receipts_to_companion


_USER_AGENT = "grok-agent/x-money-vision-analyzer (Apache-2.0)"


# --- Rate limiter (process-local) -----------------------------------------

class _RateLimiter:
    def __init__(self) -> None:
        self._last_call: dict[str, float] = {}

    def throttle(self, source: str, min_interval_s: float = 0.5) -> None:
        last = self._last_call.get(source, 0.0)
        wait = min_interval_s - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_call[source] = time.monotonic()


_RATE = _RateLimiter()


# --- Provenance helpers ---------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provenance(source: str, endpoint: str, cost_usd: float = 0.0, **extra: Any) -> dict:
    return {
        "source":       source,
        "endpoint":     endpoint,
        "retrieved_at": _now_iso(),
        "cost_usd":     cost_usd,
        **extra,
    }


def _log_provenance(action: str, prov: dict, payload_summary: dict | None = None) -> None:
    log_path = provenance_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": prov.get("retrieved_at", _now_iso()),
        "action":    action,
        **prov,
        "payload":   payload_summary or {},
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


# --- Grok 4.3 vision STUB -------------------------------------------------

def _grok_vision_call(
    image_path: str,
    *,
    mode: str = "receipt",
    vision_pass_index: int = 1,
) -> dict:
    """STUB — Grok 4.3 vision parser.

    Returns a dict matching the JSON schemas in
    ``prompts/user_templates.md#parse-receipt`` (mode='receipt') or
    ``#parse-statement`` (mode='statement'), so the surrounding store /
    importer can persist structurally-valid rows today. The real Grok
    client wires in a later prompt — until then the result is flagged
    ``provenance.stub: True`` and ``confidence: "low"`` so Article IV
    stays honest.
    """
    _RATE.throttle("grok-vision", min_interval_s=0.5)
    prov = _provenance(
        source="grok-4.3-vision (stub)",
        endpoint="via_grok_4.3 vision tool-call",
        cost_usd=0.0,
        stub=True,
    )

    if mode == "receipt":
        result: dict[str, Any] = {
            "vendor":             "Stub Vendor",
            "tx_date":            datetime.now(timezone.utc).date().isoformat(),
            "currency":           "USD",
            "subtotal":           0.0,
            "tax":                0.0,
            "total":              0.0,
            "line_items":         [],
            "category_suggested": "other",
            "confidence":         "low",
            "confidence_reason": (
                "Grok 4.3 vision client is stubbed in P34; real parsing "
                "ships in a later prompt."
            ),
            "notes":              f"STUB extraction for {image_path}",
            "provenance": {
                "image_path":         image_path,
                "page":               1,
                "model":              "grok-4.3-vision (stub)",
                "vision_pass_index":  int(vision_pass_index),
                "retrieved_at":       _now_iso(),
                "stub":               True,
                "redaction_applied":  True,
            },
        }
    elif mode == "statement":
        result = {
            "issuer":            "Stub Issuer",
            "statement_date":    datetime.now(timezone.utc).date().isoformat(),
            "period_start":      datetime.now(timezone.utc).date().isoformat(),
            "period_end":        datetime.now(timezone.utc).date().isoformat(),
            "currency":          "USD",
            "transactions":      [],
            "totals":            {"inflow": 0.0, "outflow": 0.0, "net": 0.0},
            "confidence":        "low",
            "confidence_reason": (
                "Grok 4.3 vision client is stubbed in P34; real statement "
                "parsing ships in a later prompt."
            ),
            "provenance": {
                "image_paths":        [image_path],
                "model":              "grok-4.3-vision (stub)",
                "vision_pass_index":  int(vision_pass_index),
                "retrieved_at":       _now_iso(),
                "stub":               True,
            },
        }
    else:
        result = {
            "error":      f"Unknown mode '{mode}'. Use 'receipt' or 'statement'.",
            "provenance": prov,
        }

    _log_provenance(
        "grok_vision_call", prov,
        {"image_path": image_path, "mode": mode,
         "vision_pass_index": int(vision_pass_index),
         "confidence": result.get("confidence")},
    )
    return result


# --- Manifest tool: parse_statement ---------------------------------------

def parse_statement(image_paths: list[str]) -> dict:
    """Parse a multi-page statement (image series or PDF pages already split).

    Each page goes through ``_grok_vision_call(mode='statement')``; the
    result is the per-statement aggregate. Today the underlying Grok call
    is a stub, so the returned shape is structurally valid but reports
    ``confidence: "low"`` and ``stub: True`` in provenance.
    """
    started = _now_iso()
    pages: list[dict] = []
    for p in image_paths:
        pages.append(_grok_vision_call(p, mode="statement", vision_pass_index=1))

    aggregated: dict[str, Any] = {
        "image_paths":   list(image_paths),
        "page_count":    len(image_paths),
        "issuer":        pages[0].get("issuer") if pages else None,
        "currency":      pages[0].get("currency") if pages else "USD",
        "transactions":  [],
        "page_results":  pages,
        "started_at":    started,
        "confidence":    "low",
        "provenance": {
            "source":             "grok-4.3-vision (stub)",
            "endpoint":           "via_grok_4.3 vision tool-call",
            "retrieved_at":       _now_iso(),
            "vision_pass_index":  1,
            "stub":               True,
        },
        "error":         None,
    }
    return aggregated


# --- Manifest tool: import_to_companion_dashboard -------------------------

def import_to_companion_dashboard(parsed_items: list[dict], **_: Any) -> dict:
    """Manifest tool — write parsed receipts into Tool #1's SQLite.

    CONSENT-GATED: the caller (UI / Grok runtime) must have already presented
    the action plan to the user and received explicit approval before invoking
    this. This function does NOT implement the consent UI itself — it only
    delegates to ``import_receipts.import_receipts_to_companion`` after
    checking the input is non-empty.
    """
    prov = _provenance(
        source="x-money-vision-analyzer/import_to_companion_dashboard",
        endpoint="data/import_receipts.py",
        cost_usd=0.0,
    )
    if not parsed_items:
        result = {
            "imported":  0,
            "requested": 0,
            "skipped":   0,
            "failed":    0,
            "error":     "No parsed_items provided — nothing to import.",
            "provenance": prov,
        }
        _log_provenance("import_to_companion_dashboard", prov, {"status": "noop"})
        return result

    raw = import_receipts_to_companion(parsed_items)
    raw["provenance"] = prov
    _log_provenance(
        "import_to_companion_dashboard", prov,
        {"requested": raw.get("requested"),
         "imported":  raw.get("imported"),
         "skipped":   raw.get("skipped"),
         "failed":    raw.get("failed")},
    )
    return raw
