# 组件配方 / Recipes

要落地某个具体组件时读这一份。类名对应 `assets/components.css`。
代码是 React + TypeScript；换框架时结构照搬，只有语法要改。

---

## 应用外壳

侧栏固定宽、主区独立滚动，装饰层垫在内容底下：

```tsx
export function App() {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar />
      <main style={{ flex: 1, overflowY: "auto", position: "relative" }}>
        <WaveBackdrop />
        <div style={{ position: "relative", zIndex: 1 }}>
          <Page />
        </div>
      </main>
    </div>
  );
}
```

`overflow: hidden` 在外层、`overflowY: auto` 在 `main` 上 —— 这样侧栏不跟着滚，
页头滚出去时侧栏还在。

## Button

三个变体够用：`primary`（一屏最多一个）、`ghost`（默认）、`danger`。

```tsx
import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger";
}

export function Button({ variant = "ghost", className, ...rest }: ButtonProps) {
  return <button type="button" className={`btn btn-${variant} ${className ?? ""}`} {...rest} />;
}
```

默认值是 `ghost` 而不是 `primary`：主按钮稀缺才有意义，默认给 ghost 能避免一屏三个实心蓝块。
`type="button"` 写死，避免在表单里误触发提交。

## PageHeader

尺度对比的载体。每个页面都用它，不要各自写标题样式。

```tsx
interface PageHeaderProps {
  eyebrow: string;
  title: string;
  meta?: ReactNode;      // 一般是几个 .mono-chip
  actions?: ReactNode;   // 一般是 1-2 个 Button
}

export function PageHeader({ eyebrow, title, meta, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__left">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="display-1">{title}</h1>
      </div>
      <div className="page-header__meta">
        {meta}
        {actions}
      </div>
    </header>
  );
}
```

`eyebrow` 写栏目名（"指挥教学"），`title` 写这一页是什么。两者不要重复。

## 装饰性背景层

页面上半部分的氛围层。几支同色系叠加、透明度都很低、底部渐隐融入 `--bg`。
纯装饰，所以 `aria-hidden` + `pointer-events: none`（在 `.backdrop` 上）。

```tsx
export function WaveBackdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <svg viewBox="0 0 1440 420" preserveAspectRatio="none"
           style={{ width: "100%", height: "100%", display: "block" }}>
        <defs>
          <linearGradient id="wave-g1" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--wave-4)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="var(--wave-4)" stopOpacity="0.02" />
          </linearGradient>
          {/* g2 / g3 / g4 同理，依次换成 --wave-1/2/3，透明度 0.16 → 0.12 递减 */}
          <linearGradient id="wave-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff" stopOpacity="1" />
            <stop offset="62%" stopColor="#fff" stopOpacity="1" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id="wave-mask">
            <rect width="1440" height="420" fill="url(#wave-fade)" />
          </mask>
          <filter id="wave-soften" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="10" />
          </filter>
        </defs>
        <g mask="url(#wave-mask)" filter="url(#wave-soften)">
          <path d="M0,90 C180,40 360,140 540,90 C720,40 900,140 1080,90 C1260,40 1350,110 1440,80 L1440,0 L0,0 Z"
                fill="url(#wave-g1)" />
          {/* 其余三条把基线依次下移到 150 / 210 / 280，相位错开 */}
        </g>
      </svg>
    </div>
  );
}
```

```css
.backdrop {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 420px;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
```

**换主题时这一层要跟着换**：波浪是这套系统里唯一带项目色彩的图形。
新项目如果和"水/波"无关，把它换成别的低透明度几何叠层，或者整层删掉 ——
删掉之后界面依然成立，它只是氛围。

## 两级侧栏

```tsx
<nav className="rail">
  <div className="brand">…</div>

  <button className={`rail__section ${open ? "rail__section--open" : ""}`}>
    <TeachIcon /> <span>指挥教学</span>
  </button>
  {open && (
    <div className="group">
      <button className={`rail__item ${active ? "rail__item--active" : ""}`}>课程</button>
      <button className="rail__item">考试</button>
    </div>
  )}

  <div className="rail__divider" />
</nav>
```

一级项如果只靠图标分不清（尤其是应用的主要分岔口），就把栏加宽到 196px 带上文字。
64px 纯图标栏只适合分类彼此差异很大的场合。

## 状态显示

```tsx
<div className="status-bar">
  <span className={`status-dot status-dot--${ok ? "ok" : "off"}`} />
  <span className="status-label">Backend</span>
  <span>{name}</span>
  {!ok && <span style={{ color: "var(--wine)", fontSize: 12 }}>{warn}</span>}
</div>
```

进行中：

```tsx
<span style={{ display: "inline-flex", alignItems: "baseline", gap: 10 }}>
  <span className="pulsing">Working…</span>
  <span className="timer">{elapsed}</span>
</span>
```

计时器一定要 `tabular-nums`（`.timer` 里已带）—— 衬线体的比例数字会让秒数每跳一次就抖一下。

## canvas / SVG 里用 token

`ctx.font` 不认 CSS 变量，从 computed style 取回来，别在每个画布里写死字体名：

```ts
let cached = "";

function family(): string {
  if (!cached) {
    const v = getComputedStyle(document.documentElement).getPropertyValue("--font-mono").trim();
    cached = v || "Georgia, serif";
  }
  return cached;
}

/** 例：canvasFont(11) → `11px "Source Serif 4", …` */
export function canvasFont(px: number, weight?: number | string): string {
  return `${weight ? `${weight} ` : ""}${px}px ${family()}`;
}
```

颜色同理：画布里要用主色时读 `--accent`，不要抄一遍 `#7cb2e8`。
漏掉这一步的代价是换主题时所有图表文字和刻度纹丝不动。

## 图标

不装图标库。统一 `20x20`、`stroke-width: 1.6`、`stroke="currentColor"`、`fill="none"`、
圆角端点，用 `currentColor` 跟随所在按钮的文字色：

```tsx
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function PlayIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" {...base}>
      <path d="M6 4.5 15 10l-9 5.5Z" />
    </svg>
  );
}
```

图标画项目自己的东西（领域里的具体物件），不要用通用的齿轮/文件夹凑数。

## 换主色

只动这三处，其余不要碰：

```css
--accent: <新主色>;
--accent-dim: <新主色压暗 30% 左右>;
--wave-1..4: <新主色的四支深浅变体，或整段删掉>;
```

三条约束：

1. `--accent` 会被当作 `.btn-primary` 的**底色**，上面压 `--bg` 做文字 ——
   所以它必须够亮，暗色主色会让主按钮的文字看不清。
2. 保持冷暖对比：底色是暖炭黑，主色偏冷时最好看。想用暖色主色（橙/黄），
   底色要跟着往中性灰调，否则整片发糊。
3. `--wine` 是状态色，不要拿它当主色用 —— 全站的"危险/异常"语义挂在它身上。

底色（`--bg` / `--surface*`）和 `--ink` 是一套暖调，成组替换或者干脆不动。
只把 `--bg` 改成纯黑会让所有颜色发脏。
