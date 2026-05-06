# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built for xAI, X, Grok and the ecosystem community — the local-first outreach tracker for the
# Creator Agent Program. Logs every outreach attempt, response, and delivered
# agent to a Windows AppData JSON store. No data leaves your machine.
"""outreach-tracker.py — Creator Agent Program outreach tracker.

Local-first, privacy-respecting CLI for the @JanSol0s outreach flow:

  python outreach-tracker.py log       — log a new outreach attempt
  python outreach-tracker.py respond   — mark an attempt as responded
  python outreach-tracker.py deliver   — mark an agent as delivered
  python outreach-tracker.py list      — list all outreach (most recent first)
  python outreach-tracker.py stats     — print live stats

Storage: $env:LOCALAPPDATA\\grok-agent\\creator-program\\outreach.json

Privacy contract:
  • X handles are stored ONLY when the creator has DM'd you first (explicit
    inbound consent). The tracker refuses to log a handle without the
    --consent flag.
  • Notes fields are local-only and never synced.
  • The tracker never makes outbound network calls.

Disclaimers:
  • This tool tracks outreach metadata only. It does not give financial, tax,
    legal, or business advice.
  • If a creator picks the monetization-optimizer template, remind them on
    delivery: "Not financial advice. Not tax advice. Vietnam-resident creators
    with international platform earnings — consult a licensed local advisor."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---- The 20 templates (mirrors templates/creator/) -------------------------

CREATOR_TEMPLATES: tuple[str, ...] = (
    "content-idea-generator",
    "reply-drafter",
    "analytics-summarizer",
    "monetization-optimizer",
    "thread-builder",
    "mention-summarizer",
    "dm-triager",
    "trend-aligned-poster",
    "quote-tweet-suggestor",
    "follower-quality-analyzer",
    "niche-influencer-finder",
    "cross-platform-reposter",
    "content-calendar-builder",
    "ab-test-suggester",
    "comment-engagement-booster",
    "hashtag-strategy-advisor",
    "growth-experiment-runner",
    "competitor-watch",
    "content-recycler",
    "brand-voice-trainer",
)

STATUS_VALUES: tuple[str, ...] = ("pending", "responded", "delivered", "declined", "stale")
MIN_FOLLOWER_FLOOR = 10_000  # program eligibility per CLAUDE.md §2


# ---- Storage layout --------------------------------------------------------


def appdata_dir() -> Path:
    """Resolve $env:LOCALAPPDATA\\grok-agent\\creator-program\\ on Windows.

    Falls back to ~/AppData/Local on dev machines without the env var set,
    and to ~/.grok-agent-test on non-Windows CI runners (CI only — never the
    end-user path).
    """
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        base = Path(local_app)
    elif sys.platform == "win32":
        base = Path.home() / "AppData" / "Local"
    else:
        # CI / non-Windows fallback so smoke tests stay green; never the path
        # an end user actually hits in production.
        base = Path.home() / ".grok-agent-test"
    return base / "grok-agent" / "creator-program"


def store_path() -> Path:
    return appdata_dir() / "outreach.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load() -> dict[str, Any]:
    p = store_path()
    if not p.exists():
        return {"version": 1, "created_at": _utcnow(), "entries": []}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict[str, Any]) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)


# ---- Validation ------------------------------------------------------------


def _validate_handle(handle: str) -> str:
    h = handle.strip().lstrip("@")
    if not h or " " in h or len(h) > 15:
        raise SystemExit(f"ERROR: invalid X handle: {handle!r} (max 15 chars, no spaces)")
    return h


def _validate_template(template: str) -> str:
    if template not in CREATOR_TEMPLATES:
        valid = ", ".join(CREATOR_TEMPLATES)
        raise SystemExit(f"ERROR: unknown template {template!r}. Valid: {valid}")
    return template


def _validate_followers(n: int) -> int:
    if n < MIN_FOLLOWER_FLOOR:
        raise SystemExit(
            f"ERROR: follower_count={n} below program floor of {MIN_FOLLOWER_FLOOR}. "
            "The Creator Agent Program targets 10k+ creators only."
        )
    return n


def _next_id(entries: list[dict[str, Any]]) -> str:
    return f"OR-{len(entries) + 1:04d}"


# ---- Commands --------------------------------------------------------------


def cmd_log(args: argparse.Namespace) -> int:
    if not args.consent:
        print(
            "REFUSED: --consent flag required. Per the privacy contract, this "
            "tracker only logs an X handle when the creator has DM'd YOU first "
            "(explicit inbound consent). Re-run with --consent if that holds.",
            file=sys.stderr,
        )
        return 2

    handle = _validate_handle(args.handle)
    template = _validate_template(args.template)
    followers = _validate_followers(args.followers)
    niche = args.niche.strip()[:80] if args.niche else "unspecified"

    data = _load()
    entry_id = _next_id(data["entries"])

    entry: dict[str, Any] = {
        "id": entry_id,
        "handle": handle,
        "niche": niche,
        "follower_count": followers,
        "chosen_template": template,
        "logged_at": _utcnow(),
        "responded_at": None,
        "delivered_at": None,
        "status": "pending",
        "notes": (args.notes or "").strip()[:500],
        "consent_recorded": True,
    }
    data["entries"].append(entry)
    _save(data)

    print(f"Logged outreach {entry_id} for @{handle} → {template} ({followers:,} followers).")
    if template == "monetization-optimizer":
        print(
            "REMINDER on delivery: 'Not financial advice. Not tax advice. "
            "Vietnam-resident creators with international platform earnings — "
            "consult a licensed local advisor before acting on any output.'"
        )
    return 0


def _find_entry(data: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for e in data["entries"]:
        if e["id"] == entry_id:
            return e
    raise SystemExit(f"ERROR: no outreach entry with id {entry_id!r}")


def cmd_respond(args: argparse.Namespace) -> int:
    data = _load()
    entry = _find_entry(data, args.id)
    if entry["status"] not in ("pending", "stale"):
        print(f"WARN: entry {entry['id']} is already {entry['status']}; updating anyway.")
    entry["responded_at"] = _utcnow()
    entry["status"] = "responded"
    if args.notes:
        existing = entry.get("notes", "")
        sep = " | " if existing else ""
        entry["notes"] = (existing + sep + args.notes.strip())[:500]
    _save(data)
    print(f"Marked {entry['id']} as responded.")
    return 0


def cmd_deliver(args: argparse.Namespace) -> int:
    data = _load()
    entry = _find_entry(data, args.id)
    if entry["status"] == "delivered":
        print(f"WARN: entry {entry['id']} already delivered at {entry['delivered_at']}.")
        return 0
    entry["delivered_at"] = _utcnow()
    entry["status"] = "delivered"
    if args.notes:
        existing = entry.get("notes", "")
        sep = " | " if existing else ""
        entry["notes"] = (existing + sep + args.notes.strip())[:500]
    _save(data)
    print(f"Marked {entry['id']} as delivered. Template: {entry['chosen_template']}.")
    if entry["chosen_template"] == "monetization-optimizer":
        print(
            "On delivery DM, paste: 'Not financial advice. Not tax advice. "
            "Vietnam-resident creators with international platform earnings — "
            "please consult a licensed local advisor before acting.'"
        )
    return 0


def cmd_decline(args: argparse.Namespace) -> int:
    data = _load()
    entry = _find_entry(data, args.id)
    entry["status"] = "declined"
    if args.notes:
        existing = entry.get("notes", "")
        sep = " | " if existing else ""
        entry["notes"] = (existing + sep + args.notes.strip())[:500]
    _save(data)
    print(f"Marked {entry['id']} as declined.")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    data = _load()
    if not data["entries"]:
        print("(no outreach logged yet — run `log` to start)")
        return 0
    rows = sorted(data["entries"], key=lambda e: e["logged_at"], reverse=True)
    print(f"{'ID':<8} {'Handle':<18} {'Template':<28} {'Followers':>10} {'Status':<10} Logged")
    print("-" * 96)
    for e in rows:
        print(
            f"{e['id']:<8} @{e['handle']:<17} {e['chosen_template']:<28} "
            f"{e['follower_count']:>10,} {e['status']:<10} {e['logged_at'][:10]}"
        )
    return 0


def cmd_stats(_args: argparse.Namespace) -> int:
    data = _load()
    entries = data["entries"]
    total = len(entries)
    if total == 0:
        print("(no outreach logged yet)")
        return 0

    by_status: dict[str, int] = {s: 0 for s in STATUS_VALUES}
    by_template: dict[str, int] = {}
    for e in entries:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        t = e["chosen_template"]
        by_template[t] = by_template.get(t, 0) + 1

    delivered = by_status.get("delivered", 0)
    responded = by_status.get("responded", 0) + delivered
    response_rate = (responded / total * 100.0) if total else 0.0
    delivery_rate = (delivered / total * 100.0) if total else 0.0

    print(f"Outreach total : {total}")
    print(f"Response rate  : {response_rate:.1f}%  ({responded} responded, {delivered} delivered)")
    print(f"Delivery rate  : {delivery_rate:.1f}%  (target: 30 delivered creators)")
    print()
    print("By status:")
    for s in STATUS_VALUES:
        print(f"  {s:<11} {by_status.get(s, 0):>4}")
    print()
    print("Top templates requested:")
    for t, n in sorted(by_template.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:>3}  {t}")
    print()
    print(f"Store: {store_path()}")
    return 0


# ---- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="outreach-tracker",
        description=(
            "Local-first outreach tracker for the Grok Agent OS Creator Program. "
            "Built for xAI, X, Grok and the ecosystem community. ❤️"
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    log = sub.add_parser("log", help="Log a new outreach attempt (requires --consent)")
    log.add_argument("--handle", required=True, help="X handle (with or without leading @)")
    log.add_argument("--niche", required=True, help="Creator niche (max 80 chars)")
    log.add_argument(
        "--followers", type=int, required=True, help=f"Follower count (must be >= {MIN_FOLLOWER_FLOOR:,})"
    )
    log.add_argument(
        "--template", required=True, help="One of the 20 creator templates (see README)"
    )
    log.add_argument("--notes", default="", help="Free-form notes (max 500 chars, local-only)")
    log.add_argument(
        "--consent",
        action="store_true",
        help="Confirm the creator DM'd you first (required by privacy contract)",
    )
    log.set_defaults(func=cmd_log)

    respond = sub.add_parser("respond", help="Mark an outreach as responded")
    respond.add_argument("--id", required=True, help="Entry ID, e.g. OR-0007")
    respond.add_argument("--notes", default="", help="Append notes")
    respond.set_defaults(func=cmd_respond)

    deliver = sub.add_parser("deliver", help="Mark an agent as delivered")
    deliver.add_argument("--id", required=True, help="Entry ID, e.g. OR-0007")
    deliver.add_argument("--notes", default="", help="Append notes")
    deliver.set_defaults(func=cmd_deliver)

    decline = sub.add_parser("decline", help="Mark an outreach as declined")
    decline.add_argument("--id", required=True, help="Entry ID, e.g. OR-0007")
    decline.add_argument("--notes", default="", help="Append notes")
    decline.set_defaults(func=cmd_decline)

    sub.add_parser("list", help="List all outreach (most recent first)").set_defaults(func=cmd_list)
    sub.add_parser("stats", help="Print live program stats").set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
