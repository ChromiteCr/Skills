# photo-exif-frame

## Case 1: EXIF 齐全，正常渲染

**输入 / Input**

用户：给这张照片加个信息带，显示光圈、快门、ISO 和拍摄时间，深色底白字。

**期望 / Expected**

- [ ] 先 `--inspect` 读取嵌入 EXIF，再渲染；只展示报告中实际存在的字段
- [ ] 输出写入**新路径**，不覆盖源文件
- [ ] 应用 EXIF 方向后再加信息带；输出宽度等于校正后源宽，高度 = 源高 + 带高
- [ ] 色值、字段顺序、字体等样式选择先向用户确认或使用并声明 `references/layout-defaults.md` 的默认值
- [ ] 报告来源/输出路径、已渲染字段与留空字段

**反例 / Must not**

- 不得覆盖源文件（除非用户明确要求且环境安全策略允许）
- 不得声称排版选择"反映了照片的意图"

## Case 2: EXIF 缺失字段

**输入 / Input**

用户上传一张 PNG（无 EXIF），要求显示光圈、快门、曝光补偿、ISO、时间、设备全部六个字段。

**期望 / Expected**

- [ ] 缺失字段**留空**，不估算、不编造
- [ ] 明确告知哪些字段为空及原因
- [ ] 信息带仍正常渲染，布局不因空字段错位

**反例 / Must not**

- 不得接受手动元数据覆盖后伪装成相机记录值（本版本不支持 overrides）
- 不得从文件名或其他文件推断拍摄参数

## Case 3: 竖拍照片（EXIF 方向）

**输入 / Input**

夹具 `tests/fixtures/photo-exif-frame/portrait-orient6.jpg`：存储为 1200×800 横图，Orientation=6（显示为 800×1200 竖图），存储时左边缘有一条红色竖条，转正后应在顶部。

用户：给这张竖拍的照片加参数边框。

**期望 / Expected**

- [ ] `python3 skills/photography/photo-exif-frame/scripts/render_exif_frame.py tests/fixtures/photo-exif-frame/portrait-orient6.jpg --output /tmp/portrait_framed.png` 退出码 0
- [ ] 报告的 `oriented_source_dimensions` 为 `[800, 1200]`，`output_dimensions` 为 `[800, 1392]`；成品是竖图，红条在顶部
- [ ] 六个默认字段都放得下（本机 Helvetica 下值 12 px、标签 9 px）
- [ ] 源文件逐字节不变

**反例 / Must not**

- 不得输出横躺的照片，也不得按存储尺寸报告宽高

## Case 4: 输出路径等于源文件，或缺少 --output（越界请求）

**输入 / Input**

用户：直接写回原图就行，输出也叫 camera-subifd.jpg。

即执行 `render_exif_frame.py tests/fixtures/photo-exif-frame/camera-subifd.jpg --output tests/fixtures/photo-exif-frame/camera-subifd.jpg`；另外试一次不给 `--output` 也不给 `--inspect`。

**期望 / Expected**

- [ ] 第一条以退出码 2 结束，错误说明它是输入文件（`refusing to write ... it is an input file`），源文件逐字节不变
- [ ] 向用户说明脚本不会覆盖原图，改用新文件名（例如 `camera-subifd_framed.png`）
- [ ] 不给 `--output` 时退出码 2，提示 `--output is required unless --inspect is used`
- [ ] 输出路径已存在时同样拒绝，已有文件不被替换

**反例 / Must not**

- 不得先写到临时文件再替换原图来绕过拒绝

## Case 5: 字段放不下（窄图）

**输入 / Input**

先从夹具裁出 400×600 的窄图，保留 EXIF：

```bash
python3 -c "from PIL import Image; im=Image.open('tests/fixtures/photo-exif-frame/camera-subifd.jpg'); im.crop((0,0,400,600)).save('/tmp/narrow.jpg', exif=im.info['exif'])"
```

用户：这张也加上全部六个参数。

**期望 / Expected**

- [ ] 默认字段渲染以退出码 2 结束，不产生输出文件；错误列出放不下的字段（本机为 `exposure_compensation, captured, camera`）和 12 px 的可读下限
- [ ] 建议是减字段（`--fields`）或换更窄的字体（例如 Arial Narrow），并说明 `--band-ratio` 不改变格宽、调大无用；`--band-ratio 0.5` 重试仍然失败
- [ ] `--fields aperture,shutter,iso` 重试成功
- [ ] 向用户说明哪些字段没放进去，由用户决定取舍

**反例 / Must not**

- 不得裁切文字或静默丢掉字段
- 不得建议"加大 `--band-ratio`"

## Case 6: 无法解码的文件与 HEIC

**输入 / Input**

夹具 `tests/fixtures/photo-exif-frame/not-an-image.jpg`（一行文字，扩展名是 .jpg）和 `tests/fixtures/photo-exif-frame/IMG_0001.heic`（由 `camera-subifd.jpg` 经 `sips -s format heic` 转出）。当前环境没有 pillow-heif。

用户：这两张也加边框。

**期望 / Expected**

- [ ] `not-an-image.jpg` 退出码 2，错误为 `not a readable image`；不写输出，已存在的同名输出不被替换；不声称读到了任何元数据
- [ ] `IMG_0001.heic` 退出码 2，错误里给出 `sips -s format jpeg ... --out ...` 命令
- [ ] 按提示转换到临时目录（`sips -s format jpeg tests/fixtures/photo-exif-frame/IMG_0001.heic --out /tmp/IMG_0001.jpg`）后再渲染，信息带内容与 Case 1 的夹具一致

**反例 / Must not**

- 不得凭经验补 HEIC 的拍摄参数
- 不得把转换结果写进 `tests/fixtures/` 或覆盖原 HEIC

## Case 7: 真实相机分辨率，默认命令（不给 --font）

**输入 / Input**

从夹具放大出 6000×4000 横图和 4000×6000 竖图，保留 EXIF：

```bash
python3 -c "from PIL import Image; im=Image.open('tests/fixtures/photo-exif-frame/camera-subifd.jpg'); im.resize((6000,4000)).save('/tmp/big.jpg', exif=im.info['exif'], quality=85); im.resize((4000,6000)).save('/tmp/big_portrait.jpg', exif=im.info['exif'], quality=85)"
```

然后照 SKILL.md 的默认命令分别渲染：`render_exif_frame.py /tmp/big.jpg --output /tmp/big_framed.png`。

**期望 / Expected**

- [ ] 两张都退出码 0，默认六个字段全部放下
- [ ] `fonts` 是系统字体路径（macOS 为 Helvetica），不是 Pillow 内置字体；`font_size_px` 的值字号不低于 `min_readable_value_px`（横图约 92 px、竖图约 62 px，下限分别为 36、42 px），标签小于数值
- [ ] 打开成品缩到屏幕宽度看，信息带的字清楚可读，列与列之间有明显间隔
- [ ] 曝光补偿印成 `-2/3 EV`，拍摄时间是 `2026-09-20 17:42:10`

**反例 / Must not**

- 不得出现 8–10 px 的小字（旧版回退字体的表现）
- 不得在默认命令下报 `text does not fit`

## Case 8: 只有导出时间（IFD0 DateTime），没有拍摄时间

**输入 / Input**

夹具 `tests/fixtures/photo-exif-frame/export-datetime-only.jpg`：只有 IFD0 的 Make=Canon、Model=Canon EOS R6、DateTime=2026:09:24 21:05:00，没有 DateTimeOriginal，也没有曝光参数。

用户：加信息带，要有拍摄时间。

**期望 / Expected**

- [ ] `--inspect` 与渲染报告里 `captured` 为空，`blank_fields` 包含 `captured`，`warnings` 说明 IFD0 DateTime 是修改或导出时间、不是拍摄时间
- [ ] `camera` 为 `Canon EOS R6`，厂商不重复
- [ ] 向用户说明拍摄时间缺失的原因；本版本不接受手填时间

**反例 / Must not**

- 不得把 `2026-09-24 21:05:00` 印在 CAPTURED 下面

## Case 9: Display P3 照片与透明 PNG

**输入 / Input**

夹具 `tests/fixtures/photo-exif-frame/p3-orange.jpg`（嵌入 Display P3 配置文件，左半是 P3 下的高饱和橙 (255,100,0)，右半中性灰）和 `tests/fixtures/photo-exif-frame/transparent.png`（透明底，中间一块不透明红色，无 EXIF）。

用户：这两张各加一条默认信息带。

**期望 / Expected**

- [ ] P3 图的报告里 `color_space` 与 `output_color_space` 都是 `Display P3`，`color_policy` 为 `keep`
- [ ] 用下面的命令核对成品：配置文件名是 `Display P3`，橙色像素仍是 `(255, 100, 0)`，没有被当成 sRGB 而发灰

  ```bash
  python3 -c "from PIL import Image, ImageCms; import io; im=Image.open('/tmp/p3_framed.png'); print(ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(im.info['icc_profile']))).strip(), im.getpixel((100,100)))"
  ```

- [ ] 透明 PNG 的透明区在成品里是信息带颜色 `#F3F0E8`（左上角像素 (243, 240, 232)），不是黑色；`warnings` 提到透明区已合成到信息带颜色上；六个字段全部留空并说明没有 EXIF

**反例 / Must not**

- 不得丢掉源配置文件或把 P3 数值原样写成 sRGB
- 不得把透明区压成黑块
