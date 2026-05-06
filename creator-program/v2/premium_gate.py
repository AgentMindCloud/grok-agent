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
"""Premium gating — decorator + context manager + Streamlit helper.

Three gating surfaces:

  is_premium(creator_id)            — boolean check.
  @requires_premium                 — decorator that raises PermissionError
                                      when the wrapped callable is invoked
                                      with a non-premium creator_id.
  premium_context(creator_id)       — context manager yielding inside a
                                      premium-only block.
  gate_streamlit_tab(creator_id, .) — UI helper that hides a tab body and
                                      surfaces an upgrade prompt for free
                                      creators.

All four delegate to load_account; if the account file is missing the
creator is treated as FREE (i.e., gated). This is the safe default for paid
features: no record on disk -> no premium access.
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

from .tier_manager import Tier, load_account


F = TypeVar("F", bound=Callable[..., Any])

_DENIED_MESSAGE = (
    "This feature is locked to Creator Program v2 Premium. "
    "Upgrade in your account dashboard to unlock advanced templates, "
    "priority support, the analytics dashboard, weekly curation pins, "
    "and revenue-share eligibility."
)


def is_premium(creator_id: str) -> bool:
    """Return True iff the creator's persisted tier is PREMIUM."""
    try:
        account = load_account(creator_id)
    except FileNotFoundError:
        return False
    return account.tier is Tier.PREMIUM


def _resolve_creator_id(args: tuple, kwargs: dict) -> str:
    """Pull the creator_id from a call's args/kwargs, supporting both forms."""
    if "creator_id" in kwargs:
        creator_id = kwargs["creator_id"]
    elif args:
        creator_id = args[0]
    else:
        raise TypeError(
            "@requires_premium expects 'creator_id' as the first positional "
            "argument or a keyword argument."
        )
    if not isinstance(creator_id, str) or not creator_id:
        raise TypeError("creator_id must be a non-empty string")
    return creator_id


def requires_premium(func: F) -> F:
    """Decorator: raise PermissionError if the caller is not premium.

    The wrapped callable's first positional argument (or a `creator_id`
    keyword argument) is interpreted as the creator id.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        creator_id = _resolve_creator_id(args, kwargs)
        if not is_premium(creator_id):
            raise PermissionError(_DENIED_MESSAGE)
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


@contextmanager
def premium_context(creator_id: str) -> Iterator[None]:
    """Context manager that yields only when the creator is premium."""
    if not is_premium(creator_id):
        raise PermissionError(_DENIED_MESSAGE)
    yield


def gate_streamlit_tab(creator_id: str, tab_label: str) -> bool:
    """Return True if the tab should render, False if it must be hidden.

    For non-premium creators, surfaces a Streamlit error message that names
    the locked tab and prompts an upgrade. The streamlit import is lazy so
    this module can be imported in non-UI contexts without dragging the
    Streamlit dependency in.
    """
    if is_premium(creator_id):
        return True
    try:
        import streamlit as st  # type: ignore[import-not-found]
    except ImportError:
        # Streamlit not installed — caller is in a non-UI context; the False
        # return value alone is enough to gate the feature.
        return False
    st.error(
        f"'{tab_label}' is locked. {_DENIED_MESSAGE}"
    )
    return False
