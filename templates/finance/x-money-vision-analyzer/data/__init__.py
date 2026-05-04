# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Data package for the X Money Vision Analyzer.

Single source of truth for the AppData path resolvers (this tool AND
Tool #1's cross-tool target), the SQLite layer, and the cross-tool
writer ``data/import_receipts.py`` that is the only Constitution-permitted
write path into the X Money Companion Dashboard.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "appdata_root", "db_path", "receipts_dir", "provenance_log_path",
    "companion_appdata_root", "companion_db_path", "companion_provenance_log_path",
]


def appdata_root() -> Path:
    """Resolve this tool's local-first data folder.

    Production target is Windows 11 + PowerShell, where this resolves to
    ``$env:LOCALAPPDATA\\grok-agent\\x-money-vision-analyzer``. On
    non-Windows runs we fall back to ``~/.local/share/...`` so the
    skeleton boots cleanly everywhere.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-vision-analyzer"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-money-vision-analyzer"


def db_path() -> Path:
    """Canonical SQLite path for this tool."""
    return appdata_root() / "data.db"


def receipts_dir() -> Path:
    """Local folder where user-dropped receipt images live."""
    return appdata_root() / "receipts"


def provenance_log_path() -> Path:
    """This tool's append-only provenance log per Constitution Article IV."""
    return appdata_root() / "provenance.log"


# --- Cross-tool target: X Money Companion Dashboard (Tool #1) -------------

def companion_appdata_root() -> Path:
    """Tool #1's AppData root — the cross-tool write target."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-money-companion-dashboard"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-money-companion-dashboard"


def companion_db_path() -> Path:
    """Tool #1's SQLite path — the cross-tool write target."""
    return companion_appdata_root() / "data.db"


def companion_provenance_log_path() -> Path:
    """Tool #1's append-only provenance log — written to in lock-step on every cross-tool import."""
    return companion_appdata_root() / "provenance.log"
