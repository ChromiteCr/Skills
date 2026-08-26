---
name: ai-session-handoff-writer
description: Create a portable handoff document for a paused or transferred AI-assisted task, preserving verified progress, decisions, risks, and the next concrete step.
version: 0.1.0
---

# ai-session-handoff-writer

## What this skill does

This skill turns an in-progress task into a handoff document that another agent or person can continue with minimal context loss.

It is optimized for long-running work, session resets, model switches, ownership changes, and paused tasks.

## Use this skill when

- A task will continue in another session
- Work is being transferred between people or agents
- A project has multiple open threads and needs a clean restart point
- You need to preserve not just status, but also why decisions were made

## Do not use this skill when

- A one-line chat update is enough
- There is no meaningful progress, decision, or artifact to hand off
- The recipient is not allowed to see the underlying work or data
- The main need is a code diff review rather than a task-level handoff

## Required inputs

Collect or infer these before writing:

1. **Task objective** — what the work is trying to achieve
2. **Current state** — what is already done and what remains open
3. **Artifacts** — files, documents, links, tickets, datasets, or outputs that matter
4. **Key decisions** — important choices already made
5. **Rationale** — why those choices were made
6. **Verification status** — what has been checked versus assumed
7. **Risks or blockers** — what could stop or mislead the next worker
8. **Next step** — the best immediate continuation action

If any required input is missing, keep the section and label it clearly as `[missing]` rather than inventing details.

## Evidence labels

Use these labels consistently inside the handoff:

- `[confirmed]` — directly verified from files, tests, outputs, or trusted records
- `[inferred]` — strongly supported but not directly verified in the current context
- `[unverified]` — reported, assumed, or still needs checking
- `[missing]` — required information is not currently available

Do not blur these categories.

## Workflow

### 1) Define the handoff target

State who or what should be able to continue after reading the handoff:

- another general-purpose agent
- a coding-focused agent
- a human collaborator
- your future self in a later session

Write for the least-informed plausible recipient.

### 2) Separate facts from interpretation

Before drafting, sort notes into:

- completed work
- decisions
- evidence
- open questions
- next actions

If a claim cannot be supported, mark it `[inferred]` or `[unverified]`.

### 3) Capture only the continuation-critical context

Prefer information that changes what the next worker should do:

- exact file paths or artifact names
- commands already tried and their outcomes
- constraints, approvals, or boundaries
- rejected approaches worth not repeating
- ordering dependencies

Avoid dumping long transcripts unless they contain irreplaceable reasoning.

### 4) Write the handoff in the standard structure

Use the template in `handoff-template.md`.

Minimum required sections:

1. Objective
2. Current status
3. Completed work
4. Key decisions and rationale
5. Evidence and verification
6. Outstanding issues and risks
7. Recommended next actions
8. Restart notes

### 5) Validate before sending

A handoff is only complete if the next worker can answer all of these:

- What is the goal?
- What is already done?
- What should not be undone lightly?
- What still needs verification?
- What is the very next action?
- Where are the relevant artifacts?

If any answer is unclear, revise the handoff.

## Output rules

- Prefer bullets over long prose
- Put the next action near the end as a numbered list
- Name files and paths explicitly
- Preserve uncertainty labels
- Keep tone neutral and operational
- Redact secrets, tokens, passwords, and private data unless explicitly authorized for the recipient

## Quality checklist

Before finalizing, confirm:

- All required sections are present
- Every major claim has an evidence label
- Paths, URLs, or artifact identifiers are explicit where relevant
- Decisions include reasons, not just outcomes
- Risks mention likely failure modes or missing information
- Next actions are ordered and concrete
- The document does not expose secrets beyond the intended audience

## Failure modes to avoid

- Writing a status summary with no restart path
- Mixing verified facts with guesses
- Omitting the rationale behind important choices
- Burying blockers in narrative text
- Providing ten possible next steps instead of one recommended sequence
- Repeating raw chat history instead of distilling it

## Handoff compression guidance

When the context is large, compress in this order:

1. Keep decisions and rationale
2. Keep artifact locations
3. Keep verification results
4. Keep blockers and dependencies
5. Summarize routine background detail last

## Suggested prompt pattern

When using this skill, produce a handoff document that:

- preserves verified progress
- distinguishes confirmed vs inferred vs unverified information
- lists concrete artifacts and locations
- explains key decisions and why they were made
- ends with a short ordered next-step plan

## Deliverable

Return a completed handoff document based on `handoff-template.md`.
