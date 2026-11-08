import uuid
from typing import Any

import sympy

from src.domain.domain_checks import real_domain
from src.domain.expressions.ast_nodes import ExpressionNode
from src.domain.math_engine import MathEngine as SympyAdapter
from src.domain.modules.protocol import MathModule
from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)

from .steps import EquationStepGenerator


class EquationsModule(MathModule):
    """Módulo para resolver ecuaciones algebraicas."""

    def __init__(self, adapter: SympyAdapter):
        self.adapter = adapter
        self.step_generator = EquationStepGenerator(adapter)

    def get_id(self) -> str:
        return "equations"

    def solve(
        self, expression: ExpressionNode, parameters: dict[str, Any]
    ) -> SolutionResponse:
        try:
            var_name = parameters.get("variable", "x")

            # 1. Transformar a SymPy
            expr = self.adapter.ast_to_sympy(expression)
            var = sympy.Symbol(var_name, real=True)

            # 2. Computar el resultado puramente matemático
            solution_set = self.adapter.solve_equation(expr, var)
            solution_set = solution_set.intersect(
                real_domain(expression, var, self.adapter)
            )

            # 3. Generar pasos educativos
            # Para steps.py deberíamos pasarle el conjunto u otra representación,
            # pero por compatibilidad si es FiniteSet le pasamos la lista de soluciones.
            step_outcome = self.step_generator.generate_steps(expr, var, solution_set)

            # 4. Formatear la respuesta
            if solution_set == sympy.S.Reals:
                result_text = "Todos los números reales son solución"
                result_latex = (
                    "\\text{Todos los números reales son solución (} "
                    "\\mathbb{R} \\text{)}"
                )
            elif solution_set == sympy.EmptySet:
                result_text = "No existe solución real"
                result_latex = "\\text{No existe solución real (} \\emptyset \\text{)}"
            elif isinstance(solution_set, sympy.FiniteSet):
                result_text = ", ".join(
                    [f"{var_name} = {str(sol)}" for sol in solution_set]
                )
                result_latex = ", \\quad ".join(
                    [f"{var_name} = {sympy.latex(sol)}" for sol in solution_set]
                )
            else:
                result_text = str(solution_set)
                result_latex = sympy.latex(solution_set)

            payload = MathPayload(canonical_text=result_text, latex=result_latex)
            item = ResultItem(value=payload, label="Soluciones Exactas")

            calc = CalculationBlock(status="success", primary_result=item)

            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=(
                    ResolutionStatus.UNEVALUATED
                    if solution_set.has(sympy.ConditionSet)
                    else ResolutionStatus.SUCCESS
                ),
                calculation=calc,
                procedure=step_outcome,
            )

        except Exception as e:
            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.FAILED,
                error=str(e),
                calculation=None,
            )
