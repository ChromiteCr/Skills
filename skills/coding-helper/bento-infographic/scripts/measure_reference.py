#!/usr/bin/env python3
"""量 bento 总结图：格子、格缝、外边距、圆角、主图和标签字号。

同一套量法既量苹果的样图（tests/fixtures/bento-infographic/apple-reference/），
也量本 skill 自己渲染出来的 PNG，两边的读数才能直接比。

用法：
  measure_reference.py tiles IMAGE [--method color|gutter]
  measure_reference.py all DIR [-o measurements.json]

all 会读 DIR/labels.json：每张图用哪种分割方法、要不要人工切线、标签的框和原文。
字号靠本机的 SF Pro 可变字体（/System/Library/Fonts/SFNS.ttf）按同样的字高与宽度重新渲染来反推；
没有这个文件时只给字高，不给字号。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

TOOL = "measure_reference 0.1.0"
SF_FONT = Path("/System/Library/Fonts/SFNS.ttf")
MIN_TILE_FRAC = 0.01        # 面积小于画布 1% 的连通域不算格子（图标、高光）
GUTTER_MAX = 40             # 两格之间隔得比这远就不算格缝
ROUND_K = 1 - 1 / math.sqrt(2)


# ---------------------------------------------------------------- basics

def to_array(img) -> np.ndarray:
    if isinstance(img, (str, Path)):
        img = Image.open(img)
    if isinstance(img, Image.Image):
        img = np.asarray(img.convert("RGB"))
    return np.asarray(img, dtype=np.float64)


def hex_color(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in rgb)


def luminance(a: np.ndarray) -> np.ndarray:
    return a.mean(axis=2)


def background(a: np.ndarray) -> np.ndarray:
    """Median colour of the outermost 3 px frame."""
    frame = np.concatenate([a[:3].reshape(-1, 3), a[-3:].reshape(-1, 3),
                            a[:, :3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)])
    return np.median(frame, axis=0)


# ---------------------------------------------------------------- segmentation

def _boxes_from_labels(lab: np.ndarray, n: int) -> list[list[int]]:
    boxes = []
    for sl in ndi.find_objects(lab):
        if sl is None:
            continue
        boxes.append([sl[1].start, sl[0].start, sl[1].stop, sl[0].stop])
    return boxes


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _merge_overlapping(boxes: list[list[int]]) -> list[list[int]]:
    """Fragments of one tile (a dark band in a photo, an icon) have overlapping boxes; real tiles never do."""
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out = []
        while boxes:
            cur = boxes.pop()
            i = 0
            while i < len(boxes):
                if _overlap(cur, boxes[i]):
                    o = boxes.pop(i)
                    cur = [min(cur[0], o[0]), min(cur[1], o[1]), max(cur[2], o[2]), max(cur[3], o[3])]
                    changed = True
                    i = 0
                else:
                    i += 1
            out.append(cur)
        boxes = out
    return boxes


def _apply_cuts(mask: np.ndarray, cuts) -> np.ndarray:
    """A cut forces a gutter where two tiles read as one: {"y", "x0", "x1", "width"} or {"x", "y0", "y1", "width"}."""
    mask = mask.copy()
    h, w = mask.shape
    for c in cuts or ():
        half = max(1, int(c.get("width", 8))) / 2
        if "y" in c:
            y0, y1 = int(round(c["y"] - half)), int(round(c["y"] + half))
            mask[max(0, y0):min(h, y1), max(0, int(c.get("x0", 0))):min(w, int(c.get("x1", w)))] = False
        else:
            x0, x1 = int(round(c["x"] - half)), int(round(c["x"] + half))
            mask[max(0, int(c.get("y0", 0))):min(h, int(c.get("y1", h))), max(0, x0):min(w, x1)] = False
    return mask


def tile_mask_color(a: np.ndarray, bg: np.ndarray) -> np.ndarray:
    tol = 4 if bg.mean() > 128 else 6
    mask = np.abs(a - bg).max(axis=2) > tol
    return ndi.binary_opening(mask, structure=np.ones((3, 3)))


def tile_mask_gutter(a: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """For frosted tiles whose colours run into the canvas: gutters are long, flat, canvas-bright runs."""
    lum = luminance(a)
    g = ndi.gaussian_filter(lum, 1.0)
    gy, gx = np.gradient(g)
    flat = (np.hypot(gx, gy) < 0.9) & (lum > bg.mean() - 8) & (lum < bg.mean() + 16)

    def long_runs(m: np.ndarray) -> np.ndarray:
        out = np.zeros_like(m)
        for r in range(m.shape[0]):
            row = m[r]
            edges = np.flatnonzero(np.diff(np.concatenate([[0], row.astype(np.int8), [0]])))
            for s, e in zip(edges[::2], edges[1::2]):
                if e - s >= 60:
                    out[r, s:e] = True
        return out

    gutter = long_runs(flat) | long_runs(flat.T).T
    tiles = ~ndi.binary_dilation(gutter, iterations=1)
    return ndi.binary_opening(tiles, structure=np.ones((5, 5)))


def find_tiles(a: np.ndarray, method: str = "color", cuts=None):
    bg = background(a)
    mask = tile_mask_color(a, bg) if method == "color" else tile_mask_gutter(a, bg)
    mask = _apply_cuts(mask, cuts)
    lab, n = ndi.label(mask)
    boxes = _boxes_from_labels(lab, n)
    if method == "color":
        boxes = _merge_overlapping(boxes)
    h, w = mask.shape
    min_area = (MIN_TILE_FRAC if method == "color" else MIN_TILE_FRAC * 0.4) * w * h
    boxes = [b for b in boxes if (b[2] - b[0]) * (b[3] - b[1]) >= min_area]
    boxes.sort(key=lambda b: (b[1], b[0]))
    return bg, mask, boxes


# ---------------------------------------------------------------- per-tile readings

def corner_radii_mask(mask: np.ndarray, box) -> list[float | None]:
    """Fallback when a tile has too little contrast for sub-pixel reading: walk each corner's diagonal
    on the binary mask. Biased by a pixel or two, so it is only a fallback."""
    x0, y0, x1, y1 = box
    sub = mask[y0:y1, x0:x1]
    h, w = sub.shape
    out = []
    for flip_y, flip_x in ((False, False), (False, True), (True, False), (True, True)):
        m = sub[::-1] if flip_y else sub
        m = m[:, ::-1] if flip_x else m
        r = None
        for k in range(min(h, w) // 2):
            if m[k, k]:
                r = round(k / ROUND_K, 1)
                break
        out.append(r)
    return out


def fill_color(a: np.ndarray, box) -> np.ndarray:
    x0, y0, x1, y1 = box
    w = x1 - x0
    strip = a[y0 + 8:y0 + 14, x0 + int(w * 0.3):x0 + int(w * 0.7)].reshape(-1, 3)
    return np.median(strip, axis=0) if len(strip) else np.array([np.nan] * 3)


def _cross(profile: np.ndarray, mid: float, rising: bool) -> float:
    """Sub-pixel index where the profile first passes mid (rising: from below)."""
    v = (profile - mid) if rising else (mid - profile)
    for i in range(1, len(v)):
        if v[i - 1] < 0 <= v[i]:
            return i - 1 + (-v[i - 1]) / (v[i] - v[i - 1])
    return math.nan


PAD = 6        # how far outside a tile's integer box the scanlines start
INSET = 10     # where the tile's own brightness is sampled, inside the edge


def _corner_patch(lum: np.ndarray, box, corner: int):
    """Patch with the given corner moved to the top-left, starting PAD px outside the tile."""
    x0, y0, x1, y1 = box
    h, w = lum.shape
    if x0 < PAD or y0 < PAD or x1 + PAD > w or y1 + PAD > h:
        return None
    p = lum[y0 - PAD:y1 + PAD, x0 - PAD:x1 + PAD]
    if corner in (2, 3):
        p = p[::-1]
    if corner in (1, 3):
        p = p[:, ::-1]
    return p


def _corner_reading(p: np.ndarray, bg_l: float, r_hint: float):
    """Edges, radius and bend extent for the top-left corner of patch p (tile starts near (PAD, PAD))."""
    hh, ww = p.shape
    along = int(min(3 * r_hint + 24, ww / 2, hh / 2))
    if along < 2 * r_hint + 12:
        return None
    tile_l = float(np.median(p[PAD + INSET:PAD + INSET + 4, int(along * 0.7):along]))
    if abs(tile_l - bg_l) < 8:
        return None
    mid, rising = (bg_l + tile_l) / 2, tile_l > bg_l
    depth = PAD + int(r_hint) + 12
    top = np.array([_cross(p[:depth, k], mid, rising) for k in range(along)])
    left = np.array([_cross(p[k, :depth], mid, rising) for k in range(along)])
    far = slice(int(along * 0.7), along)
    if np.isnan(top[far]).all() or np.isnan(left[far]).all():
        return None
    ty, lx = float(np.nanmedian(top[far])), float(np.nanmedian(left[far]))
    d = None
    for s in np.arange(0.0, float(depth), 0.25):
        v = ndi.map_coordinates(p, [[ty + s], [lx + s]], order=1)[0]
        if ((v - mid) if rising else (mid - v)) >= 0:
            d = s
            break
    if not d:
        return None
    r = d / ROUND_K
    ext = []
    for prof, base, other in ((top, ty, lx), (left, lx, ty)):
        off = prof - base
        idx = [k for k in range(len(off)) if not math.isnan(off[k]) and off[k] > 0.35]
        if not idx:
            return None
        ext.append(idx[-1] + 1 - other)
    # Crossings are in pixel-centre coordinates; a pixel's area starts half a pixel earlier,
    # so the geometric edge (50% coverage) sits 0.5 px further in.
    return {"edge_t": ty - PAD + 0.5, "edge_l": lx - PAD + 0.5, "radius": r, "bend": float(np.mean(ext)) / r}


def refine_tile(a: np.ndarray, bg: np.ndarray, mask: np.ndarray, box) -> dict:
    """Sub-pixel edges (midpoint between canvas and tile brightness), corner radii and bend ratios.
    The bend ratio (where the edge starts to curve / radius) is about 0.85-1.05 for a circular arc;
    a continuous-curvature corner starts bending much earlier."""
    lum = luminance(a)
    bg_l = float(bg.mean())
    x0, y0, x1, y1 = box
    hint_list = [r for r in corner_radii_mask(mask, box) if r is not None]
    r_hint = float(np.median(hint_list)) if hint_list else 0.0
    if r_hint < 6:
        # The gutter method's mask has square corners; start from the typical radius (2% of the width).
        r_hint = 0.02 * a.shape[1]
    edges = [float(x0), float(y0), float(x1), float(y1)]
    radii, bends = [], []
    readings = []
    for corner in range(4):
        p = _corner_patch(lum, box, corner)
        rd = _corner_reading(p, bg_l, r_hint) if (p is not None and r_hint >= 6) else None
        readings.append(rd)
        radii.append(None if rd is None else round(rd["radius"], 2))
        bends.append(None if rd is None else round(rd["bend"], 3))
    # edges from the corner readings (each corner gives one horizontal and one vertical edge)
    tops = [rd["edge_t"] for c, rd in enumerate(readings) if rd and c in (0, 1)]
    bots = [rd["edge_t"] for c, rd in enumerate(readings) if rd and c in (2, 3)]
    lefts = [rd["edge_l"] for c, rd in enumerate(readings) if rd and c in (0, 2)]
    rights = [rd["edge_l"] for c, rd in enumerate(readings) if rd and c in (1, 3)]
    if tops:
        edges[1] = y0 + float(np.median(tops))
    if bots:
        edges[3] = y1 - float(np.median(bots))
    if lefts:
        edges[0] = x0 + float(np.median(lefts))
    if rights:
        edges[2] = x1 - float(np.median(rights))
    if not any(r is not None for r in radii):
        radii = corner_radii_mask(mask, box)
    good_bends = [b for b in bends if b is not None]
    return {"edges": [round(e, 2) for e in edges], "radius": radii,
            "curve_ratio": round(float(np.median(good_bends)), 3) if good_bends else None}


def gutters(boxes) -> dict:
    hs, vs = [], []
    for a in boxes:
        for b in boxes:
            if a is b:
                continue
            if min(a[3], b[3]) - max(a[1], b[1]) > 40 and 0 < b[0] - a[2] < GUTTER_MAX:
                hs.append(round(b[0] - a[2], 2))
            if min(a[2], b[2]) - max(a[0], b[0]) > 40 and 0 < b[1] - a[3] < GUTTER_MAX:
                vs.append(round(b[1] - a[3], 2))
    allg = hs + vs
    return {"h": sorted(hs), "v": sorted(vs), "median": round(float(np.median(allg)), 2) if allg else None}


def hero_of(boxes, w: int, h: int) -> dict | None:
    cx, cy = w / 2, h / 2
    inside = [b for b in boxes if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]]
    if not inside:
        return None
    b = max(inside, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    bw, bh = b[2] - b[0], b[3] - b[1]
    return {
        "index": boxes.index(b),
        "box": [int(round(v)) for v in b],
        "w_frac": round(bw / w, 4),
        "h_frac": round(bh / h, 4),
        "area_frac": round(bw * bh / (w * h), 4),
        "aspect": round(bw / bh, 3),
        "center_offset": [round(((b[0] + b[2]) / 2 - cx) / w, 4), round(((b[1] + b[3]) / 2 - cy) / h, 4)],
    }


# ---------------------------------------------------------------- labels

def _ink_metrics(lum: np.ndarray, dark_text: bool):
    lo, hi = np.percentile(lum, 2), np.percentile(lum, 98)
    mid = (lo + hi) / 2
    ink = lum < mid if dark_text else lum > mid
    rows = ink.sum(axis=1)
    ys = np.flatnonzero(rows)
    if len(ys) == 0:
        return None
    r = rows[ys[0]:ys[-1] + 1]
    dense = [k for k, v in enumerate(r) if v >= 0.25 * r.max()]
    xs = np.flatnonzero(ink.sum(axis=0))
    return {"asc": dense[-1] + 1, "width": int(xs[-1] - xs[0] + 1), "top": int(ys[0])}


def sf_font(size: int, weight: int = 600, opsz: int = 60):
    font = ImageFont.truetype(str(SF_FONT), size)
    values = {"Width": 100, "Optical Size": opsz, "GRAD": 400, "Weight": weight}
    axes = []
    for ax in font.get_variation_axes():
        name = ax["name"].decode() if isinstance(ax["name"], bytes) else ax["name"]
        axes.append(values.get(name, ax["default"]))
    font.set_variation_by_axes(axes)
    return font


def _render_metrics(text: str, size: int = 200, weight: int = 600):
    font = sf_font(size, weight)
    w = int(font.getlength(text)) + 40
    h = int(size * 1.8)
    im = Image.new("L", (w, h), 255)
    ImageDraw.Draw(im).text((20, int(size * 0.3)), text, font=font, fill=0)
    return _ink_metrics(np.asarray(im, dtype=np.float64), True)


def label_metrics(a: np.ndarray, label: dict) -> dict:
    x0, y0, x1, y1 = label["box"]
    lum = luminance(a)[y0:y1, x0:x1]
    s = _ink_metrics(lum, label.get("polarity", "dark") == "dark")
    out = {"text": label["text"], "box": label["box"]}
    if s is None:
        return out
    out.update({"cap_px": s["asc"], "ink_width": s["width"], "top": y0 + s["top"]})
    if SF_FONT.exists():
        r = _render_metrics(label["text"])
        out["font_px_width"] = round(200 * s["width"] / r["width"], 2)
        out["font_px_cap"] = round(200 * s["asc"] / r["asc"], 2)
    return out


# ---------------------------------------------------------------- whole image

def measure_image(img, method: str = "color", cuts=None, labels=None, name: str = "") -> dict:
    a = to_array(img)
    h, w = a.shape[:2]
    bg, mask, boxes = find_tiles(a, method, cuts)
    tiles = []
    for b in boxes:
        ref = refine_tile(a, bg, mask, b)
        fill = fill_color(a, b)
        tiles.append({"box": b, "edges": ref["edges"], "fill": None if np.isnan(fill).any() else hex_color(fill),
                      "radius": ref["radius"], "curve_ratio": ref["curve_ratio"]})
    edges = [t["edges"] for t in tiles]
    ratios = [t["curve_ratio"] for t in tiles if t["curve_ratio"] is not None]
    res = {
        "file": name,
        "size": [w, h],
        "method": method,
        "cuts": cuts or [],
        "background": hex_color(bg),
        "n_tiles": len(tiles),
        "tiles": tiles,
        "margins": {"l": round(min(e[0] for e in edges), 2), "t": round(min(e[1] for e in edges), 2),
                    "r": round(w - max(e[2] for e in edges), 2), "b": round(h - max(e[3] for e in edges), 2)}
        if edges else None,
        "gutters": gutters(edges),
        "hero": hero_of(edges, w, h),
        "curve_ratio_median": round(float(np.median(ratios)), 3) if ratios else None,
        "labels": [label_metrics(a, lb) for lb in (labels or [])],
    }
    res["summary"] = summarise(res)
    return res


def summarise(res: dict) -> dict:
    w, h = res["size"]
    fonts = [lb["font_px_width"] for lb in res["labels"] if "font_px_width" in lb]
    u = float(np.median(fonts)) if fonts else None
    radii = [r for t in res["tiles"] for r in t["radius"] if r is not None]
    radius = float(np.median(radii)) if radii else None
    g = res["gutters"]["median"]
    out = {"u_px": None if u is None else round(u, 2),
           "u_frac_w": None if u is None else round(u / w, 5),
           "u_frac_short": None if u is None else round(u / min(w, h), 5),
           "gutter_px": g, "radius_px": radius}
    if u:
        out["gutter_u"] = None if g is None else round(g / u, 3)
        out["radius_u"] = None if radius is None else round(radius / u, 3)
        m = res["margins"]
        out["margin_u"] = None if m is None else round(float(np.median(list(m.values()))) / u, 3)
    return out


def measure(path, method: str = "color", cuts=None, labels=None) -> dict:
    path = Path(path)
    return measure_image(path, method, cuts, labels, name=path.name)


def measure_dir(directory) -> dict:
    directory = Path(directory)
    spec_path = directory / "labels.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}
    images = sorted(p for p in directory.iterdir() if p.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg"})
    results = []
    for p in images:
        conf = spec.get(p.name, {})
        results.append(measure(p, conf.get("method", "color"), conf.get("cuts"), conf.get("labels")))
    return {"tool": TOOL, "sf_font": SF_FONT.exists(), "images": results}


def table(results: dict) -> str:
    lines = ["file                            tiles  hero w×h (area)        u %W    gutter/u  radius/u  curve"]
    for r in results["images"]:
        s, hero = r["summary"], r["hero"] or {}
        u = "%.3f" % (100 * s["u_frac_w"]) if s.get("u_frac_w") else "  —  "
        lines.append("%-31s %4d   %5.1f%% × %5.1f%% (%4.1f%%)  %6s   %6s    %6s    %s" % (
            r["file"], r["n_tiles"], 100 * hero.get("w_frac", 0), 100 * hero.get("h_frac", 0),
            100 * hero.get("area_frac", 0), u, s.get("gutter_u", "—"), s.get("radius_u", "—"),
            r["curve_ratio_median"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tiles", help="measure one image (no labels)")
    t.add_argument("image")
    t.add_argument("--method", choices=("color", "gutter"), default="color")
    al = sub.add_parser("all", help="measure every image in DIR using DIR/labels.json")
    al.add_argument("directory")
    al.add_argument("-o", "--output")
    args = ap.parse_args(argv)
    if args.cmd == "tiles":
        print(json.dumps(measure(args.image, args.method), ensure_ascii=False, indent=1))
        return 0
    results = measure_dir(args.directory)
    if args.output:
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(table(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
