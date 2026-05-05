# Copyright 2026 AgentMindCloud
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0
#
# Built to help xAI and Grok win — the local-first operator dashboard for
# the Creator Agent Program. Reads outreach.json + testimonials.json from
# AppData; never makes outbound network calls; never modifies the source
# stores.
"""creator-dashboard.py — Creator Agent Program operator dashboard.

Two output modes:

  python creator-dashboard.py          # terminal summary (stdout)
  python creator-dashboard.py --html PATH   # write a single-file HTML report

The dashboard combines outreach + testimonials data and surfaces the
v1.5-improvements §2.4 "Niches × Templates" matrix that lets the operator
tailor DMs by niche.

Privacy: read-only over the local stores. No edits, no network calls.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Mirrors outreach-tracker.py / testimonial-collector.py — single source of truth.
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

# Niche → suggested under-loved templates (per v1.5-improvements §2.5).
NICHE_RECOMMENDATIONS: dict[str, tuple[str, ...]] = {
    "ai-agents": ("competitor-watch", "niche-influencer-finder"),
    "fintech": ("brand-voice-trainer", "cross-platform-reposter"),
    "fitness": ("content-calendar-builder", "comment-engagement-booster"),
    "developer-tools": ("ab-test-suggester", "growth-experiment-runner"),
    "education": ("content-recycler", "quote-tweet-suggestor"),
    "gaming": ("trend-aligned-poster", "comment-engagement-booster"),
    "food": ("content-calendar-builder", "cross-platform-reposter"),
    "travel": ("cross-platform-reposter", "content-recycler"),
    "climate": ("thread-builder", "quote-tweet-suggestor"),
    "web3": ("competitor-watch", "monetization-optimizer"),
}


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


def _load_json(filename: str) -> dict[str, Any]:
    p = appdata_dir() / filename
    if not p.exists():
        return {"version": 1, "entries": []}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ---- Aggregations ---------------------------------------------------------


def _funnel(outreach: list[dict[str, Any]]) -> dict[str, int | float]:
    total = len(outreach)
    by_status: dict[str, int] = {}
    for e in outreach:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    delivered = by_status.get("delivered", 0)
    responded = by_status.get("responded", 0) + delivered
    return {
        "total": total,
        "delivered": delivered,
        "responded": responded,
        "pending": by_status.get("pending", 0),
        "declined": by_status.get("declined", 0),
        "stale": by_status.get("stale", 0),
        "response_rate": (responded / total * 100.0) if total else 0.0,
        "delivery_rate": (delivered / total * 100.0) if total else 0.0,
    }


def _top_niches(outreach: list[dict[str, Any]], n: int = 10) -> list[tuple[str, int]]:
    by_niche: dict[str, int] = {}
    for e in outreach:
        k = (e.get("niche") or "unspecified").strip().lower()
        by_niche[k] = by_niche.get(k, 0) + 1
    return sorted(by_niche.items(), key=lambda kv: -kv[1])[:n]


def _top_templates(outreach: list[dict[str, Any]], n: int = 20) -> list[tuple[str, int]]:
    by_t: dict[str, int] = {}
    for e in outreach:
        t = e["chosen_template"]
        by_t[t] = by_t.get(t, 0) + 1
    return sorted(by_t.items(), key=lambda kv: -kv[1])[:n]


def _zero_signup_templates(outreach: list[dict[str, Any]]) -> list[str]:
    seen = {e["chosen_template"] for e in outreach}
    return [t for t in CREATOR_TEMPLATES if t not in seen]


def _niche_template_matrix(outreach: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Niche -> {template -> count}. Powers the v1.5 §2.4 dashboard view."""
    matrix: dict[str, dict[str, int]] = {}
    for e in outreach:
        niche = (e.get("niche") or "unspecified").strip().lower()
        tpl = e["chosen_template"]
        matrix.setdefault(niche, {})
        matrix[niche][tpl] = matrix[niche].get(tpl, 0) + 1
    return matrix


def _testimonial_summary(testimonials: list[dict[str, Any]]) -> dict[str, Any]:
    publishable = [
        t for t in testimonials
        if t.get("consent_to_publish") and not t.get("revoked_at")
    ]
    return {
        "total": len(testimonials),
        "publishable": len(publishable),
        "anonymous": sum(
            1 for t in publishable if not t.get("consent_to_attribute")
        ),
        "monetization": sum(
            1 for t in publishable if "monetization-optimizer" in t.get("templates_used", [])
        ),
        "recent": sorted(publishable, key=lambda t: t["captured_at"], reverse=True)[:3],
    }


def recommend_for_niche(niche: str) -> list[str]:
    return list(NICHE_RECOMMENDATIONS.get(niche.strip().lower(), ()))


# ---- Terminal renderer ---------------------------------------------------


def _render_terminal(outreach: list[dict[str, Any]], testimonials: list[dict[str, Any]]) -> str:
    funnel = _funnel(outreach)
    niches = _top_niches(outreach, 10)
    tpls = _top_templates(outreach, 10)
    zero = _zero_signup_templates(outreach)
    ts = _testimonial_summary(testimonials)
    matrix = _niche_template_matrix(outreach)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  CREATOR AGENT PROGRAM — DASHBOARD")
    lines.append(f"  {now}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("FUNNEL")
    lines.append("------")
    lines.append(f"  Outreach total : {funnel['total']:>4}")
    lines.append(
        f"  Responded      : {funnel['responded']:>4}  "
        f"({funnel['response_rate']:.1f}%)"
    )
    lines.append(
        f"  Delivered      : {funnel['delivered']:>4}  "
        f"({funnel['delivery_rate']:.1f}%)   target: 30"
    )
    lines.append(f"  Pending        : {funnel['pending']:>4}")
    lines.append(f"  Declined       : {funnel['declined']:>4}")
    lines.append(f"  Stale          : {funnel['stale']:>4}")
    lines.append("")

    lines.append("TOP NICHES")
    lines.append("----------")
    if niches:
        for niche, count in niches:
            lines.append(f"  {count:>3}  {niche}")
    else:
        lines.append("  (no outreach yet)")
    lines.append("")

    lines.append("TOP TEMPLATES (requested)")
    lines.append("-------------------------")
    if tpls:
        for t, c in tpls:
            lines.append(f"  {c:>3}  {t}")
    else:
        lines.append("  (no outreach yet)")
    lines.append("")

    if zero:
        lines.append(f"ZERO-SIGNUP TEMPLATES ({len(zero)} of 20)")
        lines.append("-" * 35)
        lines.append(
            "  Surface these in DM macros (v1.5 §2.5). They aren't worse —"
        )
        lines.append("  they're less discoverable.")
        for t in zero:
            lines.append(f"  • {t}")
        lines.append("")

    lines.append("NICHES × TEMPLATES (v1.5 §2.4)")
    lines.append("-------------------------------")
    if matrix:
        for niche, tpls_in_niche in sorted(matrix.items()):
            top = sorted(tpls_in_niche.items(), key=lambda kv: -kv[1])[:3]
            top_str = ", ".join(f"{t} ({c})" for t, c in top)
            recs = recommend_for_niche(niche)
            recs_str = (
                f"  → suggest also: {', '.join(recs)}" if recs else ""
            )
            lines.append(f"  {niche:<18} {top_str}")
            if recs_str:
                lines.append(recs_str)
    else:
        lines.append("  (no outreach yet)")
    lines.append("")

    lines.append("TESTIMONIALS")
    lines.append("------------")
    lines.append(f"  Total            : {ts['total']:>4}")
    lines.append(f"  Publishable      : {ts['publishable']:>4}")
    lines.append(f"  Anonymous        : {ts['anonymous']:>4}")
    lines.append(
        f"  Monetization-OP  : {ts['monetization']:>4}   "
        "(V.1+V.2 footer required)"
    )
    if ts["recent"]:
        lines.append("  Most recent (publishable):")
        for t in ts["recent"]:
            attrib = (
                f"@{t['handle']}" if t.get("consent_to_attribute") else "anon"
            )
            quote_short = t["quote"][:80] + ("…" if len(t["quote"]) > 80 else "")
            lines.append(f'    • {attrib}: "{quote_short}"')
    lines.append("")

    lines.append("DISCLAIMERS (Constitution V.1 + V.2)")
    lines.append("------------------------------------")
    lines.append("  Not financial advice. Not tax advice.")
    lines.append("  Vietnam-resident creators with international platform")
    lines.append("  earnings: consult a licensed local advisor.")
    lines.append("")
    lines.append("Built to help xAI and Grok win.")
    return "\n".join(lines)


# ---- HTML renderer -------------------------------------------------------

# Cinnabar / parchment palette per CLAUDE.md branding for visual assets.
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Creator Agent Program — Dashboard</title>
<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<style>
  :root {{
    --bg: #f6efe1;
    --ink: #2a1a14;
    --accent: #c1442f;
    --accent-soft: #e07a63;
    --muted: #7a6a5e;
    --rule: #d8c8b3;
    --card: #fbf6ec;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px;
    background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    line-height: 1.5;
  }}
  h1 {{ margin: 0 0 4px 0; font-size: 28px; color: var(--accent); }}
  h2 {{ margin: 32px 0 8px; font-size: 18px; border-bottom: 2px solid var(--rule); padding-bottom: 6px; }}
  .meta {{ color: var(--muted); margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
  .card {{
    background: var(--card); border: 1px solid var(--rule); border-radius: 8px;
    padding: 16px;
  }}
  .card .num {{ font-size: 32px; font-weight: 600; color: var(--accent); }}
  .card .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--rule); font-size: 14px; }}
  th {{ background: var(--card); font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{ background: var(--card); padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  blockquote {{
    margin: 8px 0; padding: 8px 14px;
    border-left: 4px solid var(--accent-soft);
    background: var(--card);
    font-style: italic;
  }}
  .disclaimer {{
    margin-top: 32px; padding: 12px 16px; border: 1px solid var(--accent);
    border-radius: 8px; background: rgba(193, 68, 47, 0.06);
    font-size: 13px; color: var(--ink);
  }}
  .footer {{ margin-top: 24px; color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
<h1>Creator Agent Program — Dashboard</h1>
<div class="meta">Generated {now} · Built to help xAI and Grok win 🚀</div>

<h2>Funnel</h2>
<div class="grid">
  <div class="card"><div class="num">{total}</div><div class="label">Outreach total</div></div>
  <div class="card"><div class="num">{responded}</div><div class="label">Responded ({response_rate:.1f}%)</div></div>
  <div class="card"><div class="num">{delivered}</div><div class="label">Delivered ({delivery_rate:.1f}% · target 30)</div></div>
  <div class="card"><div class="num">{pending}</div><div class="label">Pending</div></div>
  <div class="card"><div class="num">{declined}</div><div class="label">Declined</div></div>
  <div class="card"><div class="num">{stale}</div><div class="label">Stale (auto-flagged)</div></div>
</div>

<h2>Top niches</h2>
{top_niches_table}

<h2>Top templates requested</h2>
{top_templates_table}

<h2>Niches × Templates (v1.5 §2.4 — paste into DMs)</h2>
{matrix_table}

<h2>Zero-signup templates ({zero_count} / 20)</h2>
<p>Surface these in welcome DM macros — they aren't worse, just less discoverable.</p>
{zero_table}

<h2>Testimonials</h2>
<div class="grid">
  <div class="card"><div class="num">{ts_total}</div><div class="label">Total</div></div>
  <div class="card"><div class="num">{ts_publishable}</div><div class="label">Publishable</div></div>
  <div class="card"><div class="num">{ts_monetization}</div><div class="label">Monetization-OP (V.1+V.2 required)</div></div>
</div>
<h3>Most recent (publishable)</h3>
{recent_testimonials}

<div class="disclaimer">
  <strong>⚠️ Not financial advice. Not tax advice.</strong>
  Where the dashboard surfaces the <code>monetization-optimizer</code> template,
  the standard V.1 + V.2 disclaimer + Vietnam-resident addendum from
  <code>safety/constitution.md</code> apply unchanged. Always consult a
  licensed advisor before acting on any output.
</div>

<div class="footer">
  Source: <code>$env:LOCALAPPDATA\\grok-agent\\creator-program\\</code>
  · No data leaves your machine · Apache 2.0 · Built to help xAI and Grok win.
</div>
</body>
</html>
"""


def _table(headers: list[str], rows: list[list[str]], num_cols: tuple[int, ...] = ()) -> str:
    th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_rows: list[str] = []
    for row in rows:
        tds = []
        for i, cell in enumerate(row):
            klass = ' class="num"' if i in num_cols else ""
            tds.append(f"<td{klass}>{cell}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    body = "".join(body_rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _render_html(outreach: list[dict[str, Any]], testimonials: list[dict[str, Any]]) -> str:
    funnel = _funnel(outreach)
    niches = _top_niches(outreach, 15)
    tpls = _top_templates(outreach, 20)
    zero = _zero_signup_templates(outreach)
    matrix = _niche_template_matrix(outreach)
    ts = _testimonial_summary(testimonials)

    top_niches_table = _table(
        ["Niche", "Count"],
        [[html.escape(n), str(c)] for n, c in niches] or [["(no outreach yet)", "—"]],
        num_cols=(1,),
    )
    top_templates_table = _table(
        ["Template", "Count"],
        [[f"<code>{html.escape(t)}</code>", str(c)] for t, c in tpls]
        or [["(no outreach yet)", "—"]],
        num_cols=(1,),
    )

    matrix_rows: list[list[str]] = []
    for niche, m in sorted(matrix.items()):
        top = sorted(m.items(), key=lambda kv: -kv[1])[:3]
        cells = ", ".join(
            f"<code>{html.escape(t)}</code> ({c})" for t, c in top
        )
        recs = recommend_for_niche(niche)
        recs_str = (
            "Suggest also: "
            + ", ".join(f"<code>{html.escape(t)}</code>" for t in recs)
            if recs
            else ""
        )
        matrix_rows.append([html.escape(niche), cells, recs_str])
    matrix_table = _table(
        ["Niche", "Top picks", "Suggest also (under-loved)"], matrix_rows
    ) if matrix_rows else "<p>(no outreach yet)</p>"

    zero_table = _table(
        ["Template"], [[f"<code>{html.escape(t)}</code>"] for t in zero]
    ) if zero else "<p>All templates have at least one sign-up. 🎉</p>"

    if ts["recent"]:
        recent_blocks: list[str] = []
        for t in ts["recent"]:
            attrib = (
                f"— @{html.escape(t['handle'])}"
                if t.get("consent_to_attribute")
                else "— anonymous"
            )
            quote = html.escape(t["quote"])
            tpls_used = ", ".join(
                f"<code>{html.escape(x)}</code>" for x in t.get("templates_used", [])
            )
            recent_blocks.append(
                f'<blockquote>"{quote}"<br><small>{attrib} · {tpls_used}</small></blockquote>'
            )
        recent_testimonials = "\n".join(recent_blocks)
    else:
        recent_testimonials = "<p>(no publishable testimonials yet)</p>"

    return _HTML_TEMPLATE.format(
        now=html.escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        total=funnel["total"],
        responded=funnel["responded"],
        response_rate=funnel["response_rate"],
        delivered=funnel["delivered"],
        delivery_rate=funnel["delivery_rate"],
        pending=funnel["pending"],
        declined=funnel["declined"],
        stale=funnel["stale"],
        top_niches_table=top_niches_table,
        top_templates_table=top_templates_table,
        matrix_table=matrix_table,
        zero_count=len(zero),
        zero_table=zero_table,
        ts_total=ts["total"],
        ts_publishable=ts["publishable"],
        ts_monetization=ts["monetization"],
        recent_testimonials=recent_testimonials,
    )


# ---- CLI -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="creator-dashboard",
        description=(
            "Local-first operator dashboard for the Creator Agent Program. "
            "Built to help xAI and Grok win."
        ),
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Write a single-file HTML dashboard to this path (terminal output is suppressed)",
    )
    args = parser.parse_args(argv)

    outreach = _load_json("outreach.json").get("entries", [])
    testimonials = _load_json("testimonials.json").get("entries", [])

    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(_render_html(outreach, testimonials), encoding="utf-8")
        print(f"Wrote dashboard → {args.html}")
    else:
        sys.stdout.write(_render_terminal(outreach, testimonials))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
