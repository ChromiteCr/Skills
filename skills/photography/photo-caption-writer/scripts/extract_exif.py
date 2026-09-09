#!/usr/bin/env python3
"""Extract caption-safe EXIF fields from an image as JSON.

Requires Pillow. GPS and other potentially sensitive metadata are intentionally
excluded. Missing values are emitted as null; this script never guesses them.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys
from typing import Any

try:
    from PIL import ExifTags, Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - depends on the host environment
    print("error: Pillow is required (python -m pip install Pillow)", file=sys.stderr)
    raise SystemExit(2)


SAFE_TAGS = {
    "DateTimeOriginal": "captured_at",
    "Make": "camera_make",
    "Model": "camera_model",
    "LensModel": "lens",
    "ExposureTime": "exposure_time",
    "FNumber": "aperture",
    "ISOSpeedRatings": "iso",
    "PhotographicSensitivity": "iso",
    "FocalLength": "focal_length_mm",
    "ExposureBiasValue": "exposure_compensation_ev",
}


def rational_number(value: Any) -> float | None:
    """Convert Pillow rationals and numeric values to a finite float."""
    try:
        number = float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def exposure_text(value: Any) -> str | None:
    """Format exposure time without replacing recorded precision by a guess."""
    number = rational_number(value)
    if number is None or number <= 0:
        return None
    if number < 1:
        fraction = Fraction(number).limit_denominator(8000)
        return f"{fraction.numerator}/{fraction.denominator} s"
    return f"{number:g} s"


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def extract(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_file": path.name,
        "captured_at": None,
        "camera_make": None,
        "camera_model": None,
        "lens": None,
        "exposure_time": None,
        "aperture": None,
        "iso": None,
        "focal_length_mm": None,
        "exposure_compensation_ev": None,
    }

    with Image.open(path) as image:
        exif = image.getexif()
        values: dict[str, Any] = {}
        for tag_id, value in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if tag_name in SAFE_TAGS:
                values[SAFE_TAGS[tag_name]] = value

    for key in ("captured_at", "camera_make", "camera_model", "lens"):
        result[key] = clean_text(values.get(key))

    result["exposure_time"] = exposure_text(values.get("exposure_time"))

    aperture = rational_number(values.get("aperture"))
    result["aperture"] = f"f/{aperture:g}" if aperture and aperture > 0 else None

    iso = rational_number(values.get("iso"))
    result["iso"] = int(iso) if iso is not None and iso >= 0 and iso.is_integer() else iso

    focal = rational_number(values.get("focal_length_mm"))
    result["focal_length_mm"] = round(focal, 3) if focal is not None and focal >= 0 else None

    compensation = rational_number(values.get("exposure_compensation_ev"))
    result["exposure_compensation_ev"] = (
        round(compensation, 3) if compensation is not None else None
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract non-location EXIF fields for factual photo captions."
    )
    parser.add_argument("image", type=Path, help="path to an image file")
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"not a file: {args.image}")

    try:
        data = extract(args.image)
    except (OSError, UnidentifiedImageError) as exc:
        print(f"error: cannot read image: {exc}", file=sys.stderr)
        return 1

    json.dump(
        data,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
