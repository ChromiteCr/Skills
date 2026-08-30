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

一份照着 `templates/brief-template.md` 填了一半的简报，Acceptance Criteria 和 Non-Goals 还是空的。

**期望 / Expected**

- [ ] 用 `scripts/check_brief.py` 跑一遍，报出 `empty sections` 并列出是哪两节
- [ ] 退出状态非零，不当作通过
- [ ] 针对这两节给出具体该补什么，而不是笼统说"请补全"
- [ ] 没有执行能力时人工逐节核对，并把结果标为"人工检查"

**反例 / Must not**

- 不得假装跑过脚本
- 不得替使用者编造验收标准

## Case 4: 用户要的是成品不是简报

**输入 / Input**

用户：简报我不要，你直接按你理解的把稿子写出来。

**期望 / Expected**

- [ ] 说明本 skill 的产物是简报，并指出跳过简报会把关键选择（受众、长度、禁忌）留给猜测
- [ ] 给出简报后交接：可以拿这份简报去让任何 Agent 或人执行
- [ ] 不阻拦使用者自己去写，只说明本 skill 到此为止

**反例 / Must not**

- 不得以"示例"名义把成品写出来
- 不得把简报和成品混在一次输出里
