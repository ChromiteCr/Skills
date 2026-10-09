# 苹果发布会 bento 总结图：测量样图

苹果发布会收尾总结图的截图：前五张 2026-10-07、第六张 2026-10-08 由使用者提供。它们是计划中的 `bento-infographic`
的测量依据（方案见仓库根目录 `AUDIT-AND-IDEAS.md` 第四部分），字号、格缝、圆角、主图比例都从这里量出来，
将来也给排版器做结构回归。

- **版权归 Apple Inc.** 这里只用作版式测量：不复制进任何 skill 目录，不进 `dist/` 的单技能包，
  任何产物都不引用、不拼贴、不描摹这些图。
- 图是视频截图的压缩版（WebP），单个像素读数有 ±1–2 px 的误差。

| 文件 | 内容 | 出处 | 底与格 | 格数（含主图） | 尺寸 |
|---|---|---|---|---|---|
| `01-iphone-16e.webp` | iPhone 16e | 2025-02-19 发布（新闻稿与视频，没有现场发布会） | 浅底，磨砂渐变格 | 16 | 1507×844 |
| `02-apple-watch-ultra-2.webp` | Apple Watch Ultra 2 | 2023-09-12 发布会（Wonderlust） | 白底，浅灰格 | 17 | 1400×788 |
| `03-ios-18.webp` | iOS 18 | 2024-06-10 WWDC24 主题演讲 | 浅灰底，白格 | 18 | 2000×1125 |
| `04-iphone-duo.webp` | iPhone Duo（折叠屏） | 2026-09-09 发布会 | 浅灰底，白格 | 17 | 1920×1080 |
| `05-iphone-17-pro.webp` | iPhone 17 Pro | 2025-09-09 发布会 | 深灰底，黑格 | 14 | 2000×1125 |
| `06-iphone-18-pro.webp` | iPhone 18 Pro | 2026-09-09 发布会（官方页 apple.com/iphone-18-pro，2026-10-08 查阅） | 深灰底，黑格 | 16 | 2000×1125 |

出处按苹果新闻稿核对，2026-10-07：
[iPhone 16e](https://www.apple.com/newsroom/2025/02/apple-debuts-iphone-16e-a-powerful-new-member-of-the-iphone-16-family/)、
[Apple Watch Ultra 2](https://www.apple.com/newsroom/2023/09/apple-unveils-apple-watch-ultra-2/)、
[iPhone Duo](https://www.apple.com/newsroom/2026/09/apple-unveils-iphone-duo/)、
[iPhone 17 Pro](https://www.apple.com/newsroom/2025/09/apple-unveils-iphone-17-pro-and-iphone-17-pro-max/)；
iOS 18 那张见 [AppleInsider 2024-06-12 的报道](https://appleinsider.com/articles/24/06/12/everything-apple-wants-you-to-know-that-is-coming-to-ios-18)。
历年的这类总结片可以在社区存档 [Apple Summary Slides](https://apple-summary-slides.vercel.app/all) 里翻到（iOS 18 这张不在里面）。

量出来的数字与量法见 `AUDIT-AND-IDEAS.md` 4.2；每张图的读数在 `measurements.json`（由 `measure_reference.py all` 生成，
人工切线和标签框在 `labels.json`）。第 6 张另有一组裁剪 `iphone-18-pro-crops/`，只供对齐调试，说明见那个目录。
