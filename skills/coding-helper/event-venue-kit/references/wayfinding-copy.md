# 路线文案、搜索与链接 / Wayfinding copy, search and links

> 给 `EVK.wayfind.describe(plan, lang)`、搜索框、链接语法和所有"一句话"的人。原站措辞是一个实例（**原站取值 / source value**），标"（本套件补充）"的是原站没有、为英文或其他场合补的。
> 例子里的场馆、实体是虚构的；结构取自原站的真实输出。

## 1 总则与双语分工 / Principles

1. **按遇见的顺序叙述**：我站的地方 → 怎么出门 → 地标 → 换层 → 出楼梯 → 门牌 → 进去后 → 展位。
2. **用人会看见、读到的东西**：门牌号、电梯、洗手间、展位号；不用方位词，除非场地本来就用（校园、户外，§4.1）。
3. **近似要说出来**：距离带"约"。**只发布走过的指引**：房间提示字段默认空，没人走过就不写。
4. **一步一句**；可选从句只在有信息时才出现，短腿保持短。
5. **平静的工具语气**：短动词，没有感叹号、没有 emoji、没有"哎呀"。
6. **语言分工，不是逐句互译**：原站英文行 = 路牌（短祈使句，不带数字和转向），中文行 = 句子（转向、地标、距离全在这里）。两种语言的**动作和目的地一致**。

| 双语策略 | 原站取值 | 可换 |
|---|---|---|
| 分工 | 英文标题 + 中文整句 | 两种整句平行；用户一次选定语言；图标 + 单语标签；中文在前（内容本来用中文写成时，如主题路线名） |
| 主语言 | 英文（学术语境），即 `lead=en` | `lead=zh`：每步取 `step.cn` 的标题与整句为主、`step.en.text` 为副；混合人群**两种同时出现**，不靠切换钮藏起一种（`ux-contracts.md` LD） |

---

## 2 中文步骤模板 / Chinese step templates

`describe(plan, "zh" | "en" | "both")` 返回 `[{ kind, floor, seg, metres, head, text, en:{head,text}, cn:{head,text} }]`；`"both"` = 英文标题 + 中文整句。中文模板（`{}` 为槽，`〔〕` 为可选从句）：

| 类型 | 标题 head | 整句 text | 可选从句何时出现 |
|---|---|---|---|
| walk（首段） | `走到{房间}` / `走到{楼梯名}` | `从{起点}出发，〔出门后左转/右转/直走，〕走到{房间}门口，约 {N} 米。` | 起点是房间、出口朝向可定义，且起点房间 ≠ 目的房间 |
| walk（出楼梯 / 电梯后） | 同上 | `〔出楼梯后左转/右转/直走，〕走到{房间}门口，约 {N} 米。` | 本段第一个点离楼梯中心 > 0.1 m |
| stairs / lift | `上到 {层} 层` / `乘电梯上到 …` | `走楼梯上到 {层} 层。` / `乘电梯下到 …` | |
| arrive | `{展位} 号展位 · {实体名}` | `进入{房间}〔再走约 {N} 米〕，{实体名}在 {展位} 号展位。` | 室内余段 ≥ 3 m 才有"再走约" |
| 同房间 | `就在这个房间 · {展位} 号展位` | `就在{房间}里：{实体名}在 {展位} 号展位。` | 起点房间 = 目的房间 |
| walk（目标在开放区 / 无区地面） | `走到 {展位} 号展位` | 同上两行，目的地换成 `{展位} 号展位`（无"门口"）；起点房间的转向写"出房间后"；动词按下文 | |
| arrive（展位在开放区里） | `{展位} 号展位 · {实体名}` | `{实体名}在{区域}的 {展位} 号展位。`（无区地面：`{实体名}在 {展位} 号展位。`） | 没有"进入" |

**开放区与走廊（`areas[]`）**：区没有门，句子里**一个"门"字也没有**：目的地是展位本身，起点房间的转向写"出房间后"（"as you leave the room"，不写 "out of the door"）。`corridor` 用"沿"（follow），`open` 用"穿过"（cross）：任何一段 walk（含去楼梯的）在同一区内走了 ≥ 4 m 且占全段 ≥ 40 %（`viaMin` / `viaShare`）就换成"沿…走到 / 穿过…走到"。区也能当起点（`starts()` 里的 `area:<id>`："从西走廊出发"）。区名写成普通名词 `{en:"west corridor", cn:"西走廊"}`：英文不带 the（句子自己加）、不以 door / 门口 结尾。

槽的写法：
- `{起点}` / `{房间}`：入口、大堂 → 全名（"入口"、"一层大堂"，原站带全角括号"一层大堂（西门入口）"）；房间 → 纯数字标号写数字（"203"，后接"门口"），有名字写名字（"报告厅"）；主题路线后续段 → `{实体名}（{房间} · {展位}）`。
- `{层}`：步骤里用楼层的**短名** `floors[].short.cn`（缺省 = "<层号> 层"，"2 层"）；原站测试钉死整句 `走楼梯下到 1 层。`。`{展位}` 两位补零（"01"）。
- **单位词**走 `venue.terms`（`booth` / `room` 的中英文），按活动换：展位 / 摊位 / 展台 / 展品 / 会议室；booth / stand / stall / exhibit / room。

实测输出（`assets/demo/venue.json`，虚构场馆；`"both"` 模式）：
```
入口 → Echo Pottery 回声陶艺（203 · 02）   全程约 24 米
1 walk   Walk to the stairs at the east end   从入口出发，穿过中庭走到东侧楼梯，约 14 米。
2 stairs Up to 2F                             走楼梯上到 2 层。
3 walk   Walk to Room 203                     出楼梯后右转，走到 203 门口，约 5 米。
4 arrive Booth 02 · Echo                      进入 203 再走约 5 米，回声陶艺在 02 号展位。
```
目标在开放区里（没有"门"）：
```
入口 → Driftwood（西走廊 · 07，3F），后两步
3 walk   Walk to booth 07       出楼梯后右转，沿西走廊走到 07 号展位，约 10 米。
4 arrive Booth 07 · Driftwood   浮木木作在西走廊的 07 号展位。
入口 → Lanterns（中庭 · 01，1F）
1 walk   Walk to booth 01       从入口出发，穿过中庭走到 01 号展位，约 11 米。
2 arrive Booth 01 · Lanterns    中庭灯笼在中庭的 01 号展位。
```

---

## 3 英文步骤模板 / English step templates

**标题**（原站取值，路牌式，无数字、无转向）：`Walk to {room}` · `Walk to the {stairs-name}` · `Up to {floor}` / `Down to {floor}` / `Lift up to {floor}` · `{Booth} {no} · {short}` · `Same room · {booth} {no}`。房间：纯数字标号 → `Room 203`（`terms.room`），有名字 → `the Grand Hall`。`{floor}` 是楼层的短名 `floors[].short.en`（缺省 = 楼层 id，"2F"）。`{short}` 取拉丁字母的短名；`short` 是中文时引擎改用 `name.en`，英文行里不出现汉字。

**整句**（引擎 `describe(plan, "en")`；原站只有标题，整句是本套件补充）：

| 类型 | 模板 |
|---|---|
| walk（首段） | `From {origin}, 〔{turn left\|turn right\|go straight} out of the door, 〕walk to {room}, about {n} m.` |
| walk（出楼梯 / 电梯后） | `Out of the {stairs\|lift}, {turn left\|keep straight\|turn right}, walk to {room}, about {n} m.` |
| stairs / lift | `Take the {stairs\|lift} {up\|down} to {floor}.` |
| arrive | `Go into {room}〔 and walk about {n} m further〕. {Entity} is at {booth} {no}.` |
| 同房间 | `It is in {room} itself. {Entity} is at {booth} {no}.` |
| walk（到开放区里的展位） | 同上两行，`walk to {room}` 换成 `{follow the {corridor}\|cross the {area}} to {booth} {no}`；首段转向写 `{turn left\|…} as you leave the room` |
| arrive（开放区 / 无区地面） | `{Entity} is at {booth} {no} in {the area}.`（无区：`…is at {booth} {no}.`） |

规则：阿拉伯数字；`m` 前加空格；"about" 对应"约"；`{origin}` 入口 / 大堂用 `the` + 全名。
- **英文名怎么写进句子**：`name.en` 写成**牌子上的样子**：专有名称用 Title Case（`South Entrance`、`Grand Hall`、`Atrium Lanterns`），**不带开头的 the**——句子需要冠词时引擎自己加，名字里真有开头的 `The` 也会先去掉再加（不会出现 "the The Grand Hall"）；普通名词性的区名可以小写（`west corridor`），两种写法引擎都原样用（"Follow the West Corridor to booth 07" / "Follow the west corridor …"），地图上首字母大写。实体名在句首，原样（"The Kelp Company is at booth 01."），所以实体的 `name.en` 开头的 The 要保留。
- **到达句不再用分号**：`…walk about 6 m further. Kelp & Co. is at booth 01.`，实体名是句首，大小写不受前半句限制。
- **楼层**：句子与地图的爬楼标签（"Up to 3F"）都取 `floors[].short`；标题与小节名才取 `floors[].name`（§4.4）。
换法：命令式碎片（`Left out of 203. Straight 11 m.`）；距离在前；每个转角一步；第二人称叙述。

---

## 4 地标 · 距离 · 转向 · 命名 / Landmarks, distances, turns, naming

### 4.1 地标梯
楼梯 / 电梯井的名字（引擎 `connectorName`）依次取：①作者在数据里给的 `label`（"东侧楼梯 / stairs at the east end"）；②电梯 → `电梯 / lift`；③9 m 内最近的电梯或洗手间块 → `电梯旁的楼梯 / stairs by the lift`、`洗手间旁的楼梯 / stairs by the toilets`（原站取值）；④门在 4 m 内的房间 → `203 旁的楼梯`；⑤`楼梯 / stairs`。
要求（本套件补充）：**同一层楼梯名必须互异**，重名就在数据里给 `label`，构建期检查。语法：`label.en` 不带 the（引擎自己加，否则成 "the the stairs"），同样适用于入口、大堂、房间、区的英文名（上面"英文名怎么写进句子"）；`label.cn` 原样使用（"东侧楼梯"）。展位词走 `terms.booth`：`booth.cn` 是**后缀模板**（引擎写"07 号"再接它：给"展位"，不是"号展位"或整句），`booth.en` 是小写名词。换法：区域色；校园 / 户外用方位；最近展位名。

### 4.2 距离：先"到门口"，再"进入后"
- `到门口` = 折线首次**进入**目的房间多边形前的长度（沿线每 0.1 m 采样）；`进入后` = 余下的长度。
- `metres(m) = max(1, round(m))`，永远写"约 N 米"，不出"0 米"；"再走约 N 米"只在余段 ≥ 3 m 时出现；总长（kicker）= 各段之和，爬楼梯不加。kicker：`To · 28 m` / `前往 · 约 28 米`。
- 换法（本套件补充，推算）：步数（≈ 0.75 m / 步）；时间（≈ 1.3 m/s，12 m ≈ "约 10 秒"）；长路线取整到 5 m；累计"还剩 18 米"；英制（取整到 5 ft）。

### 4.3 转向词
- `turn(a, b)`：`dot = a·b/|a||b|`；`dot > 0.82`（偏转 < 约 35°）→ 直走；否则 `cross = a×b/|a||b|`，`> 0` 右转，否则左转。**平面 y 轴朝南**：朝东 (1,0) 转到朝南 (0,1)，`cross = +1` = 右转。（测：此用例）
- 出房间的转向：沿折线找首次离开起点房间的位置 `d`，`a = d−0.6 m` 处，`b = d+0.4 m`，`c = d+3.2 m`，比较 `b−a` 与 `c−b`。
- 出楼梯的转向：楼梯中心 → 沿新段 1.2 m 处，对比该点 → 4 m 处；仅当本段首点离楼梯中心 > 0.1 m。
- **只在方向有定义时说**：大堂起点、同房间都没有转向。词表：`左转 / 右转 / 直走` ↔ `turn left / turn right / go straight`，句内如 `出门后左转，` `出楼梯后右转，`。
- 换法：钟面（"10 点钟方向"）；方位；渐进词（本套件补充：35–70° `bear left`、70–120° `turn left`、> 120° `sharp left`）；只给箭头。

### 4.4 命名顺序：房间在前，楼层在后
| 场合 | 顺序 | 例 |
|---|---|---|
| 选择列表、起点下拉、搜索结果（扫读键在前） | 房间在前，楼层作小标签或在后 | `203 展区 · 二层` / `Room 203 · 2F`；结果行右侧：小字楼层在上、大字房号在下 |
| 英文描述行 | 小 → 大 | `Room 203 · 2F` |
| 中文描述行（原站） | 大 → 小 | `二层 · 203 展区` |
| 步骤句 | 只写房间；楼层由"上到 2 层"那步承担 | `走到 204 门口` |

原站的不一致：描述行楼层在前，下拉里房间在前。**建议每个表面选一种顺序，同一表面两种语言一致**，写进 `DESIGN.md`。
楼层词同理，**选一种**：楼层控件、位置行、步骤句都用同一个短名，测：步骤句里的楼层串 = 控件上的标签串 = 位置行里的楼层串。在数据里这是两个字段：
- `floors[].short`（`{en:"4F", cn:"4 层"}`）：**句子、楼层钮、标签、位置行**（"Take the stairs up to 4F." / "走楼梯上到 4 层。" / "Room 204 · 4F"）和地图的爬楼标签。缺省 `{en: id, cn: "<层号> 层"}`（层号 ≥ 1），层号 ≤ 0（地下）取楼层的中文名。
- `floors[].name`（`{en:"Fourth Floor", cn:"四层"}`）：**标题**（首页的楼层分组标题、楼层弹层的名字）。缺省 = id。
- **同一串不印两遍**：标题把 `short` 当小标签、`name` 当名字，两者在某种语言里相等（`1F` 与 `1F`）就只印一次，不出现"1F 1F"；起点下拉里"1F Lobby"这样名字里已带楼层的，就不再接楼层后缀。中文 `short` 汉字之间不留空格（"四层"），汉字与数字之间留一个（"4 层"，§5）。
- 想让句子说"二层"而不是"2 层"：把 `short.cn` 设成 `二层`，一处改，句子、钮、位置行同变。

---

## 5 中日韩—拉丁空格 / CJK–Latin spacing

1. **规则**：汉字与相邻的拉丁字母、数字之间加**一个空格**，双向。在句子**组装完的最后一刻**做（生成句子用 `EVK.spaced(str)`；静态文案手写同样规则）。
```js
function spaced(t){ return t
  .replace(/([\u4e00-\u9fff])([A-Za-z0-9])/g, "$1 $2")
  .replace(/([A-Za-z0-9])([\u4e00-\u9fff])/g, "$1 $2"); }
```
| 之前 | 之后 |
|---|---|
| 走到301门口 | 走到 301 门口 |
| 在01号展位 | 在 01 号展位 |
| 走楼梯上到2层。 | 走楼梯上到 2 层。 |
| 第3步，共4步 | 第 3 步，共 4 步 |
| 约28米 | 约 28 米 |
| Echo在01号 | Echo 在 01 号 |
| 凯斯特机器人（204 · 01）出发 | 不变（全角括号、标点两侧不加） |

2. 范围可按场馆扩展：假名 `\u3040-\u30ff`、扩展 A `\u3400-\u4dbf`、带变音的拉丁 `\u00C0-\u024F`。只作用于**纯文本**（先于 HTML 转义），不碰 URL、属性、代码。
3. **构建期反向清理**：模板里的换行会在两个汉字之间变成可见空隙，生成 HTML 时删除两个 CJK 字符间的空白（跳过 `<pre>`、`<script>`、`<textarea>`）。
4. 例外——**锁定件**：大数字 + 小单位（`8所`、`03 层楼`）靠字号差排版，不加空格。
5. CSS：`line-break: strict`；拉丁名称用 `word-break: keep-all`（中文名不用，floor F10）；`text-autospace: normal` 可作渐进增强（与字面空格不会叠加）；`<html lang>` 写对；中文副行字距 +0.02–0.12em，行高 1.7–1.85。
6. 测：断言整句 `走楼梯下到 1 层。`；标题也要过 `spaced`（`走到 203`，不是 `走到203`）；`spaced` 对表中每行幂等。

---

## 6 搜索 / Search

### 6.1 规范化：一份函数，到处共用
引擎自带：`EVK.search.normalize(s)`（全角转半角 → NFKC → 小写 → 去变音 → 去掉所有空白、标点、符号）。原站只有最小版 `trim().toLowerCase().replace(/[\s\-_.,'’()·–—\/]/g, "")`，套件在它之上加了后四步。
构建期（Python）、列表过滤、地图搜索、404 / 路由器**同一实现**，非 JS 端逐例对拍并有测试：`kestrel robotics` = `Kestrel-Robotics` = `kestrelrobotics`；`3-02` = `302`；中文名、缩写都命中。繁简不互通（把另一种写法加进 `fields`）。
构建期还要：规范化每个别名；别名之间或与保留名（`map`、`about`…）冲突 → 报错；**纯数字别名 → 报错**（数字永远指房间 / 展位）。
换法：拼音首字母；模糊匹配；服务端。

### 6.2 排名：看名字解释了多少查询
```js
var s = EVK.search.create(venue.entities, { groups: GROUPS, rooms: venue.floors });
s.query("kestrel") // → [{ entity, score, why }, …] 最好的在前；s.best(q) → 第一个实体或 null
```
分数越大越好：**4** 整名相等（`why:"name"`）· **3** 名称前缀 · **2** 其他键前缀（组词 `group`、房号 `room`、`tag`、`id`、`booth`）· **1** 子串 · **0.5** 多个词各自命中（AND）；同分按传入的场地原序，列表不重排。空查询 = 全部、原序、score 0；`best("")` 为 null。名称键 = 中英文名、`short`、去掉开头 The 的英文名、多词英文名的首字母（`ttr`）、`fields` 里的字段；房号键 = 房间或区的 id / label / 名字，"房号+展位"（`20301`、`203-01`）；裸展位号只在全场唯一时才是键。
**平铺的选择列表按分数排序；分组网格就地过滤、不重排、空组隐藏**（两种形状两种行为：用 `query()` 的结果当可见集合）。Enter 取 `best()`。
换法：模糊分；热度 / 最近；按字母；分组结果带标题（"展商 / 房间 / 类别"）。

### 6.3 组词：人是按类别找的
手写一小层同义词，让"工程""女校""市中心"这类说法有结果（换法：分面 chips；自动标签；自然语言提问）。结构（`EVK.search` 的 `groups` 直接吃这个形状）：
```json
{ "groups": [{ "words": ["机器人","robot","robotics","ai"], "tags": ["robotics"] }, { "words": ["首层"], "floors": ["1F"] }],
  "ambiguous": ["riverside","河滨"], "reserved": ["map","about"] }
```
一组按 `ids` / `tags` / `rooms` / `floors` 圈出实体（另可写成 `[[words, ids]]` 或 `{词: ids}`）。
- 每组中英文 + 缩写同义词都列；原站 21 组，覆盖类型（理工、文理、女校、公立）、地区 / 城市 / 国家、联盟。别的活动：展商品类、展厅年代、会议议程轨道。
- **歧义词**（同时指多个实体的城市、地名）**从别名表移除，只留作组词**——搜得出列表，但不会变成单实体快捷链接。
- 与 `venue.json` 的 `entities[].tags` 对接：标签进 `data-keys`，不进 `data-names`。
- 起步页（`ux-contracts.md` §17）从 `venue.json` 的 `x-groups` 读这一层（数组，每项 `{words, tags, ids, rooms, floors}`）；不写也行，标签和房号本来就搜得到。

### 6.4 占位符教能力
公式：`{名称例}、{缩写例}、{类别例}、{位置码例}…`，最多 4 个，**全取自真实数据**，以省略号收尾；名称类与类别类之间可用"，或"分开。
原站：路线表单 `校名、缩写、藤校、加州、203…`；首页 `英文名、中文名、缩写，或藤校、加州、理工…`。英文（本套件补充）：`Name, short name, category, room — e.g. Echo, craft, 203…`。
不要只写"搜索…"。**例子是人会敲的东西**：真实的名称，一两个，用主语言写（`lead=zh` 取中文名，`lead=en` 取短名或英文名），名字太长的跳过，没有名字可用时取一个房号；**不拿标签 id 当例子**（`night`、`x-groups` 的键是内部的词，不是人会敲的），也不在中文页里冒出英文标签。汉字之间无空格、汉字与拉丁 / 数字之间一个空格（§5）：起步页的中文模板是 `名称、类别、房号，例如{ex}…`，`{ex}` = 一两个真实名称用顿号连起来（演示场地里是"海带生物塑料、盐风风筝"这样的）。换法：轮播示例；输入框下的示例 chips；只在一次无结果后才出示例行。

---

## 7 状态与错误文案 / States and error copy

公式：**发生了什么 + 下一步**。无错误码、不责怪、不用"哎呀"。

| 场景 | 中文（原站） | English（本套件补充） |
|---|---|---|
| 无网络 | 网络连接失败，请稍后再试。 | Can't reach the network. Please try again in a moment. |
| 频率限制 / 服务忙 | 操作太频繁了，请稍等一会儿再试。/ 服务器正忙，请稍后再试。 | Too many tries. Please wait a moment. / The server is busy. Please try again shortly. |
| 其他 | 出错了，请稍后再试。 | Something went wrong. Please try again. |
| 功能启动失败 | `{功能}暂时无法使用，请稍后刷新页面。` | `{Feature} is unavailable right now. Please refresh the page.` |
| 搜索无结果 | 没有找到匹配的学校。可以试试英文缩写、中文简称或教室号。 | No matches. Try an abbreviation, a short name, or a room number. |
| 位置未公布 | To be announced / 展位位置将在活动前公布 | 同左（双语块） |
| 路线算不出（本套件补充，原站静默） | 暂时算不出这条路。换个起点试试，或到下方名录里看展位位置。 | We couldn't work out this route. Try another starting point, or find the booth in the directory below. |
| 无 JS | 楼层图和路线导航需要开启 JavaScript；下方的展区名录列出了每所学校的教室和展位号。 | The floor map and directions need JavaScript. The directory below lists every room and booth. |
| 示例数据 | 示例数据：楼层、展位和摘要均为演示内容，不代表实际安排。 | Sample data: floors, booths and summaries are for demonstration only. |

诚实：近似用"约"，未定写"待定 / TBD"，示意图写"示意"；不可撤销的操作，后果写在按钮正下方。起步页照此办理：`venue.json` 的 `event {name, date, time, place, note}` 缺哪项就印"待定 / TBA"，`x-schematic` 一设就出示意横幅（词在它的 UI 词典 `sample_tag` / `sample_text`）并加 `noindex`。

---

## 8 链接语法 / Link grammar

参数名可以改，**语义、优先级、校验不能省**；最终写进 `DESIGN.md`。

| 参数（原站） | 含义 |
|---|---|
| `s=<slug>` | 高亮该实体的展位并打开其房间弹层 |
| `r=<房间>` | 打开房间弹层 |
| `f=<楼层>` | 只显示一层 |
| `to=<slug>` | 打开路线面板并选好目的地，只问起点 |
| `from=room:203` / `lobby:2F` / `entrance:1F` / `area:WEST`（配 `to`） | 立即开始路线；值是带命名空间的键（`wf.starts()` 的 `id`），与下拉 `value`、`localStorage` 通用；`room:<区 id>` 同样认得 |
| `tour=<id>&stop=<n>` | 从第 n 站（**1 起**）走主题路线 |
| `nav=tour` / `nav=school` | 以该模式打开路线面板 |
| `g=<组键>`（首页，起步页） | 只显示一组：`event.group_by` 的组（楼层 id、标签 id 或房间 id）；不认识的键忽略（UR-2） |

- **优先级**（代码顺序）：`tour` > `to`(+`from`) > `nav` > `s` > `r` > `f` > 无；出现路线类参数时先清掉初始的 `s` 目标。
- **校验**：每个以 URL 值为键的查找用自有属性检查：
```js
function has(o,k){ return k!=null && Object.prototype.hasOwnProperty.call(o,k); }
```
- **同步**：路线运行时 `history.replaceState(null,"",path+"?"+query+hash)`，不污染历史；保留 hash；结束只清自己的参数；步骤序号不写进地址。
- **地址永久**：slug 一经印刷（二维码）冻结；拼错的最后一段由路由器规范化后查别名表，命中就 `location.replace(dest + search + hash)`；站内链接根绝对。

---

## 9 播报与替代文字 / Live-region sentences and alt text

**播报**：视觉隐藏的 `aria-live="polite"`，每次**一句**，位置在前。

| 场合 | 中文 | English |
|---|---|---|
| 步骤变化（原站） | `第 {i} 步，共 {n} 步：{该步中文句}` | `Step {i} of {n}: {sentence}` |
| 总览（原站） | `{实体名}，全程约 {N} 米，共 {M} 步。` | `{Entity}, about {N} m in total, {M} steps.` |
| 换到下一站（本套件补充） | `第 {j} 所，共 {m} 所：{实体名}。` | `Stop {j} of {m}: {Entity}.` |
| 选中房间（本套件补充） | `已选中 {房间}，{k} 个展位。` | `{Room} selected, {k} booths.` |
| 搜索结果（本套件补充，停顿 ~300 ms） | `{k} 个结果。` / `没有找到匹配的结果。` | `{k} results.` / `No matches.` |

规则：一句；位置在前；不播地图相机动作、动画进度、倒计时；语言与页面 `lang` 一致。

**替代文字 / aria-label**：公式 = **是什么 + 它传达的事实 + 怎么操作 + 等价的文字入口在哪**。
- 地图画布：`立体楼层导览：可以拖动旋转、双指缩放，方向键也可以操作。点房间或标记查看展位，下方的展区名录列出全部展位。` / `3D floor guide. Drag to rotate, pinch to zoom, or use the arrow keys. Tap a room or marker to see its booths; the directory below lists every booth.`
- 实体页小图：`{楼层}立体图：{实体}的展位在{房间}，{no} 号，已圈出。可以拖动旋转。` / `{Floor} 3D view: {entity} is in {room}, booth {no}, circled. Drag to rotate.`（不要只靠颜色，原站写"红圈"）
- 阅读导航：`报告目录，正在读第 {i} 部分，共 {n} 部分` / `Contents, reading part {i} of {n}`
- 号牌图：`alt` = 房间 label。装饰性 SVG：`aria-hidden`。

---

## 10 语气与标签词表 / Voice and label table

**EN 一到两个词，CN 是口语化的回答，不是直译。** 全局导航用正式名，需要的地方用口语名，英文词同一个。

| 用在 | English | 中文（原站） |
|---|---|---|
| 全局入口 | Directions | 路线导航 |
| 实体页 / 房间弹层 | Directions | 怎么走 |
| 主题入口 | Themed Routes | 主题路线 |
| 表单 | I am at · Go to | 我现在在 · 去哪所学校 |
| 模式切换 | To a School · Themed Routes | 去某所学校 · 主题路线 |
| 面板 | Close · Overview · Back · Next | 关闭 · 全览 · 上一步 / 上一所 · 下一步 / 下一所 |
| 面板链接 | School page · Change route | 学校页 · 重新选择 |
| 地图 | Drag to rotate · Reset | 拖动旋转 · 复位 |

- 统计行用量词补全数字（`3 Floors | 3 层`、`52 | 所大学`）；页标题模板 `{页名}｜{短标题}`。
- 换法：俏皮；纯图标；第二人称帮助式；严格机构式。通用化时把"学校"换成项目的实体词，在 `DESIGN.md` 列一张"词 → 词"表。

---

## 11 检查清单 / Checklist
- 每步有动作、目的地、距离（带"约"）；可选从句只在有信息时出现；中英文动作和目的地一致；开放区 / 走廊的句子里没有"门"，英文行没有汉字。
- `spaced` 幂等；楼梯名同层互异；楼层串在控件、位置行、步骤句里一致（都取 `floors[].short`），任何标题里没有同一串印两遍；英文名没有开头的 the（实体名除外），读一遍"From the …"、"Follow the …"、到达句。
- 左 / 右只在方向有定义时出现；同房间和大堂起点没有转向词。
- 占位符例子取自真实数据；别名无冲突无纯数字；歧义词只搜不跳。
- URL 查找走 `has()`；`replaceState`；hash 保留。
- 错误句含"下一步"；播报每次一句、位置在前；画布与小图的 label 说清事实、操作、文字入口。
