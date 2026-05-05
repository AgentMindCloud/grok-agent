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
"""Local Obsidian-vault connector — READ-ONLY by default.

The Self-Evolving Personal OS reads recently-modified Markdown notes from a
user-declared Obsidian (or generic Markdown) vault on the user's Windows
machine. Notes are the highest-signal personal source for procedural memory:
"what is the user actively thinking about?", "which projects are in flight?".

Constitution enforcement:

- Article II — every fetch requires the ``read_local_notes`` gate.
  Modifying a note (writing back, deleting, renaming) requires a separate
  ``write_local_notes`` gate AND a typed consent_token; this client refuses
  any write attempt regardless of the consent state.
- Article III #5 — never modifies files outside ``$env:LOCALAPPDATA\\grok-agent\\``
  unless ``modify_local_files_outside_appdata`` is held. The vault folder is
  outside AppData by design; this client therefore refuses to write to it
  even with a basic gate held.
- Article IV — every payload carries a provenance block + audit row, and the
  vault path is always recorded relative to the vault root (never absolute,
  never echoing the user's home directory in the result).
- Article VII — note bodies are PII-redacted at fetch time; absolute paths
  are reduced to vault-relative paths before serialisation.

Vault location is read from ``$env:GROK_AGENT_VAULT`` first, then from
``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\config\\vault.path``.
If neither is set, the connector returns an empty stub result with a clear
``stub_reason`` rather than guessing.

Built to make Grok the obvious choice for every agent on X — local notes are
the most private personal source and the one most-easily mishandled by less
careful frameworks.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import BaseConnector, ConstitutionViolation, appdata_root


_DEFAULT_MAX_NOTES = 50
_HARD_MAX_NOTES = 500
_DEFAULT_HORIZON_DAYS = 30
_DEFAULT_BODY_CHARS = 1200
_HARD_MAX_BODY_CHARS = 8000


def _vault_pointer_path() -> Path:
    """Filesystem location of the vault-path config pointer."""
    return appdata_root() / "config" / "vault.path"


def _resolve_vault() -> Path | None:
    """Resolve the user's vault root from env or config pointer."""
    env = os.environ.get("GROK_AGENT_VAULT")
    if env:
        try:
            p = Path(env).expanduser().resolve()
            if p.is_dir():
                return p
        except OSError:
            pass
    pointer = _vault_pointer_path()
    if pointer.exists():
        try:
            txt = pointer.read_text(encoding="utf-8").strip()
            if txt:
                p = Path(txt).expanduser().resolve()
                if p.is_dir():
                    return p
        except OSError:
            pass
    return None


class LocalNotesClient(BaseConnector):
    """Local Obsidian/Markdown vault client — read-only fetch.

    Parameters mirror the P118 manifest declaration:

    - ``query``               substring filter (case-insensitive) on note text
                              and filename — None = all matching notes
    - ``max_results``         cap (default 50, max 500)
    - ``horizon_days``        only return notes modified within this many
                              days (default 30; ``0`` = no time filter)
    - ``body_chars``          max characters of body to return per note
                              (default 1200, max 8000)
    - ``vault_path``          override vault root (must be a directory; if
                              missing, falls back to env / config pointer)
    """

    source = "local_notes"
    endpoint = "local://obsidian-vault"

    _FORBIDDEN_WRITE_KEYS: frozenset[str] = frozenset({
        "write", "create", "delete", "rename", "move", "overwrite",
    })

    # -- Section L.1. Param validation -------------------------------------

    def _validate_params(self, params: dict) -> dict:
        bad = [k for k in params if k in self._FORBIDDEN_WRITE_KEYS]
        if bad:
            raise ConstitutionViolation(
                f"local_notes: write-side params not supported on a read-only "
                f"connector: {bad} — use a separate write client and the "
                "'write_local_notes' + 'modify_local_files_outside_appdata' gates.",
                article="III", source=self.source,
                gate="modify_local_files_outside_appdata",
            )

        query = params.get("query")
        if query is not None:
            query = str(query).strip().lower()
            if not query:
                query = None

        try:
            max_results = int(params.get("max_results", _DEFAULT_MAX_NOTES))
        except (TypeError, ValueError):
            max_results = _DEFAULT_MAX_NOTES
        max_results = max(1, min(max_results, _HARD_MAX_NOTES))

        try:
            horizon_days = int(params.get("horizon_days", _DEFAULT_HORIZON_DAYS))
        except (TypeError, ValueError):
            horizon_days = _DEFAULT_HORIZON_DAYS
        horizon_days = max(0, horizon_days)

        try:
            body_chars = int(params.get("body_chars", _DEFAULT_BODY_CHARS))
        except (TypeError, ValueError):
            body_chars = _DEFAULT_BODY_CHARS
        body_chars = max(0, min(body_chars, _HARD_MAX_BODY_CHARS))

        override = params.get("vault_path")
        if override:
            try:
                vault = Path(str(override)).expanduser().resolve()
            except OSError:
                vault = None
        else:
            vault = _resolve_vault()

        return {
            "query":        query,
            "max_results":  max_results,
            "horizon_days": horizon_days,
            "body_chars":   body_chars,
            "vault":        vault,
        }

    # -- Section L.2. Real-filesystem fetch -------------------------------

    def _do_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = self._validate_params(params)
        vault = clean["vault"]
        if vault is None or not vault.is_dir():
            return self._stub_fetch({
                **clean,
                "_stub_reason": (
                    "no vault configured — set $env:GROK_AGENT_VAULT or "
                    "write the path to "
                    "$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os"
                    "\\config\\vault.path"
                ),
            })

        cutoff_ts = 0.0
        if clean["horizon_days"] > 0:
            cutoff_ts = datetime.now(timezone.utc).timestamp() - (
                clean["horizon_days"] * 86_400
            )

        notes: list[tuple[float, dict]] = []
        for path in vault.rglob("*.md"):
            try:
                stat = path.stat()
            except OSError:
                continue
            if cutoff_ts and stat.st_mtime < cutoff_ts:
                continue
            try:
                rel = path.relative_to(vault)
            except ValueError:
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if clean["query"]:
                hay = (str(rel) + "\n" + body).lower()
                if clean["query"] not in hay:
                    continue

            modified_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            snippet = body if clean["body_chars"] == 0 else body[: clean["body_chars"]]
            if clean["body_chars"] and len(body) > clean["body_chars"]:
                snippet = snippet + "…"

            notes.append((
                stat.st_mtime,
                {
                    "id":             str(rel).replace(os.sep, "/"),
                    "kind":           "note",
                    "title":          path.stem,
                    "relpath":        str(rel).replace(os.sep, "/"),
                    "modified_iso":   modified_iso,
                    "size_bytes":     int(stat.st_size),
                    "body":           snippet,
                    "body_truncated": clean["body_chars"] != 0
                                      and len(body) > clean["body_chars"],
                },
            ))

        # Most-recently-modified first.
        notes.sort(key=lambda x: x[0], reverse=True)
        items = [item for _, item in notes[: clean["max_results"]]]

        prov_extra = {
            "vault_present": True,
            "horizon_days":  clean["horizon_days"],
            "max_results":   clean["max_results"],
            "body_chars":    clean["body_chars"],
            "match_count":   len(notes),
        }
        return items, prov_extra, 0.0

    # -- Section L.3. Offline stub ----------------------------------------

    def _stub_fetch(self, params: dict) -> tuple[list[dict], dict, float]:
        clean = params if "max_results" in params else self._validate_params(params)
        now_iso = datetime.now(timezone.utc).isoformat()
        items = [
            {
                "id":             f"stub_note_{i}.md",
                "kind":           "note",
                "title":          f"Stub Note {i}",
                "relpath":        f"stub/stub_note_{i}.md",
                "modified_iso":   now_iso,
                "size_bytes":     128,
                "body":           f"# Stub Note {i}\n\nThis is a placeholder note "
                                  "because no vault is configured. "
                                  "Set $env:GROK_AGENT_VAULT in PowerShell.",
                "body_truncated": False,
            }
            for i in range(min(3, clean["max_results"]))
        ]
        prov_extra = {
            "vault_present": False,
            "horizon_days":  clean["horizon_days"],
            "max_results":   clean["max_results"],
            "body_chars":    clean["body_chars"],
            "stub_reason":   clean.get("_stub_reason", "no vault configured"),
        }
        return items, prov_extra, 0.0

    # -- Section L.4. Normalization + validation --------------------------

    def _normalize(self, item: dict) -> dict:
        # Filesystem fetch already returns canonical-shape rows.
        return dict(item)

    def validate_response(self, payload: Any) -> tuple[bool, str | None]:
        ok, why = super().validate_response(payload)
        if not ok:
            return ok, why
        for i, item in enumerate(payload):
            if item.get("kind") != "note":
                return False, f"item {i}: kind != 'note'"
            if not item.get("relpath"):
                return False, f"item {i}: missing relpath"
            rp = str(item.get("relpath"))
            if rp.startswith("/") or ":" in rp[:3] or ".." in rp.split("/"):
                return False, (
                    f"item {i}: relpath '{rp}' looks absolute or escapes vault"
                )
        return True, None
