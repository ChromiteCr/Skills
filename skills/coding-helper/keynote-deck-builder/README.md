# keynote-deck-builder

把一段描述、一份演讲稿或一份现有 PPT，做成发布会主题演讲那种片子。一片一个概念，字大，留白多，讲到才出现。
同一套视觉也用在课堂、讲座和学术报告上。

## 目录

```
keynote-deck-builder/
├── SKILL.md                          技能本体
├── references/
│   └── stage-style-research.md       取证记录，规则的依据，分 A/B/C 三档
├── templates/
│   ├── deck-outline.md               阶段一：场合、叙事拍点、逐片清单、出场顺序、讲义
│   └── deck.html                     阶段二：单文件演示，三十三类片型各一个实例
├── scripts/
│   ├── read_pptx.py                  从现有 .pptx 提取文字，标出该拆的片与近重复的片
│   ├── outline_to_pptx.py            从片单 JSON 生成可编辑的 .pptx，带动画与讲者备注
│   ├── pptx_motion.py                pptx 的动画与转场写入，也能 --inspect 一份现成的 pptx
│   ├── inline_images.py              图片内联成 data URI，查分辨率与来源行，清掉 GPS
│   └── export_pdf.sh                 HTML 导 16:9 PDF
└── examples/
    ├── example-outline.md            发布会：虚构产品 Cadence 的大纲
    ├── example-deck.html             同一个产品的 13 张片
    ├── example-deck.json             同一个产品的 pptx 片单
    ├── lecture-outline.md            课堂：一堂讲单摆周期的课
    ├── lecture-deck.html             同一堂课的 17 张片
    ├── lecture-deck.json             同一堂课的 pptx 片单
    └── lecture-handout.md            同一堂课的讲义
```

## 怎么用

在 Claude Code 里直接说：

```
做一份苹果发布会风格的 PPT，产品是 <你的项目>
给高一讲单摆，十五分钟，做一套苹果风格的片子
```

或者把材料给它：

```
把这份演讲稿做成发布会风格的片子 @speech.md
把我这个 PPT 改成发布会风格 @deck.pptx
```

它先判断场合（发布会、答辩、课堂、讲堂），再给一份 `deck-outline.md`：叙事拍点、逐片清单、
每张片分几步出、每个数字和每张图的出处、哪些内容被舍弃或移进讲义。
**这一步会停下来等你确认**，因为哪句话该单独占一张片是整件事里最需要你拍板的判断。

确认之后出 `deck.html`。

## 放映

| 按键 | 作用 |
|---|---|
| → / 空格 | 下一步；本片步数走完才进下一片 |
| ← | 上一步 |
| P | 讲者视图：另开一个窗口，显示备注、下一张和计时 |
| B | 黑屏 |
| F | 全屏 |
| Home / End | 第一张 / 最后一张 |

地址后面加 `#5` 从第 5 张开始。

## 四种场合差在哪

视觉、字号、不用项目符号、事实校验这些四种场合都一样。课堂与讲堂换三条文字规则：

- **证据片的标题是一句主张**，不是名词短语。主张句加视觉证据的片子，理解测验明显更好
- **允许提问片**，只要真有人作答、答案一定揭晓。课前小测在真实课堂里有效，但一节课放两三道就够
- **结尾可以有回顾**，但要先给提示让人自己想，再揭晓；参考文献片也可以有。「谢谢观看」照旧不要

课堂还要一份讲义：投影上删掉的推导、条件和出处都放进去。依据见 `references/stage-style-research.md` 第 12 节。

## 四种产出

| 产出 | 命令 | 什么时候用 |
|---|---|---|
| HTML | 技能直接生成 | 默认。逐步出现、跨片连续过渡、讲者视图都在这里 |
| 内联版 HTML | `python3 scripts/inline_images.py deck.html` | 放了真图以后，发给别人之前 |
| PDF | `./scripts/export_pdf.sh deck.html` | 要发给别人，或者现场怕浏览器出岔子。**所有步骤都会印出来，包括提问片的答案** |
| pptx | `python3 scripts/outline_to_pptx.py deck.json` | 要在 Keynote 或 PowerPoint 里继续改 |

pptx **带动画**：讲到才出现、讲过的调暗、讲到的换重点色、相邻两片的同一个东西用 Morph 平移过去，
时长和 HTML 一样。这些是直接写 PresentationML 做的，写法照 PowerPoint 自己存出来的文件抄。
加 `--static` 关掉全部动画（检查题会拆成题目与揭晓两张），要把文件发出去让人自己翻时用。

它仍然**会丢东西**：底色只能纯色，公式与推演的式子退成纯文本要重排，图表不做，
误解片的划线改成调暗。**Keynote 导入后动画剩多少没有验证过。**

看一份 pptx 每张片分几步：`python3 scripts/pptx_motion.py --inspect deck.pptx`。

`.key` 做不到。格式私有，没有任何库能写入。要进 Keynote 就先生成 pptx 再导入。

## 先看一眼效果

```bash
open examples/example-deck.html
open examples/lecture-deck.html
```

第一份是发布会，第 11 张演示了没有出处的数字在片上该怎么标。
第二份是课堂，第 7 张推演逐行出现，第 8 张到第 9 张的符号 T 会移过去。

同一堂课的 pptx：`python3 scripts/outline_to_pptx.py examples/lecture-deck.json`，
17 张片里 8 张分步、共 19 次点击，第 9 张进入时是 Morph。

## 几条硬规则

- **一片一个概念**。两个概念就是两片
- **片子不重复讲稿的句子**。片上放碎片、数字、图或一句主张，解释留给讲的人
- **字号不低于 40px**，深礼堂 48px。塞不下就删字，不是缩字号
- **讲到才出现**。一次出一个意义单位，讲过的调暗，不飞入不弹跳
- **柱状图基线从零起**，柱子本身要看得清
- **没有项目符号**。顺序性内容逐步出现或拆片，并列性内容改成格子或图形
- **数字和图都要有出处**。指不回材料的标【未确认】，而且要标在片上
- **不用任何厂商的商标、产品渲染图或活动视觉**。图片位是占位，你自己换

规则的依据在 `references/stage-style-research.md`，每条标了证据强度。查不到公开依据的说法（比如那些
流传的动效时长参数）标成 C 档，没有写进规则。
