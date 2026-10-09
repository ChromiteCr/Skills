#!/usr/bin/env python3
"""bento-infographic 的测试。

只用两种数据：脚本现画的合成图，和仓库 tests/fixtures/bento-infographic/ 里的样图。
找不到 fixtures（比如单技能 zip 里）就跳过那几条。由 bento.py 的自检参数调起，也可以直接运行本文件。
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO = HERE.parents[3]
FIXTURES = REPO / "tests" / "fixtures" / "bento-infographic"
APPLE = FIXTURES / "apple-reference"

import measure_reference as mr  # noqa: E402
import bento_spec as bs  # noqa: E402
import bento_render as br  # noqa: E402
import bento_layout as bl  # noqa: E402
import bento_check as bc  # noqa: E402

SPECS = FIXTURES / "specs"
CHROME_OK = br.CHROME.exists()


# ---------------------------------------------------------------- synthetic drawings

def superellipse_rect(x0, y0, x1, y1, a, n=5.0, steps=64):
    """Polygon of a rectangle whose corners are superellipse arcs of extent a."""
    pts = []
    quads = [((x1 - a, y0 + a), 1, -1, False),
             ((x0 + a, y0 + a), -1, -1, True),
             ((x0 + a, y1 - a), -1, 1, False),
             ((x1 - a, y1 - a), 1, 1, True)]
    for (cx, cy), sx, sy, rev in quads:
        ts = [i / steps * math.pi / 2 for i in range(steps + 1)]
        if rev:
            ts = ts[::-1]
        for t in ts:
            pts.append((cx + sx * a * math.cos(t) ** (2 / n), cy + sy * a * math.sin(t) ** (2 / n)))
    return pts


def draw_bento(boxes, size=(1600, 900), canvas="#e8e8e8", tile="#ffffff", radius=32,
               corner="circle", scale=4):
    """Draw tiles at 4x and box-downsample, so edges are anti-aliased without ringing."""
    w, h = size
    big = Image.new("RGB", (w * scale, h * scale), canvas)
    d = ImageDraw.Draw(big)
    for x0, y0, x1, y1 in boxes:
        if corner == "circle":
            d.rounded_rectangle([x0 * scale, y0 * scale, x1 * scale - 1, y1 * scale - 1],
                                radius=radius * scale, fill=tile)
        else:
            d.polygon(superellipse_rect(x0 * scale, y0 * scale, x1 * scale, y1 * scale, radius * scale),
                      fill=tile)
    return big.resize((w, h), Image.BOX)


# 1600x900, margin 12, gutter 12, hero 784x432 in the centre; 12 tiles in all.
SYNTH_BOXES = [
    (12, 12, 412, 222), (424, 12, 1024, 222), (1036, 12, 1588, 222),           # top band
    (12, 234, 396, 484), (12, 496, 396, 666),                                    # left column
    (408, 234, 1192, 666),                                                       # hero
    (1204, 234, 1588, 434), (1204, 446, 1588, 666),                              # right column
    (12, 678, 312, 888), (324, 678, 824, 888), (836, 678, 1176, 888), (1188, 678, 1588, 888),
]
SYNTH_HERO = (408, 234, 1192, 666)


class MeasureSynthetic(unittest.TestCase):
    def _check(self, img):
        res = mr.measure_image(img)
        self.assertEqual(res["n_tiles"], len(SYNTH_BOXES))
        got = sorted(tuple(t["box"]) for t in res["tiles"])
        for want, have in zip(sorted(SYNTH_BOXES), got):
            for a, b in zip(want, have):
                self.assertLessEqual(abs(a - b), 1, (want, have))
        radii = [r for t in res["tiles"] for r in t["radius"] if r is not None]
        self.assertTrue(radii)
        self.assertTrue(29 <= float(np.median(radii)) <= 35, np.median(radii))
        g = res["gutters"]["median"]
        self.assertTrue(11 <= g <= 13, g)
        self.assertEqual(tuple(res["hero"]["box"]), SYNTH_HERO)
        self.assertLessEqual(abs(res["hero"]["center_offset"][0]), 0.001)
        self.assertLessEqual(abs(res["hero"]["center_offset"][1]), 0.001)
        return res

    def test_light(self):
        res = self._check(draw_bento(SYNTH_BOXES))
        self.assertEqual(res["background"], "#e8e8e8")

    def test_dark(self):
        res = self._check(draw_bento(SYNTH_BOXES, canvas="#181818", tile="#000000"))
        self.assertEqual(res["background"], "#181818")

    def test_round_corner_vs_squircle(self):
        circle = mr.measure_image(draw_bento(SYNTH_BOXES, radius=32))
        squircle = mr.measure_image(draw_bento(SYNTH_BOXES, radius=72, corner="squircle"))
        c, s = circle["curve_ratio_median"], squircle["curve_ratio_median"]
        self.assertIsNotNone(c)
        self.assertIsNotNone(s)
        self.assertTrue(0.7 <= c <= 1.15, c)
        self.assertGreater(s, c + 0.3)

    def test_cut_splits_merged_tiles(self):
        # Two tiles touching with no gutter read as one; a cut separates them again.
        img = draw_bento([(12, 12, 400, 400), (12, 400, 400, 888), (412, 12, 1588, 888)])
        self.assertEqual(mr.measure_image(img)["n_tiles"], 2)
        cut = {"y": 400, "x0": 0, "x1": 405, "width": 2}
        self.assertEqual(mr.measure_image(img, cuts=[cut])["n_tiles"], 3)


@unittest.skipUnless((APPLE / "labels.json").exists(), "Apple reference fixtures not present")
class MeasureApple(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = mr.measure_dir(APPLE)

    def by_prefix(self, prefix):
        return next(r for r in self.results["images"] if r["file"].startswith(prefix))

    def test_tile_counts(self):
        counts = [self.by_prefix(p)["n_tiles"] for p in ("01", "02", "03", "04", "05", "06")]
        self.assertEqual(counts, [16, 17, 18, 17, 14, 16])

    def test_hero_dead_centre(self):
        for r in self.results["images"]:
            dx, dy = r["hero"]["center_offset"]
            # Sample 1 is cropped flush on the right and its frosted edges are gradients.
            limit = 0.005 if r["file"].startswith("01") else 0.002
            self.assertLessEqual(max(abs(dx), abs(dy)), limit, r["file"])

    def test_product_hero_is_half_by_half(self):
        for p in ("01", "04", "05", "06"):
            hero = self.by_prefix(p)["hero"]
            self.assertTrue(0.48 <= hero["w_frac"] <= 0.50, (p, hero["w_frac"]))
            self.assertTrue(0.47 <= hero["h_frac"] <= 0.49, (p, hero["h_frac"]))

    def test_unit_gutter_radius(self):
        # 2026-10-08 sub-pixel re-measure: u 1.22-1.23% W, gutter 0.67-0.68u, radius 1.53-1.56u.
        if not mr.SF_FONT.exists():
            self.skipTest("SF Pro system font not available")
        for p in ("02", "03", "04", "05", "06"):
            s = self.by_prefix(p)["summary"]
            self.assertTrue(0.0118 <= s["u_frac_w"] <= 0.0128, (p, s["u_frac_w"]))
            self.assertTrue(0.62 <= s["gutter_u"] <= 0.72, (p, s["gutter_u"]))
            self.assertTrue(1.50 <= s["radius_u"] <= 1.62, (p, s["radius_u"]))

    def test_gutter_and_radius_follow_canvas_width(self):
        # Sample 1 sets its labels larger, but its gutter and radius are the same share of the width.
        for r in self.results["images"]:
            w = r["size"][0]
            s = r["summary"]
            self.assertTrue(0.0075 <= s["gutter_px"] / w <= 0.0088, (r["file"], s["gutter_px"] / w))
            self.assertTrue(0.0183 <= s["radius_px"] / w <= 0.0195, (r["file"], s["radius_px"] / w))

    def test_corners_are_circular(self):
        for p in ("03", "04", "05", "06"):
            ratio = self.by_prefix(p)["curve_ratio_median"]
            self.assertIsNotNone(ratio, p)
            self.assertTrue(0.8 <= ratio <= 1.2, (p, ratio))


# ---------------------------------------------------------------- spec

def minimal_spec(**over):
    spec = {
        "schema": "bento/1",
        "canvas": {"use": "screen", "width": 3840, "height": 2160, "dpr": 2},
        "theme": "light", "mode": "product", "lang": "zh-CN", "font": "system", "accent": None,
        "source_line": None,
        "tiles": [
            {"id": "hero", "kind": "hero", "word": "Skills", "weight": 3},
            {"id": "a", "kind": "word", "word": "写作规则", "label": "去掉套话"},
        ],
    }
    spec.update(over)
    return spec


class SpecTests(unittest.TestCase):
    def test_unit(self):
        self.assertAlmostEqual(bs.unit_px(1920, 1080, "screen"), 23.76, places=2)
        self.assertAlmostEqual(bs.unit_px(621, 828, "phone"), 17.388, places=2)
        self.assertAlmostEqual(bs.unit_px(1240, 1754, "print"), 27.28, places=2)

    def test_tokens_ratios(self):
        t = bs.tokens(1920, 1080, "screen", "light", "zh-CN")
        u = t["u"]
        for key, ratio in (("gutter", 0.68), ("margin", 0.68), ("radius", 1.55), ("inset", 0.95),
                           ("word", 1.75), ("number", 3.2)):
            self.assertAlmostEqual(t[key] / u, ratio, places=2, msg=key)
        self.assertEqual(t["line_height"], 1.3)
        self.assertEqual(bs.tokens(1920, 1080, "screen", "dark", "en")["line_height"], 1.18)
        self.assertEqual(t["weight"], 600)
        self.assertEqual((t["canvas"], t["tile"], t["ink"]), ("#e8e8e8", "#ffffff", "#000000"))
        d = bs.tokens(1920, 1080, "screen", "dark", "zh-CN")
        self.assertEqual((d["canvas"], d["tile"], d["ink"]), ("#181818", "#000000", "#ffffff"))

    def test_font_stack_puts_system_ui_first(self):
        self.assertTrue(bs.FONT_STACKS["system"].startswith("system-ui"))
        self.assertNotIn("-apple-system", bs.FONT_STACKS["system"])
        self.assertIn('"Inter"', bs.FONT_STACKS["system"])

    def test_validate_catches_problems(self):
        def errs(**over):
            return bs.validate_spec(minimal_spec(**over))
        self.assertEqual(errs(), [])
        two_heroes = minimal_spec()["tiles"] + [{"id": "h2", "kind": "hero", "word": "X"}]
        self.assertTrue(any("恰好有一个" in e for e in errs(tiles=two_heroes)))
        long_label = [minimal_spec()["tiles"][0], {"id": "a", "kind": "word", "word": "写作", "label": "这是一个超过十二个字的很长很长的标签"}]
        self.assertTrue(any("超过 12 字" in e for e in errs(tiles=long_label)))
        wide_line = [minimal_spec()["tiles"][0], {"id": "a", "kind": "word", "word": "写作", "label": "一二三四五六七八九十十一\n二"}]
        found = errs(tiles=wide_line)
        self.assertTrue(any("一行约" in e for e in found), found)
        self.assertTrue(any("孤字" in e for e in found), found)
        no_source = [minimal_spec()["tiles"][0], {"id": "n", "kind": "stat", "value": "62", "label": "技能"}]
        self.assertTrue(any("facts" in e for e in errs(tiles=no_source)))
        ok_unverified = [minimal_spec()["tiles"][0], {"id": "n", "kind": "stat", "value": "62", "label": "技能（未确认）",
                                                      "unverified": True}]
        self.assertEqual(errs(tiles=ok_unverified), [])
        hidden = [minimal_spec()["tiles"][0], {"id": "n", "kind": "stat", "value": "62", "label": "技能", "unverified": True}]
        self.assertTrue(any("看得出来" in e for e in errs(tiles=hidden)))
        chart = [minimal_spec()["tiles"][0], {"id": "c", "kind": "chart", "series": [1, 2, 3], "label": "趋势",
                                              "unverified": True}]
        self.assertTrue(any("research" in e for e in errs(tiles=chart)))
        unknown = [minimal_spec()["tiles"][0], {"id": "x", "kind": "banner", "label": "横幅"}]
        self.assertTrue(any("未知的 kind" in e for e in errs(tiles=unknown)))
        missing = [minimal_spec()["tiles"][0], {"id": "p", "kind": "photo", "image": "nope.jpg", "label": "照片"}]
        self.assertTrue(any("图片不存在" in e for e in bs.validate_spec(minimal_spec(tiles=missing), HERE)))

    def test_cjk_spacing(self):
        self.assertEqual(bs.cjk_spacing_problems("测量结果3mm"), ["果3"])
        self.assertEqual(bs.cjk_spacing_problems("测量结果 3 mm"), [])

    @unittest.skipUnless((SPECS / "replica-16x9.json").exists(), "specs fixture not present")
    def test_replica_spec_is_valid(self):
        spec = bs.load_spec(SPECS / "replica-16x9.json")
        self.assertEqual(bs.validate_spec(spec, SPECS), [])


# ---------------------------------------------------------------- render (command-line Chrome)

@unittest.skipUnless(CHROME_OK and (SPECS / "replica-16x9.json").exists(), "Chrome or specs fixture missing")
class RenderCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        import tempfile
        cls.tmp = Path(tempfile.mkdtemp(prefix="bento-test-"))
        spec = bs.load_spec(SPECS / "replica-16x9.json")
        layout = json.loads((SPECS / "replica-16x9.layout.json").read_text(encoding="utf-8"))
        html_path = br.build_html(spec, layout, cls.tmp, base_dir=SPECS)
        cls.png = br.screenshot_cli(html_path, cls.tmp / "replica.png", 1920, 1080, 2)
        cls.measure = mr.measure(cls.png)
        cls.u_out = bs.unit_px(1920, 1080, "screen") * 2

    def test_png_size(self):
        with Image.open(self.png) as im:
            self.assertEqual(im.size, (3840, 2160))

    def test_object_and_flank_tiles_build(self):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-kinds-"))
        Image.new("RGB", (400, 300), "#888888").save(tmp / "thing.png")
        spec = minimal_spec(tiles=[
            {"id": "hero", "kind": "hero", "word": "Demo", "weight": 3},
            {"id": "obj", "kind": "object", "image": "thing.png", "label": "侧面"},
            {"id": "fl", "kind": "flank", "image": "thing.png", "left": "6.9″", "right": "6.3″", "label": "两种尺寸（未确认）",
             "unverified": True},
        ])
        self.assertEqual(bs.validate_spec(spec, tmp), [])
        layout = {"schema": "bento-layout/1", "grid": {"cols": 28, "rows": 16},
                  "cells": {"hero": [7, 4, 14, 8], "obj": [0, 0, 7, 4], "fl": [21, 0, 7, 4]}}
        page = br.build_html(spec, layout, tmp / "out", base_dir=tmp).read_text(encoding="utf-8")
        self.assertIn('data-kind="object"', page)
        self.assertIn('class="flank-side"', page)
        self.assertIn("6.9″", page)
        self.assertNotIn("{{", page)

    def test_measured_like_apple(self):
        m = self.measure
        self.assertEqual(m["n_tiles"], 17)
        g = m["gutters"]["median"] / self.u_out
        self.assertTrue(0.65 <= g <= 0.71, g)
        radii = [r for t in m["tiles"] for r in t["radius"] if r is not None]
        self.assertTrue(1.50 <= float(np.median(radii)) / self.u_out <= 1.60, float(np.median(radii)) / self.u_out)
        hero = m["hero"]
        self.assertTrue(0.48 <= hero["w_frac"] <= 0.50, hero["w_frac"])
        self.assertTrue(0.47 <= hero["h_frac"] <= 0.49, hero["h_frac"])
        self.assertLessEqual(max(abs(v) for v in hero["center_offset"]), 0.002)


# ---------------------------------------------------------------- DevTools-protocol renderer

PROBE_PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
html,body{margin:0;width:600px;height:400px;background:#ffffff;overflow:hidden}
#red{position:absolute;left:50px;top:50px;width:100px;height:100px;background:#ff0000}
.sys{position:absolute;left:200px;top:40px;font:600 24px system-ui, BlinkMacSystemFont, "PingFang SC", sans-serif}
.apple{position:absolute;left:200px;top:90px;font:600 24px -apple-system}
.inter{position:absolute;left:200px;top:140px;font:600 24px "Inter"}
@page{size:600px 400px;margin:0}
</style></head><body><div id="red"></div><div class="sys">AB 中文</div><div class="apple">AB</div>
<div class="inter">AB</div>
<script>
window.__bentoReady = new Promise(res => setTimeout(() => {
  const d = document.createElement('div');
  d.style.cssText = 'position:absolute;left:300px;top:250px;width:40px;height:40px;background:#000';
  document.body.appendChild(d); res(true);
}, 1500));
</script></body></html>"""


def families_for(chrome, selector):
    chrome.call("DOM.enable")
    chrome.call("CSS.enable")
    root = chrome.call("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
    node = chrome.call("DOM.querySelector", {"nodeId": root, "selector": selector})["nodeId"]
    return [f.get("familyName") for f in chrome.call("CSS.getPlatformFontsForNode", {"nodeId": node}).get("fonts", [])]


@unittest.skipUnless(CHROME_OK, "Chrome missing")
class ChromeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.tmp = Path(tempfile.mkdtemp(prefix="bento-chrome-test-"))
        (cls.tmp / "probe.html").write_text(PROBE_PAGE, encoding="utf-8")
        cls.chrome = br.Chrome()
        cls.chrome.open(cls.tmp / "probe.html", 600, 400, 2)
        cls.png = cls.chrome.screenshot(cls.tmp / "probe.png")

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def test_size_and_pixels(self):
        with Image.open(self.png) as im:
            self.assertEqual(im.size, (1200, 800))
            r, g, b = im.convert("RGB").getpixel((200, 200))
            self.assertTrue(r > 240 and g < 20 and b < 20, (r, g, b))

    def test_waits_for_page_ready(self):
        # The black square appears 1.5 s after load; the screenshot must contain it.
        with Image.open(self.png) as im:
            self.assertEqual(im.convert("RGB").getpixel((640, 540)), (0, 0, 0))

    def test_system_stack_uses_sf_and_pingfang(self):
        fams = families_for(self.chrome, ".sys")
        self.assertTrue(any("SF" in (f or "") or f == "System Font" for f in fams), fams)
        self.assertIn("PingFang SC", fams)

    def test_apple_system_alone_does_not_reach_sf(self):
        # Chrome ignores -apple-system; that is why the stack starts with system-ui (4.8).
        fams = families_for(self.chrome, ".apple")
        self.assertFalse(any("SF" in (f or "") or f == "System Font" for f in fams), fams)

    def test_pdf_is_one_page_of_the_right_size(self):
        if not any((f or "").startswith("Inter") for f in families_for(self.chrome, ".inter")):
            self.skipTest("Inter is not installed (PDF uses the open fonts)")
        import re
        pdf = self.chrome.print_pdf(self.tmp / "probe.pdf").read_bytes()
        boxes = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
        self.assertTrue(boxes)
        w, h = float(boxes[0][0]), float(boxes[0][1])
        self.assertAlmostEqual(w, 600 * 0.75, delta=1)
        self.assertAlmostEqual(h, 400 * 0.75, delta=1)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), 1)


@unittest.skipUnless(CHROME_OK and (SPECS / "replica-16x9.json").exists(), "Chrome or specs fixture missing")
class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-render-test-"))
        cls.a = br.render(SPECS / "replica-16x9.json", SPECS / "replica-16x9.layout.json", tmp / "a")
        cls.b = br.render(SPECS / "replica-16x9.json", SPECS / "replica-16x9.layout.json", tmp / "b")
        cls.dom = json.loads(Path(cls.a["dom"]).read_text(encoding="utf-8"))
        cls.fonts = json.loads(Path(cls.a["fonts"]).read_text(encoding="utf-8"))

    def test_outputs_exist(self):
        for key in ("html", "png", "textless_png", "dom", "fonts"):
            self.assertTrue(Path(self.a[key]).exists(), key)
        with Image.open(self.a["png"]) as im:
            self.assertEqual(im.size, (3840, 2160))

    def test_same_input_same_bytes(self):
        import hashlib
        digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
        self.assertEqual(digest(self.a["png"]), digest(self.b["png"]))

    def test_dom_metrics(self):
        self.assertEqual(len(self.dom["tiles"]), 17)
        self.assertEqual(self.dom["canvas"], {"w": 1920, "h": 1080, "dpr": 2})
        labels = {t["tile"]: t for t in self.dom["texts"] if t["role"] == "label"}
        self.assertEqual(labels["grade"]["lines"], 1)
        self.assertAlmostEqual(labels["grade"]["font_size"], 23.76, places=1)
        self.assertEqual(labels["grade"]["font_weight"], 600)
        self.assertFalse(any(t["wide"] for t in self.dom["texts"]))

    def test_every_text_uses_listed_fonts(self):
        allowed = {".SF NS", "SF Pro", "System Font", "PingFang SC", "Inter", "Noto Sans SC"}
        for entry in self.fonts:
            for f in entry["fonts"]:
                self.assertIn(f["family"], allowed, entry)


# ---------------------------------------------------------------- plan command

class PlanTests(unittest.TestCase):
    def run_plan(self, spec_path, out):
        import contextlib
        import io
        import bento
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = bento.main(["plan", str(spec_path), "--out", str(out)])
        return code, buf.getvalue()

    @unittest.skipUnless((SPECS / "product-16x9-light.json").exists(), "specs fixture not present")
    def test_good_spec_prints_table_and_wireframe(self):
        import tempfile
        out = Path(tempfile.mkdtemp(prefix="bento-plan-"))
        code, text = self.run_plan(SPECS / "product-16x9-light.json", out)
        self.assertEqual(code, 0, text)
        self.assertIn("格数 %d" % len(bs.load_spec(SPECS / "product-16x9-light.json")["tiles"]), text)
        self.assertIn("62 / 个技能", text)
        self.assertTrue((out / "wireframe.png").exists())

    def test_bad_spec_reports_problems(self):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-plan-bad-"))
        spec = minimal_spec(tiles=[
            {"id": "hero", "kind": "hero", "word": "Demo", "weight": 3},
            {"id": "long", "kind": "word", "word": "写作", "label": "这是一个超过十二个字的很长很长的标签"},
            {"id": "num", "kind": "stat", "value": "62", "label": "技能"},
        ])
        (tmp / "bento.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        code, text = self.run_plan(tmp / "bento.json", tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("超过 12 字", text)
        self.assertIn("facts", text)

    @unittest.skipUnless((SPECS / "research-3x4.layout.json").exists(), "research fixture not present")
    def test_without_chrome(self):
        import contextlib
        import io
        import os
        import tempfile
        import bento
        out = Path(tempfile.mkdtemp(prefix="bento-nochrome-"))
        args = ["render", str(SPECS / "research-3x4.json"), str(SPECS / "research-3x4.layout.json"), "--out"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(bento.main(args + [str(out / "html"), "--html-only"]), 0)
        self.assertTrue((out / "html" / "bento.html").exists())
        self.assertIn("降级", buf.getvalue())
        saved = br.CHROME
        try:
            br.CHROME = Path("/nonexistent/chrome")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(bento.main(args + [str(out / "png")]), 4)
            self.assertIn("BENTO_CHROME", err.getvalue())
        finally:
            br.CHROME = saved
        os.environ["BENTO_CHROME"] = "/opt/some/chrome"
        try:
            self.assertEqual(br.find_chrome(), Path("/opt/some/chrome"))
        finally:
            del os.environ["BENTO_CHROME"]


# ---------------------------------------------------------------- QA checks

@unittest.skipUnless(CHROME_OK and (SPECS / "product-16x9.layout.json").exists(), "Chrome or specs fixture missing")
class QaTests(unittest.TestCase):
    """A good render passes every check; each way of breaking it is caught by its own check."""

    @classmethod
    def setUpClass(cls):
        import json
        import tempfile
        cls.tmp = Path(tempfile.mkdtemp(prefix="bento-qa-"))
        cls.spec_path = SPECS / "product-16x9-light.json"
        cls.layout = json.loads((SPECS / "product-16x9.layout.json").read_text(encoding="utf-8"))
        r = br.render(cls.spec_path, SPECS / "product-16x9.layout.json", cls.tmp, run_check=False)
        cls.png, cls.textless = r["png"], r["textless_png"]
        cls.dom = json.loads(Path(r["dom"]).read_text(encoding="utf-8"))
        cls.dom["fonts"] = json.loads(Path(r["fonts"]).read_text(encoding="utf-8"))
        cls.spec = bs.load_spec(cls.spec_path)

    def run_check(self, spec=None, dom=None, png=None):
        return bc.check(spec or self.spec, self.layout, dom or self.dom, png or self.png, self.textless)

    def failed(self, qa):
        return {c["id"] for c in qa["checks"] if not c["pass"]}

    def mutated_dom(self):
        import copy
        return copy.deepcopy(self.dom)

    def text_of(self, dom, role, tile=None):
        return next(t for t in dom["texts"] if t["role"] == role and (tile is None or t["tile"] == tile))

    def test_good_render_passes(self):
        qa = self.run_check()
        self.assertTrue(qa["pass"], [c for c in qa["checks"] if not c["pass"]])
        self.assertEqual(len(qa["checks"]), 19)

    def test_overflow(self):
        d = self.mutated_dom()
        self.text_of(d, "label")["wide"] = True
        self.assertEqual(self.failed(self.run_check(dom=d)), {"overflow"})

    def test_weight(self):
        d = self.mutated_dom()
        self.text_of(d, "label")["font_weight"] = 700
        self.assertEqual(self.failed(self.run_check(dom=d)), {"weight"})

    def test_unit_size_and_type_scale(self):
        d = self.mutated_dom()
        self.text_of(d, "label")["font_size"] = 20.0
        self.assertIn("unit_size", self.failed(self.run_check(dom=d)))
        d = self.mutated_dom()
        self.text_of(d, "number")["font_size"] = 10 * bs.unit_px(1920, 1080, "screen")
        self.assertIn("type_scale", self.failed(self.run_check(dom=d)))

    def test_contrast(self):
        d = self.mutated_dom()
        self.text_of(d, "label", "lyrics")["color"] = "rgb(170, 170, 170)"
        self.assertEqual(self.failed(self.run_check(dom=d)), {"contrast"})

    def test_accent_hues(self):
        d = self.mutated_dom()
        self.text_of(d, "number", "skills")["color"] = "rgb(230, 30, 30)"
        self.text_of(d, "number", "cases")["color"] = "rgb(30, 60, 230)"
        self.assertIn("accent_hues", self.failed(self.run_check(dom=d)))

    def test_text_only_share(self):
        import copy
        spec = copy.deepcopy(self.spec)
        for t in spec["tiles"]:
            if t["kind"] == "icon":
                t.update({"kind": "word", "word": "示例"})
                t.pop("icon")
        self.assertIn("text_only_share", self.failed(self.run_check(spec=spec)))

    def test_tile_count(self):
        import copy
        spec = copy.deepcopy(self.spec)
        spec["tiles"] = spec["tiles"][:9]
        self.assertIn("tile_count", self.failed(self.run_check(spec=spec)))

    def test_hero_center(self):
        d = self.mutated_dom()
        hero = next(t for t in d["tiles"] if t["id"] == "hero")
        hero["rect"][0] += 40
        self.assertIn("hero_center", self.failed(self.run_check(dom=d)))

    def test_fonts(self):
        d = self.mutated_dom()
        d["fonts"][0]["fonts"].append({"family": "Times", "postscript": "Times-Roman", "glyphs": 3})
        self.assertEqual(self.failed(self.run_check(dom=d)), {"fonts"})

    def test_gutter_radius_min_tile(self):
        d = self.mutated_dom()
        tile = next(t for t in d["tiles"] if t["id"] == "lyrics")
        tile["rect"][0] += 3
        self.assertIn("gutter_uniform", self.failed(self.run_check(dom=d)))
        d = self.mutated_dom()
        next(t for t in d["tiles"] if t["id"] == "lyrics")["radius"] = 10.0
        self.assertEqual(self.failed(self.run_check(dom=d)), {"radius_uniform"})
        d = self.mutated_dom()
        next(t for t in d["tiles"] if t["id"] == "lyrics")["rect"][3] = 2 * bs.unit_px(1920, 1080, "screen")
        self.assertIn("min_tile", self.failed(self.run_check(dom=d)))

    def test_label_lines(self):
        d = self.mutated_dom()
        self.text_of(d, "label", "lyrics")["lines"] = 3
        self.assertEqual(self.failed(self.run_check(dom=d)), {"label_lines"})

    def test_cjk_spacing(self):
        import copy
        spec = copy.deepcopy(self.spec)
        next(t for t in spec["tiles"] if t["id"] == "lyrics")["label"] = "测量结果3mm"
        self.assertIn("cjk_spacing", self.failed(self.run_check(spec=spec)))

    def test_output_size(self):
        small = self.tmp / "small.png"
        Image.open(self.png).resize((1920, 1080)).save(small)
        self.assertEqual(self.failed(self.run_check(png=small)), {"output_size"})

    def test_upscale_is_a_warning(self):
        qa = self.run_check()
        up = next(c for c in qa["checks"] if c["id"] == "image_upscale")
        self.assertTrue(up["pass"])
        self.assertTrue(any("放大" in w for w in qa["warnings"]))


# ---------------------------------------------------------------- layout engine

def stub_spec(n_ring: int, hero: dict, w: int = 3840, h: int = 2160, use: str = "screen", aspects=None) -> dict:
    tiles = [dict({"id": "hero", "kind": "hero"}, **hero)]
    for i in range(n_ring):
        a = aspects[i] if aspects else 1.3
        tiles.append({"id": "t%02d" % i, "kind": "photo", "image": "x.jpg", "_img_aspect": a, "weight": 1})
    return {"schema": "bento/1", "canvas": {"use": use, "width": w, "height": h, "dpr": 2}, "theme": "light",
            "mode": "product", "lang": "en", "tiles": tiles, "seed": 0}


def occupancy_ok(layout) -> bool:
    cols, rows = layout["grid"]["cols"], layout["grid"]["rows"]
    return bl.coverage_ok([tuple(v) for v in layout["cells"].values()], cols, rows)


class LayoutTests(unittest.TestCase):
    def tok(self, w=1920, h=1080, use="screen"):
        return bs.tokens(w, h, use, "light", "en")

    def test_grid_for(self):
        self.assertEqual(bl.grid_for(1920, 1080, 23.76), (56, 32))
        self.assertEqual(bl.grid_for(621, 828, 17.39), (24, 32))
        self.assertEqual(bl.grid_for(540, 960, 15.12), (24, 44))

    def test_place_hero(self):
        t = self.tok()
        self.assertEqual(bl.place_hero(56, 32, {"image": "p.png", "fit": "cover"}, t), (14, 8, 28, 16))
        self.assertEqual(bl.place_hero(56, 32, {"word": "iOS"}, t), (17, 11, 22, 10))
        self.assertEqual(bl.place_hero(56, 32, {"image": "p.png", "_img_aspect": 1.0}, t), (18, 8, 20, 16))
        phone = bs.tokens(621, 828, "phone", "light", "en")
        c, r, w, h = bl.place_hero(24, 32, {"image": "p.png", "_img_aspect": 1.6}, phone)
        self.assertEqual((c, w), (0, 24))
        self.assertEqual((32 - h) % 2, 0)

    def test_candidates_are_valid(self):
        spec = stub_spec(15, {"image": "p.png", "fit": "cover"})
        cands = bl.candidates(spec, n=3, seeds=200)
        self.assertEqual(len(cands), 3)
        t = self.tok()
        px, py = bl.pitches(t, 56, 32)
        for lay in cands:
            self.assertTrue(occupancy_ok(lay))
            self.assertEqual(len(lay["cells"]), 16)
            self.assertEqual(lay["cells"]["hero"], [14, 8, 28, 16])
            rects = [tuple(v) for v in lay["cells"].values()]
            self.assertLessEqual(bl.through_seams(rects, 56, 32), 2)
            for rect in rects:
                x, y, w, h = bl.rect_px(rect, t, px, py)
                self.assertGreaterEqual(w, 6.0 * t["u"] - 0.01)
                self.assertGreaterEqual(h, 4.8 * t["u"] - 0.01)
                self.assertLessEqual(max(w / h, h / w), 3.5 + 1e-6)
        sigs = {(tuple(sorted((v[2], v[3]) for v in c["cells"].values())), tuple(c["pattern"].values())) for c in cands}
        self.assertEqual(len(sigs), 3)

    def test_same_seed_same_layout(self):
        spec = stub_spec(15, {"image": "p.png", "fit": "cover"})
        self.assertEqual(bl.candidates(spec, n=2, seeds=120), bl.candidates(spec, n=2, seeds=120))

    def test_long_label_never_lands_in_a_narrow_tile(self):
        spec = stub_spec(15, {"image": "p.png", "fit": "cover"})
        spec["tiles"][1] = {"id": "long", "kind": "icon", "icon": "x", "weight": 1,
                            "label": "Photographic Styles with texture"}
        t = self.tok()
        px, py = bl.pitches(t, 56, 32)
        for lay in bl.candidates(spec, n=3, seeds=200):
            x, y, w, h = bl.rect_px(lay["cells"]["long"], t, px, py)
            self.assertGreaterEqual(w / t["u"] + 1e-6, bl.text_u("Photographic Styles with texture") + 2 * bs.RATIOS["pad"])

    def test_fast_enough(self):
        import time
        spec = stub_spec(16, {"image": "p.png", "fit": "cover"})
        start = time.time()
        bl.candidates(spec, n=3, seeds=500)
        self.assertLess(time.time() - start, 4.0)


@unittest.skipUnless((APPLE / "measurements.json").exists(), "Apple measurements not present")
class LayoutRegression(unittest.TestCase):
    """Fed each sample's tile count and hero shape, the engine must reproduce its structure."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.m = json.loads((APPLE / "measurements.json").read_text(encoding="utf-8"))

    def bands(self, r):
        W, H = r["size"]
        hero = r["hero"]["box"]
        # Outer edge of the top band (tiles above the hero) and of the left column (tiles left of it).
        tops = [t["box"] for t in r["tiles"] if t["box"][3] <= hero[1] + 2 and t["box"][0] < hero[2] and t["box"][2] > hero[0]]
        lefts = [t["box"] for t in r["tiles"] if t["box"][2] <= hero[0] + 2 and t["box"][1] < hero[3] and t["box"][3] > hero[1]]
        top = max(b[3] for b in tops) / H if tops else None
        left = max(b[2] for b in lefts) / W if lefts else None
        return top, left

    def test_samples(self):
        for r in self.m["images"]:
            W, H = r["size"]
            hero = r["hero"]
            word_hero = r["file"].startswith("03")
            hero_spec = {"word": "iOS"} if word_hero else {"image": "p.png", "box_aspect": hero["aspect"]}
            aspects = [(t["box"][2] - t["box"][0]) / (t["box"][3] - t["box"][1])
                       for i, t in enumerate(r["tiles"]) if i != hero["index"]]
            spec = stub_spec(r["n_tiles"] - 1, hero_spec, aspects=aspects)
            cands = bl.candidates(spec, n=3, seeds=300)
            self.assertTrue(cands, r["file"])
            tok = bs.tokens(1920, 1080, "screen", "light", "en")
            px, py = bl.pitches(tok, *[cands[0]["grid"][k] for k in ("cols", "rows")])
            hb = [hero["box"][0] / W, hero["box"][1] / H, hero["box"][2] / W, hero["box"][3] / H]
            best_iou, best_band = 0.0, 1.0
            top_s, left_s = self.bands(r)
            for lay in cands:
                self.assertEqual(len(lay["cells"]), r["n_tiles"])
                x, y, w, h = bl.rect_px(lay["cells"]["hero"], tok, px, py)
                ob = [x / 1920, y / 1080, (x + w) / 1920, (y + h) / 1080]
                best_iou = max(best_iou, box_iou(ob, hb))
                c0, r0 = lay["cells"]["hero"][0], lay["cells"]["hero"][1]
                top_o = (tok["margin"] + r0 * py - tok["gutter"]) / 1080
                left_o = (tok["margin"] + c0 * px - tok["gutter"]) / 1920
                diffs = [abs(top_o - top_s) if top_s else 0, abs(left_o - left_s) if left_s else 0]
                best_band = min(best_band, max(diffs))
            if r["file"].startswith(("02", "03")):
                self.assertGreaterEqual(best_iou, 0.75, r["file"])
            else:
                self.assertGreaterEqual(best_iou, 0.90, r["file"])
                self.assertLessEqual(best_band, 0.02, r["file"])


# ---------------------------------------------------------------- alignment with the official iPhone 18 Pro slide

def box_iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


@unittest.skipUnless(CHROME_OK and (SPECS / "iphone-18-pro-dark.json").exists()
                     and (APPLE / "06-iphone-18-pro.webp").exists(), "Chrome or alignment fixtures missing")
class AlignIphone18Pro(unittest.TestCase):
    """Same content as Apple's slide (crops of its pictures), our layout and type: the structure must line up."""

    @classmethod
    def setUpClass(cls):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-align-"))
        spec = bs.load_spec(SPECS / "iphone-18-pro-dark.json")
        layout = json.loads((SPECS / "iphone-18-pro-dark.layout.json").read_text(encoding="utf-8"))
        html_path = br.build_html(spec, layout, tmp, base_dir=SPECS)
        png = br.screenshot_cli(html_path, tmp / "ours.png", 2000, 1125, 2)
        small = tmp / "ours-2000.png"
        Image.open(png).convert("RGB").resize((2000, 1125), Image.LANCZOS).save(small)
        cls.ours = mr.measure(small)
        cls.official = mr.measure(APPLE / "06-iphone-18-pro.webp")

    def test_same_tile_count(self):
        self.assertEqual(self.ours["n_tiles"], self.official["n_tiles"])

    def test_tiles_line_up(self):
        ious = [max(box_iou(o["box"], t["box"]) for o in self.ours["tiles"]) for t in self.official["tiles"]]
        self.assertGreaterEqual(float(np.median(ious)), 0.90, ious)
        self.assertGreaterEqual(min(ious), 0.75, ious)
        self.assertGreaterEqual(box_iou(self.ours["hero"]["box"], self.official["hero"]["box"]), 0.97)

    def test_gutter_and_radius_match(self):
        g = self.ours["gutters"]["median"] / self.official["gutters"]["median"]
        self.assertTrue(0.95 <= g <= 1.05, g)
        ro = float(np.median([r for t in self.ours["tiles"] for r in t["radius"] if r is not None]))
        rf = float(np.median([r for t in self.official["tiles"] for r in t["radius"] if r is not None]))
        self.assertTrue(0.94 <= ro / rf <= 1.06, ro / rf)


# ---------------------------------------------------------------- any aspect ratio, Chinese labels (round 7)

# The nine canvases of AUDIT-AND-IDEAS.md 4.12 round 7: name -> (output width, height, use).
CANVASES = {
    "16x9": (3840, 2160, "screen"), "4x3": (2048, 1536, "screen"), "21x9": (3440, 1440, "screen"),
    "a4": (2480, 3508, "print"), "1x1": (2160, 2160, "phone"), "3x4": (1242, 1656, "phone"),
    "4x5": (1080, 1350, "phone"), "9x16": (1080, 1920, "phone"), "1x2": (1080, 2160, "phone"),
}
MATRIX = SPECS / "matrix"


class RatioTests(unittest.TestCase):
    def test_grid_for_every_canvas(self):
        for name, (w, h, use) in CANVASES.items():
            tok = bs.tokens(w / 2, h / 2, use)
            cols, rows = bl.grid_for(w / 2, h / 2, tok["u"])
            self.assertEqual((cols % 4, rows % 4), (0, 0), name)
            cw, ch = br.grid_tracks(tok, cols, rows)
            self.assertTrue(0.8 <= cw / ch <= 1.25, "%s cell %.2f" % (name, cw / ch))

    def test_portrait_canvas_gives_a_wide_picture_the_full_width(self):
        for name in ("a4", "3x4", "4x5", "9x16", "1x2"):
            w, h, use = CANVASES[name]
            tok = bs.tokens(w / 2, h / 2, use)
            cols, rows = bl.grid_for(w / 2, h / 2, tok["u"])
            c, r, hw, hh = bl.place_hero(cols, rows, {"image": "p.png", "_img_aspect": 1.6}, tok)
            self.assertEqual((c, hw), (0, cols), name)
            self.assertEqual(r * 2 + hh, rows, name)
            c, r, hw, hh = bl.place_hero(cols, rows, {"image": "p.png", "_img_aspect": 1.2}, tok)
            self.assertLess(hw, cols, name)

    def test_count_ranges(self):
        self.assertEqual(bs.count_range("screen", 1920, 1080), (14, 18))
        self.assertEqual(bs.count_limits("screen", 1920, 1080), (10, 21))
        self.assertEqual(bs.count_range("phone", 540, 960), bs.count_range("screen", 1920, 1080))
        seen = []
        for name in ("1x1", "4x3", "16x9", "21x9"):
            w, h, use = CANVASES[name]
            lo, hi = bs.count_range(use, w / 2, h / 2)
            lo_x, hi_x = bs.count_limits(use, w / 2, h / 2)
            self.assertTrue(lo_x <= lo < hi <= hi_x, name)
            seen.append(lo)
        self.assertEqual(seen, sorted(seen))
        for name, (w, h, use) in CANVASES.items():
            lo_x, hi_x = bs.count_limits(use, w / 2, h / 2)
            self.assertTrue(lo_x <= 12 <= hi_x, name)

    def test_chinese_line_over_eleven_is_rejected(self):
        def errs(label):
            return bs.validate_spec(minimal_spec(tiles=[minimal_spec()["tiles"][0],
                                                        {"id": "a", "kind": "word", "word": "写作", "label": label}]))
        self.assertEqual(errs("一二三四五六七八九十十"), [])
        self.assertTrue(any("一行约" in e for e in errs("一二三四五六七八九十十二")))
        self.assertEqual(errs("全天续航\n一次充满"), [])

    def test_no_break_space_in_names_is_kept(self):
        import tempfile
        name = "iPhone 18 Pro Max"
        self.assertEqual(bs.label_lines("适配 " + name), ["适配 " + name])
        self.assertEqual(bs.cjk_spacing_problems("适配 " + name), [])
        spec = minimal_spec(tiles=[minimal_spec()["tiles"][0],
                                   {"id": "a", "kind": "word", "word": "Pro", "label": "适配 " + name}])
        layout = {"grid": {"cols": 56, "rows": 32}, "cells": {"hero": [14, 8, 28, 16], "a": [0, 0, 14, 8]}}
        page = br.build_html(spec, layout, Path(tempfile.mkdtemp(prefix="bento-nbsp-"))).read_text(encoding="utf-8")
        self.assertIn(name, page)

    def test_cjk_spacing_warns(self):
        self.assertEqual(bs.cjk_spacing_problems("续航36小时"), ["航3", "6小"])
        self.assertEqual(bs.cjk_spacing_problems("支持USB"), ["持U"])
        self.assertEqual(bs.cjk_spacing_problems("续航 36 小时，支持 USB"), [])

    def test_photo_label_goes_where_the_photo_is_dark(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-photo-"))
        im = Image.new("RGB", (400, 300), "#f2f2f2")
        ImageDraw.Draw(im).rectangle([0, 0, 400, 150], fill="#101010")
        im.save(tmp / "dark-top.png")
        im.transpose(Image.FLIP_TOP_BOTTOM).save(tmp / "dark-bottom.png")
        tok = bs.tokens(1920, 1080, "screen")
        box = {"w": 400.0, "h": 300.0}
        self.assertEqual(br.photo_label_pos(tmp / "dark-top.png", box, None, "电影感调色", tok), "top")
        self.assertEqual(br.photo_label_pos(tmp / "dark-bottom.png", box, None, "电影感调色", tok), "bottom")
        self.assertGreater(br.photo_label_contrast(tmp / "dark-top.png", box, None, "电影感调色", "top", tok), 4.5)
        self.assertEqual(br._focus_fractions("50% 100%"), (0.5, 1.0))
        self.assertEqual(br._focus_fractions("bottom"), (0.5, 1.0))
        self.assertEqual(br._focus_fractions("right top"), (1.0, 0.0))

    def test_wide_screenshot_in_a_tall_tile_is_shown_whole(self):
        import re
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-ui-"))
        Image.new("RGB", (1600, 900), "#202020").save(tmp / "screen.png")
        spec = minimal_spec(tiles=[minimal_spec()["tiles"][0],
                                   {"id": "s", "kind": "ui", "image": "screen.png", "label": "演示片"}])

        def fit(cell):
            layout = {"grid": {"cols": 56, "rows": 32}, "cells": {"hero": [14, 8, 28, 16], "s": cell}}
            page = br.build_html(spec, layout, tmp / ("out-%d" % cell[2]), base_dir=tmp).read_text(encoding="utf-8")
            tile = page[page.index('id="t-s"'):]
            return re.search(r"fit-(contain|cover)", tile).group(1)
        self.assertEqual(fit([0, 0, 8, 24]), "contain")
        self.assertEqual(fit([0, 0, 24, 10]), "cover")

    def test_wide_screenshot_gets_a_wide_tile(self):
        t = {"id": "s", "kind": "ui", "image": "s.png", "_img_aspect": 16 / 9, "label": "演示片"}
        pref, _ = bl.preferred_aspect(t)
        self.assertGreater(pref, 1.4)
        self.assertEqual(bl.preferred_aspect(dict(t, _img_aspect=0.46))[0], 1.0)


@unittest.skipUnless(CHROME_OK and MATRIX.exists(), "Chrome or matrix fixture missing")
class MatrixTests(unittest.TestCase):
    """The same twelve tiles on all nine canvases: lays out, renders and passes every check."""

    def test_nine_canvases_pass(self):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-matrix-"))
        for name, (w, h, use) in CANVASES.items():
            with self.subTest(canvas=name):
                spec_path = MATRIX / (name + ".json")
                spec = bs.load_spec(spec_path)
                self.assertEqual((spec["canvas"]["width"], spec["canvas"]["height"], spec["canvas"]["use"]), (w, h, use))
                self.assertEqual(bs.validate_spec(spec, MATRIX), [])
                cands = bl.candidates(spec, n=1, base_dir=MATRIX)
                self.assertTrue(cands, name)
                lay = tmp / (name + ".layout.json")
                lay.write_text(json.dumps(cands[0]), encoding="utf-8")
                r = br.render(spec_path, lay, tmp / name)
                self.assertTrue(r["qa_pass"], r["qa_summary"])


# ---------------------------------------------------------------- research mode, source line, cut-out (round 8)

def research_spec(**over):
    spec = minimal_spec(mode="research", tiles=[
        {"id": "hero", "kind": "hero", "word": "Skills", "weight": 3},
        {"id": "t", "kind": "stat", "value": "1.23", "uncertainty": "0.04", "unit": "s", "label": "单次渲染",
         "n": 12, "condition": "室温", "facts": [{"text": "x", "source": "y"}]},
    ])
    spec.update(over)
    return spec


class ResearchSpecTests(unittest.TestCase):
    def test_line_chart_has_one_line_one_dot_one_value(self):
        import bento_chart
        out = bento_chart.svg(series=[3, 5, 4, 8, 6], highlight=3, kind="line", width=300, height=160, u=20)
        self.assertEqual((out.count("<polyline"), out.count("<circle"), out.count("<text")), (1, 1, 1))
        for absent in ("<line", "<path", "<rect", "tick", "grid"):
            self.assertNotIn(absent, out)
        self.assertIn('stroke-width="2.40"', out)             # 0.12u
        self.assertIn(">8</text>", out)
        self.assertIn('fill="#000000"/>', out)                # no accent: the dot is ink
        self.assertIn('fill="#ff3b30"/>', bento_chart.svg([1, 2], 1, "line", 100, 80, 10, "#000000", "#ff3b30"))
        with self.assertRaises(ValueError):
            bento_chart.svg([1, 2], highlight=5)

    def test_bar_chart_marks_one_bar(self):
        import bento_chart
        out = bento_chart.svg([8, 7, 6.5], highlight=0, kind="bar", width=200, height=120, u=10,
                              highlight_label="8 分")
        self.assertEqual(out.count("<rect"), 3)
        self.assertEqual(out.count('fill="#000000"/>'), 1)      # the highlighted bar
        self.assertEqual(out.count('fill="#c7c7c7"/>'), 2)
        self.assertIn(">8 分</text>", out)
        self.assertNotIn("<line", out)

    def test_research_numbers_need_uncertainty(self):
        def errs(**tile):
            base = {"id": "t", "kind": "stat", "value": "1.23", "label": "渲染", "facts": [{"text": "x", "source": "y"}]}
            return bs.validate_spec(minimal_spec(mode="research", tiles=[minimal_spec()["tiles"][0], dict(base, **tile)]))
        self.assertTrue(any("uncertainty" in e for e in errs()))
        self.assertEqual(errs(uncertainty="0.04"), [])
        self.assertEqual(errs(exact=True), [])
        self.assertEqual(errs(n=1), [])
        self.assertTrue(any("二选一" in e for e in errs(uncertainty="0.04", exact=True)))
        self.assertTrue(any("数值" in e for e in errs(uncertainty="很小")))
        self.assertTrue(any("太长" in e for e in errs(exact=True, condition="室温二十五度，湿度百分之四十")))
        self.assertTrue(any("一行" in e for e in errs(exact=True, label="渲染\n耗时", n=3)))
        product = bs.validate_spec(minimal_spec(tiles=[minimal_spec()["tiles"][0],
                                                       {"id": "t", "kind": "stat", "value": "1", "label": "渲染",
                                                        "uncertainty": "0.1", "unverified": True}]))
        self.assertTrue(any("research" in e for e in product))

    def test_uncertainty_and_meta_line_are_drawn(self):
        import re
        import tempfile
        layout = {"grid": {"cols": 56, "rows": 32}, "cells": {"hero": [17, 11, 22, 10], "t": [0, 0, 16, 11]}}
        page = br.build_html(research_spec(), layout, Path(tempfile.mkdtemp(prefix="bento-research-"))
                             ).read_text(encoding="utf-8")
        num = re.search(r'<div class="num[^"]*"[^>]*>(.*?)</div>', page).group(1)
        self.assertEqual(re.sub(r"<[^>]+>", "", num), "1.23 ± 0.04 s")
        self.assertIn('<span class="pm">', num)
        self.assertIn("n = 12，室温", page)
        self.assertEqual(bs.cjk_spacing_problems("n = 12，室温"), [])
        self.assertEqual(bs.display_label({"label": "Render", "n": 5}, "en"), "Render\nn = 5")

    def test_source_line_only_when_asked(self):
        import tempfile
        layout = {"grid": {"cols": 56, "rows": 32}, "cells": {"hero": [17, 11, 22, 10], "t": [0, 0, 16, 11]}}
        tmp = Path(tempfile.mkdtemp(prefix="bento-source-"))
        off = br.build_html(research_spec(), layout, tmp / "off").read_text(encoding="utf-8")
        on = br.build_html(research_spec(source_line="数据：本机实测"), layout, tmp / "on").read_text(encoding="utf-8")
        self.assertNotIn('class="source"', off)
        self.assertIn('class="source"', on)
        tok = bs.tokens_for(research_spec(source_line="数据：本机实测"))
        self.assertAlmostEqual(tok["margin_bottom"] / tok["u"], 2 * 0.68 + 0.75, places=2)
        self.assertEqual(bs.tokens_for(research_spec())["margin_bottom"], bs.tokens_for(research_spec())["margin"])


@unittest.skipUnless(CHROME_OK and (SPECS / "research-3x4.layout.json").exists(), "Chrome or research fixture missing")
class ResearchRenderTests(unittest.TestCase):
    def test_research_example_passes(self):
        import tempfile
        r = br.render(SPECS / "research-3x4.json", SPECS / "research-3x4.layout.json",
                      Path(tempfile.mkdtemp(prefix="bento-research-")))
        self.assertTrue(r["qa_pass"], r["qa_summary"])

    def test_source_line_is_small_readable_and_inside(self):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="bento-research-src-"))
        spec = bs.load_spec(SPECS / "research-3x4.json")
        spec["source_line"] = "数据：调色原型 0.4.1 实测；渲染耗时为本库 0.3.0 本机实测"
        for t in spec["tiles"]:
            if t.get("image"):
                t["image"] = str((SPECS / t["image"]).resolve())
        spec_path = tmp / "research.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        r = br.render(spec_path, SPECS / "research-3x4.layout.json", tmp / "out")
        self.assertTrue(r["qa_pass"], r["qa_summary"])
        dom = json.loads(Path(r["dom"]).read_text(encoding="utf-8"))
        src = next(t for t in dom["texts"] if t["role"] == "source")
        tok = bs.tokens_for(spec)
        self.assertAlmostEqual(src["font_size"] / tok["u"], 0.75, places=2)
        bottom = max(t["rect"][1] + t["rect"][3] for t in dom["tiles"])
        self.assertGreaterEqual(src["ink"][1], bottom + 0.5 * tok["margin"])
        self.assertLessEqual(src["ink"][1] + src["ink"][3], tok["css_h"])


SWIFT = Path("/usr/bin/swift")


def _macos_major() -> int:
    import platform
    try:
        return int(platform.mac_ver()[0].split(".")[0])
    except ValueError:
        return 0


@unittest.skipUnless(SWIFT.exists() and _macos_major() >= 14 and (FIXTURES / "images" / "coffee.jpg").exists(),
                     "needs macOS 14+, swift and the coffee fixture")
class CutoutTests(unittest.TestCase):
    def test_coffee_cut_out(self):
        import subprocess
        import tempfile
        out = Path(tempfile.mkdtemp(prefix="bento-cutout-")) / "coffee-cut.png"
        subprocess.run([str(SWIFT), str(HERE / "cutout.swift"), str(FIXTURES / "images" / "coffee.jpg"), str(out)],
                       check=True, capture_output=True, timeout=300)
        im = Image.open(out)
        self.assertEqual(im.mode, "RGBA")
        share = float((np.asarray(im)[..., 3] > 127).mean())
        self.assertTrue(0.10 <= share <= 0.80, share)


# ---------------------------------------------------------------- runner

GROUPS = {
    "measure": [MeasureSynthetic, MeasureApple],
    "spec": [SpecTests],
    "render": [RenderCliTests],
    "chrome": [ChromeTests, RenderTests],
    "layout": [LayoutTests, LayoutRegression],
    "plan": [PlanTests],
    "qa": [QaTests],
    "align": [AlignIphone18Pro],
    "ratio": [RatioTests],
    "matrix": [MatrixTests],
    "research": [ResearchSpecTests, ResearchRenderTests, CutoutTests],
}


def run_tests(group="all", verbosity=2):
    suite = unittest.TestSuite()
    names = GROUPS if group == "all" else {group: GROUPS[group]}
    for classes in names.values():
        for cls in classes:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run_tests(sys.argv[1] if len(sys.argv) > 1 else "all"))
