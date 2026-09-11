"""Deterministic application resolution. Fuzzy matches never auto-launch."""

import difflib

from agenai_appletv_mcp.domain.errors import AmbiguousAppError, AppNotFoundError
from agenai_appletv_mcp.domain.models.device import AppInfo


def resolve_app(query: str, apps: list[AppInfo]) -> AppInfo:
    """Resolve `query` to exactly one installed application.

    Order:
    1. Exact bundle identifier.
    2. Case-insensitive exact display name.
    3. Ambiguous names fail.
    4. Missing names fail, optionally suggesting close candidates.
    """

    requested = query.strip()
    if not requested:
        raise AppNotFoundError("Application name must not be empty.")

    for app in apps:
        if app.bundle_id == requested:
            return app

    normalized = requested.casefold()
    name_matches = [app for app in apps if (app.name or "").casefold() == normalized]
    if len(name_matches) == 1:
        return name_matches[0]
    if len(name_matches) > 1:
        identifiers = ", ".join(app.bundle_id for app in name_matches)
        raise AmbiguousAppError(
            f'Application "{requested}" is ambiguous. Matching bundle identifiers: {identifiers}.'
        )

    suggestion = _nearest_name(requested, apps)
    if suggestion:
        raise AppNotFoundError(
            f'Application "{requested}" was not found. Did you mean: {suggestion}?'
        )
    raise AppNotFoundError(f'Application "{requested}" was not found.')


def filter_apps(apps: list[AppInfo], query: str | None) -> list[AppInfo]:
    """Filter listed apps with case-insensitive substring matching."""

    if query is None:
        return list(apps)
    needle = query.strip().casefold()
    if not needle:
        return list(apps)
    return [
        app
        for app in apps
        if needle in app.bundle_id.casefold() or needle in (app.name or "").casefold()
    ]


def _nearest_name(requested: str, apps: list[AppInfo]) -> str | None:
    names = [app.name for app in apps if app.name]
    matches = difflib.get_close_matches(requested, names, n=1, cutoff=0.6)
    return matches[0] if matches else None
