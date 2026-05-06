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
"""
Analytics Summarizer -- zero-dependency CLI demo runner.

Built for xAI, X, Grok and the ecosystem community. ❤️

This v1 runner is fully self-contained: it ships niche-aware offline metric
bundles with deterministic top-3 performers per bucket, plus a strict 6-section
synthesis pipeline that respects the 4 standard metric rows and the 3+3
direction/magnitude vocabulary defined in `prompts/system.md` (auto-loaded).
To wire to live Grok 4.3, replace the body of `generate_analytics_summary()`
with a Grok call that consumes the system prompt and returns the same schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --demo ai
    python run.py --x-handle @creator --metrics-file metrics.json --compare-to previous_period
    python run.py --x-handle @me --metrics '[{"metric":"impressions","current":412000,"prev":348000}]'
    python run.py --x-handle @test --metrics impressions,engagement,reach,follower_delta --date-range 2026-04-05:2026-05-05
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import random
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

VERSION = "0.1.0"
TAGLINE = "Built for xAI, X, Grok and the ecosystem community. ❤️"

BANNER = (
    "============================================================\n"
    f"  ANALYTICS SUMMARIZER  v{VERSION}\n"
    "  Your X numbers, briefed in 60 seconds.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

STANDARD_METRICS: Tuple[str, ...] = (
    "impressions", "engagement", "reach", "follower_delta",
)

DIRECTION_LABELS: Tuple[str, ...] = ("up", "down", "stable")
MAGNITUDE_LABELS: Tuple[str, ...] = ("small", "moderate", "large")

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2")),
]
DEFAULT_BUCKET = "general"

FINANCE_KEYWORDS = (
    "monetiz", "payout", "earnings", "sponsor", "cashtag",
    "token", "p&l", "tax", "invest",
)


def _fmt_number(n: float) -> str:
    """Compact human-readable number rendering (e.g. 412000 -> '412k')."""
    if n is None:
        return "--"
    a = abs(n)
    if a >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if a >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    if isinstance(n, int) or (isinstance(n, float) and n == int(n)):
        return f"{int(n):,}"
    return f"{n:.1f}"


# Per-bucket demo metric bundles (current vs prev) + top-3 posts.
DEMO_METRIC_BUNDLES: Dict[str, Dict[str, Any]] = {
    "ai": {
        "default_niche": "AI agents on X",
        "metrics": {
            "impressions": {"current": 412000, "prev": 348000},
            "engagement": {"current": 31200, "prev": 24600},
            "reach": {"current": 285000, "prev": 264000},
            "follower_delta": {"current": 4210, "prev": 2580},
        },
        "top_posts": [
            {"handle": "post_thread_42", "format": "thread", "headline_metric_name": "engagements", "headline_metric_value": 4820,
             "why": "8-tweet 'MCP servers explained' caught the active trend window"},
            {"handle": "post_quote_18", "format": "quote tweet", "headline_metric_name": "engagements", "headline_metric_value": 3140,
             "why": "replied to a niche contradiction -- disagreement is high-engagement"},
            {"handle": "post_image_05", "format": "image", "headline_metric_name": "engagements", "headline_metric_value": 2860,
             "why": "comparison chart format outperformed text-only in the same week"},
        ],
        "benchmark": {
            "impressions": 360000, "engagement": 24000, "reach": 270000, "follower_delta": 3000,
            "source": "100 mid-tier AI-creator handles, last 30d",
        },
    },
    "productivity": {
        "default_niche": "Productivity systems for solopreneurs",
        "metrics": {
            "impressions": {"current": 248000, "prev": 232000},
            "engagement": {"current": 21800, "prev": 19200},
            "reach": {"current": 195000, "prev": 188000},
            "follower_delta": {"current": 1820, "prev": 1450},
        },
        "top_posts": [
            {"handle": "post_thread_31", "format": "thread", "headline_metric_name": "engagements", "headline_metric_value": 3580,
             "why": "single-tab-focus playbook -- practical step-by-step in 6 tweets"},
            {"handle": "post_image_12", "format": "image", "headline_metric_name": "bookmarks", "headline_metric_value": 2240,
             "why": "weekly review template image got bookmarked widely"},
            {"handle": "post_reply_07", "format": "reply", "headline_metric_name": "engagements", "headline_metric_value": 1640,
             "why": "reply to a viral productivity thread surfaced fresh audience"},
        ],
        "benchmark": {
            "impressions": 220000, "engagement": 19500, "reach": 188000, "follower_delta": 1500,
            "source": "120 mid-tier productivity creator handles, last 30d",
        },
    },
    "finance": {
        "default_niche": "creator economy finance",
        "metrics": {
            "impressions": {"current": 184000, "prev": 152000},
            "engagement": {"current": 14800, "prev": 12100},
            "reach": {"current": 142000, "prev": 132000},
            "follower_delta": {"current": 1610, "prev": 1240},
        },
        "top_posts": [
            {"handle": "post_thread_22", "format": "thread", "headline_metric_name": "engagements", "headline_metric_value": 2680,
             "why": "X Money tax-export thread hit during creator-tax-season trending"},
            {"handle": "post_image_09", "format": "image", "headline_metric_name": "saves", "headline_metric_value": 1820,
             "why": "personal P&L dashboard screenshot drew the highest save rate"},
            {"handle": "post_quote_11", "format": "quote tweet", "headline_metric_name": "engagements", "headline_metric_value": 1340,
             "why": "rebuttal to a vendor benchmark claim -- contradiction lifted reach"},
        ],
        "benchmark": {
            "impressions": 165000, "engagement": 12800, "reach": 138000, "follower_delta": 1300,
            "source": "80 mid-tier finance-creator handles, last 30d",
        },
    },
    "creator": {
        "default_niche": "creator economy",
        "metrics": {
            "impressions": {"current": 320000, "prev": 305000},
            "engagement": {"current": 24600, "prev": 23900},
            "reach": {"current": 235000, "prev": 232000},
            "follower_delta": {"current": 1980, "prev": 1820},
        },
        "top_posts": [
            {"handle": "post_thread_19", "format": "thread", "headline_metric_name": "engagements", "headline_metric_value": 3120,
             "why": "owned-audience math thread reignited a long-running debate"},
            {"handle": "post_reply_15", "format": "reply", "headline_metric_name": "engagements", "headline_metric_value": 2050,
             "why": "value-add reply to a viral newsletter-vs-X funnel post"},
            {"handle": "post_quote_07", "format": "quote tweet", "headline_metric_name": "engagements", "headline_metric_value": 1490,
             "why": "data-led quote tweet on cadence research drew bookmarks"},
        ],
        "benchmark": {
            "impressions": 305000, "engagement": 23000, "reach": 230000, "follower_delta": 1700,
            "source": "150 mid-tier creator-economy handles, last 30d",
        },
    },
    "fitness": {
        "default_niche": "Zone 2 training",
        "metrics": {
            "impressions": {"current": 138000, "prev": 124000},
            "engagement": {"current": 11200, "prev": 9800},
            "reach": {"current": 108000, "prev": 102000},
            "follower_delta": {"current": 940, "prev": 720},
        },
        "top_posts": [
            {"handle": "post_thread_27", "format": "thread", "headline_metric_name": "engagements", "headline_metric_value": 1980,
             "why": "Zone-2-for-desk-workers thread caught the longevity trend wave"},
            {"handle": "post_image_03", "format": "image", "headline_metric_name": "saves", "headline_metric_value": 1410,
             "why": "VO2-max heart-rate-zones graphic became a save magnet"},
            {"handle": "post_video_02", "format": "video", "headline_metric_name": "views", "headline_metric_value": 8200,
             "why": "30-second form-cue video outperformed the rest of the week"},
        ],
        "benchmark": {
            "impressions": 125000, "engagement": 10000, "reach": 105000, "follower_delta": 800,
            "source": "60 mid-tier fitness-creator handles, last 30d",
        },
    },
    "general": {
        "default_niche": "X creator",
        "metrics": {
            "impressions": {"current": 92000, "prev": 88000},
            "engagement": {"current": 7400, "prev": 7100},
            "reach": {"current": 78000, "prev": 76000},
            "follower_delta": {"current": 580, "prev": 530},
        },
        "top_posts": [
            {"handle": "post_thread_05", "format": "thread", "headline_metric_name": "engagements", "headline_metric_value": 980,
             "why": "long-form takeaway thread with a contrarian opener"},
            {"handle": "post_image_02", "format": "image", "headline_metric_name": "saves", "headline_metric_value": 720,
             "why": "summary infographic compressed the week's lesson into one image"},
            {"handle": "post_reply_01", "format": "reply", "headline_metric_name": "engagements", "headline_metric_value": 410,
             "why": "value-add reply on a viral parent post drew a fresh audience"},
        ],
        "benchmark": {
            "impressions": 90000, "engagement": 7200, "reach": 76000, "follower_delta": 540,
            "source": "evergreen median across mid-tier creator handles",
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_bucket(blob: str) -> str:
    s = blob.lower()
    for bucket, keys in NICHE_BUCKETS:
        for k in keys:
            if k in s:
                return bucket
    return DEFAULT_BUCKET


def is_finance_adjacent(blob: str) -> bool:
    s = blob.lower()
    return any(k in s for k in FINANCE_KEYWORDS)


def deterministic_seed(x_handle: str, metrics_blob: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{metrics_blob}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def _pct(current: float, prev: float) -> Optional[float]:
    if prev == 0:
        return None
    return (current - prev) / prev * 100.0


def _direction_for(pct: Optional[float]) -> str:
    if pct is None:
        return "stable"
    if pct > 1.0:
        return "up"
    if pct < -1.0:
        return "down"
    return "stable"


def _magnitude_for(pct: Optional[float]) -> str:
    if pct is None:
        return "small"
    a = abs(pct)
    if a < 5.0:
        return "small"
    if a < 20.0:
        return "moderate"
    return "large"


def _format_pct(pct: Optional[float]) -> str:
    if pct is None:
        return "--"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _bundle_for_bucket(bucket: str) -> Dict[str, Any]:
    return DEMO_METRIC_BUNDLES.get(bucket, DEMO_METRIC_BUNDLES["general"])


def _records_from_bundle(bundle: Dict[str, Any], wanted: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    metric_names = wanted or list(STANDARD_METRICS)
    out: List[Dict[str, Any]] = []
    for name in metric_names:
        if name in bundle["metrics"]:
            row = bundle["metrics"][name]
            out.append({
                "metric": name,
                "current": row["current"],
                "prev": row.get("prev"),
            })
    return out


def parse_metrics_input(args: argparse.Namespace, bucket: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Return (metric_records, top_posts, source_label).

    Source label is one of: 'inline-json', 'file', 'demo', 'names+demo',
    'date-range-fallback'.
    """
    if args.metrics_file:
        text = Path(args.metrics_file).read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            records = data.get("metrics", [])
            top_posts = data.get("top_posts", [])
        else:
            records = data
            top_posts = []
        return list(records), list(top_posts), "file"

    if args.metrics:
        s = args.metrics.strip()
        if s.startswith("["):
            records = json.loads(s)
            return list(records), [], "inline-json"
        # Comma-separated metric names.
        names = [n.strip() for n in s.split(",") if n.strip()]
        bundle = _bundle_for_bucket(args.demo or bucket)
        return _records_from_bundle(bundle, wanted=names), list(bundle["top_posts"]), "names+demo"

    if args.demo:
        bundle = _bundle_for_bucket(args.demo)
        return _records_from_bundle(bundle), list(bundle["top_posts"]), "demo"

    if args.date_range:
        # No values supplied; fall back to bucket bundle so the demo still works.
        bundle = _bundle_for_bucket(bucket)
        return _records_from_bundle(bundle), list(bundle["top_posts"]), "date-range-fallback"

    raise ValueError("must supply --metrics, --metrics-file, --demo, or --date-range")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _enriched_metric_rows(
    records: List[Dict[str, Any]], compare_to: str,
) -> List[Dict[str, Any]]:
    """For each record, compute pct + direction + magnitude."""
    rows: List[Dict[str, Any]] = []
    for r in records:
        cur = r["current"]
        prev = r.get("prev") if compare_to != "none" else None
        pct = _pct(cur, prev) if prev not in (None, 0) else None
        rows.append({
            "metric": r["metric"],
            "current": cur,
            "prev": prev,
            "pct": pct,
            "direction": _direction_for(pct),
            "magnitude": _magnitude_for(pct),
            "delta_quote": _format_pct(pct),
        })
    return rows


def _ordered_standard_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return rows in standard order, with placeholders for missing metrics."""
    by_metric = {r["metric"]: r for r in rows}
    out: List[Dict[str, Any]] = []
    for name in STANDARD_METRICS:
        if name in by_metric:
            out.append(by_metric[name])
        else:
            out.append({
                "metric": name, "current": None, "prev": None, "pct": None,
                "direction": "stable", "magnitude": "small", "delta_quote": "--",
            })
    return out


def _detect_garbage_batch(rows: List[Dict[str, Any]]) -> bool:
    if not rows:
        return True
    empty = sum(1 for r in rows if r.get("current") in (None, 0))
    return empty / len(rows) > 0.7


def _build_trends(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Generate 3-5 trends from the standard metric rows."""
    by_metric = {r["metric"]: r for r in rows if r.get("current") is not None}

    trends: List[Dict[str, str]] = []

    # Trend 1: dominant metric movement (engagement preferred, else impressions)
    primary_name = "engagement" if "engagement" in by_metric else (
        "impressions" if "impressions" in by_metric else next(iter(by_metric), None)
    )
    if primary_name and by_metric[primary_name].get("pct") is not None:
        r = by_metric[primary_name]
        trends.append({
            "name": f"{primary_name} compounding" if r["direction"] == "up" else f"{primary_name} cooling",
            "direction": r["direction"],
            "magnitude": r["magnitude"],
            "delta_quote": r["delta_quote"],
            "plain_english": (
                f"Per-period {primary_name} moved {r['delta_quote']} -- "
                f"{'audience is staying longer' if r['direction'] == 'up' else 'momentum needs a refresh'}."
            ),
        })

    # Trend 2: follower velocity
    if "follower_delta" in by_metric and by_metric["follower_delta"].get("pct") is not None:
        r = by_metric["follower_delta"]
        trends.append({
            "name": "follower velocity",
            "direction": r["direction"],
            "magnitude": r["magnitude"],
            "delta_quote": r["delta_quote"],
            "plain_english": (
                f"Net follower additions moved {r['delta_quote']} -- "
                f"{'the niche is finding the account' if r['direction'] == 'up' else 'discovery slowed; consider a new posting cadence'}."
            ),
        })

    # Trend 3: reach-vs-engagement gap
    if "reach" in by_metric and "engagement" in by_metric:
        rr, re_ = by_metric["reach"], by_metric["engagement"]
        rp = rr.get("pct"); ep = re_.get("pct")
        if rp is not None and ep is not None:
            gap = ep - rp
            if abs(gap) >= 5.0:
                if gap > 0:
                    name = "reach lagging engagement"
                    plain = f"Engagement grew {ep:.1f}% but reach only grew {rp:.1f}% -- the existing audience is leaning in but distribution didn't compound; consider quote-tweet seeding."
                else:
                    name = "reach outpacing engagement"
                    plain = f"Reach grew {rp:.1f}% but engagement only grew {ep:.1f}% -- distribution is broadening but not landing; tighten the angle on next thread."
                trends.append({
                    "name": name,
                    "direction": "up" if gap > 0 else "down",
                    "magnitude": _magnitude_for(gap),
                    "delta_quote": f"engagement {_format_pct(ep)} vs reach {_format_pct(rp)}",
                    "plain_english": plain,
                })
            else:
                trends.append({
                    "name": "reach and engagement aligned",
                    "direction": "stable",
                    "magnitude": "small",
                    "delta_quote": f"engagement {_format_pct(ep)} vs reach {_format_pct(rp)}",
                    "plain_english": "Reach and engagement are moving in lockstep -- a clean signal week.",
                })

    # Trend 4: impressions-only fallback if engagement missing
    if "impressions" in by_metric and primary_name != "impressions" and len(trends) < 4:
        r = by_metric["impressions"]
        if r.get("pct") is not None:
            trends.append({
                "name": "impression volume",
                "direction": r["direction"],
                "magnitude": r["magnitude"],
                "delta_quote": r["delta_quote"],
                "plain_english": (
                    f"Total impressions moved {r['delta_quote']} -- "
                    f"{'distribution is expanding' if r['direction'] == 'up' else 'distribution contracting'}."
                ),
            })

    return trends[:5]


def _pick_top_3(top_posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not top_posts:
        return []
    posts = list(top_posts)
    # Sort by headline metric desc.
    posts.sort(key=lambda p: -float(p.get("headline_metric_value", 0)))
    return posts[:3]


def _build_recommendations(
    rows: List[Dict[str, Any]],
    trends: List[Dict[str, str]],
    top_posts: List[Dict[str, Any]],
    niche_label: str,
    bucket: str,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    bridges: List[Dict[str, Any]] = []
    by_metric = {r["metric"]: r for r in rows if r.get("current") is not None}

    if top_posts:
        winner = top_posts[0]
        bridges.append({
            "text": (
                f"Expand the angle from '{winner['handle']}' "
                f"into 5 more ideas via `content-idea-generator --niche \"{niche_label}\"` -- "
                f"the winning {winner.get('format', 'post')} format compounds when you stack it."
            ),
            "finance_tag": is_finance_adjacent(winner.get("why", "")),
        })

    follower = by_metric.get("follower_delta")
    if follower and follower.get("direction") == "up" and follower.get("magnitude") in ("moderate", "large"):
        bridges.append({
            "text": (
                f"Triage the +{int(follower['current']):,} new mentions surfaced this period via "
                "`mention-summarizer` -- fresh audience deserves a same-day reply pass."
            ),
            "finance_tag": False,
        })

    primary = next((t for t in trends if t.get("direction") == "up" and t.get("magnitude") in ("moderate", "large")), None)
    if primary:
        bridges.append({
            "text": (
                f"Ship 3 trend-aligned posts on the '{primary['name']}' uplift via "
                f"`trend-aligned-poster --niche \"{niche_label}\" --trend-source x_trending`."
            ),
            "finance_tag": is_finance_adjacent(primary.get("name", "")),
        })

    bridges.append({
        "text": (
            f"Queue tomorrow's brief on the dominant signal via "
            f"`daily-briefing-agent --focus-areas \"{niche_label}\"` -- thread the analytics signal directly into the morning brief."
        ),
        "finance_tag": False,
    })

    # Optional finance-adjacent monetization recommendation
    if bucket == "finance":
        bridges.append({
            "text": (
                "Investigate the strongest monetization-adjacent post via `research-assistant --query "
                "\"creator payout strategy\"` -- the cited evidence sharpens any tax-export thread you ship next."
            ),
            "finance_tag": True,
        })

    rng.shuffle(bridges[1:])  # keep #1 (top-performer expansion) anchored
    return bridges[:5]


def _build_benchmark_table(rows: List[Dict[str, Any]], bucket: str) -> Tuple[List[Dict[str, Any]], str]:
    bundle = _bundle_for_bucket(bucket)
    benchmark = bundle.get("benchmark", {})
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("current") is None:
            continue
        bench_val = benchmark.get(r["metric"])
        if bench_val is None:
            continue
        ratio = r["current"] / bench_val if bench_val else 0
        if ratio < 0.85:
            gap = "well below"
        elif ratio < 0.95:
            gap = "below"
        elif ratio <= 1.05:
            gap = "at"
        elif ratio <= 1.15:
            gap = "above"
        else:
            gap = "well above"
        out.append({
            "metric": r["metric"],
            "you": r["current"],
            "benchmark": bench_val,
            "gap": gap,
        })
    return out, benchmark.get("source", "")


def _confidence_label(rows: List[Dict[str, Any]], top_posts: List[Dict[str, Any]], compare_to: str) -> Tuple[str, str]:
    n_metrics = sum(1 for r in rows if r.get("current") is not None)
    n_with_prev = sum(1 for r in rows if r.get("prev") not in (None, 0))
    n_posts = len(top_posts)
    if n_metrics == 4 and n_with_prev == 4 and n_posts >= 3 and compare_to != "none":
        label = "high"
    elif n_metrics >= 3 and n_with_prev >= 2 and n_posts >= 2:
        label = "medium-high"
    elif n_metrics >= 2:
        label = "medium"
    else:
        label = "low"
    reason = (
        f"{n_metrics}/4 standard metrics present; {n_with_prev} with comparison baseline; "
        f"{n_posts} top posts cited; compare_to={compare_to}."
    )
    return label, reason


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_analytics_summary(
    x_handle: str,
    metrics: Optional[List[Dict[str, Any]]] = None,
    top_posts: Optional[List[Dict[str, Any]]] = None,
    metric_focus: str = "all",
    time_range: str = "30d",
    compare_to: str = "previous_period",
    niche: Optional[str] = None,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured analytics summary dict.

    Output schema:
      {
        "x_handle", "today", "metric_focus", "time_range", "compare_to",
        "niche_bucket", "niche_label",
        "metric_rows" (4 official, possibly with placeholders),
        "trends" (3-5), "top_posts" (3 max),
        "recommendations" (3-5), "confidence_label", "confidence_reason",
        "benchmark_rows": [...] | None, "benchmark_source": str | None,
        "refused": bool, "warning": str | None,
      }
    """
    if metric_focus not in ("impressions", "engagement", "reach", "all"):
        raise ValueError(f"metric_focus must be impressions|engagement|reach|all, got {metric_focus!r}")
    if time_range not in ("7d", "30d", "90d"):
        raise ValueError(f"time_range must be 7d|30d|90d, got {time_range!r}")
    if compare_to not in ("previous_period", "benchmark", "none"):
        raise ValueError(f"compare_to must be previous_period|benchmark|none, got {compare_to!r}")

    today = today or _dt.date.today()
    metrics_blob = json.dumps(metrics or [], sort_keys=True)
    rng = random.Random(deterministic_seed(x_handle, metrics_blob, today))

    bucket = detect_bucket(niche or "")
    niche_label = niche or _bundle_for_bucket(bucket).get("default_niche", "X creator")

    enriched = _enriched_metric_rows(metrics or [], compare_to)
    standard = _ordered_standard_rows(enriched)

    if _detect_garbage_batch(standard):
        return {
            "refused": True,
            "warning": (
                ">70% of input metric rows are empty or zero-valued. Re-export "
                "from X analytics with non-empty rows, or pass --demo to try "
                "the offline pipeline."
            ),
            "x_handle": x_handle, "today": today.isoformat(),
            "metric_focus": metric_focus, "time_range": time_range,
            "compare_to": compare_to,
            "niche_bucket": bucket, "niche_label": niche_label,
            "metric_rows": standard, "trends": [],
            "top_posts": top_posts or [], "recommendations": [],
            "confidence_label": "low",
            "confidence_reason": "garbage batch detected",
            "benchmark_rows": None, "benchmark_source": None,
        }

    trends = _build_trends(standard)
    top_3 = _pick_top_3(top_posts or [])
    recommendations = _build_recommendations(
        rows=official, trends=trends, top_posts=top_3,
        niche_label=niche_label, bucket=bucket, rng=rng,
    )
    conf_label, conf_reason = _confidence_label(official, top_3, compare_to)

    benchmark_rows: Optional[List[Dict[str, Any]]] = None
    benchmark_source: Optional[str] = None
    if compare_to == "benchmark":
        benchmark_rows, benchmark_source = _build_benchmark_table(official, bucket)

    # Headline
    primary = next((t for t in trends if t.get("direction") == "up"), trends[0] if trends else None)
    if primary and top_3:
        headline = (
            f"{time_range} {primary['name']} ({primary['magnitude']}); "
            f"top winner: {top_3[0]['handle']} "
            f"({top_3[0].get('format', 'post')}) -- queue more via content-idea-generator."
        )
    elif primary:
        headline = (
            f"{time_range} {primary['name']} ({primary['magnitude']}, "
            f"{primary['delta_quote']}); ship a thread to compound the signal."
        )
    else:
        headline = f"{time_range} signals are stable -- evergreen mode; ship a thread to break the plateau."

    return {
        "refused": False,
        "warning": None,
        "x_handle": x_handle,
        "today": today.isoformat(),
        "metric_focus": metric_focus,
        "time_range": time_range,
        "compare_to": compare_to,
        "niche_bucket": bucket,
        "niche_label": niche_label,
        "metric_rows": standard,
        "trends": trends,
        "top_posts": top_3,
        "recommendations": recommendations,
        "headline": headline,
        "confidence_label": conf_label,
        "confidence_reason": conf_reason,
        "benchmark_rows": benchmark_rows,
        "benchmark_source": benchmark_source,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_analytics_summary


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fmt_value(v: Any) -> str:
    if v is None:
        return "--"
    if isinstance(v, float):
        return _fmt_number(v)
    if isinstance(v, int):
        return _fmt_number(v) if v >= 1000 else f"{v}"
    return str(v)


def render_report(result: Dict[str, Any]) -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )
    meta = textwrap.dedent(f"""\
        # Analytics Summary -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Niche bucket:** {result['niche_bucket']}
        - **Niche label:** {result['niche_label']}
        - **Time range:** {result['time_range']}
        - **Metric focus:** {result['metric_focus']}
        - **Compare to:** {result['compare_to']}

        > {TAGLINE}

        """)

    if result["refused"]:
        body = textwrap.dedent(f"""\
            ## Refusal

            {result['warning']}

            Confidence: {result['confidence_label']} -- {result['confidence_reason']}.
            """)
        return license_block + meta + body

    out: List[str] = ["## Headline", "", result["headline"], ""]

    out.append("## Key Metrics")
    out.append("")
    out.append(f"| metric | current | vs {result['compare_to']} | delta | direction |")
    out.append("| ------ | ------- | -------------------------- | ----- | --------- |")
    for r in result["metric_rows"]:
        cur = _fmt_value(r["current"])
        prev = _fmt_value(r["prev"])
        out.append(f"| {r['metric']} | {cur} | {prev} | {r['delta_quote']} | {r['direction']} |")
    out.append("")

    out.append("## Trends")
    out.append("")
    if result["trends"]:
        for i, t in enumerate(result["trends"], start=1):
            out.append(
                f"{i}. **{t['name']}** -- direction: {t['direction']}; "
                f"magnitude: {t['magnitude']}; delta: {t['delta_quote']}."
            )
            out.append(f"   - {t['plain_english']}")
    else:
        out.append("- No trend movements surfaced.")
    out.append("")

    out.append("## Top Performing Content")
    out.append("")
    if result["top_posts"]:
        for i, p in enumerate(result["top_posts"], start=1):
            metric_name = p.get("headline_metric_name", "engagements")
            metric_value = p.get("headline_metric_value", "--")
            out.append(
                f"{i}. **{p['handle']}** ({p.get('format', 'unknown')}) -- "
                f"headline metric: {metric_name}={metric_value}; "
                f"why this won: {p.get('why', '(grounded in input)')}."
            )
    else:
        out.append("- No post-level breakdown supplied; rerun with top_posts in input.")
    out.append("")

    out.append("## Recommendations")
    out.append("")
    for rec in result["recommendations"]:
        out.append(f"- {rec['text']}")
        if rec.get("finance_tag"):
            out.append("  Context only -- not financial advice.")
    out.append("")

    out.append("## Confidence")
    out.append("")
    out.append(f"{result['confidence_label']} -- {result['confidence_reason']}")
    out.append("")

    if result.get("benchmark_rows") is not None:
        out.append("## Benchmark Comparison")
        out.append("")
        out.append("| metric | you | benchmark | gap |")
        out.append("| ------ | --- | --------- | --- |")
        for b in result["benchmark_rows"]:
            out.append(f"| {b['metric']} | {_fmt_value(b['you'])} | {_fmt_value(b['benchmark'])} | {b['gap']} |")
        if result.get("benchmark_source"):
            out.append("")
            out.append(f"benchmark source: {result['benchmark_source']}")
        out.append("")

    return license_block + meta + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="analytics-summarizer",
        description=(
            f"Analytics Summarizer v{VERSION} -- your X numbers briefed in 60 seconds. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --demo ai
              python run.py --x-handle @creator --metrics-file metrics.json --compare-to previous_period
              python run.py --x-handle @me --metrics impressions,engagement,reach,follower_delta --date-range 2026-04-05:2026-05-05 --demo ai
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument(
        "--metrics", default=None,
        help="Either inline JSON list of metric records OR a comma-separated metric-name list (impressions,engagement,reach,follower_delta).",
    )
    parser.add_argument(
        "--metrics-file", default=None,
        help="Path to a JSON file with {metrics, top_posts} or just a metrics list.",
    )
    parser.add_argument(
        "--date-range", default=None,
        help="ISO range like '2026-04-05:2026-05-05' (v1: falls back to bucket bundle if no other input).",
    )
    parser.add_argument(
        "--demo", choices=sorted(DEMO_METRIC_BUNDLES.keys()), default=None,
        help="Use a prefab niche metric bundle.",
    )
    parser.add_argument(
        "--metric-focus", choices=("impressions", "engagement", "reach", "all"), default="all",
        help="Metric category to weight in the summary (default all).",
    )
    parser.add_argument(
        "--time-range", choices=("7d", "30d", "90d"), default="30d",
        help="Look-back window label (default 30d).",
    )
    parser.add_argument(
        "--compare-to", choices=("previous_period", "benchmark", "none"), default="previous_period",
        help="What to compare current numbers against (default previous_period).",
    )
    parser.add_argument("--niche", default=None, help="Optional niche hint (e.g. 'AI agents on X').")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument("--version", action="version", version=f"analytics-summarizer {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    if args.date:
        try:
            today = _dt.date.fromisoformat(args.date)
        except ValueError:
            sys.stderr.write(f"X  Invalid --date {args.date!r}; expected YYYY-MM-DD\n")
            return 64
    else:
        today = _dt.date.today()

    bucket = detect_bucket(
        (args.niche or "") + " " + (args.demo or "") + " " + (args.x_handle or "")
    )
    if bucket == DEFAULT_BUCKET and args.demo:
        bucket = args.demo

    try:
        records, top_posts, source_label = parse_metrics_input(args, bucket)
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
        sys.stderr.write(f"X  failed to load metrics: {e}\n")
        return 64

    try:
        result = generate_analytics_summary(
            x_handle=args.x_handle,
            metrics=records,
            top_posts=top_posts,
            metric_focus=args.metric_focus,
            time_range=args.time_range,
            compare_to=args.compare_to,
            niche=args.niche,
            today=today,
        )
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 64

    report = render_report(result)

    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        n_metrics = sum(1 for r in result["metric_rows"] if r.get("current") is not None)
        verb = "Refused" if result["refused"] else f"Wrote summary ({n_metrics}/4 metrics, source={source_label})"
        sys.stdout.write(f"\nOK {verb} -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
