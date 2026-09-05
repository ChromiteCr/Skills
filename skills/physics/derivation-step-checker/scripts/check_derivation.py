#!/usr/bin/env python3
"""Check constrained scalar derivation steps for algebra and dimensions."""

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
        return self.visit(tree.body)

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
    if expr.func == sp.sqrt:
        return add_dim({}, dimension(expr.args[0], dimensions), Fraction(1, 2))
    if expr.func in DIMENSIONLESS_FUNCTIONS:
        arg_dim = dimension(expr.args[0], dimensions)
        if arg_dim:
            raise CheckError(f"{expr.func.__name__} requires a dimensionless argument in {expr}")
        return {}
    raise CheckError(f"cannot determine dimensions of {expr}")


def parse_equation(text: object, parser: ExpressionParser) -> tuple[sp.Expr, sp.Expr]:
    if not isinstance(text, str) or text.count("=") != 1:
        raise CheckError("equation must contain exactly one '='")
    left, right = text.split("=", 1)
    return parser.parse(left), parser.parse(right)


def load_input(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CheckError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CheckError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def main() -> int:
    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("input", type=Path, help="derivation JSON file")
    args = arg_parser.parse_args()

    try:
        data = load_input(args.input)
        if not isinstance(data, dict):
            raise CheckError("top-level JSON value must be an object")
        raw_symbols = data.get("symbols")
        steps = data.get("steps")
        nonzero = data.get("nonzero", [])
        if not isinstance(raw_symbols, dict) or not raw_symbols:
            raise CheckError("symbols must be a nonempty object")
        if not isinstance(steps, list) or not steps:
            raise CheckError("steps must be a nonempty list")
        if not isinstance(nonzero, list) or any(not isinstance(item, str) for item in nonzero):
            raise CheckError("nonzero must be a list of symbol names")
        invalid_names = [name for name in raw_symbols if not isinstance(name, str) or not name.isidentifier()]
        if invalid_names:
            raise CheckError(f"invalid symbol names: {invalid_names}")

        symbols = {name: sp.Symbol(name) for name in raw_symbols}
        unknown_nonzero = sorted(set(nonzero) - set(symbols))
        if unknown_nonzero:
            raise CheckError(f"nonzero contains unknown symbols: {unknown_nonzero}")
        dimensions: dict[sp.Symbol, dict[str, Fraction]] = {}
        for name, raw_dim in raw_symbols.items():
            if not isinstance(raw_dim, dict):
                raise CheckError(f"dimension vector for {name} must be an object")
            dimensions[symbols[name]] = clean_dim({str(key): parse_number(value) for key, value in raw_dim.items()})

        parser = ExpressionParser(symbols)
        failed = False
        for index, step in enumerate(steps, start=1):
            step_id = str(step.get("id", index)) if isinstance(step, dict) else str(index)
            errors: list[str] = []
            try:
                if not isinstance(step, dict):
                    raise CheckError("step must be an object")
                for field in ("id", "before", "after", "law", "applicability"):
                    if field not in step or not isinstance(step[field], str) or not step[field].strip():
                        errors.append(f"missing nonempty {field}")
                if errors:
                    raise CheckError("; ".join(errors))
                before_l, before_r = parse_equation(step["before"], parser)
                after_l, after_r = parse_equation(step["after"], parser)
                factor = parser.parse(step.get("factor", "1"))
                if sp.simplify(factor) == 0:
                    errors.append("equivalence factor must be nonzero")

                for label, left, right in (
                    ("before", before_l, before_r),
                    ("after", after_l, after_r),
                ):
                    left_dim, right_dim = dimension(left, dimensions), dimension(right, dimensions)
                    if left_dim != right_dim:
                        errors.append(f"{label} equation has mismatched dimensions: {left_dim} != {right_dim}")

                undeclared = sorted(str(sym) for sym in factor.free_symbols if str(sym) not in nonzero)
                if undeclared:
                    errors.append(f"factor symbols not declared nonzero: {undeclared}")
                difference = sp.simplify((before_l - before_r) - factor * (after_l - after_r))
                if difference != 0:
                    errors.append(f"residuals are not equivalent; remaining expression: {difference}")
            except CheckError as exc:
                errors.append(str(exc))

            if errors:
                failed = True
                print(f"FAIL step {step_id}")
                for error in errors:
                    print(f"  - {error}")
            else:
                print(f"PASS step {step_id}: algebra and dimensions; physical applicability not checked")

        return 1 if failed else 0
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
