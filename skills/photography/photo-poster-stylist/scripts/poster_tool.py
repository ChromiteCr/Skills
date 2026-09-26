#!/usr/bin/env python3
"""Render and validate restrained SVG posters using only Python's standard library.

  python3 poster_tool.py render poster.json poster.svg
  python3 poster_tool.py validate poster.svg
  python3 poster_tool.py --selftest

validate checks, in the SVG's viewBox coordinates (so a bleed offset counts):
  - every rect, circle, ellipse, polygon and path lies on the canvas, bleed included;
    paths by their exact outline (M/L/H/V/C/S/Q/T/A/Z, absolute and relative),
    curves by their extrema rather than their control points;
  - text: the anchor lies on the canvas and an estimated box stays inside the trim.
    The box is a rough estimate: full-width (CJK) characters 1 em, spaces 0.3 em,
    other characters 0.6 em; 0.8 em above and 0.2 em below the baseline;
  - colours, element count, text sizes and weights, and text contrast.
Warnings (exit 0): text reaching into the 5% side margins of the safe area, and,
with bleed, a shape that crosses the trim edge but stops short of the bleed edge.
transform, style, stroke and elements other than the ones above are rejected,
because these checks cannot follow them.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import io
import json
import math
import re
import sys
import tempfile
import unicodedata
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


# ---------------------------------------------------------------- geometry

PATH_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
SVG_NUMBER_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
SEPARATORS = " \t\r\n\f,"
EPS = 1e-6
SUPPORTED_ELEMENTS = {"title", "desc", "metadata", "g", "text"} | GRAPHICS
SAFE_AREA = 0.05  # references/layout-rules.md: live text at least 5% of the shorter trim edge from the trim


def parse_numbers(text: str | None, label: str) -> list[float]:
    """A list of SVG numbers separated by spaces and/or commas ("10,20 -5.5e1"). Anything else is an error."""
    values: list[float] = []
    i, n = 0, len(text or "")
    while True:
        while i < n and text[i] in SEPARATORS:
            i += 1
        if i >= n:
            return values
        match = SVG_NUMBER_RE.match(text, i)
        if not match:
            die(f"{label} is not a list of numbers near {text[i:i + 12]!r}")
        values.append(float(match.group()))
        i = match.end()


def parse_path(d: str) -> list[tuple[str, list[float]]]:
    """Split SVG path data into (command, arguments), one entry per segment.

    Implicit repeats are expanded (pairs after M become L), and arc flags may be
    packed without separators ("a5 5 0 1010 10"). Raises ValueError on malformed data.
    """
    segments: list[tuple[str, list[float]]] = []
    i, n = 0, len(d)
    command: str | None = None

    def skip() -> None:
        nonlocal i
        while i < n and d[i] in SEPARATORS:
            i += 1

    def number() -> float:
        nonlocal i
        skip()
        match = SVG_NUMBER_RE.match(d, i)
        if not match:
            die(f"path data is malformed near {d[i:i + 12]!r} (position {i})")
        i = match.end()
        return float(match.group())

    def flag() -> float:
        nonlocal i
        skip()
        if i < n and d[i] in "01":
            i += 1
            return float(d[i - 1])
        die(f"path arc flag must be 0 or 1 near {d[i:i + 12]!r} (position {i})")

    while True:
        skip()
        if i >= n:
            break
        char = d[i]
        if char.isalpha():
            if char.upper() not in PATH_ARITY:
                die(f"path data has an unknown command {char!r} (position {i})")
            command = char
            i += 1
            if command in "Zz":
                segments.append((command, []))
                continue
        elif command is None:
            die("path data must start with a moveto command (M or m)")
        elif command in "Zz":
            die(f"path data has numbers after Z (position {i})")
        upper = command.upper()
        args = [flag() if upper == "A" and k in (3, 4) else number() for k in range(PATH_ARITY[upper])]
        segments.append((command, args))
        if command in "Mm":
            command = "L" if command == "M" else "l"
    if not segments or segments[0][0] not in "Mm":
        die("path data must start with a moveto command (M or m)")
    return segments


def _roots(a: float, b: float, c: float) -> list[float]:
    """Real roots of a*t^2 + b*t + c = 0 (linear when a is 0)."""
    if abs(a) < 1e-12:
        return [] if abs(b) < 1e-12 else [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    root = math.sqrt(disc)
    return [(-b + root) / (2 * a), (-b - root) / (2 * a)]


def _cubic_points(p0, p1, p2, p3) -> list[tuple[float, float]]:
    """End points plus the axis extrema of a cubic Bezier curve (not its control points)."""
    ts = [0.0, 1.0]
    for k in (0, 1):
        a = -p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]
        b = 2 * (p0[k] - 2 * p1[k] + p2[k])
        c = p1[k] - p0[k]
        ts += [t for t in _roots(a, b, c) if 0 < t < 1]
    return [tuple((1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * p1[k] + 3 * (1 - t) * t ** 2 * p2[k] + t ** 3 * p3[k]
                  for k in (0, 1)) for t in ts]


def _quad_points(p0, p1, p2) -> list[tuple[float, float]]:
    ts = [0.0, 1.0]
    for k in (0, 1):
        denominator = p0[k] - 2 * p1[k] + p2[k]
        if abs(denominator) > 1e-12 and 0 < (p0[k] - p1[k]) / denominator < 1:
            ts.append((p0[k] - p1[k]) / denominator)
    return [tuple((1 - t) ** 2 * p0[k] + 2 * (1 - t) * t * p1[k] + t ** 2 * p2[k] for k in (0, 1)) for t in ts]


def _arc_points(p0, rx: float, ry: float, angle: float, large: bool, sweep: bool, p1) -> list[tuple[float, float]]:
    """End points plus the axis extrema of an SVG elliptical arc (SVG 1.1, implementation notes F.6.5)."""
    (x1, y1), (x2, y2) = p0, p1
    rx, ry = abs(rx), abs(ry)
    if (x1, y1) == (x2, y2):
        return [p0]
    if rx == 0 or ry == 0:
        return [p0, p1]
    phi = math.radians(angle % 360)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    hx, hy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cos_p * hx + sin_p * hy, -sin_p * hx + cos_p * hy
    scale = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    numerator = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, numerator / denominator)) if denominator else 0.0
    if large == sweep:
        coef = -coef
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2
    theta1 = math.atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
    delta = math.atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx) - theta1
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    points = [p0, p1]
    for base in (math.atan2(-ry * sin_p, rx * cos_p), math.atan2(ry * cos_p, rx * sin_p)):
        for theta in (base, base + math.pi):
            travelled = (theta - theta1) % (2 * math.pi) if delta > 0 else (theta1 - theta) % (2 * math.pi)
            if travelled <= abs(delta):
                points.append((cx + rx * cos_p * math.cos(theta) - ry * sin_p * math.sin(theta),
                               cy + rx * sin_p * math.cos(theta) + ry * cos_p * math.sin(theta)))
    return points


def path_bounds(d: str) -> tuple[float, float, float, float]:
    """Exact bounding box (x0, y0, x1, y1) of SVG path data: curves by their extrema, not their control points."""
    points: list[tuple[float, float]] = []
    x = y = start_x = start_y = 0.0
    last_cubic = last_quad = None  # second control point of the previous C/S, control point of the previous Q/T
    for command, a in parse_path(d):
        upper = command.upper()
        ox, oy = (x, y) if command.islower() else (0.0, 0.0)
        cubic = quad = None
        if upper == "M":
            x, y = a[0] + ox, a[1] + oy
            start_x, start_y = x, y
            points.append((x, y))
        elif upper == "L":
            x, y = a[0] + ox, a[1] + oy
            points.append((x, y))
        elif upper == "H":
            x = a[0] + ox
            points.append((x, y))
        elif upper == "V":
            y = a[0] + oy
            points.append((x, y))
        elif upper in "CS":
            if upper == "C":
                c1, c2, end = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy), (a[4] + ox, a[5] + oy)
            else:
                c1 = (2 * x - last_cubic[0], 2 * y - last_cubic[1]) if last_cubic else (x, y)
                c2, end = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            points += _cubic_points((x, y), c1, c2, end)
            cubic, (x, y) = c2, end
        elif upper in "QT":
            if upper == "Q":
                c, end = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            else:
                c = (2 * x - last_quad[0], 2 * y - last_quad[1]) if last_quad else (x, y)
                end = (a[0] + ox, a[1] + oy)
            points += _quad_points((x, y), c, end)
            quad, (x, y) = c, end
        elif upper == "A":
            end = (a[5] + ox, a[6] + oy)
            points += _arc_points((x, y), a[0], a[1], a[2], bool(a[3]), bool(a[4]), end)
            x, y = end
        else:  # Z closes back to the start of the subpath
            x, y = start_x, start_y
        last_cubic, last_quad = cubic, quad
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    if not all(math.isfinite(v) for v in xs + ys):
        die("path data has a coordinate that is not a finite number")
    return min(xs), min(ys), max(xs), max(ys)


def shape_bounds(tag: str, element: ET.Element) -> tuple[float, float, float, float]:
    if tag == "rect":
        x, y = parse_num(element.get("x", "0"), "rect x"), parse_num(element.get("y", "0"), "rect y")
        w, h = parse_num(element.get("width"), "rect width"), parse_num(element.get("height"), "rect height")
        if w < 0 or h < 0:
            die("rect width and height must not be negative")
        return x, y, x + w, y + h
    if tag == "circle":
        cx, cy, r = (parse_num(element.get(k), f"circle {k}") for k in ("cx", "cy", "r"))
        if r < 0:
            die("circle r must not be negative")
        return cx - r, cy - r, cx + r, cy + r
    if tag == "ellipse":
        cx, cy, rx, ry = (parse_num(element.get(k), f"ellipse {k}") for k in ("cx", "cy", "rx", "ry"))
        if rx < 0 or ry < 0:
            die("ellipse rx and ry must not be negative")
        return cx - rx, cy - ry, cx + rx, cy + ry
    if tag == "polygon":
        values = parse_numbers(element.get("points", ""), "polygon points")
        if len(values) < 6 or len(values) % 2:
            die("polygon has invalid points")
        return min(values[0::2]), min(values[1::2]), max(values[0::2]), max(values[1::2])
    d = element.get("d")
    if not d or not d.strip():
        die("path has no d attribute")
    return path_bounds(d)


def char_em(char: str) -> float:
    """Rough advance width in em: full-width (CJK) 1, space 0.3, anything else 0.6."""
    if char.isspace():
        return 0.3
    return 1.0 if unicodedata.east_asian_width(char) in ("W", "F") else 0.6


def text_box(element: ET.Element) -> tuple[float, float, tuple[float, float, float, float], str]:
    """(anchor x, anchor y, estimated box, content). The box is 0.8 em above and 0.2 em below the baseline."""
    x, y = parse_num(element.get("x", "0"), "text x"), parse_num(element.get("y", "0"), "text y")
    size = parse_num(element.get("font-size"), "text font-size")
    content = "".join(element.itertext())
    width = sum(size * char_em(c) for c in content)
    anchor = element.get("text-anchor", "start")
    if anchor not in ("start", "middle", "end"):
        die(f"text-anchor {anchor!r} is not supported; use start, middle or end")
    left = x if anchor == "start" else x - width / 2 if anchor == "middle" else x - width
    return x, y, (left, y - 0.8 * size, left + width, y + 0.2 * size), content


def outside(box, area, eps: float) -> list[str]:
    """Which sides of `box` lie beyond `area`."""
    sides = []
    if box[0] < area[0] - eps:
        sides.append("left")
    if box[1] < area[1] - eps:
        sides.append("top")
    if box[2] > area[2] + eps:
        sides.append("right")
    if box[3] > area[3] + eps:
        sides.append("bottom")
    return sides


def span(box) -> str:
    return f"x {fmt(round(box[0], 2))}..{fmt(round(box[2], 2))}, y {fmt(round(box[1], 2))}..{fmt(round(box[3], 2))}"


def short(text: str) -> str:
    return text if len(text) <= 16 else text[:15] + "…"


# ---------------------------------------------------------------- validation


def inspect(svg_path: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings). Bounds are checked in viewBox user units, so a bleed offset is respected."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        root = ET.parse(svg_path).getroot()
    except (ET.ParseError, OSError) as exc:
        return [f"cannot parse SVG: {exc}"], []
    if local_name(root.tag) != "svg":
        return ["root element is not svg"], []
    try:
        width = parse_num(root.get("width"), "svg width")
        height = parse_num(root.get("height"), "svg height")
        if width <= 0 or height <= 0:
            return ["canvas dimensions must be positive"], []
        if root.get("viewBox") is None:
            canvas = (0.0, 0.0, width, height)
        else:
            box = parse_numbers(root.get("viewBox"), "svg viewBox")
            if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
                die("svg viewBox must be 'min-x min-y width height' with a positive width and height")
            canvas = (box[0], box[1], box[0] + box[2], box[1] + box[3])
    except ValueError as exc:
        return [str(exc)], []
    eps = EPS * max(canvas[2] - canvas[0], canvas[3] - canvas[1])

    # trim box: the canvas minus the bleed written by `render` (no metadata: the whole canvas)
    trim, bleed = canvas, 0.0
    meta = next((e for e in root.iter() if local_name(e.tag) == "metadata" and e.get("data-trim-width") is not None), None)
    if meta is not None:
        try:
            trim_w = parse_num(meta.get("data-trim-width"), "metadata data-trim-width")
            trim_h = parse_num(meta.get("data-trim-height"), "metadata data-trim-height")
            bleed = parse_num(meta.get("data-bleed", "0"), "metadata data-bleed")
            trim = (canvas[0] + bleed, canvas[1] + bleed, canvas[2] - bleed, canvas[3] - bleed)
            if abs(trim[2] - trim[0] - trim_w) > 0.01 or abs(trim[3] - trim[1] - trim_h) > 0.01:
                errors.append(
                    f"metadata trim {fmt(trim_w)}x{fmt(trim_h)} with bleed {fmt(bleed)} does not match the viewBox "
                    f"({span(canvas)})"
                )
        except ValueError as exc:
            errors.append(str(exc))
    trim_short = min(trim[2] - trim[0], trim[3] - trim[1])
    safe = SAFE_AREA * trim_short

    colors: set[str] = set()
    graphic_count = 0
    background = None
    texts: list[ET.Element] = []
    for element in root.iter():
        tag = local_name(element.tag)
        if element is not root and tag not in SUPPORTED_ELEMENTS:
            errors.append(f"<{tag}> is not supported by the poster checks; use rect, circle, ellipse, polygon, path or text")
            continue
        if element.get("transform") is not None:
            errors.append(f"<{tag}> has a transform, which the bounds check cannot follow; write the final coordinates instead")
        if element.get("style") is not None:
            errors.append(f"<{tag}> uses a style attribute, which the colour checks cannot read; use a fill attribute")
        stroke = element.get("stroke")
        if stroke and stroke.lower() != "none":
            errors.append(f"<{tag}> has a stroke, which the colour and bounds checks do not cover; draw it as a filled shape")
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

        if tag in GRAPHICS:
            try:
                box = shape_bounds(tag, element)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            sides = outside(box, canvas, eps)
            if sides:
                edge = "bleed edge" if bleed > 0 else "canvas edge"
                errors.append(f"{tag} extends outside the canvas past the {'/'.join(sides)} {edge} ({span(box)}; canvas {span(canvas)})")
            elif bleed > 0 and role != "background":
                for i, side in enumerate(("left", "top", "right", "bottom")):
                    sign = -1 if i < 2 else 1
                    beyond_trim = sign * (box[i] - trim[i]) >= -eps
                    short_of_bleed = sign * (canvas[i] - box[i]) > eps
                    if beyond_trim and short_of_bleed:
                        warnings.append(
                            f"{tag} reaches the {side} trim edge but stops short of the bleed edge ({span(box)}); "
                            f"extend it to {fmt(round(canvas[i], 2))} or keep it inside the trim, so an off cut leaves no sliver"
                        )
        elif tag == "text":
            texts.append(element)
            try:
                x, y, box, content = text_box(element)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if outside((x, y, x, y), canvas, eps):
                errors.append(f"text {short(content)!r} is anchored at ({fmt(x)}, {fmt(y)}), outside the canvas ({span(canvas)})")
                continue
            sides = outside(box, trim, eps)
            if sides:
                errors.append(
                    f"text {short(content)!r} is estimated at {span(box)} and runs past the {'/'.join(sides)} trim edge "
                    f"(trim {span(trim)}); shorten the copy or reduce the size"
                )
            elif box[0] < trim[0] + safe - eps or box[2] > trim[2] - safe + eps:
                warnings.append(
                    f"text {short(content)!r} is estimated at {span(box)} and runs into the side margin of the safe area "
                    f"({fmt(round(trim[0] + safe, 2))}..{fmt(round(trim[2] - safe, 2))}); shorten it or reduce the size "
                    "unless the edge tension is intended"
                )

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
        except ValueError:
            size = 0  # already reported above
        weights.add(element.get("font-weight", "400"))
        fill = element.get("fill", "")
        if background and HEX_RE.fullmatch(fill):
            required = 3.0 if size >= 0.04 * trim_short else 4.5
            ratio = contrast(fill.upper(), background)
            if ratio + 1e-9 < required:
                errors.append(f"text contrast {ratio:.2f}:1 is below {required:.1f}:1")
    if len(sizes) > 2:
        errors.append(f"poster uses {len(sizes)} text sizes; maximum is 2")
    if len(weights) > 2:
        errors.append(f"poster uses {len(weights)} text weights; maximum is 2")
    return errors, warnings


def validate(svg_path: Path) -> list[str]:
    """Errors only (kept for callers of the old interface); see inspect() for warnings too."""
    return inspect(svg_path)[0]


# ---------------------------------------------------------------- self-test


def selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    palette = {"background": "#F3EFE6", "foreground": "#151515", "accent": "#D95336"}

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)

        def run(name: str, shapes: list, width: float = 1080, height: float = 1350, bleed: float = 36, **copy):
            spec = {"width": width, "height": height, "bleed": bleed, "palette": palette, "shapes": shapes}
            spec.update(copy)
            (d / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            render(d / f"{name}.json", d / f"{name}.svg")
            return inspect(d / f"{name}.svg")

        def has(messages: list[str], fragment: str) -> bool:
            return any(fragment in m for m in messages)

        errors, warnings = run("example", [
            {"type": "circle", "cx": 760, "cy": 410, "r": 210, "fill": "accent"},
            {"type": "rect", "x": 90, "y": 620, "width": 900, "height": 360, "fill": "foreground"},
        ], bleed=0, title="NORTH WINDOW", subtitle="Shanghai · 2026", credit="Photograph: supplied by user")
        check("SKILL.md example passes with no warnings", not errors and not warnings, str(errors + warnings))

        errors, warnings = run("full_bleed", [{"type": "rect", "x": -36, "y": -36, "width": 1152, "height": 1422, "fill": "accent"}])
        check("bleed 36: full-bleed rect passes (was reported outside)", not errors and not warnings, str(errors + warnings))

        errors, _ = run("beyond_bleed", [{"type": "rect", "x": 1100, "y": 100, "width": 50, "height": 50, "fill": "accent"}])
        check("bleed 36: rect ending at 1150 > bleed edge 1116 fails (was PASS)", has(errors, "rect extends outside the canvas"), str(errors))

        errors, _ = run("beyond_1036", [{"type": "rect", "x": 1040, "y": 100, "width": 30, "height": 30, "fill": "accent"}], width=1000, height=1400)
        check("trim 1000, bleed 36: rect at 1040..1070 fails (was PASS)", has(errors, "extends outside the canvas"), str(errors))

        errors, warnings = run("short_of_bleed", [{"type": "rect", "x": 900, "y": 100, "width": 200, "height": 50, "fill": "accent"}])
        check("rect crossing the trim but short of the bleed edge: warning, not error", not errors and has(warnings, "short of the bleed edge"), str(errors + warnings))

        errors, _ = run("circle_out", [{"type": "circle", "cx": 1080, "cy": 1350, "r": 60, "fill": "accent"}])
        check("circle past the bleed corner fails", has(errors, "circle extends outside"), str(errors))
        errors, _ = run("circle_in", [{"type": "circle", "cx": 1080, "cy": 1350, "r": 30, "fill": "accent"}])
        check("circle inside the bleed corner passes", not errors, str(errors))
        errors, _ = run("poly_out", [{"type": "polygon", "points": [[-40, 0], [100, 0], [100, 100]], "fill": "accent"}])
        check("polygon past the left bleed edge fails", has(errors, "polygon extends outside"), str(errors))

        errors, _ = run("path_far", [{"type": "path", "d": "M 5000 5000 L 6000 5000 L 6000 6000 Z", "fill": "accent"}], width=1000, height=1000, bleed=0)
        check("path far outside a 1000x1000 canvas fails (was PASS)", has(errors, "path extends outside the canvas"), str(errors))

        cjk = "这是一个很长的中文标题用来测试文字会不会超出画布"
        errors, _ = run("cjk", [], bleed=0, title=cjk[:26])
        check("26-character Chinese title at 64.8 px fails (was PASS)", has(errors, "runs past the right trim edge"), str(errors))
        errors, warnings = run("latin_fit", [], bleed=0, title="NORTH WINDOW")
        check("short Latin title passes", not errors and not warnings, str(errors + warnings))
        errors, warnings = run("latin_margin", [], bleed=0, title="THE LONG QUIET HOURS AT 5AM")
        check("title reaching the safe-area margin: warning only", not errors and has(warnings, "safe area"), str(errors + warnings))

    # exact path bounds, absolute and relative, every command
    cases = [
        ("M/L/H/V/Z absolute", "M 10 20 L 30 40 H 5 V 60 Z", (5, 20, 30, 60)),
        ("m/l/h/v/z relative", "m 10 20 l 20 20 h -25 v 20 z m 100 0 l 5 5", (5, 20, 115, 60)),
        ("implicit lineto after M", "M0 0 100 50 20 80", (0, 0, 100, 80)),
        ("cubic: control points outside, curve inside", "M 100 100 C 100 -20 900 -20 900 100", (100, 10, 900, 100)),
        ("cubic bulging outside", "M 100 100 C 100 -200 900 -200 900 100", (100, -125, 900, 100)),
        ("S reflects the previous control point", "M 100 400 C 100 100 300 100 300 400 S 500 700 500 400", (100, 175, 500, 625)),
        ("s relative", "M 100 400 c 0 -300 200 -300 200 0 s 200 300 200 0", (100, 175, 500, 625)),
        ("Q apex", "M 100 400 Q 300 100 500 400", (100, 250, 500, 400)),
        ("T reflects the Q control point", "M 100 400 Q 300 100 500 400 T 900 400", (100, 250, 900, 550)),
        ("t relative", "M 100 400 q 200 -300 400 0 t 400 0", (100, 250, 900, 550)),
        ("A sweep 1 goes over the top", "M 100 300 A 300 300 0 0 1 700 300", (100, 0, 700, 300)),
        ("A sweep 0 goes under", "M 100 300 A 300 300 0 0 0 700 300", (100, 300, 700, 600)),
        ("a relative, packed flags", "M10 10a5 5 0 1010 10", None),
        ("A radius too small is scaled up", "M 0 0 A 1 1 0 0 1 100 0", (0, -50, 100, 0)),
        ("A rotated ellipse, sweep 1 runs clockwise (right side)", "M 0 0 A 100 50 90 0 1 0 200", (0, 0, 50, 200)),
        ("A rotated ellipse, sweep 0 (left side)", "M 0 0 A 100 50 90 0 0 0 200", (-50, 0, 0, 200)),
        ("numbers with exponents and no separators", "M1e2-5L.5.5", (0.5, -5, 100, 0.5)),
    ]
    for name, d_attr, expected in cases:
        try:
            got = path_bounds(d_attr)
            ok = expected is None or all(abs(g - e) < 1e-6 for g, e in zip(got, expected))
            check(f"path bounds: {name}", ok, f"{tuple(round(v, 4) for v in got)} != {expected}")
        except ValueError as exc:
            check(f"path bounds: {name}", False, str(exc))
    for bad in ("L 10 10", "M 10 10 L 20", "M 10 10 X 5 5", "M 0 0 A 5 5 0 2 0 10 10", "M 0 0 Z 5"):
        try:
            path_bounds(bad)
            check(f"malformed path rejected: {bad!r}", False)
        except ValueError:
            check(f"malformed path rejected: {bad!r}", True)

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        head = ('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="-50 -50 1100 1100">'
                '<rect x="-50" y="-50" width="1100" height="1100" fill="#FFFFFF" data-role="background"/>')
        samples = {
            "no metadata: viewBox offset respected": (head + '<rect x="-40" y="-40" width="100" height="100" fill="#000000"/></svg>', None),
            "transform rejected": (head + '<g transform="translate(900 0)"><rect x="0" y="0" width="300" height="10" fill="#000000"/></g></svg>', "transform"),
            "stroke rejected": (head + '<rect x="0" y="0" width="10" height="10" fill="#000000" stroke="#FF0000"/></svg>', "stroke"),
            "unsupported element rejected": (head + '<line x1="0" y1="0" x2="5000" y2="0"/></svg>', "<line> is not supported"),
            "text anchored outside the canvas": (head + '<text x="2000" y="100" font-size="20" fill="#000000">x</text></svg>', "outside the canvas"),
            "middle-anchored text measured both ways": (head + '<text x="10" y="100" font-size="40" text-anchor="middle" fill="#000000">WIDE TITLE</text></svg>', "left trim edge"),
        }
        for name, (svg, fragment) in samples.items():
            (d / "t.svg").write_text(svg, encoding="utf-8")
            errors, _ = inspect(d / "t.svg")
            check(name, (not errors) if fragment is None else has(errors, fragment), str(errors))

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(["--help"])
            except SystemExit as exc:
                code = exc.code
        check("--help prints usage and exits 0", code == 0 and "usage" in out.getvalue().lower())

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true", help="run the built-in checks and exit")
    subparsers = parser.add_subparsers(dest="command")
    render_parser = subparsers.add_parser("render", help="render JSON specification to SVG")
    render_parser.add_argument("spec", type=Path)
    render_parser.add_argument("output", type=Path)
    validate_parser = subparsers.add_parser("validate", help="validate an SVG poster")
    validate_parser.add_argument("svg", type=Path)
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.command is None:
        parser.error("choose a command: render or validate")
    try:
        if args.command == "render":
            render(args.spec, args.output)
            print(f"rendered {args.output}")
        else:
            errors, warnings = inspect(args.svg)
            for warning in warnings:
                print(f"WARNING: {warning}", file=sys.stderr)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("PASS: SVG meets deterministic poster checks"
                  + (f" ({len(warnings)} warning{'s' if len(warnings) != 1 else ''})" if warnings else ""))
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
