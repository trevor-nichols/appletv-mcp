"""PNG header inspection."""

import struct

from appletv_mcp.infrastructure.screen_capture import PngInfo, inspect_png
from tests.helpers.png import PNG_SIGNATURE, make_png


def test_inspect_png_reads_dimensions() -> None:
    assert inspect_png(make_png(3, 2)) == PngInfo(width=3, height=2, size=len(make_png(3, 2)))


def test_inspect_png_rejects_non_png_and_truncated_input() -> None:
    assert inspect_png(b"") is None
    assert inspect_png(b"GIF89a" + b"\x00" * 40) is None
    assert inspect_png(PNG_SIGNATURE) is None
    assert inspect_png(make_png()[:20]) is None


def test_inspect_png_requires_ihdr_first_with_positive_dimensions() -> None:
    valid = make_png()
    wrong_chunk = valid[:12] + b"IDAT" + valid[16:]
    assert inspect_png(wrong_chunk) is None
    zero_width = valid[:16] + struct.pack(">II", 0, 1) + valid[24:]
    assert inspect_png(zero_width) is None
    bad_length = valid[:8] + struct.pack(">I", 12) + valid[12:]
    assert inspect_png(bad_length) is None
