#!/usr/bin/env python3
"""从 plan.json 解出版面并产出单文件 HTML。

    python3 build_spread.py plan.json [out.html]

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

plan.json 的结构见 SKILL.md 的「协议」一节。
"""

import base64
import io
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("缺 Pillow。装：pip3 install Pillow")

MM_PER_INCH = 25.4
JPEG_QUALITY = 88


def die(msg):
    sys.exit(f"错误：{msg}")


def aspect(path: Path) -> float:
    with Image.open(path) as im:
        w, h = im.size
    if not h:
        die(f"{path.name} 高度为 0")
    return w / h


def px_of(path: Path) -> tuple:
    with Image.open(path) as im:
        return im.size


def solve_band(items, W, g, base: Path):
    """解带高，返回 (h_mm, [每个 item 的 width_mm])。"""
    n = len(items)
    if n == 0:
        die("有一带是空的")

    coef = 0.0          # h 的系数
    const = W - (n - 1) * g   # 右边的常数项

    meta = []
    for it in items:
        t = it.get("type", "photo")
        if t == "photo":
            a = aspect(base / it["src"])
            coef += a
            meta.append(("photo", a, None))
        elif t == "stack":
            srcs = it["src"]
            if not isinstance(srcs, list) or len(srcs) < 2:
                die("stack 至少要两张，否则直接用 photo")
            S = sum(1.0 / aspect(base / s) for s in srcs)
            m = len(srcs)
            coef += 1.0 / S
            const += (m - 1) * g / S
            meta.append(("stack", S, m))
        elif t == "text":
            w = float(it.get("width_mm", 0))
            if w <= 0:
                die("text 栏必须给 width_mm")
            const -= w
            meta.append(("text", w, None))
        else:
            die(f"不认识的 item type: {t}")

    if coef <= 0:
        die("一带里至少要有一个 photo 或 stack，不能全是 text 栏")
    h = const / coef
    if h <= 0:
        die(f"带高解出来是 {h:.1f}mm ——文字栏太宽或天沟太大，版心放不下")

    widths = []
    for kind, val, m in meta:
        if kind == "photo":
            widths.append(val * h)
        elif kind == "stack":
            widths.append((h - (m - 1) * g) / val)
        else:
            widths.append(val)
    return h, widths


def encode(path: Path, target_mm: float, dpi: int, problems: list):
    """按显示宽度缩放并编码。分辨率不足记进 problems。"""
    need_px = target_mm / MM_PER_INCH * dpi
    src_w, src_h = px_of(path)
    if src_w < need_px:
        problems.append((path.name, src_w, need_px, target_mm))
        return None
    with Image.open(path) as im:
        im = im.convert("RGB")
        scale = need_px / src_w
        size = (max(1, round(src_w * scale)), max(1, round(src_h * scale)))
        im = im.resize(size, Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("用法: python3 build_spread.py plan.json [out.html]")
    plan_path = Path(sys.argv[1])
    if not plan_path.is_file():
        die(f"找不到 {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    base = plan_path.parent

    pg = plan.get("page", {})
    PW = float(pg.get("width_mm", 297))
    PH = float(pg.get("height_mm", 420))
    M = float(pg.get("margin_mm", 18))
    g = float(pg.get("gutter_mm", 3))
    dpi = int(pg.get("dpi", 300))
    W = PW - 2 * M
    if W <= 0:
        die("页边距比页宽还大")

    bands = plan.get("bands") or []
    if not bands:
        die("plan 里没有 bands")

    problems, html_bands, total_h = [], [], 0.0

    for bi, band in enumerate(bands, 1):
        items = band.get("items") or []
        h, widths = solve_band(items, W, g, base)
        total_h += h
        parts = []
        for it, w in zip(items, widths):
            t = it.get("type", "photo")
            grow = f"{w:.4f}"
            if t == "photo":
                p = base / it["src"]
                a = aspect(p)
                b64 = encode(p, w, dpi, problems)
                img = ("" if b64 is None else
                       f'<img src="data:image/jpeg;base64,{b64}" alt="">')
                parts.append(
                    f'<figure class="ph" style="flex:{grow} 1 0;aspect-ratio:{a:.5f}">'
                    f'{img}</figure>')
            elif t == "stack":
                subs = []
                for s in it["src"]:
                    p = base / s
                    a = aspect(p)
                    b64 = encode(p, w, dpi, problems)
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

    head = plan.get("header", {})
    accent = plan.get("accent", "#b3121d")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else plan_path.with_suffix(".html")

    tpl = (Path(__file__).resolve().parent.parent / "templates" / "spread.html")
    if not tpl.is_file():
        die(f"找不到模板 {tpl}")
    html = tpl.read_text(encoding="utf-8")
    html = (html
            .replace("{{PAGE_W}}", f"{PW:g}")
            .replace("{{PAGE_H}}", f"{PH:g}")
            .replace("{{MARGIN}}", f"{M:g}")
            .replace("{{GUTTER}}", f"{g:g}")
            .replace("{{ACCENT}}", accent)
            .replace("{{TITLE}}", esc(plan.get("title", "照片版面")))
            .replace("{{FOLIO}}", esc(head.get("folio", "")))
            .replace("{{MASTHEAD}}", esc(head.get("masthead", "")))
            .replace("{{SECTION}}", esc(head.get("section", "")))
            .replace("{{HEADLINE}}", esc(head.get("headline", "")))
            .replace("<!--BANDS-->", "\n".join(html_bands)))
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
    print("导 PDF：浏览器打开后 Cmd+P，纸张选自定"
          f" {PW:g}×{PH:g}mm，边距选无，勾选背景图形。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
