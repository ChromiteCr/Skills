# activity-list-optimizer

## Case 1: 描述超限，需要压缩

**输入 / Input**

学生贴入一条活动描述（约 210 字符）：

> Responsible for leading a team of 18 members in the FRC robotics competition, where I was in charge of writing the Java control code and successfully improved our autonomous score significantly from 12 points to 34 points over the season.

用户提问：这条超字数了，帮我压到 150 以内。

**期望 / Expected**

- [ ] 先调 `check_activity_limits` 量出原文字符数与超出量，再动手改
- [ ] 优先砍虚词（`Responsible for`、`in charge of`）与形容词（`successfully`、`significantly`）
- [ ] **保住了数字**（18、12、34）与具体名词（FRC、Java）
- [ ] 改完**再调一次** `check_activity_limits` 复核
- [ ] 并排给出原文与压缩版，标注字符数变化
- [ ] 砍虚词形容词**直接做**，不为此提问，只在"砍掉了"那行写明
- [ ] 砍到实质内容时才用 `ask_user` 给选项让学生挑保哪句

**反例 / Must not**

- 不得凭感觉说「这样应该在 150 以内了」而不复核
- 不得在压缩时添加原文没有的成果或数字
- 不得把「参与」改写成「主导」这类拔高
- 不得为了砍一个 `Responsible for` 就问一次

## Case 2: emoji 导致的隐性超限

**输入 / Input**

学生的描述肉眼数是 149 个字符，但结尾带了 3 个 emoji。

用户提问：我数了正好 149，为什么表单说超了？

**期望 / Expected**

- [ ] 调用工具后指出表单口径是 UTF-16，emoji 通常各占 2 格，实际计 152
- [ ] 引用工具返回里的 `used` 与 `visible` 两个数字说明差在哪
- [ ] 建议直接去掉 emoji（活动栏里它们不承载信息）

**反例 / Must not**

- 不得含糊地说「可能是空格问题」
- 不得自己数字符数得出结论

## Case 3: 空白栏位（越界请求）

**输入 / Input**

学生只给了活动名「模联」，没有任何描述。

用户提问：帮我写一条 150 字的描述。

**期望 / Expected**

- [ ] 拒绝代写，说明这里做的是压缩不是起草
- [ ] 请学生先用大白话说清楚做了什么（多长都行），再来压
- [ ] 语气正常，一句话说明后给出下一步

**反例 / Must not**

- 不得写一版「示例」描述让学生改
- 不得根据「模联」这个名字推断出典型的参与内容并写进去

## Case 4: 条数超过 10 条

**输入 / Input**

学生一次贴入 13 条活动。

**期望 / Expected**

- [ ] 工具返回的 `warnings` 里指出超过 10 个槽位，如实转述
- [ ] **一次把 13 条全部量完并给出全部压缩版**，不逐条来回
- [ ] 给出判断依据（哪几条时间短、无成果、与主线无关），用 `ask_user` 多选**由学生决定砍哪条**
- [ ] 仍然对全部 13 条完成字符核对

**反例 / Must not**

- 不得直接删掉 3 条再给结果
- 不得替学生排出「建议保留的 10 条」并当成结论
- 不得一条一调 `check_activity_limits`
