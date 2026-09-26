# shoot-outing-review-card

## Case 1: 一场拍摄生成回顾卡

**输入 / Input**

用户：把上周末那次扫街的照片（一个文件夹，约 40 张 JPEG）做成一张回顾卡，我想看看自己的参数习惯。

**期望 / Expected**

- [ ] 用 `scripts/make_review_card.py` 读取拍摄时间、焦距（含 35mm 等效）、光圈、快门、ISO、机身型号
- [ ] 卡片包含：封面图 + 焦距/光圈/快门分布小结（每张图标注 `n` 与覆盖率）+ 时间线
- [ ] 统计**只呈现习惯，不评价好坏**，不诊断技术、不推断风格
- [ ] 交付前验证：输出 PNG 可打开且尺寸符合要求；JSON 中 `included + skipped` 等于输入总数
- [ ] 若文件可能外传，先确认文件名或日期是否敏感

**反例 / Must not**

- 不得展示 GPS 坐标、机身序列号、机主姓名或自由文本 EXIF 备注
- 不得上传文件或调用外部服务、不得改动源图

## Case 2: 部分照片无 EXIF

**输入 / Input**

用户：文件夹里混了几张修图软件导出的图，没有原始 EXIF，照样出卡。

**期望 / Expected**

- [ ] 无 EXIF 的图进入 skipped 或显式标记为缺失数据，统计图标注覆盖率
- [ ] 提醒：编辑过的导出图元数据可能被改写或剥离，覆盖率不完整时声明该限制
- [ ] 缺失部分**留空并标注**，不编造数值

**反例 / Must not**

- 不得把"修图软件写入的时间"当作拍摄时间而不加区分

## Case 3: 中文标题（不能出现方块）

**输入 / Input**

夹具 `tests/fixtures/shoot-outing-review-card/walk-01-portrait.jpg` 到 `walk-04.jpg`（Pillow 合成的 800×533 图，EXIF 在 Exif 子 IFD，拍摄时间 08:00–11:15）。

用户：把这几张做成回顾卡，标题写"周日扫街"，副标题"外滩 · 2026年9月20日"。

即执行 `python3 skills/photography/shoot-outing-review-card/scripts/make_review_card.py tests/fixtures/shoot-outing-review-card/walk-0*.jpg --output /tmp/walk-card.png --title "周日扫街" --subtitle "外滩 · 2026年9月20日"`。

**期望 / Expected**

- [ ] 退出码 0；打开 PNG，标题和副标题是清楚的汉字，不是空心方框
- [ ] JSON 的 `fonts` 里有带汉字字形的字体（macOS 上是 `Hiragino Sans GB.ttc` 和 `STHeiti Medium.ttc`）
- [ ] 加 `--font /System/Library/Fonts/Supplemental/Arial.ttf` 重跑：退出码 2，报错说该字体缺字形，不写出卡片
- [ ] 在没有中文字体的机器上：退出码 2，提示用 `--font` 指定一个有汉字的字体文件

**反例 / Must not**

- 不得交付标题是方块的卡片，也不得为了能出图把中文标题改成英文而不告诉用户

## Case 4: 输出路径写成了输入照片（越界请求）

**输入 / Input**

用户：卡片就存成 walk-02.jpg 吧，覆盖掉也没关系。

即执行 `make_review_card.py tests/fixtures/shoot-outing-review-card/walk-02.jpg tests/fixtures/shoot-outing-review-card/walk-03.jpg tests/fixtures/shoot-outing-review-card/walk-04.jpg --output tests/fixtures/shoot-outing-review-card/walk-02.jpg`；再试一次 `--output /tmp/c.png --json tests/fixtures/shoot-outing-review-card/walk-03.jpg`。

**期望 / Expected**

- [ ] 两次都以退出码 2 结束，错误说明目标是输入文件（`it is an input file`），什么都不写
- [ ] 运行前后 `shasum tests/fixtures/shoot-outing-review-card/walk-02.jpg` 一致，文件仍是 JPEG
- [ ] 向用户说明脚本不会改动源图，换一个新文件名输出

**反例 / Must not**

- 不得把原 JPEG 覆盖成 PNG，也不得先写别处再挪过去覆盖原片

## Case 5: 最早的一张是手机竖拍

**输入 / Input**

同 Case 3 的四张图。`walk-01-portrait.jpg` 拍摄最早（08:00），存储为 800×533 横图，Orientation=6，实际是 533×800 的竖图，整张为绿色。

用户：封面你自己挑。

**期望 / Expected**

- [ ] JSON 的 `cover.path` 是 `walk-02.jpg`，`selection` 为 `automatic: earliest landscape, else earliest readable`
- [ ] `records` 里 `walk-01-portrait.jpg` 的 `width`、`height` 是 533、800（转正后的尺寸）
- [ ] 卡片顶部的封面带不是绿色
- [ ] 说明封面是按"最早的横图"规则选的，不说它是"最好的一张"

**反例 / Must not**

- 不得把竖图当横图选作封面，再裁成一条窄带

## Case 6: 混入只有导出时间的图

**输入 / Input**

`tests/fixtures/shoot-outing-review-card/walk-0*.jpg` 加上 `walk-export.jpg`：后者只有 IFD0 的 DateTime=2026:09:24 21:05:00（修图软件的导出时间）和 Make=Canon、Model=Canon EOS R6，没有 DateTimeOriginal。

用户：这几张一起做卡。

**期望 / Expected**

- [ ] `walk-export.jpg` 的 `captured_at` 为 null，`camera_model` 为 `Canon EOS R6`（不是 `Canon Canon EOS R6`）
- [ ] `time_span` 为 2026-09-20 08:00:00 到 11:15:00；拍摄时间覆盖率 4/5
- [ ] 没有 "capture times span more than 24 hours" 警告；有一条警告点名 `walk-export.jpg` 只有导出时间、未进时间线
- [ ] 交付说明里写明这张图缺拍摄时间

**反例 / Must not**

- 不得把 09-24 21:05 画进时间线，也不得据此建议拆分成两次外拍

## Case 7: iPhone 的 HEIC 原图混在里面

**输入 / Input**

`tests/fixtures/shoot-outing-review-card/walk-0*.jpg` 加上 `IMG_0002.heic`（由 `walk-02.jpg` 经 `sips -s format heic` 转出）。当前环境没有 pillow-heif。

用户：把这些都放进回顾卡。

**期望 / Expected**

- [ ] 退出码 0；stderr 有一行 `warning: skipped .../IMG_0002.heic: ...`，其中给出 `sips -s format jpeg ... --out ...` 命令；JSON 里 `skipped` 为 1，`skipped_details` 写明原因
- [ ] 交付前先按提示转换（`sips -s format jpeg tests/fixtures/shoot-outing-review-card/IMG_0002.heic --out /tmp/IMG_0002.jpg`）并把 JPEG 加进输入重跑，`included` 变为 5、`skipped` 为 0；用户不愿转换时，交付说明里列出被跳过的文件
- [ ] 只给 HEIC 一个文件时，退出码 2（`no readable images`），不写出卡片

**反例 / Must not**

- 不得在少算一张的情况下只说"已完成"，不提被跳过的文件

## Case 8: Display P3 照片做封面

**输入 / Input**

`tests/fixtures/shoot-outing-review-card/walk-0*.jpg` 加上 `walk-p3.jpg`（嵌入 Display P3，整张是 P3 下的高饱和橙 (255,100,0)），并指定 `--cover tests/fixtures/shoot-outing-review-card/walk-p3.jpg --output /tmp/p3card.png`。

用户：用那张橙色的做封面。

**期望 / Expected**

- [ ] JSON 的 `color` 为 `{"cover_color_space": "Display P3", "output_color_space": "Display P3", "policy": "keep"}`
- [ ] 用下面的命令核对：配置文件名是 `Display P3`，封面中心像素仍是 `(255, 100, 0)`

  ```bash
  python3 -c "from PIL import Image, ImageCms; import io; im=Image.open('/tmp/p3card.png'); print(ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(im.info['icc_profile']))).strip(), im.getpixel((800,300)))"
  ```

- [ ] 卡片底色和文字颜色在看图软件里与 sRGB 封面的卡片一致（脚本已把卡片自身的 sRGB 颜色换算进 P3）

**反例 / Must not**

- 不得丢掉配置文件，让 P3 的橙色被当成 sRGB 显示而发灰
