#!/usr/bin/env python3
"""Shared image input/output for the photo skills.

Identical copies of this file live in every skill that uses it, and
scripts/validate.sh checks that all copies have the same sha256. To change it,
edit one copy, run `python3 image_io.py --selftest`, then copy it over the
others.

- open_image(): applies the EXIF orientation, keeps and names the ICC profile,
  and explains HEIC instead of failing with a traceback.
- read_exif(): reads IFD0 and the Exif sub-IFD. Only DateTimeOriginal counts as
  the capture time; IFD0 DateTime is the file's last edit or export time.
- to_rgb(), to_srgb(), choose_output_profile(), srgb_color_in_profile():
  composite transparency onto a chosen background, convert between ICC
  profiles, and express a design colour (given in sRGB) in the output profile.
- check_output_path(), save_image(): never overwrite an input, embed the ICC
  profile, write JPEG at 4:4:4.
- load_font(), fit_size(): pick an installed font that has the glyphs the text
  needs (Chinese included) and find the largest size that fits.

Usage:
  python3 image_io.py info PHOTO [PHOTO ...]   # orientation, colour space, EXIF as JSON
  python3 image_io.py --selftest
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from PIL import ExifTags, Image, ImageCms, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - depends on the host environment
    print("error: Pillow is required (python3 -m pip install Pillow)", file=sys.stderr)
    raise SystemExit(2)

__version__ = "1.1.0"

try:  # optional: HEIC/HEIF support
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - depends on the host environment
    HEIF_SUPPORTED = False

HEIF_EXTS = {".heic", ".heif", ".hif"}
RASTER_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".gif"}
READABLE_EXTS = RASTER_EXTS | (HEIF_EXTS if HEIF_SUPPORTED else set())
OUTPUT_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".tif": "TIFF", ".tiff": "TIFF", ".webp": "WEBP"}

EXIF_IFD = 0x8769
GPS_IFD = 0x8825
ORIENTATION_TAG = 0x0112


class ImageIOError(Exception):
    """A problem the user can act on. The message is safe to print as-is."""


# ---------------------------------------------------------------- reading


def heif_hint(path: str | Path) -> str:
    p = Path(path)
    return (
        f"{p.name}: HEIC/HEIF needs the pillow-heif package (python3 -m pip install pillow-heif). "
        f'On macOS you can convert first and keep the EXIF: sips -s format jpeg "{p}" --out "{p.with_suffix(".jpg")}"'
    )


def _looks_like_heif(p: Path) -> bool:
    try:
        head = p.read_bytes()[:32]
    except OSError:
        return False
    return any(brand in head for brand in (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1", b"ftypmsf1", b"ftypheim"))


def has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (img.mode == "P" and "transparency" in img.info)


def profile_name(icc: bytes | None) -> str:
    """Human-readable name of an embedded ICC profile ("Display P3", "sRGB IEC61966-2.1", ...)."""
    if not icc:
        return "untagged (treated as sRGB)"
    try:
        name = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip()
    except Exception:
        return "embedded ICC profile (unreadable)"
    return name or "embedded ICC profile (unnamed)"


def open_image(path: str | Path, *, apply_orientation: bool = True) -> tuple[Image.Image, dict[str, Any]]:
    """Open a photo upright, with its ICC profile kept.

    Returns (image, meta). meta has: path, name, format, mode, size (after
    orientation), orientation (the EXIF value 1-8), icc_profile (bytes or None),
    color_space (profile name), has_alpha. Raises ImageIOError for missing,
    unreadable and HEIC files (with the conversion command).
    """
    p = Path(path).expanduser()
    if not p.is_file():
        raise ImageIOError(f"not a file: {p}")
    if p.suffix.lower() in HEIF_EXTS and not HEIF_SUPPORTED:
        raise ImageIOError(heif_hint(p))
    try:
        with Image.open(p) as src:
            src.load()
            fmt = src.format
            icc = src.info.get("icc_profile") or None
            try:
                orientation = int(src.getexif().get(ORIENTATION_TAG, 1) or 1)
            except Exception:
                orientation = 1
            img = ImageOps.exif_transpose(src) if apply_orientation else src.copy()
    except UnidentifiedImageError as exc:
        if _looks_like_heif(p) and not HEIF_SUPPORTED:
            raise ImageIOError(heif_hint(p)) from exc
        raise ImageIOError(f"{p.name}: not a readable image") from exc
    except OSError as exc:
        raise ImageIOError(f"{p.name}: cannot read image ({exc})") from exc
    if icc:
        img.info["icc_profile"] = icc
    meta = {
        "path": str(p),
        "name": p.name,
        "format": fmt,
        "mode": img.mode,
        "size": img.size,
        "orientation": orientation if orientation in range(1, 9) else 1,
        "icc_profile": icc,
        "color_space": profile_name(icc),
        "has_alpha": has_alpha(img),
    }
    return img, meta


def oriented_size(path: str | Path) -> tuple[int, int]:
    """Displayed (width, height) after EXIF orientation, without decoding pixels."""
    p = Path(path).expanduser()
    if p.suffix.lower() in HEIF_EXTS and not HEIF_SUPPORTED:
        raise ImageIOError(heif_hint(p))
    try:
        with Image.open(p) as im:
            w, h = im.size
            try:
                orientation = int(im.getexif().get(ORIENTATION_TAG, 1) or 1)
            except Exception:
                orientation = 1
    except UnidentifiedImageError as exc:
        if _looks_like_heif(p) and not HEIF_SUPPORTED:
            raise ImageIOError(heif_hint(p)) from exc
        raise ImageIOError(f"{p.name}: not a readable image") from exc
    except OSError as exc:
        raise ImageIOError(f"{p.name}: cannot read image ({exc})") from exc
    return (h, w) if orientation in (5, 6, 7, 8) else (w, h)


# ---------------------------------------------------------------- EXIF


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = str(value).replace("\x00", "").strip()
    if any(ord(c) > 127 for c in text):
        # Pillow decodes ASCII-typed tags as Latin-1, so a UTF-8 model name such as
        # "测试机" arrives as mojibake. Undo that only when it round-trips cleanly.
        try:
            text = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text or None


def _number(value: Any) -> float | None:
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    try:
        number = float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _exif_datetime(value: Any) -> str | None:
    """'2026:08:31 18:30:05' -> '2026-08-31 18:30:05'; blank or zero dates -> None."""
    text = _clean_text(value)
    if not text:
        return None
    m = re.match(r"^(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})", text)
    if not m or m.group(1) == "0000" or m.group(2) == "00":
        return None
    return "{}-{}-{} {}:{}:{}".format(*m.groups())


_MAKE_NOISE = re.compile(r"\b(CORPORATION|CORP\.?|COMPANY|CO\.?|LTD\.?|INC\.?|IMAGING|CAMERA|AG|GMBH)\b[,.]?", re.I)


def camera_name(make: str | None, model: str | None) -> str | None:
    """'Canon' + 'Canon EOS R5' -> 'Canon EOS R5'; 'NIKON CORPORATION' + 'NIKON Z 6' -> 'NIKON Z 6'."""
    make = _clean_text(make)
    model = _clean_text(model)
    if not model:
        return make
    if not make:
        return model
    short = re.sub(r"\s+", " ", _MAKE_NOISE.sub("", make)).strip(" ,.") or make
    lowered = model.lower()
    if lowered.startswith(make.lower()) or lowered.startswith(short.split()[0].lower()):
        return model
    return f"{short} {model}"


def read_exif(source: str | Path | Image.Image) -> dict[str, Any]:
    """Caption-safe EXIF fields from IFD0 and the Exif sub-IFD.

    captured_at is DateTimeOriginal only (None when absent). file_modified_at is
    IFD0 DateTime: the last edit/export time, never a capture time. GPS values
    are not returned, only whether they exist.
    """
    if isinstance(source, Image.Image):
        exif = source.getexif()
    else:
        p = Path(source).expanduser()
        if p.suffix.lower() in HEIF_EXTS and not HEIF_SUPPORTED:
            raise ImageIOError(heif_hint(p))
        try:
            with Image.open(p) as im:
                exif = im.getexif()
        except UnidentifiedImageError as exc:
            if _looks_like_heif(p) and not HEIF_SUPPORTED:
                raise ImageIOError(heif_hint(p)) from exc
            raise ImageIOError(f"{p.name}: not a readable image") from exc
        except OSError as exc:
            raise ImageIOError(f"{p.name}: cannot read image ({exc})") from exc

    named: dict[str, Any] = {}
    for tag, value in exif.items():
        named[ExifTags.TAGS.get(tag, str(tag))] = value
    try:
        sub = exif.get_ifd(EXIF_IFD)
    except Exception:
        sub = {}
    for tag, value in sub.items():
        named[ExifTags.TAGS.get(tag, str(tag))] = value
    try:
        has_gps = bool(exif.get_ifd(GPS_IFD))
    except Exception:
        has_gps = False

    make = _clean_text(named.get("Make"))
    model = _clean_text(named.get("Model"))
    iso = _number(named.get("PhotographicSensitivity") or named.get("ISOSpeedRatings"))
    focal35 = _number(named.get("FocalLengthIn35mmFilm"))
    orientation = _number(named.get("Orientation"))
    return {
        "camera_make": make,
        "camera_model": model,
        "camera": camera_name(make, model),
        "lens": _clean_text(named.get("LensModel")),
        "lens_make": _clean_text(named.get("LensMake")),
        "f_number": _number(named.get("FNumber")),
        "exposure_time_s": _number(named.get("ExposureTime")),
        "iso": int(iso) if iso is not None and iso >= 0 and float(iso).is_integer() else iso,
        "focal_length_mm": _number(named.get("FocalLength")),
        "focal_length_35mm": int(focal35) if focal35 else None,
        "exposure_bias_ev": _number(named.get("ExposureBiasValue")),
        "captured_at": _exif_datetime(named.get("DateTimeOriginal")),
        "captured_offset": _clean_text(named.get("OffsetTimeOriginal")),
        "digitized_at": _exif_datetime(named.get("DateTimeDigitized")),
        "file_modified_at": _exif_datetime(named.get("DateTime")),
        "orientation": int(orientation) if orientation and int(orientation) in range(1, 9) else 1,
        "has_gps": has_gps,
        "has_serial_number": bool(named.get("BodySerialNumber") or named.get("LensSerialNumber")),
    }


def format_exposure(seconds: float | None) -> str | None:
    """1/250 -> '1/250 s'; 0.8 -> '0.8 s'; 2 -> '2 s'."""
    if seconds is None or seconds <= 0:
        return None
    if seconds < 1:
        inverse = 1 / seconds
        if abs(inverse - round(inverse)) < 0.02 * inverse:
            return f"1/{round(inverse)} s"
        return f"{seconds:.2g} s"
    return f"{seconds:g} s"


def format_f_number(value: float | None) -> str | None:
    if value is None or value <= 0:
        return None
    return f"f/{round(value, 1):g}"


def format_focal(mm: float | None) -> str | None:
    if mm is None or mm <= 0:
        return None
    return f"{round(mm)} mm" if abs(mm - round(mm)) < 0.05 else f"{mm:.1f} mm"


def format_ev(value: float | None) -> str | None:
    """-0.666667 -> '-2/3 EV'; 1.333 -> '+1 1/3 EV'; 0 -> '0 EV'; 0.7 -> '+0.7 EV'."""
    if value is None:
        return None
    if abs(value) < 1e-6:
        return "0 EV"
    sign = "+" if value > 0 else "-"
    magnitude = abs(value)
    best = min((Fraction(round(magnitude * d), d) for d in (1, 2, 3)), key=lambda f: abs(float(f) - magnitude))
    if abs(float(best) - magnitude) < 0.02:
        whole, rest = divmod(best.numerator, best.denominator)
        if rest == 0:
            body = f"{whole}"
        elif whole == 0:
            body = f"{rest}/{best.denominator}"
        else:
            body = f"{whole} {rest}/{best.denominator}"
    else:
        body = f"{magnitude:.1f}"
    return f"{sign}{body} EV"


# ---------------------------------------------------------------- colour


_SRGB_PROFILE: Any = None


def srgb_profile() -> Any:
    global _SRGB_PROFILE
    if _SRGB_PROFILE is None:
        _SRGB_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    return _SRGB_PROFILE


def srgb_icc_bytes() -> bytes:
    return srgb_profile().tobytes()


def _intent(name: str) -> Any:
    table = getattr(ImageCms, "Intent", None)
    if table is not None:
        return {"perceptual": table.PERCEPTUAL, "relative": table.RELATIVE_COLORIMETRIC}[name]
    return {"perceptual": 0, "relative": 1}[name]  # pragma: no cover - Pillow < 10


def to_rgb(img: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """RGB copy of any mode. Transparent areas become `background`, never black."""
    if img.mode == "RGB":
        return img
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16N", "I"):
        scale = 1 / 256 if img.mode.startswith("I;16") else 1 / 65536
        return img.convert("I").point(lambda v: v * scale).convert("L").convert("RGB")
    if has_alpha(img):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, tuple(background) + (255,))
        base.alpha_composite(rgba)
        out = base.convert("RGB")
    else:
        out = img.convert("RGB")
    if "icc_profile" in img.info and img.mode != "CMYK":
        out.info["icc_profile"] = img.info["icc_profile"]
    return out


def to_srgb(
    img: Image.Image,
    icc: bytes | None,
    *,
    intent: str = "relative",
    background: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Convert from the embedded profile to sRGB. Untagged input is treated as sRGB already."""
    if img.mode not in ("RGB", "CMYK", "L"):
        img = to_rgb(img, background)
    if not icc:
        return img if img.mode == "RGB" else img.convert("RGB")
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        out = ImageCms.profileToProfile(img, src, srgb_profile(), renderingIntent=_intent(intent), outputMode="RGB")
    except Exception as exc:
        raise ImageIOError(f"cannot convert from the embedded profile '{profile_name(icc)}' to sRGB ({exc})") from exc
    out.info["icc_profile"] = srgb_icc_bytes()
    return out


def profile_space(icc: bytes | None) -> str | None:
    """'RGB', 'CMYK', 'GRAY' ... for a readable ICC profile, else None."""
    if not icc:
        return None
    try:
        return ImageCms.ImageCmsProfile(io.BytesIO(icc)).profile.xcolor_space.strip().upper()
    except Exception:
        return None


def choose_output_profile(iccs: Iterable[bytes | None]) -> tuple[str, bytes | None]:
    """One colour space for an RGB canvas that combines one or more photos.

    ("keep", icc): every input has the same RGB profile (same name), or none, so
    paste as-is and embed that profile. ("srgb", sRGB bytes): profiles differ, or
    the shared profile is not an RGB one (CMYK, grey), so convert each photo with
    to_srgb() before pasting.
    """
    iccs = list(iccs)
    names = {profile_name(icc) for icc in iccs}
    if len(names) <= 1:
        first = iccs[0] if iccs else None
        if first is None or profile_space(first) == "RGB":
            return "keep", first
    return "srgb", srgb_icc_bytes()


def srgb_color_in_profile(rgb: tuple[int, int, int], icc: bytes | None) -> tuple[int, int, int]:
    """The sRGB colour `rgb` expressed in the output profile, so it looks as specified once that profile is embedded."""
    if not icc:
        return tuple(rgb)[:3]
    try:
        pixel = ImageCms.profileToProfile(
            Image.new("RGB", (1, 1), tuple(rgb)[:3]),
            srgb_profile(),
            ImageCms.ImageCmsProfile(io.BytesIO(icc)),
            renderingIntent=_intent("relative"),
            outputMode="RGB",
        )
        return tuple(pixel.getpixel((0, 0)))[:3]
    except Exception:
        return tuple(rgb)[:3]


# ---------------------------------------------------------------- writing


def check_output_path(
    output: str | Path,
    inputs: Iterable[str | Path] = (),
    *,
    overwrite: bool = True,
    overwrite_flag: str | None = None,
) -> Path:
    """Refuse to write over an input file (always) or an existing file (unless overwrite).

    overwrite_flag names the caller's command-line option (e.g. "--overwrite") for
    the error message; leave it None when the script has no such option.
    """
    out = Path(output).expanduser()
    out_abs = out.resolve() if out.parent.exists() else out.absolute()
    for src in inputs:
        s = Path(src).expanduser()
        same = False
        if s.exists() and out.exists():
            try:
                same = os.path.samefile(s, out)
            except OSError:
                same = False
        if same or s.resolve() == out_abs:
            raise ImageIOError(f"refusing to write {out}: it is an input file. Choose a different output name.")
    if out.is_dir():
        raise ImageIOError(f"{out} is a directory; give a file name")
    if out.exists() and not overwrite:
        hint = f" or pass {overwrite_flag} to replace it" if overwrite_flag else ""
        raise ImageIOError(f"{out} already exists; choose a different output name{hint}")
    return out


def save_image(
    img: Image.Image,
    output: str | Path,
    *,
    icc_profile: bytes | None = None,
    inputs: Iterable[str | Path] = (),
    overwrite: bool = True,
    overwrite_flag: str | None = None,
    quality: int = 95,
    background: tuple[int, int, int] = (255, 255, 255),
    exif: bytes | None = None,
) -> Path:
    """Write with the ICC profile embedded (sRGB when icc_profile is None).

    JPEG is written at 4:4:4 chroma; alpha is composited onto `background`
    because JPEG cannot store it. The format follows the file extension.
    """
    out = check_output_path(output, inputs, overwrite=overwrite, overwrite_flag=overwrite_flag)
    fmt = OUTPUT_FORMATS.get(out.suffix.lower())
    if fmt is None:
        raise ImageIOError(f"unsupported output extension '{out.suffix}' (use .jpg, .png, .tif or .webp)")
    icc = icc_profile if icc_profile is not None else srgb_icc_bytes()
    params: dict[str, Any] = {"icc_profile": icc}
    if fmt == "JPEG":
        img = to_rgb(img, background)
        params.update(quality=quality, subsampling=0, optimize=True)
    elif fmt == "WEBP":
        params.update(quality=quality)
    if exif:
        params["exif"] = exif
    if not out.parent.exists():
        raise ImageIOError(f"output folder does not exist: {out.parent}")
    img.save(out, fmt, **params)
    return out


# ---------------------------------------------------------------- fonts


CJK_FONTS = (
    # macOS (checked on macOS 26, where /System/Library/Fonts/PingFang.ttc does not exist)
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)
CJK_BOLD_FONTS = (
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
) + CJK_FONTS
LATIN_FONTS = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "DejaVuSans.ttf",
)
LATIN_BOLD_FONTS = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "DejaVuSans-Bold.ttf",
)

_CJK_RE = re.compile("[\u2e80-\u2fff\u3000-\u30ff\u3100-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]")


def needs_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def font_covers(path: str, text: str) -> bool:
    """True when the font has a glyph for every visible character (checked with fontTools if installed)."""
    try:
        import logging

        from fontTools.ttLib import TTCollection, TTFont  # type: ignore

        logging.getLogger("fontTools").setLevel(logging.ERROR)
    except Exception:
        return True  # cannot check; trust the candidate list
    chars = {ord(c) for c in text if not c.isspace()}
    if not chars:
        return True
    try:
        if path.lower().endswith((".ttc", ".otc")):
            fonts = TTCollection(path, lazy=True).fonts[:1]
        else:
            fonts = [TTFont(path, lazy=True)]
        cmap = fonts[0].getBestCmap() or {}
    except Exception:
        return True
    return chars <= set(cmap)


def load_font(size: float, *, path: str | Path | None = None, text: str = "", bold: bool = False) -> tuple[Any, str]:
    """(font, description). An explicit path wins; otherwise the first installed candidate covering `text`.

    Raises ImageIOError when the text needs Chinese glyphs and no installed font
    has them, rather than rendering boxes.
    """
    px = max(1, int(round(size)))
    if path:
        try:
            return ImageFont.truetype(str(path), px), str(path)
        except OSError as exc:
            raise ImageIOError(f"cannot load font {path}: {exc}") from exc
    cjk = needs_cjk(text)
    if cjk:
        candidates = CJK_BOLD_FONTS if bold else CJK_FONTS
    else:
        candidates = (LATIN_BOLD_FONTS if bold else LATIN_FONTS) + CJK_FONTS
    for candidate in candidates:
        if os.path.isabs(candidate) and not os.path.exists(candidate):
            continue
        try:
            font = ImageFont.truetype(candidate, px)
        except OSError:
            continue
        if text and not font_covers(candidate, text):
            continue
        return font, candidate
    if cjk:
        raise ImageIOError("no installed font has Chinese glyphs; pass a font file with --font")
    try:
        return ImageFont.load_default(size=px), f"Pillow built-in font at {px}px"
    except TypeError:  # Pillow < 10.1 has no sized default font
        return ImageFont.load_default(), "Pillow built-in bitmap font (fixed small size; pass --font)"


def text_width(draw: ImageDraw.ImageDraw, text: str, font: Any) -> float:
    return float(draw.textlength(text, font=font))


def fit_size(fits: Callable[[int], bool], min_size: int, max_size: int) -> int | None:
    """Largest integer size in [min_size, max_size] with fits(size) True; None if even min_size fails.

    `fits` must be monotone (true for small sizes, false above some size).
    """
    lo, hi = int(min_size), int(max_size)
    if hi < lo or not fits(lo):
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


# ---------------------------------------------------------------- CLI and self-test


def info(path: str) -> dict[str, Any]:
    img, meta = open_image(path)
    exif = read_exif(path)
    meta = {k: v for k, v in meta.items() if k != "icc_profile"}
    meta["exif"] = exif
    meta["exif_display"] = {
        "camera": exif["camera"],
        "aperture": format_f_number(exif["f_number"]),
        "shutter": format_exposure(exif["exposure_time_s"]),
        "iso": f"ISO {exif['iso']}" if exif["iso"] is not None else None,
        "focal": format_focal(exif["focal_length_mm"]),
        "exposure_bias": format_ev(exif["exposure_bias_ev"]),
    }
    return meta


def selftest() -> int:
    from PIL import TiffImagePlugin

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # 1. orientation 6: stored landscape, displayed portrait
        exif = Image.Exif()
        exif[ORIENTATION_TAG] = 6
        Image.new("RGB", (60, 40), (200, 30, 30)).save(d / "rot6.jpg", exif=exif.tobytes())
        img, meta = open_image(d / "rot6.jpg")
        check("orientation 6 -> portrait", img.size == (40, 60) and meta["orientation"] == 6, str(img.size))
        check("oriented_size without decode", oriented_size(d / "rot6.jpg") == (40, 60))

        # 2. EXIF in the Exif sub-IFD, DateTime vs DateTimeOriginal
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif[0x0110] = "Canon EOS R5"
        exif[0x0132] = "2026:09:01 10:00:00"
        exif[EXIF_IFD] = {
            0x829D: TiffImagePlugin.IFDRational(28, 10),
            0x829A: TiffImagePlugin.IFDRational(1, 250),
            0x8827: 400,
            0x920A: TiffImagePlugin.IFDRational(35, 1),
            0x9204: TiffImagePlugin.IFDRational(-2, 3),
            0x9003: "2026:08:31 18:30:05",
            0xA434: "RF24-70mm F2.8 L IS USM",
        }
        Image.new("RGB", (32, 24), (90, 90, 90)).save(d / "exif.jpg", exif=exif.tobytes())
        e = read_exif(d / "exif.jpg")
        check("Exif sub-IFD read", e["f_number"] == 2.8 and e["iso"] == 400 and e["focal_length_mm"] == 35.0, str(e))
        check("capture time is DateTimeOriginal", e["captured_at"] == "2026-08-31 18:30:05")
        check("IFD0 DateTime kept apart", e["file_modified_at"] == "2026-09-01 10:00:00")
        check("lens read", e["lens"] == "RF24-70mm F2.8 L IS USM")
        check("shutter 1/250 s", format_exposure(e["exposure_time_s"]) == "1/250 s", str(format_exposure(e["exposure_time_s"])))
        check("EV -2/3", format_ev(e["exposure_bias_ev"]) == "-2/3 EV", str(format_ev(e["exposure_bias_ev"])))
        check("EV +1 1/3", format_ev(1.3333) == "+1 1/3 EV")
        check("EV 0 and 0.7", format_ev(0.0) == "0 EV" and format_ev(0.7) == "+0.7 EV")
        check("f/2.8, 35 mm", format_f_number(2.8) == "f/2.8" and format_focal(35.0) == "35 mm")
        check("UTF-8 model name repaired", _clean_text("测试机".encode("utf-8").decode("latin-1")) == "测试机"
              and _clean_text("Café") == "Café")
        check("camera name dedup", e["camera"] == "Canon EOS R5"
              and camera_name("NIKON CORPORATION", "NIKON Z 6") == "NIKON Z 6"
              and camera_name("Apple", "iPhone 15 Pro") == "Apple iPhone 15 Pro")
        Image.new("RGB", (8, 8)).save(d / "noexif.jpg")
        check("no DateTimeOriginal -> None", read_exif(d / "noexif.jpg")["captured_at"] is None)

        # 3. transparency composited onto the given background, not black
        rgba = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        check("transparent -> background", to_rgb(rgba, (250, 248, 240)).getpixel((0, 0)) == (250, 248, 240))

        # 4. ICC: keep Display P3, convert to sRGB, choose a common space
        p3_path = "/System/Library/ColorSync/Profiles/Display P3.icc"
        if os.path.exists(p3_path):
            p3 = Path(p3_path).read_bytes()
            Image.new("RGB", (8, 8), (230, 90, 40)).save(d / "p3.jpg", icc_profile=p3, quality=95)
            img, meta = open_image(d / "p3.jpg")
            check("P3 profile named", "P3" in meta["color_space"], meta["color_space"])
            converted = to_srgb(img, meta["icc_profile"])
            check("P3 -> sRGB changes values", converted.getpixel((4, 4)) != img.getpixel((4, 4)),
                  f"{img.getpixel((4, 4))} -> {converted.getpixel((4, 4))}")
            save_image(img, d / "p3_keep.jpg", icc_profile=meta["icc_profile"], inputs=[d / "p3.jpg"])
            _, m2 = open_image(d / "p3_keep.jpg")
            check("keep policy round-trips P3", "P3" in m2["color_space"])
            save_image(converted, d / "p3_srgb.jpg", inputs=[d / "p3.jpg"])
            _, m3 = open_image(d / "p3_srgb.jpg")
            check("sRGB policy embeds sRGB", "sRGB" in m3["color_space"], m3["color_space"])
            check("common space: same -> keep", choose_output_profile([p3, p3])[0] == "keep")
            check("common space: mixed -> srgb", choose_output_profile([p3, None])[0] == "srgb")
            check("profile_space(P3) is RGB", profile_space(p3) == "RGB")
            white = srgb_color_in_profile((255, 255, 255), p3)
            orange = srgb_color_in_profile((230, 90, 40), p3)
            check("design colour into P3: white stays white", max(abs(a - b) for a, b in zip(white, (255, 255, 255))) <= 1, str(white))
            check("design colour into P3: orange changes", orange != (230, 90, 40), str(orange))
            cmyk_path = "/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc"
            if os.path.exists(cmyk_path):
                cmyk = Path(cmyk_path).read_bytes()
                check("non-RGB profile is never kept", choose_output_profile([cmyk])[0] == "srgb"
                      and profile_space(cmyk) == "CMYK")
        else:
            check("ICC tests skipped (no Display P3 profile on this system)", True)

        # 5. never overwrite an input; refuse existing output without overwrite
        try:
            save_image(Image.new("RGB", (4, 4)), d / "exif.jpg", inputs=[d / "exif.jpg"])
            check("refuse output == input", False)
        except ImageIOError:
            check("refuse output == input", True)
        try:
            check_output_path(d / "noexif.jpg", [], overwrite=False)
            check("refuse existing file", False)
        except ImageIOError as exc:
            check("refuse existing file, no flag suggested", "--overwrite" not in str(exc), str(exc))
        try:
            check_output_path(d / "noexif.jpg", [], overwrite=False, overwrite_flag="--overwrite")
        except ImageIOError as exc:
            check("refuse existing file, caller's flag named", "--overwrite" in str(exc), str(exc))

        # 6. HEIC explained, not a traceback
        (d / "x.heic").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
        if not HEIF_SUPPORTED:
            try:
                open_image(d / "x.heic")
                check("HEIC message", False)
            except ImageIOError as exc:
                check("HEIC message", "sips" in str(exc))
            (d / "y.jpg").write_bytes((d / "x.heic").read_bytes())
            try:
                open_image(d / "y.jpg")
                check("HEIC with wrong extension", False)
            except ImageIOError as exc:
                check("HEIC with wrong extension", "sips" in str(exc))

        # 7. fonts
        check("needs_cjk", needs_cjk("回顾卡 2026") and not needs_cjk("Shoot review 2026"))
        try:
            font, desc = load_font(40, text="外拍回顾")
            check("CJK font found", desc in CJK_FONTS or desc in CJK_BOLD_FONTS, desc)
        except ImageIOError as exc:
            check("CJK font found (none installed: clear error)", "Chinese" in str(exc), str(exc))
        font, desc = load_font(30, text="Shoot review")
        check("sized Latin font", getattr(font, "size", 30) == 30, desc)
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        size = fit_size(lambda s: text_width(draw, "f/2.8  1/250 s  ISO 400", load_font(s, text="f/2.8")[0]) <= 300, 8, 200)
        check("fit_size finds a size that fits", size is not None and 8 <= size < 200, str(size))

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared image I/O for the photo skills.")
    parser.add_argument("--selftest", action="store_true", help="run the built-in checks and exit")
    sub = parser.add_subparsers(dest="command")
    p_info = sub.add_parser("info", help="print orientation, colour space and EXIF as JSON")
    p_info.add_argument("images", nargs="+")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.command == "info":
        status = 0
        for path in args.images:
            try:
                print(json.dumps(info(path), ensure_ascii=False, indent=2, default=str))
            except ImageIOError as exc:
                print(f"error: {exc}", file=sys.stderr)
                status = 1
        return status
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
