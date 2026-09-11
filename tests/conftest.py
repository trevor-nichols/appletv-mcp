"""Broad pytest configuration. Keep fixtures small; helpers live elsewhere."""

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("APPLE_TV_INTEGRATION_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(
        reason="live Apple TV tests are opt-in (APPLE_TV_INTEGRATION_TESTS=1)"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
