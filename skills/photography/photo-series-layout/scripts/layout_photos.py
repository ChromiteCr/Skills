#!/usr/bin/env python3
"""Render 3–9 photographs into a deterministic one-page layout."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys
from typing import Iterable

try:
    from PIL import Image, ImageColor, ImageOps, UnidentifiedImageError
except ImportError as exc:  # pragma: no cover - exercised when dependency is absent
    raise SystemExit("Pillow is required. Install it with: python -m pip install Pillow") from exc

SUPPORTED_OUTPUTS = {".png", ".jpg", ".jpeg", ".pdf"}


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
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
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("images", nargs="+", type=Path, help="3–9 input image paths in display order")
    command.add_argument("--output", required=True, type=Path, help="output .png, .jpg/.jpeg, or .pdf")
    command.add_argument("--layout", choices=("auto", "grid", "horizontal", "vertical"), default="auto")
    command.add_argument("--fit", choices=("contain", "cover"), default="contain")
    command.add_argument("--canvas-width", type=positive_int, help="fixed output width in pixels")
    command.add_argument("--canvas-height", type=positive_int, help="fixed output height in pixels")
    command.add_argument("--cell-width", type=positive_int, default=1200)
    command.add_argument("--cell-height", type=positive_int, default=900)
    command.add_argument("--columns", type=positive_int, help="column count for grid layout")
    command.add_argument("--margin", type=nonnegative_int, default=72)
    command.add_argument("--gutter", type=nonnegative_int, default=28)
    command.add_argument("--background", type=parse_color, default=parse_color("#ffffff"))
    command.add_argument("--quality", type=int, default=92, help="JPEG quality from 1 to 100")
    command.add_argument("--dpi", type=positive_int, default=300, help="output DPI metadata")
    command.add_argument("--overwrite", action="store_true")
    return command


def auto_grid(count: int, target_ratio: float) -> tuple[int, int]:
    if count == 3:
        return (1, 3) if target_ratio >= 1 else (3, 1)
    if count == 4:
        return 2, 2
    if count in {5, 6}:
        return (2, 3) if target_ratio >= 1 else (3, 2)
    return 3, 3


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
    target = 1.0
    if args.canvas_width and args.canvas_height:
        target = args.canvas_width / args.canvas_height
    return auto_grid(count, target)


def validate(args: argparse.Namespace) -> None:
    args.images = [path.expanduser() for path in args.images]
    args.output = args.output.expanduser()
    count = len(args.images)
    if not 3 <= count <= 9:
        raise ValueError(f"expected 3–9 images, received {count}")
    resolved = [path.resolve() for path in args.images]
    if len(set(resolved)) != count:
        raise ValueError("duplicate input paths are not allowed")
    missing = [str(path) for path in args.images if not path.is_file()]
    if missing:
        raise ValueError("missing input image(s): " + ", ".join(missing))
    suffix = args.output.suffix.lower()
    if suffix not in SUPPORTED_OUTPUTS:
        raise ValueError("output extension must be .png, .jpg/.jpeg, or .pdf")
    if args.output.exists() and not args.overwrite:
        raise ValueError(f"output exists; pass --overwrite to replace it: {args.output}")
    if (args.canvas_width is None) != (args.canvas_height is None):
        raise ValueError("--canvas-width and --canvas-height must be supplied together")
    if not 1 <= args.quality <= 100:
        raise ValueError("--quality must be from 1 to 100")
    if args.columns and args.layout in {"horizontal", "vertical"}:
        raise ValueError("--columns cannot be combined with horizontal or vertical layout")


def load_images(paths: Iterable[Path]) -> list[Image.Image]:
    loaded: list[Image.Image] = []
    try:
        for path in paths:
            with Image.open(path) as source:
                corrected = ImageOps.exif_transpose(source)
                loaded.append(corrected.convert("RGB"))
    except (OSError, UnidentifiedImageError) as exc:
        for image in loaded:
            image.close()
        raise ValueError(f"could not decode input image: {exc}") from exc
    return loaded


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


def save(canvas: Image.Image, args: argparse.Namespace) -> None:
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    options = {"dpi": (args.dpi, args.dpi)}
    if suffix in {".jpg", ".jpeg"}:
        options.update({"quality": args.quality, "optimize": True})
    canvas.save(output, **options)


def main() -> int:
    args = parser().parse_args()
    try:
        validate(args)
        rows, columns = grid_shape(args, len(args.images))
        canvas_width, canvas_height, cell_width, cell_height = dimensions(args, rows, columns)
        images = load_images(args.images)
        canvas = Image.new("RGB", (canvas_width, canvas_height), args.background)
        try:
            for index, image in enumerate(images):
                row, column = divmod(index, columns)
                x = args.margin + column * (cell_width + args.gutter)
                y = args.margin + row * (cell_height + args.gutter)
                tile = fitted(image, (cell_width, cell_height), args.fit, args.background)
                canvas.paste(tile, (x, y))
                tile.close()
            save(canvas, args)
        finally:
            canvas.close()
            for image in images:
                image.close()
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"wrote {args.output} | {canvas_width}x{canvas_height}px | "
        f"{rows}x{columns} | fit={args.fit} | images={len(args.images)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
