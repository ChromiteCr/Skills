# photo-series-layout

## Case 1: 六张照片排一页网格

**输入 / Input**

用户：把这 6 张成品照片排成一页，网格布局，间距统一，输出一张长图。顺序就按我给的来。

**期望 / Expected**

- [ ] **保留用户给定顺序**，不擅自按明暗/冷暖重排
- [ ] 用 `scripts/layout_photos.py` 确定性执行：画幅归一化、间距网格一致
- [ ] 路径作为独立参数传递，不拼接未转义的 shell 字符串
- [ ] 若照片已用 `photo-exif-frame` 装裱，把装裱图当输入资产，**不再加第二层框**

**反例 / Must not**

- 不得替用户"选最佳照片"、修图或编造图注
- 不得从像素推断作品意图

## Case 2: 用户明确请求排序建议

**输入 / Input**

用户：这 9 张照片顺序我拿不准，你能给几个候选顺序吗？

**期望 / Expected**

- [ ] 给**候选**顺序（如按时间、明暗、冷暖）供人选择，最终决定权在用户
- [ ] 说明每个候选的叙事逻辑，不宣称某种顺序"客观上更好"

**反例 / Must not**

- 不得未经请求就重排

## Case 3: 裁切要先征得同意

**输入 / Input**

用户：这 6 张横竖不一，帮我排成等大的横格子，要铺满，不要留白边。

**期望 / Expected**

- [ ] 说明铺满要用 `cover`，会裁掉照片边缘的内容
- [ ] 先征得同意再渲染；不同意就用默认的 `contain`（格内留背景色条）
- [ ] 渲染后在报告里写明用了 `cover` 以及裁切提醒

**反例 / Must not**

- 不得未经同意就用 `cover`
- 不得拉伸照片来填满格子

## Case 4: 越界 —— 从像素推断情绪和故事

**输入 / Input**

用户：你看看这几张哪张情绪最强，按那天真实发生的故事给它们排个序，再配几句话。

**期望 / Expected**

- [ ] 拒绝从像素推断"情绪最强"和"当天的真实故事"，说明这些只有拍摄者知道
- [ ] 请拍摄者补充背景，或只按看得见的属性（时间、明暗、冷暖、重复形状）给不超过三个候选顺序，并标明每个候选的依据
- [ ] 配文不在本 skill 范围：单张图注转 `photo-caption-writer`

**反例 / Must not**

- 不得编造叙事或情绪弧线
- 不得替拍摄者挑出"最好的一张"

## Case 5: 输入不足 —— 没给照片路径和输出格式

**输入 / Input**

用户：帮我把上次那组照片拼一下。

**期望 / Expected**

- [ ] 追问照片路径（按展示顺序）和输出格式（PNG、JPEG 或一页 PDF）
- [ ] 其余视觉设置（布局、边距、间距、背景、fit）说明默认值，渲染前告诉使用者

**反例 / Must not**

- 不得猜路径或自行决定照片顺序
- 不得在没有输入的情况下宣称已生成文件

## Case 6: auto 排 8 张不留空格；5 张竖向长图

**输入 / Input**

夹具 `tests/fixtures/photo-series-layout/`：`s1.jpg`…`s8.jpg`，240×180，左上角白块里印着序号。在仓库根目录运行：

```bash
python3 skills/photography/photo-series-layout/scripts/layout_photos.py --output /tmp/eight.png tests/fixtures/photo-series-layout/s{1..8}.jpg
python3 skills/photography/photo-series-layout/scripts/layout_photos.py --output /tmp/long.png --layout vertical tests/fixtures/photo-series-layout/s{1..5}.jpg
```

**期望 / Expected**

- [ ] 8 张：输出行含 `4 columns x 2 rows` 和 `empty cells=0`，画布 5028×1972
- [ ] 打开图片，序号 1–8 从左到右、从上到下，与传入顺序一致
- [ ] 5 张竖向：`1 column x 5 rows`，每张各出现一次，边距与间距一致
- [ ] 向使用者汇报时同样写"4 列 × 2 行"（列在前），与脚本输出一致

**反例 / Must not**

- 不得出现 3×3 空一格（旧版 auto 查表的行为）
- 不得把"4 columns x 2 rows"说成"2×4"而不注明哪个是列

## Case 7: 校验失败 —— 超过 9 张、重复路径、覆盖已有文件

**输入 / Input**

1. 用户给了 10 张照片。
2. 用户把 `s1.jpg` 传了两次：`layout_photos.py --output /tmp/dup.png tests/fixtures/photo-series-layout/s1.jpg tests/fixtures/photo-series-layout/s1.jpg tests/fixtures/photo-series-layout/s2.jpg`
3. 输出路径已存在；或者输出路径就是其中一张输入照片，同时加了 `--overwrite`。

**期望 / Expected**

- [ ] 10 张：停下，问是删掉哪张还是拆成两页，不静默丢图
- [ ] 重复路径：脚本报错并提示 `--allow-duplicates`；Agent 先问使用者是不是有意重复，确认后才加这个开关重跑
- [ ] 输出已存在：要求使用者同意后才加 `--overwrite`
- [ ] 输出就是输入照片：即使加了 `--overwrite` 脚本也拒绝，原照片不变；换一个输出文件名
- [ ] 每种情况都不写出任何输出文件

**反例 / Must not**

- 不得未经确认就加 `--allow-duplicates` 或 `--overwrite`
- 不得覆盖任何一张输入照片

## Case 8: 色彩、方向与透明

**输入 / Input**

夹具：`p3-red.jpg`（嵌 Display P3 配置文件的饱和橙红）、`alpha.png`（透明底，中间一块红色）、`phone-portrait.jpg`（存储为 240×160、EXIF Orientation=6 的手机竖拍，存储时左上角的红块显示在右上角）。在仓库根目录运行：

```bash
python3 skills/photography/photo-series-layout/scripts/layout_photos.py --output /tmp/colour.jpg --background '#ff00ff' tests/fixtures/photo-series-layout/p3-red.jpg tests/fixtures/photo-series-layout/alpha.png tests/fixtures/photo-series-layout/phone-portrait.jpg
python3 skills/photography/photo-series-layout/scripts/layout_photos.py --output /tmp/p3only.png tests/fixtures/photo-series-layout/p3-red.jpg tests/fixtures/photo-series-layout/p3-red.jpg tests/fixtures/photo-series-layout/p3-red.jpg --allow-duplicates
```

**期望 / Expected**

- [ ] 混合配置文件：输出行写 `colour: converted to sRGB and embedded it (inputs: Display P3, untagged ...)`；P3 那一格读出来约为 (255, 0, 0)，输出嵌入 sRGB
- [ ] 全是 Display P3：`colour: kept Display P3 (all inputs) and embedded it`，像素值保持 (234, 51, 35)，白色背景仍是白色
- [ ] 透明区域是背景色 `#ff00ff`，不是黑色
- [ ] 竖拍照片是竖的，红块在右上角
- [ ] 报告里写明色彩处理方式

**反例 / Must not**

- 不得丢掉 ICC 配置文件，让 P3 照片被当成 sRGB 而发灰
- 不得把透明区域压成黑色
- 不得宣称做了色彩校样（这只是色彩空间转换）

## Case 9: HEIC 与缺少 Pillow

**输入 / Input**

1. 夹具 `iphone.heic`（iPhone 默认格式，本机没有 pillow-heif）：`layout_photos.py --output /tmp/heic.png tests/fixtures/photo-series-layout/iphone.heic tests/fixtures/photo-series-layout/s1.jpg tests/fixtures/photo-series-layout/s2.jpg`
2. 在没有安装 Pillow 的环境里渲染。

**期望 / Expected**

- [ ] HEIC：脚本退出码 2，给出 `sips -s format jpeg ".../iphone.heic" --out ".../iphone.jpg"`，没有 traceback；Agent 把命令交给使用者或在 macOS 上转一份副本后重跑
- [ ] 缺 Pillow：说明需要 `python3 -m pip install Pillow`，给出完整的运行命令

**反例 / Must not**

- 不得跳过 HEIC 照片、少一张照常出图
- 不得在没跑成功时宣称已生成文件

## Case 10: 分流 —— 刊物版面、每带署名

**输入 / Input**

用户：社团刊物要一版摄影专题，12 张照片，分几带排，每带配图注和摄影者署名，要能打印成 A3。

**期望 / Expected**

- [ ] 判断不属于本 skill：超过 9 张，而且要分带、定主次、每带署名的刊物版面
- [ ] 转用 `photo-spread-composer`
- [ ] 说明本 skill 只做 3–9 张、按原顺序的等大网格、长图或一页 PDF，不加文字

**反例 / Must not**

- 不得丢掉 3 张凑成 9 张
- 不得在本 skill 里加图注或署名
