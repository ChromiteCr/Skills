# UX 契约 / UX Contracts

> 每个交互部件分两半：**契约 CONTRACT**——必须成立、可测，抽到任何方向都不变（多半是可访问性、正确性、隐私）；**呈现 PRESENTATION**——方向可以换的外观与手感，每项给原站取值和替代。
> 判别法：换了会让人用不了 / 看错 / 被误导 = 契约；换了只改气质 = 呈现。
> 编号如 `SE-3`，供测试、`DESIGN.md`、lint 引用；括号里是测法。**原站取值 / source value** 是一个实例，不是默认。
> 地图画法见 `map-craft.md`（§ 号），措辞与搜索细节见 `wayfinding-copy.md`。起步页（`install.py --starter`）已经满足其中哪些、代码在哪，见 §17。

| 部件 | 前缀 | 部件 | 前缀 |
|---|---|---|---|
| 实体搜索 | SE | 底部弹层 | SH |
| 实体网格 | GR | 地图与弹层共用屏幕 | MS |
| 实体页 | EP | URL 状态与记忆 | UR |
| 阅读导航 | RN | 空态 / 错误 / 无 JS | ZS |
| 地图 | MP | 读屏播报 | LV |
| 房间聚焦 | RF | 分步路线 | DR |
| 主题路线 | TR | 偏好与平台适配 | PF |
| 语言主次 | LD | | |

章节：§1 SE · §2 GR · §3 EP · §4 RN · §5 MP · §6 RF · §7 DR · §8 TR · §9 SH · §10 MS · §11 UR · §12 ZS · §13 LV · §14 最小测试矩阵 · §15 PF · §16 LD · §17 起步页（已满足 / 归你）。

---

## 1 实体搜索 / Entity search（SE）

**契约**

- SE-0 **用引擎自带的搜索**：`EVK.search.create(entities, {groups, rooms, fields}) → {query(q, {limit}), best(q)}`（`assets/engine/search.js`，无 DOM，Node 里也能跑）。分数 4 整名 / 3 名称前缀 / 2 其他键前缀 / 1 子串 / 0.5 多词各自命中；同分按传入的场地原序；空查询 = 全部原序，`best("")` 为 null。`rooms` 传 `venue.floors`，房号和开放区名就成了键。不要每个项目再抄一份。（测：`node assets/engine/search.js --selftest`）
- SE-1 **一个规范化函数**：全角转半角、NFKC、小写、去变音、去掉所有空白、标点与符号（`EVK.search.normalize`）。构建期（Python）、列表过滤、地图搜索、404 / 路由器共用同一实现；非 JS 端必须逐例一致并有测试。（测：`kestrel robotics` = `Kestrel-Robotics` = `kestrelrobotics`；`3-02` = `3·02` = `302`）
- SE-2 两组键：**名称键**（英文名、中文名、缩写、短名、去掉开头 The 的英文名、多词英文名的首字母）；**描述键** = 名称键 + 组词 + 标签 + 房间或开放区的 id / label / 中英文名 + 楼层 id + "房号+展位"（`20301`）。纯数字永远指房间 / 展位，不得做实体别名（构建期报错）。
- SE-3 平铺选择列表按匹配质量 4 档排序：整名相等 > 名称前缀 > 描述前缀 > 描述子串；同档保持场地原序（稳定）；空查询 = 全部原序；不匹配 = 隐藏。（测：名称恰为查询者排第一，名称前缀其次，描述子串最后；`20` 列出 201–204）
- SE-4 分组网格上的过滤：就地隐藏，不重排；组内无可见项则整组隐藏；无结果 → `role="status"` 空态，含可试的例子。
- SE-5 **歧义词只搜不跳**：同时指多个实体的城市 / 通名从别名表删除，只留作组词。（测：歧义词 `riverside` 列出所有相关实体，不跳转）
- SE-6 Enter 取第一个可见结果；`type="search"`、`enterkeyhint="search"`、`autocomplete="off"`；几百项以内不防抖，不发网络请求。
- SE-7 预填值必须能让自己排第一（深链预填目的地用**完整名称** → 整名相等档）。
- SE-8 有标签（可见或视觉隐藏）；字号 ≥ 16 px（iOS 聚焦不缩放）；高 ≥ 44。
- SE-9 占位符教能力：名称 / 缩写 / 类别 / 位置码各一例，取自真实数据（`wayfinding-copy.md` §6.4）。

**呈现**

| 项 | 原站取值 | 可换 |
|---|---|---|
| 外观 | 浅底色条 + 2 px 墨色下线，聚焦变强调色；圆角 0，去掉 WebKit 清除钮 | 1 px 框盒；药丸 + 图标；全屏搜索；命令面板 |
| 反馈 | 无高亮 | 命中字母高亮 / 加粗 |
| 类别发现 | 手写 21 组词 | 分面 chips；自动标签；自然语言 |
| 匹配 | 前缀 / 子串（引擎已含 NFKC、去变音、全角折叠） | 拼音首字母；编辑距离；繁简互通（`fields` 里加另一种写法）；服务端 |
| 提交 | Enter 取首项 | 方向键高亮后 Enter；唯一结果自动前往；"Go" 钮 |

---

## 2 实体网格 / Entity grid（GR）

**契约**

- GR-1 每个实体都能从一个列表到达；一格一链接，整格可点（高 ≥ 44，原站 56）。
- GR-2 一格含：标记（徽 / 色块 / 首字母）+ 主语言名 + 副语言名（可省略号）+ 位置码（房间·展位）。位置码是格内唯一的强调色。
- GR-3 标记缺失 → 同尺寸占位，格子不位移（图片带 `width` / `height`）。
- GR-4 位置未定 → 写"待定 / TBD"，不留空；数量为 0 → 不印（`:empty{display:none}`）。
- GR-5 分组标题含计数（"United States 美国 · 43 所"）；搜索时空组整组隐藏（SE-4）。
- GR-6 **列数按宽度分档**（手机 2，≥ 700 3，≥ 1000 4），不靠无限 `auto-fill`；文字与分隔线永远留间距——第一列左内边距 0（标记贴齐页边距），后续列加左内边距，每个断点重设。
- GR-7 按下态触摸即现（`:active` 无过渡），松开缓出；悬停样式只在 `(hover:hover)`；iOS 要一个空 `touchstart` 监听才触发 `:active`。
- GR-8 `min-width:0` + 省略号，名称撑不破格子。

**呈现**：格形（发丝线分格，无卡片 | 卡片 | 索引表 | 大图磁贴 | 地图优先）· 标记（30 px 圆章 | 方章 | 色块首字母）· 位置码（红色衬线数字 + 灰 `·01` | 票根 | 号牌）· 分组（国家 + 计数 | 字母索引 | chips | 标签页）· 密度（2/3/4 列 | 单列大图）。

---

## 3 实体页 / Entity page（EP）

**契约**

- EP-1 首屏（375×667）看得到：实体名 + 标记、位置码（房间 + 展位）、主操作（路线 / 地图）。放不下时位置码优先于装饰。
- EP-2 名称按长度分档定字号（原站 ≤ 4 / ≤ 7 / ≤ 12 / 更长，4 档，构建期算 `data-fit`），`overflow-wrap:anywhere` 兜底：3 字母与 13 字母的名字都铺满宽度，不横向滚动。**配方只设 `--name-min` / `--name-vw` / `--name-max`（最长一档的 `clamp`），不在 `.evk-entity-name` 上写 `font-size`**：`base.css` 的 `data-fit` 各档按比例缩放它们，配方自己设了字号，分档就失效。抬头里名字之外的行用明确的类：`.evk-entity-sub`（另一种语言的名字）、`.evk-entity-line`（一句话）、`.evk-entity-code`（位置码），不要用宽泛的 `.evk-entity-head > p`。
- EP-3 **实体色驱动**：一个 hex → `--e*` 七个角色（算法见 `scripts/tones.py`）；页面文字用 `--e-text`（对纸 ≥ 4.5 : 1）、深色用 `--e-dk`。不手调。（测：lint 对每个实体色的浅色与深色都检查）
- EP-4 数据条：DOM 顺序先词后值，视觉上数值在上（`flex-direction: column-reverse`）；数字 lining + tabular；`overflow-wrap:anywhere`。标记是 `.evk-num` = `<span>` 说明（先）+ `<b>` 数值（`<small>` 单位在 `<b>` 里）。`base.css` 不带 `column-reverse`：起步页的 `starter.css` 写了（`.evk-strip > .evk-num`），不用起步页就在项目样式或配方里自己写这一行，否则数值会掉到说明下面。
- EP-5 位置未公布 → 统一空态块，不留洞。
- EP-6 操作钮（路线 / 在地图上看）就绪前 `hidden`；无 JS 时位置码和文字仍完整。
- EP-7 小图 = "近景"（房间 + 四周 3.5 m），`role="img"`，label 说出"在哪"（见 `wayfinding-copy.md` §9）。
- EP-8 图片：`width` / `height` 属性；首图 eager，其余 lazy + async；占位色 = `--e-soft`；署名行排版（左：内容，右：作者 · 许可）。
- EP-9 锚点目标 `scroll-margin-top` ≥ 顶栏高 + 空气（原站 70–80 px）；`:target` 高亮。
- EP-10 上一个 / 下一个：文字 + 名称，2 px 顶线。
- EP-11 **地址永久**：slug 一经印刷（二维码）冻结；改名走别名 / 重定向。
- EP-12 **阅读块**：实体页的内容是 `reading.md` §3 那 12 种封闭块（`p note quote list facts cards steps table timeline numbers qa fold`）的有序列表：页面级 `entity.blocks`，或章内 `parts[].blocks`。每块 `{type, …}`，输出带 `evk-r-<type>` 的标记（`base.css` §9b 只画结构，配方只加性格）；坏块让构建失败，并指出实体与位置（"entity kelp: blocks[2] (timeline) item 1 has no 'at'"）；`fold` 最多嵌两层。（测：十二种各放一块、320 px 无横向滚动；`table` 是可聚焦的 `role="region"`，行列数与表头一致）

**呈现**：页头（`directions.json` 的 `entity_header`：table-tent、placard、ticket-stub、index-card、envelope、stamp-tile、masthead、title-block、luggage-tag、specimen-sheet；原站 = 巨名 + 6 px 规则线 + 小章）· 关键数据块（全宽强调色带 + 号牌 | 票根 | 针卡 | 固定底栏）· 数据条（发丝格 | 药丸 | 大数字 + 条 | 一行字）· 配色（实体色 | 全局强调 | 分节色）· 地图与文字（0.7fr / 1.3fr | 全宽地图 + 浮钮）。

---

## 4 阅读导航 / Reading navigator（RN）

**契约**

- RN-1 由 `[data-part]` 构建：一部分一个标记，标记数 = 部分数。（测：N 个 part → N 个标记）
- RN-2 未读 / 已读 / 当前**至少两个通道**编码（长度或位置 + 墨色或色相），不得只靠颜色。
- RN-3 "当前部分" = 最后一个顶边 ≤ **阅读线**的部分；阅读线 = 顶栏底 + 视口高 × 0.28（范围 0.2–0.4）。
- RN-4 进度在读完正文时到 100%：`span = 报告高 − 视口高 × 0.6`，`p = clamp((栏底 − 报告顶)/span, 0, 1)`，用 `transform: scaleX` 不用 `width`。
- RN-5 面板：按钮 `aria-expanded` + `aria-controls`；打开 → 焦点到当前行（`preventScroll`），↑↓ Home End 在行间移动；Esc 关闭并还焦点；外部点击、点链接都关闭；含"回到顶部"。
- RN-6 hash 深链（点击 / `hashchange` / 加载）：沿目标祖先打开所有 `<details>` 再滚动。
- RN-7 滚动与 resize 监听被动、每帧合并；仅当索引变化才写 DOM 与 `aria-label`；初始 current 用哨兵值，首帧必更新。
- RN-8 渐进增强：按钮与进度线在 markup 里 `hidden`；页内目录链接列表是无 JS 回退。
- RN-9 按钮点击区 ≥ 44×44（原站 42，是软肋）。
- RN-10 `aria-label` 随部分更新："报告目录，正在读第 3 部分，共 8 部分"。
- RN-11 桌面 ≥ 980 px：部分头 + 子导航成粘性左栏（`top` = 栏高 + 空气）；手机：子导航为可横滑 chips，首项对齐页边距。

**呈现**（`nav` 轴）

| 值 | 说明 |
|---|---|
| `lines-top-left`（原站） | 栏内左上一列短线，每部分一条；未读 12×2 px 淡、已读 12 px 墨色、当前 26 px 长 + 实体色；`transition: width .25s` |
| `side-ticks` | 屏幕边缘竖向刻度 |
| `tab-strip` | 顶部可横滑的标签条 |
| `progress-ring` | 环绕按钮的进度环 + 数字 |
| `chapter-rail` | 桌面侧栏章节轨 |

面板：4 px 实体色顶线 + 阴影，宽 `min(360px, 100vw − 24px)`，行 3 px 左线。进度线 2 px 贴栏下，**替换**而非叠加栏下发丝线。

---

## 5 地图 / Map（MP）

**契约**

- MP-1 画布 `role="img"` + `tabindex="0"` + 一句 label：是什么 + 怎么操作（拖动 / 双指 / 方向键）+ 文本名录在哪。
- MP-2 同一份数据的**文本名录**（按楼层 / 房间分组，编号列表）一直在页面里，无 JS 也在。画布不是唯一入口。
- MP-3 手势：单指 / 鼠标横拖 1:1 转动（orbit、exploded；**oblique 的拖动 = 平移、偏航锁定，plan 只在纸面内转**，所以 brief 说"能转"就冻结 `projection=rotate`，不是 `3d`，`map-craft.md` §15）；触屏竖滑滚页面（`touch-action: pan-y`）；双指缩放 + 扭转 + 倾斜；ctrl+滚轮缩放；键盘 ←→↑↓ `+` `-`，另有 `[` `]` 在实体间切换、`Esc` 取消选择、`0` / `Home` 复位（`EVK.VenueMap`）。
- MP-4 点按 = 位移 ≤ 7 px 且 < 600 ms；命中顺序 标记 > 房间 > 楼层；命中半径 = 可视 + 6 px；alpha ≤ 0.5 的层不接受命中。（测：拖动结束不触发选择）
- MP-5 弹簧可打断，松手带速度，限位用橡皮筋（`map-craft.md` §3）。
- MP-6 **静止 0 次 rAF**；离屏 0 次 rAF；resize 不播动画；方案 / 主题变化重读颜色。（测：停下后 Performance 面板无帧）
- MP-7 提示条一次性：首次按下或 6 s 后消失；Reset 仅离家时出现，用 `hidden`。
- MP-8 楼层控件二选一：`aria-pressed` 按钮组（原站），或 `role="tablist"` + `aria-selected` 且实现方向键（`EVK.seg`）。路线模式下无一选中；按一个楼层 = 结束路线。**配方的选中态两个属性都要覆盖**（`[aria-selected="true"], [aria-pressed="true"]`），只写一个，另一种写法就落回 base 的实心块；选中态里的双语配对继承该面的字色（LD-2）。**放不下就在控件里横滑**：`.evk-seg` 自带 `overflow-x:auto`，配方不得改成 `overflow:hidden`（会把放不下的钮裁掉，第 5、6 层再也点不到），按钮不缩到 44 px 以下，带上路线钮在 320 px 也不撑宽页面（F19）；切角之类的形状放在按钮上（`clip-path`），不放在控件上。
- MP-9 选定目标：其余标记降到梯度、目标放大 + 脉冲三次（相机落定后才开始）。
- MP-10 容器先有 `--m-ground` 背景；标记图未到不跳；字体到达后重绘。
- MP-11 减弱动效：无开场、无脉冲、虚线静止、无惯性，终态相同。
- MP-12 打印隐藏画布；构建期数据校验失败 = 构建失败（`EVK.wayfind.create(venue).warnings` 必须为空）。
- MP-13 **开放区与挑空**：`areas[]`（走廊、中庭地面）像房间一样可点选、可聚焦、有名字、能放展位，但没有墙、没有门；`void` 块是通往下层的开口，不可走，里面不得放东西，叠层时是一口看得到下层的井，其他视图是 X 框（`map-craft.md` §9.1）。绕着中庭的环形回廊是一个带洞的区（`areas[].holes`）：洞里的点不属于这个区（展位归属、路线文案、点按），地图描出两圈轮廓（`map-craft.md` §1.3）。（测：点开放区与点房间终态相同；展位放进挑空 → 构建期警告；点回廊的洞不选中回廊）
- MP-14 **标签随 lead**：地图标签、提示框、aria 的主语言来自 `VenueMap` 的 `lead`（缺省读 `<html data-evk-lead>`，变化时自动重读），主行在上、更大。（测：翻一次 lead，主次对调）
- MP-15 **俯仰有底**：橡皮筋可越过限位，但俯仰不得 ≤ 0，每个 `arc` / `ellipse` 半径不得为负。（测：四个方向猛拖到头，控制台无 IndexSizeError，仍能拖回）
- MP-16 **墨线与墙面读得出**：`--m-cap`（墙帽、环、针、图标描线）对 `--m-slab` ≥ 7 : 1，`--m-wall` ≥ 3 : 1，浅深各一份（`map-craft.md` §5.7，floor F03）。生成器走到这两个值，`lint_floor.py` 查（cap < 4.5 失败，< 7 警告，wall < 3 警告）；手改令牌后重跑。（测：浅深各截一张总览，墙与墨线在楼板上清晰）
- MP-17 **长条楼在竖屏上不缩成一条**：脚印长宽比 > 1.6 : 1（沿 x 的长边）、画布竖屏、投影会在平面里转（orbit、exploded、plan；oblique 的偏航是倾斜，不夹）时，`VenueMap` 把**静止偏航**夹到"一层脚印仍占可用宽 80%"的最大值（可用宽 = 画布宽减楼层数字槽；偏航 0 也够不到就取最好的一档），在 resize、转屏、令牌变化时重算；拖动、双指和键盘不夹，横屏不动。`draw.py` 照常在包络里抽 `yaw`，夹是引擎在运行时做的，不改牌。规则与数值见 `map-craft.md` §2.8。（测：长条楼的牌在 343–375 px 宽下，每层脚印宽明显大于未夹时；实测 50 × 20 m、4 层、exploded，122–150 → 205–248 px，偏航夹到 5°；转横屏恢复原偏航）

**呈现**：投影 / 材质 / 标记 / 光 / 暗化 = 令牌（`map-craft.md` §14–15；`--keep projection=rotate` = orbit | exploded，`3d` 还含 oblique）· 楼层控件（2 px 框分段，选中反色 | 药丸 | 下划线标签 | 竖向选层柱）· 提示条（磨砂药丸 + "Drag to rotate 拖动旋转" | 动画手指 | 首次自动转一下 | 无）· Reset（文字钮 | 罗盘）· 画布高 `clamp(440px, 74vh, 780px)`。

---

## 6 房间聚焦 / Room focus（RF）

**契约**

- RF-1 入口等价：点房间（含开放区）、点标记、`?r=`、名录里的房间卡 → 同一终态：房间被选中、相机聚焦、弹层列出该房间的实体。
- RF-2 相机：其余层淡出；取景 share ≈ 0.62、俯仰更陡；用户转过的偏航保留；落点避开弹层（MS）。
- RF-3 房间用**地面淡染**（`--m-select-fill`）加一圈内缩的**边线**（`--m-select`，对楼板 ≥ 3:1）高亮：淡染单独不够，状态要有第二通道（floor F07）。
- RF-4 弹层已开时点另一个房间：**就地换内容**，不重播入场，不抢焦点。
- RF-5 关闭：相机回到之前模式（与弹层离开同时开始，不等动画结束）；目标取消高亮。`map.focusRoom(null)` 就做这件事：回到聚焦前的视图（总览或那一层），页面不必自己 `setFloor`。（测：3F 聚焦 → 关闭 → 仍在 3F）
- RF-6 从标记进入 → 该实体成为目标，弹层中其行用强调色。
- RF-7 无实体的房间不进名录，但可在地图上看。

**呈现**：高亮（地面淡染 | 抬高 0.3 m | 光晕）· 相机角度 · 弹层内容（门牌式：房号牌 + 英 / 中位置行 + 编号列表 | 缩略图卡 | 单操作 callout）。

---

## 7 分步路线 / Directions（DR）

**契约**

- DR-1 入口：至少一个全局入口 + 每个"需要时刻"各一（实体页、房间弹层）；引擎就绪前按钮 `hidden`。
- DR-2 表单两问，**先问起点**（默认 = 入口大堂或上次记住的；列表大堂在前再各房间），再问去哪（SE 搜索）。
- DR-3 打开面板：焦点至多进到面板标题（`tabindex="-1"`、`preventScroll`；原站总是移入，`EVK.Sheet` 只在键盘打开时移入），**不**聚焦输入框（手机键盘会盖住列表）。
- DR-4 对每个（起点 × 实体）都出得了路线，构建期穷举测试；运行时仍为空 → 显示可见提示（不得像原站那样静默）。
- DR-5 运行态**开在第 1 步**；总览是一键可逆开关（`aria-pressed`）；再点当前步骤行也切换总览。
- DR-6 步骤列表：每步一个按钮；恰有一个 `aria-current="step"`；编号用 CSS counter（文字干净；隐藏非当前步用 `visibility:hidden; height:0`，不用 `display:none`，它会重置计数器，每步都显示"1"）；步骤有 `walk` / `stairs` / `arrive` 类型；爬楼梯用第二种颜色**并配文字或形状**。
- DR-7 每步 = 一条短标题（祈使句，无数字）+ 一句完整指示（转向、地标、距离）。分工与模板见 `wayfinding-copy.md` §2–§4。
- DR-8 距离先"到门口"再"进入后"；"约 N 米"，N ≥ 1；室内余段 < 3 m 不报；转向只在可定义处说（出房间、出楼梯），"直走"阈值 ≈ 35°；大堂起点不报转向；目标在开放区或无区地面时，文案里没有"门"（"沿西走廊走到 07 号展位"，转向写"出房间后"，`wayfinding-copy.md` §2）。
- DR-9 Back / Overview / Next 位置固定，Next 为主；单实体 = "上一步 / 下一步"，主题路线 = "上一所 / 下一所"（标签写明单位）；端点 `disabled`。
- DR-10 地图 `lock`（点按、悬停暂停）；楼层控件无一按下。
- DR-11 "重新选择"回到表单并保留起点 / 目的地 / 模式，地图回总览，焦点到标题。
- DR-12 **焦点只在旧目标将消失时才移动**（如表单被步骤替换）；关闭面板且焦点在内 → 还给发起钮。（注意原站点击步骤行会重建列表丢焦点——重绘时恢复焦点）
- DR-13 按**高度**减量：矮屏（`(max-height: 900px)` 且窄）只显示当前步，总览态显示全部（`:has()` 兜底）；运行态弹层 ≤ 54dvh，812 px 高的手机仍留 ≥ 40 % 给地图；窄屏非当前步隐藏副语言行（原站隐藏英文行）、主语言两行截断。
- DR-14 播报：每次变化一句，位置在前（LV-1）。
- DR-15 URL 镜像与起点记忆见 UR。
- DR-16 **只发布走过的指引**：房间提示字段默认空；距离带"约"。
- DR-17 惰性：首次规划才建网格，Dijkstra 提前退出，无需加载态。

**呈现**

| 项 | 原站取值 | 可换 |
|---|---|---|
| 面板 | 底部弹层：kicker → 目的地 → 步骤 → 三钮 → 两个文字链 | 顶部横幅（车载式）；横滑步骤卡；单大指令卡 + 进度条 |
| 步骤标记 | 20 px 方形数字、当前行左 3 px 实体色条 + 淡底 + 填充、爬楼梯用第二色 | 时间线节点；转向图标；只加粗当前行 |
| 按钮 | Back / Overview 纸色，Next 墨色；反选填充表示按下 | 主钮 + 文字链；仅图标 |
| 起点输入 | 原生 `select` | 定位；点地图；扫码；推断自上一页 |
| 初始取景 | 第 1 步 | 先总览 1.5 s 再进第 1 步；地图预览 + "开始" |
| 路线调色 | 红走、琥珀爬、白色流动虚线 | 单色 + 线型；图标线；渐变 |
| 密度 | 62vh 上限，非当前步折叠 | 横滑；收起的"窥视"档 |

---

## 8 主题路线 / Themed tours（TR）

**契约**

- TR-1 主题路线 = 有序实体列表（原站 5–8 站）+ 名称 + 一句说明；**每一站必须有展位**（构建期测试）。
- TR-2 第 1 段从所选起点出发，之后每段从上一站的展位出发（"从凯斯特机器人（204 · 01）出发"）。
- TR-3 Back / Next 按**站**跳；标签写"上一所 / 下一所"；步骤内靠点行；端点 `disabled`。
- TR-4 URL：`tour=<id>&stop=<n>`，`n` 从 1 起（给人读），内部 0 起。
- TR-5 地图：站点右上角按序号显示站序圆；站点 alpha 0.72（步骤态 0.4），其余 0.26 / 0.1（`map-craft.md` §8）。
- TR-6 列表行：名称（按**内容的作者语言**为主）+ 说明（2 行截断）+ 站数 lockup（大数字 + 小单位，不空格）。
- TR-7 kicker 写进度："<名称> · 2 / 6"。
- TR-8 （建议，原站无）无 JS 时把各主题的站序印成文字列表。

**呈现**：名称语言顺序（原站 CN 在前，因为名称用中文写成 | 英文在前）· 分组（5 组各带 `.k` 标题 | 平铺）· 行样式（文字行 | 封面拼贴卡 | 做成实体列表的筛选标签）· 生成方式（手选 | 按标签自动 | 最短总步行自动排序）。

---

## 9 底部弹层 / Bottom sheet（SH）

引擎：`EVK.Sheet` / `EVK.Spring` / `EVK.rubber`。

**契约**

- SH-1 **非模态伴随**：无遮罩、无焦点陷阱、不设 `aria-modal`；`role="dialog"` + `aria-labelledby`；背后地图可用，页面可滚。
- SH-2 弹簧：关得比开快（原站开 response 0.35 / 关 0.30，ζ = 1）；回弹用 ζ 0.8，是唯一欠阻尼。数值可调，**关 < 开** 的关系不变。
- SH-3 **速度接续**：动画从当前位置与速度出发；按下手柄 = 停下弹簧、原点取当前位置；松手把手指速度交给下一段。（测：飞行中抓住不跳）
- SH-4 向下 1:1 跟手；向上橡皮筋 `over·dim·0.55 / (dim + 0.55·over)`，`dim` = 弹层高。
- SH-5 **松手按落点判定**：最近一小段样本算速度（原站 ≤ 5 个，`EVK.Sheet` 取最近 100 ms，且松手本身算一个样本，所以停顿后再抬手会回弹），落点 = 位置 + `v/1000 × 0.998/(1−0.998)`（= 0.499 s 的滑行）；落点 > 高度 × 0.5 → 关闭（带速度），否则回弹。
- SH-6 手柄区有界：只有手柄区 `touch-action:none`；内部 `button / select / a` 不起拖；列表正常滚；`pointercancel` = `pointerup`；`setPointerCapture` 放 try/catch；忽略第二指。
- SH-7 入出同轴：入场从 `高度 + 24 px`（含阴影余量）出发，**先 set 再 to**（同一任务，不画中间帧）；出场同路径；**关闭的副作用**（地图缩出、取消高亮）在手势开始时就触发；已开时换内容不重播入场。
- SH-8 静止时行内 `transform` 为空。
- SH-9 Esc 关最上层（路线面板先于房间弹层）；关闭后若焦点在内 → 还给发起控件。
- SH-10 一次一个：开路线关房间弹层，反之亦然；每个弹层的 `onClose` 清理自己的状态。
- SH-11 `viewport-fit=cover`；底部内边距加 `env(safe-area-inset-bottom)`。
- SH-12 大屏（原站 ≥ 880 px）变角落卡片（宽 400，右 24 下 24，隐藏手柄），同一份标记。
- SH-13 减弱动效：`open()` 只解除 `hidden`，`close()` 立即完成，终态相同。
- SH-14 操作控件 ≥ 44（原站 Close 38，是软肋）。

**呈现**

| 项 | 原站取值 | 可换 |
|---|---|---|
| 形态 | 左右下各 8 px 内缩的浮卡 + 6 px 强调色顶帽 + 方角 | 贴边 + 圆角顶 + 遮罩；三档吸附；气泡；侧栏 |
| 手柄 | 40×4 方块，`--sub` 50% | 药丸；无 |
| 阴影 | 品牌色 24%，不用纯黑 | 黑；无 |
| 入场 | 同轴滑入 | 淡入 + 上升 8 px；从被点对象缩放 |
| 手感 | `--spring-dur` / `--spring-bounce`：沉稳 0.5–0.65 / 0；轻快 0.35–0.45 / 0.2–0.3 | |
| 尺寸 | 最高 70vh；表单 `min(72vh, 640px)`；运行 `min(62vh, 560px)` | |

---

## 10 地图与弹层共用屏幕 / Map + sheet screen sharing（MS）

引擎：`map.setPad({top,right,bottom,left})`、`EVK.fitAbove(map, sheetEl)`。

**契约**

- MS-1 弹层不遮住刚选的东西：算**未遮挡矩形**（视口 − 顶栏 − 弹层，与地图相交的部分），把主体居中其中。
- MS-2 用**落定后**的几何（`offsetHeight` / 终点矩形），不用动画中的 `getBoundingClientRect`；与弹层同刻触发相机，一步到位，不二次居中。（测：弹层落定后相机不再动）
- MS-3 遮挡形状决定补偿：**条带 → 平移**（不改比例）；**侧栏 → 重新取景**（改比例）。
- MS-4 可见带 < 80 px 就什么都不做（别把模型推出画面）。
- MS-5 重算触发：开房间弹层、开路线面板、开始路线（rAF 内）、面板内切模式或内容变高（`EVK.fitAbove.watch` 观察弹层自身尺寸）、弹层关闭完成（清零）、resize、**页面滚动**（弹层 fixed 而地图随页滚；被动监听，rAF 合并）。
- MS-6 开始路线：把地图滚到顶栏下方（栏高 + 空气），死区 40 px；`load` 前用 `auto`，不用 smooth（避免与浏览器滚动恢复打架）。
- MS-7 旋转 / resize：仅在宽窄类别翻转（`W > 1.15H`）时重排路线，250 ms 去抖；其余只重新取景。
- MS-8 同时只有一个遮挡源参与 fit，路线面板优先于房间弹层。

**呈现**：补偿（平移 + 重取景 | 缩容器高度 | 大屏并排栅格，永不覆盖 | 弹层内容改放地图下方）· 时序（同时 | 弹层先 | 相机先 | 共享一个进度值）· 把地图做成 sticky / app-shell 可以消掉整套数学。

---

## 11 URL 状态与记忆 / URL state and memory（UR）

参考语法与优先级见 `wayfinding-copy.md` §8。

**契约**

- UR-1 每个值得分享的状态有 URL；参数小而正交，优先级写进 `DESIGN.md`。
- UR-2 所有以 URL 值为键的查找用**自有属性**检查（`hasOwnProperty` / `Map`）。（测：`?to=constructor`、`?r=__proto__` 不解析）
- UR-3 路线运行时用 `history.replaceState` 同步地址（回退键仍离开地图）；保留 hash；结束时只清自己写的参数。
- UR-4 记忆只存稳定的事实（起点）；读取时校验仍存在于当前数据；`localStorage` 全部 try/catch，失败无感。
- UR-5 slug 永久；大小写不敏感；拼错由路由器容错，**保留 query 与 hash**。
- UR-6 站内链接根绝对（404 页在任何地址提供）；`file://` 示例用相对路径。
- UR-7 URL 与存储里不放个人数据。

**呈现**：参数名与形态（query | 路径 `/map/route/kestrel` | hash | 短码）· 是否每步 `pushState` · 是否提供"分享"钮 · 记忆的范围（起点 | 加上最近目的地 | 无）。

---

## 12 空态 / 错误 / 无 JS / Empty, error, no-JS（ZS）

**契约**

- ZS-1 **一个"缺席"组件**用于所有非数据状态，总带原因或下一步（例：搜索无结果 → "可以试试缩写或房号，例如 KES、204"）。
- ZS-2 缺失资源退化为文字 / 色块：无号牌图 → 文字号牌；无楼层字形 → 文本；无标记图 → 同尺寸色盘；格子不位移。
- ZS-3 需 JS 的控件在 markup 里 `hidden` / `disabled`，就绪后显示；全局 `[hidden]{display:none !important}`。
- ZS-4 无 JS 基线：服务端渲染的名录（按层、按房间、编号列表，第一等的版面）+ 一句 `<noscript>` 指向它。数据走 `<script type="application/json">`，`</` 转义。
- ZS-5 错误文案：发生了什么 + 下一步；无错误码、不责怪（模板见 `wayfinding-copy.md` §7）。
- ZS-6 存储 / 网络 / 定位失败 → 功能降级，不抛；遥测 fire-and-forget，永不影响 UI。
- ZS-7 示例数据站：醒目横幅 + `noindex`；示意图标"示意"。
- ZS-8 加载占位用语义色（`--paper-2`、`--e-soft`），不用灰骨架。

**呈现**：空态形式（淡底块 + 4 px 左线 | 插图 + CTA | 骨架 | 行内提示）· 横幅（整幅色条 | 角标 | 水印）· 无 JS 名录样式（门牌卡网格，描边 2 px | 单张表 | 平面图 + 图例 | 手风琴）。

---

## 13 读屏播报 / Live regions（LV）

**契约**

- LV-1 路线：**一个**视觉隐藏的 `aria-live="polite"`，每次变化重写**一句**，位置在前（"第 3 步，共 4 步：…"）；总览："…，全程约 N 米，共 M 步。"。大容器本身不 live。
- LV-2 空态用 `role="status"`。
- LV-3 页面 `lang` 与播报语言一致；夹带的另一语言片段标 `lang`。
- LV-4 导航按钮 / 阅读导航用动态 `aria-label` 带位置，不用 live。
- LV-5 （建议，原站该路径休眠）键盘或名录触发地图选择时：弹层标题获焦（`preventScroll`）或播报一句"已选中 203 展区，4 个展位"。
- LV-6 （建议）搜索结果数：输入停顿约 300 ms 后播报"N 个结果 / 没有找到"。
- LV-7 不用 live 播报动画进度、相机变化、倒计时。
- LV-8 用最窄的语义：`aria-pressed`（切换）、`aria-current`（当前页 / 步）、`aria-expanded` + `aria-controls`（展开）；没实现方向键就不用 `tablist`。

**呈现**：句式与详细度见 `wayfinding-copy.md` §9——可只播一种语言，也可两种。

---

## 14 最小测试矩阵 / Minimal test matrix

| 测 | 覆盖 |
|---|---|
| 规范化等价、排名 4 档、歧义词不跳、数字别名拒绝（`node assets/engine/search.js --selftest`） | SE-0…5 |
| 每个起点 × 每个实体都出路线，跨层必有楼梯，最长路线 < 上界，措辞固定句（如 `走楼梯下到 1 层。`）；`node assets/engine/wayfind.js --selftest 你的venue.json` 一次跑完，开放区目标的句子里没有"门"；有路走不通时不崩，打印"no route for N of M"、每个起点与每个实体的失败数、前 10 对和"门画在共用墙上"的提示，退出码 1；`create().errors` 与 `.warnings` 都为空（房间 / 区 id 写错是 error，门开进另一间房是 warning：`door 101@[x,y] opens into 104`） | DR-4、DR-8、MP-12 |
| lead 翻一次（en ↔ zh）：配对顺序、层级、地图标签、步骤文字、aria 都随之，不改 CSS | LD-1…5、MP-14 |
| `?to=constructor` / `?r=__proto__` 不解析；`localStorage` 抛错页面照常 | UR-2、UR-4 |
| 每个实体色的浅 / 深色 `--e-text` ≥ 4.5 : 1 | EP-3 |
| 375 px：首屏有位置码；无横向滚动；3 字母与 13 字母的名字都不溢出 | EP-1、EP-2、GR-8 |
| 减弱动效：弹层无行程、地图无开场 / 脉冲 / 惯性 | SH-13、MP-11 |
| 浅深各渲染：主按钮、按下的分段（`aria-selected` 与 `aria-pressed` 各一）、填色标签，字读得出；名字最长 / 最短各一，`data-fit` 起作用 | LD-2、MP-8、EP-2 |
| 浅深各看总览：墙面与墨线在楼板上清晰；`lint_floor.py` 对 `m-cap` / `m-wall` 无失败也无警告 | MP-16 |
| `rotate` 的牌拖动能绕到后面；oblique 的牌拖动是平移、提示条不写"旋转" | MP-3 |
| 无 JS：名录完整、控件不可见、`<noscript>` 在 | ZS-3、ZS-4 |
| 停手后地图无 rAF；离屏无 rAF | MP-6 |
| **拖动与惯性**：点击拖动工具不发中间的 `pointermove` 时，用下面的片段发合成指针事件；`rotate` 牌与 oblique 牌各跑一遍，再开减弱动效跑一遍 | MP-3、MP-5、MP-6、MP-11 |
| 长条楼（脚印 > 1.6 : 1）375 px 竖屏：每层脚印填满宽度；转横屏恢复 | MP-17 |
| 7 个楼层钮 + 路线钮在 320 px：控件内横滑，页面无横向滚动，每个钮 ≥ 44 | MP-8、F19 |
| `entity.blocks` 十二种块各一、`fold` 嵌两层、一个故意写坏的块（构建失败并指出位置） | EP-12 |
| 品类道具逐个设成关闭值（`--prop-*`），浅深各看一遍：母题消失、版面不塌、没有残影（`specimen.py --props off` 看整张牌） | `craft-details.md` R08 |
| 键盘走一遍：Tab 到画布 → 方向键 → Enter 名录 → 路线 → Esc；焦点环可见（含切角元素） | MP-1、DR-12、SH-9 |

**合成指针拖动 / Driving a drag with synthetic pointer events**：有的浏览器工具的 `left_click_drag` 只发按下和抬起，没有中间的 `pointermove`，画布转不动，"拖动 1:1、惯性、静止后无帧"就测不到。下面的片段在页面里自己发 `pointerdown` → 一串 `pointermove` → `pointerup`，粘进控制台（`map.html`、`engine-demo.html` 都行；`.evk-map canvas` 要在页面上）。引擎读的是 `performance.now()`，不读事件时间戳，所以步与步之间要真的等（`sleep`），一次发完就没有速度。**页面必须在前台、可见**：后台标签里计时器被节流，速度窗口（最近 90 ms）对不上，惯性测不准。

```js
window.evkDrag = async (o = {}) => {
  o = { canvas: '.evk-map canvas', from: [.75, .5], to: [.3, .5], steps: 9, gap: 16, hold: 0, type: 'touch', ...o };
  const cv = document.querySelector(o.canvas), box = cv.closest('.evk-map'), r = cv.getBoundingClientRect();
  const sleep = ms => new Promise(f => setTimeout(f, ms));
  const sig = () => { const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data; let h = 0; for (let i = 0; i < d.length; i += 97) h = (h * 31 + d[i]) | 0; return h; };
  const fire = (type, [fx, fy]) => cv.dispatchEvent(new PointerEvent(type, { pointerId: 7, pointerType: o.type, isPrimary: true, bubbles: true, cancelable: true, button: 0, buttons: type === 'pointerup' ? 0 : 1, clientX: r.left + r.width * fx, clientY: r.top + r.height * fy }));
  const at = k => o.from.map((v, i) => v + (o.to[i] - v) * k), res = { before: sig() };
  fire('pointerdown', o.from);
  for (let i = 1; i <= o.steps; i++) { await sleep(o.gap); fire('pointermove', at(i / o.steps)); }
  res.dragging = box.classList.contains('is-dragging'); res.moved = sig() !== res.before;
  await sleep(o.hold); fire('pointerup', o.to);
  const t0 = performance.now(); let last = sig(), lastChange = 0, now = 0;
  while ((now = performance.now() - t0) < 4000 && now - lastChange < 600) { await sleep(100); const s = sig(); if (s !== last) { last = s; lastChange = now; } }
  const reset = box.querySelector('.evk-map-reset');
  return { ...res, coastedMs: Math.round(lastChange), resetShown: !!reset && !reset.hidden };
};
await evkDrag();               // 快速横拖，立刻抬起
await evkDrag({ hold: 200 });  // 拖完停 200 ms 再抬起
await evkDrag({ type: 'mouse', to: [.4, .6] });   // 鼠标：横拖转偏航，竖拖还会改俯仰
```

读结果：`dragging` 为真、`moved` 为真（画布像素变了）、`resetShown` 为真（离家了）；快速抬起 `coastedMs` 在 0 到 4000 之间（带惯性滑行，然后**停住**：连续 600 ms 画面不变就是静止，MP-6）；`hold: 200` 的 `coastedMs` ≈ 0（手指停过就不滑行，MP-5）；系统开了减弱动效，三种都是 0（MP-11）。在 Chrome 156 无头模式里实测过：快抬 1.2 s 滑完，停 200 ms 为 0，减弱动效为 0。合成的 `pointerId` 没有真的按下，`setPointerCapture` 会抛，引擎包在 try / catch 里（SH-6）；换成你自己写的画布时，捕获也要这样容错。

---

## 15 偏好与平台适配 / Preferences and platform（PF）
- PF-1 每个"精致效果"有一行回退：`prefers-reduced-motion`（无行程）、`prefers-reduced-transparency`（栏、提示条改不透明）、`prefers-contrast: more`（发丝线加深、次要文字变深）。**对比度模式在深色里也要生效**——选择器特异性不要被深色块盖掉（原站软肋：只在浅色生效）。
- PF-2 悬停样式只在 `(hover:hover)`；`touch-action: manipulation` + 透明 tap 高亮 + 自制 `:active`（GR-7）。
- PF-3 声明 `color-scheme`，两套 `theme-color`；背景图标（`select` 箭头的 data-URI 读不到 CSS 变量）深色另备，或用 `currentColor` / mask。
- PF-4 打印：隐藏地图、弹层、操作钮；文本名录与实体页照印。

---

## 16 语言主次 / Lead language（LD）

层级的规则见 `floor.md` F08；这里是可测的契约。

**契约**

- LD-1 **一个参数管全页**：`lead` = `en | zh`，写在 `<html data-evk-lead>`（`kit.py` 生成，`--keep lead=zh`）。主语言是每个双语配对的**第一个子元素**，生成器按 lead 调换写入顺序，每行带 `lang`。
- LD-2 **角色层与文字层分开**：层级（字号、字重、颜色、顺序）认位置，字体、大小写、字距、断行认 `.en` / `.cn` / `lang`；配方不得把层级写在 `.en` / `.cn` 上（`craft-details.md` B09）。**填色面（主按钮、按下的分段、填色标签）里的配对继承该面的字色**，配方不能再给这三处的 `.evk-k` / `.en` / `.cn` 写颜色（`base.css` "FILLS"，floor F02）。网格格的位置契约是"标记、主行、副行、位置码"。
- LD-3 **跟随 lead 的东西**：地图标签与提示框（MP-14）；路线步骤（取 `step.cn` 或 `step.en` 的标题与整句为主，另一种语言的整句为副）；播报（LV-3）；`EVK.partNav` 的目录行（界面字串随 `<html lang>`，无 lang 时随 lead）。
- LD-4 **两种语言同时可见**（brief 没说单语时）：副语言只更小更淡，不删，副行 ≥ 11 px。
- LD-5 **改 lead 要重排生成的 DOM**：纯 CSS 部件即时生效；配对顺序和 `partNav` 目录要重排或 `destroy()` 重建。（测：切一次 lead，配对主语言都在前，没改任何 CSS）

**呈现**：切换钮（`?lead=zh` 打开即中文优先）| 只在构建期定 | 按部件分工（如主题路线名随内容语言）。

---

## 17 起步页 / Starter pages

`install.py <roll> <目录> --starter --venue data/venue.json`（或单独跑 `scripts/starter.py data/venue.json .evk/roll.json <目录>`，`--card N`、`--dry-run`、`--force`、`--force-assets`）从场地数据和选定的牌长出一套能用的页面：`index.html`（欢迎块、统计、地图预览、搜索 + 楼层筛选 + 分组网格）、`map.html`（地图、楼层控件、搜索、房间 / 展位弹层、路线弹层、静态名录）、`e/<id>.html`（每个实体一页）。**它是起点，不是成品**：下面列出的契约它已满足，其余归你；改页面时留着它的钩子（`sp-*` 类、`id`、`data-*`），先在它上面改，不从零写胶水。

| 文件（套件里） | 项目里 | 管什么 |
|---|---|---|
| `scripts/starter.py` | 构建时跑，不装进项目 | 所有**静态**标记：页面完整、无 JS 也能读；缺的日期 / 时间写"待定 / TBA"，不编；双语配对按 lead 主语言在前 |
| `assets/starter/starter.js` | `assets/starter.js`（**归你**） | 只**增强**：搜索与筛选、地图、弹层、路线、URL。开头的 UI 词典（`/* ui:begin */ … /* ui:end */`）是页面上所有词的来源；`starter.py` 读**项目里这份**的词典（缺的词回落到套件那份）来写静态页，所以改词在项目的 `assets/starter.js` 里改，再重建 |
| `assets/starter/starter.css` | `assets/starter.css`（**归你**） | 版式胶水，只用令牌，不写颜色和字体名 |
| 由 `venue.json` 生成 | `data/venue.js` | `window.EVK_VENUE`（脚本而非 `fetch`，`file://` 也能开） |

加载顺序：`evk/tokens.css`、`base.css`、`recipe.css`、`assets/starter.css`；`<body>` 末尾 `data/venue.js`、引擎（tones、search、spring、sheet、part-nav、wayfind、venue-map）、`assets/starter.js`。venue 可选字段：`event {name, date, time, place, note, group_by}`、`floors[].short`（楼层的短名，见下）、`terms.tags`（标签的中英文词）、`entity.facts` / `parts` / `blurb` / `blocks`（`reading.md` §3.1）、`x-schematic`（示意横幅 + `noindex`）、`x-groups`（搜索组词，也是按标签分组时的组），见 `assets/engine/venue.schema.json`。已有文件不覆盖，冲突一次列全、什么都不写，加 `--force` 才覆盖（重建会盖掉你对这几页的改动：改动大了就不要再重建）。

**`--force` 与 `--force-assets`**：`--force` 重写**生成的**页面（`index.html`、`map.html`、`e/*.html`）和 `data/venue.js`，但**从不**覆盖项目里已有的 `assets/starter.js`、`assets/starter.css`——那是你的拷贝，`plan()` 把它们排除在冲突之外，`render.kept` 列出被留下的。要把这两个文件换回套件的版本，直接跑 `starter.py … --force --force-assets`（你对它们的改动会丢，先备份；`install.py` 只有 `--force`，不带这个开关）。于是改词的循环是：改项目的 `assets/starter.js` 词典 → `starter.py … --force` → 静态页带上新词；静态页里项目拷贝缺的词回落到套件那份；浏览器里的脚本只认项目拷贝自己的词典，缺一个词就显示键名，所以套件新增了词、改了脚本，要把它们合并进项目的拷贝（或 `--force-assets`）。

**已满足**（括号是契约编号；代码在 `starter.js`，静态部分在 `starter.py`）

- 搜索与网格：SE-0、SE-3、SE-4、SE-6、SE-7、SE-8、SE-9（用 `EVK.search`；就地隐藏、空组整组隐藏、空态 `role="status"`；Enter 取首项；目的地预填完整名称；占位符的例子是一两个**真实名称**（没有就取一个房号），用**主语言**写，汉字间无空格、汉字与拉丁 / 数字间一个空格，从不拿标签 id 当例子）· GR-1、GR-2、GR-5、GR-6（2 / 3 / 4 列，`base.css`）。
- **分组**：`event.group_by` = `floor`（默认）| `tag` | `room`。`tag` 的组取自 `x-groups` 里带 `tags` / `ids` 的项，否则取每个实体的第一个标签；组名取 `terms.tags` 的中英文词，没有就取标签 id 首字母大写（最后手段，给每个出现的标签写词）。多于一组时多出一个分组控件（`#seg-group`），`?g=<组键>` 打开即只显示该组（`group_by=floor` 时键就是楼层 id）；楼层控件照旧。
- 实体页：EP-1、EP-2（`data-fit`；抬头里的附加行是 `.evk-entity-sub` / `.evk-entity-line`）、EP-3（实体色由 `tones` 写成内联角色）、EP-4（先词后值的 DOM，`starter.css` 倒置）、EP-6（操作是链接，无 JS 也通）、EP-7（近景小图 `role="img"` 说出在哪）、EP-10、EP-12（`entity.blocks`：带 `title` 的块自成一章并进目录，没有 `title` 的接在前一章后面，没有章就先立一章"简介 / About"；`entity.parts` 在前、块生成的章在后；12 种块的形状见 `starter.py` 文件头与 `reading.md` §3.1）；`[data-part]` 章节 + ≥ 3 章时的目录列表即 RN-1、RN-8（`part-nav.js` 在页面就绪时对 `[data-report]` 自己挂 `partNav`，其余 RN 由它负责）。
- 地图：MP-1、MP-2、MP-8（`aria-pressed` 组，路线中无一选中，按楼层 = 结束路线；至多 6 个楼层钮加路线钮在 320 px 也在控件里横滑）、MP-3（提示条、画布 label 与地图介绍随卡的投影，词典里各三组词 `map_hint` / `_pan` / `_plan`，同样的 `map_drag*`、`map_what*`、`map_view*`：orbit 与 exploded 写"拖动旋转 / Drag to rotate"，oblique 写"拖动平移 / Drag to pan"；plan 的单指拖动在引擎里是纸面内转，词要与引擎一致，见 MP-3）· RF-1、RF-4、RF-5、RF-6（点房间 / 标记 / `?r=` / 名录房间卡同一终态，`focusRoom(null)` 回原视图）。
- 路线：DR-2（先问起点，大堂在前；再搜目的地）、DR-4（算不出有可见提示）、DR-5、DR-6（`aria-current="step"`，爬楼用第二色**加文字**）、DR-9、DR-10、DR-11、DR-12（重绘后恢复焦点）、DR-14、DR-15 · SH-1、SH-10（`EVK.Sheet`，一次一个）· MS-5、MS-6、MS-8（`EVK.fitAbove.watch`）。
- URL 与记忆：UR-1…UR-4、UR-7（地图页 `?s= ?r= ?f= ?to= ?from= ?via=lift`，首页 `?g=`；查表用自有属性；`replaceState`，保留 hash，只动自己的参数；起点记在 `localStorage`，try/catch，读出时校验仍存在）。
- 缺席与读屏：ZS-1、ZS-3（需 JS 的控件在标记里 `hidden`）、ZS-4（静态名录 + `<noscript>`）、ZS-6、ZS-7（`x-schematic`）· LV-1、LV-2、LV-3、LV-6 · LD-1、LD-3（lead 来自卡）· F10（静态文字里两个汉字之间无空白）。
- **楼层的两种写法**：`floors[].short`（`{en:"4F", cn:"4 层"}`，缺省 = id 与"<层号> 层"）用在路线句子、楼层钮、标签和位置行（"204 · 4F"），`name`（`{en:"Fourth Floor", cn:"四层"}`）只用在标题；同一个字符串从不印两遍（`name` 与 `short` 在某种语言里相同就只印一次，起点下拉里"1F 大堂"不再加"1F"后缀）。改了引擎里 `short` 的缺省，`starter.py` 的 `Site._places` 与 `starter.js` 的 `FL` 要同改。

**归你**（起步页没做，或只做了默认）

- TR 主题路线；DR-1 的房间弹层入口（地图页有全局按钮，展位弹层与实体页有"怎么走"，房间弹层只列展位）；UR-5 / UR-6（拼错容错、404、根绝对链接：起步页用相对链接，才能在 `file://` 和子路径下直接打开，上线前自己定）。
- EP-8 图片与署名；EP-11 slug 冻结（`e/<id>.html` 取自 venue 的 `id`，印成二维码前冻结）；EP-12 里起步页没有的：来源脚注、访谈带（`reading.md` §2.6、§7）。
- SE-2 / SE-5 的组词与歧义词：写进 `x-groups`。
- MP-12 的构建期校验：起步页不跑，自己跑 `node evk/engine/wayfind.js --selftest data/venue.json`（套件里是 `assets/engine/`），并对建好的页面跑 `lint_floor.py page.html`。
- 词典里的措辞（`map_hint*`、`cv_*`、`search_ph` 等）按项目的口气改：改项目的 `assets/starter.js`，再 `starter.py --force`（上面的循环）。
- 改了生成的页面，在 `DESIGN.md` 的 Deviations 记一行并写明还原法。
