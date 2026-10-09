# iPhone 18 Pro 官方总结片的裁剪（只供对齐调试）

从同目录上一级的 `06-iphone-18-pro.webp`（苹果官方 iPhone 18 Pro 总结片，使用者 2026-10-08 提供）裁出来的图片，
给 `tests/fixtures/bento-infographic/specs/iphone-18-pro-dark.json` 用：内容和官方完全相同，排版和文字交给本 skill，
再拿成图和官方逐格比（`test_bento.py` 的 `AlignIphone18Pro`）。

- **版权归 Apple Inc.** 只用于本仓库的对齐测试：不进 `skills/` 目录、不进 `examples/`、不进 dist 包，
  也不出现在任何对外展示的页面上（使用者 2026-10-08 的要求）。
- 裁的时候避开了官方图上的标签文字，标签由本 skill 重新排；图片里自带的界面文字（相机界面的读数、A20 芯片上的字）照原样保留。

| 文件 | 官方格子 | 裁剪框（2000×1125 坐标） |
|---|---|---|
| `hero.png` | 主图（PRO 与机身） | 523, 305, 1477, 820 |
| `pro-controls.png` | Pro controls | 30, 28, 486, 268 |
| `telephoto.png` | 4x/8x Fusion Telephoto | 818, 100, 1084, 270 |
| `sizes-phones.png` | 6.9″ / 6.3″ 中间的两台机身 | 1236, 40, 1362, 262 |
| `dynamic-island.png` | Redesigned Dynamic Island 的界面条 | 52, 510, 458, 582 |
| `main-camera.png` | 48MP Fusion Main camera with variable aperture | 28, 673, 487, 1015 |
| `colors-phones.png` | Beautiful new colors 的四台机身 | 1515, 350, 1970, 552 |
| `reference-image-icon.png` | Apple Reference Image 的图标 | 1560, 610, 1680, 725 |
| `charging-icon.png` | Faster wired charging 的电池图标 | 1795, 630, 1945, 712 |
| `cinematic.png` | Cinematic from regular video | 522, 855, 786, 1020 |
| `siri-orb.png` | Siri AI 的球 | 835, 890, 965, 1020 |
| `a20-chip.png` | A20 PRO 芯片 | 1068, 885, 1245, 1062 |
| `photographic-styles.png` | Photographic Styles with texture control | 1611, 856, 1972, 1018 |
