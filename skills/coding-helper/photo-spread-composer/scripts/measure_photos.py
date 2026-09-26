#!/usr/bin/env python3
"""量一组照片：长宽比、像素、EXIF 里的署名，并标出不能用的。

    python3 measure_photos.py <目录或文件…> [--dpi 300] [--min-mm 40]
    python3 measure_photos.py --selftest

只读，不改任何文件，也不把照片本身读进对话——排版只需要长宽比和像素数。

尺寸按 EXIF 方向转正后计：手机竖拍的照片存成横图、靠 Orientation 标签转正，
这里量出来就是竖图，和 build_spread.py 排进版面的一致。

--min-mm 是"这张照片最小会被排到多宽"的预估，用来提前发现分辨率不够的。
真正的判定在 build_spread.py 里按解出的实际尺寸做，这里只是早一步预警。

依赖 Pillow 和同目录的 image_io.py（与摄影类 skill 共用的读图模块）。
HEIC 要装 pillow-heif 才读得了；没装时逐张给出 sips 转换命令，不会静默跳过。
"""

import argparse
import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import image_io  # noqa: E402  (shared copy; also checks that Pillow is installed)
except ModuleNotFoundError as exc:  # pragma: no cover - only when the file was not copied along
    if exc.name == "image_io":
        sys.exit("缺 image_io.py：它和本脚本放在同一个 scripts/ 目录，复制时要一起带上")
    raise

from PIL import ExifTags, Image  # noqa: E402

# 目录扫描收哪些文件：能读的格式，再加上 HEIC——读不了也要列出来说明，不能静默漏掉
SCAN_EXTS = image_io.READABLE_EXTS | image_io.HEIF_EXTS
# EXIF 里可能存署名的两个标签
CREDIT_TAGS = {"Artist", "Copyright"}


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"要一个正整数，收到 {value!r}")
    if number <= 0:
        raise argparse.ArgumentTypeError(f"要一个正整数，收到 {value!r}")
    return number


def positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"要一个正数，收到 {value!r}")
    if not number > 0 or number == float("inf"):
        raise argparse.ArgumentTypeError(f"要一个正数，收到 {value!r}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="measure_photos.py",
        description="量一组照片的长宽比、像素和 EXIF 署名，标出分辨率可能不够、缺署名和读不了的。只读，不改文件。",
    )
    parser.add_argument("paths", nargs="*", metavar="目录或文件", help="照片目录或照片文件，可以给多个")
    parser.add_argument("--dpi", type=positive_int, default=300, help="目标分辨率，打印默认 300，屏幕浏览用 150")
    parser.add_argument("--min-mm", type=positive_float, default=40.0, help="预估这张照片最小会排到多宽（mm），默认 40")
    parser.add_argument("--selftest", action="store_true", help="跑内置的回归检查后退出")
    return parser


def _text(value) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value).replace("\x00", "").strip()


def credit_of(path: Path) -> str:
    try:
        with Image.open(path) as im:
            exif = im.getexif()
    except Exception:
        return ""
    out = []
    for tag_id, value in exif.items():
        if ExifTags.TAGS.get(tag_id, "") in CREDIT_TAGS and _text(value):
            out.append(_text(value))
    return " / ".join(out)


def is_heif(path: Path, exc: Exception) -> bool:
    return path.suffix.lower() in image_io.HEIF_EXTS or "HEIC/HEIF" in str(exc)


def heic_hint(path: Path) -> str:
    return (
        f"{path.name}：HEIC 本机读不了（没有装 pillow-heif）。先转成 JPEG，macOS 自带、保留 EXIF："
        f'sips -s format jpeg "{path}" --out "{path.with_suffix(".jpg")}"'
    )


def collect(paths) -> tuple:
    files, missing = [], []
    for a in paths:
        p = Path(a).expanduser()
        if p.is_dir():
            files += [
                f for f in sorted(p.iterdir())
                if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in SCAN_EXTS
            ]
        elif p.is_file():
            files.append(p)
        else:
            missing.append(a)
    return files, missing


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.paths:
        parser.error("至少给一个照片目录或文件")

    files, missing = collect(args.paths)
    for a in missing:
        print(f"跳过（找不到）: {a}", file=sys.stderr)
    if not files:
        print("没有找到可读的图片", file=sys.stderr)
        return 1

    dpi, min_mm = args.dpi, args.min_mm
    need_px = min_mm / 25.4 * dpi
    print(f"# {len(files)} 张 · 按 {dpi}dpi、最小排到 {min_mm:g}mm 宽预估"
          f"（需 {need_px:.0f}px）· 尺寸按 EXIF 方向转正后计\n")
    print(f"{'文件':<34}{'像素':>13}{'长宽比':>8}  {'取向':<6}{'署名'}")
    print("-" * 86)

    rows, no_credit, too_small, unreadable = [], [], [], []
    for f in files:
        try:
            w, h = image_io.oriented_size(f)
        except image_io.ImageIOError as e:
            if is_heif(f, e):
                unreadable.append(heic_hint(f))
                print(f"{f.name:<34}  读不出：HEIC，要先转成 JPEG（命令见下）")
            else:
                unreadable.append(f"{f.name}：{e}")
                print(f"{f.name:<34}  读不出：{e}")
            continue
        if not w or not h:
            unreadable.append(f"{f.name}：尺寸为 0")
            print(f"{f.name:<34}  读不出：尺寸为 0")
            continue
        cred = credit_of(f)
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
            print(f"  {name}: {w}px，排到 {min_mm:g}mm 需要 {need:.0f}px，差 {need-w:.0f}px")
        print("  排小一点可以过；build_spread.py 会按实际解出的尺寸再判一次。")

    if no_credit:
        print(f"\nEXIF 里没有署名（{len(no_credit)} 张）：{'、'.join(no_credit[:8])}"
              + ("…" if len(no_credit) > 8 else ""))
        print("  署名不能省。EXIF 里没有就在 plan 的 credit 字段手写，问清楚是谁拍的。")

    if unreadable:
        print(f"\n读不了的（{len(unreadable)} 张），不会进版面：")
        for line in unreadable:
            print(f"  {line}")
        if any("HEIC" in line for line in unreadable):
            print("  HEIC 转成 JPEG 后，对转出来的文件重新量一遍，plan 里也写转出来的文件名。")
    return 0 if rows else 1


# ---------------------------------------------------------------- self-test


def _run(argv) -> tuple:
    """(exit code, stdout, stderr) of main(argv), with argparse exits caught."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def selftest() -> int:
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # 手机竖拍：存成 1200×800，Orientation=6，显示为 800×1200
        exif = Image.Exif()
        exif[0x0112] = 6
        exif[0x013B] = "Test Shooter"
        Image.new("RGB", (1200, 800), (40, 120, 200)).save(d / "phone.jpg", exif=exif.tobytes())
        Image.new("RGB", (1500, 1000), (200, 200, 60)).save(d / "wide.jpg")
        (d / "iphone.heic").write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
        (d / "notes.txt").write_text("not a photo")

        code, out, err = _run([str(d), "--dpi=150", "--min-mm=60"])
        phone = next((line for line in out.splitlines() if line.startswith("phone.jpg")), "")
        check("orientation 6 measured upright (800×1200, 竖)", "800×1200" in phone and "0.667" in phone and "竖" in phone, phone)
        check("--dpi=150 --min-mm=60 (equals form) honoured", "按 150dpi、最小排到 60mm" in out, out.splitlines()[0] if out else err)
        check("credit read from EXIF Artist", "Test Shooter" in phone, phone)
        check("normal run exits 0", code == 0, str(code))
        if not image_io.HEIF_SUPPORTED:
            check("HEIC listed with the sips command", "sips -s format jpeg" in out and "iphone.heic" in out, out[-400:])
        check("non-image files in a folder are not listed", "notes.txt" not in out)

        code, out, err = _run([str(d), "--dpi", "150"])
        check("space form still works", "按 150dpi" in out)

        code, out, err = _run([str(d), "--dpl=150"])
        check("unknown option is an error, not skipped", code == 2 and "unrecognized" in err, f"{code} {err.strip()[-80:]}")

        code, out, err = _run([str(d), "--dpi=abc"])
        check("non-numeric --dpi is an error", code == 2 and "--dpi" in err, err.strip()[-80:])

        code, out, err = _run(["--help"])
        check("--help prints usage and exits 0", code == 0 and "usage" in out.lower(), str(code))

        code, out, err = _run([str(d / "nope.jpg")])
        check("missing file reported, exit 1", code == 1 and "找不到" in err and "Traceback" not in err, err.strip())

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}".rstrip())
    print(f"{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
