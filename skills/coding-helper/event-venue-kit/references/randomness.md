# 抽牌协议 / The draw protocol

这份文件规定"每个项目长得不一样"是怎么做到的。质量来自地板和引擎，外观来自抽牌。两件事分开放，随机才不会掉质量。

## 为什么要抽牌 / Why draw at all

- **同一份 brief，不抽牌就是同一个网站。** 实测：没有本技能时，同一个"高中科学节 + 3D 楼层图"的 brief 跑两次，两次都选了元素周期表做主视觉，都是浅方格纸底 + 墨色 + 一个强调色 + 等宽小字 + 倒计时胶囊 + 四格数字 + 底部 Tab。第三个 brief（旧书市集）落进了另一个常见聚类：暖纸 + 宋体 + 印泥红 + 邮戳。三份都做得认真，问题是它们来自同一个"平均印象"。
- **只写禁令会换来下一个默认值。** Anthropic 的 frontend-design 从"别用 Inter 和紫色渐变"改到"别落进奶油底 + 衬线 + 赭红"；huashu-design 的第三轮实验把约束加满后，三版全部退回冷色网格。结论是"加选项，不加禁令"。
- **所以随机发生在方向池里，而不是写在指令里。** 池子里每个方向都是一整套自洽的外观（配色结构、字体角色、形状语言、分隔线、实体页头、地图材质、动效性格），手工定过、能出样张；抽中之后再在方向的包络内抽具体参数。

## 协议 / Protocol

1. **先盘点，再抽牌。** 按 `references/derive.md` 列出这个活动的 8–12 件实物（名字里的名词、建筑、仪式、数据、上一届、观众手里的媒介），每件给 1–3 个标签。标签只用 derive.md 的词表。
2. **抽三张。**
   ```bash
   python3 scripts/draw.py --tags campus,science,competition --out .evk/roll.json
   ```
   - 不给 `--seed` 时脚本自己取随机种子并写进 `roll.json`；给了就能复现同一手牌。
   - 权重 = 方向基础权重 × 标签匹配 × 历史降权（最近 6 次选过的方向 × 0.25，永远不为 0）× `--steer`。
   - 原站方向 `varsity` 的基础权重只有 0.15。
3. **看样张，不看名字。**
   ```bash
   python3 scripts/specimen.py .evk/roll.json --all --out .evk/specimens
   ```
   三张牌各出一页自包含的样张（首页入口、实体网格、实体页头、分部、底部弹层、活地图）。**在浏览器里打开三页再选。**只读方向名，得到的是那个名字的平均印象。
4. **选一张，写一句理由。** 理由必须点名盘点清单里的一件实物（"201 门口那条红墙带"，而不是"更有活力"）。
   ```bash
   python3 scripts/draw.py choose 2 --reason "义卖小票和收银机的打孔纸带，正好落在 festival-riso 的票根上" --roll .evk/roll.json
   ```
   选定才写入历史（`~/.event-venue-kit/history.json`），下一次抽牌会给它降权。
5. **落地。** `python3 scripts/install.py .evk/roll.json <项目目录>`：写 `evk/tokens.css`，复制 `base.css`、该方向的 recipe 与引擎，生成项目里的 `DESIGN.md`。没有选定的牌，install 会拒绝运行。
6. **做完再量。** `lint_floor.py` 查地板，`similarity.py` 查与原站的指纹距离（12 个轴，匹配比例 ≥ 0.5 而用户没要原站外观时，回到第 2 步重抽）。

## 什么时候可以不按抽到的来 / When the draw yields

- **已有品牌或硬性约束：冻结，不抽。** 抽牌**之前**就把 brief 翻成 `--keep`，不要等抽完再发现冲突。
  - 品牌色：`--keep palette=#0B5FFF,#FF5A1F`。字体：`--keep display="Source Serif 4"`。
  - 地图："可旋转 / 能转" 写成 `--keep projection=rotate`（orbit 或 exploded，拖动就转）；"3D、能看到几层" 写成 `--keep projection=3d`（还包括 oblique：固定斜角，拖动是平移）；`--keep projection=plan` 是平面。
  - 主语言：`--keep lead=zh`（中文为主）或 `lead=en`。
  - 被冻结的轴照用，其余照抽。冻结不会改变其他参数的抽法：同一个种子，加不加 `--keep`，没冻结的参数都一样。brief 里白纸黑字的要求永远压过抽牌。
- **选定之后要改，用 `adjust`，不要重抽。**
  - 例：`python3 scripts/draw.py adjust pitch=30 wall_h=.6 --reason "brief 要看清三层" --roll .evk/roll.json`。
  - 它在原牌上改，重算依赖的颜色与 token、指纹和相似度，把"改了什么、从多少到多少、为什么"记进 `adjusted`。再跑 `install.py <roll> <项目> --update`，只重写 `evk/tokens.css` 和 `.evk/roll.json`（`tokens.css` 里你打开的 `--prop-*` 行原样保留，其他手改的 token 会被重新生成），不动你改过的页面和 `DESIGN.md`（新的规格写到 `.evk/DESIGN.generated.md`，自己合进去）。
  - 手改 `roll.json` 会让指纹和相似度停在旧值。`choose` 之后重抽，会让刚选的方向在历史里被降权。
  - 重抽只在 `choose` 之前做。万一选定后必须重抽，`draw.py` 与 `choose` 都加 `--no-history`，并在 `DESIGN.md` 写明原因。
- **重抽只在三种情况下允许，最多两次，理由写进 `roll.json`：**
  1. 与品牌或 brief 的硬约束冲突；
  2. 这个方向做不出某件"最差情况的物件"（门牌、单色印章、5 米外的房号、32 px 小图标）；
  3. 与原站相似度 ≥ 0.5。
  - "不太喜欢"不算理由：先去看样张，看过还不行，就用 `--steer` 调整方向而不是一直重抽。
- **用户要原站的样子：** 只有用户明说"做成和 College Fair 那个一样 / 同一家族"时才用 `--canon`。这时完整规格在 `references/reference-direction/DESIGN.md`。
- **用户说"更大胆 / 更稳"：** `--steer bolder` 提高离原站远、对比强的方向的权重，并把包络往大胆一端拉；`--steer safer` 反过来。
- **方向内的参数可以手动微调**，前提是理由来自内容（例如实体名普遍很长，就把展示字号的比例从 1.5 调到 1.33）。改动写进项目的 `DESIGN.md`，并在 `roll.json` 里记一条 `adjusted`。

## 抽牌永远碰不到的东西 / What the draw never touches

地板（`references/floor.md`）和 UX 契约（`references/ux-contracts.md`）不参与随机：
- 对比度角色与实体色算法；
- 双语层级；
- 触控与焦点；
- 减弱动效；
- 只为状态而动、可打断的弹簧；
- 地图静止时不重绘；
- 读长页时任何时刻都知道自己在哪；
- 路线能给出分步文字；
- 真实数据，不放个人信息。

抽牌只改这些契约的**呈现**，不改契约本身。

## 没有 Python 时（降级） / Without Python (degraded)

运行环境跑不了脚本时，流程不变，按下面的手工做法，并在输出里写明"降级：手工抽牌"：

1. 打开 `library/directions.json`，按标签匹配给每个方向打分：匹配 1 个标签 ×1.5，2 个以上 ×2。`varsity` 固定 ×0.15。
2. 用当前秒数（`date +%S`，或对话里给出的时间）对候选总数取模，抽第一张；剔除它再取一次模，抽第二张、第三张。
3. 每张牌的参数取包络的中点，配色按 `scripts/kit.py` 文件头描述的步骤手算对比度。**拿不准的对比度不要凭眼估，标"未核"。**
4. 没有样张时，用文字写出三张牌各自的首页与实体页头长什么样（各 3 行），选一张并写理由。
5. 交付时把种子（所用秒数）、三张牌、选择与理由写进项目的 `DESIGN.md`。
