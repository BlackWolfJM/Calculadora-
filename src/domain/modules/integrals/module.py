import uuid
from typing import Any

import sympy

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

from .steps import IntegralStepGenerator
from .substitution import analyze_substitution, format_math_latex


class IntegralsModule(MathModule):
    """Caso de uso principal para cálculo de integrales indefinidas."""

    def __init__(self, adapter: SympyAdapter):
        self.adapter = adapter
        self.step_generator = IntegralStepGenerator(adapter)

    def get_id(self) -> str:
        return "integrals"

    def solve(
        self, expression: ExpressionNode, parameters: dict[str, Any]
    ) -> SolutionResponse:
        try:
            var_name = parameters.get("variable", "x")

            # 1. Transformar a SymPy
            expr = self.adapter.ast_to_sympy(expression)
            var = sympy.Symbol(var_name, real=True)

            bounds: tuple[sympy.Expr, sympy.Expr] | None = None
            if "lower_limit" in parameters and "upper_limit" in parameters:
                bounds = (
                    sympy.sympify(parameters["lower_limit"]),
                    sympy.sympify(parameters["upper_limit"]),
                )

            sub_analysis = analyze_substitution(expr, var, bounds)

            # 2. Computar el resultado puramente matemático
            if sub_analysis is not None and sub_analysis.status == "verified":
                if sub_analysis.definite_value is not None:
                    result_expr = sub_analysis.definite_value
                else:
                    result_expr = sub_analysis.antideriv_in_x
            else:
                result_expr = self.adapter.integrate(expr, var)

            # 3. Generar pasos educativos de forma determinista
            steps_outcome = self.step_generator.generate_steps(expr, var, bounds)

            # 4. Formatear la respuesta
            if result_expr.has(sympy.Integral):
                # Integral no evaluada
                payload = MathPayload(
                    canonical_text=str(result_expr),
                    latex=sympy.latex(result_expr),
                )
                return SolutionResponse(
                    response_id=str(uuid.uuid4()),
                    status=ResolutionStatus.UNEVALUATED,
                    calculation=CalculationBlock(
                        status="unevaluated",
                        primary_result=ResultItem(
                            value=payload,
                            label="Integral no evaluada",
                        ),
                    ),
                    procedure=steps_outcome,
                    warnings=[
                        (
                            "No se encontró una antiderivada cerrada dentro del "
                            "alcance disponible."
                        )
                    ],
                )

            if (
                bounds is not None
                and sub_analysis is not None
                and sub_analysis.definite_value is not None
            ):
                result_text = str(result_expr)
                result_latex = format_math_latex(result_expr)
            else:
                # Integral indefinida exitosa, agregando "+ C"
                result_text = str(result_expr) + " + C"
                result_latex = format_math_latex(result_expr) + " + C"

            payload = MathPayload(canonical_text=result_text, latex=result_latex)
            item = ResultItem(value=payload, label="Exact Result")

            calc_block = CalculationBlock(status="success", primary_result=item)

            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.SUCCESS,
                calculation=calc_block,
                procedure=steps_outcome,
            )

        except Exception as e:
            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.FAILED,
                error=str(e),
                calculation=None,
            )
