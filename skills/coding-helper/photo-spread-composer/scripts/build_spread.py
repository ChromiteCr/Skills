#!/usr/bin/env python3
"""从 plan.json 解出版面并产出单文件 HTML。

    python3 build_spread.py plan.json [out.html]
    python3 build_spread.py --selftest

这个脚本负责的是**唯一的硬约束**：一带之内所有 item 等高、两端顶到版心。
带高由下面这个方程唯一确定，所以 plan.json 里不需要、也不应该出现任何位置或尺寸：

    h · [ Σ aᵢ + Σ 1/Sⱼ ] = W − (n−1)·g − Σ wₖ + Σ (mⱼ−1)·g / Sⱼ

      W    版心宽 = 页宽 − 2×页边距
      g    天沟
      aᵢ   photo 的长宽比（宽/高）
      Sⱼ   stack 内各图 1/长宽比 之和；mⱼ 为该 stack 的图数
      wₖ   text 栏的固定宽度

解出来之后：
  - 按显示尺寸算每张需要多少像素（mm ÷ 25.4 × dpi），**不足就报错，不静默放大**
  - 缩到实际需要的尺寸再内联成 base64，所以成品不会因为塞了原图而爆掉
  - 输出的 HTML 用 flex-grow 表达比例，与解出的宽度严格一致，且缩放页面不失真

读图走同目录的 image_io.py（与摄影类 skill 共用，依赖 Pillow）：
  - 先按 EXIF 方向转正，再取长宽比、查分辨率、缩放。手机竖拍不会横躺，也不会按横图算带高
  - 每张内联照片保留自己的 ICC 配置文件：iPhone 的 Display P3 照片仍标 Display P3，
    浏览器显示和打印成 PDF 都按它解释，不会发灰。没有配置文件的照片标成 sRGB；
    灰度和 CMYK 配置文件的照片转成 sRGB
  - 透明区域铺纸色，不会变黑
  - 找不到的照片、读不了的 HEIC 直接报文件名和办法，不抛 traceback

plan.json 的结构见 SKILL.md 的「协议」一节。写错的键会报错，不会被静默忽略。
"""

import argparse
import base64
import contextlib
import io
import json
import math
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import image_io  # noqa: E402  (shared copy; also checks that Pillow is installed)
except ModuleNotFoundError as exc:  # pragma: no cover - only when the file was not copied along
    if exc.name == "image_io":
        sys.exit("缺 image_io.py：它和本脚本放在同一个 scripts/ 目录，复制时要一起带上")
    raise

from PIL import Image, ImageCms  # noqa: E402

MM_PER_INCH = 25.4
JPEG_QUALITY = 88
PAPER_RGB = (0xFD, 0xFD, 0xFB)  # 模板里的 --paper；透明区域铺这个颜色
BANDS_MARKER = "<!--BANDS-->"   # 模板正文里的照片占位，必须正好出现一次
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "spread.html"

PLAN_KEYS = {"title", "accent", "header", "page", "bands"}
PAGE_KEYS = {"width_mm", "height_mm", "margin_mm", "gutter_mm", "dpi"}
HEADER_KEYS = {"folio", "masthead", "section", "headline"}
BAND_KEYS = {"caption", "credit", "items"}
ITEM_KEYS = {
    "photo": {"type", "src"},
    "stack": {"type", "src"},
    "text": {"type", "width_mm", "title", "byline", "body"},
}
ACCENT_RE = re.compile(r"^(#[0-9A-Fa-f]{3}|#[0-9A-Fa-f]{6}|[A-Za-z]{3,20})$")


def die(msg):
    sys.exit(f"错误：{msg}")


def check_keys(obj, allowed, where):
    if not isinstance(obj, dict):
        die(f"{where} 应该是一个对象（{{…}}）")
    unknown = sorted(set(obj) - allowed)
    if unknown:
        die(f"{where} 里有不认识的键 {'、'.join(unknown)}；可用的键：{'、'.join(sorted(allowed))}")


def number(obj, key, default, where, minimum=0.0, strict=False):
    value = obj.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        die(f"{where}.{key} 应该是数字，现在是 {value!r}")
    if value < minimum or (strict and value == minimum):
        die(f"{where}.{key} 应该{'大于' if strict else '不小于'} {minimum:g}，现在是 {value!r}")
    return float(value)


# ---------------------------------------------------------------- photos


def explain(path: Path, exc: Exception) -> str:
    if path.suffix.lower() in image_io.HEIF_EXTS or "HEIC/HEIF" in str(exc):
        return (f"{path.name} 是 HEIC，本机读不了（没有装 pillow-heif）。先转成 JPEG，macOS 自带、保留 EXIF："
                f'sips -s format jpeg "{path}" --out "{path.with_suffix(".jpg")}"，再把 plan 里的 src 改成 .jpg')
    return f"{path.name} 读不了：{exc}"


_SIZES = {}


def photo_path(base: Path, src, where) -> Path:
    if not isinstance(src, str) or not src.strip():
        die(f"{where} 的 src 应该是照片路径（字符串）")
    path = (base / src).expanduser()
    if not path.is_file():
        die(f"找不到照片 {src}（plan.json 里的路径按它所在的目录解析，查的是 {path.resolve()}）")
    return path


def oriented_px(path: Path) -> tuple:
    """按 EXIF 方向转正后的 (宽, 高)，只读文件头。"""
    key = str(path.resolve())
    if key not in _SIZES:
        try:
            w, h = image_io.oriented_size(path)
        except image_io.ImageIOError as exc:
            die(explain(path, exc))
        if not w or not h:
            die(f"{path.name} 的宽或高为 0")
        _SIZES[key] = (w, h)
    return _SIZES[key]


def aspect(path: Path) -> float:
    w, h = oriented_px(path)
    return w / h


def icc_space(icc):
    """'RGB'、'GRAY'、'CMYK'，没有配置文件时 None，读不出时 'UNREADABLE'。"""
    if not icc:
        return None
    try:
        return ImageCms.ImageCmsProfile(io.BytesIO(icc)).profile.xcolor_space.strip().upper()
    except Exception:
        return "UNREADABLE"


def display_rgb(img, meta):
    """(RGB 图, 要嵌入的 ICC, 色彩说明)。RGB 配置文件原样保留；灰度、CMYK 转 sRGB；未标注的标成 sRGB。"""
    icc = meta["icc_profile"]
    space = icc_space(icc)
    if space in ("GRAY", "CMYK") or img.mode == "CMYK":
        source = icc if space in ("GRAY", "CMYK") else None
        if space == "GRAY" and img.mode != "L":
            img = image_io.to_rgb(img, PAPER_RGB).convert("L")  # 先把透明铺成纸色
        try:
            out = image_io.to_srgb(img, source, background=PAPER_RGB)
        except image_io.ImageIOError as exc:
            die(f"{meta['name']}：{exc}")
        return out, image_io.srgb_icc_bytes(), f"{meta['color_space']} → 转成 sRGB"
    if space == "RGB":
        return image_io.to_rgb(img, PAPER_RGB), icc, f"{meta['color_space']}（保留原配置文件）"
    if space == "UNREADABLE":
        return image_io.to_rgb(img, PAPER_RGB), image_io.srgb_icc_bytes(), "配置文件读不出 → 按 sRGB 标注"
    return image_io.to_rgb(img, PAPER_RGB), image_io.srgb_icc_bytes(), "未标注 → 按 sRGB 标注"


def solve_band(items, W, g, base: Path, bi: int):
    """解带高，返回 (h_mm, [每个 item 的 width_mm])。"""
    n = len(items)
    if n == 0:
        die(f"第 {bi} 带是空的")

    coef = 0.0          # h 的系数
    const = W - (n - 1) * g   # 右边的常数项

    meta = []
    for ii, it in enumerate(items, 1):
        where = f"第 {bi} 带第 {ii} 个 item"
        if not isinstance(it, dict):
            die(f"{where} 应该是一个对象（{{…}}）")
        t = it.get("type", "photo")
        if t not in ITEM_KEYS:
            die(f"{where} 的 type {t!r} 不认识；可用：photo、stack、text")
        check_keys(it, ITEM_KEYS[t], where)
        if t == "photo":
            a = aspect(photo_path(base, it.get("src"), where))
            coef += a
            meta.append(("photo", a, None))
        elif t == "stack":
            srcs = it.get("src")
            if not isinstance(srcs, list) or len(srcs) < 2:
                die(f"{where}：stack 至少要两张，否则直接用 photo")
            S = sum(1.0 / aspect(photo_path(base, s, where)) for s in srcs)
            m = len(srcs)
            coef += 1.0 / S
            const += (m - 1) * g / S
            meta.append(("stack", S, m))
        else:
            w = number(it, "width_mm", 0, where, strict=True)
            const -= w
            meta.append(("text", w, None))

    if coef <= 0:
        die(f"第 {bi} 带里至少要有一个 photo 或 stack，不能全是 text 栏")
    h = const / coef
    if h <= 0:
        die(f"第 {bi} 带的带高解出来是 {h:.1f}mm ——文字栏太宽或天沟太大，版心放不下")

    widths = []
    for kind, val, m in meta:
        if kind == "photo":
            widths.append(val * h)
        elif kind == "stack":
            widths.append((h - (m - 1) * g) / val)
        else:
            widths.append(val)
    return h, widths


def encode(path: Path, target_mm: float, dpi: int, problems: list, colours: dict):
    """转正、按显示宽度缩放并编码。分辨率不足记进 problems。"""
    need_px = target_mm / MM_PER_INCH * dpi
    src_w, src_h = oriented_px(path)
    if src_w < need_px:
        problems.append((path.name, src_w, need_px, target_mm))
        return None
    try:
        img, meta = image_io.open_image(path)  # 已按 EXIF 方向转正，ICC 随图带着
    except image_io.ImageIOError as exc:
        die(explain(path, exc))
    rgb, icc, note = display_rgb(img, meta)
    size = (max(1, round(need_px)), max(1, round(src_h * need_px / src_w)))
    rgb = rgb.resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    # 重新编码时不带原 EXIF：像素已经转正，再带 Orientation 标签浏览器会再转一次
    rgb.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, icc_profile=icc)
    colours.setdefault(note, set()).add(path.name)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def fill_template(tpl: str, values: dict, bands_html: str) -> str:
    """只替换正文里那一处照片占位；{{KEY}} 一遍替换完，填进去的内容不会再被当成占位。"""
    n = tpl.count(BANDS_MARKER)
    if n != 1:
        die(f"模板里的照片占位 {BANDS_MARKER} 应该正好出现一次，现在是 {n} 次"
            "（多出来的一处会把整版照片再注入一遍，成品体积翻倍）")

    def sub(part):
        return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)), part)

    before, after = tpl.split(BANDS_MARKER)
    return sub(before) + bands_html + sub(after)


def load_plan(plan_path: Path) -> dict:
    if not plan_path.is_file():
        die(f"找不到 {plan_path}")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"{plan_path.name} 不是合法的 JSON：第 {exc.lineno} 行第 {exc.colno} 列，{exc.msg}")
    except UnicodeDecodeError:
        die(f"{plan_path.name} 不是 UTF-8 编码的文本")
    check_keys(plan, PLAN_KEYS, "plan.json")
    return plan


def build(plan_path: Path, out_arg) -> int:
    plan = load_plan(plan_path)
    base = plan_path.parent

    pg = plan.get("page", {})
    check_keys(pg, PAGE_KEYS, "page")
    PW = number(pg, "width_mm", 297, "page", strict=True)
    PH = number(pg, "height_mm", 420, "page", strict=True)
    M = number(pg, "margin_mm", 18, "page")
    g = number(pg, "gutter_mm", 3, "page")
    dpi_value = number(pg, "dpi", 300, "page", strict=True)
    if not float(dpi_value).is_integer():
        die(f"page.dpi 应该是整数，现在是 {pg.get('dpi')!r}")
    dpi = int(dpi_value)
    W = PW - 2 * M
    if W <= 0:
        die("页边距比页宽还大")

    head = plan.get("header", {})
    check_keys(head, HEADER_KEYS, "header")
    accent = plan.get("accent", "#b3121d")
    if not isinstance(accent, str) or not ACCENT_RE.match(accent):
        die(f"accent 应该是 #rgb、#rrggbb 或颜色名，现在是 {accent!r}")

    bands = plan.get("bands") or []
    if not isinstance(bands, list) or not bands:
        die("plan 里没有 bands（应该是一个非空列表）")

    problems, html_bands, total_h, colours, inputs = [], [], 0.0, {}, [plan_path]

    for bi, band in enumerate(bands, 1):
        check_keys(band, BAND_KEYS, f"第 {bi} 带")
        items = band.get("items") or []
        if not isinstance(items, list):
            die(f"第 {bi} 带的 items 应该是列表")
        h, widths = solve_band(items, W, g, base, bi)
        total_h += h
        parts = []
        for ii, (it, w) in enumerate(zip(items, widths), 1):
            where = f"第 {bi} 带第 {ii} 个 item"
            t = it.get("type", "photo")
            grow = f"{w:.4f}"
            if t == "photo":
                p = photo_path(base, it["src"], where)
                inputs.append(p)
                a = aspect(p)
                b64 = encode(p, w, dpi, problems, colours)
                img = ("" if b64 is None else
                       f'<img src="data:image/jpeg;base64,{b64}" alt="">')
                parts.append(
                    f'<figure class="ph" style="flex:{grow} 1 0;aspect-ratio:{a:.5f}">'
                    f'{img}</figure>')
            elif t == "stack":
                subs = []
                for s in it["src"]:
                    p = photo_path(base, s, where)
                    inputs.append(p)
                    a = aspect(p)
                    b64 = encode(p, w, dpi, problems, colours)
                    img = ("" if b64 is None else
                           f'<img src="data:image/jpeg;base64,{b64}" alt="">')
                    # 子图不写 aspect-ratio：它的高度由纵向 flex 按 1/长宽比 分配，
                    # 宽度是 stack 的宽度，两者之比正好等于原长宽比（见 solve_band 推导）。
                    # 再写 aspect-ratio 会和 flex 争夺主轴尺寸。
                    subs.append(
                        f'<figure class="ph" style="flex:{1/a:.5f} 1 0">{img}</figure>')
                # stack 必须有确定高度，否则内部 flex-basis:0 的子项会塌成 0。
                # 它的长宽比由已解出的 w 与 h 直接给出，是导出量不是手写值。
                parts.append(
                    f'<div class="stack" style="flex:{grow} 1 0;'
                    f'aspect-ratio:{w/h:.5f}">' + "".join(subs) + "</div>")
            else:
                title = esc(it.get("title", ""))
                byline = esc(it.get("byline", ""))
                body = esc(it.get("body", ""))
                parts.append(
                    f'<div class="txt" style="flex:{grow} 1 0">'
                    f'{f"<h3>{title}</h3>" if title else ""}'
                    f'{f"<p class=by>{byline}</p>" if byline else ""}'
                    f'{f"<p>{body}</p>" if body else ""}</div>')

        cap = esc(band.get("caption", ""))
        cred = esc(band.get("credit", ""))
        capline = ""
        if cap or cred:
            capline = (f'<p class="cap">{cap}'
                       f'{" " if cap and cred else ""}'
                       f'{f"<span class=cred>{cred}</span>" if cred else ""}</p>')
        html_bands.append(f'<section class="band" data-band="{bi}">'
                          + "".join(parts) + "</section>" + capline)

    if problems:
        print("分辨率不足，没有生成文件。这几张按解出的尺寸排会糊：\n", file=sys.stderr)
        for name, have, need, mm in problems:
            print(f"  {name}: 有 {have}px，排到 {mm:.1f}mm 需要 {need:.0f}px，"
                  f"差 {need-have:.0f}px", file=sys.stderr)
        print("\n三条出路：把它排小一点（换到 item 更多的带）、"
              "换一张、或降低 page.dpi（屏幕浏览用 150 就够）。", file=sys.stderr)
        return 1

    out = Path(out_arg).expanduser() if out_arg else plan_path.with_suffix(".html")
    try:
        image_io.check_output_path(out, inputs)
    except image_io.ImageIOError as exc:
        die(str(exc))
    if not out.parent.exists():
        die(f"输出目录不存在：{out.parent}")

    if not TEMPLATE.is_file():
        die(f"找不到模板 {TEMPLATE}")
    values = {
        "PAGE_W": f"{PW:g}", "PAGE_H": f"{PH:g}", "MARGIN": f"{M:g}", "GUTTER": f"{g:g}",
        "ACCENT": accent,
        "TITLE": esc(plan.get("title", "照片版面")),
        "FOLIO": esc(head.get("folio", "")),
        "MASTHEAD": esc(head.get("masthead", "")),
        "SECTION": esc(head.get("section", "")),
        "HEADLINE": esc(head.get("headline", "")),
    }
    html = fill_template(TEMPLATE.read_text(encoding="utf-8"), values, "\n".join(html_bands))
    out.write_text(html, encoding="utf-8")

    # 署名是硬规矩，不能只靠自觉。缺了就出声——但不拦住生成，
    # 因为排版过程中先看效果再补署名是正常工作流。
    missing = [i for i, b in enumerate(bands, 1) if not str(b.get("credit", "")).strip()]

    kb = out.stat().st_size / 1024
    print(f"已生成: {out}  ({kb:.0f} KB)")
    if missing:
        print(f"⚠ 第 {'、'.join(map(str, missing))} 带没有署名。"
              f"署名是事实不是装饰，交付前必须补上，查不到作者的照片不上版。")
    print(f"版心 {W:g}×{PH-2*M:g}mm · {len(bands)} 带 · 内容总高 {total_h:.1f}mm"
          f"（不含图注与带间距）")
    if total_h > PH - 2 * M:
        print(f"注意：内容比版心高 {total_h-(PH-2*M):.1f}mm，会溢出到第二页。"
              f"减一带、或把某带的 item 加多（item 越多带越矮）。")
    print("色彩：" + "；".join(f"{note} × {len(names)}" for note, names in sorted(colours.items())))
    print("导 PDF：浏览器打开后 Cmd+P，纸张选自定"
          f" {PW:g}×{PH:g}mm，边距选无，勾选背景图形。")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_spread.py",
        description="从 plan.json 解出带状版面、查分辨率、把照片转正缩放后内联，产出单文件 HTML。",
    )
    parser.add_argument("plan", nargs="?", help="plan.json 的路径")
    parser.add_argument("out", nargs="?", help="输出的 HTML，默认与 plan.json 同名、扩展名 .html")
    parser.add_argument("--selftest", action="store_true", help="跑内置的回归检查后退出")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.plan:
        parser.error("需要 plan.json 的路径")
    _SIZES.clear()
    return build(Path(args.plan).expanduser(), args.out)


# ---------------------------------------------------------------- self-test


class _Parts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.comments, self.imgs = [], 0

    def handle_comment(self, data):
        self.comments.append(data)

    def handle_starttag(self, tag, attrs):
        self.imgs += tag == "img"


def _run(argv) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            if isinstance(exc.code, str):
                err.write(exc.code)
                code = 1
            else:
                code = exc.code or 0
    return code, out.getvalue(), err.getvalue()


def _decode_all(html: str) -> list:
    out = []
    for b64 in re.findall(r"data:image/jpeg;base64,([A-Za-z0-9+/=]+)", html):
        im = Image.open(io.BytesIO(base64.b64decode(b64)))
        im.load()
        out.append(im)
    return out


def _close(a, b, tol=6) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def selftest() -> int:
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # 手机竖拍：存 1200×800、Orientation=6，显示为 800×1200。存储时左上角的红块，转正后在右上角
        phone = Image.new("RGB", (1200, 800), (40, 120, 200))
        phone.paste((255, 0, 0), (0, 0, 300, 200))
        exif = Image.Exif()
        exif[0x0112] = 6
        phone.save(d / "phone.jpg", exif=exif.tobytes(), quality=95)
        Image.new("RGB", (1500, 1000), (200, 200, 60)).save(d / "wide.jpg", quality=95)
        Image.new("RGB", (900, 1200), (60, 60, 60)).save(d / "tall.jpg", quality=95)
        rgba = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
        rgba.paste((220, 20, 20, 255), (400, 250, 800, 550))
        rgba.save(d / "alpha.png")
        p3_path = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
        has_p3 = p3_path.exists()
        if has_p3:
            Image.new("RGB", (1200, 900), (234, 51, 35)).save(d / "p3.jpg", icc_profile=p3_path.read_bytes(), quality=95)
        (d / "iphone.heic").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")

        def write_plan(name, bands, page=None, **extra):
            plan = {"page": page or {"width_mm": 297, "height_mm": 420, "margin_mm": 18, "gutter_mm": 3, "dpi": 72},
                    "bands": bands}
            plan.update(extra)
            (d / name).write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            return str(d / name)

        band1 = {"caption": "横 + 手机竖拍", "credit": "摄影：测试",
                 "items": [{"type": "photo", "src": "wide.jpg"}, {"type": "photo", "src": "phone.jpg"}]}
        band2 = {"caption": "透明 PNG 与 stack", "credit": "摄影：测试",
                 "items": [{"type": "photo", "src": "p3.jpg" if has_p3 else "wide.jpg"},
                           {"type": "stack", "src": ["alpha.png", "wide.jpg"]},
                           {"type": "text", "width_mm": 40, "title": "说明", "body": "文字栏"}]}
        plan = write_plan("plan.json", [band1, band2])
        code, out, err = _run([plan, str(d / "spread.html")])
        check("normal build exits 0", code == 0, err.strip())
        html = (d / "spread.html").read_text(encoding="utf-8") if code == 0 else ""
        images = _decode_all(html)
        parts = _Parts()
        parts.feed(html)
        check("each photo inlined exactly once (5 slots, 5 images)", len(images) == 5 and parts.imgs == 5, f"{len(images)} data URIs, {parts.imgs} <img>")
        check("no photo data inside HTML comments", not any("base64" in c for c in parts.comments))
        check("placeholder marker consumed", BANDS_MARKER not in html)
        ratios = re.findall(r"aspect-ratio:([0-9.]+)", html)
        check("portrait phone shot gets aspect-ratio 0.66667", len(ratios) > 1 and ratios[1] == "0.66667", str(ratios[:2]))
        if len(images) == 5:
            ph = images[1].convert("RGB")
            w, h = ph.size
            check("phone shot inlined upright (portrait pixels)", h > w, str(ph.size))
            check("phone shot red corner moved to top-right", _close(ph.getpixel((w - 3, 2)), (255, 0, 0), 40)
                  and not _close(ph.getpixel((2, 2)), (255, 0, 0), 60), f"TL {ph.getpixel((2, 2))} TR {ph.getpixel((w - 3, 2))}")
            check("no Orientation tag left in the inlined JPEG", images[1].getexif().get(0x0112) in (None, 1))
            names = [image_io.profile_name(im.info.get("icc_profile")) for im in images]
            check("untagged photo is tagged sRGB", "sRGB" in names[0], names[0])
            if has_p3:
                p3 = images[2].convert("RGB")
                check("Display P3 photo keeps its profile", "P3" in names[2], names[2])
                check("Display P3 pixels not reinterpreted", _close(p3.getpixel((p3.width // 2, p3.height // 2)), (234, 51, 35)),
                      str(p3.getpixel((p3.width // 2, p3.height // 2))))
            al = images[3].convert("RGB")
            check("transparent area becomes paper colour, not black", _close(al.getpixel((1, 1)), PAPER_RGB), str(al.getpixel((1, 1))))
            check("opaque part of the PNG kept", _close(al.getpixel((al.width // 2, al.height // 2)), (220, 20, 20), 12))
        check("colour report printed", "色彩：" in out and ("Display P3（保留原配置文件）" in out or not has_p3), out[-300:])

        plan = write_plan("missing.json", [{"caption": "x", "credit": "y", "items": [{"type": "photo", "src": "nope.jpg"}, {"type": "photo", "src": "wide.jpg"}]}])
        code, out, err = _run([plan])
        check("missing photo: clear message, no traceback", code == 1 and "nope.jpg" in err and "Traceback" not in err, err.strip())

        if not image_io.HEIF_SUPPORTED:
            plan = write_plan("heic.json", [{"caption": "x", "credit": "y", "items": [{"type": "photo", "src": "iphone.heic"}, {"type": "photo", "src": "wide.jpg"}]}])
            code, out, err = _run([plan])
            check("HEIC: sips hint instead of a traceback", code == 1 and "sips -s format jpeg" in err and "Traceback" not in err, err.strip())

        plan = write_plan("lowres.json", [band1], page={"dpi": 600})
        code, out, err = _run([plan, str(d / "lowres.html")])
        check("under-resolution stops the build and writes nothing", code == 1 and "分辨率不足" in err and not (d / "lowres.html").exists(), err.strip()[:120])

        plan = write_plan("typo.json", [band1], page={"gutter": 3, "dpi": 72})
        code, out, err = _run([plan])
        check("unknown key is an error, not ignored", code == 1 and "gutter" in err, err.strip())

        (d / "broken.json").write_text('{"bands": [', encoding="utf-8")
        code, out, err = _run([str(d / "broken.json")])
        check("malformed JSON: clear message", code == 1 and "JSON" in err and "Traceback" not in err, err.strip())

        plan = write_plan("css.json", [band1], accent="red; } body { display:none")
        code, out, err = _run([plan])
        check("accent is validated before it reaches the CSS", code == 1 and "accent" in err, err.strip())

        plan = write_plan("self.json", [band1])
        code, out, err = _run([plan, str(d / "wide.jpg")])
        check("refuses to write over an input photo", code == 1 and "input" in err, err.strip())

        try:
            fill_template("<!-- 注释里写了 <!--BANDS--> -->\n<body><!--BANDS--></body>", {}, "X")
            check("template with the marker twice is refused", False)
        except SystemExit as exc:
            check("template with the marker twice is refused", "2 次" in str(exc), str(exc))
        filled = fill_template("<title>{{TITLE}}</title><!--BANDS--><p>{{FOLIO}}</p>", {"TITLE": "{{FOLIO}}", "FOLIO": "12"}, "B")
        check("placeholders are filled in one pass", filled == "<title>{{FOLIO}}</title>B<p>12</p>", filled)
        check("shipped template has the marker exactly once", TEMPLATE.read_text(encoding="utf-8").count(BANDS_MARKER) == 1)

        code, out, err = _run(["--help"])
        check("--help prints usage and exits 0", code == 0 and "usage" in out.lower(), str(code))

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
