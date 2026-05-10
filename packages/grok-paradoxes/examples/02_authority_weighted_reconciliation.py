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
"""Example 02 — authority-weighted reconciliation.

Built for xAI, X, Grok and the ecosystem community. ❤️

Two sources disagree on ACME's quarterly revenue. One is an SEC filing
(authority=0.9), the other is an anonymous rumor account (authority=0.4).
``weight_authorities`` prefers the higher-authority claim and explains why.
"""
from __future__ import annotations

from grok_paradoxes import Claim, Source, weight_authorities


def main() -> None:
    high = Source(name="sec_filing", authority=0.9, scope="regulatory")
    low = Source(name="rumor_account", authority=0.4, scope="social")

    claims = [
        Claim(subject="ACME", predicate="revenue", value=120, source=high, confidence=0.85),
        Claim(subject="ACME", predicate="revenue", value=180, source=low, confidence=0.85),
    ]

    suggestion = weight_authorities(claims)

    print("Reconciliation suggestion:")
    print(f"  preferred value : {suggestion.preferred_claim.value}")
    print(f"  preferred source: {suggestion.preferred_claim.source.name}")
    print(f"  rationale       : {suggestion.rationale}")
    print(f"  confidence_delta: {suggestion.confidence_delta:+.3f}")


if __name__ == "__main__":
    main()
