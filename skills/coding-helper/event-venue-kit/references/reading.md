# 实体长页系统 / The Long-Form Entity Page System

原站 52 张学校页，每页一份学生研究报告（3–12 章，最多 145 条来源），一页一个颜色，读起来像同一本书。这份文件讲这套系统：实体色、封闭的块词汇、编号章节、阅读导航、照片与署名、引用与来源、带限定语的数字、逐字内容、手机上的阅读尺度。

要带走的四件事：
1. **内容是数据，渲染器管全部审美。** 作者只能用 12 种"形状"，内容各异也像一本书，设计力气集中在 12 个部件上。
2. **实体只有一个很小的主题接口**：一个输入色，派生若干角色；其余全部冻结。
3. **阅读导航分"契约"和"呈现"**：契约永远要有，呈现可以随方向抽牌换。
4. **数字有限定语，来源有固定位置，文字不改写。**

"原站" = 原站取值 / source value，是一个实例；"可换"是真选项。

## 1. 何时使用 / When

- 每个实体有一篇长内容：研究报告、展商介绍、艺术家页、展品说明、议程详情。
- 实体只有名字、房号、一句话时，`evk-entity-head` + `evk-strip` 就够，跳过 §3–§7。起步页（`ux-contracts.md` §17）是这一档的起点：`venue.json` 里 `entity.blurb`、`entity.facts`、`entity.parts` 是 §3.1 形状的最小子集，`entity.blocks` / `parts[].blocks` 是正式的块列表（12 种封闭词汇，§3.1），`scripts/starter.py` 在构建期把它们写成实体页（对照见 §3.1 末）。内容要时间表、问答、卡片、表格时，写成块，不要自己另起一套渲染。
- 内容量级差 20 倍，两端都要测：章 3 / 12，来源 0 / 145，数字条 3 / 4 项，名字 3 / 14 字符（floor F19）。

## 2. 一个实体一种颜色 / One colour per entity

### 2.1 角色

| 令牌 | 原站名 | 是什么 | 用在 |
|---|---|---|---|
| `--e` | `--school` | 填充，保持输入色 | 色带、条、步骤方块、卡片顶边、小方块符号、数字卡顶线、进度线 |
| `--e-text` | `--school-text` | 纸上的字版 | 名字、数字、引语、Q 标、表头字、引用上标、当前项 |
| `--e-on` | `--on-school` | 填充上的字 | 步骤数字、访谈带里的字 |
| `--e-soft` | `--school-soft` | 10% 淡底 | 卡片底、图片占位、`:target` 高亮、按下的 chip |
| `--e-line` | `--school-line` | 45% 线色 | chip 边、注记左线、时间线脊 |
| `--e-dk` | `--school-dk` | 深色里的字与填充 | 深色下两者合一 |
| `--e-soft-dk` | `--school-soft-dk` | 22% 混入夜 | 深色淡底 |

`base.css` 只给三个别名 `--e-fill / --e-ink / --e-tint`（浅色 = `--e / --e-text / --e-soft`，深色 = `--e-dk / --e-dk / --e-soft-dk`），组件只写别名。线色的深色处理由 recipe 定（原站深色里线退回中性 `--rule`）。

### 2.2 注入

- 一行内联样式放在实体根元素上（`EVK.applyEntity(el, hex)`，或构建期写出）；组件不知道"实体"的存在；新增一个实体不写一行 CSS。
- 写回落值 `var(--e, var(--a))`，没登记颜色的实体退回方向自己的结构色。
- 可换：`[data-entity]` + 每实体一小段 CSS（允许个性）；构建期生成每实体样式表；运行时从徽章取色（不推荐，没有对比度保证）。

### 2.3 算法（`scripts/tones.py` 与 `EVK.tones` 同输入同输出）

- **字版**：套件默认保持色相与彩度，按 OKLCH 亮度 0.01 一步变深，停在第一个 ≥ 4.6:1（对纸）的位置。原站是朝页面墨色按 1% 一步混合（`tones.py --method mix` 复现，下面的原站实例就是这种算法的结果）。
- **深色字版**：同色相提亮（套件默认 OKLCH 步进；原站 HLS 提亮、饱和度封顶 .62），停在第一个 ≥ 4.6:1（对夜）；已够亮的不动。
- **填充**：保持输入色；仅当纸字与墨字在其上都 < 4.6 才朝墨色压暗（原站 52 色里这道保险一次没触发）。
- **反白字**：纸与墨里取对比更高者（Caltech 橙上用墨字 6.33，其余 48 个用纸色）。
- **淡底 / 线 / 深色淡底**：10% 实体色 + 90% 纸；45% + 55%；22% 实体色 + 78% 夜。
- 原站实例：Caltech `#FF6C0C`→字 `#B45111` 4.67；UCSD `#09A7C8`→`#0D7991` 4.63；Princeton `#E77500`→`#AA5A08` 4.62；UNC `#7BAFD4`→`#52728B` 4.66。深色：UChicago `#370404`→`#DA6060`，Harvard `#A51C30`→`#D95E70`。48 个深色结果都落在 4.60–4.76，"刚好够"。
- 目标 4.6、步长 1%、混合比例是参数，可换；"算出来、有测试"不可换。

### 2.4 颜色从哪来

- 原站：取自各组海报的主色，偏深偏稳（HLS 亮度中位 .255，蓝系 19 个），只有 4 个亮色。进系统前"向墨靠拢"，整站看起来像墨，不是糖果。
- 可换：官方品牌色；从实体照片取色；OKLCH 固定亮度与彩度、只转色相（最和谐）；把亮度钳进一个带内。
- 撞色（JHU 与 Duke 都是 `#1B3761`）：身份不能只靠颜色，名字和徽章必须在场。

### 2.5 两层意义，两种颜色

- 活动层强调色 = "这是活动 / 去做"；实体色 = "这是它"。一块里不同时放两个高饱和色，也不把活动强调色铺成实体色面。
- 原站：实体页上的红只剩活动层（房号带、按钮、焦点环）；桌牌条的红色短尾换成中性金（`#A98B5F`，深色 `#CDB38A`，章号同色；2.94:1，只作冗余装饰）。
- 可换：活动层用中性墨色（下划线），颜色全让给实体；活动层用形状（切角）；用一个与任何实体色都不冲突的强调（荧光黄）。

### 2.6 访谈带：整页唯一一次反相

- 做法：容器 `.is-interview` 上重定 9 个令牌：标题色、次级色、`--e-text`、金属点缀、`--e` 五个一律指向 `--e-on`；`--rule`、`--e-line`、`--e-soft` 改成纸色的 28% / 45% / 10% 透明；`--paper` 改成实体色（宽表里粘住的首列因此不会露底）。里面所有块自动反白；次要字用 `opacity:.82`，不再引入新灰。
- 例外补丁：卡片顶边、方块、时间线、列表符号用 `currentColor`；步骤方块反过来（底 on，字 fill）。
- 手机出血，≥ 760 回到版心内、内边距 32；深色里**不跟随**（仍用输入色，靠色相差活着）。
- 位置：最后一个正文章。把阅读从"资料"切到"人说的话"；稀有才有分量，每页至多一次。进入前先用一条 `note` 声明"以下为个人体验 / 访谈补充，保留原意，供与官方资料对照"。
- 风险（推算）：纸色 @ .82 叠在填充上，Cornell 4.56 勉强过，LSE 3.75、Brown 4.30、Imperial 4.43 会不过。原站只有 3 页用，没出事；你的实体用到时逐个测。
- 可换：浅色反相（淡底 + 墨字，不需要推导对比）；语录墙；聊天气泡；左右分栏 Q | A；音频卡。

### 2.7 测试（对每个实体）

`--e-text`/纸 ≥ 4.5；`--e-dk`/夜 ≥ 4.5；`--e`/`--e-on` ≥ 4.5；用访谈带的再测 `--e-on @ .82`/`--e`；深色里 `--e` 对夜 < 3:1 的列出来，看截图（floor F04–F05）。

## 3. 封闭的块词汇 / The closed block vocabulary

### 3.1 数据形状

```json
{ "title":"…", "lede":"一句话", "stats":[{"value":"1636","en":"Founded","cn":"创立","note":"约"}],
  "facts":[{"k":"类型","v":"私立研究型"}],
  "parts":[{"en":"Overview","cn":"基本情况概述","kind":"main|interview|intro",
    "blocks":[{"t":"p","text":"…"},{"t":"cards","items":[{"title":"…","meta":"…","text":"…"}]},
              {"t":"sub","title":"…","fold":true,"blocks":[…]}]}],
  "sources":{"intro":"资料访问日期与说明","items":["[1] …"]} }
```

数据里双语仍是 `en` / `cn` 两个键；显示顺序由 `lead` 定（`<html data-evk-lead>`），渲染器把 lead 语言写在配对的第一个子元素里（`ux-contracts.md` LD）。
块：`p note quote list facts cards steps table timeline numbers qa sub`（原站的 12 种；`venue.json` 里 `sub` 拆成两样，见下：`fold` 与块的 `title`）。构建期校验：数字条 ≤ 4；必填字段；表格每行列数 = 表头；`sub` / `fold` 嵌套 ≤ 2；报错指出文件与位置。块类名 `evk-r-<块>`（`base.css` §9b 画结构，只用令牌；配方在各自文件末尾加性格，旋钮 `--r-gap`、`--r-card-min`、`--r-card-top`、`--r-card-radius`、`--r-badge-r`、`--r-node`、`--r-node-r`、`--r-at`、`--r-quote-bar`、`--r-leading`）。

**`venue.json` 里的形**（`entity.*`，全部可选，类型见 `assets/engine/venue.schema.json`；`text` = 字符串或 `{en, cn}`），起步页读它们：

| `venue.json` | 对应上面的 | 起步页怎么写 |
|---|---|---|
| `blurb` 一句话 | `lede` | 名字下一行（`.evk-entity-line`），lead 语言在前 |
| `facts [{n, unit, label}]` | `stats`：`n` ↔ `value`，`label` ↔ `en` / `cn`，`unit` 是数字后的小字 | `.evk-strip` 里每项一个 `.evk-num`（说明在前、数值在后，`starter.css` 倒置）；`n` 原样印、不折行；没有 `facts` 就没有数字条 |
| `parts [{title, text, blocks?}]` | `parts`：`text` 是一段或一组段（`p` 块），`blocks` 是章内的块 | 每项一个 `<section class="evk-part" data-part>`，编号 `01…`；≥ 3 节（含末尾的"在哪"）加页内目录（无 JS 回退），阅读导航由 `part-nav.js` 自动挂 |
| `blocks [{type, …}]`（页面级） | 没有"章"的块列表 | 带 `title` 的块自成一章（进目录与阅读导航）；没有 `title` 的接在前一章后面，前面没有章就先立"简介 / About"；`parts` 的章在前，块生成的章在后 |

注意撞名：`venue.json` 的 `facts` 是**数字条**（对应 `stats`），不是下面 `facts` 块（`k` / `v` 键值行）。没有 `parts`、`blocks`，也没有 `blurb` 时，起步页写一节标"示意 / Placeholder"的占位，不编内容；末尾总有一节"在哪"（小地图 + 路线链接）。最小形没有 `kind`、来源：限定语（年份、"约"）写进块的 `note` / `label` / `unit`（§8）；`intro` 章与来源脚注、访谈带不在 `venue.json` 里，由你的渲染器接手。

**`blocks` 里的 12 种块**（`{type, …}`，`type` 也可写成 `t`；每个 `text` 是字符串或 `{en, cn}`；任何块可带 `title`：在章内是一行小标题，在页面级是新的一章）。模式在 `venue.schema.json` 的 `$defs.readBlocks`，起步页的实现与报错在 `starter.py` 文件头：

| `type` | 字段 | 标记（`base.css` §9b 画它） |
|---|---|---|
| `p` | `text`：一段，或一组（每项一段） | `<p class="evk-r-p">` |
| `note` | `text`；可选 `title` | `<aside class="evk-r-note">`：安静的声明（核验日期、适用范围，§8） |
| `quote` | `text`；可选 `by` | `<blockquote class="evk-r-quote">…<cite class="by">` |
| `list` | `items: [text]`；`ordered` | `<ul>` / `<ol class="evk-r-list">`；做事的顺序用 `steps` |
| `facts` | `items: [{k, v}]` | `<dl class="evk-r-facts"><div><dt>…<dd>` |
| `cards` | `items: [{title, meta?, text?}]` | `<ul class="evk-r-cards [is-short\|is-long]"><li>`；短 / 长按最长文字定（§3.2） |
| `steps` | `items: [text 或 {title?, text}]` | `<ol class="evk-r-steps">`，方块计数器 |
| `table` | `caption?`、`head: [text]`、`rows: [[text]]`（每行与 `head` 等长） | `<div class="evk-r-table" role="region" tabindex="0" aria-label>`，宽表横滑 |
| `timeline` | `items: [{at, text, title?}]`；`at` 是 `"10:30"`、年份或一个 `text` | `<ol class="evk-r-timeline"><li><time datetime>`（`HH:MM` 才写 `<time>`） |
| `numbers` | `items: [{value, label, note?}]`（2–6 个）；起步页也认 `n` 与 `unit`（数值后的小字） | `<ul class="evk-r-numbers"><li><b>数值</b><span>说明</span>` |
| `qa` | `items: [{q, a}]` | `<dl class="evk-r-qa"><div><dt>…<dd>` |
| `fold` | `title`、`blocks`、`open?` | `<details class="evk-r-fold evk-fold">`；里面再放一层 `fold` 为止 |

例（时间表与问答，双语写法）：

```json
"blocks": [
  { "type": "timeline", "title": {"en": "Today", "cn": "今天"},
    "items": [{ "at": "10:30", "text": {"en": "Kite launch", "cn": "风筝放飞"} },
              { "at": "14:00", "text": {"en": "Clay workshop", "cn": "陶艺工坊"} }] },
  { "type": "qa", "title": {"en": "Questions", "cn": "常见问题"},
    "items": [{ "q": {"en": "Do I need a ticket?", "cn": "需要票吗？"}, "a": {"en": "No.", "cn": "不需要。"} }] }
]
```

坏块让构建失败并指明位置（"entity kelp: blocks[2] (timeline) item 1 has no 'at'"）。起步页的行为边界（写块时留意）：`numbers` 的 `note` 它不印（把限定语写进 `label`，或 `unit`）；`qa` 的 `a` 它只印一个 `text`（一段；多段就拆成几个 `p` 块）；块里的另一种语言是第二行，淡色。别往 `venue.json` 里塞来源脚注和访谈带这类还没有块形状的东西。

### 3.2 块 → 外观（原站取值）

表里的块在页面上是 `evk-r-<块>`（`base.css` §9b 画结构，配方加性格，见 §3.1）。`sub` 在 `venue.json` 里是块的 `title`（一行小标题 `.evk-r-title`，样式在起步页的 `starter.css`）或 `fold`；原站的"顶层前缀实体色方块"那一手要在配方或项目样式里补。

| 块 | 结构与数值 | 布局由什么决定 |
|---|---|---|
| p | `.part-body` 1.02rem / 1.85，≤ 40em，段间 .75em，`strong` 取标题色 | — |
| sub | 标题 700 1.1rem / 1.5，顶层前缀 .5em 实体色**方块**，第二层 1rem 字版色；间距 2.1em / 1.5em；`fold:true` 变折叠 | 最多两层 |
| note | 左 2px `--e-line`，.86rem / 1.7，次级色 | — |
| quote | 左 3px `--e`，衬线粗体 1.18rem / 1.7 `--e-text`，`by` .8rem | — |
| list | `li::marker{color:var(--e)}`，`li+li` 间距 .35em | — |
| facts | `dl` 行 `grid: minmax(5.5em,7.5em) 1fr`，行距 9px，1px 行线；≥ 760 顶部要点两栏（间距 40） | 标签列宽用 em |
| cards | 淡底 `--e-soft` + 顶 3px `--e`，内边距 15/16/14，标题 700 1rem / 1.45，meta .76rem `--e-text`，正文 .93rem / 1.75 | **最长文字**：≤ 40 字 `is-short`（手机也 2 列）；> 220 字 `is-long`（始终 1 列）；默认 3 列当 ≤ 120 字且个数是 3 的倍数，否则 2 列；手机 1 列、≥ 700 为 2 列、≥ 1100 才 3 列 |
| steps | 30×30 方块计数器（`--e` 底，`--e-on` 字，slab 700 .95rem），左内边距 44 | — |
| table | `caption` .8rem；行线 1px，表头线 2px `--e`，表头 700 .8rem `--e-text`；无竖线无斑马；容器 `tabindex=0 role=region`；≥ 4 列 `min-width:620px` 且首列 `sticky; background:var(--paper)` | 宽表横滑，不缩字 |
| timeline | 脊 1px `--e-line` 在 `left:4px`；节点 9×9 方块，`top:.55em`；年份 slab 700 1.2rem `--e-text` | 线穿过方块中心 |
| numbers | 2 列，≥ 700 `auto-fit minmax(150px,1fr)`；每项顶 2px `--e`；数值 `clamp(1.45rem,6.4vw,2rem)` `--e-text`；说明 .8rem | 数值是自由文本（中文数词、区间） |
| qa | 问：粗体，前置 slab "Q"（1.2rem，`--e-text`，`aria-hidden`）；答：缩进 `calc(.7em + 12px)`，对齐问句首字；`.qa + .qa` 顶 1px 线、间距 1.4em / 1.2em | 只标"问" |
| 折叠 | 原生 `<details>`，summary `min-height:54px`，提示"展开 / 收起"（.74rem，`--e-text`）+ 边框画的箭头；相邻折叠 `margin-top:-1px` 合线 | 长列表、整段深度内容默认收起 |
| 行内 | `**粗**`；裸 URL 自动成链接（不吞结尾标点，含 `）)，。、；：`）；`[3]` `[3-5]` `[1,2]` → 上标引用，不存在的编号降级成无链接上标，未配对的 `**` 丢弃 | 对异常输入降级，不报错 |

原站用量（52 份）：p 3775 · sub 2474（折叠 311）· cards 677 · numbers 248 · list 244 · table 213 · facts 88 · note 86 · timeline 45 · steps 31 · quote 19 · qa 5。

### 3.3 为什么封闭

- 作者只能挑形状，所以内容各异也像同一本书；设计力气集中在 12 个部件上。每种内容"形状"有自己的部件：日期表 → 时间线，一串数字 → 数字卡，访谈 → 问答。
- 全部由同五样东西搭成：实体色条或线、淡底、slab 数字、方形记号、1px 线。
- 可换：只用 6 个块（p / list / table / figure / quote / callout）；MDX + 自由组件；每个块类型一套独立主题。

## 4. 章节：编号、章头、粘性 / Parts

### 4.1 三种章与两套计数

- `kind`：`main`（正文章）、`interview`（访谈章，仍编号）、`intro`（说明章：报告说明、数据口径，不编号，字 .92rem 次级色）。
- 显示编号只数 main 与 interview（`01`…）；锚点 `id="part-N"` 数全部章，所以导航线数 = 章数（要有测试）。
- 原站章数：main 227、intro 8、interview 3。

### 4.2 章头

- 原站：一条 1px 线开头，`margin-top:56`（≥ 980 为 88）→ 大号章号（slab 700 `clamp(2.4rem,11vw,3.4rem)` / .9，中性金，对齐数字，**跨两行**）+ 英文小标签（.66rem / .18em 全大写，次级色，取自一个很小的固定词汇：Overview、Academics、Other Resources、Admissions、Interview、Scope、Data Notes、Takeaway）+ 中文标题（衬线 700 `clamp(1.4rem,5.6vw,1.9rem)` / 1.3，+.04em，标题色）。整个章头约 80px 高。
- 契约内的标记：`<section class="evk-part" data-part id="part-N"><header class="evk-part-head"><span class="no">01</span><span class="evk-k">…</span></header>…`。章头标题是一个双语配对：lead 语言写在第一个子元素，角色层按位置分主辅（`lead=en`：英文小标签 + 中文标题，即上面的原站排法；`lead=zh`：中文标题为主，拉丁眉标退成 ≥ 11 px 的小标签）。别把"小标签"写死在 `.en` 上。
- 可换：章号在标题右侧；超大"幽灵"数字压在标题后；整行色带做章头；眉标两侧拉线；罗马数字；只有标题、章号放页边。

### 4.3 桌面粘性左栏（≥ 980）

- 原站：`.part` 变两栏 `250px | 1fr`，间距 56，章头 `position:sticky; top:84px`（栏高 62 + 22 空气），`max-height:calc(100vh − 110px); overflow-y:auto; scrollbar-width:thin`（小节多时栏自己能滚），章号 3.6rem；正文 ≤ 40em。
- 可换：顶部粘性横栏；右侧细竖导航；章头不粘、只在章首放目录；手风琴章。

### 4.4 小节导航（章内 ≥ 3 个顶层小节才生成）

- 手机：出血的横向 chip 带（`margin:14px -20px 0`，`ol` 内边距 `0 20px` 让首项对齐页边，隐藏滚动条）；chip `padding:6px 12px`，1px `--e-line`，.82rem，不换行，直角；按下 `--e-soft`。出血本身就是"可横滑"的暗示，不需要箭头。
- ≥ 980：同一组链接变成粘性栏里的竖列：顶 1px 线，每项 `padding:7px 0 7px 12px`、底 1px 线、左 2px 透明；当前项左线变 `--e`、字变 `--e-text`；与章导航共用同一条阅读线（§5.4）。
- 原站缺口：手机上 `.is-on` 没有样式，chip 没有"当前"状态；你的版本补上（加粗或底色）。
- 可换：下拉 `select`；tab 切换而非滚动；圆点。

### 4.5 编号按尺度换样子

章 `01`（金色 slab）· 目录序号（加宽小字 `--e-text`）· 步骤（方块里不补零的数）· 问答（字母 Q）· 来源（方括号 `[3]`、上标）· 时间线（真实年份）· 数字卡（数值本身）。每个尺度一种样子，读者不会把"章 01""步骤 1""来源 [1]"混在一起。可换：全站一种编号；字母与罗马数字分层；只在最高层编号。

## 5. 阅读导航：契约与呈现 / Reading navigator — contract vs presentation

### 5.1 契约（不随方向变）

| # | 契约 | 怎么验 |
|---|---|---|
| N1 | 页面上**常驻**一个"我在第几部分"的指示，不靠滚动条 | 滚到三处，每次都能指出来 |
| N2 | **一步**跳到任一部分 | 点一下列表项就到 |
| N3 | 已读 / 未读 / 当前**不只靠颜色**（长度、粗细、标签、字重至少再占一个通道） | 灰度截图 |
| N4 | 进度**在文末之前**就满 | 滚到来源前，进度已 100% |
| N5 | 无 JS 时有一份完整章节列表 | 关 JS |
| N6 | 键盘与读屏可用：按钮 `aria-expanded` / `aria-controls`，标签随状态变，Esc 关闭并还焦点，打开时焦点落在当前项 | 键盘走一遍 |
| N7 | 锚点跳进折叠内容时**先展开再滚动** | 点引用 |
| N8 | 当前章按**一条阅读线**判定，不按元素顶部 | 见 §5.4 |
| N9 | 只在状态变化时写 DOM；滚动与缩放合并到一帧；被动监听 | 性能面板 |

章数 < 3 时建议整个导航不显示（只留章节列表）。

### 5.2 `EVK.partNav(root)` 与原站的面板

`EVK.partNav` 按 `[data-part]` 建出：每章一条线、当前线更长且用实体色、已读线上墨色、栏下进度线（`--p` 0..1，`scaleX`，无 transition）、点开的章节面板，Esc 与点外面关闭，打开 `<details>` 祖先。原站面板的做法可当蓝本：锚在按钮上，宽 `min(360px, 100vw − 24px)`，顶 4px `--e`，`max-height:calc(100vh − 90px)`，行 = 序号 + 标题 + 副语小字（`EVK.partNav` 按章头配对的顺序生成：lead 语言在上、较粗，另一种在下；每行带 `.cn` / `.en` 与 `lang`，`data-title` / `data-title-cn` 可覆盖章头文字），当前行左 3px `--e` + 淡底，底部"Back to top 回到顶部"；按钮标签 `报告目录，正在读第 N 部分，共 M 部分`。呈现由 CSS 决定：`.evk-lines`（里面每章一个 `<i>`）、`.evk-progress`；状态类名沿用原站 `is-done`、`is-on`，以 `assets/engine/part-nav.js` 文件头为准。面板与按钮的界面字串随 `<html lang>`，页面没有 lang 时随 `data-evk-lead`；改 lead 之后要 `destroy()` 再 `EVK.partNav()` 重建一次，目录才会重排。

### 5.3 五种呈现（方向的 `nav` 参数选一个）

除 lines-top-left 外，其余四种原站没做，是按同一份契约推出的做法；先做原型再信。

| 呈现 | 几何 | 三种状态怎么编码 | 手机上 | 适合 |
|---|---|---|---|---|
| **lines-top-left**（原站） | 栏左上的按钮 42×42，里面 26×30 的一列线：未读 12×2px 次级色 .45；已读 12px 墨色；当前 26px 实体色；线距 4（> 6 条时 2px 距、1.5px 高）。图形落在 20px 页边上（`margin-left:-8px`，点击区向外扩） | 长度 + 墨 / 色 + 不透明度 | 同 | 厚重、编辑部、校徽类 |
| **side-ticks** | 视口右（或左）边缘的竖向刻度，每章一格；当前格更长更粗 + 标号，点或悬停展开标签；点击区 ≥ 44 | 长度 + 粗细 + 当前显示标号 | 贴边会与系统返回手势冲突：留 ≥ 16px 内缩，或改在栏内 | 海报、建筑图纸、仪表 |
| **tab-strip** | 栏下一条可横滑的编号 tab（`01 02 03` + 短标题）；当前项 3px 下划线 + 字重；当前项自动滚入视野 | 下划线粗细 + 字重 + `aria-current` | 本身就是手机形态；注意它是第二条粘性栏，总粘性高度算进 `scroll-margin` | 车票、交通导视、登机牌 |
| **progress-ring** | 栏里实体徽章或章号外一圈分段环（n 段，段间留缝），中心 `02/05`；点开同一个面板 | 段的粗细 + 填充 + 中心数字 | 同；环直径 ≥ 44 | 徽章、印章、仪表类 |
| **chapter-rail** | ≥ 980 左侧竖栏：章号 + 标题列表 + 一条竖向进度脊（原站的粘性章头 + 小节竖列就是它的一半）；手机折回 lines 或 tab-strip | 脊上填充 + 当前行左线 + 字重 | 折叠 | 报纸、博物馆展板、图书馆卡片 |

不论呈现怎么变，面板、键盘、`aria`、阅读线、进度公式都不变；章数多时线与刻度要压缩（原站 > 6 条改 1.5px 高、2px 距）。

### 5.4 阅读线与进度的数学（原站）

- 阅读线 = 栏底 + 视口高 × **0.28**；当前章 = 顶部 ≤ 阅读线的最后一章；`is-done` = 序号 < 当前，`is-on` = 当前。小节导航用同一条线。眼睛停在上三分之一，不是顶边。
- 进度 `p = clamp((栏底 − 报告顶) / (报告高 − 视口高 × 0.6), 0, 1)`，`--p` 写 4 位小数；分母扣掉 0.6 个视口，让进度在最后一屏进入时就满。
- `current` 初值 −2（让第一次一定写）；`scroll` / `resize` 合并到一个 `requestAnimationFrame`；DOM 只在序号变化时写。
- 可换：`IntersectionObserver`（`rootMargin: -28% 0 -72% 0`）；占视口面积最大的章；CSS `animation-timeline: scroll()` 画进度线（不需要 JS）；"约 4 分钟读完"。

### 5.5 渐进增强与栏下细线

- `.partnav`、`.read-progress` 在 HTML 里带 `hidden`，脚本找到才显示并给 `<body>` 加 `has-report`；这时通用的"滚动后出现"细线隐藏，避免两条 2px 线叠在同一行。
- 无 JS 的导航：服务端渲染的目录列表 `ol.part-index`（2px 顶线、1px 行线，序号 `--e-text`、标题 slab 600 1.12rem、副标 .82rem，`min-height:60`，按下 `--paper-2` 无过渡）。

### 5.6 锚点跳进折叠内容

`openFor(hash)`：找到目标后沿 `closest('details')` 向上逐层 `open = true`，仅当真的展开过才 `scrollIntoView()`；在点击、`hashchange` 与首次加载三个入口都调用。测试：页面里每个 `href="#x"` 都有对应 `id`。`scroll-margin-top` 取栏高 + 8 到 24（原站 章 70 / 小节 76 / 来源 80）。

## 6. 照片与署名 / Photo breaks and credits

- **主图**：手机出血（`margin:22px -20px 0`），4:3；≥ 760 `margin-top:28`、16:9、`max-height:74vh`。`object-fit:cover`；`object-position:50% {focus_y}%` 逐图设（建筑、天际线的重点在哪就切到哪）；`width` / `height` 属性；`srcset` 720w + 1440w，`sizes="(min-width:1160px) 1080px, 100vw"`；主图 eager，其余 `loading=lazy decoding=async`。加载前底色 = `--e-soft`，不是灰。
- **分隔带**：插在第 2 章之前（序号 1）和约 2/3 处（序号 `max(2, round(2n/3))`，从 0 数；n = 2 只放一张，n < 2 不放）。`margin-top:56`；手机 3:2，≥ 760 变 21:9——换比例给长页换气，又不夺走注意力。每实体共 3 张。
- **无照片**：主图位放一条条纹或签名条，页面依然有头。
- **图注**：`figcaption` 两端对齐 `display:flex; justify-content:space-between; flex-wrap:wrap; gap:2px 14px`，.72rem / 1.5，次级色；左 = 地点（中 · 英，顺带科普，也是 alt），右 = `Photo: 作者 · 授权`，链接 `color:inherit`、1px 下划线用线色。**图出血，图注文字回到 20px 页边**（`padding:7px 20px 0`，≥ 760 `8px 0 0`）。
- **数据**：每张图的元数据 `file / page / author / license / license_url / subject_en / subject_cn / w / h / focus_y` 与图同生命周期，缺一个字段构建失败；只收 CC0 / PD / CC BY / CC BY-SA，来源页必须是图库的文件页（原站：Wikimedia Commons）；缩放算"改动"，在 NOTICE 里写明。
- 可换：视差主图；双色调（实体色）照片；徽章形状蒙版；轮播；图上角标署名；点开 ⓘ 显示署名；正文间用大号引语或色带代替图片分隔。

## 7. 引用与来源 / Citations and sources

- **正文里**：上标 `[3]`，`font-size:.62em; line-height:0; vertical-align:super`，无下划线，`--e-text`。`line-height:0` 才不会撑开 1.85 的行距。
- **来源页脚**：`<footer><details id="sources"><summary>Sources 资料来源 + 计数</summary>…</details></footer>`；顶 1px 线，`margin-top:64`，.8rem / 1.65，次级色；summary `min-height:48`，计数 slab 600；条目 `padding:5px 0`、顶 1px 线、`overflow-wrap:anywhere`、`scroll-margin-top:80`；`li:target{background:var(--e-soft)}`。没有条目时 `details` 直接 `open`（只留说明）。
- **开头一句"访问日期与口径"**：例"以下资料均于 2026-10-17 访问；网页未标注发布日期者以访问日期计；院系页与正式课程目录不一致时优先参考课程目录。"
- **条目格式**：选一个国家标准或学科惯例，全站统一；原站用 GB/T 7714 电子文献式 `[1] 机构. 题名[EB/OL].(发布日)[访问日]. URL`。
- 来源数 0–145：折叠后只占 48px，页面不拖尾；计数本身是严谨的信号。
- 可换：每章末一小组注释；桌面边注（sidenote）；悬停 / 点按弹出来源卡；二维码指向来源页。

## 8. 带限定语的数字 / Numbers with qualifiers

- **页首数字条**（`dl.stat-strip`，≤ 4 项）：DOM 顺序是标签、数值（读屏和语义正确），视觉用 `flex-direction:column-reverse` 把数值放在上面；`justify-content:flex-end` 让各格数值顶对齐。上 1px 线，每格 `border-bottom + border-left` 1px，首格无左线无左内边距（文字贴页边）。手机 2×2（3 项时 3 列），≥ 760 `repeat(var(--n,4),1fr)`，格内 `18px 20px`。数值 slab 700 `clamp(1.55rem,7.4vw,2.5rem)` / 1.05，`--e-text`，`lining-nums tabular-nums`，`overflow-wrap:anywhere`；标签英文 .58rem / .14em + 中文 .72rem；**说明 `small` .72rem 紧贴数值下方**。
- **正文里的数字卡**（`numbers`）：同一概念的"正文版"：线更粗（顶 2px 实体色）、数字更小。
- **限定语位置是契约**：数值 `value` 是自由文本（"第 31 名""1,510–1,560""两万四千余人"），`note` 放年份、"约"、截至、榜单与版本（"U.S. News 2027 版"）；表格 `caption` 写榜单名与年份；口径不同的来源并列时，写一章"数据口径说明"逐项对照，正文说明以哪个为主。
- **官方事实与个人经验分开**：每个"声明"有固定的安静样式（`note` 或 `intro` 章）：核验日期、适用对象、哪些是研究分析而非学校承诺、有没有做过实地访问。
- 原站缺口：相邻格一个有 `note` 一个没有时，标签行不在同一水平线；可接受，眼睛在读数字。
- 可换：一个超大主数字 + 三个小数字；横滑 chip；每个数字带迷你条；账本式（左标签右数字）；环形；数字在下标签在上。

## 9. 逐字内容纪律 / Verbatim-content discipline

当实体内容是别人写的（学生报告、展商自述、艺术家陈述）：

1. **文字全部用原文**；只允许删：封面、目录、写作模板提示语、分工、成员姓名、PDF 页眉页码，以及隐私删除。编辑动作是"选哪个块来呈现"，不是改写。
2. **逐条比对原文**（忽略空格与全角半角）：原文每一段在页面上都能找到，或有删去的理由；删除要列出来，不静默。
3. **再做一遍独立复核**：隐私、标签与数字口径、结构、遗漏。原站 52 份都过了这一遍，并因此删除了两段作者个人经历。
4. **结构跟着每份内容自己的章节走**（原站 3–12 章），不套四章模板；英文小标签取固定词汇，中文标题保留原话。
5. **受访者不具名**（"受访学长"）；人名、班级、小组、联系方式不进页面（floor F24）。
6. 内容里夹着写给作者的评审语气（"报告应注明具体年份"）：原文照排，但在交付说明里指出，由所有者决定，不要悄悄改写。
7. 内容是你自己写的（不是转载）：纪律变成"事实带限定语、意见标注为意见"。

## 10. 手机上的阅读尺度 / Mobile reading measures

| 项 | 原站取值 |
|---|---|
| 正文 | 1.02rem / 1.85；`max-width:40em`。375 宽减 40 边距 = 335px ≈ 20 个汉字一行；桌面 652.8px = 40 个汉字 |
| 其余行宽 | 摘要 34em、lede 36em、引言 32em |
| 块间距 | 全部用 `em`（1em–2.1em）随字号成比例；结构间距才用 56 / 64 / 88 |
| 字号层级 | 正文 1.02 · 卡片正文 .93 · 注记 .86 · 表格 .9 · 页脚 .8 · 图注 .72；小节标题只有 1.1 / 1 两档，层级靠方块与颜色 |
| 可点高度 | 章节列表行 60 · 折叠 54 · 来源 48 · 导航钮 42（低于线，新项目取 ≥ 44） |
| 出血 | 照片、房号带、访谈带、小节 chip 带出血；图注、chip 首项文字回到 20px 页边 |
| 表格 | 横滑 + 首列粘住 + 键盘可聚焦，聚焦环偏移 4px |
| 卡片列数 | 手机 1（短卡 2），≥ 700 2，≥ 1100 3，由内容长度决定 |
| 锚点 | `scroll-margin-top` 70 / 76 / 80；粘性头 `top:84` |
| 首屏顺序 | 眉标（区域）→ 名字 → 中文名 → lede → 主图；首屏不放大段正文（`lead=zh`：名字行是中文名，其后跟拉丁名；实体名 `h1` 是中文时自带 `lang="zh-CN"` 或 `.cn`，才会用中文展示字体与 0 字距） |
| 强调 | 加粗 = 变成标题色 + 变粗，松行距里只靠字重看不出 |
| 换行 | `line-break:strict`；不两端对齐；汉字间不留空白 |

可换：宋体正文（更文学）；行高 2.0；两栏正文（密集长栏）；更窄的 30em。

## 11. 从印刷物搬到页面 / From print to page

- 保留**阅读顺序与比例**，丢掉坐标：先看图、再看数、再看细节；首屏 = 眉标 → 名字 → 副语名 → 一句话 → 主图（原站副语是中文名），不放大段正文。
- 验收用三个可比较的量：颜色比例、字号层级、分区顺序；挑任意三张印刷物对比页面首屏，一致即可，不追求逐像素。
- 来源异质（原站 50 张海报：经典校刊 17、手工拼贴 15、现代机构 10）时，选**一个主骨架**，只从别的家族借部件，不借情绪。
- 数字条在页面里只出现一次，放首屏下方；访谈带最多一次；贴纸式点缀每页 ≤ 2 个、±2°。

## 12. 自检清单 / Checklist

- [ ] 每个实体：`--e-text` / `--e-dk` / `--e-on` 三项对比 ≥ 4.5；用访谈带的再测 @ .82；深色里 `--e` 对夜 < 3:1 的有边线或徽章环。
- [ ] 导航线（刻度、tab、环段）数量 = `[data-part]` 数量。
- [ ] 章数 3 与 12、来源 0 与 145、数字条 3 与 4 项都排过。
- [ ] `blocks` 十二种各排一次（两层折叠、四列宽表、最长一张卡片、`at` 是 `10:30` 与自由文本各一）；320 px 无横向页面滚动，表在自己的容器里横滑；一个故意写坏的块让构建失败并指出位置（`ux-contracts.md` EP-12）。
- [ ] 关 JS：章节列表仍可跳；开 JS：滚到三处，指示都对；点引用，折叠的 `<details>` 先开。
- [ ] 每个 `href="#x"` 有对应 `id`；`scroll-margin-top` ≥ 栏高 + 8。
- [ ] 灰度截图下，已读 / 当前 / 未读仍可分。
- [ ] 每张图有图注与授权；来源清单条数 = 图数；无个人信息（floor F24、F25）。
- [ ] 每个醒目数字旁有限定语位置；声明（核验日期、适用范围）有固定样式。
- [ ] 375 px 浅色与深色各看一遍：长表、长校名、长 URL、最长一节。
- [ ] lead 翻一次（en ↔ zh）：章头、目录面板、数字条、格子的主辅都对调，中文行都有 `lang` 或 `.cn`，不改 CSS。
