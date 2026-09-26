# 脚本输入 / check_program.py input

`scripts/check_program.py` 的两个子命令各读一份 JSON。**字段名照抄下表。**
脚本不认识的字段一律按输入错误处理（退出 2），并提示最接近的正确写法，
不会静默忽略：以前把 `hands_on` 拼成 `hands-on`，脚本会当成"没动手"，结论就错了。
备注、说明写进 `notes`。

退出码：0 通过；1 存在问题（证据不足、孤立场次等）；2 输入无法解析
（JSON 语法错、缺必填字段、类型不对、未知字段、日期晚于今天）。WARN 不影响退出码。

## stage：履历

```json
{
  "claimed": "catena",
  "history": [
    {"date": "2026-03-14", "attendance": 6, "artifacts": ["共同疑问三条"]},
    {"date": "2026-04-11", "attendance": 5, "artifacts": ["分歧清单"], "new_faces": 2},
    {"date": "2026-05-09", "attendance": 7, "artifacts": ["读法对照表"],
     "hands_on": true, "new_faces": 1, "returning_new_faces": 1,
     "notes": "再来的是 4 月那两位之一"}
  ]
}
```

| 字段 | 位置 | 必填 | 类型 | 含义 |
|---|---|---|---|---|
| `claimed` | 根 | 是 | 字符串 | 使用者声称的阶段：`seed` 种子 / `incubation` 孵化 / `catena` 系列 / `workshop` 走深度轴 / `public` 走广度轴 |
| `history` | 根 | 是 | 数组 | 已经办过的场次，每场一个对象。排期不算，只写真的办过的 |
| `date` | 每场 | 是 | `YYYY-MM-DD` | 办的日期。晚于今天按输入错误处理；本机日期不对时用 `--today` 指定 |
| `attendance` | 每场 | 是 | 非负整数 | 到场人数。0 人的场次不计入，给 WARN |
| `artifacts` | 每场 | 否 | 字符串数组 | 这场留下的东西，逐件写（笔记、清单、照片……）。缺省为空 |
| `hands_on` | 每场 | 否 | `true` / `false` | 参与者这场动手做过事，不只是听和讨论 |
| `participant_output` | 每场 | 否 | `true` / `false`，或字符串数组 | 参与者做出了自己的作品；写数组时逐件列出 |
| `new_faces` | 每场 | 否 | 非负整数 | 本场第一次来的圈外新人数 |
| `returning_new_faces` | 每场 | 否 | 非负整数 | 之前以圈外新人身份来过、本场再来的人数 |
| `notes` | 根或每场 | 否 | 任意 | 备注，脚本不读 |

- 可选字段省略、写 `null`，都当作没有记录。
- `new_faces` 和 `returning_new_faces` 是本场到场者里互不重叠的两部分，加起来不能超过 `attendance`。
- 判定规则见 SKILL.md 第二节。脚本只核痕迹，闸门里要人判断的条目它不管。

## catena：系列图

各字段对应 `artifact-templates.md` 里 Catena Map 的各栏。

```json
{
  "series_question": "我们读的这几本书，对「记忆」的处理有什么不同？",
  "external_inputs": ["原书第二章"],
  "sessions": [
    {"id": "s1", "question": "各自读到了什么？", "format": "reading-group",
     "participant_action": "带一段自己划的原文来读",
     "consumes": [], "produces": ["共同疑问三条"], "leader": "小林"},
    {"id": "s2", "question": "这三条疑问里，哪一条我们意见不一致？", "format": "seminar",
     "participant_action": "对照原书第二章，就三条疑问各写一句立场",
     "consumes": ["共同疑问三条", "原书第二章"], "produces": ["分歧清单"]}
  ],
  "final_output": "一份分歧清单"
}
```

| 字段 | 位置 | 必填 | 类型 | Catena Map 里的栏 | 含义 |
|---|---|---|---|---|---|
| `series_question` | 根 | 是 | 字符串 | 系列总问题 | 一个问题，不是一个主题 |
| `external_inputs` | 根 | 否 | 字符串数组 | 外部输入 | 不来自本系列任何一场的材料。消费它们不再 WARN，但不算和前面几场接上 |
| `final_output` | 根 | 否 | 任意 | 整个系列最后形成什么 | 说明性，脚本不读 |
| `sessions` | 根 | 是 | 数组，至少 2 场 | 每一场 | |
| `id` | 每场 | 是 | 字符串 | id | 不能重复 |
| `question` | 每场 | 是 | 字符串 | 子问题 | 空着算问题（退出 1） |
| `format` | 每场 | 是 | 字符串 | 形式 | `lecture` / `seminar` / `reading-group` / `workshop` / `public-program` / `custom`，见 `format-selection.md` |
| `format_note` | 每场 | `custom` 时必填 | 字符串 | | 本地形式的规则，见 `local-vocabulary.md` |
| `participant_action` | 每场 | 是 | 字符串 | 参与者要做的事 | 空着算问题（退出 1） |
| `consumes` | 每场 | 否 | 字符串数组 | consumes | 除第一场外，至少一件要来自前面某场的 `produces` |
| `produces` | 每场 | 是 | 字符串数组 | produces | 空数组算问题（退出 1） |
| `leader` | 每场 | 否 | 任意 | 带领者 | 说明性，脚本不读 |
| `notes` | 根或每场 | 否 | 任意 | | 备注，脚本不读 |

`consumes`、`produces`、`external_inputs` 都靠**字面**匹配：同一件东西每处写同一串字符。
