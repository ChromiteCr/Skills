# SKILL INDEX

全部 skills 的索引。**新增 skill 必须在此登记**，`./scripts/validate.sh` 会校验。
Index of all skills. Every skill must be registered here; validation enforces it.

登记格式：一行一个 skill，`| skill | 优先级 | 状态 | 版本 | 一句话用途 |`。
未建成的 skill 状态写 `planned`，版本留 `—`。

Library Version: `0.5.0`

---

## coding-helper — P0

低 token、可控、多 Agent 协作的编程工作流。Token-efficient, controllable, multi-agent coding workflow.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
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
| `modeling-problem-reading-coach` | P0 | planned | — | 拆解建模题目与隐含条件 |
| `model-selection-tutor` | P0 | planned | — | 比较候选模型的适用性 |
| `modeling-assumption-builder` | P0 | planned | — | 梳理并检验模型假设 |
| `model-critique-coach` | P0 | planned | — | 批判方案的弱点与反例 |
| `paper-structure-coach` | P0 | planned | — | 优化论文结构与论证链 |
| `paper-enhancement-builder` | P0 | planned | — | 提出论文可改进项 |
| `latex-paper-formatter` | P0 | planned | — | 整理 LaTeX 格式与规范 |
| `modeling-code-builder` | P0 | planned | — | 基于学生已有思路辅助写代码 |
| `team-role-coach` | P0 | planned | — | 团队分工与协作节奏 |

## study-planning — P0

学习规划、活动整理、反思与成长档案。Study planning and growth canvas.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `deadline-to-study-plan` | P0 | draft | 0.2.0 | 从截止日期倒推学习计划 |
| `weekly-study-review` | P0 | draft | 0.2.0 | 每周复盘与计划修正 |
| `activity-profile-builder` | P0 | draft | 0.2.0 | 整理活动经历档案 |
| `reflection-interviewer` | P0 | draft | 0.2.0 | 以访谈方式引导反思 |
| `admissions-reader` | P0 | draft | 0.2.0 | 以招生官视角点评现有档案与经历 |
| `activity-list-optimizer` | P0 | draft | 0.2.0 | 把活动描述压进 Common App 字符限额 |
| `application-timeline-builder` | P0 | draft | 0.2.0 | 从各校截止日倒推申请季节点 |

## skill-authoring — P0

写 skill 的 skill。把使用者反复用到的做法固定成可执行的 SKILL.md。Meta: authoring skills themselves.

| Skill | 优先级 | 状态 | 版本 | 用途 |
|---|---|---|---|---|
| `skill-creator` | P0 | draft | 0.3.1 | 先定位使用者在哪一步，写出草稿再问关键分歧，产出一份能跑的 SKILL.md |

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
