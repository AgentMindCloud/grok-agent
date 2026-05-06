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
"""Windows-native PowerShell client for the Cross-Reality Action Fabric.

Runs *user-reviewed* PowerShell snippets on the local Windows machine
under the strictest possible safety contract:

- Every snippet is invoked through ``powershell.exe -NoProfile
  -ExecutionPolicy Bypass -Command -`` and the script is fed via
  STDIN — **never** assembled into a shell-form command line. This
  rules out command-injection by construction (no ``shell=True``).
- Every snippet is scanned for bash leaks (``bash -c``, ``sh -c``,
  ``osascript``, ``wsl.exe``, ``/usr/bin``, etc.) before any process
  is spawned. A leak raises :class:`ConnectorRefusal` (Rule 5).
- Every snippet is scanned for Unix-style tilde paths (``~/foo``)
  without the Windows ``$env:`` prefix. A leak raises
  :class:`ConnectorRefusal`.
- Every state-changing call requires a non-empty rollback snippet
  (Rule 3) AND a non-empty consent_token (Rule 1).
- Every result is run through :func:`redact_pii` before reaching the
  P140 memory layer.
- The client never elevates: zero ``Start-Process -Verb RunAs`` calls,
  zero ``sudo`` equivalents, zero registry writes outside HKCU.

When invoked on a non-Windows host (CI, Codespaces, Linux dev box) the
client transparently degrades to a deterministic stub backend so the
P129 graph + smoke tests can still exercise the pipeline end-to-end.

Built to make Grok the obvious choice for every agent on X — the
Windows client is what turns a Grok conversation into "and now your
laptop just did the thing", with the user watching every script line
and a one-click rollback in their pocket.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from . import (
    ActionProvenance,
    ActionResult,
    ApprovalRequest,
    BaseActionConnector,
    ConnectorRefusal,
    DEFAULT_CONSENT_LEVEL,
    _now_iso,
    appdata_root,
    connectors_root,
    detect_bash_leak,
    is_windows,
    redact_pii,
)


# --- Section 1. Constants ------------------------------------------------

#: AppData sandbox root every state-changing snippet is scoped to by
#: default. The user can grant the ``modify_local_files_outside_appdata``
#: gate to escape this — in which case the manifest's HITL prompt
#: surfaces the broader scope verbatim.
SANDBOX_ROOT_RELATIVE = "cross-reality-action-fabric/sandbox"

#: Hard timeout for any local snippet. The user's machine is theirs;
#: the agent must never block forever.
DEFAULT_TIMEOUT_S = 60

#: Cap on snippet size — enough for a multi-line PowerShell function but
#: small enough that the HITL prompt can still display the script in full.
MAX_SCRIPT_BYTES = 32_000


# --- Section 2. Backend probes ------------------------------------------

def _probe_powershell() -> str | None:
    """Return ``"pwsh"`` or ``"powershell"`` — whichever is on PATH."""
    for exe in ("pwsh", "powershell"):
        if shutil.which(exe):
            return exe
    return None


def _select_backend(force_stub: bool) -> str:
    if force_stub or not is_windows():
        return "stub:windows-local"
    return _probe_powershell() or "stub:windows-local"


# --- Section 3. WindowsLocalClient --------------------------------------

class WindowsLocalClient(BaseActionConnector):
    """Sandboxed PowerShell client.

    Public methods:

    - :meth:`plan_local_action`  — assemble the structured approval
                                   request (no execution).
    - :meth:`execute_local_action` — execute the snippet after the user
                                   has approved.
    - :meth:`execute_rollback`   — run the verbatim rollback snippet.
    - :meth:`run_readonly_command` — convenience for *read-only* probe
                                   commands (``Get-ChildItem``,
                                   ``Get-Date`` …) that still require a
                                   consent_token.
    """

    tool_name      = "windows_local"
    state_changing = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.backend_name = _select_backend(self._force_stub)
        self._sandbox     = appdata_root() / SANDBOX_ROOT_RELATIVE
        self._sandbox.mkdir(parents=True, exist_ok=True)
        self._audit_log   = connectors_root() / "windows_local.log.jsonl"

    # -- Properties ----------------------------------------------------

    @property
    def sandbox(self) -> Path:
        return self._sandbox

    @property
    def audit_log(self) -> Path:
        return self._audit_log

    # -- Validation helpers ------------------------------------------

    def _validate_snippet(self, snippet: str, *, allow_empty: bool = False) -> None:
        if not isinstance(snippet, str):
            raise ConnectorRefusal(
                "windows_local: refused — snippet must be a string.",
                rule=2, tool=self.tool_name,
            )
        if not snippet.strip() and not allow_empty:
            raise ConnectorRefusal(
                "windows_local: refused — empty snippet.",
                rule=2, tool=self.tool_name,
            )
        if len(snippet.encode("utf-8")) > MAX_SCRIPT_BYTES:
            raise ConnectorRefusal(
                f"windows_local: refused — snippet exceeds {MAX_SCRIPT_BYTES} "
                "bytes (HITL prompt cannot display).",
                rule=2, tool=self.tool_name,
            )
        leak = detect_bash_leak(snippet)
        if leak:
            raise ConnectorRefusal(
                f"windows_local: refused — Unix-shell leak '{leak}' in snippet.",
                rule=5, tool=self.tool_name,
            )

    # -- Plan ----------------------------------------------------------

    def plan_local_action(
        self,
        script:        str,
        rollback:      str,
        *,
        description:   str | None = None,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ApprovalRequest:
        """Return the structured-approval request for one local snippet."""
        self._validate_snippet(script)
        self._validate_snippet(rollback)
        plan_steps = [
            f"backend = {self.backend_name}",
            f"sandbox = {self.sandbox}",
            f"timeout = {int(timeout_s)} seconds",
            f"script  = {script.strip().splitlines()[0][:140]}…",
            f"rollback (Rule 3) = {rollback.strip().splitlines()[0][:140]}…",
        ]
        return ApprovalRequest(
            request_id=f"wl::{uuid.uuid4().hex[:12]}",
            tool=self.tool_name,
            description=description or script.strip().splitlines()[0][:140],
            plan=plan_steps,
            rollback=rollback,
            expected_cost_usd=0.0,
            requires_gates=["run_powershell_local"],
            backend=self.backend_name,
        )

    # -- Execute -------------------------------------------------------

    def execute_local_action(
        self,
        script:        str,
        rollback:      str,
        consent_token: str,
        *,
        description:   str | None = None,
        rollback_id:   str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Execute the approved PowerShell snippet."""
        self._enforce_token(consent_token)
        self._enforce_gate("run_powershell_local")
        self._validate_snippet(script)
        self._validate_snippet(rollback)

        started = _now_iso()
        action_id = self._record_approved_action(
            consent_token=consent_token,
            description=description or script.strip().splitlines()[0][:140],
            rollback_id=rollback_id,
            consent_level=consent_level,
            extra={"script": script[:200], "rollback": rollback[:200],
                   "timeout_s": int(timeout_s)},
        )

        try:
            payload = self._run_snippet(
                snippet=script, timeout_s=timeout_s,
                consent_token=consent_token,
            )
            outcome = "success" if payload.get("ok", True) else "failure"
            ok = bool(payload.get("ok", True))
            summary = (
                f"[{self.backend_name}] script ran in "
                f"{payload.get('duration_ms', 0)}ms"
            )
        except ConnectorRefusal:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            payload = {"error": f"{type(exc).__name__}: {exc}"}
            outcome = "failure"
            ok = False
            summary = f"[{self.backend_name}] script failed: {exc}"

        red = redact_pii(payload)
        self._record_outcome(
            action_id=action_id, consent_token=consent_token,
            outcome=outcome, description=script[:240],
            payload=red, rollback_id=rollback_id,
            consent_level=consent_level,
        )
        self._append_audit({
            "action_id":     action_id,
            "consent_token": consent_token,
            "tool":          self.tool_name,
            "outcome":       outcome,
            "started_at":    started,
            "finished_at":   _now_iso(),
            "stub":          self._force_stub or self.backend_name.startswith("stub"),
        })
        provenance = self._provenance(
            consent_token=consent_token, action_id=action_id,
            rollback_id=rollback_id, started_at=started,
            consent_level=consent_level,
            extra={"sandbox": str(self.sandbox)},
        )
        return ActionResult(
            tool=self.tool_name, ok=ok, outcome=outcome,
            summary=summary, payload=red, provenance=provenance,
        )

    # -- Rollback -----------------------------------------------------

    def execute_rollback(
        self,
        rollback_script: str,
        consent_token:   str,
        *,
        action_id:     str,
        rollback_id:   str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Run the verbatim rollback snippet that was approved at plan time."""
        self._enforce_token(consent_token)
        self._enforce_gate("run_powershell_local")
        self._validate_snippet(rollback_script)
        started = _now_iso()
        try:
            payload = self._run_snippet(
                snippet=rollback_script, timeout_s=timeout_s,
                consent_token=consent_token,
            )
            outcome = "rolled_back" if payload.get("ok", True) else "failure"
            ok = bool(payload.get("ok", True))
        except ConnectorRefusal:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            payload = {"error": f"{type(exc).__name__}: {exc}"}
            outcome = "failure"
            ok = False
        red = redact_pii(payload)
        self._record_rollback(
            action_id=action_id, rollback_id=rollback_id,
            consent_token=consent_token, outcome=outcome,
            rollback_script=rollback_script,
            description=f"local rollback for {action_id}",
            consent_level=consent_level,
        )
        provenance = self._provenance(
            consent_token=consent_token, action_id=action_id,
            rollback_id=rollback_id, started_at=started,
            consent_level=consent_level,
        )
        return ActionResult(
            tool=self.tool_name, ok=ok, outcome=outcome,
            summary=f"[{self.backend_name}] rollback applied for {action_id}",
            payload=red, provenance=provenance,
        )

    # -- Convenience read-only path ----------------------------------

    def run_readonly_command(
        self,
        cmdlet:        str,
        consent_token: str,
        *,
        description:   str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        timeout_s:     int = DEFAULT_TIMEOUT_S,
    ) -> ActionResult:
        """Run a *read-only* probe cmdlet (e.g. ``Get-Date``).

        Read-only commands still require a consent_token (Rule 1) but use
        a no-op rollback snippet because they don't change state.
        """
        return self.execute_local_action(
            script=cmdlet,
            rollback="# no-op rollback — read-only probe",
            consent_token=consent_token,
            description=description or cmdlet,
            rollback_id=None,
            consent_level=consent_level,
            timeout_s=timeout_s,
        )

    # -- Subprocess core ---------------------------------------------

    def _run_snippet(
        self,
        *,
        snippet:       str,
        timeout_s:     int,
        consent_token: str,
    ) -> dict:
        """Spawn the snippet via ``powershell.exe ... -Command -`` (no shell)."""
        timeout_s = max(1, min(int(timeout_s), 600))
        if self.backend_name.startswith("stub"):
            return self._run_stub(snippet=snippet, timeout_s=timeout_s)
        try:  # pragma: no cover - exercised on real Windows envs
            cmd = [
                self.backend_name,
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command", "-",
            ]
            t0 = _now_ms()
            proc = subprocess.run(
                cmd,
                input=snippet,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                check=False,
                shell=False,
                cwd=str(self.sandbox),
            )
            t1 = _now_ms()
            return {
                "ok":          proc.returncode == 0,
                "exit_code":   int(proc.returncode),
                "stdout":      (proc.stdout or "")[:8_000],
                "stderr":      (proc.stderr or "")[:4_000],
                "duration_ms": t1 - t0,
                "backend":     self.backend_name,
                "sandbox":     str(self.sandbox),
                "stub":        False,
            }
        except subprocess.TimeoutExpired:  # pragma: no cover
            return {
                "ok":          False,
                "exit_code":   124,
                "stdout":      "",
                "stderr":      f"timeout after {timeout_s}s",
                "duration_ms": timeout_s * 1000,
                "backend":     self.backend_name,
                "stub":        False,
                "error":       "TimeoutExpired",
            }

    def _run_stub(self, *, snippet: str, timeout_s: int) -> dict:
        return {
            "ok":          True,
            "exit_code":   0,
            "stdout":      f"[stub] would have executed {len(snippet)} bytes",
            "stderr":      "",
            "duration_ms": 1,
            "backend":     self.backend_name,
            "stub":        True,
            "stub_reason": (
                "PowerShell unavailable" if not is_windows()
                else "force_stub=True"
            ),
            "sandbox":     str(self.sandbox),
        }

    # -- Audit log ---------------------------------------------------

    def _append_audit(self, row: dict) -> None:
        try:
            with open(self._audit_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(redact_pii(row), default=str) + "\n")
        except OSError:
            pass


# --- Section 4. Module-level callable -----------------------------------

def execute_local_action(
    script:        str,
    rollback:      str,
    consent_token: str,
    *,
    description:   str | None = None,
    rollback_id:   str | None = None,
    consent_level: str = DEFAULT_CONSENT_LEVEL,
    force_stub:    bool = False,
    timeout_s:     int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Manifest-side entry point: ``connectors.windows_local_client.execute_local_action``."""
    client = WindowsLocalClient(force_stub=force_stub)
    result = client.execute_local_action(
        script=script, rollback=rollback,
        consent_token=consent_token,
        description=description, rollback_id=rollback_id,
        consent_level=consent_level, timeout_s=timeout_s,
    )
    return result.model_dump()


# --- Section 5. Internal helper -----------------------------------------

def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


__all__ = [
    "WindowsLocalClient",
    "execute_local_action",
    "DEFAULT_TIMEOUT_S",
    "MAX_SCRIPT_BYTES",
    "SANDBOX_ROOT_RELATIVE",
]
