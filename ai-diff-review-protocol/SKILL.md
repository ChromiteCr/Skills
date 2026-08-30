---
name: ai-diff-review-protocol
description: Review an AI-generated code change by risk rather than by line-by-line reading. Triage whether the change matches intent, touches risky boundaries, creates broad side effects, and stays reversible.
version: 0.1.0
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

- You do not have the actual change content yet.
- You need proof of behavioral correctness; this skill can flag risk, not prove the code works.
- The task is primarily architectural redesign rather than change review.

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

1. **Verdict**: `pass`, `caution`, or `stop`
2. **One-sentence rationale**
3. **Risk summary**
   - intent match
   - risky boundaries touched
   - likely side effects
   - reversibility
4. **High-priority review targets** (up to 5)
5. **Required follow-up before merge/apply**
6. **Confidence**: high / medium / low

## Review protocol

### Step 1 — Intent match

Summarize the requested change in one sentence, then compare it against the diff.

Check:

- Is the requested scope present?
- Did the AI also change unrelated code?
- Is there evidence of over-building or under-delivering?
- Are names, comments, and tests aligned with the claimed intent?

If the change solves a different problem than requested, mark **stop**.

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

## Deterministic checks from the diff itself

When a unified diff or patch is available, extract these objective signals:

- number of changed files
- files added / deleted / renamed
- total additions and deletions
- whether tests changed
- whether config, migration, lockfile, or secrets-related files changed
- whether the patch mixes code, tests, and infra in one batch
- whether there are large deletions or mechanical renames

Use these thresholds as defaults, not laws:

- **1–3 files** changed: usually local, keep reviewing
- **4–8 files** changed: check for scope creep
- **9+ files** changed: assume broader risk until shown otherwise
- **200+ changed lines**: require a clearer side-effect summary
- **touches tests only minimally while production code changes a lot**: ask why
- **touches config/migrations/public API**: raise boundary risk

If no diff is provided and only a prose summary exists, say the deterministic layer could not run.

## Decision rules

Return `pass` only when all are true:

- the change clearly matches intent
- no unexplained risky boundary edits
- side-effect surface is narrow or well-justified
- rollback is easy or documented
- validation evidence is proportional to risk

Return `caution` when:

- the core idea looks right, but risk or evidence is incomplete
- the change touches shared code or config
- tests/evidence are partial
- the patch is larger than the request suggests

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
- Add one regression test for the original bug
- Show behavior before/after for invalid input
- Confirm whether changing the default is intentional

Confidence: medium
```

## Notes for agent implementations

- Accept diff text from any source; do not assume Git is available.
- If objective diff stats cannot be computed, still run the four-step reasoning protocol and lower confidence.
- Do not claim code is correct unless validation evidence is supplied.
- Prefer quoting exact changed paths or hunks when present.
