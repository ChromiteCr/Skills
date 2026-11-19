#!/usr/bin/env python3
"""从片单 JSON 生成可编辑的 .pptx，带动画。

    python3 outline_to_pptx.py deck.json [out.pptx]
    python3 outline_to_pptx.py deck.json --static     不写任何动画
    python3 outline_to_pptx.py --help                 看这份说明与片单格式
    python3 outline_to_pptx.py --palette <颜色> [--sat 0.35] [--accent <主色>]
                                                      算一套和内容匹配的底色，HTML 与片单都用它
    python3 outline_to_pptx.py --selftest

依赖 python-pptx（`pip3 install python-pptx`）；image / claim 带图时还要 Pillow（`pip3 install pillow`）。

这条路的价值是「能在 Keynote 或 PowerPoint 里继续改」。动画由 `pptx_motion.py` 写入
（PresentationML 的 <p:timing>），HTML 模板的四件事都做得到：

  讲到才出现  逐项浮入（淡入 + 上移），一步一次点击
  讲过的调暗  换成 faint 色
  讲到的点名  换成重点色
  跨片连续    相邻两片的同一个对象用 Morph（平滑）切换，旧版本回退成淡入淡出

**仍然会丢东西，要如实告诉使用者**：

  - 内容片的底色是纯色；封面、分节、静场可以用色场或两段的柔和渐变（"ground"），和 HTML 一样
  - 公式退成纯文本，要在 PowerPoint 或 Keynote 的公式编辑器里重排
  - 颗粒、圆角容器、bento 的大小分层都被简化
  - 图表不做，在 PowerPoint 里手工摆更快
  - 公式里逐项点名做不到（一个文本框只能整体换色），讲到哪一项靠嘴说
  - 误解片的划线做不到，改成把误解调暗

要视觉精度就用 templates/deck.html；要可编辑就用这个。两者不冲突，可以都给。

画布是 13.333 × 7.5 英寸，也就是 960 × 540pt，正好是 HTML 舞台（1920 × 1080px）的一半，
所以版面上 px ÷ 2 = pt：大数字 280px 对应 140pt，标题 80px 对应 40pt。
小字这里用 30pt，比 HTML 的 40px（对应 20pt）相对更大，是有意偏严。塞不下就删字，不要调低。

每张片都可以带 "notes"，写进 pptx 的演讲者备注。讲者备注里在该点下一步的词前标【点】。

底色（0.10.1）：默认用和文字、讲的内容风格匹配的颜色，没有合适的匹配色才用黑色。
  "background": "#RRGGBB"  匹配色，写在最外层管整套，写在单张片上管这一张（章节换色）。
                           色值用 --palette 算：色相取品牌色或内容联想的颜色，饱和度按语气
                           （学术约 0.35，发布会约 0.45），明度压到白字 ≥ 10:1、次要字 ≥ 7:1。
                           重点色压在匹配色上要 ≥ 4.5:1，不够会报；--palette --accent 会给出提亮的值
  "theme": "dark"          没写 background 时是纯黑（"black" 同义）；0.9.0 的旧片单因此照旧是黑底
  "theme": "tinted"        带色近黑：主色的色相、明度 8.5%，几乎是黑
  "theme": "graphite"      石墨 #1c1c1e，LED 屏、电视、录播
  "theme": "light"         浅色 #f5f5f7，亮教室。加 "background" 时页面照旧浅色，匹配色只上色场；
                           重点色要压暗到浅底上过 4.5:1，--palette 打出的「亮教室」那两行就是这一套
  "tinted"、"graphite"、"black" 和整套的 "background" 同时写会报，按 background 出。
  切视频要纯黑的静场：在那张片上写 "background": "#000000"（浅色主题里再加 "ground": "field"）。
  封面、分节、静场可以加 "ground": "field"（色场，白字）或 "fade"（底色 → 色场的柔和渐变）；
  别的片型写了会报。静场是 {"type": "rest"}，可加 "value": "T" 在右下角画一个同色调巨字，最多 4 个字。

一张片一层字（0.9.0 起）：说明是讲的人说的。旧片单里标题卡、大数字、功能名、价格、提问、
满版图、概念、公式的 "caption"，流程条每一步的第二项，公式下面的 "items"，导出时不上片，
原样挪进讲者备注，并打一条「注意」。

大字下面不垫说明。下面这些不是说明，留在片上：数字前后的限定词与单位（和数字同一行）、
出处行（来源、样本量、测试条件，放左下）、「未确认」标记、引语的出处、图片来源行、误解片的正确说法；
各片型自带的项名与标签（规格与 bento 的项名、双列对比的列头、价格的配置名、推演右栏的依据、
回顾的提示词与要点、提问片的标签与选项、误解片的标签、图表的项名）是内容本身。
在片单里，出处行是 title、num、versus 与 formula 的 "source"（论文讲读的标题卡写「论文讲读 · 作者 年份」）、
claim 与 derive 的 "caption"；引语的出处是
quote 的 "caption"；图片来源行是 image 的 "credit"；误解片的正确说法是 myth 的 "caption"。
公式写不短的适用条件（「不计空气阻力」）也写进 formula 的 "source"。

大数字的 value 按「[限定词␠]数字[单位]」写：限定词在前、和数字隔一个空格，单位跟在数字后面，
两者都缩到数字的 0.4 倍、和数字同一行，合计最多 8 个字：中文一字算一个，拉丁字母、数字与符号
两个算一个，空格不算（「CO₂ 平均误差」加「ppm」算 7 个）。数字的正负号认 + - − ±。
{"type": "num", "value": "最长 22 小时视频播放"} 切成「最长」「22」「小时视频播放」三段。
限定词里可以带跟在名字后面的版本号：「比 Drift 1 薄 30%」取最后一个数，切成「比 Drift 1 薄」「30」「%」；
版本号写在数字后面（「3 倍于 Drift 1」）切不开，改写成「是 Drift 1 的 3 倍」。
样本量、来源、测试条件不写进 value，写进 "source"：画在左下（30pt、次要色、一行），不挪进备注。
超过 8 个字、整行放不下、切不开（比如单位里还带数字），都会报一条「注意」。
「4K120」「A17 Pro」这种名字照原样排，不报；中文贴着数字（「续航30天」）会报。

片单格式（type 决定版式，其余字段按类型取用）：

    {
      "accent": "#e27f55",
      "background": "#4a2a1c",
      "font": "Helvetica Neue",
      "slides": [
        {"type": "title",   "value": "产品名"},
        {"type": "phrase",  "value": "转账不该点 7 次"},
        {"type": "num",     "value": "最长 22 小时视频播放",
                            "unverified": false, "accent": false},
        {"type": "num",     "value": "满意度 4.2 分", "source": "n = 30 · 中期问卷"},
        {"type": "section", "value": "章节名", "ground": "field"},
        {"type": "rest",    "value": "T"},          静场：讲故事、举例、答问时用，value 可省
        {"type": "feature", "value": "功能名"},
        {"type": "quote",   "value": "用户原话", "caption": "出处，必填"},
        {"type": "steps",   "value": "这套流程产出什么",
                            "items": ["步骤", "步骤", "步骤"]},
        {"type": "specs",   "value": "规格",
                            "items": [["项", "值"], ["项", "值"]]},
        {"type": "versus",  "value": "对比什么",
                            "items": [["上一代", "1.0"], ["本代", "3.2"]],
                            "source": "版本与测试时间，可省"},
        {"type": "price",   "value": "产品名",
                            "items": [["¥4999", "128GB"]]},
        {"type": "close",   "value": "收束一句"},

        课堂与讲堂：
        {"type": "roadmap",    "items": ["现象", "原理", "应用"], "current": 1},
        {"type": "question",   "kicker": "概念题", "value": "摆长变成 4 倍，周期变成几倍",
                               "items": ["2 倍", "4 倍", "16 倍"], "answer": 0},
        {"type": "image",      "src": "figures/a.jpg", "value": "图上的一句",
                               "credit": "来源，必填", "focus": [0.5, 0.4]},
        {"type": "claim",      "value": "一句主张", "caption": "出处",
                               "src": "figures/evidence.png"},
        {"type": "definition", "value": "术语", "symbol": "T"},
        {"type": "derive",     "value": "这一段要证明什么",
                               "items": [["式子", "凭什么这一步成立"], ["式子", "凭什么"]],
                               "caption": "出处", "caption_at": 2},
        {"type": "formula",    "value": "T ≈ 2π √(L / g)"},
        {"type": "myth",       "value": "误解原话", "caption": "正确说法"},
        {"type": "recap",      "items": [["提示词", "一个短语"]]},          三条封顶；HTML 的缩略图在 pptx 里没有
        {"type": "recap",      "value": "贡献", "build": false,
                               "items": [["1", "一行，12 字内"]]},          学术报告的最后一张，问答时停着
        {"type": "refs",       "items": ["作者（年份）. 题名. 出处."]},     备用页：放在最后一张之后

        每张都可以加 "notes": "讲者备注"
        每张都可以加 "build": false 让这张片一次出完；分步走的片型还认 "dim": false
        相邻两片上同一个东西写同一个 "morph": "T"，翻页时用 Morph 平滑切换
      ]
    }

出场顺序按片型定（`BUILD` 与 `DIM` 两张表），不用逐片写步数：
流程条、推演逐步走并调暗；回顾逐条出；提问片在原地揭晓；误解片在原地改正。
规格密排与双列对比默认一次出齐，要逐个出就写 "build": true。

自检：每个会折行的文本框都按它自己的高度算能放几行，放不下的行、折行后只剩一两个字的孤行
都会报出来（只报不改，生成的文件照旧）。片单里不认识的字段也会报，格式不对的片直接报错、不写文件。
"""

import colorsys
import io
import json
import re
import sys
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from pptx.util import Inches, Pt
except ImportError:
    sys.exit("缺 python-pptx。装：pip3 install python-pptx")

try:
    import pptx_motion as motion
except ImportError:
    sys.exit("找不到 pptx_motion.py，它应该和本脚本在同一个目录")

try:
    from PIL import Image, ImageOps
except ImportError:          # 只有 image / claim 带图时才需要
    Image = ImageOps = None

# 16:9
W, H = Inches(13.333), Inches(7.5)
# 内容离边 10–15%
PAD_X, PAD_Y = Inches(1.6), Inches(0.9)
BODY_W = W - PAD_X * 2

# 字号：下限 30pt，不可破
# 顶端几档与 HTML 模板同一套（0.8.0 起整体小一号：中文字身满格，180px 两行就重得像横幅）
SIZE = {"num": 140, "phrase": 72, "feature": 56, "title": 40,
        "sub": 30, "label": 30}

# 底色（0.10.1）：默认用和文字、讲的内容风格匹配的颜色，片单里写 "background"；没写就是纯黑。
# "tinted" 是 0.10.0 的带色近黑，"graphite" 是石墨，"light" 是亮教室用的浅色，"black" 是 "dark" 的别名
THEMES = ("dark", "black", "tinted", "graphite", "light")
INK_DARK, MUTED_ON_COLOR = "#f5f5f7", "#c7c7cc"

# 哪些片型默认逐个出现。片单里可以用 "build": false 关掉
BUILD = {"steps": True, "derive": True, "recap": True,
         "question": True, "myth": True, "specs": False, "versus": False}
# 哪些片型默认把讲过的调暗：只有一步接一步往下走的才调暗
DIM = {"steps": True, "derive": True}

# 能跨片配对的片型：值是「哪个对象参与 Morph」
MORPH_OK = {"title", "phrase", "close", "num", "section", "feature",
            "definition", "formula", "image", "claim"}


def rgb(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.lstrip("#").upper())


def luminance(color: RGBColor) -> float:
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: RGBColor, b: RGBColor) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ── 配色：模板与导出共用这一套算法，HTML 与 pptx 出来的颜色一样 ─────────────
def _hls_hex(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _hex_hls(color: str):
    c = color.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        raise ValueError(f"颜色要写成 #RRGGBB，收到 {color!r}")
    return colorsys.rgb_to_hls(*(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)))


def _cr(a: str, b: str) -> float:
    return contrast(rgb(a), rgb(b))


def palette_for_bg(bg: str, accent: str = None) -> dict:
    """给定一个底色（原样保留，不改），推出格子、分隔线、巨字、色场、调暗色，并核对比度。
    重点色压在底色上不到 4.5:1 时，按明度每次 +0.03 提亮，给出能用的值。"""
    bg = "#" + bg.strip().lstrip("#").lower()
    h, L, s = _hex_hls(bg)
    if s < 0.10:
        s = 0.0                          # 灰色底不带色相，免得推出一个随机的色相
    tile = _hls_hex(h, L + 0.03, s)
    line = _hls_hex(h, L + 0.14, s * 0.6)
    ghost = _hls_hex(h, L + 0.04, s)
    field = _hls_hex(h, max(L - 0.07, 0.03), 0.0 if s == 0 else min(s + 0.10, 0.70))
    fs, fl = min(s, 0.15), 0.40
    while not (_cr(bg, _hls_hex(h, fl, fs)) >= 3.2 and _cr(tile, _hls_hex(h, fl, fs)) >= 3.0) and fl < 0.95:
        fl = round(fl + 0.01, 2)
    out = {"bg": bg, "tile": tile, "line": line, "ghost": ghost, "field": field,
           "faint": _hls_hex(h, fl, fs), "ink": INK_DARK, "muted": MUTED_ON_COLOR,
           "fade_end": field, "accent": None, "notes": []}
    if accent:
        given = "#" + accent.strip().lstrip("#").lower()
        ah, al, as_ = _hex_hls(given)
        a = given
        while _cr(bg, a) < 4.5 and al < 0.9:
            al = round(al + 0.03, 2)
            a = _hls_hex(ah, al, as_)
        if a != given:
            out["notes"].append(f"重点色 {given} 压在底色上只有 {_cr(bg, given):.2f}:1，"
                                f"提亮成 {a}（{_cr(bg, a):.2f}:1）")
        out["accent"] = a
    out["checks"] = {"正文": _cr(bg, INK_DARK), "次要字": _cr(bg, MUTED_ON_COLOR),
                     "格子上的次要字": _cr(tile, MUTED_ON_COLOR), "调暗色": _cr(bg, out["faint"]),
                     "色场正文": _cr(field, INK_DARK)}
    if out["accent"]:
        out["checks"]["重点色"] = _cr(bg, out["accent"])
    return out


def matched_palette(color: str, sat: float = None, accent: str = None) -> dict:
    """匹配色（0.10.1）：色相取输入色，饱和度取 sat（没给就取输入色的，上限 0.60；
    灰色输入且没给 sat 时为 0），明度从 min(输入明度, 0.20) 起每次降 0.01，
    直到白字 ≥ 10:1、次要字 #c7c7cc ≥ 7:1。其余颜色由 palette_for_bg 从这个底色推出。"""
    if sat is not None and not 0 <= sat <= 1:
        raise ValueError(f"--sat 要在 0 到 1 之间（学术约 0.35，发布会约 0.45），收到 {sat}")
    h, l0, s0 = _hex_hls(color)
    # 灰色输入没有色相（colorsys 给灰色的色相是 0），这时给 --sat 只会长出一个随机的红色，所以照旧是中性灰
    s = 0.0 if s0 < 0.10 else min(sat if sat is not None else s0, 0.60)
    L = round(min(l0, 0.20), 2)
    while not (_cr(_hls_hex(h, L, s), INK_DARK) >= 10 and _cr(_hls_hex(h, L, s), MUTED_ON_COLOR) >= 7) and L > 0:
        L = round(L - 0.01, 2)
    return palette_for_bg(_hls_hex(h, L, s), accent)


def light_room(bg: str, accent: str = None) -> dict:
    """亮教室用浅色主题时（0.10.1）：页面是 #f5f5f7，匹配色只上封面、分节、静场的色场；
    重点色按明度每次降 0.01，压到 #f5f5f7 上过 4.5:1；巨字与渐变的浅端取匹配色的色相。"""
    bg = "#" + bg.strip().lstrip("#").lower()
    t = derive_palette(bg, "light")
    out = {"field": bg, "ghost": "#" + t["ghost"].lower(), "fade_end": "#" + t["fade_end"].lower(),
           "accent": None, "ratio": None}
    if accent:
        ah, al, as_ = _hex_hls(accent)
        a = "#" + accent.strip().lstrip("#").lower()
        while _cr(a, "#f5f5f7") < 4.5 and al > 0.05:
            al = round(al - 0.01, 2)
            a = _hls_hex(ah, al, as_)
        out["accent"], out["ratio"] = a, _cr(a, "#f5f5f7")
    return out


def derive_palette(accent: str, theme: str = "tinted") -> dict:
    """0.10.0 的带色近黑（theme "tinted"）与各主题的色场、巨字：HLS 取主色的色相。
    返回不带 # 的大写十六进制。主色接近灰色（饱和度 < 0.10）时用中性的一套。"""
    h, _, s = _hex_hls(accent)
    if s < 0.10:
        pal = {"bg": "161617", "tile": "1F1F21", "line": "3A3A3C", "faint": "6E6E73",
               "field": "2C2C2E", "ghost": "202022"}
        light_ghost, mist = _hls_hex(0, 0.925, 0), _hls_hex(0, 0.86, 0)
    else:
        L = 0.20
        while not (_cr(_hls_hex(h, L, 0.60), INK_DARK) >= 10 and _cr(_hls_hex(h, L, 0.60), "#c7c7cc") >= 7):
            L = round(L - 0.01, 2)
        pal = {"bg": _hls_hex(h, 0.085, 0.22), "tile": _hls_hex(h, 0.13, 0.16),
               "line": _hls_hex(h, 0.24, 0.10), "faint": _hls_hex(h, 0.47, 0.08),
               "field": _hls_hex(h, L, 0.60), "ghost": _hls_hex(h, 0.125, 0.22)}
        light_ghost, mist = _hls_hex(h, 0.925, 0.10), _hls_hex(h, 0.86, 0.25)
    pal = {k: v.lstrip("#").upper() for k, v in pal.items()}
    if theme == "light":
        pal["ghost"], pal["fade_end"] = light_ghost.lstrip("#").upper(), mist.lstrip("#").upper()
    else:
        pal["fade_end"] = pal["field"]
    return pal


def theme_palette(theme: str, accent: str, background: str = None) -> dict:
    """片单的 theme / background 落成一整套颜色（不带 # 的大写十六进制）与一句说明。"""
    if theme not in THEMES:
        raise ValueError(f"theme 只认 {'、'.join(THEMES)}，收到 {theme!r}")
    up = lambda c: c.lstrip("#").upper()
    tinted = derive_palette(accent, "light" if theme == "light" else "tinted")
    if background and theme == "light":
        # 亮教室：页面照旧浅色，匹配色只上色场（封面、分节、静场），巨字与渐变浅端取匹配色的色相
        room = light_room(background)
        pal = {"bg": "F5F5F7", "ink": "1D1D1F", "muted": "6E6E73", "faint": "86868B",
               "tile": "FFFFFF", "line": "D2D2D7", "ghost": up(room["ghost"]),
               "field": up(room["field"]), "fade_end": up(room["fade_end"])}
        pal["name"] = f"浅色 #F5F5F7，色场用匹配色 #{pal['field']}"
        return pal
    if background:
        m = palette_for_bg(background)
        pal = {k: up(m[k]) for k in ("bg", "ink", "muted", "faint", "field", "ghost", "fade_end", "tile", "line")}
        pal["name"] = f"匹配色 #{pal['bg']}"
        return pal
    if theme in ("dark", "black"):
        pal = {"bg": "000000", "ink": "F5F5F7", "muted": "98989D", "faint": "6E6E73",
               "tile": "1C1C1E", "line": "38383A", "ghost": "1C1C1E"}
        name = "黑色 #000000"
    elif theme == "tinted":
        pal = {k: tinted[k] for k in ("bg", "faint", "tile", "line", "ghost")}
        pal.update(ink="F5F5F7", muted="AEAEB2")
        name = f"带色近黑 #{pal['bg']}"
    elif theme == "graphite":
        pal = {"bg": "1C1C1E", "ink": "F5F5F7", "muted": "AEAEB2", "faint": "7C7C80",
               "tile": "2C2C2E", "line": "48484A", "ghost": "2A2A2C"}
        name = "石墨 #1C1C1E"
    else:
        pal = {"bg": "F5F5F7", "ink": "1D1D1F", "muted": "6E6E73", "faint": "86868B",
               "tile": "FFFFFF", "line": "D2D2D7", "ghost": tinted["ghost"]}
        name = "浅色 #F5F5F7"
    pal.update(field=tinted["field"], fade_end=tinted["fade_end"], name=name)
    return pal


# 各类字符占多少 em，按 Helvetica Neue 的字宽取的近似值。中日韩字是全宽，恒为 1 em
WIDTH = {"cjk": 1.0, "space": 0.28, "thin": 0.3, "narrow": 0.35,
         "digit": 0.56, "lower": 0.52, "upper": 0.68, "math": 0.6}


def est_width(text: str, size_pt: float) -> int:
    """粗估一行字的宽度（EMU）。实测偏差约 ±8%，够用来把两个文本框拼在一起居中，
    也够用来判断一行放不放得下（判断时留了余量）。"""
    em = 0.0
    for ch in str(text):
        if ord(ch) > 0x2E80:
            em += WIDTH["cjk"]
        elif ch == " ":
            em += WIDTH["space"]
        elif ch in "/|ilt’'":
            em += WIDTH["thin"]
        elif ch in ".,:;()[]-–−¹²³":
            em += WIDTH["narrow"]
        elif ch.isdigit():
            em += WIDTH["digit"]
        elif ch in "π√θ=+×÷≈≥≤":
            em += WIDTH["math"]
        elif ch.isupper():
            em += WIDTH["upper"]
        else:
            em += WIDTH["lower"]
    return int(Pt(size_pt * em))


class Deck:
    def __init__(self, spec: dict, animate: bool = True):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        self.accent_hex = spec.get("accent", "#5A8DEE")
        self.accent = rgb(self.accent_hex)
        self.theme = spec.get("theme", "dark")
        self.warnings = []
        self.use_palette(theme_palette(self.theme, self.accent_hex, spec.get("background")),
                         spec.get("background"), "片单最外层")
        if spec.get("background") and self.theme in ("black", "tinted", "graphite"):
            self.warnings.append(
                f"theme「{self.theme}」和 background 都写了：整套按 background 的匹配色出，theme 没用上。"
                f"要{ {'black': '纯黑', 'tinted': '带色近黑', 'graphite': '石墨'}[self.theme] }就删掉 background")
        self.font = spec.get("font", "Helvetica Neue")
        self.base = Path(spec.get("_base", "."))
        self.animate = animate
        self.motions = []
        self.m = None            # 当前这张片的出场顺序
        self.anchor = None       # 当前这张片参与 Morph 的对象

    def use_palette(self, pal, background=None, where="片单", check=True):
        """换一整套颜色：片单最外层用一次，单张片写了 "background" 时只在那一张换。
        匹配色过不了线、重点色太近都报出来，但不偷偷改使用者写的颜色。"""
        self.palette = pal
        self.bg, self.ink, self.muted = rgb(pal["bg"]), rgb(pal["ink"]), rgb(pal["muted"])
        self.faint, self.field, self.ghost = rgb(pal["faint"]), rgb(pal["field"]), rgb(pal["ghost"])
        self.fade_end = rgb(pal["fade_end"])
        if not check:
            return
        if background and getattr(self, "theme", "dark") == "light":
            text = contrast(self.field, rgb(INK_DARK))
            if text < 7:
                self.warnings.append(
                    f"{where}的色场 #{self.field} 上白字只有 {text:.2f}:1（要 7:1 以上）。用 --palette {background} 算一个压暗的")
            ratio = contrast(self.accent, self.bg)
            if ratio < 4.5:
                self.warnings.append(
                    f"{where}的重点色 #{self.accent} 压在浅色底上只有 {ratio:.2f}:1，要 4.5:1 以上。"
                    f"用 --palette {background} --accent #{self.accent} 打出的「亮教室」那一行")
        elif background:
            text, sub = contrast(self.bg, rgb(INK_DARK)), contrast(self.bg, rgb(MUTED_ON_COLOR))
            if text < 10 or sub < 7:
                self.warnings.append(
                    f"{where}的底色太亮：#{self.bg} 上白字只有 {text:.2f}:1、次要字 {sub:.2f}:1"
                    f"（要 10:1 与 7:1）。用 --palette {background} 算一个压暗的底色")
            ratio = contrast(self.accent, self.bg)
            if ratio < 4.5:
                self.warnings.append(
                    f"{where}的重点色 #{self.accent} 压在底色 #{self.bg} 上只有 {ratio:.2f}:1，"
                    f"要 4.5:1 以上。用 --palette {background} --accent #{self.accent} 算一个提亮的")
        else:
            # 调暗色与重点色的对比度按 WCAG 大字下限 3:1 核一遍，改配色后这里会报
            for name, color in (("调暗色", self.faint), ("重点色", self.accent)):
                ratio = contrast(color, self.bg)
                if ratio < 3.0:
                    self.warnings.append(
                        f"{name} #{color} 在底色 #{self.bg} 上只有 {ratio:.2f}:1，"
                        f"大字下限是 3:1（WCAG 1.4.3），换一个")

    def _ground(self, slide, d):
        """封面、分节、静场可以换底：色场（纯色、白字）或柔和渐变（底色 → 色场，上暗下亮）。
        返回这张片上的字该用的颜色；None 表示照常。"""
        ground = d.get("ground")
        if not ground:
            return None
        fill = slide.background.fill
        if ground == "field":
            fill.solid()
            fill.fore_color.rgb = self.field
            return rgb(INK_DARK)
        if ground == "fade":
            fill.gradient()
            # python-pptx 的角度写进 XML 时是反的：270 → a:lin ang=5400000，即 PowerPoint 的「线性向下」
            fill.gradient_angle = 270
            stops = fill.gradient_stops
            stops[0].color.rgb, stops[0].position = self.bg, 0.0
            stops[1].color.rgb, stops[1].position = self.fade_end, 1.0
        return None

    def slide(self):
        s = self.prs.slides.add_slide(self.blank)
        fill = s.background.fill
        fill.solid()
        fill.fore_color.rgb = self.bg
        self.m = motion.Motion(s)
        self.motions.append(self.m)
        self.anchor = None
        return s

    def text(self, slide, body, *, top, height, size, color=None,
             bold=False, align=PP_ALIGN.CENTER, left=None, width=None,
             wrap=True, inset=True, what=None, lines=None):
        """加一个文本框。会折行的框顺带过一遍 _fits：行数上限默认按框高算
        （1.2 倍行高，四舍五入，至少一行），要更严就传 lines。"""
        width = width if width is not None else BODY_W
        box = slide.shapes.add_textbox(
            left if left is not None else PAD_X,
            top,
            width,
            height,
        )
        if wrap:
            cap = lines or max(1, round(height / (Pt(size) * 1.2)))
            self._fits(body, size, width, what or f"第 {len(self.prs.slides)} 张", cap)
        tf = box.text_frame
        tf.word_wrap = wrap
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        if not inset:
            # 两个文本框要拼在一起时，去掉自带的内边距，接缝才准
            tf.margin_left = tf.margin_right = 0
        p = tf.paragraphs[0]
        p.alignment = align
        for n, line in enumerate(str(body).split("\n")):
            if n:
                p.add_line_break()
            run = p.add_run()
            run.text = line
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.name = self.font
            run.font.color.rgb = color or self.ink
        return box

    def _build(self, d, kind):
        """这张片要不要逐个出现。"""
        return bool(self.animate and d.get("build", BUILD.get(kind, False)))

    def _dim(self, d, kind):
        return bool(self._build(d, kind) and d.get("dim", DIM.get(kind, False)))

    def _cap(self, items, limit, what):
        """超出上限的项不静默丢掉，报出来让使用者自己决定拆片还是删。"""
        items = list(items)
        if len(items) > limit:
            self.warnings.append(f"{what}最多放 {limit} 项，多出来的 {len(items) - limit} 项没上片，"
                                 f"拆成两张或者删掉")
        return items[:limit]

    def _fits(self, text, size, width, what, lines=1):
        """按估宽算这段字会折成几行，超过上限就报。手工换行的那几行一起算进来。
        估宽有 ±8% 的偏差，所以判断时按 1.08 倍放宽，宁可漏报也不误报。"""
        usable = int(width - Inches(0.2))      # 栏宽按三等分算出来是小数，取整才好数行
        budget = max(1, int(usable / Pt(size)))
        shown = str(text).replace(chr(10), " / ")
        rendered = 0
        orphan = False
        for line in str(text).split("\n"):
            wide = int(est_width(line, size) / 1.08)
            rows = max(1, -(-wide // usable))
            rendered += rows
            # 末行只剩一两个字就是孤行，这一条在中文排版里最常出问题
            if rows > 1 and wide % usable < Pt(size) * 2:
                orphan = True
        if rendered > lines:
            self.warnings.append(
                f"{what}「{shown}」要占 {rendered} 行，"
                f"这里只放得下 {lines} 行（每行约 {budget} 个中文字），删字或者拆片")
        elif orphan:
            self.warnings.append(
                f"{what}「{shown}」折行后末行可能只剩一两个字（孤行），"
                f"用 \\n 在语义处手工断行，或者删字")

    def _step(self, shapes, step, dim_at=None):
        """一组形状同时出现，可选在某一步一起调暗。"""
        for shape in shapes:
            self.m.show(shape, step)
            if dim_at:
                self.m.recolor(shape, dim_at, self.faint)

    def _source(self, slide, d):
        """出处行：来源、样本量、测试条件（事实校验第 9 条），放左下、次要色、一行，
        和推演的出处同一个位置。它是证据，不是说明，所以不挪进备注。"""
        if d.get("source"):
            self.text(slide, d["source"], top=Inches(6.85), height=Inches(0.5),
                      size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT,
                      lines=1, what="出处行")

    # ── 各片型 ────────────────────────────────────────────
    def title(self, d):
        s = self.slide()
        color = self._ground(s, d)
        self.anchor = self.text(s, d["value"], top=Inches(2.4), height=Inches(1.9),
                                size=SIZE["phrase"], bold=True, color=color)
        # 论文讲读的标题卡写「论文讲读 · 作者 年份」，不让人以为是作者本人在讲
        self._source(s, d)

    def phrase(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(2.5), height=Inches(2.5),
                                size=SIZE["phrase"], bold=True)

    def num(self, d):
        s = self.slide()
        # 大数字默认白字。重点色只给「要区分的那个数」，由片单写 "accent": true 决定
        color = self.accent if d.get("accent") else self.ink
        value = str(d["value"])
        here = f"第 {len(self.prs.slides)} 张大数字「{value}」"
        # 按「[限定词␠]数字[单位]」切：限定词在前、和数字隔一个空格（「最长」「CO₂ 平均误差」），
        # 单位跟在后面（「小时视频播放」）。正负号认 + - − ±，货币符号算进数字
        m = re.match(r"^\s*(?:(\D+?)\s+)?([-+−±]?[¥$€£]?[\d.,，]+(?:\s*[×x/:：]\s*[\d.,]+)?)"
                     r"\s*(\D*)$", value)
        if not m:
            # 对比对象带版本号（「比 Drift 1 薄 30%」）：数字取最后一个，限定词里可以有数字，
            # 但不能有「=」或括号，「4.2 分（n = 30）」这种照旧切不开
            m = re.match(r"^\s*([^=（(]*\S)\s+([-+−±]?[¥$€£]?[\d.,，]+)\s*(\D*)$", value)
            # 限定词里的数字只能是跟在拉丁名字后面的版本号（「Drift 1」「iPhone 15」「M3」）；
            # 「12 月 1 日」「2 小时 30 分钟」「3 倍于 Drift 1」不算，照旧切不开
            if m and re.search(r"\d", re.sub(r"[A-Za-z][A-Za-z-]* ?\d+", "", m.group(1))):
                m = None
        pre, number, unit = ((m.group(1) or "").strip(), m.group(2), m.group(3).strip()) if m \
            else ("", value, "")
        # 「4K120」「M4」「A17 Pro」这种名字照原样排，不报。两处以上带数字（样本量、对比塞进了 value），
        # 或者中文贴着数字（「续航30天」漏了空格），才报
        if not m and (sum(bool(re.search(r"\d", t)) for t in value.split()) >= 2
                      or re.search(r"[⺀-￿]\d|\d[⺀-￿]", value)):
            self.warnings.append(f"{here}切不成「限定词 数字 单位」，整串按 {SIZE['num']}pt 排："
                                 f"一张只放一个数，限定词和数字隔一个空格，单位里不再带数字；"
                                 f"样本量、来源、测试条件写进 \"source\"（左下的出处行）")
        # 中文一字算一个，拉丁字母、数字与符号两个算一个（字宽约一半），空格不算
        extra = sum(1 if ord(c) > 0x2E80 else 0.5 for c in re.sub(r"\s", "", pre + unit))
        if extra > 8:
            self.warnings.append(f"{here}的限定词和单位共 {extra:g} 个字（中文一字算一个，"
                                 f"拉丁字母与符号两个算一个，空格不算），最多 8 个："
                                 f"删掉能省的字，「最长」「平均」这类限定条件留着；"
                                 f"来源、样本量、测试条件写进 \"source\"")
        self.anchor = self.text(s, number, top=Inches(2.0), height=Inches(2.6),
                                size=SIZE["num"], bold=True, color=color)
        # 限定词与单位缩到 0.4 倍，和 HTML 的 .pre / .unit 一致：「3 倍」的「倍」和 3 一样大，整片就重了
        small = round(SIZE["num"] * 0.4)
        para = self.anchor.text_frame.paragraphs[0]
        pre_text = pre + " " if pre else ""
        unit_text = unit if unit in ("%",) else (" " + unit if unit else "")
        for text in (unit_text, pre_text):
            if text:
                run = para.add_run()
                run.text = text
                run.font.size = Pt(small)
                run.font.bold = True
                run.font.name = self.font
                run.font.color.rgb = color
        if pre_text:
            para.runs[0]._r.addprevious(para.runs[-1]._r)     # 限定词挪到数字前面
        # text() 只核了数字。限定词和单位接在同一行，连起来再核一次（数字自己放不下时上面已经报过）
        usable = int(BODY_W - Inches(0.2))
        alone = int(est_width(number, SIZE["num"]) / 1.08)
        whole = int((est_width(pre_text, small) + est_width(number, SIZE["num"])
                     + est_width(unit_text, small)) / 1.08)
        if alone <= usable < whole:
            self.warnings.append(f"{here}连限定词和单位要占 {-(-whole // usable)} 行，这里只放得下 1 行："
                                 f"限定词不删，单位删字，来源与测试条件写进 \"source\"，或者拆片")
        self._source(s, d)
        # 未确认项在片上必须看得见，不能只写在大纲里
        if d.get("unverified"):
            self.text(s, "未确认", top=Inches(4.9),
                      height=Inches(0.6), size=SIZE["label"], color=self.muted)

    def section(self, d):
        s = self.slide()
        color = self._ground(s, d)
        # 分节标题用正文色，和 HTML 的 .feature 一样；色场上 _ground 给的是白字
        self.anchor = self.text(s, d["value"], top=Inches(3.1), height=Inches(1.3),
                                size=SIZE["title"], color=color)

    def rest(self, d):
        """静场：讲故事、举例、答问时切到这一张，屏幕上没有要读的字，注意力回到讲的人身上。
        给了 value 就在右下角画一个同色调巨字（比底色略亮），只作氛围，最多 4 个字。"""
        s = self.slide()
        self._ground(s, d)
        value = str(d.get("value") or "").strip()
        if not value:
            return
        if d.get("ground") == "field":
            self.warnings.append(f"静场「{value}」在色场上不画巨字：巨字是比底色略亮的氛围，压在色场上会刺眼；"
                                 f"要巨字就用底色或 \"fade\"")
            return
        weight = sum(1 if ord(c) > 0x2E80 else 0.5 for c in value if not c.isspace())
        if weight > 4:
            self.warnings.append(f"静场的巨字「{value}」最多 4 个字（中文算 1，其余算半个），"
                                 f"它只作氛围，不是要读的字")
        box = s.shapes.add_textbox(W - Inches(7.6), H - Inches(5.6), Inches(7.6), Inches(5.6))
        tf = box.text_frame
        tf.word_wrap = False
        tf.vertical_anchor = MSO_ANCHOR.BOTTOM
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        run = p.add_run()
        run.text = value
        run.font.size = Pt(380)
        run.font.bold = True
        run.font.name = self.font
        run.font.color.rgb = self.ghost

    def feature(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(2.6), height=Inches(1.4),
                                size=SIZE["feature"], bold=True)

    def specs(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        items = self._cap(d.get("items", []), 6, "规格密排")
        build = self._build(d, "specs")
        # 两项、四项排成两列（2 × 2，和 HTML 示例一致），其余排三列。三列里一格只放得下三个 64pt 的字
        cols = 2 if len(items) in (2, 4) else 3
        col_w = BODY_W / cols
        for n, (k, v) in enumerate(items):
            if v is None or not str(v).strip():
                self.warnings.append(f"第 {len(self.prs.slides)} 张规格密排第 {n + 1} 项「{k}」没有值："
                                     f"规格是项名加值成对，只有名字的并列项换成流程条或功能名片")
            cx = PAD_X + col_w * (n % cols)
            cy = Inches(2.6) + Inches(1.9) * (n // cols)
            label = self.text(s, k, top=cy, height=Inches(0.55), size=SIZE["label"],
                              color=self.muted, align=PP_ALIGN.LEFT,
                              left=cx, width=col_w - Inches(0.3))
            value = self.text(s, v, top=cy + Inches(0.6), height=Inches(0.9), size=64,
                              bold=True, align=PP_ALIGN.LEFT,
                              left=cx, width=col_w - Inches(0.3))
            if build:
                self._step([label, value], n + 1)

    def versus(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        items = d.get("items", [])[:2]
        build = self._build(d, "versus")
        col_w = BODY_W / 2
        for n, (head, val) in enumerate(items):
            cx = PAD_X + col_w * n
            # 列头必须标明对比的轴，否则「快 3 倍」是没有对象的说法
            label = self.text(s, head, top=Inches(2.6), height=Inches(0.7),
                              size=SIZE["sub"], color=self.muted,
                              left=cx, width=col_w - Inches(0.4))
            value = self.text(s, val, top=Inches(3.4), height=Inches(1.8), size=88,
                              bold=True, color=self.accent if n else self.ink,
                              left=cx, width=col_w - Inches(0.4))
            if build:
                self._step([label, value], n + 1)
        # 对比的版本与测试时间（事实校验第 4 条）写进出处行
        self._source(s, d)

    def price(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(1.4), height=Inches(1.0),
                  size=SIZE["title"], bold=True)
        items = d.get("items", [])[:3]
        if items:
            col_w = BODY_W / len(items)
            for n, (p, cfg) in enumerate(items):
                # 价格下面只放配置名。发售日期垫在这里就是大字下面的第二层字
                if re.search(r"\d+\s*月\s*\d+\s*日|发售|上市|开售|预售", str(cfg)):
                    self.warnings.append(f"第 {len(self.prs.slides)} 张价格「{p}」下面的「{cfg}」"
                                         f"像发售日期：价格下面那一格只放配置名（「标准版」），"
                                         f"发售日期由讲的人说，非要上片就单独做一张单句大字")
                cx = PAD_X + col_w * n
                self.text(s, p, top=Inches(3.0), height=Inches(1.4), size=60,
                          bold=True, color=self.ink,
                          left=cx, width=col_w)
                self.text(s, cfg, top=Inches(4.4), height=Inches(0.7),
                          size=SIZE["sub"], color=self.muted,
                          left=cx, width=col_w)

    def quote(self, d):
        s = self.slide()
        self.text(s, f"「{d['value']}」", top=Inches(2.2), height=Inches(2.8),
                  size=54, bold=False)
        # 出处必须写。没有出处的引语是把编的话当证据用
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(5.2), height=Inches(0.7),
                      size=SIZE["sub"], color=self.muted)

    def steps(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        items = self._cap(d.get("items", []), 5, "流程条")
        if not items:
            return
        build, dim = self._build(d, "steps"), self._dim(d, "steps")
        col_w = BODY_W / len(items)
        for n, name in enumerate(items):
            cx = PAD_X + col_w * n
            # 每一步只有名字：一句说明是讲的人说的，fold_into_notes 已把它挪进备注
            group = [
                self.text(s, f"{n + 1:02d}", top=Inches(2.9), height=Inches(0.6),
                          size=SIZE["label"], color=self.faint, align=PP_ALIGN.LEFT,
                          left=cx, width=col_w - Inches(0.2)),
                self.text(s, name, top=Inches(3.5), height=Inches(0.9), size=44,
                          bold=True, align=PP_ALIGN.LEFT,
                          left=cx, width=col_w - Inches(0.2)),
            ]
            if build:
                self._step(group, n + 1, n + 2 if dim and n + 1 < len(items) else None)

    def close(self, d):
        self.phrase(d)

    # ── 课堂与讲堂 ────────────────────────────────────────
    def _box(self, slide, left, top, width, height, rgb, alpha=None):
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
        shape.line.fill.background()
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb
        if alpha is not None:
            # python-pptx 没有透明度接口，直接写 <a:alpha>
            clr = shape.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
            clr.append(clr.makeelement(qn("a:alpha"), {"val": str(int(alpha * 100000))}))
        return shape

    def _image_stream(self, path):
        """转正并重新编码，丢掉 EXIF（含 GPS）。返回 (流, 宽, 高)。"""
        if Image is None:
            sys.exit("带图的片型需要 Pillow。装：pip3 install pillow")
        src = (self.base / path).resolve()
        if not src.is_file():
            raise FileNotFoundError(path)
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            buf = io.BytesIO()
            if im.mode in ("RGBA", "LA", "P"):
                im.save(buf, "PNG", optimize=True)
            else:
                im.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
            size = im.size
        buf.seek(0)
        return buf, size[0], size[1]

    def _cover(self, slide, path, left, top, width, height, focus=(0.5, 0.5)):
        stream, w, h = self._image_stream(path)
        pic = slide.shapes.add_picture(stream, left, top, width, height)
        box, img = width / height, w / h
        fx, fy = focus
        if img > box:                      # 太宽，左右裁
            cut = 1 - box / img
            pic.crop_left = cut * fx
            pic.crop_right = cut * (1 - fx)
        elif img < box:                    # 太高，上下裁
            cut = 1 - img / box
            pic.crop_top = cut * fy
            pic.crop_bottom = cut * (1 - fy)
        return pic

    def _contain(self, slide, path, left, top, width, height):
        stream, w, h = self._image_stream(path)
        scale = min(width / w, height / h)
        pw, ph = int(w * scale), int(h * scale)
        return slide.shapes.add_picture(
            stream, left + (width - pw) // 2, top + (height - ph) // 2, pw, ph)

    def _pair(self, slide, left_text, right_text, *, top, height, size, gap_em=0.3,
              left_color=None, right_color=None, bold=False):
        """左右两块字拼成一行，接缝对齐：左块右对齐、右块左对齐，整体按估宽居中。
        拆成两个形状是为了让左边那个符号能单独参与 Morph。返回 (左形状, 右形状)。"""
        lw, rw = est_width(left_text, size), est_width(right_text, size)
        gap = int(Pt(size * gap_em))
        seam = int((W - (lw + gap + rw)) / 2) + lw
        slack = int(Pt(size))          # 估宽偏小也不至于挤掉字
        left = self.text(slide, left_text, top=top, height=height, size=size,
                         color=left_color, bold=bold, align=PP_ALIGN.RIGHT,
                         left=max(0, seam - lw - slack), width=lw + slack,
                         wrap=False, inset=False)
        right = self.text(slide, right_text, top=top, height=height, size=size,
                          color=right_color, bold=bold, align=PP_ALIGN.LEFT,
                          left=seam + gap, width=rw + slack, wrap=False, inset=False)
        return left, right

    def roadmap(self, d):
        s = self.slide()
        stops = self._cap(d.get("items", []), 4, "路线的站点")
        cur = d.get("current")
        if not stops:
            return
        col_w = BODY_W / len(stops)
        for n, name in enumerate(stops):
            color = self.ink if n == cur else self.muted
            self.text(s, name, top=Inches(3.1), height=Inches(1.2), size=SIZE["title"],
                      bold=(n == cur), color=color, left=PAD_X + col_w * n, width=col_w)

    def _question_page(self, d, answer, reveal):
        """画一张提问片。reveal 为真时直接画成揭晓后的样子（没有动画时用）。
        返回选项形状表。揭晓的依据由讲的人说，不上片。"""
        s = self.slide()
        if d.get("kicker"):
            self.text(s, d["kicker"], top=Inches(1.3), height=Inches(0.6),
                      size=SIZE["label"], bold=True, color=self.muted)
        self.text(s, d["value"], top=Inches(2.0), height=Inches(1.3),
                  size=SIZE["title"], bold=True)
        boxes = []
        options = self._cap(d.get("items", []), 4, "提问的选项")
        if options:
            col_w = BODY_W / len(options)
            for n, opt in enumerate(options):
                hit = reveal and n == answer
                color = self.accent if hit else (self.faint if reveal else self.ink)
                boxes.append(self.text(s, opt, top=Inches(3.6), height=Inches(1.1),
                                       size=36, bold=True, color=color,
                                       left=PAD_X + col_w * n, width=col_w - Inches(0.2)))
        return boxes

    def question(self, d):
        answer = d.get("answer")
        # 预测题不给 answer，只出题目这一张，讲完再用另一条片单揭晓
        if answer is None:
            self._question_page(d, None, False)
            return
        if self._build(d, "question"):
            boxes = self._question_page(d, answer, False)
            for n, box in enumerate(boxes):
                self.m.recolor(box, 1, self.accent if n == answer else self.faint)
            return
        # 没有动画：拆成题目与揭晓两张，不然答案一上来就摆在那儿
        self._question_page(d, answer, False)
        self._question_page(d, answer, True)

    def image(self, d):
        s = self.slide()
        if not d.get("src"):
            self.warnings.append(f"满版图「{d.get('value', '')}」没有给 src，这张只放了文字")
        else:
            try:
                self.anchor = self._cover(s, d["src"], 0, 0, W, H,
                                          tuple(d.get("focus", (0.5, 0.5))))
            except FileNotFoundError as exc:
                self.warnings.append(f"满版图找不到图片 {exc}，这张只放了文字")
        # 底部 32% 恒为 0.72 的黑，与 HTML 模板一致
        band = int(H * 0.32)
        self._box(s, 0, H - band, W, band, RGBColor(0, 0, 0), alpha=0.72)
        white = RGBColor(0xFF, 0xFF, 0xFF)
        soft = RGBColor(0xC7, 0xC7, 0xC7)
        self.text(s, d.get("value", ""), top=H - band + Inches(0.3), height=Inches(1.0),
                  size=SIZE["title"], bold=True, color=white, align=PP_ALIGN.LEFT)
        if d.get("credit"):
            self.text(s, d["credit"], top=H - Inches(0.62), height=Inches(0.5), size=SIZE["label"],
                      color=soft, align=PP_ALIGN.RIGHT, left=Inches(0.3), width=W - Inches(0.6))
        elif d.get("src"):
            self.warnings.append(f"满版图「{d.get('value', '')}」有图但没有来源行（credit）")

    def claim(self, d):
        s = self.slide()
        # 主张句一行（0.10.0）：一行放不下就是还没想清楚，删字或者拆片
        claim = self.text(s, d["value"], top=PAD_Y, height=Inches(1.4), size=40,
                          bold=True, align=PP_ALIGN.LEFT, lines=1, what="主张句")
        self.anchor = claim
        if d.get("src"):
            try:
                self.anchor = self._contain(s, d["src"], PAD_X, Inches(2.4),
                                            BODY_W, Inches(3.9))
            except FileNotFoundError as exc:
                self.warnings.append(f"证据图找不到：{exc}")
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(6.5), height=Inches(0.55),
                      size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT)

    def definition(self, d):
        s = self.slide()
        if d.get("symbol"):
            # 术语与符号分成两个形状：符号要能单独跟下一张公式里的同一个符号配对
            term, sym = self._pair(s, d["value"], d["symbol"], top=Inches(2.5),
                                   height=Inches(1.4), size=SIZE["feature"], bold=True)
            self.anchor = sym
        else:
            self.anchor = self.text(s, d["value"], top=Inches(2.5), height=Inches(1.4),
                                    size=SIZE["feature"], bold=True)

    def derive(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.2), size=40,
                  bold=True, align=PP_ALIGN.LEFT)
        rows = self._cap(d.get("items", []), 4, "推演")
        build, dim = self._build(d, "derive"), self._dim(d, "derive")
        # 右栏先按「30pt 下每行 9 个中文字」定宽，式子列拿剩下的；依据的名字一行、8 字内（0.10.0），
        # 宽出来的一个字是余量
        gap, why_w = int(Pt(18)), int(Pt(9 * SIZE["label"]) + Inches(0.2))
        expr_w = BODY_W - why_w - gap
        why_left = PAD_X + expr_w + gap
        for n, row in enumerate(rows):
            expr, why = (list(row) + [""])[:2] if isinstance(row, (list, tuple)) else (row, "")
            y = Inches(2.2) + Inches(1.15) * n
            # 式子一行：行距 1.15 英寸，折成两行就压到下一行
            group = [self.text(s, expr, top=y, height=Inches(1.0), size=36,
                               align=PP_ALIGN.LEFT, left=PAD_X, width=expr_w,
                               what="推演的式子", lines=1)]
            if why:
                # 右栏一行：写依据的名字，8 字内（0.10.0 起，不再两行）
                group.append(self.text(s, why, top=y, height=Inches(1.0),
                                       size=SIZE["label"], color=self.muted,
                                       align=PP_ALIGN.LEFT, left=why_left, width=why_w,
                                       what="推演右栏", lines=1))
            if build:
                self._step(group, n + 1, n + 2 if dim and n + 1 < len(rows) else None)
        if d.get("caption"):
            cite = self.text(s, d["caption"], top=Inches(6.85), height=Inches(0.5),
                             size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT)
            at = d.get("caption_at")
            if build and at:
                self.m.show(cite, min(int(at), max(len(rows), 1)))
        self.warnings.append(f"推演「{d['value']}」的式子是纯文本，"
                             f"要在 PowerPoint 或 Keynote 的公式编辑器里重排")

    def formula(self, d):
        s = self.slide()
        value = str(d["value"])
        # 近似式写 ≈（小角度下的单摆周期），和等号一样在这里切开
        cut = min((i for i in (value.find("="), value.find("≈")) if i > 0), default=-1)
        head, sep, tail = (value[:cut], value[cut], value[cut + 1:]) if cut > 0 else (value, "", "")
        # 适用条件写在式子同一行，所以只给一行：折成两行就是条件太长，该挪进主张句或出处行
        if d.get("morph") and sep and head.strip():
            # 等号左边单独成一个形状，才能跟上一张概念片里的同一个符号配对。拼出来的两块不折行，另核一次
            self._fits(value, SIZE["feature"], BODY_W, "公式", 1)
            left, _ = self._pair(s, head.strip(), sep + tail, top=Inches(2.2),
                                 height=Inches(1.6), size=SIZE["feature"], gap_em=0.22)
            self.anchor = left
        else:
            self.anchor = self.text(s, value, top=Inches(2.2), height=Inches(1.6),
                                    size=SIZE["feature"], lines=1, what="公式")
        # 写不短的适用条件（「不计空气阻力」）进左下的出处行，和数字的限定条件一样不能丢
        self._source(s, d)
        self.warnings.append(f"公式「{value}」是纯文本，"
                             f"要在 PowerPoint 或 Keynote 的公式编辑器里重排")

    def myth(self, d):
        s = self.slide()
        reveal = self._build(d, "myth")
        self.text(s, "常见误解", top=Inches(1.5), height=Inches(0.6), size=SIZE["label"],
                  bold=True, color=self.muted, align=PP_ALIGN.LEFT)
        said = self.text(s, d["value"], top=Inches(2.1), height=Inches(1.1), size=44,
                         bold=True, color=self.ink if reveal else self.muted,
                         align=PP_ALIGN.LEFT)
        # 正确说法揭晓时不再加「实际上」标签：误解已经调暗，下面这句是什么一看就知道
        fact = self.text(s, d.get("caption", ""), top=Inches(3.9), height=Inches(1.1),
                         size=44, bold=True, align=PP_ALIGN.LEFT)
        if reveal:
            # HTML 里揭晓时给误解划线，pptx 划不了线，改成把误解调暗
            self.m.recolor(said, 1, self.faint)
            self.m.show(fact, 1)

    def recap(self, d):
        s = self.slide()
        self.text(s, d.get("value", "回顾"), top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        build = self._build(d, "recap")
        if d.get("value") == "贡献":
            # 贡献：带走的那几句就是这张片的主体，正文色、大字、一次出齐，问答时一直停着
            for n, (_, point) in enumerate(self._cap(d.get("items", []), 3, "贡献")):
                self.text(s, point, top=Inches(2.3) + Inches(1.15) * n, height=Inches(1.0),
                          size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT, lines=1, what="贡献")
            return
        for n, (cue, point) in enumerate(self._cap(d.get("items", []), 3, "回顾")):
            y = Inches(2.3) + Inches(1.15) * n
            self.text(s, cue, top=y, height=Inches(0.9), size=32, bold=True,
                      align=PP_ALIGN.LEFT, left=PAD_X, width=Inches(2.6))
            box = self.text(s, point, top=y, height=Inches(0.9), size=SIZE["sub"],
                            color=self.muted, align=PP_ALIGN.LEFT,
                            left=PAD_X + Inches(2.8), width=BODY_W - Inches(2.8))
            if build:
                # 提示词一直在，要点点一下出一条：先让听众自己想
                self.m.show(box, n + 1)

    def refs(self, d):
        items = d.get("items", [])
        # 30pt 下一张放 4 条，多了自动续页
        for start in range(0, max(len(items), 1), 4):
            s = self.slide()
            title = d.get("value", "参考文献") + ("（续）" if start else "")
            self.text(s, title, top=PAD_Y, height=Inches(1.0), size=SIZE["title"],
                      bold=True, align=PP_ALIGN.LEFT)
            page = items[start:start + 4]
            # 这一页有几条就把 4.8 英寸分几份：一条长英文文献要四行，只给两行的高度会被截
            slot = Inches(4.8) / max(len(page), 1)
            for n, ref in enumerate(page):
                self.text(s, ref, top=Inches(2.2) + int(slot * n), height=int(slot - Inches(0.1)),
                          size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT)


# 一张片一层字（0.9.0）：大字下面不垫说明小字，说明是讲的人说的（冗余原则：图加旁白优于图加旁白加
# 同样的屏幕文字）。这些片型的 caption 不上片，挪进讲者备注；引语的出处、主张与推演的出处、
# 误解片的正确说法照旧上片
CAPTION_TO_NOTES = {"title", "phrase", "num", "section", "feature", "price", "close",
                    "question", "image", "definition", "formula"}


def fold_into_notes(spec):
    """把不再上片的说明小字挪进讲者备注。返回 (新片单, 提示)：旧片单照样能导，一个字也不丢。"""
    slides, notices = [], []
    for n, d in enumerate(spec.get("slides") or [], 1):
        if not isinstance(d, dict):
            slides.append(d)
            continue
        d, kind, moved = dict(d), d.get("type"), []
        if kind in CAPTION_TO_NOTES and d.get("caption"):
            moved.append(str(d.pop("caption")))
        if kind == "steps":
            names = []
            for item in d.get("items") or []:
                if isinstance(item, (list, tuple)):
                    if len(item) > 2:
                        raise SpecError(f"片单第 {n} 张（steps）有一步写了 {len(item)} 项，"
                                        f"每一步只认 [名字, 说明] 两项")
                    name, desc = (list(item) + ["", ""])[:2]
                    if desc:
                        moved.append(f"{name}：{desc}")
                    names.append(name)
                else:
                    names.append(item)
            d["items"] = names
        if kind == "formula" and d.get("items"):
            moved.append("；".join(str(i) for i in d.pop("items")))
        if moved:
            said = "\n".join(moved)
            # 不直接并进 notes：--static 下提问片拆成两张，揭晓的依据只能写进揭晓那张（build() 里分）
            d["_moved"] = f"片上不放，讲出来：{said}"
            tail = ("限定词和单位写进 value，和数字同一行；出处、样本量写进 \"source\"" if kind == "num"
                    else "适用条件写在式子同一行（「θ ≪ 1」）；写不短的写进 \"source\"（左下的出处行）"
                    if kind == "formula"
                    else "非要留在片上的限定条件，写进大字或数字的单位里")
            notices.append(f"片单第 {n} 张（{kind}）大字下面的说明「{' / '.join(moved)}」挪进了讲者备注："
                           f"一张片一层字。{tail}")
        slides.append(d)
    return dict(spec, slides=slides), notices


KINDS = ("title", "phrase", "num", "section", "feature",
         "specs", "versus", "price", "close", "quote", "steps",
         "roadmap", "question", "image", "claim", "definition",
         "derive", "formula", "myth", "recap", "refs", "rest")
# 片单里认的字段。以 _ 开头的是注释（如 "_note"），不查
TOP_KEYS = {"accent", "theme", "font", "slides", "background"}
SLIDE_KEYS = {"type", "value", "caption", "items", "notes", "build", "dim", "morph",
              "unverified", "kicker", "answer", "current", "src", "credit", "focus",
              "symbol", "caption_at", "source", "ground", "background"}
# 换底（"ground"）只给封面、分节、静场；内容片一律平涂
GROUND_KINDS = {"title", "section", "rest"}
# 出处行（"source"）只有大数字、双列对比与公式画，别的片型的出处各有字段
SOURCE_KINDS = {"num", "versus", "formula", "title"}


class SpecError(Exception):
    """片单格式不对。报出来就停，不写文件。"""


def unknown_keys(spec):
    """拼错的字段会被静默忽略（比如 "bulid": true 就不分步），所以逐个报出来。"""
    notes = []
    extra = sorted(k for k in spec if k not in TOP_KEYS and not str(k).startswith("_"))
    if extra:
        notes.append(f"片单最外层有不认识的字段 {', '.join(extra)}，没用上")
    for n, d in enumerate(spec["slides"], 1):
        extra = sorted(k for k in d if k not in SLIDE_KEYS and not str(k).startswith("_"))
        if extra:
            notes.append(f"片单第 {n} 张（{d.get('type')}）有不认识的字段 {', '.join(extra)}，没用上")
        if d.get("ground") and (d.get("type") not in GROUND_KINDS or d.get("ground") not in ("field", "fade")):
            notes.append(f"片单第 {n} 张（{d.get('type')}）的 ground「{d.get('ground')}」没用上："
                         f"只有 title、section、rest 认，值只能是 \"field\" 或 \"fade\"")
        if d.get("source") and d.get("type") not in SOURCE_KINDS:
            notes.append(f"片单第 {n} 张（{d.get('type')}）的 \"source\" 只有 title、num、versus 与 formula 认，没上片："
                         f"主张与推演的出处写进 \"caption\"，满版图的来源写进 \"credit\"")
    return notes


def build(spec, animate=True):
    """按片单把整份 pptx 建好，不存盘。
    返回 (deck, 不认识的片型, Morph 处数, 点击次数, 分步的片数)；格式不对抛 SpecError。"""
    slides = spec.get("slides")
    if not isinstance(slides, list) or not all(isinstance(d, dict) for d in slides):
        raise SpecError("slides 要是一个列表，每张片是一个 {...}")
    if spec.get("theme", "dark") not in THEMES:
        raise SpecError(f"theme 只认 {'、'.join(THEMES)}，收到 {spec.get('theme')!r}")
    try:
        deck = Deck(spec, animate=animate)
    except ValueError as exc:
        raise SpecError(f"accent 与 background 要写成 #RRGGBB，收到 accent {spec.get('accent')!r}、"
                        f"background {spec.get('background')!r}（{exc}）") from exc
    deck.warnings.extend(unknown_keys(spec))
    spec, folded = fold_into_notes(spec)
    slides = spec["slides"]
    deck.warnings.extend(folded)
    handlers = {name: getattr(deck, name) for name in KINDS}

    unknown, morphs, prev_key, prev_text, prev_kind, paired = set(), 0, None, None, None, {}
    for n, d in enumerate(slides, 1):
        kind = d.get("type")
        fn = handlers.get(kind) if isinstance(kind, str) else None
        if fn is None:
            unknown.add(str(kind))
            continue
        before = len(deck.prs.slides)
        saved = None
        try:
            if d.get("background"):
                # 章节换色：这一张换一套颜色，做完换回来
                saved = deck.palette
                deck.use_palette(theme_palette(deck.theme, deck.accent_hex, d["background"]),
                                 d["background"], f"片单第 {n} 张")
            fn(d)
        except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
            what = f"缺字段 {exc}" if isinstance(exc, KeyError) else f"{type(exc).__name__}: {exc}"
            raise SpecError(f"片单第 {n} 张（{kind}）格式不对：{what}。"
                            f"对照 --help 里的片单格式改") from exc
        finally:
            if saved is not None:
                deck.use_palette(saved, check=False)
        made = [deck.prs.slides[k] for k in range(before, len(deck.prs.slides))]
        # 一张片单可能生成多张（提问、参考文献续页），备注每张都写
        for i, s in enumerate(made):
            parts = [str(d["notes"])] if d.get("notes") else []
            # --static 下提问片拆成题目与揭晓两张：挪进来的揭晓依据只写进揭晓那张
            if d.get("_moved") and (kind != "question" or i == len(made) - 1):
                parts.append(d["_moved"])
            if parts:
                s.notes_slide.notes_text_frame.text = "\n".join(parts)

        key = d.get("morph")
        this_key = this_text = None
        if key and animate:
            if kind not in MORPH_OK or deck.anchor is None or len(made) != 1:
                deck.warnings.append(f"「{kind}」这类片没有可配对的对象，morph「{key}」没做")
            else:
                this_text = (deck.anchor.text_frame.text.strip()
                             if getattr(deck.anchor, "has_text_frame", False) else None)
                if ("formula" in (kind, prev_kind) and prev_key == key and prev_text is not None
                        and this_text != prev_text):
                    # 公式只有等号左边那一块能配对。上一张的 g 配到「h = ½gt²」，就是把 g 变成 h
                    deck.warnings.append(
                        f"morph「{key}」两端的字不一样（「{prev_text}」→「{this_text}」）："
                        f"pptx 里公式只有等号左边那一块能配对，没做 Morph；要配右边的符号只在 HTML 里配")
                    paired[key] = True        # 原因已经报过，不再报「没有配对成功」
                    this_text = None
                else:
                    motion.morph(deck.anchor, key)
                    this_key = key
                    paired.setdefault(key, False)
                    if prev_key == key:
                        motion.transition(made[0], "morph", motion.MORPH_MS)
                        paired[key] = True
                        morphs += 1
        prev_key, prev_text, prev_kind = this_key, this_text, kind

    for key, done in paired.items():
        if not done:
            deck.warnings.append(f"morph「{key}」没有配对成功："
                                 f"要相邻两张片各有一个同名的对象，隔着别的片配不上")

    clicks = sum(m.write() for m in deck.motions)
    stepped = sum(1 for m in deck.motions if m.cues)
    return deck, unknown, morphs, clicks, stepped


def selftest() -> int:
    """审计复现的几个输入当回归用例，外加一份正常片单。通过退出 0，否则 1。"""
    import subprocess
    import tempfile

    def texts(prs):
        return {sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame}

    def fit_notes(deck):
        return [w for w in deck.warnings if "要占" in w or "孤行" in w]

    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        def deck_of(*slides, **extra):
            return build(dict({"slides": list(slides), "_base": tmp}, **extra))

        # 审计复现：36 个字的单句大字要排五行，原来只在推演片上查，这里一声不吭
        long = "这是一句为了测试而故意写得非常长的单句大字，一共三十六个字，排出来超出画"
        deck = deck_of({"type": "phrase", "value": long})[0]
        checks.append((f"{len(long)} 字的单句大字报放不下", any("要占" in w for w in deck.warnings)))
        # 72pt 下一行放得下 10 个字（0.8.0 起的字号），所以用 12 个字：折成 10 + 2，末行是孤行
        deck = deck_of({"type": "phrase", "value": "练了多久，还是没人说得清"})[0]
        checks.append(("逗号连着的十二个字自己折行，报孤行", any("孤行" in w for w in deck.warnings)))
        deck = deck_of({"type": "phrase", "value": "练了多久，没人说得清"})[0]
        checks.append(("十个字的单句大字一行放得下，不报", not fit_notes(deck)))
        deck = deck_of({"type": "num", "value": "3 倍"})[0]
        runs = [r.text for r in deck.prs.slides[0].shapes[0].text_frame.paragraphs[0].runs]
        checks.append(("大数字的单位单独一段、缩小", runs == ["3", " 倍"]))
        deck = deck_of({"type": "phrase", "value": "练了多久\n没人说得清"})[0]
        checks.append(("手工断成两行的单句大字不报", not deck.warnings))

        # 规格密排默认一次出齐，写 "build": true 才逐个出（与 SKILL.md 阶段三一致）
        specs = {"type": "specs", "value": "规格", "items": [["续航", "30 天"], ["重量", "24 克"]]}
        plain, stepped = deck_of(specs)[3], deck_of(dict(specs, build=True))[3]
        checks.append(("规格密排默认 0 步，写 build: true 才 2 步", (plain, stepped) == (0, 2)))

        # 降级表补上的五类：时刻、信号汇入、取舍、one more thing、环保，都要真的导出来
        five = [
            {"type": "phrase", "value": "整屏只剩一张照片和一个光标"},
            {"type": "steps", "value": "建议的来处", "build": False,
             "items": ["照片", "地点", "写作建议"]},
            {"type": "steps", "value": "取舍", "items": ["不做社交", "不做排行"]},
            {"type": "phrase", "value": "One more thing"},
            {"type": "feature", "value": "环保"},
        ]
        deck, unknown, _, clicks, _ = deck_of(*five)
        out = Path(tmp) / "five.pptx"
        deck.prs.save(str(out))
        again = Presentation(str(out))
        want = {"整屏只剩一张照片和一个光标", "写作建议", "不做排行", "One more thing", "环保"}
        checks.append(("降级表的五类都导出了，字一个不少",
                       not unknown and len(again.slides) == 5 and want <= texts(again)))
        checks.append(("信号汇入一次出齐，取舍逐条出（共 2 次点击）", clicks == 2))
        checks.append(("这五张没有放不下的字", not fit_notes(deck)))
        checks.append(("不认识的片型报出来，不静默", deck_of({"type": "moment"})[1] == {"moment"}))

        # 一张片一层字：旧片单里大字下面的说明不上片，挪进讲者备注并提示；引语的出处照旧上片
        deck = deck_of({"type": "feature", "value": "只听节奏", "caption": "识别节奏，不录音频"},
                       {"type": "steps", "value": "流程", "items": [["拍照", "对着谱架"], ["记录", ""]]},
                       {"type": "formula", "value": "T ≈ 2π √(L / g)", "items": ["L 摆长"]},
                       {"type": "quote", "value": "终于知道自己练了多久", "caption": "中期问卷"})[0]
        shown = texts(deck.prs)
        said = [sl.notes_slide.notes_text_frame.text for sl in deck.prs.slides]
        checks.append(("说明小字不上片，原样挪进备注，三条各报一次",
                       not {"识别节奏，不录音频", "对着谱架", "L 摆长"} & shown
                       and "识别节奏，不录音频" in said[0] and "对着谱架" in said[1] and "L 摆长" in said[2]
                       and sum("挪进了讲者备注" in w for w in deck.warnings) == 3))
        checks.append(("引语的出处照旧上片", "中期问卷" in shown))
        deck = deck_of({"type": "num", "value": "38 分钟平均差距"})[0]
        runs = [r.text for r in deck.prs.slides[0].shapes[0].text_frame.paragraphs[0].runs]
        checks.append(("限定条件写进单位，和数字同一行", runs == ["38", " 分钟平均差距"]))

        # 大数字按「[限定词␠]数字[单位]」切：限定词画成数字前面的 0.4 倍小字，正负号认 ±
        def num_runs(value):
            deck = deck_of({"type": "num", "value": value})[0]
            para = deck.prs.slides[0].shapes[0].text_frame.paragraphs[0]
            return deck, [r.text for r in para.runs], [r.font.size.pt for r in para.runs]

        deck, runs, sizes = num_runs("最长 22 小时视频播放")
        checks.append(("「最长」写在数字前、缩小，整行放得下不报",
                       runs == ["最长 ", "22", " 小时视频播放"] and sizes == [56, 140, 56]
                       and not deck.warnings))
        deck, runs, _ = num_runs("CO₂ 平均误差 ±45 ppm")
        checks.append(("±45 ppm 也切得开；「CO₂ 平均误差」加「ppm」按 7 个字算，不报",
                       num_runs("±45 ppm")[1] == ["±45", " ppm"]
                       and runs == ["CO₂ 平均误差 ", "±45", " ppm"] and not deck.warnings))
        checks.append(("限定词里带版本号也切得开：取最后一个数",
                       num_runs("比 Drift 1 薄 30%")[1] == ["比 Drift 1 薄 ", "30", "%"]))
        bad = [num_runs(v) for v in ("3 倍于 Drift 1", "12 月 1 日", "续航30天")]
        checks.append(("版本号写在数字后、日期、漏了空格：不乱切，整串照排并报切不成",
                       [r for _, r, _ in bad] == [["3 倍于 Drift 1"], ["12 月 1 日"], ["续航30天"]]
                       and all(any("切不成" in w for w in d.warnings) for d, _, _ in bad)))
        names = [num_runs(v) for v in ("4K120", "A17 Pro")]
        checks.append(("「4K120」「A17 Pro」这种名字照原样排，不报切不成",
                       [r for _, r, _ in names] == [["4K120"], ["A17 Pro"]]
                       and not any("切不成" in w for d, _, _ in names for w in d.warnings)))
        deck, runs, _ = num_runs("22 小时本地视频播放时长")
        checks.append(("限定词加单位超过 8 个字报出来，照样缩小",
                       runs == ["22", " 小时本地视频播放时长"]
                       and any("最多 8 个" in w for w in deck.warnings)))
        deck, runs, _ = num_runs("4.2 分（n = 30）")
        checks.append(("单位里带数字切不开，报出来并指向 source",
                       runs == ["4.2 分（n = 30）"]
                       and any("切不成" in w and '"source"' in w for w in deck.warnings)))
        # 审计复现：原来只核数字，四位数加 8 个字的单位折成两行也不报
        deck, runs, _ = num_runs("1200 小时本地视频播放")
        checks.append(("数字连单位一行放不下，报出来",
                       any("连限定词和单位要占 2 行" in w for w in deck.warnings)))

        # 出处行：大数字与双列对比的 "source" 画在左下，不进备注（公式的另有一条）；旧的 num caption 照旧挪进备注
        deck = deck_of({"type": "num", "value": "满意度 4.2 分", "source": "n = 30 · 中期问卷"},
                       {"type": "versus", "value": "CO₂ 误差", "source": "n = 20 · 厂内实测",
                        "items": [["参考仪器", "±0"], ["本机", "±45"]]},
                       {"type": "num", "value": "4.2 分", "caption": "中期问卷"},
                       {"type": "feature", "value": "节奏识别", "source": "厂内实测"})[0]
        said = "\n".join(sl.notes_slide.notes_text_frame.text for sl in deck.prs.slides)
        spots = [(sh.left, sh.top, sh.text_frame.paragraphs[0].runs[0].font.size.pt)
                 for s in list(deck.prs.slides)[:2] for sh in s.shapes
                 if sh.has_text_frame and sh.text_frame.text in ("n = 30 · 中期问卷", "n = 20 · 厂内实测")]
        checks.append(("出处行上片在左下 30pt，不进备注",
                       spots == [(PAD_X, Inches(6.85), SIZE["label"])] * 2
                       and "n = 30" not in said and "n = 20" not in said))
        checks.append(("旧的 num caption 挪进备注并指向 source；别的片型写 source 会报",
                       "中期问卷" in said
                       and any("片单第 3 张（num）" in w and '"source"' in w for w in deck.warnings)
                       and any("片单第 4 张（feature）" in w and '"source"' in w for w in deck.warnings)))

        # 价格下面不垫发售日期；规格密排每项要有值；公式连同条件只给一行
        deck = deck_of({"type": "price", "value": "Cadence",
                        "items": [["¥699", "标准版"], ["¥499", "12 月 1 日发售"]]},
                       {"type": "specs", "value": "监测", "items": [["PM2.5", ""], ["CO₂", "±45 ppm"]]},
                       {"type": "formula", "value": "h = ½ g t²（由静止释放，不计空气阻力）"})[0]
        checks.append(("价格下面写发售日期会报，配置名不报",
                       sum("像发售日期" in w for w in deck.warnings) == 1
                       and any("「12 月 1 日发售」" in w for w in deck.warnings)))
        checks.append(("规格密排只有项名没有值会报", any("「PM2.5」没有值" in w for w in deck.warnings)))
        checks.append(("公式连长条件折成两行会报", any(w.startswith("公式「") and "要占" in w
                                                    for w in deck.warnings)))
        # 写不短的条件进公式的出处行，在左下上片、不进备注
        deck = deck_of({"type": "formula", "value": "h = ½ g t²", "source": "由静止释放，不计空气阻力"})[0]
        checks.append(("公式的 source 画在左下，不报不认识",
                       "由静止释放，不计空气阻力" in texts(deck.prs)
                       and not any('"source"' in w for w in deck.warnings)))
        # 公式只有等号左边能配对：概念片的 g 配到「h = ½ g t²」，原来会把 g 变成 h 还报 1 处 Morph
        deck, _, morphs, _, _ = deck_of(
            {"type": "definition", "value": "重力加速度", "symbol": "g", "morph": "g"},
            {"type": "formula", "value": "h = ½ g t²", "morph": "g"})
        back, _, back_morphs, _, _ = deck_of(
            {"type": "formula", "value": "h = ½ g t²", "morph": "g"},
            {"type": "definition", "value": "重力加速度", "symbol": "g", "morph": "g"})
        checks.append(("公式等号左边和相邻那张的符号不一样，两个方向都不做 Morph 并报出来",
                       morphs == 0 and back_morphs == 0
                       and all(any("两端的字不一样" in w for w in d.warnings)
                               and not any("没有配对成功" in w for w in d.warnings)
                               for d in (deck, back))))
        deck = deck_of({"type": "formula", "value": "h = ½ g t²", "caption": "由静止释放，不计空气阻力"})[0]
        checks.append(("旧片单公式的 caption 挪进备注，提示指向 source",
                       any("挪进了讲者备注" in w and '"source"' in w for w in deck.warnings)))

        # 审计复现：--static 下提问片拆两张，挪进备注的揭晓依据原来两张都写，课前删掉揭晓那张也会漏答案
        deck = build({"slides": [{"type": "question", "value": "摆长变成 4 倍，周期变成几倍？",
                                  "items": ["2 倍", "4 倍", "16 倍"], "answer": 0,
                                  "caption": "周期与摆长的平方根成正比", "notes": "给二十秒"}],
                      "_base": tmp}, animate=False)[0]
        said = [sl.notes_slide.notes_text_frame.text for sl in deck.prs.slides]
        checks.append(("--static 的提问片：揭晓依据只写进揭晓那张",
                       len(said) == 2 and "平方根" not in said[0] and "给二十秒" in said[0]
                       and "平方根" in said[1]))
        # 审计复现：流程条一步写了三项，第三项原来一声不吭地丢掉
        try:
            deck_of({"type": "steps", "value": "流程", "items": [["拍照", "对着谱架", "约 2 秒"]]})
            checks.append(("流程条一步写三项报错，不丢字", False))
        except SpecError as exc:
            checks.append(("流程条一步写三项报错，不丢字", "3 项" in str(exc)))

        # 正常的课堂片单：概念片的符号 Morph 到公式，提问原地揭晓，推演逐行
        deck, unknown, morphs, clicks, stepped = deck_of(
            {"type": "definition", "value": "周期", "symbol": "T", "morph": "T"},
            {"type": "formula", "value": "T ≈ 2π √(L / g)", "morph": "T"},
            {"type": "question", "value": "摆长变成 4 倍，周期变成几倍？",
             "items": ["2 倍", "4 倍", "16 倍"], "answer": 0},
            {"type": "derive", "value": "例：L = 1.0 m",
             "items": [["T ≈ 2π √(L / g)", "周期公式"], ["≈ 2.0 s", "两位有效数字"]]})
        # 只数 Morph 处数测不出 ≈ 没切开（整条式子也能配对），所以再看配对的对象是不是只有 T
        morph_obj = [sh.text_frame.text for sh in deck.prs.slides[1].shapes if sh.name.startswith("!!")]
        checks.append(("正常片单：1 处 Morph（≈ 处切开，参与配对的只有 T），2 张分步共 3 次点击",
                       (morphs, stepped, clicks) == (1, 2, 3) and not unknown and morph_obj == ["T"]))
        checks.append(("正常片单没有误报放不下或孤行", not fit_notes(deck)))

        # 0.10.1 底色：默认匹配色，没有匹配色就黑；带色近黑留作 "tinted"
        def bg_of(slide):
            fill = slide.background.fill
            return str(fill.fore_color.rgb) if fill.type == 1 else None

        def grad_of(slide):
            fill = slide.background.fill
            return [str(st.color.rgb) for st in fill.gradient_stops] if fill.type == 3 else None

        def run_colors(slide):
            return [str(r.font.color.rgb) for sh in slide.shapes if sh.has_text_frame
                    for p in sh.text_frame.paragraphs for r in p.runs]

        pinned = {
            ("#e0774a", 0.45, "#e0774a"): ("#4a2a1c", "#553020", "#6e4e3f", "#593222", "#331a0f", "#977d72", "#e27f55"),
            ("#53ac80", 0.35, "#e0913a"): ("#1c3b2c", "#214534", "#3e6050", "#234936", "#0e251a", "#6a907e", "#e0913a"),
            ("#5378ac", 0.35, "#4fae9b"): ("#213045", "#26374f", "#445469", "#283a53", "#121f30", "#728297", "#4fae9b"),
            ("#8e8e93", None, "#5a8dee"): ("#333333", "#3b3b3b", "#575757", "#3d3d3d", "#212121", "#858585", "#749ff1"),
        }
        got = {k: tuple(matched_palette(*k)[f] for f in ("bg", "tile", "line", "ghost", "field", "faint", "accent"))
               for k in pinned}
        checks.append(("matched_pinned_values：四组匹配色与钉住的值一致", got == pinned))
        neutral = matched_palette("#8e8e93", None, "#5a8dee")
        checks.append(("matched_neutral_stays_neutral：灰色输入不带色相",
                       (neutral["bg"], neutral["field"]) == ("#333333", "#212121")))
        cli = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--palette", "#e0774a",
                              "--sat", "0.45", "--accent", "#e0774a"], capture_output=True, text=True)
        checks.append(("palette_cli_prints_variables：--palette 打出 CSS 变量、JSON 与提亮后的重点色",
                       cli.returncode == 0 and "--bg-base: #4a2a1c" in cli.stdout
                       and '"background": "#4a2a1c"' in cli.stdout and "#e27f55" in cli.stdout))
        checks.append(("tinted_pinned_values：带色近黑照 0.10.0 的算法",
                       derive_palette("#5a8dee") == {"bg": "11141A", "tile": "1C2026", "line": "373B43",
                                                     "faint": "6E7581", "field": "142952", "ghost": "191E27",
                                                     "fade_end": "142952"}
                       and derive_palette("#e0774a")["bg"] == "1A1411"
                       and derive_palette("#8e8e93")["bg"] == "161617"))
        deck = deck_of({"type": "phrase", "value": "一句"}, accent="#5a8dee")[0]
        checks.append(("theme_dark_default_black：没写 background 的旧片单照旧纯黑",
                       bg_of(deck.prs.slides[0]) == "000000"))
        deck = deck_of({"type": "specs", "value": "规格", "items": [["续航", "30 天"]]},
                       background="#4a2a1c", accent="#e0774a")[0]
        checks.append(("background_matched_deck：整套匹配色，次要字换成 #c7c7cc",
                       bg_of(deck.prs.slides[0]) == "4A2A1C" and "C7C7CC" in run_colors(deck.prs.slides[0])))
        deck = deck_of({"type": "phrase", "value": "第一章"},
                       {"type": "specs", "value": "规格", "items": [["续航", "30 天"]], "background": "#213045"},
                       {"type": "phrase", "value": "第三张"})[0]
        s1, s2, s3 = list(deck.prs.slides)
        checks.append(("background_per_slide：单张片换章节色，配色只管这一张",
                       (bg_of(s1), bg_of(s2), bg_of(s3)) == ("000000", "213045", "000000")
                       and "C7C7CC" in run_colors(s2) and "C7C7CC" not in run_colors(s1)))
        light = deck_of({"type": "phrase", "value": "一句"}, background="#87a6d6")[0]
        close = deck_of({"type": "phrase", "value": "一句"}, background="#4a2a1c", accent="#4a2a1c")[0]
        checks.append(("background_too_light_warns：底色太亮或重点色太近都会报，不偷偷改色",
                       any("底色太亮" in w for w in light.warnings)
                       and bg_of(light.prs.slides[0]) == "87A6D6"
                       and any("重点色" in w for w in close.warnings)))
        deck = deck_of({"type": "phrase", "value": "一句"}, theme="tinted", accent="#5a8dee")[0]
        checks.append(("theme_tinted_stays：tinted 是带色近黑", bg_of(deck.prs.slides[0]) == "11141A"))
        deck = deck_of({"type": "section", "value": "原理", "ground": "field"},
                       {"type": "section", "value": "检验", "ground": "fade"},
                       theme="tinted", accent="#5a8dee")[0]
        f1, f2 = list(deck.prs.slides)
        matched_field = deck_of({"type": "section", "value": "原理", "ground": "field"},
                                background="#213045")[0]
        checks.append(("ground_field_and_fade：色场纯色白字、渐变两段；匹配色片用匹配色场",
                       bg_of(f1) == "142952" and "F5F5F7" in run_colors(f1)
                       and grad_of(f2) == ["11141A", "142952"]
                       and f2.background._cSld.bg.xpath(".//a:lin")[0].get("ang") == "5400000"
                       and bg_of(matched_field.prs.slides[0]) == "121F30"))
        deck = deck_of({"type": "num", "value": "3 倍", "ground": "field"})[0]
        checks.append(("ground_on_wrong_type_warns：大数字片写 ground 会报，底色不变",
                       any("片单第 1 张（num）" in w and "ground" in w for w in deck.warnings)
                       and bg_of(deck.prs.slides[0]) == "000000"))
        deck = deck_of({"type": "section", "value": "原理", "ground": "fade"}, theme="light", accent="#2b5fd0")[0]
        stops = grad_of(deck.prs.slides[0])
        checks.append(("light_theme_grounds_keep_contrast：浅色主题的渐变压得住正文",
                       stops is not None and stops[0] == "F5F5F7"
                       and contrast(rgb("1D1D1F"), rgb(stops[1])) >= 7))
        # 终审第 1 条：灰色输入加了 --sat 也不能长出色相（colorsys 给灰色的色相是 0，原来会变成酱红）
        grey_sat = [matched_palette(c, 0.35)["bg"] for c in ("#808080", "#8e8e93")]
        try:
            matched_palette("#e0774a", -0.3)
            neg_ok = False
        except ValueError:
            neg_ok = True
        bad_cli = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--palette", "#e0774a",
                                  "--sat", "1.5"], capture_output=True, text=True)
        checks.append(("matched_neutral_with_sat_stays_neutral：灰色输入写了 --sat 照样是中性灰；--sat 出了 0–1 报错",
                       grey_sat == ["#333333", "#333333"] and neg_ok and bad_cli.returncode != 0))
        # 终审第 2、3 条：浅色主题写 background，匹配色上色场，页面照旧浅色；别的主题被 background 盖掉要报
        light_bg = deck_of({"type": "section", "value": "原理", "ground": "field"},
                           {"type": "phrase", "value": "一句"},
                           theme="light", background="#1c3b2c", accent="#a35a12")[0]
        sl = list(light_bg.prs.slides)
        over = deck_of({"type": "phrase", "value": "一句"}, theme="graphite", background="#213045")[0]
        checks.append(("light_theme_background_goes_to_field：浅色主题的 background 只上色场；graphite 被盖掉会报",
                       bg_of(sl[0]) == "1C3B2C" and bg_of(sl[1]) == "F5F5F7"
                       and not any("太亮" in w for w in light_bg.warnings)
                       and bg_of(over.prs.slides[0]) == "213045"
                       and any("graphite" in w and "background" in w for w in over.warnings)))
        light_cli = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--palette", "#53ac80",
                                    "--sat", "0.35", "--accent", "#e0913a"], capture_output=True, text=True)
        la = re.search(r'"theme": "light", "background": "#1c3b2c", "accent": "(#[0-9a-f]{6})"', light_cli.stdout)
        checks.append(("palette_cli_prints_light_line：--palette 也打出亮教室那一套，重点色压在 #f5f5f7 上过 4.5:1",
                       la is not None and contrast(rgb(la.group(1)), rgb("F5F5F7")) >= 4.5
                       and "--field: #1c3b2c" in light_cli.stdout))
        # 终审第 4 条：分节标题用正文色（HTML 的 .feature 也是），浅色渐变上不再是 3.5:1 的次要字
        lsec = deck_of({"type": "section", "value": "原理", "ground": "fade"}, theme="light", accent="#2b5fd0")[0]
        dsec = deck_of({"type": "section", "value": "原理"})[0]
        checks.append(("section_title_is_ink：分节标题用正文色",
                       run_colors(lsec.prs.slides[0]) == ["1D1D1F"] and run_colors(dsec.prs.slides[0]) == ["F5F5F7"]))
        # 论文讲读的标题卡要写原作者与年份（Case 34），标题卡认 "source"
        tsrc = deck_of({"type": "title", "value": "主张加证据", "source": "论文讲读 · Garner 与 Alley 2013"})[0]
        ttext = [sh.text_frame.text for sh in tsrc.prs.slides[0].shapes if sh.has_text_frame]
        checks.append(("title_source_line：标题卡的出处行画在左下，不报不认识",
                       "论文讲读 · Garner 与 Alley 2013" in ttext and not unknown_keys(
                           {"slides": [{"type": "title", "value": "x", "source": "y"}]})))
        # 贡献：带走的那几句是这张片的主体，用正文色、大字，不是次要色的小字
        contrib = deck_of({"type": "recap", "value": "贡献", "build": False,
                           "items": [["1", "标题写结论"], ["2", "正文放证据图"]]})[0]
        cruns = [r for sh in contrib.prs.slides[0].shapes if sh.has_text_frame
                 for para in sh.text_frame.paragraphs for r in para.runs if r.text == "标题写结论"]
        checks.append(("contrib_takeaways_large_ink：贡献的几句用正文色、40pt 以上",
                       len(cruns) == 1 and str(cruns[0].font.color.rgb) == "F5F5F7"
                       and cruns[0].font.size >= Pt(40)))
        empty = deck_of({"type": "rest"})[0]
        glyph = deck_of({"type": "rest", "value": "T"}, theme="tinted", accent="#5a8dee")[0]
        long_rest = deck_of({"type": "rest", "value": "练琴计时器"})[0]
        gshapes = [sh for sh in glyph.prs.slides[0].shapes if sh.has_text_frame]
        grun = gshapes[0].text_frame.paragraphs[0].runs[0] if gshapes else None
        checks.append(("rest_value_limits：静场不给字就空着，给字画同色调巨字，超过 4 个字报",
                       not [sh for sh in empty.prs.slides[0].shapes if sh.has_text_frame]
                       and grun is not None and str(grun.font.color.rgb) == "191E27"
                       and grun.font.size.pt >= 300
                       and any("最多 4 个字" in w for w in long_rest.warnings)))
        on_field = deck_of({"type": "rest", "value": "T", "ground": "field"}, theme="light", accent="#2b5fd0")[0]
        checks.append(("rest_on_field_skips_glyph：色场上的静场不画巨字（会刺眼），报出来",
                       not [sh for sh in on_field.prs.slides[0].shapes if sh.has_text_frame]
                       and any("色场" in w and "巨字" in w for w in on_field.warnings)))
        deck = deck_of({"type": "recap", "items": [["质量", "不影响周期"], ["摆长", "T ∝ √L"],
                                                    ["条件", "小角度"], ["周期", "来回一次"]]})[0]
        checks.append(("recap_caps_at_three：回顾三条封顶，多的报出来",
                       any("回顾最多放 3 项" in w for w in deck.warnings)))
        # 参考文献备用页：一条长英文文献（APA 约 190 字符）要四行，原来每条只给两行的高度
        ref = ("Garner, J. K., & Alley, M. P. (2013). How the design of presentation slides affects audience "
               "comprehension: A case for the assertion–evidence approach. International Journal of "
               "Engineering Education, 29(6), 1564–1579.")
        one = deck_of({"type": "refs", "items": [ref]})[0]
        five = deck_of({"type": "refs", "items": ["Author, A. (2020). Title. Journal."] * 5})[0]
        checks.append(("refs_long_entry_fits：一条长文献在备用页上放得下，五条照旧续页",
                       not fit_notes(one) and len(five.prs.slides) == 2 and not fit_notes(five)))
        deck = deck_of({"type": "claim", "value": "摆长变成原来的四倍以后周期只会变成原来的两倍而已"})[0]
        short = deck_of({"type": "claim", "value": "摆长 4 倍，周期 2 倍"})[0]
        checks.append(("claim_title_one_line：主张句一行放不下就报",
                       any("要占 2 行" in w for w in deck.warnings) and not fit_notes(short)))
        deck = deck_of({"type": "derive", "value": "例",
                        "items": [["T ≈ 2π √(L / g)", "这一步用的是小角度近似"]]})[0]
        ok8 = deck_of({"type": "derive", "value": "例", "items": [["T ≈ 2π √(L / g)", "小角度近似"]]})[0]
        checks.append(("derive_basis_one_line：推演右栏一行放不下就报",
                       any("推演右栏" in w and "要占" in w for w in deck.warnings)
                       and not [w for w in ok8.warnings if "推演右栏" in w]))

        # 拼错的字段不静默；格式不对的片报出第几张
        deck = deck_of({"type": "specs", "value": "规格", "bulid": True,
                        "items": [["续航", "30 天"]]})[0]
        checks.append(("拼错的字段 bulid 会报", any("bulid" in w for w in deck.warnings)))
        try:
            deck_of({"type": "phrase", "value": "一句"}, {"type": "specs", "items": [["只有一项"]]})
            checks.append(("格式不对的片报错并指出第 2 张", False))
        except SpecError as exc:
            checks.append(("格式不对的片报错并指出第 2 张", "第 2 张" in str(exc)))

        # 审计复现：--help 原来被当成不认识的选项，退出 1
        run = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--help"],
                             capture_output=True, text=True)
        checks.append(("--help 打印用法与片单格式，退出 0",
                       run.returncode == 0 and "片单格式" in run.stdout))

    ok = True
    for name, passed in checks:
        ok &= passed
        print(f"  {'pass' if passed else 'FAIL'}  {name}")
    print("自检" + ("通过" if ok else "未通过"))
    return 0 if ok else 1


def print_palette(argv) -> int:
    """--palette <颜色> [--sat S] [--accent <主色>]：算出和这个颜色匹配的一整套底色，
    打印可以直接贴进 deck.html 的 CSS 变量、片单的 JSON 字段和对比度。"""
    def value(flag):
        i = argv.index(flag)
        if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
            sys.exit(f"{flag} 后面要跟一个值。用法：--palette <颜色> [--sat 0.35] [--accent <主色>]")
        return argv[i + 1]
    try:
        color = value("--palette")
        sat = float(value("--sat")) if "--sat" in argv else None
        accent = value("--accent") if "--accent" in argv else None
        pal = matched_palette(color, sat, accent)
    except ValueError as exc:
        sys.exit(f"{exc}。用法：--palette <颜色> [--sat 0.35] [--accent <主色>]")
    h, L, s = _hex_hls(pal["bg"])
    print(f"匹配色 {pal['bg']}（色相 {h * 360:.0f}°，饱和度 {s:.2f}，明度 {L:.2f}），由 {color} 推出")
    print(":root {")
    for name, key in (("--bg-base", "bg"), ("--tile", "tile"), ("--line", "line"), ("--ink", "ink"),
                      ("--muted", "muted"), ("--faint", "faint"), ("--field", "field"),
                      ("--ghost", "ghost"), ("--fade-end", "fade_end"), ("--accent", "accent")):
        if pal.get(key):
            print(f"  {name}: {pal[key]};")
    print("}")
    pairs = [f'"background": "{pal["bg"]}"'] + ([f'"accent": "{pal["accent"]}"'] if pal["accent"] else [])
    print(", ".join(pairs))
    print("对比度：" + "，".join(f"{k} {v:.2f}:1" for k, v in pal["checks"].items()))
    for note in pal["notes"]:
        print(f"注意：{note}")
    # 亮教室：页面换成 #f5f5f7，匹配色只上色场，重点色压暗；HTML 的浅色主题与片单都照这一套写
    room = light_room(pal["bg"], accent)
    print('亮教室用浅色（"theme": "light"）：页面 #f5f5f7，匹配色只上封面、分节、静场的色场')
    css = ([f"--accent: {room['accent']}"] if room["accent"] else []) + [
        f"--field: {room['field']}", f"--ghost: {room['ghost']}", f"--fade-end: {room['fade_end']}"]
    print("  " + "; ".join(css) + ";")
    light = ['"theme": "light"', f'"background": "{pal["bg"]}"'] + (
        [f'"accent": "{room["accent"]}"'] if room["accent"] else [])
    print(", ".join(light) + (f"（重点色压在 #f5f5f7 上 {room['ratio']:.2f}:1）" if room["accent"] else ""))
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return 0
    if "--selftest" in argv:
        return selftest()
    if "--palette" in argv:
        return print_palette(argv)
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    unknown_flags = flags - {"--static"}
    if unknown_flags:
        sys.exit(f"不认识的选项: {', '.join(sorted(unknown_flags))}。用法见 --help")
    if not args:
        sys.exit(__doc__.split("片单格式")[0].strip())

    src = Path(args[0])
    if not src.is_file():
        sys.exit(f"找不到文件: {src}")

    try:
        spec = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        sys.exit(f"{src} 不是合法的 JSON：{exc}")
    if not isinstance(spec, dict):
        sys.exit("片单最外层要是一个 {...}，slides 写在里面")
    slides = spec.get("slides") or []
    if not slides:
        sys.exit("片单里没有 slides")

    spec["_base"] = str(src.parent)
    animate = "--static" not in flags
    try:
        deck, unknown, morphs, clicks, stepped = build(spec, animate)
    except SpecError as exc:
        sys.exit(f"{exc}。没有写出文件")
    made = len(deck.prs.slides)

    out = Path(args[1]) if len(args) > 1 else src.with_suffix(".pptx")
    deck.prs.save(str(out))

    print(f"已生成: {out}  ({made} 页)")
    if animate:
        print(f"动画：{stepped} 张片分步，共 {clicks} 次点击"
              f"{f'；{morphs} 处 Morph 平滑切换' if morphs else ''}")
        print("看每张片分几步：python3 pptx_motion.py --inspect " + out.name)
    else:
        print("没有写动画（--static）：提问片拆成了题目与揭晓两张")
    if unknown:
        print(f"跳过了不认识的片型: {', '.join(sorted(map(str, unknown)))}")
    for w in deck.warnings:
        print(f"注意：{w}")
    name = deck.palette["name"]
    print(f"底色：{name}" + ("（没写 background；要匹配色写 \"background\"，色值用 --palette 算）"
                           if name.startswith("黑色") else ""))
    print("pptx 仍然丢的东西：公式是纯文本、图表要手工摆、bento 的大小分层被简化。")
    print("要那个层次的视觉就用 templates/deck.html。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
