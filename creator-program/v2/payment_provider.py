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
"""Payment-provider abstraction.

Two concrete providers ship with the scaffold:

  MockPaymentProvider  — in-memory dict; deterministic; used by tests and dev.
  StripePaymentProvider — calls real Stripe APIs via the `stripe` library.
                          Production keys are NOT permitted in this scaffold;
                          the constructor enforces that the key starts with
                          `sk_test_`.

A `get_provider(name)` factory returns the right concrete provider by name.
Real Stripe calls are guarded by the test-mode key check; live transactions
still require manual review and an explicit production-key migration that is
out of scope for the scaffold.
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Optional

from .tier_manager import Tier


# Tier -> Stripe price ID mapping. Stripe price IDs are environment-specific;
# the values below are placeholders that map test-mode prices configured in
# the Stripe test dashboard. Real values are loaded from environment variables
# so this module never embeds tenant-specific configuration.
_STRIPE_PRICE_BY_TIER: Dict[Tier, str] = {
    Tier.PREMIUM: os.environ.get("STRIPE_PRICE_PREMIUM", "price_premium_test"),
}


class PaymentProvider(ABC):
    """Abstract payment provider.

    Concrete providers handle subscriptions and creator payouts. All money
    movement is delegated to this layer; tier_manager.py never talks to a
    payment API directly.
    """

    @abstractmethod
    def create_subscription(self, creator_id: str, tier: Tier) -> str:
        """Create a subscription for a creator and return its provider id."""

    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel an existing subscription. Returns True on success."""

    @abstractmethod
    def get_subscription_status(self, subscription_id: str) -> str:
        """Return the provider's status string ('active', 'canceled', and similar)."""

    @abstractmethod
    def process_payout(self, creator_id: str, amount_usd: float) -> str:
        """Send a revenue-share payout to a creator. Returns the transfer id."""


class StripePaymentProvider(PaymentProvider):
    """Stripe-backed payment provider.

    The constructor reads `$env:STRIPE_API_KEY` and refuses to start unless the
    key begins with `sk_test_`. Production keys are NOT permitted in this
    scaffold — promotion to live keys requires a separate review.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("STRIPE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "STRIPE_API_KEY is not set. Use $env:STRIPE_API_KEY = 'sk_test_...' "
                "in PowerShell before instantiating StripePaymentProvider."
            )
        if not api_key.startswith("sk_test_"):
            raise RuntimeError(
                "Production Stripe keys are not permitted in this scaffold. "
                "Use a test-mode key (prefix 'sk_test_')."
            )
        # Lazy import keeps `stripe` an optional dependency for callers that
        # only need MockPaymentProvider (tests, local dev without Stripe).
        import stripe  # type: ignore[import-not-found]

        stripe.api_key = api_key
        self._stripe = stripe

    def create_subscription(self, creator_id: str, tier: Tier) -> str:
        price_id = _STRIPE_PRICE_BY_TIER.get(tier)
        if not price_id:
            raise ValueError(f"No Stripe price configured for tier={tier!r}")
        sub = self._stripe.Subscription.create(
            customer=creator_id,
            items=[{"price": price_id}],
            metadata={"creator_id": creator_id, "tier": tier.value},
        )
        return str(sub["id"])

    def cancel_subscription(self, subscription_id: str) -> bool:
        result = self._stripe.Subscription.modify(
            subscription_id, cancel_at_period_end=True
        )
        return bool(result.get("cancel_at_period_end"))

    def get_subscription_status(self, subscription_id: str) -> str:
        sub = self._stripe.Subscription.retrieve(subscription_id)
        return str(sub["status"])

    def process_payout(self, creator_id: str, amount_usd: float) -> str:
        if amount_usd <= 0:
            raise ValueError("amount_usd must be positive")
        # Stripe expects amount in the smallest currency unit (cents for USD).
        transfer = self._stripe.Transfer.create(
            amount=int(round(amount_usd * 100)),
            currency="usd",
            destination=creator_id,
            metadata={"creator_id": creator_id, "kind": "creator-program-revshare"},
        )
        return str(transfer["id"])


class MockPaymentProvider(PaymentProvider):
    """In-memory payment provider used by tests and local development.

    Deterministic: subscription ids are `sub_mock_<uuid4>` and payouts are
    recorded in a dict keyed by transfer id.
    """

    def __init__(self) -> None:
        self._subscriptions: Dict[str, Dict[str, object]] = {}
        self._payouts: Dict[str, Dict[str, object]] = {}

    def create_subscription(self, creator_id: str, tier: Tier) -> str:
        sub_id = f"sub_mock_{uuid.uuid4().hex[:12]}"
        self._subscriptions[sub_id] = {
            "creator_id": creator_id,
            "tier": tier.value,
            "status": "active",
        }
        return sub_id

    def cancel_subscription(self, subscription_id: str) -> bool:
        if subscription_id not in self._subscriptions:
            return False
        self._subscriptions[subscription_id]["status"] = "canceled"
        return True

    def get_subscription_status(self, subscription_id: str) -> str:
        sub = self._subscriptions.get(subscription_id)
        if not sub:
            return "not_found"
        return str(sub["status"])

    def process_payout(self, creator_id: str, amount_usd: float) -> str:
        if amount_usd <= 0:
            raise ValueError("amount_usd must be positive")
        transfer_id = f"tr_mock_{uuid.uuid4().hex[:12]}"
        self._payouts[transfer_id] = {
            "creator_id": creator_id,
            "amount_usd": amount_usd,
        }
        return transfer_id

    # Helpers exposed for tests; not part of the abstract interface.
    def list_subscriptions(self) -> Dict[str, Dict[str, object]]:
        return dict(self._subscriptions)

    def list_payouts(self) -> Dict[str, Dict[str, object]]:
        return dict(self._payouts)


def get_provider(name: str = "mock") -> PaymentProvider:
    """Factory: return a concrete PaymentProvider by name.

    Supported names: 'mock', 'stripe'. Unknown names raise ValueError.
    """
    normalized = (name or "").strip().lower()
    if normalized == "mock":
        return MockPaymentProvider()
    if normalized == "stripe":
        return StripePaymentProvider()
    raise ValueError(f"Unknown payment provider: {name!r}")
