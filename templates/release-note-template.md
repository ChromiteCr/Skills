---
template: release-note
version: 0.1.0
---

# Release Notes — v<version>

日期：YYYY-MM-DD · 层级：Library / Skill / Workflow · 类型：major / minor / patch

版本规则见 [VERSIONING.md](../VERSIONING.md)。

---

## 摘要 / Summary

一到三句话：这个版本带来了什么变化。面向使用者，不是 commit 日志。

## 新增 / Added

- `<skill-name>` (`0.1.0`) — 一句话用途

## 变更 / Changed

- `<skill-name>` `0.1.0 → 0.2.0` — 改了什么，对使用者的影响

## 修复 / Fixed

- ...

## 破坏性变更 / Breaking

**有破坏性变更时此节必填**，并说明迁移方式。

| 变更 | 影响 | 如何迁移 |
|---|---|---|
| ... | ... | ... |

无则写「无」。

## 弃用 / Deprecated

| skill / 能力 | 替代方案 | 计划移除版本 |
|---|---|---|
| ... | ... | ... |

## 验证 / Verification

- [ ] `./scripts/validate.sh` 通过
- [ ] `claude --plugin-dir "$(pwd)"` 从干净会话加载正常
- [ ] 新增/变更 skill 的用例已运行

## 升级说明 / Upgrade notes

使用者需要做的动作；无则写「无需操作」。
