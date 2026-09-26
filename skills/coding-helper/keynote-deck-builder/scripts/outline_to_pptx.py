#!/usr/bin/env python3
"""从片单 JSON 生成可编辑的 .pptx，带动画。

    python3 outline_to_pptx.py deck.json [out.pptx]
    python3 outline_to_pptx.py deck.json --static     不写任何动画
    python3 outline_to_pptx.py --help                 看这份说明与片单格式
    python3 outline_to_pptx.py --selftest

依赖 python-pptx（`pip3 install python-pptx`）；image / claim 带图时还要 Pillow（`pip3 install pillow`）。

这条路的价值是「能在 Keynote 或 PowerPoint 里继续改」。动画由 `pptx_motion.py` 写入
（PresentationML 的 <p:timing>），HTML 模板的四件事都做得到：

  讲到才出现  逐项浮入（淡入 + 上移），一步一次点击
  讲过的调暗  换成 faint 色
  讲到的点名  换成重点色
  跨片连续    相邻两片的同一个对象用 Morph（平滑）切换，旧版本回退成淡入淡出

**仍然会丢东西，要如实告诉使用者**：

  - 底色只能是纯色，做不到 HTML 模板里那种多层渐变
  - 公式退成纯文本，要在 PowerPoint 或 Keynote 的公式编辑器里重排
  - 颗粒、圆角容器、bento 的大小分层都被简化
  - 图表不做，在 PowerPoint 里手工摆更快
  - 公式里逐项点名做不到（一个文本框只能整体换色），改成下方的项逐个出现
  - 误解片的划线做不到，改成把误解调暗

要视觉精度就用 templates/deck.html；要可编辑就用这个。两者不冲突，可以都给。

画布是 13.333 × 7.5 英寸，也就是 960 × 540pt，正好是 HTML 舞台（1920 × 1080px）的一半，
所以版面上 px ÷ 2 = pt：大数字 320px 对应 160pt，标题 96px 对应 48pt。
小字这里用 30pt，比 HTML 的 40px（对应 20pt）相对更大，是有意偏严。塞不下就删字，不要调低。

每张片都可以带 "notes"，写进 pptx 的演讲者备注。

片单格式（type 决定版式，其余字段按类型取用）：

    {
      "accent": "#5a8dee",
      "theme": "dark",
      "font": "Helvetica Neue",
      "slides": [
        {"type": "title",   "value": "产品名", "caption": "一句话定位"},
        {"type": "phrase",  "value": "转账不该点七次"},
        {"type": "num",     "value": "7 次", "caption": "完成一笔转账",
                            "unverified": false},
        {"type": "section", "value": "章节名"},
        {"type": "feature", "value": "功能名", "caption": "一句话"},
        {"type": "quote",   "value": "用户原话", "caption": "出处，必填"},
        {"type": "steps",   "value": "这套流程产出什么",
                            "items": [["步骤", "一句话"], ["步骤", "一句话"]]},
        {"type": "specs",   "value": "规格",
                            "items": [["项", "值"], ["项", "值"]]},
        {"type": "versus",  "value": "对比什么",
                            "items": [["上一代", "1.0"], ["本代", "3.2"]]},
        {"type": "price",   "value": "产品名",
                            "items": [["¥4999", "128GB"]], "caption": "9 月 20 日"},
        {"type": "close",   "value": "收束一句"},

        课堂与讲堂：
        {"type": "roadmap",    "items": ["现象", "原理", "应用"], "current": 1},
        {"type": "question",   "kicker": "先预测", "value": "摆长变成 4 倍，周期变成几倍",
                               "items": ["2 倍", "4 倍", "16 倍"], "answer": 0,
                               "caption": "揭晓后的一句依据"},
        {"type": "image",      "src": "figures/a.jpg", "value": "图上的一句",
                               "caption": "一行小字", "credit": "来源，必填",
                               "focus": [0.5, 0.4]},
        {"type": "claim",      "value": "一句主张", "caption": "出处",
                               "src": "figures/evidence.png"},
        {"type": "definition", "value": "术语", "symbol": "T", "caption": "一句定义"},
        {"type": "derive",     "value": "这一段要证明什么",
                               "items": [["式子", "凭什么这一步成立"], ["式子", "凭什么"]],
                               "caption": "出处", "caption_at": 2},
        {"type": "formula",    "value": "T = 2π √(L / g)", "caption": "可省",
                               "items": ["L 摆长", "g 重力加速度"]},
        {"type": "myth",       "value": "误解原话", "caption": "正确说法"},
        {"type": "recap",      "items": [["提示词", "一句要点"]]},
        {"type": "refs",       "items": ["作者（年份）. 题名. 出处."]},

        每张都可以加 "notes": "讲者备注"
        每张都可以加 "build": false 让这张片一次出完；分步走的片型还认 "dim": false
        相邻两片上同一个东西写同一个 "morph": "T"，翻页时用 Morph 平滑切换
      ]
    }

出场顺序按片型定（`BUILD` 与 `DIM` 两张表），不用逐片写步数：
流程条、推演逐步走并调暗；回顾、公式的项逐个出；提问片在原地揭晓；误解片在原地改正。
规格密排与双列对比默认一次出齐，要逐个出就写 "build": true。

自检：每个会折行的文本框都按它自己的高度算能放几行，放不下的行、折行后只剩一两个字的孤行
都会报出来（只报不改，生成的文件照旧）。片单里不认识的字段也会报，格式不对的片直接报错、不写文件。
"""

import io
import json
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
SIZE = {"num": 160, "phrase": 90, "feature": 60, "title": 48,
        "sub": 30, "label": 30}

THEME = {
    "dark":  {"bg": "0A0B0E", "ink": "F5F5F7", "muted": "8E8E93", "faint": 0.45},
    "light": {"bg": "F5F5F7", "ink": "1D1D1F", "muted": "6E6E73", "faint": 0.52},
}

# 哪些片型默认逐个出现。片单里可以用 "build": false 关掉
BUILD = {"steps": True, "derive": True, "recap": True, "formula": True,
         "question": True, "myth": True, "specs": False, "versus": False}
# 哪些片型默认把讲过的调暗：只有一步接一步往下走的才调暗
DIM = {"steps": True, "derive": True}

# 能跨片配对的片型：值是「哪个对象参与 Morph」
MORPH_OK = {"title", "phrase", "close", "num", "section", "feature",
            "definition", "formula", "image", "claim"}


def rgb(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.lstrip("#").upper())


def blend(fg: RGBColor, bg: RGBColor, alpha: float) -> RGBColor:
    """把带透明度的前景色合成成实色。HTML 模板的 --muted / --faint 是透明度，
    pptx 的底色是纯色，所以这里按同样的透明度算出实色，不靠眼睛调。"""
    return RGBColor(*(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg)))


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
        pal = THEME[spec.get("theme", "dark")]
        self.bg = rgb(pal["bg"])
        self.ink = rgb(pal["ink"])
        self.muted = rgb(pal["muted"])
        self.faint = blend(self.ink, self.bg, pal["faint"])
        self.accent = rgb(spec.get("accent", "#5A8DEE"))
        self.font = spec.get("font", "Helvetica Neue")
        self.base = Path(spec.get("_base", "."))
        self.animate = animate
        self.motions = []
        self.m = None            # 当前这张片的出场顺序
        self.anchor = None       # 当前这张片参与 Morph 的对象
        self.warnings = []
        # 调暗色与重点色的对比度按 WCAG 大字下限 3:1 核一遍，改配色后这里会报
        for name, color in (("调暗色", self.faint), ("重点色", self.accent)):
            ratio = contrast(color, self.bg)
            if ratio < 3.0:
                self.warnings.append(
                    f"{name} #{color} 在底色 #{self.bg} 上只有 {ratio:.2f}:1，"
                    f"大字下限是 3:1（WCAG 1.4.3），换一个")

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

    # ── 各片型 ────────────────────────────────────────────
    def title(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(2.4), height=Inches(1.9),
                                size=SIZE["phrase"], bold=True)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.5), height=Inches(0.8),
                      size=SIZE["sub"], color=self.muted)

    def phrase(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(2.5), height=Inches(2.5),
                                size=SIZE["phrase"], bold=True)

    def num(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(2.0), height=Inches(2.6),
                                size=SIZE["num"], bold=True, color=self.accent)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.7), height=Inches(0.7),
                      size=SIZE["sub"], color=self.muted)
        # 未确认项在片上必须看得见，不能只写在大纲里
        if d.get("unverified"):
            self.text(s, "未确认 · 材料里没有出处", top=Inches(5.5),
                      height=Inches(0.6), size=SIZE["label"], color=self.muted)

    def section(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(3.1), height=Inches(1.3),
                                size=SIZE["title"], color=self.muted)

    def feature(self, d):
        s = self.slide()
        self.anchor = self.text(s, d["value"], top=Inches(2.6), height=Inches(1.4),
                                size=SIZE["feature"], bold=True)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.2), height=Inches(0.8),
                      size=SIZE["sub"], color=self.muted)

    def specs(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        items = self._cap(d.get("items", []), 6, "规格密排")
        build = self._build(d, "specs")
        col_w = BODY_W / 3
        for n, (k, v) in enumerate(items):
            cx = PAD_X + col_w * (n % 3)
            cy = Inches(2.6) + Inches(1.9) * (n // 3)
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
            value = self.text(s, val, top=Inches(3.4), height=Inches(1.8), size=100,
                              bold=True, color=self.accent if n else self.ink,
                              left=cx, width=col_w - Inches(0.4))
            if build:
                self._step([label, value], n + 1)

    def price(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(1.4), height=Inches(1.0),
                  size=SIZE["title"], bold=True)
        items = d.get("items", [])[:3]
        if items:
            col_w = BODY_W / len(items)
            for n, (p, cfg) in enumerate(items):
                cx = PAD_X + col_w * n
                self.text(s, p, top=Inches(3.0), height=Inches(1.4), size=90,
                          bold=True, color=self.accent if n == 0 else self.ink,
                          left=cx, width=col_w)
                self.text(s, cfg, top=Inches(4.4), height=Inches(0.7),
                          size=SIZE["sub"], color=self.muted,
                          left=cx, width=col_w)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(5.4), height=Inches(0.7),
                      size=SIZE["sub"], color=self.muted)

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
        for n, (name, desc) in enumerate(items):
            cx = PAD_X + col_w * n
            group = [
                self.text(s, f"{n + 1:02d}", top=Inches(2.7), height=Inches(0.6),
                          size=SIZE["label"], color=self.accent, align=PP_ALIGN.LEFT,
                          left=cx, width=col_w - Inches(0.2)),
                self.text(s, name, top=Inches(3.3), height=Inches(0.9), size=44,
                          bold=True, align=PP_ALIGN.LEFT,
                          left=cx, width=col_w - Inches(0.2)),
                self.text(s, desc, top=Inches(4.2), height=Inches(1.2),
                          size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT,
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
            color = self.accent if n == cur else self.muted
            self.text(s, name, top=Inches(3.1), height=Inches(1.2), size=SIZE["title"],
                      bold=(n == cur), color=color, left=PAD_X + col_w * n, width=col_w)

    def _question_page(self, d, answer, reveal):
        """画一张提问片。reveal 为真时直接画成揭晓后的样子（没有动画时用）。
        返回 (选项形状表, 依据形状)。"""
        s = self.slide()
        if d.get("kicker"):
            self.text(s, d["kicker"], top=Inches(1.3), height=Inches(0.6),
                      size=SIZE["label"], bold=True, color=self.accent)
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
        sub = None
        if d.get("caption") and (reveal or self.animate):
            sub = self.text(s, d["caption"], top=Inches(5.0), height=Inches(0.7),
                            size=SIZE["sub"], color=self.muted)
        return boxes, sub

    def question(self, d):
        answer = d.get("answer")
        # 预测题不给 answer，只出题目这一张，讲完再用另一条片单揭晓
        if answer is None:
            self._question_page(d, None, False)
            return
        if self._build(d, "question"):
            boxes, sub = self._question_page(d, answer, False)
            for n, box in enumerate(boxes):
                self.m.recolor(box, 1, self.accent if n == answer else self.faint)
            if sub:
                self.m.show(sub, 1)
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
        if d.get("caption"):
            self.text(s, d["caption"], top=H - band + Inches(1.25), height=Inches(0.6),
                      size=SIZE["sub"], color=soft, align=PP_ALIGN.LEFT)
        if d.get("credit"):
            self.text(s, d["credit"], top=H - Inches(0.62), height=Inches(0.5), size=SIZE["label"],
                      color=soft, align=PP_ALIGN.RIGHT, left=Inches(0.3), width=W - Inches(0.6))
        elif d.get("src"):
            self.warnings.append(f"满版图「{d.get('value', '')}」有图但没有来源行（credit）")

    def claim(self, d):
        s = self.slide()
        claim = self.text(s, d["value"], top=PAD_Y, height=Inches(1.4), size=40,
                          bold=True, align=PP_ALIGN.LEFT)
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
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.1), height=Inches(1.0),
                      size=SIZE["sub"], color=self.muted)

    def derive(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.2), size=40,
                  bold=True, align=PP_ALIGN.LEFT)
        rows = self._cap(d.get("items", []), 4, "推演")
        build, dim = self._build(d, "derive"), self._dim(d, "derive")
        # 右栏先按「30pt 下每行 9 个中文字、两行封顶」定宽，式子列拿剩下的。
        # HTML 那边右栏是 44px / 每行 11 字，pptx 的 30pt 下限相对更大，所以一行放得少
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
                # 右栏 30pt 比 HTML 的 44px 相对更大，所以一行放得少，两行封顶
                group.append(self.text(s, why, top=y, height=Inches(1.0),
                                       size=SIZE["label"], color=self.muted,
                                       align=PP_ALIGN.LEFT, left=why_left, width=why_w,
                                       what="推演右栏", lines=2))
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
        head, sep, tail = value.partition("=")
        if d.get("morph") and sep and head.strip():
            # 等号左边单独成一个形状，才能跟上一张概念片里的同一个符号配对
            left, _ = self._pair(s, head.strip(), "=" + tail, top=Inches(2.2),
                                 height=Inches(1.6), size=SIZE["feature"], gap_em=0.22)
            self.anchor = left
        else:
            self.anchor = self.text(s, value, top=Inches(2.2), height=Inches(1.6),
                                    size=SIZE["feature"])
        items = self._cap(d.get("items", []), 4, "公式下面的项")
        build = self._build(d, "formula")
        if items:
            col_w = BODY_W / len(items)
            for n, item in enumerate(items):
                box = self.text(s, item, top=Inches(4.3), height=Inches(0.7),
                                size=SIZE["label"], color=self.muted,
                                left=PAD_X + col_w * n, width=col_w)
                if build:
                    self.m.show(box, n + 1)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(5.3), height=Inches(0.7),
                      size=SIZE["sub"], color=self.muted)
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
        tag = self.text(s, "实际上", top=Inches(3.7), height=Inches(0.6), size=SIZE["label"],
                        bold=True, color=self.accent, align=PP_ALIGN.LEFT)
        fact = self.text(s, d.get("caption", ""), top=Inches(4.3), height=Inches(1.1),
                         size=44, bold=True, align=PP_ALIGN.LEFT)
        if reveal:
            # HTML 里揭晓时给误解划线，pptx 划不了线，改成把误解调暗
            self.m.recolor(said, 1, self.faint)
            self.m.show(tag, 1)
            self.m.show(fact, 1)

    def recap(self, d):
        s = self.slide()
        self.text(s, d.get("value", "回顾"), top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        build = self._build(d, "recap")
        for n, (cue, point) in enumerate(self._cap(d.get("items", []), 4, "回顾")):
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
            for n, ref in enumerate(items[start:start + 4]):
                self.text(s, ref, top=Inches(2.2) + Inches(1.2) * n, height=Inches(1.1),
                          size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT)


KINDS = ("title", "phrase", "num", "section", "feature",
         "specs", "versus", "price", "close", "quote", "steps",
         "roadmap", "question", "image", "claim", "definition",
         "derive", "formula", "myth", "recap", "refs")
# 片单里认的字段。以 _ 开头的是注释（如 "_note"），不查
TOP_KEYS = {"accent", "theme", "font", "slides"}
SLIDE_KEYS = {"type", "value", "caption", "items", "notes", "build", "dim", "morph",
              "unverified", "kicker", "answer", "current", "src", "credit", "focus",
              "symbol", "caption_at"}


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
    return notes


def build(spec, animate=True):
    """按片单把整份 pptx 建好，不存盘。
    返回 (deck, 不认识的片型, Morph 处数, 点击次数, 分步的片数)；格式不对抛 SpecError。"""
    slides = spec.get("slides")
    if not isinstance(slides, list) or not all(isinstance(d, dict) for d in slides):
        raise SpecError("slides 要是一个列表，每张片是一个 {...}")
    if spec.get("theme", "dark") not in THEME:
        raise SpecError(f"theme 只认 {' 或 '.join(THEME)}，收到 {spec.get('theme')!r}")
    try:
        deck = Deck(spec, animate=animate)
    except ValueError as exc:
        raise SpecError(f"accent 要写成 #RRGGBB，收到 {spec.get('accent')!r}（{exc}）") from exc
    deck.warnings.extend(unknown_keys(spec))
    handlers = {name: getattr(deck, name) for name in KINDS}

    unknown, morphs, prev_key, paired = set(), 0, None, {}
    for n, d in enumerate(slides, 1):
        kind = d.get("type")
        fn = handlers.get(kind) if isinstance(kind, str) else None
        if fn is None:
            unknown.add(str(kind))
            continue
        before = len(deck.prs.slides)
        try:
            fn(d)
        except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
            what = f"缺字段 {exc}" if isinstance(exc, KeyError) else f"{type(exc).__name__}: {exc}"
            raise SpecError(f"片单第 {n} 张（{kind}）格式不对：{what}。"
                            f"对照 --help 里的片单格式改") from exc
        made = [deck.prs.slides[k] for k in range(before, len(deck.prs.slides))]
        # 一张片单可能生成多张（提问、参考文献续页），备注每张都写
        if d.get("notes"):
            for s in made:
                s.notes_slide.notes_text_frame.text = str(d["notes"])

        key = d.get("morph")
        this_key = None
        if key and animate:
            if kind not in MORPH_OK or deck.anchor is None or len(made) != 1:
                deck.warnings.append(f"「{kind}」这类片没有可配对的对象，morph「{key}」没做")
            else:
                motion.morph(deck.anchor, key)
                this_key = key
                paired.setdefault(key, False)
                if prev_key == key:
                    motion.transition(made[0], "morph", motion.MORPH_MS)
                    paired[key] = True
                    morphs += 1
        prev_key = this_key

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
        deck = deck_of({"type": "phrase", "value": "练了多久，没人说得清"})[0]
        checks.append(("逗号连着的十个字自己折行，报孤行", any("孤行" in w for w in deck.warnings)))
        deck = deck_of({"type": "phrase", "value": "练了多久\n没人说得清"})[0]
        checks.append(("手工断成两行的单句大字不报", not deck.warnings))

        # 规格密排默认一次出齐，写 "build": true 才逐个出（与 SKILL.md 阶段三一致）
        specs = {"type": "specs", "value": "规格", "items": [["续航", "30 天"], ["重量", "24 克"]]}
        plain, stepped = deck_of(specs)[3], deck_of(dict(specs, build=True))[3]
        checks.append(("规格密排默认 0 步，写 build: true 才 2 步", (plain, stepped) == (0, 2)))

        # 降级表补上的五类：时刻、信号汇入、取舍、one more thing、环保，都要真的导出来
        five = [
            {"type": "feature", "value": "就地取材", "caption": "整屏只剩一张照片和一个光标"},
            {"type": "steps", "value": "建议的来处", "build": False,
             "items": [["照片", ""], ["地点", ""], ["写作建议", "在设备上处理"]]},
            {"type": "steps", "value": "取舍",
             "items": [["不做社交", "有人看就会表演"], ["不做排行", "记录不是比赛"]]},
            {"type": "phrase", "value": "One more thing"},
            {"type": "feature", "value": "环保", "caption": "外壳用回收铝"},
        ]
        deck, unknown, _, clicks, _ = deck_of(*five)
        out = Path(tmp) / "five.pptx"
        deck.prs.save(str(out))
        again = Presentation(str(out))
        want = {"就地取材", "整屏只剩一张照片和一个光标", "写作建议", "在设备上处理",
                "不做排行", "记录不是比赛", "One more thing", "外壳用回收铝"}
        checks.append(("降级表的五类都导出了，字一个不少",
                       not unknown and len(again.slides) == 5 and want <= texts(again)))
        checks.append(("信号汇入一次出齐，取舍逐条出（共 2 次点击）", clicks == 2))
        checks.append(("这五张没有放不下的字", not fit_notes(deck)))
        checks.append(("不认识的片型报出来，不静默", deck_of({"type": "moment"})[1] == {"moment"}))

        # 正常的课堂片单：概念片的符号 Morph 到公式，提问原地揭晓，推演逐行
        deck, unknown, morphs, clicks, stepped = deck_of(
            {"type": "definition", "value": "周期", "symbol": "T",
             "caption": "来回摆动一次所用的时间", "morph": "T"},
            {"type": "formula", "value": "T = 2π √(L / g)", "items": ["L 摆长", "g 重力加速度"],
             "morph": "T"},
            {"type": "question", "value": "摆长变成 4 倍，周期变成几倍？",
             "items": ["2 倍", "4 倍", "16 倍"], "answer": 0, "caption": "周期与摆长的平方根成正比"},
            {"type": "derive", "value": "一米长的摆，周期约两秒",
             "items": [["T = 2π √(L / g)", "小角度下的周期公式"], ["≈ 2.0 s", "两位有效数字"]]})
        checks.append(("正常片单：1 处 Morph，3 张分步共 5 次点击",
                       (morphs, stepped, clicks) == (1, 3, 5) and not unknown))
        checks.append(("正常片单没有误报放不下或孤行", not fit_notes(deck)))

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


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return 0
    if "--selftest" in argv:
        return selftest()
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
    print("pptx 仍然丢的东西：底色只能纯色、公式是纯文本、图表要手工摆、bento 的大小分层被简化。")
    print("要那个层次的视觉就用 templates/deck.html。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
