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
"""Tier manager — Pydantic v2 models + local-first JSON persistence.

The tier manager is the single source of truth for a creator's membership
status in Creator Program v2. Two tiers exist today:

  FREE     — every public template + community support.
  PREMIUM  — advanced templates, priority support, analytics dashboard,
             weekly curation pin, and revenue-share eligibility (subject to a
             payout policy defined in P128).

Storage is local-first: each account lives at
`$env:LOCALAPPDATA\\grok-agent\\creator-program\\accounts\\<creator_id>.json`.
On non-Windows runners (CI), the resolver falls back to
`~/AppData/Local/grok-agent/...` so the same path shape works everywhere.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Tier(str, Enum):
    """The two tiers offered by Creator Program v2."""

    FREE = "free"
    PREMIUM = "premium"


class TierFeatures(BaseModel):
    """Hard-coded feature flags per tier.

    Adding a new feature requires (a) adding the field here and (b) updating
    `get_tier_features` for both tiers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    advanced_templates: bool = False
    priority_support: bool = False
    analytics_dashboard: bool = False
    weekly_curation_pin: bool = False
    revenue_share_eligible: bool = False


class CreatorAccount(BaseModel):
    """A creator's tier record. Persisted as JSON, one file per creator."""

    model_config = ConfigDict(extra="forbid")

    creator_id: str = Field(..., min_length=1, max_length=128)
    tier: Tier = Tier.FREE
    joined_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    payment_provider_id: Optional[str] = None
    features: TierFeatures = Field(default_factory=TierFeatures)


def get_tier_features(tier: Tier) -> TierFeatures:
    """Return the hard-coded feature flag set for a tier.

    The mapping is intentionally hard-coded; tier features are not configurable
    by users and changes require a code review.
    """
    if tier is Tier.PREMIUM:
        return TierFeatures(
            advanced_templates=True,
            priority_support=True,
            analytics_dashboard=True,
            weekly_curation_pin=True,
            revenue_share_eligible=True,
        )
    if tier is Tier.FREE:
        return TierFeatures(
            advanced_templates=False,
            priority_support=False,
            analytics_dashboard=False,
            weekly_curation_pin=False,
            revenue_share_eligible=False,
        )
    raise ValueError(f"Unknown tier: {tier!r}")


def upgrade_to_premium(
    account: CreatorAccount, payment_provider_id: str
) -> CreatorAccount:
    """Return a new CreatorAccount with PREMIUM tier and payment provider id.

    The original account is not mutated; callers must persist the returned
    instance with `save_account` to make the change durable.
    """
    if not payment_provider_id:
        raise ValueError("payment_provider_id is required to upgrade to PREMIUM")
    return account.model_copy(
        update={
            "tier": Tier.PREMIUM,
            "payment_provider_id": payment_provider_id,
            "features": get_tier_features(Tier.PREMIUM),
        }
    )


def downgrade_to_free(account: CreatorAccount) -> CreatorAccount:
    """Return a new CreatorAccount with FREE tier and no payment provider id."""
    return account.model_copy(
        update={
            "tier": Tier.FREE,
            "payment_provider_id": None,
            "features": get_tier_features(Tier.FREE),
        }
    )


def _storage_root() -> Path:
    """Resolve the local-first accounts directory and ensure it exists.

    Honors `$env:LOCALAPPDATA` on Windows; falls back to
    `~/AppData/Local/grok-agent/creator-program/accounts` so CI runners on
    Linux see the same shape (the path is written, not parsed by the OS).
    """
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Local"
    accounts = root / "grok-agent" / "creator-program" / "accounts"
    accounts.mkdir(parents=True, exist_ok=True)
    return accounts


def _account_path(creator_id: str) -> Path:
    """Resolve the JSON file path for a creator id, validating the id shape."""
    if not creator_id or "/" in creator_id or "\\" in creator_id:
        raise ValueError(f"Invalid creator_id: {creator_id!r}")
    return _storage_root() / f"{creator_id}.json"


def load_account(creator_id: str) -> CreatorAccount:
    """Load a creator's account from disk, raising FileNotFoundError on miss."""
    path = _account_path(creator_id)
    if not path.exists():
        raise FileNotFoundError(f"No account on disk for creator_id={creator_id!r}")
    return CreatorAccount.model_validate_json(path.read_text(encoding="utf-8"))


def save_account(account: CreatorAccount) -> Path:
    """Write the account to disk and return the resolved Path."""
    path = _account_path(account.creator_id)
    path.write_text(account.model_dump_json(indent=2), encoding="utf-8")
    return path
