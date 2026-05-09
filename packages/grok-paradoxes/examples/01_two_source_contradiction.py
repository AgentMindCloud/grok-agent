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
"""Example 01 — two-source contradiction detection.

Built for xAI, X, Grok and the ecosystem community. ❤️

Two independent sources report different prices for BTC with similar
self-reported confidence. The detector surfaces the disagreement instead
of silently picking one.
"""
from __future__ import annotations

from grok_paradoxes import Claim, ContradictionDetector, Source


def main() -> None:
    s1 = Source(name="x_post", authority=0.6, scope="social")
    s2 = Source(name="news_wire", authority=0.7, scope="news")

    claims = [
        Claim(subject="BTC", predicate="price", value=10, source=s1, confidence=0.8),
        Claim(subject="BTC", predicate="price", value=15, source=s2, confidence=0.8),
    ]

    detector = ContradictionDetector(min_severity="minor")
    contradictions = detector.detect(claims)

    print(f"Detected {len(contradictions)} contradiction(s):")
    for c in contradictions:
        print(f"  [{c.severity}] {c.rationale}")
        print(f"    {c.claim_a.source.name} -> {c.claim_a.value}")
        print(f"    {c.claim_b.source.name} -> {c.claim_b.value}")


if __name__ == "__main__":
    main()
