<!--
Copyright 2026 AgentMindCloud
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Creator Program v2 — Paid-Tier Scaffolding

> Built for xAI, X, Grok and the ecosystem community. ❤️

This package is the foundation for the Creator Program v2 paid tier
introduced in Phase 6. It ships three production-ready modules — tier
modeling, payment-provider abstraction, and premium gating — plus a unit
test suite that runs on Windows 11 + PowerShell.

P127 lays the scaffold. The next prompt (P128) plugs in the curation cadence
harness and the revenue-share payout policy on top of `process_payout`.

> ⚠️ **Not financial advice.** This tool provides information only.
> Always consult a licensed financial advisor before making decisions.

> ⚠️ **Not tax advice.** Tax obligations vary by jurisdiction.
> Consult a licensed tax professional. Especially relevant for
> Vietnam-resident creators with international platform earnings.

---

## Quickstart (Windows 11 + PowerShell)

```powershell
# 1. Install runtime + test dependencies (Pydantic v2 is required).
python -m pip install "pydantic>=2.7" stripe pytest

# 2. Configure Stripe in TEST MODE ONLY.
#    The scaffold refuses to start with a live key (must begin with sk_test_).
$env:STRIPE_API_KEY = "sk_test_replace_me_with_a_real_test_key"

# 3. Run the unit test suite.
python -m pytest creator-program/v2/tests/ -v
```

You should see all tests pass. The tests redirect on-disk storage into a
pytest tmp_path so your real `$env:LOCALAPPDATA\grok-agent\` is never touched.

---

## Architecture overview

Three modules, each with one clear responsibility:

| Module                     | Responsibility                                                        |
| -------------------------- | --------------------------------------------------------------------- |
| `tier_manager.py`          | Pydantic v2 tier models + local-first JSON persistence per creator.   |
| `payment_provider.py`      | Abstract `PaymentProvider` ABC + `StripePaymentProvider` (test-mode)  |
|                            | + `MockPaymentProvider` for tests, plus a `get_provider()` factory.   |
| `premium_gate.py`          | `is_premium`, `@requires_premium` decorator, `premium_context`        |
|                            | manager, and `gate_streamlit_tab` UI helper.                          |

The package's `__init__.py` re-exports the public API. Importing from inside
the repo (which uses a hyphenated `creator-program/` folder name) is handled
by `tests/conftest.py`; production callers can adopt the same importlib
pattern or rename the folder in their own deployment.

---

## Free vs Premium feature table

| Feature                  | FREE  | PREMIUM |
| ------------------------ | :---: | :-----: |
| Advanced templates       |   —   |   ✓     |
| Priority support         |   —   |   ✓     |
| Analytics dashboard      |   —   |   ✓     |
| Weekly curation pin      |   —   |   ✓     |
| Revenue-share eligible   |   —   |   ✓     |

The mapping is hard-coded in `tier_manager.get_tier_features`. Adding a new
flag requires a code review — feature flags are not user-configurable.

---

## Local-first storage

Each creator account is persisted to a single JSON file at:

```
$env:LOCALAPPDATA\grok-agent\creator-program\accounts\<creator_id>.json
```

On non-Windows runners (e.g. CI), the resolver falls back to
`~/AppData/Local/grok-agent/creator-program/accounts/`. Path shape is
identical across operating systems, so test fixtures and Windows production
paths agree.

The serialized record includes only:

- `creator_id`
- `tier` (`free` or `premium`)
- `joined_at` (UTC ISO-8601)
- `payment_provider_id` (the Stripe subscription id, when premium)
- `features` (the resolved feature flag set)

No PII beyond the creator id is stored. No analytics. No telemetry. Clearing
the JSON file revokes all premium privileges immediately.

---

## Stripe test-mode warning

`StripePaymentProvider` reads `$env:STRIPE_API_KEY` and refuses to start
unless the key begins with `sk_test_`. Production keys are NOT permitted in
this scaffold. Promotion to live keys requires:

1. A separate review (security + finance).
2. A migration plan covering refunds, chargebacks, and Vietnam-specific tax
   reporting.
3. A signed agreement with the creator, surfaced through the UI before any
   premium charge is captured.

Until those land, every Stripe call here is bound to test-mode price ids and
test-mode customer ids. `MockPaymentProvider` is the recommended provider
for development; switch to Stripe only when you have a real test-mode key.

```powershell
# Verify the guard fires when no key is set.
$env:STRIPE_API_KEY = $null
python -c "from grok_creator_v2 import StripePaymentProvider; StripePaymentProvider()"
# RuntimeError: STRIPE_API_KEY is not set...
```

---

## Public API surface

```python
from grok_creator_v2 import (
    CreatorAccount,
    Tier,
    TierFeatures,
    upgrade_to_premium,
    downgrade_to_free,
    save_account,
    load_account,
    is_premium,
    requires_premium,
    premium_context,
    gate_streamlit_tab,
    PaymentProvider,
    MockPaymentProvider,
    StripePaymentProvider,
    get_provider,
)
```

The alias `grok_creator_v2` is established by `tests/conftest.py` because
the on-disk folder name is `creator-program/v2/` and the hyphen blocks a
plain `import creator-program.v2`. In application code, use the same
importlib pattern shown in `conftest.py` or vendor the package under a
non-hyphenated name in your deployment artifact.

---

## Running tests

```powershell
# Run the full test module.
python -m pytest creator-program/v2/tests/ -v

# Run a single test.
python -m pytest creator-program/v2/tests/test_tier_manager.py::test_premium_gate_blocks_free -v

# Show coverage (requires pytest-cov from pyproject [dev] extras).
python -m pytest creator-program/v2/tests/ --cov=creator-program/v2 --cov-report=term-missing
```

Tests use pytest's `tmp_path` and `monkeypatch` fixtures to redirect the
storage root, so the suite is hermetic and never writes to the real
`$env:LOCALAPPDATA` tree.

---

## Future work

- **P128 — Curation cadence harness.** Builds the weekly pin scheduler that
  consumes `weekly_curation_pin` and the revenue-share payout policy that
  consumes `process_payout` from the payment provider.
- **P129+ — Phase 6 follow-ups.** Contributor guide, paid-tier dashboard,
  and the production-key migration runbook listed under "Stripe test-mode
  warning" above.

---

> Built for xAI, X, Grok and the ecosystem community. ❤️
