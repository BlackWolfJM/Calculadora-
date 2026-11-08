from src.domain.errors import StructuredMathError
from src.domain.expressions.ast_nodes import (
    Add,
    Constant,
    Divide,
    Equals,
    ExpressionNode,
    FunctionCall,
    ListLiteral,
    Multiply,
    Negate,
    NumberLiteral,
    Power,
    Subtract,
    Symbol,
)


class ASTSecurityValidator:
    """
    Validador de seguridad para prevenir ataques de denegación de servicio (DoS)
    a través de expresiones matemáticas maliciosas.
    """

    def __init__(
        self, max_depth: int = 15, max_nodes: int = 50, max_exponent: float = 100.0
    ):
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_exponent = max_exponent

    def validate(self, ast: ExpressionNode) -> None:
        """
        Recorre el AST y lanza StructuredMathError si excede los límites.
        """
        self._check_node(ast, current_depth=1, node_count=[0])

    def _raise_error(
        self, node: ExpressionNode, code: str, message: str, suggestion: str
    ) -> None:
        line = 1
        column = 1
        end_line = 1
        end_column = 1
        fragment = ""

        if hasattr(node, "span") and node.span:
            line = getattr(node.span, "line", 1)
            column = getattr(node.span, "column", 1)
            end_line = getattr(node.span, "end_line", line)
            end_column = getattr(node.span, "end_column", column + 1)

        raise StructuredMathError(
            code=code,
            message=message,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            fragment=fragment,
            suggestion=suggestion,
        )

    def _check_node(
        self, node: ExpressionNode, current_depth: int, node_count: list[int]
    ) -> None:
        node_count[0] += 1

        if node_count[0] > self.max_nodes:
            self._raise_error(
                node,
                code="ERR_SECURITY_NODES",
                message="La expresión matemática es demasiado compleja.",
                suggestion=(
                    f"Simplifica tu expresión. Se superó el límite de "
                    f"{self.max_nodes} operaciones matemáticas."
                ),
            )

        if current_depth > self.max_depth:
            self._raise_error(
                node,
                code="ERR_SECURITY_DEPTH",
                message=(
                    "La expresión matemática tiene demasiados niveles de anidación."
                ),
                suggestion=(
                    f"Evita usar demasiados paréntesis o funciones anidadas "
                    f"(máximo {self.max_depth} niveles)."
                ),
            )

        if isinstance(node, NumberLiteral):
            return

        elif isinstance(node, Symbol) or isinstance(node, Constant):
            return

        elif isinstance(node, (Add, Subtract, Multiply, Divide, Equals)):
            self._check_node(node.left, current_depth + 1, node_count)
            self._check_node(node.right, current_depth + 1, node_count)

        elif isinstance(node, Negate):
            self._check_node(node.operand, current_depth + 1, node_count)

        elif isinstance(node, ListLiteral):
            for item in node.items:
                self._check_node(item, current_depth + 1, node_count)

        elif isinstance(node, FunctionCall):
            if len(node.arguments) != 1:
                self._raise_error(
                    node,
                    "ERR_FUNCTION_ARITY",
                    f"{node.name} requiere exactamente un argumento.",
                    "Escribe una expresión dentro de los paréntesis.",
                )
            for arg in node.arguments:
                self._check_node(arg, current_depth + 1, node_count)

        elif isinstance(node, Power):
            val = self._bounded_constant_value(node.exponent)
            if val is not None and abs(val) > self.max_exponent:
                self._raise_error(
                    node.exponent,
                    code="ERR_SECURITY_EXPONENT",
                    message=f"El exponente {val} es demasiado grande.",
                    suggestion=(
                        f"Por motivos de rendimiento, los exponentes están "
                        f"limitados a ±{self.max_exponent}."
                    ),
                )

            self._check_node(node.base, current_depth + 1, node_count)
            self._check_node(node.exponent, current_depth + 1, node_count)
        else:
            self._raise_error(
                node,
                "ERR_UNSUPPORTED_NODE",
                "Nodo no admitido.",
                "Utiliza la sintaxis matemática documentada.",
            )

    def _bounded_constant_value(self, node: ExpressionNode) -> float | None:
        if isinstance(node, FunctionCall):
            if node.name == "abs" and len(node.arguments) == 1:
                value = self._bounded_constant_value(node.arguments[0])
                return abs(value) if value is not None else None
            if node.arguments and all(
                self._bounded_constant_value(a) is not None for a in node.arguments
            ):
                self._raise_error(
                    node,
                    "ERR_SECURITY_EXPONENT",
                    "Simplifica el exponente numérico antes de calcular.",
                    "Introduce su valor numérico explícito.",
                )
            return None
        if isinstance(node, NumberLiteral):
            return float(node.value)
        elif isinstance(node, Negate):
            val = self._bounded_constant_value(node.operand)
            return -val if val is not None else None
        elif isinstance(node, Add):
            left = self._bounded_constant_value(node.left)
            right = self._bounded_constant_value(node.right)
            if left is not None and right is not None:
                return left + right
            return None
        elif isinstance(node, Subtract):
            left = self._bounded_constant_value(node.left)
            right = self._bounded_constant_value(node.right)
            if left is not None and right is not None:
                return left - right
            return None
        elif isinstance(node, Multiply):
            left = self._bounded_constant_value(node.left)
            right = self._bounded_constant_value(node.right)
            if left is not None and right is not None:
                return left * right
            return None
        elif isinstance(node, Divide):
            left = self._bounded_constant_value(node.left)
            right = self._bounded_constant_value(node.right)
            if left is not None and right is not None:
                if right == 0:
                    self._raise_error(
                        node,
                        code="ERR_DIVISION_BY_ZERO",
                        message="División por cero detectada.",
                        suggestion=(
                            "Verifica la expresión, no se puede dividir por cero."
                        ),
                    )
                return left / right
            return None
        elif isinstance(node, Power):
            base = self._bounded_constant_value(node.base)
            exp = self._bounded_constant_value(node.exponent)
            if base is not None and exp is not None:
                if base == 1 or exp == 0:
                    return 1.0
                if base == -1 and exp.is_integer():
                    return -1.0 if int(exp) % 2 else 1.0
                if abs(base) > 100 or abs(exp) > 10:
                    return float("inf")
                try:
                    return base**exp
                except Exception:
                    return float("inf")
            return None

        return None
