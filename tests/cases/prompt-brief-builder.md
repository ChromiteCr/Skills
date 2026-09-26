# prompt-brief-builder

## Case 1: 一句话需求

**输入 / Input**

用户：帮我写个东西，介绍一下我们团队做的这个项目。

**期望 / Expected**

- [ ] 先从这句话里抽出**已知**的部分（主题是团队项目、产物是一段文字），不把已知也拿去问
- [ ] 只问 3–5 个高杠杆问题，优先问：给谁看、多长、在哪儿发、有没有必须提到或必须避开的东西
- [ ] 产出的简报九个字段齐全：Objective / Deliverable / Audience / Available Inputs /
      Constraints / Acceptance Criteria / Non-Goals / Open Questions / Suggested Execution Prompt
- [ ] 未确认的内容进 Open Questions 并标 `Assumption:` 或 `Needs user confirmation`
- [ ] Suggested Execution Prompt 不依赖任何一家模型的专有语法

**反例 / Must not**

- 不得一次抛出十个问题
- 不得直接开始写那段介绍文字
- 不得替使用者编造项目内容填进 Available Inputs

## Case 2: 用户不肯回答追问

**输入 / Input**

用户：我不知道给谁看，你看着办。别问了，直接给简报。

**期望 / Expected**

- [ ] 仍然产出一份完整简报，未确认项写进 Open Questions 并明确标为假设
- [ ] Acceptance Criteria 至少有一条可判定的条目，不写"写得好"
- [ ] 说明哪些假设一旦不成立，产物要重做

**反例 / Must not**

- 不得因为使用者不回答就停下不产出
- 不得把假设直接写进 Objective 当成事实

## Case 3: 简报字段留空，脚本要抓到

**输入 / Input**

一份照着 `templates/brief-template.md` 填了一半的简报，Acceptance Criteria 和 Non-Goals 还是空的：
`tests/fixtures/prompt-brief-builder/half-filled-brief.md`。

**期望 / Expected**

- [ ] 用 `scripts/check_brief.py` 跑一遍，报出 `empty sections` 并列出是哪两节（`## Acceptance Criteria`、`## Non-Goals`）
- [ ] 退出状态非零，不当作通过
- [ ] 针对这两节给出具体该补什么，而不是笼统说"请补全"
- [ ] 没有执行能力时人工逐节核对，并把结果标为"人工检查"

**反例 / Must not**

- 不得假装跑过脚本
- 不得替使用者编造验收标准

## Case 4: 用户要的是成品不是简报

**输入 / Input**

（接在 Case 1 之后）用户：简报我不要，你直接按你理解的把稿子写出来。

**期望 / Expected**

- [ ] 按正文"不适用"一条退出本 skill：不再追问，不出简报
- [ ] 交回常规写作流程直接写稿；可以在稿子前用一两行写明推断出的假设（受众、长度、语气），方便使用者一眼纠正
- [ ] 最多用一句话提醒跳过简报意味着受众、长度这些选择是猜的，不反复劝

**反例 / Must not**

- 不得继续追问，或坚持先交一份简报
- 不得把推断出的假设说成使用者提过的要求
- 不得把整份九节简报和成品一起塞进这次输出

## Case 5: 约束互相矛盾

**输入 / Input**

用户：帮我写个东西给 AI，让它写一篇产品介绍，300 字以内，但我们这十个模块每个都要讲到，每个模块要有一个使用场景的例子。

**期望 / Expected**

- [ ] 指出"300 字以内"和"十个模块各带一个场景例子"放在一起做不到（平均每个模块不到 30 字，放不下一个场景）
- [ ] 把这个冲突写进 Open Questions / Assumptions，标 `Needs user confirmation`，并给出可选的取舍让使用者挑：
      放宽字数；只讲三到四个核心模块、其余列名字；每个模块一句话、不带例子
- [ ] 追问时把这个冲突当作高杠杆问题优先问，总数仍不超过 5 个
- [ ] 使用者不回答时，简报里写明采用了哪个假设（`Assumption: ...`），并说明这个假设不成立时产物要重做

**反例 / Must not**

- 不得自己悄悄挑一个（例如直接删掉一半模块或无视字数），当作使用者的要求写进 Constraints
- 不得在 Suggested Execution Prompt 里把两条矛盾的约束原样都交给执行者

## Case 6: 照模板原样交出、只剩空标签的简报

**输入 / Input**

`tests/fixtures/prompt-brief-builder/labels-only-brief.md`：Objective 等六节已填，Deliverable、Audience、Constraints 三节只剩模板里的
`- Artifact:`、`- Primary audience:`、`- Must include:` 这类空标签。另外把 SKILL.md "Output template" 里的模板原样存成文件再跑一次。

**期望 / Expected**

- [ ] 在仓库根目录跑 `python3 skills/ai-usage/prompt-brief-builder/scripts/check_brief.py tests/fixtures/prompt-brief-builder/labels-only-brief.md`，
      报出 `empty sections`，列出 `## Deliverable`、`## Audience`、`## Constraints` 三节，退出码 1
- [ ] 对 SKILL.md 的模板原样同样判为不通过，九节全部列为空
- [ ] 把 `## Objective` 写成 `## Objective `（行尾多一个空格）时，这一节不会被误判为空

**反例 / Must not**

- 不得因为标题都在就当作通过
- 不得替使用者编造受众或约束去填这三节
