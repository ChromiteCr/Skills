---
template: edit-plan
version: 0.1.0
---

# Edit Plan

改代码**之前**写这份计划；计划变化时不要偷改，另写一份 Revision Plan（见文末）。
Write this before editing code. If the plan changes, write a revision plan instead of silently drifting.

---

## 目标 / Goal

一句话：这次改动要达成什么。可验证。

## 不做什么 / Out of scope

明确列出这次**不碰**的东西。这一节是控制范围的关键，不能省。

- ...

## 相关文件 / Files in scope

只列真正要读或改的文件。超过 8 个文件说明范围过大，先拆。

| 文件 | 读 / 改 | 为什么 |
|---|---|---|
| `path/to/file.ts` | 改 | ... |
| `path/to/other.ts` | 读 | 确认接口 |

## 改动步骤 / Steps

每步一个可独立提交的小 patch。每步注明验证方式。

1. **步骤名** — `path/to/file.ts`
   - 改什么：...
   - 验证：`<command>` 或 观察点
2. **步骤名** — ...

## 风险 / Risks

| 风险 | 影响 | 应对 |
|---|---|---|
| ... | ... | ... |

## 验证方案 / Verification

- [ ] `<test command>`
- [ ] 手动检查点：...

「改完看起来没问题」不算验证。必须有可运行的命令或明确的观察点。

## 回滚 / Rollback

如何撤回：分支名、commit 边界、或需要手动还原的状态。

---

# Revision Plan（计划变化时追加）

## 触发原因 / Why the plan changed

发现了什么与原计划不符的事实。

## 与原计划的差异 / Diff from original

| 原计划 | 现计划 | 原因 |
|---|---|---|
| ... | ... | ... |

## 新的范围边界 / Updated scope

- 新增：...
- 移除：...

范围扩大时先确认，不要顺手做完。
