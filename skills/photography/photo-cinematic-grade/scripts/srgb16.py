# Optional 16-bit SDR sRGB PNG export for AUDIT-AND-IDEAS.md 3.2.
# New implementation, not recovered historical prototype code.
# PNG specification: https://www.w3.org/TR/png-3/
# RGB color type 2; 16-bit samples in network byte order; filter 0;
# zlib-compressed IDAT and iCCP, with standard PNG CRC-32 checksums.
# No implicit transfer function, ICC conversion, gamut clipping or dithering.
# Caller supplies encoded sRGB, after explicit gamut handling.
from pathlib import Path
import struct
from hashlib import sha256
import zlib

import numpy as np

from image_io import InputError, MAX_PIXELS

PROFILE = Path(__file__).resolve().parent.parent / "assets" / "srgb-output.icc"
PROFILE_SHA256 = 'e4ec1dcf49e54b320546ca0f33c6d661278599526a3075c1051acfb8129cbaaf'
QUANTIZE_ALGORITHM = "encoded-srgb16-half-up-no-dither-v1"


def quantize_srgb16(encoded):
    # Final normalized encoded-sRGB -> uint16, nearest integer, ties upward.
    # The 65535 maximum follows 2**16 - 1, not a creative coefficient.
    # Reject even one ULP outside [0,1]; gamut losses must be reported upstream.
    try:
        raw = np.asarray(encoded)
        if (raw.dtype.kind not in "iuf" or not raw.size or raw.ndim == 0
                or raw.shape[-1] != 3):
            raise ValueError
        values = raw.astype(np.float64, copy=True)
    except (ValueError, TypeError, OverflowError):
        raise InputError("expected nonempty real RGB triples in encoded sRGB") from None
    if not np.all(np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise InputError("encoded sRGB must be finite and in 0..1; map gamut first")
    code = values * 65535
    lower = np.floor(code)
    # Compare fractions rather than adding 0.5, preserving near-half boundaries.
    return (lower + (code - lower >= 0.5)).astype(np.uint16)


def _chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload)))


def encode_png16(samples):
    # Input is an HxWx3 uint16 array, already quantized, including big-endian
    # or non-contiguous arrays. No silent cast from uint8/float/signed integers.
    # Bundled ICC is a real generated sRGB profile with a fixed creation header,
    # so fresh processes never stamp a new time into identical PNG outputs.
    try:
        rgb = np.asarray(samples)
    except (ValueError, TypeError, OverflowError):
        raise InputError("expected HxWx3 uint16 RGB samples") from None
    if (rgb.dtype.kind != "u" or rgb.dtype.itemsize != 2 or rgb.ndim != 3
            or rgb.shape[-1] != 3 or not 0 < rgb.shape[0] * rgb.shape[1] <= MAX_PIXELS):
        raise InputError("expected HxWx3 uint16 RGB within the 24 megapixel limit")
    try:
        profile = PROFILE.read_bytes()
    except OSError:
        raise InputError("bundled sRGB output profile is unavailable") from None
    # Digest is measured from the actual locally generated asset, not a mock ICC.
    if sha256(profile).hexdigest() != PROFILE_SHA256:
        raise InputError("bundled sRGB output profile integrity check failed")
    height, width, _ = rgb.shape
    pieces = [b"\x89PNG\r\n\x1a\n",
              _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0)),
              _chunk(b"iCCP", b"sRGB\x00\x00" + zlib.compress(profile, level=9))]
    compressor = zlib.compressobj(level=9)
    for row in rgb:
        # One scanline at a time avoids a second full raw-image allocation.
        compressed = compressor.compress(b"\x00" + row.astype(">u2", copy=False).tobytes())
        if compressed:
            pieces.append(_chunk(b"IDAT", compressed))
    pieces.append(_chunk(b"IDAT", compressor.flush()))
    pieces.append(_chunk(b"IEND", b""))
    return b"".join(pieces)
