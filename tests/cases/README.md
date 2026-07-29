# 测试用例 / Test cases

每个 skill 至少一个用例，文件名必须是 `<skill-name>.md`（与 frontmatter 的 `name` 一致）。
`./scripts/validate.sh` 会检查文件存在且非空。

用例是**可重复的人工评估脚本**：给定输入，说明什么样的输出算通过。不要求自动化。
Cases are repeatable manual evaluations: given this input, state what counts as a pass.

## 格式 / Format

```markdown
# <skill-name>

## Case 1: <场景名>

**输入 / Input**

<贴给 Agent 的原始输入；需要夹具时引用 tests/fixtures/...>

**期望 / Expected**

- [ ] 触发了正确的 skill
- [ ] 输出包含 <必需段落>
- [ ] 未越过边界：<具体边界>

**反例 / Must not**

- 不得虚构数据或来源
- 不得代写应由使用者产出的内容

## Case 2: 输入不足时
...
```

至少覆盖三类：**正常输入**、**输入不足**（应追问而非猜测）、**越界请求**（应拒绝并给出可做的替代）。
Cover normal input, insufficient input, and an out-of-bounds request.

夹具文件放 `tests/fixtures/`。
