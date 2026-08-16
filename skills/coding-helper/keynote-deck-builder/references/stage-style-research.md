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

**换算**：30pt = 40px（1pt = 1/72 英寸，CSS 里 96dpi）。所以 1920×1080 的 HTML 舞台上，任何文字的 `font-size` 不低于 **40px**。

## 2. 版式原型 / Slide archetypes

十四类反复出现的片型。分层靠**格子大小**，不靠列表缩进。

| # | 原型 | 构成 |
|---|---|---|
| 1 | 标题卡 | 一句标题 + 一个视觉主体（产品图 / 视频 / 渐变底）|
| 2 | 单句大字 | 超大字号一句短话，配极少视觉。为三秒内读完设计 |
| 3 | 大数字 | 巨大数字占据画面，下面一行小字说明。**一张片只放一个数字** |
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
| B | Magic Move 是招牌转场：对象从上一张平滑移到下一张 | [Magic Move 教程](https://business.tutsplus.com/tutorials/keynote-magic-move--cms-31554) |
| B | Apple 不公开发布真正的舞台模板文件；第三方"发布会风格模板"都是仿的 | [Apple 设计资源](https://developer.apple.com/design/resources/) |
| C | 底色是"灰→深蓝→近黑的渐变加轻噪点" —— 只有一个 Quora 回答说过，方向可信但不能当定论，也没有可靠的十六进制值 | — |
| C | 动效时长（1.0 秒溶解、0.3–0.5 秒短揭示）—— 这些是 **Keynote 应用的默认值**，不是对真实发布会的实测 | — |

**结论性判断**（据 A/B 档推出，写进规则）：底色用近黑的多层渐变而不是纯黑，浅色主题用近白而不是纯白；重点色一支为主；产品位放占位图。

## 4. 叙事结构 / Narrative

这一节对"从演讲稿生成片子"最关键。

| 档 | 事实 | 来源 |
|---|---|---|
| A | **片子不重复讲稿的句子**。片是覆在讲话之上的一层，不是承载信息的主体；焦点是讲的人。Jobs 有过五分钟只对着 33 个字讲的段落 | [Camillieri](https://medium.com/adventures-in-consumer-technology/this-is-how-we-make-slides-at-apple-b8a84352bf6d)、[Presentation Zen](https://presentationzen.com/blog/steve-jobs-and-visual-presentation) |
| A | **不照读片子**。讲的人重复片上文字会造成认知过载，大脑要同时读和听 | 同上 |
| A | **问题先于产品**。先让人感到现状的挫败、"投入到问题里"，再给解法。用人话讲问题（"你不希望你的手机能……？"），不用技术约束讲 | [Gong 对 2007 iPhone 发布会的拆解](https://www.gong.io/blog/steve-jobs-iphone-keynote) |
| A | Duarte 的结构：确立"现状"（对手/问题），转向"可能"，中段在两者间来回摆荡，最后收到产品带来的新常态 | [Duarte TED](https://www.ted.com/talks/nancy_duarte_the_secret_structure_of_great_talks)、[Resonate](https://www.duarte.com/resources/books/resonate/) |
| A | **三的法则**：工作记忆约容纳三个块，三是避免过载的最优数。分段和段内分点都用三 | [Gallo](https://www.carminegallo.com/books/presentation-secrets-of-steve-jobs/)、[Slidegenius](https://www.slidegenius.com/blog/apple-presentations-3) |
| A | 数字出场时，**这个数字是片上唯一的文字**，随口播同时落地，留一拍让人消化再展开。一张片最多一个统计数字 | [Inc. / Gallo](https://www.inc.com/carmine-gallo/since-apples-new-product-launch-number-100-million-keeps-popping-up-its-not-accidental.html) |
| A | 复杂概念一律用熟悉物类比落地："思维的自行车"、"一千首歌装进口袋"、从信封里抽出 MacBook Air | [Forbes / Gallo](https://www.forbes.com/sites/carminegallo/2026/04/01/the-simple-strategy-that-made-steve-jobs-so-good-at-explaining-complex-ideas/) |
| B | 九拍结构：打破现状 → 展示收益 → 在痛与益之间反复 → 早早给出核心揭示（iPhone 在第 3 分钟）→ 每约 9 分钟换节奏（换人、换演示、换故事）→ 简化片子 → 多用人称代词 → 给路标 → 段间回顾 | [Gong](https://www.gong.io/blog/steve-jobs-iphone-keynote) |
| B | 整场约 88 分钟 | 同上 |
| B | Cook 时代比 Jobs 时代多用约 24.9% 的统计数字，演讲者从一两人变成 90 分钟里十到十二人 | [Quantified AI 对比](https://www.quantified.ai/blog/is-tim-cook-a-better-presenter-than-steve-jobs/) |
| B | 刻意停顿：句后的沉默与话本身一样有力，用来造张力、让概念落地 | [the power of the pause](https://bespoke-coaching.com/blog/the_power_of_the_pause_in_presentations/) |
| B | "one more thing" 用的是 Columbo 手法：看似要结束，停顿，再抛一个 | [Wikipedia](https://en.wikipedia.org/wiki/One_More_Thing) |
| C | 一个产品段落跨多少张片 —— 公开分析里没有计数。"约 10–20 张"是目测推断 | — |

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

1. **`.key` 不可能程序化生成**。格式私有无文档，没有库支持写入。AppleScript 只能控制 Keynote（打开、导出、放映），不能建片。唯一通路是生成 `.pptx` 再由 Keynote 导入。来源：[iWork 自动化文档](https://iworkautomation.com/keynote/document-export.html)
2. **CSS 里不要写 `"SF Pro Display"`**。本机文件名是 `SFNS.ttf`，按 "SF Pro Display" 引不可靠。用 `system-ui, -apple-system` 让系统解析，既拿到 SF 又不涉及分发字体文件。
3. **python-pptx 完全不支持动画**：无进入退出效果、无转场、无动作路径。来源：[slideforge 整理](https://slideforge.dev/blog/python-pptx-limitations-we-solved)。所以 pptx 那条路要如实告诉使用者没有转场。
4. **reveal.js 没有单文件导出**，要手工内联；Slidev 产出多文件 dist 且需要 Node。都不满足"不装东西、单文件、离线"。来源：[reveal.js issue 788](https://github.com/hakimel/reveal.js/issues/788)、[Slidev 导出文档](https://sli.dev/guide/exporting.html)
5. **手写 HTML+CSS 最合适**：一屏一片、`scroll-snap`、零依赖、离线一致、浏览器直接打印成 PDF。

## 6. 反"发布会腔"/ Against the register

研究里没有这一条，但它是这套风格最容易翻车的地方，所以写进规则。

这套视觉语言天生鼓励空洞的最高级："革命性"、"魔法般"、"这改变了一切"、"重新定义"。Jobs 用这些词时下面垫着真东西（多点触控、一千首歌、从信封里抽出来的厚度）。**词是垫出来的，不是贴上去的。**

所以：形容词要么有一个能指回材料的数字或事实垫着，要么删掉。这一条与本仓库 `writing-rules` 的立场一致。
