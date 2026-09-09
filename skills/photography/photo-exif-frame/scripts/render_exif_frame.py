#!/usr/bin/env python3
"""Inspect EXIF and add a configurable metadata band below one photograph."""

from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from PIL import ExifTags, Image, ImageColor, ImageDraw, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover - environment-dependent
    raise SystemExit("Pillow is required: python -m pip install Pillow") from exc

FIELD_LABELS = {
    "aperture": "APERTURE",
    "shutter": "SHUTTER",
    "exposure_compensation": "EXP. COMP.",
    "iso": "ISO",
    "captured": "CAPTURED",
    "camera": "CAMERA",
}
DEFAULT_FIELDS = list(FIELD_LABELS)
TAG_NAME = {tag_id: name for tag_id, name in ExifTags.TAGS.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source image")
    parser.add_argument("--output", type=Path, help="new framed image")
    parser.add_argument("--inspect", action="store_true", help="print metadata JSON only")
    parser.add_argument(
        "--fields",
        default=",".join(DEFAULT_FIELDS),
        help="comma-separated fields: " + ",".join(DEFAULT_FIELDS),
    )
    parser.add_argument("--band-color", default="#F3F0E8")
    parser.add_argument("--text-color", default="#171717")
    parser.add_argument("--band-ratio", type=float, default=0.16)
    parser.add_argument("--padding-ratio", type=float, default=0.04)
    parser.add_argument("--font", type=Path, help="TrueType/OpenType font path")
    return parser.parse_args()


def rational(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def fraction_text(value: Any) -> str:
    number = rational(value)
    if number is None or number <= 0:
        return ""
    if number >= 1:
        return f"{number:g} s"
    frac = Fraction(number).limit_denominator(8000)
    return f"{frac.numerator}/{frac.denominator} s"


def signed_ev(value: Any) -> str:
    number = rational(value)
    if number is None:
        return ""
    return f"{number:+g} EV"


def aperture_text(value: Any) -> str:
    number = rational(value)
    return f"f/{number:g}" if number and number > 0 else ""


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value).strip().strip("\x00")


def extract_metadata(image: Image.Image) -> dict[str, str]:
    try:
        raw = image.getexif()
    except Exception:
        raw = {}

    items = dict(raw.items())
    # Exposure fields commonly live in the nested Exif IFD rather than IFD0.
    get_ifd = getattr(raw, "get_ifd", None)
    if callable(get_ifd):
        try:
            exif_ifd_id = getattr(getattr(ExifTags, "IFD", object()), "Exif", 34665)
            items.update(dict(get_ifd(exif_ifd_id).items()))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
    named = {TAG_NAME.get(tag_id, str(tag_id)): value for tag_id, value in items.items()}

    make = clean_text(named.get("Make"))
    model = clean_text(named.get("Model"))
    camera = " ".join(part for part in (make, model) if part)
    if make and model.lower().startswith(make.lower()):
        camera = model

    iso = named.get("PhotographicSensitivity", named.get("ISOSpeedRatings"))
    if isinstance(iso, (tuple, list)):
        iso = iso[0] if iso else None

    return {
        "aperture": aperture_text(named.get("FNumber")),
        "shutter": fraction_text(named.get("ExposureTime")),
        "exposure_compensation": signed_ev(named.get("ExposureBiasValue")),
        "iso": clean_text(iso),
        "captured": clean_text(named.get("DateTimeOriginal", named.get("DateTime"))),
        "camera": camera,
    }


def parse_fields(raw: str) -> list[str]:
    fields = [item.strip() for item in raw.split(",") if item.strip()]
    if not fields:
        raise ValueError("at least one field is required")
    unknown = [field for field in fields if field not in FIELD_LABELS]
    if unknown:
        raise ValueError("unknown field(s): " + ", ".join(unknown))
    if len(set(fields)) != len(fields):
        raise ValueError("fields must not be repeated")
    return fields


def load_font(path: Path | None, size: int) -> tuple[ImageFont.ImageFont, str]:
    if path:
        if not path.is_file():
            raise ValueError(f"font does not exist: {path}")
        return ImageFont.truetype(str(path), size=size), str(path)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size), "Pillow DejaVu Sans fallback"
    except OSError:
        return ImageFont.load_default(), "Pillow default fallback"


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> float:
    if not text:
        return 0.0
    box = draw.textbbox((0, 0), text, font=font)
    return float(box[2] - box[0])


def report(image: Image.Image, metadata: dict[str, str], fields: list[str]) -> dict[str, Any]:
    return {
        "oriented_source_dimensions": [image.width, image.height],
        "metadata": metadata,
        "selected_fields": fields,
        "blank_fields": [field for field in fields if not metadata[field]],
    }


def render(args: argparse.Namespace, image: Image.Image, metadata: dict[str, str], fields: list[str]) -> dict[str, Any]:
    if args.output is None:
        raise ValueError("--output is required unless --inspect is used")
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if source == output:
        raise ValueError("output must differ from input")
    if not (0.08 <= args.band_ratio <= 0.50):
        raise ValueError("--band-ratio must be between 0.08 and 0.50")
    if not (0.0 <= args.padding_ratio <= 0.20):
        raise ValueError("--padding-ratio must be between 0 and 0.20")

    band_height = max(48, math.ceil(image.height * args.band_ratio))
    padding = math.ceil(image.width * args.padding_ratio)
    available = image.width - 2 * padding
    if available <= 0:
        raise ValueError("padding leaves no horizontal content area")
    cell_width = available / len(fields)

    background = ImageColor.getrgb(args.band_color)
    foreground = ImageColor.getrgb(args.text_color)
    canvas = Image.new("RGB", (image.width, image.height + band_height), background)
    canvas.paste(image.convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(canvas)

    label_size = max(9, round(band_height * 0.12))
    value_size = max(11, round(band_height * 0.19))
    label_font, label_font_name = load_font(args.font, label_size)
    value_font, value_font_name = load_font(args.font, value_size)
    gap = max(4, round(band_height * 0.08))
    label_y = image.height + max(8, round(band_height * 0.20))
    value_y = label_y + label_size + gap

    too_wide: list[str] = []
    for index, field in enumerate(fields):
        label = FIELD_LABELS[field]
        value = metadata[field]
        max_width = cell_width - gap
        if text_width(draw, label, label_font) > max_width or text_width(draw, value, value_font) > max_width:
            too_wide.append(field)
            continue
        x = padding + index * cell_width
        draw.text((round(x), label_y), label, fill=foreground, font=label_font)
        if value:
            draw.text((round(x), value_y), value, fill=foreground, font=value_font)
    if too_wide:
        raise ValueError(
            "text does not fit field cell(s): "
            + ", ".join(too_wide)
            + "; select fewer fields, increase image width, or choose a more compact font"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    canvas.save(output)

    result = report(image, metadata, fields)
    result.update(
        {
            "output": str(output),
            "output_dimensions": [canvas.width, canvas.height],
            "band_ratio": args.band_ratio,
            "padding_ratio": args.padding_ratio,
            "band_color": args.band_color,
            "text_color": args.text_color,
            "fonts": sorted({label_font_name, value_font_name}),
            "source_exif_copied": False,
            "warnings": ["Source EXIF was read for display but was not copied to the output."],
        }
    )
    return result


def main() -> int:
    args = parse_args()
    try:
        fields = parse_fields(args.fields)
        if not args.input.is_file():
            raise ValueError(f"input does not exist: {args.input}")
        with Image.open(args.input) as opened:
            metadata = extract_metadata(opened)
            image = ImageOps.exif_transpose(opened).copy()
        result = report(image, metadata, fields) if args.inspect else render(args, image, metadata, fields)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
