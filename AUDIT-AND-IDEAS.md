# 审计与新 skill 提案

生成日期 2026-08-21 · 库版本 0.16.0 · 已建成 30 个 skill

由 7 个并行 Agent 产出后经人工复核：3 路只读审计（coding-helper+skill-authoring / modeling 九个 / study-planning+songwriting+writing 十五个），4 路点子（物理两路、摄影一路、AI 使用一路）。

**这份文档里的结论分三档，请按档位区别对待：**

| 档 | 含义 |
|---|---|
| **已核实** | 我用 grep / 读文件亲自验过，行号和事实可信 |
| **待核实** | Agent 说的，看起来合理，但我没逐条验 |
| **已否决** | Agent 报了但我验完认为不成立，附理由。**不要照着做** |

> 审计 Agent 至少出过一次假引用（见第一部分 D 节），所以未标"已核实"的条目动手前请先自己看一眼原文。

---

## 第一部分：现有 skill 的优化清单

### A. 真问题，值得动

#### A1. 硬编码的易变事实没有出处也没有日期 — **已核实**

两个 skill 把会逐年变动的外部事实写死在正文里，既没有来源也没有记录日期：

- `activity-list-optimizer` SKILL.md:57–63 与 description 里写死 Common App 字符限额（职位 50 / 组织 100 / 描述 150）。脚本 `check_activity_limits` 负责数字符是对的，**但上限本身是写死的常量**，Common App 几乎每季都可能调。
- `application-timeline-builder` SKILL.md:82–88 写死提前量（推荐信 4–6 周、主文书 3–4 周、补充文书 2–3 周、送分 2–3 周、自查 3–5 天）。这条比上一条轻，因为表格旁边写了"学生的实际情况优先"，属于经验值而非硬事实。

**建议**：给这类常量加一行「核对日期 + 出处 URL」，并在 changelog 里约定"上游变了就发 PATCH"。这正是 `keynote-deck-builder` 用 A/B/C 分档解决的同一类问题。

#### A2. `modeling-problem-reading-coach` 完全没有引用 `_shared/` — **已核实**

modeling 九个 skill 里，八个引用 `_shared/` 文档 3 到 5 次，只有它是 **0 次**：

```
modeling-code-builder            5
model-critique-coach             4
model-selection-tutor            4
modeling-assumption-builder      4
paper-enhancement-builder        4
paper-structure-coach            4
team-role-coach                  3
latex-paper-formatter            1
modeling-problem-reading-coach   0   ← 孤儿
```

它是整条工作流的**第一步**，读题阶段就该开始给证据打标签。建议至少引用 `modeling-work-contract.md`（evidence_status 标注）与 `validation-playbook.md`（量纲与单位检查）。

#### A3. `writing-rules` 与 `zlc` 的互斥只写了一边 — **已核实**

`zlc` 里提了 `writing-rules` 两次，`writing-rules` 里提 `zlc` **零次**。两个 skill 的风格正好相反（一个专门禁升华腔，一个专门写升华腔），只有单向声明意味着从 `writing-rules` 那侧进来的用户不会被告知存在冲突。

**建议**：在 `writing-rules` 的边界一节补一句对称声明。这是 PATCH 级改动。

#### A4. 该用脚本而没用脚本的地方

| skill | 现在靠模型做 | 脚本能确定性完成什么 | 档 |
|---|---|---|---|
| modeling 全类 | 量纲一致性人工审（`modeling-assumption-builder` 里有专门章节） | 读变量表 + 解析方程，用 sympy 查量纲；跨章节符号冲突检测（同一个 λ 在不同节表示不同东西） | 待核实 |
| modeling 全类 | Run Manifest 字段完整性靠自觉 | 校验 `code-reproducibility-checklist.md` 规定的必填字段（run_id / 代码版本 / 环境 / 种子 / 输出哈希） | 待核实 |
| `ui-design-system-builder` | 反默认清单靠模型自查 | 解析产出的 CSS，检查是否又回到 Inter / #3b82f6 / 8px 圆角 / 那条标准阴影；对比度按 WCAG 实算 | 待核实 |

`latex-paper-formatter/scripts/check_latex.py` 和 `lyric-doctor/scripts/lyric_check.py` 已经是这条路的成功先例。

#### A5. 边界模糊的三组 skill

| 组 | 用户会怎么迷路 | 档 |
|---|---|---|
| `reflection-interviewer` ↔ `activity-profile-builder` | 都从"想记录一下这段经历"触发；一个做深度反思访谈，一个做结构化清单 | 待核实 |
| `model-selection-tutor` ↔ `modeling-assumption-builder` | 手上有草稿模型又拿不准的人，两个都像 | 待核实 |
| `paper-structure-coach` ↔ `paper-enhancement-builder` | "帮我改进论文"两个都命中；一个重排已有内容，一个规划要补的新工作 | 待核实 |

**建议**：每组在两边的「不适用于」里各加一句判别句，形式参考 `zlc` 里那句"与 `writing-rules` 互斥"。

### B. 小修

- `radio-quote-card` 的 description 里有一条触发语是 `生成 XX RADIO 的图`，`XX` 是占位符不是人话，换成「做一张车队无线电那种语录卡」。**待核实**
- `skills/.DS_Store` 触发校验脚本 WARN。加进 `.gitignore` 并删掉。**已核实**
- modeling 九个的测试用例都缺两类：**矛盾输入**（两份互相打架的题意）和**边界违规**（用户直接要求它违反自己的"不代写"）。`keynote-deck-builder` 的 Case 4 是后者的范本。**待核实**

### C. 其实没问题，不用动

写在这里是为了**防止过度施工**——审计 Agent 天然倾向于给每个 skill 都找出点毛病。

| skill | 判断 |
|---|---|
| `skill-creator` (0.3.1) | 流程清楚，用例覆盖了"改已有技能"和"从上文抠答案"两种。纯教练型 skill 不需要脚本 |
| `lyric-doctor` (0.1.0) | 已有脚本兜确定性部分，正文明确划分了"脚本管机械、模型管语感"。0.1.0 但成熟度不像 |
| `zlc` (0.1.0) | 公式够紧，失败模式表列了六种写坏的方式，边界防住了冒充和群体攻击 |
| `writing-rules` (0.2.0) | 15 条规则加禁用词表，严谨度已经是 1.0 的料 |
| `activity-profile-builder` (0.2.0) | "拆成表格、缺项标待补、拿不准按低的记"这套已经很实用 |
| `weekly-study-review` (0.2.0) | 判据只有一条"下周会因此做什么不一样的事"，够狠且可测 |
| `keynote-deck-builder` (0.3.0) | 本仓库的参照标准 |

### D. 我否决的审计结论

| Agent 报的 | 为什么不成立 |
|---|---|
| `launch-summary-panel` SKILL.md:210 有 bento 格数上限、:214 有 7:1 对比度要求，缺出处 | **假引用。** 该文件只有 182 行，不存在 210/214 行；这两条规则实际在 `keynote-deck-builder/SKILL.md:209` 和 `:214`。已 grep 确认原文件里根本没有这两条 |
| `maestrwave-ui-system` 应该补 references 解释"为什么是五档字号" | 这是从一个真实在跑的项目里抽出来的既成视觉系统，五档就是那个项目的事实。要求它为自己的既定取值找外部文献是把 `keynote-deck-builder` 那套套错了地方 |
| `launch-summary-panel` / `ui-design-system-builder` 的圆角、间距等数值缺文献依据 | 同上。设计取值是选择不是主张，不需要引用。`keynote-deck-builder` 需要引用是因为它在**断言别人的做法**（"苹果不低于 30pt"），性质不同 |
| 摄影那路："我 8 个点子没有一个不值得做" | 没有回答我的问题。见第二部分我自己的否决清单 |

---

## 第二部分：新 skill 提案

### ⚠️ 先看：七个撞名 — **已核实**

四路点子 Agent 都没查 `SKILL_INDEX.md` 里已规划未建的条目，导致以下提案与既有规划**直接同名或高度重叠**：

| 提案名 | 撞上 | 怎么办 |
|---|---|---|
| `experiment-design-guide` | `research-coaching/experiment-design-guide`（已规划） | 改名 `physics-measurement-planner`，聚焦物理测量的误差预算，与通用研究设计分开 |
| `physics-literature-reading-coach` | `research-coaching/literature-reading-coach`（已规划） | **砍掉**，等通用那个建成再看要不要做物理特化 |
| `ai-use-disclosure-checker` | `competition-literacy/competition-ethics-checker`（已规划） | 二选一。我倾向保留已规划的名字，把申报措辞范本并进去 |
| `agent-altitude-decider` | `coding-helper/context-budget-planner` + `multi-agent-task-router`（均已规划） | 重叠约七成。建议并入 `multi-agent-task-router` 而不是新开 |
| `reproducibility-manifest-builder` | `modeling-code-builder` 已有 Run Manifest 结构 | 物理版只在积分器、数值精度、种子上有增量，**建议不单开** |
| `problem-formalization-coach` | `modeling/modeling-problem-reading-coach` | 机制确实不同（一个面向开放建模题，一个面向已成文的物理题），可以并存但要在两边写判别句 |
| `lab-report-structure-coach` | `modeling/paper-structure-coach` | 学科不同、体裁不同，可并存 |

### 物理（第一优先，数量最多）

去重合并两路的 24 条后保留 16 条，分四组。

#### 组一：动笔之前（把题变成可解的东西）

| name | 一句话 | 确定性部分 | 重复风险 |
|---|---|---|---|
| `problem-formalization-coach` | 题面拆成已知、未知、约束、该用哪条定律及为什么、假设，**不解题** | 检查字段完整；检出凭空补进来的量 | 与 `modeling-problem-reading-coach` 需划界 |
| `problem-representation-scout` | 诊断卡住是因为缺哪个表示（受力图、能量柱状图、电路重画、参考系） | 无 | 无 |
| `reference-frame-choice-guide` | 帮选参考系并说清为什么，估各系下的代数复杂度 | 可符号比较不同系下表达式项数 | 无 |
| `competition-scenario-extractor` | 把两三页的竞赛题压成干净题面 + 子问题树 + 可忽略项 + 近似的安全性 | 标出模糊措辞、缺失约束、题面内自相矛盾的量纲 | 无 |

#### 组二：检错（最便宜的防线）

| name | 一句话 | 确定性部分 | 重复风险 |
|---|---|---|---|
| `dimensional-analysis-checker` | 逐项查量纲，抓符号错、漏项、多余项 | sympy 量纲检查；列出该约掉却没约掉的项 | 无 |
| `limiting-case-validator` | 查公式在 m→0、v→c、θ→0 等极限下是否物理合理 | sympy 求极限、提主项、查符号 | 无 |
| `answer-plausibility-checker` | 数值答案先过嗅觉测试再信：量级、极限、单位、与已知参考值比 | 量级估算 + 常见物理量参考值表 | 与上两条部分重叠，可考虑三合一 |
| `derivation-step-checker` | 逐步验推导：代数、定律适用性、单位守恒、符号翻转 | sympy 逐步代数验证 | 无 |

#### 组三：概念与估算

| name | 一句话 | 确定性部分 | 重复风险 |
|---|---|---|---|
| `physics-misconception-diagnoser` | 从学生的做法反推踩了哪个经典迷思，命名它再教 | 匹配已知迷思清单（力与运动、热与温度、电流被"用掉"、参考系混淆） | 无 |
| `fermi-estimation-coach` | 结构化数量级估算，每步带合理性检查 | 检查中间估值是否落在已知量级区间 | 无 |
| `symbolic-first-discipline-coach` | 并排展示符号做到底与早代入数字的差别，让人看见代价 | 符号解与数值解逐步对比 | 无 |
| `concept-to-formula-deriver` | 从守恒律或定义重建标准公式，每步标物理含义 | 终式与标准式比对 | **边界要写死**：可以讲公式从哪来，作业推导本人做 |

#### 组四：实验、数据与计算

| name | 一句话 | 确定性部分 | 重复风险 |
|---|---|---|---|
| `uncertainty-propagator` | 不确定度传播（含相关项），给灵敏度系数 | sympy 求导 + 蒙特卡罗对标；查雅可比条件数 | 无 |
| `model-fit-auditor` | 拟合诚实性体检：残差、χ²/自由度、过拟合信号、异常点处理 | scipy 算标准化残差、leverage、影响函数、AIC/BIC | 无 |
| `dataset-systematic-error-hunter` | 从原始数据里找藏着的系统误差（温漂、零点漂移、非线性） | 残差对时间/温度/参数的趋势、首尾漂移、重复不一致 | 无 |
| `numerical-stability-auditor` | 判模拟结果可不可信：能量守恒、步长收敛、鬼频检测 | 能量相对漂移、变步长收敛率、功率谱找离散化鬼峰 | 无 |

**并入其他条目、不单开的**：`significant-figures-enforcer`（并进 `uncertainty-propagator`，有效数字本就由不确定度决定）、`nondimensionalizer`（并进 `numerical-stability-auditor` 的前置步骤）、`simulation-sanity-checker`（与 `limiting-case-validator` 机制重复）、`physics-figure-builder`（`keynote-deck-builder` 的图表规则已覆盖大半，差的部分可做成 references）。

**先做哪三个**：`dimensional-analysis-checker` → `limiting-case-validator` → `model-fit-auditor`。理由是这三个确定性最强（sympy/scipy 直接跑）、见效最快、且互不重叠；两路 Agent 独立推荐的前三名里都有后两个。

### 摄影（第二优先）

**本机工具实况 — 已核实**：`ffmpeg` / `ffprobe` 有（在 anaconda 路径下），`PIL 11.1.0` / `numpy 2.1.3` / `scipy 1.15.3` / `imageio` 有。**`exiftool`、ImageMagick（magick/convert）、`dcraw`、`darktable-cli`、`rawtherapee-cli`、`wkhtmltopdf` 全都没有**，`rawpy` 和 `piexif` 也没装。所以任何依赖 exiftool 或 RAW 解码的点子，要么先装东西，要么改用 PIL。

| name | 一句话 | 确定性部分 | 我的判断 |
|---|---|---|---|
| `exif-habit-diagnoser` | 读一整场拍摄的 EXIF，诊断摄影师自己的习惯（88% 都在 f/2.8、快门常低于焦距倒数） | PIL 读 EXIF + numpy 分组统计，出 CSV 与文字报告 | **推荐先做。** 纯统计、不需要"看懂"照片，正是文本 Agent 能做好的 |
| `sharpness-culler` | 用 Laplacian 方差给一组照片的清晰度分级，供人工终审 | PIL 转灰度 + numpy 拉普拉斯方差，出分级 CSV | **推荐先做。** 算法成熟，且明确只做初筛不做删除 |
| `burst-collapse-script-builder` | 按时间戳聚类连拍组，生成待删脚本（只生成不执行） | PIL 读拍摄时间聚类，输出带注释的 bash | 值得做，但"选最清那张"要依赖上一条，应合并或声明依赖 |
| `color-drift-detector` | 检测一组照片白平衡漂移并分组 | PIL 读 RGB + 色温估计模型 | 值得做，但要老实说明：从已烘焙的 JPEG 反推色温误差不小 |
| `metadata-privacy-exporter` | 按策略批量剥离敏感 EXIF（位置、机身序列号），保留署名与版权 | PIL EXIF 读写 | 值得做。**边界写死：绝不删版权与作者字段** |
| `contact-sheet-generator` | 生成接触印相页（HTML 或 PDF），可按 EXIF 排序 | PIL 出缩略图 + HTML 模板 | 值得做，优先级最低，纯便利工具 |

**我否决的（Agent 说"没有不值得做的"，这是在回避问题）**：

- `look-specification-builder` — 它的设计是"给一段参考描述加一张样片，输出调色参数脚本"。问题在于 **Agent 看不到那张样片的美学意图**，直方图统计推不出"富士 Portra 那种偏绿"。这条要么降级成"把你已经调好的参数固化成可复用脚本"（诚实且有用），要么不做。**按原样做出来会是个假装懂调色的东西。**
- `color-space-sanity-checker` — 真实需求存在，但没有 exiftool 的情况下 PIL 对 ICC profile 的读取覆盖不全，做出来会漏报。**要做就先装 exiftool**，别用半残的实现骗自己。

### AI 使用（第三优先）

Agent 自己杀掉了 `prompt-context-hygiene`，理由成立——那是模型本来就会给的建议，固化成 skill 不改变任何行为。我同意。

剩下四个里，两个撞名（见前表），实际新增只有两个：

| name | 一句话 | 确定性部分 | 判断 |
|---|---|---|---|
| `confabulation-detector` | 把 Agent 的回答拆成可检验声明，逐条给验证方法（链接测活、库版本查证、DOI 核对） | URL 活性检查、包版本与发布时间校对 | **推荐先做。** 这是四个里唯一有真确定性内容的，而且直接防住"引用了不存在的库/论文"这种会在评审时炸掉的事故 |
| `ai-code-audit-coach` | 教怎么审自己看不太懂的 AI 生成代码 | 行数、嵌套深度、缺测试、硬编码密钥等客观度量 | 值得做，但要老实写明**它查不了算法正确性**。与已规划的 `test-debug-loop` 要划界 |

---

## 建议的动手顺序

1. **先清小债**（半小时级）：`.DS_Store` 进 gitignore；`writing-rules` 补对称互斥声明；`radio-quote-card` 换触发语；`modeling-problem-reading-coach` 补 `_shared/` 引用。
2. **给易变事实加日期与出处**：`activity-list-optimizer` 和 `application-timeline-builder`。这两条不修，某一年会静默地给出错的字数上限。
3. **建第一个物理 skill**：`dimensional-analysis-checker`。它最小、最确定、也最能验证"物理类到底适不适合做成 skill"。
4. 视第 3 步的结果再决定要不要铺开物理其余 15 个。

## 待你定的分歧

1. **物理要不要单开一个 category？** 现在没有 `physics/`。16 个 skill 足够单开一类，但也可以拆进 `modeling`（计算类）和一个新的 `problem-solving`。
2. **撞名的四个怎么处理**：是把新点子并进已规划的条目，还是改名并存？我倾向并入，避免 `SKILL_INDEX` 里出现两个做同一件事的名字。
3. **摄影这一类值不值得开**。六个点子都能做，但都偏工具而非判断，和这个库"把判断写下来"的定位不完全一致。也可以只做 `exif-habit-diagnoser` 一个试水。
4. **`answer-plausibility-checker` 三合一？** 它与 `dimensional-analysis-checker`、`limiting-case-validator` 机制重叠，可以合成一个"答案体检"skill，也可以保持三个各管一段。
