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
Mention Summarizer -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships embedded niche-aware demo
mention batches plus a deterministic theme/sentiment/priority pipeline so
creators get value the instant `grok install this` finishes. To wire to live
Grok 4.3, replace the body of `generate_mention_summary()` with a Grok call
that consumes `prompts/system.md` (auto-loaded) and returns the same schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --demo ai
    python run.py --x-handle @creator --mentions-file mentions.json --suggest-replies
    python run.py --x-handle @me --mentions '[{"author":"@a","text":"Great work"}]'
    python run.py --x-handle @me --date-range 2026-05-01..2026-05-04   # uses local cache
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
TAGLINE = "Built to help xAI and Grok win."

BANNER = (
    "============================================================\n"
    f"  MENTION SUMMARIZER  v{VERSION}\n"
    "  Triage your X mentions in 30 seconds.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Static analyzers (mirrors the keyword sets used by sibling templates).
# ---------------------------------------------------------------------------

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual", "review")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2")),
]
DEFAULT_BUCKET = "general"

POSITIVE_KEYWORDS = (
    "love", "great", "amazing", "thanks", "thank", "shipped", "ship",
    "+1", "fantastic", "game changer", "bookmark", "bookmarking", "saved",
    "best", "incredible", "useful", "helpful", "genuinely", "saved my",
    "biggest unlock", "keep going",
)
NEGATIVE_KEYWORDS = (
    "hate", "broken", "slow", "lag", "wrong", "disappoint", "fail", "sucks",
    "crashed", "crash", "bug", "issue", "missing", "lagging", "lacking",
    "loses", "losing track",
)
SPAM_KEYWORDS = (
    "send dm for", "send me a dm", "click my bio", "follow back",
    "free crypto", "free airdrop", "rt to win", "comment yes for",
    "comment 'yes'", "report this", "rugpull", "rug pull", "doxx",
    "swatted", "this person is a",
)
FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading", "earnings",
    "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
)

THEME_KEYWORDS_BY_BUCKET: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {
    "ai": [
        ("Grok agents and models", ("grok", "agent", "agents", "model")),
        ("RAG and tool-calling", ("rag", "tool", "calling", "retrieval", "tool-calling")),
        ("Evals and monitoring", ("eval", "evals", "test", "monitoring", "log", "memory")),
        ("Docs and community", ("docs", "documentation", "thread", "community", "lagging")),
        ("Long-context and prompts", ("prompt", "caching", "context", "long-context", "summarization", "structured")),
    ],
    "productivity": [
        ("Focus systems", ("focus", "single-tab", "deep-work", "deep", "concentration", "block", "blocks")),
        ("Calendar and time", ("calendar", "tetris", "time", "schedule", "meetings", "stack")),
        ("Rituals and cadence", ("ritual", "rituals", "weekly", "review", "cadence", "friday", "fridays")),
        ("Automation and glue", ("automation", "powershell", "shortcut", "script", "bundle")),
        ("Energy and habits", ("energy", "habit", "habits", "morning", "sleep", "track")),
    ],
    "finance": [
        ("Earnings and payouts", ("earning", "earnings", "payout", "payment")),
        ("Tax and reporting", ("tax", "taxes", "reporting")),
        ("Cashtag and tokens", ("cashtag", "token", "$")),
        ("Tools and dashboards", ("dashboard", "chart", "graph", "tool")),
        ("Strategy and forecasts", ("forecast", "model", "strategy", "plan")),
    ],
    "creator": [
        ("Audience and growth", ("audience", "growth", "follow", "follower", "followers")),
        ("Threads and content", ("thread", "threads", "content", "post", "tweet")),
        ("Newsletter and funnel", ("newsletter", "funnel", "list")),
        ("Monetization", ("monetize", "revenue", "sponsor", "deal")),
    ],
    "fitness": [
        ("Training systems", ("zone", "lifting", "training", "vo2")),
        ("Nutrition and recovery", ("protein", "nutrition", "sleep")),
    ],
    "general": [
        ("Questions and asks", ("?", "question", "ask", "curious")),
        ("Praise and shoutouts", ("love", "great", "thanks", "amazing")),
        ("Critiques and concerns", ("broken", "wrong", "slow", "bug")),
    ],
}

ACTION_VERBS = (
    "reply now",
    "reply within 24h",
    "mute",
    "block",
    "ignore",
    "flag for follow-up",
)

# Embedded demo batches (used by --demo {bucket}). Each batch is 12 mentions
# with deliberately varied sentiment / priority / spam ratio.
DEMO_BATCHES: Dict[str, List[Dict[str, str]]] = {
    "ai": [
        {"author": "@dev_kai", "text": "Just shipped my first Grok agent after reading your thread. Game changer."},
        {"author": "@ml_curious", "text": "Your take on RAG pipelines clicked for me -- thanks for putting it out there."},
        {"author": "@solo_builder", "text": "Question on tool-calling agents: how do you handle the eval loop?"},
        {"author": "@team_lead", "text": "Curious how you'd approach long-context summarization for a smaller team."},
        {"author": "@docs_fan", "text": "Love your Grok 4.3 content but the docs are lagging the releases."},
        {"author": "@bug_hunter", "text": "Your prompt caching demo crashed on Windows 11. Anyone else?"},
        {"author": "@spammer42", "text": "Send DM for free crypto trading signals!"},
        {"author": "@thread_saver", "text": "Bookmarking your MCP servers thread for the team."},
        {"author": "@shipper99", "text": "Anyone using Grok agents in production? Looking for war stories."},
        {"author": "@v1_planner", "text": "How does structured outputs compare to fine-tuning for v1 builds?"},
        {"author": "@speed_fan", "text": "You're shipping faster than anyone else in this space -- keep going."},
        {"author": "@eval_curious", "text": "Quick agent memory question: what's your eval set size?"},
    ],
    "productivity": [
        {"author": "@focus_kai", "text": "Tried single-tab focus this week. Workflow feels weirdly different."},
        {"author": "@solo_writer", "text": "Your weekly review ritual changed how I think about Fridays. Game changer."},
        {"author": "@calendar_user", "text": "Question on calendar tetris: how do you handle deep-work blocks vs meetings?"},
        {"author": "@morning_person", "text": "Your 3-task-day post is the best productivity advice I've read this year."},
        {"author": "@energy_track", "text": "Love the energy-vs-time framing but I keep losing track by Wednesday."},
        {"author": "@scripter", "text": "Is there a PowerShell shortcut bundle you'd recommend for weekly review automation?"},
        {"author": "@spambot99", "text": "RT to win -- comment YES for a free productivity bundle!"},
        {"author": "@thread_saver_p", "text": "Bookmarking your single-tab focus thread -- sharing with my team."},
        {"author": "@review_doer", "text": "Started doing Friday reviews -- biggest unlock in months."},
        {"author": "@doubt_curious", "text": "The 3-task day sounds great but breaks down when meetings stack. Tips?"},
        {"author": "@deep_work_fan", "text": "How do you protect deep-work blocks from Slack/X interruptions?"},
        {"author": "@grateful_solo", "text": "Your rituals saved my week. Genuinely. Thanks."},
    ],
    "finance": [
        {"author": "@payout_curious", "text": "How do you forecast earnings when X Money is volatile week-to-week?"},
        {"author": "@tax_anxious", "text": "Tax export from your tool saved me a weekend. Thank you."},
        {"author": "@cashtag_q", "text": "Curious how you'd model $XYZ flows with the Companion Dashboard."},
        {"author": "@spamtoken", "text": "Send DM for free crypto trading signals!"},
        {"author": "@dashboard_fan", "text": "The Streamlit dashboard layout is the cleanest finance UI I've seen on X."},
        {"author": "@p_and_l", "text": "P&L view crashed when I imported 200+ rows. Sample CSV in DMs if useful."},
        {"author": "@strategy_curious", "text": "Question on creator-payout strategy: how do you split cohorts in the optimizer?"},
        {"author": "@thread_keeper_f", "text": "Bookmarking your X Money thread for the finance club."},
        {"author": "@compliance_q", "text": "Love the disclaimers but is there a 1099-style report planned?"},
        {"author": "@speed_finance", "text": "You're shipping finance tools faster than most fintech orgs -- amazing."},
        {"author": "@volatility_q", "text": "How does the model handle volatility tails in earnings forecasts?"},
        {"author": "@grateful_creator", "text": "Tax estimator changed how I plan quarters. Genuinely useful."},
    ],
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


def sentiment_of(text: str) -> str:
    t = text.lower()
    has_pos = any(k in t for k in POSITIVE_KEYWORDS)
    has_neg = any(k in t for k in NEGATIVE_KEYWORDS)
    if has_pos and has_neg:
        return "mixed"
    if has_pos:
        return "positive"
    if has_neg:
        return "negative"
    return "neutral"


def is_spam(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in SPAM_KEYWORDS)


def is_finance_adjacent(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in FINANCE_KEYWORDS)


def deterministic_seed(x_handle: str, mentions: List[Dict[str, str]], today: _dt.date) -> int:
    blob = x_handle + "|" + today.isoformat() + "|" + json.dumps(
        [{"a": m.get("author", ""), "t": m.get("text", "")} for m in mentions],
        sort_keys=True, ensure_ascii=False,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def load_system_prompt() -> str:
    """Load prompts/system.md so future Grok wiring is a one-line entrypoint."""
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Mention loading
# ---------------------------------------------------------------------------

def _coerce_mentions(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        raise ValueError("mentions input must be a JSON list of objects")
    out: List[Dict[str, str]] = []
    for i, m in enumerate(raw):
        if not isinstance(m, dict):
            raise ValueError(f"mentions[{i}] must be a JSON object")
        author = str(m.get("author", "")).strip() or f"@user_{i + 1}"
        text = str(m.get("text", "")).strip()
        if not text:
            raise ValueError(f"mentions[{i}] is missing 'text'")
        ts = str(m.get("timestamp", "")).strip() or None
        out.append({"author": author, "text": text, **({"timestamp": ts} if ts else {})})
    return out


def load_mentions_inline(s: str) -> List[Dict[str, str]]:
    return _coerce_mentions(json.loads(s))


def load_mentions_file(path: str) -> List[Dict[str, str]]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"mentions file not found: {path}")
    return _coerce_mentions(json.loads(p.read_text(encoding="utf-8")))


def load_demo_mentions(bucket: str) -> List[Dict[str, str]]:
    if bucket not in DEMO_BATCHES:
        raise ValueError(
            f"--demo bucket must be one of {sorted(DEMO_BATCHES)}, got {bucket!r}"
        )
    return [dict(m) for m in DEMO_BATCHES[bucket]]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def compute_spam_ratio(mentions: List[Dict[str, str]]) -> float:
    if not mentions:
        return 0.0
    spam = sum(1 for m in mentions if is_spam(m["text"]))
    return spam / len(mentions)


def extract_themes(
    mentions: List[Dict[str, str]],
    bucket: str,
    max_themes: int = 5,
) -> List[Dict[str, Any]]:
    groups = THEME_KEYWORDS_BY_BUCKET.get(bucket, THEME_KEYWORDS_BY_BUCKET["general"])
    found: List[Dict[str, Any]] = []
    for name, keys in groups:
        matched: List[Tuple[Dict[str, str], int]] = []  # (mention, keyword_match_count)
        for m in mentions:
            if is_spam(m["text"]):
                continue
            text_l = m["text"].lower()
            hits = sum(1 for k in keys if k in text_l)
            if hits:
                matched.append((m, hits))
        if matched:
            mention_objs = [m for m, _ in matched]
            theme_sent = _aggregate_sentiment([sentiment_of(m["text"]) for m in mention_objs])
            # Pick rep quote: prefer the mention with the most theme-keyword
            # hits AND a sentiment matching the theme's aggregate; fall back to
            # most-hits, then first.
            aligned = [
                (m, h) for m, h in matched if sentiment_of(m["text"]) == theme_sent
            ] or matched
            aligned.sort(key=lambda mh: (-mh[1], len(mh[0]["text"])))
            rep = aligned[0][0]["text"]
            found.append({
                "name": name,
                "count": len(matched),
                "sentiment": theme_sent,
                "representative_quote": rep,
            })
    # Sort by count desc, then keep top max_themes (min 1)
    found.sort(key=lambda t: (-t["count"], t["name"]))
    return found[:max_themes]


def _aggregate_sentiment(labels: List[str]) -> str:
    if not labels:
        return "neutral"
    if "mixed" in labels:
        return "mixed"
    pos = labels.count("positive")
    neg = labels.count("negative")
    if pos and neg:
        return "mixed"
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def compute_sentiment_mix(mentions: List[Dict[str, str]]) -> Dict[str, int]:
    mix = {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}
    for m in mentions:
        if is_spam(m["text"]):
            # Spam mentions don't count toward sentiment mix per system prompt.
            continue
        mix[sentiment_of(m["text"])] += 1
    return mix


def _priority_score(text: str, sentiment: str) -> Tuple[int, str, str]:
    """Return (numeric_score, priority_label, suggested_action)."""
    if is_spam(text):
        return 1, "low", "block"
    has_question = "?" in text
    if sentiment == "negative" and has_question:
        # Bug reports / actionable critiques outrank generic questions.
        return 10, "high", "reply now"
    if sentiment == "mixed":
        return 8, "medium-high", "flag for follow-up"
    if sentiment == "negative":
        return 7, "medium-high", "reply now"
    if has_question and sentiment in ("neutral", "positive"):
        return 9, "medium-high", "reply within 24h"
    if sentiment == "positive":
        return 5, "medium", "ignore"
    return 4, "medium", "flag for follow-up"


_PRIORITY_RANK = {"high": 4, "medium-high": 3, "medium": 2, "low": 1}


def _topic_snippet(text: str, max_words: int = 4) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", text.lower())
    skip = {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "is", "are", "was", "were", "be", "this", "that",
        "you", "your", "i", "my", "we", "they", "do", "does", "did", "any",
        "what", "when", "where", "why", "how", "who", "out", "into", "about",
        "than", "then", "so", "all", "no", "not", "yes", "thanks", "great",
        "love", "just", "really", "very", "much", "more", "some", "first",
        "anyone", "else",
    }
    keep = [w for w in words if w not in skip and len(w) > 2]
    return " ".join(keep[:max_words]) if keep else "this"


def pick_priorities(
    mentions: List[Dict[str, str]],
    max_picks: int = 3,
) -> List[Dict[str, Any]]:
    # Dedup by author -- aggregate text + bump priority by 1 level.
    by_author: Dict[str, List[Dict[str, str]]] = {}
    for m in mentions:
        by_author.setdefault(m["author"], []).append(m)

    scored: List[Dict[str, Any]] = []
    for author, items in by_author.items():
        merged_text = " ".join(it["text"] for it in items)
        sent = _aggregate_sentiment([sentiment_of(it["text"]) for it in items])
        score, label, action = _priority_score(items[0]["text"], sent)
        cumulative_bump = 0
        if len(items) > 1:
            cumulative_bump = 2
            label = _bump_priority(label)
        finance = is_finance_adjacent(merged_text)
        snippet = _topic_snippet(merged_text)
        cum_phrase = (
            f" ({len(items)} cumulative mentions)" if len(items) > 1 else ""
        )
        if is_spam(merged_text):
            reason = f"clear DM-bait/scam pattern around '{snippet}'{cum_phrase}."
        elif sent == "negative" and "?" in merged_text:
            reason = f"actionable bug/critique on '{snippet}'; same-day reply prevents churn{cum_phrase}."
        elif sent == "mixed":
            reason = f"mixed signal on '{snippet}' -- praise plus a concrete concern in the same mention{cum_phrase}."
        elif "?" in merged_text and sent != "negative":
            reason = f"thoughtful question on '{snippet}'; high-engagement reply pattern{cum_phrase}."
        elif sent == "negative":
            reason = f"actionable negative feedback on '{snippet}' worth a same-day reply{cum_phrase}."
        else:
            reason = f"warm advocate signal on '{snippet}'{cum_phrase}."
        scored.append({
            "author": author,
            "priority": label,
            "score": score + cumulative_bump,
            "reason": reason,
            "action": action,
            "finance_tag": finance and not is_spam(merged_text),
            "merged_text": merged_text,
        })

    scored.sort(key=lambda d: (-d["score"], d["author"]))
    picked = scored[:max_picks]

    # Spread rule: if all picks share the same priority label, downgrade the
    # one with the lowest score (deterministic tiebreak: alphabetical author).
    labels = {p["priority"] for p in picked}
    if len(picked) >= 2 and len(labels) == 1:
        weakest = min(picked, key=lambda d: (d["score"], d["author"]))
        # If all scores tie (common with question-only batches), downgrade the
        # last-by-author to avoid picking the first-listed entry.
        if all(p["score"] == weakest["score"] for p in picked):
            weakest = max(picked, key=lambda d: d["author"])
        weakest["priority"] = _downgrade_priority(weakest["priority"])

    # Re-sort by priority rank descending so the displayed order matches the
    # final labels (highest priority first).
    picked.sort(key=lambda d: (-_PRIORITY_RANK.get(d["priority"], 0), -d["score"], d["author"]))
    return picked


def _bump_priority(label: str) -> str:
    order = ["low", "medium", "medium-high", "high"]
    if label in order:
        idx = order.index(label)
        return order[min(idx + 1, len(order) - 1)]
    return label


def _downgrade_priority(label: str) -> str:
    order = ["low", "medium", "medium-high", "high"]
    if label in order:
        idx = order.index(label)
        return order[max(idx - 1, 0)]
    return label


def generate_action_items(
    themes: List[Dict[str, Any]],
    priorities: List[Dict[str, Any]],
    niche: Optional[str],
    bucket: str,
    sentiment_mix: Dict[str, int],
) -> List[str]:
    items: List[str] = []
    # 1. Reply / block / mute the priority list
    for p in priorities:
        if p["action"] == "block":
            items.append(f"Block {p['author']} -- {p['reason'].rstrip('.')}.")
        elif p["action"] == "reply now":
            items.append(f"Reply to {p['author']} today -- {p['reason'].rstrip('.')}.")
        elif p["action"] == "reply within 24h":
            items.append(f"Reply to {p['author']} within 24h -- {p['reason'].rstrip('.')}.")
        elif p["action"] == "flag for follow-up":
            items.append(f"Flag {p['author']} for follow-up -- {p['reason'].rstrip('.')}.")
    # 2. Theme-driven action when a 'mixed' or 'negative' theme is present
    for t in themes:
        if t["sentiment"] == "mixed" and t["count"] >= 1:
            items.append(
                f"Address the '{t['name']}' theme directly "
                f"(e.g. a status thread or a dedicated reply chain)."
            )
            break
    # 3. Sentiment-led action
    total = sum(sentiment_mix.values())
    if total and sentiment_mix.get("positive", 0) / total >= 0.5:
        items.append(
            "Bookmark the warmest 3 mentions for a milestone post or testimonial reel."
        )
    # 4. Niche-aware suggestion
    bucket_action = {
        "ai": "Schedule a Grok 4.3 deep-dive thread by Friday to compound the agent-niche signal.",
        "productivity": "Ship a 'one-tab focus playbook' thread this week -- demand is clearly there.",
        "finance": "Add an 'export status' note to the Companion Dashboard README; tax-export feedback is warm.",
        "creator": "Start a weekly recap thread; mentions show audience hunger for cadence.",
        "fitness": "Pin a Zone-2 starter resource; multiple mentions ask for entry points.",
        "general": "Pin the highest-quality reply as a sticky for new followers visiting your profile.",
    }.get(bucket)
    if bucket_action:
        items.append(bucket_action)
    # Cap 3-5 items, keep at least 3 if we have them
    if len(items) > 5:
        items = items[:5]
    return items


def pick_reply_suggestions(
    priorities: List[Dict[str, Any]],
    niche: Optional[str],
    max_picks: int = 3,
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for p in priorities:
        if p["action"] in ("block", "mute", "ignore"):
            continue
        snippet = _topic_snippet(p["merged_text"], max_words=3)
        if "bug" in p["reason"] or "critique" in p["reason"]:
            why = f"actionable bug report on '{snippet}'; same-day reply prevents churn"
            draft = f"Confirming on my end -- '{snippet}' lands as a fix this week. Will tag you when patched."
        elif "?" in p["merged_text"]:
            why = f"thoughtful question on '{snippet}'; expert-signal reply lands well"
            draft = f"Quick take on '{snippet}': ship smallest version first, evaluate in week two. Eval template inbound."
        elif "mixed" in p["reason"]:
            why = f"mixed signal on '{snippet}'; replying defuses the negative half publicly"
            draft = f"Fair point on '{snippet}' -- docs pass queued this week. Will tag you when it lands."
        else:
            why = f"warm advocate signal on '{snippet}'; reply compounds goodwill"
            draft = f"Genuinely appreciate this -- '{snippet}' feedback keeps the cadence honest."
        # Cap draft to 140 chars per system prompt
        if len(draft) > 140:
            draft = draft[:140].rstrip().rstrip(",;:") + "."
        out.append({
            "author": p["author"],
            "why_high_leverage": why,
            "draft": draft,
        })
        if len(out) >= max_picks:
            break
    return out


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_mention_summary(
    x_handle: str,
    mentions: Optional[List[Dict[str, str]]] = None,
    date_range: Optional[str] = None,
    max_mentions: int = 50,
    niche: Optional[str] = None,
    suggest_replies: bool = False,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured summary dict for (x_handle, mentions[, today]).

    Output schema:
        {
          "refused": bool,
          "warning": str | None,
          "headline": str,
          "themes": [{"name", "count", "sentiment", "representative_quote"}, ...],
          "sentiment_mix": {"positive": N, "neutral": N, "negative": N, "mixed": N},
          "priorities": [{"author", "priority", "reason", "action", "finance_tag"}, ...],
          "action_items": [str, ...],
          "reply_suggestions": [{"author", "why_high_leverage", "draft"}, ...],
          "covered": int,    # count actually summarized (excludes spam)
          "total_input": int,
          "spam_excluded": int,
          "niche_bucket": str,
          "date_range": str | None,
        }
    """
    if max_mentions < 1 or max_mentions > 200:
        raise ValueError(f"max_mentions must be 1..200, got {max_mentions}")
    today = today or _dt.date.today()

    if mentions is None and not date_range:
        raise ValueError("must supply either mentions= or date_range=")
    if mentions is not None and date_range:
        raise ValueError("mentions= and date_range= are mutually exclusive")

    if mentions is None:
        # Local cache lookup is a v2 feature; for v1 we surface a clear refusal.
        return {
            "refused": True,
            "warning": (
                f"--date-range requested ({date_range}) but no local mention "
                f"cache exists. Pass --mentions, --mentions-file, or --demo "
                f"{{ai|productivity|finance}} instead."
            ),
            "headline": "",
            "themes": [],
            "sentiment_mix": {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0},
            "priorities": [],
            "action_items": [],
            "reply_suggestions": [],
            "covered": 0,
            "total_input": 0,
            "spam_excluded": 0,
            "niche_bucket": detect_bucket(niche or ""),
            "date_range": date_range,
        }

    capped = mentions[:max_mentions]
    spam_ratio = compute_spam_ratio(capped)

    if spam_ratio > 0.7:
        return {
            "refused": True,
            "warning": (
                f"{int(spam_ratio * 100)}% of the input batch matches spam / "
                f"DM-bait / RT-to-win patterns. Refusing to summarize per "
                f"Constitution rule #5; recommend muting/blocking the senders."
            ),
            "headline": "",
            "themes": [],
            "sentiment_mix": {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0},
            "priorities": [],
            "action_items": [],
            "reply_suggestions": [],
            "covered": 0,
            "total_input": len(capped),
            "spam_excluded": sum(1 for m in capped if is_spam(m["text"])),
            "niche_bucket": detect_bucket(niche or ""),
            "date_range": None,
        }

    bucket = detect_bucket(
        " ".join([niche or ""] + [m["text"] for m in capped])
    )
    spam_count = sum(1 for m in capped if is_spam(m["text"]))
    non_spam = [m for m in capped if not is_spam(m["text"])]

    themes = extract_themes(non_spam, bucket, max_themes=5)
    sentiment_mix = compute_sentiment_mix(capped)
    priorities = pick_priorities(capped, max_picks=3)
    action_items = generate_action_items(themes, priorities, niche, bucket, sentiment_mix)
    replies = pick_reply_suggestions(priorities, niche) if suggest_replies else []

    pos = sentiment_mix.get("positive", 0)
    neu = sentiment_mix.get("neutral", 0)
    neg = sentiment_mix.get("negative", 0)
    mixed_n = sentiment_mix.get("mixed", 0)
    mood = "mostly positive" if pos and pos >= neu and pos >= neg else (
        "mostly neutral" if neu >= pos and neu >= neg else "mixed"
    )
    spam_phrase = f"; {spam_count} spam mute/block recommended" if spam_count else ""
    headline = (
        f"{len(capped)} mentions, {mood} around {themes[0]['name']}"
        if themes else f"{len(capped)} mentions"
    ) + spam_phrase + "."

    return {
        "refused": False,
        "warning": None,
        "headline": headline,
        "themes": themes,
        "sentiment_mix": sentiment_mix,
        "priorities": priorities,
        "action_items": action_items,
        "reply_suggestions": replies,
        "covered": len(non_spam),
        "total_input": len(capped),
        "spam_excluded": spam_count,
        "niche_bucket": bucket,
        "date_range": None,
        "_x_handle": x_handle,
        "_today": today.isoformat(),
        "_suggest_replies": suggest_replies,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_mention_summary


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _redact_quote(text: str, max_chars: int = 110) -> str:
    """Mask plausible PII tokens before quoting."""
    redacted = re.sub(r"\b\d{3}-?\d{3}-?\d{4}\b", "[redacted-phone]", text)
    redacted = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[redacted-email]", redacted)
    if len(redacted) > max_chars:
        redacted = redacted[: max_chars - 3].rstrip() + "..."
    return redacted


def render_report(
    x_handle: str,
    result: Dict[str, Any],
    today: _dt.date,
    suggest_replies: bool,
) -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )
    meta_header = textwrap.dedent(f"""\
        # Mention Summary -- {today.isoformat()}

        - **Creator:** {x_handle}
        - **Niche bucket:** {result['niche_bucket']}
        - **Total input:** {result['total_input']}
        - **Covered (non-spam):** {result['covered']}
        - **Spam excluded:** {result['spam_excluded']}

        > {TAGLINE}

        """)

    if result["refused"]:
        body = textwrap.dedent(f"""\
            ## Refusal

            {result['warning']}

            Confidence: high -- refusal triggered before structured analysis.
            """)
        return license_block + meta_header + body

    # Headline
    out: List[str] = ["## Headline", "", result["headline"], ""]

    # Themes
    out.append("## Themes")
    out.append("")
    if result["themes"]:
        for i, t in enumerate(result["themes"], start=1):
            out.append(
                f"{i}. **{t['name']}** (count: {t['count']}, sentiment: {t['sentiment']})"
            )
            out.append(f"   - \"{_redact_quote(t['representative_quote'])}\"")
    else:
        out.append("- No clusterable themes (input batch too small or noisy).")
    out.append("")

    # Sentiment table
    mix = result["sentiment_mix"]
    out.append("## Sentiment")
    out.append("")
    out.append("| label    | mention_count |")
    out.append("| -------- | ------------- |")
    out.append(f"| positive | {mix.get('positive', 0)} |")
    out.append(f"| neutral  | {mix.get('neutral', 0)} |")
    out.append(f"| negative | {mix.get('negative', 0)} |")
    out.append(f"| mixed    | {mix.get('mixed', 0)} |")
    out.append("")

    # Top-3 Priority
    out.append("## Top-3 Priority")
    out.append("")
    if result["priorities"]:
        for i, p in enumerate(result["priorities"], start=1):
            out.append(f"{i}. **{p['author']}** -- priority: {p['priority']}")
            out.append(f"   - Reason: {p['reason']}")
            out.append(f"   - Action: {p['action']}")
            if p.get("finance_tag"):
                out.append("   Context only -- not financial advice.")
    else:
        out.append("- No priority mentions identified.")
    out.append("")

    # Action Items
    out.append("## Action Items")
    out.append("")
    if result["action_items"]:
        for item in result["action_items"]:
            out.append(f"- {item}")
    else:
        out.append("- No actionable items surfaced.")
    out.append("")

    # Reply Suggestions (optional)
    if suggest_replies and result["reply_suggestions"]:
        out.append("## Reply Suggestions")
        out.append("")
        for i, r in enumerate(result["reply_suggestions"], start=1):
            out.append(f"{i}. **{r['author']}** -- {r['why_high_leverage']}")
            out.append(f"   - Draft: \"{r['draft']}\"")
        out.append("")

    confidence = (
        f"Confidence: medium -- offline keyword pipeline; covered "
        f"{result['covered']} of {result['total_input']} mentions, "
        f"{result['spam_excluded']} spam excluded. For live grounding, wire "
        f"`prompts/system.md` to the xAI API (see README)."
    )
    out.append(confidence)
    return license_block + meta_header + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _ranged_int(lo: int, hi: int) -> Callable[[str], int]:
    def _fn(s: str) -> int:
        try:
            value = int(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"expected integer, got {s!r}") from None
        if value < lo or value > hi:
            raise argparse.ArgumentTypeError(f"must be between {lo} and {hi}, got {value}")
        return value
    return _fn


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mention-summarizer",
        description=(
            f"Mention Summarizer v{VERSION} -- triage your X mentions in 30 seconds. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --demo ai
              python run.py --x-handle @creator --mentions-file mentions.json --suggest-replies
              python run.py --x-handle @me --mentions '[{"author":"@a","text":"Great work"}]'
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--mentions",
        help="Inline JSON list of mention objects: '[{\"author\":\"@a\",\"text\":\"...\"}, ...]'",
    )
    src.add_argument(
        "--mentions-file",
        help="Path to a JSON file containing the same mention-list shape.",
    )
    src.add_argument(
        "--date-range",
        help="ISO range like '2026-05-01..2026-05-04' for local cache lookups (v2 feature; v1 returns a clear refusal).",
    )
    src.add_argument(
        "--demo", choices=sorted(DEMO_BATCHES.keys()),
        help="Use an embedded niche-aware demo batch (12 mentions). Convenience for first-run.",
    )

    parser.add_argument(
        "--max-mentions", type=_ranged_int(1, 200), default=50,
        help="Cap on mentions to ingest per run (1..200, default 50).",
    )
    parser.add_argument("--niche", default=None, help="Optional niche hint (e.g. 'AI tooling').")
    parser.add_argument("--suggest-replies", action="store_true",
                        help="Also surface 1-3 high-leverage reply suggestions.")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument("--version", action="version", version=f"mention-summarizer {VERSION}")
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

    try:
        if args.mentions:
            mentions: Optional[List[Dict[str, str]]] = load_mentions_inline(args.mentions)
            date_range: Optional[str] = None
        elif args.mentions_file:
            mentions = load_mentions_file(args.mentions_file)
            date_range = None
        elif args.demo:
            mentions = load_demo_mentions(args.demo)
            date_range = None
        else:
            mentions = None
            date_range = args.date_range
    except (json.JSONDecodeError, ValueError, FileNotFoundError) as e:
        sys.stderr.write(f"X  failed to load mentions: {e}\n")
        return 64

    try:
        result = generate_mention_summary(
            x_handle=args.x_handle,
            mentions=mentions,
            date_range=date_range,
            max_mentions=args.max_mentions,
            niche=args.niche,
            suggest_replies=args.suggest_replies,
            today=today,
        )
    except ValueError as e:
        sys.stderr.write(f"X  {e}\n")
        return 64

    report = render_report(
        x_handle=args.x_handle,
        result=result,
        today=today,
        suggest_replies=args.suggest_replies,
    )

    if args.output:
        out_path = Path(args.output)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        verb = "Refused" if result["refused"] else f"Wrote summary ({result['covered']} covered)"
        sys.stdout.write(f"\nOK {verb} -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
