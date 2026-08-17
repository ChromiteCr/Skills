# Modeling Work Contract

建模技能之间只交接结论、证据位置、未决问题和下一步，不交接长推理记录。使用稳定 ID，避免论文、代码和
讨论中的“变量 A”实际指向三件不同的事。

## 1. 状态标签

每个事实、数字、假设、结果与结论使用下列一个 `evidence_status`：

| 标签 | 含义 | 可以怎样升级 |
|---|---|---|
| `verified` | 已由原题、可信来源或可复现检查确认 | 保留证据位置与检查方式 |
| `student-provided` | 使用者提供，但尚未独立核对 | 补原始记录、来源或执行验证 |
| `inferred` | 根据已有材料推断 | 写清依据、适用范围和反证条件 |
| `unverified` | 有具体说法，但验证尚未执行或失败 | 记录待运行的检查，不写成事实 |
| `missing` | 后续步骤需要，但当前没有 | 指定由谁、从哪里补 |

“模型输出”不自动等于 `verified`；它至少需要输入、运行与解释三层核对。

产物本身另用 `artifact_status`：`proposed -> in-progress -> review-ready -> changes-requested -> verified -> accepted -> superseded`。
二者不能合并：一个论文草稿可以是 `artifact_status: accepted`，其中某条数字仍是 `evidence_status: unverified`。
只有产物已 `accepted` 且下游所依赖条目的 `evidence_status` 满足当前 Gate，接收者才可把它当作前提。

## 2. 稳定 ID

| 前缀 | 对象 | 最少字段 |
|---|---|---|
| `Q` | 子问题 | 动作、输入、输出、约束、验收条件 |
| `V` | 变量 | 符号、含义、类型、单位 / 维度、范围、来源、状态 |
| `D` | 数据 | 来源、版本 / 截止时间、字段、单位、许可、处理记录 |
| `A` | 假设 | 原句、类型、理由、作用域、风险、反证 / 压力测试 |
| `M` | 模型 | 家族、结构 / 方程、参数、输入、输出、预期用途 |
| `C` | 主张 | 精确措辞、作用域、证据 ID、限制、论文位置 |
| `T` | 验证 | 测试对象、数据 / 场景、指标、基线、决策规则、结果 |
| `R` | 运行 | 代码版本、输入快照、环境、命令、随机种子、输出路径 |
| `F` | 图表 | 支持的主张、数据 / 运行 ID、单位、图注、生成方式 |

新增条目使用新 ID，不因排序变化重新编号。删除时标记废弃并说明替代，避免旧论文段落指向错误对象。

## 3. 最小工作包

按任务阶段保留需要的段落；没有内容的字段写 `missing`，不要编造填满。

```markdown
# Modeling Work Packet

## Scope
- packet_version: 0.1
- artifact_status: proposed | in-progress | review-ready | changes-requested | verified | accepted | superseded
- owner:
- reviewer:
- source_material:
- last_verified:

## Problem Contract
- questions: Q...
- objectives:
- constraints:
- required_deliverables:
- scope:

## Variable Ledger
| ID | Symbol | Type | Meaning | Unit / Dimension | Range | Source | Status |

## Data Register
| ID | Source / Version | Fields | Time / Space Scope | Processing | License | Status |

## Model Decisions
| ID | Family / Structure | Intended Use | Alternatives | Decision Status | Rationale |

## Assumption Register
| ID | Statement | Type | Scope | Risk | Test | Status |

## Validation Register
| ID | Target | Baseline | Data / Scenario | Metric | Decision Rule | Result | Status |

## Claims and Evidence
| ID | Claim | Evidence IDs | Scope | Limitation | Status |

## Run and Figure Register
| ID | Inputs / Command | Seed / Environment | Outputs | Supports | Status |

## Open Items
| ID | Missing / Conflict | Effect | Owner | Next Check |

## Next Handoff
- receiving_skill:
- accepted_items:
- provisional_items:
- blocking_items:
- next_action:
```

## 4. 交接规则

1. 只把 `artifact_status: accepted` 且所需条目 `evidence_status: verified` 的内容当成已核前提；
	`student-provided` / `inferred` 只有在接收者明确接受其风险与作用域时才能暂用，其他状态必须连同风险传递。
2. 数值必须连单位和口径一起交接。只有数值没有单位，等于没有交接。
3. 方程必须能追到变量账本；结论必须能追到验证或结果；图表必须能追到运行或数据。
4. 下游发现上游错误时，不静默修正。登记冲突，回写受影响 ID，再重跑依赖项。
5. 运行另用 `run_status: not-run | failed | passed-with-warnings | passed`；不与产物或证据状态混用。
6. 交接长度以能让接收者继续工作为准；原始材料用位置引用，不整段复制。

## 5. 工具无关约定

- 能读文件：记录实际读到的文件与版本；不能读：请使用者贴相关段落。
- 能执行：记录命令、环境、退出状态和输出；不能执行：给可复现步骤并标 `unverified`。
- 能写文件：修改前保留原内容与改动范围；不能写：在对话中返回完整候选产物。
- 能调用独立审查：给审查者最小工作包；不能调用：做一遍明确标注的自审并说明独立性不足。
- 能联网：仍需记录来源；不能联网：不补写来源、规则或文献元数据。

宿主工具名称不属于工作包。换 Agent 时只映射语义动作，不改建模契约。