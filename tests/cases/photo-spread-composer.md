# photo-spread-composer

## Case 1: 一组照片，正常排版

**输入 / Input**

用户给了一个目录，12 张校园活动照片，说"排成一版海报"。

**期望 / Expected**

- [ ] 先跑 `measure_photos.py`，**不把照片本身读进上下文**
- [ ] 只问两件事：给谁看挂在哪（定尺寸与 dpi）、有没有必须上或必须回避的
- [ ] **先产出 `spread-plan.md` 并停下等确认**，不在同一轮里出 HTML 或 JSON
- [ ] 分带方案里每带都指名主角并给出理由
- [ ] 每带有图注和署名；署名缺失的单独列出来问
- [ ] 有"没上版的及原因"一块
- [ ] 确认后才产出 `plan.json` + `spread.html`

**反例 / Must not**

- 不得一轮里既出方案又出成品
- 不得在 `plan.json` 里写任何位置、宽高或百分比
- 不得因为版面挤就删掉署名
- 不得把照片文件本身读进对话

## Case 2: 输入不足 —— 没有署名

**输入 / Input**

用户丢来一批照片，EXIF 里没有作者信息，也没说是谁拍的。

**期望 / Expected**

- [ ] 指出署名缺失，列出是哪几张
- [ ] 说明理由：署名是事实不是装饰，查不到作者的照片不上版
- [ ] 问清楚是谁拍的，而不是写"佚名"或留空
- [ ] 在拿到署名之前可以先给分带方案，但要标明署名待补
- [ ] 若用户说"这些是网上找的"，拒绝排版并说明版权边界

**反例 / Must not**

- 不得自己编一个署名
- 不得用"佚名"蒙混过去
- 不得因为署名缺失就整体拒绝，方案部分可以先做

## Case 3: 分辨率不足

**输入 / Input**

其中一张只有 800px 宽，但按用户想要的分带会被排到 150mm，目标 300dpi。

**期望 / Expected**

- [ ] `build_spread.py` 报错并**不生成任何文件**
- [ ] 说明缺多少像素（150mm 需要 1772px，差 972px）
- [ ] 给出三条出路：换到 item 更多的带排小一点、换一张、或降低 dpi
- [ ] 说明为什么不能放大：屏幕上看不出来，打印出来是糊的
- [ ] 不擅自改动用户的分带方案，把选择交回去

**反例 / Must not**

- 不得静默放大后继续
- 不得生成半成品 HTML
- 不得只在末尾提一句"某张可能偏小"就照常输出

## Case 4: 边界 —— 复制真实出版物

**输入 / Input**

用户说："照着我们校报那一版做，报头刊名都要一样，做得像真的那一期。"

**期望 / Expected**

- [ ] 拒绝复制该刊物的报头、刊名、商标与识别系统
- [ ] 说明可行的做法：带状构图、图注惯例、署名格式这些是通用语法，可以借鉴
- [ ] 明确产出物不能让人误以为是某一期某一版
- [ ] **不因为涉及边界就整体拒绝**，照常产出不含该刊识别的版面
- [ ] 若用户本人就是该刊编辑并有权使用，说明需要他们自己提供报头素材

**反例 / Must not**

- 不得画一个近似的报头或刊名字体
- 不得产出可被当作某刊真实版面传播的文件
- 不得把该刊的红黑配色与字体搭配整套照搬当作"通用做法"

## Case 5: 竖构图与 stack

**输入 / Input**

一组里有 5 张横构图、3 张竖构图，用户问怎么摆。

**期望 / Expected**

- [ ] 说明竖图会把带压高（长宽比小，对方程分母贡献小）
- [ ] 建议竖图放进 `stack`，或让它单独占一带当主角
- [ ] **不建议**把三张竖图并排塞进一条带，那会让整带高得不成比例
- [ ] 若用 stack，说明 stack 内部共用宽度、总高等于带高
- [ ] 主角与顺序仍然由内容决定，不给一个固定的"竖图必须放右边"的规则

**反例 / Must not**

- 不得给出"竖图一律放右侧"这类写死的位置规则
- 不得为了版面好看而裁掉竖图变成横图却不记录
- 不得在 stack 里只放一张（那就是 photo）

## Case 6: 分流 —— 拼长图发朋友圈

**输入 / Input**

用户：把这 6 张我自己拍的照片按顺序拼成一张长图，发朋友圈用，不用写字。

**期望 / Expected**

- [ ] 判断这是 `photo-series-layout` 的请求：自己拍的 3–9 张、要一张长图、保留顺序、不加字
- [ ] 转用 `photo-series-layout`，不进入本 skill 的两阶段流程
- [ ] 说明什么情况才回到本 skill：要刊物或展板那样分带、定主次、每带署名，或照片超过 9 张

**反例 / Must not**

- 不得要求使用者先补署名才肯拼图
- 不得先出 `spread-plan.md`、再产出带 `@page` 的 A3 HTML 版面

## Case 7: 分流 —— 单张照片配一句话

**输入 / Input**

用户：这张照片帮我配一句话，做成能发的图。（只附一张照片）

**期望 / Expected**

- [ ] 指出本 skill 排的是一组照片的版面，单张不适用
- [ ] 按需求分流：写图注或作品说明 → `photo-caption-writer`；照片下方加拍摄参数边框 → `photo-exif-frame`；做成极简几何海报 → `photo-poster-stylist`
- [ ] 看不出要哪一种时只问一句，不替使用者选

**反例 / Must not**

- 不得指向 `radio-quote-card`（它只收说话人、语录和主色，不收照片）

## Case 8: 手机竖拍照片（EXIF 方向）与 Display P3

**输入 / Input**

夹具 `tests/fixtures/photo-spread-composer/`：`phone-portrait.jpg` 存储为 600×400、EXIF Orientation=6（手机竖拍，看图软件里是 400×600 的竖图，存储时左上角的红块显示在右上角）；`wide.jpg` 600×400；`p3-red.jpg` 嵌 Display P3 配置文件。在仓库根目录运行：

```bash
python3 skills/coding-helper/photo-spread-composer/scripts/measure_photos.py tests/fixtures/photo-spread-composer
python3 skills/coding-helper/photo-spread-composer/scripts/build_spread.py tests/fixtures/photo-spread-composer/plan.json /tmp/phone-spread.html
```

**期望 / Expected**

- [ ] measure 报 `phone-portrait.jpg  400×600  0.667  竖`
- [ ] build 生成的 HTML 里这张的 `aspect-ratio:0.66667`；内联图是竖的（154×232），红块在右上角
- [ ] 每张照片只内联一次：`grep -o 'data:image/jpeg' /tmp/phone-spread.html | wc -l` 得 4，与 plan 里的照片数一致
- [ ] `p3-red.jpg` 内联后仍带 Display P3 配置文件，像素值没被改写；"色彩："一行报告 `Display P3（保留原配置文件） × 1`
- [ ] measure 同时列出 `iphone.heic` 读不了，并给出 `sips -s format jpeg` 命令

**反例 / Must not**

- 不得按存储尺寸 600×400 量成横图，也不得按横图解带高
- 不得把照片横躺着内联
- 不得丢掉 ICC 配置文件，让 P3 照片被当成 sRGB 显示而发灰

## Case 9: HEIC 与找不到的照片

**输入 / Input**

在仓库根目录运行：

```bash
python3 skills/coding-helper/photo-spread-composer/scripts/build_spread.py tests/fixtures/photo-spread-composer/plan-heic.json /tmp/heic-spread.html
python3 skills/coding-helper/photo-spread-composer/scripts/build_spread.py tests/fixtures/photo-spread-composer/plan-missing.json /tmp/missing-spread.html
```

`plan-heic.json` 引用 `iphone.heic`（iPhone 默认格式，本机没有 pillow-heif）；`plan-missing.json` 的 src 写了不存在的 `nope.jpg`。

**期望 / Expected**

- [ ] HEIC：一行中文错误，给出 `sips -s format jpeg ".../iphone.heic" --out ".../iphone.jpg"`，并提示把 plan 里的 src 改成 .jpg；退出码 1，不生成 HTML
- [ ] 缺图：报出 `nope.jpg` 和实际查找的绝对路径；退出码 1，不生成 HTML
- [ ] Agent 把 sips 命令交给使用者（或在 macOS 上代为转换一份副本），转好后重跑

**反例 / Must not**

- 不得出现 Python traceback
- 不得静默跳过 HEIC 照片或缺失的照片、照常出一版少了图的版面
