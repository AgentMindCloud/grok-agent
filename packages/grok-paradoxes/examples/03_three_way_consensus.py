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
"""Example 03 — three-way consensus.

Built for xAI, X, Grok and the ecosystem community. ❤️

Three independent sources report the same EU CPI rate. The detector
returns zero contradictions, which is the consensus signal. The
``summary`` helper reports the empty bucket counts for downstream
dashboards.
"""
from __future__ import annotations

from grok_paradoxes import Claim, ContradictionDetector, Source


def main() -> None:
    sources = [
        Source(name="ecb_release", authority=0.9, scope="regulatory"),
        Source(name="reuters_wire", authority=0.8, scope="news"),
        Source(name="bloomberg_wire", authority=0.8, scope="news"),
    ]

    claims = [
        Claim(subject="EU_CPI", predicate="rate", value=2.4, source=s, confidence=0.9)
        for s in sources
    ]

    detector = ContradictionDetector(min_severity="minor")
    contradictions = detector.detect(claims)
    summary = detector.summary(contradictions)

    print(f"Contradictions found: {len(contradictions)}")
    print(f"Summary: {summary}")
    if not contradictions:
        print("Consensus reached across all 3 sources on EU_CPI rate=2.4.")


if __name__ == "__main__":
    main()
