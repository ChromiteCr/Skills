# 印刷、二维码、徽章、字体与照片 / Print parity and asset craft

原站的每个素材走同一条路：**一份母版 → 一个脚本 → 按使用尺寸生成 → 输出入库**，站点构建只用标准库。52 个风格各异的校徽、156 张出自上百位摄影师的照片、52 张印刷告示能看起来是一家人，靠的是**变换**，不是来源。本 kit 不带任何第三方素材；这里写的是项目自己的素材管线，数值是"原站取值"，旁边给区间或备选。

## 何时使用 / When to use

印刷告示要和网页实体页"是一家"：§1。放二维码：§2。外来标志（校徽、展商、赞助商）进统一网格：§3；客户的 logo 与体系冲突：§4。字体与预算：§5、§9。照片：§6。署名与版权：§7。写文案：§8。

## 原则一页纸 / Principles

1. 素材 = 母版 + 脚本 + 使用尺寸的输出，输出入库；重工具（Pillow、fontTools、Chrome）只在源变化时跑。
2. 脚本**先失败后写入**：缺文件、未知 slug、授权不符、图太小、页数不对，都在写任何东西之前停。
3. 印刷与网页用同一套设计系统和字体。移植时保角色、顺序、颜色、角色间比例，再按新媒介重设绝对尺寸。
4. 印刷系列固定几何，让内容去适应，不要反过来。
5. 机读部件（二维码）不上色，只加框。
6. 署名是数据：来源表按资产 ID 建，缺一条就是构建失败。
7. 下载物当数据：放进不入库的 `incoming/`，`python3 -I` 读，外部命令加超时。

---

## 1. 打印告示与实体页同一设计 / Print notices share the entity-page design

原站：每校一张 A4 横版（52 张），由设计稿的竖版桌牌转成横版。脚本头写着目标："实体名和两个二维码是最大的，其余都小。"

### 1.1 移植 = 保角色，不保数值

| 角色 | 设计稿桌牌（A4 竖，4 px/mm） | 网页实体页 | A4 横版告示 |
|---|---|---|---|
| 边距 | 60 px = 15 mm | 页边 20 px | 16 mm |
| 实体名 | 700，372 px = 93 mm，行高 .74，-.025em，不折行，适配下限 96 px（步长 4） | `clamp(3.6rem, 19vw, 9rem)`，行高 .86，按字数分 `fit-2/3/4` | **44 mm**（桌牌的 47%），行高 **.9**，-.01em，适配下限 8 px（步长 1） |
| 规则线 | 6 px，红尾 64 px | 6 px，尾 64 px，最宽 660 px | 1.6 mm，红尾 22% |
| 全名 / 中文名 | 600 38 px / 500 32 px，.08em，keep-all | 页面正文 | 600 6.4 mm / 500 6 mm，.06em |
| 条纹 | 12/4/6/4/12 px（3:1:1.5:1:3），在红带上方 | 3:1:2:1:3 | 3:1:2:1:3 渐变，3.5 mm，页中 |
| 房间与展位 | **通栏红带 72.5 mm** 在底部，房号 42.5 mm 高；`BOOTH` 加 76 px 号码，3 px 纸白下划线 | 红色房间带、展位号 | **无红带**；房号 20 mm 高落在纸上；展位号 11 mm **红**，.6 mm 深蓝下划线，宽 52 mm |

横版保留了语法（眉标、巨大的名字、规则线、全名、中文名、条纹、铭牌、展位行），按新格式的任务重设尺度：名字缩到 47% 好让两个二维码入场，行高 .74 放到 .9，竖版独有的底部红带去掉，房间和展位交给小铭牌加红色数字。**这是移植，不是复制。**备选：竖版原样保留、二维码放背面；横版保留红带并把二维码放进红带；从零设计，只借 token。

### 1.2 三档字号

| 档 | 原站取值 | pt（推算） |
|---|---|---|
| 英雄：实体短名；两个二维码块 | 44 mm / .9；80 × 80 mm | 124.7 pt |
| 中档：全名 6.4 mm；中文名 6 mm；二维码说明 6.2 mm；展位号 11 mm / .8 | | 18.1 pt；31 pt |
| 标签：大写标签 | 2.7 / 2.8 / 3.0 / 3.1 / 3.2 / 3.4 mm | 最小 7.65 pt |

先决定哪 2–3 样东西要在远处读，让它们靠**比例（≥ 6:1，原站约 7:1）**占优，其余缩到接近图注，不放第四档。观看距离也是三个：隔着房间（名字、二维码）、桌边（全名、号码）、凑近（标签）。备选：只留名字一个英雄，二维码降到 40 mm；英雄 = 房号；英雄 = 照片。

### 1.3 固定几何

- 同一左轴 `left: 16mm`，右 16 mm，页眉 `top: 9mm; height: 14mm`，底部 ≈ 9 mm；**只有条纹出血**（`left: 0; right: 0`），一条出血带对着带页边的内容，读作"桌沿"。
- 区带绝对定位（mm）：页眉 9–23；名字块 26–92；条纹 95–98.5；下区 103（二维码）/ 105（位置块）；页面 `297mm × 209.8mm; overflow: hidden; break-after: page`。52 张几何一致，叠在桌上对齐，二维码永远在同一处；流式布局会让区带随名字长短漂移。
- 备选：CSS grid 命名行（`grid-template-rows: 14mm 1fr 3.5mm 1fr`）；居中对称；12 列；悬挂缩进。

### 1.4 页高、纸色与出血

- **页高 209.8 mm，不是 210。**Chrome 的 A4 页高是 594.96 pt = 209.89 mm（推算），210 mm 的盒子会溢出，每张多出一页空白。0.2 mm 余量避免 52 张空白页；`.page:last-child { break-after: auto }`；渲染脚本断言 PDF 页数等于张数，否则中止。
- PNG 路径：画 3512 px 宽，再裁成 3508 × 2480，存 `dpi=(300,300)`（A4 @ 300 dpi = 3507.9 × 2480.3 px，推算）。
- **纸色是故意印出来的**：`html, body, .page { background: <paper>; -webkit-print-color-adjust: exact; print-color-adjust: exact }`。原站：粉笔白 `#F7F5F0`，正文用深蓝而非黑，整张只有深蓝和红两种墨；纯白和纯黑留给二维码和徽章盘这类机读 / 中性部件。
- 备选：白纸只印墨色（便宜，没有出血问题）；整张深色纸；向印厂指定有色纸而不是印背景。出血：原站没有，没和印厂核实（未验证）。

### 1.5 名字适配：测量，不要猜

- 等 `document.fonts.ready`，再循环缩小：步长 1 px，下限 8 px，容差 0.5 px。全名：`scrollWidth > clientWidth + 0.5`；短名（`white-space: nowrap`）：`scrollWidth > clientWidth + 0.5 || text.offsetHeight > box.clientHeight`。结束设 `body[data-ready="1"]`，渲染器等它。
- 观察：Northwestern 刚好撑到规则线末端；Georgia Tech 约占栏的 76%、Princeton 约 58%，保持满字号。
- 其他实现：网页按字数分桶 `fit-2`（5–7 字符）、`fit-3`（8–12）、`fit-4`（> 12），`--fs` 依次 `clamp(3rem, 14vw, 7rem)`、`clamp(2.6rem, 10.5vw, 5.4rem)`、`clamp(2.2rem, 8.2vw, 4.4rem)`。备选：`text-wrap: balance` 允许两行；窄字宽轴；缩写表；不推荐 SVG `textLength`。
- **陷阱**：紧行高加 `overflow: hidden` 会切掉下降部（g y p j）；原站 Georgia Tech 的 g 被切平。用 `overflow: clip` 加 `overflow-clip-margin`，或底部留内边距，或只测量不裁切。

### 1.6 名字块与规则线

顺序：地区眉标（3.2 mm 红，宽大写 700，.16em；中文 3.1 mm 灰 .06em，`margin-left: 2.5mm`）→ 短名 → 规则线（高 1.6 mm，`margin: 4mm 0 3.6mm`，深蓝 `flex: 1` + 红尾 22%）→ 全名 → 中文名（`margin: 1.6mm 0 0`）。这是报纸标题栈：眉标 / 主标 / 下划线 / 副标 / 本地语言行；对应 kit 的 `.evk-eyebrow`、`.evk-entity-name`、`.evk-entity-rule`。

**装饰端帽按媒介重新定比例**，它是栏宽的函数：桌牌尾 64/720 px ≈ 8.9%，网页 64/660 ≈ 9.7%（推算）；横版 222 mm 的栏上 16 mm 只占 7%，读作斑点，所以印刷取 22%（≈ 49 mm）。备选：尾 = 线厚的 3 倍方块；尾 = 展位号下划线的宽度（52 mm）；按 3:1:2:1:3 切分。

### 1.7 线与框

- 四种线厚按角色复用：**.4 mm**（浅分隔）、**.6 mm**（画框、下划线）、**1.6 mm**（规则线）、**3.5 mm**（条纹）。
- 画框用盒外的 `box-shadow: 0 0 0 .6mm <ink>`：80 mm 的牌就是 80 mm，二维码几何不变。白块落在粉笔白上只差约 3% 亮度，框是必要的。备选：`outline` + `outline-offset`；裁切标记式的角框。

### 1.8 位置块与"深蓝 = 信息，红 = 行动"

- 位置块（`left: 16mm; top: 105mm; width: 80mm`，列布局，间隔 1.6 mm）：三层房号 SVG 高 20 mm（缺文件时文字回退）→ `ROOM 201 · 2F` 3.4 mm / `二层 · 201 展区` 3.3 mm 灰 → 展位行（宽 52 mm，`padding-bottom: 1.2mm; border-bottom: .6mm`；左 `BOOTH` / `展位号` 叠放 2.7 mm，右展位号 700 11 mm / .8 红）。
- 层级：大铭牌（在哪）> 小标签（是什么）> 画线的值（哪一个）。展位号坐在下划线上像"填写栏"，红色 = 这位展商独有的数。
- 颜色二分：深蓝 = 信息（详情码说明），红 = 行动（投票码说明）。红也用在眉标、展位号、规则尾上，所以这是**倾向，不是规则**。备选：一行 `201 · 01`；平面图缩略图加红点；按楼层上色。

### 1.9 双语与混排

- **按元素定主语言**：名字是专有名词，英文主（44 / 6.4 mm 压在 6 mm 灰中文名上）；指令是说给读中文的学生听的，中文主（`扫码查看本校详情` 6.2 mm 600 压在 3 mm `SCAN FOR DETAILS` 上）；标签地址英文大写在前、中文在后更小更灰。次要语言永远要有，只是更小或更淡。全名 / 中文名 = 6.4 / 6 = 1.07（推算），靠颜色（`#13294B` 对 `#5B6270`）和字重补足。
- **每种文字单独设字距**：大写 .16em，CJK .06em；`.cn` 显式重置 `text-transform: none; letter-spacing: .06em`（中文常嵌在 `.k` 里，会继承拉丁字距；套件的 `base.css` 文字层已含这套重置）。日期两种语言都印、靠右，`align-items: baseline`（不是 `center`），拉丁大写和汉字才同基线；`lang="zh-CN"`。
- 双标志：主标 14 mm | 发丝线（.4 × 8 mm）| 副标 7.5 mm，间隔 5 mm；主标 ≥ 副标 1.8 倍，共用中线。备选：上下叠放；副标缩成文字；只用一个。

### 1.10 输出管线

- 同一套 HTML / CSS / 字体 → 无头 Chrome → 矢量 PDF → 光栅化 3508 × 2480 PNG（300 dpi）。参数：`--headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --allow-file-access-from-files --virtual-time-budget=20000`。
- **字体以 data URI 内嵌**，无头 Chrome 不需要文件 / 网络；印刷 `font-display: block`（不能印出回退字体），网页 `swap`。
- 矢量加光栅都交付（PDF 12.0 MB / 52 页；PNG 平均 356 KB）。
- **按用户的工作流排序**：楼层 → 房间 → 展位，文件名 `<房间>-<展位>-<slug>.png`（`201-01-Princeton.png`），PDF 同序；贴告示的人是一间间走的。备选：字母序；一房一 PDF。
- 装饰图 `alt=""`；名字、房号、展位保持活文字，PDF 可搜索。
- **别手抄调色板。**原站在 `notices.py`、网页 CSS、设计稿 token 三处各写一份，会漂移，品牌测试只查网页那份。在 kit 里，告示 HTML 引用项目的 `evk/tokens.css` 用 `var(--paper)` 等（Chrome 打印支持自定义属性），实体色用 `scripts/tones.py` 派生。**品类道具的开关也在同一份 `tokens.css` 里**（`--prop-*`，`derive.md` §8.1）：网页上关掉的母题（叶形标签、网点、条码……），告示引用同一份令牌就同样关着；告示里自己画的母题（比如票根底部的条码）按同一份盘点依据决定留不留，别网页关了、告示还印着。

骨架（示意）：`@page { size: A4 landscape; margin: 0 }`；`.sheet { position: relative; width: 297mm; height: 209.8mm; overflow: hidden; break-after: page; background: var(--paper); print-color-adjust: exact }`；各区带 `position: absolute`，只有条纹带 `left: 0; right: 0`；二维码块 `box-shadow: 0 0 0 .6mm var(--a)`。

---

## 2. 二维码工艺 / QR craft

| 项 | 原站取值 | 为什么 / 备选 |
|---|---|---|
| 颜色 | `<rect fill="#fff"/><path fill="#000"/>` + `shape-rendering="crispEdges"`；测试断言 `fill="#000"` | 最高对比、无抗锯齿：隔桌、弱光、激光打印都能扫。品牌色只出现在 .6 mm 画框和说明文字。备选：深色模块（对比 ≥ 7:1，风险更高）；圆角模块加中心 logo；反白（易扫不出） |
| 静区 | 资产自带 `BORDER = 4` 模块，牌子再加 `padding: 3mm` | 推算：29 模块加两侧静区 = 37 模块，74 mm 内方 → 2.0 mm/模块，静区 8 mm，加 3 mm = 11 mm 白边。静区属于二维码资产，不属于页面 |
| 纠错 | 级别 M（15%） | 脏污折痕可恢复又不增密度。备选：L；Q/H 加 logo |
| 密度 | 推算：51 个 slug 是 29 × 29（版本 3），1 个（Northwestern，43 字符）是 33 × 33，模块 2.0 → 1.8 mm | 为码密度设计 URL：短域名 + 短 slug，并检查**整套**最大长度（42 字符是版本 3-M 的界限） |
| PNG | 1 位灰度，32 px/模块，`pHYs` ppm = round(300 / 0.0254) = 11811，zlib 9；37 × 32 = 1184 px = 10.0 cm @ 300 dpi（推算） | 整数倍无重采样模糊；1 位文件小；dpi 标签让 Word 默认按 10 cm 插入。测试解码 PNG 并与编码器逐模块比对。备选：纯矢量；屏幕用 16 px 模块；8 位透明 |

- **第三方给的码**只归一化，不重生成、不改样式：去截图蓝框、阈值成 1 位、去 JPEG 噪点，放进尺寸相同的同款白块，`image-rendering: pixelated`（1180 px 位图以 74 mm 显示约 400 dpi，模块边保持硬）。备选：要原始 URL 自己生成（信任模型变了）；放进它自己的卡片；两个目标合成一个落地 URL。
- **说明三件套**：中文指令（6.2 mm / 600）、英文大写（`SCAN FOR DETAILS` 3 mm）、可输入的 URL（2.8 mm 灰）。自己控制的 URL 都给人一个可输入的后备；对方的链接（投票码）只写 `扫码投票 / SCAN TO VOTE`。备选：编号短码；NFC。

---

## 3. 第三方标志归一 / Badge normalisation: any third-party mark into one family

校徽、展商 logo、赞助商、讲者机构，进同一网格都要过同一组变换。原站：同一个白盘、同一套缩放律、同一条安全边；母版 128 × 128 调色板 PNG，细环由网页 CSS 画。

| token | 含义 | 原站取值 | 备选 |
|---|---|---|---|
| ground | 公共中性底 | 不透明纯白圆盘，盘外透明 | 粉笔白方块；实体色 10% 浅底；透明加投影；全部重着色成单色 |
| container | 公共外形 | 圆（唯一不偏向任何标志轮廓的形状） | 圆角方；与方向的切角一致（`--chamfer`）；不加容器 |
| fit | 尺寸律 | 圆章占盘 **92%**；其他最长边 **74%**，越窄越大至 **83%**：`side = min(0.74 · (max/min)^0.25, 0.83)` | 全部同比例；按填充面积；逐个手调 |
| clamp | 安全边 | 每次缩 1%，直到每个像素 `hypot(x·side, y·side + lift) ≤ 0.90 / 2` | 允许横幅出界并软遮罩 |
| centre | 光学中心 | 高盾（h/w > 1.05）下移 2% 直径 | 取质心；顶对齐 |
| ring | 外环 | 页面 CSS 画，随主题变 | `box-shadow: 0 0 0 var(--hair) var(--rule)`；实体色环 |
| ladder | 尺寸阶梯 | 首页网格 30 px（母版 128 = 4.3 倍）；页头 52 → 76 px；印刷 34 mm（母版 640 px） | 母版 ≥ 最小用途 × DPR 3 |
| blank | 没有标志 | 文字回退 | 首字母字标落在 `--e-tint` 上（`.evk-mark` 的占位） |

面积为什么要补偿：圆章本身是圆，填 92% 像盘子本身；盾有角有尖，92% 会戳出圆外；方形取 74% 让视觉重量与圆章相当（等面积应是指数 0.5，推算；0.25 是折中）。

- **圆章判定**：宽高比在 [0.9, 1.1]，且四个角方块（各 12% 边长）最大填充占比 ≤ 0.10，且 72 个角度桶的径向到达（`far = 2·hypot`，1.0 = 最长边的一半）10 百分位 ≥ 0.8、最大 ≤ 1.1；菱形在对角线上只有 0.71，判非圆。用分位数不用极值。备选：手填 `kind`；与内切圆 IoU > 0.85。
- **取轮廓**：有 alpha（`histogram()[255] < 0.995·w·h`）用 `alpha > 8`，没有就把最暗通道 > 245 当背景。**不透明的圆形源**先用 4 倍椭圆裁一遍（略大于外框的内切圆），LANCZOS 缩小，`alpha = min(alpha, clip)`，否则白底 JPEG 的方角会在深色地图上露出鬼角。
- **抗锯齿**：4 倍超采样合成（512 px）再 LANCZOS 缩到 128；SVG 栅格化 1024。
- **颜色与边缘透明度分开量化**：铺在白上 `quantize(colors=240, FASTOCTREE, dither=NONE)`；通道全 ≥ 250 的项吸附成精确 `#FFFFFF`；盘边软 alpha（< 250）映射到 **16 个"不同透明度的纯白"**（`tRNS = [255]*n + [round(k·255/15) for k in range(16)]`）。RGBA 一起量化会把白盘变成几种近白，深色背景下是灰斑。
- **质量门**：`drift(a, b)` = 两图合成在中灰 `(154, 160, 166)` 上的平均绝对差（0–255）；`MAX_DRIFT = 3.0`，超了改存 RGBA；每文件打印一行 `Stanford fit palette 7.3 KB`。在中灰上比，才暴露白底上看不出的白边和 alpha 错误。备选：SSIM；联系表人工看。
- 印刷另渲一份（`SS = 2, RENDER = 2048, SIZE = 640`），目标不存在或比源旧才重做；缺 Pillow 回退到站点 128 px。**每个尺寸都从母版出，绝不放大缩略图。**观察：34 mm 盘配 640 px ≈ 478 dpi（推算），过量，12 MB（RGBA，没走调色板路径）。
- **网页上怎么用**：网格与页头里的真实标志写成 `<span class="evk-mark evk-mark--img"><img …></span>`。`base.css` 把它放在纸色圆盘上、细线外环、`object-fit: contain`；不加 `--img` 的 `.evk-mark` 是各方向的纯色或纯形标记，里面的图片会被 recipe 隐藏。地图上的同一批标志由 `--m-token: badge` 渲染，`VenueMap` 的 `image(entity)` 返回同一张图。
- 色彩分工：克制的色板里，标志成为唯一的"变化色"，52 个小彩盘是地图的数据点和首页网格的视觉索引；选中一个时其余淡出。备选：校园照片作颜色来源；统一字体的字母标。

---

## 4. 贴纸式裁切 / Sticker-logo cut: a client logo that clashes with the system

**情境**：主办方晚到的 logo 是白纸上的位图（原站：3000 × 3000 JPEG，拱门、书、栗色大写，与深蓝 / 红 / 粉笔白不同），要放在纸面、深色模式和品牌色面板上。**做法**：不重新着色，用白边隔离，缩小使用（页头 144 px，告示 14 mm），让体系的 token、字体、条纹、切角继续承担身份。

| 参数 | 原站取值 | 含义 |
|---|---|---|
| `INK` | 225 | 最暗通道 < 225 属于 logo |
| `SPECK` | 400 px | 更小的连通块丢弃 |
| `CLOSE` | 0.03 × 宽（90 px） | 窄于约两倍此值的缺口（字母之间、大写下方）被填平 |
| `RIM` | 0.012 × 宽（36 px） | 白色贴纸边 |

步骤：连通域标记 → 去斑点 → 四周 pad `c + r + 2` → `binary_closing(disk(c))` → `binary_dilation(disk(r))` → `binary_fill_holes` → `gaussian_filter(sigma = r·0.6) > 0.5`（圆润外轮廓）→ 去 pad → 裁到包围盒 + 4 px。拱门内部和字母之间的白保留，加一圈细边，读作实体贴纸，放在粉笔白、深蓝、深色模式上都没有可见矩形。

细节：缩放前把透明像素的 RGB 置白（`rgba[..., :3][rgba[..., 3] == 0] = 255`），否则缩放器把透明处的黑插进边缘；图标版留 4 px 透明边（192 × 192 画布，logo 缩略到 184），免得浏览器的图标蒙版切到白边。输出按角色命名：`emblem.png` 高 640（入口面板；31.3 KB）、`emblem-small.png` 高 144（页头页脚；6.5 KB）、`emblem-icon.png` 192 × 192（6.8 KB），都量化成 256 色 FASTOCTREE、无抖动。一份母版加一个脚本，晚到的 logo 替换就是一条命令。

备选：放进白色圆角徽章；去掉白底（需要反白版）；重着色成单墨；专用中性面板。

---

## 5. 字体子集预算 / Font subsetting budget

**先分路：能不能下载字体文件？** 下载要先问使用者（说清文件名、来源、大小）。牌上的字体都是免费字体，但套件不带文件，页面运行时也不向第三方要字体（floor F27）。

| 路 | 做法 | `DESIGN.md` 写什么 |
|---|---|---|
| **不能下载**（没网、没授权、使用者说不） | 直接用 `tokens.css` 的 `--f-*` 栈：每个栈已以系统回落和 CJK 系统字收尾（lint F09 查），牌上的字名留在栈首，装了的人看到原字。页面里不放任何字体 CDN 的 `<link>` / `@import`。上线前用回落字重看一遍：大字的字距、名字分档（EP-2）、数字宽度是按牌上字体调的，回落字更宽或更窄就要重测；`specimen.py` 默认联网预览字体，加 `--offline` 看到的才是实际会出的样子（`--png` 截出的样张图同理：要看回落字就带 `--offline`）。 | "字体：系统回落（牌上的 X、Y 未装载）"，并列出每个声音落到哪个系统字 |
| **能下载** | 自托管，裁成子集（见下）；OFL 文本放字体旁；样张里的联网字体链接不要抄进页面。 | 字体清单：文件、字符范围、轴、字节数、授权 |

自托管的做法（`pip install fonttools brotli`，只在你的机器上跑，站点构建不依赖）：
```bash
# 静态字体：裁成 Latin 子集（范围同下面的"Latin 范围串"）
pyftsubset Face-700.ttf --unicodes="U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD" \
  --layout-features='*' --flavor=woff2 --desubroutinize --name-IDs=0,1,2,3,4,5,6,13,14 --output-file=site/fonts/face-700.woff2
# 可变字体：先裁（同上，去掉 --flavor），再钉轴（轴=值 钉死，轴=最小:最大 限幅），最后转 woff2
fonttools varLib.instancer Face-sub.ttf wdth=125 wght=500:800 -o Face-pinned.ttf
fonttools ttLib.woff2 compress Face-pinned.ttf -o site/fonts/face-expanded.woff2
```
```css
@font-face { font-family: "Face"; src: url(fonts/face-700.woff2) format("woff2"); font-weight: 700; font-display: swap; }
```
`<link rel="preload" as="font" type="font/woff2" crossorigin href="fonts/face-700.woff2">` 至多两个；文件名带内容哈希，`Cache-Control: public, max-age=31536000, immutable`；CJK 仍用设备字体。

| 原站取值 | 内容 | 大小 |
|---|---|---|
| `zilla-slab-600.woff2` / `-700.woff2` | Zilla Slab SemiBold / Bold | 23,512 / 23,372 B |
| `archivo-expanded.woff2` | Archivo 可变 [wdth, wght]，**wdth 钉在 125**，wght 保留 500–800 | 29,696 B |
| 合计 | 3 个文件 | 76,580 B = 74.8 KB |

- **一个展示声音加一个标签声音，各自硬子集。**建议区间（非原站）：2–4 个文件，合计 40–120 KB。
- **先子集，再钉轴**：`desubroutinize = True`；`name_IDs = [0,1,2,3,4,5,6,13,14]`（保留版权和许可条目）；OFL 文本放字体旁；`instancer.instantiateVariableFont(font, {"wdth": 125, "wght": (500, 800)})`。钉死的实例起个以实物命名的家族名（`"Archivo Expanded"`），CSS 里就不用 `font-stretch` hack。
- **Latin 范围串**：`U+0000-00FF, 0131, 0152-0153, 02BB-02BC, 02C6, 02DA, 02DC, 0304, 0308, 0329, 2000-206F, 20AC, 2122, 2191, 2193, 2212, 2215, FEFF, FFFD`。**U+2192（→）不在范围内**（只有 2191 / 2193），右箭头会回退到别的字体；U+00B7（·）在 Latin-1 里。要用箭头就加进子集或改画 SVG。
- **中文用设备字体，不发 CJK**：`"PingFang SC", "Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`（kit 里是 `--f-cjk`）。备选：CJK 子集加 `unicode-range` 与 `font-display: optional`；中文衬线。
- **数据数字强制 `font-variant-numeric: lining-nums tabular-nums`**：Zilla 默认是旧式数字，"52 universities. 10 rooms. 3 floors." 里的 3 会掉到基线下。
- **加载**：只 preload 首屏用到的两个（700 与 Archivo，`<link rel="preload" as="font" type="font/woff2" crossorigin>`）；网页 `swap`，印刷 `block`；文件名带 10 位内容哈希，`Cache-Control: public, max-age=31536000, immutable`。备选：`optional`（无布局偏移，可能永远用回退字体）；全用系统字体。
- **回退栈按"类"配**：板岩衬线 → `Rockwell, Georgia, serif`；宽无衬线 → `"Helvetica Neue", Arial, sans-serif`，换字只变纹理不变类别。
- OFL 1.1 随字体发；原站测试禁止任何第三方 CDN。本 kit 只按名字引用字体并带系统回退，不带文件。

---

## 6. 照片管线 / Photo pipeline

| 项 | 原站取值 | 区间 / 备选 |
|---|---|---|
| 宽度 | hero 1440、内页 1200、小图 720，每校 3 张 | 480 / 960 / 1920；AVIF + WebP |
| 体积（实测） | 大图均 165 KB（hero 200、内页 148、最大 408、最小 24），小图均 50 KB（最大 109）；共 26.4 + 8.1 MB | 按角色设预算 |
| 编码 | WebP `quality=60, method=6`，LANCZOS | 理由未记载，推测风景 / 建筑低细节。备选：hero q75–80、内页 q55；AVIF q35；LQIP |
| 比例 | 手机 4:3（分隔图 3:2）；≥ 760 px 时 hero 16:9 加 `max-height: 74vh`，分隔图 21:9；`object-fit: cover` | 全 3:2；方形网格；全出血 100vh；瀑布流 |

源图 h/w 最小 0.434、中位 0.667、最大 0.785。标记（无布局跳动）：

```html
<img src="small.webp" srcset="small.webp 720w, big.webp 1440w" sizes="(min-width: 1160px) 1080px, 100vw"
     width="1440" height="960" alt="…" style="object-position:50% 45%" loading="lazy" decoding="async">
```

宽高来自内容数据里存的自然尺寸；hero eager（它是 LCP），其余 lazy；加载前占位用实体浅色。备选：`<picture>` 加 AVIF；`fetchpriority="high"`。

**已知缺口**：`srcset` 只有 720w 和 1440w / 1200w 两个候选，390 CSS px 的 DPR 2 手机要 780 设备像素，已超 720w，会取大图，手机一页照片约 0.5 MB 而不是 150 KB（推算）。补一个约 960w 的中间候选即可。

**`focus_y`：每张照片存一个纵向焦点**（0–1，默认 .5，留两位小数），仅当 ≠ .5 才输出 `object-position: 50% {focus_y·100}%`。原站 156 张全有：62 × 0.50、42 × 0.45、13 × 0.40、12 × 0.42、10 × 0.55，其余 17 张在 0.15–0.62（傍晚的 Von KleinSmid Center 0.15，Scripps Pier 0.62）。为什么：同一张图被裁成 4:3、16:9、21:9，21:9 只留 3:2 照片高度的 64%（0.4286 / 0.667，推算），留塔还是留草坪要由图决定；校园照片的主体略高于中线，所以 0.45 最常见。备选：二维焦点；显著性自动裁切；`<picture>` 预裁三份。

**说明与署名**：手机上图出血穿过页边（`margin: 22px -20px 0`）；`figcaption` 用 flex、两端对齐，`font-size: .72rem; line-height: 1.5; color: var(--sub)`，左 `{中文主题} · {English subject}`，右 `Photo: {作者} · {许可链接}`，链接 `color: inherit`、1 px 规则色下划线。署名**紧贴图下方**，字小而淡，不躲进页脚。备选：角标叠在图上；点按显示；只放画廊页脚和 `SOURCES.txt`。

**放置**：每校最多 3 张当长文的章节分隔：#1 在名字下（hero），#2 在第二部分前，#3 约 2/3 处，分隔图 `margin-top: 56px`。说明写有名字的地标（双语），提供信息而不是装饰。

**内容契约与授权门**（失败即中止）：必填键 `file, page, author, license, subject_en, subject_cn`，缺则退出并指明第几张；源图窄于 1200 px 拒收；缩放前 `ImageOps.exif_transpose`；每次运行先删旧 WebP；只收 CC0 / Public domain / PD / CC BY(-SA)，用 `\bN[CD]\b`（先把 `-` 换成空格）拒 NC / ND。测试：照片的 `page` 以可信图库域名开头，授权匹配 `^(CC0|CC BY|Public domain|PD)`。原站分布：CC BY-SA × 88、CC BY × 41、Public domain × 16、CC0 × 11。备选：自己拍摄；插画。

---

## 7. 版权与署名即设计 / Rights and credits as design

- **署名放三处，三个尺度**：资产旁（照片下 "Photo: 作者 · 许可"；标志脚注"校徽来自 Wikipedia 和 Wikimedia Commons，归各大学所有，只用来标示展位。来源与授权 Sources"）；机读清单（站点上 `assets/crests/SOURCES.txt`、`assets/photos/SOURCES.txt`，TSV）；仓库级 `NOTICE`。三处都不占主页面的视觉重量。备选：只做 Credits 页；嵌入 XMP。
- **来源表按资产 ID**：`SOURCES[slug] = (文件, 描述页, 许可, 许可链接, 作者)`（原站从 MediaWiki API 取）；任何 slug 缺条目或文件缺失，都在写入前中止。原站标志许可：23 公有领域、1 CC0、25 合理使用、3 需署名。25 个是只用来标识的非自由标志，坦白说出来比假装更诚实也更稳妥。备选：画简单字标避开合理使用；向各方要新闻包标志。
- **NOTICE 七节，中文在前英文在后，重点写"哪些不在许可范围内"**：① 代码（MIT）② 第三方代码与字体（QR 库 MIT；Zilla Slab 与 Archivo 为 OFL 1.1，注明由脚本子集）③ 品牌资产（活动 logo、房号与楼层数字、统计数字）不在 MIT 内 ④ 标志 ⑤ 学生作品版权归作者 ⑥ 大学名称：不隶属、未获背书 ⑦ 照片（"缩放即为改动"）。对每类资产写清许可、改了什么、谁拥有。备选：每个文件 SPDX 头；`LICENSES/` 目录。
- **中性命名与隐私**（地板）：房间名用教室号，不写"某某班"；内容文件不写组员姓名、班级、分工；构建测试对**成品**跑正则（原站：页面不得匹配 `2[0-3]\s*班|第\s*\d+\s*组`）。

---

## 8. 文案声线 / Copy voice

| 项 | 原站取值 | 备选 |
|---|---|---|
| 句子 | 对象 + 动作 + 条件，数字精确，无感叹号、无反问、无煽动："52 个研究小组各研究一所大学，在展位上以招生官的身份介绍研究成果。" "每台手机只能投一次，提交后不能修改。" | 俏皮加表情；第二人称祈使；编辑体长导语；只有标签 |
| 温度 | 整站**一句**有温度的话，在首页：`Class of 2028, / meet your colleges.` 与 "2028届同学，欢迎来到 SDSZ College Fair。"；其余平实，这一句才有分量 | 提问式；只写日期地点；引一句学生原话 |
| 标签 | 英文 1–2 个名词 + 中文自然说法，同一概念全站一对：`Map / 导览`、`Directory / 展区名录`、`Directions / 怎么走` | 中文先行；中文放提示；语言切换 |
| 统计与位置 | `03 Floors 层楼`、`10 Rooms 个展区`：中文是补全数字的量词短语，数字补零成两位（计分牌感）；`201 展区 · 二层` / `ROOM 201 · 2F` | 不补零 |
| 错误与空态 | 原因（短）+ 动作 + 例子，不责怪用户："没有找到匹配的学校。可以试试英文缩写，例如 MIT、UCLA。" 待定：`To be announced / 展位位置将在活动前公布。` | 重试按钮；幽默 404；错误码 |
| 指令 | 动词开头，一行一个动作，带确切对象："扫码查看本校详情 / Scan for details"、"走楼梯下到 1 层。" | 图标加数字；完整句子 |

**中文排版放在构建里做**：模板为了好读而换行，会在两个汉字之间渲染出可见空格，所以构建时去掉 CJK 与 CJK 之间的空白（保护 `<pre>`、`<script>`）；数字与量词、中文与拉丁之间保留空格（"52 个研究小组"、"10 月 24 日（周六）"、"欢迎来到 SDSZ College Fair"）；中文句用全角标点。备选：CSS `text-autospace`；源文本阶段处理；`word-break: keep-all`。观察：原站写成 "2028届"（无空格），与别处不一致。

**署名政策与内容保真**：遵循项目所有者的署名声明，页面里不加"由 AI 生成"之类的标注或生成器注释，除非所有者要求。转载他人文字只删不改，逐字比对原文并列出删除；排版（卡片、表格、时间线）是编辑工作，文字归作者。备选：轻度改写并留修订痕迹；摘录加原文链接。

---

## 9. 性能预算与检查 / Performance budgets and checks

| 预算 | 原站取值 |
|---|---|
| 字体 | 76,580 B，preload 3 个里的 2 个，`swap`，immutable |
| 照片 | 156 × (大 + 小)，仓库共 34.5 MB；hero eager，其余 lazy + async |
| 第三方资源 | 无；无内联脚本（JSON 数据块可以） |
| 缓存 | 资产 `public, max-age=31536000, immutable`（10 位哈希名）；其他 3600 s；HTML `no-cache`；`encode zstd gzip` |
| 印刷 | PDF 12.0 MB；PNG 平均 356 KB；印刷徽章 640 px RGBA 共 12 MB（可改走调色板路径） |

**按角色设预算，在素材脚本里强制**：每个脚本只写自己角色的输出并打印尺寸（"52 badges, X KB in all, Y KB on average"；"共 156 张，34.5 MB"）。每次运行看到字节数，预算就不会悄悄退步。备选：CI 预算文件；Lighthouse CI；打包分析器。

**把能判定的品牌规则变成构建断言**（原站）：52 个实体色在纸上和深色模式下都 ≥ 4.5:1；字体带哈希名与 OFL 文件；反白 logo 存在且含 `#F7F5F0`；无第三方资源、无内联脚本；二维码 PNG 解码后与编码器逐模块比对；每张照片有署名；每个展位从每个起点都可到达；生产构建里没有 demo 字符串；墙上有门；链接检查；隐私正则。kit 里 `scripts/lint_floor.py` 管对比度、CJK 回退、减弱动效、焦点；命名、隐私、署名由项目自己补。备选：视觉回归截图（`specimen.py --png` 已能对每张牌截手机宽的浅 / 深 × 顶部 / 路线图，可当最小版；项目页面自己截：同一条无头 Chrome 命令 `--headless=new --virtual-time-budget=4000 --screenshot`，无头窗口最窄 500 px，要 390 px 就把页面放进 390 px 的 iframe，再加 `--force-prefers-reduced-motion` 让弹簧直接到终态，细节见 `scripts/specimen.py` 文件头）；token lint；人工 QA 清单。
