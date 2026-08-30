---
name: ai-code-onboarding-checklist
description: 当拿到一段 AI 生成的代码，还没决定要不要信、要不要跑、要不要往上继续加东西时使用。先做一遍客观体检：行数与嵌套深度、有没有测试、有没有硬编码密钥或遗留 TODO、依赖是不是真实存在、有没有危险调用；再给风险评级和下一步动作。老实写明它查不了算法正确性——体检通过不等于代码是对的。
category: ai-usage/code-review
version: 0.1.0
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
- validating external factual claims made alongside the code.

Prefer neighboring skills for those cases:

- `ai-diff-review-protocol` for patch-focused review;
- `ai-generated-test-auditor` for test-quality audit;
- `ai-output-fact-checker` for claims about libraries, papers, versions, or commands.

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

### Step 3 — Rate risk

Map findings to one verdict:

- **`read-only OK`**: no obvious secrets, no severe placeholders, assumptions are small and visible, scope is modest.
- **`review before run`**: code may be salvageable, but missing tests, unclear dependencies, or partial placeholders make execution risky.
- **`high-risk before run`**: likely secrets, invented dependencies, misleading setup, or obviously unfinished critical paths.
- **`not enough evidence`**: scope too incomplete to judge responsibly.

### Step 4 — Recommend the next action

Give the smallest safe next step, for example:

- “Read these two functions manually before running anything.”
- “Stub the missing environment variables and run only unit tests.”
- “Verify these three dependencies exist before install.”
- “Do not execute; first remove hard-coded credential material.”

## Deterministic checks this skill should prefer

Whenever the environment allows, prefer objective checks for:

- line counts;
- file counts;
- longest-file identification;
- obvious nesting-depth heuristics;
- `TODO` / `FIXME` / `not implemented` markers;
- secret-pattern regex checks;
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
- Top risks:
  1. hard-coded cookie material
  2. no proof of retry/error-path behavior
  3. dependency/setup unclear
- Next safest action: remove cookies, verify imports, run only against a throwaway target
- Blind spots: no runtime execution, cannot confirm scraper correctness
