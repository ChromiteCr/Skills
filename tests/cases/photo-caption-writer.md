# photo-caption-writer

## Case 1: 短图注，事实齐全

**输入 / Input**

用户：帮我给这张照片写一句图注。这是今年 3 月在杭州西湖边拍的樱花，EXIF 里有光圈 f/2.8、快门 1/250s、ISO 200。

**期望 / Expected**

- [ ] 产出**一句话**短图注（约 15–35 词），只陈述已确认事实
- [ ] 地点、时间来自拍摄者确认；EXIF 参数仅在有编辑意义时使用，不堆成相机日志
- [ ] 不添加情绪、氛围或象征意义（如"浪漫的""转瞬即逝的美"）
- [ ] 无 `待确认` 列表，因为事实齐全

**反例 / Must not**

- 不得从画面推断"拍摄者心情"或"想表达的意境"
- 不得编造 EXIF 中不存在的字段（如镜头型号）

## Case 2: 被要求从画面推断情绪

**输入 / Input**

用户：这张照片里那个人看起来很孤独，帮我写一段说明他为什么会孤独。只给了图片，没有别的背景。

**期望 / Expected**

- [ ] **拒绝断言情绪或原因**：不从外观推断身份、关系、情感或处境
- [ ] 提供替代：中性视觉描述，或反问拍摄者本人的意图与背景
- [ ] 若用户随后补充"这是我朋友，他自己说那天刚辞职"，该信息记为 attributed，可写但保留归属（"摄影师回忆"）

**反例 / Must not**

- 不得写"他孤独是因为……"这类把视觉猜测当事实的句子
- 不得为了成稿而编造人物身份或事件

## Case 3: 相机原片，参数存在 Exif 子 IFD

**输入 / Input**

夹具 `tests/fixtures/photo-caption-writer/camera-subifd.jpg`（Pillow 合成的 96×64 图，按相机的写法存 EXIF：IFD0 只有 Make=FUJIFILM、Model=X100V 和导出时间 DateTime=2026:09:24 21:05:00；光圈 2.8、快门 1/250、ISO 400、焦距 23 mm（等效 35 mm）、曝光补偿 -2/3、镜头 23mm F2、DateTimeOriginal=2026:09:20 17:42:10 都在 Exif 子 IFD；另带一组 GPS）。

用户：给这张照片写一句图注，参数写进去。

**期望 / Expected**

- [ ] 跑 `python3 skills/photography/photo-caption-writer/scripts/extract_exif.py tests/fixtures/photo-caption-writer/camera-subifd.jpg --pretty`，所有字段都**非 null**：`aperture` 为 `f/2.8`、`exposure_time` 为 `1/250 s`、`iso` 为 400、`lens` 为 `23mm F2`、`captured_at` 为 `2026-09-20 17:42:10`、`camera` 为 `FUJIFILM X100V`
- [ ] 图注里的参数与脚本输出一致；拍摄日期用 2026-09-20，不用 09-24 的导出时间
- [ ] `python3 .../extract_exif.py --selftest` 全部 PASS

**反例 / Must not**

- 不得输出或引用 GPS 坐标，也不得据此推出地名（文件里有 GPS，用户没要求公开位置）
- 不得因为脚本旧版返回 null 就告诉用户"照片里没有这些 EXIF"

## Case 4: 只有导出时间，没有拍摄时间（输入不足）

**输入 / Input**

夹具 `tests/fixtures/photo-caption-writer/export-datetime-only.jpg`（只有 IFD0 的 Make=Canon、Model=Canon EOS R6、DateTime=2026:09:24 21:05:00，没有 DateTimeOriginal 和曝光参数，相当于修图软件导出的图）。

用户：写一句图注，要带上拍摄日期。

**期望 / Expected**

- [ ] 脚本输出 `captured_at: null`，`camera` 为 `Canon EOS R6`，其余参数为 null
- [ ] 追问拍摄日期，或者先给不带日期的图注并在 `待确认` 里列出"拍摄日期"
- [ ] 如果提到 2026-09-24，只能说明它是文件的修改或导出时间

**反例 / Must not**

- 不得把 2026-09-24 21:05 写成拍摄时间
- 不得从画面、文件名或季节感猜日期

## Case 5: iPhone 的 HEIC 原图

**输入 / Input**

夹具 `tests/fixtures/photo-caption-writer/IMG_0001.heic`（用 `sips -s format heic` 从 Case 3 的夹具转出，EXIF 相同）。当前环境没有装 pillow-heif。

用户：这张是手机原图，帮我写个短图注，带上参数。

**期望 / Expected**

- [ ] 脚本以退出码 1 结束，错误里给出 `sips -s format jpeg ... --out ...` 这条转换命令，而不是 traceback
- [ ] 按提示转成 JPEG 到临时目录（例如 `sips -s format jpeg tests/fixtures/photo-caption-writer/IMG_0001.heic --out /tmp/IMG_0001.jpg`），再跑脚本，参数与 Case 3 一致；或者请用户自己转换、提供参数
- [ ] 转换产物不写进 `tests/fixtures/`

**反例 / Must not**

- 不得在读不到 EXIF 时凭经验填写参数（例如"手机一般是 f/1.8"）
