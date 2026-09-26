#!/usr/bin/env python3
"""歌词机械体检：字数、断句、陈词命中、重复行、与字数模板的比对。

只做不需要读音的检查。押韵、画面感、推进、可唱性需要判断，交给模型，
见 skills/songwriting/_shared/craft-reference.md。

用法：
    python3 lyric_check.py 歌词.txt
    python3 lyric_check.py 歌词.txt --template 模板.txt
    python3 lyric_check.py 歌词.txt --extra 星光，月光
    python3 lyric_check.py --selftest

歌词文件：段落名单独一行，空行分隔段落。段落名可以写成「主歌 1」「主歌1」「【主歌】」
「[Verse 1]」「副歌：」「副歌 A」；AABA 里单独一行的「A」「B」也是段落名。
模板文件同格式，x 表示一个字，空格（半角、全角都行）表示停顿。

歌词的每一段按下面的顺序找模板段落，找到就停：
  1. 段落名相同（不计括号、冒号、空格、大小写）
  2. 去掉尾部编号、把同一种段落的不同写法归一后相同：「主歌 1」「主歌2」「Verse」
     对「主」，「副歌」「Chorus」对「副」，「预副歌」对「预副」，「桥段」对「桥」，
     「尾声」对「尾」。A/B 后缀不去掉：「副歌 A」只对「副 A」「副歌 A」，不对「副」
  3. 还找不到就报出来，计入机械问题，不按位置硬配
同一种段落在歌词里重复出现（主歌 2、第二遍副歌）时反复套用同一个模板段落；
模板把同名段落写了几遍，就按出现的次序一一对应。模板和歌词都没有段落名时整首逐行比对。

退出码：0 没有机械问题；1 有机械问题；2 输入有误（读不了文件、模板里没有 x 行、歌词为空）。
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# 陈词黑名单，与 craft-reference.md 第 2 节一致，--selftest 逐条核对。
# 参考表句式组的「所有的X都会Y」由 ALL_WILL 查；「都会变成」「都会过去」是脚本多查的
# 两个常见变体（前面不带「所有」也算），参考表里没有单列。
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
    "终会", "终将", "这就是最好的", "请相信", "会好的", "都会变成", "都会过去",
]
ALL_WILL = re.compile(r"所有.{0,6}?都会")
ALL_WILL_LABEL = "句式:所有的X都会Y"

CJK = re.compile(r"[一-鿿]")

# 段落名靠关键词识别，不靠"这行很短"。短句歌词（"很勇敢"）也会很短，
# 用长度判断会把词当成段落名吃掉。
SECTION_WORDS = [
    "主歌", "主", "预副歌", "预副", "副歌", "副", "桥段", "桥", "尾段", "尾声", "尾",
    "间奏", "前奏", "引子", "Verse", "Chorus", "Pre-Chorus", "Pre", "Bridge",
    "Outro", "Intro", "Hook", "Refrain",
]
# 同一种段落的不同写法，第 2 步匹配时归到一起；不在表里的写法保持原样
CANON = {
    "主歌": "主", "verse": "主",
    "预副歌": "预副", "pre-chorus": "预副", "pre": "预副",
    "副歌": "副", "chorus": "副",
    "桥段": "桥", "bridge": "桥",
    "尾段": "尾", "尾声": "尾", "outro": "尾",
    "引子": "前奏", "intro": "前奏",
}
# 段落词 + 可选的大写 A-D 后缀 + 可选编号；段落词不分大小写，后缀只认大写
SECTION_RE = re.compile(
    r"^(?P<word>(?i:%s))?\s*(?P<letter>[A-D])?\s*(?:[0-9]+|[一二三四五六七八九十]+)?$"
    % "|".join(re.escape(w) for w in sorted(SECTION_WORDS, key=len, reverse=True))
)
WRAPPED = re.compile(r"^[\[【(（〔]\s*(.*?)\s*[\]】)）〕]$")
TRAILING_COLON = re.compile(r"\s*[:：]$")
UNNAMED = "未命名"


class InputError(Exception):
    """输入有误：退出码 2。"""


def count_chars(text):
    """只数汉字，忽略标点、空格、拉丁字母。"""
    return len(CJK.findall(text))


def segments(line):
    """按空格（半角、全角）切出停顿分段，返回每段字数。"""
    return [count_chars(p) for p in line.split() if count_chars(p)]


def last_char(line):
    chars = CJK.findall(line)
    return chars[-1] if chars else ""


def clean_name(line):
    """去掉段落名两侧的括号和结尾的冒号：「【主歌】」「副歌：」「[Verse 1]」。"""
    s = TRAILING_COLON.sub("", line.strip())
    m = WRAPPED.match(s)
    if m:
        s = TRAILING_COLON.sub("", m.group(1))
    return s.strip()


def header_name(line):
    """这一行是段落名就返回清理后的名字，是歌词行返回 None。"""
    name = clean_name(line)
    m = SECTION_RE.match(name)
    if m and (m.group("word") or m.group("letter")):
        return name
    return None


def exact_key(name):
    return re.sub(r"\s+", "", name).casefold()


def loose_key(name):
    """去掉尾部编号、同义写法归一；A/B 后缀保留。认不出的名字退回 exact_key。"""
    m = SECTION_RE.match(name)
    if not (m and (m.group("word") or m.group("letter"))):
        return exact_key(name)
    word = (m.group("word") or "").casefold()
    return CANON.get(word, word) + (m.group("letter") or "").casefold()


def read_text(path, what):
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise InputError("%s文件不是 UTF-8 编码：%s" % (what, path))
    except OSError as e:
        raise InputError("读不了%s文件 %s：%s" % (what, path, e.strerror or e))


def parse_lyrics(text):
    """返回 [(段落名, [行, ...]), ...]。第一个段落名之前的行归入「未命名」。"""
    sections, name, lines = [], None, []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        header = header_name(stripped)
        if header is not None:
            if lines:
                sections.append((name or UNNAMED, lines))
                lines = []
            name = header
        else:
            lines.append(stripped)
    if lines:
        sections.append((name or UNNAMED, lines))
    if not sections:
        raise InputError("歌词里没有读到任何歌词行")
    return sections


def parse_template(text):
    """模板用 x 表示字，返回 [(段落名, [(总字数, [分段字数]), ...]), ...]。"""
    sections, name, rows = [], None, []
    for number, raw in enumerate(text.splitlines(), 1):
        compact = re.sub(r"\s", "", raw)
        if not compact:
            continue
        if set(compact) <= {"x", "X"}:
            parts = [len(p) for p in raw.split()]
            rows.append((sum(parts), parts))
            continue
        xs = compact.count("x") + compact.count("X")
        if xs >= 3 and 2 * xs >= len(compact):
            raise InputError(
                "模板第 %d 行「%s」像字数行，却混了 x 和空格以外的字符；字数行只写 x，停顿用空格"
                % (number, raw.strip())
            )
        if rows:
            sections.append((name or UNNAMED, rows))
            rows = []
        name = clean_name(raw)
    if rows:
        sections.append((name or UNNAMED, rows))
    if not sections:
        raise InputError("模板里没有读到任何 x 行（x 表示一个字，停顿用空格）")
    return sections


def match_sections(sections, template):
    """给歌词每一段找模板段落，返回模板下标列表，找不到的是 None。"""
    exact = [exact_key(n) for n, _ in template]
    loose = [loose_key(n) for n, _ in template]
    picked = []
    for name, _ in sections:
        found = None
        for key, keys in ((exact_key(name), exact), (loose_key(name), loose)):
            cands = [i for i, k in enumerate(keys) if k == key]
            if cands:
                # 模板把同名段落写了几遍时按出现次序对应，写一遍的反复套用
                seen = sum(1 for p in picked if p in cands)
                found = cands[seen] if seen < len(cands) else cands[0]
                break
        picked.append(found)
    return picked


def find_cliches(line, extra=()):
    hits = []
    for group, words in (
        ("意象", CLICHE_IMAGE), ("情绪", CLICHE_EMOTION), ("句式", CLICHE_PHRASE),
    ):
        for w in words:
            if w in line:
                hits.append("%s:%s" % (group, w))
    if ALL_WILL.search(line):
        # 「所有的伤都会变成星光」的句式只算一处，不再和「都会变成」重复计
        hits = [h for h in hits if h not in ("句式:都会变成", "句式:都会过去")]
        hits.append(ALL_WILL_LABEL)
    for w in extra:
        if w and w in line:
            hits.append("自定:%s" % w)
    return hits


def split_extra(text):
    """--extra 的词表，逗号（全角半角）或顿号分隔。"""
    return [w.strip() for w in re.split(r"[,，、]", text or "") if w.strip()]


def check(sections, template=None, extra=()):
    """跑全部机械检查。返回 (报告的各行, 结果 dict)；结果供 --selftest 断言。"""
    out = []
    problems = 0
    notes = {}
    all_lines = []
    total_cliche = Counter()
    matches = match_sections(sections, template) if template else [None] * len(sections)
    tpl_named = bool(template) and not (len(template) == 1 and template[0][0] == UNNAMED)
    tpl_names = "、".join(dict.fromkeys(n for n, _ in template)) if template else ""

    for si, ((name, lines), ti) in enumerate(zip(sections, matches)):
        tpl_rows = template[ti][1] if ti is not None else None
        head = "\n== %s ==" % name
        if template:
            if ti is None:
                problems += 1
                if not tpl_named:
                    why = "模板没有段落名，没法对号：给模板每段写上段落名，或者去掉歌词里的段落名按整首逐行比对"
                elif name == UNNAMED:
                    why = "这几行前面没有段落名，没法和模板对号：在段首加一行段落名（如「主歌 1」）"
                else:
                    why = "模板里没有对应的段落（模板段落：%s），本段没有比对字数" % tpl_names
                head += "  ⚠ " + why
            elif template[ti][0] != name:
                head += "  （对模板「%s」）" % template[ti][0]
        out.append(head)

        for i, line in enumerate(lines):
            n = count_chars(line)
            segs = segments(line)
            seg_note = "+".join(str(s) for s in segs) if len(segs) > 1 else ""
            note = []

            if tpl_rows is not None and i < len(tpl_rows):
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

            if note:
                notes[(si, i)] = note
            all_lines.append(line)
            out.append("  %2d. %-38s %2d字%s  末「%s」%s"
                       % (i + 1, line, n,
                          " (%s)" % seg_note if seg_note else "",
                          last_char(line),
                          "  ⚠ " + "；".join(note) if note else ""))

        if tpl_rows is not None and len(lines) != len(tpl_rows):
            out.append("  ⚠ 本段 %d 行，模板 %d 行" % (len(lines), len(tpl_rows)))
            problems += 1

    dupes = [l for l, c in Counter(all_lines).items() if c > 1]
    endings = Counter(last_char(l) for l in all_lines if last_char(l))
    repeated_end = [(c, n) for c, n in endings.items() if n > 2]
    used = {m for m in matches if m is not None}
    unused = [n for i, (n, _) in enumerate(template) if i not in used] if template else []

    out.append("\n== 汇总 ==")
    out.append("  行数 %d，总字数 %d" % (len(all_lines), sum(count_chars(l) for l in all_lines)))
    out.append("  陈词命中 %d 处%s" % (sum(total_cliche.values()),
                                    "：" + " ".join("%s×%d" % (k, v) for k, v in total_cliche.most_common())
                                    if total_cliche else ""))
    if dupes:
        out.append("  完全重复的行：" + " / ".join(dupes))
    if repeated_end:
        out.append("  同一个字收尾 ≥3 次：" + " ".join("%s×%d" % (c, n) for c, n in repeated_end))
    if unused:
        out.append("  模板里没用上的段落：" + "、".join(unused))
    out.append("  机械问题 %d 处" % problems)
    out.append("\n  押韵、画面感、推进、可唱性需要判断，脚本不做，见 craft-reference.md")

    return out, {
        "problems": problems, "matches": matches, "notes": notes, "cliches": total_cliche,
        "dupes": dupes, "repeated_end": repeated_end, "unused": unused,
    }


# ---------------------------------------------------------------- selftest

def craft_reference_text():
    """找 craft-reference.md：仓库里在分类的 _shared/，单技能 zip 里在 skill 的 _shared/。"""
    for base in list(Path(__file__).resolve().parents)[:4]:
        path = base / "_shared" / "craft-reference.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


def craft_entries(text):
    """读参考表第 2 节的三组，返回 [(组, 条目), ...]。"""
    entries = []
    for title, group in (("意象组", "意象"), ("情绪组", "情绪"), ("句式组", "句式")):
        m = re.search(r"^\*\*%s\*\*[:：](.+)$" % title, text, re.M)
        if not m:
            raise ValueError("craft-reference.md 里找不到「%s」那一行" % title)
        items = m.group(1).split("/") if group == "句式" else m.group(1).split()
        entries += [(group, item.strip()) for item in items if item.strip()]
    return entries


def selftest():
    results = []

    def run(lyrics, template=None, extra=()):
        tpl = parse_template(template) if template is not None else None
        return check(parse_lyrics(lyrics), tpl, extra)[1]

    def has_note(result, key, text):
        return any(text in n for n in result["notes"].get(key, []))

    def case(title, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # 用例本身出错也算失败，不让自检崩掉
            ok, detail = False, "%s: %s" % (type(e).__name__, e)
        results.append((title, ok, detail))

    tpl_zf = "主\nxxxxx\nxxxxx\n\n副\nxxxxxxx\nxxxxxxx\n"

    def repeat_sections():
        # 审计 A3：歌词「主歌 1 / 主歌 2」对模板「主」，重复段超字以前被静默跳过、报 0 处
        lyrics = ("主歌 1\n我推开门\n风灌进来\n\n副歌\n今天我出了门\n买了一袋橘子\n\n"
                  "主歌 2\n这一行明显多出好多个字了\n楼下很安静\n\n"
                  "副歌\n今天我出了门\n今天终于出了门啊啊啊啊\n")
        r = run(lyrics, tpl_zf)
        ok = (r["matches"] == [0, 1, 0, 1] and has_note(r, (2, 0), "字数 +7")
              and has_note(r, (3, 1), "字数 +4") and r["problems"] == 2)
        return ok, "matches=%s problems=%d" % (r["matches"], r["problems"])

    def no_ordinal_fallback():
        # 审计 A3：模板 主/预副/副、歌词 主歌 1/副歌，按序号兜底把副歌配到预副，报假超字
        tpl = "主\nxxxxx\nxxxxx\n\n预副\nxxx\nxxx\n\n副\nxxxxxxx\nxxxxxxx\n"
        r = run("主歌 1\n我推开门\n风灌进来\n\n副歌\n今天我出了门\n买了一袋橘子\n", tpl)
        ok = r["matches"] == [0, 2] and r["problems"] == 0 and r["unused"] == ["预副"]
        return ok, "matches=%s problems=%d unused=%s" % (r["matches"], r["problems"], r["unused"])

    def bracket_headers():
        # 审计 A3 / scripts-b-10：【主歌】【副歌】以前被当成歌词行，整首并进「未命名」
        tpl = "主\nxxxxxxxxx\nxxxxxxxxx\n\n副\nxxxxxxxxx\nxxxxxxxxx\n"
        lyrics = ("【主歌】\n我把外套搭在椅背上\n他们说今天是好天气\n\n"
                  "【副歌】\n楼下面馆的灯还亮着\n那条消息我看了六遍\n")
        names = [n for n, _ in parse_lyrics(lyrics)]
        r = run(lyrics, tpl)
        ok = names == ["主歌", "副歌"] and r["matches"] == [0, 1] and r["problems"] == 0
        return ok, "names=%s matches=%s problems=%d" % (names, r["matches"], r["problems"])

    def colon_headers():
        # scripts-b-10：[主歌] 【副歌】 副歌： 的「歌」以前算成行末字，误报「歌×3」
        lyrics = ("[主歌]\n我把外套搭在椅背上\n他们说今天是好天气\n\n【副歌】\n楼下面馆的灯还亮着\n"
                  "那条消息我看了六遍\n\n副歌：\n楼下面馆的灯还亮着\n那条消息我看了六遍\n")
        r = run(lyrics)
        count = len(parse_lyrics(lyrics))
        ok = count == 3 and not any(c == "歌" for c, _ in r["repeated_end"])
        return ok, "sections=%d repeated_end=%s" % (count, r["repeated_end"])

    def aaba():
        # 审计 A3：AABA 的 A、B 本身是段落名，以前不认，报假的字数和停顿问题
        tpl = "A\nxxxxxxxxx\nxxxxxxxxx\n\nB\nxxxxxx\nxxxxxx\n"
        lyrics = ("A\n我把外套搭在椅背上\n楼下面馆的灯还亮着\n\nA\n那条消息我看了六遍\n窗外的车一辆辆过去\n\n"
                  "B\n今天我出了门\n买了一袋橘子\n\nA\n我把外套搭在椅背上\n楼下面馆的灯还亮着\n")
        r = run(lyrics, tpl)
        ok = r["matches"] == [0, 0, 1, 0] and r["problems"] == 0
        return ok, "matches=%s problems=%d" % (r["matches"], r["problems"])

    def ab_suffix_kept():
        # 核查者更正：A/B 后缀不整体去掉。模板只有「副」时「副歌 A」报出来；模板分写 A、B 时分开对
        r1 = run("副歌 A\n今天我出了门\n", "副\nxxxxxxx\n")
        tpl = "副 A\nxxxxxxx\nxxxxxxx\n\n副 B\nxxxxxxx\nxxxxxxx\nxxxxxxx\n"
        lyrics = ("副歌 A\n今天我出了门了\n买了一袋橘子了\n\n"
                  "副歌 B\n今天我出了门了\n买了一袋橘子了\n又走回了家门口\n")
        r2 = run(lyrics, tpl)
        ok = (r1["matches"] == [None] and r1["problems"] == 1
              and r2["matches"] == [0, 1] and r2["problems"] == 0)
        return ok, "only-副: %s/%d; A-B: %s/%d" % (r1["matches"], r1["problems"], r2["matches"], r2["problems"])

    def header_forms():
        headers = ["副歌 A", "副歌A", "A", "B", "[副歌]", "【副歌】", "副歌：", "副歌 1",
                   "副歌二", "Verse 2", "（副歌）", "Pre-Chorus", "主歌 1："]
        lyric_lines = ["很勇敢", "我推开门", "A面的歌", "我说：", "（啦啦啦）", "主角"]
        missed = [h for h in headers if header_name(h) is None]
        eaten = [l for l in lyric_lines if header_name(l) is not None]
        return not missed and not eaten, "missed=%s eaten=%s" % (missed, eaten)

    def fullwidth_space():
        # 审计 A3：模板用全角空格「xxxx　xxxxx」以前被当成段落名，模板整份失效、报 0 处
        tpl = "主\nxxxx　xxxxx\n"
        parsed = parse_template(tpl)
        r = run("主\n这一行明显多出好多个字了啊\n", tpl)
        ok = (parsed == [("主", [(9, [4, 5])])] and has_note(r, (0, 0), "字数 +4")
              and r["problems"] == 2)
        return ok, "parsed=%s problems=%d" % (parsed, r["problems"])

    def bad_input_errors():
        errors = 0
        for fn, arg in ((parse_template, "主\nxxxxx，xxxxx\n"), (parse_template, "主歌\n副歌\n"),
                        (parse_lyrics, "\n\n")):
            try:
                fn(arg)
            except InputError:
                errors += 1
        return errors == 3, "%d/3 raised InputError" % errors

    def extra_fullwidth_comma():
        # 审计 A3：--extra '绿萝，可乐' 以前当成一个词，命中 0 处
        words = split_extra("绿萝，可乐、猫,狗")
        r = run("主\n窗台上的绿萝又长了\n冰箱里只剩一罐可乐\n", extra=split_extra("绿萝，可乐"))
        ok = words == ["绿萝", "可乐", "猫", "狗"] and sum(r["cliches"].values()) == 2
        return ok, "words=%s hits=%d" % (words, sum(r["cliches"].values()))

    def blacklist():
        # 审计 B3：参考表的「这就是最好的」「所有的X都会Y」以前漏查；SKILL.md 与用例的例句必须不命中
        checks = [
            ("句式:这就是最好的" in find_cliches("你说这就是最好的"), "这就是最好的"),
            (ALL_WILL_LABEL in find_cliches("所有的伤都会好起来"), "所有的伤都会好起来"),
            (sorted(find_cliches("所有的伤都会变成星光")) == [ALL_WILL_LABEL, "意象:星光"], "不重复计"),
            ("句式:都会变成" in find_cliches("那些受过的伤 都会变成星光"), "都会变成"),
            (find_cliches("一切都值得") == [], "SKILL.md 例句「一切都值得」"),
            (find_cliches("你已经做得很好了") == [], "用例例句「你已经做得很好了」"),
        ]
        bad = [what for ok, what in checks if not ok]
        return not bad, "failed: %s" % bad if bad else "6/6"

    def craft_sync():
        text = craft_reference_text()
        if text is None:
            return True, "跳过：找不到 _shared/craft-reference.md"
        entries = craft_entries(text)
        missing = []
        for group, item in entries:
            probe = item.replace("X", "那件事").replace("Y", "那件事")
            if not any(h.startswith(group + ":") for h in find_cliches(probe)):
                missing.append(item)
        image = {i for g, i in entries if g == "意象"}
        emotion = {i for g, i in entries if g == "情绪"}
        ok = not missing and image == set(CLICHE_IMAGE) and emotion == set(CLICHE_EMOTION)
        return ok, "%d entries, not covered: %s, image diff: %s, emotion diff: %s" % (
            len(entries), missing, sorted(image ^ set(CLICHE_IMAGE)), sorted(emotion ^ set(CLICHE_EMOTION)))

    def normal():
        r1 = run("主\n我推开了门\n灯还亮着 面馆没关\n", "主\nxxxxx\nxxxx xxxx\n")
        r2 = run("我推开了门\n风灌了进来\n", "xxxxx\nxxxxx\n")  # 都没有段落名：整首逐行比对
        ok = r1["matches"] == [0] and r1["problems"] == 0 and r2["matches"] == [0] and r2["problems"] == 0
        return ok, "named %s/%d, unnamed %s/%d" % (r1["matches"], r1["problems"], r2["matches"], r2["problems"])

    def unnamed_reported():
        r1 = run("我推开了门\n", "主\nxxxxx\n")        # 歌词没写段落名、模板有
        r2 = run("主歌 1\n我推开了门\n", "xxxxx\n")   # 模板没写段落名、歌词有
        ok = r1["matches"] == [None] and r1["problems"] == 1 and r2["matches"] == [None] and r2["problems"] == 1
        return ok, "%s/%d, %s/%d" % (r1["matches"], r1["problems"], r2["matches"], r2["problems"])

    def repeated_template_in_order():
        tpl = "副\nxxxxxxx\nxxxxxxx\n\n副\nxxxxxxx\nxxxxxxx\nxxxxxxx\n"
        lyrics = ("副歌\n今天我出了门了\n买了一袋橘子了\n\n"
                  "副歌\n今天我出了门了\n买了一袋橘子了\n又走回了家门口\n")
        r = run(lyrics, tpl)
        return r["matches"] == [0, 1] and r["problems"] == 0, "matches=%s problems=%d" % (r["matches"], r["problems"])

    def cli():
        me = str(Path(__file__).resolve())
        help_run = subprocess.run([sys.executable, me, "--help"], capture_output=True, text=True)
        missing = subprocess.run([sys.executable, me, "/nonexistent/歌词.txt"], capture_output=True, text=True)
        ok = (help_run.returncode == 0 and "usage" in help_run.stdout
              and missing.returncode == 2 and "读不了" in missing.stderr)
        return ok, "--help rc=%d, missing file rc=%d" % (help_run.returncode, missing.returncode)

    case("A3 重复段、段名写法不同（主歌 1 对模板「主」）", repeat_sections)
    case("A3 不按序号兜底（副歌不再配到预副）", no_ordinal_fallback)
    case("A3 【主歌】【副歌】段落名", bracket_headers)
    case("A3 [主歌] 副歌： 不算歌词行", colon_headers)
    case("A3 AABA 的 A、B 段落名", aaba)
    case("A3 A/B 后缀不整体去掉", ab_suffix_kept)
    case("A3 段落名与歌词行的区分", header_forms)
    case("A3 模板全角空格", fullwidth_space)
    case("A3 模板或歌词读不出内容时报错", bad_input_errors)
    case("A3 --extra 全角逗号、顿号", extra_fullwidth_comma)
    case("B3 黑名单补漏与例句", blacklist)
    case("B3 与 craft-reference 第 2 节同步", craft_sync)
    case("正常稿：段名相同、字数都在 ±1 内", normal)
    case("没有段落名的一方报出来，不硬配", unnamed_reported)
    case("模板同名段落写了两遍时按次序对应", repeated_template_in_order)
    case("--help 退出 0，文件读不了退出 2", cli)

    print("lyric_check.py --selftest")
    for title, ok, detail in results:
        print("  %s  %s%s" % ("PASS" if ok else "FAIL", title, "" if ok else "  (%s)" % detail))
        if ok and detail.startswith("跳过"):
            print("        %s" % detail)
    passed = sum(1 for _, ok, _ in results if ok)
    print("selftest %d/%d pass" % (passed, len(results)))
    return 0 if passed == len(results) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="lyric_check.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("lyrics", nargs="?", help="歌词文件（UTF-8）")
    ap.add_argument("--template", help="字数模板文件（x 表示字）")
    ap.add_argument("--extra", default="", help="额外的禁用词，逗号（全角半角都行）或顿号分隔")
    ap.add_argument("--selftest", action="store_true", help="跑内置回归用例，全过退出 0，否则退出 1")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.lyrics:
        ap.error("需要一个歌词文件；只想跑自检用 --selftest")

    try:
        sections = parse_lyrics(read_text(args.lyrics, "歌词"))
        template = parse_template(read_text(args.template, "模板")) if args.template else None
    except InputError as e:
        print("错误：%s" % e, file=sys.stderr)
        return 2

    out, result = check(sections, template, split_extra(args.extra))
    print("\n".join(out))
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
