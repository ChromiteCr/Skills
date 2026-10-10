# 审计与新 skill 提案 · 第二轮

生成日期 2026-09-24 · 库版本 0.22.3 · 已建成 61 个 skill

> **2026-10-07 补充：新增第四部分「发布会 bento 信息图」方案**（你点名要做，取代 `launch-summary-panel`；4.13 的五个问题已定；4.12 已细化成 11 轮的逐轮执行计划）；第二部分的开头和 C、E、F 节各补了一处。

第一轮（2026-08-21，库版本 0.16.0）提案的 skill 已全部建成。第一轮原文用 `git show 40e9001:AUDIT-AND-IDEAS.md` 查看；它没勾掉的遗留项在本轮第一部分 H 节逐条核对过。

**本轮怎么做的。** 12 路只读审计：基础设施 1 路，脚本实跑 2 路，按分类的内容审计 8 路，跨分类 1 路。每路配一个独立核查者，逐条重新打开文件、重跑命令，复现不了就判否决。审计报了 176 条，核查者另补 20 条；否决 3 条，56 条"部分成立"，按核查者更正后的说法写进本文。影响最大的 A1 由我在仓库副本上另外实测，并对照了官方文档。初稿写完后，又由一个核查者把全文和原始审计数据逐条对照，改正了十几处说法，补回 7 条漏项。

| 档 | 含义 |
|---|---|
| 无标注 | 审计报出、核查者独立复现，行号和事实可信 |
| **【实测】** | 在仓库副本上真实运行过，看到了结果 |
| **已否决 / 改判** | 见 I 节。否决的不要照着做；改判的是问题成立、但结论或修法换了 |

> 行号以 commit `40e9001` 为准。同一个问题被多路审计各报一次的，这里合并成一条。

---

## 第一部分：现有 skill 的问题

> **2026-09-26 更新：本部分各项已修完，随库版本 0.22.4 发布**（细节见 `CHANGELOG.md` 与各 skill 的变更记录）。I 节否决的各项没有照做；改判的按改判后的修法做。

严重度：**高** = 装不上、给错结论、脚本坏了、误导使用者；**中** = 会咬人的不一致；**低** = 顺手清理。

### A. 先修这几条（高）

#### A1. [x] 按 README 装上插件，一个 skill 都加载不到 — **【实测】**

`skills/` 下只有分类目录，技能在 `skills/<分类>/<技能>/SKILL.md` 这一层。Claude Code 扫 `skills/` 时只看它的直接子目录，不往下递归（本机 2.1.177 的加载器如此，官方 plugins-reference 给的目录结构也只有一层）。`scripts/sync-skill-links.sh` 本来要在顶层建 61 个符号链接补这一层，但它从没运行过：仓库里没有一个链接，脚本也没有可执行位；脚本头说"校验脚本用 --check"，`validate.sh` 其实没调用它。本机 `installed_plugins.json` 里也没有 skills-library，所以一直没人从安装路径发现这件事。

我在两份仓库副本上用无头模式各启动一次，读启动事件里的技能列表：

| 副本 | `skills-library` 加载到的 skill |
|---|---|
| 现状 | **0** |
| `plugin.json` 加上 `"skills": ["./skills/ai-usage", …十个分类目录]` | **61** |

`plugin.json` 的 `skills` 字段是在默认 `skills/` 之外**追加**扫描的目录，每一项必须以 `./` 开头，可以指向 skill 目录本身，也可以指向装着若干 skill 目录的上级目录。所以列出十个分类目录就能全部加载。写成 `"./skills"` 不起作用：它等于默认目录，会被过滤掉。

- 修法：`plugin.json` 列出十个分类目录；`validate.sh` 加一条"每个含 `*/SKILL.md` 的分类目录都必须在列表里"，否则将来新开的分类会静默不加载；删掉 `sync-skill-links.sh`，或者把它改写成这条检查。提交 61 个符号链接也能用（核查者在副本上试过，`validate.sh` 不受影响），但 Windows 的 `core.symlinks=false` 和 zip 打包都会碰到链接问题，清单方案更稳。
- 版本：Library PATCH。

#### A2. [x] 物理入口把已建成的下游标成"计划中"，还叮嘱 Agent 别调用

`physics-problem-router/SKILL.md:96–101` 的分流表里，按名字标"计划中"的有 5 个（concept-to-formula-deriver、fermi-estimation-coach、dimensional-analysis-checker、limiting-case-validator、derivation-step-checker），:101 还有一行"组四各 skill｜计划中"笼统盖住另外 4 个，合计 9 个已建成的 skill 被标成计划中，并给出"暂时手工做"的替代路径。`symbolic-first-discipline-coach`、`answer-plausibility-checker` 两个完全没有行。同样过时的说法还在 `physics-mechanism-decomposer:41/42/204`、`dimensional-analysis-checker:199–202`。

两份用例会反过来惩罚正确分流：`tests/cases/physics-problem-router.md:21`"不得调用尚未建成的 `fermi-estimation-coach`"，`tests/cases/problem-representation-scout.md:88` 把 `limiting-case-validator` 标为计划中。**skill 和用例必须在同一次提交里改。** 组四拆成四行写出实名，补上缺的两行。router 的 :161、:174 是通用规则，保留。

版本：router、decomposer、dimensional 各 skill PATCH。

#### A3. [x] 确定性脚本静默给出错误结论

这个库的承诺是"脚本兜底事实"。下面这些脚本在常见输入上给出**错的**结论而不报错，比不做检查更糟。

| 脚本 | 问题 | 严重度 |
|---|---|---|
| `physics/_shared/scripts/dimcheck.py`（五个物理 skill 共用） | `[check]` 里写成方程 `a = b` 时被当成"名字 = 表达式"，两边量纲不一致也报"全部通过"；`^1/2` 被解析成"一次方再除以 2"；`µ` 这类兼容字符被 NFKC 改写后，已声明的符号报"未声明"；语法错误算进"不一致"，退出码是 1 而不是文档说的 2。`problem-formalization-coach:152` 还在教人把方程写进 `[check]` | 高 |
| `concept-to-formula-deriver/scripts/compare_formula.py` | 自己 docstring 里的示例跑出"不等价"；`I`、`E` 被静默当成虚数单位和自然常数；`N/Q/S/gamma/beta/lambda` 直接崩溃；解析失败和"不等价"共用退出码 1 | 高 |
| `derivation-step-checker/scripts/check_derivation.py` | `… = 0` 形式被判量纲不一致；`10**m` 这类非 exp 形式的指数不查量纲 | 高 |
| `dataset-systematic-error-hunter/scripts/hunt_systematics.py` | 用原始幂次的正规方程拟二次式：自变量是 Unix 时间戳时算出负的 SSE 降幅，是 SI 小量时静默返回 null；时间列是 ISO 字符串时丢掉全部数据，n=0 还 exit 0 | 高 |
| `lyric-doctor/scripts/lyric_check.py` | 歌词段名与模板段名写法不同时（歌词"主歌 1"对模板"主"，而本库 craft-reference 的模板写"主"、adversarial 与 mapper 的输出写"主歌 1"），重复段被静默跳过，超字仍报"机械问题 0 处"；按序号兜底还会把段落配错类型、报出假的超字；不认 `【主歌】`、`主歌：` 这类段名；模板里有全角空格整份失效；`--extra` 不认全角逗号。修法：精确段名 → 去掉尾部数字后的归一名 → 找不到就报；不要一律去掉 A/B 后缀，AABA 里 A、B 本身就是段名 | 高 |
| `model-fit-auditor/scripts/audit_fit.py` | 求逆用绝对阈值：自变量是 SI 小量时误报 rank-deficient 并以 exit 2 退出，残差、拟合优度等诊断全部丢失；自变量偏移大、数据量小时反而不报错，静默给出错误的杠杆值和 Cook 距离（核查者复现：n=8 时杠杆值之和 0.785，理论上应等于参数个数 2） | 中 |
| `latex-paper-formatter/scripts/check_latex.py` | `\input`、`\bibliography` 按子文件目录解析（TeX 按主文件目录）；macOS 文件系统不分大小写，查不出图片路径的大小写错误，用例 Case 1 的期望在使用者自己的机器上不成立；中文"公式 (3)"、"式（5）"查不出；带点的文件名不补 `.tex`；从 skill 目录照 SKILL.md 的命令跑时一个文件都不读 | 中 |
| `prompt-brief-builder/scripts/check_brief.py` | SKILL.md 自带的空模板能通过校验；标题行末尾多一个空格就把整节判空 | 中 |
| `fermi-estimation-coach/scripts/check_estimate.py` | `product` 合成要求各机制单位与目标单位完全相同，只有谎标单位才能通过；三个字段类型错时抛 TypeError | 中 |
| `program-maturity-navigator/scripts/check_program.py` | stage 的 JSON 字段名只写在脚本里，拼错的可选键静默算成"没动手"；未来日期和 attendance=0 的场次也算"已发生"；人数字段填非整数时直接 traceback；提示使用者写 `external_inputs`，脚本却从不读 | 中 |
| `uncertainty-propagator/scripts/propagate_uncertainty.py` | 未声明的 `E` 静默按欧拉数算；`lambda` 过了变量名校验，解析时才报看不懂的错 | 低 |

两处看起来像静默出错、其实是规则本身的问题，单独列出：

- `check_derivation.py` 的非零检查逐个符号判断，声明 m1、m2 非零后除以 (m1−m2) 直接放行。这和 `references/input-schema.md:29` 的写法一致，是规则漏洞。改成允许在 `nonzero` 里写表达式，用 `factor_list` 拆出每个非常数因子逐个核对（中）。
- `check_brief.py` 把全中文标题的简报判成"缺全部标题"。脚本是按 SKILL.md 自己的英文模板校验的，缺口在本地化契约：首选在 SKILL.md 写明"标题保持英文"；要接受中文标题，得先把中文标题归一到规范键，:66 的标签正则也要同步改（低）。

另有四个脚本不认 `--help`，会把它当成文件名（`check_test_audit_manifest.py`、`check_brief.py`、`check_limit_manifest.py`、`audit_fit.py`）。`limiting-case-validator` 的正文从没交代 manifest 的格式和调用命令，只能读源码猜，空 manifest 还会被判"结构完整"。

**修法的共同点**：每个脚本补一个 `--selftest`，把上面这些输入作为回归用例；遇到不认识的键或自由符号时报错，不要静默。

#### A4. [x] 摄影脚本：读不到参数、照片横躺、字小到看不清、会覆盖原片

| 脚本 | 问题 | 严重度 |
|---|---|---|
| `photo-caption-writer/scripts/extract_exif.py` | 只读 IFD0，真实相机 JPEG 的光圈、快门、ISO、焦距、镜头、拍摄时间、曝光补偿**全部返回 null** | 高 |
| `photo-spread-composer` 两个脚本 | 不处理 EXIF 方向：手机竖拍被量成横图，带高方程用错长宽比，内联后照片横躺；`EXTS` 列了 `.heic` 但读不了，直接抛 traceback；模板头部注释里有字面量 `<!--BANDS-->`，**整版照片被注入两次，成品体积翻倍** | 高 |
| `photo-exif-frame/scripts/render_exif_frame.py` | 不给 `--font` 时回退到 10px 默认字体，真实分辨率下信息带读不清；而换成按尺寸渲染的字体后，默认 6 个字段**放不下**，SKILL 教的补救"加大 `--band-ratio`"方向正好相反。两件事必须一起修：字号按格宽倒推，缩到放得下为止，低于下限才报错 | 高 |
| `shoot-outing-review-card/scripts/make_review_card.py` | 标题字体只认 Arial / DejaVu，**中文全部渲染成方块**；`--output` 可以指向输入照片，会把原 JPEG 静默覆盖成 PNG；自动选封面用未转正的尺寸，竖拍被当成横图 | 高 |
| 三个出图脚本 | 丢掉 ICC 配置：iPhone 的 Display P3 照片输出后被当成 sRGB，颜色发灰；`photo-series-layout/SKILL.md:75` 却说转到了共同 RGB 空间 | 中 |
| `photo-exif-frame`、`shoot-outing-review-card` | 把 IFD0 的 `DateTime`（文件修改或导出时间）当拍摄时间印出来，违反它们自己"不编造事实"的边界 | 中 |
| `photo-poster-stylist/scripts/poster_tool.py` | validate 不看 viewBox 偏移：有出血时，正确的出血形状报越界，完全画外的形状反而 PASS；path 和文字完全不查边界 | 中 |
| `photo-series-layout` | references 描述的 auto 排布算法并不存在，脚本是写死的表，8 张出 3×3 空一格；SKILL.md:135 写"重复路径经确认后可用"，脚本 :99 却无条件拒绝，也没有放行开关；references 用"列×行"记号，脚本打印"行×列" | 中 |
| 零碎 | 透明 PNG 的透明区压成黑色；-2/3 EV 印成 `-0.666667 EV`；回顾卡机身名重复厂商；`measure_photos.py` 静默忽略 `--dpi=150` 这种等号写法，`build_spread.py` 找不到源文件时直接抛 traceback，SKILL.md 没写 Pillow 依赖 | 低 |

字体路径注意：本机（macOS 26）没有 `/System/Library/Fonts/PingFang.ttc`，核查者实测能加载且有汉字字形的是 `Hiragino Sans GB.ttc`、`STHeiti Medium.ttc`、`Supplemental/Arial Unicode.ttf`。`ImageFont.load_default(size=)` 需要 Pillow ≥ 10.1，旧版会抛 TypeError，要一并兜住。

HEIC：四个读图脚本都读不了，SKILL 里一句没提。至少写明"先 `sips -s format jpeg`（macOS，保留 EXIF）"。

#### A5. [x] ai-usage：description 承诺的东西没交付

- **`ai-code-onboarding-checklist`**（高）：description 承诺查"危险调用"，正文和输出表里都没有这一项。补一节（eval/exec、`shell=True`、递归删除、反序列化、提权、外发网络），或者从 description 删掉。
- **`ai-diff-review-protocol`**（中）：description 和用例说 diff 统计"由脚本出"、"超阈值强制人工逐段过"，目录里没有脚本，正文 :176 还写阈值不是铁律。第一轮规划过这个脚本，也勾了完成。补 `scripts/diff_risk.py`（纯标准库，能直接解析粘贴进来的 diff 文本，因为 :264 写了不假定有 Git），并在输出契约里加"Diff stats"一段。另外，只有口头描述、没有 diff 时，正文让照常出结论，用例禁止出结论：应分两种情况，有前后片段就照常走并降置信度，只有口头描述就不给 verdict，只列补材料清单。
- **`ai-generated-test-auditor`**（中）：description、`suggest_hint`、索引、README 都说它"验证改坏后测试会不会变红"，正文和脚本其实只做突变**计划**。统一改成"规划 2–5 个突变抽样，能执行时再实跑"。
- **索引说"脚本能兜底的绝不靠模型自觉"**（中）：7 个 ai-usage skill 里只有 2 个有脚本。第一轮为 `ai-output-fact-checker`、`ai-code-onboarding-checklist`、`ai-session-handoff-writer` 规划的确定性部分没做。落差在规划表和索引这一层：这三个 skill 自己的 SKILL.md 并没有声称自带脚本。要么补（第二部分 C 节），要么如实改描述。

### B. 正文与脚本互相矛盾（中）

#### B1. [x] keynote-deck-builder 的残留

多数条目早于 0.7.0：:163、:326 来自 08-16，:894 来自 08-17，`read_pptx.py` 自 08-17 起没改过；Case 13、:556 等少数几条是 0.6.0 与 0.7.0 引入的。

- **体量**：SKILL.md 73.6KB、984 行，触发一次约 2.4 万 token；其余 60 份都在 14KB 以下。变更记录一节就占 10.5KB。:952 写着"发布会与答辩不读……课堂与讲堂才读"，可 SKILL.md 是整份载入的，这句门控挡不住任何东西。把变更记录挪进 skill 目录的 `CHANGELOG.md`，把"当这不是发布会"和"片上文字的句式"两节挪进 `references/` 并写明读取条件，按字节算正文能减 25%–36%。
- 用例 Case 13（`tests/cases/keynote-deck-builder.md:300–309`）还按 0.6.0 的说法验收（"动画带不进 pptx"），与 0.7.0 正文和同文件 Case 23 直接冲突。
- 正文 :556 与脚本 docstring 说"规格密排逐个出"，脚本默认 `specs` 不分步。
- HTML→pptx 降级表漏了五类片型（时刻、信号汇入、取舍、one more thing、环保），导出时被跳过。映射时注意：`phrase` 只渲染 value 不读 caption，"时刻"应映射到 `feature`。
- 发布会示例第 9 张用了问句标题，违反自家"不用问句"；`example-deck.json` 与大纲、HTML 对不上。
- `read_pptx.py` 不递归组合形状，组里的文字被静默丢掉；`inline_images.py` 拒收被 Pillow 识别成 MPO 的 JPEG，报错却让用户"先转成 JPEG"。
- `outline_to_pptx.py` 的"放不下、孤行"自检只在 derive 片型上跑，长 phrase 超出画布不报（变更记录却说是全局的）。
- 正文残留旧数字和旧指代：:163"从下面十四类里选"应为三十三类；:173"最后三类"应写明是通用里的最后三类（时刻、信号汇入、取舍）；:326 应为 15 字；:894"至今十三年"会过期；`read_pptx.py` docstring 阈值过时；SKILL.md 没写 python-pptx、Pillow 依赖。

#### B2. [x] 其他 coding-helper

- `radio-quote-card`（中）：字号按字符数定档，中文语录实测溢出 800×1000 卡片并被裁掉。中文另立档位（按实渲染，约 66px/40 字、56px/55 字、46px/85 字封顶），加一个中文用例。
- `maestrwave-ui-system`（中）：规定"字号只用五档"，自带的 CSS 用了 7 处档外字号；:61 的"五个"应为"六个"。另外 `.field-label`（11px，ink 48%）在 `--bg`、`--surface`、`--surface-2` 上的对比度是 4.43、4.33、4.13，都低于 AA 的 4.5（点子轮的提出者与评审各自算过一遍）。
- `launch-summary-panel`（低）：正文要求圆角 16–24px，模板小卡用 14px；与 keynote 的分流只写了一边。

#### B3. [x] 其他 skill 的正文与用例冲突

- `lyric-doctor`（中）：SKILL.md:70 和用例 :25 拿来示范"脚本查不出"的空话，实际都会被脚本命中，用例的 :23 与 :25 还互相矛盾；`CLICHE_PHRASE` 漏了 craft-reference:53 的"这就是最好的"。三位点子评审都要求这一条立刻单独发 PATCH。
- `ai-output-fact-checker`（中）：状态规定只能用五个固定值，自己的示例和用例各用了一个不在集合里的词。
- `prompt-brief-builder`（中）：用例 Case 4 与正文 :54 相反（使用者坚持要成品时，正文说退出，用例说继续）；没有矛盾输入用例，与 CHANGELOG 0.19.0 的说法不符。
- `adversarial-lyric-writer`（中）：字数收敛靠模型自报、模型复核，全流程没有一步跑脚本数字数（要等 A3 的 lyric_check 修好才能接上）；前面说"主 Agent 全程不写句子"，第 3、4 轮又让主 Agent 重写行（低）。
- `ai-session-handoff-writer`（低）：用例要求九节齐全，正文只要求八节；正文允许"明确授权后"写入密钥，用例和 README 一律禁止。
- `ai-answer-triage`（低）：对可执行类（D 类）的处置，description:3、正文 :158、README:129 三处说法不一致（Step 4 的排序在 :217–219）。
- `ai-generated-test-auditor`（低）：脚本的枚举值与正文术语对不上，照正文写"mirrored logic"会被判 invalid；用例从没跑过这个脚本；参数传入目录时抛 IsADirectoryError。
- `answer-plausibility-checker`（低）：用例把 check 级的 fail 当结论，还要求一项 SKILL 里没有的有效数字检查；脚本支持的 `expected_range`、`max_order_gap` 没写进输入格式；`check_plausibility.py:83` 用 ±u 区间是否重叠判相容，1.56σ 的差异也判 FAIL，uncertainty 也没说明覆盖因子。输入样例写明是标准不确定度（k=1），脚本另外输出 z 值。
- `uncertainty-propagator`（低）：弹性系数取不取绝对值，SKILL.md:101 与 `references/method.md:41` 不一致。
- `project-brainstorm`（低）：用例要求转述 `mergedGroups`、`distinct`，正文只介绍了 `kept` 和 `similar`。
- `skill-creator`（低）：用例 Case 4 期望改技能时递增 version，正文没教这一步。
- `writing-rules`（低）：用例还写着"十条规则"，现在是十五条；与 zlc 的互斥、"不代写"两条边界在两边用例里都没覆盖。
- `program-maturity-navigator`（低）：标题写"四道闸"，实际有 G1–G5；边界说不做单场流程，模板却要求填时间流程。
- `modeling-problem-reading-coach`（低）：第 6 步标题要求"至少两个拆法"，正文说只在有歧义时才给多个；中文证据标签里【待确认】没有对应的共享 `evidence_status`（映射到 `unverified` 加歧义 ID 即可，不要新增状态）。
- `modeling-code-builder`（低）：Run Manifest 有三套字段定义，输出模板缺 `status` 和 `tests`。以 `code-reproducibility-checklist.md` §7 为唯一 schema。
- `numerical-stability-auditor`（低）：自收敛模式下，SKILL 要求至少 3 个分辨率，只能得到 2 个差值，脚本拒收；均匀采样容差 1e-6 太严，时间列四舍五入到 4 位小数就跳过鬼频检查（容差应按打印精度算）。

### C. 内容错误（物理、写作、核验规则）

- [x] `problem-representation-scout/SKILL.md:60`（中）：把"滑动→纯滚动"的阶段边界判据写成"|f| 达到 μ_s N"，错了。应拆成两行：静→滑是维持无滑所需的静摩擦达到 μ_s N；滑→滚是接触点相对滑动速度趋于 0，之后再验 |f_req| ≤ μ_s N。
- [x] `physics/_shared/law-applicability-table.md:56`（中）：把积分形式的法拉第通量法则 ε = −dΦ/dt 标为"恒成立"。法拉第圆盘（单极发电机）正是已知例外；微分形式恒成立，积分形式要求回路随导体一起运动。
- [x] `physics/_shared/dimensionless-groups.md:15`（中）：π 定理的"秩"示例错了。某个量纲只出现在一个量里并不降秩；几个基本量纲只以固定组合出现时才降秩。`dimensional-analysis-checker:208` 说这里列了"两种数错方式"，文档里只有一种。
- [x] 准静态与绝热（低 + 中）：两份共享参考把两者说成"矛盾"，实际靠时间尺度窗口 τ_mech ≪ τ_process ≪ τ_heat 可以同时成立（例子用活塞压缩，别用声波）。`tests/cases/derivation-step-checker.md` Case 1 据此把两者判成冲突，是错误物理（中）。
- [x] `physics-mechanism-decomposer:157`（低）：给出不带温度和来源的物性数值，违反它自己的边界条款。
- [x] `songwriting/_shared/craft-reference.md`（中）：开口辙的范围 :35 与 :70 不一致，:75 的长音规则又和表格矛盾，副歌开口辙这道关的结论随引用哪一行而翻转。
- [x] `lyric-structure-mapper:127`（中）："每分钟 180 到 240 字"与自己的模板、自己举的例子对不上，时长估算约偏短一半。改成按 BPM 推算。
- [x] `ai-output-fact-checker:180`（中）：DOI 规则只要求作者、年份、标题三项对上两项，DOI 指向同一作者同年的另一篇也能过。标题必须一致，再加作者或年份一项。
- [x] `ai-output-fact-checker:172`（中）："包名存在"就算核实通过，没提 AI 幻觉出的包名可能已被人抢注。补"存在不等于可信"：看首发时间、源码仓库、维护者、下载量；加一个抢注反例用例。
- [x] `model-fit-auditor` description（低）："残差有结构＝漏了物理"与正文（第 4 步已列出漂移、校准）不一致。改成"模型、测量过程或不确定度模型三者之一不完整"，并点名 `dataset-systematic-error-hunter`；`suggest_hint`（:19）和 `SKILL_INDEX.md:72` 同步改。

### D. 学术诚信边界

- [x] `modeling-code-builder`（中）：:185 在"无执行能力"时给完整实现候选，不看任务是否受评，与 :167–169（不能写文件时已区分受评与非受评）和边界 :201–202 冲突；共享契约 `modeling/_shared/modeling-work-contract.md:108` 在"不能写"时也无条件返回完整候选。两处都补上受评条件：受评任务只给实现合同、伪代码、测试与局部补丁。Case 6 输入写明"非考核的个人项目"，另加一条"只能聊天、规则未说明"的用例。
- [x] `symbolic-first-discipline-coach`（中）：闸门只在使用者"明确要求代写"时触发，输出契约默认交一份完整符号推导；作业进行中只说"我卡住了"的学生会拿到完整解。Inputs 加"场景"，会被评分的作业进行中只给结构性问题；示例里"only then substitute numbers"改成由使用者代入。
- [x] `project-brainstorm`（中）：把 EE/IA 选题列为适用场景，却没有受评选题的诚信边界。补一句：受评选题只给方向和可行性，研究问题由学生定并交导师确认。
- [x] `fermi-estimation-coach`（中）：教练型 skill，没有代做边界，也没有代做请求的用例。其余七个物理 skill 各自写了边界，只差一条指向 `_shared/physics-evidence-contract.md` §4 的引用（低）。
- [x] `admissions-reader:42`、`reflection-interviewer:124`（低）：把"帮忙写文书"转给一个不存在的"文书类 skill""另一个 skill"。改成"文书本库不代写，只帮学生改自己写的稿"。
- [x] `dimensional-analysis-checker`（低）：:182 的诚信条款带条件，References 也没引用证据契约 §4；用例没有覆盖 `dimcheck.py` 路径，也没覆盖无执行能力时的降级。

### E. 兼容声明与运行时能力不符（中）

- [x] study-planning 八个 skill 加 `skill-creator`：正文必经步骤依赖 nestudy 专有工具（`check_activity_limits`、`resolve_deadline`、`propose_*`、`ask_user`），却声明兼容 claude-code 和 generic-llm-agent，也没有降级路径。其中四处明令不许手算：`activity-list-optimizer:74`、`application-timeline-builder:136`、`project-brainstorm:126`、`deadline-to-study-plan:80`。在 Claude Code 里这些工具不存在，两条规定直接矛盾。
- [x] `adversarial-lyric-writer`、`lyric-concept-builder`：核心流程依赖 Claude Code 的子代理，却声明 generic-llm-agent 兼容。
- [x] `application-timeline-builder:96`（低）：引用了库里找不到的工具 `count_essay_words`、`check_activity_limits`。

**建议定一条仓库规则**写进 CONTRIBUTING §3.1：正文点名的工具只有某个运行时才有时，要么不声明其他运行时，要么写一段"没有该能力时"的降级（字符数用 `python3 -c` 按 UTF-16 计、时区用 `zoneinfo`、`propose_*` 改成输出 Markdown 卡片、子代理改成三次互不共享上下文的独立调用，并如实标注"降级"）。现在 CONTRIBUTING.md:41 说"同一份 SKILL.md 在两边都能用"，:46 又把 `capabilities` 定义为运行本 skill"必需"的能力，两句放在一起，没有说必需能力缺席时怎么办。规则补在 :46 附近。

### F. 分流与触发语

- [x] **`photo-spread-composer` ↔ `photo-series-layout`**（中）：抢同一句请求，互不点名；spread-composer:48 还把单张照片指给不收照片的 `radio-quote-card`。两边各补判别句：自己拍的 3–9 张、要一张长图或 PDF、保留顺序 → series；刊物或展板版面、分带定主次、每张带署名 → spread。单张照片改指 `photo-caption-writer` / `photo-exif-frame`。spread-composer 仍挂在 `coding-helper/ui-design`；挪到 photography 按 VERSIONING 属于目录结构变更（Library MAJOR，0.x 可在 MINOR 位做但要写明），不是修复必需。
- [x] **摄影五个 skill 的 description 全是英文**（中）：全库仅有的纯英文 description，与仓库惯例和它们自己的中文用例不符。每个前面加 2–4 条中文原话触发语（"给照片加参数边框""把这几张拼成一页""给这张照片写图注""做一张这次外拍的回顾卡""把照片做成极简海报"），英文可以保留。
- [x] **`ai-answer-triage` ↔ `ai-output-fact-checker` ↔ `ai-code-onboarding-checklist`**（中）：触发语几乎一样，互不点名。triage 只排序和处置，逐条核实走 fact-checker，整段代码走 onboarding；triage:49–51 的三条泛称改成实名。`ai-diff-review-protocol` ↔ `ai-generated-test-auditor` 同样互不点名（低）。
- [x] **modeling ↔ physics 零交叉引用**（中）：modeling 九个 skill 从不提 physics。reading-coach 加"物理题 / IYPT / 实验现象 → `physics-problem-router`"，description 的"竞赛题"改成"数学建模竞赛题"；problem-formalization-coach 加对称的一句；assumption-builder、critique-coach 加"只查单条方程的量纲或极限 → `dimensional-analysis-checker` / `limiting-case-validator`"，并在量纲段引用 `../../physics/_shared/scripts/dimcheck.py`（这也是第一轮 A4 唯一值得做的一步）；model-fit-auditor 与 model-critique-coach 互相写判别句。
- [x] **`project-brainstorm` ↔ `program-maturity-navigator`**（中）：navigator 建好后 brainstorm 没补回指句。按对象分流：已定了要办读书会、分享、讲座、社群活动（不论办没办过）→ navigator；个人项目、研究课题、还要在几个方向里挑 → brainstorm。
- [x] **`concept-to-formula-deriver`**（中）：description 把最常见的说法"帮我推导 X"排除在外，它自己的用例恰恰要求处理这类请求。
- [x] **`prompt-brief-builder`**（低）：保留"帮我写个东西"（改判理由见 I 节），只在"不适用于"补实名分流：写歌 → `lyric-concept-builder`，复习计划 → `deadline-to-study-plan`，建模题 → `modeling-problem-reading-coach`，物理题 → `physics-problem-router`。
- [x] 物理几处（低）：`concept-to-formula-deriver` 与 `symbolic-first-discipline-coach` 不引用任何 `_shared` 文件；`symbolic-first-discipline-coach:64–66` 有三处泛称路由；deriver 与 `derivation-step-checker` 功能相邻却互不点名；`problem-formalization-coach:43` 说"可以讲某条公式从哪条守恒律来"，却不点名 deriver。
- [x] 零碎（低）：`modeling-assumption-builder` 的触发语"怎么做假设检验"在中文里指统计检验；`adversarial-lyric-writer` 的"我们在写一首关于 X 的歌"和 `lyric-concept-builder` 几乎一字不差；`reflection-interviewer` ↔ `activity-profile-builder` 的"何时使用"两边几乎同句，未建档的分支没有用例；`limiting-case-validator` 不提两个检错兄弟；8 个 skill 另有 14 处泛称路由（"用别的 skill""走建模类"）换成实名。

### G. 记账与校验

- [x] **`SKILL_INDEX.md` 8 行漂移**（中）：6 个版本落后（三个 modeling 0.1.1、`activity-list-optimizer`、`application-timeline-builder`、`writing-rules` 0.2.1），2 个优先级不一致（`dataset-systematic-error-hunter`、`numerical-stability-auditor` 在 frontmatter 是 P1，索引是 P2）。`validate.sh` 已经解析索引行，顺手比对三列即可。
- [x] **授权矛盾**（中）：`photo-exif-frame`、`shoot-outing-review-card` 的 frontmatter 写 `license: MIT`，插件清单是 `UNLICENSED`，仓库根没有 LICENSE。0.20.0 清理过同样的问题。删掉这两行，或者库级统一定一个许可证。
- [x] **README**：10 个 physics skill 列在"Applications and growth records"标题下（:103–112，低）；:41 说 token 成本那一半"lives in coding-helper"，coding-helper 相关的 8 行全是 planned，也没列进"Not written yet"（中）。
- [x] **`SKILL_INDEX.md`**（低）：physics 的脚本说明段落错放在 study-planning 小节里（:95–98），"八个确定性脚本"应为九个；physics 小节的描述还停在组〇和组一。
- [x] **三个摄影 skill 在自己目录里另存了一份测试**（中）：`skills/photography/*/tests/cases.md` 与 `tests/cases/<name>.md` 内容不同，登记的那份只有 2 个用例。合并后删除副本；注意 `photo-exif-frame/SKILL.md:104` 引用了副本，要一起改。
- [x] **单技能 zip 缺共享文件**（中，【实测】）：20 份 SKILL.md 引用 `../_shared/…`：physics 的四份共享参考与 `dimcheck.py`，modeling 的五份共享文档（work-contract、validation-playbook、paper-argument-checklist、team-workflow、code-reproducibility-checklist），songwriting 的 craft-reference。`dist/` 里的单技能 zip 只打了 skill 自己的目录，例如 `dimensional-analysis-checker.zip` 里只有一份 SKILL.md。各 skill 自带的脚本还在（`lyric-doctor.zip` 里有 `lyric_check.py`），丢的只是 `_shared` 文件，但依赖它们的步骤都会断。`dist/keynote-deck-builder.zip` 还是 0.6.0（打包于 9/17，源码 9/18 升到 0.7.0）。仓库里没有打包脚本，zip 是手工做的。修法：补一个 `scripts/package.sh`，打包时把被引用的 `_shared` 文件一起放进 zip 并改写相对路径，文件名带上 frontmatter 里的版本。插件安装不受影响，因为插件根就是仓库根。新写的共享代码怎么放，见第二部分 F 节的约定。
- [x] **`validate.sh` 的盲区**（中）：真实出过、现在仍检不出的错误有：索引的版本、优先级列漂移；已建成的 skill 在索引里仍写 planned；`skills/` 以外出现 SKILL.md（0.19.0 那次七个 skill 放在仓库根）；frontmatter 的缩进键；skill 目录里的第二份测试；description 没有中文字符；徽章数与实际数；`plugin.json` 的 skills 路径（A1）。另外没有 hook 或 CI 强制运行它，0.22.2 那次 Library Version 漂移脚本能查出，只是没人跑。
- [x] **CHANGELOG**（低）：漏记 8 个 Library 版本（0.7.0、0.8.0、0.9.0、0.10.0、0.13.0、0.14.0、0.15.0、0.17.0）；0.20.0 写"八个新脚本"后面列了十个；0.14.1 日期错。历史条目不改，在下一版注明更正即可。
- [x] **模板与流程文档**（低）：`templates/skill-template.md` 的 `compatible_agents` 默认带 openclaw，不带 codex 和 nestudy，与 README 不一致；CONTRIBUTING 写"main 受保护、只走 PR、squash、打 tag"，实际是直推 main。二选一：按个人仓库的实际做法改写，但写明"提交前必须跑 validate.sh"。

### H. 第一轮遗留项核对

| 项 | 本轮结论 |
|---|---|
| A1 写死的易变事实 | 已修（0.22.2）：两处都补了核对日期和来源。本轮补一条：`activity-list-optimizer` 新加的"工具限额过期要报告"规则没有用例，2026-27 季的选填和改名变化没记 |
| A2 reading-coach 引用 `_shared` | 已修（0.22.2）。剩【待确认】标签没有映射（B3，低） |
| A3 writing-rules ↔ zlc 互斥 | 已修（0.2.1），两边都有 |
| A4 该用脚本的地方 | **没做**。它在第一轮是"待核实"的建议，从未承诺，不算缺陷。量纲那条并入 F 节 modeling ↔ physics；CSS 反默认与对比度校验进了第二部分（`css_token_lint`）；Run Manifest 字段校验暂不做，第二部分没有对应提案 |
| A5 三组边界 | 第一组（反思 ↔ 档案）两边早已互相指向，剩触发语同句和未建档分支（F，低）；第二组（选型 ↔ 假设）选型侧已修，假设侧 :29 的"已有候选"仍冲突（低）；第三组（结构 ↔ 增强）增强侧缺一句"有草稿但结构不稳 → structure"（低） |
| B1 radio-quote-card 的"XX" | **否决**，见 I 节 |
| B2 `skills/.DS_Store` | 已修，已进 `.gitignore` |
| B3 modeling 两类用例 | "边界违规"一半，九个 skill 本来就都有；"矛盾输入"一半只有 `modeling-code-builder` 补了一条，还放在 `references/evaluation-cases.md` 里（会被当运行时参考加载）。把 evaluation-cases 的两个 Case 都移进 `tests/cases/`（Case 2 还测"不要在报告里提到 AI"这类隐瞒请求，不能删），并给 reading-coach、assumption-builder 各补一条"题面与附件口径冲突" |
| `program-maturity-navigator` 的 Leminar 等空槽 | **不是问题**。`references/local-vocabulary.md:3` 写明这些空槽留给使用者填。只需在 :14 注明"skill 内部用 catena 作'系列'的代号，不代表本地定义" |

### I. 否决与改判

**否决：报了但不成立，不要照着做**

| 报的 | 为什么不成立 |
|---|---|
| `fermi-estimation-coach` 把"机制清单已排好"设成硬前提，普通估算请求会被拒 | 有文档、有测试的刻意设计。使用者说出一条机制链就能继续（:35、:63 已覆盖） |
| `skill-creator` 教的骨架落进本仓库会让 `validate.sh` 失败 | 它面向学生、产物走 `propose_skill` 存进运行时技能库，从没承诺落进本仓库。真正成立的只有兼容声明（E 节） |
| `radio-quote-card` 的"生成 XX RADIO 的图"是占位符，应删 | "XX"是中文里约定俗成的"某某"，恰好是使用者最字面的说法，删了反而漏触发。第一轮 B1 一并否决。想加就加"F1 team radio 那种卡"这类词，不要删 |
| 删掉 `physics-problem-router` 表里的 :161、:174 | 那两行是通用规则，不针对具体下游，保留 |
| 把 `program-maturity-navigator` 的 CLI 名 `catena` 改掉 | 属于改输入契约（skill MAJOR）。加一句注释就够 |
| 给 22 个英文正文 skill 各加"用使用者的语言输出" | 模型默认跟随使用者语言，属于措辞偏好 |

**改判：问题成立，但结论或修法换了**

| 报的 | 改判 |
|---|---|
| `prompt-brief-builder` 的"帮我写个东西"太宽，应删 | 两位核查者意见相反：一位认为触发语过宽是真实风险，另一位指出这是它的核心定位（:26、第一轮提案原文）。采纳后者：保留触发语，只加实名分流（F 节），并把 Case 4 改成与 :54 一致 |
| 21 个 skill 缺"变更记录"小节 | 缺失属实，模板本身也自带"0.1.0｜初始草稿"一行；两位物理核查者认为 0.1.0 初版可以暂不补。结论：不为此单独发一轮 PATCH，下次改到哪个 skill 就顺手补上初始行 |
| `numerical-stability-auditor` 新增完整的 self-convergence 模式 | 问题成立，修法太重（MINOR）。写明差值和步长怎么配对、允许两个差值并给警告（PATCH）就够 |

### J. 其实没问题，不用动

同样是为了防止过度施工。这里只列没有被本文其他小节点到的部分。

| skill / 部件 | 判断 |
|---|---|
| `reference-frame-choice-guide` | 物理内容逐条核对全部正确：惯性力、科里奥利力不做功、离心势、雅可比积分、ΔT 的伽利略不变性、相对论不变量 |
| `uncertainty-propagator` 的方法 | 样例实跑 u=0.038935，与手算解析值一致，蒙特卡罗对标 0.038967；相关项、分布换算都对。例外只有 A3 的 `E`、`lambda` 和 B3 的弹性系数符号 |
| `numerical-stability-auditor` 的精确解路径 | 收敛阶实跑 2.0，漂移与鬼频判据合理。例外见 B3 |
| `model-fit-auditor` 的统计公式 | AIC/BIC、Cook's D、χ²/ν 在写明的前提下都正确。问题在脚本的数值实现（A3） |
| `physics/_shared/physics-evidence-contract.md` | SI 定义常数、g_n、G 的不确定度量级、水的黏度都核对无误 |
| `competition-scenario-extractor` | 与 dimcheck 的 CLI 一致，自由度计数与定律适用条件核对正确，用例覆盖矛盾输入和代推越界 |
| `team-role-coach`；`model-critique-coach` 的正文 | 计数、Gate 与共享文档完全对齐，拒绝伪造的用例齐全。critique-coach 只需补 F 节的两句分流 |
| `weekly-study-review`、`deadline-to-study-plan`、`activity-profile-builder` 的正文与用例 | 维持第一轮判断。兼容声明的问题在 E 节，activity-profile-builder 另有 F 节的触发语同句 |
| `llm-midi-composition` | 审计者对照本机参考实现逐条核对了 token 上限、音符数、温度等说法 |
| `zlc`、`writing-rules` 正文 | 维持第一轮判断；互斥两边都写了 |
| `ui-design-system-builder` | token 示例与 maestrwave 资产逐项相同，与 maestrwave 双向互斥 |
| keynote 的 `pptx_motion.py`、`export_pdf.sh` | `pptx_motion --selftest` 10 项全过，读回结果与 README 一致；`export_pdf.sh` 出 1920×1080 的 17 页 PDF，错误退出码正确 |

### K. 建议的修复顺序

1. **A1**：一次提交，Library PATCH。不修的话其余一切都用不上。
2. **A2**：router 与两份用例同一次提交。
3. **B3 的 lyric-doctor 黑名单与例句**：改动最小，三位评审都要求立刻发。
4. **A3**：先修 `dimcheck.py`（五个物理 skill 共用），再修 `compare_formula.py`、`check_derivation.py`、`hunt_systematics.py`、`lyric_check.py`。每个脚本随修随补 `--selftest`。
5. **A4**：摄影脚本。建议和第二部分的电影感调色 skill 一起做：两边都要处理 ICC、EXIF 方向、HEIC 与字体。按第二部分 F 节的约定，每个渲染 skill 放一份相同的 `image_io.py`，`validate.sh` 查各副本 sha256 一致。
6. **G 节的 `validate.sh` 升级**（索引三列、planned 行、skills 路径、license、skill 目录里的测试副本）再加一个 pre-commit hook，防止同类问题回来。
7. 其余按严重度逐个 PATCH。

---

## 第二部分：新 skill 提案

**怎么来的。** 六路按领域出点子（摄影；物理、建模与研究；编程与 AI；申请与社群；作词、写作与元技能；跨领域），共 46 条。三位评审各拿一个角度给每一条打 1–5 分并给判定（先做 / 以后做 / 合并 / 否决）：对你有没有用；脚本部分是不是真能算、能测；和已有 skill 或彼此之间重不重复。下面的"分"是三位评审的平均分，"先做票"是给"先做"的评审人数。重复的点子按评审意见合并，被合并掉的列在 E 节。电影感调色是你点名必须做的，不参与打分，完整方案见第三部分。bento 信息图也是你点名要做的（2026-10-07 加），同样不参与打分，方案见第四部分。

**分批规则**，直接按评审判定，不掺我的偏好：

| 批次 | 条件 |
|---|---|
| 第一批 | 至少两位评审给"先做"（11 条） |
| 第二批 | 一位评审给"先做"且没有否决票，或三位都给"以后做"且均分 ≥ 3.67 |
| 备选 | 其余（包括有否决票的） |

**这一轮的共同标准**，比第一轮收紧了两条：
1. 每条必须说清它关掉的是哪个具体默认，也就是现在 Agent 或使用者实际会犯的、看得见的错误；
2. "脚本只检查字段填没填"不算确定性部分。只有这一层的点子，要么找到真能算的东西，要么降为纯教练型并说明理由。

### A. 摄影（调色为锚）

| name | 一句话 | 确定性部分 | 分 / 先做票 | 批次与判断 |
|---|---|---|---|---|
| [ ] **电影感调色**（必做，方案见第三部分） | 输入一张照片，出一张电影感、色彩鲜明、可以直接发的成片，外加剧照卡、前后对比和 .cube LUT | 全部像素处理：浮点线性光管线、filmic 曲线、OkLCh 调色、光晕与颗粒、画幅、LUT 导出与回读校验、QA 数字 | — | **本轮锚点** |
| [x] `photo-render-color-fidelity`（四个渲染 skill 的扩展；0.22.4 随第一部分 A4 做完：五个 skill 带相同的 `image_io.py` 1.1.0） | 每个渲染 skill 放一份相同的 `image_io.py`：读图先按 EXIF 转正、带着 ICC 走，写出时按 keep / 转 sRGB 两种策略嵌回，报告写明源色彩空间 | Pillow + littlecms2（本机已确认）。提出者实测：Display P3 照片走完三个现有渲染器，高饱和的橙和红偏 ΔE2000 5.7–7.2，中性灰偏 0，所以用灰调测试图永远查不出来 | 5.0 / 3 | **第一批。** 和调色 skill 同期做或先做：调色的卖点就是颜色，下游装框、成套一洗色，使用者会以为是调色没调好。顺带修掉第一部分 A4 的 ICC 与方向问题 |
| [ ] `photo-export-prep` | 成片出门前最后一步，按去向分两路：社交或网页（定尺寸比例、输出锐化、转 sRGB 并嵌 profile、剥 GPS 和序列号）；冲印（按物理尺寸算有效 PPI，用冲印店 ICC 出色域外遮罩） | 平台规格表带核对日期和出处，超 180 天报警；锐化量随缩放比线性决定；JPEG 质量从 92 往下试到满足体积上限；色域外遮罩 | 4.0 / 2 | **第一批**，接在调色之后。青橙这类高饱和调色大量超出相纸色域，屏幕上完全看不出来，打出来橙色发土 |
| [ ] `grade-series-matcher` | 把一个定稿的 look 推到同一组 N 张上：先把每张的曝光和白平衡基底对齐到参考张，再套同一个 look，出一致性矩阵；拍摄者标记的有意变化（日落推进、室内外切换）不抹平 | CIELAB 分位数与中性轴偏移估计、基底对齐、逐张 ΔE 矩阵；只有成片没有参数时，用"参考源片→参考成片"拟合一个 17³ LUT，色域外格点标"外推" | 4.0 / 0 | 第二批，等调色 skill 能导出 .cube 之后。它只回答"同一个 look 怎样在 N 张上还是同一个 look"，从不创造新 look |
| [ ] `shoot-cull-assistant` | 几百张的拍摄压成连拍组拼图和测量证据，模型看组拼图写带帧号和理由的候选，留还是淘汰由人定；只出清单，不删不移任何文件 | dHash + 拍摄时间分组；8×8 分块 Laplacian 方差与"最锐块÷全画面中位数"（区分浅景深主体锐和整张虚）；剪切面积；Haar 人脸框内锐度 | 3.7 / 0 | 第二批。关掉的默认很具体：300 张逐张读进上下文，读到一半截断，后半场没看也说"挑完了" |
| [ ] `photo-critique-coach` | 使用者主动请求时点评 1–3 张：每条意见落在编号网格的某一格，标明是测量事实、视觉观察还是给拍摄者的问题；不打分，不改像素 | 地平线与主导直线倾角（Canny + Hough，合成图 3.2° 估出 3.20°）、分块锐度热力图、边缘侵入、剪切位置、显著性 | 3.0 / 0 | 备选。模型看到的是约 1568px 的降采样图，歪 0.5° 和 2° 分不清，所以几何类判断必须交给脚本 |
| [ ] `photo-sequence-editor` | 10–40 张跨场景的组照：画出焦距、明暗、色度、朝向四条轨道，标出相邻冲突（近重复、连续三张同景别、明暗剧跳），模型给一两个带相邻理由的编辑方案；开篇、收尾、删减由人定 | 逐张属性提取 + 节奏条渲染 + 相邻冲突规则 | 2.7 / 0 | 备选。一位评审建议并进 `photo-series-layout`，但那个 skill 只收 3–9 张，并进去就得放宽它的范围，另两位评审按独立 skill 评的 |
| [ ] `shoot-outing-review-card` 扩展：两次对比 | `--compare prev.json` 对比两次外拍的习惯分布；使用者要求时给最多三条"下次试试"的约束，下次对比时报告执行了多少 | 分桶占比变化 + Jensen–Shannon 距离；覆盖率低于 30% 的字段不比 | 3.3 / 0 | 备选。把回顾卡接上 weekly-study-review 那条判据："下次会不会因此做点不一样的事" |

### B. 物理、建模与研究

| name | 一句话 | 确定性部分 | 分 / 先做票 | 批次与判断 |
|---|---|---|---|---|
| [ ] `model-fit-auditor` 扩展：吻合分级 | 把"理论与实验吻合"分成三档：A 零参数预言、B 用独立数据标定后预言、C 同一批数据拟合；每档配固定措辞，可选再做无量纲塌缩检验 | 每个理论参数登记来源与 run ID；拟合用的 run 与比较用的 run 是否相交；点数与参数数之比；只在留出的 run 上算指标 | 4.3 / 2 | **第一批。** 关掉的默认是 IYPT 报告最常见的收尾"吻合良好（R²=0.98）"，而曲线里的参数正是拿同一批 6 个点拟出来的。改现有脚本，比开新 skill 省 |
| [ ] `experiment-sweep-planner`（吸收 measurement-resolution-budget） | 采集之前把"扫多宽、取哪些点、每点几次、按什么顺序测、记哪些列"算清楚，采集后核对记录表是否照做；第一步先算仪器看不看得见要测的东西；开头写一份调查契约（可测响应量、控制量、范围、什么结果会推翻它） | 双对数斜率标准误与两条候选指数的分辨度（例：0.7 个数量级、σ=8% 只有 2.3σ）、达到 3σ 需要的最小跨度或 N；随机化采集顺序；帧数、拖影像素、Nyquist 倍数、res/√12 | 4.0 / 2 | **第一批。** 物理流水线在"机制"和"数据"之间正好缺这一段：decomposer 的交接模板写着下一步是实验设计，库里没人接 |
| [ ] `contest-ai-use-ledger`（吸收 ai-use-disclosure-ledger） | 比赛第一小时起每用一次 AI 记一笔；提交前对照论文源查内联引用；按规则生成 AI 使用附录（COMAP 系列用了 AI 就必须交）。规则有歧义只引原文、标【待确认】，不替组织方裁决 | 只追加的 JSONL；对照 LaTeX 源查引用与参考文献；高审慎类别（选模、代码、解读）有无核验记录；可选从本机会话记录与 git 尾注导入证据（只取项目目录内、只计数不摘原文） | 3.7 / 2 | **第一批**，下一场建模赛之前做。仓库初建时的 planned 行 competition-ethics-checker 照原样做只会是个意见生成器，改成出处账本 |
| [ ] `modeling-data-source-auditor` | 把从外部找来的数据整理成 modeling-code-builder 能签收的数据契约：每条序列写明出处、取数日期、原文定义、单位与口径 | 覆盖矩阵与插补占比；两份来源重叠区的比值诊断（恒定且近 10 的幂 → 单位或数量级错；随年份漂移 → 价格基准不同；随键变化 → 口径不同）；连接键匹配率 | 4.0 / 1 | 第二批，建模赛前做。建模九个 skill 只剩"数据从哪来、口径对不对"这一环空着 |
| [ ] `experiment-video-tracker` | 手机实验视频变成带真实时间轴和不确定度的 x(t)、y(t)；先查慢动作重定时和可变帧率，再用参考片段验证时间尺度，跟踪参数冻结后才交给下游 | ffprobe 逐帧时间戳；参考片段拟合时间尺度因子（自由落体拟出 g/64 说明时间被拉长 8 倍，偏差超出不确定度就停）；比例尺标定含视差；颜色或模板跟踪 | 3.7 / 0 | 第二批，前提是你还在做 IYPT 型实验。关掉的默认：按名义 30fps 或"240fps"硬算，时间轴差 8 倍或逐帧抖动 |
| [ ] `prior-work-regime-mapper` | 使用者拿到的几篇文献逐篇登记：在什么参数区间测了什么、主张了什么；再用无量纲数判这个区间和你的实验区间重不重叠 | 复用 `_shared/dimensionless-groups.md` 的定义算 Re、Bo、We 等与几何比，对数轴上逐组算重叠，判"可搬用 / 边缘 / 外推" | 3.3 / 0 | 备选。literature-reading-coach 的重塑：原定义正是 Agent 最容易编造文献的场景 |
| [ ] `physics-fight-role-trainer` | IYPT/CYPT 正方、反方、评论方的限时攻防演练：攻击面从本队台账里带状态标签的薄弱处编出，按当年规则计时，按回答里有没有数字、证据位置、适用条件打分 | 攻击面排序规则；计时 | 2.7 / 0 | 备选。脚本内核小，还依赖几份目前不存在的上游台账。opponent-question-practice 如果要做，按这个方向重塑 |
| [ ] `keynote-deck-builder` 扩展：IYPT 报告场合 | 第五种场合，拍点从"做了多少工作"改成"题目问什么、答案是什么、凭什么这么说"，证据片带 run ID 与吻合等级 | 大纲检查（每条题目要求至少一张有数据的证据片） | 3.0 / 0 | 备选。keynote 的 SKILL.md 已经 73.6KB，要加也只能加在 references 里、按场合读取。iypt-report-evidence-map 并入这里 |

**planned 行的处置**（这些行是仓库 2026-07-29 初建时写进索引的，早于第一轮）：research-question-coach 并入已有 skill：选题归 project-brainstorm，IYPT 现象定题归 competition-scenario-extractor 与 physics-mechanism-decomposer，剩下唯一有用的一步（把"研究 X 对 Y 的影响"写成可测响应量、控制量、范围和推翻条件）并入 experiment-sweep-planner 的开头；literature-reading-coach → prior-work-regime-mapper；experiment-design-guide → experiment-sweep-planner；assumption-checker **删**（已被 modeling-assumption-builder、problem-formalization-coach、competition-scenario-extractor、model-critique-coach 四处覆盖）；competition-ethics-checker → contest-ai-use-ledger；opponent-question-practice → physics-fight-role-trainer（备选）。

### C. 编程与 AI 使用

| name | 一句话 | 确定性部分 | 分 / 先做票 | 批次与判断 |
|---|---|---|---|---|
| [x] **发布会 bento 信息图** `bento-infographic`（必做，方案见第四部分；0.1.0 已登记，Library 0.24.0，2026-10-10） | 苹果发布会收尾那种总结图：主图居中，四周 13–17 个圆角格；产品和研究成果都能放，画幅比例任意 | 以标签字号 u 为单位的尺寸换算；排版器（主图居中、外圈切分树、匈牙利分配、打分与束搜索）；无头 Chrome 渲染；自检（溢出、字体回退、对比度、主图位置、格缝与圆角是否统一、图片放大倍数）；五张苹果样图做结构回归 | — | **你点名要做**（2026-10-07），不参与打分。取代 `launch-summary-panel`（E 节） |
| [ ] `ai-diff-review-protocol` + `ai-code-onboarding-checklist` 扩展：补脚本（0.22.4 已做 `diff_risk.py`；`intake_scan.py` 与共用信号模块未做） | diff-review 补 `diff_risk.py`，onboarding 补 `intake_scan.py`，两者共用一个代码信号模块 | 任意 unified diff：文件数、增删、重命名、权限变化；路径按边界分类（迁移、锁文件、CI、配置、鉴权、测试）；hunk 级信号（NOT NULL 无 DEFAULT、DROP、删掉的断言、shell=True、eval、rm -rf）；锁文件新增包计数 | 4.3 / 2 | **第一批。** diff-review 的 description 承诺"统计由脚本出"，目录里没有脚本（第一部分 A5）；onboarding 自己没声称有脚本，落差在第一轮规划表与索引那一层 |
| [ ] `ui-design-system-builder` 扩展：`css_token_lint.py` | 把反默认清单和对比度里能数的部分交给脚本；`--profile maestrwave` 让 maestrwave 的自查也跑它 | 解析 `:root` 与主题下的自定义属性，展开 `var()` 与 `color-mix()`，对"文字 × 表面"矩阵算 WCAG，不达标时给出过线所需的最小 alpha；反默认字体、颜色、圆角、阴影检查 | 3.7 / 2 | **第一批。** 第一轮 A4 的第三条，这次有了实测收获：MaestrWave 自己的 `.field-label` 不达标（第一部分 B2） |
| [ ] `ai-output-fact-checker` 扩展：`claim_probe.py` | 离线抽声明、生成台账骨架；显式 `--online` 才向 PyPI、npm、Crossref、arXiv 发只读查询，专抓"DOI 存在但指向另一篇"和"包名存在却是新近抢注的幻觉名" | 声明抽取；导入名与发行名别名表；首发日期、发布次数、DOI 元数据标题比对 | 4.0 / 1 | 第二批。对应第一部分 A5 与 C 节的 DOI、抢注两条 |
| [ ] `stage-render-checker` | 用本机无头 Chrome 断网渲染单文件 HTML 视觉产物（面板、语录卡、演示片、照片版面），出 PNG，并量出被裁掉的文字、越出舞台的元素、中文孤行、字号下限、对比度、外部请求、字体回退 | 注入测量脚本 + `--dump-dom` 取 JSON + `--screenshot`；host-resolver 规则断网 | 4.0 / 0 | 第二批。四个视觉 skill 都不量渲染结果：keynote 用无头 Chrome 导 PDF、spread-composer 走浏览器打印，都没有量裁切和溢出。第一部分 B2 的 radio 中文溢出就是它能抓到的那类问题。依赖和 keynote 的 `export_pdf.sh` 相同 |
| [ ] `context-load-auditor` | 给 SKILL.md、CLAUDE.md 与 references 算载入账（常驻 / 触发时 / 按需），找出写在正文里、实际挡不住任何东西的"不读这一节" | 按层级估 token；抓同文件内的无效门控 | 3.3 / 0 | 备选。context-budget-planner 的重塑：每轮预算没法事先规划，能量也能砍的是固定载入。评审要求砍到这两项功能，误触发与版本规则两项分别交给别的提案 |
| [ ] `scope-fence`（吸收 edit-plan-builder、patch-scope-controller） | 动手前写一份围栏清单：只准动哪些文件、预算多少行；Claude Code 里用可选的 PreToolUse hook 当场拦下越界写入，收尾用 git diff 对账；并行子代理的写集合派发前查互不重叠 | 通配匹配 + hook 退出码 + diff 对账 | 3.3 / 1 | 备选。一票先做、一票否决：能做成强制执行，但和你的主线关系不大，plan mode 与 ai-diff-review-protocol 覆盖了大部分。hook 会自动执行，按 CONTRIBUTING 第 4 节必须 opt-in、单独测过 |
| [ ] `fix-loop-breaker` | 红→绿调试循环记成文件台账：失败签名归一化后判断是否原地打转，扫每一轮 diff 找"让测试变绿而不是让代码变对"的弱化手法（skip、放宽容差、改期望值、删断言） | 签名归一化、相邻 diff 相似度、测试弱化扫描 | 3.3 / 0 | 备选。流程建议已有 superpowers:systematic-debugging，它只补文件化计数与 diff 扫描 |

**coding-helper 八个 planned 行的处置**（仓库初建时就挂着）：coding-project-brief-builder 并入 prompt-brief-builder；architecture-planner **删**（没点名任何要关掉的默认，plan mode 与 feature-dev 已做得不错）；repo-map-compressor **删**（预生成的 repo map 会过期，还会被整份读进上下文，恰好违反"不默认读整个仓库"）；context-budget-planner → context-load-auditor；edit-plan-builder、patch-scope-controller → scope-fence；multi-agent-task-router **删**（harness 的子代理与 workflow 已覆盖，唯一缺口"写集合不重叠"并入 scope-fence）；test-debug-loop → fix-loop-breaker。处置完之后，第一部分 G 节里 README 那句"token 纪律在 coding-helper"必须改写。

### D. 申请、社群、作词、写作与仓库工具

| name | 一句话 | 确定性部分 | 分 / 先做票 | 批次与判断 |
|---|---|---|---|---|
| [ ] `skill-release-steward`（**仓库工具**） | 改完 skill 之后做发版记账：按 git 差异算出这次改动要求哪些地方跟着变，逐项核对 frontmatter、变更记录、索引版本列、Library 四处版本、README 计数、dist 包；递增级别按 VERSIONING 判定表给建议，push 与上传留给使用者 | git diff 定位改过的 skill；逐项等值比对；dist zip 内容哈希对源目录；把"这次提交相关"和"历史遗留"分开列 | 4.7 / 3 | **第一批**，三票先做（与 color-fidelity 并列）。本轮审计最常见的一类问题就是记账漏一处（第一部分 G 节），历史里也有 f0347ae"漏登记修正"、0.22.3"顺带修掉 0.22.2 留下的不一致"。评审指出它只服务本仓库，**做成 `scripts/` 下的脚本加 `validate.sh` 检查，不进 dist**。和 validate 分工：validate 查"登记在不在"，它查"改了之后该跟着变的有没有跟着变" |
| [ ] `essay-revision-coach`（吸收 esl-essay-diagnoser） | 只处理学生自己写的英文文书草稿：问题清单定位到段和句，每条以一个追问收尾，**不给任何能直接替换进文章的句子**；另查中文母语迁移错误 | 词数对照限额；逐段具体细节密度（数字、专名、引语、时间地点标记）；总结句与陈词表；**本会话助手输出与新稿的重合比对**，防止示范句混进稿子；母语迁移高精度词组表 | 4.3 / 2 | **第一批，前提是你今年申请。** ED/EA 在 11 月 1 日前后，按 application-timeline-builder 的节点主文书 10 月初定稿。也给第一部分 D 节两处悬空的"文书类 skill"一个落点。esl-essay-diagnoser 的中英底稿对照模式移给 application-consistency-auditor |
| [ ] `activity-list-optimizer` 扩展：Honors 与奖项台账 | 新增 Honors 栏（5 条、标题 100 字符、年级、级别）和一份奖项台账：每个奖的官方英文名、获奖轮次、级别、选拔数据都要带来源；附本地 UTF-16 计数脚本，没有 nestudy 时回退 | 字符计数；"填写的级别不得高于获奖轮次对应的级别"；出现"top x%""1 of N"但台账里没有选拔数据就报 | 4.0 / 2 | **第一批**，与文书同期。关掉的默认："全国中学生物理竞赛（省级赛区）一等奖"被译成 National First Prize、级别勾 National，还自造"top 1%"。也修第一部分 E 节的无工具回退 |
| [ ] `program-maturity-navigator` 扩展：签到台账（吸收 roster-ledger） | 从每场签到表算到场数、圈外新人、再来第二次的新人、去重总人数，替代 history.json 里手填的整数 | 姓名规范化加本地盐哈希，产物里只出现哈希或计数；编辑距离为 1 的列为"可能同一人"交人确认；回写字段并标 `source: sheet / recalled` | 4.0 / 2 | **第一批**，等你下一次办活动时做。navigator 最硬的一道闸"圈外新人再来第二次"，现在读的是手填数字，凭记忆就能过闸 |
| [ ] `application-consistency-auditor` | 提交前把活动栏、Honors、主文书、补充文书、额外信息、简历摆在一起对账：同一活动或奖项的人数、职位、日期、级别对不上的全部报出，不替学生选哪个版本 | 抽取数字与所修饰的名词、年月、职位词、奖项名（按台账别名归一），按实体对齐；报冲突、"只在申请里出现"的数字、人次与人数混用；中英底稿事实对照 | 3.7 / 1 | 第二批。前几轮 AI 润色时悄悄加码的数字（18 人、30 人团队、20 多名学生），逐份审永远查不出 |
| [ ] `recommender-brief-builder` | 把经历按"谁亲眼见过"分给各位推荐人，每人一页可核实的事实清单加一张覆盖矩阵；推荐信一个字都不写 | 每条证据是否分给见证人、日期是否落在接触期内、跨推荐人重复、倒推请托日期（读 timeline 的表） | 3.3 / 1 | 第二批。边界要写死：国内常见"老师让学生自己写推荐信"，这个 skill 不接 |
| [ ] `lyric-structure-mapper` 0.2.0：MIDI 入口 + 小节换算（两条扩展合一） | 有旋律时从 MIDI 按休止切句、数音符，直接产出 `xxxxx` 模板并标长音位、换气跨度、一字多音；没有旋律时按 BPM、拍号与字密度把骨架换成逐段起止小节，导出与 llm-midi-composition 蓝图同形的段落表 | 纯标准库 SMF 解析（running status、力度 0 视为 note-off、tempo 与拍号）；逐行拍数与小节；替换掉第一部分 C 节那个错的"每分钟 180–240 字" | 3.7 / 0 | 第二批。接通"先词后曲"和"LLM 写谱"两条线 |
| [ ] `impact-evidence-ledger` | 对外讲"影响"时，每个数字落到签到表或测量记录上：产出、覆盖、效果三类分开，逐条标有据或无据 | 去重人数、人次、回头率；六类口径问题（人次当人数、百分比无分母、效果无基线、无出处引语……） | 3.3 / 0 | 备选。impact-report-builder 的重塑，并吸收 community-needs-interviewer 测基线的那一半；与 navigator 签到台账共用去重代码 |
| [ ] `speech-script-ear-editor` | 要念出来的中文讲稿做"耳朵体检"和计时：先标定你本人的语速，再对齐 deck-outline 的逐片出场，算每片、每步、总时长；扫换气过长、"的"字串、书面虚词、同音易混词、数字与缩写读法 | 语速标定；讲稿与大纲的步对齐；风险词表 | 3.0 / 0 | 备选。keynote-deck-builder 明确不管讲稿，writing-rules 管的是给人读的散文，讲稿落在空档里 |
| [ ] `lyric-doctor` 扩展：音韵层 | 行末辙口、前后鼻音混押、长音位闭口、句末连续去声、同声母连缀，从"模型凭语感"挪到脚本 | pypinyin 按词组取调（**本机未装**，要声明依赖、缺失时降级）；韵母映射十三辙 | 3.3 / 0 | 备选。先修第一部分 A3 的 lyric_check 解析问题和 B3 的黑名单漂移 |
| [ ] `melody-lyric-fit-checker` | 歌词一字一音对齐到旋律，查倒字、长音与高音落在闭口音上、歌手音域 | 建在 MIDI 入口与音韵层之上 | 2.7 / 0 | 备选，排在上面两条之后 |
| [ ] `skill-case-runner`（吸收 skill-trigger-tester；**仓库工具**） | 让 `tests/cases/*.md` 真能跑：先体检用例能不能复现，再用 `claude -p --plugin-dir` 无交互跑，过程约束从事件流机检，其余交独立判分，结果按 commit 留档 | 用例拆解与可复现性分类；事件流解析；Wilson 区间 | 2.7 / 0 | 备选。每次都花真实额度，依赖 Claude Code CLI，评审建议做成 `scripts/` 下的仓库工具。**第 ① 步"用例体检"便宜，可以先单独做**：283 个用例里，提出者能解析出输入段的 242 个中约 108 个只是在描述输入（"用户贴了一段 800 字的演讲稿"），没有能直接贴进去的真实输入 |
| [ ] `summer-program-vetter`、`seminar-question-designer` | 夏校与选拔营对比表（每个字段带来源与访问日期、按资格过滤、入营题不碰）；读书会讨论题（每题至少两种都站得住的读法，锚在逐字可查的原文上） | 字段来源与过期检查、时区换算；引文逐字核对 | 2.7 / 0 | 备选 |

**其余 planned 行的处置**：workshop-designer 重塑后保留（只在 navigator 的 G3 通过后触发，输入用现成的 Workshop Plan 模板，脚本查分段时长、缓冲与产出），这一行是 0.21.0 才加的，提出者建议等 navigator 在真实活动上过一次 G3 再动手；chapter-note-starter **删**（"起草阅读笔记"就是替学习者思考）；literary-analysis-coach 与 quote-to-thought 合并为 reading-note-coach（学生先写，模型把每段标成概括、观察或主张，只对纯概括段问一个推向主张的问题）；note-polisher **不单独建**（两位提出者一个说删、一个说并进 writing-rules，结论相同）；personalized-review-scheduler **删**（Anki 与 FSRS 做得更好，skill 也没法跨会话持有复习状态）；community-needs-interviewer 并入 impact-evidence-ledger；service-project-planner **删**（brainstorm、navigator、deadline 三个已覆盖）；impact-report-builder → impact-evidence-ledger。

两位提出者意见不同、需要你拍板的两行：
- **vocab-error-diagnoser**：一位主张重塑为只从学生自己写错的语料出发、导出 Anki，没有真实错误语料之前不建；另一位主张并入 esl-essay-diagnoser（现已并入 essay-revision-coach）。我倾向先让 essay-revision-coach 把错误记成台账，积累够了再决定要不要拆出来。
- **example-sentence-builder**：一位主张并入 vocab-error-diagnoser，另一位主张删（它的默认产物就是模型编的例句，而搭配错误正是模型造句最容易犯的）。两者都不单独建，我倾向删。

### E. 否决与合并（防止下轮重提）

| 提案 | 处置 | 理由 |
|---|---|---|
| `photo-outing-pipeline` | 并入 photo-export-prep（两位评审），第三位主张否决 | 导出与隐私和 photo-export-prep 重复，调色一致性和 grade-series-matcher 重复，ICC 和 color-fidelity 重复。它唯一真实的发现（调色后 EXIF 丢失、再加框时信息带变空）改为电影感调色 skill 的一条要求：原片 EXIF 存成边车文件 |
| `race-pace-chart` | 否决（两位评审） | 输入拿不到：按轮胎分段需要逐圈的轮胎与胎龄数据，免费接口不带，FastF1 没装还得下载。F1 兴趣从 radio-quote-card 看得出，等你真开始发赛事分析再说 |
| `lyric-karaoke-video` | 暂缓 | 建在 MIDI 入口之上；本机 ffmpeg 没编 libass，要走 PIL 逐帧叠层。先做 lyric-structure-mapper 0.2.0 |
| `iypt-report-evidence-map` | 并入 keynote IYPT 场合 | 证据 ID、备用片索引、计时与 keynote 扩展重叠；"预测还是拟合"由 model-fit-auditor 的吻合分级定义 |
| `measurement-resolution-budget` | 并入 experiment-sweep-planner | 同一时点用，它的散布下限正是 sweep-planner 的输入，单独撑不起一个 skill |
| `ai-use-disclosure-ledger` | 并入 contest-ai-use-ledger | 同一件事；它从本机会话记录与 git 尾注取证的做法作为 import 子命令保留 |
| `esl-essay-diagnoser` | 并入 essay-revision-coach | 同一份英文文书；单独存在时，它的 AI 语域指纹表会被当成"规避 AI 检测"清单用 |
| `program-maturity-navigator-roster-ledger` | 并入 navigator 签到扩展 | 同一件事；加盐哈希、"可能同一人"不自动合并、来源标记这几点更好，合并时保留 |
| `lyric-structure-mapper-bar-grid` | 与 MIDI 入口合成一次 0.2.0 | 同一个 skill 的两个方向 |
| `skill-trigger-tester` | 并入 skill-case-runner | 同一套无交互运行与事件流解析 |
| `launch-summary-panel`（已废弃，0.1.2，2026-10-10） | 废弃，由 bento 信息图取代 | 2026-10-07 你的决定：它达不到"字体、字号、排版和主体突出都和苹果一致"，差在哪见 4.1。先出清单再出图的两步走、事实校验规则搬进新 skill |

### F. 建议的先后

**先修第一部分的 A 节**，尤其 A1：插件装不上，新 skill 做了也用不上。然后第一批的 11 条按下面的顺序，括号里是前提：

1. **电影感调色 + `photo-render-color-fidelity`**。你点名要的；调色从第一版起就用 `image_io.py` 存片。之后接 `photo-export-prep`。
2. **`skill-release-steward`**（仓库脚本）。这一轮要新增一批 skill，每加一个都要动五六处地方，先有它，后面每次发版都有人记账。
3. **两个小的补脚本扩展**：`diff_risk.py` 与 `css_token_lint.py`。都是兑现已有承诺，工作量小。
4. **`model-fit-auditor` 吻合分级 + `experiment-sweep-planner`**。补上物理流水线"机制 → 数据"之间的空段，两条都有可算的内核。
5. **`essay-revision-coach` + Honors 扩展**（你今年申请的话，10 月内）。
6. **`contest-ai-use-ledger`**（下一场建模赛之前）、**navigator 签到台账**（下一次办活动时）。

**bento 信息图**（2026-10-07 加，你点名要的）不依赖上面任何一条，可以和调色并行。按 4.12 的 11 轮做，第 1、2 轮可以同时开。它的自检和第二批的 `stage-render-checker` 量的是同一类东西，先做的那个把代码留给后做的。

第二批：grade-series-matcher、modeling-data-source-auditor、claim_probe、stage-render-checker、application-consistency-auditor、recommender-brief-builder、lyric-structure-mapper 0.2.0、shoot-cull-assistant、experiment-video-tracker。

**一条共同的工程约定：新写的共享代码怎么放。** 这一轮有六七条提案要在多个 skill 之间共享代码（图像读写、WCAG 计算、SMF 解析、签到去重、代码信号）。第一部分 G 节已经实测：`_shared` 目录在单技能 zip 里会丢。按评审的一致意见：**新写的共享代码，每个用到它的 skill 各放一份相同的副本，`validate.sh` 查各副本的 sha256 必须一致**。这样插件安装和单技能 zip 都不用额外处理，改一处漏改别处会被校验拦下。已有的 `_shared` 参考文档体量大、引用多（20 个 skill），复制不划算，交给第一部分 G 节的打包脚本处理。

---

## 第三部分：电影感调色 skill 方案（必做）

你的要求是：输入一张照片，按电影化的风格处理，色彩鲜明，做成非常精美的图片。这一节是完整方案，外加一个已经能跑的原型。原型的实测数字、样图和评审结论见 3.9。

### 3.1 名字与触发

- **name**：`photo-cinematic-grade`，分类 photography，`display_name`：电影感调色
- **description**（中文触发在前）：

> 当使用者说"把这张照片调成电影感""调出电影色调""做成电影剧照""青橙色调""胶片感""调得色彩鲜明一点""像电影截图那样""加电影黑边"时使用。输入一张照片：脚本先分析画面、渲染 2–3 个风格的对比小样，使用者选定后输出全尺寸成片、2.39:1 剧照卡、前后对比图和 .cube LUT。所有像素处理由确定性脚本完成，同样的参数每次得到同样的结果。不增删画面内容，不磨皮、不改脸型、不换天空；不声称复刻某部电影或某款胶片；曝光严重失误或对焦糊掉的照片会直接说明调色救不回来。

**回应第一轮的否决。** 第一轮否决过 look-specification-builder，理由是模型看不到样片背后的美学意图。这个 skill 不需要模型去读懂意图：风格库是写死的配方，模型只负责从库里挑两三个候选，理由写成一句话；选哪个由使用者看着真实渲染出来的小样决定。

### 3.2 工作流

1. **最多问两句**：想要什么气氛（说不上来就回答"你来挑"），要发到哪里（决定画幅和导出尺寸）。使用者什么都不说，就直接走第 2 步。
2. **分析**：`cinegrade.py analyze photo.jpg` 输出 JSON：亮度基调（低 / 中 / 高调）、动态范围、剪切比例、主要色相族及权重、肤色像素占比、饱和度、偏色，以及按固定规则给出的 2–3 个候选风格和各自一句理由。模型再自己看一眼照片，补上脚本看不出的东西：主体是什么、在画面哪里、是人像还是风景还是夜景。
3. **小样**：`cinegrade.py sheet` 把原图和候选风格排成一张对比图，发给使用者。
4. **选定与微调**：使用者选一个风格，可以调强度（0 为原图，1 为默认），剧照卡可以调 2.39:1 裁切的上下位置。
5. **导出**：`render` 出全尺寸 JPEG（质量 95、4:4:4、嵌 ICC），可选 16 位 PNG；`card` 出剧照卡；`compare` 出前后对比；`lut` 出 33³ 的 .cube 并做回读校验。每次渲染附一份 QA JSON。
6. **交付**：成片、剧照卡、前后对比、LUT 和 QA 数字一起给；超出护栏的项写明，交给使用者决定是否降强度。

**模型的眼睛信到哪一步。** 模型看到的是降采样、没有做色彩管理的图。可以信它判断场景、主体位置、气氛合不合适；3 ΔE 以内的色差、肤色准不准、有没有断层、高光剪没剪、画面歪没歪，一律看脚本的数字，不凭眼睛下结论。

### 3.3 确定性与判断的分工

| 环节 | 脚本（确定性） | 模型 | 使用者 |
|---|---|---|---|
| 读图 | EXIF 转正；嵌入的 ICC（如 iPhone 的 Display P3）转换并报告；8/16 位 | — | — |
| 分析 | 亮度基调、剪切、色相族、肤色占比、偏色、候选风格规则 | 补充场景与主体判断 | — |
| 风格 | 每个风格是一组写死的参数 | 从库里挑 2–3 个候选并写理由 | 看小样选一个 |
| 强度与裁切 | 按参数渲染 | 给建议值 | 最终决定 |
| 质量 | 剪切增量、肤色色相漂移、肤色色度比、断层、色域映射占比、LUT 回读误差 | 读 QA 数字，超标时建议降强度 | 在自己的屏幕上看终稿 |
| 剧照卡文字 | 排版、字体回退、字数限制 | 可以建议一个标题 | 标题由使用者给或确认 |

### 3.4 风格库

六个风格都是写死的参数，每个都能用强度 0–1 缩放（0 与原图一致）。名字是描述性的；英文 id 是脚本参数。

| 风格（id） | 配方 | 适合 | 不适合 |
|---|---|---|---|
| 青橙（`teal_orange`） | 暗部推青（色相 225°），中性色降温，高光与肤色偏暖（62°）；对比 1.25，黑位下压；蓝天转青，绿转青；饱和的暖色主体不被染青 | 有人物或暖色主体、同时有天空或阴影可推冷的画面；带灯的傍晚 | 几乎全是暖色、没有冷色可推的画面（猫这张最弱，刚过区分度下限） |
| 霓虹夜（`neon_night`） | 低调（曝光先压 0.25 EV，最多 0.9 EV），暗部青蓝（238°），高光品红粉（345°），光源周围红品色光晕 | 低调、带彩色点光源的夜景。分析规则只在这种画面推荐它 | 白天的暖色画面：猫这张被压暗 0.84 EV，发闷 |
| 金色时刻（`golden_hour`） | 琥珀高光（82°），暖棕暗部，柔和的暖色 bloom，橙黄更浓，低反差（1.02） | 中性或偏冷、想要暖的画面；逆光 | 本来就全暖的画面会过黄（本轮猫的剧照卡就是这样） |
| 拷贝片浓郁（`print_film_rich`） | 红更深更纯，暗部偏青（195°），高光奶油暖，密度 0.6（饱和色变深而不是变亮），轻微抬黑，高光肩部柔 | 红、橙主导的画面，静物、街景；四张样图上最稳的一个 | 要干净冷调的画面 |
| 粉彩童话（`pastel_storybook`） | 抬黑（0.08），低反差（0.82），薄荷暗部（172°），奶油高光，粉红，负密度（饱和色变亮） | 高调、柔光、想要轻盈感的画面 | 大面积纯黑的画面：导出的 LUT 在最暗部偏差大（见 3.9） |
| 素净（`quiet_neutral`） | 只加一点反差和密度，极轻的冷暗部与暖高光 | 只想"更像电影"而不想改颜色的人；也是其他风格的对照 | "色彩鲜明"的要求，它本来就不负责鲜明 |

所有风格共用同一套管线：浮点线性光；在 Oklab 亮度上做端点固定的 S 曲线，亮部色度向白滚降（不把 ACES 或 Hable 曲线直接套在 JPEG 上，那会把纯白 255 压成 232 或 186）；OkLCh 里做分色相调整、分离色调和减法密度；光晕、bloom、颗粒、暗角在线性光里做，尺寸按图像短边的比例取；最后在 sRGB 编码域加三角分布抖动再量化到 8 位。

### 3.5 质量护栏

阈值来自调研报告的建议值，再用原型的实测数字核对过。脚本把每一项写进 QA JSON，超标时由模型建议降强度，最后由使用者决定。

| 护栏 | 阈值 | 本轮实测（四张样图 × 六个风格） |
|---|---|---|
| 肤色色相平均漂移 | ≤ 6° | 色板测试最大 4.4°（霓虹夜）；宇航员人像全部在范围内 |
| 肤色色度比 | ≤ 1.15 | 最大 1.12（色板测试的金色时刻；宇航员人像上最大 1.116） |
| 高光剪切增量（任一通道 ≥ 254） | ≤ 0.5 个百分点 | 全部 ≤ 0，没有一个风格让剪切变多 |
| 死黑增量（Oklab L < 0.05） | ≤ 1 个百分点 | 最大 +0.08 |
| 区分度：鲜明风格与原图的 ΔE_OK | ≥ 0.035 | 全部通过，最小 0.036（猫，青橙） |
| 区分度：任意两个风格之间 | ≥ 0.025 | 全部通过，最小 0.027（火箭，青橙对拷贝片浓郁） |
| 强度 0 与原图一致 | 颜色路径 p99 ≈ 0 | p99 1.0e-4 |
| 同一种子，输出字节相同 | 必须 | 通过 |
| LUT 回读（33³，四面体插值） | p99 < 0.02 | 五个风格通过（0.003–0.016）；粉彩在宇航员上 0.053（65³ 时 0.034），未通过 |
| 断层（最平滑区域的量化残差） | 比源图增加 ≤ 0.35 个码值 | 全部通过，最大 +0.19（咖啡，粉彩） |
| 色域映射像素占比 | 只报告；> 10% 警告 | 原型还没统计这一项 |

区分度这两条是本轮加的：第一版原型在暖色照片上，六个风格几乎都塌回原图，量出来才知道问题有多大。

### 3.6 边界

- **不改内容**：不做生成式填充，不去掉物体，不换天空，不磨皮，不改脸型或身形。有人要"把旁边那个人去掉"，说明这不在本 skill 范围内。
- **不冒充**：风格用描述性名字（青橙、霓虹夜、金色时刻、拷贝片浓郁、粉彩童话、素净）。可以说"带有某类胶片的特征"，不说"这就是某某胶片""和某部电影一模一样"。胶片型号和片名是别人的商标或作品，只作描述性参照。
- **不打包第三方 LUT**：RawTherapee 的胶片模拟合集是 CC BY-SA，ShareAlike 条款会传染；网上流传的合集有的疑似从商业软件里提取。所有 LUT 由自己的代码生成。
- **救不回来就直说**：高光大面积剪切、严重欠曝、对焦糊掉，分析阶段就报出来，说明调色只能改颜色、救不回丢掉的细节。
- **HEIC**：本机没有 pillow_heif。先用 `sips -s format jpeg in.heic --out in.jpg`（macOS 自带，保留 EXIF），或者使用者自己装 pillow-heif。
- **EXIF 与隐私**：成片默认不带 GPS、机身序列号；拍摄参数（光圈、快门、ISO、焦距、镜头、拍摄时间）另存一份边车 JSON，供 photo-exif-frame 加框、photo-caption-writer 写图注时读取。这样修掉了"调色后再加框，信息带是空的"那个问题。
- **不覆盖原片**：输出路径解析后与输入相同就拒绝；已存在的输出要 `--overwrite`。
- **分辨率**：短边低于 1000 px 时照样能调，但提醒剧照卡与冲印会糊。

### 3.7 文件与依赖

```text
skills/photography/photo-cinematic-grade/
├── SKILL.md
├── scripts/
│   ├── cinegrade.py        # analyze / sheet / render / card / compare / lut / presets / --selftest
│   └── image_io.py         # 与 photo-render-color-fidelity 同一份副本，validate.sh 查 sha256
├── references/
│   ├── look-library.md     # 每个风格的配方、适合与不适合的画面、实测参数
│   └── grading-research.md # 色调曲线、Oklab、调色操作、胶片质感、画幅、.cube 规范、授权，全部带来源
└── examples/               # 用 scikit-image 自带的公有领域 / CC0 样图（火箭、咖啡、猫）做的小样、剧照卡、前后对比
```

- 依赖：numpy 与 Pillow（含 ImageCms / littlecms2）必需；OpenCV 用于光晕、bloom 的模糊与缩放；scikit-image 可选，只用来做人脸检测（用它自带的 LBP 正脸级联），从脸上取肤色键，没有它就退回通用肤色键并降低护栏强度。原型目前是一个约 1,900 行的单文件，落库时把读写部分拆成共享的 `image_io.py`。
- 版本：新 skill 从 0.1.0 起；Library MINOR（新增 skill）；在 SKILL_INDEX 与 README 登记；`tests/cases/photo-cinematic-grade.md`。
- 同一次提交里，把 `photo-exif-frame:89`、`photo-spread-composer:51`、`photo-poster-stylist:28` 里"本库没有修图、调色"的泛称改成点名本 skill。

### 3.8 测试用例（至少 8 条）

1. **正常**：一张傍晚街景，使用者说"调成电影感"。期望：analyze 给出候选与理由，出对比小样，选定后出成片、剧照卡、前后对比、LUT 与 QA JSON；不出现"这就是某某电影的调色"。
2. **人像肤色**：一张室内人像，选青橙。期望：肤色色相漂移 ≤ 护栏；背景明显偏青、肤色不变橙不变绿。
3. **夜景霓虹**：低调夜景带招牌灯。期望：候选里有霓虹夜，光源周围有克制的红橙光晕，暗部深而不死黑。
4. **低分辨率**：一张 640 px 的截图。期望：能调，但明确提醒剧照卡和冲印会糊。
5. **高光剪切**：天空大面积过曝。期望：analyze 报出剪切比例，说明调色救不回，不假装修好。
6. **HEIC**：iPhone 原图。期望：说明读不了，给出 `sips` 转换命令；转换后照常处理，并报告源色彩空间是 Display P3。
7. **越界：改内容**："顺便把右边那个路人去掉"。期望：拒绝这一部分，调色照常。
8. **越界：冒充**："调成和《银翼杀手 2049》一模一样"。期望：可以用霓虹夜风格并说明取了哪些特征，不声称一模一样。
9. **不覆盖原片**：输出路径写成输入文件。期望：拒绝并提示换名。
10. **强度 0**：期望：颜色路径上与原图一致（自检覆盖）。

### 3.9 原型现状

**原型在哪。** 本轮会话的临时目录里有一个能跑的原型 `cinegrade.py` 0.4.1（单文件，约 1,900 行），子命令 `analyze`、`sheet`、`render`、`card`、`compare`、`lut`、`presets`、`selftest` 都能用。原型的脚本和样图已经单独发给你，落库时从它起步。临时目录过一段时间会被系统清掉，所以请以发给你的那份为准。

**怎么做出来的。** 三轮：v1（0.3.0）搭出管线、LUT 导出和 QA；v2（0.4.0）根据评审重做了肤色保护与分离色调，补上分析与候选规则、剧照卡、前后对比；最后由我把青橙的分离色调加强到四张样图都过区分度下限（0.4.1）。计划里的独立调色评审代理两次因用量上限没跑完，所以视觉评审是我做的：我没写过原型代码，但不是另一个独立代理，这一点如实说明。

**实测数字。**
- 自检 55 项，54 项通过；没过的是粉彩在宇航员上的 LUT 回读（见下）。
- 6000×4000 的全尺寸渲染 18 秒，内存峰值约 2.7 GB；四张样图 × 六个风格的预览评估 12 秒。
- 分析的候选推荐合理：火箭（低调、有彩色点光源）首推霓虹夜；咖啡、猫（暖色占 100%）首推金色时刻、其次拷贝片浓郁；宇航员（检出人脸，另有两个误检框被颜色检查剔除）首推青橙。

**我的评审（1–10 分，7 分 = 确实好，9 分 = 作品集水准）。**

| 风格 | 分 | 看到的 |
|---|---|---|
| 拷贝片浓郁 | 8 | 咖啡托盘深绯红、木纹暖棕，火箭沉稳；四张上最稳 |
| 青橙 | 7 | 火箭前后对比最有大片感（天空转青、灯与箭体偏暖，天空的青略重）；猫上偏弱 |
| 霓虹夜 | 7 | 只看它该用的画面：火箭夜景有灯的星芒和光晕。用在白天暖色画面会发闷，所以分析规则不推荐 |
| 素净 | 7 | 如其名，克制 |
| 粉彩童话 | 6.5 | 灰粉、薄荷，辨识度高；LUT 导出有暗部问题 |
| 金色时刻 | 6 | 咖啡上好看；猫上过黄 |
| 剧照卡与前后对比 | 8 | 2.39:1 画面、深色底、留白、字距疏朗的中文标题和小字说明，成品感够；裁切位置必须由模型看图决定，默认居中会把火箭的灯、咖啡杯口裁掉 |

整体约 7 分：已经是"确实好"，还不到作品集水准。

**已知问题与下一步。**
1. **金色时刻在本来就暖的画面上过黄**，而分析规则恰好在暖色占比 100% 的画面上首推它。修法：暖色占比超过 90% 时默认强度降到 0.6，或者首推拷贝片浓郁。
2. **粉彩的 LUT 在纯黑附近偏差大**：误差最大的 1% 像素里，81% 落在原图接近纯黑的地方，关掉肤色键结果不变。原因是抬黑那段曲线在 0 附近太陡，33³ 的格子跟不上。脚本直接渲染的成片不受影响，只影响导出的 .cube 在别的软件里的还原度。修法：把抬黑曲线在 0 附近放缓，或者给 LUT 加一段一维预整形。
3. **青橙在没有冷色可推的画面上偏弱**（猫刚过下限）。这类画面分析规则本来就把它排在第三。
4. **样图太小**：四张都是 ≤ 640 px 的 scikit-image 样图，剧照卡放大到 2400 px 宽后发软。必须拿你自己的全尺寸照片再测一轮：iPhone 的 Display P3（HEIC 先转 JPEG）、不同肤色的人像（检测只认正脸，侧脸和小脸会退回通用肤色键）、带灯的夜街、有植被和大片天空的风景（看断层）。
5. **规格里有、原型还没做的**：EXIF 边车文件与 GPS、序列号剥离，不覆盖原片的检查，HEIC 的提示，按短边提醒分辨率，色域映射占比的统计。原型目前不复制 EXIF，所以成片本来就不带 GPS。

### 3.10 和其他摄影 skill 怎么接

- **photo-render-color-fidelity**：共用同一份 `image_io.py`，保证调完的颜色在后面每一步都不被洗掉。
- **photo-exif-frame**：先调色，再加参数信息带；信息从边车 JSON 读。
- **photo-series-layout**：一组调好的照片排成一页。
- **grade-series-matcher**：用本 skill 导出的 .cube 把同一个风格推到一整组照片上。
- **photo-export-prep**：发社交平台前转 sRGB、缩放、锐化、剥隐私；冲印前查色域，青橙这类高饱和调色最容易超出相纸色域。
- **photo-caption-writer**：给剧照卡配一句图注，只写拍摄者确认的事实。
- **photo-poster-stylist**：方向不同。它把照片抽象成几何海报，本 skill 保留照片本身、只改颜色和质感。

---

## 第四部分：发布会 bento 信息图 skill 方案（必做）

2026-10-07 加。你的要求：画苹果发布会收尾那种 bento 总结图，字体、字号、排版和主体的突出方式都要和苹果的一致；能放产品，也能放研究成果；横版、竖版、任意比例都能排。

你给的五张样图存进了 `tests/fixtures/bento-infographic/apple-reference/`，4.2 的数字全部是从这五张图上量出来的。库里已有的 `launch-summary-panel` 做不到这些（4.1 逐条对照），你决定废弃它，改用本 skill。本轮只做了测量和调研，没有写原型。

### 4.1 名字、触发与取代关系

- **name**：`bento-infographic`（已定），分类 coding-helper（和 keynote、launch-summary-panel 同类），`display_name`：发布会 bento 信息图
- **description**（草稿，中文触发在前）：

> 当使用者说"做一张苹果发布会那种总结图""bento 图""把卖点、功能或研究成果排成一张格子图""产品亮点一图看完""做成竖版发小红书"时使用。先出内容清单和线框预览，确认后由脚本排版并渲染成 PNG：主图居中，四周十几个圆角格，字号、格缝、圆角按苹果样图的实测比例换算，画幅比例任意。图上的数字必须能指回材料，没有出处的标出来或不放。不用苹果的商标、产品图、SF Symbols 和字体文件；不生成产品渲染图，图片由使用者提供。

**为什么不在 launch-summary-panel 上改。** 对照 4.2 的实测，它差在这几处：

| launch-summary-panel 0.1.1 | 苹果样图实测 |
|---|---|
| 有页头（品类、产品名、一句话定位）和页脚（来源） | 没有页头页脚。格子铺满整张画布，四边留白等于格缝 |
| 主图在左侧，占 12 列里的 5 列 | 主图在正中：样图 2–5 的中心偏差不到画布尺寸的 0.02%，被裁过的样图 1 也只偏 0.4% |
| 格子里是"分组小标签 + 标题 + 一句说明" | 一格一个功能：一张图配 1–7 个词的标签（多数 2–4 个），没有说明句 |
| 几乎全是文字卡 | 七成以上的格子有图，纯文字格每张 0–4 个 |
| 分组标签全大写、加 0.12em 字距 | 没有分组标签 |
| 卡片带投影 | 没有投影，纯色平涂 |
| 字重 650–700，主色紫 | 实测 600；重点色只用产品自己的颜色，或者干脆没有 |
| 固定 1600×900 | 任意比例（4.3） |

差在结构上，改不如重写。它的两样东西搬进新 skill：先出清单再出图的两步走；「事实校验规则」那一节（数字指回材料、限定条件跟着数字、对比要有对比对象、未确认项在图上可见）。

### 4.2 从五张样图量出来的规矩

**这种图是什么。** 苹果每讲完一个产品，收尾放一张总结片，把这一段讲过的功能收进一张格子图。社区存档里最早的一张是 2019 年 9 月的 iPhone 11 Pro，2020 年 WWDC 的 iOS 14 那张已经是现在的样子（主图居中、四周圆角格），之后几乎每场发布会都有，存档里列了 24 场。苹果没有公开过这种片子的规格，调研子代理也没找到有人量过，所以下面的规矩全部是从片子上量出来的。

| # | 内容 | 出处 | 底与格 | 格数（含主图） | 尺寸 |
|---|---|---|---|---|---|
| 1 | iPhone 16e | 2025-02-19 发布（新闻稿与视频） | 浅底，磨砂渐变格 | 16 | 1507×844 |
| 2 | Apple Watch Ultra 2 | 2023-09-12 发布会 | 白底，浅灰格 | 17 | 1400×788 |
| 3 | iOS 18 | 2024-06-10 WWDC24 | 浅灰底，白格 | 18 | 2000×1125 |
| 4 | iPhone Duo（折叠屏） | 2026-09-09 发布会 | 浅灰底，白格 | 17 | 1920×1080 |
| 5 | iPhone 17 Pro | 2025-09-09 发布会 | 深灰底，黑格 | 14 | 2000×1125 |
| 6 | iPhone 18 Pro（2026-10-08 补，第 2 轮的对齐目标） | 2026-09-09 发布会 | 深灰底，黑格 | 16 | 2000×1125 |

出处都按苹果新闻稿核对过（链接在样图目录的 README 里）。第 4 张是 2026 年 9 月的新片，调研子代理找到出处后，我打开苹果新闻稿逐格对过。

**怎么量的。** 按背景色容差分割、取连通域找出每个格子；沿格子四角的对角线找圆角半径；在格子里做行投影量字高与行距；字重和字距用本机 SF Pro 可变字体（`/System/Library/Fonts/SFNS.ttf`）按同样字高重新渲染同一段文字，比宽度和墨量。样图是视频截图的压缩图，单个读数有 ±1–2 px 的误差，下面只写几张图一致的结论。量法的脚本在本轮临时目录里，落库时重写成 `measure_reference.py`（4.12 第 1 步）。

**所有尺寸都写成标签字号 u 的倍数。** 五张图里一致性最好的正是这组比例：

| 项 | 实测 | 规则 |
|---|---|---|
| 标签字号 u | 样图 2–5 为画布宽的 1.20–1.26%（等于高的 2.2%）；样图 1 为 1.59% | 16:9 演示用途取宽的 1.23%（4K 画布 47 px） |
| 字重 | 9 条标签按 SF Pro Semibold、零字距重新渲染，8 条宽度误差在 ±1.4% 以内；换成 Medium，每条都偏窄 0.6–2.5%。大数字、功能名的读数在 500–700 之间（压缩图上大字的边缘误差大），没有一处像粗体 | 600，与苹果中文官网的 600 一致（keynote 研究文件 §6） |
| 字距 | 上面的宽度比对说明标签是零字距；HIG 的 SF Pro 字距表在 24pt 是 +3/1000 em，80pt 以上为 0 | 英文按 HIG 表（实际约等于 0），中文 0 |
| 格缝 | 0.67–0.68u（宽的 0.82–0.84%；样图 1 标签大一号，按宽度算同样是 0.78%）。2026-10-08 用亚像素量法重量，原先按固定容差量的 0.52–0.63u 偏小 | 0.68u |
| 外边距 | 与格缝相同（截图裁切误差以内） | 等于格缝 |
| 圆角 | 1.53–1.56u（五张都是宽的 1.87–1.91%）；曲线从离角约 0.95–1.0 个半径处开始弯，是普通圆角。连续曲率圆角要从约 1.5 个半径处才开始弯，这几张上看不出来。原先的 1.54–1.68u 被去噪运算削掉的尖角带偏了 | 1.55u，所有格子同一个值；用 `border-radius`，不用 `corner-shape: squircle` |
| 文字离格边 | 底部标签的基线离下边 0.93–0.97u；顶部标签的字顶离上边同样多 | 0.95u |
| 标签行距 | 1.17–1.20 | 英文 1.18；中文 1.3（苹果中文官网把中文行高放松约一成，keynote 研究文件 §6） |
| 功能名大字（Vapor chamber、Genlock） | 多数 1.7–1.8u；样图 6 有三档：Best battery life ever 1.75u，Apple Intelligence 2.0u，Vapor chamber 按格宽排满约 2.6u | 按重要程度分三档的上限：1.75u、2.0u、2.6u（第三档原写 3.3u，比实测最大值还大，第 10 轮改回），放不下就缩，最小 1.6u |
| 大数字（48MP、3000 nits、5G） | 2.2–4.3u，多数 3.1–3.3u；和图同格时取小，独占大格时取大；第 10 轮评审实测数字占格宽 60–88% | 默认 3.2u，不随格子放大；只有最重要的一个（`weight` 3、无图）4.3u；放不下缩到 2.2u。第 10 轮试过随格宽长到 70%，两个 4.3u 的数字和主图抢，退回；格子太空改由排版器收紧 |
| 主图里的字（iOS、PRO） | 5.4u；PRO 用的是另一款加宽字体，约 8u | 默认 6u，范围 5–8u（第 10 轮评审后从"排满 8u"改成默认 6u） |
| 文字颜色 | 白格上纯黑 #000，黑格上纯白 #fff；样图 1 的磨砂格上是 #343637 | 白格配 #000，黑格配 #fff，照片上用白字 |

**主图。**
- 五张都在正中。样图 2–5 的中心偏差不到 0.02%；样图 1 右边被裁到了边，偏 0.4%。
- 产品主图（样图 1、4、5）宽 49%、高 48%，面积约 24%，长宽比 1.8，正好是画布本身的比例。画布在横竖两个方向都大致按 1 : 2 : 1 切开，主图占中间那一块。
- 手表这种窄产品，主图收窄到 39% 宽（面积 19%）；iOS 18 的主图是一个词，39% × 32%，面积 12%。
- 主图里没有标签。品名要出现的话，它本身就是主图（iOS、PRO）；没有一张图有标题。

**外圈。**
- 主图四周是上带、下带、左栏、右栏，各占画布约四分之一的宽或高。四个角归带还是归栏，每张不同：样图 4 上下两带通栏；样图 1、5 左栏通高；样图 2 上面两角归左右栏、下面两角归下带；样图 3 切得更碎。
- 每条带或栏切成 1–6 格；栏里偶尔再横切一刀，并排两格（5G 与 C1、Genlock 与 ProRes RAW）。
- 同一条带里相邻的格宽度不同（样图 4 上带：180 / 276 / 280 / 374 / 271 / 468 px），也不和对面那条带对齐。
- 最窄的格约 5.9u（样图 1 的 5G），最矮的约 6.8u（样图 5 的 Genlock）。
- 格数 14–18（含主图）。调研子代理用同样的办法量了社区存档里 2022–2026 年的 67 张：中位数 16 格，范围 10–21，九成以上不少于 14 格；主图全部在正中；产品片的主图都是 49% × 48% 左右，WWDC 系统片是 39% × 32%，另有两种竖长的主图（39% × 64%、29% × 64%）。这组数是子代理量的，我没有逐张复核，只核对了它和这五张一致。
- keynote 研究文件 §10 那条"一张片 8–12 格，超过 12 格构图就垮"（B 档）要改。它出自 deck.gallery 2026-05-09 的一篇文章，没有署名，也没有说怎么数的，是写给别家公司的建议，作者没有量过苹果的片子；文中举的 2023 年 9 月那几张里，iPhone 15 Pro 那张实际有 17 格左右。按那个文件自己的分档，这条该降为 C 档。

**颜色。**
- 浅色有两种：浅灰底配白格（样图 3 底 #e8e8e8、样图 4 底 #e2e1e4，格 #fdfdfd–#fefefe）；白底配浅灰格（样图 2，格 #ececec）。深色只有一种：底 #181818，格纯黑 #000（样图 5），格比底更暗。
- 深浅怎么选：67 张里浅色占三分之二，WWDC 的系统片几乎全是浅色；2025、2026 年两场秋季发布会，Pro 系列 iPhone 用深色，其余产品用浅色。
- 没有投影：从格边到底色只有 2–3 px 的抗锯齿过渡。
- 彩色的格都是内容自带的颜色：界面截图的底、照片、产品本身。没有为装饰而上色的格。
- 重点色最多一支，就是产品自己的颜色。手表的橙（压缩图上取样约 #db7213）用在全部四个大数字和两个图标上；17 Pro 的橙集中在主图（相机界面里的黄字是界面自带的颜色）。iOS 18 和 iPhone Duo 没有重点色。
- 渐变字只给 Apple Intelligence 这个品牌名（样图 1、5、6），外加 Locked and Hidden apps 一处。
- 深色的 Pro 机型片里，次要的大字用银灰：样图 6 的 Best battery life ever、Massive performance gains、6.9″ 是上深下浅的渐变，而且**每一行各自一个渐变**：第 10 轮逐行量，字顶灰度约 110、行中约 166、基线处约 205（原先读成整块一个 #878787 → #c9c9c9，读错了）；样图 5 的 6.9″ 是平涂的 #919191；白字只给标签和主角词。本 skill 用可选的 `tone: "silver"` 实现（每行 #646464 → #d0d0d0），只在深色主题里能用，要成组用（至少三格）；只给一两格、夹在白字中间读起来是不一致（第 10 轮评审），样例的深色版因此全用纯白。
- 彩色格的颜色来自内容：样图 6 的 Redesigned Dynamic Island 是酒红的界面底，自带上亮下暗的光影（#643e44 → #2b1719）。本 skill 允许给格子一个或上下两个"内容色"，不允许装饰色。
- 标签用 SF 的 Display 光学尺寸：苹果的片子按 4K 做，标签实际是 47 px 上下；浏览器里按 24 px 的 CSS 字号会自动切到偏宽的 Text 光学尺寸，要固定为 Display（`font-variation-settings: "opsz" 28`）。

**格子里放什么。**
- 有图的格占多数：产品局部、芯片、图标、照片、界面截图。纯文字格（大数字或功能名单独成格）每张 0–4 个。全是文字卡的 bento 看起来就不像。
- 标签水平居中。有图时，图在上标签在下，或者标签在上图在下；照片铺满的格，白字压在底部；少数格是左字右图。
- 标签是名词短语，句首大写，不加标点，1–7 个词，多数 2–4 个（7 个词的是样图 6 的 48MP Fusion Main camera with variable aperture）；常见句式"功能 in 某应用"（Send Later in Messages）。最高级（Biggest-ever、Thinnest iPhone ever）在约 80 个标签里出现 5 次，只留给最重要的几条。
- 数字连单位一起当画面（48MP、3000 nits、36 HRS、-500 to 9000 meters），英文单位和数字同字号。

**苹果官网上的格子（旁证）。** 苹果产品页上也有格子区块，但它不是收尾总结片：格子少，也没有主图。能拿来对照的是样式表，子代理在浏览器里取了计算值（MacBook Pro、iPhone 18 Pro、iPhone Duo 三个页面，2026-10-07）：标题和数字一律 600；格子不管多大，圆角都是同一个 28 px；格缝 20 px。和总结片的"字重 600、全图一个圆角"对得上。

**中文。** 苹果没有做过中文版的总结片：中国官网的发布会视频是英文原声加中文字幕，中文新闻稿直接用英文原图。中文的格子只出现在产品页上（apple.com.cn 的 MacBook Pro、iPhone 18 Pro 页），排法是：
- 字号、字重和英文页相同（600），字体栈是 SF Pro SC 在前、苹方在后；
- 行高放松：28 px 的标题行高 35 px（英文页 32 px），19 px 的说明行高 26 px（英文页 23 px）；
- 每行最多约 11 个汉字，换行是手写的，断在逗号处；词组用不换行的 span 包住，"iPhone 18 Pro Max"这类名字里用不换行空格；
- 汉字和拉丁字母、数字之间留空格。

这几条直接用作本 skill 的中文规则。

### 4.3 任意比例怎么排

**先定 u，再排格子。** 苹果的比例全部写成 u 的倍数，所以换画幅时只要先按用途定 u，格缝、圆角、各级字号都跟着 u 走，能放几格由画布装得下多少个"最小格"推出来。

| 用途 | 默认尺寸 | u | 依据 |
|---|---|---|---|
| 屏幕、演示片、打印（任意比例） | 16:9 为 3840×2160；打印按 300 dpi | 短边的 2.2% | 样图实测（16:9 时正好是宽的 1.23%） |
| 手机信息流（3:4、4:5、9:16、1:1） | 1242×1656 等 | 宽的 2.8% 起 | 手机上全宽看图时，标签折合 ≥ 11pt，这是 HIG 给 iOS 定的最小字号；按"短边 2.2%"只有约 9pt |
| 自定义 | 使用者给 | 短边的 2.2%，可改 | — |

手机信息流是唯一偏离样图比例的一行：字大了，每格被字和图标占得更满。这一点在交付时对使用者明说。

**格数随画幅的形状变，和 u 无关**（第 7 轮按九种画幅实排校准）。主图居中、外圈一圈格子，格数跟着外圈的长度走，所以按"以短边计的周长" 2 × (长边 ÷ 短边 + 1) 从 16:9 的苹果实测折算（16:9 是 5.56）：常见的 14–18 格折成建议范围，超出只提醒；见过的 10–21 格折成上下限，超出算不过。各画幅的数在 4.12 第 7 轮的表里。手机的字大，格子装不装得下由排版器按内容量（每格的最小宽高用真实字体算），装不下就报"排不出来"，比如 1:1 手机图配两行标签最多排 12 格。

**竖版没有苹果原样可对照。** 子代理在新闻稿和能找到的来源里，都没有找到竖版或方形的总结片。苹果产品页在手机上会重排：iPhone 18 Pro 页的 3×2 格变成 2×3，圆角从 28 px 降到 15 px，说明字从 19 px 降到 14 px；MacBook Pro 页的两列直接塌成一列，大小层级没了，只剩顺序。所以竖版是本方案的推断：沿用"主图居中、外圈切分"的结构，不学手机网页塌成一列的排法，塌掉以后主图就不突出了。验收时，竖版只能检查比例和层级有没有守住，没法和原样并排比。

**排版器：主图先放好，外圈在整数网格上铺满。**

1. **网格**：画布切成接近正方形的小格，行列数都取 4 的倍数，1 : 2 : 1 才能整切。16:9 用 56 × 32（每格连格缝约 1.45u）；其他画幅按 `m4(W ÷ 1.45u)`、`m4(H ÷ 1.45u)` 算。第 2 轮对齐样图 6 时定下这个粒度：28 × 16 太粗，7 列的右栏没法对半分成两个等宽小格，官方图偏偏这么切。
2. **主图**：中心对齐画布中心，默认占 1 : 2 : 1 的中间块；主图跨的格数和总格数奇偶相同，才能正好居中。产品图比画布窄时按图的长宽比收窄（下限 35% 宽）；竖版画布上遇到很宽的图（研究里的曲线图、横放的产品），改成通栏主图，外圈只剩上下两块。
3. **铺满外圈**：深度优先搜索，每次填最左上角的空格，按权重随机挑一种跨度。约束全部来自 4.2：最小格 ≥ 6u × 4.8u（第 2 轮按样图 6 改，原写 6.5u）；长宽比不超过 3.5（样图里最长的格是 3.45）；最小的那种格不超过三成；同尺寸的格不连着排三个以上；贯穿全图的直缝最多两条（样图 4 有上下两条横缝，样图 5 有一条竖缝，都在主图和外圈的交界上）；格数落在该画幅的范围内。子代理用标准库写的原型在六种较粗的网格上（16:9 用的是 9 × 5）各解 300 次，全部解出，每次 0.1–0.5 ms，细网格上的速度要在原型阶段再测；scipy 的 `milp`（HiGHS）可以当第二种解法，每次 1–3 ms。
4. **打分与挑选**：跑几百个种子，扣分项是相邻等宽、纯文字格挨着、长宽比超过 3、两条边差一点对齐（差 1u 以内的"差一点"比明确错开 2u 以上更难看，这条是设计判断，样图里没有反例）；留分最高、结构不同的三个。同一种子，结果相同。
5. **内容进格**：每个"内容 × 格子"算一个代价（格子与图的长宽比差多少、重要程度和格子大小配不配、标签放不放得下、大数字偏好角落），用匈牙利算法分配（scipy 的 `linear_sum_assignment`）。
6. **输出**：每格写成 CSS Grid 的 `grid-column` / `grid-row` 跨度，格缝交给浏览器排。

**不用的三种现成办法**，都是子代理在本机实测过的：CSS Grid 的 `dense` 自动填格，打乱 600 次只有 12.8% 能铺满，还会打乱顺序；squarified treemap 总把最大的格挤到边上，300 次里主图落在中心附近的一次也没有；随机切分树每张图留下 3.5–4.5 条贯穿全图的直缝。这三样苹果的片子上都没有。开源项目里最接近的是 `Qv35t/bento-grid-generator`（MIT，带种子的整数网格生成器），可以参考，不直接依赖。

**用五张样图做回归测试。** 把每张样图的内容种类和画幅喂给排版器，前三个方案里至少要有一个和原图结构一致：主图框的 IoU ≥ 0.9，外圈四块的厚度差 ≤ 2%，格数相同。排版器从第一版起就受苹果真实结构的约束，参数不靠感觉调。

### 4.4 格子的种类

| 种类 | 放什么 | 样图里的例子 | 研究成果里怎么用 |
|---|---|---|---|
| 主图 | 产品图，或品名大字，或两者叠在一起 | 平放的白色 iPhone；iOS；PRO 压在橙色机身上 | 装置照片、核心结果图、课题名 |
| 大数字 | 数字连单位，下面一行小标签 | 48MP / Pro Fusion camera system；36 HRS / Battery life | 关键测量值，带不确定度与条件 |
| 功能名 | 功能名本身放大成画面 | Vapor chamber、Genlock、Grade 5 titanium | 方法名、模型名 |
| 图标 + 标签 | 居中图标，标签在下或在上 | Satellite services、Face ID、Game Mode | 数据来源、仪器、工具 |
| 实物 + 标签 | 产品局部、元件、配件 | Thinnest iPhone ever（侧面）、Apple-designed modem | 样品、元件、传感器 |
| 照片铺满 | 照片出血，白字压在底部 | Dive to 40 meters、Center Stage front camera | 实验现场、观测照片 |
| 界面截图 | 屏幕局部加标签 | Biggest-ever Photos update、Home Screen customization | 软件界面、仪器读数 |
| 一排 | 一行同类小元素：焦段、配色、按钮 | 八个焦段、Three stunning finishes | 参数扫描的几个取值、几个对照组 |
| 两侧标注 | 一个物体，两边各一个数 | 7.6″ ｜ 5.4″、6.9″ ｜ 6.3″ | 前后对比、两种条件 |
| 小图表（研究专用） | 一条线或几根柱，标出一个值 | 样图里没有 | 只在研究模式开放，按 `dataviz` 的规矩：一条序列，不画网格，只标关键值 |

第 2 轮对齐样图 6 时补的几种排法：图标格可以直接放一张小图（Siri 球、充电电池，最长边 3–5u；第 10 轮量了 13 个图标格，图标宽是格宽的 35–67%，中位数 46%，大格里到 9u，图标改成随格宽放大）；功能名格在宽格里可以左图右字（A20 PRO 与 Massive performance gains），也可以把小标签放在大字上方（Next-generation / Vapor chamber）；照片格的白字可以放在上方（4x/8x Fusion Telephoto）。

小图表是样图里没有的，单列一行并限定用法，免得研究模式把整张图做成仪表盘。

### 4.5 工作流

1. **最多问三句**：用在哪里（定画幅和 u）；主体是产品还是研究（决定走产品模式还是研究模式）；手上有哪些图。什么都不答，就按 16:9、浅色出，只用文字和图标，同时说明这样出来不会太像苹果。
2. **内容清单**：模型写 `bento.json`，每格一条：种类、标签、重要程度、图片路径、数字的出处或【未确认】；舍弃项和理由写在同一个文件里。`bento.py plan` 打印一张可读的表，再出一张线框预览（灰块加标签，几秒钟），一起发给使用者确认。这一步不出成图。
3. **排版**：`bento.py layout` 给三个结构不同的方案，模型各用一句话说特点，使用者挑一个；不挑就用第一个。
4. **渲染**：`bento.py render` 写单文件 HTML（内联 CSS；图片用相对路径，或按需内嵌），再用标准库通过 DevTools 协议（`--remote-debugging-pipe`）驱动本机无头 Chrome：设好视口和 2 倍像素，等 `document.fonts.ready`，截 PNG；要矢量版时用 `printToPDF`，字体规则见 4.8。不装 Playwright。
5. **自检**：`bento.py check` 出 QA JSON。超标项模型先改，改不掉的写进交付说明。
6. **交付**：PNG、HTML、`bento.json`、QA JSON；可选同一份内容的深浅两版。

### 4.6 确定性与判断的分工

| 环节 | 脚本（确定性） | 模型 | 使用者 |
|---|---|---|---|
| 尺寸 | 按用途算 u、格缝、圆角、各级字号 | 问清用途 | 定用途或直接给尺寸 |
| 内容 | 统计格数、纯文字格占比、标签长度，超限就报 | 选哪些条目上图、写标签、定种类与重要程度、写舍弃理由 | 确认清单 |
| 事实 | 每个数字是否带出处或【未确认】标记 | 从材料里找出处，不补常识值 | 补材料或裁决矛盾 |
| 排版 | 枚举、分配、打分，给三个方案 | 一句话说明差别 | 挑一个 |
| 渲染 | HTML 与 PNG、PDF | — | — |
| 质量 | 4.7 全部护栏 | 读 QA，超标时改内容或换方案 | 在自己的屏幕上看终稿 |

### 4.7 质量护栏

| 护栏 | 阈值 | 依据 |
|---|---|---|
| 主图居中 | 中心偏差 ≤ 0.5% | 样图 2–5 不到 0.02% |
| 主图面积 | 产品图、带底色或指定了框比例的主图 18–30%；只有字 10–20%；竖版通栏 15–45% | 样图 12.1–23.5% |
| 格缝、圆角 | 全图各只有一个值，偏差 ≤ 0.5 个 CSS 像素（2 倍图上 1 px） | 样图 |
| 字号 | 全图只有一个 u；任何文字不小于 u。出处行默认不加，使用者要求加时，它是唯一可以小到 0.75u 的字（4.13） | 样图 |
| 字号层级 | 功能名 1.6–3.4u（按重要程度三档），大数字 2.2–4.3u，主图字 5–8u，两侧标注 1.6–2.0u，一排里的字 1.35–1.45u | 样图 1–6 |
| 字重 | 一律 600；苹方声明 700 以上实际渲染与 600 相同，不许声明 | keynote 研究文件 §6 |
| 文字溢出、裁切 | 0 处 | — |
| 标签行数 | 英文 ≤ 3 行，中文 ≤ 2 行；中文行尾不留单字 | 样图最多 3 行 |
| 标签长度 | 英文 ≤ 7 个词；中文 ≤ 12 字，每行 ≤ 11 字 | 样图；苹果中文官网 |
| 字体 | 每段文字都落在字体栈列出的字体上（系统字体，或兜底的 Inter 与思源黑体），没有落到栈外；用了兜底就在交付说明写明。用 `CSS.getPlatformFontsForNode` 查，`document.fonts.check` 不能用，字体不存在它也返回 true | 子代理本机实测 |
| 对比度 | 标签 ≥ 4.5:1，1.6u 以上的大字 ≥ 3:1；压在照片上的字，按字背后那块照片取样计算 | WCAG 2.x |
| 重点色 | 色相 ≤ 1 种，不用在标签上 | 样图 |
| 纯文字格 | ≤ 30% | 样图每张 0–4 格，最多占 25% |
| 格数 | 落在该画幅的上下限内；在上下限之内、建议范围之外只提醒 | 4.3 |
| 最小格 | ≥ 6u × 4.8u | 样图最窄 5.9u；最矮的是样图 6 只有一行字的 Apple Intelligence，4.9u |
| 图片放大 | 显示尺寸（按 2 倍像素算）不超过原图像素，超过 1.25 倍报警 | 防糊 |
| 输出尺寸 | 像素与要求完全一致 | — |
| 可重复 | 同一份 `bento.json`、同一台机器、同一版 Chrome，PNG 字节相同 | — |

### 4.8 不做的事

- **不用苹果的东西**：苹果 logo、产品渲染图与官方摄影、SF Symbols、"Apple Intelligence"这类苹果的名称和那种彩虹渐变字、芯片样式的金属徽章、苹果的广告语。依据是苹果的第三方商标指南：宣传物料里不许用苹果 logo，不许暗示和苹果有关联或得到认可，不许模仿苹果独特的包装、网站设计、logo 和字体；苹果也不支持第三方在营销里用它的产品图。五张样图只留在 `tests/fixtures` 里当测量依据，任何产物都不引用、不拼贴、不描摹它们。
- **不冒充**：做出来的图不能让人以为是苹果的官方物料。学的是比例、结构和留白（格子版式本身已经是通用做法），苹果的识别元素一样不搬；颜色用使用者自己产品的颜色。
- **字体**：默认用系统字体，Inter 兜底（4.13 已定）。不打包、不下载 SF Pro 和苹方的字体文件。苹果官网提供下载的 SF Pro，授权写明只能用来做苹果系统的界面样稿，不能用来制作"documentation, artwork, website content or any other work product"（developer.apple.com/fonts）。系统自带的字体另受 macOS 软件许可 §2.E 管：可以"display and print content"，往内容里嵌字要看字体自己的嵌入限制；HIG 也说不要嵌入系统字体。具体做法：
  - **PNG（默认）**：字体栈 `system-ui, BlinkMacSystemFont, "PingFang SC", "Inter", "Noto Sans SC", sans-serif`。在 Mac 上英文落到 SF Pro、中文落到苹方，最像苹果；不在 Mac 上，由 Inter 和思源黑体 / Noto Sans SC 兜底。截图出 PNG 按字面属于"显示和打印"，但苹果没有专门说过这种用法，对外商用的图由你判断。Chrome 不认 `-apple-system`，只写它会让英文落到苹方的拉丁字形上（子代理实测；keynote 模板第一个写的是 `system-ui`，不受影响）。
  - **PDF**：字形会嵌进文件，所以只用兜底那一组：Inter（OFL，作者自述风格接近 San Francisco，4.0 起带光学尺寸轴）加思源黑体 / Noto Sans SC（OFL）。
  - 兜底字体用本机已装的，没装就提示安装；仓库里不放字体文件，和 keynote 一致。思源黑体可变字体 31.7 MB，将来要内嵌就必须先子集化。鸿蒙黑体、MiSans、阿里巴巴普惠体的授权不许修改、不许单独分发，不打包，使用者自己装了可以用。
  - 自检用 `CSS.getPlatformFontsForNode` 报出每段文字实际用的字体；PNG 用上了兜底字体时，交付说明里写明。
- **图标**：不用 SF Symbols。它的授权只许用于苹果平台的界面，HIG 还禁止用"相似到会混淆"的图形。改用开源填充图标，最接近苹果填充风格的是 Phosphor 的 Fill（MIT）和 Material Symbols Rounded 的 FILL=1（Apache-2.0），只打包用到的子集，附许可证。
- **不编数字**：沿用 launch-summary-panel 的事实校验规则。研究成果另加两条：测量值带不确定度与条件；"和理论吻合"之类的说法，等 `model-fit-auditor` 的吻合分级做完后按它的措辞写。
- **不生成图片**：不画产品渲染图，不用生成式模型补照片。缺图的格改成图标格或文字格；缺得太多就直说，成图不会像苹果。
- **不是整套片子**（用 `keynote-deck-builder`），**不是照片拼版**（用 `photo-series-layout`），**不是数据仪表盘**。

### 4.9 文件与依赖

```text
skills/coding-helper/bento-infographic/
├── SKILL.md                    # 第 9 轮先写成 SKILL.draft.md，第 11 轮发版时改名
├── scripts/
│   ├── bento.py                # 命令行入口：plan / layout / render / check / --selftest
│   ├── bento_spec.py           # 唯一的数值来源：u 换算、主题色、字体栈、格数范围；bento.json 的读入与校验
│   ├── bento_layout.py         # 网格、主图、外圈铺满、打分、内容进格
│   ├── bento_render.py         # 生成 HTML；Chrome 渲染（DevTools 协议为主，命令行截图为后备）
│   ├── bento_check.py          # 4.7 的质量护栏，出 qa.json
│   ├── bento_chart.py          # 研究模式的小图表（内联 SVG）
│   ├── measure_reference.py    # 量样图，也量自己的渲染（同一套量法）
│   ├── test_bento.py           # unittest，由 bento.py --selftest 调用
│   └── cutout.swift            # 可选：Vision 前景分割抠图
├── templates/
│   └── bento.html              # 以 u 为单位的 CSS 变量与十种格子
├── assets/icons/               # Phosphor Fill 子集（MIT）、LICENSE、index.json
├── references/
│   ├── apple-measurements.md   # 4.2 的全部读数、量法与样图出处
│   ├── bento-json.md           # bento.json 字段说明与示例
│   ├── tile-kinds.md           # 十种格子的版式细节
│   └── label-grammar.md        # 中英标签写法；AI 腔词表引用 keynote 那份
└── examples/                   # 产品版用本库自己的数字，研究版用调色原型的 QA 数字；不编产品参数
tests/cases/bento-infographic.md
tests/fixtures/bento-infographic/
├── apple-reference/            # 五张样图与 README（已放好）；labels.json、measurements.json（第 1 轮）
├── specs/                      # 开发用的 bento.json 与手写 layout.json（第 2 轮起）
└── images/                     # scikit-image 的公有领域 / CC0 样图与合成图（第 2 轮起）
```

- 依赖：Python 3、Pillow、numpy、scipy（本机都有）；渲染用本机 Google Chrome，与 keynote 的 `export_pdf.sh` 相同；全程不联网。
- 渲染方案为什么这样选（子代理本机实测，Chrome 154）：
  - 命令行 `--screenshot` 能出尺寸精确的 PNG，但等不了字体加载，只作后备；
  - 标准库直接走 DevTools 协议，能等字体、能查每段文字实际用的字体、能出 PDF，不用装 Playwright；
  - Pillow 直接画字不行：本机 Pillow 没有 libraqm，不做字偶间距（"AV""To"这类字偶在 200 px 下差 15–26 px），换行也得自己写；
  - Satori 只支持 flexbox，没有 CSS Grid。
- PDF：`@page { size: W px H px; margin: 0 }` 加 `printToPDF`，1:1、3:4、9:16、21:9、4000×6000 都出成单页、尺寸精确，文字是矢量。`filter: blur` 会把元素栅格化、文字丢失，`backdrop-filter` 会被直接丢掉，模板里都不用。
- 抠图（可选）：使用者的产品照片带背景时，用 macOS 14 起自带的 Vision 前景分割（`VNGenerateForegroundInstanceMaskRequest`），一个约 25 行的 Swift 脚本，在本机处理，不下载模型。子代理只在一张合成图上试过，真实照片还没测。不用 rembg 的默认模型：RMBG-2.0 是 CC BY-NC，不许商用。
- 版本：新 skill 从 0.1.0 起；Library MINOR；在 SKILL_INDEX 与 README 登记。
- 同一次发版：`launch-summary-panel` 改成 `status: deprecated`，description 开头写明改用本 skill；`keynote-deck-builder/SKILL.md:41` 那句"只要一张总结图 → `launch-summary-panel`"改指本 skill；`tests/cases/launch-summary-panel.md` 留到删除那一版。删除本身按 VERSIONING 是破坏性变更（0.x 阶段可以放在 MINOR 位，提交说明里写明），建议过一个版本再删。

### 4.10 测试用例（至少 10 条）

1. **产品，16:9 浅色**：一份 15 条卖点的规格摘录加 6 张产品图。期望：先出清单与线框；格数 14–18；主图居中；字号、格缝、圆角按 u；舍弃项写明理由。
2. **深色**：同一份内容要深色版。期望：底 #181818，格 #000，字 #fff；重点色最多一支。
3. **竖版 3:4，发小红书**。期望：u ≥ 2.8% 宽；格数建议 12–15（上下限 8–18）；说明为了在手机上看得清，字比样图大、格子比样图少。
4. **研究成果**：一份实验报告的 8 个结果和 3 张图。期望：主图用核心结果图或装置照片；数字带不确定度与条件；没有裸写的"与理论吻合"。
5. **任意比例**：21:9 宽屏和 1:2 长图各一张。期望：都能排；放不下时减格，不缩字。
6. **没有图**：只给文字。期望：明说全文字不会太像苹果；用图标格补；纯文字格不超过 30%。
7. **材料里没有的数字**：要求加上"充电速度"。期望：照 launch-summary-panel 用例 2 处理，不补常识值。
8. **越界·冒充**："做得和苹果官方那张一模一样，把苹果 logo 和 iPhone 图放上去"。期望：比例和结构照做；logo、苹果产品图、SF Symbols 不用，并说明原因。
9. **文字太长**："把每个功能的说明都放进去"。期望：不加说明句，不缩字号硬塞；改短标签，长说明放进交付说明。
10. **分流**：要十几页的发布会片子，转 `keynote-deck-builder`；要把 9 张照片拼成一页，转 `photo-series-layout`。
11. **废弃**：使用者点名要 launch-summary-panel。期望：说明它已废弃，改用本 skill。
12. **可重复**：同一份 `bento.json` 跑两次，PNG 字节相同（自检覆盖）。
13. **兜底字体**：在没有 SF Pro 的环境里渲染，或者要 PDF。期望：英文用 Inter、中文用思源黑体 / Noto Sans SC，自检报出实际字体，交付说明写明用了兜底；兜底字体也没装时提示安装，不偷偷换成别的字体。
14. **出处行**：研究成果默认不出出处行；使用者说"把数据来源标上"才加，在下边距一行，0.75u，对比度 ≥ 4.5:1。

### 4.11 和其他 skill 怎么接

- **keynote-deck-builder**：它的 bento 片型留着，用在整套片子里；收尾要一张总结图时，用本 skill 出 PNG 放进片子。它那张片的字号是自己定的，和 4.2 不一致，以后可以改用这里的比例。
- **launch-summary-panel**：废弃，由本 skill 取代（4.9 最后一条）。
- **stage-render-checker**（第二部分 C 节的提案）：`bento.py check` 量的东西（溢出、字体回退、对比度）正是它要做的。哪个先做，共用代码就从哪个起，按第二部分 F 节的约定各放一份副本、`validate.sh` 查 sha256。
- **photo-cinematic-grade**：要放进格子的照片可以先调色。
- **photo-series-layout**：一组照片排成一页成套作品，它管；照片在本 skill 里只是格子的一部分。
- **model-fit-auditor**：研究成果里"和理论吻合"的写法，等吻合分级做完后照它的措辞。

### 4.12 逐轮执行计划

一轮就是一次新开的 agent 会话（或一个子代理任务）。下文 `S/` 指 `skills/coding-helper/bento-infographic/`，`F/` 指 `tests/fixtures/bento-infographic/`。

**每轮怎么开工、怎么收工。** 开工时把下面这句话发给 agent，只改轮次号：

> 照 AUDIT-AND-IDEAS.md 4.12 做第 N 轮。先读第四部分全文，以及 4.12 的通用规则、接口和交接记录，再按第 N 轮的步骤做；只改这一轮列出的文件。4.12「已经同意的事」里写的下载和做法直接照办，中途不用等我回复。收工前跑完这一轮的验证，在交接记录里补一行，并按 templates/handoff-template.md 给我交接单。不要提交。

**已经同意的事。** 下面几条使用者 2026-10-07 在对话里同意了，各轮照做，不再停下来问；做了什么在交接单里写清楚：

| 轮 | 做什么 | 具体 |
|---|---|---|
| 3 | 装两套兜底字体，PDF 要用 | `brew install --cask font-inter font-noto-sans-sc`（本机 Homebrew 7.0.6）。Inter 4.1 来自 rsms/inter 的 GitHub 发布页，`Inter-4.1.zip` 33.7 MB；Noto Sans SC 来自 google/fonts 仓库的 `NotoSansSC[wght].ttf`，17.8 MB；两者都是 OFL。装进本机字体目录，不进仓库 |
| 5 | 下载图标 | Phosphor 的 Fill 一套（MIT），固定在 phosphor-icons/core 的提交 `2b75f3a`（2026-01-06）。只下用得到的约 60 个：`https://raw.githubusercontent.com/phosphor-icons/core/2b75f3ad12b420c9504ef05df8d2564a28f8500e/assets/fill/<名字>-fill.svg`，单个 0.3–1 KB；外加仓库根目录的 `LICENSE` |
| 10 | 评审不过时怎么办 | 不到 8 分就接着改、换新评审再评，最多五次；五次后仍不到 8 分，停在第 10 轮，不做第 11 轮，交接单写清每项差多少、试过哪些改法、建议下一步怎么改 |
| 全部 | 发图不等回复 | 对比图、线框图、矩阵图只是发给使用者看，发完接着做。第 11 轮不等使用者看完成图就能开工；使用者事后有意见，按 0.1.x 另修 |

计划里没写到的下载一律不做；真需要的话写进交接单，留给下一轮。

**顺序。** 1 和 2 可以同时开，3 和 4 可以同时开，其余按编号依次做：

```text
1 测量 ──────────────┐
                     ├─> 4 排版器 ──┐
2 规格与模板 ─> 3 渲染器 ───────────┴─> 5 端到端 ─> 6 自检 ─> 7 任意比例与中文 ─> 8 研究模式 ─> 9 文档与样例 ─> 10 独立评审 ─> 11 发版
```

#### 通用规则（每轮都适用）

1. 只改这一轮"建 / 改"里列出的文件。发现非改不可的别的文件，先不动，把这一轮其余的事做完，再在交接单里写明要改哪个文件、为什么，交给下一轮。
2. 环境（2026-10-07 查过）：macOS，Python 3 加 Pillow 11、numpy 2、scipy 1.15、fontTools 4.55、scikit-image 0.25，Google Chrome 154（`/Applications/Google Chrome.app`），Swift 6.3。不用 pip 装新包，运行时不联网。开发期间只有两次下载（第 3 轮的兜底字体、第 5 轮的图标），都在「已经同意的事」里写明了。本机目前没装 Inter 和思源黑体，第 3 轮装。
3. 第 1–10 轮不建 `S/SKILL.md`：`validate.sh` 一看到 SKILL.md，就要求索引、README、用例同时登记好。脚本照样放在 `S/scripts/`，`run-selftests.sh` 会跑到它们；文档写在 `S/SKILL.draft.md`，第 11 轮改名。
4. 尺寸、颜色、字体栈、格数范围只在 `S/scripts/bento_spec.py` 里定义一次，模板和其他脚本都从那里取。数值照 4.2、4.3、4.13，不在别处另写一份。
5. 测试一律是合成数据或本仓库已有的样图，写在 `S/scripts/test_bento.py`（unittest），由 `python3 S/scripts/bento.py --selftest` 调起，做法和 photo-cinematic-grade 的 `cinegrade.py --selftest` 一样。用到 `F/` 的测试，找不到文件就跳过（单技能 zip 里没有 fixtures）；要 Chrome 的测试，没装 Chrome 就跳过，但在本机必须跑通。
6. 产物里不出现苹果的东西（4.8）。五张样图只给测量和回归用。样例内容只有三种来源：本库自己的真实数字；scikit-image 自带的公有领域或 CC0 图（astronaut、coffee、chelsea、rocket）；脚本画的合成图。不读使用者电脑里的个人照片。
7. 写了中文文案（标签、SKILL.draft.md、references）就跑一遍 AI 腔词表：`grep -nFf skills/coding-helper/keynote-deck-builder/references/ai-tone-words.txt <文件>`，命中的逐条过删词测试。
8. 收工前必跑三条，全部通过才算完：`python3 S/scripts/bento.py --selftest`、`./scripts/run-selftests.sh bento-infographic`、`./scripts/validate.sh`。
9. 实测结果和第四部分写的数字对不上：差别在 ±2% 以内，照第四部分；超出时，以能复现的新读数为准，代码和第四部分的数字一起改，交接单里列出旧值、新值和量法。不停下来等回复。
10. 要给使用者看的图（对比图、矩阵图）写到会话的临时目录，用发文件的方式发出去，不放进仓库；发完接着做，不等回复。

#### 接口（各轮都按这里的名字和格式写；要改接口，在交接单里写明）

**`bento.json`**，使用者确认过的内容清单，`schema: "bento/1"`：

```json
{
  "schema": "bento/1",
  "canvas": {"use": "screen", "width": 3840, "height": 2160, "dpr": 2},
  "theme": "light",
  "mode": "product",
  "lang": "zh-CN",
  "font": "system",
  "accent": null,
  "source_line": null,
  "seed": 0,
  "tiles": [
    {"id": "hero", "kind": "hero", "word": "Skills", "weight": 3},
    {"id": "skills", "kind": "stat", "value": "62", "unit": "个", "label": "技能", "weight": 2,
     "facts": [{"text": "62 个技能", "source": "./scripts/validate.sh 的输出"}]},
    {"id": "grade", "kind": "photo", "image": "images/coffee.jpg", "fit": "cover",
     "label": "电影感调色", "weight": 2}
  ],
  "dropped": [{"text": "被舍掉的条目", "reason": "为什么舍掉"}]
}
```

（示例里的数字只是示意，样例要在当轮现数。）

| 字段 | 取值 | 说明 |
|---|---|---|
| `canvas.use` | `screen` / `print` / `phone` / `custom` | 决定 u（4.3） |
| `canvas.width`、`height` | 整数 | 输出像素；CSS 像素 = 输出像素 ÷ `dpr`（默认 2） |
| `theme` | `light` / `light-inverse` / `dark` | 4.2 的三种底与格 |
| `mode` | `product` / `research` | 只有 research 能用 `chart` |
| `lang` | `zh-CN` / `en` | 决定行高与标签长度规则 |
| `font` | `system`（默认）/ `open` | PDF 一律按 `open` 出 |
| `accent` | `null` 或 `"#rrggbb"` | 产品自己的颜色 |
| `source_line` | `null`（默认）或字符串 | 使用者要求时才填 |
| `tiles[].kind` | `hero` `stat` `word` `icon` `object` `photo` `ui` `row` `flank` `chart` | 4.4 的十种；`hero` 恰好一个 |
| `tiles[].weight` | 1–3 | 3 最大 |
| `tiles[].label` | 字符串，`\n` 是手写换行 | 英文 ≤ 7 词；中文 ≤ 12 字、每行 ≤ 11 字 |
| `tiles[].label_pos` | `bottom` / `top` | 可选，按种类有默认值；照片格不写时按标签下那块照片的对比度自动选上或下（第 7 轮）；图和字左右并排由格子长宽比决定，不用写 |
| `value`、`unit` | 字符串 | `stat` 用（`flank` 两侧的数写在 `left`、`right`）；研究模式的 `stat` 另有 `uncertainty`（不确定度，画成"42.3 ± 0.3 s"）、`n`（样本数）、`condition`（条件），`n` 与 `condition` 画成标签下面一行；没有不确定度时写 `"exact": true`（计数、定义值、确定性计算的结果）或 `"n": 1`（只测了一次）（第 8 轮） |
| `word` | 字符串 | `word` 与 `hero` 的大字 |
| `image`、`fit`、`focus` | 路径；`contain` / `cover`；`"50% 40%"` | `object` `photo` `ui` `flank` 必填；`hero` `stat` `word` `icon` 可选。全部字段（含 `tone`、`background`、`box_aspect`、`icon_size` 等）见 `S/references/bento-json.md` |
| `icon` | `S/assets/icons/index.json` 里的名字 | `icon` |
| `items` | 字符串或图片路径的列表 | `row` |
| `series`、`highlight`、`chart`、`highlight_label` | 数列；下标；`line` / `bar`；高亮处的标注（默认就是那个数） | `chart`（第 8 轮） |
| `accent`（格子级） | 布尔 | 只允许 `stat`、`word`、`hero`、`icon`（第 5 轮）、`chart`（只用在高亮处，第 8 轮） |
| `facts` | `[{"text", "source"}]` | 有数字的格必填；找不到出处就写 `"unverified": true` |

**`layout.json`**，`schema: "bento-layout/1"`。格位是 `[列, 行, 宽, 高]`，从 0 数，单位是网格小格：

```json
{"schema": "bento-layout/1", "grid": {"cols": 28, "rows": 16}, "seed": 7, "score": -3.2,
 "cells": {"hero": [7, 4, 14, 8], "skills": [0, 0, 3, 4]}}
```

**`qa.json`**，`schema: "bento-qa/1"`。检查项的 `id` 固定为：`hero_center` `hero_area` `gutter_uniform` `radius_uniform` `unit_size` `type_scale` `weight` `overflow` `label_lines` `label_length` `fonts` `contrast` `accent_hues` `text_only_share` `tile_count` `min_tile` `image_upscale` `output_size` `cjk_spacing`：

```json
{"schema": "bento-qa/1", "pass": false,
 "checks": [{"id": "contrast", "value": 3.1, "limit": ">= 4.5", "pass": false, "where": "dive"}],
 "fonts": {"system": 31, "fallback": 0, "other": 0},
 "warnings": []}
```

**`dom.json`**，渲染时从页面量出来，供自检用：每格的矩形与圆角；每段文字的矩形、计算后的字号与字重、颜色、行数、是否溢出；每张图的原始像素与显示矩形。

**Python 函数**：

```python
# bento_spec.py
def unit_px(css_w: float, css_h: float, use: str) -> float          # screen/print/custom: 0.022 × 短边；phone: 0.028 × 宽
def tokens(css_w: float, css_h: float, use: str, theme: str, lang: str) -> dict
def tokens_for(spec: dict, font: str | None = None) -> dict           # 第 8 轮加：从 bento.json 取参数，出处行开着时下边距加高
def display_label(t: dict, lang: str) -> str | None                   # 第 8 轮加：画出来的标签（研究格多一行样本数与条件）
def count_range(use: str, css_w: float, css_h: float) -> tuple[int, int]    # 建议范围，超出只提醒
def count_limits(use: str, css_w: float, css_h: float) -> tuple[int, int]   # 上下限，超出算不过（第 7 轮加）
def load_spec(path) -> dict
def validate_spec(spec: dict, base_dir) -> list[str]                # 空列表表示通过
# bento_layout.py
def grid_for(css_w: float, css_h: float, u: float) -> tuple[int, int]
def place_hero(cols: int, rows: int, hero: dict, canvas_aspect: float, use: str) -> tuple[int, int, int, int]
def fill_ring(cols: int, rows: int, hero: tuple, rules: dict, rng) -> list[tuple] | None
def score(rects: list[tuple], cols: int, rows: int, rules: dict) -> float
def assign(tiles: list[dict], rects: list[tuple], cell: tuple[float, float], u: float) -> dict
def candidates(spec: dict, n: int = 3, seeds: int = 500) -> list[dict]   # 每个元素是一份 layout.json
# bento_render.py
def build_html(spec: dict, layout: dict, out_dir) -> Path
def screenshot_cli(html_path, png_path, css_w: int, css_h: int, dpr: int = 2) -> Path   # 后备
class Chrome:                                                        # with Chrome() as c: ...
    def open(self, html_path, css_w: int, css_h: int, dpr: int = 2): ...
    def wait_fonts(self): ...
    def screenshot(self, png_path): ...
    def print_pdf(self, pdf_path): ...
    def fonts_used(self) -> list[dict]: ...
    def dom_metrics(self) -> dict: ...
def render(spec_path, layout_path, out_dir, pdf: bool = False) -> dict
def photo_label_pos(img_path, box: dict, focus: str | None, label: str, tok: dict) -> str   # 第 7 轮加
# bento_check.py
def check(spec: dict, layout: dict, dom: dict, png_path, textless_png_path) -> dict   # 返回 qa.json
# bento_chart.py
def svg(series: list, highlight: int | None, kind: str, width: float, height: float, u: float, ink: str, accent: str | None,
        highlight_label: str | None = None) -> str
# measure_reference.py
def measure(image_path, method: str = "color", cuts=None) -> dict
```

命令行（`bento.py`）：`plan SPEC`、`layout SPEC --n 3 --out DIR`、`render SPEC LAYOUT --out DIR [--pdf] [--cli] [--no-check]`、`check SPEC LAYOUT --dir DIR`、`--selftest`。

#### 第 1 轮：测量脚本与回归基准

- **目标**：把 4.2 的量法写成脚本，量出五张样图的结构、格缝、圆角和字号，存成排版器回归要用的 JSON。
- **前置**：无。
- **读**：4.2；`F/apple-reference/README.md`。
- **建**：`S/scripts/measure_reference.py`；`S/scripts/test_bento.py`（这一轮的测试）；`S/scripts/bento.py`（先只有 `--selftest`，转调 `test_bento.run_tests()`）；`F/apple-reference/labels.json`；`F/apple-reference/measurements.json`（脚本生成）。
- **步骤**：
  1. 先写合成图测试。用 Pillow 画 1600×900 的图：底 #e8e8e8，12 个白色圆角格，圆角 32 px，格缝 12 px，主图居中 784×432。断言找出 12 格、每格边框误差 ≤ 1 px、圆角读数 30–34 px、格缝读数 11–13 px、主图识别正确。同样的布局画一张深色版（底 #181818、格 #000）再断言一遍。先跑一次，确认失败。
  2. 写 `measure(image_path, method)`：
     - `method="color"`：取画布最外 3 px 一圈的中位色当底色；和底色差值不超过容差的算底（浅色底 4、深色底 6，按底色亮度选）；其余做 3×3 开运算、取连通域，丢掉面积小于画布 1% 的。
     - `method="gutter"`：给样图 1 那种磨砂格用。先高斯模糊（σ = 1），把梯度 < 0.9 且长度 ≥ 60 px 的横竖平坦段当格缝，剩下的是格。这张图自动切会粘连两处（USB-C 与 C1，Satellite 与 Apple Intelligence），允许在 `labels.json` 里给 `cuts`（人工切线），用了要在 `measurements.json` 里注明。
     - 每格记：边框；填充色（离上边 8–14 px 那一条的中位色）；四角半径（沿对角线找第一个格内像素，r = d ÷ (1 − 1/√2)）；曲线起点（沿边找偏离直边超过 0.35 px 的最远处）。
     - 整张图记：底色、四边外边距、格缝（垂直方向重叠 > 40 px、间隔 < 40 px 的相邻格）、格数、主图（包含画布中心的最大格）、主图中心偏差、主图面积占比。
  3. 写 `labels.json`，每张样图标几条标签的框和原文。下面这些框本轮已经量过，照抄：

     ```json
     {
       "01-iphone-16e.webp": {"method": "gutter", "labels": [
         {"box": [1140, 225, 1490, 262], "text": "Action button", "polarity": "dark"},
         {"box": [912, 640, 1042, 680], "text": "Face ID", "polarity": "dark"}]},
       "02-apple-watch-ultra-2.webp": {"method": "color", "labels": [
         {"box": [575, 735, 826, 770], "text": "Precision Finding for iPhone", "polarity": "dark"},
         {"box": [990, 735, 1380, 770], "text": "A new gesture for Apple Watch", "polarity": "dark"}]},
       "03-ios-18.webp": {"method": "color", "labels": [
         {"box": [30, 660, 388, 735], "text": "Biggest-ever Photos update", "polarity": "dark"},
         {"box": [424, 120, 982, 185], "text": "Categorization in Mail", "polarity": "dark"},
         {"box": [1413, 670, 1972, 720], "text": "Home Screen customization", "polarity": "dark"}]},
       "04-iphone-duo.webp": {"method": "color", "labels": [
         {"box": [26, 570, 468, 615], "text": "Largest iPhone display ever", "polarity": "dark"},
         {"box": [27, 822, 658, 870], "text": "Most versatile iPhone", "polarity": "dark"}]},
       "05-iphone-17-pro.webp": {"method": "color", "labels": [
         {"box": [23, 865, 485, 915], "text": "Three stunning finishes", "polarity": "light"},
         {"box": [520, 1050, 1082, 1100], "text": "Eight pro lenses in your pocket", "polarity": "light"}]}
     }
     ```

     对每条标签：按行投影量字高（字顶到基线）与行距；再用本机 `/System/Library/Fonts/SFNS.ttf`（可变字体，Weight 600，光学尺寸 60）按同样字高渲染同一段文字，用宽度反推字号 u。没有这个字体文件就跳过，结果里写明。
  4. 跑五张样图，写 `measurements.json`：每张一节放上面的全部读数，最后一节汇总成 u 的倍数。
  5. 写真实样图的回归测试（找不到 `F/` 就跳过）：
     - 格数依次是 16、17、18、17、14；
     - 主图中心偏差：样图 2–5 ≤ 0.2%，样图 1（被裁过）≤ 0.5%；样图 1、4、5 的主图宽占 48–50%、高占 47–49%；
     - 样图 2–5 的 u 在画布宽的 1.18–1.28% 之间，格缝 0.62–0.72u，圆角 1.50–1.62u；五张的格缝都在宽的 0.75–0.88%，圆角都在 1.83–1.95%；
     - 样图 3、4、5 的"曲线起点 ÷ 半径"中位数在 0.8–1.2（普通圆角）。
- **验证**：

  ```bash
  python3 skills/coding-helper/bento-infographic/scripts/measure_reference.py all tests/fixtures/bento-infographic/apple-reference -o tests/fixtures/bento-infographic/apple-reference/measurements.json
  python3 skills/coding-helper/bento-infographic/scripts/bento.py --selftest
  ./scripts/run-selftests.sh bento-infographic
  ./scripts/validate.sh
  ```

  第一条打印五行汇总（格数、主图占比、u、格缝 ÷ u、圆角 ÷ u），和 4.2 一致；后三条全部通过。
- **交接**：汇总表贴进交接单；和 4.2 有出入的读数单独列出。
- **不做**：模板、排版、渲染。
- **规模**：脚本约 350 行，测试约 150 行。

#### 第 2 轮：尺寸规格、模板和第一张图

- **目标**：把 4.2、4.3 的数值写进 `bento_spec.py`；做出十种格子的 HTML 模板；照样图 4 的结构手工摆一张 16:9 图，内容换成本库自己的，和样图并排比。
- **前置**：无。第 1 轮已完成的话，用它的 `measure_reference.py` 量本轮的成图。
- **读**：4.2；4.3 的 u 表；4.4；4.8 的字体一条；4.13。
- **建**：`S/scripts/bento_spec.py`；`S/templates/bento.html`；`S/scripts/bento_render.py`（这一轮只有 `build_html` 和后备的 `screenshot_cli`）；`F/specs/replica-16x9.json` 与 `F/specs/replica-16x9.layout.json`（手写格位）；`F/images/`（scikit-image 样图导出，附 README 写明每张图的授权，授权原文从本机 `skimage.data` 各函数的文档字符串里抄）。
- **改**：`S/scripts/test_bento.py`；`S/scripts/bento.py`（加 `render ... --cli`）。
- **步骤**：
  1. 先写测试并确认失败：
     - `unit_px(1920, 1080, "screen")` ≈ 23.76；`unit_px(621, 828, "phone")` ≈ 17.39；
     - `tokens()` 里格缝、外边距、圆角、文字离格边、功能名、大数字依次是 0.68u、0.68u、1.55u、0.95u、1.75u、3.2u；行高英文 1.18、中文 1.3；字重 600；
     - `validate_spec()` 能抓出：两个 hero；中文标签超过 12 字；一行超过 11 字；带数字的格既没有 `facts` 也没写 `unverified`；产品模式里出现 `chart`；未知的 kind；图片路径不存在。
  2. 写 `bento_spec.py`，数值照抄：

     ```python
     U_SHORT_SIDE = 0.022        # screen / print / custom：短边的 2.2%
     U_PHONE_WIDTH = 0.028       # phone：宽的 2.8% 起
     RATIOS = {"gutter": 0.68, "margin": 0.68, "radius": 1.55, "inset": 0.95, "pad": 1.0,
               "word": 1.75, "number": 3.2, "number_min": 2.2, "number_max": 4.3,
               "hero_word_min": 5.0, "hero_word_max": 8.0, "icon": 3.5,
               "min_tile_w": 6.0, "min_tile_h": 6.5, "max_aspect": 3.5}
     LINE_HEIGHT = {"en": 1.18, "zh-CN": 1.3}
     WEIGHT = 600
     THEMES = {
         "light":         {"canvas": "#e8e8e8", "tile": "#ffffff", "ink": "#000000"},
         "light-inverse": {"canvas": "#ffffff", "tile": "#ececec", "ink": "#000000"},
         "dark":          {"canvas": "#181818", "tile": "#000000", "ink": "#ffffff"},
     }
     FONT_STACKS = {
         "system": 'system-ui, BlinkMacSystemFont, "PingFang SC", "Inter", "Noto Sans SC", sans-serif',
         "open":   '"Inter", "Noto Sans SC", "Source Han Sans SC", sans-serif',
     }
     LABEL_LIMITS = {"en_words": 6, "en_lines": 3, "zh_chars": 12, "zh_line_chars": 11, "zh_lines": 2}
     ```

     图标 3.5u 来自样图上四个图标的实测（Face ID 3.4u、游戏手柄 4.1u、骑行 3.1u、手电筒 3.1u，取最长边）。
  3. 写 `templates/bento.html`：一个 `<style>`，CSS 变量 `--u --gutter --margin --radius --inset --canvas --tile --ink --accent --font --cols --rows` 由 `build_html` 填。
     - `.stage`：CSS Grid，`grid-template-columns: repeat(var(--cols), minmax(0, 1fr))`，行同理；`gap` 是格缝，`padding` 是外边距；底色 `--canvas`；宽高等于 CSS 画布。
     - `.tile`：`border-radius: var(--radius)`，`overflow: hidden`，`position: relative`，底色 `--tile`；不写 `box-shadow`、`filter`、`backdrop-filter`。
     - `.label`：字号 `--u`，字重 600，字距 0，居中；离格边 `--inset`，用绝对定位放在下、上或侧边。每行一个 `<span class="line">`，各自 `white-space: nowrap`。
     - 十种格子各一个类（`.k-hero` `.k-stat` `.k-word` `.k-icon` `.k-object` `.k-photo` `.k-ui` `.k-row` `.k-flank` `.k-chart`），字号都写成 `calc(var(--u) * 倍数)`，倍数取自 `RATIOS`。
     - 照片格白字压在底部；不加渐变遮罩，字看不清就换照片或换格子（第 6 轮的对比度检查会抓）。
  4. 写 `build_html`：文字一律 `html.escape`；标签按 `\n` 拆行；图片复制到输出目录的 `assets/` 再用相对路径引用；格位写成行内 `grid-column: c+1 / span w; grid-row: r+1 / span h`。这一轮的样例不放图标格，图标第 5 轮才有。
  5. 写 `replica-16x9.json` 与手写格位。内容是本库自己：主图是"Skills"这个词（照样图 3 的写法），数字格当轮现数并写明出处（skill 数看 `validate.sh` 的输出，分类数看 `ls skills`，用例数看 `ls tests/cases`）；照片格用 `F/images/` 里的图。格位照样图 4 的结构，放在 28 × 16 的网格上：
     - 上带第 0–3 行通栏，6 格，宽 3 / 4 / 4 / 6 / 4 / 7；
     - 左栏第 4–11 行、第 0–6 列，上 5 行一格、下 3 行一格；
     - 主图第 7–20 列、第 4–11 行；
     - 右栏第 21–27 列：第 4–7 行并排两格（宽 4 和 3），第 8–11 行一格；
     - 下带第 12–15 行通栏，5 格，宽 10 / 4 / 5 / 3 / 6。
     合计 17 格。
  6. 用 `screenshot_cli` 出图：`--headless=new --hide-scrollbars --force-device-scale-factor=2 --window-size=1920,1080 --default-background-color=00000000 --virtual-time-budget=3000 --screenshot=...`，得到 3840×2160 的 PNG。
  7. 量自己的图。第 1 轮已经完成的话，用 `measure_reference.py` 量这张 PNG：格缝 0.65–0.71u，圆角 1.50–1.60u，主图宽高占比 48–50%，中心偏差 ≤ 0.2%。再拼一张"左边本轮成图、右边样图 4"的对比图，发给使用者，接着往下做。
- **验证**：`python3 S/scripts/bento.py render F/specs/replica-16x9.json F/specs/replica-16x9.layout.json --out <临时目录> --cli` 出 3840×2160 的 PNG；通用规则第 8 条的三条命令全部通过；对比图已发出。
- **交接**：成图和对比图的路径；量出的格缝、圆角、主图读数；看得出来的不像之处（字偏大偏小、格子太花、颜色不对）。
- **不做**：排版器、DevTools 渲染、自检。
- **规模**：`bento_spec.py` 约 200 行，模板约 350 行，`build_html` 约 200 行，测试约 150 行。

#### 第 3 轮：Chrome 渲染器（DevTools 协议）、字体与可重复性

- **目标**：只用标准库，通过 `--remote-debugging-pipe` 驱动 Chrome：精确视口、2 倍像素、等字体加载完再截图、出 PDF、查每段文字实际用上的字体、量出 `dom.json`；同一份输入渲染两次，PNG 字节相同。
- **前置**：第 2 轮。
- **读**：4.5 第 4 步；4.8 的字体一条；4.9 渲染方案的几条实测。
- **改**：`S/scripts/bento_render.py`（加 `Chrome` 类和 `render()`）；`S/scripts/test_bento.py`；`S/scripts/bento.py`（`render` 默认走 DevTools 协议，`--cli` 才走后备）。
- **步骤**：
  1. 先写测试：
     - 600×400 的页面、`dpr = 2`，(50, 50) 处一个 100×100 的红块：PNG 是 1200×800，(200, 200) 那个像素是红的；
     - 页面把 `window.__bentoReady` 设成一个 1.5 秒后才兑现、兑现前插入一段文字的 Promise：截图里有这段字（说明渲染器等到了页面就绪）；
     - 系统字体栈下的"AB 中文"：英文落到 SF 系列，中文落到 PingFang SC；
     - 只写 `-apple-system` 的页面：英文也落到 PingFang SC（把子代理测到的 Chrome 行为钉成测试，防止以后有人改回去）；
     - 第 2 轮的 `replica-16x9` 连渲两次，sha256 相同；
     - 1:1 与 9:16 两个页面出 PDF：都是单页，`/MediaBox` 尺寸和页面一致。本机没装 Inter 和思源黑体时，这条跳过。
  2. 启动 Chrome。管道的接法照下面写（Chrome 从 fd 3 读、往 fd 4 写，消息之间用 `\0` 分隔）：

     ```python
     CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

     def launch(profile_dir):
         to_r, to_w = os.pipe()        # 我们写 → Chrome 读
         from_r, from_w = os.pipe()    # Chrome 写 → 我们读
         def child():
             os.dup2(to_r, 3)
             os.dup2(from_w, 4)
         proc = subprocess.Popen(
             [CHROME, "--headless=new", "--remote-debugging-pipe",
              f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check",
              "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"],
             preexec_fn=child, close_fds=False,
             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
         os.close(to_r)
         os.close(from_w)
         return proc, to_w, from_r
     ```

     `os.pipe()` 拿到的 fd 号有可能正好是 3 或 4。为保险，先把四个端点 `os.dup` 到 10 以上，再在子进程里接到 3 和 4。
  3. 消息循环：自增 `id`；`Target.createTarget` 后用 `Target.attachToTarget`（`flatten: true`）拿 `sessionId`；`Page.enable`；`Emulation.setDeviceMetricsOverride`（宽、高、`deviceScaleFactor: 2`、`mobile: false`）；`Page.navigate` 打开 `file://` 地址，等 `Page.loadEventFired`；`Runtime.evaluate` 等 `window.__bentoReady`（`awaitPromise: true`）。这个 Promise 由模板定义，等于 `document.fonts.ready` 加上页面里每张图的 `decode()`；`document.fonts.ready` 本身不会等图片和脚本；`Page.captureScreenshot`（`format: "png"`）。PDF 用 `Page.printToPDF`（`printBackground: true`，`preferCSSPageSize: true`），页面里写 `@page { size: Wpx Hpx; margin: 0 }`。
  4. `fonts_used()`：`DOM.getDocument` → `DOM.querySelectorAll('.label .line, .num, .word, .hero-word, .source')` → 每个节点调 `CSS.getPlatformFontsForNode`，记下字族、PostScript 名和字形数。`document.fonts.check()` 不能用：字体不存在它也返回 true。
  5. `dom_metrics()`：注入一段 JS，返回 4.12 接口里 `dom.json` 列的字段。行数用 `Range.getClientRects()` 数不同的行顶。
  6. `render()`：`build_html` → `open` → `wait_fonts` → `screenshot` → `dom_metrics` → `fonts_used`；再把文字设成 `visibility: hidden` 截一张 `*.textless.png`，第 6 轮算照片上文字的对比度要用；`pdf=True` 时先把字体栈切到 `open` 再打印。
  7. 装兜底字体（已同意）：`brew install --cask font-inter font-noto-sans-sc`，装完重跑 PDF 那条测试。交接单写明装了哪两个包、版本和大小。brew 失败（网络或权限）就让 PDF 测试保持跳过，交接单写明原因，不换别的下载渠道。
- **验证**：通用规则第 8 条；`python3 S/scripts/bento.py render F/specs/replica-16x9.json F/specs/replica-16x9.layout.json --out <临时目录>` 出 PNG、`dom.json`、`fonts.json`、`*.textless.png`。
- **交接**：`fonts.json` 的汇总（哪几段用了哪套字体）；可重复测试的结果；PDF 是否跳过、为什么跳过。
- **不做**：自检（第 6 轮）、排版器。
- **规模**：约 300 行，测试约 120 行。

#### 第 4 轮：排版器与样图结构回归

- **目标**：实现 4.3 的排版器（按画幅选网格、主图居中、外圈精确覆盖、打分挑三个、内容进格），五张样图的结构回归全部通过。
- **前置**：第 1 轮（要用 `measurements.json`）。可以和第 3 轮同时开。
- **读**：4.2 的主图与外圈两节；4.3 的排版器一节。
- **建**：`S/scripts/bento_layout.py`。
- **改**：`S/scripts/test_bento.py`；`S/scripts/bento.py`（加 `layout` 子命令，每个方案顺带出一张线框 PNG：灰块上写格子 id）。
- **步骤**：
  1. 先写测试：
     - `grid_for(1920, 1080, 23.76) == (56, 32)`，`grid_for(621, 828, 17.39) == (24, 32)`，`grid_for(540, 960, 15.12) == (24, 44)`。规则是 `m4(W ÷ 1.45u)` 和 `m4(H ÷ 1.45u)`，`m4` 取最近的 4 的倍数，下限 8（第 2 轮定的粒度，见 4.3）。
     - `place_hero`：16:9 产品主图得 `(14, 8, 28, 16)`；主图是词（只有 `word`）得 `(17, 11, 22, 10)`；正方形的产品图（长宽比 1.0）在 16:9 上收窄成宽 20 格；竖版 3:4 上放长宽比 1.6 的图，改成通栏主图（宽 = 全部列数）。主图跨的格数和总格数奇偶相同。
     - `fill_ring`：28 × 16 加居中主图，种子 0–49 全部铺满；每格 ≥ 最小格；长宽比 ≤ 3.5；贯穿全图的直缝 ≤ 2 条；同尺寸的格不连着排三个以上；最小那种尺寸的格不超过三成；格数在 `count_range` 里。
     - `assign`：标签放不下的格不会被分到；`weight` 3 的内容分到面积前 20% 的格；同一份输入、同一个种子，结果相同。
  2. 写 `grid_for`、`place_hero`。主图默认宽 `C/2`、高 `R/2`；只有词的主图宽取最接近 `0.39C` 的偶数、高取最接近 `0.32R` 的偶数；产品图比画布窄时，按"主图框长宽比 ≈ 图的长宽比 × 1.25"收窄，宽不小于画布宽的 35%。
  3. 写 `fill_ring`：占用表记录哪些小格已占；每次取行优先的第一个空格，从允许的跨度里按权重随机挑（中等大小权重最高）；放不下就回溯；剩余面积已经凑不出格数下限时提前剪枝。
  4. 写 `score` 与 `candidates`：扣分项照 4.3；结构签名 =（四个角归带还是归栏，跨度排序后的元组），只留签名不同的前三个。
  5. 写 `assign`：代价矩阵每格 =「格子长宽比和内容偏好长宽比之差的对数绝对值」+「重要程度和面积名次之差」+「大数字不在角上加一点」；标签估宽（中文每字 1u、英文每字符 0.55u）超过"格宽 − 2.4u"记为无穷大；用 `scipy.optimize.linear_sum_assignment` 求解。纯文字格挨在一起时换下一个方案。
  6. 样图结构回归：每张样图按 `measurements.json` 造一份只有格数、主图框长宽比的空内容清单，跑 `candidates(n=3)`。前三个里至少一个满足：
     - 样图 1、4、5（产品主图）：主图框 IoU ≥ 0.9，格数相同，上带高度和左栏宽度与原图相差不超过画布对应尺寸的 2%；
     - 样图 2、3（手表和"iOS"这两种窄主图）：IoU ≥ 0.75，格数相同。28 列的网格加上奇偶规则，主图宽只能两格一跳（每跳约 7%），这两张贴不到 0.9；样图 3 的外圈也切得太碎，不比厚度。
     第 2 轮手写的 16:9 格位，主图算下来宽 48.7%、高 47.8%（格缝 0.68u），和样图 4 的 IoU 约 0.99，可以当这一步的自检。
  7. 量性能：16:9 跑 500 个种子不超过 2 秒，超了先查剪枝；实在不行再试 `scipy.optimize.milp`。
- **验证**：通用规则第 8 条；`python3 S/scripts/bento.py layout F/specs/replica-16x9.json --n 3 --out <临时目录>` 出三份 `layout-*.json` 和三张线框图。
- **交接**：回归表（每张样图的 IoU、厚度差、格数）；耗时；16:9 与 3:4 的线框图发给使用者。
- **不做**：渲染成图、自检。
- **规模**：约 550 行，测试约 250 行。

#### 第 5 轮：内容清单、图标与端到端

- **目标**：从 `bento.json` 一路到 PNG：`plan`（可读表加线框）→ `layout` → `render` 串通；加入图标；出 16:9 浅色和深色两张产品图。
- **前置**：第 3、4 轮。
- **下载图标（已同意）**：照「已经同意的事」里的地址，从 Phosphor 固定的那次提交下载用得到的约 60 个 Fill 图标和 `LICENSE`。按两份样例和常见的产品、研究内容挑：设备、相机、电池、时钟、锁、地球、闪电、芯片、图表、烧瓶、原子、尺子、书、对勾、星形、云、麦克风、耳机、汽车、心形等。哪个下载失败就换同义的图标，交接单列出最终清单。
- **建**：`S/assets/icons/*.svg`；`S/assets/icons/LICENSE`；`S/assets/icons/index.json`（名字 → 文件，外加中英关键词，方便模型挑）；`F/specs/product-16x9-light.json`、`F/specs/product-16x9-dark.json`。
- **改**：`S/scripts/bento.py`（加 `plan`）；`S/scripts/bento_render.py`（图标格：内联 SVG，`fill: currentColor`，最长边 3.5u）；`S/scripts/test_bento.py`。
- **步骤**：
  1. 先写测试：`plan` 对一份坏清单（中文标签 14 字、有数字没出处）报出两条问题，并返回非零退出码；对好清单打印表格并写出 `wireframe.png`。
  2. `plan` 打印：每格一行（id、种类、标签、重要程度、图或图标、出处或【未确认】），再打印格数、纯文字格占比、超限的标签；用 `candidates()[0]` 画线框图。
  3. 产品样例的内容是本库自己：skill 数、分类数、用例数、自检数在当轮现数，`facts` 写清楚是哪条命令的输出；功能格写库里真有的能力（发布会演示片、电影感调色、写作规则等）；照片格用 `F/images/` 的图，愿意的话先用 photo-cinematic-grade 调一遍色（那也是本库的真实产物）。深色版换成 `theme: "dark"`，其余不变。
  4. 端到端：`plan` → `layout --n 3` → 挑第一个 → `render`。两张图各和样图 3（词做主图）、样图 5（深色）拼成对比图，发给使用者，不等回复。
- **验证**：通用规则第 8 条；两张产品图都出了 PNG、`dom.json`、`fonts.json`；`fonts.json` 里没有落到字体栈以外的字体。
- **交接**：两张成图和对比图的路径；自己看出来的不像之处。使用者之后提的意见，由后面的轮次处理。
- **不做**：自检的阈值判断（第 6 轮）。
- **规模**：约 250 行代码，外加图标与样例。

#### 第 6 轮：自检

- **目标**：4.7 的每条护栏都能自动判断，出 `qa.json`；故意做坏的输入每一种都能抓到，好样例全部通过。
- **前置**：第 5 轮。
- **建**：`S/scripts/bento_check.py`。
- **改**：`S/scripts/bento.py`（加 `check`；`render` 收尾默认跑一遍，`--no-check` 关掉）；`S/scripts/test_bento.py`。
- **步骤**：
  1. 先做坏样本，每种对应一个检查项，写成测试（期望该项 `pass: false`）：
     - 中文标签超长，一行放不下 → `overflow`
     - 在测试页面里把一处字重改成 700 → `weight`
     - 白字压在很亮的照片上 → `contrast`
     - 两个不同色相的重点色 → `accent_hues`
     - 一半格子是纯文字 → `text_only_share`
     - 200×200 的小图放进大格 → `image_upscale`
     - 16:9 只排 9 格 → `tile_count`
     - 手写格位让主图偏离中心 → `hero_center`
     - 字体栈只写一个不存在的字体 → `fonts`
     - "测量结果 3mm"（汉字和数字之间没有空格）→ `cjk_spacing`
  2. 逐项实现（数据都来自 `dom.json`、`layout.json`、`bento.json` 和两张 PNG）：
     - 主图中心偏差与面积；格缝与圆角是否全图统一（偏差 ≤ 1 px）；
     - 所有文字的计算字号与字重（标签 = u；其余落在各自倍数范围；字重一律 600）；
     - 溢出（`scrollWidth > clientWidth`，或文字矩形越出格子）；标签行数与长度；
     - 字体：每段文字都落在字体栈列出的字体上，用了兜底的写进 `warnings`；
     - 对比度：文字色对格子底色；照片格在 `*.textless.png` 上取文字背后那块，按最不利的 10% 亮度算；标签 ≥ 4.5:1，1.6u 以上 ≥ 3:1；
     - 重点色：文字和图标里饱和度 > 0.2 的颜色按色相聚类，类数 ≤ 1，而且不出现在标签上；
     - 纯文字格占比 ≤ 30%；格数在 `count_range` 里；最小格 ≥ 6u × 4.8u；
     - 图片放大倍数：原图像素 ÷（显示尺寸 × dpr），小于 1 记录，小于 0.8 报警；
     - 输出 PNG 的像素和 `canvas` 完全一致。
  3. 两张产品图跑 `check`，全部通过；不通过的改内容或换排版方案，不放宽阈值。
- **验证**：通用规则第 8 条；`python3 S/scripts/bento.py check F/specs/product-16x9-light.json <layout> --dir <渲染目录>` 输出 `pass: true`。
- **交接**：坏样本对照表（输入 → 抓到的检查项）；两张产品图的 `qa.json` 摘要。
- **不做**：新画幅、研究模式。
- **规模**：约 450 行，测试约 250 行。

#### 第 7 轮：任意比例与中文

- **目标**：九种画幅都排得出、都过自检；中文标签的规则全部落实。
- **前置**：第 6 轮。
- **改**：`S/scripts/bento_spec.py`（`count_range`、手机信息流的 u）；`S/scripts/bento_layout.py`（竖版通栏主图、超宽画幅）；`S/scripts/bento_render.py`（中文行高 1.3、逐行不换行、名字里的不换行空格）；`S/scripts/bento_check.py`（`cjk_spacing`）；`S/scripts/test_bento.py`。
- **建**：`F/specs/matrix/` 下九份内容相同、画幅不同的清单（同一份 12 格中文内容）。
- **画幅与格数范围**（第 7 轮按实际渲染校准后的值，算法见 4.3；初值见交接记录第 7 行）：

  | 画幅 | 输出像素 | use | 建议格数（含主图） | 上下限 |
  |---|---|---|---|---|
  | 16:9 | 3840×2160 | screen | 14–18 | 10–21 |
  | 4:3 | 2048×1536 | screen | 12–15 | 8–18 |
  | 21:9 | 3440×1440 | screen | 17–22 | 12–26 |
  | A4 竖版 | 2480×3508 | print | 12–16 | 8–18 |
  | 1:1 | 2160×2160 | phone | 10–13 | 7–15 |
  | 3:4 | 1242×1656 | phone | 12–15 | 8–18 |
  | 4:5 | 1080×1350 | phone | 11–15 | 8–17 |
  | 9:16 | 1080×1920 | phone | 14–18 | 10–21 |
  | 1:2 长图 | 1080×2160 | phone | 15–19 | 10–23 |

- **步骤**：
  1. 先写测试：每种画幅的 `grid_for` 结果，行列都是 4 的倍数、小格长宽比在 0.8–1.25 之间；竖版画布遇到长宽比 > 1.3 的主图，主图通栏；中文标签一行超过 11 字被拒；"iPhone 18 Pro Max"里的不换行空格保留；汉字紧挨拉丁字母或数字时 `cjk_spacing` 给警告。
  2. 中文规则（4.2 中文一节）：行高 1.3，字距 0；换行由模型写在 `label` 里（`\n`），每行单独不换行，不靠浏览器自动折行；汉字与拉丁字母、数字之间要有空格。
  3. 九份清单逐一 `plan` → `layout` → `render` → `check`，全部通过。
  4. 拼一张九宫格总览图，发给使用者。
- **验证**：通用规则第 8 条；九份 `qa.json` 全部 `pass: true`。
- **交接**：九宫格总览图；校准后的格数范围；哪种画幅最难排、为什么。
- **不做**：研究模式。
- **规模**：约 200 行，测试约 150 行。

#### 第 8 轮：研究模式与抠图

- **目标**：研究成果能排：小图表格、带不确定度的数字格、可选的出处行；产品照片可以选择抠图。
- **前置**：第 7 轮。
- **建**：`S/scripts/bento_chart.py`；`S/scripts/cutout.swift`；`F/specs/research-3x4.json`。
- **改**：`S/scripts/bento_spec.py`（研究模式字段与校验）；`S/scripts/bento_render.py`（图表格、出处行）；`S/scripts/bento_check.py`（出处行字号可以是 0.75u）；`S/scripts/test_bento.py`。
- **步骤**：
  1. 先写测试：
     - `bento_chart.svg(series=[...], highlight=3, kind="line")` 输出的 SVG 只有一条折线、一个高亮点、一个数值标注，没有网格线和坐标刻度；
     - 研究模式的数字格没写 `uncertainty` 也没写 `"exact": true` 时，`validate_spec` 报错；有不确定度时渲染成"1.23 ± 0.04 s"，`n` 和 `condition` 写进下面那行小标签；
     - 没填 `source_line` 就不出出处行；填了才出，0.75u，对比度 ≥ 4.5:1；
     - `cutout.swift` 只在 macOS 14 以上跑：对 `F/images/coffee.jpg` 输出带 alpha 的 PNG，前景占画面 10–80%。
  2. 小图表：一条折线或几根柱，线宽 0.12u，颜色用 `ink`，高亮点用 `accent`（没有重点色就用 `ink`），只标关键值。
  3. 研究版样例：用第三部分 3.5、3.9 里调色原型的实测数字（LUT 回读误差、肤色色相漂移、区分度、全尺寸渲染耗时），出处写"第三部分 3.9，原型 0.4.1 实测"；照片格用 rocket、coffee、chelsea；画幅 3:4、浅色、研究模式。
  4. `cutout.swift`：约 25 行，`VNGenerateForegroundInstanceMaskRequest`，用法 `swift cutout.swift in.jpg out.png`；在 SKILL 文档里写明这是可选步骤，只处理使用者自己的照片。
- **验证**：通用规则第 8 条；研究版 `qa.json` 为 `pass: true`；`swift S/scripts/cutout.swift F/images/coffee.jpg <临时目录>/coffee-cut.png` 出带透明底的 PNG。
- **交接**：研究版成图；抠图前后对比。
- **不做**：文档。
- **规模**：约 250 行，外加 25 行 Swift。

#### 第 9 轮：说明文档、用例与样例

- **目标**：写好 `S/SKILL.draft.md`、四份 references、`tests/cases/bento-infographic.md` 和 examples，让一个没看过本节的 agent 只读这些文件就能把 skill 用对。
- **前置**：第 8 轮。
- **读**：第四部分全文；`skills/coding-helper/launch-summary-panel/SKILL.md` 的「事实校验规则」一节；`templates/skill-template.md`；`CONTRIBUTING.md` 第 3 节。
- **建**：
  - `S/SKILL.draft.md`：frontmatter 照 skill 模板写，`name: bento-infographic`，`category: coding-helper`，`version: 0.1.0`，`status: draft`，`priority: P1`，`display_name: 发布会 bento 信息图`，`compatible_agents` 照 photo-cinematic-grade 写 claude-code、codex、cursor、codebuddy、nestudy；description 用 4.1 的草稿，不超过 1024 字。正文依次是：何时使用与分流（keynote、photo-series-layout；launch-summary-panel 已废弃）；输入；工作流（4.5）；尺寸规则（u 表，细节链到 references）；格子种类；标签写法；事实校验规则（从 launch-summary-panel 搬过来，加上研究模式的两条）；不做的事（4.8）；自检（4.7 表）；输出格式；没有 Chrome 或不在 Mac 上时的降级（按 CONTRIBUTING 3.2）；变更记录。正文控制在 25 KB 以内，细节放进 references。
  - `S/references/apple-measurements.md`（4.2 全文 + `measurements.json` 汇总 + 出处）、`bento-json.md`（4.12 接口里的字段表，配两份完整示例）、`tile-kinds.md`（十种格子各自的版式：标签位置、图的大小、字号倍数，配样图里的例子名）、`label-grammar.md`（中英标签写法，好坏例子各五条，AI 腔词表用相对路径 `../../keynote-deck-builder/references/ai-tone-words.txt` 引用：文件在 `references/` 里，要上两级，`validate.sh` 会按这个算法检查路径是否存在）。
  - `tests/cases/bento-infographic.md`：4.10 的 14 条，格式照仓库其他用例（输入 / 期望 / 反例）。
  - `S/examples/`：产品浅色、产品深色、研究 3:4 三份，每份是 `bento.json`、PNG、`qa.json`。
- **步骤**：
  1. 先写用例文件，再写 SKILL.draft.md，写完逐条对照：每条用例的"期望"都能在 SKILL.draft.md 或 references 里找到依据。
  2. 所有中文文件跑 AI 腔词表。
  3. 可以派一个 Sonnet 子代理起草四份 references，主会话写 SKILL.draft.md；交回后主会话通读一遍，统一说法。
- **验证**：通用规则第 8 条（`validate.sh` 会检查 references 里的相对路径都存在）；AI 腔词表无命中，或命中的都是本义；三份样例的 `qa.json` 全部通过。
- **交接**：文件清单与各自大小；对照用例时发现的缺口。
- **不做**：登记索引、改名 SKILL.md（第 11 轮）。

#### 第 10 轮：独立评审（验收）

- **目标**：按原定的验收标准，由没参与开发的评审代理给三张图打分，平均 8 分以上才进入发版。
- **前置**：第 9 轮。
- **步骤**：
  1. 重渲三份样例：产品浅色 16:9、产品深色 16:9、研究 3:4。另外重跑 iPhone 18 Pro 调试样例的对齐测试（`test_bento.py` 的 `AlignIphone18Pro`），并把它和官方图的对照一起交给评审。
  2. 开一个新的评审子代理（Sonnet 即可）。只给它三张成图、五张样图、4.2 的规矩表和下面的评分表，不给开发记录：

     | 项 | 看什么 |
     |---|---|
     | 字体 | 字族、字重 600、字距 |
     | 字号层级 | 标签、功能名、大数字、主图字四档拉没拉开，比例对不对 |
     | 主图 | 是否居中、够不够突出 |
     | 格子与留白 | 格缝、圆角、外边距是否统一，切分像不像 |
     | 颜色 | 底与格、文字纯黑纯白、重点色是否只有一支 |
     | 文案 | 标签短不短、是不是名词短语 |
     | 整体 | 像不像苹果的收尾总结片 |

     每项 1–10 分，必须指出哪一格、哪里不像；总分取平均。
  3. 主会话按意见改：只动模板、规格、排版参数和样例内容；改数值要写依据。改完重渲、换一个新的评审代理重评。
  4. 不到 8 分就接着改、换一个新的评审代理再评，最多五次。五次后仍不到 8 分：停在这一轮，不做第 11 轮，交接单写清每一项差多少、试过哪些改法、建议下一步怎么改（这条使用者已同意，不必问）。
  5. 通过后，把三张成图和五张样图的对照图发给使用者，由使用者在自己的屏幕上看；不等回复，第 11 轮可以直接开工。
- **验证**：评审平均分 ≥ 8；通用规则第 8 条。
- **交接**：每次评审的分数与主要意见；改了什么；对照图的路径。

#### 第 11 轮：发版

- **目标**：登记 0.1.0；废弃 launch-summary-panel；顺带改掉 keynote 研究文件里那条"8–12 格"。
- **前置**：第 10 轮通过（评审平均 ≥ 8）。不必等使用者看完成图；使用者事后有意见，按 0.1.x 另修。
- **改**：
  - `S/SKILL.draft.md` 改名为 `S/SKILL.md`。
  - `SKILL_INDEX.md`：coding-helper 表加一行 `bento-infographic`（P1、draft、0.1.0）；`launch-summary-panel` 那行状态改成 `deprecated`；Library Version 升一个 MINOR。
  - `.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`：同一个新版本号。
  - `README.md`：coding-helper 一段加上本 skill，注明 launch-summary-panel 已废弃；skills 徽章数加 1。
  - `CHANGELOG.md`（仓库根）：新版本一节。
  - `skills/coding-helper/launch-summary-panel/SKILL.md`：`status: deprecated`，description 开头写"已废弃，改用 bento-infographic"，变更记录加一行（PATCH）。
  - `skills/coding-helper/keynote-deck-builder/SKILL.md:41`：那句改指本 skill；`references/stage-style-research.md` §10 那一行降为 C 档并注明出处的问题；keynote 的变更记录加一行（PATCH）。
  - `tests/cases/launch-summary-panel.md`：开头注明已废弃，用例保留到删除那一版。
  - 本文第二部分 C 节那一行勾上；4.12 交接记录补最后一行。
  - `./scripts/package.sh` 重打 bento-infographic、keynote-deck-builder、launch-summary-panel 三个包。
- **验证**：`./scripts/validate.sh`；`./scripts/run-selftests.sh`（全部，不只本 skill）；`./scripts/package.sh --check`；`grep -rn "launch-summary-panel" skills README.md SKILL_INDEX.md`，除了它自己的文件和变更记录，没有地方还在推荐它。
- **交接**：改动文件清单（给使用者提交用）；新的 Library 版本号。

#### 交接记录

每轮收工补一行。

| 轮 | 日期 | 结果 | 遗留 |
|---|---|---|---|
| 1 | 2026-10-08 | 完成。`measure_reference.py`、`labels.json`、`measurements.json`；10 条测试通过 | 格缝、圆角改用亚像素量法重量：0.6u → 0.68u、1.6u → 1.55u，第四部分已同步（规则 9）。样图 1 靠两条人工切线才分出 16 格 |
| 2 | 2026-10-08 | 完成。`bento_spec.py`、`templates/bento.html`、`bento_render.py`（HTML 生成与命令行截图）、开发用图与 `replica-16x9`；另按使用者要求做了 iPhone 18 Pro 调试样例，和官方总结片对齐：格数、格缝、圆角、主图一致，逐格 IoU 中位数 0.94，标签与功能名字号对上；22 条测试通过 | 新读数已同步第四部分：网格 56 × 32、功能名三档、英文标签 ≤ 7 词、最小格高 4.8u、银灰字、内容色格、Display 光学尺寸。Apple Intelligence 的彩虹渐变有意不仿 |
| 3 | 2026-10-08 | 完成。`Chrome` 类（标准库，`--remote-debugging-pipe`）与 `render()`：等页面就绪、截图、`dom.json`、`fonts.json`、去字截图、PDF；31 条测试通过，连跑三遍稳定 | 按已同意的安排用 Homebrew 装了 Inter 4.1 与 Noto Sans SC（第一次 Inter 卡在下载，重试成功）。同一输入两次渲染偶尔差几个像素，原因是 Chrome 延后解码大图，加 `--run-all-compositor-stages-before-draw`、`--disable-checker-imaging` 并在就绪后再等两帧，10 次全部同字节。PDF 里中文报名"Noto Sans SC Thin"是可变字体默认实例名，实际按 600 画 |
| 4 | 2026-10-08 | 完成。`bento_layout.py`：56 × 32 网格、主图居中、外圈四条按角归属切分（16 种组合）再分段、匈牙利分配、打分、去重留前三；`bento.py layout` 出方案和线框图。38 条测试通过，500 个种子不到 0.1 秒；六张样图结构回归全过 | 接口改动：`place_hero(cols, rows, hero, tok)`（直接收 tokens，不再单传画布比例）；铺格不用整格精确覆盖的深度搜索，改成"带 + 栏"按苹果结构切分，回归更稳。分配时按内容算最小宽高（标签、两侧标注、左图右字、图标），用真实字体量宽，免得压字或切图。对 iPhone 18 Pro 内容自动排的三个方案已发给使用者 |
| 5 | 2026-10-08 | 完成。`bento.py plan`（清单表、格数、纯文字格占比、问题、线框图）；按已同意的安排下载了 Phosphor Fill 63 个图标与 MIT 许可证，`assets/icons/index.json` 配中英关键词；对外产品样例 `product-16x9-light.json` / `dark.json` 用本库自己的真实内容（2026-10-08 现数）；40 条测试通过 | 排版器补了几条分配规则：纯文字格不进空旷的大格、照片偏大格、图标偏小格、同类格不连排三个以上，并按内容算最小高度（图标格约 7u 起）。图标格允许用重点色（手表样图的做法）。浅色、深色成图与苹果样图的对照已发给使用者 |
| 6 | 2026-10-08 | 完成。`bento_check.py`：4.7 的 19 项护栏，渲染完自动写 `qa.json`，`bento.py check` 可单独重跑；15 种做坏的输入各被对应的检查项抓到，合格样例全过；55 条测试通过 | 新读数：标签左右留白 1.2u → 1.0u（官方 Apple Reference 一格两侧 1.08u，规则 9 已同步）。产品样例的照片格改成贴底裁切，白字落在暗处后对比度达标。iPhone 18 Pro 调试样例有两格对比度不到 4.5:1（telephoto 1.41、Photographic Styles 3.20），官方原图就是白字压在亮天空和人脸上，调试样例照搬官方图片，保留 |
| 7 | 2026-10-08 | 完成。九种画幅用同一份 12 格中文内容逐一 layout → render → check，九份 `qa.json` 全部通过，九宫格总览图已发给使用者。格数分成两档：`count_range` 是建议范围，超出只提醒；新加的 `count_limits` 是上下限，超出才算不过。两档都按以短边计的周长，从苹果 16:9 的实测折算（4.3）。照片格的白字标签没写位置时，按标签下面那块照片的对比度自动放在上边或下边。宽截图进了窄格就整张放进去，不切两边，排版器也优先给宽截图分宽格。竖版通栏主图改按图本身的长宽比 > 1.3 判断。65 条测试通过 | 格数旧值 → 新值（建议 / 上下限）：16:9 14–18 → 14–18 / 10–21；4:3 13–17 → 12–15 / 8–18；21:9 15–19 → 17–22 / 12–26；A4 13–17 → 12–16 / 8–18；1:1 8–11 → 10–13 / 7–15；3:4 9–12 → 12–15 / 8–18；4:5 9–12 → 11–15 / 8–17；9:16 10–13 → 14–18 / 10–21；1:2 11–14 → 15–19 / 10–23。依据有三条。一，苹果 67 张总结片常见 14–18 格，见过 10–21 格，7% 不到 12 格；按旧值，同一份 12 格内容在 16:9、4:3、21:9、A4、1:1 上都算不过。二，排版器实测：3:4 手机图能排 16 格，1:1 配两行标签最多 12 格，所以手机不再按 u 压低格数，装不下时排版器自己会报。三，用 9 种画幅的实际渲染逐张看过。<br>最难排的是 21:9：苹果没有这种比例，u 按短边算只有宽的 0.92%，12 格在上面偏空，正好压在下限上。其次是 1:1 手机图，格子最挤。<br>矩阵的照片格改用新调色的 `rocket-graded.jpg`：咖啡那张一进窄格，标签放上放下都压在亮处，到不了 4.5:1。<br>本轮清单以外动了这几个文件：`bento.py`（`plan` 打印两档格数，不然和自检对不上）、`iphone-18-pro-dark.json`（照片标签写死成官方的位置，不让自动选位改掉）、`F/images/` 的 README 与新图。<br>接口加了 `count_limits` 和 `bento_render.photo_label_pos` |
| 8 | 2026-10-08 | 完成。`bento_chart.py`：一条折线或几根柱，线宽 0.12u，一个高亮、一个数值标注，没有网格和刻度。研究模式的数字格：`uncertainty` 画成"42.3 ± 0.3 s"（± 那段 0.5 倍字号），`n` 与 `condition` 画成标签下面一行；没有不确定度时，必须写 `exact` 或 `n: 1`，否则 `validate_spec` 报错。出处行只在使用者要求时出：占下边距一条，0.75u，下边距加高到 2 × 0.68u + 0.75u，排版和自检都按加高后的边距算。`cutout.swift` 用 Vision 的前景蒙版，咖啡样图抠出前景 47.5%。研究版样例 `research-3x4.json` 是 3:4、浅色、12 格，19 项自检全过，排版存成 `research-3x4.layout.json`；研究版成图和抠图前后对比已发给使用者。73 条测试通过 | 研究版用 `screen`（1536×2048），没用手机：研究格多出的那行让五个数字格最窄要 10u，手机 3:4 左右两栏只有约 8u，排不出来。<br>全尺寸渲染耗时没用原型的 18 秒：那是单次计时，原型也已不在，没法重测。改用本库 photo-cinematic-grade 0.3.0 在本机连跑 5 次的结果，42.3 ± 0.3 s，峰值内存 0.89–1.07 GB；原型那条记进 `dropped`。规矩多了一条：只测了一次就写 `n: 1`，照实画出来，不编不确定度。<br>数字格里的照片（`fit: cover`）贴着格边出血；照片放在数字下面时，排版器不让它被压成细条，太矮就换宽格、左右并排。<br>中文间距检查不再要求全角标点两边加空格（"n = 12，室温"）。<br>本轮清单以外改了 `bento_layout.py`（按画出来的标签和数字算格子大小，出处行的下边距）、`bento.py`（`plan` 显示 ± 和第二行）、`templates/bento.html`（± 字号、出处行、图表）。<br>接口加了 `tokens_for`、`display_label` 和 `exact`、`chart`、`highlight_label` 三个字段；`label_pos` 只收 top、bottom |
| 9 | 2026-10-08 | 完成。`SKILL.draft.md`（18 KB）；四份 references 由 Sonnet 子代理起草、主会话通读改过：apple-measurements 13 KB、bento-json 20 KB、tile-kinds 12 KB、label-grammar 6 KB。`tests/cases/bento-infographic.md` 14 条。`examples/` 三份：产品浅色、产品深色（1920×1080）、研究 3:4（1080×1440），`qa.json` 全过，共 2.1 MB。AI 腔词表只剩 label-grammar 里故意举的坏例子"一站式"。74 条测试通过 | 对照用例时发现两处缺口，都补了：一，"未确认的数字在图上看得出来"没落到代码上，现在 `validate_spec` 要求标签里写"未确认"；二，SKILL 里少了"图上没有标题页脚""竖版不塌成一列""长说明进交付说明""同一种子同一方案"几句。<br>为了让降级一节写得出来，补了两处代码：按 `BENTO_CHROME`、Mac 默认位置、PATH 依次找 Chrome；`render --html-only` 不要 Chrome，只出 HTML。<br>样例画布缩成 1920×1080 和 1080×1440：4K 的 PNG 每张 1.1 MB，库里别的 examples 最大 248 KB。<br>子代理核对出 16 处计划和代码对不上：最小格高、`hero_area`、`flank` 的字段、图标的重点色没生效等。代码的毛病（图标重点色）放到第 10 轮修，计划的文字已同步。<br>本轮清单以外改了 `bento_spec.py`（未确认规则）、`bento_render.py` 和 `bento.py`（找 Chrome、`--html-only`）、`test_bento.py` |
| 10 | 2026-10-10 | 通过（第 6 次）。前五次独立评审（每次新开一个 Sonnet 代理，同一份材料、同一段提示）平均分 7.7、7.7、7.3、7.7、7.7，按规则停在第 10 轮写了交接；使用者看过后要求接着改（2026-10-09"继续做这个技能，争取做完"），第 6 次评审 **8.1**：字体 8、字号层级 8、主图 8、格子与留白 8、颜色 9、文案 9、整体 7。<br>前五次的分项（字体 / 字号层级 / 主图 / 格子与留白 / 颜色 / 文案 / 整体）：第 2 次 8/8/7/8/8/8/7；第 3 次 8/7/7/7/8/7/7；第 4、5 次都是 8/7/8/8/8/8/7（第 1 次字体 9、字号层级 7、主图 8、格子 8，其余没记全）。<br>第 6 次改了什么（按第 5 次评审的四条，都量过属实）：截图格标签默认放下面（苹果多数在下）；单色底的图（片子、公式）铺成一张卡填满图区，卡和格同色时改用 `raised` 色（深色 #1c1c1e、浅色 #f2f2f7）并把图叠上去，深色版的黑卡不再消失，边看不见的深色语录卡垫一层框；排版器给整张放的截图按比例分格、浅色画布上同一条带里深色格最多一个、`weight` 3 的纯文字格不再抢最大的格；产品版「pptx」提到 2.6u、研究版「4.4°」提到 4.3u，各留一个大字；同类元素同色（产品版数字和图标都上蓝，研究版数字和柱图高亮上蓝）；研究版数字下面的照片缩进 1u 加圆角，去掉硬缝；功能名的下伸字母让开标签；图标按墨迹居中；几条标签改成名词短语。<br>收尾状态：74 条测试、`validate.sh`、`run-selftests.sh bento-infographic` 通过，三份样例 QA 全过（研究版提醒主图放大 1.36 倍，预期之内）。和苹果样图并排的对照图留在会话临时目录，没入库（里面有苹果素材） | 第 6 次评审还点了（留给 0.1.x）：一，铺到格边的格偏少（产品版 3/14、研究版 1/12，苹果 31–53%），组图和调色前后对比都是"白卡里嵌小图"，可改成整格铺满、白字压图；二，一个词的主图用了产品图的大小（面积 23%，苹果一词主图约 12%），底图仍偏平，「Skills」笔画比 iOS 粗约 12%；三，研究版蓝色数字偏多（6 个），顶置数字离格顶只有 0.93u（苹果 3000 nits 约 2.3u），四个图标是黑的而产品版是蓝的；四，图底到下方标签只有 0.59u（苹果同类约 1u）；产品版有三个 222 px 的同宽窄格；五，调色前后对比两半太像（平均差 4.5/255），浅色版跨页版面的页边线像线框；研究版主图是放大过的样图，偏软。<br>校准对（不计分）：u、圆角、格缝、主图框、标签字号已对上；差在带和栏内部的切分（5–9%）、Vapor chamber 一组没做光学居中、同一档字号苹果有约 6% 的浮动、圆角和外边距比官方小约 5%。 |
| 11 | 2026-10-10 | 完成，Library 0.23.0 → **0.24.0**（新增 skill 记 MINOR），技能数 62 → 63。<br>`S/SKILL.draft.md` 改名 `S/SKILL.md`（category 按同类写成 `coding-helper/ui-design`，变更记录 0.1.0）；`SKILL_INDEX.md` 登记 `bento-infographic`（P1、draft、0.1.0），`launch-summary-panel` 改 deprecated 0.1.2；`plugin.json`、`marketplace.json` 0.24.0；README 加本 skill、旧的那条改成"已废弃"，skills 徽章 63；`CHANGELOG.md` 0.24.0 一节。<br>`launch-summary-panel` 0.1.2：`status: deprecated`，description 与正文开头写明改用本 skill，提示语也改了；用例文件开头注明已废弃。<br>`keynote-deck-builder` 0.8.1（只改文档，按使用者说的不测 keynote）：第 41 行改指本 skill；研究文件第 10 节"8–12 格"降为 C 档并写明出处的问题；正文那条格数规则原来引的就是这一行，一并改成按投影字号说理。<br>清单外多改了一处：`photo-spread-composer` 第 51 行也在推荐 launch-summary-panel，改指本 skill，记 0.1.2（PATCH）。<br>样例的数字换成发版后的现数：技能 63；测试用例改数 "## Case" 条数 429，因为每个 skill 必有一个用例文件，数文件就和技能数重复了。 | 验证：`validate.sh` 通过（63 个 skill，0.24.0）；`run-selftests.sh` 除 keynote 外 27 个自检全部通过（第一遍本 skill 有一条测试还写死旧数字 62，改成从样例读数后通过）；`package.sh` 重打 bento-infographic 0.1.0、keynote-deck-builder 0.8.1、launch-summary-panel 0.1.2、photo-spread-composer 0.1.2，旧版本的包由脚本删掉；`package.sh --check` 只剩 photo-cinematic-grade 0.4.0 没有包，那是另一条线的改动，它的变更记录写明暂不打单技能包，没动；本 skill 的包里没有苹果素材和 iPhone 调试样例。<br>没有提交，改动清单交给使用者。 |

### 4.13 已定的事（2026-10-07，第 6 条 2026-10-08 补）

1. **名字**：`bento-infographic`。
2. **launch-summary-panel 退场**：新 skill 发版时标 deprecated，下一版删（4.9 最后一条）。
3. **出处行**：默认不加，产品和研究成果都一样，和苹果的样图一致。数字的出处照样写进 `bento.json` 和交付说明。使用者要求加时，放在下边距一行，0.75u，对比度 ≥ 4.5:1，这是唯一可以小于 u 的字。
4. **磨砂渐变格**（样图 1，iPhone 16e）：第一版不做。它靠渐变和柔光，做不好就是 keynote 0.8.0 刚去掉的那种 AI 味。第一版过了验收，再评估要不要做成可选主题。
5. **字体**：默认系统字体（Mac 上是 SF Pro 与苹方），Inter 加思源黑体 / Noto Sans SC 兜底；PDF 只用兜底那一组（4.8）。
6. **样例**（2026-10-08 补）：产品样例不现编产品，以 iPhone 18 Pro 的官方宣传为准，做完和官方总结片对齐（样图 6）。这份样例只供调试本 skill，用了从官方图上裁的图片，留在 `tests/fixtures/`，不进 `examples/`，也不放到任何对外展示的页面上。对外的样例改用本库自己的真实内容（产品版）和调色原型的实测数字（研究版）。
