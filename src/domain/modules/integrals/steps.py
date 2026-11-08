from __future__ import annotations

import sympy

from src.domain.math_engine import MathEngine as SympyAdapter
from src.domain.modules.integrals.substitution import (
    _is_direct_elementary_in_var,
    analyze_substitution,
)
from src.domain.steps import (
    EducationalStep,
    StepCoverage,
    StepOutcome,
    StepStatus,
)


class IntegralStepGenerator:
    """Explica integrales básicas y declara cobertura parcial."""

    def __init__(self, adapter: SympyAdapter) -> None:
        self.adapter = adapter

    def generate_steps(
        self,
        expr: sympy.Expr,
        var: sympy.Symbol,
        bounds: tuple[sympy.Expr, sympy.Expr] | None = None,
    ) -> StepOutcome:
        try:
            if (
                isinstance(expr, sympy.Integral)
                or bounds is not None
                or not _is_direct_elementary_in_var(expr, var)
            ):
                sub_analysis = analyze_substitution(expr, var, bounds)
                if sub_analysis is not None:
                    if sub_analysis.status == "verified":
                        return StepOutcome(
                            status=StepStatus.SUCCESS,
                            coverage=StepCoverage.COMPLETE,
                            steps=list(sub_analysis.steps),
                        )
                    if sub_analysis.status == "rejected":
                        raw_expr = (
                            expr.function if isinstance(expr, sympy.Integral) else expr
                        )
                        result = self.adapter.integrate(raw_expr, var)
                        return StepOutcome(
                            status=(
                                StepStatus.UNSUPPORTED
                                if result.has(sympy.Integral)
                                else StepStatus.SUCCESS
                            ),
                            coverage=StepCoverage.PARTIAL,
                            steps=list(sub_analysis.steps),
                        )

            result = self.adapter.integrate(expr, var)
            root_step, complete = self._explain(expr, var, "step_0")

            if result.has(sympy.Integral):
                return StepOutcome(
                    status=StepStatus.UNSUPPORTED,
                    coverage=StepCoverage.PARTIAL,
                    steps=[root_step],
                )

            constant_step = EducationalStep(
                step_id="step_c",
                rule_name="Constante de integración",
                explanation=(
                    "Como se trata de una integral indefinida, se añade "
                    "una constante arbitraria C. Todas las funciones que "
                    "solo difieren en una constante tienen la misma "
                    "derivada."
                ),
                before_latex=sympy.latex(result),
                after_latex=f"{sympy.latex(result)} + C",
                sub_steps=[],
            )

            return StepOutcome(
                status=StepStatus.SUCCESS,
                coverage=(StepCoverage.COMPLETE if complete else StepCoverage.PARTIAL),
                steps=[root_step, constant_step],
            )
        except Exception:
            import traceback

            traceback.print_exc()
            return StepOutcome(
                status=StepStatus.FAILED,
                coverage=StepCoverage.UNAVAILABLE,
                steps=[],
            )

    def _before(self, expr: sympy.Expr, var: sympy.Symbol) -> str:
        integral = sympy.Integral(expr, var)
        return sympy.latex(integral)

    def _after(self, expr: sympy.Expr, var: sympy.Symbol) -> str:
        return sympy.latex(self.adapter.integrate(expr, var))

    def _step(
        self,
        step_id: str,
        rule_name: str,
        explanation: str,
        expr: sympy.Expr,
        var: sympy.Symbol,
        sub_steps: list[EducationalStep] | None = None,
    ) -> EducationalStep:
        return EducationalStep(
            step_id=step_id,
            rule_name=rule_name,
            explanation=explanation,
            before_latex=self._before(expr, var),
            after_latex=self._after(expr, var),
            sub_steps=sub_steps or [],
        )

    def _linear_coefficient(
        self,
        argument: sympy.Expr,
        var: sympy.Symbol,
    ) -> sympy.Expr | None:
        derivative = sympy.diff(argument, var)
        if derivative == 0 or derivative.has(var):
            return None
        return derivative

    def _explain(
        self,
        expr: sympy.Expr,
        var: sympy.Symbol,
        prefix: str,
    ) -> tuple[EducationalStep, bool]:
        # Todo lo independiente de la variable actúa como constante.
        if not expr.has(var):
            step = self._step(
                prefix,
                "Integral de una constante",
                (
                    f"La expresión {sympy.latex(expr)} no depende de "
                    f"{sympy.latex(var)}. Integrar una constante k "
                    "produce k multiplicada por la variable."
                ),
                expr,
                var,
            )
            return step, True

        if expr == var:
            step = self._step(
                prefix,
                "Integral de la variable",
                (
                    "Se interpreta la variable como una potencia de "
                    "exponente 1. Al aplicar la regla de la potencia se "
                    "suma uno al exponente y se divide por el nuevo "
                    "exponente: ∫x dx = x²/2."
                ),
                expr,
                var,
            )
            return step, True

        # Linealidad.
        if expr.is_Add:
            children: list[EducationalStep] = []
            complete = True
            for index, term in enumerate(expr.args):
                child, child_complete = self._explain(
                    term,
                    var,
                    f"{prefix}_{index}",
                )
                children.append(child)
                complete = complete and child_complete

            step = self._step(
                prefix,
                "Linealidad de la integral",
                (
                    "La integral de una suma es la suma de las "
                    "integrales. Se integra cada término por separado y "
                    "se añade una sola constante C al final."
                ),
                expr,
                var,
                children,
            )
            return step, complete

        # Potencias y recíprocos.
        if expr.is_Pow:
            base, exponent = expr.as_base_exp()
            coefficient = self._linear_coefficient(base, var)

            if base == var and exponent == -1:
                step = self._step(
                    prefix,
                    "Integral del recíproco",
                    (
                        "El exponente es -1, así que la regla usual de "
                        "potencias no puede aplicarse. Se usa "
                        "∫1/x dx = ln|x|."
                    ),
                    expr,
                    var,
                )
                return step, True

            if exponent == -1 and coefficient is not None:
                step = self._step(
                    prefix,
                    "Recíproco de una función lineal",
                    (
                        "La base tiene derivada constante. Para "
                        "u=ax+b, ∫1/u dx = ln|u|/a. El divisor compensa "
                        "la derivada constante de la función interior."
                    ),
                    expr,
                    var,
                )
                return step, True

            if not exponent.has(var) and exponent != -1:
                if base == var:
                    step = self._step(
                        prefix,
                        "Regla de la potencia",
                        (
                            "Para ∫x^n dx, con n distinto de -1, se "
                            "suma uno al exponente y se divide por el "
                            "nuevo exponente: x^(n+1)/(n+1)."
                        ),
                        expr,
                        var,
                    )
                    return step, True

                if coefficient is not None:
                    step = self._step(
                        prefix,
                        "Potencia de una función lineal",
                        (
                            "La base es lineal y su derivada es una "
                            "constante. Se aplica la regla de potencia a "
                            "la base completa y se divide además por su "
                            "derivada."
                        ),
                        expr,
                        var,
                    )
                    return step, True

            if not base.has(var) and exponent.has(var):
                exp_coefficient = self._linear_coefficient(exponent, var)
                if exp_coefficient is not None:
                    step = self._step(
                        prefix,
                        "Integral de función exponencial",
                        (
                            "La base es constante y el exponente es lineal. "
                            "Para a^u, la integral es a^u / (u' · ln(a)). "
                            f"Aquí dividimos por {sympy.latex(exp_coefficient)}"
                            f"·ln({sympy.latex(base)})."
                        ),
                        expr,
                        var,
                    )
                    return step, True

        # Múltiplo constante.
        if expr.is_Mul:
            independent, dependent = expr.as_independent(
                var,
                as_Add=False,
            )
            if independent != 1 and dependent != 1:
                child, child_complete = self._explain(
                    dependent,
                    var,
                    f"{prefix}_dependent",
                )
                step = self._step(
                    prefix,
                    "Regla del múltiplo constante",
                    (
                        f"El factor {sympy.latex(independent)} no depende "
                        "de la variable de integración. Se conserva "
                        "fuera de la integral mientras se integra el "
                        "factor restante."
                    ),
                    expr,
                    var,
                    [child],
                )
                return step, child_complete

        # Funciones elementales con argumento lineal.
        if len(expr.args) == 1:
            argument = expr.args[0]
            coefficient = self._linear_coefficient(argument, var)

            if coefficient is not None and expr.func == sympy.sin:
                step = self._step(
                    prefix,
                    "Integral del seno lineal",
                    (
                        "Para u=ax+b, ∫sin(u) dx = -cos(u)/a. El "
                        "divisor a compensa la derivada del argumento."
                    ),
                    expr,
                    var,
                )
                return step, True

            if coefficient is not None and expr.func == sympy.cos:
                step = self._step(
                    prefix,
                    "Integral del coseno lineal",
                    (
                        "Para u=ax+b, ∫cos(u) dx = sin(u)/a. El "
                        "divisor a compensa la derivada del argumento."
                    ),
                    expr,
                    var,
                )
                return step, True

            if coefficient is not None and expr.func == sympy.exp:
                step = self._step(
                    prefix,
                    "Integral de la exponencial lineal",
                    (
                        "La exponencial conserva su forma al integrar. "
                        "Para u=ax+b, ∫exp(u) dx = exp(u)/a."
                    ),
                    expr,
                    var,
                )
                return step, True

            if coefficient is not None and expr.func == sympy.tan:
                step = self._step(
                    prefix,
                    "Integral de la tangente lineal",
                    (
                        "Para u=ax+b, la tangente se integra como "
                        "-ln|cos(u)|/a. El divisor a compensa la "
                        "derivada del argumento."
                    ),
                    expr,
                    var,
                )
                return step, True

        # Logaritmo básico por partes.
        if expr.func == sympy.log and expr.args == (var,):
            step = self._step(
                prefix,
                "Integral del logaritmo por partes",
                (
                    "Se usa integración por partes con u=ln(x) y "
                    "dv=dx. Entonces du=dx/x y v=x, por lo que "
                    "∫ln(x)dx = x·ln(x)-∫1dx = x·ln(x)-x."
                ),
                expr,
                var,
            )
            return step, True

        # Integración por Sustitución Simple f(g(x)) * g'(x)
        if expr.is_Mul:
            factors = list(expr.args)
            for i, factor in enumerate(factors):
                inner_func = None
                if (
                    hasattr(factor, "func")
                    and len(factor.args) == 1
                    and factor.func not in (sympy.Add, sympy.Mul)
                ):
                    inner_func = factor.args[0]
                elif factor.is_Pow:
                    base, exp = factor.as_base_exp()
                    if base.has(var) and not exp.has(var):
                        inner_func = base

                if inner_func is not None and inner_func != var:
                    g_prime = sympy.diff(inner_func, var)
                    if g_prime != 0:
                        other_factors = sympy.Mul(*(factors[:i] + factors[i + 1 :]))
                        ratio = sympy.simplify(other_factors / g_prime)

                        if ratio != 0 and not ratio.has(var):
                            u_sym = sympy.Symbol("u")
                            if factor.is_Pow:
                                _, exp = factor.as_base_exp()
                                new_factor = u_sym**exp
                            else:
                                new_factor = factor.func(u_sym)

                            integrand_u = ratio * new_factor
                            child, child_complete = self._explain(
                                integrand_u, u_sym, f"{prefix}_sub"
                            )

                            step = self._step(
                                prefix,
                                "Integración por Sustitución (Cambio de variable)",
                                (
                                    "Se identifica el patrón f(g(x))·g'(x). "
                                    "Hacemos el cambio de variable "
                                    f"u = {sympy.latex(inner_func)}. "
                                    f"Entonces, du = ({sympy.latex(g_prime)}) dx. "
                                    "La integral se transforma en "
                                    f"∫{sympy.latex(integrand_u)} du, "
                                    "que es más directa. Finalmente se deshace "
                                    "el cambio sustituyendo u de vuelta."
                                ),
                                expr,
                                var,
                                [child],
                            )
                            return step, child_complete

        # Resultado no evaluado o método todavía no explicado.
        result = self.adapter.integrate(expr, var)
        if result.has(sympy.Integral):
            explanation = (
                "El motor no encontró una antiderivada cerrada dentro "
                "del alcance disponible. Se conserva la integral sin "
                "evaluar y no se presenta como éxito completo."
            )
        else:
            explanation = (
                "El motor de cálculo obtuvo una antiderivada, pero el "
                "motor educativo todavía no dispone de una secuencia "
                "detallada y verificable para el método utilizado. El "
                "procedimiento se marca como parcial."
            )

        step = self._step(
            prefix,
            "Método de integración todavía no desarrollado",
            explanation,
            expr,
            var,
        )
        return step, False
