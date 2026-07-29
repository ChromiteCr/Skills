# VERSIONING

本仓库使用三层语义化版本。全局 CLAUDE.md 中的项目版本号规则**不适用于本仓库**。
Three layers of semantic versioning. The global project versioning rules do not apply here.

## 1. 三层版本 / Three layers

| 层级 | 记录位置 | 含义 |
|---|---|---|
| **Library Version** | `.claude-plugin/plugin.json` 的 `version`（与 `marketplace.json` 条目保持一致） | 整个 Skills 仓库的版本 |
| **Skill Version** | 每个 `SKILL.md` frontmatter 的 `version` | 单个 skill 的版本 |
| **Workflow Version** | 工作流文档 frontmatter 的 `version`（如 `workflows/` 或 skill 目录内的流程文件） | 可复用工作流的版本 |

三层各自独立递增。改一个 skill 不需要动 Library Version；但**新增或删除 skill**、**改变仓库结构或模板契约**时必须动 Library Version。

## 2. 递增规则 / Increment rules

```text
0.x.x   实验 / 草稿阶段        experimental / draft
1.0.0   稳定可用版本          first stable release
MAJOR   破坏性结构变化        breaking structural change
MINOR   新增 skill 或新增能力  new skill or new capability
PATCH   措辞、示例、边界或文档修正  wording, examples, boundaries, docs
```

### 判定表 / What counts as what

| 变更 | Library | Skill |
|---|---|---|
| 新增一个 skill | MINOR | 新 skill 从 `0.1.0` 起 |
| 删除或重命名 skill | MAJOR | — |
| skill 新增一个输出段或新能力 | — | MINOR |
| skill 改写措辞、补例子、收紧边界 | — | PATCH |
| skill 改变输出格式契约、改必填输入 | — | MAJOR |
| 改模板契约（`templates/*`）或目录结构 | MAJOR | 受影响 skill 跟随 MAJOR |
| 只改 README / CONTRIBUTING / 索引 | PATCH | — |

`0.x.x` 阶段允许在 MINOR 位做破坏性变更（`0.1.0 → 0.2.0`），但需在 PR 描述里写明。

## 3. status 字段 / Status

| status | 含义 | 版本区间 |
|---|---|---|
| `draft` | 结构在动，随时可能重写 | `0.x.x` |
| `beta` | 结构稳定，仍在调措辞和边界 | `0.x.x` |
| `stable` | 可依赖，破坏性变更需 MAJOR | `>= 1.0.0` |
| `deprecated` | 保留但不再维护，说明替代方案 | 任意 |

`status: stable` 要求版本 `>= 1.0.0`，反之 `>= 1.0.0` 不允许 `draft`。校验脚本会检查这一条。

## 4. 变更记录 / Changelog

- Library 级变更记入 `CHANGELOG.md`（首次发布时创建）。
- Skill 级变更记在该 skill 目录内的 `CHANGELOG.md`，或在 `SKILL.md` 末尾的「变更记录」小节，最新的在最上方。

格式：

```markdown
| 版本 | 日期 | 变更 | 类型 |
|---|---|---|---|
| 0.2.0 | 2026-08-03 | 新增 handoff 输出段 | minor |
| 0.1.1 | 2026-07-30 | 收紧学术诚信边界 | patch |
```

## 5. 发布 / Release

发布一个 Library 版本时：

1. 确认 `./scripts/validate.sh` 通过。
2. 更新 `plugin.json` 与 `marketplace.json` 的 `version`（两处必须一致，脚本会校验）。
3. 更新 `CHANGELOG.md` 与 `SKILL_INDEX.md`。
4. 用 `templates/release-note-template.md` 写 release note。
5. 打 tag：`v<library-version>`。
