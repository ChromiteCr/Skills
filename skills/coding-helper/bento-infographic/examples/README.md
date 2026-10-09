# 样例

三份完整样例，每份有 `bento.json`（内容清单）、`layout.json`（选定的排版）、`bento.png`（成图）、`qa.json`（19 项自检，全部通过）。

| 目录 | 画幅 | 内容 |
|---|---|---|
| `product-light/` | 16:9，1920×1080，浅色 | 本库自己的数字（2026-10-08 现数）和产物：技能数、测试用例数，演示片、规格片、公式片、跨页版面、语录卡、调色前后对比、组图等截图；主图是脚本画的本库蓝色层叠弧面加品名 |
| `product-dark/` | 同上，深色 | 同一份内容、同一个排版；公式片和组图换成深色版，大字一律纯白 |
| `research-3x4/` | 3:4，1080×1440，浅色，研究模式 | 电影感调色原型 0.4.1 的实测数字（仓库根目录 `AUDIT-AND-IDEAS.md` 第三部分 3.5、3.9），外加本库 photo-cinematic-grade 0.3.0 在本机实测的渲染耗时；数字和柱图高亮用本库徽章的蓝 |

每个数字的出处写在 `bento.json` 各格的 `facts` 里；没上图的条目和理由写在 `dropped` 里。

重新渲染（在本 skill 目录下）：

```bash
python3 scripts/bento.py render examples/research-3x4/bento.json examples/research-3x4/layout.json --out /tmp/bento-research
```

## 图片来源

只用三种来源，不用苹果的任何素材。

| 文件 | 来源 | 授权 |
|---|---|---|
| `images/skills-wallpaper.jpg` | 脚本画的合成图：用本库 README 徽章的蓝 #2f81f7 画的五层弧面，每层带亮边和投在下一层上的软影（生成脚本在仓库的 `tests/fixtures/bento-infographic/images/make_wallpaper.py`） | 本库自己画的 |
| `images/coffee.jpg` | scikit-image 0.25 `skimage.data.coffee()`，摄影 Rachel Michetti | CC0 |
| `images/coffee-compare.jpg` | 上面那张经本库 photo-cinematic-grade 0.3.0 `compare`（warm-muted，强度 70）出的左原图、右调色并排图 | 同上 |
| `images/chelsea.jpg` | `skimage.data.chelsea()`，摄影 Stefan van der Walt | CC0 |
| `images/rocket.jpg` | `skimage.data.rocket()`：SpaceX Falcon 9 发射 DSCOVR | 公有领域 |
| `images/rocket-graded.jpg` | 上面那张经本库 photo-cinematic-grade 0.3.0 调色（warm-muted，强度 70） | 公有领域 |
| `images/astronaut-graded.jpg` | `skimage.data.astronaut()`（宇航员 Eileen Collins，NASA）经本库 photo-cinematic-grade 0.3.0 调色（warm-muted，强度 70） | 公有领域 |
| `images/keynote-formula-crop-*.png`、`keynote-specs-crop-dark.png`、`keynote-number-crop-dark.png` | 本库 keynote-deck-builder 两份示例片（讲座第 9 片的单摆公式、发布会第 9 片的规格、第 3 片的大数字）的截图，按内容裁出中间一块；公式片有浅色、深色两版，另两张只用深色版（浅色版在白格里看不出边） | 本库自己的产物 |
| `images/series-grid-light.jpg`、`series-grid-dark.jpg` | 本库 photo-series-layout 把六张样图（宇航员、咖啡、火箭、猫、哈勃深空、摄影师，都来自 scikit-image）排成 3 × 2：`layout_photos.py … --layout grid --fit cover --canvas-width 1200 --canvas-height 800 --margin 0 --gutter 16`，白底、黑底各一张，缩到 900×600 存 JPEG（质量 90） | 公有领域与 CC0（各图出处见仓库 `tests/fixtures/bento-infographic/images/README.md`） |
| `images/spread-top.png` | 本库 photo-spread-composer 示例版面的上半页（版面里的照片是示例自带的色块占位图） | 本库自己的产物 |
| `images/radio-card.png` | 本库 radio-quote-card 示例卡片的截图 | 本库自己的产物 |

产品版的重点色也是 #2f81f7。研究版的主图是调过色的宇航员样图，只作示意；图上的数字说的是调色原型和本库的调色脚本，不是这张图。
