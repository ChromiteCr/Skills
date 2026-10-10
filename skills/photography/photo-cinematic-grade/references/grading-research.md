# Grading research — 实现依据与证据边界

## 本版依据

本文件是 render、候选小样与前后对比的工程说明，不声称已完成电影样片研究或实测胶片建模。
下列是规范/库文档参考入口；**本批次没有联网读取或复核这些页面**，没有把未访问的页面当作实测证据：

- ICC profile 规范与色彩管理资料：https://www.color.org/icc_specs2.xalter
- Pillow ImageCms API：https://pillow.readthedocs.io/en/stable/reference/ImageCms.html
- Pillow ImageOps EXIF transpose：https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose
- PNG 规范与色彩/元数据块：https://www.w3.org/TR/png-3/

**本地实测证据**：Pillow 11.3.0 / LittleCMS 2.17 的合成夹具，通过该 skill 的 `scripts/test_cinegrade.py` 重跑。
真实 Display P3/Adobe RGB 资料、不同平台解码差异、校色显示器视觉检查不在此证据范围，交付时不能写“已验证”。

## 色彩管理决策

1. 显示参照 SDR 输入先归一到 sRGB，再做创意变换；不在未识别的色彩空间上直接套数值。
2. 有 ICC：LittleCMS 相对色度意图，RGB 输出，flags=0。这个选择不是“无损宽色域转换”；超出目标色域的颜色可能被裁切，当前 QA 看不到转换前的色域损失。
3. 无 ICC：要求用户明确确认 sRGB。PNG gamma 与 sRGB 冲突或只有非明确 sRGB 色度声明时拒绝，不私自从几项数字拼 ICC。
4. 拒绝可检测到的 cICP/HDR PNG 信号；没有全面的 JPEG HDR/增益图识别。调用前确认 SDR；8-bit 不能当成充分证明。
5. ICC 转换/解码失败不降级；HDR、RAW、HEIC、高位深和打印交付需要专门流程，不靠改扩展名或重新贴 sRGB 标签解决。

## 确定性像素契约：encoded-srgb-integer-v1

以下是创意参数设计，并非来自 ICC 或 PNG 规范的推荐调色值。
所有处理作用于 EXIF 转正并归一后的 RGB8 像素；对每个像素独立，无随机性。

定义 `R(n,d) = floor((n + floor(d/2))/d)`，d 为正整数。
它是最近整数舍入，恰好半整数时向正无穷方向，包括负数；避免宿主浮点舍入差异。

1. **曲线**：对相邻点 `(x0,y0)` 与 `(x1,y1)`，`t(x)=y0 + R((x-x0)*(y1-y0), x1-x0)`。提前生成 256 项查表。
2. **冷暖偏移**：各通道 `u=t + R(shadow*(255-t)+highlight*t, 255)`，三通道各有自己的偏移。
3. **去/增饱和**：`Y=R(54*r+183*g+19*b,256)`；`v=Y+R((u-Y)*saturation_percent,100)`。
   这里的权重只是编码 sRGB 上的亮度近似，不是线性光亮度，也不承诺保持知觉亮度或色相。
4. **范围处理**：记录 v<0 或 v>255 的通道样本数，再钳位到 0..255。
5. **强度混合**：`out=R(original*(100-strength)+bounded*strength,100)`。
   strength=0 直接返回原像素，既不计算满强度变换，也不制造无效警告。

`neutral` 的曲线恒等、偏移 0、饱和度 100，对任意强度都是恒等；这是数值回归的锚。
手算夹具覆盖纯色、灰阶、曲线节点、负数舍入和一半强度，不能只用实现自身生成“期望值”。

## 候选小样的缩放证据边界（0.2.0）

候选使用同一份已转正、已归一的输入，先以整数比例求尺寸，再用 Pillow LANCZOS 缩放，
`reducing_gap=None`，最后执行上面的整数调色。默认长边 1024、上限 2048 是控制预览成本的工程选择，
不是印刷、画质或观看距离标准；不放大、不裁剪。短边最近整数取整，半整数向上且至少为 1。
缩放仍在编码 sRGB 上，不声称线性光重采样；解码/ICC/缩放版本都影响跨环境复现。

测试用手列尺寸（含半整数、极端长宽比与不放大）、纯色不变量、EXIF 像素位置、真实 sRGB ICC、
模拟 ICC 转换调用次序，以及“对独立缩小图执行 render”的数值对账核验流程。
非线性反例同时确认先缩后调不等同于先调后缩；不把后者当作候选的像素真值。
三份小样的数值 QA 只作用于预览，不能担保全尺寸细节与色带，也没有新增真实广色域或视觉验收证据。

## 非目标与风险

- 不是胶片特性曲线拟合、ACES、场景线性成像、自动白平衡或曝光修复。
- 8-bit 再调色可能产生条带。保留原片，不建议把输出反复作为输入继续叠加。
- 曲线提黑或收高光不能恢复已丢失的细节；端点下降不等于画质更好。
- 数值独立性不等于文件字节不变：解码器、ICC 库、生成的 ICC 与编码器版本均记录并解释。比对像素散列，不误用 PNG 文件散列作跨版本一致性证明。
- metadata 清除不是视觉脱敏，内容散列也不是匿名化。输出不带原始 ICC 文本，不传播其可能的设备信息。

## 后续验收必须补的证据

依队列 A 分增量补齐，不以此文档替代实现：card 的参数与像素对账、LUT 网格与 render 误差界、真实广色域输入的色彩管理核验、人工视觉确认。


## compare 的验证边界（0.3.0）

实现依据是只读计划 3.2、3.7 的前后对比输出要求。历史 0.4.1 原型在本 skill 当前文件和路径历史中未找到，
本版复用现有 load_image / grade_pixels / encode_png / write_new_bundle，重新实现左右并排。
不新增调色系数、不修改三份原有工程配方，不把它们当成计划规定的六个风格。

两幅直接相邻，单幅保持原尺寸；2W 来自两幅宽度相加，不是新的视觉配方。
验证以手算黑白灰、合成彩色像素、八种 EXIF 转正位置、独立 render 的输出逐像素对账为依据。
QA 只数一幅 before 和一幅 after，未把并排图面积当成每幅照片的面积。
本轮所有新夹具都是明确标注的合成测试输入，未得到真实摄影效果确认；没有读取个人照片或下载材料。

真实 P3、人像、夜景、天空渐变仍需独立验收。当前 compare 尚未复现历史原型的装饰、中文排版或 8 分视觉评价。


## 浮点色彩内核（0.4.0，重新实现）

本轮推进只读计划 3.4 中浮点线性光、Oklab 亮度曲线与 OkLCh 运算的核心实现。
当前 skill 文件与该路径本地 Git 历史只有现有整数实现，未找到历史 0.4.1 原型。
`color_core.py` 从标准色彩数学重新实现，不声称移植原型、复现 55 项自检或原型照片评分。
本模块尚未接入 CLI render，整数渲染器的配方、像素与安全读写契约保持不变。

### 数值来源与精度

- sRGB 传递函数使用标准阈值 0.04045、0.0031308，线性段 12.92，指数 2.4，以及 0.055/1.055。
  负坐标采用保留符号的扩展，便于后续统计色域外值；不截成 0。
  可核对来源为 CSS Color 4 的 Sample code for color conversions，
  https://www.w3.org/TR/css-color-4/#color-conversion-code 。
- 线性 sRGB 到 Oklab 使用 Björn Ottosson 于 2021-01-25 更新的两组矩阵，
  https://bottosson.github.io/posts/oklab/ 。代码逐项列出发表的十位小数系数。
  它们是标准颜色空间变换系数，不是拟造的创意配方。逆矩阵由同一组前向矩阵计算，
  避免另外一组舍入后的逆矩阵引入不必要的往返偏差。LMS 用实数立方根，允许负值。
- 这些是供核对的公开来源，本轮未联网重新读取页面。测试的 RGB 原色向量保留八位小数，
  绝对容差 5e-8 用于覆盖参考向量末位舍入。网格往返容差验证的是数值实现，不是摄影色差护栏。
- 所有公开函数返回 float64，不改写输入；输入须为非空、有限的实数。
  色彩坐标最后一轴为 3，传递函数与亮度曲线也支持标量与任意形状。
  RGB 必须先归一到 0..1，函数不会把 255 猜成一个 8-bit 码值。扩展坐标可超出此范围。
  Oklab/OkLCh 转换不钳位 L，亮度曲线单独要求 L 在 0..1。
- OkLCh 用 C=hypot(a,b)，h=atan2(b,a)，角度归一到 [0,360)。恰好 C=0 时记录 h=0；
  近中性仍保留实际坐标，没有虚构肤色键或色度阈值。输入 C<0 拒绝。

### 端点固定亮度曲线

计划给出了部分风格的 contrast 参数，并未规定曲线公式。本轮选择以下可解析验证的工程实现：

`S_c(L) = L^c / (L^c + (1-L)^c)`，c>0；强度混合为 `(1-s)L + s*S_c(L)`，s∈[0,1]。

两端固定在 0 和 1，中点固定在 0.5，中点导数为 c；c=1 恒等，c>1 加反差，0<c<1 降反差。
实现用 log-odds 与稳定 sigmoid，避免直接计算幂导致分子、分母同时下溢。
contrast 与 strength 必须显式传入，没有新增默认配方系数；strength=0 或 contrast=1 返回精确副本。
`contrast_oklab` 只改 L，a/b 不变，后续还须实现计划中的高光色度滚降、肤色保护与色域映射。
不会暗中钳位或量化来伪造可显示结果。

这是重新设计的公式，尚未经 Bill 对真实摄影效果确认，不作为已经批准的六风格配方。
测试使用计划的 1.25、1.02、0.82 检查单调性、端点与方向；contrast=2 只用于手算
S(0.25)=0.1、S(0.75)=0.9 的合成数学例子，不能把它当推荐调色参数。
标准 D65、显示参照 SDR 的线性化也不等于场景辐射恢复、RAW 显影或 HDR 管线。

### 最小 API 串接示例

下面仅说明数据路径，不运行、保存或验收真实照片。`normalized_rgb8` 必须来自既有
`load_image` 完成 EXIF 转正与 ICC 归一后的 RGB8，不能绕过颜色输入确认。
`confirmed_contrast` 和 `confirmed_strength` 由调用者明确传入，不在示例里编造默认值。

```python
encoded = np.asarray(normalized_rgb8, dtype=np.float64) / 255
linear = color_core.srgb_to_linear(encoded)
lab = color_core.linear_srgb_to_oklab(linear)
lab = color_core.contrast_oklab(lab, contrast=confirmed_contrast, strength=confirmed_strength)
linear_after = color_core.oklab_to_linear_srgb(lab)
# linear_after may be out of gamut. A later pipeline must map/report before encoding.
```

22 项新增自动测试只用合成数学数值，没有读取个人照片或下载材料。
真实 P3、人像肤色、夜景、天空断层、六风格区分度、LUT 回读与输出文件字节重复性均未由本增量验收。


## 高光色度滚降（0.5.0，重新实现）

本增量对应只读计划 3.4 的“亮部色度向白滚降”。前一版只调 L，a/b 恒定；
本版新增 `highlight_rolloff_oklab`，在经过亮度曲线的 Oklab 上按位置缩小 a/b。
保留现有 `contrast_oklab` 的纯亮度契约，调用者按先亮度、后滚降的顺序串接。
未找到历史 0.4.1 原型，不声称其配方、像素、性能或视觉成绩已经复现。

### 工程曲线的来源

这是本轮新设计的 Hermite 三次插值，来自以下数学约束，没有实验拟合系数：
在肩部起点保留全部色度，在白点满强度时色度为零，两端导数为零。
设归一化肩部位置 t∈[0,1]，色度保留量 f 为三次多项式，则
f(0)=1、f(1)=0、f′(0)=0、f′(1)=0 唯一确定
`f(t)=1-3t²+2t³=(1-t)²(1+2t)`。
系数 1、2、3 来自这四个边界条件，不是计划中未给出的调色配方。

设显式输入起点 q=start，强度 s=strength，输入为 (L,a,b)：

- L≤q 时，返回原坐标。
- L>q 时，`t=(L-q)/(1-q)`，`k=(1-s)+s*f(t)`，返回 `(L,k*a,k*b)`。
- q 必须在 [0,1)，s 必须在 [0,1]；所有输入必须是有限实数，L 在 [0,1]。
- L 不变；非零色度的 hue 不变，色度乘以 k。k 在 [1-s,1] 之间且随 L 非增。
  满强度白点 k=0，此时 hue 未定义，沿用内核 C=0 时记 h=0 的约定。
- s=0 返回独立的精确副本，仍先验证所有输入。s<1 的白点仍可有色度，
  函数不会为“看起来可显示”而偷偷改成全强度或钳位 RGB。

实现采用因式形式，避免在接近白点时用 `1-smoothstep(t)` 相消成零。
只计算 L>q 的像素，即使 q 是小于 1 的最大 float64，也不会对阴影作极小分母除法。
浮点下溢允许趋于零，溢出或非有限值拒绝；没有中间量化、裁切、RGB 色域映射或肤色键。
算法标识为 `oklab-highlight-chroma-hermite-v1`，原色彩转换标识保持不变。

### 参数、确认与证据边界

计划没有指定高光起点或这条三次公式。q、s 均无默认值，必须由调用者显式给出。
公式属于待真实摄影验证的工程实现，不是 Bill 已确认的六风格配方。
测试中 q=0.5、C、强度、采样网格与数值容差全部是合成数学测试选择，
目的为验证端点、方向、连续性、浮点稳定性与输入契约，没有真实观察数据含义。
q 的坐标是曲线后的 Oklab L，不是 sRGB 通道值、像素亮度统计或 EV。

只展示串接方式，以下代码不在本说明中执行，不读写图片，不假定参数已获确认：

```python
lab_after_tone = color_core.contrast_oklab(
    lab, contrast=confirmed_contrast, strength=confirmed_tone_strength)
lab_after_rolloff = color_core.highlight_rolloff_oklab(
    lab_after_tone, start=confirmed_highlight_start,
    strength=confirmed_highlight_strength)
linear_after = color_core.oklab_to_linear_srgb(lab_after_rolloff)
# Still potentially out of gamut. Map and report before encoding in a later stage.
```

两阶段强度各有作用域；这里没有新增“整套 look 的总强度”契约。
整个 skill 的 strength=0 验收仍须在未来完整管线和文件输出上再做。
本轮的 16 项新增测试包含手算 t=1/4、1/2、3/4 的结果、色相/亮度保持、单调性、
两端零斜率、只读与非连续输入、非法值、无默认参数、极窄肩部、接近白点残差，
以及合成 RGB 网格与已有传递函数/亮度曲线串接。原有测试断言保持不变。

CLI 仍为原有整数调色，真实 P3、人像、夜景与天空断层没有新增验收证据。
高光去色也不保证 RGB 落回 sRGB 色域；分色相/肤色保护、减法密度、色域映射与占比 QA、
纹理、最终抖动、六风格参数与端到端接入、LUT、16 位输出仍需后续完成。
