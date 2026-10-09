#!/usr/bin/env python3
"""尺寸、颜色、字体栈、格数范围，以及 bento.json 的读入与校验。

全 skill 的数值只在这里定义一次（AUDIT-AND-IDEAS.md 第四部分 4.2、4.3、4.13）。
所有尺寸都是"标签字号 u"的倍数；u 按用途从画布尺寸算出来。
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

SCHEMA = "bento/1"
USES = ("screen", "print", "phone", "custom")
U_SHORT_SIDE = 0.022        # screen / print / custom：短边的 2.2%（16:9 时等于宽的 1.23%）
U_PHONE_WIDTH = 0.028       # phone：宽的 2.8%，手机全宽看图时标签约 11pt

# 苹果样图实测，2026-10-08 用亚像素量法重量（tests/fixtures/bento-infographic/apple-reference/measurements.json）
RATIOS = {
    "gutter": 0.68, "margin": 0.68, "radius": 1.55, "inset": 0.95,
    "word": 1.75, "number": 3.2, "number_min": 2.2, "number_max": 4.3,
    "hero_word_min": 5.0, "hero_word_max": 8.0, "icon": 3.5,
    # 第 10 轮：主图字默认 6u（样图 3 的 iOS 5.4u，"PRO" 那种加宽字才到 8u）；图标随格宽放大，
    # 样图 2–6 的 13 个图标格里图标宽是格宽的 35–67%（中位数 46%），绝对值 3.5–9.1u
    "hero_word": 6.0, "icon_fill": 0.46, "icon_max": 9.0,
    "min_tile_w": 6.0, "min_tile_h": 4.8, "max_aspect": 3.5,
    "pad": 1.0,              # 标签左右至少留这么多（官方 iPhone 18 Pro 片 Apple Reference 一格两侧各 1.08u）
    "source": 0.75,          # 出处行，默认不出
}
# 功能名按重要程度分三档的上限（官方 iPhone 18 Pro 总结片实测：Best battery life ever 1.75u、
# Apple Intelligence 2.0u；Vapor chamber 按格宽排满，约 2.6u）。放不下时往下缩，最小 1.6u。
# 第三档原来是 3.3u，比实测最大的 2.6u 还大，第 10 轮第 4 次评审指出「pptx」压过了别的字，改回实测值
WORD_SIZES = {1: 1.75, 2: 2.0, 3: 2.6}
WORD_MIN = 1.6
WORD_PAD = 1.0             # 功能名左右留白（官方 Best battery life ever：282 px 的格里字宽 232 px）
TONES = ("ink", "silver")   # silver：深色主题里次要大字用的银灰渐变，每行各自上深下浅
# 第 10 轮按样图 6 逐行重量：每行字顶约 110、基线处约 205–210（灰度），渐变按行走，不是整块一个渐变。
# 色标放在行框的 20%（大写字母顶）和 84%（基线）处
SILVER = ("#646464", "#d0d0d0")
SILVER_STOPS = (20, 84)
LINE_HEIGHT = {"en": 1.18, "zh-CN": 1.3}
WEIGHT = 600
CJK_UNIT_SCALE = 0.45       # "36 小时"里的"小时"相对数字的字号；拉丁单位（MP、nits）与数字同字号
UNCERTAINTY_SCALE = 0.5     # 研究模式"1.23 ± 0.04 s"里"± 0.04 s"相对数字的字号

# 系统字体的竖向度量（SFNS.ttf 的 hhea：上伸 0.9668、下伸 0.2109、大写高 0.7046 em）。
# 标签的基线（英文）或汉字墨迹底边（中文，见下面 HAN_INK_*）放在离格边 inset 处。
SF_ASCENT, SF_DESCENT, SF_CAP = 0.9668, 0.2109, 0.7046

# raised：图片的底和格子同色、边看不见时（黑底的片子放进黑格），垫在图下面的那层面，取 iOS 的次级底色
# （深色 #1c1c1e，浅色 #f2f2f7；第 10 轮第 5 次评审：深色版的黑卡片放进黑格就没了）
THEMES = {
    "light":         {"canvas": "#e8e8e8", "tile": "#ffffff", "ink": "#000000", "raised": "#f2f2f7"},
    "light-inverse": {"canvas": "#ffffff", "tile": "#ececec", "ink": "#000000", "raised": "#ffffff"},
    "dark":          {"canvas": "#181818", "tile": "#000000", "ink": "#ffffff", "raised": "#1c1c1e"},
}
FONT_STACKS = {
    "system": 'system-ui, BlinkMacSystemFont, "PingFang SC", "Inter", "Noto Sans SC", sans-serif',
    "open":   '"Inter", "Noto Sans SC", "Source Han Sans SC", sans-serif',
}
# 英文最多 7 个词：官方 iPhone 18 Pro 总结片有一条 "48MP Fusion Main camera with variable aperture"
LABEL_LIMITS = {"en_words": 7, "en_lines": 3, "zh_units": 12, "zh_line_units": 11, "zh_lines": 2}

TILE_KINDS = ("hero", "stat", "word", "icon", "object", "photo", "ui", "row", "flank", "chart")
IMAGE_KINDS = {"object", "photo", "ui", "flank"}   # icon 格可以用 icon 名字，也可以用一张小图
ACCENT_KINDS = {"stat", "word", "hero", "icon", "chart"}   # 手表样图里重点色也用在图标上；图表只用在高亮处
TEXT_ONLY_KINDS = {"stat", "word"}            # 没有图也没有图标时算纯文字格
LABEL_POS = {"hero": None, "stat": "center", "word": "center", "icon": "bottom", "object": "bottom",
             "photo": "bottom", "ui": "bottom", "row": "bottom", "flank": "bottom", "chart": "top"}
# 界面截图的标签默认在下：苹果样图里图在上、标签在下是常态（样图 3 约 1/15 在上，5 为 0，6 约 3/12，
# 4 为 5/12）；截图从下边出血时（如整页版面）在 bento.json 里写 label_pos: "top"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ICON_INDEX = Path(__file__).resolve().parent.parent / "assets" / "icons" / "index.json"


def icon_names() -> set[str]:
    try:
        return set(json.loads(ICON_INDEX.read_text(encoding="utf-8"))["icons"])
    except (OSError, ValueError, KeyError):
        return set()
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------- sizing

def canvas_css(spec: dict) -> tuple[float, float, int]:
    c = spec["canvas"]
    dpr = int(c.get("dpr", 2))
    return c["width"] / dpr, c["height"] / dpr, dpr


def unit_px(css_w: float, css_h: float, use: str, ratio: float | None = None) -> float:
    """Label font size u in CSS px."""
    if use == "phone":
        return (ratio or U_PHONE_WIDTH) * css_w
    return (ratio or U_SHORT_SIDE) * min(css_w, css_h)


# 中文标签在 Chrome 里实测（第 10 轮第 5 次，产品版 9 个标签）：1.3 倍行框里，苹方墨迹顶在行框顶下 0.085 em，
# 墨迹底在行框底上 0.245 em。按 SF 的上伸下伸推算是 0.198 / 0.162 em，汉字整体比推算高约 0.11 em，
# 底部标签因此离格边 1.05u 而不是 0.95u（第 4 次评审量到的"标签偏高"）。中文直接用实测值
HAN_INK_FROM_LINE_TOP, HAN_INK_FROM_LINE_BOTTOM = 0.085, 0.245


def label_shifts(lang: str) -> dict:
    """How far (in u) the label's line box must sit past the inset so that the visual edge lands on it."""
    lh = LINE_HEIGHT.get(lang, LINE_HEIGHT["en"])
    half = (lh - (SF_ASCENT + SF_DESCENT)) / 2          # half-leading of the primary (SF) font
    if lang == "zh-CN":
        return {"bottom": HAN_INK_FROM_LINE_BOTTOM, "top": HAN_INK_FROM_LINE_TOP}
    return {"bottom": half + SF_DESCENT, "top": half + SF_ASCENT - SF_CAP}


def tokens(css_w: float, css_h: float, use: str, theme: str = "light", lang: str = "zh-CN",
           accent: str | None = None, font: str = "system", u_ratio: float | None = None,
           source: bool = False) -> dict:
    u = unit_px(css_w, css_h, use, u_ratio)
    t = {k: round(v * u, 3) for k, v in RATIOS.items() if k not in ("max_aspect",)}
    # The source line (off by default, 4.13) gets its own band under the tiles: a margin above it, a margin below.
    t["margin_bottom"] = round((2 * RATIOS["margin"] + RATIOS["source"]) * u, 3) if source else t["margin"]
    t.update({
        "u": round(u, 3), "css_w": css_w, "css_h": css_h,
        "line_height": LINE_HEIGHT.get(lang, LINE_HEIGHT["en"]), "weight": WEIGHT,
        "font": FONT_STACKS[font], "lang": lang, "theme": theme,
        "accent": accent or THEMES[theme]["ink"],
        "max_aspect": RATIOS["max_aspect"],
        "shift": {k: round(v * u, 3) for k, v in label_shifts(lang).items()},
    })
    t.update(THEMES[theme])
    return t


def tokens_for(spec: dict, font: str | None = None) -> dict:
    """tokens() for a bento.json."""
    css_w, css_h, _ = canvas_css(spec)
    return tokens(css_w, css_h, spec["canvas"]["use"], spec.get("theme", "light"), spec.get("lang", "zh-CN"),
                  spec.get("accent"), font or spec.get("font", "system"), spec["canvas"].get("u_ratio"),
                  bool(spec.get("source_line")))


# 格数（含主图）。苹果 2022–26 年的 67 张 16:9 总结片：常见 14–18（九成不少于 14），最少 10、最多 21。
# 主图居中、外圈一圈格子，格数随外圈的长度变，所以别的画幅按"以短边计的周长" 2 × (长边/短边 + 1)
# 折算（16:9 是 5.56）。第 7 轮按九种画幅实排校准：格数和 u 无关，手机的字大，能排多少由排版器按内容判断。
APPLE_COUNT = {"typical": (14, 18), "observed": (10, 21)}


def _ring_scale(css_w: float, css_h: float) -> float:
    long_side, short_side = max(css_w, css_h), min(css_w, css_h)
    return (long_side / short_side + 1) / (16 / 9 + 1)


def count_range(use: str, css_w: float, css_h: float) -> tuple[int, int]:
    """Suggested tile count including the hero (Apple's typical 14–18 at 16:9); outside it the QA warns."""
    s = _ring_scale(css_w, css_h)
    lo, hi = APPLE_COUNT["typical"]
    return int(lo * s + 0.5), int(hi * s + 0.5)


def count_limits(use: str, css_w: float, css_h: float) -> tuple[int, int]:
    """Hard limits including the hero (Apple's observed 10–21 at 16:9); outside them the QA fails."""
    s = _ring_scale(css_w, css_h)
    lo, hi = APPLE_COUNT["observed"]
    return max(5, int(lo * s + 1e-9)), int(hi * s + 0.5)


# ---------------------------------------------------------------- text measures

def is_cjk(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def display_units(text: str) -> float:
    """Approximate width in u: a Han character is 1, a Latin letter or digit about 0.55, a space 0.3."""
    total = 0.0
    for ch in text:
        if is_cjk(ch):
            total += 1.0
        elif ch.isspace():
            total += 0.3
        elif ch.isalnum():
            total += 0.55
        else:
            total += 0.35
    return round(total, 2)


def label_lines(label: str | None) -> list[str]:
    return [] if not label else [ln.strip() for ln in label.split("\n")]


def has_cjk(text: str) -> bool:
    return any(is_cjk(ch) for ch in text or "")


def is_han(ch: str) -> bool:
    """A Han character (not full-width punctuation such as ，or ：)."""
    return is_cjk(ch) and unicodedata.category(ch) == "Lo"


def cjk_spacing_problems(text: str) -> list[str]:
    """Han characters touching Latin letters or digits without a space (Apple's Chinese pages put one in).
    Full-width punctuation needs no space: "n = 12，室温"."""
    bad = []
    for a, b in zip(text, text[1:]):
        if (is_han(a) and b.isascii() and b.isalnum()) or (a.isascii() and a.isalnum() and is_han(b)):
            bad.append(a + b)
    return bad


def meta_line(t: dict, lang: str = "zh-CN") -> str | None:
    """Research mode: sample size and condition, shown as one more line under a number's label."""
    parts = []
    if t.get("n") not in (None, ""):
        parts.append("n = %s" % t["n"])
    if t.get("condition"):
        parts.append(str(t["condition"]).strip())
    if not parts:
        return None
    return ("，" if lang == "zh-CN" else ", ").join(parts)


def display_label(t: dict, lang: str = "zh-CN") -> str | None:
    """The label as drawn: the written label, plus the research meta line when there is one."""
    meta = meta_line(t, lang)
    label = t.get("label") or ""
    if not meta:
        return label or None
    return (label + "\n" + meta) if label else meta


# ---------------------------------------------------------------- spec

def load_spec(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tile_has_number(t: dict) -> bool:
    blob = " ".join(str(t.get(k, "")) for k in ("value", "label", "word", "left", "right", "condition"))
    return t["kind"] in ("stat", "flank", "chart") or any(ch.isdigit() for ch in blob)


def validate_spec(spec: dict, base_dir=None) -> list[str]:
    """Return a list of problems in Chinese; an empty list means the spec is usable."""
    errs: list[str] = []
    base = Path(base_dir) if base_dir else None
    if spec.get("schema") != SCHEMA:
        errs.append('schema 必须是 "%s"' % SCHEMA)
    c = spec.get("canvas") or {}
    if c.get("use") not in USES:
        errs.append("canvas.use 必须是 %s 之一" % "、".join(USES))
    for k in ("width", "height"):
        if not isinstance(c.get(k), int) or c.get(k, 0) <= 0:
            errs.append("canvas.%s 必须是正整数（输出像素）" % k)
    if not isinstance(c.get("dpr", 2), int) or c.get("dpr", 2) < 1:
        errs.append("canvas.dpr 必须是正整数")
    if spec.get("theme", "light") not in THEMES:
        errs.append("theme 必须是 %s 之一" % "、".join(THEMES))
    mode = spec.get("mode", "product")
    if mode not in ("product", "research"):
        errs.append("mode 必须是 product 或 research")
    lang = spec.get("lang", "zh-CN")
    if lang not in LINE_HEIGHT:
        errs.append("lang 必须是 zh-CN 或 en")
    if spec.get("font", "system") not in FONT_STACKS:
        errs.append("font 必须是 system 或 open")
    accent = spec.get("accent")
    if accent is not None and not (isinstance(accent, str) and HEX_RE.match(accent)):
        errs.append('accent 必须是 null 或 "#rrggbb"')
    if spec.get("source_line") is not None and not isinstance(spec.get("source_line"), str):
        errs.append("source_line 必须是 null 或字符串")

    tiles = spec.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        errs.append("tiles 必须是非空列表")
        return errs
    ids = set()
    heroes = 0
    for i, t in enumerate(tiles):
        where = "tiles[%d]%s" % (i, ("（%s）" % t.get("id")) if t.get("id") else "")
        tid, kind = t.get("id"), t.get("kind")
        if not isinstance(tid, str) or not ID_RE.match(tid):
            errs.append("%s：id 要用小写字母、数字和短横线" % where)
        elif tid in ids:
            errs.append("%s：id 重复" % where)
        ids.add(tid)
        if kind not in TILE_KINDS:
            errs.append("%s：未知的 kind %r" % (where, kind))
            continue
        heroes += kind == "hero"
        if t.get("weight", 1) not in (1, 2, 3):
            errs.append("%s：weight 只能是 1、2、3" % where)
        errs.extend(_label_problems(t.get("label"), lang, where))
        if tile_has_number(t) and not t.get("unverified") and not _facts_ok(t.get("facts")):
            errs.append("%s：有数字就要在 facts 里写出处，找不到出处就写 \"unverified\": true" % where)
        if tile_has_number(t) and t.get("unverified"):
            shown = "%s %s" % (display_label(t, lang) or "", t.get("word") or "")
            if "未确认" not in shown and "unverified" not in shown.lower():
                errs.append('%s：没有出处的数字要在图上看得出来：标签里写上"未确认"（英文写 unverified），'
                            "或者不放这一格" % where)
        if kind == "chart" and mode != "research":
            errs.append("%s：chart 只在 research 模式里用" % where)
        if kind == "chart" and (not isinstance(t.get("series"), list) or len(t.get("series", [])) < 2
                                or not all(isinstance(v, (int, float)) for v in t.get("series", []))):
            errs.append("%s：chart 需要至少两个数据点的 series（数字）" % where)
        if kind == "chart" and t.get("chart", "line") not in ("line", "bar"):
            errs.append("%s：chart 只能是 line 或 bar" % where)
        if kind == "chart" and t.get("highlight") is not None and not (
                isinstance(t["highlight"], int) and 0 <= t["highlight"] < len(t.get("series") or [])):
            errs.append("%s：highlight 是 series 里的下标（从 0 数）" % where)
        errs.extend(_research_problems(t, mode, lang, where))
        bg = t.get("background")
        if bg is not None and not ((isinstance(bg, str) and HEX_RE.match(bg)) or (
                isinstance(bg, list) and len(bg) == 2 and all(isinstance(c, str) and HEX_RE.match(c) for c in bg))):
            errs.append('%s：background 是 "#rrggbb"，或上下两个颜色 ["#顶", "#底"]；只用内容自带的颜色' % where)
        tone = t.get("tone", "ink")
        if tone not in TONES:
            errs.append("%s：tone 只能是 ink 或 silver" % where)
        if tone == "silver" and spec.get("theme", "light") != "dark":
            errs.append("%s：silver 只用在深色主题" % where)
        if tone == "silver" and t.get("accent"):
            errs.append("%s：silver 和重点色不能同时用" % where)
        if t.get("accent") and kind not in ACCENT_KINDS:
            errs.append("%s：只有 stat、word、hero、icon、chart 能用重点色" % where)
        if t.get("accent") and not accent:
            errs.append("%s：用了重点色，但顶层 accent 没给颜色" % where)
        if kind in IMAGE_KINDS and not t.get("image"):
            errs.append("%s：%s 格需要 image" % (where, kind))
        if kind == "hero" and not (t.get("image") or t.get("word")):
            errs.append("%s：主图要有 image 或 word" % where)
        if kind == "icon" and not (t.get("icon") or t.get("image")):
            errs.append("%s：icon 格需要 icon 名字或一张小图 image" % where)
        if kind == "icon" and t.get("icon") and icon_names() and t["icon"] not in icon_names():
            errs.append("%s：没有叫 %s 的图标（可用的见 assets/icons/index.json）" % (where, t["icon"]))
        if kind == "icon" and t.get("icon_size") is not None and not (3.0 <= float(t["icon_size"]) <= RATIOS["icon_max"]):
            errs.append("%s：icon_size 在 3–9u 之间（样图实测范围）；不写就按格宽自动定" % where)
        if t.get("label_pos") is not None and t["label_pos"] not in ("top", "bottom"):
            errs.append("%s：label_pos 只能是 top 或 bottom（照片格不写就按对比度自动选）" % where)
        if t.get("fit") is not None and t["fit"] not in ("contain", "cover"):
            errs.append("%s：fit 只能是 contain 或 cover" % where)
        if kind == "row" and not t.get("items"):
            errs.append("%s：row 格需要 items" % where)
        if kind == "stat" and not t.get("value"):
            errs.append("%s：stat 格需要 value" % where)
        if kind == "word" and not t.get("word"):
            errs.append("%s：word 格需要 word" % where)
        for path in _image_paths(t):
            if base is not None and not (base / path).exists():
                errs.append("%s：图片不存在 %s" % (where, path))
    if heroes != 1:
        errs.append("必须恰好有一个 kind 为 hero 的格（现在 %d 个）" % heroes)
    return errs


def _research_problems(t: dict, mode: str, lang: str, where: str) -> list[str]:
    """Numbers in research mode carry their uncertainty, or say why they need none."""
    fields = [k for k in ("uncertainty", "n", "condition", "exact") if t.get(k) not in (None, "", False)]
    if mode != "research" or t.get("kind") != "stat":
        return ["%s：%s 只用在 research 模式的 stat 格" % (where, "、".join(fields))] if fields else []
    errs = []
    unc, exact, n = t.get("uncertainty"), t.get("exact"), t.get("n")
    if n not in (None, "") and not (str(n).isdigit() and int(str(n)) >= 1):
        errs.append("%s：n 是样本数，正整数" % where)
    if unc not in (None, "") and not any(ch.isdigit() for ch in str(unc)):
        errs.append('%s：uncertainty 写数值，如 "0.04"' % where)
    if unc not in (None, "") and exact:
        errs.append("%s：写了 uncertainty 又写 exact，二选一" % where)
    if unc in (None, "") and not exact and str(n) != "1":
        errs.append('%s：研究模式的数字要写 uncertainty（如 "0.04"）；计数、定义值、确定性计算的结果写 '
                    '"exact": true；只测了一次写 "n": 1' % where)
    meta = meta_line(t, lang)
    if meta:
        if len(label_lines(t.get("label"))) > 1:
            errs.append("%s：写了 n 或 condition，标签只能一行（第二行放样本数与条件）" % where)
        too_long = (display_units(meta) > LABEL_LIMITS["zh_line_units"] if lang == "zh-CN"
                    else len(meta.split()) > LABEL_LIMITS["en_words"])
        if too_long:
            errs.append("%s：样本数与条件那一行太长：%s" % (where, meta))
    return errs


def _facts_ok(facts) -> bool:
    return isinstance(facts, list) and bool(facts) and all(
        isinstance(f, dict) and str(f.get("text", "")).strip() and str(f.get("source", "")).strip() for f in facts)


def _image_paths(t: dict) -> list[str]:
    out = [t["image"]] if t.get("image") else []
    for it in t.get("items") or []:
        if isinstance(it, str) and Path(it).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
            out.append(it)
    return out


def _label_problems(label, lang: str, where: str) -> list[str]:
    lines = label_lines(label)
    if not lines:
        return []
    errs = []
    if lang == "zh-CN":
        if len(lines) > LABEL_LIMITS["zh_lines"]:
            errs.append("%s：中文标签最多 %d 行" % (where, LABEL_LIMITS["zh_lines"]))
        total = sum(display_units(ln) for ln in lines)
        if total > LABEL_LIMITS["zh_units"]:
            errs.append("%s：中文标签约 %.1f 字，超过 %d 字" % (where, total, LABEL_LIMITS["zh_units"]))
        for ln in lines:
            if display_units(ln) > LABEL_LIMITS["zh_line_units"]:
                errs.append("%s：一行约 %.1f 字，超过 %d 字" % (where, display_units(ln), LABEL_LIMITS["zh_line_units"]))
            if has_cjk(ln) and display_units(ln) < 2:
                errs.append("%s：一行只剩一个字（孤字）" % where)
    else:
        words = " ".join(lines).split()
        if len(words) > LABEL_LIMITS["en_words"]:
            errs.append("%s：英文标签 %d 个词，超过 %d 个" % (where, len(words), LABEL_LIMITS["en_words"]))
        if len(lines) > LABEL_LIMITS["en_lines"]:
            errs.append("%s：英文标签最多 %d 行" % (where, LABEL_LIMITS["en_lines"]))
    return errs
