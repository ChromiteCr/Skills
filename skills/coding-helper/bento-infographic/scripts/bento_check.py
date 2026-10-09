#!/usr/bin/env python3
"""自检：AUDIT-AND-IDEAS.md 4.7 的质量护栏，逐条判断，出 qa.json（schema bento-qa/1）。

数据来自渲染时量出的 dom.json（每格、每段字、每张图的位置与计算样式，外加 fonts 一项：
每段字实际用的字体）、layout.json、bento.json，以及两张 PNG（正常的与去掉文字的，后者用来算照片上文字的对比度）。
"""
from __future__ import annotations

import colorsys
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

import bento_spec as bs

SYSTEM_FONTS = (".SF", "SF Pro", "System Font", "PingFang")
FALLBACK_FONTS = ("Inter", "Noto Sans SC", "Source Han Sans SC")
LARGE_ROLES = {"number", "word", "heroword", "flank"}


# ---------------------------------------------------------------- colour helpers

def parse_color(css: str) -> tuple[float, float, float, float]:
    """'rgb(r, g, b)' / 'rgba(r, g, b, a)' / '#rrggbb' -> 0..1 floats."""
    css = css.strip()
    if css.startswith("#"):
        return tuple(int(css[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1.0,)
    nums = [float(x) for x in re.findall(r"[\d.]+", css)]
    if len(nums) >= 3:
        a = nums[3] if len(nums) > 3 else 1.0
        return nums[0] / 255, nums[1] / 255, nums[2] / 255, a
    return 0.0, 0.0, 0.0, 1.0


def rel_luminance(rgb) -> float:
    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b) -> float:
    la, lb = rel_luminance(a), rel_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def saturation(rgb) -> float:
    return colorsys.rgb_to_hls(*rgb[:3])[2]


def hue_bucket(rgb) -> int:
    return int(colorsys.rgb_to_hls(*rgb[:3])[0] * 360 // 30)


# ---------------------------------------------------------------- the checks

def _check(cid: str, ok: bool, value, limit: str, where=None, note=None) -> dict:
    d = {"id": cid, "pass": bool(ok), "value": value, "limit": limit}
    if where:
        d["where"] = where
    if note:
        d["note"] = note
    return d


def check(spec: dict, layout: dict, dom: dict, png_path=None, textless_png_path=None) -> dict:
    css_w, css_h, dpr = bs.canvas_css(spec)
    lang = spec.get("lang", "zh-CN")
    tok = bs.tokens_for(spec)
    u = tok["u"]
    tiles_spec = {t["id"]: t for t in spec["tiles"]}
    tiles_dom = {t["id"]: t for t in dom["tiles"]}
    texts = dom["texts"]
    checks, warnings = [], []

    # hero position and size
    hero_id = next(t["id"] for t in spec["tiles"] if t["kind"] == "hero")
    hx, hy, hw, hh = tiles_dom[hero_id]["rect"]
    stage_cy = (tok["margin"] + css_h - tok["margin_bottom"]) / 2      # the canvas centre unless a source line is on
    off = max(abs(hx + hw / 2 - css_w / 2) / css_w, abs(hy + hh / 2 - stage_cy) / css_h)
    checks.append(_check("hero_center", off <= 0.005, round(off, 5), "<= 0.005"))
    area = hw * hh / (css_w * css_h)
    hero_t = tiles_spec[hero_id]
    inner_w = css_w - 2 * tok["margin"]
    if hw >= 0.95 * inner_w:
        lo, hi = 0.15, 0.45
    elif hero_t.get("image") or hero_t.get("box_aspect"):
        lo, hi = 0.18, 0.30               # a picture, or a word whose box was sized like a product
    else:
        lo, hi = 0.10, 0.20
    checks.append(_check("hero_area", lo <= area <= hi, round(area, 4), "%.2f–%.2f" % (lo, hi)))

    # gutters, margins and corner radius are the same everywhere
    rects = [t["rect"] for t in dom["tiles"]]
    gaps = []
    for a in rects:
        for b in rects:
            if a is b:
                continue
            if min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]) > 1 and 0 < b[0] - (a[0] + a[2]) < 3 * tok["gutter"]:
                gaps.append(b[0] - (a[0] + a[2]))
            if min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]) > 1 and 0 < b[1] - (a[1] + a[3]) < 3 * tok["gutter"]:
                gaps.append(b[1] - (a[1] + a[3]))
    margins = [min(r[0] for r in rects), min(r[1] for r in rects),
               css_w - max(r[0] + r[2] for r in rects), css_h - max(r[1] + r[3] for r in rects)]
    tol = 0.5 + 1e-6                      # half a CSS px = one output px at dpr 2
    bad_gaps = [round(g, 2) for g in gaps if abs(g - tok["gutter"]) > tol]
    want_margins = [tok["margin"], tok["margin"], tok["margin"], tok["margin_bottom"]]
    bad_margins = [round(m, 2) for m, w in zip(margins, want_margins) if abs(m - w) > tol]
    checks.append(_check("gutter_uniform", not bad_gaps and not bad_margins,
                         {"gutter": round(tok["gutter"], 2), "off": bad_gaps[:5], "margins_off": bad_margins},
                         "±0.5 px"))
    bad_r = sorted({round(t["radius"], 2) for t in dom["tiles"] if abs(t["radius"] - tok["radius"]) > tol})
    checks.append(_check("radius_uniform", not bad_r, {"radius": round(tok["radius"], 2), "off": bad_r}, "±0.5 px"))

    # type sizes and weight
    bad_unit, bad_scale = [], []
    ranges = {"number": (bs.RATIOS["number_min"], bs.RATIOS["number_max"]),
              "word": (bs.WORD_MIN, 3.4), "heroword": (bs.RATIOS["hero_word_min"], bs.RATIOS["hero_word_max"]),
              "flank": (1.6, 2.0), "item": (1.35, 1.45)}
    for t in texts:
        size = t["font_size"] / u
        if t["role"] in ("label", "sub", "chartlabel"):
            if abs(size - 1.0) > 0.01:
                bad_unit.append("%s %.2fu" % (t["tile"], size))
        elif t["role"] == "source":
            if abs(size - bs.RATIOS["source"]) > 0.01:
                bad_unit.append("source %.2fu" % size)
        elif t["role"] in ranges:
            lo_r, hi_r = ranges[t["role"]]
            if not (lo_r - 0.01 <= size <= hi_r + 0.01):
                bad_scale.append("%s %s %.2fu" % (t["tile"], t["role"], size))
    checks.append(_check("unit_size", not bad_unit, round(u, 3), "labels = u", bad_unit or None))
    checks.append(_check("type_scale", not bad_scale, len(bad_scale), "number 2.2–4.3u, word 1.6–3.4u, hero 5–8u",
                         bad_scale or None))
    bad_w = ["%s %s %s" % (t["tile"], t["role"], t["font_weight"]) for t in texts if t["font_weight"] != bs.WEIGHT]
    checks.append(_check("weight", not bad_w, len(bad_w), "600", bad_w or None))

    # overflow: a line wider than its box, or ink outside the tile
    over = []
    for t in texts:
        tile = tiles_dom.get(t["tile"])
        ink = t.get("ink")
        if t.get("wide"):
            over.append("%s %s" % (t["tile"], t["role"]))
        elif tile and ink and t["role"] != "source":
            x, y, w, h = tile["rect"]
            if ink[0] < x - 0.5 or ink[1] < y - 0.5 or ink[0] + ink[2] > x + w + 0.5 or ink[1] + ink[3] > y + h + 0.5:
                over.append("%s %s" % (t["tile"], t["role"]))
    checks.append(_check("overflow", not over, len(over), "0", over or None))

    # label lines and length
    max_lines = bs.LABEL_LIMITS["zh_lines"] if lang == "zh-CN" else bs.LABEL_LIMITS["en_lines"]
    bad_lines = []
    for t in texts:
        if t["role"] != "label":
            continue
        want = len(bs.label_lines(tiles_spec.get(t["tile"], {}).get("label")))
        if t["lines"] > max_lines or (want and t["lines"] != want):
            bad_lines.append("%s %d 行" % (t["tile"], t["lines"]))
    checks.append(_check("label_lines", not bad_lines, len(bad_lines), "<= %d, as written" % max_lines,
                         bad_lines or None))
    length_problems = []
    for t in spec["tiles"]:
        length_problems += bs._label_problems(t.get("label"), lang, t["id"])
    checks.append(_check("label_length", not length_problems, len(length_problems),
                         "en <= 7 words; zh <= 12, line <= 11", length_problems or None))

    # fonts actually used
    counts = {"system": 0, "fallback": 0, "other": 0}
    others = []
    for entry in dom.get("fonts", []):
        for f in entry["fonts"]:
            fam = f.get("family") or ""
            if fam.startswith(SYSTEM_FONTS):
                counts["system"] += f.get("glyphs", 0)
            elif fam.startswith(FALLBACK_FONTS):
                counts["fallback"] += f.get("glyphs", 0)
            else:
                counts["other"] += f.get("glyphs", 0)
                others.append("%s: %s" % (entry.get("tile"), fam))
    if counts["fallback"] and spec.get("font", "system") == "system":
        warnings.append("有 %d 个字形用了兜底字体（Inter 或思源黑体），不是系统字体" % counts["fallback"])
    checks.append(_check("fonts", not others, counts, "only the listed fonts", sorted(set(others)) or None))

    # contrast
    bad_c = []
    textless = _load(textless_png_path)
    for t in texts:
        if t["role"] == "source":
            pass
        color = parse_color(t["color"])
        if t.get("tone") == "silver":
            color = parse_color(bs.SILVER[0])
        bgs = _backgrounds(t, tiles_dom.get(t["tile"]), tiles_spec.get(t["tile"]), textless, dpr, tok)
        if not bgs:
            continue
        worst = min(contrast(color, bg) for bg in bgs)
        need = 3.0 if (t["role"] in LARGE_ROLES and t["font_size"] >= 1.6 * u - 0.01) else 4.5
        if worst < need:
            bad_c.append("%s %s %.2f < %.1f" % (t["tile"], t["role"], worst, need))
    checks.append(_check("contrast", not bad_c, len(bad_c), "labels >= 4.5, large >= 3", bad_c or None))

    # accent: at most one hue, never on labels
    hues, label_colour = set(), []
    for t in texts:
        rgb = parse_color(t["color"])
        if t.get("tone") == "accent" or saturation(rgb) > 0.2:
            if saturation(rgb) > 0.2:
                hues.add(hue_bucket(rgb))
            if t["role"] in ("label", "sub"):
                label_colour.append(t["tile"])
    checks.append(_check("accent_hues", len(hues) <= 1 and not label_colour, len(hues), "<= 1, not on labels",
                         label_colour or None))

    # content mix and tile sizes
    ring = [t for t in spec["tiles"] if t["kind"] != "hero"]
    text_only = [t for t in ring if t["kind"] in bs.TEXT_ONLY_KINDS and not t.get("image")]
    share = len(text_only) / max(1, len(ring))
    checks.append(_check("text_only_share", share <= 0.30 + 1e-9, round(share, 3), "<= 0.30"))
    lo_n, hi_n = bs.count_limits(spec["canvas"]["use"], css_w, css_h)
    lo_t, hi_t = bs.count_range(spec["canvas"]["use"], css_w, css_h)
    n = len(spec["tiles"])
    if lo_n <= n < lo_t:
        warnings.append("格数 %d 少于这个画幅常见的 %d–%d，每格会比苹果的空一些" % (n, lo_t, hi_t))
    elif hi_t < n <= hi_n:
        warnings.append("格数 %d 多于这个画幅常见的 %d–%d，格子会挤" % (n, lo_t, hi_t))
    checks.append(_check("tile_count", lo_n <= n <= hi_n, n, "%d–%d (usual %d–%d)" % (lo_n, hi_n, lo_t, hi_t)))
    small = ["%s %.1fu×%.1fu" % (t["id"], t["rect"][2] / u, t["rect"][3] / u) for t in dom["tiles"]
             if t["rect"][2] < bs.RATIOS["min_tile_w"] * u - 0.5 or t["rect"][3] < bs.RATIOS["min_tile_h"] * u - 0.5]
    checks.append(_check("min_tile", not small, len(small), ">= 6u × 4.8u", small or None))

    # pictures blown up beyond their pixels
    worst_up, ups = 0.0, []
    for im in dom.get("images", []):
        nw, nh = im["natural"]
        rw, rh = im["rect"][2], im["rect"][3]
        if not nw or not nh or not rw or not rh:
            continue
        scale = (max(rw / nw, rh / nh) if im["fit"] == "cover" else
                 min(rw / nw, rh / nh) if im["fit"] == "contain" else rw / nw) * dpr
        worst_up = max(worst_up, scale)
        if scale > 1.25:
            ups.append("%s %.2f×" % (im["tile"], scale))
    if ups:
        warnings.append("图片被放大超过 1.25 倍，会糊：" + "、".join(ups))
    checks.append(_check("image_upscale", True, round(worst_up, 2), "warn > 1.25", ups or None))

    # output size
    if png_path and Path(png_path).exists():
        with Image.open(png_path) as im:
            size = list(im.size)
        want = [spec["canvas"]["width"], spec["canvas"]["height"]]
        checks.append(_check("output_size", size == want, size, "%d×%d" % tuple(want)))

    # Han characters touching Latin letters or digits
    spacing = []
    if lang == "zh-CN":
        for t in spec["tiles"]:
            for field in ("label", "word"):
                for pair in bs.cjk_spacing_problems(t.get(field) or ""):
                    spacing.append("%s「%s」" % (t["id"], pair))
    checks.append(_check("cjk_spacing", not spacing, len(spacing), "space between Han and Latin/digits",
                         spacing or None))

    return {"schema": "bento-qa/1", "pass": all(c["pass"] for c in checks), "checks": checks,
            "fonts": counts, "warnings": warnings}


# ---------------------------------------------------------------- background sampling for contrast

def _load(path):
    if not path or not Path(path).exists():
        return None
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def _backgrounds(text: dict, tile: dict | None, tile_spec: dict | None, textless, dpr: int, tok: dict) -> list:
    """Colours behind a piece of text: the tile colour(s), or the photo pixels under it (worst 10%)."""
    if tile is None:
        return [parse_color(tok["canvas"])]
    over_picture = tile_spec and (tile_spec["kind"] == "photo" or
                                  (tile_spec["kind"] in ("word", "stat", "hero") and tile_spec.get("image")
                                   and tile_spec.get("fit") == "cover"))
    if over_picture and textless is not None and text.get("ink"):
        x, y, w, h = [v * dpr for v in text["ink"]]
        sub = textless[int(max(0, y)):int(y + h), int(max(0, x)):int(x + w)]
        if sub.size:
            lum = sub @ np.array([0.2126, 0.7152, 0.0722])
            light_text = rel_luminance(parse_color(text["color"])) > 0.5
            q = np.percentile(lum, 90 if light_text else 10)
            idx = np.unravel_index(np.argmin(np.abs(lum - q)), lum.shape)
            return [tuple(sub[idx])]
    bgs = []
    image = tile.get("background_image") or ""
    for m in re.findall(r"rgba?\([^)]*\)", image):
        bgs.append(parse_color(m))
    if not bgs:
        bgs.append(parse_color(tile.get("background") or tok["tile"]))
    return bgs


def summary(qa: dict) -> str:
    bad = [c for c in qa["checks"] if not c["pass"]]
    if not bad:
        head = "QA 通过（%d 项）" % len(qa["checks"])
    else:
        head = "QA 没通过：" + "；".join("%s %s" % (c["id"], c.get("where") or c["value"]) for c in bad)
    if qa["warnings"]:
        head += "\n提醒：" + "；".join(qa["warnings"])
    return head
