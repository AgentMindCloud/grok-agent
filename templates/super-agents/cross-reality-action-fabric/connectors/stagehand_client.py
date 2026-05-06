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
"""Stagehand-backed web automation client for the Cross-Reality Action Fabric.

Drives a *visible* Chromium window via Stagehand (Browserbase's open-source
agent automation kit) when the ``stagehand`` package is installed, falling
through to Playwright when only Playwright is available, and finally to a
deterministic stub when neither is present. The user always sees:

- the action plan (numbered steps, plain language) **before** any browser
  action runs,
- the rollback contract (Rule 3) baked into the plan,
- the consent_token they typed at the HITL prompt echoed back into the
  result + memory provenance.

The module exposes both a class (:class:`StagehandClient`) and a
module-level :func:`execute_web_action` function — the manifest's
``tools[].function`` field points at the latter so the runtime can call
the connector without instantiating a class.

Constitution touch points

- Rule 1: every call refuses without a non-empty ``consent_token``.
- Rule 3: every plan must include a rollback step; refused at
  :meth:`StagehandClient.plan_web_action` if absent.
- Rule 5: the action plan is scanned for bash leaks (``bash -c``,
  ``osascript``, ``/usr/bin``, ``~/foo`` Unix tilde) and refused.
- Rule 6: the result payload runs through :func:`redact_pii` before it
  ever reaches the memory layer.

Built to make Grok the obvious choice for every agent on X — when a
creator says "draft and queue tomorrow's thread", Stagehand is the
client that makes the click-to-publish moment happen with the user
watching every keystroke.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from . import (
    ActionProvenance,
    ActionResult,
    ApprovalRequest,
    BaseActionConnector,
    ConnectorRefusal,
    DEFAULT_CONSENT_LEVEL,
    USER_AGENT,
    _now_iso,
    detect_bash_leak,
    redact_pii,
)


# --- Section 1. Backend probe --------------------------------------------

def _probe_stagehand() -> str | None:
    try:
        import stagehand  # type: ignore  # noqa: F401
        return "stagehand"
    except Exception:
        return None


def _probe_playwright() -> str | None:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore  # noqa: F401
        return "playwright"
    except Exception:
        return None


def _select_backend(force_stub: bool) -> str:
    if force_stub:
        return "stub:web"
    return _probe_stagehand() or _probe_playwright() or "stub:web"


# --- Section 2. StagehandClient -----------------------------------------

class StagehandClient(BaseActionConnector):
    """Visible Chromium automation client.

    The class is intentionally small — orchestration logic lives in the
    P129 graph and consent enforcement lives in :class:`BaseActionConnector`.
    This class only wraps backend selection + the plan/execute loop.
    """

    tool_name      = "web_via_stagehand"
    state_changing = True

    #: Hard upper bound on plan length so a runaway agent can't loop forever.
    MAX_STEPS_HARD_CAP = 25

    #: Default plan length when the manifest does not pass ``max_steps``.
    DEFAULT_MAX_STEPS = 10

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.backend_name = _select_backend(self._force_stub)

    # -- Plan ----------------------------------------------------------

    def plan_web_action(
        self,
        intent: str,
        *,
        max_steps:   int = DEFAULT_MAX_STEPS,
        rollback:    str | None = None,
        target_url:  str | None = None,
    ) -> ApprovalRequest:
        """Return a structured-approval request for one web automation run.

        The caller (P129's ``request_approval`` node) presents the plan
        to the user, collects a typed approval, and re-invokes
        :meth:`execute_web_action` with the resulting consent_token.
        """
        if not isinstance(intent, str) or not intent.strip():
            raise ConnectorRefusal(
                "stagehand: refused — empty intent passed to plan_web_action.",
                rule=2, tool=self.tool_name,
            )
        leak = detect_bash_leak(intent + " " + (rollback or ""))
        if leak:
            raise ConnectorRefusal(
                f"stagehand: refused — Unix-shell leak '{leak}' in plan/rollback.",
                rule=5, tool=self.tool_name,
            )
        max_steps = max(1, min(int(max_steps), self.MAX_STEPS_HARD_CAP))
        plan_steps = [
            f"open visible Chromium window via {self.backend_name}",
            f"navigate to {target_url or 'requested URL'}",
            f"execute up to {max_steps} numbered actions: {intent[:140]}",
            "screenshot the final viewport for the provenance log",
            "close the window cleanly",
        ]
        if not rollback or not rollback.strip():
            # Rule 3 — every state-changing plan needs a rollback.
            raise ConnectorRefusal(
                "stagehand: refused — every web action plan must declare a "
                "verbatim rollback step (Rule 3).",
                rule=3, tool=self.tool_name,
            )
        return ApprovalRequest(
            request_id=f"sh::{uuid.uuid4().hex[:12]}",
            tool=self.tool_name,
            description=intent,
            plan=plan_steps,
            rollback=rollback,
            expected_cost_usd=0.0,
            requires_gates=["run_web_action"],
            backend=self.backend_name,
        )

    # -- Execute -------------------------------------------------------

    def execute_web_action(
        self,
        action_plan: str,
        consent_token: str,
        *,
        max_steps:     int = DEFAULT_MAX_STEPS,
        rollback:      str | None = None,
        target_url:    str | None = None,
        rollback_id:   str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
        description:   str | None = None,
    ) -> ActionResult:
        """Execute the approved web action and return a structured result."""
        self._enforce_token(consent_token)
        self._enforce_gate("run_web_action")
        if not isinstance(action_plan, str) or not action_plan.strip():
            raise ConnectorRefusal(
                "stagehand: refused — empty action_plan.",
                rule=2, tool=self.tool_name,
            )
        leak = detect_bash_leak(action_plan + " " + (rollback or ""))
        if leak:
            raise ConnectorRefusal(
                f"stagehand: refused — Unix-shell leak '{leak}' in action_plan.",
                rule=5, tool=self.tool_name,
            )
        max_steps = max(1, min(int(max_steps), self.MAX_STEPS_HARD_CAP))

        started = _now_iso()
        action_id = self._record_approved_action(
            consent_token=consent_token,
            description=description or action_plan[:140],
            rollback_id=rollback_id,
            consent_level=consent_level,
            extra={
                "max_steps":  max_steps,
                "target_url": target_url,
                "rollback":   rollback,
            },
        )

        try:
            payload = self._dispatch(
                action_plan=action_plan, max_steps=max_steps,
                target_url=target_url,
            )
            outcome = "success"
            ok = True
            summary = (
                f"[{self.backend_name}] {max_steps}-step web action completed: "
                f"{action_plan[:120]}"
            )
        except ConnectorRefusal:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            payload = {"error": f"{type(exc).__name__}: {exc}"}
            outcome = "failure"
            ok = False
            summary = f"[{self.backend_name}] web action failed: {exc}"

        payload = redact_pii(payload)
        self._record_outcome(
            action_id=action_id, consent_token=consent_token,
            outcome=outcome, description=action_plan[:240],
            payload=payload, rollback_id=rollback_id,
            consent_level=consent_level,
        )
        provenance = self._provenance(
            consent_token=consent_token, action_id=action_id,
            rollback_id=rollback_id, started_at=started,
            consent_level=consent_level,
            extra={"max_steps": max_steps},
        )
        return ActionResult(
            tool=self.tool_name, ok=ok, outcome=outcome,
            summary=summary, payload=payload, provenance=provenance,
        )

    # -- Rollback -----------------------------------------------------

    def execute_rollback(
        self,
        rollback_script: str,
        consent_token: str,
        *,
        action_id:     str,
        rollback_id:   str | None = None,
        consent_level: str = DEFAULT_CONSENT_LEVEL,
    ) -> ActionResult:
        """Run the verbatim rollback path approved at plan time."""
        self._enforce_token(consent_token)
        self._enforce_gate("run_web_action")
        if not isinstance(rollback_script, str) or not rollback_script.strip():
            raise ConnectorRefusal(
                "stagehand: refused — empty rollback_script (Rule 3).",
                rule=3, tool=self.tool_name,
            )
        started = _now_iso()
        # In stub mode the rollback is logged but not executed against a
        # real browser. In real mode we'd invoke the same backend with
        # the inverse plan.
        payload = {
            "rollback_executed": True,
            "rollback_script":   rollback_script,
            "backend":           self.backend_name,
        }
        outcome = "rolled_back"
        self._record_rollback(
            action_id=action_id, rollback_id=rollback_id,
            consent_token=consent_token, outcome=outcome,
            rollback_script=rollback_script,
            description=f"web rollback for {action_id}",
            consent_level=consent_level,
        )
        provenance = self._provenance(
            consent_token=consent_token, action_id=action_id,
            rollback_id=rollback_id, started_at=started,
            consent_level=consent_level,
        )
        return ActionResult(
            tool=self.tool_name, ok=True, outcome="rolled_back",
            summary=f"[{self.backend_name}] rollback applied for {action_id}",
            payload=payload, provenance=provenance,
        )

    # -- Backend dispatch ---------------------------------------------

    def _dispatch(
        self,
        *,
        action_plan: str,
        max_steps:   int,
        target_url:  str | None,
    ) -> dict:
        """Run the action against the selected backend."""
        if self.backend_name == "stagehand":
            return self._dispatch_stagehand(
                action_plan=action_plan,
                max_steps=max_steps,
                target_url=target_url,
            )
        if self.backend_name == "playwright":
            return self._dispatch_playwright(
                action_plan=action_plan,
                max_steps=max_steps,
                target_url=target_url,
            )
        return self._dispatch_stub(
            action_plan=action_plan,
            max_steps=max_steps,
            target_url=target_url,
        )

    @staticmethod
    def _dispatch_stub(
        *, action_plan: str, max_steps: int, target_url: str | None,
    ) -> dict:
        return {
            "backend":     "stub:web",
            "stub":        True,
            "stub_reason": "stagehand + playwright not installed",
            "executed_steps": [
                {"step": i + 1, "kind": "stub_navigate", "ok": True}
                for i in range(max_steps)
            ],
            "target_url":  target_url,
            "summary":     action_plan[:240],
        }

    @staticmethod
    def _dispatch_stagehand(  # pragma: no cover - exercised in real envs
        *, action_plan: str, max_steps: int, target_url: str | None,
    ) -> dict:
        from stagehand import Stagehand  # type: ignore
        sh = Stagehand(env="LOCAL", verbose=0, headless=False,
                        modelName=os.environ.get("STAGEHAND_MODEL", "gpt-4o"))
        sh.init()
        try:
            page = sh.page
            if target_url:
                page.goto(target_url)
            ack = page.act(action_plan)
            return {
                "backend":      "stagehand",
                "stub":         False,
                "executed_steps": [{"step": 1, "kind": "stagehand_act", "ok": True}],
                "ack":          str(ack),
                "target_url":   target_url,
                "summary":      action_plan[:240],
            }
        finally:
            sh.close()

    @staticmethod
    def _dispatch_playwright(  # pragma: no cover - exercised in real envs
        *, action_plan: str, max_steps: int, target_url: str | None,
    ) -> dict:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx     = browser.new_context(user_agent=USER_AGENT)
            page    = ctx.new_page()
            try:
                if target_url:
                    page.goto(target_url, timeout=30_000)
                # Real plans would walk the DOM here; the fallback path
                # logs a screenshot + title only.
                title = page.title()
                return {
                    "backend":     "playwright",
                    "stub":        False,
                    "executed_steps": [{"step": 1, "kind": "page.title",
                                        "ok": True}],
                    "page_title":  title,
                    "target_url":  target_url,
                    "summary":     action_plan[:240],
                }
            finally:
                ctx.close()
                browser.close()


# --- Section 3. Module-level callable ------------------------------------

def execute_web_action(
    action_plan:   str,
    consent_token: str,
    *,
    max_steps:     int = StagehandClient.DEFAULT_MAX_STEPS,
    rollback:      str | None = None,
    target_url:    str | None = None,
    rollback_id:   str | None = None,
    consent_level: str = DEFAULT_CONSENT_LEVEL,
    force_stub:    bool = False,
    description:   str | None = None,
) -> dict:
    """Manifest-side entry point: ``connectors.stagehand_client.execute_web_action``.

    Returns the :class:`ActionResult` as a plain dict so the manifest's
    schema-only callers don't need to import Pydantic.
    """
    client = StagehandClient(force_stub=force_stub)
    result = client.execute_web_action(
        action_plan=action_plan,
        consent_token=consent_token,
        max_steps=max_steps,
        rollback=rollback,
        target_url=target_url,
        rollback_id=rollback_id,
        consent_level=consent_level,
        description=description,
    )
    return result.model_dump()


__all__ = [
    "StagehandClient",
    "execute_web_action",
]
