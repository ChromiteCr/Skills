# Checker input schema

The checker accepts one UTF-8 JSON object. Expressions use `+ - * / **` (or `^`), parentheses, known symbol names, numeric constants, and the functions `sqrt`, `abs`, `sin`, `cos`, `tan`, `exp`, and `log`. Trigonometric, exponential, and logarithmic arguments must be dimensionless.

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
- `nonzero` (optional): symbol names explicitly assumed nonzero. If a step's equivalence factor contains symbols, each must appear here.
- `steps` (required): nonempty list of step objects.
- `id` (required): displayed step identifier.
- `before`, `after` (required): equations containing exactly one `=` each.
- `factor` (optional, default `1`): value satisfying `residual(before) = factor * residual(after)`. It records operations such as multiplying both sides or reversing signs.
- `law` (required): named law, definition, algebraic move, or approximation.
- `applicability` (required): conditions needed at this step. Presence is machine-checked; truth is a human judgment.

## Interpretation

Exit code `0` means all machine-checkable tests passed. Exit code `1` means at least one step failed or the input was invalid. A pass establishes only constrained symbolic equivalence and dimensional consistency; it does not establish that the model, law, frame, approximation, or domain is physically appropriate.
