"""Backend contract; Qt, persistence and concrete adapters stay outside domain."""

from typing import Any, Protocol

from src.domain.expressions.ast_nodes import ExpressionNode


class MathEngine(Protocol):
    def ast_to_sympy(self, node: ExpressionNode) -> Any: ...
    def diff(self, expr: Any, variable: Any, order: int = 1) -> Any: ...
    def integrate(
        self, expr: Any, variable: Any, limits: tuple | None = None
    ) -> Any: ...
    def solve_equation(self, expr: Any, variable: Any) -> Any: ...
