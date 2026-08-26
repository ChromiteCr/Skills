#!/usr/bin/env python3
"""量一组照片：长宽比、像素、EXIF 里的署名，并标出不能用的。

    python3 measure_photos.py <目录或文件…> [--dpi 300] [--min-mm 40]

只读，不改任何文件，也不把照片本身读进对话——排版只需要长宽比和像素数。

--min-mm 是"这张照片最小会被排到多宽"的预估，用来提前发现分辨率不够的。
真正的判定在 build_spread.py 里按解出的实际尺寸做，这里只是早一步预警。
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ExifTags
except ImportError:
    sys.exit("缺 Pillow。装：pip3 install Pillow")

EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}
# EXIF 里可能存署名的两个标签
CREDIT_TAGS = {"Artist", "Copyright"}


def credit_of(img) -> str:
    try:
        exif = img.getexif()
    except Exception:
        return ""
    out = []
    for tag_id, value in exif.items():
        name = ExifTags.TAGS.get(tag_id, "")
        if name in CREDIT_TAGS and str(value).strip():
            out.append(str(value).strip())
    return " / ".join(out)


def collect(args) -> list:
    files = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            files += [f for f in sorted(p.iterdir()) if f.suffix.lower() in EXTS]
        elif p.is_file():
            files.append(p)
        else:
            print(f"跳过（找不到）: {a}", file=sys.stderr)
    return files


def main() -> int:
    dpi, min_mm, argv = 300, 40.0, []
    rest = sys.argv[1:]
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--dpi" and i + 1 < len(rest):
            dpi = int(rest[i + 1]); i += 2
        elif a == "--min-mm" and i + 1 < len(rest):
            min_mm = float(rest[i + 1]); i += 2
        elif a.startswith("--"):
            i += 1                      # 不认识的开关，跳过它自己
        else:
            argv.append(a); i += 1
    if not argv:
        sys.exit(__doc__.strip().splitlines()[2])

    files = collect(argv)
    if not files:
        sys.exit("没有找到可读的图片")

    need_px = min_mm / 25.4 * dpi
    print(f"# {len(files)} 张 · 按 {dpi}dpi、最小排到 {min_mm:.0f}mm 宽预估"
          f"（需 {need_px:.0f}px）\n")
    print(f"{'文件':<34}{'像素':>13}{'长宽比':>8}  {'取向':<6}{'署名'}")
    print("-" * 86)

    rows, no_credit, too_small = [], [], []
    for f in files:
        try:
            with Image.open(f) as im:
                w, h = im.size
                cred = credit_of(im)
        except Exception as e:
            print(f"{f.name:<34}  读不出：{e}")
            continue
        a = w / h
        orient = "横" if a > 1.15 else ("竖" if a < 0.87 else "方")
        if w < need_px:
            too_small.append((f.name, w, need_px))
        if not cred:
            no_credit.append(f.name)
        rows.append((f.name, w, h, a))
        print(f"{f.name:<34}{w:>6}×{h:<6}{a:>8.3f}  {orient:<6}{cred or '—'}")

    print()
    if rows:
        aspects = [r[3] for r in rows]
        wide = sum(1 for a in aspects if a > 1.15)
        tall = sum(1 for a in aspects if a < 0.87)
        print(f"取向分布：横 {wide} · 竖 {tall} · 接近方 {len(aspects)-wide-tall}")
        print("提示：一带之内混入竖构图会把带压高；竖图更适合放进 stack 或单独占一带。")

    if too_small:
        print(f"\n分辨率预警（{len(too_small)} 张）：")
        for name, w, need in too_small:
            print(f"  {name}: {w}px，排到 {min_mm:.0f}mm 需要 {need:.0f}px，差 {need-w:.0f}px")
        print("  排小一点可以过；build_spread.py 会按实际解出的尺寸再判一次。")

    if no_credit:
        print(f"\nEXIF 里没有署名（{len(no_credit)} 张）：{'、'.join(no_credit[:8])}"
              + ("…" if len(no_credit) > 8 else ""))
        print("  署名不能省。EXIF 里没有就在 plan 的 credit 字段手写，问清楚是谁拍的。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
