"""Lightweight PNG structure check. No imaging library, no pixel decode."""

import struct
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IHDR_LENGTH = 13
_CHUNK_HEADER = 8
_CHUNK_CRC = 4


@dataclass(frozen=True, slots=True)
class PngInfo:
    width: int
    height: int
    size: int


def inspect_png(data: bytes) -> PngInfo | None:
    """Return header facts for a plausible PNG, or `None` when `data` is not one.

    The check walks chunks until a complete IEND. It requires IHDR first, at least
    one IDAT, and no chunk that extends past the buffer. CRCs and pixel data are
    not verified; the helper hands over the device's own encoder output unchanged.
    Bytes after IEND are ignored so a trailing encoder trailer does not fail.
    """

    if not data.startswith(PNG_SIGNATURE):
        return None
    offset = len(PNG_SIGNATURE)
    width = 0
    height = 0
    saw_ihdr = False
    saw_idat = False
    while offset + _CHUNK_HEADER <= len(data):
        length, kind = struct.unpack(">I4s", data[offset : offset + _CHUNK_HEADER])
        chunk_end = offset + _CHUNK_HEADER + length + _CHUNK_CRC
        if chunk_end > len(data):
            return None
        if not saw_ihdr:
            if kind != b"IHDR" or length != _IHDR_LENGTH:
                return None
            dim_at = offset + _CHUNK_HEADER
            width, height = struct.unpack(">II", data[dim_at : dim_at + 8])
            if width == 0 or height == 0:
                return None
            saw_ihdr = True
        elif kind == b"IHDR":
            return None
        elif kind == b"IDAT":
            saw_idat = True
        elif kind == b"IEND":
            if length != 0 or not saw_idat:
                return None
            return PngInfo(width=width, height=height, size=len(data))
        offset = chunk_end
    return None
