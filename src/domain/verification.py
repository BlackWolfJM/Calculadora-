import sympy

from src.domain.responses import ResolutionStatus, SolutionResponse


class MathVerifier:
    """
    Realiza una verificación matemática independiente para asegurar
    que los resultados reportados o los pasos educativos son consistentes.
    """

    def __init__(self, adapter=None):
        self.adapter = adapter

    def verify_ast(self, response, ast, parameters, operation):
        if not response.calculation or operation not in {"derivatives", "integrals"}:
            return response
        if self.adapter is None:
            raise RuntimeError("Verification backend was not configured")
        return self.attach_verification(
            response, self.adapter.ast_to_sympy(ast), parameters, operation
        )

    def verify_derivative(
        self,
        original_expr: sympy.Expr,
        var: sympy.Symbol,
        calculated_result: str,
        order: int = 1,
    ) -> bool:
        """
        Verifica que el resultado de una derivada coincida con el cálculo directo.
        """
        try:
            expected = sympy.diff(original_expr, var, order)
            symbols = {s.name: s for s in original_expr.free_symbols}
            symbols[var.name] = var
            actual = sympy.sympify(calculated_result, locals=symbols)
            # Verificamos si la diferencia simplificada es cero
            return sympy.simplify(expected - actual) == 0
        except Exception:
            return False

    def verify_integral(
        self, integrand: sympy.Expr, var: sympy.Symbol, calculated_antiderivative: str
    ) -> bool:
        """
        Verifica una integral derivando la antiderivada devuelta y
        comparándola con el integrando.
        """
        try:
            # Quitamos el + C si existe
            if calculated_antiderivative.endswith(" + C"):
                calculated_antiderivative = calculated_antiderivative[:-4]
            symbols = {s.name: s for s in integrand.free_symbols}
            symbols[var.name] = var
            antiderivative = sympy.sympify(calculated_antiderivative, locals=symbols)
            # Derivamos la respuesta
            derived = sympy.diff(antiderivative, var)
            # Comparamos con el integrando original
            return sympy.simplify(integrand - derived) == 0
        except Exception:
            return False

    def attach_verification(
        self,
        response: SolutionResponse,
        original_expr: sympy.Expr,
        parameters: dict,
        operation: str,
    ) -> SolutionResponse:
        """
        Toma una respuesta existente y le adjunta el resultado de la
        verificación matemática.
        """
        if not response.calculation or not response.calculation.primary_result:
            return response
        if response.status == ResolutionStatus.UNEVALUATED:
            return response

        calculated_str = response.calculation.primary_result.value.canonical_text
        var_name = parameters.get("variable", "x")
        var = sympy.Symbol(var_name, real=True)

        is_verified = False
        if operation == "derivatives":
            order = parameters.get("order", 1)
            is_verified = self.verify_derivative(
                original_expr, var, calculated_str, order
            )
        elif operation == "integrals":
            is_verified = self.verify_integral(original_expr, var, calculated_str)
        else:
            # Temporarily do not verify other operations (like equations)
            # until verification is implemented
            return response

        # En caso de fallo en la verificación, podríamos cambiar el status
        # a PARTIAL o advertir.
        from dataclasses import replace

        warnings = list(response.warnings)
        if is_verified:
            ver_text = "Verificado matemáticamente con éxito."
        else:
            ver_text = "No se pudo verificar la equivalencia matemática del resultado."
            warnings.append(ver_text)

        return replace(
            response,
            verification=ver_text,
            warnings=warnings,
            status=ResolutionStatus.SUCCESS_WITH_WARNINGS
            if not is_verified and response.status == ResolutionStatus.SUCCESS
            else response.status,
        )
