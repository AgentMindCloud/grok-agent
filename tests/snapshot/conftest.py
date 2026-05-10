# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Shared fixtures for syrupy snapshot tests of the Super Agent stub
outputs.

Built for xAI, X, Grok and the ecosystem community.

Snapshots are deterministic by construction: we strip every field that
naturally drifts between runs (timestamps, run_ids, ULIDs, file paths
that include ``$env:LOCALAPPDATA``, git SHAs) before serialising. If
``syrupy`` isn't installed the whole module is skipped via
``pytest.importorskip``.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

# Skip the module if syrupy is missing.
syrupy = pytest.importorskip("syrupy")


# --------------------------------------------------------------------------
# Field names whose values are non-deterministic. Stripped recursively from
# every dict before snapshotting. Listed explicitly so future drift is
# easy to add — never use a wildcard like "anything that looks random".
# --------------------------------------------------------------------------
_VOLATILE_KEYS: frozenset[str] = frozenset(
    {
        "run_id",
        "version_id",
        "parent_version_id",
        "started_at",
        "finished_at",
        "computed_at",
        "timestamp",
        "ts",
        "created_at",
        "updated_at",
        "log_path",
        "appdata_root",
        "git_sha",
        "commit_sha",
    }
)


# Patterns we strip from any string value (timestamps, ULIDs, hex SHAs).
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_ULID_RE = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
_HEX_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def _scrub_string(s: str) -> str:
    s = _TIMESTAMP_RE.sub("<TIMESTAMP>", s)
    s = _ULID_RE.sub("<ULID>", s)
    # Hex-SHA scrub is intentionally scoped to long runs of hex so we don't
    # eat ordinary identifiers like "abc123".
    s = _HEX_SHA_RE.sub("<SHA>", s)
    return s


def _scrub(obj: Any) -> Any:
    """Recursively scrub volatile keys + value patterns from ``obj``.

    Returns a deep copy with:
    - any key in ``_VOLATILE_KEYS`` replaced by ``"<SCRUBBED>"``
    - any string matching a timestamp/ULID/hex-SHA pattern normalised
    - lists + tuples + dicts preserved in their structure
    """
    if isinstance(obj, dict):
        return {
            k: ("<SCRUBBED>" if k in _VOLATILE_KEYS else _scrub(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub(v) for v in obj)
    if isinstance(obj, str):
        return _scrub_string(obj)
    return obj


@pytest.fixture(scope="session")
def deterministic_serializer():
    """Return a callable that scrubs a payload for stable snapshotting."""
    return _scrub
