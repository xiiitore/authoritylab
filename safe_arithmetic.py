"""Bounded arithmetic evaluator adapted from the public xiiitore/xiii project.

This module evaluates a deliberately small mathematical expression language.
It does not use eval(), access the filesystem, or execute arbitrary Python.
"""
from __future__ import annotations

import ast
import math
import operator

MAX_EXPRESSION_LENGTH = 512
MAX_AST_NODES = 64
MAX_AST_DEPTH = 16
MAX_INTEGER_BITS = 256
MAX_ABS_EXPONENT = 100
MAX_ABS_BASE_FOR_POWER = 1_000_000

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_FUNCS = {
    name: getattr(math, name)
    for name in ("sqrt", "log", "log10", "exp", "sin", "cos", "tan", "floor", "ceil")
}
_FUNCS.update(abs=abs, round=round, min=min, max=max)
_CONSTS = {"pi": math.pi, "e": math.e}


def safe_eval(expression: str) -> float:
    """Evaluate bounded arithmetic expressions; reject all other Python syntax."""
    if not isinstance(expression, str):
        raise TypeError("expression must be text")
    if not expression.strip() or len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("expression is empty or exceeds the permitted length")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("invalid mathematical expression") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError("expression contains too many AST nodes")

    def evaluate(node: ast.AST, depth: int = 0) -> int | float:
        if depth > MAX_AST_DEPTH:
            raise ValueError("expression is nested too deeply")
        if isinstance(node, ast.Expression):
            value = evaluate(node.body, depth + 1)
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, int) and node.value.bit_length() > MAX_INTEGER_BITS:
                raise ValueError("numeric literal is too large")
            value = node.value
        elif isinstance(node, ast.Name) and node.id in _CONSTS:
            value = _CONSTS[node.id]
        elif isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left = evaluate(node.left, depth + 1)
            right = evaluate(node.right, depth + 1)
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_ABS_EXPONENT:
                    raise ValueError("exponent is too large")
                if abs(left) > MAX_ABS_BASE_FOR_POWER and right > 1:
                    raise ValueError("power base is too large")
            value = _OPS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            value = _OPS[type(node.op)](evaluate(node.operand, depth + 1))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS
            and not node.keywords
        ):
            value = _FUNCS[node.func.id](*(evaluate(arg, depth + 1) for arg in node.args))
        else:
            raise ValueError("expression contains a disallowed construct")

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("result is not numeric")
        if isinstance(value, int) and value.bit_length() > MAX_INTEGER_BITS:
            raise ValueError("result is too large")
        if not math.isfinite(value):
            raise ValueError("result is not finite")
        return value

    try:
        return evaluate(tree)
    except (ArithmeticError, OverflowError) as exc:
        raise ValueError("arithmetic evaluation failed") from exc


def check_number(expression: str, claimed: int | float, rel_tol: float = 1e-6) -> dict[str, object]:
    """Recompute an expression and compare it with a finite claimed result."""
    if isinstance(claimed, bool) or not isinstance(claimed, (int, float)) or not math.isfinite(claimed):
        raise ValueError("claimed result must be a finite number")
    if (
        isinstance(rel_tol, bool)
        or not isinstance(rel_tol, (int, float))
        or not math.isfinite(rel_tol)
        or rel_tol < 0
        or rel_tol > 1
    ):
        raise ValueError("relative tolerance must be finite and within [0, 1]")
    actual = safe_eval(expression)
    return {
        "expression": expression,
        "claimed": claimed,
        "recomputed": actual,
        "match": math.isclose(actual, claimed, rel_tol=rel_tol, abs_tol=1e-9),
        "abs_diff": abs(actual - claimed),
    }
