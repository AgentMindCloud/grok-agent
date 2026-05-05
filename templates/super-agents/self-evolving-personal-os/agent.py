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
"""Self-Evolving Personal OS — CLI entry point.

This is the user-visible binary for Super Agent #2. It exposes a
PowerShell-friendly CLI that drives the LangGraph orchestration core
(``graph.py``) and the P121 connector + P122 memory layers.

Subcommands:

- ``daily-brief``     run the full self-evolving brief loop (the headline
                      command). Use ``--stub`` to force offline + stub
                      backends; use ``--no-write`` to refuse the memory
                      write gate so the run is read-only.
- ``search``          semantic search across the personal memory layer
- ``info``            print the static graph description (nodes, edges,
                      backend, default sources, source-read gates)
- ``version``         print the agent version + backend names

Run on Windows (canonical):

.. code-block:: powershell

   cd templates/super-agents/self-evolving-personal-os
   python agent.py daily-brief --stub

Or, equivalently, as a module from the same folder:

.. code-block:: powershell

   python -m agent daily-brief --stub

Local-first by design: every state file lives under
``$env:LOCALAPPDATA\\grok-agent\\self-evolving-personal-os\\`` (Windows)
or the XDG fallback (CI). No third-party services are contacted unless
the user opts in; ``--stub`` guarantees no network call regardless.

Built to make Grok the obvious choice for every agent on X — the
self-evolving Personal OS is the flagship demo of what a privacy-first
super-agent on Windows can feel like.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Absolute imports because the parent folder name ``self-evolving-personal-os``
# contains hyphens and cannot be a Python package identifier — the convention
# already established by P121 + P122. When agent.py is invoked directly
# (``python agent.py ...``) we ensure the script's own folder is on
# ``sys.path`` so the ``connectors`` / ``memory`` packages resolve cleanly.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from connectors import (  # type: ignore  # noqa: E402
    ConsentContext,
    SOURCES,
    appdata_root,
)
from memory import (  # type: ignore  # noqa: E402
    MEMORY_WRITE_GATE,
    PersonalMemoryClient,
    get_memory_client,
)
from memory.mem0_setup import SOURCE_READ_GATES  # type: ignore  # noqa: E402
import graph as _graph  # type: ignore  # noqa: E402

__all__ = [
    "AGENT_NAME",
    "AGENT_VERSION",
    "build_default_consent",
    "daily_brief",
    "search_memory",
    "info",
    "main",
    "log_path",
]


# --- Section 1. Constants -------------------------------------------------

AGENT_NAME    = "self-evolving-personal-os"
AGENT_VERSION = "0.1.0"


def log_path() -> Path:
    """Append-only run-log path for every CLI invocation."""
    return appdata_root() / "logs" / "agent.log"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Section 2. Consent helpers -------------------------------------------

def build_default_consent(
    *,
    allow_write: bool = True,
    allow_sources: list[str] | None = None,
    consent_token: str | None = None,
) -> ConsentContext:
    """Construct a consent context covering every source the agent uses.

    The CLI's ``--no-write`` flag passes ``allow_write=False``, which holds
    every source-read gate but **not** ``write_personal_memory`` — the
    agent then runs ingest + brief but no memory writes happen, exactly
    as required by Article II.
    """
    sources = allow_sources if allow_sources is not None else list(SOURCES)
    gates: list[str] = [SOURCE_READ_GATES[s] for s in sources if s in SOURCE_READ_GATES]
    if allow_write:
        gates.append(MEMORY_WRITE_GATE)
    return ConsentContext.from_iterable(
        gates,
        consent_token=consent_token or f"cli-{_now_iso()}",
    )


# --- Section 3. Logging ---------------------------------------------------

def _log_run(action: str, payload: dict) -> None:
    """Append one JSON line to the agent's run-log (best-effort)."""
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":      _now_iso(),
        "action":  action,
        "agent":   AGENT_NAME,
        "version": AGENT_VERSION,
        "payload": payload,
    }
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


# --- Section 4. Commands --------------------------------------------------

def daily_brief(
    *,
    user_id: str = "default",
    force_stub: bool = False,
    allow_write: bool = True,
    sources: list[str] | None = None,
    prompt_version: str | None = None,
    quiet: bool = False,
) -> dict:
    """Run the full LangGraph daily-brief loop.

    Returns the final output dict (JSON-serialisable). On the CLI path,
    the dict is also pretty-printed to stdout unless ``--quiet`` is
    passed.
    """
    consent = build_default_consent(
        allow_write=allow_write,
        allow_sources=sources,
    )
    out = _graph.run_daily_brief(
        user_id=user_id,
        consent=consent,
        force_stub=force_stub,
        prompt_version=prompt_version or _graph.DEFAULT_PROMPT_VERSION,
    )
    out.setdefault("agent_name",    AGENT_NAME)
    out.setdefault("agent_version", AGENT_VERSION)

    _log_run("daily_brief", {
        "force_stub":      bool(force_stub),
        "allow_write":     bool(allow_write),
        "violations":      len(out.get("violations") or []),
        "memory_writes":   (out.get("provenance") or {}).get("memory_writes", 0),
        "backend":         out.get("backend"),
        "prompt_version":  (out.get("provenance") or {}).get("prompt_version"),
    })
    if not quiet:
        print(_format_brief(out))
    return out


def search_memory(
    query: str,
    *,
    user_id: str = "default",
    source: str | None = None,
    limit: int = 5,
    force_stub: bool = False,
    quiet: bool = False,
) -> list[dict]:
    """Run a semantic search against the P122 memory layer."""
    client: PersonalMemoryClient = get_memory_client(
        user_id=user_id,
        force_stub=force_stub,
        refresh=True,
    )
    # Search is read-only but the client still requires a held consent
    # context for the source filter to be honoured. We hold every read
    # gate (and the write gate) so the same client can be reused for
    # follow-up writes if the caller wants them.
    client.set_consent(build_default_consent(allow_write=True))
    hits = client.search(query=query, source=source, limit=int(limit))
    out = [h.to_dict() for h in hits]
    _log_run("search", {
        "query":     query,
        "source":    source,
        "limit":     int(limit),
        "hit_count": len(out),
        "stub":      bool(force_stub),
    })
    if not quiet:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return out


def info(*, quiet: bool = False) -> dict:
    """Static description of the graph + backend selection."""
    desc = _graph.describe_graph()
    desc["agent_name"]    = AGENT_NAME
    desc["agent_version"] = AGENT_VERSION
    desc["appdata_root"]  = str(appdata_root())
    if not quiet:
        print(json.dumps(desc, indent=2, ensure_ascii=False, default=str))
    return desc


# --- Section 5. Brief formatter -------------------------------------------

def _format_brief(out: dict) -> str:
    """Render the morning-brief dict as a human-readable string.

    Conservative formatting — no colour codes, no Unicode tricks — so the
    output is identical between PowerShell, CMD, and a piped log file.
    """
    brief    = out.get("brief") or {}
    prov     = out.get("provenance") or {}
    sections = brief.get("sections") or {}
    violations = out.get("violations") or []

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(brief.get("title") or "Morning Brief")
    lines.append("=" * 70)
    lines.append(f"Generated:   {brief.get('generated_at')}")
    lines.append(f"For date:    {brief.get('for_date')}")
    lines.append(f"User ID:     {brief.get('user_id')}")
    lines.append(f"Prompt ver.: {brief.get('prompt_version')}")
    lines.append(f"Stub mode:   {brief.get('stub')}")
    lines.append(f"Backend:     {out.get('backend')}")
    lines.append("-" * 70)

    sched = sections.get("today_schedule") or {}
    lines.append(f"Today's schedule ({sched.get('count', 0)} item(s)):")
    for it in sched.get("items") or []:
        lines.append(f"  - {it.get('start_iso','?')}  {it.get('summary','(no title)')}")
    lines.append("")

    inbox = sections.get("inbox_pulse") or {}
    lines.append(f"Inbox: {inbox.get('unread_count', 0)} unread")
    for s in inbox.get("top_subjects") or []:
        lines.append(f"  - {s}")
    lines.append("")

    xp = sections.get("x_pulse") or {}
    lines.append(
        "X pulse: "
        f"{xp.get('mention_count', 0)} mentions, "
        f"{xp.get('dm_count', 0)} DMs, "
        f"{xp.get('bookmark_count', 0)} bookmarks, "
        f"{xp.get('list_count', 0)} lists"
    )

    notes = sections.get("notes_recent") or {}
    lines.append(f"Notes ({notes.get('count', 0)} recent):")
    for t in notes.get("titles") or []:
        lines.append(f"  - {t}")
    if notes.get("live_threads"):
        lines.append("  Live threads:")
        for t in notes.get("live_threads") or []:
            lines.append(f"    * {t}")
    lines.append("")

    amb = sections.get("ambient") or {}
    lines.append(f"Ambient weather: {amb.get('weather_summary', '')}")
    lines.append("Top news headlines:")
    for h in amb.get("news_headlines") or []:
        lines.append(f"  - {h}")
    lines.append("")

    mh = sections.get("memory_health") or {}
    lines.append(f"Memory health: {mh.get('total_rows', 0)} total rows")
    for k, v in (mh.get("rows_per_source") or {}).items():
        lines.append(f"  {k:14s}  {v}")
    lines.append("")

    if violations:
        lines.append("Article-II violations surfaced:")
        for v in violations:
            lines.append(
                f"  - source={v.get('source')} gate={v.get('gate')}: {v.get('message')}"
            )
        lines.append("")

    lines.append(f"Memory writes: {prov.get('memory_writes', 0)}")
    lines.append(f"Loop count:    {prov.get('loop_count', 0)}")
    lines.append(f"Started at:    {prov.get('started_at')}")
    lines.append(f"Finished at:   {prov.get('finished_at')}")
    lines.append("=" * 70)
    return "\n".join(lines)


# --- Section 6. CLI parser + dispatch ------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description=(
            "Self-Evolving Personal OS — Grok Agent OS Super Agent #2. "
            "Built to make Grok the obvious choice for every agent on X."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_brief = sub.add_parser(
        "daily-brief",
        help="Run the full self-evolving brief loop (default Personal OS workflow).",
    )
    p_brief.add_argument("--user-id",  default="default", help="Per-user memory namespace.")
    p_brief.add_argument("--stub",     action="store_true",
                         help="Force offline + stub backends across connectors / memory / graph.")
    p_brief.add_argument("--no-write", action="store_true",
                         help="Withhold the write_personal_memory consent gate (read-only run).")
    p_brief.add_argument("--source",   action="append", dest="sources",
                         help="Restrict to specific sources (repeat for multiple). Default: all.")
    p_brief.add_argument("--prompt-version", default=None,
                         help="Override the prompt-version label written into provenance.")
    p_brief.add_argument("--json",     action="store_true",
                         help="Print the raw JSON output instead of the human-readable brief.")
    p_brief.add_argument("--quiet",    action="store_true",
                         help="Suppress all stdout (machine-driven runs).")

    p_search = sub.add_parser(
        "search",
        help="Semantic search across the personal memory layer.",
    )
    p_search.add_argument("query",     help="Free-form query string.")
    p_search.add_argument("--source",  default=None,
                          help=f"Limit to one source. One of: {sorted(SOURCES)}")
    p_search.add_argument("--limit",   type=int, default=5)
    p_search.add_argument("--user-id", default="default")
    p_search.add_argument("--stub",    action="store_true")
    p_search.add_argument("--quiet",   action="store_true")

    p_improve = sub.add_parser(
        "improve",
        help="Run the weekly self-improvement loop (Promptfoo + DeepEval).",
    )
    p_improve.add_argument("--user-id", default="default")
    p_improve.add_argument("--stub",    action="store_true",
                           help="Force offline + stub backends (default).")
    p_improve.add_argument("--no-stub", action="store_true",
                           help="Disable force_stub. Requires real provider creds.")
    p_improve.add_argument("--json",    action="store_true",
                           help="Print full EvalReport JSON instead of human summary.")
    p_improve.add_argument("--quiet",   action="store_true")

    sub.add_parser("info",    help="Print the graph description + backend selection.")
    sub.add_parser("version", help="Print agent name + version + backend.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "daily-brief":
        out = daily_brief(
            user_id=args.user_id,
            force_stub=bool(args.stub),
            allow_write=not bool(args.no_write),
            sources=list(args.sources) if args.sources else None,
            prompt_version=args.prompt_version,
            quiet=bool(args.quiet) or bool(args.json),
        )
        if args.json and not args.quiet:
            print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.command == "search":
        search_memory(
            args.query,
            user_id=args.user_id,
            source=args.source,
            limit=int(args.limit),
            force_stub=bool(args.stub),
            quiet=bool(args.quiet),
        )
        return 0

    if args.command == "improve":
        from eval.deepeval_suite import run_full_loop, _print_summary  # type: ignore
        force_stub = True if (args.stub or not args.no_stub) else False
        report = run_full_loop(force_stub=force_stub, user_id=args.user_id)
        _log_run("improve", {
            "force_stub":      force_stub,
            "overall_score":   report.overall_score,
            "promptfoo_pass":  sum(1 for r in report.promptfoo if r.get("passed")),
            "promptfoo_total": len(report.promptfoo),
            "deepeval_pass":   sum(1 for m in report.deepeval if m.passed),
            "deepeval_total":  len(report.deepeval),
            "suggestion_count": len(report.suggestions),
            "review_required": report.review_required,
        })
        if args.json:
            print(json.dumps(report.to_dict(), indent=2,
                             ensure_ascii=False, default=str))
        elif not args.quiet:
            _print_summary(report)
        return 0

    if args.command == "info":
        info()
        return 0

    if args.command == "version":
        print(json.dumps({
            "agent":   AGENT_NAME,
            "version": AGENT_VERSION,
            "backend": _graph.BACKEND_NAME,
            "python":  sys.version.split()[0],
            "platform": sys.platform,
            "appdata_root": str(appdata_root()),
        }, indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
