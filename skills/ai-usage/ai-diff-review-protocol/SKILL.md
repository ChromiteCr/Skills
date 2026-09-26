---
name: ai-diff-review-protocol
description: 当 AI 改完代码、要决定这份 diff 放不放行时使用。不逐行精读，按四步走查高风险点——意图是否匹配、有没有碰到边界条件、副作用面有多大、能不能回滚——每步有明确的放过与打回判据。改动文件数、增删行数、动到的迁移/锁文件/CI/配置/鉴权/测试文件和危险 hunk 先由 scripts/diff_risk.py 统计（粘贴进来的 diff 文本也能读，不需要 Git），越过固定阈值时必须人工逐段过。只有口头描述、没有改动内容时不给结论，只列要补的材料。diff 里新写的测试可不可信交给 ai-generated-test-auditor；没有基线的整段新代码走 ai-code-onboarding-checklist。
category: ai-usage/code-review
version: 0.2.0
status: draft
priority: P1
compatible_agents:
  - claude-code
  - codex
  - cursor
  - codebuddy
  - nestudy
  - generic-llm-agent
display_name: AI 改动走查协议
outputs:
  - chat
max_rounds: 20
suggest_hint: 用「AI 改动走查协议」按意图、边界、副作用、可逆性四步过一遍这份 diff
---

# AI Diff Review Protocol

## Purpose

Use this skill after an AI agent, coding assistant, or teammate proposes a code change and you need a fast but disciplined review protocol.

This skill is optimized for **reviewing a provided patch / unified diff / before-vs-after file excerpt**. It does **not** require a specific vendor, IDE, or agent platform.

The goal is not to replace deep code review. The goal is to answer four questions quickly and honestly:

1. **Intent match** — Did the change actually do what was requested?
2. **Boundary safety** — Did it touch risky areas that need slower review?
3. **Side-effect surface** — How much unrelated behavior could this change affect?
4. **Reversibility** — If this is wrong, how hard is it to back out safely?

## Use when

- You have a diff, patch, or changed-file excerpts from an AI-generated edit.
- You want a structured go / caution / stop recommendation.
- You need to focus limited review time on the highest-risk parts.

## Do not use when

- You only have a description of the change, not the change itself. Give no verdict; list the materials to provide (see *When there is no unified diff*).
- You need proof of behavioral correctness; this skill can flag risk, not prove the code works.
- The task is primarily architectural redesign rather than change review.
- The code is new and there is no baseline to diff against: use `ai-code-onboarding-checklist`.
- The only question is whether the tests in the change can be trusted: use `ai-generated-test-auditor`.

## Required inputs

Provide as many of these as possible:

- **Requested intent**: what the AI was asked to change
- **Actual change**: unified diff, patch text, or before/after snippets
- **Changed files list**: if already available
- **Known constraints**: performance, security, backward compatibility, migration, rollout, deadlines
- **Validation evidence**: tests run, logs, screenshots, benchmark notes, or "not run"

If any required input is missing, say so explicitly and downgrade confidence.

## Output contract

Return these sections in order:

1. **Verdict**: `pass`, `caution`, or `stop`. With only a prose description of the change there is no verdict (see *When there is no unified diff*).
2. **One-sentence rationale**
3. **Diff stats**: the summary from `scripts/diff_risk.py`: files changed, +/− lines, renames and mode changes, boundary files, hunk signals, new lock-file packages, the thresholds crossed, and "manual hunk-by-hunk pass: required / not required". Without a unified diff write "Diff stats: not computed (no unified diff)"; numbers counted by reading the diff are labelled "counted by hand".
4. **Risk summary**
   - intent match
   - risky boundaries touched
   - likely side effects
   - reversibility
5. **High-priority review targets** (up to 5)
6. **Required follow-up before merge/apply**, including the hunks a person must read when a manual pass is required
7. **Confidence**: high / medium / low

## Review protocol

### Step 1 — Intent match

Summarize the requested change in one sentence, then compare it against the diff.

Check:

- Is the requested scope present?
- Did the AI also change unrelated code?
- Is there evidence of over-building or under-delivering?
- Are names, comments, and tests aligned with the claimed intent?

If the change solves a different problem than requested, mark **stop**.

If most of the validation evidence is tests written in this same diff, those tests still have to earn trust: hand them to `ai-generated-test-auditor` (or apply its oracle and mutation questions yourself) before counting them as evidence.

### Step 2 — Boundary safety

Treat the following as high-risk boundaries unless proven otherwise:

- authentication / authorization
- payments / billing
- secrets / credentials / tokens
- data deletion / retention / privacy-sensitive handling
- database schema / migrations / persistence formats
- concurrency / async orchestration / retries / locks
- security controls / escaping / validation / sandboxing
- deployment, infrastructure, CI/CD, runtime config, feature flags
- public API contracts, SDK signatures, serialization formats
- core shared utilities used widely across the codebase

For each touched boundary, answer:

- What boundary was touched?
- Was the change necessary for the stated intent?
- What is the failure mode if this edit is wrong?
- What extra validation is required?

If a high-risk boundary changed without matching validation evidence, mark at least **caution**.

### Step 3 — Side-effect surface

Estimate the blast radius from the change shape.

Look for:

- many files changed for a small requested task
- edits in shared helpers, base classes, middleware, schemas, or config
- test snapshots or fixtures updated without clear explanation
- refactors mixed together with bug fixes
- renamed symbols crossing many call sites
- default behavior changes hidden behind "cleanup"
- lockfile / dependency churn unrelated to the request

Classify side-effect surface as:

- **narrow** — local behavior only
- **medium** — a few connected modules
- **broad** — shared paths or system-wide behavior

Broad surface with weak evidence usually means **caution** or **stop**.

### Step 4 — Reversibility

Judge how safely the change can be backed out.

More reversible:

- additive code behind a flag
- isolated new function or file
- no schema or data mutation
- behavior can be disabled without data repair

Less reversible:

- destructive migrations
- data rewrites
- removal of old code paths before proving the new one
- config changes that alter runtime behavior globally
- public contract changes without compatibility layer

Classify reversibility as:

- **easy rollback**
- **rollback with care**
- **hard to reverse**

Hard-to-reverse changes need explicit rollback notes before approval.

## Diff stats and thresholds (`scripts/diff_risk.py`)

Run the script on the diff before the four steps. It needs only Python 3, no Git and no packages:

```bash
python3 scripts/diff_risk.py change.diff           # a saved diff, or a pasted chat message saved to a file
git diff main... | python3 scripts/diff_risk.py     # when Git is available
python3 scripts/diff_risk.py --json change.diff     # machine-readable report
python3 scripts/diff_risk.py --selftest             # regression cases
```

It reads any unified diff text: `git diff`, `git show`, `git format-patch`, `diff -u` / `diff -ruN`, or a diff pasted into a chat together with the prose and code fences around it. It reports:

- files changed; files added, deleted, renamed or copied; binary files; mode changes (a file becoming executable, symlinks, submodules);
- additions and deletions per file and in total;
- the boundary category of every path: `migration`, `lockfile`, `deps`, `ci`, `config`, `auth`, `secrets`, `test`, `docs`, `data`, `code`;
- hunk signals on changed lines: NOT NULL without DEFAULT outside CREATE TABLE, DROP / TRUNCATE / ORM drops, assertions deleted from tests, tests skipped or focused, `shell=True`, `os.system`, a download piped into `sh`, `eval` / `exec`, recursive deletes, unsafe deserialization, privilege changes, and literals that look like credentials (values redacted);
- packages added, removed or bumped in lock files (npm, yarn, pnpm, Pipfile, poetry, uv, Cargo, pdm, composer, go.sum, Gemfile, Gradle); other lock formats are reported as not parsed;
- the thresholds it applied, whether a manual hunk-by-hunk pass is required, and which hunks to read.

Exit code 0 means no manual pass is required, 1 means a manual pass is required, 2 means the input holds no unified diff or cannot be read. If you cannot run Python, take the same numbers from the diff by reading it, apply the same table, and label the Diff stats "counted by hand".

The script and this table use the same numbers:

| Rule | Effect |
|---|---|
| 1–3 files changed | local; keep reviewing |
| 4–8 files changed | check for scope creep |
| 9+ files changed | manual hunk-by-hunk pass of every hunk |
| 200+ changed lines (additions + deletions, lock files excluded) | manual pass of every hunk, and a clearer side-effect summary |
| any `migration`, `auth`, `secrets`, `ci`, `config` or `deps` file | manual pass of that file's hunks; raise boundary risk in Step 2 |
| a lock file adds packages, or its format is not parsed | manual pass; confirm each new package is real and intended |
| any hunk signal | manual pass of that hunk |
| production code changes by 100+ lines while test lines stay under 10 % of that | ask why (no manual pass by itself) |

A manual hunk-by-hunk pass means a person reads each listed hunk (every hunk when a size rule is crossed) and says whether it belongs to the requested change. You may pre-read and annotate the hunks, but that does not replace the person's pass. Until the person confirms it, the verdict cannot be `pass`. Staying under every threshold does not make a diff safe: a one-line change to a config default can still be `stop`. Public API changes cannot be recognized from paths; Step 2 asks about them regardless.

## When there is no unified diff

- **Before/after snippets, whole changed files, or an excerpt, but no unified diff**: run the four steps on what you have. Write "Diff stats: not computed (no unified diff)", or count what you can and label it "counted by hand". Confidence is at most medium; name the files or hunks you did not see.
- **Only a prose description of the change** ("it optimised the cache and fixed a few small things"): give no verdict. Say which steps cannot run (Steps 2 and 3 need the change itself; Step 1 can only compare two descriptions) and list the smallest set of materials to provide: the `git diff` or `git show <commit>` output, the list of changed files, and whether tests, config or migrations changed. A phrase like "and fixed a few small things" is itself a scope-creep signal worth naming.

## Decision rules

Return `pass` only when all are true:

- the change clearly matches intent
- no unexplained risky boundary edits
- side-effect surface is narrow or well-justified
- rollback is easy or documented
- validation evidence is proportional to risk
- every manual hunk-by-hunk pass the thresholds require has been done by a person

Return `caution` when:

- the core idea looks right, but risk or evidence is incomplete
- the change touches shared code or config
- tests/evidence are partial
- the patch is larger than the request suggests
- a required manual hunk-by-hunk pass has not been done yet (list the hunks under Required follow-up)

Return `stop` when any of these occur:

- requested intent and actual change do not match
- hidden scope creep dominates the patch
- high-risk boundaries changed with no credible validation plan
- the change is hard to reverse and the rollout/rollback story is missing
- the reviewer cannot tell what the patch is trying to do

## Recommended response style

Be concise, specific, and operational.

Prefer:

- "This changed request parsing *and* auth middleware; only the first matches intent."
- "Rollback is hard because the migration deletes columns rather than deprecating them."
- "Need targeted checks for backward compatibility on the public JSON shape."

Avoid vague comments like:

- "Looks risky"
- "Please review carefully"
- "Might have side effects"

## Failure modes

- Confusing **large** changes with **bad** changes
- Missing hidden risk in a very small config edit
- Treating passing tests as proof of correctness
- Approving because comments sound plausible while the diff does something else
- Ignoring reversibility until after rollout

## Example mini-template

```markdown
Verdict: caution

Rationale: The patch mostly matches the request, but it also changes shared request validation and a runtime config default.

Diff stats (scripts/diff_risk.py): 3 files, +48 / -12; boundary files: config (config/defaults.yaml); hunk signals: none; new lock-file packages: none.
Manual hunk-by-hunk pass: required (config file touched): config/defaults.yaml @@ -10,4 +10,4 @@

Risk summary:
- Intent match: partial match; bug fix is present, config expansion is extra
- Risky boundaries: runtime config, shared validator
- Likely side effects: medium; all endpoints using the validator may be affected
- Reversibility: rollback with care; code can revert cleanly, but config default change needs release coordination

High-priority review targets:
1. Validator behavior for previously accepted inputs
2. Default config value and backward compatibility
3. Test coverage for invalid/edge cases

Required follow-up before merge/apply:
- A person reads the config/defaults.yaml hunk (manual pass required by the config boundary)
- Add one regression test for the original bug
- Show behavior before/after for invalid input
- Confirm whether changing the default is intentional

Confidence: medium
```

## Notes for agent implementations

- Accept diff text from any source; do not assume Git is available. `scripts/diff_risk.py` parses pasted text directly.
- If you have the change content but cannot compute objective stats (no unified diff, or no way to run Python), still run the four-step reasoning protocol, label any numbers "counted by hand", and lower confidence. If you only have a prose description, give no verdict (see *When there is no unified diff*).
- Do not claim code is correct unless validation evidence is supplied.
- Prefer quoting exact changed paths or hunks when present.

## 变更记录 / Changelog

| 版本 | 日期 | 变更 | 类型 |
|---|---|---|---|
| 0.2.0 | 2026-09-26 | 补上 description 承诺却不存在的统计脚本：新增 scripts/diff_risk.py（纯标准库，能读粘贴的 diff；统计文件与增删行、重命名与权限变化，按边界分类路径，标出危险 hunk，数锁文件新增包，给出阈值与是否必须人工逐段过，带 --selftest），输出契约加 Diff stats 一段；阈值改成脚本与正文同一张表，越线必须人工逐段过；没有 diff 时分两种：有前后片段照常走并降置信度，只有口头描述不给结论只列补材料；与 ai-generated-test-auditor、ai-code-onboarding-checklist 互相点名 | minor |
| 0.1.0 | 2026-08-30 | 初始版本 | minor |
