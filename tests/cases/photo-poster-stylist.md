# photo-poster-stylist

## Case 1: 描述充分，产出海报

**输入 / Input**

用户：把这张照片做成极简海报。照片是我拍的一座红色灯塔，背景是纯蓝天，灯塔在画面右侧三分之一处。我想要几何化处理。

**期望 / Expected**

- [ ] 视觉抽象（主体轮廓、主色板、明暗结构）**显式写出**，由人确认后再渲染
- [ ] 色板克制（最多三色），几何化、留白优先；元素数量有上限强制极简
- [ ] 用 `scripts/poster_tool.py render` 生成 SVG，再用 `validate` 子命令做确定性校验
- [ ] 网格、字重层级、出血遵循 `references/layout-rules.md`
- [ ] 排版与抽象是否"还像原图"由用户判断，不自行宣布成功

**反例 / Must not**

- 不得推断拍摄者未提供的意图、象征或地点
- 不得做写实矢量描摹或修图式复刻

## Case 2: 缺描述时先问

**输入 / Input**

用户：把这张照片做成海报。（只给图，没有任何描述）

**期望 / Expected**

- [ ] 先向拍摄者收集对照片的描述与想要的抽象方向，不直接从像素脑补主题
- [ ] 说明需要哪些决策（主体取舍、色板、文字内容），只问会改变输出的问题
- [ ] 若当前环境看不到图片（例如用户只说"把我那张夜景做成艺术海报"），直说看不到，并索要主体轮廓、主要明暗块、必须保留的一个细节、尺寸和文字

**反例 / Must not**

- 不得编造"照片想表达的情感"或替拍摄者决定主体
- 不得凭"夜景"二字脑补霓虹色、地点、情绪或故事

## Case 3: 色板要求自相矛盾

**输入 / Input**

用户：这五个颜色都必须用上：深蓝、橙、米白、墨绿、灰。另外海报要严格三色。

**期望 / Expected**

- [ ] 指出两条要求互相矛盾：五种必用色与三色上限不能同时满足
- [ ] 问哪条优先；或者给两套明确分开的三色方向，各自说明取舍
- [ ] 使用者选定之前不渲染

**反例 / Must not**

- 不得悄悄丢掉其中两种颜色
- 不得为了塞进五色而绕过 `poster_tool.py` 的调色板检查

## Case 4: 越界 —— 精修人像、还原五官

**输入 / Input**

用户：把这张人像精修一下，磨皮美白，五官要还原得一模一样，再做成海报。

**期望 / Expected**

- [ ] 说明本 skill 只做极简几何的再诠释，不做修图、合成或写实描摹
- [ ] 说明本库没有修图 skill；精修要用修图软件另做
- [ ] 愿意的话，可以提议基于这张照片做一张几何抽象海报，但要说清人脸不会被逼真还原

**反例 / Must not**

- 不得宣称极简海报流程能保留五官细节
- 不得把人脸画成细致的矢量描摹

## Case 5: 校验失败 —— 第四种颜色、越界形状、前景色等于背景色

**输入 / Input**

夹具 `tests/fixtures/photo-poster-stylist/invalid.json`：前景色与背景色相同，一个形状用了调色板外的 `#2255AA`，且从 x=900 画到 1300，超出 1080 宽的画布。在仓库根目录运行：

```bash
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py render tests/fixtures/photo-poster-stylist/invalid.json /tmp/invalid.svg
```

**期望 / Expected**

- [ ] render 以退出码 1 报 `shapes[0].fill introduces a color outside the declared palette`，不写出 SVG
- [ ] Agent 改规格（把颜色换成调色板里的角色）后重新 render，再 validate：报 `rect extends outside the canvas` 和 `text contrast 1.00:1 is below 3.0:1`，退出码 1
- [ ] 三类问题都修好、validate 通过之后才说完成

**反例 / Must not**

- 不得手改 SVG 绕过校验而不说明理由
- 不得在校验失败时宣称海报已完成

## Case 6: 出血 —— 满出血色块通过，越过出血边报错

**输入 / Input**

印刷海报，成品 1080×1350，出血 36。在仓库根目录运行：

```bash
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py render tests/fixtures/photo-poster-stylist/bleed-ok.json /tmp/bleed-ok.svg
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py validate /tmp/bleed-ok.svg
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py render tests/fixtures/photo-poster-stylist/bleed-out.json /tmp/bleed-out.svg
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py validate /tmp/bleed-out.svg
```

`bleed-ok.json` 的色带从 (-36, -36) 起、宽 1152，铺满上、左、右三边的出血；`bleed-out.json` 有一块从 x=1100 画到 1150 的色块，超出右侧出血边 1116。

**期望 / Expected**

- [ ] `bleed-ok.svg`：`PASS`，铺进出血区的色带不算越界
- [ ] `bleed-out.svg`：`ERROR: rect extends outside the canvas past the right bleed edge`，退出码 1
- [ ] Agent 把越界的色块收回出血边以内，或按设计意图延伸到正好 1116

**反例 / Must not**

- 不得为了过校验把铺满出血的色带缩回成品尺寸以内
- 不得把越过出血边的形状当作通过

## Case 7: path 越界与超长中文标题

**输入 / Input**

夹具 `tests/fixtures/photo-poster-stylist/path-and-title.json`：一条画在 (5000, 5000)–(6000, 6000) 的 path，和一个 26 个汉字的标题（1080 宽的海报上字号 64.8）。在仓库根目录运行：

```bash
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py render tests/fixtures/photo-poster-stylist/path-and-title.json /tmp/path-title.svg
python3 skills/photography/photo-poster-stylist/scripts/poster_tool.py validate /tmp/path-title.svg
```

**期望 / Expected**

- [ ] 报 `path extends outside the canvas`
- [ ] 报标题估算宽度约 81..1766、越过右侧成品边（trim），建议缩短文案或减小字号
- [ ] 退出码 1；Agent 与拍摄者商量缩短标题，而不是自行删字

**反例 / Must not**

- 不得因为 path 或文字"没有 x/width 属性"就放过边界检查
- 不得自行改写使用者提供的标题文字

## Case 8: 分流 —— 多张照片

**输入 / Input**

用户：这 6 张照片帮我做成一张海报，排在一起。

**期望 / Expected**

- [ ] 说明本 skill 一次只把一张照片抽象成几何海报
- [ ] 按需求分流：3–9 张按原顺序拼成一页、长图或 PDF → `photo-series-layout`；要刊物式分带、每带署名的版面 → `photo-spread-composer`
- [ ] 若使用者其实想要从其中一张做几何海报，先确认是哪一张

**反例 / Must not**

- 不得把 6 张照片硬塞进一张几何海报
- 不得指向不存在的"排版工作流"而不点名具体 skill
