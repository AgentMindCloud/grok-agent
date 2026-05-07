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
#
# Built for xAI, X, Grok and the ecosystem community.
"""Creator Program v2 — package marker.

The paid-tier scaffold (tier_manager / payment_provider / premium_gate) was
removed in P172/post-P172 cleanup as dead code with zero production callers.
The submodule that remains is `curation/`, which is wired to a live cron in
.github/workflows/curation-cadence.yml.

Importing this package directly requires either path-based discovery (pytest)
or a sys.path entry for the parent `creator-program/` directory because that
directory name contains a hyphen. The curation tests under
`curation/tests/conftest.py` register this package as `grok_creator_v2` at
test-collection time.
"""

__all__: list[str] = []
