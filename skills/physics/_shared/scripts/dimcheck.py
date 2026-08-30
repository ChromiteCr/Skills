#!/usr/bin/env python3
"""dimcheck.py — 量纲一致性检查器 / dimensional consistency checker.

只用 Python 标准库。给一份符号量纲表和若干表达式，确定性地回答三件事：

1. 每个表达式的量纲是什么，与声明的期望是否一致；
2. 加减号两侧的量纲是否相同（不同就是漏项、多项或抄错）；
3. 指数、对数、三角函数的宗量是否无量纲（这是最常见的隐藏错误）。

它**不判断物理是否正确**。量纲通过只说明这条式子还没被最便宜的一关筛掉。

输入文件格式（`#` 起注释，空行忽略）::

    [symbols]
    rho = M L^-3
    U   = L T^-1
    L   = L
    mu  = M L^-1 T^-1

    [check]
    Re      = rho*U*L/mu        ; 1
    inertia = rho*U^2*L^2       ; M L T^-2
    viscous = mu*U*L

    [compare]
    inertia viscous

基本量纲：`M` 质量、`L` 长度、`T` 时间、`I` 电流、`K` 热力学温度、
`N` 物质的量、`J` 发光强度。无量纲写 `1`。指数可为整数或分数（`L^1/2`）。

用法::

    python3 dimcheck.py problem.dim
    python3 dimcheck.py --selftest

退出状态 0 表示全部通过，1 表示存在不一致，2 表示输入本身无法解析。
"""

import argparse
import ast
import re
import sys
from fractions import Fraction

BASE = ("M", "L", "T", "I", "K", "N", "J")

# 宗量必须无量纲、结果也无量纲的函数。
TRANSCENDENTAL = {
    "exp", "log", "ln", "log10", "log2",
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "erf",
}
# 保持量纲的一元函数。
DIM_PRESERVING = {"abs", "-", "+"}


class DimError(Exception):
    pass


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


def parse_dim(text, where=""):
    """把 'M L^-3' 解析成 Dim。"""
    text = text.strip()
    if text in ("1", "-", ""):
        return DIMLESS
    out = {}
    for token in text.replace("*", " ").split():
        m = _TERM.match(token)
        if not m:
            raise DimError("%s无法解析量纲片段 %r" % (where, token))
        sym, exp = m.group(1), m.group(2)
        if sym not in BASE:
            raise DimError(
                "%s未知基本量纲 %r（可用：%s）" % (where, sym, " ".join(BASE))
            )
        out[sym] = out.get(sym, Fraction(0)) + Fraction(exp if exp else 1)
    return Dim(out)


# ---------------------------------------------------------------- 表达式求量纲


def _const_value(node):
    """只对纯数字子表达式求值，用于幂指数。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(node.value).limit_denominator(10 ** 6)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _const_value(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = _const_value(node.left), _const_value(node.right)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            if b == 0:
                raise DimError("指数里出现除以零")
            return a / b
    raise DimError("幂指数必须是常数；这里不是")


def dim_of(node, syms):
    if isinstance(node, ast.Expression):
        return dim_of(node.body, syms)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return DIMLESS
        raise DimError("不支持的常量 %r" % (node.value,))

    if isinstance(node, ast.Name):
        if node.id not in syms:
            raise DimError("符号 %r 没有在 [symbols] 里声明量纲" % node.id)
        return syms[node.id]

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, (ast.UAdd, ast.USub)):
            return dim_of(node.operand, syms)
        raise DimError("不支持的一元运算")

    if isinstance(node, ast.BinOp):
        op = node.op
        if isinstance(op, ast.Pow):
            base = dim_of(node.left, syms)
            n = _const_value(node.right)
            return base ** n
        left = dim_of(node.left, syms)
        if isinstance(op, ast.Mult):
            return left * dim_of(node.right, syms)
        if isinstance(op, ast.Div):
            return left / dim_of(node.right, syms)
        if isinstance(op, (ast.Add, ast.Sub)):
            right = dim_of(node.right, syms)
            if left != right:
                raise DimError(
                    "相加减的两项量纲不同：左 [%s]，右 [%s]" % (left, right)
                )
            return left
        raise DimError("不支持的二元运算 %s" % type(op).__name__)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise DimError("只支持形如 f(x) 的函数调用")
        fname = node.func.id
        if node.keywords:
            raise DimError("函数不接受关键字参数")
        if fname == "sqrt":
            if len(node.args) != 1:
                raise DimError("sqrt 需要恰好一个参数")
            return dim_of(node.args[0], syms) ** Fraction(1, 2)
        if fname in TRANSCENDENTAL:
            for arg in node.args:
                d = dim_of(arg, syms)
                if not d.dimensionless:
                    raise DimError(
                        "%s() 的宗量必须无量纲，实际是 [%s]" % (fname, d)
                    )
            return DIMLESS
        if fname == "abs":
            if len(node.args) != 1:
                raise DimError("abs 需要恰好一个参数")
            return dim_of(node.args[0], syms)
        raise DimError("未知函数 %r" % fname)

    raise DimError("表达式里出现不支持的语法节点 %s" % type(node).__name__)


def eval_expr(expr, syms):
    src = expr.replace("^", "**")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        raise DimError("表达式语法错误：%s" % exc.msg)
    return dim_of(tree, syms)


# ---------------------------------------------------------------- 输入文件


def parse_input(text):
    syms, checks, compares = {}, [], []
    section = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            if section not in ("symbols", "check", "compare"):
                raise DimError("第 %d 行：未知小节 %r" % (lineno, section))
            continue
        if section is None:
            raise DimError("第 %d 行：内容出现在任何小节之前" % lineno)

        if section == "symbols":
            if "=" not in line:
                raise DimError("第 %d 行：应为 '符号 = 量纲'" % lineno)
            name, _, dim = line.partition("=")
            name = name.strip()
            if not name.isidentifier():
                raise DimError("第 %d 行：%r 不是合法符号名" % (lineno, name))
            syms[name] = parse_dim(dim, "第 %d 行：" % lineno)

        elif section == "check":
            expect = None
            body = line
            if ";" in line:
                body, _, exp_text = line.partition(";")
                expect = parse_dim(exp_text, "第 %d 行期望值：" % lineno)
            if "=" not in body:
                raise DimError("第 %d 行：应为 '名字 = 表达式 [; 期望量纲]'" % lineno)
            name, _, expr = body.partition("=")
            checks.append((lineno, name.strip(), expr.strip(), expect))

        else:  # compare
            names = line.split()
            if len(names) < 2:
                raise DimError("第 %d 行：[compare] 每行至少两个名字" % lineno)
            compares.append((lineno, names))

    return syms, checks, compares


def run(syms, checks, compares, out=sys.stdout):
    failures = 0
    known = dict(syms)

    if checks:
        out.write("量纲检查 / dimension checks\n")
    for lineno, name, expr, expect in checks:
        try:
            dim = eval_expr(expr, known)
        except DimError as exc:
            out.write("  FAIL  %-14s 第 %d 行：%s\n" % (name, lineno, exc))
            failures += 1
            continue
        known[name] = dim
        if expect is None:
            out.write("  ----  %-14s [%s]\n" % (name, dim))
        elif dim == expect:
            out.write("  pass  %-14s [%s]\n" % (name, dim))
        else:
            out.write(
                "  FAIL  %-14s 第 %d 行：得到 [%s]，声明的是 [%s]\n"
                % (name, lineno, dim, expect)
            )
            failures += 1

    if compares:
        out.write("同量纲比较 / comparability\n")
    for lineno, names in compares:
        missing = [n for n in names if n not in known]
        if missing:
            out.write(
                "  FAIL  第 %d 行：未定义的名字 %s\n" % (lineno, ", ".join(missing))
            )
            failures += 1
            continue
        dims = {n: known[n] for n in names}
        distinct = set(dims.values())
        if len(distinct) == 1:
            out.write(
                "  pass  %s 同为 [%s]，比值无量纲\n"
                % (" / ".join(names), next(iter(distinct)))
            )
        else:
            out.write("  FAIL  第 %d 行：以下各项量纲不同，不能直接比大小\n" % lineno)
            for n in names:
                out.write("          %-14s [%s]\n" % (n, dims[n]))
            failures += 1

    return failures


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

SELFTEST_MUSTFAIL = [
    # 加减量纲不同
    ("[symbols]\nU = L T^-1\n[check]\nbad = U + 1\n", "量纲不同"),
    # 超越函数宗量带量纲
    ("[symbols]\nE = M L^2 T^-2\n[check]\nbad = exp(E)\n", "无量纲"),
    # 声明的期望与实际不符
    ("[symbols]\nU = L T^-1\n[check]\nbad = U ; L\n", "声明的是"),
    # 未声明的符号
    ("[symbols]\nU = L T^-1\n[check]\nbad = U*q\n", "没有在 [symbols]"),
    # compare 的各项量纲不同
    (
        "[symbols]\nF = M L T^-2\nW = M L^2 T^-2\n"
        "[check]\nf = F\nw = W\n[compare]\nf w\n",
        "不能直接比大小",
    ),
]


def selftest(out=sys.stdout):
    import io

    ok = True
    out.write("=== 正例 ===\n")
    syms, checks, compares = parse_input(SELFTEST)
    failures = run(syms, checks, compares, out)
    if failures:
        out.write("自检失败：正例出现 %d 处不一致\n" % failures)
        ok = False

    out.write("=== 必须被抓到的反例 ===\n")
    for src, needle in SELFTEST_MUSTFAIL:
        buf = io.StringIO()
        try:
            s, c, p = parse_input(src)
            n = run(s, c, p, buf)
        except DimError as exc:
            buf.write(str(exc))
            n = 1
        text = buf.getvalue()
        if n and needle in text:
            out.write("  pass  抓到：%s\n" % needle)
        else:
            out.write("  FAIL  没抓到 %r，实际输出：\n%s\n" % (needle, text))
            ok = False

    out.write("自检%s\n" % ("通过" if ok else "未通过"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="量纲一致性检查器")
    ap.add_argument("file", nargs="?", help="输入文件；省略时从标准输入读")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检并退出")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    except OSError as exc:
        sys.stderr.write("读不到输入：%s\n" % exc)
        return 2

    try:
        syms, checks, compares = parse_input(text)
    except DimError as exc:
        sys.stderr.write("输入无法解析：%s\n" % exc)
        return 2

    failures = run(syms, checks, compares)
    if failures:
        print("结果：%d 处不一致。" % failures)
        return 1
    print("结果：全部通过。量纲一致不等于物理正确。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
