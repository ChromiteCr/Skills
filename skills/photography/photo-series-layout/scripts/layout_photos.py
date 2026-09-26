#!/usr/bin/env python3
"""Render 3–9 photographs into a deterministic one-page layout.

Reading and writing go through the shared image_io.py next to this file:
photos are turned upright by their EXIF orientation, HEIC gets a conversion
command instead of a traceback, transparent areas take the background colour,
and the page is written in one colour space:

- every photo has the same RGB profile (for example all Display P3 from one
  iPhone): the page stays in that profile and embeds it;
- profiles differ, or one is CMYK or grey: every photo is converted to sRGB
  first and sRGB is embedded. Untagged photos count as sRGB;
- PDF output is always converted to sRGB, because Pillow's PDF writer stores
  pixels as DeviceRGB without a profile and viewers read that as sRGB.

auto layout: for every column count c = 1..N with r = ceil(N / c) rows, keep
the grids with the fewest empty cells (a single strip always has none, so auto
never leaves an empty cell), then pick the one whose page shape at the nominal
cell size is closest to the target shape: --canvas-width : --canvas-height when
given, otherwise one cell's shape (--cell-width : --cell-height, 4:3 by default).
Grids are reported as "C columns x R rows".

  python3 layout_photos.py --output series.png photo1.jpg photo2.jpg photo3.jpg
  python3 layout_photos.py --selftest
"""

from __future__ import annotations

import argparse
import contextlib
import io
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import image_io  # noqa: E402  (shared copy; also checks that Pillow is installed)
except ModuleNotFoundError as exc:  # pragma: no cover - only when the file was not copied along
    if exc.name == "image_io":
        raise SystemExit("error: image_io.py is missing; it must sit next to layout_photos.py in scripts/") from exc
    raise

from PIL import Image, ImageColor, ImageOps  # noqa: E402

SUPPORTED_OUTPUTS = {".png", ".jpg", ".jpeg", ".pdf"}


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {value!r}") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {value!r}") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def parse_color(value: str) -> tuple[int, int, int]:
    try:
        color = ImageColor.getrgb(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid color: {value}") from exc
    if len(color) != 3:
        raise argparse.ArgumentTypeError("background color must not include transparency")
    return color


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Render 3–9 photographs into a deterministic one-page layout (PNG, JPEG or one-page PDF).",
        epilog="Grids are reported as 'C columns x R rows'. Run with --selftest to check the renderer.",
    )
    command.add_argument("images", nargs="+", type=Path, help="3–9 input image paths in display order")
    command.add_argument("--output", required=True, type=Path, help="output .png, .jpg/.jpeg, or .pdf")
    command.add_argument(
        "--layout",
        choices=("auto", "grid", "horizontal", "vertical"),
        default="auto",
        help="auto: grid without empty cells closest to the target shape; grid: roughly square contact sheet "
        "(columns = ceil(sqrt(N)), may leave empty cells); horizontal: 1 row; vertical: 1 column",
    )
    command.add_argument("--fit", choices=("contain", "cover"), default="contain")
    command.add_argument("--canvas-width", type=positive_int, help="fixed output width in pixels")
    command.add_argument("--canvas-height", type=positive_int, help="fixed output height in pixels")
    command.add_argument("--cell-width", type=positive_int, default=1200)
    command.add_argument("--cell-height", type=positive_int, default=900)
    command.add_argument("--columns", type=positive_int, help="column count for an explicit grid (may leave empty cells)")
    command.add_argument("--margin", type=nonnegative_int, default=72)
    command.add_argument("--gutter", type=nonnegative_int, default=28)
    command.add_argument("--background", type=parse_color, default=parse_color("#ffffff"), help="canvas colour (sRGB)")
    command.add_argument("--quality", type=int, default=92, help="JPEG quality from 1 to 100 (also used inside a PDF)")
    command.add_argument("--dpi", type=positive_int, default=300, help="output DPI metadata (sets the PDF page size)")
    command.add_argument("--overwrite", action="store_true", help="replace an existing output file (never an input photo)")
    command.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="allow the same photo more than once; only after the user confirmed the repetition",
    )
    command.add_argument("--selftest", action="store_true", help="run the built-in checks and exit")
    return command


# ---------------------------------------------------------------- grid


def grid_ratio(rows: int, columns: int, cell_width: int, cell_height: int, margin: int, gutter: int) -> float:
    """Page width / height of a rows x columns grid at the nominal cell size."""
    width = 2 * margin + columns * cell_width + (columns - 1) * gutter
    height = 2 * margin + rows * cell_height + (rows - 1) * gutter
    return width / height


def grid_candidates(count: int) -> list[tuple[int, int, int]]:
    """(rows, columns, empty cells) for every column count, with no empty row."""
    out = []
    for columns in range(1, count + 1):
        rows = math.ceil(count / columns)
        out.append((rows, columns, rows * columns - count))
    return out


def auto_grid(count: int, target_ratio: float, cell_width: int = 1200, cell_height: int = 900,
              margin: int = 72, gutter: int = 28) -> tuple[int, int]:
    """Fewest empty cells first, then the page shape closest to target_ratio (ties: fewer rows)."""
    def key(candidate: tuple[int, int, int]) -> tuple[int, float, int]:
        rows, columns, empty = candidate
        error = abs(math.log(grid_ratio(rows, columns, cell_width, cell_height, margin, gutter) / target_ratio))
        return empty, round(error, 9), rows

    rows, columns, _ = min(grid_candidates(count), key=key)
    return rows, columns


def grid_label(rows: int, columns: int) -> str:
    return f"{columns} column{'s' if columns != 1 else ''} x {rows} row{'s' if rows != 1 else ''}"


def target_ratio(args: argparse.Namespace) -> float:
    if args.canvas_width and args.canvas_height:
        return args.canvas_width / args.canvas_height
    return args.cell_width / args.cell_height


def grid_shape(args: argparse.Namespace, count: int) -> tuple[int, int]:
    if args.layout == "horizontal":
        return 1, count
    if args.layout == "vertical":
        return count, 1
    if args.columns:
        columns = args.columns
        return math.ceil(count / columns), columns
    if args.layout == "grid":
        columns = math.ceil(math.sqrt(count))
        return math.ceil(count / columns), columns
    return auto_grid(count, target_ratio(args), args.cell_width, args.cell_height, args.margin, args.gutter)


def strip_note(args: argparse.Namespace, count: int, rows: int, columns: int) -> str | None:
    """When auto had to fall back to a single strip (N = 5 or 7), say how to get a compact grid instead."""
    if args.layout != "auto" or args.columns or count < 5 or not (rows == 1 or columns == 1):
        return None
    if any(e == 0 and r > 1 and c > 1 for r, c, e in grid_candidates(count)):
        return None
    target = target_ratio(args)
    compact = [(r, c, e) for r, c, e in grid_candidates(count) if r > 1 and c > 1]
    if not compact:
        return None
    r, c, e = min(compact, key=lambda x: (x[2], abs(math.log(grid_ratio(x[0], x[1], args.cell_width, args.cell_height, args.margin, args.gutter) / target))))
    return (
        f"note: {count} photos fit without an empty cell only as a single strip. For a compact grid pass "
        f"--columns {c} ({grid_label(r, c)}, {e} empty cell{'s' if e != 1 else ''} at the end); "
        "empty cells need the user's approval."
    )


# ---------------------------------------------------------------- checks


def validate(args: argparse.Namespace) -> None:
    args.images = [path.expanduser() for path in args.images]
    args.output = args.output.expanduser()
    count = len(args.images)
    if not 3 <= count <= 9:
        raise ValueError(f"expected 3–9 images, received {count}")
    resolved = [path.resolve() for path in args.images]
    repeated = sorted({str(path) for path, full in zip(args.images, resolved) if resolved.count(full) > 1})
    if repeated and not args.allow_duplicates:
        raise ValueError(
            "the same photo is listed more than once: " + ", ".join(repeated)
            + ". If the user confirmed the repetition, pass --allow-duplicates"
        )
    missing = [str(path) for path in args.images if not path.is_file()]
    if missing:
        raise ValueError("missing input image(s): " + ", ".join(missing))
    suffix = args.output.suffix.lower()
    if suffix not in SUPPORTED_OUTPUTS:
        raise ValueError("output extension must be .png, .jpg/.jpeg, or .pdf")
    try:
        image_io.check_output_path(args.output, args.images, overwrite=args.overwrite, overwrite_flag="--overwrite")
    except image_io.ImageIOError as exc:
        raise ValueError(str(exc)) from exc
    if (args.canvas_width is None) != (args.canvas_height is None):
        raise ValueError("--canvas-width and --canvas-height must be supplied together")
    if not 1 <= args.quality <= 100:
        raise ValueError("--quality must be from 1 to 100")
    if args.columns and args.layout in {"horizontal", "vertical"}:
        raise ValueError("--columns cannot be combined with horizontal or vertical layout")


def probe(paths: Iterable[Path]) -> list[bytes | None]:
    """ICC profile of each input, read from the file header. Unreadable files and HEIC stop here."""
    iccs: list[bytes | None] = []
    for path in paths:
        try:
            image_io.oriented_size(path)
            with Image.open(path) as source:
                iccs.append(source.info.get("icc_profile") or None)
        except image_io.ImageIOError as exc:
            raise ValueError(str(exc)) from exc
        except OSError as exc:
            raise ValueError(f"{path.name}: cannot read image ({exc})") from exc
    return iccs


def colour_plan(iccs: list[bytes | None], suffix: str) -> tuple[str, bytes | None, str]:
    """(policy, profile of the page, one-line description for the report)."""
    names = sorted({image_io.profile_name(icc) for icc in iccs})
    if suffix == ".pdf":
        if any(iccs):
            return "srgb", None, f"converted to sRGB for PDF (inputs: {', '.join(names)})"
        return "keep", None, "sRGB (untagged inputs; PDF carries no profile)"
    policy, icc = image_io.choose_output_profile(iccs)
    if policy == "keep":
        if icc is None:
            return "keep", None, "sRGB embedded (untagged inputs)"
        return "keep", icc, f"kept {image_io.profile_name(icc)} (all inputs) and embedded it"
    return "srgb", icc, f"converted to sRGB and embedded it (inputs: {', '.join(names)})"


# ---------------------------------------------------------------- rendering


def dimensions(args: argparse.Namespace, rows: int, columns: int) -> tuple[int, int, int, int]:
    if args.canvas_width and args.canvas_height:
        available_width = args.canvas_width - 2 * args.margin - (columns - 1) * args.gutter
        available_height = args.canvas_height - 2 * args.margin - (rows - 1) * args.gutter
        if available_width < columns or available_height < rows:
            raise ValueError("margin and gutter leave no usable cell area")
        cell_width = available_width // columns
        cell_height = available_height // rows
        return args.canvas_width, args.canvas_height, cell_width, cell_height
    width = 2 * args.margin + columns * args.cell_width + (columns - 1) * args.gutter
    height = 2 * args.margin + rows * args.cell_height + (rows - 1) * args.gutter
    return width, height, args.cell_width, args.cell_height


def fitted(image: Image.Image, size: tuple[int, int], mode: str, background: tuple[int, int, int]) -> Image.Image:
    if mode == "cover":
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    result = Image.new("RGB", size, background)
    contained = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    position = ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2)
    result.paste(contained, position)
    contained.close()
    return result


def page_pixels(path: Path, policy: str, background: tuple[int, int, int]) -> Image.Image:
    """The photo upright, as RGB in the page's colour space, transparency on the background colour."""
    try:
        image, meta = image_io.open_image(path)
    except image_io.ImageIOError as exc:
        raise ValueError(str(exc)) from exc
    icc = meta["icc_profile"]
    # the background is an sRGB colour; express it in the photo's own profile before compositing
    local_background = image_io.srgb_color_in_profile(background, icc)
    try:
        if policy == "keep":
            return image_io.to_rgb(image, local_background)
        if image_io.profile_space(icc) == "GRAY" and image.mode not in ("L", "RGB"):
            image = image_io.to_rgb(image, local_background).convert("L")
        return image_io.to_srgb(image, icc, background=local_background)
    except image_io.ImageIOError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def save(canvas: Image.Image, args: argparse.Namespace, icc: bytes | None) -> None:
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    options: dict[str, object] = {"dpi": (args.dpi, args.dpi)}
    if suffix in {".jpg", ".jpeg"}:
        options.update({"quality": args.quality, "optimize": True, "subsampling": 0,
                        "icc_profile": icc or image_io.srgb_icc_bytes()})
    elif suffix == ".png":
        options["icc_profile"] = icc or image_io.srgb_icc_bytes()
    else:  # PDF: Pillow stores DeviceRGB and cannot embed a profile; pixels are already sRGB
        options.update({"quality": args.quality, "subsampling": 0})
    canvas.save(output, **options)


def render(args: argparse.Namespace) -> str:
    validate(args)
    count = len(args.images)
    rows, columns = grid_shape(args, count)
    canvas_width, canvas_height, cell_width, cell_height = dimensions(args, rows, columns)
    iccs = probe(args.images)
    policy, page_icc, colour_note = colour_plan(iccs, args.output.suffix.lower())
    page_background = image_io.srgb_color_in_profile(args.background, page_icc) if policy == "keep" else args.background
    canvas = Image.new("RGB", (canvas_width, canvas_height), page_background)
    try:
        for index, path in enumerate(args.images):
            row, column = divmod(index, columns)
            x = args.margin + column * (cell_width + args.gutter)
            y = args.margin + row * (cell_height + args.gutter)
            image = page_pixels(path, policy, args.background)
            tile = fitted(image, (cell_width, cell_height), args.fit, page_background)
            canvas.paste(tile, (x, y))
            tile.close()
            image.close()
        save(canvas, args, page_icc)
    finally:
        canvas.close()
    empty = rows * columns - count
    return (
        f"wrote {args.output} | {canvas_width}x{canvas_height}px | {grid_label(rows, columns)} | "
        f"fit={args.fit} | images={count} | empty cells={empty} | colour: {colour_note}"
    )


def main(argv: list[str] | None = None) -> int:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--selftest", action="store_true")
    known, _ = pre.parse_known_args(argv)
    if known.selftest:
        return selftest()
    args = parser().parse_args(argv)
    try:
        report = render(args)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(report)
    rows, columns = grid_shape(args, len(args.images))
    note = strip_note(args, len(args.images), rows, columns)
    if note:
        print(note, file=sys.stderr)
    empty = rows * columns - len(args.images)
    if empty:
        print(f"note: {empty} empty cell{'s' if empty != 1 else ''} at the end of the grid; "
              "confirm with the user that the gap is intended.", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- self-test


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def _close(a, b, tol: int = 4) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _pdf_image(path: Path) -> Image.Image:
    data = path.read_bytes()
    match = re.search(rb"/DCTDecode.*?stream\r?\n", data, re.S)
    start = match.end()
    return Image.open(io.BytesIO(data[start:data.index(b"endstream", start)]))


def selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    grids = {n: auto_grid(n, 1200 / 900) for n in range(3, 10)}
    check("auto without canvas keeps 3/4/6/9 as before", grids[3] == (1, 3) and grids[4] == (2, 2)
          and grids[6] == (2, 3) and grids[9] == (3, 3), str(grids))
    check("auto: 8 photos -> 4 columns x 2 rows, no empty cell", grids[8] == (2, 4), str(grids[8]))
    check("auto never leaves an empty cell (3-9, several canvases)", all(
        r * c == n for ratio in (4 / 3, 3000 / 1000, 1000 / 3000, 1080 / 1350, 1.0)
        for n in range(3, 10) for r, c in [auto_grid(n, ratio)]))
    check("auto: 8 photos on 4000x1500 -> 4 columns x 2 rows", auto_grid(8, 4000 / 1500) == (2, 4))
    check("auto: 5 photos on 3000x1000 -> 5 columns x 1 row", auto_grid(5, 3000 / 1000) == (1, 5))
    check("auto: 6 photos on portrait 1080x1350 -> 2 columns x 3 rows", auto_grid(6, 1080 / 1350) == (3, 2))

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for i in range(1, 10):
            Image.new("RGB", (400, 300), (20 * i, 90, 160)).save(d / f"s{i}.jpg", quality=95)
        photos = [str(d / f"s{i}.jpg") for i in range(1, 10)]

        code, out, err = _run(["--output", str(d / "eight.png"), *photos[:8]])
        check("8 photos auto: 4 columns x 2 rows, empty cells=0", code == 0 and "4 columns x 2 rows" in out
              and "empty cells=0" in out, out + err)

        code, out, err = _run(["--output", str(d / "five.png"), *photos[:5]])
        check("5 photos auto: strip plus a --columns hint", code == 0 and "5 columns x 1 row |" in out
              and "--columns 3" in err, out + err)
        code, out, err = _run(["--output", str(d / "three.png"), *photos[:3]])
        check("3 photos auto: 1x3 strip, no hint", code == 0 and "3 columns x 1 row |" in out and "note:" not in err, out + err)

        code, out, err = _run(["--output", str(d / "dup.png"), photos[0], photos[0], photos[1]])
        check("duplicate path refused without the flag", code == 2 and "--allow-duplicates" in err
              and not (d / "dup.png").exists(), err.strip())
        code, out, err = _run(["--output", str(d / "dup.png"), "--allow-duplicates", photos[0], photos[0], photos[1]])
        check("duplicate path allowed with --allow-duplicates", code == 0 and (d / "dup.png").exists(), err.strip())

        code, out, err = _run(["--output", str(d / "ten.png"), *photos, photos[0]])
        check("10 photos refused", code == 2 and "3–9" in err)

        code, out, err = _run(["--output", photos[2], "--overwrite", *photos[:3]])
        check("output that is an input photo refused, even with --overwrite", code == 2 and "input file" in err
              and Image.open(photos[2]).size == (400, 300), err.strip())
        code, out, err = _run(["--output", str(d / "eight.png"), *photos[:8]])
        check("existing output refused without --overwrite", code == 2 and "--overwrite" in err, err.strip())

        # orientation 6: stored 600x400, displayed 400x600; red block stored top-left -> displayed top-right
        phone = Image.new("RGB", (600, 400), (40, 120, 200))
        phone.paste((255, 0, 0), (0, 0, 150, 100))
        exif = Image.Exif()
        exif[0x0112] = 6
        phone.save(d / "phone.jpg", exif=exif.tobytes(), quality=95)
        rgba = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
        rgba.paste((220, 20, 20, 255), (100, 75, 300, 225))
        rgba.save(d / "alpha.png")
        code, out, err = _run(["--output", str(d / "mix.png"), "--layout", "horizontal", "--cell-width", "400",
                               "--cell-height", "600", "--margin", "0", "--gutter", "0", "--background", "#ff00ff",
                               str(d / "phone.jpg"), str(d / "alpha.png"), photos[0]])
        check("mixed render exits 0", code == 0, err.strip())
        if code == 0:
            page = Image.open(d / "mix.png").convert("RGB")
            check("orientation 6 photo upright (red top-right)", _close(page.getpixel((396, 3)), (255, 0, 0), 40)
                  and _close(page.getpixel((3, 596)), (40, 120, 200), 40), f"{page.getpixel((396, 3))} {page.getpixel((3, 596))}")
            check("transparent PNG area takes the background, not black",
                  _close(page.getpixel((400 + 200, 300 - 140)), (255, 0, 255)), str(page.getpixel((600, 160))))

        p3_path = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
        if p3_path.exists():
            p3 = p3_path.read_bytes()
            for i in (1, 2, 3):
                Image.new("RGB", (400, 300), (234, 51, 35)).save(d / f"p3_{i}.jpg", icc_profile=p3, quality=95)
            p3_photos = [str(d / f"p3_{i}.jpg") for i in (1, 2, 3)]
            code, out, err = _run(["--output", str(d / "p3.png"), *p3_photos])
            page = Image.open(d / "p3.png")
            check("all Display P3: page keeps and embeds P3", code == 0 and "P3" in image_io.profile_name(page.info.get("icc_profile"))
                  and _close(page.convert("RGB").getpixel((72 + 600, 72 + 450)), (234, 51, 35)), out + err)
            check("P3 page: white background stays white", _close(page.convert("RGB").getpixel((5, 5)), (255, 255, 255), 1))

            code, out, err = _run(["--output", str(d / "p3mix.jpg"), p3_photos[0], photos[0], photos[1]])
            page = Image.open(d / "p3mix.jpg")
            check("mixed P3 + untagged: converted to sRGB and embedded", code == 0 and "sRGB" in image_io.profile_name(page.info.get("icc_profile"))
                  and _close(page.convert("RGB").getpixel((72 + 600, 72 + 450)), (255, 0, 0), 6), f"{out}{err} {page.convert('RGB').getpixel((672, 522))}")

            code, out, err = _run(["--output", str(d / "p3.pdf"), *p3_photos])
            pix = _pdf_image(d / "p3.pdf").convert("RGB").getpixel((72 + 600, 72 + 450)) if code == 0 else None
            check("PDF: P3 converted to sRGB (PDF carries no profile)", code == 0 and pix is not None
                  and _close(pix, (255, 0, 0), 6) and "converted to sRGB for PDF" in out, f"{out}{err} {pix}")

        (d / "iphone.heic").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
        if not image_io.HEIF_SUPPORTED:
            code, out, err = _run(["--output", str(d / "heic.png"), str(d / "iphone.heic"), *photos[:2]])
            check("HEIC: sips hint, no traceback", code == 2 and "sips -s format jpeg" in err and "Traceback" not in err, err.strip())

        code, out, err = _run(["--help"])
        check("--help prints usage and exits 0", code == 0 and "usage" in out.lower() and "--allow-duplicates" in out)

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
