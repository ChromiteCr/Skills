# keynote-deck-builder

把一段描述、一份演讲稿或一份现有 PPT，做成发布会主题演讲那种片子。一片一个概念，字大，留白多。

## 目录

```
keynote-deck-builder/
├── SKILL.md                          技能本体
├── references/
│   └── stage-style-research.md       取证记录，规则的依据，分 A/B/C 三档
├── templates/
│   ├── deck-outline.md               阶段一：叙事拍点与逐片清单
│   └── deck.html                     阶段二：单文件演示，十八类片型各一个实例
├── scripts/
│   ├── read_pptx.py                  从现有 .pptx 提取文字，标出该拆的片与近重复的片
│   ├── outline_to_pptx.py            从片单 JSON 生成可编辑的 .pptx
│   └── export_pdf.sh                 HTML 导 16:9 PDF
└── examples/
    ├── example-outline.md            虚构产品 Cadence 的大纲
    ├── example-deck.html             同一个产品的 13 张片
    └── example-deck.json             同一个产品的 pptx 片单
```

## 怎么用

在 Claude Code 里直接说：

```
做一份苹果发布会风格的 PPT，产品是 <你的项目>
```

或者把材料给它：

```
把这份演讲稿做成发布会风格的片子 @speech.md
把我这个 PPT 改成发布会风格 @deck.pptx
```

它会先给一份 `deck-outline.md`——叙事拍点、逐片清单、每个数字的出处、以及哪些内容被舍弃了。
**这一步会停下来等你确认**，因为哪句话该单独占一张片是整件事里最需要你拍板的判断。

答辩和课程汇报也能用，拍点会跟着改。但目录页、分工页、课程要求的说明页在这套风格里没有位置，
它会把这几页单独列出来问你，不会自己删掉。

确认之后出 `deck.html`。翻页用方向键、空格或滚动。

## 三种产出

| 产出 | 命令 | 什么时候用 |
|---|---|---|
| HTML | 技能直接生成 | 默认。视觉精度最高，离线单文件，浏览器直接放映 |
| PDF | `./scripts/export_pdf.sh deck.html` | 要发给别人，或者现场怕浏览器出岔子 |
| pptx | `python3 scripts/outline_to_pptx.py deck.json` | 要在 Keynote 或 PowerPoint 里继续改 |

pptx 那条路**会丢东西**：python-pptx 完全不支持动画与转场，底色只能是纯色。它换来的是可编辑。

`.key` 做不到。格式私有，没有任何库能写入。要进 Keynote 就先生成 pptx 再导入。

## 先看一眼效果

```bash
open examples/example-deck.html
```

十三张片，虚构产品。第 11 张演示了没有出处的数字在片上该怎么标。

## 几条硬规则

- **一片一个概念**。两个概念就是两片
- **片子不重复讲稿的句子**。片上放碎片、数字或图，句子留给讲的人说
- **字号不低于 40px**（= 30pt）。塞不下就删字，不是缩字号
- **没有项目符号**。顺序性内容拆片，并列性内容改成 bento 格或图形
- **数字要有出处**。指不回材料的标【未确认】，而且要标在片上
- **不用任何厂商的商标、产品渲染图或活动视觉**。产品位是占位图，你自己换

规则的依据在 `references/stage-style-research.md`，每条标了证据强度。查不到公开依据的说法（比如那些
流传的动效时长参数）标成 C 档，没有写进规则。
