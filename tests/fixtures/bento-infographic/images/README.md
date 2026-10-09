# bento-infographic 开发与测试用图

只放三种来源的图（AUDIT-AND-IDEAS.md 4.12 通用规则第 6 条）：公有领域或 CC0 的照片、本库自己的产物截图、脚本画的合成图。
不放使用者电脑里的个人照片，也不放苹果的任何素材（苹果样图在旁边的 `apple-reference/`，只用来测量）。

| 文件 | 来源 | 授权 |
|---|---|---|
| `astronaut.jpg` | scikit-image 0.25 `skimage.data.astronaut()`：宇航员 Eileen Collins，取自 NASA Great Images 数据库 | 公有领域（"No known copyright restrictions, released into the public domain."） |
| `coffee.jpg` | `skimage.data.coffee()`：Pikolo Espresso Bar 的一杯咖啡，摄影 Rachel Michetti | CC0（"No copyright restrictions. CC0 by the photographer"） |
| `coffee-graded.jpg` | 上面那张经本库 `photo-cinematic-grade` 0.2.0 调色：`cinegrade.py render coffee.jpg --look warm-muted --strength 70 --assume-srgb` | 同上 |
| `chelsea.jpg` | `skimage.data.chelsea()`：猫 Chelsea，摄影 Stefan van der Walt | CC0（"No copyright restrictions. CC0 by the photographer"） |
| `rocket.jpg` | `skimage.data.rocket()`：SpaceX Falcon 9 发射 DSCOVR | 公有领域（SpaceX 2015 年把照片放进公有领域） |
| `rocket-graded.jpg` | 上面那张经本库 `photo-cinematic-grade` 0.3.0 调色：`cinegrade.py render rocket.jpg --output <目录> --look warm-muted --strength 70 --assume-srgb`，PNG 转 JPEG（质量 92）。画幅矩阵用它：顶上是夜空，白字放在哪种裁切里都看得清 | 同上 |
| `keynote-slide-number.png` | 本库 `keynote-deck-builder/examples/example-deck.html` 第 3 片的截图，裁掉了底部控制栏 | 本库自己的产物 |
| `keynote-slide-number-light.png` | 同一张片的浅色主题（页面上 `data-theme="light"`），截法相同；第 10 轮给浅色产品样例用 | 本库自己的产物 |
| `astronaut-graded.jpg` | `astronaut.jpg` 经本库 `photo-cinematic-grade` 0.3.0 调色（warm-muted，强度 70），研究版样例的主图 | 同 `astronaut.jpg` |
| `keynote-slide-formula-light.png`、`-dark.png` | 本库 `keynote-deck-builder/examples/lecture-deck.html` 第 9 片（单摆周期公式）的浅色、深色截图，1440×750 | 本库自己的产物 |
| `keynote-slide-specs-light.png`、`-dark.png` | 同一库 `example-deck.html` 第 9 片（规格密排）的浅色、深色截图，1440×750 | 本库自己的产物 |
| `spread-page.png` | 本库 `photo-spread-composer/examples/example-spread.html` 整页截图，只留版面本身，900 宽 | 本库自己的产物（版面里的照片是示例自带的色块占位图） |
| `skills-wallpaper.jpg` | 脚本画的合成图：`make_wallpaper.py`（同目录，确定性，不用随机数）用本库 README 徽章的蓝 #2f81f7 画的五层弧面，每层带亮边和投在下一层上的软影，中间留一块深蓝放白字；产品版样例的主图底（第 10 轮第 5 次重画：原来三块平涂圆面，评审说像系统默认壁纸） | 本库自己画的 |
| `coffee-compare.jpg` | `coffee.jpg` 经本库 `photo-cinematic-grade` 0.3.0 `compare`（warm-muted，强度 70）出的左原图、右调色并排图 | 同 `coffee.jpg` |
| `keynote-formula-crop-*.png`、`keynote-specs-crop-*.png`、`keynote-number-crop-*.png` | 上面几张演示片截图按内容裁出的中间一块（四周留 6–18% 的边，长宽比约 1.6），不缩略整页 | 本库自己的产物 |
| `spread-top.png` | `spread-page.png` 的上半页（标题和前两排照片） | 本库自己的产物 |
| `keynote-slide-phrase.png` | 同一份示例的第 2 片 | 本库自己的产物 |
| `keynote-slide-feature.png` | 同一份示例的第 6 片 | 本库自己的产物 |
| `radio-card.png` | 本库 `radio-quote-card/examples/example-card.html` 的截图，只留卡片本身 | 本库自己的产物 |
| `hubble.jpg` | `skimage.data.hubble_deep_field()`：哈勃望远镜的深空视场 | 公有领域（"may be freely used in the public domain"，NASA） |
| `camera.jpg` | `skimage.data.camera()`：摄影师与三脚架，摄影 Lav Varshney（灰度图存成 RGB JPEG） | CC0（"No copyright restrictions. CC0 by the photographer"） |
| `series-grid-light.jpg`、`series-grid-dark.jpg` | 本库 `photo-series-layout` 把 `astronaut.jpg`、`coffee.jpg`、`rocket.jpg`、`chelsea.jpg`、`hubble.jpg`、`camera.jpg` 排成 3 × 2：`layout_photos.py <六张> --layout grid --fit cover --canvas-width 1200 --canvas-height 800 --margin 0 --gutter 16 --background "#ffffff"`（深色版 `#000000`），PNG 缩到 900×600 存 JPEG（质量 90）；产品版样例的"组图排版"一格 | 同上面六张 |

授权原文抄自本机 scikit-image 各函数的文档字符串（2026-10-08）。scikit-image 的原图尺寸较小（最长边 512–640 px），
放进大格子会被放大，自检会报"图片放大"，这是预期之内的。
