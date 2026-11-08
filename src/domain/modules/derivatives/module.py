import uuid
from typing import Any, Dict

import sympy

from src.domain.expressions.ast_nodes import ExpressionNode
from src.domain.math_engine import MathEngine as SympyAdapter
from src.domain.modules.derivatives.steps import DerivativeStepGenerator
from src.domain.modules.protocol import MathModule
from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)


class DerivativesModule(MathModule):
    def __init__(self, sympy_adapter: SympyAdapter) -> None:
        self.adapter = sympy_adapter
        self.step_generator = DerivativeStepGenerator(sympy_adapter)

    def get_id(self) -> str:
        return "derivatives"

    def solve(
        self, expression: ExpressionNode, parameters: Dict[str, Any]
    ) -> SolutionResponse:
        # 1. Extraer parámetros con defaults
        var_name = parameters.get("variable", "x")
        order = parameters.get("order", 1)

        if not isinstance(order, int) or isinstance(order, bool):
            raise ValueError("El orden de derivación debe ser un entero.")

        if not 1 <= order <= 5:
            raise ValueError("El orden de derivación debe estar entre 1 y 5.")

        try:
            # 2. Traducción segura al motor (SymPy)
            sympy_expr = self.adapter.ast_to_sympy(expression)
            sympy_var = sympy.Symbol(var_name, real=True)

            # 3. Operación de derivación
            sympy_result = self.adapter.diff(sympy_expr, sympy_var, order)

            # 4. Formatear la salida para la capa de presentación
            canonical = str(sympy_result)
            latex = sympy.latex(sympy_result)

            payload = MathPayload(canonical_text=canonical, latex=latex)
            result_item = ResultItem(value=payload, label="Derivada")

            calc_block = CalculationBlock(status="SUCCESS", primary_result=result_item)

            # 5. Generar pasos educativos (Traza recursiva estructurada)
            steps_outcome = self.step_generator.generate_steps(
                sympy_expr, sympy_var, order
            )

            # 6. Generar la respuesta bajo el contrato unificado
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
            )
