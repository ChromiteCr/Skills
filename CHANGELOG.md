# CHANGELOG

Library 级变更记录。单个 skill 的变更记在各自 `SKILL.md` 末尾的「变更记录」小节。
Library-level changes only; per-skill changes live in each `SKILL.md`.

递增规则见 [VERSIONING.md](VERSIONING.md)。最新的在最上方。

## 0.2.0 — 2026-08-03

- 新增 skill `admissions-reader`（`skills/study-planning/admissions-reader/`，`0.1.0` / draft）：以顶尖大学招生官视角通读学生档案与经历，只读不写。
- frontmatter 增加一组**可选**的运行时扩展键，供 StudyNest 这类 SKILL.md 运行时读取：`display_name`、`capabilities`、`optional_capabilities`、`outputs`、`max_rounds`、`suggest_hint`。这些键不进必填集合，`scripts/validate.sh` 不拒绝额外键，Claude Code 也忽略未知键——同一份 SKILL.md 因此在两边都能用，不需要 fork 格式。
