#!/usr/bin/env python3
"""Render a privacy-conscious photography outing review card.

Pillow is the only non-standard dependency. Source files are opened read-only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from PIL import ExifTags, Image, ImageDraw, ImageFont, ImageOps
except ImportError as exc:
    raise SystemExit("Pillow is required: python -m pip install Pillow") from exc

FIELDS = ("captured_at", "focal_mm", "focal_35_mm", "aperture", "shutter_s", "iso")
TIME_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S")


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("images", nargs="+", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--json", dest="json_path", type=Path)
    p.add_argument("--title", default="Shoot review")
    p.add_argument("--subtitle", default="")
    p.add_argument("--cover", type=Path)
    p.add_argument("--accent", default="#E98A4B")
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--no-camera-model", action="store_true")
    args = p.parse_args()
    if args.width < 900:
        p.error("--width must be at least 900")
    if not valid_hex(args.accent):
        p.error("--accent must be a color like #E98A4B")
    return args


def valid_hex(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
        return True
    except ValueError:
        return False


def ratio(value: Any) -> float | None:
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return float(Fraction(value[0], value[1]))
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def date_value(value: Any) -> datetime | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str):
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            pass
    return None


def read_record(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            raw = image.getexif()
            entries = list(raw.items())
            # DateTimeOriginal and exposure tags commonly live in the nested
            # Exif IFD rather than the top-level image IFD.
            try:
                entries.extend(raw.get_ifd(0x8769).items())
            except (AttributeError, KeyError, TypeError):
                pass
            exif = {ExifTags.TAGS.get(k, str(k)): v for k, v in entries}
    except Exception as exc:  # Pillow raises format-specific exception classes.
        return None, f"{path}: {type(exc).__name__}"

    captured = date_value(exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized") or exif.get("DateTime"))
    focal = ratio(exif.get("FocalLength"))
    focal35 = ratio(exif.get("FocalLengthIn35mmFilm"))
    aperture = ratio(exif.get("FNumber"))
    shutter = ratio(exif.get("ExposureTime"))
    iso = ratio(exif.get("PhotographicSensitivity") or exif.get("ISOSpeedRatings"))
    make = clean_text(exif.get("Make"))
    model = clean_text(exif.get("Model"))
    camera = " ".join(x for x in (make, model) if x)
    return {
        "path": str(path),
        "captured_at": captured,
        "focal_mm": focal,
        "focal_35_mm": focal35,
        "aperture": aperture,
        "shutter_s": shutter,
        "iso": iso,
        "camera_model": camera or None,
        "width": width,
        "height": height,
    }, None


def clean_text(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return " ".join(str(value).split())[:100] if value else ""


def coverage(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total = len(records)
    return {
        key: {
            "n": sum(r[key] is not None for r in records),
            "total": total,
            "fraction": round(sum(r[key] is not None for r in records) / total, 4),
        }
        for key in FIELDS
    }


def usable(info: dict[str, Any]) -> bool:
    return info["n"] >= 3 and info["fraction"] >= 0.30


def choose_cover(records: list[dict[str, Any]], explicit: Path | None) -> tuple[dict[str, Any], str]:
    if explicit:
        target = explicit.expanduser().resolve()
        for record in records:
            if Path(record["path"]).expanduser().resolve() == target:
                return record, "user-selected"
        raise ValueError("--cover must be one of the input images")
    ordered = sorted(records, key=lambda r: (r["captured_at"] is None, r["captured_at"] or datetime.max, r["path"]))
    return next((r for r in ordered if r["width"] >= r["height"]), ordered[0]), "automatic: earliest landscape, else earliest readable"


def bucket(value: float, edges: list[float], labels: list[str]) -> str:
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1]


def histogram(records: list[dict[str, Any]], field: str, edges: list[float], labels: list[str]) -> dict[str, Any]:
    counts = Counter(bucket(r[field], edges, labels) for r in records if r[field] is not None)
    return {"field": field, "bins": [{"label": label, "count": counts[label]} for label in labels]}


def build_histograms(records: list[dict[str, Any]], cov: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    use_equiv = cov["focal_35_mm"]["n"] == len(records) and len(records) > 0
    focal_field = "focal_35_mm" if use_equiv else "focal_mm"
    focal = histogram(records, focal_field, [18, 35, 50, 85, math.inf], ["<18", "18–34", "35–49", "50–84", "85+"])
    focal["label"] = "Focal length (35 mm eq.)" if use_equiv else "Focal length (actual mm)"
    aperture = histogram(records, "aperture", [2.8, 4, 5.6, 8, math.inf], ["<2.8", "2.8–3.9", "4–5.5", "5.6–7.9", "8+"])
    aperture["label"] = "Aperture (f-number)"
    shutter = histogram(records, "shutter_s", [1 / 500, 1 / 125, 1 / 30, 1, math.inf], [">1/500", "1/500–1/126", "1/125–1/31", "1/30–<1s", "1s+"])
    shutter["label"] = "Shutter duration"
    return [focal, aperture, shutter]


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit_cover(path: str, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)


def draw_hist(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], hist: dict[str, Any], info: dict[str, Any], accent: str) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0, y0), hist["label"], fill="#F2F0EB", font=font(27, True))
    status = f"n={info['n']}/{info['total']} · {info['fraction']:.0%} coverage"
    draw.text((x0, y0 + 36), status, fill="#9A9893", font=font(19))
    if not usable(info):
        draw.text((x0, y0 + 88), "insufficient data", fill="#C2BDB4", font=font(25))
        return
    bins = hist["bins"]
    maximum = max((b["count"] for b in bins), default=1) or 1
    chart_top, chart_bottom = y0 + 88, y1 - 42
    gap = 12
    bar_w = max(12, (x1 - x0 - gap * (len(bins) - 1)) // len(bins))
    for i, item in enumerate(bins):
        bx = x0 + i * (bar_w + gap)
        height = int((chart_bottom - chart_top) * item["count"] / maximum)
        draw.rounded_rectangle((bx, chart_bottom - height, bx + bar_w, chart_bottom), radius=5, fill=accent)
        draw.text((bx, chart_bottom + 8), item["label"], fill="#AAA7A0", font=font(15))
        draw.text((bx, chart_bottom - height - 25), str(item["count"]), fill="#F2F0EB", font=font(16, True))


def draw_timeline(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], records: list[dict[str, Any]], info: dict[str, Any], accent: str) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0, y0), "Capture timeline", fill="#F2F0EB", font=font(27, True))
    draw.text((x0, y0 + 36), f"n={info['n']}/{info['total']} · {info['fraction']:.0%} coverage", fill="#9A9893", font=font(19))
    times = sorted(r["captured_at"] for r in records if r["captured_at"])
    if not usable(info):
        draw.text((x0, y0 + 88), "insufficient data", fill="#C2BDB4", font=font(25))
        return
    start, end = times[0], times[-1]
    span = max((end - start).total_seconds(), 1)
    baseline = y0 + 120
    draw.line((x0, baseline, x1, baseline), fill="#55534F", width=3)
    for moment in times:
        x = x0 + int((x1 - x0) * (moment - start).total_seconds() / span)
        draw.ellipse((x - 5, baseline - 5, x + 5, baseline + 5), fill=accent)
    draw.text((x0, baseline + 20), start.strftime("%H:%M"), fill="#AAA7A0", font=font(18))
    end_label = end.strftime("%H:%M")
    tw = draw.textlength(end_label, font=font(18))
    draw.text((x1 - tw, baseline + 20), end_label, fill="#AAA7A0", font=font(18))


def render(args: argparse.Namespace, records: list[dict[str, Any]], cover: dict[str, Any], cov: dict[str, dict[str, Any]], hists: list[dict[str, Any]]) -> Image.Image:
    width = args.width
    scale = width / 1600
    height = int(1460 * scale)
    margin = int(72 * scale)
    canvas = Image.new("RGB", (width, height), "#171716")
    draw = ImageDraw.Draw(canvas)
    cover_h = int(610 * scale)
    canvas.paste(fit_cover(cover["path"], (width, cover_h)), (0, 0))
    draw.text((margin, cover_h + int(45 * scale)), args.title[:80], fill="#F4F1EA", font=font(int(52 * scale), True))
    if args.subtitle:
        draw.text((margin, cover_h + int(112 * scale)), args.subtitle[:120], fill="#AAA7A0", font=font(int(24 * scale)))
    camera = Counter(r["camera_model"] for r in records if r["camera_model"]).most_common(1)
    summary = f"{len(records)} readable image{'s' if len(records) != 1 else ''}"
    if camera and not args.no_camera_model:
        summary += f" · {camera[0][0]}"
    draw.text((margin, cover_h + int(160 * scale)), summary, fill=args.accent, font=font(int(22 * scale), True))

    chart_y = cover_h + int(225 * scale)
    gap = int(42 * scale)
    available = width - 2 * margin - 2 * gap
    chart_w = available // 3
    for i, hist in enumerate(hists):
        field = hist["field"]
        info = cov[field]
        x = margin + i * (chart_w + gap)
        draw_hist(draw, (x, chart_y, x + chart_w, chart_y + int(350 * scale)), hist, info, args.accent)
    draw_timeline(draw, (margin, chart_y + int(400 * scale), width - margin, height - margin), records, cov["captured_at"], args.accent)
    return canvas


def serial_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat(sep=" ") if isinstance(v, datetime) else v) for k, v in record.items()}


def main() -> int:
    args = cli()
    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    for path in args.images:
        record, error = read_record(path)
        if record:
            records.append(record)
        else:
            skipped.append(error or str(path))
    if not records:
        print("error: no readable images", file=sys.stderr)
        return 2
    try:
        cover, cover_method = choose_cover(records, args.cover)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    cov = coverage(records)
    hists = build_histograms(records, cov)
    warnings = [f"{field}: insufficient data" for field, info in cov.items() if not usable(info)]
    times = sorted(r["captured_at"] for r in records if r["captured_at"])
    if len(times) >= 2 and (times[-1] - times[0]).total_seconds() > 86400:
        warnings.append("capture times span more than 24 hours; consider splitting the outing")
    payload = {
        "schema_version": "1.0",
        "input_count": len(args.images),
        "included": len(records),
        "skipped": len(skipped),
        "skipped_details": skipped,
        "cover": {"path": cover["path"], "selection": cover_method},
        "time_span": {
            "start": times[0].isoformat(sep=" ") if times else None,
            "end": times[-1].isoformat(sep=" ") if times else None,
        },
        "coverage": cov,
        "histograms": hists,
        "warnings": warnings,
        "records": [serial_record(r) for r in records],
        "privacy": "GPS, serial numbers, owner names, and EXIF comments are not read or emitted.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json_path = args.json_path or args.output.with_suffix(args.output.suffix + ".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        card = render(args, records, cover, cov, hists)
        card.save(args.output, format="PNG")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"error: could not write output: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {args.output}")
    print(f"wrote {json_path}")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
