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
"""Creator Program v2 — paid-tier scaffolding.

Public API (re-exported from the modules in this package):

  Tier models / persistence  -> tier_manager
  Payment-provider abstraction -> payment_provider
  Premium gating helpers     -> premium_gate

Importing this package directly requires either path-based discovery (pytest)
or a sys.path entry for the parent `creator-program/` directory because that
directory name contains a hyphen. The tests under tests/ use a conftest.py to
insert this package's parent on sys.path at collection time.
"""

from .tier_manager import (
    CreatorAccount,
    Tier,
    TierFeatures,
    downgrade_to_free,
    get_tier_features,
    load_account,
    save_account,
    upgrade_to_premium,
)
from .payment_provider import (
    MockPaymentProvider,
    PaymentProvider,
    StripePaymentProvider,
    get_provider,
)
from .premium_gate import (
    gate_streamlit_tab,
    is_premium,
    premium_context,
    requires_premium,
)

__all__ = [
    "CreatorAccount",
    "MockPaymentProvider",
    "PaymentProvider",
    "StripePaymentProvider",
    "Tier",
    "TierFeatures",
    "downgrade_to_free",
    "gate_streamlit_tab",
    "get_provider",
    "get_tier_features",
    "is_premium",
    "load_account",
    "premium_context",
    "requires_premium",
    "save_account",
    "upgrade_to_premium",
]
