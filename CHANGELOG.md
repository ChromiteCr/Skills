# CHANGELOG

Library 级变更记录。单个 skill 的变更记在各自 `SKILL.md` 末尾的「变更记录」小节。
Library-level changes only; per-skill changes live in each `SKILL.md`.

递增规则见 [VERSIONING.md](VERSIONING.md)。最新的在最上方。

## 0.3.0 — 2026-08-04

`study-planning` 第一批建成，新增 6 个 skill（均 `0.1.0` / draft），该集合从 1 个补齐到 7 个：

- `deadline-to-study-plan` — 从截止日倒推出**有交付物**的阶段性节点。不排满、不编造截止日、不给「每天学两小时」这类无法验收的任务。
- `weekly-study-review` — 基于实际完成情况而非感受做周复盘，产出复盘文档 + 下周调整动作。判据只有一条：下周会因此做什么不一样的事；说不出就如实说这次复盘没有产出。
- `activity-profile-builder` — 把口述的活动经历追问成结构化档案。只记录学生说出口的内容，成果为空就留空，级别按事实判定不往高了写——背景注水正是从这一步开始的。
- `reflection-interviewer` — 一次一个问题的 STAR 访谈，产出保留原话问答的反思资产，并提案经历之间的关联边。取代运行时里写死的六题模板：写死的模板只能问同样的六个问题，而访谈的价值恰恰在于顺着回答追问。
- `activity-list-optimizer` — 把已写好的活动描述压进 Common App 字符限额，每改一版都用工具重新数字符（表单按 UTF-16 计，emoji 占 2 格）。**压缩学生已写出的内容是编辑，在空白处替他写是代写**，本 skill 只做前者。
- `application-timeline-builder` — 从各校截止日倒推申请季节点并换算北京时间。未核实的截止日一律不猜，要求先去官网确认。

这一批统一守住一条边界：**只整理与追问学生已有的内容，不代写应由学生本人产出的申请材料**；所有写入都走提案确认。

## 0.2.0 — 2026-08-03

- 新增 skill `admissions-reader`（`skills/study-planning/admissions-reader/`，`0.1.0` / draft）：以顶尖大学招生官视角通读学生档案与经历，只读不写。
- frontmatter 增加一组**可选**的运行时扩展键，供 StudyNest 这类 SKILL.md 运行时读取：`display_name`、`capabilities`、`optional_capabilities`、`outputs`、`max_rounds`、`suggest_hint`。这些键不进必填集合，`scripts/validate.sh` 不拒绝额外键，Claude Code 也忽略未知键——同一份 SKILL.md 因此在两边都能用，不需要 fork 格式。
