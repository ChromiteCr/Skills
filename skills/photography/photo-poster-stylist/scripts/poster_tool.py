#!/usr/bin/env python3
"""Render and validate restrained SVG posters using only Python's standard library."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
NUMBER_RE = re.compile(r"^-?(?:\d+(?:\.\d*)?|\.\d+)$")
GRAPHICS = {"rect", "circle", "ellipse", "polygon", "path"}
TEXT_ROLES = (("title", 0.060, "700"), ("subtitle", 0.026, "400"), ("credit", 0.026, "400"))


def die(message: str) -> None:
    raise ValueError(message)


def number(value, label: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        die(f"{label} must be a finite number")
    result = float(value)
    if minimum is not None and result < minimum:
        die(f"{label} must be >= {minimum}")
    return result


def fmt(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.4f}".rstrip("0").rstrip(".")


def color(value: str, palette: dict[str, str], label: str) -> str:
    resolved = palette.get(value, value)
    if not isinstance(resolved, str) or not HEX_RE.fullmatch(resolved):
        die(f"{label} must be a palette role or #RRGGBB color")
    if resolved.upper() not in {v.upper() for v in palette.values()}:
        die(f"{label} introduces a color outside the declared palette")
    return resolved.upper()


def attrs(items: dict[str, object]) -> str:
    return " ".join(f'{key}="{html.escape(str(value), quote=True)}"' for key, value in items.items())


def render(spec_path: Path, output_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        die("specification root must be an object")
    width = number(spec.get("width"), "width", 1)
    height = number(spec.get("height"), "height", 1)
    bleed = number(spec.get("bleed", 0), "bleed", 0)
    palette = spec.get("palette")
    if not isinstance(palette, dict) or set(palette) != {"background", "foreground", "accent"}:
        die("palette must contain exactly background, foreground, and accent")
    for role, value in palette.items():
        if not isinstance(value, str) or not HEX_RE.fullmatch(value):
            die(f"palette.{role} must be #RRGGBB")
    if len({v.upper() for v in palette.values()}) > 3:
        die("palette may contain no more than three colors")

    shapes = spec.get("shapes", [])
    if not isinstance(shapes, list) or len(shapes) > 24:
        die("shapes must be a list with at most 24 items")

    full_w, full_h = width + 2 * bleed, height + 2 * bleed
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="{SVG_NS}" width="{fmt(full_w)}" height="{fmt(full_h)}" '
        f'viewBox="{-bleed:g} {-bleed:g} {fmt(full_w)} {fmt(full_h)}" role="img">',
        "  <title>Minimal poster</title>",
        f'  <metadata data-trim-width="{fmt(width)}" data-trim-height="{fmt(height)}" data-bleed="{fmt(bleed)}" />',
        f'  <rect x="{-bleed:g}" y="{-bleed:g}" width="{fmt(full_w)}" height="{fmt(full_h)}" fill="{palette["background"].upper()}" data-role="background" />',
    ]

    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict):
            die(f"shapes[{index}] must be an object")
        kind = shape.get("type")
        if kind not in GRAPHICS:
            die(f"shapes[{index}].type is unsupported")
        fill = color(shape.get("fill", "foreground"), palette, f"shapes[{index}].fill")
        data: dict[str, object] = {"fill": fill, "data-role": "graphic"}
        if kind == "rect":
            for key in ("x", "y"):
                data[key] = fmt(number(shape.get(key), f"shapes[{index}].{key}"))
            for key in ("width", "height"):
                data[key] = fmt(number(shape.get(key), f"shapes[{index}].{key}", 0))
        elif kind == "circle":
            for key in ("cx", "cy"):
                data[key] = fmt(number(shape.get(key), f"shapes[{index}].{key}"))
            data["r"] = fmt(number(shape.get("r"), f"shapes[{index}].r", 0))
        elif kind == "ellipse":
            for key in ("cx", "cy"):
                data[key] = fmt(number(shape.get(key), f"shapes[{index}].{key}"))
            for key in ("rx", "ry"):
                data[key] = fmt(number(shape.get(key), f"shapes[{index}].{key}", 0))
        elif kind == "polygon":
            points = shape.get("points")
            if not isinstance(points, list) or len(points) < 3:
                die(f"shapes[{index}].points must contain at least three [x,y] pairs")
            pairs = []
            for point_index, point in enumerate(points):
                if not isinstance(point, list) or len(point) != 2:
                    die(f"shapes[{index}].points[{point_index}] must be [x,y]")
                pairs.append(",".join(fmt(number(v, "polygon coordinate")) for v in point))
            data["points"] = " ".join(pairs)
        else:
            path_data = shape.get("d")
            if not isinstance(path_data, str) or not path_data.strip() or any(c in path_data for c in "<>\""):
                die(f"shapes[{index}].d must be a non-empty safe SVG path string")
            data["d"] = path_data.strip()
        lines.append(f"  <{kind} {attrs(data)} />")

    margin = 0.075 * min(width, height)
    y_positions = (height - margin * 2.4, height - margin * 1.45, height - margin * 0.65)
    foreground = palette["foreground"].upper()
    for (role, scale, weight), y in zip(TEXT_ROLES, y_positions):
        text = spec.get(role, "")
        if text is None:
            text = ""
        if not isinstance(text, str):
            die(f"{role} must be text")
        if text:
            size = max(10.0, min(width, height) * scale)
            lines.append(
                f'  <text x="{fmt(margin)}" y="{fmt(y)}" fill="{foreground}" '
                f'font-family="sans-serif" font-size="{fmt(size)}" font-weight="{weight}" '
                f'data-role="{role}">{html.escape(text)}</text>'
            )
    lines.append("</svg>")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_num(value: str | None, label: str) -> float:
    if value is None or not NUMBER_RE.fullmatch(value.strip()):
        die(f"{label} must be a plain numeric SVG value")
    return float(value)


def rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))


def luminance(hex_color: str) -> float:
    values = []
    for channel in rgb(hex_color):
        x = channel / 255
        values.append(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def validate(svg_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.parse(svg_path).getroot()
    except (ET.ParseError, OSError) as exc:
        return [f"cannot parse SVG: {exc}"]
    if local_name(root.tag) != "svg":
        return ["root element is not svg"]
    try:
        width = parse_num(root.get("width"), "svg width")
        height = parse_num(root.get("height"), "svg height")
    except ValueError as exc:
        return [str(exc)]
    if width <= 0 or height <= 0:
        errors.append("canvas dimensions must be positive")

    colors: set[str] = set()
    graphic_count = 0
    background = None
    texts: list[ET.Element] = []
    for element in root.iter():
        tag = local_name(element.tag)
        fill = element.get("fill")
        if fill and fill.lower() != "none":
            if HEX_RE.fullmatch(fill):
                colors.add(fill.upper())
            else:
                errors.append(f"{tag} uses unsupported fill {fill!r}; use #RRGGBB")
        role = element.get("data-role")
        if role == "background" and fill and HEX_RE.fullmatch(fill):
            background = fill.upper()
        elif tag in GRAPHICS and role != "background":
            graphic_count += 1
        if tag == "text":
            texts.append(element)

        try:
            if tag == "rect":
                x, y = parse_num(element.get("x", "0"), "rect x"), parse_num(element.get("y", "0"), "rect y")
                w, h = parse_num(element.get("width"), "rect width"), parse_num(element.get("height"), "rect height")
                if role != "background" and (x < 0 or y < 0 or x + w > width or y + h > height):
                    errors.append("rect extends outside the canvas")
            elif tag == "circle":
                cx, cy, r = (parse_num(element.get(k), f"circle {k}") for k in ("cx", "cy", "r"))
                if cx - r < 0 or cy - r < 0 or cx + r > width or cy + r > height:
                    errors.append("circle extends outside the canvas")
            elif tag == "ellipse":
                cx, cy, rx, ry = (parse_num(element.get(k), f"ellipse {k}") for k in ("cx", "cy", "rx", "ry"))
                if cx - rx < 0 or cy - ry < 0 or cx + rx > width or cy + ry > height:
                    errors.append("ellipse extends outside the canvas")
            elif tag == "polygon":
                coordinates = [float(v) for v in re.findall(r"-?(?:\d+(?:\.\d*)?|\.\d+)", element.get("points", ""))]
                if len(coordinates) < 6 or len(coordinates) % 2:
                    errors.append("polygon has invalid points")
                elif any(x < 0 or x > width for x in coordinates[0::2]) or any(y < 0 or y > height for y in coordinates[1::2]):
                    errors.append("polygon extends outside the canvas")
        except ValueError as exc:
            errors.append(str(exc))

    if len(colors) > 3:
        errors.append(f"poster uses {len(colors)} visible colors; maximum is 3")
    if graphic_count > 24:
        errors.append(f"poster uses {graphic_count} graphic elements; maximum is 24")
    if background is None:
        errors.append("missing a #RRGGBB background element with data-role='background'")

    sizes: set[float] = set()
    weights: set[str] = set()
    for element in texts:
        try:
            size = parse_num(element.get("font-size"), "text font-size")
            sizes.add(size)
        except ValueError as exc:
            errors.append(str(exc))
            size = 0
        weights.add(element.get("font-weight", "400"))
        fill = element.get("fill", "")
        if background and HEX_RE.fullmatch(fill):
            required = 3.0 if size >= 0.04 * min(width, height) else 4.5
            ratio = contrast(fill.upper(), background)
            if ratio + 1e-9 < required:
                errors.append(f"text contrast {ratio:.2f}:1 is below {required:.1f}:1")
    if len(sizes) > 2:
        errors.append(f"poster uses {len(sizes)} text sizes; maximum is 2")
    if len(weights) > 2:
        errors.append(f"poster uses {len(weights)} text weights; maximum is 2")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    render_parser = subparsers.add_parser("render", help="render JSON specification to SVG")
    render_parser.add_argument("spec", type=Path)
    render_parser.add_argument("output", type=Path)
    validate_parser = subparsers.add_parser("validate", help="validate an SVG poster")
    validate_parser.add_argument("svg", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "render":
            render(args.spec, args.output)
            print(f"rendered {args.output}")
        else:
            errors = validate(args.svg)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("PASS: SVG meets deterministic poster checks")
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
