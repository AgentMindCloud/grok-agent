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
"""Local-first JSONL provenance logger for the Self-Evolving Personal OS.

This module is the **audit-trail layer** of Super Agent #2. It captures one
:class:`ProvenanceRecord` per node execution per run and appends it to a
date-rolled JSONL file under the user's Windows AppData folder. Together
with the trail already written by P123's ``output_with_provenance`` node,
this gives the user a complete, queryable, replayable record of every
decision the agent made.

Local-first by design:

- One JSONL file per UTC day at
  ``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\provenance\\
  YYYY-MM-DD.jsonl``.
- Append-only — the logger never opens an existing file in write mode.
- PII redacted at write time via :func:`connectors.redact_pii` (the same
  engine P121 / P122 use).
- Pure-Python: no external service is contacted from this module. Cloud
  observability is opt-in and lives in :mod:`provenance.langfuse_hooks`.

Public surface:

- :class:`ProvenanceRecord`  the structured row schema
- :class:`LocalProvenanceLogger`  the append + query API
- :func:`get_default_logger`  process-wide cached singleton
- :func:`export_audit_report`  Markdown report for one date / run / source

Built to help xAI and Grok win — provenance is what turns a Super Agent
from a chatbot into something the user can trust at the OS level.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Reuse P121 primitives.  Absolute import because the parent folder name
# ``self-evolving-personal-os`` contains hyphens.
from connectors import (  # type: ignore
    appdata_root,
    redact_pii,
)

__all__ = [
    "ProvenanceRecord",
    "LocalProvenanceLogger",
    "provenance_root",
    "current_log_path",
    "log_path_for",
    "get_default_logger",
    "reset_default_logger",
    "export_audit_report",
    "summarise_run",
    "make_run_id",
]


# --- Section 1. Constants and paths ---------------------------------------

CONFIDENCE_LEVELS: tuple[str, ...] = ("low", "medium", "high")
_ISO_FMT = "%Y-%m-%d"


def provenance_root() -> Path:
    """Filesystem location for the daily JSONL files."""
    return appdata_root() / "provenance"


def log_path_for(date_iso: str) -> Path:
    """Path of the JSONL file for one UTC day (``YYYY-MM-DD``)."""
    safe = "".join(c for c in date_iso if c.isdigit() or c == "-")
    if not safe:
        raise ValueError(f"invalid date_iso: {date_iso!r}")
    return provenance_root() / f"{safe}.jsonl"


def current_log_path() -> Path:
    """Path of the JSONL file for today (UTC)."""
    return log_path_for(datetime.now(timezone.utc).strftime(_ISO_FMT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    """One run = one CLI invocation = one full graph traversal."""
    return f"run-{uuid.uuid4().hex[:12]}"


# Match only date-named files (YYYY-MM-DD.jsonl) so the LocalProvenanceLogger
# never accidentally parses sibling files in the same dir (e.g. the Langfuse
# stub trace ``langfuse_stub_trace.jsonl``).
import re as _re  # noqa: E402  — local-only helper
_DATE_FILENAME_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}\.jsonl$")


def _date_jsonl_files(root: Path) -> list[Path]:
    """List date-named JSONL files in the provenance dir."""
    try:
        return sorted(
            p for p in root.glob("*.jsonl")
            if _DATE_FILENAME_RE.match(p.name)
        )
    except OSError:
        return []


# --- Section 2. ProvenanceRecord schema ----------------------------------

@dataclass
class ProvenanceRecord:
    """One JSONL row.  Schema is intentionally tight and stable.

    Every per-node trace conforms to this dataclass. The brief's final
    output dict embeds a list of these as ``output.provenance.trail`` (in
    its compact form), and this logger persists the full version to disk.
    """

    record_id:        str
    run_id:           str
    user_id:          str
    node_name:        str
    timestamp:        str
    inputs_redacted:  dict
    outputs_redacted: dict
    sources:          list[str]
    confidence:       str | None         # one of CONFIDENCE_LEVELS or None
    stub_reason:      str | None
    memory_version:   str | None
    duration_ms:      float | None
    error:            str | None
    correlation_id:   str | None
    backend:          str = "local-jsonl"
    schema_version:   str = "p124.v1"
    extra:            dict = field(default_factory=dict)

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)

    @classmethod
    def from_jsonl(cls, line: str) -> "ProvenanceRecord":
        data = json.loads(line)
        return cls(
            record_id=str(data.get("record_id") or ""),
            run_id=str(data.get("run_id") or ""),
            user_id=str(data.get("user_id") or ""),
            node_name=str(data.get("node_name") or ""),
            timestamp=str(data.get("timestamp") or ""),
            inputs_redacted=dict(data.get("inputs_redacted") or {}),
            outputs_redacted=dict(data.get("outputs_redacted") or {}),
            sources=list(data.get("sources") or []),
            confidence=data.get("confidence"),
            stub_reason=data.get("stub_reason"),
            memory_version=data.get("memory_version"),
            duration_ms=data.get("duration_ms"),
            error=data.get("error"),
            correlation_id=data.get("correlation_id"),
            backend=str(data.get("backend") or "local-jsonl"),
            schema_version=str(data.get("schema_version") or "p124.v1"),
            extra=dict(data.get("extra") or {}),
        )


# --- Section 3. Input / output digest helpers ----------------------------

# Keys we never emit verbatim into the JSONL. Either too large (raw items
# are stored elsewhere — Qdrant + the audit DB), or carry runtime objects
# that don't serialise (``_composite``, ``_memory_client``, ``consent``).
_STATE_REDACT_KEYS: frozenset[str] = frozenset({
    "_composite", "_memory_client",
    "consent",
})

#: How many fetched items per source we summarise inline.  Anything beyond
#: this lives only in the connector-level provenance log + Qdrant.
_INLINE_ITEM_LIMIT = 3


def _summarise_state(state: dict) -> dict:
    """Build a redacted, JSON-safe digest of the orchestrator state.

    The output is stored on every record under ``inputs_redacted`` so the
    audit can show what the node saw without bloating the file.
    """
    if not isinstance(state, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in state.items():
        if k in _STATE_REDACT_KEYS:
            continue
        if isinstance(v, dict) and v and k == "fetched":
            digest = {}
            for src, payload in v.items():
                items = (payload or {}).get("items") or []
                digest[src] = {
                    "item_count": len(items),
                    "first_kinds": list({
                        it.get("kind") for it in items[:_INLINE_ITEM_LIMIT]
                        if isinstance(it, dict) and "kind" in it
                    }),
                    "error":      (payload or {}).get("error"),
                    "stub":       bool(((payload or {}).get("provenance") or {})
                                      .get("stub", False)),
                }
            out[k] = digest
        elif isinstance(v, dict):
            out[k] = redact_pii(v)
        elif isinstance(v, list):
            # Only include short / structurally-light lists.
            if len(v) > _INLINE_ITEM_LIMIT * 4:
                out[k] = {"length": len(v), "truncated": True}
            else:
                out[k] = redact_pii(v)
        else:
            out[k] = redact_pii(v)
    return out


def _summarise_update(update: dict) -> dict:
    """Same shape as :func:`_summarise_state` but for the per-node return."""
    return _summarise_state(update)


def _detect_sources(state: dict, update: dict) -> list[str]:
    """Best-effort detection of which source IDs the node touched."""
    out: set[str] = set()
    fetched = update.get("fetched") if isinstance(update, dict) else None
    if isinstance(fetched, dict):
        out.update(str(k) for k in fetched.keys())
    rem = update.get("remembered") if isinstance(update, dict) else None
    if isinstance(rem, dict):
        out.update(str(k) for k in rem.keys())
    if not out:
        # Fall back to whatever was already captured in the prior state.
        f0 = state.get("fetched") if isinstance(state, dict) else None
        if isinstance(f0, dict):
            out.update(str(k) for k in f0.keys())
    return sorted(out)


def _detect_confidence(state: dict, update: dict, *, force_stub: bool) -> str | None:
    """Map state into a tri-state confidence value.

    The rule is deliberately simple so the field stays meaningful:

    - ``low``     when ``force_stub`` is True or any source returned an error
    - ``medium``  when all sources returned non-empty data but at least one
                  carried ``provenance.stub: True``
    - ``high``    everything else
    """
    if force_stub:
        return "low"
    fetched = (update.get("fetched") if isinstance(update, dict) else None) \
        or (state.get("fetched") if isinstance(state, dict) else None) or {}
    if not isinstance(fetched, dict) or not fetched:
        return None
    saw_error = False
    saw_stub  = False
    for payload in fetched.values():
        if not isinstance(payload, dict):
            continue
        if payload.get("error"):
            saw_error = True
        prov = payload.get("provenance") or {}
        if isinstance(prov, dict) and prov.get("stub"):
            saw_stub = True
    if saw_error:
        return "low"
    if saw_stub:
        return "medium"
    return "high"


# --- Section 4. LocalProvenanceLogger ------------------------------------

class LocalProvenanceLogger:
    """Append-only JSONL audit logger.

    Thread-safe (one process-wide lock; SQLite-style write-ahead is
    overkill for daily-rolled append-only JSONL).
    """

    def __init__(
        self,
        *,
        user_id: str = "default",
        run_id: str | None = None,
        root: Path | None = None,
    ) -> None:
        self._user_id = user_id or "default"
        self._run_id  = run_id or make_run_id()
        self._root    = root or provenance_root()
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # -- Identity ----------------------------------------------------------

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def run_id(self) -> str:
        return self._run_id

    def new_run(self, run_id: str | None = None) -> str:
        """Start a fresh run; subsequent log_step calls use the new id."""
        with self._lock:
            self._run_id = run_id or make_run_id()
        return self._run_id

    # -- Write side --------------------------------------------------------

    def log_step(
        self,
        *,
        node_name: str,
        state: dict,
        update: dict,
        force_stub: bool = False,
        duration_ms: float | None = None,
        error: str | None = None,
        correlation_id: str | None = None,
        extra: dict | None = None,
    ) -> ProvenanceRecord:
        """Persist one ProvenanceRecord and return it."""
        sources = _detect_sources(state or {}, update or {})
        confidence = _detect_confidence(state or {}, update or {}, force_stub=force_stub)
        memory_version = (state or {}).get("prompt_version")

        record = ProvenanceRecord(
            record_id=f"prv-{uuid.uuid4().hex[:16]}",
            run_id=self._run_id,
            user_id=self._user_id,
            node_name=str(node_name),
            timestamp=_now_iso(),
            inputs_redacted=_summarise_state(state or {}),
            outputs_redacted=_summarise_update(update or {}),
            sources=sources,
            confidence=confidence,
            stub_reason=(
                "force_stub mode (offline backends across stack)"
                if force_stub else None
            ),
            memory_version=str(memory_version) if memory_version else None,
            duration_ms=float(duration_ms) if duration_ms is not None else None,
            error=error,
            correlation_id=correlation_id,
            extra=dict(extra or {}),
        )
        return self._append(record)

    def log_record(self, record: ProvenanceRecord) -> ProvenanceRecord:
        """Persist a pre-built record (used by the wrapper in graph.py)."""
        return self._append(record)

    def _append(self, record: ProvenanceRecord) -> ProvenanceRecord:
        path = log_path_for(record.timestamp.split("T", 1)[0])
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(record.to_jsonl() + "\n")
        return record

    # -- Read side ---------------------------------------------------------

    def query_by_date(self, date_iso: str) -> list[ProvenanceRecord]:
        """Return every record written on a given UTC date."""
        path = log_path_for(date_iso)
        if not path.exists():
            return []
        return list(self._read_lines(path))

    def query_by_run_id(self, run_id: str) -> list[ProvenanceRecord]:
        """Return every record for one run across all date files."""
        out: list[ProvenanceRecord] = []
        for path in sorted(_date_jsonl_files(self._root)):
            for rec in self._read_lines(path):
                if rec.run_id == run_id:
                    out.append(rec)
        return out

    def query_by_source(self, source: str) -> list[ProvenanceRecord]:
        """Return every record that touched a given source."""
        out: list[ProvenanceRecord] = []
        for path in sorted(_date_jsonl_files(self._root)):
            for rec in self._read_lines(path):
                if source in rec.sources:
                    out.append(rec)
        return out

    def latest_run(self) -> list[ProvenanceRecord]:
        """Return every record from the most recent run on disk."""
        run_id: str | None = None
        for path in sorted(_date_jsonl_files(self._root), reverse=True):
            recs = list(self._read_lines(path))
            if not recs:
                continue
            run_id = recs[-1].run_id
            break
        return self.query_by_run_id(run_id) if run_id else []

    def list_runs(self) -> list[str]:
        """List every run_id seen, newest first."""
        seen: dict[str, str] = {}
        for path in sorted(_date_jsonl_files(self._root)):
            for rec in self._read_lines(path):
                if rec.run_id and rec.run_id not in seen:
                    seen[rec.run_id] = rec.timestamp
        return [rid for rid, _ts in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)]

    @staticmethod
    def _read_lines(path: Path) -> Iterable[ProvenanceRecord]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield ProvenanceRecord.from_jsonl(line)
                    except (ValueError, KeyError, TypeError):
                        # A corrupted line must not poison the rest of the
                        # file. Skip it; the user can ``Get-Content`` the
                        # file directly to inspect.
                        continue
        except OSError:
            return


# --- Section 5. Process-wide singleton ----------------------------------

_DEFAULT_LOCK = threading.Lock()
_DEFAULT_LOGGER: LocalProvenanceLogger | None = None


def get_default_logger(
    *,
    user_id: str = "default",
    refresh: bool = False,
) -> LocalProvenanceLogger:
    """Cached default logger.  ``refresh=True`` rebuilds the singleton."""
    global _DEFAULT_LOGGER
    with _DEFAULT_LOCK:
        if (
            refresh
            or _DEFAULT_LOGGER is None
            or _DEFAULT_LOGGER.user_id != user_id
        ):
            _DEFAULT_LOGGER = LocalProvenanceLogger(user_id=user_id)
    return _DEFAULT_LOGGER


def reset_default_logger() -> None:
    """Drop the cached singleton (used by smoke tests for hermeticity)."""
    global _DEFAULT_LOGGER
    with _DEFAULT_LOCK:
        _DEFAULT_LOGGER = None


# --- Section 6. Markdown audit export -----------------------------------

_REPORT_HEADER = (
    "# Self-Evolving Personal OS — Provenance Audit\n"
    "\n"
    "Built to help xAI and Grok win. This report is generated locally on\n"
    "your Windows machine and never leaves it unless you opt in.\n"
    "\n"
)


def summarise_run(records: list[ProvenanceRecord]) -> dict:
    """Compact summary used both by the Markdown report and the CLI."""
    if not records:
        return {
            "run_id":         None,
            "started_at":     None,
            "finished_at":    None,
            "node_count":     0,
            "sources_seen":   [],
            "stub":           False,
            "errors":         [],
            "confidences":    {},
            "memory_version": None,
            "user_id":        None,
        }
    sources_seen: set[str] = set()
    errors: list[str] = []
    confidences: dict[str, int] = {}
    stub_run = False
    for r in records:
        sources_seen.update(r.sources)
        if r.error:
            errors.append(f"{r.node_name}: {r.error}")
        if r.confidence:
            confidences[r.confidence] = confidences.get(r.confidence, 0) + 1
        if r.stub_reason:
            stub_run = True
    return {
        "run_id":         records[0].run_id,
        "started_at":     records[0].timestamp,
        "finished_at":    records[-1].timestamp,
        "node_count":     len(records),
        "sources_seen":   sorted(sources_seen),
        "stub":           stub_run,
        "errors":         errors,
        "confidences":    confidences,
        "memory_version": records[-1].memory_version,
        "user_id":        records[0].user_id,
    }


def export_audit_report(
    *,
    date_iso: str | None = None,
    run_id: str | None = None,
    source: str | None = None,
    logger: LocalProvenanceLogger | None = None,
) -> str:
    """Build a Markdown audit report.

    Pass at most one filter (``date_iso`` / ``run_id`` / ``source``); if all
    three are None the report covers every run on the most recent JSONL
    file. The report is rendered as plain Markdown so the user can paste
    it into a PR, a GitHub issue, or a forwarded email.
    """
    log = logger or get_default_logger()

    if run_id:
        records = log.query_by_run_id(run_id)
        title_filter = f"run `{run_id}`"
    elif source:
        records = log.query_by_source(source)
        title_filter = f"source `{source}`"
    elif date_iso:
        records = log.query_by_date(date_iso)
        title_filter = f"date `{date_iso}`"
    else:
        records = log.latest_run()
        title_filter = "latest run"

    summary = summarise_run(records)
    lines: list[str] = []
    lines.append(_REPORT_HEADER.rstrip())
    lines.append(f"## Audit scope: {title_filter}")
    lines.append("")
    lines.append(f"- Run ID: `{summary['run_id']}`")
    lines.append(f"- User ID: `{summary['user_id']}`")
    lines.append(f"- Started: `{summary['started_at']}`")
    lines.append(f"- Finished: `{summary['finished_at']}`")
    lines.append(f"- Node count: **{summary['node_count']}**")
    lines.append(f"- Sources seen: {', '.join(f'`{s}`' for s in summary['sources_seen']) or '_none_'}")
    lines.append(f"- Stub run: **{summary['stub']}**")
    lines.append(f"- Memory / prompt version: `{summary['memory_version']}`")
    if summary["confidences"]:
        bits = [f"{lvl}={n}" for lvl, n in sorted(summary["confidences"].items())]
        lines.append(f"- Confidence distribution: {', '.join(bits)}")
    if summary["errors"]:
        lines.append("- Errors surfaced:")
        for e in summary["errors"]:
            lines.append(f"  - {e}")
    lines.append("")
    lines.append("## Per-node trail")
    lines.append("")
    if not records:
        lines.append("_No records matched the requested filter._")
    else:
        lines.append("| # | Node | Timestamp | Sources | Confidence | Stub | Error |")
        lines.append("|---|------|-----------|---------|------------|------|-------|")
        for i, r in enumerate(records, 1):
            srcs = ", ".join(f"`{s}`" for s in r.sources) or "_none_"
            err  = (r.error or "_none_").replace("|", "\\|")
            stub = "yes" if r.stub_reason else "no"
            conf = r.confidence or "_none_"
            lines.append(
                f"| {i} | `{r.node_name}` | `{r.timestamp}` | {srcs} | "
                f"{conf} | {stub} | {err} |"
            )
    lines.append("")
    lines.append(f"_Report generated at {_now_iso()}._")
    lines.append("")
    return "\n".join(lines)
