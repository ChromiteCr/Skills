#!/usr/bin/env python3
"""Inspect EXIF and add a configurable metadata band below one photograph.

Reading and writing go through the shared `image_io.py` next to this file:
the photo is turned upright from its EXIF orientation, EXIF is read from IFD0
and the Exif sub-IFD, and the output embeds the source's RGB ICC profile
("keep" policy; Display P3 stays Display P3). CMYK or grey profiles are
converted to sRGB. Transparent areas are composited onto the band colour.

Type size: values start at 19% of the band height and labels at 0.63 of the
value size (at least 9 px); both shrink until every label and value fits its
cell, with at least 0.6 of the value size between columns. The
renderer stops with an error (and writes nothing) when the values would have
to be smaller than the readable minimum: 12 px or 0.6% of the output's long
edge, whichever is larger. `--band-ratio` changes the band height, not the
width of a cell, so it cannot cure a width overflow; fewer fields or a
narrower font can.

The capture time comes from DateTimeOriginal only. IFD0 DateTime is the
file's last edit or export time and is never shown as the capture time.

Usage:
  python3 render_exif_frame.py INPUT --inspect
  python3 render_exif_frame.py INPUT --output framed.png [options]
  python3 render_exif_frame.py --selftest

Exit codes: 0 success, 2 error (nothing written), 1 self-test failure.
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
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import image_io  # noqa: E402  (shared copy; also checks that Pillow is installed)

from PIL import Image, ImageCms, ImageColor, ImageDraw, ImageFont  # noqa: E402

FIELD_LABELS = {
    "aperture": "APERTURE",
    "shutter": "SHUTTER",
    "exposure_compensation": "EXP. COMP.",
    "iso": "ISO",
    "captured": "CAPTURED",
    "camera": "CAMERA",
}
DEFAULT_FIELDS = list(FIELD_LABELS)

VALUE_BAND_RATIO = 0.19  # value text height target, as a share of the band height
LABEL_RATIO = 0.12 / 0.19  # labels are smaller than values
MIN_LABEL_PX = 9
MIN_VALUE_PX = 12  # readable minimum: absolute floor ...
MIN_VALUE_FRACTION = 0.006  # ... and share of the output's long edge
EXIF_NOT_COPIED = "Source EXIF was read for display but was not copied to the output."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect EXIF and add a configurable metadata band below one photograph.",
        epilog="Exit codes: 0 success, 2 error (nothing written), 1 self-test failure.",
    )
    parser.add_argument("input", type=Path, nargs="?", help="source image")
    parser.add_argument("--output", type=Path, help="new framed image (.png, .jpg, .tif or .webp); must not exist yet")
    parser.add_argument("--inspect", action="store_true", help="print metadata JSON only")
    parser.add_argument(
        "--fields",
        default=",".join(DEFAULT_FIELDS),
        help="comma-separated fields: " + ",".join(DEFAULT_FIELDS),
    )
    parser.add_argument("--band-color", default="#F3F0E8", help="band colour, sRGB (default #F3F0E8)")
    parser.add_argument("--text-color", default="#171717", help="text colour, sRGB (default #171717)")
    parser.add_argument("--band-ratio", type=float, default=0.16, help="band height / photo height, 0.08-0.50")
    parser.add_argument("--padding-ratio", type=float, default=0.04, help="side padding / photo width, 0-0.20")
    parser.add_argument("--font", type=Path, help="TrueType/OpenType font path (default: an installed system font)")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression checks and exit")
    return parser.parse_args(argv)


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


# ---------------------------------------------------------------- metadata


def display_metadata(exif: dict[str, Any]) -> dict[str, str]:
    iso = exif["iso"]
    return {
        "aperture": image_io.format_f_number(exif["f_number"]) or "",
        "shutter": image_io.format_exposure(exif["exposure_time_s"]) or "",
        "exposure_compensation": image_io.format_ev(exif["exposure_bias_ev"]) or "",
        "iso": (f"{iso:g}" if isinstance(iso, float) else str(iso)) if iso is not None else "",
        "captured": exif["captured_at"] or "",  # DateTimeOriginal only
        "camera": exif["camera"] or "",
    }


def metadata_warnings(exif: dict[str, Any], metadata: dict[str, str], fields: list[str]) -> list[str]:
    warnings = []
    if not any(metadata.values()):
        warnings.append("No embedded EXIF values were found; every field is blank.")
    if "captured" in fields and not exif["captured_at"] and exif["file_modified_at"]:
        warnings.append(
            "captured: the file has no DateTimeOriginal. Its IFD0 DateTime is the last edit or export time, "
            "not a capture time, so CAPTURED is left blank."
        )
    return warnings


def report(size: tuple[int, int], metadata: dict[str, str], fields: list[str], color_space: str) -> dict[str, Any]:
    return {
        "oriented_source_dimensions": [size[0], size[1]],
        "metadata": metadata,
        "selected_fields": fields,
        "blank_fields": [field for field in fields if not metadata[field]],
        "color_space": color_space,
    }


# ---------------------------------------------------------------- colour


# Shared with the other photo scripts (image_io.py 1.1.0).
profile_space = image_io.profile_space
srgb_color_in_profile = image_io.srgb_color_in_profile


def parse_color(value: str, option: str) -> tuple[int, int, int]:
    try:
        return tuple(ImageColor.getrgb(value))[:3]
    except ValueError as exc:
        raise ValueError(f"{option}: not a colour: {value!r}") from exc


# ---------------------------------------------------------------- fonts


class Fonts:
    """One typeface at many sizes: resolved once, then reloaded by path (fast) while fitting."""

    def __init__(self, explicit: Path | None, text: str) -> None:
        self.warnings: list[str] = []
        if explicit is not None:
            if not explicit.is_file():
                raise ValueError(f"font does not exist: {explicit}")
            image_io.load_font(20, path=explicit)  # raises ImageIOError when unreadable
            if not image_io.font_covers(str(explicit), text):
                raise ValueError(f"font {explicit} has no glyphs for some characters in: {text}")
            self.path: str | None = str(explicit)
            self.description = str(explicit)
            return
        _, description = image_io.load_font(20, text=text)  # raises for Chinese text without a Chinese font
        if description.startswith("Pillow built-in bitmap font"):
            raise ValueError("no scalable font is installed and this Pillow has only a fixed 10 px font; pass --font")
        if description.startswith("Pillow built-in font"):
            self.path = None
            self.description = "Pillow built-in font"
            self.warnings.append("No system font was found; Pillow's built-in font was used. Pass --font to choose one.")
        else:
            self.path = description
            self.description = description

    @functools.lru_cache(maxsize=None)
    def get(self, size: int) -> Any:
        if self.path is None:
            return ImageFont.load_default(size=size)
        return image_io.load_font(size, path=self.path)[0]


def line_height(font: Any) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


# ---------------------------------------------------------------- layout


def label_px(value_px: int) -> int:
    return max(MIN_LABEL_PX, round(value_px * LABEL_RATIO))


def fit_type(
    draw: ImageDraw.ImageDraw,
    fonts: Fonts,
    texts: list[tuple[str, str, str]],
    cell_width: float,
    band_height: int,
    min_px: int,
) -> tuple[int | None, list[str], bool]:
    """(value_px, overflowing fields at min_px, band too short at min_px)."""

    def gap(size: int) -> int:  # minimum space between one column's text and the next column
        return max(6, round(0.6 * size))

    def too_wide(size: int) -> list[str]:
        value_font, label_font = fonts.get(size), fonts.get(label_px(size))
        room = cell_width - gap(size)
        return [
            field
            for field, label, value in texts
            if image_io.text_width(draw, label, label_font) > room or image_io.text_width(draw, value, value_font) > room
        ]

    def block(size: int) -> int:
        return line_height(fonts.get(label_px(size))) + round(0.15 * size) + line_height(fonts.get(size))

    def fits(size: int) -> bool:
        return block(size) <= 0.8 * band_height and not too_wide(size)

    max_px = max(min_px, round(VALUE_BAND_RATIO * band_height))
    size = image_io.fit_size(fits, min_px, max_px)
    if size is not None:
        return size, [], False
    return None, too_wide(min_px), block(min_px) > 0.8 * band_height


def check_output(output: Path | None, source: Path) -> Path:
    if output is None:
        raise ValueError("--output is required unless --inspect is used")
    out = image_io.check_output_path(output, [source])  # refuses the input file itself
    if out.exists():
        raise ValueError(f"output already exists: {out}; choose a new file name")
    if out.suffix.lower() not in image_io.OUTPUT_FORMATS:
        raise ValueError(f"unsupported output extension '{out.suffix}'; use .png, .jpg, .tif or .webp")
    return out


def render(args: argparse.Namespace, fields: list[str]) -> dict[str, Any]:
    source = args.input
    output = check_output(args.output, source)
    if not (0.08 <= args.band_ratio <= 0.50):
        raise ValueError("--band-ratio must be between 0.08 and 0.50")
    if not (0.0 <= args.padding_ratio <= 0.20):
        raise ValueError("--padding-ratio must be between 0 and 0.20")
    band_srgb = parse_color(args.band_color, "--band-color")
    text_srgb = parse_color(args.text_color, "--text-color")

    image, meta = image_io.open_image(source)  # upright, ICC kept
    exif = image_io.read_exif(source)
    metadata = display_metadata(exif)
    warnings = [EXIF_NOT_COPIED] + metadata_warnings(exif, metadata, fields)

    # colour: keep an RGB profile as-is; convert CMYK/grey profiles to sRGB; untagged stays sRGB
    icc = meta["icc_profile"]
    space = profile_space(icc)
    if icc and space == "RGB":
        policy, out_icc = "keep", icc
    elif icc and space in ("CMYK", "GRAY"):
        policy, out_icc = "converted to sRGB", image_io.srgb_icc_bytes()
        warnings.append(f"The source profile '{meta['color_space']}' is not RGB; the photo was converted to sRGB.")
    else:
        policy, out_icc = "untagged, sRGB embedded", None
        if icc:
            warnings.append("The embedded ICC profile could not be read; the photo was treated as sRGB.")
    band_rgb = srgb_color_in_profile(band_srgb, out_icc if policy == "keep" else None)
    text_rgb = srgb_color_in_profile(text_srgb, out_icc if policy == "keep" else None)
    if policy == "converted to sRGB":
        photo = image_io.to_srgb(image, icc, background=band_rgb)
    else:
        photo = image_io.to_rgb(image, band_rgb)
    if meta["has_alpha"]:
        warnings.append("Transparent areas were composited onto the band colour.")

    width, height = photo.size
    band_height = max(48, math.ceil(height * args.band_ratio))
    padding = math.ceil(width * args.padding_ratio)
    available = width - 2 * padding
    if available <= 0:
        raise ValueError("padding leaves no horizontal content area")
    cell_width = available / len(fields)
    long_edge = max(width, height + band_height)
    min_px = max(MIN_VALUE_PX, math.ceil(MIN_VALUE_FRACTION * long_edge))

    texts = [(field, FIELD_LABELS[field], metadata[field]) for field in fields]
    fonts = Fonts(args.font, " ".join(label + " " + value for _, label, value in texts))
    warnings += fonts.warnings
    canvas = Image.new("RGB", (width, height + band_height), band_rgb)
    draw = ImageDraw.Draw(canvas)
    value_px, too_wide, too_short = fit_type(draw, fonts, texts, cell_width, band_height, min_px)
    if value_px is None:
        if too_wide:
            raise ValueError(
                f"text does not fit field cell(s) even at the {min_px} px readable minimum: {', '.join(too_wide)}; "
                "select fewer fields (--fields) or pass a narrower font (--font). "
                "--band-ratio changes the band height, not the cell width, so raising it does not help"
            )
        raise ValueError(f"the band is too short for {min_px} px text; increase --band-ratio")
    label_size = label_px(value_px)
    value_font, label_font = fonts.get(value_px), fonts.get(label_size)

    canvas.paste(photo, (0, 0))
    v_gap = round(0.15 * value_px)
    block = line_height(label_font) + v_gap + line_height(value_font)
    label_y = height + (band_height - block) // 2
    value_y = label_y + line_height(label_font) + v_gap
    for index, (_, label, value) in enumerate(texts):
        x = round(padding + index * cell_width)
        draw.text((x, label_y), label, fill=text_rgb, font=label_font)
        if value:
            draw.text((x, value_y), value, fill=text_rgb, font=value_font)

    output.parent.mkdir(parents=True, exist_ok=True)
    image_io.save_image(canvas, output, icc_profile=out_icc, inputs=[source], overwrite=False)

    result = report(photo.size, metadata, fields, meta["color_space"])
    result.update(
        {
            "output": str(output),
            "output_dimensions": [canvas.width, canvas.height],
            "output_color_space": image_io.profile_name(out_icc or image_io.srgb_icc_bytes()),
            "color_policy": policy,
            "band_ratio": args.band_ratio,
            "padding_ratio": args.padding_ratio,
            "band_color": args.band_color,
            "text_color": args.text_color,
            "fonts": [fonts.description],
            "font_size_px": {"label": label_size, "value": value_px},
            "min_readable_value_px": min_px,
            "source_exif_copied": False,
            "warnings": warnings,
        }
    )
    return result


def inspect(args: argparse.Namespace, fields: list[str]) -> dict[str, Any]:
    size = image_io.oriented_size(args.input)
    exif = image_io.read_exif(args.input)
    with Image.open(args.input) as opened:
        icc = opened.info.get("icc_profile") or None
    metadata = display_metadata(exif)
    result = report(size, metadata, fields, image_io.profile_name(icc))
    result["warnings"] = metadata_warnings(exif, metadata, fields)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        if args.input is None:
            raise ValueError("an input image is required (or --selftest)")
        fields = parse_fields(args.fields)
        if not args.input.is_file():
            raise ValueError(f"input does not exist: {args.input}")
        result = inspect(args, fields) if args.inspect else render(args, fields)
    except (OSError, ValueError, image_io.ImageIOError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------- self-test


def _run(argv: list[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse errors
            code = int(exc.code or 0)
    try:
        data = json.loads(out.getvalue()) if code == 0 else {}
    except json.JSONDecodeError:
        data = {}
    return code, data, err.getvalue()


def _ink_rows(path: Path, top: int, threshold: int = 110) -> int:
    """Rows of the band (from `top` down) that contain dark text pixels."""
    with Image.open(path) as im:
        band = im.convert("L").crop((0, top, im.width, im.height))
    return sum(1 for y in range(band.height) if band.crop((0, y, band.width, y + 1)).getextrema()[0] < threshold)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selftest() -> int:
    from PIL import TiffImagePlugin

    rational = TiffImagePlugin.IFDRational
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    def camera_exif(make: str = "FUJIFILM", model: str = "X100V", orientation: int | None = None) -> bytes:
        exif = Image.Exif()
        exif[0x010F] = make
        exif[0x0110] = model
        exif[0x0132] = "2026:09:24 21:05:00"  # IFD0 DateTime: export time
        if orientation:
            exif[0x0112] = orientation
        exif[0x8769] = {
            0x829D: rational(28, 10),
            0x829A: rational(1, 250),
            0x8827: 400,
            0x9204: rational(-2, 3),
            0x9003: "2026:09:20 17:42:10",
        }
        return exif.tobytes()

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        Image.new("RGB", (1200, 800), (70, 110, 150)).save(d / "camera.jpg", exif=camera_exif(), quality=90)

        # 1. EXIF in the Exif sub-IFD, EV as a fraction, capture time from DateTimeOriginal
        code, data, err = _run([str(d / "camera.jpg"), "--inspect"])
        md = data.get("metadata", {})
        check("inspect: all six fields from the sub-IFD", code == 0 and all(md.get(f) for f in DEFAULT_FIELDS), str(md) + err)
        check("EV shown as -2/3 EV", md.get("exposure_compensation") == "-2/3 EV", str(md.get("exposure_compensation")))
        check("captured = DateTimeOriginal, not IFD0 DateTime", md.get("captured") == "2026-09-20 17:42:10",
              str(md.get("captured")))

        # 2. default render: sized system font, labels smaller than values, sRGB embedded
        code, data, err = _run([str(d / "camera.jpg"), "--output", str(d / "framed.png")])
        sizes = data.get("font_size_px", {})
        check("default render exits 0", code == 0, err.strip())
        check("output = source width x (height + band)", data.get("output_dimensions") == [1200, 800 + 128],
              str(data.get("output_dimensions")))
        check("value text >= readable minimum, labels smaller",
              sizes.get("value", 0) >= data.get("min_readable_value_px", 99) and sizes.get("label", 99) < sizes.get("value", 0),
              str(sizes))
        check("untagged source -> sRGB embedded", code == 0 and "sRGB" in image_io.open_image(d / "framed.png")[1]["color_space"])

        # 3. real resolution without --font: readable text (the old fallback drew 8 px glyphs)
        Image.new("RGB", (6000, 4000), (70, 110, 150)).save(d / "big.jpg", exif=camera_exif(), quality=80)
        code, data, err = _run([str(d / "big.jpg"), "--output", str(d / "big_framed.jpg")])
        value_px = data.get("font_size_px", {}).get("value", 0)
        rows = _ink_rows(d / "big_framed.jpg", 4000) if code == 0 else 0
        check("6000x4000 default: value text >= 36 px", code == 0 and value_px >= 36, f"{data.get('font_size_px')} {err}")
        check("6000x4000 default: glyph rows match the size", rows >= value_px, f"ink rows {rows}, value {value_px}px")

        # 4. a larger band never makes the text overflow (the old advice made it worse)
        ok = all(
            _run([str(d / "camera.jpg"), "--output", str(d / f"band{r}.png"), "--band-ratio", str(r)])[0] == 0
            for r in (0.08, 0.16, 0.30, 0.50)
        )
        check("band ratio 0.08 / 0.16 / 0.30 / 0.50 all fit", ok)

        # 5. the SKILL.md custom example
        arial = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
        argv = [str(d / "camera.jpg"), "--output", str(d / "custom.png"), "--fields", "aperture,shutter,iso,captured,camera",
                "--band-color", "#F3F0E8", "--text-color", "#171717", "--band-ratio", "0.16", "--padding-ratio", "0.04"]
        code, data, err = _run(argv + (["--font", str(arial)] if arial.exists() else []))
        check("SKILL.md custom example renders", code == 0, err.strip())

        # 6. portrait: Orientation 6, red bar on the stored left edge ends up on top
        stored = Image.new("RGB", (1200, 800), (70, 110, 150))
        ImageDraw.Draw(stored).rectangle((0, 0, 59, 799), fill=(220, 30, 30))
        stored.save(d / "rot6.jpg", exif=camera_exif(orientation=6), quality=90)
        code, data, err = _run([str(d / "rot6.jpg"), "--output", str(d / "rot6_framed.png")])
        top = Image.open(d / "rot6_framed.png").getpixel((400, 10)) if code == 0 else (0, 0, 0)
        check("portrait: output is upright 800 wide", data.get("output_dimensions") == [800, 1200 + 192],
              str(data.get("output_dimensions")) + err)
        check("portrait: stored left edge is now the top", top[0] > 180 and top[1] < 80, str(top))

        # 7. never write over the input; never replace an existing output
        before = _sha(d / "camera.jpg")
        code, _, err = _run([str(d / "camera.jpg"), "--output", str(d / "camera.jpg")])
        check("output == input refused, source untouched", code == 2 and "input file" in err and _sha(d / "camera.jpg") == before,
              err.strip())
        before = _sha(d / "framed.png")
        code, _, err = _run([str(d / "camera.jpg"), "--output", str(d / "framed.png")])
        check("existing output refused, not replaced", code == 2 and "already exists" in err and _sha(d / "framed.png") == before,
              err.strip())
        code, _, err = _run([str(d / "camera.jpg")])
        check("missing --output -> actionable error", code == 2 and "--output is required" in err, err.strip())

        # 8. only IFD0 DateTime: CAPTURED stays blank, with a warning
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif[0x0110] = "Canon EOS R6"
        exif[0x0132] = "2026:09:24 21:05:00"
        Image.new("RGB", (1200, 800), (90, 90, 90)).save(d / "export.jpg", exif=exif.tobytes())
        code, data, err = _run([str(d / "export.jpg"), "--output", str(d / "export_framed.png")])
        check("DateTime only: CAPTURED blank", code == 0 and data["metadata"]["captured"] == "" and "captured" in data["blank_fields"],
              str(data.get("metadata")) + err)
        check("DateTime only: warning says why", any("DateTimeOriginal" in w for w in data.get("warnings", [])),
              str(data.get("warnings")))
        check("camera name not repeated", data.get("metadata", {}).get("camera") == "Canon EOS R6")

        # 9. HEIC and undecodable input: clear error, nothing written
        (d / "IMG_0001.HEIC").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
        code, _, err = _run([str(d / "IMG_0001.HEIC"), "--output", str(d / "heic_framed.png")])
        if image_io.HEIF_SUPPORTED:
            check("HEIC (pillow-heif installed): no traceback", code in (0, 2))
        else:
            check("HEIC -> exit 2 with the sips command", code == 2 and "sips -s format jpeg" in err
                  and not (d / "heic_framed.png").exists(), err.strip())
        (d / "broken.jpg").write_bytes(b"not an image")
        code, _, err = _run([str(d / "broken.jpg"), "--output", str(d / "broken_framed.png")])
        check("undecodable input -> exit 2, nothing written", code == 2 and not (d / "broken_framed.png").exists(), err.strip())

        # 10. Display P3: profile kept, saturated orange unchanged, band colour still #F3F0E8 once managed
        p3_path = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
        if p3_path.exists():
            p3 = p3_path.read_bytes()
            Image.new("RGB", (1200, 800), (255, 100, 0)).save(d / "p3.png", icc_profile=p3)
            code, data, err = _run([str(d / "p3.png"), "--output", str(d / "p3_framed.png")])
            framed, meta = image_io.open_image(d / "p3_framed.png") if code == 0 else (None, {})
            check("P3: output embeds Display P3", code == 0 and "P3" in meta.get("color_space", ""), str(meta.get("color_space")) + err)
            check("P3: orange pixel unchanged (not washed out)", framed is not None and framed.getpixel((100, 100)) == (255, 100, 0),
                  str(framed.getpixel((100, 100)) if framed else None))
            if framed is not None:
                band = image_io.to_srgb(framed.crop((0, 900, 4, 904)), meta["icc_profile"]).getpixel((0, 0))
                check("P3: band shows #F3F0E8 after colour management", all(abs(a - b) <= 2 for a, b in zip(band, (243, 240, 232))),
                      str(band))
        else:
            check("P3 checks skipped (no Display P3 profile on this system)", True)

        # 11. transparent PNG: transparent area takes the band colour, not black
        rgba = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
        ImageDraw.Draw(rgba).rectangle((400, 200, 800, 600), fill=(200, 30, 30, 255))
        rgba.save(d / "alpha.png")
        code, data, err = _run([str(d / "alpha.png"), "--output", str(d / "alpha_framed.png"), "--band-color", "#F3F0E8"])
        corner = Image.open(d / "alpha_framed.png").convert("RGB").getpixel((5, 5)) if code == 0 else None
        check("transparent -> band colour, not black", corner == (243, 240, 232), f"{corner} {err}")

        # 12. overflow on a narrow image: error names the fields, no band-ratio advice, nothing written
        Image.new("RGB", (400, 600), (70, 110, 150)).save(d / "narrow.jpg", exif=camera_exif("Apple", "iPhone 15 Pro Max"))
        code, _, err = _run([str(d / "narrow.jpg"), "--output", str(d / "narrow_framed.png")])
        check("narrow overflow -> exit 2, names fields", code == 2 and "camera" in err and not (d / "narrow_framed.png").exists(),
              err.strip())
        check("overflow advice: fewer fields / narrower font, not a bigger band",
              "fewer fields" in err and "raising it does not help" in err, err.strip())

        # 13. Chinese text gets a font with Chinese glyphs (or a clear error), never boxes
        #     (EXIF ASCII tags written by Pillow cannot carry Chinese, so the font choice is tested directly)
        try:
            font = Fonts(None, "CAMERA 华为 测试相机").description
            check("Chinese text -> font with Chinese glyphs", font in image_io.CJK_FONTS and image_io.font_covers(font, "华为测试相机"),
                  font)
        except image_io.ImageIOError as exc:
            check("Chinese text without a Chinese font -> clear error", "Chinese" in str(exc), str(exc))
        if arial.exists():
            try:
                Fonts(arial, "CAMERA 测试相机")
                check("Latin-only --font with Chinese text refused", False, "no error")
            except ValueError as exc:
                check("Latin-only --font with Chinese text refused", "no glyphs" in str(exc), str(exc))

        # 14. usage errors
        code, _, err = _run([str(d / "camera.jpg"), "--inspect", "--fields", "aperture,gps"])
        check("unknown field -> exit 2", code == 2 and "unknown field" in err, err.strip())

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
