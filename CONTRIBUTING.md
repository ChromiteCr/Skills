# Contributing

这是个人维护的仓库：改动直接提交到 `main`，不走 PR 流程。流程尽量短，但提交前的校验不能省。
A personal repository: changes are committed straight to `main`. The process is short; the checks before each commit are not optional.

## 1. 基本规则 / Ground rules

- 一次提交只做一件事：新增一个 skill、修改一个 skill、或一次文档/脚本调整。一批修复合成一次提交时，提交说明逐项列出。
- **提交前必须跑 `./scripts/validate.sh`，不通过不提交。** 建议启用仓库自带的 pre-commit hook，让 git 每次替你跑（每个克隆启用一次）：`git config core.hooksPath scripts/git-hooks`。
- 不提交凭据、私有端点或个人数据。用户特定值走插件 user configuration。

## 2. 流程 / Workflow

```text
改动 → 本地校验 → 对照第 5 节自查 → 提交 → 需要发版时按 VERSIONING.md 第 5 节
edit → validate locally → self-check (section 5) → commit → release per VERSIONING.md §5
```

```sh
./scripts/validate.sh                 # 结构、清单、frontmatter、索引、引用、共享副本
./scripts/run-selftests.sh <skill>    # 改了脚本时：跑该 skill 脚本的 --selftest
claude --plugin-dir "$(pwd)"          # 从干净会话加载一次，确认 skill 真的被识别
```

`validate.sh` 强制检查清单里可机检的部分：目录结构；`plugin.json` 的 `skills` 列出了每个分类目录（Claude Code 只扫 `skills/` 的直接子目录，漏列的分类整个不加载）；frontmatter 合法（键从行首写起）、description 带中文触发语、没有与插件清单冲突的 `license`；`tests/cases/<name>.md` 存在且非空，skill 目录里没有第二份测试；在 `SKILL_INDEX.md` 与 `README.md` 中登记，索引的优先级、状态、版本三列与 frontmatter 一致；`../` 引用的共享文件和兄弟 skill 文件真实存在；共享代码的各份副本逐字节相同；`skills/` 以外没有 SKILL.md。脚本不通过就不要提交。

## 3. 新增 Skill / Adding a skill

1. 创建 `skills/<category>/<skill-name>/SKILL.md`，全部小写 kebab-case。新开的分类同时加进 `.claude-plugin/plugin.json` 的 `skills` 列表。
2. 从 `templates/skill-template.md` 起草；SKILL.md 保持简洁。
3. 填写 metadata：`name` / `category` / `version` / `status` / `priority` / `compatible_agents`。
4. 模板、参考资料、确定性脚本放在同一 skill 目录内，按需加载。脚本带 `--help` 与 `--selftest`。
5. 在 `tests/cases/` 添加至少一个可重复用例。
6. 在 `SKILL_INDEX.md` 和 `README.md` 登记该 skill 并简要说明功能。

### 3.1 运行时扩展键 / Runtime extension keys

除必填键外，frontmatter 可以带一组**可选**扩展键，供把 SKILL.md 当作可执行规格来跑的运行时读取（目前是 nestudy）。校验脚本不拒绝额外键，Claude Code 也忽略未知键，所以**同一份 SKILL.md 在两边都能用，不需要 fork 格式**。不写这些键的 skill 一切照旧。

| 键 | 类型 | 含义 |
|---|---|---|
| `display_name` | 字符串 | 界面上显示的名字（`name` 是 kebab-case 目录名，不适合直接展示） |
| `capabilities` | 列表 | 运行本 skill **必需**的能力名。**不写 = 只读**——这是安全默认值，作者漏写不会让 skill 拿到写权限 |
| `optional_capabilities` | 列表 | 有则更好、缺了也能跑的能力 |
| `outputs` | 列表 | 产出类型，取值限 `chat` / `document` / `canvas` / `event` |
| `max_rounds` | 整数 | 多轮工具调用的轮数上限；缺省由运行时决定 |
| `suggest_hint` | 字符串 | 运行时主动建议这个 skill 时用的一句话 |

能力名由运行时定义，不在本仓库内枚举；运行时不认识的能力名会被忽略，并在加载时报出来。

"两边都能用"指的是格式。`capabilities` 里的能力在另一个运行时里缺席时怎么办，由下一节规定。

### 3.2 只有某个运行时才有的工具 / Runtime-only tools

正文点名的工具只有某个运行时才有时（例如 nestudy 的 `check_activity_limits`、`resolve_deadline`、`propose_*`、`ask_user`，或 Claude Code 的子代理），二选一：

1. `compatible_agents` 只写有这些工具的运行时；
2. 在正文写一节「没有这些工具时（降级）」，逐个工具给出替代做法，并要求输出里如实标注"降级"。

常用替代：字符数用 `python3 -c` 按 UTF-16 码元计；日期与时区换算用 `zoneinfo`；`propose_*` 改成输出一张 Markdown 卡片，交给使用者自己保存；`ask_user` 改成在对话里直接问；子代理改成互不共享上下文的独立调用，做不到时在同一上下文里按角色依次进行，并标注"降级：各角色互相看得见"。

正文里"必须用某工具、不许手算"一类规定要写成：有工具时用工具；没有时跑降级一节给出的命令，结果标"降级计算"；任何时候都不凭眼估。

### 3.3 共享文件与共享代码 / Shared files and code

- 分类目录下的 `_shared/`（参考文档，以及 `physics/_shared/scripts/dimcheck.py`）按相对路径引用：`../_shared/<file>`，跨分类写 `../../<category>/_shared/<file>`。
- 单技能 zip 只用 `./scripts/package.sh` 打（输出 `dist/<skill>-<version>.zip`）：被引用的 `_shared` 文件和兄弟 skill 的脚本会一起放进 zip 的 `<skill>/_shared/`，引用路径随之改写。不要手工打 zip。
- 新写的、多个 skill 都要用的代码，每个用到它的 skill 各放一份相同的副本（例如摄影类的 `scripts/image_io.py`），文件里写明 `scripts/validate.sh checks that all copies have the same sha256`。校验脚本据此找出全部副本并比对 sha256；改一处，就复制到全部。

## 4. 其他组件 / Other components

- 子代理：`agents/*.md`，frontmatter 合法，工具权限最小化。
- Hooks：只写进 `hooks/hooks.json`；必须 opt-in、匹配范围窄、单独测过。Hooks 会自动执行，提交说明中写明触发条件与影响面。（`scripts/git-hooks/` 是本仓库自用的 git hook，不随插件分发。）
- MCP：`.mcp.json`，仅在认证方式与用户配置模型已写清楚时加入。
- LSP：`.lsp.json`，仅为具体语言支持需求加入。

## 5. 提交前自查 / Pre-commit checklist

- [ ] `./scripts/validate.sh` 通过
- [ ] 改过的脚本 `--selftest` 通过（`./scripts/run-selftests.sh <skill>`）
- [ ] 新增或改名的 skill 已用 `claude --plugin-dir "$(pwd)"` 从干净会话加载确认
- [ ] 改动范围与提交说明一致，无夹带的无关改动
- [ ] 新增/修改的 skill 有测试用例，且已在 `SKILL_INDEX.md`、`README.md` 登记
- [ ] version / status 已按 `VERSIONING.md` 更新（MAJOR / MINOR / PATCH），变更记录加了一行
- [ ] 工具权限最小；新增 hook 已说明触发条件
- [ ] 无凭据、私有端点或个人数据
- [ ] 教学类 skill 的安全边界明确：只做指导、解释、批判、格式化与优化，不代替使用者思考，不虚构数据或结果

## 6. 自查重点 / Review focus

优先看四件事：**权限范围**、**自动执行行为（hooks）**、**边界声明**、**测试用例是否真的能复现**。其余（措辞、结构）可以之后以 PATCH 迭代。

Check permission scope, automatic execution, stated boundaries, and reproducible tests first. Wording and structure can be iterated as PATCH releases later.
