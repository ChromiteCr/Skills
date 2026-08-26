# photo-spread-composer

把一组照片排成报纸摄影版那样的展示版面：分带、定主次、两端顶到版心。

**这个 skill 不给版式，给语法。** 谁占最大格、分几带、哪张打头，由这一组照片决定，
每次都不一样。写成固定模板等于替使用者做了判断，而且必然做错。

## 目录

```
photo-spread-composer/
├── SKILL.md                     技能本体：协议 / 语法 / 留给判断的
├── references/
│   └── layout-grammar.md        语法来由与带高方程的推导
├── templates/
│   ├── spread-plan.md           阶段一：分带方案
│   └── spread.html              阶段二：语法的 CSS 实现，无任何写死的位置
├── scripts/
│   ├── measure_photos.py        量长宽比、像素、EXIF 署名，标出不可用的
│   └── build_spread.py          解带高方程 + 查分辨率 + 缩放内联 + 出 HTML
└── examples/
    ├── example-plan.md          阶段一产物
    ├── example-plan.json        阶段二输入
    ├── example-spread.html      成品（合成占位图）
    └── photos/                  占位图，非真实作品
```

## 怎么用

```
把这些照片排成一版 @photos/
做一张照片展示海报，A2 竖版
```

先量一遍：

```bash
python3 scripts/measure_photos.py photos/ --dpi 300 --min-mm 60
```

它会给出长宽比、取向分布、分辨率预警和署名缺失清单。**不会把照片读进对话**。

然后 skill 出一份 `spread-plan.md`——分带、主次、图注、署名、没上版的及原因，
**停下来等你确认**。确认后翻成 `plan.json` 跑：

```bash
python3 scripts/build_spread.py plan.json spread.html
```

## 位置是解出来的

一带之内所有 item 等高、两端顶齐，带高由一个方程唯一确定：

```
h · [ Σ aᵢ + Σ 1/Sⱼ ] = W − (n−1)·g − Σ wₖ + Σ (mⱼ−1)·g / Sⱼ
```

所以 `plan.json` 里**没有、也不应该有任何一个位置或尺寸**。你只说哪几张在一带、什么顺序，
剩下的脚本解。想改版式就改分带和顺序重跑，不要回模板里加 margin 或固定宽度。

推导在 [references/layout-grammar.md](references/layout-grammar.md)。

## 三种 item

| type | 是什么 | 用在哪 |
|---|---|---|
| `photo` | 一张 | 默认 |
| `stack` | 竖向叠放的一组，共用宽度 | 竖构图的去处；一张竖图想占满带高时 |
| `text` | 固定宽度的文字栏 | 作品自述、创作说明 |

## 几条硬规矩

- **一带一主角**。三张一样大摆一排，这带就没有主语
- **层级只靠面积**。不加边框、阴影、圆角、白边
- **天沟全页统一**，横竖相同
- **图注归带不归张**，贴带下方左对齐
- **署名必留**，查不到作者的照片不上版
- **分辨率不足直接报错**，不静默放大——放大后屏幕上看不出来，打印出来是糊的
- **不复制任何真实出版物的报头、刊名或识别系统**。做语法，不做身份

## 先看一眼

```bash
open examples/example-spread.html
```

四条带演示四种带型。里面是合成占位图，署名是虚构的。
