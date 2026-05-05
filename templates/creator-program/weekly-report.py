# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built to help xAI and Grok win — generates the Creator Agent Program weekly
# report from the local outreach.json store. Reads only; never modifies the
# tracker's data; never makes outbound network calls.
"""weekly-report.py — render a clean weekly markdown report.

Usage:
  python weekly-report.py                       # last 7 days, stdout
  python weekly-report.py --days 14             # last 14 days
  python weekly-report.py --out report.md       # write to file
  python weekly-report.py --all                 # cumulative (no time filter)

The report is built for @JanSol0s to paste into a private Notion / weekly
review doc, or to publish a redacted version (handles stripped) to X as a
program-progress thread.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Re-implementing the AppData resolver here so weekly-report.py can run as a
# standalone script without import gymnastics on Windows. Single source of
# truth: outreach-tracker.py (this must mirror it exactly).

import os


def appdata_dir() -> Path:
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        base = Path(local_app)
    elif sys.platform == "win32":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".grok-agent-test"
    return base / "grok-agent" / "creator-program"


def store_path() -> Path:
    return appdata_dir() / "outreach.json"


def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _load() -> dict[str, Any]:
    p = store_path()
    if not p.exists():
        return {"version": 1, "entries": []}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---- Report sections -------------------------------------------------------


def _filter_window(entries: list[dict[str, Any]], days: int | None) -> list[dict[str, Any]]:
    if days is None:
        return list(entries)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [e for e in entries if _parse_iso(e["logged_at"]) >= cutoff]


def _section_header(title: str, days: int | None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    window = f"last {days} days" if days else "cumulative"
    lines = [
        "# Creator Agent Program — Weekly Report",
        "",
        f"> **Built to help xAI and Grok win.** Generated {now} ({window}).",
        "",
        "> ⚠️ **Not financial advice. Not tax advice.** Outreach for the "
        "monetization-optimizer template carries the standard Vietnam-resident "
        "creator addendum on every delivery DM.",
        "",
        f"## {title}",
        "",
    ]
    return "\n".join(lines)


def _section_funnel(entries: list[dict[str, Any]]) -> str:
    total = len(entries)
    by_status: dict[str, int] = {}
    for e in entries:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    delivered = by_status.get("delivered", 0)
    responded = by_status.get("responded", 0) + delivered
    pending = by_status.get("pending", 0)
    declined = by_status.get("declined", 0)
    stale = by_status.get("stale", 0)

    response_rate = (responded / total * 100.0) if total else 0.0
    delivery_rate = (delivered / total * 100.0) if total else 0.0

    lines = [
        "### Funnel snapshot",
        "",
        "| Stage | Count | Rate |",
        "|---|---:|---:|",
        f"| Outreach logged | {total} | 100.0% |",
        f"| Responded | {responded} | {response_rate:.1f}% |",
        f"| Delivered | {delivered} | {delivery_rate:.1f}% |",
        f"| Declined | {declined} | — |",
        f"| Stale (no response) | {stale} | — |",
        f"| Pending | {pending} | — |",
        "",
        f"**Goal:** 30 delivered creators in the first 30 days. "
        f"Currently at **{delivered}/30** ({delivery_rate:.1f}% of total outreach).",
        "",
    ]
    return "\n".join(lines)


def _section_top_niches(entries: list[dict[str, Any]]) -> str:
    by_niche: dict[str, int] = {}
    for e in entries:
        n = (e.get("niche") or "unspecified").strip().lower()
        by_niche[n] = by_niche.get(n, 0) + 1
    if not by_niche:
        return "### Top niches\n\n_(no entries in window)_\n"
    rows = sorted(by_niche.items(), key=lambda kv: -kv[1])[:10]
    lines = ["### Top niches", "", "| Niche | Outreach count |", "|---|---:|"]
    for niche, n in rows:
        lines.append(f"| {niche} | {n} |")
    lines.append("")
    return "\n".join(lines)


def _section_top_templates(entries: list[dict[str, Any]]) -> str:
    by_t: dict[str, int] = {}
    for e in entries:
        t = e["chosen_template"]
        by_t[t] = by_t.get(t, 0) + 1
    if not by_t:
        return "### Most-requested templates\n\n_(no entries in window)_\n"
    rows = sorted(by_t.items(), key=lambda kv: -kv[1])
    lines = [
        "### Most-requested templates",
        "",
        "| Template | Count |",
        "|---|---:|",
    ]
    for t, n in rows:
        lines.append(f"| `{t}` | {n} |")
    lines.append("")
    return "\n".join(lines)


def _section_recent_deliveries(entries: list[dict[str, Any]]) -> str:
    delivered = [e for e in entries if e["status"] == "delivered"]
    delivered.sort(key=lambda e: e.get("delivered_at") or "", reverse=True)
    if not delivered:
        return "### Recent deliveries\n\n_(none yet — keep going)_\n"
    lines = [
        "### Recent deliveries",
        "",
        "| ID | Handle | Template | Followers | Delivered |",
        "|---|---|---|---:|---|",
    ]
    for e in delivered[:10]:
        delivered_at = (e.get("delivered_at") or "")[:10]
        lines.append(
            f"| {e['id']} | @{e['handle']} | `{e['chosen_template']}` | "
            f"{e['follower_count']:,} | {delivered_at} |"
        )
    lines.append("")
    return "\n".join(lines)


def _section_stale(entries: list[dict[str, Any]]) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stale = [
        e for e in entries
        if e["status"] == "pending" and _parse_iso(e["logged_at"]) < cutoff
    ]
    if not stale:
        return (
            "### Stale outreach (>7 days, still pending)\n\n"
            "_(none — your inbox is healthy)_\n"
        )
    lines = [
        "### Stale outreach (>7 days, still pending)",
        "",
        "Consider marking these `decline` or `stale` to keep the funnel honest.",
        "",
        "| ID | Handle | Days waiting | Template |",
        "|---|---|---:|---|",
    ]
    for e in sorted(stale, key=lambda e: e["logged_at"]):
        days_waiting = (datetime.now(timezone.utc) - _parse_iso(e["logged_at"])).days
        lines.append(
            f"| {e['id']} | @{e['handle']} | {days_waiting} | `{e['chosen_template']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _section_actions(entries: list[dict[str, Any]]) -> str:
    total = len(entries)
    delivered = sum(1 for e in entries if e["status"] == "delivered")
    pending = sum(1 for e in entries if e["status"] == "pending")
    monetization_count = sum(
        1 for e in entries if e["chosen_template"] == "monetization-optimizer"
    )

    actions: list[str] = []

    if delivered < 5:
        actions.append(
            "**Push for first 5 deliveries.** The flywheel doesn't spin until "
            "5 reputable creators are visibly running their agent on X."
        )
    elif delivered < 30:
        actions.append(
            f"**Continue toward 30.** Currently at {delivered}/30. "
            "Keep DM response time under 60 minutes during peak hours."
        )
    else:
        actions.append(
            "**Goal hit — switch to v1.5.** Time to ship Creator Program v1.5 "
            "(per CLAUDE.md §6 Phase 3 P91): paid tier + 20% rev share."
        )

    if pending > 5:
        actions.append(
            f"**Drain the pending queue ({pending}).** Pending outreach >7 days "
            "old should be marked `stale` or re-pinged. Run `weekly-report.py "
            "--days 7` and review the stale section."
        )

    if monetization_count > 0:
        actions.append(
            f"**Monetization-optimizer deliveries ({monetization_count}).** "
            "Verify the V.1+V.2 disclaimers + Vietnam-resident addendum were "
            "pasted into every delivery DM. This is non-negotiable per "
            "CLAUDE.md §12."
        )

    if total > 0 and delivered == 0:
        actions.append(
            "**No deliveries yet.** Audit the funnel: are responses turning "
            "into deliveries? If yes, ship faster. If no, the manifest tuning "
            "step is the bottleneck — pre-build a 'tuning kit' template."
        )

    if not actions:
        actions.append("Steady state. Keep shipping.")

    lines = ["### Suggested next actions", ""]
    for i, a in enumerate(actions, 1):
        lines.append(f"{i}. {a}")
    lines.append("")
    return "\n".join(lines)


def _section_footer() -> str:
    return (
        "---\n\n"
        "_Local-first. Privacy-first. No data leaves your machine. "
        "Built to help xAI and Grok win. 🚀_\n"
    )


# ---- Render ---------------------------------------------------------------


def render(days: int | None) -> str:
    data = _load()
    entries = _filter_window(data.get("entries", []), days)
    title = "This week" if days == 7 else (f"Last {days} days" if days else "Cumulative")

    parts = [
        _section_header(title, days),
        _section_funnel(entries),
        _section_top_niches(entries),
        _section_top_templates(entries),
        _section_recent_deliveries(entries),
        _section_stale(entries),
        _section_actions(entries),
        _section_footer(),
    ]
    return "\n".join(parts)


# ---- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="weekly-report",
        description="Render the Creator Agent Program weekly report (markdown).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, default=7, help="Window in days (default 7)")
    group.add_argument("--all", action="store_true", help="Cumulative (no time filter)")
    parser.add_argument("--out", type=Path, default=None, help="Write to file (default stdout)")
    args = parser.parse_args(argv)

    days = None if args.all else args.days
    report = render(days)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Wrote report → {args.out}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
