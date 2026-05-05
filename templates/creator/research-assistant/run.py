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
Research Assistant -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships niche-aware offline research
corpora (multi-source topic packs with pre-flagged contradictions and analyst
inferences) so creators get value the instant `grok install this` finishes.
To wire to live Grok 4.3, replace the body of `generate_research_summary()`
with a Grok call that consumes `prompts/system.md` (auto-loaded) and returns
the same schema with proper [src N] citation discipline.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --query "long-context vs RAG"
    python run.py --x-handle @creator --query "single-tab focus" --depth deep
    python run.py --x-handle @me --query "tax automation" --sources academic --output today.md
    python run.py --x-handle @test --query "long-context vs RAG" --depth deep
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
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
    f"  RESEARCH ASSISTANT  v{VERSION}\n"
    "  Citations-first creator research, in 60 seconds.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

# ---------------------------------------------------------------------------
# Static research corpora -- offline, zero-dep, niche-aware.
# Replace `generate_research_summary()` body with a Grok 4.3 call to upgrade.
# ---------------------------------------------------------------------------

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp", "long-context", "context")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings", "tax", "payout")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual", "pomodoro")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2", "zone")),
]
DEFAULT_BUCKET = "general"

ACTION_LABELS = ("weak", "moderate", "strong")
SOURCE_LABEL_ENUM = ("x", "news", "academic", "gov", "evergreen", "analyst")

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading", "earnings",
    "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
    "x money", "payout",
)

# Each topic has: keywords (for query matching), sources (4-5),
# contradictions (1-2), analyst_inference, default_next_step_focus.
RESEARCH_CORPUS_BY_BUCKET: Dict[str, Dict[str, Dict[str, Any]]] = {
    "ai": {
        "long-context vs RAG": {
            "keywords": ("long-context", "long context", "rag", "retrieval", "context window"),
            "default_query": "What's the strongest evidence that long-context models reduce the need for RAG?",
            "sources": [
                {"shorthand": "@kai_ai long-context thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Long-context wins on summarization and meeting-style tasks where the entire context can be loaded once"},
                {"shorthand": "\"long-context wars heat up\" (news)", "label": "news", "strength": "weak",
                 "claim": "Vendor benchmark claims show long-context outperforming RAG by wide margins"},
                {"shorthand": "RAG-vs-long-context preprint (academic)", "label": "academic", "strength": "strong",
                 "claim": "RAG still outperforms long-context on retrieval-heavy QA where the answer lives in a small slice of a large corpus"},
                {"shorthand": "enterprise AI adoption report (gov)", "label": "gov", "strength": "moderate",
                 "claim": "Enterprise adoption is mixed -- 38% of surveyed teams ship long-context-only stacks, but most retain RAG as a fallback"},
                {"shorthand": "@retrieval_skeptic critique (X)", "label": "x", "strength": "moderate",
                 "claim": "Independent evaluations show vendor long-context outperformance claims overstate the real gap on retrieval-heavy tasks"},
            ],
            "contradictions": [
                {"topic": "Long-context vs RAG superiority",
                 "side_a": ("[src 2]", "claims a wide vendor lead for long-context"),
                 "side_b": ("[src 3, src 5]", "show a much smaller delta on independent retrieval-heavy benchmarks")},
                {"topic": "Enterprise adoption pattern",
                 "side_a": ("[src 1]", "frames RAG as legacy"),
                 "side_b": ("[src 4]", "shows most enterprises retain RAG as a fallback even when shipping long-context stacks")},
            ],
            "analyst_inference": "The decision is workload-shaped, not model-shaped: the same model can favor either pattern depending on retrieval density",
            "next_step_focus": "the workload-shaped decision finding is the strongest contrarian thread angle",
        },
        "agent eval": {
            "keywords": ("eval", "evals", "agent eval", "evaluation", "promptfoo"),
            "default_query": "What does the data say about agent eval rigor for v1 builders?",
            "sources": [
                {"shorthand": "@dev_kai eval-loop thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Teams that ship a 5-input eval set on day one stay shipping into month three; teams that skip evals churn by week six"},
                {"shorthand": "Promptfoo case-study writeup (news)", "label": "news", "strength": "weak",
                 "claim": "Vendor case-studies suggest 30%+ regression-catch rates from automated eval loops"},
                {"shorthand": "agent reliability preprint (academic)", "label": "academic", "strength": "strong",
                 "claim": "Eval-set size of 5-20 cases captures the bulk of regressions in agent stacks; gains beyond 50 are marginal"},
                {"shorthand": "DevOps adoption survey (gov)", "label": "gov", "strength": "moderate",
                 "claim": "Most enterprise AI teams under-invest in evals relative to model size; <30% have a formal eval pipeline"},
            ],
            "contradictions": [
                {"topic": "How big should the eval set be?",
                 "side_a": ("[src 1]", "argues 5 inputs is enough on day one"),
                 "side_b": ("[src 3]", "shows the regression-catch curve flattens above 20 cases")},
            ],
            "analyst_inference": "The right starting point is 5 cases on day one, then grow to 15-20 by week six -- both sources point to the same operational rhythm even when their numbers differ",
            "next_step_focus": "the day-one-vs-week-six eval rhythm is the strongest how-to thread angle",
        },
    },
    "productivity": {
        "single-tab focus": {
            "keywords": ("single-tab", "single tab", "focus", "deep work", "pomodoro", "concentration"),
            "default_query": "Does single-tab focus actually outperform Pomodoro for solopreneurs?",
            "sources": [
                {"shorthand": "@focus_kai single-tab thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Single-tab discipline beats Pomodoro for deep-work blocks because context-switching cost dominates timer benefits"},
                {"shorthand": "\"Pomodoro revival 2026\" (news)", "label": "news", "strength": "weak",
                 "claim": "Pomodoro adoption among knowledge workers up 18% YoY, mostly tied to async-meeting fatigue"},
                {"shorthand": "deep-work productivity study (academic)", "label": "academic", "strength": "strong",
                 "claim": "Single-tab + 90-minute uninterrupted blocks outperform 25/5 Pomodoro on creative-task throughput in controlled trials"},
                {"shorthand": "remote-work hours report (gov)", "label": "gov", "strength": "moderate",
                 "claim": "Self-reported deep-work satisfaction is highest among workers using single-tab methods; Pomodoro users report higher consistency but lower output"},
                {"shorthand": "@pomodoro_fan critique (X)", "label": "x", "strength": "moderate",
                 "claim": "Single-tab discipline is impossible for context-switching roles; Pomodoro is the realist's option"},
            ],
            "contradictions": [
                {"topic": "Single-tab universality",
                 "side_a": ("[src 1, src 3]", "argue single-tab is dominant for creative throughput"),
                 "side_b": ("[src 5]", "argues it's impractical for context-switching roles")},
                {"topic": "Pomodoro trajectory",
                 "side_a": ("[src 2]", "shows Pomodoro is rising"),
                 "side_b": ("[src 4]", "shows Pomodoro users report lower output despite higher consistency")},
            ],
            "analyst_inference": "The right method is role-shaped: solopreneurs in creative roles benefit from single-tab; context-switching roles benefit from Pomodoro -- both can be true simultaneously",
            "next_step_focus": "the role-shaped framing is the strongest contrarian thread angle for the productivity niche",
        },
    },
    "finance": {
        "tax automation": {
            "keywords": ("tax", "taxes", "automation", "1099", "creator tax", "tax export", "vietnam"),
            "default_query": "How should creators automate tax tracking for X Money payouts?",
            "sources": [
                {"shorthand": "@tax_anxious export-tool thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Per-payout CSV exports reduced quarterly tax-prep time by 40%+ for solo creators in the early sample"},
                {"shorthand": "\"creator tax season 2026\" (news)", "label": "news", "strength": "weak",
                 "claim": "Platforms are racing to ship 1099-style aggregation; X Money's own export is the cleanest in the cohort"},
                {"shorthand": "remote-work tax compliance preprint (academic)", "label": "academic", "strength": "moderate",
                 "claim": "International creators with platform earnings face higher compliance burden; jurisdiction-specific aggregation reduces error rates"},
                {"shorthand": "Vietnam creator-tax guidance update (gov)", "label": "gov", "strength": "strong",
                 "claim": "Vietnam-resident creators with X Money earnings must report platform income quarterly; aggregator tools are accepted as evidence"},
                {"shorthand": "@compliance_q 1099-style ask (X)", "label": "x", "strength": "weak",
                 "claim": "Creators want a single 1099-style report; current per-payout CSVs require manual aggregation"},
            ],
            "contradictions": [
                {"topic": "Aggregation completeness",
                 "side_a": ("[src 2]", "frames current export as the cleanest available"),
                 "side_b": ("[src 5]", "highlights gaps that creators still bridge manually")},
            ],
            "analyst_inference": "The current export covers the data; the missing layer is reporting-format aggregation -- a v2 tool feature, not a data problem",
            "next_step_focus": "the aggregation-format gap is the strongest how-to thread for the finance niche",
        },
    },
    "creator": {
        "owned-audience math": {
            "keywords": ("owned-audience", "owned audience", "newsletter", "audience math", "funnel"),
            "default_query": "Does owned-audience math actually beat raw follower count for creators?",
            "sources": [
                {"shorthand": "@audience_q funnel thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Creators with newsletter funnels report 3-5x higher per-follower engagement than follower-count peers"},
                {"shorthand": "\"creator monetization 2026\" (news)", "label": "news", "strength": "weak",
                 "claim": "Industry coverage frames owned-audience math as the durable creator metric"},
                {"shorthand": "platform engagement study (academic)", "label": "academic", "strength": "strong",
                 "claim": "Per-follower engagement on X is heavy-tailed; the top decile earns 60%+ of monetization regardless of follower count"},
                {"shorthand": "@cadence_fan rebuttal (X)", "label": "x", "strength": "moderate",
                 "claim": "Owned-audience math discounts the audience-discovery role of follower count; both matter"},
            ],
            "contradictions": [
                {"topic": "Owned-audience exclusivity",
                 "side_a": ("[src 1, src 2]", "argue owned-audience math is the durable metric"),
                 "side_b": ("[src 4]", "argues raw follower count still drives discovery and shouldn't be discounted")},
            ],
            "analyst_inference": "Both metrics matter at different stages: follower count for discovery in months 0-12, owned-audience math for retention and monetization beyond month 12",
            "next_step_focus": "the stage-shaped metric framing is the strongest list-led thread angle",
        },
    },
    "fitness": {
        "Zone 2 training": {
            "keywords": ("zone 2", "zone two", "vo2", "training", "cardio"),
            "default_query": "Does Zone 2 actually deliver the longevity benefits the discourse claims?",
            "sources": [
                {"shorthand": "@zone2_fan training thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Consistent Zone 2 over 12+ weeks measurably improves recovery quality and resting heart rate"},
                {"shorthand": "longevity study update (news)", "label": "news", "strength": "weak",
                 "claim": "Industry coverage frames Zone 2 as the longevity gold standard"},
                {"shorthand": "metabolic adaptation preprint (academic)", "label": "academic", "strength": "strong",
                 "claim": "Zone 2 measurably increases mitochondrial density in untrained subjects; effect plateaus after ~16 weeks"},
                {"shorthand": "@high_intensity rebuttal (X)", "label": "x", "strength": "moderate",
                 "claim": "Zone 2 alone misses peak VO2 stimulus; high-intensity intervals are still required for the full longevity stack"},
            ],
            "contradictions": [
                {"topic": "Zone 2 sufficiency",
                 "side_a": ("[src 1, src 3]", "support Zone 2 as a primary longevity driver"),
                 "side_b": ("[src 4]", "argues high-intensity intervals are still required for the full stack")},
            ],
            "analyst_inference": "The strongest practical pattern is Zone 2 as the volume base + 1-2 high-intensity sessions per week for the VO2 ceiling -- both sides converge on this in practice",
            "next_step_focus": "the volume-base + intensity-ceiling synthesis is the strongest data-led thread angle",
        },
    },
    "general": {
        "evergreen synthesis": {
            "keywords": (),
            "default_query": "What does balanced creator research look like for an evergreen topic?",
            "sources": [
                {"shorthand": "broad creator-research X thread (X)", "label": "x", "strength": "moderate",
                 "claim": "Balanced research surfaces 3-5 sources per question and explicitly flags contradictions before drawing conclusions"},
                {"shorthand": "creator research best-practices essay (news)", "label": "news", "strength": "weak",
                 "claim": "Citation-first research is what separates durable creator content from hot takes"},
                {"shorthand": "synthesis methodology preprint (academic)", "label": "academic", "strength": "moderate",
                 "claim": "Multi-source synthesis with contradictions surfaced reduces reader-side error rates relative to single-source summaries"},
            ],
            "contradictions": [],
            "analyst_inference": "The trustworthy default is 3-5 sources, contradictions explicit, conclusions calibrated to source strength",
            "next_step_focus": "the citation-first framing applies to any creator topic",
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


def deterministic_seed(x_handle: str, query: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{query.strip().lower()}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def _resolve_topic(query: str, bucket: str) -> Tuple[str, Dict[str, Any]]:
    """Match query to a topic in the bucket; fall back to bucket's first topic."""
    bucket_topics = RESEARCH_CORPUS_BY_BUCKET.get(bucket) or RESEARCH_CORPUS_BY_BUCKET["general"]
    q_lower = query.lower()
    best: Optional[Tuple[str, Dict[str, Any]]] = None
    best_score = 0
    for topic_name, topic_data in bucket_topics.items():
        score = sum(1 for k in topic_data["keywords"] if k in q_lower)
        if score > best_score:
            best = (topic_name, topic_data)
            best_score = score
    if best:
        return best
    # Fallback: first topic in bucket
    first_name = next(iter(bucket_topics))
    return first_name, bucket_topics[first_name]


def _filter_sources(sources: List[Dict[str, str]], wanted: str) -> List[Dict[str, str]]:
    if wanted == "all":
        return sources
    return [s for s in sources if s["label"] == wanted]


def _depth_targets(depth: str) -> Dict[str, int]:
    return {
        "quick": {"findings": 3, "next_steps": 3},
        "standard": {"findings": 5, "next_steps": 4},
        "deep": {"findings": 8, "next_steps": 5},
    }[depth]


# ---------------------------------------------------------------------------
# Findings, contradictions, next steps
# ---------------------------------------------------------------------------

def _build_findings(
    sources: List[Dict[str, str]],
    contradictions: List[Dict[str, Any]],
    analyst_inference: str,
    target_count: int,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    # 1. One finding per source (in source-order so [src N] is stable).
    for i, s in enumerate(sources, start=1):
        finding = {
            "text": s["claim"] + ".",
            "citation": f"[src {i}]",
            "finance_tag": is_finance_adjacent(s["claim"]),
        }
        findings.append(finding)
        if len(findings) >= target_count:
            return findings

    if len(findings) >= target_count:
        return findings

    # 2. Cross-citation finding (combines first 2 sources if at least 2 exist).
    if len(sources) >= 2:
        cross = (
            f"Taken together, {sources[0]['claim']} and {sources[1]['claim']} "
            "trace the same operational rhythm even when their specific framings differ."
        )
        findings.append({
            "text": cross,
            "citation": "[src 1, src 2]",
            "finance_tag": is_finance_adjacent(cross),
        })
        if len(findings) >= target_count:
            return findings

    # 3. Contradiction-frame finding (from first contradiction if available).
    if contradictions:
        c = contradictions[0]
        side_a_cite, _ = c["side_a"]
        side_b_cite, _ = c["side_b"]
        # Strip brackets to combine
        merged_cite = f"{side_a_cite}, {side_b_cite}".replace("[", "").replace("]", "").replace(", ,", ", ")
        merged_cite = re.sub(r"\s+", " ", merged_cite)
        text = (
            f"On {c['topic'].lower()}, the picture is genuinely mixed -- the cited "
            "sources disagree on the magnitude even when they agree on the direction."
        )
        findings.append({
            "text": text,
            "citation": f"[{merged_cite}]",
            "finance_tag": is_finance_adjacent(text),
        })
        if len(findings) >= target_count:
            return findings

    # 4. Analyst inference (only ever 1-2 in a single output per system prompt).
    if analyst_inference:
        findings.append({
            "text": analyst_inference + ".",
            "citation": "[analyst inference]",
            "finance_tag": is_finance_adjacent(analyst_inference),
        })

    return findings[:target_count]


def _build_next_steps(
    bucket: str,
    topic_name: str,
    next_step_focus: str,
    target_count: int,
    suggest_visual: bool,
) -> List[str]:
    """Generate cross-template-bridged next steps."""
    bridges = [
        (
            f"Expand the strongest finding ({next_step_focus}) into a thread via "
            f"`content-idea-generator` -- the contrarian / how-to angle is underused."
        ),
        (
            "Triage the X-source mentions in this batch via `mention-summarizer` "
            "to surface which advocates vs critics deserve a same-day reply."
        ),
        (
            f"Draft 3 voice-matched replies to the contradiction's loudest X voice "
            f"via `reply-drafter` -- the disagreement is high-engagement."
        ),
        (
            f"Queue '{topic_name}' for tomorrow's brief via "
            f"`daily-briefing-agent --focus-areas \"{topic_name}\"` to compound the signal."
        ),
        (
            f"Ship 3 trend-aligned posts on the strongest finding via "
            f"`trend-aligned-poster --niche \"{topic_name}\" --trend-source x_trending`."
        ),
        (
            "Skim the strongest academic source's setup paragraph before drafting "
            "any thread -- it's where the methodology caveats live."
        ),
    ]
    return bridges[:target_count]


def _build_visual_prompt(query: str, bucket: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment hero card illustrating the research "
        f"question '{query}' in the {bucket} niche. Clean composition, neon "
        "highlights, Windows 11 desktop vibe, 16:9, no text overlay."
    )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_research_summary(
    x_handle: str,
    query: str,
    depth: str = "standard",
    sources: str = "all",
    niche: Optional[str] = None,
    include_visual: bool = False,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured research summary dict.

    Output schema:
      {
        "x_handle", "query", "today", "depth_requested", "depth_used",
        "sources_filter", "niche_bucket", "topic_matched",
        "key_findings": [{"text", "citation", "finance_tag"}],
        "contradictions": [{"topic", "side_a", "side_b"}],
        "sources_cited": [{"index", "shorthand", "strength", "label"}],
        "next_steps": [str], "confidence_label", "confidence_reason",
        "visual_prompt": str | None, "refused": bool, "warning": str | None,
      }
    """
    if depth not in ("quick", "standard", "deep"):
        raise ValueError(f"depth must be one of quick|standard|deep, got {depth!r}")
    if sources not in ("all", "x", "news", "academic", "gov"):
        raise ValueError(f"sources must be one of all|x|news|academic|gov, got {sources!r}")
    if not query.strip():
        raise ValueError("query must be non-empty")

    today = today or _dt.date.today()
    rng = random.Random(deterministic_seed(x_handle, query, today))

    bucket = detect_bucket((niche or "") + " " + query)
    topic_name, topic_data = _resolve_topic(query, bucket)

    full_sources = topic_data["sources"]
    filtered = _filter_sources(full_sources, sources)
    if not filtered:
        return {
            "refused": False,
            "warning": (
                f"--sources {sources!r} filtered out every source for topic "
                f"{topic_name!r}. Re-run with --sources all or pick a different category."
            ),
            "x_handle": x_handle, "query": query, "today": today.isoformat(),
            "depth_requested": depth, "depth_used": depth,
            "sources_filter": sources,
            "niche_bucket": bucket, "topic_matched": topic_name,
            "key_findings": [], "contradictions": [],
            "sources_cited": [], "next_steps": [],
            "confidence_label": "low",
            "confidence_reason": "no sources passed the filter",
            "visual_prompt": None,
        }

    targets = _depth_targets(depth)
    actual_depth = depth
    # Downgrade deep -> standard if filtered pool is too small (cost-aware).
    if depth == "deep" and len(filtered) < 4:
        actual_depth = "standard"
        targets = _depth_targets("standard")

    findings = _build_findings(
        sources=filtered,
        contradictions=topic_data["contradictions"],
        analyst_inference=topic_data["analyst_inference"],
        target_count=targets["findings"],
        rng=rng,
    )

    contradictions = topic_data["contradictions"][:] if depth != "quick" else []
    sources_cited = [
        {"index": i + 1, "shorthand": s["shorthand"],
         "strength": s["strength"], "label": s["label"]}
        for i, s in enumerate(filtered)
    ]

    next_steps = _build_next_steps(
        bucket=bucket,
        topic_name=topic_name,
        next_step_focus=topic_data["next_step_focus"],
        target_count=targets["next_steps"],
        suggest_visual=include_visual,
    )

    # Confidence
    strong_count = sum(1 for s in filtered if s["strength"] == "strong")
    moderate_count = sum(1 for s in filtered if s["strength"] == "moderate")
    label_set = {s["label"] for s in filtered}
    if strong_count >= 1 and len(filtered) >= 4:
        conf_label = "high" if actual_depth == "deep" else "medium-high"
    elif strong_count >= 1 or len(filtered) >= 3:
        conf_label = "medium-high" if actual_depth != "quick" else "medium"
    else:
        conf_label = "medium" if filtered else "low"

    cross_source_note = ""
    if actual_depth == "deep":
        cross_source_note = (
            f" Cross-source synthesis: {len(label_set)} distinct source categories "
            "agree on the practical rhythm even when they disagree on the magnitude; "
            "the analyst-inference finding is where the convergence lands honestly."
        )

    conf_reason = (
        f"{len(filtered)} cited source(s) span {sorted(label_set)}; "
        f"{strong_count} strong, {moderate_count} moderate; "
        f"{len(contradictions)} contradiction(s) surfaced; "
        f"depth={actual_depth} ({'downgraded from deep due to filter' if actual_depth != depth else 'as requested'})."
        + cross_source_note
    )

    visual_prompt = _build_visual_prompt(query, bucket) if include_visual else None

    return {
        "refused": False,
        "warning": None,
        "x_handle": x_handle,
        "query": query,
        "today": today.isoformat(),
        "depth_requested": depth,
        "depth_used": actual_depth,
        "sources_filter": sources,
        "niche_bucket": bucket,
        "topic_matched": topic_name,
        "key_findings": findings,
        "contradictions": contradictions,
        "sources_cited": sources_cited,
        "next_steps": next_steps,
        "confidence_label": conf_label,
        "confidence_reason": conf_reason,
        "visual_prompt": visual_prompt,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_research_summary


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_report(result: Dict[str, Any]) -> str:
    license_block = (
        "<!-- Copyright 2026 AgentMindCloud -->\n"
        "<!-- Licensed under the Apache License, Version 2.0 -->\n"
        "<!-- http://www.apache.org/licenses/LICENSE-2.0 -->\n"
        f"<!-- {TAGLINE} -->\n\n"
    )
    meta = textwrap.dedent(f"""\
        # Research Summary -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Niche bucket:** {result['niche_bucket']}
        - **Topic matched:** {result['topic_matched']}
        - **Depth requested:** {result['depth_requested']}
        - **Depth used:** {result['depth_used']}
        - **Sources filter:** {result['sources_filter']}

        > {TAGLINE}

        """)

    if result.get("warning"):
        body = textwrap.dedent(f"""\
            ## Refusal / Warning

            {result['warning']}

            Confidence: {result['confidence_label']} -- {result['confidence_reason']}
            """)
        return license_block + meta + body

    out: List[str] = []

    out.append("## Question")
    out.append("")
    out.append(result["query"])
    out.append("")

    out.append("## Key Findings")
    out.append("")
    for i, f in enumerate(result["key_findings"], start=1):
        out.append(f"{i}. {f['text']} {f['citation']}")
        if f.get("finance_tag"):
            out.append("   Context only -- not financial advice.")
    out.append("")

    out.append("## Contradictions Flagged")
    out.append("")
    if result["contradictions"]:
        for c in result["contradictions"]:
            side_a_cite, side_a_text = c["side_a"]
            side_b_cite, side_b_text = c["side_b"]
            out.append(
                f"- **{c['topic']}** -- Source {side_a_cite} {side_a_text}; "
                f"source {side_b_cite} {side_b_text}. Neither resolved; "
                "the user picks based on their workload."
            )
    else:
        out.append("- No contradictions surfaced across the cited sources.")
    out.append("")

    out.append("## Sources Cited")
    out.append("")
    out.append("| # | source | strength | label |")
    out.append("| - | ------ | -------- | ----- |")
    for s in result["sources_cited"]:
        out.append(f"| {s['index']} | {s['shorthand']} | {s['strength']} | {s['label']} |")
    out.append("")

    out.append("## Suggested Next Steps")
    out.append("")
    for step in result["next_steps"]:
        out.append(f"- {step}")
    out.append("")

    out.append("## Confidence")
    out.append("")
    out.append(f"{result['confidence_label']} -- {result['confidence_reason']}")
    out.append("")

    if result["visual_prompt"]:
        out.append("## Visual Aid")
        out.append("")
        out.append(result["visual_prompt"])
        out.append("")

    return license_block + meta + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_DEMO_QUERIES: Dict[str, str] = {
    "ai": "What's the strongest evidence that long-context models reduce the need for RAG?",
    "productivity": "Does single-tab focus actually outperform Pomodoro for solopreneurs?",
    "finance": "How should creators automate tax tracking for X Money payouts?",
    "creator": "Does owned-audience math actually beat raw follower count for creators?",
    "fitness": "Does Zone 2 actually deliver the longevity benefits the discourse claims?",
}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="research-assistant",
        description=(
            f"Research Assistant v{VERSION} -- citations-first creator research. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --query "long-context vs RAG"
              python run.py --x-handle @creator --query "single-tab focus" --depth deep
              python run.py --x-handle @me --query "tax automation" --sources academic --output today.md
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument("--query", default=None, help="The research question or topic. Required unless --demo is set.")
    parser.add_argument(
        "--demo", choices=sorted(_DEMO_QUERIES.keys()), default=None,
        help="Use a prefab niche query if --query is omitted.",
    )
    parser.add_argument(
        "--depth", choices=("quick", "standard", "deep"), default="standard",
        help="Research depth (default standard).",
    )
    parser.add_argument(
        "--sources", choices=("all", "x", "news", "academic", "gov"), default="all",
        help="Source category filter (default all).",
    )
    parser.add_argument("--niche", default=None, help="Optional niche hint (e.g. 'AI agents on X').")
    parser.add_argument("--suggest-visual", action="store_true",
                        help="Append a Visual Aid section (Grok Imagine prompt).")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Optional output file path (Windows-friendly; folders auto-created).",
    )
    parser.add_argument("--no-banner", action="store_true", help="Suppress the banner header.")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override 'today' for deterministic regeneration (YYYY-MM-DD).",
    )
    parser.add_argument("--version", action="version", version=f"research-assistant {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    query = args.query or (_DEMO_QUERIES[args.demo] if args.demo else None)
    if not query:
        sys.stderr.write("X  --query is required (or pass --demo {ai|productivity|finance|creator|fitness})\n")
        return 64

    if args.date:
        try:
            today = _dt.date.fromisoformat(args.date)
        except ValueError:
            sys.stderr.write(f"X  Invalid --date {args.date!r}; expected YYYY-MM-DD\n")
            return 64
    else:
        today = _dt.date.today()

    try:
        result = generate_research_summary(
            x_handle=args.x_handle,
            query=query,
            depth=args.depth,
            sources=args.sources,
            niche=args.niche,
            include_visual=args.suggest_visual,
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
        n = len(result.get("key_findings", []))
        sys.stdout.write(f"\nOK Wrote summary -> {out_path} ({n} findings)\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
