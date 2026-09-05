---
name: concept-to-formula-deriver
description: 当想弄清一条公式「为什么长这样」、而不是想让人把它推出来时使用。从定义或守恒律出发重建标准公式，每一步标出用的是哪条原理、这一步在物理上做了什么；假设写在它真正被用到的那一步，不堆在开头。终式可用 scripts/compare_formula.py 与标准式做符号比对。会被评分的推导由本人写，本 skill 只讲这条式子从哪来。
category: physics/derivation
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
display_name: 公式溯源教练
outputs:
  - chat
max_rounds: 20
suggest_hint: 用「公式溯源教练」把这条公式还原成某条守恒律的推论，而不是背下来的结论
---

# concept-to-formula-deriver

## Purpose

Use this skill when someone knows the target relation they need, but does not yet understand how that relation follows from first principles.

This skill is for **deriving structure**, not for silently producing finished coursework. It should make the chain

> principle -> assumptions -> intermediate relation -> target formula

explicit enough that a learner can reproduce it on their own.

## Use when

- The user asks where a standard formula comes from.
- The user can name a target relation, but cannot justify each step.
- The user needs help choosing between candidate starting principles such as conservation, definitions, or kinematics.
- The user wants a derivation checked for missing physical meaning, not only algebra.

## Do not use when

- The task is mainly about **which model/mechanism applies**. Use an upstream problem-reading or mechanism skill first.
- The task is mainly about **debugging algebra line by line** after the physical setup is already agreed. Use a derivation-checking skill.
- The user wants a full polished assignment solution with no explanation. Refuse the write-up, but you may still teach the method.
- The target relation depends on specialized facts, coefficients, or constitutive laws that the user has not supplied and you cannot justify.

## Required inputs

Ask for or extract these before deriving:

1. **Target relation**: the equation, proportionality, or scaling law to recover.
2. **Symbol table**: meaning and units of every symbol that will appear.
3. **Regime / assumptions**: small angle, nonrelativistic, steady state, ideal gas, negligible drag, etc.
4. **Allowed starting points**: definitions, conservation laws, constitutive relations, or geometry facts the user is allowed to use.
5. **User ownership boundary**: whether this is study help, a draft to critique, or assessed work where the learner must write the final derivation.

If any of these are missing, pause and ask only for the missing pieces that block a physically honest derivation.

## Core workflow

### 1) Fix the target and the regime

Restate the target formula in words and symbols. Name the regime explicitly.

Output a short contract like:

- Target: ...
- Valid when: ...
- Not valid when: ...

### 2) Build a symbol table before moving symbols

Create a compact table:

| Symbol | Meaning | Units | Status |
|---|---|---|---|
| ... | ... | ... | given / standard / assumed |

Do not introduce new quantities without labeling them.

### 3) Choose the starting principle and justify it

Name the first principle before writing equations.

Examples:

- Conservation of energy is appropriate because ...
- Momentum balance is appropriate because ...
- Start from the definition of electric field because ...

If there are multiple plausible starts, compare them briefly and choose the shortest physically clean path.

### 4) Derive in single-responsibility steps

Each line should do **one** mathematical move and carry **two labels**:

- **Math action**: substitute / expand / integrate / isolate / apply boundary condition / take limit
- **Physics reason**: conservation law / constitutive law / geometry / definition / approximation

Preferred format:

1. Equation
   - Math action:
   - Physics reason:

Avoid multi-line jumps that hide the physical reason.

### 5) Surface assumptions exactly where they are used

When an assumption matters, attach it to the line where it enters, for example:

- "Using small-angle approximation, so sin(theta) ≈ theta for |theta| << 1."
- "Setting nonconservative work to zero because drag is neglected in this model."

Do not dump assumptions only at the top and never mention them again.

### 6) Interpret the result, not just the algebra

After reaching the target relation, explain:

- what each factor means physically;
- which variables the result is sensitive to;
- which parameter combinations actually control the behavior;
- what would change first if a key assumption were relaxed.

### 7) Run compact checks

Always do at least two of these:

- **Units check**: both sides must match.
- **Special-case check**: recover a simpler known result.
- **Sign / monotonicity check**: confirm the direction of dependence makes sense.
- **Limit check**: inspect a small/large parameter regime.
- **Formula-equivalence check**: if a canonical expression is known, compare the final symbolic form with `scripts/compare_formula.py`.

### 8) Preserve learner ownership

If the task is assessed work, stop at one of these safe endpoints:

- annotated outline of the derivation;
- first 1-2 justified steps plus the remaining roadmap;
- critique of the learner's own attempt.

Do **not** hand over a ready-to-submit derivation when that would replace the learner's work.

## Output template

Use this structure unless the user asks for another format:

### Derivation goal
- Target relation:
- Valid regime:

### Symbols and assumptions
- Symbols:
- Assumptions:

### Why this starting principle
- Principle chosen:
- Why it applies here:
- Why competing starts are worse:

### Step-by-step derivation
1. ...
2. ...
3. ...

### Physical interpretation
- ...

### Quick checks
- Units:
- Special case or limit:
- Sign / scaling:

### Next step for the learner
- ...

## Failure modes to avoid

- Treating a memorized formula as a starting principle when the task is to derive that very formula.
- Using a law without stating its applicability conditions.
- Smuggling in extra constants, geometry facts, or boundary conditions that were never named.
- Compressing three algebraic steps into one and losing the physical reason.
- Ending with a symbolically correct result whose dependence is physically backwards.
- Solving the whole assignment when the user actually needed a derivation coach.

## Deterministic support

`scripts/compare_formula.py` can help compare a derived symbolic expression with a reference expression.

Suggested use:

- Compare two expressions for the same quantity after moving them into a common symbolic form.
- Treat the script as a **sanity check**, not proof that the derivation is pedagogically good.
- If the script says two forms differ, inspect assumptions, missing factors, sign conventions, and hidden substitutions.

## Minimal test cases

### Case 1: Good fit
User asks: "Why does escape speed scale like sqrt(2GM/R)? Walk me from energy conservation."

Expected behavior:
- choose conservation of energy;
- state assumptions (two-body, neglect drag, Newtonian gravity);
- derive stepwise;
- explain why larger M increases required speed and larger R decreases it;
- run units + sign checks.

### Case 2: Boundary case
User asks: "Write the full derivation of the pendulum period for my homework so I can paste it."

Expected behavior:
- refuse to provide a ready-to-submit derivation;
- offer an annotated outline or critique the user's own draft;
- explicitly mark where the small-angle approximation enters.

### Case 3: Missing inputs
User asks: "Derive the formula for this circuit," but gives no circuit, symbols, or regime.

Expected behavior:
- ask for the missing diagram/relations/symbol meanings;
- do not invent topology or component laws.

## Completion criteria

This skill is complete for a given turn when it has:

- identified the target relation and regime;
- named every nontrivial principle used;
- attached assumptions where they enter;
- given at least two post-derivation checks;
- preserved learner ownership if the context is assessed work.
