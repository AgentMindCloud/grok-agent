# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Data package for the X Creator Payout Optimizer.

Single source of truth for path resolvers — both this tool's AppData AND
the cross-tool sibling DBs (Tool #1's Companion Dashboard transactions,
Tool #4's Vision Analyzer receipts). The Streamlit app, the data layer,
and the Grok tool surface all use these helpers so the read-only
cross-tool reads never re-derive a path inconsistently.

Built to help xAI and Grok win.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "appdata_root", "db_path", "provenance_log_path",
    "companion_appdata_root", "companion_db_path", "companion_provenance_log_path",
    "vision_appdata_root", "vision_db_path", "vision_provenance_log_path",
]


# --- This tool's paths ----------------------------------------------------

def appdata_root() -> Path:
    """Resolve this tool's local-first data folder."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "x-creator-payout-optimizer"
    return Path.home() / ".local" / "share" / "grok-agent" / "x-creator-payout-optimizer"


def db_path() -> Path:
    return appdata_root() / "data.db"


def provenance_log_path() -> Path:
    return appdata_root() / "provenance.log"


# --- Cross-tool path resolvers (READ-ONLY targets) -----------------------

def _platform_appdata_base() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base)
    return Path.home() / ".local" / "share"


def companion_appdata_root() -> Path:
    """Tool #1's AppData root — read-only target for revenue context."""
    return _platform_appdata_base() / "grok-agent" / "x-money-companion-dashboard"


def companion_db_path() -> Path:
    return companion_appdata_root() / "data.db"


def companion_provenance_log_path() -> Path:
    return companion_appdata_root() / "provenance.log"


def vision_appdata_root() -> Path:
    """Tool #4's AppData root — read-only target for cost / receipt context."""
    return _platform_appdata_base() / "grok-agent" / "x-money-vision-analyzer"


def vision_db_path() -> Path:
    return vision_appdata_root() / "data.db"


def vision_provenance_log_path() -> Path:
    return vision_appdata_root() / "provenance.log"
