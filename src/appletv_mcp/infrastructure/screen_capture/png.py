"""Lightweight PNG header inspection. No imaging library, no decoding."""

import struct
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IHDR_LENGTH = 13
_MIN_PNG_LENGTH = len(PNG_SIGNATURE) + 4 + 4 + _IHDR_LENGTH + 4


@dataclass(frozen=True, slots=True)
class PngInfo:
    width: int
    height: int
    size: int


def inspect_png(data: bytes) -> PngInfo | None:
    """Return header facts for a plausible PNG, or `None` when `data` is not one.

    The check covers the eight-byte signature and a well-formed IHDR chunk with
    positive dimensions. It does not verify CRCs or decode pixel data; the
    helper hands over the device's own encoder output unchanged.
    """

    if len(data) < _MIN_PNG_LENGTH or not data.startswith(PNG_SIGNATURE):
        return None
    chunk_length, chunk_type = struct.unpack(">I4s", data[8:16])
    if chunk_type != b"IHDR" or chunk_length != _IHDR_LENGTH:
        return None
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        return None
    return PngInfo(width=width, height=height, size=len(data))
