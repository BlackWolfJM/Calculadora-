from typing import Any, Dict, Protocol

from src.domain.expressions.ast_nodes import ExpressionNode
from src.domain.responses import SolutionResponse


class MathModule(Protocol):
    """
    Contrato que deben cumplir todos los módulos matemáticos
    (Derivadas, Integrales, etc.).
    """

    def get_id(self) -> str:
        """Devuelve el identificador único del módulo."""
        ...

    def solve(
        self, expression: ExpressionNode, parameters: Dict[str, Any]
    ) -> SolutionResponse:
        """
        Resuelve una operación matemática dada una expresión validada en AST
        y parámetros específicos del módulo (ej. variable respecto a la cual derivar).
        """
        ...
