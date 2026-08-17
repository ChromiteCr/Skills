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
| B | 中文标题行高比拉丁紧：CJK 字身框没有升降部余量。正文级 1.0–1.3，100px 以上取 1.0–1.15 | [中文排版要点](https://pixelcake.com.tw/posts/chinese-typography-tips/) |
| B | 大字中文字距容忍度远小于拉丁，0 或轻微负值常见，正值不要超过 0.15em | 同上 |
| B | 显示级中文标题的可读字数约 8 到 15 字。中文单字信息密度高于拉丁单词，同样一张片装的**字数更少而信息更多** | [标题字数建议](https://zhuanlan.zhihu.com/p/582583945) |

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
| B | bento 网格的构图规矩：一张片 8–12 格，超过 12 格构图垮掉；锚点格面积约为支撑格的两倍；格子里放数字而不是标题 | [bento 版式拆解](https://www.deck.gallery/blog/apple-bento-grid-breakdown/) |
| B | **bento 已经用滥**：2024 年后"每个 SaaS 落地页都默认用它"，设计圈批评其同质化。较好的做法是混合媒介、有意打破对齐 | [bento 实践指南](https://www.saasframe.io/blog/designing-bento-grids-that-actually-work-a-2026-practical-guide/) |
| B | "one more thing" 自 2014 年 Apple Watch 之后基本停用；独角戏式的空台揭示被多人分段与预录片段取代 | [one more thing 清单](https://www.macworld.com/article/674643/every-one-more-thing-apple-has-ever-announced.html) |
| B | Liquid Glass 上线后被批评可读性下降：文字与壁纸混在一起、半透明图标与背景糊成一片，被拿来类比 Windows Vista Aero | [对 Liquid Glass 的批评](https://medium.com/macoclock/apple-has-dressed-its-operating-systems-in-liquid-glass-551d1ef991b4) |

## 11. 反"发布会腔"/ Against the register

研究里没有这一条，但它是这套风格最容易翻车的地方，所以写进规则。

这套视觉语言天生鼓励空洞的最高级："革命性"、"魔法般"、"这改变了一切"、"重新定义"。Jobs 用这些词时下面垫着真东西（多点触控、一千首歌、从信封里抽出来的厚度）。**词是垫出来的，不是贴上去的。**

所以：形容词要么有一个能指回材料的数字或事实垫着，要么删掉。这一条与本仓库 `writing-rules` 的立场一致。
