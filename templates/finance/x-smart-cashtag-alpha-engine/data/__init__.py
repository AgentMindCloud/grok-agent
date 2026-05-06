# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Data package for the X Smart Cashtag Alpha Engine.

Single source of truth for the AppData path resolver and the SQLite layer.
The Streamlit app (``app.py``), the Grok tool layer, and any sibling tool
that wants to read this engine's alpha-report or watchlist history use this
package.

Built for xAI, X, Grok and the ecosystem community. ❤️
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["appdata_root", "db_path", "provenance_log_path"]


def appdata_root() -> Path:
    """Resolve the local-first data folder for this engine.

    Production target is Windows 11 + PowerShell, where this resolves to
    ``$env:LOCALAPPDATA\\grok-agent\\x-smart-cashtag-alpha-engine``. On
    non-Windows runs (Streamlit Cloud, dev containers, CI) we fall back to
    ``~/.local/share/grok-agent/x-smart-cashtag-alpha-engine`` so the data
    layer boots cleanly everywhere.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-smart-cashtag-alpha-engine"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-smart-cashtag-alpha-engine"


def db_path() -> Path:
    """Canonical SQLite path for this engine."""
    return appdata_root() / "data.db"


def provenance_log_path() -> Path:
    """Append-only provenance log per Constitution Article IV."""
    return appdata_root() / "provenance.log"
