# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
"""Post the Mon/Wed/Fri curation digest to the public Discord.

Built for xAI, X, Grok and the ecosystem community. ❤️

This script is the bridge between two existing systems:

  1. ``docs/agent-trust-scores.json`` — deterministic, public, auditable
     trust scores produced by ``scripts/compute-trust-score.py``.
  2. ``creator-program/v2/curation/`` — the Mon/Wed/Fri creator-program
     curation outputs landed by ``.github/workflows/curation-cadence.yml``.

It assembles a markdown digest with the top-3 trust-tier agents this
week plus the most recent creator-template highlights, then POSTs it to
the Discord webhook URL configured as the ``DISCORD_WEBHOOK_URL``
repository secret.

Graceful-degradation contract (see CLAUDE.md §17 + §18):

- If ``DISCORD_WEBHOOK_URL`` is not set in the environment, OR
- If ``--dry-run`` is passed on argv,

the script prints the digest to stdout and exits 0. It never crashes
the CI workflow because of a missing optional secret.

Usage:

    python scripts/post-discord-digest.py
    python scripts/post-discord-digest.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRUST_SCORES = _REPO_ROOT / "docs" / "agent-trust-scores.json"
_CURATION_DIR = _REPO_ROOT / "creator-program" / "v2" / "curation"
_FOOTER_LINK = "https://github.com/AgentMindCloud/grok-agent"
_LOCALAPPDATA_CURATION = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    / "grok-agent"
    / "creator-program"
    / "curation"
)


def _load_trust_scores() -> dict[str, Any]:
    """Return the parsed trust-score JSON, or an empty stub when missing."""
    if not _TRUST_SCORES.exists():
        return {"agents": {}, "computed_at": "(missing)"}
    try:
        return json.loads(_TRUST_SCORES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(
            f"WARN: could not parse {_TRUST_SCORES.relative_to(_REPO_ROOT)}: {exc}\n"
        )
        return {"agents": {}, "computed_at": "(parse-error)"}


def _top_three_agents(trust_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the three highest-scoring agents, deterministic tiebreak by slug."""
    agents = list((trust_data.get("agents") or {}).values())
    agents.sort(key=lambda a: (-int(a.get("score", 0)), str(a.get("slug", ""))))
    return agents[:3]


def _recent_curation_outputs() -> list[Path]:
    """Return up to five recent curation output files from both candidate roots."""
    candidates: list[Path] = []
    for root in (_CURATION_DIR, _LOCALAPPDATA_CURATION):
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            if path.is_file():
                candidates.append(path)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:5]


def _summarise_curation_file(path: Path) -> str:
    """Return a short bullet-line summary for a curation output file."""
    rel = path.name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return f"- `{rel}` (could not parse JSON)"
    if isinstance(payload, dict):
        title = (
            payload.get("title")
            or payload.get("week_iso")
            or payload.get("subcommand")
            or payload.get("kind")
            or "curation output"
        )
        count = ""
        for key in ("templates", "selected", "items", "highlights", "retros"):
            value = payload.get(key)
            if isinstance(value, list):
                count = f" — {len(value)} item(s)"
                break
        return f"- `{rel}`: {title}{count}"
    if isinstance(payload, list):
        return f"- `{rel}` — {len(payload)} item(s)"
    return f"- `{rel}`"


def _format_agent_line(agent: dict[str, Any]) -> str:
    slug = agent.get("slug", "(unknown)")
    score = agent.get("score", 0)
    tier = agent.get("tier", "?")
    category = agent.get("category", "uncategorized")
    return f"- **{slug}** — tier {tier} ({score}/100) — `{category}`"


def assemble_digest() -> str:
    """Assemble the markdown digest body posted to Discord."""
    trust_data = _load_trust_scores()
    top_three = _top_three_agents(trust_data)
    curation_files = _recent_curation_outputs()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"# Grok Agent OS — Curation Digest ({now})")
    lines.append("")
    lines.append("Built for xAI, X, Grok and the ecosystem community. ❤️")
    lines.append("")
    lines.append("## Top-3 trust-tier agents this week")
    lines.append("")
    if top_three:
        for agent in top_three:
            lines.append(_format_agent_line(agent))
    else:
        lines.append("- (no scored agents found in `docs/agent-trust-scores.json`)")
    lines.append("")
    lines.append("## Recent creator-template highlights")
    lines.append("")
    if curation_files:
        for path in curation_files:
            lines.append(_summarise_curation_file(path))
    else:
        lines.append(
            "- (no recent curation output found under "
            "`creator-program/v2/curation/` or `$LOCALAPPDATA/grok-agent/creator-program/curation/`)"
        )
    lines.append("")
    lines.append(f"More: <{_FOOTER_LINK}>")
    return "\n".join(lines)


def _post_to_webhook(webhook_url: str, content: str) -> int:
    """POST the digest to Discord. Return process exit code (0 on success)."""
    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        sys.stderr.write(
            "ERROR: requests is not installed. Install: python -m pip install requests\n"
        )
        return 0  # graceful degradation — never crash CI on missing dep
    # Discord caps a single message at 2000 chars; truncate with a marker.
    payload_content = content
    if len(payload_content) > 1900:
        payload_content = payload_content[:1880] + "\n... (truncated)"
    try:
        response = requests.post(
            webhook_url,
            json={"content": payload_content},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001 — never crash CI on network glitch
        sys.stderr.write(f"WARN: Discord POST failed: {exc}\n")
        return 0
    if response.status_code >= 400:
        sys.stderr.write(
            f"WARN: Discord POST returned HTTP {response.status_code}: {response.text[:200]}\n"
        )
        return 0
    print(f"Discord POST OK (HTTP {response.status_code}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="post-discord-digest",
        description="Assemble and POST the curation digest to Discord.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest to stdout instead of POSTing to the webhook.",
    )
    args = parser.parse_args(argv)

    digest = assemble_digest()
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

    if args.dry_run or not webhook_url:
        if not webhook_url and not args.dry_run:
            print(
                "INFO: DISCORD_WEBHOOK_URL not set; printing digest to stdout.",
                file=sys.stderr,
            )
        print(digest)
        return 0

    return _post_to_webhook(webhook_url, digest)


if __name__ == "__main__":
    raise SystemExit(main())
