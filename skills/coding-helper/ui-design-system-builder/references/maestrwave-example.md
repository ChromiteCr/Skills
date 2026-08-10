# 实例：MaestrWave 的视觉语言

这套方法总结自 `MTX/MaestrWave` 的前端。**需要一个完整参照时才读这份**，
写新项目的 token 不需要它。

项目是"AI 生成管弦乐 + 体感指挥"的 Web 应用，React + Vite，CSS Modules，无 UI 框架。

---

## 1. 意象 → 配色

意象是**月光下的水面**。从项目名（Maestr*Wave*）和领域（波形、指挥）里抠出来的。

```css
:root {
  --bg: #15130f;          /* 暖炭黑 */
  --surface: #211c15;
  --surface-2: #2c2519;
  --surface-3: #382f1f;
  --accent: #7cb2e8;      /* 浅水蓝，呼应波形 */
  --accent-dim: #4d6f96;
  --wine: #b8453a;        /* 录制 / 重绘 / 危险，与蓝一冷一暖 */
  --ink: #f3eddd;         /* 暖白 */
  --line: rgba(243, 237, 221, 0.1);
  --line-strong: rgba(243, 237, 221, 0.18);

  /* 装饰波浪用的四支蓝，深浅冷暖略有差异，叠加时才有层次 */
  --wave-1: #8fc1f0;
  --wave-2: #5f9bd6;
  --wave-3: #3a6ea8;
  --wave-4: #bcdcf7;

  color-scheme: dark;
}
```

源码里的原话，说明了它在躲什么：

> 暖炭黑的深色基底 + 浅一点的水蓝主色，像月光下的水面：accent（浅蓝）呼应波形/波浪的主题，
> wine（酒红）保留作为"录制/重绘"等状态色，和蓝形成一冷一暖的对比，
> 不是通用的"暖白+赤陶"或"纯黑+荧光绿"默认组合。

四支底色是**明度台阶**（`bg → surface → surface-2 → surface-3`），
深色界面里层级靠明度而不是阴影，全项目几乎不用 `box-shadow`。

文字层级不另起 token，一律 `color-mix`：

```css
color: color-mix(in srgb, var(--ink) 55%, transparent);   /* 次要文字 */
color: color-mix(in srgb, var(--ink) 48%, transparent);   /* 表单小标签 */
color: color-mix(in srgb, var(--ink) 38%, transparent);   /* placeholder */
```

## 2. 排版尺度

全站三个字体 token 都指向衬线体，CJK 排在拉丁之后：

```css
--font-display: "Source Serif 4", "Noto Serif SC", Georgia, serif;
--font-body:    "Source Serif 4", "Noto Serif SC", Georgia, serif;
--font-mono:    "Source Serif 4", "Noto Serif SC", Georgia, serif;
```

尺度对比是这套系统的核心 —— 巨大标题 vs 克制的小号标签：

| 类 | 字号 | 字重 | 字距 | 用在哪 |
|---|---|---|---|---|
| `.display-1` | `clamp(40px, 6vw, 64px)` | 600 | `-0.02em` | 每页主标题 |
| `.display-2` | `clamp(24px, 3vw, 32px)` | 600 | `-0.01em` | 区块标题 |
| `body` | 14px / 1.5 | 400 | — | 正文 |
| `.eyebrow` | 11px | 500 | `0.14em` uppercase | 标题上方的小标，用 `--accent` |
| `.label` | 12px | 400 | `0.01em` | 说明文字，55% 透明 |
| `.field-label` | 11px | 500 | `0.09em` uppercase | 表单字段标签，48% 透明 |
| `.mono-chip` | 12px | 500 | `0.04em` | 元信息胶囊，`tabular-nums` |

这套对比固化在 `PageHeader` 组件里（eyebrow + `display-1` + 右侧小号 meta），
所有页面共用，没有哪一页自己写标题样式。

## 3. 样式分层

```
styles/global.css              字体引入、:root token、跨页排版类、表单基础样式、
                               prefers-reduced-motion、滚动条
components/X/X.module.css      组件自己的布局
pages/YPage/YPage.module.css   页面自己的布局
```

`.display-1` `.eyebrow` `.label` `.mono-chip` `.field-label` 都是在第二个页面用到之后
从 module 提到 global 的 —— 源码注释写着"各页面统一用这一个类，不再各自重复定义"。

## 4. 层级换手法，不是调强度

侧栏两级导航（`Sidebar.module.css`）：

```css
/* 一级展开态：浅色描边 + 微亮底 */
.sectionOpen {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 28%, transparent);
}

/* 二级选中态：实心高亮，色彩反转 */
.itemActive {
  color: var(--bg);
  background: var(--accent);
}
```

源码里的理由：

> 一级和二级同时用实心块的话，视线分不出层级，反而更乱。

同一手法在 OutputPage 上再用一次：主模式切换用实色底的分段控件，
次一级的"配对方式"用更小、无实底的按钮组，"避免和上面的主切换抢视觉重心"。

## 5. token 要能穿透到 canvas

`lib/canvasFont.ts` —— canvas 的 `ctx.font` 不认 CSS 变量，所以从 computed style 取回来：

```ts
const v = getComputedStyle(document.documentElement).getPropertyValue("--font-mono").trim();
```

> 不这么做的话，每个画布都得自己写死一串字体名 —— M6 换衬线体时就发现刻度文字全被漏掉了。

## 6. 可用性底线

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
}

textarea:focus, input:focus, select:focus, button:focus-visible {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent);
}
```

- 装饰波浪层：`aria-hidden="true"` + `pointer-events: none` + 底部渐隐融入 `--bg`
- 按钮：`min-height: 42px`，`:active` 时 `scale(0.98)`，`:disabled` 时 `opacity: 0.4`
- 时长/计数一律 `font-variant-numeric: tabular-nums`
- 唯一的装饰性动画是生成中的 `wavingPulse` 呼吸，注释写明用途：
  "暗示还在跑，没卡住" —— 它表达状态，不是装饰

## 7. 自绘，不引库

- 图标：`components/icons.tsx`，统一 `20x20`、`stroke-width: 1.6`、`currentColor`，
  手绘线性图形，不装图标库。每个图标都和领域有关（指挥棒、拍型轨迹、评分板）
- Logo：斜切的 M/W 折线，既是首字母也是波形；与 `public/icon.svg` 同一份图形，
  底色写死不走 token —— "它是品牌标识，需要在侧栏、浏览器标签、桌面图标等不同背景下保持一致"
- 前端依赖只有 react / zustand / qrcode / mediapipe / @fontsource

## 8. 注释写取舍

字体那一段是最完整的例子（`global.css`）：

```css
/*
  CJK 只引 400/600 两档。@fontsource 的中文包按 unicode-range 切成一百多个分片，
  每多一档字重，产物 CSS 就多几十 KB（gzip 后）—— 而 CSS 是阻塞渲染的。
  界面里只用到 400/500/600 三档，500 的场合（.mono-chip / .field-label / .eyebrow）
  中文极少，交给浏览器回退到 400 看不出差别。700 全项目没用到。
*/
```

```css
/*
  --font-mono 现在也是衬线体（按「UI 全部改 Serif」的要求）。代价是数字不再等宽，
  情绪柱状图刻度、时间码、.mono-chip 这些地方的数字会参差 —— DOM 里靠
  font-variant-numeric: tabular-nums 补救，canvas 里补救不了。
  觉得不合适时把这一行改回 "IBM Plex Mono", ui-monospace, monospace 即可，
  其余代码全都引用 token，不用动。
*/
```

侧栏加宽那一段说明改动的理由来自使用，而不是审美：

```css
/*
  M6：从 64px 纯图标栏改成 196px 带文字的两级导航。
  加宽的理由是一级项「指挥教学 / 指挥体验」光靠图标分不清，
  而这两项是整个应用的分岔口，认错了就走错路。
*/
```

## 9. 响应式按内容断点

没有通用栅格。断点是针对具体组件定的：`@media (max-width: 480px)` 让操作按钮占满一行、
`@media (max-width: 600px)` 把四列的重绘表单塌成两列。
写在那个组件自己的 module 里，不在全局。
