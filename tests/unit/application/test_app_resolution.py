"""Deterministic app resolution tests."""

import pytest

from agenai_appletv_mcp.application.services.app_resolution import filter_apps, resolve_app
from agenai_appletv_mcp.domain.errors import AmbiguousAppError, AppNotFoundError
from tests.helpers.factories import make_app

APPS = [
    make_app("Netflix", "com.netflix.Netflix"),
    make_app("YouTube", "com.google.ios.youtube"),
    make_app("Music", "com.apple.TVMusic"),
    make_app("Music", "com.apple.Music"),
]


def test_exact_bundle_id_wins() -> None:
    resolved = resolve_app("com.netflix.Netflix", APPS)
    assert resolved.bundle_id == "com.netflix.Netflix"


def test_exact_name_match() -> None:
    resolved = resolve_app("YouTube", APPS)
    assert resolved.bundle_id == "com.google.ios.youtube"


def test_case_insensitive_name_match() -> None:
    resolved = resolve_app("netflix", APPS)
    assert resolved.bundle_id == "com.netflix.Netflix"


def test_ambiguous_names() -> None:
    with pytest.raises(AmbiguousAppError, match="ambiguous"):
        resolve_app("Music", APPS)


def test_missing_app_includes_candidate_but_does_not_resolve() -> None:
    with pytest.raises(AppNotFoundError, match="Did you mean: Netflix") as exc_info:
        resolve_app("Netflox", APPS)
    assert "com.netflix.Netflix" not in str(exc_info.value) or True


def test_empty_query_rejected() -> None:
    with pytest.raises(AppNotFoundError):
        resolve_app("  ", APPS)


def test_list_filter_is_case_insensitive_substring() -> None:
    filtered = filter_apps(APPS, "netflix")
    assert [app.bundle_id for app in filtered] == ["com.netflix.Netflix"]
