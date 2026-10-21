# Precision-preserving input boundary for AUDIT-AND-IDEAS.md 3.3.
# New implementation, not recovered prototype code. No creative coefficients.
# PNG structure/filter definitions: https://www.w3.org/TR/png-3/
# Supports noninterlaced opaque RGB16 PNG and the existing RGB8/L8 loader.
# Arbitrary 16-bit ICC conversion is deliberately NOT delegated to Pillow RGB8.
# Only the exact bundled standard sRGB ICC is accepted for tagged RGB16 input;
# untagged input requires explicit sRGB confirmation. Other profiles fail closed.
from dataclasses import dataclass
import hashlib
import struct
import warnings
import zlib

import numpy as np
from PIL import Image

import image_io
from image_io import InputError, MAX_ICC_BYTES, MAX_PIXELS
from srgb16 import PROFILE_SHA256

ALGORITHM = "snapshot-srgb-float64-input-v1"
SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass
class FloatImage:
    # Encoded display-referred sRGB, normalized float64; not scene-linear RGB.
    encoded_srgb: np.ndarray
    provenance: dict


def _inflate(data, limit):
    # Bound BEFORE allocating decompressed output. Require exactly one complete
    # zlib stream, not a truncated stream, concatenated streams or trailing data.
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(data, limit + 1)
    except zlib.error:
        raise InputError("invalid PNG compressed stream") from None
    if (len(raw) > limit or decoder.unconsumed_tail or not decoder.eof
            or decoder.unused_data):
        raise InputError("PNG compressed stream exceeds its bound or is incomplete")
    return raw


def _chunks(blob):
    if not blob.startswith(SIGNATURE):
        raise InputError("expected a PNG snapshot")
    offset, chunks, seen = 8, [], set()
    in_data = False
    data_ended = False
    single = {b"IHDR", b"PLTE", b"iCCP", b"sRGB", b"gAMA", b"cHRM", b"eXIf"}
    before_data = single - {b"eXIf"}
    while offset < len(blob):
        if len(blob) - offset < 12:
            raise InputError("truncated PNG chunk")
        length, = struct.unpack_from(">I", blob, offset)
        end = offset + 12 + length
        if length > 0x7fffffff or end > len(blob):
            raise InputError("invalid or truncated PNG chunk length")
        kind = blob[offset + 4:offset + 8]
        if any(not (65 <= c <= 90 or 97 <= c <= 122) for c in kind) or kind[2] & 32:
            raise InputError("invalid PNG chunk type")
        payload = blob[offset + 8:end - 4]
        checksum, = struct.unpack_from(">I", blob, end - 4)
        if zlib.crc32(kind + payload) != checksum:
            raise InputError("PNG chunk checksum mismatch")
        if not chunks and kind != b"IHDR":
            raise InputError("PNG IHDR must be first")
        if kind in single and kind in seen:
            raise InputError("duplicate PNG structural or color metadata")
        if kind in before_data and in_data:
            raise InputError("PNG structural or color metadata follows image data")
        if kind in {b"acTL", b"fcTL", b"fdAT"}:
            raise InputError("animated PNG is not supported")
        if kind in {b"cICP", b"mDCv", b"cLLi"}:
            raise InputError("cICP/HDR-signaled PNG requires a separate color-managed export")
        if kind == b"tRNS":
            raise InputError("only opaque RGB16 PNG is supported")
        if not kind[0] & 32 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            raise InputError("unknown critical PNG chunk")
        if kind == b"IDAT":
            if data_ended:
                raise InputError("PNG IDAT chunks must be consecutive")
            in_data = True
        elif in_data:
            data_ended = True
        chunks.append((kind, payload))
        seen.add(kind)
        offset = end
        if kind == b"IEND":
            if payload or not in_data or offset != len(blob):
                raise InputError("invalid PNG end or trailing data")
            return chunks
    raise InputError("PNG IEND is missing")


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _samples(raw, width, height):
    # PNG filters act on BYTES, with six bytes per RGB16 pixel. Carry between
    # high/low sample bytes is not part of filtering. Arithmetic is modulo 256.
    stride = width * 6
    if len(raw) != height * (stride + 1):
        raise InputError("PNG decompressed scanline length mismatch")
    rows = np.empty((height, stride), dtype=np.uint8)
    previous = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind = raw[start]
        row = bytearray(raw[start + 1:start + stride + 1])
        if kind > 4:
            raise InputError("unknown PNG scanline filter")
        if kind == 1:
            # Each of the six byte lanes has its own cumulative sum.
            values = np.frombuffer(row, dtype=np.uint8).reshape(width, 6)
            row = bytearray(np.cumsum(values, axis=0, dtype=np.uint64).astype(np.uint8).tobytes())
        elif kind == 2:
            row = bytearray((np.frombuffer(row, dtype=np.uint8)
                             + np.frombuffer(previous, dtype=np.uint8)).tobytes())
        elif kind in (3, 4):
            for i in range(stride):
                a = row[i - 6] if i >= 6 else 0
                b = previous[i]
                c = previous[i - 6] if i >= 6 else 0
                predictor = (a + b) // 2 if kind == 3 else _paeth(a, b, c)
                row[i] = (row[i] + predictor) & 255
        rows[y] = np.frombuffer(row, dtype=np.uint8)
        previous = row
    return rows.view(">u2").reshape(height, width, 3).astype(np.uint16)


def _color(metadata, assume_srgb):
    gamma = metadata.get(b"gAMA")
    chroma = metadata.get(b"cHRM")
    srgb = metadata.get(b"sRGB")
    if gamma is not None and (len(gamma) != 4 or int.from_bytes(gamma, "big") == 0):
        raise InputError("invalid PNG gamma")
    if chroma is not None and len(chroma) != 32:
        raise InputError("invalid PNG chromaticities")
    if srgb is not None and (len(srgb) != 1 or srgb[0] > 3):
        raise InputError("invalid PNG sRGB rendering intent")
    if b"iCCP" in metadata:
        if srgb is not None:
            raise InputError("simultaneous PNG ICC and sRGB declarations are ambiguous")
        payload = metadata[b"iCCP"]
        end = payload.find(b"\x00")
        if not 1 <= end <= 79 or len(payload) < end + 3 or payload[end + 1] != 0:
            raise InputError("invalid PNG ICC container")
        name = payload[:end]
        if (any(not (32 <= c <= 126 or 161 <= c <= 255) for c in name)
                or name.startswith(b" ") or name.endswith(b" ") or b"  " in name):
            raise InputError("invalid PNG ICC profile name")
        profile = _inflate(payload[end + 2:], MAX_ICC_BYTES)
        digest = hashlib.sha256(profile).hexdigest()
        if digest != PROFILE_SHA256:
            raise InputError("16-bit ICC conversion unavailable for this profile; export RGB16 sRGB with the supported profile or explicitly confirmed untagged sRGB")
        return {"action": "verified_srgb_icc_identity", "source_icc_sha256": digest}, []
    if not assume_srgb:
        raise InputError("missing ICC profile; confirm sRGB explicitly with assume_srgb=True")
    if gamma is not None and abs(int.from_bytes(gamma, "big") / 100000 - 0.45455) > 0.0001:
        raise InputError("PNG gamma conflicts with sRGB; provide a supported ICC profile")
    if chroma is not None:
        # Unlike a guessed profile, these are the STANDARD sRGB/D65 PNG cHRM
        # integers (coordinates scaled by 100000), not creative coefficients.
        standard = (31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000)
        if srgb is None or struct.unpack(">8I", chroma) != standard:
            raise InputError("PNG chromaticities require a supported ICC profile")
    return {"action": "explicit_srgb_assumption"}, ["untagged_source_assumed_srgb"]


def _orientation(metadata):
    if b"eXIf" not in metadata:
        return 1, {}, []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            exif = Image.Exif()
            payload = metadata[b"eXIf"]
            if not payload.startswith((b"II\x2a\x00", b"MM\x00\x2a")):
                raise InputError("invalid PNG EXIF container")
            exif.load(payload)
            orientation = exif.get(274, 1)
            if type(orientation) is not int or orientation not in range(1, 9):
                raise InputError("invalid EXIF orientation")
            technical, notes = image_io.technical_exif(exif)
            return orientation, technical, notes
    except InputError:
        raise
    except (OSError, ValueError, TypeError, SyntaxError, KeyError, Warning, struct.error):
        raise InputError("PNG EXIF validation failed") from None


def _orient(samples, orientation):
    if orientation == 2:
        return samples[:, ::-1]
    if orientation == 3:
        return samples[::-1, ::-1]
    if orientation == 4:
        return samples[::-1]
    if orientation == 5:
        return samples.transpose(1, 0, 2)
    if orientation == 6:
        return np.rot90(samples, -1)
    if orientation == 7:
        return samples.transpose(1, 0, 2)[::-1, ::-1]
    if orientation == 8:
        return np.rot90(samples, 1)
    return samples


def load_float_image(source, *, assume_srgb=False):
    # Read/hash/decode one immutable snapshot. Legacy RGB8 decoding is reused
    # without changing load_image behavior or the existing integer CLI contract.
    blob = image_io._read_source(source)
    is16 = blob.startswith(SIGNATURE) and len(blob) > 24 and blob[24] == 16
    if not is16:
        loaded = image_io._load_image_blob(blob, assume_srgb=assume_srgb)
        encoded = np.asarray(loaded.image).astype(np.float64) / 255
        provenance = dict(loaded.provenance)
        provenance.update({"source_bit_depth": 8, "working_precision": "float64",
                           "input_algorithm": ALGORITHM})
        return FloatImage(encoded, provenance)
    chunks = _chunks(blob)
    metadata = {kind: payload for kind, payload in chunks if kind != b"IDAT"}
    header = metadata[b"IHDR"]
    if len(header) != 13:
        raise InputError("invalid PNG IHDR length")
    width, height, depth, kind, compression, filtering, interlace = struct.unpack(">IIBBBBB", header)
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise InputError("image exceeds the 24 megapixel limit or has invalid dimensions")
    if (depth, kind, compression, filtering, interlace) != (16, 2, 0, 0, 0):
        raise InputError("only noninterlaced opaque RGB16 PNG supported by the precision-preserving input API")
    palette = metadata.get(b"PLTE")
    if palette is not None and (not palette or len(palette) % 3 or len(palette) > 768):
        raise InputError("invalid optional PNG palette")
    color, notes = _color(metadata, assume_srgb)
    orientation, technical, exif_notes = _orientation(metadata)
    raw = _inflate(b"".join(payload for kind, payload in chunks if kind == b"IDAT"), height * (width * 6 + 1))
    samples = _orient(_samples(raw, width, height), orientation)
    encoded = samples.astype(np.float64) / 65535
    return FloatImage(encoded, {
        "source_sha256": hashlib.sha256(blob).hexdigest(),
        "source_format": "PNG", "source_bit_depth": 16,
        "source_dimensions": [width, height],
        "oriented_dimensions": [encoded.shape[1], encoded.shape[0]],
        "orientation_applied": orientation, "color_management": color,
        "technical_exif": technical, "warnings": notes + exif_notes,
        "working_precision": "float64", "input_algorithm": ALGORITHM,
        "limitations": ["display_referred_sdr_not_scene_radiance",
                        "rgb16_icc_identity_only_no_arbitrary_profile_conversion",
                        "legacy_integer_cli_still_rejects_16bit_input",
                        "no_visual_or_photographic_detail_acceptance"],
    })
