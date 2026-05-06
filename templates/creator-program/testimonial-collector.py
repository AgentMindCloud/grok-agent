# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built for xAI, X, Grok and the ecosystem community — the local-first testimonial collection
# system for the Creator Agent Program. Captures consent-gated quotes from
# real creators and turns them into publish-ready markdown cards. Mirrors the
# storage + privacy contract of outreach-tracker.py.
"""testimonial-collector.py — Creator Agent Program testimonial collector.

Subcommands:

  python testimonial-collector.py add            — record a new testimonial
  python testimonial-collector.py list           — list all testimonials
  python testimonial-collector.py export         — export to markdown / JSON
  python testimonial-collector.py generate-cards — render publish-ready cards
  python testimonial-collector.py revoke         — flip consent to off
  python testimonial-collector.py stats          — counts + linkage to outreach

Storage: $env:LOCALAPPDATA\\grok-agent\\creator-program\\testimonials.json

Privacy contract (matches outreach-tracker.py):
  • Testimonials are recorded ONLY with explicit consent. The `add` command
    refuses without --consent-publish.
  • Attribution is a SECOND, separate flag (--consent-attribute). A creator
    may consent to publish but ask to remain anonymous.
  • generate-cards / export emit ONLY entries where consent_to_publish=True.
  • A revoke flips consent off; revoked entries are kept on disk (audit
    trail) but excluded from every public output forever.
  • Honest-feedback principle: NEVER edit a quote for tone. If a creator
    sends mixed feedback, log it verbatim or don't log it at all.

Disclaimers:
  • This tool collects social proof, not financial / tax / legal claims.
  • If a testimonial mentions monetization-optimizer outcomes, the
    generate-cards output appends the standard V.1+V.2 disclaimer footer
    automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Mirrors outreach-tracker.py — the 20 valid template slugs.
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

VALID_SOURCES: tuple[str, ...] = ("dm", "x-reply", "x-quote-tweet", "email", "voice-memo", "other")
QUOTE_MIN_CHARS = 20
QUOTE_MAX_CHARS = 600


# ---- Storage --------------------------------------------------------------


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
    return appdata_dir() / "testimonials.json"


def outreach_path() -> Path:
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


# ---- Validation -----------------------------------------------------------


def _validate_handle(handle: str) -> str:
    h = handle.strip().lstrip("@")
    if not h or " " in h or len(h) > 15:
        raise SystemExit(f"ERROR: invalid X handle: {handle!r} (max 15 chars, no spaces)")
    return h


def _validate_quote(q: str) -> str:
    qs = q.strip()
    if len(qs) < QUOTE_MIN_CHARS:
        raise SystemExit(f"ERROR: quote too short ({len(qs)} chars; min {QUOTE_MIN_CHARS}).")
    if len(qs) > QUOTE_MAX_CHARS:
        raise SystemExit(f"ERROR: quote too long ({len(qs)} chars; max {QUOTE_MAX_CHARS}).")
    return qs


def _validate_templates(templates: list[str]) -> list[str]:
    if not templates:
        raise SystemExit("ERROR: at least one --template is required.")
    out: list[str] = []
    for t in templates:
        t = t.strip()
        if t not in CREATOR_TEMPLATES:
            valid = ", ".join(CREATOR_TEMPLATES)
            raise SystemExit(f"ERROR: unknown template {t!r}. Valid: {valid}")
        if t not in out:
            out.append(t)
    return out


def _validate_source(source: str) -> str:
    if source not in VALID_SOURCES:
        valid = ", ".join(VALID_SOURCES)
        raise SystemExit(f"ERROR: invalid source {source!r}. Valid: {valid}")
    return source


def _validate_outreach_link(outreach_id: str | None) -> str | None:
    if not outreach_id:
        return None
    p = outreach_path()
    if not p.exists():
        print(f"WARN: outreach store not found at {p}; storing link {outreach_id!r} unverified.")
        return outreach_id
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not any(e["id"] == outreach_id for e in data.get("entries", [])):
        raise SystemExit(
            f"ERROR: outreach id {outreach_id!r} not found in outreach.json. "
            "Either log the outreach first via outreach-tracker.py, or omit --outreach-id."
        )
    return outreach_id


def _next_id(entries: list[dict[str, Any]]) -> str:
    return f"TS-{len(entries) + 1:04d}"


# ---- Commands -------------------------------------------------------------


def cmd_add(args: argparse.Namespace) -> int:
    if not args.consent_publish:
        print(
            "REFUSED: --consent-publish flag required. Per the privacy contract, "
            "testimonials are only recorded with explicit publish consent. If "
            "the creator hasn't agreed in writing, do not log this.",
            file=sys.stderr,
        )
        return 2

    handle = _validate_handle(args.handle)
    quote = _validate_quote(args.quote)
    templates = _validate_templates(args.template)
    source = _validate_source(args.source)
    outreach_id = _validate_outreach_link(args.outreach_id)

    data = _load()
    entry_id = _next_id(data["entries"])

    entry: dict[str, Any] = {
        "id": entry_id,
        "handle": handle,
        "niche": (args.niche or "unspecified").strip()[:80],
        "follower_count": int(args.followers) if args.followers is not None else None,
        "quote": quote,
        "templates_used": templates,
        "source": source,
        "linked_outreach_id": outreach_id,
        "captured_at": _utcnow(),
        "consent_to_publish": True,
        "consent_to_attribute": bool(args.consent_attribute),
        "revoked_at": None,
        "revoked_reason": None,
        "notes": (args.notes or "").strip()[:500],
    }
    data["entries"].append(entry)
    _save(data)

    attribution = f"@{handle}" if entry["consent_to_attribute"] else "anonymous (consent-publish only)"
    print(f"Logged testimonial {entry_id} — {attribution} — templates: {', '.join(templates)}")
    if "monetization-optimizer" in templates:
        print(
            "NOTE: a monetization-optimizer testimonial will render with the "
            "V.1+V.2 disclaimer footer in any generated card / export."
        )
    return 0


def _find(data: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for e in data["entries"]:
        if e["id"] == entry_id:
            return e
    raise SystemExit(f"ERROR: no testimonial with id {entry_id!r}")


def cmd_revoke(args: argparse.Namespace) -> int:
    data = _load()
    entry = _find(data, args.id)
    if entry.get("revoked_at"):
        print(f"WARN: {entry['id']} already revoked at {entry['revoked_at']}.")
        return 0
    entry["consent_to_publish"] = False
    entry["revoked_at"] = _utcnow()
    entry["revoked_reason"] = (args.reason or "creator request").strip()[:200]
    _save(data)
    print(f"Revoked {entry['id']} — will be excluded from all public exports going forward.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = _load()
    entries = data["entries"]
    if not args.include_revoked:
        entries = [e for e in entries if not e.get("revoked_at")]
    if not entries:
        print("(no testimonials yet)")
        return 0
    print(f"{'ID':<8} {'Handle':<18} {'Niche':<20} {'Templates':<3} Captured")
    print("-" * 78)
    for e in sorted(entries, key=lambda e: e["captured_at"], reverse=True):
        anon = " (anon)" if not e.get("consent_to_attribute") else ""
        rev = " [REVOKED]" if e.get("revoked_at") else ""
        n_tpl = len(e["templates_used"])
        print(
            f"{e['id']:<8} @{e['handle']:<17}{anon} {e['niche']:<20} "
            f"{n_tpl:<3} {e['captured_at'][:10]}{rev}"
        )
    return 0


def _render_card(entry: dict[str, Any]) -> str:
    """Render a single publish-ready markdown testimonial card.

    Honest-feedback principle: the quote is rendered verbatim. We add
    attribution + a 'templates that helped' line and (when applicable) the
    finance disclaimer footer. We never edit the quote.
    """
    quote = entry["quote"].strip()
    templates_used = entry.get("templates_used", [])
    templates_md = ", ".join(f"`{t}`" for t in templates_used)

    if entry.get("consent_to_attribute"):
        followers = entry.get("follower_count")
        followers_str = f" · {followers // 1000}k followers" if followers else ""
        attribution_line = f"— @{entry['handle']} · {entry.get('niche','')}{followers_str}"
    else:
        attribution_line = (
            f"— anonymous creator · {entry.get('niche','')} "
            "(attribution withheld at creator's request)"
        )

    lines = [
        f"> \"{quote}\"",
        ">",
        f"> {attribution_line}",
        f"> Templates that helped: {templates_md}",
    ]

    if "monetization-optimizer" in templates_used:
        lines.extend(
            [
                ">",
                "> ⚠️ _Not financial advice. Not tax advice. The "
                "monetization-optimizer surfaces signals only — always consult "
                "a licensed advisor before acting._",
            ]
        )
    return "\n".join(lines)


def _publishable(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        e for e in data["entries"]
        if e.get("consent_to_publish") and not e.get("revoked_at")
    ]


def cmd_generate_cards(args: argparse.Namespace) -> int:
    data = _load()
    entries = _publishable(data)
    if args.template_filter:
        wanted = _validate_templates([args.template_filter])[0]
        entries = [e for e in entries if wanted in e.get("templates_used", [])]
    if not entries:
        print("(no publishable testimonials match the filter)")
        return 0

    entries.sort(key=lambda e: e["captured_at"], reverse=True)

    header = [
        "<!-- Copyright 2026 AgentMindCloud -->",
        "<!-- Licensed under the Apache License, Version 2.0 -->",
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->",
        "",
        "# Creator Agent Program — Testimonial Cards",
        "",
        f"> **Built for xAI, X, Grok and the ecosystem community. ❤️** Generated {_utcnow()[:10]}. "
        f"{len(entries)} card(s) — every quote is verbatim, every entry is "
        "consent-gated, every revoked entry is excluded.",
        "",
    ]
    if args.template_filter:
        header.append(f"_Filter: only testimonials mentioning `{args.template_filter}`._\n")

    body = ["\n\n---\n\n".join(_render_card(e) for e in entries)]
    footer = [
        "",
        "---",
        "",
        "_All testimonials are reproduced with explicit publish consent. "
        "Creators may revoke consent at any time; revoked entries are removed "
        "from this file on the next regeneration._",
        "",
        "_Built for xAI, X, Grok and the ecosystem community. ❤️_",
    ]
    out = "\n".join(header) + "\n".join(body) + "\n" + "\n".join(footer)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out, encoding="utf-8")
        print(f"Wrote {len(entries)} card(s) → {args.out}")
    else:
        sys.stdout.write(out)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    data = _load()
    if args.fmt == "json":
        # Export full schema, including revoked entries (with the revoke audit
        # fields), so the file is a faithful local backup. The PUBLIC variant
        # is generate-cards.
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"Wrote full JSON backup → {args.out}")
        else:
            sys.stdout.write(json.dumps(data, indent=2))
        return 0

    # markdown export = generate-cards under the hood
    return cmd_generate_cards(args)


def cmd_stats(_args: argparse.Namespace) -> int:
    data = _load()
    entries = data["entries"]
    total = len(entries)
    if total == 0:
        print("(no testimonials yet)")
        return 0

    publishable = len(_publishable(data))
    revoked = sum(1 for e in entries if e.get("revoked_at"))
    anonymous = sum(
        1 for e in entries
        if e.get("consent_to_publish") and not e.get("consent_to_attribute") and not e.get("revoked_at")
    )
    linked = sum(1 for e in entries if e.get("linked_outreach_id"))
    monetization = sum(
        1 for e in entries
        if "monetization-optimizer" in e.get("templates_used", [])
    )

    by_template: dict[str, int] = {}
    for e in entries:
        for t in e.get("templates_used", []):
            by_template[t] = by_template.get(t, 0) + 1

    print(f"Testimonials total : {total}")
    print(f"  Publishable     : {publishable}")
    print(f"  Anonymous       : {anonymous}")
    print(f"  Revoked         : {revoked}")
    print(f"  Linked outreach : {linked}/{total}")
    print(f"  Monetization-OP : {monetization}  (require V.1+V.2 footer)")
    print()
    print("Top templates mentioned:")
    for t, n in sorted(by_template.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:>3}  {t}")
    print()
    print(f"Store: {store_path()}")
    return 0


# ---- CLI ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="testimonial-collector",
        description=(
            "Local-first testimonial collector for the Grok Agent OS Creator "
            "Program. Built for xAI, X, Grok and the ecosystem community. ❤️"
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Record a new testimonial (consent required)")
    add.add_argument("--handle", required=True, help="Creator's X handle")
    add.add_argument("--niche", default="unspecified", help="Creator niche (max 80 chars)")
    add.add_argument("--followers", type=int, default=None, help="Follower count (optional)")
    add.add_argument(
        "--quote",
        required=True,
        help=f"The verbatim testimonial ({QUOTE_MIN_CHARS}-{QUOTE_MAX_CHARS} chars). Never edit for tone.",
    )
    add.add_argument(
        "--template",
        action="append",
        required=True,
        help="Repeat for each template. Must match a slug in templates/creator/.",
    )
    add.add_argument("--source", default="dm", help=f"Source channel ({', '.join(VALID_SOURCES)})")
    add.add_argument("--outreach-id", default=None, help="Optional OR-XXXX from outreach.json")
    add.add_argument("--notes", default="", help="Local-only notes (max 500 chars)")
    add.add_argument(
        "--consent-publish",
        action="store_true",
        help="Required. Confirm the creator agreed in writing to publication.",
    )
    add.add_argument(
        "--consent-attribute",
        action="store_true",
        help="Optional. Confirm the creator wants their handle public. Default: anonymous.",
    )
    add.set_defaults(func=cmd_add)

    revoke = sub.add_parser("revoke", help="Withdraw publish consent (kept on disk for audit)")
    revoke.add_argument("--id", required=True, help="TS-XXXX entry id")
    revoke.add_argument("--reason", default="creator request", help="Free-text reason (≤200 chars)")
    revoke.set_defaults(func=cmd_revoke)

    lst = sub.add_parser("list", help="List testimonials")
    lst.add_argument("--include-revoked", action="store_true", help="Also show revoked entries")
    lst.set_defaults(func=cmd_list)

    cards = sub.add_parser("generate-cards", help="Render publish-ready markdown cards")
    cards.add_argument("--out", type=Path, default=None, help="Write to file (default stdout)")
    cards.add_argument(
        "--template-filter",
        default=None,
        help="Only include testimonials mentioning this template slug",
    )
    cards.set_defaults(func=cmd_generate_cards)

    exp = sub.add_parser("export", help="Export to markdown (publish-ready) or JSON (full backup)")
    exp.add_argument("--fmt", choices=("markdown", "json"), default="markdown")
    exp.add_argument("--out", type=Path, default=None, help="Write to file (default stdout)")
    exp.add_argument("--template-filter", default=None, help="Markdown only — filter by template")
    exp.set_defaults(func=cmd_export)

    sub.add_parser("stats", help="Counts + outreach linkage").set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
