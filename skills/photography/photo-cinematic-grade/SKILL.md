---
name: photo-cinematic-grade
description: 照片电影感调色、低饱和冷暖分离、先保原片再调色。用确定性像素处理而不是生成式重绘；先确认用途与色彩输入，输出带 sRGB ICC 的新图和隐私优先的参数/QA 边车。当前首个增量仅支持 8-bit SDR JPEG/PNG 的 render 与数值 QA；候选小样、card、compare、LUT 尚未实现。不负责 RAW 显影、修图换景、冲印交付或精确复刻电影/胶片。
category: photography
version: 0.1.0
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

这是队列 A 的第一个可独立验证增量，不代表整个 skill 已验收完成。

- **已实现**：`scripts/cinegrade.py render`、`looks`、确定性整数调色、三份基础配方、独立 `image_io.py`、数值 QA、隐私边车、原件与已有输出保护。
- **尚未实现**：自动候选小样、`card`、`compare`、`lut` 命令，以及相应的集成测试。不得暗示它们已经可用，不能用生成图或口头描述冒充实际小样。
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

输出目录中只有：

- `render.png`：EXIF 转正后的原分辨率、不透明 8-bit RGB、嵌入 sRGB ICC；不复制来源 EXIF、XMP、GPS、文本或缩略图。
- `report.json`：完整性收据与数值 QA，最后写入。包括输入内容 SHA-256、尺寸、原 Orientation、ICC 处理动作/散列、技术 EXIF 白名单、配方与强度、输出像素/文件散列、依赖版本。

边车白名单只有曝光秒数、f-number、ISO、焦距；缺失就省略，不补造。**不保存**原始路径、原文件名、GPS、拍摄时间、相机/镜头型号、设备序列号、作者、原始 ICC 文本或完整 EXIF。
内容散列和技术参数仍可关联原片，边车默认私用；对外分享前询问是否需要附带。
去掉元数据不等于视觉匿名，画面内的人脸、地址、车牌等仍需人工检查。

输出必须是一个全新的目录；已有文件、空目录、链接都拒绝，不提供 `--force`。
脚本先在内存中完成解码、调色、编码，再原子占用新目录。写盘失败可能留部分文件，**保留现场**，用新目录重试；不要删旧目录或改写原片。
只有 `report.json` 可解析、`status` 为 `complete` 且 `png_sha256` 与实际文件一致才视为完成。退出码 0 为成功，2 为输入/写盘拒绝；未通过时不能宣称已交付。

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

本增量提交后继续队列 A，不进入 B：

1. 下一增量：确定性候选小样（中性基线 + 两个风格、固定参数与新目录、缩放与元数据测试）。
2. 再做 `card` / `compare` 与对应可视校验。
3. 再做 `lut`、LUT 与 render 数值对账、综合色彩/隐私/QA 验收。

## 变更记录

| 版本 | 日期 | 变更 | 类型 |
|---|---|---|---|
| 0.1.0 | 2026-10-07 | 首个独立增量：确定性 render、三份基础配方、安全 I/O、技术 EXIF 白名单边车与数值 QA；小样/card/compare/lut 待后续 | minor |
