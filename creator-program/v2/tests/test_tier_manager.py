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
"""Unit tests for Creator Program v2 tier_manager + premium_gate.

The conftest in this directory loads `creator-program/v2` under the alias
`grok_creator_v2` because the parent folder name contains a hyphen. All test
imports go through that alias.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# These imports rely on conftest.py loading the v2 package as `grok_creator_v2`.
from grok_creator_v2 import (  # noqa: E402  pylint: disable=wrong-import-position
    CreatorAccount,
    MockPaymentProvider,
    Tier,
    TierFeatures,
    downgrade_to_free,
    get_tier_features,
    is_premium,
    load_account,
    requires_premium,
    save_account,
    upgrade_to_premium,
)
from grok_creator_v2 import tier_manager  # noqa: E402
from grok_creator_v2 import premium_gate  # noqa: E402


@pytest.fixture(autouse=True)
def _redirect_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the on-disk accounts directory into pytest's tmp_path.

    Both modules (tier_manager + premium_gate) read the storage root via
    `tier_manager._storage_root`; patching one location is enough because
    premium_gate imports `load_account` which closes over that resolver.
    """
    accounts_dir = tmp_path / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tier_manager, "_storage_root", lambda: accounts_dir)
    return accounts_dir


def test_tier_enum_has_two_values() -> None:
    assert {t.value for t in Tier} == {"free", "premium"}
    assert Tier.FREE.value == "free"
    assert Tier.PREMIUM.value == "premium"


def test_tier_features_defaults_for_free() -> None:
    features = get_tier_features(Tier.FREE)
    assert isinstance(features, TierFeatures)
    assert features.advanced_templates is False
    assert features.priority_support is False
    assert features.analytics_dashboard is False
    assert features.weekly_curation_pin is False
    assert features.revenue_share_eligible is False


def test_tier_features_premium_has_all_flags() -> None:
    features = get_tier_features(Tier.PREMIUM)
    assert features.advanced_templates is True
    assert features.priority_support is True
    assert features.analytics_dashboard is True
    assert features.weekly_curation_pin is True
    assert features.revenue_share_eligible is True


def test_creator_account_serialization_roundtrip() -> None:
    account = CreatorAccount(
        creator_id="creator_alpha",
        tier=Tier.PREMIUM,
        payment_provider_id="sub_mock_abc123",
        features=get_tier_features(Tier.PREMIUM),
    )
    raw = account.model_dump_json()
    restored = CreatorAccount.model_validate_json(raw)
    assert restored == account
    assert restored.tier is Tier.PREMIUM
    assert restored.features.priority_support is True


def test_upgrade_to_premium_changes_tier_and_features() -> None:
    free_account = CreatorAccount(creator_id="creator_beta")
    assert free_account.tier is Tier.FREE
    upgraded = upgrade_to_premium(free_account, payment_provider_id="sub_mock_xyz")
    assert upgraded.tier is Tier.PREMIUM
    assert upgraded.payment_provider_id == "sub_mock_xyz"
    assert upgraded.features.revenue_share_eligible is True
    # Original instance is untouched (immutable upgrade).
    assert free_account.tier is Tier.FREE
    assert free_account.payment_provider_id is None


def test_upgrade_to_premium_requires_provider_id() -> None:
    free_account = CreatorAccount(creator_id="creator_gamma")
    with pytest.raises(ValueError):
        upgrade_to_premium(free_account, payment_provider_id="")


def test_downgrade_to_free() -> None:
    premium_account = CreatorAccount(
        creator_id="creator_delta",
        tier=Tier.PREMIUM,
        payment_provider_id="sub_mock_keep",
        features=get_tier_features(Tier.PREMIUM),
    )
    downgraded = downgrade_to_free(premium_account)
    assert downgraded.tier is Tier.FREE
    assert downgraded.payment_provider_id is None
    assert downgraded.features.priority_support is False
    # Original premium instance unchanged.
    assert premium_account.tier is Tier.PREMIUM


def test_save_and_load_account_roundtrip() -> None:
    account = CreatorAccount(
        creator_id="creator_epsilon",
        tier=Tier.PREMIUM,
        payment_provider_id="sub_mock_save",
        features=get_tier_features(Tier.PREMIUM),
    )
    path = save_account(account)
    assert path.exists()
    assert path.name == "creator_epsilon.json"
    loaded = load_account("creator_epsilon")
    assert loaded == account


def test_load_account_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_account("creator_does_not_exist")


def test_premium_gate_blocks_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """A free creator cannot pass the @requires_premium gate; a premium one can.

    This test also exercises MockPaymentProvider to confirm the payment layer
    issues a deterministic subscription id used as the payment_provider_id.
    """
    provider = MockPaymentProvider()

    free_account = CreatorAccount(creator_id="creator_zeta")
    save_account(free_account)

    @requires_premium
    def premium_only_action(creator_id: str) -> str:
        return f"served:{creator_id}"

    # Free account is gated.
    assert is_premium("creator_zeta") is False
    with pytest.raises(PermissionError):
        premium_only_action("creator_zeta")

    # Upgrade through the mock payment provider, persist, and re-check.
    sub_id = provider.create_subscription("creator_zeta", Tier.PREMIUM)
    assert sub_id.startswith("sub_mock_")
    upgraded = upgrade_to_premium(free_account, payment_provider_id=sub_id)
    save_account(upgraded)

    assert is_premium("creator_zeta") is True
    assert premium_only_action("creator_zeta") == "served:creator_zeta"
    assert premium_only_action(creator_id="creator_zeta") == "served:creator_zeta"


def test_premium_context_manager_blocks_and_allows() -> None:
    free_account = CreatorAccount(creator_id="creator_eta")
    save_account(free_account)
    with pytest.raises(PermissionError):
        with premium_gate.premium_context("creator_eta"):
            raise AssertionError("body must not execute for free creators")

    upgraded = upgrade_to_premium(free_account, payment_provider_id="sub_mock_ctx")
    save_account(upgraded)
    entered = False
    with premium_gate.premium_context("creator_eta"):
        entered = True
    assert entered is True


def test_mock_payment_provider_lifecycle() -> None:
    provider = MockPaymentProvider()
    sub_id = provider.create_subscription("creator_theta", Tier.PREMIUM)
    assert provider.get_subscription_status(sub_id) == "active"
    assert provider.cancel_subscription(sub_id) is True
    assert provider.get_subscription_status(sub_id) == "canceled"
    transfer_id = provider.process_payout("creator_theta", amount_usd=42.5)
    assert transfer_id.startswith("tr_mock_")
    assert provider.list_payouts()[transfer_id]["amount_usd"] == 42.5
