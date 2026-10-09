#!/usr/bin/env python3
"""bento-infographic 的命令行入口。

  bento.py render SPEC LAYOUT --out DIR [--pdf] [--cli] [--html-only]
        生成 HTML，用本机 Chrome（DevTools 协议）渲染成 PNG，并量出 dom.json、fonts.json；
        --pdf 另出矢量 PDF（只用 Inter 与思源黑体）；--cli 改用命令行截图（后备，量不了页面）；
        --html-only 只出 HTML，不要 Chrome（降级：没有 PNG，也没有自检）。Chrome 不在默认位置时设 BENTO_CHROME
  bento.py plan SPEC [--out DIR]
        打印内容清单（每格一行）、格数、纯文字格占比和问题，并出一张线框预览；有问题时退出码非零
  bento.py layout SPEC [--n 3] [--seeds 500] --out DIR
        自动排版，出 layout-1.json …（分数从好到差）和对应的线框图
  bento.py check SPEC LAYOUT --dir DIR
        对已渲染的目录重跑自检（读 dom.json、fonts.json、bento.png、bento.textless.png），写 qa.json；没通过退出码 1
  bento.py --selftest
        跑测试
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Apple-keynote-style bento infographic: plan, layout, render, check.")
    ap.add_argument("--selftest", action="store_true", help="run the synthetic and fixture tests")
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="command")
    r = sub.add_parser("render", help="build the HTML and render it to PNG")
    r.add_argument("spec")
    r.add_argument("layout")
    r.add_argument("--out", required=True, help="output directory (created if missing)")
    r.add_argument("--cli", action="store_true", help="use Chrome's command-line screenshot (fallback)")
    r.add_argument("--pdf", action="store_true", help="also print a vector PDF with the open fonts")
    r.add_argument("--no-check", action="store_true", help="skip the QA checks")
    r.add_argument("--html-only", action="store_true", help="write the HTML only, no Chrome (no PNG, no QA)")
    ck = sub.add_parser("check", help="re-run the QA checks on a rendered directory")
    ck.add_argument("spec")
    ck.add_argument("layout")
    ck.add_argument("--dir", required=True)
    pl = sub.add_parser("plan", help="print the content list, its problems, and a wireframe preview")
    pl.add_argument("spec")
    pl.add_argument("--out", help="where to write wireframe.png (default: next to the spec)")
    lay = sub.add_parser("layout", help="propose layouts (best first) with wireframes")
    lay.add_argument("spec")
    lay.add_argument("--n", type=int, default=3)
    lay.add_argument("--seeds", type=int, default=500)
    lay.add_argument("--out", required=True)
    return ap


def cmd_render(args) -> int:
    import bento_render as br
    import bento_spec as bs
    spec_path = Path(args.spec).resolve()
    spec = bs.load_spec(spec_path)
    problems = bs.validate_spec(spec, spec_path.parent)
    if problems:
        print("bento.json 有问题：\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    out = Path(args.out)
    if args.html_only:
        layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
        print("html  %s" % br.build_html(spec, layout, out, base_dir=spec_path.parent))
        print("降级：只出了 HTML，没有 PNG，也没有自检")
        return 0
    if not br.CHROME.exists():
        print("没找到 Google Chrome（%s）。装上 Chrome，或用环境变量 BENTO_CHROME 指到它；"
              "只要 HTML 就加 --html-only（降级：没有 PNG，也没有自检）。" % br.CHROME, file=sys.stderr)
        return 4
    if args.cli:
        layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
        css_w, css_h, dpr = bs.canvas_css(spec)
        html_path = br.build_html(spec, layout, out, base_dir=spec_path.parent)
        print(br.screenshot_cli(html_path, out / "bento.png", round(css_w), round(css_h), dpr))
        return 0
    result = br.render(spec_path, args.layout, out, pdf=args.pdf, run_check=not args.no_check)
    for key in ("png", "pdf", "html", "dom", "fonts", "qa"):
        if key in result:
            print("%-5s %s" % (key, result[key]))
    if "qa_summary" in result:
        print(result["qa_summary"])
    return 0


def cmd_check(args) -> int:
    import bento_check
    import bento_spec as bs
    spec = bs.load_spec(Path(args.spec).resolve())
    layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    d = Path(args.dir)
    dom = json.loads((d / "dom.json").read_text(encoding="utf-8"))
    dom["fonts"] = json.loads((d / "fonts.json").read_text(encoding="utf-8"))
    qa = bento_check.check(spec, layout, dom, d / "bento.png", d / "bento.textless.png")
    (d / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
    print(bento_check.summary(qa))
    return 0 if qa["pass"] else 1


def cmd_plan(args) -> int:
    import bento_layout as bl
    import bento_spec as bs
    spec_path = Path(args.spec).resolve()
    spec = bs.load_spec(spec_path)
    problems = bs.validate_spec(spec, spec_path.parent)
    tiles = spec.get("tiles") or []
    print("%-18s %-7s %-6s %-26s %s" % ("id", "种类", "重要", "标签 / 字", "图或图标 · 出处"))
    for t in tiles:
        pm = (" ± %s " % t["uncertainty"]) if t.get("uncertainty") not in (None, "") else ""
        main = t.get("word") or ("%s%s%s" % (t.get("value", ""), pm, t.get("unit") or "") if t.get("kind") == "stat" else "")
        text = " / ".join(x for x in (main, bs.display_label(t, spec.get("lang", "zh-CN")) or "") if x).replace("\n", " / ")
        media = t.get("image") or (("图标 " + t["icon"]) if t.get("icon") else "")
        facts = "【未确认】" if t.get("unverified") else "; ".join(f.get("source", "") for f in t.get("facts") or [])
        print("%-18s %-7s %-6s %-26s %s" % (t.get("id"), t.get("kind"), t.get("weight", 1), text[:26],
                                           " · ".join(x for x in (media, facts) if x)))
    ring = [t for t in tiles if t.get("kind") != "hero"]
    text_only = [t for t in ring if bl.text_only(t)]
    css_w, css_h, _ = bs.canvas_css(spec) if spec.get("canvas") else (0, 0, 0)
    lo, hi = bs.count_range(spec["canvas"]["use"], css_w, css_h) if css_w else (0, 0)
    lo_x, hi_x = bs.count_limits(spec["canvas"]["use"], css_w, css_h) if css_w else (0, 0)
    print("\n格数 %d（这个画幅建议 %d–%d，最少 %d、最多 %d）；纯文字格 %d/%d（%.0f%%，上限 30%%）" % (
        len(tiles), lo, hi, lo_x, hi_x, len(text_only), len(ring), 100 * len(text_only) / max(1, len(ring))))
    if len(text_only) > 0.3 * len(ring):
        problems.append("纯文字格超过三成：苹果的格子大多有图，换成图标格或实物格")
    if css_w and not (lo_x <= len(tiles) <= hi_x):
        problems.append("格数 %d 不在 %d–%d 之间" % (len(tiles), lo_x, hi_x))
    elif css_w and not (lo <= len(tiles) <= hi):
        print("提醒：格数不在建议范围里，%s" % ("每格会空一些，能补就补几格" if len(tiles) < lo else "格子会挤，能并就并几格"))
    for d in spec.get("dropped") or []:
        print("舍弃：%s（%s）" % (d.get("text"), d.get("reason")))
    if problems:
        print("\n问题：\n  " + "\n  ".join(problems))
        return 2
    cands = bl.candidates(spec, n=1, base_dir=spec_path.parent)
    if not cands:
        print("\n排不出来：格子太多或画布太小。")
        return 3
    out = Path(args.out) if args.out else spec_path.parent
    out.mkdir(parents=True, exist_ok=True)
    print("\n线框预览：%s" % bl.wireframe(spec, cands[0], out / "wireframe.png"))
    return 0


def cmd_layout(args) -> int:
    import bento_layout as bl
    import bento_spec as bs
    spec_path = Path(args.spec).resolve()
    spec = bs.load_spec(spec_path)
    problems = bs.validate_spec(spec, spec_path.parent)
    if problems:
        print("bento.json 有问题：\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cands = bl.candidates(spec, n=args.n, seeds=args.seeds, base_dir=spec_path.parent)
    if not cands:
        print("排不出来：格子太多或画布太小。减几格，或者换大一点的画幅。", file=sys.stderr)
        return 3
    for i, lay in enumerate(cands, 1):
        path = out / ("layout-%d.json" % i)
        path.write_text(json.dumps(lay, ensure_ascii=False, indent=1), encoding="utf-8")
        bl.wireframe(spec, lay, out / ("layout-%d.png" % i))
        corners = "".join("带" if lay["pattern"][c] == "band" else "栏" for c in ("tl", "tr", "bl", "br"))
        print("%s  分数 %.2f  四角（左上 右上 左下 右下）：%s" % (path, lay["score"], corners))
    return 0


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.selftest:
        if args.command:
            ap.error("--selftest cannot be combined with a command")
        from test_bento import run_tests
        return run_tests()
    if args.command == "render":
        return cmd_render(args)
    if args.command == "layout":
        return cmd_layout(args)
    if args.command == "plan":
        return cmd_plan(args)
    if args.command == "check":
        return cmd_check(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
