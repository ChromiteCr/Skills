---
name: photo-cinematic-grade
description: 照片电影感调色、低饱和冷暖分离、先保原片再调色。用确定性像素处理而不是生成式重绘；先确认用途与色彩输入，输出带 sRGB ICC 的新图和隐私优先的参数/QA 边车。支持 8-bit SDR JPEG/PNG 的 render、固定三选候选小样 candidates 与数值 QA；card、compare、LUT 尚未实现。不负责 RAW 显影、修图换景、冲印交付或精确复刻电影/胶片。
category: photography
version: 0.2.0
status: draft
priority: P2
compatible_agents:
  - claude-code
  - codex
  - cursor
  - codebuddy
  - nestudy
---

# Photo Cinematic Grade

把摄影者已拍下的像素调成克制的电影感，不替摄影者换掉画面。
脚本负责像素、参数和数值，摄影者决定氛围与是否接受。

## 当前能力与未完成项

当前累计完成 render 基础与候选小样两个增量，不代表整个 skill 已验收完成。

- **已实现**：`scripts/cinegrade.py render`、`looks`、`candidates`（中性基线 + 两个风格的固定三选小样）、确定性整数调色、三份基础配方、独立 `image_io.py`、数值 QA、隐私边车、原件与已有输出保护。
- **尚未实现**：`card`、`compare`、`lut` 命令，以及相应的集成测试。不得暗示它们已经可用，不能用生成图或口头描述冒充实际小样。候选固定列出而不自动排名或替摄影者选定。
- 不提供局部蒙版、人物/肤色识别、白平衡或曝光自动矫正、颗粒、暗角、锐化、降噪、裁剪。避免把调色变成无法追溯的整图修饰。

## 触发与分流

适用：“把这张照片调成电影感”“想要低饱和、暖亮部、冷暗部”“保留原片，给我一个可复现的调色版”。

- 只写图注：`photo-caption-writer`；加 EXIF 信息带：`photo-exif-frame`。
- 排多张成组：`photo-series-layout`；拼出版式跨页：`photo-spread-composer`。
- 社交尺寸、压缩、PPI、冲印 ICC 等交付准备不在本增量内。`photo-export-prep` 尚在开发队列，不能声称已可调用。
- RAW、HEIC、HDR、16-bit、CMYK、透明图、调色后输出某个打印机色域：停止，要求先由合适的色彩管理工具导出一份 **新的** 8-bit SDR sRGB JPEG/PNG。不要覆盖或强制改标签。

## 开始前：只问会改变输出的内容

1. 确认有权处理的原图、输出位置与用途，是否为需要忠实色彩的记录、产品、艺术品或新闻图片。此类图片先建议 `neutral`，不默认风格化。
2. 摄影者想要的方向，以及必须保持的颜色（肤色、衣服、品牌色等）。没有回答时先提议 `warm-muted`、强度 60，而不是当作已确认。
3. 是否已转成 SDR sRGB、有没有 ICC。**没有 ICC 就追问，不能为了让脚本跑通擅加 `--assume-srgb`。** 有 ICC 时总是实际转换，坏 ICC 必须拒绝，不允许改为“假定 sRGB”继续。

不从照片推断人的身份、真实情绪、地点或拍摄动机。处理只在本地；不得为分析或调色而上传照片。

## 运行条件

Python 3.10+、Pillow 11.3+（含 LittleCMS；已实测 Pillow 11.3.0 / LittleCMS 2.17）。
本增量不自动安装依赖或调用云端服务。运行前检查运行环境；缺依赖就说明未执行，按用户授权在合适环境补齐后再试。

只接受不超过 64 MiB、2400 万像素的单帧、8-bit、不透明 RGB/L JPEG/PNG。
这是避免内存与运行时间失控的工程上限，不是画质门槛。
拒绝 palette、alpha/tRNS、多帧、PNG 高位深及 cICP/HDR 信号，不静默降位深或丢透明层。
JPEG HDR/增益图没有全面自动识别能力，输入必须由用户确认为 SDR。

在 skill 目录下执行；路径由用户指定，不要扫描整个人的照片库：

```bash
python3 scripts/cinegrade.py --help
python3 scripts/cinegrade.py looks

# 有有效嵌入 ICC 的原图：run-warm-01 必须不存在，父目录必须已存在。
python3 scripts/cinegrade.py render source.jpg \
  --output run-warm-01 --look warm-muted --strength 60

# 仅在用户明确确认无 ICC 的输入确实是 sRGB 后：
python3 scripts/cinegrade.py render source.png \
  --output run-neutral-01 --look neutral --strength 0 --assume-srgb
```

`render` 输出目录中只有：

- `render.png`：EXIF 转正后的原分辨率、不透明 8-bit RGB、嵌入 sRGB ICC；不复制来源 EXIF、XMP、GPS、文本或缩略图。
- `report.json`：完整性收据与数值 QA，最后写入。包括输入内容 SHA-256、尺寸、原 Orientation、ICC 处理动作/散列、技术 EXIF 白名单、配方与强度、输出像素/文件散列、依赖版本。

边车白名单只有曝光秒数、f-number、ISO、焦距；缺失就省略，不补造。**不保存**原始路径、原文件名、GPS、拍摄时间、相机/镜头型号、设备序列号、作者、原始 ICC 文本或完整 EXIF。
内容散列和技术参数仍可关联原片，边车默认私用；对外分享前询问是否需要附带。
去掉元数据不等于视觉匿名，画面内的人脸、地址、车牌等仍需人工检查。

输出必须是一个全新的目录；已有文件、空目录、链接都拒绝，不提供 `--force`。
脚本先在内存中完成解码、调色、编码，再原子占用新目录。写盘失败可能留部分文件，**保留现场**，用新目录重试；不要删旧目录或改写原片。
只有命令有可靠的成功退出记录，同时 `report.json` 可解析、`status` 为 `complete` 且每个输出的 `png_sha256` 与实际文件一致才视为完成（render 检查 `output`；candidates 检查 `candidates` 中全部三项）。退出码 0 为成功，2 为输入/写盘拒绝；未通过时不能宣称已交付。

## 候选小样：先看方向，不自动选片

用户同意比较方向后，运行 `candidates`。源图的权限、SDR、ICC 与隐私要求和 `render` 完全相同；
没有 ICC 仍要先确认，不为了生成小样绕过颜色管理。忠实色彩用途仍优先中性，不默认推荐风格化。

```bash
# 有有效嵌入 ICC 的原图；run-candidates-01 必须不存在。
python3 scripts/cinegrade.py candidates source.jpg --output run-candidates-01

# 可显式改变两个风格共同的强度和预览长边；不会放大原图。
python3 scripts/cinegrade.py candidates source.jpg \
  --output run-candidates-02 --strength 40 --max-edge 768
```

固定顺序与文件名，不由图像内容或模型随机决定：

| 文件 | 配方 | 强度 |
|---|---|---|
| `01-neutral.png` | `neutral` | 永远 0，作为小样尺寸的中性基线 |
| `02-warm-muted.png` | `warm-muted` | `--strength`，默认 60 |
| `03-cool-muted.png` | `cool-muted` | 同上 |

- 一次读取输入快照，一次 EXIF 转正/ICC 归一；先缩小，再将同一份小样像素送入三份配方。
- `--max-edge` 为 1..2048 整数，默认 1024。长边不超过该值；较小图片不放大、不裁切。
  缩小时每条边按 `max(1, floor((原边长 × max_edge + floor(原长边/2)) / 原长边))` 求整，
  即最近整数、半整数向上、至少 1 像素。比例只受整像素取整影响，极细长图片可能有较明显的取整偏差。
- 缩放固定用 Pillow LANCZOS，`reducing_gap=None`，在编码 sRGB 上执行；不是线性光缩放。
  报告记录处理顺序、缩放参数与实际尺寸；未缩放时 `resampling` 为 `none`。
- `--strength` 为 0..100 整数，只作用于两个风格。设为 0 时三张小样像素相同，仍保留固定三项，不冒充三种不同效果。
- 三张 PNG 都重新嵌入 sRGB ICC，不复制来源元数据；所有图像编码完成后才占用一个全新目录。
  最后写入唯一 `report.json`：输入溯源、缩放契约、逐张完整配方/强度、文件与像素散列、依赖版本及数值 QA。
  任一写入失败，保留部分文件，不宣称完成、不补写收据、不重用目录。
- 顶层 `qa.before` 对应**缩放后、调色前**基线，各候选 `qa.after` 与越界计数只针对该小样。
  `selection.automatic_selection=false`、`selected_look=null`：脚本没有选择赢家。

**小样不是最终交付图。** 先缩后调与先全尺寸调色再缩小的像素一般不同，不能承诺两者散列相同。
小样 QA 不能证明全尺寸高光/暗部细节、肤色或色带已通过。请摄影者明确选择配方和强度，再对**原始输入**
运行 `render` 到另一个新目录并做全尺寸 QA；不要把候选 PNG 当原片再次调色，也不要直接放大小样交付。
显示环境不可用时，如实写“已生成三张候选，视觉未验收”，不代用户选定或声称好看。
本命令只输出独立 PNG 与收据，不生成拼卡、滑块对比、LUT，也不扩展到社交/冲印导出。

## 调色契约

配方在 `references/look-library.json`，选择说明见 `references/look-library.md`。

1. 对输入读一次快照；内容散列与解码使用同一批字节。
2. 应用 EXIF Orientation，绝不通过丢 EXIF 假装转正。
3. 嵌入 ICC → LittleCMS 相对色度转换到 sRGB，无隐式感知映射；无 ICC 必须显式确认 sRGB。带冲突 gamma/chromaticity 的未标记 PNG 拒绝。
4. **在编码 sRGB 值上**做整数分段曲线 → 冷暖偏移 → 饱和度 → 钳位 → 与原像素按强度混合。顺序固定，不使用随机数、生成模型、外部网络或隐式自动增强。
5. `neutral` 对归一后的像素恒等；任何配方强度 0 也恒等。注意“归一后恒等”不等于保留 JPEG 字节、宽色域源像素或 EXIF 旋转前的排列。

确定性承诺是：同一解码/ICC 环境、同一输入、配方与强度，输出像素一致。
跨 Pillow/LittleCMS 版本可能不同；PNG 文件字节不作跨运行恒等承诺（ICC/编码器可能变化）。报告记录环境及实际散列。
本变换不是线性光处理、胶片物理仿真或特定电影的精确复刻，8-bit 调色有色带风险。
具体数学与规范参考见 `references/grading-research.md`，其中工程参数与来源规则明确分开。

## QA 与交付

脚本自动报告：

- 输入与输出每个通道处在 0 / 255 的像素数；以及总像素数。
- 满强度配方在最终钳位之前超出 0..255 的通道样本数。强度 0 不执行配方，此项为 0；其他强度时这个数反映满强度配方，不是实际输出的剪切像素数。
- 明确要求人工检查的项目及数值警告。

端点数不是“已剪切”的证明，也不是“细节完好”的证明；真正的细节可能在相机或 ICC 归一时已经丢失。
数值 QA 不检测宽色域源的色域损失，不会判断肤色自然、审美成功、印刷可用或屏幕颜色准确。

交付前在能显示图像的环境中检查：肤色与记忆色、云/灯的高光细节、暗部层次、平滑渐变色带。不能查看图像时，只报告“脚本与数值已检查，视觉未验收”，不评价好看与否。
如果用户认为太强，保留当前结果，降低强度写入另一个新目录，不覆盖上一版。

简短交付单：

- 用途与用户确认的方向；配方 / 强度。
- ICC 处理动作、是否用了明确的 sRGB 假设。
- 新输出图与边车；原片未改写。
- QA 警告、实际完成的视觉检查、未验证项。

## 测试

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/cinegrade.py --selftest
PYTHONDONTWRITEBYTECODE=1 python3 scripts/image_io.py --selftest
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_cinegrade.py
```

测试只合成小图，临时文件局限本 skill 的 `scripts/` 内，结束清理自己创建的夹具；不读取真实照片、系统字体或其他技能。
交互验收场景位于仓库的 `tests/cases/photo-cinematic-grade.md`。
实测范围是合成 RGB/L、sRGB ICC 与模拟 ICC 调用；**真实 Display P3/Adobe RGB 照片与跨平台视觉验收尚未完成**。

## 后续验收顺序

以下为本 skill 尚未完成的功能；实际开发顺序以每轮同步后只读的 AUDIT-AND-IDEAS.md 时间表为准，不在本文件固定全仓项目顺序：

1. 下一增量：`card` / `compare` 与对应可视校验，复用已完成的候选参数和像素收据。
2. 再做 `lut`、LUT 与 render 数值对账、综合色彩/隐私/QA 验收。

## 变更记录

| 版本 | 日期 | 变更 | 类型 |
|---|---|---|---|
| 0.2.0 | 2026-10-07 | 新增 candidates 固定三选小样：一次颜色归一、确定性限边缩放、逐图配方/散列/QA、整组新目录保护及隐私/失败测试；card/compare/lut 仍待实现 | minor |
| 0.1.0 | 2026-10-07 | 首个独立增量：确定性 render、三份基础配方、安全 I/O、技术 EXIF 白名单边车与数值 QA；小样/card/compare/lut 待后续 | minor |

### 收据发布与文件系统边界

PNG 写完后，先将报告写为 `.report.pending`，成功 flush/fsync/close 后，以同目录硬链接、不覆盖的方式发布 `report.json`。此前任一步失败均保留现场，不发布最终收据。若文件系统不支持硬链接则安全失败，不改用会覆盖目标的发布方式。发布成功后尝试移除临时别名；此可选清理失败时可能多留 `.report.pending`，但最终收据与三图仍有效。

只在可信、不会被其他进程并发替换的输出父目录运行；这不是恶意路径替换防护，也不承诺任意断电后的目录持久性。恢复时必须同时核对成功退出、最终收据和全部输出散列，不能凭孤立的 complete 字段判定成功。
