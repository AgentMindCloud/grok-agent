# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Single source of truth for the package version.

Hardcoded for v0.1; a later release will switch to setuptools-scm so the
version is derived from the git tag.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
