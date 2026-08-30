# CHANGELOG

Library 级变更记录。单个 skill 的变更记在各自 `SKILL.md` 末尾的「变更记录」小节。
Library-level changes only; per-skill changes live in each `SKILL.md`.

递增规则见 [VERSIONING.md](VERSIONING.md)。最新的在最上方。

## 0.19.0 — 2026-08-30

**修复七个游离的 skill 目录。** 它们此前提交在仓库根目录（`ai-*`、`prompt-brief-builder`、
`dimensional-analysis-checker`），不在 `skills/` 下，因此 `validate.sh` 看不见它们，
`SKILL_INDEX.md` 与 `README.md` 也从未登记——等于写了但没装上。

- 新开 `ai-usage` 分类，六个 skill 移入 `skills/ai-usage/`：`prompt-brief-builder`、
  `ai-answer-triage`、`ai-output-fact-checker`、`ai-code-onboarding-checklist`、
  `ai-diff-review-protocol`、`ai-session-handoff-writer`
- `dimensional-analysis-checker` 移入 `skills/physics/`，是组三的第一个，
  索引里从 `planned` 改为 `draft`

frontmatter 全部按 `CONTRIBUTING.md` 归一：七个必填键补齐（此前多数只有
`name` / `description` / `version` 三个；`ai-output-fact-checker` 把 `description` 写成了
`summary`，`dimensional-analysis-checker` 用了非约定的 `tags`）。`outputs` 违反取值契约的
（`claim-ledger` 之类）改成 `chat` / `document`。description 一律改写成中文触发式，
与 `modeling`、`physics` 保持一致。

两处交叉引用补上，避免与新建的东西重复：

- `dimensional-analysis-checker` 的确定性路径改为优先用 `physics/_shared/scripts/dimcheck.py`
  （纯标准库，随处可跑），SymPy 只留给它做不了的事（无量纲组枚举、量纲矩阵求秩、代数化简）；
  并补上指向 `_shared/` 四份共享参考的 References。推荐邻居按实际状态标注，`planned` 的
  不再当作可调用
- `ai-session-handoff-writer` 补一节说清它与仓库根 `templates/handoff-template.md` 的分工：
  后者是同一 session 内子代理交回主代理的短单（接手方已有上下文），前者是跨 session 的完整交接。
  判据只有一句：接手方有没有本轮上下文

七份 `tests/cases/` 用例补齐，均含矛盾输入与边界违规两类场景——这是 `AUDIT-AND-IDEAS.md`
第一部分 B 节点名的缺口。用例覆盖了几个关键的诚实边界：量纲通过不等于公式正确
（系数错了照样通过）、体检通过不等于代码正确、一条声明为真不能给整段盖章、
没有 diff 就不给放行结论、密钥只写位置不写值。

## 0.18.0 — 2026-08-30

新开 `physics` 分类，落地 `AUDIT-AND-IDEAS.md` 里物理流水线的组〇与组一，共 6 个 draft skill（均从 `0.1.0` 起）：

- `physics-problem-router`：三个判别问题（答案唯一吗 / 什么算做完 / 卡在哪）定出类型、产物与卡点，
  再分流；专门检出"要一个数但问题是开放的"和"其实该先回去读题"两种走错门
- `competition-scenario-extractor`：竞赛题、IYPT 一句话题、文献段落、实验记录四类材料分别处理，
  压成干净题面、给定量台账、理想化台账、约束与子问题树；模糊措辞、符号单位冲突、
  未知与方程计数三项确定性检查
- `problem-formalization-coach`：每条条件追到定律，适用条件不写出来就不许往下推；
  区分完整与非完整约束数自由度；守恒律是首次积分而非额外方程；欠定就是欠定，不用"合理假设"补
- `problem-representation-scout`：阶段边界只有五种（约束改变、接触断开、摩擦切换、冲量、相变）；
  冲量极限下位置不能突变、速度能、有限力的冲量趋零；再按"要求的量里不含什么"选表示
- `reference-frame-choice-guide`：区分坐标轴旋转、伽利略变换与非惯性系三件事；
  给完整惯性力式（平动、科里奥利、离心、欧拉）；强制产出不变量清单
- `physics-mechanism-decomposer`：收支表与物理域清单双路枚举防漏；标度律必须带指数并标来源档；
  只比同量纲的量；可分辨观测量的判据是指数或符号不同，不是系数不同

共享参考拆为四份按需加载的文档：证据契约与有效数字纪律、定律适用条件表、理想化对照表、无量纲数表。
物理常数只写死 2019 年 SI 定义值（精确），测量值一律要求引用时注明 CODATA 版本与查阅日期——
这是 `AUDIT-AND-IDEAS.md` 的 A1 条（写死易变事实）在新分类上的落实。

`_shared/scripts/dimcheck.py` 是纯标准库的量纲检查器：解析符号量纲表与表达式，
检查加减两侧同量纲、指数对数三角函数的宗量无量纲、若干项是否同量纲可比，
并对未声明的符号报错（这正是"检出凭空补进来的量"）。带 `--selftest`，含五个必须被抓到的反例。

边界统一为拆解与检查：不解题、不列完整方程组、不给数值答案、不补条件、不虚构常数与文献；
作业与竞赛进行中只给结构与判据，不因催促放宽。六份测试用例都含矛盾输入与边界违规两类场景。

## 0.16.0 — 2026-08-17

新增完整的 `modeling` P0 工作流，共 9 个 draft skills（均从 `0.1.0` 起）：

- `modeling-problem-reading-coach`：把原题拆成题面契约、变量与单位、子问题依赖和待确认歧义
- `model-selection-tutor`：用简单基线、十道门槛与判别测试比较模型家族
- `modeling-assumption-builder`：区分事实、定义、设计选择、数值设置与真正假设，并为高风险假设设计反证
- `model-critique-coach`：从论文主张反向追到运行、模型、数据与假设，按对结论的影响分级
- `modeling-code-builder`：只实现学生确认的模型，强制小例、不变量、验证矩阵和 run manifest
- `paper-structure-coach`：用主张—证据图组织章节、段落和图表，阻止摘要结论越过正文证据
- `paper-enhancement-builder`：把真实 gap 排成有依赖、验收、失败退路和停止条件的最小修订计划
- `latex-paper-formatter`：冻结内容后处理 LaTeX 引用、表图、编译与 PDF 验收
- `team-role-coach`：按产物与决策分 owner / reviewer，以九个 Gate、交接包和冻结点组织协作

共享方法拆为五份按需加载的参考：状态与稳定 ID、验证与可辨识性、代码复现、论文论证、团队闸门。
所有技能同时声明 `claude-code`、`codex`、`cursor`、`codebuddy`、`nestudy` 与 `generic-llm-agent`，正文只依赖
语义动作；没有文件、执行、联网、写入、子代理或可视化能力时都有明确降级路径，不会把未运行写成已验证。

`latex-paper-formatter` 另带一个只用 Python 标准库的 `check_latex.py`，静态检查多文件输入、重复 / 未定义标签、
常用 natbib / biblatex 引用键、缺图、手工编号与遗留占位符，并限制所有读取在显式项目根内。合法、故障、
plural citation、路径逃逸与编码错误 fixture 已接入 `validate.sh`，JSON 输出和退出状态都有确定性验证。

边界统一为教练、批判、实现与格式化：不代写可直接提交的竞赛论文，不替学生隐藏模型决定，不虚构数据、结果、
来源、专家意见、团队贡献或检查状态。

## 0.14.1 — 2026-08-05

运行时改名：`compatible_agents` 里的 `studynest` 全部改为 `nestudy`（与域名 nestudy.cn 对齐），
README / CONTRIBUTING / 本文件里指向该运行时的说法一并更新。

只是换个名字，没有行为变化：`compatible_agents` 从来只做必填校验、不做匹配，
所以改名前写着 `studynest` 的 skill 装到哪儿都照跑。

## 0.6.0 — 2026-08-05

`study-planning` 新增 `project-brainstorm`（`0.1.0` / draft），该集合补到 8 个。

**项目动手之前的那一步，此前整个库是空的。** 已有的 skill 都从"项目已经定了"开始——
排计划、录档案、写反思。而学生真正卡住的地方在更前面：不是没有想法，
是没法判断哪个想法真做得动。

三条设计要点：

- **不问"你对什么感兴趣"**。这问题学生答不好，而且档案与已有经历里读到的东西比他临时
  想出来的答案准。直接给三个方案，**在代价上拉开**（几周 / 一学期 / 一年以上），
  每个写满五项：第一件事、要什么、做完手里有什么、可能死在哪、和已有的关系。
- **「可能死在哪」是五项里最有用的一项**。学生放弃项目的原因通常在开始时就看得见——
  需要学校批但没人牵头、需要连续三个月投入但下学期是大考季。说出来比列十个优点有用。
- **先去重再数积累**。学生的反思、复盘、活动记录里同一件事会出现好几遍，
  不合并就会把"三条记录"读成"三件事"，据此劝他别做一个其实还很空的方向。
  这一步用运行时新增的 `dedupe_findings`（nestudy 侧）：链接规范化 + 字面重合度，
  确定的部分由代码做，**语义上算不算一回事仍然是判断题**，工具只把中间地带的成对结果
  报出来交给模型看。

网页检索的部分等 nestudy S11 的 `web_search` 落地后接入——去重本身不需要改动，
它只认 `{title, url, text}` 这个形状，不关心结果从哪来。

## 0.5.0 — 2026-08-04

全部 8 个 skill 升到 `0.2.0`，统一转向**先产出、少提问**。

改的是同一个毛病：这批 skill 第一版都写成了"问齐了再动手"，
跑起来就是一轮问一句、每句都叫「最后一个问题」，学生要敲五六次字才等到第一个成品。
而多数人**说不清自己要什么，却一眼能看出眼前这版哪里不对**——
先给一版带着显式假设的东西，比先问一轮再动手快得多，也准得多。

新的统一姿势：

1. **能读的去读，能默认的先做**。缺信息不是停下来的理由，是把假设写在最上面的理由。
   藏起来的假设才有害，写出来的假设是给学生的靶子。
2. **要问就一次问完**，用新的 `ask_user` 能力出一张带选项的卡（最多 4 问），
   而不是在正文里叮嘱"不要挤牙膏"——那句话写了三遍也没管住。
   只问**会改变产出方向、且只有本人知道**的事：每天真有多少时间、ED 走哪一轮、这条描述该保哪句。
3. **不为确认而确认**。"要不要我帮你写"、"这样可以吗"、"确认保存吗"一律删掉——
   提案卡本身就是那次确认。

按 skill 的主要改动：

- `deadline-to-study-plan` — 按"每天 2 小时"直接排出第一版并写明假设，同一轮问可用时间与固定安排。截止日不明仍是唯一先停下来的一问。
- `weekly-study-review` — 对账段直接写出来（数据都在，不需要问任何人）；归因改成带选项的选择题，两件未完成一次问完，不再一次只问一件。
- `activity-profile-builder` — 从"逐项追问到齐"改成"一次听完口述直接拆成六字段表格，缺项标「待补」"。**留空是正确结果不是失败**：逼学生现在编一个成果出来，比空着有害。
- `activity-list-optimizer` — 一次量完全部条目并给出全部压缩版；砍虚词形容词直接做，只有砍到实质内容才用选择题问该保哪句。
- `application-timeline-builder` — 已核实的学校照排完整时间线，不因为有一所待确认就整份都不给；轮次选择（ED 是有约束力的承诺）用选择题问。
- `admissions-reader` — 开场不问问题，读完直接评；`ask_user` 只用在点评**之后**的"想深挖哪一块"。
- `skill-creator` — 从访谈式改成"查完能力直接贴一份完整草稿"，自己拿的主意全部标出来，关键分歧（触发场景 / 要不要写库 / 边界）一次问完。
- `reflection-interviewer` — **唯一保留慢慢问的 skill**。替学生写一版反思让他改，写出来的就是你的反思不是他的，这里先产出是错的。只把可穷举的两处（选哪段经历、连哪条边）改成选择题，开放访谈仍然一次一问；删掉"先贴全文再问对不对"那一轮——提案卡本身就是回读确认。

`ask_user` 是 nestudy 运行时新增的能力（`kind: ask`：不碰数据，出一张选择题卡然后停机等人）。
八个 skill 一律把它放在 **`optional_capabilities`** 而不是 `capabilities`——
这不是保守，是新姿势的自洽：每个流程都必须在问不了的时候仍然走得完（按默认值做出来并写明假设），
那它就不是必需能力。Claude Code 里没有这个工具，同一份 SKILL.md 照样跑得动。

## 0.4.0 — 2026-08-04

新增集合 `skill-authoring`（写 skill 的 skill），首个成员：

- `skill-creator`（`0.1.0` / draft）— 访谈式产出一份能跑的 `SKILL.md`。三条设计要点：
  **先查能力再动笔**（能力名由运行时定义，凭印象写必然声明出不存在的名字，那个 skill 装上去就是坏的）；
  **「什么时候用它」要到使用者的原话**（description 是 agent 判断该不该触发的唯一依据，写空了技能就永远不会被想起来）；
  **「绝对不做什么」是必问项**——好技能与坏技能的差别多半在边界上，而作者一开始想不到要写边界。
  要的能力运行时没有就直说，不写"看起来能跑、实际调不到工具"的壳。

## 0.3.0 — 2026-08-04

`study-planning` 第一批建成，新增 6 个 skill（均 `0.1.0` / draft），该集合从 1 个补齐到 7 个：

- `deadline-to-study-plan` — 从截止日倒推出**有交付物**的阶段性节点。不排满、不编造截止日、不给「每天学两小时」这类无法验收的任务。
- `weekly-study-review` — 基于实际完成情况而非感受做周复盘，产出复盘文档 + 下周调整动作。判据只有一条：下周会因此做什么不一样的事；说不出就如实说这次复盘没有产出。
- `activity-profile-builder` — 把口述的活动经历追问成结构化档案。只记录学生说出口的内容，成果为空就留空，级别按事实判定不往高了写——背景注水正是从这一步开始的。
- `reflection-interviewer` — 一次一个问题的 STAR 访谈，产出保留原话问答的反思资产，并提案经历之间的关联边。取代运行时里写死的六题模板：写死的模板只能问同样的六个问题，而访谈的价值恰恰在于顺着回答追问。
- `activity-list-optimizer` — 把已写好的活动描述压进 Common App 字符限额，每改一版都用工具重新数字符（表单按 UTF-16 计，emoji 占 2 格）。**压缩学生已写出的内容是编辑，在空白处替他写是代写**，本 skill 只做前者。
- `application-timeline-builder` — 从各校截止日倒推申请季节点并换算北京时间。未核实的截止日一律不猜，要求先去官网确认。

这一批统一守住一条边界：**只整理与追问学生已有的内容，不代写应由学生本人产出的申请材料**；所有写入都走提案确认。

## 0.2.0 — 2026-08-03

- 新增 skill `admissions-reader`（`skills/study-planning/admissions-reader/`，`0.1.0` / draft）：以顶尖大学招生官视角通读学生档案与经历，只读不写。
- frontmatter 增加一组**可选**的运行时扩展键，供 nestudy 这类 SKILL.md 运行时读取：`display_name`、`capabilities`、`optional_capabilities`、`outputs`、`max_rounds`、`suggest_hint`。这些键不进必填集合，`scripts/validate.sh` 不拒绝额外键，Claude Code 也忽略未知键——同一份 SKILL.md 因此在两边都能用，不需要 fork 格式。
