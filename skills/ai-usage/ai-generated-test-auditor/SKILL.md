---
name: ai-generated-test-auditor
description: 当 AI 写完测试、要决定信不信这份测试时使用。查四类假信心：断言与实现是否同源复制、有没有边界与异常用例、失败信号够不够强、以及把被测代码改坏之后测试会不会真的变红（突变抽样）。测试全绿不等于代码对，也可能是测试根本抓不住错。
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
display_name: AI 测试体检
outputs:
  - chat
max_rounds: 20
suggest_hint: 用「AI 测试体检」看这份 AI 写的测试删掉实现之后会不会真的变红
---

# ai-generated-test-auditor

Use this skill when an AI has already proposed or written tests and you need to decide whether those tests are actually protecting behavior, or just producing a reassuring green checkmark.

This skill audits **test quality**, not product correctness. Its job is to find weak assertions, implementation mirroring, missing boundary/error cases, and evidence that the suite would stay green even after a meaningful bug.

## What this skill does

- Separates the **behavioral contract** from the AI-generated test code.
- Checks whether tests rely on an **independent oracle** or merely replay implementation logic.
- Audits coverage shape:
  - happy path;
  - boundary values;
  - invalid input / failure paths;
  - state transitions / side effects;
  - regressions for previously known bugs.
- Plans a small set of **reversible sample mutations** that should make good tests fail.
- Produces a verdict: **usable / usable with gaps / weak / misleading**.

## Good fits

Use it for:

- reviewing tests created by Copilot, ChatGPT, Claude, Cursor, Aider, or similar tools;
- checking whether a generated suite only tests the obvious path;
- spotting tautological assertions like “expected = same helper as production code”;
- deciding what a human reviewer must strengthen before merging;
- preparing a focused test-review handoff for another engineer or agent.

## Not for

Do **not** use this skill to:

- claim the underlying implementation is correct;
- replace real test execution;
- generate a full production-ready test suite from scratch;
- approve risky refactors without runtime evidence.

If the user actually wants new tests written, a test-authoring skill should do that first. Come back to this skill once there is a candidate suite to inspect.

## Required inputs

Ask for the smallest set that makes an audit meaningful:

1. **Behavioral target**
   - what function, module, endpoint, workflow, or bugfix the tests are supposed to protect;
2. **AI-generated tests**
   - pasted code, file content, or a precise summary of key assertions;
3. **Implementation summary**
   - enough to see whether tests copy internal logic instead of checking behavior;
4. **How tests would be run**
   - command, framework, or at least the expected environment;
5. **Any known edge cases or failure modes**
   - if already known by the user or issue tracker.

If these are missing, say exactly what is missing. Do not pretend to certify tests you cannot inspect.

## Core workflow

### Step 1: restate the contract under test

Before reading assertions, write down:

- what external behavior should be true;
- what inputs matter;
- what outputs, state changes, or side effects matter;
- what should fail, reject, or stay unchanged.

Prefer contract language such as:

- accepts / rejects;
- returns / raises / logs / persists;
- preserves ordering / idempotence / monotonicity;
- does not mutate unrelated state.

### Step 2: classify each test by evidence strength

For each test or cluster of similar tests, classify the oracle:

- **independent oracle** — compares against a hard requirement, fixture, known output, invariant, or manually reasoned expectation;
- **derived oracle** — expected value computed by a simpler but still independent method;
- **mirrored logic** — expected value built by repeating the production algorithm or the same branch conditions;
- **weak signal** — only checks “did not crash”, status 200, non-null, truthy, or snapshot noise without semantic assertions.

Anything in the last two categories is high-risk when AI wrote it.

### Step 3: audit coverage shape

Check whether the suite includes, skips, or hand-waves:

1. **happy path**;
2. **boundary cases**
   - empty input, zero, one, min/max, exact threshold, off-by-one neighbors;
3. **error / invalid input cases**;
4. **stateful or side-effect cases**
   - retries, duplicate calls, persistence, ordering, cleanup;
5. **regression hooks**
   - tests tied to a known bug or failure mode.

If a category is absent, name the missing risk explicitly.

### Step 4: look for AI-specific failure patterns

Treat these as red flags:

- assertions copied from implementation formulas or helper functions;
- mocks so aggressive that real behavior disappears;
- snapshot tests with no focused semantic assertions;
- exact string assertions on unstable text without checking the real contract;
- tests that only verify the current implementation, not intended behavior;
- “parameterized” cases that are all the same shape;
- boundary values mentioned in comments but not asserted;
- TODO/FIXME placeholders left in test code;
- tests for private helpers while public behavior stays untested.

### Step 5: plan reversible sample mutations

Pick 2–5 small mutations that a decent suite should catch.

Prefer mutations like:

- flip `>` to `>=` or `<` to `<=` at a threshold;
- remove validation or an early return;
- replace a computed value with a constant;
- swap sort order;
- skip persistence / callback / emitted event;
- change one branch’s sign, key, or unit conversion.

For each mutation, record:

- target behavior being challenged;
- likely file/function or logic point;
- what test should fail;
- what it means if no test would fail.

If you cannot run mutations in the current environment, still provide the **plan** and label runtime evidence as missing.

### Step 6: produce a verdict

Use one of:

- **usable** — covers core behavior with mostly independent oracles and meaningful failure signals;
- **usable with gaps** — main path is protected, but specific missing edges or weak assertions remain;
- **weak** — many tests are shallow, mirrored, or leave important behavior unprotected;
- **misleading** — a green suite would create false confidence because the assertions barely test the contract.

## Output format

Use this structure:

### 1. Audit target
- what the tests claim to protect;
- what evidence was actually available.

### 2. Contract summary
- key behaviors;
- failure modes that should matter.

### 3. Evidence audit
A compact table with:
- test or cluster;
- oracle type;
- strength;
- concern.

### 4. Coverage gaps
- missing boundary cases;
- missing error cases;
- missing side-effect or regression coverage.

### 5. Sample mutation plan
For each mutation:
- mutation idea;
- behavior it probes;
- test expected to fail;
- interpretation if suite stays green.

### 6. Verdict
- usable / usable with gaps / weak / misleading;
- what to strengthen next.

### 7. Evidence status
Tag statements when useful:
- `given`;
- `observed in test code`;
- `inferred from implementation summary`;
- `should be verified by execution`;
- `missing evidence`.

## Boundary rules

- Do not claim coverage percentages you did not measure.
- Do not claim mutation resistance unless mutations were actually executed.
- Do not rewrite the whole suite unless the user explicitly asks for authoring help.
- Do not confuse “tests pass” with “tests are meaningful”.
- If only a prose summary is available, downgrade confidence and say so.

## Deterministic helper

This skill includes a dependency-free helper script:

- `scripts/check_test_audit_manifest.py`

It validates whether a planned audit packet is structurally complete enough to review consistently:

- required fields present;
- implementation file paths unique;
- test case IDs unique;
- mutation sample IDs unique;
- every mutation points to declared implementation files and named test cases;
- warns when happy path, boundary, error, or side-effect coverage is missing from the audit packet.

Example manifest shape:

```json
{
  "target": "Validate AI-generated tests for create_user",
  "implementationFiles": ["src/user_service.py"],
  "testCases": [
    {
      "id": "accepts_valid_name",
      "kind": "happy-path",
      "oracle": "independent",
      "summary": "Creates a user when name and email are valid"
    },
    {
      "id": "rejects_blank_name",
      "kind": "error-path",
      "oracle": "independent",
      "summary": "Raises ValueError for blank name"
    }
  ],
  "mutationSamples": [
    {
      "id": "skip_blank_name_validation",
      "targetFile": "src/user_service.py",
      "kind": "remove-validation",
      "expectedFailingTests": ["rejects_blank_name"],
      "why": "A real guard should be observable through the public API"
    }
  ]
}
```

Run it with any Python 3 environment:

```bash
python scripts/check_test_audit_manifest.py path/to/test-audit-manifest.json
```

## Heuristics this skill should apply

Prefer these questions when deciding whether AI-generated tests are trustworthy:

- Would the test still pass if the implementation returned a constant or cached default?
- Does the expected value come from an independent requirement, or from reusing production logic?
- Are there threshold neighbors, invalid shapes, and empty cases?
- Does any test prove an important side effect happened, not merely that the function returned?
- Is there at least one mutation per major behavioral promise that should clearly turn the suite red?

## Mini examples

- If the production code sorts ascending and the test builds `sorted(input)` as its expected value, that is often mirrored logic, not a strong oracle.
- If an API test only checks status `200` and “response is not null”, it does not prove the payload contract.
- If deleting an input-validation branch would leave the suite green, the suite is giving false confidence exactly where users are likely to get hurt.

## Success criterion

The skill has done its job when the user can say:

1. which tests genuinely protect behavior;
2. which tests only mirror implementation or check noise;
3. which edge and failure cases are still unprotected;
4. which 2–5 sample mutations should be tried next;
5. and how much trust the current suite has earned.
