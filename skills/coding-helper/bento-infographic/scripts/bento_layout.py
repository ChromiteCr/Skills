#!/usr/bin/env python3
"""排版器：主图放在正中，外圈切成格子，再把内容分进去。

结构照苹果的总结片（AUDIT-AND-IDEAS.md 4.2、4.3）：
- 画布切成接近正方形的小格（每格连格缝约 1.45u），行列都取 4 的倍数；
- 主图居中，默认占 1 : 2 : 1 切分的中间块；
- 外圈是上带、下带、左栏、右栏，四个角各归带或归栏（16 种组合）；
- 每一条沿长度切成几段，段可以再沿厚度一分为二（5G 与 C1 那样并排）；
- 内容用匈牙利算法分进格子；跑几百个种子打分，留结构不同的前几个。
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

import bento_spec as bs

PITCH_U = 1.45                 # 小格连格缝的边长，单位 u
SEED_TRIES = 500
TEXT_W = {"cjk": 1.0, "latin": 0.55}


# ---------------------------------------------------------------- geometry helpers

def m4(x: float, lo: int = 8) -> int:
    return max(lo, int(round(x / 4.0)) * 4)


def nearest_even(x: float) -> int:
    return max(2, int(round(x / 2.0)) * 2)


def grid_for(css_w: float, css_h: float, u: float) -> tuple[int, int]:
    return m4(css_w / (PITCH_U * u)), m4(css_h / (PITCH_U * u))


def pitches(tok: dict, cols: int, rows: int) -> tuple[float, float]:
    """Cell pitch (cell + gutter) in CSS px. The bottom margin is taller when there is a source line."""
    g, m = tok["gutter"], tok["margin"]
    mb = tok.get("margin_bottom", m)
    return (tok["css_w"] - 2 * m + g) / cols, (tok["css_h"] - m - mb + g) / rows


def span_px(n: int, pitch: float, gutter: float) -> float:
    return n * pitch - gutter


def cells_for(px: float, pitch: float, gutter: float) -> float:
    return (px + gutter) / pitch


def rect_px(rect, tok: dict, px: float, py: float) -> tuple[float, float, float, float]:
    c, r, w, h = rect
    g, m = tok["gutter"], tok["margin"]
    return m + c * px, m + r * py, span_px(w, px, g), span_px(h, py, g)


# ---------------------------------------------------------------- hero

def hero_box_aspect(hero: dict) -> float | None:
    """Desired hero box aspect (w/h). Product pictures get 25% room around them."""
    if hero.get("box_aspect"):
        return float(hero["box_aspect"])
    a = hero.get("_img_aspect")
    if a and hero.get("fit", "contain") != "cover":
        return a * 1.25
    return None


def place_hero(cols: int, rows: int, hero: dict, tok: dict) -> tuple[int, int, int, int]:
    px, py = pitches(tok, cols, rows)
    g = tok["gutter"]
    canvas_aspect = tok["css_w"] / tok["css_h"]
    if hero.get("word") and not hero.get("image") and not hero.get("box_aspect"):
        # Apple's word hero (iOS 18) is 39% × 32% of a 16:9 canvas; on narrow canvases it must still
        # hold the word at 5u with room around it.
        w, h = nearest_even(0.39 * cols), nearest_even(0.32 * rows)
        need_w = text_u(hero["word"]) * bs.RATIOS["hero_word_min"] * tok["u"] + 4 * tok["u"]
        need_h = bs.RATIOS["hero_word_min"] * tok["u"] + 4 * tok["u"]
        w = min(cols, max(w, nearest_even(cells_for(need_w, px, g) + 0.49)))
        h = min(rows, max(h, nearest_even(cells_for(need_h, py, g) + 0.49)))
        return (cols - w) // 2, (rows - h) // 2, w, h
    aspect = hero_box_aspect(hero)
    wide = (hero.get("box_aspect") or hero.get("_img_aspect") or 0) > 1.3
    w, h = cols // 2, rows // 2
    if aspect:
        default_aspect = span_px(w, px, g) / span_px(h, py, g)
        if canvas_aspect < 1 and wide:
            # Portrait canvas, wide picture: a full-width hero band.
            w = cols
            h_px = (tok["css_w"] - 2 * tok["margin"]) / aspect
            h = min(nearest_even(cells_for(h_px, py, g)), rows // 2 + (rows // 2) % 2)
        elif aspect < default_aspect:
            if aspect < 0.75:
                h = min(nearest_even(0.64 * rows), rows - 8)
            w_px = aspect * span_px(h, py, g)
            w = nearest_even(cells_for(w_px, px, g))
            w = max(w, nearest_even(0.28 * cols) if aspect < 0.75 else nearest_even(0.35 * cols))
            w = min(w, cols // 2)
    if (cols - w) % 2:
        w -= 1
    if (rows - h) % 2:
        h -= 1
    return (cols - w) // 2, (rows - h) // 2, w, h


# ---------------------------------------------------------------- ring strips

CORNERS = ("tl", "tr", "bl", "br")


def strips_for(cols: int, rows: int, hero, pattern: dict) -> list[dict]:
    """pattern[corner] is 'band' (the top/bottom band owns that corner) or 'column'."""
    c0, r0, w, h = hero
    c1, r1 = c0 + w, r0 + h
    out = []
    if r0 > 0:
        x0 = 0 if pattern["tl"] == "band" else c0
        x1 = cols if pattern["tr"] == "band" else c1
        out.append({"name": "top", "dir": "h", "x": x0, "y": 0, "len": x1 - x0, "thick": r0})
    if rows - r1 > 0:
        x0 = 0 if pattern["bl"] == "band" else c0
        x1 = cols if pattern["br"] == "band" else c1
        out.append({"name": "bottom", "dir": "h", "x": x0, "y": r1, "len": x1 - x0, "thick": rows - r1})
    if c0 > 0:
        y0 = 0 if pattern["tl"] == "column" else r0
        y1 = rows if pattern["bl"] == "column" else r1
        out.append({"name": "left", "dir": "v", "x": 0, "y": y0, "len": y1 - y0, "thick": c0})
    if cols - c1 > 0:
        y0 = 0 if pattern["tr"] == "column" else r0
        y1 = rows if pattern["br"] == "column" else r1
        out.append({"name": "right", "dir": "v", "x": c1, "y": y0, "len": y1 - y0, "thick": cols - c1})
    return [s for s in out if s["len"] > 0 and s["thick"] > 0]


def _composition(rng: random.Random, total: int, n: int, lo: int) -> list[int] | None:
    """n integers >= lo summing to total, randomly spread."""
    extra = total - n * lo
    if n <= 0 or extra < 0:
        return None
    weights = [rng.random() ** 1.3 + 0.15 for _ in range(n)]
    s = sum(weights)
    parts = [lo + int(extra * w / s) for w in weights]
    for i in rng.sample(range(n), total - sum(parts)):
        parts[i] += 1
    return parts


def _strip_tiles(rng: random.Random, strip: dict, k: int, mins: dict) -> list[tuple] | None:
    """Cut one strip into k tiles. Returns rects (c, r, w, h)."""
    along_min = mins["w"] if strip["dir"] == "h" else mins["h"]
    across_min = mins["h"] if strip["dir"] == "h" else mins["w"]
    max_segments = strip["len"] // along_min
    splittable = strip["thick"] >= 2 * across_min
    lo_split = max(0, k - max_segments)
    hi_split = (k // 2) if splittable else 0
    if lo_split > hi_split:
        return None
    # Splits are the exception in Apple's slides (one or two per slide), except in a band much thicker than a
    # tile is tall: iOS 18's word hero leaves bands a third of the canvas high, cut into two rows of short tiles.
    thick = strip["thick"] >= 2.6 * across_min
    splits = lo_split if rng.random() < (0.3 if thick else 0.7) else rng.randint(lo_split, hi_split)
    n = k - splits
    if n < 1:
        return None
    lengths = _composition(rng, strip["len"], n, along_min)
    if lengths is None:
        return None
    split_idx = set(rng.sample(range(n), splits))
    rects = []
    pos = 0
    for i, L in enumerate(lengths):
        if i in split_idx:
            a = rng.randint(across_min, strip["thick"] - across_min)
            parts = [(0, a), (a, strip["thick"] - a)]
        else:
            parts = [(0, strip["thick"])]
        for off, t in parts:
            if strip["dir"] == "h":
                rects.append((strip["x"] + pos, strip["y"] + off, L, t))
            else:
                rects.append((strip["x"] + off, strip["y"] + pos, t, L))
        pos += L
    return rects


def _capacity(strip: dict, mins: dict) -> int:
    along_min = mins["w"] if strip["dir"] == "h" else mins["h"]
    across_min = mins["h"] if strip["dir"] == "h" else mins["w"]
    segs = strip["len"] // along_min
    return segs * (2 if strip["thick"] >= 2 * across_min else 1)


def fill_ring(cols: int, rows: int, hero, k: int, mins: dict, rng: random.Random):
    """One random ring with exactly k tiles, or None. Returns (rects, pattern)."""
    pattern = {c: rng.choice(("band", "column")) for c in CORNERS}
    strips = strips_for(cols, rows, hero, pattern)
    caps = [_capacity(s, mins) for s in strips]
    if not strips or sum(caps) < k or len(strips) > k:
        return None
    # Allocate tiles to strips roughly by area, at least one each.
    areas = [s["len"] * s["thick"] for s in strips]
    alloc = [1] * len(strips)
    for _ in range(k - len(strips)):
        open_idx = [i for i in range(len(strips)) if alloc[i] < caps[i]]
        if not open_idx:
            return None
        wts = [areas[i] / alloc[i] * (0.6 + rng.random()) for i in open_idx]
        alloc[open_idx[int(np.argmax(wts))]] += 1
    rects = []
    for s, n in zip(strips, alloc):
        r = _strip_tiles(rng, s, n, mins)
        if r is None:
            return None
        rects.extend(r)
    return rects, pattern


# ---------------------------------------------------------------- checks and score

def coverage_ok(rects, cols: int, rows: int) -> bool:
    occ = np.zeros((rows, cols), dtype=np.int16)
    for c, r, w, h in rects:
        if c < 0 or r < 0 or c + w > cols or r + h > rows:
            return False
        occ[r:r + h, c:c + w] += 1
    return bool((occ == 1).all())


def through_seams(rects, cols: int, rows: int) -> int:
    """Grid lines (not the canvas edge) that cross the whole canvas without cutting a tile."""
    count = 0
    for x in range(1, cols):
        if all(not (c < x < c + w) for c, r, w, h in rects):
            count += 1
    for y in range(1, rows):
        if all(not (r < y < r + h) for c, r, w, h in rects):
            count += 1
    return count


def tile_aspect(rect, tok, px, py) -> float:
    _, _, w, h = rect_px(rect, tok, px, py)
    return w / h


def layout_penalty(rects, hero, cols, rows, tok, px, py, rng_tie: float = 0.0) -> float | None:
    """Structural score (lower is better); None when a hard rule is broken."""
    u = tok["u"]
    pen = 0.0
    for rect in rects:
        a = tile_aspect(rect, tok, px, py)
        if a > bs.RATIOS["max_aspect"] or a < 1 / bs.RATIOS["max_aspect"]:
            return None
        if a > 3.0 or a < 1 / 3.0:
            pen += 1.5
    if through_seams(rects + [hero], cols, rows) > 2:
        return None
    # Monotony: neighbours in the same strip with the same span.
    spans = {}
    for c, r, w, h in rects:
        spans.setdefault((w, h), 0)
        spans[(w, h)] += 1
    smallest = min(spans, key=lambda s: s[0] * s[1])
    if spans[smallest] / len(rects) > 0.30:
        pen += 2.0
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            same_row = a[1] == b[1] and a[3] == b[3] and (a[0] + a[2] == b[0] or b[0] + b[2] == a[0])
            same_col = a[0] == b[0] and a[2] == b[2] and (a[1] + a[3] == b[1] or b[1] + b[3] == a[1])
            if (same_row and a[2] == b[2]) or (same_col and a[3] == b[3]):
                pen += 1.0                     # round 10 review: a column cut 250 / 250 / 250 reads as a table
    # Four or more tiles in a row (or a column) growing or shrinking step by step look arranged, not cut.
    groups: dict = {}
    for c, r, w, h in rects:
        groups.setdefault(("row", r, h), []).append((c, w))
        groups.setdefault(("col", c, w), []).append((r, h))
    for items in groups.values():
        if len(items) >= 4:
            sizes = [s for _, s in sorted(items)]
            steps = [b - a for a, b in zip(sizes, sizes[1:])]
            if all(d > 0 for d in steps) or all(d < 0 for d in steps):
                pen += 1.0
    # Bands of tall tiles: in Apple's slides a tile in the top or bottom band is at most about a quarter of the
    # canvas high (samples 3–6: 15–24%); thicker bands are cut into two rows (round 10 review).
    stage_h = tok["css_h"] - tok["margin"] - tok.get("margin_bottom", tok["margin"])
    for rect in rects:
        if (rect[1] == 0 or rect[1] + rect[3] == rows) and rect_px(rect, tok, px, py)[3] > 0.27 * stage_h:
            pen += 1.0
    # Near misses: two tile edges 0 < d < 1u apart are worse than a clear offset.
    boxes = [rect_px(r, tok, px, py) for r in rects]
    for edges in ({b[0] for b in boxes} | {b[0] + b[2] for b in boxes}, {b[1] for b in boxes} | {b[1] + b[3] for b in boxes}):
        xs = sorted(edges)
        for a, b in zip(xs, xs[1:]):
            if 0.5 < b - a < u:
                pen += 0.4
    return pen + rng_tie


# ---------------------------------------------------------------- assignment

def text_u(text: str, cjk_scale: float = 1.0) -> float:
    """Width in em of text at weight 600, measured with the real fonts (SF Pro, PingFang) when present."""
    import bento_render
    return bento_render.text_em(text, cjk_scale)


def _lab(t: dict) -> str | None:
    """The label as drawn (research numbers add an n / condition line; prepare() fills _label)."""
    return t["_label"] if "_label" in t else t.get("label")


def _label_width_u(label: str | None) -> float:
    if not label:
        return 0.0
    return max((text_u(ln) for ln in bs.label_lines(label)), default=0.0)


def _text_block_u(t: dict) -> tuple[float, float]:
    """Rough width and height in u of the tile's main text (number, word or label)."""
    if t["kind"] == "stat":
        import bento_render
        size = bs.RATIOS["number_max"] if int(t.get("weight", 1)) >= 3 and not t.get("image") else bs.RATIOS["number"]
        w = bento_render._number_parts(t)[1] * size
        h = size + len(bs.label_lines(_lab(t))) * 1.25
        return max(w, _label_width_u(_lab(t))), h
    if t["kind"] == "word":
        lines = bs.label_lines(t.get("word")) or [t.get("word", "")]
        size = bs.WORD_SIZES.get(int(t.get("weight", 1)), 1.75)
        w = max(text_u(ln) for ln in lines) * size
        h = len(lines) * size * 1.1 + len(bs.label_lines(_lab(t))) * 1.25
        return w, h
    return _label_width_u(_lab(t)), len(bs.label_lines(_lab(t))) * 1.25


def min_width_u(t: dict) -> float:
    """The narrowest tile (in u) the content can live in at its smallest allowed size."""
    kind = t["kind"]
    need = _label_width_u(_lab(t)) + 2 * bs.RATIOS["pad"] if _lab(t) else 0.0
    if kind == "flank":
        side = max(text_u(str(t.get("left", ""))), text_u(str(t.get("right", "")))) * bs.RATIOS["word"]
        need = max(need, 2 * side + 2 * 1.0 + 2 * 0.6 + 4.0)      # two values, gaps, a picture at least 4u wide
    if kind == "row":
        items = t.get("items") or []
        text = sum(text_u(str(i)) * 1.4 for i in items if not str(i).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")))
        pics = 4.0 * sum(1 for i in items if str(i).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")))
        need = max(need, text + pics + (len(items) + 1) * 1.0)
    if kind == "stat":
        import bento_render                # the number at its smallest size still fits across
        need = max(need, bento_render._number_parts(t)[1] * bs.RATIOS["number_min"] + 2 * bs.WORD_PAD)
    if kind in ("word", "stat") and t.get("image") and t.get("fit", "contain") != "cover":
        tw, _ = _text_block_u(t)
        scale = (1.6 / bs.WORD_SIZES.get(int(t.get("weight", 1)), 1.75)) if kind == "word" else (2.2 / 3.2)
        share = 0.56 if kind == "word" else 0.46
        need = max(need, (tw * scale + 2 * bs.WORD_PAD) / share)
    return need


def min_height_u(t: dict) -> float:
    """The shortest tile (in u) the content fits: only a line or two of words may go down to 4.8u."""
    kind = t["kind"]
    lab = len(bs.label_lines(_lab(t))) * 1.25
    insets = 2 * 0.95
    if kind == "icon":
        return float(t.get("icon_size", bs.RATIOS["icon"])) + 0.5 + lab + insets
    if kind in ("photo", "object", "ui", "flank", "row", "chart"):
        return max(7.0, lab + insets + 3.0)
    if kind == "stat":
        return 2.2 + lab + insets + (3.0 if t.get("image") and t.get("fit", "contain") == "cover" else 0.0)
    if kind == "word":
        lines = len(bs.label_lines(t.get("word"))) or 1
        return max(bs.RATIOS["min_tile_h"], lines * 1.6 * 1.1 + lab + insets)
    return bs.RATIOS["min_tile_h"]


FILL_RATIO = 2.0     # a text or icon tile up to twice the area of its content costs nothing (Apple: 1.1–2.4)
FILL_COST = 2.0      # per e-fold beyond that


def content_area_u(t: dict, wu: float, hu: float) -> float:
    """Area in u² of what a text or icon tile holds, with the usual clearances: 1u each side of the words,
    0.95u above and below. An icon grows with its tile (46% of the width, 3.5–9u), so its share is
    measured at the size it would be drawn in this tile."""
    if t["kind"] == "icon":
        lab = len(bs.label_lines(_lab(t))) * 1.25
        side = float(t["icon_size"]) if t.get("icon_size") is not None else \
            min(max(bs.RATIOS["icon_fill"] * wu, bs.RATIOS["icon"]), bs.RATIOS["icon_max"])
        side = max(2.0, min(side, hu - 1.0 - 0.95 - lab - 0.5, wu - 2.0))
        return (max(side, _label_width_u(_lab(t))) + 2 * bs.RATIOS["pad"]) * (side + 0.5 + lab + 2 * 0.95)
    tw, th = _text_block_u(t)
    return (tw + 2 * bs.WORD_PAD) * (th + 2 * 0.95)


def preferred_aspect(t: dict) -> tuple[float, float]:
    """(preferred tile aspect w/h, weight of the preference)."""
    kind = t["kind"]
    img = t.get("_img_aspect")
    if kind == "photo":
        return (img or 1.3), 0.5
    if kind == "object":
        return ((img or 1.3) * 0.85), 1.0
    if kind == "ui":
        # A phone screen runs off the tile edge in any squarish tile; a wide screenshot needs a wide tile
        # to keep its full width (bento_render.UI_BLEED_MIN).
        if img and img > 1.0:
            # Shown whole (fit contain), a screenshot only fills its tile when the tile has its proportions:
            # Apple's fill 81–84% of the tile width, ours filled 45–61% in tiles twice as wide (round 10, review 5).
            return img * 0.9, (1.6 if t.get("fit") == "contain" else 0.9)
        if img and t.get("fit") == "contain":
            return max(0.6, img * 0.9), 1.6
        return 1.0, 0.4
    if kind == "icon":
        return 1.0, 0.7
    if kind == "row":
        return 2.6, 1.0
    if kind == "flank":
        return 1.7, 0.8
    if kind == "chart":
        return 1.5, 0.6
    tw, th = _text_block_u(t)
    if kind == "stat" and t.get("image"):
        return 1.9, 0.6
    if kind == "word" and t.get("image"):
        return 2.0, 0.6
    return max(0.8, min(2.4, (tw + 2.4) / (th + 2.0))), 1.0


def assign(tiles: list[dict], rects: list[tuple], tok: dict, px: float, py: float):
    """Hungarian assignment of content to rects. Returns (mapping id -> rect, cost) or (None, inf)."""
    u = tok["u"]
    n = len(tiles)
    areas = [rect_px(r, tok, px, py)[2] * rect_px(r, tok, px, py)[3] for r in rects]
    order = np.argsort(-np.array(areas))
    rank = np.empty(n)
    rank[order] = np.arange(n) / max(1, n - 1)            # 0 = largest
    cost = np.zeros((n, n))
    min_w = [min_width_u(t) for t in tiles]
    min_h = [min_height_u(t) for t in tiles]
    for i, t in enumerate(tiles):
        pref, pw = preferred_aspect(t)
        label_w = _label_width_u(_lab(t))
        text_w, text_h = _text_block_u(t)
        wgt = int(t.get("weight", 1))
        for j, rect in enumerate(rects):
            x, y, w, h = rect_px(rect, tok, px, py)
            wu, hu = w / u, h / u
            c = pw * abs(math.log((w / h) / pref))
            if wgt >= 3 and not text_only(t):
                c += 3.0 * max(0.0, rank[j] - 0.2)
            elif wgt >= 2:
                # Weight 3 on a number or a word means bigger type, not a bigger tile: Apple's largest feature
                # name (Vapor chamber, 2.6u) sits in a middle-sized tile, and a big tile around a few words is empty.
                c += 1.2 * abs(rank[j] - 0.35)
            else:
                c += 0.8 * max(0.0, 0.45 - rank[j])
            if label_w and label_w + 2 * bs.RATIOS["pad"] > wu:
                c += 50.0
            if min_w[i] > wu or min_h[i] > hu:
                c += 50.0
            if t["kind"] in ("stat", "word") and not t.get("image"):
                num = bs.RATIOS["number_max"] if wgt >= 3 else bs.RATIOS["number"]
                min_scale = (bs.RATIOS["number_min"] / num) if t["kind"] == "stat" else (1.6 / bs.WORD_SIZES.get(wgt, 1.75))
                if text_w * min_scale + 2 * bs.WORD_PAD > wu or text_h * min_scale + 2 * 0.95 > hu:
                    c += 50.0
            if t["kind"] == "stat" and (rect[0] == 0 or rect[1] == 0):
                c -= 0.15
            side_image = t["kind"] in ("word", "stat") and t.get("image") and t.get("fit", "contain") != "cover"
            if side_image and w / h < 1.4 and t["kind"] == "word":
                c += 50.0                       # picture beside the words needs a wide tile
            if t["kind"] == "flank" and w / h < 1.2:
                c += 50.0
            if t["kind"] == "stat" and t.get("image") and t.get("fit") == "cover" and w / h < 1.4:
                # Number on top, photo underneath: the photo must not shrink to a strip.
                img_u = hu - 0.95 - min(3.2, 0.35 * hu) - len(bs.label_lines(_lab(t))) * 1.3 - 0.5
                if img_u < max(4.5, 0.35 * hu):
                    c += 50.0
            if t["kind"] == "ui" and t.get("_img_aspect") and not t.get("fit"):
                lab_u = len(bs.label_lines(_lab(t))) * 1.3 + 0.95 + 0.5
                area = (wu - 2.4) / max(1.0, hu - lab_u)
                if area < 0.9 * t["_img_aspect"]:
                    c += 2.0                     # the screen would have to shrink to fit whole
            if text_only(t) and wgt < 3:
                c += 1.0 * max(0.0, 0.4 - rank[j])   # a few words do not fill one of the biggest tiles
            if text_only(t) or t["kind"] == "icon":
                # Nor float in a mostly empty one: Apple's text and icon tiles are 1.1–2.4 times the area of what
                # they hold (Genlock 1.6, 5G 1.6, Locked and Hidden apps 1.6, Apple Intelligence 1.7–2.4; Game Mode
                # 1.1, the battery 1.4, Satellite services 2.0). Round 10, review 4 measured ours at 3.5–7.
                c += FILL_COST * max(0.0, math.log((wu * hu) / (FILL_RATIO * content_area_u(t, wu, hu))))
            if (text_only(t) or t["kind"] == "icon") and rect[1] == 0:
                c += 0.6       # Apple's top bands lead with pictures: five of samples 1–6 have at most one text or icon tile there
            if text_only(t) and w / h < 0.7:
                c += 1.0       # the narrowest text tile in samples 1–6 is 5G at 0.71; a number in a slit reads as a gap
            if t["kind"] == "photo":
                c += 0.5 * rank[j]                   # photographs earn the larger tiles
            if t["kind"] == "icon":
                c += 0.6 * max(0.0, 0.5 - rank[j])   # an icon alone looks lost in a big tile
            cost[i, j] = c
    rows_i, cols_j = linear_sum_assignment(cost)
    total = float(cost[rows_i, cols_j].sum())
    mapping = {tiles[i]["id"]: rects[j] for i, j in zip(rows_i, cols_j)}
    return mapping, total


def same_kind_runs(tiles: list[dict], mapping: dict) -> float:
    """Three or more tiles of the same kind side by side in a band read as a list, not a bento."""
    by_id = {t["id"]: t for t in tiles}
    rows: dict[tuple, list] = {}
    for tid, (c, r, w, h) in mapping.items():
        rows.setdefault((r, h), []).append((c, w, by_id[tid]["kind"]))
    pen = 0.0
    for items in rows.values():
        items.sort()
        run = 1
        for (c0, w0, k0), (c1, w1, k1) in zip(items, items[1:]):
            run = run + 1 if (k1 == k0 and c1 == c0 + w0) else 1
            if run >= 3:
                pen += 1.5
    return pen


def text_only(t: dict) -> bool:
    return t["kind"] in bs.TEXT_ONLY_KINDS and not t.get("image")


def adjacency_penalty(tiles: list[dict], mapping: dict) -> float:
    by_id = {t["id"]: t for t in tiles}
    ids = [i for i in mapping if text_only(by_id[i])]
    pen = 0.0
    for i, a_id in enumerate(ids):
        a = mapping[a_id]
        for b_id in ids[i + 1:]:
            b = mapping[b_id]
            touch_x = (a[0] + a[2] == b[0] or b[0] + b[2] == a[0]) and min(a[1] + a[3], b[1] + b[3]) > max(a[1], b[1])
            touch_y = (a[1] + a[3] == b[1] or b[1] + b[3] == a[1]) and min(a[0] + a[2], b[0] + b[2]) > max(a[0], b[0])
            if touch_x or touch_y:
                pen += 2.0
    return pen


# ---------------------------------------------------------------- candidates

def _image_aspect(path: Path) -> float | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size[0] / im.size[1]
    except Exception:
        return None


def _image_dark(path: Path) -> bool:
    """A picture that reads as a dark block on a light slide: mean relative luminance under 0.12."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(path) as im:
            a = np.asarray(im.convert("RGB").resize((64, 64)), dtype=np.float64) / 255.0
    except Exception:
        return False
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return float((lin @ np.array([0.2126, 0.7152, 0.0722])).mean()) < 0.12


def dark_bands(tiles: list[dict], mapping: dict, rows: int, theme: str) -> float:
    """On a light slide, dark tiles spread out: Apple's light samples have at most one dark tile in the top or
    the bottom band (iOS 18: Messages via satellite on top; iPhone Duo: Nano-texture on top, Grade 5 titanium
    at the bottom). Round 10, review 5: three black cards and a night photo made our top band heavy."""
    if theme == "dark":
        return 0.0
    by_id = {t["id"]: t for t in tiles}
    pen = 0.0
    for edge in ("top", "bottom"):
        n = 0
        for tid, (c, r, w, h) in mapping.items():
            t = by_id[tid]
            if (r == 0 if edge == "top" else r + h == rows) and t.get("kind") != "hero" and t.get("_img_dark"):
                n += 1
        pen += 1.0 * max(0, n - 1)
    return pen


def prepare(spec: dict, base_dir=None) -> tuple[dict, list[dict], dict]:
    """Tokens, tiles (with image aspects), minimum tile spans in cells."""
    tok = bs.tokens_for(spec)
    base = Path(base_dir) if base_dir else None
    tiles = []
    for t in spec["tiles"]:
        t = dict(t)
        t["_label"] = bs.display_label(t, spec.get("lang", "zh-CN"))
        if t.get("image") and base is not None:
            t["_img_aspect"] = _image_aspect(base / t["image"])
            t["_img_dark"] = _image_dark(base / t["image"])
        tiles.append(t)
    return tok, tiles, {}


def candidates(spec: dict, n: int = 3, seeds: int = SEED_TRIES, base_dir=None, seed0: int | None = None) -> list[dict]:
    tok, tiles, _ = prepare(spec, base_dir)
    cols, rows = grid_for(tok["css_w"], tok["css_h"], tok["u"])
    px, py = pitches(tok, cols, rows)
    g = tok["gutter"]
    mins = {"w": math.ceil(cells_for(bs.RATIOS["min_tile_w"] * tok["u"], px, g) - 1e-9),
            "h": math.ceil(cells_for(bs.RATIOS["min_tile_h"] * tok["u"], py, g) - 1e-9)}
    hero_t = next(t for t in tiles if t["kind"] == "hero")
    ring_tiles = [t for t in tiles if t["kind"] != "hero"]
    hero = place_hero(cols, rows, hero_t, tok)
    k = len(ring_tiles)
    base_seed = spec.get("seed", 0) if seed0 is None else seed0
    found = {}
    for s in range(seeds):
        rng = random.Random(base_seed * 100003 + s)
        res = fill_ring(cols, rows, hero, k, mins, rng)
        if res is None:
            continue
        rects, pattern = res
        if not coverage_ok(rects + [hero], cols, rows):
            continue
        pen = layout_penalty(rects, hero, cols, rows, tok, px, py)
        if pen is None:
            continue
        mapping, acost = assign(ring_tiles, rects, tok, px, py)
        if mapping is None or acost >= 50:
            continue
        score = (pen + acost + adjacency_penalty(ring_tiles, mapping) + same_kind_runs(ring_tiles, mapping)
                 + dark_bands(ring_tiles, mapping, rows, spec.get("theme", "light")))
        sig = ("".join(pattern[c][0] for c in CORNERS), tuple(sorted((r[2], r[3]) for r in rects)))
        if sig not in found or score < found[sig]["score"]:
            cells = {hero_t["id"]: list(hero)}
            cells.update({tid: list(r) for tid, r in mapping.items()})
            found[sig] = {"schema": "bento-layout/1", "grid": {"cols": cols, "rows": rows},
                          "seed": base_seed * 100003 + s, "score": round(score, 3),
                          "pattern": {c: pattern[c] for c in CORNERS}, "cells": cells}
    ranked = sorted(found.values(), key=lambda d: (d["score"], d["seed"]))
    return ranked[:n]


# ---------------------------------------------------------------- wireframe

def wireframe(spec: dict, layout: dict, png_path, width: int = 1600) -> Path:
    """Grey boxes with tile ids: a quick look at a layout before rendering."""
    from PIL import Image, ImageDraw
    css_w, css_h, _ = bs.canvas_css(spec)
    tok, tiles, _ = prepare(spec)
    cols, rows = layout["grid"]["cols"], layout["grid"]["rows"]
    px, py = pitches(tok, cols, rows)
    scale = width / css_w
    im = Image.new("RGB", (width, round(css_h * scale)), tok["canvas"])
    d = ImageDraw.Draw(im)
    kinds = {t["id"]: t["kind"] for t in tiles}
    for tid, rect in layout["cells"].items():
        x, y, w, h = rect_px(rect, tok, px, py)
        box = [x * scale, y * scale, (x + w) * scale, (y + h) * scale]
        fill = "#c9c9cc" if kinds.get(tid) == "hero" else ("#d8d8db" if tok["theme"] != "dark" else "#2a2a2c")
        d.rounded_rectangle(box, radius=tok["radius"] * scale, fill=fill)
        d.text((box[0] + 8, box[1] + 6), "%s\n%s" % (tid, kinds.get(tid, "")),
               fill="#000000" if tok["theme"] != "dark" else "#ffffff")
    im.save(png_path)
    return Path(png_path)
