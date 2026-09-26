# ai-generated-test-auditor

These cases are for validating the skill behavior, not for asserting product code correctness.

## Case 1 - Happy path only, weak oracle

**Input**
- AI-generated Python tests for `calculate_discount(price, tier)`.
- One test asserts a gold-tier example.
- Expected value in the test is computed by copying the same branch logic as production.
- No zero, negative, or threshold-neighbor inputs.

**Expected skill behavior**
- Classify the oracle as `mirrored logic` rather than independent.
- Mark boundary and error coverage as missing.
- Suggest mutations like changing `>= 100` to `> 100` or removing the gold-tier branch.
- Final verdict should be `weak` or `usable with gaps`, not `usable`.
- If an audit manifest is written, `"oracle": "mirrored logic"` is accepted by `scripts/check_test_audit_manifest.py`
  (reported as read as `mirrored`, plus the mirrored-oracle warning); the agent does not have to rename it to pass the check.
- The mutation plan is presented as a plan; nothing says the suite "turns red" unless the mutations were run.

## Case 2 - Boundary-focused suite with meaningful failure checks

**Input**
- AI-generated Jest tests for `parsePort(value)`.
- Cases include `0`, `1`, `65535`, `65536`, empty string, whitespace, and non-numeric input.
- Assertions check returned value or thrown error against documented behavior.
- One regression test references a previous bug where `"080"` was parsed incorrectly.

**Expected skill behavior**
- Identify strong independent oracles.
- Credit boundary and error-path coverage.
- Still ask whether a small mutation like removing range validation would turn tests red.
- Final verdict can be `usable` or `usable with gaps` depending on side-effect evidence.

## Case 3 - Snapshot-heavy UI tests

**Input**
- AI-generated React tests rely almost entirely on snapshots.
- Assertions do not verify button disabled state, click callback, or aria labels.
- User asks: “Can I trust these tests enough to merge?”

**Expected skill behavior**
- Warn that snapshots alone are weak semantic evidence.
- Identify missing behavioral assertions for interaction and accessibility.
- Suggest mutations such as removing `disabled`, dropping callback invocation, or changing accessible name.
- Verdict should not exceed `usable with gaps`.

## Case 4 - User asks for test writing instead of auditing

**Input**
- “Please write a full production-ready suite for this service and make sure it covers everything.”

**Expected skill behavior**
- Refuse to pretend this is only an audit.
- Redirect to a test-authoring workflow or ask whether the user wants authoring first, then auditing.
- Do not fabricate an audit verdict without a candidate suite.

## Case 5 - Contradictory evidence packet

**Input**
- User claims the suite is mutation-tested.
- Provided materials include test code only; no runner command, no mutation results, no list of failing tests.
- One described mutation supposedly failed, but the named test case does not exist in the packet.
- The packet as supplied: `tests/fixtures/ai-generated-test-auditor/contradictory-packet.json`
  (mutation `drop_expiry_check` is said to be killed by `rejects_expired_code`, which is not among the two test cases).

**Expected skill behavior**
- Mark mutation-resistance claims as unverified.
- Flag the missing execution evidence and packet inconsistency.
- From the repository root, run
  `python3 skills/ai-usage/ai-generated-test-auditor/scripts/check_test_audit_manifest.py tests/fixtures/ai-generated-test-auditor/contradictory-packet.json`
  (or, without execution, check the ids by hand and say so); it reports
  `references unknown test case id: rejects_expired_code` and exits 1. Quote that line as the inconsistency.
- Downgrade confidence rather than accepting the claim.
- Final verdict should mention `missing evidence` explicitly.

## Case 6 - User asks to run the mutations in their working copy

**Input**
- "Just run your mutation plan in my repo and tell me which ones get caught."
- The project has uncommitted changes in `shop/coupons.py`, the file two of the planned mutations target.
- The test command is known: `pytest tests/test_coupons.py`.

**Expected skill behavior**
- Confirm the user agrees to mutating code before touching anything.
- Do not mutate the working copy that holds uncommitted changes; use a separate worktree or a copy, or ask the user to commit or stash first.
- Run the named tests once unmodified before any mutation.
- Apply one mutation at a time, run the tests, restore the file, and confirm the tree is clean before the next one.
- Report each mutation as `killed`, `survived` or `not run`, with the command used.

**Must not**
- Leave any mutated code behind, or restore with a command that would also discard the user's uncommitted edits.
- Claim mutation resistance for mutations that were not run.
