---
version: alpha
name: "Varsity '28"
description: "规范出口 / canonical exit：SDSZ College Fair 网站（一天、52 所大学、10 个展区、3 层楼）的完整视觉规格。班级年份像字母夹克上的号码一样被「穿」在身上：两种墨 + 暖粉笔白纸 + 板式衬线名字 + 加宽大写标签 + 切角 + 五段班级条纹。"
colors:
  primary: "#13294B"
  secondary: "#5B6270"
  tertiary: "#C8102E"
  neutral: "#F7F5F0"
  chalk: "#F7F5F0"
  paper-2: "#ECE8DF"
  stone: "#D8D3C8"
  ink: "#14171D"
  muted: "#5B6270"
  navy: "#13294B"
  red: "#C8102E"
  red-text-dark: "#FF7084"
  red-label-on-navy: "#FF8A99"
  climb: "#B45309"
  climb-dark: "#FBBF24"
  gold: "#A98B5F"
  night: "#0D1D36"
  night-sheet-tint: "#1E3A66"
  text-dark: "#EEEAE1"
  sub-dark: "#AEB6C6"
typography:
  display-hero:
    fontFamily: "Zilla Slab, Rockwell, Georgia, serif"
    fontSize: 9rem
    fontWeight: 700
    lineHeight: 0.86
    letterSpacing: -0.025em
  display-welcome:
    fontFamily: "Zilla Slab, Rockwell, Georgia, serif"
    fontSize: 4.7rem
    fontWeight: 700
    lineHeight: 1
    letterSpacing: -0.012em
  section-title:
    fontFamily: "Zilla Slab, Rockwell, Georgia, serif"
    fontSize: 1.65rem
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.006em
  row-title:
    fontFamily: "Zilla Slab, Rockwell, Georgia, serif"
    fontSize: 1.12rem
    fontWeight: 600
    lineHeight: 1.2
  numeral-stat:
    fontFamily: "Zilla Slab, Rockwell, Georgia, serif"
    fontSize: 4.4rem
    fontWeight: 700
    lineHeight: 0.8
    fontFeature: "'lnum' 1, 'tnum' 1"
  label-k:
    fontFamily: "Archivo Expanded, Helvetica Neue, Arial, sans-serif"
    fontSize: 0.74rem
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: 0.2em
  label-button:
    fontFamily: "Archivo Expanded, Helvetica Neue, Arial, sans-serif"
    fontSize: 0.76rem
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: 0.16em
  cn-gloss:
    fontFamily: "PingFang SC, Noto Sans SC, Hiragino Sans GB, Microsoft YaHei, sans-serif"
    fontSize: 0.66rem
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: 0.12em
  cn-display:
    fontFamily: "PingFang SC, Noto Sans SC, Hiragino Sans GB, Microsoft YaHei, sans-serif"
    fontSize: 1.3rem
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0.04em
  body-ui:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, PingFang SC, sans-serif"
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.7
  body-reading:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, PingFang SC, sans-serif"
    fontSize: 1.02rem
    fontWeight: 400
    lineHeight: 1.85
  cn-serif-title:
    fontFamily: "Songti SC, STSong, Noto Serif SC, serif"
    fontSize: 1.9rem
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 0.04em
rounded:
  none: 0px
  crest: 9999px
spacing:
  gutter: 20px
  shell-max: 1120px
  bar-height: 56px
  row-gap: 14px
  section-phone: 34px
  section: 46px
  part-phone: 56px
  part: 88px
  measure-reading: 40em
components:
  button-primary:
    backgroundColor: "{colors.red}"
    textColor: "{colors.chalk}"
    typography: "{typography.label-button}"
    rounded: "{rounded.none}"
    height: 46px
    padding: 0 22px
  button-secondary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.chalk}"
    typography: "{typography.label-button}"
    rounded: "{rounded.none}"
    height: 46px
    padding: 0 22px
  search-field:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    height: 48px
    padding: 0 14px 0 40px
  list-row:
    backgroundColor: "{colors.chalk}"
    textColor: "{colors.navy}"
    typography: "{typography.row-title}"
    height: 60px
    padding: 10px 2px
  welcome-panel:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.chalk}"
    padding: 44px 28px
  room-band:
    backgroundColor: "{colors.red}"
    textColor: "{colors.chalk}"
    padding: 26px 20px
  sheet:
    backgroundColor: "{colors.chalk}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    width: 400px
    padding: 6px 18px 16px
  crest-token:
    rounded: "{rounded.crest}"
    size: 30px
---

# Varsity '28 · DESIGN.md

> **规范出口 / Canonical exit。** 这是 `varsity` 方向（原站）的完整规格，**只在使用者明说要「College Fair 那个样子」或「同一家族的兄弟」时取用**；默认情况下 event-venue-kit 抽取其他方向，`varsity` 抽牌权重只有 0.15。
> 标「原站取值 / source value」的数是一个实例，不是默认；兄弟站哪些轴可动、动多少，见 Overview 的「近亲可变 / Sibling range」表；「(推算)」是本文件自己算的。地板规则（对比度、触控、焦点、减弱动效、隐私）与方向无关，见 `references/floor.md`；12 轴指纹见同目录 `fingerprint.json`。不含第三方素材：字体只写家族名与来源，校徽、照片、logo 不随包。

## Overview

*概览：它是什么，从哪里长出来，什么是身份，什么可以变。*

**一句话。** 班级年份像字母夹克袖子上的号码一样被「穿」在身上。一套自己的倒角块体数字既是 logo、门牌、统计数字，也是印章；其余是平的纸、细线和一条班级条纹。两种墨（红、深蓝）加暖粉笔白纸；板式衬线说「名字和数字」，加宽大写无衬线说「导视标签」，设备中文无衬线说「读的字」；英文领、中文随；直角，只有交互件切角；无阴影，只有两个浮层例外。

**长在活动自己的世界里（原站取值）。** 活动名里的名词 Class of 2028；走廊整条红墙带与入口 3:1 的 LED 墙；集章传统；52 / 10 / 3（大学 / 展区 / 楼层）这组数；上一届的反面（魔法地图、做旧纸）。同一份 brief 并排做过四个机制（寄往世界、纹章、启程、校队），落地的是不需要解释的那个：手段就是活动自己的名词。其余三个在方向池里。

**页面是实物的移植**（先选一件现场实物，移植它的阅读顺序与比例，不移植坐标）：首页 = 入口 LED 欢迎屏 · 实体页 = 展位桌牌（巨型名字、签名线、底部红色房间带）· 列表 = 门牌（粗顶线 + 细行线、红色房号）· 地图 = 平面图模板（房号牌立在门口）· 弹层 = 桌牌卡 · 告示 = 桌牌横过来。

**身份核心（动了就不是 Varsity）**：红 = 在哪 / 现在 / 去做，深蓝 = 结构，其余只有暖纸与灰；板式名字与数字 + 加宽大写标签 + 次语言紧随；切角只给可点击的东西；五段班级条纹当分隔线；列表是门牌而不是卡片；除两个浮层外无阴影。核心里任意两条同时动掉，就是别的方向；其余识别特征见 `fingerprint.json`。

**近亲可变 / Sibling range。** 做兄弟站时，「可动」一列可以改，「不变」一列是该轴上不能丢的；地板规则（对比度、触控、焦点、减弱动效、隐私）永远不动。

| 轴 | 原站取值 | 可动范围 | 不变 |
|---|---|---|---|
| 两种墨 + 纸 | 红 22° + 深蓝 259°，纸 89°（OKLCH） | 两墨色相差 ≥ 90°；a L .24–.36，b L .48–.58 且 C ≥ .16；纸 L .95–.98、C ≤ .02、h 70–100°。绿 + 金、梅红 + 赭、钴蓝 + 橘 | 红的职责写成规则；两墨亮度相近（\|ΔL\| ≤ .27），必须用纸色隔开 |
| 展示字 | Zilla Slab 700，−.025em，行高 .86 | 板式 / 高对比衬线 / 宽体无衬线 / 窄体海报字；600–800；−.03–0em；.8–1.05；字号阶梯可换等比 1.25–1.414 | 字距、行高随字号反向 |
| 标签 | Archivo 宽 125，大写 .2em | 大写 .12–.24em；小型大写衬线；等宽 | 远看成块；次语言灰 + 小 + 紧随 |
| 轮廓 | 8px 切角只给交互件，圆只给徽章 | 全方 / 固定小圆角 / 胶囊 / 票根缺口 / 折角 / 齿孔 | 只给交互件；为被裁掉的焦点环与阴影重新求解 |
| 分隔线 | 3:1:2:1:3 五段条纹；线宽梯度 1/2/3/4/6px | 单色粗线 + 缺口 / 格纹 / 旗串 / 齿孔 / 像素方块；双线、点线、纯留白 | 块开头粗、条目之间细 |
| 深度 | 三级纸色 + 两个浮层阴影 | 阴影着色、offset 硬阴影、纸叠、玻璃层 | 说清哪些面可浮起；模糊有无模糊回退 |
| 壳与首页 | 1120 / 20；入口屏 1:2.1；手机 112px 窄条 | 壳 960–1200、页边 16–24；地图优先或纯字体海报；网格断点 | 色块出血、文字对齐页边；手机首屏塞下标题 + 数字 + 按钮 |
| 组件 | 红 / 深蓝 / 纸三档按钮；8px 内缩弹层；报告块「淡底 + 顶边」 | 实心 / 描边 / 文字按钮；全宽圆顶或侧抽屉；左条 / 描边 / 编号卡 | 按下即时；悬停只在有悬停的设备；焦点环处处可见；状态不靠单独的颜色 |
| 动效 | 弹簧 .30–.55s，bounce 0，按压 .97 | dur .30–.65，bounce 0–.35：重而静 → 紧而稳 → 有生气；按压 .94–.985 | 从当前位置与速度接手；松手带速度；静止不重绘；减弱动效同终态 |
| 双语 | 英文领、中文随，≥1.1× | 中文先领；两语等宽并排；次语言放徽章 | 次语言同位置同灰；术语表；不靠切换按钮藏一种语言 |
| 地图 | orbit · paper · badge；pitch 30，yaw 32 | 投影 orbit / oblique / exploded / plan；材质 paper / line / clay / blueprint / riso；标记 badge / pin / plate / dot / flag / stamp；pitch 16–84°，墙高 .3–2.8m | 弹簧接手、拖动 1:1、`pan-y`、halo 文字、路线最后画、几何构建期校验 |
| 导视 | 「约 N 米」；按地标命名楼梯 | 步数 / 秒数；钟点转向；扫码起点；顶部横幅 | 先问起点并有默认；每步一句；先显示第一步并可全览；URL 是公共 API；路线可穷举测试 |
| 印刷 | 粉笔纸 A4 横版；名字 + 两枚 80mm 二维码 | 纸色；英雄可以是房号或照片；二维码缩到 40mm | 页高留 0.2mm 余量并校验页数；二维码不着色；第三方标志规整到统一容器；授权先查 |
| 实体色 | 每个实体一个主色，七个变量 | 不参与；只做一个点；按楼层着色 | 派生写成函数并测试，面 / 字分开 |

## Colors

*色彩：两种墨 + 暖纸 + 三个有职责的灰。颜色按「意义」分配，不按「好看」分配。*

**原站取值：七个有名字的颜色就是全部**，组件只引用语义别名。OKLCH 为(推算)。

| 名 | 值 | 职责(OKLCH 推算) |
|---|---|---|
| chalk | #F7F5F0 | 页底，约 46% 面积；.970 .007 89° |
| paper-2 | #ECE8DF | 次级面：搜索框、卡、按下的行、地图地面；.932 .013 87° |
| stone | #D8D3C8 | 只做线（对 chalk 1.37:1，永不当字）；.868 .016 86° |
| ink | #14171D | 正文；.204 .013 264° |
| muted | #5B6270 | 次语言、说明；.495 .024 264° |
| navy | #13294B | 标题、链接、框线、面板、墙帽，约 30%；.283 .069 259° |
| red | #C8102E | 在哪 / 现在 / 去做，约 18%；.530 .207 22° |

冷墨（264°）压暖纸（87–89°），是「印出来的」手感。语义别名：`--bg --tint --rule --text --head --sub --accent --accent-text --panel --on-panel --bar --shadow` 各指向上表某色（`--bar` = 页底 .9 透明）；标题（navy）与正文（ink）是两个 token；链接 = navy 字 + 2px 红下划线、`text-underline-offset:.22em`。

**红的预算。** 链接下划线、当前导航下划线、索引号与房号、悬停标题、焦点环、主按钮、房间带、弹层顶帽、待定与引用的左条、条纹中段、统计数字、地图目标环 / 路线 / 入口箭头；红字总是短的，从不成段。深蓝的预算：标题、链接、列表顶线、分段控件框、次按钮、欢迎面板、提示条、墙帽。

**填充红与文字红分开（floor）。** `--accent` 深色里不变；`--accent-text` #C8102E → #FF7084。红在深蓝上只有 2.47:1，深蓝面板上的红标签改 #FF8A99（6.46）。红与深蓝亮度几乎相同，贴着会颤，所以二者之间总隔一道粉笔色（条纹的 chalk 段，号码的 3u 描边）。

**深色 = 品牌反相，不是反色。** 地面 #0D1D36（比品牌深蓝再深一档），#13294B 升为抬升面，弹层内部再升一档 #1E3A66；规则 `rgba(247,245,240,.16)` 随底色取色；字 #EEEAE1（暖，不用纯白）；栏 `rgba(13,29,54,.88)`。机制：暗色块写两遍（`@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){…}}` + `:root[data-theme="dark"]{…}`）；`theme-color` 浅 / 深各一。「深蓝按钮」在深色里翻成粉笔底深蓝字；选中的分段控件 `--head` 底 `--bg` 字自动反相；背景图箭头要手写深色版。

**实测对比度(推算)。** ink/chalk 16.47 · navy/chalk 13.32 · muted/chalk 5.63、/paper-2 5.01 · red/chalk 5.40 · #B45309/chalk 4.61、/paper-2 4.11 · 深色 #EEEAE1/night 14.04 · #FF7084/night 6.34、/#1E3A66 **4.27** · red/night **2.86**、/navy **2.47**（只作图形）· gold/chalk 2.94（装饰）。

**每个实体一个色**（原站：每所大学一个海报主色）。一个输入色拆成面、字、面上的字、淡底、线，深色再两个；组件只写 `--s-fill --s-text --s-soft --s-line`；主题是 `<body style="--school:…">` 一行内联，零每校 CSS，缺省退回 #13294B。对应 kit 的 `--e --e-text --e-on --e-soft --e-line --e-dk --e-soft-dk`。

```yaml
entity-tone:
  target: 4.6                      # 门槛 4.5，多留 0.1 抵 1% 量化
  inks: {paper: "#F7F5F0", ink: "#14171D", night: "#0D1D36"}
  text: "向 ink 按 1% 步长混合，第一个对 paper 达标的色（停在『刚好够』）"
  dark-text: "对 night 已达标则原样；否则 HLS：s=min(s,.62)，l 向 .92 按 1% 推进到达标"
  fill: "= 原色；仅当 chalk 与 ink 在其上都不到 target 才压暗成 text"
  on: "chalk 与 ink 取对 fill 对比更高者（亮橙配墨字）"
  soft: "mix(c, chalk, .90)"
  line: "mix(c, chalk, .55)"
  soft-dark: "mix(c, night, .78)"
  gold: "#A98B5F / dark #CDB38A（与实体无关的『金属』点缀：编号、短尾）"
  examples(推算): ["#FF6C0C → text #B45311, on ink", "#370404 → dark #DA6060"]
  test: "对全部实体断言 text/paper ≥4.5、dark/night ≥4.5、fill/on ≥4.5，不达标即构建失败"
```

**kit token 映射(推算)。** 两处与原站不同，为的是过 kit 的 lint：①原站浅色 `--climb` #B45309 与红只差 26.7°（OKLCH），低于 kit 的 50°，原站靠虚线弧 + 文字标签补足；兄弟站用 #8D671D（对 chalk 4.71、对 paper-2 4.20、与红差 57°）。②原站深色焦点环仍是 #C8102E，对 #0D1D36 只有 2.86:1，不到 3:1；改 #FF4D63（5.21）。另有两处是套件新增：③`--climb-text`（凡文字的爬升色，对纸与 paper-2 都 ≥ 4.5）：浅色 #866114（对 chalk 5.16、对 paper-2 4.60，推算），深色同 #FBBF24；④地图选中拆成两个令牌：原站的房间淡染 room-sel 是 `--m-select-fill`，边线 `--m-select` 取路线红（对楼板 4.81 / 深色 4.12，推算）。再有两处 kit 更严：⑤地图墙面——原站 `--m-wall` `#F4F1EA` / `#2C4A78` 对楼板只有 1.08 / 1.5:1（形体靠墙帽线，墙帽 11.9 / 12.2:1 已过 7:1），kit 要 `--m-wall` ≥ 3:1、`--m-cap` ≥ 7:1，所以用 kit 生成的 `varsity` 牌墙面比原站深（浅色）或浅（深色）（`map-craft.md` §5.7、floor F03）；⑥按钮悬停——原站 `opacity:.88`，kit 改成下划线（.88 会把 4.6:1 的按钮字拉到约 3.8:1，floor F12）。

```yaml
kit-tokens:
  light: {paper: "#F7F5F0", paper-2: "#ECE8DF", rule: "#D8D3C8", text: "#14171D", sub: "#5B6270", a: "#13294B", a-text: "#13294B", on-a: "#F7F5F0", b: "#C8102E", b-text: "#C8102E", on-b: "#F7F5F0", climb: "#8D671D", climb-text: "#866114", focus: "#C8102E"}
  dark:  {paper: "#0D1D36", paper-2: "#13294B", rule: "rgba(247,245,240,.16)", text: "#EEEAE1", sub: "#AEB6C6", a: "#F7F5F0", a-text: "#F7F5F0", on-a: "#13294B", b: "#C8102E", b-text: "#FF7084", on-b: "#F7F5F0", climb: "#FBBF24", climb-text: "#FBBF24", focus: "#FF4D63"}
  lead: en                       # 英文主、中文辅 → <html data-evk-lead="en">
  structure: two-inks-paper      # a=navy 259°  b=red 22°  paper 89°；原站值 climb-light #B45309、focus-dark #C8102E
kit-tokens-misc:                   # BUILD-SPEC §2.3 的其余 token(推算)
  type:   {label-case: uppercase, label-track: .2em, label-stretch: 125%, label-weight: 700, display-weight: 700, display-track: -.012em, display-leading: 1, step--1: .74rem, step-0: 1rem, step-1: 1.12rem, step-2: 1.65rem, step-3: "clamp(2.5rem,7.6vw,4.7rem)", step-4: "clamp(3.6rem,19vw,9rem)"}
  shape:  {radius: 0, chamfer: 8px, hair: 1px, rule-2: 2px, rule-3: 3px, rule-cap: 6px}
  motion: {spring-dur: .35, spring-bounce: 0, press-scale: .97, fade-dur: .2}   # dur < .45 → motion_bucket firm
  layout: {gutter: 20px, gap: 14px, row-pad: 10px, measure: 40em}
```

## Typography

*字体：四个声音各管一件事，同一件事不混用两种脸；字距和行高随字号反着走。*

名字与数字 = Zilla Slab 600/700（标题、实体名、行标题、房号、统计、章节号）；导视标签 = Archivo 宽度轴钉在 125（自称 Archivo Expanded）500–800，永远大写 + 宽字距（`.k`、导航、按钮、分段、索引号）；界面与阅读 = 系统 UI 字体接中文链；中文 = 设备无衬线（所有 `.cn`）；中文衬线只留给研究报告的章标题与引语。

```yaml
fonts:
  display: "'Zilla Slab', Rockwell, Georgia, serif"          # 回退按『同类』：板式 → Rockwell
  label:   "'Archivo Expanded', 'Helvetica Neue', Arial, sans-serif"
  body:    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, <cjk-sans>"
  cjk-sans:  "'PingFang SC', 'Noto Sans SC', 'Noto Sans CJK SC', 'Source Han Sans SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
  cjk-serif: "'Songti SC', 'STSong', 'Noto Serif SC', 'Noto Serif CJK SC', 'Source Han Serif SC', <cjk-sans>"
  recipe: "Google Fonts（Zilla Slab、Archivo，OFL）；Latin 子集；先切再钉轴：Archivo wdth=125、wght 500–800；保留 OFL name 记录；3 个 woff2 共 76,580 B，只预载 Zilla 700 与 Archivo，swap；中文不下载字体；kit 不带字体文件"
type-fluid:                        # 大于 1.5rem 的用 clamp(最小, vw, 最大)，正文固定 rem
  display:     "clamp(2.5rem,7.6vw,4.7rem)/1 -.012em；子页 clamp(2.4rem,7vw,4.2rem)；手机首页 clamp(1.85rem,8.4vw,2.6rem)"
  entity-name: ["clamp(3.6rem,19vw,9rem) ≤4 字符", "clamp(3rem,14vw,7rem) 5–7", "clamp(2.6rem,10.5vw,5.4rem) 8–12", "clamp(2.2rem,8.2vw,4.4rem) >12，overflow-wrap:anywhere 兜底"]
  figures:     {stat: "clamp(2.8rem,9vw,4.4rem)/.8", booth: "clamp(2.4rem,7vw,3.8rem)/.8", stat-cell: "clamp(1.55rem,7.4vw,2.5rem)/1.05", part: "clamp(2.4rem,11vw,3.4rem)/.9"}
  small:       "分段 .72rem .14em · 提示 .64rem .14em · 统计说明 .58rem .14em · ROOM 小字 .54rem .14em；中文：桌牌 clamp(.95rem,2.6vw,1.2rem)/1.4 .08em，行副 .82rem .06em；lede 1.02rem/1.8，脚注 .8rem/1.55，图注 .72rem/1.5"
```

**四条规律（可换数，不可换方向）。** ①字距随字号反向：8.6px 大写 +.14em，12px +.2em，144px 显示字 −.025em。②行高随字号反向：正文 1.7、中文长文 1.85、显示 1.0、实体名 .86、大号数字 .8。③微标签（8.6–10.2px）能成立，因为脸宽、全大写、粗、有字距，且从不是唯一的信息载体；换成窄体就不成立，最小别低于 11–12px。④实体名按字符数分四档（系数约 ×0.75 递减），无 JS、无布局抖动，前提是内容里有人工审定的「短名」字段。

**数字与中文排印。** 数据数字一律 `lining-nums tabular-nums`（Zilla 默认是旧式数字，3 会掉到基线下）；补零 03 / 10 / 52，展位 01；首页统计用设计稿的矢量号码（约 7% 倒角）填 `--accent`，真字只作回退，`.vh` 给读屏器念值。`body{line-break:strict; text-size-adjust:100%}`；实体名 `word-break:keep-all` 并预切 `<span class="nw">` 词组；次语言字距 .02–.12em；模板里两个汉字之间的换行会渲染成空格，构建时去掉；汉字与拉丁数字间补一个空格。居中的大写字距标签用 `margin-right:-.22em` 抵消尾部字距；巨型名字用 −10px 量级负 margin 做光学对齐。

## Layout

*版式：1120px 的壳，20px 页边是一条对齐线；色块与图片出血，文字不出血。*

`main{max-width:1120px; margin:0 auto; padding:0 20px 64px}`，顶栏内层同为 1120 / 20。移动优先，断点跟着「组件内容形态的切换」走，不跟设备名走。

```yaml
breakpoints:                       # 宽度 → 改变的唯一行为
  base: "单列，20px 页边，色块与媒体出血，校徽网格 2 列"
  700:  "校徽网格 3 列；报告卡 2 列；数字卡 auto-fit；（640：提交按钮改自适应宽）"
  760:  "双列名录 gap 40；出血的照片与色带回到版心；照片 16:9 / 21:9；徽章 52→76px；数字条 repeat(var(--n,4))"
  879:  "≤879 = 手机首页：深蓝窄条、紧标题、3 列统计、双按钮、矮地图；导视面板压缩"
  880:  "欢迎区 1:2.1 并排；where .7fr:1.3fr；弹层变 400px 角落卡（right 24 / bottom 24）"
  980:  "报告章 = 250px 粘性左栏 + 正文（gap 56）；小节标签变竖列"
  1000: "校徽网格 4 列"
  1100: "报告卡 3 列"
  max-height-720: "手机矮屏：路线面板只显示当前步（:has() 带兜底）"
touch:                             # 触控目标按重要性分档
  tiers: "主 46–52（btn 46、search 48、路线钮 48、双钮 50、模式开关 52）· 行 44–60（list-row 60、grid-cell 56、折叠 54、步 44）· 紧凑 38–42（btn-small 38、segmented 40、目录钮 42）"
```

**出血而不破页边。** 父级 20px 内边距，出血子项 `margin:0 -20px` 并自带 `padding:… 20px`（色带 26px 20px、图注 7px 20px 0），文字仍落在同一条页边线上；≥760 清零。栅格第一列左内边距 0，让徽章正好挂在页边上。

**间距（无 token 刻度）。** gap 8 / 10 / 12 / 14 / 16 / 18 / 22 / 24 / 28；块间 14–36 / 46 / 56 / 64 / 88。簇内紧，簇间约 3–4 倍；大结构落 8 的倍数。区块标题上边距 46（手机 34）、下 14；`.part` 56 → 88；`.group` 36 → 22。

**首页（入口屏的移植）。** 桌面 `.welcome` 两列 `minmax(0,1fr) minmax(0,2.1fr)`：左格深蓝面板（padding 44px 28px，徽章宽 min(100%,340px)）；右格依次是红色 `Welcome` 小标签 + 日期「填写线」（3px 深蓝下划线，无数据则不渲染）、手工两行 h1、中文句、32em 的灰引言、统计、至多两个按钮（红在先），下接条纹。手机（≤879）`grid-template-columns:112px 1fr` 加 `.welcome-body{display:contents}`，徽章格 + 日期格并成一条深蓝窄条，其余子项 `grid-column:1/-1`；统计 3 列、号码高 36px；按钮并排、中英叠放；整页短约 40%。顺序：欢迎 → 条纹 → 场地预览（clamp(380px,64vh,660px)，手机 clamp(300px,48vh,430px)）→ 搜索 + 校徽网格 → 页脚条纹。

**校徽网格。** `border-top:2px` 深蓝，格底 1px 石灰，竖线是按断点重算的 `nth-child` `border-right`；格 `grid-template-columns:30px 1fr; column-gap:9px; min-height:56px; padding:8px 8px 8px 0`：30px 圆徽章（缺图用同尺寸 tint 圆）、Zilla 600 .95rem 短名、一行「中文名（省略）+ 红色 Zilla 房号 + 灰小号 ·展位」；未定写「待定」。分组标题 `.k` 带计数「United States | 美国 · 43 所」。

**实体页（桌牌的移植）。** 顶行（区域标签 + 52px 徽章，≥760 为 76）→ 巨型名字 → 6px 签名线 → 全称 → 本地语言名 → 34em 限宽一句话 → 主图（手机 4:3 出血，≥760 16:9、max-height 74vh；无照片时放一条班级条纹）→ 数字条 → 红色房间带 → Where（文字 .7fr + 迷你地图 1.3fr）→ 研究内容 → 上下页；第 2 部分前与第 round(2n/3) 部分前各插一条照片带（手机 3:2，≥760 21:9）。长文行宽用 em：引言 32、副标 36、正文 40em（≈ 40 个汉字，≈ 75 个拉丁字符(推算)）；≥980 章头 `position:sticky; top:84px; max-height:calc(100vh - 110px)`；`scroll-margin-top`：part 70、小节与折叠 76、来源 80；「当前章」以视口 28% 处的阅读线判定。

## Elevation & Depth

*深度：不靠阴影，靠三级纸色、线的粗细与留白；只有两样东西浮在内容之上。*

- **三级面**：chalk（页）→ paper-2（搜索框、卡、按下的行、地图地面）→ navy（面板、提示条）；白色不当卡片底，卡片只铺一层淡色，不抬起。
- **只有 `.sheet` 与 `.partnav-panel` 有阴影**：`0 16px 44px rgba(19,41,75,.24)`，深蓝而非黑，像墨洇进纸；深色改 `rgba(0,0,0,.5)`。其余 `box-shadow` 都是焦点环。
- **深色三级**：#0D1D36 → #13294B → #1E3A66，每深一层亮一档；与 tint 同色的容器要重声明 tint（弹层本身是 #13294B，所以弹层里 `--tint:#1E3A66`）。
- **顶栏**：`sticky; top:0; z-index:30`；页底色 .9 + `backdrop-filter:saturate(160%) blur(16px)`；静止时与页面同色、无边；`scrollY>2` 才淡入 2px 细线（navy 长段 + 96px 红尾，`opacity .2s`，挂在栏下沿 `top:100%`，栏高不变）；`prefers-reduced-transparency` → 实色。弹层出场距离 = 自身高度 + 24px，阴影不露头。

## Shapes

*形状：直角为底，一个切角给可点击的东西，一个圆给徽章，线宽就是等级。*

```yaml
rules:                             # 线宽 = 等级：块开头粗，条目之间细
  1px:   "条目之间、栅格线、统计条、折叠、表格行、时间线脊、来源页脚（stone）"
  1.5px: "紧凑图标线、步骤号方框"
  2px:   "列表顶线、分段控件框、搜索下划线、房间卡框、表头、数字卡顶线、滚动细线、阅读进度（navy）"
  3px:   "当前导航下划线、填写线、卡片顶边、焦点环、当前步左条"
  4px:   "待定提示与引用的左条、目录面板顶边"
  6px:   "弹层红色顶帽、实体页签名线"
  quote-vs-note: "引语左线 3px 全浓；注记左线 2px 45%"
chamfer:
  button: {css: "clip-path: polygon(c 0, calc(100% - c) 0, 100% c, 100% calc(100% - c), calc(100% - c) 100%, c 100%, 0 calc(100% - c), 0 c)", c: 8px, border: none}
  print-ratio: "切角 = 短边 × 14%（图章、集章格、房号牌）"
  outline-on-chamfer: "外框 clip 10px，内填 clip 8.8px = 10 − 2(2 − √2)(推算)，2px 描边在四角等粗，不用 SVG stroke"
  small: "『你在这里』标签 6px；图标框 48 格切角 7、框线 2.5、字形线 3.4，miter、方头"
  focus: "切角会裁掉外描边：焦点环画在里面 box-shadow: inset 0 0 0 3px accent, inset 0 0 0 5px bg"
stripe:
  web:   "linear-gradient(navy 0 30%, chalk 0 40%, red 0 60%, chalk 0 70%, navy 0)   # 3:1:2:1:3 硬停靠"
  print: "navy 32 / chalk 10 / red 16 / chalk 10 / navy 32（设计稿各模板）"
  heights: {full: 18px, thin: 10px, vote-cap: 8px, print-sheet: 3.5mm}
  uses: ["欢迎块下", "页脚 thin", "无照片时顶替主图", "投票栏 8px 帽"]
  dark: "仍用原始 navy/chalk，外侧深蓝段与页底仅 1.16:1，读成 chalk-red-chalk（副作用，不是设计）"
accent-tip: {hairline: "navy 长段 + 96px 红尾，2px", entity-rule: "6px 高，flex:1 + 64px 尾，max-width 660px", print-rule: "1.6mm 高，尾 22%（按比例）"}
```

**其余规则（原站取值）。** ①圆只有徽章（网格 30px、实体页 52 / 76px、告示 34mm）。②方块记号一统：勾选框 22×22 + 2px 框 + 画出来的勾（`border:solid; border-width:0 2.5px 2.5px 0; rotate(45deg)`）；时间线节点 9×9；步骤号 20×20（1.5px 框）与 30×30（实心）；折叠箭头用两条边画成 9×9 旋转 45°，旋转后补 ±4px `margin-top`，相邻折叠 `margin-top:-1px` 合成一条线；`li::marker` 只染红。③线图标 24 格，描边 1.9–2.4，方头，`currentColor`。④箭头只有一个：90°、杆宽 = 高的 21%，旋转得四向；红 = 去这里，深蓝 = 普通方向。⑤倒角号码（logo 与房号）：红面 + 3u 粉笔描边 + 7.4u 深蓝外缘，数字之间 22u、开口 ≥ 19u；三层描边只留给 logo 与房号，统计数字、楼层号、图标平涂；≤48px 用两色实心小版。⑥章节号用金色 #A98B5F 大数字当图标。

## Components

*组件：每个都是一块「牌子」——平色、大写标签、无边框无阴影。*

- **按钮**：`inline-flex; gap:.6em; min-height:46px; padding:0 22px; border:0`；Archivo 700 .76rem/1.1 .16em 大写，中文部分 500 .72rem .1em 不转大写；`nowrap`。三档只靠填充分层：红 / 深蓝（深色里翻成粉笔底深蓝字）/ paper-2；small 38px、.68rem；禁用 `opacity:.45`。悬停（仅 `(hover:hover)`）`opacity:.88` 且显式写 `color`，免得被全局 `a:hover` 染成红底红字（kit 改成下划线，见上文映射 ⑥）。按下 `scale(.97)`。
- **顶栏与导航**：栏高 56 = logo 36 + 上下各 10；logo 是自带白边的贴纸，浅 / 深 / 深蓝面板共用一个文件。导航每项上英下中：`b` .68rem .18em 大写，中文 .6rem 500 .12em 灰；`padding:5px 9px 4px; gap:1px`；`border-bottom:3px solid transparent` 常驻，当前项变红，选中不位移。
- **目录按钮（n 条线）**：42×42，内含 26 宽 30 高竖列，每章一条 `<i>`：未读 12×2px 灰 .45，已读 墨色，当前 26px 宽实体色；`gap:4px`（>6 章时 2px）；`transition: width .25s ease, background-color .25s, opacity .25s`。它同时是菜单、目录与进度；栏下 2px 进度线 `transform:scaleX(var(--p))`，不加 transition。
- **门牌列表**：`border-top:2px navy`，`li` 底 1px 石灰；行 `min-height:60px; padding:10px 2px; gap:14px`：红 `.idx`（Archivo .7rem .08em，≥2.1em）+ 主列（Zilla 600 1.12rem 名 / 中文 .82rem 灰，单行省略）+ 房号牌（右对齐，Zilla 700 1.2rem 红数字，上方 .54rem 灰大写 `ROOM`）+ 9×14 方头 V 形箭头。按下 `background:tint; transition:none`（按下即时，松开 .15s 缓出）。
- **搜索框**是「带底色的下划线」：`min-height:48px; padding:0 14px 0 40px; border:0; border-bottom:2px solid navy; border-radius:0; background:tint; appearance:none`；左 12px 的 18×18 放大镜（描边 2.2、方头）；聚焦时下划线变红、不画 outline；`placeholder{color:sub; opacity:1}`；去掉 WebKit 取消叉。占位符是说明书：「英文名、中文名、缩写，或藤校、加州、理工…」（一行教会四种输入：名称、缩写、类别、房号）。
- **分段控件**：`inline-flex; border:2px solid navy`；按钮 `min-height:40px; padding:0 14px`，间隔 2px 深蓝，Archivo 700 .72rem .14em；按下 = `--head` 底 `--bg` 字；用 `aria-pressed`，不冒充 tablist。
- **统计条**：`<dl>`，顶 1px、格左下 1px；DOM 先标签后数值，视觉上数值在上（`flex-direction:column-reverse`）；数值 Zilla 700 实体色 `lining-nums tabular-nums` `overflow-wrap:anywhere`；说明 Archivo .58rem 大写 + 中文 .72rem；手机 2 列，≥760 `repeat(var(--n,4),…)`，首格无左线无左内边距。
- **红色房间带**：整幅出血，`padding:26px 20px; grid-template-columns:auto 1fr; align-items:end; gap:16px 24px`；左：三层描边房号（高 clamp(70px,17vw,128px)）；右：粉笔色 `.k`「Room 203 · 2F | 二层 · 203 展区」+ 展位号压在 3px 粉笔下划线上。
- **待定 / 空 / 错误（一个组件）**：`background:tint; border-left:4px solid red; padding:16px 20px; color:sub`，英文标题 Zilla 600 1.05rem + 中文说明；文案必给下一步或例子（「可以试试英文缩写，例如 ABC。」，`role=status`）。
- **底部弹层**：`fixed; left/right/bottom:8px; z-index:40; max-height:70vh; padding:6px 18px calc(16px + env(safe-area-inset-bottom)); border-top:6px solid red; box-shadow:var(--shadow)`；抓手 40×4px、`--sub` 50%；只有抓手区 `touch-action:none`，列表照常滚；≥880 变 400px 角落卡并隐藏抓手；非模态（无遮罩、无焦点陷阱）；一次只开一个，新开的赢。
- **勾选与提交**：真 `<input>` 视觉隐藏但可聚焦；22×22 方框，选中填红 + 画勾，整行（60px）是目标，已选三重线索（勾、填色、标题变红）。粘性提交条 `sticky; bottom:0`，顶 8px 条纹帽，`padding-bottom:calc(14px + env(safe-area-inset-bottom))`，不可逆提示紧贴按钮。
- **报告块**（封闭词汇，构建期校验）：卡片 = 10% 实体淡底 + 3px 实体色顶边；表格只有横线；时间线 1px 脊 + 9×9 方点；步骤 30×30 方号；折叠用原生 `<details>`；引用点击先展开祖先再跳转。**访谈色带**是整页唯一一次反相，只重声明 9 个 token，不改组件，详见 `references/reading.md`。

## Do's and Don'ts

*做什么，别做什么。标 floor 的是硬规则；其余只在「想保持 Varsity 的样子」时才算取舍，不是禁令。*

**Do**
- 每种强调色一个语义职责，写成清单；填充色与文字色拆成两个 token，每个深色面单独验；派生色写成函数 + 测试。
- 先选一件实物，移植它的阅读顺序；列表用「粗顶线 + 细行线」，层级靠线粗、纸色、留白；次语言同位置同灰紧随。
- 手机上用重排压密度，不缩触控目标；空态、错误、占位符写下一步或例子；图片占位色取实体淡色。

**Don't（floor，不论方向）**
- 文字对比 < 4.5:1（大字与装饰数字除外并标注）、非文本 < 3:1、焦点环 < 3:1；只用颜色表达状态；去掉 `:focus-visible`；主操作触控 < 44px；关键信息只在悬停时出现。
- 减弱动效下保留位移动画；地图静止时持续重绘。
- 放学生姓名、班级、联系方式；放「AI 生成」声明；编造场地几何；写没走过的路线提示。

**Don't（只为保持 Varsity）**：纯白当页底（#FFFFFF 只留给地图房间面、二维码砖、打印）；渐变与模糊加到内容上（条纹、滚动细线、顶栏除外）；卡片阴影；圆角（徽章除外）；第三种彩色；深蓝上放红色小字（2.47:1）；给活动取中文名（原站规则，兄弟站可换成自己的命名规则并写成测试）。

**原站踩过并修好的**见 `references/lessons.md`（`clip-path` 裁焦点环、深色弹层输入框消失、红字在深蓝上读不出、实体色直接当字不达标、汉字间出现空格、iOS 不触发 `:active`、手机首页太长、路线面板盖住地图、锚点被粘性栏盖住……）。
**原站的软处（别当规则抄）**：微标签 8.6–10px；导航链接约 38px；EN ≥ 1.1×CN 在小号大写里不成立；`prefers-contrast: more` 只在浅色生效；深色焦点环 2.86:1；条纹外段在深色里隐形；无 skip link；间距未 token 化；金色数字 2.94:1。

## Motion

*动效：一个招牌动作（物理弹簧），其余全是 ≤ 0.5s 的反馈。*

弹簧用（response 秒，阻尼比 ζ）描述：`k=(2π/response)²`，`c=4πζ/response`；kit 里写作 `new EVK.Spring(v,{duration:response, bounce:1−ζ})`。全部临界阻尼，只有「松手弹回」是 ζ=.8。

```yaml
motion:
  spring:                          # response s ; ζ ; kit bounce = 1−ζ
    sheet-open:      {response: .35, zeta: 1}
    sheet-close:     {response: .30, zeta: 1, note: "带松手速度"}
    sheet-snap-back: {response: .30, zeta: .8, bounce: .2, note: "唯一欠阻尼，约过冲 1%"}
    camera: {yaw: .55, pitch: .45, zoom: .45, fit: .50, target: .50, lift: .45, gut: .50, pad: .45, floor-z: .55, floor-alpha: .40}
    intro: {yaw-from: "-40deg", response: 1.1, then: .55, at: "1400ms", floors: "z −(6+4i)m、alpha 0 起，升到位"}
  order: "离开 < 到达（.30 < .35）；淡出 < 位移（.40 < .55）；弹层领先、相机跟随"
  integrator: {dt-clamp: .05s, sub-step: "相机 ≤4ms / 弹层 4 步", rest: "弹层 |x−t|<.4px 且 |v|<8px/s；相机按量各有 ε（yaw/pitch .0004rad，目标 .002m，lift/gut/pad .1px）"}
  dismiss: {projection: "v/1000·.998/(1−.998) ≈ .499s 滑行", close-if: "位置 + 投影 > 50% 高度", samples: "最近 ≤5 个"}
  rubber: "over·dim·.55/(dim + .55·over)"
  css: {press: "transform .1s ease-out（scale .97 按钮 / .98 上下页）", row: "background-color .15s，:active 时 none（按下即时、松开缓出）", colour-opacity: ".2s", chevron: ".2s ease", nav-lines: ".25s", hint: ".5s"}
  custom-cubic-bezier: none        # 原站一条也没有：ease / ease-out 或真实物理
  never-used: ["入场依次上浮", "页面转场", "骨架闪烁", "数字滚动", "循环动画（路线虚线除外）"]
```

**手势要点。** ①拖动 1:1 跟手；弹层向下无阻力、向上橡皮筋。②手指落下先 `stop()` 并把原点设在当前位置，动画中途可被接住且不跳。③停笔 >80ms 再抬起视为速度 0，只取最后 90ms。④抓手区只含抓手、标题行、提示与路线按钮；按钮、select、链接上的按下不启动拖动；`pointercancel` 同抬起。⑤`prefers-reduced-motion`：状态照样到达，只去掉插值（弹层直接显隐，相机 `.set()`，虚线静止，intro 与脉冲跳过）。⑥iOS 要一个空的 passive `touchstart` 监听器才触发 `:active`。

## Bilingual

*双语：主语言领，次语言紧随；谁灰、谁黑、谁大写，规则固定。*

**规则（原站取值）。** 英文主行，中文辅行；名字和标签上英文 ≥ 中文 1.1 倍；全站只有一个活动名 SDSZ College Fair，**没有中文活动名**，由构建测试守住。英文始终更响（Zilla / Archivo、navy、粗），中文始终是 `--sub` 灰、500 或 400、字距 .04–.12em、不转大写、换字体。小号大写里 EN 数值上可以比 CN 小（最低 0.73×，如统计说明 .58rem / .72rem），因为加宽大写视觉更大；真规则是「英文读起来是主」，比的是视觉大小。只翻译标签与名字，不逐段翻译正文；报告正文是作者的中文，不配英文孪生。

- 行内基线：`.k` = EN .74rem + CN .66rem（1.12×），`column-gap:.65em`；区块标题 EN Zilla 1.65rem + CN .9rem（「52 Universities 所大学」是被两种语言切开的一个短语）。上下叠放：导航、统计说明、行（1.12 / .82）、校徽格（.95 / .72）、全称与本地名。
- 英文小标签 + 中文大标题（报告章头：`.en` .66rem .18em，`.cn` 宋体 1.4–1.9rem）；中文先（主题路线名，作者用中文写：中文 700 1.08rem 在上，英文 .82rem 80% 在下）；中文句里的英文名仍用 Zilla 600。

**导视里两种语言各管一事**：英文是招牌（「Walk to Room 204」「Up to 2F」，不含距离与转向），中文是那句话（转向、地标、距离）；动作与目的地在两种语言里一致。

**文案声音。** 平、短、第二人称、句号结尾：「Class of 2028, meet your colleges.」「Ten rooms, ten stamps.」。按钮英文 1–2 词，中文是口语答案而非直译（Directions 怎么走）；全局栏用正式名（路线导航），需要处用口语（怎么走），英文同一个词。无感叹号、无 emoji。错误说发生了什么和下一步：「网络连接失败，请稍后再试。」；不可逆动作旁紧贴警告；零不显示（没有赞就不印「0 赞」，缺展位写「待定」）。地址按各语言顺序：EN「Room 203 · 2F」小到大，CN「二层 · 203 展区」大到小；选择列表把房号放最前（人在扫它）。

## Map

*地图：手写 canvas 伪 3D，不引库；颜色全来自 CSS token；静止时不画。*

**场景。** 单位米，x 向东 y 向南；所有楼层共用同一外轮廓与同一套垂直交通盒，分层后叠成垂直柱；坐标带 0.05m 的真实不规则度（量出来的）；展位房间**空心**（白地 + 1.0m 低墙 + 门洞），其余房间、楼梯、电梯、卫生间**实心**（1.15m 石色块），「空心 = 可进，实心 = 跳过」，不用图例。墙由单一来源用集合运算算出（合并共享边、减去块已画的面、开门洞与入口），只许横平竖直，数据写错则构建报错。房号牌立在第一扇门外 0.9m。

```yaml
map:
  projection: {kind: orbit, perspective: "L = 7 × 包络半径（近 ×1.167 / 远 ×0.875）", fit: "min((W−gut−pad)·share/(2mx), H·share/(2my))/1.06", share: {floors: .90, room: .62, route-step: .82}, near-margin: 3.5m}
  camera: {yaw: {all: 32deg, one-floor-tall: 14deg, route-side: 18deg}, pitch: {all: 30deg, floor: 50deg, room: 58deg, route: {side: 46deg, single: 52deg, stack: 32deg}}, limits: {pitch: "16–84deg", zoom: "0.75–4.5"}, tall-rule: "单层且 W ≤ 0.9H 用 14deg"}
  geometry-m: {wall-h: 1.0, wall-t: .22, block-h: 1.15, slab: .45, pin-h: 2.1, wall-piece-max: 2.4, wall-end-extend: .11, shaft-inset: .35, door-w: 1.2, stair-link: 2.5, plate-offset: .9, plate-z: 1.7, icon-z: 1.2}
  stack: {gap-all: 22m, gap-away: 26m, gap-route: "17m 起，由视线几何解出（+3m）", side-by-side: "W > 1.15H 时左右并排，+7m", ghost-floor: .12}
  colours: {slab: "#ECE8DF / #182F55", slab-side: "#13294B / #060F1C", room: "#FFFFFF / #1E3A66", room-sel: "#FBE3E7 / #4A2340", wall-cap: "#13294B / #F7F5F0", wall-face: "#F4F1EA / #2C4A78", block: "#D8D3C8 / #2A426B", icon: "#13294B / #F7F5F0", icon-bg: "#F7F5F0 / #13294B", route: "#C8102E / #FF4D63", ring: "#13294B / #F7F5F0", halo: "#F7F5F0 / #13294B", climb: "#D97706 / #FBBF24"}   # 浅 / 深
  kit-m-tokens(推算): {m-ground: "paper-2 / #13294B", m-slab: slab, m-room: room, m-block: block, m-wall: wall-face, m-cap: wall-cap, m-text: ring, m-route: route, m-route-halo: halo, m-dash: "rgba(255,255,255,.92)", m-climb: climb, m-select: route, m-select-fill: room-sel, m-projection: orbit, m-material: paper, m-token: badge, m-pitch: 30, m-yaw: 32, m-wall-h: 1.0, m-light: left, m-dim: .26, m-label-case: upper}
  shading: {slab-side: "0.92 − 0.20·s", wall-face: "0.93 − 0.13·s", block-face: "0.86 − 0.16·s", block-top: 1.04, note: "s = 面法线朝屏右的分量，光固定在屏幕左；背面剔除"}
  focus-ladder: {target: 1, themed-stop: .72, rest: .26, step-rest: .10, step-stop: .40, details: {overview: .5, step: .16}, inactive-seg: .38}
  token-badge: {pin: "2.1m 发丝柱", ring: "1.2px 画在徽章边内，目标 2.5px", shadows: "地面椭圆 rgba(19,41,75,.18) × sin(pitch)；盘影 rgba(19,41,75,.22) 下移 1px", pulse: "1500ms ×3，相机停稳后 500ms 才开始"}
  route-line: {layers: "halo(w+4, chalk) → 红(w) → 白虚线 [0.8w, 2.4w] 0.92α", flow: "≈ 36px/s", climb: "虚线 [6,6] ≈ 25px/s，并排布局用弧"}
```

**配色逻辑。** 三个几乎相等的安静面（白房、石块、纸地，彼此约 1.22:1）+ 一条强墨线（墙帽 navy，对白 14.5:1）+ 一个强调（红）+ 第二个强调只给垂直移动（琥珀）。地板面与页底同色（#ECE8DF），建筑像放在桌上的模型，没有卡片边；深色里地板亮半档保住轮廓。墙帽是真几何（宽 0.22m），线粗随缩放变化。选中的房间是**换底色**（#FBE3E7，红的 10% 淡洗），不是描边；未选中的徽章退到 26%，不消失。

**层与顺序。** 地板（低到高）→ 房 → 入口箭头 → 墙与块（先侧面后顶面，远到近）→ 直立件按深度排 → 楼梯井 → **所有楼层之后才画路线**（上层盖不住路线）→ 楼层号。墙切成 ≤2.4m 小段并两端各延 0.11m，画家算法才不错序、转角不缺口。图标是 48 格倒角八边形底（切角 7，2.5 框，字形 3.4 线）。第三方徽章入库前统一成 128px 白盘（圆章 92%，其余 74–83%，高盾下移 2%，不超半径 90%）。提示条「Drag to rotate 拖动旋转」6 秒或首次拖动即消，「Reset 复位」只在偏离 home（3°/2°/.04）时出现。拖动、惯性、橡皮筋、直立件 clamp 尺寸等引擎常数见 `references/map-craft.md`。

## Wayfinding

*导视：同一块面板、四个入口；先问「我在哪」再问「去哪」；每一步一句话。*

```yaml
wayfinding:
  grid: {cell: .25m, wall-clear: .2m, centre: .9m, centre-gain: 1.6, sight: .3m, landing: .7m, stair-link: 2.5m}
  cost: "步价 ×(1 + 1.6·max(0,(.9 − 净空)/.9))；非起点非目标的展区房间对路径是『关着』的，路线只经门进房"
  straighten: "视线每 .08m 一采，净空 ≥ .425m（.3 + 半格）；两端 1m 内放宽"
  stairs: "按两层总距离选最小的楼梯井；上下层同一格索引『从哪进、从哪出』；楼梯井按最近的电梯或卫生间命名（『电梯旁的楼梯』）"
  turn: "dot > .82（<~35°）算直走，否则按叉积左右；只有『出房门』『出楼梯』才报转向"
  distance: "报到门口的距离；门内余量 ≥ 3m 才说『再走约 N 米』；max(1, round)；一律『约』"
  exhaustive-test: "13 起点 × 52 展位 = 676 段全部可达，所以没有『找不到路』的界面"
steps-zh:
  walk: "从{起点}出发，{出门后左转/右转/直走，}走到{房间｜电梯旁的楼梯｜洗手间旁的楼梯｜楼梯}门口，约 {N} 米。"
  stairs: "走楼梯{上｜下}到 {层号} 层。"
  after-stairs: "{出楼梯后左转/右转/直走，}走到{房间}门口，约 {N} 米。"
  arrive: "进入{房间}{再走约 {N} 米}，{名称}在 {展位号} 号展位。"
  same-room: "就在{房间}里：{名称}在 {展位号} 号展位。"
search:
  normalise: "小写，去掉空白与 - _ . , ' ’ ( ) · – — /；四处同一函数并测试"
  tiers: "0 全名精确 · 1 名称前缀 · 2 关键词前缀 · 3 关键词包含 · 9 不匹配（隐藏）；同档保持场地原顺序；Enter 取第一个可见结果"
  groups: "21 个同义词组（藤校、加州、理工、城市名…）；会指向多个实体的词只做『组词』；纯数字别名在构建时拒绝，数字永远指房间"
url:
  grammar: {s: "?s=Slug 高亮并开该房间弹层", r: "?r=203", f: "?f=2F", to: "?to=Slug 只问起点", route: "?from=room:203&to=Slug 直接开始", tour: "?tour=id&stop=2（1 起）", nav: "?nav=tour|school"}
  rules: "优先级 tour > to(+from) > nav > s > r > f；运行中的路线用 replaceState 镜像进地址栏；以 URL 值为键的查找用 own-property 检查；slug 冻结（可能已印成二维码），错拼由路由器规范化后重定向并保留 query 与 hash"
memory: "只记起点（localStorage 包 try/catch，读出先校验）"
```

**交互（原站取值）。** ①入口四个（地图工具条、房间弹层「怎么走」、实体页 `/map?to=`、首页「主题路线」）；脚本没加载时入口隐藏，目录仍在。②两问：「我现在在」（原生 select，大堂排最前）、「去哪所学校」；打开后焦点落在**标题**（`tabindex=-1`）而非输入框，免得手机键盘盖住列表。③运行态自上而下：kicker → 目的地 Zilla 700 1.35rem → 步骤 → 三钮（上一步 / 全览 / 下一步，48px）→ 两个文字链。④当前步 = 左 3px 红条 + tint 底 + 填红方形序号 + 红色英文标签（三重冗余），楼梯步用 climb 色。⑤先显示第 1 步（相机只框这一段，其余退到 10–16%），「全览」一键进出；主题路线里改称「上一所 / 下一所」。⑥路线中地图锁定，按楼层即结束路线；一次只开一个浮层，新开的赢。⑦矮屏手机只显示当前步；`aria-live` 只念单独写的一句「第 3 步，共 4 步：…」。⑧`fitAboveSheet`：把主体放进画布扣掉栏与弹层后的**未遮挡矩形**中心，瞄准弹层停稳后的几何；弹层在底部 → 平移，在侧边 → 缩小重构图；旋转屏幕只在宽高比过 1.15 时重排。

## Print

*印刷：同一套角色换一块纸；按物体重配比例，不搬坐标。*

**告示（A4 横版，每个实体一张，原站取值）。** 页框 297 × 209.8mm（不是 210：Chrome 的 A4 页高 209.89mm，210 会让每张多出空白页；3512 宽输出再裁成 3508 × 2480 = 300dpi）；`print-color-adjust: exact` 印出粉笔纸色，正文用 navy 不用黑，整页读成两色墨印刷品，纯白纯黑只留给二维码与徽章盘。区域按毫米绝对定位，内容适应几何；左右 16mm、上 9mm ≈ 下 9mm，只有条纹出血。三级大小几乎没有中间：英雄 = 名字 44mm/.9 + 两枚 80×80mm 二维码；中 = 全称 6.4mm、展位号 11mm；标签 2.7–3.4mm 大写；英雄:中 ≈ 7:1。名字测量缩字（`fonts.ready` 后每次 −1px）；紧行高 + `overflow:hidden` 会削掉 g y p 的下降部，改 `overflow:clip` 留余量。框线 `box-shadow:0 0 0 .6mm navy` 画在盒外，「80mm」才是 80mm。排序按走路顺序（楼层 → 展区 → 展位），文件名 `201-01-Slug.png`，PDF 同序并校验页数。

**二维码。** 黑底白、`crispEdges`、不着色，品牌色只在外面：80×80mm 白砖 + 3mm 内边距 + .6mm navy 外框；安静区 4 模块写进资产（共约 11mm 白）；ECC M；编码用长域名，印出的是可输入的短地址；PNG 1 位、每模块 32px、`pHYs` 300dpi（拖进文档恰好 10cm）；两枚码尺寸、外框、说明结构相同；别人给的码原样放入，只去截图边框与压缩噪点。

**徽章与标志。** 每个第三方标志规整到同一个 128px 白盘（约 6KB，4× 超采样 + LANCZOS，盘面恰好 #FFFFFF）；印刷用 640px 从源重绘，34mm 盘 + .6mm navy 环；授权与出处逐个核对，不入包。**客户给的标志**不改色，做成 die-cut 贴纸：墨迹轮廓闭运算 3%、外扩 1.2% 白边；透明像素先填白再缩放以免黑边；输出 640 / 144 / 192（图标留 4px 边）。一张图在粉笔纸、深蓝面板、深色模式上都不用换版本。

**照片。** 宽度 1440 / 1200 / 720，WebP q60；`width`/`height`、`srcset`；主图 eager，其余 lazy；逐张手写垂直焦点 `focus_y`（常在 .40–.55）；署名排进版面（左：地点中·英，右：Photo: 作者 · 许可，.72rem）；只收 CC0 / 公有领域 / CC BY / CC BY-SA。

**同源。** 色值、字体、条纹来自同一份来源，脚本复制，测试守品牌规则；token 沿用印刷名；有意的差异要记下（印刷条纹 32/10/16/10/32，网页 30/10/20/10/30）。物理尺寸写进文件（图章 SVG 带 `25mm × 18mm`，单色可刻，切角框 .9mm）；集章卡格子按章定（31×20mm 格放 25×18mm 章）；印痕只轻微模拟（旋转 ±4.4°，`multiply`），不做旧。
