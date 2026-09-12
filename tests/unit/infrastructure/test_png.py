"""PNG header inspection."""

import struct
import zlib

from appletv_mcp.infrastructure.screen_capture import PngInfo, inspect_png
from tests.helpers.png import PNG_SIGNATURE, make_png


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def test_inspect_png_reads_dimensions() -> None:
    assert inspect_png(make_png(3, 2)) == PngInfo(width=3, height=2, size=len(make_png(3, 2)))


def test_inspect_png_rejects_non_png_and_truncated_input() -> None:
    png = make_png()
    assert inspect_png(b"") is None
    assert inspect_png(b"GIF89a" + b"\x00" * 40) is None
    assert inspect_png(PNG_SIGNATURE) is None
    assert inspect_png(png[:20]) is None
    assert inspect_png(png[:33]) is None
    idat_payload_start = 33 + 8
    assert inspect_png(png[: idat_payload_start + 4]) is None
    assert inspect_png(png[:-12]) is None
    assert inspect_png(png[:-3]) is None


def test_inspect_png_rejects_ihdr_and_iend_without_idat() -> None:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    data = PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IEND", b"")
    assert inspect_png(data) is None


def test_inspect_png_requires_ihdr_first_with_positive_dimensions() -> None:
    valid = make_png()
    wrong_chunk = valid[:12] + b"IDAT" + valid[16:]
    assert inspect_png(wrong_chunk) is None
    zero_width = valid[:16] + struct.pack(">II", 0, 1) + valid[24:]
    assert inspect_png(zero_width) is None
    bad_length = valid[:8] + struct.pack(">I", 12) + valid[12:]
    assert inspect_png(bad_length) is None


def test_inspect_png_accepts_bytes_after_iend() -> None:
    png = make_png()
    assert inspect_png(png + b"trailer") == PngInfo(width=1, height=1, size=len(png) + 7)
