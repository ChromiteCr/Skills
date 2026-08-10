# maestrwave-ui-system

## Case 1: 新项目直接套用

**输入 / Input**

一个空的 React + Vite 项目，只有默认的 `App.tsx` 和 Vite 模板样式。界面以中文为主。

用户提问：新项目的前端照着 MaestrWave 那套来。

**期望 / Expected**

- [ ] 给出 `npm i @fontsource/source-serif-4 @fontsource/noto-serif-sc`
- [ ] 把 `assets/global.css` 落到 `src/styles/global.css` 并在入口 import
- [ ] **保留 CJK 的两行 `@import`**，并说明只引拉丁字体会让中文掉到系统黑体
- [ ] 铺组件层，页面用 `PageHeader` + `.page-body` + `.card` 的骨架
- [ ] 先在**一个**页面上跑起来，而不是一次改完全站
- [ ] 结尾报「已铺 / 换了的 token / 还缺的组件」三件事，不贴整份 CSS

**反例 / Must not**

- 不得顺手装 Tailwind / MUI / shadcn
- 不得复用 MaestrWave 的 logo 字标或那套领域图标
- 不得新增字号档位（比如在 display-2 和 body 之间加一档 18px）
- 不得把颜色写成 `#7cb2e8` 这样的字面量而不走 token

## Case 2: 换主色 —— 项目和音频无关

**输入 / Input**

一个记账应用，要套这套系统，但用户说「蓝色不合适，想要偏绿的」。

**期望 / Expected**

- [ ] 只改 `--accent` / `--accent-dim` / `--wave-*`，不动 `--bg` / `--surface*` / `--ink`
- [ ] 提醒 `--accent` 会当作 `.btn-primary` 的底色、上面压 `--bg` 做文字，
      所以必须够亮，否则主按钮文字看不清
- [ ] 指出 `--wine` 是状态色，不要拿它当第二主色
- [ ] 装饰波浪层与记账无关，建议换成别的低透明度叠层或整层删掉，
      并说明删掉之后界面依然成立

**反例 / Must not**

- 不得把 `--bg` 一起改成纯黑或冷灰
- 不得为了配绿色而新增一批颜色 token
- 不得保留一层和项目毫无关系的水波装饰还说「这是这套系统的一部分」

## Case 3: 越界 —— 要浅色版 / 顺手改逻辑

**输入 / Input**

已有项目，用户提问：把样式统一成 MaestrWave 那套，另外做个浅色模式。

代码里同时存在一处 `useEffect` 依赖写错、一处 `outline: none` 把焦点态干掉了。

**期望 / Expected**

- [ ] 如实说明这套只有暗色，明度台阶在浅色下不成立，浅色是另起一套的工作量
- [ ] 不直接反色交差
- [ ] 修掉 `outline: none`，恢复统一焦点态（这属于样式范围内）
- [ ] **指出** `useEffect` 依赖的问题，交给用户决定，不顺手改

**反例 / Must not**

- 不得用 `filter: invert()` 或简单反色冒充浅色模式
- 不得顺手修业务逻辑
- 不得为了统一而保留 `outline: none`
