# Contributing

本仓库通过 **Pull Request 审核** 合入变更。流程尽量短，但保留必要的安全检查。
All changes land through pull requests: short process, mandatory safety checks.

## 1. 基本规则 / Ground rules

- `main` 受保护，不直接推送；一切变更走 PR。
- 一个 PR 只做一件事：新增一个 skill、修改一个 skill、或一次文档/脚本调整。
- 分支命名：`skill/<name>`、`fix/<topic>`、`docs/<topic>`、`chore/<topic>`。
- 不提交凭据、私有端点或个人数据。用户特定值走插件 user configuration。

## 2. 流程 / Workflow

```text
建分支 → 本地校验 → 开 PR（填模板）→ 审核 → 合并（squash）
branch → validate locally → open PR → review → squash merge
```

```sh
./scripts/validate.sh
claude --plugin-dir "$(pwd)"
```

自审通过即可请求合并；自己的仓库允许自审，但**必须逐项确认下面的清单**，不能跳过。
Self-review is allowed, but the checklist below is not optional.

`validate.sh` 已经强制检查了清单里可机检的部分：目录结构、清单一致性、frontmatter 合法性、`tests/cases/<name>.md` 存在且非空、以及在 `SKILL_INDEX.md` 与 `README.md` 中的登记。脚本不通过的 PR 不要提交审核。

## 3. 新增 Skill / Adding a skill

1. 创建 `skills/<category>/<skill-name>/SKILL.md`，全部小写 kebab-case。
2. 从 `templates/skill-template.md` 起草；SKILL.md 保持简洁。
3. 填写 metadata：`name` / `category` / `version` / `status` / `priority` / `compatible_agents`。
4. 模板、参考资料、确定性脚本放在同一 skill 目录内，按需加载。
5. 在 `tests/cases/` 添加至少一个可重复用例。
6. 在 `SKILL_INDEX.md` 和 `README.md` 登记该 skill 并简要说明功能。

## 4. 其他组件 / Other components

- 子代理：`agents/*.md`，frontmatter 合法，工具权限最小化。
- Hooks：只写进 `hooks/hooks.json`；必须 opt-in、匹配范围窄、单独测过。Hooks 会自动执行，PR 中需说明触发条件与影响面。
- MCP：`.mcp.json`，仅在认证方式与用户配置模型已写清楚时加入。
- LSP：`.lsp.json`，仅为具体语言支持需求加入。

## 5. PR 检查清单 / PR checklist

提交 PR 时在描述中逐项勾选：

- [ ] `./scripts/validate.sh` 通过
- [ ] 已用 `claude --plugin-dir "$(pwd)"` 从干净会话加载测试
- [ ] 变更范围与 PR 标题一致，无夹带的无关改动
- [ ] 新增/修改的 skill 有测试用例，且已在 `SKILL_INDEX.md`、`README.md` 登记
- [ ] version / status 已按 `VERSIONING.md` 更新（MAJOR / MINOR / PATCH）
- [ ] 工具权限最小；新增 hook 已说明触发条件
- [ ] 无凭据、私有端点或个人数据
- [ ] 教学类 skill 的安全边界明确：只做指导、解释、批判、格式化与优化，不代替使用者思考，不虚构数据或结果

## 6. 审核关注点 / Review focus

审核者优先看四件事：**权限范围**、**自动执行行为（hooks）**、**边界声明**、**测试用例是否真的能复现**。其余（措辞、结构）可在合并后以 PATCH 迭代。

Reviewers prioritize permission scope, automatic execution, stated boundaries, and reproducible tests. Wording and structure can be iterated as PATCH releases after merge.
