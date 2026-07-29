---
name: skill-name-in-kebab-case
description: 一句话说明「什么时候用它」和「它产出什么」。Agent 靠这句话决定是否触发，写具体、写触发词，不要写成宣传语。
category: category-name/optional-subtopic
version: 0.1.0
status: draft
priority: P0
compatible_agents:
  - claude-code
  - openclaw
  - cursor
  - codebuddy
  - generic-llm-agent
---

# Skill Name

<!--
使用说明（创建后删除本注释）：
1. 复制本文件到 skills/<category>/<skill-name>/SKILL.md
2. frontmatter 的 name 必须等于目录名；category 必须等于所在的分类目录名
3. 在 tests/cases/<skill-name>.md 添加至少一个用例
4. 在 SKILL_INDEX.md 登记，并在 README.md 相应集合中补一行
5. 运行 ./scripts/validate.sh
-->

一句话定位：这个 skill 做什么，不做什么。

## 何时使用 / When to use

- 触发场景 1
- 触发场景 2

**不适用于** / Not for：

- 反例 1（应改用 `<other-skill>`）

## 需要的输入 / Inputs

| 输入 | 必填 | 说明 |
|---|---|---|
| ... | 是 | ... |
| ... | 否 | 缺失时的默认行为 |

输入不足时：**先问清关键项，不要猜**。列出你需要的最少信息即可，不要一次问十个问题。

## 流程 / Process

1. 第一步——做什么、产出什么中间物
2. 第二步
3. 第三步

每一步的产出应可单独检查；不要一次输出全部再让用户从头核对。

## 输出格式 / Output

```markdown
## <段落标题>
...

## <段落标题>
...
```

输出要求：
- 结构固定，便于下游 skill 或 Agent 消费
- 简洁，不复述输入
- 需要移交给其他 Agent 时，用 `templates/handoff-template.md` 的短格式

## 边界 / Boundaries

- 只做指导、解释、批判、格式化与优化
- 不替使用者思考，不代写应由本人产出的内容
- 不虚构数据、来源、实验或结果；信息不足就说明缺什么
- 不越权操作文件系统、网络或凭据；确定性工作交给脚本

## Token 控制 / Token discipline

- 只读与当前任务相关的文件，不默认读整个仓库
- 长日志、长历史先压缩再引用
- 状态写入文件，不长期驻留在对话上下文

## 参考资料 / References

放在同目录下，按需加载，不在本文件内展开：

- `references/<topic>.md` — 何时读它

## 变更记录 / Changelog

| 版本 | 日期 | 变更 | 类型 |
|---|---|---|---|
| 0.1.0 | YYYY-MM-DD | 初始草稿 | minor |
