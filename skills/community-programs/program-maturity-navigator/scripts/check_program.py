#!/usr/bin/env python3
"""check_program.py — 活动成熟度的两项确定性检查 / two mechanical checks.

只用 Python 标准库。它不判断活动好不好，只回答两个能机械回答的问题：

``stage``   你说的阶段，手上的痕迹撑不撑得住？
            阶段由**留下的痕迹**决定，不由活动叫什么名字决定。办过三次
            「系列读书会」却没有任何记录的，证据只支持 incubation。
            只有真的办过、有人到场的场次才算痕迹：日期晚于今天的记录按输入错误
            处理（排期不是履历），到场 0 人的场次不计入，并给出警告。

``catena``  这个系列是真有顺序，还是把相近题目摆在了一起？
            每一场声明它消费什么（``consumes``）、产出什么（``produces``）。
            除第一场外，每一场必须至少消费一件**前面某场产出**的东西；
            消费不到的那一场就是孤立节点，把它拿掉系列不会有任何损失。
            根对象的 ``external_inputs`` 列出不来自本系列的外部材料：
            消费它们不再警告，但也不算和前面几场接上。

两种输入的全部字段见 ../references/check-program-input.md，``--help`` 也列了一遍。
脚本不认识的字段一律按输入错误处理，免得拼错的键被静默当成"没有"。
备注写进 ``notes``。

用法::

    python3 check_program.py stage  history.json [--today YYYY-MM-DD]
    python3 check_program.py catena catena.json
    python3 check_program.py --selftest

退出状态 0 表示通过，1 表示存在问题，2 表示输入无法解析
（JSON 语法错、缺必填字段、类型不对、未知字段、日期晚于今天）。
警告（WARN）不影响退出状态。
"""

import argparse
import datetime
import difflib
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

# 两种输入认得的全部字段。不在这里的键一律报输入错误（退出 2）：
# 拼错的可选键（例如把 hands_on 写成 hands-on）以前会被静默当成"没有"，
# 结论就错了。说明性的内容写进 notes。
STAGE_ROOT_KEYS = ("claimed", "history", "notes")
STAGE_EVENT_KEYS = ("date", "attendance", "artifacts", "hands_on",
                    "participant_output", "new_faces", "returning_new_faces", "notes")
CATENA_ROOT_KEYS = ("series_question", "sessions", "external_inputs", "final_output", "notes")
CATENA_SESSION_KEYS = ("id", "question", "format", "format_note", "participant_action",
                       "consumes", "produces", "leader", "notes")
FIELD_DOC = "references/check-program-input.md"

FIELDS_HELP = """\
stage 的输入（履历）：
  根对象  claimed（必填）       seed / incubation / catena / workshop / public
          history（必填）       已经办过的场次，数组；排期不算
          notes                 备注，脚本不读
  每一场  date（必填）          YYYY-MM-DD，不能晚于今天
          attendance（必填）    到场人数，非负整数；0 人的场次不计入
          artifacts             这场留下的东西，字符串数组，缺省为空
          hands_on              参与者这场动手做过事：true / false
          participant_output    参与者做出了自己的作品：true / false，或列出作品的字符串数组
          new_faces             本场第一次来的圈外新人数，非负整数
          returning_new_faces   之前以圈外新人身份来过、本场再来的人数，非负整数
          notes                 备注，脚本不读

catena 的输入（系列图）：
  根对象  series_question（必填）  系列总问题
          sessions（必填）         至少 2 场
          external_inputs          不来自本系列任何一场的外部材料，字符串数组
          final_output、notes      说明性字段，脚本不读
  每一场  id（必填）、question、format、participant_action、consumes、produces、
          format_note（format 为 custom 时必填）、leader、notes

不认识的字段按输入错误处理（退出 2）。完整说明与示例：""" + FIELD_DOC


class InputError(Exception):
    pass


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise InputError("读不到 %s：%s" % (path, exc))
    except UnicodeDecodeError:
        raise InputError("%s 不是 UTF-8 编码的文本" % path)
    except json.JSONDecodeError as exc:
        raise InputError("JSON 语法错误，第 %d 行第 %d 列：%s" % (exc.lineno, exc.colno, exc.msg))


def need(obj, key, where, kind=None):
    if key not in obj:
        raise InputError("%s 缺少字段 %r" % (where, key))
    val = obj[key]
    if kind is not None and not isinstance(val, kind):
        raise InputError("%s 的 %r 类型不对" % (where, key))
    return val


def check_keys(obj, allowed, where):
    """不认识的字段直接报错，并给出最接近的正确写法。"""
    unknown = [k for k in obj if k not in allowed]
    if not unknown:
        return
    parts = []
    for key in unknown:
        close = difflib.get_close_matches(key, allowed, n=1, cutoff=0.6)
        parts.append("%r（是不是 %r？）" % (key, close[0]) if close else repr(key))
    raise InputError("%s 有脚本不认识的字段：%s。认得的字段：%s。备注写进 notes，字段表见 %s"
                     % (where, "、".join(parts), "、".join(allowed), FIELD_DOC))


def show(val):
    return json.dumps(val, ensure_ascii=False)


def is_text_list(val):
    return isinstance(val, list) and all(isinstance(x, str) and x.strip() for x in val)


# ---------------------------------------------------------------- stage


def check_date(text, where):
    if not isinstance(text, str):
        raise InputError("%s 的 date 必须是 YYYY-MM-DD 字符串" % where)
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise InputError("%s 的 date %r 不是合法日期" % (where, text))


def count(obj, key, where, required=False):
    """人数字段：非负整数。可选字段省略或写 null 都当作没有记录（0）。"""
    val = obj.get(key)
    if val is None:
        if required:
            raise InputError("%s 缺少字段 %r" % (where, key))
        return 0
    if isinstance(val, bool) or not isinstance(val, int) or val < 0:
        raise InputError("%s 的 %s 必须是非负整数（人数），收到 %s" % (where, key, show(val)))
    return val


def assess(data, today):
    """从 history 推出证据支持的坐标。只有真的办过、有人到场的场次才算痕迹。"""
    history = need(data, "history", "根对象", list)
    notes, warnings, held = [], [], []

    for i, ev in enumerate(history, 1):
        where = "history[%d]" % i
        if not isinstance(ev, dict):
            raise InputError("%s 必须是对象" % where)
        check_keys(ev, STAGE_EVENT_KEYS, where)
        day = check_date(need(ev, "date", where), where)
        if day > today:
            raise InputError("%s 的日期 %s 晚于今天（%s）。history 只写已经办过的场次，排期不是痕迹；"
                             "如果是本机日期不对，用 --today 指定" % (where, ev["date"], today.isoformat()))
        att = count(ev, "attendance", where, required=True)
        artifacts = ev.get("artifacts", [])
        if not is_text_list(artifacts):
            raise InputError("%s 的 artifacts 必须是字符串数组，逐件写这场留下的东西" % where)
        hands_on = ev.get("hands_on")
        if hands_on is not None and not isinstance(hands_on, bool):
            raise InputError("%s 的 hands_on 只能写 true 或 false，收到 %s" % (where, show(hands_on)))
        output = ev.get("participant_output")
        if output is not None and not isinstance(output, bool) and not is_text_list(output):
            raise InputError("%s 的 participant_output 只能写 true / false，或者列出作品的字符串数组，收到 %s"
                             % (where, show(output)))
        new = count(ev, "new_faces", where)
        back = count(ev, "returning_new_faces", where)
        if new + back > att:
            raise InputError("%s 的 new_faces（%d）加 returning_new_faces（%d）超过了到场人数 attendance（%d）："
                             "两者都是本场到场者的一部分，互不重叠" % (where, new, back, att))
        if att == 0:
            warnings.append("%s（%s）到场 0 人，不算办过的场次，不计入" % (where, ev["date"]))
            continue
        held.append({"date": ev["date"], "artifacts": artifacts,
                     "hands_on": bool(hands_on), "output": bool(output),
                     "new_faces": new, "returning_new_faces": back})

    n = len(held)
    bare = [e["date"] for e in held if not e["artifacts"]]

    # 主干
    if n == 0:
        trunk = 0
        notes.append("没有已发生的活动，证据只支持 seed")
    elif n < 3 or bare:
        trunk = 1
        if n < 3:
            notes.append("只办过 %d 次，不足 3 次" % n)
        if bare:
            notes.append("这几次没有留下任何产物：%s" % "、".join(bare))
    else:
        trunk = 2

    # 深度轴
    depth = 0
    if any(e["output"] for e in held):
        depth = 2
    elif any(e["hands_on"] for e in held):
        depth = 1
    if depth == 0:
        notes.append("没有任何一次参与者动手做过事，深度轴为 0")

    # 广度轴
    breadth = 0
    if any(e["returning_new_faces"] > 0 for e in held):
        breadth = 2
    elif any(e["new_faces"] > 0 for e in held):
        breadth = 1
    if breadth == 0:
        notes.append("没有记录到圈外新人，广度轴为 0")
    elif breadth == 1:
        notes.append("有新人来过但没有再来第二次，广度轴停在 1")

    return trunk, depth, breadth, held, notes, warnings


def run_stage(data, out, today=None):
    if today is None:
        today = datetime.date.today()
    check_keys(data, STAGE_ROOT_KEYS, "根对象")
    claimed = need(data, "claimed", "根对象", str)
    if claimed not in CLAIMS:
        raise InputError("claimed 必须是 %s 之一" % "、".join(sorted(CLAIMS)))

    trunk, depth, breadth, events, notes, warnings = assess(data, today)
    need_t, need_d, need_b = CLAIMS[claimed]

    for w in warnings:
        out.write("WARN  %s\n" % w)
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
    check_keys(data, CATENA_ROOT_KEYS, "根对象")
    series_q = need(data, "series_question", "根对象", str)
    sessions = need(data, "sessions", "根对象", list)
    if not series_q.strip():
        raise InputError("series_question 不能为空")
    if len(sessions) < 2:
        raise InputError("sessions 至少要有 2 场，否则不成其为系列")
    external = data.get("external_inputs", [])
    if not is_text_list(external):
        raise InputError("external_inputs 必须是字符串数组，逐件写不来自本系列任何一场的外部材料")
    external = set(external)

    errors, warnings = [], []
    seen = set()
    produced_before = set()      # 前面各场累积的产物
    consumed_any = set()         # 被后续消费过的产物
    formats = []
    outputs = []                 # 每一场的 (id, produces)，查悬空产物用

    for i, s in enumerate(sessions):
        where = "sessions[%d]" % (i + 1)
        if not isinstance(s, dict):
            raise InputError("%s 必须是对象" % where)
        check_keys(s, CATENA_SESSION_KEYS, where)
        sid = need(s, "id", where, str)
        if sid in seen:
            errors.append("%s 的 id %r 重复" % (where, sid))
        seen.add(sid)

        for field in ("question", "participant_action"):
            val = s.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append("%s（%s）的 %s 不能为空" % (where, sid, field))

        fmt = s.get("format")
        if fmt is not None and not isinstance(fmt, str):
            raise InputError("%s 的 format 必须是字符串，取值：%s；收到 %s"
                             % (where, "、".join(sorted(FORMATS)), show(fmt)))
        note = s.get("format_note", "")
        if not isinstance(note, str):
            raise InputError("%s 的 format_note 必须是字符串" % where)
        if fmt not in FORMATS:
            errors.append("%s（%s）的 format %r 不在允许集合：%s"
                          % (where, sid, fmt, "、".join(sorted(FORMATS))))
        else:
            formats.append(fmt)
            if fmt == "custom" and not note.strip():
                errors.append("%s（%s）用了 custom，必须写 format_note 说明规则" % (where, sid))

        consumes = s.get("consumes", [])
        produces = s.get("produces", [])
        for field, val in (("consumes", consumes), ("produces", produces)):
            if not is_text_list(val):
                raise InputError("%s 的 %s 必须是字符串数组，同一件产物每处写同一串字符" % (where, field))
        if not produces:
            errors.append("%s（%s）没有产出任何东西，下一场无从接手" % (where, sid))

        if i > 0:
            linked = [c for c in consumes if c in produced_before]
            if not linked:
                errors.append(
                    "%s（%s）是孤立的：它消费的 %s 没有一件来自前面几场%s。"
                    "把这一场拿掉，系列不会有任何损失"
                    % (where, sid, consumes if consumes else "（什么都没写）",
                       "（external_inputs 里的外部材料不算接上）"
                       if any(c in external for c in consumes) else "")
                )
            consumed_any.update(linked)
            for c in consumes:
                if c not in produced_before and c not in external:
                    warnings.append("%s（%s）消费的 %r 不是前面任何一场的产物，"
                                    "如果它来自外部材料请写进 external_inputs"
                                    % (where, sid, c))
        produced_before.update(produces)
        outputs.append((sid, produces))

    # 悬空产物：除最后一场外，产出了却没人接手
    for i, (sid, produces) in enumerate(outputs[:-1]):
        for p in produces:
            if p not in consumed_any:
                warnings.append("第 %d 场（%s）的产物 %r 后面没有任何一场用到"
                                % (i + 1, sid, p))

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

# 自检里的"今天"是固定的，结果不随运行日期变化。
SELFTEST_TODAY = datetime.date(2026, 6, 30)

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


def with_event(base, index, claimed=None, drop=(), **fields):
    """复制一份履历，改其中一场。自检用。"""
    data = json.loads(json.dumps(base))
    ev = data["history"][index]
    for key in drop:
        ev.pop(key, None)
    ev.update(fields)
    if claimed:
        data["claimed"] = claimed
    return data


SELFTEST_STAGE_TYPO = with_event(SELFTEST_STAGE_OK, 0, claimed="workshop", **{"hands-on": True})
SELFTEST_STAGE_GUESSED = with_event(
    with_event(SELFTEST_STAGE_OK, 1, drop=("new_faces",), newcomers=2),
    2, claimed="public", drop=("new_faces", "returning_new_faces"),
    newcomers=1, returning_newcomers=1)
SELFTEST_STAGE_FUTURE = {
    "claimed": "catena",
    "history": [
        {"date": "2027-01-10", "attendance": 6, "artifacts": ["共同疑问三条"]},
        {"date": "2027-02-10", "attendance": 5, "artifacts": ["分歧清单"]},
        {"date": "2027-03-10", "attendance": 7, "artifacts": ["读法对照表"]},
    ],
}
SELFTEST_STAGE_ZERO = {
    "claimed": "catena",
    "history": [
        {"date": "2026-03-14", "attendance": 0, "artifacts": ["共同疑问三条"]},
        {"date": "2026-04-11", "attendance": 0, "artifacts": ["分歧清单"]},
        {"date": "2026-05-09", "attendance": 0, "artifacts": ["读法对照表"]},
    ],
}
SELFTEST_STAGE_WORDS = with_event(SELFTEST_STAGE_OK, 1, claimed="public", new_faces="两个")
SELFTEST_STAGE_LISTNUM = with_event(SELFTEST_STAGE_OK, 2, claimed="public", returning_new_faces=[1])
SELFTEST_STAGE_OVERCOUNT = with_event(SELFTEST_STAGE_OK, 1, new_faces=9)
SELFTEST_STAGE_NOTES = dict(with_event(SELFTEST_STAGE_OK, 0, notes="第一次借的是图书馆小教室"),
                            notes="数字来自签到表")

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


def with_session(base, index, root=None, drop=(), **fields):
    """复制一份系列图，改其中一场或根对象。自检用。"""
    data = json.loads(json.dumps(base))
    s = data["sessions"][index]
    for key in drop:
        s.pop(key, None)
    s.update(fields)
    data.update(root or {})
    return data


SELFTEST_CATENA_BADFMT = with_session(SELFTEST_CATENA_OK, 1, format=["seminar"])
SELFTEST_CATENA_EXT = with_session(SELFTEST_CATENA_OK, 1, root={"external_inputs": ["原书第二章"]},
                                   consumes=["共同疑问三条", "原书第二章"])
SELFTEST_CATENA_EXT_ONLY = with_session(SELFTEST_CATENA_OK, 1, root={"external_inputs": ["原书第二章"]},
                                        consumes=["原书第二章"])
SELFTEST_CATENA_EXT_STR = with_session(SELFTEST_CATENA_OK, 1, root={"external_inputs": "原书第二章"})
SELFTEST_CATENA_TYPO = with_session(SELFTEST_CATENA_OK, 2, drop=("consumes",), consume=["分歧清单"])
SELFTEST_CATENA_NESTED = with_session(SELFTEST_CATENA_OK, 2, consumes=[["分歧清单"]])
SELFTEST_CATENA_TEMPLATE = with_session(SELFTEST_CATENA_OK, 0, root={"final_output": "读法对照表"},
                                        leader="小林", notes="模板里「带领者」一栏写进 leader")


def selftest(out):
    import contextlib
    import io

    def stage(data, buf):
        return run_stage(data, buf, SELFTEST_TODAY)

    ok = True
    cases = [
        # (说明, 函数, 输入, 期望退出码, 输出里必须有, 输出里不能有)
        ("stage：办过三次但没记录，声称 catena → 应拦下", stage, SELFTEST_STAGE_BAD, 1, "补上产物记录", None),
        ("stage：三次都有产物，声称 catena → 应通过", stage, SELFTEST_STAGE_OK, 0, "证据支持", None),
        ("stage：同一份记录声称 workshop → 应拦下（深度轴 0）", stage,
         SELFTEST_STAGE_WORKSHOP, 1, "参与者动手", None),
        ("stage：新人来过但没再来，声称 public → 应拦下", stage,
         SELFTEST_STAGE_PUBLIC_1, 1, "没有再来第二次", None),
        ("stage：新人再来了，声称 public → 应通过", stage,
         dict(SELFTEST_STAGE_OK, claimed="public"), 0, "证据支持", None),
        ("stage：键名拼成 hands-on → 报输入错误并提示 hands_on", stage,
         SELFTEST_STAGE_TYPO, 2, "'hands_on'", None),
        ("stage：用猜出来的 newcomers / returning_newcomers → 报输入错误", stage,
         SELFTEST_STAGE_GUESSED, 2, "newcomers", None),
        ("stage：日期晚于今天（排期写进了履历）→ 报输入错误", stage,
         SELFTEST_STAGE_FUTURE, 2, "晚于今天", None),
        ("stage：三场到场都是 0 → 不计入，声称 catena 应拦下", stage,
         SELFTEST_STAGE_ZERO, 1, "到场 0 人", "证据支持 catena"),
        ("stage：new_faces 写成「两个」→ 报输入错误，不崩溃", stage,
         SELFTEST_STAGE_WORDS, 2, "非负整数", None),
        ("stage：returning_new_faces 写成数组 → 报输入错误，不崩溃", stage,
         SELFTEST_STAGE_LISTNUM, 2, "非负整数", None),
        ("stage：新人数超过到场人数 → 报输入错误", stage,
         SELFTEST_STAGE_OVERCOUNT, 2, "超过了到场人数", None),
        ("stage：带 notes 备注的正常履历 → 应通过", stage, SELFTEST_STAGE_NOTES, 0, "证据支持", None),
        ("catena：三场首尾相接 → 应通过", run_catena, SELFTEST_CATENA_OK, 0, "首尾相接", None),
        ("catena：两场各读各的 → 应报孤立", run_catena, SELFTEST_CATENA_ORPHAN, 1, "孤立", None),
        ("catena：format 写成数组 → 报输入错误，不崩溃", run_catena,
         SELFTEST_CATENA_BADFMT, 2, "format 必须是字符串", None),
        ("catena：外部材料写进 external_inputs → 不再警告", run_catena,
         SELFTEST_CATENA_EXT, 0, "首尾相接", "原书第二章"),
        ("catena：只消费外部材料的一场 → 仍然孤立", run_catena,
         SELFTEST_CATENA_EXT_ONLY, 1, "外部材料不算接上", None),
        ("catena：external_inputs 写成字符串 → 报输入错误", run_catena,
         SELFTEST_CATENA_EXT_STR, 2, "external_inputs", None),
        ("catena：键名拼成 consume → 报输入错误并提示 consumes", run_catena,
         SELFTEST_CATENA_TYPO, 2, "'consumes'", None),
        ("catena：consumes 里套了数组 → 报输入错误，不崩溃", run_catena,
         SELFTEST_CATENA_NESTED, 2, "consumes 必须是字符串数组", None),
        ("catena：模板里的带领者、最后形成什么写进 leader / final_output → 应通过", run_catena,
         SELFTEST_CATENA_TEMPLATE, 0, "首尾相接", None),
    ]
    for desc, fn, data, want, needle, absent in cases:
        buf = io.StringIO()
        try:
            code = fn(json.loads(json.dumps(data)), buf)
        except InputError as exc:
            buf.write(str(exc))
            code = 2
        text = buf.getvalue()
        if code == want and needle in text and (absent is None or absent not in text):
            out.write("  pass  %s\n" % desc)
        else:
            ok = False
            out.write("  FAIL  %s（退出 %d，期望 %d）\n%s\n" % (desc, code, want, text))

    # 命令行：--help 打印用法和字段表并以 0 退出；--today 写错按输入错误处理
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            main(["--help"])
        code = None
    except SystemExit as exc:
        code = exc.code
    if code == 0 and "returning_new_faces" in buf.getvalue():
        out.write("  pass  --help 打印用法与字段表，退出 0\n")
    else:
        ok = False
        out.write("  FAIL  --help（退出 %r）\n" % code)
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        code = main(["stage", "--today", "2026-02-30", "不存在的文件.json"])
    if code == 2 and "--today" in buf.getvalue():
        out.write("  pass  --today 不是合法日期 → 输入错误，退出 2\n")
    else:
        ok = False
        out.write("  FAIL  --today 校验（退出 %r）\n%s\n" % (code, buf.getvalue()))

    out.write("自检%s\n" % ("通过" if ok else "未通过"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="活动成熟度的两项确定性检查",
                                 epilog=FIELDS_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=["stage", "catena"],
                    help="stage 查阶段与痕迹是否相符；catena 查系列有没有顺序")
    ap.add_argument("file", nargs="?", help="输入 JSON")
    ap.add_argument("--today", metavar="YYYY-MM-DD",
                    help="stage 用：把「今天」固定为这一天，晚于它的场次按排期报错；默认取本机日期")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检并退出")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(sys.stdout)
    if not args.mode or not args.file:
        ap.error("需要 mode 与输入文件，或者用 --selftest")

    try:
        today = datetime.date.today()
        if args.today is not None:
            try:
                today = datetime.date.fromisoformat(args.today)
            except ValueError:
                raise InputError("--today %r 不是合法的 YYYY-MM-DD 日期" % args.today)
        data = load(args.file)
        if not isinstance(data, dict):
            raise InputError("顶层必须是一个 JSON 对象")
        if args.mode == "stage":
            return run_stage(data, sys.stdout, today)
        return run_catena(data, sys.stdout)
    except InputError as exc:
        sys.stderr.write("输入有问题：%s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
