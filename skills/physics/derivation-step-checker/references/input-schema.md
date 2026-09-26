# Checker input schema

The checker accepts one UTF-8 JSON object. Expressions use `+ - * / **` (or `^`), parentheses, known symbol names, numeric constants, and the functions `sqrt`, `abs`, `sin`, `cos`, `tan`, `exp`, and `log`. `pi` and `E` (Euler's number) are built-in constants unless you declare a symbol with that name. Trigonometric, exponential, and logarithmic arguments must be dimensionless. A symbolic exponent, as in `10**m` or `2**(-t/T)`, must be dimensionless and its base must be dimensionless too.

```json
{
  "symbols": {
    "F": {"M": 1, "L": 1, "T": -2},
    "m": {"M": 1},
    "a": {"L": 1, "T": -2}
  },
  "nonzero": ["m"],
  "steps": [
    {
      "id": "1",
      "before": "F = m*a",
      "after": "a = F/m",
      "factor": "-m",
      "law": "Newton's second law for a constant-mass system in an inertial frame",
      "applicability": "m is constant and nonzero; F is the net external force; the frame is inertial"
    }
  ]
}
```

## Fields

- `symbols` (required): map each expression symbol to its dimension vector. Dimension keys are arbitrary base labels such as `M`, `L`, `T`, `I`, `Theta`, `N`, and `J`; exponents are numbers or strings representing rational numbers.
- `nonzero` (optional): symbols or expressions explicitly assumed nonzero, for example `"m"` or `"m1 - m2"`. The checker splits each step's `factor` into its non-constant factors (numerator and denominator, with SymPy `factor_list`); every such factor must be listed here or be provably nonzero, such as `exp(x)`. Declaring `m1` and `m2` does not declare `m1 - m2`: dividing by a difference or a sum needs that expression listed. A listed product such as `"m1*m2"` or `"m1**2 - m2**2"` declares each of its factors. Sign does not matter: `"m1 - m2"` also covers `m2 - m1`.
- `steps` (required): nonempty list of step objects.
- `id` (required): displayed step identifier.
- `before`, `after` (required): equations containing exactly one `=` each.
- `factor` (optional, default `1`): value satisfying `residual(before) = factor * residual(after)`. It records operations such as multiplying both sides or reversing signs.
- `law` (required): named law, definition, algebraic move, or approximation.
- `applicability` (required): conditions needed at this step. Presence is machine-checked; truth is a human judgment.

## Interpretation

Exit code `0` means all machine-checkable tests passed. Exit code `1` means at least one step failed or the input was invalid, including an unknown top-level or step key. Exit code `2` means the command line itself was wrong, for example no input file. `python3 scripts/check_derivation.py --selftest` runs the built-in regression cases. A pass establishes only constrained symbolic equivalence and dimensional consistency; it does not establish that the model, law, frame, approximation, or domain is physically appropriate.

An equation with one side identically `0`, such as `m*g - k*x = 0`, is dimensionally consistent whatever the other side's dimension; the other side is still checked on its own, so `m*g - k = 0` with `k` a spring constant fails because it adds unlike terms.
