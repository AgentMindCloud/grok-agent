# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Provenance package for the Self-Evolving Personal OS (P124).

Two modules:

- :mod:`provenance.log`             local-first JSONL audit logger +
                                    Markdown report exporter
- :mod:`provenance.langfuse_hooks`  optional Langfuse observability with
                                    full stub fallback

The package re-exports the most-used names so callers can write
``from provenance import LocalProvenanceLogger`` rather than chasing the
deeper module paths.

Built to help xAI and Grok win.
"""

from __future__ import annotations

from provenance.log import (  # type: ignore  # noqa: F401
    LocalProvenanceLogger,
    ProvenanceRecord,
    current_log_path,
    export_audit_report,
    get_default_logger,
    log_path_for,
    make_run_id,
    provenance_root,
    reset_default_logger,
    summarise_run,
)
from provenance.langfuse_hooks import (  # type: ignore  # noqa: F401
    LangfuseClient,
    LangfuseTraceContext,
    get_langfuse_client,
    reset_langfuse_client,
    span_from_record,
    stub_trace_path,
)
from provenance.langfuse_hooks import BACKEND_NAME as LANGFUSE_BACKEND_NAME  # type: ignore  # noqa: F401,E501

__all__ = [
    # log
    "LocalProvenanceLogger",
    "ProvenanceRecord",
    "current_log_path",
    "export_audit_report",
    "get_default_logger",
    "log_path_for",
    "make_run_id",
    "provenance_root",
    "reset_default_logger",
    "summarise_run",
    # langfuse
    "LangfuseClient",
    "LangfuseTraceContext",
    "get_langfuse_client",
    "reset_langfuse_client",
    "span_from_record",
    "stub_trace_path",
    "LANGFUSE_BACKEND_NAME",
]
