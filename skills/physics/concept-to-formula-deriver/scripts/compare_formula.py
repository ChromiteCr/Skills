#!/usr/bin/env python3
"""Compare two symbolic expressions, or two equations, for equivalence.

Usage:
    python3 compare_formula.py --derived "sqrt(2*G*M/R)" --reference "(2*G*M/R)**0.5"
    python3 compare_formula.py --derived "Eq(2*pi*sqrt(L/g), T)" --reference "Eq(T, 2*pi*sqrt(L/g))"
    python3 compare_formula.py --derived "sqrt(q**2)" --reference "q" --real q
    python3 compare_formula.py --selftest

Requires sympy.

How input is read:
  - Every name is a plain symbol, including E, I, N, Q, S, gamma, beta and lambda.
    The only constant is pi (also written as the Greek letter pi); write Euler's
    number as exp(1). Names are compared after Unicode NFKC normalisation, so the
    micro sign and the Greek mu are the same symbol.
  - Known functions: sqrt, cbrt, exp, log (natural), ln, log10, sin, cos, tan,
    cot, sec, csc, asin, acos, atan, atan2, sinh, cosh, tanh, asinh, acosh,
    atanh, Abs, abs, sign, Eq. Any other name followed by "(" is an error.
  - Every symbol is assumed positive, which is what lets L*sqrt(g/L) equal
    sqrt(g*L). Name the symbols that can be negative or zero with --real
    (comma separated); they are then only assumed real.
  - Decimals are exact fractions (0.5 is 1/2). Powers are ** or ^; superscript
    characters are rejected. Products need an explicit *.
  - An equation is written Eq(lhs, rhs). Two equations are equivalent when their
    residuals lhs - rhs differ only by a nonzero constant factor, so swapping the
    sides is fine. Equations rearranged by squaring (T = ... against
    T**2 = ...) are not constant multiples; compare the expressions for the
    target quantity instead.

Verdicts and exit status:
  0  equivalent: yes           the difference simplifies to 0 (equations: the
                               residual ratio is a nonzero constant)
  1  equivalent: no            a numerical counterexample was found and is printed
  2  input error               unparsable input, unknown function, bad option;
                               one line on stderr
  3  equivalent: undetermined  simplification did not reach 0, but no
                               counterexample was found at the sample points

This is a lightweight deterministic check. It does not prove that a derivation
is physically justified; it only checks symbolic equivalence.
"""

from __future__ import annotations

import argparse
import io
import random
import sys
import tokenize
import unicodedata

try:
    import sympy as sp
except Exception as exc:  # pragma: no cover - import failure path is user-facing
    print(f"ERROR: sympy is required for symbolic comparison ({exc}).", file=sys.stderr)
    sys.exit(2)

EXIT_YES, EXIT_NO, EXIT_INPUT, EXIT_UNDETERMINED = 0, 1, 2, 3

FUNCTIONS = {
    "sqrt": sp.sqrt, "cbrt": sp.cbrt, "exp": sp.exp, "log": sp.log, "ln": sp.log,
    "log10": lambda x: sp.log(x, 10),
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan, "atan2": sp.atan2,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
    "Abs": sp.Abs, "abs": sp.Abs, "sign": sp.sign,
    # Kept unevaluated so the positivity assumption cannot turn Eq(F, 0) into False.
    "Eq": lambda lhs, rhs: sp.Eq(lhs, rhs, evaluate=False),
}
CONSTANTS = {"pi": sp.pi, "π": sp.pi}
OPERATORS = {"+", "-", "*", "/", "**", "^", "(", ")", ","}
SUPERSCRIPTS = {"¹", "²", "³"} | {chr(c) for c in range(0x2070, 0x2080)}
SKIPPED_TOKENS = {tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT}
SAMPLE_POINTS = 8
RELATIVE_TOLERANCE = 1e-9


class InputError(Exception):
    """Input that cannot be compared; reported on one line with exit status 2."""


class _Printer(sp.printing.str.StrPrinter):
    """Print Euler's number and the imaginary unit so they cannot be mistaken for symbols E and I."""

    def _print_Exp1(self, expr):
        return "exp(1)"

    def _print_ImaginaryUnit(self, expr):
        return "sqrt(-1)"


def _text(expr) -> str:
    return _Printer().doprint(expr)


def _rewrite(text: str, label: str) -> tuple[str, set[str]]:
    """Turn the input into Python code over placeholders; return (code, symbol names)."""
    if not text.strip():
        raise InputError(f"{label} is empty")
    superscripts = sorted({ch for ch in text if ch in SUPERSCRIPTS})
    if superscripts:
        raise InputError(f"{label}: superscript characters {''.join(superscripts)} are not read as "
                         "powers; write x**2 or x^2")
    text = unicodedata.normalize("NFKC", text.strip())
    try:
        tokens = [tok for tok in tokenize.generate_tokens(io.StringIO(text).readline)
                  if tok.type not in SKIPPED_TOKENS]
    except (tokenize.TokenError, SyntaxError) as exc:
        raise InputError(f"{label}: cannot parse ({exc.args[0] if exc.args else exc})") from None

    parts: list[str] = []
    names: set[str] = set()
    for index, tok in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        is_call = following is not None and following.string == "("
        if tok.type == tokenize.NAME:
            name = tok.string
            if not name.isidentifier():
                raise InputError(f"{label}: unsupported character in {name!r}; use * for products "
                                 "and sqrt() for roots")
            if name in FUNCTIONS:
                if not is_call:
                    raise InputError(f"{label}: '{name}' is a function; write {name}(...)")
                parts.append(f"_F[{name!r}]")
            elif name in CONSTANTS:
                if is_call:
                    raise InputError(f"{label}: '{name}' is a constant, not a function")
                parts.append(f"_C[{name!r}]")
            else:
                if is_call:
                    raise InputError(f"{label}: '{name}(...)' is not a supported function (for a product "
                                     f"write {name}*(...)); supported: " + ", ".join(sorted(FUNCTIONS)))
                names.add(name)
                parts.append(f"_S[{name!r}]")
        elif tok.type == tokenize.NUMBER:
            try:
                sp.Rational(tok.string)
            except (TypeError, ValueError):
                raise InputError(f"{label}: unsupported number {tok.string!r}") from None
            parts.append(f"_R({tok.string!r})")
        elif tok.type == tokenize.OP and tok.string in OPERATORS:
            parts.append("**" if tok.string == "^" else tok.string)
        elif tok.type == tokenize.OP and tok.string == "=":
            raise InputError(f"{label}: write an equation as Eq(lhs, rhs), not lhs = rhs")
        else:
            raise InputError(f"{label}: unsupported token {tok.string!r}")
    return " ".join(parts), names


def _evaluate(code: str, symbols: dict[str, sp.Symbol], label: str):
    namespace = {"_F": FUNCTIONS, "_C": CONSTANTS, "_S": symbols, "_R": sp.Rational}
    try:
        value = eval(code, {"__builtins__": {}}, namespace)  # noqa: S307 - code is built from whitelisted tokens only
    except SyntaxError:
        raise InputError(f"{label}: invalid syntax (use * for products and ** or ^ for powers)") from None
    except Exception as exc:
        raise InputError(f"{label}: cannot evaluate ({exc})") from None
    if isinstance(value, sp.logic.boolalg.BooleanAtom):
        raise InputError(f"{label}: the equation is identically {value}; nothing to compare")
    if isinstance(value, sp.Equality):
        return value
    if not isinstance(value, sp.Expr):
        raise InputError(f"{label}: expected one expression or one Eq(lhs, rhs)")
    if value.has(sp.zoo, sp.oo, -sp.oo, sp.nan):
        raise InputError(f"{label}: the expression is not finite (division by zero?)")
    return value


def _sample_points(symbols: dict[str, sp.Symbol], real: set[str]) -> list[dict]:
    """Fixed pseudo-random points: positive symbols in [0.5, 3]; real symbols of both signs."""
    rng = random.Random(20260926)
    points = []
    for index in range(SAMPLE_POINTS):
        point = {}
        for name in sorted(symbols):
            magnitude = sp.Rational(str(round(rng.uniform(0.5, 3.0), 3)))
            if name in real:
                negative = index == 0 or (index > 1 and rng.random() < 0.5)
                magnitude = -magnitude if negative else magnitude
            point[symbols[name]] = magnitude
        points.append(point)
    return points


def _number(expr, point) -> complex | None:
    try:
        value = expr.evalf(30, subs=point)
        if value.has(sp.zoo, sp.oo, -sp.oo, sp.nan) or not value.is_number:
            return None
        return complex(value)
    except (TypeError, ValueError, ZeroDivisionError, ArithmeticError):
        return None


def _close(a: complex, b: complex) -> bool:
    return abs(a - b) <= RELATIVE_TOLERANCE * max(abs(a), abs(b), 1e-30)


def _show(point) -> str:
    return ", ".join(f"{sym}={float(value):g}" for sym, value in sorted(point.items(), key=lambda kv: str(kv[0])))


def _fmt(value: complex) -> str:
    return f"{value.real:.6g}" if abs(value.imag) <= 1e-12 * max(abs(value), 1e-30) else f"{value:.6g}"


def _check_expressions(derived, reference, points, lines) -> int:
    difference = sp.simplify(derived - reference)
    lines.append(f"difference: {_text(difference)}")
    if difference == 0 or difference.is_zero is True:
        lines.append("equivalent: yes")
        return EXIT_YES
    valid = 0
    for point in points:
        d, r = _number(derived, point), _number(reference, point)
        if d is None or r is None:
            continue
        valid += 1
        if not _close(d, r):
            lines.append("equivalent: no")
            lines.append(f"counterexample: at {_show(point)}: derived = {_fmt(d)}, reference = {_fmt(r)}")
            return EXIT_NO
    lines.append("equivalent: undetermined")
    lines.append(f"note: simplification did not reduce the difference to 0, but the two sides agree at "
                 f"{valid} sample point(s); check by hand before calling them different")
    return EXIT_UNDETERMINED


def _check_equations(derived, reference, points, lines) -> int:
    residuals = []
    for label, equation in (("--derived", derived), ("--reference", reference)):
        residual = sp.simplify(equation.lhs - equation.rhs)
        if residual == 0:
            raise InputError(f"{label}: the equation is an identity (lhs - rhs simplifies to 0)")
        residuals.append(residual)
    derived_residual, reference_residual = residuals
    ratio = sp.simplify(derived_residual / reference_residual)
    lines.append(f"residual_ratio: {_text(ratio)}")
    if not ratio.free_symbols and ratio.is_number and ratio.is_finite and ratio.is_zero is False:
        lines.append("equivalent: yes")
        return EXIT_YES
    values = []
    for point in points:
        d, r = _number(derived_residual, point), _number(reference_residual, point)
        if d is not None and r is not None:
            values.append((point, d, r))
    anchor = max(values, key=lambda item: abs(item[2]), default=None)
    if len(values) >= 3 and anchor is not None and abs(anchor[2]) > 0:
        factor = anchor[1] / anchor[2]
        for point, d, r in values:
            if not _close(d, factor * r):
                lines.append("equivalent: no")
                lines.append(f"counterexample: residual ratio is {_fmt(factor)} at {_show(anchor[0])} "
                             f"but derived residual = {_fmt(d)}, reference residual = {_fmt(r)} "
                             f"at {_show(point)}")
                lines.append("note: residuals that are not constant multiples can still describe the same "
                             "relation after squaring or other rearrangement; compare the expressions for "
                             "the target quantity in that case")
                return EXIT_NO
    lines.append("equivalent: undetermined")
    lines.append("note: simplification did not show a constant residual ratio, and no counterexample "
                 "was found at the sample points; check by hand")
    return EXIT_UNDETERMINED


def compare(derived_text: str, reference_text: str, real_names: set[str] | None = None) -> tuple[int, list[str]]:
    """Return (exit status, report lines). Raise InputError for input that cannot be compared."""
    derived_code, derived_names = _rewrite(derived_text, "--derived")
    reference_code, reference_names = _rewrite(reference_text, "--reference")
    all_names = derived_names | reference_names
    real = {unicodedata.normalize("NFKC", name) for name in (real_names or set())}
    unknown = sorted(real - all_names)
    if unknown:
        raise InputError(f"--real names not found in either expression: {', '.join(unknown)}")
    symbols = {name: sp.Symbol(name, real=True) if name in real else sp.Symbol(name, positive=True)
               for name in all_names}
    derived = _evaluate(derived_code, symbols, "--derived")
    reference = _evaluate(reference_code, symbols, "--reference")
    is_equation = isinstance(derived, sp.Equality)
    if is_equation != isinstance(reference, sp.Equality):
        raise InputError("one input is an equation and the other an expression; compare like with like")

    assumed = "every symbol positive"
    if real:
        assumed += f" except {', '.join(sorted(real))} (real, sign unknown)"
    lines = [f"mode: {'equation (lhs - rhs compared up to a nonzero constant factor)' if is_equation else 'expression'}",
             f"assumptions: {assumed}"]
    if is_equation:
        lines.append(f"derived_normalized: {_text(sp.simplify(derived.lhs - derived.rhs))}")
        lines.append(f"reference_normalized: {_text(sp.simplify(reference.lhs - reference.rhs))}")
    else:
        lines.append(f"derived_normalized: {_text(sp.simplify(derived))}")
        lines.append(f"reference_normalized: {_text(sp.simplify(reference))}")
    points = _sample_points(symbols, real)
    checker = _check_equations if is_equation else _check_expressions
    status = checker(derived, reference, points, lines)
    for label, only in (("--derived", derived_names - reference_names),
                        ("--reference", reference_names - derived_names)):
        if only:
            lines.append(f"note: symbols only in {label}: {', '.join(sorted(only))}")
    return status, lines


SELFTEST_CASES = [
    # (label, derived, reference, real names, expected exit status)
    ("docstring example: float exponent", "sqrt(2*G*M/R)", "(2*G*M/R)**0.5", "", EXIT_YES),
    ("docstring example: same equation", "Eq(T, 2*pi*sqrt(L/g))", "Eq(T, 2*pi*sqrt(L/g))", "", EXIT_YES),
    ("equation sides swapped", "Eq(2*pi*sqrt(L/g), T)", "Eq(T, 2*pi*sqrt(L/g))", "", EXIT_YES),
    ("equation scaled by a constant", "Eq(2*T, 4*pi*sqrt(L/g))", "Eq(T, 2*pi*sqrt(L/g))", "", EXIT_YES),
    ("positive symbols let roots combine", "L*sqrt(g/L)", "sqrt(g*L)", "", EXIT_YES),
    ("tests Case 4: (L/g)**(1/2)", "2*pi*(L/g)**(1/2)", "2*pi*sqrt(L/g)", "", EXIT_YES),
    ("caret power", "(2*G*M/R)^(1/2)", "sqrt(2*G*M/R)", "", EXIT_YES),
    ("I is a current, not the imaginary unit", "I**2*R", "-R", "", EXIT_NO),
    ("E is an energy, not Euler's number", "E", "exp(1)", "", EXIT_NO),
    ("N parses as a symbol", "mu*N", "N*mu", "", EXIT_YES),
    ("Q parses as a symbol", "Q/T", "Q*T**-1", "", EXIT_YES),
    ("S parses as a symbol", "S*T", "T*S", "", EXIT_YES),
    ("gamma parses as a symbol", "gamma*m*c**2", "m*c**2*gamma", "", EXIT_YES),
    ("beta parses as a symbol", "beta*x", "x*beta", "", EXIT_YES),
    ("lambda parses as a symbol", "h*c/lambda", "c*h/lambda", "", EXIT_YES),
    ("micro sign equals Greek mu", "µ*x", "μ*x", "", EXIT_YES),
    ("Greek pi is the constant", "2*π*sqrt(L/g)", "2*pi*sqrt(L/g)", "", EXIT_YES),
    ("really different formulas", "sqrt(2*G*M/R)", "sqrt(G*M/R)", "", EXIT_NO),
    ("Eq(x,0) is not Eq(x*y,0)", "Eq(x, 0)", "Eq(x*y, 0)", "", EXIT_NO),
    ("signed symbol declared with --real", "sqrt(q**2)", "q", "q", EXIT_NO),
    ("same pair with default positive symbols", "sqrt(q**2)", "q", "", EXIT_YES),
    ("decimal approximation of 2*pi", "2*pi", "6.283185307179586", "", EXIT_UNDETERMINED),
    ("parse failure a+", "a+", "a", "", EXIT_INPUT),
    ("unknown function", "f(x)", "x", "", EXIT_INPUT),
    ("equation against expression", "Eq(T, 2*pi*sqrt(L/g))", "2*pi*sqrt(L/g)", "", EXIT_INPUT),
    ("single = instead of Eq", "T = 2*pi*sqrt(L/g)", "Eq(T, 2*pi*sqrt(L/g))", "", EXIT_INPUT),
    ("superscript power", "x²", "x**2", "", EXIT_INPUT),
    ("implicit product", "2x", "2*x", "", EXIT_INPUT),
    ("--real names a missing symbol", "x", "x", "y", EXIT_INPUT),
    ("identity equation", "Eq(x, x)", "Eq(x, 1)", "", EXIT_INPUT),
]


def _real_names(raw: str) -> set[str]:
    return {name.strip() for name in raw.replace(" ", ",").split(",") if name.strip()}


def selftest() -> int:
    failures = 0
    for label, derived, reference, real, expected in SELFTEST_CASES:
        try:
            status, _ = compare(derived, reference, _real_names(real))
        except InputError:
            status = EXIT_INPUT
        ok = status == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}: exit {status}" + ("" if ok else f", expected {expected}"))
    total = len(SELFTEST_CASES)
    print(f"selftest: {total - failures}/{total} passed")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two symbolic expressions or two Eq(lhs, rhs) equations for equivalence.",
        epilog="exit status: 0 equivalent, 1 not equivalent (counterexample printed), "
               "2 input error, 3 undetermined. Every symbol is assumed positive unless listed in --real.")
    parser.add_argument("--derived", help="derived expression or Eq(lhs, rhs)")
    parser.add_argument("--reference", help="reference expression or Eq(lhs, rhs)")
    parser.add_argument("--real", default="", metavar="NAMES",
                        help="comma-separated symbols that may be negative or zero (default: all positive)")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.derived is None or args.reference is None:
        parser.error("--derived and --reference are both required (or use --selftest)")
    try:
        status, lines = compare(args.derived, args.reference, _real_names(args.real))
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except Exception as exc:  # sympy internals; never report a crash as "not equivalent"
        print(f"ERROR: could not compare: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INPUT
    print("\n".join(lines))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
