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
Thread Builder -- zero-dependency CLI demo runner.

Built to help xAI and Grok win the agent platform battle on X.

This v1 runner is fully self-contained: it ships per-angle body skeletons
(hook + payoff + 4-6 body slots + CTA), per-bucket fillers, and a deterministic
synthesis pipeline that respects the 4-tier length contract and ≤280-char
limit defined in `prompts/system.md` (auto-loaded). To wire to live Grok 4.3,
replace the body of `generate_thread_outline()` with a Grok call that consumes
the system prompt and returns the same schema.

Usage (Windows 11 PowerShell):
    python run.py --x-handle @JanSol0s --topic "shipping a Grok agent in a week"
    python run.py --x-handle @creator --topic "5 productivity rituals" --thread-length long
    python run.py --x-handle @me --topic "long-context vs RAG" --tone data-led --include-visuals
    python run.py --x-handle @test --topic "shipping a Grok agent in a week" --thread-length standard --include-visuals
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
    f"  THREAD BUILDER  v{VERSION}\n"
    "  Topic in, thread out -- under 60 seconds, ready to ship.\n"
    f"  {TAGLINE}\n"
    "============================================================\n"
)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"

MAX_TWEET_CHARS = 280

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

ANGLES: Tuple[str, ...] = (
    "contrarian", "data-led", "story-led", "list-led",
    "prediction", "comparison", "how-to", "hot-take",
)

LENGTH_TARGETS: Dict[str, int] = {
    "short": 5, "standard": 8, "long": 12,
}

NICHE_BUCKETS: List[Tuple[str, Tuple[str, ...]]] = [
    ("ai", ("ai", "agent", "agents", "llm", "claude", "grok", "chatgpt", "ml", "model", "rag", "mcp", "context")),
    ("finance", ("money", "crypto", "stock", "trading", "fintech", "invest", "cashtag", "token", "defi", "earnings", "tax", "payout")),
    ("productivity", ("productivity", "solopreneur", "system", "workflow", "habit", "focus", "deep work", "calendar", "ritual", "pomodoro")),
    ("creator", ("creator", "content", "monetize", "audience", "newsletter", "thread", "growth")),
    ("fitness", ("fitness", "health", "running", "lifting", "nutrition", "training", "vo2", "zone")),
]
DEFAULT_BUCKET = "general"

PARENT_ANGLE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "how-to": ("how to", "how i", "step", "playbook", "guide", "ship", "build", "in a week", "setup"),
    "list-led": ("5 ", "7 ", "10 ", "patterns", "ways", "lessons", "mistakes", "rules", "tips"),
    "contrarian": ("stop", "everyone says", "wrong", "actually", "myth", "stop optimizing"),
    "data-led": ("number", "stat", "%", "tracked", "data on", "metrics", "deltas"),
    "story-led": ("shipped", "lived", "story", "happened", "year", "month", "i tried"),
    "prediction": ("predict", "by q", "going to", "future", "next year", "by year-end"),
    "comparison": (" vs ", "versus", "compare", "compared", "better than"),
    "hot-take": ("underrated", "hot take", "sleeping on", "most underrated"),
}
DEFAULT_PARENT_ANGLE = "how-to"

FINANCE_KEYWORDS = (
    "crypto", "token", "cashtag", "stock", "trading", "earnings",
    "$", "fintech", "defi", "invest", "p&l", "tax", "buy", "sell",
    "x money", "payout",
)

POLICY_VIOLATING_KEYWORDS = (
    "doxx", "doxxing", "ratio them", "harass", "pile on",
    "cancel them", "ratio-bait",
)

TONE_PREPENDS: Dict[str, str] = {
    "punchy": "",
    "thoughtful": "On reflection -- ",
    "data-led": "Quick numbers: ",
    "warm": "Big fan of this space -- ",
}

# Per-bucket fillers used by body templates.
BUCKET_FILLERS: Dict[str, Dict[str, str]] = {
    "ai": {
        "expected_action": "fine-tuning",
        "artifact": "eval set",
        "check": "eval",
        "cta_word": "eval",
        "expected_outcome": "model size beats prompt design",
        "budget_phrase": "Track cost-per-1k-tokens weekly",
    },
    "productivity": {
        "expected_action": "to-do app stacking",
        "artifact": "weekly review",
        "check": "review",
        "cta_word": "review",
        "expected_outcome": "more apps means more capture",
        "budget_phrase": "Track minutes-per-task weekly",
    },
    "finance": {
        "expected_action": "spreadsheet manual entry",
        "artifact": "P&L sheet",
        "check": "ledger",
        "cta_word": "ledger",
        "expected_outcome": "tax automation isn't worth the setup",
        "budget_phrase": "Track cost-per-export monthly",
    },
    "creator": {
        "expected_action": "follower-count chasing",
        "artifact": "content library",
        "check": "audit",
        "cta_word": "library",
        "expected_outcome": "raw follower count drives monetization",
        "budget_phrase": "Track save-rate per post weekly",
    },
    "fitness": {
        "expected_action": "calorie counting",
        "artifact": "training log",
        "check": "log",
        "cta_word": "log",
        "expected_outcome": "intensity always beats consistency",
        "budget_phrase": "Track HR-zone time weekly",
    },
    "general": {
        "expected_action": "the obvious move",
        "artifact": "review log",
        "check": "audit",
        "cta_word": "review",
        "expected_outcome": "doing more is the answer",
        "budget_phrase": "Track effort-vs-output weekly",
    },
}

# 2 hook templates per angle; runner picks the parent + 2 complement angles
# to span ≥2 different angles.
HOOK_TEMPLATES_BY_ANGLE: Dict[str, List[str]] = {
    "how-to": [
        "Shipped {topic_short} in 7 days. Here's the loop that actually works -- {check}s on day one, not day thirty.",
        "How to ship {topic_short} for {niche} in one week. Step-by-step, with the {artifact} inside.",
    ],
    "contrarian": [
        "Stop optimizing for {expected_action}. Optimize for {topic_short}. The conventional path is the slow path in {niche}.",
        "Hot take on {topic_short} for {niche}: most advice is wrong at v1, accidentally right at v3, never the leverage move.",
    ],
    "data-led": [
        "3 numbers that changed how I think about {topic_short} in {niche}. The first one is bigger than you'd guess.",
        "Tracked {topic_short} for 90 days. Three deltas surprised me; sharing the data before the explanations.",
    ],
    "story-led": [
        "Shipped my first {topic_short} thing last month. The lesson nobody warned me about kicked in on week three.",
        "Lived this one in {niche}: {topic_short} broke my workflow on Tuesday, fixed it by Friday. Sharing the arc.",
    ],
    "list-led": [
        "5 {topic_short} patterns every {niche} person should steal. Most folks know 1-2; the rest are quiet wins.",
        "Top 5 {topic_short} levers nobody pulls in {niche}. Cheap to copy; works on day one.",
    ],
    "prediction": [
        "Two predictions for {niche} in 6 months: 1) {topic_short} wins. 2) {expected_action} stops mattering. Bookmark.",
        "By Q4, {topic_short} will be table-stakes in {niche}. The early movers are already compounding quietly.",
    ],
    "comparison": [
        "{topic_short} vs {expected_action}: not even close once you ship at scale in {niche}.",
        "Why {topic_short} eats {expected_action} for breakfast in {niche}, in one short thread.",
    ],
    "hot-take": [
        "Hot take: {topic_short} is the most underrated thing in {niche} right now.",
        "Most {niche} advice ignores {topic_short} entirely. That's exactly why it's the edge for the next 90 days.",
    ],
}

# Body skeletons per parent angle: 8 slots = (role, template). Keep prose
# under ~250 chars after substitution so 280-char limit holds even for long
# topic strings.
BODY_TEMPLATES_BY_ANGLE: Dict[str, List[Tuple[str, str]]] = {
    "how-to": [
        ("Hook", "Shipped {topic_short} in 7 days. Here's the loop that actually works -- {check}s on day one, not day thirty."),
        ("Payoff", "The 4-step loop: 1) cap inputs 2) log every call 3) ship a tiny {artifact} 4) review on Friday. Boring on day one, dangerous by week six."),
        ("Step 1", "Step 1 -- cap inputs. v1 attempts fail because the input space is unbounded. Pick 3-5 input shapes; build for those first; expand only when the {check} forces it."),
        ("Step 2", "Step 2 -- log every call. Inputs, outputs, latency, cost. You can't iterate on what you can't see. The first week of logs is the most expensive thing you'll skip."),
        ("Step 3", "Step 3 -- ship a tiny {artifact}. Five cases. Real ones. The regression-catch curve flattens above 20, but five catches the dumb breaks before users see them."),
        ("Step 4", "Step 4 -- {check} review. 30 minutes. Look at the worst 5 outputs, log what surprised you, write 1 new {artifact} case. Same time every Friday. Compounding is real."),
        ("Outcome", "By day 30 my {topic_short} caught its own regressions; by day 60 the {artifact} was the real product. Boring on day one, dangerous by week six -- everything compounds."),
        ("CTA", "That's the loop. If you want the 5-case {artifact} template, reply '{cta_word}' and I'll DM. Or just steal the structure -- it's not the secret."),
    ],
    "list-led": [
        ("Hook", "5 {topic_short} patterns every {niche} person should steal. Most folks know 1-2; the rest are quiet wins."),
        ("Payoff", "Saved 3 quarters of effort once I started using these. Cheap to copy; works on day one. Going through them in order."),
        ("Item 1", "1. Cap your inputs. Build for 3-5 shapes; expand only when the {check} forces it. The unbounded version is where most v1 attempts die quietly."),
        ("Item 2", "2. Log every call. Latency, cost, output drift. The first week of logs is what makes weeks 2-12 actually iterate; skipping it costs you a quarter."),
        ("Item 3", "3. Ship a tiny {artifact}. Five cases is enough. The regression-catch curve flattens above 20; five catches the dumb breaks before they reach users."),
        ("Item 4", "4. Friday {check} review. 30 minutes. Worst 5 outputs, what surprised you, write 1 new case. By week six the {artifact} is the product."),
        ("Item 5", "5. Cap the cost. {budget_phrase}. Cost drift is the silent killer; track it weekly or you'll find a 5x bill at the end of month two."),
        ("CTA", "That's the 5. The thing that surprises most folks is that #5 is the moat -- everyone copies #1-4, almost nobody runs the cost dashboard. Reply '{cta_word}'."),
    ],
    "contrarian": [
        ("Hook", "Stop optimizing for {expected_action}. Optimize for {topic_short}. The conventional path is the slow path in {niche}."),
        ("Wisdom", "Conventional wisdom in {niche} says {expected_outcome}. Hot take: it's wrong at v1, accidentally right at v3, never the leverage move."),
        ("Why fails", "The reason it fails: {expected_action} optimizes for the wrong axis. You can't win at scale on a metric that doesn't track {topic_short}."),
        ("Alternative", "What works instead: {topic_short}. Cheap to test, hard to argue with by week six. Most folks who ship it don't go back to {expected_action}."),
        ("Evidence", "I lived this. Started with the conventional path; switched on week three. By week six the {check} confirmed the swap was the right call."),
        ("Edge case", "Exception: {expected_action} works for the very smallest scale where {topic_short} is overkill. Beyond that, it's noise."),
        ("Synthesis", "Synthesis: at v1 {expected_action} is the trap; at v3 {topic_short} is the moat. The faster you swap, the further you compound."),
        ("CTA", "If you want the swap playbook, reply '{cta_word}'. Or just try it for 14 days and tell me I'm wrong; the result speaks for itself."),
    ],
    "data-led": [
        ("Hook", "3 numbers that changed how I think about {topic_short} in {niche}. The first one is bigger than you'd guess."),
        ("Payoff", "Tracked these for 90 days. Each one rewrote a different assumption. Sharing the deltas before the explanations."),
        ("Datum 1", "1. {topic_short} compounds at roughly 2x the rate of {expected_action} when measured at week six. The size of the gap is what surprised me."),
        ("Datum 2", "2. Per-{check} cost dropped ~40% once I capped inputs to 3-5 shapes. Boring optimization; biggest single win of the quarter."),
        ("Datum 3", "3. Friday review days move the worst-output count more than any prompt change in the same week. The ritual matters more than the smart trick."),
        ("Interpretation", "Read the deltas as a system: cheap-to-test wins compound; smart-but-fragile wins don't. The cost number is the leading indicator most folks miss."),
        ("Surprise", "The thing I didn't expect: the same numbers held across 3 niches in the cohort -- so the playbook is portable, not bucket-specific."),
        ("CTA", "If you want the 90-day tracker template, reply '{cta_word}'. The numbers aren't the secret; the discipline of tracking them is."),
    ],
    "story-led": [
        ("Hook", "Shipped my first {topic_short} thing last month. The lesson nobody warned me about kicked in on week three."),
        ("Setup", "Going in I thought {expected_action} was the unlock. v1 looked fine. Then v2 wobbled in a way that wasn't on any tutorial's page."),
        ("Conflict", "The wobble was simple in hindsight: I couldn't see what was breaking because I hadn't built the {check}. Iterating on vibes, not signal."),
        ("Attempt", "First fix: more prompt tuning. Bought me a week. Second fix: more aggressive caching. Bought me three days. Both treated symptoms, not the root."),
        ("Breakthrough", "The breakthrough: shipped a tiny {artifact} on Saturday. Five cases. Suddenly I could see the failure modes -- the wobble had been there all along."),
        ("Lesson", "The lesson: in {niche}, you can't skip the boring step. {topic_short} is what you ship; the {artifact} is what lets you keep shipping."),
        ("Generalization", "Saw this same arc in 3 friends shipping {niche} v1s. Different topics, same pattern -- evals before optimization, every time."),
        ("CTA", "If you want the 5-case {artifact} I started with, reply '{cta_word}'. The lesson took me three weeks; you get it for the price of a DM."),
    ],
    "prediction": [
        ("Hook", "Two predictions for {niche} in the next 6 months: 1) {topic_short} wins. 2) {expected_action} stops mattering. Bookmark this."),
        ("Prediction one-liner", "{topic_short} becomes table-stakes by Q4; the people watching this closely already shifted. The latecomers will scramble."),
        ("Signal 1", "Signal 1: shipping cadence on {topic_short}-first projects is up sharply over 90 days. The early movers built the moat quietly."),
        ("Signal 2", "Signal 2: cost economics tilted hard against {expected_action} once {topic_short} hit production at scale. Hard to undo once the curve crosses."),
        ("Signal 3", "Signal 3: docs and tutorials around {topic_short} now outnumber {expected_action} for the first time -- attention is the leading indicator."),
        ("Counter-take", "Steel-man: {expected_action} still wins for the smallest scale where overhead matters more than ceiling. Beyond that, the curve flips."),
        ("Falsifiability", "How I'd be proven wrong: a 90-day window where {expected_action} measurably outperforms on a public benchmark. Watching for it; haven't seen it."),
        ("CTA", "Bookmark; come back at the 90-day mark. If I'm right, reply '{cta_word}' for the playbook. If I'm wrong, tell me why."),
    ],
    "comparison": [
        ("Hook", "{topic_short} vs {expected_action}: not even close once you ship at scale in {niche}. The framing is wrong; the differentiator isn't obvious."),
        ("Two-sides framing", "Both have real advocates. Both work in narrow regimes. Most arguments boil down to 'works on Tuesday' rather than 'works at scale on Friday'."),
        ("Side A pros", "{topic_short} wins on auditability, on iteration speed, on cost-per-{check}. The boring axes; the durable ones."),
        ("Side B pros", "{expected_action} wins on speed-of-first-spin and on the easy demo. The shiny axes; the ones that lose by month two."),
        ("Real differentiator", "Real differentiator: can you audit the failure mode? With {topic_short} the answer is yes by week one; with {expected_action} it's still 'sort of' by week six."),
        ("Recommendation", "Use {expected_action} for the 5-day prototype to convince the room. Switch to {topic_short} the moment a user touches it. The crossover point is real."),
        ("Edge case", "Exception: at very small scale where the {check} cost outweighs the moat, {expected_action} wins. Stop calling that case the rule."),
        ("CTA", "If you want the side-by-side template I use to make the call, reply '{cta_word}'. The comparison isn't the secret; doing it on schedule is."),
    ],
    "hot-take": [
        ("Hook", "Hot take: {topic_short} is the most underrated thing in {niche} right now. The community is sleeping on it; early movers are quietly compounding."),
        ("Claim restated", "Restating: most {niche} advice ignores {topic_short} entirely. That's exactly why it's the edge for the next 90 days."),
        ("Why now", "Why now: the {check} cost dropped, the tooling caught up, and the people who needed permission to try got it from the cohort that shipped first."),
        ("Context", "Running this in {niche} and the compounding is louder than anything the conventional path produced. Same effort; very different velocity."),
        ("Clincher", "Clincher: the boring move is the leveraged move. {topic_short} > {expected_action} not because it's clever but because it survives v3 reliably."),
        ("Edge case", "Edge case: at very small scale {expected_action} can still feel right. That's the trap -- the regime where it feels right is where the curve is about to flip."),
        ("Ask", "Real question: what's stopping you from shipping a {topic_short}-first {check} this week? Not the v1; just the smallest possible test of the swap."),
        ("CTA", "If you want the 14-day swap playbook, reply '{cta_word}'. Or just steal the structure and tell me how it goes; the playbook isn't the secret."),
    ],
}

# Long-mode extras (4 extra slots per angle for 12-tweet threads).
LONG_EXTRAS_BY_ANGLE: Dict[str, List[Tuple[str, str]]] = {
    "how-to": [
        ("Pitfall 1", "Pitfall 1 most folks hit: skipping the {artifact}. Looks fast on day one; costs a quarter when v2 breaks."),
        ("Pitfall 2", "Pitfall 2: over-tuning before measuring. The {check} tells you what to fix; vibes don't."),
        ("Tooling note", "Tooling note: any {check} library works. The discipline matters more than the framework. Start with what you have."),
        ("FAQ", "FAQ I keep getting: 'how big should the {artifact} be?' Five cases is enough. Twenty is plenty. Fifty is research."),
    ],
    "list-led": [
        ("Bonus 1", "Bonus 1: pin a Friday calendar block for the {check} ritual. Cheap; sustains compounding."),
        ("Bonus 2", "Bonus 2: write the {artifact} in plain language; future-you reads it more often than you'd guess."),
        ("Anti-pattern", "Anti-pattern: trying all 5 in week one. Pick #1 and #3 first; layer the rest as the cadence holds."),
        ("Closing", "Closing thought: each pattern looks tiny in isolation. Together they're the difference between a v1 that ships and one that compounds."),
    ],
    "contrarian": [
        ("Anticipated objection", "Anticipated objection: 'but {expected_action} is what everyone uses.' That's the data point, not the argument. Volume isn't quality."),
        ("Counter-counter", "Counter-counter: I'm not saying never use {expected_action}. I'm saying notice when it stops being the leverage move and pivot."),
        ("Adoption arc", "Adoption arc: contrarians ship first; the cohort follows by month three; the curve flips by month six. Every time."),
        ("Steel-man closing", "Steel-man closing: if you genuinely think {expected_action} > {topic_short} at v3, ship a 14-day test and post the {check} numbers."),
    ],
    "data-led": [
        ("Datum 4", "4. Pin-rate on the hook tweet correlates with thread completion rate ~3x better than reply count. The hook is the moat, not the body."),
        ("Datum 5", "5. Threads that include a {check} reference get ~30% more saves than threads that don't. The ritual signal lands."),
        ("Caveat", "Caveat: cohort was N=24 over 90 days, not a controlled trial. Treat as direction, not magnitude."),
        ("Closing", "Closing: numbers without rituals are entertainment; rituals without numbers are vibes. Track + review = leverage."),
    ],
    "story-led": [
        ("Aside", "Aside: the moment I knew the {artifact} was working was when I caught myself laughing at one of the bad outputs at 11pm Friday. Visibility is freedom."),
        ("Other arc", "Saw the same arc in a friend shipping {topic_short} for {niche}; same wobble, same fix, same week-six payoff. Pattern, not coincidence."),
        ("Tooling", "Tooling I used: nothing fancy. A markdown file with 5 inputs and 5 expected outputs. Read every Friday for 30 minutes. That's it."),
        ("Closing", "Closing: the boring step is the love letter you write to your future self. Skip it, lose the leverage. Write it, compound for months."),
    ],
    "prediction": [
        ("Earlier signal", "Earlier signal worth watching: when the docs catch up to the early movers, the curve has already crossed. Don't wait for the docs."),
        ("Trailing signal", "Trailing signal: when the conference talks pivot, you're a quarter late. Faster signal: who's shipping in public weekly."),
        ("Bet sizing", "Bet sizing: you don't need to be all-in. A 14-day {check} test is enough to know if the prediction holds for your specific stack."),
        ("Closing", "Closing: predictions aren't the work. The {check} you ship to test them is the work. Bookmark the test plan, not the take."),
    ],
    "comparison": [
        ("Hidden axis", "Hidden axis most folks ignore: cost-of-rollback. {topic_short} rolls back cleanly; {expected_action} drags context with it."),
        ("Honest mixed case", "Honest mixed case: hybrid stacks (use both) outperform either alone in the middle band. Don't read this thread as 'pick one'."),
        ("When to switch", "When to switch: the day the {check} numbers diverge by 2x in either direction, the comparison stops being academic."),
        ("Closing", "Closing: comparison threads age better when you commit to a re-test in 90 days. Pin a calendar block; revisit; update the post."),
    ],
    "hot-take": [
        ("Cohort signal", "Cohort signal: the 5 folks I trust most in {niche} all shipped a {topic_short}-first {check} in the last 30 days. That's the leading indicator."),
        ("Adoption velocity", "Adoption velocity: hot takes that compound have a 14-day test attached. This one does. The take is the bait; the test is the work."),
        ("Honest disagreement", "Honest disagreement: if your {niche} workload is genuinely tiny, {expected_action} is fine. Just don't generalize from that case."),
        ("Closing", "Closing: the strongest hot takes are boring on day one and dangerous by week six. {topic_short} clears that bar; ship it and tell me how it goes."),
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


def detect_parent_angle(topic: str) -> str:
    t = (topic or "").lower()
    best = None
    best_score = 0
    for angle, keys in PARENT_ANGLE_KEYWORDS.items():
        score = sum(1 for k in keys if k in t)
        if score > best_score:
            best, best_score = angle, score
    return best or DEFAULT_PARENT_ANGLE


def is_finance_adjacent(text: str) -> bool:
    s = (text or "").lower()
    return any(k in s for k in FINANCE_KEYWORDS)


def violates_policy(topic: str) -> bool:
    s = (topic or "").lower()
    return any(k in s for k in POLICY_VIOLATING_KEYWORDS)


def deterministic_seed(x_handle: str, topic: str, today: _dt.date) -> int:
    raw = f"{x_handle}|{topic.strip().lower()}|{today.isoformat()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def topic_short(topic: str, max_words: int = 4) -> str:
    """Extract a short noun-phrase from the topic for template substitution."""
    skip = {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "is", "are", "was", "were", "be", "this", "that",
        "you", "your", "i", "my", "we", "they", "do", "does", "did", "any",
        "what", "when", "where", "why", "how", "into", "about", "than",
        "then", "so", "all", "no", "not", "yes", "thanks", "great", "love",
        "just", "really", "very", "much", "more", "some", "first", "anyone",
        "else", "shipping", "shipped", "build", "building", "ship", "i'm",
        "ive", "i've", "lessons", "learned", "tips",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", (topic or "").lower())
    keep = [w for w in words if w not in skip and len(w) > 2]
    if not keep:
        return (topic or "this").strip()
    return " ".join(keep[:max_words])


def _tone_apply(text: str, tone: str, max_chars: int = MAX_TWEET_CHARS) -> str:
    prepend = TONE_PREPENDS.get(tone, "")
    if not prepend:
        return text
    candidate = prepend + text
    return candidate if len(candidate) <= max_chars else text


def _safe_render(template: str, max_chars: int, **kwargs: str) -> str:
    text = template.format(**kwargs).strip()
    if len(text) <= max_chars:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    while parts and len(" ".join(parts)) > max_chars:
        parts.pop()
    tightened = " ".join(parts).strip()
    if 0 < len(tightened) <= max_chars:
        return tightened
    cut = text[:max_chars].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(",;:")
    return cut


def _resolve_length(length: str, parent_angle: str) -> int:
    if length == "auto":
        if parent_angle in ("hot-take", "contrarian"):
            return LENGTH_TARGETS["short"]
        return LENGTH_TARGETS["standard"]
    return LENGTH_TARGETS.get(length, LENGTH_TARGETS["standard"])


def _build_imagine_prompt(role: str, topic_str: str, niche: str) -> str:
    return (
        f"Minimal cinnabar-and-parchment illustration depicting '{role}' "
        f"for the thread on '{topic_str}' in the {niche} niche. Clean "
        "composition, neon highlights, Windows 11 desktop vibe, 16:9, "
        "no text overlay."
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _pick_complement_angles(parent: str, rng: random.Random, n: int = 2) -> List[str]:
    pool = [a for a in ANGLES if a != parent]
    rng.shuffle(pool)
    return pool[:n]


def _build_hook_variants(
    parent: str,
    fillers: Dict[str, str],
    tone: str,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Return 3 variants spanning the parent angle plus 2 complement angles."""
    angles_picked = [parent] + _pick_complement_angles(parent, rng, n=2)
    out: List[Dict[str, Any]] = []
    for angle in angles_picked:
        templates = HOOK_TEMPLATES_BY_ANGLE[angle]
        rng.shuffle(templates)
        chosen = templates[0]
        rendered = _safe_render(chosen, MAX_TWEET_CHARS, **fillers)
        toned = _tone_apply(rendered, tone)
        out.append({
            "angle": angle,
            "char_count": len(toned),
            "draft": toned,
        })
    return out


def _build_full_drafts(
    parent: str,
    length_target: int,
    fillers: Dict[str, str],
    tone: str,
    include_visuals: bool,
    niche_label: str,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    body = list(BODY_TEMPLATES_BY_ANGLE[parent])
    extras = list(LONG_EXTRAS_BY_ANGLE[parent])

    # Apply length contract.
    if length_target <= 5:
        # short: hook + payoff + 2 body slots + CTA
        slots = [body[0], body[1], body[2], body[4], body[7]]
    elif length_target <= 8:
        slots = body[: length_target] if length_target < 8 else body
    else:
        # long: standard 8 + extras
        rng.shuffle(extras)
        slots = body + extras[: length_target - 8]
        # Ensure CTA is last
        cta = body[7]
        slots = [s for s in slots if s != cta] + [cta]
        slots = slots[:length_target]

    drafts: List[Dict[str, Any]] = []
    for i, (role, template) in enumerate(slots, start=1):
        rendered = _safe_render(template, MAX_TWEET_CHARS, **fillers)
        toned = _tone_apply(rendered, tone)
        # Engagement: hook = medium-high, climax slots = high, body = medium.
        if i == 1:
            engagement = "medium-high"
        elif role.startswith(("Outcome", "Lesson", "Synthesis", "Clincher", "Real differentiator", "Breakthrough")):
            engagement = "high"
        elif role == "CTA":
            engagement = "medium-high"
        else:
            engagement = "medium" if i % 2 == 0 else "medium-high"

        grok_imagine = None
        if include_visuals and (i == 1 or (i - 1) % 3 == 0):
            grok_imagine = _build_imagine_prompt(role, fillers["topic_short"], niche_label)

        finance_tag = is_finance_adjacent(toned)

        drafts.append({
            "n": i,
            "role": role,
            "char_count": len(toned),
            "engagement": engagement,
            "draft": toned,
            "grok_imagine": grok_imagine,
            "finance_tag": finance_tag,
        })
    return drafts


def _build_outline(drafts: List[Dict[str, Any]]) -> List[str]:
    """Map each tweet position to its narrative role in one short clause."""
    return [f"{d['n']}. {d['role']}" for d in drafts]


def _build_engagement_tips(parent: str, niche_label: str) -> List[str]:
    base = [
        "Pin the hook for 48h; the algorithm rewards sustained dwell time on threads.",
        "Reply to the first 3 quote-tweets within 30 minutes -- drives the second wave.",
        "Schedule between 9-11am in your largest audience timezone, midweek if possible.",
        "Reply with a numbered 'tweet N+1' anecdote when the thread crosses 10k impressions -- adds a fresh hook for late readers.",
    ]
    niche_specific = {
        "ai": "Drop the eval-set markdown in the replies once the thread crosses 5k impressions -- the technical bookmark spike compounds.",
        "productivity": "Pin a Friday calendar block reminder in the comments -- ritual signal lifts saves on this niche.",
        "finance": "Add the 'Context only -- not financial advice' line in the first reply too; it travels with screenshots.",
        "creator": "Cross-post the hook to your newsletter on day 2 -- the dual-channel reinforcement compounds.",
        "fitness": "Pin a beginner-friendly resource in the comments -- this niche over-rewards entry-points.",
        "general": "Watch reply quality after hour 3; the second wave is the leading indicator of which thread becomes evergreen.",
    }.get(niche_label, niche_specific := None) or "Watch reply quality after hour 3; the second wave is the leading indicator of which thread becomes evergreen."
    return base + [niche_specific]


def _build_cross_template_bridges(
    parent: str,
    drafts: List[Dict[str, Any]],
    niche_label: str,
) -> List[str]:
    bridges: List[str] = []
    # 1. CIG bridge for the strongest body tweet
    if len(drafts) >= 3:
        strongest = drafts[len(drafts) // 2]  # mid-thread climax
        bridges.append(
            f"Spin Tweet {strongest['n']}'s angle ('{strongest['role']}') into 5 follow-up "
            f"ideas via `content-idea-generator --niche \"{niche_label}\"`."
        )
    # 2. Mention triage
    bridges.append(
        "Triage inbound mentions on this thread via `mention-summarizer` -- "
        "the CTA will surface high-LTV asks worth a same-day reply pass."
    )
    # 3. Analytics check
    bridges.append(
        "After 48h, run `analytics-summarizer --time-range 7d` to confirm the "
        "engagement signal compounded vs your usual baseline."
    )
    # 4. Reply drafter for contradictions
    bridges.append(
        "Draft 3 voice-matched replies to the loudest contradicting voice via "
        "`reply-drafter` -- disagreement is high-engagement on this niche."
    )
    # 5. Daily briefing for tomorrow
    if parent in ("contrarian", "hot-take", "prediction"):
        bridges.append(
            f"Queue tomorrow's brief on the contrarian angle via "
            f"`daily-briefing-agent --focus-areas \"{niche_label}\"`."
        )
    return bridges[:5]


def _composite_engagement(drafts: List[Dict[str, Any]]) -> str:
    if not drafts:
        return "low"
    # If any tweet is high → high; else if hook is medium-high → medium-high; else medium.
    if any(d["engagement"] == "high" for d in drafts):
        return "high"
    if drafts[0]["engagement"] == "medium-high":
        return "medium-high"
    return "medium"


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def generate_thread_outline(
    x_handle: str,
    topic: str,
    thread_length: str = "standard",
    tone: str = "punchy",
    include_visuals: bool = False,
    niche: Optional[str] = None,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """Return a structured thread outline dict.

    Output schema documented in P59 system prompt.
    """
    if thread_length not in ("short", "standard", "long", "auto"):
        raise ValueError(f"thread_length must be short|standard|long|auto, got {thread_length!r}")
    if tone not in TONE_PREPENDS:
        raise ValueError(f"tone must be one of {list(TONE_PREPENDS)}, got {tone!r}")
    if not topic.strip():
        raise ValueError("topic must be non-empty")

    today = today or _dt.date.today()

    if violates_policy(topic):
        return {
            "refused": True,
            "warning": (
                "Topic matches policy-violating patterns (doxxing / harassment / "
                "ratio-bait). Refusing to produce a thread per Constitution rule #9."
            ),
            "x_handle": x_handle, "today": today.isoformat(),
            "topic": topic, "parent_angle": None,
            "headline": "", "hook_variants": [], "outline": [],
            "drafts": [], "engagement_tips": [], "bridges": [],
            "composite_engagement": "low",
            "include_visuals": include_visuals,
            "niche_bucket": detect_bucket(niche or topic),
            "niche_label": niche or detect_bucket(niche or topic),
        }

    rng = random.Random(deterministic_seed(x_handle, topic, today))

    bucket = detect_bucket((niche or "") + " " + topic)
    niche_label = niche or {
        "ai": "AI agents on X",
        "productivity": "Productivity systems for solopreneurs",
        "finance": "creator economy finance",
        "creator": "creator economy",
        "fitness": "Zone 2 training",
    }.get(bucket, "X creator")

    fillers = dict(BUCKET_FILLERS[bucket])
    fillers["topic_short"] = topic_short(topic)
    fillers["niche"] = niche_label

    parent_angle = detect_parent_angle(topic)
    length_target = _resolve_length(thread_length, parent_angle)

    hook_variants = _build_hook_variants(parent_angle, fillers, tone, rng)
    drafts = _build_full_drafts(
        parent=parent_angle, length_target=length_target,
        fillers=fillers, tone=tone, include_visuals=include_visuals,
        niche_label=niche_label, rng=rng,
    )
    outline = _build_outline(drafts)
    engagement_tips = _build_engagement_tips(parent_angle, bucket)
    bridges = _build_cross_template_bridges(parent_angle, drafts, niche_label)
    composite = _composite_engagement(drafts)

    headline = (
        f"{parent_angle.replace('-', ' ').capitalize()} thread on {fillers['topic_short']} "
        f"for {niche_label} -- composite engagement: {composite}."
    )

    return {
        "refused": False,
        "warning": None,
        "x_handle": x_handle,
        "today": today.isoformat(),
        "topic": topic,
        "thread_length_requested": thread_length,
        "thread_length_used": length_target,
        "tone": tone,
        "include_visuals": include_visuals,
        "parent_angle": parent_angle,
        "niche_bucket": bucket,
        "niche_label": niche_label,
        "headline": headline,
        "hook_variants": hook_variants,
        "outline": outline,
        "drafts": drafts,
        "engagement_tips": engagement_tips,
        "bridges": bridges,
        "composite_engagement": composite,
    }


# Manifest tool alias (manifest declares tools[0].function = "generate").
generate = generate_thread_outline


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
        # Thread Package -- {result['today']}

        - **Creator:** {result['x_handle']}
        - **Topic:** {result['topic']}
        - **Niche bucket:** {result['niche_bucket']}
        - **Niche label:** {result['niche_label']}
        - **Parent angle:** {result['parent_angle']}
        - **Thread length:** {result['thread_length_requested']} -> {result['thread_length_used']} tweets
        - **Tone:** {result['tone']}
        - **Visuals:** {'on' if result['include_visuals'] else 'off'}

        > {TAGLINE}

        """)

    if result["refused"]:
        body = textwrap.dedent(f"""\
            ## Refusal

            {result['warning']}

            Confidence: high -- refusal triggered before structured generation.
            """)
        return license_block + meta + body

    out: List[str] = ["## Headline", "", result["headline"], ""]

    out.append("## Hook Variants")
    out.append("")
    for i, h in enumerate(result["hook_variants"], start=1):
        out.append(f"{i}. **angle: {h['angle']}** ({h['char_count']} chars)")
        out.append(f"   - \"{h['draft']}\"")
    out.append("")

    out.append("## Thread Outline")
    out.append("")
    for line in result["outline"]:
        out.append(line)
    out.append("")

    out.append("## Full Drafts")
    out.append("")
    for d in result["drafts"]:
        out.append(
            f"### Tweet {d['n']} -- {d['role']} ({d['char_count']} chars, engagement: {d['engagement']})"
        )
        out.append("")
        out.append(f"\"{d['draft']}\"")
        out.append("")
        if d.get("grok_imagine"):
            out.append(f"- **Grok Imagine prompt:** {d['grok_imagine']}")
            out.append("")
        if d["finance_tag"]:
            out.append("Context only -- not financial advice.")
            out.append("")

    out.append("## Engagement Tips")
    out.append("")
    for tip in result["engagement_tips"]:
        out.append(f"- {tip}")
    out.append("")

    out.append("## Cross-Template Bridges")
    out.append("")
    for b in result["bridges"]:
        out.append(f"- {b}")
    out.append("")

    confidence = (
        f"Confidence: medium -- offline template library; "
        f"{len(result['drafts'])} tweets, all under {MAX_TWEET_CHARS} chars; "
        f"parent angle '{result['parent_angle']}' consistent across hook variants. "
        "For live grounding, wire `prompts/system.md` to the xAI API (see README)."
    )
    out.append(confidence)
    return license_block + meta + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_DEMO_TOPICS: Dict[str, str] = {
    "ai": "shipping a Grok agent in a week",
    "productivity": "5 single-tab focus rituals for solopreneurs",
    "finance": "X Money tax automation for creators",
    "creator": "owned-audience math vs follower-count chasing",
    "fitness": "Zone 2 training for desk workers",
}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="thread-builder",
        description=(
            f"Thread Builder v{VERSION} -- topic in, thread out. "
            f"{TAGLINE}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (Windows 11 PowerShell):
              python run.py --x-handle @JanSol0s --topic "shipping a Grok agent in a week"
              python run.py --x-handle @creator --topic "5 productivity rituals" --thread-length long
              python run.py --x-handle @me --demo ai --include-visuals
        """),
    )
    parser.add_argument("--x-handle", required=True, help="Your X handle, e.g. @JanSol0s.")
    parser.add_argument("--topic", default=None, help="Thread topic in plain language. Required unless --demo is set.")
    parser.add_argument(
        "--demo", choices=sorted(_DEMO_TOPICS.keys()), default=None,
        help="Use a prefab niche topic for first-run demos.",
    )
    parser.add_argument(
        "--thread-length", choices=("short", "standard", "long", "auto"), default="standard",
        help="Thread length contract (default standard).",
    )
    parser.add_argument(
        "--tone", choices=tuple(TONE_PREPENDS.keys()), default="punchy",
        help="Voice flavor (default punchy).",
    )
    parser.add_argument("--include-visuals", action="store_true",
                        help="Attach Grok Imagine prompt to hook + every 3rd tweet.")
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
    parser.add_argument("--version", action="version", version=f"thread-builder {VERSION}")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.no_banner:
        sys.stdout.write(BANNER)

    topic = args.topic or (_DEMO_TOPICS[args.demo] if args.demo else None)
    if not topic:
        sys.stderr.write("X  --topic is required (or pass --demo {ai|productivity|finance|creator|fitness})\n")
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
        result = generate_thread_outline(
            x_handle=args.x_handle,
            topic=topic,
            thread_length=args.thread_length,
            tone=args.tone,
            include_visuals=args.include_visuals,
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
        n = len(result["drafts"])
        verb = "Refused" if result["refused"] else f"Wrote {n}-tweet thread"
        sys.stdout.write(f"\nOK {verb} -> {out_path}\n")
    else:
        sys.stdout.write("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
