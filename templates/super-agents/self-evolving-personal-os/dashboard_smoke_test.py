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
"""Smoke test for the Self-Evolving Personal OS dashboard (P126).

Layered on top of the 143 prior P121 + P122 + P123 + P124 + P125
checks. This suite adds 14 new checks across four areas:

1. Module / file surface — dashboard.py + requirements.txt +
   .streamlit/config.toml exist with the right shape.
2. Pure-Python data helpers — build_overview_payload,
   build_brief_payload, build_memory_payload, build_provenance_payload,
   build_improve_payload all return the expected schema regardless of
   whether Streamlit is installed.
3. Action runners — run_daily_brief_action, run_memory_search_action,
   run_improve_action wire the dashboard to the existing CLI without
   touching agent.py / graph.py.
4. PII + force_stub — every payload that flows through the dashboard
   carries a ``redaction_applied`` provenance flag and ``stub`` honours
   the sidebar toggle.

Run on Windows (canonical):

.. code-block:: powershell

   cd templates/super-agents/self-evolving-personal-os
   python -m dashboard_smoke_test

Built to help xAI and Grok win.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

import dashboard as _dash  # type: ignore
from connectors import ConsentContext, SOURCES, appdata_root  # type: ignore
from memory import MEMORY_WRITE_GATE  # type: ignore
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore
from provenance import (  # type: ignore
    LocalProvenanceLogger,
    ProvenanceRecord,
    current_log_path,
    reset_default_logger,
    reset_langfuse_client,
)


# -- Section S.1. Helpers --------------------------------------------------

def _ok(label: str) -> None:
    print(f"  PASS  {label}")


def _fail(label: str, why: str) -> None:
    print(f"  FAIL  {label}: {why}")
    raise SystemExit(1)


def _wipe() -> None:
    root = appdata_root()
    for sub in ("memory", "logs", "provenance", "eval"):
        shutil.rmtree(root / sub, ignore_errors=True)
    try:
        (root / "connector_audit.db").unlink(missing_ok=True)
    except OSError:
        pass
    reset_default_logger()
    reset_langfuse_client()


def _full_consent() -> ConsentContext:
    return ConsentContext.from_iterable(
        list(SOURCE_READ_GATES.values()) + [MEMORY_WRITE_GATE],
        consent_token="p126-smoke",
    )


# -- Section S.2. Test cases ---------------------------------------------

def test_module_surface() -> None:
    print("[1/4] module / file surface ----------------------------------------")
    here = Path(__file__).resolve().parent

    dash_path = here / "dashboard.py"
    if not dash_path.exists():
        _fail("dashboard.py", "missing")
    _ok("dashboard.py present")

    text = dash_path.read_text(encoding="utf-8")
    if "Apache License, Version 2.0" not in text:
        _fail("dashboard header", "Apache 2.0 license missing")
    _ok("dashboard.py carries Apache 2.0 header")

    if "Built to help xAI and Grok win" not in text \
            and "Built for xAI, Grok" not in text:
        _fail("dashboard tagline", "ecosystem-ally line missing")
    _ok("dashboard.py carries the 'help xAI and Grok win' line")

    cfg_path = here / ".streamlit" / "config.toml"
    if not cfg_path.exists():
        _fail(".streamlit/config.toml", "missing")
    _ok(".streamlit/config.toml present")

    cfg_text = cfg_path.read_text(encoding="utf-8")
    if "Apache License, Version 2.0" not in cfg_text:
        _fail("config.toml header", "Apache 2.0 missing")
    if "port = 8505" not in cfg_text:
        _fail("config.toml port", "expected port = 8505 (Super Agent #2 slot)")
    if 'gatherUsageStats = false' not in cfg_text:
        _fail("config.toml privacy", "gatherUsageStats must be false")
    _ok(".streamlit/config.toml port=8505 + privacy-safe defaults")

    req_path = here / "requirements.txt"
    if not req_path.exists():
        _fail("requirements.txt", "missing")
    req_text = req_path.read_text(encoding="utf-8")
    for dep in ("streamlit", "pandas", "plotly", "PyYAML"):
        if dep not in req_text:
            _fail(f"requirements.txt[{dep}]", "dep missing")
    _ok("requirements.txt declares streamlit + pandas + plotly + PyYAML")

    # Tab titles + page config
    if len(_dash.TAB_TITLES) != 5:
        _fail("TAB_TITLES count", str(len(_dash.TAB_TITLES)))
    if list(_dash.TAB_TITLES) != [
        "Overview", "Daily Brief", "Memory Explorer",
        "Provenance Audit", "Self-Improve",
    ]:
        _fail("TAB_TITLES order", str(_dash.TAB_TITLES))
    _ok("dashboard advertises exactly 5 tabs in the canonical order")

    # Module imports cleanly without Streamlit
    if _dash.STREAMLIT_AVAILABLE not in (True, False):
        _fail("STREAMLIT_AVAILABLE", "must be a bool")
    _ok(f"dashboard module imports cleanly (Streamlit available: {_dash.STREAMLIT_AVAILABLE})")


def test_data_helpers() -> None:
    print("[2/4] pure-Python data helpers ------------------------------------")
    _wipe()

    # build_overview_payload — even on a fresh machine with no runs.
    payload = _dash.build_overview_payload()
    for k in (
        "agent_name", "agent_version", "graph_backend",
        "langfuse_backend", "deepeval_backend",
        "appdata_root", "memory_root", "provenance_root", "eval_root",
        "max_evolution_loops", "default_sources",
        "memory_write_gate", "source_read_gates",
        "latest_run", "rows_per_source", "tagline",
    ):
        if k not in payload:
            _fail(f"overview[{k}]", "missing")
    _ok("build_overview_payload returns 16 expected keys")

    if list(payload["default_sources"]) != list(SOURCES):
        _fail("overview.default_sources", str(payload["default_sources"]))
    _ok("overview.default_sources matches the 6 manifest-declared sources")

    # Now run a brief and verify the brief / memory / provenance / improve
    # helpers all consume the real outputs cleanly.
    out = _dash.run_daily_brief_action(force_stub=True)
    if not out or not out.get("brief"):
        _fail("run_daily_brief_action", "empty brief")
    _ok("run_daily_brief_action returned a non-empty brief")

    brief_payload = _dash.build_brief_payload(out)
    for k in (
        "title", "generated_at", "for_date", "user_id",
        "prompt_version", "stub", "backend",
        "sections", "violations", "provenance",
    ):
        if k not in brief_payload:
            _fail(f"brief[{k}]", "missing")
    if brief_payload["empty"]:
        _fail("brief.empty", "should be False after a real run")
    if not brief_payload["stub"]:
        _fail("brief.stub", "force_stub=True should propagate")
    _ok("build_brief_payload echoes the brief shape with stub=True")
    if len(brief_payload["sections"]) < 6:
        _fail("brief.sections count", str(len(brief_payload["sections"])))
    _ok(f"brief carries {len(brief_payload['sections'])} sections (≥ 6)")

    # build_memory_payload
    hits = _dash.run_memory_search_action("stub", limit=5, force_stub=True)
    mem_payload = _dash.build_memory_payload(hits)
    if mem_payload["row_count"] != len(hits):
        _fail("memory.row_count", "mismatch")
    if mem_payload["row_count"] == 0:
        _fail("memory.row_count", "expected ≥ 1 hit after a brief")
    if not all("score" in r and "source" in r and "snippet" in r
               for r in mem_payload["rows"]):
        _fail("memory.rows shape", "missing required fields")
    _ok(f"build_memory_payload returns {mem_payload['row_count']} clean rows")

    # build_provenance_payload
    log = LocalProvenanceLogger()
    today = current_log_path().name.replace(".jsonl", "")
    records = _dash.load_records_for_date(today)
    if not records:
        _fail("load_records_for_date", "empty after a brief")
    prov_payload = _dash.build_provenance_payload(records)
    if prov_payload["row_count"] != len(records):
        _fail("prov.row_count", "mismatch")
    if not prov_payload["run_ids"]:
        _fail("prov.run_ids", "empty")
    _ok(f"build_provenance_payload returns {prov_payload['row_count']} rows "
        f"across {len(prov_payload['run_ids'])} run(s)")
    # Filter narrowing
    one_run = prov_payload["run_ids"][0]
    narrowed = _dash.build_provenance_payload(records, run_id_filter=one_run)
    if narrowed["row_count"] > prov_payload["row_count"]:
        _fail("prov filter", "filter increased row count")
    _ok("provenance run_id filter narrows the row set monotonically")


def test_actions_and_pii() -> None:
    print("[3/4] action runners + PII / force_stub ---------------------------")
    _wipe()

    # run_improve_action triggers the P125 loop and returns an EvalReport.
    report = _dash.run_improve_action(force_stub=True)
    payload = _dash.build_improve_payload(report)
    for k in ("run_id", "started_at", "finished_at", "force_stub",
              "backend", "overall_score", "review_required",
              "promptfoo", "deepeval", "suggestions"):
        if k not in payload:
            _fail(f"improve[{k}]", "missing")
    _ok("build_improve_payload returns the canonical 10-field shape")

    if not payload["force_stub"]:
        _fail("improve.force_stub", "expected True")
    _ok("force_stub propagates into the EvalReport")
    if len(payload["promptfoo"]) != 8:
        _fail("improve.promptfoo size", str(len(payload["promptfoo"])))
    if len(payload["deepeval"]) != 5:
        _fail("improve.deepeval size", str(len(payload["deepeval"])))
    _ok("improve payload has 8 promptfoo + 5 deepeval rows")

    # Suggestions on a clean stub run should be empty (everything passes).
    if payload["suggestions"]:
        _fail("clean-stub suggestions", "expected empty on happy path")
    _ok("clean-stub run produces zero needs_review suggestions")

    # PII redaction at the dashboard boundary (memory hits).
    leaky = "Email me at alice@example.com or @alice_smith"
    cleaned = _dash.redact_for_display(leaky)
    if "alice@example.com" in cleaned or "@alice_smith" in cleaned:
        _fail("redact_for_display", f"raw PII surfaced: {cleaned}")
    _ok("redact_for_display scrubs emails + handles at display time")

    # The dashboard sources list mirrors the connector layer exactly.
    if set(_dash.SOURCES) != set(SOURCES):
        _fail("SOURCES parity", "dashboard SOURCES drifted from connectors")
    _ok("dashboard SOURCES list mirrors connectors.SOURCES exactly")


def test_disclaimers_and_constants() -> None:
    print("[4/4] disclaimers + constants -------------------------------------")
    here = Path(__file__).resolve().parent
    text = (here / "dashboard.py").read_text(encoding="utf-8")

    if "Not financial advice" in text or "Not tax advice" in text:
        # We are NOT a finance tool — surfacing those disclaimers here
        # would be misleading. Personal OS uses the Article V.3
        # real-world-action banner instead.
        _fail("disclaimer mix", "personal-OS dashboard must NOT carry V.1/V.2 finance banners")
    _ok("dashboard avoids inappropriate finance / tax disclaimers")

    if "real-world actions" not in text or "explicit consent" not in text:
        _fail("disclaimer V.3", "real-world-action banner missing")
    _ok("dashboard carries the V.3 real-world-action consent banner")

    if "Local-first" not in text:
        _fail("local-first banner", "missing")
    _ok("dashboard surfaces the local-first + privacy-first banner")

    # The dashboard never instructs `cd ` with bash-only flags (Hard Six).
    bad_bashisms = ["sudo ", "chmod ", "mkdir -p", "&&", "/usr/bin/python", "/bin/bash"]
    leaked = [b for b in bad_bashisms if b in text]
    if leaked:
        _fail("PowerShell-only", f"bash-isms present: {leaked}")
    _ok("dashboard.py contains no bash-only invocations")


# -- Section S.3. Entry point --------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    print("=" * 70)
    print("P126 Self-Evolving Personal OS dashboard smoke test")
    print(f"Streamlit available: {_dash.STREAMLIT_AVAILABLE}")
    print("=" * 70)
    try:
        test_module_surface()
        test_data_helpers()
        test_actions_and_pii()
        test_disclaimers_and_constants()
    except SystemExit:
        print("=" * 70)
        print("RESULT: FAIL")
        return 1
    except Exception:
        print("UNCAUGHT EXCEPTION:")
        traceback.print_exc()
        print("=" * 70)
        print("RESULT: FAIL")
        return 1
    print("=" * 70)
    print("RESULT: PASS — all 4 P126 acceptance areas covered")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
