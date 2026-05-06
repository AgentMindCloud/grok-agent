# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Local provenance log (P113, Slot 5 / 1 of 2).

Built for xAI, X, Grok and the ecosystem community. ❤️

This module is the official local-first half of the Trust Engine. It
owns the append-only JSONL provenance log at
``<appdata>/provenance/events.jsonl`` and mirrors every write into the
``Mem0QdrantStore.audit_trail`` table (when a real ``version_id`` is
available) so the per-version timeline and the global "everything that
ever happened" timeline stay in sync.

What gets logged
================

Three ingest paths funnel into the same JSONL stream:

1. **Orchestrator events** — the 6-node DAG calls
   ``logger.log_event("ingest.ok", payload)`` and
   ``logger.log_event("synthesis.finalized", payload)`` directly. Each
   call writes one JSONL line.
2. **Claim and contradiction records** — the orchestrator's
   ``_node_finalize`` calls ``logger.log_claim(claim, version_id)`` and
   ``logger.log_contradiction(contradiction, version_id)`` for every
   row of the freshly-built ``SynthesisVersion``. Defense-in-depth
   ``ConstitutionViolation`` triggers on empty ``source_id`` or empty
   ``claim_ids``.
3. **Rich-API calls** — ``log_step``, ``log_connector_fetch``, and
   ``log_contradiction_flag`` are extension methods slots 6 / 7 call
   directly. Each writes a JSONL line in the same shape.

Slot boundary contract
======================

* This module does NOT redefine the orchestrator's ``ProvenanceLogger``
  Protocol — it implements it. The composite in ``__init__.py`` is what
  the orchestrator typechecks against.
* This module does NOT modify ``orchestrator.py``, ``graph.py``, the
  memory layer, or the connector layer. Every cross-module dependency
  is via the relative-then-absolute import idiom from ``graph.py:182-187``.
* Append-only. There is no ``update`` or ``delete`` method. Constitution
  rule: "you can rewind to any prior state — synthesis is versioned."

JSONL event shape
=================

Every line is one JSON object with the same fixed top-level keys::

    {
      "event_id":     "<sha256[:16]>",
      "event_type":   "<dotted.event.type>",
      "version_id":   "<sha256[:16]>" | null,
      "topic":        "<topic>" | null,
      "recorded_at":  "<iso8601>",
      "payload":      { ... }
    }

The ``payload`` is the verbatim dict the caller passed; the logger does
NOT introspect it beyond a Constitution check on known fields
(``source_id``, ``claim_ids``).
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import dataclasses + exception from the orchestrator + memory layer
# ---------------------------------------------------------------------------


def _import_orchestrator():
    try:
        from .. import orchestrator as _orch  # type: ignore
        return _orch
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("orchestrator")


def _import_memory():
    try:
        from ..memory import Mem0QdrantStore  # type: ignore
        return Mem0QdrantStore
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    return importlib.import_module("memory").Mem0QdrantStore


_orch = _import_orchestrator()
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
_default_appdata_root = _orch._default_appdata_root

Mem0QdrantStore = _import_memory()


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceEvent:
    """One JSONL row.

    The dict payload is opaque from the logger's perspective except for
    Constitution checks on known fields.
    """

    event_id:    str
    event_type:  str
    version_id:  Optional[str]
    topic:       Optional[str]
    recorded_at: datetime
    payload:     dict

    def to_jsonl(self) -> str:
        return json.dumps({
            "event_id":    self.event_id,
            "event_type":  self.event_type,
            "version_id":  self.version_id,
            "topic":       self.topic,
            "recorded_at": self.recorded_at.isoformat(),
            "payload":     self.payload,
        }, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_jsonl(cls, line: str) -> "ProvenanceEvent":
        d = json.loads(line)
        return cls(
            event_id=d["event_id"],
            event_type=d["event_type"],
            version_id=d.get("version_id"),
            topic=d.get("topic"),
            recorded_at=datetime.fromisoformat(d["recorded_at"]),
            payload=dict(d.get("payload") or {}),
        )


@dataclass(frozen=True)
class ProvenanceRewindResult:
    """Returned by ``rewind_with_provenance``."""

    version:         SynthesisVersion
    parent_chain:    tuple[SynthesisVersion, ...]
    descendants:     tuple[SynthesisVersion, ...]
    events_for_target: tuple[ProvenanceEvent, ...]
    events_for_chain:  tuple[ProvenanceEvent, ...]   # all ancestors' events


# ---------------------------------------------------------------------------
# Known event-type prefixes (informational — used by the report renderer)
# ---------------------------------------------------------------------------

EVENT_NODE_PREFIXES = (
    "ingest.",
    "normalise.",
    "detect_contradictions.",
    "score.",
    "audit.",
    "finalize.",
)
EVENT_RUNTIME_PREFIXES = ("runtime.",)
EVENT_CONNECTOR_PREFIXES = ("connector.",)
EVENT_MEMORY_PREFIXES = ("memory.",)
EVENT_SYNTHESIS_PREFIXES = ("synthesis.",)
EVENT_CLAIM_PREFIXES = ("claim.",)
EVENT_CONTRADICTION_PREFIXES = ("contradiction.",)


def _classify_event(event_type: str) -> str:
    for kind, prefixes in (
        ("dag-node",      EVENT_NODE_PREFIXES),
        ("runtime",       EVENT_RUNTIME_PREFIXES),
        ("connector",     EVENT_CONNECTOR_PREFIXES),
        ("memory",        EVENT_MEMORY_PREFIXES),
        ("synthesis",     EVENT_SYNTHESIS_PREFIXES),
        ("claim",         EVENT_CLAIM_PREFIXES),
        ("contradiction", EVENT_CONTRADICTION_PREFIXES),
    ):
        if any(event_type.startswith(p) for p in prefixes):
            return kind
    return "other"


# ---------------------------------------------------------------------------
# LocalProvenanceLog — append-only JSONL + optional Mem0QdrantStore mirror
# ---------------------------------------------------------------------------


@dataclass
class LocalProvenanceLog:
    """The local-first official provenance log.

    The composite in ``__init__.py`` holds an instance of this class as
    its ``local`` field. Slots 6 / 7 talk to the composite; this class
    is internal-but-not-private (re-exported for power users who want
    direct file-level operations).
    """

    appdata_root: Path
    log_path:     Path
    store:        Optional[Mem0QdrantStore] = field(default=None, repr=False)
    _lock:        threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- construction ----------------------------------------------------

    def __post_init__(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            # Touch the file so subsequent appends always have something
            # to open without race conditions.
            self.log_path.write_text("", encoding="utf-8")

    # ---- core append helper ---------------------------------------------

    def _append(self, event: ProvenanceEvent) -> None:
        line = event.to_jsonl()
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
        # Best-effort mirror into the memory store's audit_trail.
        if self.store is not None and event.version_id:
            try:
                structured = getattr(self.store, "structured", None)
                if structured is None or not hasattr(structured, "append_audit_entry"):
                    return
                # Only mirror when the version actually exists in the store.
                # This matches P111's FK constraint without raising.
                if structured.get_version(event.version_id) is None:
                    return
                structured.append_audit_entry(
                    version_id=event.version_id,
                    kind=f"provenance:{event.event_type}",
                    reason=json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))[:1000],
                )
            except Exception:
                # Mirror failures never poison the JSONL write.
                pass

    @staticmethod
    def _make_event_id(event_type: str, version_id: Optional[str], payload: dict) -> str:
        seed = f"{event_type}|{version_id or '_'}|{json.dumps(payload, sort_keys=True, default=str)}|{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    # ---- Protocol-required (3) ------------------------------------------

    def log_event(self, event_type: str, payload: dict) -> None:
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("log_event: event_type must be a non-empty string")
        if not isinstance(payload, dict):
            raise TypeError("log_event: payload must be a dict")

        # Constitution defense-in-depth on known fields:
        if event_type.startswith("claim.") and not (payload.get("source_id") or "").strip():
            raise ConstitutionViolation(
                f"Constitution violation: event {event_type!r} carries an empty "
                f"source_id; provenance is mandatory."
            )

        version_id = payload.get("version_id")
        topic = payload.get("topic")
        evt = ProvenanceEvent(
            event_id=self._make_event_id(event_type, version_id, payload),
            event_type=event_type,
            version_id=version_id if isinstance(version_id, str) else None,
            topic=topic if isinstance(topic, str) else None,
            recorded_at=datetime.now(timezone.utc),
            payload=dict(payload),
        )
        self._append(evt)

    def log_claim(self, claim: Claim, version_id: str) -> None:
        if not claim.source_id:
            raise ConstitutionViolation(
                f"Constitution violation: claim {claim.claim_id!r} has empty source_id; "
                f"provenance log refuses to record citation-less claims."
            )
        if not version_id:
            raise ValueError("log_claim: version_id must be a non-empty string")
        payload = {
            "claim_id":   claim.claim_id,
            "subject":    claim.subject,
            "predicate":  claim.predicate,
            "value":      claim.value,
            "source":     claim.source,
            "source_id":  claim.source_id,
            "confidence": float(claim.confidence),
            "version_id": version_id,
        }
        self.log_event("claim.recorded", payload)

    def log_contradiction(self, contradiction: Contradiction, version_id: str) -> None:
        if not contradiction.claim_ids:
            raise ConstitutionViolation(
                f"Constitution violation: contradiction {contradiction.contradiction_id!r} "
                f"has empty claim_ids; provenance log refuses to record contradictions "
                f"that point at no claims."
            )
        if not version_id:
            raise ValueError("log_contradiction: version_id must be a non-empty string")
        payload = {
            "contradiction_id":    contradiction.contradiction_id,
            "subject":             contradiction.subject,
            "predicate":           contradiction.predicate,
            "claim_ids":           list(contradiction.claim_ids),
            "severity":            int(contradiction.severity),
            "severity_components": dict(contradiction.severity_components),
            "note":                contradiction.note,
            "version_id":          version_id,
        }
        self.log_event("contradiction.recorded", payload)

    # ---- Rich API (6) ---------------------------------------------------

    def log_step(
        self,
        step_name: str,
        version_id: Optional[str] = None,
        *,
        status: str = "ok",
        payload: Optional[dict] = None,
    ) -> None:
        """Generic DAG-node logger for slots 6 / 7 to call directly."""

        if not step_name:
            raise ValueError("log_step: step_name must be a non-empty string")
        if status not in ("start", "ok", "error", "skipped"):
            raise ValueError(
                f"log_step: status must be one of "
                f"('start','ok','error','skipped'); got {status!r}."
            )
        full_payload = dict(payload or {})
        full_payload.setdefault("step", step_name)
        full_payload.setdefault("status", status)
        if version_id:
            full_payload["version_id"] = version_id
        self.log_event(f"node.{step_name}.{status}", full_payload)

    def log_connector_fetch(
        self,
        connector_name: str,
        query: str,
        since: datetime,
        items: Sequence[Any],
        *,
        cache_hit: bool = False,
        version_id: Optional[str] = None,
    ) -> None:
        """Connector-fetch logger. Defense-in-depth Constitution check on
        every item's source_id-equivalent field.
        """

        if not connector_name:
            raise ValueError("log_connector_fetch: connector_name must be non-empty")
        for it in items:
            item_id = getattr(it, "item_id", None) or (it.get("item_id") if isinstance(it, dict) else None)
            if not item_id:
                raise ConstitutionViolation(
                    f"Constitution violation: log_connector_fetch saw a "
                    f"{connector_name!r} item with empty item_id."
                )
        payload = {
            "connector": connector_name,
            "query":     query,
            "since":     since.isoformat(),
            "item_count": len(items),
            "cache_hit": bool(cache_hit),
        }
        if version_id:
            payload["version_id"] = version_id
        suffix = "cache_hit" if cache_hit else "ok"
        self.log_event(f"connector.{connector_name}.fetch.{suffix}", payload)

    def log_contradiction_flag(
        self,
        contradiction_id: str,
        *,
        reason: str,
        flagged_by: str = "user",
        version_id: Optional[str] = None,
    ) -> str:
        """Append-only flag of an existing contradiction.

        Mirrors the flag into ``Mem0QdrantStore.append_flag`` when a store
        is wired so the contradiction-flags table stays the official
        per-contradiction view; the JSONL log keeps the global timeline.
        Returns the flag_id when a store is wired, or an event_id when not.
        """

        if not contradiction_id:
            raise ValueError("log_contradiction_flag: contradiction_id must be non-empty")
        if not reason:
            raise ValueError("log_contradiction_flag: reason must be non-empty")

        flag_id: Optional[str] = None
        if self.store is not None:
            try:
                flag_id = self.store.flag_contradiction(
                    contradiction_id=contradiction_id,
                    reason=reason,
                    flagged_by=flagged_by,
                )
            except Exception:
                flag_id = None
        payload = {
            "contradiction_id": contradiction_id,
            "reason":           reason,
            "flagged_by":       flagged_by,
            "flag_id":          flag_id,
        }
        if version_id:
            payload["version_id"] = version_id
        self.log_event("contradiction.flagged", payload)
        return flag_id or self._make_event_id("contradiction.flagged", version_id, payload)

    def get_audit_trail(
        self,
        version_id: str,
        *,
        full_chain: bool = True,
        kinds: Optional[Iterable[str]] = None,
    ) -> tuple[ProvenanceEvent, ...]:
        """Return every JSONL event matching the version (and ancestors when ``full_chain``).

        ``kinds`` is an optional filter on the dotted event-type prefix —
        e.g. ``("connector", "claim")``. Matched against the
        ``_classify_event`` taxonomy.
        """

        if not version_id:
            return ()

        target_ids: set[str] = {version_id}
        if full_chain and self.store is not None:
            try:
                for v in self.store.structured.walk_chain(version_id):
                    target_ids.add(v.version_id)
            except Exception:
                pass

        kind_filter = set(kinds) if kinds is not None else None

        out: list[ProvenanceEvent] = []
        for ev in self._iter_events():
            if ev.version_id and ev.version_id in target_ids:
                if kind_filter is not None and _classify_event(ev.event_type) not in kind_filter:
                    continue
                out.append(ev)
        return tuple(out)

    def export_report(
        self,
        version_id: str,
        *,
        format: str = "markdown",
    ) -> str:
        """Render a per-version provenance report.

        Currently supports ``"markdown"`` only — slots 7 (Streamlit UI)
        will likely add JSON/HTML variants on top of this.
        """

        if format != "markdown":
            raise ValueError(
                f"export_report: format={format!r} is not supported in Slot 5 / P113. "
                f"Use format='markdown'."
            )
        version: Optional[SynthesisVersion] = None
        if self.store is not None:
            try:
                version = self.store.structured.get_version(version_id)
            except Exception:
                version = None

        events = self.get_audit_trail(version_id, full_chain=True)
        return _render_markdown_report(version_id, version, events)

    def rewind_with_provenance(self, version_id: str) -> Optional[ProvenanceRewindResult]:
        """Return a complete rewind + the JSONL event chain.

        Requires the memory store be wired. Returns ``None`` when the
        version isn't found.
        """

        if self.store is None:
            return None
        rewind = None
        try:
            rewind = self.store.rewind_to_version(version_id)
        except Exception:
            rewind = None
        if rewind is None:
            return None

        events_for_target: list[ProvenanceEvent] = []
        chain_ids = {v.version_id for v in rewind.parent_chain}
        events_for_chain: list[ProvenanceEvent] = []
        for ev in self._iter_events():
            if ev.version_id == version_id:
                events_for_target.append(ev)
            elif ev.version_id and ev.version_id in chain_ids:
                events_for_chain.append(ev)
        return ProvenanceRewindResult(
            version=rewind.version,
            parent_chain=rewind.parent_chain,
            descendants=rewind.descendants,
            events_for_target=tuple(events_for_target),
            events_for_chain=tuple(events_for_chain),
        )

    # ---- iteration helpers ----------------------------------------------

    def _iter_events(self) -> Iterable[ProvenanceEvent]:
        if not self.log_path.exists():
            return ()
        out: list[ProvenanceEvent] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(ProvenanceEvent.from_jsonl(line))
                except Exception:
                    # Skip corrupt lines — append-only design tolerates
                    # them without taking the rest of the log down.
                    continue
        return out

    def all_events(self) -> tuple[ProvenanceEvent, ...]:
        return tuple(self._iter_events())

    def event_count(self) -> int:
        if not self.log_path.exists():
            return 0
        n = 0
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    n += 1
        return n

    def connect_store(self, store: Mem0QdrantStore) -> None:
        self.store = store


# ---------------------------------------------------------------------------
# Markdown report renderer
# ---------------------------------------------------------------------------


def _render_markdown_report(
    version_id: str,
    version: Optional[SynthesisVersion],
    events: Sequence[ProvenanceEvent],
) -> str:
    out = io.StringIO()
    out.write("<!-- Copyright 2026 AgentMindCloud -->\n")
    out.write("<!-- Licensed under the Apache License, Version 2.0 -->\n")
    out.write("<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n")
    out.write(
        "<!-- Living Narrative Fabric — Provenance report (P113 Trust Engine) -->\n\n"
    )
    out.write(f"# Provenance Report — `{version_id}`\n\n")
    out.write(
        "> Append-only audit trail covering every node, connector fetch, "
        "memory operation, and contradiction flag that produced this "
        "synthesis. Built for xAI, X, Grok and the ecosystem community. ❤️\n\n"
    )

    out.write("## 1. Topic Snapshot\n\n")
    if version is not None:
        out.write(f"- **Topic**: {version.topic}\n")
        out.write(f"- **Time range**: {version.time_range}\n")
        out.write(f"- **Created at (UTC)**: {version.created_at.isoformat()}\n")
        out.write(f"- **Confidence score**: {version.confidence_score}/100\n")
        out.write(
            f"- **Parent**: "
            + (f"`{version.parent_version_id}`" if version.parent_version_id else "(first version on this topic)")
            + "\n"
        )
        out.write(f"- **Audit triggered**: {'yes' if version.audit_triggered else 'no'}\n\n")
    else:
        out.write("- (version metadata not retrievable from memory store)\n\n")

    out.write("## 2. Run Timeline\n\n")
    if not events:
        out.write("_No events recorded for this version._\n\n")
    else:
        out.write("| # | Recorded at (UTC) | Event type | Kind |\n")
        out.write("|---:|---|---|---|\n")
        for n, ev in enumerate(events, start=1):
            kind = _classify_event(ev.event_type)
            out.write(f"| {n} | {ev.recorded_at.isoformat()} | `{ev.event_type}` | {kind} |\n")
        out.write("\n")

    out.write("## 3. Connector Activity\n\n")
    connector_events = [ev for ev in events if _classify_event(ev.event_type) == "connector"]
    if not connector_events:
        out.write("_No connector events recorded._\n\n")
    else:
        out.write("| Connector | Query | Items | Cache hit |\n")
        out.write("|---|---|---:|:---:|\n")
        for ev in connector_events:
            p = ev.payload or {}
            out.write(
                f"| `{p.get('connector', '?')}` | {p.get('query', '?')} "
                f"| {p.get('item_count', 0)} | "
                f"{'✓' if p.get('cache_hit') else ''} |\n"
            )
        out.write("\n")

    out.write("## 4. Contradictions Flagged\n\n")
    contradiction_events = [
        ev for ev in events
        if _classify_event(ev.event_type) == "contradiction"
    ]
    if not contradiction_events:
        out.write("_No contradictions recorded for this version chain._\n\n")
    else:
        out.write("| Contradiction id | Subject — predicate | Severity | Note |\n")
        out.write("|---|---|---:|---|\n")
        for ev in contradiction_events:
            p = ev.payload or {}
            out.write(
                f"| `{p.get('contradiction_id', '?')}` | "
                f"{p.get('subject', '?')} — {p.get('predicate', '?')} | "
                f"{p.get('severity', '?')}/10 | "
                f"{p.get('note') or p.get('reason') or ''} |\n"
            )
        out.write("\n")

    out.write("## 5. Bridges\n\n")
    out.write(
        "Pair this report with the synthesis itself + at least three of the "
        "fabric's bridges so the audit actually moves a decision:\n\n"
    )
    if version is not None and version.bridges:
        for b in version.bridges:
            out.write(f"- `{b}`\n")
    else:
        out.write("- `self-evolving-personal-os`\n")
        out.write("- `cross-reality-action-fabric`\n")
        out.write("- `analytics-summarizer`\n")
    out.write("\n---\n\n")
    out.write(
        "*Built for xAI, X, Grok and the ecosystem community. ❤️ "
        "Apache-2.0. Local-first. Privacy-first.*\n"
    )
    return out.getvalue()


__all__ = (
    "EVENT_NODE_PREFIXES",
    "EVENT_RUNTIME_PREFIXES",
    "EVENT_CONNECTOR_PREFIXES",
    "EVENT_MEMORY_PREFIXES",
    "EVENT_SYNTHESIS_PREFIXES",
    "EVENT_CLAIM_PREFIXES",
    "EVENT_CONTRADICTION_PREFIXES",
    "LocalProvenanceLog",
    "ProvenanceEvent",
    "ProvenanceRewindResult",
)
