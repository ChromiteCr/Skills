#!/usr/bin/env python3
"""Extract caption-safe EXIF fields from an image as JSON.

Requires Pillow. Reads IFD0 and the Exif sub-IFD (where cameras store aperture,
shutter, ISO, focal length, lens and capture time) through the shared
`image_io.py` next to this file. `captured_at` comes from DateTimeOriginal only;
a file that carries only IFD0 DateTime (its last edit or export time) gets
`captured_at: null`. GPS and other potentially sensitive metadata are
intentionally excluded. Missing values are emitted as null; this script never
guesses them.

Usage:
  python3 extract_exif.py IMAGE [--pretty]
  python3 extract_exif.py --selftest

Exit codes: 0 success, 1 unreadable image (HEIC included, with the conversion
command), 2 usage error or missing file.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import image_io  # noqa: E402  (shared copy; also checks that Pillow is installed)

KEYS = (
    "source_file",
    "captured_at",
    "camera_make",
    "camera_model",
    "camera",
    "lens",
    "exposure_time",
    "aperture",
    "iso",
    "focal_length_mm",
    "focal_length_35mm",
    "exposure_compensation_ev",
)


def exposure_text(number: float | None) -> str | None:
    """Format exposure time without replacing recorded precision by a guess."""
    if number is None or number <= 0:
        return None
    if number < 1:
        fraction = Fraction(number).limit_denominator(8000)
        return f"{fraction.numerator}/{fraction.denominator} s"
    return f"{number:g} s"


def extract(path: Path) -> dict[str, Any]:
    exif = image_io.read_exif(path)
    aperture = exif["f_number"]
    focal = exif["focal_length_mm"]
    compensation = exif["exposure_bias_ev"]
    result: dict[str, Any] = {
        "source_file": path.name,
        "captured_at": exif["captured_at"],
        "camera_make": exif["camera_make"],
        "camera_model": exif["camera_model"],
        "camera": exif["camera"],
        "lens": exif["lens"],
        "exposure_time": exposure_text(exif["exposure_time_s"]),
        "aperture": f"f/{aperture:g}" if aperture and aperture > 0 else None,
        "iso": exif["iso"],
        "focal_length_mm": round(focal, 3) if focal is not None and focal >= 0 else None,
        "focal_length_35mm": exif["focal_length_35mm"],
        "exposure_compensation_ev": round(compensation, 3) if compensation is not None else None,
    }
    return {key: result[key] for key in KEYS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract non-location EXIF fields for factual photo captions."
    )
    parser.add_argument("image", nargs="?", type=Path, help="path to an image file")
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression checks and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.image is None:
        parser.error("an image path is required (or --selftest)")
    if not args.image.is_file():
        parser.error(f"not a file: {args.image}")

    try:
        data = extract(args.image)
    except image_io.ImageIOError as exc:
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


# ---------------------------------------------------------------- self-test


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse errors
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


def selftest() -> int:
    from PIL import Image, TiffImagePlugin

    rational = TiffImagePlugin.IFDRational
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)

        # 1. camera layout: Make/Model in IFD0, exposure fields in the Exif sub-IFD
        exif = Image.Exif()
        exif[0x010F] = "FUJIFILM"
        exif[0x0110] = "X100V"
        exif[0x0132] = "2026:09:24 21:05:00"  # IFD0 DateTime = export time, not capture time
        exif[0x8769] = {
            0x829D: rational(28, 10),
            0x829A: rational(1, 250),
            0x8827: 400,
            0x920A: rational(23, 1),
            0xA405: 35,
            0x9204: rational(-2, 3),
            0x9003: "2026:09:20 17:42:10",
            0xA434: "23mm F2",
        }
        exif[0x8825] = {1: "N", 2: (rational(31, 1), rational(14, 1), rational(0, 1))}
        Image.new("RGB", (32, 24), (90, 90, 90)).save(d / "camera.jpg", exif=exif.tobytes())
        code, out, err = _run([str(d / "camera.jpg")])
        data = json.loads(out) if code == 0 else {}
        check("camera JPEG: exit 0", code == 0, err.strip())
        check("camera JPEG: every field non-null", data and all(data[k] is not None for k in KEYS), out.strip())
        check("aperture/shutter/ISO from the sub-IFD",
              data.get("aperture") == "f/2.8" and data.get("exposure_time") == "1/250 s" and data.get("iso") == 400,
              out.strip())
        check("capture time is DateTimeOriginal, not IFD0 DateTime", data.get("captured_at") == "2026-09-20 17:42:10",
              str(data.get("captured_at")))
        check("lens, focal length, 35 mm eq., EV", data.get("lens") == "23mm F2" and data.get("focal_length_mm") == 23.0
              and data.get("focal_length_35mm") == 35 and data.get("exposure_compensation_ev") == -0.667, out.strip())
        check("camera name without a repeated maker", data.get("camera") == "FUJIFILM X100V", str(data.get("camera")))
        check("GPS excluded (only the documented keys)", set(data) == set(KEYS) and "gps" not in out.lower(), out.strip())
        check("original keys kept", set(KEYS) - {"camera", "focal_length_35mm"} <= set(data), str(sorted(data)))

        # 2. only ISO, stored in the sub-IFD
        exif = Image.Exif()
        exif[0x8769] = {0x8827: 1600}
        Image.new("RGB", (8, 8)).save(d / "iso_only.jpg", exif=exif.tobytes())
        code, out, _ = _run([str(d / "iso_only.jpg")])
        data = json.loads(out) if code == 0 else {}
        check("ISO-only file: iso read, rest null",
              data.get("iso") == 1600 and data.get("aperture") is None and data.get("captured_at") is None, out.strip())

        # 3. export with only IFD0 DateTime: no capture time
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif[0x0110] = "Canon EOS R6"
        exif[0x0132] = "2026:09:24 21:05:00"
        Image.new("RGB", (8, 8)).save(d / "datetime_only.jpg", exif=exif.tobytes())
        code, out, _ = _run([str(d / "datetime_only.jpg")])
        data = json.loads(out) if code == 0 else {}
        check("IFD0 DateTime only -> captured_at null", code == 0 and data.get("captured_at") is None
              and "2026" not in out, out.strip())
        check("camera 'Canon' + 'Canon EOS R6' -> 'Canon EOS R6'", data.get("camera") == "Canon EOS R6",
              str(data.get("camera")))

        # 4. no EXIF at all
        Image.new("RGB", (8, 8)).save(d / "plain.png")
        code, out, _ = _run([str(d / "plain.png")])
        data = json.loads(out) if code == 0 else {}
        check("no EXIF -> all null", code == 0 and all(data[k] is None for k in KEYS if k != "source_file"), out.strip())

        # 5. HEIC without pillow-heif: clear message with the sips command, exit 1
        (d / "IMG_0001.HEIC").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
        code, out, err = _run([str(d / "IMG_0001.HEIC")])
        if image_io.HEIF_SUPPORTED:
            check("HEIC (pillow-heif installed: decoder error, no traceback)", code in (0, 1), err.strip())
        else:
            check("HEIC -> exit 1 with the sips command", code == 1 and "sips -s format jpeg" in err, err.strip())

        # 6. usage errors
        code, _, err = _run([str(d / "missing.jpg")])
        check("missing file -> exit 2", code == 2 and "not a file" in err, err.strip())

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
