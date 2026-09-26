# CHANGELOG

Library 级变更记录。单个 skill 的变更记在各自 `SKILL.md` 末尾的「变更记录」小节，或该 skill 目录下的 `CHANGELOG.md`（`keynote-deck-builder` 从 0.7.1 起用后者）。
Library-level changes only; per-skill changes live in each `SKILL.md`.

递增规则见 [VERSIONING.md](VERSIONING.md)。最新的在最上方。

## 0.22.4 — 2026-09-26

第二轮审计（`AUDIT-AND-IDEAS.md` 第一部分）的修复。没有新增或删除 skill，Library 按规则记 PATCH；
57 个 skill 各升一版（多数 PATCH，四 个 MINOR），细节记在各自的变更记录里。

**插件装上就能用（A1）**

- `plugin.json` 加上 `skills`，列出十个分类目录。Claude Code 只扫 `skills/` 的直接子目录，技能在下一层，
  所以此前按 README 安装，一个 skill 都加载不到；无头会话实测从 0 个变成 61 个。
- 删掉从未运行过、也没有被任何地方调用的 `scripts/sync-skill-links.sh`。

**校验、打包与提交前检查（G）**

- `validate.sh` 补上审计列出的盲区：分类目录必须列进 `plugin.json`；`SKILL_INDEX.md` 的优先级、状态、版本三列
  逐列比对 frontmatter，建成的 skill 不能还写 planned；`skills/` 以外的 SKILL.md；缩进的 frontmatter 键；
  skill 目录里的第二份测试；没有中文触发语的 description；与插件清单冲突的 `license`；README 徽章数；
  `../` 引用的共享文件与兄弟 skill 文件必须存在；共享代码各副本的 sha256 必须一致。
- 新增 `scripts/package.sh`：单技能 zip 改由脚本打，文件名带版本（`dist/<skill>-<version>.zip`），
  被引用的 `_shared` 文件和兄弟 skill 的脚本一起放进 zip 的 `<skill>/_shared/` 并改写路径；`--check` 报告缺失或过期的包。
  此前 20 个 skill 的 zip 缺共享文件，`keynote-deck-builder.zip` 还停在 0.6.0。`dist/` 已全部重打。
- 新增 `scripts/run-selftests.sh`：跑所有带 `--selftest` 的脚本，相同的共享副本只跑一次。
- 新增 `scripts/git-hooks/pre-commit`：提交前跑 `validate.sh` 和这次改动到的 skill 的脚本自检。
  每个克隆启用一次：`git config core.hooksPath scripts/git-hooks`。0.22.2 那次 Library Version 漂移，脚本本来查得出，只是没人跑。

**脚本不再静默给错结论（A3、A4、A5）**

- 物理十个脚本全部带上 `--selftest` 与 `--help`，未知键和未声明的符号一律报错，不再静默：
  - `_shared/scripts/dimcheck.py`：`[check]` 里的方程两边真的比对（原来被当成"名字 = 表达式"，量纲不一致也报"全部通过"）；
    `^1/2` 这类不加括号的分数指数以退出码 2 拒收；`µ` 等兼容字符按 NFKC 归一；输入写法错误退出码 2，量纲结论 1。
  - `compare_formula.py`：名字一律按普通符号解析（`I`、`E` 不再被当成虚数单位和自然常数，`lambda`、`gamma` 不再崩溃）；
    默认正值假设，`--real` 可关；判"不等价"必须给出数值反例；退出码分成 0 等价 / 1 不等价 / 2 输入错误 / 3 无法判定。
  - `check_derivation.py`：`… = 0` 不再误判量纲；符号指数要求无量纲；`nonzero` 可写表达式并逐个因子核对，
    只声明 m1、m2 不再放行除以 m1−m2。
  - `hunt_systematics.py`、`audit_fit.py`：拟合改在中心化、缩放后的自变量上做（后者用列主元 QR 与相对秩容差，并校验杠杆值之和等于秩），
    Unix 时间戳与 SI 小量不再给出负的 SSE 降幅、误报秩亏或错误的杠杆值；时间列认 ISO 8601，没有可用行时报错而不是 n=0 照常退出。
  - `check_estimate.py`：product 合成按各机制单位相乘再比对目标单位（原规则只有谎标单位才能通过）。
  - `check_plausibility.py`：不确定度相容改用 z 值（输入按 k=1 的标准不确定度），1.56σ 不再判失败。
  - `propagate_uncertainty.py` 不再把未声明的 `E` 当欧拉数；`check_limit_manifest.py` 不再把空 manifest 判"结构完整"；
    `audit_stability.py` 自收敛允许两个差值并警告，均匀采样容差按时间列的打印精度算。
- `check_latex.py`：按主文件目录解析 `\input` 与参考文献；macOS 上也查得出图片路径的大小写错误；查中文"公式 (3)""式（5）"手工编号；
  照 SKILL.md 从 skill 目录运行能读到论文。
- `lyric_check.py`：段名按"精确 → 去编号归一 → 对不上就报"匹配，重复段不再被静默跳过；认【主歌】、主歌：；
  模板里的全角空格与 `--extra` 的全角逗号生效；陈词黑名单与 `craft-reference.md` 同步（补"这就是最好的"）。
- `check_program.py`：拼错的键、未来日期、非整数人数报输入错误；到场 0 人的场次不计；`external_inputs` 生效。
- `check_brief.py`：只有占位的节判空，SKILL 自带的空模板不再通过；标题行尾多一个空格不再把整节判空。
  `check_test_audit_manifest.py`：接受正文用语（mirrored logic 等），传目录不再抛异常。
- 新脚本 `ai-diff-review-protocol/scripts/diff_risk.py`：兑现 description 早就写着的"统计由脚本出"。纯标准库，能读粘贴进聊天的 diff，
  出文件与增删行、边界分类、危险 hunk、锁文件新增包和阈值，越线必须人工逐段过。
- 摄影：新增共享模块 `image_io.py`（五个 skill 各放一份相同副本，`validate.sh` 查 sha256），统一处理 EXIF 转正、ICC、HEIC 提示、
  有汉字字形的字体、不覆盖输入。`extract_exif.py` 读 Exif 子 IFD（原来相机 JPEG 的光圈、快门、ISO、焦距、镜头、拍摄时间全是 null）；
  信息带字号按格宽倒推，不再落到 10px；回顾卡中文标题不再是方块，`--output` 不能再指向原片；拼版里竖拍不再横躺、照片不再注入两次；
  组照实现了 references 写的 auto 排布；海报 validate 按 viewBox 坐标查边界，并检查 path 与文字。
  拍摄时间只取 DateTimeOriginal；Display P3 照片输出后不再发灰。
- `keynote-deck-builder` 0.7.1：`read_pptx.py` 递归读组合形状里的字，`inline_images.py` 把被认成 MPO 的 JPEG 当 JPEG 收，
  `outline_to_pptx.py` 的放不下与孤行自检扩到每个会折行的文本框，降级表补上五类片型；四个脚本都认 `--help`、带 `--selftest`。
  **pptx 导出没变**：用改动前的两份示例片单重新导出（带动画与 `--static` 各一次），与改动前逐部件相同。
  SKILL.md 从 73,628 字节降到 54,950 字节：变更记录移进 skill 目录的 `CHANGELOG.md`，只在特定场合用到的几节原样移进 `references/` 并写明读取条件。
- 现在 `./scripts/run-selftests.sh` 覆盖 28 个脚本，全部通过。

**正文、用例与边界**

- A2：`physics-problem-router` 把 9 个已建成的 skill 标成"计划中"并叮嘱别调用，改为可用并逐个点名，补上两个漏掉的下游；
  `physics-mechanism-decomposer`、`dimensional-analysis-checker` 的同类说法与两份惩罚正确分流的用例一并改掉。
- C（内容错误）：滑动→纯滚动的判据、积分形式法拉第通量法则的适用条件（法拉第圆盘是反例）、π 定理降秩的例子、
  准静态与绝热（时间尺度窗口内可以同时成立）、`craft-reference.md` 的开口辙定义（按表格「拖长时」一列统一）、
  歌词时长改按 BPM 推算、DOI 核对（标题必须一致）、包名存在不等于可信（可能被抢注）、`model-fit-auditor` 对残差结构的说法，逐条改正。
- D（学术诚信）：受评任务的边界补齐：`modeling-code-builder` 与共享工作契约、`symbolic-first-discipline-coach`、`fermi-estimation-coach`、
  `project-brainstorm` 的 EE/IA 选题、`dimensional-analysis-checker` 的无条件条款；两处指向不存在的"文书类 skill"改为"本库不代写，只帮改学生自己的稿"。
- E（运行时专有工具）：13 个 skill 的正文依赖 nestudy 工具或 Claude Code 子代理，却声明其他运行时兼容。
  各补「没有这些工具时（降级）」一节，给出可运行的替代命令（UTF-16 字符计数、`zoneinfo` 时区换算并提示夏令时切换），输出标"降级"。
- F（分流）：摄影五个 skill 的 description 补中文触发语；spread-composer 与 series-layout、triage 与 fact-checker 与 onboarding、
  diff-review 与 test-auditor、modeling 与 physics、brainstorm 与 navigator、reflection 与 activity-profile 各写判别句；泛称路由全部换成实名。
- B（正文与脚本、用例互相矛盾）逐条对齐，例如：`ai-code-onboarding-checklist` 补上 description 承诺的危险调用检查（MINOR）；
  `ai-generated-test-auditor` 改说"规划 2–5 个突变抽样，能执行时再实跑"；handoff 的节数与密钥规则；`maestrwave-ui-system` 自带 CSS 收回五档字号，
  `.field-label` 由 48% 提到 52%，对比度过 AA；`radio-quote-card` 按实渲染另立中文字号档；`launch-summary-panel` 小卡圆角统一。
- H（第一轮遗留）：`modeling-code-builder` 的两条评估用例移进 `tests/cases`；`program-maturity-navigator` 注明 catena 只是内部代号；
  `activity-list-optimizer` 补"工具限额过期要报告"的用例。
- G：两个摄影 skill 删掉与插件清单矛盾的 `license: MIT`；三个摄影 skill 目录里的测试副本并入 `tests/cases` 后删除。
  新增的测试夹具都在 `tests/fixtures/<skill>/` 下，全是合成的小文件。

**文档**

- `CONTRIBUTING.md` 按实际做法改写：直接提交到 `main`，提交前必须跑 `validate.sh`；新增 3.2 节「只有某个运行时才有的工具」
  （要么缩小 `compatible_agents`，要么写降级一节并标注"降级"）与 3.3 节「共享文件与共享代码」。
- `VERSIONING.md` 发布步骤补 `run-selftests.sh` 与 `package.sh`，tag 改为可选。
- `templates/skill-template.md` 的 `compatible_agents` 默认值改成与 README 一致（去掉 openclaw，补 codex、nestudy）。
- README：physics 十个条目移回 Physics 小节；"token 纪律在 coding-helper"改为如实说明尚未建成，并补进 Not written yet；
  兼容性一节写明运行时专有工具的规则。`SKILL_INDEX.md`：physics 说明段移回 physics 小节，脚本数更正为九个；
  coding-helper 与 physics 的分类说明改为如实描述现有成员。

**更正（历史条目不改，在此注明）**

- 漏记了 8 个 Library 版本：0.7.0（2026-08-10，新增 `ui-design-system-builder`）、0.8.0（08-10，`maestrwave-ui-system`）、
  0.9.0（08-10，`writing-rules`）、0.10.0（08-11，`adversarial-lyric-writer`、`lyric-concept-builder`、`lyric-doctor`、
  `lyric-structure-mapper`）、0.13.0（08-12，`launch-summary-panel`、`llm-midi-composition`、`zlc`）、
  0.14.0（08-13，`radio-quote-card`）、0.15.0（08-16，`keynote-deck-builder`）、0.17.0（08-26，`photo-spread-composer`）。
- 下面的 0.18.0 与 0.20.0 两条从未作为版本号出现在 `plugin.json`：实际是 0.17.0 → 0.19.0 → 0.21.0，
  两条的内容分别随 0.19.0 与 0.21.0 发布。
- 0.14.1 的日期应为 2026-08-14。
- 0.20.0 写"八个新脚本逐个实跑验证过"，后面列的是十个脚本。
- 0.19.0 说补齐的七份用例"均含矛盾输入与边界违规两类场景"；`prompt-brief-builder` 那份当时没有矛盾输入，本版补上（Case 5）。

## 0.22.3 — 2026-09-18

`keynote-deck-builder` 升到 0.7.0：pptx 导出带上动画。Library 层只动了索引与 README 的描述，按规则记 PATCH；
skill 本身的改动细节记在它自己的变更记录里。要点：

- 新脚本 `pptx_motion.py` 直接写 PresentationML 的 `<p:timing>`：逐项浮入、淡出、调暗与点名（字体颜色）、
  相邻两片的 Morph 平滑切换（靠 `!!` 对象名配对，旧版本回退成淡入淡出），时长沿用 HTML 模板的 320ms 与 480ms
- **XML 的写法是让 PowerPoint 16.112 自己加动画再存盘、照它写出来的抄的**，不是凭规范推的。
  实测它读回再存出来，17 张片里 16 张一字不差；导出视频逐帧确认了换色能盖住写死的字色、
  Morph 过渡中只有配对对象留在屏上移动
- 提问片因此不再拆两张，在原地揭晓；误解片的划线改成把误解调暗；回顾逐条揭晓；新增 `derive` 推演片型
- 新增三条自检（被截掉的项、放不下的行、折行后的孤行）与调暗色／重点色的 WCAG 3:1 核对；`--static` 保留旧行为
- 更正两处旧说法：python-pptx 只是没有动画接口，XML 可以直接写；Keynote 的 AppleScript 能新建片也能存 .key，
  但字典里没有出场顺序相关的类，所以动画建不出来。**Keynote 导入 pptx 后动画剩多少，本轮未验证**
- 顺带修掉 0.22.2 留下的不一致：`SKILL_INDEX.md` 里的 Library Version 当时没跟着升

## 0.22.2 — 2026-09-17

合并 Downloads 副本中滞留的未提交更改。这些改动写于 0.22.0 前后（9/10–9/15），各 skill 的 PATCH 版本与变更记录当时已写好，只是一直没有入库；Library 层按规则补记 PATCH：

- `modeling-problem-reading-coach` 0.1.1：接入 `_shared/` 工作契约与验证手册（审计项 A2 修复）
- `activity-list-optimizer` 0.2.1：Common App 易变限额补核对日期、官方来源与每申请季复核要求（审计项 A1 修复）
- `application-timeline-builder` 0.2.1：倒推提前量标明为经验默认值，补核对日期与流程来源（审计项 A1 修复）
- `model-selection-tutor` 0.1.1：明确与 `modeling-assumption-builder` 的分流
- `modeling-code-builder` 0.1.1：补充矛盾输入与受评任务边界违规评估用例，新增 `references/evaluation-cases.md`
- AUDIT-AND-IDEAS.md：A1、A2 两项标记为已修复

## 0.22.1 — 2026-09-17

`keynote-deck-builder` 升到 0.6.0：从发布会扩到课堂、讲座与学术报告。Library 层只动了索引与 README 的描述，按规则记 PATCH；
skill 本身的改动细节记在它自己的变更记录里。要点：

- 新增「场合」一节。四种场合共用视觉，分开拍点；课堂与讲堂**换掉三条文字规则**，都是学习研究与发布会做法直接冲突的地方：
  证据片标题改主张句、允许真要作答且一定揭晓的提问片、回顾改成先提示再揭晓
- 新增十二类片型、「文字的位置」「图片」「出场顺序与动效」三节、课堂事实校验五条、讲义产出
- 模板加逐步出现（`data-build` / `data-dim` / `data-mark`）、相邻两片的连续过渡（`data-morph`，View Transitions）、
  讲者视图、黑屏、全屏、地址定位；公式改用原生 MathML，不引任何公式库
- 新脚本 `inline_images.py`：图片内联，查分辨率与来源行，清掉照片里的 GPS；pptx 导出加讲者备注与九种新片型
- 新示例：一堂讲单摆周期的课（大纲、17 张片、片单、讲义）

在浏览器里实测时修掉的问题：

- 窗口尺寸一变（进出全屏），当前片会被滚动吸附带到别的片
- 页面在后台或隐藏窗口里载入时每片高度为 0，滚动同步把所有片同时报成可见，当前片被带到最后一张
- 无头打印时逐步出现的内容整片空白
- **图表里未强调的柱子用的是 5% 白，投出来几乎看不见**，不满足 WCAG 1.4.11 的非文字 3:1；这条影响所有已有的发布会片子，改用已量过的 `--faint`
- 调暗若用透明度叠乘，次要字会掉到 1.7:1，改成统一换色
- 负号紧跟等号时被排成减号，两侧留空

另外更正了一处旧说法：「30pt = 40px」用的是 CSS 的 96dpi 换算，而 Keynote 画布本身以 pt 为单位，1920×1080 画布上 30pt 就是 30px。
40px 下限不受影响，它靠视角几何成立。

仓库层面：README 徽章行里 commit activity 指向的是另一个仓库（MaestrWave），已改回本仓库；skills 数从 31 更新为实际数量；按全局约定补上 stars 徽章。

## 0.22.0 — 2026-09-09

新开 `photography` 分类，落地审计文档组四的五项摄影技能（均 0.1.0 draft），共同分工：
**脚本兜底一切事实，模型只做判断与排版决策。**

- `photo-caption-writer`：基于拍摄者确认的事实与可选 EXIF 写短图注/长作品阐述；
  证据分 confirmed / attributed / unknown 三清单，拒绝从画面推断情绪、身份与意图。
- `photo-exif-frame`：照片下方加可配置信息带（光圈/快门/曝光补偿/ISO/时间/设备）；
  缺字段留空不编造，永不覆盖源文件，版式默认值写入 references。
- `photo-poster-stylist`：把拍摄者自己的描述转译为极简几何 SVG 海报；
  脚本校验调色板与元素数量上限，强制极简，不假装会画画。
- `photo-series-layout`：3–9 张照片排成一页成套作品；顺序默认由人定，
  与 `photo-exif-frame` 可组合且不加第二层框。
- `shoot-outing-review-card`：一场拍摄生成回顾卡（封面 + 参数习惯分布 + 时间线）；
  只呈现习惯不评价好坏，GPS/序列号等隐私字段永不展示。

另修复 A3：`writing-rules`（0.2.0→0.2.1）补上与 `zlc` 的双向互斥声明，原来互斥只写了 `zlc` 一边。

## 0.21.0 — 2026-09-05

新开 `community-programs` 分类，首个 skill `program-maturity-navigator`（0.1.0 draft）：
把「这个活动下一步该干什么」变成一个有证据门槛的判断。

按讨论时定下的五处设计，与最初那份提案有实质出入：

**一、双轴，不是线性链。** 提案把两条链（读书会→…→城市读书会；学长课堂→…→Workshop）
合成一条五级梯子。但提案自己已经写出症结——城市读书会是**扩大范围**，Workshop 是**加深参与**。
这是两个轴，不是一条梯子。合并会造出三个假问题：两者谁更高？八个人的深度 Workshop 算不算卡住？
两百人却什么也不留的公共讲座算第几级？现在主干只有三段（种子／孵化／系列），之后分叉成
深度与广度两个 0–2 的独立轴，位置判定输出一个坐标而不是级别。提案里的原则
「上升不等于参与者更优秀」「允许停在当前阶段」因此变成结构自带，不再靠嘴上强调。

**两个轴的门槛有意不对称**：深度进入要 1（动手过一次就证明形式跑得起来），
广度进入要 2（来过一个陌生人证明不了什么，再来一次才是信号）。

**二、闸门是证据清单，不是判断题。** 表单模型都会填，这个 skill 的价值全在会不会拦住人。
五道闸（G1–G5）逐条列出「拿什么证明」。其中 G2 的第二条是最硬的一条：
**试办必须产生至少一条出乎意料的观察**——完全符合预期说明没有在观察，
那次试办没有产生新信息，不构成放行证据。

**三、位置由痕迹决定，不由名字决定。** 第一个问题不是「你觉得自己在哪个阶段」，
而是「上一次是哪天、来了几个人、留下了什么」。办过三次「系列读书会」却拿不出记录的，
证据只支持孵化。这是唯一的防名词通胀机制。

**四、系列的顺序做成机器可判的。** 提案的原则「不能只把相近题目放在一起」原本只是一句话。
现在每一场声明 `consumes` / `produces`，脚本查连通性：除第一场外必须至少消费一件前面某场的产物。
消费不到的就是孤立节点——把它拿掉系列不会有任何损失，那它就不该在系列里。

**五、补了两份提案里没有的产物。** `孵化复盘`（G2 的证据来源，提案只有 Incubation Plan 没有复盘）
和 `停办记录`。后者尤其要紧：大多数种子会死，只有成功形状的表格会逼人给已经黄了的活动
写成功形状的文档。停办原因必须归到没人要／没人带／时间不对三类之一，三者处理完全不同，
不许合并成「效果不佳」。

架构按提案作者本人的倾向，先做单个总控 skill。**但拆分预判改了**：
`activity-format-router` 不拆——它就是一张二十行的决策表，独立成 skill 撑不起一份 SKILL.md，
且脱离活动背景判不准，放进 `references/format-selection.md`；
`workshop-designer` 保留为 planned，它的输入（材料、场地、时长切分、安全与无障碍）
与前面几阶段几乎不共享字段，真跑几轮后值得拆。

`Catena`、`Incubator`、`学长课堂`、`Leminar` 归入 `references/local-vocabulary.md` 由使用者填写，
机制部分保持通用。`Leminar` 无定义即留空槽，不按字面猜——
「Lecture 加 Seminar」是猜测不是定义。

`scripts/check_program.py` 纯标准库，两个子命令 `stage` 与 `catena`，带 `--selftest`（七个用例）。
实跑验证：四本书各读各的被判出三个孤立节点；改成前后传递产物之后通过。
九份测试用例覆盖提案点名的四种情形，外加混淆两轴、Leminar 缺定义、粉饰停办、
跳过闸门与无执行能力。

## 0.20.0 — 2026-09-05

**修复十一个未接入的 skill。** `physics` 组二、三、四共十个，加 `ai-usage/ai-generated-test-auditor`，
此前已写好正文与脚本但 frontmatter 不合规、测试用例放在各自目录里、索引与 README 未登记，
`validate.sh` 报 64 个错误。与 0.19.0 修的那批是同一种失败方式：写完了但没装上。

`physics` 至此覆盖 `AUDIT-AND-IDEAS.md` 规划的完整五组流水线：

- 组二（动手纪律）：`concept-to-formula-deriver`、`symbolic-first-discipline-coach`、`fermi-estimation-coach`
- 组三（检错）：`limiting-case-validator`、`answer-plausibility-checker`、`derivation-step-checker`
  （`dimensional-analysis-checker` 已于 0.19.0 归位）
- 组四（数据与模拟）：`uncertainty-propagator`、`model-fit-auditor`、
  `dataset-systematic-error-hunter`、`numerical-stability-auditor`

做的事：

- frontmatter 全部按 `CONTRIBUTING.md` 归一。原状况五花八门：多数只有 `name` / `description` / `version`；
  `fermi-estimation-coach` 与 `uncertainty-propagator` 把 `version` / `status` 塞进嵌套的 `metadata:`
  块里（扁平解析器读出来带引号，过不了 semver 校验）；`ai-generated-test-auditor` 用了非约定的 `tags`；
  `symbolic-first-discipline-coach` 与 `answer-plausibility-checker` 带 `license` 键。
  description 一律改写成中文触发式，与既有 skill 一致
- 七份写在 skill 目录内的用例（`TEST-CASES.md`、`tests/cases.md`、`tests/test_cases.md`）
  移到 `tests/cases/<name>.md`，内容保留；另补写四份缺失的
  （`concept-to-formula-deriver`、`symbolic-first-discipline-coach`、
  `answer-plausibility-checker`、`derivation-step-checker`）
- 十一个 skill 在 `SKILL_INDEX.md` 从 `planned` 改为 `draft`，并在 `README.md` 登记

**八个新脚本逐个实跑验证过**，正例与反例都跑，退出状态确认能区分通过与失败：
`check_derivation.py`、`check_limit_manifest.py`、`check_plausibility.py`、`check_estimate.py`、
`compare_formula.py`、`audit_fit.py`、`audit_stability.py`、`hunt_systematics.py`、
`propagate_uncertainty.py`、`check_test_audit_manifest.py`。

其中修掉一个真 bug：`check_derivation.py` 在 `=` 两侧切分后没有 strip，
`"F = m*a"` 里的 `" m*a"` 被 `ast.parse` 当成缩进而报 `unexpected indent`——
**它自己 `references/input-schema.md` 里的示例都跑不通**。改为解析前 strip。

抽查过的数值都对：`audit_stability convergence` 对 `error ∝ step²` 的数据给出斜率 2.0；
`propagate_uncertainty` 对单摆 `g = 4π²L/T²` 在 `L = 0.994`、`T = 2.006` 下给出 9.7518 m·s⁻²。

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
