# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Living Narrative Fabric — Trust Engine / Provenance package (P113, Slot 5).

Built for xAI, X, Grok and the ecosystem community. ❤️

This package is the durable, exportable, optionally-cloud-mirrored
replacement for the default ``NoopProvenanceLogger`` shipped with
P110's orchestration core. It composes two siblings:

* :class:`provenance.log.LocalProvenanceLog` — the official local-first
  append-only JSONL stream at ``<appdata>/provenance/events.jsonl``,
  mirrored into the ``Mem0QdrantStore.audit_trail`` table whenever a
  real ``version_id`` is in scope.
* :class:`provenance.langfuse_hooks.LangfuseProvenanceHooks` — the
  optional cloud-side mirror that creates a ``Trace`` per synthesis
  and ``Span``/``Generation`` records per node / connector /
  claim / contradiction. Becomes a no-op when neither
  ``LANGFUSE_PUBLIC_KEY`` nor the ``langfuse`` SDK is available.

Slot boundary contract
======================

* This package satisfies the ``ProvenanceLogger`` Protocol from P110's
  ``orchestrator.py`` exactly (3 methods: ``log_event``, ``log_claim``,
  ``log_contradiction``). The orchestrator wires it in via
  ``LivingNarrativeFabric.with_dependencies(provenance=...)``.
* On the SAME composite class, this package exposes 6 rich methods
  for slots 6 / 7 to call directly: ``log_step``,
  ``log_connector_fetch``, ``log_contradiction_flag``,
  ``get_audit_trail``, ``export_report``, ``rewind_with_provenance``.
* This package makes ZERO changes to ``orchestrator.py``,
  ``graph.py``, the memory layer, or the connector layer.

Plug-in pattern
===============

::

    from memory     import build_memory_store
    from connectors import build_connectors
    from provenance import build_provenance_logger
    from orchestrator import LivingNarrativeFabric

    store      = build_memory_store()
    connectors = build_connectors(store=store, force_stub=True)
    logger     = build_provenance_logger(store=store)

    fabric = LivingNarrativeFabric().with_dependencies(
        sources=tuple(connectors.connectors),
        memory=store,
        provenance=logger,
    )
    version = fabric.synthesize(topic="Grok Agent OS launch", time_range="7d")
    print(logger.export_report(version.version_id))

CLI smoke test
==============

::

    cd templates\\super-agents\\living-narrative-fabric
    python provenance\\__init__.py

Prints ``P113 provenance layer smoke OK`` on success; raises
``AssertionError`` on any failure. Runs in zero-install mode (no
Langfuse SDK, no Langfuse keys) and exercises:

* Protocol satisfaction on the composite
* Append-only JSONL writes for ``log_event`` / ``log_claim`` /
  ``log_contradiction`` calls coming from a real ``synthesize()`` run
* Rich-API calls (``log_step``, ``log_connector_fetch``,
  ``log_contradiction_flag``, ``get_audit_trail``, ``export_report``,
  ``rewind_with_provenance``)
* ``ConstitutionViolation`` raises on empty source_id / claim_ids
* Langfuse no-op recorded-call witness (so a real key just turns the
  same call sites into actual Langfuse spans without code changes)
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Re-import from orchestrator + memory + sibling modules
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
        from ..memory import (  # type: ignore
            Mem0QdrantStore,
            build_memory_store,
        )
        return Mem0QdrantStore, build_memory_store
    except Exception:
        pass
    parent = Path(__file__).resolve().parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    mem_pkg = importlib.import_module("memory")
    return mem_pkg.Mem0QdrantStore, mem_pkg.build_memory_store


_orch = _import_orchestrator()
SynthesisVersion = _orch.SynthesisVersion
Claim = _orch.Claim
Contradiction = _orch.Contradiction
ConstitutionViolation = _orch.ConstitutionViolation
ProvenanceLogger = _orch.ProvenanceLogger
LivingNarrativeFabric = _orch.LivingNarrativeFabric
_default_appdata_root = _orch._default_appdata_root

Mem0QdrantStore, build_memory_store = _import_memory()


def _import_siblings():
    try:
        from . import log as _log_mod  # type: ignore
        from . import langfuse_hooks as _lf_mod  # type: ignore
        return _log_mod, _lf_mod
    except Exception:
        pass
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    return (
        importlib.import_module("log"),
        importlib.import_module("langfuse_hooks"),
    )


_log_mod, _lf_mod = _import_siblings()
LocalProvenanceLog = _log_mod.LocalProvenanceLog
ProvenanceEvent = _log_mod.ProvenanceEvent
ProvenanceRewindResult = _log_mod.ProvenanceRewindResult
LangfuseProvenanceHooks = _lf_mod.LangfuseProvenanceHooks
LangfuseCallRecord = _lf_mod.LangfuseCallRecord


# ---------------------------------------------------------------------------
# LivingNarrativeFabricProvenance — the composite
# ---------------------------------------------------------------------------


@dataclass
class LivingNarrativeFabricProvenance:
    """Composite provenance logger that satisfies the orchestrator's Protocol
    and exposes the 6 rich methods.

    The 3 Protocol methods fan out to BOTH the local JSONL log and the
    Langfuse hooks (Langfuse becomes a no-op when no SDK / keys). The
    6 rich methods delegate to the local log only — Langfuse is
    fire-and-forget and doesn't expose query operations the rich API
    needs to support.
    """

    local:    LocalProvenanceLog
    langfuse: LangfuseProvenanceHooks

    # ---- Protocol-required (3) ------------------------------------------

    def log_event(self, event_type: str, payload: dict) -> None:
        # Local first — JSONL is the official record.
        self.local.log_event(event_type, payload)
        # Langfuse second — best-effort cloud mirror.
        try:
            self.langfuse.log_event(event_type, payload)
        except ConstitutionViolation:
            raise
        except Exception:
            pass

    def log_claim(self, claim: Claim, version_id: str) -> None:
        self.local.log_claim(claim, version_id)
        try:
            self.langfuse.log_claim(claim, version_id)
        except ConstitutionViolation:
            raise
        except Exception:
            pass

    def log_contradiction(self, contradiction: Contradiction, version_id: str) -> None:
        self.local.log_contradiction(contradiction, version_id)
        try:
            self.langfuse.log_contradiction(contradiction, version_id)
        except ConstitutionViolation:
            raise
        except Exception:
            pass

    # ---- Rich API (6) ---------------------------------------------------

    def log_step(
        self,
        step_name: str,
        version_id: Optional[str] = None,
        *,
        status: str = "ok",
        payload: Optional[dict] = None,
    ) -> None:
        self.local.log_step(step_name, version_id, status=status, payload=payload)
        # Mirror into Langfuse via the generic event API.
        try:
            self.langfuse.log_event(
                f"node.{step_name}.{status}",
                {**(payload or {}), "step": step_name, "status": status,
                 "version_id": version_id},
            )
        except ConstitutionViolation:
            raise
        except Exception:
            pass

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
        self.local.log_connector_fetch(
            connector_name, query, since, items,
            cache_hit=cache_hit, version_id=version_id,
        )
        try:
            self.langfuse.log_event(
                f"connector.{connector_name}.fetch."
                + ("cache_hit" if cache_hit else "ok"),
                {
                    "connector":  connector_name,
                    "query":      query,
                    "since":      since.isoformat(),
                    "item_count": len(items),
                    "cache_hit":  bool(cache_hit),
                    "version_id": version_id,
                },
            )
        except ConstitutionViolation:
            raise
        except Exception:
            pass

    def log_contradiction_flag(
        self,
        contradiction_id: str,
        *,
        reason: str,
        flagged_by: str = "user",
        version_id: Optional[str] = None,
    ) -> str:
        flag_id = self.local.log_contradiction_flag(
            contradiction_id, reason=reason, flagged_by=flagged_by,
            version_id=version_id,
        )
        try:
            self.langfuse.log_event("contradiction.flagged", {
                "contradiction_id": contradiction_id,
                "reason":           reason,
                "flagged_by":       flagged_by,
                "flag_id":          flag_id,
                "version_id":       version_id,
            })
        except ConstitutionViolation:
            raise
        except Exception:
            pass
        return flag_id

    def get_audit_trail(
        self,
        version_id: str,
        *,
        full_chain: bool = True,
        kinds: Optional[Iterable[str]] = None,
    ) -> tuple[ProvenanceEvent, ...]:
        return self.local.get_audit_trail(
            version_id, full_chain=full_chain, kinds=kinds,
        )

    def export_report(
        self,
        version_id: str,
        *,
        format: str = "markdown",
    ) -> str:
        return self.local.export_report(version_id, format=format)

    def rewind_with_provenance(
        self,
        version_id: str,
    ) -> Optional[ProvenanceRewindResult]:
        return self.local.rewind_with_provenance(version_id)

    # ---- introspection ---------------------------------------------------

    @property
    def runtime_info(self) -> dict:
        return {
            "local_log_path":   str(self.local.log_path),
            "local_event_count": self.local.event_count(),
            "langfuse":          self.langfuse.runtime_info,
        }

    def connect_store(self, store: Mem0QdrantStore) -> None:
        self.local.connect_store(store)

    def flush(self) -> None:
        self.langfuse.flush()


# ---------------------------------------------------------------------------
# Factory + convenience wirers
# ---------------------------------------------------------------------------


def build_provenance_logger(
    *,
    appdata_root:        Optional[Path] = None,
    store:               Optional[Mem0QdrantStore] = None,
    log_filename:        str = "events.jsonl",
    langfuse_public_key: Optional[str] = None,
    langfuse_secret_key: Optional[str] = None,
    langfuse_host:       Optional[str] = None,
) -> LivingNarrativeFabricProvenance:
    """Build a fully-wired ``LivingNarrativeFabricProvenance`` composite.

    Parameters
    ----------
    appdata_root :
        Local data directory. ``None`` → resolves via
        ``orchestrator._default_appdata_root()``.
    store :
        Optional ``Mem0QdrantStore``; when supplied, every JSONL write
        is mirrored into the store's audit_trail (when a version_id is
        in scope).
    log_filename :
        Filename for the JSONL log under ``<appdata>/provenance/``.
    langfuse_public_key, langfuse_secret_key, langfuse_host :
        Optional explicit Langfuse credentials. ``None`` → resolves via
        ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` / ``LANGFUSE_HOST``
        env vars.
    """

    root = appdata_root if appdata_root is not None else _default_appdata_root()
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    log_path = root / "provenance" / log_filename

    local = LocalProvenanceLog(
        appdata_root=root,
        log_path=log_path,
        store=store,
    )
    langfuse = LangfuseProvenanceHooks(
        public_key=langfuse_public_key,
        secret_key=langfuse_secret_key,
        host=langfuse_host,
    )
    return LivingNarrativeFabricProvenance(local=local, langfuse=langfuse)


def with_provenance(
    fabric: LivingNarrativeFabric,
    **kwargs: Any,
) -> LivingNarrativeFabric:
    """Return a copy of ``fabric`` with a fresh provenance logger injected."""

    return fabric.with_dependencies(provenance=build_provenance_logger(**kwargs))


# ---------------------------------------------------------------------------
# Smoke test (zero-install, zero-API-keys)
# ---------------------------------------------------------------------------


def run_smoke_test(*, verbose: bool = True) -> None:
    """Self-contained smoke test for the provenance layer.

    Runs in local-only mode — no Langfuse SDK, no Langfuse keys, no
    network — and verifies:

    1. Composite satisfies the ``ProvenanceLogger`` Protocol.
    2. ``log_event`` writes an append-only JSONL line.
    3. End-to-end: a real ``LivingNarrativeFabric.synthesize`` call
       with the composite injected via ``with_dependencies(provenance=...)``
       produces N events (>= 1 per claim + per contradiction + per
       runtime/finalize stage).
    4. ``log_claim``, ``log_contradiction`` write event_type=claim.recorded /
       contradiction.recorded rows.
    5. ``ConstitutionViolation`` raises on:
        - ``log_claim`` with empty source_id
        - ``log_contradiction`` with empty claim_ids
        - ``log_event`` of type ``claim.*`` with empty source_id
    6. Rich-API methods all work:
        - ``log_step``
        - ``log_connector_fetch``
        - ``log_contradiction_flag``
        - ``get_audit_trail``
        - ``export_report`` (markdown)
        - ``rewind_with_provenance``
    7. Langfuse no-op witness records every call so a real key turns
       the same wiring into real spans without code changes.
    """

    import shutil
    import tempfile

    tmp_root = Path(tempfile.mkdtemp(prefix="lnf-provenance-smoke-"))
    try:
        store = build_memory_store(appdata_root=tmp_root)
        logger = build_provenance_logger(appdata_root=tmp_root, store=store)

        if verbose:
            print(f"[smoke] runtime_info = {logger.runtime_info}")

        # ---- (1) Protocol satisfaction --------------------------------
        assert isinstance(logger, ProvenanceLogger), (
            "LivingNarrativeFabricProvenance does not satisfy ProvenanceLogger Protocol."
        )

        # ---- (2) Plain log_event ---------------------------------------
        logger.log_event("smoke.start", {"topic": "smoke", "note": "warmup"})
        assert logger.local.event_count() == 1
        assert logger.langfuse.recorded_calls, (
            "Langfuse no-op witness should record the trace.create + span.create."
        )

        # ---- (3) End-to-end synthesize integration --------------------
        # Use orchestrator's stub sources (same default the orchestrator
        # uses when no sources are passed) so the smoke test stays
        # zero-install — connectors are exercised in P112's smoke.
        fabric = LivingNarrativeFabric().with_dependencies(
            memory=store,
            provenance=logger,
        )
        v1 = fabric.synthesize(topic="smoke-topic", time_range="7d")
        v2 = fabric.synthesize(topic="smoke-topic", time_range="30d")
        assert v2.parent_version_id == v1.version_id

        # Every claim/contradiction in v1 + v2 should have been logged.
        events = logger.local.all_events()
        claim_events = [
            e for e in events if e.event_type == "claim.recorded"
            and e.version_id in {v1.version_id, v2.version_id}
        ]
        assert len(claim_events) >= len(v1.claims) + len(v2.claims), (
            f"expected >= {len(v1.claims) + len(v2.claims)} claim events; "
            f"got {len(claim_events)}."
        )

        synth_finalized = [
            e for e in events if e.event_type == "synthesis.finalized"
        ]
        assert len(synth_finalized) >= 2, (
            f"expected >= 2 synthesis.finalized events (one per version); "
            f"got {len(synth_finalized)}."
        )

        # ---- (4) Direct log_claim / log_contradiction -----------------
        # Reuse a real claim from v1 and a real contradiction (if any).
        if v1.claims:
            initial_claim_count = sum(
                1 for e in logger.local.all_events()
                if e.event_type == "claim.recorded"
            )
            logger.log_claim(v1.claims[0], v1.version_id)
            after = sum(
                1 for e in logger.local.all_events()
                if e.event_type == "claim.recorded"
            )
            assert after == initial_claim_count + 1

        # ---- (5) ConstitutionViolation raises -------------------------
        bad_claim = Claim(
            claim_id="bad", subject="x", predicate="y", value="z",
            source="newsapi", source_id="",  # ← empty
            confidence=0.5, extracted_at=datetime.now(timezone.utc),
            sentiment=None,
        )
        try:
            logger.log_claim(bad_claim, v1.version_id)
            raise AssertionError("log_claim accepted empty source_id")
        except ConstitutionViolation:
            pass

        bad_contradiction = Contradiction(
            contradiction_id="bad", subject="x", predicate="y",
            claim_ids=tuple(),  # ← empty
            severity=5, severity_components={}, note="bad",
        )
        try:
            logger.log_contradiction(bad_contradiction, v1.version_id)
            raise AssertionError("log_contradiction accepted empty claim_ids")
        except ConstitutionViolation:
            pass

        try:
            logger.log_event("claim.test", {"source_id": ""})
            raise AssertionError("log_event(claim.*) accepted empty source_id")
        except ConstitutionViolation:
            pass

        # ---- (6) Rich-API methods -------------------------------------
        logger.log_step("ingest", v1.version_id, status="ok",
                        payload={"items": 18})
        from datetime import timedelta
        # log_connector_fetch expects items with item_id (not claim_id);
        # synthesize fake SourceItem-shaped dicts so the smoke test
        # doesn't depend on the connector layer.
        fake_items = [{"item_id": f"smoke-item-{i}"} for i in range(3)]
        logger.log_connector_fetch(
            "newsapi", "smoke-topic",
            datetime.now(timezone.utc) - timedelta(days=7),
            fake_items, cache_hit=False, version_id=v1.version_id,
        )

        if v1.contradictions:
            flag_id = logger.log_contradiction_flag(
                v1.contradictions[0].contradiction_id,
                reason="smoke flag", flagged_by="smoke-runner",
                version_id=v1.version_id,
            )
            assert flag_id, "log_contradiction_flag returned empty flag_id"
            flag_events = [
                e for e in logger.local.all_events()
                if e.event_type == "contradiction.flagged"
            ]
            assert flag_events, "no contradiction.flagged events recorded"

        trail = logger.get_audit_trail(v2.version_id, full_chain=True)
        assert isinstance(trail, tuple)
        assert any(
            e.version_id == v1.version_id for e in trail
        ) or any(
            e.version_id == v2.version_id for e in trail
        ), (
            "get_audit_trail did not return events from either version."
        )

        report = logger.export_report(v2.version_id, format="markdown")
        assert "# Provenance Report" in report
        assert "Run Timeline" in report
        assert "Connector Activity" in report
        assert "Contradictions Flagged" in report

        rewind = logger.rewind_with_provenance(v2.version_id)
        assert rewind is not None
        assert rewind.version.version_id == v2.version_id
        assert rewind.parent_chain and rewind.parent_chain[-1].version_id == v1.version_id
        assert isinstance(rewind.events_for_target, tuple)

        # ---- (7) Langfuse no-op witness -------------------------------
        # Real key would turn these into actual API calls; with no key
        # set we just need to confirm the right call sites were hit.
        methods_seen = {c.method for c in logger.langfuse.recorded_calls}
        assert "trace.create" in methods_seen
        assert any(m in methods_seen for m in ("span.create", "generation.create"))

        if verbose:
            print("P113 provenance layer smoke OK")
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = (
    "ConstitutionViolation",
    "LangfuseCallRecord",
    "LangfuseProvenanceHooks",
    "LivingNarrativeFabricProvenance",
    "LocalProvenanceLog",
    "ProvenanceEvent",
    "ProvenanceLogger",
    "ProvenanceRewindResult",
    "build_provenance_logger",
    "run_smoke_test",
    "with_provenance",
)


if __name__ == "__main__":  # pragma: no cover
    run_smoke_test()
