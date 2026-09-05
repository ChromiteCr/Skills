# limiting-case-validator

These cases are written so an agent can practice the skill without needing vendor-specific tooling.

## Case 1 — Small-angle pendulum period

**Input**

Candidate result: `T = 2π * sqrt(L/g) * (1 + θ0)` for a simple pendulum at small amplitude.

Symbols:
- `T`: period
- `L`: pendulum length
- `g`: gravitational acceleration
- `θ0`: launch amplitude in radians

Known benchmark:
- In the small-angle limit `θ0 -> 0`, the period should reduce to `2π * sqrt(L/g)`.
- The correction should not make the period decrease for positive amplitude.

**What a good answer should catch**

- Tests the limit `θ0 -> 0`.
- Notices the candidate does reduce to the benchmark in that limit.
- Flags that the linear correction in `θ0` is suspicious because the exact expansion is even in amplitude near zero.
- Gives at least a partial-fail or fail style verdict, not a clean pass.

## Case 2 — Drag law with zero drag coefficient

**Input**

Candidate terminal speed formula: `v_t = sqrt(2mg/(ρ C_d A))`.

Known benchmark:
- As `C_d -> 0`, there is no finite terminal speed; the notion of terminal speed breaks down because drag vanishes.

**What a good answer should catch**

- Identifies `C_d` as a control parameter.
- Evaluates the limit `C_d -> 0` and sees divergence.
- Explains that the divergence is not automatically a bug; it matches the physical expectation that no finite terminal speed exists without drag.
- Marks the limit as a pass when interpreted correctly.

## Case 3 — Parallel resistors benchmark

**Input**

Candidate formula for two resistors in parallel: `R_eq = R1 + R2`.

Known benchmark:
- If `R2 -> ∞`, then `R_eq -> R1`.
- If `R2 -> 0`, then `R_eq -> 0`.
- `R_eq` must be less than or equal to the smaller resistor.

**What a good answer should catch**

- Tests at least the open-circuit and short-circuit limits.
- Sees that the candidate fails both benchmark behaviors.
- Uses physical language, not only algebra, to explain why the formula cannot describe a parallel network.

## Case 4 — Nonrelativistic energy expansion

**Input**

Candidate claim: total relativistic energy is approximately `E ≈ pc` for all speeds.

Known benchmark:
- In the nonrelativistic limit `v << c`, total energy should behave like `mc^2 + p^2/(2m)` to leading orders.

**What a good answer should catch**

- Chooses the nonrelativistic regime as the key limit.
- Notes that `E ≈ pc` corresponds to a massless or ultrarelativistic regime, not the all-speed case.
- Gives a fail verdict for the stated claim.

## Case 5 — Boundary / scope discipline

**Input**

The user only says: "Check whether my final answer is plausible" and provides no formula, variables, or benchmark case.

**What a good answer should do**

- Refuse to bluff.
- Ask for the expression, symbol meanings, and at least one relevant regime or special case.
- Mark the current run as underdetermined.
