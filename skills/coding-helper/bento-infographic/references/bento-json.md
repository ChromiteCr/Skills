# bento.json、layout.json、qa.json 的字段 / Field reference

`bento.json` 是使用者确认过的内容清单。字段、默认值和校验以 `scripts/bento_spec.py` 为准。`bento.py plan`、`layout`、`render` 都先跑 `validate_spec`：有问题逐条列出，退出码 2。下表"报错"是提示的摘要。没列出的键（如 `note`）被忽略。图片路径相对 `bento.json` 所在的目录。

## 顶层字段

| 字段 | 取值（默认） | 说明与报错 |
|---|---|---|
| `schema` | `"bento/1"` | `schema 必须是 "bento/1"` |
| `canvas.use` | `screen` `print` `phone` `custom` | 定 u：`phone` 取宽的 2.8%，其余取短边的 2.2%。`canvas.use 必须是 … 之一` |
| `canvas.width`、`height` | 正整数，输出像素 | `canvas.width 必须是正整数（输出像素）` |
| `canvas.dpr` | 正整数（2） | CSS 像素 = 输出像素 ÷ dpr。`canvas.dpr 必须是正整数` |
| `canvas.u_ratio` | 小数，可不写 | 换掉 2.2% 或 2.8%；不校验 |
| `theme` | `light`（默认）`light-inverse` `dark` | 底、格、字色见 `apple-measurements.md`。`theme 必须是 … 之一` |
| `mode` | `product`（默认）`research` | 只有 research 能用 `chart`、`uncertainty` 等。`mode 必须是 product 或 research` |
| `lang` | `zh-CN`（默认）`en` | 定行高（中 1.3，英 1.18）和标签长度规则 |
| `font` | `system`（默认）`open` | `open` 是 Inter 加 Noto Sans SC；PDF 一律按 `open` 出 |
| `accent` | `null`（默认）或 `"#rrggbb"` | 产品自己的颜色，最多一支。`accent 必须是 null 或 "#rrggbb"` |
| `source_line` | `null`（默认）或字符串 | 使用者要求才填，画在下边距那一条，0.75u |
| `seed` | 整数（0） | `layout` 的随机种子，同种子同方案；不校验 |
| `tiles` | 列表 | `tiles 必须是非空列表` |
| `dropped` | `[{"text", "reason"}]` | 舍弃的条目和理由，`plan` 会打印；不校验 |

## 格子字段

| 字段 | 取值（默认） | 用在 | 报错与备注 |
|---|---|---|---|
| `id` | 小写字母、数字、短横线 | 全部 | `id 要用小写字母、数字和短横线`；`id 重复` |
| `kind` | `hero` `stat` `word` `icon` `object` `photo` `ui` `row` `flank` `chart` | 全部 | `未知的 kind`；`必须恰好有一个 kind 为 hero 的格` |
| `weight` | 1（默认）2 3 | 外圈各格 | `weight 只能是 1、2、3`。3 给最大的格，1 避开最大的格；定 `word` 的字号档；无图的 `stat` 取 3 时数字从 4.3u 排起 |
| `label` | 字符串，`\n` 换行 | 全部，`hero` 不画 | 长度规则与报错见 `label-grammar.md` |
| `label_pos` | `top` `bottom` | `word` `object` `flank` `row` `photo` `ui` 生效；`stat` `icon` `chart` 忽略 | `label_pos 只能是 top 或 bottom`。默认值见 `tile-kinds.md`；`photo` 不写则按对比度选 |
| `value`、`unit` | 字符串 | `stat` | `stat 格需要 value` |
| `word` | 字符串，可含 `\n` | `word` `hero` | `word 格需要 word`；`主图要有 image 或 word` |
| `image` | 路径 | `object` `photo` `ui` `flank` 必填；`hero` `stat` `word` `icon` 可选 | `X 格需要 image`；`图片不存在 路径` |
| `fit` | `contain` `cover` | `hero` `stat` `word` `object` `ui`；`photo` 恒为 cover，`flank` `icon` `row` 恒为 contain | `fit 只能是 contain 或 cover`。`ui` 不写则自动选 |
| `focus` | CSS `object-position`，如 `"50% 100%"` | 带图的格，`icon` `row` 除外 | 不校验。裁切时留哪一块 |
| `icon`、`icon_size` | `assets/icons/index.json` 里的名字（63 个）；3–9，单位 u（不写就取格宽的 46%，夹在 3.5–9u） | `icon` | `icon 格需要 icon 名字或一张小图 image`；`没有叫 x 的图标`；`icon_size 在 3–9u 之间` |
| `items` | 字符串或图片路径的列表 | `row` | `row 格需要 items` |
| `left`、`right` | 字符串，如 `"6.9″"` | `flank` | 不校验，至少写一个 |
| `series`、`chart`、`highlight`、`highlight_label` | 数列；`line`（默认）`bar`；下标，从 0 数；字符串（默认画那个数） | `chart` | `chart 只在 research 模式里用`；`chart 需要至少两个数据点的 series（数字）`；`chart 只能是 line 或 bar`；`highlight 是 series 里的下标（从 0 数）` |
| `uncertainty`、`n`、`condition`、`exact` | 数值字符串，如 `"0.3"`；正整数；字符串；布尔 | research 的 `stat` | 规则见下 |
| `accent` | 布尔（false） | `stat` `word` `hero` `icon` `chart` | `只有 stat、word、hero、icon、chart 能用重点色`；`用了重点色，但顶层 accent 没给颜色`。`chart` 只染高亮处，`icon` 染图标 |
| `tone` | `ink`（默认）`silver` | `hero` `stat` `word` `flank` 的字 | `tone 只能是 ink 或 silver`；`silver 只用在深色主题`；`silver 和重点色不能同时用` |
| `background` | `"#rrggbb"`，或 `["#顶", "#底"]` | 全部 | `background 是 "#rrggbb"，或上下两个颜色 [...]；只用内容自带的颜色`。白字够读（主图大字 ≥ 3:1，有标签的格 ≥ 4.5:1）字就变白，否则取黑白里对比度高的 |
| `image_side` | `left`（默认）`right` | 带图的 `word` | 不校验，不是 `left` 一律按 `right` |
| `on_image` | `"light"` | `fit: cover` 的 `word` | 不校验，`light` 让字变白 |
| `box_aspect` | 小数，宽 ÷ 高 | `hero` | 不校验。主图框的长宽比，不写则按图的长宽比 × 1.25。只有字的主图写了它，就按产品主图排（16:9 上写 1.8 约占宽高各一半），自检的面积范围也按产品主图 |
| `facts` | `[{"text": "原文", "source": "出处"}]` | 带数字的格必填 | 规则见下 |
| `unverified` | 布尔 | 带数字却找不到出处的格 | 规则见下 |

**带数字的格**：`kind` 是 `stat`、`flank`、`chart`，或 `value`、`label`、`word`、`left`、`right`、`condition` 里有阿拉伯数字（`unit`、`items` 不算）。这样的格要有 `facts`，每条的 `text` 和 `source` 都不为空，否则报 `有数字就要在 facts 里写出处，找不到出处就写 "unverified": true`。写了 `unverified` 的格，画出的标签或 `word` 里要有"未确认"（英文 unverified），否则报 `没有出处的数字要在图上看得出来`。

**研究模式的数字**（`mode: "research"` 的 `stat`）：

- `uncertainty`、`n`、`condition`、`exact` 只能写在这种格上，别处写了报 `… 只用在 research 模式的 stat 格`（`exact: false` 不算写）。
- `n` 是正整数（`n 是样本数，正整数`）；`uncertainty` 要含数字（`uncertainty 写数值，如 "0.04"`）；它和 `exact` 二选一。
- 没有不确定度时：计数、定义值、确定性计算的结果写 `"exact": true`；只测了一次写 `"n": 1`，照实画出来。都没写，报 `研究模式的数字要写 uncertainty（…）`。
- 画成 `42.3 ± 0.3 s`（`± 0.3 s` 缩到 0.5 倍字号）。写了 `n` 或 `condition`，标签下多一行，如 `n = 5`、`n = 12，室温`；这时 `label` 只能一行，多出的那行中文折算不超过 11 字、英文不超过 7 词。写法见 `label-grammar.md`。

## layout.json

`schema` 为 `"bento-layout/1"`。格位是 `[列, 行, 宽, 高]`，从 0 数，单位是网格小格；每个 `id`（含主图）一条。渲染只读 `grid` 和 `cells`；`seed`、`score`（越小越好）、`pattern`（四个角归带 `band` 还是归栏 `column`）由 `layout` 写。

```json
{"schema": "bento-layout/1", "grid": {"cols": 56, "rows": 32}, "seed": 455, "score": 14.137,
 "pattern": {"tl": "band", "tr": "column", "bl": "band", "br": "band"},
 "cells": {"hero": [17, 11, 22, 10], "skills": [7, 0, 12, 11]}}
```

## qa.json

`schema` 为 `"bento-qa/1"`，`pass` 是全部检查都过。`where` 是字符串列表，检查能指出哪一格时才有。`warnings` 放只提醒的事：用了兜底字体、格数在建议范围外、图片放大。`dom.json`、`fonts.json` 是渲染时量出的中间数据，供自检用。

```json
{"schema": "bento-qa/1", "pass": false,
 "checks": [{"id": "contrast", "pass": false, "value": 1, "limit": "labels >= 4.5, large >= 3",
             "where": ["grade label 3.10 < 4.5"]}],
 "fonts": {"system": 122, "fallback": 0, "other": 0}, "warnings": []}
```

19 项检查的 `id`：

| id | 查什么 |
|---|---|
| `hero_center` | 主图中心离画布中心 ≤ 0.5%（有出处行时以格子区的中心为准） |
| `hero_area` | 主图面积占比：有图、带底色或写了 `box_aspect` 的 18–30%，只有字 10–20%，通栏 15–45% |
| `gutter_uniform` | 格缝和四边外边距都是 0.68u（有出处行时下边距 2.11u），偏差 ≤ 0.5 个 CSS 像素（dpr 2 时是 1 个输出像素） |
| `radius_uniform` | 每格圆角都是 1.55u，偏差同上 |
| `unit_size` | 标签字号都是 u（±1%）；出处行 0.75u |
| `type_scale` | 大数字 2.2–4.3u，功能名 1.6–3.4u，主图字 5–8u，`flank` 两侧的值 1.6–2.0u，`row` 里的字 1.35–1.45u |
| `weight` | 每段字的字重都是 600 |
| `overflow` | 文字行比盒子宽，或墨迹出了格子：0 处 |
| `label_lines` | 画出的行数 ≤ 2（中）或 3（英），且等于 `label` 里写的行数 |
| `label_length` | 同 `validate_spec` 的标签长度规则 |
| `fonts` | 每段字都落在字体栈里的字体上；栈外字体不过，用了兜底（Inter、Noto Sans SC）只提醒 |
| `contrast` | 标签 ≥ 4.5:1；1.6u 以上的大字 ≥ 3:1；照片上的字取字背后最不利的 10% 像素 |
| `accent_hues` | 饱和度超过 0.2 的文字色相最多一种，且不在标签上 |
| `text_only_share` | 外圈里没有图的 `stat`、`word` 格 ≤ 30% |
| `tile_count` | 格数（含主图）在 `count_limits` 内；不在 `count_range` 内只提醒 |
| `min_tile` | 每格 ≥ 6u × 4.8u |
| `image_upscale` | 图片按 dpr 放大超过 1.25 倍只提醒，这一项永远算过 |
| `output_size` | PNG 像素和 `canvas` 完全一致（没有 PNG 时不出这一项） |
| `cjk_spacing` | `zh-CN`：`label`、`word` 里汉字紧挨拉丁字母或数字，没有空格 |

## 格数

格数含主图。`count_range(use, css_w, css_h)` 是建议范围，超出只提醒；`count_limits` 是上下限，超出 `tile_count` 不过，`plan` 也报问题。基准是苹果 16:9 的 67 张总结片：常见 14–18 格，见过 10–21 格（`apple-measurements.md`）。别的画幅按以短边计的周长折算：系数 s = 2 × (长边 ÷ 短边 + 1) ÷ 5.56；建议 = (14s, 18s) 四舍五入；上下限 = (10s 向下取整，不小于 5；21s 四舍五入)。只看画幅的形状，不看 `use`。手机的字大，但格数不按 u 压低，装不下时 `layout` 报"排不出来"（第 7 轮实测：1:1 手机图配两行标签最多排 12 格）。

| 画幅 | 输出像素 | `use` | u（输出 px） | 网格 | 建议 | 上下限 |
|---|---|---|---|---|---|---|
| 16:9 | 3840×2160 | screen | 47.5 | 56×32 | 14–18 | 10–21 |
| 4:3 | 2048×1536 | screen | 33.8 | 40×32 | 12–15 | 8–18 |
| 21:9 | 3440×1440 | screen | 31.7 | 76×32 | 17–22 | 12–26 |
| A4 竖版 | 2480×3508 | print | 54.6 | 32×44 | 12–16 | 8–18 |
| 1:1 | 2160×2160 | phone | 60.5 | 24×24 | 10–13 | 7–15 |
| 3:4 | 1242×1656 | phone | 34.8 | 24×32 | 12–15 | 8–18 |
| 4:5 | 1080×1350 | phone | 30.2 | 24×32 | 11–15 | 8–17 |
| 9:16 | 1080×1920 | phone | 30.2 | 24×44 | 14–18 | 10–21 |
| 1:2 长图 | 1080×2160 | phone | 30.2 | 24×48 | 15–19 | 10–23 |

## 示例一：产品，16:9 浅色

内容是本库自己的数字和产物（2026-10-10 发版后的现数）。主图是品名压在一张脚本画的图上（本库 README 徽章的蓝 #2f81f7 画的几层弧面，每层带亮边和投在下一层上的软影），`box_aspect` 1.8 让它按产品主图的大小排；同一个蓝做重点色，给全部大数字和图标（同一类元素要么都上，要么都不上）。九格放本库产物的截图或照片，截图都先裁到有信息的那一块；浅色截图在白格里看不出边的，换成深色版；截图的标签都在下，只有从下边出血的整页版面写 `label_pos: "top"`。纯文字格三格，图标格两格；`pptx` 写 `weight` 3，排 2.6u；量词写进标签开头（"63" / "个技能"）；测试用例数的是用例条数（每个 skill 必有一个用例文件，数文件就和技能数重复了）。画布取默认 3840×2160 的一半。和 `examples/product-light/bento.json` 相同，只是图片路径写成 `images/…`（那里是 `../images/…`）。深色版（`examples/product-dark/`）用同一个排版，公式片和组图换成深色版，大字一律纯白。

```json
{
  "schema": "bento/1",
  "canvas": {"use": "screen", "width": 1920, "height": 1080, "dpr": 2},
  "theme": "light",
  "mode": "product",
  "lang": "zh-CN",
  "font": "system",
  "accent": "#2f81f7",
  "source_line": null,
  "seed": 0,
  "tiles": [
    {"id": "hero", "kind": "hero", "word": "Skills", "image": "images/skills-wallpaper.jpg", "fit": "cover", "box_aspect": 1.8, "weight": 3},
    {"id": "skills", "kind": "stat", "value": "63", "label": "个技能", "weight": 2, "accent": true, "facts": [{"text": "63 个 SKILL.md（含已废弃的 launch-summary-panel）", "source": "find skills -name SKILL.md，2026-10-10"}]},
    {"id": "cases", "kind": "stat", "value": "429", "label": "条测试用例", "weight": 1, "facts": [{"text": "tests/cases 下 63 个文件里共 429 条 Case（数 \"## Case\" 标题）", "source": "grep -c '^## Case' tests/cases/*.md，2026-10-10"}], "accent": true},
    {"id": "pptx", "kind": "word", "word": "pptx", "label": "动画导出", "weight": 3},
    {"id": "mathml", "kind": "word", "word": "MathML", "label": "原生公式", "weight": 2, "image": "images/keynote-formula-crop-light.png", "image_side": "right"},
    {"id": "specs", "kind": "ui", "image": "images/keynote-specs-crop-dark.png", "label": "规格一览页", "weight": 2, "fit": "contain"},
    {"id": "deck", "kind": "ui", "image": "images/keynote-number-crop-dark.png", "label": "发布会幻灯片", "weight": 1, "fit": "contain"},
    {"id": "spread", "kind": "ui", "image": "images/spread-top.png", "label": "照片跨页排版", "weight": 2, "label_pos": "top"},
    {"id": "radio", "kind": "ui", "image": "images/radio-card.png", "label": "车队无线电卡片", "weight": 1, "fit": "contain"},
    {"id": "grade", "kind": "ui", "image": "images/coffee-compare.jpg", "label": "调色前后对比", "weight": 2, "fit": "contain"},
    {"id": "night", "kind": "photo", "image": "images/rocket-graded.jpg", "label": "夜景调色", "weight": 1},
    {"id": "series", "kind": "ui", "image": "images/series-grid-light.jpg", "label": "组图排版", "weight": 2, "fit": "contain"},
    {"id": "physics", "kind": "icon", "icon": "atom", "label": "物理\n17 个技能", "weight": 2, "accent": true, "facts": [{"text": "physics 下 17 个 SKILL.md", "source": "find skills/physics -name SKILL.md，2026-10-10"}]},
    {"id": "lyrics", "kind": "icon", "icon": "music-notes", "label": "歌词诊断", "weight": 1, "accent": true}
  ],
  "dropped": [
    {"text": "库版本号 0.24.0", "reason": "每次发版都会变，放进总结图很快过期"},
    {"text": "各分类的技能数（数学建模 9、学习规划 8、AI 使用 7、摄影 6、作词 5、社群活动 1）", "reason": "几格都写\"N 个技能\"读起来像清单；只留最大的物理一类写数字，其余换成具体的功能"},
    {"text": "31 个带自检的脚本", "reason": "和测试用例挨着放显得重复，图上留一个数"},
    {"text": "截止日倒排计划、AI 输出事实核查（两格图标）", "reason": "纯图标格只留两个，苹果样图每张 0–3 个；换成有图的组图排版"},
    {"text": "LaTeX 论文排版", "reason": "本机没有 LaTeX，出不了真实的排版截图；纯文字格已有三个"}
  ]
}
```

## 示例二：研究成果，3:4 浅色

数字来自电影感调色原型 0.4.1 的实测，加上本库 photo-cinematic-grade 0.3.0 在本机实测的渲染耗时（全尺寸连跑 5 次；不同像素数各跑 1 次，画成柱状图）。画幅是 3:4 却用 `screen` 不用 `phone`：研究格的字多，手机 3:4 的左右两栏只有约 8u，排不下。统计量写进标签（"最大""最小"），限值留在 `facts` 里；LUT 回读有一个风格没达标，就写"5/6"。重点色用本库徽章的蓝，给全部数字和柱图的高亮；最要紧的肤色漂移写 `weight` 3，排 4.3u。主图是调过色的宇航员样图，只作示意。和 `examples/research-3x4/bento.json` 相同，只是图片路径写成 `images/…`。

```json
{
  "schema": "bento/1",
  "canvas": {"use": "screen", "width": 1080, "height": 1440, "dpr": 2},
  "theme": "light",
  "mode": "research",
  "lang": "zh-CN",
  "font": "system",
  "accent": "#2f81f7",
  "source_line": null,
  "seed": 0,
  "tiles": [
    {"id": "hero", "kind": "hero", "image": "images/astronaut-graded.jpg", "fit": "cover", "weight": 3, "facts": [{"text": "主图是宇航员样图（肤色护栏的测试对象）经本库 photo-cinematic-grade 0.3.0 调色（warm-muted，强度 70）的结果，只作示意", "source": "examples/README.md"}]},
    {"id": "hue", "kind": "stat", "value": "4.4", "unit": "°", "label": "最大肤色漂移", "exact": true, "weight": 3, "facts": [{"text": "肤色色相平均漂移：色板测试最大 4.4°（霓虹夜），护栏 ≤ 6°；确定性计算，四张样图 × 六个风格", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}], "accent": true},
    {"id": "lut", "kind": "stat", "value": "5/6", "label": "合格的 LUT 回读", "exact": true, "weight": 1, "facts": [{"text": "LUT 回读（33³，四面体插值）p99 上限 0.02：五个风格达标（0.003–0.016），粉彩在宇航员上 0.053 未达标", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}], "accent": true},
    {"id": "render", "kind": "stat", "value": "42.3", "uncertainty": "0.3", "unit": "s", "label": "全尺寸渲染", "n": 5, "weight": 2, "facts": [{"text": "cinegrade.py render，warm-muted 70，6000×4000 JPEG；5 次 41.89、42.40、42.59、42.60、42.01 s，均值 42.30，标准差 0.33；峰值内存 0.89–1.07 GB", "source": "本库 photo-cinematic-grade 0.3.0，Apple M4 Pro，2026-10-08 本机实测"}], "accent": true},
    {"id": "distinct", "kind": "stat", "value": "0.036", "label": "最小原图色差", "exact": true, "image": "images/chelsea.jpg", "fit": "cover", "weight": 2, "facts": [{"text": "鲜明风格与原图的 ΔE_OK 全部 ≥ 0.035，最小 0.036（猫，青橙）", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}], "accent": true},
    {"id": "between", "kind": "stat", "value": "0.027", "label": "最小风格间色差", "exact": true, "image": "images/rocket.jpg", "fit": "cover", "weight": 1, "facts": [{"text": "任意两个风格之间的 ΔE_OK 全部 ≥ 0.025，最小 0.027（火箭，青橙对拷贝片浓郁）", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}], "accent": true},
    {"id": "banding", "kind": "stat", "value": "+0.19", "unit": "码值", "label": "最大断层增量", "exact": true, "image": "images/coffee.jpg", "fit": "cover", "weight": 1, "facts": [{"text": "最平滑区域的量化残差比源图增加 ≤ 0.35 个码值，最大 +0.19（咖啡，粉彩）", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}], "accent": true},
    {"id": "scores", "kind": "chart", "chart": "bar", "series": [5.2, 10.7, 21.6, 42.3], "highlight": 2, "highlight_label": "21.6 s", "label": "渲染耗时", "weight": 2, "facts": [{"text": "cinegrade.py render，warm-muted 70，同一张图缩放到 2000×1500、3000×2000、4000×3000、6000×4000：5.20、10.69、21.63 s（各测 1 次），42.30 s（5 次均值）；耗时和像素数大致成正比", "source": "本库 photo-cinematic-grade 0.3.0，Apple M4 Pro，2026-10-09 本机实测"}], "accent": true},
    {"id": "selftest", "kind": "icon", "icon": "terminal-window", "label": "自检 54/55", "weight": 1, "facts": [{"text": "自检 55 项，54 项通过；没过的是粉彩在宇航员上的 LUT 回读", "source": "AUDIT-AND-IDEAS.md 第三部分 3.9，原型 0.4.1 实测"}]},
    {"id": "repeat", "kind": "icon", "icon": "fingerprint", "label": "确定性输出", "weight": 1, "facts": [{"text": "同一种子，输出字节相同：通过", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}]},
    {"id": "skin", "kind": "icon", "icon": "shield-check", "label": "人像肤色护栏", "weight": 1, "facts": [{"text": "宇航员人像上，肤色色相漂移与色度比全部在护栏内", "source": "AUDIT-AND-IDEAS.md 第三部分 3.5，原型 0.4.1 实测"}]},
    {"id": "looks", "kind": "icon", "icon": "palette", "label": "六个调色风格", "weight": 1, "facts": [{"text": "青橙、霓虹夜、金色时刻、拷贝片浓郁、粉彩童话、素净", "source": "AUDIT-AND-IDEAS.md 第三部分 3.6"}]}
  ],
  "dropped": [
    {"text": "原型的全尺寸渲染 18 秒、峰值内存 2.7 GB", "reason": "只测了一次，原型也不在了，不能重测；改用本库 0.3.0 本机连跑 5 次的耗时"},
    {"text": "六个风格的自评分（8、7、7、7、6.5、6）", "reason": "作者自评，不是测量；六根柱子差不多高，放上去没有信息量"},
    {"text": "高光剪切增量、死黑增量", "reason": "都是 0 或接近 0，放上去没有信息量"}
  ]
}
```
