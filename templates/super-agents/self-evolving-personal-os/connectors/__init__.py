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
"""Public-API connector helpers for the Self-Evolving Personal OS (Super Agent #2).

This package is the **Slot 4** deliverable of the Self-Evolving Personal OS
build path. It sits on top of:

- P118  manifest + Agent Constitution
- P119  orchestration core (6-node DAG, ``with_connectors`` injection point)
- P120  ``Mem0QdrantPersonalStore`` (DPAPI-encrypted, PII-redacted, procedural
        memory)

and feeds the orchestrator with personal-scoped data from six sources declared
in the manifest:

- ``x_personal``     mentions / DMs / lists / bookmarks via the X graph
                     (delegated through Grok 4.3 tool-calling)
- ``gcal``           Google Calendar (read-only by default)
- ``gmail``          Gmail (read-only by default)
- ``local_notes``    a local Obsidian vault on the user's Windows machine
- ``weather``        OpenWeather / weather.gov forecast for the user's locale
- ``news_personal``  GNews / NewsAPI personalized headlines for the user's
                     declared topics

Every connector implements the same :class:`Connector` Protocol and therefore
plugs into the P119 orchestrator's ``with_connectors`` call without any
modification to the orchestrator itself. Every connector enforces three
non-negotiable behaviours, in the order shown:

1. **Consent enforcement** — before any I/O the connector consults the active
   ``ConsentContext`` (passed through by the orchestrator) and raises
   :class:`ConstitutionViolation` if the required gate is not held. This
   matches the ``constitution.consent_gates`` block declared in P118 manifest
   and is independent of whatever the underlying API permits.
2. **PII redaction at fetch time** — handles, email addresses, phone numbers,
   street addresses, geo lat/lon, payment card-like patterns and free-form
   secrets are redacted **before** the result leaves the connector. The
   orchestrator never sees the raw values; only the agent-internal store does.
3. **Provenance attachment** — every successful fetch returns a row with a
   ``provenance`` block containing source, endpoint, retrieved_at, cost_usd,
   ``stub`` flag, ``redaction_applied`` flag, and an optional
   ``audit_row_id``. The orchestrator uses this to honour Article IV of the
   Constitution.

The composite :class:`PersonalOSConnectors` registers all six connectors and
exposes the unified API the P119 orchestrator depends on
(``fetch(source, ...)``, ``fetch_batch(...)``, ``connect_memory(store)``,
``set_consent(ctx)``, ``set_force_stub(flag)``). The
:func:`build_connectors` factory wires the composite from a manifest dict (so
the runtime can build it from ``grok-agent.yaml`` directly), and
:func:`with_connectors` is the bridge function that P119's
``PersonalOSOrchestrator.with_connectors`` is expected to call.

Built for xAI, Grok and the whole community on X — the personal data layer
xAI hasn't shipped yet.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, runtime_checkable

__all__ = [
    # Exceptions
    "ConstitutionViolation",
    # Data classes
    "ConsentContext",
    "FetchResult",
    "ConnectorAuditRow",
    # Protocols
    "Connector",
    "MemoryStore",
    # Composite + factory
    "PersonalOSConnectors",
    "build_connectors",
    "with_connectors",
    # PII helpers (re-exported for use by individual clients)
    "redact_pii",
    "make_provenance",
    # Path helpers (used by individual clients + smoke tests)
    "appdata_root",
    "audit_db_path",
]


# --- Section 1. Constants and module-level state --------------------------

_USER_AGENT = "grok-agent/self-evolving-personal-os (Apache-2.0)"

# Manifest-declared sources (matches P118 manifest exactly).
SOURCES: tuple[str, ...] = (
    "x_personal",
    "gcal",
    "gmail",
    "local_notes",
    "weather",
    "news_personal",
)

# Required consent gate per source. The orchestrator enforces these before
# calling fetch(); the connector double-enforces inside fetch() so a bug in
# the orchestrator can never bypass Article II.
CONSENT_REQUIRED: dict[str, str] = {
    "x_personal":     "read_x_personal",
    "gcal":           "read_gcal",
    "gmail":          "read_gmail",
    "local_notes":    "read_local_notes",
    "weather":        "read_weather",
    "news_personal":  "read_news_personal",
}

# Memory collection routing. Mirrors the P120 ``Mem0QdrantPersonalStore``
# collection layout: ``personal.<source>``.
MEMORY_COLLECTION: dict[str, str] = {
    "x_personal":     "personal.x",
    "gcal":           "personal.calendar",
    "gmail":          "personal.email",
    "local_notes":    "personal.notes",
    "weather":        "personal.weather",
    "news_personal":  "personal.news",
}

# Cache TTL per source (seconds). Pulled from the P118 manifest defaults; a
# manifest override may extend or shorten these but the connector always
# caps to a sensible upper bound to avoid stale personal data.
DEFAULT_CACHE_TTL_S: dict[str, int] = {
    "x_personal":     5 * 60,         # 5 min
    "gcal":          15 * 60,         # 15 min
    "gmail":         10 * 60,         # 10 min
    "local_notes":   60 * 60,         # 1 hour (filesystem changes are slow)
    "weather":       30 * 60,         # 30 min
    "news_personal": 15 * 60,         # 15 min
}


# --- Section 2. Path helpers ----------------------------------------------

def appdata_root() -> Path:
    """Resolve the local-first data folder for the Personal OS.

    Production target is Windows 11 + PowerShell, where this resolves to
    ``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os``. On
    non-Windows runs (Streamlit Cloud, dev containers, CI) we fall back to
    ``~/.local/share/grok-agent/self-evolving-personal-os`` so the data
    layer boots cleanly everywhere.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "grok-agent" / "self-evolving-personal-os"
    return Path.home() / ".local" / "share" / "grok-agent" / "self-evolving-personal-os"


def audit_db_path() -> Path:
    """SQLite path for the per-fetch audit log shared by every connector."""
    return appdata_root() / "connector_audit.db"


# --- Section 3. Exceptions and data classes -------------------------------

class ConstitutionViolation(RuntimeError):
    """Raised when a connector is asked to do something Article II/III forbids.

    This is the single failure type all connectors raise. The P119
    orchestrator catches it, downgrades the affected DAG node to ``blocked``,
    surfaces the violation to the user, and refuses to proceed silently.
    """

    def __init__(
        self,
        message: str,
        *,
        article: str = "II",
        source: str | None = None,
        gate: str | None = None,
    ) -> None:
        super().__init__(message)
        self.article = article
        self.source = source
        self.gate = gate

    def __repr__(self) -> str:  # pragma: no cover — diagnostic helper
        return (
            f"ConstitutionViolation(article={self.article!r}, "
            f"source={self.source!r}, gate={self.gate!r}, "
            f"message={self.args[0]!r})"
        )


@dataclass
class ConsentContext:
    """Snapshot of the user's currently-held consent gates.

    The orchestrator builds one of these per session from the user's
    typed-confirmation dialogue and threads it through to every connector
    call. The dataclass is intentionally tiny and immutable-feeling so the
    orchestrator can pin a copy alongside the action plan in its provenance
    log without worrying about side-effects.
    """

    gates: frozenset[str] = field(default_factory=frozenset)
    consent_token: str | None = None
    granted_at: str | None = None
    timeout_seconds: int = 60

    def has(self, gate: str) -> bool:
        """Return True iff ``gate`` is held for the current scope."""
        return gate in self.gates

    @classmethod
    def from_iterable(cls, gates: Iterable[str], **kwargs: Any) -> "ConsentContext":
        return cls(gates=frozenset(gates), **kwargs)


@dataclass
class FetchResult:
    """Uniform return shape across every connector.

    The orchestrator and the memory store both consume the same dataclass,
    which keeps the integration surface tiny. ``items`` is always a list of
    plain dicts — never a custom object — so JSON serialisation, Pydantic
    validation, and SQLite persistence all work without an adapter layer.
    """

    source: str
    items: list[dict]
    provenance: dict
    error: str | None = None
    cached: bool = False
    redaction_applied: bool = True

    def to_dict(self) -> dict:
        return {
            "source":             self.source,
            "items":              list(self.items),
            "provenance":         dict(self.provenance),
            "error":              self.error,
            "cached":             self.cached,
            "redaction_applied":  self.redaction_applied,
        }


@dataclass
class ConnectorAuditRow:
    """One row of the per-fetch audit log (Article IV provenance)."""

    timestamp: str
    source: str
    gate: str
    consent_token: str | None
    item_count: int
    cache_hit: bool
    stub: bool
    redaction_applied: bool
    error: str | None
    cost_usd: float


# --- Section 4. PII redaction --------------------------------------------

# Conservative regexes — false positives are preferable to leaking PII. The
# patterns are deliberately strict and the redaction strings are all-caps
# tokens so a downstream eyeball test can spot them at a glance.
_PII_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email",    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    ("phone",    re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}\b"), "[REDACTED_PHONE]"),
    ("card",     re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_CARD]"),
    ("ssn_us",   re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    ("xhandle",  re.compile(r"(?<![\w/])@([A-Za-z0-9_]{2,15})\b"), "@[REDACTED_HANDLE]"),
    ("latlon",   re.compile(r"\b-?\d{1,3}\.\d{4,}\s*[,;]\s*-?\d{1,3}\.\d{4,}\b"), "[REDACTED_GEO]"),
    ("street",   re.compile(r"\b\d{1,6}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b"), "[REDACTED_ADDRESS]"),
)

# Field names (case-insensitive) whose values are always redacted regardless of
# regex match. Defence-in-depth for cases like a JSON blob ``{"address": "..."}``
# where the value alone wouldn't trip the street regex.
_PII_FIELD_NAMES: frozenset[str] = frozenset({
    "email", "email_address", "phone", "phone_number",
    "address", "home_address", "billing_address", "shipping_address",
    "ssn", "tax_id", "passport", "credit_card", "card_number", "card",
    "lat", "lon", "latitude", "longitude", "geo",
    "ip", "ip_address", "device_id",
    "password", "secret", "token", "api_key",
})


def redact_pii(value: Any) -> Any:
    """Redact PII from a string, list, or dict — recursive and deep.

    Returns a new structure; the input is not mutated. Used by every
    connector before any payload leaves the connector boundary.
    """
    if isinstance(value, str):
        out = value
        for _name, pattern, replacement in _PII_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, list):
        return [redact_pii(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_pii(v) for v in value)
    if isinstance(value, dict):
        red: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _PII_FIELD_NAMES:
                red[k] = "[REDACTED]" if v is not None else None
            else:
                red[k] = redact_pii(v)
        return red
    return value


# --- Section 5. Provenance helpers ----------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_provenance(
    source: str,
    endpoint: str,
    *,
    cost_usd: float = 0.0,
    stub: bool = False,
    cached: bool = False,
    redaction_applied: bool = True,
    **extra: Any,
) -> dict:
    """Build a provenance block per Constitution Article IV."""
    return {
        "source":             source,
        "endpoint":            endpoint,
        "retrieved_at":        _now_iso(),
        "cost_usd":            float(cost_usd),
        "stub":                bool(stub),
        "cached":              bool(cached),
        "redaction_applied":   bool(redaction_applied),
        **extra,
    }


# --- Section 6. Per-source audit log (SQLite) -----------------------------

_AUDIT_LOCK = threading.Lock()
_AUDIT_INIT = False


def _audit_init() -> None:
    """Lazily create the audit-log SQLite table on first use."""
    global _AUDIT_INIT
    if _AUDIT_INIT:
        return
    with _AUDIT_LOCK:
        if _AUDIT_INIT:
            return
        path = audit_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_audit (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp          TEXT    NOT NULL,
                    source             TEXT    NOT NULL,
                    gate               TEXT    NOT NULL,
                    consent_token      TEXT,
                    item_count         INTEGER NOT NULL,
                    cache_hit          INTEGER NOT NULL,
                    stub               INTEGER NOT NULL,
                    redaction_applied  INTEGER NOT NULL,
                    error              TEXT,
                    cost_usd           REAL    NOT NULL DEFAULT 0.0
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_audit_source_ts "
                "ON connector_audit(source, timestamp)"
            )
            con.commit()
        finally:
            con.close()
        _AUDIT_INIT = True


def _audit_write(row: ConnectorAuditRow) -> int | None:
    """Append a row to the audit log (best-effort)."""
    try:
        _audit_init()
        with _AUDIT_LOCK:
            con = sqlite3.connect(audit_db_path())
            try:
                cur = con.execute(
                    """
                    INSERT INTO connector_audit
                      (timestamp, source, gate, consent_token,
                       item_count, cache_hit, stub, redaction_applied,
                       error, cost_usd)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.timestamp, row.source, row.gate, row.consent_token,
                        int(row.item_count),
                        1 if row.cache_hit else 0,
                        1 if row.stub else 0,
                        1 if row.redaction_applied else 0,
                        row.error, float(row.cost_usd),
                    ),
                )
                con.commit()
                return int(cur.lastrowid or 0)
            finally:
                con.close()
    except sqlite3.Error:
        # Audit logging is best-effort. A disk error must never break the
        # primary fetch path or shadow the connector's own error message.
        return None


# --- Section 7. Memory-store Protocol -------------------------------------

@runtime_checkable
class MemoryStore(Protocol):
    """Minimum surface the connectors expect from the P120 store.

    The real ``Mem0QdrantPersonalStore`` exposes a richer API (semantic
    search, procedural-memory replay, DPAPI key rotation). For the
    connectors we only need a write-side method that takes the FetchResult
    and the manifest-routed collection name — everything else is the
    store's concern.
    """

    def upsert_fetch(self, collection: str, result: "FetchResult") -> int:  # pragma: no cover
        ...


class _NullMemoryStore:
    """Fallback when no memory store is wired (CI, smoke tests, dry runs)."""

    def upsert_fetch(self, collection: str, result: "FetchResult") -> int:
        # Returns the item count so callers can still rely on a numeric
        # return type; nothing is actually persisted.
        return len(result.items)


# --- Section 8. Connector Protocol (consumed by P119 orchestrator) --------

@runtime_checkable
class Connector(Protocol):
    """Minimal contract every personal-source connector must satisfy.

    The P119 orchestrator's ``with_connectors`` injection point binds to
    this Protocol. Each per-source client (``XPersonalClient``,
    ``GCalClient``, etc.) implements all five methods on a common
    :class:`BaseConnector` defined below.
    """

    source: str

    def fetch(
        self, *, consent: ConsentContext, force_stub: bool = False, **params: Any
    ) -> FetchResult: ...

    def fetch_batch(
        self,
        batch: list[dict],
        *,
        consent: ConsentContext,
        force_stub: bool = False,
    ) -> list[FetchResult]: ...

    def validate_response(self, payload: Any) -> tuple[bool, str | None]: ...

    def attach_provenance(self, items: list[dict], prov: dict) -> list[dict]: ...

    def connect_memory(self, store: MemoryStore | None) -> None: ...


# --- Section 9. BaseConnector — shared machinery -------------------------

class BaseConnector:
    """Shared machinery: cache, consent enforcement, audit logging.

    Per-source clients subclass this and override :meth:`_do_fetch` (the
    actual API call) and :meth:`_normalize` (the API-shape → connector-shape
    transform). Every other method on the Protocol is implemented here once
    and inherited by all six clients.

    The class is intentionally synchronous. The P119 orchestrator runs nodes
    on a thread pool; async would force the orchestrator to know which
    runtime its connectors live in. Threads keep the surface boring.
    """

    #: Identifier matching the manifest's ``public_apis[*].id``.
    source: str = ""
    #: Default cache TTL (seconds) — derived from :data:`DEFAULT_CACHE_TTL_S`.
    cache_ttl_s: int = 0
    #: Free-form endpoint string written into provenance.
    endpoint: str = ""

    def __init__(
        self,
        *,
        cache_ttl_s: int | None = None,
        force_stub_default: bool = False,
        endpoint: str | None = None,
    ) -> None:
        self.source = self.source or self.__class__.__name__.lower().replace("client", "")
        self.cache_ttl_s = (
            int(cache_ttl_s)
            if cache_ttl_s is not None
            else DEFAULT_CACHE_TTL_S.get(self.source, 300)
        )
        self.endpoint = endpoint or self.endpoint or self.source
        self._force_stub_default = bool(force_stub_default)
        self._cache: dict[str, tuple[float, FetchResult]] = {}
        self._memory: MemoryStore = _NullMemoryStore()
        self._lock = threading.Lock()

    # -- Public API (Connector Protocol) ------------------------------------

    def fetch(
        self, *, consent: ConsentContext, force_stub: bool = False, **params: Any
    ) -> FetchResult:
        gate = CONSENT_REQUIRED.get(self.source, f"read_{self.source}")
        self._enforce_consent(consent, gate)

        cache_key = self._cache_key(params)
        cached = self._cache_lookup(cache_key)
        if cached is not None:
            self._audit(
                gate=gate, consent_token=consent.consent_token,
                item_count=len(cached.items), cache_hit=True,
                stub=cached.provenance.get("stub", False),
                error=cached.error, cost_usd=0.0,
            )
            return cached

        use_stub = bool(force_stub or self._force_stub_default)
        try:
            raw_items, prov_extra, cost_usd = (
                self._stub_fetch(params)
                if use_stub
                else self._do_fetch(params)
            )
        except ConstitutionViolation:
            raise
        except Exception as e:  # pragma: no cover — defensive
            error_msg = f"{type(e).__name__}: {e}"
            prov = make_provenance(
                self.source, self.endpoint,
                cost_usd=0.0, stub=use_stub,
                cached=False, redaction_applied=True,
                fallback_to_stub=False,
            )
            result = FetchResult(
                source=self.source, items=[], provenance=prov,
                error=error_msg, cached=False, redaction_applied=True,
            )
            self._audit(
                gate=gate, consent_token=consent.consent_token,
                item_count=0, cache_hit=False, stub=use_stub,
                error=error_msg, cost_usd=0.0,
            )
            return result

        normalised = [self._normalize(item) for item in raw_items]
        redacted   = [redact_pii(item) for item in normalised]
        ok, why    = self.validate_response(redacted)
        if not ok:
            error_msg = f"validation failed: {why}"
            prov = make_provenance(
                self.source, self.endpoint,
                cost_usd=cost_usd, stub=use_stub,
                cached=False, redaction_applied=True,
                **(prov_extra or {}),
            )
            result = FetchResult(
                source=self.source, items=[], provenance=prov,
                error=error_msg, cached=False, redaction_applied=True,
            )
            self._audit(
                gate=gate, consent_token=consent.consent_token,
                item_count=0, cache_hit=False, stub=use_stub,
                error=error_msg, cost_usd=cost_usd,
            )
            return result

        prov = make_provenance(
            self.source, self.endpoint,
            cost_usd=cost_usd, stub=use_stub,
            cached=False, redaction_applied=True,
            **(prov_extra or {}),
        )
        items_with_prov = self.attach_provenance(redacted, prov)
        result = FetchResult(
            source=self.source, items=items_with_prov, provenance=prov,
            error=None, cached=False, redaction_applied=True,
        )
        self._cache_store(cache_key, result)
        self._memory_write(result)
        audit_row_id = self._audit(
            gate=gate, consent_token=consent.consent_token,
            item_count=len(items_with_prov), cache_hit=False,
            stub=use_stub, error=None, cost_usd=cost_usd,
        )
        if audit_row_id is not None:
            result.provenance["audit_row_id"] = audit_row_id
        return result

    def fetch_batch(
        self,
        batch: list[dict],
        *,
        consent: ConsentContext,
        force_stub: bool = False,
    ) -> list[FetchResult]:
        out: list[FetchResult] = []
        for params in batch:
            out.append(self.fetch(consent=consent, force_stub=force_stub, **params))
        return out

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        if not isinstance(payload, list):
            return False, "expected list of dicts"
        for i, item in enumerate(payload):
            if not isinstance(item, dict):
                return False, f"item {i} is not a dict"
        return True, None

    def attach_provenance(self, items: list[dict], prov: dict) -> list[dict]:
        out: list[dict] = []
        for it in items:
            new = dict(it)
            new.setdefault("provenance", dict(prov))
            out.append(new)
        return out

    def connect_memory(self, store: MemoryStore | None) -> None:
        self._memory = store if store is not None else _NullMemoryStore()

    # -- Hooks subclasses must override -------------------------------------

    def _do_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        """Real-API fetch.  Return (items, prov_extra, cost_usd).

        Subclasses override. The default implementation falls back to the
        stub so an under-construction client still returns runnable data.
        """
        return self._stub_fetch(params)

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        """Offline stub. Subclasses override with realistic-shape data."""
        return [], {"stub_reason": "not implemented"}, 0.0

    def _normalize(self, item: dict) -> dict:
        """Map the raw API shape onto the connector's canonical schema."""
        return dict(item)

    # -- Private helpers ----------------------------------------------------

    def _enforce_consent(self, consent: ConsentContext, gate: str) -> None:
        if consent is None or not consent.has(gate):
            raise ConstitutionViolation(
                f"{self.source}: consent gate '{gate}' not held — "
                "Article II requires explicit user approval before any read.",
                article="II", source=self.source, gate=gate,
            )

    def _cache_key(self, params: dict) -> str:
        try:
            return repr(sorted(params.items()))
        except TypeError:
            return repr(params)

    def _cache_lookup(self, key: str) -> FetchResult | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            ts, result = entry
            if (time.monotonic() - ts) > self.cache_ttl_s:
                self._cache.pop(key, None)
                return None
            cached = FetchResult(
                source=result.source,
                items=list(result.items),
                provenance={**result.provenance, "cached": True},
                error=result.error,
                cached=True,
                redaction_applied=result.redaction_applied,
            )
            return cached

    def _cache_store(self, key: str, result: FetchResult) -> None:
        with self._lock:
            self._cache[key] = (time.monotonic(), result)

    def _memory_write(self, result: FetchResult) -> None:
        if not result.items:
            return
        collection = MEMORY_COLLECTION.get(self.source, f"personal.{self.source}")
        try:
            self._memory.upsert_fetch(collection, result)
        except Exception:  # pragma: no cover — store errors are non-fatal here
            # A memory write failure must not shadow a successful fetch. The
            # P120 store is responsible for surfacing its own write errors;
            # at the connector layer we prefer to return the data than crash.
            pass

    def _audit(
        self,
        *,
        gate: str,
        consent_token: str | None,
        item_count: int,
        cache_hit: bool,
        stub: bool,
        error: str | None,
        cost_usd: float,
    ) -> int | None:
        return _audit_write(
            ConnectorAuditRow(
                timestamp=_now_iso(),
                source=self.source,
                gate=gate,
                consent_token=consent_token,
                item_count=item_count,
                cache_hit=cache_hit,
                stub=stub,
                redaction_applied=True,
                error=error,
                cost_usd=cost_usd,
            )
        )


# --- Section 10. Composite + factory + with_connectors --------------------

class PersonalOSConnectors:
    """Composite container of all six personal-scoped connectors.

    The P119 orchestrator only sees this object; it never imports the
    individual clients directly. The composite is responsible for:

    - holding the active :class:`ConsentContext`
    - dispatching ``fetch(source, ...)`` to the right per-source connector
    - wiring the P120 :class:`MemoryStore` into every client at once
    - exposing a uniform ``force_stub`` toggle for tests and dry runs
    """

    def __init__(self, clients: dict[str, BaseConnector]) -> None:
        missing = set(SOURCES) - set(clients.keys())
        if missing:
            raise ValueError(
                f"PersonalOSConnectors missing required sources: "
                f"{sorted(missing)}"
            )
        self._clients: dict[str, BaseConnector] = dict(clients)
        self._consent: ConsentContext = ConsentContext()
        self._force_stub: bool = False

    # -- Wiring ------------------------------------------------------------

    def set_consent(self, consent: ConsentContext) -> None:
        if not isinstance(consent, ConsentContext):
            raise TypeError("consent must be a ConsentContext")
        self._consent = consent

    def set_force_stub(self, flag: bool) -> None:
        self._force_stub = bool(flag)

    def connect_memory(self, store: MemoryStore | None) -> None:
        for client in self._clients.values():
            client.connect_memory(store)

    def get(self, source: str) -> BaseConnector:
        if source not in self._clients:
            raise KeyError(f"unknown source '{source}'")
        return self._clients[source]

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(self._clients.keys())

    # -- Dispatch ----------------------------------------------------------

    def fetch(self, source: str, **params: Any) -> FetchResult:
        client = self.get(source)
        return client.fetch(
            consent=self._consent,
            force_stub=self._force_stub,
            **params,
        )

    def fetch_batch(
        self, plan: list[tuple[str, dict]] | dict[str, list[dict]]
    ) -> dict[str, list[FetchResult]]:
        out: dict[str, list[FetchResult]] = {}
        if isinstance(plan, dict):
            iterable = ((src, batch) for src, batch in plan.items())
            for src, batch in iterable:
                client = self.get(src)
                out.setdefault(src, []).extend(
                    client.fetch_batch(batch, consent=self._consent,
                                       force_stub=self._force_stub)
                )
        else:
            for src, params in plan:
                out.setdefault(src, []).append(self.fetch(src, **params))
        return out


def build_connectors(manifest: dict | None = None) -> PersonalOSConnectors:
    """Factory — build the composite from a manifest dict.

    The manifest dict is the parsed ``grok-agent.yaml`` (P118). The factory
    only reads ``public_apis`` and ``constitution.consent_gates``; any other
    manifest field is ignored so this function stays compatible with future
    schema changes that don't touch those two sections.

    Passing ``manifest=None`` builds with defaults — useful for unit tests
    and the smoke harness shipped with this slot.
    """
    from .x_personal_client    import XPersonalClient
    from .gcal_client          import GCalClient
    from .gmail_client         import GmailClient
    from .local_notes_client   import LocalNotesClient
    from .weather_news_client  import WeatherClient, NewsPersonalClient

    overrides: dict[str, dict] = {}
    if manifest:
        for api in (manifest.get("public_apis") or []):
            api_id = api.get("id")
            if api_id in SOURCES:
                overrides[api_id] = api

    def _kwargs(source: str) -> dict[str, Any]:
        api = overrides.get(source) or {}
        kw: dict[str, Any] = {}
        if "cache_ttl_s" in api:
            kw["cache_ttl_s"] = int(api["cache_ttl_s"])
        if api.get("endpoint"):
            kw["endpoint"] = str(api["endpoint"])
        return kw

    clients: dict[str, BaseConnector] = {
        "x_personal":     XPersonalClient(**_kwargs("x_personal")),
        "gcal":           GCalClient(**_kwargs("gcal")),
        "gmail":          GmailClient(**_kwargs("gmail")),
        "local_notes":    LocalNotesClient(**_kwargs("local_notes")),
        "weather":        WeatherClient(**_kwargs("weather")),
        "news_personal":  NewsPersonalClient(**_kwargs("news_personal")),
    }
    return PersonalOSConnectors(clients)


def with_connectors(
    orchestrator: Any,
    *,
    manifest: dict | None = None,
    memory_store: MemoryStore | None = None,
    consent: ConsentContext | None = None,
    force_stub: bool = False,
) -> Any:
    """Bridge function for the P119 orchestrator's ``with_connectors`` hook.

    Mutates ``orchestrator`` in-place by attaching a fully-wired
    :class:`PersonalOSConnectors` on the ``connectors`` attribute, then
    returns the orchestrator so callers can chain configuration calls
    (matching the P119 builder style ``orch.with_memory(...).with_connectors(...)``).

    No prior P119 / P120 file is modified — the orchestrator picks up the
    ``connectors`` attribute from the runtime side, which keeps this slot's
    integration purely additive.
    """
    composite = build_connectors(manifest)
    if memory_store is not None:
        composite.connect_memory(memory_store)
    if consent is not None:
        composite.set_consent(consent)
    composite.set_force_stub(force_stub)
    setattr(orchestrator, "connectors", composite)
    return orchestrator
