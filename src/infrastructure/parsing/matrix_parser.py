"""Analiza la sintaxis matricial con una gramática acotada, sin ejecutar texto."""

import ast
import operator
import re
from dataclasses import dataclass

import sympy as sp
from sympy.polys.polyerrors import PolynomialError

from src.domain.errors import StructuredMathError
from src.domain.expressions.ast_nodes import ExpressionNode

MAX_MATRIX_SIZE = 8
MAX_TEXT = 2400
MAX_NODES = 480
MAX_DEPTH = 15

NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z")
NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?\Z")
TOKEN = re.compile(
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z][A-Za-z0-9_]*|\s+|."
)
REPEAT = re.compile(r"(?<![\w.])(\d+)\.(\d*)\((\d+)\)")
ROOT = re.compile(r"\(root of (.+?) near ([+-]?(?:\d+(?:\.\d*)?|\.\d+))\)", re.I)

SCALAR_FUNCTIONS = {
    "sqrt": (sp.sqrt, 1),
    "cbrt": (sp.cbrt, 1),
    "exp": (sp.exp, 1),
    "log": (sp.log, 1),
    "ln": (sp.log, 1),
    "log10": (lambda x: sp.log(x, 10), 1),
    "abs": (sp.Abs, 1),
    "conjugate": (sp.conjugate, 1),
    "arg": (sp.arg, 1),
    "min": (sp.Min, 2),
    "max": (sp.Max, 2),
    "gcd": (sp.gcd, 2),
    "sin": (sp.sin, 1),
    "sen": (sp.sin, 1),
    "cos": (sp.cos, 1),
    "tan": (sp.tan, 1),
    "tg": (sp.tan, 1),
    "cot": (sp.cot, 1),
    "cosh": (sp.cosh, 1),
    "sinh": (sp.sinh, 1),
    "tanh": (sp.tanh, 1),
    "coth": (sp.coth, 1),
    "arccos": (sp.acos, 1),
    "acos": (sp.acos, 1),
    "arcsin": (sp.asin, 1),
    "asin": (sp.asin, 1),
    "arctan": (sp.atan, 1),
    "atan": (sp.atan, 1),
    "arccot": (sp.acot, 1),
    "acot": (sp.acot, 1),
    "arcosh": (sp.acosh, 1),
    "acosh": (sp.acosh, 1),
    "arsinh": (sp.asinh, 1),
    "asinh": (sp.asinh, 1),
    "artanh": (sp.atanh, 1),
    "atanh": (sp.atanh, 1),
    "arcoth": (sp.acoth, 1),
    "acoth": (sp.acoth, 1),
    "re": (sp.re, 1),
    "im": (sp.im, 1),
    "derivative": (sp.diff, 2),
    "factor": (sp.factor, 1),
    "resultant": (sp.resultant, 3),
}

MATRIX_FUNCTIONS = {
    "rank": (sp.MatrixBase.rank, 1),
    "adjugate": (sp.MatrixBase.adjugate, 1),
    "inverse": (sp.MatrixBase.inv, 1),
    "determinant": (sp.MatrixBase.det, 1),
    "transpose": (sp.MatrixBase.transpose, 1),
    "adjoint": (sp.MatrixBase.adjoint, 1),
    "pseudoinverse": (sp.MatrixBase.pinv, 1),
    "trace": (sp.MatrixBase.trace, 1),
}

CONSTANTS = {"pi": sp.pi, "e": sp.E, "i": sp.I, "rad": sp.S.One, "deg": sp.pi / 180}
FUNCTION_NAMES = (
    SCALAR_FUNCTIONS.keys()
    | MATRIX_FUNCTIONS.keys()
    | {
        "root_near",
        "factorial",
    }
)
RESERVED_NAMES = (
    CONSTANTS.keys() | FUNCTION_NAMES | {"A", "B", "X", "Y", "I", "E", "infinity"}
)
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}
ALLOWED_NODES = (
    ast.Expression,
    ast.List,
    ast.Tuple,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Constant,
    ast.Call,
    ast.Compare,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.MatMult,
    ast.UAdd,
    ast.USub,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


@dataclass(frozen=True)
class MatrixInput(ExpressionNode):
    source: str
    tree: ast.expr


def _periodic(match: re.Match) -> str:
    whole, fixed, period = match.groups()
    if len(whole) + len(fixed) + len(period) > 28:
        raise ValueError("El decimal periódico tiene demasiadas cifras.")
    return (
        f"({int(whole)}+{int(fixed or '0')}/{10 ** len(fixed)}"
        f"+{int(period)}/{10 ** len(fixed) * (10 ** len(period) - 1)})"
    )


def normalize_matrix_input(source: str) -> str:
    # Replace postfix operators from the innermost operand outward.
    source = _postfix(source)
    text = source.strip().translate(
        str.maketrans(
            {
                "{": "[",
                "}": "]",
                "−": "-",
                "×": "*",
                "÷": "/",
                "\\": "@",
                "π": "pi",
                "∞": "infinity",
                "°": "*deg",
                "≠": "!=",
                "≤": "<=",
                "≥": ">=",
                "⩽": "<=",
                "⩾": ">=",
            }
        )
    )
    text = ROOT.sub(r"root_near(\1,\2)", text)
    text = REPEAT.sub(_periodic, text)
    text = re.sub(r"(?<![<>!=])=(?!=)", "==", text).replace("^", "**")
    parts = []
    previous = ""
    for match in TOKEN.finditer(text):
        token = match.group()
        if token.isspace():
            continue
        # MatrixCalc commonly writes AX, while ordinary names such as phi are atomic.
        tokens = list(token) if re.fullmatch(r"[ABXY]{2,4}", token) else [token]
        for item in tokens:
            ends_atom = previous in {")", "]"} or bool(
                NAME.fullmatch(previous) or NUMBER.fullmatch(previous)
            )
            starts_atom = item == "(" or bool(
                NAME.fullmatch(item) or NUMBER.fullmatch(item)
            )
            if (
                ends_atom
                and starts_atom
                and not (
                    item == "("
                    and (
                        previous in FUNCTION_NAMES
                        or (len(previous) > 1 and NAME.fullmatch(previous))
                    )
                )
            ):
                parts.append("*")
            parts.append(item)
            previous = item
    return "".join(parts)


def _postfix(source: str) -> str:
    while match := re.search(r"\^\{\*\}|!(?!=)", source):
        end = len(source[: match.start()].rstrip())
        start = end - 1
        if start >= 0 and source[start] in ")]}":
            pairs = {")": "(", "]": "[", "}": "{"}
            stack = []
            while start >= 0:
                char = source[start]
                if char in pairs:
                    stack.append(pairs[char])
                elif stack and char == stack[-1]:
                    stack.pop()
                    if not stack:
                        break
                start -= 1
            if start > 0 and source[start] == "(":
                function = re.search(r"[A-Za-z][A-Za-z0-9_]*$", source[:start])
                if function and function.group() in FUNCTION_NAMES:
                    start = function.start()
        else:
            atom = re.search(
                r"(?:[A-Za-z][A-Za-z0-9_]*|(?:\d+(?:\.\d*)?|\.\d+)"
                r"(?:[eE][+-]?\d+)?)$",
                source[:end],
            )
            start = atom.start() if atom else -1
        if start < 0:
            raise ValueError("El operador posfijo requiere un operando.")
        function = "factorial" if match.group() == "!" else "adjoint"
        source = (
            source[:start] + f"{function}({source[start:end]})" + source[match.end() :]
        )
        if len(source) > MAX_TEXT * 2:
            raise ValueError("La expresión matricial es demasiado larga.")
    return source


def matrix_symbols(parsed: MatrixInput) -> set[str]:
    return {
        node.id
        for node in ast.walk(parsed.tree)
        if isinstance(node, ast.Name) and node.id not in RESERVED_NAMES
    }


def parse_matrix_input(source: str) -> MatrixInput:
    if not source.strip():
        raise ValueError("Escribe una matriz o una expresión matricial.")
    if len(source) > MAX_TEXT:
        raise ValueError(f"La entrada matricial admite hasta {MAX_TEXT} caracteres.")
    if "#" in source or '"' in source or "'" in source:
        raise ValueError("La expresión contiene sintaxis no admitida.")
    normalized = normalize_matrix_input(source)
    try:
        tree = ast.parse(normalized, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Revisa la sintaxis de la matriz o de la expresión.") from exc
    pending = [(tree, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > MAX_DEPTH:
            raise StructuredMathError(
                code="ERR_SECURITY_DEPTH",
                message="La expresión matricial tiene demasiados niveles.",
                line=1,
                column=1,
                end_line=1,
                end_column=2,
                fragment="",
                suggestion="Simplifica la expresión.",
            )
        if count > MAX_NODES:
            raise ValueError("La expresión matricial tiene demasiadas operaciones.")
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError("La expresión contiene sintaxis no admitida.")
        if isinstance(node, ast.Name) and not NAME.fullmatch(node.id):
            raise ValueError("El nombre de una variable no es válido.")
        if isinstance(node, ast.Constant):
            raw = normalized[node.col_offset : node.end_col_offset]
            match = NUMBER.fullmatch(raw)
            if match is None or len(raw) > 32 or abs(int(match[1] or 0)) > 100:
                raise ValueError(
                    "Usa números con hasta 32 caracteres y exponente ±100."
                )
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in FUNCTION_NAMES
        ):
            raise ValueError(
                "La función no está disponible en la calculadora matricial."
            )
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return MatrixInput(normalized, tree.body)


def as_matrix(value) -> sp.ImmutableMatrix:
    if isinstance(value, sp.MatrixBase):
        return sp.ImmutableMatrix(value)
    if not isinstance(value, tuple) or not 1 <= len(value) <= MAX_MATRIX_SIZE:
        raise ValueError(f"Usa una matriz de 1 a {MAX_MATRIX_SIZE} filas.")
    if not isinstance(value[0], tuple) or not 1 <= len(value[0]) <= MAX_MATRIX_SIZE:
        raise ValueError(f"Cada fila debe tener entre 1 y {MAX_MATRIX_SIZE} celdas.")
    width = len(value[0])
    for row in value:
        if not isinstance(row, tuple) or len(row) != width:
            raise ValueError("Todas las filas deben tener el mismo número de celdas.")
        if any(
            not isinstance(cell, sp.Expr) or cell.is_finite is False for cell in row
        ):
            raise ValueError("Cada celda debe contener una expresión escalar.")
    return sp.ImmutableMatrix(value)


def _as_value(value):
    if isinstance(value, tuple):
        return as_matrix(value)
    return value


def _check_scalar(value):
    if value.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        raise ValueError("La operación produjo un valor no finito o indefinido.")
    for number in value.atoms(sp.Rational):
        if max(abs(int(number.p)).bit_length(), int(number.q).bit_length()) > 4096:
            raise ValueError("El resultado numérico supera el límite de cálculo.")
    return value


def matrix_power(matrix: sp.MatrixBase, exponent):
    if matrix.rows != matrix.cols:
        raise ValueError("La potencia requiere una matriz cuadrada.")
    if exponent == sp.oo:
        transform, jordan = matrix.jordan_form()
        diagonal = []
        for index, eigenvalue in enumerate(jordan.diagonal()):
            if eigenvalue == 1:
                if index + 1 < jordan.rows and jordan[index, index + 1] != 0:
                    raise ValueError("La matriz tiene un bloque de Jordan creciente.")
                diagonal.append(1)
            elif (1 - sp.Abs(eigenvalue)).is_positive is True:
                diagonal.append(0)
            else:
                raise ValueError("No se pudo establecer un límite finito de Aⁿ.")
        return (transform * sp.diag(*diagonal) * transform.inv()).applyfunc(sp.simplify)
    if not isinstance(exponent, sp.Expr):
        raise ValueError("El exponente debe ser escalar.")
    if exponent.is_number and (
        exponent.is_real is not True
        or (12 - sp.Abs(exponent)).is_nonnegative is not True
    ):
        raise ValueError("La potencia matricial numérica admite exponentes reales ±12.")
    return matrix.pow(exponent)


class MatrixEvaluator:
    def __init__(self, parsed: MatrixInput, environment: dict | None = None):
        self.parsed = parsed
        self.environment = environment or {}

    def evaluate(self, node: ast.expr | None = None):
        if node is None:
            node = self.parsed.tree
        result = self._evaluate(node)
        if isinstance(result, sp.Expr) and result != sp.oo:
            return _check_scalar(result)
        return result

    def _evaluate(self, node):
        if isinstance(node, ast.Constant):
            return sp.Rational(
                self.parsed.source[node.col_offset : node.end_col_offset]
            )
        if isinstance(node, (ast.List, ast.Tuple)):
            return tuple(self.evaluate(item) for item in node.elts)
        if isinstance(node, ast.Name):
            if node.id in self.environment:
                return self.environment[node.id]
            if node.id == "infinity":
                return sp.oo
            if node.id in ("I", "E") and self.environment:
                operand = next(iter(self.environment.values()))
                return sp.eye(operand.rows)
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
            if node.id in {"A", "B", "X", "Y", "I", "E"}:
                raise ValueError(f"La matriz {node.id} no está definida.")
            return (
                sp.Symbol(node.id, integer=True)
                if node.id in {"k", "n"}
                else (sp.Symbol(node.id))
            )
        if isinstance(node, ast.UnaryOp):
            value = _as_value(self.evaluate(node.operand))
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left = _as_value(self.evaluate(node.left))
            right = _as_value(self.evaluate(node.right))
            return self._binary(node.op, left, right)
        if isinstance(node, ast.Call):
            return self._call(
                node.func.id, [_as_value(self.evaluate(arg)) for arg in node.args]
            )
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ValueError("Usa una sola relación por expresión.")
            left = _as_value(self.evaluate(node.left))
            right = _as_value(self.evaluate(node.comparators[0]))
            relation = {
                ast.Eq: sp.Eq,
                ast.NotEq: sp.Ne,
                ast.Lt: sp.Lt,
                ast.LtE: sp.Le,
                ast.Gt: sp.Gt,
                ast.GtE: sp.Ge,
            }[type(node.ops[0])]
            return relation(left, right)
        raise ValueError("Se requiere una expresión matricial válida.")

    @staticmethod
    def _binary(op, left, right):
        if type(op) in BINARY:
            return BINARY[type(op)](left, right)
        if isinstance(op, ast.Div):
            if isinstance(right, sp.MatrixBase):
                return left * right.inv()
            if right == 0:
                raise ValueError("No se puede dividir por cero.")
            return left / right
        if isinstance(op, ast.MatMult):
            return as_matrix(left).inv() * as_matrix(right)
        if isinstance(left, sp.MatrixBase):
            return matrix_power(left, right)
        if not isinstance(right, sp.Expr) or (
            right.is_number and (100 - sp.Abs(right)).is_nonnegative is not True
        ):
            raise ValueError("Usa exponentes escalares entre -100 y 100.")
        return left**right

    @staticmethod
    def _call(name, args):
        if name == "root_near" and len(args) == 2:
            expression, guess = args
            if not isinstance(expression, sp.Expr) or len(expression.free_symbols) != 1:
                raise ValueError("La raíz aproximada requiere una sola incógnita.")
            return sp.nsolve(expression, next(iter(expression.free_symbols)), guess)
        if name == "factorial" and len(args) == 1:
            if isinstance(args[0], sp.Integer) and 0 <= args[0] <= 100:
                return sp.factorial(args[0])
            raise ValueError("El factorial requiere un entero de 0 a 100.")
        if name in MATRIX_FUNCTIONS:
            function, arity = MATRIX_FUNCTIONS[name]
            if len(args) == arity:
                return function(as_matrix(args[0]))
        elif name in SCALAR_FUNCTIONS:
            function, arity = SCALAR_FUNCTIONS[name]
            if len(args) == arity and all(isinstance(arg, sp.Expr) for arg in args):
                try:
                    return function(*args)
                except PolynomialError as exc:
                    raise ValueError(
                        "La función requiere una expresión polinómica."
                    ) from exc
        raise ValueError(f"Revisa los argumentos de {name}.")
