# Modeling Team Workflow

建模团队按产物和决策分工，不按“一个人只建模、一个人只写代码、一个人只写论文”切断证据链。每个关键产物有
一名 owner、一名 reviewer 和可核对的退出条件。

## 1. 产物生命周期

```text
proposed -> in-progress -> review-ready -> changes-requested
         -> verified -> accepted -> superseded
```

- `review-ready`：owner 完成自查并附证据，不代表正确
- `verified`：reviewer 按退出条件核对
- `accepted`：团队决定下游可依赖该版本
- `superseded`：新版本替代，旧版本保留追踪，不静默删除

任何 `draft / unverified` 结果进入论文时必须显式标状态，不能靠文件名“final”升级。

## 2. 最小角色职责

角色可以由同一人兼任，但高风险决策尽量由不同人复核：

| 职责 | Owns | Reviews | 不能单独批准 |
|---|---|---|---|
| problem steward | 题面契约、变量 / 单位、规则覆盖 | 模型是否回答原题 | 自己新增的题意解释 |
| model steward | 候选、假设、方程、选择记录 | 实现与论文是否忠实 | 自己模型的最终有效性 |
| data / code steward | 数据、实现、测试、运行与图表 | 方程映射、复现 | 自己生成的关键结果与图 |
| evidence / paper steward | 主张图、章节、引用、格式与提交包 | 结果措辞和规则覆盖 | 没有运行来源的数字 |
| integrity reviewer | 来源、AI 使用、贡献、最终清单 | 所有高风险声明 | 本人独立产出的同一项 |

人数不足时可以合并 owner，但 reviewer 检查仍要显式执行；单人项目把它标为 self-review，不冒充独立复核。

## 3. 九个质量闸门

| Gate | 进入条件 | 最少退出条件 | 失败回退 |
|---|---|---|---|
| G0 Problem contract | 原题与规则可读 | 动作、变量 / 单位、约束、交付、歧义有状态 | 补题面 / 确认解释 |
| G1 Model decision | G0 accepted | 基线 + 候选 + 判别测试 + 决策 / 拒绝记录 | 重开目标或数据条件 |
| G2 Assumption freeze | 候选结构明确 | 高承重假设有作用域、后果与测试 | 改模型 / 缩作用域 |
| G3 Baseline verified | 数据合同与小例可用 | 小例、不变量、输入校验和简单基线通过 | 修数据 / 实现 |
| G4 Main run | G2 / G3 accepted | 求解诊断、运行清单、结果来源与警告完整 | 修实现 / 参数 / 模型 |
| G5 Validation review | 冻结主模型与指标 | 校准外验证、关键灵敏度 / 稳健性或诚实限制 | 降级结论 / 补测试 |
| G6 Paper evidence | 可用结果与验证 | 每条核心主张接到图表 / 运行，摘要不超证据 | 修证据链 / 结构 |
| G7 Build review | 内容冻结 | 静态检查、编译、PDF 视觉与规则覆盖完成 | 修格式 / 回退内容 |
| G8 Final integrity | 提交包冻结 | 来源、数字、贡献、AI 披露、文件与截止复核 | 阻止提交直至关闭 blocker |

闸门不是会议名称，是可核对退出条件。赶时间可以缩小作用域，不能把未过 Gate 改名为通过。

## 4. Artifact Register

| Artifact ID | 内容 | Owner | Reviewer | Version | Status | Depends on | Evidence / path | Next gate |
|---|---|---|---|---|---|---|---|---|

至少登记：原题 / 规则、变量账本、数据快照、模型决策、假设、代码、测试、运行、图表、主张图、论文源、PDF、提交清单。

## 5. Decision Log

| Decision ID | Question | Alternatives | Decision | Evidence | Decider(s) | Revisit trigger |
|---|---|---|---|---|---|---|

必须记录：题意解释、模型选择、指标 / 权重、数据处理、参数边界、拒绝方案、结论降级和提交范围。没有证据的决定可以
暂定，但要写重开条件。

## 6. Handoff Packet

```markdown
## <artifact / task>
- status: <lifecycle state>
- version / owner:
- completed: <可核对结果>
- evidence: <IDs / paths / run>
- verification: <command / reviewer / not-run>
- assumptions / warnings: <只列影响下游的>
- open blockers: <缺什么、影响什么>
- next action: <一件事 + owner + exit condition>
```

交接时不给“我大概做完了”。接收者先核版本、状态、单位和证据，再开始下游工作。

## 7. 同步与冲突

- 日常同步只回答：完成证据、当前 blocker、下一个 Gate，不逐人朗读工作日志
- 模型 / 数据 / 变量定义只在单一登记处修改，论文和代码引用 ID
- 冲突先写成可判别问题，列双方依据和最便宜检查；没有证据时由负责决策的人暂定并记重开条件
- 上游 accepted 产物变化时，列出所有受影响运行、图表和主张，不能只改论文一句话
- 最后时段冻结新功能，只关闭 blocker、修证据链、编译与检查提交包