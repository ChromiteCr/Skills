#!/usr/bin/env python3
"""从现有 .pptx 里提取文字与结构，供重构成发布会风格时读。

    python3 read_pptx.py deck.pptx
    python3 read_pptx.py --selftest

只读，不改原文件。输出每页的文字、表格、图片数量，组合形状里的文字也读（组合套组合照样往里读）。
四种情况标成「需要拆」：某一行超过 20 个词（基本是整句，该留给讲的人说）、全页超过 60 个词、
出现项目符号层级、与前面某页的文字重合六成以上（同一张版式换配图重复用）。

依赖 python-pptx（`pip3 install python-pptx`）。

为什么要有这个脚本：把整份 pptx 的 XML 塞进上下文很贵，而且大部分是版式噪音。
这里只取文字和密度信号。
"""

import sys
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.util import Emu
except ImportError:
    sys.exit("缺 python-pptx。装：pip3 install python-pptx")

USAGE = "用法: python3 read_pptx.py <file.pptx>  |  --selftest  |  --help"

# 该拆片的判据。光数总词数会冤枉规格密排和 bento——那两种片型本来就有很多标签值对，
# 但每条都很短。真正需要拆的信号是片上出现了整句散文，或者有项目符号层级。
PROSE_WORDS = 20   # 单行超过这个词数，基本是一整句，属于该留给讲的人说的部分
TOTAL_WORDS = 60   # 总量上限。定这么松是因为规格密排与五步流程条本来就有十几个短标签，
                   # 卡在 45 会把它们全冤枉掉。真正的信号是 PROSE_WORDS，这条只兜底
DUPE_RATIO = 0.6   # 两页文字重合到这个比例，按同一张片的重复用法处理


def words(text: str) -> int:
    """中英混排的粗略计数：非 ASCII 按字算，ASCII 按空格分词。"""
    cjk = sum(1 for ch in text if ord(ch) > 0x2E80)
    latin = len([w for w in "".join(
        ch if ord(ch) <= 0x2E80 else " " for ch in text).split() if w])
    return cjk + latin


def walk(shapes):
    """按文档顺序给出每一个形状；遇到组合就往里走，组合套组合也一样。
    汇报 PPT 里的流程图、标注框、数据框常常是组合，只看顶层会把里面的字静默丢掉。"""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from walk(shape.shapes)
        else:
            yield shape


def report(prs, name: str) -> str:
    out = []
    seen: dict[frozenset, int] = {}   # 文字指纹 → 首次出现的页码
    dupes: list[tuple[int, int, float]] = []
    w, h = prs.slide_width, prs.slide_height
    ratio = f"{w / h:.3f}" if h else "?"
    out.append(f"# {name}")
    out.append(f"尺寸 {Emu(w).inches:.2f}in × {Emu(h).inches:.2f}in · 宽高比 {ratio} "
               f"({'16:9' if abs(w / h - 16 / 9) < 0.01 else '不是 16:9，重构时要改'})")
    out.append(f"共 {len(prs.slides)} 页\n")

    total_dense = 0

    for n, slide in enumerate(prs.slides, 1):
        lines, tables, pics, bullets = [], 0, 0, 0

        for shape in walk(slide.shapes):
            if shape.shape_type == 13 or shape.__class__.__name__ == "Picture":
                pics += 1
            if getattr(shape, "has_table", False) and shape.has_table:
                tables += 1
                continue
            if not getattr(shape, "has_text_frame", False):
                continue
            for para in shape.text_frame.paragraphs:
                text = "".join(r.text for r in para.runs).strip()
                if not text:
                    continue
                # level > 0 基本就是项目符号层级
                if para.level > 0:
                    bullets += 1
                lines.append(text)

        counts = [words(t) for t in lines]
        wc = sum(counts)
        prose = sum(1 for c in counts if c > PROSE_WORDS)

        # 近重复：同一张版式换个配图重复用，是密集汇报 PPT 里最常见的浪费。
        # 逐页单独看永远看不出来，要跨页比。
        fp = frozenset(lines)
        near = None
        if fp:
            for prev_fp, prev_n in seen.items():
                overlap = len(fp & prev_fp) / max(len(fp | prev_fp), 1)
                if overlap >= DUPE_RATIO:
                    near = (prev_n, overlap)
                    break
            if near:
                dupes.append((near[0], n, near[1]))
            else:
                seen[fp] = n

        reasons = []
        if near:
            reasons.append(f"与第 {near[0]} 页重合 {near[1]:.0%}")
        if prose:
            reasons.append(f"{prose} 行是整句")
        if bullets:
            reasons.append(f"项目符号 {bullets} 行")
        if wc > TOTAL_WORDS:
            reasons.append(f"总量 {wc} 词")
        if reasons:
            total_dense += 1

        out.append(f"## 第 {n} 页 · {wc} 词" +
                   (f" · 图 {pics}" if pics else "") +
                   (f" · 表 {tables}" if tables else "") +
                   (f"  ← 需要拆：{'，'.join(reasons)}" if reasons else ""))
        for t, c in zip(lines, counts):
            out.append(f"  - {t}" + (f"   ← {c} 词，整句，该留给讲的人说"
                                     if c > PROSE_WORDS else ""))
        out.append("")

    out.append(f"---\n{total_dense} / {len(prs.slides)} 页需要拆。")
    if dupes:
        pairs = "、".join(f"{b}≈{a}" for a, b, _ in dupes)
        out.append(f"{len(dupes)} 页与前面的片近重复（{pairs}）：同一张版式换配图重复用，合并成一张。")
    out.append("整句的那几行：片上只留碎片、数字或图，句子留给讲的人说。")
    out.append("项目符号那几行：顺序性的拆片，并列性的改成 bento 格或图形。")
    out.append("规格密排与 bento 本来就有很多短标签，词数高不算问题，看的是有没有整句。")
    return "\n".join(out)


def selftest() -> int:
    """审计复现的组合形状当回归用例，另加各条判据与 CLI 的检查。通过退出 0，否则 1。"""
    import io
    import subprocess
    import tempfile
    from pptx.util import Inches

    def box(shapes, text, top=1.0):
        tb = shapes.add_textbox(Inches(1), Inches(top), Inches(8), Inches(0.8))
        tb.text_frame.text = text
        return tb.text_frame

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]

    # 第 1 页：审计复现。顶层一个文本框，组合里一个，组合套组合里再一个，外加组合里的一张图
    s = prs.slides.add_slide(blank)
    box(s.shapes, "顶层文字")
    group = s.shapes.add_group_shape()
    box(group.shapes, "组合里的关键数据 42%", 2.0)
    inner = group.shapes.add_group_shape()
    box(inner.shapes, "组合套组合的第三步", 3.0)
    png = io.BytesIO()
    from PIL import Image                       # python-pptx 自己就依赖 Pillow
    Image.new("RGB", (8, 8), (200, 60, 40)).save(png, "PNG")
    png.seek(0)
    group.shapes.add_picture(png, Inches(9), Inches(2), Inches(1), Inches(1))

    # 第 2 页：项目符号
    tf = box(prs.slides.add_slide(blank).shapes, "三个问题")
    for item in ("第一条", "第二条"):
        para = tf.add_paragraph()
        para.text, para.level = item, 1
    # 第 3 页：一整句散文（25 个字）
    box(prs.slides.add_slide(blank).shapes, "我们在过去一年里访谈了两千名用户发现大家都记不清练了多久")
    # 第 4 页：短标签很多，总量超过 60 词
    s = prs.slides.add_slide(blank)
    for k in range(7):
        box(s.shapes, f"规格项目第{k}条的数值说明", 0.5 + k * 0.9)
    # 第 5 页：与第 4 页重复；第 6 页：正常的一页
    s = prs.slides.add_slide(blank)
    for k in range(7):
        box(s.shapes, f"规格项目第{k}条的数值说明", 0.5 + k * 0.9)
    box(prs.slides.add_slide(blank).shapes, "练了多久")

    text = report(prs, "selftest.pptx")
    heads = [line for line in text.split("\n") if line.startswith("## 第")]   # 每页的标题行
    checks = [
        ("组合里的文字读得到（审计复现）", "组合里的关键数据 42%" in text),
        ("组合套组合里的文字也读得到", "组合套组合的第三步" in text),
        ("组合里的图片也计数", "· 图 1" in heads[0]),
        ("项目符号标出来", "项目符号 2 行" in heads[1]),
        ("整句标出来", "1 行是整句" in heads[2]),
        ("总量超过 60 词标出来", "总量" in heads[3]),
        ("近重复标出来", "与第 4 页重合" in heads[4] and "5≈4" in text),
        ("正常的一页不标", "需要拆" not in heads[5]),
    ]

    me = str(Path(__file__).resolve())
    run = subprocess.run([sys.executable, me, "--help"], capture_output=True, text=True)
    checks.append(("--help 打印用法，退出 0", run.returncode == 0 and "read_pptx.py deck.pptx" in run.stdout))
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.pptx"
        bad.write_text("不是 pptx", encoding="utf-8")
        run = subprocess.run([sys.executable, me, str(bad)], capture_output=True, text=True)
        checks.append(("坏文件报清楚的错、不吐 traceback",
                       run.returncode == 1 and "读不出来" in run.stderr and "Traceback" not in run.stderr))

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
    if argv == ["--selftest"]:
        return selftest()
    opts = [a for a in argv if a.startswith("-")]
    if opts:
        sys.exit(f"不认识的选项: {', '.join(opts)}。{USAGE}")
    if len(argv) != 1:
        sys.exit(USAGE)

    path = Path(argv[0])
    if not path.is_file():
        sys.exit(f"找不到文件: {path}")
    try:
        prs = Presentation(str(path))
    except Exception as exc:                    # 不是 zip、不是 pptx、包坏了
        sys.exit(f"读不出来：{path} 不是有效的 .pptx（{type(exc).__name__}: {exc}）")
    print(report(prs, path.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
