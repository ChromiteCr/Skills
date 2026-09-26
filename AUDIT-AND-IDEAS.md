# 审计与新 skill 提案 · 第二轮

生成日期 2026-09-24 · 库版本 0.22.3 · 已建成 61 个 skill

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

**怎么来的。** 六路按领域出点子（摄影；物理、建模与研究；编程与 AI；申请与社群；作词、写作与元技能；跨领域），共 46 条。三位评审各拿一个角度给每一条打 1–5 分并给判定（先做 / 以后做 / 合并 / 否决）：对你有没有用；脚本部分是不是真能算、能测；和已有 skill 或彼此之间重不重复。下面的"分"是三位评审的平均分，"先做票"是给"先做"的评审人数。重复的点子按评审意见合并，被合并掉的列在 E 节。电影感调色是你点名必须做的，不参与打分，完整方案见第三部分。

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

### F. 建议的先后

**先修第一部分的 A 节**，尤其 A1：插件装不上，新 skill 做了也用不上。然后第一批的 11 条按下面的顺序，括号里是前提：

1. **电影感调色 + `photo-render-color-fidelity`**。你点名要的；调色从第一版起就用 `image_io.py` 存片。之后接 `photo-export-prep`。
2. **`skill-release-steward`**（仓库脚本）。这一轮要新增一批 skill，每加一个都要动五六处地方，先有它，后面每次发版都有人记账。
3. **两个小的补脚本扩展**：`diff_risk.py` 与 `css_token_lint.py`。都是兑现已有承诺，工作量小。
4. **`model-fit-auditor` 吻合分级 + `experiment-sweep-planner`**。补上物理流水线"机制 → 数据"之间的空段，两条都有可算的内核。
5. **`essay-revision-coach` + Honors 扩展**（你今年申请的话，10 月内）。
6. **`contest-ai-use-ledger`**（下一场建模赛之前）、**navigator 签到台账**（下一次办活动时）。

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
