---
name: ai-code-onboarding-checklist
description: 当拿到一段 AI 生成的代码，还没决定要不要信、要不要跑、要不要往上继续加东西时使用。先做一遍客观体检：行数与嵌套深度、有没有测试、有没有硬编码密钥或遗留 TODO、依赖是不是真实存在、有没有危险调用（eval/exec、shell=True、递归删除、反序列化、提权、外发网络，按正文给的 grep 模式逐类查）；再给风险评级和下一步动作。老实写明它查不了算法正确性——体检通过不等于代码是对的。回答里文字、事实和代码混在一起时先用 ai-answer-triage 分级；只审相对已有代码的一份改动用 ai-diff-review-protocol。
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
display_name: AI 代码入库体检
outputs:
  - chat
max_rounds: 20
suggest_hint: 跑这段 AI 写的代码之前，先用「AI 代码入库体检」查密钥、依赖和测试覆盖
---

# ai-code-onboarding-checklist

## Purpose

Use this skill when someone has received code from an AI system and wants a **first-pass safety and maintainability triage** before deeper review.

This skill answers questions like:

- Is the code small enough to review directly, or already too tangled?
- Did the AI leave obvious placeholders, TODOs, or unfinished branches?
- Are there hard-coded secrets, tokens, or suspicious credentials?
- Do declared dependencies appear real and named consistently?
- Does it contain calls that can do damage as soon as it runs: eval/exec, shell commands, recursive deletes, unsafe deserialization, privilege changes, outbound network calls?
- Are there tests, examples, or any executable proof that the code was meant to work?

It does **not** claim algorithmic correctness, business correctness, or production readiness.

## When to use

Use this skill when the user says things like:

- “AI 帮我写了这段代码，先帮我看看能不能信。”
- “Before I run this, give me an objective sanity check.”
- “Tell me what is mechanically risky in this generated repo.”
- “I want a checklist review, not a full rewrite.”

## When not to use

Do **not** use this skill as the main tool for:

- proving the algorithm is correct;
- reviewing only a patch or diff against an existing codebase;
- auditing whether AI-generated tests are meaningful;
- validating external factual claims made alongside the code;
- sorting a whole AI answer in which the code is only one part among explanations, facts and advice.

Prefer neighboring skills for those cases:

- `ai-diff-review-protocol` for patch-focused review;
- `ai-generated-test-auditor` for test-quality audit;
- `ai-output-fact-checker` for claims about libraries, papers, versions, or commands;
- `ai-answer-triage` to sort a mixed answer first; the code blocks it marks "test first" come back here.

## Required inputs

Ask for or infer the smallest workable set:

1. **Scope**: file, folder, or pasted snippet to inspect.
2. **Language / stack** if obvious from filenames is not enough.
3. **Intended use**: toy experiment, homework draft, internal tool, shipping product, etc.
4. **Trust decision needed now**:
   - safe to read only
   - safe to run locally
   - safe to build on
   - safe to merge

If one of these is missing, continue with a best-effort review but mark the missing field explicitly.

## Output contract

Return a compact report with these sections, in this order:

1. **Verdict** — one of:
   - `read-only OK`
   - `review before run`
   - `high-risk before run`
   - `not enough evidence`
2. **Findings table** with these rows:
   - size / complexity
   - test evidence
   - placeholders / TODOs
   - secrets / credentials
   - dependency reality
   - config & environment assumptions
   - dangerous calls
3. **Top 3 concrete risks**
4. **Next safest action**
5. **Known blind spots**

Keep judgments evidence-based. Quote filenames, symbols, or exact snippets when possible.

## Review procedure

### Step 1 — Frame the task

Identify:

- what artifact is being reviewed;
- whether it is standalone or partial;
- whether the user wants permission to run it, extend it, or merge it.

If the artifact is only a fragment, say so early. Fragments often fail checks that full projects would pass.

### Step 2 — Run objective intake checks

Check the following items in order.

#### A. Size and structure

Measure or estimate:

- total files in scope;
- total non-blank, non-comment lines when practical;
- unusually long files;
- unusually deep nesting or callback chains;
- duplicated blocks or near-copy-paste sections.

Risk signals:

- one file trying to do everything;
- abrupt style shifts suggesting stitched-together generation;
- very large functions with vague names;
- repeated branches differing only by constants.

#### B. Test evidence

Look for any of:

- dedicated test files;
- runnable examples;
- sample inputs/outputs;
- assertions outside production code;
- CI hints or documented verification steps.

If no test evidence exists, say that clearly. Absence of tests is not proof of failure, but it lowers trust sharply.

#### C. Placeholders and unfinished edges

Search for signs such as:

- `TODO`, `FIXME`, `XXX`, `HACK`, `placeholder`, `stub`, `mock`;
- empty exception handlers;
- `pass`, `return null`, `return None`, `throw new Error("not implemented")`, or equivalent unfinished branches;
- comments that promise behavior the code does not implement;
- dead parameters that are accepted but never used.

Distinguish between harmless future work and blockers to safe execution.

#### D. Secrets and credential handling

Look for:

- API keys, tokens, private keys, JWT-like blobs;
- passwords, DSNs, webhook URLs, or service-account JSON content;
- hard-coded emails, phone numbers, or internal endpoints that should probably be externalized.

If a string merely looks secret-like but cannot be confirmed, label it `suspected secret`, not `confirmed secret`.

#### E. Dependency reality

Check whether the code references libraries, packages, commands, or services that appear consistent with the stated stack.

Review for:

- imports that do not match the declared dependency manifest;
- packages that look misspelled or invented;
- a package name that exists on the registry but may not be the package the code expects: names that AI tools invent get registered by other people. Existing is not the same as trustworthy; note the first-release date, source repository, maintainers and download counts, or hand the check to `ai-output-fact-checker`;
- APIs used as if copied from a different version;
- framework assumptions with no setup instructions;
- network services, databases, or environment variables required but never documented.

If the environment is missing, downgrade confidence rather than guessing.

#### F. Config and execution assumptions

Extract assumptions about:

- OS;
- runtime version;
- environment variables;
- required files or directories;
- ports, paths, permissions, or external services.

Call out any assumption that would make “just run it” unsafe or misleading.

#### G. Dangerous calls

Look for calls that can do damage the moment the code runs, whether or not the logic is right. Run these patterns over the scope (for pasted code, search the pasted text the same way), then open every hit and read it in context:

```bash
S=path/to/scope   # the file or folder under review
grep -rnE '\b(eval|exec)\s*\(|new Function\s*\(|__import__\s*\(' "$S"   # eval / exec
grep -rnE 'shell\s*=\s*True|os\.(system|popen)\s*\(|child_process|execSync\s*\(|\|\s*(sudo\s+)?(ba|z)?sh\b' "$S"   # shell execution, curl | sh
grep -rnE 'rm\s+-[a-zA-Z]*[rR]|rmtree\s*\(|rimraf|fs\.(rm|rmdir)(Sync)?\s*\(|-delete\b|\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b' "$S"   # recursive delete
grep -rnE 'pickle\.loads?\s*\(|dill\.loads?\s*\(|marshal\.loads?\s*\(|shelve\.open\s*\(|yaml\.(unsafe_)?load(_all)?\s*\(|jsonpickle|torch\.load\s*\(|joblib\.load\s*\(|allow_pickle\s*=\s*True|ObjectInputStream|unserialize\s*\(' "$S"   # deserialization
grep -rnE '\bsudo\b|\bset(e|re|res)?[ug]id\b|chmod\s+(-R\s+)?0?777|chmod\s+[ugoa]*\+[rwx]*s|0o?777|--privileged' "$S"   # privilege escalation
grep -rnE 'requests\.(get|post|put|patch|delete|request)\s*\(|urlopen\s*\(|http\.client|httpx\.|aiohttp|socket\.(socket|create_connection)|fetch\s*\(|axios|XMLHttpRequest|WebSocket|\bcurl\s|\bwget\s|smtplib|ftplib|paramiko' "$S"   # outbound network
```

A hit is serious when:

- **eval / exec**: the evaluated string contains anything the program does not fully control: user input, file content, a network response, a downloaded setting.
- **shell execution**: the command string is assembled (f-string, `+`, `format`, template literal) from arguments, file names or input, or a download is piped into a shell (`curl … | sh`).
- **recursive delete**: the target path is computed or comes from input, or could resolve to `/`, `~` or the project root.
- **deserialization**: `pickle`, `marshal`, `dill`, `joblib`, `torch.load`, `yaml.load` without `Loader=yaml.SafeLoader`, or Java/PHP object streams read data someone else can write: a download, an upload, a shared cache, a user-supplied file.
- **privilege escalation**: `sudo`, setuid/setgid, `chmod 777` or `+s`, `--privileged` containers, anything that runs with or hands out more rights than the task needs.
- **outbound network**: the destination is not explained by the stated purpose, or the call sends local data out (files, environment variables, tokens).

The patterns are a net, not a verdict. They also match harmless code (JavaScript `RegExp.exec`, a local function named `fetch`, `rm -r` inside a README) and miss aliases (`from pickle import loads`). Read each hit before labelling it.

Report each hit as `path:line — signal — the call with secrets redacted — where the risky argument comes from`, labelled:

- `confirmed`: you read it, it runs on the normal path (no flag, no confirmation prompt), and one of the conditions above holds;
- `suspected`: the pattern matched but you could not trace the argument or the code path;
- `not found`: the patterns ran over the whole scope and nothing matched;
- `not checked`: the patterns could not be run over the whole scope; say which part was missed.

An outbound call that is the stated purpose (a scraper fetching its target) is recorded as expected, with its destination, not as a risk. Hits that appear only in comments, docs or test fixtures are listed but do not raise the verdict by themselves.

### Step 3 — Rate risk

Map findings to one verdict:

- **`read-only OK`**: no obvious secrets, no severe placeholders, no dangerous calls beyond expected ones, assumptions are small and visible, scope is modest.
- **`review before run`**: code may be salvageable, but missing tests, unclear dependencies, partial placeholders, or `suspected` dangerous calls make execution risky.
- **`high-risk before run`**: likely secrets, invented dependencies, misleading setup, obviously unfinished critical paths, or any `confirmed` dangerous call from G. One confirmed dangerous call is enough, even when every other row is clean.
- **`not enough evidence`**: scope too incomplete to judge responsibly.

### Step 4 — Recommend the next action

Give the smallest safe next step, for example:

- “Read these two functions manually before running anything.”
- “Stub the missing environment variables and run only unit tests.”
- “Verify these three dependencies exist before install.”
- “Do not execute; first remove hard-coded credential material.”
- “Do not run until `pickle.loads` no longer reads data downloaded from the settings host.”

## Deterministic checks this skill should prefer

Whenever the environment allows, prefer objective checks for:

- line counts;
- file counts;
- longest-file identification;
- obvious nesting-depth heuristics;
- `TODO` / `FIXME` / `not implemented` markers;
- secret-pattern regex checks;
- the dangerous-call patterns in G;
- dependency-manifest presence and name matching;
- test-file presence by filename convention.

When tooling is unavailable, perform the same checklist manually and label each item as:

- `confirmed`
- `suspected`
- `not found`
- `not checked`

## Guardrails

- Do not say the code is “correct” just because it looks tidy.
- Do not say a dependency is fake unless you have direct evidence.
- Do not invent test coverage from comments or examples.
- Do not execute untrusted code automatically.
- Do not expose secrets in the report; redact them.
- If the user asks whether to merge, state clearly that this skill is only an intake screen, not a full code review.

## Failure modes to avoid

Bad review patterns:

- praising code quality without citing evidence;
- confusing “no tests found” with “tests definitely do not exist” when scope is partial;
- treating a demo script as production-safe;
- ignoring environment assumptions because the code itself is short;
- burying the only real blocker under a long generic checklist.

## Handoff guidance

Escalate after this skill when needed:

- to `ai-diff-review-protocol` if the real question is whether a change is safe relative to an existing baseline;
- to `ai-generated-test-auditor` if tests exist but may be hollow;
- to a language- or framework-specific debugging skill if the user wants fixes rather than triage.

## Minimal example

**User ask:** “AI 写了个 Python 小工具给我抓网页，能直接跑吗？”

**Good response shape:**

- Verdict: `review before run`
- Findings:
  - size / complexity: small single-file script
  - test evidence: none found
  - placeholders: one `TODO` in retry branch
  - secrets / credentials: no confirmed secret, but cookie header hard-coded
  - dependency reality: `requests` plausible; browser-cookie import unclear
  - config assumptions: requires network access and target-site cookies
  - dangerous calls: `requests.get` to the target site only (expected, it is the purpose); no eval/exec, shell, delete, deserialization or privilege hits
- Top risks:
  1. hard-coded cookie material
  2. no proof of retry/error-path behavior
  3. dependency/setup unclear
- Next safest action: remove cookies, verify imports, run only against a throwaway target
- Blind spots: no runtime execution, cannot confirm scraper correctness

## 变更记录 / Changelog

| 版本 | 日期 | 变更 | 类型 |
|---|---|---|---|
| 0.2.0 | 2026-09-26 | 补上 description 承诺却没有的危险调用检查：新增 G 节（六类 grep 模式、何时算严重、confirmed/suspected 标注），Findings 表加 dangerous calls 一行，确认的危险调用直接评 high-risk before run；E 步补"包名存在不等于可信"；与 ai-answer-triage 互相点名 | minor |
| 0.1.0 | 2026-08-30 | 初始版本 | minor |
