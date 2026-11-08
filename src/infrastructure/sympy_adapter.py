from collections.abc import Callable

import sympy

from src.domain.expressions.ast_nodes import (
    Add,
    Constant,
    Divide,
    Equals,
    ExpressionNode,
    FunctionCall,
    Multiply,
    Negate,
    NumberLiteral,
    Power,
    Subtract,
    Symbol,
)

FUNCTIONS: dict[str, Callable[[sympy.Expr], sympy.Expr]] = {
    "sin": sympy.sin,
    "sen": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "tg": sympy.tan,
    "ln": sympy.log,
    "sqrt": sympy.sqrt,
    "abs": sympy.Abs,
    "exp": sympy.exp,
    "arcsin": sympy.asin,
    "arcsen": sympy.asin,
    "arccos": sympy.acos,
    "arctan": sympy.atan,
}


class SympyAdapter:
    """
    Adaptador seguro para traducir AST propio a objetos de SymPy.
    Nunca usa eval(), sympify() o parse_expr() con texto de usuario.
    """

    def ast_to_sympy(self, node: ExpressionNode) -> sympy.Expr:
        if isinstance(node, NumberLiteral):
            if isinstance(node.value, int):
                return sympy.Integer(node.value)
            return sympy.Float(node.value)

        elif isinstance(node, Symbol):
            return sympy.Symbol(node.name, real=True)

        elif isinstance(node, Constant):
            if node.name in ("pi", "π"):
                return sympy.pi
            elif node.name == "e":
                return sympy.E
            return sympy.Symbol(node.name, real=True)

        elif isinstance(node, Add):
            return sympy.Add(
                self.ast_to_sympy(node.left), self.ast_to_sympy(node.right)
            )

        elif isinstance(node, Subtract):
            right = sympy.Mul(sympy.Integer(-1), self.ast_to_sympy(node.right))
            return sympy.Add(self.ast_to_sympy(node.left), right)

        elif isinstance(node, Multiply):
            return sympy.Mul(
                self.ast_to_sympy(node.left), self.ast_to_sympy(node.right)
            )

        elif isinstance(node, Divide):
            left = self.ast_to_sympy(node.left)
            right = sympy.Pow(self.ast_to_sympy(node.right), sympy.Integer(-1))
            return sympy.Mul(left, right)

        elif isinstance(node, Power):
            return sympy.Pow(
                self.ast_to_sympy(node.base), self.ast_to_sympy(node.exponent)
            )

        elif isinstance(node, Negate):
            return sympy.Mul(sympy.Integer(-1), self.ast_to_sympy(node.operand))

        elif isinstance(node, FunctionCall):
            return self._convert_function(node)

        elif isinstance(node, Equals):
            return sympy.Eq(self.ast_to_sympy(node.left), self.ast_to_sympy(node.right))

        raise ValueError(f"Nodo AST no soportado por SympyAdapter: {type(node)}")

    def _convert_function(self, node: FunctionCall) -> sympy.Expr:
        name = node.name.lower()
        args = [self.ast_to_sympy(arg) for arg in node.arguments]

        if name == "log10":
            if len(args) != 1:
                raise ValueError("log10 requiere exactamente un argumento")
            return sympy.log(args[0], 10)

        function = FUNCTIONS.get(name)
        if function is None:
            raise ValueError(f"Función no soportada: {node.name}")

        if len(args) != 1:
            raise ValueError(
                f"La función {node.name} requiere exactamente un argumento"
            )

        return function(args[0])

    def diff(
        self, expr: sympy.Expr, variable: sympy.Symbol, order: int = 1
    ) -> sympy.Expr:
        return sympy.diff(expr, variable, order)

    def integrate(
        self, expr: sympy.Expr, variable: sympy.Symbol, limits: tuple | None = None
    ) -> sympy.Expr:
        if limits:
            res = sympy.integrate(expr, (variable, limits[0], limits[1]))
        else:
            res = sympy.integrate(expr, variable)

        def fix_log(arg):
            if not isinstance(arg, sympy.Abs):
                return sympy.log(sympy.Abs(arg))
            return sympy.log(arg)

        return res.replace(sympy.log, fix_log)

    def solve_equation(self, expr: sympy.Expr, variable: sympy.Symbol) -> sympy.Set:
        """
        Resuelve una ecuación (expr = 0 o expr1 = expr2) para la variable dada.
        Retorna un conjunto de soluciones en el dominio de los Reales.
        """
        residual = (
            sympy.simplify(expr.lhs - expr.rhs)
            if isinstance(expr, sympy.Equality)
            else sympy.simplify(expr)
        )
        return sympy.solveset(residual, variable, domain=sympy.S.Reals)
