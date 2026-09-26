#!/usr/bin/env python3
"""Check constrained scalar derivation steps for algebra and dimensions.

Input: one UTF-8 JSON object, described in references/input-schema.md.

    python3 scripts/check_derivation.py derivation.json
    python3 scripts/check_derivation.py --selftest

Per step the checker verifies residual equivalence up to the declared factor,
that every non-constant factor of that factor is declared nonzero (or provably
nonzero), and dimensional consistency: both sides of each equation, every sum,
and the arguments of sin, cos, tan, exp, log and of symbolic exponents. A side
that is identically 0 matches any dimension; the other side is still checked
for internal consistency.

Exit 0: every step passed. Exit 1: a step failed or the input was invalid.
A pass says nothing about whether a physical law applies.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from fractions import Fraction
from pathlib import Path

try:
    import sympy as sp
except ImportError:
    print("ERROR: SymPy is required (install the 'sympy' package).", file=sys.stderr)
    raise SystemExit(2)

ALLOWED_FUNCTIONS = {
    "sqrt": sp.sqrt,
    "abs": sp.Abs,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "exp": sp.exp,
    "log": sp.log,
}
DIMENSIONLESS_FUNCTIONS = {sp.sin, sp.cos, sp.tan, sp.exp, sp.log}
TOP_LEVEL_KEYS = {"symbols", "nonzero", "steps"}
STEP_KEYS = {"id", "before", "after", "factor", "law", "applicability"}


class CheckError(ValueError):
    pass


def parse_number(value: object) -> Fraction:
    if isinstance(value, bool):
        raise CheckError("boolean dimension exponent is not allowed")
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise CheckError(f"invalid dimension exponent: {value!r}") from exc


def clean_dim(dim: dict[str, Fraction]) -> dict[str, Fraction]:
    return {key: value for key, value in dim.items() if value}


def add_dim(a: dict[str, Fraction], b: dict[str, Fraction], scale: Fraction = Fraction(1)) -> dict[str, Fraction]:
    result = dict(a)
    for key, value in b.items():
        result[key] = result.get(key, Fraction(0)) + scale * value
    return clean_dim(result)


def format_dim(dim: dict[str, Fraction]) -> str:
    if not dim:
        return "[1]"
    return "[" + " ".join(key if value == 1 else f"{key}^{value}" for key, value in sorted(dim.items())) + "]"


class ExpressionParser(ast.NodeVisitor):
    def __init__(self, symbols: dict[str, sp.Symbol]):
        self.symbols = symbols

    def parse(self, text: str) -> sp.Expr:
        if not isinstance(text, str) or not text.strip():
            raise CheckError("expression must be a nonempty string")
        normalized = text.strip().replace("^", "**")
        try:
            tree = ast.parse(normalized, mode="eval")
        except SyntaxError as exc:
            raise CheckError(f"invalid expression {text!r}: {exc.msg}") from exc
        expr = self.visit(tree.body)
        if expr.has(sp.zoo, sp.oo, -sp.oo, sp.nan):
            raise CheckError(f"expression {text!r} divides by zero or is not finite")
        return expr

    def visit_Name(self, node: ast.Name) -> sp.Expr:
        if node.id in self.symbols:
            return self.symbols[node.id]
        if node.id == "pi":
            return sp.pi
        if node.id == "E":
            return sp.E
        raise CheckError(f"unknown symbol: {node.id}")

    def visit_Constant(self, node: ast.Constant) -> sp.Expr:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CheckError("only numeric constants are allowed")
        return sp.Rational(str(node.value))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> sp.Expr:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise CheckError("unsupported unary operator")

    def visit_BinOp(self, node: ast.BinOp) -> sp.Expr:
        left, right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise CheckError("unsupported binary operator")

    def visit_Call(self, node: ast.Call) -> sp.Expr:
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise CheckError("unsupported function")
        if len(node.args) != 1 or node.keywords:
            raise CheckError(f"{node.func.id} requires exactly one positional argument")
        return ALLOWED_FUNCTIONS[node.func.id](self.visit(node.args[0]))

    def generic_visit(self, node: ast.AST) -> sp.Expr:
        raise CheckError(f"unsupported syntax: {type(node).__name__}")


def dimension(expr: sp.Expr, dimensions: dict[sp.Symbol, dict[str, Fraction]]) -> dict[str, Fraction]:
    if expr.is_Number or expr in (sp.pi, sp.E):
        return {}
    if expr.is_Symbol:
        return dimensions[expr]
    if expr.is_Add:
        parts = [dimension(arg, dimensions) for arg in expr.args]
        if any(part != parts[0] for part in parts[1:]):
            raise CheckError(f"addition combines unlike dimensions in {expr}")
        return parts[0]
    if expr.is_Mul:
        result: dict[str, Fraction] = {}
        for arg in expr.args:
            result = add_dim(result, dimension(arg, dimensions))
        return result
    if expr.is_Pow:
        base, exponent = expr.args
        base_dim = dimension(base, dimensions)
        if not exponent.is_number:
            exponent_dim = dimension(exponent, dimensions)
            if exponent_dim:
                raise CheckError(f"exponent must be dimensionless in {expr}; it has {format_dim(exponent_dim)}")
            if base_dim:
                raise CheckError(f"dimensioned base has a symbolic exponent in {expr}")
            return {}
        try:
            power = Fraction(str(exponent))
        except ValueError as exc:
            raise CheckError(f"unsupported exponent in {expr}") from exc
        return {key: value * power for key, value in base_dim.items() if value * power}
    if expr.func == sp.Abs:
        return dimension(expr.args[0], dimensions)
    if expr.func in DIMENSIONLESS_FUNCTIONS:
        arg_dim = dimension(expr.args[0], dimensions)
        if arg_dim:
            raise CheckError(f"{expr.func.__name__} requires a dimensionless argument in {expr}")
        return {}
    raise CheckError(f"cannot determine dimensions of {expr}")


def is_identically_zero(expr: sp.Expr) -> bool:
    return expr.is_zero is True or sp.simplify(expr) == 0


def nonconstant_factors(expr: sp.Expr) -> list[sp.Expr]:
    """Non-constant factors of numerator and denominator (SymPy factor_list).

    Each returned factor must be nonzero for expr to be finite and nonzero.
    """
    numerator, denominator = sp.fraction(sp.together(expr))
    factors: list[sp.Expr] = []
    for part in (numerator, denominator):
        try:
            _coefficient, items = sp.factor_list(part)
        except sp.PolynomialError:
            items = [(part, 1)]
        for base, _power in items:
            if not base.is_number:
                factors.append(base)
    return factors


def is_declared_nonzero(factor: sp.Expr, declared: list[sp.Expr]) -> bool:
    if factor.is_zero is False:
        return True
    for item in declared:
        if factor == item or factor == -item or sp.expand(factor - item) == 0 or sp.expand(factor + item) == 0:
            return True
    if factor.func == sp.Abs:
        return all(is_declared_nonzero(inner, declared) for inner in nonconstant_factors(factor.args[0]))
    return False


def parse_equation(text: object, parser: ExpressionParser) -> tuple[sp.Expr, sp.Expr]:
    if not isinstance(text, str) or text.count("=") != 1:
        raise CheckError("equation must contain exactly one '='")
    left, right = text.split("=", 1)
    return parser.parse(left), parser.parse(right)


def load_input(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CheckError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def check_document(data: object) -> tuple[bool, list[str]]:
    """Return (failed, report lines). Invalid input raises CheckError."""
    if not isinstance(data, dict):
        raise CheckError("top-level JSON value must be an object")
    unknown_keys = sorted(set(data) - TOP_LEVEL_KEYS)
    if unknown_keys:
        raise CheckError(f"unknown top-level keys: {unknown_keys} (allowed: {sorted(TOP_LEVEL_KEYS)})")
    raw_symbols = data.get("symbols")
    steps = data.get("steps")
    nonzero = data.get("nonzero", [])
    if not isinstance(raw_symbols, dict) or not raw_symbols:
        raise CheckError("symbols must be a nonempty object")
    if not isinstance(steps, list) or not steps:
        raise CheckError("steps must be a nonempty list")
    if not isinstance(nonzero, list) or any(not isinstance(item, str) for item in nonzero):
        raise CheckError("nonzero must be a list of strings (symbol names or expressions)")
    invalid_names = [name for name in raw_symbols if not isinstance(name, str) or not name.isidentifier()]
    if invalid_names:
        raise CheckError(f"invalid symbol names: {invalid_names}")

    symbols = {name: sp.Symbol(name) for name in raw_symbols}
    dimensions: dict[sp.Symbol, dict[str, Fraction]] = {}
    for name, raw_dim in raw_symbols.items():
        if not isinstance(raw_dim, dict):
            raise CheckError(f"dimension vector for {name} must be an object")
        dimensions[symbols[name]] = clean_dim({str(key): parse_number(value) for key, value in raw_dim.items()})

    parser = ExpressionParser(symbols)
    declared: list[sp.Expr] = []
    for text in nonzero:
        try:
            expr = parser.parse(text)
        except CheckError as exc:
            raise CheckError(f"nonzero entry {text!r}: {exc}") from exc
        if is_identically_zero(expr):
            raise CheckError(f"nonzero entry {text!r} is identically zero")
        # A declared product or quotient is nonzero only if each factor is.
        declared.extend(nonconstant_factors(expr))

    failed = False
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        step_id = str(step.get("id", index)) if isinstance(step, dict) else str(index)
        errors: list[str] = []
        try:
            if not isinstance(step, dict):
                raise CheckError("step must be an object")
            unknown_step_keys = sorted(set(step) - STEP_KEYS)
            if unknown_step_keys:
                errors.append(f"unknown step keys: {unknown_step_keys} (allowed: {sorted(STEP_KEYS)})")
            for field in ("id", "before", "after", "law", "applicability"):
                if field not in step or not isinstance(step[field], str) or not step[field].strip():
                    errors.append(f"missing nonempty {field}")
            if errors:
                raise CheckError("; ".join(errors))
            before_l, before_r = parse_equation(step["before"], parser)
            after_l, after_r = parse_equation(step["after"], parser)
            factor = parser.parse(step.get("factor", "1"))
            if is_identically_zero(factor):
                errors.append("equivalence factor must be nonzero")

            for label, left, right in (
                ("before", before_l, before_r),
                ("after", after_l, after_r),
            ):
                # A side that is identically 0 matches any dimension, but the
                # other side must still be consistent on its own.
                left_dim = None if is_identically_zero(left) else dimension(left, dimensions)
                right_dim = None if is_identically_zero(right) else dimension(right, dimensions)
                if left_dim is not None and right_dim is not None and left_dim != right_dim:
                    errors.append(
                        f"{label} equation has mismatched dimensions: {format_dim(left_dim)} != {format_dim(right_dim)}"
                    )

            undeclared = [
                str(item) for item in nonconstant_factors(factor) if not is_declared_nonzero(item, declared)
            ]
            if undeclared:
                errors.append(
                    f"factor {factor} has factors not declared nonzero: {undeclared}"
                    " (list each in nonzero; declaring m1 and m2 does not declare m1 - m2)"
                )
            difference = sp.simplify((before_l - before_r) - factor * (after_l - after_r))
            if difference != 0:
                errors.append(f"residuals are not equivalent; remaining expression: {difference}")
        except CheckError as exc:
            if str(exc) not in errors:
                errors.append(str(exc))

        if errors:
            failed = True
            lines.append(f"FAIL step {step_id}")
            lines.extend(f"  - {error}" for error in errors)
        else:
            lines.append(f"PASS step {step_id}: algebra and dimensions; physical applicability not checked")
    return failed, lines


# ---------------------------------------------------------------- self-test

_SPRING = {"m": {"M": 1}, "g": {"L": 1, "T": -2}, "k": {"M": 1, "T": -2}, "x": {"L": 1}}
_MASSES = {"m1": {"M": 1}, "m2": {"M": 1}, "v": {"L": 1, "T": -1}, "p": {"M": 1, "L": 1, "T": -1}}


def _step(before: str, after: str, factor: str = "1", step_id: str = "s") -> dict:
    return {"id": step_id, "before": before, "after": after, "factor": factor,
            "law": "test", "applicability": "test"}


def _divide(nonzero: list[str]) -> dict:
    return {"symbols": _MASSES, "nonzero": nonzero,
            "steps": [_step("(m1-m2)*v = (m1-m2)*p/m1", "v = p/m1", "m1-m2")]}


# (label, input, expected: "PASS" / "FAIL" / "ERROR", substring that must appear)
SELFTEST_CASES = [
    ("schema example (normal case)",
     {"symbols": {"F": {"M": 1, "L": 1, "T": -2}, "m": {"M": 1}, "a": {"L": 1, "T": -2}},
      "nonzero": ["m"], "steps": [_step("F = m*a", "a = F/m", "-m")]}, "PASS", "PASS step s"),
    ("'... = 0' form is dimensionally consistent",
     {"symbols": _SPRING, "nonzero": ["k"], "steps": [_step("m*g - k*x = 0", "x = m*g/k", "-k")]},
     "PASS", "PASS step s"),
    ("'0 = ...' form is dimensionally consistent",
     {"symbols": _SPRING, "steps": [_step("0 = m*g - k*x", "k*x = m*g")]}, "PASS", "PASS step s"),
    ("zero side does not hide an inconsistent other side",
     {"symbols": _SPRING, "steps": [_step("m*g - k = 0", "m*g - k = 0")]},
     "FAIL", "addition combines unlike dimensions"),
    ("10**m with dimensioned m is rejected",
     {"symbols": {"y": {}, "m": {"M": 1}}, "steps": [_step("y = 10**m", "y = 10**m")]},
     "FAIL", "exponent must be dimensionless"),
    ("2**(-m) with dimensioned m is rejected",
     {"symbols": {"y": {}, "m": {"M": 1}}, "steps": [_step("y = 2**(-m)", "y = 2**(-m)")]},
     "FAIL", "exponent must be dimensionless"),
    ("half-life form 2**(-t/T) passes",
     {"symbols": {"N": {}, "N0": {}, "t": {"T": 1}, "T": {"T": 1}}, "nonzero": ["N0"],
      "steps": [_step("N = N0*2**(-t/T)", "N/N0 = 2**(-t/T)", "N0")]}, "PASS", "PASS step s"),
    ("dividing by m1-m2 needs more than m1, m2 nonzero", _divide(["m1", "m2"]),
     "FAIL", "not declared nonzero: ['m1 - m2']"),
    ("dividing by m1-m2 passes once m1-m2 is declared", _divide(["m1", "m2", "m1 - m2"]),
     "PASS", "PASS step s"),
    ("a declared product declares each factor", _divide(["m1**2 - m2**2"]), "PASS", "PASS step s"),
    ("declaring m1 - m2 also covers the factor m2 - m1",
     {"symbols": _MASSES, "nonzero": ["m1 - m2"],
      "steps": [_step("(m2-m1)*v = (m2-m1)*p/m1", "v = p/m1", "m2-m1")]}, "PASS", "PASS step s"),
    ("provably nonzero factor exp(x) needs no declaration",
     {"symbols": {"x": {}, "y": {"L": 1}, "z": {"L": 1}},
      "steps": [_step("y*exp(x) = z*exp(x)", "y = z", "exp(x)")]}, "PASS", "PASS step s"),
    ("symbol-only nonzero still works for a product factor",
     {"symbols": {"m": {"M": 1}, "k": {"M": 1, "T": -2}, "x": {"L": 1}, "y": {"L": 1}},
      "nonzero": ["m", "k"], "steps": [_step("2*m*k*x = 2*m*k*y", "x = y", "2*m*k")]},
     "PASS", "PASS step s"),
    ("sign error is caught (tests/cases Case 3)",
     {"symbols": {"F": {"M": 1, "L": 1, "T": -2}, "m": {"M": 1}, "a": {"L": 1, "T": -2}},
      "nonzero": ["m"], "steps": [_step("F = m*a", "a = F*m", "-m")]}, "FAIL", "mismatched dimensions"),
    ("unknown top-level key is an input error",
     {"symbols": {"x": {}}, "nonezero": [], "steps": [_step("x = 1", "x = 1")]}, "ERROR", "unknown top-level keys"),
    ("unknown symbol in nonzero is an input error",
     {"symbols": {"x": {}}, "nonzero": ["q"], "steps": [_step("x = 1", "x = 1")]}, "ERROR", "unknown symbol: q"),
    ("division by zero is rejected",
     {"symbols": {"x": {}}, "steps": [_step("x = 1/0", "x = 1/0")]}, "FAIL", "divides by zero"),
]


def selftest() -> int:
    passed = 0
    for label, data, expected, needle in SELFTEST_CASES:
        try:
            failed, lines = check_document(data)
            outcome, text = ("FAIL" if failed else "PASS"), "\n".join(lines)
        except CheckError as exc:
            outcome, text = "ERROR", str(exc)
        if outcome == expected and needle in text:
            passed += 1
            print(f"  pass  {label}")
        else:
            print(f"  FAIL  {label}: got {outcome}, expected {expected} with {needle!r}\n{text}")
    total = len(SELFTEST_CASES)
    print(f"selftest {'passed' if passed == total else 'FAILED'} ({passed}/{total})")
    return 0 if passed == total else 1


def main(argv: list[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(
        prog="check_derivation.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    arg_parser.add_argument("input", type=Path, nargs="?", help="derivation JSON file")
    arg_parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = arg_parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.input is None:
        arg_parser.error("an input file is required unless --selftest is given")

    try:
        failed, lines = check_document(load_input(args.input))
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
