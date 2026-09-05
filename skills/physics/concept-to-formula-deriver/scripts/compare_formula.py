#!/usr/bin/env python3
"""Compare two symbolic expressions for equivalence.

Usage:
    python compare_formula.py --derived "sqrt(2*G*M/R)" --reference "(2*G*M/R)**0.5"
    python compare_formula.py --derived "Eq(T, 2*pi*sqrt(L/g))" --reference "Eq(T, 2*pi*sqrt(L/g))"

This is a lightweight deterministic check for skill authors and agents.
It does not prove the derivation is physically justified; it only checks symbolic equivalence.
"""

from __future__ import annotations

import argparse
import sys

try:
    import sympy as sp
except Exception as exc:  # pragma: no cover - import failure path is user-facing
    print("ERROR: sympy is required for symbolic comparison.", file=sys.stderr)
    print(f"Import failure: {exc}", file=sys.stderr)
    sys.exit(2)


def _parse_expression(raw: str) -> sp.Expr:
    text = raw.strip()
    parsed = sp.sympify(text, evaluate=False)
    if isinstance(parsed, sp.Equality):
        return sp.simplify(parsed.lhs - parsed.rhs)
    return sp.simplify(parsed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two symbolic expressions for equivalence.")
    parser.add_argument("--derived", required=True, help="Derived expression or equation.")
    parser.add_argument("--reference", required=True, help="Reference expression or equation.")
    args = parser.parse_args()

    derived = _parse_expression(args.derived)
    reference = _parse_expression(args.reference)

    difference = sp.simplify(derived - reference)
    equivalent = difference == 0

    print(f"derived_normalized: {sp.sstr(derived)}")
    print(f"reference_normalized: {sp.sstr(reference)}")
    print(f"difference: {sp.sstr(difference)}")
    print(f"equivalent: {'yes' if equivalent else 'no'}")

    return 0 if equivalent else 1


if __name__ == "__main__":
    raise SystemExit(main())
