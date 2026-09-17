#!/usr/bin/env python3
"""把 deck.html 引用的本地图片内联成 data URI，顺带检查分辨率、来源行与隐私元数据。

    python3 inline_images.py deck.html [out.html]
    python3 inline_images.py --selftest

为什么要内联：模板的硬规则是单文件、不引外部资源，离线打开必须一致。
图片留成相对路径，文件一挪就断。

检查与处理：

1. **分辨率**。满版图（`.stage.bleed` 里的图）铺满 1920×1080，半幅图（`.stage.half`）铺满
   960×1080，都用 `object-fit: cover`，所以宽和高都要够，不然会被放大。放大糊掉的图投出来
   比没有图更糟，所以不够就报错。其余位置的图不知道显示尺寸，不查
2. **来源行**。满版与半幅图所在的片必须有非空的 `.credit`，且不能还是 `{{...}}` 占位。
   自己拍的也要写「作者自摄」
3. **元数据**。手机照片的 EXIF 常带 GPS 坐标，原样内联等于把拍摄地点塞进一份要分发的文件。
   JPEG 与 PNG 一律重新编码，元数据随之丢弃；重新编码前先按 EXIF 方向转正
4. **体积**。最长边超过 2560px 的按比例缩小，但不会缩到低于第 1 条的要求

只处理 `<img src="相对路径">`。`data:` 开头的不动；`http(s)://` 开头的报错，
那违反了不引外部资源的规则。有错误时不写出文件。

依赖 Pillow（`pip3 install pillow`）。
"""

import base64
import html
import io
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("缺 Pillow。装：pip3 install pillow")

MAX_EDGE = 2560
NEED = {"bleed": (1920, 1080), "half": (960, 1080)}
REENCODE = {"JPEG": ("image/jpeg", "JPEG"), "PNG": ("image/png", "PNG")}
PASSTHRU = {"GIF": "image/gif", "WEBP": "image/webp"}

SECTION = re.compile(r"<section\b.*?</section>", re.S)
STAGE = re.compile(r'<div\s+class="stage\b([^"]*)"')
IMG = re.compile(r'<img\b[^>]*?\bsrc="([^"]+)"[^>]*>', re.S)
CREDIT = re.compile(r'<div\s+class="credit"[^>]*>(.*?)</div>', re.S)
TAG = re.compile(r"<[^>]+>")
COMMENT = re.compile(r"<!--.*?-->", re.S)


def kind_of(section: str):
    m = STAGE.search(section)
    if not m:
        return None
    classes = m.group(1).split()
    for k in NEED:
        if k in classes:
            return k
    return None


def encode(path: Path, need):
    """返回 (data_uri, 说明)。分辨率不够时抛 ValueError。"""
    with Image.open(path) as im:
        fmt = im.format
        if fmt in PASSTHRU:
            if need:
                w, h = im.size
                if w < need[0] or h < need[1]:
                    raise ValueError(f"{w}×{h}，这个位置至少要 {need[0]}×{need[1]}")
            data = path.read_bytes()
            return (f"data:{PASSTHRU[fmt]};base64,{base64.b64encode(data).decode()}",
                    f"{fmt} 原样内联（未重新编码，元数据未清理，请自行确认）")
        if fmt not in REENCODE:
            raise ValueError(f"不支持的格式 {fmt}，先转成 JPEG 或 PNG")

        im = ImageOps.exif_transpose(im)
        w, h = im.size
        if need and (w < need[0] or h < need[1]):
            factor = max(need[0] / w, need[1] / h)
            raise ValueError(f"{w}×{h}，这个位置至少要 {need[0]}×{need[1]}（会被放大到 {factor:.2f} 倍）")

        scale = min(1.0, MAX_EDGE / max(w, h))
        if need:
            scale = max(scale, need[0] / w, need[1] / h)
        scale = min(scale, 1.0)
        if scale < 1.0:
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

        mime, save_as = REENCODE[fmt]
        buf = io.BytesIO()
        if save_as == "JPEG":
            im.convert("RGB").save(buf, "JPEG", quality=85, optimize=True, progressive=True)
        else:
            im.save(buf, "PNG", optimize=True)
        note = f"{w}×{h}" + (f" → {im.size[0]}×{im.size[1]}" if scale < 1.0 else "") + "，元数据已清除"
        return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}", note


def process(src: Path, out: Path, log=print) -> int:
    text = src.read_text(encoding="utf-8")
    base = src.parent
    errors, warnings, cache = [], [], {}

    def fix_section(match):
        section = match.group(0)
        live = COMMENT.sub("", section)          # 注释里的示例 <img> 不算
        kind = kind_of(live)
        need = NEED.get(kind)
        slide_no = text.count('<section class="slide"', 0, match.start()) + 1

        if kind and not IMG.search(live):
            warnings.append(f"第 {slide_no} 张：{kind} 图还是占位，没有放图")
        if kind and IMG.search(live):
            credit = CREDIT.search(live)
            body = html.unescape(TAG.sub("", credit.group(1))).strip() if credit else ""
            if not body or "{{" in body:
                errors.append(f"第 {slide_no} 张：{kind} 图没有填来源行（.credit）")

        def fix_img(m):
            src_attr = m.group(1)
            if src_attr.startswith("data:"):
                return m.group(0)
            if re.match(r"^https?://", src_attr):
                errors.append(f"第 {slide_no} 张：{src_attr} 是外部资源，下载到本地再引")
                return m.group(0)
            path = (base / html.unescape(src_attr)).resolve()
            if not path.is_file():
                errors.append(f"第 {slide_no} 张：找不到 {src_attr}")
                return m.group(0)
            key = (path, need)
            try:
                if key not in cache:
                    cache[key] = encode(path, need)
                uri, note = cache[key]
            except ValueError as exc:
                errors.append(f"第 {slide_no} 张：{src_attr} {exc}")
                return m.group(0)
            except OSError as exc:
                errors.append(f"第 {slide_no} 张：{src_attr} 读不出来（{exc}）")
                return m.group(0)
            log(f"  第 {slide_no} 张  {src_attr}  {note}")
            return m.group(0).replace(f'src="{src_attr}"', f'src="{uri}"', 1)

        # 只替换注释以外的 <img>
        pieces, last = [], 0
        for c in COMMENT.finditer(section):
            pieces.append(IMG.sub(fix_img, section[last:c.start()]))
            pieces.append(c.group(0))
            last = c.end()
        pieces.append(IMG.sub(fix_img, section[last:]))
        return "".join(pieces)

    result = SECTION.sub(fix_section, text)

    for w in warnings:
        log(f"  ! {w}")
    if errors:
        log("有问题，没有写出文件：")
        for e in errors:
            log(f"  ✗ {e}")
        return 1
    out.write_text(result, encoding="utf-8")
    log(f"已写出：{out}（{out.stat().st_size / 1024:.0f} KB）")
    return 0


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # 够大的满版图，带一个 GPS EXIF 字段
        big = Image.new("RGB", (3000, 1700), (40, 90, 160))
        exif = Image.Exif()
        exif[0x8825] = {2: (31.0, 14.0, 0.0)}      # GPSInfo / GPSLatitude
        big.save(d / "big.jpg", exif=exif)
        Image.new("RGB", (1200, 800), (10, 10, 10)).save(d / "small.jpg")

        def deck(img, credit):
            return (f'<section class="slide"><div class="stage bleed">'
                    f'<div class="photo"><img src="{img}" alt=""></div>'
                    f'<div class="credit">{credit}</div></div></section>')

        cases = [
            ("满版图够大、有来源 → 通过并清掉 GPS", deck("big.jpg", "来源：作者自摄"), 0),
            ("满版图只有 1200×800 → 拦下", deck("small.jpg", "来源：作者自摄"), 1),
            ("来源行还是占位 → 拦下", deck("big.jpg", "{{来源}}"), 1),
            ("外部链接 → 拦下", deck("https://example.com/a.jpg", "来源：某处"), 1),
            ("注释里的示例 img 不处理", '<section class="slide"><div class="stage bleed">'
             '<div class="photo"><!-- <img src="nope.jpg" alt=""> --></div>'
             '<div class="credit">{{来源}}</div></div></section>', 0),
        ]
        ok = True
        for name, body, want in cases:
            src = d / "deck.html"
            src.write_text(body, encoding="utf-8")
            out = d / "out.html"
            if out.exists():
                out.unlink()
            lines = []
            code = process(src, out, log=lines.append)
            extra = ""
            if want == 0 and "big.jpg" in body and code == 0:
                uri = re.search(r'src="data:image/jpeg;base64,([^"]+)"', out.read_text()).group(1)
                with Image.open(io.BytesIO(base64.b64decode(uri))) as im:
                    gps = im.getexif().get(0x8825)
                    extra = f"，内联后 {im.size[0]}×{im.size[1]}，GPS {'仍在' if gps else '已清除'}"
                    if gps or max(im.size) > MAX_EDGE:
                        code = 99
            passed = code == want
            ok &= passed
            print(f"  {'pass' if passed else 'FAIL'}  {name}（退出 {code}{extra}）")
            if not passed:
                print("\n".join("        " + l for l in lines))
        print("自检" + ("通过" if ok else "未通过"))
        return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if not args or args[0].startswith("-"):
        print(__doc__.strip().split("\n\n")[0])
        print("用法：python3 inline_images.py deck.html [out.html]  |  --selftest")
        return 64
    src = Path(args[0])
    if not src.is_file():
        print(f"找不到文件：{src}")
        return 66
    out = Path(args[1]) if len(args) > 1 else src.with_name(src.stem + ".inlined.html")
    return process(src, out)


if __name__ == "__main__":
    raise SystemExit(main())
