"""Tiny valid PNG fixtures built without an imaging library."""

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def make_png(width: int = 1, height: int = 1, *, filler: bytes = b"") -> bytes:
    """Return a well-formed opaque grey RGB PNG of the given size.

    `filler` is appended as an ancillary chunk so tests can inflate the file
    to an arbitrary byte length while keeping it a valid PNG.
    """

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x80\x80\x80" * width
    idat = zlib.compress(row * height)
    chunks = [_chunk(b"IHDR", ihdr), _chunk(b"IDAT", idat)]
    if filler:
        chunks.append(_chunk(b"tEXt", b"pad\x00" + filler))
    chunks.append(_chunk(b"IEND", b""))
    return PNG_SIGNATURE + b"".join(chunks)


FAKE_SCREEN_PNG = make_png(2, 2)
