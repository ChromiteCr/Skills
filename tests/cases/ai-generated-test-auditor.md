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

**Expected skill behavior**
- Mark mutation-resistance claims as unverified.
- Flag the missing execution evidence and packet inconsistency.
- Downgrade confidence rather than accepting the claim.
- Final verdict should mention `missing evidence` explicitly.
