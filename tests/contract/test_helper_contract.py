"""The exit-code table is shared with the `appletv-screenshot` helper by copy.

The helper is a separate project with its own dependencies, so this test loads its
stdlib-only `exit_codes.py` by path instead of importing the package.
"""

import importlib.util
from enum import IntEnum
from pathlib import Path

from appletv_mcp.infrastructure.screen_capture import (
    HELPER_CONTRACT_VERSION,
    HelperExitCode,
    error_for_exit_status,
)

SIDECAR_EXIT_CODES = (
    Path(__file__).resolve().parents[2]
    / "sidecars"
    / "appletv-screenshot"
    / "src"
    / "appletv_screenshot"
    / "exit_codes.py"
)


def _load_sidecar_table() -> tuple[int, dict[str, int]]:
    assert SIDECAR_EXIT_CODES.is_file(), f"helper exit codes missing at {SIDECAR_EXIT_CODES}"
    spec = importlib.util.spec_from_file_location("sidecar_exit_codes", SIDECAR_EXIT_CODES)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    exit_codes: type[IntEnum] = module.ExitCode
    contract_version: int = module.CONTRACT_VERSION
    return contract_version, {member.name: int(member) for member in exit_codes}


def test_sidecar_exit_codes_match_the_helper_contract() -> None:
    contract_version, sidecar_table = _load_sidecar_table()

    assert contract_version == HELPER_CONTRACT_VERSION
    assert sidecar_table == {member.name: int(member) for member in HelperExitCode}


def test_every_failure_code_maps_to_a_domain_error() -> None:
    for code in HelperExitCode:
        if code is HelperExitCode.SUCCESS:
            continue
        error = error_for_exit_status(int(code))
        assert error.message, f"{code.name} has no operator-facing message"
