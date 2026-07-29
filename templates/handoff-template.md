---
template: handoff
version: 0.1.0
---

# Handoff

子 Agent 交回主 Agent 的**短交接单**。目标是让主 Agent 不需要读子 Agent 的推理过程。
Short handoff from a sub-agent. The parent must not need the sub-agent's reasoning log.

规则：
- 总长控制在 ~30 行以内
- 只写结论、证据位置、下一步；不写推理过程
- 文件一律写成 `path:line`，便于跳转
- 不确定的事标 `未验证 / unverified`，不要写成结论

---

## 任务 / Task

一句话：被要求做什么。

## 结论 / Result

- done / partial / blocked
- 一到三句话说明发生了什么

## 改动 / Changes

| 文件 | 改了什么 |
|---|---|
| `path/to/file.ts:42` | ... |

无改动写「无」。

## 证据 / Evidence

- 命令：`<command>`
- 结果：通过 / 失败（失败贴最短的关键输出，不超过 10 行）

未运行验证就写「未验证」，不要用「应该可以」代替。

## 遗留 / Open items

- [ ] 未完成项 + 卡在哪
- [ ] 需要主 Agent 决策的点（给出选项与建议）

## 下一步建议 / Next

一到两条，具体到文件或命令。
