#!/usr/bin/env python3
"""dimcheck.py — 量纲一致性检查器 / dimensional consistency checker.

只用 Python 标准库。给一份符号量纲表和若干表达式或方程，确定性地回答三件事：

1. 每个表达式的量纲是什么，与声明的期望是否一致；
2. 加减号两侧、等号两边的量纲是否相同（不同就是漏项、多项或抄错）；
3. 指数、对数、三角函数的宗量，以及含符号的幂指数，是否无量纲（这是最常见的隐藏错误）。

它**不判断物理是否正确**。量纲通过只说明这条式子还没被最便宜的一关筛掉。

输入文件格式（`#` 起注释，空行忽略）::

    [symbols]
    rho = M L^-3
    U   = L T^-1
    L   = L
    mu  = M L^-1 T^-1
    g   = L T^-2
    h   = L

    [check]
    Re      = rho*U*L/mu            ; 1
    inertia = rho*U^2*L^2           ; M L T^-2
    viscous = mu*U*L
    rho*g*h == 1/2*rho*U^2
    bern    = rho*g*h == 1/2*rho*U^2

    [compare]
    inertia viscous

[symbols] 每行 `符号 = 量纲`。基本量纲：`M` 质量、`L` 长度、`T` 时间、`I` 电流、
`K` 热力学温度、`N` 物质的量、`J` 发光强度。无量纲写 `1`。量纲写法里的指数可为
整数或分数，`L^1/2` 是 L 的 1/2 次方。同一个符号声明两次且量纲不同，算输入错误。

[check] 每行一条，行尾可加 `; 期望量纲`：

- `名字 = 表达式`：名字既不在 [symbols] 里、也没被前面的 [check] 行定义过时，这一行
  是定义：算出表达式的量纲记在这个名字下，后面的行和 [compare] 可以引用它。
- `左边 == 右边`：方程，两边量纲必须相同。写成 `左边 = 右边` 也按方程查，除非左边
  只是一个新名字（那就是上一条的定义）；左边是已声明的符号时照样比较两边。
- `名字 = 左边 == 右边`：带名字的方程；两边一致时，名字记为两边共同的量纲。
- `<`、`>`、`<=`、`>=` 连起来的不等式同样要求两边量纲相同。
- 一边写成 `0` 的方程（`m*g - k*x == 0`）只查另一边内部是否自洽。

表达式支持 `+ - * /`、乘方 `^` 或 `**`、括号，以及函数 sqrt、abs 和
exp、log、ln、log10、log2、sin、cos、tan、asin、acos、atan、sinh、cosh、tanh、erf
（后面这一组的宗量必须无量纲）。`pi`（或 `π`）是内置的无量纲常数，除非 [symbols]
里声明了同名符号。幂指数含符号时（如 `2^(-t/T)`），指数和底数都必须无量纲。

**表达式里的分数指数必须加括号**，写 `x^(1/2)`。乘方后面紧跟"数字/数字"
（`x^1/2`、`v^2/2`、`x**3/2`）有歧义，一律按输入错误拒绝；先乘方再除以常数请写
`(v^2)/2` 或 `1/2*v^2`。

符号名按 NFKC 归一化后比较，与 Python 解析表达式时一致：`µ`（U+00B5 微符号）与
希腊字母 `μ` 是同一个名字，`ℓ` 与 `l`、全角 `ｖ` 与 `v` 也是。

[compare] 每行至少两个名字，断言它们量纲相同、可以直接比大小。

用法::

    python3 dimcheck.py problem.dim
    python3 dimcheck.py < problem.dim
    python3 dimcheck.py --selftest

退出状态：0 表示全部通过；1 表示存在量纲不一致（含用了没声明的符号）；2 表示输入
本身无法解析（语法错误、不认识的函数、有歧义的写法、名字冲突、空输入），这时不做
任何检查。只有 [symbols]、没有 [check] 和 [compare] 时只核对量纲写法，退出状态 0，
结果行写明没有检查任何式子。
"""

import argparse
import ast
import io
import keyword
import math
import re
import sys
import unicodedata
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction

BASE = ("M", "L", "T", "I", "K", "N", "J")

# 宗量必须无量纲、结果也无量纲的函数。
TRANSCENDENTAL = {
    "exp", "log", "ln", "log10", "log2",
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "erf",
}
# 只接受一个参数的函数：sqrt 取 1/2 次方，abs 保持量纲。
ONE_ARG = {"sqrt", "abs"}
# 内置无量纲常数；[symbols] 里声明了同名符号时以声明为准。
BUILTIN_CONSTANTS = ("pi", "π")

# [check] 里的关系符。长的写在前面，`==` 不会被拆成两个 `=`。
RELATION = re.compile(r"(==|<=|>=|≤|≥|=|<|>)")
# 乘方后紧跟"数字/数字"：`x^1/2` 是 (x^1)/2 还是 x^(1/2)？一律要求加括号。
AMBIGUOUS_POWER = re.compile(
    r"(?:\^|\*\*)\s*[+-]?\s*(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*/\s*[+-]?\s*\.?\d"
)


class InputError(Exception):
    """输入无法解析：退出状态 2，不做任何检查。"""


class DimError(Exception):
    """量纲不一致或用了没声明的符号：退出状态 1。"""


class Dim:
    """基本量纲指数向量。"""

    __slots__ = ("e",)

    def __init__(self, e=None):
        self.e = {}
        for k, v in (e or {}).items():
            v = Fraction(v)
            if v:
                self.e[k] = v

    def __eq__(self, other):
        return isinstance(other, Dim) and self.e == other.e

    def __hash__(self):
        return hash(tuple(sorted(self.e.items())))

    @property
    def dimensionless(self):
        return not self.e

    def __mul__(self, other):
        out = dict(self.e)
        for k, v in other.e.items():
            out[k] = out.get(k, Fraction(0)) + v
        return Dim(out)

    def __truediv__(self, other):
        out = dict(self.e)
        for k, v in other.e.items():
            out[k] = out.get(k, Fraction(0)) - v
        return Dim(out)

    def __pow__(self, n):
        n = Fraction(n)
        return Dim({k: v * n for k, v in self.e.items()})

    def __str__(self):
        if not self.e:
            return "1"
        parts = []
        for k in BASE:
            if k in self.e:
                v = self.e[k]
                parts.append(k if v == 1 else "%s^%s" % (k, v))
        for k in sorted(self.e):  # 非标准基（不应出现，但不静默丢弃）
            if k not in BASE:
                parts.append("%s^%s" % (k, self.e[k]))
        return " ".join(parts)


DIMLESS = Dim()

_TERM = re.compile(r"^([A-Za-z]+)(?:\^(-?\d+(?:/\d+)?))?$")


def norm(name):
    """名字按 NFKC 归一化，与 Python 解析标识符时的做法一致。"""
    return unicodedata.normalize("NFKC", name)


def parse_dim(text, where=""):
    """把 'M L^-3' 解析成 Dim。"""
    text = text.strip()
    if text in ("1", "-", ""):
        return DIMLESS
    out = {}
    for token in text.replace("*", " ").split():
        m = _TERM.match(token)
        if not m:
            raise InputError("%s无法解析量纲片段 %r" % (where, token))
        sym, exp = m.group(1), m.group(2)
        if sym not in BASE:
            raise InputError(
                "%s未知基本量纲 %r（可用：%s）" % (where, sym, " ".join(BASE))
            )
        out[sym] = out.get(sym, Fraction(0)) + Fraction(exp if exp else 1)
    return Dim(out)


def _check_name(name):
    if not name.isidentifier():
        raise InputError("%r 不是合法的名字" % name)
    if keyword.iskeyword(name) or keyword.iskeyword(norm(name)):
        raise InputError(
            "%r 是 Python 关键字，不能当名字（例如 lambda 改写成 lam 或 λ）" % name
        )


# ---------------------------------------------------------------- 表达式


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_zero_literal(node):
    """字面量 0（可带正负号）。0 与任何量纲相容。"""
    if isinstance(node, ast.Constant) and _is_number(node.value):
        return node.value == 0
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _is_zero_literal(node.operand)
    return False


def _const_value(node):
    """纯数字子表达式的值（用于幂指数）；含符号时返回 None。"""
    if isinstance(node, ast.Constant) and _is_number(node.value):
        return Fraction(node.value).limit_denominator(10 ** 6)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _const_value(node.operand)
        if v is None:
            return None
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ):
        a, b = _const_value(node.left), _const_value(node.right)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if b == 0:
            raise InputError("幂指数里出现除以零")
        return a / b
    return None


def _validate(node):
    """解析阶段的语法白名单：不认识的写法算输入错误（退出状态 2）。"""
    if isinstance(node, ast.Constant):
        if not _is_number(node.value):
            raise InputError("不支持的常量 %r" % (node.value,))
        if isinstance(node.value, float) and not math.isfinite(node.value):
            raise InputError("数字超出范围")
        return
    if isinstance(node, ast.Name):
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise InputError("不支持的一元运算 %s" % type(node.op).__name__)
        _validate(node.operand)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            raise InputError("不支持的运算符 %s" % type(node.op).__name__)
        _validate(node.left)
        _validate(node.right)
        if isinstance(node.op, ast.Pow):
            _const_value(node.right)  # 提前报出指数里的除以零
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise InputError("只支持形如 f(x) 的函数调用")
        fname = node.func.id
        if node.keywords:
            raise InputError("函数不接受关键字参数")
        if fname in ONE_ARG:
            if len(node.args) != 1:
                raise InputError("%s 需要恰好一个参数" % fname)
        elif fname in TRANSCENDENTAL:
            if not node.args:
                raise InputError("%s 至少需要一个参数" % fname)
        else:
            raise InputError(
                "不认识的函数 %r（可用：%s）"
                % (fname, "、".join(sorted(ONE_ARG | TRANSCENDENTAL)))
            )
        for arg in node.args:
            _validate(arg)
        return
    raise InputError("表达式里出现不支持的写法（%s）" % type(node).__name__)


def compile_expr(text):
    """把一段表达式解析成 AST；写法有问题时抛 InputError。"""
    m = AMBIGUOUS_POWER.search(text)
    if m:
        raise InputError(
            "%r 里的 %r 有歧义：是先乘方再除，还是分数次方？"
            "分数指数请加括号，如 x^(1/2)；先乘方再除请写 (v^2)/2 或 1/2*v^2"
            % (text, " ".join(m.group(0).split()))
        )
    src = text.replace("^", "**")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        hint = ""
        for word in re.findall(r"[^\W\d]\w*", text):
            if keyword.iskeyword(norm(word)):
                hint = "；%r 是 Python 关键字，不能当符号名" % word
                break
        raise InputError("表达式语法错误：%s（%s）%s" % (exc.msg, text, hint))
    _validate(tree.body)
    return tree.body


def _undeclared(trees, syms):
    """各表达式里所有没声明的符号，按出现顺序一次列全（函数名不算）。"""
    seen = []
    for tree in trees:
        func_ids = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        names = [
            n for n in ast.walk(tree) if isinstance(n, ast.Name) and id(n) not in func_ids
        ]
        for node in sorted(names, key=lambda n: n.col_offset):
            if node.id not in syms and node.id not in seen:
                seen.append(node.id)
    return seen


def _undeclared_error(names):
    hint = "（名字按 NFKC 归一化后比较）" if any(not n.isascii() for n in names) else ""
    shown = "、".join(repr(n) for n in names)
    return "符号 %s 没有在 [symbols] 里声明量纲%s" % (shown, hint)


def dim_of(node, syms):
    if isinstance(node, ast.Expression):
        return dim_of(node.body, syms)

    if isinstance(node, ast.Constant):
        return DIMLESS

    if isinstance(node, ast.Name):
        if node.id not in syms:
            raise DimError(_undeclared_error([node.id]))
        return syms[node.id]

    if isinstance(node, ast.UnaryOp):
        return dim_of(node.operand, syms)

    if isinstance(node, ast.BinOp):
        op = node.op
        if isinstance(op, ast.Pow):
            base = dim_of(node.left, syms)
            n = _const_value(node.right)
            if n is not None:
                return base ** n
            e = dim_of(node.right, syms)
            if not e.dimensionless:
                raise DimError("幂指数必须无量纲，实际是 [%s]" % e)
            if not base.dimensionless:
                raise DimError(
                    "有量纲的底数 [%s] 只能取常数次幂；指数含符号时底数必须无量纲" % base
                )
            return DIMLESS
        if isinstance(op, (ast.Add, ast.Sub)):
            if _is_zero_literal(node.left):
                return dim_of(node.right, syms)
            if _is_zero_literal(node.right):
                return dim_of(node.left, syms)
            left, right = dim_of(node.left, syms), dim_of(node.right, syms)
            if left != right:
                raise DimError(
                    "相加减的两项量纲不同：左 [%s]，右 [%s]" % (left, right)
                )
            return left
        left, right = dim_of(node.left, syms), dim_of(node.right, syms)
        if isinstance(op, ast.Mult):
            return left * right
        return left / right  # ast.Div；其余运算已在 _validate 里拒绝

    if isinstance(node, ast.Call):
        fname = node.func.id
        if fname == "sqrt":
            return dim_of(node.args[0], syms) ** Fraction(1, 2)
        if fname == "abs":
            return dim_of(node.args[0], syms)
        for arg in node.args:  # TRANSCENDENTAL
            d = dim_of(arg, syms)
            if not d.dimensionless:
                raise DimError("%s() 的宗量必须无量纲，实际是 [%s]" % (fname, d))
        return DIMLESS

    raise DimError("表达式里出现不支持的写法（%s）" % type(node).__name__)


# ---------------------------------------------------------------- 输入文件


class Check:
    """[check] 的一行：parts 是被关系符隔开的各段，ops 是关系符。"""

    __slots__ = ("lineno", "name", "parts", "ops", "trees", "expect", "text")

    def __init__(self, lineno, name, parts, ops, trees, expect, text):
        self.lineno, self.name, self.parts, self.ops = lineno, name, parts, ops
        self.trees, self.expect, self.text = trees, expect, text


def _parse_symbol(line, lineno, syms, raw_names, sym_line):
    if "=" not in line:
        raise InputError("应为 '符号 = 量纲'")
    name, _, dim_text = line.partition("=")
    name = name.strip()
    _check_name(name)
    key = norm(name)
    dim = parse_dim(dim_text)
    if key in syms:
        if raw_names[key] != name:
            raise InputError(
                "%r 与第 %d 行的 %r 按 NFKC 归一化后是同一个名字，表达式里分不开；请改名"
                % (name, sym_line[key], raw_names[key])
            )
        if syms[key] != dim:
            raise InputError(
                "符号 %r 已在第 %d 行声明为 [%s]，这里又声明为 [%s]；"
                "一个符号有两个含义时要分开命名" % (name, sym_line[key], syms[key], dim)
            )
        return
    syms[key], raw_names[key], sym_line[key] = dim, name, lineno


def _parse_check(line, lineno):
    body, expect = line, None
    if ";" in line:
        body, _, exp_text = line.partition(";")
        expect = parse_dim(exp_text, "期望量纲：")
    pieces = RELATION.split(body)
    parts = [p.strip() for p in pieces[0::2]]
    ops = pieces[1::2]
    if len(parts) < 2:
        raise InputError(
            "应为 '名字 = 表达式'、'左边 == 右边' 或 '名字 = 左边 == 右边'，"
            "行尾可加 '; 期望量纲'"
        )
    if any(not p for p in parts):
        raise InputError("关系式里有一边是空的：%r" % body.strip())
    name = None
    if ops[0] == "=" and parts[0].isidentifier():
        _check_name(parts[0])
        name = parts[0]
    trees = [compile_expr(p) for p in parts]
    return Check(lineno, name, parts, ops, trees, expect, " ".join(body.split()))


def parse_input(text):
    """返回 (syms, raw_names, checks, compares)；任何一行写法有问题都抛 InputError。"""
    syms, raw_names, sym_line = {}, {}, {}
    checks, compares, errors = [], [], []
    section = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            if line.startswith("[") and line.endswith("]"):
                name = line[1:-1].strip().lower()
                if name not in ("symbols", "check", "compare"):
                    section = "?"
                    raise InputError(
                        "未知小节 %r（可用：symbols、check、compare）" % name
                    )
                section = name
                continue
            if section is None:
                raise InputError("内容出现在任何小节之前")
            if section == "?":
                continue  # 未知小节里的行，随小节一起报过错
            if section == "symbols":
                _parse_symbol(line, lineno, syms, raw_names, sym_line)
            elif section == "check":
                checks.append(_parse_check(line, lineno))
            else:
                raws = line.split()
                if len(raws) < 2:
                    raise InputError("[compare] 每行至少两个名字")
                compares.append((lineno, [norm(r) for r in raws], raws))
        except InputError as exc:
            errors.append("第 %d 行：%s" % (lineno, exc))
    if len(errors) == 1:
        raise InputError(errors[0])
    if errors:
        raise InputError(
            "共 %d 处\n%s" % (len(errors), "\n".join("  " + e for e in errors))
        )
    return syms, raw_names, checks, compares


# ---------------------------------------------------------------- 检查


def _side_labels(n):
    return ["左边", "右边"] if n == 2 else ["第 %d 项" % (i + 1) for i in range(n)]


def run(syms, checks, compares, out=sys.stdout):
    failures = 0
    known = {c: DIMLESS for c in BUILTIN_CONSTANTS}
    known.update(syms)

    if checks:
        out.write("量纲检查 / dimension checks\n")
    for chk in checks:
        key = norm(chk.name) if chk.name else None
        is_new_name = key is not None and key not in known

        if is_new_name and len(chk.parts) == 2:  # 定义：名字 = 表达式
            missing = _undeclared(chk.trees[1:], known)
            try:
                if missing:
                    raise DimError(_undeclared_error(missing))
                if _is_zero_literal(chk.trees[1]):
                    dim = chk.expect if chk.expect is not None else DIMLESS
                else:
                    dim = dim_of(chk.trees[1], known)
            except DimError as exc:
                out.write("  FAIL  %-14s 第 %d 行：%s\n" % (chk.name, chk.lineno, exc))
                failures += 1
                continue
            known[key] = dim
            if chk.expect is None:
                out.write("  ----  %-14s [%s]\n" % (chk.name, dim))
            elif dim == chk.expect:
                out.write("  pass  %-14s [%s]\n" % (chk.name, dim))
            else:
                out.write(
                    "  FAIL  %-14s 第 %d 行：得到 [%s]，声明的是 [%s]\n"
                    % (chk.name, chk.lineno, dim, chk.expect)
                )
                failures += 1
            continue

        # 方程或不等式：各边量纲必须相同。
        if is_new_name:  # 名字 = 左边 == 右边
            label, texts, trees = chk.name, chk.parts[1:], chk.trees[1:]
            shown = " ".join(" ".join(p) for p in zip(chk.ops[1:], texts[1:]))
            shown = "%s %s" % (texts[0], shown)
        else:
            label, texts, trees, shown = "(方程)", chk.parts, chk.trees, chk.text
        labels = _side_labels(len(trees))
        missing = _undeclared(trees, known)
        if missing:
            out.write(
                "  FAIL  %-14s 第 %d 行：%s：%s\n"
                % (label, chk.lineno, shown, _undeclared_error(missing))
            )
            failures += 1
            continue
        dims, bad = [], None
        for side, text, tree in zip(labels, texts, trees):
            if _is_zero_literal(tree):
                dims.append(None)
                continue
            try:
                dims.append(dim_of(tree, known))
            except DimError as exc:
                bad = "%s %s 内部：%s" % (side, text, exc)
                break
        if bad:
            out.write("  FAIL  %-14s 第 %d 行：%s：%s\n" % (label, chk.lineno, shown, bad))
            failures += 1
            continue
        present = [d for d in dims if d is not None]
        if len(set(present)) > 1:
            out.write(
                "  FAIL  %-14s 第 %d 行：%s：两边量纲不同\n" % (label, chk.lineno, shown)
            )
            for side, text, d in zip(labels, texts, dims):
                shown_dim = "0，与任何量纲相容" if d is None else d
                out.write("          %-6s %-18s [%s]\n" % (side, text, shown_dim))
            failures += 1
            continue
        if present:
            common = present[0]
        else:  # 各边都是 0
            common = chk.expect if chk.expect is not None else DIMLESS
        if is_new_name:
            known[key] = common
        note = "（写成 0 的一边与任何量纲相容）" if None in dims and present else ""
        if chk.expect is not None and common != chk.expect:
            out.write(
                "  FAIL  %-14s 第 %d 行：%s：两边同为 [%s]，声明的是 [%s]\n"
                % (label, chk.lineno, shown, common, chk.expect)
            )
            failures += 1
        else:
            out.write("  pass  %-14s %s：两边同为 [%s]%s\n" % (label, shown, common, note))

    if compares:
        out.write("同量纲比较 / comparability\n")
    check_names = {norm(c.name) for c in checks if c.name}
    for lineno, keys, raws in compares:
        missing = [r for k, r in zip(keys, raws) if k not in known]
        if missing:
            why = [
                "%s（它所在的 [check] 行没有通过）" % r
                if norm(r) in check_names
                else "%s（文件里没有这个名字）" % r
                for r in missing
            ]
            out.write("  FAIL  第 %d 行：未定义的名字 %s\n" % (lineno, "、".join(why)))
            failures += 1
            continue
        dims = {r: known[k] for k, r in zip(keys, raws)}
        distinct = set(dims.values())
        if len(distinct) == 1:
            out.write(
                "  pass  %s 同为 [%s]，比值无量纲\n"
                % (" / ".join(raws), next(iter(distinct)))
            )
        else:
            out.write("  FAIL  第 %d 行：以下各项量纲不同，不能直接比大小\n" % lineno)
            for r in raws:
                out.write("          %-14s [%s]\n" % (r, dims[r]))
            failures += 1

    return failures


def process(text, out=sys.stdout, err=sys.stderr):
    """跑一份输入文本，返回退出状态。"""
    if text.startswith("﻿"):
        text = text[1:]
    try:
        syms, raw_names, checks, compares = parse_input(text)
    except InputError as exc:
        err.write("输入无法解析：%s\n" % exc)
        return 2
    if not syms and not checks and not compares:
        err.write(
            "输入无法解析：没有任何内容。至少要有 [symbols] 和一行 [check] 或 [compare]。\n"
        )
        return 2
    if not checks and not compares:
        out.write("符号表 / symbols\n")
        for key, dim in syms.items():
            out.write("  ----  %-14s [%s]\n" % (raw_names[key], dim))
        out.write(
            "结果：只核对了 [symbols] 的量纲写法（%d 个符号）；"
            "没有 [check] 或 [compare]，没有检查任何式子。\n" % len(syms)
        )
        return 0
    failures = run(syms, checks, compares, out)
    if failures:
        out.write("结果：%d 处不一致。\n" % failures)
        return 1
    out.write("结果：全部通过。量纲一致不等于物理正确。\n")
    return 0


# ---------------------------------------------------------------- 自检

SELFTEST = r"""
[symbols]
rho   = M L^-3
U     = L T^-1
Len   = L
mu    = M L^-1 T^-1
g     = L T^-2
sigma = M T^-2
h     = M T^-3 K^-1
k_s   = M L T^-3 K^-1
E     = M L^2 T^-2
kT    = M L^2 T^-2

[check]
Re         = rho*U*Len/mu           ; 1
inertia    = rho*U^2*Len^2          ; M L T^-2
viscous    = mu*U*Len               ; M L T^-2
gravity    = rho*g*Len^3            ; M L T^-2
cap_length = sqrt(sigma/(rho*g))    ; L
period     = 2*3.14159*sqrt(Len/g)  ; T
Biot       = h*Len/k_s              ; 1
boltz      = exp(-E/kT)             ; 1

[compare]
inertia viscous gravity
"""

_ENERGY = "[symbols]\nm = M\ng = L T^-2\nh = L\nv = L T^-1\n[check]\n"
_FORCES = "[symbols]\nm = M\ng = L T^-2\nT = M L T^-2\na = L T^-2\n"
_SPRING = "[symbols]\nm = M\ng = L T^-2\nk = M T^-2\nx = L\n[check]\n"

# (说明, 输入, 期望退出状态, 输出里必须出现的片段；以 ! 开头表示不得出现)
SELFTEST_CASES = [
    ("正例：定义、期望量纲、同量纲比较", SELFTEST, 0, ["全部通过"]),
    # 原有的五个反例
    ("加减量纲不同", "[symbols]\nU = L T^-1\n[check]\nbad = U + 1\n", 1, ["量纲不同"]),
    ("超越函数宗量带量纲", "[symbols]\nE = M L^2 T^-2\n[check]\nbad = exp(E)\n", 1, ["无量纲"]),
    ("声明的期望与实际不符", "[symbols]\nU = L T^-1\n[check]\nbad = U ; L\n", 1, ["声明的是"]),
    ("未声明的符号", "[symbols]\nU = L T^-1\n[check]\nbad = U*q\n", 1, ["没有在 [symbols]"]),
    ("一行里的未声明符号一次列全", "[symbols]\nm = M\n[check]\nm*g*h == 1/2*m*v^2\n", 1,
     ["'g'、'h'、'v' 没有在 [symbols]"]),
    ("写成 0 的定义与任何期望量纲相容", "[symbols]\nt = T\n[check]\nv0 = 0 ; L T^-1\n", 0,
     ["全部通过"]),
    (
        "compare 的各项量纲不同",
        "[symbols]\nF = M L T^-2\nW = M L^2 T^-2\n[check]\nf = F\nw = W\n[compare]\nf w\n",
        1,
        ["不能直接比大小"],
    ),
    # 审计回归：[check] 里的方程
    ("方程两边量纲不同（m*g*h = 1/2*m*v）", _ENERGY + "m*g*h = 1/2*m*v\n", 1,
     ["两边量纲不同", "!全部通过"]),
    ("方程两边一致（m*g*h = 1/2*m*v^2）", _ENERGY + "m*g*h = 1/2*m*v^2\n", 0,
     ["两边同为 [M L^2 T^-2]"]),
    ("== 写法的方程", _ENERGY + "m*g*h == 1/2*m*v\n", 1, ["两边量纲不同"]),
    (
        "左边是已声明的符号（F = m*v）",
        "[symbols]\nF = M L T^-2\nm = M\nv = L T^-1\n[check]\nF = m*v\n",
        1,
        ["两边量纲不同"],
    ),
    ("带名字的方程（eq1 = m*g - T = m*a）",
     _FORCES + "[check]\neq1 = m*g - T = m*a\nw = m*g\n[compare]\neq1 w\n", 0,
     ["两边同为 [M L T^-2]", "全部通过"]),
    ("方程的一边是 0", _SPRING + "m*g - k*x == 0\n", 0, ["全部通过"]),
    ("一边是 0，另一边内部不自洽", _SPRING + "m*g - k == 0\n", 1, ["相加减的两项量纲不同"]),
    (
        "不等式两边一致",
        "[symbols]\nf = M L T^-2\nmu_s = 1\nNn = M L T^-2\n[check]\nf <= mu_s*Nn\n",
        0,
        ["全部通过"],
    ),
    (
        "不等式两边不一致",
        "[symbols]\nf = M L T^-2\nmu_s = 1\n[check]\nf <= mu_s\n",
        1,
        ["两边量纲不同"],
    ),
    # 审计回归：分数指数
    ("(g*d)^1/2 有歧义，拒绝", "[symbols]\ng = L T^-2\nd = L\n[check]\nvt = (g*d)^1/2\n",
     2, ["歧义"]),
    ("m*v^2/2 有歧义，拒绝", _ENERGY + "KE = m*v^2/2\n", 2, ["歧义"]),
    ("(g*d)^(1/2) 是半次方", "[symbols]\ng = L T^-2\nd = L\n[check]\nvt = (g*d)^(1/2) ; L T^-1\n",
     0, ["pass  vt"]),
    ("[symbols] 里的 L^1/2 仍是半次方", "[symbols]\nq = L^1/2\n[check]\nr = q^2 ; L\n",
     0, ["全部通过"]),
    # 审计回归：NFKC
    ("µ（U+00B5）声明后可用",
     "[symbols]\nµ = M L^-1 T^-1\nU = L T^-1\nd = L\n[check]\nF = µ*U*d ; M L T^-2\n",
     0, ["全部通过"]),
    ("ℓ 声明后可用", "[symbols]\nℓ = L\ng = L T^-2\n[check]\nT0 = 2*pi*sqrt(ℓ/g) ; T\n",
     0, ["全部通过"]),
    ("全角字母声明后可用", "[symbols]\nｖ = L T^-1\nt = T\n[check]\ns = ｖ*t ; L\n",
     0, ["全部通过"]),
    ("µ 与 μ 同时声明，按输入错误拒绝", "[symbols]\nµ = M\nμ = L\n[check]\nx = μ\n",
     2, ["NFKC"]),
    # 审计回归：语法错误退出 2，不算不一致
    ("表达式语法错误退出 2", _FORCES + "[check]\neq1 = m*g - \n", 2, ["语法错误", "!不一致"]),
    ("不认识的函数退出 2", "[symbols]\nx = 1\n[check]\ny = besselj0(x)\n", 2, ["不认识的函数"]),
    ("关键字当符号名", "[symbols]\nlambda = L\n[check]\nk = 1/lambda\n", 2, ["关键字"]),
    ("同一符号两个量纲", "[symbols]\nT = T\nT = K\n[check]\nx = T\n", 2, ["又声明为"]),
    ("空输入", "", 2, ["没有任何内容"]),
    ("只有 [symbols]", "[symbols]\nm = M\n", 0, ["没有检查任何式子", "!全部通过"]),
    # 含符号的幂指数
    ("2^(-t/T_half) 通过",
     "[symbols]\nN0 = 1\nt = T\nT_half = T\n[check]\nNt = N0*2^(-t/T_half) ; 1\n", 0, ["全部通过"]),
    ("2^t（t 有量纲）", "[symbols]\nt = T\n[check]\ny = 2^t\n", 1, ["幂指数必须无量纲"]),
    ("x^n（x 有量纲）", "[symbols]\nx = L\nn = 1\n[check]\ny = x^n\n", 1, ["只能取常数次幂"]),
]


def _run_text(text):
    out, err = io.StringIO(), io.StringIO()
    code = process(text, out, err)
    return code, out.getvalue() + err.getvalue()


def selftest(out=sys.stdout):
    passed = total = 0
    for label, text, want, needles in SELFTEST_CASES:
        total += 1
        code, output = _run_text(text)
        problems = []
        if code != want:
            problems.append("退出状态 %d，应为 %d" % (code, want))
        for needle in needles:
            if needle.startswith("!"):
                if needle[1:] in output:
                    problems.append("不该出现 %r" % needle[1:])
            elif needle not in output:
                problems.append("缺少 %r" % needle)
        if problems:
            out.write("  FAIL  %s：%s\n%s\n" % (label, "；".join(problems), output))
        else:
            passed += 1
            out.write("  pass  %s\n" % label)

    total += 1
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            main(["--help"])
        code = 0
    except SystemExit as exc:
        code = exc.code or 0
    if code == 0 and "[check]" in buf.getvalue():
        passed += 1
        out.write("  pass  --help 打印用法并退出 0\n")
    else:
        out.write("  FAIL  --help：退出状态 %r\n" % code)

    ok = passed == total
    out.write("自检%s（%d/%d）\n" % ("通过" if ok else "未通过", passed, total))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="dimcheck.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("file", nargs="?", help="输入文件；省略时从标准输入读")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检并退出")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        if args.file:
            with open(args.file, encoding="utf-8-sig") as fh:
                text = fh.read()
        else:
            text = sys.stdin.read()
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("读不到输入：%s\n" % exc)
        return 2

    return process(text)


if __name__ == "__main__":
    sys.exit(main())
