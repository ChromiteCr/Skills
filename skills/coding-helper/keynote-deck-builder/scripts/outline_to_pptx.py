#!/usr/bin/env python3
"""从片单 JSON 生成可编辑的 .pptx。

    python3 outline_to_pptx.py deck.json [out.pptx]

这条路的价值是「能在 Keynote 或 PowerPoint 里继续改」。**它会丢东西，要如实告诉使用者**：

  - python-pptx 完全不支持动画与转场，导出来的片子没有任何动效
  - 底色只能是纯色，做不到 HTML 模板里那种多层渐变
  - 颗粒、圆角容器、bento 的大小分层都被简化

要视觉精度就用 templates/deck.html；要可编辑就用这个。两者不冲突，可以都给。

画布是 13.333 × 7.5 英寸，也就是 960 × 540pt，正好是 HTML 舞台（1920 × 1080px）的一半，
所以版面上 px ÷ 2 = pt：大数字 320px 对应 160pt，标题 96px 对应 48pt。
小字这里用 30pt，比 HTML 的 40px（对应 20pt）相对更大，是有意偏严。塞不下就删字，不要调低。

每张片都可以带 "notes"，写进 pptx 的演讲者备注。
逐步出现在 pptx 里做不出来，所以提问片会拆成两张：题目一张、揭晓一张。
图片会先转正、重新编码再放进去，照片里的 GPS 等元数据不会跟着进 pptx。

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
        {"type": "formula",    "value": "T = 2π √(L / g)", "caption": "可省",
                               "items": ["L 摆长", "g 重力加速度"]},
        {"type": "myth",       "value": "误解原话", "caption": "正确说法"},
        {"type": "recap",      "items": [["提示词", "一句要点"]]},
        {"type": "refs",       "items": ["作者（年份）. 题名. 出处."]},

        每张都可以加 "notes": "讲者备注"
      ]
    }
"""

import json
import sys
from pathlib import Path

import io

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
    "dark":  {"bg": "0A0B0E", "ink": "F5F5F7", "muted": "8E8E93"},
    "light": {"bg": "F5F5F7", "ink": "1D1D1F", "muted": "6E6E73"},
}


def rgb(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.lstrip("#").upper())


class Deck:
    def __init__(self, spec: dict):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        pal = THEME[spec.get("theme", "dark")]
        self.bg = rgb(pal["bg"])
        self.ink = rgb(pal["ink"])
        self.muted = rgb(pal["muted"])
        self.accent = rgb(spec.get("accent", "#5A8DEE"))
        self.font = spec.get("font", "Helvetica Neue")
        self.base = Path(spec.get("_base", "."))
        self.warnings = []

    def slide(self):
        s = self.prs.slides.add_slide(self.blank)
        fill = s.background.fill
        fill.solid()
        fill.fore_color.rgb = self.bg
        return s

    def text(self, slide, body, *, top, height, size, color=None,
             bold=False, align=PP_ALIGN.CENTER, left=None, width=None):
        box = slide.shapes.add_textbox(
            left if left is not None else PAD_X,
            top,
            width if width is not None else BODY_W,
            height,
        )
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = str(body)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = self.font
        run.font.color.rgb = color or self.ink
        return box

    # ── 各片型 ────────────────────────────────────────────
    def title(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(2.4), height=Inches(1.9),
                  size=SIZE["phrase"], bold=True)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.5), height=Inches(0.8),
                      size=SIZE["sub"], color=self.muted)

    def phrase(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(2.5), height=Inches(2.5),
                  size=SIZE["phrase"], bold=True)

    def num(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(2.0), height=Inches(2.6),
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
        self.text(s, d["value"], top=Inches(3.1), height=Inches(1.3),
                  size=SIZE["title"], color=self.muted)

    def feature(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(2.6), height=Inches(1.4),
                  size=SIZE["feature"], bold=True)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.2), height=Inches(0.8),
                      size=SIZE["sub"], color=self.muted)

    def specs(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        items = d.get("items", [])[:6]
        col_w = BODY_W / 3
        for n, (k, v) in enumerate(items):
            cx = PAD_X + col_w * (n % 3)
            cy = Inches(2.6) + Inches(1.9) * (n // 3)
            self.text(s, k, top=cy, height=Inches(0.55), size=SIZE["label"],
                      color=self.muted, align=PP_ALIGN.LEFT,
                      left=cx, width=col_w - Inches(0.3))
            self.text(s, v, top=cy + Inches(0.6), height=Inches(0.9), size=64,
                      bold=True, align=PP_ALIGN.LEFT,
                      left=cx, width=col_w - Inches(0.3))

    def versus(self, d):
        s = self.slide()
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        items = d.get("items", [])[:2]
        col_w = BODY_W / 2
        for n, (head, val) in enumerate(items):
            cx = PAD_X + col_w * n
            # 列头必须标明对比的轴，否则「快 3 倍」是没有对象的说法
            self.text(s, head, top=Inches(2.6), height=Inches(0.7),
                      size=SIZE["sub"], color=self.muted,
                      left=cx, width=col_w - Inches(0.4))
            self.text(s, val, top=Inches(3.4), height=Inches(1.8), size=100,
                      bold=True, color=self.accent if n else self.ink,
                      left=cx, width=col_w - Inches(0.4))

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
        items = d.get("items", [])[:5]
        if not items:
            return
        col_w = BODY_W / len(items)
        for n, (name, desc) in enumerate(items):
            cx = PAD_X + col_w * n
            self.text(s, f"{n + 1:02d}", top=Inches(2.7), height=Inches(0.6),
                      size=SIZE["label"], color=self.accent, align=PP_ALIGN.LEFT,
                      left=cx, width=col_w - Inches(0.2))
            self.text(s, name, top=Inches(3.3), height=Inches(0.9), size=44,
                      bold=True, align=PP_ALIGN.LEFT,
                      left=cx, width=col_w - Inches(0.2))
            self.text(s, desc, top=Inches(4.2), height=Inches(1.2),
                      size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT,
                      left=cx, width=col_w - Inches(0.2))

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
        return w, h

    def _contain(self, slide, path, left, top, width, height):
        stream, w, h = self._image_stream(path)
        scale = min(width / w, height / h)
        pw, ph = int(w * scale), int(h * scale)
        slide.shapes.add_picture(stream, left + (width - pw) // 2, top + (height - ph) // 2, pw, ph)

    def roadmap(self, d):
        s = self.slide()
        stops = d.get("items", [])[:4]
        cur = d.get("current")
        if not stops:
            return
        col_w = BODY_W / len(stops)
        for n, name in enumerate(stops):
            color = self.accent if n == cur else self.muted
            self.text(s, name, top=Inches(3.1), height=Inches(1.2), size=SIZE["title"],
                      bold=(n == cur), color=color, left=PAD_X + col_w * n, width=col_w)

    def question(self, d):
        options = d.get("items", [])[:4]
        answer = d.get("answer")
        # 预测题可以不给 answer，那就只出题目这一张，讲完再用另一条片单揭晓
        for reveal in ((False, True) if answer is not None else (False,)):
            s = self.slide()
            if d.get("kicker"):
                self.text(s, d["kicker"], top=Inches(1.3), height=Inches(0.6),
                          size=SIZE["label"], bold=True, color=self.accent)
            self.text(s, d["value"], top=Inches(2.0), height=Inches(1.3), size=SIZE["title"], bold=True)
            if options:
                col_w = BODY_W / len(options)
                for n, opt in enumerate(options):
                    hit = reveal and n == answer
                    color = self.accent if hit else (self.muted if reveal else self.ink)
                    self.text(s, opt, top=Inches(3.6), height=Inches(1.1), size=36, bold=True,
                              color=color, left=PAD_X + col_w * n, width=col_w - Inches(0.2))
            if reveal and d.get("caption"):
                self.text(s, d["caption"], top=Inches(5.0), height=Inches(0.7),
                          size=SIZE["sub"], color=self.muted)

    def image(self, d):
        s = self.slide()
        if not d.get("src"):
            self.warnings.append(f"满版图「{d.get('value', '')}」没有给 src，这张只放了文字")
        else:
            try:
                self._cover(s, d["src"], 0, 0, W, H, tuple(d.get("focus", (0.5, 0.5))))
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
        self.text(s, d["value"], top=PAD_Y, height=Inches(1.4), size=40, bold=True, align=PP_ALIGN.LEFT)
        if d.get("src"):
            try:
                self._contain(s, d["src"], PAD_X, Inches(2.4), BODY_W, Inches(3.9))
            except FileNotFoundError as exc:
                self.warnings.append(f"证据图找不到：{exc}")
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(6.5), height=Inches(0.55),
                      size=SIZE["label"], color=self.muted, align=PP_ALIGN.LEFT)

    def definition(self, d):
        s = self.slide()
        term = d["value"] + (f"  {d['symbol']}" if d.get("symbol") else "")
        self.text(s, term, top=Inches(2.5), height=Inches(1.4), size=SIZE["feature"], bold=True)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(4.1), height=Inches(1.0),
                      size=SIZE["sub"], color=self.muted)

    def formula(self, d):
        s = self.slide()
        self.text(s, d["value"], top=Inches(2.2), height=Inches(1.6), size=SIZE["feature"])
        items = d.get("items", [])[:4]
        if items:
            col_w = BODY_W / len(items)
            for n, item in enumerate(items):
                self.text(s, item, top=Inches(4.3), height=Inches(0.7), size=SIZE["label"],
                          color=self.muted, left=PAD_X + col_w * n, width=col_w)
        if d.get("caption"):
            self.text(s, d["caption"], top=Inches(5.3), height=Inches(0.7),
                      size=SIZE["sub"], color=self.muted)
        self.warnings.append(f"公式「{d['value']}」是纯文本，要在 PowerPoint 或 Keynote 的公式编辑器里重排")

    def myth(self, d):
        s = self.slide()
        self.text(s, "常见误解", top=Inches(1.5), height=Inches(0.6), size=SIZE["label"],
                  bold=True, color=self.muted, align=PP_ALIGN.LEFT)
        self.text(s, d["value"], top=Inches(2.1), height=Inches(1.1), size=44,
                  bold=True, color=self.muted, align=PP_ALIGN.LEFT)
        self.text(s, "实际上", top=Inches(3.7), height=Inches(0.6), size=SIZE["label"],
                  bold=True, color=self.accent, align=PP_ALIGN.LEFT)
        self.text(s, d.get("caption", ""), top=Inches(4.3), height=Inches(1.1), size=44,
                  bold=True, align=PP_ALIGN.LEFT)

    def recap(self, d):
        s = self.slide()
        self.text(s, d.get("value", "回顾"), top=PAD_Y, height=Inches(1.0),
                  size=SIZE["title"], bold=True, align=PP_ALIGN.LEFT)
        for n, (cue, point) in enumerate(d.get("items", [])[:4]):
            y = Inches(2.3) + Inches(1.15) * n
            self.text(s, cue, top=y, height=Inches(0.9), size=32, bold=True, align=PP_ALIGN.LEFT,
                      left=PAD_X, width=Inches(2.6))
            self.text(s, point, top=y, height=Inches(0.9), size=SIZE["sub"], color=self.muted,
                      align=PP_ALIGN.LEFT, left=PAD_X + Inches(2.8), width=BODY_W - Inches(2.8))

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


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__.split("片单格式")[0].strip())

    src = Path(sys.argv[1])
    if not src.is_file():
        sys.exit(f"找不到文件: {src}")

    spec = json.loads(src.read_text(encoding="utf-8"))
    slides = spec.get("slides") or []
    if not slides:
        sys.exit("片单里没有 slides")

    spec["_base"] = str(src.parent)
    deck = Deck(spec)
    handlers = {name: getattr(deck, name) for name in
                ("title", "phrase", "num", "section", "feature",
                 "specs", "versus", "price", "close", "quote", "steps",
                 "roadmap", "question", "image", "claim", "definition",
                 "formula", "myth", "recap", "refs")}

    unknown = set()
    for d in slides:
        fn = handlers.get(d.get("type"))
        if fn is None:
            unknown.add(d.get("type"))
            continue
        before = len(deck.prs.slides)
        fn(d)
        # 一张片单可能生成多张（提问、参考文献续页），备注每张都写
        if d.get("notes"):
            for k in range(before, len(deck.prs.slides)):
                deck.prs.slides[k].notes_slide.notes_text_frame.text = str(d["notes"])
    made = len(deck.prs.slides)

    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pptx")
    deck.prs.save(str(out))

    print(f"已生成: {out}  ({made} 页)")
    if unknown:
        print(f"跳过了不认识的片型: {', '.join(sorted(map(str, unknown)))}")
    for w in deck.warnings:
        print(f"注意：{w}")
    print("这份 pptx 没有动画与转场，底色是纯色 —— python-pptx 做不到这些。")
    print("要那个层次的视觉就用 templates/deck.html。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
