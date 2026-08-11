#!/usr/bin/env python3
"""歌词机械体检：字数、断句、陈词命中、重复行、与字数模板的比对。

只做不需要读音的检查。押韵、画面感、推进、可唱性需要判断，交给模型，
见 skills/songwriting/_shared/craft-reference.md。

用法：
    python3 lyric_check.py 歌词.txt
    python3 lyric_check.py 歌词.txt --template 模板.txt
    python3 lyric_check.py 歌词.txt --extra 星光,月光

歌词文件格式：段落名单独一行，空行分隔段落。模板文件同格式，用 x 表示字。
"""

import argparse
import re
import sys
from collections import Counter

# 陈词黑名单，与 _shared/craft-reference.md 第 2 节保持一致
CLICHE_IMAGE = [
    "星光", "月光", "阳光", "光芒", "微风", "晚风", "海洋", "彼岸", "远方",
    "天堂", "翅膀", "花开", "岁月", "时光", "泪光", "伤疤", "港湾", "灯火",
    "荆棘", "迷雾", "黑夜", "黎明", "星辰", "大海",
]
CLICHE_EMOTION = [
    "治愈", "温柔", "拥抱", "绽放", "闪耀", "璀璨", "勇敢", "坚强", "迷茫",
    "彷徨", "释怀", "沉淀", "救赎", "破碎", "蜕变", "煎熬", "疲惫", "不安",
]
CLICHE_PHRASE = [
    "总有一天", "不必", "不用", "你值得", "慢慢来", "别害怕", "本来的样子",
    "终会", "终将", "请相信", "会好的", "都会变成", "都会过去",
]

CJK = re.compile(r"[一-鿿]")

# 段落名靠关键词识别，不靠"这行很短"。短句歌词（"很勇敢"）也会很短，
# 用长度判断会把词当成段落名吃掉。
SECTION_WORDS = [
    "主歌", "主", "预副歌", "预副", "副歌", "副", "桥段", "桥", "尾段", "尾声", "尾",
    "间奏", "前奏", "引子", "Verse", "Chorus", "Pre-Chorus", "Pre", "Bridge",
    "Outro", "Intro", "Hook", "Refrain",
]
SECTION_HINT = re.compile(
    r"^(%s)\s*[0-9一二三四五六七八九]?$" % "|".join(sorted(SECTION_WORDS, key=len, reverse=True)),
    re.IGNORECASE,
)


def count_chars(text):
    """只数汉字，忽略标点、空格、拉丁字母。"""
    return len(CJK.findall(text))


def segments(line):
    """按空格切出停顿分段，返回每段字数。"""
    return [count_chars(p) for p in line.split() if count_chars(p)]


def last_char(line):
    chars = CJK.findall(line)
    return chars[-1] if chars else ""


def parse(path):
    """返回 [(段落名, [行, ...]), ...]。没有段落名的开头归入「未命名」。"""
    raw = open(path, encoding="utf-8").read().splitlines()
    sections, name, lines = [], None, []
    for line in raw:
        stripped = line.strip()
        if not stripped:
            continue
        if SECTION_HINT.match(stripped):
            if lines:
                sections.append((name or "未命名", lines))
                lines = []
            name = stripped
        else:
            lines.append(stripped)
    if lines:
        sections.append((name or "未命名", lines))
    return sections


def parse_template(path):
    """模板用 x 表示字，返回 [(段落名, [(总字数, [分段字数]), ...]), ...]。"""
    raw = open(path, encoding="utf-8").read().splitlines()
    sections, name, rows = [], None, []
    for line in raw:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped and set(stripped.replace(" ", "")) <= {"x", "X"}:
            parts = [len(p) for p in stripped.split() if p]
            rows.append((sum(parts), parts))
        else:
            if rows:
                sections.append((name or "未命名", rows))
                rows = []
            name = stripped
    if rows:
        sections.append((name or "未命名", rows))
    return sections


def find_cliches(line, extra):
    hits = []
    for group, words in (
        ("意象", CLICHE_IMAGE), ("情绪", CLICHE_EMOTION), ("句式", CLICHE_PHRASE),
    ):
        for w in words:
            if w in line:
                hits.append("%s:%s" % (group, w))
    for w in extra:
        if w and w in line:
            hits.append("自定:%s" % w)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lyrics")
    ap.add_argument("--template", help="字数模板文件（x 表示字）")
    ap.add_argument("--extra", default="", help="额外的禁用词，逗号分隔")
    args = ap.parse_args()

    extra = [w.strip() for w in args.extra.split(",") if w.strip()]
    sections = parse(args.lyrics)
    template = parse_template(args.template) if args.template else None

    problems = 0
    all_lines = []
    total_cliche = Counter()

    for idx, (name, lines) in enumerate(sections):
        tpl_rows = None
        if template:
            match = [rows for n, rows in template if n == name]
            tpl_rows = match[0] if match else (template[idx][1] if idx < len(template) else None)

        print("\n== %s ==" % name)
        for i, line in enumerate(lines):
            n = count_chars(line)
            segs = segments(line)
            seg_note = "+".join(str(s) for s in segs) if len(segs) > 1 else ""
            note = []

            if tpl_rows and i < len(tpl_rows):
                want, want_segs = tpl_rows[i]
                diff = n - want
                if abs(diff) > 1:
                    note.append("字数 %+d（模板 %d）" % (diff, want))
                    problems += 1
                elif diff:
                    note.append("字数 %+d，在 ±1 内" % diff)
                if len(segs) != len(want_segs):
                    note.append("停顿 %d 处，模板 %d 处" % (len(segs) - 1, len(want_segs) - 1))
                    problems += 1

            hits = find_cliches(line, extra)
            if hits:
                note.append("陈词 " + " ".join(hits))
                for h in hits:
                    total_cliche[h] += 1

            all_lines.append(line)
            print("  %2d. %-38s %2d字%s  末「%s」%s"
                  % (i + 1, line, n,
                     " (%s)" % seg_note if seg_note else "",
                     last_char(line),
                     "  ⚠ " + "；".join(note) if note else ""))

        if tpl_rows and len(lines) != len(tpl_rows):
            print("  ⚠ 本段 %d 行，模板 %d 行" % (len(lines), len(tpl_rows)))
            problems += 1

    dupes = [l for l, c in Counter(all_lines).items() if c > 1]
    endings = Counter(last_char(l) for l in all_lines if last_char(l))
    repeated_end = [(c, n) for c, n in endings.items() if n > 2]

    print("\n== 汇总 ==")
    print("  行数 %d，总字数 %d" % (len(all_lines), sum(count_chars(l) for l in all_lines)))
    print("  陈词命中 %d 处%s" % (sum(total_cliche.values()),
                              "：" + " ".join("%s×%d" % (k, v) for k, v in total_cliche.most_common())
                              if total_cliche else ""))
    if dupes:
        print("  完全重复的行：" + " / ".join(dupes))
    if repeated_end:
        print("  同一个字收尾 ≥3 次：" + " ".join("%s×%d" % (c, n) for c, n in repeated_end))
    print("  机械问题 %d 处" % problems)
    print("\n  押韵、画面感、推进、可唱性需要判断，脚本不做，见 craft-reference.md")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
