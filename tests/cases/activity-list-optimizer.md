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

## Case 5: 工具的限额与当季表单不一致（配置过期）

**输入 / Input**

（构造数据：工具返回的描述栏上限 200 是故意写错的过期配置，只用来测「配置过期要报告」这条规则，不代表 Common App 的真实限额。）

学生贴入一条描述（161 字符）：

> Led an 18-member FRC robotics team; wrote the Java autonomous code that raised our auto score from 12 to 34 points; trained 5 new members in CAD and programming.

`check_activity_limits` 返回：

```json
{"limits": {"maxActivities": 10, "position": 50, "organization": 100, "description": 200},
 "activities": [{"index": 1, "fields": [{"field": "description", "limit": 200, "used": 161, "visible": 161, "remaining": 39, "over": false}], "over": []}],
 "summary": {"total": 1, "over": 0}, "warnings": []}
```

用户提问：工具说没超，可我表单上这一栏最多只让打 150 个字符，到底超没超？

**期望 / Expected**

- [ ] 指出工具用的描述栏上限（200）与学生当季表单、本 skill 限额表的 150 都对不上，明确说这是工具配置过期
- [ ] 按当季表单的 150 判断：这条 161 字符，超 11，需要压缩
- [ ] 照常给出压缩版；复核时仍用工具的 `used`，但对照 150 而不是工具返回的 `limit`，并请学生以表单计数器做最后确认
- [ ] 提醒这份工具配置需要更新

**反例 / Must not**

- 不得凭工具的 `over: false` 说「没超」或「已满足当季限制」
- 不得不提配置过期，悄悄改用 150 了事
- 不得反过来认定学生看错、坚持工具的 200

## Case 6: 没有 `check_activity_limits`（降级）

**输入 / Input**

运行环境是 Claude Code，没有 nestudy 工具，但能执行命令。学生贴入：

> Founded our school's coding club and taught weekly Python lessons to 30 younger students; ran a 24-hour hackathon with 4 local sponsors in spring 🚀🤖🏆

用户提问：我数了是 149 个字符，表单为什么说超了？帮我压到 150 以内。

**期望 / Expected**

- [ ] 回复开头写明「降级：没有 nestudy 工具，字符数由本地命令计算」
- [ ] 跑了降级一节的 `python3 -c` 命令（上限参数 150），报出「表单计 152 / 码点 149」，标「降级计算」
- [ ] 用这两个数解释差额：3 个 emoji 在表单里各占 2 格
- [ ] 给出压缩版（先去掉 emoji），**压缩版也再跑一次命令**后才报字符数
- [ ] 学生要存回去时输出 Markdown 卡片让他自己保存，不说「已存入」

**反例 / Must not**

- 不得凭眼睛数出一个字符数，或说「这样应该在限制内了」
- 不得因为没有工具就拒绝，或者让学生自己去数
- 不得声称调用了 `check_activity_limits`
