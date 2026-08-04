# Agent Skills Library

个人可复用 Agent 技能库 · A personal, reusable Agent skills library.

---

## 1. 项目定位 / What this is

**中文**

这是我的个人 **Agent Skills Library**，用于维护一组可复用的 Agent skills，供不同 AI Agents 调用，而不只服务某一个平台。它不是普通代码项目，而是一个持续增长的 Agent 工作流技能库。

核心目标：

- 集中维护可复用的 Agent skills
- 尽量让 skills 跨不同 Agents 使用
- 按主题分类，按优先级建设
- 每个 skill 使用统一结构
- 管理仓库、单个 skill、核心 workflow 三层版本
- 帮助 Agent 更清晰、更省 token、更可控地产出结果
- 避免替代学生思考，避免生成不诚信的学术成果

**English**

A personal Agent Skills Library: a growing collection of reusable agent workflow skills meant to be callable by multiple AI agents, not tied to one platform. Goals: one place for reusable skills, cross-agent portability, topic-based organization with explicit priorities, a uniform per-skill structure, three-layer versioning, and clearer / cheaper / more controllable agent output — without replacing student thinking or producing academically dishonest work.

---

## 2. 仓库组织方式 / Repository organization

现阶段使用 **一个总仓库** 管理所有 skills，按主题建立目录。只有当某个集合需要独立工具链、CI、包发布或社区维护时，才考虑拆分为独立仓库。

Single repository for now, organized by topic. Split out only if a collection outgrows it (own toolchain, CI, package release, community maintenance).

```text
Skills/
├── README.md
├── SKILL_INDEX.md              # 全部 skills 索引 / index of all skills
├── VERSIONING.md               # 三层版本规则 / versioning rules
├── CONTRIBUTING.md
├── templates/
│   ├── skill-template.md
│   ├── handoff-template.md
│   ├── edit-plan-template.md
│   ├── project-brief-template.md
│   └── release-note-template.md
│
├── skills/                     # 插件加载入口 / plugin skill root
│   ├── coding-helper/
│   ├── modeling/
│   ├── study-planning/
│   ├── reading-notes/
│   ├── research-coaching/
│   ├── competition-literacy/
│   ├── vocabulary-learning/
│   └── social-practice/
│
├── .claude-plugin/             # 插件与 Marketplace 清单 / manifests
├── agents/                     # 专用子代理 / specialized subagents
├── hooks/                      # 生命周期钩子 (hooks.json)
├── scripts/                    # 校验与确定性脚本 / validation & deterministic utils
└── tests/                      # cases/ 与 fixtures/
```

主题目录放在 `skills/` 下，这样既保留按主题分类，也能被 Claude Code 作为插件直接加载（每个 skill 一个 `SKILL.md`）。MCP / LSP 配置放在插件根目录：`.mcp.json`、`.lsp.json`。不要把组件目录放进 `.claude-plugin/`，那里只放清单。

Topic folders live under `skills/` so the layout stays topic-based while remaining loadable as a Claude Code plugin (one `SKILL.md` per skill). `.mcp.json` / `.lsp.json` belong at the plugin root; `.claude-plugin/` holds manifests only.

---

## 3. 本仓库将创建的 skills 集合 / Skill collections in this repo

> 我会一次创建 `coding-helper`、`modeling`、`study-planning`、`reading-notes`、`research-coaching`、`competition-literacy`、`vocabulary-learning` 和 `social-practice` 这几个 skills 集合，并将它们都放在这个仓库里。现阶段所有相关 skills 都在同一个仓库中按主题分类维护；如果未来某个集合发展成独立大型项目，再考虑拆分为单独仓库。

All eight collections are created together and maintained in this single repository, organized by topic; a collection is split out only if it later becomes a large standalone project.

---

## 4. 优先级规划 / Build priorities

### P0 — 第一批 / First wave

**1. Coding Helper** — 优先建设，因为它反过来帮助开发和维护其他 skills。Built first because it helps build everything else.

| Skill | 用途 |
|---|---|
| `coding-project-brief-builder` | 项目立项与需求收敛 |
| `architecture-planner` | 架构与模块规划 |
| `repo-map-compressor` | 生成 repo map，压缩上下文 |
| `context-budget-planner` | 规划 token 预算 |
| `edit-plan-builder` | 改代码前先写编辑计划 |
| `patch-scope-controller` | 控制 patch 范围，小步修改 |
| `multi-agent-task-router` | 多 Agent 分工调度 |
| `test-debug-loop` | 测试—调试闭环 |

目标 / Goals：用自定义版本号系统管理开发；降低 token 消耗；明确项目规划、编辑计划、修改计划、代码实现、测试验证、成果转化流程；支持多 Agent 分别做规划、编写、审查、测试、文档；控制 Agent 小步修改，不乱改、不跑偏。

核心流程 / Core flow：

```text
项目规划 → 上下文压缩 → 编辑计划 → 代码实现 → 审查与调试 → 成果产出与转化
plan → compress context → edit plan → implement → review & debug → deliver
```

**2. Modeling**

`modeling-problem-reading-coach` · `model-selection-tutor` · `modeling-assumption-builder` · `model-critique-coach` · `paper-structure-coach` · `paper-enhancement-builder` · `latex-paper-formatter` · `modeling-code-builder` · `team-role-coach`

目标：帮助学生理解建模题目、构建假设、比较模型、批判方案、优化论文结构、整理 LaTeX、基于学生已有思路辅助写代码。

边界 / Boundaries：只做指导、解释、批判、格式化和优化；不替学生虚构模型、数据、实验或结果；不替代学生思考。

**3. Study Planning / Growth Canvas**

`deadline-to-study-plan` · `weekly-study-review` · `activity-profile-builder` · `reflection-interviewer` · `admissions-reader` · `activity-list-optimizer` · `application-timeline-builder`

目标：支持学习规划、活动整理、反思访谈、生涯规划和成长档案建设。

已建成 / Built:

| Skill | 用途 |
|---|---|
| `deadline-to-study-plan` | 从截止日倒推出有交付物的阶段性节点并落进日程；不排满、不编造截止日 |
| `weekly-study-review` | 基于实际完成情况做周复盘，产出复盘文档与下周的调整动作；判据是「下周会做什么不一样的事」 |
| `activity-profile-builder` | 通过追问把口述的活动经历整理成结构化档案；只记录学生说出口的内容，级别按事实判定 |
| `reflection-interviewer` | 一次一个问题的 STAR 反思访谈，产出保留原话的反思资产与经历之间的关联；不替学生总结 |
| `admissions-reader` | 以顶尖大学招生官视角通读档案与经历，指出亮点、短板与下一步；只读不写，不代写申请材料 |
| `activity-list-optimizer` | 把已写好的活动描述压进 Common App 字符限额，每版都用工具复核字符数；只压缩，不代写空白 |
| `application-timeline-builder` | 从各校截止日倒推申请季节点并换算北京时间；未核实的截止日一律要求先去官网确认 |

这一组的共同边界 / Shared boundaries：**只整理与追问学生已有的内容，不代写应由学生本人产出的申请材料**；
所有写入都以提案形式交由学生确认；不给录取概率，不虚构未提供的经历、成果或日期。

### P1 — 第二批 / Second wave

**4. Reading and Notes** — `chapter-note-starter` · `literary-analysis-coach` · `quote-to-thought` · `note-polisher`
目标：帮助学生从剧情概括走向真正的阅读理解、文本分析和笔记表达。

**5. Research Coaching** — `research-question-coach` · `literature-reading-coach` · `experiment-design-guide` · `assumption-checker`
目标：从老师/教练角度辅助学生提出研究问题、阅读文献、设计实验、检查假设。

**6. Competition Literacy** — `competition-ethics-checker` · `opponent-question-practice`
目标：训练答辩、对手提问、竞赛表达，并检查 AI 使用是否越界。

### P2 — 后续扩展 / Later

**7. Vocabulary Learning** — `vocab-error-diagnoser` · `personalized-review-scheduler` · `example-sentence-builder`
目标：服务个性化词汇学习、错因诊断、复习计划和例句生成。

**8. Social Practice** — `community-needs-interviewer` · `service-project-planner` · `impact-report-builder`
目标：支持社会实践、社区需求访谈、服务项目规划和影响力报告整理。

---

## 5. Coding Helper 重点说明 / Focus notes

`coding-helper` 是本仓库的优先核心之一，关注：

- 自定义版本号系统
- 低 token 编程工作流
- 先规划项目，再编辑代码
- 改代码前先写 edit plan
- 计划变化时先写 revision plan
- 小步 patch，控制修改范围
- 多 Agent 分工完成规划、实现、审查、测试、文档
- 将最终成果转为 README、demo script、release notes、部署说明或项目复盘

降低 token 消耗的关键方法 / Token-reduction methods：

**1. 上下文压缩 / Context compression**

- 不默认读取整个仓库
- 先生成 repo map
- 只读取当前任务相关文件
- 压缩长日志和长历史
- 将项目状态写入文件，而不是一直放在聊天上下文中

**2. Prompt caching / 稳定提示**

- 固定长期不变的工作流规则、输出格式、风格规则和安全边界
- 区分 stable context 和 dynamic task context
- 每次任务只更新动态部分

**3. 多 Agent 上下文隔离 / Context isolation**

- 不同 Agent 分别负责规划、读项目、实现、审查、测试和文档
- 每个 Agent 只接收自己需要的上下文
- 子 Agent 返回短 handoff，而不是长推理日志

---

## 6. 版本号系统 / Versioning

三层版本 / Three layers：

```text
Library Version   整个 Skills 仓库版本 / whole repository
Skill Version     单个 skill 版本 / individual skill
Workflow Version  可复用工作流版本 / reusable workflow
```

规则 / Rules：

```text
0.x.x   实验 / 草稿阶段        experimental / draft
1.0.0   稳定可用版本          first stable release
MAJOR   破坏性结构变化        breaking structural change
MINOR   新增 skill 或新增能力  new skill or new capability
PATCH   措辞、示例、边界或文档修正  wording, examples, boundaries, docs
```

每个 skill 的 metadata 示例 / Per-skill metadata:

```yaml
name: repo-map-compressor
category: coding-helper/token-efficiency
version: 0.1.0
status: draft
priority: P0
compatible_agents:
  - openclaw
  - claude-code
  - cursor
  - codebuddy
  - generic-llm-agent
```

本仓库不使用全局 CLAUDE.md 中的项目版本号规则。This repo does not apply the global project versioning rules.

---

## 7. 本地校验与安装 / Local validation & install

```sh
./scripts/validate.sh
claude --plugin-dir "$(pwd)"
```

第一条是硬性门槛，检查：目录结构与必需文件、插件与 Marketplace 清单一致（含 Library Version 两处相同）、每个 `SKILL.md` 的 frontmatter 完整且合法（`name` 与目录同名、`category` 与所在目录一致、semver、`status` 与版本区间匹配、`priority` 合法）、每个 skill 在 `tests/cases/<name>.md` 有非空用例、且已在 `SKILL_INDEX.md` 与本 README 登记。第二条把仓库作为本地插件加载，用于在发布前测试每个组件。

`validate.sh` checks layout, manifest consistency, per-skill frontmatter, a non-empty test case, and registration in both the index and this README.

新增 skill 时从 [templates/skill-template.md](templates/skill-template.md) 起草，路径为 `skills/<category>/<skill-name>/SKILL.md`。版本规则见 [VERSIONING.md](VERSIONING.md)，全部 skills 见 [SKILL_INDEX.md](SKILL_INDEX.md)。

公开发布前：替换 Marketplace 占位 owner、选择正式 license、必要时更新插件名。发布后可通过 Marketplace 安装：

```text
/plugin marketplace add <GitHub-owner>/<repository>
/plugin install skills-library@skills-library
```

---

## 8. 每个 skill 的基本要求 / Requirements per skill

- 用途单一、边界明确 / narrow purpose, documented boundaries
- 清晰的 `description`，便于 Agent 正确触发 / clear description for reliable triggering
- 至少一个可重复的测试用例（`tests/cases/`）/ at least one repeatable test case
- 确定性工作放进脚本；参考资料放在 skill 目录内，按需加载 / deterministic work in scripts, references loaded on demand
- 最小权限的工具访问 / least-privilege tool access
- 不提交任何凭据或私有端点 / never commit credentials or private endpoints

贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。See CONTRIBUTING.md for the review workflow.
