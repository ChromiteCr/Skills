#!/usr/bin/env python3
"""check_program.py — 活动成熟度的两项确定性检查 / two mechanical checks.

只用 Python 标准库。它不判断活动好不好，只回答两个能机械回答的问题：

``stage``   你说的阶段，手上的痕迹撑不撑得住？
            阶段由**留下的痕迹**决定，不由活动叫什么名字决定。办过三次
            「系列读书会」却没有任何记录的，证据只支持 incubation。

``catena``  这个系列是真有顺序，还是把相近题目摆在了一起？
            每一场声明它消费什么（``consumes``）、产出什么（``produces``）。
            除第一场外，每一场必须至少消费一件**前面某场产出**的东西；
            消费不到的那一场就是孤立节点，把它拿掉系列不会有任何损失。

用法::

    python3 check_program.py stage  history.json
    python3 check_program.py catena catena.json
    python3 check_program.py --selftest

退出状态 0 表示通过，1 表示存在问题，2 表示输入无法解析。
警告（WARN）不影响退出状态。
"""

import argparse
import datetime
import json
import sys

TRUNK = ["seed", "incubation", "catena"]
CLAIMS = {
    # claimed -> (最低主干, 最低深度, 最低广度)
    #
    # 两个轴的门槛不对称，这是有意的：
    #   深度 1（有人动手过一次）足以证明这个形式跑得起来——动手了就是动手了；
    #   广度 1（来过一个圈外新人）什么也证明不了，来一次可能只是路过。
    #   陌生人**再来第二次**才是信号，所以 public 要求广度 2。
    "seed": (0, 0, 0),
    "incubation": (1, 0, 0),
    "catena": (2, 0, 0),
    "workshop": (2, 1, 0),
    "public": (2, 0, 2),
}
FORMATS = {
    "lecture", "seminar", "reading-group", "workshop",
    "public-program", "custom",
}


class InputError(Exception):
    pass


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise InputError("读不到 %s：%s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise InputError("JSON 语法错误，第 %d 行第 %d 列：%s" % (exc.lineno, exc.colno, exc.msg))


def need(obj, key, where, kind=None):
    if key not in obj:
        raise InputError("%s 缺少字段 %r" % (where, key))
    val = obj[key]
    if kind is not None and not isinstance(val, kind):
        raise InputError("%s 的 %r 类型不对" % (where, key))
    return val


# ---------------------------------------------------------------- stage


def check_date(text, where):
    if not isinstance(text, str):
        raise InputError("%s 的 date 必须是 YYYY-MM-DD 字符串" % where)
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise InputError("%s 的 date %r 不是合法日期" % (where, text))


def assess(data):
    """从 history 推出证据支持的坐标。"""
    history = need(data, "history", "根对象", list)
    problems, notes = [], []

    events = []
    for i, ev in enumerate(history, 1):
        where = "history[%d]" % i
        if not isinstance(ev, dict):
            raise InputError("%s 必须是对象" % where)
        check_date(need(ev, "date", where), where)
        att = need(ev, "attendance", where)
        if not isinstance(att, int) or isinstance(att, bool) or att < 0:
            raise InputError("%s 的 attendance 必须是非负整数" % where)
        ev.setdefault("artifacts", [])
        if not isinstance(ev["artifacts"], list):
            raise InputError("%s 的 artifacts 必须是数组" % where)
        events.append(ev)

    n = len(events)
    with_artifacts = [e for e in events if e["artifacts"]]

    # 主干
    if n == 0:
        trunk = 0
        notes.append("没有已发生的活动，证据只支持 seed")
    elif n < 3 or len(with_artifacts) < n:
        trunk = 1
        if n < 3:
            notes.append("只办过 %d 次，不足 3 次" % n)
        if len(with_artifacts) < n:
            bare = [e["date"] for e in events if not e["artifacts"]]
            notes.append("这几次没有留下任何产物：%s" % "、".join(bare))
    else:
        trunk = 2

    # 深度轴
    depth = 0
    if any(e.get("participant_output") for e in events):
        depth = 2
    elif any(e.get("hands_on") for e in events):
        depth = 1
    if depth == 0:
        notes.append("没有任何一次参与者动手做过事，深度轴为 0")

    # 广度轴
    breadth = 0
    if any(int(e.get("returning_new_faces") or 0) > 0 for e in events):
        breadth = 2
    elif any(int(e.get("new_faces") or 0) > 0 for e in events):
        breadth = 1
    if breadth == 0:
        notes.append("没有记录到圈外新人，广度轴为 0")
    elif breadth == 1:
        notes.append("有新人来过但没有再来第二次，广度轴停在 1")

    return trunk, depth, breadth, events, notes, problems


def run_stage(data, out):
    claimed = need(data, "claimed", "根对象", str)
    if claimed not in CLAIMS:
        raise InputError("claimed 必须是 %s 之一" % "、".join(sorted(CLAIMS)))

    trunk, depth, breadth, events, notes, _ = assess(data)
    need_t, need_d, need_b = CLAIMS[claimed]

    out.write("已发生的活动：%d 次\n" % len(events))
    out.write("证据支持的坐标：主干 %s ／ 深度 %d ／ 广度 %d\n"
              % (TRUNK[trunk], depth, breadth))
    out.write("你声称的阶段：%s（需要 主干 %s ／ 深度 %d ／ 广度 %d）\n"
              % (claimed, TRUNK[need_t], need_d, need_b))
    for note in notes:
        out.write("  · %s\n" % note)

    gaps = []
    if trunk < need_t:
        gaps.append("主干差 %s → %s" % (TRUNK[trunk], TRUNK[need_t]))
        if need_t == 2:
            if len(events) < 3:
                gaps.append("  还需要办满 3 次（现在 %d 次）" % len(events))
            bare = [e["date"] for e in events if not e["artifacts"]]
            if bare:
                gaps.append("  这几次要补上产物记录：%s" % "、".join(bare))
    if depth < need_d:
        gaps.append("深度差：还没有任何一次参与者动手做过事")
    if breadth < need_b:
        if breadth == 0:
            gaps.append("广度差：还没有圈外新人来过")
        else:
            gaps.append("广度差：新人来过但没有再来第二次")

    if gaps:
        out.write("\n证据不足，不能按 %s 往下走：\n" % claimed)
        for g in gaps:
            out.write("  %s\n" % g)
        out.write("\n阶段由留下的痕迹决定，不由活动叫什么决定。\n")
        return 1

    out.write("\n证据支持 %s。这只说明位置判对了，不说明活动办得好。\n" % claimed)
    return 0


# ---------------------------------------------------------------- catena


def run_catena(data, out):
    series_q = need(data, "series_question", "根对象", str)
    sessions = need(data, "sessions", "根对象", list)
    if not series_q.strip():
        raise InputError("series_question 不能为空")
    if len(sessions) < 2:
        raise InputError("sessions 至少要有 2 场，否则不成其为系列")

    errors, warnings = [], []
    seen = set()
    produced_before = set()      # 前面各场累积的产物
    consumed_any = set()         # 被后续消费过的产物
    formats = []

    for i, s in enumerate(sessions):
        where = "sessions[%d]" % (i + 1)
        if not isinstance(s, dict):
            raise InputError("%s 必须是对象" % where)
        sid = need(s, "id", where, str)
        if sid in seen:
            errors.append("%s 的 id %r 重复" % (where, sid))
        seen.add(sid)

        for field in ("question", "participant_action"):
            val = s.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append("%s（%s）的 %s 不能为空" % (where, sid, field))

        fmt = s.get("format")
        if fmt not in FORMATS:
            errors.append("%s（%s）的 format %r 不在允许集合：%s"
                          % (where, sid, fmt, "、".join(sorted(FORMATS))))
        else:
            formats.append(fmt)
            if fmt == "custom" and not str(s.get("format_note", "")).strip():
                errors.append("%s（%s）用了 custom，必须写 format_note 说明规则" % (where, sid))

        consumes = s.get("consumes", [])
        produces = s.get("produces", [])
        if not isinstance(consumes, list) or not isinstance(produces, list):
            raise InputError("%s 的 consumes / produces 必须是数组" % where)
        if not produces:
            errors.append("%s（%s）没有产出任何东西，下一场无从接手" % (where, sid))

        if i > 0:
            linked = [c for c in consumes if c in produced_before]
            if not linked:
                errors.append(
                    "%s（%s）是孤立的：它消费的 %s 没有一件来自前面几场。"
                    "把这一场拿掉，系列不会有任何损失"
                    % (where, sid, consumes if consumes else "（什么都没写）")
                )
            consumed_any.update(linked)
            for c in consumes:
                if c not in produced_before:
                    warnings.append("%s（%s）消费的 %r 不是前面任何一场的产物，"
                                    "如果它来自外部材料请写进 external_inputs"
                                    % (where, sid, c))
        produced_before.update(produces)

    # 悬空产物：除最后一场外，产出了却没人接手
    for i, s in enumerate(sessions[:-1]):
        for p in s.get("produces", []):
            if p not in consumed_any:
                warnings.append("第 %d 场（%s）的产物 %r 后面没有任何一场用到"
                                % (i + 1, s.get("id"), p))

    if formats and set(formats) == {"lecture"}:
        warnings.append("整个系列参与者只在听。形式该由参与者需要做什么决定，"
                        "全程 lecture 通常说明这一步没想过")

    for w in warnings:
        out.write("WARN  %s\n" % w)
    for e in errors:
        out.write("ERROR %s\n" % e)

    if errors:
        out.write("\n%d 处问题。有顺序不等于按时间排好，而是后一场用得上前一场的产物。\n"
                  % len(errors))
        return 1
    out.write("OK    %d 场首尾相接，每一场都用得上前面的产物。\n" % len(sessions))
    out.write("      结构成立不代表题目选得对，那是判断，不是检查。\n")
    return 0


# ---------------------------------------------------------------- selftest


SELFTEST_STAGE_BAD = {
    "claimed": "catena",
    "history": [
        {"date": "2026-03-14", "attendance": 6, "artifacts": []},
        {"date": "2026-04-11", "attendance": 5, "artifacts": []},
        {"date": "2026-05-09", "attendance": 7, "artifacts": []},
    ],
}
SELFTEST_STAGE_OK = {
    "claimed": "catena",
    "history": [
        {"date": "2026-03-14", "attendance": 6, "artifacts": ["共同疑问三条"]},
        {"date": "2026-04-11", "attendance": 5, "artifacts": ["分歧清单"], "new_faces": 2},
        {"date": "2026-05-09", "attendance": 7, "artifacts": ["读法对照表"],
         "new_faces": 1, "returning_new_faces": 1},
    ],
}
SELFTEST_STAGE_WORKSHOP = dict(SELFTEST_STAGE_OK, claimed="workshop")
SELFTEST_STAGE_PUBLIC_1 = {
    "claimed": "public",
    "history": [
        {"date": "2026-03-14", "attendance": 6, "artifacts": ["共同疑问三条"]},
        {"date": "2026-04-11", "attendance": 5, "artifacts": ["分歧清单"], "new_faces": 2},
        {"date": "2026-05-09", "attendance": 7, "artifacts": ["读法对照表"], "new_faces": 1},
    ],
}
SELFTEST_CATENA_OK = {
    "series_question": "我们读的这几本书，对「记忆」的处理有什么不同？",
    "sessions": [
        {"id": "s1", "question": "各自读到了什么？", "format": "reading-group",
         "participant_action": "带一段自己划的原文来读",
         "consumes": [], "produces": ["共同疑问三条"]},
        {"id": "s2", "question": "这三条疑问里，哪一条我们意见不一致？", "format": "seminar",
         "participant_action": "提前就三条疑问各写一句立场",
         "consumes": ["共同疑问三条"], "produces": ["分歧清单"]},
        {"id": "s3", "question": "分歧来自读法还是来自文本？", "format": "seminar",
         "participant_action": "拿分歧清单回到原文找依据",
         "consumes": ["分歧清单"], "produces": ["读法对照表"]},
    ],
}
SELFTEST_CATENA_ORPHAN = {
    "series_question": "同上",
    "sessions": [
        {"id": "s1", "question": "A", "format": "reading-group",
         "participant_action": "读", "consumes": [], "produces": ["笔记 A"]},
        {"id": "s2", "question": "B", "format": "reading-group",
         "participant_action": "读", "consumes": [], "produces": ["笔记 B"]},
    ],
}


def selftest(out):
    import io

    ok = True
    cases = [
        ("stage：办过三次但没记录，声称 catena → 应拦下", run_stage, SELFTEST_STAGE_BAD, 1, "补上产物记录"),
        ("stage：三次都有产物，声称 catena → 应通过", run_stage, SELFTEST_STAGE_OK, 0, "证据支持"),
        ("stage：同一份记录声称 workshop → 应拦下（深度轴 0）", run_stage,
         SELFTEST_STAGE_WORKSHOP, 1, "参与者动手"),
        ("stage：新人来过但没再来，声称 public → 应拦下", run_stage,
         SELFTEST_STAGE_PUBLIC_1, 1, "没有再来第二次"),
        ("stage：新人再来了，声称 public → 应通过", run_stage,
         dict(SELFTEST_STAGE_OK, claimed="public"), 0, "证据支持"),
        ("catena：三场首尾相接 → 应通过", run_catena, SELFTEST_CATENA_OK, 0, "首尾相接"),
        ("catena：两场各读各的 → 应报孤立", run_catena, SELFTEST_CATENA_ORPHAN, 1, "孤立"),
    ]
    for desc, fn, data, want, needle in cases:
        buf = io.StringIO()
        try:
            code = fn(json.loads(json.dumps(data)), buf)
        except InputError as exc:
            buf.write(str(exc))
            code = 2
        text = buf.getvalue()
        if code == want and needle in text:
            out.write("  pass  %s\n" % desc)
        else:
            ok = False
            out.write("  FAIL  %s（退出 %d，期望 %d）\n%s\n" % (desc, code, want, text))
    out.write("自检%s\n" % ("通过" if ok else "未通过"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="活动成熟度的两项确定性检查")
    ap.add_argument("mode", nargs="?", choices=["stage", "catena"],
                    help="stage 查阶段与痕迹是否相符；catena 查系列有没有顺序")
    ap.add_argument("file", nargs="?", help="输入 JSON")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检并退出")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(sys.stdout)
    if not args.mode or not args.file:
        ap.error("需要 mode 与输入文件，或者用 --selftest")

    try:
        data = load(args.file)
        if not isinstance(data, dict):
            raise InputError("顶层必须是一个 JSON 对象")
        return (run_stage if args.mode == "stage" else run_catena)(data, sys.stdout)
    except InputError as exc:
        sys.stderr.write("输入有问题：%s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
