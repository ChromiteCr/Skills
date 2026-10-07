#!/usr/bin/env python3
"""Conservative, standalone I/O for cinegrade; not a shared-module copy.

Only 8-bit RGB/L JPEG and PNG are accepted. No automatic profile assumption,
metadata passthrough, file replacement, RAW conversion or dependency install.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path
import stat
import warnings

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

MAX_PIXELS = 24_000_000
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_ICC_BYTES = 2 * 1024 * 1024


class InputError(ValueError):
    """Unsupported or unsafe input; messages never contain source metadata."""


@dataclass
class LoadedImage:
    image: Image.Image
    provenance: dict


def _positive_number(value):
    # Do not coerce strings: EXIF text fields are not safe technical values.
    if isinstance(value, (str, bytes, bool)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) and 0 < result <= 1_000_000 else None


def technical_exif(exif):
    """A numeric allowlist, never a raw EXIF dump. No location/time/device IDs."""
    try:
        nested = exif.get_ifd(34665) if 34665 in exif else {}
        fields = {**dict(exif), **nested}
    except (ValueError, TypeError, KeyError, OSError, SyntaxError):
        return {}, ['exif_technical_unreadable']
    result = {}
    for tag, name in ((33434, 'exposure_seconds'), (33437, 'f_number'),
                      (34855, 'iso'), (37386, 'focal_length_mm')):
        value = _positive_number(fields.get(tag))
        if value is not None:
            result[name] = value
    return result, []


def _read_source(path):
    # Reject symlinks at the final component and non-regular files; do not hang
    # on a FIFO. Hash and decode the same in-memory snapshot, not a second read.
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise InputError('source must be a regular file, not a symlink or device')
            if st.st_size > MAX_SOURCE_BYTES:
                raise InputError('source exceeds the 64 MiB compressed-file limit')
            blob = stream.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        raise InputError('cannot read source as a regular, non-symlink file') from None
    if len(blob) > MAX_SOURCE_BYTES:
        raise InputError('source exceeds the 64 MiB compressed-file limit')
    return blob


def _check_png_signaling(blob):
    # Pillow versions expose different ancillary keys. Inspect chunk names too
    # so cICP/HDR signaling cannot be ignored simply because the decoder does.
    if not blob.startswith(b'\x89PNG\r\n\x1a\n'):
        return False
    offset = 8
    icc_chunks = 0
    while offset < len(blob):
        if offset + 12 > len(blob):
            raise InputError('truncated PNG chunk')
        length = int.from_bytes(blob[offset:offset + 4], 'big')
        kind = blob[offset + 4:offset + 8]
        if offset + 12 + length > len(blob):
            raise InputError('truncated PNG chunk')
        if kind in {b'cICP', b'mDCv', b'cLLi'}:
            raise InputError('cICP/HDR-signaled PNG requires a separate color-managed export')
        if kind == b'iCCP':
            icc_chunks += 1
            if icc_chunks > 1:
                raise InputError('multiple PNG ICC profiles are ambiguous')
        offset += 12 + length
        if kind == b'IEND':
            break
    return bool(icc_chunks)


def load_image(source, *, assume_srgb=False):
    blob = _read_source(source)
    png_claims_icc = _check_png_signaling(blob)
    notes = []
    try:
        with warnings.catch_warnings():
            # A corrupt/truncated EXIF/profile must not be silently accepted.
            warnings.simplefilter('error')
            with Image.open(io.BytesIO(blob)) as opened:
                if opened.format not in {'JPEG', 'PNG'}:
                    raise InputError('only 8-bit JPEG/PNG supported; export RAW/HEIC/HDR separately')
                if getattr(opened, 'n_frames', 1) != 1:
                    raise InputError('animated or multi-frame images are not supported')
                width, height = opened.size
                if not 0 < width * height <= MAX_PIXELS:
                    raise InputError('image exceeds the 24 megapixel limit or has invalid dimensions')
                if opened.format == 'PNG' and (len(blob) < 25 or blob[24] != 8):
                    raise InputError('PNG must have an 8-bit sample depth; no silent downconversion')
                if opened.mode not in {'RGB', 'L'} or 'transparency' in opened.info:
                    raise InputError('only opaque RGB/L images supported; no alpha, palette or CMYK')
                if opened.format == 'JPEG' and getattr(opened, 'bits', 8) != 8:
                    raise InputError('JPEG must have an 8-bit sample depth')
                # Reject modern HDR signaling even if the base image is RGB8.
                if any(k in opened.info for k in ('cicp', 'mDCv', 'cLLi')):
                    raise InputError('HDR-signaled PNG is not supported')
                opened.load()
                exif = opened.getexif()
                orientation = exif.get(274, 1)
                if not isinstance(orientation, int) or isinstance(orientation, bool) or orientation not in range(1, 9):
                    raise InputError('invalid EXIF orientation')
                safe_exif, exif_notes = technical_exif(exif)
                notes.extend(exif_notes)
                profile_bytes = opened.info.get('icc_profile')
                jpeg_claims_icc = any(
                    marker == 'APP2' and payload.startswith(b'ICC_PROFILE\x00')
                    for marker, payload in getattr(opened, 'applist', [])
                )
                if (png_claims_icc or jpeg_claims_icc) and profile_bytes is None:
                    raise InputError('embedded ICC container is corrupt or incomplete; refusing fallback')
                oriented = ImageOps.exif_transpose(opened)
                if profile_bytes is not None:
                    if not profile_bytes or len(profile_bytes) > MAX_ICC_BYTES:
                        raise InputError('empty or oversized embedded ICC profile')
                    try:
                        profile = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
                        # Relative colorimetric, no implicit perceptual transform.
                        normalized = ImageCms.profileToProfile(
                            oriented, profile, ImageCms.createProfile('sRGB'),
                            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                            outputMode='RGB', flags=0,
                        )
                    except (ImageCms.PyCMSError, OSError, ValueError, TypeError):
                        raise InputError('embedded ICC cannot be converted; refusing fallback') from None
                    color = {'action': 'icc_to_srgb', 'intent': 'relative_colorimetric',
                             'source_icc_sha256': hashlib.sha256(profile_bytes).hexdigest()}
                else:
                    if not assume_srgb:
                        raise InputError('missing ICC profile; confirm sRGB explicitly with --assume-srgb')
                    # A declared non-sRGB gamma/chromaticity is not overridden by
                    # --assume-srgb. No attempt to reconstruct a profile from it.
                    if 'gamma' in opened.info and abs(opened.info['gamma'] - 0.45455) > 0.0001:
                        raise InputError('PNG gamma conflicts with sRGB; provide a valid ICC profile')
                    if 'chromaticity' in opened.info and 'srgb' not in opened.info:
                        raise InputError('PNG chromaticities require a valid ICC profile')
                    normalized = oriented.convert('RGB')
                    color = {'action': 'explicit_srgb_assumption'}
                    notes.append('untagged_source_assumed_srgb')
                # Fresh pixels prevent Pillow's info/EXIF/XMP passthrough.
                clean = Image.frombytes('RGB', normalized.size, normalized.tobytes())
                return LoadedImage(clean, {
                    'source_sha256': hashlib.sha256(blob).hexdigest(),
                    'source_format': opened.format,
                    'source_dimensions': [width, height],
                    'oriented_dimensions': list(clean.size),
                    'orientation_applied': orientation,
                    'color_management': color,
                    'technical_exif': safe_exif,
                    'warnings': notes,
                })
    except InputError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError, Warning):
        raise InputError('image decode or metadata validation failed; no output written') from None


def encode_png(image):
    """Return an sRGB-tagged PNG with no source ancillary metadata."""
    clean = Image.frombytes('RGB', image.size, image.tobytes())
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    output = io.BytesIO()
    clean.save(output, format='PNG', icc_profile=profile, compress_level=9)
    return output.getvalue()


def write_new_run(output_dir, png, report):
    """Reserve a fresh directory atomically; report.json is the completion receipt.

    Parent must already exist. A failed write may leave a partial directory;
    keep it for inspection and retry with a new name. Never clean user data.
    """
    target = Path(output_dir)
    try:
        target.mkdir(mode=0o700, parents=False, exist_ok=False)
    except OSError:
        raise InputError('output must be a new directory under an existing writable parent') from None
    try:
        for name, data in (('render.png', png), ('report.json', report)):
            with (target / name).open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    except OSError:
        raise InputError('output write failed; preserve partial directory and retry with a new name') from None


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true', help='run synthetic I/O and privacy tests')
    args = parser.parse_args()
    if args.selftest:
        from test_cinegrade import run_tests
        return run_tests('io')
    parser.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
