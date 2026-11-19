# 发布会演讲风格研究 / Stage Keynote Style Research

写 `keynote-deck-builder` 时的取证记录。SKILL.md 里的每条硬规则都应该能指回这里的某一条。

**证据分三档**，写规则时区别对待：

- **A 有依据**：来自 Apple 官方文档，或多个独立来源互相印证，或前 Apple 产品市场人员的公开说明
- **B 单一来源**：只有一处说过，可信但不能当定论
- **C 未证实**：搜不到公开依据，或来源本身是通用建议而非对发布会的实测。**不要据此写硬规则**

---

## 1. 字体与文字量 / Type and density

| 档 | 事实 | 来源 |
|---|---|---|
| A | 幻灯片上**字号不得小于 30pt**。这是 Apple 内部的硬规定，作用是逼着人删内容而不是缩字号 | [PJ Camillieri（前 Apple 产品市场）](https://medium.com/adventures-in-consumer-technology/this-is-how-we-make-slides-at-apple-b8a84352bf6d) |
| A | **一个概念一张片**。重要的数字或概念要单独占一张，不和别的挤在一起 | 同上 |
| A | **项目符号被称作"瘟疫"**。顺序性内容要拆成多张片，并列性内容要改成图形（圆、图示、隐喻） | 同上 |
| A | 现在用 SF Pro（San Francisco），九种字重，Text 与 Display 两个变体分别对应小字与大字 | [Apple Fonts](https://developer.apple.com/fonts/) |
| A | 2002–2015 年用 Myriad Pro，是那十三年的企业字体 | [fontinlogo](https://fontinlogo.com/post/the-story-of-apples-typography) |
| A | **SF Pro 的 EULA 只允许用于制作 Apple 系统的界面 mockup**，不能用于网页、非 Apple 平台或第三方商业软件。可合法替代的 OFL 字体：Inter、Public Sans、DM Sans、Work Sans | [Apple Fonts](https://developer.apple.com/fonts/)、[findfont 整理](https://www.findfont.co/learn/best-free-san-francisco-sf-pro-font-alternatives) |
| B | Keynote 软件里的一套黄金比例字阶：正文 24pt，H5→H1 为 24 / 38.83 / 62.83 / 101.66 / 164.49pt | [Made in Keynote](https://medium.com/@madeinkeynote/5-steps-to-better-keynote-typography-template-download-e7dca012b8cb) |
| B | 居中对齐是常态；两端对齐在公开分析过的发布会里没出现过 | [Keynote 对齐文档](https://support.apple.com/guide/keynote/align-text-tane1c9a464f/mac) |
| C | 标题用全大写还是句首大写 —— 无公开规范 | — |
| C | 大字的字距处理、多行标题的行高 —— 无公开实测 | — |
| C | 标题末尾加不加句号 —— 只有 Tim Cook 那张 "71 seconds. Sold out." 一个观察样本，不足以当规则 | — |

**换算要看画布，不能一律按 96dpi**（2026-09-17 更正）。早先写的「30pt = 40px」用的是 CSS 的打印换算
（1pt = 1/72 英寸、96dpi），但 Keynote 的画布本身以 pt 为单位：1920×1080 的片子导出就是 1920×1080
（[Apple Community](https://discussions.apple.com/thread/250059356)、[Casey Printing](https://www.caseyprinting.com/blog/how-to-get-a-print-ready-file-out-of-apple-keynote)，B 档），
所以在这种画布上 30pt 就是 30px。PowerPoint 的 16:9 默认画布是 960×540pt，30pt 相当于 1080 高舞台上的 60px。
**本 skill 的 40px 下限不靠这条换算成立**，靠的是第 9 节的视角几何；它比苹果 30pt 那条更严，方向一致。

## 2. 版式原型 / Slide archetypes

十四类反复出现的片型。分层靠**格子大小**，不靠列表缩进。

| # | 原型 | 构成 |
|---|---|---|
| 1 | 标题卡 | 一句标题 + 一个视觉主体（产品图 / 视频 / 渐变底）|
| 2 | 单句大字 | 超大字号一句短话，配极少视觉。为三秒内读完设计 |
| 3 | 大数字 | 巨大数字占据画面。**一张片只放一个数字**。原整理写「下面一行小字说明」，本 skill 0.9.0 起不照做：说明由讲的人说，限定词与单位和数字同一行，来源与样本量写进左下的出处行 |
| 4 | 产品主图 | 产品照占六成以上画面，最多配一个产品名或一句短断言 |
| 5 | 功能名 | 功能或产品名大字居中，配一个视觉（图标 / 截图 / 产品）|
| 6 | bento 网格 | 大小不等的格子，最大格放主图或界面截图，小格放规格与单点能力 |
| 7 | 规格密排 | 密集小格：芯片名、续航小时数、性能指标 |
| 8 | 双列对比 | 前后 / 新旧 / 竞品对比，列头标明对比的轴 |
| 9 | 图表 | 性能、采用率、趋势 |
| 10 | logo 墙 | 合作方 logo 阵列，通常灰度处理以免视觉噪音 |
| 11 | 章节分隔 | 满版底色，大字章节名，无细节 |
| 12 | 价格与上市 | 产品名、价格、容量与颜色选项、发售日期 |
| 13 | one more thing | 大字，Jobs 时代签名动作，Cook 时代基本停用（2014 Apple Watch 是例外）|
| 14 | 环保 | 环境承诺，独立成片或作为 bento 里的一格 |

来源：[deck.gallery 对 Apple bento 版式的整理](https://www.deck.gallery/blog/apple-bento-grid-decks-roundup/)、[Camillieri](https://medium.com/adventures-in-consumer-technology/this-is-how-we-make-slides-at-apple-b8a84352bf6d)、[applegazette 的 one more thing 清单](https://www.applegazette.com/lifestyle/every-one-thing-from-steve-jobs-keynotes/)

**已剔除的说法**：网上流传的"每分钟 0.5–1 张片"引的是一个通用幻灯片计时计算器，不是对发布会的实测，属 C 档，不采用。片上的测试条件小字（脚注免责声明）也搜不到公开分析，属 C 档。

## 3. 配色、画面与动效 / Color, imagery, motion

| 档 | 事实 | 来源 |
|---|---|---|
| A | 重点色**用得极省**，"少而有意图，冲击才最大"。一张片一到两支，极少三支 | [WWDC 2026 session 251](https://developer.apple.com/videos/play/wwdc2026/251/) |
| A | 重点色承担**语义**（数据、按钮、分类），不做装饰；且不能单靠颜色传达信息，要配形状或文字 | [Apple 设计体系整理](https://superdesign.dev/blog/apple-design-system) |
| A | `#007AFF`（systemBlue）这类值是社区取样，**不是官方规格**，会随系统与场景变化。不要写死 | 同上 |
| A | 产品用大面积柔光（大白色柔光板）打，消除硬阴影，形成招牌式的无影观感 | [产品摄影分析](https://www.picturecorrect.com/a-rare-look-at-how-apple-likely-does-product-photography) |
| A | 16:9 是现代发布会的通用比例，1920×1080 是标准产出尺寸 | [Keynote 尺寸](https://www.wps.com/blog/how-to-change-slide-size-in-keynote-a-comprehensive-guide/) |
| B | 片面几乎无装饰件：正片无页码、无页眉页脚、无边框、无卡片容器；logo 只在首尾片或母版上 | [Keynote 版式文档](https://support.apple.com/guide/keynote/add-and-edit-slide-layouts-tan7a2b69972/mac) |
| B | 不用纯白，改用近白或极浅灰，因为纯白投影时刺眼 | [presentation design rules](https://www.pi.inc/blog/presentation-design-rules) |
| B | 产品居中浮着，留白约占四到五成；图不出血、不压边 | [Keynote 反射与阴影](https://support.apple.com/guide/keynote/add-a-reflection-or-shadow-tan315eaae29/mac) |
| B | 内容离边留 10–15% | [舞台背景设计](https://elitemultimedia.com/event-backdrop-design-corporate-stage-backgrounds) |
| A | Magic Move 是 Keynote 的一种转场：对象从上一张的位置移到下一张的新位置 | [Apple 支持：给片上对象加动画](https://support.apple.com/guide/keynote/animate-objects-on-a-slide-tanf96d92cb6/mac) |
| B | 它是发布会的招牌转场 | [Magic Move 教程](https://business.tutsplus.com/tutorials/keynote-magic-move--cms-31554) |
| B | Apple 不公开发布真正的舞台模板文件；第三方"发布会风格模板"都是仿的 | [Apple 设计资源](https://developer.apple.com/design/resources/) |
| C | 底色是"灰→深蓝→近黑的渐变加轻噪点" —— 只有一个 Quora 回答说过，方向可信但不能当定论，也没有可靠的十六进制值 | — |
| A | 苹果官网的深浅两种底都是纯色：样式表里出现的底色是 `#000`、`#fff`、`#f5f5f7` 这类实色；iPhone 概览页的样式表里一共 4 处 `linear-gradient`，全是界面遮罩（滚动边缘、弹窗蒙层），**没有一处用作底色或文字填充**（`background-clip: text` 为 0 处） | apple.com.cn/iphone 的 `overview.built.css`，2026-09-28 取 |
| A | 苹果官网文字与分隔线的常用实色：`#1d1d1f`（浅底正文）、`#f5f5f7`（深底正文，即 rgb 245,245,247）、`#6e6e73` 与 `#86868b`（次要文字）、`#d2d2d7`（浅底分隔线）、`#424245`（深底分隔线） | 同上，及 `globalheader.css` |
| C | 动效时长（1.0 秒溶解、0.3–0.5 秒短揭示）—— 这些是 **Keynote 应用的默认值**，不是对真实发布会的实测 | — |

**0.10.0 补查**（2026-10-13）：使用者要求「保持苹果发布会的简约，但可以不是纯黑底」。
补查了苹果的舞台照片、Keynote 自带主题、HIG、Material 3、Duarte、AI 模板的样子和投影。

| 档 | 事实 | 来源 |
|---|---|---|
| B | **苹果舞台上讲述页的片底几乎都是纯黑**。美来自满版的产品微距、界面、实景照片、黑白人像；没见到渐变、光晕或颗粒底，也没见到整页的产品色底。样本有限 | Apple Newsroom 官方图集：2019-03、WWDC19、2019-09、WWDC20、WWDC23，约 31 张拍到屏幕的照片，目测（2019-03 与 2019-09 的链接见第 6c 节） |
| B | 上面那批照片里的例子：2019-09 Tim Cook 开场，身后是三摄的巨幅特写；WWDC19 Tim Cook 身后是黑底上的深灰巨字「Mac Pro」；2019-03 Spielberg 讲创作时，身后是低亮度的蓝绿氛围图；Kumail Nanjiani 讲自己的故事时，屏幕上只留 Apple TV+ 标志 | 同上 |
| B | WWDC19 的霓虹图形是那场活动的视觉识别，不是通用背景 | 同上 |
| A | **Keynote 14.5 自带主题以平涂为主**：Basic Black 与 Black 都是 #000000；Minimalist Dark 是灰蓝 #4B6079 | 本机 Keynote.app 包内的主题文件 |
| A | 色块只用在少数母版上：Basic Color 的 17 个母版里只有 2 个用海军蓝 #003462（含封面），其余是白底；Bold Color 是青、黄、粉与白交替 | 同上 |
| A | 渐变主题：Gradient 黑 → 海军蓝 → 蓝灰（取样近似 #020204 → #262642 → #717080）；Slate 上亮下暗的石墨（约 #727272 → #2C2C2C）；Showroom 浅灰加暗角。另有会动的云与波浪背景 | 同上 |
| A | **HIG Dark Mode**：背景更暗、前景更亮；颜色对比不低于 4.5:1，小字争取 7:1；没有要求纯黑 | Apple Human Interface Guidelines · Dark Mode |
| A | **HIG Color**：颜色要在不同光照下测；不要只靠颜色传达信息 | Apple HIG · Color |
| A | **HIG Materials**：Liquid Glass 只给控件与导航那一层，不进内容层 | Apple HIG · Materials |
| A | **Material 3** 从一个种子色派生出中性色阶，表面与背景都取自中性色阶。这是「从主色派生带色的中性底」的正式先例 | Material Design 3 |
| B | Duarte：黑底显得正式，大会场里画面上的物体像在发光；白底随意，适合小场地 | Duarte（书评转述） |
| B | Duarte：背景是台面，不是作品 | Duarte |
| B | 没有引导时，模型做的页面倾向 Inter 字体、白底紫色渐变 | Anthropic 2025-11 的文章 |
| B | 玻璃拟态宜少用，最大的问题是可读性 | NN/g |
| C | 「发光球、霓虹光晕、颗粒等于 AI 味」没有权威来源，是行业观感与使用者本人的判断 | — |
| A | 环境光会把投影画面冲淡 | ProjectorCentral |
| B | 细微的配色差别在投影上看不出来，要到现场实测 | Vanderbilt 2020 |
| B | 大面积平缓的暗区最容易出色带。加噪点能打散色带，这正是「颗粒渐变」的技术来源 | Netflix CAMBI（arXiv 2102.00079）；CSS-Tricks |

**结论性判断**（0.10.1，据 A/B 档推出，写进规则）：

- **底色平涂**。舞台上以纯黑为主（B），Keynote 自带主题以平涂为主（A），苹果官网的底都是实色（A）
- **不必是黑色**。Keynote 有灰蓝、海军蓝的主题，HIG 只要求背景更暗、前景更亮、对比够，Material 3 从种子色派生带色的中性底（都是 A）。
  默认用什么颜色，是使用者 2026-11-18 定的：**底色默认用和文字、讲的内容风格匹配的颜色；没有合适的匹配色，用黑色 #000**。
  匹配色从哪来，按先后：使用者指定的颜色；品牌或产品色；内容本身的颜色联想（课堂、板书 → 黑板绿；海洋、航天、物理 → 深蓝；
  植物、医学、环保 → 深绿；文史、艺术 → 深红褐；音乐、手作 → 暖褐）。文字的语气定饱和度：学术约 0.35，发布会约 0.45，封顶 0.60。
  明度交给 `--palette` 算，压到白字 ≥ 10:1、次要字 ≥ 7:1，不凭眼睛调
- **整套一个底色，或者按章节换色**。一个章节内不换色
- **封面、分节、静场可以换底**：色场、柔和渐变、同色调巨字，内容片不用。Basic Color 只在 17 个母版里的 2 个上用色块（A）；
  Gradient、Slate、Showroom 都只在一个色相里变明暗（A，取样值见上表）；WWDC19 的「Mac Pro」是黑底上的深灰巨字（B）。
  用渐变前在现场投影上看一眼有没有色带，有就改平涂（B）
- **备选**：带色近黑（主色的色相、明度 8.5%，几乎是黑；0.10.0 曾把它定为默认，导出 pptx 写 `"theme": "tinted"`）、
  石墨 `#1c1c1e`（LED 屏、电视、录播）、浅色 `#f5f5f7`（亮教室；这时匹配色改用在重点色与分节色场上）
- **不加光晕、颗粒、玻璃卡片、多色渐变，也不用会动的背景**。玻璃不进内容层（HIG，A）；运动起始会抓走注意（Abrams 与 Christ 2003，B，见第 13b 节）；
  白底紫色渐变、玻璃拟态是 AI 模板常见的样子（B），光晕加颗粒算 AI 味只是观感（C）。颗粒本来是给渐变遮色带用的，平涂用不着它
- 文字三档用实色；重点色一支，一张片最多用在一处；产品位放占位图（这几条 0.8.0 起没变）

**0.8.0 更正**：原来这里写的是「底色用近黑的多层渐变而不是纯黑」。那条结论实际只靠上表的 C 档一行，
按本文件自己的约定不该写进规则。改成纯色的依据是苹果官网的样式表（上表 A 档两行）。
另一个理由来自使用者的反馈：带光晕和颗粒的近黑底，恰恰是 AI 生成的片子一眼能认出来的样子。

**0.10.1 放宽**：0.8.0 定的是纯色、深色纯黑；0.10.1 只放宽颜色，纯色不必是黑，默认和内容匹配，没有合适的才用黑。平涂、不加光晕与颗粒照旧。

## 4. 叙事结构 / Narrative

这一节对"从演讲稿生成片子"最关键。

| 档 | 事实 | 来源 |
|---|---|---|
| A | **片子不重复讲稿的句子**。片是覆在讲话之上的一层，不是承载信息的主体；焦点是讲的人。Jobs 有过五分钟只对着 33 个字讲的段落 | [Camillieri](https://medium.com/adventures-in-consumer-technology/this-is-how-we-make-slides-at-apple-b8a84352bf6d)、[Presentation Zen](https://presentationzen.com/blog/steve-jobs-and-visual-presentation) |
| A | **不照读片子**。讲的人重复片上文字会造成认知过载，大脑要同时读和听 | 同上 |
| A | **2007 年 iPhone 先报出名字，再讲问题**。顺序：铺垫（Macintosh、iPod 改变过行业）→ 今天发三件东西 → 揭晓其实是一台设备，叫 iPhone → 现有智能手机的问题（不聪明、不好用、塑料键盘、固定按键、触控笔）→ 多点触控 → 软件与设计 → 分块演示（iPod、电话、上网）→ 伙伴登台 → 价格 → 上市 → 收束。问题出现在揭晓之后，所以「问题必须先于产品」不成立 | [爱好者转录页](https://www.allaboutstevejobs.com/videos/keynotes/macworld_2007)、[Macworld 当天的直播文字](https://www.macworld.com/article/1054764/macworld-expo/liveupdate.html)，两处顺序一致 |
| B | 同一场的时间码：揭晓 28:32，讲问题 29:41。转录页自己说明时间码可能偏几分钟，只作参考 | 爱好者转录页 |
| A | Duarte 的结构：确立"现状"（对手/问题），转向"可能"，中段在两者间来回摆荡，最后收到产品带来的新常态 | [Duarte TED](https://www.ted.com/talks/nancy_duarte_the_secret_structure_of_great_talks)、[Resonate](https://www.duarte.com/resources/books/resonate/) |
| A | **工作记忆约容纳三个块**。这支撑的是一个**上限**：并列的点超过三四个就会过载 | [Gallo](https://www.carminegallo.com/books/presentation-secrets-of-steve-jobs/) |
| B | Gallo 由此主张「三是最优数，分段和段内分点都用三」。**这是演讲教练的处方，不是研究结论**——容量上限推不出「必须凑够三个」。本 skill 只采纳上限，不采纳处方 | [Gallo](https://www.carminegallo.com/books/presentation-secrets-of-steve-jobs/)、[Slidegenius](https://www.slidegenius.com/blog/apple-presentations-3) |
| A | 数字出场时，**这个数字是片上唯一的文字**，随口播同时落地，留一拍让人消化再展开。一张片最多一个统计数字 | [Inc. / Gallo](https://www.inc.com/carmine-gallo/since-apples-new-product-launch-number-100-million-keeps-popping-up-its-not-accidental.html) |
| A | 复杂概念一律用熟悉物类比落地："思维的自行车"、"一千首歌装进口袋"、从信封里抽出 MacBook Air | [Forbes / Gallo](https://www.forbes.com/sites/carminegallo/2026/04/01/the-simple-strategy-that-made-steve-jobs-so-good-at-explaining-complex-ideas/) |
| B | 九拍结构：打破现状 → 展示收益 → 在痛与益之间反复 → 早早给出核心揭示（iPhone 在第 3 分钟；和上面转录页 28:32 的时间码对不上，起算点不明）→ 每约 9 分钟换节奏（换人、换演示、换故事）→ 简化片子 → 多用人称代词 → 给路标 → 段间回顾 | [Gong](https://www.gong.io/blog/steve-jobs-iphone-keynote) |
| B | 整场约 88 分钟 | 同上 |
| B | Cook 时代比 Jobs 时代多用约 24.9% 的统计数字，演讲者从一两人变成 90 分钟里十到十二人 | [Quantified AI 对比](https://www.quantified.ai/blog/is-tim-cook-a-better-presenter-than-steve-jobs/) |
| B | 刻意停顿：句后的沉默与话本身一样有力，用来造张力、让概念落地 | [the power of the pause](https://bespoke-coaching.com/blog/the_power_of_the_pause_in_presentations/) |
| B | "one more thing" 用的是 Columbo 手法：看似要结束，停顿，再抛一个 | [Wikipedia](https://en.wikipedia.org/wiki/One_More_Thing) |
| C | 一个产品段落跨多少张片 —— 公开分析里没有计数。"约 10–20 张"是目测推断 | — |

**0.10.0 更正**：这张表原来有一行「问题先于产品」，记 A 档，出处是 Gong 对 2007 年 iPhone 发布会的拆解；
SKILL.md 据此要求问题必须先于主角出场。上面两处来源对得上的顺序是先揭晓、后讲问题，所以那一行删掉，
规则改成「叙事路线」原则 1：开头几分钟交代听众为什么要听；发布会可以先揭晓，但「为什么要在乎」不拖过揭晓后的那一段。
原行后半句「用人话讲问题，不用技术约束讲」没有被推翻，留作写法上的建议，不作规则依据。

## 4b. 示例路线的出处（0.10.0）/ Route sources

0.10.0 应使用者要求补查（2026-10-13）：叙事路线不钉死，给几条常见、做得好的示例，允许改。
SKILL.md「叙事路线」路线表的十五条，每条在下表都有一行，路线名加粗；没有外部实例的照实写。路线是示例，不是规则：
出处说明有人这样讲过、讲得通，不说明必须这样讲。同一个来源在本节和第 12b 节的档次可能不同（例如 Kayvon），各按各自那部分调研记的档。

| 档 | 事实 | 来源 |
|---|---|---|
| B | **问题先行型** · Duarte 的 sparkline：在「现状」与「可能」之间往返，最后到行动号召与「新的美好」。它是一种形状，不是清单 | [Duarte 博客](https://www.duarte.com/blog/move-presentation-audience-with-story-techniques-in-presentations/)、TED 演讲 |
| 顺序 A；时间码 B | **揭晓型** · Macworld 2007 iPhone：铺垫 → 今天发三件东西 → 揭晓 → 现有智能手机的问题 → 多点触控 → 软件与设计 → 分块演示 → 伙伴登台 → 价格 → 上市 → 收束。细节与时间码见第 4 节 | [爱好者转录页](https://www.allaboutstevejobs.com/videos/keynotes/macworld_2007)、[Macworld 当天的直播文字](https://www.macworld.com/article/1054764/macworld-expo/liveupdate.html) |
| 中段 A；其余 B | **品类空位型** · 2010 iPad：近况与数据 → 笔记本与手机之间有没有第三类设备的位置 → 新设备必须在几类任务上做得更好 → 上网本只是更便宜，不算 → 揭晓 → 演示 → 生态 → 价格与上市 → 回顾。从提问到上网本再到揭晓这一段是 A | [Macworld 直播](https://www.macworld.com/article/202171/apple_event.html)（直播墙钟时间） |
| 收口 A；短片在价格前 B；以短片开头 C | **逐件循环型** · 九月发布会每个产品一段：（用户故事）→ 功能块 → 短片 → 价格与上市；同一家族的价格合并到家族段末尾。2024-09：Watch S10 价格 10:20，iPhone 16 价格 11:11，iPhone 16 Pro 价格 11:35。2025-09：AirPods 价格 10:13；Apple Watch 段以用户来信和跌倒检测片段开场，10:30 统一公布价格；三款 iPhone 价格合并到 11:11。Newsroom 新闻稿都有「价格与上市」小节 | [MacRumors 2024-09 直播](https://www.macrumors.com/2024/09/09/apple-event-live-blog-september-2024/)、[MacRumors 2025-09 直播](https://www.macrumors.com/2025/09/09/apple-event-live-blog-september-2025/)、Apple Newsroom |
| 结构 A；时间 B | 逐件循环型的平台版 · WWDC 按平台逐段讲：开场 → 可选议程 → 横跨所有平台的主题 → 各平台 → 开发者工具 → 发布时间表 → 收束。横跨主题有时在前、有时在后：2024 先报议程，Apple Intelligence 放到 11:06；2025 先讲 Apple Intelligence 与新设计；2023 先讲 Mac 硬件，11:21 进入 one more thing（Vision Pro） | WWDC 2023–2025 |
| A | one more thing，可以接在发布会路线的末尾：Apple Watch（2014）、Apple Music（2015）、iPhone X（2017）；WWDC 2023 的 Vision Pro 也是这样出场 | [Macworld 清单](https://www.macworld.com/article/674643/every-one-more-thing-apple-has-ever-announced.html) |
| — | **内容主导型** · 没有外部实例。这是本 skill 0.4.0 起自己的路线，理由写在 SKILL.md「内容主导：没有数字的项目」 | — |
| A | **先猜后讲** · Sinha 与 Kapur 2021 元分析：先让学生试、再讲解，总体 g = 0.36；但对小学二至五年级和通用技能，先讲后练占优 | Sinha & Kapur 2021，RER |
| A | 先猜后讲的前提：只在给对比案例、或在学生方案上展开讲解时才有效 | Loibl, Roll & Rummel 2017 |
| B | 预测型演示的效应偏小：只看演示，正确解释率 24%；先预测再看，30% | Crouch 等 2004 |
| 方法 A；成绩数据 B | **同伴教学循环** · 短讲 → 概念题独立作答 → 讨论 → 再答 → 讲解。首轮正确率约 35–70% 时，讨论后的提升最明显 | Crouch & Mazur 2001，Am. J. Phys. 69:970–977，p.970、p.972 |
| 结构 A；效果 B | MIT 8.02 TEAL：短讲、桌面实验、可视化、PRS 概念题与小组练习混合；学习增益约为对照的 2 倍，是准实验。实例：OCW 8.02 2007 春第 4 次课，开头有提纲与回顾，中间 6 道 PRS 题，以课堂习题收尾 | Belcher 2003；Dori & Belcher 2005；8.02 课件总表（链接见第 6c 节） |
| A | **回顾—小步—例题** · 斯坦福 CS106B 2022 冬第 7 讲：提纲 → 提取式小测 → 逐步例题 → 换情境例题 → 今日小结 → 课后任务 → 下次预告。A 指这份课件本身 | CS106B 2022 冬第 7 讲课件 |
| — | IES 实践指南按自己的分级：例题与练习交替，中等证据；用测验让学生重温，强证据；深度解释性提问，强证据；「用前测题引入新课」，低证据。这几级是 IES 自己评的，不另折成 A/B/C | IES 实践指南，Pashler 等 2007 |
| B | Rosenshine 2012 的十条原则 | Rosenshine 2012 |
| A | 专长逆转：例题对新手有效，对熟手优势消失，甚至反过来 | Kalyuga 等 2003 |
| B | **动机加一个想法** · Simon Peyton Jones「How to give a great research talk」：动机约两成，一个核心想法约八成；开头不放提纲；不单列相关工作；例子是主要武器 | Peyton Jones |
| B | **三明治** · Patrick Winston《How to Speak》：求职报告五分钟内讲出愿景与已做成的几步；最后一页写「贡献」，问答时停着；合作者放第一页；不以「谢谢」作最后一句 | MIT OCW RES.TLL-005（2018 IAP） |
| A | MIT EECS 的求职报告建议：Randy Davis 说先想清希望别人转述的三句话；Durand 说深讲一项贡献 | [MIT EECS](https://www.eecs.mit.edu/career-opportunities-at-eecs/faculty-job-talks-tips-from-the-faculty/) |
| B | MIT CommKit：求职报告是沙漏结构；发布结果侧重结果与意义，征求反馈侧重方法 | MIT CommKit（EECS、BE、AeroAstro） |
| B | **框定—方案—效果—取舍** · Kayvon Fatahalian「Tips for Giving Clear Talks」（2023-11 版）：分节页给一条路线，框定问题 → 方案 → 效果 → 没选的方案 → 收尾（p.57–58）；结果部分一页一个结论，写进标题（p.48）；以积极的大图景收尾（p.60–62）；先说为什么再说是什么，叙事上的意外几乎总是坏事（p.40） | [cleartalktips.pdf](https://graphics.stanford.edu/~kayvonf/misc/cleartalktips.pdf) |
| A | Durand 的讲演笔记：重要的节结束时设「重置点」；内容分层 | [TalkAdvice.pdf](https://people.csail.mit.edu/fredo/TalkAdvice.pdf) |
| B | **公开讲座** · Winston：开场先给一个承诺（empowerment promise），说清听完能多知道什么 | Winston《How to Speak》 |
| B | **路线图分章** · MIT Comm Lab 生物工程系 2026-02 的答辩复盘：路线图、每章一句结论、讲完回到路线图 | MIT CommKit（BE） |
| B | **阶段评审** · MIT 航空航天系 CommKit 的首次委员会会议：目标与现状 → 缺口和做法 → 已完成 → 计划 → 请评审回答的具体问题 | MIT CommKit（AeroAstro） |
| — | **课程项目答辩** · 没有外部实例。这是本 skill 0.2.0 起的答辩改法，原来是 `references/non-launch-occasions.md` 那张表的一行，0.10.0 收进路线表 | — |
| A | 课堂总体：主动学习让考试成绩提高 0.47 个标准差，传统讲授的挂科风险约是主动学习的 1.5 倍（225 项研究） | Freeman 等 2014，PNAS，doi 10.1073/pnas.1319030111 |
| B | 把 5E 或 Gagné 九事件当固定序列用，证据弱 | 2026-10-13 课堂调研 |
| A | 真实课件核查：CS231n、CS106B、MIT 8.02 都是开头回顾、中途提问，结尾总结不统一。A 指这几份课件 | 这几份课件本身 |

**七条原则各指回哪几行**（SKILL.md「叙事路线」）：

1. 开头几分钟交代听众为什么要听（A）：Winston 的承诺开场、Peyton Jones 的动机在前、Kayvon 的先说为什么、MIT CommKit 的沙漏结构，各自是 B，四处一致。发布会可以先揭晓，见第 4 节 2007 年 iPhone 那两行
2. 一场一个主信息，一张片一个点（A）：上表 MIT EECS 那行（Randy Davis 的三句话）；第 1 节 Camillieri；第 12b 节 Kayvon、ENGR 103、CWSEI 的「一页一个结论」
3. 抽象的东西落到例子、演示、数字或类比上（A）：第 4 节类比那行；Peyton Jones「例子是主要武器」；第 12b 节 Kayvon「展示而不是描述」
4. 长于十五分钟就设路标和「重新上车点」（A）：Durand 的「重置点」（A）；第 12 节 Gong 拆的路标与段间回顾（B）
5. 收尾落在实质内容上（A）：九月发布会每段以价格与上市收口（A）；Winston 的「贡献」页、Kayvon 的大图景收尾（B）。「不说谢谢」只有 Winston 一人主张（B）
6. 悬念只留给发布会的揭晓（A）：Kayvon p.40「叙事上的意外几乎总是坏事」；Winston 要求求职报告五分钟内讲出愿景（各 B，两处一致）
7. 课堂每隔一段让每个人作答一次（A）：Freeman 等 2014

**不写成规则的**：下面这些说法查过，证据不够或者有反例，路线表与七条原则都不写：

- 固定拍数或固定顺序
- 开场必须放议程
- 结尾必须放总结
- 问题必须先于揭晓：2007 年 iPhone 是反例
- 最多三点：作为讲稿规则，没找到可核实的依据（C）
- 先预测总有帮助：IES 把「用前测题引入新课」评为低证据
- 先做后讲普遍更好：对低年级与通用技能正相反
- 最后一页放参考文献：与 Winston、Peyton Jones 冲突
- 团队页必须放在收束前
- 绝不说谢谢：只有 Winston 一人这样主张
- 把 20/80、75/25、35–70% 这类比例当硬阈值

## 5. 技术选型 / Tooling

本机实测（2026-08-14，写这份 skill 的机器上）：

| 项 | 结果 |
|---|---|
| `python3 -c "import pptx"` | 1.0.2，已装 |
| Keynote.app | 已装 |
| Google Chrome | 已装（可用 `--headless --print-to-pdf`）|
| `/System/Library/Fonts` | 有 `SFNS.ttf` 等，**没有叫 "SF Pro Display" 的文件** |
| Marp / Slidev | 都没装 |

由此定的事：

1. **`.key` 不可能程序化生成**。格式私有无文档，没有库支持写入。唯一通路是生成 `.pptx` 再由 Keynote 导入。来源：[iWork 自动化文档](https://iworkautomation.com/keynote/document-export.html)

   **0.7.0 更正**：原来这条写成「AppleScript 只能控制 Keynote，不能建片」，不准确。本机 Keynote 14.5 的脚本字典里有 `make`（能新建 slide、text item、image）、`save ... as Keynote`（能存 .key）、以及 `transition properties`（含 `magic move` 枚举值）。字典里**没有任何跟出场顺序／build 有关的类**，只有 `show next`（"Advance one build or slide"）和导出选项 `all stages`（"print each stage of builds"）这两处提到 build。所以准确的说法是：片能建，转场能设，**动画建不出来**。依据是 `sdef /Applications/Keynote.app` 的输出本身。
2. **CSS 里不要写 `"SF Pro Display"`**。本机文件名是 `SFNS.ttf`，按 "SF Pro Display" 引不可靠。用 `system-ui, -apple-system` 让系统解析，既拿到 SF 又不涉及分发字体文件。
3. **python-pptx 没有动画接口**：库里没有进入退出效果、转场、动作路径的 API。来源：[slideforge 整理](https://slideforge.dev/blog/python-pptx-limitations-we-solved)。

   **0.7.0 更正**：原来这条写成「完全不支持动画」并据此告诉使用者 pptx 没有转场，那是把「库没有接口」说成了「格式做不到」。PresentationML 本身有完整的动画模型（`<p:timing>`），python-pptx 又允许直接操作底层 XML，所以动画可以自己写。做法与取证见第 15 节。
4. **reveal.js 没有单文件导出**，要手工内联；Slidev 产出多文件 dist 且需要 Node。都不满足"不装东西、单文件、离线"。来源：[reveal.js issue 788](https://github.com/hakimel/reveal.js/issues/788)、[Slidev 导出文档](https://sli.dev/guide/exporting.html)
5. **手写 HTML+CSS 最合适**：一屏一片、`scroll-snap`、零依赖、离线一致、浏览器直接打印成 PDF。

## 6. 中文排版 / CJK typography

第一轮五路检索全是拉丁文字的资料，但这个 skill 产出的几乎都是中文片子。这一节补的是最大的缺口。

| 档 | 事实 | 来源 |
|---|---|---|
| A | macOS 自 10.11 起内置苹方，Chrome 与 Safari 的 `system-ui` 在 macOS 上解析到苹方 SC。**苹方是 macOS 独占**，Windows 走微软雅黑，所以字体栈必须显式写后备 | [苹方与系统字体解析](https://gist.github.com/bitinn/42c95ed95aa3dcf155e2) |
| A | **苹方的 700/800/900 渲染完全相同**，实际字重上限是 Semibold。声明 700 拿不到更粗的字 | [CJK 字重实测](https://blog.csdn.net/zwkkkk1/article/details/100107380) |
| A | **伪粗体（算法加粗）在 CJK 上很难看**，"粗体"本来就不是中文的传统概念。缺真字重时应 `font-synthesis: none` | [font-synthesis 说明](https://www.edge-cases.com/css/font-synthesis-css) |
| A | 思源黑体与 Noto Sans CJK 是同一套字体的两个名字，自 v1.002 起用 SIL OFL 1.1，是可以合法分发的替代 | [Source Han Sans](https://en.wikipedia.org/wiki/Source_Han_Sans) |
| A | **`line-break: strict` 启用避头尾禁则**：句号逗号等不得出现在行首，开括号等不得出现在行尾。2020 年 7 月起浏览器普遍支持 | [MDN line-break](https://developer.mozilla.org/en-US/docs/Web/CSS/line-break)、[东亚换行规则](https://en.wikipedia.org/wiki/Line_breaking_rules_in_East_Asian_languages) |
| A | **`text-autospace: normal` 自 2025 年 11 月成为 baseline**（Chrome 140+、Safari 18.4+），自动在中日韩与拉丁字母数字之间插入约 1/4 em | [MDN text-autospace](https://developer.mozilla.org/en-US/docs/Web/CSS/text-autospace) |
| A | W3C 建议中西文之间留至多 1/4 em | [W3C 行内间距](https://www.w3.org/International/articles/styling/inline-space) |
| B | `line-break: strict` 只阻止**坏的**断行，不会替你挑**好的**断点。大字标题要精确控制断在哪，仍然得手写 `<br>` | [MDN line-break](https://developer.mozilla.org/en-US/docs/Web/CSS/line-break) |
| B | 中文标题行高比拉丁紧：CJK 字身框没有升降部余量。正文级 1.0–1.3，100px 以上取 1.0–1.15（**0.8.0 起被下面 A 档一行取代**） | [中文排版要点](https://pixelcake.com.tw/posts/chinese-typography-tips/) |
| B | 大字中文字距容忍度远小于拉丁，0 或轻微负值常见，正值不要超过 0.15em | 同上 |
| A | **苹果中文官网对 `:lang(zh)` 把字距一律归零**：`body`、各级标题、数字（`.stat-value`）、按钮、说明文字都写 `letter-spacing: 0em`，拉丁版里的 −0.015em 到 −0.022em 在中文里全部取消 | apple.com.cn/iphone 的 `overview.built.css`，2026-09-28 取；共 689 条 `:lang(zh)` 规则 |
| A | **苹果中文官网的中文行高比拉丁略松**：80px 标题 1.05 → 1.0875，28px 卡片标题 1.1429 → 1.25，24px 小标题 1.1667 → 1.2917，正文约 1.357 | 同上 |
| A | **苹果官网最大的标题也只用 600**：80px 的 `typography-headline-super` 与数字 `stat-value` 都是 `font-weight: 600`，正文 400；中文字体栈是 `SF Pro SC, SF Pro Display, SF Pro Icons, PingFang SC, …` | 同上 |
| A | 苹果官网的字号阶梯（拉丁基准）：80 / 64 / 56 / 48 / 40 / 32 / 28 / 24 / 21 / 19 / 17 / 12px；相邻两档的比多在 1.1 到 1.4 之间，最大标题约是正文的 4.7 倍 | 同上 |
| B | 显示级中文标题的可读字数约 8 到 15 字。中文单字信息密度高于拉丁单词，同样一张片装的**字数更少而信息更多** | [标题字数建议](https://zhuanlan.zhihu.com/p/582583945) |

## 6b. 片上文字的句式 / The grammar of slide copy

第一轮查的是"写什么"，这一节查的是"用什么句式写"。
实跑一次之后发现缺这一节：产出的文案在长度和具体性上都合格，但语气是**讲解**和**提问**，
不是发布会片子上那种**陈述**。

| 档 | 事实 | 来源 |
|---|---|---|
| A | **苹果官网英文页通篇没有问句标题**。句式是名词短语、短陈述片段、祈使句，且大量用两段式对仗（"Truly helpful. Truly yours."、"More personal. More powerful."） | 实取 [apple.com/apple-intelligence](https://www.apple.com/apple-intelligence/) |
| A | **中文页同样没有问句标题，标题末尾不加句号**。固定模式是两层：四字名词标签 + 一句短陈述——「轻松上手 / 从其他智能手机换成 iPhone，很简单」「经久耐用 / iPhone 的价值，时间可证」「环保 / 设计，为地球设想」 | 实取 [apple.com.cn/iphone](https://www.apple.com.cn/iphone/) |
| A | **章节名是单个名词**：隐私、环保、创新、iOS | 同上 |
| A | 中文文案约**八成是名词性结构**，动词被删除、后移或埋进句中 | [数英 港台陆文案对比](https://www.digitaling.com/articles/349110.html)、[张洪 苹果式中文分析](https://blog.zhheo.com/p/8657316e.html) |
| A | **动词后移／属格倒装**：写「A15 芯片的高能效」而不是「高能效的 A15 芯片」 | [张洪](https://blog.zhheo.com/p/8657316e.html) |
| A | **对仗靠字数相等与内韵，不靠词性严格相对**：「身量小，能量大」「事事拿手，轻松入手」「可重复充电，又可圈可点」 | [数英 349110](https://www.digitaling.com/articles/349110.html) |
| A | 「比大更大」翻车的三个原因：同一个字重复不产生递进只产生冗余；撞上廉价广告的语感；「比…还…」是书面古语，与现代产品主张冲突。改成「岂止于大」才成立 | [网易科技](https://www.163.com/tech/article/A5SJ41FF000915BD.html) |
| A | 大陆文案倾向省略人称；港台偶尔用「你」 | [数英 977745](https://www.digitaling.com/articles/977745.html) |
| B | 问句只作**反问式重构**用（先立预期再推翻），如「你的下一台电脑，何必是电脑」。**求解式直问（"你想要更快的芯片吗"）被明确排除** | 同上 |
| B | 口语可用但有线：判据是"一个不每天上网的读者能不能不靠语境看懂"。平台梗与过时网络语不行 | [搜狐 苹果文案口语化](https://www.sohu.com/a/493037359_339227) |
| C | "无 `我们`" —— 方向可信但只有单一来源的概括，实取页面里也确实没见到，不作为硬规则，只作倾向 | — |

英文侧（这个 skill 产出中文，但对照能看清哪些是通例、哪些是中文特有）：

| 档 | 事实 | 来源 |
|---|---|---|
| A | 片上标题约 **65% 是名词短语或最高级说法**，35% 是陈述句或祈使句。实例：「A widescreen iPod with touch controls」「All-day battery life」「1,000 songs in your pocket」 | [2007 iPhone 发布会实录](http://www.european-rhetoric.com/analyses/ikeynote-analysis-iphone/transcript-2007/)、[WWDC 2023 实录](https://www.rev.com/transcripts/apple-wwdc-2023-transcript) |
| A | **片上文字总是比口播更短、更少解释、更偏收益或断言**。片子锚定注意力，解释留给嘴 | 同上 + [Presentation Zen](https://presentationzen.com/blog/steve-jobs-and-visual-presentation) |
| A | **能省动词就省**：写「All-day battery life」而不是「The battery lasts all day」 | [Apple 文案技法整理](https://leadpages.com/blog/landing-pages-apple-borrow-apples-best-copywriting-techniques-copy) |
| B | **问句只出现在口播里，不出现在片上**。2007 年那场，片上是「A widescreen iPod with touch controls」，Jobs 嘴上说的是「Does it do email? Yeah, it does.」 | [Duarte 对 Jobs 修辞手法的整理](https://www.duarte.com/blog/rhetoric-isnt-a-bad-thing-16-rhetorical-devices-regularly-used-by-steve-jobs/)、2007 实录 |
| B | **讲机制时片上几乎不写字**：用动画或演示代替，片上只留一个名字当标注（「Multi-touch」）。技术细节走口播 | 多来源归纳，见上 |
| B | 英文片上**不用 you / we**，走产品视角。**注意这条与中文相反**——中文页会用「你」（「数据怎么安置，全听你的」） | 英文侧多来源；中文侧实取 apple.com.cn |
| B | 英文标题用句号分隔并列的名词短语（「MacBook Air. The world's thinnest notebook.」）。**中文不这么做**，中文标题末尾不加句号 | 同上 |

### 「苹果式中文」是要避开的，不是要学的

上面引的苹果中文页文案有两副面孔，写规则时必须分开对待。
**第一版规则是从官网标题推出来的，这是个错误的取材面**，这一节是修正。

「苹果式中文」在中文语境里是**批评性的词**，指苹果翻译腔那种句式：
句子结构破碎、常缺主语、滥用排比与顶真、硬拆成语、生造四字词、英文语序直译。

| 档 | 事实 | 来源 |
|---|---|---|
| A | 这个词指的是「句子结构破碎，经常缺乏主语，滥用排比、顶真、偏正短语和不恰当四字词的广告文体」 | [萌娘百科 苹果式中文](https://zh.moegirl.org.cn/%E8%8B%B9%E6%9E%9C%E5%BC%8F%E4%B8%AD%E6%96%87)（条目内容经检索摘要获得，页面本身取不到）|
| A | 典型翻车：「开发者的大事，大快所有人心的大好事」——三个「大」重复，成语「大快人心」被硬塞进「所有」，拗口 | [爱范儿](https://www.ifanr.com/426156)、[知乎相关问题](https://www.zhihu.com/question/24138410) |
| A | 手法清单：重复、双关、顶真、用错词、奇怪排比、随便拆解成语、模仿「一棵是枣树，另一棵还是枣树」，目的是制造陌生感 | 同上 |
| B | 具体机制五条：碎句子、移除主语、名词前置（「A15 芯片的高能效」）、重复与排比、删「被」字 | [张洪 苹果式中文分析](https://blog.zhheo.com/p/8657316e.html) |
| B | 同一位作者的评价：「看着觉得奇怪，但令人印象深刻」，同时承认「生涩、大量语法错误」，并指出**更适合书面语而非口头表达** | 同上 |

**由此得到的关键区分**：官网文案与片上文字的处境不一样。

| | 官网文案 | 片上文字 |
|---|---|---|
| 读者状态 | 自己停下来看，可以反复读 | 三秒扫一眼，旁边有人在讲 |
| 陌生化 | 是卖点，让人停住 | 是成本，抢走理解时间 |
| 可以承受 | 拗口、生造、语序古怪 | 一眼读不懂就是失败 |

所以**官网那套手法不能直接搬上片**。五条机制里只有「名词前置」是可以照搬的，
它不增加理解成本；其余四条在片上都是负担。

**由此定的规则**写在 SKILL.md 的「片上文字的句式」一节，例句与全文在 `references/slide-copy-grammar.md`。
中英差异那两条要分开写进规则，不能混用。

## 6c. 片上用词：苹果发布会与斯坦福、MIT 的课件 / Wording (0.9.0)

0.9.0 应使用者要求补查（2026-10-11）：片上的字还嫌多，用词要往顶尖大学的课件和苹果发布会上靠。
课件逐页抽了文字计数；苹果这边读了五场活动的官方中英字幕轨（2024-05-07、2024-06-10 WWDC24、2024-09-09、2025-06-09 WWDC25、2025-09-09；
口播，不等于屏幕上的字）和 Newsroom 的舞台照片。
**苹果舞台屏幕上的原字没能逐帧核对**（浏览器访问视频站被权限拦下），凡说到"屏幕上有什么字"的，档次按下表标。

**苹果：大字下面有没有字**

| 档 | 事实 | 来源 |
|---|---|---|
| A | 揭晓类的片只有产品图、芯片标识或名字，没有说明文字：13 张拍到大屏的官方舞台照片里，iPhone 11 Pro、Apple Watch Series 5、A13、M2、Apple TV+ 那几页都是这样 | [2019-09 活动集锦](https://www.apple.com/newsroom/2019/09/highlights-from-apples-keynote-event/)、[2019-03](https://www.apple.com/newsroom/2019/03/highlights-from-apples-keynote-event/)、[WWDC22](https://www.apple.com/newsroom/2022/06/wwdc22-highlights/) |
| A | 口播里每个数字、每个倍数都带对比对象：比 iPhone 15 快 30%、比 Series 9 薄近 10%、从 6 小时增加到 8 小时、是首代神经网络引擎的 60 倍 | 官方简中字幕：2024-09-09（0:45:53、0:09:06）、2025-09-09（0:11:56）、2024-05-07（0:20:10） |
| C | 大数字页底下是不是有一行写对比对象的小字：照片没拍到，字幕里看不出，**没有核实**。本 skill 不照它做小字：限定词与单位和数字同一行，来源与样本量写进左下的出处行 | — |

**苹果：命名与句式**（官方简中字幕与 apple.com.cn Newsroom 简中稿，A）

| 档 | 事实 | 来源 |
|---|---|---|
| A | 功能名意译，2 到 5 个字，多带一个类别词收尾：灵动岛、全天候显示、车祸检测、运动模式、光像引擎、操作按钮、待机显示、相机控制、摄影风格、同步双拍、超瓷晶面板 2 | [iPhone 14 Pro](https://www.apple.com.cn/newsroom/2022/09/apple-debuts-iphone-14-pro-and-iphone-14-pro-max/)、[15 Pro](https://www.apple.com.cn/newsroom/2023/09/apple-unveils-iphone-15-pro-and-iphone-15-pro-max/)、[16 Pro](https://www.apple.com.cn/newsroom/2024/09/apple-debuts-iphone-16-pro-iphone-16-pro-max/)、[17 Pro](https://www.apple.com.cn/newsroom/2025/09/apple-unveils-iphone-17-pro-and-iphone-17-pro-max-cn/) 简中稿 |
| A | 新概念和品牌词保留原文，中英之间留空格：Center Stage 前置摄像头、Liquid Glass（官方简中稿与字幕都没有译成"液态玻璃"）、MagSafe | 同上；2025-06-09 WWDC25 字幕 0:10:00 |
| A | 最高级说"迄今最…"，参照是自家的历史：迄今最薄、迄今规模最大的设计更新 | 2025-09-09 字幕 0:42:20；2025-06-09 字幕 0:09:06 |
| A | 条件性的指标前面带"最长""最高""最多"；比较写"是…的 N 倍""从 A 增加到 B""比 X 薄近 10%" | 最长：2025-09-09 字幕 0:35:27（播放最长 8 小时视频）、0:52:32；最高：2024-05-07 字幕 0:18:24；最多：2024-09-09 字幕 0:06:14；比较的三种写法见上一张表第 2 行 |
| A | 数字用阿拉伯数字，数字与汉字、字母之间留空格，大数用万、亿：5.6 毫米、4800 万像素、3000 尼特、38 万亿次 | 2025-09-09 字幕 0:43:08、0:35:48、0:43:26；2024-05-07 字幕 0:20:04 |
| A | 开场与收尾用同一个框架：2025-09 那场开头和结尾都说 iPhone 迄今最大飞跃 | 2025-09-09 字幕 0:02:55、1:10:41 |

**斯坦福、MIT 课件**（逐页抽文字计数，档次逐条标）。看了九套幻灯片：MIT 8.02 第 1、7 讲，8.01L 第 21、22、29 讲，18.600 第 33 讲，
6.S191 第 1 讲；斯坦福 CS231n 第 3 讲、CS106B 第 7 讲、CS224n 第 1 讲、CS161 第 1 讲、EE364a 第 1 讲。
斯坦福物理 41/43 的课件不公开，物理一侧的证据全部来自 MIT。

| 档 | 事实 | 来源 |
|---|---|---|
| A | 标题默认是话题名词短语。各套里不超过 3 个英文词的标题占 41–80%，物理课最短（8.02 两讲 70–80%） | [8.02 第 1 讲](https://ocw.mit.edu/courses/8-02-physics-ii-electricity-and-magnetism-spring-2007/576bb3137e9ce4ecc87f73f18221278d_presentati_w01d1.pdf)、[CS231n 第 3 讲](https://cs231n.stanford.edu/slides/2026/lecture_3.pdf) 等九套 |
| A | 问句标题占 0–18% | 九套统计 |
| B | 问句用来引出下一页的结论：只核到一例，8.02 第 7 讲一页末行问能量存在哪，下一页首行就答"存在电场里"（问句在页末，不在标题位置） | [8.02 第 7 讲](https://ocw.mit.edu/courses/8-02-physics-ii-electricity-and-magnetism-spring-2007/30f84e5307b76d469b9f8901964ca1cd_presentati_w03d1.pdf) |
| A | 整句结论标题占 0–9%，短而确定（Fields are 3D） | 同上 |
| A | 课堂提问用写明活动的标签：MIT 的栏目叫 Concept Questions，片上写 PRS Question 加场景名；斯坦福写 Think-Pair-Share、Interactive Session，或 Q 与 A 成对 | [8.02 课件总表](https://www.ocw.mit.edu/courses/8-02-physics-ii-electricity-and-magnetism-spring-2007/pages/class-slides)、CS161、CS224n、CS231n |
| A | 例题、小结、大纲都有固定的标签：Example、In Class Problem；Summary、Take-away、Wrap up；Outline、Lecture Plan、Today | 同上 |
| A | 物理量写成"名称 符号 [单位]"；公式的适用条件贴在式子右边的方括号里（单摆周期式旁注小角度近似） | 8.02 第 1 讲；[RES.8-009 第 2–3 讲](https://ocw.mit.edu/courses/res-8-009-introduction-to-oscillations-and-waves-summer-2017/mitres_8_009su17_lec2_3.pdf) |
| B | 例题的标题给数据：8.02 第 7 讲的例题标题是"1 Farad Capacitor"，下面是代入（只核到这一例） | 8.02 第 7 讲 |
| A | 每页正文中位数 20–66 个英文词，比发布会的片子多得多：课件要能在课后单独看 | 九套统计 |

**本 skill 怎么用这些**：发布会照苹果来，片上只有名字、数字和一句话；课堂的片子比课件少字，因为本 skill 把
课后要看的东西放进了讲义（Duarte 的 slidedoc，见第 12 节），所以只借课件的**用词**（名词短语标题、固定的活动标签、
"名称 符号（单位）"、条件贴在式子右边、例题标题给数据），不借它的字数。
问句标题在课堂里除了提问片只多放开一种：下一张片立刻用一句结论回答它。依据只有上表那一例（B），
「一节课一两处」是本 skill 定的上限，课件里没有这个数。

## 7. 数字与主张的举证 / Claim substantiation

原来那节事实校验规则是我自己编的，没有外部依据。这一节是它的依据。
**出处是美国商业广告的监管标准**，本 skill 的使用者多数在做答辩与项目演示而非广告，
所以按"什么样的数字算诚实"来用，不作为法律建议。

| 档 | 事实 | 来源 |
|---|---|---|
| A | **接近性要求**：限定条件必须"清晰醒目"且紧邻主张本身。光打一个星号指向别处的脚注不满足这个标准 | [FTC 广告举证政策声明](https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation) |
| A | **"最高可达 / up to"**：要能证明**典型用户**在正常情况下能达到那个上限，不是个别案例。依赖特定配置时，条件要写在主张旁边 | [FTC 对 up-to 主张的口径](https://advertisinglaw.fkks.com/post/102jcia/the-ftc-weighs-in-again-on-up-to-claims) |
| A | **对比性主张**：对比基准必须清楚标明，且要用当前版本而非过时的对照物。"快 3 倍"不写清比什么、哪个版本、什么时候测的，就是不合格 | [FTC 对比广告政策](https://www.ftc.gov/legal-library/browse/statement-policy-regarding-comparative-advertising) |
| A | 性能类主张的举证门槛是"有资质且可靠的证据"：有记录的方法、公开的条件、能代表典型使用场景 | [FTC 举证政策声明](https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation) |
| A | **调研数字的披露标准**：样本量、抽样方法、误差范围、调查方式、加权方式、题目原文 | [AAPOR 披露标准](https://aapor.org/standards-and-ethics/disclosure-standards/) |
| A | 苹果自己**不在数字旁边打星号**。做法是页首一句统概免责（"实际结果会有差异"），再用分区详列测试日期、机型、网络类型与条件 | [Apple 电池续航页](https://www.apple.com/iphone/battery.html) |

## 8. 图表 / Charts

**这是整套风格里唯一一处不能照抄参考对象的地方。**

| 档 | 事实 | 来源 |
|---|---|---|
| A | 纵轴截断导致系统性误读。Correll、Bertini、Franconeri 专门检验了"折线图可以豁免"这个流行说法——**不能**，折线与柱状都会被误读；而且**断轴标记也不能缓解** | [Correll et al., CHI 2020](https://dl.acm.org/doi/10.1145/3313831.3376222) |
| A | Pandey 等 330 人实验：截断纵轴造成的误读效应量为"大" | [Pandey et al. 2015](https://medium.com/@Infogram/study-asks-how-deceptive-are-deceptive-visualizations-8ff52fd81239) |
| A | **苹果自己的图表被批评过**：iPhone 累计销量图整个纵轴刻度缺失，iPad 那张低估实际销量约三成 | [Quartz 的分析](https://qz.com/138458/apple-is-either-terrible-at-designing-charts-or-thinks-you-wont-notice-the-difference) |
| A | 双纵轴通过调整两侧量程可以造出虚假相关 | [Flourish 对双轴图的说明](https://flourish.studio/blog/dual-axis-charts/) |
| A | 面积编码违反 Stevens 幂律：人对面积的感知指数约 0.7，会系统性低估；用半径编码更糟 | [编码方式与感知](https://www.datylon.com/blog/bad-data-visualization-examples) |
| A | 3D 透视让前景柱看起来比等值的背景柱大，无法比较 | [Highcharts 对 3D 图的分析](https://www.highcharts.com/blog/best-practices/3d-graph-useful-visualization-or-misleading-illusion/) |
| A | Okabe-Ito 八色板由色觉障碍研究者设计，在各类色觉障碍下都可区分 | [色觉障碍安全色板](https://glasbey.readthedocs.io/en/latest/color_vision_deficiency.html) |
| A | 红绿色觉障碍影响约 8% 男性、0.5% 女性 | [色觉障碍流行率](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12385717/) |
| B | 直接标注优于图例：图例迫使观众在图与图例之间来回，增加认知负荷与出错率。投影距离下图例基本读不到 | [直接标注与图例](https://xdgov.github.io/data-design-standards/components/labels/) |
| B | Gelman 的折中："零如果就在附近，就请它进来"——数据接近零就带上零轴，远离零（如股价 90–200）可以不带，但要明确标注 | [Observable 的讨论](https://observablehq.com/blog/never-okay-crop-y-axis-except-when-it-is) |

## 9. 投影可读性与无障碍 / Legibility and accessibility

| 档 | 事实 | 来源 |
|---|---|---|
| A | WCAG 对比度：正文 4.5:1，大字（≥18pt 或 ≥14pt 粗体）3:1；AAA 分别是 7:1 与 4.5:1 | [WebAIM 对比度](https://webaim.org/articles/contrast/)、[WCAG 1.4.3](https://www.w3.org/TR/UNDERSTANDING-WCAG20/visual-audio-contrast-contrast.html) |
| A | **颜色不能是传达信息的唯一手段**，要配文字、图标或形状 | [WCAG 1.4.1](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html) |
| A | `prefers-reduced-motion` 对应操作系统的减弱动效设置；WCAG 2.3.3 要求由交互触发的动画可关闭 | [WCAG 2.3.3](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) |
| A | 前庭功能障碍者会被快速位移、视差与自动播放触发眩晕与恶心 | [前庭无障碍](https://alistapart.com/article/accessibility-for-vestibular/) |
| A | 投影距离下无衬线优于衬线；**Thin 与 Light 字重在投影上笔画会糊掉或消失**，正文不低于 Regular(400) | [可读性指南](https://www.linearity.io/blog/legibility-vs-readability/) |
| B | AVIXA 的视距标准与 10–20 弧分的文字张角要求 | [AVIXA 显示尺寸标准](https://www.avixa.org/resources/standards/display-image-size-for-2d-content)、[Extron 字号文章](https://www.extron.com/article/videowallfontsize) |
| B | 环境光会吞掉对比度：500 lux 下，标称 1000:1 的投影机实际会掉到 50:1 以下 | [环境光与投影](https://global.xgimi.com/blogs/projectors-101/choose-projectors-in-different-ambient-light) |
| B | 深底浅字与浅底深字没有普适优胜者，**对比度比色相重要**。亮房间用浅底时要用近白而不是纯白 | [Tufte 的讨论](https://www.edwardtufte.com/notebook/recommended-background-for-projected-presentations/) |
| C | "最小字高 = 房间进深英寸 ÷ 400" —— 换算下来只有 8.6 弧分，**低于 10 弧分的可辨识下限**，这条规则是错的，不采用 | — |

### 本仓库自行推导：40px 下限站得住吗

流传的经验规则彼此矛盾（"每 10 英尺 1 英寸"是 28.6 弧分，"进深 ÷ 400"是 8.6 弧分，差三倍多），
所以直接用几何算。**结论与幕布物理尺寸无关**，只取决于字高占屏高的比例与"视距等于几个屏高"：

```
θ(弧分) = 3437.75 × (字高px / 1080) ÷ (视距 ÷ 屏高)
```

40px 下限的张角：

| 视距（屏高的倍数） | 6 | 8 | 10 | 12 |
|---|---|---|---|---|
| 张角（弧分） | 21.2 | 15.9 | 12.7 | 10.6 |

按 15 弧分的舒适阈值反推所需字高：6 屏高需 28px，8 屏高需 38px，10 屏高需 47px，12 屏高需 57px。

**所以 40px（30pt）对进深 8 个屏高以内的房间成立，深礼堂要提到 48px。**
这条独立几何推导与苹果内部那条"不低于 30pt"互相印证，两者来源完全无关。

## 10. 2023–2026 的演变 / Recent evolution

| 档 | 事实 | 来源 |
|---|---|---|
| A | SF Pro 已并入可变字体，带光学尺寸轴：20pt 以下走 Text（字距放宽、笔画加重），以上走 Display（字距收紧） | [Apple Fonts](https://developer.apple.com/fonts/) |
| A | Liquid Glass 是 WWDC 2025 发布的**系统 UI 材质**，是苹果专有的，**不出现在发布会的片子里**，只在软件演示录像中 | [WWDC 2025 报道](https://www.engadget.com/big-tech/wwdc-2025-ios-26-new-liquid-glass-design-and-everything-else-apple-announced-171718769.html) |
| A | 拟物化（真实材质、产品下方倒影、厚投影）在 iOS 7（2013）被整体废除，至今十三年。现在再用一眼就是旧年份的味道 | [iOS 7 与拟物化的终结](https://applescoop.org/story/the-end-of-skeuomorphism-how-ios-7-changed-ui-design) |
| C | bento 网格的构图规矩：一张片 8–12 格，超过 12 格构图垮掉；锚点格面积约为支撑格的两倍；格子里放数字而不是标题。**0.8.1 由 B 降为 C**：这是一篇博客的经验之谈，没有量过；苹果 2022–26 年的收尾总结图实测格数中位数 16、九成以上不少于 14 格（`bento-infographic/references/apple-measurements.md`），「超过 12 格就垮」和实物对不上 | [bento 版式拆解](https://www.deck.gallery/blog/apple-bento-grid-breakdown/) |
| B | **bento 已经用滥**：2024 年后"每个 SaaS 落地页都默认用它"，设计圈批评其同质化。较好的做法是混合媒介、有意打破对齐 | [bento 实践指南](https://www.saasframe.io/blog/designing-bento-grids-that-actually-work-a-2026-practical-guide/) |
| B | "one more thing" 自 2014 年 Apple Watch 之后基本停用；独角戏式的空台揭示被多人分段与预录片段取代 | [one more thing 清单](https://www.macworld.com/article/674643/every-one-more-thing-apple-has-ever-announced.html) |
| B | Liquid Glass 上线后被批评可读性下降：文字与壁纸混在一起、半透明图标与背景糊成一片，被拿来类比 Windows Vista Aero | [对 Liquid Glass 的批评](https://medium.com/macoclock/apple-has-dressed-its-operating-systems-in-liquid-glass-551d1ef991b4) |

## 11. 反"发布会腔"/ Against the register

研究里没有这一条，但它是这套风格最容易翻车的地方，所以写进规则。

这套视觉语言天生鼓励空洞的最高级："革命性"、"魔法般"、"这改变了一切"、"重新定义"。Jobs 用这些词时下面垫着真东西（多点触控、一千首歌、从信封里抽出来的厚度）。**词是垫出来的，不是贴上去的。**

所以：形容词要么有一个能指回材料的数字或事实垫着，要么删掉。这一条与本仓库 `writing-rules` 的立场一致。

## 12. 课堂与讲堂 / Lectures and classrooms

2026-09-17 为扩到课堂与讲堂补查。发布会的做法大多能搬，**有三处与学习研究直接冲突**，按研究改。

| 档 | 事实 | 来源 |
|---|---|---|
| A | **主张句标题加视觉证据优于「短语标题加项目符号」**。110 名工科本科生随机分两组看同一段 MRI 讲解（同一份 1000 词旁白）：主张句组论述题总分显著更高，t(93.43) = 3.67，p < 0.001，d = 0.81；误解更少，d = 0.47。主张句组的标准是「标题不超过两行、每张配相关图、正文字数尽量少」，平均每片 21.2 词，对照组 41.5 词 | [Garner & Alley 2013, IJEE 29(6)](https://writing.engr.psu.edu/ae_comprehension.pdf) |
| A | **上面那个效应不能单独归给标题**。主张句组同时减少了字数、每张都有图，而且 11 张里有 8 张的图是讲到才出现，对照组没有动画。是一整套做法的效应 | 同上，2.2 节 |
| C | 「主张句标题里的要点比项目符号里的更容易被回忆」常被归到 Alley 等 2006 —— 本次只在搜索摘要里见到，没读到原文；[WUSTL 教学中心](https://ctl.wustl.edu/in-powerpoint-its-the-headline-that-makes-the-difference/)那页转述的其实是上面 2013 年那项。不作为依据（**0.10.0 起被第 12b 节 Alley 等 2006 那行的 A 档取代**） | — |
| A | **课前小测在真实课堂里有效**：学期末考试中，考过的内容与没考过但相关的内容都有提升；机制可能是课上注意力更集中、课后自学更有方向。形式是短、低风险的选择题 | [Soderstrom & Bjork 2023, Educ Psychol Rev 35:88](https://link.springer.com/article/10.1007/s10648-023-09805-6) |
| A | **在真实讲课录像里，课前提问的效果是正向但有限的**（二十分钟以上的真实课程录像，信号检测论与自传体记忆两门） | [Toftness, Carpenter, Lauber & Mickes 2018, JARMAC](https://pure.royalholloway.ac.uk/en/publications/the-limited-effects-of-prequestions-on-learning-from-authentic-le/) |
| A | 较短的教学视频里，分段前提问能提升记忆 | [Carpenter & Toftness 2017, JARMAC 6(1)](https://www.sciencedirect.com/science/article/abs/pii/S2211368116301103) |
| — | **先用题目引入新课，证据等级低**（0.10.0 补）：IES 实践指南把「用前测题引入新课」评为低证据。这是 IES 自己的分级，不另折成 A/B/C。所以预测题是一个选项，不保证有效 | IES 实践指南，Pashler 等 2007 |
| A | **先试后讲有反转条件**（0.10.0 补）：Sinha 与 Kapur 2021 的元分析里，先让学生试、再讲解，总体 g = 0.36；但对小学二至五年级和通用技能，先讲后练占优。更多的前提与预测型演示的数据见第 4b 节 | Sinha & Kapur 2021，RER |
| A | **练习测验优于重读与其他对照**（217 项研究的元分析）。所以回顾片要先让人提取，再揭晓 | [Adesope, Trevisan & Sundararajan 2017, RER 87(3)](https://journals.sagepub.com/doi/abs/10.3102/0034654316689306) |
| A | **先学部件的名称与状态，再学系统怎么运作**，三个实验的迁移测验都更好（预训练原则） | [Mayer, Mathias & Wetzell 2002](https://pubmed.ncbi.nlm.nih.gov/12240927/) |
| A | 冗余原则：图加旁白优于图加旁白加同样的屏幕文字；信号原则：给要点加提示有益；分段原则：分段呈现有益（原文指学习者自控节奏的分段）。冗余原则在 2021 汇总里变弱，0.10.0 起只作旁证，见第 12b 节 | [Mayer《多媒体学习》](https://assets.cambridge.org/97805217/35353/frontmatter/9780521735353_frontmatter.pdf) |
| A | **信号原则的元分析**：27 项研究、2464 人，理解与迁移的效应 r = 0.17，先验知识少的学习者受益更明显 | [Richter, Scheiter & Eitel 2016](https://www.sciencedirect.com/science/article/abs/pii/S1747938X15000664) |
| A | **诱惑性细节效应**：有趣但与内容无关的图和细节会拖累学习，68 项研究的元分析 | [Sundararajan & Adesope 2020](https://link.springer.com/article/10.1007/s10648-020-09522-4) |
| A | 纠正误解时，「指出误解 + 标明它不对 + 给出正确解释」三段式比只讲正确解释更有效 | [Tippett 2010 综述](https://eric.ed.gov/?id=EJ905216) |
| A | 工作样例的设计原则：好的例题各部分高度整合，**用标注或分段把概念结构显出来**；一类问题配多个例题。推演片右栏写「这一步凭什么成立」就是这条的做法 | [Atkinson, Derry, Renkl & Wortham 2000, RER 70(2) 181–214](https://journals.sagepub.com/doi/10.3102/00346543070002181) |
| A | 苹果自己的演示课：「一场演示应当是对话……问他们问题，让他们一直在线」；「先勾画叙事」；「对比今天的现实与可能的未来」 | [WWDC18「Presenting Design Work」](https://developer.apple.com/videos/play/wwdc2018/811/) |
| B | **拿在手里读的文档与投影片是两种东西**：前者要能脱离讲的人独立读懂，后者不行。Duarte 称前者为 slidedoc | [Duarte, Slidedocs](https://www.duarte.com/resources/guides-tools/slidedocs-visual-documents/) |
| B | 2007 年 iPhone 发布会有「给路标」与「段间回顾」两个动作 | [Gong](https://www.gong.io/blog/steve-jobs-iphone-keynote) |
| C | 苹果发布会结尾有一张汇总所有发布内容的回顾片 —— 没找到可引的一手描述，不作为依据 | — |
| C | 提问片一节课放几道最合适 —— 没有找到直接实测。「两三道、放在最要紧的概念前后」是据上面两项研究的效应大小做的判断 | — |

**结论性判断**：课堂与讲堂的证据片用主张句；允许真要作答、当场揭晓的提问片，少而准；
回顾先提取后揭晓；名字先于机制；图必须是证据；讲义与投影分开。
主张句那条的效应量大，但要记住它是一整套做法的效应。

0.10.0 补：预测题的效果有限，IES 把「用前测题引入新课」评为低证据；先试后讲对低年级与通用技能会反过来。
所以「先猜后讲」只是课堂路线里的一条，不是默认。主张句压到一行，学术片少字的依据见第 12b 节。

## 12b. 学术片少字（0.10.0）/ Fewer words on academic slides

0.10.0 应使用者要求补查（2026-10-13）：学术讲座的片子借发布会少字的做法，结合斯坦福、MIT 的课件，减少片上的字，突出主体和重点。
规则写在 `references/classroom.md`「学术片怎么少字」，SKILL.md「场合」里是摘要。
分四块：讲演与课件指南、实验与研究、实例页、不采纳的做法。同一个来源在这里和第 4b 节的档次可能不同，各按各自那部分调研记的档。

**讲演与课件指南**

| 档 | 事实 | 来源 |
|---|---|---|
| A | Winston 说过的：页总是太多，字总是太多（25:12）；不要念片子，片子是佐料，不是主菜（约 26:26）；改稿顺序是删背景装饰 → 删字 → 删 logo（27:08）→ 删标题（27:17）；人只有一个语言处理器；不用激光笔，改在图上画箭头（约 29:43–31:38）；打印出来铺开，看哪张太重（约 31:52）；一场只许一张故意复杂的片，即 hapax legomenon（约 33:25） | Winston《How to Speak》逐字稿 p.6–8，MIT OCW RES.TLL-005（2018 IAP） |
| B | 上面这些做法有没有效果，是 Winston 自己的判断 | 同上 |
| C | Winston 提到的学生小实验没有发表 | 同上 |
| A | MIT Comm Lab 生物工程系（BE）：标题写成说出要点的整句；理想情况下，全页唯一的完整句就是标题；字越多，越控制不住观众看哪里；把此刻不讲的数据调灰；用颜色、箭头、标签强调；分步揭示 | [BE Slideshow](http://mitcommlab.mit.edu/be/commkit/slideshow/) |
| A | MIT Comm Lab 核科学与工程系（NSE）：标题含主要结论；用注释把观众引到图或公式的关键处；公式里暂时无关的部分调灰；一个基础色加一个强调色 | MIT Comm Lab NSE「Slide design」 |
| A | MIT Comm Lab 机械系（MechE）：标题是一行讲清重要性的短语；设计类报告偏好短标题 | MIT Comm Lab MechE |
| A | MIT Comm Lab 土木与环境系（CEE）三篇：只留支撑论点的那个面板，用箭头标出原本只写在图注里的发现；结论页放前文图的缩略版 | [CEE：结论页用缩略图](https://mitcommlab.mit.edu/cee/2024/02/01/using-miniature-figures-to-enhance-your-conclusion-slides/) 等三篇 |
| A | MIT 20.020（2009 春）：话题式标题只交代「是什么」，不说「所以呢」；观众要么读，要么听 | MIT 20.020 课程材料 |
| A | Kayvon Fatahalian：展示而不是描述（p.28）；观众不想自己解读图（p.38）；解释图里每个元素，并说明高亮色的含义（p.44）；讲结果图的顺序是要回答的问题 → 坐标轴 → 唯一的结论（p.46–47）；结果页一页一个结论，写进标题（p.48–49）；结果页不放无关数据，往往要把论文里的图重画（p.52）；标题连起来读就是摘要（p.54） | [cleartalktips.pdf](https://graphics.stanford.edu/~kayvonf/misc/cleartalktips.pdf)（2023-11 版） |
| A | 斯坦福 ENGR 103《Visual Aids》：按冗余与信号原则大幅减字，标题用一句说出主旨（p.4）；一页一个观点（p.5）；字号不小于 24 磅（p.8）；图例直接标在图上（p.12–13）；可以按 B 黑屏（p.16）。它也建议每页放机构 logo，这条不采纳 | [ENGR 103 讲义](https://web.stanford.edu/~mvassar/handouts/Week%203%20-%203%20-%20Visual%20Aids%20Lecture%20Notes.pdf) |
| B | 斯坦福 OCP：文字少用，一页一个概念，细节进讲义 | 斯坦福 OCP |
| A | CWSEI 汇编（Wieman 在斯坦福开的课的学生汇编）：一页一个信息，由标题概括；装饰性背景有认知成本；不需要画面时放空白页；讲课用的片子与复习笔记分成两套 | [CWSEI Cognitive Load](https://cwsei.ubc.ca/files/resources/instructor/Cognitive-Load_CWSEI.pdf) |

**实验与研究**

| 档 | 事实 | 来源 |
|---|---|---|
| A | **Garner 与 Alley 2013**（对原文核过）：主张句组的设计标准是句子标题不超过两行、配相关图、正文尽量少（p.9）；110 人随机分组（59 对 51）；主张句组每页 21.2 词、每页都有相关图、8 张讲到才出现，对照组 41.5 词、64% 有相关图、没有动画 | [Garner & Alley 2013, IJEE 29(6)](https://writing.engr.psu.edu/ae_comprehension.pdf) |
| A | 同上，结果：论述题 d = 0.81；误解 d = 0.47；延迟测验 d = 0.89；心理负荷 d = −0.50。即时选择题只有推理题是主张句组占优 | 同上 |
| A | 同上，要说准的地方：主张句组自评先备知识更高，但与成绩不相关；两组各给自己那套片的字量打分，主张句组反而更低（3.87 对 4.41，7 分制，d = −0.60；两组没看过对方的片）；论文讨论部分写明五条多媒体原则同时用上，是一整套做法 | 同上 |
| B | Wolfe、Alley 与 Garner 2012 复验：对照组也用了同样设计的图后，主张句组只剩不显著的正向趋势。这次 ASEE 页面返回 403，没能复核，转述自 2026-10-13 的调研；只写在 references 里，不进示例片 | Wolfe, Alley & Garner 2012，ASEE |
| A | Alley 等 2006（弗吉尼亚理工的地学大课，非随机）：句子标题组 15 题回忆 79% 对 69%；示例标题 7–16 词 | Alley 等 2006，ASEE |
| A | **Yue、Bjork 与 Bjork 2013**：屏幕文字与旁白逐字相同，学得最差；稍作改写的缩写句比逐字版好（d = 0.95），迁移比不放字好（d ≈ 0.6）；学习者自己偏好逐字版 | J. Educ. Psych. 105(2):266–277 |
| A | Mayer 的原则：一致性原则（删无关内容）23/23，中位 d = 0.86；空间邻近 22/22，中位 d = 1.10；信号原则 24/28，中位 d = 0.41（2021：15/16，0.69）；多媒体原则 13/13，d = 1.35 | Mayer 与 Fiorella 2014 汇总；2021 汇总 |
| A | **冗余原则变弱**：2021 汇总里只剩 8/12，中位 d = 0.10。所以 0.10.0 起「一张片一层字」改以一致性原则、信号原则与 Yue 2013 为主，冗余原则只作旁证 | 2021 汇总 |
| B | Schneider 等 2018 信号元分析：保持 g = 0.53、迁移 g = 0.33；在图上做颜色高亮对迁移有效，闪烁有害。只读了摘要 | Schneider 等 2018 |
| B | Schroeder 与 Cenkci 2018 空间邻近元分析：g = 0.63 | Schroeder & Cenkci 2018 |
| C | 主张标题能多短：没有研究直接比较过长短不同的主张标题 | — |
| A | 「两行」是 Alley 体系的上限，不是目标 | 见上面 Garner 与 Alley 2013、Alley 等 2006 两行 |
| A | 斯坦福、MIT 真实页面上的主张标题有 3–13 个英文词 | 下面的实例页 |

**实例页**

| 档 | 事实 | 来源 |
|---|---|---|
| A | 斯坦福 CS149 2025 秋第 1 讲（Kayvon 与 Olukotun）第 50 页：一张借来的趋势图，两个红框框住曲线变平的区段，框外各配一条约 5 词的短标签 | 课件截图，目视 |
| A | 同上第 56 页：产品名加一行大字「64 核、4.3 GHz」，加一个红箭头与一个短标签 | 同上 |
| A | 同上第 48 页：一条红色折线，没有图例 | 同上 |
| B | MIT 6.S191 2026 第 1 讲第 75–77 页：每次点击换一句结论 | 课件，OCR |
| B | 斯坦福 CS231n 2026 第 2 讲第 25–27 页：红框加红字标签 | 课件 |
| B | MIT 8.02 2007 第 1 次课第 38 页：两幅可视化，各配一个词的标签 | 课件 |
| C | 页脚、页码和机构标识对学习有什么影响，没有直接研究。上面这几套课件（CS231n、6.S191、CS149、8.02）普遍保留它们，和 Winston「删 logo」相反 | — |

**不采纳**：

- Winston「证据片也删标题」：与 Kayvon、MIT Comm Lab、Garner 与 Alley 冲突。删标题只用于纯图片片、分节片、提问片
- 苹果式「证据页只放一个词或一张图，没有判断句」：Yue 2013 显示一句短结论比不放字好；Durand 也要求关键观点上片
- 把冗余原则当减字的主要依据
- 把 d = 0.81 记在句子标题一项上
- 把每页 21.2 词当指标
- 每页放 logo
- 用 Winston 学生的小实验当数字依据
- 问句标题当默认：Alley 2006 里问句改成句子后，有升有降

**字号备查**：斯坦福 OCP、ENGR 103 与 Durand 的 24 磅下限，约合本模板 1920×1080 画布的 48px（本 skill 的 40px 约合 20 磅）。
本轮不改下限，记作备查。

## 13. 出场顺序与跨片连续 / Builds and continuity

| 档 | 事实 | 来源 |
|---|---|---|
| A | Keynote 的出场时机有四种：转场之后、点击时、与第 N 个同时、第 N 个之后；可在「出场顺序」窗口里拖动调整 | [Apple 支持：更改出场顺序与时间](https://support.apple.com/guide/keynote/change-build-order-and-timing-tan3ad5f8d82/mac) |
| A | 苹果动效准则：有目的地加动效，不为动而动；让动效可选，不能只靠它传达重要信息；反馈动画简短精确；让人能打断动效，不必等它放完 | [Apple HIG · Motion](https://developer.apple.com/design/human-interface-guidelines/motion) |
| A | **动画未必比静图好**：动画常常太快太复杂，违反「可理解性原则」；许多连续过程在人的理解里本来就是一串离散步骤 | [Tversky, Morrison & Bétrancourt 2002](https://hci.stanford.edu/courses/cs448b/papers/Tversky_AnimationFacilitate_IJHCS02.pdf) |
| A | Chrome 109（2023 年 1 月）起默认启用 MathML Core 的原生渲染 | [Igalia](https://www.igalia.com/2023/01/10/Igalia-Brings-MathML-Back-to-Chromium.html)、[Frédéric Wang](https://frederic-wang.fr/2023/01/31/mathml-in-chrome-109/) |
| A | WCAG 2.3.3：由交互触发的动效应能关闭；`prefers-reduced-motion` 是对应的系统设置 | WCAG 2.1 |
| C | 发布会里文字出场的具体效果与时长 —— 没有公开实测，模板的 320ms 是本仓库的取值 | — |

**本仓库实测**（2026-09-17，macOS 上的 Chrome，STIX Two Math）：

- 120px 的公式，一级上下标 84px、二级 66px，顶层分式的分子分母保持 120px，嵌套分式 84px
- 72px 的行内公式，分式的分子分母 50.4px，再往里一层 39.6px，破 40px 下限
- 缩放比例来自字体的 MATH 表（约 70% 与 55%），换字体会变，换了要重测
- 调暗用透明度叠乘时，深色主题下次要字从 0.62 乘到约 0.28，对比度掉到 1.7:1；
  改成统一换到 `--faint`，最坏底色下深色 3.99:1、浅色 3.40:1

## 13b. 让注意力留在讲的人身上（0.10.0）/ Attention on the speaker

0.10.0 应使用者要求补查（2026-10-13）：片子要和讲的内容结合在一起，让注意力在讲的人身上，不在 PPT 上。
SKILL.md「让注意力留在讲的人身上」六条的依据都在这里。

| 档 | 事实 | 来源 |
|---|---|---|
| B | 字多的片，注视更多 | LeFebvre 等 2022 |
| B | 真实课堂里，文字区获得显著更多的注意 | Yang 等 2013 |
| B | 学生大部分时间看新出现的片上内容，不看讲者。样本小 | Rosengrant 等 2011 |
| B | 209 人：常规片子压低了对只靠口述的信息的记忆，精简片子没有 | Wecker 2012 |
| A | 57 项研究：只显示关键词，比显示全文好 | Adesope 与 Nesbit 2012 |
| B | 运动起始会抓走注意。推论：每个 build 都把视线拉走一次 | Abrams 与 Christ 2003 |
| A | 综合上面几行：「字多就把视线拉到屏幕、压低听讲」，多个来源方向一致 | 同上几项 |
| C | 字少了，观众多看讲者多少：没有定量数据 | — |
| A | **时间邻近原则**：图和对应的话同时出现，比先后出现学得好 | Fiorella 与 Mayer 2021 |
| A | **Glance Test**：每页三秒内看懂 | [Duarte](https://www.duarte.com/resources/guides-tools/the-glance-test/) |
| A | Winston 的逐字稿里没有「切黑屏」的论述（否定性核查） | Winston《How to Speak》逐字稿 |
| B | 乔布斯会让屏幕短暂变空 | Garr Reynolds 的描述 |
| B | 在片里预置纯黑页，不靠临场按 B；临场按 B 再恢复，会把观众拉回上一页 | Bert Decker |
| A | Keynote 与 PowerPoint 都有 B 黑屏、W 白屏 | 两家的官方支持文档 |
| B | 2007 年 iPhone 发布时，乔布斯每说出一个产品名，屏幕上对应的图标就出现，动画按台词编排 | Ravi Agrawal《India Connected》 |

**六条各指回哪几行**：

1. 三秒测试：Glance Test（A）
2. 屏上不放讲稿原句：上表眼动与实验那几行，综合 A；其中 Adesope 与 Nesbit 2012 是 A，Wecker 2012 是 B；再加第 12b 节 Yue 2013（A）
3. 静场片预置在片单里：Reynolds、Decker（B）；B 键黑屏只当应急，恢复时会拉回上一张（Decker，B）。Winston 的逐字稿里没有这条（A，否定性核查）
4. 每一步对着一个卡点出现：时间邻近原则（A）；2007 年 iPhone 的动画按台词编排（B）。每个 build 都拉走一次视线（Abrams 与 Christ 2003，B），所以对不上一句话的 build 不要加
5. 不用激光笔：Winston 约 29:43–31:38，见第 12b 节（说过什么 A，效果判断 B）
6. 一场最多一张故意复杂的片：Winston 的 hapax legomenon，约 33:25，见第 12b 节（说过什么 A，效果判断 B）

## 14. 照片与叠字 / Photographs and overlays

| 档 | 事实 | 来源 |
|---|---|---|
| A | 文字压在背景图上时，对比度按字下面最不利的那部分算；背景图让对比度不足属于 WCAG 1.4.3 的失败情形 | [W3C F83](https://www.w3.org/TR/WCAG20-TECHS/F83.html) |
| B | 常用做法是在图与字之间加一层半透明的纯色遮罩，让字下面的底色可控、可计算 | [W3C 1.4.3 理解文档](https://www.w3.org/TR/UNDERSTANDING-WCAG20/visual-audio-contrast-contrast.html) |
| C | 「60% 黑遮罩对任何照片都够 4.5:1」这类说法 —— 来源是工具网站，本仓库不引，自己算 |

**本仓库自行计算**（按浏览器在 sRGB 空间做透明度合成，最坏情况是遮罩下为纯白像素）：

| 目标对比度 | 纯黑遮罩至少 |
|---|---|
| 3:1（大字底线） | 0.420 |
| 4.5:1（正文底线） | 0.540 |
| 7:1（本 skill 的投影目标） | 0.650 |

模板取 0.72：白字 9.29:1，0.78 白的小字 6.46:1。

**照片的隐私**：手机照片的 EXIF 常带 GPS 坐标（EXIF 标签 0x8825）。`inline_images.py` 重新编码 JPEG 与 PNG 时不带原元数据，
自检里用一张写了 GPS 的图验证过内联后已清除。

## 15. pptx 里的动画 / Animation in pptx

pptx 那条路要不要动画，卡在「XML 到底怎么写」上。规范只说了元素和属性，没说 PowerPoint 认什么组合，
所以这一节的 A 档事实分两种来源：**微软的规格文档**，和**让 PowerPoint 自己写一遍**。

### 15a. 让 PowerPoint 自己写（本机取证，2026-09-17）

做法：python-pptx 生成一份只有文本框的 pptx，用 AppleScript 让 PowerPoint for Mac 16.112 给这些文本框
加上各种动画与转场，再存回 .pptx，然后读它写出来的 XML。这比照规范推可靠，因为写出来的就是它自己认的。

| 档 | 效果（PowerPoint 的名字） | XML |
|---|---|---|
| A | 淡入 | `presetID="10" presetClass="entr"`：`<p:set>` 置 `style.visibility` 为 visible，加 `<p:animEffect transition="in" filter="fade">` |
| A | 浮入（上浮） | `presetID="42" presetClass="entr"`：同上再加两条 `<p:anim>`，`ppt_x` 原地不动，`ppt_y` 从 `#ppt_y+.1` 到 `#ppt_y` |
| A | 淡化（退场） | `presetID="10" presetClass="exit"`：`<p:animEffect transition="out" filter="fade">`，末尾把 `style.visibility` 置 hidden |
| A | 字体颜色 | `presetID="3" presetClass="emph" presetSubtype="2"`：`<p:animClr clrSpc="rgb" dir="cw">` 打在 `style.color` 上，`<p:cBhvr override="childStyle">` |
| A | 点击才开始 | 每次点击是一层 `<p:par>`，外层 `<p:cond delay="indefinite"/>`，内层 `delay="0"`；这一步的第一个效果 `nodeType="clickEffect"`，其余 `withEffect` |
| A | 与上一步同时／上一步之后 | 同时是 `withEffect`；之后是另起一组并把 `delay` 设成前面的总时长，`nodeType="afterEffect"` |
| A | 构建列表 | `<p:bldLst>` 里每个 (`spid`, `grpId`) 一条 `<p:bldP>`，同一个形状上第 n 个效果的 `grpId` 是 n − 1；存盘时按 spid、grpId 排序 |
| A | 下一次点击时调暗 | 挂在效果自己的 `<p:subTnLst>` 里：`<p:animClr>` 打在 `ppt_c` 上，`<p:cTn ... masterRel="nextClick" afterEffect="1">` |
| A | 淡入淡出转场 | `<mc:AlternateContent>` → `<mc:Choice Requires="p14">` → `<p:transition p14:dur="320"><p:fade/></p:transition>`，`<mc:Fallback>` 里是不带时长的同一个转场 |
| A | 平滑（Morph）转场 | `<mc:Choice Requires="p159">` → `<p:transition p14:dur="480"><p159:morph option="byObject"/></p:transition>`，Fallback 是 `<p:fade/>` |

顺带两个坑，都是实测撞出来的：

- **旧版的「动画设置」接口会毁掉整条时间线**。用 AppleScript 的 `animation settings`（`after effect`、`dim color`
  那一套，对应 PowerPoint 2003 的模型）设一次调暗，PowerPoint 会把这张片上已有的动画全部重建成最简单的
  「出现」，淡入、上浮、字体颜色全丢。所以调暗不用这个接口，用一条独立的字体颜色效果。
- **读动画属性会让 PowerPoint 崩退**。`repeat with e in (effects of ...)` 里取 `name of e`、`timing of e`
  时，PowerPoint 16.112 直接退出（AppleScript 收到 -609）。统计 `count of effects` 没问题。

### 15b. 微软与苹果的文档

| 档 | 事实 | 来源 |
|---|---|---|
| A | `morph` 元素在 `p159` 命名空间，类型 `CT_MorphTransition`，`option` 属性必填 | [MS-PPTX 2.6.1.1 morph](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/68d26d78-f7f5-47ab-835d-4e6c82ff39f0)、[CT_MorphTransition](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/41ca8fbf-efc8-49ac-8a32-7bd0856544bd) |
| A | `option` 三个取值：`byObject`（对象）、`byWord`（词）、`byChar`（字符） | [ST_TransitionMorphOption](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/22e711ee-35a7-42cb-b87c-1c277ec11070) |
| A | 转场扩展元素挂在 `sld` 的 `AlternateContent` 下，Choice 按命名空间分 p14 / p15 / p159，另有 Fallback | [MS-PPTX 2.2.1 Slide Transition Extensions](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/22ebe6b5-2ade-43d9-977a-98fa194725c2) |
| A | `p14:dur` 指定「转场从开始到结束的时间」 | [MS-PPTX 2.3.2.3 dur](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/9032bdb2-b273-470b-8ac4-c98a8c944494) |
| A | Morph 配对规则：相邻两片上**同类型**的两个对象，名字以 `!!` 开头且相同，就会被强制配成一对；一个 `!!名字` 在一张片上要唯一；`!!` 对象不会和非 `!!` 对象配对 | [微软支持：Morph transition tips and tricks](https://support.microsoft.com/en-us/office/morph-transition-tips-and-tricks-bc7f48ff-f152-4ee8-9081-d3121788024f) |
| B | Keynote 导入 PowerPoint 时「支持大多数对象 build」「支持大多数转场」，转场时长支持 | [Apple：Keynote 兼容性](https://www.apple.com/uk/keynote/compatibility/) |
| C | Keynote 导入后 Morph 会不会变成 Magic Move、字体颜色效果还剩不剩 —— **本轮没有验证**，苹果那页也没提 Morph | — |

### 15c. 本仓库实测（2026-09-18，PowerPoint for Mac 16.112）

- **对 ECMA-376 的 `pml.xsd` 校验**：生成的三份示例共 49 张片全部通过。同时做了反面对照
  （把 `presetClass` 改成非法值、`morph option` 改成非法值、`bldLst` 里插一个非法元素），都能被拦下，
  说明校验确实在查这些地方。另注：pptx 技能自带的 `validate.py` 对这三个错误都判通过，**不能用它验动画**
- **PowerPoint 读回再存出来**：17 张片的课堂示例，16 张的动画 XML 与我们生成的一字不差，
  第 17 张只差 `xmlns:p159` 声明在哪一层（PowerPoint 提到了 `AlternateContent` 上）。
  它读到的效果数量与转场也对得上（第 9 张读成 `morph by object`，时长 0.48 秒）
- **导出视频逐帧看**：提问片点击后，正确选项转成重点色、其余两个掉到 faint、依据那行淡入——
  说明 `override="childStyle"` 的换色能盖住我们给每个 run 写死的颜色（这一点从 XML 看不出来）。
  Morph 过渡中间那一帧，屏幕上只剩配对的那个符号在移动，两张片的其余部分都在溶解
- **本仓库的取值**（不是苹果或微软的参数）：出现／退场／换色 320ms、Morph 480ms、上移舞台高度的 16/1080。
  PowerPoint 自己的默认值分别是浮入 1 秒、字体颜色 2 秒、Morph 2 秒、上移 10%
- **没验证的**：Keynote 导入、Google Slides 导入、Windows 版 PowerPoint、LibreOffice（本机没装）
