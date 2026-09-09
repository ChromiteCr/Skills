# SKILL INDEX

全部 skills 的索引。**新增 skill 必须在此登记**，`./scripts/validate.sh` 会校验。
Index of all skills. Every skill must be registered here; validation enforces it.

登记格式：一行一个 skill，`| skill | 优先级 | 状态 | 版本 | 一句话用途 |`。
未建成的 skill 状态写 `planned`，版本留 `—`。

Library Version: `0.21.0`

---

## coding-helper — P0

低 token、可控、多 Agent 协作的编程工作流。Token-efficient, controllable, multi-agent coding workflow.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `ui-design-system-builder` | P0 | draft | 0.1.0 | 从项目意象推出一套 token 与排版尺度，让界面不像模板 |
| `maestrwave-ui-system` | P0 | draft | 0.1.0 | 直接套用 MaestrWave 那套深色衬线视觉，附可粘贴的 global.css 与组件层 |
| `radio-quote-card` | P2 | draft | 0.1.0 | 名字＋内容＋主色生成车队无线电风格语录卡，单文件 800×1000，不带任何厂商徽标 |
| `launch-summary-panel` | P1 | draft | 0.1.0 | 产品资料收成 16:9 bento 总结面板：先出策划稿再出单文件 HTML，数字必须有出处 |
| `keynote-deck-builder` | P1 | draft | 0.5.1 | 描述／演讲稿／现有 PPT 做成发布会风格演示：先定叙事拍点再出片，一片一个概念，不用项目符号，可导 PDF 与可编辑 pptx |
| `photo-spread-composer` | P2 | draft | 0.1.0 | 一组照片排成带状构图的展示版面：位置由带高方程解出，主次与分带留给判断，分辨率不足直接拦下 |
| `coding-project-brief-builder` | P0 | planned | — | 收敛需求，产出项目 brief |
| `architecture-planner` | P0 | planned | — | 规划架构与模块边界 |
| `repo-map-compressor` | P0 | planned | — | 生成 repo map，压缩上下文 |
| `context-budget-planner` | P0 | planned | — | 规划每轮任务的 token 预算 |
| `edit-plan-builder` | P0 | planned | — | 改代码前先写编辑计划 |
| `patch-scope-controller` | P0 | planned | — | 控制 patch 范围，小步修改 |
| `multi-agent-task-router` | P0 | planned | — | 拆任务并分派给多个 Agent |
| `test-debug-loop` | P0 | planned | — | 测试—调试闭环与收敛判据 |

## modeling — P0

建模指导、批判与论文整理。仅指导，不代写、不虚构数据。Coaching only; no fabricated models or data.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `modeling-problem-reading-coach` | P0 | draft | 0.1.0 | 把题面拆成目标、变量与单位、约束、子问题依赖和待确认歧义，不越界选模型 |
| `model-selection-tutor` | P0 | draft | 0.1.0 | 用简单基线、选型门槛与判别测试比较候选，给条件式推荐而不编性能 |
| `modeling-assumption-builder` | P0 | draft | 0.1.0 | 区分事实、定义、选择与假设，为每条前提登记作用域、失效后果和反证测试 |
| `model-critique-coach` | P0 | draft | 0.1.0 | 从核心主张反向追到运行、模型、数据和假设，按结论影响分级并设计反例 |
| `paper-structure-coach` | P0 | draft | 0.1.0 | 用主张—证据图重排章节、段落与图表，让摘要、正文、运行和限制闭环 |
| `paper-enhancement-builder` | P0 | draft | 0.1.0 | 把具体缺口按结论影响、评分关联、成本和风险排成有验收条件的最小修订计划 |
| `latex-paper-formatter` | P0 | draft | 0.1.0 | 冻结内容后修 LaTeX 结构、引用、表图与版面，用静态检查、实际编译和 PDF 验收闭环 |
| `modeling-code-builder` | P0 | draft | 0.1.0 | 把已确认模型实现为有小例、不变量、验证矩阵和运行清单的可复现代码 |
| `team-role-coach` | P0 | draft | 0.1.0 | 按产物和依赖分 owner/reviewer，用九个 Gate、交接包与冻结点控制团队协作 |

## physics — P0

从一句现象或一道题，拆到可以动手的结构：分流、题面、原理、表示、参考系、机制。
只做拆解、检查与判据，不解题、不给答案。
Physics decomposition pipeline: routing, framing, principles, representations, frames, mechanisms. It never solves.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `physics-problem-router` | P0 | draft | 0.1.0 | 统一入口：定问题类型、目标产物与卡点，检出"要的产物与问题类型不匹配"，再分流 |
| `competition-scenario-extractor` | P0 | draft | 0.1.0 | 长材料压成干净题面与子问题树；每条理想化标出关掉的机制与破坏判据；抓模糊措辞、单位冲突与欠定 |
| `problem-formalization-coach` | P0 | draft | 0.1.0 | 每条条件追到定律并强制写出适用条件；数自由度与独立方程，判断定不定得下来 |
| `problem-representation-scout` | P0 | draft | 0.1.0 | 先按约束改变与冲量把过程切成阶段，再为每段配一个能回答本段问题的表示 |
| `reference-frame-choice-guide` | P1 | draft | 0.1.0 | 比较候选参考系要付的惯性力代价，强制列出换系后不变的量与只是表象变了的量 |
| `physics-mechanism-decomposer` | P0 | draft | 0.1.0 | 开放现象拆成机制清单：收支表查漏、标度律带指数、同量纲排序、配可分辨的观测量 |
| `dimensional-analysis-checker` | P0 | draft | 0.1.0 | 逐项查量纲：加减同量纲、两边一致、超越函数宗量无量纲；每个通过的项还要说出它代表什么物理贡献 |
| `concept-to-formula-deriver` | P1 | draft | 0.1.0 | 从守恒律或定义重建标准公式，每步标物理含义；假设写在真正用到它的那一步；终式可符号比对 |
| `symbolic-first-discipline-coach` | P1 | draft | 0.1.0 | 符号做到结构不再变化，与早代入数字并排对照，暴露约掉的量与只以组合出现的参数 |
| `fermi-estimation-coach` | P1 | draft | 0.1.0 | 显式因子分解，每个因子给低／中／高与证据档，算区间不算装饰小数；worksheet 有脚本校验 |
| `limiting-case-validator` | P0 | draft | 0.1.0 | 先写下物理上该发生什么，再做极限化简两相对照；专抓发散、变号、丢掉已知特例 |
| `answer-plausibility-checker` | P1 | draft | 0.1.0 | 单位、符号、量级、极限、参考值、守恒收支六项嗅觉测试；无标准答案时改用双锚点 |
| `derivation-step-checker` | P1 | draft | 0.1.0 | 逐步查代数、量纲、符号，外加定律的适用条件是否中途被悄悄破坏；前三项有脚本 |
| `uncertainty-propagator` | P1 | draft | 0.1.0 | 含相关项的协方差传播，给符号灵敏度、不确定度预算与蒙特卡罗对标；灵敏度大不等于贡献大 |
| `model-fit-auditor` | P1 | draft | 0.1.0 | 残差结构、带不确定度的拟合优度、杠杆与影响点、信息准则；残差有结构就是漏了物理 |
| `dataset-systematic-error-hunter` | P2 | draft | 0.1.0 | 扫漂移、温度依赖、非线性、滞回、重复不一致，每类归因到具体物理过程而非「数据有问题」 |
| `numerical-stability-auditor` | P2 | draft | 0.1.0 | 守恒量漂移曲线、步长收敛阶、功率谱鬼频；结果随步长变就先做收敛性检查 |

共用参考在 `skills/physics/_shared/`：证据契约与有效数字纪律、定律适用条件表、
理想化对照表、无量纲数表。确定性检查在 `skills/physics/_shared/scripts/dimcheck.py`
（纯标准库，`--selftest` 可跑）。

## study-planning — P0

学习规划、活动整理、反思与成长档案。Study planning and growth canvas.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `project-brainstorm` | P0 | draft | 0.1.0 | 项目动手前的全方位判断：去重已有积累，给三个带代价的方案 |
| `deadline-to-study-plan` | P0 | draft | 0.2.0 | 从截止日期倒推学习计划 |
| `weekly-study-review` | P0 | draft | 0.2.0 | 每周复盘与计划修正 |
| `activity-profile-builder` | P0 | draft | 0.2.0 | 整理活动经历档案 |
| `reflection-interviewer` | P0 | draft | 0.2.0 | 以访谈方式引导反思 |
| `admissions-reader` | P0 | draft | 0.2.0 | 以招生官视角点评现有档案与经历 |
| `activity-list-optimizer` | P0 | draft | 0.2.0 | 把活动描述压进 Common App 字符限额 |
| `application-timeline-builder` | P0 | draft | 0.2.0 | 从各校截止日倒推申请季节点 |

`physics/` 现已覆盖完整流水线的五组：入口分流、题面到可解结构、动手纪律、检错、数据与模拟。
八个确定性脚本分散在各 skill 的 `scripts/` 下，另有共享的 `_shared/scripts/dimcheck.py`。
除 `uncertainty-propagator`（需 sympy 与 numpy）与 `concept-to-formula-deriver`、
`derivation-step-checker`（需 sympy）外，其余脚本只用标准库。

## community-programs — P1

学生社群活动怎么从一个零散想法长成成熟项目。读书会、分享、讲座、Workshop、公共活动。
Turning a scattered activity idea into a program that survives.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `program-maturity-navigator` | P1 | draft | 0.1.0 | 按留下的痕迹判活动实际长到哪儿，用带证据清单的五道闸决定下一步；深度与广度是两个独立的轴 |
| `workshop-designer` | P2 | planned | — | 把成熟内容转成参与式任务、流程与交付物；等主控 skill 跑过几轮、输入输出稳定后再拆 |

活动形式的选择表、七份表单骨架（含停办记录）与本地词汇留在
`program-maturity-navigator/references/`，不单独拆成 skill——
形式选择只是一张表，脱离活动背景反而判不准。

## ai-usage — P1

用 AI 的纪律：给出去之前先把需求说清，拿回来之后先分级、先核实、先体检。
每个 skill 只解决一个具体痛点，脚本能兜底的绝不靠模型自觉。
Discipline for working with AI: specify before, triage and verify after.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `prompt-brief-builder` | P0 | draft | 0.1.0 | 一句话需求用至多 3–5 个追问补成九字段任务简报，字段完整性有脚本校验 |
| `ai-answer-triage` | P0 | draft | 0.1.0 | 把 AI 回答按声明类型分四级，每级配处置动作，按影响半径排序给最小的下一步检查 |
| `ai-output-fact-checker` | P0 | draft | 0.1.0 | 拆成可检验声明逐条配核验路径，专防引用了不存在的库、论文和命令 |
| `ai-code-onboarding-checklist` | P1 | draft | 0.1.0 | AI 生成代码的客观体检：体量、测试、占位符、密钥、依赖真实性；明写它查不了算法正确性 |
| `ai-diff-review-protocol` | P1 | draft | 0.1.0 | 按意图、边界、副作用、可逆性四步走查 diff，不逐行精读，有 pass/caution/stop 判据 |
| `ai-session-handoff-writer` | P1 | draft | 0.1.0 | 跨 session 或换人接手时的交接文档：决定带理由、事实与推断分标、重启须知 |
| `ai-generated-test-auditor` | P1 | draft | 0.1.0 | 查断言是否与实现同源复制、有无边界与异常用例、失败信号强不强；用突变抽样验证测试真能变红 |

`ai-session-handoff-writer` 与仓库根的 `templates/handoff-template.md` 不是一回事：
后者是子代理交回主代理的短单（同一 session，接手方已有上下文），前者是跨 session 的完整交接。

## skill-authoring — P0

写 skill 的 skill。把使用者反复用到的做法固定成可执行的 SKILL.md。Meta: authoring skills themselves.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `skill-creator` | P0 | draft | 0.3.1 | 先定位使用者在哪一步，写出草稿再问关键分歧，产出一份能跑的 SKILL.md |

## songwriting — P1

中文作词工作流（概念 → 骨架 → 对抗式填词 → 体检），以及让 LLM 写谱生成 MIDI 的工程方法。
Chinese lyric writing plus LLM-to-MIDI composition.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `llm-midi-composition` | P1 | draft | 0.1.0 | 两级调用让 LLM 写谱产 MIDI：蓝图 + 分谱、残稿抢救、确定性修复、降级如实标注 |
| `lyric-concept-builder` | P1 | draft | 0.1.0 | 动笔前定处境、意象系统、情绪弧线与 hook 候选 |
| `lyric-structure-mapper` | P1 | draft | 0.1.0 | 把 `xxxxx` 字数模板解析成骨架表，或给常用骨架 |
| `adversarial-lyric-writer` | P1 | draft | 0.1.0 | 三个 sonnet 子代理并行独立起草，红队逐句挑，主 Agent 按句裁决 |
| `lyric-doctor` | P1 | draft | 0.1.0 | 成稿体检：脚本查字数与陈词，模型判韵辙、画面感与 hook，出定点修改清单 |

共用手艺参考在 `skills/songwriting/_shared/craft-reference.md`（十三辙表、陈词黑名单、可唱性、模板读法）。

## writing — P1

中文写作风格约束与文体模仿。只在使用者点名时启用。Chinese prose style rules and style mimicry, opt-in only.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `zlc` | P2 | draft | 0.1.0 | 四拍点评句式：表态、否定加事实、价值、呼吁；褒贬三开关一起翻 |
| `writing-rules` | P1 | draft | 0.2.0 | 十五条反 AI 腔规则：禁破折号、禁"不是A，是B"、打破三点式、必须有立场、禁虚构细节、硬性禁用词表、写完即止 |

`zlc` 与 `writing-rules` 互斥，后者专门禁止这种升华腔。

## reading-notes — P1

从剧情概括走向真正的文本分析。From plot summary to real textual analysis.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `chapter-note-starter` | P1 | planned | — | 起草章节阅读笔记 |
| `literary-analysis-coach` | P1 | planned | — | 引导文本分析而非概括 |
| `quote-to-thought` | P1 | planned | — | 从引文推进到自己的观点 |
| `note-polisher` | P1 | planned | — | 打磨笔记表达 |

## research-coaching — P1

以教练视角辅助研究过程。Research coaching, not ghost-writing.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `research-question-coach` | P1 | planned | — | 打磨研究问题 |
| `literature-reading-coach` | P1 | planned | — | 指导文献阅读与筛选 |
| `experiment-design-guide` | P1 | planned | — | 引导实验设计 |
| `assumption-checker` | P1 | planned | — | 检查研究假设与漏洞 |

## competition-literacy — P1

答辩训练与竞赛 AI 使用边界。Defense practice and AI-use boundaries.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `competition-ethics-checker` | P1 | planned | — | 检查 AI 使用是否越界 |
| `opponent-question-practice` | P1 | planned | — | 模拟对手提问与答辩 |

## vocabulary-learning — P2

个性化词汇学习。Personalized vocabulary learning.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `vocab-error-diagnoser` | P2 | planned | — | 诊断词汇错误成因 |
| `personalized-review-scheduler` | P2 | planned | — | 生成个性化复习计划 |
| `example-sentence-builder` | P2 | planned | — | 生成贴合语境的例句 |

## photography — P2

摄影产物的确定性处理与克制写作：脚本兜底事实，模型只做判断。Photography outputs: scripts own the facts, the model owns judgment.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `photo-caption-writer` | P2 | draft | 0.1.0 | 基于拍摄者确认的事实与 EXIF 写图注或作品阐述，不从画面脑补情绪与意图 |
| `photo-exif-frame` | P2 | draft | 0.1.0 | 照片下方加信息带：光圈、快门、曝光补偿、ISO、时间、设备；缺字段留空不编造 |

## social-practice — P2

社会实践与影响力整理。Social practice and impact reporting.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `community-needs-interviewer` | P2 | planned | — | 社区需求访谈引导 |
| `service-project-planner` | P2 | planned | — | 服务项目规划 |
| `impact-report-builder` | P2 | planned | — | 整理影响力报告 |

---

## 状态说明 / Status legend

`planned` 规划中，尚未创建 · `draft` 结构在动 · `beta` 结构稳定，措辞在调 · `stable` 可依赖 · `deprecated` 已弃用

详见 [VERSIONING.md](VERSIONING.md)。
