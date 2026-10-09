#!/usr/bin/env python3
"""把 bento.json 和 layout.json 变成单文件 HTML，再交给本机 Chrome 渲染成 PNG。

build_html      生成 HTML（尺寸全部来自 bento_spec.tokens）
screenshot_cli  命令行无头截图，后备用：等不了字体，也量不了页面
"""
from __future__ import annotations

import html
import math
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import bento_spec as bs

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TEMPLATE = SKILL / "templates" / "bento.html"
ICONS = SKILL / "assets" / "icons"
MAC_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def find_chrome() -> Path:
    """Google Chrome: $BENTO_CHROME first, then the macOS app, then google-chrome / chromium on PATH."""
    if os.environ.get("BENTO_CHROME"):
        return Path(os.environ["BENTO_CHROME"])
    if MAC_CHROME.exists():
        return MAC_CHROME
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        hit = shutil.which(name)
        if hit:
            return Path(hit)
    return MAC_CHROME


CHROME = find_chrome()
PINGFANG_GLOB = "/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc"

GAP = 0.5          # 图与标签之间，单位 u
MEDIA_PAD = 1.0    # 实物、图标、一排、两侧标注的图离格边，单位 u
UI_BLEED_MIN = 0.9  # 界面图出格（苹果的做法）要求图区宽高比至少是截图的 0.9 倍，否则两侧切掉太多，改为整张放进去
LABEL_CONTRAST = 4.5


# ---------------------------------------------------------------- text width (for choosing sizes)

@lru_cache(maxsize=4)
def _sf(size: int = 200):
    from PIL import ImageFont
    import measure_reference as mr
    return mr.sf_font(size, bs.WEIGHT) if mr.SF_FONT.exists() else None


@lru_cache(maxsize=1)
def _pingfang(size: int = 200):
    import glob
    from PIL import ImageFont
    from fontTools.ttLib import TTCollection
    for path in glob.glob(PINGFANG_GLOB):
        try:
            coll = TTCollection(path)
            for i, f in enumerate(coll.fonts):
                if f["name"].getDebugName(4) == "PingFang SC Semibold":
                    return ImageFont.truetype(path, size, index=i)
        except Exception:
            continue
    return None


def text_em(text: str, cjk_scale: float = 1.0) -> float:
    """Width of text in em at weight 600: SF Pro for Latin, PingFang for Han (or a rough estimate)."""
    sf, pf = _sf(), _pingfang()
    total = 0.0
    run, run_cjk = "", None
    def flush(seg, cjk):
        if not seg:
            return 0.0
        if cjk:
            w = pf.getlength(seg) / 200 if pf else len(seg) * 1.0
            return w * cjk_scale
        if sf:
            return sf.getlength(seg) / 200
        return bs.display_units(seg)
    for ch in text:
        c = bs.is_cjk(ch)
        if run and c != run_cjk:
            total += flush(run, run_cjk)
            run = ""
        run += ch
        run_cjk = c
    total += flush(run, run_cjk)
    return total


# ---------------------------------------------------------------- geometry

def grid_tracks(tok: dict, cols: int, rows: int) -> tuple[float, float]:
    tw = (tok["css_w"] - 2 * tok["margin"] - (cols - 1) * tok["gutter"]) / cols
    th = (tok["css_h"] - tok["margin"] - tok.get("margin_bottom", tok["margin"]) - (rows - 1) * tok["gutter"]) / rows
    return tw, th


def tile_box(cell, tok: dict, tw: float, th: float) -> dict:
    c, r, w, h = cell
    g, m = tok["gutter"], tok["margin"]
    return {"x": m + c * (tw + g), "y": m + r * (th + g), "w": w * tw + (w - 1) * g, "h": h * th + (h - 1) * g}


def _px(v: float) -> str:
    return "%.2fpx" % v


# ---------------------------------------------------------------- pieces

def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _lines_html(text: str) -> str:
    return "".join('<span class="line">%s</span>' % _esc(ln) for ln in bs.label_lines(text))


def _label(text: str | None, pos: str, on_photo: bool = False) -> str:
    if not text:
        return ""
    cls = "label pos-%s%s" % (pos, " on-photo" if on_photo else "")
    return '<div class="%s">%s</div>' % (cls, _lines_html(text))


def _label_block_h(text: str | None, tok: dict) -> float:
    n = len(bs.label_lines(text))
    return n * tok["line_height"] * tok["u"]


def _unit_html(unit: str | None) -> tuple[str, str]:
    """Separator and unit markup. Latin units sit at the number's size (48MP, 3000 nits); Han units shrink."""
    if not unit:
        return "", ""
    cjk = bs.has_cjk(unit)
    tight = (not cjk) and (unit[0] in "%×x″'°" or (unit.isascii() and unit.isupper() and len(unit) <= 2))
    sep = "" if tight else " "
    cls = "unit cjk" if cjk else "unit"
    return sep, '<span class="%s">%s</span>' % (cls, _esc(unit))


def _number_parts(t: dict) -> tuple[str, float]:
    """Inner HTML of a number and its width in em. Research numbers with an uncertainty read
    "1.23 ± 0.04 s": the value full size, "± 0.04 s" at UNCERTAINTY_SCALE."""
    value, unit = str(t.get("value", "")), t.get("unit") or ""
    sep, unit_html = _unit_html(unit)
    unc = t.get("uncertainty")
    if unc not in (None, ""):
        tail = " ± %s%s%s" % (unc, sep, unit)
        return ('%s<span class="pm">%s</span>' % (_esc(value), _esc(tail)),
                text_em(value) + text_em(tail) * bs.UNCERTAINTY_SCALE)
    width = text_em(value) + text_em(sep) + (text_em(unit, bs.CJK_UNIT_SCALE) if unit else 0.0)
    return _esc(value) + _esc(sep) + unit_html, width


def _number_size(t: dict, box: dict, tok: dict, has_media: bool, cap: bool = True) -> float:
    u = tok["u"]
    _, width = _number_parts(t)
    # A big number keeps clear of the tile edges: 1.1u each side and no more than 75% of the width
    # (round 10 review: Apple's numbers never run edge to edge).
    avail_w = box["w"] - 2 * 1.1 * u
    if cap:
        avail_w = min(avail_w, 0.75 * box["w"])
    label_h = _label_block_h(bs.display_label(t, tok["lang"]), tok) + 0.05 * u
    avail_h = box["h"] - 2 * tok["inset"] - label_h
    if has_media:
        avail_h = box["h"] * 0.35
    # Apple's numbers are mostly 3.1–3.3u; only the one key number (weight 3) goes up to 4.3u. Growing every
    # number with its tile made two 4.3u numbers compete with the hero (round 10, review 4); a roomy tile is the
    # layout's problem (bento_layout.assign keeps text tiles tight), not a reason to inflate the type.
    big = (not has_media) and t.get("weight", 1) >= 3
    base = bs.RATIOS["number_max"] * u if big else bs.RATIOS["number"] * u
    size = min(base, avail_w / max(width, 0.1), avail_h)
    return max(size, bs.RATIOS["number_min"] * u)


def _descent_em(text: str) -> float:
    """How far the Latin ink of text (SF Pro, weight 600) reaches below the baseline, in em. A slash or a comma
    in a number hangs under it; the label below must clear that tail, not just the baseline (round 10: the
    tail of "5/6" came within 3 px of its label)."""
    sf = _sf()
    latin = "".join(ch for ch in str(text) if not bs.is_cjk(ch))
    if not sf or not latin.strip():
        return 0.0
    return max(0.0, sf.getbbox(latin, anchor="ls")[3] / 200)


def _num_div(t: dict, size: float, inner: str, accent: str) -> str:
    style = "font-size:%s" % _px(size)
    tail = _descent_em(t.get("value", ""))
    if tail > 0.05:                       # digits overshoot the baseline by about 0.01 em; a slash by much more
        style += ";padding-bottom:%.3fem" % tail
    return '<div class="num%s" style="%s">%s</div>' % (accent, style, inner)


def _word_size(text: str, box: dict, tok: dict, base_ratio: float, lo: float, hi: float,
               extra_h: float = 0.0, width_factor: float = 1.0, pad_u: float | None = None) -> float:
    u = tok["u"]
    lines = bs.label_lines(text) or [text]
    width = max(text_em(ln) for ln in lines) * width_factor
    avail_w = box["w"] - 2 * (pad_u * u if pad_u is not None else tok["pad"])
    avail_h = (box["h"] - 2 * tok["inset"] - extra_h) / (len(lines) * 1.1)
    size = min(base_ratio * u, avail_w / max(width, 0.1), avail_h, hi * u)
    return max(size, lo * u)


def _media(inner: str, top: float, right: float, bottom: float, left: float, fit: str = "contain",
           extra_cls: str = "") -> str:
    style = "top:%s;right:%s;bottom:%s;left:%s" % (_px(top), _px(right), _px(bottom), _px(left))
    return '<div class="media fit-%s%s" style="%s">%s</div>' % (fit, (" " + extra_cls) if extra_cls else "",
                                                                 style, inner)


def _img(src: str, focus: str | None = None) -> str:
    style = ' style="object-position:%s"' % _esc(focus) if focus else ""
    return '<img src="%s" alt=""%s>' % (_esc(src), style)


def _whole(src: str, area_w: float, area_h: float, aspect: float | None) -> str:
    """A picture shown whole inside a tile, sized explicitly so its rounded corners sit on the picture itself
    (object-fit would round the empty box around it). Every embedded picture gets the same corners
    (round 10, review 4: one square-cornered picture among rounded ones)."""
    a = aspect or (area_w / max(area_h, 1.0))
    w = min(area_w, area_h * a)
    return '<img class="screen whole" src="%s" alt="" style="width:%s;height:%s">' % (_esc(src), _px(w), _px(w / a))


CARD_ASPECT = (0.8, 2.4)    # a solid-background card is never narrower or wider than this (w ÷ h)
CARD_FILL = (0.84, 0.80)    # the picture's content fills up to 84% of the card's width, 80% of its height
CARD_ZOOM = 1.15            # …but is never drawn more than 1.15 times its plain "whole picture" size (a slide's
                            # big number must not outgrow the real numbers of the slide)
INVISIBLE_EDGE = 1.25       # an edge with less contrast than this against the tile is lost: #1c1c1e on black is 1.23,
                            # the radio card's #141117 edge 1.12 ("almost invisible", round 10, review 5)


@lru_cache(maxsize=64)
def _edge_info(img_path: str) -> tuple:
    """(median colour of the picture's outer 2% ring, whether that ring is one flat colour, the bounding box of
    everything that is not that colour in image pixels, has transparency)."""
    import numpy as np
    from PIL import Image
    with Image.open(img_path) as im:
        alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        a = np.asarray(im.convert("RGB")).astype(np.int16)
    h, w = a.shape[:2]
    k = max(2, min(h, w) // 50)
    ring = np.concatenate([a[:k].reshape(-1, 3), a[-k:].reshape(-1, 3),
                           a[:, :k].reshape(-1, 3), a[:, -k:].reshape(-1, 3)])
    med = np.median(ring, axis=0)
    flat = bool((np.abs(ring - med).max(axis=1) <= 6).mean() >= 0.98)
    bbox = None
    if flat:
        ys, xs = np.nonzero(np.abs(a - med).max(axis=2) > 24)
        if xs.size:
            bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in med), flat, bbox, alpha


def _picture(src: str, img_path: str | None, area_w: float, area_h: float, aspect: float | None, tok: dict) -> str:
    """An embedded picture (a screenshot, a slide, a formula) shown whole in the picture area of a tile.

    Round 10, review 5: such pictures took 45–61% of the tile width where Apple's take 81–84%, and black slides
    on the black tiles of the dark theme disappeared. So:
    - a picture on one flat background (a slide crop) becomes a card of that background filling the picture
      area (aspect kept within CARD_ASPECT), its content fitted to CARD_FILL of the card;
    - when that background is the tile's own colour, the card takes the theme's raised colour instead and the
      picture is blended onto it (screen on dark tiles, multiply on light ones), so its background turns into
      the card while its type and inner panels stay;
    - any other picture is shown whole at its own proportions; if its edge cannot be seen against the tile, it
      sits on a raised frame.
    All of them keep the same 0.6u corners and no outline."""
    import bento_check as bc
    if not img_path:
        return _whole(src, area_w, area_h, aspect)
    edge, flat, bbox, alpha = _edge_info(img_path)
    if alpha:
        return _whole(src, area_w, area_h, aspect)
    a = aspect or (area_w / max(area_h, 1.0))
    hidden = bc.contrast(bc.parse_color(edge), bc.parse_color(tok["tile"])) < INVISIBLE_EDGE
    u = tok["u"]
    if flat and bbox:
        card_w = min(area_w, area_h * CARD_ASPECT[1])
        card_h = min(area_h, card_w / CARD_ASPECT[0])
        size = _image_size(img_path) or (1, 1)
        iw, ih = size
        plain = min(card_w / iw, card_h / ih)
        cw, ch = bbox[2] - bbox[0], bbox[3] - bbox[1]
        s = min(card_w * CARD_FILL[0] / cw, card_h * CARD_FILL[1] / ch, plain * CARD_ZOOM)
        left = card_w / 2 - (bbox[0] + cw / 2) * s
        top = card_h / 2 - (bbox[1] + ch / 2) * s
        if hidden:
            bg = "var(--raised)"
            blend = " blend-screen" if tok["theme"] == "dark" else " blend-multiply"
        else:
            bg, blend = edge, ""
        return ('<div class="card" style="width:%s;height:%s;background:%s">'
                '<img class="fitted%s" src="%s" alt="" style="left:%s;top:%s;width:%s;height:%s"></div>'
                % (_px(card_w), _px(card_h), bg, blend, _esc(src), _px(left), _px(top), _px(iw * s), _px(ih * s)))
    if hidden:
        pad = 0.45 * u
        inner = _whole(src, area_w - 2 * pad, area_h - 2 * pad, a)
        return '<div class="frame" style="padding:%s;background:var(--raised)">%s</div>' % (_px(pad), inner)
    return _whole(src, area_w, area_h, a)


def _icon_svg(name: str) -> str:
    path = ICONS / ("%s.svg" % name)
    if not path.exists():
        return ""
    svg = path.read_text(encoding="utf-8")
    return svg[svg.find("<svg"):] if "<svg" in svg else ""


def icon_side(t: dict, box: dict, tok: dict, lab_h: float) -> float:
    """Icon size in px. icon_size (in u) when bento.json gives one; otherwise 46% of the tile width, the median
    of Apple's icon tiles, kept between 3.5u and 9u and inside the room above the label."""
    u = tok["u"]
    if t.get("icon_size") is not None:
        side = float(t["icon_size"]) * u
    else:
        side = min(max(bs.RATIOS["icon_fill"] * box["w"], bs.RATIOS["icon"] * u), bs.RATIOS["icon_max"] * u)
    below = (tok["inset"] - tok["shift"]["bottom"]) + lab_h + GAP * u if t.get("label") else MEDIA_PAD * u
    room_h = box["h"] - MEDIA_PAD * u - below
    room_w = box["w"] - 2 * MEDIA_PAD * u
    return max(min(side, room_h, room_w), 2.0 * u)


def _image_wants_white(img_path, tok: dict) -> bool:
    """White type on a picture when the middle of the picture is dark enough for large text (3:1)."""
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            w, h = im.size
            mid = im.convert("RGB").crop((w // 5, h // 5, w - w // 5, h - h // 5)).resize((1, 1), Image.BOX)
            r, g, b = mid.getpixel((0, 0))
    except Exception:
        return False
    return _wants_white("#%02x%02x%02x" % (r, g, b), tok, large_only=True)


def _wants_white(bg, tok: dict, large_only: bool = False) -> bool:
    """White text on a tile coloured by its content when white reads well enough (Apple puts white type on
    coloured surfaces); otherwise whichever of black and white contrasts more."""
    import bento_check as bc
    stops = [bg] if isinstance(bg, str) else list(bg)
    lums = [bc.rel_luminance(bc.parse_color(c)) for c in stops]
    white = 1.05 / (max(lums) + 0.05)
    black = (min(lums) + 0.05) / 0.05
    return white >= (3.0 if large_only else 4.5) or white >= black


def _image_size(path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


_FOCUS_WORDS = {"left": 0.0, "top": 0.0, "center": 0.5, "right": 1.0, "bottom": 1.0}


def _focus_fractions(focus: str | None) -> tuple[float, float]:
    """CSS object-position ("50% 100%", "center bottom", "top") as fractions of the free space."""
    parts = (focus or "50% 50%").split()[:2]
    if len(parts) == 1:
        parts = ["center", parts[0]] if parts[0] in ("top", "bottom") else [parts[0], "center"]
    elif parts[0] in ("top", "bottom") or parts[1] in ("left", "right"):
        parts = [parts[1], parts[0]]
    vals = [float(p[:-1]) / 100 if p.endswith("%") else _FOCUS_WORDS.get(p, 0.5) for p in parts]
    return vals[0], vals[1]


def photo_label_contrast(img_path, box: dict, focus: str | None, label: str, pos: str, tok: dict) -> float:
    """White label on a cover-fitted photo: contrast against the brightest tenth of the pixels under it,
    measured the way bento_check measures the rendered page."""
    import numpy as np
    from PIL import Image
    import bento_check
    with Image.open(img_path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0
    ih, iw = rgb.shape[:2]
    s = max(box["w"] / iw, box["h"] / ih)
    fx, fy = _focus_fractions(focus)
    ox, oy = (box["w"] - iw * s) * fx, (box["h"] - ih * s) * fy
    lines = bs.label_lines(label)
    bw = max(text_em(ln) for ln in lines) * tok["u"]
    bh = len(lines) * tok["line_height"] * tok["u"]
    x0 = (box["w"] - bw) / 2
    if pos == "bottom":
        y0 = box["h"] - (tok["inset"] - tok["shift"]["bottom"]) - bh
    else:
        y0 = tok["inset"] - tok["shift"]["top"]
    sub = rgb[max(0, int((y0 - oy) / s)):min(ih, math.ceil((y0 + bh - oy) / s)),
              max(0, int((x0 - ox) / s)):min(iw, math.ceil((x0 + bw - ox) / s))]
    if not sub.size:
        return 21.0
    lum = sub @ np.array([0.2126, 0.7152, 0.0722])
    q = np.percentile(lum, 90)
    idx = np.unravel_index(np.argmin(np.abs(lum - q)), lum.shape)
    return bento_check.contrast((1.0, 1.0, 1.0), tuple(sub[idx]))


def photo_label_pos(img_path, box: dict, focus: str | None, label: str, tok: dict) -> str:
    """Where a white label goes on a photo when bento.json leaves it open: the bottom (Apple's usual place)
    unless the picture is too light there and darker at the top. The crop changes with the canvas, so this
    is decided per render."""
    bottom = photo_label_contrast(img_path, box, focus, label, "bottom", tok)
    if bottom >= LABEL_CONTRAST * 1.2:      # margin: the rendered page resamples the photo, highlights move a little
        return "bottom"
    top = photo_label_contrast(img_path, box, focus, label, "top", tok)
    return "top" if top > bottom else "bottom"


# ---------------------------------------------------------------- tiles

def _tile_html(t: dict, box: dict, cell, tok: dict, asset) -> str:
    u = tok["u"]
    kind = t["kind"]
    pos = t.get("label_pos") or bs.LABEL_POS[kind]
    label = t.get("label")
    pad_m = MEDIA_PAD * u
    lab_h = _label_block_h(label, tok)
    below_label = (tok["inset"] - tok["shift"]["bottom"]) + lab_h + GAP * u if label else pad_m
    under_top_label = (tok["inset"] - tok["shift"]["top"]) + lab_h + GAP * u if label else pad_m
    accent = " accent" if t.get("accent") else (" tone-silver" if t.get("tone") == "silver" else "")
    style = ["grid-column:%d / span %d" % (cell[0] + 1, cell[2]), "grid-row:%d / span %d" % (cell[1] + 1, cell[3])]
    cls = ["tile", "k-" + kind]
    if t.get("background"):
        # The tile takes its colour from its content (Apple's coloured tiles are UI or product colours);
        # two colours give the top-to-bottom light falloff such a tile has, nothing more.
        bg = t["background"]
        style.append("background:%s" % (bg if isinstance(bg, str) else "linear-gradient(180deg, %s, %s)" % tuple(bg)))
        if _wants_white(bg, tok, large_only=kind == "hero"):
            cls.append("on-photo")
    body = []

    if kind == "hero":
        word = t.get("word")
        if t.get("image"):
            fit = t.get("fit", "contain")
            if fit == "cover":
                body.append(_media(_img(asset(t["image"]), t.get("focus")), 0, 0, 0, 0, "cover"))
                if word and t.get("_img_path") and _image_wants_white(t["_img_path"], tok):
                    cls.append("on-photo")          # the word sits on the picture: white when the picture is dark
            else:
                top = pad_m
                if word:
                    size = _word_size(word, {"w": box["w"], "h": box["h"] * 0.6}, tok, bs.RATIOS["hero_word"],
                                      bs.RATIOS["hero_word_min"], bs.RATIOS["hero_word_max"])
                    top = tok["inset"] + size * 1.05
                body.append(_media(_img(asset(t["image"]), t.get("focus")), top, pad_m, pad_m, pad_m, "contain"))
        if word:
            size = _word_size(word, box if not t.get("image") else {"w": box["w"], "h": box["h"] * 0.6}, tok,
                              bs.RATIOS["hero_word"], bs.RATIOS["hero_word_min"], bs.RATIOS["hero_word_max"])
            if t.get("image") and t.get("fit", "contain") != "cover":
                top = tok["inset"] - 0.1734 * size
                body.append('<div class="hero-word%s" style="top:%s;font-size:%s">%s</div>'
                            % (accent, _px(top), _px(size), _esc(word)))
            else:
                body.append('<div class="stack"><div class="hero-word-inline%s" style="font-size:%s;line-height:1;'
                            'white-space:nowrap">%s</div></div>' % (accent, _px(size), _esc(word)))

    elif kind == "stat":
        has_media = bool(t.get("image"))
        label = bs.display_label(t, tok["lang"])          # research mode adds the n / condition line
        lab_h = _label_block_h(label, tok)
        size = _number_size(t, box, tok, has_media)
        inner, _ = _number_parts(t)
        num = _num_div(t, size, inner, accent)
        sub = '<div class="sub">%s</div>' % _lines_html(label) if label else ""
        if has_media and box["w"] / box["h"] >= 1.4:
            # Wide tile: number and label on the left, picture on the right (like Apple's 48MP tile).
            text_w = box["w"] * 0.46
            size = _number_size(t, {"w": text_w - 0.4 * u, "h": box["h"]}, tok, False, cap=False)
            num = _num_div(t, size, inner, accent)
            body.append('<div class="stack" style="right:auto;width:%s">%s%s</div>' % (_px(text_w), num, sub))
            # A product picture sits inside the tile; a photograph (cover) runs to the tile's edges.
            edge = 0.0 if t.get("fit") == "cover" else pad_m
            body.append(_media(_img(asset(t["image"]), t.get("focus")), edge, edge, edge, text_w,
                               t.get("fit", "contain")))
        elif has_media:
            style.append("--num-shift-top:%s" % _px(0.1734 * size))
            body.append('<div class="stack at-top">%s%s</div>' % (num, sub))
            tail = _descent_em(t.get("value", ""))
            top = tok["inset"] + size * (1 + (tail if tail > 0.05 else 0.0)) + lab_h + GAP * u
            # The picture under the number sits inside the tile with the embedded-picture corners, a photograph
            # too: a full-width photo under a white header read as a seam (round 10, review 5).
            img = _img(asset(t["image"]), t.get("focus")).replace("<img ", '<img class="screen" ', 1)
            body.append(_media(img, top, pad_m, pad_m, pad_m, t.get("fit", "contain")))
        else:
            body.append('<div class="stack">%s%s</div>' % (num, sub))

    elif kind == "word":
        sub = '<div class="sub%s">%s</div>' % (" above" if pos == "top" else "", _lines_html(label)) if label else ""
        weight = int(t.get("weight", 1))
        side = bool(t.get("image")) and t.get("fit", "contain") != "cover" and box["w"] / box["h"] >= 1.4
        text_box = {"w": box["w"] * 0.56, "h": box["h"]} if side else box
        # A p or g in the last line hangs below the baseline; the label underneath clears that tail the way it
        # clears the baseline of a word without one (round 10, review 5: "pptx" sat 2 px above its label).
        word_lines = bs.label_lines(t["word"]) or [t["word"]]
        tail = _descent_em(word_lines[-1]) if label and pos != "top" else 0.0
        tail = tail if tail > 0.05 else 0.0
        base = bs.WORD_SIZES.get(weight, bs.RATIOS["word"])
        size = _word_size(t["word"], text_box, tok, base, bs.WORD_MIN, base,
                          lab_h + (0.15 * u if label else 0) + tail * base * u, 1.0, bs.WORD_PAD)
        word_style = "font-size:%s%s" % (_px(size), ";padding-bottom:%.3fem" % tail if tail else "")
        word = '<div class="word%s" style="%s">%s</div>' % (accent, word_style, _lines_html(t["word"]))
        group = (sub + word) if pos == "top" else (word + sub)
        if side:
            # Picture on one side, the words on the other (like Apple's A20 PRO / Massive performance gains tile).
            img_w = box["w"] - text_box["w"]
            left_img = t.get("image_side", "left") == "left"
            pic = _picture(asset(t["image"]), t.get("_img_path"), img_w - pad_m, box["h"] - 2 * pad_m,
                           t.get("_img_aspect"), tok)
            body.append(_media(pic, pad_m, (box["w"] - img_w) if left_img else pad_m, pad_m,
                               pad_m if left_img else (box["w"] - img_w), "contain"))
            body.append('<div class="stack" style="%s:auto;width:%s">%s</div>'
                        % ("left" if left_img else "right", _px(text_box["w"]), group))
        elif t.get("image") and t.get("fit", "contain") != "cover":
            # Not wide enough to sit side by side: picture on top, words underneath, never on top of each other.
            text_h = len(word_lines) * size * 1.1 + tail * size + (lab_h + 0.15 * u if label else 0)
            bottom = tok["inset"] + text_h + GAP * u
            pic = _picture(asset(t["image"]), t.get("_img_path"), box["w"] - 2 * pad_m, box["h"] - pad_m - bottom,
                           t.get("_img_aspect"), tok)
            body.append(_media(pic, pad_m, pad_m, bottom, pad_m, "contain"))
            body.append('<div class="stack" style="justify-content:flex-end">%s</div>' % group)
        else:
            if t.get("image"):
                body.append(_media(_img(asset(t["image"]), t.get("focus")), 0, 0, 0, 0, "cover"))
                if t.get("on_image") == "light":
                    cls.append("on-photo")
            body.append('<div class="stack">%s</div>' % group)

    elif kind == "icon":
        side = icon_side(t, box, tok, lab_h)
        if t.get("icon"):
            inner = '<div class="icon%s" style="--icon:%s">%s</div>' % (accent, _px(side), _icon_svg(t["icon"]))
        else:
            # A small raster object drawn as an icon (Apple's Siri orb, charging battery).
            inner = '<img class="icon-img" src="%s" alt="" style="max-width:%s;max-height:%s">' % (
                _esc(asset(t["image"])), _px(side), _px(side))
        body.append(_media(inner, pad_m, pad_m, below_label, pad_m))
        body.append(_label(label, "bottom"))

    elif kind in ("object", "flank", "row"):
        if pos == "top":
            top, bottom = under_top_label, pad_m
        else:
            top, bottom = pad_m, below_label
        if kind == "object":
            body.append(_media(_img(asset(t["image"]), t.get("focus")), top, pad_m, bottom, pad_m,
                               t.get("fit", "contain")))
        elif kind == "flank":
            side_w = max(text_em(str(t.get("left", ""))), text_em(str(t.get("right", "")))) * tok["word"]
            inner_pad = pad_m + side_w + 0.6 * u
            body.append(_media(_img(asset(t["image"]), t.get("focus")), top, inner_pad, bottom, inner_pad, "contain"))
            for side, val in (("left", t.get("left")), ("right", t.get("right"))):
                if val:
                    body.append('<div class="flank-side" style="%s:%s;top:%s;bottom:%s"><span class="%s">%s</span></div>'
                                % (side, _px(pad_m), _px(top), _px(bottom), accent.strip(), _esc(val)))
        else:
            items = []
            for it in t.get("items", []):
                if isinstance(it, str) and it.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")):
                    items.append(_img(asset(it)))
                else:
                    items.append('<span class="item">%s</span>' % _esc(it))
            body.append(_media('<div class="row">%s</div>' % "".join(items), top, pad_m, bottom, pad_m))
        body.append(_label(label, "top" if pos == "top" else "bottom"))

    elif kind == "photo":
        if label and not t.get("label_pos") and t.get("_img_path"):
            pos = photo_label_pos(t["_img_path"], box, t.get("focus"), label, tok)
        body.append(_media(_img(asset(t["image"]), t.get("focus")), 0, 0, 0, 0, "cover"))
        body.append(_label(label, "top" if pos == "top" else "bottom", on_photo=True))

    elif kind == "ui":
        # Apple's UI tiles: the screen keeps its full width and runs off the far edge. In an area much
        # narrower than the screenshot that would cut its sides off, so the whole screen goes in instead.
        side = 1.2 * u
        if pos == "bottom":
            top, bottom, focus = 0.0, below_label, "50% 100%"
        else:
            top, bottom, focus = under_top_label, 0.0, "50% 0%"
        fit = t.get("fit")
        a_img = t.get("_img_aspect")
        if fit is None:
            area_w, area_h = box["w"] - 2 * side, max(1.0, box["h"] - top - bottom)
            fit = "cover" if not a_img or area_w / area_h >= UI_BLEED_MIN * a_img else "contain"
        if fit == "contain":
            top, bottom, focus = (pad_m, bottom, "50% 50%") if pos == "bottom" else (top, pad_m, "50% 50%")
            area_w, area_h = box["w"] - 2 * side, max(1.0, box["h"] - top - bottom)
            body.append(_media(_picture(asset(t["image"]), t.get("_img_path"), area_w, area_h, a_img, tok),
                               top, side, bottom, side, "contain"))
        else:
            edge = "bleed-top" if pos == "bottom" else "bleed-bottom"
            body.append(_media(_img(asset(t["image"]), t.get("focus") or focus).replace("<img ", '<img class="screen %s" ' % edge, 1),
                               top, side, bottom, side, fit))
        body.append(_label(label, "bottom" if pos == "bottom" else "top"))

    elif kind == "chart":
        import bento_chart
        svg = bento_chart.svg(t["series"], t.get("highlight"), t.get("chart", "line"),
                              box["w"] - 2 * pad_m, box["h"] - under_top_label - pad_m, u, tok["ink"],
                              tok["accent"] if t.get("accent") else None, t.get("highlight_label"))
        body.append(_media(svg, under_top_label, pad_m, pad_m, pad_m))
        body.append(_label(label, "top"))

    return '<div class="%s" id="t-%s" data-id="%s" data-kind="%s" style="%s">%s</div>' % (
        " ".join(cls), _esc(t["id"]), _esc(t["id"]), kind, ";".join(style), "".join(body))


def css_vars(tok: dict, cols: int, rows: int) -> str:
    pairs = [
        ("w", _px(tok["css_w"])), ("h", _px(tok["css_h"])), ("u", _px(tok["u"])),
        ("gutter", _px(tok["gutter"])), ("margin", _px(tok["margin"])), ("margin-bottom", _px(tok["margin_bottom"])),
        ("radius", _px(tok["radius"])),
        ("inset", _px(tok["inset"])), ("pad", _px(tok["pad"])), ("icon", _px(tok["icon"])),
        ("word", _px(tok["word"])), ("source", _px(tok["source"])),
        ("shift-bottom", _px(tok["shift"]["bottom"])), ("shift-top", _px(tok["shift"]["top"])),
        ("canvas", tok["canvas"]), ("tile", tok["tile"]), ("ink", tok["ink"]), ("accent", tok["accent"]),
        ("raised", tok["raised"]), ("font", tok["font"]), ("lh", str(tok["line_height"])), ("cols", str(cols)), ("rows", str(rows)),
    ]
    return "\n".join("    --%s: %s;" % kv for kv in pairs)


def build_html(spec: dict, layout: dict, out_dir, base_dir=None, font: str | None = None) -> Path:
    """Write out_dir/bento.html (and copy images into out_dir/assets). Returns the HTML path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = Path(base_dir) if base_dir else Path.cwd()
    css_w, css_h, _ = bs.canvas_css(spec)
    tok = bs.tokens_for(spec, font)
    cols, rows = layout["grid"]["cols"], layout["grid"]["rows"]
    tw, th = grid_tracks(tok, cols, rows)
    assets = out_dir / "assets"
    copied: dict[str, str] = {}

    def asset(rel: str) -> str:
        if rel in copied:
            return copied[rel]
        src = (base / rel).resolve()
        assets.mkdir(exist_ok=True)
        name = "%02d-%s" % (len(copied), src.name)
        shutil.copyfile(src, assets / name)
        copied[rel] = "assets/" + name
        return copied[rel]

    tiles = []
    for t in spec["tiles"]:
        cell = layout["cells"][t["id"]]
        if t.get("image"):
            t = dict(t, _img_path=str((base / t["image"]).resolve()))
            size = _image_size(t["_img_path"])
            if size:
                t["_img_aspect"] = size[0] / size[1]
        tiles.append(_tile_html(t, tile_box(cell, tok, tw, th), cell, tok, asset))
    source = ""
    if spec.get("source_line"):
        source = '<div class="source"><span class="line">%s</span></div>' % _esc(spec["source_line"])
    page = TEMPLATE.read_text(encoding="utf-8")
    title = next((t.get("word") for t in spec["tiles"] if t["kind"] == "hero" and t.get("word")), "bento")
    page = (page.replace("{{lang}}", _esc(spec.get("lang", "zh-CN")))
                .replace("{{title}}", _esc(title))
                .replace("{{css_vars}}", css_vars(tok, cols, rows))
                .replace("{{cjk_unit_scale}}", str(bs.CJK_UNIT_SCALE))
                .replace("{{pm_scale}}", str(bs.UNCERTAINTY_SCALE))
                .replace("{{silver_top}}", "%s %d%%" % (bs.SILVER[0], bs.SILVER_STOPS[0]))
                .replace("{{silver_bottom}}", "%s %d%%" % (bs.SILVER[1], bs.SILVER_STOPS[1]))
                .replace("{{page_w}}", "%d" % round(css_w)).replace("{{page_h}}", "%d" % round(css_h))

                .replace("{{tiles}}", "\n".join(tiles))
                .replace("{{source_line}}", source))
    path = out_dir / "bento.html"
    path.write_text(page, encoding="utf-8")
    return path


# ---------------------------------------------------------------- fallback renderer

def screenshot_cli(html_path, png_path, css_w: int, css_h: int, dpr: int = 2) -> Path:
    """Chrome's command-line screenshot. Cannot wait for fonts; kept as a fallback."""
    if not CHROME.exists():
        raise FileNotFoundError("Google Chrome not found at %s" % CHROME)
    png_path = Path(png_path).resolve()
    cmd = [str(CHROME), "--headless=new", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
           "--force-color-profile=srgb", "--force-device-scale-factor=%d" % dpr,
           "--window-size=%d,%d" % (round(css_w), round(css_h)), "--default-background-color=00000000",
           "--virtual-time-budget=3000", "--screenshot=%s" % png_path, Path(html_path).resolve().as_uri()]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return png_path


# ---------------------------------------------------------------- DevTools-protocol renderer

import base64
import fcntl
import json as _json
import os
import tempfile
import time

TEXT_SELECTORS = [
    ("label", ".label"), ("number", ".num"), ("word", ".word"), ("sub", ".sub"),
    ("heroword", ".hero-word, .hero-word-inline"), ("flank", ".flank-side"), ("item", ".row .item"),
    ("source", ".source"), ("chartlabel", ".chart-label"),
]

DOM_METRICS_JS = r"""
(() => {
  const rect = el => { const b = el.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; };
  const roles = %s;
  const tiles = [...document.querySelectorAll('.tile')].map(t => {
    const cs = getComputedStyle(t);
    return {id: t.dataset.id, kind: t.dataset.kind, rect: rect(t), radius: parseFloat(cs.borderTopLeftRadius),
            background: cs.backgroundColor, background_image: cs.backgroundImage};
  });
  const texts = [];
  for (const [role, sel] of roles) {
    for (const el of document.querySelectorAll(sel)) {
      const tile = el.closest('.tile');
      const cs = getComputedStyle(el);
      const boxes = [];
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        if (!n.textContent.trim()) continue;
        const rg = document.createRange();
        rg.selectNodeContents(n);
        boxes.push(...[...rg.getClientRects()].filter(q => q.width > 0 && q.height > 0));
      }
      const tops = [];
      for (const q of [...boxes].sort((a, b) => a.top - b.top)) {
        if (!tops.length || Math.abs(q.top - tops[tops.length - 1]) > 2) tops.push(q.top);
      }
      let ink = null;
      for (const q of boxes) {
        ink = ink ? [Math.min(ink[0], q.left), Math.min(ink[1], q.top), Math.max(ink[2], q.right), Math.max(ink[3], q.bottom)]
                  : [q.left, q.top, q.right, q.bottom];
      }
      const lineEls = el.querySelectorAll('.line');
      const container = el.getBoundingClientRect();
      let wide = false;
      for (const ln of (lineEls.length ? lineEls : [el])) {
        const lr = ln.getBoundingClientRect();
        if (ln.scrollWidth > ln.clientWidth + 1 && ln !== el) wide = true;
        if (lr.width > container.width + 1) wide = true;
      }
      const silver = el.classList.contains('tone-silver') || !!el.querySelector('.tone-silver');
      const accent = el.classList.contains('accent');
      texts.push({tile: tile ? tile.dataset.id : null, role, text: el.innerText ?? el.textContent, rect: rect(el),
                  ink: ink ? [ink[0], ink[1], ink[2] - ink[0], ink[3] - ink[1]] : null,
                  font_size: parseFloat(cs.fontSize), font_weight: parseInt(cs.fontWeight, 10),
                  font_family: cs.fontFamily, color: cs.color, tone: silver ? 'silver' : (accent ? 'accent' : 'ink'),
                  lines: tops.length, wide});
    }
  }
  const images = [...document.querySelectorAll('.tile img')].map(img => {
    const cs = getComputedStyle(img);
    return {tile: img.closest('.tile').dataset.id, natural: [img.naturalWidth, img.naturalHeight], rect: rect(img),
            fit: img.classList.contains('icon-img') ? 'exact' : cs.objectFit};
  });
  return {canvas: {w: innerWidth, h: innerHeight, dpr: devicePixelRatio}, tiles, texts, images};
})()
"""

HIDE_TEXT_CSS = (".label, .num, .word, .sub, .hero-word, .hero-word-inline, .flank-side, .row .item, .source,"
                 " .chart-label"
                 " { visibility: hidden !important; }")


class ChromeError(RuntimeError):
    pass


def _high_fd(fd: int) -> int:
    """Duplicate fd to a number above 10 so it cannot collide with the child's fds 3 and 4."""
    new = fcntl.fcntl(fd, fcntl.F_DUPFD, 10)
    os.close(fd)
    return new


class Chrome:
    """Minimal DevTools-protocol client over --remote-debugging-pipe (standard library only)."""

    def __init__(self, chrome: Path = CHROME, timeout: float = 60.0):
        if not Path(chrome).exists():
            raise ChromeError("Google Chrome not found at %s" % chrome)
        self.timeout = timeout
        self.profile = tempfile.mkdtemp(prefix="bento-chrome-")
        to_r, to_w = os.pipe()
        from_r, from_w = os.pipe()
        to_r, from_w = _high_fd(to_r), _high_fd(from_w)

        def child():
            os.dup2(to_r, 3)
            os.dup2(from_w, 4)

        self.proc = subprocess.Popen(
            [str(chrome), "--headless=new", "--remote-debugging-pipe", "--user-data-dir=%s" % self.profile,
             "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--force-color-profile=srgb",
             "--disable-extensions", "--disable-background-networking", "--disable-sync", "--mute-audio",
             # Same input, same bytes: finish every compositor stage before a frame is drawn, and do not
             # defer decoding of large images (otherwise a screenshot can catch the low-quality first pass).
             "--run-all-compositor-stages-before-draw", "--disable-checker-imaging", "--disable-gpu",
             "about:blank"],
            preexec_fn=child, close_fds=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(to_r)
        os.close(from_w)
        self.w, self.r = to_w, from_r
        self.buf = b""
        self.next_id = 0
        self.events: list[dict] = []
        self.session = None

    # -- transport
    def _send(self, method: str, params: dict | None = None, session: bool = True) -> int:
        self.next_id += 1
        msg = {"id": self.next_id, "method": method, "params": params or {}}
        if session and self.session:
            msg["sessionId"] = self.session
        os.write(self.w, _json.dumps(msg).encode() + b"\0")
        return self.next_id

    def _read_message(self, deadline: float) -> dict:
        while b"\0" not in self.buf:
            if time.time() > deadline:
                raise ChromeError("timed out waiting for Chrome")
            chunk = os.read(self.r, 1 << 20)
            if not chunk:
                raise ChromeError("Chrome closed the pipe")
            self.buf += chunk
        raw, self.buf = self.buf.split(b"\0", 1)
        return _json.loads(raw)

    def call(self, method: str, params: dict | None = None, session: bool = True) -> dict:
        mid = self._send(method, params, session)
        deadline = time.time() + self.timeout
        while True:
            msg = self._read_message(deadline)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise ChromeError("%s: %s" % (method, msg["error"].get("message")))
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def wait_event(self, name: str) -> dict:
        deadline = time.time() + self.timeout
        for i, ev in enumerate(self.events):
            if ev.get("method") == name:
                return self.events.pop(i)
        while True:
            msg = self._read_message(deadline)
            if msg.get("method") == name:
                return msg
            if "method" in msg:
                self.events.append(msg)

    def evaluate(self, expression: str, await_promise: bool = True):
        res = self.call("Runtime.evaluate", {"expression": expression, "awaitPromise": await_promise,
                                             "returnByValue": True})
        if "exceptionDetails" in res:
            raise ChromeError("page script failed: %s" % res["exceptionDetails"].get("text"))
        return res.get("result", {}).get("value")

    # -- page
    def open(self, html_path, css_w: float, css_h: float, dpr: int = 2):
        if self.session is None:
            target = self.call("Target.createTarget", {"url": "about:blank"}, session=False)["targetId"]
            self.session = self.call("Target.attachToTarget", {"targetId": target, "flatten": True},
                                     session=False)["sessionId"]
            self.call("Page.enable")
        self.css_w, self.css_h, self.dpr = round(css_w), round(css_h), dpr
        self.call("Emulation.setDeviceMetricsOverride", {"width": self.css_w, "height": self.css_h,
                                                          "deviceScaleFactor": dpr, "mobile": False})
        self.events = [e for e in self.events if e.get("method") != "Page.loadEventFired"]
        self.call("Page.navigate", {"url": Path(html_path).resolve().as_uri()})
        self.wait_event("Page.loadEventFired")
        self.wait_ready()

    def wait_ready(self):
        """Wait for the template's window.__bentoReady (fonts loaded, every image decoded), then two frames."""
        self.evaluate("(window.__bentoReady || document.fonts.ready).then(() => new Promise(r =>"
                      " requestAnimationFrame(() => requestAnimationFrame(() => r(true)))))")

    def screenshot(self, png_path) -> Path:
        data = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False,
                                                    "fromSurface": True})["data"]
        png_path = Path(png_path)
        png_path.write_bytes(base64.b64decode(data))
        return png_path

    def print_pdf(self, pdf_path) -> Path:
        data = self.call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True,
                                             "marginTop": 0, "marginBottom": 0, "marginLeft": 0,
                                             "marginRight": 0})["data"]
        pdf_path = Path(pdf_path)
        pdf_path.write_bytes(base64.b64decode(data))
        return pdf_path

    def dom_metrics(self) -> dict:
        return self.evaluate(DOM_METRICS_JS % _json.dumps(TEXT_SELECTORS), await_promise=False)

    def fonts_used(self) -> list[dict]:
        """Which fonts actually drew each text element (CSS.getPlatformFontsForNode)."""
        self.call("DOM.enable")
        self.call("CSS.enable")
        root = self.call("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
        out = []
        for role, sel in TEXT_SELECTORS:
            ids = self.call("DOM.querySelectorAll", {"nodeId": root, "selector": sel})["nodeIds"]
            texts = self.evaluate("[...document.querySelectorAll(%s)].map(e => [e.closest('.tile') ? "
                                  "e.closest('.tile').dataset.id : null, e.innerText ?? e.textContent])"
                                  % _json.dumps(sel),
                                  await_promise=False) or []
            for nid, (tile, text) in zip(ids, texts):
                fonts = self.call("CSS.getPlatformFontsForNode", {"nodeId": nid}).get("fonts", [])
                out.append({"tile": tile, "role": role, "text": text,
                            "fonts": [{"family": f.get("familyName"), "postscript": f.get("postScriptName"),
                                       "glyphs": f.get("glyphCount")} for f in fonts]})
        return out

    def add_style(self, css: str):
        self.evaluate("(() => { const s = document.createElement('style'); s.textContent = %s;"
                      " document.head.appendChild(s); return true; })()" % _json.dumps(css), await_promise=False)

    def close(self):
        try:
            self._send("Browser.close", session=False)
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        for fd in (self.w, self.r):
            try:
                os.close(fd)
            except OSError:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def render(spec_path, layout_path, out_dir, pdf: bool = False, run_check: bool = True) -> dict:
    """bento.json + layout.json -> out_dir/{bento.html, bento.png, bento.textless.png, dom.json, fonts.json[, bento.pdf]}."""
    spec_path, out_dir = Path(spec_path).resolve(), Path(out_dir)
    spec = bs.load_spec(spec_path)
    layout = _json.loads(Path(layout_path).read_text(encoding="utf-8"))
    css_w, css_h, dpr = bs.canvas_css(spec)
    html_path = build_html(spec, layout, out_dir, base_dir=spec_path.parent)
    result = {"html": str(html_path)}
    with Chrome() as c:
        c.open(html_path, css_w, css_h, dpr)
        result["png"] = str(c.screenshot(out_dir / "bento.png"))
        dom = c.dom_metrics()
        fonts = c.fonts_used()
        (out_dir / "dom.json").write_text(_json.dumps(dom, ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / "fonts.json").write_text(_json.dumps(fonts, ensure_ascii=False, indent=1), encoding="utf-8")
        c.add_style(HIDE_TEXT_CSS)
        result["textless_png"] = str(c.screenshot(out_dir / "bento.textless.png"))
        if pdf:
            # PDF embeds glyph outlines, so it only ever uses the open fonts (4.8).
            pdf_html = build_html(spec, layout, out_dir / "pdf", base_dir=spec_path.parent, font="open")
            c.open(pdf_html, css_w, css_h, 1)
            result["pdf"] = str(c.print_pdf(out_dir / "bento.pdf"))
            result["pdf_fonts"] = c.fonts_used()
    result.update({"dom": str(out_dir / "dom.json"), "fonts": str(out_dir / "fonts.json")})
    if run_check:
        import bento_check
        qa = bento_check.check(spec, layout, dict(dom, fonts=fonts), result["png"], result["textless_png"])
        (out_dir / "qa.json").write_text(_json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
        result["qa"] = str(out_dir / "qa.json")
        result["qa_pass"] = qa["pass"]
        result["qa_summary"] = bento_check.summary(qa)
    return result
