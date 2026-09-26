#!/usr/bin/env python3
"""Render a privacy-conscious photography outing review card.

Pillow is the only non-standard dependency; fontTools is optional and lets the
script check that a font has every glyph. Reading and writing go through the
shared `image_io.py` next to this file. Source files are opened read-only, and
an --output or --json path that is one of the input photos is refused.

- Capture time is EXIF DateTimeOriginal only. IFD0 DateTime is the last edit
  or export time; a file that has only that counts as missing a capture time
  and stays off the timeline.
- Widths and heights are the displayed sizes (EXIF orientation applied), so
  the automatic cover really is the earliest landscape photo.
- Colour: the cover is the only photo on the card; its RGB ICC profile is
  embedded (Display P3 stays Display P3) and the card's own colours are
  converted into it. CMYK or grey covers are converted to sRGB.
- Fonts: --font, or an installed font that has every glyph of the text
  (Chinese titles get a Chinese font). No such font -> error, never boxes.
- HEIC/HEIF (without pillow-heif) and unreadable files are skipped with a
  warning on stderr (for HEIC, the sips command that converts it); the card is
  made from the rest.

Usage:
  python3 make_review_card.py IMG [IMG ...] --output card.png [options]
  python3 make_review_card.py --selftest

Exit codes: 0 card written (warnings on stderr), 2 error (nothing written),
1 self-test failure.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import io
import json
import math
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import image_io  # noqa: E402  (shared copy; also checks that Pillow is installed)

from PIL import Image, ImageCms, ImageColor, ImageDraw, ImageFont, ImageOps  # noqa: E402

FIELDS = ("captured_at", "focal_mm", "focal_35_mm", "aperture", "shutter_s", "iso")
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M:%S")
BACKGROUND = "#171716"
# Everything the card itself writes (chart titles, bins, counts, times); one font is chosen for all of it.
CARD_TEXT = (
    "Focal length (35 mm eq.) (actual mm) Aperture (f-number) Shutter duration Capture timeline "
    "insufficient data n=/ · % coverage <18 18–34 35–49 50–84 85+ <2.8 2.8–3.9 4–5.5 5.6–7.9 8+ "
    ">1/500 1/500–1/126 1/125–1/31 1/30–<1s 1s+ 0123456789:"
)


def cli(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Render a photography outing review card (PNG or JPEG) and a JSON sidecar.",
        epilog="Exit codes: 0 card written (warnings on stderr), 2 error (nothing written), 1 self-test failure.",
    )
    p.add_argument("images", nargs="*", type=Path, help="photos from one outing")
    p.add_argument("--output", type=Path, help="card image, .png or .jpg; must not be one of the input photos")
    p.add_argument("--json", dest="json_path", type=Path, help="JSON sidecar path (default: output name + .json)")
    p.add_argument("--title", default="Shoot review")
    p.add_argument("--subtitle", default="")
    p.add_argument("--cover", type=Path)
    p.add_argument("--accent", default="#E98A4B")
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--font", type=Path, help="font file for all text (default: an installed font that has the glyphs, Chinese included)")
    p.add_argument("--no-camera-model", action="store_true")
    p.add_argument("--selftest", action="store_true", help="run the built-in regression checks and exit")
    args = p.parse_args(argv)
    if args.selftest:
        return args
    if not args.images:
        p.error("at least one image is required")
    if args.output is None:
        p.error("the following arguments are required: --output")
    if args.width < 900:
        p.error("--width must be at least 900")
    if not valid_hex(args.accent):
        p.error("--accent must be a color like #E98A4B")
    if args.font is not None and not args.font.is_file():
        p.error(f"--font: not a file: {args.font}")
    return args


def valid_hex(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
        return True
    except ValueError:
        return False


def date_value(value: Any) -> datetime | None:
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
        width, height = image_io.oriented_size(path)  # displayed size, EXIF orientation applied
        with Image.open(path) as image:
            image.verify()
        exif = image_io.read_exif(path)
    except image_io.ImageIOError as exc:
        message = str(exc)
        if message.startswith(path.name + ": "):
            message = message[len(path.name) + 2:]
        return None, f"{path}: {message}"
    except Exception as exc:  # Pillow raises format-specific exception classes.
        return None, f"{path}: {type(exc).__name__}"

    captured = date_value(exif["captured_at"])  # DateTimeOriginal only
    iso = exif["iso"]
    return {
        "path": str(path),
        "captured_at": captured,
        "focal_mm": exif["focal_length_mm"],
        "focal_35_mm": float(exif["focal_length_35mm"]) if exif["focal_length_35mm"] else None,
        "aperture": exif["f_number"],
        "shutter_s": exif["exposure_time_s"],
        "iso": float(iso) if iso is not None else None,
        "camera_model": exif["camera"],  # maker not repeated ("Canon EOS R6", not "Canon Canon EOS R6")
        "width": width,
        "height": height,
        "_file_time_only": captured is None and exif["file_modified_at"] is not None,
    }, None


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
        raise ValueError("--cover must be one of the readable input images")
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


# ---------------------------------------------------------------- fonts and colour


class FontBook:
    """--font for everything, or per text an installed font that has all of its glyphs."""

    def __init__(self, explicit: Path | None) -> None:
        self.explicit = str(explicit) if explicit else None
        self.paths: dict[tuple[str, bool], str | None] = {}
        self.used: set[str] = set()
        self.warnings: list[str] = []
        if self.explicit:
            image_io.load_font(20, path=self.explicit)  # raises ImageIOError when unreadable

    def resolve(self, text: str, bold: bool) -> str | None:
        key = (text, bold)
        if key not in self.paths:
            if self.explicit:
                if not image_io.font_covers(self.explicit, text):
                    raise image_io.ImageIOError(f"font {self.explicit} has no glyphs for some characters in {text!r}; pass a font that has them")
                path: str | None = self.explicit
            else:
                _, description = image_io.load_font(20, text=text, bold=bold)  # raises for Chinese without a Chinese font
                if description.startswith("Pillow built-in bitmap font"):
                    raise image_io.ImageIOError("no scalable font is installed and this Pillow has only a fixed 10 px font; pass --font")
                path = None if description.startswith("Pillow built-in font") else description
                if path is None:
                    note = "No system font was found; Pillow's built-in font was used. Pass --font to choose one."
                    if note not in self.warnings:
                        self.warnings.append(note)
            self.paths[key] = path
            self.used.add(path or "Pillow built-in font")
        return self.paths[key]

    @functools.lru_cache(maxsize=None)
    def _load(self, path: str | None, size: int) -> Any:
        if path is None:
            return ImageFont.load_default(size=size)
        return image_io.load_font(size, path=path)[0]

    def get(self, size: int, text: str = CARD_TEXT, bold: bool = False) -> Any:
        return self._load(self.resolve(text, bold), max(1, int(size)))

    def fit(self, draw: ImageDraw.ImageDraw, text: str, bold: bool, max_px: int, min_px: int, max_width: int, what: str) -> Any:
        """The largest size in [min_px, max_px] at which `text` fits `max_width`."""
        size = image_io.fit_size(lambda s: image_io.text_width(draw, text, self.get(s, text, bold)) <= max_width, min_px, max_px)
        if size is None:
            raise image_io.ImageIOError(f"{what} is too long to fit the card even at {min_px} px; shorten it")
        return self.get(size, text, bold)


# Shared with the other photo scripts (image_io.py 1.1.0).
profile_space = image_io.profile_space
srgb_color_in_profile = image_io.srgb_color_in_profile


class Palette:
    """Card colours are written as sRGB hex; convert them into the output profile once each."""

    def __init__(self, icc: bytes | None) -> None:
        self.icc = icc
        self.cache: dict[str, tuple[int, int, int]] = {}

    def __call__(self, hex_color: str) -> tuple[int, int, int]:
        if hex_color not in self.cache:
            self.cache[hex_color] = srgb_color_in_profile(tuple(ImageColor.getrgb(hex_color))[:3], self.icc)
        return self.cache[hex_color]


# ---------------------------------------------------------------- drawing


def draw_hist(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], hist: dict[str, Any], info: dict[str, Any],
              accent: str, fonts: FontBook, color: Palette) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0, y0), hist["label"], fill=color("#F2F0EB"), font=fonts.get(27, bold=True))
    status = f"n={info['n']}/{info['total']} · {info['fraction']:.0%} coverage"
    draw.text((x0, y0 + 36), status, fill=color("#9A9893"), font=fonts.get(19))
    if not usable(info):
        draw.text((x0, y0 + 88), "insufficient data", fill=color("#C2BDB4"), font=fonts.get(25))
        return
    bins = hist["bins"]
    maximum = max((b["count"] for b in bins), default=1) or 1
    chart_top, chart_bottom = y0 + 88, y1 - 42
    gap = 12
    bar_w = max(12, (x1 - x0 - gap * (len(bins) - 1)) // len(bins))
    for i, item in enumerate(bins):
        bx = x0 + i * (bar_w + gap)
        height = int((chart_bottom - chart_top) * item["count"] / maximum)
        draw.rounded_rectangle((bx, chart_bottom - height, bx + bar_w, chart_bottom), radius=5, fill=color(accent))
        draw.text((bx, chart_bottom + 8), item["label"], fill=color("#AAA7A0"), font=fonts.get(15))
        draw.text((bx, chart_bottom - height - 25), str(item["count"]), fill=color("#F2F0EB"), font=fonts.get(16, bold=True))


def draw_timeline(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], records: list[dict[str, Any]],
                  info: dict[str, Any], accent: str, fonts: FontBook, color: Palette) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0, y0), "Capture timeline", fill=color("#F2F0EB"), font=fonts.get(27, bold=True))
    draw.text((x0, y0 + 36), f"n={info['n']}/{info['total']} · {info['fraction']:.0%} coverage", fill=color("#9A9893"), font=fonts.get(19))
    times = sorted(r["captured_at"] for r in records if r["captured_at"])
    if not usable(info):
        draw.text((x0, y0 + 88), "insufficient data", fill=color("#C2BDB4"), font=fonts.get(25))
        return
    start, end = times[0], times[-1]
    span = max((end - start).total_seconds(), 1)
    baseline = y0 + 120
    draw.line((x0, baseline, x1, baseline), fill=color("#55534F"), width=3)
    for moment in times:
        x = x0 + int((x1 - x0) * (moment - start).total_seconds() / span)
        draw.ellipse((x - 5, baseline - 5, x + 5, baseline + 5), fill=color(accent))
    draw.text((x0, baseline + 20), start.strftime("%H:%M"), fill=color("#AAA7A0"), font=fonts.get(18))
    end_label = end.strftime("%H:%M")
    tw = draw.textlength(end_label, font=fonts.get(18))
    draw.text((x1 - tw, baseline + 20), end_label, fill=color("#AAA7A0"), font=fonts.get(18))


def render(args: argparse.Namespace, records: list[dict[str, Any]], cover: dict[str, Any], cov: dict[str, dict[str, Any]],
           hists: list[dict[str, Any]], fonts: FontBook) -> tuple[Image.Image, bytes | None, dict[str, Any], list[str]]:
    width = args.width
    scale = width / 1600
    height = int(1460 * scale)
    margin = int(72 * scale)
    warnings: list[str] = []

    photo, meta = image_io.open_image(cover["path"])  # upright, ICC kept
    icc = meta["icc_profile"]
    # The cover is the only photo on the card, so its own profile is the common space ("keep").
    policy, out_icc = image_io.choose_output_profile([icc])
    space = profile_space(icc)
    if icc and space in ("CMYK", "GRAY"):
        policy, out_icc = "converted to sRGB", image_io.srgb_icc_bytes()
        photo = image_io.to_srgb(photo, icc, background=tuple(ImageColor.getrgb(BACKGROUND))[:3])
        warnings.append(f"The cover's profile '{meta['color_space']}' is not RGB; the cover was converted to sRGB.")
    elif icc and space != "RGB":
        policy, out_icc = "untagged, sRGB embedded", None
        warnings.append("The cover's embedded ICC profile could not be read; it was treated as sRGB.")
    elif not icc:
        policy = "untagged, sRGB embedded"
    color = Palette(out_icc if policy == "keep" else None)

    canvas = Image.new("RGB", (width, height), color(BACKGROUND))
    draw = ImageDraw.Draw(canvas)
    cover_h = int(610 * scale)
    photo = image_io.to_rgb(photo, color(BACKGROUND))  # transparent areas take the card background
    canvas.paste(ImageOps.fit(photo, (width, cover_h), method=Image.Resampling.LANCZOS), (0, 0))

    text_width = width - 2 * margin
    title_font = fonts.fit(draw, args.title, True, int(52 * scale), int(28 * scale), text_width, "--title")
    draw.text((margin, cover_h + int(45 * scale)), args.title, fill=color("#F4F1EA"), font=title_font)
    if args.subtitle:
        subtitle_font = fonts.fit(draw, args.subtitle, False, int(24 * scale), int(16 * scale), text_width, "--subtitle")
        draw.text((margin, cover_h + int(112 * scale)), args.subtitle, fill=color("#AAA7A0"), font=subtitle_font)
    camera = Counter(r["camera_model"] for r in records if r["camera_model"]).most_common(1)
    summary = f"{len(records)} readable image{'s' if len(records) != 1 else ''}"
    if camera and not args.no_camera_model:
        summary += f" · {camera[0][0]}"
    summary_font = fonts.fit(draw, summary, True, int(22 * scale), int(16 * scale), text_width, "the summary line")
    draw.text((margin, cover_h + int(160 * scale)), summary, fill=color(args.accent), font=summary_font)

    chart_y = cover_h + int(225 * scale)
    gap = int(42 * scale)
    available = width - 2 * margin - 2 * gap
    chart_w = available // 3
    for i, hist in enumerate(hists):
        info = cov[hist["field"]]
        x = margin + i * (chart_w + gap)
        draw_hist(draw, (x, chart_y, x + chart_w, chart_y + int(350 * scale)), hist, info, args.accent, fonts, color)
    draw_timeline(draw, (margin, chart_y + int(400 * scale), width - margin, height - margin), records, cov["captured_at"],
                  args.accent, fonts, color)
    color_info = {
        "cover_color_space": meta["color_space"],
        "output_color_space": image_io.profile_name(out_icc or image_io.srgb_icc_bytes()),
        "policy": policy,
    }
    if meta["has_alpha"]:
        warnings.append("Transparent areas of the cover were composited onto the card background.")
    return canvas, out_icc, color_info, warnings


def serial_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat(sep=" ") if isinstance(v, datetime) else v) for k, v in record.items() if not k.startswith("_")}


def output_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Refuse an --output or --json path that is one of the input photos, before any work is done."""
    output = image_io.check_output_path(args.output, args.images)
    if output.suffix.lower() not in image_io.OUTPUT_FORMATS:
        raise image_io.ImageIOError(f"--output must end in .png, .jpg, .tif or .webp (got '{output.suffix or 'no extension'}')")
    json_path = args.json_path or output.with_suffix(output.suffix + ".json")
    if json_path.expanduser().absolute() == output.expanduser().absolute():
        raise image_io.ImageIOError("--json must differ from --output")
    image_io.check_output_path(json_path, args.images)
    return output, json_path


def main(argv: list[str] | None = None) -> int:
    args = cli(argv)
    if args.selftest:
        return selftest()
    try:
        output, json_path = output_paths(args)
        fonts = FontBook(args.font)
    except image_io.ImageIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    skipped_paths: set[Path] = set()
    for path in args.images:
        record, error = read_record(path)
        if record:
            records.append(record)
        else:
            skipped.append(error or str(path))
            skipped_paths.add(path.expanduser().absolute())
            print(f"warning: skipped {error or path}", file=sys.stderr)
    if not records:
        print("error: no readable images", file=sys.stderr)
        return 2
    if args.cover and args.cover.expanduser().absolute() in skipped_paths:
        print(f"error: --cover {args.cover} could not be read (see the warning above)", file=sys.stderr)
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
    file_time_only = [r["path"] for r in records if r["_file_time_only"]]
    if file_time_only:
        warnings.append(
            f"{len(file_time_only)} image(s) carry only IFD0 DateTime (an edit or export time), not DateTimeOriginal; "
            "they count as missing capture time and are left off the timeline: " + ", ".join(file_time_only)
        )
    if skipped:
        warnings.append(f"{len(skipped)} file(s) skipped; see skipped_details")

    try:
        card, out_icc, color_info, render_warnings = render(args, records, cover, cov, hists, fonts)
    except image_io.ImageIOError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    warnings += render_warnings + fonts.warnings
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
        "color": color_info,
        "fonts": sorted(fonts.used),
        "warnings": warnings,
        "records": [serial_record(r) for r in records],
        "privacy": "GPS, serial numbers, owner names, and EXIF comments are not read or emitted.",
    }

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        image_io.save_image(card, output, icc_profile=out_icc, inputs=args.images)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"error: could not write output: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {output}")
    print(f"wrote {json_path}")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- self-test


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse errors
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selftest() -> int:
    from PIL import TiffImagePlugin

    rational = TiffImagePlugin.IFDRational
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    def exif_bytes(dto: str | None, make: str = "FUJIFILM", model: str = "X100V", orientation: int | None = None,
                   file_time: str | None = None, f_number: tuple[int, int] = (28, 10)) -> bytes:
        exif = Image.Exif()
        exif[0x010F] = make
        exif[0x0110] = model
        if file_time:
            exif[0x0132] = file_time
        if orientation:
            exif[0x0112] = orientation
        sub = {0x829D: rational(*f_number), 0x829A: rational(1, 250), 0x8827: 400, 0x920A: rational(23, 1), 0xA405: 35}
        if dto:
            sub[0x9003] = dto
        exif[0x8769] = sub
        return exif.tobytes()

    def load_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # earliest capture is a phone portrait stored landscape with Orientation 6 (green)
        Image.new("RGB", (600, 400), (30, 160, 60)).save(
            d / "a_portrait.jpg", exif=exif_bytes("2026:09:20 08:00:00", "Apple", "iPhone 15 Pro", orientation=6))
        for i, (name, dto, shade) in enumerate([("b.jpg", "2026:09:20 09:05:00", (70, 110, 150)),
                                                 ("c.jpg", "2026:09:20 10:30:00", (140, 90, 90)),
                                                 ("d.jpg", "2026:09:20 11:15:00", (90, 90, 140))]):
            Image.new("RGB", (600, 400), shade).save(d / name, exif=exif_bytes(dto, f_number=(28 + 20 * i, 10)))
        # an edited export: only IFD0 DateTime, four days later
        Image.new("RGB", (600, 400), (120, 120, 120)).save(
            d / "e_export.jpg", exif=exif_bytes(None, "Canon", "Canon EOS R6", file_time="2026:09:24 21:05:00"))
        photos = [str(d / n) for n in ("a_portrait.jpg", "b.jpg", "c.jpg", "d.jpg", "e_export.jpg")]

        # 1. normal run
        code, out, err = _run(photos + ["--output", str(d / "card.png")])
        data = load_json(d / "card.png.json")
        check("normal run exits 0", code == 0, err.strip())
        check("card is 1600x1460 PNG", code == 0 and Image.open(d / "card.png").size == (1600, 1460)
              and Image.open(d / "card.png").format == "PNG")
        check("included + skipped == inputs", data.get("included", 0) + data.get("skipped", 0) == len(photos), str(data.get("included")))

        # 2. portrait orientation: the earliest photo is a portrait, so the cover is the earliest landscape
        rec = {Path(r["path"]).name: r for r in data.get("records", [])}
        check("portrait recorded upright (400x600)", (rec.get("a_portrait.jpg", {}).get("width"), rec.get("a_portrait.jpg", {}).get("height")) == (400, 600),
              str(rec.get("a_portrait.jpg")))
        check("auto cover skips the portrait", Path(data.get("cover", {}).get("path", "")).name == "b.jpg", str(data.get("cover")))

        # 3. IFD0 DateTime is not a capture time
        check("export: captured_at null", "e_export.jpg" in rec and rec["e_export.jpg"]["captured_at"] is None, str(rec.get("e_export.jpg")))
        check("no false 'more than 24 hours' warning", not any("24 hours" in w for w in data.get("warnings", [])), str(data.get("warnings")))
        check("warning names the file-time-only image", any("IFD0 DateTime" in w and "e_export.jpg" in w for w in data.get("warnings", [])),
              str(data.get("warnings")))
        check("timeline span from DateTimeOriginal", data.get("time_span", {}).get("end") == "2026-09-20 11:15:00", str(data.get("time_span")))

        # 4. camera name without the repeated maker
        check("camera 'Canon' + 'Canon EOS R6' -> 'Canon EOS R6'", rec.get("e_export.jpg", {}).get("camera_model") == "Canon EOS R6",
              str(rec.get("e_export.jpg", {}).get("camera_model")))

        # 5. never write over an input photo
        before = _sha(d / "b.jpg")
        code, _, err = _run(photos + ["--output", str(d / "b.jpg")])
        check("--output == input refused, photo untouched", code == 2 and "input file" in err and _sha(d / "b.jpg") == before, err.strip())
        code, _, err = _run(photos + ["--output", str(d / "card2.png"), "--json", str(d / "c.jpg")])
        check("--json == input refused, nothing written", code == 2 and not (d / "card2.png").exists(), err.strip())
        code, _, err = _run(photos + ["--output", str(d / "card3.png"), "--json", str(d / "card3.png")])
        check("--json == --output refused", code == 2 and "--json must differ" in err, err.strip())

        # 6. Chinese title and subtitle get a font with Chinese glyphs, never boxes
        title, subtitle = "周日扫街 Sunday", "外滩 · 2026年9月20日"
        code, _, err = _run(photos + ["--output", str(d / "zh.png"), "--title", title, "--subtitle", subtitle])
        if code == 0:
            fonts = load_json(d / "zh.png.json").get("fonts", [])
            cjk = [f for f in fonts if f in image_io.CJK_FONTS or f in image_io.CJK_BOLD_FONTS]
            check("Chinese title -> fonts that cover it", bool(cjk) and all(image_io.font_covers(f, title + subtitle) for f in cjk), str(fonts))
        else:
            check("Chinese title without a Chinese font -> clear error", code == 2 and "Chinese" in err, err.strip())
        arial = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
        if arial.exists():
            code, _, err = _run(photos + ["--output", str(d / "zh_arial.png"), "--title", title, "--font", str(arial)])
            check("Latin-only --font with a Chinese title refused", code == 2 and "no glyphs" in err and not (d / "zh_arial.png").exists(),
                  err.strip())
            code, _, err = _run(photos + ["--output", str(d / "arial.png"), "--title", "Sunday walk", "--font", str(arial)])
            check("--font used for all text", code == 0 and load_json(d / "arial.png.json").get("fonts") == [str(arial)], err.strip())

        # 7. HEIC: skipped with the sips command; only HEIC -> error
        (d / "IMG_0001.HEIC").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
        code, _, err = _run(photos + [str(d / "IMG_0001.HEIC"), "--output", str(d / "heic.png")])
        data = load_json(d / "heic.png.json")
        if image_io.HEIF_SUPPORTED:
            check("HEIC (pillow-heif installed): no traceback", code in (0, 2))
        else:
            check("HEIC skipped with a warning and the sips command", code == 0 and "skipped" in err and "sips -s format jpeg" in err
                  and data.get("skipped") == 1 and "sips" in " ".join(data.get("skipped_details", [])), err.strip())
            code, _, err = _run([str(d / "IMG_0001.HEIC"), "--output", str(d / "heic_only.png")])
            check("only HEIC -> exit 2, nothing written", code == 2 and not (d / "heic_only.png").exists(), err.strip())

        # 8. Display P3 cover: profile kept, orange unchanged, card colours converted into P3
        p3_path = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
        if p3_path.exists():
            Image.new("RGB", (600, 400), (255, 100, 0)).save(d / "p3.png", icc_profile=p3_path.read_bytes(),
                                                              exif=exif_bytes("2026:09:20 07:00:00"))
            code, _, err = _run(photos + [str(d / "p3.png"), "--output", str(d / "p3card.png"), "--cover", str(d / "p3.png")])
            card, meta = image_io.open_image(d / "p3card.png") if code == 0 else (None, {})
            check("P3 cover: card embeds Display P3", code == 0 and "P3" in meta.get("color_space", ""), str(meta.get("color_space")) + err)
            check("P3 cover: orange unchanged (not washed out)", card is not None and card.getpixel((800, 300)) == (255, 100, 0),
                  str(card.getpixel((800, 300)) if card else None))
            if card is not None:
                background = image_io.to_srgb(card.crop((5, 1455, 6, 1456)), meta["icc_profile"]).getpixel((0, 0))
                check("P3 cover: background still #171716 once managed", all(abs(a - b) <= 2 for a, b in zip(background, (23, 23, 22))),
                      str(background))
        else:
            check("P3 checks skipped (no Display P3 profile on this system)", True)

        # 9. transparent cover takes the card background; .jpg output is a real JPEG
        rgba = Image.new("RGBA", (600, 400), (0, 0, 0, 0))
        rgba.save(d / "alpha.png")
        code, _, err = _run(photos + [str(d / "alpha.png"), "--output", str(d / "alpha.jpg"), "--cover", str(d / "alpha.png")])
        corner = Image.open(d / "alpha.jpg").convert("RGB").getpixel((10, 10)) if code == 0 else None
        check("transparent cover -> card background, not black", corner is not None and all(abs(a - b) <= 3 for a, b in zip(corner, (23, 23, 22))),
              f"{corner} {err.strip()}")
        check(".jpg output is a real JPEG", code == 0 and Image.open(d / "alpha.jpg").format == "JPEG")

        # 10. usage errors
        code, _, err = _run(["--output", str(d / "x.png")])
        check("no images -> exit 2", code == 2, err.strip())
        code, _, err = _run(photos + ["--output", str(d / "noext")])
        check("output without extension -> exit 2", code == 2 and "extension" in err, err.strip())

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
