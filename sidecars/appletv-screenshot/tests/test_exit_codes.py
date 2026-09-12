from appletv_screenshot.exit_codes import CONTRACT_VERSION, ExitCode


def test_exit_code_table_is_the_published_contract() -> None:
    assert {member.name: int(member) for member in ExitCode} == {
        "SUCCESS": 0,
        "USAGE": 2,
        "DEVICE_NOT_FOUND": 10,
        "AMBIGUOUS_DEVICE": 11,
        "PAIRING_REQUIRED": 12,
        "TUNNEL_UNAVAILABLE": 13,
        "CAPTURE_FAILED": 14,
        "OUTPUT_WRITE_FAILED": 15,
        "CAPTURE_TIMEOUT": 16,
        "CONFIG_INVALID": 17,
    }
    assert CONTRACT_VERSION == 1


def test_usage_matches_argparse_exit_status() -> None:
    assert ExitCode.USAGE == 2
