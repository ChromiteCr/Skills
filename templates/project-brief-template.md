---
template: project-brief
version: 0.1.0
---

# Project Brief

项目启动时的**唯一事实来源**。写进文件，不要只留在对话里——这是省 token 的关键。
The single source of truth at project start. Keep it in a file, not in chat context.

---

## 一句话定义 / One-liner

给谁、解决什么问题、用什么方式。

## 成功判据 / Definition of done

可验证的条目，不写「体验更好」这类不可判定的目标。

- [ ] ...
- [ ] ...

## 范围 / Scope

**做** / In:
- ...

**不做** / Out:
- ...

「不做」比「做」更重要，写具体。

## 约束 / Constraints

| 类型 | 约束 |
|---|---|
| 技术栈 | ... |
| 运行环境 | ... |
| 时间 | ... |
| 数据 / 隐私 | ... |
| 不可引入的依赖 | ... |

## 关键决策 / Decisions

已定下的选择及其理由，避免后续反复讨论。

| 决策 | 选择 | 理由 | 日期 |
|---|---|---|---|
| ... | ... | ... | YYYY-MM-DD |

## 未决问题 / Open questions

| 问题 | 阻塞什么 | 谁来定 |
|---|---|---|
| ... | ... | ... |

阻塞性问题先问；不阻塞的先按假设推进，并在此记录假设。

## 里程碑 / Milestones

| 阶段 | 产出 | 版本 |
|---|---|---|
| 1 | ... | ... |

## 上下文清单 / Context manifest

Agent 每轮任务应读哪些文件，按需加载而非全量读取。

| 文件 | 何时读 |
|---|---|
| `README.md` | 始终 |
| `docs/repo-map.md` | 定位代码时 |
| `path/...` | 涉及该模块时 |

## 状态 / Current state

每轮任务结束后更新这一节，替代把历史堆在对话上下文里。

- 当前版本：
- 已完成：
- 进行中：
- 下一步：
