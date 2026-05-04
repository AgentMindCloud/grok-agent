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
"""DM Triager — runner.

CLI entry point for the ``dm-triager`` creator template
(grok-agent.yaml v2.15, kind: creator-template, runtime: cli_only).

Reads a creator-supplied X DM export (JSON) — or seeded demo DMs when
no file is provided — and emits the strict 7/8-section triage report
defined by the P91 system prompt:

  1. Triage Snapshot
  2. Triage Health (4-row metric table + weighted score + paradox if active)
  3. Bucket Breakdown (4 priority buckets: Urgent / Opportunity / Routine / Spam)
  4. Suggested Actions (max 6 — spam-burst DMs excluded + Red Flagged)
  5. Red Flags (2-4 cards; paradox + spam burst + others)
  6. Recommendations (3-5; reply-drafter + mention-summarizer unconditional)
  7. Confidence
  + Optional DM Audit (auto-appended when spam-burst detected OR
    window=7d)

Hard guarantees enforced by this runner:

* Drafts only. Never auto-replies, mutes, blocks, or reports any DM.
* No fabricated statistics. Demo DMs carry an explicit
  `[demo DM — re-run with --dms-file for real X data]` label.
* Opportunity-flood paradox surfaced in BOTH the Triage Health section
  AND the Red Flags section whenever Opportunity ratio > 30% AND
  Authentic sender share < the configured floor (default 60).
* Triage Health score formula is fixed:
    round(0.30*Authentic_norm + 0.25*Opportunity_norm +
          0.25*SpamInverted_norm + 0.20*UrgencyBand_norm)
* Spam-burst guard: >=5 Spam-bucket DMs with >60% pairwise Jaccard
  token overlap → excluded from suggested-action queue + consolidated
  Red Flag with severity high and specific remediation.
* Suggested-action queue capped at 6 after spam-burst filter.
* Unconditional bridges: reply-drafter (position 1) and
  mention-summarizer (position 2) in every Recommendations section.
* Privacy-first: no sender X handles, raw DM text, attachment URLs, or
  external links in rendered output. DM intent is paraphrased only.
  DM content never leaves the user's local Windows machine.
* Deterministic: seeded by sha256(handle + sorted-payload-json + window).
  Date is NOT included in the seed so examples remain reproducible.
* Zero external network calls in v1.

Manifest contract::

    generate = generate_dm_triage

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

# Triage Health metric weights (must sum to 1.0)
HEALTH_WEIGHTS = {
    "Authentic sender share": 0.30,
    "Opportunity ratio":      0.25,
    "Spam pressure":          0.25,   # inverted before normalising
    "Triage urgency rate":    0.20,   # band-shaped
}

# Healthy ranges for sub-score normalisation (lo, hi → 0–100)
HEALTHY_RANGES = {
    "Triage urgency rate":    ( 5.0, 25.0),  # band-shaped (full marks inside)
    "Opportunity ratio":      (10.0, 40.0),  # % of total DMs
    "Spam pressure":          ( 0.0, 25.0),  # % of total DMs (inverted)
    "Authentic sender share": (60.0, 95.0),  # % of total DMs
}

# Opportunity-flood paradox thresholds
PARADOX_OPPORTUNITY_THRESHOLD = 30.0    # Opportunity ratio > 30%
DEFAULT_AUTHENTICITY_FLOOR     = 60.0   # Authentic sender share < floor

# Suggested-action queue
PRIORITY_SCORE_THRESHOLD = 50           # DMs with score >= this are priority
MAX_ACTION_QUEUE = 6

# Spam-burst guard
BURST_MIN_CLUSTER_SIZE = 5
BURST_JACCARD_THRESHOLD = 0.60          # pairwise Jaccard > 60%

WINDOW_OPTIONS = (7, 30, 90)
COMPARE_OPTIONS = ("previous_period", "benchmark")

BUCKETS = ("Urgent", "Opportunity", "Routine", "Spam")

DEMO_LABEL = "[demo DM — re-run with --dms-file for real X data]"

# ---------------------------------------------------------------------------
# Demo data — 3 seeded modes (embedded so the runner is offline-safe)
# ---------------------------------------------------------------------------

# Spam-burst core tokens shared across the 6-member burst in DEMO_FLOOD.
# Core set (6 tokens): present in all 6 burst DMs → pairwise Jaccard = 6/8 = 0.75 > 0.60.
_SPAM_CORE = ["dm", "crypto", "airdrop", "click", "link", "wallet"]

DEMO_FLOOD = {
    "x_handle": "@JanSol0s",
    "window_days": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "current_period": {
        "total_dms": 78,
        "urgent_count": 9,
        "opportunity_count": 28,
        "routine_count": 19,
        "spam_count": 22,
        "authentic_sender_count": 40,
    },
    "previous_period": {
        "total_dms": 58,
        "urgent_count": 8,
        "opportunity_count": 12,
        "routine_count": 20,
        "spam_count": 18,
        "authentic_sender_count": 44,
    },
    "dms": [
        # --- 6 genuine priority DMs (priority_score 59–96, Urgent/Opportunity) ---
        {
            "id": "d001", "bucket": "Opportunity", "priority_score": 96,
            "intent": "Verified brand sponsorship inquiry with concrete scope, deliverables, and a budget range",
            "sender_followers": 18400,
            "tokens": ["sponsorship", "brand", "scope", "budget", "deliverables"],
        },
        {
            "id": "d002", "bucket": "Urgent", "priority_score": 88,
            "intent": "Paying client asking for feedback on a contracted draft before tomorrow's deadline",
            "sender_followers": 4100,
            "tokens": ["client", "feedback", "draft", "deadline", "contracted"],
        },
        {
            "id": "d003", "bucket": "Opportunity", "priority_score": 80,
            "intent": "Podcast producer requesting a feature interview on the period's anchor thread",
            "sender_followers": 9300,
            "tokens": ["podcast", "feature", "interview", "anchor", "thread"],
        },
        {
            "id": "d004", "bucket": "Urgent", "priority_score": 73,
            "intent": "Existing collab partner needing an answer before the contract renewal date",
            "sender_followers": 2700,
            "tokens": ["collab", "partner", "renewal", "contract", "answer"],
        },
        {
            "id": "d005", "bucket": "Opportunity", "priority_score": 67,
            "intent": "Newsletter writer asking for citation permission for the habit-stacking thread",
            "sender_followers": 5800,
            "tokens": ["newsletter", "citation", "permission", "thread", "writer"],
        },
        {
            "id": "d006", "bucket": "Opportunity", "priority_score": 59,
            "intent": "Adjacent-niche creator proposing a thread swap on a shared topic",
            "sender_followers": 1900,
            "tokens": ["adjacent", "creator", "swap", "topic", "shared"],
        },
        # --- 6 spam-burst members (priority_score 54–87, all Spam bucket) ---
        # Core tokens present in all 6; one unique token per member keeps Jaccard = 0.75 per pair.
        {
            "id": "s001", "bucket": "Spam", "priority_score": 87,
            "intent": "Coordinated spam DM matching crypto-airdrop burst pattern",
            "sender_followers": 14,
            "tokens": _SPAM_CORE + ["bonus"],
        },
        {
            "id": "s002", "bucket": "Spam", "priority_score": 81,
            "intent": "Coordinated spam DM matching crypto-airdrop burst pattern",
            "sender_followers": 9,
            "tokens": _SPAM_CORE + ["instant"],
        },
        {
            "id": "s003", "bucket": "Spam", "priority_score": 74,
            "intent": "Coordinated spam DM matching crypto-airdrop burst pattern",
            "sender_followers": 6,
            "tokens": _SPAM_CORE + ["limited"],
        },
        {
            "id": "s004", "bucket": "Spam", "priority_score": 68,
            "intent": "Coordinated spam DM matching crypto-airdrop burst pattern",
            "sender_followers": 4,
            "tokens": _SPAM_CORE + ["winner"],
        },
        {
            "id": "s005", "bucket": "Spam", "priority_score": 61,
            "intent": "Coordinated spam DM matching crypto-airdrop burst pattern",
            "sender_followers": 7,
            "tokens": _SPAM_CORE + ["urgent"],
        },
        {
            "id": "s006", "bucket": "Spam", "priority_score": 54,
            "intent": "Coordinated spam DM matching crypto-airdrop burst pattern",
            "sender_followers": 3,
            "tokens": _SPAM_CORE + ["claim"],
        },
        # --- 6 lower-priority items (priority_score 12–42, mixed buckets) ---
        {
            "id": "d007", "bucket": "Routine", "priority_score": 42,
            "intent": "Casual peer check-in with no time-bound ask",
            "sender_followers": 480,
            "tokens": ["peer", "check", "casual"],
        },
        {
            "id": "d008", "bucket": "Routine", "priority_score": 36,
            "intent": "Friendly question about content publishing schedule",
            "sender_followers": 320,
            "tokens": ["schedule", "content", "publishing", "question"],
        },
        {
            "id": "d009", "bucket": "Urgent", "priority_score": 28,
            "intent": "Brand-mention concern that has already been self-resolved by another follower",
            "sender_followers": 210,
            "tokens": ["mention", "concern", "resolved", "follower"],
        },
        {
            "id": "d010", "bucket": "Routine", "priority_score": 22,
            "intent": "Brief fan message expressing appreciation for a recent thread",
            "sender_followers": 95,
            "tokens": ["fan", "appreciation", "thread", "brief"],
        },
        {
            "id": "d011", "bucket": "Spam", "priority_score": 18,
            "intent": "Low-context promotional pitch — independent of the coordinated burst",
            "sender_followers": 60,
            "tokens": ["pitch", "promo", "independent"],
        },
        {
            "id": "d012", "bucket": "Spam", "priority_score": 12,
            "intent": "Generic follow-back DM with no specific ask",
            "sender_followers": 45,
            "tokens": ["follow", "back", "generic"],
        },
    ],
}

DEMO_HEALTHY = {
    "x_handle": "@habitstacker",
    "window_days": 30,
    "compare_to": "previous_period",
    "data_source": "demo",
    "current_period": {
        "total_dms": 71,
        "urgent_count": 7,
        "opportunity_count": 21,
        "routine_count": 36,
        "spam_count": 7,
        "authentic_sender_count": 65,
    },
    "previous_period": {
        "total_dms": 58,
        "urgent_count": 6,
        "opportunity_count": 16,
        "routine_count": 30,
        "spam_count": 6,
        "authentic_sender_count": 53,
    },
    "dms": [
        {
            "id": "d001", "bucket": "Opportunity", "priority_score": 92,
            "intent": "Brand sponsorship inquiry from an established habit-coaching company with concrete scope",
            "sender_followers": 12300,
            "tokens": ["sponsorship", "brand", "habit", "scope", "established"],
        },
        {
            "id": "d002", "bucket": "Opportunity", "priority_score": 86,
            "intent": "Podcast producer asking to feature the creator in a deep-work episode",
            "sender_followers": 7600,
            "tokens": ["podcast", "feature", "deep", "work", "episode"],
        },
        {
            "id": "d003", "bucket": "Urgent", "priority_score": 78,
            "intent": "Existing collaborator asking for feedback on a draft before tomorrow's call",
            "sender_followers": 3400,
            "tokens": ["collaborator", "feedback", "draft", "call", "tomorrow"],
        },
        {
            "id": "d004", "bucket": "Opportunity", "priority_score": 70,
            "intent": "Newsletter writer requesting permission to cite the habit-stacking thread",
            "sender_followers": 5200,
            "tokens": ["newsletter", "permission", "cite", "habit", "stacking"],
        },
        {
            "id": "d005", "bucket": "Opportunity", "priority_score": 62,
            "intent": "Adjacent-niche creator proposing a thread swap on shared productivity topic",
            "sender_followers": 2100,
            "tokens": ["adjacent", "thread", "swap", "productivity", "creator"],
        },
        {
            "id": "d006", "bucket": "Urgent", "priority_score": 53,
            "intent": "Returning client asking to book the next monthly coaching slot",
            "sender_followers": 880,
            "tokens": ["client", "coaching", "monthly", "slot", "returning"],
        },
        {
            "id": "d007", "bucket": "Routine", "priority_score": 44,
            "intent": "Friendly fan question about which books inspired the evening-friction system",
            "sender_followers": 410,
            "tokens": ["fan", "books", "evening", "inspired", "system"],
        },
        {
            "id": "d008", "bucket": "Routine", "priority_score": 35,
            "intent": "Peer check-in with no time-bound ask",
            "sender_followers": 290,
            "tokens": ["peer", "check", "casual"],
        },
        {
            "id": "d009", "bucket": "Spam", "priority_score": 22,
            "intent": "Low-context promotional pitch — not part of any coordinated burst",
            "sender_followers": 70,
            "tokens": ["pitch", "promo", "independent"],
        },
        {
            "id": "d010", "bucket": "Routine", "priority_score": 18,
            "intent": "Brief one-line affirmation from a longtime follower",
            "sender_followers": 130,
            "tokens": ["affirmation", "follower", "brief"],
        },
    ],
}

DEMO_7D = {
    "x_handle": "@JanSol0s",
    "window_days": 7,
    "compare_to": "previous_period",
    "data_source": "demo",
    "current_period": {
        "total_dms": 28,
        "urgent_count": 4,
        "opportunity_count": 8,
        "routine_count": 11,
        "spam_count": 5,
        "authentic_sender_count": 18,
    },
    "previous_period": {
        "total_dms": 22,
        "urgent_count": 3,
        "opportunity_count": 5,
        "routine_count": 10,
        "spam_count": 4,
        "authentic_sender_count": 17,
    },
    "dms": [
        {
            "id": "d001", "bucket": "Opportunity", "priority_score": 87,
            "intent": "Niche peer asking to co-author a thread on a shared infrastructure topic",
            "sender_followers": 3200,
            "tokens": ["niche", "peer", "co-author", "thread", "infrastructure"],
        },
        {
            "id": "d002", "bucket": "Urgent", "priority_score": 76,
            "intent": "Existing client asking for feedback on a draft before publishing this week",
            "sender_followers": 1900,
            "tokens": ["client", "feedback", "draft", "publishing", "week"],
        },
        {
            "id": "d003", "bucket": "Opportunity", "priority_score": 64,
            "intent": "Adjacent-niche creator inquiring about a cross-platform collaboration",
            "sender_followers": 1500,
            "tokens": ["adjacent", "creator", "cross", "platform", "collaboration"],
        },
        {
            "id": "d004", "bucket": "Routine", "priority_score": 55,
            "intent": "Detailed question about how to structure a similar agent-eval workflow",
            "sender_followers": 720,
            "tokens": ["workflow", "structure", "agent", "eval", "question"],
        },
        {
            "id": "d005", "bucket": "Urgent", "priority_score": 47,
            "intent": "Brand-mention concern that has already been self-resolved",
            "sender_followers": 380,
            "tokens": ["mention", "concern", "resolved"],
        },
        {
            "id": "d006", "bucket": "Spam", "priority_score": 39,
            "intent": "Generic follow-back DM — independent, not part of any cluster",
            "sender_followers": 55,
            "tokens": ["follow", "back", "generic"],
        },
        {
            "id": "d007", "bucket": "Routine", "priority_score": 28,
            "intent": "Brief peer check-in with no time-bound ask",
            "sender_followers": 240,
            "tokens": ["peer", "check", "casual"],
        },
        {
            "id": "d008", "bucket": "Spam", "priority_score": 18,
            "intent": "Low-effort promotional pitch — not part of any coordinated burst",
            "sender_followers": 40,
            "tokens": ["promo", "pitch", "low"],
        },
    ],
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BucketAggregates:
    total: int
    urgent: int
    opportunity: int
    routine: int
    spam: int
    authentic: int


@dataclass
class TriageHealthMetrics:
    urgency_rate_pct: float
    opportunity_ratio_pct: float
    spam_pressure_pct: float
    authentic_share_pct: float
    # Previous period equivalents for trend arrows
    prev_urgency_rate_pct: float
    prev_opportunity_ratio_pct: float
    prev_spam_pressure_pct: float
    prev_authentic_share_pct: float


@dataclass
class TriageHealthScores:
    urgency_rate_pct: float
    opportunity_ratio_pct: float
    spam_pressure_pct: float
    authentic_share_pct: float
    urgency_arrow: str
    opportunity_arrow: str
    spam_arrow: str
    authentic_arrow: str
    health_score: int
    paradox_active: bool
    interpretations: dict = field(default_factory=dict)


@dataclass
class ActionItem:
    id: str
    bucket: str
    intent: str
    priority_score: int
    is_demo: bool


@dataclass
class SpamBurst:
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


def load_dms_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"--dms-file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--dms-file is not valid JSON: {exc}") from exc


def parse_aggregates(period: dict) -> BucketAggregates:
    return BucketAggregates(
        total=int(period["total_dms"]),
        urgent=int(period["urgent_count"]),
        opportunity=int(period["opportunity_count"]),
        routine=int(period["routine_count"]),
        spam=int(period["spam_count"]),
        authentic=int(period["authentic_sender_count"]),
    )


# ---------------------------------------------------------------------------
# Spam-burst detection (Jaccard similarity on token sets, Spam bucket only)
# ---------------------------------------------------------------------------


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union > 0 else 0.0


def detect_spam_bursts(dms: list[dict]) -> list[SpamBurst]:
    """Return clusters of >=5 Spam-bucket DMs with >60% pairwise Jaccard overlap."""
    spams = [d for d in dms if d.get("bucket") == "Spam"]
    if len(spams) < BURST_MIN_CLUSTER_SIZE:
        return []

    token_sets = [set(d.get("tokens", [])) for d in spams]
    n = len(spams)

    # Build adjacency matrix: edge when Jaccard > threshold
    adj: list[list[bool]] = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(token_sets[i], token_sets[j]) > BURST_JACCARD_THRESHOLD:
                adj[i][j] = adj[j][i] = True

    # BFS to find connected components of size >= BURST_MIN_CLUSTER_SIZE
    visited = [False] * n
    bursts: list[SpamBurst] = []
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
        if len(component) >= BURST_MIN_CLUSTER_SIZE:
            bursts.append(SpamBurst(
                member_ids=[spams[i]["id"] for i in component],
                size=len(component),
            ))

    return bursts


# ---------------------------------------------------------------------------
# Action queue building
# ---------------------------------------------------------------------------


def build_action_queue(
    dms: list[dict],
    burst_member_ids: set[str],
    is_demo: bool,
) -> list[ActionItem]:
    """Return up to MAX_ACTION_QUEUE DMs sorted by priority_score desc,
    with spam-burst members excluded."""
    eligible = [
        d for d in dms
        if d["id"] not in burst_member_ids
        and int(d.get("priority_score", 0)) >= PRIORITY_SCORE_THRESHOLD
    ]
    eligible.sort(key=lambda d: int(d.get("priority_score", 0)), reverse=True)
    queue: list[ActionItem] = []
    for d in eligible[:MAX_ACTION_QUEUE]:
        queue.append(ActionItem(
            id=d["id"],
            bucket=str(d.get("bucket", "Routine")),
            intent=str(d.get("intent", "(paraphrased DM)")),
            priority_score=int(d.get("priority_score", 0)),
            is_demo=is_demo,
        ))
    return queue


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_health_metrics(payload: dict) -> TriageHealthMetrics:
    cur = parse_aggregates(payload["current_period"])
    prev = parse_aggregates(payload["previous_period"])

    cur_total = max(cur.total, 1)
    prev_total = max(prev.total, 1)

    urgency_rate_pct      = cur.urgent       / cur_total * 100.0
    opportunity_ratio_pct = cur.opportunity  / cur_total * 100.0
    spam_pressure_pct     = cur.spam         / cur_total * 100.0
    authentic_share_pct   = cur.authentic    / cur_total * 100.0

    prev_urgency_rate_pct      = prev.urgent       / prev_total * 100.0
    prev_opportunity_ratio_pct = prev.opportunity  / prev_total * 100.0
    prev_spam_pressure_pct     = prev.spam         / prev_total * 100.0
    prev_authentic_share_pct   = prev.authentic    / prev_total * 100.0

    return TriageHealthMetrics(
        urgency_rate_pct=urgency_rate_pct,
        opportunity_ratio_pct=opportunity_ratio_pct,
        spam_pressure_pct=spam_pressure_pct,
        authentic_share_pct=authentic_share_pct,
        prev_urgency_rate_pct=prev_urgency_rate_pct,
        prev_opportunity_ratio_pct=prev_opportunity_ratio_pct,
        prev_spam_pressure_pct=prev_spam_pressure_pct,
        prev_authentic_share_pct=prev_authentic_share_pct,
    )


# ---------------------------------------------------------------------------
# Normalisation + scoring
# ---------------------------------------------------------------------------


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def _urgency_band_norm(pct: float) -> float:
    """Inverse-U: full marks inside [5, 25], linear decay over a 25-pt skirt either side."""
    lo, hi = HEALTHY_RANGES["Triage urgency rate"]
    if lo <= pct <= hi:
        return 100.0
    if pct < lo:
        return max(0.0, 100.0 - (lo - pct) * 4.0)
    return max(0.0, 100.0 - (pct - hi) * 4.0)


def _spam_inv_norm(pct: float) -> float:
    """Inverted: 0% spam → 100, 25%+ spam → 0."""
    lo, hi = HEALTHY_RANGES["Spam pressure"]
    if pct <= lo:
        return 100.0
    if pct >= hi:
        return 0.0
    return 100.0 * (1.0 - (pct - lo) / (hi - lo))


def _pct_arrow(delta_pct: float) -> str:
    """Standard ±5% / ±25% thresholds for relative-change comparisons."""
    if delta_pct >= 25.0:
        return "▲▲"
    if delta_pct >= 5.0:
        return "▲"
    if delta_pct >= -5.0:
        return "▬"
    if delta_pct >= -25.0:
        return "▼"
    return "▼▼"


def _spam_arrow(delta_pct: float) -> str:
    """Spam pressure arrow inverts: a fall in spam reads as health-improving."""
    return _pct_arrow(-delta_pct)


def score_health(
    m: TriageHealthMetrics,
    authenticity_floor: float,
) -> TriageHealthScores:
    norm_authentic = _norm(
        m.authentic_share_pct,
        HEALTHY_RANGES["Authentic sender share"][0],
        HEALTHY_RANGES["Authentic sender share"][1],
    )
    norm_opportunity = _norm(
        m.opportunity_ratio_pct,
        HEALTHY_RANGES["Opportunity ratio"][0],
        HEALTHY_RANGES["Opportunity ratio"][1],
    )
    norm_spam_inv = _spam_inv_norm(m.spam_pressure_pct)
    norm_urgency = _urgency_band_norm(m.urgency_rate_pct)

    health_score = round(
        HEALTH_WEIGHTS["Authentic sender share"] * norm_authentic
        + HEALTH_WEIGHTS["Opportunity ratio"]    * norm_opportunity
        + HEALTH_WEIGHTS["Spam pressure"]        * norm_spam_inv
        + HEALTH_WEIGHTS["Triage urgency rate"]  * norm_urgency
    )

    # Trend arrows (relative-change deltas vs previous period)
    def _rel_delta(cur: float, prev: float) -> float:
        return (cur - prev) / max(prev, 0.01) * 100.0

    urgency_arrow     = _pct_arrow(_rel_delta(m.urgency_rate_pct, m.prev_urgency_rate_pct))
    opportunity_arrow = _pct_arrow(_rel_delta(m.opportunity_ratio_pct, m.prev_opportunity_ratio_pct))
    spam_arrow        = _spam_arrow(_rel_delta(m.spam_pressure_pct, m.prev_spam_pressure_pct))
    authentic_arrow   = _pct_arrow(_rel_delta(m.authentic_share_pct, m.prev_authentic_share_pct))

    paradox = (
        m.opportunity_ratio_pct > PARADOX_OPPORTUNITY_THRESHOLD
        and m.authentic_share_pct < authenticity_floor
    )

    return TriageHealthScores(
        urgency_rate_pct=m.urgency_rate_pct,
        opportunity_ratio_pct=m.opportunity_ratio_pct,
        spam_pressure_pct=m.spam_pressure_pct,
        authentic_share_pct=m.authentic_share_pct,
        urgency_arrow=urgency_arrow,
        opportunity_arrow=opportunity_arrow,
        spam_arrow=spam_arrow,
        authentic_arrow=authentic_arrow,
        health_score=health_score,
        paradox_active=paradox,
        interpretations=_build_interpretations(m, authenticity_floor),
    )


def _build_interpretations(m: TriageHealthMetrics, floor: float) -> dict:
    out: dict[str, str] = {}

    # Triage urgency rate
    if 5.0 <= m.urgency_rate_pct <= 25.0:
        out["Triage urgency rate"] = (
            "Inside the healthy band; urgent items are present but not drowning the inbox."
        )
    elif m.urgency_rate_pct < 5.0:
        out["Triage urgency rate"] = (
            "Below the healthy floor; either inbox is quiet or genuinely urgent items are being mis-bucketed."
        )
    elif m.urgency_rate_pct <= 35.0:
        out["Triage urgency rate"] = (
            "Above the healthy band; inbox is signalling overload — protect focus blocks before scaling cadence."
        )
    else:
        out["Triage urgency rate"] = (
            "Far above the healthy band; check whether manufactured-urgency tactics are inflating the bucket."
        )

    # Opportunity ratio
    if m.opportunity_ratio_pct > PARADOX_OPPORTUNITY_THRESHOLD:
        out["Opportunity ratio"] = (
            "Elevated — verify whether senders are authentic before treating as real inbound."
        )
    elif m.opportunity_ratio_pct >= 10.0:
        out["Opportunity ratio"] = (
            "Inside the healthy band; opportunity inflow supports continued outbound visibility."
        )
    else:
        out["Opportunity ratio"] = (
            "Below the healthy floor; inbound opportunity volume is thin — review surface visibility."
        )

    # Spam pressure
    if m.spam_pressure_pct >= 25.0:
        out["Spam pressure"] = (
            "Above the healthy ceiling; coordinated spam burst inflates this number — see Red Flags."
        )
    elif m.spam_pressure_pct >= 10.0:
        out["Spam pressure"] = (
            "Moderate spam volume; manageable with standard inbox hygiene."
        )
    else:
        out["Spam pressure"] = "Low spam pressure; inbox signal-to-noise is healthy."

    # Authentic sender share
    if m.authentic_share_pct >= 90.0:
        out["Authentic sender share"] = "Excellent authentic signal; sender-quality floor is high."
    elif m.authentic_share_pct >= 75.0:
        out["Authentic sender share"] = (
            "Majority of DMs from established senders; sender-quality stable."
        )
    elif m.authentic_share_pct >= floor:
        out["Authentic sender share"] = (
            f"Above the {floor:.0f}% floor; borderline — audit sender quality if the share keeps falling."
        )
    else:
        out["Authentic sender share"] = (
            f"Below the {floor:.0f}% floor; combined with elevated Opportunity ratio triggers the opportunity-flood paradox."
        )

    return out


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def build_red_flags(
    scores: TriageHealthScores,
    bursts: list[SpamBurst],
    window: int,
    authenticity_floor: float,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # Rule 1: Opportunity-flood paradox
    if scores.paradox_active:
        flags.append(RedFlag(
            title="Opportunity-flood paradox",
            severity="high",
            explanation=(
                f"Opportunity ratio at {scores.opportunity_ratio_pct:.1f}% sits above the "
                f"+{int(PARADOX_OPPORTUNITY_THRESHOLD)}% threshold while Authentic sender share at "
                f"{scores.authentic_share_pct:.1f}% is below the {authenticity_floor:.0f}% floor. "
                "Opportunities are arriving in volume but most senders have low authenticity — "
                "likely a cold-outreach campaign masquerading as opportunity."
            ),
            remediation=(
                "Tighten the inbound filter for the next window (verified-only DMs, or higher follower floor) "
                "before treating opportunity volume as real inbound; if the gap persists, accept the period as "
                "a noise event and retarget for authentic-only opportunity volume."
            ),
        ))

    # Rule 2: Spam-burst guard
    for burst in bursts:
        flags.append(RedFlag(
            title="Coordinated spam burst",
            severity="high",
            explanation=(
                f"{burst.size} Spam-bucket DMs share >60% pairwise token overlap — "
                "evidence of a coordinated outreach burst rather than independent spam. "
                "All burst members excluded from the suggested-action queue."
            ),
            remediation=(
                "Do not engage with burst members individually; replying or reporting one-by-one amplifies the "
                "signal. If X exposes a bulk-report tool, queue them for one batched report rather than per-DM "
                "action; otherwise tighten the inbound filter to verified-only for the next window."
            ),
        ))

    # Rule 3: 7-day single-day variance
    if window == 7:
        flags.append(RedFlag(
            title="Single-day variance exposure",
            severity="medium",
            explanation=(
                "A 7d DM window is dominated by single-day variance; one viral post or "
                "one quiet day can flip every trend arrow."
            ),
            remediation=(
                "Re-run with --window 30 once 14+ more days have passed before declaring directional reads."
            ),
        ))

    # Rule 4: Low authentic sender share watch
    if scores.authentic_share_pct < 65.0 and not scores.paradox_active:
        flags.append(RedFlag(
            title="Low authentic sender share",
            severity="medium",
            explanation=(
                f"Authentic sender share at {scores.authentic_share_pct:.1f}% is below the 65% watch "
                "threshold; a meaningful portion of this period's DMs may be bot or low-quality accounts."
            ),
            remediation=(
                "Pair with `follower-quality-analyzer` to audit the sender cohort before acting on any "
                "opportunity signal."
            ),
        ))

    # Rule 5: Near-flood watch (opportunity rising while authenticity slipping but paradox not yet active)
    if (
        not scores.paradox_active
        and scores.opportunity_ratio_pct > 25.0
        and scores.authentic_share_pct < 70.0
    ):
        flags.append(RedFlag(
            title="Near-flood watch",
            severity="low",
            explanation=(
                f"Opportunity ratio at {scores.opportunity_ratio_pct:.1f}% is approaching the "
                f"+{int(PARADOX_OPPORTUNITY_THRESHOLD)}% paradox threshold while Authentic sender share at "
                f"{scores.authentic_share_pct:.1f}% is already drifting toward the {authenticity_floor:.0f}% "
                "floor — one more low-authenticity inbound window could trigger the opportunity-flood paradox."
            ),
            remediation=(
                "Run `mention-summarizer` to confirm whether the same low-authenticity pattern is showing in "
                "public mentions — divergence here is an early-warning signal."
            ),
        ))

    # Defensive top-up: always emit at least 2 flags
    if len(flags) < 2:
        flags.append(RedFlag(
            title="Single-period read",
            severity="low",
            explanation=(
                "One DM window is directional, not conclusive. "
                "Treat the Triage Health score as a snapshot, not a trend."
            ),
            remediation=(
                "Re-run monthly to build a baseline of trend arrows across consecutive windows."
            ),
        ))

    return flags[:4]


# ---------------------------------------------------------------------------
# Recommendations (mandatory: reply-drafter + mention-summarizer always first)
# ---------------------------------------------------------------------------


def build_recommendations(
    rng: Random,
    scores: TriageHealthScores,
    action_queue: list[ActionItem],
    bursts: list[SpamBurst],
    window: int,
) -> list[Recommendation]:
    queue_count = len(action_queue)

    # Mandatory position 1: reply-drafter
    if scores.paradox_active:
        reply_text = (
            f"Work through the {queue_count}-DM action queue Urgent items first; "
            "treat every Opportunity entry as unverified until sender authenticity is confirmed."
        )
    else:
        reply_text = (
            f"Work through the {queue_count}-DM action queue in sequence; "
            "voice-faithful replies only, no engagement bait."
        )
    mandatory_reply = Recommendation(text=reply_text, bridge_slug="reply-drafter")

    # Mandatory position 2: mention-summarizer
    if scores.paradox_active or bursts:
        mention_text = (
            "Cross-reference this DM window against the same period's mention summary to confirm "
            "whether the low-authenticity pattern shows up in public mentions or only in DMs."
        )
    else:
        mention_text = (
            "Cross-reference this DM window against the period's mention summary to confirm whether "
            "DM patterns mirror the public mention signal."
        )
    mandatory_mention = Recommendation(text=mention_text, bridge_slug="mention-summarizer")

    # Optional pool (shuffled)
    optional_pool: list[Recommendation] = []

    if bursts:
        optional_pool.append(Recommendation(
            text=(
                "Do not engage with the coordinated spam burst individually; if X exposes a bulk-report "
                "tool, queue burst members for one batched action rather than per-DM."
            ),
            bridge_slug="reply-drafter",
        ))

    if scores.paradox_active or scores.authentic_share_pct < 70.0:
        optional_pool.append(Recommendation(
            text=(
                "Audit the sender cohort that drove the Opportunity bucket — cold-outreach campaigns "
                "produce volume without genuine inbound intent."
            ),
            bridge_slug="follower-quality-analyzer",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Compare this DM window against competitor DM patterns to confirm the signal is specific "
            "to this creator's surface, not a niche-wide outreach trend."
        ),
        bridge_slug="competitor-watch",
    ))

    if scores.opportunity_ratio_pct >= 20.0 and not scores.paradox_active and queue_count > 0:
        optional_pool.append(Recommendation(
            text=(
                "Re-source the next anchor post in the cluster that drove genuine Opportunity DMs; "
                "the inbox is signalling which content type the right audience values."
            ),
            bridge_slug="content-idea-generator",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Correlate the bucket mix with the period's impression and engagement metrics to confirm "
            "DM volume tracks reach, not just visibility spikes."
        ),
        bridge_slug="analytics-summarizer",
    ))

    if scores.opportunity_ratio_pct >= 20.0 and not scores.paradox_active:
        optional_pool.append(Recommendation(
            text=(
                "A/B test the inbound-prompt CTA that drove the highest-quality Opportunity DMs to "
                "confirm the format lifts authentic inbound, not just total volume."
            ),
            bridge_slug="ab-test-suggester",
        ))

    optional_pool.append(Recommendation(
        text=(
            "Audit the brand voice used in the Routine-bucket replies to confirm the tone is "
            "consistent with the public-content voice the creator wants to scale."
        ),
        bridge_slug="brand-voice-trainer",
    ))

    # Shuffle optional pool with seeded RNG
    rng.shuffle(optional_pool)

    # De-duplicate bridge slugs (avoid two reply-drafter recs from optional)
    seen_optional: set[str] = {"reply-drafter", "mention-summarizer"}
    deduped: list[Recommendation] = []
    for rec in optional_pool:
        if rec.bridge_slug not in seen_optional:
            deduped.append(rec)
            seen_optional.add(rec.bridge_slug)

    result = [mandatory_reply, mandatory_mention] + deduped[:3]
    return result[:5]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def build_confidence(
    scores: TriageHealthScores,
    bursts: list[SpamBurst],
    window: int,
    is_demo: bool,
) -> tuple[str, str]:
    if is_demo:
        return (
            "low",
            "data source is seeded demo DMs — re-run with --dms-file pointing at the actual X DM "
            "export to lift confidence.",
        )
    if window == 30 and scores.health_score >= 65 and not bursts:
        return (
            "high",
            f"30d window covers the main signals; Triage Health score {scores.health_score}/100 "
            "with no spam-burst interference.",
        )
    if scores.health_score >= 50:
        return (
            "medium",
            f"Triage Health score {scores.health_score}/100; widen the window or supply richer DM data "
            "to lift to high.",
        )
    return (
        "low",
        f"Triage Health score {scores.health_score}/100; investigate the falling metrics and "
        "spam-burst interference before declaring a trend.",
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _demo_tag(is_demo: bool) -> str:
    return f" {DEMO_LABEL}" if is_demo else ""


def _render_snapshot(payload: dict, scores: TriageHealthScores, is_demo: bool) -> str:
    handle = normalize_handle(payload["x_handle"])
    window = int(payload["window_days"])
    compare = payload.get("compare_to", "previous_period")

    if scores.paradox_active:
        headline = (
            f"{handle}: {window}d DM window — opportunity-flood paradox active; "
            f"Opportunity ratio {scores.opportunity_ratio_pct:.1f}% but Authentic sender share is only "
            f"{scores.authentic_share_pct:.1f}%."
        )
    elif scores.health_score >= 70:
        headline = (
            f"{handle}: {window}d DM window — healthy inbox signal "
            f"(Triage Health {scores.health_score}/100)."
        )
    elif scores.health_score >= 50:
        headline = (
            f"{handle}: {window}d DM window — directional period "
            f"(Triage Health {scores.health_score}/100); monitor sender authenticity."
        )
    else:
        headline = (
            f"{handle}: {window}d DM window — weak period "
            f"(Triage Health {scores.health_score}/100); investigate the falling metrics before scaling."
        )

    data_line = (
        "seeded demo DMs — re-run with --dms-file for real X data"
        if is_demo
        else "real X DM export from --dms-file"
    )

    return "\n".join([
        "## Triage Snapshot",
        f"**{headline}**",
        "",
        f"- **Creator handle**: {handle}",
        f"- **Window**: {window}d",
        f"- **Comparison basis**: {compare}",
        f"- **Data source**: {data_line}",
    ])


def _render_triage_health(
    scores: TriageHealthScores, is_demo: bool, bursts: list[SpamBurst],
) -> str:
    dt = _demo_tag(is_demo)
    spam_interp = scores.interpretations["Spam pressure"]
    if bursts:
        burst_total = sum(b.size for b in bursts)
        spam_interp = (
            f"Above the healthy ceiling; coordinated spam burst ({burst_total} DMs) inflates this number — see Red Flags."
        )

    rows = [
        "| Metric | Value | Trend | Interpretation |",
        "|---|---|---|---|",
        (
            f"| Triage urgency rate    | {scores.urgency_rate_pct:.1f}%{dt} | "
            f"{scores.urgency_arrow} | {scores.interpretations['Triage urgency rate']} |"
        ),
        (
            f"| Opportunity ratio      | {scores.opportunity_ratio_pct:.1f}%{dt} | "
            f"{scores.opportunity_arrow} | {scores.interpretations['Opportunity ratio']} |"
        ),
        (
            f"| Spam pressure          | {scores.spam_pressure_pct:.1f}%{dt} | "
            f"{scores.spam_arrow} | {spam_interp} |"
        ),
        (
            f"| Authentic sender share | {scores.authentic_share_pct:.1f}%{dt} | "
            f"{scores.authentic_arrow} | {scores.interpretations['Authentic sender share']} |"
        ),
    ]
    out = "## Triage Health\n\n" + "\n".join(rows)
    if scores.paradox_active:
        out += (
            "\n\n> ⚠️ paradox: opportunities are arriving in volume but most senders have low "
            "authenticity — likely a cold-outreach campaign masquerading as opportunity, not real inbound."
        )
    out += f"\n\n**Triage Health score**: {scores.health_score}/100"
    return out


def _render_bucket_breakdown(
    payload: dict,
    is_demo: bool,
    bursts: list[SpamBurst],
) -> str:
    cur = parse_aggregates(payload["current_period"])
    dt = _demo_tag(is_demo)
    total = max(cur.total, 1)
    urg_pct = cur.urgent      / total * 100.0
    opp_pct = cur.opportunity / total * 100.0
    rou_pct = cur.routine     / total * 100.0
    spm_pct = cur.spam        / total * 100.0

    rows = [
        "| Bucket      | Count | Share  |",
        "|---|---|---|",
        f"| Urgent      | {cur.urgent}{dt}      | {urg_pct:.1f}% |",
        f"| Opportunity | {cur.opportunity}{dt} | {opp_pct:.1f}% |",
        f"| Routine     | {cur.routine}{dt}     | {rou_pct:.1f}% |",
        f"| Spam        | {cur.spam}{dt}        | {spm_pct:.1f}% |",
    ]

    if bursts and spm_pct > 20.0:
        burst_total = sum(b.size for b in bursts)
        note = (
            f"Spam bucket dominates the lower half of the inbox. The coordinated burst "
            f"({burst_total} DMs) inflates the Spam count — see Red Flags."
        )
    elif opp_pct > rou_pct and opp_pct >= 30.0:
        note = (
            "Opportunity bucket leads — verify sender authenticity before scaling outbound visibility."
        )
    elif rou_pct >= 50.0:
        note = (
            "Routine bucket dominates; the inbox is mostly community engagement rather than action items."
        )
    elif urg_pct >= 25.0:
        note = (
            "Urgent bucket is heavy this window — protect a daily focus block to clear the queue."
        )
    else:
        note = "Buckets are roughly balanced; no single bucket dominates the period."

    return "## Bucket Breakdown\n\n" + "\n".join(rows) + "\n\n" + note


def _render_action_queue(
    queue: list[ActionItem],
    total_priority_count: int,
    bursts: list[SpamBurst],
    is_demo: bool,
) -> str:
    burst_total = sum(b.size for b in bursts)
    dt = _demo_tag(is_demo)

    if burst_total > 0:
        header = (
            f"## Suggested Actions "
            f"({len(queue)} of {total_priority_count} priority DMs — "
            f"{burst_total} spam-burst DMs excluded)"
        )
    else:
        header = f"## Suggested Actions ({len(queue)} priority DMs)"

    if not queue:
        return header + "\n\n_(no priority DMs above the threshold after spam-burst filter)_"

    lines = [header, ""]
    for i, item in enumerate(queue, start=1):
        score_label = f"priority {item.priority_score}{dt}"
        lines.append(
            f"{i}. **{item.intent}** ({item.bucket} · {score_label}) — bridges to: `reply-drafter`"
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


def _render_dm_audit(
    payload: dict,
    bursts: list[SpamBurst],
    is_demo: bool,
) -> str:
    window = int(payload["window_days"])
    window_line = (
        "7d window is dominated by single-day variance; treat all reads as directional."
        if window == 7
        else f"{window}d window is sufficient for the bucket patterns surfaced."
    )
    data_line = (
        "seeded demo placeholders — runner cannot speak to real-creator confidence until "
        "--dms-file is supplied."
        if is_demo
        else "real DM export loaded; no missing-field gaps detected."
    )
    burst_total = sum(b.size for b in bursts)
    if burst_total > 0:
        burst_line = (
            f"{burst_total} spam-burst DMs removed from the action queue; "
            "Spam bucket share is inflated by the burst."
        )
        next_sample = (
            "re-run in 30 days to determine whether the burst is a recurring outreach campaign or a one-off event."
        )
    else:
        burst_line = "none detected — Spam bucket reflects independent low-context outreach."
        next_sample = (
            "re-run when 14+ more days have passed; widen to 30d if currently on 7d."
            if window == 7
            else "re-run in 30 days to build consecutive-window trend data."
        )

    return "\n".join([
        "## DM Audit (auto-triggered)",
        "",
        f"- **Window adequacy**: {window_line}",
        f"- **Data source confidence**: {data_line}",
        f"- **Spam-burst impact**: {burst_line}",
        f"- **Suggested next sample**: {next_sample}",
        "- **Re-run cadence**: weekly during active outreach campaigns, otherwise monthly.",
    ])


def render_report(
    payload: dict,
    scores: TriageHealthScores,
    action_queue: list[ActionItem],
    total_priority_count: int,
    bursts: list[SpamBurst],
    flags: list[RedFlag],
    recs: list[Recommendation],
    confidence: tuple[str, str],
    is_demo: bool,
) -> str:
    sections = [
        _render_snapshot(payload, scores, is_demo),
        "",
        _render_triage_health(scores, is_demo, bursts),
        "",
        _render_bucket_breakdown(payload, is_demo, bursts),
        "",
        _render_action_queue(action_queue, total_priority_count, bursts, is_demo),
        "",
        _render_red_flags(flags),
        "",
        _render_recommendations(recs),
        "",
        "## Confidence",
        f"Confidence: {confidence[0]} — {confidence[1]}",
    ]

    audit_trigger = bool(bursts) or int(payload["window_days"]) == 7
    if audit_trigger:
        sections.extend([
            "",
            _render_dm_audit(payload, bursts, is_demo),
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
        f"<!-- Generated by DM Triager (Grok Agent OS) for {handle} at {when_iso} -->\n"
        "<!-- Drafts only — DM content stays on your machine. Built for X, Grok & the ecosystem community. -->\n\n"
    )


# ---------------------------------------------------------------------------
# Public entry — manifest binds to this via `function: generate`
# ---------------------------------------------------------------------------


def generate_dm_triage(
    *,
    x_handle: str,
    dms_file: Optional[str] = None,
    window: int = 30,
    compare_to: str = "previous_period",
    opportunity_authenticity_floor: float = DEFAULT_AUTHENTICITY_FLOOR,
    demo_mode: Optional[str] = None,
) -> str:
    handle = normalize_handle(x_handle)
    if window not in WINDOW_OPTIONS:
        raise ValueError(f"window must be one of {WINDOW_OPTIONS}, got {window!r}")
    if compare_to not in COMPARE_OPTIONS:
        raise ValueError(f"compare_to must be one of {COMPARE_OPTIONS}, got {compare_to!r}")

    if dms_file:
        payload = load_dms_file(Path(dms_file).expanduser().resolve())
        is_demo = bool(payload.get("data_source") == "demo")
    elif demo_mode == "flood":
        payload = json.loads(json.dumps(DEMO_FLOOD))
        is_demo = True
    elif demo_mode == "healthy":
        payload = json.loads(json.dumps(DEMO_HEALTHY))
        is_demo = True
    elif demo_mode == "7d":
        payload = json.loads(json.dumps(DEMO_7D))
        is_demo = True
    else:
        raise ValueError(
            "Provide --dms-file <path> or one of --demo / --demo-healthy / --demo-7d."
        )

    # CLI flags override payload meta
    payload["x_handle"] = handle
    payload["window_days"] = window
    payload["compare_to"] = compare_to

    dms_list = payload.get("dms", [])

    # Spam-burst detection (Spam bucket only)
    bursts = detect_spam_bursts(dms_list)
    burst_member_ids: set[str] = {
        bid for b in bursts for bid in b.member_ids
    }

    # Suggested-action queue (spam-burst members excluded)
    action_queue = build_action_queue(dms_list, burst_member_ids, is_demo)

    # Total priority count before burst filter (for queue header label)
    total_priority_count = sum(
        1 for d in dms_list
        if int(d.get("priority_score", 0)) >= PRIORITY_SCORE_THRESHOLD
    )

    # Metrics and scoring
    health_metrics = compute_health_metrics(payload)
    scores = score_health(health_metrics, opportunity_authenticity_floor)

    # Seeded RNG: sha256(handle + sorted-json + window); date excluded for reproducibility
    seed_str = handle + json.dumps(payload, sort_keys=True) + str(window)
    seed = hashlib.sha256(seed_str.encode("utf-8")).digest()[:8]
    rng = Random(int.from_bytes(seed, "big"))

    flags = build_red_flags(scores, bursts, window, opportunity_authenticity_floor)
    recs = build_recommendations(rng, scores, action_queue, bursts, window)
    confidence = build_confidence(scores, bursts, window, is_demo)

    return render_report(
        payload, scores, action_queue, total_priority_count,
        bursts, flags, recs, confidence, is_demo,
    )


generate = generate_dm_triage


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def banner() -> str:
    return (
        "============================================================\n"
        "  DM Triager (Grok Agent OS · creator template)\n"
        "  Drafts only · Local-first · DM content stays on your machine\n"
        "  Built for X, Grok & the ecosystem community.\n"
        "============================================================\n"
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dm-triager",
        description=(
            "Read creator-supplied X DM data (or seeded demo DMs) and emit a 7/8-section "
            "DM triage report with 4 canonical Triage Health metrics, opportunity-flood "
            "paradox detection, 4-bucket distribution (Urgent / Opportunity / Routine / "
            "Spam), suggested-action queue (max 6) with spam-burst guard, and mandatory "
            "bridges to reply-drafter + mention-summarizer. Drafts only. DM content "
            "never leaves your local Windows machine."
        ),
    )
    p.add_argument(
        "--handle", required=True,
        help="The creator's X handle (with or without leading @).",
    )
    p.add_argument(
        "--dms-file",
        help="Path to a JSON DM export. Required unless a --demo flag is passed.",
    )
    p.add_argument(
        "--days", "--window", dest="window", type=int, choices=list(WINDOW_OPTIONS),
        default=30,
        help="Period window in days (7, 30, or 90). 7d auto-triggers DM Audit. Default 30.",
    )
    p.add_argument(
        "--compare-to", choices=list(COMPARE_OPTIONS), default="previous_period",
        help="Comparison basis for trend arrows. Default previous_period.",
    )
    p.add_argument(
        "--opportunity-authenticity-floor", type=float, default=DEFAULT_AUTHENTICITY_FLOOR,
        help=(
            f"Authentic sender share threshold below which the opportunity-flood paradox fires "
            f"when Opportunity ratio > 30%% (default {DEFAULT_AUTHENTICITY_FLOOR})."
        ),
    )
    p.add_argument("--output", help="Optional path to save the rendered report.")
    p.add_argument("--no-banner", action="store_true", help="Suppress the runner banner on stdout.")
    p.add_argument(
        "--demo", action="store_true",
        help="Run with the canonical opportunity-flood paradox + spam-burst demo DMs.",
    )
    p.add_argument(
        "--demo-healthy", action="store_true",
        help="Run with healthy inbox demo DMs (no paradox, no burst).",
    )
    p.add_argument(
        "--demo-7d", action="store_true",
        help="Run with 7-day window demo DMs (auto-triggers DM Audit).",
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
        demo_mode = "flood"
    elif args.demo_healthy:
        demo_mode = "healthy"
    elif args.demo_7d:
        demo_mode = "7d"

    if not args.dms_file and demo_mode is None:
        sys.stderr.write(
            "error: provide --dms-file <path> or one of --demo / --demo-healthy / --demo-7d.\n"
        )
        return 2

    rendered = generate_dm_triage(
        x_handle=args.handle,
        dms_file=args.dms_file,
        window=args.window,
        compare_to=args.compare_to,
        opportunity_authenticity_floor=args.opportunity_authenticity_floor,
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
