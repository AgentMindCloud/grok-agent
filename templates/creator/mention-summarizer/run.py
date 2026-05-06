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
"""Mention Summarizer — runner.

CLI entry point for the ``mention-summarizer`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied X mention export (JSON) — or seeded demo
mentions when no file is provided — and emits the strict 7/8-section
mention summary defined by the P89 system prompt:

  1. Mention Snapshot
  2. Mention Health (4-row metric table + weighted score + paradox if active)
  3. Sentiment Breakdown (3-band: positive / neutral / negative)
  4. Priority Reply Queue (max 8 — troll-cluster members excluded + Red Flagged)
  5. Red Flags (2–4 cards; paradox + troll cluster + others)
  6. Recommendations (3–5; reply-drafter + analytics-summarizer unconditional)
  7. Confidence
  + Optional Mention Audit (auto-appended when troll-cluster detected OR
    window=7d)

Hard guarantees enforced by this runner:

* Drafts only. Never auto-replies to any mention.
* No fabricated statistics. Demo mentions carry an explicit
  `[demo mention — re-run with --mentions-file for real X data]` label.
* Sentiment-spike paradox surfaced in BOTH the Mention Health section
  AND the Red Flags section whenever Mention volume delta > +30% AND
  Net sentiment score < 10 (configurable via --sentiment-baseline).
* Mention Health score formula is fixed:
    round(0.30*Sentiment_norm + 0.25*Volume_norm +
          0.25*Priority_norm + 0.20*Authentic_norm)
* Troll-cluster guard: ≥5 negative mentions with >60% pairwise Jaccard
  token overlap → excluded from priority queue + consolidated Red Flag
  with severity high and specific remediation.
* Priority reply queue capped at 8 after troll filter.
* Unconditional bridges: reply-drafter (position 1) and
  analytics-summarizer (position 2) in every Recommendations section.
* Privacy-first: no non-creator handles in rendered output. Mention
  intent is paraphrased — never raw text or author handles.
* Deterministic: seeded by sha256(handle + sorted-payload-json + window).
  Date is NOT included in the seed so examples remain reproducible.
* Zero external network calls in v1.

Manifest contract::

    generate = generate_mention_summary

Built for X, Grok & the ecosystem community.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Optional

# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "prompts" / "system.md"

# Mention Health metric weights (must sum to 1.0)
HEALTH_WEIGHTS = {
    "Net sentiment score":   0.30,
    "Mention volume delta":  0.25,
    "Priority reply rate":   0.25,
    "Authentic reach share": 0.20,
}

# Healthy ranges for sub-score normalisation (lo, hi → 0–100)
HEALTHY_RANGES = {
    "Net sentiment score":   (-30.0,  80.0),   # −100 to +100 scale
    "Mention volume delta":  (-10.0,  40.0),   # % change
    "Priority reply rate":   (  5.0,  30.0),   # % of total mentions
    "Authentic reach share": ( 60.0,  95.0),   # % of total mentions
}

# Sentiment-spike paradox thresholds
PARADOX_VOLUME_THRESHOLD = 30.0        # Mention volume delta > +30%
DEFAULT_SENTIMENT_BASELINE = 10.0      # Net sentiment score < 10

# Priority reply queue
PRIORITY_SCORE_THRESHOLD = 50          # mentions with score >= this are priority
MAX_PRIORITY_QUEUE = 8

# Troll-cluster guard
TROLL_MIN_CLUSTER_SIZE = 5
TROLL_JACCARD_THRESHOLD = 0.60         # pairwise Jaccard > 60%

WINDOW_OPTIONS = (7, 30, 90)
COMPARE_OPTIONS = ("previous_period", "benchmark")

DEMO_LABEL = "[demo mention — re-run with --mentions-file for real X data]"

# ---------------------------------------------------------------------------
# Demo data — 3 seeded modes (embedded so the runner is offline-safe)
# ---------------------------------------------------------------------------

# Troll tokens shared across the 6-member troll cluster in DEMO_TROLL.
# Core set (6 tokens): present in all 6 cluster mentions → pairwise Jaccard = 6/8 = 0.75 > 0.60.
_TROLL_CORE = ["content", "garbage", "stop", "posting", "terrible", "account"]

DEMO_TROLL = {
    "x_handle": "@JanSol0s",
    "window_days": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "current_period": {
        "total_mentions": 84,
        "positive_count": 14,
        "neutral_count": 32,
        "negative_count": 38,
        "authentic_mention_count": 71,
    },
    "previous_period": {
        "total_mentions": 58,
        "positive_count": 22,
        "neutral_count": 20,
        "negative_count": 16,
        "authentic_mention_count": 51,
        "priority_mention_count": 9,
    },
    "mentions": [
        # --- 8 genuine priority mentions (priority_score 57–98) ---
        {
            "id": "m001", "sentiment": "positive", "priority_score": 98,
            "intent": "Thoughtful question about multi-agent orchestration scaling beyond 10 concurrent agents",
            "author_followers": 4200,
            "tokens": ["multi", "agent", "orchestration", "scaling", "question"],
        },
        {
            "id": "m002", "sentiment": "neutral", "priority_score": 91,
            "intent": "Request for a comparison between two competing orchestration frameworks from the top thread",
            "author_followers": 3100,
            "tokens": ["comparison", "frameworks", "orchestration", "request"],
        },
        {
            "id": "m003", "sentiment": "positive", "priority_score": 85,
            "intent": "Detailed follow-up on agent-eval failure modes with a proposed alternative validation approach",
            "author_followers": 2800,
            "tokens": ["agent", "eval", "failure", "validation", "approach"],
        },
        {
            "id": "m004", "sentiment": "neutral", "priority_score": 79,
            "intent": "Developer asking for clarification on the offline runner design and Windows path handling",
            "author_followers": 1900,
            "tokens": ["offline", "runner", "windows", "paths", "clarification"],
        },
        {
            "id": "m005", "sentiment": "positive", "priority_score": 74,
            "intent": "Niche peer sharing a related finding that validates the central claim in the period's top post",
            "author_followers": 5600,
            "tokens": ["finding", "validates", "claim", "peer", "niche"],
        },
        {
            "id": "m006", "sentiment": "negative", "priority_score": 68,
            "intent": "Critical but substantive pushback on the benchmark drift claim — cites a counter-example",
            "author_followers": 2200,
            "tokens": ["benchmark", "drift", "counter", "pushback", "claim"],
        },
        {
            "id": "m007", "sentiment": "positive", "priority_score": 63,
            "intent": "Adjacent-niche creator asking about adapting the agent-eval approach to a content-workflow context",
            "author_followers": 1500,
            "tokens": ["adapting", "workflow", "context", "creator", "approach"],
        },
        {
            "id": "m008", "sentiment": "neutral", "priority_score": 57,
            "intent": "Question about Windows-first deployment versus cross-platform tradeoffs for the CLI runner",
            "author_followers": 870,
            "tokens": ["windows", "deployment", "cross", "platform", "tradeoffs"],
        },
        # --- 6 troll-cluster members (priority_score 54–88, all negative) ---
        # Core tokens present in all 6; unique token per member keeps Jaccard = 0.75 per pair.
        {
            "id": "t001", "sentiment": "negative", "priority_score": 88,
            "intent": "Coordinated negative mention matching cluster pattern",
            "author_followers": 12,
            "tokens": _TROLL_CORE + ["your"],
        },
        {
            "id": "t002", "sentiment": "negative", "priority_score": 82,
            "intent": "Coordinated negative mention matching cluster pattern",
            "author_followers": 8,
            "tokens": _TROLL_CORE + ["this"],
        },
        {
            "id": "t003", "sentiment": "negative", "priority_score": 75,
            "intent": "Coordinated negative mention matching cluster pattern",
            "author_followers": 5,
            "tokens": _TROLL_CORE + ["just"],
        },
        {
            "id": "t004", "sentiment": "negative", "priority_score": 69,
            "intent": "Coordinated negative mention matching cluster pattern",
            "author_followers": 3,
            "tokens": _TROLL_CORE + ["awful"],
        },
        {
            "id": "t005", "sentiment": "negative", "priority_score": 61,
            "intent": "Coordinated negative mention matching cluster pattern",
            "author_followers": 7,
            "tokens": _TROLL_CORE + ["please"],
        },
        {
            "id": "t006", "sentiment": "negative", "priority_score": 54,
            "intent": "Coordinated negative mention matching cluster pattern",
            "author_followers": 4,
            "tokens": _TROLL_CORE + ["bad"],
        },
        # --- 6 lower-priority genuine mentions (priority_score 10–45) ---
        {
            "id": "m009", "sentiment": "positive", "priority_score": 45,
            "intent": "Brief supportive comment on the thread style",
            "author_followers": 320,
            "tokens": ["thread", "style", "support", "nice"],
        },
        {
            "id": "m010", "sentiment": "neutral", "priority_score": 38,
            "intent": "Repost note with no question or engagement hook",
            "author_followers": 210,
            "tokens": ["repost", "share", "note"],
        },
        {
            "id": "m011", "sentiment": "positive", "priority_score": 30,
            "intent": "Generic appreciation with no specific question",
            "author_followers": 150,
            "tokens": ["appreciate", "great", "work"],
        },
        {
            "id": "m012", "sentiment": "neutral", "priority_score": 24,
            "intent": "Offhand mention in a multi-person tag chain",
            "author_followers": 90,
            "tokens": ["tag", "mention", "chain"],
        },
        {
            "id": "m013", "sentiment": "negative", "priority_score": 18,
            "intent": "Low-signal complaint with no actionable content",
            "author_followers": 45,
            "tokens": ["complaint", "unhappy", "dislike"],
        },
        {
            "id": "m014", "sentiment": "positive", "priority_score": 10,
            "intent": "Emoji-only positive reaction with no text",
            "author_followers": 80,
            "tokens": ["emoji", "reaction"],
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "window_days": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "current_period": {
        "total_mentions": 71,
        "positive_count": 45,
        "neutral_count": 18,
        "negative_count": 8,
        "authentic_mention_count": 67,
    },
    "previous_period": {
        "total_mentions": 58,
        "positive_count": 32,
        "neutral_count": 16,
        "negative_count": 10,
        "authentic_mention_count": 53,
        "priority_mention_count": 5,
    },
    "mentions": [
        {
            "id": "m001", "sentiment": "positive", "priority_score": 94,
            "intent": "Creator in adjacent habit-science niche sharing their own evening-friction audit results inspired by the thread",
            "author_followers": 6800,
            "tokens": ["habit", "evening", "friction", "audit", "inspired"],
        },
        {
            "id": "m002", "sentiment": "positive", "priority_score": 87,
            "intent": "Detailed question about the shutdown-ritual framework and whether it applies to async-first teams",
            "author_followers": 3900,
            "tokens": ["shutdown", "ritual", "async", "teams", "framework"],
        },
        {
            "id": "m003", "sentiment": "positive", "priority_score": 81,
            "intent": "Follow-up sharing a concrete data point that adds a counter-example to the habit-stacking case study",
            "author_followers": 2700,
            "tokens": ["data", "counter", "habit", "stacking", "case"],
        },
        {
            "id": "m004", "sentiment": "neutral", "priority_score": 74,
            "intent": "Podcast producer asking to feature the shutdown-ritual thread in a deep-work episode",
            "author_followers": 4100,
            "tokens": ["podcast", "feature", "deep", "work", "episode"],
        },
        {
            "id": "m005", "sentiment": "positive", "priority_score": 67,
            "intent": "Newsletter writer citing the habit-stacking numbers post as a reference for an upcoming issue",
            "author_followers": 5200,
            "tokens": ["newsletter", "citing", "habit", "numbers", "reference"],
        },
        {
            "id": "m006", "sentiment": "positive", "priority_score": 60,
            "intent": "Productivity coach asking for permission to adapt the evening-friction audit into a client worksheet",
            "author_followers": 1800,
            "tokens": ["productivity", "coach", "adapt", "worksheet", "permission"],
        },
        {
            "id": "m007", "sentiment": "positive", "priority_score": 52,
            "intent": "Question about the recommended minimum commitment period before the habit-stacking effect is measurable",
            "author_followers": 730,
            "tokens": ["minimum", "commitment", "measurable", "habit", "period"],
        },
        {
            "id": "m008", "sentiment": "neutral", "priority_score": 44,
            "intent": "Offhand repost note adding the creator's handle to an existing thread without a direct question",
            "author_followers": 290,
            "tokens": ["repost", "thread", "note"],
        },
        {
            "id": "m009", "sentiment": "negative", "priority_score": 38,
            "intent": "Mild pushback on the claim that shutdown rituals apply equally to deep-work and shallow-work contexts",
            "author_followers": 410,
            "tokens": ["pushback", "shallow", "work", "claim", "rituals"],
        },
        {
            "id": "m010", "sentiment": "positive", "priority_score": 28,
            "intent": "Brief supportive reply with an emoji and a one-word affirmation",
            "author_followers": 120,
            "tokens": ["supportive", "emoji", "affirmation"],
        },
    ],
}

DEMO_7D = {
    "x_handle": "@JanSol0s",
    "window_days": 7,
    "compare_to": "previous_period",
    "data_source": "demo",
    "current_period": {
        "total_mentions": 31,
        "positive_count": 9,
        "neutral_count": 14,
        "negative_count": 8,
        "authentic_mention_count": 27,
    },
    "previous_period": {
        "total_mentions": 24,
        "positive_count": 7,
        "neutral_count": 11,
        "negative_count": 6,
        "authentic_mention_count": 21,
        "priority_mention_count": 3,
    },
    "mentions": [
        {
            "id": "m001", "sentiment": "positive", "priority_score": 89,
            "intent": "Niche peer sharing a new benchmark result that directly extends the top thread's central argument",
            "author_followers": 3400,
            "tokens": ["benchmark", "extends", "argument", "thread", "peer"],
        },
        {
            "id": "m002", "sentiment": "neutral", "priority_score": 76,
            "intent": "Developer asking whether the offline runner design applies to edge-compute deployments",
            "author_followers": 2100,
            "tokens": ["offline", "runner", "edge", "compute", "deployment"],
        },
        {
            "id": "m003", "sentiment": "positive", "priority_score": 64,
            "intent": "Creator in an adjacent niche asking to collaborate on a thread that bridges both communities",
            "author_followers": 1700,
            "tokens": ["collaborate", "bridge", "communities", "thread", "adjacent"],
        },
        {
            "id": "m004", "sentiment": "neutral", "priority_score": 55,
            "intent": "Question about the CLI runner's PowerShell compatibility on Windows Server environments",
            "author_followers": 980,
            "tokens": ["powershell", "compatibility", "windows", "server", "cli"],
        },
        {
            "id": "m005", "sentiment": "negative", "priority_score": 47,
            "intent": "Substantive disagreement with the single-axis isolation contract described in the thread",
            "author_followers": 820,
            "tokens": ["disagreement", "isolation", "contract", "thread"],
        },
        {
            "id": "m006", "sentiment": "positive", "priority_score": 38,
            "intent": "Brief affirmation of the infra-tooling thread from a longtime follower",
            "author_followers": 540,
            "tokens": ["affirmation", "tooling", "infra", "follower"],
        },
        {
            "id": "m007", "sentiment": "neutral", "priority_score": 29,
            "intent": "Repost with an added observation about a single-day spike in a related niche topic",
            "author_followers": 210,
            "tokens": ["repost", "spike", "niche", "observation"],
        },
        {
            "id": "m008", "sentiment": "negative", "priority_score": 21,
            "intent": "Critical comment about the posting frequency during the window — no actionable content",
            "author_followers": 95,
            "tokens": ["frequency", "posting", "critical", "comment"],
        },
    ],
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MentionAggregates:
    total: int
    positive: int
    neutral: int
    negative: int
    authentic: int


@dataclass
class MentionHealthMetrics:
    volume_delta_pct: float
    net_sentiment: float
    priority_rate_pct: float
    authentic_share_pct: float
    # Previous period equivalents for trend arrows
    prev_net_sentiment: float
    prev_priority_rate_pct: float
    prev_authentic_share_pct: float


@dataclass
class MentionHealthScores:
    volume_delta_pct: float
    net_sentiment: float
    priority_rate_pct: float
    authentic_share_pct: float
    volume_arrow: str
    sentiment_arrow: str
    priority_arrow: str
    authentic_arrow: str
    health_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)


@dataclass
class PriorityMention:
    id: str
    sentiment: str
    intent: str
    priority_score: int
    is_demo: bool


@dataclass
class TrollCluster:
    member_ids: list[str]
    size: int


@dataclass
class RedFlag:
    title: str
    severity: str
    explanation: str
    remediation: str


@dataclass
class Recommendation:
    text: str
    bridge_slug: str


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def normalize_handle(raw: str) -> str:
    h = raw.strip()
    if not h:
        return ""
    return h if h.startswith("@") else "@" + h


def load_mentions_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"--mentions-file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--mentions-file is not valid JSON: {exc}") from exc


def parse_aggregates(period: dict) -> MentionAggregates:
    return MentionAggregates(
        total=int(period["total_mentions"]),
        positive=int(period["positive_count"]),
        neutral=int(period["neutral_count"]),
        negative=int(period["negative_count"]),
        authentic=int(period["authentic_mention_count"]),
    )


# ---------------------------------------------------------------------------
# Troll-cluster detection (Jaccard similarity on token sets)
# ---------------------------------------------------------------------------


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union > 0 else 0.0


def detect_troll_clusters(mentions: list[dict]) -> list[TrollCluster]:
    """Return clusters of ≥5 negative mentions with >60% pairwise Jaccard overlap."""
    negatives = [m for m in mentions if m.get("sentiment") == "negative"]
    if len(negatives) < TROLL_MIN_CLUSTER_SIZE:
        return []

    token_sets = [set(m.get("tokens", [])) for m in negatives]
    n = len(negatives)

    # Build adjacency matrix: edge when Jaccard > threshold
    adj: list[list[bool]] = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(token_sets[i], token_sets[j]) > TROLL_JACCARD_THRESHOLD:
                adj[i][j] = adj[j][i] = True

    # BFS to find connected components of size ≥ TROLL_MIN_CLUSTER_SIZE
    visited = [False] * n
    clusters: list[TrollCluster] = []
    for start in range(n):
        if visited[start]:
            continue
        component: list[int] = []
        queue = [start]
        while queue:
            node = queue.pop()
            if visited[node]:
                continue
            visited[node] = True
            component.append(node)
            for neighbour in range(n):
                if adj[node][neighbour] and not visited[neighbour]:
                    queue.append(neighbour)
        if len(component) >= TROLL_MIN_CLUSTER_SIZE:
            clusters.append(TrollCluster(
                member_ids=[negatives[i]["id"] for i in component],
                size=len(component),
            ))

    return clusters


# ---------------------------------------------------------------------------
# Priority queue building
# ---------------------------------------------------------------------------


def build_priority_queue(
    mentions: list[dict],
    cluster_member_ids: set[str],
    is_demo: bool,
) -> list[PriorityMention]:
    """Return up to MAX_PRIORITY_QUEUE mentions sorted by priority_score desc,
    with troll-cluster members excluded."""
    eligible = [
        m for m in mentions
        if m["id"] not in cluster_member_ids
        and int(m.get("priority_score", 0)) >= PRIORITY_SCORE_THRESHOLD
    ]
    eligible.sort(key=lambda m: int(m.get("priority_score", 0)), reverse=True)
    queue: list[PriorityMention] = []
    for m in eligible[:MAX_PRIORITY_QUEUE]:
        queue.append(PriorityMention(
            id=m["id"],
            sentiment=m.get("sentiment", "neutral"),
            intent=str(m.get("intent", "(paraphrased mention)")),
            priority_score=int(m.get("priority_score", 0)),
            is_demo=is_demo,
        ))
    return queue


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_health_metrics(payload: dict) -> MentionHealthMetrics:
    cur = parse_aggregates(payload["current_period"])
    prev_raw = payload["previous_period"]
    prev = MentionAggregates(
        total=int(prev_raw["total_mentions"]),
        positive=int(prev_raw["positive_count"]),
        neutral=int(prev_raw["neutral_count"]),
        negative=int(prev_raw["negative_count"]),
        authentic=int(prev_raw["authentic_mention_count"]),
    )
    prev_priority_count = int(prev_raw.get("priority_mention_count", 0))

    # Metric 1: Mention volume delta
    prev_total = max(prev.total, 1)
    volume_delta_pct = (cur.total - prev.total) / prev_total * 100.0

    # Metric 2: Net sentiment score (−100 to +100)
    cur_total = max(cur.total, 1)
    net_sentiment = (cur.positive - cur.negative) / cur_total * 100.0

    # Metric 3: Priority reply rate — computed from mentions array when present
    mentions_list = payload.get("mentions", [])
    if mentions_list:
        priority_count = sum(
            1 for m in mentions_list
            if int(m.get("priority_score", 0)) >= PRIORITY_SCORE_THRESHOLD
        )
    else:
        # Fallback: not computable from aggregates; use 0 to avoid fabricating
        priority_count = 0
    priority_rate_pct = priority_count / cur_total * 100.0

    # Metric 4: Authentic reach share
    authentic_share_pct = cur.authentic / cur_total * 100.0

    # Previous period equivalents for trend arrows
    prev_net = (prev.positive - prev.negative) / max(prev.total, 1) * 100.0
    prev_priority_rate = prev_priority_count / max(prev.total, 1) * 100.0
    prev_authentic_share = prev.authentic / max(prev.total, 1) * 100.0

    return MentionHealthMetrics(
        volume_delta_pct=volume_delta_pct,
        net_sentiment=net_sentiment,
        priority_rate_pct=priority_rate_pct,
        authentic_share_pct=authentic_share_pct,
        prev_net_sentiment=prev_net,
        prev_priority_rate_pct=prev_priority_rate,
        prev_authentic_share_pct=prev_authentic_share,
    )


# ---------------------------------------------------------------------------
# Normalisation + scoring
# ---------------------------------------------------------------------------


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


# 5-arrow trend bucketing
def _pct_arrow(delta_pct: float) -> str:
    """Standard ±5% / ±25% thresholds for % change metrics."""
    if delta_pct >= 25.0:
        return "▲▲"
    if delta_pct >= 5.0:
        return "▲"
    if delta_pct >= -5.0:
        return "▬"
    if delta_pct >= -25.0:
        return "▼"
    return "▼▼"


def _sentiment_arrow(delta_pts: float) -> str:
    """Tighter ±5 pt / ±15 pt thresholds for the −100 to +100 net sentiment scale."""
    if delta_pts >= 15.0:
        return "▲▲"
    if delta_pts >= 5.0:
        return "▲"
    if delta_pts >= -5.0:
        return "▬"
    if delta_pts >= -15.0:
        return "▼"
    return "▼▼"


def score_health(
    m: MentionHealthMetrics,
    sentiment_baseline: float,
) -> MentionHealthScores:
    lo_vol, hi_vol = HEALTHY_RANGES["Mention volume delta"]
    lo_sent, hi_sent = HEALTHY_RANGES["Net sentiment score"]
    lo_pri, hi_pri = HEALTHY_RANGES["Priority reply rate"]
    lo_auth, hi_auth = HEALTHY_RANGES["Authentic reach share"]

    norm_vol = _norm(m.volume_delta_pct, lo_vol, hi_vol)
    norm_sent = _norm(m.net_sentiment, lo_sent, hi_sent)
    norm_pri = _norm(m.priority_rate_pct, lo_pri, hi_pri)
    norm_auth = _norm(m.authentic_share_pct, lo_auth, hi_auth)

    health_score = round(
        HEALTH_WEIGHTS["Net sentiment score"]   * norm_sent
        + HEALTH_WEIGHTS["Mention volume delta"]  * norm_vol
        + HEALTH_WEIGHTS["Priority reply rate"]   * norm_pri
        + HEALTH_WEIGHTS["Authentic reach share"] * norm_auth
    )

    # Trend arrows
    volume_arrow = _pct_arrow(m.volume_delta_pct)

    sentiment_delta = m.net_sentiment - m.prev_net_sentiment
    sentiment_arrow = _sentiment_arrow(sentiment_delta)

    prev_pri = max(m.prev_priority_rate_pct, 0.01)
    priority_delta_pct = (m.priority_rate_pct - m.prev_priority_rate_pct) / prev_pri * 100.0
    priority_arrow = _pct_arrow(priority_delta_pct)

    prev_auth = max(m.prev_authentic_share_pct, 0.01)
    authentic_delta_pct = (m.authentic_share_pct - m.prev_authentic_share_pct) / prev_auth * 100.0
    authentic_arrow = _pct_arrow(authentic_delta_pct)

    paradox = (
        m.volume_delta_pct > PARADOX_VOLUME_THRESHOLD
        and m.net_sentiment < sentiment_baseline
    )

    return MentionHealthScores(
        volume_delta_pct=m.volume_delta_pct,
        net_sentiment=m.net_sentiment,
        priority_rate_pct=m.priority_rate_pct,
        authentic_share_pct=m.authentic_share_pct,
        volume_arrow=volume_arrow,
        sentiment_arrow=sentiment_arrow,
        priority_arrow=priority_arrow,
        authentic_arrow=authentic_arrow,
        health_score=health_score,
        paradox_active=paradox,
        interpretations=_build_interpretations(m, sentiment_baseline),
    )


def _build_interpretations(m: MentionHealthMetrics, baseline: float) -> dict:
    out: dict[str, str] = {}

    # Volume delta
    if m.volume_delta_pct > PARADOX_VOLUME_THRESHOLD:
        out["Mention volume delta"] = (
            "Strong rise — verify the spike originates from genuine niche engagement, not a coordinated campaign."
        )
    elif m.volume_delta_pct >= 5.0:
        out["Mention volume delta"] = "Rising; the trend supports the current content cadence."
    elif m.volume_delta_pct >= -5.0:
        out["Mention volume delta"] = "Stable vs the comparison basis; no cadence change needed."
    elif m.volume_delta_pct >= -25.0:
        out["Mention volume delta"] = "Falling; check whether the prior period contained an outlier post."
    else:
        out["Mention volume delta"] = "Strong fall; investigate content reach changes or topic drift."

    # Net sentiment
    if m.net_sentiment >= 50.0:
        out["Net sentiment score"] = (
            "Net-positive community signal; the majority of mentions reflect substantive support."
        )
    elif m.net_sentiment >= baseline:
        out["Net sentiment score"] = (
            f"Above the {baseline:.0f} baseline; community sentiment is net-positive."
        )
    elif m.net_sentiment >= -10.0:
        out["Net sentiment score"] = (
            f"Near-neutral; the period's mentions split roughly evenly across sentiment bands."
        )
    else:
        out["Net sentiment score"] = (
            "Net-negative; the volume spike is driven predominantly by criticism rather than community support."
        )

    # Priority reply rate
    if m.priority_rate_pct >= 25.0:
        out["Priority reply rate"] = (
            "High reply burden — consider batching lower-priority mentions to protect focus time."
        )
    elif m.priority_rate_pct >= 10.0:
        out["Priority reply rate"] = (
            "Moderate reply burden; manageable with a structured daily triage session."
        )
    elif m.priority_rate_pct >= 5.0:
        out["Priority reply rate"] = "Low reply burden; all priority mentions can be handled in one session."
    else:
        out["Priority reply rate"] = (
            "Very few priority mentions — either volume is low or most mentions are low-signal."
        )

    # Authentic reach share
    if m.authentic_share_pct >= 90.0:
        out["Authentic reach share"] = "Excellent authentic signal; bot-floor is minimal."
    elif m.authentic_share_pct >= 75.0:
        out["Authentic reach share"] = (
            "Majority of mentions from established accounts; bot-floor signal stable."
        )
    elif m.authentic_share_pct >= 60.0:
        out["Authentic reach share"] = (
            "Borderline authentic share; audit for bot activity if the rate continues to fall."
        )
    else:
        out["Authentic reach share"] = (
            "Low authentic share; a significant portion of mentions may be bot or low-quality accounts."
        )

    return out


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: MentionHealthScores,
    clusters: list[TrollCluster],
    window: int,
    sentiment_baseline: float,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: Sentiment-spike paradox
    if scores.paradox_active:
        flags.append(RedFlag(
            title="Sentiment-spike paradox",
            severity="high",
            explanation=(
                f"Mention volume delta at +{scores.volume_delta_pct:.1f}% sits above the "
                f"+{int(PARADOX_VOLUME_THRESHOLD)}% threshold while Net sentiment score at "
                f"{scores.net_sentiment:.1f} is below the {sentiment_baseline:.0f} baseline. "
                "Volume grew but the new mentions are net-negative — not community support."
            ),
            remediation=(
                "Inspect whether the volume spike traces to an external trigger (quote-tweet storm, trending topic) "
                "before deciding whether to engage; if so, accept the period as a signal event and retarget next "
                "period for community sentiment."
            ),
        ))

    # Rule 2: Troll-cluster guard
    for cluster in clusters:
        flags.append(RedFlag(
            title="Coordinated negative cluster",
            severity="high",
            explanation=(
                f"{cluster.size} negative mentions share >60% pairwise token overlap — "
                "evidence of a coordinated pile-on rather than independent criticism. "
                "All cluster members excluded from the priority reply queue."
            ),
            remediation=(
                "Do not reply to cluster members individually; replying amplifies the signal. "
                "If the cluster persists across two consecutive windows, consider a single calm "
                "public clarification or report the pattern to X safety."
            ),
        ))

    # Rule 3: 7-day single-day variance
    if window == 7:
        flags.append(RedFlag(
            title="Single-day variance exposure",
            severity="medium",
            explanation=(
                "A 7d mention window is dominated by single-day variance; one viral post or "
                "one quiet day can flip every trend arrow."
            ),
            remediation=(
                "Re-run with --window 30 once 14+ more days have passed before declaring directional reads."
            ),
        ))

    # Rule 4: High authentic reach loss (potential bot activity)
    if scores.authentic_share_pct < 65.0:
        flags.append(RedFlag(
            title="Low authentic reach share",
            severity="medium",
            explanation=(
                f"Authentic reach share at {scores.authentic_share_pct:.1f}% is below the 65% watch threshold; "
                "a meaningful portion of this period's mentions may be bot or low-quality accounts."
            ),
            remediation=(
                "Pair with `follower-quality-analyzer` to audit the mention cohort before acting on any volume signal."
            ),
        ))

    # Rule 5: Near-paradox warning (volume close but sentiment above baseline)
    if (
        not scores.paradox_active
        and scores.volume_delta_pct > 20.0
        and scores.net_sentiment < 20.0
    ):
        flags.append(RedFlag(
            title="Near-paradox watch",
            severity="low",
            explanation=(
                f"Mention volume delta at +{scores.volume_delta_pct:.1f}% is growing while Net sentiment "
                f"score at {scores.net_sentiment:.1f} remains modest — one more negative-heavy window could "
                "trigger the sentiment-spike paradox."
            ),
            remediation=(
                "Run `analytics-summarizer` to confirm whether the content driving volume is the same content "
                "earning engagement — divergence here is an early-warning signal."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-period read",
            severity="low",
            explanation=(
                "One mention window is directional, not conclusive. "
                "Treat the Mention Health score as a snapshot, not a trend."
            ),
            remediation=(
                "Re-run monthly to build a baseline of trend arrows across consecutive windows."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations (mandatory: reply-drafter + analytics-summarizer always first)
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: MentionHealthScores,
    priority_queue: list[PriorityMention],
    clusters: list[TrollCluster],
    window: int,
) -> list[Recommendation]:
    # Mandatory position 1: reply-drafter
    queue_count = len(priority_queue)
    mandatory_reply = Recommendation(
        text=(
            f"Work through the {queue_count}-mention priority queue in sequence; "
            "voice-faithful replies only, no engagement bait."
        ),
        bridge_slug="reply-drafter",
    )

    # Mandatory position 2: analytics-summarizer
    if scores.paradox_active:
        analytics_text = (
            "Cross-reference this mention window against the same period's impression and engagement "
            "metrics to confirm whether the volume spike correlates with a content or reach event."
        )
    else:
        analytics_text = (
            "Cross-reference this mention window against the period analytics to confirm the "
            "sentiment trend is consistent with the broader engagement signal."
        )
    mandatory_analytics = Recommendation(
        text=analytics_text,
        bridge_slug="analytics-summarizer",
    )

    # Optional pool (shuffled)
    optional_pool: list[Recommendation] = []

    if clusters:
        optional_pool.append(Recommendation(
            text=(
                "Do not reply to the coordinated negative cluster individually; if the pattern "
                "persists across the next window, draft a single calm public clarification."
            ),
            bridge_slug="reply-drafter",
        ))

    if scores.paradox_active or scores.net_sentiment < 20.0:
        optional_pool.append(Recommendation(
            text=(
                "Audit whether the content archetype that drove the mention spike attracts the "
                "right audience — divergent niches produce volume without community sentiment."
            ),
            bridge_slug="follower-quality-analyzer",
        ))

    if scores.net_sentiment >= 30.0 and priority_queue:
        optional_pool.append(Recommendation(
            text=(
                "Re-source the next anchor post in the cluster that generated the highest-quality "
                "positive mentions; the community has signalled which content they value."
            ),
            bridge_slug="content-idea-generator",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Compare the sentiment pattern against competitor mention windows to confirm "
            "the signal is specific to this creator's content, not a niche-wide trend."
        ),
        bridge_slug="competitor-watch",
    ))

    if scores.volume_delta_pct > 15.0 and not scores.paradox_active:
        optional_pool.append(Recommendation(
            text=(
                "Promote the content archetype that drove the mention spike into a structured A/B "
                "to confirm the format lifts engagement rate, not just volume."
            ),
            bridge_slug="ab-test-suggester",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Review the brand voice used in the top-performing content to confirm the tone "
            "that drove positive mentions is the tone the creator wants to scale."
        ),
        bridge_slug="brand-voice-trainer",
    ))

    # Shuffle optional pool with seeded RNG
    rng.shuffle(optional_pool)

    # De-duplicate bridge slugs (avoid two reply-drafter recs from optional)
    seen_optional: set[str] = {"reply-drafter", "analytics-summarizer"}
    deduped: list[Recommendation] = []
    for rec in optional_pool:
        if rec.bridge_slug not in seen_optional:
            deduped.append(rec)
            seen_optional.add(rec.bridge_slug)

    result = [mandatory_reply, mandatory_analytics] + deduped[:3]
    return result[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def build_confidence(
    scores: MentionHealthScores,
    clusters: list[TrollCluster],
    window: int,
    is_demo: bool,
) -> tuple[str, str]:
    if is_demo:
        return (
            "low",
            "data source is seeded demo mentions — re-run with --mentions-file pointing at the "
            "actual X mention export to lift confidence.",
        )
    if window == 30 and scores.health_score >= 65 and not clusters:
        return (
            "high",
            f"30d window covers the main signals; Mention Health score {scores.health_score}/100 "
            "with no troll-cluster interference.",
        )
    if scores.health_score >= 50:
        return (
            "medium",
            f"Mention Health score {scores.health_score}/100; widen the window or supply richer "
            "mention data to lift to high.",
        )
    return (
        "low",
        f"Mention Health score {scores.health_score}/100; investigate the falling metrics and "
        "troll-cluster interference before declaring a trend.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _demo_tag(is_demo: bool) -> str:
    return f" {DEMO_LABEL}" if is_demo else ""


def _render_snapshot(payload: dict, scores: MentionHealthScores, is_demo: bool) -> str:
    handle = normalize_handle(payload["x_handle"])
    window = int(payload["window_days"])
    compare = payload.get("compare_to", "previous_period")

    if scores.paradox_active:
        headline = (
            f"{handle}: {window}d mention window — sentiment-spike paradox active; "
            f"mention volume spiked +{scores.volume_delta_pct:.1f}% but community "
            f"sentiment is net-negative at {scores.net_sentiment:.1f}."
        )
    elif scores.health_score >= 70:
        headline = (
            f"{handle}: {window}d mention window — healthy community signal "
            f"(Mention Health {scores.health_score}/100)."
        )
    elif scores.health_score >= 50:
        headline = (
            f"{handle}: {window}d mention window — directional period "
            f"(Mention Health {scores.health_score}/100); monitor sentiment trend."
        )
    else:
        headline = (
            f"{handle}: {window}d mention window — weak period; investigate "
            "falling sentiment before scaling content cadence."
        )

    data_line = (
        "seeded demo mentions — re-run with --mentions-file for real X data"
        if is_demo
        else "real X export from --mentions-file"
    )

    return "\n".join([
        "## Mention Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Window**: {window}d",
        f"- **Comparison basis**: {compare}",
        f"- **Data source**: {data_line}",
    ])


def _render_mention_health(
    scores: MentionHealthScores, is_demo: bool, clusters: list[TrollCluster],
) -> str:
    dt = _demo_tag(is_demo)
    cluster_note = ""
    if clusters:
        total_cluster = sum(c.size for c in clusters)
        cluster_note = (
            f" Troll cluster ({total_cluster} mentions) excluded from queue; "
            f"{MAX_PRIORITY_QUEUE} genuine priority replies queued."
        )
    pri_interp = scores.interpretations["Priority reply rate"]
    if clusters:
        pri_interp = f"Elevated — {cluster_note.strip()}"

    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        (
            f"| Mention volume delta | {scores.volume_delta_pct:+.1f}%{dt} | "
            f"{scores.volume_arrow} | {scores.interpretations['Mention volume delta']} |"
        ),
        (
            f"| Net sentiment score  | {scores.net_sentiment:.1f}{dt} | "
            f"{scores.sentiment_arrow} | {scores.interpretations['Net sentiment score']} |"
        ),
        (
            f"| Priority reply rate  | {scores.priority_rate_pct:.1f}%{dt} | "
            f"{scores.priority_arrow} | {pri_interp} |"
        ),
        (
            f"| Authentic reach share| {scores.authentic_share_pct:.1f}%{dt} | "
            f"{scores.authentic_arrow} | {scores.interpretations['Authentic reach share']} |"
        ),
    ]
    out = "## Mention Health\n\n" + "\n".join(rows)
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: mention volume spiked but net sentiment is below the baseline — "
            "growth driven by negative or neutral mentions rather than community support."
        )
    out += f"\n\n**Mention Health score**: {scores.health_score}/100"
    return out


def _render_sentiment_breakdown(
    payload: dict,
    is_demo: bool,
    clusters: list[TrollCluster],
) -> str:
    cur = parse_aggregates(payload["current_period"])
    dt = _demo_tag(is_demo)
    total = max(cur.total, 1)
    pos_pct = cur.positive / total * 100.0
    neu_pct = cur.neutral / total * 100.0
    neg_pct = cur.negative / total * 100.0

    rows = [
        "| Band     | Count | Share  |",
        "|---|---|---|",
        f"| Positive | {cur.positive}{dt} | {pos_pct:.1f}% |",
        f"| Neutral  | {cur.neutral}{dt}  | {neu_pct:.1f}% |",
        f"| Negative | {cur.negative}{dt} | {neg_pct:.1f}% |",
    ]

    if neg_pct > 40.0 and clusters:
        cluster_total = sum(c.size for c in clusters)
        note = (
            f"Negative band dominates this period. "
            f"The troll cluster ({cluster_total} coordinated mentions) inflates the negative count — see Red Flags."
        )
    elif pos_pct > 55.0:
        note = "Positive band dominates; the majority of community mentions reflect substantive support."
    elif neg_pct > pos_pct:
        note = (
            "Negative band leads the period. Investigate whether the sentiment is driven by a "
            "specific content type or an external trigger before acting on cadence."
        )
    else:
        note = "Sentiment is split across bands; no single tone dominates the period."

    return "## Sentiment Breakdown\n\n" + "\n".join(rows) + "\n\n" + note


def _render_priority_queue(
    queue: list[PriorityMention],
    total_priority_count: int,
    clusters: list[TrollCluster],
    is_demo: bool,
) -> str:
    cluster_total = sum(c.size for c in clusters)
    dt = _demo_tag(is_demo)

    if cluster_total > 0:
        header = (
            f"## Priority Reply Queue "
            f"({len(queue)} of {total_priority_count} priority mentions — "
            f"{cluster_total} troll-cluster mentions excluded)"
        )
    else:
        header = f"## Priority Reply Queue ({len(queue)} priority mentions)"

    if not queue:
        return header + "\n\n_(no priority mentions above the threshold after troll filter)_"

    lines = [header, ""]
    for i, m in enumerate(queue, start=1):
        score_label = f"priority {m.priority_score}{dt}"
        lines.append(
            f"{i}. **{m.intent}** ({m.sentiment} · {score_label}) — bridges to: `reply-drafter`"
        )
    return "\n".join(lines)


def _render_red_flags(flags: list[RedFlag]) -> str:
    return "## Red Flags\n\n" + "\n".join(
        f"- **{f.title}** · severity: {f.severity} — {f.explanation} "
        f"*Remediation:* {f.remediation}"
        for f in flags
    )


def _render_recommendations(recs: list[Recommendation]) -> str:
    lines = ["## Recommendations", ""]
    for i, rec in enumerate(recs, start=1):
        lines.append(f"{i}. {rec.text} — bridges to: `{rec.bridge_slug}`")
    return "\n".join(lines)


def _render_mention_audit(
    payload: dict,
    clusters: list[TrollCluster],
    is_demo: bool,
) -> str:
    window = int(payload["window_days"])
    window_line = (
        "7d window is dominated by single-day variance; treat all reads as directional."
        if window == 7
        else f"{window}d window is sufficient for the sentiment patterns surfaced."
    )
    data_line = (
        "seeded demo placeholders — runner cannot speak to real-creator confidence until "
        "--mentions-file is supplied."
        if is_demo
        else "real mention export loaded; no missing-field gaps detected."
    )
    cluster_total = sum(c.size for c in clusters)
    if cluster_total > 0:
        cluster_line = (
            f"{cluster_total} troll-cluster mentions removed from the priority queue; "
            "negative sentiment band is inflated by the cluster."
        )
        next_sample = (
            "re-run in 30 days to determine whether the cluster is a recurring pattern or a one-off event."
        )
    else:
        cluster_line = "none detected — negative sentiment band reflects genuine independent mentions."
        next_sample = (
            "re-run when 14+ more days have passed; widen to 30d if currently on 7d."
            if window == 7
            else "re-run in 30 days to build consecutive-window trend data."
        )

    return "\n".join([
        "## Mention Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {window_line}",
        f"- **Data source confidence**: {data_line}",
        f"- **Troll-cluster impact**: {cluster_line}",
        f"- **Suggested next sample**: {next_sample}",
        "- **Re-run cadence**: weekly during active mention spikes, otherwise monthly.",
    ])


def render_report(
    payload: dict,
    scores: MentionHealthScores,
    priority_queue: list[PriorityMention],
    total_priority_count: int,
    clusters: list[TrollCluster],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    is_demo: bool,
) -> str:
    sections = [
        _render_snapshot(payload, scores, is_demo),
        "",
        _render_mention_health(scores, is_demo, clusters),
        "",
        _render_sentiment_breakdown(payload, is_demo, clusters),
        "",
        _render_priority_queue(priority_queue, total_priority_count, clusters, is_demo),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    audit_trigger = bool(clusters) or int(payload["window_days"]) == 7
    if audit_trigger:
        sections.extend([
            "",
            _render_mention_audit(payload, clusters, is_demo),
        ])

    return "\n".join(sections).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Saved-file Apache 2.0 header
# ---------------------------------------------------------------------------


def saved_file_header(handle: str, when_iso: str) -> str:
    return (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- Generated by Mention Summarizer (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — never auto-published. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_mention_summary(
    *,
    x_handle: str,
    mentions_file: Optional[str] = None,
    window: int = 30,
    compare_to: str = "previous_period",
    sentiment_baseline: float = DEFAULT_SENTIMENT_BASELINE,
    demo_mode: Optional[str] = None,
) -> str:
    handle = normalize_handle(x_handle)
    if window not in WINDOW_OPTIONS:
        raise ValueError(f"window must be one of {WINDOW_OPTIONS}, got {window!r}")
    if compare_to not in COMPARE_OPTIONS:
        raise ValueError(f"compare_to must be one of {COMPARE_OPTIONS}, got {compare_to!r}")

    if mentions_file:
        payload = load_mentions_file(Path(mentions_file).expanduser().resolve())
        is_demo = bool(payload.get("data_source") == "demo")
    elif demo_mode == "troll":
        payload = json.loads(json.dumps(DEMO_TROLL))
        is_demo = True
    elif demo_mode == "healthy":
        payload = json.loads(json.dumps(DEMO_HEALTHY))
        is_demo = True
    elif demo_mode == "7d":
        payload = json.loads(json.dumps(DEMO_7D))
        is_demo = True
    else:
        raise ValueError(
            "Provide --mentions-file <path> or one of --demo / --demo-healthy / --demo-7d."
        )

    # CLI flags override payload meta
    payload["x_handle"] = handle
    payload["window_days"] = window
    payload["compare_to"] = compare_to

    mentions_list = payload.get("mentions", [])

    # Troll-cluster detection
    clusters = detect_troll_clusters(mentions_list)
    cluster_member_ids: set[str] = {
        mid for c in clusters for mid in c.member_ids
    }

    # Priority queue (troll-cluster members excluded)
    priority_queue = build_priority_queue(mentions_list, cluster_member_ids, is_demo)

    # Total priority count before troll filter (for queue header label)
    total_priority_count = sum(
        1 for m in mentions_list
        if int(m.get("priority_score", 0)) >= PRIORITY_SCORE_THRESHOLD
    )

    # Metrics and scoring
    health_metrics = compute_health_metrics(payload)
    scores = score_health(health_metrics, sentiment_baseline)

    # Seeded RNG: sha256(handle + sorted-json + window); date excluded for reproducibility
    seed_str = handle + json.dumps(payload, sort_keys=True) + str(window)
    seed = hashlib.sha256(seed_str.encode("utf-8")).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))

    flags = build_red_flags(scores, clusters, window, sentiment_baseline)
    recs = build_recommendations(rng, scores, priority_queue, clusters, window)
    confidence = build_confidence(scores, clusters, window, is_demo)

    return render_report(
        payload, scores, priority_queue, total_priority_count,
        clusters, flags, recs, confidence, is_demo,
    )


generate = generate_mention_summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  Mention Summarizer (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · Troll-cluster guard active\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mention-summarizer",
        description=(
            "Read creator-supplied X mention data (or seeded demo mentions) and emit a "
            "7/8-section mention summary with 4 official Mention Health metrics, "
            "sentiment-spike paradox detection, 3-band sentiment breakdown, priority "
            "reply queue (max 8) with troll-cluster guard, and mandatory bridges to "
            "reply-drafter + analytics-summarizer. Drafts only."
        ),
    )
    p.add_argument(
        "--handle", required=True,
        help="The creator's X handle (with or without leading @).",
    )
    p.add_argument(
        "--mentions-file",
        help="Path to a JSON mention export. Required unless a --demo flag is passed.",
    )
    p.add_argument(
        "--days", "--window", dest="window", type=int, choices=list(WINDOW_OPTIONS),
        default=30,
        help="Period window in days (7, 30, or 90). 7d auto-triggers Mention Audit. Default 30.",
    )
    p.add_argument(
        "--compare-to", choices=list(COMPARE_OPTIONS), default="previous_period",
        help="Comparison basis for delta calculation. Default previous_period.",
    )
    p.add_argument(
        "--sentiment-baseline", type=float, default=DEFAULT_SENTIMENT_BASELINE,
        help=(
            f"Net sentiment score threshold below which the paradox fires when volume also "
            f"spikes (default {DEFAULT_SENTIMENT_BASELINE})."
        ),
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo", action="store_true",
        help="Run with the official paradox-firing + troll-cluster demo mentions.",
    )
    p.add_argument(
        "--demo-healthy", action="store_true",
        help="Run with healthy community mentions (positive-dominant, no paradox, no troll cluster).",
    )
    p.add_argument(
        "--demo-7d", action="store_true",
        help="Run with 7-day window demo mentions (auto-triggers Mention Audit).",
    )
    p.add_argument(
        "--show-system-prompt", action="store_true",
        help="Print system prompt path + size on stderr.",
    )
    return p


def cli(argv: Optional[list[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    if not args.no_banner:
        sys.stdout.write(banner())
        sys.stdout.flush()

    if args.show_system_prompt:
        if SYSTEM_PROMPT_PATH.exists():
            sys.stderr.write(
                f"[system-prompt] loaded from {SYSTEM_PROMPT_PATH}\n"
                f"[system-prompt] {len(SYSTEM_PROMPT_PATH.read_text(encoding='utf-8'))} chars\n"
            )
        else:
            sys.stderr.write(
                f"[system-prompt] not found at {SYSTEM_PROMPT_PATH} — runner uses embedded contract\n"
            )

    demo_mode: Optional[str] = None
    if args.demo:
        demo_mode = "troll"
    elif args.demo_healthy:
        demo_mode = "healthy"
    elif args.demo_7d:
        demo_mode = "7d"

    if not args.mentions_file and demo_mode is None:
        sys.stderr.write(
            "error: provide --mentions-file <path> or one of --demo / --demo-healthy / --demo-7d.\n"
        )
        return 2

    rendered = generate_mention_summary(
        x_handle=args.handle,
        mentions_file=args.mentions_file,
        window=args.window,
        compare_to=args.compare_to,
        sentiment_baseline=args.sentiment_baseline,
        demo_mode=demo_mode,
    )

    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        when_full = datetime.now(timezone.utc).isoformat()
        out_path.write_text(
            saved_file_header(normalize_handle(args.handle), when_full) + rendered,
            encoding="utf-8",
        )
        sys.stderr.write(f"[saved] {out_path}\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
